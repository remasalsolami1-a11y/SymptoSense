"""Privacy-by-design consent, user data controls, doctor handoff, and anonymous analytics.

This module never treats aggregate associations as medical causality. Consent logs contain
no health content. Temporary handoff links store only the user-selected summary payload.
"""
from __future__ import annotations
import logging

import base64
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import threading
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import db
import research_study

PH = db.PH
CONSENT_VERSION = os.environ.get("CONSENT_VERSION", "2.1")
PRIVACY_POLICY_VERSION = os.environ.get("PRIVACY_POLICY_VERSION", "2.1")
try:
    PRIVACY_THRESHOLD = max(3, min(20, int(os.environ.get("ANALYTICS_PRIVACY_THRESHOLD", "5") or 5)))
except (TypeError, ValueError):
    PRIVACY_THRESHOLD = 5
_EPHEMERAL_CONSENT_SECRET = secrets.token_bytes(32)
# This project does not currently train/fine-tune an AI model from user health records.
AI_IMPROVEMENT_ACTIVE = False
# Keyed by db._database_identity() (see medical_knowledge.py / db.py for the
# same pattern) so a different database within the same process is detected.
_SCHEMA_READY = None
_SCHEMA_LOCK = threading.Lock()


def _now():
    return datetime.now(timezone.utc).isoformat()


def _secret():
    configured = os.environ.get("CONSENT_HASH_SECRET") or os.environ.get("WEB_SECRET")
    return configured.encode() if configured else _EPHEMERAL_CONSENT_SECRET


def _subject_hash(subject_key: str) -> str:
    return hmac.new(_secret(), str(subject_key or "guest").encode(), hashlib.sha256).hexdigest()


def _token_hash(token: str) -> str:
    return hashlib.sha256((token or "").encode()).hexdigest()


def _rows(c):
    cols = [d[0] for d in c.description]
    return [dict(zip(cols, row)) for row in c.fetchall()]


def _existing_tables(c) -> set[str]:
    if db.USE_POSTGRES:
        c.execute("SELECT tablename FROM pg_tables WHERE schemaname=current_schema()")
        return {str(r[0]) for r in c.fetchall()}
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {str(r[0]) for r in c.fetchall()}


def _cols_for_table(c, table: str) -> set[str]:
    if db.USE_POSTGRES:
        c.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s", (table,))
        return {r[0] for r in c.fetchall()}
    c.execute(f"PRAGMA table_info({table})")
    return {r[1] for r in c.fetchall()}


