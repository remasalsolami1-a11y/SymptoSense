"""V243: final welcome / language-selection page (agreed design)."""
import source_bundle
import re
from pathlib import Path

WEB = source_bundle.webapp_text()


def _welcome_block():
    s = WEB.index('def welcome_page():')
    e = WEB.index('\ndef home_page():', s)
    return WEB[s:e]


def _style_block():
    b = _welcome_block()
    s = b.index('<style id="ss-welcome-layout-v7">')
    return b[s:b.index('</style>', s)]


def test_terms_and_privacy_are_real_links_with_big_tap_targets():
    b = _welcome_block()
    assert '<nav class="first-lang-legal"' in b
    assert '<a href="__TERMS_URL__">' in b and '<a href="__PRIVACY_URL__">' in b
    assert '_localized_url("/terms", ui_lang)' in WEB and '_localized_url("/privacy", ui_lang)' in WEB
    assert 'onclick' not in b[b.index('<nav class="first-lang-legal"'):b.index('</nav>', b.index('<nav class="first-lang-legal"'))]
    css = _style_block()
    assert 'min-height:44px!important' in css and 'min-width:44px!important' in css
    assert '.first-lang-legal a:focus-visible' in css


def test_no_font_below_12px_on_welcome_page():
    css = _style_block()
    sizes = [float(x) for x in re.findall(r'font-size:([\d.]+)px', css)]
    sizes += [float(x) for x in re.findall(r'font:[^;{}]*?(\d+(?:\.\d+)?)px/', css)]
    assert sizes and min(sizes) >= 12, sorted(set(sizes))


def test_simple_mobile_scroll_and_safe_area():
    css = _style_block()
    assert 'min-height:100dvh!important' in css
    assert 'env(safe-area-inset-top)' in css and 'env(safe-area-inset-bottom)' in css
    assert 'overflow-y:hidden' not in css and 'overflow:hidden' not in css
    assert 'scroll-snap' not in css
    # No fake phone bezel from the reference mockups.
    assert 'border:7px' not in css


def test_language_badges_are_not_country_codes_or_flag_emoji():
    b = _welcome_block()
    assert '>ع</span>' in b and '>EN</span>' in b
    assert '>SA</span>' not in b and '>GB</span>' not in b
    assert not re.search('[\U0001F1E6-\U0001F1FF]', b)


def test_single_language_per_block_and_fonts():
    css = _style_block()
    assert "'Tajawal'" in css and "'Poppins'" in css
    assert 'IBM Plex' not in css
    assert 'data-copy="ar"' in _welcome_block() and 'data-copy="en"' in _welcome_block()


def test_decorative_art_is_aria_hidden_svg_only():
    b = _welcome_block()
    assert b.count('class="fl-art') == 2
    assert 'aria-hidden="true" focusable="false"' in b
    assert 'first-lang-plus' not in b


def test_language_links_keep_server_targets():
    b = _welcome_block()
    assert 'data-lang="ar" href="__LANG_AR_TARGET__"' in b
    assert 'data-lang="en" href="__LANG_EN_TARGET__"' in b
    assert 'id="languageOptions"' in b and 'id="languageTitle"' in b


def test_legal_links_use_high_contrast_color():
    # #174E88 keeps >= 4.5:1 even over the light-blue wave artwork at the bottom.
    assert 'first-lang-legal a{color:#174E88!important;' in _style_block()
