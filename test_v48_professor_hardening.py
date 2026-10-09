from __future__ import annotations
import source_bundle

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _import_symptom_engine_without_groq():
    import importlib
    import types
    if "groq" not in sys.modules:
        fake = types.ModuleType("groq")
        class _Groq:
            def __init__(self, *args, **kwargs):
                pass
        fake.Groq = _Groq
        sys.modules["groq"] = fake
    return importlib.import_module("symptom_engine_v2")


def test_symptom_state_token_rejects_tamper_and_expiry():
    eng = _import_symptom_engine_without_groq()

    secret = "s" * 40
    state = eng.AssessmentState()
    token = eng.sign_state(state, secret, issued_at=1_000)
    payload, sig = token.split(".", 1)
    changed = ("A" if payload[:1] != "A" else "B") + payload[1:]
    with pytest.raises(ValueError, match="invalid_state_token"):
        eng.verify_state_token(changed + "." + sig, secret, now=1_001)
    with pytest.raises(ValueError, match="expired_state_token"):
        eng.verify_state_token(token, secret, max_age_seconds=60, now=1_061)


def test_symptom_state_never_trusts_serialized_step():
    eng = _import_symptom_engine_without_groq()

    st = eng.from_dict({"step": "result", "complete": False})
    assert st.step == "age"
    with pytest.raises(ValueError, match="invalid_state"):
        eng.from_dict({"step": "result", "complete": True})


def test_fhir_bundle_has_required_composition_author_and_valid_refs():
    import fhir_export

    bundle = fhir_export.build_bundle(
        account_id=7,
        user={"name": "Example"},
        health_profile={"gender": "female"},
        analyses=[{"id": 1, "symptoms": ["headache"], "created_at": "2026-09-18T10:00:00+00:00"}],
        blood_tests=[],
        medications=[
            {"id": 2, "med_name": "Example Active", "active": True},
            {"id": 3, "med_name": "Example Stopped", "active": False},
        ],
    )
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "collection"
    resources = [entry["resource"] for entry in bundle["entry"]]
    composition = next(r for r in resources if r["resourceType"] == "Composition")
    assert composition.get("author") and composition["author"][0].get("reference")
    device = next(r for r in resources if r["resourceType"] == "Device")
    assert composition["author"][0]["reference"] == next(
        e["fullUrl"] for e in bundle["entry"] if e["resource"] is device
    )
    meds = {r["medicationCodeableConcept"]["text"]: r for r in resources if r["resourceType"] == "MedicationStatement"}
    assert meds["Example Active"]["status"] == "active"
    assert meds["Example Stopped"]["status"] == "stopped"
    for entry in bundle["entry"]:
        assert re.fullmatch(r"urn:uuid:[0-9a-fA-F-]{36}", entry["fullUrl"])


def test_passkey_configuration_fails_closed_on_origin_rp_mismatch(monkeypatch):
    import passkeys

    monkeypatch.setenv("SITE_URL", "https://symptosensehealth.com")
    monkeypatch.setenv("WEBAUTHN_ORIGIN", "https://evil.example")
    monkeypatch.setenv("WEBAUTHN_RP_ID", "symptosensehealth.com")
    cfg = passkeys.config()
    assert cfg["valid_configuration"] is False
    assert cfg["secure_origin"] is False
    assert cfg["configuration_error"] == "rp_id_origin_mismatch"


def test_passkeys_require_discoverable_credentials():
    source = (ROOT / "passkeys.py").read_text(encoding="utf-8")
    assert "ResidentKeyRequirement.REQUIRED" in source
    assert "UserVerificationRequirement.REQUIRED" in source


def test_passkey_login_next_is_context_encoded():
    source = (ROOT / "v47_routes.py").read_text(encoding="utf-8")
    assert 'urlencode({"next": next_target})' in source
    assert "web_security.json_for_script(next_target" in source
    assert "json.dumps(next_target" not in source


def test_admin_v1_requires_full_admin_session_callback():
    source = source_bundle.webapp_text()
    assert 'admin_allowed=lambda scope="access": bool(_admin_allowed(scope) and _admin_session_valid())' in source


