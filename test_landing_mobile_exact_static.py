from pathlib import Path

WEBAPP = Path(__file__).resolve().parents[1] / 'webapp.py'
TEXT = WEBAPP.read_text(encoding='utf-8')


def _welcome_block():
    start = TEXT.index('def welcome_page():')
    end = TEXT.index('\ndef home_page():', start)
    return TEXT[start:end]


def test_mobile_landing_uses_current_competition_structure():
    block = _welcome_block()
    required = [
        'first-lang-trust',
        'first-lang-logo-mark',
        'Your Health, Smarter',
        'افهم أعراضك.<br>اعرف خطوتك التالية.',
        'Understand your symptoms.<br>Know your next step.',
        '<span lang="ar" dir="rtl">اختر اللغة</span>',
        '<span lang="en">Choose language</span>',
        '🇸🇦',
        '🇬🇧',
        'first-lang-benefits',
        'معلومات موثوقة',
        'سهل الاستخدام',
        'للتوعية فقط',
        'first-lang-leaf',
    ]
    for token in required:
        assert token in block, token
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
    assert 'min-height:100svh' in TEXT
    assert 'white-space:normal!important' in TEXT
    assert "scrollIntoView({behavior:'smooth',block:'center'})" not in block
    assert '<meta name="theme-color" content="#F8FCFF">' in block
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
        "ssChooseLanguage('ar',this)",
        "ssChooseLanguage('en',this)",
        "document.cookie = 'lang=' + lang",
        "localStorage.setItem('ss_lang', lang)",
        "window.location.href = SS_NEXT_PAGE || '/home'",
    ]:
        assert token in block, token
