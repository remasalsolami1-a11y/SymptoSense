import source_bundle
import versioning
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()
CHAT = source_bundle.chat_view_text()
BOT = (ROOT / "bot.py").read_text(encoding="utf-8")
MODEL_CARD = (ROOT / "MODEL_CARD.md").read_text(encoding="utf-8")
SECURITY = (ROOT / "web_security.py").read_text(encoding="utf-8")
BRIDGE = (ROOT / "static" / "js" / "interaction-bridge.js").read_text(encoding="utf-8")
E2E = (ROOT / "tools" / "e2e_browser.py").read_text(encoding="utf-8")
CI = (ROOT / "ci.yml").read_text(encoding="utf-8")
RC = (ROOT / "release_candidate.py").read_text(encoding="utf-8")
SW = (ROOT / "service-worker.js").read_text(encoding="utf-8")


def test_release_metadata_is_v46():
    assert versioning.APP_VERSION == __import__("release_candidate").APP_VERSION
    assert versioning.RC_ID == __import__("release_candidate").RC_ID
    assert versioning.SW_CACHE in SW


def test_ml_accuracy_is_documentation_only_not_user_facing():
    assert "65.28%" in MODEL_CARD
    assert "63.5%" not in BOT
    assert "65.3%" not in BOT
    assert "65.28%" not in BOT
    assert "65.28%" not in WEB
    assert "65.28%" not in CHAT


def test_home_copy_avoids_diagnostic_probability_language():
    combined = WEB + "\n" + CHAT
    for phrase in (
        "احتمال مرتفع", "احتمال متوسط", "احتمال بسيط",
        "High probability", "Medium probability", "Low probability",
        "حسابات دقيقة", "استخدام آمن",
    ):
        assert phrase not in combined
    assert "حسابات صحية تقديرية" in WEB
    assert "معلومات وتنبيهات دوائية" in WEB


def test_result_disclaimer_explicitly_says_no_diagnosis():
    assert "لا تقدم تشخيصًا طبيًا" in CHAT
    assert "does not provide a medical diagnosis" in CHAT


def test_demo_is_fictional_fast_and_account_detached():
    assert "Run demo assessment" in CHAT
    assert "تشغيل المثال الآن" in CHAT
    assert "state.demo_mode = true" in CHAT
    assert "if (state.demo_mode)" in CHAT
    assert "if (state.previous_record_id) payload.previous_record_id = state.previous_record_id" in CHAT
    assert "localStorage.getItem('symptosense_blood_id')" in CHAT
    assert 'data["blood_id"] = None' in WEB
    assert 'data["previous_record_id"] = None' in WEB
    assert 'data["use_saved"] = False' in WEB
    assert '"user_id": None if demo_mode else' in WEB
    assert "if uid and not demo_mode" in WEB


def test_executable_inline_javascript_is_not_allowed_by_csp():
    assert '"script-src-attr \'none\'"' in SECURITY
    assert "script-src 'self' 'unsafe-inline'" not in SECURITY.replace(
        "broad ``script-src 'unsafe-inline'``", ""
    )
    assert "/static/js/interaction-bridge.js" in WEB
    assert "eval(" not in BRIDGE
    assert "new Function(" not in BRIDGE
    assert "ALLOWED_CALLS" in BRIDGE
    assert "addEventListener" in BRIDGE


def test_large_chat_view_was_extracted_from_monolith():
    assert "from chat_view import render_chat_page" in WEB
    assert "render_chat_page(lang=" in WEB
    assert "def render_chat_page" in CHAT
    # V111 adds guarded response compression and a small async analytics queue
    # while keeping the large chat view extracted. Retain a tight ceiling.
    assert len(WEB.splitlines()) < 24000
    assert len(CHAT.splitlines()) > 2000


def test_browser_e2e_covers_requested_viewports_and_interactions():
    for token in ("iphone-390", "mobile-430", "ipad", "laptop", "desktop"):
        assert token in E2E
    assert "Run demo assessment" in E2E
    assert "script-src-attr 'none'" in E2E
    assert "#asstFab" in E2E
    assert "CSP interaction bridge behavior" in CI
    assert "Responsive browser E2E matrix" in CI
