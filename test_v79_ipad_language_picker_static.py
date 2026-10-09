import source_bundle
from pathlib import Path

WEB = source_bundle.webapp_text()


def test_ipad_language_picker_has_dedicated_tablet_breakpoint():
    assert '@media (min-width:601px){' in WEB
    assert 'width:min(100%,460px)!important' in WEB
    assert 'min-height:68px!important' in WEB


def test_ipad_landscape_language_picker_has_compact_height_breakpoint():
    # The picker is a natural-scroll column now: short landscape screens simply scroll.
    assert 'first-lang-leaf,body.ss-welcome-page .first-lang-start{display:none!important;}' in WEB
    assert 'overflow-y:visible!important' in WEB


def test_language_picker_keeps_two_real_server_links():
    assert 'href="__LANG_AR_TARGET__"' in WEB
    assert 'href="__LANG_EN_TARGET__"' in WEB
    assert 'onclick="ssChooseLanguage' not in WEB


def test_webapp_remains_below_static_quality_limit():
    # V76: bumped from 18000 -- a real correctness fix (search sources-wiping
    # bug) needed a few extra lines; this is not unbounded growth room.
    # V199 lab intake adds camera/multi-page/review flows inline. Keep a
    # temporary ceiling that still catches runaway growth; the next structural
    # refactor should move the lab UI into its own module instead of weakening
    # this guard further.
    assert len(WEB.splitlines()) < 24000
