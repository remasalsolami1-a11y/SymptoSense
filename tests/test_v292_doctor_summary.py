"""V292: the doctor summary in Arabic and English."""
import doctor_summary
import webapp


def test_names_come_from_the_knowledge_base_and_free_text_is_marked():
    r = doctor_summary.build({"age": 28, "gender": "male", "symptoms": ["صداع", "حمى", "شي غريب"], "duration": "📅 1-3 أيام",
                              "severity": 2, "yes": ["neck-pain"], "no": ["vomiting"], "matches": ["influenza"], "urgency": "soon"})
    assert "Symptoms: Headache, Fever, شي غريب (patient's words)" in r["en"]
    assert "Duration: 1-3 days" in r["en"] and "Confirmed on follow-up: Neck pain" in r["en"] and "Denied on follow-up: Vomiting" in r["en"]
    assert "Assessment urgency: Needs an appointment soon" in r["en"] and "Influenza" in r["en"]
    assert "الأعراض: صداع، حمى، شي غريب" in r["ar"] and "not a medical diagnosis" in r["en"]
    assert doctor_summary._duration_en("كلام حر") == "كلام حر (patient's words)"


def test_endpoint_needs_consent_and_returns_both_languages():
    c = webapp.app.test_client()
    assert c.post("/api/doctor-summary", json={"symptoms": ["صداع"]}).status_code == 403
    c.post("/api/consent/preferences", json={"service_usage": True})
    j = c.post("/api/doctor-summary", json={"symptoms": ["صداع"], "urgency": "low"}).get_json()
    assert j["ok"] and "Headache" in j["en"] and "صداع" in j["ar"]


def test_doctor_card_offers_the_language_tabs():
    from pathlib import Path
    js = (Path(__file__).resolve().parents[1] / "static" / "js" / "chat" / "doctor-summary.js").read_text(encoding="utf-8")
    assert "fetch('/api/doctor-summary'" in js and 'data-sum-lang="both"' in js
