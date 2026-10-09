"""Email-only medication reminder engine for SymptoSense.

Medication reminders are user-authored schedules. This module deliberately does
not use Web Push, browser notification permissions, PushManager, VAPID, or push
subscriptions. Delivery is transactional email via Brevo or Resend.
"""
from __future__ import annotations

import hashlib
import html
import json
import logging
import os
import secrets
import threading
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests

import db
import medication_telegram

PH = db.PH
log = logging.getLogger("SymptoSense.MedicationEmail")
ALLOWED_SNOOZE = {5, 10, 15, 30}
ALLOWED_FREQ = {"daily", "specific_days"}
_EMAIL_ADVISORY_LOCK_ID = 781264021
_LOCAL_EMAIL_CYCLE_LOCK = threading.Lock()
_SCHEMA_READY_KEY = None
_SCHEMA_LOCK = threading.Lock()


def _reminder_grace_seconds() -> int:
    """How long after a scheduled dose we still attempt delivery.

    Railway deployments/restarts and a user completing Telegram linking can
    briefly delay the background worker.  A five-minute window was too narrow
    in production, so the default is 30 minutes and remains configurable.
    """
    try:
        value = int(str(os.environ.get("MED_REMINDER_GRACE_SECONDS", "1800")).strip())
    except (TypeError, ValueError, OverflowError):
        value = 1800
    return max(300, min(7200, value))


def _serial():
    return "SERIAL PRIMARY KEY" if db.USE_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _token_hash(raw: str):
    return hashlib.sha256(str(raw).encode("utf-8")).hexdigest()


def _cols(c, table):
    if db.USE_POSTGRES:
        c.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s", (table,))
        return {r[0] for r in c.fetchall()}
    c.execute(f"PRAGMA table_info({table})")
    return {r[1] for r in c.fetchall()}


def _add_col(c, table, name, sql_type_default):
    if name not in _cols(c, table):
        c.execute(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type_default}")


