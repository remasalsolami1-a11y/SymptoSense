"""Operational services for SymptoSense V2.

This module deliberately stores *operational metadata only*.  Usage events do
not include symptoms, health-profile fields, chat text, analysis results, IP
addresses, email addresses, or other medical/personal content.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from collections import Counter
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import db


PH = db.PH
ALLOWED_CONTENT_TYPES = {"health_tip", "faq", "educational", "mental_health", "awareness", "intro"}
ALLOWED_STATUSES = {"active", "draft", "disabled"}
ALLOWED_ROLES = {"user", "admin"}
_SCHEMA_KEY = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rows(c):
    columns = [d[0] for d in c.description]
    return [dict(zip(columns, row)) for row in c.fetchall()]


def _row(c):
    rows = _rows(c)
    return rows[0] if rows else None


def _json(value):
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def init_schema() -> None:
    """Create V2 tables. Safe to call on every process start."""
    global _SCHEMA_KEY
    schema_key = (bool(db.USE_POSTGRES), db.DATABASE_URL if db.USE_POSTGRES else os.path.abspath(db.DB_PATH))
    if _SCHEMA_KEY == schema_key:
        return
    db.init_db()
    conn = db._conn()
    c = conn.cursor()
    serial = "SERIAL PRIMARY KEY" if db.USE_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"
    try:
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS ss_usage_events (
                id {serial}, event_type TEXT NOT NULL, service TEXT NOT NULL,
                path TEXT NOT NULL, lang TEXT NOT NULL, device_type TEXT NOT NULL,
                response_status INTEGER, response_ms INTEGER, created_at TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_ss_usage_created ON ss_usage_events(created_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ss_usage_service ON ss_usage_events(service)")
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS ss_content (
                id {serial}, slug TEXT UNIQUE NOT NULL, content_type TEXT NOT NULL,
                title_ar TEXT NOT NULL, title_en TEXT NOT NULL,
                body_ar TEXT NOT NULL, body_en TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'general', status TEXT NOT NULL DEFAULT 'draft',
                version INTEGER NOT NULL DEFAULT 1, created_by INTEGER, updated_by INTEGER,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_ss_content_status ON ss_content(status, content_type)")
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS ss_admin_audit (
                id {serial}, admin_id INTEGER, action TEXT NOT NULL,
                entity_type TEXT NOT NULL, entity_id TEXT,
                previous_value TEXT, new_value TEXT, timestamp TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_ss_admin_audit_time ON ss_admin_audit(timestamp)")
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS ss_login_activity (
                id {serial}, user_id INTEGER, identity_hash TEXT NOT NULL,
                success INTEGER NOT NULL, is_admin INTEGER NOT NULL DEFAULT 0,
                device_type TEXT NOT NULL, occurred_at TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_ss_login_activity_time ON ss_login_activity(occurred_at)")
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS ss_password_resets (
                id {serial}, user_id INTEGER NOT NULL, token_hash TEXT UNIQUE NOT NULL,
                expires_at TEXT NOT NULL, used_at TEXT, created_at TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_ss_password_reset_exp ON ss_password_resets(expires_at)")
        if db.USE_POSTGRES:
            c.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s", ("ss_users",))
            cols = {row[0] for row in c.fetchall()}
        else:
            c.execute("PRAGMA table_info(ss_users)")
            cols = {row[1] for row in c.fetchall()}
        if "status" not in cols:
            c.execute("ALTER TABLE ss_users ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
        conn.commit()
        _SCHEMA_KEY = schema_key
    finally:
        conn.close()


def device_type(user_agent: str) -> str:
    ua = (user_agent or "").lower()
    if any(x in ua for x in ("ipad", "tablet", "kindle")):
        return "tablet"
    if any(x in ua for x in ("mobile", "iphone", "android")):
        return "mobile"
    return "desktop"


def classify_service(path: str) -> str:
    path = (path or "/").split("?", 1)[0]
    rules = (
        ("symptom_analysis", ("/chat", "/api/analyze")),
        ("assistant", ("/api/assistant",)),
        ("lab_analysis", ("/blood", "/api/blood")),
        ("medications", ("/meds", "/api/med")),
        ("mental_health", ("/relax", "/checkin", "/api/wellbeing")),
        ("calculators", ("/calculators", "/api/calc")),
        ("medical_sources", ("/sources", "/api/sources")),
        ("accounts", ("/login", "/register", "/profile", "/settings")),
        ("admin", ("/admin", "/api/admin")),
    )
    for service, prefixes in rules:
        if any(path.startswith(prefix) for prefix in prefixes):
            return service
    return "site"


def record_usage(event_type: str, path: str, lang: str, user_agent: str,
                 response_status: int = 200, response_ms: int | None = None,
                 service: str | None = None) -> None:
    """Store a content-free operational event; errors never affect requests."""
    try:
        init_schema()
        conn = db._conn()
        c = conn.cursor()
        c.execute(
            "INSERT INTO ss_usage_events (event_type,service,path,lang,device_type,response_status,response_ms,created_at) "
            f"VALUES ({','.join([PH] * 8)})",
            (
                (event_type or "page_view")[:40], (service or classify_service(path))[:50],
                (path or "/")[:180], "en" if lang == "en" else "ar",
                device_type(user_agent), int(response_status or 0),
                int(response_ms) if response_ms is not None else None, _now(),
            ),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def analytics_summary(days: int = 30) -> dict:
    """Return aggregate, privacy-preserving operational analytics only."""
    init_schema()
    days = max(1, min(365, int(days or 30)))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    conn = db._conn()
    c = conn.cursor()
    try:
        c.execute(
            "SELECT event_type,service,path,lang,device_type,response_status,response_ms,created_at "
            f"FROM ss_usage_events WHERE created_at >= {PH} ORDER BY created_at",
            (since.isoformat(),),
        )
        events = _rows(c)
        c.execute("SELECT COUNT(*) AS n FROM ss_users")
        total_users = int((_row(c) or {}).get("n") or 0)
        c.execute("SELECT created_at FROM ss_users WHERE created_at >= %s ORDER BY created_at" % PH, (since.isoformat(),))
        user_rows = [r[0] for r in c.fetchall()]
        c.execute("SELECT COUNT(*) AS n FROM records")
        total_analyses = int((_row(c) or {}).get("n") or 0)
        c.execute("SELECT timestamp,symptoms FROM records WHERE timestamp >= %s AND COALESCE(analytics_eligible,0)=1 ORDER BY timestamp" % PH, (since.isoformat(),))
        analysis_rows = c.fetchall()
    finally:
        conn.close()

    services, languages, devices, paths = Counter(), Counter(), Counter(), Counter()
    activity_daily, assistant_daily = Counter(), Counter()
    errors = alerts = assistant = 0
    response_values = []
    for event in events:
        services[event["service"]] += 1
        languages[event["lang"]] += 1
        devices[event["device_type"]] += 1
        paths[event["path"]] += 1
        day = str(event["created_at"])[:10]
        activity_daily[day] += 1
        status = int(event.get("response_status") or 0)
        errors += int(status >= 400)
        alerts += int(event.get("event_type") == "safety_alert")
        if event.get("event_type") == "assistant_use":
            assistant += 1
            assistant_daily[day] += 1
        if event.get("response_ms") is not None:
            response_values.append(int(event["response_ms"]))

    users_daily = Counter(str(ts)[:10] for ts in user_rows)
    analyses_daily = Counter(str(row[0])[:10] for row in analysis_rows)
    symptom_counter = Counter()
    for _, symptoms in analysis_rows:
        for symptom in str(symptoms or "").split(","):
            symptom = symptom.strip()
            if symptom:
                symptom_counter[symptom] += 1

    today = datetime.now(timezone.utc).date()
    periods = {"daily": 0, "weekly": 0, "monthly": len(events)}
    for event in events:
        try:
            dt = datetime.fromisoformat(str(event["created_at"]).replace("Z", "+00:00")).date()
            periods["daily"] += int(dt == today)
            periods["weekly"] += int(dt >= today - timedelta(days=6))
        except Exception:
            pass

    all_days = [(since.date() + timedelta(days=i)).isoformat() for i in range(days + 1)]
    return {
        "range_days": days,
        "total_users": total_users,
        "total_events": len(events),
        "analyses": total_analyses,
        "range_analyses": len(analysis_rows),
        "assistant_uses": assistant,
        "errors": errors,
        "alerts": alerts,
        "activity": len(events),
        "periods": periods,
        "services": [{"name": k, "count": v} for k, v in services.most_common(12)],
        "languages": dict(languages),
        "devices": dict(devices),
        "sections": [{"path": k, "count": v} for k, v in paths.most_common(12)],
        "top_symptoms": [{"name": k, "count": v} for k, v in symptom_counter.most_common(12)],
        "timeline": [{"date": d, "count": activity_daily[d]} for d in all_days],
        "users_timeline": [{"date": d, "count": users_daily[d]} for d in all_days],
        "analyses_timeline": [{"date": d, "count": analyses_daily[d]} for d in all_days],
        "assistant_timeline": [{"date": d, "count": assistant_daily[d]} for d in all_days],
        "average_response_ms": round(sum(response_values) / len(response_values)) if response_values else None,
    }


def _clean_slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9_-]+", "-", (value or "").strip().lower()).strip("-")
    return value[:100]


def validate_content(data: dict) -> dict:
    value = {
        "slug": _clean_slug(data.get("slug")),
        "content_type": str(data.get("content_type") or "").strip(),
        "title_ar": str(data.get("title_ar") or "").strip()[:250],
        "title_en": str(data.get("title_en") or "").strip()[:250],
        "body_ar": str(data.get("body_ar") or "").strip()[:12000],
        "body_en": str(data.get("body_en") or "").strip()[:12000],
        "category": str(data.get("category") or "general").strip()[:100],
        "status": str(data.get("status") or "draft").strip(),
    }
    if not value["slug"] or value["content_type"] not in ALLOWED_CONTENT_TYPES:
        raise ValueError("invalid_content_type_or_slug")
    if not all((value["title_ar"], value["title_en"], value["body_ar"], value["body_en"])):
        raise ValueError("arabic_and_english_content_required")
    if value["status"] not in ALLOWED_STATUSES:
        raise ValueError("invalid_status")
    return value


def list_content(public_only: bool = False, query: str = "", content_type: str = "") -> list[dict]:
    init_schema()
    conn = db._conn()
    c = conn.cursor()
    try:
        clauses, params = [], []
        if public_only:
            clauses.append(f"status={PH}")
            params.append("active")
        if content_type:
            clauses.append(f"content_type={PH}")
            params.append(content_type)
        sql = "SELECT * FROM ss_content"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY updated_at DESC"
        c.execute(sql, tuple(params))
        rows = _rows(c)
    finally:
        conn.close()
    q = (query or "").strip().lower()
    if q:
        rows = [r for r in rows if q in " ".join(str(v) for v in r.values()).lower()]
    return rows


def get_content(content_id: int) -> dict | None:
    init_schema()
    conn = db._conn()
    c = conn.cursor()
    try:
        c.execute(f"SELECT * FROM ss_content WHERE id={PH}", (int(content_id),))
        return _row(c)
    finally:
        conn.close()


def audit(admin_id: int | None, action: str, entity_type: str, entity_id,
          previous=None, new=None) -> None:
    init_schema()
    conn = db._conn()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO ss_admin_audit (admin_id,action,entity_type,entity_id,previous_value,new_value,timestamp) "
            f"VALUES ({','.join([PH] * 7)})",
            (admin_id, action[:80], entity_type[:80], str(entity_id or "")[:100],
             _json(previous), _json(new), _now()),
        )
        conn.commit()
    finally:
        conn.close()


def save_content(data: dict, admin_id: int, content_id: int | None = None) -> dict:
    value = validate_content(data)
    init_schema()
    conn = db._conn()
    c = conn.cursor()
    previous = None
    try:
        if content_id:
            c.execute(f"SELECT * FROM ss_content WHERE id={PH}", (int(content_id),))
            previous = _row(c)
            if not previous:
                raise ValueError("content_not_found")
            c.execute(
                "UPDATE ss_content SET slug={0},content_type={0},title_ar={0},title_en={0},body_ar={0},body_en={0},"
                "category={0},status={0},version=version+1,updated_by={0},updated_at={0} WHERE id={0}".format(PH),
                (value["slug"], value["content_type"], value["title_ar"], value["title_en"],
                 value["body_ar"], value["body_en"], value["category"], value["status"],
                 admin_id, _now(), int(content_id)),
            )
            saved_id = int(content_id)
        else:
            now = _now()
            values = (value["slug"], value["content_type"], value["title_ar"], value["title_en"],
                      value["body_ar"], value["body_en"], value["category"], value["status"],
                      admin_id, admin_id, now, now)
            if db.USE_POSTGRES:
                c.execute(
                    "INSERT INTO ss_content (slug,content_type,title_ar,title_en,body_ar,body_en,category,status,created_by,updated_by,created_at,updated_at) "
                    f"VALUES ({','.join([PH] * 12)}) RETURNING id", values,
                )
                saved_id = c.fetchone()[0]
            else:
                c.execute(
                    "INSERT INTO ss_content (slug,content_type,title_ar,title_en,body_ar,body_en,category,status,created_by,updated_by,created_at,updated_at) "
                    f"VALUES ({','.join([PH] * 12)})", values,
                )
                saved_id = c.lastrowid
        conn.commit()
    finally:
        conn.close()
    saved = get_content(saved_id)
    audit(admin_id, "updated" if previous else "created", "content", saved_id, previous, saved)
    return saved


def delete_content(content_id: int, admin_id: int) -> None:
    previous = get_content(content_id)
    if not previous:
        raise ValueError("content_not_found")
    conn = db._conn()
    c = conn.cursor()
    try:
        # Published content is recoverably disabled. Drafts can be removed.
        if previous.get("status") == "active":
            c.execute(f"UPDATE ss_content SET status='disabled',version=version+1,updated_by={PH},updated_at={PH} WHERE id={PH}",
                      (admin_id, _now(), int(content_id)))
            action = "disabled"
        else:
            c.execute(f"DELETE FROM ss_content WHERE id={PH}", (int(content_id),))
            action = "deleted"
        conn.commit()
    finally:
        conn.close()
    audit(admin_id, action, "content", content_id, previous, None)


def list_users_admin() -> list[dict]:
    """Return only the fields the admin UI needs; no health data or chats."""
    init_schema()
    conn = db._conn()
    c = conn.cursor()
    try:
        c.execute("SELECT id,email,status,created_at,last_login,role FROM ss_users ORDER BY created_at DESC")
        rows = _rows(c)
        # Email is used only server-side to compute the effective owner role;
        # it is deliberately removed from the Admin user listing response.
        for row in rows:
            row["role"] = "admin" if str(row.get("role") or "user").strip().lower() == "admin" and db.is_owner_admin_email(row.get("email")) else "user"
            row.pop("email", None)
        return rows
    finally:
        conn.close()


def set_user_status(user_id: int, status: str, admin_id: int) -> dict:
    if status not in {"active", "disabled"}:
        raise ValueError("invalid_status")
    init_schema()
    conn = db._conn()
    c = conn.cursor()
    try:
        c.execute(f"SELECT id,status,role FROM ss_users WHERE id={PH}", (int(user_id),))
        previous = _row(c)
        if not previous:
            raise ValueError("user_not_found")
        if int(user_id) == int(admin_id) and status == "disabled":
            raise ValueError("cannot_disable_current_admin")
        c.execute(f"UPDATE ss_users SET status={PH} WHERE id={PH}", (status, int(user_id)))
        conn.commit()
    finally:
        conn.close()
    updated = {**previous, "status": status}
    audit(admin_id, "status_changed", "user_account", user_id, previous, updated)
    return updated


def set_user_role(user_id: int, role: str, admin_id: int) -> dict:
    """Role changes are intentionally unavailable from the dashboard/API.

    The single owner Admin is synchronized only from the authenticated existing owner account.
    """
    raise ValueError("role_management_disabled")


def identity_hash(email: str) -> str:
    key = os.environ.get("WEB_SECRET", "symptosense-audit").encode()
    return hashlib.sha256(key + (email or "").strip().lower().encode()).hexdigest()[:24]


def log_login(email: str, user_id: int | None, success: bool, is_admin: bool, user_agent: str) -> None:
    try:
        init_schema()
        conn = db._conn()
        c = conn.cursor()
        c.execute(
            "INSERT INTO ss_login_activity (user_id,identity_hash,success,is_admin,device_type,occurred_at) "
            f"VALUES ({','.join([PH] * 6)})",
            (user_id, identity_hash(email), int(bool(success)), int(bool(is_admin)),
             device_type(user_agent), _now()),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def login_activity(limit: int = 200) -> list[dict]:
    init_schema()
    conn = db._conn()
    c = conn.cursor()
    try:
        c.execute("SELECT id,user_id,success,is_admin,device_type,occurred_at FROM ss_login_activity ORDER BY id DESC " +
                  (f"LIMIT {PH}"), (max(1, min(500, int(limit))),))
        return _rows(c)
    finally:
        conn.close()


def audit_log(limit: int = 200) -> list[dict]:
    init_schema()
    conn = db._conn()
    c = conn.cursor()
    try:
        c.execute("SELECT id,admin_id,action,entity_type,entity_id,previous_value,new_value,timestamp "
                  f"FROM ss_admin_audit ORDER BY id DESC LIMIT {PH}", (max(1, min(500, int(limit))),))
        return _rows(c)
    finally:
        conn.close()


def create_password_reset(email: str, minutes: int = 30):
    init_schema()
    conn = db._conn()
    c = conn.cursor()
    token = secrets.token_urlsafe(36)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    try:
        c.execute(f"SELECT id,status FROM ss_users WHERE email={PH}", ((email or "").strip().lower(),))
        user = _row(c)
        if not user or user.get("status") != "active":
            return None, None
        now = datetime.now(timezone.utc)
        c.execute(
            "INSERT INTO ss_password_resets (user_id,token_hash,expires_at,created_at) "
            f"VALUES ({','.join([PH] * 4)})",
            (user["id"], token_hash, (now + timedelta(minutes=minutes)).isoformat(), now.isoformat()),
        )
        conn.commit()
        return token, user["id"]
    finally:
        conn.close()


def consume_password_reset(token: str, password: str) -> bool:
    if len(password or "") < 8:
        raise ValueError("password_too_short")
    init_schema()
    conn = db._conn()
    c = conn.cursor()
    token_hash = hashlib.sha256((token or "").encode()).hexdigest()
    try:
        c.execute(f"SELECT id,user_id,expires_at,used_at FROM ss_password_resets WHERE token_hash={PH}", (token_hash,))
        row = _row(c)
        if not row or row.get("used_at"):
            return False
        expires = datetime.fromisoformat(str(row["expires_at"]).replace("Z", "+00:00"))
        if expires < datetime.now(timezone.utc):
            return False
        c.execute(f"UPDATE ss_users SET password_hash={PH} WHERE id={PH}", (db._hash_password(password), row["user_id"]))
        c.execute(f"UPDATE ss_password_resets SET used_at={PH} WHERE id={PH}", (_now(), row["id"]))
        conn.commit()
        return True
    finally:
        conn.close()


def email_is_valid(value: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", (value or "").strip()))


def official_https_url(value: str) -> bool:
    try:
        parsed = urlparse(value or "")
        return parsed.scheme == "https" and bool(parsed.netloc)
    except Exception:
        return False
