"""V252: search covers lab tests and 2-3 word queries across symptoms, conditions and tests."""
import pytest

import blood_test
import search_fidelity
import search_lab_cards
import webapp


@pytest.fixture(scope="module")
def client():
    c = webapp.app.test_client()
    c.environ_base["REMOTE_ADDR"] = "192.0.2.77"
    assert c.post("/api/consent/preferences", json={"service_usage": True, "analytics_research": False}).status_code == 200
    return c


def _search(client, q):
    lang = "en" if q.isascii() else "ar"
    r = client.get("/api/search", query_string={"q": q, "lang": lang}).get_json()["result"]
    topics = r.get("matched_topics") or [r]
    keys = [t.get("key") for t in topics]
    nsrc = sum(len(t.get("sources") or []) for t in topics)
    return r, keys, nsrc


def test_every_blood_analyte_name_returns_a_sourced_card():
    for key, ref in blood_test.REFS.items():
        for name in (ref[0], ref[1]):
            card = search_lab_cards.lookup(name, "en" if name.isascii() else "ar", exact_only=True)
            assert card and card["lab_key"] == key, (key, name)
            assert len(card["sources"]) >= 2, (key, name)
            assert card["what"] and card["doctor"]


@pytest.mark.parametrize("q,key", [
    ("AST", "lab_ast"), ("ALT", "lab_alt"), ("CRP مرتفع", "lab_crp"), ("الصوديوم", "lab_sodium"),
    ("low magnesium", "lab_magnesium"), ("الكوليسترول الضار مرتفع", "lab_ldl"), ("حمض اليوريك", "lab_uric_acid"),
    ("إنزيم الليباز", "lab_lipase"), ("Cardiac troponin", "lab_troponin"),
])
def test_lab_queries_are_answered_from_blood_tables(client, q, key):
    r, keys, nsrc = _search(client, q)
    assert keys[0] == key and nsrc >= 2


def test_ast_is_not_confused_with_asthma(client):
    assert _search(client, "AST")[1][0] != "asthma"


def test_lab_direction_words_choose_the_matching_paragraph():
    high = search_lab_cards.lookup("CRP high", "en")
    low = search_lab_cards.lookup("low magnesium", "en")
    assert high["lab_direction"] == "high" and high["worry"].startswith("If high")
    assert low["lab_direction"] == "low" and low["worry"].startswith("If low")


@pytest.mark.parametrize("q,expected", [
    ("ألم اسفل يسار البطن", "left-lower-abdominal-pain"),
    ("حرقان بالبول", "urinary_symptoms"),
    ("نزيف انف", "nosebleed"),
    ("blood in urine", "blood-in-urine"),
    ("swollen lymph nodes", "swollen-lymph-nodes"),
    ("cold hands feet", "cold-extremities"),
    ("حكة في العين", "eye-itching"),
    ("ضغط الدم المنخفض", "low_blood_pressure"),
    ("frequent urination night", "nighttime_urination"),
    ("قدمي منتفخة", "leg_swelling"),
    ("neck stiffness fever", "stiff-neck"),
])
def test_two_or_three_word_queries_reach_the_right_sourced_topic(client, q, expected):
    r, keys, nsrc = _search(client, q)
    assert expected in keys, (q, keys)
    assert nsrc >= 2


def test_ambiguous_side_query_shows_both_candidates(client):
    r, keys, _ = _search(client, "وجع بطن يمين")
    assert "right-upper-abdominal-pain" in keys and "right-lower-abdominal-pain" in keys


def test_query_that_matches_nothing_exactly_shows_closest_topic_not_unrelated_card(client):
    r, keys, nsrc = _search(client, "knee swelling")
    assert "salivary_gland_swelling" not in keys
    assert r.get("closest_match") and nsrc >= 2


def test_chest_pain_is_never_replaced_by_a_less_urgent_card(client):
    assert _search(client, "chest pain breathing")[1][0] == "chest_pain"


def test_coverage_helper_understands_synonyms_and_prefixes():
    assert search_fidelity.coverage("حرقان بالبول", "ألم عند التبول") >= 0.5
    assert search_fidelity.coverage("وجع بطن", "ألم البطن") == 1.0
    assert search_fidelity.coverage("knee swelling", "Salivary gland swelling with meals") == 0.5
    assert search_fidelity.content_tokens("what is the CRP level") == ["crp", "level"]


def test_single_word_and_empty_queries_are_untouched(client):
    assert search_fidelity.best_candidates("صداع", "ar") == []
    assert client.get("/api/search", query_string={"q": "", "lang": "ar"}).get_json()["result"] is None


@pytest.mark.parametrize("q,expected", [
    ("نزيف من الأنف", "nosebleed"), ("ألم عند البلع", "painful-swallowing"),
    ("دوخة مع الحركة أو السفر", "motion-triggered-dizziness"),
])
def test_exact_library_symptom_names_are_not_hijacked_by_generic_context_cards(client, q, expected):
    r, keys, nsrc = _search(client, q)
    assert keys[0] == expected and nsrc >= 2
    assert r.get("key") != "generic_context_relation"
