import source_bundle
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()
MK = (ROOT / "medical_knowledge.py").read_text(encoding="utf-8")
DB = (ROOT / "db.py").read_text(encoding="utf-8")
CORE = (ROOT / "analysis_core.py").read_text(encoding="utf-8")


class FinalV8StaticTests(unittest.TestCase):
    def test_root_keeps_language_picker_visible(self):
        # V107+: opening the root/PWA launch screen intentionally shows the
        # language picker every time; the explicit selection then persists.
        start = WEB.index('@app.route("/")')
        end = WEB.index('@app.route("/language/<code>"', start)
        block = WEB[start:end]
        self.assertIn("welcome_page()", block)
        self.assertNotIn('redirect(url_for("home")', block)
        self.assertIn('response.headers["Cache-Control"] = "no-store, max-age=0"', block)
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
        self.assertIn('matches=[] if risk["level"]=="urgent" else match_diseases(', MK)
        self.assertIn('negatives=all_negatives', MK)
        self.assertIn('gender=gender, age=age', MK)

    def test_analysis_record_and_result_use_one_transaction(self):
        self.assertIn('def save_analysis_record_with_result(', DB)
        self.assertIn('record_id = db.save_analysis_record_with_result(', CORE)

    def test_single_symptom_confidence_policy_not_relaxed(self):
        # v7 medical-confidence gate must remain unchanged by the speed work.
        self.assertIn('2+ canonical', CORE)
        self.assertIn('_displayable_matches(', CORE)
        self.assertIn('recognized_symptom_count=recognized_symptom_count', CORE)

    def test_no_design_or_landing_copy_change_marker(self):
        self.assertIn('افهم أعراضك<em>واعرف خطوتك التالية</em>', WEB)
        self.assertIn('Understand your symptoms<em>and know your next step</em>', WEB)


if __name__ == "__main__":
    unittest.main()
