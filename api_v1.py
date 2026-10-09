"""Versioned API surface for SymptoSense V48.

The API is intentionally conservative: account mutations require the existing
same-origin session + CSRF protections, admin callbacks are supplied by the web
layer, and experimental engines are protected by runtime feature flags.
"""
from __future__ import annotations

import base64
import re
import time
from flask import Blueprint, jsonify, request, session, Response

import background_jobs
import db
import feature_flags
import fhir_export
import medical_knowledge
import passkeys
import search_engine_v2
import source_monitor
import symptom_engine_v2

_JOB_ID_RE = re.compile(r"^job_[0-9a-f]{32}$")
_PASSKEY_CHALLENGE_TTL = 5 * 60


def _ok(data=None, status=200, **meta):
    body = {"ok": True, "data": data, "meta": {"api_version": "v1", **meta}}
    return jsonify(body), status


def _err(code, status=400, message=None, **details):
    return jsonify({
        "ok": False,
        "error": {"code": str(code), "message": message or str(code), "details": details or None},
        "meta": {"api_version": "v1"},
    }), status


def _safe_exception_code(exc, allowed, fallback):
    """Expose only stable, documented machine codes from caught exceptions.

    Exception text can unexpectedly include provider/library details.  Public API
    responses therefore opt in to a small allow-list instead of returning
    ``str(exc)`` verbatim.
    """
    code = str(exc or "").strip()
    return code if code in set(allowed) else str(fallback)


_JSON_ERROR_CODES = {"payload_too_large", "json_object_required"}
_SYMPTOM_ERROR_CODES = _JSON_ERROR_CODES | {
    "state_token_required", "state_signing_key_unavailable", "invalid_state_token",
    "expired_state_token", "invalid_state", "assessment_already_complete",
    "invalid_age", "invalid_gender", "invalid_symptoms", "missing_symptoms",
    "missing_duration", "invalid_duration", "invalid_severity",
    "invalid_red_flag_context", "invalid_context", "assessment_incomplete",
}
_JOB_ERROR_CODES = _JSON_ERROR_CODES | {
    "job_not_allowed", "invalid_job_parameters", "invalid_job_payload",
    "background_backend_unavailable",
}


def _json_object(max_bytes=64_000, *, allow_empty: bool = False):
    # Content-Length is not guaranteed for every transfer mode.  Inspect the
    # cached body too so chunked/malformed requests cannot bypass the API's
    # tighter limit and fall back to Flask's much larger global upload limit.
    if request.content_length and request.content_length > max_bytes:
        raise ValueError("payload_too_large")
    raw = request.get_data(cache=True)
    if len(raw) > max_bytes:
        raise ValueError("payload_too_large")
    if not raw and allow_empty:
        return {}
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError("json_object_required")
    return data


def _feature_or_error(enabled: bool):
    return None if enabled else _err("feature_disabled", 404)


def _store_challenge(key: str, challenge: bytes) -> None:
    session[key] = {
        "value": base64.b64encode(challenge).decode("ascii"),
        "issued_at": int(time.time()),
    }


def _pop_challenge(key: str, *, max_age: int = _PASSKEY_CHALLENGE_TTL) -> bytes:
    item = session.pop(key, None)
    if not isinstance(item, dict):
        raise ValueError("missing_challenge")
    issued = item.get("issued_at")
    value = item.get("value")
    if isinstance(issued, bool) or not isinstance(issued, int) or not isinstance(value, str):
        raise ValueError("invalid_challenge")
    now = int(time.time())
    if issued > now + 60 or now - issued > max_age:
        raise ValueError("expired_challenge")
    try:
        raw = base64.b64decode(value, validate=True)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("invalid_challenge")
    if not raw or len(raw) > 256:
        raise ValueError("invalid_challenge")
    return raw


