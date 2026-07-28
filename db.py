import os
import sqlite3
import hashlib
from datetime import datetime, timedelta, timezone
from collections import Counter

DB_PATH = os.environ.get("DB_PATH", "symptosense.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
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
    conn.commit()
    conn.close()


def _hash_user(user_id) -> str:
    # One-way hash so we never store the real Telegram user id.
    salt = os.environ.get("HASH_SALT", "symptosense")
    return hashlib.sha256(f"{salt}:{user_id}".encode()).hexdigest()[:16]


def get_last_record(user_id):
    """Returns the most recent PREVIOUS record for this user, or None."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT timestamp, symptoms, severity, duration, urgency "
        "FROM records WHERE user_hash=? ORDER BY id DESC LIMIT 1",
        (_hash_user(user_id),),
    )
    row = c.fetchone()
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
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO records (user_hash, timestamp, lang, age, gender, symptoms, duration, severity, urgency) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (
            _hash_user(user_id),
            datetime.now(timezone.utc).isoformat(),
            lang, age, gender,
            ",".join(symptoms or []),
            duration, severity, urgency,
        ),
    )
    conn.commit()
    conn.close()


def get_trends(days=7):
    """Returns (Counter of symptom -> count, total_sessions) for the last N days."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    c.execute("SELECT symptoms FROM records WHERE timestamp >= ?", (since,))
    rows = c.fetchall()
    conn.close()
    counter = Counter()
    for (symptoms_str,) in rows:
        for s in symptoms_str.split(","):
            s = s.strip()
            if s:
                counter[s] += 1
    return counter, len(rows)
