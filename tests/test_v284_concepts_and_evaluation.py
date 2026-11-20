"""V284: compositional red-flag concepts, Arabic verbal negation, and the offline evaluator."""
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import clinical_text  # noqa: E402
import red_flag_concepts as rfc  # noqa: E402
import safety_engine  # noqa: E402


def _rules(text):
    return {r for r, _a, _e in rfc.evaluate(text)}


@pytest.mark.parametrize("text, rule", [
    ("بعد ما أكلت انتفخت شفايفي ولساني بسرعة وصار نفسي ضيق.", "concept_anaphylaxis"),
    ("Severe allergic reaction with widespread hives, wheeze, and dizziness.", "concept_anaphylaxis"),
    ("البراز صاير أسود مثل القار وأحس إني بيغمى علي.", "concept_gi_bleed"),
    ("Black tarry stool with faintness.", "concept_gi_bleed"),
    ("ولدي انضرب على راسه وبعدها صار يستفرغ أكثر من مرة ونعسان مرة.", "concept_head_injury"),
    ("بطني يوجعني بقوة ومشدود مثل الخشبة وما وقفت أستفرغ.", "concept_acute_abdomen"),
    ("فجأة جاني ألم قوي في الخصية وفيها انتفاخ.", "concept_testicular_torsion"),
    ("أمي عندها سكر وصارت متلخبطة وتتنفس بسرعة وبعمق وتستفرغ.", "concept_diabetic_emergency"),
    ("الربو عندي قوي وأخذت البخاخ وما تحسنت.", "concept_severe_asthma"),
    ("حرارتي عالية ورقبتي متيبسة وراسي يعورني مرة.", "concept_meningitis"),
    ("عندي نزيف قوي وأحس بضعف شديد.", "concept_bleeding_shock"),
    ("فجأة ما صرت أشوف بعيني اليمين.", "concept_sudden_vision_loss"),
    ("فجأة فمي مال وما أقدر أرفع يدي.", "concept_stroke_fast"),
])
def test_concept_rules_recognise_red_flags_in_any_wording(text, rule):
    assert rule in _rules(text)
    assert safety_engine.evaluate({"symptoms": [text]}, lang="en" if text.isascii() else "ar")["emergency"]


@pytest.mark.parametrize("text", [
    "ما عندي ضيق تنفس ولا تورم في الشفايف",          # denied pair
    "Mild neck stiffness after sleeping awkwardly, no fever or neurologic symptoms.",
    "ركبتي تطقطق بدون ألم ولا ورم.",
    "ما اقدر اشوف زين بعد ما قريت كثير",              # blurred, not vision loss
    "طحت أمس وراسي يعورني شوي",                      # head knock without danger signs
    "عندي سكر وأحس بعطش",                            # diabetes alone
    "I have asthma and my inhaler helps",
    "Minor bruise after bumping the leg, not enlarging and no unusual bleeding.",
    "عندي سيلان أنف وعطاس خفيف",
])
def test_concept_rules_do_not_fire_on_mild_or_denied_symptoms(text):
    assert _rules(text) == set()


def test_one_letter_typos_are_corrected_against_concept_vocabulary_only():
    norm = clinical_text.normalize_clinical_text("انتفخت شفايفي ولساني وصار نفسي ضيق")
    typo = norm.replace("شفايفي", "شفيفي")
    assert rfc.correct_typos(typo) == norm
    assert rfc.correct_typos("كتبت رسالة طويلة") == "كتبت رسالة طويلة"  # unrelated words untouched
    assert "concept_anaphylaxis" in _rules("انتفخت شفيفي ولساني وصار نفسي ضيق")


def test_arabic_verbal_negation_before_a_symptom():
    assert not clinical_text.contains_unnegated_any("ما اغمي علي", ["اغمي"])
    assert not clinical_text.contains_unnegated_any("لم يغمى عليه", ["يغمي"])
    assert not safety_engine.evaluate({"symptoms": ["ما أغمى علي وما عندي تشنج، بس دايخ شوي."]}, lang="ar")["emergency"]
    # phrases that themselves start with ما still fire
    assert safety_engine.evaluate({"symptoms": ["ما اقدر اتنفس"]}, lang="ar")["emergency"]
    assert safety_engine.evaluate({"symptoms": ["أبوي طاح وما يرد علينا ولا يصحى."]}, lang="ar")["emergency"]


def test_concept_layer_is_fast_enough_for_every_request():
    texts = ["ولدي انضرب على راسه وبعدها صار يستفرغ أكثر من مرة ونعسان مرة. %d" % i for i in range(400)]
    t = time.perf_counter()
    for x in texts:  # distinct texts: no cache hits
        rfc.evaluate(x)
    assert (time.perf_counter() - t) / len(texts) < 0.01  # < 10 ms per text


