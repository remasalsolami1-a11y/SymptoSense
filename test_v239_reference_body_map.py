import source_bundle
import versioning
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CHAT=source_bundle.chat_view_text()
CSS=(ROOT/"app-shell-v111.css").read_text()
WEB=source_bundle.webapp_text()
SW=(ROOT/"service-worker.js").read_text()

def test_v239_anatomical_layers_present():
    # V244 replaced the raster/layered art with a clean inline SVG body map.
    for token in ["bmBody(", "bm-zone", "bm-hl-f", "bm-hl-s", "bm-halo"]:
        assert token in CHAT

def test_v239_reference_css_present():
    assert "V239 reference-matched clinical body map" in CSS
    assert ".smart-body-svg.v239" in CSS

def test_v239_cache_bust():
    assert "/assets/app-shell-v112.css?v=277" in WEB
    assert "symptosense-app-shell-v112-v277" in WEB
    assert versioning.SW_CACHE in SW

def test_duplicate_chat_and_css_are_synced():
    assert source_bundle.chat_view_text()==CHAT
    assert (ROOT/"app-shell-v111.css").read_text()==CSS
