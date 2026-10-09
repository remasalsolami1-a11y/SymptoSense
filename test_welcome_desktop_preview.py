"""V268: desktop language page (CSS-only preview) + contrast / card / arrow / motion tweaks."""
import re

import source_bundle

WEB = source_bundle.webapp_text()


def _block():
    s = WEB.index('def welcome_page():')
    return WEB[s:WEB.index('\ndef home_page():', s)]


def _css():
    b = _block()
    s = b.index('<style id="ss-welcome-layout-v7">')
    return b[s:b.index('</style>', s)]


def _lum(hex_):
    h = hex_.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _ratio(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_secondary_text_color_passes_wcag_aa_on_every_background():
    css = _css()
    body = re.search(r'--fl-body:(#[0-9A-Fa-f]{6})', css).group(1)
    # page gradient ends + the lightest and darkest wave tones drawn behind the bottom text
    for bg in ('#F8FBFF', '#E6F2FC', '#BFDDF7', '#FFFFFF'):
        assert _ratio(body, bg) >= 4.5, (body, bg, _ratio(body, bg))


def test_language_cards_are_larger_with_soft_blue_border_and_clear_focus():
    css = _css()
    assert 'min-height:76px!important' in css
    assert 'border:2px solid var(--fl-card-line)!important' in css
    assert '.first-lang-option:hover{' in css and '.first-lang-option:focus-visible{outline:3px solid #174E88!important' in css


def test_arrow_is_one_svg_mirrored_by_css_on_the_rtl_page():
    b = _block()
    assert '"‹" if is_ar else "›"' not in b
    assert 'M9 5l7 7-7 7' in b
    css = _css()
    assert '.first-lang--ar .first-lang-option .lang-arrow svg{transform:scaleX(-1);}' in css


def test_preview_is_decorative_desktop_only_and_motion_is_optional():
    b, css = _block(), _css()
    assert '<div class="fl-preview" aria-hidden="true">' in b
    pv = b[b.index('<div class="fl-preview"'):b.index('</section>', b.index('<div class="fl-preview"'))]
    # nothing focusable or linked inside the decorative preview
    assert '<a ' not in pv and '<button' not in pv and 'tabindex' not in pv and '<img' not in pv
    assert 'body.ss-welcome-page .fl-preview{display:none;}' in css
    assert '@media (min-width:980px)' in css
    assert '@media (min-width:980px) and (prefers-reduced-motion:no-preference)' in css
    assert 'animation:none!important' in css
    # no animation outside the desktop + no-reduced-motion block
    outside = css.replace(css[css.index('@media (min-width:980px) and (prefers-reduced-motion:no-preference)'):css.index('@keyframes flFloat')], '')
    assert 'animation:flFloat' not in outside


def test_preview_uses_real_section_names_in_both_languages_and_no_trust_claims():
    b = _block()
    for token in ('تحليل الأعراض', 'Symptom analysis', 'الأدوية', 'Medications', 'Tests &amp; CBC', 'الحاسبات الصحية', 'Health calculators'):
        assert token in b, token
    # unreviewed-claims guard: the page must not claim approved/accredited sources
    for bad in ('معتمدة', 'accredited', 'clinically approved', 'medically approved'):
        assert bad not in b, bad
