"""Optional Telegram layer for medication reminders.

Email remains the always-on baseline. Telegram is an optional additional channel
linked once through a deep-link to the SymptoSense bot.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import threading
import re
import time
from datetime import datetime, timedelta, timezone

import requests

import db

PH = db.PH
_SCHEMA_READY_KEY = None
_SCHEMA_LOCK = threading.Lock()


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _serial():
    return "SERIAL PRIMARY KEY" if db.USE_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"


def _hash(value: str) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


_BOT_CACHE = {"at": 0.0, "token_sig": "", "username": "", "verified": False, "error": ""}


def _env_bot_username() -> str:
    return os.getenv("TELEGRAM_BOT_USERNAME", "").strip().lstrip("@")


def _bot_token() -> str:
    return os.getenv("TELEGRAM_BOT_TOKEN", "").strip()


def bot_identity(force: bool = False) -> dict:
    """Resolve the bot username from Telegram getMe, with env fallback.

    This deliberately does not make a temporary Telegram/network failure look like
    a missing server configuration when TELEGRAM_BOT_USERNAME is already set.
    """
    token = _bot_token()
    env_username = _env_bot_username()
    if not token:
        return {"ok": False, "username": env_username, "verified": False, "source": "env", "error": "missing_bot_token"}

    token_sig = _hash(token)[:16]
    now = time.monotonic()
    if (not force and _BOT_CACHE.get("token_sig") == token_sig and now - float(_BOT_CACHE.get("at") or 0) < 600):
        username = str(_BOT_CACHE.get("username") or env_username)
        return {
            "ok": bool(username),
            "username": username,
            "verified": bool(_BOT_CACHE.get("verified")),
            "source": "telegram" if _BOT_CACHE.get("verified") else "env",
            "error": str(_BOT_CACHE.get("error") or ""),
        }

    error = ""
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=8)
        data = r.json() if r.content else {}
        if r.ok and data.get("ok") and isinstance(data.get("result"), dict):
            username = str(data["result"].get("username") or "").strip().lstrip("@")
            if username:
                _BOT_CACHE.update({"at": now, "token_sig": token_sig, "username": username, "verified": True, "error": ""})
                return {"ok": True, "username": username, "verified": True, "source": "telegram", "error": ""}
        error = f"getme_http_{r.status_code}"
    except Exception:
        error = "getme_request_failed"

    # If Telegram is temporarily unreachable, an explicit Railway username still
    # keeps linking available instead of showing a false "not configured" state.
    _BOT_CACHE.update({"at": now, "token_sig": token_sig, "username": env_username, "verified": False, "error": error})
    return {"ok": bool(env_username), "username": env_username, "verified": False, "source": "env", "error": error or ("missing_bot_username" if not env_username else "")}


def configuration_status(force_verify: bool = False) -> dict:
    ident = bot_identity(force=force_verify)
    secret_ok = bool(os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip())
    username = str(ident.get("username") or "")
    token_ok = bool(_bot_token())
    configured_ok = bool(token_ok and username and secret_ok)
    if not token_ok:
        config_error = "missing_bot_token"
    elif not username:
        config_error = "missing_bot_username"
    elif not secret_ok:
        config_error = "missing_webhook_secret"
    else:
        config_error = ""
    return {
        "configured": configured_ok,
        "bot_ready": bool(token_ok and username),
        "bot_username": username,
        "bot_verified": bool(ident.get("verified")),
        "bot_identity_source": ident.get("source") or "",
        "bot_check_error": ident.get("error") or "",
        "webhook_secret_configured": secret_ok,
        "config_error": config_error,
    }


def configured() -> bool:
    return bool(configuration_status().get("configured"))


def init_schema():
    """Create Telegram reminder tables once per database identity."""
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
            c.execute(f"""
                CREATE TABLE IF NOT EXISTS med_telegram_links (
                    user_id INTEGER PRIMARY KEY,
                    chat_id TEXT UNIQUE,
                    telegram_username TEXT,
                    pending_username TEXT,
                    enabled INTEGER NOT NULL DEFAULT 0,
                    connect_token_hash TEXT UNIQUE,
                    connect_expires_at TEXT,
                    linked_at TEXT,
                    updated_at TEXT NOT NULL
                )
            """)
            try:
                if db.USE_POSTGRES:
                    c.execute("ALTER TABLE med_telegram_links ADD COLUMN IF NOT EXISTS pending_username TEXT")
                else:
                    c.execute("PRAGMA table_info(med_telegram_links)")
                    cols={r[1] for r in c.fetchall()}
                    if "pending_username" not in cols:
                        c.execute("ALTER TABLE med_telegram_links ADD COLUMN pending_username TEXT")
            except Exception:
                pass
            c.execute("CREATE INDEX IF NOT EXISTS idx_med_telegram_chat ON med_telegram_links(chat_id)")
            c.execute(f"""
                CREATE TABLE IF NOT EXISTS med_telegram_deliveries (
                    id {_serial()},
                    user_id INTEGER NOT NULL,
                    plan_id INTEGER NOT NULL,
                    log_date TEXT NOT NULL,
                    log_time TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempted_at TEXT,
                    sent_at TEXT,
                    error_code TEXT,
                    UNIQUE(user_id, plan_id, log_date, log_time)
                )
            """)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        _SCHEMA_READY_KEY = key


def normalize_username(value: str) -> str:
    username = str(value or "").strip().lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", username):
        raise ValueError("invalid_telegram_username")
    return username


def prepare_username(user_id, username: str) -> dict:
    """Save the requested Telegram username and return a one-time activation link."""
    init_schema(); username = normalize_username(username); now = _now()
    conn=db._conn(); c=conn.cursor()
    try:
        vals=(int(user_id), username, now)
        if db.USE_POSTGRES:
            c.execute(
                "INSERT INTO med_telegram_links(user_id,pending_username,updated_at) VALUES(%s,%s,%s) "
                "ON CONFLICT(user_id) DO UPDATE SET pending_username=EXCLUDED.pending_username,updated_at=EXCLUDED.updated_at",
                vals,
            )
        else:
            c.execute(
                "INSERT INTO med_telegram_links(user_id,pending_username,updated_at) VALUES(?,?,?) "
                "ON CONFLICT(user_id) DO UPDATE SET pending_username=excluded.pending_username,updated_at=excluded.updated_at",
                vals,
            )
        conn.commit()
    finally:
        conn.close()
    current=status(user_id)
    if current.get("linked") and str(current.get("telegram_username") or "").lower()==username.lower():
        return {"configured": current.get("configured", False), "linked": True, "username": username, "url": None}
    link=create_connect_link(user_id)
    return {**link, "linked": False, "username": username}


def _row(user_id):
    init_schema(); conn = db._conn(); c = conn.cursor()
    try:
        c.execute(f"SELECT chat_id,telegram_username,pending_username,enabled,linked_at,updated_at FROM med_telegram_links WHERE user_id={PH}", (int(user_id),))
        r = c.fetchone()
        if not r:
            return None
        return {"chat_id": r[0], "telegram_username": r[1], "pending_username": r[2], "enabled": bool(r[3]), "linked_at": r[4], "updated_at": r[5]}
    finally:
        conn.close()


def status(user_id) -> dict:
    cfg = configuration_status()
    state_error = ""
    try:
        row = _row(user_id) or {}
    except Exception:
        # Configuration and account-link state are separate concerns. A DB read
        # problem must not incorrectly label Telegram itself as unconfigured.
        row = {}
        state_error = "link_state_unavailable"
    return {
        **cfg,
        "linked": bool(row.get("chat_id")),
        "enabled": bool(row.get("chat_id") and row.get("enabled")),
        "telegram_username": row.get("telegram_username") or "",
        "pending_username": row.get("pending_username") or "",
        "linked_at": row.get("linked_at"),
        "state_error": state_error,
    }


def create_connect_link(user_id, ttl_minutes=20) -> dict:
    cfg = configuration_status(force_verify=True)
    username = str(cfg.get("bot_username") or "").strip().lstrip("@")
    if not cfg.get("configured") or not username:
        return {"configured": False, "url": None, "config_error": cfg.get("config_error") or "telegram_not_configured"}
    init_schema()
    raw = secrets.token_urlsafe(24)
    token = "meds_" + raw
    token_hash = _hash(token)
    expires = (datetime.now(timezone.utc) + timedelta(minutes=max(5, min(60, int(ttl_minutes))))).replace(microsecond=0).isoformat()
    now = _now(); conn = db._conn(); c = conn.cursor()
    try:
        vals = (int(user_id), token_hash, expires, now)
        if db.USE_POSTGRES:
            c.execute(
                "INSERT INTO med_telegram_links(user_id,connect_token_hash,connect_expires_at,updated_at) VALUES(%s,%s,%s,%s) "
                "ON CONFLICT(user_id) DO UPDATE SET connect_token_hash=EXCLUDED.connect_token_hash,connect_expires_at=EXCLUDED.connect_expires_at,updated_at=EXCLUDED.updated_at",
                vals,
            )
        else:
            c.execute(
                "INSERT INTO med_telegram_links(user_id,connect_token_hash,connect_expires_at,updated_at) VALUES(?,?,?,?) "
                "ON CONFLICT(user_id) DO UPDATE SET connect_token_hash=excluded.connect_token_hash,connect_expires_at=excluded.connect_expires_at,updated_at=excluded.updated_at",
                vals,
            )
        conn.commit()
    finally:
        conn.close()
    return {"configured": True, "url": f"https://t.me/{username}?start={token}", "expires_at": expires}


def handle_start(chat_id, telegram_username, start_arg) -> dict:
    """Link a Telegram chat to the SymptoSense account represented by start_arg."""
    init_schema()
    token = str(start_arg or "").strip()
    if not token.startswith("meds_") or len(token) > 180:
        return {"ok": False, "reason": "invalid_token"}
    now = datetime.now(timezone.utc); th = _hash(token)
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute(f"SELECT user_id,connect_expires_at,pending_username FROM med_telegram_links WHERE connect_token_hash={PH}", (th,))
        row = c.fetchone()
        if not row:
            return {"ok": False, "reason": "invalid_token"}
        uid, exp_raw, pending_username = int(row[0]), row[1], str(row[2] or "").strip()
        try:
            exp = datetime.fromisoformat(str(exp_raw).replace("Z", "+00:00"))
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
        except Exception:
            return {"ok": False, "reason": "expired_token"}
        if exp < now:
            return {"ok": False, "reason": "expired_token"}
        actual_username = str(telegram_username or "").strip().lstrip("@")
        if pending_username and actual_username.lower() != pending_username.lower():
            return {"ok": False, "reason": "username_mismatch", "expected_username": pending_username}
        chat = str(chat_id or "").strip()
        if not chat:
            return {"ok": False, "reason": "missing_chat"}
        # One Telegram chat maps to one SymptoSense account at a time.
        c.execute(f"UPDATE med_telegram_links SET chat_id=NULL,enabled=0,updated_at={PH} WHERE chat_id={PH} AND user_id<>{PH}", (_now(), chat, uid))
        c.execute(
            f"UPDATE med_telegram_links SET chat_id={PH},telegram_username={PH},pending_username={PH},enabled=1,connect_token_hash=NULL,connect_expires_at=NULL,linked_at={PH},updated_at={PH} WHERE user_id={PH}",
            (chat, actual_username[:120], actual_username[:120], _now(), _now(), uid),
        )
        conn.commit()
        return {"ok": True, "user_id": uid}
    finally:
        conn.close()


def disconnect(user_id) -> bool:
    init_schema(); conn = db._conn(); c = conn.cursor()
    try:
        c.execute(f"UPDATE med_telegram_links SET chat_id=NULL,telegram_username=NULL,pending_username=NULL,enabled=0,connect_token_hash=NULL,connect_expires_at=NULL,updated_at={PH} WHERE user_id={PH}", (_now(), int(user_id)))
        changed = c.rowcount > 0
        conn.commit(); return changed
    finally:
        conn.close()


def _send_message(chat_id: str, text: str, taken_url: str | None = None, snooze_url: str | None = None) -> tuple[bool, str]:
    """Send a Telegram message, keeping the reminder text deliverable even if buttons fail.

    A plain connectivity test has no inline keyboard, while scheduled reminders do.
    Telegram rejects the *entire* sendMessage request when an inline button URL is
    malformed or temporarily unacceptable. In that case retry once without the
    buttons so the medication reminder itself is not lost.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return False, "telegram_not_configured"
    payload = {"chat_id": str(chat_id), "text": text, "disable_web_page_preview": True}
    has_buttons = bool(taken_url or snooze_url)
    if has_buttons:
        row = []
        if taken_url:
            row.append({"text": "✓ تم تناوله / Taken", "url": taken_url})
        if snooze_url:
            row.append({"text": "⏰ تأجيل 10 دقائق / Snooze", "url": snooze_url})
        payload["reply_markup"] = {"inline_keyboard": [row]}
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload, timeout=12)
        if r.ok and (r.json() or {}).get("ok"):
            return True, "telegram"

        # The scheduled reminder differs from the successful connection test by
        # its inline buttons. If Telegram rejects those buttons, preserve the
        # actual reminder by retrying the same text without reply_markup.
        if has_buttons:
            plain_payload = {
                "chat_id": str(chat_id),
                "text": text,
                "disable_web_page_preview": True,
            }
            retry = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json=plain_payload,
                timeout=12,
            )
            if retry.ok and (retry.json() or {}).get("ok"):
                return True, "telegram_plain_fallback"
            return False, f"telegram_http_{retry.status_code}"

        return False, f"telegram_http_{r.status_code}"
    except Exception:
        return False, "telegram_request_failed"


