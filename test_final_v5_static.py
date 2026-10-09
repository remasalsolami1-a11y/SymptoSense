import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text() + "\n" + source_bundle.chat_view_text()


def test_desktop_focus_does_not_scroll_analysis_page():
    assert "textInp.focus({ preventScroll: true })" in WEB
    # Do not silently fall back to a plain focus for this analysis input.
    block = WEB[WEB.index("function showText"):WEB.index("function hideText", WEB.index("function showText"))]
    assert "textInp.focus();" not in block


def test_assistant_provider_fails_fast_to_local_fallback():
    start = WEB.index("def _groq_chat_completion_with_retry")
    end = WEB.index("def _followup_local_answer", start)
    helper = WEB[start:end]
    assert "timeout=6" in helper
    assert "range(2)" not in helper
    assert "time.sleep(" not in helper
    assert "min(float(timeout or 6), 6.0)" in helper
