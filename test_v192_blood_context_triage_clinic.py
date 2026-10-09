import source_bundle
from pathlib import Path

import blood_test

ROOT = Path(__file__).resolve().parent
WEBAPP = source_bundle.webapp_text()


def _analyze(raw, *, gender="", age=None):
    entries, parsed_age = blood_test.parse_blood_text(raw)
    results, notes, dangers, level, child_note = blood_test.analyze_blood(
        entries, gender=gender, age=age if age is not None else parsed_age
    )
    indicators = blood_test.describe_results(results, "ar")
    return results, indicators, dangers, level


def test_lab_range_is_primary_and_missing_range_stays_unclassified():
    results, indicators, dangers, level = _analyze("Glucose | 160 | mg/dL | 70 | 99 | High")
    row = results[0]
    assert row["status"] == "high"
    assert row["reference_source"] == "lab_reference"
    assert row["low"] == 70.0 and row["high"] == 99.0
    assert indicators[0]["verification_level"] in {"double_verified", "lab_range_verified"}

    results, indicators, dangers, level = _analyze("Troponin | 30 | ng/L | | |")
    row = results[0]
    assert row["status"] == "unclassified"
    assert row["reference_source"] == "unclassified"
    assert indicators[0]["attention_level"] == "needs_confirmation"
    assert level == "unclassified"
    assert not dangers


def test_context_is_sanitized_and_does_not_override_classification():
    ctx = blood_test.normalize_analysis_context({
        "fasting_status": "not-a-value",
        "sample_time": "99:99",
        "notes": "  iron    supplement  " + ("x" * 400),
    })
    assert ctx["fasting_status"] == "unknown"
    assert ctx["sample_time"] == ""
    assert len(ctx["notes"]) <= 300
    assert "  " not in ctx["notes"]

    results, indicators, dangers, level = _analyze("Glucose | 160 | mg/dL | 70 | 99 | High")
    notes = blood_test.build_context_notes(
        results,
        {"fasting_status": "non_fasting", "sample_time": "14:30", "notes": "دواء صباحي"},
        "ar",
    )
    assert results[0]["status"] == "high"
    assert any("لا نغيّر تصنيف المختبر" in n for n in notes)
    assert any("14:30" in n for n in notes)


def test_verified_numeric_triage_distinguishes_urgent_and_emergency():
    results, indicators, dangers, level = _analyze("HGB | 6.5 | g/dL | 12 | 16 | Low")
    assert level == "urgent"
    assert indicators[0]["attention_level"] == "urgent"
    assert any(d[0] == "urgent" for d in dangers)
    assert not any(d[0] == "emergency" for d in dangers)

    results, indicators, dangers, level = _analyze("HGB | 4.5 | g/dL | 12 | 16 | Low")
    assert level == "emergency"
    assert indicators[0]["attention_level"] == "emergency"
    assert any(d[0] == "emergency" for d in dangers)


def test_lab_printed_critical_is_urgent_not_blind_universal_emergency():
    results, indicators, dangers, level = _analyze("Troponin | 30 | ng/L | | | Critical")
    row = results[0]
    assert row["reported_critical"] is True
    assert row["reference_source"] == "lab_reported_status"
    assert indicators[0]["attention_level"] == "urgent"
    assert level == "urgent"
    assert any(d[0] == "urgent" for d in dangers)
    assert not any(d[0] == "emergency" for d in dangers)


def test_possible_factors_are_cautious_and_non_diagnostic():
    results, indicators, dangers, level = _analyze("HGB | 10 | g/dL | 12 | 16 | Low")
    item = indicators[0]
    assert item["possible_factors"]
    assert "تشخيص" in item["possible_factors_note"]
    assert all(isinstance(x, str) and x.strip() for x in item["possible_factors"])


def test_dynamic_doctor_questions_and_clinic_summary_include_context():
    results, indicators, dangers, level = _analyze("Glucose | 160 | mg/dL | 70 | 99 | High")
    ctx = {"fasting_status": "unknown", "sample_time": "08:15", "notes": "أستخدم دواء يوميًا"}
    questions = blood_test.build_doctor_questions(indicators, ctx, "ar")
    assert 3 <= len(questions) <= 5
    assert any("صيام" in q for q in questions)

    summary = blood_test.build_doctor_summary(
        results,
        patterns=[],
        lang="ar",
        age=31,
        gender="f",
        context=ctx,
        level=level,
        questions=questions,
    )
    assert "ملخص التحاليل للعيادة" in summary
    assert "وقت السحب: 08:15" in summary
    assert "أستخدم دواء يوميًا" in summary
    assert "أسئلة مقترحة للطبيب" in summary
    assert "لا يمثل تشخيصًا" in summary


def test_blood_ui_contains_v192_context_and_clinic_workflow():
    required = [
        "الأولوية دائمًا للنطاق المرجعي المكتوب في تقرير مختبرك",
        "clinical_context",
        "labxFasting",
        "labxSampleTime",
        "function labxContextProfile()",
        "if(ctxProfile.timing||ctxProfile.meds)",
        "reported_critical",
        "possible_factors",
        "download-clinic",
        "labxDownloadClinicSummary",
        "doctor_questions",
        "context_notes",
    ]
    for marker in required:
        assert marker in WEBAPP, marker
