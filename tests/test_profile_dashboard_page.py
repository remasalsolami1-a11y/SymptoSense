"""/profile (dashboard) and the profile editor, against the real app and database."""
import re
import uuid
from datetime import datetime, timedelta, timezone

import pytest

import db
import webapp
from pagelib import profile_dashboard_html as page
from services import profile_dashboard_service as svc


@pytest.fixture(autouse=True)
def _testing(monkeypatch):
    monkeypatch.setitem(webapp.app.config, "TESTING", True)   # skips the browser CSRF gate, as the other API tests do


def _user():
    db.init_db()
    uid, err = db.create_ss_user("pd-%s@example.test" % uuid.uuid4().hex[:8], "Rema <b>", "TestPassword123!")
    conn = db._conn(); conn.execute("UPDATE ss_users SET email_verified=1 WHERE id=?", (uid,)); conn.commit(); conn.close()
    return uid


def _client(uid, lang="ar", consent=True):
    c = webapp.app.test_client()
    c.set_cookie("lang", lang)
    with c.session_transaction() as s:
        s["ss_user_id"] = uid
    if consent:
        assert c.post("/api/consent/preferences", json={"service_usage": True, "analytics_research": False}).status_code == 200
    return c


def _main(html):
    html = re.sub(r"<style.*?</style>", "", html, flags=re.S)
    m = re.search(r'<main class="pd".*?</main>', html, re.S)
    assert m, "dashboard markup missing"
    return m.group(0)


def _text(fragment):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment))


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_new_user_sees_a_friendly_non_empty_page(lang):
    uid = _user()
    r = _client(uid, lang).get("/%s/profile" % lang, follow_redirects=True)
    assert r.status_code == 200
    body = _main(r.get_data(as_text=True))
    txt = _text(body)
    assert ("غير مضاف" if lang == "ar" else "Not added") in txt
    assert ("ينقص ملفك" if lang == "ar" else "Your profile is missing") in txt
    assert ("لا يوجد بعد" if lang == "ar" else "None yet") in txt
    assert body.count('class="pd-card"') == 4
    assert "<b>" not in _text(body) and "&lt;b&gt;" in body            # the user's name is escaped, not parsed
    assert 'dir="%s"' % ("rtl" if lang == "ar" else "ltr") in body


def test_complete_profile_hides_the_missing_line():
    uid = _user()
    db.save_health_profile(uid, {"display_name": "R", "dob": "1990-05-01", "gender": "female", "allergies": "لا يوجد",
                                 "health_conditions": "لا يوجد", "medications": "لا يوجد"})
    body = _main(_client(uid).get("/ar/profile", follow_redirects=True).get_data(as_text=True))
    assert "ينقص ملفك" not in body and "لا شيء" not in body
    assert "تاريخ الميلاد" in body and "أنثى" in body


def test_dashboard_shows_dates_only_and_never_leaks_medical_values():
    uid = _user()
    key = "account-%s" % uid
    db.save_analysis_record_with_result(key, "ar", 30, "female", ["صداع"], "يومان", "3", "emergency", {"triage_level": "emergency"})
    db.save_blood_test(key, {"hgb": 4.1, "wbc": 55.5}, member_id=0)
    db.save_vital(key, 0, "bp", 240, 150)
    db.save_followup(key, db.get_records(key, limit=1)[0]["id"], "worse", True)
    body = _main(_client(uid, "en").get("/en/profile", follow_redirects=True).get_data(as_text=True))
    txt = _text(body)
    for label in ("Latest symptom analysis", "Latest CBC", "Latest vital reading", "Latest follow-up"):
        assert label in txt
    assert txt.count("None yet") == 0
    for leaked in ("emergency", "240", "150", "4.1", "55.5", "worse", "urgent", "danger", "abnormal", "high", "low"):
        assert not re.search(r"\b%s\b" % re.escape(leaked), txt.lower()), leaked


def test_alerts_are_administrative_and_use_neutral_wording():
    uid = _user()
    key = "account-%s" % uid
    rid = db.save_analysis_record_with_result(key, "ar", 30, "female", ["صداع"], "يومان", "3", "routine", {})
    conn = db._conn()
    conn.execute("UPDATE records SET timestamp=? WHERE id=?", ((datetime.now(timezone.utc) - timedelta(days=2)).isoformat(), rid))
    conn.commit(); conn.close()
    body = _main(_client(uid, "en").get("/en/profile", follow_redirects=True).get_data(as_text=True))
    assert "You can update how you are doing now." in body
    for scary in ("you have", "diagnos", "serious", "emergency", "problem"):
        assert scary not in _text(body).lower()


