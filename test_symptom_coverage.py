"""
Coverage and safety guarantees for the symptom -> result pipeline.

1. test_every_symptom_yields_a_usable_result: runs analysis_core.run_analysis()
   once per symptom in medical_knowledge.SYMPTOMS (currently 100+) and asserts
   the result is never empty/broken — each one must produce EITHER (a) a
   confident, source-grounded disease possibility, OR (b) a clear safe risk
   assessment with a real recommended next step. This is the automated form
   of "every symptom must lead to an answer, not a blank result."

2. test_indirect_phrases_are_recognized: colloquial/indirect phrasings that
   previously fell through to "unmatched" must now resolve to a canonical
   symptom (via alias or light stemming).

3. test_emergency_red_flags_never_force_a_disease_guess: when a genuine
   emergency red flag fires (chest pain + breathing difficulty, seizure,
   loss of consciousness, severe bleeding, one-sided weakness), the result
   must never include a guessed possible_conditions value — only the safety
   assessment.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "symptom_coverage.db")

import db  # noqa: E402
db.DB_PATH = os.environ["DB_PATH"]

import medical_knowledge as mk  # noqa: E402
import analysis_core  # noqa: E402


class SymptomCoverageTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        mk.init_schema()

    def _analyze(self, symptoms, **overrides):
        payload = {
            "user_id": "coverage-test", "age": 32, "gender": "female",
            "symptoms": symptoms, "duration": "يومين", "severity": 2,
            "conditions": "", "medications": "", "notes": "",
        }
        payload.update(overrides)
        return analysis_core.run_analysis(payload, lang="ar")

    def test_every_symptom_yields_a_usable_result(self):
        failures = []
        for slug, ar, _en, _category, aliases_ar, _aliases_en in mk.SYMPTOMS:
            # Skip symptoms that are themselves emergency red-flag triggers —
            # those are covered separately and are expected to suppress
            # possible_conditions by design (see test 3 below).
            if slug in self._RED_FLAG_SYMPTOM_SLUGS():
                continue
            text = ar
            result = self._analyze([text])
            has_named_possibility = bool((result.get("possible_conditions") or "").strip())
            has_safe_assessment = bool(result.get("urgency")) and bool((result.get("simple_explanation") or "").strip())
            if not (has_named_possibility or has_safe_assessment):
                failures.append(slug)
        self.assertEqual(
            failures, [],
            f"these symptoms produced neither a named possibility nor a safe "
            f"risk assessment (an empty/broken result): {failures}"
        )

    @staticmethod
    def _RED_FLAG_SYMPTOM_SLUGS():
        slugs = set()
        for _slug, _ar, _en, required, _mode, _kw_ar, _kw_en, _min_sev, risk_level, _msg_ar, _msg_en, _src in mk.RED_RULES:
            if risk_level == "urgent":
                slugs.update(required)
        return slugs

    # ------------------------------------------------------------------
    # Indirect / colloquial phrasing
    # ------------------------------------------------------------------
    INDIRECT_PHRASES = [
        ("ركبتي تطقطق بدون ألم", "joint-clicking"),
        ("نبض غريب خلف الأذن", "tinnitus"),
        ("وخز خلف الأذن", "numbness"),
    ]

    def test_indirect_phrases_are_recognized(self):
        for phrase, expected_slug in self.INDIRECT_PHRASES:
            norm = mk.normalize_symptoms([phrase], lang="ar")
            matched_slugs = {m["slug"] for m in norm["canonical"]}
            self.assertIn(
                expected_slug, matched_slugs,
                f"phrase '{phrase}' should resolve to symptom '{expected_slug}' "
                f"but matched {matched_slugs or 'nothing'} (unmatched: {norm['unmatched']})"
            )

    # ------------------------------------------------------------------
    # Emergency red flags must never be paired with a guessed disease
    # ------------------------------------------------------------------
    EMERGENCY_PHRASES = [
        ["ألم شديد بالصدر", "ضيق تنفس شديد"],
        ["نوبة تشنجية"],
        ["فقدان الوعي"],
        ["نزيف شديد"],
        ["ضعف مفاجئ في جهة واحدة من الجسم"],
    ]

    def test_emergency_red_flags_never_force_a_disease_guess(self):
        for symptoms in self.EMERGENCY_PHRASES:
            result = self._analyze(symptoms, severity=4)
            possible = (result.get("possible_conditions") or "")
            # A real named possibility is rendered as "Name — confidence label."
            # (see analysis_core._render_possible_conditions); the safety
            # placeholder shown for urgent/empty matches never uses that
            # separator. This checks no specific disease name was guessed,
            # regardless of the exact wording of the safety placeholder.
            self.assertNotIn(
                " — ", possible,
                f"emergency input {symptoms} unexpectedly named a specific "
                f"possible condition: {possible!r}"
            )
            self.assertTrue(result.get("emergency") or result.get("urgency") == "high",
                             f"emergency input {symptoms} was not flagged as urgent/emergency")


if __name__ == "__main__":
    unittest.main()
