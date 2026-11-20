"""POST /api/checkin must answer bad input with 400, never 500 (found in the V68 pre-release check)."""
import re
import uuid

import pytest

import db
import webapp


def _client():
    db.init_db()
    uid, _ = db.create_ss_user("ck-%s@example.test" % uuid.uuid4().hex[:8], "CK", "TestPassword123!")
    conn = db._conn(); conn.execute("UPDATE ss_users SET email_verified=1 WHERE id=?", (uid,)); conn.commit(); conn.close()
    c = webapp.app.test_client()
    with c.session_transaction() as s:
        s["ss_user_id"] = uid
    assert c.post("/api/consent/preferences", json={"service_usage": True, "analytics_research": False}).status_code == 200
    page = c.get("/en/family").get_data(as_text=True)
    c.environ_base["HTTP_X_CSRF_TOKEN"] = re.search(r'name="symptosense-csrf" content="([^"]+)"', page).group(1)
    return c


@pytest.mark.parametrize("body", [{}, {"rating": None}, {"rating": "abc"}, {"rating": 3.5}, {"rating": True}, {"rating": 0}, {"rating": 6}, {"rating": -2}, [], "x",
                                  {"rating": "\u00b2"}, {"rating": "\u2461"}, {"rating": "\u00b9"}, {"rating": "3.5"}, {"rating": "1e1"}, {"rating": "٣٣"},
                                  {"rating": "9" * 5000}, {"rating": [3]}, {"rating": {"v": 3}}, {"rating": float("inf")}])
def test_bad_rating_is_400_not_500(body):
    r = _client().post("/api/checkin", json=body)
    assert r.status_code == 400, (body, r.status_code, r.get_data(as_text=True)[:200])
    assert r.get_json()["ok"] is False


def test_valid_rating_still_saves():
    r = _client().post("/api/checkin", json={"rating": 4, "date": "2026-10-13"})
    assert r.status_code == 200 and r.get_json()["ok"] is True
    r = _client().post("/api/checkin", json={"rating": "5", "date": "2026-10-13"})
    assert r.status_code == 200


@pytest.mark.parametrize("raw", ["{bad", "", "not json", "[1,", "\xff\xfe"])
def test_malformed_json_is_400_not_500(raw):
    c = _client()
    for path in ("/api/checkin", "/api/feedback"):
        r = c.post(path, data=raw, content_type="application/json")
        assert r.status_code == 400, (path, raw, r.status_code, r.get_data(as_text=True)[:200])
        assert r.get_json()["ok"] is False


@pytest.mark.parametrize("value", [4, "4", " 4 ", 4.0, "\u0664"])   # \u0664 = Arabic-Indic digit four
def test_valid_ratings_variants_still_save(value):
    r = _client().post("/api/checkin", json={"rating": value, "date": "2026-10-13"})
    assert r.status_code == 200 and r.get_json()["today"]["value"] == 4


@pytest.mark.parametrize("value", ["\u00b2", "\u2461", "abc", None, 3.5, True, {}, 0, 6])
def test_feedback_bad_rating_is_400(value):
    r = _client().post("/api/feedback", json={"rating": value})
    assert r.status_code == 400, (value, r.status_code)


@pytest.mark.parametrize("comment", [["a"], {"a": 1}, 5, True, 1.5])
def test_feedback_comment_must_be_text(comment):
    r = _client().post("/api/feedback", json={"rating": 4, "comment": comment})
    assert r.status_code == 400 and r.get_json()["error"] == "invalid_comment"


@pytest.mark.parametrize("comment", [None, "", "  nice  ", "x" * 2000, "a\x00b", "\u0645\u0645\u062a\u0627\u0632"])
def test_feedback_text_comments_still_save(comment):
    r = _client().post("/api/feedback", json={"rating": 4, "comment": comment})
    assert r.status_code == 200 and r.get_json()["ok"] is True


@pytest.mark.parametrize("record_id", [[1], {"a": 1}, "\u00b2", "abc", 1.5, True, -3, 10 ** 30, "9" * 400, float("inf"), float("nan")])
def test_feedback_bad_record_id_is_400(record_id):
    r = _client().post("/api/feedback", json={"rating": 4, "record_id": record_id})
    assert r.status_code == 400 and r.get_json()["error"] == "invalid_record_id", (record_id, r.status_code)


@pytest.mark.parametrize("field,value", [("reason_code", ["x"]), ("context", {"a": 1}), ("reason_code", 5), ("public_comment", [1])])
def test_feedback_other_fields_never_500(field, value):
    r = _client().post("/api/feedback", json={"rating": 4, field: value})
    assert r.status_code < 500, (field, value, r.status_code)
