"""V285: "Why this result?" — every emergency reason quotes the user's own words, faithfully."""
import json
from pathlib import Path

import pytest

import clinical_text
import emergency_explain
import red_flag_concepts as rfc
import research_study
import safety_engine

ROOT = Path(__file__).resolve().parents[1]

CASES = [
    ("ولدي انضرب على راسه وبعدها صار يستفرغ أكثر من مرة ونعسان مرة.", "ar"),
    ("chest pain قوي وأعرق", "ar"),
    ("ما عندي ألم صدر بس انتفخت شفيفي وصار نفسي ضيق", "ar"),
    ("Black tarry stool with faintness.", "en"),
    ("حرارتي عالية ورقبتي متيبسة وراسي يعورني مرة.", "ar"),
    ("الربو عندي قوي وأخذت البخاخ وما تحسنت.", "ar"),
    ("فجأة فمي مال وما أقدر أرفع يدي.", "ar"),
]


@pytest.mark.parametrize("text, lang", CASES)
def test_every_quote_is_an_exact_unnegated_slice_of_the_input(text, lang):
    items = rfc.explain(text)
    assert items, "an emergency concept rule should fire"
    fired = {r for r, _a, _e in rfc.evaluate(text)}
    assert {i["rule_id"] for i in items} == fired  # explanation covers exactly the decision
    norm = clinical_text.normalize_clinical_text
    for item in items:
        assert item["evidence"], item["rule_id"]
        for ev in item["evidence"]:
            assert ev["concept"] in rfc._RULE_CONCEPTS[item["rule_id"]]
            for q in ev["quotes"]:
                assert text[q["start"]:q["end"]] == q["text"] and q["text"].strip()
                # the quoted words are not themselves preceded by a negator in the input
                before = norm(text[:q["start"]]).split()
                assert not (before and before[-1] in {"ما", "لا", "مو", "مب", "no", "not", "without"}), q


def test_negated_symptoms_are_never_quoted():
    items = rfc.explain("ما عندي ألم صدر بس انتفخت شفيفي وصار نفسي ضيق")
    quoted = " ".join(q["text"] for i in items for e in i["evidence"] for q in e["quotes"])
    assert "صدر" not in quoted and "شفيفي" in quoted and {i["rule_id"] for i in items} == {"concept_anaphylaxis"}


def test_overlapping_quotes_are_merged():
    ev = rfc.explain("Black tarry stool with faintness.")[0]["evidence"]
    assert [q["text"] for e in ev for q in e["quotes"]] == ["Black tarry stool", "faintness"]


def test_every_rule_has_concepts_labels_and_a_specific_reason():
    for rid, _ar, _en, _rule in rfc.RULES:
        assert rid in rfc._RULE_CONCEPTS
        assert all(c in rfc.CONCEPTS and c in rfc.CONCEPT_LABELS for c in rfc._RULE_CONCEPTS[rid])
        assert rid in emergency_explain._WHY, rid  # no generic fallback for concept rules
    assert set(rfc.CONCEPT_LABELS) <= set(rfc.CONCEPTS)


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_emergency_result_quotes_the_users_words_and_is_json_safe(lang):
    patient = {"symptoms": ["ولدي انضرب على راسه وبعدها صار يستفرغ أكثر من مرة ونعسان مرة."]}
    safety = safety_engine.evaluate(patient, lang=lang)
    assert safety["emergency"] and "concept_head_injury" in safety["evidence"]
    res = safety_engine.emergency_result(safety, lang, patient)
    json.dumps(res, ensure_ascii=False)
    reason = next(r for r in res["risk_reasons"] if r["rule_id"] == "concept_head_injury")
    assert [q for e in reason["evidence"] for q in e["quotes"]] == ["انضرب على راسه", "يستفرغ أكثر من مرة", "ونعسان"]
    assert "انضرب على راسه" in reason["message"] and reason["source"]
    assert reason["message"].startswith("كتبتَ" if lang == "ar" else "You wrote")


def test_reason_labels_pair_with_their_own_rule_even_when_flags_are_deduplicated():
    safety = {"flags": ["A"], "rule_ids": ["severe_chest_pain", "chest_pain_cardiac_features"],
              "rule_labels": {"severe_chest_pain": "A", "chest_pain_cardiac_features": "A"}}
    rr, _ = emergency_explain.reasons(safety, "en")
    assert [r["rule_id"] for r in rr] == ["severe_chest_pain"]  # one reason per shown label


def test_phrase_rules_without_evidence_fall_back_to_the_inputs():
    rr, why = emergency_explain.reasons({"flags": ["x"], "rule_ids": ["severe_breathing"]}, "en", {"symptoms": ["cannot breathe"]})
    assert rr[0]["evidence"] == [] and "cannot breathe" in why


def test_frontend_renders_evidence_and_source_in_both_languages():
    js = (ROOT / "static/js/chat/red-flags.js").read_text(encoding="utf-8")
    assert "r.evidence" in js and "data-em-evidence" in js and "TT('em_ev_t')" in js and "TT('em_src')" in js
    assert "esc(q)" in js and "esc(e.label" in js  # user text is escaped
    view = (ROOT / "chat_view.py").read_text(encoding="utf-8")
    assert view.count('"em_ev_t"') == 2 and view.count('"em_src"') == 2


def test_concept_module_is_part_of_the_frozen_algorithm_signature():
    files = {f["file"] for f in research_study.algorithm_signature()["files"]}
    assert {"red_flag_concepts.py", "arabizi.py"} <= files and "emergency_explain.py" not in research_study.CORE_FILES
