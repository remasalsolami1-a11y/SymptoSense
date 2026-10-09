import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()
EMAIL = (ROOT / 'medication_email.py').read_text(encoding='utf-8')
SW = (ROOT / 'service-worker.js').read_text(encoding='utf-8')
ENV = (ROOT / '.env.example').read_text(encoding='utf-8')
PROC = (ROOT / 'Procfile').read_text(encoding='utf-8')


def test_public_sitemap_is_strict_and_language_prefixed():
    block = WEB.split('@app.route("/sitemap.xml")', 1)[1].split('@app.route("/api/stats")', 1)[0]
    for page in ('"/health-library"', '"/about"', '"/how-we-work"', '"/privacy"', '"/terms"'):
        assert page in block
    for forbidden in ('admin', 'safeid', 'profile', 'health-record', 'competition-dashboard', 'share/', 'reset-password'):
        assert forbidden not in block
    assert '"/ar/"' in block and '"/en/"' in block
    assert 'hreflang="ar"' in block and 'hreflang="en"' in block and 'hreflang="x-default"' in block


def test_robots_explicitly_blocks_sensitive_and_internal_paths():
    block = WEB.split('@app.route("/robots.txt")', 1)[1].split('@app.route("/sitemap.xml")', 1)[0]
    for path in ('/admin/', '/safeid/', '/share/', '/reset-password/', '/verify-email/', '/profile', '/health-record', '/family', '/settings', '/manage', '/memory', '/competition'):
        assert path in block


def test_competition_legacy_urls_are_admin_only_redirects():
    block = WEB.split('@app.route("/competition-dashboard")', 1)[1].split('@app.route("/innovation-lab")', 1)[0]
    assert '@app.route("/competition")' in block
    assert '_admin_page_gate("/admin/competition-dashboard")' in block
    assert 'redirect(url_for("admin_competition_dashboard"), code=301)' in block
    assert 'X-Robots-Tag' in block and 'noindex' in block


def test_medication_web_push_is_removed_from_active_site():
    assert '/api/push/' not in WEB
    assert '/api/admin/push/' not in WEB
    assert 'Notification.requestPermission' not in WEB
    assert 'PushManager' not in WEB
    assert "addEventListener('push'" not in SW
    assert 'notificationclick' not in SW


def test_email_reminder_engine_and_cron_contract():
    assert 'CREATE TABLE IF NOT EXISTS medication_reminders' in EMAIL
    assert 'CREATE TABLE IF NOT EXISTS med_email_deliveries' in EMAIL
    assert 'def send_due_emails' in EMAIL
    assert '⏰ حان وقت جرعة' in EMAIL
    assert 'تم تناوله' in EMAIL and 'تأجيل 10 دقائق' in EMAIL
    assert 'BREVO_API_KEY=' in ENV and 'RESEND_API_KEY=' in ENV
    assert 'python medication_email_job.py' in ENV
    assert '* * * * *' in ENV
    assert 'push_worker.py' not in PROC
