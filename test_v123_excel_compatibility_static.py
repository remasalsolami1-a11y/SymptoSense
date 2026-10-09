from pathlib import Path

ROOT=Path(__file__).resolve().parent
DB=(ROOT/'db.py').read_text(encoding='utf-8')

def export_block():
    a=DB.index('def admin_export_symptom_trials_xlsx():')
    b=DB.index('def admin_clear_symptom_trials():', a)
    return DB[a:b]

def test_export_has_only_requested_columns():
    block=export_block()
    assert "headers=['Age | العمر','Gender | الجنس','Symptoms | الأعراض','Duration | المدة']" in block
    assert 'tester_code' not in block
    assert 'risk_level' not in block

def test_export_avoids_excel_table_parts_and_duplicate_filter_metadata():
    block=export_block()
    assert 'from openpyxl.worksheet.table import Table' not in block
    assert 'Table(' not in block
    assert 'add_table(' not in block
    assert 'auto_filter' not in block

def test_export_avoids_risky_print_title_and_page_setup_metadata():
    block=export_block()
    assert 'print_title_rows' not in block
    assert 'page_setup' not in block
    assert 'fitToPage' not in block

def test_export_keeps_simple_professional_formatting():
    block=export_block()
    assert 'freeze_panes' not in block
    assert "'C':58" in block
    assert "Saved analyses | التحليلات المحفوظة: {len(rows)}" in block
