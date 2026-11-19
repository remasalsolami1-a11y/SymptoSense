"""V253: assistant personal context is opt-in, minimal and never used in mental-health mode."""
import uuid

import assistant_context
import db
import webapp


def _user():
    db.init_db()
    uid, err = db.create_ss_user("ac-%s@example.test" % uuid.uuid4().hex[:8], "AC", "TestPassword123!")
    conn = db._conn(); conn.execute("UPDATE ss_users SET email_verified=1 WHERE id=?", (uid,)); conn.commit(); conn.close()
    return uid


def test_context_is_minimal_and_bounded():
    uid = _user()
    owner = "account-%s" % uid
    db.save_record(owner, "ar", 30, "female", ["صداع"], "يوم", 3, "low")
    ctx = assistant_context.build(owner, "ar")
    assert "صداع" in ctx and len(ctx) <= assistant_context.MAX_CHARS
    assert "@" not in ctx and "AC" not in ctx.split()
    assert assistant_context.system_addendum("", "ar") == ""
    assert "never to diagnose" in assistant_context.system_addendum("x", "en")


def test_only_sent_when_opted_in_signed_in_and_not_mh(monkeypatch):
    uid = _user()
    db.save_record("account-%s" % uid, "ar", 30, "female", ["صداع"], "يوم", 3, "low")
    seen = []

    class _Msg:  # minimal provider stub
        content = "جواب"

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    def fake(msgs, **kw):
        seen.append(msgs[0]["content"])
        return _Resp()
    monkeypatch.setattr(webapp, "_groq_chat_completion_with_retry", fake)
    c = webapp.app.test_client()
    c.set_cookie("lang", "ar")
    assert c.post("/api/consent/preferences", json={"service_usage": True, "analytics_research": False}).status_code == 200
    body = {"lang": "ar", "messages": [{"role": "user", "content": "اشرح لي كيف أرتب جدول نومي مع الدراسة والعمل"}]}
    c.post("/api/assistant", json=dict(body, use_my_data=True))          # anonymous: ignored
    with c.session_transaction() as s:
        s["ss_user_id"] = uid
    assert c.post("/api/consent/preferences", json={"service_usage": True, "analytics_research": False}).status_code == 200
    assert c.post("/api/assistant", json=body).get_json()["ok"]            # signed in, not opted in
    c.post("/api/assistant", json=dict(body, use_my_data=True))           # opted in
    c.post("/api/assistant", json=dict(body, use_my_data=True, mode="mh"))
    flagged = ["اختار مشاركة" in s for s in seen]
    assert flagged == [False, False, True, False]
