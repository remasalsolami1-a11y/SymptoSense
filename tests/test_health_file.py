"""V252: unified health file - lab trends, recurring symptoms, medicines, visit summary."""
import pytest

import uuid

import db
import health_file
import webapp


def _t(date, rows):
    return {"timestamp": date + "T08:00:00+00:00",
            "data": {"indicators": [{"key": k, "name_ar": k, "name_en": k, "value": v, "unit": u, "status": s} for k, v, u, s in rows]}}


def test_trend_direction_streak_and_unit_separation():
    tests = [_t("2026-01-01", [("ferritin", 20, "ng/mL", "low"), ("hgb", 13, "g/dL", "normal")]),
             _t("2026-04-01", [("ferritin", 15, "ng/mL", "low"), ("hgb", 13.1, "g/dL", "normal")]),
             _t("2026-07-01", [("ferritin", 9, "ng/mL", "low"), ("hgb", 13.0, "g/dL", "normal")])]
    labs = {r["key"]: r for r in health_file.lab_trends(tests)}
    assert labs["ferritin"]["direction"] == "down" and labs["ferritin"]["out_of_range_streak"] == 3 and labs["ferritin"]["persistent"]
    assert [p["value"] for p in labs["ferritin"]["points"]] == [20, 15, 9]
    assert labs["hgb"]["direction"] == "stable" and not labs["hgb"]["persistent"]
    assert health_file.lab_trends(tests)[0]["key"] == "ferritin"      # attention items first


def test_different_units_are_never_mixed_and_bad_values_skipped():
    tests = [_t("2026-01-01", [("glucose", 5.5, "mmol/L", "normal")]), _t("2026-02-01", [("glucose", 100, "mg/dL", "normal")]),
             _t("2026-03-01", [("glucose", "n/a", "mg/dL", "normal")])]
    labs = health_file.lab_trends(tests)
    assert {(r["key"], r["unit"]): r["count"] for r in labs} == {("glucose", "mmol/L"): 1, ("glucose", "mg/dL"): 1}
    assert all(r["direction"] == "single" for r in labs)


def test_recurring_symptoms_threshold():
    recs = [{"symptoms": ["صداع", "غثيان"]}, {"symptoms": ["صداع"]}, {"symptoms": ["صداع", "تعب"]}]
    rows = {r["symptom"]: r for r in health_file.symptom_patterns(recs)}
    assert rows["صداع"]["recurring"] and rows["صداع"]["count"] == 3 and not rows["غثيان"]["recurring"]


def test_summary_is_neutral_bilingual_and_has_no_diagnosis_words():
    d = {"days": 365, "counts": {"analyses": 3, "lab_reports": 3, "medicines": 1, "high_urgency": 0},
         "recurring": [{"symptom": "صداع", "count": 3, "recurring": True}], "symptoms": [{"symptom": "صداع", "count": 3, "recurring": True}],
         "high_urgency_dates": [], "attention_labs": health_file.lab_trends([_t("2026-01-01", [("ferritin", 9, "ng/mL", "low")]),
                                                                           _t("2026-02-01", [("ferritin", 8, "ng/mL", "low")])]),
         "medicines": [{"name": "Panadol", "dose": "500mg", "frequency": ""}]}
    for lang in ("ar", "en"):
        text = health_file.summary_text(d, lang)
        assert "ferritin" in text and "Panadol" in text and "صداع" in text
        assert "diagnos" in text.lower() or "تشخيص" in text
        for bad in ("you have", "لديك مرض", "مصاب"):
            assert bad not in text


def test_render_escapes_user_text():
    d = {"days": 30, "counts": {"analyses": 1, "lab_reports": 0, "medicines": 0, "high_urgency": 0}, "labs": [], "attention_labs": [],
         "symptoms": [{"symptom": "<script>alert(1)</script>", "count": 1, "recurring": False}], "recurring": [], "medicines": [],
         "high_urgency_dates": [], "summary_text": "<img src=x onerror=alert(1)>"}
    out = health_file.render(d, "ar")
    assert "<script>" not in out and "<img src=x" not in out and "&lt;script&gt;" in out


