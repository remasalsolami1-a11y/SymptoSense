"""Real PostgreSQL checks for member removal, archive, snooze uniqueness and clean-up.

Skipped unless TEST_DATABASE_URL points at a disposable PostgreSQL database, e.g.
    TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/sstest pytest test_postgres_family_delete.py
"""
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone

import pytest

if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

pytestmark = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set")


@pytest.fixture(scope="module")
def pg():
    import db, medication_email, family_archive
    if not db.USE_POSTGRES:
        pytest.skip("database layer is not on PostgreSQL in this process")
    db.init_db(); medication_email.init_schema(); family_archive.ensure_schema()
    return db


def _world(db, tag):
    import medication_email
    uid_row = None
    email = "%s-%s@example.test" % (tag, uuid.uuid4().hex[:8])
    uid, err = db.create_ss_user(email, "PG Test", "StrongPassword123!")
    assert uid and not err
    conn = db._conn(); c = conn.cursor()
    c.execute(f"UPDATE ss_users SET email_verified=1,status='active' WHERE id={db.PH}", (uid,))
    conn.commit(); conn.close()
    owner = "account-%s" % uid
    mid = db.save_member(owner, "other", "Child", "8", "f")
    now = datetime.now(timezone.utc)
    pid = medication_email.save_plan(uid, {"med_name": "M", "times": ["08:00"], "timezone": "UTC", "start_date": now.date().isoformat(), "member_id": mid})
    pid = int(pid.get("id") if isinstance(pid, dict) else pid)
    rid = db.save_record(owner, "ar", 8, "female", ["headache"], "1 day", 1, "monitor", member_id=mid)
    rid = rid if isinstance(rid, int) else int(rid["id"] if isinstance(rid, dict) else rid)
    db.save_result(owner, rid, {"detail": "x"}); db.save_followup(owner, rid, "better")
    db.save_symptom_relief_log(owner, rid, "headache", "rest"); db.save_blood_test(owner, {"Hb": 12.5}, member_id=mid)
    return uid, owner, mid, pid, rid


def _count(db, table, owner, rid):
    conn = db._conn(); c = conn.cursor()
    c.execute(f"SELECT COUNT(*) FROM {table} WHERE user_hash={db.PH} AND record_id={db.PH}", (db._hash_user(owner), rid))
    n = c.fetchone()[0]; conn.close()
    return n


class _FailOn:
    """Wrap db._conn so a statement beginning with `prefix` raises like a database error would."""
    def __init__(self, db, prefix):
        import psycopg2
        self.db, self.prefix, self.err = db, prefix, psycopg2.OperationalError("injected failure")
        self.real = db._conn

    def __enter__(self):
        outer = self
        class Cur:
            def __init__(self, cur): self._c = cur
            def execute(self, sql, *a):
                if sql.startswith(outer.prefix):
                    raise outer.err
                return self._c.execute(sql, *a)
            def __getattr__(self, n): return getattr(self._c, n)
        class Conn:
            def __init__(self, conn): self._k = conn
            def cursor(self): return Cur(self._k.cursor())
            def __getattr__(self, n): return getattr(self._k, n)
        self.db._conn = lambda: Conn(self.real())
        return self

    def __exit__(self, *exc):
        self.db._conn = self.real


def test_pg_member_removal_rolls_back_everything_when_the_medication_step_fails(pg):
    import psycopg2, family_archive, medication_email
    uid, owner, mid, pid, rid = _world(pg, "pg1")
    with _FailOn(pg, "DELETE FROM med_plans"):
        with pytest.raises(psycopg2.OperationalError):
            family_archive.delete_member(owner, uid, mid, delete_data=True)
    assert pg.get_member(owner, mid) and pg.get_records(owner, member_id=mid) and pg.load_result(owner, rid)
    assert any(p["id"] == pid for p in medication_email.list_plans(uid, active_only=False))
    assert _count(pg, "symptom_followups", owner, rid) == 1 and _count(pg, "symptom_relief_logs", owner, rid) == 1
    assert family_archive.delete_member(owner, uid, mid, delete_data=True)          # the pool is healthy and a retry succeeds
    assert not pg.get_member(owner, mid) and not pg.get_records(owner, member_id=mid) and _count(pg, "results", owner, rid) == 0


def test_pg_standalone_health_data_delete_is_atomic(pg):
    import psycopg2
    uid, owner, mid, pid, rid = _world(pg, "pg2")
    with _FailOn(pg, "DELETE FROM vitals"):
        with pytest.raises(psycopg2.OperationalError):
            pg.delete_member_data(owner, mid)
    assert pg.get_records(owner, member_id=mid) and pg.get_blood_tests(owner, member_id=mid) and pg.load_result(owner, rid)
    pg.delete_member_data(owner, mid)
    assert not pg.get_records(owner, member_id=mid) and not pg.get_blood_tests(owner, member_id=mid)


