"""TOTP two-factor authentication for the single SymptoSense Admin account.

Secrets are encrypted at rest with Fernet using a key derived from WEB_SECRET.
Recovery codes are stored only as salted hashes and are consumed once used.
"""
from __future__ import annotations
import logging

import base64
import hashlib
import hmac
import io
import json
import os
import secrets
import struct
import time
from datetime import datetime, timezone
from urllib.parse import quote

import db

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # pragma: no cover - deployment readiness will report this
    logging.getLogger(__name__).debug("Handled exception in module initialization; fallback applied (handler 24)")
    Fernet = None
    InvalidToken = Exception

PH = db.PH
_SCHEMA_READY = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _web_secret() -> str:
    return os.environ.get("WEB_SECRET", "").strip()


def available() -> bool:
    return bool(_web_secret()) and Fernet is not None


def required() -> bool:
    return os.environ.get("ADMIN_2FA_REQUIRED", "1").strip().lower() not in {"0", "false", "no", "off"}


def _fernet():
    if not available():
        raise RuntimeError("admin_2fa_unavailable")
    digest = hashlib.sha256(("symptosense-admin-2fa-v1|" + _web_secret()).encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def init_schema() -> None:
    global _SCHEMA_READY
    key = db._database_identity()
    if _SCHEMA_READY == key:
        return
    db.init_db()
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute("""
            CREATE TABLE IF NOT EXISTS ss_admin_2fa (
                user_id INTEGER PRIMARY KEY,
                secret_enc TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 0,
                recovery_hashes TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                enabled_at TEXT,
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit(); _SCHEMA_READY = key
    finally:
        conn.close()


def _encrypt(secret: str) -> str:
    return _fernet().encrypt(secret.encode("ascii")).decode("ascii")


def _decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(str(token).encode("ascii")).decode("ascii")
    except InvalidToken as exc:
        raise RuntimeError("admin_2fa_secret_unreadable") from exc


def _secret() -> str:
    # 160-bit TOTP secret, compatible with Google/Microsoft Authenticator and 1Password.
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _normalize_code(value: str) -> str:
    return "".join(ch for ch in str(value or "").strip().upper() if ch.isalnum())


def _totp(secret: str, at: int | None = None, digits: int = 6, period: int = 30) -> str:
    now = int(time.time() if at is None else at)
    counter = now // period
    padded = secret + "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(padded, casefold=True)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(binary % (10 ** digits)).zfill(digits)


def verify_totp(secret: str, code: str, window: int = 1) -> bool:
    value = _normalize_code(code)
    if len(value) != 6 or not value.isdigit():
        return False
    now = int(time.time())
    for step in range(-abs(window), abs(window) + 1):
        if hmac.compare_digest(_totp(secret, now + step * 30), value):
            return True
    return False


def _recovery_pepper() -> bytes:
    return hashlib.sha256(("symptosense-admin-recovery-v1|" + _web_secret()).encode()).digest()


def _recovery_hash(code: str) -> str:
    norm = _normalize_code(code)
    return hmac.new(_recovery_pepper(), norm.encode("ascii"), hashlib.sha256).hexdigest()


def _generate_recovery_codes(n: int = 8) -> list[str]:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    out = []
    for _ in range(n):
        raw = "".join(secrets.choice(alphabet) for _ in range(10))
        out.append(raw[:5] + "-" + raw[5:])
    return out


def status(user_id: int) -> dict:
    init_schema()
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute(f"SELECT enabled,recovery_hashes,created_at,enabled_at,updated_at FROM ss_admin_2fa WHERE user_id={PH}", (int(user_id),))
        row = c.fetchone()
    finally:
        conn.close()
    hashes = []
    if row:
        try: hashes = json.loads(row[1] or "[]")
        except Exception: logging.getLogger(__name__).debug("Handled exception in status; fallback applied (handler 151)"); hashes = []
    return {
        "available": available(),
        "required": required(),
        "configured": bool(row),
        "enabled": bool(row and row[0]),
        "recovery_codes_remaining": len(hashes),
        "created_at": row[2] if row else None,
        "enabled_at": row[3] if row else None,
        "updated_at": row[4] if row else None,
    }


def begin_setup(user_id: int) -> str:
    if not available():
        raise RuntimeError("admin_2fa_unavailable")
    init_schema(); uid = int(user_id); now = _now()
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute(f"SELECT secret_enc,enabled FROM ss_admin_2fa WHERE user_id={PH}", (uid,))
        row = c.fetchone()
        if row and bool(row[1]):
            return _decrypt(row[0])
        if row:
            try:
                return _decrypt(row[0])
            except Exception:
                logging.getLogger(__name__).warning("Handled exception in begin_setup; fallback applied (handler 177)")
                pass
        secret = _secret(); token = _encrypt(secret)
        if row:
            c.execute(f"UPDATE ss_admin_2fa SET secret_enc={PH},enabled=0,recovery_hashes='[]',updated_at={PH} WHERE user_id={PH}", (token, now, uid))
        else:
            c.execute(f"INSERT INTO ss_admin_2fa(user_id,secret_enc,enabled,recovery_hashes,created_at,enabled_at,updated_at) VALUES({','.join([PH]*7)})",
                      (uid, token, 0, "[]", now, None, now))
        conn.commit(); return secret
    finally:
        conn.close()


def current_secret(user_id: int) -> str | None:
    init_schema(); conn = db._conn(); c = conn.cursor()
    try:
        c.execute(f"SELECT secret_enc FROM ss_admin_2fa WHERE user_id={PH}", (int(user_id),))
        row = c.fetchone()
        return _decrypt(row[0]) if row else None
    finally:
        conn.close()


def confirm_setup(user_id: int, code: str) -> list[str]:
    uid = int(user_id); secret = current_secret(uid)
    if not secret or not verify_totp(secret, code):
        raise ValueError("invalid_2fa_code")
    codes = _generate_recovery_codes(8)
    hashes = json.dumps([_recovery_hash(x) for x in codes])
    now = _now(); conn = db._conn(); c = conn.cursor()
    try:
        c.execute(f"UPDATE ss_admin_2fa SET enabled=1,recovery_hashes={PH},enabled_at={PH},updated_at={PH} WHERE user_id={PH}",
                  (hashes, now, now, uid))
        conn.commit()
    finally:
        conn.close()
    return codes


def verify(user_id: int, code: str) -> tuple[bool, str | None]:
    """Return (valid, method). method is 'totp' or 'recovery'."""
    init_schema(); uid = int(user_id)
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute(f"SELECT secret_enc,enabled,recovery_hashes FROM ss_admin_2fa WHERE user_id={PH}", (uid,))
        row = c.fetchone()
        if not row or not bool(row[1]):
            return False, None
        secret = _decrypt(row[0])
        if verify_totp(secret, code):
            return True, "totp"
        norm = _normalize_code(code)
        if not norm:
            return False, None
        target = _recovery_hash(norm)
        try: hashes = list(json.loads(row[2] or "[]"))
        except Exception: logging.getLogger(__name__).debug("Handled exception in verify; fallback applied (handler 233)"); hashes = []
        for i, saved in enumerate(hashes):
            if hmac.compare_digest(str(saved), target):
                hashes.pop(i)
                c.execute(f"UPDATE ss_admin_2fa SET recovery_hashes={PH},updated_at={PH} WHERE user_id={PH}", (json.dumps(hashes), _now(), uid))
                conn.commit(); return True, "recovery"
        return False, None
    finally:
        conn.close()


def disable(user_id: int, current_code: str) -> bool:
    ok, _ = verify(user_id, current_code)
    if not ok:
        return False
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute(f"DELETE FROM ss_admin_2fa WHERE user_id={PH}", (int(user_id),))
        changed = c.rowcount > 0; conn.commit(); return changed
    finally:
        conn.close()


def provisioning_uri(secret: str, account_email: str, issuer: str = "SymptoSense") -> str:
    label = quote(f"{issuer}:{account_email}")
    return f"otpauth://totp/{label}?secret={quote(secret)}&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30"


def qr_data_uri(uri: str) -> str:
    try:
        import qrcode
        img = qrcode.make(uri)
        buf = io.BytesIO(); img.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        logging.getLogger(__name__).warning("Handled exception in qr_data_uri; fallback applied (handler 267)")
        return ""
