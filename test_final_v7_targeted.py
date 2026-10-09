import source_bundle
import json
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _run_python(code):
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=True,
    )
    return proc.stdout.strip()


class FinalV7TargetedRegressionTests(unittest.TestCase):
    def test_headache_nausea_can_show_trusted_low_match_instead_of_empty_result(self):
        code = textwrap.dedent(
            r'''
            import json, os, sys, tempfile, types
            from pathlib import Path

            tmp = tempfile.TemporaryDirectory(prefix="ss-v7-lowmatch-")
            os.environ.pop("DATABASE_URL", None)
            os.environ["DB_PATH"] = str(Path(tmp.name) / "test.sqlite3")
            os.environ["WEB_SECRET"] = "v7-test-secret-abcdefghijklmnopqrstuvwxyz"
            os.environ["SITE_URL"] = "http://localhost"
            os.environ["SESSION_COOKIE_SECURE"] = "0"

            groq = types.ModuleType("groq")
            groq.Groq = type("Groq", (), {})
            sys.modules["groq"] = groq

            import analysis_core

            patient = {
                "age": 25,
                "gender": "f",
                "symptoms": ["صداع", "غثيان"],
                "duration": "يوم",
                "severity": 2,
                "conditions": "",
                "medications": "",
                "allergies": "",
                "history_answered": True,
                "negative_symptoms": ["vomiting"],
                "user_id": "v7-test",
            }
            result = analysis_core.run_analysis(patient, "ar")
            print(json.dumps({
                "status": result.get("assessment_status"),
                "low_confidence": result.get("low_confidence"),
                "possible": result.get("possible_conditions"),
                "matches": [
                    {
                        "slug": m.get("slug"),
                        "level": m.get("match_level"),
                        "matched_count": len(m.get("matched_symptoms") or []),
                        "source_count": len(m.get("sources") or []),
                    }
                    for m in (result.get("knowledge_matches") or [])
                ],
            }, ensure_ascii=False))
            '''
        )
        data = json.loads(_run_python(code).splitlines()[0])
        self.assertEqual(data["status"], "complete")
        self.assertFalse(data["low_confidence"])
        self.assertIn("الصداع النصفي", data["possible"])
        self.assertTrue(data["matches"])
        self.assertTrue(any(m["matched_count"] >= 2 and m["source_count"] >= 1 for m in data["matches"]))
        # One-symptom weak leftovers such as generic sinusitis/flu matches must stay hidden.
        self.assertTrue(all(m["matched_count"] >= 2 for m in data["matches"] if m["level"] == "weak"))

    def test_semantically_duplicate_red_flags_are_deduped_and_gi_warning_is_merged(self):
        code = textwrap.dedent(
            r'''
            import json, sys, types
            groq = types.ModuleType("groq")
            groq.Groq = type("Groq", (), {})
            sys.modules["groq"] = groq
            import analysis_core

            bundle = {
                "risk": {"level": "low"},
                "matches": [
                    {"red_flags": "جفاف شديد، قلة بول، خمول غير معتاد، دم في القيء أو البراز أو ألم بطن شديد."},
                    {"red_flags": "جفاف شديد، دم في القيء أو البراز، ألم شديد أو تدهور عام."},
                ],
            }
            print(json.dumps(analysis_core._grounded_guidance(bundle, {}, "ar"), ensure_ascii=False))
            '''
        )
        data = json.loads(_run_python(code).splitlines()[0])
        danger = data["danger_signs"]
        self.assertEqual(danger.count("جفاف"), 1)
        self.assertEqual(danger.count("دم في القيء أو البراز"), 1)
        self.assertIn("جفاف شديد أو علامات نزيف هضمي", danger)

    def test_source_strip_uses_translated_moh_token_not_fixed_arabic_label(self):
        text = source_bundle.webapp_text()
        badge = '<span class="ss-source-badge">__MOH__</span>'
        old_badge = '<span class="ss-source-badge">وزارة الصحة</span>'
        self.assertIn(badge, text)
        self.assertNotIn(old_badge, text)
        self.assertIn('"__MOH__": bi("وزارة الصحة", "Saudi MOH")', text)


if __name__ == "__main__":
    unittest.main()
