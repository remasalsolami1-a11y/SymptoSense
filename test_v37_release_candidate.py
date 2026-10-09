import source_bundle
import versioning
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()
READY = (ROOT / "production_readiness.py").read_text(encoding="utf-8")
DASH = (ROOT / "dashboard.py").read_text(encoding="utf-8")
PRIV = (ROOT / "privacy_features.py").read_text(encoding="utf-8")
EXPORT = (ROOT / "admin_complete.py").read_text(encoding="utf-8")
STUDY = (ROOT / "research_study.py").read_text(encoding="utf-8")
VERIFY = (ROOT / "production_verification.py").read_text(encoding="utf-8")
RC = (ROOT / "release_candidate.py").read_text(encoding="utf-8")


def test_live_email_verification_requires_admin_confirmation():
    assert '/api/admin/auth-email-test' in WEB
    assert '/api/admin/auth-email-confirm' in WEB
    assert 'confirmation_required' in WEB
    assert 'live_verified' in READY
    assert 'testProductionEmail()' in DASH
    assert 'confirmProductionEmail()' in DASH


def test_medication_email_readiness_is_release_specific():
    assert '/api/admin/medication-email/status' in WEB
    assert 'medication_email' in READY
    assert 'loadMedicationEmailStatus' in DASH
    assert '/api/push/' not in WEB


def test_privacy_safe_sentry_test_and_scrubbing_are_present():
    assert 'for field in ("request", "user", "breadcrumbs", "extra", "contexts")' in WEB
    assert 'send_default_pii=False' in WEB
    assert 'include_local_variables=False' in WEB
    assert '/api/admin/error-monitoring/test' in WEB
    assert 'symptosense_admin_monitoring_test' in WEB
    assert 'error_monitoring' in READY
    assert 'testErrorMonitoring()' in DASH


def test_research_study_version_can_be_frozen_and_written_to_records():
    assert 'research_study_freezes' in STUDY
    assert 'algorithm_signature' in STUDY
    assert 'UNFROZEN-CHANGED' in STUDY
    assert 'research_study_version' in PRIV
    assert 'research_app_version' in PRIV
    assert '/api/admin/research-study/freeze' in WEB
    assert 'Research Study Version' in EXPORT
    assert 'freezeResearchStudy()' in DASH


def test_release_candidate_is_feature_frozen():
    assert versioning.APP_VERSION == __import__("release_candidate").APP_VERSION
    assert versioning.RC_ID == __import__("release_candidate").RC_ID
    assert 'FEATURE_FREEZE' in RC
    assert 'release_candidate' in READY


def test_technical_verification_store_contains_no_identity_or_health_columns():
    assert 'production_verifications' in VERIFY
    for forbidden in ('email TEXT', 'symptoms TEXT', 'medication TEXT', 'user_id INTEGER', 'name TEXT'):
        assert forbidden not in VERIFY
