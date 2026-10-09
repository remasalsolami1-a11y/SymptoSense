import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DASH = (ROOT / 'dashboard.py').read_text(encoding='utf-8')
WEB = source_bundle.webapp_text()
DB = (ROOT / 'db.py').read_text(encoding='utf-8')


def test_admin_dashboard_has_guarded_launch_reset_button():
    assert 'إعادة ضبط بيانات التجربة' in DASH
    assert "openLaunchReset()" in DASH
    assert 'launchResetPassword' in DASH
    assert 'launchResetPhrase' in DASH
    assert "phrase!=='RESET'" in DASH
    assert "confirm(txt(" in DASH


def test_reset_api_is_admin_csrf_protected_and_password_confirmed():
    assert '@app.route("/api/admin/reset-test-data", methods=["POST"])' in WEB
    assert '@admin_api_required("access")' in WEB
    assert 'confirmation != "RESET"' in WEB
    assert 'db.verify_ss_user_password(_ss_user_id(), current_password)' in WEB
    assert 'db.reset_public_launch_data(_ss_user_id())' in WEB


def test_reset_preserves_admin_and_curated_medical_content():
    assert 'DELETE FROM ss_users WHERE id <>' in DB
    assert 'mk_unmatched_log' in DB
    # Curated knowledge and content must never be part of the purge list.
    reset_block = DB.split('def reset_public_launch_data', 1)[1].split('def get_ss_user', 1)[0]
    assert '"ss_content"' not in reset_block
    assert '"medical_medications"' not in reset_block
    assert '"mk_diseases"' not in reset_block
    assert '"mk_symptoms"' not in reset_block
    assert '"mk_sources"' not in reset_block
    assert '"ss_schema_meta"' not in reset_block
