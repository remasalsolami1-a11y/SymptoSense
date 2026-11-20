"""Careful clean-up of rows that older versions left behind. Dry-run by default; nothing is deleted without --apply.

    python orphan_cleanup.py                      # report only
    python orphan_cleanup.py --apply              # delete dependents whose analysis no longer exists
    python orphan_cleanup.py --apply --meds       # also delete medication plans of family members that no longer exist
    python orphan_cleanup.py --apply --archive-dangling
                                                  # keep records of vanished members: put them in the archive so they can be restored/erased

Only rows whose parent is provably gone are touched; everything runs in ONE transaction.
"""
import argparse
import json
from datetime import datetime, timezone

import db
import family_archive
import medication_email

PH = db.PH
DEPENDENTS = ("results", "feedback", "followups", "symptom_followups", "symptom_relief_logs")


def _scan(c):
    rep = {"dependents": {}, "dangling_members": [], "orphan_med_plans": []}
    for t in DEPENDENTS:
        if db._table_exists(c, t):
            c.execute(f"SELECT COUNT(*) FROM {t} WHERE record_id IS NOT NULL AND record_id NOT IN (SELECT id FROM records)")
            rep["dependents"][t] = c.fetchone()[0]
    if db._table_exists(c, "ss_analysis_links"):
        c.execute("SELECT COUNT(*) FROM ss_analysis_links WHERE previous_record_id NOT IN (SELECT id FROM records) "
                  "OR current_record_id NOT IN (SELECT id FROM records)")
        rep["dependents"]["ss_analysis_links"] = c.fetchone()[0]
    seen = set()
    for t in ("records", "blood_tests", "vitals"):
        if not db._table_exists(c, t):
            continue
        c.execute(f"SELECT DISTINCT user_hash, member_id FROM {t} WHERE member_id IS NOT NULL AND member_id > 0")
        for owner, mid in c.fetchall():
            if (owner, mid) in seen:
                continue
            c.execute(f"SELECT 1 FROM family_members WHERE user_hash={PH} AND id={PH}", (owner, mid))
            alive = c.fetchone() is not None
            c.execute(f"SELECT 1 FROM family_member_archive WHERE user_hash={PH} AND member_id={PH}", (owner, mid))
            if not alive and c.fetchone() is None:
                seen.add((owner, mid)); rep["dangling_members"].append({"user_hash": owner, "member_id": mid})
    c.execute("SELECT id FROM ss_users")
    for (uid,) in c.fetchall():  # medication tables are keyed by the numeric id, family tables by "account-<id>"
        c.execute(f"SELECT id, member_id FROM med_plans WHERE user_hash={PH} AND member_id > 0", (db._hash_user(uid),))
        for pid, mid in c.fetchall():
            owner = db._hash_user("account-%s" % uid)
            c.execute(f"SELECT 1 FROM family_members WHERE user_hash={PH} AND id={PH}", (owner, mid))
            if c.fetchone() is None:
                rep["orphan_med_plans"].append({"user_id": uid, "plan_id": pid, "member_id": mid})
    return rep


def run(apply=False, meds=False, archive_dangling=False):
    db.init_db(); medication_email.init_schema(); family_archive.ensure_schema()
    conn = db._conn(); done = False
    try:
        c = conn.cursor()
        rep = _scan(c)
        rep["applied"] = bool(apply)
        if apply:
            for t, n in rep["dependents"].items():
                if n and t != "ss_analysis_links":
                    c.execute(f"DELETE FROM {t} WHERE record_id IS NOT NULL AND record_id NOT IN (SELECT id FROM records)")
            if rep["dependents"].get("ss_analysis_links"):
                c.execute("DELETE FROM ss_analysis_links WHERE previous_record_id NOT IN (SELECT id FROM records) "
                          "OR current_record_id NOT IN (SELECT id FROM records)")
            if meds:
                for p in rep["orphan_med_plans"]:
                    medication_email.delete_plan_rows(c, int(p["user_id"]), db._hash_user(p["user_id"]), int(p["plan_id"]))
            if archive_dangling:
                now = datetime.now(timezone.utc).isoformat()
                for d in rep["dangling_members"]:
                    c.execute(f"INSERT INTO family_member_archive (member_id, user_hash, relation, name, archived_at) VALUES ({','.join([PH] * 5)})",
                              (d["member_id"], d["user_hash"], "other", "فرد محذوف سابقًا / Previously removed person #%s" % d["member_id"], now))
            conn.commit()
        done = True
        return rep
    finally:
        if not done:
            conn.rollback()
        conn.close()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--meds", action="store_true")
    ap.add_argument("--archive-dangling", action="store_true")
    a = ap.parse_args(argv)
    print(json.dumps(run(a.apply, a.meds, a.archive_dangling), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