def _delivery_status(user_id, plan_id, log_date, log_time):
    init_schema(); conn = db._conn(); c = conn.cursor()
    try:
        c.execute(f"SELECT status FROM med_telegram_deliveries WHERE user_id={PH} AND plan_id={PH} AND log_date={PH} AND log_time={PH}", (int(user_id), int(plan_id), str(log_date), str(log_time)))
        r = c.fetchone(); return r[0] if r else None
    finally:
        conn.close()


def _record_delivery(user_id, plan_id, log_date, log_time, status, error_code=None):
    init_schema(); now = _now(); sent_at = now if status == "sent" else None
    conn = db._conn(); c = conn.cursor()
    try:
        vals = (int(user_id), int(plan_id), str(log_date), str(log_time), status, now, sent_at, error_code)
        if db.USE_POSTGRES:
            c.execute(
                "INSERT INTO med_telegram_deliveries(user_id,plan_id,log_date,log_time,status,attempted_at,sent_at,error_code) VALUES(%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT(user_id,plan_id,log_date,log_time) DO UPDATE SET status=EXCLUDED.status,attempted_at=EXCLUDED.attempted_at,sent_at=EXCLUDED.sent_at,error_code=EXCLUDED.error_code",
                vals,
            )
        else:
            c.execute(
                "INSERT INTO med_telegram_deliveries(user_id,plan_id,log_date,log_time,status,attempted_at,sent_at,error_code) VALUES(?,?,?,?,?,?,?,?) "
                "ON CONFLICT(user_id,plan_id,log_date,log_time) DO UPDATE SET status=excluded.status,attempted_at=excluded.attempted_at,sent_at=excluded.sent_at,error_code=excluded.error_code",
                vals,
            )
        conn.commit()
    finally:
        conn.close()


