from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent

def _load():
    spec = spec_from_file_location("railway_entrypoint_v88", ROOT / "railway_entrypoint.py")
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def _call(mod, path="/health", method="GET"):
    captured = {}
    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = dict(headers)
    body = b"".join(mod.bootstrap_app({"PATH_INFO": path, "REQUEST_METHOD": method}, start_response))
    return captured, body

def test_health_is_503_until_real_app_is_loaded():
    mod = _load()
    meta, body = _call(mod)
    assert meta["status"].startswith("503")
    assert b'"ok":false' in body
    assert b'"status":"starting"' in body

def test_health_is_200_after_real_app_and_core_database_are_ready(monkeypatch):
    mod = _load()
    def fake_app(environ, start_response):
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [b"ok"]
    monkeypatch.setitem(sys.modules, "webapp", SimpleNamespace(
        _STARTUP_CORE_STATE={"ready": True, "failed": False, "attempts": 1, "error_type": ""}
    ))
    with mod._STATE_LOCK:
        mod._STATE["app"] = fake_app
        mod._STATE["phase"] = "serving"
    meta, body = _call(mod)
    assert meta["status"].startswith("200")
    assert b'"ok":true' in body
    assert b'"core_database":"ready"' in body

def test_health_remains_live_when_app_loaded_but_core_database_failed(monkeypatch):
    mod = _load()
    monkeypatch.setitem(sys.modules, "webapp", SimpleNamespace(
        _STARTUP_CORE_STATE={"ready": False, "failed": True, "attempts": 6, "error_type": "OperationalError"}
    ))
    with mod._STATE_LOCK:
        mod._STATE["app"] = lambda environ, start_response: [b"ok"]
        mod._STATE["phase"] = "serving"
    meta, body = _call(mod)
    assert meta["status"].startswith("200")
    assert b'"status":"alive"' in body
    assert b'"core_database":"failed"' in body

def test_failed_import_never_gets_promoted_by_healthcheck():
    mod = _load()
    with mod._STATE_LOCK:
        mod._STATE["app"] = None
        mod._STATE["phase"] = "failed"
        mod._STATE["error_type"] = "ImportError"
    meta, body = _call(mod)
    assert meta["status"].startswith("503")
    assert b'"status":"failed"' in body
    assert b'"boot_error":"ImportError"' in body
