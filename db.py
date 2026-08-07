import os
import io
import json
import logging
import sqlite3
import hashlib
from datetime import datetime, timedelta, timezone
from collections import Counter

# PostgreSQL (production, Railway) if DATABASE_URL is set, otherwise SQLite (local dev).
DB_PATH = os.environ.get("DB_PATH", "symptosense.db")
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
USE_POSTGRES = bool(DATABASE_URL)

PH = "%s" if USE_POSTGRES else "?"

_logger = logging.getLogger("SymptoSense")


def _init_backend():
    """Validates the PostgreSQL connection once. On failure, falls back to SQLite
    so the bot keeps running instead of crashing, and logs the real error."""
    global USE_POSTGRES, PH
    if not USE_POSTGRES:
        return
    try:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        conn.close()
    except Exception as e:
        _logger.error(
            f"PostgreSQL connection failed ({e!r}) — falling back to SQLite. "
            f"Fix DATABASE_URL to enable persistent storage."
        )
        USE_POSTGRES = False
        PH = "?"


def _conn():
    if USE_POSTGRES:
        import psycopg2
        return psycopg2.connect(DATABASE_URL)
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
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
                CREATE TABLE IF NOT EXISTS daily_checkins (
                    id SERIAL PRIMARY KEY,
                    user_hash TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    severity INTEGER
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
                    timestamp TEXT NOT NULL
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_fb_record ON feedback(record_id)")
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
                CREATE TABLE IF NOT EXISTS daily_checkins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_hash TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    severity INTEGER
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
                    timestamp TEXT NOT NULL
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_fb_record ON feedback(record_id)")
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
        conn.commit()
        _migrate_records(conn, c)
        _migrate_feedback(conn, c)
        conn.commit()
    finally:
        conn.close()


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
    except Exception as e:
        import logging
        logging.getLogger("SymptoSense").error(f"log_visit failed for user {user_id}: {e!r}")
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


def save_record(user_id, lang, age, gender, symptoms, duration, severity, urgency, conditions=None, medications=None):
    conn = _conn()
    try:
        c = conn.cursor()
        if USE_POSTGRES:
            c.execute(
                f"INSERT INTO records (user_hash, timestamp, lang, age, gender, symptoms, conditions, medications, duration, severity, urgency) "
                f"VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH}) RETURNING id",
                (
                    _hash_user(user_id),
                    datetime.now(timezone.utc).isoformat(),
                    lang, age, gender,
                    ",".join(symptoms or []),
                    conditions or "", medications or "",
                    duration, severity, urgency,
                ),
            )
            rec_id = c.fetchone()[0]
        else:
            c.execute(
                f"INSERT INTO records (user_hash, timestamp, lang, age, gender, symptoms, conditions, medications, duration, severity, urgency) "
                f"VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})",
                (
                    _hash_user(user_id),
                    datetime.now(timezone.utc).isoformat(),
                    lang, age, gender,
                    ",".join(symptoms or []),
                    conditions or "", medications or "",
                    duration, severity, urgency,
                ),
            )
            rec_id = c.lastrowid
        conn.commit()
        return rec_id
    finally:
        conn.close()


def save_followup(user_id, record_id, outcome):
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"INSERT INTO followups (user_hash, record_id, timestamp, outcome) VALUES ({PH},{PH},{PH},{PH})",
            (_hash_user(user_id), record_id, datetime.now(timezone.utc).isoformat(), outcome),
        )
        conn.commit()
    finally:
        conn.close()


def _all_followups():
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            "SELECT id, record_id, timestamp, outcome FROM followups ORDER BY id"
        )
        return c.fetchall()
    finally:
        conn.close()


def save_daily_checkin(user_id, severity):
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"INSERT INTO daily_checkins (user_hash, timestamp, severity) VALUES ({PH},{PH},{PH})",
            (_hash_user(user_id), datetime.now(timezone.utc).isoformat(), int(severity)),
        )
        conn.commit()
    finally:
        conn.close()


def get_daily_checkins(user_id, days=7):
    """Returns [(date_str, avg_severity), ...] for the last N days, newest last."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"SELECT timestamp, severity FROM daily_checkins "
            f"WHERE user_hash={PH} AND timestamp >= {PH} ORDER BY timestamp",
            (_hash_user(user_id), since),
        )
        rows = c.fetchall()
    finally:
        conn.close()
    by_day = {}
    for ts, sev in rows:
        day = ts[:10]
        by_day.setdefault(day, []).append(sev)
    out = []
    for day in sorted(by_day):
        vals = by_day[day]
        out.append((day, round(sum(vals) / len(vals), 2)))
    return out


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


def save_feedback(user_id, record_id, rating, comment=None):
    conn = _conn()
    try:
        c = conn.cursor()
        c.execute(
            f"INSERT INTO feedback (user_hash, record_id, rating, comment, timestamp) VALUES ({PH},{PH},{PH},{PH},{PH})",
            (_hash_user(user_id), record_id, rating, comment, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


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
            except Exception:
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
