import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
WEB = (ROOT / "webapp.py").read_text(encoding="utf-8")
MK = (ROOT / "medical_knowledge.py").read_text(encoding="utf-8")
DB = (ROOT / "db.py").read_text(encoding="utf-8")
CORE = (ROOT / "analysis_core.py").read_text(encoding="utf-8")


class FinalV8StaticTests(unittest.TestCase):
    def test_root_returns_standalone_welcome_directly(self):
        self.assertIn('return welcome_page()', WEB)
        self.assertIn('bare=True, extra_css=LANG_PICKER_CSS', WEB)

    def test_root_is_not_cacheable(self):
        self.assertIn('response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"', WEB)
        self.assertIn('response.headers["X-SymptoSense-Landing"] = "bare-v8"', WEB)

    def test_root_skips_global_login_injection(self):
        self.assertIn('if request.path == "/":\n            return response', WEB)

    def test_consent_is_cached_per_request(self):
        self.assertIn('_ss_consent_state_cache', WEB)
        self.assertIn('consent = _consent_state()', WEB)

    def test_knowledge_bundle_reuses_one_connection(self):
        self.assertIn('norm=normalize_symptoms(raw_symptoms,lang,conn=conn)', MK)
        self.assertIn('risk=evaluate_risk(norm["canonical"],raw_symptoms,notes,severity,age,lang,conn=conn)', MK)
        self.assertIn('match_diseases(norm["canonical"],lang,negatives=negatives,conn=conn)', MK)

    def test_analysis_record_and_result_use_one_transaction(self):
        self.assertIn('def save_analysis_record_with_result(', DB)
        self.assertIn('record_id = db.save_analysis_record_with_result(', CORE)

    def test_single_symptom_confidence_policy_not_relaxed(self):
        # v7 medical-confidence gate must remain unchanged by the speed work.
        self.assertIn('2+ canonical', CORE)
        self.assertIn('_displayable_matches(all_matches, data_quality)', CORE)

    def test_no_design_or_landing_copy_change_marker(self):
        self.assertIn('افهم أعراضك.<br>اعرف خطوتك التالية.', WEB)
        self.assertIn('Understand your symptoms.<br>Know your next step.', WEB)


if __name__ == "__main__":
    unittest.main()
