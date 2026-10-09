"""Privacy-safe production verification state for SymptoSense.

Stores only technical launch checks (timestamps, provider names, opaque event ids).
No email addresses, symptoms, medication names, message bodies, or other health data
are written here.
"""
from __future__ import annotations
import logging

import json
from datetime import datetime, timezone

import db

PH = db.PH
_SCHEMA_READY = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_schema():
    global _SCHEMA_READY
    key = (db.USE_POSTGRES, getattr(db, "DATABASE_URL", ""), getattr(db, "DB_PATH", ""))
    if _SCHEMA_READY == key:
        return
    db.init_db(); conn = db._conn(); c = conn.cursor()
    try:
        c.execute("""
            CREATE TABLE IF NOT EXISTS production_verifications (
                verification_key TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT '',
                event_at TEXT,
                details_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit(); _SCHEMA_READY = key
    finally:
        conn.close()


def record(key: str, status: str, details: dict | None = None, event_at: str | None = None) -> dict:
    init_schema(); key = str(key or "").strip()[:80]
    if not key:
        raise ValueError("verification_key_required")
    status = str(status or "").strip()[:40]
    now = _now(); payload = json.dumps(details or {}, ensure_ascii=False, separators=(",", ":"))[:6000]
    conn = db._conn(); c = conn.cursor()
    try:
        if db.USE_POSTGRES:
            c.execute(
                f"INSERT INTO production_verifications(verification_key,status,event_at,details_json,updated_at) VALUES({','.join([PH]*5)}) "
                "ON CONFLICT(verification_key) DO UPDATE SET status=EXCLUDED.status,event_at=EXCLUDED.event_at,details_json=EXCLUDED.details_json,updated_at=EXCLUDED.updated_at",
                (key, status, event_at or now, payload, now),
            )
        else:
            c.execute(
                f"INSERT INTO production_verifications(verification_key,status,event_at,details_json,updated_at) VALUES({','.join([PH]*5)}) "
                "ON CONFLICT(verification_key) DO UPDATE SET status=excluded.status,event_at=excluded.event_at,details_json=excluded.details_json,updated_at=excluded.updated_at",
                (key, status, event_at or now, payload, now),
            )
        conn.commit()
    finally:
        conn.close()
    return get(key) or {"key": key, "status": status, "event_at": event_at or now, "details": details or {}}


def get(key: str) -> dict | None:
    init_schema(); conn = db._conn(); c = conn.cursor()
    try:
        c.execute(f"SELECT verification_key,status,event_at,details_json,updated_at FROM production_verifications WHERE verification_key={PH}", (str(key or ""),))
        row = c.fetchone()
    finally:
        conn.close()
    if not row:
        return None
    try:
        details = json.loads(row[3] or "{}")
        if not isinstance(details, dict): details = {}
    except Exception:
        logging.getLogger(__name__).debug("Handled exception in get; fallback applied (handler 81)")
        details = {}
    return {"key": row[0], "status": row[1], "event_at": row[2], "details": details, "updated_at": row[4]}


def public_summary() -> dict:
    """Return technical-only status safe for the authenticated Admin dashboard."""
    keys = ("email_delivery", "error_monitoring")
    return {key: get(key) for key in keys}
