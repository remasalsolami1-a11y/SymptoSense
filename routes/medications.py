"""HTTP layer for medication reminders: receive the request, call MedicationService, shape the response.

The rules live in services/medication_service.py. This module keeps only what is genuinely HTTP: reading the request,
the consent gate, cache headers, status codes and the error envelope. Remaining webapp.py dependencies are injected by
register_routes() (transitional; see ARCHITECTURE_AR.md).
"""
from routes import _inject
from flask import jsonify
from flask import redirect
from flask import request
from services.medication_service import MEDS_API_REVISION, MedicationError, MedicationService
import medication_email

DEPS = ("_consent_required_json", "_kick_medication_delivery_now", "_localized_url", "_medication_user_id", "_medication_worker_snapshot", "_mk_error", "_service_consent_ok", "_start_medication_reminder_worker_once", "_t", "api_login_required", "meds_page", )

service = MedicationService(lambda key: _t(key))
_NO_STORE = "private, no-store, no-cache, must-revalidate, max-age=0"
_SPECS = {}
_WRAPPERS = {
    "meds": (),
    "meds_email_action": (),
    "api_meds_plan": ('api_login_required', ),
    "api_meds_plan_item": ('api_login_required', ),
    "api_meds_today": ('api_login_required', ),
    "api_meds_log": ('api_login_required', ),
    "api_meds_snooze": ('api_login_required', ),
    "api_meds_weekly": ('api_login_required', ),
    "api_meds_calendar": ('api_login_required', ),
    "api_meds_settings": ('api_login_required', ),
    "api_meds_telegram_status": ('api_login_required', ),
    "api_meds_telegram_test": ('api_login_required', ),
    "api_meds_telegram_connect": ('api_login_required', ),
    "api_meds_telegram_disconnect": ('api_login_required', ),
    "api_meds_delivery_status": ('api_login_required', ),
    "api_meds": (),
}


def route(rule, **opts):
    def deco(fn):
        _SPECS.setdefault(fn.__name__, {"fn": fn, "rules": []})["rules"].append((rule, opts))
        return fn
    return deco


def _error(exc):
    return jsonify({"ok": False, "error": exc.code}), exc.status


def _forbidden():
    return jsonify({"ok": False, "error": "action_not_allowed", "error_code": "action_not_allowed"}), 403


def _bad_request(exc, default):
    return jsonify({"ok": False, "error": (exc.args[0] if exc.args else "") or default}), 400


def _stamped(payload, *, full=False):
    """JSON response carrying the meds revision and the no-store headers (full adds Pragma/Expires for GETs)."""
    response = jsonify(payload)
    response.headers["Cache-Control"] = _NO_STORE
    if full:
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    response.headers["X-SymptoSense-Meds-Revision"] = MEDS_API_REVISION
    return response


@route("/meds")
def meds():
    # Keep the page reachable so users can inspect/delete already-stored data.
    # Creating or modifying sensitive reminder data is consent-gated server-side.
    return meds_page()


@route("/meds/email-action/<token>")
def meds_email_action(token):
    """One-time action link from a medication reminder email."""
    try:
        result = medication_email.handle_email_action(str(token or ""))
        lang = "en" if result.get("lang") == "en" else "ar"
        state = "taken" if result.get("status") == "taken" else "snoozed"
        return redirect(_localized_url("/meds", lang) + "?email_action=" + state, code=302)
    except (PermissionError, ValueError):
        lang = "en" if str(request.args.get("lang") or "").lower() == "en" else "ar"
        return redirect(_localized_url("/meds", lang) + "?email_action=invalid", code=302)


@route("/api/meds/plan", methods=["GET", "POST"])
def api_meds_plan():
    try:
        uid = _medication_user_id()
        if request.method == "POST":
            payload = service.create_plan(uid, request.get_json(silent=True))
            _start_medication_reminder_worker_once()
            _kick_medication_delivery_now()
            return _stamped(payload)
        return _stamped(service.list_plans(uid, request.args.get("member")), full=True)
    except MedicationError as exc: return _error(exc)
    except PermissionError: return _forbidden()
    except (TypeError, ValueError) as exc: return _bad_request(exc, "invalid_reminder")
    except Exception as exc: return _mk_error(exc)


@route("/api/meds/plan/<int:pid>", methods=["PUT", "DELETE"])
def api_meds_plan_item(pid):
    try:
        uid = _medication_user_id()
        if request.method == "DELETE":
            return _stamped(service.delete_plan(uid, pid), full=True)
        # Editing a reminder is an explicit user action; no additional consent gate.
        payload = service.update_plan(uid, pid, request.get_json(silent=True))
        _start_medication_reminder_worker_once()
        _kick_medication_delivery_now()
        return _stamped(payload)
    except MedicationError as exc: return _error(exc)
    except PermissionError: return _forbidden()
    except (TypeError, ValueError) as exc: return _bad_request(exc, "invalid_reminder")
    except Exception as exc: return _mk_error(exc)


