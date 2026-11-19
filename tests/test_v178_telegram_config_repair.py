import importlib


def test_bot_identity_prefers_getme(monkeypatch):
    import medication_telegram
    importlib.reload(medication_telegram)
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'token123')
    monkeypatch.setenv('TELEGRAM_BOT_USERNAME', 'Wrong_Name')
    monkeypatch.setenv('TELEGRAM_WEBHOOK_SECRET', 'secret123')

    class Resp:
        ok = True
        status_code = 200
        content = b'{}'
        def json(self):
            return {'ok': True, 'result': {'username': 'SymptoSense_Bot'}}
    monkeypatch.setattr(medication_telegram.requests, 'get', lambda *a, **k: Resp())
    cfg = medication_telegram.configuration_status(force_verify=True)
    assert cfg['configured'] is True
    assert cfg['bot_username'] == 'SymptoSense_Bot'
    assert cfg['bot_verified'] is True


def test_env_username_keeps_config_ready_on_transient_getme_failure(monkeypatch):
    import medication_telegram
    importlib.reload(medication_telegram)
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'token123')
    monkeypatch.setenv('TELEGRAM_BOT_USERNAME', 'SymptoSense_Bot')
    monkeypatch.setenv('TELEGRAM_WEBHOOK_SECRET', 'secret123')
    def fail(*a, **k):
        raise RuntimeError('network')
    monkeypatch.setattr(medication_telegram.requests, 'get', fail)
    cfg = medication_telegram.configuration_status(force_verify=True)
    assert cfg['configured'] is True
    assert cfg['bot_username'] == 'SymptoSense_Bot'
    assert cfg['bot_verified'] is False
    assert cfg['bot_check_error'] == 'getme_request_failed'


def test_missing_secret_is_specific(monkeypatch):
    import medication_telegram
    importlib.reload(medication_telegram)
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'token123')
    monkeypatch.setenv('TELEGRAM_BOT_USERNAME', 'SymptoSense_Bot')
    monkeypatch.delenv('TELEGRAM_WEBHOOK_SECRET', raising=False)
    def fail(*a, **k):
        raise RuntimeError('network')
    monkeypatch.setattr(medication_telegram.requests, 'get', fail)
    cfg = medication_telegram.configuration_status(force_verify=True)
    assert cfg['configured'] is False
    assert cfg['config_error'] == 'missing_webhook_secret'


def test_meds_ui_no_longer_collapses_all_failures_to_not_configured():
    import source_bundle
    text = source_bundle.webapp_text()
    assert 'تعذر التحقق من حالة Telegram الآن' in text
    assert 'Telegram جاهز، لكن تعذر قراءة حالة الربط' in text
    assert "config_error==='missing_webhook_secret'" in text