def test_built_in_safety_regression_matrix_still_passes():
    rep = safety_engine.validation_report()
    assert rep["all_passed"], [c for c in rep["cases"] if not c["passed"]]


# ---------------------------------------------------------------- evaluator
def test_wilson_interval_and_kappa_match_known_values():
    import evaluate_engine as ev

    lo, hi = ev.wilson(8, 10)
    assert round(lo, 3) == 0.490 and round(hi, 3) == 0.943  # textbook Wilson 95% CI for 8/10
    assert ev.wilson(0, 0) == (0.0, 0.0)
    assert ev.cohen_kappa([("high", "high"), ("low", "low")]) == 1.0
    assert ev.cohen_kappa([("high", "low"), ("low", "high")]) == -1.0
    m = ev.metrics([{"expected": "high", "predicted": "low"}, {"expected": "low", "predicted": "medium"}])
    assert m["critical_under_triage"]["k"] == 1 and m["over_triage"]["k"] == 1


def test_evaluation_cases_are_complete_and_typos_deterministic():
    import evaluate_engine as ev

    cases = ev.load_cases()
    assert len(cases["en_dev"]) == 60 and len(cases["en_test"]) == 120
    assert len(cases["ar_msa"]) == len(cases["ar_dialect"]) == len(cases["ar_dialect_typos"]) == 40
    assert {c["expected"] for c in cases["ar_dialect"]} == {"high", "medium", "low"}
    assert ev.arabic_typos("صدري يعورني مرة وأعرق", "X") == ev.arabic_typos("صدري يعورني مرة وأعرق", "X")
    assert ev.arabic_typos("صدري يعورني مرة وأعرق", "X") != "صدري يعورني مرة وأعرق"


def test_doctor_packet_is_blinded_and_labels_round_trip(tmp_path, monkeypatch):
    import csv
    import shutil

    import doctor_review_packet as drp
    import evaluate_engine as ev

    shutil.copy(ROOT / "evaluation" / "arabic_cases.json", tmp_path / "arabic_cases.json")
    monkeypatch.setattr(ev, "EVAL_DIR", tmp_path)
    for name, value in (("EVAL", tmp_path), ("PACKET", tmp_path / "doctor_review.csv"),
                        ("KEY", tmp_path / "doctor_review_key.csv"), ("FILLED", tmp_path / "doctor_labels.csv")):
        monkeypatch.setattr(drp, name, value)
    drp.make()
    with (tmp_path / "doctor_review.csv").open(encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    assert list(rows[0]) == ["review_id", "language", "case_text", "doctor_label", "doctor_note"]
    assert all(r["doctor_label"] == "" and "BENCH" not in r["review_id"] for r in rows)  # no ids or labels leak
    # a simulated clinician who agrees with every starter label
    truth = {c["id"]: c["expected"] for items in ev.load_cases().values() for c in items}
    key = drp.key()
    with (tmp_path / "doctor_labels.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["review_id", "doctor_label"])
        w.writerows((rid, truth[cid]) for rid, cid in key.items())
    assert drp.check(tmp_path / "doctor_labels.csv") == 0
    ref = ev.load_reference()
    assert len(ref) == 220 + 80  # dialect labels propagate to MSA and typo variants
    agreement = ev.label_agreement(ref)
    assert agreement["n"] == 220 and agreement["kappa"] == 1.0


def test_report_never_claims_clinician_labels_unless_they_exist():
    import evaluation_report as rep

    base = {"conditions": {k: {a: {m: {"value": 0.5, "ci95": [0.4, 0.6], "k": 1, "n": 2}
                                   for m in ("high_sensitivity", "critical_under_triage", "over_triage", "accuracy")}
                               | {"confusion": {e: {p: 0 for p in ("high", "medium", "low")} for e in ("high", "medium", "low")}}
                               for a in ("rules", "rules_triage", "hybrid")}
                           for k in ("en_test", "en_dev", "ar_msa", "ar_dialect", "ar_dialect_typos")},
            "safety_suite": {"n": 1, "passed": {"k": 1}}, "meta": {"controlled": {}}}
    base["meta"]["reference"] = "starter benchmark labels (not clinician-verified)"
    assert "غير مراجَعة طبيًا" in rep.render(base) and "تصنيف طبيب" not in rep.render(base)
    base["meta"]["reference"] = "clinician (doctor_labels.csv)"
    assert "تصنيف طبيب" in rep.render(base)
