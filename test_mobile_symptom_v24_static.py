import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEBAPP = source_bundle.webapp_text() + "\n" + source_bundle.chat_view_text()
MARKER = "iPhone / small-phone symptom layout — consolidated final override 2026-09-15"
FINAL = WEBAPP.split(MARKER, 1)[1].split('BASE_CSS = """', 1)[0]


def test_final_small_phone_override_is_last_premium_mobile_layer():
    assert MARKER in WEBAPP
    assert "@media (max-width:640px)" in FINAL
    assert "--bnav-h:58px" in FINAL


def test_mobile_header_is_single_compact_row():
    assert "grid-template-columns:minmax(0,1fr) minmax(88px,29vw) 44px!important" in FINAL
    assert "grid-template-rows:auto!important" in FINAL
    assert "min-height:68px!important" in FINAL
    assert "body.ss-chat-page .chat-head .avatar{display:none!important}" in FINAL


def test_family_selector_does_not_duplicate_person_icon():
    assert '<option value="0">__ME__</option>' in WEBAPP
    assert '<option value="0">👤 __ME__</option>' not in WEBAPP


def test_accessibility_control_is_icon_sized_on_small_phones():
    assert "body.ss-chat-page .chat-access>summary" in FINAL
    assert "width:44px!important" in FINAL
    assert "font-size:0!important" in FINAL
    assert "content:'🔊'" in FINAL


def test_question_and_answer_controls_form_one_grouped_card():
    assert "body.ss-chat-page #chatBody:not(.result-mode)" in FINAL
    assert "border-radius:18px 18px 0 0!important" in FINAL
    assert "body.ss-chat-page #chatInput" in FINAL
    assert "border-radius:0 0 18px 18px!important" in FINAL
    assert "body.ss-chat-page #chatOptions" in FINAL


def test_mobile_uses_one_scroll_surface_and_preserves_report_mode():
    assert "overflow-y:auto!important" in FINAL
    assert "body.ss-chat-page .chat-wrap.report-mode #chatOptions{display:none!important}" in FINAL
    assert "#chatBody:not(.result-mode)" in FINAL


def test_bottom_nav_is_compact_and_safe_area_aware():
    assert "height:calc(var(--bnav-h) + var(--safe-bottom))!important" in FINAL
    assert "min-height:50px!important" in FINAL
    assert "font-size:9px!important" in FINAL