def test_pg_archive_restore_purge_and_ids(pg):
    import family_archive, medication_email
    uid, owner, mid, pid, rid = _world(pg, "pg3")
    assert family_archive.delete_member(owner, uid, mid, delete_data=False)
    assert pg.get_records(owner, member_id=mid) and [a for a in family_archive.list_archived(owner) if a["id"] == mid]
    other = pg.save_member(owner, "other", "Child", "8", "f")
    assert other != mid                                                                # same name, new person, new id
    assert family_archive.restore_member(owner, mid)                                    # explicit id into a SERIAL column
    assert pg.get_member(owner, mid) and pg.get_records(owner, member_id=mid)
    assert pg.save_member(owner, "other", "Next", "1", "m") not in (mid, other)         # the sequence still hands out fresh ids
    assert family_archive.delete_member(owner, uid, mid, delete_data=False)
    assert family_archive.purge_archived(owner, mid)
    assert not pg.get_records(owner, member_id=mid) and _count(pg, "results", owner, rid) == 0


def test_pg_concurrent_deletes_of_the_same_member_end_clean(pg):
    import family_archive, medication_email
    uid, owner, mid, pid, rid = _world(pg, "pg4")
    results, errors = [], []
    def go():
        try:
            results.append(family_archive.delete_member(owner, uid, mid, delete_data=False))
        except Exception as exc:  # collected for the assertion
            errors.append(repr(exc))
    ts = [threading.Thread(target=go) for _ in range(6)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert not errors, errors
    assert results.count(True) == 1 and results.count(False) == 5, results           # exactly one winner, the rest see "already gone"
    assert not pg.get_member(owner, mid) and not [p for p in medication_email.list_plans(uid, active_only=False) if p["id"] == pid]
    assert len([a for a in family_archive.list_archived(owner) if a["id"] == mid]) == 1


def _pending(pg, plan, date_s=None, time_s=None):
    conn = pg._conn(); c = conn.cursor()
    sql = f"SELECT status, COUNT(*) FROM med_snoozes WHERE plan_id={pg.PH}"
    args = [plan]
    if date_s:
        sql += f" AND log_date={pg.PH} AND log_time={pg.PH}"; args += [date_s, time_s]
    c.execute(sql + " GROUP BY status", tuple(args))
    rows = dict(c.fetchall()); conn.close()
    return rows


def test_pg_concurrent_snooze_every_request_succeeds_and_one_pending_remains(pg):
    import medication_email
    uid, owner, mid, pid, rid = _world(pg, "pg5")
    now = datetime.now(timezone.utc)
    hhmm = now.strftime("%H:%M"); day = now.date().isoformat()
    plan = medication_email.save_plan(uid, {"med_name": "S", "times": [hhmm], "timezone": "UTC", "start_date": (now.date() - timedelta(days=1)).isoformat()})
    plan = int(plan.get("id") if isinstance(plan, dict) else plan)
    outcomes = []
    gate = threading.Barrier(8)
    def press():
        try:
            gate.wait(timeout=10)
            outcomes.append(("ok", medication_email.schedule_snooze(uid, plan, 0, day, hhmm, 10)))
        except Exception as exc:  # recorded as this request's outcome
            outcomes.append(("error", repr(exc)))
    ts = [threading.Thread(target=press) for _ in range(8)]
    [t.start() for t in ts]; [t.join() for t in ts]
    # every request has an explicit outcome: all eight presses succeed (none surfaces a unique-index error to the user)
    assert len(outcomes) == 8 and all(o[0] == "ok" and o[1] == 10 for o in outcomes), outcomes
    rows = _pending(pg, plan, day, hhmm)
    assert rows.get("pending") == 1, rows                      # exactly one active snooze for this dose
    assert rows.get("pending", 0) + rows.get("cancelled", 0) == 8, rows   # nothing lost, nothing duplicated: 1 live + 7 replaced


def test_pg_snooze_pressed_again_replaces_and_other_doses_are_independent(pg):
    import medication_email
    uid, owner, mid, pid, rid = _world(pg, "pg5b")
    now = datetime.now(timezone.utc)
    t1, t2 = "08:00", "20:00"; day = now.date().isoformat()
    plan = medication_email.save_plan(uid, {"med_name": "S2", "times": [t1, t2], "timezone": "UTC", "start_date": (now.date() - timedelta(days=1)).isoformat()})
    plan = int(plan.get("id") if isinstance(plan, dict) else plan)
    for _ in range(3):
        medication_email.schedule_snooze(uid, plan, 0, day, t1, 10)
    medication_email.schedule_snooze(uid, plan, 0, day, t2, 10)
    assert _pending(pg, plan, day, t1) == {"pending": 1, "cancelled": 2}
    assert _pending(pg, plan, day, t2) == {"pending": 1}


def test_pg_concurrent_snooze_and_taken_never_leaves_a_pending_reminder_for_a_taken_dose(pg):
    import medication_email
    uid, owner, mid, pid, rid = _world(pg, "pg5c")
    now = datetime.now(timezone.utc)
    hhmm = now.strftime("%H:%M"); day = now.date().isoformat()
    plan = medication_email.save_plan(uid, {"med_name": "S3", "times": [hhmm], "timezone": "UTC", "start_date": (now.date() - timedelta(days=1)).isoformat()})
    plan = int(plan.get("id") if isinstance(plan, dict) else plan)
    medication_email.schedule_snooze(uid, plan, 0, day, hhmm, 10)
    pg.log_med_status(uid, 0, plan, day, hhmm, "taken")
    with pytest.raises(PermissionError):                      # a taken dose cannot be postponed any more
        medication_email.schedule_snooze(uid, plan, 0, day, hhmm, 10)
    assert _pending(pg, plan, day, hhmm).get("pending", 0) <= 1


def test_pg_a_lost_connection_after_commit_is_still_reported_as_success(pg):
    import psycopg2, family_archive
    uid, owner, mid, pid, rid = _world(pg, "pg6")
    real = pg._conn; state = {"committed": False}
    class Cur:
        def __init__(self, cur, conn): self._c, self._conn = cur, conn
        def execute(self, sql, *a):
            if sql.startswith("DELETE FROM family_members"):
                self._conn.is_removal = True
            return self._c.execute(sql, *a)
        def __getattr__(self, n): return getattr(self._c, n)
    class Conn:
        is_removal = False
        def __init__(self, conn): self._k = conn
        def cursor(self): return Cur(self._k.cursor(), self)
        def commit(self):
            self._k.commit()
            if self.is_removal:
                state["committed"] = True      # the removal transaction is durable; from now on the server "goes away"
        def __getattr__(self, n): return getattr(self._k, n)
    def flaky():
        if state["committed"]:
            raise psycopg2.OperationalError("connection lost after commit")
        return Conn(real())
    pg._conn = flaky
    try:
        assert family_archive.delete_member(owner, uid, mid, delete_data=True) is True   # verification could not run: still success
    finally:
        pg._conn = real
    assert not pg.get_member(owner, mid)


def test_pg_a_connection_failure_before_anything_happens_raises_and_changes_nothing(pg):
    import psycopg2, family_archive
    uid, owner, mid, pid, rid = _world(pg, "pg7")
    real = pg._conn
    def down():
        raise psycopg2.OperationalError("server down")
    pg._conn = down
    try:
        with pytest.raises(psycopg2.OperationalError):
            family_archive.delete_member(owner, uid, mid, delete_data=True)
    finally:
        pg._conn = real
    assert pg.get_member(owner, mid) and pg.get_records(owner, member_id=mid)


def test_pg_orphan_cleanup_and_adherence(pg):
    import orphan_cleanup, family_archive, medication_email
    uid, owner, mid, pid, rid = _world(pg, "pg8")
    h = pg._hash_user(owner); ghost = 987654000 + uuid.uuid4().int % 999
    conn = pg._conn(); c = conn.cursor()
    c.execute(f"INSERT INTO results (user_hash, record_id, data) VALUES ({pg.PH},{pg.PH},{pg.PH})", (h, ghost, "{}"))
    c.execute(f"INSERT INTO symptom_followups (user_hash, record_id, outcome, new_sign, timestamp) VALUES ({pg.PH},{pg.PH},{pg.PH},{pg.PH},{pg.PH})", (h, ghost, "better", 0, "t"))
    conn.commit(); conn.close()
    pg.save_record(owner, "ar", 8, "female", ["x"], "1 day", 1, "monitor", member_id=4242)
    assert orphan_cleanup.run()["dependents"]["results"] >= 1 and _count(pg, "results", owner, ghost) == 1   # dry run keeps it
    orphan_cleanup.run(apply=True)
    assert _count(pg, "results", owner, ghost) == 0 and _count(pg, "results", owner, rid) == 1
    orphan_cleanup.run(apply=True, archive_dangling=True)
    assert any(a["id"] == 4242 for a in family_archive.list_archived(owner))
    assert pg.med_adherence(owner, member_id=mid, days=30)["days"] == 30


class _CommitFails:
    """The connection that runs the removal transaction fails exactly at COMMIT; the server rolls the transaction back."""
    def __init__(self, db, when):
        import psycopg2
        self.db, self.when, self.real = db, when, db._conn
        self.err = psycopg2.OperationalError("connection lost at commit")
        self.hit = False

    def __enter__(self):
        outer = self
        class Cur:
            def __init__(self, cur, conn): self._c, self._conn = cur, conn
            def execute(self, sql, *a):
                if sql.startswith("DELETE FROM family_members"):
                    self._conn.is_removal = True
                return self._c.execute(sql, *a)
            def __getattr__(self, n): return getattr(self._c, n)
        class Conn:
            is_removal = False
            def __init__(self, conn): self._k = conn
            def cursor(self): return Cur(self._k.cursor(), self)
            def commit(self):
                if self.is_removal and outer.when == "before" and not outer.hit:
                    outer.hit = True
                    self._k.rollback()                        # the transaction never became durable
                    raise outer.err
                self._k.commit()
            def __getattr__(self, n): return getattr(self._k, n)
        self.db._conn = lambda: Conn(self.real())
        return self

    def __exit__(self, *exc):
        self.db._conn = self.real


@pytest.mark.parametrize("delete_data", [False, True])
def test_pg_failure_at_commit_loses_nothing_and_a_retry_completes(pg, delete_data):
    import psycopg2, family_archive, medication_email
    uid, owner, mid, pid, rid = _world(pg, "pg8%d" % delete_data)
    with _CommitFails(pg, "before") as f:
        with pytest.raises(psycopg2.OperationalError):
            family_archive.delete_member(owner, uid, mid, delete_data=delete_data)
    assert f.hit
    # nothing partial: member, plan, records, children and archive state are exactly as before
    assert pg.get_member(owner, mid)
    assert any(p["id"] == pid for p in medication_email.list_plans(uid, active_only=False))
    assert pg.get_records(owner, member_id=mid)
    for t in ("results", "symptom_followups", "symptom_relief_logs"):
        assert _count(pg, t, owner, rid) == 1, t
    assert not [a for a in family_archive.list_archived(owner) if a["id"] == mid]
    # retrying is safe and finishes the job
    assert family_archive.delete_member(owner, uid, mid, delete_data=delete_data) is True
    assert not pg.get_member(owner, mid)
    assert not [p for p in medication_email.list_plans(uid, active_only=False) if p["id"] == pid]
    assert bool([a for a in family_archive.list_archived(owner) if a["id"] == mid]) is (not delete_data)
    assert family_archive.delete_member(owner, uid, mid, delete_data=delete_data) is False   # third call: already gone


def test_pg_http_concurrent_deletes_exactly_one_200_and_the_rest_404(pg):
    import re, webapp
    uid, owner, mid, pid, rid = _world(pg, "pg9")
    clients = []
    for _ in range(6):
        c = webapp.app.test_client(); c.set_cookie("lang", "ar")
        with c.session_transaction() as sess:
            sess["ss_user_id"] = uid
        clients.append(c)
    hdr = {"Host": "localhost"}
    tokens = []
    for c in clients:
        page = c.get("/family", headers=hdr).get_data(as_text=True)
        tokens.append(re.search(r'name="symptosense-csrf"\s+content="([^"]*)"', page).group(1))
    out = []
    gate = threading.Barrier(len(clients))
    def go(c, tok):
        gate.wait(timeout=10)
        r = c.delete("/api/family/%d" % mid, headers={"Host": "localhost", "X-CSRF-Token": tok})
        out.append((r.status_code, r.get_json()))
    ts = [threading.Thread(target=go, args=(c, t)) for c, t in zip(clients, tokens)]
    [t.start() for t in ts]; [t.join() for t in ts]
    codes = sorted(o[0] for o in out)
    assert codes == [200, 404, 404, 404, 404, 404], out
    assert [o[1] for o in out if o[0] == 200] == [{"ok": True}]
    assert all(o[1] == {"ok": False, "error": "family_member_not_found"} for o in out if o[0] == 404), out
    assert not pg.get_member(owner, mid)


def test_pg_concurrent_restore_and_purge_each_get_a_definite_answer(pg):
    import family_archive
    uid, owner, mid, pid, rid = _world(pg, "pg10")
    assert family_archive.delete_member(owner, uid, mid, delete_data=False) is True
    res = []
    gate = threading.Barrier(6)
    def restore():
        gate.wait(timeout=10); res.append(("restore", family_archive.restore_member(owner, mid)))
    def purge():
        gate.wait(timeout=10); res.append(("purge", family_archive.purge_archived(owner, mid)))
    ts = [threading.Thread(target=restore) for _ in range(3)] + [threading.Thread(target=purge) for _ in range(3)]
    [t.start() for t in ts]; [t.join() for t in ts]
    wins = [r for r in res if r[1]]
    assert len(wins) == 1, res                                     # the archive row can be consumed only once
    assert not [a for a in family_archive.list_archived(owner) if a["id"] == mid]
    assert bool(pg.get_member(owner, mid)) is (wins[0][0] == "restore")
