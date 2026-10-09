"""Secure database backup / restore verification utilities for SymptoSense.

Production PostgreSQL backups use pg_dump/pg_restore and are encrypted at rest
with a dedicated Fernet key. The web process never exposes backup contents.
Use this module from a Railway cron/worker or an operator shell, not from a
public HTTP endpoint.

Commands:
  python backup_restore.py generate-key
  python backup_restore.py backup
  python backup_restore.py verify
  python backup_restore.py restore-test
  python backup_restore.py status
"""
from __future__ import annotations
import logging

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import db

STATUS_FILE = "backup_status.json"
DEFAULT_MAX_AGE_HOURS = 30
DEFAULT_RESTORE_MAX_AGE_DAYS = 14


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    """Read bounded integer deployment settings without crashing maintenance jobs."""
    try:
        value = int(os.environ.get(name, str(default)) or default)
    except (TypeError, ValueError):
        value = int(default)
    return max(int(minimum), min(int(maximum), value))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None = None) -> str:
    return (dt or _utcnow()).isoformat()


def _backup_dir() -> Path:
    raw = (os.environ.get("BACKUP_DIR") or "").strip()
    if not raw:
        if os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_PROJECT_ID"):
            raise RuntimeError("BACKUP_DIR must point to a persistent Railway Volume in production")
        raw = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")
    path = Path(raw).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass
    return path


def _status_path() -> Path:
    return _backup_dir() / STATUS_FILE


def _write_json_atomic(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.flush()
        os.fsync(fh.fileno())
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)


