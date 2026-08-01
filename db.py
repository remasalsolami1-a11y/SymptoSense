import os
import io
import sqlite3
import hashlib
from datetime import datetime, timedelta, timezone
from collections import Counter

# PostgreSQL (production, Railway) if DATABASE_URL is set, otherwise SQLite (local dev).
DB_PATH = os.environ.get("DB_PATH", "symptosense.db")
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
USE_POSTGRES = bool(DATABASE_URL)

PH = "%s" if USE_POSTGRES else "?"


def _conn():
    if USE_POSTGRES:
        import psycopg2
        return psycopg2.connect(DATABASE_URL)
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
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
        conn.commit()
    finally:
        conn.close()


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


def log_visit(user_id):
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"INSERT INTO visits (user_hash, timestamp) VALUES ({PH},{PH})",
            (_hash_user(user_id), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
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
            "SELECT id, user_hash, timestamp, lang, age, gender, symptoms, duration, severity, urgency "
            "FROM records ORDER BY id"
        )
        return c.fetchall()
    finally:
        conn.close()


def export_all_records_csv():
    import csv
    rows = _all_records()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id","user_hash","timestamp","lang","age","gender","symptoms","duration","severity","urgency"])
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
    headers = ["id","user_hash","timestamp","lang","age","gender","symptoms","duration","severity","urgency"]
    ws.append(headers)
    for row in rows:
        ws.append(list(row))

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
            f"SELECT timestamp, symptoms, severity, duration, urgency "
            f"FROM records WHERE user_hash={PH} ORDER BY id DESC LIMIT 1",
            (_hash_user(user_id),),
        )
        row = c.fetchone()
    finally:
        conn.close()
    if not row:
        return None
    ts, symptoms, severity, duration, urgency = row
    return {
        "timestamp": ts,
        "symptoms": [s for s in symptoms.split(",") if s],
        "severity": severity,
        "duration": duration,
        "urgency": urgency,
        "days_ago": (datetime.now(timezone.utc) - datetime.fromisoformat(ts)).days,
    }


def save_record(user_id, lang, age, gender, symptoms, duration, severity, urgency):
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"INSERT INTO records (user_hash, timestamp, lang, age, gender, symptoms, duration, severity, urgency) "
            f"VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})",
            (
                _hash_user(user_id),
                datetime.now(timezone.utc).isoformat(),
                lang, age, gender,
                ",".join(symptoms or []),
                duration, severity, urgency,
            ),
        )
        conn.commit()
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
