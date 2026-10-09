import source_bundle
from pathlib import Path

ROOT=Path(__file__).resolve().parent
WEB=source_bundle.webapp_text()
DASH=(ROOT/"dashboard.py").read_text(encoding="utf-8")

def test_settings_has_real_url_fallback():
    assert 'href="/admin?view=adminsettings#labTrialCleanupCard"' in DASH
    assert "{% set settings_open = requested_view == 'adminsettings' %}" in DASH
    assert "view{{ ' on' if settings_open else '' }}" in DASH

def test_sidebar_has_direct_lab_data_page():
    assert 'href="/admin/analysis-trials"' in DASH
    assert "ملفات Excel للتجارب" in DASH

def test_excel_download_is_direct_anchor_not_js_only():
    assert 'href="/admin/analysis-trials/export.xlsx"' in DASH

def test_lab_data_page_works_without_dashboard_js():
    assert '@app.route("/admin/lab-trials", methods=["GET", "POST"])' in WEB
    start=WEB.index("def admin_lab_trials_page():")
    block=WEB[start:start+9000]
    assert 'db.admin_symptom_trial_summary()' in block
    assert 'db.admin_clear_symptom_trials()' in block
    assert 'db.verify_ss_user_password' in block
    assert 'DELETE TRIALS' in block
    assert '/admin/analysis-trials/export.xlsx' in block

def test_admin_route_no_longer_blocks_on_knowledge_schema_init():
    start=WEB.index('@app.route("/admin")')
    end=WEB.index('@app.route("/admin/lab-trials"', start)
    block=WEB[start:end]
    assert "medical_knowledge.init_schema()" not in block
