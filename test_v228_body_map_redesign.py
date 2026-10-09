import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHAT = source_bundle.chat_view_text()
CSS = (ROOT / 'static' / 'css' / 'app-shell-v111.css').read_text(encoding='utf-8')


def test_v228_uses_detailed_clinical_svg_instead_of_old_simple_silhouette():
    assert 'smart-body-svg v228' in CHAT
    assert 'linearGradient id="skinFront"' in CHAT
    assert 'linearGradient id="torsoSoft"' in CHAT
    assert 'body-zone-glow' in CHAT
    assert 'viewBox="0 0 320 680"' in CHAT


def test_v228_keeps_front_back_and_labeled_connected_zones():
    assert 'أمام الجسم' in CHAT and 'خلف الجسم' in CHAT
    # V244: labels are connected to the dots with SVG leader lines (left/right columns).
    assert 'bm-label bm-' in CHAT and 'bm-line' in CHAT
    assert "side:'L'" in CHAT and "side:'R'" in CHAT


def test_v228_mobile_method_tabs_are_short_not_wrapped_descriptions():
    assert 'اختيار سريع' in CHAT and 'من الجسم' in CHAT and 'اكتب بنفسك' in CHAT
    assert '.symptom-method-copy>small{display:none!important}' in CSS
    assert 'white-space:nowrap!important' in CSS


def test_v228_sheet_uses_dynamic_viewport_and_safe_area_for_ios_safari():
    assert 'height:min(94dvh,900px)!important' in CSS
    assert 'max-height:min(94dvh,900px)!important' in CSS
    assert 'env(safe-area-inset-bottom)' in CSS
    assert '.symptom-body-sheet-content' in CSS
    assert 'overflow-y:auto!important' in CSS
    assert '-webkit-overflow-scrolling:touch' in CSS


def test_v228_body_is_scaled_to_fit_short_and_narrow_phones():
    assert 'height:clamp(330px,56dvh,500px)!important' in CSS
    assert '@media(max-width:380px)' in CSS
    assert '@media(max-height:680px) and (max-width:640px)' in CSS
    assert 'height:clamp(300px,49dvh,360px)!important' in CSS


def test_v228_preserves_symptom_selection_and_free_text_flow():
    assert 'data-body-symptom' in CHAT
    assert 'data-body-other-input' in CHAT
    assert 'data-body-other-submit' in CHAT
    assert 'وش تحس في هذا المكان؟' in CHAT
    assert 'extractSmartSymptoms(value)' in CHAT


def test_v228_does_not_add_disease_names_to_body_map_layer():
    block = CHAT[CHAT.index('const BODY_MAP_ZONES'):CHAT.index('let selectedBodyZone')]
    for disease in ('سرطان', 'التهاب الزائدة', 'جلطة', 'ورم', 'Cancer', 'Appendicitis'):
        assert disease not in block


def test_duplicate_runtime_files_stay_identical():
    assert source_bundle.chat_view_text() == CHAT
    assert (ROOT / 'app-shell-v111.css').read_text(encoding='utf-8') == CSS
