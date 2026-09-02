"""Regression tests for the disease-matching confidence scoring in medical_knowledge.py.

These guard the two behavioral fixes:
1. A disease's match score must not be diluted just because the user entered many
   unrelated symptoms elsewhere (the old `user_coverage` metric divided by the
   user's TOTAL symptom count, which unfairly penalized detailed symptom entry).
2. A disease must not be forced to "moderate" confidence purely because 3+ generic,
   low-weight symptoms happened to match, regardless of the actual score.
"""
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

_TEMP = tempfile.TemporaryDirectory(prefix="symptosense-matching-")
os.environ.pop("DATABASE_URL", None)
os.environ["DB_PATH"] = str(Path(_TEMP.name) / "matching.sqlite3")
os.environ["WEB_SECRET"] = "matching-test-secret-more-than-32-characters"
os.environ["SITE_URL"] = "http://localhost"
os.environ["SESSION_COOKIE_SECURE"] = "0"

import db
import medical_knowledge as mk


def _now():
    return datetime.now(timezone.utc).isoformat()


def _seed_disease(conn, slug, name, symptom_weights):
    """Create a disease with the given {symptom_slug: weight} map and one verified source.
    Returns the disease id."""
    c = conn.cursor()
    now = _now()
    c.execute(
        f"INSERT INTO mk_diseases (slug,name_ar,name_en,description_ar,description_en,"
        f"recommended_next_step_ar,recommended_next_step_en,last_updated,status,created_at,updated_at) "
        f"VALUES ({','.join([db.PH]*11)})",
        (slug, name, name, "d", "d", "n", "n", now, "active", now, now),
    )
    conn.commit()
    c.execute(f"SELECT id FROM mk_diseases WHERE slug={db.PH}", (slug,))
    disease_id = int(c.fetchone()[0])

    for sym_slug, weight in symptom_weights.items():
        c.execute(f"SELECT id FROM mk_symptoms WHERE slug={db.PH}", (sym_slug,))
        row = c.fetchone()
        if row:
            symptom_id = int(row[0])
        else:
            c.execute(
                f"INSERT INTO mk_symptoms (slug,name_ar,name_en,description_ar,description_en,"
                f"aliases_ar,aliases_en,status,created_at,updated_at) VALUES ({','.join([db.PH]*10)})",
                (sym_slug, sym_slug, sym_slug, "d", "d", "[]", "[]", "active", now, now),
            )
            conn.commit()
            c.execute(f"SELECT id FROM mk_symptoms WHERE slug={db.PH}", (sym_slug,))
            symptom_id = int(c.fetchone()[0])
        c.execute(
            f"INSERT INTO mk_disease_symptoms (disease_id,symptom_id,weight,typicality,status,created_at,updated_at) "
            f"VALUES ({','.join([db.PH]*7)})",
            (disease_id, symptom_id, weight, "common", "active", now, now),
        )
        conn.commit()

    # A verified, active source is required for a disease to appear in results at all.
    c.execute(
        f"INSERT INTO mk_sources (slug,source_name,organization,official_url,source_type,"
        f"reliability_level,verification_status,status,created_at,updated_at) VALUES ({','.join([db.PH]*10)})",
        (slug + "-src", "Test Source", "Test Org", "https://example.org", "guideline",
         "high", "verified", "active", now, now),
    )
    conn.commit()
    c.execute(f"SELECT id FROM mk_sources WHERE slug={db.PH}", (slug + "-src",))
    source_id = int(c.fetchone()[0])
    c.execute(
        f"INSERT INTO mk_disease_sources (disease_id,source_id,reference_title_ar,reference_title_en,"
        f"reference_url,status,created_at,updated_at) VALUES ({','.join([db.PH]*8)})",
        (disease_id, source_id, "t", "t", "https://example.org/ref", "active", now, now),
    )
    conn.commit()
    return disease_id


def _canonical(slugs):
    """Build a canonical symptom list matching mk.match_diseases' expected input shape."""
    conn = db._conn()
    c = conn.cursor()
    out = []
    for slug in slugs:
        c.execute(f"SELECT id,slug,name_ar,name_en FROM mk_symptoms WHERE slug={db.PH}", (slug,))
        row = c.fetchone()
        out.append({"symptom_id": row[0], "slug": row[1], "name_ar": row[2], "name_en": row[3]})
    return out


class SymptomMatchingScoreTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        mk.init_schema()

    def test_extra_unrelated_symptoms_do_not_dilute_a_strong_match(self):
        """Entering more (unrelated) symptoms elsewhere must not weaken a disease's own score."""
        conn = db._conn()
        _seed_disease(conn, "cond-a", "Condition A", {
            "sym-a1": 0.9, "sym-a2": 0.8, "sym-a3": 0.3, "sym-a4": 0.2,
        })
        for i in range(6):
            _seed_disease(conn, f"filler-{i}", f"Filler {i}", {f"sym-filler-{i}": 0.5})

        canonical_focused = _canonical(["sym-a1", "sym-a2"])
        result_focused = mk.match_diseases(canonical_focused, lang="ar", limit=20)
        match_focused = next(m for m in result_focused if m["slug"] == "cond-a")

        canonical_with_noise = _canonical(
            ["sym-a1", "sym-a2"] + [f"sym-filler-{i}" for i in range(6)]
        )
        result_noisy = mk.match_diseases(canonical_with_noise, lang="ar", limit=20)
        match_noisy = next(m for m in result_noisy if m["slug"] == "cond-a")

        # _score is stripped from the public result before it's returned, so we compare
        # the derived match_level (and matched symptom set) instead, which is what the
        # bug actually affected: unrelated extra symptoms must not weaken this disease's level.
        self.assertEqual(match_focused["match_level"], "strong")
        self.assertEqual(match_noisy["match_level"], "strong")
        self.assertEqual(
            {s["slug"] for s in match_focused["matched_symptoms"]},
            {s["slug"] for s in match_noisy["matched_symptoms"]},
        )

    def test_generic_low_weight_symptoms_do_not_force_moderate(self):
        """3+ matched symptoms alone must not guarantee 'moderate' if the weighted score is low."""
        conn = db._conn()
        _seed_disease(conn, "cond-b", "Condition B", {
            "sym-b1": 0.2, "sym-b2": 0.2, "sym-b3": 0.2, "sym-b4": 0.6, "sym-b5": 0.6,
        })
        canonical = _canonical(["sym-b1", "sym-b2", "sym-b3"])
        result = mk.match_diseases(canonical, lang="ar", limit=20)
        match = next(m for m in result if m["slug"] == "cond-b")

        self.assertEqual(match["match_level"], "weak")


if __name__ == "__main__":
    unittest.main()
