"""Privacy-aware content-gap analytics for SymptoSense Admin.

This module intentionally keeps product-improvement signals separate from user
accounts. Search-gap rows never store a user/session id, and phrases are scrubbed
for obvious identifiers before storage. Logging is called only when the caller
has already verified optional analytics consent.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone

import db
import medical_knowledge

_READY_KEY = None

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_URL_RE = re.compile(r"\b(?:https?://|www\.)\S+", re.I)
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{6,}\d)(?!\d)")
_DIGIT_RE = re.compile(r"[0-9٠-٩۰-۹]+")
_SPACE_RE = re.compile(r"\s+")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def init_schema() -> None:
    global _READY_KEY
    db.init_db()
    key = db._database_identity()
    if _READY_KEY == key:
        return
    conn = db._conn()
    try:
        c = conn.cursor()
        serial = "SERIAL PRIMARY KEY" if db.USE_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"
        c.execute(f"""CREATE TABLE IF NOT EXISTS ss_search_gap_log (
            id {serial}, phrase_key TEXT NOT NULL, phrase_label TEXT NOT NULL,
            lang TEXT NOT NULL DEFAULT 'ar', created_at TEXT NOT NULL
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ss_search_gap_created ON ss_search_gap_log(created_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ss_search_gap_key ON ss_search_gap_log(phrase_key,lang)")
        conn.commit()
        _READY_KEY = key
    finally:
        conn.close()


def _scrub_phrase(value: str) -> str:
    """Keep an actionable search phrase while removing obvious identifiers.

    Search gaps are useful only when the wording can reveal a missing topic or
    alias. Numbers are removed because ages, phone numbers, dates and record
    values are not needed for that purpose.
    """
    text = " ".join(str(value or "").strip().split())[:240]
    if not text:
        return ""
    text = _EMAIL_RE.sub(" ", text)
    text = _URL_RE.sub(" ", text)
    text = _PHONE_RE.sub(" ", text)
    text = _DIGIT_RE.sub(" ", text)
    text = re.sub(r"[^A-Za-z\u0600-\u06FF\s\-_/]+", " ", text)
    text = _SPACE_RE.sub(" ", text).strip(" -_/\t\r\n")
    if len(text) < 2:
        return ""
    return text[:120]


def log_search_gap(query: str, lang: str = "ar") -> bool:
    """Record one anonymous, scrubbed no-match search phrase.

    Repeated identical searches are rate-limited to one row every five minutes
    so refreshes cannot dominate the Admin report.
    """
    phrase = _scrub_phrase(query)
    if not phrase:
        return False
    lang = "en" if lang == "en" else "ar"
    init_schema()
    key = hashlib.sha256((lang + "\0" + phrase.casefold()).encode("utf-8")).hexdigest()[:24]
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=5)).replace(microsecond=0).isoformat()
    conn = db._conn()
    try:
        c = conn.cursor()
        c.execute(
            f"SELECT 1 FROM ss_search_gap_log WHERE phrase_key={db.PH} AND lang={db.PH} AND created_at>={db.PH} LIMIT 1",
            (key, lang, cutoff),
        )
        if c.fetchone():
            return False
        c.execute(
            f"INSERT INTO ss_search_gap_log(phrase_key,phrase_label,lang,created_at) VALUES({db.PH},{db.PH},{db.PH},{db.PH})",
            (key, phrase, lang, _now()),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def search_gap_report(limit: int = 20, days: int = 30) -> list[dict]:
    init_schema()
    limit = max(1, min(int(limit or 20), 100))
    days = max(1, min(int(days or 30), 365))
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).replace(microsecond=0).isoformat()
    conn = db._conn()
    try:
        c = conn.cursor()
        c.execute(
            f"SELECT phrase_label,lang,COUNT(*) AS n,MAX(created_at) FROM ss_search_gap_log "
            f"WHERE created_at>={db.PH} GROUP BY phrase_key,phrase_label,lang ORDER BY n DESC,MAX(created_at) DESC LIMIT {db.PH}",
            (cutoff, limit),
        )
        return [
            {"phrase": r[0], "lang": r[1], "count": int(r[2] or 0), "last_seen": r[3]}
            for r in c.fetchall()
        ]
    finally:
        conn.close()


def _weak_source_conditions(limit: int = 20) -> list[dict]:
    medical_knowledge.init_schema()
    conn = db._conn()
    try:
        c = conn.cursor()
        c.execute(
            f"""SELECT d.id,d.slug,d.name_ar,d.name_en,COUNT(s.id) AS source_count
                FROM mk_diseases d
                LEFT JOIN mk_disease_sources ds ON ds.disease_id=d.id AND ds.status='active'
                LEFT JOIN mk_sources s ON s.id=ds.source_id AND s.status='active' AND s.verification_status='verified'
                WHERE d.status='active'
                GROUP BY d.id,d.slug,d.name_ar,d.name_en
                HAVING COUNT(s.id) < 2
                ORDER BY COUNT(s.id) ASC,d.id ASC
                LIMIT {db.PH}""",
            (max(1, min(int(limit or 20), 100)),),
        )
        return [
            {"id": int(r[0]), "slug": r[1], "name_ar": r[2], "name_en": r[3], "verified_source_count": int(r[4] or 0)}
            for r in c.fetchall()
        ]
    finally:
        conn.close()


