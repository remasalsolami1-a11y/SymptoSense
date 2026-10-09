import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEBAPP = source_bundle.webapp_text()
TELEGRAM = (ROOT / "medication_telegram.py").read_text(encoding="utf-8")


def test_plain_start_gets_help_not_invalid_token():
    assert 'if not arg:' in WEBAPP
    assert 'medication_telegram.send_start_help' in WEBAPP
    assert 'return jsonify({"ok": True, "handled": "start_help"})' in WEBAPP


def test_help_message_explains_site_linking():
    assert 'def send_start_help' in TELEGRAM
    assert 'لربط Telegram بتذكيرات الأدوية' in TELEGRAM
    assert 'لن يتم ربط الحساب بدون رابط الربط الخاص بك' in TELEGRAM


def test_real_deep_link_still_uses_handle_start():
    assert 'medication_telegram.handle_start' in WEBAPP
    assert 'token.startswith("meds_")' in TELEGRAM


def test_link_errors_are_specific():
    assert 'reason == "expired_token"' in TELEGRAM
    assert 'reason == "invalid_token"' in TELEGRAM
    assert 'reason == "username_mismatch"' in TELEGRAM
