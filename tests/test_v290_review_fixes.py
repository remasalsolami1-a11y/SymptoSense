"""V290: fixes from the sealed fresh-probe review — missing emergency types, past history,
meaning-safe typo correction, blood name-numbers, INR/lactate, unrecognised tests — and the
blood advice cards with their safety rules."""
import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import arabic_lexicon  # noqa: E402
import blood_advice  # noqa: E402
import blood_critical  # noqa: E402
import blood_test  # noqa: E402
import red_flag_concepts as rfc  # noqa: E402
import safety_engine  # noqa: E402
import temporal_context  # noqa: E402
import text_context  # noqa: E402


def _rules(text):
    return {r for r, _a, _e in rfc.evaluate(text)}


# ------------------------------------------------------------------ sealed probe set
def test_sealed_probe_file_is_unchanged_and_logged():
    raw = (ROOT / "evaluation" / "fresh_probe_sealed.json").read_bytes()
    import evaluate_fresh_probe
    assert hashlib.sha256(raw).hexdigest() == evaluate_fresh_probe.SEALED_SHA256
    assert evaluate_fresh_probe.SEALED_SHA256 in (ROOT / "evaluation" / "HELDOUT_LOG.md").read_text(encoding="utf-8")
    data = json.loads(raw)
    assert len(data["symptoms"]) == 35 and len(data["blood"]) == 23
    assert "not a blind held-out" in data["about"]


def test_probe_results_recorded_and_improved():
    res = json.loads((ROOT / "evaluation" / "results" / "fresh_probe_results.json").read_text(encoding="utf-8"))
    assert res["meta"]["sealed_sha256_ok"]
    b = res["baseline_v289"]
    assert res["symptoms"]["correct"] > b["symptoms_n"] - b["symptoms_wrong"]
    assert res["blood"]["correct"] > b["blood_n"] - b["blood_wrong"]


# ------------------------------------------------------------------ new emergency types
@pytest.mark.parametrize("text, rule", [
    ("بنتي غصّت بقطعة لحم وما تقدر تتنفس", "concept_choking"),
    ("He has a grape stuck in his throat and cannot breathe", "concept_choking"),
    ("My son swallowed two magnets from a toy", "concept_dangerous_ingestion"),
    ("طفلي شرب من علبة المبيض", "concept_dangerous_ingestion"),
    ("She swallowed a handful of sleeping tablets", "concept_overdose"),
    ("أمي أخذت علبة بنادول كاملة", "concept_overdose"),
    ("Chemical burn on my face from oven cleaner", "concept_serious_burn"),
    ("انكب علي ماي حار وصدري كله فيه فقاعات", "concept_serious_burn"),
    ("After the fall her wrist is bent at an odd angle", "concept_fracture_deformity"),
    ("ابني طاح من الدرج ويده معوجة بشكل غريب", "concept_fracture_deformity"),
    ("Feels like a heavy weight crushing my chest", "concept_chest_crushing"),
    ("صدري كأن عليه حجر ثقيل", "concept_chest_crushing"),
    ("ولدي ما يقدر يتنفس", "concept_cannot_breathe"),
    ("أمي فجأة ما تقدر تمسك الملعقة", "concept_stroke_fast"),
    ("Temperature of 39 with a terrible headache and I can't bend my neck forward", "concept_meningitis"),
])
def test_new_emergency_types(text, rule):
    assert rule in _rules(text)


@pytest.mark.parametrize("text", [
    "شرقت بالموية شوي وكحيت وراحت", "I swallowed a cherry stone by mistake, feel fine", "عندي حبوب كثير في وجهي",
    "I took two paracetamol tablets for a headache", "I took my pills and drank lots of water", "I took all my pills today as usual",
    "Small burn on my finger from the pan, red and sore", "My whole body burns with fever", "Twisted my ankle a little, can walk fine",
    "My grandma fell but got up by herself and is fine", "Mild chest soreness when I press on the muscle after the gym",
    "Stiff neck from sleeping badly, no fever", "I ate a lot of chocolate",
])
def test_look_alikes_stay_out_of_the_new_rules(text):
    assert not (_rules(text) & rfc.V290_RULES)