def _unmapped_symptoms(limit: int = 20) -> list[dict]:
    medical_knowledge.init_schema()
    conn = db._conn()
    try:
        c = conn.cursor()
        c.execute(
            f"""SELECT s.id,s.slug,s.name_ar,s.name_en,
                       COUNT(DISTINCT ds.id) AS condition_links,
                       COUNT(DISTINCT src.id) AS verified_sources
                FROM mk_symptoms s
                LEFT JOIN mk_disease_symptoms ds ON ds.symptom_id=s.id AND ds.status='active'
                LEFT JOIN mk_symptom_sources ss ON ss.symptom_id=s.id AND ss.status='active'
                LEFT JOIN mk_sources src ON src.id=ss.source_id AND src.status='active' AND src.verification_status='verified'
                WHERE s.status='active'
                GROUP BY s.id,s.slug,s.name_ar,s.name_en
                HAVING COUNT(DISTINCT ds.id)=0 OR COUNT(DISTINCT src.id)=0
                ORDER BY COUNT(DISTINCT ds.id) ASC,COUNT(DISTINCT src.id) ASC,s.id ASC
                LIMIT {db.PH}""",
            (max(1, min(int(limit or 20), 100)),),
        )
        return [
            {
                "id": int(r[0]), "slug": r[1], "name_ar": r[2], "name_en": r[3],
                "condition_links": int(r[4] or 0), "verified_source_count": int(r[5] or 0),
            }
            for r in c.fetchall()
        ]
    finally:
        conn.close()




def _search_gap_summary(days: int) -> tuple[int, int]:
    init_schema()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).replace(microsecond=0).isoformat()
    conn = db._conn()
    try:
        c = conn.cursor()
        c.execute(
            f"SELECT COUNT(*),COUNT(DISTINCT phrase_key) FROM ss_search_gap_log WHERE created_at>={db.PH}",
            (cutoff,),
        )
        row = c.fetchone() or (0, 0)
        return int(row[0] or 0), int(row[1] or 0)
    finally:
        conn.close()


def _unmatched_symptom_occurrences(days: int) -> int:
    medical_knowledge.init_schema()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).replace(microsecond=0).isoformat()
    conn = db._conn()
    try:
        c = conn.cursor()
        c.execute(
            f"SELECT COUNT(*) FROM mk_unmatched_log WHERE matched=0 AND created_at>={db.PH}",
            (cutoff,),
        )
        row = c.fetchone()
        return int((row or [0])[0] or 0)
    finally:
        conn.close()


def _weak_source_condition_count() -> int:
    medical_knowledge.init_schema()
    conn = db._conn()
    try:
        c = conn.cursor()
        c.execute(
            """SELECT COUNT(*) FROM (
                 SELECT d.id,COUNT(s.id) AS source_count
                 FROM mk_diseases d
                 LEFT JOIN mk_disease_sources ds ON ds.disease_id=d.id AND ds.status='active'
                 LEFT JOIN mk_sources s ON s.id=ds.source_id AND s.status='active' AND s.verification_status='verified'
                 WHERE d.status='active' GROUP BY d.id HAVING COUNT(s.id)<2
               ) gap_rows"""
        )
        row = c.fetchone()
        return int((row or [0])[0] or 0)
    finally:
        conn.close()


def _coverage_gap_count() -> int:
    medical_knowledge.init_schema()
    conn = db._conn()
    try:
        c = conn.cursor()
        c.execute(
            """SELECT COUNT(*) FROM (
                 SELECT s.id
                 FROM mk_symptoms s
                 LEFT JOIN mk_disease_symptoms ds ON ds.symptom_id=s.id AND ds.status='active'
                 LEFT JOIN mk_symptom_sources ss ON ss.symptom_id=s.id AND ss.status='active'
                 LEFT JOIN mk_sources src ON src.id=ss.source_id AND src.status='active' AND src.verification_status='verified'
                 WHERE s.status='active'
                 GROUP BY s.id
                 HAVING COUNT(DISTINCT ds.id)=0 OR COUNT(DISTINCT src.id)=0
               ) gap_rows"""
        )
        row = c.fetchone()
        return int((row or [0])[0] or 0)
    finally:
        conn.close()


def report(days: int = 30, limit: int = 20) -> dict:
    """Build one actionable, privacy-aware content-gap report for Admin."""
    days = max(1, min(int(days or 30), 365))
    limit = max(1, min(int(limit or 20), 100))
    search_gaps = search_gap_report(limit=limit, days=days)
    unmatched = medical_knowledge.unmatched_symptom_report(limit=limit, days=days)
    search_occurrences, unique_search_gaps = _search_gap_summary(days)
    unmatched_occurrences = _unmatched_symptom_occurrences(days)
    weak_conditions = _weak_source_conditions(limit=limit)
    weak_condition_count = _weak_source_condition_count()
    unmapped = _unmapped_symptoms(limit=limit)
    coverage_gap_count = _coverage_gap_count()
    review = medical_knowledge.periodic_review_status()
    queue = (review.get("queue") or [])[:limit]
    assistant = db.assistant_feedback_stats()
    unmet = [x for x in (assistant.get("reasons") or []) if x.get("reason") in {"not_answered", "need_more", "not_relevant", "unclear"}]
    return {
        "generated_at": _now(),
        "days": days,
        "summary": {
            "search_gap_occurrences": search_occurrences,
            "unique_search_gaps": unique_search_gaps,
            "unmatched_symptom_occurrences": unmatched_occurrences,
            "weak_source_conditions": weak_condition_count,
            "coverage_items": coverage_gap_count,
            "review_due": len(review.get("queue") or []),
            "assistant_unmet_feedback": sum(int(x.get("count") or 0) for x in unmet),
        },
        "search_gaps": search_gaps,
        "unmatched_symptoms": unmatched,
        "weak_source_conditions": weak_conditions,
        "coverage_gaps": unmapped,
        "review_queue": queue,
        "assistant_unmet_reasons": unmet,
        "privacy": {
            "search_gap_user_ids_stored": False,
            "search_gap_session_ids_stored": False,
            "search_gap_obvious_identifiers_scrubbed": True,
            "assistant_message_text_stored": False,
        },
    }
