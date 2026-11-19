import unittest

import health_search


class HealthSearchCompoundTests(unittest.TestCase):
    def test_single_symptom_keeps_curated_causes(self):
        result = health_search.search_health("دوخة", "ar")
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "الدوخة")
        self.assertGreater(len(result.get("causes") or []), 0)

    def test_compound_phrase_recognizes_taste_and_dizziness(self):
        result = health_search.search_health("أحس بطعم سكر عند الدوخة", "ar")
        self.assertEqual(result["category"], "combined")
        titles = [t["title"] for t in result["matched_topics"]]
        self.assertIn("طعم حلو أو غير معتاد في الفم", titles)
        self.assertIn("الدوخة", titles)
        for topic in result["matched_topics"]:
            self.assertGreater(len(topic.get("causes") or []), 0)

    def test_taste_phrase_does_not_false_match_diabetes(self):
        result = health_search.search_health("أحس بطعم السكر مع الدوخة", "ar")
        keys = [t["key"] for t in result.get("matched_topics") or [result]]
        self.assertIn("sweet_taste", keys)
        self.assertIn("dizziness", keys)
        self.assertNotIn("diabetes", keys)

    def test_english_compound_query(self):
        result = health_search.search_health("sweet taste in mouth and dizziness", "en")
        self.assertEqual(result["category"], "combined")
        keys = [t["key"] for t in result["matched_topics"]]
        self.assertIn("sweet_taste", keys)
        self.assertIn("dizziness", keys)


if __name__ == "__main__":
    unittest.main()
