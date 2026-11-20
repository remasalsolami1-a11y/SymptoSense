"""V289: improving stroke signs, typo'd emergencies, typo/Arabizi durations, 'see a doctor soon'
combinations, AI-reply guard, and the end-to-end API measurement."""
import json
from pathlib import Path

import pytest

import answer_guard
import red_flag_concepts as rfc
import safety_engine
import text_context as tc

ROOT = Path(__file__).resolve().parents[1]
COMBO = json.loads((ROOT / "evaluation" / "medium_combo_cases.json").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("text", [
    "ميلان مفاجئ في الوجه مع ضعف في الذراع حتى لو بدأت الأعراض تتحسن.",   # a TIA is still an emergency
    "بعد ما اكلت انتفت شفايفي ولساني بسرعه وصار نفسي ضيق.",               # انتفت -> انتفخت
    "فجاه صار عندي ضعف وتنميل بجهه وحده من جسمي وكامي صار ثقيل.",
])
def test_emergencies_with_improvement_words_or_typos(text):
    assert safety_engine.evaluate({"symptoms": [text]}, lang="ar")["emergency"]


def test_typo_correction_does_not_change_words_it_already_knows():
    assert "concept_stroke_fast" in {r for r, _a, _e in rfc.evaluate("وجهي مايل فجأة")}   # مايل used to become مايلك
    assert not safety_engine.evaluate({"symptoms": ["وجهي مايل في الصورة من زمان"]}, lang="ar")["emergency"]  # longstanding


@pytest.mark.parametrize("text, days", [
    ("عندي كحه من اكثر من ثلاث اسابع", 21.5),
    ("نزل وزني كثير هالاابيع", 14),
    ("تعبان من اابيع.", 7),
    ("7rara mn thlath ayam w k7a", 3),
    ("Anxiety most days for months", 60),
    ("migraines more frequent over the last month", 30),
])
def test_durations_survive_typos_arabizi_and_bare_units(text, days):
    assert tc.extract(text)["duration"]["days"] == pytest.approx(days)


def test_typo_fix_never_turns_ordinary_words_into_numbers():
    assert tc._prepare("واحس بدوخه") == "واحس بدوخه"


@pytest.mark.parametrize("case", COMBO, ids=lambda c: c["id"])
def test_see_a_doctor_soon_combinations_and_look_alikes(case):
    sig = tc.triage_signal(case["text"], case["lang"])
    assert (sig is not None and sig[0] == "soon") == (case["label"] == "medium"), case["text"]


def test_negated_self_harm_risk_is_not_an_emergency():
    text = "Low mood, loss of interest, and sleep difficulty lasting several weeks without immediate self-harm risk."
    assert not safety_engine.evaluate({"symptoms": [text]}, lang="en")["emergency"]


@pytest.mark.parametrize("reply, user, lang", [
    ("هذا غالبًا شيء بسيط ولا داعي لزيارة الطبيب.", "يحرقني وقت التبول وأروح الحمام كل شوي", "ar"),
    ("Nothing to worry about, just rest.", "Fever lasting four days", "en"),
    ("You don't need a doctor for this.", "Painful red eye and bright light hurts it", "en"),
])
def test_ai_reply_guard_removes_reassurance_and_adds_doctor_advice(reply, user, lang):
    out, changed = answer_guard.guard(reply, user, lang)
    assert changed and not answer_guard._DISMISSIVE.search(out) and answer_guard._ADVISES_DOCTOR.search(out)


def test_ai_reply_guard_leaves_mild_cases_alone():
    assert answer_guard.guard("Rest and fluids help a cold.", "mild runny nose since yesterday", "en") == ("Rest and fluids help a cold.", False)


def test_assistant_route_guards_every_model_reply():
    # Checked through the live route manually (a mocked model reply "Nothing to worry about ..." came back
    # without that sentence and with "please see a doctor"). Here: the guard sits on the model's return path.
    src = (ROOT / "routes" / "assistant.py").read_text(encoding="utf-8")
    ai_path = src.split("r = _groq_chat_completion_with_retry(", 1)[1].split('@route("/api/assistant/feedback"', 1)[0]
    final_return = ai_path.split("return jsonify", 1)[0]
    assert "answer_guard.guard(answer, last_text, lang)" in final_return and 'if mode != "mh"' in final_return


def test_results_recorded():
    res = json.loads((ROOT / "evaluation" / "results" / "results.json").read_text(encoding="utf-8"))
    off = res["ablation_combos_off"]
    for cond in ("en_dev", "en_test", "ar_msa", "ar_dialect", "ar_dialect_typos", "medium_combo"):
        assert res["conditions"][cond]["hybrid"]["confusion"]["low"] == off[cond]["confusion"]["low"], cond  # no new over-triage
    e2e = json.loads((ROOT / "evaluation" / "results" / "e2e_results.json").read_text(encoding="utf-8"))
    assert e2e["api_engine_agreement"]["k"] == e2e["api_engine_agreement"]["n"] > 400
    assert e2e["ai_guard"]["k"] == e2e["ai_guard"]["n"] > 0
