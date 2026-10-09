import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()
EMAIL = (ROOT / "medication_email.py").read_text(encoding="utf-8")
EMAIL_JOB = (ROOT / "medication_email_job.py").read_text(encoding="utf-8")
READY = (ROOT / "production_readiness.py").read_text(encoding="utf-8")
BACKUP = (ROOT / "backup_restore.py").read_text(encoding="utf-8")
ENV = (ROOT / ".env.example").read_text(encoding="utf-8")
DASH = (ROOT / "dashboard.py").read_text(encoding="utf-8")
SECURITY = (ROOT / "web_security.py").read_text(encoding="utf-8")


def test_sensitive_routes_are_no_store_and_security_headers_hardened():
    assert '"/api/"' in WEB
    assert 'private, no-store, no-cache, must-revalidate, max-age=0' in WEB
    assert 'Cross-Origin-Opener-Policy' in WEB
    assert 'Cross-Origin-Resource-Policy' in WEB
    assert "frame-ancestors 'none'" in SECURITY
    assert 'reject_cross_site_mutations' in WEB
    assert 'Sec-Fetch-Site' in WEB and 'Origin' in WEB


def test_email_reminder_cron_has_cross_process_duplicate_guard():
    assert 'pg_try_advisory_lock' in EMAIL
    assert 'pg_advisory_unlock' in EMAIL
    assert 'med_email_deliveries' in EMAIL
    assert 'send_due_emails' in EMAIL_JOB
    assert 'python medication_email_job.py' in ENV


def test_encrypted_backup_restore_is_real_not_timestamp_only():
    assert 'pg_dump' in BACKUP
    assert 'pg_restore' in BACKUP
    assert 'BACKUP_ENCRYPTION_KEY' in BACKUP
    assert 'RESTORE_TEST_DATABASE_URL must never point to the production database' in BACKUP
    assert 'backup_restore.public_status()' in READY
    assert 'Backup & restore' in READY
    assert 'BACKUP_DIR=/data/backups' in ENV


def test_security_baseline_is_launch_gate():
    assert 'security_baseline' in READY
    assert 'SESSION_COOKIE_SECURE=1' in ENV
    assert 'WEB_SECRET' in READY


def test_destructive_launch_reset_is_locked_by_default():
    assert 'ALLOW_LAUNCH_RESET=0' in ENV
    assert 'launch_reset_disabled' in WEB
    assert 'launch_reset_enabled' in DASH
