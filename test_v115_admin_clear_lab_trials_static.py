import source_bundle
from pathlib import Path

ROOT=Path(__file__).resolve().parent
WEB=source_bundle.webapp_text()
DB=(ROOT/"db.py").read_text(encoding="utf-8")
DASH=(ROOT/"dashboard.py").read_text(encoding="utf-8")

def test_db_cleanup_only_targets_blood_tests():
    start=DB.index("def admin_clear_blood_test_trials():")
    end=DB.index("def reset_public_launch_data", start)
    block=DB[start:end]
    assert 'DELETE FROM blood_tests' in block
    assert 'DELETE FROM ss_users' not in block
    assert 'DELETE FROM records' not in block
    assert 'DELETE FROM med_' not in block

def test_admin_routes_require_auth_and_password_confirmation():
    assert '@app.route("/api/admin/analysis-trials/clear", methods=["POST"])' in WEB
    start=WEB.index("def api_admin_clear_lab_trials():")
    block=WEB[start:start+3000]
    assert 'DELETE TRIALS' in block
    assert 'db.verify_ss_user_password(_ss_user_id(), current_password)' in block
    assert 'db.admin_clear_symptom_trials()' in block

def test_dashboard_has_clear_lab_trials_button_and_modal():
    assert "بيانات تجارب تحليل الأعراض" in DASH
    assert 'id="labTrialCleanupModal"' in DASH
    assert 'href="/admin/analysis-trials#delete"' in DASH
    assert "DELETE TRIALS" in DASH

def test_ui_explains_accounts_are_preserved():
    assert "لا يحذف الحسابات" in DASH or "حسابات المستخدمين" in DASH
    assert "CBC" in DASH

def test_admin_settings_loads_lab_trial_summary():
    assert "loadLabTrialSummary()" in DASH
    assert "if(name==='adminsettings'){loadAdminProfile();loadLabTrialSummary();loadBloodTrialSummary();}" in DASH
