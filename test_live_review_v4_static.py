import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text() + "\n" + source_bundle.chat_view_text()
MK = (ROOT / "medical_knowledge.py").read_text(encoding="utf-8")
CORE = (ROOT / "analysis_core.py").read_text(encoding="utf-8")


def test_release_has_nested_and_root_asset_fallbacks():
    for name in ("icon-192.png", "icon-512.png", "apple-touch-icon.png"):
        assert (ROOT / "icons" / name).exists()
        assert (ROOT / name).exists()
    assert (ROOT / "static" / "images" / "symptosense-social-preview.png").exists()
    assert (ROOT / "symptosense-social-preview.png").exists()
    assert "def social_preview_image()" in WEB
    assert "root_copy = os.path.join(BASE_DIR, safe_name)" in WEB


def test_final_analysis_uses_denied_followup_symptoms():
    assert "payload.negative_symptoms" in WEB
    assert '"negative_symptoms": [str(x).strip()' in WEB
    assert "negative_slugs" in MK
    assert "hallmark_neg" in MK
    assert 'negatives=d.get("negative_symptoms")' in CORE


def test_questionnaire_is_capped_and_old_input_is_hidden():
    assert "const SMART_FOLLOWUP_MAX = 5" in WEB
    assert "differentialCount >= SMART_FOLLOWUP_MAX" in WEB
    focus = WEB[WEB.index("function focusStepQuestion"):WEB.index("function clearOpts", WEB.index("function focusStepQuestion"))]
    assert "hideText();" in focus
    assert "Live-review questionnaire stability fix 2026-09-09" in WEB


def test_emergency_copy_does_not_overclaim_911_coverage():
    assert "Unified emergency number across all regions" not in WEB
    assert "الرقم الموحد للطوارئ في جميع المناطق" not in WEB
    assert '"em_unified_desc": "Unified Emergency Number"' in WEB
