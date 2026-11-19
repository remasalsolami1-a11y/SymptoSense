"""Context-dependent red flags found in the V251 audit (infant fever, appendicitis,
pregnancy pain, DVT/PE) and the helpers they rely on."""
import pytest

import analysis_core
import clinical_text
import context_triage


def _run(notes, symptoms=(), age=30, severity=3, gender="female"):
    return analysis_core.run_analysis({"age": age, "gender": gender, "symptoms": list(symptoms), "notes": notes,
                                       "duration": "يوم", "severity": severity}, "ar")


@pytest.mark.parametrize("notes,symptoms,age,rule", [
    ("رضيع عمره شهرين عنده حرارة 38.5", ["حمى"], 0, "infant_fever_under_3m"),
    ("الم اسفل البطن من اليمين مع حرارة وغثيان من امس", ["ألم بطن"], 22, "suspected_appendicitis"),
    ("حامل اسبوع 7 والم حاد جهة واحدة مع دوخة", ["ألم بطن"], 28, "pregnancy_pain_warning"),
    ("تورم والم في ساق واحدة بعد رحلة طويلة وضيق نفس خفيف", ["تورم"], 45, "dvt_pe_pattern"),
])
def test_audit_scenarios_are_emergencies_and_name_no_disease(notes, symptoms, age, rule):
    r = _run(notes, symptoms, age)
    assert r["emergency"] is True and r["urgency"] == "high"
    import safety_engine
    ids = safety_engine.evaluate({"age": age, "symptoms": list(symptoms), "notes": notes, "severity": 3})["rule_ids"]
    assert rule in ids
    assert "توافق" not in str(r.get("possible_conditions"))  # no diagnosis shown during an emergency


def test_english_wording_works():
    r = analysis_core.run_analysis({"age": 25, "gender": "male", "symptoms": [], "notes": "right lower abdominal pain with fever",
                                    "duration": "1 day", "severity": 3}, "en")
    assert r["emergency"] is True


@pytest.mark.parametrize("notes", [
    "ألم خفيف أسفل البطن من اليمين",
    "تورم والم في ساق واحدة بعد رحلة طويلة",
])
def test_weaker_versions_raise_care_level_without_emergency(notes):
    r = _run(notes, ["تورم" if "ساق" in notes else "ألم بطن"], 40, severity=2)
    assert not r.get("emergency")
    assert r["urgency"] in ("medium", "high")


@pytest.mark.parametrize("notes", [
    "رضيع عمره 5 اشهر حرارته 38", "ما عنده حرارة عمره شهرين", "عمري 30 وعندي حرارة",
    "ألم أسفل البطن من اليسار", "كان عندي ألم في الزايدة قبل سنين وعملت عملية",
    "حامل والم خفيف في الظهر", "حامل وغثيان الصباح", "تورم في الرجلين مع المساء",
    "ما عندي ضيق نفس ولا تورم بالساق", "ألم عضلي في الساق بعد الرياضة",
])
def test_no_false_alarms(notes):
    assert not context_triage.evaluate({"symptoms": [], "notes": notes, "age": 30})["emergency"], notes


def test_third_person_negation_is_understood():
    for t in ("ما عنده حرارة", "ما عندها حرارة", "ما فيه حرارة", "ما يعاني من حرارة", "ليس لديه حرارة"):
        assert not clinical_text.contains_unnegated_any(t, ("حرارة",)), t
    assert clinical_text.contains_unnegated_any("عنده حرارة", ("حرارة",))
    assert clinical_text.contains_unnegated_any("ما عنده نزيف لكن عنده حرارة", ("حرارة",))


def test_infant_age_helper_handles_months_word_forms():
    f = analysis_core._extract_age_months
    assert f(None, "رضيع عمره 5 اشهر") == 5.0   # used to be read as 1 month
    assert f(None, "عمره شهرين") == 2.0
    assert f(None, "عمره 6 اسابيع") == pytest.approx(6 / 4.345)
    assert f(None, "ما فيه عمر") is None


@pytest.mark.parametrize("notes", [
    "عمري 30 وعندي حرارة 38 من 3 ايام", "حرارة من اسبوعين وسعال", "fever for 2 weeks", "حرارتي 38 من يومين",
    "عندي حرارة لمدة شهر", "ابني من شهرين مريض وحرارته 38",
])
def test_duration_is_not_mistaken_for_infant_age(notes):
    assert analysis_core._extract_age_months(None, notes) is None
    assert not context_triage.evaluate({"symptoms": [], "notes": notes, "age": 30})["emergency"], notes


def test_age_field_is_trusted_without_cue():
    assert analysis_core._extract_age_months("3 months", "") == 3.0
    assert analysis_core._extract_age_months("2", "") == 24


def test_unrelated_old_events_do_not_hide_pregnancy_or_clot_warnings():
    # An old surgery / "كان عندي" earlier in the text must not suppress a current emergency.
    for t in ("عملت عملية قبل سنه وحامل الان والم حاد جهة واحدة مع دوخة",
              "كان عندي صداع قديم والحين حامل والم حاد جهة واحدة ودوخة"):
        assert context_triage.evaluate({"symptoms": [], "notes": t})["emergency"], t


def test_removed_appendix_does_not_trigger_appendicitis_rule():
    t = "عملت عملية الزايدة وعندي الم اسفل البطن يمين وحرارة"
    assert not any(x[0] == "suspected_appendicitis" for x in context_triage.evaluate({"symptoms": [], "notes": t})["emergency"])


def test_normalization_cache_keeps_long_input_fast():
    import time
    import safety_engine
    start = time.perf_counter()
    safety_engine.evaluate({"symptoms": [], "notes": "ال" * 2000})
    assert time.perf_counter() - start < 1.0
