import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEBAPP = (ROOT / "webapp.py").read_text(encoding="utf-8")
DB = (ROOT / "db.py").read_text(encoding="utf-8")
SW = (ROOT / "service-worker.js").read_text(encoding="utf-8")
RAILWAY = (ROOT / "railway.json").read_text(encoding="utf-8")


class CompetitionReadinessStaticTests(unittest.TestCase):
    def test_first_language_gate_does_not_block_public_assets_or_health(self):
        self.assertIn('path.startswith("/static/")', WEBAPP)
        self.assertIn('"/brand-icon.svg"', WEBAPP)
        self.assertIn('"/health"', WEBAPP)
        self.assertIn('"/healthz"', WEBAPP)

    def test_pwa_install_is_resilient_to_one_missing_asset(self):
        self.assertNotIn("cache.addAll(APP_SHELL)", SW)
        self.assertIn("Promise.allSettled", SW)
        self.assertIn("/icons/icon-192.png", SW)
        self.assertTrue((ROOT / "icons" / "icon-192.png").exists())
        self.assertTrue((ROOT / "icons" / "icon-512.png").exists())
        self.assertTrue((ROOT / "static" / "images" / "symptosense-social-preview.png").exists())

    def test_healthcheck_uses_health_endpoint(self):
        self.assertIn('"healthcheckPath": "/health"', RAILWAY)

    def test_csp_is_enforced_not_report_only(self):
        self.assertIn('"Content-Security-Policy",', WEBAPP)
        self.assertNotIn('"Content-Security-Policy-Report-Only",', WEBAPP)

    def test_owner_email_is_not_hardcoded(self):
        self.assertIn('os.environ.get("SYMPTOSENSE_ADMIN_EMAIL"', DB)
        self.assertNotIn("remasalsolami2020@gmail.com", DB)

    def test_missing_admin_env_does_not_demote_persisted_admin(self):
        self.assertIn("existing persisted Admin access is preserved", DB)
        self.assertIn("if OWNER_ADMIN_EMAIL:", DB)
        self.assertIn('role = "admin" if str(row[3] or "user").strip().lower() == "admin" else "user"', DB)

    def test_fainting_keeps_canonical_symptom(self):
        self.assertNotIn("add:['إغماء مع فقدان وعي'", WEBAPP)
        self.assertIn('"slug":"syncope"', WEBAPP)
        self.assertIn('"قرب الإغماء أو خفة شديدة بالرأس"', WEBAPP)

    def test_question_flow_is_monotonic_and_current_question_only(self):
        self.assertIn("let highestFlowStep = 1;", WEBAPP)
        self.assertIn("Math.max(highestFlowStep", WEBAPP)
        self.assertIn("ملخص إجاباتك", WEBAPP)

    def test_assistant_has_retry_and_local_natural_language_fallback(self):
        self.assertIn("def _groq_chat_completion_with_retry", WEBAPP)
        self.assertIn("def _assistant_general_local_fallback", WEBAPP)
        self.assertIn('"طقط"', WEBAPP)

    def test_dynamic_manifest_matches_language(self):
        self.assertIn('"lang": "ar" if ar else "en"', WEBAPP)
        self.assertIn('"dir": "rtl" if ar else "ltr"', WEBAPP)

    def test_competition_build_labels_public_metrics_as_pilot(self):
        self.assertIn("الاختبار الأولي للمستخدمين — Pilot", WEBAPP)
        self.assertIn('SHOW_PUBLIC_PILOT_COMMENTS', WEBAPP)

    def test_privacy_has_provider_and_retention_disclosures(self):
        self.assertIn("مزودو الخدمة ومكان المعالجة", WEBAPP)
        self.assertIn("الاحتفاظ والحذف", WEBAPP)
        self.assertIn("إصدار سياسة الخصوصية 1.0", WEBAPP)

    def test_report_blob_url_is_not_revoked_immediately(self):
        self.assertIn("SymptoSense_Report_", WEBAPP)
        self.assertIn("60000", WEBAPP)


if __name__ == "__main__":
    unittest.main()