def _init_schema_unlocked():
    """Ensure privacy tables exist once per application process.

    The app initializes schemas at startup. Re-running the full database DDL on
    every consent/status request adds unnecessary production latency,
    especially when PostgreSQL is hosted remotely.
    """
    global _SCHEMA_READY
    current_key = db._database_identity()
    if _SCHEMA_READY == current_key:
        return
    db.init_db()
    research_study.init_schema()
    conn = db._conn(); c = conn.cursor()
    serial = "SERIAL PRIMARY KEY" if db.USE_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"
    try:
        c.execute("""
            CREATE TABLE IF NOT EXISTS ss_consent_state (
                subject_hash TEXT PRIMARY KEY,
                user_id INTEGER,
                service_usage INTEGER NOT NULL DEFAULT 0,
                analytics_research INTEGER NOT NULL DEFAULT 0,
                research_participation INTEGER NOT NULL DEFAULT 0,
                consent_version TEXT NOT NULL,
                privacy_policy_version TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS ss_consent_log (
                id {serial}, subject_hash TEXT NOT NULL, user_id INTEGER,
                consent_type TEXT NOT NULL, consent_status TEXT NOT NULL,
                consent_version TEXT NOT NULL, privacy_policy_version TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_consent_log_subject ON ss_consent_log(subject_hash,timestamp)")
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS ss_privacy_events (
                id {serial}, subject_hash TEXT NOT NULL, action TEXT NOT NULL,
                metadata TEXT, timestamp TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_privacy_events_time ON ss_privacy_events(timestamp)")
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS ss_handoff_links (
                id {serial}, owner_hash TEXT NOT NULL, token_hash TEXT UNIQUE NOT NULL,
                payload_json TEXT NOT NULL, created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL, revoked_at TEXT
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_handoff_exp ON ss_handoff_links(expires_at)")
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS ss_safeid_cards (
                id {serial}, owner_hash TEXT NOT NULL, account_user_id INTEGER NOT NULL,
                subject_type TEXT NOT NULL DEFAULT 'self', subject_id INTEGER NOT NULL DEFAULT 0,
                token_hash TEXT UNIQUE NOT NULL, token_salt TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1, config_json TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(owner_hash, subject_type, subject_id)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_safeid_owner ON ss_safeid_cards(owner_hash,subject_type,subject_id)")
        safeid_cols = _cols_for_table(c, "ss_safeid_cards")
        if "last_alert_at" not in safeid_cols:
            c.execute("ALTER TABLE ss_safeid_cards ADD COLUMN last_alert_at TEXT")
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS ss_safeid_access (
                id {serial}, card_id INTEGER NOT NULL, mode TEXT NOT NULL,
                action TEXT NOT NULL, created_at TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_safeid_access_card_time ON ss_safeid_access(card_id,created_at)")
        # Mark whether an analysis was eligible for optional health analytics at collection time.
        if db.USE_POSTGRES:
            c.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s", ("records",))
            cols = {r[0] for r in c.fetchall()}
        else:
            c.execute("PRAGMA table_info(records)")
            cols = {r[1] for r in c.fetchall()}
        # Backward-compatible consent migration. Research participation is
        # intentionally separate from optional product analytics so scientific
        # research never relies on an analytics toggle. Existing users are not
        # retroactively opted into research.
        consent_cols = _cols_for_table(c, "ss_consent_state")
        if "research_participation" not in consent_cols:
            c.execute("ALTER TABLE ss_consent_state ADD COLUMN research_participation INTEGER NOT NULL DEFAULT 0")
        if "analytics_eligible" not in cols:
            c.execute("ALTER TABLE records ADD COLUMN analytics_eligible INTEGER NOT NULL DEFAULT 0")
        if "research_eligible" not in cols:
            c.execute("ALTER TABLE records ADD COLUMN research_eligible INTEGER NOT NULL DEFAULT 0")
        if "research_study_version" not in cols:
            c.execute("ALTER TABLE records ADD COLUMN research_study_version TEXT")
        if "research_app_version" not in cols:
            c.execute("ALTER TABLE records ADD COLUMN research_app_version TEXT")
        # Public-pilot research scope: adults only. Existing stale eligibility
        # flags from earlier versions are removed for minors/unknown age.
        c.execute("UPDATE records SET research_eligible=0 WHERE research_eligible=1 AND (age IS NULL OR age < 18)")
        conn.commit()
        _SCHEMA_READY = current_key
    finally:
        conn.close()


def init_schema():
    """Thread-safe schema initialization for startup and first concurrent requests."""
    current_key = db._database_identity()
    if _SCHEMA_READY == current_key:
        return
    with _SCHEMA_LOCK:
        # A different request may have completed the migration while this
        # caller was waiting for the process-local schema lock.
        if _SCHEMA_READY == current_key:
            return
        _init_schema_unlocked()


def get_consent(subject_key: str, user_id=None) -> dict:
    init_schema(); sh = _subject_hash(subject_key)
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute(
            "SELECT service_usage,analytics_research,research_participation,consent_version,privacy_policy_version,updated_at "
            "FROM ss_consent_state WHERE subject_hash=%s" % PH,
            (sh,),
        )
        row = c.fetchone()
    finally:
        conn.close()
    if not row:
        return {
            "service_usage": False, "analytics_research": False, "research_participation": False,
            "ai_improvement": False, "consent_version": CONSENT_VERSION,
            "privacy_policy_version": PRIVACY_POLICY_VERSION, "needs_review": True, "updated_at": None,
        }
    return {
        "service_usage": bool(row[0]), "analytics_research": bool(row[1]),
        "research_participation": bool(row[2]), "ai_improvement": False,
        "consent_version": row[3], "privacy_policy_version": row[4], "updated_at": row[5],
        "needs_review": row[3] != CONSENT_VERSION or row[4] != PRIVACY_POLICY_VERSION,
    }


def _log_consent(c, sh, user_id, consent_type, status):
    c.execute(
        "INSERT INTO ss_consent_log(subject_hash,user_id,consent_type,consent_status,consent_version,privacy_policy_version,timestamp) "
        f"VALUES ({','.join([PH]*7)})",
        (sh, int(user_id) if user_id else None, consent_type, status, CONSENT_VERSION, PRIVACY_POLICY_VERSION, _now()),
    )


def log_privacy_event(subject_key: str, action: str, metadata=None):
    init_schema(); sh = _subject_hash(subject_key)
    safe = {}
    for k, v in (metadata or {}).items():
        if k in {"status", "consent_type", "format", "scope", "period", "count"}:
            safe[k] = v
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute("INSERT INTO ss_privacy_events(subject_hash,action,metadata,timestamp) VALUES(%s,%s,%s,%s)".replace("%s", PH),
                  (sh, str(action)[:80], json.dumps(safe, ensure_ascii=False), _now()))
        conn.commit()
    finally:
        conn.close()


def save_consent(subject_key: str, user_id, service_usage: bool, analytics_research: bool, research_participation=None) -> dict:
    """Persist service, analytics, and scientific-research consent atomically.

    ``research_participation=None`` preserves the previous research choice. This
    matters for older callers and for privacy-center actions that change only
    analytics. Scientific research consent is never inferred from analytics.
    """
    init_schema()
    sh = _subject_hash(subject_key)
    uid = int(user_id) if user_id else None
    service = bool(service_usage)
    analytics = bool(analytics_research)
    now = _now()
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute(
            "SELECT service_usage,analytics_research,research_participation,consent_version,privacy_policy_version,updated_at "
            "FROM ss_consent_state WHERE subject_hash=%s" % PH,
            (sh,),
        )
        row = c.fetchone()
        previous_service = bool(row[0]) if row else False
        previous_analytics = bool(row[1]) if row else False
        previous_research = bool(row[2]) if row else False
        previous_updated_at = row[5] if row else None
        research = previous_research if research_participation is None else bool(research_participation)

        vals = (sh, uid, int(service), int(analytics), int(research), CONSENT_VERSION, PRIVACY_POLICY_VERSION, now)
        if db.USE_POSTGRES:
            c.execute(
                "INSERT INTO ss_consent_state(subject_hash,user_id,service_usage,analytics_research,research_participation,consent_version,privacy_policy_version,updated_at) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(subject_hash) DO UPDATE SET "
                "user_id=EXCLUDED.user_id,service_usage=EXCLUDED.service_usage,analytics_research=EXCLUDED.analytics_research,"
                "research_participation=EXCLUDED.research_participation,consent_version=EXCLUDED.consent_version,"
                "privacy_policy_version=EXCLUDED.privacy_policy_version,updated_at=EXCLUDED.updated_at",
                vals,
            )
        else:
            c.execute(
                "INSERT INTO ss_consent_state(subject_hash,user_id,service_usage,analytics_research,research_participation,consent_version,privacy_policy_version,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(subject_hash) DO UPDATE SET "
                "user_id=excluded.user_id,service_usage=excluded.service_usage,analytics_research=excluded.analytics_research,"
                "research_participation=excluded.research_participation,consent_version=excluded.consent_version,"
                "privacy_policy_version=excluded.privacy_policy_version,updated_at=excluded.updated_at",
                vals,
            )

        _log_consent(c, sh, uid, "service_usage", "granted" if service else ("withdrawn" if previous_service else "declined"))
        _log_consent(c, sh, uid, "analytics_research", "granted" if analytics else ("withdrawn" if previous_analytics else "declined"))
        if research_participation is not None:
            _log_consent(c, sh, uid, "research_participation", "granted" if research else ("withdrawn" if previous_research else "declined"))

        def add_event(action, metadata):
            safe = {}
            for k, v in (metadata or {}).items():
                if k in {"status", "consent_type", "format", "scope", "period", "count"}:
                    safe[k] = v
            c.execute(
                "INSERT INTO ss_privacy_events(subject_hash,action,metadata,timestamp) VALUES(%s,%s,%s,%s)".replace("%s", PH),
                (sh, str(action)[:80], json.dumps(safe, ensure_ascii=False), _now()),
            )

        add_event("privacy_settings_changed", {"status": "saved"})
        if previous_analytics != analytics:
            add_event("analytics_consent_granted" if analytics else "analytics_consent_withdrawn", {"status": "granted" if analytics else "withdrawn"})
        elif not analytics and not previous_updated_at:
            add_event("analytics_consent_declined", {"status": "declined"})
        if research_participation is not None:
            if previous_research != research:
                add_event("research_consent_granted" if research else "research_consent_withdrawn", {"status": "granted" if research else "withdrawn"})
            elif not research and not previous_updated_at:
                add_event("research_consent_declined", {"status": "declined"})
        if previous_service != service:
            add_event("service_consent_granted" if service else "service_consent_withdrawn", {"status": "granted" if service else "withdrawn"})

        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()

    return {
        "service_usage": service, "analytics_research": analytics, "research_participation": research,
        "ai_improvement": False, "consent_version": CONSENT_VERSION,
        "privacy_policy_version": PRIVACY_POLICY_VERSION, "updated_at": now, "needs_review": False,
    }


def withdraw_analytics(subject_key: str, user_id=None) -> dict:
    cur = get_consent(subject_key, user_id)
    updated = save_consent(subject_key, user_id, cur.get("service_usage", False), False, None)
    uh = db._hash_user(subject_key)
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute("UPDATE records SET analytics_eligible=0 WHERE user_hash=%s" % PH, (uh,))
        conn.commit()
    finally:
        conn.close()
    return updated


def withdraw_research(subject_key: str, user_id=None) -> dict:
    """Withdraw future scientific-research use and remove retained records from future research exports."""
    cur = get_consent(subject_key, user_id)
    updated = save_consent(
        subject_key, user_id, cur.get("service_usage", False),
        cur.get("analytics_research", False), False,
    )
    uh = db._hash_user(subject_key)
    conn = db._conn(); c = conn.cursor(); excluded = 0
    try:
        c.execute("UPDATE records SET research_eligible=0 WHERE user_hash=%s AND COALESCE(research_eligible,0)=1" % PH, (uh,))
        excluded = max(0, int(c.rowcount or 0))
        conn.commit()
    finally:
        conn.close()
    log_privacy_event(subject_key, "research_records_excluded", {"status":"completed", "count":excluded})
    updated["excluded_research_records"] = excluded
    return updated


def consent_history(subject_key: str, limit=50):
    init_schema(); sh = _subject_hash(subject_key)
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute("SELECT consent_type,consent_status,consent_version,privacy_policy_version,timestamp FROM ss_consent_log WHERE subject_hash=%s ORDER BY timestamp DESC LIMIT %s" % (PH, PH), (sh, int(limit)))
        rows = c.fetchall()
    finally:
        conn.close()
    return [{"consent_type":r[0],"status":r[1],"consent_version":r[2],"privacy_policy_version":r[3],"timestamp":r[4]} for r in rows]


def set_record_analytics_eligibility(record_id: int, eligible: bool):
    init_schema(); conn = db._conn(); c = conn.cursor()
    try:
        c.execute("UPDATE records SET analytics_eligible=%s WHERE id=%s" % (PH, PH), (int(bool(eligible)), int(record_id)))
        conn.commit()
    finally:
        conn.close()


def _record_is_adult(c, record_id: int) -> bool:
    """Research export is restricted to adults (18+) for this pilot.

    Age is evaluated at the record level so signed-in and guest analyses follow
    the same rule. Missing/non-numeric age is conservatively treated as
    ineligible for research, while service usage remains unaffected.
    """
    c.execute("SELECT age FROM records WHERE id=%s" % PH, (int(record_id),))
    row = c.fetchone()
    if not row or row[0] in (None, ""):
        return False
    try:
        return int(row[0]) >= 18
    except (TypeError, ValueError):
        return False


def set_record_research_eligibility(record_id: int, eligible: bool):
    init_schema(); conn = db._conn(); c = conn.cursor()
    try:
        adult = _record_is_adult(c, record_id)
        allowed = bool(eligible) and adult
        study_version, app_version = research_study.record_metadata() if allowed else (None, None)
        c.execute(
            "UPDATE records SET research_eligible=%s,research_study_version=%s,research_app_version=%s WHERE id=%s" % (PH, PH, PH, PH),
            (int(allowed), study_version, app_version, int(record_id)),
        )
        conn.commit()
    finally:
        conn.close()


def set_record_consent_eligibility(record_id: int, analytics: bool, research: bool):
    init_schema(); conn = db._conn(); c = conn.cursor()
    try:
        adult = _record_is_adult(c, record_id)
        research_flag = int(bool(research) and adult)
        study_version, app_version = research_study.record_metadata() if research_flag else (None, None)
        c.execute(
            "UPDATE records SET analytics_eligible=%s,research_eligible=%s,research_study_version=%s,research_app_version=%s WHERE id=%s" % (PH, PH, PH, PH, PH),
            (int(bool(analytics)), research_flag, study_version, app_version, int(record_id)),
        )
        conn.commit()
    finally:
        conn.close()


def _medication_owner_hashes(account_user_id: int, data_owner_key: str) -> tuple[str, ...]:
    """Return current + legacy medication owner hashes for one account.

    Medication reminders intentionally use the numeric account id, while the
    rest of the health record uses an ``account-<id>`` owner key. Older privacy
    code assumed those hashes were interchangeable, which hid medication rows
    from export/delete controls. Keep both so migrations remain lossless.
    """
    values = [db._hash_user(int(account_user_id)), db._hash_user(data_owner_key)]
    return tuple(dict.fromkeys(str(v) for v in values if v))


def stored_data_types(account_user_id: int, data_owner_key: str) -> dict:
    """Report only categories that are actually present for this account."""
    init_schema(); uid=int(account_user_id); uh=db._hash_user(data_owner_key); sh=_subject_hash(data_owner_key)
    med_hashes=_medication_owner_hashes(uid, data_owner_key)
    conn=db._conn(); c=conn.cursor()
    def exists(sql, params):
        try:
            c.execute(sql, params); return bool(c.fetchone()[0])
        except Exception:
            logging.getLogger(__name__).warning("Handled exception in exists; fallback applied (handler 401)")
            return False
    def table_exists(name):
        try:
            return name in _existing_tables(c)
        except Exception:
            return False
    try:
        med_present=False
        if table_exists("med_plans"):
            marks=','.join([PH]*len(med_hashes))
            med_present = exists(f"SELECT COUNT(*) FROM med_plans WHERE user_hash IN ({marks})", med_hashes)
        if not med_present and table_exists("med_reminders"):
            med_present = exists(f"SELECT COUNT(*) FROM med_reminders WHERE user_id={PH}", (uid,))
        if not med_present and table_exists("medication_reminders"):
            med_present = exists(f"SELECT COUNT(*) FROM medication_reminders WHERE user_id={PH}", (uid,))
        if not med_present and table_exists("med_logs"):
            marks=','.join([PH]*len(med_hashes))
            med_present = exists(f"SELECT COUNT(*) FROM med_logs WHERE user_hash IN ({marks})", med_hashes)
        return {
            "profile_information": bool(db.get_ss_user(uid)),
            "health_profile": exists("SELECT COUNT(*) FROM ss_health_profiles WHERE user_id=%s" % PH,(uid,)),
            "symptom_information": exists("SELECT COUNT(*) FROM records WHERE user_hash=%s" % PH,(uh,)),
            "analysis_history": exists("SELECT COUNT(*) FROM records WHERE user_hash=%s" % PH,(uh,)),
            "medication_reminders": bool(med_present),
            "assistant_history": exists("SELECT COUNT(*) FROM ss_chat_history WHERE user_id=%s" % PH,(uid,)),
            "reports": exists("SELECT COUNT(*) FROM ss_handoff_links WHERE owner_hash=%s" % PH,(uh,)),
            "safeid_cards": exists("SELECT COUNT(*) FROM ss_safeid_cards WHERE owner_hash=%s" % PH,(sh,)),
        }
    finally:
        conn.close()

def delete_health_data(account_user_id: int, data_owner_key: str) -> dict:
    """Delete health content while retaining the account and minimal consent/audit rows.

    V215 explicitly covers both health-owner hashes and numeric-account
    medication tables so privacy deletion cannot leave reminders, delivery
    tokens, Telegram links, history, or tombstones behind.
    """
    init_schema(); uh = db._hash_user(data_owner_key); sh = _subject_hash(data_owner_key); uid = int(account_user_id)
    med_hashes = _medication_owner_hashes(uid, data_owner_key)
    conn = db._conn(); c = conn.cursor(); deleted = 0
    try:
        existing = _existing_tables(c)
        plan_ids = []
        push_endpoints = []
        if "med_plans" in existing:
            marks=','.join([PH]*len(med_hashes))
            c.execute(f"SELECT id FROM med_plans WHERE user_hash IN ({marks})", med_hashes)
            plan_ids = [int(r[0]) for r in c.fetchall()]
        if "push_subscriptions" in existing:
            c.execute(f"SELECT endpoint FROM push_subscriptions WHERE user_hash={PH}", (uh,))
            push_endpoints = [str(r[0]) for r in c.fetchall() if r and r[0]]
        if "push_delivery_log" in existing:
            for endpoint in push_endpoints:
                c.execute(f"DELETE FROM push_delivery_log WHERE endpoint={PH}", (endpoint,)); deleted += max(0,int(c.rowcount or 0))
            for plan_id in plan_ids:
                c.execute(f"DELETE FROM push_delivery_log WHERE plan_id={PH}", (plan_id,)); deleted += max(0,int(c.rowcount or 0))

        # General account-owned health tables use the stable account-* owner key.
        for table, col in [
            ("results","user_hash"),("records","user_hash"),("profiles","user_hash"),
            ("blood_tests","user_hash"),("daily_checkins","user_hash"),("ss_daily_checkins","user_hash"),
            ("feedback","user_hash"),("followups","user_hash"),("visits","user_hash"),
            ("assistant_feedback","user_hash"),("family_members","user_hash"),
            ("push_subscriptions","user_hash"),("push_action_tokens","user_hash"),
            ("push_delivery_receipts","user_hash"),("ss_analysis_links","user_hash"),
            ("symptom_followups","user_hash"),("vitals","user_hash"),
        ]:
            if table in existing and col in _cols_for_table(c, table):
                c.execute(f"DELETE FROM {table} WHERE {col}={PH}", (uh,)); deleted += max(0,int(c.rowcount or 0))

        # Medication hash tables may contain either numeric-account hashes
        # (current) or account-* hashes (legacy). Remove both.
        marks=','.join([PH]*len(med_hashes))
        for table in ("med_logs","med_plans","med_snoozes","med_plan_tombstones","med_notification_settings"):
            if table in existing and "user_hash" in _cols_for_table(c, table):
                c.execute(f"DELETE FROM {table} WHERE user_hash IN ({marks})", med_hashes); deleted += max(0,int(c.rowcount or 0))

        # Numeric-account medication tables.
        for table in ("med_reminders","medication_reminders","med_reminder_settings",
                      "med_email_actions","med_email_deliveries","med_telegram_links",
                      "med_telegram_deliveries"):
            if table in existing and "user_id" in _cols_for_table(c, table):
                c.execute(f"DELETE FROM {table} WHERE user_id={PH}", (uid,)); deleted += max(0,int(c.rowcount or 0))

        for table in ("ss_health_profiles","ss_chat_history","ss_user_preferences"):
            if table in existing:
                c.execute(f"DELETE FROM {table} WHERE user_id={PH}", (uid,)); deleted += max(0,int(c.rowcount or 0))
        if "ss_handoff_links" in existing:
            c.execute(f"DELETE FROM ss_handoff_links WHERE owner_hash={PH}", (uh,)); deleted += max(0,int(c.rowcount or 0))
        if "ss_safeid_cards" in existing:
            c.execute(f"SELECT id FROM ss_safeid_cards WHERE owner_hash={PH}", (sh,))
            safeid_ids = [int(r[0]) for r in c.fetchall()]
            if "ss_safeid_access" in existing:
                for card_id in safeid_ids:
                    c.execute(f"DELETE FROM ss_safeid_access WHERE card_id={PH}", (card_id,)); deleted += max(0,int(c.rowcount or 0))
            c.execute(f"DELETE FROM ss_safeid_cards WHERE owner_hash={PH}", (sh,)); deleted += max(0,int(c.rowcount or 0))
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()
    log_privacy_event(data_owner_key, "health_data_deletion_requested", {"status":"completed", "count": deleted})
    return {"deleted_items": deleted}

def purge_consent_identity(subject_key: str, user_id=None) -> dict:
    """Remove consent/privacy identity rows linked to a deleted account."""
    init_schema(); sh = _subject_hash(subject_key); uid = int(user_id) if user_id else None
    conn = db._conn(); c = conn.cursor(); deleted = 0
    try:
        existing = _existing_tables(c)
        for table in ("ss_consent_log", "ss_consent_state", "ss_privacy_events"):
            if table in existing:
                c.execute(f"DELETE FROM {table} WHERE subject_hash={PH}", (sh,)); deleted += max(0,int(c.rowcount or 0))
        # If a legacy consent log uses a user id without the current subject hash,
        # remove that linkage as part of full account deletion.
        if uid is not None and "ss_consent_log" in existing:
            c.execute(f"DELETE FROM ss_consent_log WHERE user_id={PH}", (uid,)); deleted += max(0,int(c.rowcount or 0))
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()
    return {"deleted_consent_rows": deleted}


def _safe_user_export(account_user_id: int, data_owner_key: str) -> dict:
    """Return only data belonging to the requester. Never include password hashes/tokens/secrets."""
    init_schema(); uid = int(account_user_id)
    user = db.get_ss_user(uid) or {}
    out = {
        "generated_at": _now(),
        "account": {k:user.get(k) for k in ("id","email","name","role","status","created_at","last_login")},
        "health_profile": db.load_health_profile(uid) or {},
        "privacy_settings": db.load_privacy_settings(uid) or {},
        "consent": get_consent(data_owner_key, uid),
        "consent_history": consent_history(data_owner_key),
        "analysis_history": [],
        "assistant_history": db.get_chat_history(uid, limit=500),
        "medication_reminders": [],
        "medication_history": [],
    }
    try:
        records = db.get_records(data_owner_key, limit=1000)
        for r in records:
            item = dict(r); result = db.load_result(data_owner_key, r.get("id")) or {}
            item["result"] = result
            out["analysis_history"].append(item)
    except Exception:
        logging.getLogger(__name__).debug("Handled exception in _safe_user_export; fallback applied (handler 508)")
        pass
    # Ensure modern medication columns/tables exist before building a portable
    # user export. This is a local import to avoid adding a module-level cycle.
    try:
        import medication_email
        medication_email.init_schema()
    except Exception:
        logging.getLogger(__name__).warning("Medication schema was unavailable during user export", exc_info=True)
    conn = db._conn(); c = conn.cursor()
    try:
        try:
            med_hashes = _medication_owner_hashes(uid, data_owner_key)
            marks = ','.join([PH] * len(med_hashes))
            c.execute(f"SELECT id,member_id,med_name,dose,times,frequency,start_date,end_date,days_of_week,timezone,notes,active,created FROM med_plans WHERE user_hash IN ({marks}) ORDER BY id", med_hashes)
            out["medication_reminders"] = _rows(c)
            if "med_logs" in _existing_tables(c):
                c.execute(f"SELECT plan_id,member_id,log_date,log_time,status,created FROM med_logs WHERE user_hash IN ({marks}) ORDER BY id", med_hashes)
                out["medication_history"] = _rows(c)
        except Exception:
            logging.getLogger(__name__).debug("Handled exception in _safe_user_export; fallback applied (handler 515)")
            pass
    finally:
        conn.close()
    return out


def user_export_bytes(account_user_id: int, data_owner_key: str) -> io.BytesIO:
    raw = json.dumps(_safe_user_export(account_user_id, data_owner_key), ensure_ascii=False, indent=2, default=str).encode("utf-8")
    log_privacy_event(data_owner_key, "data_export_requested", {"status":"completed", "format":"json"})
    return io.BytesIO(raw)


def _parse_dt(v):
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError, OverflowError):
        logging.getLogger(__name__).debug("Handled exception in _parse_dt; fallback applied (handler 531)")
        return None


def create_handoff(owner_key: str, record_id: int, selected: dict, previous_ids=None, expires_minutes=60) -> dict:
    init_schema(); result = db.load_result(owner_key, int(record_id))
    if not result:
        raise PermissionError("analysis_not_found")
    expires_minutes = int(expires_minutes)
    if expires_minutes not in (15, 60, 1440):
        raise ValueError("invalid_expiration")
    allowed = {"symptoms","duration","severity","location","notes","previous_assessments","medications"}
    selected = {k: bool(v) for k,v in (selected or {}).items() if k in allowed}
    if not any(selected.values()):
        raise ValueError("select_at_least_one_field")
    payload = {"created_at": _now(), "lang": result.get("lang") or "ar", "sections": {}}
    sec = payload["sections"]
    if selected.get("symptoms"): sec["symptoms"] = result.get("symptoms") or []
    if selected.get("duration"): sec["duration"] = result.get("duration") or ""
    if selected.get("severity"): sec["severity"] = result.get("severity")
    if selected.get("location"): sec["location"] = result.get("location") or ""
    if selected.get("notes"): sec["notes"] = result.get("notes") or ""
    if selected.get("medications"): sec["medications"] = result.get("medications") or ""
    if selected.get("previous_assessments"):
        previous=[]
        for rid in (previous_ids or [])[:5]:
            try:
                rid=int(rid); old=db.load_result(owner_key,rid)
            except Exception:
                logging.getLogger(__name__).debug("Handled exception in create_handoff; fallback applied (handler 559)")
                old=None
            if old:
                previous.append({"symptoms":old.get("symptoms") or [],"duration":old.get("duration") or "","severity":old.get("severity"),"risk_level":old.get("risk_level") or old.get("urgency") or ""})
        sec["previous_assessments"] = previous
    # Do not create a valid-looking QR that opens an empty summary.  This can
    # happen when the user selects a field (for example medications) that was
    # not present in the saved analysis.  Keep privacy selection explicit and
    # ask the caller to choose an item that actually contains data.
    if not any(value not in (None, "", []) for value in sec.values()):
        raise ValueError("selected_information_empty")
    token = secrets.token_urlsafe(32); th = _token_hash(token); owner_hash = db._hash_user(owner_key)
    exp = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    conn = db._conn(); c=conn.cursor()
    try:
        c.execute("INSERT INTO ss_handoff_links(owner_hash,token_hash,payload_json,created_at,expires_at,revoked_at) VALUES(%s,%s,%s,%s,%s,%s)".replace("%s",PH),
                  (owner_hash, th, json.dumps(payload, ensure_ascii=False), _now(), exp.isoformat(), None))
        conn.commit()
    finally:
        conn.close()
    log_privacy_event(owner_key, "temporary_health_summary_created", {"status":"completed", "expiration_minutes":expires_minutes})
    return {"token": token, "expires_at": exp.isoformat(), "payload": payload}


def get_handoff(token: str) -> dict | None:
    init_schema(); th = _token_hash(token)
    conn=db._conn(); c=conn.cursor()
    try:
        c.execute("SELECT payload_json,expires_at,revoked_at FROM ss_handoff_links WHERE token_hash=%s" % PH,(th,)); row=c.fetchone()
    finally:
        conn.close()
    if not row: return None
    exp=_parse_dt(row[1]); now=datetime.now(timezone.utc)
    if row[2]: return {"status":"revoked"}
    if not exp or exp <= now: return {"status":"expired"}
    try: payload=json.loads(row[0])
    except Exception: logging.getLogger(__name__).debug("Handled exception in get_handoff; fallback applied (handler 595)"); return None
    return {"status":"active","payload":payload,"expires_at":row[1]}


def revoke_handoff(owner_key: str, token: str) -> bool:
    init_schema(); conn=db._conn(); c=conn.cursor()
    try:
        c.execute("UPDATE ss_handoff_links SET revoked_at=%s WHERE owner_hash=%s AND token_hash=%s AND revoked_at IS NULL" % (PH,PH,PH),
                  (_now(), db._hash_user(owner_key), _token_hash(token)))
        changed = bool(c.rowcount)
        conn.commit()
    finally:
        conn.close()
    if changed:
        log_privacy_event(owner_key, "temporary_health_summary_revoked", {"status":"completed"})
    return changed


def qr_png_data_uri(url: str) -> str:
    try:
        import qrcode
        img=qrcode.make(url); bio=io.BytesIO(); img.save(bio, format="PNG")
        return "data:image/png;base64,"+base64.b64encode(bio.getvalue()).decode("ascii")
    except Exception:
        logging.getLogger(__name__).warning("Handled exception in qr_png_data_uri; fallback applied (handler 618)")
        return ""



# ---- SymptoSense SafeID ---------------------------------------------------
# A persistent privacy-by-design QR card. The QR stores only an opaque bearer
# token. Public views never expose account identifiers, names, email addresses,
# phone numbers, IP addresses, or the underlying database IDs.
_SAFEID_MODES = {"emergency", "assist", "found"}
_SAFEID_ACTIONS = {"view", "contact_alert"}


def _safeid_subject(subject_type="self", subject_id=0):
    st = "member" if str(subject_type or "").lower() == "member" else "self"
    try:
        sid = max(0, int(subject_id or 0)) if st == "member" else 0
    except (TypeError, ValueError):
        sid = 0
    return st, sid


def _safeid_default_config():
    return {
        # Legacy flags are retained for backwards compatibility with cards
        # created before the emergency form became self-contained.
        "share_allergies": False,
        "share_medications": False,
        "share_conditions": False,
        "preferred_language": "",
        "support_needs": "",
        "contact_alert": True,
        # V166: the user writes emergency information directly here instead of
        # having to maintain it in account settings first.
        "emergency_allergies": "",
        "emergency_medications": "",
        "emergency_conditions": "",
        "emergency_note": "",
        "emergency_contact_enabled": False,
        "emergency_contact_name": "",
        "emergency_contact_relation": "",
        "emergency_contact_phone": "",
        "emergency_contact_message": "",
    }


def _safeid_phone(value):
    """Normalize a callable international phone number without guessing broadly.

    Saudi mobile numbers entered as 05XXXXXXXX are normalized to +9665XXXXXXXX.
    International numbers entered with + or 00 retain their country code.
    Invalid/too-short values are discarded instead of being exposed publicly.
    """
    raw = str(value or "").strip()[:40]
    if not raw:
        return ""
    digits = re.sub(r"\D", "", raw)
    if raw.startswith("00") and len(digits) >= 10:
        normalized = "+" + digits[2:]
    elif raw.startswith("+"):
        normalized = "+" + digits
    elif len(digits) == 10 and digits.startswith("05"):
        normalized = "+966" + digits[1:]
    elif len(digits) == 9 and digits.startswith("5"):
        normalized = "+966" + digits
    else:
        # Keep a plausible local/international number callable, but do not
        # invent a country code for non-Saudi numbers.
        normalized = digits
    count = len(re.sub(r"\D", "", normalized))
    return normalized if 8 <= count <= 15 else ""


def _safeid_config(value):
    out = _safeid_default_config()
    if isinstance(value, str):
        try:
            value = json.loads(value or "{}")
        except (TypeError, ValueError, OverflowError):
            value = {}
    if not isinstance(value, dict):
        value = {}
    for key in (
        "share_allergies", "share_medications", "share_conditions",
        "contact_alert", "emergency_contact_enabled",
    ):
        if key in value:
            out[key] = bool(value.get(key))
    # Preserve legacy values so older cards do not lose data on first save.
    out["preferred_language"] = str(value.get("preferred_language") or "").strip()[:100]
    out["support_needs"] = str(value.get("support_needs") or "").strip()[:600]
    out["emergency_allergies"] = str(value.get("emergency_allergies") or "").strip()[:1000]
    out["emergency_medications"] = str(value.get("emergency_medications") or "").strip()[:1000]
    out["emergency_conditions"] = str(value.get("emergency_conditions") or "").strip()[:1000]
    out["emergency_note"] = str(value.get("emergency_note") or "").strip()[:600]
    out["emergency_contact_name"] = str(value.get("emergency_contact_name") or "").strip()[:100]
    out["emergency_contact_relation"] = str(value.get("emergency_contact_relation") or "").strip()[:80]
    out["emergency_contact_phone"] = _safeid_phone(value.get("emergency_contact_phone"))
    out["emergency_contact_message"] = str(value.get("emergency_contact_message") or "").strip()[:320]
    # A direct-call button cannot be enabled without a valid number.
    if not out["emergency_contact_phone"]:
        out["emergency_contact_enabled"] = False
    return out


def _safeid_token(owner_hash: str, salt: str) -> str:
    raw = hmac.new(_secret(), ("safeid|%s|%s" % (owner_hash, salt)).encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _safeid_row_to_dict(row):
    if not row:
        return None
    return {
        "id": int(row[0]), "owner_hash": row[1], "account_user_id": int(row[2]),
        "subject_type": row[3], "subject_id": int(row[4] or 0), "token_hash": row[5],
        "token_salt": row[6], "enabled": bool(row[7]), "config": _safeid_config(row[8]),
        "created_at": row[9], "updated_at": row[10],
    }


def get_or_create_safeid(owner_key: str, account_user_id: int, subject_type="self", subject_id=0) -> dict:
    """Return the owner's SafeID card and a re-derivable opaque token."""
    init_schema()
    if not owner_key or not account_user_id:
        raise ValueError("login_required")
    st, sid = _safeid_subject(subject_type, subject_id)
    oh = _subject_hash(owner_key)
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute(
            "SELECT id,owner_hash,account_user_id,subject_type,subject_id,token_hash,token_salt,enabled,config_json,created_at,updated_at "
            "FROM ss_safeid_cards WHERE owner_hash=%s AND subject_type=%s AND subject_id=%s".replace("%s", PH),
            (oh, st, sid),
        )
        row = c.fetchone()
        if not row:
            salt = secrets.token_urlsafe(18)
            token = _safeid_token(oh, salt)
            now = _now(); cfg = _safeid_default_config()
            vals = (oh, int(account_user_id), st, sid, _token_hash(token), salt, 1, json.dumps(cfg, ensure_ascii=False), now, now)
            try:
                c.execute(
                    "INSERT INTO ss_safeid_cards(owner_hash,account_user_id,subject_type,subject_id,token_hash,token_salt,enabled,config_json,created_at,updated_at) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)".replace("%s", PH), vals,
                )
                conn.commit()
            except Exception:
                # Two first-time requests can race. The database uniqueness
                # constraint is authoritative; after rollback, reuse the card
                # created by the winning request instead of returning a 500.
                conn.rollback()
            c.execute(
                "SELECT id,owner_hash,account_user_id,subject_type,subject_id,token_hash,token_salt,enabled,config_json,created_at,updated_at "
                "FROM ss_safeid_cards WHERE owner_hash=%s AND subject_type=%s AND subject_id=%s".replace("%s", PH),
                (oh, st, sid),
            )
            row = c.fetchone()
            if not row:
                raise RuntimeError("safeid_create_failed")
        card = _safeid_row_to_dict(row)
        token = _safeid_token(card["owner_hash"], card["token_salt"])
        # A stable WEB_SECRET keeps the token stable. If a development secret was
        # changed, rotate safely instead of returning a QR that cannot be looked up.
        expected_hash = _token_hash(token)
        if expected_hash != card["token_hash"]:
            c.execute("UPDATE ss_safeid_cards SET token_hash=%s,updated_at=%s WHERE id=%s".replace("%s", PH),
                      (expected_hash, _now(), card["id"]))
            conn.commit(); card["token_hash"] = expected_hash
        card["token"] = token
        return card
    finally:
        conn.close()


def save_safeid(owner_key: str, account_user_id: int, subject_type="self", subject_id=0, config=None, enabled=None) -> dict:
    card = get_or_create_safeid(owner_key, account_user_id, subject_type, subject_id)
    cfg = _safeid_config(config)
    if enabled is None:
        enabled = bool(card.get("enabled"))
    now = _now(); conn = db._conn(); c = conn.cursor()
    try:
        c.execute("UPDATE ss_safeid_cards SET enabled=%s,config_json=%s,updated_at=%s WHERE id=%s".replace("%s", PH),
                  (1 if enabled else 0, json.dumps(cfg, ensure_ascii=False), now, card["id"]))
        conn.commit()
    finally:
        conn.close()
    log_privacy_event(owner_key, "safeid_settings_changed", {"status": "enabled" if enabled else "paused"})
    return get_or_create_safeid(owner_key, account_user_id, subject_type, subject_id)


def set_safeid_enabled(owner_key: str, account_user_id: int, subject_type="self", subject_id=0, enabled=True) -> dict:
    card = get_or_create_safeid(owner_key, account_user_id, subject_type, subject_id)
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute("UPDATE ss_safeid_cards SET enabled=%s,updated_at=%s WHERE id=%s".replace("%s", PH),
                  (1 if enabled else 0, _now(), card["id"]))
        conn.commit()
    finally:
        conn.close()
    log_privacy_event(owner_key, "safeid_enabled" if enabled else "safeid_paused", {"status": "completed"})
    return get_or_create_safeid(owner_key, account_user_id, subject_type, subject_id)


def rotate_safeid(owner_key: str, account_user_id: int, subject_type="self", subject_id=0) -> dict:
    card = get_or_create_safeid(owner_key, account_user_id, subject_type, subject_id)
    salt = secrets.token_urlsafe(18); token = _safeid_token(card["owner_hash"], salt); now = _now()
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute("UPDATE ss_safeid_cards SET token_salt=%s,token_hash=%s,updated_at=%s WHERE id=%s".replace("%s", PH),
                  (salt, _token_hash(token), now, card["id"]))
        conn.commit()
    finally:
        conn.close()
    log_privacy_event(owner_key, "safeid_rotated", {"status": "completed"})
    return get_or_create_safeid(owner_key, account_user_id, subject_type, subject_id)


def get_safeid_public(token: str) -> dict | None:
    init_schema(); th = _token_hash(str(token or ""))
    if not token or len(str(token)) < 24:
        return None
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute(
            "SELECT id,owner_hash,account_user_id,subject_type,subject_id,token_hash,token_salt,enabled,config_json,created_at,updated_at "
            "FROM ss_safeid_cards WHERE token_hash=%s" % PH, (th,),
        )
        row = c.fetchone()
    finally:
        conn.close()
    card = _safeid_row_to_dict(row)
    if not card or not card.get("enabled"):
        return None
    return card


def _safeid_subject_data(card: dict) -> dict:
    if not card:
        return {}
    uid = int(card.get("account_user_id") or 0)
    if card.get("subject_type") == "member":
        member = db.get_member("account-%s" % uid, int(card.get("subject_id") or 0)) or {}
        return {
            "allergies": member.get("allergies") or "",
            "medications": member.get("medications") or "",
            "conditions": member.get("conditions") or "",
        }
    profile = db.load_health_profile(uid) or {}
    return {
        "allergies": profile.get("allergies") or "",
        "medications": profile.get("medications") or "",
        "conditions": profile.get("health_conditions") or "",
    }


def _safeid_private_terms(card: dict) -> list[str]:
    """Known subject/account names that must never leak through free-text fields."""
    if not card:
        return []
    terms = []
    uid = int(card.get("account_user_id") or 0)
    try:
        user = db.get_ss_user(uid) or {}
        terms.append(str(user.get("name") or "").strip())
    except Exception:
        pass
    try:
        profile = db.load_health_profile(uid) or {}
        terms.append(str(profile.get("display_name") or "").strip())
    except Exception:
        pass
    if card.get("subject_type") == "member":
        try:
            member = db.get_member("account-%s" % uid, int(card.get("subject_id") or 0)) or {}
            terms.append(str(member.get("name") or "").strip())
        except Exception:
            pass
    # Longer names first avoids partial masking producing odd remnants.
    return sorted({t for t in terms if len(t) >= 2}, key=len, reverse=True)


def _safeid_public_text(value, limit=1800, private_terms=None):
    """Mask contact identifiers and known subject/account names in public text."""
    text = str(value or "").strip()[:max(1, int(limit))]
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[hidden email]", text)
    text = re.sub(r"(?<!\d)(?:\+?\d[\d\s()\-]{8,}\d)(?!\d)", "[hidden number]", text)
    for term in private_terms or []:
        term = str(term or "").strip()
        if len(term) >= 2:
            text = re.sub(re.escape(term), "[hidden name]", text, flags=re.IGNORECASE)
    return text


def safeid_public_payload(token: str, mode: str) -> dict | None:
    card = get_safeid_public(token)
    mode = str(mode or "").strip().lower()
    if not card or mode not in _SAFEID_MODES:
        return None
    cfg = card.get("config") or {}
    legacy_data = _safeid_subject_data(card)
    fields = []
    private_terms = _safeid_private_terms(card)

    if mode == "emergency":
        # V166 prefers information typed directly into the emergency feature.
        # Legacy profile toggles remain a fallback for existing cards.
        direct = (
            ("allergies", cfg.get("emergency_allergies")),
            ("medications", cfg.get("emergency_medications")),
            ("conditions", cfg.get("emergency_conditions")),
        )
        for key, value in direct:
            value = str(value or "").strip()
            if not value:
                legacy_flag = {
                    "allergies": "share_allergies",
                    "medications": "share_medications",
                    "conditions": "share_conditions",
                }[key]
                if cfg.get(legacy_flag):
                    value = str(legacy_data.get(key) or "").strip()
            if value:
                fields.append({"key": key, "value": _safeid_public_text(value, 1800, private_terms)})
        note = str(cfg.get("emergency_note") or "").strip()
        if note:
            fields.append({"key": "emergency_note", "value": _safeid_public_text(note, 600, private_terms)})
    elif mode == "assist":
        # Kept for backwards-compatible old QR links. It is no longer surfaced
        # in the simplified V166 owner experience.
        lang = str(cfg.get("preferred_language") or "").strip()
        needs = str(cfg.get("support_needs") or "").strip()
        if lang:
            fields.append({"key": "preferred_language", "value": _safeid_public_text(lang, 100, private_terms)})
        if needs:
            fields.append({"key": "support_needs", "value": _safeid_public_text(needs, 600, private_terms)})

    contact = None
    if mode in {"emergency", "found"} and cfg.get("emergency_contact_enabled"):
        phone = _safeid_phone(cfg.get("emergency_contact_phone"))
        if phone:
            contact = {
                "name": str(cfg.get("emergency_contact_name") or "").strip()[:100],
                "relation": str(cfg.get("emergency_contact_relation") or "").strip()[:80],
                "phone": phone,
                "message": str(cfg.get("emergency_contact_message") or "").strip()[:320],
            }

    payload = {
        "mode": mode,
        "fields": fields,
        "contact_available": bool(contact),
        "emergency_contact": contact,
        "updated_at": card.get("updated_at"),
    }
    safeid_log_access(token, mode, "view")
    return payload


def safeid_log_access(token: str, mode: str, action="view") -> bool:
    card = get_safeid_public(token); mode = str(mode or "").lower(); action = str(action or "").lower()
    if not card or mode not in _SAFEID_MODES or action not in _SAFEID_ACTIONS:
        return False
    now = datetime.now(timezone.utc); conn = db._conn(); c = conn.cursor()
    try:
        # Coalesce rapid refreshes so a public QR cannot flood the owner's audit log.
        c.execute("SELECT created_at FROM ss_safeid_access WHERE card_id=%s AND mode=%s AND action=%s ORDER BY id DESC LIMIT 1".replace("%s", PH),
                  (card["id"], mode, action))
        row = c.fetchone()
        if row:
            last = _parse_dt(row[0])
            window = 900 if action == "contact_alert" else 30
            if last and (now - last).total_seconds() < window:
                return False
        c.execute("INSERT INTO ss_safeid_access(card_id,mode,action,created_at) VALUES(%s,%s,%s,%s)".replace("%s", PH),
                  (card["id"], mode, action, now.isoformat()))
        conn.commit(); return True
    finally:
        conn.close()


def safeid_contact_alert(token: str) -> dict:
    card = get_safeid_public(token)
    if not card or not bool((card.get("config") or {}).get("contact_alert")):
        return {"ok": False, "reason": "unavailable"}

    # Claim the 15-minute alert window atomically in the database. This prevents
    # two simultaneous requests (including requests handled by different web
    # workers) from sending duplicate owner notifications.
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(minutes=15)).isoformat()
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute(
            "UPDATE ss_safeid_cards SET last_alert_at=%s WHERE id=%s AND enabled=1 "
            "AND (last_alert_at IS NULL OR last_alert_at<=%s)".replace("%s", PH),
            (now.isoformat(), card["id"], cutoff),
        )
        claimed = int(c.rowcount or 0) > 0
        conn.commit()
    finally:
        conn.close()
    if not claimed:
        return {"ok": False, "reason": "cooldown", "account_user_id": card.get("account_user_id")}

    # The access log is audit-only; notification eligibility is controlled by
    # the atomic claim above, so a logging race cannot send duplicate alerts.
    safeid_log_access(token, "found", "contact_alert")
    return {"ok": True, "account_user_id": card.get("account_user_id")}


