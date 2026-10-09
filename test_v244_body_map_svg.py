"""V244: inline-SVG body map, common symptoms per area, free-text fallback, readable type."""
import source_bundle
import re
from pathlib import Path

CHAT = source_bundle.chat_view_text()


def _zone_keys():
    start = CHAT.index('const BODY_MAP_ZONES = LANG ===')
    block = CHAT[start:CHAT.index('const BM_LAYOUT = {', start)]
    return set(re.findall(r"^\s+(\w+):\{label:", block, re.M))


def _layout_keys():
    start = CHAT.index('const BM_LAYOUT = {')
    block = CHAT[start:CHAT.index('const BM_SHAPES', start)]
    return set(re.findall(r"^\s+(\w+):\{dot:", block, re.M))


def test_every_body_zone_has_a_map_position_and_label():
    assert _zone_keys() and _zone_keys() == _layout_keys()


def test_map_is_inline_svg_hotspots_over_art():
    assert 'class="bm-svg"' in CHAT and 'bm-visual' in CHAT
    assert 'smart-body-static-art' not in CHAT


def test_tapping_a_zone_lists_common_symptoms_and_free_text_fallback():
    assert 'Common symptoms in this area' in CHAT and 'data-body-symptom' in CHAT
    assert 'data-body-other-input' in CHAT and 'data-body-other-submit' in CHAT


def test_zone_hit_targets_and_keyboard_support():
    assert 'r="22"' in CHAT                      # >= 44px at ~0.9 scale
    assert "e.key !== 'Enter' && e.key !== ' '" in CHAT
    assert 'role="button" tabindex="0"' in CHAT


def test_body_map_text_is_at_least_13px():
    s = CHAT.index('<style id="bm-v244">')
    css = CHAT[s:CHAT.index('</style>', s)]
    sizes = [float(x) for x in re.findall(r'font-size:([\d.]+)px', css)]
    assert sizes and min(sizes) >= 13, sorted(set(sizes))


def test_v245_anatomical_art_front_and_back_are_shipped():
    root = Path(__file__).resolve().parent
    for n in ('front', 'back'):
        f = root / f'body-{n}-v245.webp'
        assert f.exists() and f.stat().st_size > 10000
        assert f'/static/images/body-{n}-v245.webp' in CHAT
        assert f'body-{n}-v245.webp' in (root / 'Dockerfile').read_text(encoding='utf-8')
        assert f'/static/images/body-{n}-v245.webp' in (root / 'service-worker.js').read_text(encoding='utf-8')
