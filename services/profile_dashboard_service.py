"""Read-only aggregator behind the "My profile" dashboard.

Scope, deliberately narrow
--------------------------
* It COLLECTS facts from Health File, Medications, CBC, Vitals, Follow-up and Privacy and returns ONE object
  (:class:`ProfileDashboardData`). The page renders that object and never talks to those systems itself.
* It makes NO clinical decision. There are no thresholds on medical values, no triage, no interpretation. For the
  "my status now" cards it exposes only *what* happened and *when* (kind + date + a link) - never a value, a result,
  a decision level or any wording such as "needs attention" derived from a medical value. That stays true until the
  relevant areas are signed off by a clinician (see ``clinical_signoff.json``).
* The only alerts are administrative and come from the closed list :data:`ALLOWED_ALERT_CODES`. Adding a code is a
  reviewed change (``test_profile_dashboard_service.py`` pins the list).
* Framework-free: no Flask, no ``webapp`` globals. Data comes in through :class:`ProfileSources` (plain callables),
  so everything here is testable without a database. :func:`db_sources` wires the real ``db`` module lazily.
* A failing source never blanks the page: it is recorded in ``degraded`` and treated as "no data".
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional

log = logging.getLogger(__name__)

# ---- administrative alert vocabulary (closed list; each addition must be reviewed) --------------------------
ALERT_FOLLOWUP_PENDING = "followup_pending"
ALERT_PROFILE_BASICS_MISSING = "profile_basics_missing"
ALERT_NO_ACTIVE_MEDICATIONS = "no_active_medications"
ALLOWED_ALERT_CODES = frozenset({ALERT_FOLLOWUP_PENDING, ALERT_PROFILE_BASICS_MISSING, ALERT_NO_ACTIVE_MEDICATIONS})

# Follow-up timing is NOT new: these are the exact windows /api/smart-followup already applies when it offers a
# follow-up (not before 12 h, not after 30 days, not again within 20 h of an answer). Mirrored here so the dashboard
# and the chat never disagree about whether a follow-up is "due". test_profile_dashboard_service pins them.
FOLLOWUP_MIN_AGE_HOURS = 12
FOLLOWUP_MAX_AGE_DAYS = 30
FOLLOWUP_QUIET_HOURS_AFTER_ANSWER = 20

# What counts as "essential" for the missing-info line. Height/weight and free-text extras are optional and sensitive:
# they are NEVER listed as missing.
ESSENTIAL_FIELDS = ("dob", "gender", "allergies", "health_conditions", "medications")

# Input hygiene for the profile form (not clinical interpretation: only "is this a plausible number/date at all").
HEIGHT_CM = (30.0, 260.0)
WEIGHT_KG = (2.0, 400.0)
MAX_AGE_YEARS = 120
GENDER_CODES = frozenset({"", "male", "female", "other", "prefer_not_to_say"})
TEXT_FIELD_MAX = {"display_name": 80, "allergies": 1000, "health_conditions": 1000, "medications": 1000, "extra_info": 2000,
                  "activity_level": 40}
GENDER_SYNONYMS = {"m": "male", "f": "female", "ذكر": "male", "أنثى": "female", "انثى": "female"}

URLS = {
    "edit_profile": "/manage",
    "history": "/history",
    "cbc": "/blood",
    "vitals": "/vitals",
    "medications": "/meds",
    "doctor_summary": "/health-file?view=doctor",
    "privacy_center": "/privacy-center",
}


# ---- value objects --------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Identity:
    name: str = ""
    age: Optional[int] = None
    gender: Optional[str] = None          # code: male | female | other | prefer_not_to_say | None
    dob: Optional[str] = None             # ISO date
    height_cm: Optional[str] = None       # as stored (display only)
    weight_kg: Optional[str] = None
    updated_at: Optional[str] = None      # ISO date of the last profile save


@dataclass(frozen=True)
class ActivityItem:
    """One "latest ..." row: what, when, and where to open it. Deliberately no value/result/level field."""
    kind: str                             # symptom_analysis | cbc | vital | followup
    date: str                             # ISO date (YYYY-MM-DD)
    url: str
    record_id: Optional[int] = None


@dataclass(frozen=True)
class MedicationSummary:
    active_count: int = 0
    total_count: int = 0
    url: str = URLS["medications"]


@dataclass(frozen=True)
class PrivacySummary:
    use_in_analysis: bool = True
    use_in_assistant: bool = True
    service_usage: bool = False
    needs_review: bool = False
    analytics_research: bool = False
    research_participation: bool = False
    url: str = URLS["privacy_center"]


@dataclass(frozen=True)
class QuickAction:
    key: str
    url: str


@dataclass(frozen=True)
class Alert:
    code: str
    url: str


@dataclass(frozen=True)
class ProfileDashboardData:
    identity: Identity
    missing_fields: tuple
    latest_symptom_analysis: Optional[ActivityItem]
    latest_cbc: Optional[ActivityItem]
    latest_vital: Optional[ActivityItem]
    latest_followup: Optional[ActivityItem]
    medications: MedicationSummary
    privacy_summary: PrivacySummary
    quick_actions: tuple
    alerts: tuple
    degraded: tuple = field(default_factory=tuple)

    def has_any_activity(self) -> bool:
        return any((self.latest_symptom_analysis, self.latest_cbc, self.latest_vital, self.latest_followup))


@dataclass
class ProfileSources:
    """Zero-argument callables, each already bound to the signed-in user. Any may raise; any may return None."""
    load_profile: Callable[[], Optional[dict]]
    latest_record: Callable[[], Optional[dict]]
    latest_cbc: Callable[[], Optional[dict]]
    latest_vital: Callable[[], Optional[dict]]
    latest_followup: Callable[[], Optional[dict]]
    medication_plans: Callable[[], list]
    privacy_settings: Callable[[], Optional[dict]]
    consent_state: Callable[[], Optional[dict]]
    account_name: Callable[[], str] = lambda: ""


# ---- small pure helpers ---------------------------------------------------------------------------------------
def parse_timestamp(value) -> Optional[datetime]:
    """Tolerant ISO parser (date, naive or tz-aware datetime, trailing Z). Returns aware UTC or None."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        ts = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            ts = datetime.combine(date.fromisoformat(text[:10]), datetime.min.time())
        except ValueError:
            return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _iso_date(value) -> Optional[str]:
    ts = parse_timestamp(value)
    return ts.date().isoformat() if ts else None


