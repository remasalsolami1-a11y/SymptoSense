from __future__ import annotations
import source_bundle

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_search_suggestions_are_curated_and_typo_tolerant():
    import search_engine_v2
    ar = search_engine_v2.suggestions("دوخه", "ar", 5)
    en = search_engine_v2.suggestions("headach", "en", 5)
    assert ar and ar[0]["label"] == "دوخة"
    assert en and en[0]["label"].lower() == "headache"
    assert all(x["kind"] in {"symptom", "disease"} for x in ar + en)


def test_translation_quality_gate_passes():
    p = subprocess.run([sys.executable, str(ROOT / "tools" / "check_translations.py")], cwd=ROOT, capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "TRANSLATION CHECK: PASS" in p.stdout


def test_feedback_schema_supports_structured_reason(tmp_path):
    import db
    old = (db.DB_PATH, db.DATABASE_URL, db.USE_POSTGRES, db.PH, db._DB_READY_KEY)
    try:
        db.DB_PATH = str(tmp_path / "feedback.db")
        db.DATABASE_URL = ""
        db.USE_POSTGRES = False
        db.PH = "?"
        db._DB_READY_KEY = None
        db.init_db()
        with sqlite3.connect(db.DB_PATH) as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(feedback)")}
        assert {"reason_code", "context"} <= cols
        db.save_feedback("u1", None, "star:4", None, False, reason_code="clear", context="analysis_result")
        assert db.feedback_reason_stats()[0] == {"reason": "clear", "count": 1}
    finally:
        db.DB_PATH, db.DATABASE_URL, db.USE_POSTGRES, db.PH, db._DB_READY_KEY = old


def test_smart_followup_is_owner_scoped_and_not_immediate():
    src = source_bundle.webapp_text()
    assert '@app.route("/api/smart-followup", methods=["GET", "POST"])' in src
    assert "if age_seconds < 12 * 3600" in src
    assert "db.get_record_owned(user_key, record_id)" in src
    assert "privacy.get(\"use_in_analysis\", True)" in src
    assert "_service_consent_ok()" in src
    assert "db.normalize_followup(" in src          # one schema; legacy spellings are mapped at the boundary


def test_chat_uses_structured_feedback_and_smart_followup():
    src = source_bundle.chat_view_text()
    assert "maybeOfferSmartFollowup" in src
    assert "recordSmartFollowup" in src
    assert "reason_code:selectedFeedbackReason" in src
    assert "context:'analysis_result'" in src
    assert "data-reason" in src
    # Reason buttons are bound with addEventListener rather than executable inline attributes.
    assert 'onclick="selectFeedbackReason' not in src


def test_translation_gate_is_in_ci_and_release_check():
    ci = (ROOT / "ci.yml").read_text(encoding="utf-8")
    rc = (ROOT / "release_check.py").read_text(encoding="utf-8")
    assert "python tools/check_translations.py" in ci
    assert "check_translation_quality" in rc
