import source_bundle
from pathlib import Path

import analysis_core
import blood_test
import health_search
import medical_knowledge
import mental_support

ROOT = Path(__file__).resolve().parent


def test_v73_coverage_grew_without_replacing_existing_kb():
    assert len(medical_knowledge.SYMPTOMS) >= 223
    assert len(medical_knowledge.DISEASES) >= 139
    assert len(health_search.SEARCH_KB) >= 110


def test_common_new_symptoms_match_source_grounded_conditions():
    samples = {
        "اذني مسدودة": "earwax-build-up",
        "ذبابات العين": "eye-floaters-flashes",
        "حازوقة": "persistent-hiccups",
        "ريحة الفم": "halitosis",
        "بقع بيضاء بالفم": "oral-thrush",
        "فطريات الفم": "oral-thrush",
        "ينزل بول لما اكح": "urinary-incontinence-pattern",
        "تشنج الساق": "common-leg-cramps",
        "دوالي الساق": "varicose-veins",
        "اصابعي تصير بيضاء بالبرد": "raynauds-pattern",
    }
    for phrase, slug in samples.items():
        bundle = medical_knowledge.knowledge_bundle([phrase], severity=1, notes=phrase, lang="ar")
        match = (bundle.get("matches") or [None])[0]
        assert match is not None, phrase
        assert match["slug"] == slug, phrase
        source = match.get("explanation_source") or {}
        assert source.get("reference_url", "").startswith("https://www.nhs.uk/"), phrase


def test_search_expansion_handles_new_everyday_phrases():
    for phrase in ["شمع الأذن", "ذبابات العين", "حازوقة", "ريحة الفم", "فطريات الفم", "سلس بول", "هبات ساخنة", "تشنج الساق", "دوالي", "رينو"]:
        result = health_search.search_health(phrase, "ar")
        assert result
        assert result.get("recognized_topics"), phrase
        assert result.get("sources"), phrase


def test_explainability_carries_the_exact_condition_source():
    bundle = medical_knowledge.knowledge_bundle(["حازوقة"], severity=1, notes="حازوقة", lang="ar")
    xai = analysis_core.build_explainability({"severity": 1}, bundle, "ar")
    evidence = xai["condition_evidence"][0]
    assert evidence["source"]["reference_url"].endswith("/symptoms/hiccups/")
    matched_factor = next(f for f in xai["factors"] if f.get("key") == "symptom_match")
    assert matched_factor["source_ref"]["reference_url"].endswith("/symptoms/hiccups/")


def test_cbc_abnormal_cards_include_contextual_symptoms_and_source():
    rows = [{
        "key": "hgb", "name_ar": "هيموغلوبين", "name_en": "Hemoglobin",
        "unit": "g/dL", "value": 9.2, "low": 12.0, "high": 15.5, "status": "low",
    }]
    detail = blood_test.describe_results(rows, "ar")[0]
    assert len(detail["symptoms"]) >= 5
    assert any("تعب" in x for x in detail["symptoms"])
    assert "الرقم وحده" in detail["symptoms_context"]
    assert detail["source"]["url"].startswith("https://medlineplus.gov/")


def test_mental_support_has_more_specific_everyday_intents():
    assert "10" in mental_support.supportive_answer("متراكم علي وما اقدر ابدا", "ar")
    assert "حكم الناس" in mental_support.supportive_answer("عندي قلق اجتماعي وأتوتر قدام الناس", "ar")
    assert "فكرة مزعجة" in mental_support.supportive_answer("تجيني أفكار ملحة ومزعجة", "ar")
    assert "خيارين" in mental_support.supportive_answer("محتارة وما أعرف أقرر", "ar")
    assert "ما أقدر ألتزم" in mental_support.supportive_answer("ما اقدر اقول لا للناس", "ar")


def test_result_ui_places_source_inside_explanation_card():
    chat = source_bundle.chat_view_text()
    web = source_bundle.webapp_text()
    assert "مرجع هذا التفسير" in chat
    assert "Source for this explanation" in chat
    assert "m.explanation_source" in chat
    assert "bl_symptoms" in web and "bl_source" in web
