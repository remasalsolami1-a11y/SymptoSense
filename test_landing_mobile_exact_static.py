from pathlib import Path

WEBAPP = Path(__file__).resolve().parents[1] / 'webapp.py'
TEXT = WEBAPP.read_text(encoding='utf-8')


def test_mobile_landing_uses_reference_structure():
    required = [
        'first-lang-trust',
        'first-lang-logo-mark',
        'Your Health, Smarter',
        'افهم أعراضك.<br>اعرف خطوتك التالية.',
        'Understand your symptoms.<br>Know your next step.',
        'first-lang-start',
        'اختر اللغة / <span lang="en">Choose language</span>',
        '🇸🇦',
        '🇬🇧',
        'first-lang-benefits',
        'معلومات موثوقة',
        'سهل الاستخدام',
        'للتوعية فقط',
        'مدعومة بمصادر طبية موثوقة',
        'Supported by trusted medical sources',
        'first-lang-leaf',
    ]
    for token in required:
        assert token in TEXT, token


def test_mobile_landing_reference_palette_and_shapes():
    required = [
        '--lp-navy:#0D3B73',
        '--lp-blue:#248EF3',
        '--lp-cyan:#56C6ED',
        'border-radius:999px',
        'linear-gradient(95deg,#2389EF 0%,#4CB2F4 100%)',
        'grid-template-columns:repeat(2,minmax(0,1fr))',
        'grid-template-columns:repeat(3,minmax(0,1fr))',
        '@media(max-width:480px)',
        '@media(max-height:760px) and (max-width:480px)',
    ]
    for token in required:
        assert token in TEXT, token


def test_landing_language_behaviour_preserved():
    for token in [
        "ssChooseLanguage('ar',this)",
        "ssChooseLanguage('en',this)",
        "document.cookie = 'lang=' + lang",
        "localStorage.setItem('ss_lang', lang)",
        "window.location.href = SS_NEXT_PAGE || '/home'",
    ]:
        assert token in TEXT, token