def age_from_dob(dob, today: Optional[date] = None) -> Optional[int]:
    try:
        born = date.fromisoformat(str(dob or "").strip()[:10])
    except ValueError:
        return None
    today = today or date.today()
    years = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    return years if 0 <= years <= MAX_AGE_YEARS else None


def _clean(value) -> str:
    return str(value or "").strip()


def validate_profile_field(field_name: str, value, today: Optional[date] = None):
    """Validate one profile field. Returns ``(ok, cleaned_value_or_error_code)``.

    Empty is always allowed (the profile is optional). Only input plausibility is checked; nothing here interprets
    a value medically.
    """
    raw = _clean(value)
    today = today or date.today()
    if field_name == "dob":
        if not raw:
            return True, ""
        try:
            born = date.fromisoformat(raw)
        except ValueError:
            return False, "invalid_dob"
        if born > today:
            return False, "dob_in_future"
        if age_from_dob(raw, today) is None:
            return False, "dob_out_of_range"
        return True, born.isoformat()
    if field_name == "gender":
        raw = GENDER_SYNONYMS.get(raw.lower(), raw.lower())
        return (True, raw) if raw in GENDER_CODES else (False, "invalid_gender")
    if field_name in ("height", "weight"):
        if not raw:
            return True, ""
        try:
            number = float(raw.replace(",", ".").replace("٫", "."))
        except ValueError:
            return False, "invalid_" + field_name
        low, high = HEIGHT_CM if field_name == "height" else WEIGHT_KG
        if not (low <= number <= high) or number != number:
            return False, field_name + "_out_of_range"
        return True, ("%.1f" % number).rstrip("0").rstrip(".")
    if field_name in TEXT_FIELD_MAX:
        if len(raw) > TEXT_FIELD_MAX[field_name]:
            return False, field_name + "_too_long"
        return True, raw
    if field_name == "lang":
        return True, "en" if raw == "en" else "ar"
    return False, "invalid_field"


def missing_fields(profile: Optional[dict], plans: list) -> tuple:
    """Essential items with no answer. Any non-empty text counts as an answer (including "none")."""
    profile = profile or {}
    out = []
    for key in ESSENTIAL_FIELDS:
        if key == "medications":
            # The medication system is the source of truth; the free-text field only counts as a fallback.
            if not plans and not _clean(profile.get("medications")):
                out.append(key)
        elif not _clean(profile.get(key)):
            out.append(key)
    return tuple(out)


def followup_pending(record_ts: Optional[datetime], latest_followup_ts: Optional[datetime], now: datetime) -> bool:
    """Same eligibility the chat uses (see module constants). Timing only, no medical content."""
    if record_ts is None:
        return False
    age = now - record_ts
    if age < timedelta(hours=FOLLOWUP_MIN_AGE_HOURS) or age > timedelta(days=FOLLOWUP_MAX_AGE_DAYS):
        return False
    if latest_followup_ts is not None:
        if latest_followup_ts >= record_ts:
            return False  # already answered for this analysis (or a later one)
    return True


