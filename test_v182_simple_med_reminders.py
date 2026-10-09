import source_bundle
from pathlib import Path

ROOT=Path(__file__).resolve().parent
WEB=source_bundle.webapp_text()
EMAIL=(ROOT/'medication_email.py').read_text(encoding='utf-8')
TG=(ROOT/'medication_telegram.py').read_text(encoding='utf-8')

def meds_chunk():
    a=WEB.index('def meds_page():')
    b=WEB.find('\ndef ',a+20)
    return WEB[a:b]

def test_meds_ui_is_simple_and_csp_safe():
    c=meds_chunk()
    assert 'name="deliveryChannel"' in c
    assert 'value="email" checked' in c
    assert 'value="telegram"' in c
    assert 'id="telegramUsername"' in c
    for attr in ('onclick=','onchange=','onsubmit=','oninput=','onkeydown='):
        assert attr not in c

def test_api_saves_channel_and_username():
    assert 'info = medication_telegram.prepare_username' in WEB
    assert 'delivery_channel:deliveryChannel' in WEB
    assert 'telegram_username:deliveryChannel' in WEB

def test_storage_has_channel():
    assert 'delivery_channel' in EMAIL
    assert 'pending_username' in TG
    assert 'def prepare_username' in TG
    assert 'username_mismatch' in TG

def test_delivery_is_selected_channel_with_email_fallback_before_activation():
    assert 'channel == "telegram"' in EMAIL
    assert 'provider="telegram"' in EMAIL
    assert 'email_fallback' in EMAIL
