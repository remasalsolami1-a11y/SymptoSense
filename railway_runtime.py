"""Railway-specific runtime guards that do not depend on Flask.

The deploy healthcheck must be able to prove that the Python web process is
listening even if Flask request hooks, host validation, or database readiness
are still warming up.  This middleware answers Railway's documented
healthcheck host directly for the two liveness paths and lets every other
request continue to Flask unchanged.
"""
from __future__ import annotations

import json
import os
import secrets
from urllib.parse import quote


def normalize_environment(environ=None) -> None:
    """Accept safe legacy names without weakening production fail-fast checks."""
    env = os.environ if environ is None else environ
    if not str(env.get("WEB_SECRET") or "").strip():
        for name in ("SECRET_KEY", "FLASK_SECRET_KEY"):
            value = str(env.get(name) or "").strip()
            if len(value) >= 32:
                env["WEB_SECRET"] = value
                break
    if not str(env.get("DATABASE_URL") or "").strip():
        for name in ("POSTGRES_URL", "POSTGRESQL_URL"):
            value = str(env.get(name) or "").strip()
            if value.startswith(("postgres://", "postgresql://")):
                env["DATABASE_URL"] = value
                break
    if not str(env.get("DATABASE_URL") or "").strip():
        keys = ("PGUSER", "PGPASSWORD", "PGHOST", "PGPORT", "PGDATABASE")
        if all(str(env.get(k) or "").strip() for k in keys):
            user = quote(str(env["PGUSER"]), safe="")
            password = quote(str(env["PGPASSWORD"]), safe="")
            host = str(env["PGHOST"]).strip()
            port = str(env["PGPORT"]).strip()
            database = quote(str(env["PGDATABASE"]), safe="")
            env["DATABASE_URL"] = f"postgresql://{user}:{password}@{host}:{port}/{database}"

    railway_runtime = any(str(env.get(name) or "").strip() for name in (
        "RAILWAY_ENVIRONMENT", "RAILWAY_ENVIRONMENT_NAME", "RAILWAY_PROJECT_ID",
        "RAILWAY_PUBLIC_DOMAIN", "RAILWAY_PRIVATE_DOMAIN",
    ))
    mount = str(env.get("RAILWAY_VOLUME_MOUNT_PATH") or "").strip()

    # A missing Railway reference variable should not prevent the process from
    # binding its port. Prefer PostgreSQL whenever DATABASE_URL/PG* is present;
    # only fall back to SQLite when no database credentials reached the web
    # service. If a Railway Volume is attached, keep that fallback persistent.
    if railway_runtime and not str(env.get("DATABASE_URL") or "").strip():
        if mount and os.path.isabs(mount):
            env.setdefault("DB_PATH", os.path.join(mount, "symptosense.db"))
            env["SYMPTOSENSE_DATABASE_MODE"] = "sqlite-volume-fallback"
        else:
            env.setdefault("DB_PATH", "/tmp/symptosense.db")
            env["SYMPTOSENSE_DATABASE_MODE"] = "sqlite-ephemeral-fallback"

    # Keep Flask sessions stable even when WEB_SECRET was accidentally omitted.
    # With a Railway Volume we generate the secret once and reuse it on future
    # deploys; without a Volume we still boot, but mark the source as ephemeral.
    if railway_runtime and len(str(env.get("WEB_SECRET") or "").strip()) < 32:
        secret_value = ""
        if mount and os.path.isabs(mount):
            secret_path = os.path.join(mount, ".symptosense_web_secret")
            try:
                os.makedirs(mount, exist_ok=True)
                if os.path.isfile(secret_path):
                    with open(secret_path, "r", encoding="utf-8") as handle:
                        secret_value = handle.read().strip()
                if len(secret_value) < 32:
                    secret_value = secrets.token_hex(32)
                    tmp_path = secret_path + ".tmp"
                    with open(tmp_path, "w", encoding="utf-8") as handle:
                        handle.write(secret_value)
                    os.chmod(tmp_path, 0o600)
                    os.replace(tmp_path, secret_path)
                env["SYMPTOSENSE_WEB_SECRET_SOURCE"] = "railway-volume"
            except OSError:
                secret_value = ""
        if len(secret_value) < 32:
            secret_value = secrets.token_hex(32)
            env["SYMPTOSENSE_WEB_SECRET_SOURCE"] = "ephemeral-runtime"
        env["WEB_SECRET"] = secret_value


class RailwayHealthcheckMiddleware:
    """Fast-path Railway liveness before Flask routing/host validation."""

    _PATHS = {"/health", "/healthz"}
    _HOST = "healthcheck.railway.app"

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        method = str(environ.get("REQUEST_METHOD") or "GET").upper()
        path = str(environ.get("PATH_INFO") or "")
        # Liveness is intentionally host-independent. Railway may change the
        # internal Host header, and the public Flask /health route already
        # exposes the same non-sensitive liveness information. Keeping this
        # fast path scoped only by path + method avoids false deploy failures.
        if path in self._PATHS and method in {"GET", "HEAD"}:
            payload = json.dumps({"ok": True, "service": "SymptoSense", "status": "alive"}, separators=(",", ":")).encode("utf-8")
            body = b"" if method == "HEAD" else payload
            start_response("200 OK", [
                ("Content-Type", "application/json; charset=utf-8"),
                # RFC-compliant HEAD reports the GET representation length.
                ("Content-Length", str(len(payload))),
                ("Cache-Control", "no-store"),
                ("X-SymptoSense-Liveness", "1"),
            ])
            return [body]
        return self.app(environ, start_response)


def log_runtime_context(logger) -> None:
    """Log only non-secret startup facts that help diagnose Railway failures."""
    try:
        mount = str(os.environ.get("RAILWAY_VOLUME_MOUNT_PATH") or "").strip() or "none"
        logger.info(
            "RAILWAY runtime port=%s volume_mount=%s database_configured=%s web_secret_configured=%s",
            os.environ.get("PORT", "5000"),
            mount,
            bool(str(os.environ.get("DATABASE_URL") or "").strip()),
            len(str(os.environ.get("WEB_SECRET") or "").strip()) >= 32,
        )
        normalized_mount = mount.rstrip("/")
        if normalized_mount == "/opt/symptosense/app":
            logger.warning("RAILWAY volume mount overlaps application directory; move it to /data")
        elif normalized_mount in {"/app", "/srv/symptosense"}:
            logger.warning("RAILWAY legacy application-path volume detected; /data is recommended for persistence")
    except Exception:
        pass
