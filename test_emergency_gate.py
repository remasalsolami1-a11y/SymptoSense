"""V253: a red-flag notice on every free-text entry point, not only the symptom flow."""
from pathlib import Path

import pytest

import emergency_gate
import webapp

ROOT = Path(__file__).resolve().parent


@pytest.fixture(scope="module")
def client():
    c = webapp.app.test_client()
    c.environ_base["REMOTE_ADDR"] = "192.0.2.61"
    assert c.post("/api/consent/preferences", json={"service_usage": True, "analytics_research": False}).status_code == 200
    return c


@pytest.mark.parametrize("text,number", [("ألم صدر شديد", "997"), ("ابي انتحر", "937"), ("اخذت حبوب كثير", "997")])
def test_notice_for_red_flag_text(text, number):
    n = emergency_gate.notice(text, "ar")
    assert n and n["number"] == number and n["flags"] and n["rule_ids"]


@pytest.mark.parametrize("text", ["ما هو ألم الصدر", "chest pain what causes it", "فيتامين د نقص", "وش اعراض الجلطة", ""])
def test_no_notice_for_educational_or_empty_text(text):
    assert emergency_gate.notice(text, "ar") is None


def test_search_endpoint_attaches_notice_only_for_red_flags(client):
    r = client.get("/api/search", query_string={"q": "ألم صدر شديد", "lang": "ar"}).get_json()
    assert r["ok"] and r["safety_notice"]["number"] == "997" and r["result"]
    r = client.get("/api/search", query_string={"q": "ما هو ألم الصدر", "lang": "ar"}).get_json()
    assert "safety_notice" not in r


def test_medicine_endpoints_attach_notice(client):
    r = client.post("/api/meds", json={"text": "اخذت حبوب كثير من الباراسيتامول"}).get_json()
    assert r["ok"] and r["safety_notice"]["category"] == "general"
    r = client.post("/api/meds", json={"text": "باراسيتامول ايبوبروفين"}).get_json()
    assert "safety_notice" not in r
    r = client.get("/api/drug", query_string={"name": "paracetamol overdose"}).get_json()
    assert "safety_notice" in r


def test_notice_failure_never_breaks_the_response(client, monkeypatch):
    monkeypatch.setattr(emergency_gate, "notice", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    r = client.get("/api/search", query_string={"q": "ألم صدر شديد", "lang": "ar"})
    assert r.status_code == 200 and r.get_json()["ok"]
    import ops_metrics
    assert ops_metrics.snapshot()["counters"].get("error:safety_notice_failure", 0) >= 1


def test_front_end_banner_is_loaded_and_xss_safe():
    js = (ROOT / "static/js/safety-notice.js").read_text(encoding="utf8")
    assert "innerHTML" not in js and "insertAdjacentHTML" not in js and "eval(" not in js
    assert "tel:" in js and "textContent" in js
    html = client_page()
    assert "/static/js/safety-notice.js" in html


def client_page():
    c = webapp.app.test_client()
    c.set_cookie("lang", "ar")
    return c.get("/ar/search").get_data(as_text=True)
