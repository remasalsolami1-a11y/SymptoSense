"""ProfileDashboardService: read-only, descriptive, no clinical decisions."""
import ast
import dataclasses
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from services import profile_dashboard_service as svc

ROOT = Path(__file__).resolve().parent
NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)


def src(**over):
    base = dict(
        load_profile=lambda: None, latest_record=lambda: None, latest_cbc=lambda: None, latest_vital=lambda: None,
        latest_followup=lambda: None, medication_plans=lambda: [], privacy_settings=lambda: None,
        consent_state=lambda: None, account_name=lambda: "")
    base.update(over)
    return svc.ProfileSources(**base)


def build(**over):
    return svc.ProfileDashboardService(src(**over), now=lambda: NOW).build()


def test_new_user_gets_a_complete_but_empty_object_not_an_error():
    d = build()
    assert d.identity.age is None and d.identity.gender is None
    assert not d.has_any_activity()
    assert set(d.missing_fields) == {"dob", "gender", "allergies", "health_conditions", "medications"}
    assert d.degraded == ()
    assert [a.key for a in d.quick_actions] == ["edit_profile", "add_vital", "medications", "doctor_summary"]


def test_complete_profile_has_no_missing_line_and_no_basics_alert():
    prof = {"dob": "1990-05-01", "gender": "female", "allergies": "لا يوجد", "health_conditions": "none", "medications": ""}
    d = build(load_profile=lambda: prof, medication_plans=lambda: [{"id": 1, "active": True}])
    assert d.missing_fields == ()
    assert svc.ALERT_PROFILE_BASICS_MISSING not in {a.code for a in d.alerts}


def test_height_weight_and_extra_info_are_never_reported_missing():
    d = build(load_profile=lambda: {"dob": "1990-05-01", "gender": "male", "allergies": "x", "health_conditions": "y",
                                    "medications": "z"})
    assert d.missing_fields == ()


def test_medications_come_from_the_medication_system_not_the_free_text():
    d = build(load_profile=lambda: {"medications": ""}, medication_plans=lambda: [{"id": 1, "active": True}])
    assert "medications" not in d.missing_fields and d.medications.active_count == 1


def test_latest_items_expose_kind_date_and_link_only():
    d = build(
        latest_record=lambda: {"id": 7, "timestamp": "2026-10-08T09:00:00+00:00", "urgency": "emergency", "symptoms": "x"},
        latest_cbc=lambda: {"id": 2, "timestamp": "2026-10-03T08:00:00", "data": {"hgb": 5}},
        latest_vital=lambda: {"id": 3, "kind": "bp", "v1": 210, "v2": 130, "measured_at": "2026-10-07T18:00:00Z"},
        latest_followup=lambda: {"record_id": 7, "timestamp": "2026-10-08", "outcome": "worse", "new_sign": True})
    items = [d.latest_symptom_analysis, d.latest_cbc, d.latest_vital, d.latest_followup]
    assert [i.date for i in items] == ["2026-10-08", "2026-10-03", "2026-10-07", "2026-10-08"]
    assert d.latest_symptom_analysis.record_id == 7
    allowed = {"kind", "date", "url", "record_id"}
    for item in items:
        assert {f.name for f in dataclasses.fields(item)} == allowed
        blob = repr(item).lower()
        for leaked in ("emergency", "210", "hgb", "worse", "urgency"):
            assert leaked not in blob


def test_no_alert_is_derived_from_a_medical_value():
    d = build(latest_vital=lambda: {"kind": "bp", "v1": 250, "v2": 150, "measured_at": "2026-10-08"},
              latest_cbc=lambda: {"timestamp": "2026-10-08", "data": {"wbc": 99}},
              latest_record=lambda: {"id": 1, "timestamp": "2026-10-08T11:00:00+00:00", "urgency": "emergency"})
    assert all(a.code in svc.ALLOWED_ALERT_CODES for a in d.alerts)
    assert svc.ALLOWED_ALERT_CODES == {"followup_pending", "profile_basics_missing", "no_active_medications"}


