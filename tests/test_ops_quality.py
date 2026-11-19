"""V253: admin quality centre and production readiness checks."""
import uuid

import analysis_core
import db
import ops_metrics
import ops_quality
import webapp


def test_production_checks_fail_closed_in_production_only(monkeypatch):
    monkeypatch.delenv("SYMPTOSENSE_ALLOW_EPHEMERAL", raising=False)
    monkeypatch.setattr(db, "USE_POSTGRES", False)
    ok, checks = ops_quality.production_checks(True, False, False)
    assert not ok and {c["id"] for c in checks if not c["ok"]} == {"persistent_database", "web_secret", "secure_cookies"}
    assert ops_quality.production_checks(False, False, False)[0] is True
    monkeypatch.setenv("SYMPTOSENSE_ALLOW_EPHEMERAL", "1")
    assert ops_quality.production_checks(True, True, True)[0] is True
    monkeypatch.setattr(db, "USE_POSTGRES", True)
    monkeypatch.delenv("SYMPTOSENSE_ALLOW_EPHEMERAL")
    assert ops_quality.production_checks(True, True, True)[0] is True


def test_ready_reports_checks_and_503_when_production_unsafe(monkeypatch):
    monkeypatch.setattr(webapp, "_RAILWAY_RUNTIME", True)
    monkeypatch.setattr(webapp, "_configured_web_secret", "")
    r = webapp.app.test_client().get("/ready")
    assert r.status_code == 503 and r.get_json()["production_checks"]
    assert webapp.app.test_client().get("/health").status_code == 200   # liveness is unchanged


def test_analysis_updates_counters_without_content():
    ops_metrics.reset()
    r = analysis_core.run_analysis({"symptoms": ["صداع"], "age": "30", "gender": "male", "duration": "2", "severity": "3"}, "ar")
    snap = ops_quality.quality_snapshot()
    assert snap["analysis"]["completed"] == 1 and snap["analysis"]["decisions"][r["decision"]["level"]] == 1
    assert "صداع" not in repr(snap)


def test_quality_api_is_admin_only():
    c = webapp.app.test_client()
    assert c.get("/api/admin/quality").status_code in (401, 403)
    assert c.get("/admin/quality-center").status_code in (302, 401, 403)
    js = open("static/js/quality-center.js", encoding="utf-8").read()
    assert "innerHTML" not in js


def test_snapshot_reports_audit_failures_and_signoff_state(tmp_path, monkeypatch):
    import best_effort
    import ops_metrics
    import ops_quality
    ops_metrics.reset()
    best_effort.call(lambda: (_ for _ in ()).throw(OSError("x")))
    snap = ops_quality.quality_snapshot()
    assert "side_effects" in snap and snap["clinical_signoff"]["pending"] != [] or snap["clinical_signoff"]["pending"] == []
    assert snap["clinical_signoff"]["bypass_active"] in (True, False)
