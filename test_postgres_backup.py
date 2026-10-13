"""Backup -> verify -> restore-test against a real PostgreSQL (V68 pre-release check).

Found there: backup_restore.py handed the URL to pg_dump/pg_restore through PGDATABASE, which libpq does not expand,
so every PostgreSQL backup failed. The end-to-end test needs TEST_DATABASE_URL (a disposable server) and pg_dump on PATH.
"""
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def test_pg_env_splits_url_into_libpq_variables():
    import backup_restore
    env = backup_restore._pg_env("postgresql://us%40er:p%3Aw@db.example.test:6543/my_db?sslmode=require")
    assert env == {"PGDATABASE": "my_db", "PGHOST": "db.example.test", "PGPORT": "6543", "PGUSER": "us@er", "PGPASSWORD": "p:w", "PGSSLMODE": "require"}
    assert "postgresql://" not in "".join(env.values())          # never leave a URL in PGDATABASE again
    assert backup_restore._pg_env("postgres://u@h/d") == {"PGDATABASE": "d", "PGHOST": "h", "PGUSER": "u"}


TEST_URL = os.environ.get("TEST_DATABASE_URL", "")
needs_pg = pytest.mark.skipif(not TEST_URL or not shutil.which("pg_dump") or not shutil.which("pg_restore"),
                              reason="TEST_DATABASE_URL and pg_dump/pg_restore are required")


def _with_db(url, name):
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, "/" + name, p.query, ""))


@needs_pg
def test_backup_verify_restore_roundtrip(tmp_path):
    import psycopg2
    from cryptography.fernet import Fernet
    source, target = "ssbk_src_" + uuid.uuid4().hex[:8], "ssbk_dst_" + uuid.uuid4().hex[:8]
    admin = psycopg2.connect(TEST_URL); admin.autocommit = True
    for name in (source, target):
        admin.cursor().execute('CREATE DATABASE "%s" ENCODING \'UTF8\' TEMPLATE template0' % name)
    src_url, dst_url = _with_db(TEST_URL, source), _with_db(TEST_URL, target)
    try:
        seed = psycopg2.connect(src_url); k = seed.cursor()
        k.execute("CREATE TABLE ss_users (id serial PRIMARY KEY, email text)")
        k.execute("CREATE TABLE records (id serial PRIMARY KEY)")      # restore-test insists on the critical tables
        k.execute("INSERT INTO ss_users (email) VALUES ('backup-secret@example.test'), ('second@example.test')")
        seed.commit(); seed.close()
        env = dict(os.environ, DATABASE_URL=src_url, WEB_SECRET="x" * 40, BACKUP_DIR=str(tmp_path),
                   BACKUP_ENCRYPTION_KEY=Fernet.generate_key().decode(), RESTORE_TEST_DATABASE_URL=dst_url,
                   SYMPTOSENSE_DISABLE_BACKUP_SCHEDULER="1", PYTHONDONTWRITEBYTECODE="1")
        env.pop("TEST_DATABASE_URL", None)

        def cli(cmd, **over):
            r = subprocess.run([sys.executable, str(ROOT / "backup_restore.py"), "--json", cmd], cwd=str(ROOT), env=dict(env, **over),
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300)
            lines = [x for x in (r.stdout + "\n" + r.stderr).splitlines() if x.startswith("{")]
            assert lines, r.stderr[-800:]
            return json.loads(lines[-1])

        assert cli("backup")["last_backup_status"] == "ok"
        dump = next(tmp_path.glob("*.fernet"))
        assert b"backup-secret@example.test" not in dump.read_bytes()                 # encrypted at rest
        assert cli("verify")["last_verify_status"] == "ok"
        state = cli("restore-test")
        assert state["last_restore_test_status"] == "ok" and state["ready"] is True
        check = psycopg2.connect(dst_url); k = check.cursor()
        k.execute("SELECT email FROM ss_users ORDER BY id"); assert [r[0] for r in k.fetchall()] == ["backup-secret@example.test", "second@example.test"]
        check.close()
        assert cli("verify", BACKUP_ENCRYPTION_KEY=Fernet.generate_key().decode()).get("ok") is False   # wrong key is refused
        assert cli("restore-test", RESTORE_TEST_DATABASE_URL=src_url).get("ok") is False                # never restore over the live DB
        # Different text, same database: a query-string alias and a localhost <-> 127.0.0.1 swap must both be refused.
        aliases = [src_url + ("&" if "?" in src_url else "?") + "application_name=restore_alias"]
        for a, b in (("@127.0.0.1", "@localhost"), ("@localhost", "@127.0.0.1")):
            if a in src_url:
                aliases.append(src_url.replace(a, b, 1))
        for alias in aliases:
            assert alias != src_url
            refused = cli("restore-test", RESTORE_TEST_DATABASE_URL=alias)
            assert refused.get("ok") is False, alias
        # The same database seen through a role that is NOT a superuser (cannot read pg_control_*) must still be recognised.
        seed = psycopg2.connect(src_url); seed.autocommit = True      # like managed services: ordinary roles may not read pg_control_*
        seed.cursor().execute("REVOKE EXECUTE ON FUNCTION pg_control_system() FROM PUBLIC"); seed.close()
        k = admin.cursor(); k.execute("CREATE ROLE ssbk_reader LOGIN NOSUPERUSER PASSWORD 'ssbk_pw'")
        try:
            p = urlsplit(src_url); host = p.hostname + (":%d" % p.port if p.port else "")
            reader_url = urlunsplit((p.scheme, "ssbk_reader:ssbk_pw@" + host, p.path, "", ""))
            refused = cli("restore-test", RESTORE_TEST_DATABASE_URL=reader_url)
            assert refused.get("ok") is False
            from backup_restore import _live_db_identity
            assert _live_db_identity(reader_url) == _live_db_identity(src_url)       # one method, any role
        finally:
            k.execute("DROP ROLE IF EXISTS ssbk_reader")
        live = psycopg2.connect(src_url); k = live.cursor(); k.execute("SELECT count(*) FROM ss_users"); assert k.fetchone()[0] == 2; live.close()
    finally:
        for name in (source, target):
            admin.cursor().execute('DROP DATABASE IF EXISTS "%s" WITH (FORCE)' % name)
        admin.close()


