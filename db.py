import os
import io
import json
import logging
import math
import sqlite3
import hashlib
import hmac
import threading
import time
from datetime import datetime, timedelta, timezone
from collections import Counter

try:
    import psycopg2 as _psycopg2
    DB_ERRORS = (sqlite3.Error, _psycopg2.Error)
except ImportError:  # SQLite-only environments
    DB_ERRORS = (sqlite3.Error,)

# PostgreSQL (production, Railway) if DATABASE_URL is set, otherwise SQLite (local dev).
DB_PATH = os.environ.get("DB_PATH", "symptosense.db")
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
USE_POSTGRES = bool(DATABASE_URL)

# Project-owner Admin identity is deployment configuration, never source code.
# The environment variable is used for owner bootstrap/recovery, but a persisted
# role=admin remains authoritative so a temporary Railway variable mistake can
# never silently demote the existing Admin account. Legacy variable names are
# accepted only as deployment compatibility aliases.
OWNER_ADMIN_EMAIL = (
    os.environ.get("SYMPTOSENSE_ADMIN_EMAIL", "")
    or os.environ.get("ADMIN_EMAIL", "")
    or os.environ.get("OWNER_ADMIN_EMAIL", "")
).strip().lower()
if not OWNER_ADMIN_EMAIL:
    logging.getLogger("SymptoSense").warning(
        "Admin owner email is not configured; existing persisted Admin access is preserved, "
        "but automatic owner promotion/recovery is unavailable until SYMPTOSENSE_ADMIN_EMAIL is set."
    )

PH = "%s" if USE_POSTGRES else "?"

_logger = logging.getLogger("SymptoSense")

# Database/schema initialization is expensive on a remote PostgreSQL service.
# Cache readiness per actual database identity rather than as one process-wide
# boolean. This preserves the request-time speed-up while still allowing a
# different/replaced SQLite database, or a failed migration, to be initialized
# and retried safely in the same process.
_DB_READY_KEY = None
_DB_INIT_LOCK = threading.Lock()
_CHECKIN_SCHEMA_READY_KEY = None
_CHECKIN_SCHEMA_LOCK = threading.Lock()


def _database_identity():
    """Return a non-secret identity for the database currently in use.

    PostgreSQL is keyed by a one-way digest of the DSN (the DSN itself is never
    logged or stored in the cache). SQLite is keyed by its canonical path and,
    when the file exists, its device/inode so replacing a DB at the same path is
    detected without invalidating the cache on ordinary writes.
    """
    if USE_POSTGRES:
        digest = hashlib.sha256(DATABASE_URL.encode("utf-8")).hexdigest()
        return ("postgres", digest)
    path = os.path.realpath(os.path.abspath(DB_PATH))
    try:
        st = os.stat(path)
        file_identity = (getattr(st, "st_dev", None), getattr(st, "st_ino", None))
    except OSError:
        file_identity = None
    return ("sqlite", path, file_identity)


def _init_backend():
    """Validate PostgreSQL without silently splitting production data.

    When DATABASE_URL is configured, using an ephemeral local SQLite file after
    a connection failure would make accounts and health records appear to vanish
    after a Railway restart. Production therefore fails closed. A developer may
    explicitly opt into the legacy fallback only with ALLOW_SQLITE_FALLBACK=1.
    """
    global USE_POSTGRES, PH
    if not USE_POSTGRES:
        return
    try:
        # Use the same bounded retry, timeout, and keepalive policy as normal
        # application/worker connections. Railway can briefly reject a socket
        # while a PostgreSQL service is waking or being redeployed.
        conn = _conn()
        conn.close()
    except Exception as e:
        _logger.error("PostgreSQL connection failed; refusing unsafe local database fallback")
        if os.environ.get("ALLOW_SQLITE_FALLBACK", "0").strip() == "1":
            _logger.warning("ALLOW_SQLITE_FALLBACK=1 enabled; using local SQLite for development only")
            USE_POSTGRES = False
            PH = "?"
            return
        raise RuntimeError("Persistent database is unavailable") from e


def _bounded_env_int(name, default, minimum, maximum):
    try:
        value = int(os.environ.get(name, str(default)) or default)
    except (TypeError, ValueError):
        value = int(default)
    return max(int(minimum), min(int(maximum), value))


_pg_pool = None
_pg_pool_lock = threading.Lock()


def _get_pg_pool():
    """Lazily create one shared, thread-safe Postgres connection pool per
    process. Created on first use (not at import time) so each gunicorn/
    waitress worker process gets its own pool after forking, and so a
    missing/invalid DATABASE_URL only breaks the code paths that actually
    touch the database rather than import of this module."""
    global _pg_pool
    if _pg_pool is None:
        with _pg_pool_lock:
            if _pg_pool is None:
                from psycopg2.pool import ThreadedConnectionPool
                minconn = _bounded_env_int("POSTGRES_POOL_MIN", 1, 1, 10)
                maxconn = _bounded_env_int("POSTGRES_POOL_MAX", 16, minconn, 50)
                timeout = _bounded_env_int("POSTGRES_CONNECT_TIMEOUT_SECONDS", 10, 3, 30)
                # Startup schema checks must never wait indefinitely behind an
                # old deployment or long transaction. Railway marks a deploy
                # unhealthy after a bounded window, so enforce conservative
                # server-side timeouts on every PostgreSQL session. Ordinary
                # requests also benefit from failing fast instead of hanging.
                lock_timeout_ms = _bounded_env_int("POSTGRES_LOCK_TIMEOUT_MS", 5000, 1000, 30000)
                statement_timeout_ms = _bounded_env_int("POSTGRES_STATEMENT_TIMEOUT_MS", 30000, 5000, 120000)
                pg_options = (
                    f"-c lock_timeout={lock_timeout_ms} "
                    f"-c statement_timeout={statement_timeout_ms}"
                )
                _pg_pool = ThreadedConnectionPool(
                    minconn, maxconn, DATABASE_URL,
                    connect_timeout=timeout,
                    application_name="symptosense",
                    options=pg_options,
                    keepalives=1,
                    keepalives_idle=30,
                    keepalives_interval=10,
                    keepalives_count=3,
                )
    return _pg_pool


class _PooledConnectionProxy:
    """Transparent wrapper so the hundreds of existing ``conn.close()``
    call sites return the connection to the shared pool instead of tearing
    down the TCP connection each time. Every other attribute/method (cursor,
    commit, rollback, closed, ...) is forwarded to the real connection
    unchanged, so no caller needs to change."""
    __slots__ = ("_raw", "_pool", "_returned")

    def __init__(self, raw, pool):
        object.__setattr__(self, "_raw", raw)
        object.__setattr__(self, "_pool", pool)
        object.__setattr__(self, "_returned", False)

    def close(self):
        if self._returned:
            return
        object.__setattr__(self, "_returned", True)
        raw = self._raw
        try:
            if raw.closed == 0:
                # A bare rollback on an already-clean connection is a
                # harmless no-op; this guarantees a connection is never
                # handed back to another request mid-transaction.
                raw.rollback()
                self._pool.putconn(raw)
            else:
                self._pool.putconn(raw, close=True)
        except DB_ERRORS:
            try:
                self._pool.putconn(raw, close=True)
            except DB_ERRORS:
                pass

    def __getattr__(self, name):
        return getattr(self._raw, name)

    def __setattr__(self, name, value):
        setattr(self._raw, name, value)

    def __enter__(self):
        self._raw.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            return self._raw.__exit__(exc_type, exc_val, exc_tb)
        finally:
            # psycopg2 connection.__exit__ commits/rolls back but does not close.
            # Return the connection to our pool even when callers use ``with``.
            self.close()


def _conn():
    if USE_POSTGRES:
        import psycopg2
        from psycopg2.pool import PoolError
        pool = _get_pg_pool()
        attempts = _bounded_env_int("POSTGRES_CONNECT_ATTEMPTS", 3, 1, 4)
        last_error=None
        for attempt in range(attempts):
            try:
                raw = pool.getconn()
                return _PooledConnectionProxy(raw, pool)
            except (psycopg2.OperationalError, PoolError) as exc:
                # OperationalError is a real connect failure (network, auth,
                # server down). PoolError is different -- it just means every
                # connection in the pool is currently checked out by another
                # concurrent request, which is expected under real traffic
                # and resolves itself as soon as one of those requests
                # finishes and returns its connection. Both are worth a
                # short, bounded retry rather than failing the request
                # outright.
                last_error=exc
                if attempt + 1 < attempts:
                    time.sleep(0.25 * (attempt + 1))
        raise last_error
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    """Initialize/migrate the active database once per database identity.

    A failed initialization never marks the database ready, so the next call
    retries automatically. The lock avoids two request threads racing through
    migrations in the same process.
    """
    global _DB_READY_KEY
    current_key = _database_identity()
    if _DB_READY_KEY == current_key:
        return
    with _DB_INIT_LOCK:
        current_key = _database_identity()
        if _DB_READY_KEY == current_key:
            return
        _init_db_uncached()
        migrate_legacy_followups()
        # Recompute after initialization: a new SQLite file now has an inode,
        # and explicit development fallback may have changed the backend.
        _DB_READY_KEY = _database_identity()


