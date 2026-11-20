"""Removing a family member: one transaction for their medication plans, (optionally) their health data and the
member row itself, plus an archive so kept records can be restored under the SAME member id or erased later."""
import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

import db
import medication_email

PH = db.PH
log = logging.getLogger(__name__)
_COLS = "relation, name, age, gender, conditions, medications, allergies, notes, created"


def ensure_schema():
    conn = db._conn()
    try:
        c = conn.cursor()
        c.execute(
            "CREATE TABLE IF NOT EXISTS family_member_archive (member_id INTEGER NOT NULL, user_hash TEXT NOT NULL, relation TEXT, "
            "name TEXT NOT NULL, age TEXT, gender TEXT, conditions TEXT, medications TEXT, allergies TEXT, notes TEXT, created TEXT, "
            "archived_at TEXT NOT NULL, PRIMARY KEY (user_hash, member_id))"
        )
        conn.commit()
    finally:
        conn.close()


def _numeric(account_id):
    text = str(account_id or "")
    return int(text) if text.isdigit() else None


def delete_member(account_key, account_id, member_id, delete_data=False):
    """Atomically remove the member's medication plans/reminders, the member row and either their health data
    (delete_data=True) or an archive entry that keeps the records restorable. Raises on any failure, nothing is left half-done."""
    ensure_schema(); medication_email.init_schema()
    owner, mid, med_uid = db._hash_user(account_key), int(member_id), _numeric(account_id)
    conn = db._conn(); done = False
    try:
        c = conn.cursor()
        # FOR UPDATE (PostgreSQL) serialises two simultaneous deletes of the same person: the second waits, then finds nothing.
        c.execute(f"SELECT {_COLS} FROM family_members WHERE user_hash={PH} AND id={PH}" + (" FOR UPDATE" if db.USE_POSTGRES else ""), (owner, mid))
        row = c.fetchone()
        if not row:
            return False
        if med_uid is not None:
            uh = db._hash_user(med_uid)
            c.execute(f"SELECT id FROM med_plans WHERE user_hash={PH} AND member_id={PH}", (uh, mid))
            for (pid,) in c.fetchall():
                medication_email.delete_plan_rows(c, med_uid, uh, int(pid))
        if delete_data:
            db.delete_member_data_rows(c, owner, mid)
        else:
            c.execute(f"DELETE FROM family_member_archive WHERE user_hash={PH} AND member_id={PH}", (owner, mid))
            c.execute(f"INSERT INTO family_member_archive (member_id, user_hash, {_COLS}, archived_at) VALUES ({','.join([PH] * 12)})",
                      (mid, owner, *row, datetime.now(timezone.utc).isoformat()))
        c.execute(f"DELETE FROM family_members WHERE user_hash={PH} AND id={PH}", (owner, mid))
        conn.commit(); done = True
    finally:
        if not done:
            conn.rollback()
        conn.close()
    # The COMMIT above succeeded, so the removal HAPPENED. The extra check on a brand-new connection can only reveal a
    # problem (leftovers -> raise) or be unable to run (connection trouble -> log, still success): never report a finished
    # delete as failed just because the follow-up check could not connect.
    leftovers = _leftovers(owner, mid, med_uid)
    if leftovers:
        raise RuntimeError("family_member_delete_not_persisted")
    return True


def _leftovers(owner, mid, med_uid):
    """True if the member row or their medication plans are still there, False if clean, None if it could not be checked."""
    try:
        v = db._conn()
    except db.DB_ERRORS:
        log.warning("Post-delete verification skipped: could not open a connection (delete was committed)")
        return None
    try:
        vc = v.cursor()
        vc.execute(f"SELECT 1 FROM family_members WHERE user_hash={PH} AND id={PH}", (owner, mid))
        left = vc.fetchone() is not None
        if med_uid is not None:
            vc.execute(f"SELECT 1 FROM med_plans WHERE user_hash={PH} AND member_id={PH}", (db._hash_user(med_uid), mid))
            left = left or vc.fetchone() is not None
        return left
    except db.DB_ERRORS:
        log.warning("Post-delete verification skipped: query failed (delete was committed)")
        return None
    finally:
        v.close()


