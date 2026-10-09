import source_bundle
import versioning
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()
CHAT = source_bundle.chat_view_text()
ADMIN = (ROOT / "dashboard.py").read_text(encoding="utf-8")
RC = (ROOT / "release_candidate.py").read_text(encoding="utf-8")
SW = (ROOT / "service-worker.js").read_text(encoding="utf-8")
DS = (ROOT / "static" / "css" / "design-system.css").read_text(encoding="utf-8")


def test_contextual_symptom_pattern_is_real_and_not_diagnostic():
    assert "function contextualSymptomPattern(input)" in CHAT
    assert "نمط الأعراض الحالي" in CHAT
    assert "يبدو مرتبطًا أكثر" in CHAT
    assert "هذا وصف للسياق الذي أدخلته، وليس تشخيصًا" in CHAT
    for label in ("مع الحركة", "بعد الأكل", "عند الوقوف", "وقت الدورة", "بالليل", "بعد المجهود"):
        assert label in CHAT


def test_pattern_card_uses_analysis_input_and_is_suppressed_for_urgent_results():
    assert "if (u !== 'high') h += contextualSymptomPatternHtml(input);" in CHAT
    assert "نمط الأعراض الملحوظ" in CHAT


def test_typography_contract_is_unified():
    assert "font-family:'Tajawal'" in WEB
    assert "font-family:'Poppins'" in WEB
    assert "button,input,select,textarea,option" in WEB
    assert "V69 cross-surface consistency contract" in DS
    assert "html[dir='ltr'] body{font-family:'Poppins'" in ADMIN
    assert "html[dir='rtl'] body{font-family:'Tajawal'" in ADMIN


def test_buttons_and_surfaces_have_consistent_minimum_sizes():
    assert "V69 final whole-site size, shape, controls, and typography audit" in WEB
    assert "min-height:44px!important" in WEB
    assert "border-radius:16px!important" in WEB
    assert "V69 admin typography/size consistency pass" in ADMIN


def test_release_v69_metadata_and_pwa_cache():
    assert versioning.APP_VERSION == __import__("release_candidate").APP_VERSION
    assert versioning.RC_ID == __import__("release_candidate").RC_ID
    assert versioning.SW_CACHE in SW


def test_key_html_button_tags_use_explicit_button_type():
    import re
    sources = {
        "webapp.py": WEB,
        "chat_view.py": CHAT,
        "dashboard.py": ADMIN,
    }
    missing = []
    for name, source in sources.items():
        for match in re.finditer(r"<button\\b[^>]*>", source, flags=re.I | re.S):
            tag = match.group(0)
            if not re.search(r"\\btype\\s*=", tag, flags=re.I):
                missing.append((name, tag[:160]))
    assert not missing, missing


def test_compact_mobile_controls_keep_touch_targets_and_readable_copy():
    assert "V69 final home/mobile legibility + touch-target pass" in WEB
    assert ".ss-hero-primary,.ss-hero-secondary,.ss-hero-demo-cta,.ss-core-open{min-height:44px!important}" in WEB
    assert "body.ss-chat-page .quick-symptom-chip{min-height:44px!important" in WEB
    assert "body.ss-welcome-page .first-lang-benefit small{font-size:9.5px!important" in WEB