def send_due(user_id, plan_id, log_date, log_time, med_name, dose, taken_url, snooze_url, lang="ar") -> dict:
    """Send one scheduled Telegram reminder to the user's linked chat.

    ``status()`` is intentionally safe for the web API and does not expose the
    private Telegram chat id. Scheduled delivery therefore must read the
    internal link row directly. The previous implementation called status()
    and then tried ``st.get("chat_id")``, which always produced ``None``: the
    connection test worked (it already used ``_row``), while scheduled
    reminders were sent to an invalid chat target.
    """
    row = _row(user_id) or {}
    chat_id = str(row.get("chat_id") or "").strip()
    if not row.get("enabled") or not chat_id:
        return {"sent": False, "skipped": True, "reason": "not_linked"}
    if _delivery_status(user_id, plan_id, log_date, log_time) == "sent":
        return {"sent": False, "skipped": True, "reason": "already_sent"}
    med_name = str(med_name or "").strip()
    dose = str(dose or "").strip()
    if lang == "en":
        text = f"⏰ Time for {med_name}" + (f" — {dose}" if dose else "") + ".\nEmail remains your primary reminder; Telegram is an optional extra alert."
    else:
        text = f"⏰ حان وقت جرعة {med_name}" + (f" — {dose}" if dose else "") + ".\nالبريد الإلكتروني يبقى التذكير الأساسي، وTelegram تنبيه إضافي اختياري."
    ok, code = _send_message(chat_id, text, taken_url, snooze_url)
    _record_delivery(user_id, plan_id, log_date, log_time, "sent" if ok else "failed", None if ok else code)
    return {"sent": bool(ok), "skipped": False, "reason": code}


