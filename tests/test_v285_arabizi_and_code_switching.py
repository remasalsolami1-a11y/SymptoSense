"""V285: Arabizi transliteration, code-switching evaluation, regional breakdown, sealed external set."""
import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import arabizi  # noqa: E402
import red_flag_concepts as rfc  # noqa: E402


def _rules(text):
    return {r for r, _a, _e in rfc.evaluate(text)}


@pytest.mark.parametrize("text, rule", [
    ("9dri y3awrni wayed w a3ra8", "concept_cardiac_chest"),
    ("shfayfi ntf5at w nfsi 9ayg", "concept_anaphylaxis"),
    ("fj2a wjhi mal w ma a8dr arfa3 ydi", "concept_stroke_fast"),
    ("al rabo 3ndi gwi w a5dt al b5a5 w ma t7snt", "concept_severe_asthma"),
])
def test_arabizi_red_flags_are_recognised(text, rule):
    assert rule in _rules(text)


def test_explanations_quote_the_original_arabizi_words():
    ev = rfc.explain("shfayfi ntf5at w nfsi 9ayg")[0]["evidence"]
    text = "shfayfi ntf5at w nfsi 9ayg"
    quotes = [q for e in ev for q in e["quotes"]]
    assert [q["text"] for q in quotes] == ["shfayfi ntf5at", "nfsi 9ayg"]
    assert all(text[q["start"]:q["end"]] == q["text"] for q in quotes)


@pytest.mark.parametrize("text", [
    "I have chest pain 3x a day and took 5mg",
    "COVID-19 test was negative, 2nd day of cough",
    "My head hurts after the 3rd shift",
    "Pain in my knee 24h after running",
])
def test_english_text_is_never_transliterated(text):
    assert arabizi.to_arabic(text) == text and arabizi.convert_tokens(text) == []


def test_arabizi_negation_is_kept():
    assert "concept_anaphylaxis" not in _rules("ma 3ndi tawarum w nfsi mu 9ayg")
    assert arabizi.to_arabic("ma a8dr") == "ما اقدر"


def test_ablation_switch_turns_the_layer_off():
    arabizi.ENABLED = False
    rfc.matched_concepts.cache_clear()
    try:
        assert _rules("9dri y3awrni wayed w a3ra8") == set()
    finally:
        arabizi.ENABLED = True
        rfc.matched_concepts.cache_clear()
    assert _rules("9dri y3awrni wayed w a3ra8") == {"concept_cardiac_chest"}


def test_code_switching_set_is_complete_and_tagged():
    data = json.loads((ROOT / "evaluation" / "code_switching_cases.json").read_text(encoding="utf-8"))
    cases = data["cases"]
    assert len(cases) == 32 and len({c["id"] for c in cases}) == 32
    assert {c["form"] for c in cases} == {"code_switch", "arabizi"}
    assert {c["region"] for c in cases} >= {"najdi", "hejazi", "gulf", "southern"}
    assert {c["label"] for c in cases} == {"high", "medium", "low"}
    assert "DEVELOPMENT" in data["about"]  # never presented as a held-out estimate


def test_results_include_regions_and_arabizi_ablation_without_changing_older_sets():
    res = json.loads((ROOT / "evaluation" / "results" / "results.json").read_text(encoding="utf-8"))
    assert {"ar_code_switch", "ar_arabizi"} <= set(res["conditions"])
    assert set(res["regions"]) >= {"najdi", "hejazi", "gulf", "southern"}
    on = res["conditions"]["ar_arabizi"]["hybrid"]["high_sensitivity"]
    off = res["ablation_arabizi_off"]["ar_arabizi"]["high_sensitivity"]
    assert on["k"] > off["k"]


def test_doctor_packet_keeps_existing_ids_and_appends_new_cases():
    import doctor_review_packet as drp

    with (ROOT / "evaluation" / "doctor_review_key.csv").open(encoding="utf-8") as fh:
        committed = {r["review_id"]: r["case_id"] for r in csv.DictReader(fh)}
    key = drp.key()
    assert key == committed
    v284 = {k: v for k, v in key.items() if int(k[1:]) <= 220}
    assert all(not v.startswith(("CS", "AZ")) for v in v284.values())
    assert sorted(v for k, v in key.items() if 220 < int(k[1:]) <= 252) == sorted(
        [f"CS{i:02d}" for i in range(1, 25)] + [f"AZ{i:02d}" for i in range(1, 9)])
    assert all(v.startswith(("TX", "TN", "P", "MC", "VD")) for k, v in key.items() if int(k[1:]) > 252)  # V287+ cases appended after


def test_external_heldout_is_loaded_and_sealed(tmp_path, monkeypatch):
    import shutil

    import evaluate_engine as ev

    for name in ("arabic_cases.json", "external_heldout_labels.csv"):
        shutil.copy(ROOT / "evaluation" / name, tmp_path / name)
    monkeypatch.setattr(ev, "EVAL_DIR", tmp_path)
    assert ev.load_external() == [] and ev.external_seal() is None
    with (tmp_path / "external_heldout.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["writer_id", "region", "form", "scenario_id", "text"])
        w.writerow(["W01", "najdi", "dialect", "X01", "أبوي فجأة يده ثقيلة ما يقدر يرفعها وفمه مايل"])
        w.writerow(["W02", "hejazi", "code_switch", "X19", "عندي runny nose من أمس"])
        w.writerow(["W02", "hejazi", "dialect", "X99", "unknown scenario is ignored"])
    rows = ev.load_external()
    assert [r["expected"] for r in rows] == ["high", "low"]
    seal = ev.external_seal()
    assert seal["n"] == 2 and seal["writers"] == 2 and len(seal["sha256"]) == 64
    assert "ar_external" in ev.load_cases()


def test_scenario_cards_and_labels_match():
    with (ROOT / "evaluation" / "external_heldout_scenarios.csv").open(encoding="utf-8-sig") as fh:
        cards = {r["scenario_id"] for r in csv.DictReader(fh)}
    with (ROOT / "evaluation" / "external_heldout_labels.csv").open(encoding="utf-8") as fh:
        labels = {r["scenario_id"]: r["label"] for r in csv.DictReader(fh)}
    assert cards == set(labels) and len(cards) == 24
    assert set(labels.values()) == {"high", "medium", "low"}
