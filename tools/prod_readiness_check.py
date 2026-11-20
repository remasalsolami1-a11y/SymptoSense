#!/usr/bin/env python3
"""Run in the PRODUCTION environment (e.g. Railway shell) to see what is still missing. Never prints secret values.

    python tools/prod_readiness_check.py          # exit 1 while anything blocking is missing
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _set(name: str) -> bool:
    return bool((os.environ.get(name) or "").strip())


def checks() -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []
    for name, why in (("DATABASE_URL", "PostgreSQL connection"), ("WEB_SECRET", "session signing (fixed and strong)"),
                      ("HASH_SALT", "stable hashing salt (never change after data exists)"),
                      ("SYMPTOSENSE_ADMIN_EMAIL", "enables automatic admin owner promotion/recovery"),
                      ("BACKUP_DIR", "backup folder on the persistent volume (/data/backups)"),
                      ("BACKUP_ENCRYPTION_KEY", "Fernet key from `python backup_restore.py generate-key`"),
                      ("RESTORE_TEST_DATABASE_URL", "a SEPARATE database for restore tests")):
        out.append((name, _set(name), why))
    out.append(("BACKUP_SCHEDULER_ENABLED", (os.environ.get("BACKUP_SCHEDULER_ENABLED") or "").strip().lower() in {"1", "true", "yes", "on"}, "scheduled backups on"))
    differs = _set("DATABASE_URL") and _set("RESTORE_TEST_DATABASE_URL") and os.environ.get("DATABASE_URL") != os.environ.get("RESTORE_TEST_DATABASE_URL")
    out.append(("RESTORE_TEST_DATABASE_URL differs from DATABASE_URL", bool(differs), "restore test must never target production"))
    key = (os.environ.get("BACKUP_ENCRYPTION_KEY") or "").strip()
    if key:
        try:
            from cryptography.fernet import Fernet
            Fernet(key.encode())
            ok = True
        except Exception:
            ok = False
        out.append(("BACKUP_ENCRYPTION_KEY is a valid Fernet key", ok, "invalid key makes every backup fail"))
    return out


def backup_state() -> dict:
    try:
        r = subprocess.run([sys.executable, str(ROOT / "backup_restore.py"), "status", "--json"], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
        lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
        return json.loads(lines[-1]) if lines else {}
    except Exception:
        return {}


def main() -> int:
    bad = 0
    for name, ok, why in checks():
        print(("OK       " if ok else "MISSING  ") + name + " — " + why)
        bad += not ok
    for name, why in (("SENTRY_DSN", "error alerts (Sentry); without it failures are only in Railway logs"),):
        print(("OK       " if _set(name) else "ADVISED  ") + name + " — " + why)
    st = backup_state()
    if st:
        for k in ("ready", "last_backup_status", "last_verify_status", "last_restore_test_status", "restore_test_fresh"):
            if k in st:
                print(f"STATE    {k}: {st[k]}")
        bad += not st.get("ready", False)
    else:
        print("STATE    backup status unavailable (run: python backup_restore.py status)")
        bad += 1
    print("\nProof sequence: backup -> verify -> restore-test -> status must show ready=true.")
    print("READY" if not bad else f"NOT READY ({bad} item(s))")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
