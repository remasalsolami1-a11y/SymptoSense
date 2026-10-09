import source_bundle
import versioning
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()
SW = (ROOT / "service-worker.js").read_text(encoding="utf-8")

def test_page_frame_uses_app_served_css():
    assert '<link rel="stylesheet" href="/assets/app-shell-v112.css?v=274">' in WEB
    assert '/static/css/app-shell-v111.css' not in WEB

def test_app_shell_route_is_public_and_cacheable():
    assert '@app.route("/assets/app-shell-v112.css")' in WEB
    assert 'css = BASE_CSS + V2_CSS + PREMIUM_POLISH_CSS' in WEB
    assert 'response = Response(css, mimetype="text/css")' in WEB
    assert 'path.startswith("/assets/")' in WEB
    assert 'public, max-age=31536000, immutable' in WEB

def test_service_worker_precaches_new_app_shell():
    assert "'/assets/app-shell-v112.css?v=274'" in SW
    assert "url.pathname.startsWith('/assets/')" in SW
    assert versioning.SW_CACHE in SW
