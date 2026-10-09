"""Privacy-safe request correlation for logs, Sentry and API clients."""
from __future__ import annotations
import re
import secrets
import time
from flask import g, request

_VALID = re.compile(r"^[A-Za-z0-9._:-]{8,80}$")


def _incoming_id() -> str | None:
    raw = (request.headers.get("X-Request-ID") or "").strip()
    return raw if _VALID.fullmatch(raw) else None


def begin_request() -> str:
    rid = _incoming_id() or secrets.token_urlsafe(12)
    g.request_id = rid
    g.request_started_monotonic = time.monotonic()
    try:
        import sentry_sdk
        sentry_sdk.set_tag("request_id", rid)
    except Exception:
        pass
    return rid


def finish_response(response):
    rid = getattr(g, "request_id", None)
    if rid:
        response.headers["X-Request-ID"] = rid
    started = getattr(g, "request_started_monotonic", None)
    if started is not None:
        elapsed_ms = max(0.0, (time.monotonic() - started) * 1000.0)
        # Server-Timing is coarse diagnostics only; no health/user content.
        response.headers["Server-Timing"] = f"app;dur={elapsed_ms:.1f}"
    return response
