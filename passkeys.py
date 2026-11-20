"""Optional WebAuthn passkeys for SymptoSense accounts.

Cryptographic verification is delegated to the maintained ``webauthn`` package.
If the dependency, origin, or RP-ID configuration is unsafe/unavailable, the
feature fails closed.
"""
from __future__ import annotations

import base64
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import db

_HOST_RE = re.compile(r"^[a-z0-9.-]+$", re.I)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64u(text: str) -> bytes:
    raw = str(text or "")
    return base64.urlsafe_b64decode(raw + "=" * ((4 - len(raw) % 4) % 4))


def available() -> bool:
    try:
        import webauthn  # noqa: F401
        return True
    except Exception:
        return False


def config() -> dict:
    site = (os.environ.get("SITE_URL") or os.environ.get("PUBLIC_BASE_URL") or "").strip()
    site_parsed = urlparse(site) if site else None

    default_rp = (site_parsed.hostname if site_parsed else "") or "localhost"
    rp_id = (os.environ.get("WEBAUTHN_RP_ID") or default_rp).strip().lower().rstrip(".")

    default_origin = (
        f"{site_parsed.scheme}://{site_parsed.netloc}"
        if site_parsed and site_parsed.scheme and site_parsed.netloc
        else "http://localhost:5000"
    )
    origin = (os.environ.get("WEBAUTHN_ORIGIN") or default_origin).strip().rstrip("/")

    valid = True
    reason = None
    try:
        parsed = urlparse(origin)
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            valid = False; reason = "invalid_origin"
        elif parsed.scheme not in {"http", "https"} or not host:
            valid = False; reason = "invalid_origin"
        elif parsed.scheme == "http" and host not in {"localhost", "127.0.0.1", "::1"}:
            valid = False; reason = "https_required"
        elif not rp_id or not _HOST_RE.fullmatch(rp_id) or ".." in rp_id:
            valid = False; reason = "invalid_rp_id"
        elif host not in {"localhost", "127.0.0.1", "::1"} and not (host == rp_id or host.endswith("." + rp_id)):
            valid = False; reason = "rp_id_origin_mismatch"
    except Exception:
        valid = False; reason = "invalid_configuration"
        host = ""

    secure = bool(valid and (origin.startswith("https://") or host in {"localhost", "127.0.0.1", "::1"}))
    return {
        "rp_id": rp_id,
        "origin": origin,
        "rp_name": "SymptoSense",
        "secure_origin": secure,
        "valid_configuration": bool(valid),
        "configuration_error": reason,
        "library": available(),
    }


def _require_config() -> dict:
    cfg = config()
    if not cfg["library"] or not cfg["secure_origin"] or not cfg["valid_configuration"]:
        raise RuntimeError("passkeys_unavailable")
    return cfg


