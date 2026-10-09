"""Anonymous log of triage decisions (audit of the safety layer).

Stores ONLY: hour-bucketed UTC time, decision level, the rule ids that fired,
interface language and which endpoint decided.  Never the symptom text, user,
session, IP or device, so the table cannot be linked back to a person.
Failures never affect the user-facing request.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import db

_LOG = logging.getLogger("SymptoSense")
_READY = False
LEVELS = ("emergency", "high", "medium", "low")


def _ensure(conn):
    global _READY
    if _READY:
        return
    conn.cursor().execute(
        "CREATE TABLE IF NOT EXISTS ss_safety_decisions ("
        "ts TEXT NOT NULL, level TEXT NOT NULL, rule_ids TEXT NOT NULL, lang TEXT, source TEXT)"
    )
    conn.commit()
    _READY = True


def _clean_rules(rule_ids):
    out = []
    for r in rule_ids or []:
        r = str(r or "").strip()[:60]
        if r and all(ch.isalnum() or ch in "_-." for ch in r) and r not in out:
            out.append(r)
    return out[:8]


def record(level, rule_ids=(), lang="ar", source="analyze"):
    """Record one decision. Returns True when stored."""
    level = str(level or "").lower()
    level = level if level in LEVELS else "low"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:00:00Z")  # hour bucket only
    conn = None
    try:
        conn = db._conn()
        _ensure(conn)
        conn.cursor().execute(
            f"INSERT INTO ss_safety_decisions (ts, level, rule_ids, lang, source) VALUES ({db.PH},{db.PH},{db.PH},{db.PH},{db.PH})",
            (ts, level, ",".join(_clean_rules(rule_ids)), "en" if lang == "en" else "ar", str(source or "")[:30]),
        )
        conn.commit()
        return True
    except Exception as exc:  # pragma: no cover - logging must never break triage
        _LOG.warning("decision_log.record failed: error_type=%s", type(exc).__name__)
        return False
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def summary(limit_rules=15):
    """Aggregate counts for the admin review screen."""
    conn = None
    try:
        conn = db._conn()
        _ensure(conn)
        c = conn.cursor()
        c.execute("SELECT level, COUNT(*) FROM ss_safety_decisions GROUP BY level")
        by_level = {str(k): int(v) for k, v in c.fetchall()}
        c.execute("SELECT rule_ids, COUNT(*) FROM ss_safety_decisions WHERE rule_ids <> '' GROUP BY rule_ids")
        rules = {}
        for ids, n in c.fetchall():
            for rid in str(ids).split(","):
                rules[rid] = rules.get(rid, 0) + int(n)
        c.execute("SELECT MIN(ts), MAX(ts), COUNT(*) FROM ss_safety_decisions")
        first, last, total = c.fetchone()
        return {
            "total": int(total or 0), "first": first, "last": last, "by_level": by_level,
            "top_rules": sorted(rules.items(), key=lambda kv: -kv[1])[:limit_rules],
        }
    except Exception as exc:
        _LOG.warning("decision_log.summary failed: error_type=%s", type(exc).__name__)
        return {"total": 0, "first": None, "last": None, "by_level": {}, "top_rules": []}
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
