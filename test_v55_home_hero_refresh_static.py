import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()


def test_v55_brand_and_headline_are_present_without_old_copy():
    assert 'class="ss-hero-brand ss-brand-gradient"' in WEB
    assert '>SymptoSense</div>' in WEB
    assert 'bi("افهم أعراضك واعرف", "Understand your symptoms and")' in WEB
    assert 'bi("خطوتك التالية", "know your next step")' in WEB
    assert 'كل عرض له سياق' not in WEB
    assert 'SymptoSense يساعدك تفهمه' not in WEB


def test_v55_home_hero_has_device_specific_breakpoints():
    assert 'V55 home hero — reference composition + all-device responsive polish' in WEB
    assert '@media (min-width:768px) and (max-width:1180px)' in WEB
    assert '@media (max-width:767px)' in WEB
    assert '@media (max-width:430px)' in WEB
    assert '@media (max-width:350px)' in WEB


def test_v55_phone_hero_stacks_instead_of_becoming_microscopic():
    block = source_bundle.segment('V55 home hero — reference composition + all-device responsive polish')
    assert 'grid-template-columns:1fr!important' in block
    assert 'font-size:clamp(29px,8.4vw,42px)!important' in block
    assert 'grid-template-columns:1fr 1fr!important' in block
    assert 'body.ss-home-page .ss-hero-demo{grid-column:1!important' in block


def test_welcome_screen_uses_same_approved_arabic_tagline():
    assert 'افهم أعراضك<em>واعرف خطوتك التالية</em>' in WEB
    assert 'Understand your symptoms<em>and know your next step</em>' in WEB
