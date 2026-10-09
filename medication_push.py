"""Deprecated compatibility shim.

Medication reminders moved from Web Push to email-only delivery in V175.
This module intentionally contains no VAPID, PushManager, push subscription,
or browser-notification delivery logic.
"""
from medication_email import (  # noqa: F401
    init_schema,
    valid_timezone,
    save_plan,
    list_plans,
    disable_plan,
    get_settings,
    save_settings,
    schedule_snooze,
    reminder_calendar,
    plans_today,
    weekly_summary,
    send_due_emails,
    handle_email_action,
    delivery_summary,
    email_provider_status,
)


def push_config():
    return {"configured": False, "public_key": "", "deprecated": True, "replacement": "email"}


def configured_worker_mode():
    return "disabled"


def worker_status(*_args, **_kwargs):
    return {"online": False, "mode": "disabled", "expected_mode": "disabled", "deprecated": True, "replacement": "email"}


def delivery_verification_summary(*_args, **_kwargs):
    return {"sent": 0, "displayed": 0, "clicked": 0, "acted": 0, "deprecated": True, "replacement": "email"}


def start_embedded_worker_once():
    return False
