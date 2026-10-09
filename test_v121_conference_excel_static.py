from pathlib import Path

ROOT=Path(__file__).resolve().parent
DB=(ROOT/"db.py").read_text(encoding="utf-8")

def export_block():
    a=DB.index("def admin_export_blood_test_trials_xlsx():")
    b=DB.index("def admin_clear_blood_test_trials():",a)
    return DB[a:b]

def test_conference_workbook_has_four_expected_sheets():
    block=export_block()
    assert 'summary_ws.title = "Executive Summary"' in block
    assert 'wb.create_sheet("Lab Trials")' in block
    assert 'wb.create_sheet("Indicators")' in block
    assert 'wb.create_sheet("Data Dictionary")' in block

def test_conference_workbook_is_bilingual_and_review_friendly():
    block=export_block()
    for token in (
        "Conference-ready administrative export",
        "Saved Trials", "التجارب المحفوظة",
        "Risk Distribution", "توزيع مستوى النتيجة",
        "Privacy & Ethics", "الخصوصية والأخلاقيات",
        "Data Dictionary & Conference Notes",
    ):
        assert token in block

def test_empty_dataset_has_professional_state_instead_of_blank_tables():
    block=export_block()
    assert "No saved CBC trials were found in this dataset." in block
    assert "لا توجد بيانات تحليل محفوظة في الملف الحالي." in block
    assert "No CBC indicator rows are available in this export." in block

def test_export_keeps_privacy_and_legacy_schema_guards():
    block=export_block()
    assert 'has_member_id = "member_id" in columns' in block
    assert 'rows.append((row[0], row[1], row[2], row[3], 0))' in block
    assert 'tester_code = _code("U", user_hash)' in block
    assert 'text.startswith(("=", "+", "-", "@"))' in block

def test_risk_and_indicator_statuses_are_highlighted():
    block=export_block()
    assert '"Emergency | طارئ": (red, "A12828")' in block
    assert '"Urgent | عاجل": (orange, "9A4C00")' in block
    assert '"High | مرتفع": (red, "A12828")' in block
    assert '"Low | منخفض": (pale_blue, navy)' in block
