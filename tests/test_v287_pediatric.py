"""V287: children — real ages, infant fever, breathing distress, dehydration and focal fever."""
import json
from pathlib import Path

import pytest

import analysis_core
import red_flag_concepts as rfc
import safety_engine
import text_context as tc

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "evaluation" / "pediatric_cases.json").read_text(encoding="utf-8"))["cases"]


def test_set_is_complete_and_flagged_for_clinician_review():
    data = json.loads((ROOT / "evaluation" / "pediatric_cases.json").read_text(encoding="utf-8"))
    assert len(CASES) == 30 and all(isinstance(c["age"], int) for c in CASES)
    assert {c["label"] for c in CASES} == {"high", "medium", "low"}
    assert "MUST be reviewed by a clinician" in data["about"]


def test_infant_age_and_temperature_are_read_from_parent_wording():
    assert analysis_core._extract_age_months(None, "My 6-week-old baby") < 3
    assert analysis_core._extract_temperature_c("a temperature of 38.2") == 38.2
    assert analysis_core._extract_age_months(None, "fever for 6 weeks") is None  # a duration, not an age


@pytest.mark.parametrize("text, rule", [
    ("Baby is grunting with each breath and the skin between the ribs sucks in", "concept_respiratory_distress"),
    ("طفلي يتنفس بسرعة وضلوعه تنسحب لداخل مع كل نفس", "concept_respiratory_distress"),
    ("My toddler is floppy and very hard to wake up", "concept_reduced_consciousness"),
    ("No wet nappy for 12 hours, very sleepy and won't drink", "concept_severe_dehydration"),
    ("الرضيع عمره 3 أسابيع ويستفرغ أخضر", "concept_infant_bilious_vomit"),
])
def test_child_red_flags(text, rule):
    assert rule in {r for r, _a, _e in rfc.evaluate(text)}


def test_green_vomit_is_an_emergency_only_for_a_baby():
    assert not rfc.evaluate("I vomited green bile after drinking last night")


@pytest.mark.parametrize("text", [
    "أذنه توجعه وعنده حرارة من يومين",
    "Eating less than half his usual feeds for two days with a mild fever",
    "كحة نباحية بالليل بس يتنفس عادي وهو جالس",
    "بطنه يعوره من ثلاث أيام ويستفرغ مرة باليوم",
    "Burning urination with fever and pain in the side or back.",
])
def test_focal_fever_feeding_croup_and_lasting_pain_need_a_doctor_soon(text):
    sig = tc.triage_signal(text, "en" if text.isascii() else "ar")
    assert sig and sig[0] == "soon"


@pytest.mark.parametrize("text", [
    "ولدي عنده زكام وسيلان وهو يلعب عادي",
    "Teething, temperature 37.8, playing and feeding normally",
    "Bumped his head on the table, cried straight away, now playing normally",
    "حبوب حمراء خفيفة تختفي لما أضغط عليها وما فيه حرارة",
    "Baby has a blocked nose but feeds well and has plenty of wet nappies",
    "Mild fever, no rash and no ear pain",
])
def test_mild_child_cases_stay_low(text):
    assert tc.triage_signal(text, "en" if text.isascii() else "ar") is None
    assert not safety_engine.evaluate({"symptoms": [text]}, lang="en" if text.isascii() else "ar")["emergency"]


def test_pediatric_results_are_reported_with_age_per_case():
    res = json.loads((ROOT / "evaluation" / "results" / "results.json").read_text(encoding="utf-8"))
    ped = res["conditions"]["pediatric"]["hybrid"]
    assert ped["n"] == 30 and ped["confusion"]["low"]["high"] == 0
