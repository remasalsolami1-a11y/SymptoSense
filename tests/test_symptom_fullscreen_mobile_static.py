import source_bundle
from pathlib import Path


SOURCE = source_bundle.webapp_text()


def test_mobile_symptom_page_uses_the_full_available_viewport():
    marker = "Full-screen symptom questionnaire on phones/tablets 2026-09-14"
    css = SOURCE[SOURCE.index(marker):SOURCE.index("BASE_CSS = inline_assets")]
    assert "body.ss-chat-page .container" in css
    assert "height:calc(100dvh - var(--bnav-h) - var(--safe-bottom))!important" in css
    assert "body.ss-chat-page .chat-wrap" in css
    assert "height:100%!important" in css
    assert "border-radius:0!important" in css


def test_fullscreen_override_is_scoped_to_symptom_page():
    marker = "Full-screen symptom questionnaire on phones/tablets 2026-09-14"
    css = SOURCE[SOURCE.index(marker):SOURCE.index("BASE_CSS = inline_assets")]
    assert "body.ss-chat-page" in css
    assert "body.ss-home-page" not in css

