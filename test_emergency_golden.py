"""Golden emergency set: dialect wording, typos and free phrasing.

Every positive case must trigger the deterministic safety engine (the last line
of defence before symptom matching); every negative control must not.
`set == "free"` rows are free-phrasing sentences kept separate so regressions
in natural speech are reported on their own.
"""
import json
from pathlib import Path

import pytest

import analysis_core
import safety_engine

CASES = json.loads((Path(__file__).parent / "runtime_data/emergency_golden.json").read_text(encoding="utf-8"))
GOLDEN = [c for c in CASES if c["set"] == "golden"]
FREE = [c for c in CASES if c["set"] == "free"]


def _emergency(text, *, as_symptom=False):
    patient = {"symptoms": [text] if as_symptom else [], "notes": "" if as_symptom else text, "severity": 3}
    return safety_engine.evaluate(patient, "ar")["emergency"] or bool(analysis_core.detect_red_flags(patient["symptoms"], patient["notes"], "ar"))


@pytest.mark.parametrize("case", GOLDEN, ids=lambda c: c["id"])
def test_golden_cases_in_notes(case):
    assert _emergency(case["text"]) is case["expect_emergency"], case["text"]


@pytest.mark.parametrize("case", FREE, ids=lambda c: c["id"])
def test_free_phrasing_cases(case):
    assert _emergency(case["text"]) is case["expect_emergency"], case["text"]


@pytest.mark.parametrize("case", [c for c in CASES if c["expect_emergency"]], ids=lambda c: c["id"])
def test_positive_cases_also_work_as_typed_symptom(case):
    assert _emergency(case["text"], as_symptom=True), case["text"]


def test_golden_set_size_and_coverage():
    positives = [c for c in CASES if c["expect_emergency"]]
    assert len(positives) >= 180 and len(CASES) - len(positives) >= 30
    assert {"gulf", "hejazi", "egy", "msa", "typo", "free"} <= {c["dialect"] for c in CASES}
    assert {"chest", "breath", "stroke", "uncon", "seizure", "bleed", "preg", "allergy", "selfharm", "poison", "infant", "appendix", "pregnancy", "dvt"} <= {c["category"] for c in CASES}
