import source_bundle
from pathlib import Path

ROOT=Path(__file__).resolve().parent
WEB=source_bundle.webapp_text()
DB=(ROOT/"db.py").read_text(encoding="utf-8")
DASH=(ROOT/"dashboard.py").read_text(encoding="utf-8")

def test_lab_excel_export_route_exists_and_is_admin_protected():
    assert '@app.route("/api/admin/lab-trials/export-xlsx", methods=["GET"])' in WEB
    assert 'def api_admin_export_lab_trials_xlsx():' in WEB
    assert 'db.admin_export_symptom_trials_xlsx()' in WEB
    assert 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' in WEB

def test_export_uses_pseudonymous_codes_not_account_table():
    start=DB.index("def admin_export_blood_test_trials_xlsx():")
    end=DB.index("def admin_clear_blood_test_trials():", start)
    block=DB[start:end]
    assert 'tester_code = _code("U", user_hash)' in block
    assert "ss_users" not in block
    assert "SELECT id, user_hash, timestamp, data" in block

def test_workbook_has_summary_trials_and_indicator_sheets():
    start=DB.index("def admin_export_blood_test_trials_xlsx():")
    end=DB.index("def admin_clear_blood_test_trials():", start)
    block=DB[start:end]
    assert 'summary_ws.title = "Executive Summary"' in block
    assert 'wb.create_sheet("Lab Trials")' in block
    assert 'wb.create_sheet("Indicators")' in block
    assert 'wb.create_sheet("Data Dictionary")' in block

def test_admin_card_has_export_and_delete_buttons():
    assert "تحميل ملف تحليل الأعراض" in DASH
    assert 'href="/admin/analysis-trials/export.xlsx"' in DASH
    assert 'href="/admin/analysis-trials#delete"' in DASH
    assert 'id="labExportStatus"' in DASH
