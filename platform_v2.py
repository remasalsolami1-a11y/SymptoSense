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
_EPHEMERAL_IDENTITY_SECRET = secrets.token_bytes(32)


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
            CREATE TABLE IF NOT EXISTS ss_auth_rate_limits (
                id {serial}, key_hash TEXT NOT NULL, success INTEGER NOT NULL,
                attempted_at TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_ss_auth_rate_key_time ON ss_auth_rate_limits(key_hash, attempted_at)")
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS ss_password_resets (
                id {serial}, user_id INTEGER NOT NULL, token_hash TEXT UNIQUE NOT NULL,
                expires_at TEXT NOT NULL, used_at TEXT, created_at TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_ss_password_reset_exp ON ss_password_resets(expires_at)")
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS ss_email_verifications (
                id {serial}, user_id INTEGER NOT NULL, token_hash TEXT UNIQUE NOT NULL,
                expires_at TEXT NOT NULL, used_at TEXT, created_at TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_ss_email_verification_user ON ss_email_verifications(user_id, created_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ss_email_verification_exp ON ss_email_verifications(expires_at)")
        if db.USE_POSTGRES:
            c.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s", ("ss_email_verifications",))
            verification_cols = {row[0] for row in c.fetchall()}
        else:
            c.execute("PRAGMA table_info(ss_email_verifications)")
            verification_cols = {row[1] for row in c.fetchall()}
        if "code_hash" not in verification_cols:
            c.execute("ALTER TABLE ss_email_verifications ADD COLUMN code_hash TEXT")
        if "attempts" not in verification_cols:
            c.execute("ALTER TABLE ss_email_verifications ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0")
        if db.USE_POSTGRES:
            c.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s", ("ss_users",))
            cols = {row[0] for row in c.fetchall()}
        else:
            c.execute("PRAGMA table_info(ss_users)")
            cols = {row[1] for row in c.fetchall()}
        if "status" not in cols:
            c.execute("ALTER TABLE ss_users ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
        if "email_verified" not in cols:
            c.execute("ALTER TABLE ss_users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 1")
        if "email_verified_at" not in cols:
            c.execute("ALTER TABLE ss_users ADD COLUMN email_verified_at TEXT")
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
    # The consent module owns the additive analytics_eligible migration.
    import privacy_features
    privacy_features.init_schema()
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
        c.execute("SELECT id,email,status,created_at,last_login,role,COALESCE(email_verified,1) AS email_verified FROM ss_users ORDER BY created_at DESC")
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
    configured = os.environ.get("WEB_SECRET")
    key = configured.encode() if configured else _EPHEMERAL_IDENTITY_SECRET
    return hashlib.sha256(key + (email or "").strip().lower().encode()).hexdigest()[:24]


def _auth_rate_key(email: str, network_origin: str) -> str:
    """Pseudonymous login-throttle key; raw email/IP are never persisted."""
    configured = os.environ.get("WEB_SECRET")
    key = configured.encode() if configured else _EPHEMERAL_IDENTITY_SECRET
    value = f"login-rate:{(email or '').strip().lower()}|{network_origin or 'unknown'}".encode()
    return hashlib.sha256(key + value).hexdigest()


def login_attempt_allowed(email: str, network_origin: str, max_failures: int = 10,
                          window_minutes: int = 15) -> bool:
    """Return False after repeated failures for the same email/network pair."""
    init_schema()
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=window_minutes)).isoformat()
    conn = db._conn()
    c = conn.cursor()
    try:
        c.execute(
            f"SELECT COUNT(*) FROM ss_auth_rate_limits WHERE key_hash={PH} AND success=0 AND attempted_at>={PH}",
            (_auth_rate_key(email, network_origin), cutoff),
        )
        return int(c.fetchone()[0] or 0) < max(1, int(max_failures))
    finally:
        conn.close()


def record_login_attempt(email: str, network_origin: str, success: bool) -> None:
    """Record a minimal throttle event and clear failures after a valid login."""
    try:
        init_schema()
        conn = db._conn()
        c = conn.cursor()
        key_hash = _auth_rate_key(email, network_origin)
        if success:
            c.execute(f"DELETE FROM ss_auth_rate_limits WHERE key_hash={PH}", (key_hash,))
        else:
            c.execute(
                f"INSERT INTO ss_auth_rate_limits (key_hash,success,attempted_at) VALUES ({','.join([PH] * 3)})",
                (key_hash, 0, _now()),
            )
        conn.commit()
        conn.close()
    except Exception:
        pass


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


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))


def _recent_request_guard(c, table: str, user_id: int, cooldown_seconds: int = 60, max_per_hour: int = 5):
    """Return (allowed, reason) without storing recipient addresses or secrets."""
    c.execute(
        f"SELECT created_at FROM {table} WHERE user_id={PH} ORDER BY created_at DESC LIMIT 1",
        (int(user_id),),
    )
    last = _row(c)
    now = datetime.now(timezone.utc)
    if last and last.get("created_at"):
        try:
            if (now - _parse_iso(last["created_at"])).total_seconds() < int(cooldown_seconds):
                return False, "cooldown"
        except Exception:
            pass
    since = (now - timedelta(hours=1)).isoformat()
    c.execute(
        f"SELECT COUNT(*) AS n FROM {table} WHERE user_id={PH} AND created_at>={PH}",
        (int(user_id), since),
    )
    row = _row(c) or {"n": 0}
    if int(row.get("n") or 0) >= int(max_per_hour):
        return False, "rate_limited"
    return True, None


def create_password_reset(email: str, minutes: int = 30):
    """Create a single-use password reset token with resend throttling.

    The caller should always display a generic response to avoid exposing
    whether an email address has an account.
    """
    init_schema()
    conn = db._conn()
    c = conn.cursor()
    try:
        c.execute(f"SELECT id,status FROM ss_users WHERE lower(email)={PH}", ((email or "").strip().lower(),))
        user = _row(c)
        if not user or user.get("status") != "active":
            return None, None, "not_available"
        allowed, reason = _recent_request_guard(c, "ss_password_resets", int(user["id"]), 60, 5)
        if not allowed:
            return None, int(user["id"]), reason
        token = secrets.token_urlsafe(36)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        now = datetime.now(timezone.utc)
        # Keep an earlier unexpired link usable until this new message is
        # actually delivered. A provider failure must not destroy the user's
        # only working recovery path. Consuming any link invalidates all others.
        c.execute(
            "INSERT INTO ss_password_resets (user_id,token_hash,expires_at,created_at) "
            f"VALUES ({','.join([PH] * 4)})",
            (user["id"], token_hash, (now + timedelta(minutes=minutes)).isoformat(), now.isoformat()),
        )
        conn.commit()
        return token, int(user["id"]), None
    finally:
        conn.close()


def password_reset_status(token: str) -> str:
    init_schema()
    conn = db._conn(); c = conn.cursor()
    token_hash = hashlib.sha256((token or "").encode()).hexdigest()
    try:
        c.execute(f"SELECT expires_at,used_at FROM ss_password_resets WHERE token_hash={PH}", (token_hash,))
        row = _row(c)
        if not row:
            return "invalid"
        if row.get("used_at"):
            return "used"
        try:
            if _parse_iso(row.get("expires_at")) < datetime.now(timezone.utc):
                return "expired"
        except Exception:
            return "invalid"
        return "valid"
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
        if _parse_iso(row["expires_at"]) < datetime.now(timezone.utc):
            return False
        now = _now()
        # Claim the one-time token before changing the password so concurrent
        # requests cannot both consume the same link.
        c.execute(
            f"UPDATE ss_password_resets SET used_at={PH} WHERE id={PH} AND used_at IS NULL",
            (now, row["id"]),
        )
        if getattr(c, "rowcount", 1) == 0:
            conn.rollback()
            return False
        c.execute(f"UPDATE ss_users SET password_hash={PH} WHERE id={PH}", (db._hash_password(password), row["user_id"]))
        # Invalidate all other reset links for that account after a successful reset.
        c.execute(
            f"UPDATE ss_password_resets SET used_at={PH} WHERE user_id={PH} AND used_at IS NULL",
            (now, row["user_id"]),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def create_email_verification(user_id: int, minutes: int = 24 * 60, cooldown_seconds: int = 60, max_per_hour: int = 5):
    """Create a random, hashed, single-use verification token for an existing account."""
    init_schema()
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute(
            f"SELECT id,email,status,COALESCE(email_verified,1) AS email_verified FROM ss_users WHERE id={PH}",
            (int(user_id),),
        )
        user = _row(c)
        if not user or user.get("status") != "active":
            return None, None, "account_unavailable"
        if bool(user.get("email_verified")):
            return None, user.get("email"), "already_verified"
        allowed, reason = _recent_request_guard(c, "ss_email_verifications", int(user_id), cooldown_seconds, max_per_hour)
        if not allowed:
            return None, user.get("email"), reason
        token = secrets.token_urlsafe(36)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        now = datetime.now(timezone.utc)
        # Keep earlier unexpired links valid until one is consumed. This avoids
        # a failed resend revoking the only verification email the user has.
        c.execute(
            "INSERT INTO ss_email_verifications (user_id,token_hash,expires_at,created_at) "
            f"VALUES ({','.join([PH] * 4)})",
            (int(user_id), token_hash, (now + timedelta(minutes=minutes)).isoformat(), now.isoformat()),
        )
        conn.commit()
        return token, user.get("email"), None
    finally:
        conn.close()


def _verification_code_hash(user_id: int, code: str) -> str:
    """Hash an OTP with the server secret; the plain code is never stored."""
    secret = os.environ.get("WEB_SECRET", "").encode()
    return hashlib.sha256(secret + b":" + str(int(user_id)).encode() + b":" + str(code).encode()).hexdigest()


def create_email_verification_code(user_id: int, minutes: int = 15,
                                   cooldown_seconds: int = 60, max_per_hour: int = 5):
    """Create a six-digit OTP plus a backward-compatible one-time link token."""
    init_schema()
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute(
            f"SELECT id,email,status,COALESCE(email_verified,1) AS email_verified FROM ss_users WHERE id={PH}",
            (int(user_id),),
        )
        user = _row(c)
        if not user or user.get("status") != "active":
            return None, None, None, "account_unavailable"
        if bool(user.get("email_verified")):
            return None, None, user.get("email"), "already_verified"
        allowed, reason = _recent_request_guard(c, "ss_email_verifications", int(user_id), cooldown_seconds, max_per_hour)
        if not allowed:
            return None, None, user.get("email"), reason
        token = secrets.token_urlsafe(36)
        code = f"{secrets.randbelow(1_000_000):06d}"
        now = datetime.now(timezone.utc)
        c.execute(
            "INSERT INTO ss_email_verifications (user_id,token_hash,code_hash,attempts,expires_at,created_at) "
            f"VALUES ({','.join([PH] * 6)})",
            (int(user_id), hashlib.sha256(token.encode()).hexdigest(),
             _verification_code_hash(int(user_id), code), 0,
             (now + timedelta(minutes=minutes)).isoformat(), now.isoformat()),
        )
        conn.commit()
        return token, code, user.get("email"), None
    finally:
        conn.close()


def consume_email_verification_code(user_id: int, code: str, max_attempts: int = 6):
    """Consume the latest OTP. It expires, is single-use, and limits guesses."""
    value = (code or "").strip()
    if not re.fullmatch(r"\d{6}", value):
        return None, "invalid"
    init_schema()
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute(
            f"SELECT id,expires_at,used_at,attempts,code_hash FROM ss_email_verifications "
            f"WHERE user_id={PH} AND code_hash IS NOT NULL ORDER BY id DESC",
            (int(user_id),),
        )
        row = _row(c)
        if not row:
            return None, "invalid"
        if row.get("used_at"):
            return None, "used"
        if _parse_iso(row.get("expires_at")) < datetime.now(timezone.utc):
            return None, "expired"
        attempts = int(row.get("attempts") or 0)
        if attempts >= max_attempts:
            return None, "too_many_attempts"
        expected = _verification_code_hash(int(user_id), value)
        if not secrets.compare_digest(str(row.get("code_hash") or ""), expected):
            attempts += 1
            c.execute(f"UPDATE ss_email_verifications SET attempts={PH} WHERE id={PH}", (attempts, row["id"]))
            conn.commit()
            return None, "too_many_attempts" if attempts >= max_attempts else "invalid"
        now = _now()
        c.execute(
            f"UPDATE ss_email_verifications SET used_at={PH} WHERE id={PH} AND used_at IS NULL",
            (now, row["id"]),
        )
        if getattr(c, "rowcount", 1) == 0:
            conn.rollback(); return None, "used"
        c.execute(f"UPDATE ss_users SET email_verified=1,email_verified_at={PH} WHERE id={PH}", (now, int(user_id)))
        c.execute(f"UPDATE ss_email_verifications SET used_at={PH} WHERE user_id={PH} AND used_at IS NULL", (now, int(user_id)))
        conn.commit()
        return int(user_id), "verified"
    finally:
        conn.close()


def email_verification_status(token: str) -> str:
    init_schema()
    conn = db._conn(); c = conn.cursor()
    token_hash = hashlib.sha256((token or "").encode()).hexdigest()
    try:
        c.execute(f"SELECT expires_at,used_at FROM ss_email_verifications WHERE token_hash={PH}", (token_hash,))
        row = _row(c)
        if not row:
            return "invalid"
        if row.get("used_at"):
            return "used"
        try:
            if _parse_iso(row.get("expires_at")) < datetime.now(timezone.utc):
                return "expired"
        except Exception:
            return "invalid"
        return "valid"
    finally:
        conn.close()


def consume_email_verification(token: str):
    """Verify the account represented by token. Returns (user_id, status)."""
    init_schema()
    conn = db._conn(); c = conn.cursor()
    token_hash = hashlib.sha256((token or "").encode()).hexdigest()
    try:
        c.execute(
            f"SELECT id,user_id,expires_at,used_at FROM ss_email_verifications WHERE token_hash={PH}",
            (token_hash,),
        )
        row = _row(c)
        if not row:
            return None, "invalid"
        if row.get("used_at"):
            return None, "used"
        if _parse_iso(row.get("expires_at")) < datetime.now(timezone.utc):
            return None, "expired"
        now = _now()
        # Atomic enough for both supported DBs: only an unused token can win.
        c.execute(
            f"UPDATE ss_email_verifications SET used_at={PH} WHERE id={PH} AND used_at IS NULL",
            (now, row["id"]),
        )
        if getattr(c, "rowcount", 1) == 0:
            conn.rollback()
            return None, "used"
        c.execute(
            f"UPDATE ss_users SET email_verified=1,email_verified_at={PH} WHERE id={PH}",
            (now, row["user_id"]),
        )
        c.execute(
            f"UPDATE ss_email_verifications SET used_at={PH} WHERE user_id={PH} AND used_at IS NULL",
            (now, row["user_id"]),
        )
        conn.commit()
        return int(row["user_id"]), "verified"
    finally:
        conn.close()



def discard_email_verification_token(token: str):
    """Remove an unsent verification token so provider failures do not trigger cooldown."""
    init_schema()
    conn = db._conn(); c = conn.cursor()
    token_hash = hashlib.sha256((token or "").encode()).hexdigest()
    try:
        c.execute(f"DELETE FROM ss_email_verifications WHERE token_hash={PH} AND used_at IS NULL", (token_hash,))
        conn.commit()
    finally:
        conn.close()


def discard_password_reset_token(token: str):
    """Remove an unsent reset token without exposing it to logs or clients."""
    init_schema()
    conn = db._conn(); c = conn.cursor()
    token_hash = hashlib.sha256((token or "").encode()).hexdigest()
    try:
        c.execute(f"DELETE FROM ss_password_resets WHERE token_hash={PH} AND used_at IS NULL", (token_hash,))
        conn.commit()
    finally:
        conn.close()

def invalidate_email_verifications(user_id: int):
    init_schema()
    conn = db._conn(); c = conn.cursor()
    try:
        now = _now()
        c.execute(
            f"UPDATE ss_email_verifications SET used_at={PH} WHERE user_id={PH} AND used_at IS NULL",
            (now, int(user_id)),
        )
        conn.commit()
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