def safeid_access_log(owner_key: str, subject_type="self", subject_id=0, limit=12) -> list[dict]:
    init_schema(); st, sid = _safeid_subject(subject_type, subject_id); oh = _subject_hash(owner_key)
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute("SELECT id FROM ss_safeid_cards WHERE owner_hash=%s AND subject_type=%s AND subject_id=%s".replace("%s", PH),
                  (oh, st, sid)); row = c.fetchone()
        if not row: return []
        c.execute("SELECT mode,action,created_at FROM ss_safeid_access WHERE card_id=%s ORDER BY id DESC LIMIT %s".replace("%s", PH),
                  (int(row[0]), max(1, min(50, int(limit)))))
        rows = c.fetchall()
    finally:
        conn.close()
    return [{"mode": r[0], "action": r[1], "created_at": r[2]} for r in rows]

def privacy_audit_events(limit=200) -> list[dict]:
    """Return privacy actions without subject identifiers or health content."""
    init_schema(); conn=db._conn(); c=conn.cursor()
    try:
        c.execute("SELECT id,action,metadata,timestamp FROM ss_privacy_events ORDER BY id DESC LIMIT %s" % PH,(max(1,min(500,int(limit))),))
        rows=c.fetchall()
    finally:
        conn.close()
    out=[]
    for rid,action,metadata,ts in rows:
        try: meta=json.loads(metadata or "{}")
        except Exception: logging.getLogger(__name__).debug("Handled exception in privacy_audit_events; fallback applied (handler 633)"); meta={}
        safe={k:v for k,v in meta.items() if k in {"status","format","count"}}
        out.append({"id":"privacy-%s"%rid,"admin_id":None,"action":action,"entity_type":"privacy","entity_id":None,"previous_value":None,"new_value":json.dumps(safe,ensure_ascii=False) if safe else None,"timestamp":ts,"source":"privacy"})
    return out


