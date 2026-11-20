"""V253: smart follow-up - due window, one answer per analysis, no reassurance when worse."""
import uuid
from datetime import datetime, timedelta, timezone

import db
import followup
import webapp

NOW = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)


def _r(i, hours_ago):
    return {"id": i, "timestamp": (NOW - timedelta(hours=hours_ago)).isoformat(), "symptoms": ["صداع"]}


def test_window_depends_on_urgency():
    def rec(i, hours, urgency):
        r = _r(i, hours)
        r["urgency"] = urgency
        return r
    assert followup.due([rec(1, 7, "high")], [], NOW)["record_id"] == 1          # high: asked after 6h
    assert followup.due([rec(1, 7, "low")], [], NOW) is None                      # low: not before 48h
    assert followup.due([rec(1, 50, "low")], [], NOW)["record_id"] == 1
    assert followup.due([rec(1, 24 * 4, "high")], [], NOW) is None                # high closes after 3 days
    assert followup.due([rec(1, 24 * 6, "medium")], [], NOW)["record_id"] == 1
    assert followup.due([rec(1, 24 * 8, "medium")], [], NOW) is None
    assert followup.due([rec(1, 24 * 13, "low")], [], NOW)["record_id"] == 1


def test_due_window():
    assert followup.due([_r(1, 2)], [], NOW) is None                 # too fresh
    assert followup.due([_r(1, 30)], [], NOW)["record_id"] == 1
    assert followup.due([_r(1, 24 * 20)], [], NOW) is None           # too old
    assert followup.due([_r(1, 30)], [{"record_id": 1}], NOW) is None  # already answered
    assert followup.due([_r(2, 2), _r(1, 30)], [], NOW)["record_id"] == 1


def test_worse_or_new_sign_never_reassures():
    for lang in ("ar", "en"):
        for out, sign in (("worse", False), ("better", True), ("same", True)):
            r = followup.reply(out, sign, lang)
            assert r["level"] == "today" and "997" in r["message"]
    assert followup.reply("better", False, "ar")["level"] == "monitor"
    assert followup.reply("same", False, "en")["level"] == "soon"


def test_endpoint_flow_and_ownership():
    db.init_db()
    uid, err = db.create_ss_user("fu-%s@example.test" % uuid.uuid4().hex[:8], "FU", "TestPassword123!")
    other, _ = db.create_ss_user("fu-o-%s@example.test" % uuid.uuid4().hex[:8], "FU2", "TestPassword123!")
    for u in (uid, other):
        conn = db._conn(); conn.execute("UPDATE ss_users SET email_verified=1 WHERE id=?", (u,)); conn.commit(); conn.close()
    db.save_record("account-%s" % uid, "ar", 30, "female", ["صداع"], "يوم", 3, "low")
    db.save_record("account-%s" % other, "ar", 30, "male", ["سعال"], "يوم", 3, "low")
    old = (datetime.now(timezone.utc) - timedelta(hours=60)).isoformat()
    conn = db._conn(); conn.execute("UPDATE records SET timestamp=?", (old,)); conn.commit(); conn.close()
    mine = db.get_records("account-%s" % uid, limit=1)[0]["id"]
    theirs = db.get_records("account-%s" % other, limit=1)[0]["id"]

    anon = webapp.app.test_client()
    assert anon.get("/api/followup/status").status_code == 401
    c = webapp.app.test_client()
    c.set_cookie("lang", "ar")
    c.environ_base["HTTP_X_CSRF_TOKEN"] = "tok"
    assert c.post("/api/consent/preferences", json={"service_usage": True, "analytics_research": False}).status_code == 200
    with c.session_transaction() as s:
        s["ss_user_id"] = uid
        s["user_csrf"] = "tok"
    assert c.get("/api/followup/status").get_json()["due"]["record_id"] == mine
    assert "هل تحسنت" in c.get("/ar/health-file").get_data(as_text=True)
    doc = c.get("/ar/health-file?view=doctor")
    assert doc.status_code == 200 and "صفحة واحدة" in doc.get_data(as_text=True)
    assert c.post("/api/followup/answer", json={"record_id": theirs, "outcome": "better"}).status_code == 404
    assert c.post("/api/followup/answer", json={"record_id": mine, "outcome": "bogus"}).status_code == 400
    assert c.post("/api/followup/answer", json={"record_id": "x", "outcome": "better"}).status_code == 400
    r = c.post("/api/followup/answer", json={"record_id": mine, "outcome": "worse"}).get_json()
    assert r["ok"] and r["level"] == "today" and "997" in r["message"]
    assert c.get("/api/followup/status").get_json()["due"] is None
    assert db.followup_stats()["worse"]["count"] >= 1
