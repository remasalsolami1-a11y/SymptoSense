import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEBAPP = source_bundle.webapp_text()
EMAIL = (ROOT / 'medication_email.py').read_text(encoding='utf-8')


def test_successful_link_kicks_due_delivery_immediately():
    needle = 'medication_telegram.send_link_confirmation(str(chat.get("id")))'
    i = WEBAPP.index(needle)
    block = WEBAPP[i:i+900]
    assert '_start_medication_reminder_worker_once()' in block
    assert '_kick_medication_delivery_now()' in block


def test_save_and_edit_ensure_worker_is_started():
    assert WEBAPP.count('_start_medication_reminder_worker_once()') >= 4
    assert 'payload = service.create_plan(uid, request.get_json(silent=True))\n            _start_medication_reminder_worker_once()\n            _kick_medication_delivery_now()' in WEBAPP
    assert 'payload = service.update_plan(uid, pid, request.get_json(silent=True))\n        _start_medication_reminder_worker_once()\n        _kick_medication_delivery_now()' in WEBAPP


def test_email_fallback_does_not_block_later_telegram_copy():
    assert 'email_delivery_status = _delivery_status(uid, pid, log_date, log_time)' in EMAIL
    assert 'if channel == "email" and email_delivery_status == "sent"' in EMAIL
    assert 'if channel == "telegram":\n                    tg = medication_telegram.send_due' in EMAIL
    assert 'if email_delivery_status == "sent":\n                        skipped += 1\n                        continue' in EMAIL


def test_snooze_uses_same_separate_delivery_logic():
    assert 'email_delivery_status = _delivery_status(uid, pid, str(log_date), delivery_time)' in EMAIL
    assert 'if not delivered and email_delivery_status == "sent"' in EMAIL
