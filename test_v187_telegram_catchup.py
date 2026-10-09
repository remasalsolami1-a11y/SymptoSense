import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
web = source_bundle.webapp_text()
mail = (ROOT / "medication_email.py").read_text(encoding="utf-8")
tg = (ROOT / "medication_telegram.py").read_text(encoding="utf-8")


def test_grace_window_is_configurable_and_defaults_to_30_minutes():
    assert 'MED_REMINDER_GRACE_SECONDS' in mail
    assert '"1800"' in mail
    assert 'delta >= grace_seconds' in mail


def test_test_message_endpoint_and_ui_exist():
    assert '/api/meds/telegram/test' in web
    assert 'telegramTestBtn' in web
    assert 'testTelegramNow' in web
    assert 'def send_test(user_id)' in tg


def test_plain_start_wakes_delivery_worker():
    block = web[web.index('if not arg:'):web.index('result = medication_telegram.handle_start')]
    assert '_start_medication_reminder_worker_once()' in block
    assert '_kick_medication_delivery_now()' in block