def list_archived(account_key):
    ensure_schema(); owner = db._hash_user(account_key)
    conn = db._conn()
    try:
        c = conn.cursor()
        c.execute(f"SELECT member_id, name, relation, age, gender, archived_at FROM family_member_archive WHERE user_hash={PH} ORDER BY archived_at DESC", (owner,))
        rows = c.fetchall(); out = []
        for mid, name, relation, age, gender, archived_at in rows:
            counts = {}
            for table in ("records", "blood_tests", "vitals"):
                c.execute(f"SELECT COUNT(*) FROM {table} WHERE user_hash={PH} AND member_id={PH}", (owner, mid))
                counts[table] = c.fetchone()[0]
            out.append({"id": mid, "name": name, "relation": relation, "age": age, "gender": gender, "archived_at": archived_at,
                        "records": counts["records"], "blood_tests": counts["blood_tests"], "vitals": counts["vitals"]})
        return out
    finally:
        conn.close()


def restore_member(account_key, member_id):
    """Bring an archived person back under the SAME id, so every kept record is linked again. False if not archived."""
    ensure_schema(); owner, mid = db._hash_user(account_key), int(member_id)
    conn = db._conn(); done = False
    try:
        c = conn.cursor()
        # FOR UPDATE: a simultaneous restore/purge of the same archive row waits here, then finds nothing (one definite winner).
        c.execute(f"SELECT {_COLS} FROM family_member_archive WHERE user_hash={PH} AND member_id={PH}" + (" FOR UPDATE" if db.USE_POSTGRES else ""), (owner, mid))
        row = c.fetchone()
        if not row:
            return False
        c.execute(f"INSERT INTO family_members (id, user_hash, {_COLS}) VALUES ({','.join([PH] * 11)})", (mid, owner, *row))
        c.execute(f"DELETE FROM family_member_archive WHERE user_hash={PH} AND member_id={PH}", (owner, mid))
        conn.commit(); done = True
        return True
    finally:
        if not done:
            conn.rollback()
        conn.close()


def purge_archived(account_key, member_id):
    """Permanently erase an archived person's kept health data and the archive entry, in one transaction."""
    ensure_schema(); owner, mid = db._hash_user(account_key), int(member_id)
    conn = db._conn(); done = False
    try:
        c = conn.cursor()
        c.execute(f"SELECT 1 FROM family_member_archive WHERE user_hash={PH} AND member_id={PH}" + (" FOR UPDATE" if db.USE_POSTGRES else ""), (owner, mid))
        if not c.fetchone():
            return False
        db.delete_member_data_rows(c, owner, mid)
        c.execute(f"DELETE FROM family_member_archive WHERE user_hash={PH} AND member_id={PH}", (owner, mid))
        conn.commit(); done = True
        return True
    finally:
        if not done:
            conn.rollback()
        conn.close()


def register(app, current_user_id, data_user_id_getter, consent_ok, consent_required_json):
    if "family_archive" in app.blueprints:
        return
    bp = Blueprint("family_archive", __name__)

    def _gate():
        if not current_user_id():
            return jsonify({"ok": False, "error": "login_required"}), 401
        return None

    @bp.route("/api/family/archived", methods=["GET"])
    def family_archived_list():
        return _gate() or jsonify({"ok": True, "archived": list_archived(data_user_id_getter())})

    @bp.route("/api/family/archived/<int:mid>/restore", methods=["POST"])
    def family_archived_restore(mid):
        if _gate():
            return _gate()
        if not consent_ok():
            return consent_required_json("/family")
        return jsonify({"ok": True}) if restore_member(data_user_id_getter(), mid) else (jsonify({"ok": False, "error": "not_found"}), 404)

    @bp.route("/api/family/archived/<int:mid>", methods=["DELETE"])
    def family_archived_purge(mid):
        if _gate():
            return _gate()
        return jsonify({"ok": True}) if purge_archived(data_user_id_getter(), mid) else (jsonify({"ok": False, "error": "not_found"}), 404)

    app.register_blueprint(bp)
