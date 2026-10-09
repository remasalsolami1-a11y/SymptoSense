import source_bundle
from pathlib import Path

import analysis_core
import blood_test
import health_search
import medical_knowledge
import safety_engine


def test_safety_engine_keeps_emergency_for_true_immediate_flags():
    assert safety_engine.evaluate({"symptoms": ["ألم شديد في الصدر"]}, "ar")["emergency"] is True
    assert safety_engine.evaluate({"symptoms": ["فاقد الوعي الآن ولا يستجيب"]}, "ar")["emergency"] is True
    assert safety_engine.evaluate({"symptoms": ["عندي تشنج الآن"]}, "ar")["emergency"] is True


def test_resolved_faint_and_resolved_seizure_do_not_force_ambulance():
    assert safety_engine.evaluate({"symptoms": ["أغمي علي قبل ساعتين والآن طبيعي"]}, "ar")["emergency"] is False
    assert safety_engine.evaluate({"symptoms": ["صار لي تشنج أمس وانتهى"]}, "ar")["emergency"] is False
    assert analysis_core._triage({"symptoms": ["أغمي علي قبل ساعتين والآن طبيعي"], "severity": 3, "duration": "اليوم"}, "ar")["level"] == "today"


def test_severity_five_alone_is_same_day_not_ambulance():
    result = analysis_core._triage({"symptoms": ["ألم ظهر شديد"], "severity": 5, "duration": "اليوم"}, "ar")
    assert result["level"] == "today"


def test_professional_content_expansion_counts_and_topics():
    assert len(medical_knowledge.SYMPTOMS) >= 290
    assert len(medical_knowledge.DISEASES) >= 158
    assert len(health_search.SEARCH_KB) >= 136
    assert len(blood_test.REFS) >= 52
    assert any(d.get("slug") == "heart-failure-pattern" for d in medical_knowledge.DISEASES)
    assert any(d.get("slug") == "chronic-kidney-disease-pattern" for d in medical_knowledge.DISEASES)
    assert "foamy_urine" in health_search.SEARCH_KB
    assert "dysphagia" in health_search.SEARCH_KB
    assert "troponin" in blood_test.REFS
    assert "crp" in blood_test.REFS
    assert "free_t4" in blood_test.REFS


def test_new_blood_markers_never_get_application_owned_ranges():
    for key in {"free_t4", "crp", "esr", "magnesium", "phosphate", "uric_acid", "ggt", "lipase", "folate", "anc", "troponin"}:
        ranges = blood_test.REFS[key][3]
        assert ranges == (None, None, None, None)


def test_source_grounding_for_high_stakes_new_content():
    heart = next(d for d in medical_knowledge.DISEASES if d.get("slug") == "heart-failure-pattern")
    kidney = next(d for d in medical_knowledge.DISEASES if d.get("slug") == "chronic-kidney-disease-pattern")
    assert {x[0] for x in heart["sources"]} >= {"saudi-moh", "aha"}
    assert {x[0] for x in kidney["sources"]} >= {"saudi-moh", "niddk"}
    assert blood_test.DIRECT_SOURCES["troponin"]["url"].startswith("https://")


def test_seo_meta_social_meta_and_about_description_are_preserved():
    src = source_bundle.webapp_text()
    assert '<meta name="description" content="{safe_desc}">' in src
    assert '<meta property="og:description" content="{safe_desc}">' in src
    assert '<meta name="twitter:description" content="{safe_desc}">' in src
    assert 'تعرف على ريماس حميد السلمي وقصة تطوير SymptoSense.' in src
    assert 'if not desc:\n            desc = seo_desc' in src
    for route in ["/privacy", "/terms", "/blood", "/meds", "/firstaid", "/calculators", "/emergency", "/search"]:
        assert f'"{route}":' in src


def test_duplicate_legacy_routes_are_permanent_redirects():
    src = source_bundle.webapp_text()
    assert 'return redirect(_localized_url("/", selected or _lang()), code=301)' in src
    assert src.count('return redirect(_localized_url("/about"), code=301)') >= 3


def test_mobile_and_accessibility_hardening_is_shipped_with_cache_bust():
    src = source_bundle.webapp_text()
    assert '/assets/app-shell-v112.css?v=276' in src
    assert ':focus-visible{outline:3px solid #0b5f96!important' in src
    assert 'input:not([type="checkbox"]):not([type="radio"]),select,textarea{font-size:16px!important' in src
    assert '<div class="drop" id="drop" role="button" tabindex="0"' in src
    assert 'drop.addEventListener(\'keydown\'' in src
    assert 'id="bloodRes" role="region" aria-live="polite"' in src
