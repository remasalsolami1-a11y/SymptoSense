"""V253: fixed medical regression cases. A changed triage level must be reviewed by a human."""
import json
from pathlib import Path

import pytest

import medical_regression as mr

SNAP = json.loads((Path(__file__).resolve().parent / "medical_regression_snapshot.json").read_text(encoding="utf-8"))
ORDER = {"monitor": 0, "soon": 1, "today": 2, "emergency": 3}


@pytest.mark.parametrize("cid,syms,ov,must_em", mr.CASES, ids=[c[0] for c in mr.CASES])
def test_case_matches_reviewed_snapshot(cid, syms, ov, must_em):
    got = mr.run_case(syms, ov, "en" if cid.startswith("english_") else "ar")
    assert got == SNAP[cid], "triage changed for %s: %s -> %s (review, then run tools/regression_update.py)" % (cid, SNAP[cid], got)
    if must_em is True:
        assert got["emergency"] and got["level"] == "emergency"
    if must_em is False:
        assert not got["emergency"] and got["level"] in {"monitor", "soon"}


def test_snapshot_covers_every_case_and_no_orphans():
    assert set(SNAP) == {c[0] for c in mr.CASES}


def test_serious_symptoms_are_never_triaged_below_today():
    for cid in ("fainting", "chest_pain_severe", "breathing_difficulty", "breathing_difficulty_4of5", "sudden_weakness_speech", "suicidal_note", "child_high_fever"):
        assert ORDER[SNAP[cid]["level"]] >= ORDER["today"], cid
