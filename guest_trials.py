"""Keep anonymous (no-account) symptom analyses in the admin trial export.

A guest analysis is saved as a minimal, anonymous trial row ONLY when the visitor
has accepted optional usage analytics or scientific-research participation (the
service consent alone covers running the analysis, not keeping a copy). What is
stored: age, gender, symptoms, duration, severity and urgency. NOT stored:
free-text notes, conditions, medications, allergies, name, e-mail, IP address or
the browser session id itself (only a one-way hash of the random guest key).
Each purpose is flagged and withdrawn independently (privacy_features).
"""
import logging

import db

_log = logging.getLogger(__name__)
_SAVE_ERRORS = db.DB_ERRORS + (RuntimeError, OSError, ValueError, TypeError, KeyError)


def save(owner_key, lang, patient, result, demo_mode, analytics_ok, research_ok):
    """Return the new record id, or None when nothing was saved (never raises)."""
    try:
        if demo_mode or not owner_key or not (analytics_ok or research_ok):
            return None  # product-improvement use: needs at least one independently chosen optional purpose
        if patient.get("user_id") or result.get("record_id"):
            return None  # signed-in users are saved by the normal path
        symptoms = [str(s).strip() for s in (patient.get("symptoms") or []) if str(s).strip()][:20]
        if not symptoms:
            return None
        urgency = str(result.get("urgency") or ("high" if result.get("emergency") else "")) or None
        snapshot = {"age": patient.get("age"), "gender": patient.get("gender"), "symptoms": symptoms,
                    "duration": patient.get("duration") or "", "severity": patient.get("severity")}
        data = {"symptoms": symptoms, "input_snapshot": snapshot, "urgency": urgency,
                "emergency": bool(result.get("emergency")), "guest": True}
        rec = db.save_analysis_record_with_result(
            "guest-" + str(owner_key), lang, patient.get("age"), patient.get("gender"), symptoms,
            patient.get("duration"), patient.get("severity"), urgency, data)
        try:
            import privacy_features
            privacy_features.set_record_consent_eligibility(int(rec), bool(analytics_ok), bool(research_ok))
        except _SAVE_ERRORS:
            _log.debug("guest trial consent flags skipped", exc_info=True)
        return rec
    except _SAVE_ERRORS:
        _log.warning("guest symptom trial could not be saved", exc_info=True)
        return None
