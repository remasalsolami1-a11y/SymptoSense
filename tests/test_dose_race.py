"""Dose logging vs. postponing under real concurrency ("taken" and "later" pressed at the same moment).

Runs on whatever database is active: SQLite by default (isolated file), PostgreSQL when TEST_DATABASE_URL points at a
disposable database. CI runs it in both modes. Invariants checked after every race:
  * a dose that was marked `taken` never ends up `snoozed`, and has no pending snooze reminder;
  * `snoozed` <=> exactly one pending snooze; `skipped`/`taken` => none;
  * exactly one log row per dose; every request has a definite outcome (success or PermissionError, never a DB error).
"""
import os
import tempfile
import threading
import uuid
from datetime import datetime, timedelta, timezone

import pytest

if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
else:
    os.environ.pop("DATABASE_URL", None)
    os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(prefix="ss-race-"), "race.sqlite3"))
os.environ.setdefault("WEB_SECRET", "race-test-secret-that-is-longer-than-32-characters")

ROUNDS = 12


@pytest.fixture(scope="module")
def world():
    import db, medication_email
    db.init_db(); medication_email.init_schema()
    uid, err = db.create_ss_user("race-%s@example.test" % uuid.uuid4().hex[:8], "Race Test", "StrongPassword123!")
    assert uid and not err
    conn = db._conn(); c = conn.cursor()
    c.execute(f"UPDATE ss_users SET email_verified=1,status='active' WHERE id={db.PH}", (uid,))
    conn.commit(); conn.close()
    today = datetime.now(timezone.utc).date()
    times = ["%02d:%02d" % (h, m) for h in range(0, 24) for m in (0, 30)][:48]
    plan = medication_email.save_plan(uid, {"med_name": "Race", "times": times, "timezone": "UTC", "start_date": (today - timedelta(days=1)).isoformat()})
    plan = int(plan.get("id") if isinstance(plan, dict) else plan)
    return db, medication_email, uid, plan, today.isoformat(), iter(times)


def _state(db, plan, day, tm):
    conn = db._conn(); c = conn.cursor()
    c.execute(f"SELECT status FROM med_logs WHERE plan_id={db.PH} AND log_date={db.PH} AND log_time={db.PH}", (plan, day, tm))
    logs = [r[0] for r in c.fetchall()]
    c.execute(f"SELECT COUNT(*) FROM med_snoozes WHERE plan_id={db.PH} AND log_date={db.PH} AND log_time={db.PH} AND status='pending'", (plan, day, tm))
    pending = c.fetchone()[0]
    conn.close()
    return logs, pending


def _race(*jobs):
    """Run callables at the same instant; returns [('ok', value) | ('err', exception)] in job order."""
    gate = threading.Barrier(len(jobs)); out = [None] * len(jobs)
    def run(i, fn):
        gate.wait(timeout=15)
        try:
            out[i] = ("ok", fn())
        except Exception as exc:  # the outcome is the thing under test
            out[i] = ("err", exc)
    ts = [threading.Thread(target=run, args=(i, fn)) for i, fn in enumerate(jobs)]
    [t.start() for t in ts]; [t.join(timeout=60) for t in ts]
    assert all(o is not None for o in out), "a request never finished"
    return out


def _check_consistent(db, plan, day, tm):
    logs, pending = _state(db, plan, day, tm)
    assert len(logs) == 1, logs
    if logs[0] == "snoozed":
        assert pending == 1
    else:
        assert pending == 0, (logs, pending)
    return logs[0]


def test_taken_and_later_at_the_same_moment_taken_always_wins(world):
    db, me, uid, plan, day, times = world
    snoozed_first = refused = 0
    for _ in range(ROUNDS):
        tm = next(times)
        # a snooze already exists for some rounds, so the "taken" has something to cancel
        if _ % 2:
            me.schedule_snooze(uid, plan, 0, day, tm, 10)
        taken, later = _race(lambda: db.log_med_status(uid, 0, plan, day, tm, "taken"),
                             lambda: me.schedule_snooze(uid, plan, 0, day, tm, 10))
        assert taken[0] == "ok", taken                                     # recording a taken dose never fails
        if later[0] == "ok":
            snoozed_first += 1                                              # snooze ran first, then taken overwrote + cancelled it
        else:
            assert isinstance(later[1], PermissionError) and "already_taken" in str(later[1]), later
            refused += 1                                                    # taken committed first: the late snooze is refused
        assert _check_consistent(db, plan, day, tm) == "taken"
    assert snoozed_first + refused == ROUNDS


