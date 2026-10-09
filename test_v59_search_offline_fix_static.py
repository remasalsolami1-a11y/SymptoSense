import source_bundle
import versioning
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()
OFF = (ROOT / "offline.html").read_text(encoding="utf-8")
SW = (ROOT / "service-worker.js").read_text(encoding="utf-8")

def test_search_question_is_handed_to_assistant_exactly():
    assert "id=\"seaAskAssistantBtn\"" in WEB
    assert "asstOpenWithContext(q)" in WEB
    assert "var q = String(topic || '').trim();" in WEB
    assert "asstSendContextText(q);" in WEB
    assert "window.requestAnimationFrame(function()" in WEB

def test_offline_page_uses_csp_safe_external_assets():
    assert '<style' not in OFF
    assert '<script>' not in OFF
    assert '/static/css/offline.css' in OFF
    assert '/static/js/offline.js' in OFF
    assert "'/static/css/offline.css?v=193'" in SW
    assert "'/static/js/offline.js?v=193'" in SW
    assert versioning.SW_CACHE in SW