def _init_db_uncached():
    _init_backend()
    conn = _conn()
    try:
        c = conn.cursor()
        if USE_POSTGRES:
            c.execute("""
                CREATE TABLE IF NOT EXISTS records (
                    id SERIAL PRIMARY KEY,
                    user_hash TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    lang TEXT,
                    age INTEGER,
                    gender TEXT,
                    symptoms TEXT,
                    conditions TEXT,
                    medications TEXT,
                    duration TEXT,
                    severity INTEGER,
                    urgency TEXT
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_user_hash ON records(user_hash)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON records(timestamp)")
            c.execute("""
                CREATE TABLE IF NOT EXISTS visits (
                    id SERIAL PRIMARY KEY,
                    user_hash TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_visit_user ON visits(user_hash)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_visit_timestamp ON visits(timestamp)")
            c.execute("""
                CREATE TABLE IF NOT EXISTS subscribers (
                    user_id BIGINT PRIMARY KEY,
                    lang TEXT DEFAULT 'ar',
                    subscribed INTEGER DEFAULT 1,
                    added_at TEXT
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS followups (
                    id SERIAL PRIMARY KEY,
                    user_hash TEXT NOT NULL,
                    record_id INTEGER,
                    timestamp TEXT NOT NULL,
                    outcome TEXT
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_fu_record ON followups(record_id)")
            c.execute("""
                CREATE TABLE IF NOT EXISTS symptom_relief_logs (
                    id SERIAL PRIMARY KEY,
                    user_hash TEXT NOT NULL,
                    record_id INTEGER,
                    symptom_key TEXT NOT NULL,
                    factor TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_relief_user_symptom ON symptom_relief_logs(user_hash, symptom_key)")
            c.execute("""
                CREATE TABLE IF NOT EXISTS daily_checkins (
                    id SERIAL PRIMARY KEY,
                    user_hash TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    severity INTEGER,
                    checkin_date TEXT
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_ci_user ON daily_checkins(user_hash)")
            c.execute("""
                CREATE TABLE IF NOT EXISTS med_reminders (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    med_name TEXT,
                    time_utc TEXT,
                    lang TEXT DEFAULT 'ar',
                    active INTEGER DEFAULT 1,
                    created TEXT
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_med_user ON med_reminders(user_id)")
            c.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id SERIAL PRIMARY KEY,
                    user_hash TEXT NOT NULL,
                    record_id INTEGER,
                    rating TEXT,
                    comment TEXT,
                    public_comment INTEGER NOT NULL DEFAULT 0,
                    timestamp TEXT NOT NULL
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_fb_record ON feedback(record_id)")
            c.execute("""
                CREATE TABLE IF NOT EXISTS assistant_feedback (
                    id SERIAL PRIMARY KEY,
                    user_hash TEXT NOT NULL,
                    message TEXT,
                    rating INTEGER,
                    reason TEXT,
                    timestamp TEXT NOT NULL
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_asst_fb_time ON assistant_feedback(timestamp)")
            c.execute("""
                CREATE TABLE IF NOT EXISTS symptom_followups (
                    id SERIAL PRIMARY KEY,
                    user_hash TEXT NOT NULL,
                    record_id INTEGER NOT NULL,
                    outcome TEXT NOT NULL,
                    new_sign INTEGER NOT NULL DEFAULT 0,
                    timestamp TEXT NOT NULL
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_followup_user ON symptom_followups(user_hash, record_id)")
            c.execute("""
                CREATE TABLE IF NOT EXISTS vitals (
                    id SERIAL PRIMARY KEY,
                    user_hash TEXT NOT NULL,
                    member_id INTEGER NOT NULL DEFAULT 0,
                    kind TEXT NOT NULL,
                    v1 REAL NOT NULL,
                    v2 REAL,
                    context TEXT,
                    measured_at TEXT NOT NULL,
                    created TEXT NOT NULL
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_vitals_user ON vitals(user_hash, member_id, kind, measured_at)")
            c.execute("""
                CREATE TABLE IF NOT EXISTS user_data (
                    user_id BIGINT PRIMARY KEY,
                    data TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    name TEXT NOT NULL,
                    key TEXT NOT NULL,
                    state TEXT,
                    PRIMARY KEY (name, key)
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS blood_tests (
                    id SERIAL PRIMARY KEY,
                    user_hash TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    data TEXT NOT NULL,
                    member_id INTEGER DEFAULT 0,
                    file_hash TEXT
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_blood_user ON blood_tests(user_hash)")
            c.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    user_hash TEXT PRIMARY KEY,
                    lang TEXT DEFAULT 'ar',
                    age TEXT,
                    gender TEXT,
                    conditions TEXT,
                    medications TEXT,
                    allergies TEXT,
                    updated_at TEXT NOT NULL
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS results (
                    user_hash TEXT NOT NULL,
                    record_id INTEGER NOT NULL,
                    data TEXT NOT NULL,
                    PRIMARY KEY (user_hash, record_id)
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS family_members (
                    id SERIAL PRIMARY KEY,
                    user_hash TEXT NOT NULL,
                    relation TEXT,
                    name TEXT NOT NULL,
                    age TEXT,
                    gender TEXT,
                    conditions TEXT,
                    medications TEXT,
                    allergies TEXT,
                    notes TEXT,
                    created TEXT
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_fam_user ON family_members(user_hash)")
            c.execute("""
                CREATE TABLE IF NOT EXISTS med_plans (
                    id SERIAL PRIMARY KEY,
                    user_hash TEXT NOT NULL,
                    member_id INTEGER DEFAULT 0,
                    med_name TEXT NOT NULL,
                    dose TEXT,
                    times TEXT NOT NULL,
                    frequency TEXT DEFAULT 'daily',
                    start_date TEXT,
                    days INTEGER,
                    active INTEGER DEFAULT 1,
                    created TEXT
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_mp_user ON med_plans(user_hash)")
            c.execute("""
                CREATE TABLE IF NOT EXISTS med_logs (
                    id SERIAL PRIMARY KEY,
                    user_hash TEXT NOT NULL,
                    member_id INTEGER DEFAULT 0,
                    plan_id INTEGER NOT NULL,
                    log_date TEXT NOT NULL,
                    log_time TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created TEXT
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_ml_plan ON med_logs(plan_id, log_date)")
        else:
            c.execute("""
                CREATE TABLE IF NOT EXISTS records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_hash TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    lang TEXT,
                    age INTEGER,
                    gender TEXT,
                    symptoms TEXT,
                    conditions TEXT,
                    medications TEXT,
                    duration TEXT,
                    severity INTEGER,
                    urgency TEXT
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_user_hash ON records(user_hash)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON records(timestamp)")
            c.execute("""
                CREATE TABLE IF NOT EXISTS visits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_hash TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_visit_user ON visits(user_hash)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_visit_timestamp ON visits(timestamp)")
            c.execute("""
                CREATE TABLE IF NOT EXISTS subscribers (
                    user_id INTEGER PRIMARY KEY,
                    lang TEXT DEFAULT 'ar',
                    subscribed INTEGER DEFAULT 1,
                    added_at TEXT
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS followups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_hash TEXT NOT NULL,
                    record_id INTEGER,
                    timestamp TEXT NOT NULL,
                    outcome TEXT
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_fu_record ON followups(record_id)")
            c.execute("""
                CREATE TABLE IF NOT EXISTS symptom_relief_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_hash TEXT NOT NULL,
                    record_id INTEGER,
                    symptom_key TEXT NOT NULL,
                    factor TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_relief_user_symptom ON symptom_relief_logs(user_hash, symptom_key)")
            c.execute("""
                CREATE TABLE IF NOT EXISTS daily_checkins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_hash TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    severity INTEGER,
                    checkin_date TEXT
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_ci_user ON daily_checkins(user_hash)")
            c.execute("""
                CREATE TABLE IF NOT EXISTS med_reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    med_name TEXT,
                    time_utc TEXT,
                    lang TEXT DEFAULT 'ar',
                    active INTEGER DEFAULT 1,
                    created TEXT
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_med_user ON med_reminders(user_id)")
            c.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_hash TEXT NOT NULL,
                    record_id INTEGER,
                    rating TEXT,
                    comment TEXT,
                    public_comment INTEGER NOT NULL DEFAULT 0,
                    timestamp TEXT NOT NULL
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_fb_record ON feedback(record_id)")
            c.execute("""
                CREATE TABLE IF NOT EXISTS assistant_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_hash TEXT NOT NULL,
                    message TEXT,
                    rating INTEGER,
                    reason TEXT,
                    timestamp TEXT NOT NULL
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_asst_fb_time ON assistant_feedback(timestamp)")
            c.execute("""
                CREATE TABLE IF NOT EXISTS symptom_followups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_hash TEXT NOT NULL,
                    record_id INTEGER NOT NULL,
                    outcome TEXT NOT NULL,
                    new_sign INTEGER NOT NULL DEFAULT 0,
                    timestamp TEXT NOT NULL
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_followup_user ON symptom_followups(user_hash, record_id)")
            c.execute("""
                CREATE TABLE IF NOT EXISTS vitals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_hash TEXT NOT NULL,
                    member_id INTEGER NOT NULL DEFAULT 0,
                    kind TEXT NOT NULL,
                    v1 REAL NOT NULL,
                    v2 REAL,
                    context TEXT,
                    measured_at TEXT NOT NULL,
                    created TEXT NOT NULL
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_vitals_user ON vitals(user_hash, member_id, kind, measured_at)")
            c.execute("""
                CREATE TABLE IF NOT EXISTS user_data (
                    user_id INTEGER PRIMARY KEY,
                    data TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    name TEXT NOT NULL,
                    key TEXT NOT NULL,
                    state TEXT,
                    PRIMARY KEY (name, key)
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS blood_tests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_hash TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    data TEXT NOT NULL,
                    member_id INTEGER DEFAULT 0,
                    file_hash TEXT
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_blood_user ON blood_tests(user_hash)")
            c.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    user_hash TEXT PRIMARY KEY,
                    lang TEXT DEFAULT 'ar',
                    age TEXT,
                    gender TEXT,
                    conditions TEXT,
                    medications TEXT,
                    allergies TEXT,
                    updated_at TEXT NOT NULL
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS results (
                    user_hash TEXT NOT NULL,
                    record_id INTEGER NOT NULL,
                    data TEXT NOT NULL,
                    PRIMARY KEY (user_hash, record_id)
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS family_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_hash TEXT NOT NULL,
                    relation TEXT,
                    name TEXT NOT NULL,
                    age TEXT,
                    gender TEXT,
                    conditions TEXT,
                    medications TEXT,
                    allergies TEXT,
                    notes TEXT,
                    created TEXT
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_fam_user ON family_members(user_hash)")
            c.execute("""
                CREATE TABLE IF NOT EXISTS med_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_hash TEXT NOT NULL,
                    member_id INTEGER DEFAULT 0,
                    med_name TEXT NOT NULL,
                    dose TEXT,
                    times TEXT NOT NULL,
                    frequency TEXT DEFAULT 'daily',
                    start_date TEXT,
                    days INTEGER,
                    active INTEGER DEFAULT 1,
                    created TEXT
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_mp_user ON med_plans(user_hash)")
            c.execute("""
                CREATE TABLE IF NOT EXISTS med_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_hash TEXT NOT NULL,
                    member_id INTEGER DEFAULT 0,
                    plan_id INTEGER NOT NULL,
                    log_date TEXT NOT NULL,
                    log_time TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created TEXT
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_ml_plan ON med_logs(plan_id, log_date)")
        # ---- Web Push notification tables ----
        _create_push_tables(c)
        # ---- Smart Account System tables ----
        _create_ss_tables(c)
        conn.commit()
        _migrate_records(conn, c)
        _migrate_feedback(conn, c)
        _migrate_members(conn, c)
        _migrate_blood_dedup(conn, c)
        _migrate_daily_checkins(conn, c)
        _migrate_ss_columns(conn, c)
        _migrate_assistant_feedback_privacy(conn, c)
        _verify_critical_account_schema(c)
        conn.commit()
    finally:
        conn.close()

    # Keep the existing project-owner account synchronized with the persisted
    # Admin role. This never creates an account and never changes another
    # user's role. It also repairs legacy values such as Admin/ADMIN by writing
    # the canonical lowercase value ``admin`` only for the configured owner.
    try:
        owner_state = ensure_owner_admin_by_email()
        if owner_state.get("reason") == "owner_not_configured":
            _logger.info("Admin bootstrap skipped; persisted Admin role remains authoritative")
        elif not owner_state.get("found"):
            _logger.warning("Configured Admin owner account not found in ss_users; no account was created")
        elif owner_state.get("reason") == "owner_inactive":
            _logger.warning("Admin owner account exists but is inactive; Admin access remains denied")
        elif owner_state.get("promoted"):
            _logger.info("Admin owner role synchronized to canonical role=admin")
    except Exception as exc:
        # Schema initialization should surface the reason in logs but must not
        # mutate or recreate user accounts as a fallback.
        _logger.error("Admin owner role synchronization failed: %s", type(exc).__name__)


def _create_push_tables(c):
    """Create Web Push subscription and delivery de-duplication tables."""
    if USE_POSTGRES:
        c.execute("""
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id SERIAL PRIMARY KEY,
                user_hash TEXT NOT NULL,
                endpoint TEXT UNIQUE NOT NULL,
                p256dh TEXT NOT NULL,
                auth TEXT NOT NULL,
                timezone TEXT DEFAULT 'Asia/Riyadh',
                lang TEXT DEFAULT 'ar',
                active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_push_user ON push_subscriptions(user_hash)")
        c.execute("""
            CREATE TABLE IF NOT EXISTS push_delivery_log (
                id SERIAL PRIMARY KEY,
                endpoint TEXT NOT NULL,
                plan_id INTEGER NOT NULL,
                local_date TEXT NOT NULL,
                local_time TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                UNIQUE(endpoint, plan_id, local_date, local_time)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_push_delivery_plan ON push_delivery_log(plan_id)")
    else:
        c.execute("""
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_hash TEXT NOT NULL,
                endpoint TEXT UNIQUE NOT NULL,
                p256dh TEXT NOT NULL,
                auth TEXT NOT NULL,
                timezone TEXT DEFAULT 'Asia/Riyadh',
                lang TEXT DEFAULT 'ar',
                active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_push_user ON push_subscriptions(user_hash)")
        c.execute("""
            CREATE TABLE IF NOT EXISTS push_delivery_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint TEXT NOT NULL,
                plan_id INTEGER NOT NULL,
                local_date TEXT NOT NULL,
                local_time TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                UNIQUE(endpoint, plan_id, local_date, local_time)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_push_delivery_plan ON push_delivery_log(plan_id)")


def _create_ss_tables(c):
    """Create SymptoSense Smart Account tables if they don't exist."""
    if USE_POSTGRES:
        c.execute("""
            CREATE TABLE IF NOT EXISTS ss_users (
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                status TEXT NOT NULL DEFAULT 'active',
                email_verified INTEGER NOT NULL DEFAULT 1,
                email_verified_at TEXT,
                created_at TEXT NOT NULL,
                last_login TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS ss_health_profiles (
                user_id INTEGER PRIMARY KEY REFERENCES ss_users(id) ON DELETE CASCADE,
                display_name TEXT DEFAULT '',
                dob TEXT DEFAULT '',
                gender TEXT DEFAULT '',
                height TEXT DEFAULT '',
                weight TEXT DEFAULT '',
                activity_level TEXT DEFAULT '',
                medications TEXT DEFAULT '',
                allergies TEXT DEFAULT '',
                health_conditions TEXT DEFAULT '',
                extra_info TEXT DEFAULT '',
                lang TEXT DEFAULT 'ar',
                updated_at TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS ss_privacy (
                user_id INTEGER PRIMARY KEY REFERENCES ss_users(id) ON DELETE CASCADE,
                use_in_assistant INTEGER DEFAULT 1,
                use_in_analysis INTEGER DEFAULT 1,
                use_in_calculators INTEGER DEFAULT 1,
                save_chat_history INTEGER DEFAULT 1,
                updated_at TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS ss_chat_history (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES ss_users(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_ss_chat_user ON ss_chat_history(user_id)")
    else:
        c.execute("""
            CREATE TABLE IF NOT EXISTS ss_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                status TEXT NOT NULL DEFAULT 'active',
                email_verified INTEGER NOT NULL DEFAULT 1,
                email_verified_at TEXT,
                created_at TEXT NOT NULL,
                last_login TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS ss_health_profiles (
                user_id INTEGER PRIMARY KEY,
                display_name TEXT DEFAULT '',
                dob TEXT DEFAULT '',
                gender TEXT DEFAULT '',
                height TEXT DEFAULT '',
                weight TEXT DEFAULT '',
                activity_level TEXT DEFAULT '',
                medications TEXT DEFAULT '',
                allergies TEXT DEFAULT '',
                health_conditions TEXT DEFAULT '',
                extra_info TEXT DEFAULT '',
                lang TEXT DEFAULT 'ar',
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES ss_users(id) ON DELETE CASCADE
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS ss_privacy (
                user_id INTEGER PRIMARY KEY,
                use_in_assistant INTEGER DEFAULT 1,
                use_in_analysis INTEGER DEFAULT 1,
                use_in_calculators INTEGER DEFAULT 1,
                save_chat_history INTEGER DEFAULT 1,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES ss_users(id) ON DELETE CASCADE
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS ss_chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES ss_users(id) ON DELETE CASCADE
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_ss_chat_user ON ss_chat_history(user_id)")


def _migrate_ss_columns(conn, c):
    """Add new columns to existing account tables without deleting data.

    The role/status columns are security-critical, so migration failures for
    those columns are intentionally not swallowed. Optional profile migrations
    remain best-effort for backward compatibility.
    """
    def columns(table):
        if USE_POSTGRES:
            c.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
                (table,),
            )
            return {row[0] for row in c.fetchall()}
        c.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in c.fetchall()}

    user_cols = columns("ss_users")
    if "role" not in user_cols:
        c.execute("ALTER TABLE ss_users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
    if "status" not in user_cols:
        c.execute("ALTER TABLE ss_users ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
    if "email_verified" not in user_cols:
        # DEFAULT 1 makes the ALTER safe for legacy rows; the one-time security
        # migration below then explicitly moves existing accounts to the fresh
        # verification-required state without touching passwords or user data.
        c.execute("ALTER TABLE ss_users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 1")
    if "email_verified_at" not in user_cols:
        c.execute("ALTER TABLE ss_users ADD COLUMN email_verified_at TEXT")

    # Canonical single-owner RBAC and the one-time email-verification migration
    # are security-critical. Failures here must propagate so init_db() does not
    # cache a partially migrated database as ready.
    c.execute("CREATE TABLE IF NOT EXISTS ss_schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    c.execute("SELECT value FROM ss_schema_meta WHERE key='email_otp_all_accounts_v1'")
    if not c.fetchone():
        c.execute("UPDATE ss_users SET email_verified=0,email_verified_at=NULL")
        c.execute(
            "INSERT INTO ss_schema_meta (key,value) VALUES (%s,%s)" % (PH, PH),
            ("email_otp_all_accounts_v1", datetime.now(timezone.utc).isoformat()),
        )

    # Normalize role spelling without destroying a valid persisted Admin when
    # Railway temporarily lacks SYMPTOSENSE_ADMIN_EMAIL. If an owner email is
    # configured we can safely demote any stale Admin row that does not belong
    # to that owner; otherwise the already-persisted Admin remains authoritative.
    c.execute("UPDATE ss_users SET role=lower(COALESCE(role,'user'))")
    if OWNER_ADMIN_EMAIL:
        c.execute(
            "UPDATE ss_users SET role='user' WHERE role='admin' AND lower(email)<>%s" % PH,
            (OWNER_ADMIN_EMAIL,),
        )
    else:
        # Keep one historical Admin if a legacy database somehow contains more
        # than one. The oldest Admin row is retained; no ordinary user is promoted.
        c.execute("SELECT id FROM ss_users WHERE role='admin' ORDER BY id")
        admin_rows = [row[0] for row in c.fetchall()]
        if len(admin_rows) > 1:
            keep_id = int(admin_rows[0])
            c.execute("UPDATE ss_users SET role='user' WHERE role='admin' AND id<>%s" % PH, (keep_id,))
            _logger.warning("Multiple persisted Admin rows found; preserved the oldest Admin row only")

    # Database-level second line of defence: at most one canonical admin role.
    c.execute("DROP INDEX IF EXISTS idx_ss_single_active_admin")
    c.execute("DROP INDEX IF EXISTS idx_ss_single_admin")
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_ss_single_admin ON ss_users(role) WHERE role='admin'")

    try:
        hp_cols = columns("ss_health_profiles")
        for col, default in [("extra_info", ""), ("activity_level", "")]:
            if col not in hp_cols:
                c.execute(f"ALTER TABLE ss_health_profiles ADD COLUMN {col} TEXT DEFAULT '{default}'")
    except DB_ERRORS:
        # Optional profile columns must not prevent existing accounts from login.
        logging.getLogger(__name__).debug("Handled exception in _migrate_ss_columns; fallback applied (handler 786)")
        pass



def _migrate_assistant_feedback_privacy(conn, c):
    """One-time privacy migration: discard legacy free-text assistant feedback.

    Aggregate ratings and short reason categories are retained.
    """
    c.execute("CREATE TABLE IF NOT EXISTS ss_schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    marker = "assistant_feedback_no_text_v1"
    c.execute(f"SELECT value FROM ss_schema_meta WHERE key={PH}", (marker,))
    if c.fetchone():
        return
    c.execute("UPDATE assistant_feedback SET message=NULL WHERE message IS NOT NULL AND message<>''")
    c.execute(
        f"INSERT INTO ss_schema_meta (key,value) VALUES ({PH},{PH})",
        (marker, datetime.now(timezone.utc).isoformat()),
    )


def _verify_critical_account_schema(c):
    """Verify security-critical account migrations before readiness is cached."""
    if USE_POSTGRES:
        c.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
            ("ss_users",),
        )
        user_cols = {row[0] for row in c.fetchall()}
    else:
        c.execute("PRAGMA table_info(ss_users)")
        user_cols = {row[1] for row in c.fetchall()}

    required = {"role", "status", "email_verified", "email_verified_at"}
    missing = sorted(required - user_cols)
    if missing:
        raise RuntimeError("Critical account schema migration incomplete: " + ", ".join(missing))

    # The marker is written in the same transaction as the one-time migration.
    # If it is absent, initialization must not be cached as successful.
    c.execute("SELECT value FROM ss_schema_meta WHERE key='email_otp_all_accounts_v1'")
    if not c.fetchone():
        raise RuntimeError("Critical email verification migration marker is missing")


def _migrate_daily_checkins(conn, c):
    """Add a stable local-date key used by account daily tracking.

    Older installs stored only an ISO timestamp and allowed more than one row
    per day.  Keep those rows intact, backfill the date, and let the write path
    update the latest row for that user/date instead of creating duplicates.
    """
    if USE_POSTGRES:
        c.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
            ("daily_checkins",),
        )
        existing = {row[0] for row in c.fetchall()}
    else:
        c.execute("PRAGMA table_info(daily_checkins)")
        existing = {row[1] for row in c.fetchall()}
    if "checkin_date" not in existing:
        c.execute("ALTER TABLE daily_checkins ADD COLUMN checkin_date TEXT")
    # SUBSTR(text, start, length) works in both SQLite and PostgreSQL.
    c.execute(
        "UPDATE daily_checkins SET checkin_date=SUBSTR(CAST(timestamp AS TEXT),1,10) "
        "WHERE checkin_date IS NULL OR checkin_date=''"
    )
    # Legacy builds allowed multiple rows on the same day. Keep the newest row
    # for each user/date before enforcing the one-check-in-per-day invariant.
    c.execute(
        "SELECT id,user_hash,checkin_date,timestamp FROM daily_checkins "
        "WHERE checkin_date IS NOT NULL ORDER BY user_hash,checkin_date,timestamp DESC,id DESC"
    )
    seen = set()
    duplicate_ids = []
    for row in c.fetchall():
        key = (row[1], row[2])
        if key in seen:
            duplicate_ids.append(row[0])
        else:
            seen.add(key)
    for row_id in duplicate_ids:
        c.execute(f"DELETE FROM daily_checkins WHERE id={PH}", (row_id,))
    c.execute("CREATE INDEX IF NOT EXISTS idx_ci_user_date ON daily_checkins(user_hash, checkin_date)")
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_ci_user_date_unique ON daily_checkins(user_hash, checkin_date)")


def _import_legacy_daily_checkins_best_effort():
    """Copy any usable legacy daily_checkins rows into the stable tracking table.

    Legacy import must never make the live tracking feature unavailable. Railway
    databases may contain older variants of daily_checkins, so this runs in its
    own transaction and quietly skips incompatible legacy shapes after logging.
    """
    conn = _conn()
    try:
        c = conn.cursor()
        if USE_POSTGRES:
            c.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
                ("daily_checkins",),
            )
            cols = {row[0] for row in c.fetchall()}
        else:
            c.execute("PRAGMA table_info(daily_checkins)")
            cols = {row[1] for row in c.fetchall()}
        if not {"user_hash", "severity"}.issubset(cols):
            return
        if "checkin_date" in cols:
            day_expr = "checkin_date"
        elif "timestamp" in cols:
            day_expr = "SUBSTR(CAST(timestamp AS TEXT),1,10)"
        else:
            return
        ts_expr = "CAST(timestamp AS TEXT)" if "timestamp" in cols else "''"
        c.execute(
            f"SELECT user_hash,{day_expr},severity,{ts_expr} FROM daily_checkins "
            f"WHERE {day_expr} IS NOT NULL AND severity IS NOT NULL"
        )
        rows = c.fetchall()
        for user_hash, day, severity, updated_at in rows:
            day = str(day or '')[:10]
            if not day:
                continue
            try:
                rating = int(severity)
            except (TypeError, ValueError, OverflowError):
                logging.getLogger(__name__).debug("Handled exception in _import_legacy_daily_checkins_best_effort; fallback applied (handler 898)")
                continue
            if rating < 1 or rating > 5:
                continue
            c.execute(
                f"INSERT INTO ss_daily_checkins (user_hash,checkin_date,severity,updated_at) "
                f"VALUES ({PH},{PH},{PH},{PH}) "
                "ON CONFLICT(user_hash,checkin_date) DO UPDATE SET "
                "severity=excluded.severity,updated_at=excluded.updated_at",
                (str(user_hash), day, rating, str(updated_at or '')),
            )
        conn.commit()
    except Exception as exc:
        try:
            conn.rollback()
        except DB_ERRORS:
            logging.getLogger(__name__).warning("Handled exception in _import_legacy_daily_checkins_best_effort; fallback applied (handler 913)")
            pass
        _logger.warning("Legacy daily_checkins import skipped: %s", type(exc).__name__)
    finally:
        conn.close()


def ensure_daily_checkins_schema():
    """Ensure a stable account/day tracking store exists for the active DB.

    The live feature no longer depends on mutating the historical
    ``daily_checkins`` table. Some Railway databases contain older variants of
    that table, and an ALTER/index migration can fail even though the rest of
    the application is healthy. ``ss_daily_checkins`` uses a compact stable
    schema with a composite primary key, so one account can have at most one
    row per day without relying on a legacy index migration.
    """
    global _CHECKIN_SCHEMA_READY_KEY
    key = _database_identity()
    if _CHECKIN_SCHEMA_READY_KEY == key:
        return
    with _CHECKIN_SCHEMA_LOCK:
        key = _database_identity()
        if _CHECKIN_SCHEMA_READY_KEY == key:
            return
        _init_backend()
        conn = _conn()
        try:
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS ss_daily_checkins (
                    user_hash TEXT NOT NULL,
                    checkin_date TEXT NOT NULL,
                    severity INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (user_hash, checkin_date)
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_ss_ci_user_date ON ss_daily_checkins(user_hash, checkin_date)")
            if USE_POSTGRES:
                c.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
                    ("ss_daily_checkins",),
                )
                cols = {row[0] for row in c.fetchall()}
            else:
                c.execute("PRAGMA table_info(ss_daily_checkins)")
                cols = {row[1] for row in c.fetchall()}
            required = {"user_hash", "checkin_date", "severity", "updated_at"}
            missing = sorted(required - cols)
            if missing:
                raise RuntimeError("Stable daily tracking schema incomplete: " + ", ".join(missing))
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except DB_ERRORS:
                logging.getLogger(__name__).warning("Handled exception in ensure_daily_checkins_schema; fallback applied (handler 969)")
                pass
            raise
        finally:
            conn.close()
        _CHECKIN_SCHEMA_READY_KEY = _database_identity()
        # Import old rows only after the new store is fully committed. A broken
        # legacy table must never take the new feature down.
        _import_legacy_daily_checkins_best_effort()


def _migrate_feedback(conn, c):
    """Add the comment column to feedback tables created before this feature."""
    if USE_POSTGRES:
        c.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
            ("feedback",),
        )
        existing = {row[0] for row in c.fetchall()}
    else:
        c.execute("PRAGMA table_info(feedback)")
        existing = {row[1] for row in c.fetchall()}
    if "comment" not in existing:
        c.execute("ALTER TABLE feedback ADD COLUMN comment TEXT")
    if "public_comment" not in existing:
        c.execute("ALTER TABLE feedback ADD COLUMN public_comment INTEGER NOT NULL DEFAULT 0")
    if "reason_code" not in existing:
        c.execute("ALTER TABLE feedback ADD COLUMN reason_code TEXT")
    if "context" not in existing:
        c.execute("ALTER TABLE feedback ADD COLUMN context TEXT")


def _migrate_records(conn, c):
    """Add any columns introduced after the table was first created."""
    if USE_POSTGRES:
        c.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
            ("records",),
        )
        existing = {row[0] for row in c.fetchall()}
    else:
        c.execute("PRAGMA table_info(records)")
        existing = {row[1] for row in c.fetchall()}
    for col in ("conditions", "medications"):
        if col not in existing:
            c.execute(f"ALTER TABLE records ADD COLUMN {col} TEXT")


def _migrate_members(conn, c):
    """Add the member_id column to records and blood_tests for existing DBs."""
    def columns(table):
        if USE_POSTGRES:
            c.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
                (table,),
            )
            return {row[0] for row in c.fetchall()}
        c.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in c.fetchall()}
    try:
        for table in ("records", "blood_tests"):
            if "member_id" not in columns(table):
                c.execute(f"ALTER TABLE {table} ADD COLUMN member_id INTEGER DEFAULT 0")
    except DB_ERRORS:
        logging.getLogger(__name__).warning("Handled exception in _migrate_members; fallback applied (handler 1028)")
        pass


def _migrate_blood_dedup(conn, c):
    """Add exact-file de-duplication and persisted blood-consent storage.

    ``file_hash`` contains only a SHA-256 digest of the uploaded file bytes; the
    original PDF/image is never stored.  The unique index makes the guarantee
    race-safe across multiple web workers: one account/member can have at most
    one saved row for the exact same file.
    """
    def columns(table):
        if USE_POSTGRES:
            c.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
                (table,),
            )
            return {row[0] for row in c.fetchall()}
        c.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in c.fetchall()}

    existing = columns("blood_tests")
    if "file_hash" not in existing:
        c.execute("ALTER TABLE blood_tests ADD COLUMN file_hash TEXT")
    # Both SQLite and PostgreSQL allow multiple NULL values in a UNIQUE index,
    # so legacy rows (which have no hash) remain valid.
    c.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_blood_user_member_file_unique "
        "ON blood_tests(user_hash, member_id, file_hash)"
    )
    c.execute("CREATE INDEX IF NOT EXISTS idx_blood_file_hash ON blood_tests(file_hash)")
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS blood_collection_consents (
            user_hash TEXT PRIMARY KEY,
            consent_version TEXT NOT NULL,
            consented_at TEXT NOT NULL
        )
        """
    )


def fetchall(sql, params=()):
    """Generic read helper so the dashboard doesn't need a raw DB connection."""
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(sql, params)
        return c.fetchall()
    finally:
        conn.close()


def add_subscriber(user_id, lang="ar"):
    """Registers/updates a user for the daily health tip broadcast (opt-out via unsubscribe())."""
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"INSERT INTO subscribers (user_id, lang, subscribed, added_at) VALUES ({PH},{PH},1,{PH}) "
            f"ON CONFLICT(user_id) DO UPDATE SET lang=excluded.lang, subscribed=1",
            (user_id, lang, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def unsubscribe(user_id):
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(f"UPDATE subscribers SET subscribed=0 WHERE user_id={PH}", (user_id,))
        conn.commit()
    finally:
        conn.close()


def get_subscribers():
    """Returns [(user_id, lang), ...] for all currently opted-in users."""
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute("SELECT user_id, lang FROM subscribers WHERE subscribed=1")
        return c.fetchall()
    finally:
        conn.close()


def save_push_subscription(user_id, subscription, timezone_name='Asia/Riyadh', lang='ar'):
    endpoint = str(subscription.get('endpoint') or '').strip()
    keys = subscription.get('keys') or {}
    p256dh = str(keys.get('p256dh') or '').strip()
    auth = str(keys.get('auth') or '').strip()
    if not endpoint or not p256dh or not auth:
        raise ValueError('Invalid push subscription')
    now = datetime.now(timezone.utc).isoformat()
    conn = _conn()
    try:
        c = conn.cursor()
        if USE_POSTGRES:
            c.execute(
                f"INSERT INTO push_subscriptions (user_hash, endpoint, p256dh, auth, timezone, lang, active, created_at, updated_at) VALUES ({PH},{PH},{PH},{PH},{PH},{PH},1,{PH},{PH}) "
                f"ON CONFLICT(endpoint) DO UPDATE SET user_hash=EXCLUDED.user_hash, p256dh=EXCLUDED.p256dh, auth=EXCLUDED.auth, timezone=EXCLUDED.timezone, lang=EXCLUDED.lang, active=1, updated_at=EXCLUDED.updated_at",
                (_hash_user(user_id), endpoint, p256dh, auth, timezone_name or 'Asia/Riyadh', lang or 'ar', now, now),
            )
        else:
            c.execute(
                f"INSERT INTO push_subscriptions (user_hash, endpoint, p256dh, auth, timezone, lang, active, created_at, updated_at) VALUES ({PH},{PH},{PH},{PH},{PH},{PH},1,{PH},{PH}) "
                f"ON CONFLICT(endpoint) DO UPDATE SET user_hash=excluded.user_hash, p256dh=excluded.p256dh, auth=excluded.auth, timezone=excluded.timezone, lang=excluded.lang, active=1, updated_at=excluded.updated_at",
                (_hash_user(user_id), endpoint, p256dh, auth, timezone_name or 'Asia/Riyadh', lang or 'ar', now, now),
            )
        conn.commit()
    finally:
        conn.close()


def delete_push_subscription(user_id, endpoint=None):
    conn = _conn()
    try:
        c = conn.cursor()
        if endpoint:
            c.execute(f"UPDATE push_subscriptions SET active=0, updated_at={PH} WHERE user_hash={PH} AND endpoint={PH}", (datetime.now(timezone.utc).isoformat(), _hash_user(user_id), endpoint))
        else:
            c.execute(f"UPDATE push_subscriptions SET active=0, updated_at={PH} WHERE user_hash={PH}", (datetime.now(timezone.utc).isoformat(), _hash_user(user_id)))
        conn.commit()
    finally:
        conn.close()


def list_push_subscriptions(user_id=None, active_only=True):
    conn = _conn()
    try:
        c = conn.cursor()
        where, params = [], []
        if user_id is not None:
            where.append(f"user_hash={PH}")
            params.append(_hash_user(user_id))
        if active_only:
            where.append("active=1")
        sql = "SELECT user_hash, endpoint, p256dh, auth, timezone, lang, active FROM push_subscriptions"
        if where:
            sql += " WHERE " + " AND ".join(where)
        c.execute(sql, tuple(params))
        rows = c.fetchall()
    finally:
        conn.close()
    return [{'user_hash': r[0], 'endpoint': r[1], 'p256dh': r[2], 'auth': r[3], 'timezone': r[4] or 'Asia/Riyadh', 'lang': r[5] or 'ar', 'active': bool(r[6])} for r in rows]


def mark_push_subscription_inactive(endpoint):
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(f"UPDATE push_subscriptions SET active=0, updated_at={PH} WHERE endpoint={PH}", (datetime.now(timezone.utc).isoformat(), endpoint))
        conn.commit()
    finally:
        conn.close()


def list_active_med_plans_for_push():
    import json as _json
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute("SELECT id, user_hash, member_id, med_name, dose, times, start_date, days, active FROM med_plans WHERE active=1")
        rows = c.fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        try:
            times = _json.loads(r[5])
        except (TypeError, ValueError, OverflowError):
            logging.getLogger(__name__).debug("Handled exception in list_active_med_plans_for_push; fallback applied (handler 1163)")
            times = []
        out.append({'id': r[0], 'user_hash': r[1], 'member_id': r[2], 'med_name': r[3], 'dose': r[4] or '', 'times': [str(x) for x in times], 'start_date': r[6] or '', 'days': r[7], 'active': bool(r[8])})
    return out


def release_push_delivery(endpoint, plan_id, local_date, local_time):
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(f"DELETE FROM push_delivery_log WHERE endpoint={PH} AND plan_id={PH} AND local_date={PH} AND local_time={PH}", (endpoint, int(plan_id), local_date, local_time))
        conn.commit()
    finally:
        conn.close()


def claim_push_delivery(endpoint, plan_id, local_date, local_time):
    now = datetime.now(timezone.utc).isoformat()
    conn = _conn()
    try:
        c = conn.cursor()
        try:
            c.execute(f"INSERT INTO push_delivery_log (endpoint, plan_id, local_date, local_time, sent_at) VALUES ({PH},{PH},{PH},{PH},{PH})", (endpoint, int(plan_id), local_date, local_time, now))
            conn.commit()
            return True
        except DB_ERRORS:
            logging.getLogger(__name__).debug("Handled exception in claim_push_delivery; fallback applied (handler 1188)")
            conn.rollback()
            return False
    finally:
        conn.close()


def log_visit(user_id):
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"INSERT INTO visits (user_hash, timestamp) VALUES ({PH},{PH})",
            (_hash_user(user_id), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    except Exception as e:
        import logging
        logging.getLogger("SymptoSense").error("log_visit failed: error_type=%s", type(e).__name__)
    finally:
        conn.close()


def get_usage_stats(days=7):
    conn = _conn()
    try:
        c = conn.cursor()
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        c.execute("SELECT COUNT(*), COUNT(DISTINCT user_hash) FROM visits")
        total_visits, unique_visitors = c.fetchone()
        c.execute("SELECT COUNT(*), COUNT(DISTINCT user_hash) FROM records")
        total_sessions, unique_users_completed = c.fetchone()
        c.execute(f"SELECT COUNT(*) FROM visits WHERE timestamp >= {PH}", (since,))
        visits_this_period = c.fetchone()[0]
        c.execute(f"SELECT COUNT(*) FROM records WHERE timestamp >= {PH}", (since,))
        sessions_this_period = c.fetchone()[0]
        return {
            "total_visits": total_visits or 0,
            "unique_visitors": unique_visitors or 0,
            "total_sessions": total_sessions or 0,
            "unique_users_completed": unique_users_completed or 0,
            "visits_this_period": visits_this_period or 0,
            "sessions_this_period": sessions_this_period or 0,
            "period_days": days,
        }
    finally:
        conn.close()


def _all_records():
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            "SELECT id, timestamp, lang, age, gender, symptoms, conditions, medications, "
            "duration, severity, urgency FROM records ORDER BY id"
        )
        return c.fetchall()
    finally:
        conn.close()


def export_all_records_csv():
    import csv
    rows = _all_records()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id","timestamp","lang","age","gender","symptoms","conditions","medications","duration","severity","urgency"])
    writer.writerows(rows)
    return buf.getvalue()


def export_all_records_xlsx():
    """Export anonymized records as Excel file — ready for Power BI / Excel analysis."""
    try:
        import openpyxl
    except ImportError:
        # fallback to CSV wrapped in BytesIO if openpyxl not installed
        csv_str = export_all_records_csv()
        return io.BytesIO(csv_str.encode("utf-8-sig"))

    rows = _all_records()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "SymptoSense Records"
    headers = ["id","timestamp","lang","age","gender","symptoms","conditions","medications","duration","severity","urgency"]
    ws.append(headers)
    for row in rows:
        ws.append(list(row))

    fu_rows = _all_followups()
    if fu_rows:
        ws2 = wb.create_sheet("Followups")
        ws2.append(["id","record_id","timestamp","outcome"])
        for row in fu_rows:
            ws2.append(list(row))

    fb_rows = _all_feedback()
    if fb_rows:
        ws4 = wb.create_sheet("Feedback")
        ws4.append(["id","record_id","timestamp","rating","comment"])
        for row in fb_rows:
            ws4.append(list(row))

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _hash_user(user_id) -> str:
    salt = os.environ.get("HASH_SALT", "symptosense")
    return hashlib.sha256(f"{salt}:{user_id}".encode()).hexdigest()[:16]


def get_last_record(user_id):
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"SELECT id, timestamp, symptoms, severity, duration, urgency "
            f"FROM records WHERE user_hash={PH} ORDER BY id DESC LIMIT 1",
            (_hash_user(user_id),),
        )
        row = c.fetchone()
    finally:
        conn.close()
    if not row:
        return None
    rec_id, ts, symptoms, severity, duration, urgency = row
    return {
        "id": rec_id,
        "timestamp": ts,
        "symptoms": [s for s in symptoms.split(",") if s],
        "severity": severity,
        "duration": duration,
        "urgency": urgency,
        "days_ago": (datetime.now(timezone.utc) - datetime.fromisoformat(ts)).days,
    }


def get_records(user_id, limit=20, member_id=None):
    """Returns the user's diagnosis records, newest first. Optionally filtered by member_id."""
    conn = _conn()
    try:
        c = conn.cursor()
        if member_id is None:
            c.execute(
                f"SELECT id, timestamp, lang, age, gender, symptoms, duration, severity, urgency, conditions, medications "
                f"FROM records WHERE user_hash={PH} ORDER BY id DESC LIMIT {int(limit)}",
                (_hash_user(user_id),),
            )
        else:
            c.execute(
                f"SELECT id, timestamp, lang, age, gender, symptoms, duration, severity, urgency, conditions, medications "
                f"FROM records WHERE user_hash={PH} AND member_id={PH} ORDER BY id DESC LIMIT {int(limit)}",
                (_hash_user(user_id), int(member_id)),
            )
        rows = c.fetchall()
    finally:
        conn.close()
    return [
        {
            "id": r[0],
            "timestamp": r[1],
            "lang": r[2],
            "age": r[3],
            "gender": r[4],
            "symptoms": [s for s in (r[5] or "").split(",") if s],
            "duration": r[6],
            "severity": r[7],
            "urgency": r[8],
            "conditions": r[9] or "",
            "medications": r[10] or "",
        }
        for r in rows
    ]


def save_profile(user_id, lang, age, gender, conditions, medications, allergies):
    conn = _conn()
    try:
        c = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        c.execute(
            f"INSERT INTO profiles (user_hash, lang, age, gender, conditions, medications, allergies, updated_at) "
            f"VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH}) "
            f"ON CONFLICT(user_hash) DO UPDATE SET "
            f"lang=excluded.lang, age=excluded.age, gender=excluded.gender, "
            f"conditions=excluded.conditions, medications=excluded.medications, "
            f"allergies=excluded.allergies, updated_at=excluded.updated_at",
            (_hash_user(user_id), lang, age or "", gender or "", conditions or "", medications or "", allergies or "", now),
        )
        conn.commit()
    finally:
        conn.close()


def load_profile(user_id):
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            "SELECT lang, age, gender, conditions, medications, allergies, updated_at "
            "FROM profiles WHERE user_hash=%s" % PH,
            (_hash_user(user_id),),
        )
        row = c.fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return {
        "lang": row[0],
        "age": row[1] or "",
        "gender": row[2] or "",
        "conditions": row[3] or "",
        "medications": row[4] or "",
        "allergies": row[5] or "",
        "updated_at": row[6],
    }


def save_result(user_id, record_id, data):
    """Stores the full analysis result JSON, keyed by (user_hash, record_id)."""
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"INSERT INTO results (user_hash, record_id, data) VALUES ({PH},{PH},{PH}) "
            f"ON CONFLICT(user_hash, record_id) DO UPDATE SET data=excluded.data",
            (_hash_user(user_id), record_id, json.dumps(data, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()


def load_result(user_id, record_id):
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            "SELECT data FROM results WHERE user_hash=%s AND record_id=%s" % (PH, PH),
            (_hash_user(user_id), record_id),
        )
        row = c.fetchone()
    finally:
        conn.close()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except (TypeError, ValueError, OverflowError):
        logging.getLogger(__name__).debug("Handled exception in load_result; fallback applied (handler 1442)")
        return None


def save_record(user_id, lang, age, gender, symptoms, duration, severity, urgency, conditions=None, medications=None, member_id=0):
    conn = _conn()
    try:
        c = conn.cursor()
        if USE_POSTGRES:
            c.execute(
                f"INSERT INTO records (user_hash, timestamp, lang, age, gender, symptoms, conditions, medications, duration, severity, urgency, member_id) "
                f"VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH}) RETURNING id",
                (
                    _hash_user(user_id),
                    datetime.now(timezone.utc).isoformat(),
                    lang, age, gender,
                    ",".join(symptoms or []),
                    conditions or "", medications or "",
                    duration, severity, urgency, int(member_id or 0),
                ),
            )
            rec_id = c.fetchone()[0]
        else:
            c.execute(
                f"INSERT INTO records (user_hash, timestamp, lang, age, gender, symptoms, conditions, medications, duration, severity, urgency, member_id) "
                f"VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})",
                (
                    _hash_user(user_id),
                    datetime.now(timezone.utc).isoformat(),
                    lang, age, gender,
                    ",".join(symptoms or []),
                    conditions or "", medications or "",
                    duration, severity, urgency, int(member_id or 0),
                ),
            )
            rec_id = c.lastrowid
        conn.commit()
        return rec_id
    finally:
        conn.close()


def save_analysis_record_with_result(user_id, lang, age, gender, symptoms, duration, severity, urgency, result_data, conditions=None, medications=None, member_id=0):
    """Persist the analysis record and full result in one transaction/connection.

    On hosted PostgreSQL, opening a fresh connection for the record and then a
    second one for the result adds avoidable latency to the user-facing Analyze
    button. Keeping both writes atomic is also safer if one write fails.
    """
    conn = _conn()
    try:
        c = conn.cursor()
        params = (
            _hash_user(user_id),
            datetime.now(timezone.utc).isoformat(),
            lang, age, gender,
            ",".join(symptoms or []),
            conditions or "", medications or "",
            duration, severity, urgency, int(member_id or 0),
        )
        if USE_POSTGRES:
            c.execute(
                f"INSERT INTO records (user_hash, timestamp, lang, age, gender, symptoms, conditions, medications, duration, severity, urgency, member_id) "
                f"VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH}) RETURNING id",
                params,
            )
            rec_id = c.fetchone()[0]
        else:
            c.execute(
                f"INSERT INTO records (user_hash, timestamp, lang, age, gender, symptoms, conditions, medications, duration, severity, urgency, member_id) "
                f"VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})",
                params,
            )
            rec_id = c.lastrowid
        c.execute(
            f"INSERT INTO results (user_hash, record_id, data) VALUES ({PH},{PH},{PH}) "
            f"ON CONFLICT(user_hash, record_id) DO UPDATE SET data=excluded.data",
            (_hash_user(user_id), rec_id, json.dumps(result_data or {}, ensure_ascii=False)),
        )
        conn.commit()
        return rec_id
    finally:
        conn.close()


def _normalize_file_hash(file_hash):
    value = str(file_hash or "").strip().lower()
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        return None
    return value


def save_blood_collection_consent(user_id, consent_version):
    """Persist the current blood-data collection consent for a signed-in owner."""
    version = str(consent_version or "").strip()[:64]
    if not version:
        raise ValueError("consent_version_required")
    now = datetime.now(timezone.utc).isoformat()
    user_hash = _hash_user(user_id)
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"INSERT INTO blood_collection_consents (user_hash, consent_version, consented_at) VALUES ({PH},{PH},{PH}) "
            "ON CONFLICT(user_hash) DO UPDATE SET consent_version=excluded.consent_version, consented_at=excluded.consented_at",
            (user_hash, version, now),
        )
        conn.commit()
        return {"consent_version": version, "consented_at": now}
    finally:
        conn.close()


def has_blood_collection_consent(user_id, consent_version):
    """Return True only when the stored consent matches the current version."""
    version = str(consent_version or "").strip()[:64]
    if not version:
        return False
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"SELECT consent_version FROM blood_collection_consents WHERE user_hash={PH}",
            (_hash_user(user_id),),
        )
        row = c.fetchone()
        return bool(row and str(row[0] or "") == version)
    finally:
        conn.close()


def find_blood_test_by_file_hash(user_id, file_hash, member_id=0):
    """Find an already-saved analysis for the exact uploaded file bytes."""
    normalized = _normalize_file_hash(file_hash)
    if not normalized:
        return None
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"SELECT id, data, timestamp, file_hash FROM blood_tests "
            f"WHERE user_hash={PH} AND member_id={PH} AND file_hash={PH} "
            "ORDER BY id DESC LIMIT 1",
            (_hash_user(user_id), int(member_id or 0), normalized),
        )
        row = c.fetchone()
    finally:
        conn.close()
    if not row:
        return None
    try:
        return {"id": row[0], "data": json.loads(row[1]), "timestamp": row[2] or "", "file_hash": row[3] or ""}
    except (TypeError, ValueError, OverflowError):
        logging.getLogger(__name__).debug("Unable to decode saved blood-test duplicate row", exc_info=True)
        return None


def save_blood_test_once(user_id, data, member_id=0, file_hash=None):
    """Save one blood analysis, atomically de-duplicating exact file uploads.

    Returns ``(blood_id, created)``.  When another request has already saved the
    same account/member/file hash, the existing row id is returned with
    ``created=False`` rather than inserting a second Excel-visible record.
    """
    normalized = _normalize_file_hash(file_hash)
    user_hash = _hash_user(user_id)
    member = int(member_id or 0)
    payload = json.dumps(data, ensure_ascii=False)
    now = datetime.now(timezone.utc).isoformat()
    conn = _conn()
    try:
        c = conn.cursor()
        try:
            if USE_POSTGRES:
                c.execute(
                    f"INSERT INTO blood_tests (user_hash, timestamp, data, member_id, file_hash) "
                    f"VALUES ({PH},{PH},{PH},{PH},{PH}) RETURNING id",
                    (user_hash, now, payload, member, normalized),
                )
                new_id = c.fetchone()[0]
            else:
                c.execute(
                    f"INSERT INTO blood_tests (user_hash, timestamp, data, member_id, file_hash) "
                    f"VALUES ({PH},{PH},{PH},{PH},{PH})",
                    (user_hash, now, payload, member, normalized),
                )
                new_id = c.lastrowid
            conn.commit()
            return new_id, True
        except DB_ERRORS:
            conn.rollback()
            # A UNIQUE collision is the expected race-safe duplicate path.
            # Re-query by hash; if no matching row exists, re-raise the original
            # insert failure instead of hiding an unrelated database problem.
            if normalized:
                c = conn.cursor()
                c.execute(
                    f"SELECT id FROM blood_tests WHERE user_hash={PH} AND member_id={PH} AND file_hash={PH} "
                    "ORDER BY id DESC LIMIT 1",
                    (user_hash, member, normalized),
                )
                row = c.fetchone()
                if row:
                    return row[0], False
            raise
    finally:
        conn.close()


def save_blood_test(user_id, data, member_id=0, file_hash=None):
    """Backward-compatible blood-test save helper."""
    blood_id, _created = save_blood_test_once(user_id, data, member_id, file_hash=file_hash)
    return blood_id


def get_blood_tests(user_id, limit=1, member_id=None):
    conn = _conn()
    try:
        c = conn.cursor()
        if member_id is None:
            c.execute(
                f"SELECT id, data, timestamp, file_hash FROM blood_tests WHERE user_hash={PH} ORDER BY timestamp DESC LIMIT {int(limit)}",
                (_hash_user(user_id),),
            )
        else:
            c.execute(
                f"SELECT id, data, timestamp, file_hash FROM blood_tests WHERE user_hash={PH} AND member_id={PH} ORDER BY timestamp DESC LIMIT {int(limit)}",
                (_hash_user(user_id), int(member_id)),
            )
        rows = c.fetchall()
    finally:
        conn.close()
    out = []
    for row in rows:
        try:
            out.append({"id": row[0], "data": json.loads(row[1]), "timestamp": row[2] or "", "file_hash": row[3] or ""})
        except Exception:
            logging.getLogger(__name__).debug("Handled exception in get_blood_tests; fallback applied", exc_info=True)
            continue
    return out


def get_blood_test(user_id, blood_id):
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"SELECT id, data, file_hash FROM blood_tests WHERE user_hash={PH} AND id={PH}",
            (_hash_user(user_id), blood_id),
        )
        row = c.fetchone()
    finally:
        conn.close()
    if not row:
        return None
    try:
        return {"id": row[0], "data": json.loads(row[1]), "file_hash": row[2] or ""}
    except (TypeError, ValueError, OverflowError):
        logging.getLogger(__name__).debug("Handled exception in get_blood_test; fallback applied", exc_info=True)
        return None


def get_record_owned(user_id, record_id):
    """Return one analysis record only when it belongs to the supplied user."""
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"SELECT id, timestamp, lang, age, gender, symptoms, duration, severity, urgency, conditions, medications "
            f"FROM records WHERE user_hash={PH} AND id={PH} LIMIT 1",
            (_hash_user(user_id), int(record_id)),
        )
        r = c.fetchone()
    finally:
        conn.close()
    if not r:
        return None
    return {
        "id": r[0], "timestamp": r[1], "lang": r[2], "age": r[3], "gender": r[4],
        "symptoms": [x for x in (r[5] or "").split(",") if x], "duration": r[6],
        "severity": r[7], "urgency": r[8], "conditions": r[9] or "", "medications": r[10] or "",
    }


def save_symptom_relief_log(user_id, record_id, symptom_key, factor):
    """Store one user-observed relief factor once per analysis record."""
    conn = _conn()
    try:
        c = conn.cursor()
        values = (_hash_user(user_id), int(record_id), str(symptom_key)[:120], str(factor)[:40])
        c.execute(
            f"SELECT 1 FROM symptom_relief_logs WHERE user_hash={PH} AND record_id={PH} AND symptom_key={PH} AND factor={PH} LIMIT 1",
            values,
        )
        if c.fetchone():
            return False
        c.execute(
            f"INSERT INTO symptom_relief_logs (user_hash, record_id, symptom_key, factor, timestamp) VALUES ({PH},{PH},{PH},{PH},{PH})",
            values + (datetime.now(timezone.utc).isoformat(),),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def get_symptom_relief_summary(user_id, symptom_key):
    """Return factor counts for the same symptom key, scoped to one user."""
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"SELECT factor, COUNT(*) FROM symptom_relief_logs WHERE user_hash={PH} AND symptom_key={PH} GROUP BY factor ORDER BY COUNT(*) DESC, factor ASC",
            (_hash_user(user_id), str(symptom_key)[:120]),
        )
        rows = c.fetchall()
    finally:
        conn.close()
    return [{"factor": str(r[0]), "count": int(r[1])} for r in rows]


def _all_followups():
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            "SELECT id, record_id, timestamp, outcome FROM symptom_followups ORDER BY id"
        )
        return c.fetchall()
    finally:
        conn.close()


def _valid_checkin_date(value):
    text = str(value or "").strip()
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except (TypeError, ValueError, OverflowError):
        logging.getLogger(__name__).debug("Handled exception in _valid_checkin_date; fallback applied (handler 1621)")
        return None
    return text


# ---- Stable web daily tracking on the existing user_data table ----------------
# Railway installations from older releases can have different user_data layouts.
# In particular, some databases predate the updated_at column.  Daily tracking
# therefore detects the existing layout at runtime and never assumes that optional
# legacy columns exist.  This avoids requiring a migration just to use check-ins.
_WEB_CHECKIN_USERDATA_OFFSET = 1_000_000_000

def _web_checkin_storage_id(account_id):
    uid = int(account_id)
    if uid <= 0:
        raise ValueError("invalid account id")
    return -(_WEB_CHECKIN_USERDATA_OFFSET + uid)

def _clean_web_checkin_map(value):
    src = value if isinstance(value, dict) else {}
    out = {}
    for day, rating in src.items():
        day = _valid_checkin_date(day)
        try:
            rating = int(rating)
        except (TypeError, ValueError, OverflowError):
            logging.getLogger(__name__).debug("Handled exception in _clean_web_checkin_map; fallback applied (handler 1646)")
            continue
        if day and 1 <= rating <= 5:
            out[day] = rating
    return out

def _ensure_user_data_core(cursor):
    """Ensure only the tiny storage table required by daily tracking.

    This deliberately does not call init_db() or any unrelated migration. Older
    Railway databases can therefore use daily tracking even if a legacy table
    elsewhere in the project needs manual maintenance.
    """
    if USE_POSTGRES:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_data (
                user_id BIGINT PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at TEXT
            )
            """
        )
    else:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_data (
                user_id INTEGER PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at TEXT
            )
            """
        )

def _user_data_layout(cursor):
    """Return compatibility details for the existing user_data table.

    Detection follows PostgreSQL's active search_path instead of relying on
    current_schema(), because Railway databases can use a search path where the
    visible table is not reported by current_schema().
    """
    _ensure_user_data_core(cursor)
    if USE_POSTGRES:
        cursor.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name='user_data' AND table_schema = ANY(current_schemas(true))"
        )
        cols = {str(r[0]).lower(): str(r[1]).lower() for r in cursor.fetchall()}
        if not cols:
            # Last-resort introspection against the actually-resolved table.
            cursor.execute("SELECT * FROM user_data LIMIT 0")
            cols = {str(d[0]).lower(): '' for d in (cursor.description or [])}
    else:
        cursor.execute("PRAGMA table_info(user_data)")
        cols = {str(r[1]).lower(): str(r[2] or '').lower() for r in cursor.fetchall()}
    if 'user_id' not in cols or 'data' not in cols:
        raise RuntimeError('user_data schema is missing required columns')
    user_id_type = cols.get('user_id', '')
    data_type = cols.get('data', '')
    return {
        'has_updated_at': 'updated_at' in cols,
        'user_id_text': any(k in user_id_type for k in ('char', 'text', 'clob')),
        'data_json': 'json' in data_type,
    }

def _user_data_key(storage_id, layout):
    return str(storage_id) if layout.get('user_id_text') else storage_id

def _user_data_blob_param(payload, layout):
    if USE_POSTGRES and layout.get('data_json'):
        try:
            from psycopg2.extras import Json
            return Json(payload, dumps=lambda obj: json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
        except Exception:
            logging.getLogger(__name__).warning("Handled exception in _user_data_blob_param; fallback applied (handler 1719)")
            pass
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

def _decode_user_data_blob(raw):
    if isinstance(raw, dict):
        return raw
    if raw is None:
        return {}
    try:
        return json.loads(raw) or {}
    except (TypeError, ValueError, OverflowError):
        logging.getLogger(__name__).debug("Handled exception in _decode_user_data_blob; fallback applied (handler 1730)")
        return {}

def save_web_daily_checkin(account_id, severity, checkin_date=None):
    """Persist exactly one website check-in per account/day in existing user_data.

    Works with both legacy user_data(user_id,data) and the newer layout that also
    has updated_at. No daily-tracking schema migration is required.
    """
    rating = int(severity)
    if rating < 1 or rating > 5:
        raise ValueError("severity must be between 1 and 5")
    day = _valid_checkin_date(checkin_date) or datetime.now(timezone.utc).date().isoformat()
    storage_id = _web_checkin_storage_id(account_id)
    conn = _conn()
    try:
        c = conn.cursor()
        layout = _user_data_layout(c)
        storage_key = _user_data_key(storage_id, layout)
        now = datetime.now(timezone.utc).isoformat()
        empty_payload = {"kind": "symptosense_web_daily_tracking_v1", "checkins": {}}
        empty_blob = _user_data_blob_param(empty_payload, layout)
        if layout['has_updated_at']:
            c.execute(
                f"INSERT INTO user_data (user_id,data,updated_at) VALUES ({PH},{PH},{PH}) "
                "ON CONFLICT (user_id) DO NOTHING",
                (storage_key, empty_blob, now),
            )
        else:
            c.execute(
                f"INSERT INTO user_data (user_id,data) VALUES ({PH},{PH}) "
                "ON CONFLICT (user_id) DO NOTHING",
                (storage_key, empty_blob),
            )
        lock_suffix = " FOR UPDATE" if USE_POSTGRES else ""
        c.execute(f"SELECT data FROM user_data WHERE user_id={PH}" + lock_suffix, (storage_key,))
        row = c.fetchone()
        payload = _decode_user_data_blob(row[0] if row else None)
        checkins = _clean_web_checkin_map(payload.get("checkins"))
        created = day not in checkins
        checkins[day] = rating
        payload = {"kind": "symptosense_web_daily_tracking_v1", "checkins": checkins}
        blob = _user_data_blob_param(payload, layout)
        if layout['has_updated_at']:
            c.execute(
                f"UPDATE user_data SET data={PH}, updated_at={PH} WHERE user_id={PH}",
                (blob, now, storage_key),
            )
        else:
            c.execute(
                f"UPDATE user_data SET data={PH} WHERE user_id={PH}",
                (blob, storage_key),
            )
        conn.commit()
        return {"created": created, "date": day}
    except Exception:
        try:
            conn.rollback()
        except DB_ERRORS:
            logging.getLogger(__name__).warning("Handled exception in save_web_daily_checkin; fallback applied (handler 1788)")
            pass
        raise
    finally:
        conn.close()

def get_web_daily_checkin_history(account_id, limit=180):
    try:
        limit = max(1, min(365, int(limit)))
    except (TypeError, ValueError, OverflowError):
        logging.getLogger(__name__).debug("Handled exception in get_web_daily_checkin_history; fallback applied (handler 1797)")
        limit = 180
    storage_id = _web_checkin_storage_id(account_id)
    conn = _conn()
    try:
        c = conn.cursor()
        layout = _user_data_layout(c)
        storage_key = _user_data_key(storage_id, layout)
        # Only data is required. Do not SELECT updated_at because legacy Railway
        # databases may legitimately predate that optional column.
        c.execute(f"SELECT data FROM user_data WHERE user_id={PH}", (storage_key,))
        row = c.fetchone()
    finally:
        conn.close()
    if not row or row[0] is None:
        return []
    payload = _decode_user_data_blob(row[0])
    checkins = _clean_web_checkin_map(payload.get("checkins"))
    return [
        {"date": day, "value": checkins[day], "timestamp": None}
        for day in sorted(checkins, reverse=True)[:limit]
    ]

def get_web_daily_checkin_for_date(account_id, checkin_date):
    day = _valid_checkin_date(checkin_date)
    if not day:
        return None
    for item in get_web_daily_checkin_history(account_id, limit=365):
        if item["date"] == day:
            return item
    return None


def save_daily_checkin(user_id, severity, checkin_date=None):
    """Create or update exactly one daily check-in for an account/date."""
    ensure_daily_checkins_schema()
    rating = int(severity)
    if rating < 1 or rating > 5:
        raise ValueError("severity must be between 1 and 5")
    day = _valid_checkin_date(checkin_date) or datetime.now(timezone.utc).date().isoformat()
    user_hash = _hash_user(user_id)
    now = datetime.now(timezone.utc).isoformat()
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"SELECT 1 FROM ss_daily_checkins WHERE user_hash={PH} AND checkin_date={PH} LIMIT 1",
            (user_hash, day),
        )
        created = c.fetchone() is None
        c.execute(
            f"INSERT INTO ss_daily_checkins (user_hash,checkin_date,severity,updated_at) "
            f"VALUES ({PH},{PH},{PH},{PH}) "
            "ON CONFLICT(user_hash,checkin_date) DO UPDATE SET "
            "severity=excluded.severity,updated_at=excluded.updated_at",
            (user_hash, day, rating, now),
        )
        conn.commit()
        return {"created": created, "date": day}
    finally:
        conn.close()


def get_daily_checkin_for_date(user_id, checkin_date):
    ensure_daily_checkins_schema()
    day = _valid_checkin_date(checkin_date)
    if not day:
        return None
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"SELECT checkin_date,severity,updated_at FROM ss_daily_checkins "
            f"WHERE user_hash={PH} AND checkin_date={PH} LIMIT 1",
            (_hash_user(user_id), day),
        )
        row = c.fetchone()
        if not row:
            return None
        return {"date": str(row[0])[:10], "value": int(row[1]), "timestamp": row[2]}
    finally:
        conn.close()


def get_daily_checkin_history(user_id, limit=90):
    """Return newest-first daily rows for the signed-in account only."""
    ensure_daily_checkins_schema()
    try:
        limit = max(1, min(365, int(limit)))
    except (TypeError, ValueError, OverflowError):
        logging.getLogger(__name__).debug("Handled exception in get_daily_checkin_history; fallback applied (handler 1886)")
        limit = 90
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"SELECT checkin_date,severity,updated_at FROM ss_daily_checkins "
            f"WHERE user_hash={PH} ORDER BY checkin_date DESC LIMIT {int(limit)}",
            (_hash_user(user_id),),
        )
        rows = c.fetchall()
    finally:
        conn.close()
    return [
        {"date": str(day or '')[:10], "value": int(sev), "timestamp": ts}
        for day, sev, ts in rows
        if day
    ]


def get_daily_checkins(user_id, days=7):
    """Backward-compatible chart data: [(date, value), ...], oldest first."""
    try:
        days = max(1, min(365, int(days)))
    except (TypeError, ValueError, OverflowError):
        logging.getLogger(__name__).debug("Handled exception in get_daily_checkins; fallback applied (handler 1910)")
        days = 7
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=days - 1)).isoformat()
    rows = get_daily_checkin_history(user_id, limit=max(days * 3, 30))
    filtered = [(r["date"], r["value"]) for r in rows if r["date"] >= cutoff]
    filtered.sort(key=lambda x: x[0])
    return filtered


def add_med_reminder(user_id, med_name, time_utc, lang="ar"):
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"INSERT INTO med_reminders (user_id, med_name, time_utc, lang, active, created) "
            f"VALUES ({PH},{PH},{PH},{PH},1,{PH})",
            (user_id, med_name, time_utc, lang, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def remove_med_reminders(user_id):
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(f"UPDATE med_reminders SET active=0 WHERE user_id={PH}", (user_id,))
        conn.commit()
    finally:
        conn.close()


def get_active_med_reminders():
    """Returns [(user_id, med_name, time_utc, lang), ...] for active reminders."""
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            "SELECT user_id, med_name, time_utc, lang FROM med_reminders WHERE active=1 ORDER BY time_utc"
        )
        return c.fetchall()
    finally:
        conn.close()


def save_feedback(user_id, record_id, rating, comment=None, public_comment=False, reason_code=None, context=None):
    """Store explicit product feedback with bounded structured metadata.

    ``reason_code`` and ``context`` are controlled enums supplied by the server;
    they are intentionally not free-form health fields.
    """
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"INSERT INTO feedback (user_hash, record_id, rating, comment, public_comment, reason_code, context, timestamp) "
            f"VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})",
            (_hash_user(user_id), record_id, rating, comment, 1 if public_comment else 0, reason_code, context, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def feedback_reason_stats(limit=1000):
    """Aggregate structured feedback reasons for the Admin dashboard."""
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"SELECT COALESCE(reason_code,''), COUNT(*) FROM feedback "
            f"WHERE COALESCE(reason_code,'') <> '' GROUP BY reason_code ORDER BY COUNT(*) DESC LIMIT {PH}",
            (max(1, min(int(limit or 1000), 5000)),),
        )
        rows = c.fetchall()
    finally:
        conn.close()
    return [{"reason": str(r[0]), "count": int(r[1] or 0)} for r in rows]


def _feedback_star_value(raw_rating):
    """Normalize feedback to 1–5 while preserving legacy yes/no rows."""
    value = str(raw_rating or "").strip().lower()
    if value.startswith("star:"):
        try:
            n = int(value.split(":", 1)[1])
            return n if 1 <= n <= 5 else None
        except (TypeError, ValueError, OverflowError):
            logging.getLogger(__name__).debug("Handled exception in _feedback_star_value; fallback applied (handler 1976)")
            return None
    if value in {"great", "1"}: return 5
    if value in {"good", "2"}: return 4
    if value in {"ok", "3"}: return 3
    if value in {"bad", "4"}: return 1
    if value == "5": return 5
    return None

def feedback_counts():
    rows = fetchall("SELECT rating FROM feedback")
    stars = [_feedback_star_value(r[0]) for r in rows]
    stars = [n for n in stars if n is not None]
    distribution = {str(i): stars.count(i) for i in range(1, 6)}
    return {
        "great": distribution["5"], "good": distribution["4"], "ok": distribution["3"],
        "bad": distribution["1"] + distribution["2"], "total": len(stars),
        "average_5": round(sum(stars) / len(stars), 1) if stars else 0.0,
        "distribution": distribution,
    }

def feedback_comments(limit=100, public_only=False):
    """Anonymous comment rows. Public comments require explicit opt-in."""
    conn = _conn()
    try:
        c = conn.cursor()
        where = "WHERE comment IS NOT NULL AND TRIM(comment) <> ''"
        if public_only:
            where += " AND COALESCE(public_comment,0)=1"
        c.execute(f"SELECT comment, rating, timestamp FROM feedback {where} ORDER BY id DESC LIMIT {PH}", (max(1, min(int(limit), 200)),))
        rows = c.fetchall()
    finally:
        conn.close()
    return [{"comment":r[0] or "", "rating":_feedback_star_value(r[1]), "timestamp":r[2]} for r in rows]

def public_site_summary(comment_limit=8):
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM ss_users WHERE COALESCE(role,'user') <> 'admin'")
        row = c.fetchone(); users = int(row[0] if row else 0)
        c.execute("SELECT COUNT(*) FROM feedback WHERE comment IS NOT NULL AND TRIM(comment) <> '' AND COALESCE(public_comment,0)=1")
        row = c.fetchone(); comment_count = int(row[0] if row else 0)
    finally:
        conn.close()
    fb = feedback_counts()
    return {
        "users": users,
        "ratings": int(fb.get("total") or 0),
        "average_5": float(fb.get("average_5") or 0),
        "comment_count": comment_count,
        "comments": feedback_comments(comment_limit, public_only=True) if comment_limit else [],
    }

def update_feedback_comment(user_id, record_id, comment):
    """Attaches a free-text comment to the latest feedback row for this record."""
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"UPDATE feedback SET comment={PH} WHERE user_hash={PH} AND record_id={PH} "
            f"AND (comment IS NULL OR comment = '')",
            (comment, _hash_user(user_id), record_id),
        )
        conn.commit()
    finally:
        conn.close()


def save_assistant_feedback(user_id, message, rating, reason=None):
    """Store aggregate assistant feedback without chat/reply free text."""
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"INSERT INTO assistant_feedback (user_hash, message, rating, reason, timestamp) "
            f"VALUES ({PH},{PH},{PH},{PH},{PH})",
            (_hash_user(user_id), None, rating, reason,
             datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def assistant_feedback_stats():
    """Aggregate assistant feedback for the dashboard."""
    conn = _conn()
    try:
        c = conn.cursor()

        def _count(sql):
            c.execute(sql)
            row = c.fetchone()
            return row[0] if row else 0

        total = _count("SELECT COUNT(*) FROM assistant_feedback")
        useful = _count("SELECT COUNT(*) FROM assistant_feedback WHERE rating = 1")
        partial = _count("SELECT COUNT(*) FROM assistant_feedback WHERE rating = 2")
        not_useful = _count("SELECT COUNT(*) FROM assistant_feedback WHERE rating = 0")
        c.execute(
            "SELECT reason, COUNT(*) FROM assistant_feedback "
            "WHERE rating = 0 AND reason IS NOT NULL AND reason != '' "
            "GROUP BY reason ORDER BY COUNT(*) DESC"
        )
        reasons = c.fetchall()
    finally:
        conn.close()
    satisfaction = int(round((useful + 0.5 * partial) / total * 100)) if total else 0
    return {
        "total": total,
        "useful": useful,
        "partial": partial,
        "not_useful": not_useful,
        "satisfaction": satisfaction,
        "reasons": [{"reason": r, "count": n} for r, n in reasons],
    }


def _all_feedback():
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute("SELECT id, record_id, timestamp, rating, comment FROM feedback ORDER BY id")
        return c.fetchall()
    finally:
        conn.close()


def get_trends(days=7):
    conn = _conn()
    try:
        c = conn.cursor()
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        c.execute(f"SELECT symptoms FROM records WHERE timestamp >= {PH}", (since,))
        rows = c.fetchall()
    finally:
        conn.close()
    counter = Counter()
    for (symptoms_str,) in rows:
        for s in symptoms_str.split(","):
            s = s.strip()
            if s:
                counter[s] += 1
    return counter, len(rows)


# ---- Family Health Hub & Medication Companion ----

def save_member(user_id, relation, name, age, gender, conditions="", medications="", allergies="", notes=""):
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"INSERT INTO family_members (user_hash, relation, name, age, gender, conditions, medications, allergies, notes, created) "
            f"VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})",
            (_hash_user(user_id), relation, name, age or "", gender or "", conditions or "",
             medications or "", allergies or "", notes or "",
             datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        if USE_POSTGRES:
            c.execute("SELECT lastval()")
            return c.fetchone()[0]
        return c.lastrowid
    finally:
        conn.close()


def list_members(user_id):
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"SELECT id, relation, name, age, gender, conditions, medications, allergies, notes, created "
            f"FROM family_members WHERE user_hash={PH} ORDER BY id",
            (_hash_user(user_id),),
        )
        rows = c.fetchall()
    finally:
        conn.close()
    return [
        {
            "id": r[0], "relation": r[1] or "", "name": r[2],
            "age": r[3] or "", "gender": r[4] or "",
            "conditions": r[5] or "", "medications": r[6] or "",
            "allergies": r[7] or "", "notes": r[8] or "", "created": r[9] or "",
        }
        for r in rows
    ]


def get_member(user_id, member_id):
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"SELECT id, relation, name, age, gender, conditions, medications, allergies, notes, created "
            f"FROM family_members WHERE user_hash={PH} AND id={PH}",
            (_hash_user(user_id), int(member_id)),
        )
        row = c.fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return {
        "id": row[0], "relation": row[1] or "", "name": row[2],
        "age": row[3] or "", "gender": row[4] or "",
        "conditions": row[5] or "", "medications": row[6] or "",
        "allergies": row[7] or "", "notes": row[8] or "", "created": row[9] or "",
    }


def update_member(user_id, member_id, relation, name, age, gender, conditions="", medications="", allergies="", notes=""):
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"UPDATE family_members SET relation={PH}, name={PH}, age={PH}, gender={PH}, "
            f"conditions={PH}, medications={PH}, allergies={PH}, notes={PH} "
            f"WHERE user_hash={PH} AND id={PH}",
            (relation, name, age or "", gender or "", conditions or "", medications or "",
             allergies or "", notes or "", _hash_user(user_id), int(member_id)),
        )
        conn.commit()
    finally:
        conn.close()


def delete_member(user_id, member_id):
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"DELETE FROM family_members WHERE user_hash={PH} AND id={PH}",
            (_hash_user(user_id), int(member_id)),
        )
        conn.commit()
    finally:
        conn.close()

def save_med_plan(user_id, member_id, med_name, times, dose="", days=None, start_date=None, frequency="daily"):
    import json as _json
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"INSERT INTO med_plans (user_hash, member_id, med_name, dose, times, frequency, start_date, days, active, created) "
            f"VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},1,{PH})",
            (_hash_user(user_id), int(member_id or 0), med_name, dose or "",
             _json.dumps(times, ensure_ascii=False), frequency,
             start_date or datetime.now(timezone.utc).date().isoformat(),
             int(days) if days else None,
             datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        if USE_POSTGRES:
            c.execute("SELECT lastval()")
            return c.fetchone()[0]
        return c.lastrowid
    finally:
        conn.close()


def list_med_plans(user_id, member_id=None, active_only=False):
    import json as _json
    conn = _conn()
    try:
        c = conn.cursor()
        if member_id is None:
            c.execute(
                f"SELECT id, member_id, med_name, dose, times, frequency, start_date, days, active, created "
                f"FROM med_plans WHERE user_hash={PH} ORDER BY id",
                (_hash_user(user_id),),
            )
        else:
            c.execute(
                f"SELECT id, member_id, med_name, dose, times, frequency, start_date, days, active, created "
                f"FROM med_plans WHERE user_hash={PH} AND member_id={PH} ORDER BY id",
                (_hash_user(user_id), int(member_id)),
            )
        rows = c.fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        try:
            times = _json.loads(r[4])
        except (TypeError, ValueError, OverflowError):
            logging.getLogger(__name__).debug("Handled exception in list_med_plans; fallback applied (handler 2264)")
            times = []
        plan = {
            "id": r[0], "member_id": r[1], "med_name": r[2], "dose": r[3] or "",
            "times": times, "frequency": r[5] or "daily", "start_date": r[6] or "",
            "days": r[7], "active": bool(r[8]), "created": r[9] or "",
        }
        if active_only and not plan["active"]:
            continue
        out.append(plan)
    return out


def delete_med_plan(user_id, plan_id):
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"UPDATE med_plans SET active=0 WHERE user_hash={PH} AND id={PH}",
            (_hash_user(user_id), int(plan_id)),
        )
        conn.commit()
    finally:
        conn.close()


def log_med_status(user_id, member_id, plan_id, log_date, log_time, status):
    owner = _hash_user(user_id)
    conn = _conn()
    try:
        c = conn.cursor()
        # Keep occurrence replacement tenant-scoped even if a stale/corrupt row
        # happens to reuse the same plan/date/time tuple.
        c.execute(
            f"DELETE FROM med_logs WHERE user_hash={PH} AND plan_id={PH} AND log_date={PH} AND log_time={PH}",
            (owner, int(plan_id), log_date, log_time),
        )
        c.execute(
            f"INSERT INTO med_logs (user_hash, member_id, plan_id, log_date, log_time, status, created) "
            f"VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH})",
            (owner, int(member_id or 0), int(plan_id), log_date, log_time, status,
             datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def get_med_logs(user_id, plan_id=None, log_date=None):
    conn = _conn()
    try:
        c = conn.cursor()
        if plan_id is not None and log_date is not None:
            c.execute(
                f"SELECT plan_id, log_date, log_time, status FROM med_logs "
                f"WHERE user_hash={PH} AND plan_id={PH} AND log_date={PH}",
                (_hash_user(user_id), int(plan_id), log_date),
            )
        elif log_date is not None:
            c.execute(
                f"SELECT plan_id, log_date, log_time, status FROM med_logs "
                f"WHERE user_hash={PH} AND log_date={PH}",
                (_hash_user(user_id), log_date),
            )
        else:
            c.execute(
                f"SELECT plan_id, log_date, log_time, status FROM med_logs "
                f"WHERE user_hash={PH}",
                (_hash_user(user_id),),
            )
        rows = c.fetchall()
    finally:
        conn.close()
    return [{"plan_id": r[0], "log_date": r[1], "log_time": r[2], "status": r[3]} for r in rows]


def med_plans_today(user_id):
    """Active plans joined with today's (UTC) log entries."""
    plans = list_med_plans(user_id, active_only=True)
    today = datetime.now(timezone.utc).date().isoformat()
    logs = get_med_logs(user_id, log_date=today)
    log_map = {}
    for l in logs:
        log_map.setdefault((l["plan_id"], l["log_time"]), l["status"])
    out = []
    for p in plans:
        # duration check
        if p["days"]:
            try:
                end = datetime.strptime(p["start_date"], "%Y-%m-%d").date() + timedelta(days=int(p["days"]))
                if datetime.now(timezone.utc).date() > end:
                    continue
            except Exception:
                logging.getLogger(__name__).debug("Handled exception in med_plans_today; fallback applied (handler 2353)")
                pass
        out.append({
            "id": p["id"], "member_id": p["member_id"], "med_name": p["med_name"],
            "dose": p["dose"], "times": p["times"],
            "status": {t: log_map.get((p["id"], t), "") for t in p["times"]},
        })
    return out


def med_adherence(user_id, member_id=None, days=7):
    """Returns {percent, taken, expected, days} for the last N days."""
    plans = list_med_plans(user_id, member_id=member_id, active_only=False)
    if not plans:
        return {"percent": None, "taken": 0, "expected": 0, "days": days}
    logs = get_med_logs(user_id)
    log_keys = {(l["plan_id"], l["log_date"], l["log_time"]): l["status"] for l in logs}
    today = datetime.now(timezone.utc).date()
    taken = expected = 0
    for p in plans:
        if not p["active"] and p["days"]:
            # skip finished plans for the "expected" count
            continue
        try:
            start = datetime.strptime(p["start_date"], "%Y-%m-%d").date()
        except (TypeError, ValueError, OverflowError):
            logging.getLogger(__name__).debug("Handled exception in med_adherence; fallback applied (handler 2378)")
            start = today
        end = today
        if p["days"]:
            try:
                end = min(end, start + timedelta(days=int(p["days"]) - 1))
            except Exception:
                logging.getLogger(__name__).debug("Handled exception in med_adherence; fallback applied (handler 2384)")
                pass
        day_lo = max(start, today - timedelta(days=days - 1))
        for i in range((end - day_lo).days + 1):
            day = day_lo + timedelta(days=i)
            ds = day.isoformat()
            for t in p["times"]:
                expected += 1
                if log_keys.get((p["id"], ds, t)) == "taken":
                    taken += 1
    percent = round((taken * 100.0) / expected, 1) if expected else 0.0
    return {"percent": percent, "taken": taken, "expected": expected, "days": days}


def member_timeline(user_id, member_id, days=30):
    """Merges records + blood tests + med plan events into a reverse-chronological list."""
    events = []
    since = (datetime.now(timezone.utc) - timedelta(days=int(days))).isoformat()
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"SELECT id, timestamp, symptoms FROM records WHERE user_hash={PH} AND member_id={PH} AND timestamp >= {PH}",
            (_hash_user(user_id), int(member_id), since),
        )
        for rid, ts, syms in c.fetchall():
            events.append({
                "date": (ts or "")[:10], "type": "analysis",
                "title": "تحليل أعراض", "en_title": "Symptom analysis",
                "detail": ", ".join([s for s in (syms or "").split(",") if s])[:80],
                "id": rid,
            })
        c.execute(
            f"SELECT id, timestamp FROM blood_tests WHERE user_hash={PH} AND member_id={PH} AND timestamp >= {PH}",
            (_hash_user(user_id), int(member_id), since),
        )
        for bid, ts in c.fetchall():
            events.append({
                "date": (ts or "")[:10], "type": "blood",
                "title": "فحص CBC", "en_title": "CBC test",
                "detail": "", "id": bid,
            })
    finally:
        conn.close()
    for p in list_med_plans(user_id, member_id=member_id):
        events.append({
            "date": (p["start_date"] or "")[:10], "type": "med",
            "title": "دواء: " + p["med_name"], "en_title": "Medication: " + p["med_name"],
            "detail": ", ".join(p["times"]),
        })
    events.sort(key=lambda e: e["date"], reverse=True)
    return events


# ---- Persistent user/conversation state (survives bot restarts) ----

def save_user_data(user_id, data):
    conn = _conn()
    try:
        c = conn.cursor()
        blob = json.dumps(data, ensure_ascii=False)
        now = datetime.now(timezone.utc).isoformat()
        c.execute(
            f"INSERT INTO user_data (user_id, data, updated_at) VALUES ({PH},{PH},{PH}) "
            f"ON CONFLICT (user_id) DO UPDATE SET data={PH}, updated_at={PH}",
            (user_id, blob, now, blob, now),
        )
        conn.commit()
    finally:
        conn.close()


def load_user_data(user_id):
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(f"SELECT data FROM user_data WHERE user_id={PH}", (user_id,))
        row = c.fetchone()
        if not row or not row[0]:
            return {}
        return json.loads(row[0])
    finally:
        conn.close()


def clear_user_data(user_id):
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(f"DELETE FROM user_data WHERE user_id={PH}", (user_id,))
        conn.commit()
    finally:
        conn.close()


def all_user_data():
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute("SELECT user_id, data FROM user_data")
        out = {}
        for user_id, blob in c.fetchall():
            try:
                out[user_id] = json.loads(blob)
            except (TypeError, ValueError, OverflowError):
                logging.getLogger(__name__).debug("Handled exception in all_user_data; fallback applied (handler 2487)")
                continue
        return out
    finally:
        conn.close()


def save_conversation(name, key, state):
    conn = _conn()
    try:
        c = conn.cursor()
        name_key = name if name is not None else "default"
        state_blob = json.dumps(state, ensure_ascii=False) if state is not None else None
        key_blob = json.dumps(key, ensure_ascii=False)
        c.execute(
            f"INSERT INTO conversations (name, key, state) VALUES ({PH},{PH},{PH}) "
            f"ON CONFLICT (name, key) DO UPDATE SET state={PH}",
            (name_key, key_blob, state_blob, state_blob),
        )
        conn.commit()
    finally:
        conn.close()


def all_conversations():
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute("SELECT name, key, state FROM conversations")
        out = {}
        for name, key_blob, state_blob in c.fetchall():
            conv_name = None if name == "default" else name
            key = tuple(json.loads(key_blob))
            state = json.loads(state_blob) if state_blob else None
            out.setdefault(conv_name, {})[key] = state
        return out
    finally:
        conn.close()


# ---- SymptoSense Smart Account System ----

import re as _re

_ADMIN_ROLES = {"admin"}


def _email_set(env_name):
    return {
        value.strip().lower()
        for value in os.environ.get(env_name, "").split(",")
        if value.strip()
    }


def configured_admin_role(email):
    """Legacy compatibility hook.

    Admin access is no longer derived from email allowlists.  The only
    authoritative value is the persisted ``ss_users.role`` column, and the
    first owner is promoted through the one-time, authenticated claim flow.
    """
    return "user"

def _hash_password(password):
    """Hash a password with a unique salt and a deliberately slow KDF."""
    iterations = 600_000
    salt = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac(
        "sha256", (password or "").encode("utf-8"), bytes.fromhex(salt), iterations
    ).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def _verify_password(password, stored_hash):
    """Return ``(valid, needs_upgrade)`` and keep old accounts working."""
    stored_hash = stored_hash or ""
    if stored_hash.startswith("pbkdf2_sha256$"):
        try:
            _, iterations, salt, expected = stored_hash.split("$", 3)
            actual = hashlib.pbkdf2_hmac(
                "sha256",
                (password or "").encode("utf-8"),
                bytes.fromhex(salt),
                int(iterations),
            ).hex()
            return hmac.compare_digest(actual, expected), False
        except (TypeError, ValueError):
            return False, False

    # Backward compatibility for accounts created by older releases.
    legacy_salt = os.environ.get("HASH_SALT", "symptosense")
    legacy = hashlib.sha256(f"{legacy_salt}:{password or ''}".encode()).hexdigest()
    valid = hmac.compare_digest(legacy, stored_hash)
    return valid, valid


def create_ss_user(email, name, password):
    """Create a new user account. Returns (user_id, error_message)."""
    email = (email or "").strip().lower()
    name = (name or "").strip()
    password = password or ""
    if not email or len(email) > 254 or not _re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        return None, "invalid_email"
    if not name or len(name) < 2 or len(name) > 100:
        return None, "invalid_name"
    if len(password) < 8:
        return None, "password_too_short"
    if len(password) > 256:
        return None, "password_too_long"
    # The designated owner must already exist. Never create a replacement Admin
    # account if that production account is missing.
    if email == OWNER_ADMIN_EMAIL:
        existing = get_ss_user_by_email(email)
        if not existing:
            return None, "owner_account_must_exist"
    conn = _conn()
    try:
        c = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        pw_hash = _hash_password(password)
        role = "user"
        if USE_POSTGRES:
            c.execute(
                "INSERT INTO ss_users (email, name, password_hash, role, email_verified, email_verified_at, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (email, name, pw_hash, role, 0, None, now),
            )
            user_id = c.fetchone()[0]
        else:
            c.execute(
                "INSERT INTO ss_users (email, name, password_hash, role, email_verified, email_verified_at, created_at) VALUES (?,?,?,?,?,?,?)",
                (email, name, pw_hash, role, 0, None, now),
            )
            user_id = c.lastrowid
        conn.commit()
        return user_id, None
    except Exception as exc:
        # Only a real uniqueness violation means the email already exists.
        # Other database failures must not be disguised as an account state.
        is_unique = isinstance(exc, sqlite3.IntegrityError) and "unique" in str(exc).lower()
        if USE_POSTGRES:
            is_unique = is_unique or getattr(exc, "pgcode", None) == "23505"
        if is_unique:
            return None, "email_exists"
        logging.getLogger(__name__).exception("create_ss_user database failure")
        return None, "database_error"
    finally:
        conn.close()


def authenticate_ss_user_status(email, password):
    """Authenticate without exposing password material.

    Returns a small status dict so the UI can distinguish a missing account,
    invalid credentials, disabled account, and an unverified email.  last_login
    is updated only after the account is verified and authentication succeeds.
    """
    email = (email or "").strip().lower()
    password = password or ""
    if len(email) > 254 or len(password) > 256:
        return {"ok": False, "error": "incorrect_credentials"}
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            "SELECT id, password_hash, status, COALESCE(email_verified,1) FROM ss_users WHERE lower(email)=%s" % PH,
            (email,),
        )
        row = c.fetchone()
        if not row:
            # Generic credentials response prevents account enumeration.
            return {"ok": False, "error": "incorrect_credentials"}
        user_id, stored_hash, status, email_verified = row
        # Always verify the password before exposing any account-state-specific
        # outcome. Otherwise a disabled account can be enumerated with a wrong
        # password because its response differs from a missing account.
        valid, needs_upgrade = _verify_password(password, stored_hash)
        if not valid:
            return {"ok": False, "error": "incorrect_credentials"}
        if (status or "active") != "active":
            return {"ok": False, "error": "account_unavailable"}
        if not bool(email_verified):
            return {"ok": False, "error": "verification_required", "user_id": int(user_id)}
        now = datetime.now(timezone.utc).isoformat()
        if needs_upgrade:
            c.execute(
                "UPDATE ss_users SET password_hash=%s, last_login=%s WHERE id=%s" % (PH, PH, PH),
                (_hash_password(password), now, user_id),
            )
        else:
            c.execute("UPDATE ss_users SET last_login=%s WHERE id=%s" % (PH, PH), (now, user_id))
        conn.commit()
        return {"ok": True, "user_id": int(user_id)}
    finally:
        conn.close()


def authenticate_ss_user(email, password):
    """Backward-compatible authentication helper returning user_id or None."""
    result = authenticate_ss_user_status(email, password)
    return result.get("user_id") if result.get("ok") else None


def change_ss_user_password(user_id, current_password, new_password):
    """Change a signed-in account password after verifying the current value.

    Password material is never logged or returned.  The same slow PBKDF2 format
    used by account creation is applied to the replacement password.
    """
    if not user_id:
        return False, "login_required"
    if len(new_password or "") < 8:
        return False, "password_too_short"
    if len(new_password or "") > 256 or len(current_password or "") > 256:
        return False, "password_too_long"
    if hmac.compare_digest(str(current_password or ""), str(new_password or "")):
        return False, "new_password_must_differ"
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute("SELECT password_hash,status FROM ss_users WHERE id=%s" % PH, (int(user_id),))
        row = c.fetchone()
        if not row or (row[1] or "active") != "active":
            return False, "account_unavailable"
        valid, _ = _verify_password(current_password, row[0])
        if not valid:
            return False, "current_password_incorrect"
        c.execute(
            "UPDATE ss_users SET password_hash=%s WHERE id=%s" % (PH, PH),
            (_hash_password(new_password), int(user_id)),
        )
        conn.commit()
        return True, None
    finally:
        conn.close()


def verify_ss_user_password(user_id, password):
    """Verify the current password for an active signed-in user.

    This helper is intentionally small and never returns password material. It is
    used by destructive Admin actions that require an extra confirmation step.
    """
    if not user_id or not password or len(str(password)) > 256:
        return False
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute("SELECT password_hash,status FROM ss_users WHERE id=%s" % PH, (int(user_id),))
        row = c.fetchone()
        if not row or (row[1] or "active") != "active":
            return False
        valid, _ = _verify_password(password, row[0])
        return bool(valid)
    finally:
        conn.close()




def admin_symptom_trial_rows():
    """Return privacy-safe symptom-analysis fields for the Admin Excel export.

    ``records`` remains the primary source. V212 also reads the owned result JSON
    as a recovery source for legacy rows whose ``records.symptoms`` value is
    unexpectedly blank. This prevents a completed assessment from disappearing
    from the export just because one historical column was incomplete.
    """
    init_db()
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            "SELECT r.age, r.gender, r.symptoms, r.duration, res.data "
            "FROM records r "
            "LEFT JOIN results res ON res.record_id=r.id AND res.user_hash=r.user_hash "
            "ORDER BY r.timestamp DESC, r.id DESC"
        )
        raw_rows = c.fetchall()
    finally:
        conn.close()

    def _gender(value):
        raw = str(value or '').strip().lower()
        if raw in {'f', 'female', 'أنثى'}:
            return 'Female | أنثى'
        if raw in {'m', 'male', 'ذكر'}:
            return 'Male | ذكر'
        return str(value or '').strip()

    def _coerce_symptom_list(value):
        if isinstance(value, (list, tuple)):
            return [str(x).strip() for x in value if str(x).strip()]
        text = str(value or '').strip()
        if not text:
            return []
        # records.symptoms has historically been comma-separated. Accept Arabic
        # comma/newline/pipe separators too so custom symptoms are not lost.
        for sep in ('،', '\n', ' • ', '||'):
            text = text.replace(sep, ',')
        return [part.strip() for part in text.split(',') if part.strip()]

    def _recover_from_result(raw):
        try:
            data = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except (TypeError, ValueError, OverflowError):
            data = {}
        if not isinstance(data, dict):
            return []
        snapshot = data.get('input_snapshot') if isinstance(data.get('input_snapshot'), dict) else {}
        candidates = _coerce_symptom_list(snapshot.get('symptoms')) or _coerce_symptom_list(data.get('symptoms'))
        if candidates:
            return candidates
        # Older saved results already carry symptom_normalization. Reconstruct the
        # user's reported terms from canonical.original + unmatched when possible.
        norm = data.get('symptom_normalization') if isinstance(data.get('symptom_normalization'), dict) else {}
        recovered = []
        for item in norm.get('canonical') or []:
            if isinstance(item, dict):
                value = str(item.get('original') or item.get('name_ar') or item.get('name_en') or item.get('slug') or '').strip()
                if value and value not in recovered:
                    recovered.append(value)
        for item in norm.get('unmatched') or []:
            value = str(item or '').strip()
            if value and value not in recovered:
                recovered.append(value)
        return recovered

    rows = []
    for row in raw_rows:
        symptoms = _coerce_symptom_list(row[2])
        if not symptoms:
            symptoms = _recover_from_result(row[4])
        if not symptoms:
            # A symptom trial without any recoverable symptom is not useful in
            # the requested workbook, but valid completed analyses no longer get
            # dropped when the legacy records column alone is blank.
            continue
        rows.append({
            'age': row[0] if row[0] is not None else '',
            'gender': _gender(row[1]),
            'symptoms': ' • '.join(symptoms),
            'duration': str(row[3] or '').strip(),
        })
    return rows


def admin_symptom_trial_summary():
    """Privacy-safe counts matching the actual symptom-trial Excel export."""
    rows = admin_symptom_trial_rows()
    # Distinct tester count cannot be reconstructed from the privacy-safe row list,
    # so retain an account-safe DB count across records while the saved analysis
    # count exactly matches the exportable rows.
    init_db()
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute("SELECT COUNT(DISTINCT user_hash) FROM records")
        row = c.fetchone() or (0,)
        testers = max(0, int(row[0] or 0))
    finally:
        conn.close()
    return {'saved_analyses': len(rows), 'distinct_testers': testers}


def admin_export_symptom_trials_xlsx():
    """Create a minimal Excel-safe workbook with only requested trial fields."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    except ImportError as exc:
        raise RuntimeError('xlsx_export_dependency_missing') from exc

    rows=admin_symptom_trial_rows()
    wb=openpyxl.Workbook()
    ws=wb.active
    ws.title='Symptom Trials'
    ws.sheet_state='visible'
    ws.sheet_view.showGridLines=True
    ws.sheet_view.zoomScale=100
    ws.sheet_view.zoomScaleNormal=100

    navy='173B57'; blue='2F6F9F'; pale='EAF4FB'; soft='F7FAFC'
    white='FFFFFF'; muted='687B88'; text='233746'; line='D7E3EB'
    thin=Side(style='thin',color=line)

    # Maximum compatibility: no merged ranges, tables, filters, freeze panes,
    # formulas, print titles, charts, or external links.
    for col in range(1,5):
        cell=ws.cell(1,col)
        cell.fill=PatternFill('solid',fgColor=pale)
        cell.border=Border(bottom=thin)
    ws['A1']='SymptoSense — Symptom Analysis Trials | تجارب تحليل الأعراض'
    ws['A1'].font=Font(name='Calibri',size=16,bold=True,color=navy)
    ws['A1'].alignment=Alignment(vertical='center')
    ws.row_dimensions[1].height=28

    ws['A2']=f'Saved analyses | التحليلات المحفوظة: {len(rows)}'
    ws['A2'].font=Font(name='Calibri',size=10,color=muted)
    ws['C2']='Fields | الحقول: Age, Gender, Symptoms, Duration'
    ws['C2'].font=Font(name='Calibri',size=10,color=muted)

    headers=['Age | العمر','Gender | الجنس','Symptoms | الأعراض','Duration | المدة']
    for idx,label in enumerate(headers,start=1):
        cell=ws.cell(4,idx,label)
        cell.fill=PatternFill('solid',fgColor=blue)
        cell.font=Font(name='Calibri',size=10,bold=True,color=white)
        cell.alignment=Alignment(horizontal='center',vertical='center',wrap_text=True)
        cell.border=Border(left=thin,right=thin,top=thin,bottom=thin)
    ws.row_dimensions[4].height=30

    if rows:
        for r_idx,item in enumerate(rows,start=5):
            values=[item['age'],item['gender'],item['symptoms'],item['duration']]
            for c_idx,value in enumerate(values,start=1):
                cell=ws.cell(r_idx,c_idx,value)
                cell.font=Font(name='Calibri',size=10,color=text)
                cell.alignment=Alignment(
                    horizontal='center' if c_idx in (1,2,4) else 'left',
                    vertical='center',wrap_text=True
                )
                cell.border=Border(bottom=Side(style='hair',color='E7EEF4'))
                if r_idx % 2 == 0:
                    cell.fill=PatternFill('solid',fgColor=soft)
            ws.row_dimensions[r_idx].height=26
    else:
        ws['A5']='No saved symptom analyses found. | لا توجد تحليلات أعراض محفوظة.'
        ws['A5'].font=Font(name='Calibri',size=11,italic=True,color=muted)
        ws['A5'].alignment=Alignment(vertical='center',wrap_text=True)
        for col in range(1,5):
            cell=ws.cell(5,col)
            cell.fill=PatternFill('solid',fgColor=soft)
            cell.border=Border(top=thin,bottom=thin)
        ws.row_dimensions[5].height=34

    for col,width in {'A':14,'B':20,'C':58,'D':24}.items():
        ws.column_dimensions[col].width=width

    wb.active=0
    buf=io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def admin_clear_symptom_trials():
    """Delete saved symptom-analysis trials without deleting accounts or CBC data."""
    init_db()
    conn = _conn()
    try:
        c = conn.cursor()
        if USE_POSTGRES:
            c.execute("SELECT tablename FROM pg_tables WHERE schemaname = current_schema()")
            existing = {str(r[0]) for r in c.fetchall()}
        else:
            c.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing = {str(r[0]) for r in c.fetchall()}

        c.execute("SELECT COUNT(*), COUNT(DISTINCT user_hash) FROM records")
        row = c.fetchone() or (0, 0)
        saved = max(0, int(row[0] or 0))
        testers = max(0, int(row[1] or 0))

        # Clear only analysis-linked data. User accounts, profiles, medications,
        # CBC uploads, knowledge content, and unrelated feedback are preserved.
        if 'ss_analysis_links' in existing:
            c.execute('DELETE FROM ss_analysis_links')
        if 'symptom_relief_logs' in existing:
            c.execute('DELETE FROM symptom_relief_logs')
        if 'followups' in existing:
            c.execute('DELETE FROM followups')
        if 'feedback' in existing:
            c.execute('DELETE FROM feedback WHERE record_id IS NOT NULL')
        if 'results' in existing:
            c.execute('DELETE FROM results')
        if 'records' in existing:
            c.execute('DELETE FROM records')

        conn.commit()
        return {
            'deleted_analyses': saved,
            'affected_testers': testers,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def admin_blood_test_trial_summary():
    """Return privacy-safe counts for saved CBC/lab-test trials.

    No user hashes or health values are returned to the Admin UI.
    """
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute("SELECT COUNT(*), COUNT(DISTINCT user_hash) FROM blood_tests")
        row = c.fetchone() or (0, 0)
        return {
            "saved_tests": max(0, int(row[0] or 0)),
            "distinct_testers": max(0, int(row[1] or 0)),
        }
    finally:
        conn.close()




def admin_blood_collection_summary():
    """Counts matching the consent-filtered blood-analysis Excel collection."""
    init_db()
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute("SELECT user_hash, data FROM blood_tests")
        raw_rows = c.fetchall()
    finally:
        conn.close()
    saved = 0
    testers = set()
    for user_hash, raw in raw_rows:
        try:
            data = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except (TypeError, ValueError, OverflowError):
            continue
        if isinstance(data, dict) and data.get('blood_collection_consent') is True:
            saved += 1
            testers.add(str(user_hash or ''))
    return {'saved_tests': saved, 'distinct_testers': len(testers)}


def admin_blood_collection_rows():
    """Return privacy-safe rows for the Admin blood-analysis collection file.

    Only blood analyses saved after explicit blood_collection_consent are
    included. Direct user identifiers are never exported.
    """
    init_db()
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute("SELECT data FROM blood_tests ORDER BY timestamp DESC, id DESC")
        raw_rows = c.fetchall()
    finally:
        conn.close()

    def _gender(value):
        raw = str(value or '').strip().lower()
        if raw in {'f', 'female', 'أنثى'}:
            return 'Female | أنثى'
        if raw in {'m', 'male', 'ذكر'}:
            return 'Male | ذكر'
        return ''

    rows = []
    for raw_row in raw_rows:
        raw = raw_row[0] if raw_row else None
        try:
            data = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except (TypeError, ValueError, OverflowError):
            continue
        if not isinstance(data, dict):
            continue
        # V147+: participation in this Admin collection requires the explicit
        # blood-analysis collection consent shown before upload/analysis.
        if data.get('blood_collection_consent') is not True:
            continue

        indicators = data.get('indicators') if isinstance(data.get('indicators'), list) else []
        low_items = []
        for item in indicators:
            if not isinstance(item, dict) or str(item.get('status') or '').lower() != 'low':
                continue
            name = str(item.get('name') or item.get('key') or '').strip()
            if not name:
                continue
            value = item.get('value')
            unit = str(item.get('unit') or '').strip()
            detail = name
            if value not in (None, ''):
                detail += f': {value}'
                if unit:
                    detail += f' {unit}'
            low_items.append(detail)

        rows.append({
            'age': data.get('age') if data.get('age') is not None else '',
            'gender': _gender(data.get('gender')),
            'low_items': ' • '.join(low_items) if low_items else 'None | لا توجد قيم منخفضة',
        })
    return rows


def admin_export_blood_collection_xlsx():
    """Create the minimal Admin Excel file requested for blood analyses.

    Columns intentionally stay limited to Age, Gender, and low/deficient
    laboratory values. The original upload, user identity, email, and account
    identifiers are not included.
    """
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    except ImportError as exc:
        raise RuntimeError('xlsx_export_dependency_missing') from exc

    rows = admin_blood_collection_rows()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Blood Analysis Trials'
    ws.sheet_state = 'visible'
    ws.sheet_view.showGridLines = True
    ws.sheet_view.zoomScale = 100
    ws.sheet_view.zoomScaleNormal = 100

    navy='173B57'; blue='2F6F9F'; pale='EAF4FB'; soft='F7FAFC'
    white='FFFFFF'; muted='687B88'; text='233746'; line='D7E3EB'
    thin=Side(style='thin',color=line)

    for col in range(1,4):
        cell=ws.cell(1,col)
        cell.fill=PatternFill('solid',fgColor=pale)
        cell.border=Border(bottom=thin)
    ws['A1']='SymptoSense — Blood Analysis Trials | تجارب تحليل الدم'
    ws['A1'].font=Font(name='Calibri',size=16,bold=True,color=navy)
    ws['A1'].alignment=Alignment(vertical='center')
    ws.row_dimensions[1].height=28

    ws['A2']=f'Consented saved analyses | التحليلات المحفوظة بموافقة: {len(rows)}'
    ws['A2'].font=Font(name='Calibri',size=10,color=muted)
    ws['C2']='Fields | الحقول: Age, Gender, Low/Deficient Values'
    ws['C2'].font=Font(name='Calibri',size=10,color=muted)

    headers=['Age | العمر','Gender | الجنس','Low / Deficient Values | القيم المنخفضة / الناقصة']
    for idx,label in enumerate(headers,start=1):
        cell=ws.cell(4,idx,label)
        cell.fill=PatternFill('solid',fgColor=blue)
        cell.font=Font(name='Calibri',size=10,bold=True,color=white)
        cell.alignment=Alignment(horizontal='center',vertical='center',wrap_text=True)
        cell.border=Border(left=thin,right=thin,top=thin,bottom=thin)
    ws.row_dimensions[4].height=32

    if rows:
        for r_idx,item in enumerate(rows,start=5):
            values=[item['age'],item['gender'],item['low_items']]
            for c_idx,value in enumerate(values,start=1):
                cell=ws.cell(r_idx,c_idx,value)
                cell.font=Font(name='Calibri',size=10,color=text)
                cell.alignment=Alignment(
                    horizontal='center' if c_idx in (1,2) else 'left',
                    vertical='center',wrap_text=True
                )
                cell.border=Border(bottom=Side(style='hair',color='E7EEF4'))
                if r_idx % 2 == 0:
                    cell.fill=PatternFill('solid',fgColor=soft)
            ws.row_dimensions[r_idx].height=30
    else:
        ws['A5']='No consented blood-analysis trials found. | لا توجد تجارب تحليل دم محفوظة بموافقة.'
        ws['A5'].font=Font(name='Calibri',size=11,italic=True,color=muted)
        ws['A5'].alignment=Alignment(vertical='center',wrap_text=True)
        for col in range(1,4):
            cell=ws.cell(5,col)
            cell.fill=PatternFill('solid',fgColor=soft)
            cell.border=Border(top=thin,bottom=thin)
        ws.row_dimensions[5].height=34

    for col,width in {'A':14,'B':20,'C':68}.items():
        ws.column_dimensions[col].width=width

    wb.active=0
    buf=io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf

def admin_export_blood_test_trials_xlsx():
    """Export saved CBC/lab-test trials as a conference-ready Excel workbook."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.worksheet.table import Table, TableStyleInfo
    except ImportError as exc:
        raise RuntimeError("xlsx_export_dependency_missing") from exc

    init_db()

    conn = _conn()
    try:
        c = conn.cursor()
        if USE_POSTGRES:
            c.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = %s",
                ("blood_tests",),
            )
            columns = {str(row[0]) for row in c.fetchall()}
        else:
            c.execute("PRAGMA table_info(blood_tests)")
            columns = {str(row[1]) for row in c.fetchall()}

        has_member_id = "member_id" in columns
        if has_member_id:
            c.execute(
                "SELECT id, user_hash, timestamp, data, COALESCE(member_id,0) "
                "FROM blood_tests ORDER BY timestamp DESC, id DESC"
            )
        else:
            c.execute(
                "SELECT id, user_hash, timestamp, data "
                "FROM blood_tests ORDER BY timestamp DESC, id DESC"
            )

        raw_rows = c.fetchall()
        rows = []
        for row in raw_rows:
            if has_member_id:
                rows.append((row[0], row[1], row[2], row[3], row[4] or 0))
            else:
                rows.append((row[0], row[1], row[2], row[3], 0))
    finally:
        conn.close()

    def _code(prefix, value):
        digest = hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:10].upper()
        return f"{prefix}-{digest}"

    def _json_obj(raw):
        try:
            value = json.loads(raw) if isinstance(raw, str) else (raw or {})
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError, OverflowError):
            return {}

    def _excel_text(value):
        text = str(value or "")
        if text.startswith(("=", "+", "-", "@")):
            return "'" + text
        return text

    def _safe_scalar(value):
        if value is None:
            return ""
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            try:
                if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
                    return ""
            except Exception:
                pass
            return value
        return _excel_text(value)

    def _join(values):
        if not isinstance(values, list):
            return ""
        return " • ".join(_excel_text(v).strip() for v in values if str(v).strip())

    def _source_text(value):
        if isinstance(value, dict):
            name = _excel_text(value.get("name") or "").strip()
            url = _excel_text(value.get("url") or "").strip()
            return " — ".join(x for x in (name, url) if x)
        return _excel_text(value).strip()

    def _level_bilingual(level):
        return {
            "normal": "Normal | طبيعي",
            "see_doctor": "See Doctor | مراجعة طبيب",
            "urgent": "Urgent | عاجل",
            "emergency": "Emergency | طارئ",
            "unknown": "Unclassified | غير مصنف",
        }.get(str(level or "").lower(), _excel_text(level) or "Unclassified | غير مصنف")

    def _status_bilingual(status):
        return {
            "normal": "Normal | طبيعي",
            "low": "Low | منخفض",
            "high": "High | مرتفع",
            "unclassified": "Unclassified | غير مصنف",
        }.get(str(status or "").lower(), _excel_text(status) or "Unclassified | غير مصنف")

    def _gender_bilingual(value):
        raw = str(value or "").strip().lower()
        if raw in {"female", "f", "أنثى"}:
            return "Female | أنثى"
        if raw in {"male", "m", "ذكر"}:
            return "Male | ذكر"
        return _excel_text(value)

    def _profile_scope(member_id):
        return "Self | المستخدم" if int(member_id or 0) == 0 else "Family Member | فرد من العائلة"

    trial_records = []
    indicator_records = []
    level_counts = Counter()
    tester_codes = set()

    for trial_id, user_hash, timestamp_value, raw_data, member_id in rows:
        data = _json_obj(raw_data)
        trial_code = f"LAB-{int(trial_id)}"
        tester_code = _code("U", user_hash)
        tester_codes.add(tester_code)

        indicators = data.get("indicators") if isinstance(data.get("indicators"), list) else []
        statuses = Counter(
            str(x.get("status") or "unclassified").lower()
            for x in indicators if isinstance(x, dict)
        )
        level = str(data.get("level") or "unknown").lower()
        level_counts[level] += 1
        notes = data.get("notes") if isinstance(data.get("notes"), list) else []
        alerts = data.get("dangers") if isinstance(data.get("dangers"), list) else []

        trial_records.append([
            trial_code,
            _excel_text(timestamp_value),
            tester_code,
            _profile_scope(member_id),
            _safe_scalar(data.get("age")),
            _gender_bilingual(data.get("gender")),
            _level_bilingual(level),
            _excel_text(data.get("summary")),
            len(indicators),
            statuses.get("normal", 0),
            statuses.get("low", 0),
            statuses.get("high", 0),
            _join(notes),
            _join(alerts),
        ])

        for ind in indicators:
            if not isinstance(ind, dict):
                continue
            indicator_records.append([
                trial_code,
                _excel_text(timestamp_value),
                tester_code,
                _excel_text(ind.get("name") or ind.get("key")),
                _safe_scalar(ind.get("value")),
                _excel_text(ind.get("unit")),
                _safe_scalar(ind.get("low")),
                _safe_scalar(ind.get("high")),
                _status_bilingual(ind.get("status")),
                _excel_text(ind.get("meaning")),
                _excel_text(ind.get("when")),
                _join(ind.get("symptoms") or []),
                _source_text(ind.get("source")),
            ])

    wb = openpyxl.Workbook()
    summary_ws = wb.active
    summary_ws.title = "Executive Summary"
    trials_ws = wb.create_sheet("Lab Trials")
    indicators_ws = wb.create_sheet("Indicators")
    dictionary_ws = wb.create_sheet("Data Dictionary")

    for ws in (summary_ws, trials_ws, indicators_ws, dictionary_ws):
        ws.sheet_view.showGridLines = False

    navy = "173B57"
    blue = "2F6F9F"
    pale_blue = "EAF4FB"
    pale_teal = "EAF7F6"
    soft = "F7FAFC"
    white = "FFFFFF"
    text = "233746"
    muted = "687B88"
    line = "D7E3EB"
    gold = "FFF7DF"
    green = "EAF7EF"
    red = "FDEDED"
    orange = "FFF0DE"
    thin = Side(style="thin", color=line)

    title_font = Font(name="Aptos Display", size=20, bold=True, color=navy)
    subtitle_font = Font(name="Aptos", size=10, color=muted)
    header_font = Font(name="Aptos", size=9, bold=True, color=white)
    body_font = Font(name="Aptos", size=10, color=text)

    def _style_merged_box(ws, area, value, *, fill, font, align="center", border_color=line):
        ws.merge_cells(area)
        anchor = ws[area.split(":")[0]]
        anchor.value = value
        anchor.fill = PatternFill("solid", fgColor=fill)
        anchor.font = font
        anchor.alignment = Alignment(horizontal=align, vertical="center", wrap_text=True)
        edge = Side(style="thin", color=border_color)
        for merged_row in ws[area]:
            for cell in merged_row:
                cell.border = Border(left=edge, right=edge, top=edge, bottom=edge)

    def _style_table_header(ws, row_no, col_count):
        for col_idx in range(1, col_count + 1):
            cell = ws.cell(row_no, col_idx)
            cell.fill = PatternFill("solid", fgColor=blue)
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
        ws.row_dimensions[row_no].height = 42

    # Executive Summary
    summary_ws.merge_cells("A1:H2")
    summary_ws["A1"] = "SymptoSense — CBC Trial Data Export"
    summary_ws["A1"].fill = PatternFill("solid", fgColor=pale_blue)
    summary_ws["A1"].font = title_font
    summary_ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

    summary_ws.merge_cells("A3:H3")
    summary_ws["A3"] = "Conference-ready administrative export | تصدير إداري منظم وجاهز للعرض"
    summary_ws["A3"].font = subtitle_font
    summary_ws["A3"].alignment = Alignment(horizontal="center", vertical="center")

    _style_merged_box(
        summary_ws, "A5:H5", "Dataset Snapshot | ملخص البيانات",
        fill=navy, font=Font(name="Aptos", size=11, bold=True, color=white)
    )

    follow_up_total = (
        level_counts.get("see_doctor", 0)
        + level_counts.get("urgent", 0)
        + level_counts.get("emergency", 0)
    )
    kpis = [
        ("A7:B9", len(trial_records), "Saved Trials", "التجارب المحفوظة"),
        ("C7:D9", len(tester_codes), "Unique Testers", "المستخدمون"),
        ("E7:F9", level_counts.get("normal", 0), "Normal Results", "نتائج طبيعية"),
        ("G7:H9", follow_up_total, "Follow-up / Urgent", "متابعة أو عاجل"),
    ]
    for area, value, en_label, ar_label in kpis:
        _style_merged_box(
            summary_ws,
            area,
            f"{value}\n{en_label}\n{ar_label}",
            fill=soft,
            font=Font(name="Aptos", size=13, bold=True, color=navy),
        )

    if not trial_records:
        _style_merged_box(
            summary_ws,
            "A11:H13",
            "Current export status | حالة التصدير الحالية\n"
            "No saved CBC trials were found in this dataset.\n"
            "لا توجد تجارب CBC محفوظة في الملف الحالي. عند وجود بيانات فعلية ستظهر تلقائيًا في جداول التفاصيل.",
            fill=gold,
            font=Font(name="Aptos", size=11, bold=True, color="6E5712"),
            border_color="EAD79C",
        )
    else:
        _style_merged_box(
            summary_ws,
            "A11:H13",
            f"Current export status | حالة التصدير الحالية\n"
            f"{len(trial_records)} saved trial(s) across {len(tester_codes)} pseudonymous tester(s).\n"
            f"تم تضمين {len(trial_records)} تجربة محفوظة مع الحفاظ على الخصوصية.",
            fill=pale_teal,
            font=Font(name="Aptos", size=11, bold=True, color="235F60"),
            border_color="B9DEDB",
        )

    _style_merged_box(
        summary_ws, "A15:H15", "Risk Distribution | توزيع مستوى النتيجة",
        fill=navy, font=Font(name="Aptos", size=11, bold=True, color=white)
    )

    summary_ws["A16"] = "Category | الفئة"
    summary_ws["B16"] = "Count | العدد"
    _style_table_header(summary_ws, 16, 2)

    risk_rows = [
        ("Normal | طبيعي", level_counts.get("normal", 0)),
        ("See Doctor | مراجعة طبيب", level_counts.get("see_doctor", 0)),
        ("Urgent | عاجل", level_counts.get("urgent", 0)),
        ("Emergency | طارئ", level_counts.get("emergency", 0)),
        ("Unclassified | غير مصنف", level_counts.get("unknown", 0)),
    ]
    for idx, (label, count) in enumerate(risk_rows, start=17):
        summary_ws.cell(idx, 1, label)
        summary_ws.cell(idx, 2, count)
        for col_idx in (1, 2):
            cell = summary_ws.cell(idx, col_idx)
            cell.font = body_font
            cell.alignment = Alignment(vertical="center", wrap_text=True)
            cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)

    _style_merged_box(
        summary_ws,
        "D16:H18",
        "Privacy & Ethics | الخصوصية والأخلاقيات\n"
        "No direct identifiers are included. Users are represented only by pseudonymous codes.\n"
        "لا يتضمن الملف الاسم أو البريد أو رقم الحساب الخام.",
        fill=pale_teal,
        font=Font(name="Aptos", size=10, bold=True, color="235F60"),
        border_color="B9DEDB",
    )

    _style_merged_box(
        summary_ws,
        "D20:H22",
        "Interpretation Note | ملاحظة تفسيرية\n"
        "SymptoSense provides non-diagnostic guidance. Exported values are intended for "
        "administrative and analytical review, not clinical diagnosis.",
        fill=soft,
        font=Font(name="Aptos", size=9, color=muted),
    )

    summary_ws.merge_cells("A24:H24")
    summary_ws["A24"] = (
        "Generated from SymptoSense | Export timestamp (UTC): "
        + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    )
    summary_ws["A24"].font = Font(name="Aptos", size=8, color="82929D")
    summary_ws["A24"].alignment = Alignment(horizontal="center")

    for col in "ABCDEFGH":
        summary_ws.column_dimensions[col].width = 16
    summary_ws.row_dimensions[1].height = 28
    summary_ws.row_dimensions[2].height = 28
    summary_ws.row_dimensions[3].height = 22
    summary_ws.freeze_panes = "A5"
    summary_ws.print_title_rows = "1:5"
    summary_ws.page_setup.orientation = "landscape"
    summary_ws.page_setup.fitToWidth = 1
    summary_ws.sheet_properties.pageSetUpPr.fitToPage = True

    # Lab Trials
    trials_ws.merge_cells("A1:N2")
    trials_ws["A1"] = "Lab Trials | تجارب التحاليل"
    trials_ws["A1"].fill = PatternFill("solid", fgColor=pale_blue)
    trials_ws["A1"].font = title_font
    trials_ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

    trials_ws.merge_cells("A3:N3")
    trials_ws["A3"] = "One row per saved CBC trial | صف واحد لكل تجربة تحليل محفوظة"
    trials_ws["A3"].font = subtitle_font
    trials_ws["A3"].alignment = Alignment(horizontal="center")

    trial_headers = [
        "Trial Code\nكود التجربة",
        "Timestamp (UTC)\nالتاريخ والوقت",
        "Tester Code\nكود المستخدم",
        "Profile Scope\nنوع الملف",
        "Age\nالعمر",
        "Gender\nالجنس",
        "Risk Level\nمستوى النتيجة",
        "Summary\nالملخص",
        "Indicators\nعدد المؤشرات",
        "Normal\nطبيعي",
        "Low\nمنخفض",
        "High\nمرتفع",
        "Notes\nالملاحظات",
        "Alerts\nالتنبيهات",
    ]
    for col_idx, value in enumerate(trial_headers, start=1):
        trials_ws.cell(5, col_idx, value)
    _style_table_header(trials_ws, 5, len(trial_headers))

    if trial_records:
        for r_idx, record in enumerate(trial_records, start=6):
            for c_idx, value in enumerate(record, start=1):
                cell = trials_ws.cell(r_idx, c_idx, value)
                cell.font = body_font
                cell.alignment = Alignment(vertical="top", wrap_text=True)
                cell.border = Border(bottom=Side(style="hair", color="E7EEF4"))

            level_cell = trials_ws.cell(r_idx, 7)
            level_colors = {
                "Normal | طبيعي": (green, "1F6B43"),
                "See Doctor | مراجعة طبيب": (gold, "7A5D00"),
                "Urgent | عاجل": (orange, "9A4C00"),
                "Emergency | طارئ": (red, "A12828"),
            }
            if level_cell.value in level_colors:
                bg, fg = level_colors[level_cell.value]
                level_cell.fill = PatternFill("solid", fgColor=bg)
                level_cell.font = Font(name="Aptos", size=10, bold=True, color=fg)

        table_ref = f"A5:N{5 + len(trial_records)}"
        table = Table(displayName="LabTrialsTable", ref=table_ref)
        table.tableStyleInfo = TableStyleInfo(
            name="TableStyleMedium2",
            showRowStripes=True,
            showFirstColumn=False,
            showLastColumn=False,
        )
        trials_ws.add_table(table)
    else:
        _style_merged_box(
            trials_ws,
            "A7:N10",
            "No saved lab trials in this export.\n"
            "لا توجد بيانات تحليل محفوظة في الملف الحالي.",
            fill=soft,
            font=Font(name="Aptos", size=11, italic=True, color=muted),
        )

    trials_ws.freeze_panes = "A6"
    trials_ws.auto_filter.ref = f"A5:N{max(5, 5 + len(trial_records))}"
    trial_widths = [14, 22, 17, 16, 9, 10, 18, 38, 13, 10, 10, 10, 30, 30]
    for idx, width in enumerate(trial_widths, start=1):
        trials_ws.column_dimensions[openpyxl.utils.get_column_letter(idx)].width = width
    trials_ws.page_setup.orientation = "landscape"
    trials_ws.page_setup.fitToWidth = 1
    trials_ws.sheet_properties.pageSetUpPr.fitToPage = True
    trials_ws.print_title_rows = "1:5"

    # Indicators
    indicators_ws.merge_cells("A1:M2")
    indicators_ws["A1"] = "CBC Indicators | تفاصيل المؤشرات"
    indicators_ws["A1"].fill = PatternFill("solid", fgColor=pale_blue)
    indicators_ws["A1"].font = title_font
    indicators_ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

    indicators_ws.merge_cells("A3:M3")
    indicators_ws["A3"] = "One row per CBC indicator | صف واحد لكل مؤشر"
    indicators_ws["A3"].font = subtitle_font
    indicators_ws["A3"].alignment = Alignment(horizontal="center")

    indicator_headers = [
        "Trial Code\nكود التجربة",
        "Timestamp (UTC)\nالتاريخ والوقت",
        "Tester Code\nكود المستخدم",
        "Indicator\nالمؤشر",
        "Value\nالقيمة",
        "Unit\nالوحدة",
        "Reference Low\nالحد الأدنى",
        "Reference High\nالحد الأعلى",
        "Status\nالحالة",
        "Meaning\nالتفسير",
        "When to Seek Care\nمتى تطلب الرعاية",
        "Associated Symptoms\nأعراض مرتبطة",
        "Source\nالمصدر",
    ]
    for col_idx, value in enumerate(indicator_headers, start=1):
        indicators_ws.cell(5, col_idx, value)
    _style_table_header(indicators_ws, 5, len(indicator_headers))

    if indicator_records:
        for r_idx, record in enumerate(indicator_records, start=6):
            for c_idx, value in enumerate(record, start=1):
                cell = indicators_ws.cell(r_idx, c_idx, value)
                cell.font = body_font
                cell.alignment = Alignment(vertical="top", wrap_text=True)
                cell.border = Border(bottom=Side(style="hair", color="E7EEF4"))

            status_cell = indicators_ws.cell(r_idx, 9)
            status_colors = {
                "Normal | طبيعي": (green, "1F6B43"),
                "Low | منخفض": (pale_blue, navy),
                "High | مرتفع": (red, "A12828"),
                "Unclassified | غير مصنف": (soft, muted),
            }
            if status_cell.value in status_colors:
                bg, fg = status_colors[status_cell.value]
                status_cell.fill = PatternFill("solid", fgColor=bg)
                status_cell.font = Font(name="Aptos", size=10, bold=True, color=fg)

        table_ref = f"A5:M{5 + len(indicator_records)}"
        table = Table(displayName="IndicatorsTable", ref=table_ref)
        table.tableStyleInfo = TableStyleInfo(
            name="TableStyleMedium2",
            showRowStripes=True,
            showFirstColumn=False,
            showLastColumn=False,
        )
        indicators_ws.add_table(table)
    else:
        _style_merged_box(
            indicators_ws,
            "A7:M10",
            "No CBC indicator rows are available in this export.\n"
            "لا توجد تفاصيل مؤشرات في الملف الحالي.",
            fill=soft,
            font=Font(name="Aptos", size=11, italic=True, color=muted),
        )

    indicators_ws.freeze_panes = "A6"
    indicators_ws.auto_filter.ref = f"A5:M{max(5, 5 + len(indicator_records))}"
    indicator_widths = [14, 22, 17, 24, 11, 11, 13, 13, 14, 32, 34, 30, 42]
    for idx, width in enumerate(indicator_widths, start=1):
        indicators_ws.column_dimensions[openpyxl.utils.get_column_letter(idx)].width = width
    indicators_ws.page_setup.orientation = "landscape"
    indicators_ws.page_setup.fitToWidth = 1
    indicators_ws.sheet_properties.pageSetUpPr.fitToPage = True
    indicators_ws.print_title_rows = "1:5"

    # Data Dictionary
    dictionary_ws.merge_cells("A1:F2")
    dictionary_ws["A1"] = "Data Dictionary & Conference Notes | دليل البيانات"
    dictionary_ws["A1"].fill = PatternFill("solid", fgColor=pale_blue)
    dictionary_ws["A1"].font = title_font
    dictionary_ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

    dictionary_ws.merge_cells("A3:F3")
    dictionary_ws["A3"] = "Field definitions, privacy handling, and interpretation notes for reviewers"
    dictionary_ws["A3"].font = subtitle_font
    dictionary_ws["A3"].alignment = Alignment(horizontal="center")

    dictionary_rows = [
        ["Field | الحقل", "Sheet | الورقة", "Meaning | المعنى", "Type | النوع", "Privacy | الخصوصية", "Conference Note | ملاحظة"],
        ["Trial Code", "Lab Trials / Indicators", "Pseudonymous code for one saved CBC trial", "Text", "Non-identifying", "Links trial-level and indicator-level rows."],
        ["Timestamp (UTC)", "Lab Trials / Indicators", "Time the trial was saved", "Date/Time", "Low sensitivity", "UTC improves reproducibility across environments."],
        ["Tester Code", "Lab Trials / Indicators", "Stable pseudonymous user code", "Text", "Pseudonymized", "Supports grouping repeated trials without exposing identity."],
        ["Profile Scope", "Lab Trials", "Self vs family-member context", "Category", "Low sensitivity", "No family-member name is exported."],
        ["Age", "Lab Trials", "Age used in the analysis", "Numeric/Text", "Health-related", "Interpret in aggregate unless row-level review is justified."],
        ["Gender", "Lab Trials", "Gender used by CBC interpretation rules", "Category", "Health-related", "Only shown when present in the saved trial."],
        ["Risk Level", "Lab Trials", "Overall non-diagnostic result category", "Category", "Health-related", "Not a clinical diagnosis."],
        ["Indicator", "Indicators", "CBC marker such as Hemoglobin", "Text", "Health-related", "Each marker appears on its own row."],
        ["Value / Unit", "Indicators", "Recorded laboratory value and unit", "Numeric/Text", "Health-related", "Review alongside the stated reference range."],
        ["Reference Low / High", "Indicators", "Reference interval used by the feature", "Numeric", "Non-identifying", "Supports scientific traceability and review."],
        ["Status", "Indicators", "Normal / Low / High / Unclassified", "Category", "Health-related", "Rule-based label, not diagnosis."],
        ["Source", "Indicators", "Reference source attached to the indicator", "URL/Text", "Public", "Supports traceability and reproducibility."],
    ]

    for r_idx, row in enumerate(dictionary_rows, start=5):
        for c_idx, value in enumerate(row, start=1):
            cell = dictionary_ws.cell(r_idx, c_idx, value)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
            if r_idx == 5:
                cell.fill = PatternFill("solid", fgColor=blue)
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            else:
                cell.font = body_font

    dictionary_ws.freeze_panes = "A6"
    dictionary_widths = [20, 22, 36, 15, 18, 42]
    for idx, width in enumerate(dictionary_widths, start=1):
        dictionary_ws.column_dimensions[openpyxl.utils.get_column_letter(idx)].width = width
    dictionary_ws.page_setup.orientation = "landscape"
    dictionary_ws.page_setup.fitToWidth = 1
    dictionary_ws.sheet_properties.pageSetUpPr.fitToPage = True
    dictionary_ws.print_title_rows = "1:5"

    wb.active = 0
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf

def admin_clear_blood_test_trials():
    """Delete all previously saved CBC/lab-test analyses only.

    User accounts, symptom analyses, medication data, medical knowledge, and
    other profile information are intentionally preserved.
    """
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute("SELECT COUNT(*), COUNT(DISTINCT user_hash) FROM blood_tests")
        row = c.fetchone() or (0, 0)
        saved_tests = max(0, int(row[0] or 0))
        distinct_testers = max(0, int(row[1] or 0))
        c.execute("DELETE FROM blood_tests")
        conn.commit()
        return {
            "deleted_blood_tests": saved_tests,
            "affected_testers": distinct_testers,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def reset_public_launch_data(admin_user_id):
    """Remove test/user-generated data while preserving the Admin and app knowledge.

    Intended for the explicit "prepare for public launch" Admin action. The
    medical knowledge base, curated content, schema metadata, and the current
    Admin account are preserved. All user-generated/test activity is removed so
    dashboards and research exports start clean.
    """
    admin_user_id = int(admin_user_id)
    conn = _conn()
    try:
        c = conn.cursor()
        # Discover tables first so older/newer deployments remain compatible.
        if USE_POSTGRES:
            c.execute("SELECT tablename FROM pg_tables WHERE schemaname = current_schema()")
            existing = {str(r[0]) for r in c.fetchall()}
        else:
            c.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing = {str(r[0]) for r in c.fetchall()}

        # Child/activity tables first. Curated/static tables are deliberately
        # excluded (mk_*, ss_content, medical_medications, ss_schema_meta).
        purge_tables = [
            "push_action_tokens", "med_snoozes", "med_notification_settings",
            "push_delivery_log", "push_subscriptions", "med_logs", "med_plans",
            "med_reminders", "medication_reminders", "med_reminder_settings",
            "med_email_actions", "med_email_deliveries", "med_telegram_links",
            "med_telegram_deliveries", "med_plan_tombstones",
            "followups", "symptom_relief_logs", "feedback", "assistant_feedback",
            "results", "records", "daily_checkins", "blood_tests",
            "conversations", "family_members", "profiles", "user_data",
            "subscribers", "visits",
            "ss_analysis_links", "ss_user_preferences",
            "ss_chat_history", "ss_daily_checkins", "ss_health_profiles", "ss_privacy",
            "ss_consent_log", "ss_consent_state", "ss_privacy_events", "ss_handoff_links",
            "ss_journey_events", "ss_session_activity", "ss_usage_events", "ss_search_gap_log",
            "ss_login_activity", "ss_auth_rate_limits", "ss_analyze_rate_limits",
            "ss_password_resets", "ss_email_verifications", "ss_admin_audit",
            # Unmatched symptom logging is usage-derived and should start clean.
            "mk_unmatched_log",
        ]
        deleted = {}
        for table in purge_tables:
            if table not in existing:
                continue
            c.execute(f'DELETE FROM "{table}"')
            try:
                deleted[table] = max(0, int(c.rowcount or 0))
            except (TypeError, ValueError, OverflowError):
                logging.getLogger(__name__).debug("Handled exception in reset_public_launch_data; fallback applied (handler 2778)")
                deleted[table] = 0

        # Keep exactly the current Admin account; remove all test/public users.
        removed_users = 0
        if "ss_users" in existing:
            c.execute(f"DELETE FROM ss_users WHERE id <> {PH}", (admin_user_id,))
            try:
                removed_users = max(0, int(c.rowcount or 0))
            except (TypeError, ValueError, OverflowError):
                logging.getLogger(__name__).debug("Handled exception in reset_public_launch_data; fallback applied (handler 2787)")
                removed_users = 0
            # Clear nonessential Admin activity/profile state without touching
            # credentials, role, verification, or account status.
            c.execute(
                f"UPDATE ss_users SET last_login=NULL WHERE id={PH}",
                (admin_user_id,),
            )

        conn.commit()
        return {
            "removed_users": removed_users,
            "cleared_tables": len(deleted),
            "deleted_rows": sum(deleted.values()) + removed_users,
            "details": deleted,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_ss_user(user_id):
    """Get user info by ID."""
    if not user_id:
        return None
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute("SELECT id, email, name, role, created_at, last_login, status, COALESCE(email_verified,1), email_verified_at FROM ss_users WHERE id=%s" % PH, (int(user_id),))
        row = c.fetchone()
        if not row:
            return None
        role = "admin" if str(row[3] or "user").strip().lower() == "admin" else "user"
        return {"id": row[0], "email": row[1], "name": row[2], "role": role, "created_at": row[4], "last_login": row[5], "status": row[6] or "active", "email_verified": bool(row[7]), "email_verified_at": row[8]}
    finally:
        conn.close()


def get_ss_user_by_email(email):
    """Get user info by email."""
    email = (email or "").strip().lower()
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute("SELECT id, email, name, role, status, COALESCE(email_verified,1), email_verified_at FROM ss_users WHERE lower(email)=%s" % PH, (email,))
        row = c.fetchone()
        if not row:
            return None
        role = "admin" if str(row[3] or "user").strip().lower() == "admin" else "user"
        return {"id": row[0], "email": row[1], "name": row[2], "role": role, "status": row[4] or "active", "email_verified": bool(row[5]), "email_verified_at": row[6]}
    finally:
        conn.close()


def list_ss_admin_users():
    """List accounts and effective roles for super-admin role management."""
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute("SELECT id,email,name,role,created_at,last_login FROM ss_users ORDER BY id")
        rows = c.fetchall()
    finally:
        conn.close()
    out = []
    for row in rows:
        role = "admin" if str(row[3] or "user").strip().lower() == "admin" else "user"
        out.append({"id": row[0], "email": row[1], "name": row[2], "role": role,
                    "created_at": row[4], "last_login": row[5]})
    return out



def update_unverified_email(user_id, new_email, current_password):
    """Change the email only for an unverified, active account.

    This is intended for the post-registration verification flow. It never
    changes passwords, roles, or verified accounts. The current password is
    required because the pending-verification browser session alone is not
    sufficient authority to move an account to another email address.
    """
    new_email = (new_email or "").strip().lower()
    if not new_email or not _re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', new_email):
        return False, "invalid_email"
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute("SELECT email,status,COALESCE(email_verified,1),password_hash FROM ss_users WHERE id=%s" % PH, (int(user_id),))
        row = c.fetchone()
        if not row:
            return False, "account_not_found"
        if (row[1] or "active") != "active":
            return False, "account_unavailable"
        if bool(row[2]):
            return False, "already_verified"
        password_valid, _ = _verify_password(current_password or "", row[3])
        if not password_valid:
            return False, "incorrect_password"
        # The project-owner email must refer to the existing owner account only.
        if is_owner_admin_email(new_email) and new_email != (row[0] or "").strip().lower():
            return False, "email_exists"
        c.execute("SELECT id FROM ss_users WHERE lower(email)=%s AND id<>%s" % (PH, PH), (new_email, int(user_id)))
        if c.fetchone():
            return False, "email_exists"
        c.execute("UPDATE ss_users SET email=%s WHERE id=%s" % (PH, PH), (new_email, int(user_id)))
        conn.commit()
        return True, None
    finally:
        conn.close()

def is_owner_admin_email(email):
    """Return True only for the configured project-owner email.

    A missing environment variable never makes an arbitrary email an owner.
    Persisted Admin authorization is handled by ``ss_users.role`` instead.
    """
    if not OWNER_ADMIN_EMAIL:
        return False
    return (email or "").strip().lower() == OWNER_ADMIN_EMAIL


def promote_existing_owner_admin(user_id):
    """Promote the already-existing authenticated owner account only.

    No account is created, no password is touched, and no other user's role is
    modified. Returns True only when the supplied ID belongs to the owner.
    """
    if not user_id:
        return False
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute("SELECT email,status,role FROM ss_users WHERE id=%s" % PH, (int(user_id),))
        row = c.fetchone()
        if not row or (row[1] or "active") != "active" or not is_owner_admin_email(row[0]):
            return False
        if (row[2] or "user") != "admin":
            c.execute("UPDATE ss_users SET role='admin' WHERE id=%s" % PH, (int(user_id),))
            conn.commit()
        return True
    finally:
        conn.close()


def ensure_owner_admin_by_email(email=None):
    """Repair the role for the configured existing owner without creating one.

    When no owner email is configured this helper makes no database changes;
    any already-persisted Admin role remains valid.
    """
    if not OWNER_ADMIN_EMAIL:
        return {"found": False, "promoted": False, "reason": "owner_not_configured"}
    target = (email or OWNER_ADMIN_EMAIL).strip().lower()
    if target != OWNER_ADMIN_EMAIL:
        return {"found": False, "promoted": False, "reason": "not_owner_email"}
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute("SELECT id,role,status FROM ss_users WHERE lower(email)=%s" % PH, (target,))
        row = c.fetchone()
        if not row:
            return {"found": False, "promoted": False, "reason": "owner_not_found"}
        if (row[2] or "active") != "active":
            return {"found": True, "promoted": False, "reason": "owner_inactive", "user_id": row[0]}
        stored_role = str(row[1] or "user").strip().lower()
        promoted = stored_role != "admin" or (row[1] or "") != "admin"
        if promoted:
            c.execute("UPDATE ss_users SET role='admin' WHERE id=%s" % PH, (int(row[0]),))
            conn.commit()
        return {"found": True, "promoted": promoted, "reason": "ok", "user_id": row[0]}
    finally:
        conn.close()


def set_ss_user_role(user_id, role):
    """Persist a role for internal server-side use only.

    New Admin promotion requires a configured owner email. Existing persisted
    Admin authorization does not depend on the environment variable. This
    function is not exposed as a public/Admin API.
    """
    role = (role or "").strip()
    if role not in _ADMIN_ROLES | {"user"}:
        raise ValueError("invalid_role")
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute("SELECT email FROM ss_users WHERE id=%s" % PH, (int(user_id),))
        row = c.fetchone()
        if not row:
            return False
        owner = is_owner_admin_email(row[0])
        if role == "admin":
            if not OWNER_ADMIN_EMAIL:
                raise PermissionError("admin_owner_not_configured")
            if not owner:
                raise PermissionError("admin_role_reserved_for_owner")
        if role != "admin" and owner:
            raise PermissionError("owner_admin_role_is_fixed")
        c.execute("UPDATE ss_users SET role=%s WHERE id=%s" % (PH, PH), (role, int(user_id)))
        conn.commit()
        return bool(c.rowcount)
    finally:
        conn.close()


def admin_count():
    """Return the number of persisted Admin accounts (schema limits this to one)."""
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM ss_users WHERE lower(COALESCE(role,'user'))='admin'")
        return int(c.fetchone()[0] or 0)
    finally:
        conn.close()


def claim_current_user_as_admin(user_id):
    """Backward-compatible alias for the authenticated-owner repair path."""
    return promote_existing_owner_admin(user_id)


def load_health_profile(user_id):
    """Load only the authenticated user's optional health profile."""
    if not user_id:
        return None
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            "SELECT user_id,display_name,dob,gender,height,weight,activity_level,medications,allergies,health_conditions,extra_info,lang,updated_at "
            "FROM ss_health_profiles WHERE user_id=%s" % PH,
            (int(user_id),),
        )
        row = c.fetchone()
        if not row:
            return None
        keys = ["user_id","display_name","dob","gender","height","weight","activity_level","medications","allergies","health_conditions","extra_info","lang","updated_at"]
        return dict(zip(keys, row))
    finally:
        conn.close()


def save_health_profile(user_id, data):
    """Create/update an optional health profile without making health fields mandatory."""
    if not user_id:
        raise ValueError("login_required")
    data = data or {}
    allowed = ["display_name","dob","gender","height","weight","activity_level","medications","allergies","health_conditions","extra_info","lang"]
    values = {k: str(data.get(k) or "").strip()[:4000] for k in allowed}
    values["lang"] = "en" if values.get("lang") == "en" else "ar"
    if values.get("gender") not in {"", "male", "female", "other", "prefer_not_to_say"}:
        values["gender"] = ""
    now = datetime.now(timezone.utc).isoformat()
    conn = _conn()
    try:
        c = conn.cursor()
        params = (int(user_id),) + tuple(values[k] for k in allowed) + (now,)
        if USE_POSTGRES:
            c.execute(
                "INSERT INTO ss_health_profiles (user_id,display_name,dob,gender,height,weight,activity_level,medications,allergies,health_conditions,extra_info,lang,updated_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT(user_id) DO UPDATE SET display_name=EXCLUDED.display_name,dob=EXCLUDED.dob,gender=EXCLUDED.gender,height=EXCLUDED.height,weight=EXCLUDED.weight,activity_level=EXCLUDED.activity_level,medications=EXCLUDED.medications,allergies=EXCLUDED.allergies,health_conditions=EXCLUDED.health_conditions,extra_info=EXCLUDED.extra_info,lang=EXCLUDED.lang,updated_at=EXCLUDED.updated_at",
                params,
            )
        else:
            c.execute(
                "INSERT INTO ss_health_profiles (user_id,display_name,dob,gender,height,weight,activity_level,medications,allergies,health_conditions,extra_info,lang,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(user_id) DO UPDATE SET display_name=excluded.display_name,dob=excluded.dob,gender=excluded.gender,height=excluded.height,weight=excluded.weight,activity_level=excluded.activity_level,medications=excluded.medications,allergies=excluded.allergies,health_conditions=excluded.health_conditions,extra_info=excluded.extra_info,lang=excluded.lang,updated_at=excluded.updated_at",
                params,
            )
        conn.commit()
    finally:
        conn.close()


def delete_health_profile(user_id):
    """Delete only the optional health-profile row; the account remains intact."""
    if not user_id:
        return False
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute("DELETE FROM ss_health_profiles WHERE user_id=%s" % PH, (int(user_id),))
        conn.commit()
        return bool(c.rowcount)
    finally:
        conn.close()


def load_privacy_settings(user_id):
    """Return privacy choices with safe defaults when the user has not saved settings yet."""
    defaults = {"use_in_assistant": True, "use_in_analysis": True, "use_in_calculators": True, "save_chat_history": True}
    if not user_id:
        return defaults.copy()
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute("SELECT use_in_assistant,use_in_analysis,use_in_calculators,save_chat_history,updated_at FROM ss_privacy WHERE user_id=%s" % PH, (int(user_id),))
        row = c.fetchone()
        if not row:
            return defaults.copy()
        return {"use_in_assistant": bool(row[0]), "use_in_analysis": bool(row[1]), "use_in_calculators": bool(row[2]), "save_chat_history": bool(row[3]), "updated_at": row[4]}
    finally:
        conn.close()


def save_privacy_settings(user_id, data):
    if not user_id:
        raise ValueError("login_required")
    data = data or {}
    vals = {
        "use_in_assistant": int(bool(data.get("use_in_assistant", True))),
        "use_in_analysis": int(bool(data.get("use_in_analysis", True))),
        "use_in_calculators": int(bool(data.get("use_in_calculators", True))),
        "save_chat_history": int(bool(data.get("save_chat_history", True))),
    }
    now = datetime.now(timezone.utc).isoformat()
    conn = _conn()
    try:
        c = conn.cursor()
        params = (int(user_id), vals["use_in_assistant"], vals["use_in_analysis"], vals["use_in_calculators"], vals["save_chat_history"], now)
        if USE_POSTGRES:
            c.execute(
                "INSERT INTO ss_privacy(user_id,use_in_assistant,use_in_analysis,use_in_calculators,save_chat_history,updated_at) VALUES(%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT(user_id) DO UPDATE SET use_in_assistant=EXCLUDED.use_in_assistant,use_in_analysis=EXCLUDED.use_in_analysis,use_in_calculators=EXCLUDED.use_in_calculators,save_chat_history=EXCLUDED.save_chat_history,updated_at=EXCLUDED.updated_at",
                params,
            )
        else:
            c.execute(
                "INSERT INTO ss_privacy(user_id,use_in_assistant,use_in_analysis,use_in_calculators,save_chat_history,updated_at) VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(user_id) DO UPDATE SET use_in_assistant=excluded.use_in_assistant,use_in_analysis=excluded.use_in_analysis,use_in_calculators=excluded.use_in_calculators,save_chat_history=excluded.save_chat_history,updated_at=excluded.updated_at",
                params,
            )
        conn.commit()
    finally:
        conn.close()


def save_chat_message(user_id, role, content):
    """Save a chat message for a user."""
    if not user_id:
        return
    conn = _conn()
    try:
        c = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        if USE_POSTGRES:
            c.execute(
                "INSERT INTO ss_chat_history (user_id, role, content, timestamp) VALUES (%s,%s,%s,%s)",
                (int(user_id), role, content, now),
            )
        else:
            c.execute(
                "INSERT INTO ss_chat_history (user_id, role, content, timestamp) VALUES (?,?,?,?)",
                (int(user_id), role, content, now),
            )
        conn.commit()
    finally:
        conn.close()


def get_chat_history(user_id, limit=50):
    """Get chat history for a user."""
    if not user_id:
        return []
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            "SELECT role, content, timestamp FROM ss_chat_history WHERE user_id=%s ORDER BY id DESC LIMIT %s" % (PH, PH),
            (int(user_id), int(limit)),
        )
        rows = c.fetchall()
    finally:
        conn.close()
    return [{"role": r[0], "content": r[1], "timestamp": r[2]} for r in reversed(rows)]


def clear_chat_history(user_id):
    """Clear chat history for a user."""
    if not user_id:
        return
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute("DELETE FROM ss_chat_history WHERE user_id=%s" % PH, (int(user_id),))
        conn.commit()
    finally:
        conn.close()


def delete_ss_user(user_id):
    """Delete a non-Admin user account and all account-owned application data.

    General health records use the stable ``account-<id>`` owner hash, while
    medication reminder tables use the numeric account id (or its hash). V215
    removes both ownership forms plus all reminder delivery/link/tombstone rows.
    """
    if not user_id:
        return
    conn = _conn()
    try:
        c = conn.cursor(); uid = int(user_id)
        owner = _hash_user("account-%s" % uid)
        med_hashes = tuple(dict.fromkeys((_hash_user(uid), owner)))
        web_checkin_storage_id = -(_WEB_CHECKIN_USERDATA_OFFSET + uid)
        if USE_POSTGRES:
            c.execute("SELECT tablename FROM pg_tables WHERE schemaname=current_schema()")
            existing = {str(r[0]) for r in c.fetchall()}
        else:
            c.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing = {str(r[0]) for r in c.fetchall()}

        def columns(table):
            if USE_POSTGRES:
                c.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s", (table,))
                return {str(r[0]) for r in c.fetchall()}
            c.execute(f"PRAGMA table_info({table})")
            return {str(r[1]) for r in c.fetchall()}

        by_hash = ("family_members","results","blood_tests","profiles",
                   "daily_checkins","assistant_feedback","feedback","followups","records",
                   "visits","push_subscriptions","symptom_followups","vitals")
        for table in by_hash:
            if table in existing and "user_hash" in columns(table):
                c.execute(f"DELETE FROM {table} WHERE user_hash={PH}", (owner,))

        marks = ','.join([PH] * len(med_hashes))
        for table in ("med_logs","med_plans","med_snoozes","med_plan_tombstones","med_notification_settings"):
            if table in existing and "user_hash" in columns(table):
                c.execute(f"DELETE FROM {table} WHERE user_hash IN ({marks})", med_hashes)

        for table in ("med_reminders","medication_reminders","med_reminder_settings",
                      "med_email_actions","med_email_deliveries","med_telegram_links",
                      "med_telegram_deliveries"):
            if table in existing and "user_id" in columns(table):
                c.execute(f"DELETE FROM {table} WHERE user_id={PH}", (uid,))

        if "ss_daily_checkins" in existing:
            c.execute(f"DELETE FROM ss_daily_checkins WHERE user_hash={PH}", (owner,))
        if "ss_password_resets" in existing:
            c.execute(f"DELETE FROM ss_password_resets WHERE user_id={PH}", (uid,))
        if "ss_email_verifications" in existing:
            c.execute(f"DELETE FROM ss_email_verifications WHERE user_id={PH}", (uid,))
        if "ss_login_activity" in existing:
            c.execute(f"UPDATE ss_login_activity SET user_id=NULL WHERE user_id={PH}", (uid,))
        if "ss_admin_audit" in existing:
            c.execute(f"UPDATE ss_admin_audit SET admin_id=NULL WHERE admin_id={PH}", (uid,))
        if "ss_content" in existing:
            c.execute(f"UPDATE ss_content SET created_by=NULL WHERE created_by={PH}", (uid,))
            c.execute(f"UPDATE ss_content SET updated_by=NULL WHERE updated_by={PH}", (uid,))
        if "ss_chat_history" in existing:
            c.execute(f"DELETE FROM ss_chat_history WHERE user_id={PH}", (uid,))
        if "user_data" in existing:
            c.execute(f"DELETE FROM user_data WHERE user_id={PH}", (web_checkin_storage_id,))
        for table in ("ss_privacy","ss_health_profiles","ss_user_preferences","passkey_credentials"):
            if table in existing:
                c.execute(f"DELETE FROM {table} WHERE user_id={PH}", (uid,))
        if "ss_analysis_links" in existing:
            c.execute(f"DELETE FROM ss_analysis_links WHERE user_hash={PH}", (owner,))
        if "ss_admin_2fa" in existing:
            c.execute(f"DELETE FROM ss_admin_2fa WHERE user_id={PH}", (uid,))
        if "ss_admin_session_control" in existing:
            c.execute(f"DELETE FROM ss_admin_session_control WHERE user_id={PH}", (uid,))
        if "ss_users" in existing:
            c.execute(f"DELETE FROM ss_users WHERE id={PH}", (uid,))
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()



FOLLOWUP_OUTCOMES = ("better", "same", "worse")


def save_followup(user_id, record_id, outcome, new_sign=False):
    """Store a follow-up answer ("did it improve?") for one of the user's own analyses."""
    if outcome not in FOLLOWUP_OUTCOMES:
        raise ValueError("invalid_outcome")
    uh = _hash_user(user_id)
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(f"SELECT 1 FROM records WHERE id={PH} AND user_hash={PH}", (int(record_id), uh))
        if not c.fetchone():
            return False
        c.execute(
            f"INSERT INTO symptom_followups (user_hash, record_id, outcome, new_sign, timestamp) VALUES ({PH},{PH},{PH},{PH},{PH})",
            (uh, int(record_id), outcome, 1 if new_sign else 0, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def get_followups(user_id, limit=50):
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"SELECT record_id, outcome, new_sign, timestamp FROM symptom_followups WHERE user_hash={PH} ORDER BY id DESC LIMIT {int(limit)}",
            (_hash_user(user_id),),
        )
        return [{"record_id": r[0], "outcome": r[1], "new_sign": bool(r[2]), "timestamp": r[3]} for r in c.fetchall()]
    finally:
        conn.close()


_LEGACY_OUTCOME_ALIASES = {"improved": ("better", False), "better": ("better", False), "same": ("same", False),
                           "worse": ("worse", False), "new_symptoms": ("worse", True), "new_sign": ("worse", True)}


def normalize_followup(outcome, new_sign=False):
    """Map any accepted spelling to the single schema (better|same|worse + new_sign flag).

    Legacy spellings (``improved``, ``new_symptoms``) exist only so old clients and old rows keep working; they are
    converted here, at the boundary, and never stored. A new-symptom answer is conservatively stored as worse + new_sign.
    """
    key = str(outcome or "").strip().lower()
    if key not in _LEGACY_OUTCOME_ALIASES:
        raise ValueError("invalid_outcome")
    canon, implied = _LEGACY_OUTCOME_ALIASES[key]
    return canon, bool(new_sign) or implied


def get_latest_followup(user_id, record_id=None):
    """Latest follow-up answer (same table as save_followup/get_followups)."""
    conn = _conn()
    try:
        c = conn.cursor()
        if record_id is None:
            c.execute(f"SELECT record_id, timestamp, outcome, new_sign FROM symptom_followups WHERE user_hash={PH} ORDER BY id DESC LIMIT 1",
                      (_hash_user(user_id),))
        else:
            c.execute(f"SELECT record_id, timestamp, outcome, new_sign FROM symptom_followups WHERE user_hash={PH} AND record_id={PH} ORDER BY id DESC LIMIT 1",
                      (_hash_user(user_id), int(record_id)))
        row = c.fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return {"record_id": int(row[0]), "timestamp": row[1], "outcome": row[2] or "", "new_sign": bool(row[3])}


def migrate_legacy_followups():
    """Move rows of the old ``followups`` table into ``symptom_followups`` (idempotent; rows are removed once copied)."""
    conn = _conn()
    moved = 0
    try:
        c = conn.cursor()
        c.execute("SELECT id, user_hash, record_id, timestamp, outcome FROM followups ORDER BY id")
        for fid, uh, rid, ts, out in c.fetchall():
            try:
                canon, sign = normalize_followup(out)
            except ValueError:
                continue                      # unknown spelling: leave the row untouched rather than guess
            if rid is None:
                continue
            c.execute(f"SELECT 1 FROM symptom_followups WHERE user_hash={PH} AND record_id={PH} AND timestamp={PH}", (uh, rid, ts))
            if not c.fetchone():
                c.execute(f"INSERT INTO symptom_followups (user_hash, record_id, outcome, new_sign, timestamp) VALUES ({PH},{PH},{PH},{PH},{PH})",
                          (uh, rid, canon, 1 if sign else 0, ts))
            c.execute(f"DELETE FROM followups WHERE id={PH}", (fid,))
            moved += 1
        conn.commit()
    except DB_ERRORS:
        conn.rollback()
        _logger.warning("Legacy follow-up migration skipped")
    finally:
        conn.close()
    return moved


def followup_stats():
    """Aggregate, non-identifying counts for the admin quality panel."""
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute("SELECT outcome, COUNT(*), SUM(new_sign) FROM symptom_followups GROUP BY outcome")
        return {r[0]: {"count": r[1], "new_sign": int(r[2] or 0)} for r in c.fetchall()}
    finally:
        conn.close()


def save_vital(user_id, member_id, kind, v1, v2=None, context="", measured_at=None):
    now = datetime.now(timezone.utc).isoformat()
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"INSERT INTO vitals (user_hash, member_id, kind, v1, v2, context, measured_at, created) VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})",
            (_hash_user(user_id), int(member_id or 0), kind, float(v1), None if v2 is None else float(v2), context or "", measured_at or now, now),
        )
        conn.commit()
    finally:
        conn.close()


def get_vitals(user_id, member_id=0, kind=None, days=90, limit=300):
    since = (datetime.now(timezone.utc) - timedelta(days=int(days))).isoformat()
    conn = _conn()
    try:
        c = conn.cursor()
        sql = f"SELECT id, kind, v1, v2, context, measured_at FROM vitals WHERE user_hash={PH} AND member_id={PH} AND measured_at>={PH}"
        args = [_hash_user(user_id), int(member_id or 0), since]
        if kind:
            sql += f" AND kind={PH}"
            args.append(kind)
        sql += f" ORDER BY measured_at DESC LIMIT {int(limit)}"
        c.execute(sql, tuple(args))
        return [{"id": r[0], "kind": r[1], "v1": r[2], "v2": r[3], "context": r[4] or "", "measured_at": r[5]} for r in c.fetchall()]
    finally:
        conn.close()


def delete_vital(user_id, vital_id):
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(f"DELETE FROM vitals WHERE id={PH} AND user_hash={PH}", (int(vital_id), _hash_user(user_id)))
        conn.commit()
        return c.rowcount > 0
    finally:
        conn.close()
