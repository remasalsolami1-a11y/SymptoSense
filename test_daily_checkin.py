"""Regression tests for account daily tracking and mobile/share safeguards."""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import db  # noqa: E402
import privacy_features  # noqa: E402


class DailyCheckinRegressionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="symptosense-checkin-")
        self.path = str(Path(self.tmp.name) / "checkin.sqlite3")
        db.DATABASE_URL = ""
        db.USE_POSTGRES = False
        db.PH = "?"
        db.DB_PATH = self.path
        db._DB_READY_KEY = None
        db._CHECKIN_SCHEMA_READY_KEY = None

    def tearDown(self):
        self.tmp.cleanup()

    def test_one_record_per_user_per_day_updates_in_place(self):
        db.init_db()
        first = db.save_daily_checkin("account-1", 5, "2026-09-02")
        second = db.save_daily_checkin("account-1", 3, "2026-09-02")
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        history = db.get_daily_checkin_history("account-1", 30)
        self.assertEqual([(r["date"], r["value"]) for r in history], [("2026-09-02", 3)])

    def test_checkins_are_isolated_by_user(self):
        db.init_db()
        db.save_daily_checkin("account-1", 4, "2026-09-02")
        db.save_daily_checkin("account-2", 2, "2026-09-02")
        self.assertEqual(db.get_daily_checkin_for_date("account-1", "2026-09-02")["value"], 4)
        self.assertEqual(db.get_daily_checkin_for_date("account-2", "2026-09-02")["value"], 2)

    def test_legacy_table_is_backfilled_and_duplicate_day_is_collapsed(self):
        conn = sqlite3.connect(self.path)
        conn.execute(
            "CREATE TABLE daily_checkins (id INTEGER PRIMARY KEY AUTOINCREMENT, user_hash TEXT NOT NULL, timestamp TEXT NOT NULL, severity INTEGER)"
        )
        conn.execute(
            "INSERT INTO daily_checkins(user_hash,timestamp,severity) VALUES (?,?,?)",
            ("legacy", "2026-09-01T09:00:00+00:00", 2),
        )
        conn.execute(
            "INSERT INTO daily_checkins(user_hash,timestamp,severity) VALUES (?,?,?)",
            ("legacy", "2026-09-01T11:00:00+00:00", 4),
        )
        conn.commit()
        conn.close()

        db.init_db()
        conn = sqlite3.connect(self.path)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(daily_checkins)")}
        rows = conn.execute(
            "SELECT checkin_date,severity FROM daily_checkins WHERE user_hash='legacy'"
        ).fetchall()
        indexes = conn.execute("PRAGMA index_list(daily_checkins)").fetchall()
        conn.close()
        self.assertIn("checkin_date", cols)
        self.assertEqual(rows, [("2026-09-01", 4)])
        self.assertTrue(any(row[1] == "idx_ci_user_date_unique" and row[2] == 1 for row in indexes))


    def test_targeted_checkin_schema_repair_works_even_if_main_db_cache_is_warm(self):
        conn = sqlite3.connect(self.path)
        conn.execute(
            "CREATE TABLE daily_checkins (id INTEGER PRIMARY KEY AUTOINCREMENT, user_hash TEXT NOT NULL, timestamp DATETIME NOT NULL, severity INTEGER)"
        )
        conn.execute(
            "INSERT INTO daily_checkins(user_hash,timestamp,severity) VALUES (?,?,?)",
            (db._hash_user("legacy"), "2026-09-03 00:15:00", 5),
        )
        conn.commit()
        conn.close()

        # Simulate a process whose broader DB initialization cache is already warm.
        db._DB_READY_KEY = db._database_identity()
        db.ensure_daily_checkins_schema()
        row = db.get_daily_checkin_history("legacy", 7)
        self.assertEqual([(r["date"], r["value"]) for r in row], [("2026-09-03", 5)])

    def test_broken_legacy_table_does_not_block_new_tracking_store(self):
        conn = sqlite3.connect(self.path)
        # Deliberately incompatible legacy shape: missing timestamp/checkin_date.
        conn.execute(
            "CREATE TABLE daily_checkins (id INTEGER PRIMARY KEY AUTOINCREMENT, user_hash TEXT, severity INTEGER)"
        )
        conn.execute(
            "INSERT INTO daily_checkins(user_hash,severity) VALUES (?,?)",
            (db._hash_user("account-legacy-broken"), 2),
        )
        conn.commit()
        conn.close()

        # Simulate the live app already being initialized; only the tracking
        # feature guard runs now. The broken legacy table must not take it down.
        db._DB_READY_KEY = db._database_identity()
        db.ensure_daily_checkins_schema()
        saved = db.save_daily_checkin("account-legacy-broken", 4, "2026-09-03")
        self.assertTrue(saved["created"])
        row = db.get_daily_checkin_for_date("account-legacy-broken", "2026-09-03")
        self.assertEqual(row["value"], 4)

    def test_web_tracking_works_with_legacy_user_data_without_updated_at(self):
        conn = sqlite3.connect(self.path)
        conn.execute("CREATE TABLE user_data (user_id INTEGER PRIMARY KEY, data TEXT NOT NULL)")
        conn.commit()
        conn.close()

        first = db.save_web_daily_checkin(7, 4, "2026-09-03")
        second = db.save_web_daily_checkin(7, 2, "2026-09-03")
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        rows = db.get_web_daily_checkin_history(7, 30)
        self.assertEqual([(r["date"], r["value"]) for r in rows], [("2026-09-03", 2)])

    def test_web_tracking_works_with_legacy_text_user_id(self):
        conn = sqlite3.connect(self.path)
        conn.execute("CREATE TABLE user_data (user_id TEXT PRIMARY KEY, data TEXT NOT NULL)")
        conn.commit()
        conn.close()

        db.save_web_daily_checkin(8, 5, "2026-09-03")
        row = db.get_web_daily_checkin_for_date(8, "2026-09-03")
        self.assertIsNotNone(row)
        self.assertEqual(row["value"], 5)

    def test_handoff_refuses_an_empty_selected_field(self):
        db.init_db()
        privacy_features.init_schema()
        owner = "account-qr"
        record_id = db.save_record(
            owner, "ar", 21, "f", ["صداع"], "1-3 أيام", 2, "low", medications=""
        )
        db.save_result(
            owner, record_id,
            {"lang": "ar", "symptoms": ["صداع"], "duration": "1-3 أيام", "severity": 2, "medications": ""},
        )
        with self.assertRaisesRegex(ValueError, "selected_information_empty"):
            privacy_features.create_handoff(owner, record_id, {"medications": True}, [], 15)
        created = privacy_features.create_handoff(owner, record_id, {"symptoms": True}, [], 15)
        loaded = privacy_features.get_handoff(created["token"])
        self.assertEqual(loaded["status"], "active")
        self.assertEqual(loaded["payload"]["sections"]["symptoms"], ["صداع"])

    def test_frontend_regression_guards_exist(self):
        source = (PROJECT_ROOT / "webapp.py").read_text(encoding="utf-8")
        self.assertIn('@app.route("/api/checkin", methods=["GET", "POST"])', source)
        self.assertIn('url_for("public_health_handoff", token=result["token"], lang=payload_lang)', source)
        self.assertIn('path.startswith("/share/health/")', source)
        self.assertIn('white-space:nowrap;direction:ltr;unicode-bidi:isolate', source)
        self.assertIn('type="button" class="btn pri" id="generateHandoff"', source)
        privacy_source = (PROJECT_ROOT / "privacy_features.py").read_text(encoding="utf-8")
        self.assertIn('selected_information_empty', privacy_source)


if __name__ == "__main__":
    unittest.main()