def test_dashboard_without_alerts_has_no_alert_section():
    uid = _user()
    db.save_health_profile(uid, {"dob": "1990-05-01", "gender": "male", "allergies": "x", "health_conditions": "y", "medications": "z"})
    body = _main(_client(uid, "en").get("/en/profile", follow_redirects=True).get_data(as_text=True))
    assert "Worth a look" not in body


def test_privacy_summary_reflects_the_users_choices():
    uid = _user()
    db.save_privacy_settings(uid, {"use_in_analysis": False, "use_in_assistant": True, "use_in_calculators": True, "save_chat_history": True})
    txt = _text(_main(_client(uid, "en").get("/en/profile", follow_redirects=True).get_data(as_text=True)))
    assert re.search(r"Symptom analysis\s+Off", txt)
    assert re.search(r"Assistant\s+On", txt)


def test_dashboard_survives_a_failing_source(monkeypatch):
    uid = _user()
    monkeypatch.setattr(db, "get_blood_tests", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    r = _client(uid, "en").get("/en/profile", follow_redirects=True)
    assert r.status_code == 200
    assert "could not be loaded" in _text(_main(r.get_data(as_text=True)))


def test_login_is_still_required():
    r = webapp.app.test_client().get("/profile")
    assert r.status_code in (301, 302, 303)


# ---- editor / validation -----------------------------------------------------------------------------------
@pytest.mark.parametrize("field,value,code", [
    ("dob", "2999-01-01", "dob_in_future"), ("dob", "not-a-date", "invalid_dob"), ("height", "5", "height_out_of_range"),
    ("weight", "9999", "weight_out_of_range"), ("gender", "robot", "invalid_gender")])
def test_field_endpoint_rejects_implausible_values(field, value, code):
    uid = _user()
    c = _client(uid)
    r = c.post("/api/health-profile/field", json={"field": field, "value": value})
    assert r.status_code == 400 and r.get_json()["error"] == code
    assert not (db.load_health_profile(uid) or {}).get(field)


def test_field_endpoint_saves_normalised_values_and_empty_clears():
    uid = _user()
    c = _client(uid)
    assert c.post("/api/health-profile/field", json={"field": "height", "value": "170,50"}).get_json()["value"] == "170.5"
    assert c.post("/api/health-profile/field", json={"field": "dob", "value": "1990-05-01"}).get_json()["ok"]
    assert c.post("/api/health-profile/field", json={"field": "gender", "value": "ذكر"}).get_json()["value"] == "male"
    hp = db.load_health_profile(uid)
    assert (hp["height"], hp["dob"], hp["gender"]) == ("170.5", "1990-05-01", "male")
    assert c.post("/api/health-profile/field", json={"field": "height", "value": ""}).get_json()["ok"]
    assert db.load_health_profile(uid)["height"] == ""


def test_bulk_endpoint_validates_like_the_field_endpoint_and_keeps_other_fields():
    uid = _user()
    c = _client(uid)
    db.save_health_profile(uid, {"allergies": "x"})
    assert c.post("/api/health-profile", json={"weight": "9999"}).status_code == 400
    assert c.post("/api/health-profile", json={"weight": "70", "gender": "f"}).get_json()["ok"]
    hp = db.load_health_profile(uid)
    assert (hp["weight"], hp["gender"], hp["allergies"]) == ("70", "female", "x")


def test_manage_page_has_typed_editor_hooks():
    uid = _user()
    db.save_health_profile(uid, {"dob": "1990-05-01", "gender": "other"})
    html = _client(uid, "en").get("/en/manage", follow_redirects=True).get_data(as_text=True)
    assert 'id="val_dob" data-raw="1990-05-01"' in html
    assert "Other" in html and "manage-profile.js?v=263" in html
    js = open("static/js/manage-profile.js", encoding="utf-8").read()
    for token in ("input.type = 'date'", "input.type = 'number'", "createElement('select')", "dob_in_future", "height_out_of_range"):
        assert token in js


def test_renderer_escapes_everything_and_handles_bad_dates():
    data = svc.ProfileDashboardData(
        identity=svc.Identity(name='<script>alert(1)</script>', age=None, gender="female", dob="bad", updated_at="garbage"),
        missing_fields=(), latest_symptom_analysis=svc.ActivityItem("symptom_analysis", "not-a-date", '/x"><i>'),
        latest_cbc=None, latest_vital=None, latest_followup=None, medications=svc.MedicationSummary(),
        privacy_summary=svc.PrivacySummary(), quick_actions=(), alerts=())
    html = page.render(data, "en")
    assert "<script>alert" not in html and "&lt;script&gt;" in html and '"><i>' not in html
