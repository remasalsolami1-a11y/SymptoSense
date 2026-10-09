import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHAT = source_bundle.chat_view_text()
WEB = source_bundle.webapp_text()


def test_body_map_remains_available_with_compact_mobile_presentation():
    # Desktop keeps the inline disclosure; mobile V100 opens the same map on demand
    # in a bottom sheet so the symptom page is not crowded.
    assert "symptom-bodymap-always-open" in CHAT
    assert "استخدام خريطة الجسم · حدد مكان العرض" in CHAT
    assert "data-symptom-method=\"body\"" in CHAT
    assert "openBodyMapSheet" in CHAT
    assert "symptom-body-sheet" in WEB


def test_body_map_selection_is_kept_in_state_and_reset():
    assert "body_regions:[]" in CHAT
    assert "body_region_primary:null" in CHAT
    assert "body_region_needs_symptom:null" in CHAT
    assert "setBodyRegionSelection(regionKey" in CHAT


def test_map_text_conflict_gets_clarification_choices():
    assert "showBodyRegionConflict(raw, found, typedRegions)" in CHAT
    assert "اخترت ' + selectedLabel + ' من خريطة الجسم" in CHAT
    assert "+' فقط':'📍 '" in CHAT
    assert "+' فقط':'✍️ '" in CHAT
    assert "➕ الاثنين معًا" in CHAT


def test_arabic_inflection_example_batni_is_detected():
    assert "abdomen:['بطن','معده','مغص'" in CHAT
    assert "LANG === 'ar' ? text.indexOf(w) !== -1" in CHAT


def test_general_and_related_symptoms_also_use_region_conflict_guard():
    assert "const optionRegions = inferBodyRegions(s, [s]);" in CHAT
    assert "const relatedRegions = inferBodyRegions(label, [label]);" in CHAT


def test_v82_motion_hierarchy_keeps_decorative_motion_quiet():
    assert "V82 motion hierarchy" in WEB
    assert ".smart-body-stage.flash,.smart-body-part.pulse,.smart-body-region-card" in WEB
    assert ".float-ic,.au-reveal" in WEB
    assert "@keyframes ssEcgDraw" in WEB


def test_both_areas_requires_a_specific_symptom_before_continue():
    assert "body_region_needs_symptom" in CHAT
    assert "regionNeedsSymptom" in CHAT
    assert "Choose a specific symptom from" in CHAT