def openapi_spec(base_url="", cookie_name="__Host-symptosense_session") -> dict:
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "SymptoSense API",
            "version": "1.1.0",
            "description": "Versioned API for non-diagnostic symptom guidance and user-controlled health data.",
        },
        "servers": [{"url": base_url.rstrip("/") or "/"}],
        "paths": {
            "/api/v1/meta": {"get": {"summary": "API and feature metadata", "responses": {"200": {"description": "OK"}}}},
            "/api/v1/search": {"get": {"summary": "Bilingual curated health search", "parameters": [
                {"name": "q", "in": "query", "required": True, "schema": {"type": "string", "minLength": 2, "maxLength": 500}},
                {"name": "lang", "in": "query", "schema": {"type": "string", "enum": ["ar", "en"]}},
                {"name": "limit", "in": "query", "schema": {"type": "integer", "minimum": 1, "maximum": 20, "default": 8}},
            ], "responses": {"200": {"description": "Ranked curated results"}, "404": {"description": "Feature disabled"}}}},
            "/api/v1/symptoms/session/start": {"post": {"summary": "Start a signed Symptom Engine V2 session", "responses": {"200": {"description": "Initial signed state"}}}},
            "/api/v1/symptoms/session/answer": {"post": {"summary": "Apply one answer to a server-signed state", "responses": {"200": {"description": "Next signed state"}, "400": {"description": "Validation error"}}}},
            "/api/v1/symptoms/session/result": {"post": {"summary": "Run the clinical guidance engine on a completed signed state", "responses": {"200": {"description": "Non-diagnostic guidance"}}}},
            "/api/v1/fhir/export": {"get": {"summary": "Export signed-in user's own data as a FHIR R4-compatible collection Bundle", "security": [{"cookieAuth": []}], "responses": {"200": {"description": "FHIR Bundle"}, "401": {"description": "Authentication required"}}}},
            "/api/v1/passkeys/status": {"get": {"summary": "Passkey capability/status", "responses": {"200": {"description": "Status"}}}},
            "/api/v1/passkeys/register/options": {"post": {"summary": "Create a signed-in user's WebAuthn registration ceremony", "security": [{"cookieAuth": []}], "responses": {"200": {"description": "WebAuthn creation options"}, "401": {"description": "Authentication required"}}}},
            "/api/v1/passkeys/register/verify": {"post": {"summary": "Verify and store a new passkey", "security": [{"cookieAuth": []}], "responses": {"201": {"description": "Passkey registered"}}}},
            "/api/v1/passkeys/auth/options": {"post": {"summary": "Start username-less passkey authentication", "responses": {"200": {"description": "WebAuthn request options"}}}},
            "/api/v1/passkeys/auth/verify": {"post": {"summary": "Verify passkey authentication", "responses": {"200": {"description": "Authenticated"}, "401": {"description": "Verification failed"}}}},
            "/api/v1/passkeys/{passkey_id}": {"delete": {"summary": "Delete one of the signed-in user's passkeys", "security": [{"cookieAuth": []}], "parameters": [{"name": "passkey_id", "in": "path", "required": True, "schema": {"type": "integer", "minimum": 1}}], "responses": {"200": {"description": "Deletion result"}, "401": {"description": "Authentication required"}}}},
            "/api/v1/admin/source-monitor": {"get": {"summary": "Read source freshness/link-monitor status", "security": [{"cookieAuth": []}], "responses": {"200": {"description": "Monitor status"}, "403": {"description": "Admin required"}}}},
            "/api/v1/admin/source-monitor/run": {"post": {"summary": "Queue a medical-source monitor run", "security": [{"cookieAuth": []}], "responses": {"202": {"description": "Job queued"}}}},
            "/api/v1/admin/medical-versioning": {"get": {"summary": "Medical-content version and review summary", "security": [{"cookieAuth": []}], "responses": {"200": {"description": "Versioning summary"}}}},
            "/api/v1/admin/jobs": {"post": {"summary": "Queue an allow-listed operational job", "security": [{"cookieAuth": []}], "responses": {"202": {"description": "Job queued"}}}},
            "/api/v1/admin/jobs/{job_id}": {"get": {"summary": "Read one operational job status", "security": [{"cookieAuth": []}], "parameters": [{"name": "job_id", "in": "path", "required": True, "schema": {"type": "string", "pattern": "^job_[0-9a-f]{32}$"}}], "responses": {"200": {"description": "Job status"}, "404": {"description": "Job not found"}}}},
            "/api/v1/openapi.json": {"get": {"summary": "OpenAPI document", "responses": {"200": {"description": "OpenAPI JSON"}}}},
        },
        "components": {
            "securitySchemes": {
                "cookieAuth": {
                    "type": "apiKey",
                    "in": "cookie",
                    "name": cookie_name,
                    "description": "Same-origin secure session cookie; state-changing browser requests also require the session CSRF token.",
                }
            }
        },
    }


