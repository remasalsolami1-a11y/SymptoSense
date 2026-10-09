import importlib.util
import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _load_tg():
    fake_db = types.SimpleNamespace(PH='?', USE_POSTGRES=False)
    previous_db = sys.modules.get('db')
    sys.modules['db'] = fake_db
    spec = importlib.util.spec_from_file_location('medication_telegram_v189', ROOT / 'medication_telegram.py')
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    finally:
        if previous_db is None:
            sys.modules.pop('db', None)
        else:
            sys.modules['db'] = previous_db
    return mod


class Resp:
    def __init__(self, ok, code, body):
        self.ok = ok
        self.status_code = code
        self._body = body
    def json(self):
        return self._body


def test_scheduled_message_retries_without_inline_buttons(monkeypatch):
    tg = _load_tg()
    os.environ['TELEGRAM_BOT_TOKEN'] = '123:abc'
    calls = []

    def fake_post(url, json, timeout):
        calls.append(json)
        if len(calls) == 1:
            assert 'reply_markup' in json
            return Resp(False, 400, {'ok': False, 'description': 'Bad Request: BUTTON_URL_INVALID'})
        assert 'reply_markup' not in json
        return Resp(True, 200, {'ok': True})

    monkeypatch.setattr(tg.requests, 'post', fake_post)
    ok, reason = tg._send_message('42', 'dose reminder', 'https://example.com/taken', 'https://example.com/snooze')
    assert ok is True
    assert reason == 'telegram_plain_fallback'
    assert len(calls) == 2


def test_plain_test_message_remains_single_request(monkeypatch):
    tg = _load_tg()
    os.environ['TELEGRAM_BOT_TOKEN'] = '123:abc'
    calls = []

    def fake_post(url, json, timeout):
        calls.append(json)
        return Resp(True, 200, {'ok': True})

    monkeypatch.setattr(tg.requests, 'post', fake_post)
    ok, reason = tg._send_message('42', 'plain test')
    assert ok is True
    assert reason == 'telegram'
    assert len(calls) == 1
    assert 'reply_markup' not in calls[0]


def test_cross_midnight_catchup_logic_present():
    text = (ROOT / 'medication_email.py').read_text(encoding='utf-8')
    assert 'previous_due = local_due - timedelta(days=1)' in text
    assert 'occurrence_date = local_due.date()' in text
