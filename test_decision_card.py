"""V253: four-state decision card and uncertainty explanation."""
import source_bundle
from pathlib import Path

import decision_card

ROOT = Path(__file__).resolve().parent


def test_four_states_ar_and_en():
    for lvl in decision_card.LEVELS:
        for lang in ("ar", "en"):
            c = decision_card.build({"triage_level": lvl}, {}, lang)
            assert c["level"] == lvl and c["headline"] and c["action"] and c["window"]


def test_ar_headlines_are_the_four_requested_states():
    heads = {l: decision_card.build({"triage_level": l}, {}, "ar")["headline"] for l in decision_card.LEVELS}
    assert "راقب" in heads["monitor"] and "موعد" in heads["soon"] and "اليوم" in heads["today"] and "طوارئ" in heads["emergency"]


def test_emergency_has_no_would_change_and_flag_forces_emergency():
    c = decision_card.build({"triage_level": "monitor", "emergency": True}, {}, "ar")
    assert c["level"] == "emergency" and c["would_change"] == []


def test_missing_information_listed_and_shrinks_when_provided():
    empty = decision_card.build({"triage_level": "monitor"}, {}, "ar")["uncertainty"]["missing"]
    full = decision_card.build({"triage_level": "monitor"}, {"duration": "3", "severity": "5", "age": "30", "onset": "gradual",
                                                             "conditions": "none", "negative_symptoms": ["fever"]}, "ar")["uncertainty"]["missing"]
    assert len(empty) == 6 and full == []


def test_run_analysis_returns_decision():
    import analysis_core
    r = analysis_core.run_analysis({"symptoms": ["صداع"], "age": "30", "gender": "male", "duration": "2", "severity": "3"}, "ar")
    assert r["decision"]["level"] in decision_card.LEVELS


def test_ui_renders_card_with_escaping_and_views_copy_identical():
    assert (ROOT / "chat_view.py").read_text(encoding="utf-8") == (ROOT / "views" / "chat_view.py").read_text(encoding="utf-8")
    a = source_bundle.chat_view_text()
    assert "ss-decision" in a and "esc(dec.headline" in a and "esc(dec.action" in a
