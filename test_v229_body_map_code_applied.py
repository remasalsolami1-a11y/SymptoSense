import source_bundle
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CHAT=source_bundle.chat_view_text()
CSS=(ROOT/'app-shell-v111.css').read_text(encoding='utf-8')

def test_body_map_is_real_code_not_raster_mockup():
    assert 'function renderBodySilhouette(view)' in CHAT
    assert '<svg class="smart-body-svg v228"' in CHAT
    assert 'data-body-zone' in CHAT
    assert 'showBodyZone' in CHAT

def test_modal_matches_selected_mobile_design():
    assert "'اختر المنطقة'" in CHAT
    assert 'اضغط على الجزء الذي تشعر فيه بأعراض' in CHAT
    assert 'أمام الجسم' in CHAT and 'خلف الجسم' in CHAT
    assert 'smart-body-selection-note' in CHAT

def test_iphone_safari_fit_is_kept():
    assert 'dvh' in CSS
    assert 'env(safe-area-inset-bottom)' in CSS
    assert 'overflow-y:auto' in CSS
    assert '.symptom-body-sheet .smart-body-copy{display:none' in CSS

def test_mobile_method_labels_stay_short():
    for label in ('اختيار سريع','من الجسم','اكتب بنفسك'):
        assert label in CHAT
