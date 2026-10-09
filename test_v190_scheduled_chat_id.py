import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _load_tg():
    fake_db = types.SimpleNamespace(PH='?', USE_POSTGRES=False)
    previous_db = sys.modules.get('db')
    sys.modules['db'] = fake_db
    spec = importlib.util.spec_from_file_location('medication_telegram_v190', ROOT / 'medication_telegram.py')
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    finally:
        if previous_db is None:
            sys.modules.pop('db', None)
        else:
            sys.modules['db'] = previous_db
    return mod


def test_scheduled_delivery_uses_private_link_row_chat_id(monkeypatch):
    tg = _load_tg()
    monkeypatch.setattr(tg, '_row', lambda user_id: {'chat_id': '424242', 'enabled': True})
    monkeypatch.setattr(tg, '_delivery_status', lambda *args: None)
    monkeypatch.setattr(tg, '_record_delivery', lambda *args, **kwargs: None)
    seen = {}
    def fake_send(chat_id, text, taken_url=None, snooze_url=None):
        seen['chat_id'] = chat_id
        return True, 'telegram'
    monkeypatch.setattr(tg, '_send_message', fake_send)

    result = tg.send_due(7, 11, '2026-09-26', '23:55', 'Medicine', '1', 'https://x/t', 'https://x/s')
    assert result['sent'] is True
    assert seen['chat_id'] == '424242'


def test_public_status_still_does_not_expose_chat_id():
    text = (ROOT / 'medication_telegram.py').read_text(encoding='utf-8')
    status_block = text[text.index('def status(user_id)'):text.index('def create_connect_link')]
    assert '"chat_id":' not in status_block
