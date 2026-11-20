"""Single source of truth for public knowledge-base counts (V68.15).

Every public page (home, how-we-work, library, trust, English pages) must read
these numbers from get_kb_stats() so they can never disagree.

Definitions (all rows must have status='active'):
  sources       verified sources only
  symptoms      active symptoms
  conditions    active diseases
  red_flags     active red-flag rules
  links         active condition-symptom links
  symptoms_linked  active symptoms that have at least one active link
"""
import logging

_KEYS = ("sources", "symptoms", "conditions", "red_flags", "links", "symptoms_linked")


def _from_db():
    import db
    import medical_knowledge
    medical_knowledge.init_schema()
    conn = db._conn()
    try:
        c = conn.cursor()

        def one(sql):
            c.execute(sql)
            row = c.fetchone()
            return int((row or [0])[0] or 0)

        return {
            "sources": one("SELECT COUNT(*) FROM mk_sources WHERE status='active' AND verification_status='verified'"),
            "symptoms": one("SELECT COUNT(*) FROM mk_symptoms WHERE status='active'"),
            "conditions": one("SELECT COUNT(*) FROM mk_diseases WHERE status='active'"),
            "red_flags": one("SELECT COUNT(*) FROM mk_red_flags WHERE status='active'"),
            "links": one("SELECT COUNT(*) FROM mk_disease_symptoms WHERE status='active'"),
            "symptoms_linked": one(
                "SELECT COUNT(DISTINCT s.id) FROM mk_symptoms s JOIN mk_disease_symptoms ds "
                "ON ds.symptom_id=s.id AND ds.status='active' WHERE s.status='active'"),
        }
    finally:
        conn.close()


def get_kb_stats():
    """Return the canonical counts. Never raises; 'origin' tells where they came from."""
    try:
        data = _from_db()
        if data["symptoms"] or data["conditions"] or data["sources"]:
            data["origin"] = "database"
            return data
    except Exception as exc:  # pragma: no cover - defensive
        logging.getLogger(__name__).warning("kb_stats db read failed: %s", type(exc).__name__)
    data = {k: 0 for k in _KEYS}
    data["origin"] = "unavailable"
    return data
