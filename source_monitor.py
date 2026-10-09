"""Read-only freshness and availability monitor for verified medical sources."""
from __future__ import annotations
import ipaddress
import json
import socket
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from urllib.request import Request, HTTPRedirectHandler, build_opener
from urllib.error import HTTPError, URLError

import db
import medical_knowledge


def _now():
    return datetime.now(timezone.utc).isoformat()


def init_schema():
    medical_knowledge.init_schema()
    conn = db._conn()
    try:
        c = conn.cursor()
        serial = "SERIAL PRIMARY KEY" if db.USE_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"
        c.execute(f"""CREATE TABLE IF NOT EXISTS source_monitor_status (
            id {serial}, source_id INTEGER UNIQUE NOT NULL, url TEXT NOT NULL,
            state TEXT NOT NULL, http_status INTEGER, response_ms REAL,
            checked_at TEXT NOT NULL, error_code TEXT, details TEXT NOT NULL DEFAULT '{{}}'
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_source_monitor_state ON source_monitor_status(state, checked_at)")
        conn.commit()
    finally:
        conn.close()


def _public_destination(url: str) -> tuple[bool, str | None]:
    """Reject private/link-local destinations even for allow-listed hostnames."""
    if not medical_knowledge._url_is_trusted(url):
        return False, "untrusted_url"
    try:
        host = urlparse(url).hostname or ""
        infos = socket.getaddrinfo(host, urlparse(url).port or 443, type=socket.SOCK_STREAM)
        addresses = {item[4][0] for item in infos if item and item[4]}
        if not addresses:
            return False, "dns_failed"
        for raw in addresses:
            ip = ipaddress.ip_address(raw)
            if not ip.is_global:
                return False, "private_destination"
        return True, None
    except (socket.gaierror, ValueError, OSError):
        return False, "dns_failed"


class UnsafeRedirectError(RuntimeError):
    pass


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urljoin(req.full_url, newurl)
        ok, reason = _public_destination(target)
        if not ok:
            raise UnsafeRedirectError(reason or "unsafe_redirect")
        return super().redirect_request(req, fp, code, msg, headers, target)


def _safe_open(req: Request, timeout: float):
    opener = build_opener(_SafeRedirectHandler())
    return opener.open(req, timeout=timeout)


def _probe(url: str, timeout: float = 5.0) -> dict:
    ok, destination_error = _public_destination(url)
    if not ok:
        return {"state": "blocked", "http_status": None, "response_ms": 0.0, "error_code": destination_error or "untrusted_url"}
    start = time.perf_counter()
    headers = {"User-Agent": "SymptoSense-SourceMonitor/1.0", "Accept": "text/html,application/json;q=0.8,*/*;q=0.2"}
    try:
        req = Request(url, method="HEAD", headers=headers)
        with _safe_open(req, timeout=timeout) as res:
            code = int(getattr(res, "status", 200) or 200)
    except UnsafeRedirectError as exc:
        return {"state": "blocked", "http_status": None, "response_ms": round((time.perf_counter()-start)*1000,1), "error_code": str(exc)[:80]}
    except HTTPError as exc:
        code = int(exc.code or 0)
        if code in {400, 403, 405}:
            try:
                req = Request(url, method="GET", headers={**headers, "Range": "bytes=0-1024"})
                with _safe_open(req, timeout=timeout) as res:
                    code = int(getattr(res, "status", 200) or 200)
            except UnsafeRedirectError as exc2:
                return {"state": "blocked", "http_status": None, "response_ms": round((time.perf_counter()-start)*1000,1), "error_code": str(exc2)[:80]}
            except HTTPError as exc2:
                code = int(exc2.code or 0)
            except (URLError, TimeoutError, OSError):
                return {"state": "unreachable", "http_status": None, "response_ms": round((time.perf_counter()-start)*1000,1), "error_code": "connection_failed"}
        elif code >= 500:
            return {"state": "degraded", "http_status": code, "response_ms": round((time.perf_counter()-start)*1000,1), "error_code": "server_error"}
    except (URLError, TimeoutError, OSError):
        return {"state": "unreachable", "http_status": None, "response_ms": round((time.perf_counter()-start)*1000,1), "error_code": "connection_failed"}
    elapsed = round((time.perf_counter()-start)*1000,1)
    if 200 <= code < 400:
        state = "healthy"
    elif code in {401,403}:
        # Source exists but automated probing may be blocked by a WAF.
        state = "restricted"
    elif code == 404:
        state = "broken"
    else:
        state = "degraded"
    return {"state": state, "http_status": code, "response_ms": elapsed, "error_code": None if state in {"healthy","restricted"} else "http_error"}


def run_monitor(limit: int = 100, timeout: float = 5.0) -> dict:
    init_schema()
    sources = medical_knowledge.list_entities("sources", include_inactive=False, search="") or []
    results = []
    for source in sources[:max(1, min(int(limit or 100), 500))]:
        url = str(source.get("official_url") or "").strip()
        probe = _probe(url, timeout=max(1.0, min(float(timeout or 5), 10.0)))
        item = {"source_id": int(source["id"]), "source_name": source.get("source_name"), "url": url, **probe, "checked_at": _now()}
        results.append(item)
        conn = db._conn()
        try:
            c = conn.cursor()
            if db.USE_POSTGRES:
                c.execute("""INSERT INTO source_monitor_status(source_id,url,state,http_status,response_ms,checked_at,error_code,details)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT(source_id) DO UPDATE SET url=EXCLUDED.url,state=EXCLUDED.state,http_status=EXCLUDED.http_status,response_ms=EXCLUDED.response_ms,checked_at=EXCLUDED.checked_at,error_code=EXCLUDED.error_code,details=EXCLUDED.details""",
                    (item["source_id"],url,item["state"],item["http_status"],item["response_ms"],item["checked_at"],item["error_code"],json.dumps({"verification_status":source.get("verification_status"),"last_verified":source.get("last_verified")},ensure_ascii=False)))
            else:
                c.execute("""INSERT INTO source_monitor_status(source_id,url,state,http_status,response_ms,checked_at,error_code,details)
                    VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET url=excluded.url,state=excluded.state,http_status=excluded.http_status,response_ms=excluded.response_ms,checked_at=excluded.checked_at,error_code=excluded.error_code,details=excluded.details""",
                    (item["source_id"],url,item["state"],item["http_status"],item["response_ms"],item["checked_at"],item["error_code"],json.dumps({"verification_status":source.get("verification_status"),"last_verified":source.get("last_verified")},ensure_ascii=False)))
            conn.commit()
        finally:
            conn.close()
    counts = {}
    for item in results: counts[item["state"]] = counts.get(item["state"],0)+1
    review = medical_knowledge.periodic_review_status()
    return {"ok": True, "checked": len(results), "counts": counts, "results": results, "review": review, "generated_at": _now()}


def status() -> dict:
    init_schema(); conn = db._conn()
    try:
        c = conn.cursor(); c.execute("SELECT source_id,url,state,http_status,response_ms,checked_at,error_code,details FROM source_monitor_status ORDER BY checked_at DESC")
        rows = [dict(zip(["source_id","url","state","http_status","response_ms","checked_at","error_code","details"], r)) for r in c.fetchall()]
        for row in rows:
            try: row["details"] = json.loads(row.get("details") or "{}")
            except Exception: row["details"] = {}
        return {"items": rows, "review": medical_knowledge.periodic_review_status()}
    finally:
        conn.close()


if __name__ == "__main__":
    # Safe CLI entry point for a daily Railway Cron/CI schedule. It only reads
    # curated sources and writes monitor metadata; it never edits medical copy.
    print(json.dumps(run_monitor(), ensure_ascii=False, indent=2))
