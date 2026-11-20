"""V288: critical laboratory values, one-sided limits, and the blood-report benchmark."""
import json
import sys
from pathlib import Path

import pytest

import blood_critical
import blood_test

ROOT = Path(__file__).resolve().parents[1]


def _run(text, gender="f", age=35):
    entries, _ = blood_test.parse_blood_text(text)
    results, _notes, dangers, level, _child = blood_test.analyze_blood(entries, gender, age)
    return results, dangers, level


@pytest.mark.parametrize("text, level", [
    ("Potassium 7.1 mmol/L 3.5-5.1", "urgent"),
    ("Potassium 2.2 mmol/L 3.5-5.1", "urgent"),
    ("Sodium 117 mmol/L 135-145", "urgent"),
    ("Glucose 41 mg/dL 70-99", "urgent"),
    ("Fasting Glucose 2.1 mmol/L 3.9-5.5", "urgent"),
    ("Glucose 27.5 mmol/L 3.9-7.8", "urgent"),
    ("Calcium 3.6 mmol/L 2.15-2.55", "urgent"),
    ("Absolute Neutrophil Count 0.3 10^9/L 1.5-7.5", "urgent"),
    ("hs Troponin T 250 ng/L <14", "emergency"),
    ("Potassium 7.3 mmol/L", "urgent"),               # critical even without a printed range
    ("Hemoglobin 4.5 g/dL", "emergency"),             # a missing range no longer silences a danger alert
])
def test_critical_values_are_never_shown_as_routine(text, level):
    _r, dangers, got = _run(text)
    assert got == level and dangers


@pytest.mark.parametrize("text", [
    "Potassium 5.4 mmol/L 3.5-5.1",       # high but not critical
    "Sodium 132 mmol/L 135-145",
    "Glucose 128 mg/dL 70-99",
    "Glucose 2.1",                        # unit cannot be established: never guessed
    "hs Troponin T 9 ng/L <14",
])
def test_non_critical_or_ambiguous_values_raise_no_alarm(text):
    _r, dangers, level = _run(text)
    assert level not in {"urgent", "emergency"} and not dangers


def test_adult_limits_are_not_applied_to_a_known_child():
    _r, dangers, level = _run("Potassium 7.2 mmol/L 3.5-5.1", gender="child", age=8)
    assert level == "see_doctor" and not dangers
    _r, _d, level = _run("Potassium 7.2 mmol/L 3.5-5.1", age=None)  # unknown age: safer side
    assert level == "urgent"


@pytest.mark.parametrize("text, key, status, low, high", [
    ("CRP 180 mg/L <5", "crp", "high", None, 5.0),
    ("CRP 2 mg/L <5", "crp", "normal", None, 5.0),
    ("eGFR 24 mL/min/1.73m2 >60", "egfr", "low", 60.0, None),
    ("LDL 205 mg/dL less than 130", "ldl", "high", None, 130.0),
    ("Triglycerides 140 mg/dL less than 150", "triglycerides", "normal", None, 150.0),
])
def test_one_sided_laboratory_limits_are_read_and_used(text, key, status, low, high):
    results, _d, _l = _run(text)
    r = next(x for x in results if x["key"] == key)
    assert (r["status"], r["low"], r["high"], r["reference_source"]) == (status, low, high, "lab_reference_one_sided")
    assert r["verification_level"] == "lab_range_verified"


def test_arabic_decimal_separator_and_digits():
    results, _d, level = _run("البوتاسيوم ٦٫٩ mmol/L ٣٫٥-٥٫١")
    assert results[0]["raw_value"] == 6.9 and level == "urgent"


def test_absolute_neutrophil_row_is_not_read_as_a_percentage():
    results, _d, _l = _run("Absolute Neutrophil Count 0.3 10^9/L 1.5-7.5")
    assert [r["key"] for r in results] == ["anc"]


def test_critical_row_is_shown_as_urgent_not_needs_confirmation():
    results, _d, _l = _run("Potassium 7.3 mmol/L")
    item = blood_test.describe_results(results, "ar")[0]
    assert item["attention_level"] == "urgent"


def test_unit_inference_only_from_an_unambiguous_range_scale():
    assert blood_critical.canonical("glucose", 2.1, "", 3.9, 5.5) == pytest.approx(37.83, abs=0.01)
    assert blood_critical.canonical("glucose", 2.1, "", None, None) is None
    assert blood_critical.canonical("glucose", 41, "mg/dL") == 41


def test_benchmark_results_recorded_and_improved():
    now = json.loads((ROOT / "evaluation" / "results" / "blood_results.json").read_text(encoding="utf-8"))
    before = json.loads((ROOT / "evaluation" / "results" / "blood_results_v287.json").read_text(encoding="utf-8"))
    assert now["meta"]["reports"] >= 43  # V290 appended B44-B55
    assert now["critical_sensitivity"]["k"] == now["critical_sensitivity"]["n"]
    assert now["false_critical_alarms"]["k"] == 0
    assert now["critical_sensitivity"]["k"] > before["critical_sensitivity"]["k"]


def test_benchmark_matches_current_code():
    sys.path.insert(0, str(ROOT / "tools"))
    import evaluate_blood
    fresh = evaluate_blood.run()
    saved = json.loads((ROOT / "evaluation" / "results" / "blood_results.json").read_text(encoding="utf-8"))
    for k in ("extraction_recall", "status_accuracy", "level_accuracy", "critical_sensitivity", "false_critical_alarms"):
        assert fresh[k]["k"] == saved[k]["k"], k   # regenerate with: python tools/evaluate_blood.py


def test_clinical_packet_lists_critical_limits_for_sign_off():
    packet = (ROOT / "CLINICAL_REVIEW_PACKET_AR.md").read_text(encoding="utf-8")
    assert "القيم الحرجة (V288)" in packet and "potassium" in packet
