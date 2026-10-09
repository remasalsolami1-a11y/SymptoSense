import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()
EMAIL = (ROOT / "medication_email.py").read_text(encoding="utf-8")
SW = (ROOT / "service-worker.js").read_text(encoding="utf-8")

def test_medication_reminders_are_email_only():
    assert "تذكيرات الجرعات بالبريد الإلكتروني" in WEB
    assert "Notification.requestPermission" not in WEB
    assert "PushManager" not in WEB
    assert "/api/push/" not in WEB

def test_email_delivery_has_provider_and_deduplication():
    assert "def send_due_emails" in EMAIL
    assert "med_email_deliveries" in EMAIL
    assert "BREVO_API_KEY" in EMAIL and "RESEND_API_KEY" in EMAIL

def test_service_worker_has_no_medication_push_handlers():
    assert "addEventListener('push'" not in SW
    assert "notificationclick" not in SW