def test_v290_rules_can_be_switched_off_for_the_ablation():
    rfc.V290_ENABLED = False
    rfc.matched_concepts.cache_clear()
    try:
        assert "concept_overdose" not in _rules("She swallowed a handful of sleeping tablets")
    finally:
        rfc.V290_ENABLED = True
        rfc.matched_concepts.cache_clear()
    assert "concept_overdose" in _rules("She swallowed a handful of sleeping tablets")


def test_every_new_rule_has_an_explanation_and_labels():
    import emergency_explain
    for rid in rfc.V290_RULES:
        assert rid in emergency_explain._WHY and rid in rfc._RULE_CONCEPTS
        assert all(c in rfc.CONCEPT_LABELS for c in rfc._RULE_CONCEPTS[rid])


# ------------------------------------------------------------------ past history
@pytest.mark.parametrize("text, removed", [
    ("I had a seizure as a child, now I just have a headache from screens", "I had a seizure as a child"),
    ("وانا صغيرة جاتني تشنجات، الحين بس عندي زكام", "وانا صغيرة جاتني تشنجات"),
    ("قبل سنتين سويت عملية في القلب وكانت ناجحة، اليوم عندي كحة خفيفة", "قبل سنتين سويت عملية في القلب وكانت ناجحة"),
])
def test_finished_past_events_are_not_current_symptoms(text, removed):
    assert temporal_context.past_clauses(text) == [removed]
    assert not safety_engine.evaluate({"symptoms": [text]}, lang="en" if text.isascii() else "ar")["emergency"]


@pytest.mark.parametrize("text", [
    "I had a seizure as a child and today he had a seizure that lasted ten minutes",
    "History of heart disease and crushing chest pain right now",
    "since last year I get chest pain, it is bad",
    "I had a stroke years ago and I have weakness in my arm, also cough",
    "Seizure as a child",  # one clause only: never removed
])
def test_present_or_ongoing_wording_is_always_kept(text):
    assert temporal_context.past_clauses(text) == []


def test_old_event_is_dropped_but_the_current_emergency_stays():
    text = "كان عندي جلطة قبل سنة، والحين ألم شديد في صدري ينتشر لذراعي"
    assert temporal_context.past_clauses(text) == ["كان عندي جلطة قبل سنة"]
    assert safety_engine.evaluate({"symptoms": [text]}, lang="ar")["emergency"]


def test_past_history_layer_can_be_switched_off():
    temporal_context.ENABLED = False
    try:
        assert temporal_context.current_text("I had a seizure as a child, now a cold") == "I had a seizure as a child, now a cold"
    finally:
        temporal_context.ENABLED = True


# ------------------------------------------------------------------ typo correction keeps real words
@pytest.mark.parametrize("word, wrong", [("الصغير", "الصفير"), ("يوميه", "يغميه"), ("يربط", "يخربط"), ("الطفوله", "الفوله"),
                                         ("الكلب", "القلب")])
def test_real_words_are_never_corrected_into_concept_words(word, wrong):
    assert arabic_lexicon.is_real_word(word)
    assert rfc.correct_typos(word) == word != wrong


def test_real_typos_are_still_corrected():
    assert rfc.correct_typos("انتفت") == "انتفخت" and rfc.correct_typos("شفيفي") != "شفيفي"


def test_lexicon_never_contains_demo_typos():
    words = arabic_lexicon.words()
    assert len(words) > 5000 and "شفيفي" not in words and "انتفت" not in words


# ------------------------------------------------------------------ medium additions
@pytest.mark.parametrize("text", ["دمل في فخذي منتفخ وفيه قيح", "Toothache for three days and my gum is swollen",
                                  "Loose stools for four days now", "It stings when I urinate since this morning",
                                  "كاحلي متورم وأعرج من ثلاث أيام بعد ما التوى"])
def test_see_a_doctor_soon_additions(text):
    assert text_context.triage_signal(text, "en" if text.isascii() else "ar")[0] == "soon"


