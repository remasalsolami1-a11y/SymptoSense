import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()

def test_no_browser_notification_permission_flow_for_medications():
    assert "Notification.requestPermission" not in WEB
    assert "pushManager.subscribe" not in WEB
    assert "enablePushBtn" not in WEB

def test_medication_email_copy_is_visible():
    assert "تُرسل تذكيرات الجرعات تلقائيًا إلى بريد حسابك المسجّل" in WEB
    assert "لا يلزم أي إعداد إضافي" in WEB
