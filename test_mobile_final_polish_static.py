from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEBAPP = (ROOT / 'webapp.py').read_text(encoding='utf-8')


def test_phone_home_hero_visual_hidden_under_480():
    assert '@media(max-width:480px){.hh{padding:20px 16px!important}.hh-r{display:none!important}' in WEBAPP


def test_home_how_flow_is_2x2_on_regular_phones():
    assert '@media(max-width:480px){.home-how{padding:18px 14px;margin:22px 0}.home-how-flow{grid-template-columns:1fr 1fr' in WEBAPP
    assert '@media(max-width:330px){.home-how-flow{grid-template-columns:1fr}}' in WEBAPP


def test_home_does_not_duplicate_community_dashboard_stats():
    start = WEBAPP.index('def home_page():')
    end = WEBAPP.index('\n\ndef _tools_html', start)
    block = WEBAPP[start:end]
    assert 'home-community' not in block
    assert '__USER_COUNT__' not in block


def test_community_dashboard_kpis_stay_2x2_on_common_phones():
    assert '@media(max-width:700px){.community-hero{padding:26px 16px}.community-kpis{grid-template-columns:repeat(2,minmax(0,1fr))' in WEBAPP
    assert '@media(max-width:330px){.community-kpis{grid-template-columns:1fr}}' in WEBAPP
    assert '@media(max-width:430px){.community-kpis{grid-template-columns:1fr}}' not in WEBAPP


def test_landscape_chat_has_no_impossible_min_height():
    assert 'min-height: 440px' not in WEBAPP
    assert 'min-height:440px' not in WEBAPP
    assert 'body.ss-chat-page .chat-wrap { height: 100% !important; min-height: 0 !important;' in WEBAPP


def test_landscape_chat_uses_dynamic_viewport():
    assert '@media (orientation: landscape) and (max-height: 560px)' in WEBAPP
    assert 'body.ss-chat-page .container { height: calc(100dvh - var(--bnav-h) - var(--safe-bottom));' in WEBAPP
