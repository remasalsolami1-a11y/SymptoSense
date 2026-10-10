import source_bundle
import versioning
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parent
WEB=source_bundle.webapp_text()
SW=(ROOT/"service-worker.js").read_text(encoding="utf-8")
CSS=(ROOT/"static/css/app-shell-v111.css").read_text(encoding="utf-8")
METRICS=json.loads((ROOT/"release_metrics.json").read_text(encoding="utf-8"))

def test_shared_css_is_external_and_large_enough():
    assert len(CSS) > 200_000
    assert '/assets/app-shell-v112.css?v=279' in WEB
    assert '.replace("__EXTRA_CSS__", extra_css)' in WEB
    assert '.replace("__CSS__", BASE_CSS + V2_CSS + extra_css + PREMIUM_POLISH_CSS)' not in WEB

def test_gzip_is_safe_and_negotiated():
    assert "def compress_large_text_responses" in WEB
    assert '"gzip" in (request.headers.get("Accept-Encoding") or "").lower()' in WEB
    assert 'response.headers["Content-Encoding"] = "gzip"' in WEB
    assert 'vary.add("Accept-Encoding")' in WEB
    assert "not response.direct_passthrough" in WEB

def test_optional_analytics_are_not_written_synchronously():
    start=WEB.index("def v2_operational_metrics")
    block=WEB[start:start+3500]
    assert "_queue_operational_analytics" in block
    assert "platform_v2.record_usage(" not in block
    assert "admin_operational.touch_session(" not in block

def test_static_assets_receive_long_cache_headers():
    assert 'response.headers["Cache-Control"] = "public, max-age=31536000, immutable"' in WEB

def test_service_worker_no_longer_forces_network_first_for_versioned_static():
    assert "url.pathname.startsWith('/assets/')" in SW
    assert "cached||fetch(request" in SW

def test_release_metadata_v111():
    assert METRICS["delivery_revision"] == versioning.REVISION