def anonymous_health_analytics() -> dict:
    """Admin-safe aggregate health analytics from explicitly consented records.

    Small groups are suppressed using *distinct users*, not record count, so one
    prolific account cannot make a group appear privacy-safe by itself.
    """
    init_schema(); k=PRIVACY_THRESHOLD
    conn=db._conn(); c=conn.cursor()
    try:
        c.execute("SELECT user_hash,age,gender,symptoms,medications,urgency,timestamp FROM records WHERE analytics_eligible=1")
        records=c.fetchall()
        c.execute("SELECT subject_hash,consent_status,timestamp FROM ss_consent_log WHERE consent_type='analytics_research' ORDER BY timestamp")
        consent_rows=c.fetchall()
    finally:
        conn.close()
    syms=Counter(); risks=Counter(); ages=Counter(); meds=Counter()
    users_by={"symptom":defaultdict(set),"risk":defaultdict(set),"age":defaultdict(set),"med":defaultdict(set)}
    def age_group(a):
        try:a=int(a)
        except Exception:logging.getLogger(__name__).debug("Handled exception in age_group; fallback applied (handler 658)"); return "Unknown"
        if a<18:return "Under 18"
        if a<=25:return "18–25"
        if a<=35:return "26–35"
        if a<=45:return "36–45"
        if a<=55:return "46–55"
        return "56+"
    for uh,age,gender,symptoms,medications,urgency,ts in records:
        ag=age_group(age); ages[ag]+=1; users_by["age"][ag].add(uh)
        rk=str(urgency or "unknown"); risks[rk]+=1; users_by["risk"][rk].add(uh)
        for sym in {x.strip() for x in str(symptoms or "").split(",") if x.strip()}:
            syms[sym]+=1; users_by["symptom"][sym].add(uh)
        for med in {x.strip() for x in str(medications or "").replace(";",",").split(",") if x.strip()}:
            meds[med]+=1; users_by["med"][med].add(uh)
    def safe_counter(counter, key):
        return [{"label":x,"count":n,"distinct_users":len(users_by[key][x])} for x,n in counter.most_common(20) if len(users_by[key][x])>=k]
    latest={}
    for sh,status,ts in consent_rows: latest[sh]=status
    consent=Counter(latest.values()); total_consents=sum(consent.values())
    metrics={x:(round(consent.get(x,0)*100/total_consents,1) if total_consents else 0) for x in ("granted","declined","withdrawn")}
    return {
        "privacy_threshold":k,
        "eligible_records":len(records),
        "eligible_users":len({r[0] for r in records}),
        "most_reported_symptoms":safe_counter(syms,"symptom"),
        "age_groups":safe_counter(ages,"age"),
        "medication_patterns":safe_counter(meds,"med"),
        "risk_distribution":safe_counter(risks,"risk"),
        "consent_metrics":metrics,
        "consent_subjects":total_consents,
    }
