from pathlib import Path
DB=(Path(__file__).resolve().parent/"db.py").read_text(encoding="utf-8")

def _block():
    return DB[DB.index("def admin_export_blood_test_trials_xlsx():"):DB.index("def admin_clear_blood_test_trials():")]

def test_export_uses_conference_sheet_names():
    block=_block()
    assert 'summary_ws.title = "Executive Summary"' in block
    assert 'wb.create_sheet("Lab Trials")' in block
    assert 'wb.create_sheet("Indicators")' in block
    assert 'wb.create_sheet("Data Dictionary")' in block

def test_export_has_human_friendly_bilingual_headers_and_empty_state():
    block=_block()
    for token in ("كود التجربة","Timestamp (UTC)","Risk Level","مستوى النتيجة","Associated Symptoms","أعراض مرتبطة","لا توجد بيانات تحليل محفوظة"):
        assert token in block

def test_export_has_tables_freeze_and_risk_highlighting():
    block=_block()
    assert 'TableStyleMedium2' in block
    assert 'trials_ws.freeze_panes = "A6"' in block
    assert 'indicators_ws.freeze_panes = "A6"' in block
    assert '"Emergency | طارئ": (red, "A12828")' in block
