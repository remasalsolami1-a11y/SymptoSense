import source_bundle
from pathlib import Path

import analysis_core

ROOT = Path(__file__).resolve().parent
CHAT = source_bundle.chat_view_text()
WEB = source_bundle.webapp_text()


def test_input_quality_exposes_three_user_facing_states():
    limited = analysis_core.assess_data_quality({"symptoms": []}, "ar")
    assert limited["user_state"] == "limited"
    assert "معلومات محدودة" in limited["user_state_label"]

    sufficient = analysis_core.assess_data_quality(
        {"symptoms": ["صداع"], "duration": "يوم", "severity": 2}, "ar"
    )
    assert sufficient["sufficient"] is True
    assert sufficient["user_state"] in {"sufficient", "improvable"}
    assert "احتمال" not in sufficient["user_state_label"]


def test_blood_context_is_absent_without_explicit_linked_blood_payload():
    ctx = analysis_core.build_blood_symptom_context({"symptoms": ["دوخة"]}, "ar")
    assert ctx["used"] is False
    assert ctx["relevant_indicators"] == []
    assert ctx["ranking_affected"] is False


def test_blood_context_only_surfaces_relevant_abnormal_markers():
    ctx = analysis_core.build_blood_symptom_context({
        "symptoms": ["دوخة"],
        "blood_id": 7,
        "blood": {
            "summary": "saved",
            "indicators": [
                {"key": "hgb", "name": "HGB", "value": 9.2, "unit": "g/dL", "status": "low"},
                {"key": "plt", "name": "PLT", "value": 250, "unit": "10^9/L", "status": "normal"},
                {"key": "alt", "name": "ALT", "value": 80, "unit": "U/L", "status": "high"},
            ],
        },
    }, "ar")
    assert ctx["used"] is True
    assert ctx["blood_id"] == 7
    assert [x["key"] for x in ctx["relevant_indicators"]] == ["hgb"]
    assert ctx["ranking_affected"] is False


def test_blood_context_never_changes_differential_ranking():
    base = {
        "symptoms": ["دوخة", "غثيان"],
        "duration": "يوم",
        "severity": 2,
        "age": 25,
        "gender": "f",
    }
    without = analysis_core.run_analysis(dict(base), "ar")
    with_blood = analysis_core.run_analysis(dict(base, blood_id=9, blood={
        "summary": "saved",
        "indicators": [{"key": "hgb", "name": "HGB", "value": 9, "unit": "g/dL", "status": "low"}],
    }), "ar")
    assert [x.get("slug") for x in without.get("knowledge_matches", [])] == [x.get("slug") for x in with_blood.get("knowledge_matches", [])]
    assert without.get("risk_level") == with_blood.get("risk_level")
    assert with_blood["blood_context"]["used"] is True
    assert with_blood["blood_context"]["ranking_affected"] is False


def test_chat_requires_explicit_blood_choice_instead_of_auto_attaching_local_storage():
    assert "chooseBloodContextThenAnalyze" in CHAT
    assert "Use blood test" in CHAT
    assert "Continue without it" in CHAT
    assert "if (selectedBloodId) payload.blood_id" in CHAT
    assert "localStorage.getItem('symptosense_blood_id'); if (b) payload.blood_id" not in CHAT


def test_backend_only_loads_owned_blood_record_when_blood_id_is_supplied():
    assert 'blood_id = data.get("blood_id")' in WEB
    assert 'bt = db.get_blood_test(_data_user_id(), blood_id)' in WEB
    assert 'patient["blood_id"] = int(blood_id)' in WEB
