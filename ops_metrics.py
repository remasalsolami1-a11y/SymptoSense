"""Privacy-safe in-process production metrics (V253).

Counts requests / 5xx / slow requests per route *pattern* (never query strings,
user ids or health content) and keeps named counters for events that must never
fail silently, such as ``safety_check_failure``. Values are per worker process and
reset on restart; they exist so an operator can see trouble without relying on
``/health`` (which only proves the process is alive).
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

_LOCK = threading.Lock()
_STARTED = time.time()
_COUNTERS = defaultdict(int)
_ROUTES = defaultdict(lambda: {"count": 0, "errors_5xx": 0, "errors_4xx": 0, "slow": 0, "ms": deque(maxlen=200)})
_RECENT_ERRORS = deque(maxlen=20)
SLOW_MS = 2500


def incr(name: str, n: int = 1) -> None:
    with _LOCK:
        _COUNTERS[str(name)[:60]] += int(n)


def event_error(kind: str, detail: str = "") -> None:
    """Record a handled-but-important failure (kept short, no user content)."""
    with _LOCK:
        _COUNTERS["error:" + str(kind)[:50]] += 1
        _RECENT_ERRORS.append({"t": int(time.time()), "kind": str(kind)[:50], "detail": str(detail)[:120]})


def observe(route: str, status: int, elapsed_ms: float) -> None:
    route = str(route or "?")[:80]
    with _LOCK:
        r = _ROUTES[route]
        r["count"] += 1
        if status >= 500:
            r["errors_5xx"] += 1
        elif status >= 400:
            r["errors_4xx"] += 1
        if elapsed_ms >= SLOW_MS:
            r["slow"] += 1
        r["ms"].append(float(elapsed_ms))
        _COUNTERS["requests_total"] += 1
        if status >= 500:
            _COUNTERS["responses_5xx"] += 1


def _pct(values, p):
    if not values:
        return None
    s = sorted(values)
    return round(s[min(len(s) - 1, int(len(s) * p))], 1)


def snapshot(top: int = 15) -> dict:
    with _LOCK:
        total = _COUNTERS.get("requests_total", 0)
        e5 = _COUNTERS.get("responses_5xx", 0)
        routes = []
        for name, r in _ROUTES.items():
            ms = list(r["ms"])
            routes.append({"route": name, "count": r["count"], "errors_5xx": r["errors_5xx"], "errors_4xx": r["errors_4xx"],
                           "slow": r["slow"], "p50_ms": _pct(ms, 0.5), "p95_ms": _pct(ms, 0.95)})
        routes.sort(key=lambda x: (-x["errors_5xx"], -(x["p95_ms"] or 0)))
        return {"uptime_s": int(time.time() - _STARTED), "requests_total": total, "responses_5xx": e5,
                "error_rate_5xx": round(e5 / total, 4) if total else 0.0,
                "counters": {k: v for k, v in _COUNTERS.items() if k not in {"requests_total", "responses_5xx"}},
                "routes": routes[:top], "recent_errors": list(_RECENT_ERRORS)}


def reset() -> None:
    with _LOCK:
        _COUNTERS.clear(); _ROUTES.clear(); _RECENT_ERRORS.clear()
