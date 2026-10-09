import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()
DASH = (ROOT / 'dashboard.py').read_text(encoding='utf-8')
PRIV = (ROOT / 'privacy_features.py').read_text(encoding='utf-8')
VALID = (ROOT / 'research_validation.py').read_text(encoding='utf-8')
REQ = (ROOT / 'requirements.txt').read_text(encoding='utf-8')


def test_research_export_is_adult_only_defense_in_depth():
    assert 'adult = _record_is_adult(c, record_id)' in PRIV
    assert 'int(bool(research) and adult)' in PRIV
    assert 'age IS NULL OR age < 18' in PRIV
    assert 'age 18 or older' in (ROOT / 'admin_complete.py').read_text(encoding='utf-8')


def test_admin_totp_is_mandatory_and_encrypted_at_rest():
    assert 'import admin_2fa' in WEB
    assert '@app.route("/admin/2fa/setup"' in WEB
    assert '@app.route("/admin/2fa"' in WEB
    assert 'session["admin_2fa_verified"]' in WEB
    assert 'cryptography>=' in REQ
    mod=(ROOT / 'admin_2fa.py').read_text(encoding='utf-8')
    assert 'Fernet' in mod
    assert 'recovery_hashes' in mod
    assert 'verify_totp' in mod


def test_research_validation_has_balanced_starter_and_verified_only_metrics():
    assert 'BENCH-H20' in VALID and 'BENCH-M20' in VALID and 'BENCH-L20' in VALID
    assert 'reference_verified' in VALID
    assert 'Only independently verified reference cases' in VALID
    assert 'urgent_sensitivity_pct' in VALID
    assert 'urgent_specificity_pct' in VALID
    assert 'recommended_min_verified_cases' in VALID
    assert 'مرجع مستقل موثق' in DASH
    assert 'التقدم نحو 100 حالة' in DASH


def test_admin_dashboard_reports_2fa_status():
    assert "/api/admin/2fa/status" in DASH
    assert "مفعّل عبر Authenticator" in DASH
    assert "رموز الاسترداد المتبقية" in DASH
