"""V272: mobile overlap fixes (home hero result card vs trust row, possible-conditions rows, bottom-nav safe area)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CSS = (ROOT / "polish_css_v249.py").read_text(encoding="utf-8")
FRAME = (ROOT / "inline_assets" / "PAGE_FRAME.html").read_text(encoding="utf-8")
BASE = (ROOT / "inline_assets" / "BASE_CSS.css").read_text(encoding="utf-8")


def _hero_block():
    s = CSS.index('/* V272 home hero')
    return CSS[s:CSS.index('/* V272 possible-conditions')]


def test_hero_demo_has_no_fixed_height_and_card_is_in_flow():
    b = _hero_block()
    assert '.ss-hero-demo{height:auto!important;min-height:0!important;padding-top:350px!important' in b
    assert '.ss-result-card{position:relative!important;top:auto!important' in b
    assert 'grid-template-columns:minmax(0,1fr)!important' in b          # no grid blow-out (clipped text on the left)
    assert '.ss-hero-kicker' in b and 'white-space:normal!important' in b


def test_trust_indicators_are_an_independent_in_flow_container():
    b = _hero_block()
    row = b[b.index('.ss-trust-row{position:relative!important'):].split('\n')[0]
    assert 'position:relative!important' in row and 'grid-template-columns:repeat(3,minmax(0,1fr))!important' in row
    assert 'position:absolute' not in row and 'margin:16px 0 0!important' in row
    assert '.ss-trust-item{grid-column:auto!important' in b


def test_rtl_and_ltr_arrows_in_the_result_mock():
    b = _hero_block()
    assert 'html[dir="ltr"] body.ss-home-page.ss-home-page .ss-result-card' in b and 'transform:scaleX(-1)' in b


def test_possible_conditions_rows_are_flex_rows_with_wrapping_names():
    s = CSS.index('/* V272 possible-conditions')
    b = CSS[s:]
    assert '.ss-condition-head{display:flex!important;flex-direction:row!important;flex-wrap:nowrap!important' in b
    assert '.ss-condition-name{flex:1 1 0!important;min-width:0!important;overflow-wrap:anywhere!important' in b
    assert '.ss-match{flex:0 0 auto!important' in b


def test_bottom_nav_safe_area_for_content_and_footer_up_to_the_nav_breakpoint():
    assert 'viewport-fit=cover' in FRAME
    assert 'padding-bottom: calc(6px + var(--safe-bottom))' in BASE and '--safe-bottom: env(safe-area-inset-bottom' in BASE
    assert '@media (max-width:1180px){html body .footer{padding-bottom:calc(var(--bnav-h,64px) + var(--safe-bottom,0px) + 20px)!important}}' in CSS
