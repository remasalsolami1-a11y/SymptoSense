import source_bundle
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DB=(ROOT/"db.py").read_text(encoding="utf-8")
WEB=source_bundle.webapp_text()
DASH=(ROOT/"dashboard.py").read_text(encoding="utf-8")

def block():
    a=DB.index("def admin_export_symptom_trials_xlsx():")
    b=DB.index("def admin_clear_symptom_trials():",a)
    return DB[a:b]

def test_minimal_excel_structure():
    x=block()
    assert "merge_cells(" not in x
    assert "auto_filter" not in x
    assert "freeze_panes" not in x
    assert "Table(" not in x
    assert "showGridLines=True" in x
    assert "zoomScale=100" in x

def test_only_requested_columns():
    assert "headers=['Age | العمر','Gender | الجنس','Symptoms | الأعراض','Duration | المدة']" in block()

def test_server_validates_and_uses_send_file():
    a=WEB.index("def admin_lab_trials_export_xlsx():")
    b=WEB.index('@app.route("/admin/analysis-trials"',a)
    x=WEB[a:b]
    assert "zipfile.ZipFile" in x
    assert "archive.testzip()" in x
    assert "send_file(" in x
    assert "as_attachment=True" in x
    assert "conditional=False" in x
    assert "etag=False" in x

def test_link_uses_normal_attachment_response():
    assert 'href="/admin/analysis-trials/export.xlsx" download' in DASH
