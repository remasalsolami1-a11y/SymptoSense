import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEBAPP = source_bundle.webapp_text()


def test_phone_home_hero_visual_hidden_under_480():
    assert '@media(max-width:480px){.hh{padding:20px 16px!important}.hh-r{display:none!important}' in WEBAPP


def test_home_how_flow_is_2x2_on_regular_phones():
    assert '.ss-how-flow{grid-template-columns:repeat(2,minmax(0,1fr))' in WEBAPP
    assert '@media(max-width:360px)' in WEBAPP


def test_home_does_not_duplicate_community_dashboard_stats():
    block = source_bundle.function_source("home_page")
    assert 'home-community' not in block
    assert '__USER_COUNT__' not in block


def test_community_dashboard_kpis_stay_2x2_on_common_phones():
    assert '@media(max-width:700px){.community-hero{padding:26px 16px}.community-kpis{grid-template-columns:repeat(2,minmax(0,1fr))' in WEBAPP
    assert '@media(max-width:330px){.community-kpis{grid-template-columns:1fr}}' in WEBAPP
    assert '@media(max-width:430px){.community-kpis{grid-template-columns:1fr}}' not in WEBAPP


def test_landscape_chat_has_no_impossible_min_height():
    # A 440px hero minimum may exist on the homepage; it must not be imposed on chat in landscape.
    marker = '@media (orientation: landscape) and (max-height: 560px)'
    start = WEBAPP.index(marker)
    block = WEBAPP[start:start+2600]
    assert 'min-height: 440px' not in block
    assert 'min-height:440px' not in block
    assert 'body.ss-chat-page .chat-wrap { height: 100% !important; min-height: 0 !important;' in WEBAPP


def test_landscape_chat_uses_dynamic_viewport():
    assert '@media (orientation: landscape) and (max-height: 560px)' in WEBAPP
    assert 'body.ss-chat-page .container { height: calc(100dvh - var(--bnav-h) - var(--safe-bottom));' in WEBAPP
