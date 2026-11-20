"""Admin session-control helpers.

Flask uses signed client-side sessions in this project.  A server-side epoch lets
an Admin invalidate every previously issued Admin session without storing session
contents or device identifiers.
"""
from __future__ import annotations

from datetime import datetime, timezone

import db

PH = db.PH
_SCHEMA_READY = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_schema() -> None:
    global _SCHEMA_READY
    key = db._database_identity() if hasattr(db, "_database_identity") else (db.USE_POSTGRES, getattr(db, "DATABASE_URL", ""), getattr(db, "DB_PATH", ""))
    if _SCHEMA_READY == key:
        return
    db.init_db(); conn = db._conn(); c = conn.cursor()
    try:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS ss_admin_session_control (
                user_id INTEGER PRIMARY KEY,
                session_epoch INTEGER NOT NULL DEFAULT 1,
                forced_logout_at TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit(); _SCHEMA_READY = key
    finally:
        conn.close()


def current_epoch(user_id: int) -> int:
    init_schema(); uid = int(user_id); conn = db._conn(); c = conn.cursor()
    try:
        c.execute(f"SELECT session_epoch FROM ss_admin_session_control WHERE user_id={PH}", (uid,))
        row = c.fetchone()
        if row:
            return max(1, int(row[0] or 1))
        now = _now()
        if db.USE_POSTGRES:
            c.execute(
                f"INSERT INTO ss_admin_session_control(user_id,session_epoch,forced_logout_at,updated_at) VALUES({','.join([PH]*4)}) ON CONFLICT(user_id) DO NOTHING",
                (uid, 1, None, now),
            )
        else:
            c.execute(
                f"INSERT OR IGNORE INTO ss_admin_session_control(user_id,session_epoch,forced_logout_at,updated_at) VALUES({','.join([PH]*4)})",
                (uid, 1, None, now),
            )
        conn.commit()
        return 1
    finally:
        conn.close()


def rotate_epoch(user_id: int) -> int:
    """Invalidate every Admin session issued under the previous epoch."""
    init_schema(); uid = int(user_id); old = current_epoch(uid); new = old + 1; now = _now()
    conn = db._conn(); c = conn.cursor()
    try:
        if db.USE_POSTGRES:
            c.execute(
                f"INSERT INTO ss_admin_session_control(user_id,session_epoch,forced_logout_at,updated_at) VALUES({','.join([PH]*4)}) "
                "ON CONFLICT(user_id) DO UPDATE SET session_epoch=EXCLUDED.session_epoch,forced_logout_at=EXCLUDED.forced_logout_at,updated_at=EXCLUDED.updated_at",
                (uid, new, now, now),
            )
        else:
            c.execute(
                f"INSERT INTO ss_admin_session_control(user_id,session_epoch,forced_logout_at,updated_at) VALUES({','.join([PH]*4)}) "
                "ON CONFLICT(user_id) DO UPDATE SET session_epoch=excluded.session_epoch,forced_logout_at=excluded.forced_logout_at,updated_at=excluded.updated_at",
                (uid, new, now, now),
            )
        conn.commit(); return new
    finally:
        conn.close()


def status(user_id: int) -> dict:
    init_schema(); uid = int(user_id); epoch = current_epoch(uid); conn = db._conn(); c = conn.cursor()
    try:
        c.execute(f"SELECT forced_logout_at,updated_at FROM ss_admin_session_control WHERE user_id={PH}", (uid,))
        row = c.fetchone() or (None, None)
    finally:
        conn.close()
    return {"session_epoch": epoch, "forced_logout_at": row[0], "updated_at": row[1]}
