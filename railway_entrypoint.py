#!/usr/bin/env python3
"""Railway bootstrap for SymptoSense.

The socket is bound before importing the large Flask application. This makes
Railway's /health probe independent from slow imports, database wake-ups, or a
single optional module failing during application bootstrap.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import railway_runtime

railway_runtime.normalize_environment()

_LOG = logging.getLogger("SymptoSense.Bootstrap")
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper(), format="%(asctime)s %(levelname)s %(name)s %(message)s")

_STATE_LOCK = threading.Lock()
_STATE = {
    "phase": "binding",
    "app": None,
    "error_type": "",
    "started_at": time.monotonic(),
}


def _bounded_env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)) or default)
    except (TypeError, ValueError):
        value = int(default)
    return max(int(minimum), min(int(maximum), value))


def _safe_port() -> int:
    raw = str(os.environ.get("PORT") or "5000").strip()
    try:
        port = int(raw)
    except ValueError:
        port = 5000
    return port if 1 <= port <= 65535 else 5000


def _snapshot() -> dict:
    with _STATE_LOCK:
        return {
            "phase": _STATE["phase"],
            "app": _STATE["app"],
            "error_type": _STATE["error_type"],
            "uptime_ms": int((time.monotonic() - _STATE["started_at"]) * 1000),
        }


def _json_response(start_response, status: str, payload: dict):
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    start_response(status, [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
        ("X-SymptoSense-Bootstrap", "1"),
    ])
    return [body]


def bootstrap_app(environ, start_response):
    path = str(environ.get("PATH_INFO") or "/")
    method = str(environ.get("REQUEST_METHOD") or "GET").upper()
    snap = _snapshot()

    if path in {"/health", "/healthz"} and method in {"GET", "HEAD"}:
        # Bind the socket immediately, but do not tell Railway the deployment is
        # healthy until the real Flask application has imported successfully.
        # This preserves zero-downtime semantics: a broken import can never be
        # promoted merely because the bootstrap socket is reachable. Database
        # warm-up remains separate on /ready.
        app_loaded = snap["app"] is not None
        bootstrap_failed = snap["phase"] == "failed"
        # Keep /health a liveness probe: once the real Flask app is loaded it
        # remains HTTP 200 even if PostgreSQL is still warming up or degraded.
        # Surface core readiness in the payload so Railway logs/monitors do not
        # lose the database state while the bootstrap layer owns /health.
        webapp_module = sys.modules.get("webapp")
        core = getattr(webapp_module, "_STARTUP_CORE_STATE", {}) if webapp_module is not None else {}
        core_ready = bool(core.get("ready"))
        core_failed = bool(core.get("failed"))
        healthy = bool(app_loaded and not bootstrap_failed)
        status_line = "200 OK" if healthy else "503 Service Unavailable"
        payload = {
            "ok": healthy,
            "service": "SymptoSense",
            "status": "alive" if healthy else ("failed" if bootstrap_failed else "starting"),
            "bootstrap": snap["phase"],
            "boot_error": snap["error_type"] or None,
            "ready": core_ready,
            "core_database": "ready" if core_ready else ("failed" if core_failed else "starting"),
            "core_database_attempts": int(core.get("attempts") or 0),
        }
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        if method == "HEAD":
            start_response(status_line, [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(body))),
                ("Cache-Control", "no-store"),
                ("X-SymptoSense-Bootstrap", "1"),
            ])
            return [b""]
        return _json_response(start_response, status_line, payload)

    app = snap["app"]
    if app is not None:
        return app(environ, start_response)

    if path in {"/ready", "/readyz"}:
        return _json_response(start_response, "503 Service Unavailable", {
            "ok": False,
            "service": "SymptoSense",
            "status": snap["phase"],
            "boot_error": snap["error_type"] or None,
        })

    return _json_response(start_response, "503 Service Unavailable", {
        "ok": False,
        "service": "SymptoSense",
        "status": "starting" if snap["phase"] != "failed" else "configuration_error",
        "message": "SymptoSense is starting. Check /ready if this persists.",
        "boot_error": snap["error_type"] or None,
    })


def _load_full_application() -> None:
    with _STATE_LOCK:
        _STATE["phase"] = "loading-app"
    try:
        import webapp
        app = webapp.app
        with _STATE_LOCK:
            _STATE["app"] = app
            _STATE["phase"] = "app-loaded"
        railway_runtime.log_runtime_context(app.logger)
        initializer = getattr(webapp, "_initialize_core_runtime_services", None)
        if callable(initializer):
            threading.Thread(
                target=initializer,
                name="symptosense-core-startup",
                daemon=True,
            ).start()
        with _STATE_LOCK:
            _STATE["phase"] = "serving"
        _LOG.info("Full SymptoSense application loaded")
    except BaseException as exc:
        with _STATE_LOCK:
            _STATE["phase"] = "failed"
            _STATE["error_type"] = type(exc).__name__
        _LOG.exception("Full application bootstrap failed error_type=%s", type(exc).__name__)


def main() -> None:
    port = _safe_port()
    from waitress.server import create_server

    # create_server binds the socket before returning. Only after the socket is
    # live do we import the large Flask application in a background thread.
    server = create_server(bootstrap_app, host="0.0.0.0", port=port, threads=_bounded_env_int("WEB_THREADS", 12, 4, 24))
    with _STATE_LOCK:
        _STATE["phase"] = "socket-bound"
    _LOG.info("Railway bootstrap listening host=0.0.0.0 port=%s", port)
    threading.Thread(target=_load_full_application, name="symptosense-app-loader", daemon=True).start()
    server.run()


if __name__ == "__main__":
    main()
