"""V252: red-flag screening questions chosen from the entered symptoms."""
import pytest

import analysis_core
import redflag_screen
import webapp


@pytest.fixture(scope="module")
def client():
    c = webapp.app.test_client()
    c.environ_base["REMOTE_ADDR"] = "192.0.2.88"
    assert c.post("/api/consent/preferences", json={"service_usage": True, "analytics_research": False}).status_code == 200
    return c


def test_bank_is_well_formed_and_bilingual():
    ids = [s["id"] for s in redflag_screen.SCREENS]
    assert len(ids) == len(set(ids)) >= 15
    for s in redflag_screen.SCREENS:
        assert s["tier"] in {"emergency", "today"}
        assert s["q_ar"].endswith("؟") and s["q_en"].endswith("?")
        assert s["flag_ar"] and s["flag_en"] and s["slugs"]
        # a screen asks about warning signs; it must never name a disease
        for word in ("سرطان", "cancer", "diagnos", "تشخيص"):
            assert word not in s["q_ar"].lower() + s["q_en"].lower()


def test_every_slug_in_the_bank_exists_in_the_library():
    import medical_knowledge as mk
    known = {s[0] for s in mk.SYMPTOMS}
    missing = {slug for s in redflag_screen.SCREENS for slug in s["slugs"]} - known
    assert not missing, missing


@pytest.mark.parametrize("symptoms,first", [
    (["ألم صدر"], "cp_"), (["صداع"], "ha_"), (["ضيق نفس"], "sob_"), (["ألم بطن"], "ab_"), (["حمى"], "fv_"), (["ألم ظهر"], "bk_cauda"),
])
def test_next_screen_matches_the_symptom_and_emergency_comes_first(symptoms, first):
    s = redflag_screen.next_screen(symptoms, [], 30)
    assert s and s["id"].startswith(first) and s["tier"] == "emergency"


def test_unrelated_symptom_gets_no_screen_and_cap_is_enforced():
    assert redflag_screen.next_screen(["تعب"], [], 30) is None
    assert redflag_screen.next_screen(["ألم صدر"], ["a", "b", "c", "d"], 30) is None


def test_asked_screens_are_not_repeated():
    seen, asked = [], []
    for _ in range(4):
        s = redflag_screen.next_screen(["ألم بطن", "حمى"], asked, 30)
        if not s:
            break
        assert s["id"] not in asked
        asked.append(s["id"])
    assert len(asked) >= 2


def test_endpoint_returns_screen_and_done(client):
    r = client.post("/api/analyze/redflag-next", json={"symptoms": ["ألم صدر"], "asked": [], "age": 40, "lang": "en"}).get_json()
    assert r["ok"] and not r["done"] and r["screen"]["question"].endswith("?")
    r = client.post("/api/analyze/redflag-next", json={"symptoms": ["تعب"], "asked": []}).get_json()
    assert r["ok"] and r["done"] and r["screen"] is None


def test_emergency_yes_stops_analysis_server_side():
    r = analysis_core.run_analysis({"age": 30, "gender": "male", "symptoms": ["ألم صدر"], "notes": "", "duration": "يوم",
                                    "severity": 2, "redflag_yes": ["cp_radiating"]}, "ar")
    assert r["emergency"] is True and r["urgency"] == "high"


def test_unknown_or_malformed_ids_are_ignored():
    r = analysis_core.run_analysis({"age": 30, "gender": "male", "symptoms": ["تعب"], "notes": "", "duration": "يوم",
                                    "severity": 2, "redflag_yes": ["nope", "../x", 5]}, "ar")
    assert r["emergency"] is False


def test_analyze_endpoint_accepts_redflag_yes(client):
    r = client.post("/api/analyze", json={"age": 30, "gender": "male", "symptoms": ["ألم صدر"], "duration": "يوم", "severity": 2,
                                          "notes": "", "lang": "ar", "redflag_yes": ["cp_pressure"]})
    assert r.status_code == 200 and r.get_json()["emergency"] is True


def test_client_calls_screens_before_differential_and_blocks_on_emergency():
    import source_bundle
    src = source_bundle.chat_view_text()
    assert "startRedflagScreens" in src and "/api/analyze/redflag-next" in src
    assert src.index("else startRedflagScreens();") < src.index("async function startDifferentialQuestions")
    assert "sc.tier === 'emergency'" in src and "showEmergency(clarEmergencyResult(sc.flag))" in src