def test_endpoints_require_login_and_return_only_own_data():
    anon = webapp.app.test_client()
    anon.set_cookie("lang", "ar")
    assert anon.get("/api/health-file").status_code == 401
    assert anon.get("/ar/health-file").status_code == 302
    db.init_db()
    uid, err = db.create_ss_user("hf-%s@example.test" % uuid.uuid4().hex[:8], "HF", "TestPassword123!")
    assert not err
    other, err = db.create_ss_user("hf-o-%s@example.test" % uuid.uuid4().hex[:8], "HF2", "TestPassword123!")
    for u in (uid, other):
        conn = db._conn(); conn.execute("UPDATE ss_users SET email_verified=1 WHERE id=?", (u,)); conn.commit(); conn.close()
    owner = "account-%s" % uid
    for _ in range(3):
        db.save_record(owner, "ar", 30, "female", ["صداع"], "يوم", 3, "low")
    db.save_blood_test(owner, {"indicators": [{"key": "ferritin", "name_ar": "فيريتين", "name_en": "Ferritin", "value": 9, "unit": "ng/mL", "status": "low"}]})
    db.save_record("account-%s" % other, "ar", 30, "male", ["سعال"], "يوم", 3, "low")
    c = webapp.app.test_client()
    c.set_cookie("lang", "ar")
    assert c.post("/api/consent/preferences", json={"service_usage": True, "analytics_research": False}).status_code == 200
    with c.session_transaction() as s:
        s["ss_user_id"] = uid
    r = c.get("/api/health-file?days=90").get_json()
    assert r["ok"] and r["counts"]["analyses"] == 3 and r["counts"]["lab_reports"] == 1
    assert [x["symptom"] for x in r["symptoms"]] == ["صداع"] and r["recurring"][0]["count"] == 3
    page = c.get("/ar/health-file")
    assert page.status_code == 200 and "فيريتين" in page.get_data(as_text=True) and "سعال" not in page.get_data(as_text=True)
    assert c.get("/api/health-file?days=abc").status_code == 400


def test_summary_includes_latest_analysis_details():
    d = {"days": 30, "counts": {"analyses": 1, "lab_reports": 0, "medicines": 0, "high_urgency": 0}, "recurring": [], "symptoms": [],
         "high_urgency_dates": [], "attention_labs": [], "medicines": [],
         "last_detail": {"date": "2026-07-01", "symptoms": ["صداع"], "duration": "3 أيام", "severity": "6", "urgency": "medium"}}
    assert "3 أيام" in health_file.summary_text(d, "ar") and "severity: 6" in health_file.summary_text(d, "en")


def test_trend_verdict_direction_only():
    P = lambda v, s: {"value": v, "status": s}
    assert health_file.trend_verdict(P(11.1, "low"), P(12.3, "low")) == "toward_reference"      # low and rising
    assert health_file.trend_verdict(P(11.1, "low"), P(10.2, "low")) == "away_from_reference"
    assert health_file.trend_verdict(P(11.1, "low"), P(11.2, "low")) == "stable"
    assert health_file.trend_verdict(P(11.1, "low"), P(13.0, "normal")) == "toward_reference"
    assert health_file.trend_verdict(P(13.0, "normal"), P(11.0, "low")) == "away_from_reference"
    assert health_file.trend_verdict(P(210, "high"), P(180, "high")) == "toward_reference"      # high and falling
    assert health_file.trend_verdict(P(5, "low"), P(20, "high")) == "away_from_reference"
    assert health_file.trend_verdict(P(5, "unclassified"), P(5, "low")) == "unknown"
    rows = {r["key"]: r for r in health_file.lab_trends([_t("2026-01-01", [("hgb", 11.1, "g/dL", "low")]), _t("2026-03-01", [("hgb", 12.3, "g/dL", "low")])])}
    assert rows["hgb"]["verdict"] == "toward_reference"


def test_doctor_page_is_compact_escaped_and_complete():
    d = {"days": 90, "counts": {}, "recurring": [{"symptom": "صداع", "count": 3, "recurring": True}], "symptoms": [],
         "high_urgency_dates": ["2026-07-01"], "medicines": [{"name": "<b>Panadol</b>", "dose": "500mg", "frequency": ""}],
         "labs": health_file.lab_trends([_t("2026-01-01", [("hgb", 11.1, "g/dL", "low")]), _t("2026-03-01", [("hgb", 12.3, "g/dL", "low")])]),
         "last_detail": {"date": "2026-07-01", "symptoms": ["صداع"], "duration": "3 أيام", "severity": "4", "urgency": "high"},
         "followup_outcomes": ["ساءت (2026-07-02)"], "vitals": []}
    out = health_file.render_doctor(d, "ar")
    for need in ("صداع", "3 أيام", "4/5", "مرتفع", "يتجه نحو النطاق المرجعي", "Panadol", "ساءت", "2026-07-01"):
        assert need in out
    assert "<b>Panadol" not in out and "&lt;b&gt;" in out
    assert len(out) < 6000