def test_items_in_a_negated_list_are_negated():
    assert text_context.triage_signal("Mild dandruff and scalp flaking without pain, pus, or hair loss patches.", "en") is None


# ------------------------------------------------------------------ blood parsing
@pytest.mark.parametrize("text, value", [
    ("Vitamin D (25-OH) 18 ng/mL 30-100", 18), ("25(OH)D 62 nmol/L 75-250", 62), ("فيتامين د ٢٥ هيدروكسي 18 نانوغرام/مل 30-100", 18),
    ("Vitamin D 25-OH: 22 ng/mL (30-100)", 22), ("25-hydroxyvitamin D 45 nmol/L 50-125", 45),
])
def test_numbers_inside_test_names_are_not_results(text, value):
    entries, _ = blood_test.parse_blood_text(text)
    assert [(e["key"], e["value"]) for e in entries] == [("vitd", value)]


def test_inr_and_lactate_are_read_and_judged():
    for text, key, level in (("INR 4.8 0.8-1.2", "inr", "urgent"), ("PT/INR 2.6 0.8-1.2", "inr", "see_doctor"),
                             ("Lactate 4.5 mmol/L 0.5-2.2", "lactate", "urgent"), ("Lactic acid 40 mg/dL 4.5-19.8", "lactate", "urgent"),
                             ("Lactate 1.6 mmol/L 0.5-2.2", "lactate", "normal")):
        entries, _ = blood_test.parse_blood_text(text)
        results, _n, _d, lvl, _c = blood_test.analyze_blood(entries, "m", 50)
        assert [r["key"] for r in results] == [key] and lvl == level, text
    assert blood_critical.check({"key": "inr", "value": 4.0}, {"unit": ""})[0] == "urgent"
    assert blood_critical.check({"key": "inr", "value": 3.9}, {"unit": ""}) is None


def test_unrecognised_tests_are_kept_not_dropped():
    text = "Hemoglobin 13.1 g/dL 12-15.5\nProcalcitonin 2.1 ng/mL 0-0.5\nFasting 10 hours\nAge 40\nDate 12/10/2026"
    entries, _ = blood_test.parse_blood_text(text)
    names = [e.get("name") for e in entries if str(e["key"]).startswith("other_")]
    assert names == ["Procalcitonin"]
    results, _n, _d, level, _c = blood_test.analyze_blood(entries, "f", 40)
    assert level == "see_doctor"


def test_blood_benchmark_still_perfect_with_new_reports():
    res = json.loads((ROOT / "evaluation" / "results" / "blood_results.json").read_text(encoding="utf-8"))
    assert res["meta"]["reports"] == 55
    assert res["critical_sensitivity"]["k"] == res["critical_sensitivity"]["n"] and res["false_critical_alarms"]["k"] == 0


# ------------------------------------------------------------------ advice cards
def _all_text(card):
    parts = [card.get("title", ""), card.get("message", ""), card.get("retest", ""), card.get("pattern", "")]
    for k in ("foods", "helps", "blocks", "dont", "ask_first"):
        parts += card.get(k) or []
    return " ".join(parts)


_DOSE = re.compile(r"\d+(?:[.,]\d+)?\s*(?:mg|mcg|µg|μg|ug|iu|units?|ملغ|مغ|ملجم|ميكروغرام|ميكروجرام|وحدة|وحده|وحدات|حبة|حبتين|tablets?|capsules?)\b", re.I)
_GENDERED = re.compile(r"ركّزي|ركزي|راجعي|تبدئي|تتناولي|تجنبي|حافظي|تحاولي|اتبعي|لا تحاول|(?<!ال)تواصل مع|ناقش |اسأل |راجع الطبيب")


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_cards_never_contain_doses_and_always_cite_sources(lang):
    for name, card in blood_advice.all_cards_for_review(lang):
        text = _all_text(card)
        assert not _DOSE.search(text), (name, _DOSE.search(text).group(0))
        if card["kind"] == "advice":
            assert len(card["sources"]) >= 1 and all(s["url"].startswith("https://") for s in card["sources"])
            assert card["dont"] and card["ask_first"] and card["retest"]
            assert card["reviewed_by_clinician"] is False


