"""V287: rules built from the error taxonomy — fire on new wordings, stay quiet on mild look-alikes."""
import json
from pathlib import Path

import pytest

import red_flag_concepts as rfc
import safety_engine

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "evaluation" / "taxonomy_dev_cases.json").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", [c for c in CASES if c["label"] == "high"], ids=lambda c: c["id"])
def test_every_urgent_taxonomy_case_is_an_emergency(case):
    assert safety_engine.evaluate({"symptoms": [case["text"]]}, lang=case["lang"])["emergency"], case["text"]


@pytest.mark.parametrize("case", [c for c in CASES if c["label"] != "high"], ids=lambda c: c["id"])
def test_mild_look_alikes_are_not_emergencies(case):
    assert not safety_engine.evaluate({"symptoms": [case["text"]]}, lang=case["lang"])["emergency"], case["text"]


@pytest.mark.parametrize("text, rule", [
    ("ما يقدر يكمل جملة من ضيق النفس", "concept_respiratory_distress"),
    ("His lips look bluish and he is struggling for breath", "concept_respiratory_distress"),
    ("My father is barely responsive", "concept_reduced_consciousness"),
    ("أمي عندها حرارة وصارت متلخبطة", "concept_sepsis"),
    ("Fever with a purple spotty rash that does not fade when pressed", "concept_sepsis"),
    ("يغمى علي أكثر من مرة وقلبي يدق بشكل غير منتظم", "concept_cardiac_syncope"),
    ("Can't keep any fluids down, hardly peeing and getting drowsy", "concept_severe_dehydration"),
    ("ألم شديد مفاجئ في عيني مع استفراغ ونظري صار ضبابي", "concept_acute_glaucoma"),
    ("Back pain with numbness around the groin and I can't control my bladder", "concept_cauda_equina"),
    ("رجلي صارت باردة وشاحبة فجأة وما أحس فيها", "concept_limb_ischaemia"),
    ("Sudden explosive headache, the worst I have ever had", "concept_thunderclap_headache"),
    ("فجأة كلامه صار ثقيل", "concept_stroke_speech"),
    ("قرصتني نحلة وصار وجهي منتفخ ونفسي ضيق", "concept_anaphylaxis"),
    ("عندي سكر وأحس برجفة وعرق ومتلخبط", "concept_diabetic_emergency"),
])
def test_each_new_rule_fires_on_its_type(text, rule):
    assert rule in {r for r, _a, _e in rfc.evaluate(text)}


@pytest.mark.parametrize("text", [
    "I'm a bit confused about which tablet to take",            # confusion without fever
    "Fainted once at a blood test years ago, fine since",       # syncope without cardiac features
    "Cold hands in winter",                                     # cold limb alone
    "My eye hurts a little after reading, vision fine",         # eye pain without severity / vision change
    "back pain after the gym",                                  # back pain alone
    "صداع قوي بعد السهر",                                       # severe headache, not sudden
    "Vomited twice, drinking and peeing normally",
])
def test_partial_patterns_do_not_fire(text):
    assert not rfc.evaluate(text), (text, rfc.evaluate(text))


def test_english_words_are_never_typo_corrected():
    assert rfc.correct_typos("back pain") == "back pain"     # used to become "black pain"
    assert "back_pain" in rfc.matched_concepts("I have back pain")


def test_switch_measures_the_new_rules():
    rfc.V287_ENABLED = False
    try:
        assert not rfc.evaluate("My father is barely responsive")
    finally:
        rfc.V287_ENABLED = True
    assert rfc.evaluate("My father is barely responsive")


def test_results_show_taxonomy_gain_and_no_new_false_alarms():
    res = json.loads((ROOT / "evaluation" / "results" / "results.json").read_text(encoding="utf-8"))
    off = res["ablation_v287_rules_off"]
    for cond, c in res["conditions"].items():
        on_c, off_c = c["hybrid"]["confusion"], off[cond]["confusion"]
        assert on_c["high"]["high"] >= off_c["high"]["high"], cond
        # mild and medium cases raised to emergency must not increase
        assert on_c["low"]["high"] <= off_c["low"]["high"] and on_c["medium"]["high"] <= off_c["medium"]["high"], cond
    tx = res["taxonomy_by_category"]
    assert sum(r["mild_false_alarm"] for r in tx.values()) == 0
    assert res["meta"]["en_test_status"]["inspected_from"] == "V287"


def test_card_and_report_cite_the_frozen_held_out_number_not_the_dev_one():
    card = (ROOT / "SYSTEM_CARD.md").read_text(encoding="utf-8")
    assert "آخر قياس مستقل (V286" in card and "تطوير — فُحصت أخطاؤها" in card
    html = (ROOT / "evaluation" / "results" / "report.html").read_text(encoding="utf-8")
    assert "V286 — مختوم" in html and "نتيجة تطوير" in html and "حسب نوع الخطأ" in html
