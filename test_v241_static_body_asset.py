import source_bundle
import versioning
from pathlib import Path
ROOT=Path(__file__).resolve().parent
CHAT=source_bundle.chat_view_text()
WEB=source_bundle.webapp_text()
SW=(ROOT/'service-worker.js').read_text()
DOCKER=(ROOT/'Dockerfile').read_text()

def test_body_art_is_external_static_asset_not_huge_inline_data_uri():
    assert "const BODY_MAP_FRONT_STATIC = '/static/images/body-map-front-v241.png';" in CHAT
    assert "BODY_MAP_FRONT_STATIC = 'data:image" not in CHAT
    assert (ROOT/'body-map-front-v241.png').stat().st_size > 10000

def test_static_asset_is_copied_in_production_image():
    assert 'body-map-front-v241.png' in DOCKER and 'static/images/' in DOCKER

def test_cache_and_css_are_bumped():
    assert '/assets/app-shell-v112.css?v=276' in WEB
    assert 'symptosense-app-shell-v112-v276' in WEB
    assert versioning.SW_CACHE in SW
    assert "'/static/images/body-map-front-v241.png'" in SW

def test_front_body_uses_inline_svg_with_dynamic_zone_buttons():
    # V244: the map is inline SVG; zone buttons and labels are generated together.
    assert 'class="bm-svg"' in CHAT and 'bm-label' in CHAT
    assert 'smart-body-static-art' not in CHAT
    assert 'data-body-zone' in CHAT
    assert 'data-body-symptom' in CHAT

def test_chat_mirrors_match():
    assert source_bundle.chat_view_text()==CHAT
