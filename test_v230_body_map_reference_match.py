import source_bundle
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CHAT=source_bundle.chat_view_text()
CSS=(ROOT/'app-shell-v111.css').read_text(encoding='utf-8')

def test_reference_layout_has_front_back_labels_and_body_labels():
    assert 'أمام الجسم' in CHAT and 'خلف الجسم' in CHAT
    assert 'smart-body-zone' in CHAT
    assert 'smart-body-selection-tray' in CHAT

def test_reference_layout_has_selection_tray_and_next_action():
    assert 'المنطقة المختارة' in CHAT
    assert 'data-body-selection-chip' in CHAT
    assert 'data-body-next' in CHAT
    assert 'data-body-clear' in CHAT

def test_body_map_stays_interactive_not_static_image():
    assert 'renderBodySilhouette(view)' in CHAT
    assert '<svg class="smart-body-svg v228"' in CHAT
    assert 'data-body-zone' in CHAT

def test_ios_safari_fit_and_mobile_controls():
    assert 'dvh' in CSS
    assert 'env(safe-area-inset-bottom)' in CSS
    assert 'smart-body-selection-tray' in CSS
    assert 'smart-body-next' in CSS
