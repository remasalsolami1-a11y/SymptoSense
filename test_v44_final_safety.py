import source_bundle
import versioning
import os
import re
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# analysis_core imports the Groq client at module import time. These safety tests
# do not call the network, so provide the minimum import stub when the package
# is unavailable in the audit environment.
try:
    import groq  # noqa: F401
except Exception:
    mod = types.ModuleType("groq")
    class Groq:  # pragma: no cover - import shim only
        pass
    mod.Groq = Groq
    sys.modules["groq"] = mod

import clinical_text
import medical_knowledge
import mental_support
import analysis_core
import health_search


def test_negated_red_flags_do_not_trigger_arabic_or_english():
    cases = [
        ("لا يوجد ألم في الصدر", "ألم في الصدر"),
        ("ما عندي ضيق في التنفس", "ضيق في التنفس"),
        ("no chest pain", "chest pain"),
        ("I am not confused", "confused"),
        ("not poisoned", "poisoned"),
    ]
    for text, phrase in cases:
        assert not clinical_text.contains_unnegated_phrase(text, phrase), (text, phrase)


def test_positive_red_flags_still_trigger():
    assert clinical_text.contains_unnegated_phrase("عندي ألم في الصدر", "ألم في الصدر")
    assert clinical_text.contains_unnegated_phrase("I have chest pain", "chest pain")
    assert clinical_text.contains_unnegated_phrase("لا أستطيع التنفس", "لا أستطيع التنفس")


def test_symptom_normalizer_separates_negated_symptoms():
    r = medical_knowledge.normalize_symptoms(["صداع لكن لا يوجد ألم في الصدر"])
    canonical = [x["slug"] for x in r["canonical"]]
    negated = [x["slug"] for x in r.get("negated", [])]
    assert "headache" in canonical
    assert "chest-pain" not in canonical
    assert "chest-pain" in negated

    r = medical_knowledge.normalize_symptoms(["headache but no chest pain"])
    canonical = [x["slug"] for x in r["canonical"]]
    negated = [x["slug"] for x in r.get("negated", [])]
    assert "headache" in canonical
    assert "chest-pain" not in canonical
    assert "chest-pain" in negated


def test_triage_does_not_escalate_negated_chest_or_breathing():
    ar = analysis_core._triage({"symptoms": ["صداع"], "notes": "لا يوجد ألم في الصدر", "severity": 1}, "ar")
    en = analysis_core._triage({"symptoms": ["headache"], "notes": "no chest pain", "severity": 1}, "en")
    ar_breath = analysis_core._triage({"symptoms": ["صداع"], "notes": "ما عندي ضيق في التنفس", "severity": 1}, "ar")
    assert ar["level"] == "monitor"
    assert en["level"] == "monitor"
    assert ar_breath["level"] == "monitor"


def test_triage_distinguishes_urgent_from_emergency_chest_breathing():
    # A generic isolated symptom is urgent for same-day assessment, not
    # automatically labelled a life-threatening emergency.
    ar_chest = analysis_core._triage({"symptoms": ["ألم في الصدر"], "notes": "", "severity": 2}, "ar")
    en_breath = analysis_core._triage({"symptoms": ["shortness of breath"], "notes": "", "severity": 2}, "en")
    assert ar_chest["level"] == "today"
    assert en_breath["level"] == "today"

    # Severe symptoms or dangerous combinations remain emergency-level.
    severe = analysis_core._triage({"symptoms": ["ألم شديد في الصدر"], "notes": "", "severity": 4}, "ar")
    combo = analysis_core._triage({"symptoms": ["chest pain", "shortness of breath"], "notes": "", "severity": 3}, "en")
    assert severe["level"] == "emergency"
    assert combo["level"] == "emergency"


def test_mental_safety_understands_negation_but_keeps_direct_crisis_phrases():
    assert mental_support.safety_level("I am not confused") != "medical_redflag"
    assert mental_support.safety_level("no severe chest pain") != "medical_redflag"
    assert mental_support.safety_level("I don't want to die") != "direct"
    assert mental_support.safety_level("I do not want to die") != "direct"
    # The whole phrase is itself a crisis phrase; its leading "don't" must not cancel it.
    assert mental_support.safety_level("I don't want to live") == "direct"


def test_all_health_search_topics_have_source_metadata():
    assert health_search.SEARCH_KB
    for key, item in health_search.SEARCH_KB.items():
        assert item.get("sources"), key
        assert item.get("last_reviewed"), key
        assert item.get("population_scope"), key
        for src in item["sources"]:
            assert str(src.get("url", "")).startswith("https://"), (key, src)


def test_release_metadata_is_v44_final():
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    rc = (ROOT / "release_candidate.py").read_text(encoding="utf-8")
    sw = (ROOT / "service-worker.js").read_text(encoding="utf-8")
    assert "APP_VERSION=" + versioning.APP_VERSION in env
    assert "RELEASE_CANDIDATE_ID=" + versioning.RC_ID in env
    assert versioning.RC_ID == __import__("release_candidate").RC_ID
    assert versioning.SW_CACHE in sw


def test_webapp_contains_production_guards_and_hospital_rate_limit():
    src = source_bundle.webapp_text()
    assert "X-Real-IP" in src
    assert 'missing.append("DATABASE_URL")' in src
    assert "Unsafe production configuration; missing:" in src
    assert "WEB_SECRET" in src and "32" in src
    assert '"nearby_hospitals"' in src and "HOSPITALS_RATE_LIMIT_MAX" in src
    assert "OpenStreetMap" in src and "Overpass" in src
    assert "GROQ_VISION_MODEL_FALLBACK" in src


def test_bot_arabic_prompts_are_neutral_for_known_old_gendered_phrases():
    src = (ROOT / "bot.py").read_text(encoding="utf-8")
    for old in ("ردّي", "انتبهي", "قولي", "ابدئي", "تحتاجين", "توجهي", "اللي تحسين فيه"):
        assert old not in src


def test_runtime_requirements_include_direct_pillow_dependency():
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    assert re.search(r"^pillow[<=>]", req, flags=re.MULTILINE)


def test_bot_voice_symptom_extractor_is_negation_aware_static():
    src = (ROOT / "bot.py").read_text(encoding="utf-8")
    assert "def _extract_symptoms_from_text" in src
    assert "clinical_text.contains_unnegated_phrase(text, kw)" in src
    assert 'BOT_VERSION = "2026-09-17-v44-final"' in src


def test_medication_detection_respects_explicit_non_use():
    import medication_warnings
    assert medication_warnings.check_medications("I take aspirin")
    assert not medication_warnings.check_medications("I do not take aspirin")
    assert not medication_warnings.check_medications("I am not taking aspirin")
    assert not medication_warnings.check_medications("لا أتناول aspirin")
