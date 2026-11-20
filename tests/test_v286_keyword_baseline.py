"""V286: the keyword comparison baseline is fair (same vocabulary) and reported."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import keyword_baseline as kb  # noqa: E402
import safety_engine  # noqa: E402


def test_vocabulary_file_matches_what_the_engine_treats_as_emergency():
    cached = json.loads(kb.CACHE.read_text(encoding="utf-8"))["phrases"]
    assert cached == kb.build_vocabulary()  # regenerate with: python tools/keyword_baseline.py
    assert len(cached) > 300


def test_every_baseline_phrase_is_an_emergency_for_the_engine_itself():
    for phrase in kb.vocabulary()[::25]:
        lang = "en" if phrase.isascii() else "ar"
        assert safety_engine.evaluate({"symptoms": [phrase]}, lang=lang)["emergency"], phrase


def test_baseline_has_no_negation_handling_by_design():
    assert kb.predict("severe chest pain")[0] == "high"
    assert kb.predict("no severe chest pain")[0] == "high"
    assert kb.predict("عندي زكام خفيف")[0] == "low"


def test_results_contain_the_baseline_for_every_condition():
    res = json.loads((ROOT / "evaluation" / "results" / "results.json").read_text(encoding="utf-8"))
    assert all("keyword" in archs for archs in res["conditions"].values())
    neg = res["conditions"]["negation"]
    false_alarms = lambda m: m["high_specificity"]["n"] - m["high_specificity"]["k"]  # noqa: E731
    assert false_alarms(neg["hybrid"]) <= false_alarms(neg["keyword"])


def test_report_shows_the_comparison():
    html = (ROOT / "evaluation" / "results" / "report.html").read_text(encoding="utf-8")
    assert "أفضل من إيش" in html and "بحث كلمات فقط" in html


def test_v285_held_out_numbers_are_frozen_and_logged():
    frozen = json.loads((ROOT / "evaluation" / "frozen" / "results_V285_last_clean_en_test.json").read_text(encoding="utf-8"))
    assert frozen["meta"]["safety_engine"] == "deterministic-red-flag-v5-concepts"
    assert frozen["conditions"]["en_test"]["hybrid"]["high_sensitivity"]["k"] == 23
    assert "V285" in (ROOT / "evaluation" / "HELDOUT_LOG.md").read_text(encoding="utf-8")
