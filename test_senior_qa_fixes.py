import source_bundle
from pathlib import Path
import sqlite3

import db
import medical_knowledge as mk
import data_retention

ROOT = Path(__file__).resolve().parent


def _use_temp_knowledge_db(monkeypatch, tmp_path):
    path = tmp_path / "qa_privacy.db"
    monkeypatch.setattr(db, "DB_PATH", str(path))
    monkeypatch.setattr(db, "DATABASE_URL", "")
    monkeypatch.setattr(db, "USE_POSTGRES", False)
    monkeypatch.setattr(db, "PH", "?")
    monkeypatch.setattr(db, "_DB_READY_KEY", None)
    monkeypatch.setattr(db, "_CHECKIN_SCHEMA_READY_KEY", None)
    monkeypatch.setattr(mk, "_READY_KEY", None)
    mk.init_schema()
    return path


def _coverage_rows(path):
    conn = sqlite3.connect(path)
    try:
        return conn.execute("SELECT phrase, lang, matched FROM mk_unmatched_log ORDER BY id").fetchall()
    finally:
        conn.close()


def test_symptom_coverage_text_is_not_logged_without_analytics_consent(monkeypatch, tmp_path):
    path = _use_temp_knowledge_db(monkeypatch, tmp_path)
    mk.knowledge_bundle(["عبارة عرض غير معروفة لاختبار الخصوصية"], lang="ar", analytics_consent=False)
    assert _coverage_rows(path) == []


def test_only_unmatched_wording_is_logged_with_analytics_consent(monkeypatch, tmp_path):
    path = _use_temp_knowledge_db(monkeypatch, tmp_path)
    unknown = "عبارة عرض غير معروفة لاختبار التحليلات"
    mk.knowledge_bundle([unknown], lang="ar", analytics_consent=True)
    rows = _coverage_rows(path)
    assert rows == [(unknown, "ar", 0)]

    # Recognized symptom text is not retained in this free-text analytics table.
    before = list(rows)
    mk.knowledge_bundle(["صداع"], lang="ar", analytics_consent=True)
    assert _coverage_rows(path) == before


def test_unmatched_coverage_obeys_usage_analytics_retention(monkeypatch, tmp_path):
    path = _use_temp_knowledge_db(monkeypatch, tmp_path)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "INSERT INTO mk_unmatched_log(phrase,lang,matched,created_at) VALUES(?,?,?,?)",
            ("قديم", "ar", 0, "2000-01-01T00:00:00+00:00"),
        )
        conn.commit()
    finally:
        conn.close()
    monkeypatch.setenv("USAGE_ANALYTICS_RETENTION_DAYS", "180")
    result = data_retention.run_cleanup()
    assert result["deleted"].get("mk_unmatched_log") == 1
    assert _coverage_rows(path) == []


def test_bot_does_not_send_internal_exception_details_to_user():
    src = (ROOT / "bot.py").read_text(encoding="utf-8")
    start = src.index('logger.exception("ANALYSIS FAILED: error_type=%s"')
    block = src[start: start + 1800]
    assert 'str(e)' not in block
    assert '🛠' not in block
    assert 'await send(t(context, "error"))' in block


def test_admin_data_pulse_prefers_canonical_daily_checkin_table():
    src = source_bundle.webapp_text()
    block = src.split('@app.route("/api/admin/data-pulse"', 1)[1].split('@app.route("/api/admin/system-health"', 1)[0]
    assert 'table_count("ss_daily_checkins") if table_exists("ss_daily_checkins") else table_count("daily_checkins")' in block
    assert 'table_count("daily_checkins") + table_count("ss_daily_checkins")' not in block
    assert '"metric_scope": "tracked_application_rows_not_storage_bytes"' in block
    for key in ("analysis_results", "medication_logs", "medication_reminders", "assistant_feedback", "usage_events"):
        assert f'"{key}"' in block


def test_hash_salt_is_documented_and_reported_by_readiness():
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    readiness = (ROOT / "production_readiness.py").read_text(encoding="utf-8")
    assert "HASH_SALT=" in env
    assert "HASH_SALT" in security
    assert 'components["pseudonym_hash_secret"]' in readiness


def test_pooled_connection_context_manager_returns_connection_to_pool():
    class Raw:
        closed = 0
        def __init__(self):
            self.exits = 0
            self.rollbacks = 0
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            self.exits += 1
            return False
        def rollback(self):
            self.rollbacks += 1

    class Pool:
        def __init__(self):
            self.calls = []
        def putconn(self, raw, close=False):
            self.calls.append((raw, close))

    raw, pool = Raw(), Pool()
    proxy = db._PooledConnectionProxy(raw, pool)
    with proxy:
        pass
    assert raw.exits == 1
    assert raw.rollbacks == 1
    assert pool.calls == [(raw, False)]
    proxy.close()  # idempotent
    assert len(pool.calls) == 1


def test_severe_chest_pain_is_urgent_in_independent_knowledge_safety_layer(monkeypatch, tmp_path):
    _use_temp_knowledge_db(monkeypatch, tmp_path)
    for phrase, lang in (("ألم صدر شديد", "ar"), ("severe chest pain", "en")):
        result = mk.knowledge_bundle([phrase], severity=1, age=35, lang=lang)
        assert result["risk"]["level"] == "urgent"
        assert result["risk"]["emergency"] is True
        assert result["matches"] == []
        assert any(r.get("slug") == "severe-chest-pain" for r in result["risk"]["reasons"])


def test_non_severe_chest_pain_remains_review_not_urgent(monkeypatch, tmp_path):
    _use_temp_knowledge_db(monkeypatch, tmp_path)
    result = mk.knowledge_bundle(["ألم الصدر"], severity=2, age=35, lang="ar")
    assert result["risk"]["level"] == "review"
    assert result["risk"]["emergency"] is False


def test_public_versioned_api_does_not_return_arbitrary_exception_text():
    src = (ROOT / "api_v1.py").read_text(encoding="utf-8")
    assert "def _safe_exception_code" in src
    assert "return _err(str(exc)," not in src
    assert "_SYMPTOM_ERROR_CODES" in src
    assert "_JOB_ERROR_CODES" in src


def test_admin_health_checks_do_not_expose_raw_exception_text():
    src = (ROOT / "medical_knowledge.py").read_text(encoding="utf-8")
    block = src.split("def system_health():", 1)[1].split("def rollback_version", 1)[0]
    assert '"error":str(e)' not in block
    assert 'str(getattr(e,"reason",e))' not in block
    assert 'database_check_failed' in block
    assert 'provider_connection_failed' in block
    assert 'authentication_check_failed' in block


def test_admin_rollback_does_not_echo_arbitrary_value_errors():
    src = (ROOT / "v47_routes.py").read_text(encoding="utf-8")
    block = src.split("def admin_knowledge_rollback", 1)[1]
    assert 'str(exc)[:80]' not in block
    assert 'invalid_rollback_request' in block


def test_browser_test_dependencies_are_exactly_pinned():
    import json
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    deps = package.get("devDependencies") or {}
    assert deps.get("@axe-core/playwright") == "4.10.2"
    assert deps.get("@playwright/test") == "1.55.0"


def test_werkzeug_security_floor_is_explicit():
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "Werkzeug>=3.1.6,<4" in req
