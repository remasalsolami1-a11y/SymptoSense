import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHAT = source_bundle.chat_view_text()
CSS = (ROOT / 'static' / 'css' / 'app-shell-v111.css').read_text(encoding='utf-8')


def test_mobile_method_tabs_are_clear_and_keep_all_three_paths():
    for text in ('اختيار سريع', 'من الجسم', 'اكتب بنفسك'):
        assert text in CHAT
    assert 'data-symptom-method="pick"' in CHAT
    assert 'data-symptom-method="body"' in CHAT
    assert 'data-symptom-method="describe"' in CHAT


def test_body_map_uses_visual_zones_not_disease_shortcuts():
    assert 'const BODY_MAP_ZONES' in CHAT
    assert 'data-body-zone' in CHAT
    for zone in ('الرأس والوجه', 'الصدر', 'أعلى البطن', 'أسفل البطن', 'الركبة', 'أسفل الظهر'):
        assert zone in CHAT
    assert 'وش تحس في هذا المكان؟' in CHAT


def test_every_zone_can_fall_back_to_free_text():
    assert 'ما لقيت الوصف المناسب؟' in CHAT
    assert 'اكتب وش تحس في هذه المنطقة بطريقتك.' in CHAT
    assert 'data-body-other-input' in CHAT
    assert 'data-body-other-submit' in CHAT
    assert 'extractSmartSymptoms(value)' in CHAT


def test_body_zone_is_ui_specific_and_preserves_backend_region_model():
    assert "parent:'abdomen'" in CHAT
    assert "parent:'legs'" in CHAT
    assert 'setBodyRegionSelection(zone.parent, false)' in CHAT
    assert 'BODY_MAP_REGIONS' in CHAT


def test_mobile_map_is_large_and_touch_friendly():
    assert '.smart-body-visual' in CSS
    assert '.smart-body-zone' in CSS
    assert 'height:390px!important' in CSS
    assert 'max-height:92dvh!important' in CSS


def test_root_and_views_chat_are_identical():
    root_chat = (ROOT / 'chat_view.py').read_text(encoding='utf-8')
    assert root_chat == (ROOT / 'views' / 'chat_view.py').read_text(encoding='utf-8')