def test_api_v1_enforces_feature_flags_and_signed_state():
    source = (ROOT / "api_v1.py").read_text(encoding="utf-8")
    for flag in ("SEARCH_ENGINE_V2", "SYMPTOM_ENGINE_V2", "FHIR_EXPORT", "PASSKEYS", "SOURCE_MONITOR", "BACKGROUND_JOBS"):
        assert f"feature_flags.{flag}" in source
    assert "verify_state_token(token, _state_key())" in source
    assert 'name == "source_monitor" and not feature_flags.SOURCE_MONITOR' in source


def test_openapi_cookie_comes_from_real_app_config():
    api = (ROOT / "api_v1.py").read_text(encoding="utf-8")
    webapp = source_bundle.webapp_text()
    assert "session_cookie_name_getter" in api
    assert 'app.config.get("SESSION_COOKIE_NAME"' in webapp
    assert "__Host-ss_session" not in api


def test_source_monitor_blocks_private_dns(monkeypatch):
    import source_monitor

    monkeypatch.setattr(source_monitor.medical_knowledge, "_url_is_trusted", lambda url: True)
    monkeypatch.setattr(source_monitor.socket, "getaddrinfo", lambda *a, **k: [
        (source_monitor.socket.AF_INET, source_monitor.socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
    ])
    ok, reason = source_monitor._public_destination("https://trusted.example/path")
    assert ok is False
    assert reason == "private_destination"


def test_background_jobs_invalid_worker_count_is_safe(monkeypatch):
    import background_jobs

    monkeypatch.setenv("LOCAL_JOB_WORKERS", "not-a-number")
    assert background_jobs._local_worker_count() == 2
    monkeypatch.setenv("LOCAL_JOB_WORKERS", "999")
    assert background_jobs._local_worker_count() == 4


def test_background_source_monitor_payload_is_bounded():
    import background_jobs

    with pytest.raises(ValueError, match="invalid_job_parameters"):
        background_jobs.run_named_job("source_monitor", {"limit": 999999, "timeout": 5})
    with pytest.raises(ValueError, match="invalid_job_parameters"):
        background_jobs.run_named_job("source_monitor", {"limit": 10, "timeout": 99})


def test_dashboard_has_no_third_party_script_dependency():
    dashboard = (ROOT / "dashboard.py").read_text(encoding="utf-8")
    assert "cdn.jsdelivr.net" not in dashboard
    assert '/static/js/mini-charts.js' in dashboard
    assert (ROOT / "static/js/mini-charts.js").is_file()


def test_no_unsafe_javascript_execution_helpers_in_new_surface():
    files = [
        ROOT / "api_v1.py", ROOT / "v47_routes.py", ROOT / "passkeys.py",
        ROOT / "symptom_engine_v2.py", ROOT / "source_monitor.py", ROOT / "background_jobs.py",
        ROOT / "static/js/mini-charts.js",
    ]
    text = "\n".join(p.read_text(encoding="utf-8") for p in files)
    assert "new Function(" not in text
    assert not re.search(r"(?<![A-Za-z])eval\s*\(", text)


def test_v47_pages_fail_closed_when_api_v1_is_disabled():
    source = (ROOT / "v47_routes.py").read_text(encoding="utf-8")
    assert "feature_flags.PASSKEYS and feature_flags.API_V1" in source
    assert "feature_flags.SOURCE_MONITOR and feature_flags.API_V1" in source


def test_background_jobs_require_explicit_rq_mode(monkeypatch):
    import background_jobs

    monkeypatch.delenv("BACKGROUND_JOBS_BACKEND", raising=False)
    monkeypatch.setenv("REDIS_URL", "redis://example.invalid:6379/0")
    state = background_jobs.backend_status()
    assert state["backend"] == "local"
    assert state["available"] is True
    assert (ROOT / "rq_worker.py").is_file()


def test_api_json_limit_checks_actual_cached_body():
    source = (ROOT / "api_v1.py").read_text(encoding="utf-8")
    assert "request.get_data(cache=True)" in source
    assert "if len(raw) > max_bytes" in source