def test_followup_window_matches_the_chat_rules():
    assert (svc.FOLLOWUP_MIN_AGE_HOURS, svc.FOLLOWUP_MAX_AGE_DAYS, svc.FOLLOWUP_QUIET_HOURS_AFTER_ANSWER) == (12, 30, 20)
    rec = lambda hours: {"id": 1, "timestamp": (NOW - timedelta(hours=hours)).isoformat()}
    pending = lambda r, f=None: svc.ALERT_FOLLOWUP_PENDING in {a.code for a in build(latest_record=lambda: r, latest_followup=lambda: f).alerts}
    assert not pending(rec(11))            # too soon
    assert pending(rec(13))                # eligible
    assert pending(rec(24 * 30 - 1))
    assert not pending(rec(24 * 31))       # expired
    answered = {"record_id": 1, "timestamp": (NOW - timedelta(hours=1)).isoformat()}
    assert not pending(rec(48), answered)  # already answered


def test_followup_alert_respects_the_privacy_choice():
    d = build(latest_record=lambda: {"id": 1, "timestamp": (NOW - timedelta(days=2)).isoformat()},
              privacy_settings=lambda: {"use_in_analysis": False})
    assert svc.ALERT_FOLLOWUP_PENDING not in {a.code for a in d.alerts}


def test_no_active_medications_alert_only_when_plans_exist_but_none_active():
    code = svc.ALERT_NO_ACTIVE_MEDICATIONS
    codes = lambda plans: {a.code for a in build(medication_plans=lambda: plans).alerts}
    assert code not in codes([])
    assert code in codes([{"id": 1, "active": False}])
    assert code not in codes([{"id": 1, "active": True}])


def test_a_failing_source_is_isolated_and_reported():
    def boom():
        raise RuntimeError("db down")
    d = build(latest_cbc=boom, latest_record=lambda: {"id": 1, "timestamp": "2026-10-08T00:00:00+00:00"})
    assert d.latest_cbc is None and d.latest_symptom_analysis is not None
    assert d.degraded == ("cbc",)


def test_privacy_summary_reflects_real_flags():
    d = build(privacy_settings=lambda: {"use_in_analysis": False, "use_in_assistant": True},
              consent_state=lambda: {"service_usage": True, "needs_review": False, "analytics_research": True,
                                     "research_participation": False})
    p = d.privacy_summary
    assert (p.use_in_analysis, p.use_in_assistant, p.service_usage, p.analytics_research, p.research_participation) == \
        (False, True, True, True, False)


def test_age_and_name_fallbacks():
    d = build(load_profile=lambda: {"dob": "2000-10-09", "display_name": ""}, account_name=lambda: "Rema")
    assert d.identity.name == "Rema" and isinstance(d.identity.age, int)
    assert svc.age_from_dob("2000-10-09", date(2026, 10, 8)) == 25
    assert svc.age_from_dob("2000-10-08", date(2026, 10, 8)) == 26
    assert svc.age_from_dob("garbage") is None and svc.age_from_dob("1800-01-01") is None


@pytest.mark.parametrize("field,value,ok", [
    ("dob", "1990-02-30", False), ("dob", "2999-01-01", False), ("dob", "1890-01-01", False), ("dob", "1990-05-01", True),
    ("dob", "", True), ("gender", "female", True), ("gender", "x", False), ("gender", "ذكر", True), ("gender", "F", True), ("gender", "", True),
    ("height", "170", True), ("height", "17", False), ("height", "999", False), ("height", "abc", False),
    ("height", "170,5", True), ("weight", "70", True), ("weight", "0", False), ("weight", "1000", False),
    ("weight", "nan", False), ("allergies", "x" * 1001, False), ("allergies", "penicillin", True),
    ("nonsense", "x", False)])
def test_field_validation(field, value, ok):
    assert svc.validate_profile_field(field, value, today=date(2026, 10, 8))[0] is ok


def test_numeric_fields_are_normalised():
    assert svc.validate_profile_field("height", "170,50") == (True, "170.5")
    assert svc.validate_profile_field("weight", " 70.0 ") == (True, "70")


def test_service_is_framework_free_and_does_not_import_other_subsystems():
    tree = ast.parse((ROOT / "services/profile_dashboard_service.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert imported <= {"__future__", "logging", "dataclasses", "datetime", "typing"}, imported


def test_page_renderer_talks_only_to_the_service_object():
    page = (ROOT / "pagelib/profile_dashboard_html.py").read_text(encoding="utf-8")
    for forbidden in ("import db", "from db", "import vitals", "from vitals", "medication_email", "health_file", "privacy_features", "webapp", "sqlite", "psycopg"):
        assert forbidden not in page, forbidden
