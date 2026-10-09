import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()


def test_heartbeat_uses_logical_alignment_for_rtl_ltr():
    assert '.ss-heartbeat-hero{width:min(360px,86%);height:54px;margin:10px 0 14px;margin-inline-end:auto;' in WEB
    assert 'margin:10px 0 14px auto' not in WEB


def test_svg_heartbeat_dot_has_safari_stable_transform_box():
    assert '.ss-heartbeat-dot{fill:currentColor;transform-box:fill-box;transform-origin:center;' in WEB


def test_healthcheck_comment_matches_liveness_readiness_split():
    assert '/ready may return 503 while starting' in WEB
    assert '(503 while starting) rather than a network-level unreachable container.' not in WEB


def test_webapp_quality_guard_still_holds():
    # V106: production hardening and mobile/iOS fixes increased guarded runtime
    # code. Keep a tight ceiling without flagging the current audited release.
    assert len(WEB.splitlines()) < 24000
