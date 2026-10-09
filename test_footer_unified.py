"""V271: ONE footer component, restructured in place (logo + slogan, 3 columns, links row, divider, credits)."""
import re
from pathlib import Path

import source_bundle

WEB = source_bundle.webapp_text()
CSS = (Path(__file__).resolve().parent / "polish_css_v249.py").read_text(encoding="utf-8")


def _footer():
    s = WEB.index('def _footer():')
    return WEB[s:WEB.index('def _page(', s)]


def test_single_footer_component_with_required_order():
    f = _footer()
    order = ['class="f-inner"', 'class="f-brand"', 'class="f-tag"', 'class="f-grid"', 'class="f-links"', 'class="f-sep"', 'class="f-love"', 'class="f-copy"']
    pos = [f.index(t) for t in order]
    assert pos == sorted(pos), pos
    assert f.count('class="f-sec"') == 3
    assert WEB.count('def _footer():') == 1 and WEB.count('class="footer"') == 1


def test_original_site_links_and_logo_are_used():
    f = _footer()
    for href in ('href="/privacy"', 'href="/terms"', 'href="/sources"', 'href="/about"'):
        assert href in f, href
    assert 'src="/brand-icon.svg"' in f and '"/admin"' in f


def test_layout_css_three_columns_central_container_and_stacked_mobile():
    for tok in ('.f-inner{max-width:1040px', 'grid-template-columns:repeat(3,minmax(0,1fr))!important',
                '@media (max-width:600px)', 'grid-template-columns:1fr!important', 'min-height:44px', '.f-sep{border:0;height:1px'):
        assert tok in CSS, tok
    # nothing essential is hidden on phones
    mobile = CSS[CSS.index('@media (max-width:600px){html body .footer'):]
    assert 'display:none' not in mobile.split('\n')[0]


def test_credit_text_is_unchanged():
    assert 'footer_love' in _footer() and 'footer_copy_full' in _footer()
