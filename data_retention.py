"""Privacy-first retention housekeeping for non-health operational metadata.

Health records are user-controlled by default (HEALTH_DATA_RETENTION_DAYS=0):
there is no silent time-based deletion of analyses that could surprise a user or
corrupt a frozen research dataset.  Explicit user deletion/withdrawal remains
available.  Short-lived security, analytics, token and medication-email delivery metadata is pruned
on a documented schedule.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import db

PH = db.PH


def _days(name: str, default: int, *, minimum: int = 1, maximum: int = 3650) -> int:
    try:
        value = int(os.environ.get(name, str(default)) or default)
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def policy() -> dict:
    try:
        health_days = max(0, int(os.environ.get("HEALTH_DATA_RETENTION_DAYS", "0") or 0))
    except (TypeError, ValueError):
        health_days = 0
    return {
        "health_records": {
            "days": health_days,
            "mode": "user_controlled" if health_days == 0 else "configured_manual_review",
            "detail": "Retained until user deletion/withdrawal by default; no silent automatic health-record purge runs when value is 0.",
        },
        "usage_analytics_days": _days("USAGE_ANALYTICS_RETENTION_DAYS", 180),
        "security_log_days": _days("SECURITY_LOG_RETENTION_DAYS", 90),
        "rate_limit_days": _days("RATE_LIMIT_RETENTION_DAYS", 2),
        "medication_email_days": _days("MEDICATION_EMAIL_RETENTION_DAYS", 90),
        "expired_token_grace_days": _days("EXPIRED_TOKEN_RETENTION_DAYS", 7),
        "expired_handoff_grace_days": _days("EXPIRED_HANDOFF_RETENTION_DAYS", 7),
    }


def _cutoff(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=int(days))).isoformat()


def _delete(c, table: str, column: str, before: str, extra: str = "", params=()) -> int:
    sql = f"DELETE FROM {table} WHERE {column}<{PH}" + (f" AND {extra}" if extra else "")
    c.execute(sql, (before, *params))
    return max(0, int(c.rowcount or 0))


def _existing_tables(c) -> set[str]:
    if db.USE_POSTGRES:
        c.execute("SELECT tablename FROM pg_tables WHERE schemaname=current_schema()")
        return {str(r[0]) for r in c.fetchall()}
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {str(r[0]) for r in c.fetchall()}


def run_cleanup() -> dict:
    """Prune stale technical metadata. Never deletes symptom/health records."""
    db.init_db(); cfg = policy(); conn = db._conn(); c = conn.cursor(); deleted = {}
    try:
        existing = _existing_tables(c)
        usage_cutoff = _cutoff(cfg["usage_analytics_days"])
        for table,column in (("ss_usage_events","created_at"),("ss_journey_events","created_at"),("ss_session_activity","last_seen"),("mk_unmatched_log","created_at"),("ss_search_gap_log","created_at")):
            if table in existing: deleted[table] = _delete(c, table, column, usage_cutoff)

        security_cutoff = _cutoff(cfg["security_log_days"])
        if "ss_login_activity" in existing: deleted["login_activity"] = _delete(c, "ss_login_activity", "occurred_at", security_cutoff)

        rate_cutoff = _cutoff(cfg["rate_limit_days"])
        for table in ("ss_auth_rate_limits","ss_analyze_rate_limits","ss_request_rate_limits"):
            if table in existing: deleted[table] = _delete(c, table, "attempted_at", rate_cutoff)

        email_cutoff = _cutoff(cfg["medication_email_days"])
        if "med_email_deliveries" in existing: deleted["med_email_deliveries"] = _delete(c,"med_email_deliveries","attempted_at",email_cutoff)
        # Legacy Push tables are cleanup-only after the V175 email migration.
        if "push_delivery_log" in existing: deleted["legacy_push_delivery_log"] = _delete(c,"push_delivery_log","sent_at",email_cutoff)
        if "push_delivery_receipts" in existing: deleted["legacy_push_delivery_receipts"] = _delete(c,"push_delivery_receipts","sent_at",email_cutoff)

        token_cutoff = _cutoff(cfg["expired_token_grace_days"])
        for table in ("ss_password_resets","ss_email_verifications","med_email_actions","push_action_tokens"):
            if table in existing: deleted[table] = _delete(c,table,"expires_at",token_cutoff)
        handoff_cutoff = _cutoff(cfg["expired_handoff_grace_days"])
        if "ss_handoff_links" in existing: deleted["handoff_links"] = _delete(c,"ss_handoff_links","expires_at",handoff_cutoff)
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()
    return {"policy": cfg, "deleted": deleted, "deleted_total": sum(deleted.values())}

