"""Medication reminders: the business rules behind /api/meds/*.

Framework-free on purpose: no Flask import, no webapp globals. Every public method takes plain values (the signed-in
user id, query/body values) and returns ``(payload, status)`` or raises :class:`MedicationError`. The route layer only
translates HTTP to these calls and back, so the rules can be tested without a request context. Persistence still goes
through ``medication_email`` / ``medication_telegram`` / ``db``; a repository layer can replace those later without
touching the routes.
"""
from __future__ import annotations

from datetime import datetime, timezone

import db
import medication_email
import medication_telegram
import medication_warnings

MEDS_API_REVISION = "v216-runtime-lock-fix"


class MedicationError(Exception):
    """A client-visible failure: ``code`` is the JSON ``error`` value, ``status`` the HTTP status."""

    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


def _member_filter(raw, *, error: str = "invalid_member"):
    """None for 'all members'; a non-negative int otherwise (same rules the routes always applied)."""
    if raw in (None, ""):
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise MedicationError(error, 400)
    if value < 0:
        raise MedicationError(error, 400)
    return value


def _today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


class MedicationService:
    """``translate(key)`` gives the localized label for the current request ("me")."""

    def __init__(self, translate):
        self._t = translate

    # -- plans ---------------------------------------------------------------------------------------------------
    def _label_members(self, uid, plans):
        members = {m["id"]: m["name"] for m in db.list_members(uid)}
        for plan in plans:
            plan["member_name"] = members.get(plan["member_id"], self._t("me_short") if plan["member_id"] == 0 else "")
        return plans

    def list_plans(self, uid, member=None):
        db.init_db()
        medication_email.init_schema()
        plans = medication_email.list_plans(uid, member_id=_member_filter(member))
        return {"ok": True, "plans": self._label_members(uid, plans), "meds_revision": MEDS_API_REVISION}

    @staticmethod
    def _prepare_channel(uid, data):
        channel = "telegram" if str(data.get("delivery_channel") or "email").lower() == "telegram" else "email"
        info = {}
        if channel == "telegram":
            try:
                info = medication_telegram.prepare_username(uid, data.get("telegram_username"))
            except ValueError:
                raise MedicationError("invalid_telegram_username", 400)
        return channel, info

    @staticmethod
    def _saved_payload(plan_id, channel, info):
        return {"ok": True, "id": plan_id, "delivery_channel": channel,
                "telegram_activation_url": info.get("url"), "telegram_linked": bool(info.get("linked")),
                "telegram_username": info.get("username") or "", "meds_revision": MEDS_API_REVISION}

    def create_plan(self, uid, data):
        """Creating a reminder is an explicit user action (authentication + CSRF still apply at the route)."""
        db.init_db()
        medication_email.init_schema()
        data = data or {}
        channel, info = self._prepare_channel(uid, data)
        return self._saved_payload(medication_email.save_plan(uid, data), channel, info)

    def update_plan(self, uid, plan_id, data):
        medication_email.init_schema()
        data = data or {}
        channel, info = self._prepare_channel(uid, data)
        return self._saved_payload(medication_email.save_plan(uid, data, plan_id=plan_id), channel, info)

    def delete_plan(self, uid, plan_id):
        medication_email.init_schema()
        if not medication_email.delete_plan(uid, plan_id):
            raise MedicationError("not_found", 404)
        if any(int(p.get("id") or 0) == int(plan_id) for p in medication_email.list_plans(uid, active_only=False)):
            raise MedicationError("delete_not_persisted", 500)
        return {"ok": True, "deleted": True, "id": int(plan_id), "meds_revision": MEDS_API_REVISION}

    # -- today / logging -----------------------------------------------------------------------------------------
    def today(self, uid):
        return {"ok": True, "plans": self._label_members(uid, medication_email.plans_today(uid))}

    def log_status(self, uid, data):
        data = data or {}
        plan_id = int(data.get("plan_id") or 0)
        log_time = str(data.get("time") or "")
        status = str(data.get("status") or "taken")
        log_date = str(data.get("date") or _today_iso())
        if not plan_id or not log_time or status not in ("taken", "skipped"):
            raise MedicationError("invalid_reminder_status", 400)
        owned = {p["id"]: p for p in medication_email.list_plans(uid, active_only=False)}
        if plan_id not in owned:
            raise MedicationError("forbidden", 403)
        db.log_med_status(uid, int(owned[plan_id].get("member_id") or 0), plan_id, log_date, log_time, status)
        return {"ok": True}

    def snooze(self, uid, data):
        data = data or {}
        minutes = medication_email.schedule_snooze(uid, int(data.get("plan_id") or 0), 0, str(data.get("date") or _today_iso()),
                                                   str(data.get("time") or ""), data.get("minutes"))
        return {"ok": True, "minutes": minutes}

    # -- summaries -----------------------------------------------------------------------------------------------
    def weekly(self, uid, member=None):
        return {"ok": True, **medication_email.weekly_summary(uid, _member_filter(member))}

    def calendar(self, uid, member=None, days=None):
        try:
            span = max(1, min(90, int(days or 30)))
        except (TypeError, ValueError):
            raise MedicationError("invalid_query", 400)
        return {"ok": True, **medication_email.reminder_calendar(uid, _member_filter(member, error="invalid_query"), span)}

    # -- settings ------------------------------------------------------------------------------------------------
    def get_settings(self, uid):
        return {"ok": True, "settings": medication_email.get_settings(uid)}

    def save_settings(self, uid, data):
        return {"ok": True, "settings": medication_email.save_settings(uid, data or {})}

    # -- telegram ------------------------------------------------------------------------------------------------
    def telegram_status(self, uid):
        return {"ok": True, **medication_telegram.status(uid)}

    def telegram_test(self, uid):
        result = medication_telegram.send_test(uid)
        if result.get("sent"):
            return {"ok": True, "sent": True}, 200
        reason = str(result.get("reason") or "telegram_send_failed")
        return {"ok": False, "sent": False, "reason": reason, "error": reason}, (409 if reason == "not_linked" else 502)

    def telegram_connect(self, uid):
        data = medication_telegram.create_connect_link(uid)
        if not data.get("configured"):
            return {"ok": False, "error": "telegram_not_configured", "config_error": data.get("config_error") or "telegram_not_configured"}, 503
        return {"ok": True, **data}, 200

    def telegram_disconnect(self, uid):
        medication_telegram.disconnect(uid)
        return {"ok": True}

    # -- operations ----------------------------------------------------------------------------------------------
    @staticmethod
    def delivery_status(worker):
        """``worker`` is the live worker snapshot ({"started": bool, "state": dict}); read per call, never cached."""
        provider = medication_email.email_provider_status()
        state = dict(worker.get("state") or {})
        return {"ok": True, "worker_started": bool(worker.get("started")), "worker_running": bool(state.get("running")),
                "last_run": state.get("last_run"), "last_result": state.get("last_result"), "last_error": state.get("last_error"),
                "email_configured": bool(provider.get("configured")), "provider": provider.get("provider", "none")}

    @staticmethod
    def check_interactions_text(text):
        """Free-text medication check (warnings come from medication_warnings, a reviewed catalog)."""
        return {"ok": True, "warnings": medication_warnings.check_medications(text or "") or []}
