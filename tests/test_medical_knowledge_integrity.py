"""
Guards the integrity of the medical knowledge base (medical_knowledge.py).

These tests do not replace clinical review. What they catch:

1. Structural mistakes: a disease referencing a symptom slug that does not
   exist (typo / dangling reference), invalid weights, duplicate slugs, or
   an unknown category.

2. Careless or automated symptom<->disease linking: a curated denylist of
   pairs that must never appear together because they contradict basic,
   uncontroversial medical consensus (e.g. a respiratory illness should not
   be "linked" to hair loss just to make a match look more specific). If a
   contributor ever adds a shortcut that links many unrelated symptoms to a
   disease purely to force a result, this test is designed to catch it.

3. Regression of the specific, source-verified associations added on
   2026-09-11: each entry below was checked against Mayo Clinic and/or
   Cleveland Clinic material describing that symptom as part of the
   condition's recognized presentation. If a future edit silently removes
   or swaps one of these, this test fails.

Adding a new symptom<->disease association should come with: (a) a citation
or well-known clinical source in the PR/commit description, and (b) ideally
a new entry in VERIFIED_ASSOCIATIONS below so the link is protected against
accidental removal too.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "mk_integrity.db")

import db  # noqa: E402
db.DB_PATH = os.environ["DB_PATH"]

import medical_knowledge as mk  # noqa: E402


class MedicalKnowledgeIntegrityTest(unittest.TestCase):

    def test_every_disease_symptom_reference_exists(self):
        known_slugs = {s[0] for s in mk.SYMPTOMS}
        for disease in mk.DISEASES:
            for symptom_slug in disease["symptoms"]:
                self.assertIn(
                    symptom_slug, known_slugs,
                    f"{disease['slug']} references unknown symptom '{symptom_slug}' "
                    "(typo or dangling reference to a symptom that doesn't exist)."
                )

    def test_disease_symptom_weights_are_valid(self):
        for disease in mk.DISEASES:
            for symptom_slug, weight in disease["symptoms"].items():
                self.assertIsInstance(weight, (int, float), f"{disease['slug']}/{symptom_slug} weight must be numeric")
                self.assertGreater(weight, 0, f"{disease['slug']}/{symptom_slug} weight must be > 0")
                self.assertLessEqual(weight, 1, f"{disease['slug']}/{symptom_slug} weight must be <= 1")

    def test_every_symptom_has_a_known_category(self):
        known_categories = {c[0] for c in mk.CATEGORIES}
        for slug, _ar, _en, category, _aliases_ar, _aliases_en in mk.SYMPTOMS:
            self.assertIn(category, known_categories, f"symptom '{slug}' has unknown category '{category}'")

    def test_no_duplicate_symptom_slugs(self):
        slugs = [s[0] for s in mk.SYMPTOMS]
        dupes = {s for s in slugs if slugs.count(s) > 1}
        self.assertEqual(dupes, set(), f"duplicate symptom slugs found: {dupes}")

    def test_no_duplicate_disease_slugs(self):
        slugs = [d["slug"] for d in mk.DISEASES]
        dupes = {s for s in slugs if slugs.count(s) > 1}
        self.assertEqual(dupes, set(), f"duplicate disease slugs found: {dupes}")

    def test_every_symptom_has_arabic_and_english_names(self):
        for slug, ar, en, _category, _aliases_ar, _aliases_en in mk.SYMPTOMS:
            self.assertTrue(ar and ar.strip(), f"symptom '{slug}' is missing an Arabic name")
            self.assertTrue(en and en.strip(), f"symptom '{slug}' is missing an English name")

    # ------------------------------------------------------------------
    # Guard-rail: pairs that must never exist because they contradict basic
    # medical consensus. Not exhaustive — a tripwire against careless or
    # random symptom<->disease linking, not a substitute for clinical review.
    # ------------------------------------------------------------------
    IMPLAUSIBLE_PAIRS = [
        ("common-cold", "hair-loss"),
        ("common-cold", "seizure"),
        ("common-cold", "leg-swelling"),
        ("food-poisoning", "hair-loss"),
        ("food-poisoning", "tinnitus"),
        ("food-poisoning", "wrist-pain"),
        ("viral-gastroenteritis", "ear-pain"),
        ("viral-gastroenteritis", "hair-loss"),
        ("asthma", "abdominal-cramps"),
        ("asthma", "tooth-pain"),
        ("asthma", "hair-loss"),
        ("migraine", "diarrhea"),
        ("migraine", "swelling"),
        ("migraine", "hair-loss"),
        ("carpal-tunnel-syndrome", "sore-throat"),
        ("carpal-tunnel-syndrome", "fever"),
        ("carpal-tunnel-syndrome", "diarrhea"),
        ("sciatica", "cough"),
        ("sciatica", "skin-rash"),
        ("sciatica", "sore-throat"),
        ("acute-sinusitis", "leg-pain"),
        ("acute-sinusitis", "hair-loss"),
        ("acute-bronchitis", "wrist-pain"),
        ("acute-bronchitis", "hair-loss"),
        ("influenza", "hair-loss"),
        ("influenza", "wrist-pain"),
        ("peripheral-neuropathy", "sore-throat"),
        ("peripheral-neuropathy", "phlegm"),
    ]

    def test_no_implausible_symptom_disease_pairs(self):
        by_slug = {d["slug"]: d for d in mk.DISEASES}
        for disease_slug, symptom_slug in self.IMPLAUSIBLE_PAIRS:
            disease = by_slug.get(disease_slug)
            if not disease:
                continue
            self.assertNotIn(
                symptom_slug, disease["symptoms"],
                f"'{symptom_slug}' should not be linked to '{disease_slug}' — this pair "
                "contradicts basic medical consensus and likely indicates an "
                "accidental or unreviewed addition."
            )

    # ------------------------------------------------------------------
    # Positive guard-rail: associations reviewed against Mayo Clinic /
    # Cleveland Clinic (or basic, uncontested clinical consensus for very
    # well-known hallmark symptoms) on 2026-09-11. A future edit cannot
    # silently drop or swap one of these without a test failing.
    # ------------------------------------------------------------------
    VERIFIED_ASSOCIATIONS = {
        ("sciatica", "back-pain"):
            "Mayo Clinic / Cleveland Clinic: sciatica pain originates in the "
            "lower back (nerve root compression) and radiates down the leg.",
        ("peripheral-neuropathy", "burning-sensation"):
            "Mayo Clinic: burning sensation/pain is explicitly listed as a "
            "hallmark symptom of peripheral neuropathy (e.g. Mayo's 'burning "
            "feet' symptom page names peripheral neuropathy as the leading cause).",
        ("carpal-tunnel-syndrome", "wrist-pain"):
            "Cleveland Clinic: carpal tunnel syndrome 'usually first causes "
            "symptoms like wrist pain and tingling at night'.",
        ("common-cold", "sneezing"):
            "Mainstream clinical consensus (Mayo Clinic/CDC): sneezing is a "
            "hallmark common-cold symptom.",
        ("common-cold", "nasal-congestion"):
            "Mainstream clinical consensus: nasal congestion is a hallmark "
            "common-cold symptom.",
        ("acute-sinusitis", "sinus-pressure"):
            "Mainstream clinical consensus: facial/sinus pressure is a "
            "hallmark sinusitis symptom.",
        ("acute-bronchitis", "phlegm"):
            "Mainstream clinical consensus: a productive cough with phlegm "
            "is a hallmark bronchitis symptom.",
        ("food-poisoning", "abdominal-cramps"):
            "Mainstream clinical consensus: cramping is a hallmark "
            "food-poisoning symptom.",
        ("viral-gastroenteritis", "abdominal-cramps"):
            "Mainstream clinical consensus: cramping is a hallmark "
            "gastroenteritis symptom.",
        ("asthma", "rapid-breathing"):
            "Mainstream clinical consensus: rapid breathing (tachypnea) is a "
            "recognized sign of an asthma flare-up.",
        ("migraine", "blurred-vision"):
            "Mainstream clinical consensus: visual disturbance/aura is a "
            "recognized migraine feature.",
    }

    def test_verified_associations_are_present(self):
        by_slug = {d["slug"]: d for d in mk.DISEASES}
        for (disease_slug, symptom_slug), _source in self.VERIFIED_ASSOCIATIONS.items():
            disease = by_slug.get(disease_slug)
            self.assertIsNotNone(disease, f"expected disease '{disease_slug}' not found")
            self.assertIn(
                symptom_slug, disease["symptoms"],
                f"expected verified association '{symptom_slug}' -> '{disease_slug}' "
                f"is missing ({_source})"
            )

    def test_seeded_database_reflects_these_associations(self):
        """End-to-end check: after init_schema(), the actual mk_disease_symptoms
        rows in the database contain the verified associations too — not just
        the in-memory Python list."""
        mk.init_schema()
        conn = db._conn()
        try:
            c = conn.cursor()
            c.execute(
                "SELECT d.slug, s.slug FROM mk_disease_symptoms ds "
                "JOIN mk_diseases d ON d.id = ds.disease_id "
                "JOIN mk_symptoms s ON s.id = ds.symptom_id"
            )
            pairs = set(c.fetchall())
        finally:
            conn.close()
        for disease_slug, symptom_slug in self.VERIFIED_ASSOCIATIONS:
            self.assertIn(
                (disease_slug, symptom_slug), pairs,
                f"'{symptom_slug}' -> '{disease_slug}' is in the Python data but "
                "was not found in the seeded database."
            )


if __name__ == "__main__":
    unittest.main()