def create_blueprint(*, current_user_id, current_user, login_user_with_passkey, lang_getter,
                     site_url_getter, admin_allowed, rate_allowed=None,
                     state_signing_key_getter=None, session_cookie_name_getter=None,
                     data_user_id_getter=None):
    bp = Blueprint("api_v1", "api_v1", url_prefix="/api/v1")

    def _rate(scope: str, maximum: int, window_seconds: int, extra: str = "") -> bool:
        if rate_allowed is None:
            return True
        try:
            return bool(rate_allowed(scope, maximum, window_seconds, extra))
        except Exception:
            return False

    def _active_account():
        """Recheck account status for existing sessions before credential access."""
        user = current_user() or {}
        return bool(current_user_id() and user.get("status") == "active" and user.get("email_verified"))

    def _state_key():
        if state_signing_key_getter is None:
            raise ValueError("state_signing_key_unavailable")
        key = state_signing_key_getter()
        if not key or len(str(key)) < 32:
            raise ValueError("state_signing_key_unavailable")
        return key

    def _state_payload(st: symptom_engine_v2.AssessmentState, lang: str, *, progress_value=None):
        return {
            "state": st.to_dict(),
            "state_token": symptom_engine_v2.sign_state(st, _state_key()),
            "progress": symptom_engine_v2.progress(st) if progress_value is None else progress_value,
            "prompt": symptom_engine_v2.prompt(st.step, lang),
            "expires_in_seconds": symptom_engine_v2.DEFAULT_TOKEN_MAX_AGE,
        }

    @bp.get("/meta")
    def meta():
        cfg = passkeys.config() if feature_flags.PASSKEYS else {"library": False, "secure_origin": False, "rp_id": None}
        return _ok({
            "features": feature_flags.public_state(),
            "knowledge": medical_knowledge.statistics(),
            "background_jobs": background_jobs.backend_status() if feature_flags.BACKGROUND_JOBS else {"backend": "disabled", "available": False},
            "passkeys": cfg,
        })

    @bp.get("/openapi.json")
    def openapi_json():
        cookie_name = session_cookie_name_getter() if session_cookie_name_getter else "__Host-symptosense_session"
        return jsonify(openapi_spec(site_url_getter(), str(cookie_name)))

    @bp.get("/docs")
    def docs():
        cookie_name = session_cookie_name_getter() if session_cookie_name_getter else "__Host-symptosense_session"
        spec = openapi_spec(site_url_getter(), str(cookie_name))
        rows = []
        for path, methods in spec["paths"].items():
            for method, operation in methods.items():
                rows.append(f"<tr><td><code>{path}</code></td><td>{method.upper()}</td><td>{operation.get('summary','')}</td></tr>")
        html = """<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>SymptoSense API v1</title><style>@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&family=Tajawal:wght@400;500;700;800&display=swap');body{font-family:'Poppins','Tajawal','Segoe UI',sans-serif;max-width:960px;margin:40px auto;padding:0 18px;color:#18354d}table{border-collapse:collapse;width:100%}td,th{border:1px solid #dbe7ef;padding:10px;text-align:left}code{background:#f3f8fc;padding:2px 5px;border-radius:5px}</style></head><body><h1>SymptoSense API v1</h1><p>Stable versioned endpoints. Medical outputs are non-diagnostic.</p><table><thead><tr><th>Path</th><th>Method</th><th>Purpose</th></tr></thead><tbody>""" + "".join(rows) + """</tbody></table><p><a href='/api/v1/openapi.json'>OpenAPI JSON</a></p></body></html>"""
        return Response(html, mimetype="text/html")

    @bp.get("/search")
    def search():
        disabled = _feature_or_error(feature_flags.SEARCH_ENGINE_V2)
        if disabled:
            return disabled
        if not _rate("api_v1_search", 60, 60):
            return _err("rate_limited", 429)
        q = (request.args.get("q") or "").strip()
        lang = "en" if request.args.get("lang") == "en" else lang_getter()
        if len(q) < 2:
            return _err("query_too_short", 400)
        if len(q) > 500:
            return _err("query_too_long", 400)
        return _ok(search_engine_v2.search(q, lang, request.args.get("limit", 8)))

    @bp.post("/symptoms/session/start")
    def symptom_start():
        if not _rate("api_v1_symptom_session", 60, 300):
            return _err("rate_limited", 429)
        disabled = _feature_or_error(feature_flags.SYMPTOM_ENGINE_V2)
        if disabled:
            return disabled
        try:
            incoming = _json_object(4_096, allow_empty=True)
        except ValueError as exc:
            return _err(_safe_exception_code(exc, _JSON_ERROR_CODES, "invalid_request"), 400)
        lang = "en" if incoming.get("lang") == "en" else lang_getter()
        st = symptom_engine_v2.AssessmentState()
        try:
            return _ok(_state_payload(st, lang, progress_value=0))
        except ValueError as exc:
            return _err(_safe_exception_code(exc, {"state_signing_key_unavailable"}, "service_unavailable"), 503)

    @bp.post("/symptoms/session/answer")
    def symptom_answer():
        if not _rate("api_v1_symptom_answer", 120, 300):
            return _err("rate_limited", 429)
        disabled = _feature_or_error(feature_flags.SYMPTOM_ENGINE_V2)
        if disabled:
            return disabled
        try:
            data = _json_object()
            token = data.get("state_token")
            if not isinstance(token, str) or not token:
                raise ValueError("state_token_required")
            st = symptom_engine_v2.verify_state_token(token, _state_key())
            lang = "en" if data.get("lang") == "en" else lang_getter()
            updated = symptom_engine_v2.apply_answer(st, data.get("answer"), lang)
            next_state = symptom_engine_v2.from_dict(updated["state"])
            return _ok(_state_payload(next_state, lang, progress_value=updated["progress"]))
        except ValueError as exc:
            return _err(_safe_exception_code(exc, _SYMPTOM_ERROR_CODES, "invalid_assessment_request"), 400)

    @bp.post("/symptoms/session/result")
    def symptom_result():
        if not _rate("api_v1_symptom_result", 20, 300):
            return _err("rate_limited", 429)
        disabled = _feature_or_error(feature_flags.SYMPTOM_ENGINE_V2)
        if disabled:
            return disabled
        try:
            data = _json_object()
            token = data.get("state_token")
            if not isinstance(token, str) or not token:
                raise ValueError("state_token_required")
            st = symptom_engine_v2.verify_state_token(token, _state_key())
            lang = "en" if data.get("lang") == "en" else lang_getter()
            return _ok(symptom_engine_v2.analyze(st, lang))
        except ValueError as exc:
            return _err(_safe_exception_code(exc, _SYMPTOM_ERROR_CODES, "invalid_assessment_request"), 400)
        except Exception:
            return _err("analysis_unavailable", 503)

    @bp.get("/fhir/export")
    def fhir():
        disabled = _feature_or_error(feature_flags.FHIR_EXPORT)
        if disabled:
            return disabled
        uid = current_user_id()
        if not uid:
            return _err("authentication_required", 401)
        user = current_user() or {}
        if user.get("status") != "active" or not user.get("email_verified"):
            return _err("authentication_required", 401)
        owner = data_user_id_getter() if data_user_id_getter else f"account-{uid}"
        hp = db.load_health_profile(uid) or db.load_profile(owner) or {}
        bundle = fhir_export.build_bundle(
            account_id=int(uid),
            user=user,
            health_profile=hp,
            analyses=db.get_records(owner, limit=100, member_id=0),
            blood_tests=db.get_blood_tests(owner, limit=100, member_id=0),
            medications=db.list_med_plans(owner, member_id=0, active_only=False),
        )
        resp = jsonify(bundle)
        resp.headers["Content-Type"] = "application/fhir+json; charset=utf-8"
        resp.headers["Content-Disposition"] = 'attachment; filename="symptosense-fhir.json"'
        resp.headers["Cache-Control"] = "private, no-store"
        return resp

    @bp.get("/passkeys/status")
    def passkey_status():
        if not feature_flags.PASSKEYS:
            return _ok({"enabled": False, "available": False, "configuration": None, "credentials": []})
        uid = current_user_id()
        if uid and not _active_account():
            return _err("authentication_required", 401)
        cfg = passkeys.config()
        data = {
            "enabled": True,
            "available": bool(cfg.get("library") and cfg.get("secure_origin")),
            "configuration": {"rp_id": cfg.get("rp_id"), "secure_origin": cfg.get("secure_origin")},
            "credentials": passkeys.list_for_user(uid) if uid else [],
        }
        return _ok(data)

    @bp.post("/passkeys/register/options")
    def passkey_register_options():
        disabled = _feature_or_error(feature_flags.PASSKEYS)
        if disabled:
            return disabled
        if not _rate("passkey_register_options", 10, 600):
            return _err("rate_limited", 429)
        uid = current_user_id()
        user = current_user()
        if not uid or not _active_account():
            return _err("authentication_required", 401)
        try:
            raw, challenge = passkeys.registration_options(user)
            _store_challenge("passkey_reg_challenge", challenge)
            return Response(raw, mimetype="application/json")
        except RuntimeError as exc:
            return _err(_safe_exception_code(exc, {"passkeys_unavailable"}, "passkeys_unavailable"), 503)

    @bp.post("/passkeys/register/verify")
    def passkey_register_verify():
        disabled = _feature_or_error(feature_flags.PASSKEYS)
        if disabled:
            return disabled
        if not _rate("passkey_register_verify", 10, 600):
            return _err("rate_limited", 429)
        uid = current_user_id()
        if not uid or not _active_account():
            return _err("authentication_required", 401)
        try:
            data = _json_object(128_000)
            challenge = _pop_challenge("passkey_reg_challenge")
            label = data.get("label")
            if label is not None and (not isinstance(label, str) or len(label) > 80):
                raise ValueError("invalid_label")
            result = passkeys.verify_registration(int(uid), data.get("credential") or data, challenge, str(label or "Passkey"))
            return _ok(result, 201)
        except (ValueError, RuntimeError):
            return _err("passkey_registration_failed", 400)
        except Exception:
            return _err("passkey_registration_failed", 400)

    @bp.post("/passkeys/auth/options")
    def passkey_auth_options():
        disabled = _feature_or_error(feature_flags.PASSKEYS)
        if disabled:
            return disabled
        if not _rate("passkey_auth_options", 20, 600):
            return _err("rate_limited", 429)
        try:
            raw, challenge = passkeys.authentication_options()
            _store_challenge("passkey_auth_challenge", challenge)
            return Response(raw, mimetype="application/json")
        except RuntimeError as exc:
            return _err(_safe_exception_code(exc, {"passkeys_unavailable"}, "passkeys_unavailable"), 503)

    @bp.post("/passkeys/auth/verify")
    def passkey_auth_verify():
        disabled = _feature_or_error(feature_flags.PASSKEYS)
        if disabled:
            return disabled
        if not _rate("passkey_auth_verify", 20, 600):
            return _err("rate_limited", 429)
        try:
            data = _json_object(128_000)
            challenge = _pop_challenge("passkey_auth_challenge")
            uid = passkeys.verify_authentication(data.get("credential") or data, challenge)
            outcome = login_user_with_passkey(uid)
            return _ok(outcome)
        except Exception:
            return _err("passkey_authentication_failed", 401)

    @bp.delete("/passkeys/<int:passkey_id>")
    def passkey_delete(passkey_id):
        disabled = _feature_or_error(feature_flags.PASSKEYS)
        if disabled:
            return disabled
        uid = current_user_id()
        if not uid or not _active_account():
            return _err("authentication_required", 401)
        return _ok({"deleted": passkeys.delete(int(uid), int(passkey_id))})

    @bp.get("/admin/medical-versioning")
    def admin_medical_versioning():
        if not admin_allowed("medical"):
            return _err("admin_required", 403)
        return _ok(medical_knowledge.versioning_summary())

    @bp.get("/admin/source-monitor")
    def admin_source_status():
        disabled = _feature_or_error(feature_flags.SOURCE_MONITOR)
        if disabled:
            return disabled
        if not admin_allowed("medical"):
            return _err("admin_required", 403)
        return _ok(source_monitor.status())

    @bp.post("/admin/source-monitor/run")
    def admin_source_run():
        disabled = _feature_or_error(feature_flags.SOURCE_MONITOR)
        if disabled:
            return disabled
        if not feature_flags.BACKGROUND_JOBS:
            return _err("background_jobs_disabled", 503)
        if not admin_allowed("medical"):
            return _err("admin_required", 403)
        try:
            data = _json_object()
            if isinstance(data.get("limit"), bool) or isinstance(data.get("timeout"), bool):
                raise ValueError("invalid_job_parameters")
            limit = int(data.get("limit") or 100)
            timeout = float(data.get("timeout") or 5)
            if not 1 <= limit <= 500 or not 1.0 <= timeout <= 10.0:
                raise ValueError("invalid_job_parameters")
            queued = background_jobs.enqueue("source_monitor", {"limit": limit, "timeout": timeout})
            return _ok(queued, 202)
        except (TypeError, ValueError, OverflowError) as exc:
            return _err(_safe_exception_code(exc, {"invalid_job_parameters", "payload_too_large", "json_object_required"}, "invalid_job_parameters"), 400)
        except Exception:
            return _err("job_enqueue_failed", 503)

    @bp.post("/admin/jobs")
    def admin_enqueue_job():
        disabled = _feature_or_error(feature_flags.BACKGROUND_JOBS)
        if disabled:
            return disabled
        if not admin_allowed("access"):
            return _err("admin_required", 403)
        try:
            data = _json_object()
            name = str(data.get("job_name") or "").strip()
            if name == "source_monitor" and not feature_flags.SOURCE_MONITOR:
                return _err("feature_disabled", 404)
            raw_payload = data.get("payload")
            if raw_payload is not None and not isinstance(raw_payload, dict):
                raise ValueError("invalid_job_payload")
            payload = raw_payload or {}
            return _ok(background_jobs.enqueue(name, payload), 202)
        except ValueError as exc:
            return _err(_safe_exception_code(exc, _JOB_ERROR_CODES, "invalid_job_request"), 400)
        except Exception:
            return _err("job_enqueue_failed", 503)

    @bp.get("/admin/jobs/<job_id>")
    def admin_job(job_id):
        disabled = _feature_or_error(feature_flags.BACKGROUND_JOBS)
        if disabled:
            return disabled
        if not admin_allowed("access"):
            return _err("admin_required", 403)
        if not _JOB_ID_RE.fullmatch(str(job_id or "")):
            return _err("job_not_found", 404)
        item = background_jobs.get(job_id)
        return _ok(item) if item else _err("job_not_found", 404)

    return bp
