import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()


def _welcome_block():
    start = WEB.index('def welcome_page():')
    end = WEB.index('\ndef home_page():', start)
    return WEB[start:end]


def test_v232_reference_layout_content():
    block = _welcome_block()
    for token in [
        'first-lang-logo-mark', 'SymptoSense', 'Your Health, Smarter',
        'افهم أعراضك<em>واعرف خطوتك التالية</em>',
        'Understand your symptoms<em>and know your next step</em>',
        '>ع</span>', '>EN</span>', '>SA</span>' if False else 'first-lang-chip',
        'إرشاد غير تشخيصي', 'Not a diagnosis',
    ]:
        assert token in block, token
    assert '>SA</span>' not in block


def test_v232_removes_welcome_disclaimer_and_about_link():
    block = _welcome_block()
    assert 'SymptoSense يقدم معلومات وإرشادًا أوليًا ولا يشخّص الحالات الطبية.' not in block
    assert 'SymptoSense provides information and initial guidance and does not diagnose medical conditions.' not in block
    assert 'href="/about"' not in block
    assert 'من نحن / About' not in block


def test_v232_legal_links_are_real_routes():
    block = _welcome_block()
    assert '<a href="__TERMS_URL__">' in block
    assert '<a href="__PRIVACY_URL__">' in block
    assert '<span data-copy="ar" lang="ar" dir="rtl">الشروط</span>' in block
    assert '<span data-copy="en" lang="en">Terms</span>' in block
    assert '<span data-copy="ar" lang="ar" dir="rtl">الخصوصية</span>' in block
    assert '<span data-copy="en" lang="en">Privacy</span>' in block


def test_v232_mobile_scroll_and_safe_area():
    block = _welcome_block()
    for token in [
        'min-height:100dvh!important',
        'env(safe-area-inset-top)', 'env(safe-area-inset-bottom)',
        '@media (max-width:340px)', '@media (min-width:601px)',
    ]:
        assert token in block, token
    # Simple natural page scroll: never lock the page height or hide vertical overflow.
    assert 'overflow-y:hidden' not in block
    assert 'overflow:hidden' not in block


def test_v232_language_cards_keep_direct_navigation():
    block = _welcome_block()
    assert 'data-lang="ar" href="__LANG_AR_TARGET__"' in block
    assert 'data-lang="en" href="__LANG_EN_TARGET__"' in block