def test_many_snoozes_racing_one_taken(world):
    db, me, uid, plan, day, times = world
    for _ in range(4):
        tm = next(times)
        jobs = [lambda: me.schedule_snooze(uid, plan, 0, day, tm, 10) for _ in range(6)] + [lambda: db.log_med_status(uid, 0, plan, day, tm, "taken")]
        out = _race(*jobs)
        for kind, val in out:
            assert kind == "ok" or (isinstance(val, PermissionError) and "already_taken" in str(val)), val
        assert out[-1][0] == "ok"
        assert _check_consistent(db, plan, day, tm) == "taken"


def test_skipped_and_later_race_ends_in_a_consistent_state(world):
    db, me, uid, plan, day, times = world
    finals = set()
    for _ in range(ROUNDS):
        tm = next(times)
        skipped, later = _race(lambda: db.log_med_status(uid, 0, plan, day, tm, "skipped"),
                               lambda: me.schedule_snooze(uid, plan, 0, day, tm, 10))
        assert skipped[0] == "ok" and later[0] == "ok", (skipped, later)    # both are legitimate; the last writer decides
        finals.add(_check_consistent(db, plan, day, tm))
    assert finals <= {"skipped", "snoozed"}


def test_sequential_rules(world):
    db, me, uid, plan, day, times = world
    tm = next(times)
    me.schedule_snooze(uid, plan, 0, day, tm, 10)
    assert _state(db, plan, day, tm) == (["snoozed"], 1)
    db.log_med_status(uid, 0, plan, day, tm, "taken")                        # taken after snooze cancels the reminder
    assert _state(db, plan, day, tm) == (["taken"], 0)
    with pytest.raises(PermissionError):
        me.schedule_snooze(uid, plan, 0, day, tm, 10)                        # late "later" is refused
    with pytest.raises(PermissionError):
        db.log_med_status(uid, 0, plan, day, tm, "snoozed")                  # and so is a direct snoozed log
    assert _state(db, plan, day, tm) == (["taken"], 0)
    db.log_med_status(uid, 0, plan, day, tm, "skipped")                      # explicit correction taken -> skipped stays possible
    assert _state(db, plan, day, tm) == (["skipped"], 0)
    me.schedule_snooze(uid, plan, 0, day, tm, 10)                            # a deliberate snooze after skip still works
    assert _state(db, plan, day, tm) == (["snoozed"], 1)
    for _ in range(3):
        me.schedule_snooze(uid, plan, 0, day, tm, 10)
    assert _state(db, plan, day, tm) == (["snoozed"], 1)                     # repeated "later" keeps ONE reminder


def test_a_failure_inside_the_snooze_transaction_leaves_nothing_behind(world):
    db, me, uid, plan, day, times = world
    tm = next(times)
    real = db.write_dose_log
    def boom(*a, **k):
        raise db.DB_ERRORS[0]("injected failure after the snooze row was inserted")
    db.write_dose_log = boom
    try:
        with pytest.raises(db.DB_ERRORS):
            me.schedule_snooze(uid, plan, 0, day, tm, 10)
    finally:
        db.write_dose_log = real
    assert _state(db, plan, day, tm) == ([], 0)                              # no pending snooze without its log, no log without snooze
    me.schedule_snooze(uid, plan, 0, day, tm, 10)
    assert _state(db, plan, day, tm) == (["snoozed"], 1)


def test_http_taken_and_later_together(world):
    import re
    import webapp
    db, me, uid, plan, day, times = world
    def client():
        c = webapp.app.test_client(); c.set_cookie("lang", "en")
        with c.session_transaction() as s:
            s["ss_user_id"] = uid
        c.post("/api/consent/preferences", json={"service_usage": True, "analytics_research": False}, headers={"Host": "localhost"})
        tok = re.search(r'name="symptosense-csrf"\s+content="([^"]*)"', c.get("/en/meds", headers={"Host": "localhost"}).get_data(as_text=True)).group(1)
        return c, {"Host": "localhost", "X-CSRF-Token": tok}
    (c1, h1), (c2, h2) = client(), client()
    for _ in range(4):
        tm = next(times)
        a, b = _race(lambda: c1.post("/api/meds/log", json={"plan_id": plan, "time": tm, "status": "taken", "date": day}, headers=h1),
                     lambda: c2.post("/api/meds/snooze", json={"plan_id": plan, "time": tm, "date": day}, headers=h2))
        assert a[0] == "ok" and b[0] == "ok", (a, b)
        assert a[1].status_code == 200 and a[1].get_json()["ok"] is True
        assert b[1].status_code in (200, 409), b[1].status_code
        if b[1].status_code == 409:
            assert b[1].get_json() == {"ok": False, "error": "reminder_already_taken"}
        assert _check_consistent(db, plan, day, tm) == "taken"
