"""Research-version freeze for reproducible SymptoSense studies.

The freeze records the application version plus a SHA-256 signature of the core
symptom-triage engine. It does not claim clinical validity. Its purpose is to
make it visible if the evaluated algorithm changes after data collection starts.
"""
from __future__ import annotations
import logging

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import db

PH = db.PH
BASE_DIR = Path(__file__).resolve().parent
import versioning

APP_VERSION = os.environ.get("APP_VERSION", versioning.APP_VERSION)
DEFAULT_STUDY_VERSION = os.environ.get("RESEARCH_STUDY_VERSION", "SS-RV-1.0").strip() or "SS-RV-1.0"
CORE_FILES = (
    # Conservative reproducibility policy: include the complete web request layer
    # because red-flag handling, source augmentation, gating and result shaping
    # also live in webapp.py. A UI-only webapp change may therefore invalidate a
    # freeze, which is intentionally safer than silently mixing study algorithms.
    "webapp.py",
    "analysis_core.py",
    "medical_knowledge.py",
    "ml_diagnosis.py",
    "medication_warnings.py",
)
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
        serial = "SERIAL PRIMARY KEY" if db.USE_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS research_study_freezes (
                id {serial}, study_version TEXT NOT NULL, app_version TEXT NOT NULL,
                algorithm_hash TEXT NOT NULL, core_files_json TEXT NOT NULL,
                frozen_at TEXT NOT NULL, frozen_by TEXT, active INTEGER NOT NULL DEFAULT 1,
                note TEXT NOT NULL DEFAULT ''
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_research_freeze_active ON research_study_freezes(active,frozen_at)")
        conn.commit(); _SCHEMA_READY = key
    finally:
        conn.close()


def algorithm_signature() -> dict:
    digest = hashlib.sha256(); included = []
    for rel in CORE_FILES:
        path = BASE_DIR / rel
        if not path.exists():
            continue
        raw = path.read_bytes()
        digest.update(rel.encode("utf-8") + b"\0" + raw + b"\0")
        included.append({"file": rel, "sha256": hashlib.sha256(raw).hexdigest()})
    return {"sha256": digest.hexdigest(), "files": included}


def active_freeze() -> dict | None:
    init_schema(); conn = db._conn(); c = conn.cursor()
    try:
        c.execute("SELECT id,study_version,app_version,algorithm_hash,core_files_json,frozen_at,frozen_by,active,note FROM research_study_freezes WHERE active=1 ORDER BY id DESC LIMIT 1")
        row = c.fetchone()
    finally:
        conn.close()
    if not row:
        return None
    try: files = json.loads(row[4] or "[]")
    except Exception: logging.getLogger(__name__).debug("Handled exception in active_freeze; fallback applied (handler 83)"); files = []
    return {"id":int(row[0]),"study_version":row[1],"app_version":row[2],"algorithm_hash":row[3],"core_files":files,"frozen_at":row[5],"frozen_by":row[6],"active":bool(row[7]),"note":row[8] or ""}


def freeze_current(admin_id=None, study_version: str | None = None, note: str = "") -> dict:
    init_schema(); existing = active_freeze()
    if existing:
        return status()
    sig = algorithm_signature(); version = str(study_version or DEFAULT_STUDY_VERSION).strip()[:80] or DEFAULT_STUDY_VERSION
    now = _now(); conn = db._conn(); c = conn.cursor()
    try:
        c.execute(
            f"INSERT INTO research_study_freezes(study_version,app_version,algorithm_hash,core_files_json,frozen_at,frozen_by,active,note) VALUES({','.join([PH]*8)})",
            (version, APP_VERSION, sig["sha256"], json.dumps(sig["files"], separators=(",", ":")), now, str(admin_id or "")[:80], 1, str(note or "")[:500]),
        )
        conn.commit()
    finally:
        conn.close()
    return status()


def status() -> dict:
    current = algorithm_signature(); frozen = active_freeze()
    if not frozen:
        return {
            "frozen": False, "study_version": DEFAULT_STUDY_VERSION, "app_version": APP_VERSION,
            "current_algorithm_hash": current["sha256"], "integrity_ok": None,
            "detail": "Research algorithm version has not been frozen yet.",
        }
    integrity = bool(frozen.get("algorithm_hash") == current["sha256"] and frozen.get("app_version") == APP_VERSION)
    return {
        **frozen,
        "frozen": True,
        "current_app_version": APP_VERSION,
        "current_algorithm_hash": current["sha256"],
        "integrity_ok": integrity,
        "detail": "Frozen study version matches current triage engine." if integrity else "Current app/triage engine differs from the frozen study version.",
    }


def official_versions() -> tuple[str | None, str | None]:
    """Return the currently frozen study/app versions only when integrity matches."""
    st = status()
    if not (st.get("frozen") and st.get("integrity_ok")):
        return None, None
    return str(st.get("study_version") or ""), str(st.get("app_version") or "")


def record_matches_active_freeze(study_version, app_version) -> bool:
    expected_study, expected_app = official_versions()
    return bool(expected_study and expected_app and str(study_version or "") == expected_study and str(app_version or "") == expected_app)


def record_metadata() -> tuple[str, str]:
    """Version tags written to research-eligible analysis rows."""
    st = status()
    if st.get("frozen") and st.get("integrity_ok"):
        return str(st.get("study_version") or DEFAULT_STUDY_VERSION), str(st.get("app_version") or APP_VERSION)
    if st.get("frozen"):
        # Never silently label changed code as if it were the frozen version.
        return "UNFROZEN-CHANGED", APP_VERSION
    return "UNFROZEN", APP_VERSION
