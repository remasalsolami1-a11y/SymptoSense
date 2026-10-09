import source_bundle
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CHAT=source_bundle.chat_view_text()
CSS=(ROOT/'app-shell-v111.css').read_text(encoding='utf-8')
CSS_COPY=(ROOT/'static'/'css'/'app-shell-v111.css').read_text(encoding='utf-8')
CHAT_COPY=source_bundle.chat_view_text()

def test_edge_zone_labels_point_inward_on_small_screens():
    # V244: labels sit in fixed left/right columns beside the body; lines point inward to the dots.
    assert ".bm-label.bm-L{left:0}" in CHAT and ".bm-label.bm-R{right:0}" in CHAT
    assert "@media(max-width:350px){.bm-label" in CHAT

def test_small_phone_labels_remain_readable():
    assert 'font-size:10px!important' in CSS
    assert 'max-width:94px!important' in CSS

def test_body_stage_does_not_clip_connector_labels():
    assert 'overflow:visible!important' in CSS
    assert 'env(safe-area-inset-bottom)' in CSS
    assert 'dvh' in CSS

def test_duplicate_runtime_assets_stay_identical():
    assert CSS == CSS_COPY
    assert CHAT == CHAT_COPY
