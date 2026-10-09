"""V257: Home Vitals Tracker."""
import uuid

import analysis_core
import db
import vitals
import webapp


def test_validation_rejects_typos_and_converts_nothing_silently():
    assert vitals.validate("bp", 120, 80)[0]
    assert not vitals.validate("bp", 120, 130)[0]          # diastolic above systolic
    assert not vitals.validate("bp", 120)[0]                # diastolic missing
    assert not vitals.validate("temp", 3.7)[0] and vitals.validate("temp", 37.2)[0]
    assert not vitals.validate("spo2", 101)[0] and not vitals.validate("pulse", 400)[0]
    assert not vitals.validate("nonsense", 1)[0] and not vitals.validate("pulse", "abc")[0]
    assert vitals.validate("glucose", 100, None, "fasting")[3] == "fasting" and vitals.validate("glucose", 100, None, "x")[3] == ""


def test_alert_levels():
    A = lambda *a, **k: vitals.assess(*a, **k)["level"]
    assert A("bp", 118, 76) == "ok" and A("bp", 150, 95) == "attention" and A("bp", 185, 110) == "urgent" and A("bp", 85, 55) == "attention"
    assert A("glucose", 95, None, "fasting") == "ok" and A("glucose", 130, None, "fasting") == "attention" and A("glucose", 130, None, "after_meal") == "ok"
    assert A("glucose", 60) == "attention" and A("glucose", 50) == "emergency" and A("glucose", 350) == "urgent"
    assert A("temp", 37.0) == "ok" and A("temp", 38.4) == "attention" and A("temp", 40.2) == "urgent"
    assert A("pulse", 72) == "ok" and A("pulse", 110) == "attention" and A("pulse", 140) == "urgent"
    assert A("spo2", 98) == "ok" and A("spo2", 93) == "urgent" and A("spo2", 88) == "emergency"
    assert "997" in vitals.assess("spo2", 88, None, "", "ar")["message"]


def _user():
    db.init_db()
    uid, _ = db.create_ss_user("vt-%s@example.test" % uuid.uuid4().hex[:8], "VT", "TestPassword123!")
    conn = db._conn(); conn.execute("UPDATE ss_users SET email_verified=1 WHERE id=?", (uid,)); conn.commit(); conn.close()
    return uid


def _client(uid):
    c = webapp.app.test_client()
    c.set_cookie("lang", "ar")
    c.environ_base["HTTP_X_CSRF_TOKEN"] = "tok"
    with c.session_transaction() as s:
        s["ss_user_id"] = uid
        s["user_csrf"] = "tok"
    assert c.post("/api/consent/preferences", json={"service_usage": True, "analytics_research": False}).status_code == 200
    return c


def test_endpoints_ownership_units_and_page():
    uid, other = _user(), _user()
    assert webapp.app.test_client().get("/api/vitals").status_code == 401
    c = _client(uid)
    r = c.post("/api/vitals", json={"kind": "bp", "v1": 150, "v2": 95}).get_json()
    assert r["ok"] and r["alert"]["level"] == "attention"
    g = c.post("/api/vitals", json={"kind": "glucose", "v1": 5.5, "unit": "mmol", "context": "fasting"}).get_json()
    assert g["ok"]
    rows = c.get("/api/vitals?kind=glucose").get_json()["rows"]
    assert len(rows) == 1 and 98 < rows[0]["v1"] < 100                  # 5.5 mmol/L = 99.1 mg/dL
    assert c.post("/api/vitals", json={"kind": "temp", "v1": 99}).status_code == 400
    assert c.post("/api/vitals", json={"kind": "bp", "v1": 120, "v2": 200}).status_code == 400
    assert c.get("/api/vitals?kind=zzz").status_code == 400
    page = c.get("/ar/vitals")
    assert page.status_code == 200 and "150/95" in page.get_data(as_text=True)
    o = _client(other)
    assert o.get("/api/vitals").get_json()["rows"] == []                # another user sees nothing
    vid = rows[0]["id"]
    assert o.delete("/api/vitals/%d" % vid).status_code == 404         # cannot delete someone else's reading
    assert c.delete("/api/vitals/%d" % vid).status_code == 200


def test_vitals_flow_into_health_file_doctor_page_and_reasoning():
    uid = _user()
    owner = "account-%s" % uid
    db.save_vital(owner, 0, "spo2", 93)
    db.save_vital(owner, 0, "bp", 118, 76)
    c = _client(uid)
    hf = c.get("/api/health-file").get_json()
    assert any("SpO₂" in v or "الأكسجين" in v for v in hf["vitals"])
    assert "vitals" in c.get("/ar/health-file?view=doctor").get_data(as_text=True) or "القياسات" in c.get("/ar/health-file?view=doctor").get_data(as_text=True)
    r = analysis_core.run_analysis({"age": "34", "gender": "female", "duration": "يومين", "severity": "2", "symptoms": ["كحة"],
                                    "conditions": "", "medications": "", "notes": "", "user_id": owner}, "ar")
    assert any(c_["kind"] == "vitals" for c_ in r["reasoning"]["contributors"])
    assert r["triage_level"] == "today"                                  # urgent home reading raises monitor -> ... -> today



def test_emergency_vital_forces_final_emergency_and_never_lowers():
    uid = _user()
    owner = "account-%s" % uid
    db.save_vital(owner, 0, "spo2", 88)
    base = {"age": "34", "gender": "female", "duration": "يومين", "severity": "2", "symptoms": ["كحة"],
            "conditions": "", "medications": "", "notes": "", "user_id": owner}
    r = analysis_core.run_analysis(dict(base), "ar")
    assert r["triage_level"] == "emergency"
    assert r["emergency"] is True
    assert any("قراءة منزلية" in f for f in r["emergency_flags"])
    assert r["decision"]["level"] == "emergency"
    # an already-emergency case stays emergency
    r2 = analysis_core.run_analysis(dict(base, severity="5", symptoms=["صعوبة في التنفس"]), "ar")
    assert r2["triage_level"] == "emergency"
