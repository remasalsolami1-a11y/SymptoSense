"""V286: duration / severity / worsening / impact read from free text — raise-only, capped, explained."""
import json
from pathlib import Path

import pytest

import analysis_core
import text_context as tc

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("text, days", [
    ("لي أربعة أيام والحرارة ما نزلت", 4),
    ("عندي كحة من أكثر من ثلاث أسابيع", 21.5),
    ("بطني يعورني من كم يوم", 3),
    ("صار يجيني صداع هالأسابيع", 14),
    ("حلقي يحكني من يومين", 2),
    ("Fever lasting four days", 4),
    ("Cough lasting more than three weeks", 21.5),
    ("New ankle swelling persisting for a week", 7),
    ("hiccups lasting a few minutes", 3 / 1440),
])
def test_duration_is_read_from_arabic_and_english(text, days):
    d = tc.extract(text)["duration"]
    assert d and abs(d["days"] - days) < 1e-6 and d["quote"] in text


@pytest.mark.parametrize("text, level", [
    ("لي أربعة أيام والحرارة ما نزلت وتعبي يزيد.", "soon"),
    ("حلقي ملتهب وعندي حرارة من كم يوم وما أقدر أبلع الأكل.", "soon"),
    ("بطني يعورني من كم يوم وما لي نفس آكل.", "soon"),
    ("Knee pain and swelling after a minor injury, still unable to bear weight normally the next day.", "soon"),
    ("Severe back pain since this morning", "today"),
])
def test_signals_raise_to_soon_or_today(text, level):
    sig = tc.triage_signal(text, "en" if text.isascii() else "ar")
    assert sig and sig[0] == level


@pytest.mark.parametrize("text", [
    "خشمي يسيل شوي وأعطس من أمس، ما فيني حرارة ونفسي عادي.",
    "بطني منفوخ شوي بعد ما أكلت كثير وقاعد يخف.",
    "عندي حبة صغيرة في فمي من يومين وآكل وأشرب عادي.",
    "Constipation for two days without severe pain, vomiting, or bleeding.",
    "Mild sore throat for one day with normal breathing and swallowing.",
    "Cough without severe breathing difficulty",
    "الألم مو قاعد يزيد",
])
def test_mild_improving_or_denied_text_gives_no_signal(text):
    assert tc.triage_signal(text, "en" if text.isascii() else "ar") is None


def test_text_never_produces_an_emergency_and_never_lowers():
    for text in ("ألم شديد جدًا ما يتحمل من أسبوع ويزيد", "Unbearable severe pain for months, getting worse"):
        assert tc.triage_signal(text)[0] in ("soon", "today")
        tri = analysis_core._triage({"symptoms": [text], "severity": 2, "age": 35}, "ar")
        assert tri["level"] != "emergency"
    # an explicitly selected higher severity is not lowered by mild words
    tri = analysis_core._triage({"symptoms": ["صداع خفيف"], "severity": 4, "age": 35}, "ar")
    assert tri["level"] == "today"


def test_reason_quotes_the_users_words():
    tri = analysis_core._triage({"symptoms": ["حلقي ملتهب وعندي حرارة من كم يوم"], "severity": 2, "age": 35}, "ar")
    assert tri["level"] == "soon" and "«من كم يوم»" in tri["reason"]


def test_switch_turns_the_layer_off():
    tc.ENABLED = False
    try:
        assert tc.triage_signal("لي أربعة أيام والحرارة ما نزلت") is None
    finally:
        tc.ENABLED = True


def test_results_show_gain_without_new_false_alarms_on_mild_cases():
    res = json.loads((ROOT / "evaluation" / "results" / "results.json").read_text(encoding="utf-8"))
    off = res["ablation_text_context_off"]
    for cond in ("en_dev", "en_test", "ar_msa", "ar_dialect"):
        on_c, off_c = res["conditions"][cond]["hybrid"]["confusion"], off[cond]["confusion"]
        assert on_c["medium"]["medium"] > off_c["medium"]["medium"], cond
        assert on_c["low"]["low"] == off_c["low"]["low"], cond          # success criterion: no new over-triage of mild cases
        assert on_c["high"]["high"] == off_c["high"]["high"], cond      # emergencies unchanged