def init_schema():
    """Create/upgrade the medication reminder schema once per database identity.

    V215 keeps schema work out of ordinary reads. Tombstone cleanup runs once
    per process/database identity instead of on every list/calendar request.
    """
    global _SCHEMA_READY_KEY
    db.init_db()
    key = db._database_identity()
    if _SCHEMA_READY_KEY == key:
        return
    with _SCHEMA_LOCK:
        if _SCHEMA_READY_KEY == key:
            return
        conn = db._conn(); c = conn.cursor()
        try:
            _add_col(c, "med_plans", "end_date", "TEXT")
            _add_col(c, "med_plans", "notes", "TEXT DEFAULT ''")
            _add_col(c, "med_plans", "days_of_week", "TEXT DEFAULT '[]'")
            _add_col(c, "med_plans", "timezone", "TEXT DEFAULT 'Asia/Riyadh'")
            _add_col(c, "med_plans", "notifications_enabled", "INTEGER DEFAULT 1")
            _add_col(c, "med_plans", "delivery_channel", "TEXT DEFAULT 'email'")
            _add_col(c, "med_plans", "updated_at", "TEXT")

            c.execute("""
                CREATE TABLE IF NOT EXISTS med_reminder_settings (
                    user_id INTEGER PRIMARY KEY,
                    snooze_minutes INTEGER NOT NULL DEFAULT 10,
                    timezone TEXT NOT NULL DEFAULT 'Asia/Riyadh',
                    updated_at TEXT NOT NULL
                )
            """)
            c.execute(f"""
                CREATE TABLE IF NOT EXISTS medication_reminders (
                    id {_serial()},
                    user_id INTEGER NOT NULL,
                    plan_id INTEGER NOT NULL,
                    member_id INTEGER NOT NULL DEFAULT 0,
                    med_name TEXT NOT NULL,
                    dose TEXT,
                    reminder_time TEXT NOT NULL,
                    timezone TEXT NOT NULL DEFAULT 'Asia/Riyadh',
                    frequency TEXT NOT NULL DEFAULT 'daily',
                    days_of_week TEXT NOT NULL DEFAULT '[]',
                    start_date TEXT,
                    end_date TEXT,
                    active INTEGER NOT NULL DEFAULT 1,
                    delivery_channel TEXT NOT NULL DEFAULT 'email',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(plan_id, reminder_time)
                )
            """)
            _add_col(c, "medication_reminders", "delivery_channel", "TEXT DEFAULT 'email'")
            c.execute("CREATE INDEX IF NOT EXISTS idx_medication_reminders_due ON medication_reminders(active, reminder_time)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_medication_reminders_user ON medication_reminders(user_id, active)")

            # V215: deletion tombstones intentionally store no medication name or
            # other health content. user_hash + plan_id are enough to suppress a
            # stale resurrection during rolling deploys/retries.
            c.execute("""
                CREATE TABLE IF NOT EXISTS med_plan_tombstones (
                    user_hash TEXT NOT NULL,
                    plan_id INTEGER NOT NULL,
                    deleted_at TEXT NOT NULL,
                    PRIMARY KEY(user_hash, plan_id)
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_med_plan_tombstones_plan ON med_plan_tombstones(plan_id)")
            # If an unreleased/intermediate V214 database exists, scrub the old
            # med_name column immediately. The column may remain physically for
            # compatibility, but it carries no medication content from V215 on.
            try:
                if "med_name" in _cols(c, "med_plan_tombstones"):
                    c.execute("UPDATE med_plan_tombstones SET med_name='' WHERE COALESCE(med_name,'')<>''")
            except Exception:
                log.warning("Could not scrub legacy tombstone medication names", exc_info=True)

            c.execute(f"""
                CREATE TABLE IF NOT EXISTS med_snoozes (
                    id {_serial()}, user_hash TEXT NOT NULL, plan_id INTEGER NOT NULL,
                    member_id INTEGER NOT NULL DEFAULT 0, log_date TEXT NOT NULL,
                    log_time TEXT NOT NULL, due_at_utc TEXT NOT NULL, minutes INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_med_snooze_due ON med_snoozes(status,due_at_utc)")

            c.execute(f"""
                CREATE TABLE IF NOT EXISTS med_email_actions (
                    id {_serial()}, token_hash TEXT UNIQUE NOT NULL, user_id INTEGER NOT NULL,
                    plan_id INTEGER NOT NULL, member_id INTEGER NOT NULL DEFAULT 0,
                    log_date TEXT NOT NULL, log_time TEXT NOT NULL,
                    lang TEXT NOT NULL DEFAULT 'ar', action TEXT NOT NULL,
                    expires_at TEXT NOT NULL, consumed_at TEXT, created_at TEXT NOT NULL
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_med_email_action_exp ON med_email_actions(expires_at)")

            c.execute(f"""
                CREATE TABLE IF NOT EXISTS med_email_deliveries (
                    id {_serial()}, user_id INTEGER NOT NULL, plan_id INTEGER NOT NULL,
                    log_date TEXT NOT NULL, log_time TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending', provider TEXT,
                    attempted_at TEXT, sent_at TEXT, error_code TEXT,
                    UNIQUE(user_id, plan_id, log_date, log_time)
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_med_email_delivery_status ON med_email_deliveries(status, attempted_at)")

            # One-time ghost cleanup for this process/database identity. Reads still
            # exclude tombstoned plans defensively, so cleanup is not required on
            # every request.
            c.execute("""
                DELETE FROM medication_reminders
                WHERE plan_id IN (SELECT plan_id FROM med_plan_tombstones)
            """)
            c.execute("""
                DELETE FROM med_plans
                WHERE EXISTS (
                    SELECT 1 FROM med_plan_tombstones t
                    WHERE t.plan_id=med_plans.id AND t.user_hash=med_plans.user_hash
                )
            """)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        _backfill_reminder_rows()
        medication_telegram.init_schema()
        _SCHEMA_READY_KEY = key

def valid_timezone(value: str) -> str:
    value = (value or "Asia/Riyadh").strip()[:80]
    try:
        ZoneInfo(value)
        return value
    except (ZoneInfoNotFoundError, ValueError):
        return "Asia/Riyadh"


def _json_list(value):
    if isinstance(value, list):
        return value
    try:
        return json.loads(value or "[]")
    except (TypeError, ValueError, OverflowError):
        return []


def _parse_times(values) -> list[str]:
    out = []
    for raw in values or []:
        try:
            h, m = str(raw).strip().split(":", 1)
            h, m = int(h), int(m)
            if 0 <= h <= 23 and 0 <= m <= 59:
                val = f"{h:02d}:{m:02d}"
                if val not in out:
                    out.append(val)
        except Exception:
            pass
    return sorted(out)


def _parse_days(values) -> list[int]:
    out = []
    for raw in values or []:
        try:
            v = int(raw)
            if 0 <= v <= 6 and v not in out:
                out.append(v)
        except Exception:
            pass
    return sorted(out)


def _sync_reminder_rows(user_id: int, plan_id: int, plan: dict):
    now = _now(); conn = db._conn(); c = conn.cursor()
    try:
        uh = db._hash_user(int(user_id))
        c.execute(
            f"SELECT 1 FROM med_plan_tombstones WHERE user_hash={PH} AND plan_id={PH}",
            (uh, int(plan_id)),
        )
        if c.fetchone():
            # A deleted plan must never regain delivery rows.
            c.execute(f"DELETE FROM medication_reminders WHERE plan_id={PH}", (int(plan_id),))
            conn.commit()
            return
        c.execute(f"DELETE FROM medication_reminders WHERE plan_id={PH}", (int(plan_id),))
        for tm in _parse_times(plan.get("times") or []):
            values = (
                int(user_id), int(plan_id), int(plan.get("member_id") or 0),
                str(plan.get("med_name") or "")[:120], str(plan.get("dose") or "")[:120], tm,
                valid_timezone(plan.get("timezone")), str(plan.get("frequency") or "daily"),
                json.dumps(_parse_days(plan.get("days_of_week") or [])),
                str(plan.get("start_date") or "")[:10] or None,
                str(plan.get("end_date") or "")[:10] or None,
                1 if plan.get("active", True) else 0,
                "telegram" if str(plan.get("delivery_channel") or "email").lower()=="telegram" else "email",
                now, now,
            )
            c.execute(
                f"INSERT INTO medication_reminders(user_id,plan_id,member_id,med_name,dose,reminder_time,timezone,frequency,days_of_week,start_date,end_date,active,delivery_channel,created_at,updated_at) VALUES({','.join([PH]*15)})",
                values,
            )
        conn.commit()
    finally:
        conn.close()


def _backfill_reminder_rows():
    """Populate the new email table for existing medication plans when ownership is resolvable."""
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute("SELECT id FROM ss_users")
        ids = [int(r[0]) for r in c.fetchall()]
        by_hash = {db._hash_user(uid): uid for uid in ids}
        c.execute("""
            SELECT p.id,p.user_hash,p.member_id,p.med_name,p.dose,p.times,p.frequency,p.start_date,p.end_date,p.days_of_week,p.timezone,p.active,p.delivery_channel
            FROM med_plans p
            WHERE NOT EXISTS (
                SELECT 1 FROM med_plan_tombstones t
                WHERE t.user_hash=p.user_hash AND t.plan_id=p.id
            )
        """)
        rows = c.fetchall()
        c.execute("SELECT DISTINCT plan_id FROM medication_reminders")
        existing = {int(r[0]) for r in c.fetchall()}
    finally:
        conn.close()
    for r in rows:
        pid = int(r[0])
        if pid in existing:
            continue
        uid = by_hash.get(r[1])
        if not uid:
            continue
        _sync_reminder_rows(uid, pid, {
            "member_id": r[2], "med_name": r[3], "dose": r[4] or "",
            "times": _json_list(r[5]), "frequency": r[6] or "daily",
            "start_date": r[7] or "", "end_date": r[8] or "",
            "days_of_week": _json_list(r[9]), "timezone": r[10] or "Asia/Riyadh",
            "active": bool(r[11]), "delivery_channel": r[12] or "email",
        })


def save_plan(user_id, data: dict, plan_id: int | None = None) -> int:
    init_schema(); uh = db._hash_user(user_id)
    med_name = str(data.get("med_name") or "").strip()[:120]
    times = _parse_times(data.get("times") or [])
    if not med_name or not times:
        raise ValueError("medication_name_and_time_required")
    dose = str(data.get("dose") or "").strip()[:120]
    notes = str(data.get("notes") or "").strip()[:600]
    delivery_channel = "telegram" if str(data.get("delivery_channel") or "email").strip().lower()=="telegram" else "email"
    frequency = str(data.get("frequency") or "daily").strip()
    frequency = frequency if frequency in ALLOWED_FREQ else "daily"
    days_of_week = _parse_days(data.get("days_of_week") or []) if frequency == "specific_days" else []
    if frequency == "specific_days" and not days_of_week:
        raise ValueError("days_of_week_required")
    tz = valid_timezone(data.get("timezone"))
    start = str(data.get("start_date") or date.today().isoformat()).strip()[:10]
    end = str(data.get("end_date") or "").strip()[:10] or None
    try:
        start_obj = date.fromisoformat(start)
        end_obj = date.fromisoformat(end) if end else None
    except ValueError:
        raise ValueError("invalid_plan_date")
    if end_obj and end_obj < start_obj:
        raise ValueError("invalid_plan_date_range")
    try:
        member = int(data.get("member_id") or 0)
    except (TypeError, ValueError):
        raise ValueError("invalid_member")
    if member < 0 or (member and not db.get_member(user_id, member)):
        raise ValueError("invalid_member")
    days = data.get("days")
    if days in (None, ""):
        days = None
    else:
        try:
            days = int(days)
        except (TypeError, ValueError):
            raise ValueError("invalid_plan_days")
        if days < 1 or days > 3650:
            raise ValueError("invalid_plan_days")
    now = _now(); conn = db._conn(); c = conn.cursor()
    try:
        if plan_id:
            c.execute(
                f"SELECT 1 FROM med_plans p WHERE p.id={PH} AND p.user_hash={PH} "
                f"AND NOT EXISTS (SELECT 1 FROM med_plan_tombstones t WHERE t.user_hash=p.user_hash AND t.plan_id=p.id)",
                (int(plan_id), uh),
            )
            if not c.fetchone():
                raise PermissionError("plan_not_found_or_not_owned")
            c.execute(
                f"UPDATE med_plans SET member_id={PH},med_name={PH},dose={PH},times={PH},frequency={PH},start_date={PH},days={PH},end_date={PH},notes={PH},days_of_week={PH},timezone={PH},delivery_channel={PH},notifications_enabled=1,active=1,updated_at={PH} WHERE id={PH} AND user_hash={PH}",
                (member, med_name, dose, json.dumps(times), frequency, start, days, end, notes, json.dumps(days_of_week), tz, delivery_channel, now, int(plan_id), uh),
            )
            pid = int(plan_id)
        else:
            values = (uh, member, med_name, dose, json.dumps(times), frequency, start, days, 1, now, end, notes, json.dumps(days_of_week), tz, delivery_channel, 1, now)
            if db.USE_POSTGRES:
                c.execute(
                    "INSERT INTO med_plans(user_hash,member_id,med_name,dose,times,frequency,start_date,days,active,created,end_date,notes,days_of_week,timezone,delivery_channel,notifications_enabled,updated_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                    values,
                )
                pid = int(c.fetchone()[0])
            else:
                c.execute(
                    "INSERT INTO med_plans(user_hash,member_id,med_name,dose,times,frequency,start_date,days,active,created,end_date,notes,days_of_week,timezone,delivery_channel,notifications_enabled,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    values,
                )
                pid = int(c.lastrowid)
        conn.commit()
    finally:
        conn.close()
    _sync_reminder_rows(int(user_id), pid, {
        "member_id": member, "med_name": med_name, "dose": dose, "times": times,
        "frequency": frequency, "start_date": start, "end_date": end,
        "days_of_week": days_of_week, "timezone": tz, "active": True, "delivery_channel": delivery_channel,
    })
    return pid


def list_plans(user_id, member_id=None, active_only=True) -> list[dict]:
    init_schema(); uh = db._hash_user(user_id); conn = db._conn(); c = conn.cursor()
    try:
        clauses = [f"p.user_hash={PH}"]; params = [uh]
        if member_id is not None:
            clauses.append(f"p.member_id={PH}"); params.append(int(member_id))
        if active_only:
            clauses.append("p.active=1")
        clauses.append("NOT EXISTS (SELECT 1 FROM med_plan_tombstones t WHERE t.user_hash=p.user_hash AND t.plan_id=p.id)")
        c.execute("SELECT p.id,p.member_id,p.med_name,p.dose,p.times,p.frequency,p.start_date,p.days,p.active,p.created,p.end_date,p.notes,p.days_of_week,p.timezone,p.notifications_enabled,p.updated_at,p.delivery_channel FROM med_plans p WHERE " + " AND ".join(clauses) + " ORDER BY p.id DESC", tuple(params))
        rows = c.fetchall()
    finally:
        conn.close()
    return [{
        "id": r[0], "member_id": r[1], "med_name": r[2], "dose": r[3] or "",
        "times": _parse_times(_json_list(r[4])), "frequency": r[5] or "daily",
        "start_date": r[6] or "", "days": r[7], "active": bool(r[8]), "created": r[9] or "",
        "end_date": r[10] or "", "notes": r[11] or "", "days_of_week": _parse_days(_json_list(r[12])),
        "timezone": valid_timezone(r[13]), "notifications_enabled": True, "updated_at": r[15] or "",
        "delivery_channel": "telegram" if str(r[16] or "email").lower()=="telegram" else "email",
    } for r in rows]


def delete_plan(user_id, plan_id):
    """Permanently remove one owned medication reminder plan and its history.

    V215 writes a privacy-minimal tombstone (owner hash + plan id + deletion
    time only), then hard-deletes the schedule, action tokens, delivery rows,
    snoozes, dose-status history, and plan. Repeated DELETE is idempotent.
    """
    init_schema()
    uid = int(user_id); pid = int(plan_id); uh = db._hash_user(uid)
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute(
            f"SELECT 1 FROM med_plans WHERE id={PH} AND user_hash={PH}",
            (pid, uh),
        )
        row = c.fetchone()
        if not row:
            c.execute(
                f"SELECT 1 FROM med_plan_tombstones WHERE user_hash={PH} AND plan_id={PH}",
                (uh, pid),
            )
            return bool(c.fetchone())

        now = _now()
        c.execute(
            f"SELECT 1 FROM med_plan_tombstones WHERE user_hash={PH} AND plan_id={PH}",
            (uh, pid),
        )
        if c.fetchone():
            c.execute(
                f"UPDATE med_plan_tombstones SET deleted_at={PH} WHERE user_hash={PH} AND plan_id={PH}",
                (now, uh, pid),
            )
        else:
            c.execute(
                f"INSERT INTO med_plan_tombstones(user_hash,plan_id,deleted_at) VALUES({PH},{PH},{PH})",
                (uh, pid, now),
            )

        # The UI confirms that deleting a reminder also removes its reminder
        # history. This avoids retaining health-event data after an explicit
        # delete without the user knowing.
        c.execute(f"DELETE FROM medication_reminders WHERE plan_id={PH} AND user_id={PH}", (pid, uid))
        c.execute(f"DELETE FROM med_snoozes WHERE plan_id={PH} AND user_hash={PH}", (pid, uh))
        c.execute(f"DELETE FROM med_email_actions WHERE plan_id={PH} AND user_id={PH}", (pid, uid))
        c.execute(f"DELETE FROM med_email_deliveries WHERE plan_id={PH} AND user_id={PH}", (pid, uid))
        c.execute(f"DELETE FROM med_telegram_deliveries WHERE plan_id={PH} AND user_id={PH}", (pid, uid))
        c.execute(f"DELETE FROM med_logs WHERE plan_id={PH} AND user_hash={PH}", (pid, uh))
        c.execute(f"DELETE FROM med_plans WHERE id={PH} AND user_hash={PH}", (pid, uh))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    # Verify on a brand-new connection before reporting success.
    verify = db._conn(); vc = verify.cursor()
    try:
        vc.execute(f"SELECT 1 FROM med_plans WHERE id={PH} AND user_hash={PH}", (pid, uh))
        if vc.fetchone():
            raise RuntimeError("medication_delete_not_persisted")
        vc.execute(
            f"SELECT 1 FROM med_plan_tombstones WHERE user_hash={PH} AND plan_id={PH}",
            (uh, pid),
        )
        if not vc.fetchone():
            raise RuntimeError("medication_delete_tombstone_missing")
    finally:
        verify.close()
    return True

def disable_plan(user_id, plan_id):
    """Backward-compatible alias kept for older callers/tests."""
    return delete_plan(user_id, plan_id)


def get_settings(user_id) -> dict:
    init_schema(); conn = db._conn(); c = conn.cursor()
    try:
        c.execute(f"SELECT snooze_minutes,timezone FROM med_reminder_settings WHERE user_id={PH}", (int(user_id),))
        r = c.fetchone()
        if not r:
            return {"enabled": True, "snooze_minutes": 10, "timezone": "Asia/Riyadh", "channel": "email"}
        return {"enabled": True, "snooze_minutes": int(r[0] or 10), "timezone": valid_timezone(r[1]), "channel": "email"}
    finally:
        conn.close()


def save_settings(user_id, data: dict) -> dict:
    init_schema()
    try:
        snooze = int(data.get("snooze_minutes") or 10)
    except (TypeError, ValueError, OverflowError):
        snooze = 10
    if snooze not in ALLOWED_SNOOZE:
        snooze = 10
    tz = valid_timezone(data.get("timezone")); now = _now(); conn = db._conn(); c = conn.cursor()
    try:
        vals = (int(user_id), snooze, tz, now)
        if db.USE_POSTGRES:
            c.execute("INSERT INTO med_reminder_settings(user_id,snooze_minutes,timezone,updated_at) VALUES(%s,%s,%s,%s) ON CONFLICT(user_id) DO UPDATE SET snooze_minutes=EXCLUDED.snooze_minutes,timezone=EXCLUDED.timezone,updated_at=EXCLUDED.updated_at", vals)
        else:
            c.execute("INSERT INTO med_reminder_settings(user_id,snooze_minutes,timezone,updated_at) VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET snooze_minutes=excluded.snooze_minutes,timezone=excluded.timezone,updated_at=excluded.updated_at", vals)
        conn.commit()
    finally:
        conn.close()
    return get_settings(user_id)


def _plan_active_on(plan: dict, local_date: date) -> bool:
    try:
        start = date.fromisoformat(str(plan.get("start_date") or local_date.isoformat())[:10])
    except (TypeError, ValueError, OverflowError):
        start = local_date
    if local_date < start:
        return False
    end_raw = plan.get("end_date")
    if end_raw:
        try:
            if local_date > date.fromisoformat(str(end_raw)[:10]):
                return False
        except Exception:
            pass
    if plan.get("frequency") == "specific_days":
        days = _parse_days(plan.get("days_of_week") or [])
        if days and local_date.weekday() not in days:
            return False
    return bool(plan.get("active", True))


def _current_log_status(user_id, plan_id, log_date, log_time):
    for row in db.get_med_logs(user_id):
        if int(row.get("plan_id") or 0) == int(plan_id) and row.get("log_date") == log_date and row.get("log_time") == log_time:
            return row.get("status")
    return None


def schedule_snooze(user_id, plan_id, _member_id, log_date, log_time, minutes=None):
    plans = {p["id"]: p for p in list_plans(user_id, active_only=True)}
    if int(plan_id) not in plans:
        raise PermissionError("plan_not_found_or_not_owned")
    plan = plans[int(plan_id)]
    if _current_log_status(user_id, plan_id, log_date, log_time) == "taken":
        raise PermissionError("reminder_already_taken")
    settings = get_settings(user_id)
    try:
        mins = int(minutes or settings.get("snooze_minutes") or 10)
    except (TypeError, ValueError, OverflowError):
        mins = 10
    if mins not in ALLOWED_SNOOZE:
        mins = 10
    tz = ZoneInfo(valid_timezone(plan.get("timezone") or settings.get("timezone")))
    d = date.fromisoformat(str(log_date)[:10]); h, m = map(int, str(log_time).split(":", 1))
    due = datetime(d.year, d.month, d.day, h, m, tzinfo=tz).astimezone(timezone.utc) + timedelta(minutes=mins)
    uh = db._hash_user(user_id); now = _now(); conn = db._conn(); c = conn.cursor()
    try:
        c.execute(
            f"INSERT INTO med_snoozes(user_hash,plan_id,member_id,log_date,log_time,due_at_utc,minutes,status,created_at) VALUES({','.join([PH]*9)})",
            (uh, int(plan_id), int(plan.get("member_id") or 0), str(log_date), str(log_time), due.isoformat(), mins, "pending", now),
        )
        conn.commit()
    finally:
        conn.close()
    db.log_med_status(user_id, int(plan.get("member_id") or 0), int(plan_id), str(log_date), str(log_time), "snoozed")
    return mins


def reminder_calendar(user_id, member_id=None, days=30) -> dict:
    days = max(1, min(90, int(days or 30))); plans = list_plans(user_id, member_id=member_id, active_only=False)
    logs = db.get_med_logs(user_id); logmap = {(int(x["plan_id"]), x["log_date"], x["log_time"]): x["status"] for x in logs}
    settings = get_settings(user_id); tz = ZoneInfo(settings["timezone"]); now = datetime.now(timezone.utc).astimezone(tz)
    start_day = now.date() - timedelta(days=days - 1); entries = []; counts = Counter()
    for i in range(days):
        d = start_day + timedelta(days=i)
        for p in plans:
            if not _plan_active_on(p, d):
                continue
            for tm in p["times"]:
                try:
                    h, m = map(int, tm.split(":")); occ = datetime(d.year, d.month, d.day, h, m, tzinfo=ZoneInfo(p.get("timezone") or settings["timezone"]))
                except Exception:
                    continue
                status = "scheduled" if occ > now else logmap.get((p["id"], d.isoformat(), tm), "scheduled")
                entries.append({"date": d.isoformat(), "time": tm, "plan_id": p["id"], "med_name": p["med_name"], "status": status}); counts[status] += 1
    expected = sum(1 for e in entries if e["date"] < now.date().isoformat() or (e["date"] == now.date().isoformat() and e["time"] <= now.strftime("%H:%M")))
    taken = counts["taken"]; adherence = round(taken * 100.0 / expected, 1) if expected else 0.0
    return {"entries": entries, "summary": {"scheduled": expected, "taken": taken, "skipped": counts["skipped"], "snoozed": counts["snoozed"] + counts["deferred"], "adherence": adherence}}


def plans_today(user_id, member_id=None) -> list[dict]:
    plans = list_plans(user_id, member_id=member_id, active_only=True); logs = db.get_med_logs(user_id)
    logmap = {(int(x["plan_id"]), x["log_date"], x["log_time"]): x["status"] for x in logs}; settings = get_settings(user_id); out = []
    for p in plans:
        tz = valid_timezone(p.get("timezone") or settings.get("timezone")); today = datetime.now(timezone.utc).astimezone(ZoneInfo(tz)).date()
        if not _plan_active_on(p, today):
            continue
        q = dict(p); q["today_date"] = today.isoformat(); q["logs"] = {tm: logmap.get((p["id"], today.isoformat(), tm)) for tm in p["times"]}; out.append(q)
    return out


def weekly_summary(user_id, member_id=None) -> dict:
    cal = reminder_calendar(user_id, member_id=member_id, days=7); sm = cal["summary"]
    return {"expected": sm["scheduled"], "taken": sm["taken"], "skipped": sm["skipped"], "snoozed": sm["snoozed"], "percent": sm["adherence"], "days": 7}


def email_provider_status() -> dict:
    brevo = all(os.environ.get(k, "").strip() for k in ("BREVO_API_KEY", "BREVO_FROM_EMAIL", "BREVO_FROM_NAME"))
    resend = all(os.environ.get(k, "").strip() for k in ("RESEND_API_KEY", "RESEND_FROM"))
    provider = "brevo" if brevo else ("resend" if resend else "none")
    return {"configured": provider != "none", "provider": provider}


def _send_email(to_email: str, subject: str, html_body: str) -> tuple[bool, str]:
    state = email_provider_status(); provider = state["provider"]
    try:
        if provider == "brevo":
            payload = {
                "sender": {"email": os.environ["BREVO_FROM_EMAIL"].strip(), "name": os.environ["BREVO_FROM_NAME"].strip()},
                "to": [{"email": to_email}], "subject": subject, "htmlContent": html_body,
            }
            r = requests.post("https://api.brevo.com/v3/smtp/email", headers={"api-key": os.environ["BREVO_API_KEY"].strip(), "Content-Type": "application/json", "Accept": "application/json"}, json=payload, timeout=15)
            return (200 <= r.status_code < 300, "brevo" if 200 <= r.status_code < 300 else f"brevo_{r.status_code}")
        if provider == "resend":
            payload = {"from": os.environ["RESEND_FROM"].strip(), "to": [to_email], "subject": subject, "html": html_body}
            r = requests.post("https://api.resend.com/emails", headers={"Authorization": "Bearer " + os.environ["RESEND_API_KEY"].strip(), "Content-Type": "application/json"}, json=payload, timeout=15)
            return (200 <= r.status_code < 300, "resend" if 200 <= r.status_code < 300 else f"resend_{r.status_code}")
        return False, "email_not_configured"
    except requests.RequestException:
        log.warning("Medication reminder email provider request failed", exc_info=True)
        return False, f"{provider}_connection_failed" if provider != "none" else "email_not_configured"


def _site_url() -> str:
    explicit = (os.environ.get("SITE_URL") or "").strip().rstrip("/")
    if explicit.startswith("http://") or explicit.startswith("https://"):
        return explicit
    railway = (os.environ.get("RAILWAY_PUBLIC_DOMAIN") or "").strip().strip("/")
    if railway:
        return "https://" + railway
    return "https://symptosensehealth.com"


def _create_action_token(user_id, plan_id, member_id, log_date, log_time, lang, action) -> str:
    raw = secrets.token_urlsafe(32); now = datetime.now(timezone.utc); expires = now + timedelta(hours=48)
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute(
            f"INSERT INTO med_email_actions(token_hash,user_id,plan_id,member_id,log_date,log_time,lang,action,expires_at,consumed_at,created_at) VALUES({','.join([PH]*11)})",
            (_token_hash(raw), int(user_id), int(plan_id), int(member_id or 0), str(log_date), str(log_time), "en" if lang == "en" else "ar", action, expires.isoformat(), None, now.isoformat()),
        )
        conn.commit()
    finally:
        conn.close()
    return raw


def _render_email(lang, med_name, dose, taken_url, snooze_url):
    ar = lang != "en"; med = html.escape(med_name or ""); dose_safe = html.escape(dose or "")
    if ar:
        subject = f"⏰ حان وقت جرعة {med_name}"
        dose_line = f" — {dose_safe}" if dose_safe else ""
        body = f"حان الآن موعد جرعة <strong>{med}{dose_line}</strong>."
        taken_label, snooze_label = "تم تناوله", "تأجيل 10 دقائق"
        footer = "هذه رسالة تذكير آلية بناءً على الموعد الذي أضفته في SymptoSense."
    else:
        subject = f"⏰ Time for your {med_name} dose"
        dose_line = f" — {dose_safe}" if dose_safe else ""
        body = f"It is time for <strong>{med}{dose_line}</strong>."
        taken_label, snooze_label = "Taken", "Snooze 10 minutes"
        footer = "This automatic reminder is based on the schedule you added in SymptoSense."
    html_body = f'''<!doctype html><html dir="{'rtl' if ar else 'ltr'}"><body style="font-family:Arial,sans-serif;background:#f5f9fc;padding:24px;color:#18364d"><div style="max-width:560px;margin:auto;background:#fff;border:1px solid #dbe8f0;border-radius:18px;padding:24px"><h2 style="margin-top:0">SymptoSense</h2><p style="font-size:16px;line-height:1.8">{body}</p><div style="display:flex;gap:10px;flex-wrap:wrap;margin:22px 0"><a href="{html.escape(taken_url, quote=True)}" style="background:#176b97;color:#fff;text-decoration:none;padding:11px 16px;border-radius:10px;font-weight:700">✓ {taken_label}</a><a href="{html.escape(snooze_url, quote=True)}" style="background:#edf6fb;color:#176b97;text-decoration:none;padding:11px 16px;border-radius:10px;font-weight:700">⏰ {snooze_label}</a></div><p style="font-size:12px;color:#6b7f8e;line-height:1.7">{footer}</p></div></body></html>'''
    return subject, html_body


def _acquire_cycle_lock():
    if db.USE_POSTGRES:
        conn = db._conn(); c = conn.cursor()
        try:
            c.execute("SELECT pg_try_advisory_lock(%s)", (_EMAIL_ADVISORY_LOCK_ID,)); row = c.fetchone()
            if row and bool(row[0]):
                return ("postgres", conn)
        except Exception:
            conn.close(); raise
        conn.close(); return None
    if _LOCAL_EMAIL_CYCLE_LOCK.acquire(blocking=False):
        return ("local", None)
    return None


def _release_cycle_lock(lock):
    if not lock:
        return
    kind, conn = lock
    if kind == "postgres" and conn is not None:
        try:
            c = conn.cursor(); c.execute("SELECT pg_advisory_unlock(%s)", (_EMAIL_ADVISORY_LOCK_ID,)); conn.commit()
        finally:
            conn.close()
    elif kind == "local":
        try:
            _LOCAL_EMAIL_CYCLE_LOCK.release()
        except RuntimeError:
            pass


def _delivery_status(user_id, plan_id, log_date, log_time):
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute(f"SELECT status FROM med_email_deliveries WHERE user_id={PH} AND plan_id={PH} AND log_date={PH} AND log_time={PH}", (int(user_id), int(plan_id), log_date, log_time))
        r = c.fetchone(); return str(r[0]) if r else None
    finally:
        conn.close()


def _record_delivery(user_id, plan_id, log_date, log_time, status, provider=None, error_code=None):
    now = _now(); conn = db._conn(); c = conn.cursor(); vals = (int(user_id), int(plan_id), log_date, log_time, status, provider, now, now if status == "sent" else None, error_code)
    try:
        if db.USE_POSTGRES:
            c.execute("INSERT INTO med_email_deliveries(user_id,plan_id,log_date,log_time,status,provider,attempted_at,sent_at,error_code) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(user_id,plan_id,log_date,log_time) DO UPDATE SET status=EXCLUDED.status,provider=EXCLUDED.provider,attempted_at=EXCLUDED.attempted_at,sent_at=EXCLUDED.sent_at,error_code=EXCLUDED.error_code", vals)
        else:
            c.execute("INSERT INTO med_email_deliveries(user_id,plan_id,log_date,log_time,status,provider,attempted_at,sent_at,error_code) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id,plan_id,log_date,log_time) DO UPDATE SET status=excluded.status,provider=excluded.provider,attempted_at=excluded.attempted_at,sent_at=excluded.sent_at,error_code=excluded.error_code", vals)
        conn.commit()
    finally:
        conn.close()


def send_due_emails(now_utc: datetime | None = None) -> dict:
    """Send due medication reminders once. Designed for a once-per-minute cron job."""
    init_schema(); lock = _acquire_cycle_lock()
    if not lock:
        return {"sent": 0, "failed": 0, "skipped": 1, "locked": True}
    now_utc = (now_utc or datetime.now(timezone.utc)).astimezone(timezone.utc); sent = failed = skipped = 0; telegram_sent = telegram_failed = telegram_skipped = 0
    scanned = due_candidates = 0
    grace_seconds = _reminder_grace_seconds()
    try:
        conn = db._conn(); c = conn.cursor()
        try:
            c.execute("SELECT user_id,plan_id,member_id,med_name,dose,reminder_time,timezone,frequency,days_of_week,start_date,end_date,active,delivery_channel FROM medication_reminders WHERE active=1")
            rows = c.fetchall()
        finally:
            conn.close()
        for r in rows:
            scanned += 1
            uid, pid, member_id, med_name, dose, tm, tz_name, freq, days_json, start, end, active, delivery_channel = r
            try:
                tz = ZoneInfo(valid_timezone(tz_name)); local_now = now_utc.astimezone(tz); h, m = map(int, str(tm).split(":"))
                local_due = datetime(local_now.year, local_now.month, local_now.day, h, m, tzinfo=tz)
                delta = (now_utc - local_due.astimezone(timezone.utc)).total_seconds()
                # Do not send early. Allow a bounded catch-up window so a Railway
                # restart, DB wake-up, or Telegram linking step does not permanently
                # lose a reminder that was due a few minutes ago. Around midnight,
                # today's same clock time is in the future, so also consider the
                # previous local day when it is still inside the catch-up window.
                if delta < 0:
                    previous_due = local_due - timedelta(days=1)
                    previous_delta = (now_utc - previous_due.astimezone(timezone.utc)).total_seconds()
                    if 0 <= previous_delta < grace_seconds:
                        local_due = previous_due
                        delta = previous_delta
                    else:
                        continue
                if delta >= grace_seconds:
                    continue
                due_candidates += 1
                plan = {"start_date": start, "end_date": end, "frequency": freq, "days_of_week": _json_list(days_json), "active": bool(active)}
                occurrence_date = local_due.date()
                if not _plan_active_on(plan, occurrence_date):
                    continue
                log_date = occurrence_date.isoformat(); log_time = str(tm)
                if _current_log_status(int(uid), int(pid), log_date, log_time) == "taken":
                    skipped += 1; continue
                # Email fallback and Telegram delivery are tracked separately.  A prior
                # email fallback must not permanently suppress Telegram if the user
                # finishes linking the bot a few seconds later while this occurrence
                # is still inside the due window.
                email_delivery_status = _delivery_status(uid, pid, log_date, log_time)
                lang = "ar"
                taken_token = _create_action_token(uid, pid, member_id, log_date, log_time, lang, "taken")
                snooze_token = _create_action_token(uid, pid, member_id, log_date, log_time, lang, "snooze")
                base = _site_url(); taken_url = f"{base}/meds/email-action/{taken_token}"; snooze_url = f"{base}/meds/email-action/{snooze_token}"
                channel = "telegram" if str(delivery_channel or "email").lower()=="telegram" else "email"
                if channel == "email" and email_delivery_status == "sent":
                    skipped += 1; continue
                if channel == "telegram":
                    tg = medication_telegram.send_due(uid, pid, log_date, log_time, med_name, dose, taken_url, snooze_url, lang)
                    if tg.get("sent"):
                        _record_delivery(uid, pid, log_date, log_time, "sent", provider="telegram")
                        telegram_sent += 1
                        sent += 1
                        continue
                    if tg.get("reason") == "already_sent":
                        # Already delivered in a prior cycle: do not count it again as a new send.
                        _record_delivery(uid, pid, log_date, log_time, "sent", provider="telegram")
                        telegram_skipped += 1
                        skipped += 1
                        continue
                    if tg.get("skipped"):
                        telegram_skipped += 1
                    else:
                        telegram_failed += 1
                    # If fallback email already succeeded on an earlier cycle, do not
                    # send it again. Keep retrying only the Telegram copy until the
                    # five-minute due window closes.
                    if email_delivery_status == "sent":
                        skipped += 1
                        continue
                    # If Telegram was selected but has not been activated yet,
                    # fall back to the registered email rather than dropping a reminder silently.
                user = db.get_ss_user(int(uid))
                if not user or user.get("status") != "active" or not user.get("email"):
                    _record_delivery(uid, pid, log_date, log_time, "failed", error_code="user_email_unavailable"); failed += 1; continue
                subject, body = _render_email(lang, str(med_name), str(dose or ""), taken_url, snooze_url)
                ok, provider = _send_email(str(user["email"]), subject, body)
                if ok:
                    _record_delivery(uid, pid, log_date, log_time, "sent", provider=("email_fallback" if channel=="telegram" else provider)); sent += 1
                else:
                    _record_delivery(uid, pid, log_date, log_time, "failed", provider=provider, error_code=provider); failed += 1
            except Exception:
                failed += 1; log.exception("Medication email reminder failed plan_id=%s", r[1])

        # Deliver due snoozes by email as well. The original occurrence time is
        # retained for Taken/Snooze actions; a synthetic delivery key prevents
        # collision with the first email for that dose.
        conn = db._conn(); c = conn.cursor()
        try:
            cutoff = (now_utc - timedelta(minutes=15)).isoformat()
            c.execute(
                f"SELECT s.id,mr.user_id,s.plan_id,s.member_id,mr.med_name,mr.dose,s.log_date,s.log_time,s.due_at_utc,mr.delivery_channel "
                f"FROM med_snoozes s JOIN medication_reminders mr ON mr.plan_id=s.plan_id AND mr.reminder_time=s.log_time "
                f"WHERE s.status='pending' AND mr.active=1 AND s.due_at_utc<={PH} AND s.due_at_utc>={PH}",
                (now_utc.isoformat(), cutoff),
            )
            snooze_rows = c.fetchall()
        finally:
            conn.close()
        for sr in snooze_rows:
            sid, uid, pid, member_id, med_name, dose, log_date, log_time, due_at, delivery_channel = sr
            delivery_time = f"{log_time}#s{sid}"
            try:
                if _current_log_status(int(uid), int(pid), str(log_date), str(log_time)) == "taken":
                    conn = db._conn(); c = conn.cursor()
                    try:
                        c.execute(f"UPDATE med_snoozes SET status='cancelled' WHERE id={PH}", (int(sid),)); conn.commit()
                    finally:
                        conn.close()
                    skipped += 1; continue
                email_delivery_status = _delivery_status(uid, pid, str(log_date), delivery_time)
                lang = "ar"
                taken_token = _create_action_token(uid, pid, member_id, log_date, log_time, lang, "taken")
                snooze_token = _create_action_token(uid, pid, member_id, log_date, log_time, lang, "snooze")
                base = _site_url(); taken_url = f"{base}/meds/email-action/{taken_token}"; snooze_url = f"{base}/meds/email-action/{snooze_token}"
                channel = "telegram" if str(delivery_channel or "email").lower()=="telegram" else "email"
                if channel == "email" and email_delivery_status == "sent":
                    skipped += 1; continue
                delivered = False
                newly_sent = False
                already_delivered = False
                if channel == "telegram":
                    tg = medication_telegram.send_due(uid, pid, str(log_date), delivery_time, med_name, dose, taken_url, snooze_url, lang)
                    if tg.get("sent"):
                        delivered = True
                        newly_sent = True
                        telegram_sent += 1
                        _record_delivery(uid, pid, str(log_date), delivery_time, "sent", provider="telegram")
                    elif tg.get("reason") == "already_sent":
                        delivered = True
                        already_delivered = True
                        telegram_skipped += 1
                        _record_delivery(uid, pid, str(log_date), delivery_time, "sent", provider="telegram")
                    elif tg.get("skipped"):
                        telegram_skipped += 1
                    else:
                        telegram_failed += 1
                    if not delivered and email_delivery_status == "sent":
                        skipped += 1
                        continue
                if not delivered:
                    user = db.get_ss_user(int(uid))
                    if not user or user.get("status") != "active" or not user.get("email"):
                        _record_delivery(uid, pid, str(log_date), delivery_time, "failed", error_code="user_email_unavailable"); failed += 1; continue
                    subject, body = _render_email(lang, str(med_name), str(dose or ""), taken_url, snooze_url)
                    ok, provider = _send_email(str(user["email"]), subject, body)
                    if ok:
                        delivered = True
                        _record_delivery(uid, pid, str(log_date), delivery_time, "sent", provider=("email_fallback" if channel=="telegram" else provider))
                    else:
                        _record_delivery(uid, pid, str(log_date), delivery_time, "failed", provider=provider, error_code=provider); failed += 1
                if delivered:
                    conn = db._conn(); c = conn.cursor()
                    try:
                        c.execute(f"UPDATE med_snoozes SET status='sent' WHERE id={PH}", (int(sid),)); conn.commit()
                    finally:
                        conn.close()
                    if newly_sent:
                        sent += 1
                    elif already_delivered:
                        skipped += 1
                    else:
                        # Email (including Telegram fallback email) was sent in this cycle.
                        sent += 1
            except Exception:
                failed += 1; log.exception("Snoozed medication email failed plan_id=%s snooze_id=%s", pid, sid)

        return {"sent": sent, "failed": failed, "skipped": skipped, "telegram_sent": telegram_sent, "telegram_failed": telegram_failed, "telegram_skipped": telegram_skipped, "scanned": scanned, "due_candidates": due_candidates, "grace_seconds": grace_seconds, "locked": False, "provider": email_provider_status()["provider"]}
    finally:
        _release_cycle_lock(lock)


def handle_email_action(raw_token: str) -> dict:
    init_schema(); th = _token_hash(raw_token or ""); now = datetime.now(timezone.utc)
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute(f"SELECT id,user_id,plan_id,member_id,log_date,log_time,lang,action,expires_at,consumed_at FROM med_email_actions WHERE token_hash={PH}", (th,)); r = c.fetchone()
    finally:
        conn.close()
    if not r:
        raise PermissionError("invalid_action_token")
    tid, uid, pid, member_id, log_date, log_time, lang, action, expires_at, consumed_at = r
    if consumed_at:
        raise PermissionError("action_token_already_used")
    try:
        exp = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < now:
            raise PermissionError("action_token_expired")
    except ValueError:
        raise PermissionError("action_token_expired")
    claimed = _now(); conn = db._conn(); c = conn.cursor()
    try:
        c.execute(f"UPDATE med_email_actions SET consumed_at={PH} WHERE id={PH} AND consumed_at IS NULL", (claimed, tid)); conn.commit()
        if not c.rowcount:
            raise PermissionError("action_token_already_used")
    finally:
        conn.close()
    try:
        if action == "taken":
            db.log_med_status(int(uid), int(member_id or 0), int(pid), str(log_date), str(log_time), "taken")
            return {"status": "taken", "lang": lang}
        if action == "snooze":
            mins = schedule_snooze(int(uid), int(pid), int(member_id or 0), str(log_date), str(log_time), 10)
            return {"status": "snoozed", "minutes": mins, "lang": lang}
        raise ValueError("unsupported_email_action")
    except Exception:
        conn = db._conn(); c = conn.cursor()
        try:
            c.execute(f"UPDATE med_email_actions SET consumed_at=NULL WHERE id={PH} AND consumed_at={PH}", (tid, claimed)); conn.commit()
        finally:
            conn.close()
        raise


def delivery_summary(limit=100) -> dict:
    init_schema(); conn = db._conn(); c = conn.cursor()
    try:
        c.execute(f"SELECT status,provider,attempted_at,sent_at FROM med_email_deliveries ORDER BY id DESC LIMIT {max(1,min(500,int(limit)))}")
        rows = c.fetchall()
    finally:
        conn.close()
    counts = Counter(str(r[0]) for r in rows)
    return {"sent": counts["sent"], "failed": counts["failed"], "last_sent_at": next((r[3] for r in rows if r[0] == "sent"), None), "provider": email_provider_status()["provider"], "configured": email_provider_status()["configured"]}
