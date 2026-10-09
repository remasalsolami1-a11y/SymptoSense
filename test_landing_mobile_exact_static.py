import source_bundle
from pathlib import Path

WEBAPP = Path(__file__).resolve().parent / 'webapp.py'
TEXT = source_bundle.webapp_text()


def _welcome_block():
    start = TEXT.index('def welcome_page():')
    end = TEXT.index('\ndef home_page():', start)
    return TEXT[start:end]


def test_mobile_landing_uses_current_competition_structure():
    block = _welcome_block()
    required = [
        'first-lang-logo-mark',
        'Your Health, Smarter',
        'افهم أعراضك<em>واعرف خطوتك التالية</em>',
        'Understand your symptoms<em>and know your next step</em>',
        '<span data-copy="ar" lang="ar" dir="rtl">اختر لغتك للبدء</span>',
        '<span data-copy="en" lang="en">Choose your language</span>',
        '>ع</span>',
        '>EN</span>',
        'first-lang-benefits',
        'href="__PRIVACY_URL__"',
        'href="__TERMS_URL__"',
    ]
    for token in required:
        assert token in block, token
    assert '>SA</span>' not in block
    assert 'href="/about"' not in block
    assert 'SymptoSense يقدم معلومات وإرشادًا أوليًا ولا يشخّص الحالات الطبية.' not in block
    # Language selection is the primary action; the redundant Get Started button stays removed.
    assert '<button type="button" class="first-lang-start"' not in block


def test_mobile_landing_reference_palette_and_shapes():
    required = [
        '--lp-navy:#0D3B73',
        '--lp-blue:#248EF3',
        '--lp-cyan:#56C6ED',
        'border-radius:999px',
        'grid-template-columns:repeat(2,minmax(0,1fr))',
        'grid-template-columns:repeat(3,minmax(0,1fr))',
        '@media(max-width:480px)',
        '@media(max-width:480px) and (max-height:720px)',
    ]
    for token in required:
        assert token in TEXT, token


def test_mobile_landing_is_safari_safe_and_compact():
    block = _welcome_block()
    assert 'min-height:100dvh!important' in block
    assert "scrollIntoView({behavior:'smooth',block:'center'})" not in block
    assert '<meta name="theme-color" content="#F8FBFF">' in block
    assert "history.scrollRestoration = 'manual'" in block
    assert 'body.ss-welcome-page .ss-bnav' in TEXT
    # The landing is structurally bare now: hidden app chrome is not shipped in its HTML.
    page_start = TEXT.index('def _page(')
    page_end = TEXT.index('\n\n# ---------------------------------------------------------------- landing', page_start)
    page_block = TEXT[page_start:page_end]
    assert 'if bare:' in page_block
    assert '<body>{body}</body>' in page_block


def test_landing_language_behaviour_preserved():
    block = _welcome_block()
    for token in [
        'data-lang="ar" href="__LANG_AR_TARGET__"',
        'data-lang="en" href="__LANG_EN_TARGET__"',
        'ar_target = _localized_target_from_legacy(next_target, "ar")',
        'en_target = _localized_target_from_legacy(next_target, "en")',
    ]:
        assert token in block, token
    assert 'onclick="ssChooseLanguage' not in block
    assert "document.querySelectorAll('.first-lang-option[data-lang]')" not in block


def test_mobile_landing_legal_links_are_responsive():
    block = _welcome_block()
    assert 'first-lang-legal' in block
    assert 'grid-template-columns:repeat(3,minmax(0,1fr))!important' in block
    assert 'env(safe-area-inset-bottom)' in block
    assert 'min-height:44px!important' in block
