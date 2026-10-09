"""V276 safety regression tests (they LOCK the current behaviour; they do not change triage rules).

Emergency phrasing the engine already recognises must keep returning an emergency.
Phrasing it does NOT yet recognise is listed in KNOWN_GAPS: those cases are xfail so the
suite documents them without pretending they are fixed. Closing a gap means editing the
emergency lexicon, which is a clinical decision and needs clinician sign-off first
(see CLINICAL_REVIEW_SAFETY_GAPS_V276.md).
"""
import itertools

import pytest
import webapp

_ip = itertools.count(1)

EMERGENCY_CASES = [
    ("ar", ["ألم في الصدر شديد"]), ("ar", ["ضيق شديد في التنفس"]), ("ar", ["فقدان الوعي"]), ("ar", ["إغماء"]),
    ("ar", ["ضعف مفاجئ في الجانب الأيمن من الجسم"]), ("ar", ["فقدان مفاجئ للرؤية"]), ("ar", ["ما اقدر اتنفس"]),
    ("ar", ["صدري يعورني بقوة"]), ("ar", ["الم بالصدر شديد وينتشر للذراع"]), ("ar", ["ضيق نفس شديد جدا ما اقدر اتنفس"]),
    ("ar", ["التواء مفاجئ في الوجه وصعوبة الكلام"]), ("ar", ["ما اشوف فجأة"]),
    ("en", ["severe chest pain"]), ("en", ["severe shortness of breath"]), ("en", ["fainted and lost consciousness"]),
    ("en", ["passed out"]), ("en", ["sudden weakness on one side of the body"]), ("en", ["sudden loss of vision"]),
    ("en", ["I can't breathe"]), ("en", ["face drooping and slurred speech"]), ("en", ["chest pain", "ضيق نفس"]),
]

# Observed gaps (current engine returns "medium / review", not an emergency). NOT fixed here on purpose.
KNOWN_GAPS = [
    ("ar", ["اغمي علي"]), ("ar", ["فقدت الوعي"]), ("ar", ["نفسي ضايق جدا"]), ("ar", ["وجع في الصدر"]),
    ("ar", ["لا اقدر احرك يدي اليمنى فجأة"]),
    ("en", ["cant breathe"]), ("en", ["hard to breathe"]), ("en", ["chest pian"]), ("en", ["chset pain severe"]),
    ("en", ["suddenly cannot see"]), ("en", ["crushing chest pressure"]),
]

ABSOLUTE_REASSURANCE = ["لا يوجد أي خطر", "لا خطر", "no risk at all", "nothing to worry about", "completely safe", "no danger at all"]


@pytest.fixture(scope="module")
def client():
    c = webapp.app.test_client()
    c.environ_base["REMOTE_ADDR"] = "192.0.2.88"
    assert c.post("/api/consent/preferences", json={"service_usage": True, "analytics_research": False}).status_code == 200
    return c


def _analyze(client, lang, symptoms, **extra):
    body = {"age": 45, "gender": "male", "symptoms": symptoms, "duration": "اليوم" if lang == "ar" else "today", "severity": 4, "notes": "", "lang": lang}
    body.update(extra)
    r = client.post("/api/analyze", json=body, environ_overrides={"REMOTE_ADDR": "198.51.100.%d" % (next(_ip) % 250 + 1)})
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    return r.get_json()


@pytest.mark.parametrize("lang,symptoms", EMERGENCY_CASES)
def test_recognised_emergency_phrasing_stays_an_emergency(client, lang, symptoms):
    j = _analyze(client, lang, symptoms)
    assert j.get("emergency") is True and j.get("urgency") == "high"
    assert j.get("danger_signs")


@pytest.mark.xfail(reason="Known gap: needs clinician-approved lexicon change (see CLINICAL_REVIEW_SAFETY_GAPS_V276.md)", strict=False)
@pytest.mark.parametrize("lang,symptoms", KNOWN_GAPS)
def test_known_gap_phrasing_should_become_an_emergency_after_clinical_signoff(client, lang, symptoms):
    j = _analyze(client, lang, symptoms)
    assert j.get("emergency") is True


@pytest.mark.parametrize("lang,symptoms", KNOWN_GAPS)
def test_known_gaps_are_never_reported_as_low_risk_and_keep_warning_signs(client, lang, symptoms):
    j = _analyze(client, lang, symptoms)
    assert j.get("urgency") in ("medium", "high")
    assert j.get("danger_signs")


@pytest.mark.parametrize("lang,symptoms", [("ar", ["صداع"]), ("en", ["headache"]), ("ar", ["صداع", "غثيان"]), ("en", ["cough"])])
def test_unspecific_or_incomplete_input_is_not_given_a_low_risk_or_absolute_reassurance(client, lang, symptoms):
    j = _analyze(client, lang, symptoms)
    assert j.get("urgency") != "low"
    blob = str(j).lower()
    assert not any(p.lower() in blob for p in ABSOLUTE_REASSURANCE)


def test_headache_with_emergency_companion_symptom_is_not_downgraded(client):
    plain = _analyze(client, "en", ["headache"])
    worse = _analyze(client, "en", ["headache", "sudden weakness on one side of the body"])
    assert worse.get("emergency") is True and plain.get("emergency") is not True


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_emergency_result_never_shows_diagnosis_wording_and_points_to_urgent_care(client, lang):
    j = _analyze(client, lang, ["ألم في الصدر شديد"] if lang == "ar" else ["severe chest pain"])
    blob = str(j)
    assert not any(w in blob.lower() for w in ("you have a heart attack", "diagnosed with", "لديك احتشاء", "تشخيصك"))
    assert j.get("emergency") is True


def test_post_analysis_recheck_failure_never_removes_a_primary_emergency(client, monkeypatch):
    """The secondary re-check may fail (it is logged); the primary pre-analysis safety result must still stand."""
    import analysis_core
    calls = {"n": 0}
    real = analysis_core.detect_red_flags

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] > 1:
            raise RuntimeError("secondary re-check down")
        return real(*a, **k)
    monkeypatch.setattr(analysis_core, "detect_red_flags", flaky)
    j = _analyze(client, "ar", ["ضيق شديد في التنفس"])
    assert j.get("emergency") is True and j.get("urgency") == "high"
