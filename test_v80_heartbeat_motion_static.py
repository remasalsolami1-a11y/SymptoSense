import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()
CHAT = source_bundle.chat_view_text()


def test_home_hero_has_ecg_heartbeat():
    assert 'class="ss-heartbeat-hero"' in WEB
    assert 'class="ss-heartbeat-path"' in WEB
    assert '@keyframes ssEcgDraw' in WEB


def test_home_has_subtle_ecg_divider():
    assert 'class="ss-ecg-divider"' in WEB


def test_analysis_loading_uses_heartbeat():
    assert 'function heartbeatLoader(label)' in CHAT
    assert "addHtml(heartbeatLoader(TT('analyzing')), 'bot heartbeat-bubble')" in CHAT
    assert 'class="ss-analysis-pulse"' in CHAT


def test_reduced_motion_supported():
    assert '@media(prefers-reduced-motion:reduce)' in WEB
    assert 'animation:none!important' in WEB


def test_webapp_quality_size_guard_kept():
    # V106: production hardening and mobile/iOS fixes increased guarded runtime
    # code. Keep a tight ceiling without flagging the current audited release.
    assert len(WEB.splitlines()) < 24000
