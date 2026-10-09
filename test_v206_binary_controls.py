import source_bundle
from pathlib import Path

ROOT=Path(__file__).resolve().parent
WEB=source_bundle.webapp_text()
CSS=(ROOT/"app-shell-v111.css").read_text(encoding="utf-8")
STATIC=(ROOT/"static/css/app-shell-v111.css").read_text(encoding="utf-8")

def test_binary_controls_are_isolated_from_text_input_geometry():
    rule='input[type="checkbox"],input[type="radio"]'
    for src in (WEB,CSS,STATIC):
        assert rule in src
        tail=src.split(rule,1)[1][:220]
        assert 'min-height:0!important' in tail
        assert 'padding:0!important' in tail

def test_all_known_binary_control_surfaces_still_exist():
    for token in (
        'id="serviceConsent"', 'id="analyticsConsent"', 'id="researchConsent"',
        'id="bloodCollectConsent"', 'name="accept_terms"', 'id="fbPublic"',
        'name="deliveryChannel"', 'class="ss-toggle"', 'class="sid-switch"',
    ):
        assert token in WEB or token in source_bundle.chat_view_text()


def test_binary_control_css_is_cache_busted():
    sw=(ROOT/"service-worker.js").read_text(encoding="utf-8")
    assert '/assets/app-shell-v112.css?v=272' in WEB
    assert "'/assets/app-shell-v112.css?v=272'" in sw
    assert 'symptosense-app-shell-v112-v272' in WEB
