"""V198: precision triage — reduce false emergency bypasses without weakening true red flags."""
import analysis_core
import safety_engine


def _s(text, **extra):
    patient = {"symptoms": [text], "notes": ""}
    patient.update(extra)
    return safety_engine.evaluate(patient, lang="ar")


def _t(text, **extra):
    patient = {
        "symptoms": [text],
        "notes": "",
        "severity": 1,
        "duration": "",
        "age": None,
    }
    patient.update(extra)
    return analysis_core._triage(patient, "ar")


def test_true_immediate_danger_still_bypasses():
    cases = [
        "ألم شديد في الصدر",
        "ما اقدر اتنفس",
        "فاقد الوعي الآن ولا يستجيب",
        "نزيف لا يتوقف",
        "عندي تشنج الآن",
        "نوبة تشنجية الآن",
        "نوبة تشنجية مستمرة الآن",
        "ضعف مفاجئ بالطرف",
        "أسوأ صداع في حياتي",
        "بلعت حبوب كثير",
    ]
    for text in cases:
        assert _s(text)["emergency"] is True, text


def test_ambiguous_or_context_explained_cases_do_not_jump_to_emergency():
    cases = [
        "تشنج",
        "حامل ونزيف خفيف بدون ألم",
        "رضيع حرارته 40",
        "وجهي مايل من سنوات",
        "ما اقدر احرك يدي بسبب الجبس",
    ]
    for text in cases:
        result = _s(text)
        assert result["emergency"] is False, (text, result["rule_ids"])


def test_pregnancy_bleeding_uses_two_levels():
    assert _t("حامل ونزيف خفيف بدون ألم")["level"] == "today"
    assert _s("حامل ونزيف وألم شديد في البطن")["emergency"] is True


def test_infant_fever_is_age_aware():
    # V251: fever >= 38 C under 3 months needs emergency assessment (NICE/AAP febrile-infant guidance);
    # older infants stay "today" and only at high temperatures.
    assert _t("طفل عمره شهرين حرارته 38")["level"] == "emergency"
    assert _t("رضيع عمره 4 اشهر حرارته 37.5")["level"] == "monitor"
    assert _t("رضيع عمره 4 شهور حرارته 39")["level"] == "today"
    assert _t("رضيع عمره 10 شهور حرارته 38")["level"] == "monitor"
    assert _s("رضيع عمره 10 شهور حرارته 38")["emergency"] is False


def test_chronic_or_mechanical_neuro_context_is_not_red_emergency():
    assert _t("وجهي مايل من سنوات")["level"] == "soon"
    assert _t("ما اقدر احرك يدي بسبب الجبس")["level"] == "soon"


def test_fast_sign_without_chronic_or_mechanical_explanation_remains_emergency():
    assert _s("فمي مايل")["emergency"] is True
    assert _s("ما اقدر احرك يدي اليمين")["emergency"] is True
    assert _s("كلامي ثقيل فجأة")["emergency"] is True


def test_builtin_safety_matrix_passes():
    report = safety_engine.validation_report()
    assert report["all_passed"] is True, report