def init_schema():
    db.init_db(); conn = db._conn()
    try:
        c = conn.cursor(); serial = "SERIAL PRIMARY KEY" if db.USE_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"
        c.execute(f"""CREATE TABLE IF NOT EXISTS passkey_credentials (
            id {serial}, user_id INTEGER NOT NULL, credential_id TEXT UNIQUE NOT NULL,
            public_key TEXT NOT NULL, sign_count INTEGER NOT NULL DEFAULT 0,
            transports TEXT NOT NULL DEFAULT '[]', label TEXT NOT NULL DEFAULT 'Passkey',
            created_at TEXT NOT NULL, last_used_at TEXT, FOREIGN KEY(user_id) REFERENCES ss_users(id) ON DELETE CASCADE
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_passkeys_user ON passkey_credentials(user_id)")
        conn.commit()
    finally:
        conn.close()


def list_for_user(user_id: int) -> list[dict]:
    init_schema(); conn = db._conn()
    try:
        c = conn.cursor(); c.execute(f"SELECT id,credential_id,label,transports,created_at,last_used_at FROM passkey_credentials WHERE user_id={db.PH} ORDER BY id DESC", (int(user_id),))
        out = []
        for r in c.fetchall():
            try:
                transports = json.loads(r[3] or "[]")
            except (TypeError, ValueError, OverflowError):
                transports = []
            out.append({"id": r[0], "credential_id": r[1][:16] + "…", "label": r[2], "transports": transports, "created_at": r[4], "last_used_at": r[5]})
        return out
    finally:
        conn.close()


def delete(user_id: int, passkey_id: int) -> bool:
    init_schema(); conn = db._conn()
    try:
        c = conn.cursor(); c.execute(f"DELETE FROM passkey_credentials WHERE id={db.PH} AND user_id={db.PH}", (int(passkey_id), int(user_id)))
        ok = c.rowcount > 0; conn.commit(); return ok
    finally:
        conn.close()


def registration_options(user: dict) -> tuple[str, bytes]:
    cfg = _require_config()
    from webauthn import generate_registration_options, options_to_json
    from webauthn.helpers.structs import (
        PublicKeyCredentialDescriptor,
        AuthenticatorSelectionCriteria,
        ResidentKeyRequirement,
        UserVerificationRequirement,
    )

    init_schema(); conn = db._conn()
    try:
        c = conn.cursor(); c.execute(f"SELECT credential_id FROM passkey_credentials WHERE user_id={db.PH}", (int(user["id"]),))
        existing = [PublicKeyCredentialDescriptor(id=_unb64u(r[0])) for r in c.fetchall()]
    finally:
        conn.close()

    # The login ceremony intentionally omits allowCredentials so it can be
    # username-less. That requires a discoverable credential; WebAuthn's
    # residentKey=required expresses this requirement explicitly.
    options = generate_registration_options(
        rp_id=cfg["rp_id"],
        rp_name=cfg["rp_name"],
        user_id=str(user["id"]).encode("utf-8"),
        user_name=str(user.get("email") or user["id"]),
        user_display_name=str(user.get("name") or user.get("email") or "SymptoSense user"),
        exclude_credentials=existing,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
    )
    return options_to_json(options), options.challenge


def verify_registration(user_id: int, credential: dict, challenge: bytes, label: str = "Passkey") -> dict:
    cfg = _require_config()
    if not isinstance(challenge, (bytes, bytearray)) or not challenge:
        raise ValueError("missing_challenge")
    if not isinstance(credential, dict):
        raise ValueError("invalid_credential")

    from webauthn import verify_registration_response
    from webauthn.helpers import parse_registration_credential_json

    parsed_credential = parse_registration_credential_json(credential)
    verified = verify_registration_response(
        credential=parsed_credential,
        expected_challenge=bytes(challenge),
        expected_rp_id=cfg["rp_id"],
        expected_origin=cfg["origin"],
        require_user_verification=True,
    )
    cid = _b64u(verified.credential_id)
    pk = base64.b64encode(verified.credential_public_key).decode("ascii")
    transports = ((credential.get("response") or {}).get("transports") or [])
    if not isinstance(transports, list):
        transports = []
    transports = [str(x)[:40] for x in transports[:10] if isinstance(x, str)]
    clean_label = str(label or "Passkey").strip()[:80] or "Passkey"

    init_schema(); conn = db._conn()
    try:
        c = conn.cursor()
        params = (int(user_id), cid, pk, int(verified.sign_count), json.dumps(transports), clean_label, _now())
        c.execute(
            f"INSERT INTO passkey_credentials(user_id,credential_id,public_key,sign_count,transports,label,created_at) VALUES ({','.join([db.PH] * 7)})",
            params,
        )
        conn.commit()
    finally:
        conn.close()
    return {"credential_id": cid, "sign_count": int(verified.sign_count)}


def authentication_options() -> tuple[str, bytes]:
    cfg = _require_config()
    from webauthn import generate_authentication_options, options_to_json
    from webauthn.helpers.structs import UserVerificationRequirement

    options = generate_authentication_options(
        rp_id=cfg["rp_id"],
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    return options_to_json(options), options.challenge


def verify_authentication(credential: dict, challenge: bytes) -> int:
    cfg = _require_config()
    if not isinstance(challenge, (bytes, bytearray)) or not challenge:
        raise ValueError("missing_challenge")
    if not isinstance(credential, dict):
        raise ValueError("invalid_credential")
    cid = str(credential.get("id") or "")
    if not cid or len(cid) > 2048:
        raise ValueError("missing_credential")

    init_schema(); conn = db._conn()
    try:
        c = conn.cursor(); c.execute(f"SELECT id,user_id,public_key,sign_count FROM passkey_credentials WHERE credential_id={db.PH}", (cid,))
        row = c.fetchone()
        if not row:
            raise ValueError("unknown_credential")
        passkey_id, user_id, pk, sign_count = row
    finally:
        conn.close()

    from webauthn import verify_authentication_response
    from webauthn.helpers import parse_authentication_credential_json

    parsed_credential = parse_authentication_credential_json(credential)
    verified = verify_authentication_response(
        credential=parsed_credential,
        expected_challenge=bytes(challenge),
        expected_rp_id=cfg["rp_id"],
        expected_origin=cfg["origin"],
        credential_public_key=base64.b64decode(pk),
        credential_current_sign_count=int(sign_count),
        require_user_verification=True,
    )
    conn = db._conn()
    try:
        c = conn.cursor(); c.execute(
            f"UPDATE passkey_credentials SET sign_count={db.PH},last_used_at={db.PH} WHERE id={db.PH}",
            (int(verified.new_sign_count), _now(), int(passkey_id)),
        )
        conn.commit()
    finally:
        conn.close()
    return int(user_id)
