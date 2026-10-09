"""V269: the language screen shows Arabic + English together; browser language only orders the cards."""
import re
from pathlib import Path

import source_bundle

WEB = source_bundle.webapp_text()
CSS = (Path(__file__).resolve().parent / "inline_assets" / "WELCOME_BILINGUAL_CSS.css").read_text(encoding="utf-8")


def _block():
    s = WEB.index('def welcome_page():')
    return WEB[s:WEB.index('\ndef home_page():', s)]


def test_both_languages_are_visible_together_in_css():
    assert 'first-lang-headline-ar,html body.ss-welcome-page .first-lang-headline-en' in CSS
    assert 'display:block!important' in CSS
    assert 'none' not in re.sub(r'transform:none!important', '', CSS).replace('content:none!important', '')


def test_required_bilingual_copy_and_cards():
    b = _block()
    for t in ('اختر لغتك للبدء', 'Choose your language', 'إرشاد لا تشخيص', 'Guidance, not diagnosis',
              'خصوصيتك أولويتنا', 'Your privacy matters', 'Reference information',
              'دون تقديم تشخيص طبي', 'not a medical diagnosis'):
        assert t in b, t
    assert b.count('href="__LANG_AR_TARGET__"') == 1 and b.count('href="__LANG_EN_TARGET__"') == 1


def test_no_unproven_claims_on_the_language_screen():
    b = _block()
    for bad in ('موثوقة', 'معتمدة', 'محمية دائمًا', 'Trusted information', 'always protected', 'accredited'):
        assert bad not in b, bad


def test_cards_keep_44px_targets_and_own_direction_and_arrow():
    assert 'min-height:66px!important' in CSS
    assert '.first-lang-option[data-lang="ar"]{direction:rtl!important;}' in CSS
    assert '.first-lang-option[data-lang="en"]{direction:ltr!important;}' in CSS
    assert '[data-lang="ar"] .lang-arrow svg{transform:scaleX(-1)!important;}' in CSS


def test_browser_language_only_orders_cards_and_nothing_is_forced():
    b = _block()
    assert 'if not is_ar:' in b and "data-lang=\"en\"')" in b
    assert 'request.accept_languages.best_match(["ar", "en"])' in b
    # both options remain plain links (server targets), no script chooses for the user
    assert 'data-lang="ar" href="__LANG_AR_TARGET__"' in b and 'data-lang="en" href="__LANG_EN_TARGET__"' in b


def test_preview_is_smaller_than_text_column_and_still_desktop_only():
    assert 'max-width:430px!important;height:370px!important' in CSS
    assert CSS.count('fl-preview') == 1 and '@media (min-width:980px)' in CSS


def test_font_sizes_never_below_11px():
    sizes = [float(x) for x in re.findall(r'font-size:([\d.]+)px', CSS)]
    assert sizes and min(sizes) >= 11, sorted(set(sizes))