# ---- the service ----------------------------------------------------------------------------------------------
class ProfileDashboardService:
    def __init__(self, sources: ProfileSources, now: Optional[Callable[[], datetime]] = None):
        self._s = sources
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._degraded: list = []

    def _safe(self, label: str, call, default=None):
        try:
            result = call()
            return default if result is None else result
        except Exception:
            log.warning("profile dashboard source %r failed; treated as empty", label, exc_info=True)
            self._degraded.append(label)
            return default

    def build(self) -> ProfileDashboardData:
        s = self._s
        now = self._now()
        profile = self._safe("health_file", s.load_profile, {}) or {}
        plans = self._safe("medications", s.medication_plans, []) or []
        record = self._safe("symptom_analysis", s.latest_record)
        cbc = self._safe("cbc", s.latest_cbc)
        vital = self._safe("vitals", s.latest_vital)
        followup = self._safe("followup", s.latest_followup)
        privacy = self._safe("privacy", s.privacy_settings, {}) or {}
        consent = self._safe("consent", s.consent_state, {}) or {}
        account_name = self._safe("account", s.account_name, "") or ""

        identity = Identity(
            name=_clean(profile.get("display_name")) or _clean(account_name),
            age=age_from_dob(profile.get("dob")),
            gender=_clean(profile.get("gender")) or None,
            dob=_clean(profile.get("dob")) or None,
            height_cm=_clean(profile.get("height")) or None,
            weight_kg=_clean(profile.get("weight")) or None,
            updated_at=_iso_date(profile.get("updated_at")),
        )
        missing = missing_fields(profile, plans)

        record_date = _iso_date((record or {}).get("timestamp"))
        latest_symptom = (ActivityItem("symptom_analysis", record_date, URLS["history"],
                                       int(record["id"]) if str(record.get("id", "")).isdigit() else None)
                          if record and record_date else None)
        cbc_date = _iso_date((cbc or {}).get("timestamp"))
        latest_cbc = ActivityItem("cbc", cbc_date, URLS["cbc"]) if cbc and cbc_date else None
        vital_date = _iso_date((vital or {}).get("measured_at"))
        latest_vital = ActivityItem("vital", vital_date, URLS["vitals"]) if vital and vital_date else None
        followup_date = _iso_date((followup or {}).get("timestamp"))
        latest_followup = ActivityItem("followup", followup_date, URLS["history"]) if followup and followup_date else None

        active = [p for p in plans if bool(p.get("active", True))]
        meds = MedicationSummary(active_count=len(active), total_count=len(plans))

        privacy_summary = PrivacySummary(
            use_in_analysis=bool(privacy.get("use_in_analysis", True)),
            use_in_assistant=bool(privacy.get("use_in_assistant", True)),
            service_usage=bool(consent.get("service_usage")),
            needs_review=bool(consent.get("needs_review")),
            analytics_research=bool(consent.get("analytics_research")),
            research_participation=bool(consent.get("research_participation")),
        )

        alerts = []
        if privacy_summary.use_in_analysis and followup_pending(
                parse_timestamp((record or {}).get("timestamp")),
                parse_timestamp((followup or {}).get("timestamp")), now):
            alerts.append(Alert(ALERT_FOLLOWUP_PENDING, URLS["history"]))
        if missing:
            alerts.append(Alert(ALERT_PROFILE_BASICS_MISSING, URLS["edit_profile"]))
        if plans and not active:
            alerts.append(Alert(ALERT_NO_ACTIVE_MEDICATIONS, URLS["medications"]))
        assert all(a.code in ALLOWED_ALERT_CODES for a in alerts)

        actions = (QuickAction("edit_profile", URLS["edit_profile"]), QuickAction("add_vital", URLS["vitals"]),
                   QuickAction("medications", URLS["medications"]), QuickAction("doctor_summary", URLS["doctor_summary"]))
        return ProfileDashboardData(
            identity=identity, missing_fields=missing, latest_symptom_analysis=latest_symptom, latest_cbc=latest_cbc,
            latest_vital=latest_vital, latest_followup=latest_followup, medications=meds,
            privacy_summary=privacy_summary, quick_actions=actions, alerts=tuple(alerts),
            degraded=tuple(dict.fromkeys(self._degraded)),
        )


def db_sources(db, *, account_id, data_id, medication_id, consent_state, account_name="") -> ProfileSources:
    """Bind the real ``db`` functions to one signed-in user. Imports nothing itself, so tests never need a database."""
    return ProfileSources(
        load_profile=lambda: db.load_health_profile(account_id),
        latest_record=lambda: (db.get_records(data_id, limit=1, member_id=0) or [None])[0],
        latest_cbc=lambda: (db.get_blood_tests(data_id, limit=1, member_id=0) or [None])[0],
        latest_vital=lambda: (db.get_vitals(data_id, member_id=0, days=3650, limit=1) or [None])[0],
        latest_followup=lambda: db.get_latest_followup(data_id),
        medication_plans=lambda: db.list_med_plans(medication_id, member_id=0, active_only=False) if medication_id else [],
        privacy_settings=lambda: db.load_privacy_settings(account_id),
        consent_state=consent_state,
        account_name=lambda: account_name,
    )
