"""V197: colloquial / Gulf-dialect emergency coverage for the deterministic safety engine.

V198 precision supersedes a few broad V197 assumptions: dialect coverage is
preserved, but an ambiguous bare seizure, pregnancy bleeding without severe
features, and infant fever no longer trigger an ambulance-level bypass.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import safety_engine  # noqa: E402


def _emergency(symptoms, notes="", lang="ar"):
    return safety_engine.evaluate({"symptoms": list(symptoms), "notes": notes}, lang=lang)


POSITIVE = [
    # consciousness / unresponsive
    (["فاقد الوعي"], "loss_of_consciousness"),
    (["أخوي طاح ومايرد"], "loss_of_consciousness"),
    (["طاح وما يرد"], "loss_of_consciousness"),
    (["مغمى عليه"], "loss_of_consciousness"),
    (["he collapsed and is not responding"], "loss_of_consciousness"),
    # seizure
    (["يتشنج الحين"], "active_seizure"),
    (["رجل يتشنج على الأرض"], "active_seizure"),
    # chest / breathing
    (["صدري يعورني مرة"], "severe_chest_pain"),
    (["ألم في الصدر ينتشر لليد اليسار"], "chest_pain_cardiac_features"),
    (["ألم في الصدر مع تعرق"], "chest_pain_cardiac_features"),
    (["chest pain spreading to left arm"], "chest_pain_cardiac_features"),
    (["نفسي مقطوع"], "severe_breathing"),
    (["ما اقدر اخذ نفس"], "severe_breathing"),
    (["احس اني اختنق"], "severe_breathing"),
    (["gasping for air"], "severe_breathing"),
    # anaphylaxis
    (["تورم في الحلق", "ضيق تنفس"], "anaphylaxis_pattern"),
    (["وجهي منتفخ وصعب اتنفس"], "anaphylaxis_pattern"),
    # stroke
    (["فمي مايل"], "stroke_pattern"),
    (["ما اقدر احرك يدي اليمين"], "stroke_pattern"),
    (["كلامي ثقيل فجأة"], "stroke_pattern"),
    (["my face is drooping"], "stroke_pattern"),
    (["sudden weakness in my arm"], "stroke_pattern"),
    # bleeding
    (["دم كثير ينزف"], "severe_bleeding"),
    (["الدم ما يوقف"], "severe_bleeding"),
    (["ارجع دم"], "blood_vomit_or_cough"),
    (["coughing up blood"], "blood_vomit_or_cough"),
    # self-harm
    (["أبي أموت"], "self_harm_risk"),
    (["ودي انتحر"], "self_harm_risk"),
    (["افكر انهي حياتي"], "self_harm_risk"),
    (["I want to die"], "self_harm_risk"),
    # overdose / poisoning
    (["بلعت حبوب كثير"], "overdose_poisoning"),
    (["شرب مادة سامة"], "overdose_poisoning"),
    (["طفلي بلع حبوب"], "overdose_poisoning"),
    (["took too many pills"], "overdose_poisoning"),
    # special situations
    (["حامل ونزيف وألم شديد في البطن"], "pregnancy_bleeding_severe"),
    (["أسوأ صداع في حياتي"], "thunderclap_headache"),
    (["worst headache of my life"], "thunderclap_headache"),
]

NEGATIVE = [
    ["تشنج"],                              # ambiguous: clarify current vs past/spasm
    ["تشنجات"],                           # ambiguous without current/prolonged context
    ["ظهر عليه تشنج"],                    # event timing unclear
    ["حامل ونزيف"],                       # same-day review, not automatic ambulance
    ["حامل ونزيف خفيف بدون ألم"],         # same-day review
    ["رضيع حرارته 40"],                   # urgent clinical review, not ambulance by temperature alone
    ["صداع خفيف"],
    ["ركبتي تطقطق بدون ألم"],
    ["ما عندي ألم شديد في الصدر"],
    ["ألم في الصدر"],                       # chest pain alone stays with the clinical triage layer
    ["ألم في الصدر بدون تعرق"],
    ["تشنج في الساق"],                      # muscle spasm
    ["عضلاتي تتشنج"],
    ["تشنج بالرقبة"],
    ["ما عندي تشنج"],
    ["صار لي تشنج أمس وانتهى"],
    ["ما ابي اموت"],                        # "I don't want to die"
    ["ابي اموت من الضحك"],                  # idiom
    ["I am not suicidal"],
    ["حامل ونزيف من الأنف"],
    ["نزيف من الأنف"],
    ["رضيع بدون حرارة"],
    ["حرارة وكحة منذ يومين"],               # adult fever
    ["بلعت حبوب الدواء الصباحي"],           # ordinary medication
    ["تسمم غذائي"],
    ["no chest pain, sweating after gym"],
    ["أغمي علي قبل ساعتين والآن طبيعي"],    # resolved faint -> same-day review layer
]


@pytest.mark.parametrize("symptoms,rule", POSITIVE, ids=lambda v: v if isinstance(v, str) else "|".join(v))
def test_colloquial_emergency_is_detected(symptoms, rule):
    result = _emergency(symptoms)
    assert result["emergency"] is True, f"missed: {symptoms}"
    assert rule in result["rule_ids"], f"{symptoms}: expected {rule}, got {result['rule_ids']}"


@pytest.mark.parametrize("symptoms", NEGATIVE, ids=lambda v: "|".join(v))
def test_benign_or_negated_phrase_does_not_trigger(symptoms):
    result = _emergency(symptoms)
    assert result["emergency"] is False, f"false positive: {symptoms} -> {result['rule_ids']}"


def test_free_text_notes_are_covered_too():
    assert _emergency(["صداع"], notes="أخوي طاح ومايرد").get("emergency") is True


def test_builtin_matrix_still_passes_and_grew():
    report = safety_engine.validation_report()
    assert report["all_passed"] is True
    assert report["total"] >= 40


def test_self_harm_result_includes_verified_saudi_support_lines():
    safety = _emergency(["ابي اموت"])
    ar = safety_engine.emergency_result(safety, "ar")["when_to_seek_care"]
    en = safety_engine.emergency_result(_emergency(["I want to die"], lang="en"), "en")["when_to_seek_care"]
    for text in (ar, en):
        assert "997" in text and "937" in text and "920033360" in text
    other = safety_engine.emergency_result(_emergency(["فاقد الوعي"]), "ar")["when_to_seek_care"]
    assert "920033360" not in other
