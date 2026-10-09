import source_bundle
from pathlib import Path
ROOT=Path(__file__).resolve().parent
CHAT=source_bundle.chat_view_text()
CSS=(ROOT/'static'/'css'/'app-shell-v111.css').read_text(encoding='utf-8')

def test_quick_pick_is_progressive_disclosure():
    assert 'SYMS.slice(0, 8)' in CHAT
    assert "'عرض المزيد'" in CHAT
    assert 'symptomOptionsExpanded' in CHAT

def test_three_entry_methods_explain_their_difference():
    for text in ('وش تحس؟','وين تحس؟','وصفك الكامل'):
        assert text in CHAT
    assert 'symptom-method-copy' in CHAT

def test_body_map_supports_precise_subregions_and_free_text():
    assert 'body_zone_primary' in CHAT
    assert 'regionDetailZones' in CHAT
    assert 'data-body-refine-zone' in CHAT
    assert 'حدد المكان بدقة أكثر (اختياري)' in CHAT
    assert 'ما لقيت الوصف المناسب؟' in CHAT

def test_existing_region_symptom_does_not_force_duplicate_question():
    assert 'alreadyHasSymptom = hasSymptomForBodyRegion(zone.parent)' in CHAT
    assert 'لن نكرر عليك نفس السؤال' in CHAT

def test_result_has_compact_understanding_summary_and_field_editing():
    assert 'وش فهمنا من حالتك؟' in CHAT
    for field in ('symptoms','location','duration','severity'):
        assert f'data-quick-edit="{field}"' in CHAT
    assert 'ss-understood-card' in CSS
    assert 'ss-inline-edit-actions' in CSS

def test_context_payload_keeps_region_and_negatives_paths():
    assert 'body_region_primary:state.body_region_primary||null' in CHAT
    assert 'body_zone_primary:state.body_zone_primary||null' in CHAT
    assert 'payload.negative_symptoms' in CHAT

def test_visual_system_is_responsive_and_consistent():
    assert '.smart-body-refine' in CSS
    assert '.symptom-method-copy' in CSS
    assert '@media (max-width:640px)' in CSS

def test_root_and_views_chat_stay_identical():
    assert source_bundle.chat_view_text() == CHAT