@route("/api/meds/today", methods=["GET"])
def api_meds_today():
    try:
        return jsonify(service.today(_medication_user_id()))
    except Exception as exc: return _mk_error(exc)


@route("/api/meds/log", methods=["POST"])
def api_meds_log():
    if not _service_consent_ok(): return _consent_required_json("/meds")
    try:
        return jsonify(service.log_status(_medication_user_id(), request.get_json(silent=True)))
    except MedicationError as exc: return _error(exc)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "invalid_reminder_status"}), 400
    except Exception as exc: return _mk_error(exc)


@route("/api/meds/snooze", methods=["POST"])
def api_meds_snooze():
    if not _service_consent_ok(): return _consent_required_json("/meds")
    try:
        return jsonify(service.snooze(_medication_user_id(), request.get_json(silent=True)))
    except PermissionError: return _forbidden()
    except (TypeError, ValueError): return jsonify({"ok": False, "error": "invalid_reminder"}), 400
    except Exception as exc: return _mk_error(exc)


@route("/api/meds/weekly", methods=["GET"])
def api_meds_weekly():
    try:
        return jsonify(service.weekly(_medication_user_id(), request.args.get("member")))
    except (MedicationError, TypeError, ValueError): return jsonify({"ok": False, "error": "invalid_member"}), 400
    except Exception as exc: return _mk_error(exc)


@route("/api/meds/calendar", methods=["GET"])
def api_meds_calendar():
    try:
        return jsonify(service.calendar(_medication_user_id(), request.args.get("member"), request.args.get("days")))
    except (MedicationError, TypeError, ValueError): return jsonify({"ok": False, "error": "invalid_query"}), 400
    except Exception as exc: return _mk_error(exc)


@route("/api/meds/settings", methods=["GET", "PUT"])
def api_meds_settings():
    try:
        if request.method == "GET": return jsonify(service.get_settings(_medication_user_id()))
        return jsonify(service.save_settings(_medication_user_id(), request.get_json(silent=True)))
    except Exception as exc: return _mk_error(exc)


@route("/api/meds/telegram/status", methods=["GET"])
def api_meds_telegram_status():
    try:
        return jsonify(service.telegram_status(_medication_user_id()))
    except Exception as exc:
        return _mk_error(exc)


@route("/api/meds/telegram/test", methods=["POST"])
def api_meds_telegram_test():
    try:
        _start_medication_reminder_worker_once()
        payload, status = service.telegram_test(_medication_user_id())
        return jsonify(payload), status
    except Exception as exc:
        return _mk_error(exc)


@route("/api/meds/telegram/connect", methods=["POST"])
def api_meds_telegram_connect():
    # Linking Telegram is explicitly initiated by the signed-in user.
    try:
        payload, status = service.telegram_connect(_medication_user_id())
        return jsonify(payload), status
    except Exception as exc:
        return _mk_error(exc)


@route("/api/meds/telegram/disconnect", methods=["POST"])
def api_meds_telegram_disconnect():
    try:
        return jsonify(service.telegram_disconnect(_medication_user_id()))
    except Exception as exc:
        return _mk_error(exc)


@route("/api/meds/delivery-status", methods=["GET"])
def api_meds_delivery_status():
    # The worker flag is rebound at runtime in webapp.py, so it is read live on every call (never captured at import).
    return jsonify(service.delivery_status(_medication_worker_snapshot()))


@route("/api/meds", methods=["POST"])
def api_meds():
    data = request.get_json(force=True)
    try:
        return jsonify(service.check_interactions_text(data.get("text", "")))
    except Exception as e:
        return _mk_error(e, 500)


def register_routes(app, namespace):
    """Inject webapp dependencies, apply the original decorators, and add the URL rules (same endpoint names)."""
    missing = [n for n in DEPS if n not in namespace]
    if missing:
        raise RuntimeError("routes.medications: missing dependencies %s" % missing)
    g = globals()
    for n in DEPS:
        g[n] = _inject.dependency(namespace, n)
    g["app"] = app
    for name, spec in _SPECS.items():
        view = spec["fn"]
        for w in reversed(_WRAPPERS.get(name, ())):
            view = _inject.resolve_wrapper(w, g)(view)
        for rule, opts in spec["rules"]:
            kw = dict(opts)
            endpoint = kw.pop("endpoint", name)
            app.add_url_rule(rule, endpoint=endpoint, view_func=view, **kw)
