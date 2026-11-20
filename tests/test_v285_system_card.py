"""V285: SYSTEM_CARD.md is generated from the measurements and cannot drift from them."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import safety_engine  # noqa: E402
import system_card  # noqa: E402


def test_card_is_up_to_date_with_the_results():
    assert (ROOT / "SYSTEM_CARD.md").read_text(encoding="utf-8") == system_card.build()


def test_results_were_measured_on_the_current_engine():
    meta = json.loads((ROOT / "evaluation" / "results" / "results.json").read_text(encoding="utf-8"))["meta"]
    assert meta["safety_engine"] == safety_engine.ENGINE_VERSION
    assert meta["controlled"]["ai_provider"] == "disabled"


def test_generator_prose_contains_no_hand_typed_results():
    src = (ROOT / "tools" / "system_card.py").read_text(encoding="utf-8")
    body = src.split("def render", 1)[1].split("def build", 1)[0]
    # strip format expressions {...}; what is left is static prose
    static = re.sub(r"\{[^{}]*\}", "", body)
    assert not re.findall(r"\d+(?:\.\d+)?\s?%", static.replace("95%", "")), "percentages must come from results.json"


def test_every_percentage_in_the_card_comes_from_a_measurement():
    res = json.loads((ROOT / "evaluation" / "results" / "results.json").read_text(encoding="utf-8"))
    measured = set()

    def walk(x):
        if isinstance(x, dict):
            if "value" in x and isinstance(x["value"], (int, float)):
                measured.add(f"{100 * x['value']:.1f}")
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(res)
    walk(json.loads((ROOT / "evaluation" / "frozen" / "results_V286_last_clean_en_test.json").read_text(encoding="utf-8")))
    for name in ("blood_results.json", "blood_results_v287.json"):
        walk(json.loads((ROOT / "evaluation" / "results" / name).read_text(encoding="utf-8")))
    ml = json.loads((ROOT / "ml_model.json").read_text(encoding="utf-8"))["meta"]["test_accuracy"]
    measured.add(f"{100 * ml:.2f}")
    card = (ROOT / "SYSTEM_CARD.md").read_text(encoding="utf-8")
    for num in re.findall(r"(\d+\.\d+)%", card):
        assert num in measured, num


def test_card_states_the_key_limitations():
    card = (ROOT / "SYSTEM_CARD.md").read_text(encoding="utf-8")
    for phrase in ("غير مراجَعة طبيًا", "مجموعات تطوير", "not yet clinician-verified", "development", "MODEL_CARD.md"):
        assert phrase in card, phrase
