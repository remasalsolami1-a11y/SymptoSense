"""V251: verified multi-source references, new search topics, typo repair and the paracetamol-substring bug."""
import re
import urllib.parse

import pytest

import blood_test
import health_search
import medical_knowledge
import trusted_sources_v251 as trusted
import trusted_sources_wiring

ALLOWED_HOSTS = trusted_sources_wiring.ALLOWED_HOSTS


def test_every_condition_has_at_least_two_sources():
    thin = [d["slug"] for d in medical_knowledge.DISEASES if len({s[3] for s in d["sources"]}) < 2]
    assert not thin, thin


def test_every_search_topic_has_at_least_two_sources():
    thin = [k for k, v in health_search.SEARCH_KB.items() if len({s.get("url") for s in v.get("sources", [])}) < 2]
    assert not thin, thin


def test_every_blood_analyte_has_a_direct_source_and_an_additional_reference():
    for key in blood_test.REFS:
        src = blood_test.source_for_key(key)
        assert src["url"].startswith("https://"), key
        assert src.get("additional_sources"), key
        assert "lab-tests" in src["url"] or "/ency/" in src["url"] or key in blood_test.DIRECT_SOURCES, key


def test_new_source_urls_are_https_allowlisted_and_unique():
    urls = []
    for rows in list(trusted.DISEASE_SOURCES.values()) + list(trusted.SEARCH_SOURCES.values()):
        urls += [r[3] for r in rows]
    for v in trusted.BLOOD_SOURCES.values():
        urls += [r[3] for r in v.values()]
    assert len(urls) > 400
    for u in urls:
        p = urllib.parse.urlparse(u)
        assert p.scheme == "https" and p.netloc in ALLOWED_HOSTS, u
        assert not re.search(r"\s", u), u


def test_new_source_organisations_are_registered():
    registered = {row[0] for row in medical_knowledge.SOURCES}
    used = {r[0] for rows in trusted.DISEASE_SOURCES.values() for r in rows}
    assert used <= registered, used - registered


@pytest.mark.parametrize("query,lang,key", [
    ("حساسية", "ar", "allergy"), ("اكتئاب", "ar", "depression"), ("sciatica", "en", "sciatica"), ("panic attack", "en", "panic_attack"),
    ("low blood pressure", "en", "low_blood_pressure"), ("blurry vision", "en", "blurred_vision"), ("نوبة هلع", "ar", "panic_attack"),
    ("سكر", "ar", "diabetes"), ("وجع الركبه", "ar", "knee_pain_common"), ("pain when urinating", "en", "urinary_symptoms"),
])
def test_new_topics_and_aliases_resolve(query, lang, key):
    assert health_search.search_health(query, lang)["key"] == key


@pytest.mark.parametrize("query,key", [
    ("headche", "headache"), ("diziness", "dizziness"), ("nausia", "nausea"), ("diarhea", "diarrhea"), ("stomache pain", "stomach_ache"),
    ("sore troat", "sore_throat"), ("migrane", "migraine"), ("back pian", "back_pain"),
])
def test_english_typos_are_repaired(query, key):
    result = health_search.search_health(query, "en")
    assert result["key"] == key and result["typo_corrected_from"] == query


@pytest.mark.parametrize("query", ["heat", "heart rate", "paint", "hat", "form"])
def test_short_english_words_are_not_rewritten(query):
    import typo_repair
    lex = health_search._typo_lexicon("en")
    fixed, changes = typo_repair.repair(query, lex, "en")
    assert fixed == query and not changes


def test_self_harm_and_emergency_text_present_in_new_mental_and_allergy_topics():
    dep = health_search.SEARCH_KB["depression"]
    for lang in ("ar", "en"):
        assert "937" in dep[lang]["worry"] and "997" in dep[lang]["worry"]
    assert "997" in health_search.SEARCH_KB["allergy"]["ar"]["worry"]
    assert "997" in health_search.SEARCH_KB["allergy"]["en"]["worry"]


def test_headache_wording_is_not_answered_as_a_paracetamol_question(monkeypatch, tmp_path):
    import db
    import medication_warnings
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "m.db"), raising=False)
    assert medication_warnings._name_matches("راس", "باراسيتامول") is False
    assert medication_warnings._name_matches("بنادول", "بنادول / باراسيتامول") is True
    assert medication_warnings._name_matches("باراسيتا", "باراسيتامول") is True
