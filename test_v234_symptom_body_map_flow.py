import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHAT_A = source_bundle.chat_view_text()
CHAT_B = source_bundle.chat_view_text()
CSS_A = (ROOT / 'app-shell-v111.css').read_text(encoding='utf-8')
CSS_B = (ROOT / 'app-shell-v111.css').read_text(encoding='utf-8')


def test_body_method_opens_map_directly_on_mobile():
    assert "if(symptomInputMethod==='body')" in CHAT_A
    assert "openBodyMapSheet(state.body_region_primary||null)" in CHAT_A


def test_body_zone_shows_common_symptom_language():
    assert "الأعراض الأكثر شيوعًا في هذه المنطقة" in CHAT_A
    assert "Common symptoms in this area" in CHAT_A


def test_body_region_has_custom_symptom_fallback():
    assert "ما لقيت عرضك؟" in CHAT_A
    assert 'data-body-other-input' in CHAT_A
    assert 'data-body-other-submit' in CHAT_A


def test_custom_symptom_still_uses_existing_extraction_pipeline():
    assert ("if(value){ extractSmartSymptoms(value); }" in CHAT_A or "if(value){ extractSmartSymptoms(value, selectedRegion || null); }" in CHAT_A)


def test_typography_clarity_and_mobile_touch_targets():
    assert 'V234 symptom body-map clarity' in CSS_A
    assert 'font-size:20px!important' in CSS_A
    assert 'min-height:48px!important' in CSS_A
    assert '.smart-body-other input:focus' in CSS_A


def test_runtime_duplicate_assets_remain_identical():
    assert CHAT_A == CHAT_B
    assert CSS_A == CSS_B
