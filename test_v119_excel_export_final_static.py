import source_bundle
from pathlib import Path

ROOT=Path(__file__).resolve().parent
WEB=source_bundle.webapp_text()
DB=(ROOT/'db.py').read_text(encoding='utf-8')
DASH=(ROOT/'dashboard.py').read_text(encoding='utf-8')
SW=(ROOT/'service-worker.js').read_text(encoding='utf-8')

def test_browser_native_xlsx_route_exists():
    assert '@app.route("/admin/lab-trials/export.xlsx", methods=["GET"])' in WEB
    start=WEB.index('def admin_lab_trials_export_xlsx():')
    block=WEB[start:start+5000]
    assert 'db.init_db()' in block
    assert 'as_attachment=True' in block
    assert 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' in block
    assert 'download_name=filename' in block
    assert 'no-store' in block

def test_dashboard_download_is_normal_anchor():
    assert 'href="/admin/analysis-trials/export.xlsx"' in DASH

def test_old_api_route_redirects_to_native_download():
    start=WEB.index('def api_admin_export_lab_trials_xlsx():')
    block=WEB[start:start+700]
    assert 'redirect(url_for("admin_lab_trials_export_xlsx"), code=302)' in block

def test_export_handles_legacy_member_id_schema():
    start=DB.index('def admin_export_blood_test_trials_xlsx():')
    end=DB.index('def admin_clear_blood_test_trials():',start)
    block=DB[start:end]
    assert 'has_member_id = "member_id" in columns' in block
    assert 'rows.append((row[0], row[1], row[2], row[3], 0))' in block

def test_export_neutralizes_formula_injection():
    start=DB.index('def admin_export_blood_test_trials_xlsx():')
    end=DB.index('def admin_clear_blood_test_trials():',start)
    block=DB[start:end]
    assert 'text.startswith(("=", "+", "-", "@"))' in block
    assert 'return "\'" + text' in block

def test_service_worker_does_not_intercept_xlsx():
    assert "earlyUrl.pathname.endsWith('.xlsx')" in SW