def _read_status_raw() -> dict:
    try:
        with open(_status_path(), "r", encoding="utf-8") as fh:
            obj = json.load(fh)
            return obj if isinstance(obj, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _fernet():
    raw = (os.environ.get("BACKUP_ENCRYPTION_KEY") or "").strip()
    if not raw:
        return None
    from cryptography.fernet import Fernet
    try:
        return Fernet(raw.encode("ascii"))
    except Exception as exc:
        raise RuntimeError("BACKUP_ENCRYPTION_KEY is invalid; use a Fernet key") from exc


def _production_mode() -> bool:
    return bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_PROJECT_ID") or db.USE_POSTGRES)


def _require_backup_encryption():
    f = _fernet()
    if f:
        return f
    if _production_mode() and os.environ.get("ALLOW_UNENCRYPTED_BACKUPS", "0").strip() != "1":
        raise RuntimeError("BACKUP_ENCRYPTION_KEY is required for production backups")
    return None


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_db_identity(url: str) -> str:
    """Non-secret fingerprint used only to ensure test/prod DBs differ."""
    return hashlib.sha256((url or "").strip().encode("utf-8")).hexdigest()


def _redacted_db_label(url: str) -> str:
    try:
        p = urlsplit(url)
        host = p.hostname or "unknown"
        port = f":{p.port}" if p.port else ""
        dbname = (p.path or "/").lstrip("/") or "unknown"
        return f"{host}{port}/{dbname}"
    except Exception:
        logging.getLogger(__name__).warning("Handled exception in _redacted_db_label; fallback applied (handler 132)")
        return "configured-database"


def _tool(name: str) -> str:
    found = shutil.which(name)
    if not found:
        raise RuntimeError(f"{name} was not found. Install PostgreSQL client tools in the Railway image")
    return found


def _run(cmd: list[str], *, db_url: str | None = None, timeout: int = 900) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if db_url:
        # Keep credentials out of command-line arguments/process listings.
        env["PGDATABASE"] = db_url
    return subprocess.run(cmd, env=env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)


def _sqlite_snapshot(target: Path) -> None:
    source = sqlite3.connect(db.DB_PATH)
    dest = sqlite3.connect(str(target))
    try:
        source.backup(dest)
        row = dest.execute("PRAGMA integrity_check").fetchone()
        if not row or str(row[0]).lower() != "ok":
            raise RuntimeError("SQLite integrity_check failed during backup")
    finally:
        dest.close(); source.close()


def _plain_backup(temp_path: Path) -> str:
    if db.USE_POSTGRES:
        pg_dump = _tool("pg_dump")
        _run([
            pg_dump, "--format=custom", "--no-owner", "--no-privileges",
            "--file", str(temp_path),
        ], db_url=db.DATABASE_URL)
        return "postgres_custom"
    _sqlite_snapshot(temp_path)
    return "sqlite"


def create_backup() -> dict:
    out_dir = _backup_dir()
    fernet = _require_backup_encryption()
    stamp = _utcnow().strftime("%Y%m%dT%H%M%SZ")
    backend = "postgres" if db.USE_POSTGRES else "sqlite"
    plain_suffix = ".dump" if db.USE_POSTGRES else ".sqlite3"
    fd, temp_name = tempfile.mkstemp(prefix="ss-backup-", suffix=plain_suffix, dir=str(out_dir))
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        try:
            os.chmod(temp_path, 0o600)
        except OSError:
            pass
        backup_format = _plain_backup(temp_path)
        max_mb = _env_int("BACKUP_MAX_SIZE_MB", 512, 10, 2048)
        size = temp_path.stat().st_size
        if size > max_mb * 1024 * 1024:
            raise RuntimeError(f"backup exceeds BACKUP_MAX_SIZE_MB={max_mb}")

        if fernet:
            final = out_dir / f"symptosense-{backend}-{stamp}{plain_suffix}.fernet"
            # The current application dataset is intentionally bounded. Refuse
            # unexpectedly huge backups above the limit instead of exhausting RAM.
            encrypted = fernet.encrypt(temp_path.read_bytes())
            with open(final, "wb") as fh:
                fh.write(encrypted); fh.flush(); os.fsync(fh.fileno())
            encrypted_flag = True
        else:
            final = out_dir / f"symptosense-{backend}-{stamp}{plain_suffix}"
            os.replace(temp_path, final)
            encrypted_flag = False
        try:
            os.chmod(final, 0o600)
        except OSError:
            pass

        state = _read_status_raw()
        state.update({
            "schema_version": 1,
            "last_backup_status": "ok",
            "last_backup_at": _iso(),
            "last_backup_file": final.name,
            "last_backup_sha256": _sha256_file(final),
            "last_backup_bytes": int(final.stat().st_size),
            "backend": backend,
            "backup_format": backup_format,
            "encrypted": encrypted_flag,
            "database_label": _redacted_db_label(db.DATABASE_URL) if db.USE_POSTGRES else "local-sqlite",
            "last_error": None,
        })
        _write_json_atomic(_status_path(), state)
        _prune_old_backups(out_dir, keep=_env_int("BACKUP_KEEP_COUNT", 7, 2, 30))
        return public_status()
    except Exception as exc:
        state = _read_status_raw()
        state.update({"schema_version": 1, "last_backup_status": "failed", "last_backup_attempt_at": _iso(), "last_error": type(exc).__name__})
        _write_json_atomic(_status_path(), state)
        raise
    finally:
        try:
            if temp_path.exists(): temp_path.unlink()
        except OSError:
            pass


def _prune_old_backups(out_dir: Path, keep: int) -> None:
    files = sorted(
        [p for p in out_dir.iterdir() if p.is_file() and p.name.startswith("symptosense-") and p.name != STATUS_FILE],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in files[keep:]:
        try: path.unlink()
        except OSError: pass


def _materialize_latest_plain() -> tuple[Path, dict, bool]:
    state = _read_status_raw()
    name = str(state.get("last_backup_file") or "")
    if not name or Path(name).name != name:
        raise RuntimeError("No valid backup metadata is available")
    src = _backup_dir() / name
    if not src.is_file():
        raise RuntimeError("Latest backup file is missing")
    expected = str(state.get("last_backup_sha256") or "")
    if not expected or not hashlib.sha256(src.read_bytes()).hexdigest() == expected:
        raise RuntimeError("Backup checksum mismatch")
    encrypted = bool(state.get("encrypted"))
    if not encrypted:
        return src, state, False
    fernet = _fernet()
    if not fernet:
        raise RuntimeError("BACKUP_ENCRYPTION_KEY is required to verify/restore this backup")
    suffix = ".dump" if state.get("backend") == "postgres" else ".sqlite3"
    fd, name_tmp = tempfile.mkstemp(prefix="ss-restore-", suffix=suffix)
    os.close(fd)
    path = Path(name_tmp)
    try:
        path.write_bytes(fernet.decrypt(src.read_bytes()))
        os.chmod(path, 0o600)
    except Exception:
        try: path.unlink()
        except OSError: pass
        raise
    return path, state, True


def verify_latest_backup() -> dict:
    plain, state, temporary = _materialize_latest_plain()
    try:
        if state.get("backend") == "postgres":
            pg_restore = _tool("pg_restore")
            _run([pg_restore, "--list", str(plain)], timeout=120)
        else:
            conn = sqlite3.connect(str(plain))
            try:
                row = conn.execute("PRAGMA integrity_check").fetchone()
                if not row or str(row[0]).lower() != "ok":
                    raise RuntimeError("SQLite backup integrity check failed")
            finally:
                conn.close()
        state["last_verify_status"] = "ok"
        state["last_verify_at"] = _iso()
        state["last_error"] = None
        _write_json_atomic(_status_path(), state)
        return public_status()
    except Exception as exc:
        state["last_verify_status"] = "failed"
        state["last_verify_attempt_at"] = _iso()
        state["last_error"] = type(exc).__name__
        _write_json_atomic(_status_path(), state)
        raise
    finally:
        if temporary:
            try: plain.unlink()
            except OSError: pass


def restore_test() -> dict:
    plain, state, temporary = _materialize_latest_plain()
    try:
        if state.get("backend") == "postgres":
            target = (os.environ.get("RESTORE_TEST_DATABASE_URL") or "").strip()
            if not target:
                raise RuntimeError("RESTORE_TEST_DATABASE_URL is required for a PostgreSQL restore test")
            if _safe_db_identity(target) == _safe_db_identity(db.DATABASE_URL):
                raise RuntimeError("RESTORE_TEST_DATABASE_URL must never point to the production database")
            pg_restore = _tool("pg_restore")
            _run([
                pg_restore, "--dbname=", "--clean", "--if-exists", "--no-owner", "--no-privileges",
                str(plain),
            ], db_url=target)
            import psycopg2
            conn = psycopg2.connect(target, connect_timeout=10)
            try:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'")
                count = int((cur.fetchone() or [0])[0] or 0)
                if count < 1:
                    raise RuntimeError("Restore test produced no public tables")
                for table in ("ss_users", "records"):
                    cur.execute("SELECT to_regclass(%s)", (f"public.{table}",))
                    if not (cur.fetchone() or [None])[0]:
                        raise RuntimeError(f"Restore test missing critical table: {table}")
            finally:
                conn.close()
        else:
            fd, restored_name = tempfile.mkstemp(prefix="ss-sqlite-restore-", suffix=".sqlite3")
            os.close(fd)
            restored = Path(restored_name)
            try:
                shutil.copy2(plain, restored)
                conn = sqlite3.connect(str(restored))
                try:
                    row = conn.execute("PRAGMA integrity_check").fetchone()
                    if not row or str(row[0]).lower() != "ok":
                        raise RuntimeError("Restored SQLite integrity check failed")
                    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
                    if "ss_users" not in tables or "records" not in tables:
                        raise RuntimeError("Restored SQLite is missing critical tables")
                finally:
                    conn.close()
            finally:
                try: restored.unlink()
                except OSError: pass
        state["last_restore_test_status"] = "ok"
        state["last_restore_test_at"] = _iso()
        state["last_error"] = None
        _write_json_atomic(_status_path(), state)
        return public_status()
    except Exception as exc:
        state["last_restore_test_status"] = "failed"
        state["last_restore_test_attempt_at"] = _iso()
        state["last_error"] = type(exc).__name__
        _write_json_atomic(_status_path(), state)
        raise
    finally:
        if temporary:
            try: plain.unlink()
            except OSError: pass


def _age_hours(raw: str | None) -> float | None:
    if not raw: return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (_utcnow() - dt.astimezone(timezone.utc)).total_seconds() / 3600.0)
    except Exception:
        logging.getLogger(__name__).debug("Handled exception in _age_hours; fallback applied (handler 384)")
        return None


def public_status() -> dict:
    """Return backup readiness metadata only; never return paths, secrets or DSNs."""
    state = _read_status_raw()
    backup_age = _age_hours(state.get("last_backup_at"))
    restore_age = _age_hours(state.get("last_restore_test_at"))
    max_age = _env_int("BACKUP_MAX_AGE_HOURS", DEFAULT_MAX_AGE_HOURS, 1, 24 * 365)
    restore_max_days = _env_int("RESTORE_TEST_MAX_AGE_DAYS", DEFAULT_RESTORE_MAX_AGE_DAYS, 1, 3650)
    backup_ok = state.get("last_backup_status") == "ok" and backup_age is not None and backup_age <= max_age
    restore_ok = state.get("last_restore_test_status") == "ok" and restore_age is not None and restore_age <= restore_max_days * 24
    return {
        "configured": bool((os.environ.get("BACKUP_DIR") or "").strip()) if _production_mode() else True,
        "encrypted": bool(state.get("encrypted")),
        "last_backup_status": state.get("last_backup_status") or "never",
        "last_backup_at": state.get("last_backup_at"),
        "last_backup_age_hours": round(backup_age, 1) if backup_age is not None else None,
        "last_backup_bytes": int(state.get("last_backup_bytes") or 0),
        "last_verify_status": state.get("last_verify_status") or "never",
        "last_verify_at": state.get("last_verify_at"),
        "last_restore_test_status": state.get("last_restore_test_status") or "never",
        "last_restore_test_at": state.get("last_restore_test_at"),
        "last_restore_test_age_days": round(restore_age / 24, 1) if restore_age is not None else None,
        "backup_fresh": backup_ok,
        "restore_test_fresh": restore_ok,
        "ready": bool(backup_ok and restore_ok and (state.get("encrypted") or not _production_mode())),
        "backend": state.get("backend") or ("postgres" if db.USE_POSTGRES else "sqlite"),
        "last_error": state.get("last_error"),
    }


_SCHEDULER_STARTED = False

def start_scheduler_once() -> bool:
    """Start an opt-in encrypted backup scheduler inside the web service.

    Enabled when BACKUP_SCHEDULER_ENABLED=1. The scheduler only runs when a
    persistent BACKUP_DIR and encryption key are configured in production. It
    creates/verifies a fresh backup and, when RESTORE_TEST_DATABASE_URL is set,
    periodically performs an isolated restore test.
    """
    global _SCHEDULER_STARTED
    if _SCHEDULER_STARTED:
        return False
    enabled = (os.environ.get("BACKUP_SCHEDULER_ENABLED") or "0").strip().lower() in {"1","true","yes","on"}
    if not enabled:
        return False
    # Validate secure configuration before spawning a background thread.
    _backup_dir(); _require_backup_encryption()
    _SCHEDULER_STARTED = True
    interval_hours = _env_int("BACKUP_INTERVAL_HOURS", 24, 1, 168)
    poll_seconds = _env_int("BACKUP_SCHEDULER_POLL_SECONDS", 900, 300, 3600)

    def _loop():
        while True:
            try:
                st = public_status()
                if not st.get("backup_fresh") or (st.get("last_backup_age_hours") or 10**9) >= interval_hours:
                    create_backup(); verify_latest_backup(); st = public_status()
                if (os.environ.get("RESTORE_TEST_DATABASE_URL") or "").strip() and not st.get("restore_test_fresh"):
                    restore_test()
            except Exception as exc:
                # Never log a DSN, path, backup bytes, or health data.
                logging.getLogger(__name__).warning("Handled exception in _loop; fallback applied (handler 450)")
                print(f"BACKUP scheduler cycle failed: {type(exc).__name__}", file=sys.stderr)
            time.sleep(poll_seconds)

    threading.Thread(target=_loop, name="SymptoSenseBackupScheduler", daemon=True).start()
    return True

def generate_key() -> str:
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode("ascii")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="SymptoSense secure backup / restore verification")
    parser.add_argument("command", choices=("generate-key", "backup", "verify", "restore-test", "status"))
    parser.add_argument("--json", action="store_true", help="print the result as one compact JSON line (last line of stdout)")
    args = parser.parse_args(argv)
    try:
        if args.command == "generate-key":
            print(generate_key()); return 0
        if args.command == "backup": result = create_backup()
        elif args.command == "verify": result = verify_latest_backup()
        elif args.command == "restore-test": result = restore_test()
        else: result = public_status()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True) if args.json else json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        logging.getLogger(__name__).warning("Handled exception in main; fallback applied (handler 476)")
        print(json.dumps({"ok": False, "error": type(exc).__name__, "message": "backup_operation_failed"}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