def test_identity_check_fails_closed_and_distinguishes_clusters(monkeypatch):
    import backup_restore
    monkeypatch.setattr(backup_restore.db, "DATABASE_URL", "postgresql://u@prod.example.test/app")
    ident = {"postgresql://u@prod.example.test/app": ("sysid:1", "app", 16384)}
    # same cluster + database reached through another address -> refused
    monkeypatch.setattr(backup_restore, "_live_db_identity", lambda url: ident.get(url, ("sysid:1", "app", 16384)))
    with pytest.raises(RuntimeError, match="different address"):
        backup_restore._ensure_not_production("postgresql://u@alias.example.test/app")
    # identical text -> refused before any connection
    with pytest.raises(RuntimeError, match="never point"):
        backup_restore._ensure_not_production("postgresql://u@prod.example.test/app")
    # another cluster that reuses the same database name and OID is a different database -> allowed
    monkeypatch.setattr(backup_restore, "_live_db_identity", lambda url: ident.get(url, ("sysid:2", "app", 16384)))
    backup_restore._ensure_not_production("postgresql://u@other.example.test/app")
    # same cluster, other database -> allowed
    monkeypatch.setattr(backup_restore, "_live_db_identity", lambda url: ident.get(url, ("sysid:1", "restore", 16500)))
    backup_restore._ensure_not_production("postgresql://u@prod.example.test/restore")
    # cannot be proven different (unreachable) -> refused
    def boom(url):
        raise backup_restore.db.DB_ERRORS[-1]("unreachable")
    monkeypatch.setattr(backup_restore, "_live_db_identity", boom)
    with pytest.raises(RuntimeError, match="Could not verify"):
        backup_restore._ensure_not_production("postgresql://u@alias.example.test/app")


def test_unstable_or_incomplete_identity_is_refused(monkeypatch):
    import backup_restore
    monkeypatch.setattr(backup_restore.db, "DATABASE_URL", "postgresql://u@prod.example.test/app")
    calls = iter([("t1", "app", 1), ("t9", "restore", 2), ("t2", "app", 1)])         # production identity changed between reads
    monkeypatch.setattr(backup_restore, "_live_db_identity", lambda url: next(calls))
    with pytest.raises(RuntimeError, match="changed while"):
        backup_restore._ensure_not_production("postgresql://u@other.example.test/restore")



def test_incomplete_identity_is_refused(monkeypatch):
    import backup_restore

    class _Cur:
        def execute(self, *a): pass
        def fetchone(self): return ("2026-01-01", "app", None)                         # OID missing
    class _Conn:
        autocommit = False
        def cursor(self): return _Cur()
        def close(self): pass
    import psycopg2
    monkeypatch.setattr(psycopg2, "connect", lambda *a, **k: _Conn())
    with pytest.raises(RuntimeError, match="complete database identity"):
        backup_restore._live_db_identity("postgresql://u@h/app")
