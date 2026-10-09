import source_bundle
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_dashboard_with_inline_handlers_loads_csp_interaction_bridge():
    dashboard = _read("dashboard.py")
    assert re.search(r"\sdata-ss-(?:click|change|input|submit)\s*=", dashboard, re.I)
    assert '/static/js/interaction-bridge.js' in dashboard


def test_admin_performance_handlers_are_bridge_allowlisted():
    bridge = _read("static/js/interaction-bridge.js")
    assert "'loadPerformanceBenchmark'" in bridge
    assert "'runPerformanceBenchmark'" in bridge


def test_language_picker_has_server_side_navigation_fallback():
    web = source_bundle.webapp_text()
    assert 'href="__LANG_AR_TARGET__"' in web
    assert 'href="__LANG_EN_TARGET__"' in web
    assert 'def persist_explicit_language_selection(response):' in web
    assert '@app.route("/language/<code>", methods=["GET"])' in web


def test_settings_post_is_csrf_protected_and_form_carries_token():
    web = source_bundle.webapp_text()
    start = web.index('@app.route("/settings", methods=["GET", "POST"])')
    section = web[start:start + 7000]
    assert 'if request.method == "POST":' in section
    assert '_user_csrf_valid()' in section
    assert 'name="csrf_token" value="__CSRF__"' in section
    assert 'body.replace("__CSRF__"' in section


def test_registration_target_blank_links_use_noopener():
    web = source_bundle.webapp_text()
    start = web.index('accept=(')
    section = web[start:start + 1000]
    links = re.findall(r'<a\b[^>]*target="_blank"[^>]*>', section, flags=re.I)
    assert links
    assert all('rel="noopener noreferrer"' in link for link in links)