def send_link_confirmation(chat_id: str):
    return _send_message(chat_id, "✅ تم ربط Telegram بتذكيرات الأدوية في SymptoSense. البريد الإلكتروني سيبقى التذكير الأساسي.")


def send_test(user_id) -> dict:
    """Send an immediate Telegram test to the account's linked chat."""
    row = _row(user_id) or {}
    chat_id = str(row.get("chat_id") or "").strip()
    if not chat_id or not row.get("enabled"):
        return {"sent": False, "reason": "not_linked"}
    ok, code = _send_message(
        chat_id,
        "✅ اختبار SymptoSense: اتصال Telegram يعمل، وستصل تذكيرات الأدوية إلى هذه المحادثة.",
    )
    return {"sent": bool(ok), "reason": code}


def send_start_help(chat_id: str):
    """Friendly response for a manual /start that has no SymptoSense link token."""
    text = (
        "👋 أهلًا بك في SymptoSense.\n\n"
        "لربط Telegram بتذكيرات الأدوية، ابدئي الربط من صفحة تذكيرات الأدوية داخل SymptoSense "
        "ثم اضغطي زر ربط Telegram. سيفتح البوت برابط ربط آمن، وبعدها اضغطي Start مرة واحدة.\n\n"
        "إذا كنتِ فتحتِ البوت يدويًا وكتبتِ /start، فلن يتم ربط الحساب بدون رابط الربط الخاص بك."
    )
    return _send_message(str(chat_id), text)


def send_link_error(chat_id: str, reason: str, expected_username: str = ""):
    if reason == "username_mismatch":
        text = "⚠️ اسم مستخدم Telegram لا يطابق الاسم المحفوظ في SymptoSense."
        if expected_username:
            text += f"\nالاسم المحفوظ: @{expected_username}"
        text += "\nارجعي للموقع وعدّلي اسم المستخدم ثم أعيدي الربط."
    elif reason == "expired_token":
        text = "⌛ انتهت صلاحية رابط ربط Telegram. ارجعي إلى SymptoSense واضغطي ربط Telegram لإنشاء رابط جديد."
    elif reason == "invalid_token":
        text = "⚠️ رابط ربط Telegram غير صالح أو تم استخدامه من قبل. ارجعي إلى SymptoSense وأنشئي رابط ربط جديد."
    elif reason == "missing_chat":
        text = "⚠️ لم نتمكن من قراءة محادثة Telegram. افتحي البوت مباشرة ثم أعيدي الربط من SymptoSense."
    else:
        text = "تعذر ربط Telegram الآن. ارجعي إلى SymptoSense وحاولي مرة أخرى."
    return _send_message(str(chat_id), text)