def test_arabic_cards_are_gender_neutral():
    for name, card in blood_advice.all_cards_for_review("ar"):
        assert not _GENDERED.search(_all_text(card)), (name, _GENDERED.search(_all_text(card)).group(0))
    for key in ("hgb", "ferritin", "vitd", "glucose"):
        for st in ("low", "high", "normal"):
            assert not _GENDERED.search(blood_test.focus_guidance(key, st, "ar"))


def _cards(text, age=35, notes="", meds="", lang="ar", gender="f"):
    entries, _ = blood_test.parse_blood_text(text)
    results, _n, _d, _l, _c = blood_test.analyze_blood(entries, gender, age)
    ind = blood_test.describe_results(results, lang)
    blood_advice.attach(ind, results, age=age, context={"notes": notes}, medications=meds, lang=lang)
    return {i["key"]: i.get("advice") for i in ind}


def test_no_food_advice_for_critical_values_electrolytes_and_counts():
    cards = _cards("Potassium 6.4 mmol/L 3.5-5.1\nSodium 133 mmol/L 136-145\nPlatelets 120 10^9/L 150-400\nINR 4.5 0.8-1.2")
    assert cards["potassium"]["kind"] == "critical" and cards["inr"]["kind"] == "critical"
    assert cards["sodium"]["kind"] == "doctor_only" and cards["plt"]["kind"] == "doctor_only"
    assert all("foods" not in c for c in cards.values())


def test_anaemia_advice_follows_the_pattern():
    with_ferritin = _cards("Hemoglobin 10.9 g/dL 12-15.5\nFerritin 8 ng/mL 15-150")
    assert with_ferritin["ferritin"]["kind"] == "advice" and with_ferritin["hgb"]["kind"] == "pattern"
    alone = _cards("Hemoglobin 10.9 g/dL 12-15.5")
    assert alone["hgb"]["kind"] == "cause_first" and "الفيريتين" in alone["hgb"]["message"]


def test_context_changes_the_card():
    normal = _cards("Ferritin 8 ng/mL 15-150")["ferritin"]
    pregnant = _cards("Ferritin 8 ng/mL 15-150", notes="أنا حامل")["ferritin"]
    assert "الكبدة" in normal["foods"] and "الكبدة" not in pregnant["foods"]
    assert _cards("Ferritin 8 ng/mL 15-150", age=9)["ferritin"]["kind"] == "child"
    veg = _cards("Vitamin B12 150 pg/mL 200-900", notes="نباتي")["b12"]
    assert any("للنباتيين" in x for x in veg["helps"])
    met = _cards("Vitamin B12 150 pg/mL 200-900", meds="Metformin 500")["b12"]
    assert any("الميتفورمين" in x for x in met["ask_first"])


def test_english_cards_are_complete():
    cards = _cards("Ferritin 8 ng/mL 15-150\nVitamin D 18 ng/mL 30-100\nLDL 170 mg/dL < 130", lang="en")
    assert cards["ferritin"]["title"] == "How to raise iron stores"
    assert cards["vitd"]["foods"] and cards["ldl"]["blocks"]
    assert not re.search(r"[؀-ۿ]", json.dumps(cards, ensure_ascii=False))


def test_normal_values_get_no_card():
    assert _cards("Ferritin 80 ng/mL 15-150")["ferritin"] is None


def test_cards_are_in_the_api_and_the_page():
    labs = (ROOT / "routes" / "labs.py").read_text(encoding="utf-8")
    assert "blood_advice.attach(indicators, results" in labs
    page = (ROOT / "pagelib" / "pages_html.py").read_text(encoding="utf-8")
    assert "function labxAdviceHtml(a)" in page and "if(i.advice)h+=labxAdviceHtml(i.advice)" in page


def test_cards_are_in_the_clinical_review_packet():
    text = (ROOT / "CLINICAL_REVIEW_PACKET_AR.md").read_text(encoding="utf-8")
    assert "بطاقات «كيف أعدّلها؟» (V290)" in text and "iron_pregnant" in text
