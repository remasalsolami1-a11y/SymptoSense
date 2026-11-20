"""Conservative FHIR R4 export for user-controlled interoperability.

The export serializes only existing user-entered/observed information. It never
turns SymptoSense guidance into a clinical diagnosis. The generated Bundle is a
``collection`` containing R4 resources and a Composition summary; it is not an
attested clinical document and should be validated by the receiving system.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import math
import uuid

FHIR_VERSION = "4.0.1"
PROFILE_NOTE = "SymptoSense non-diagnostic user export"
FHIR_BASE = "https://symptosensehealth.com/fhir"


def _id(prefix: str, value) -> str:
    digest = hashlib.sha256(f"{prefix}:{value}".encode("utf-8")).hexdigest()[:24]
    return f"{prefix}-{digest}"


def _full_url(resource: dict) -> str:
    stable = f"{FHIR_BASE}/{resource['resourceType']}/{resource['id']}"
    return "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, stable))


def _ref(resource: dict) -> str:
    return _full_url(resource)


def _entry(resource: dict) -> dict:
    return {"fullUrl": _full_url(resource), "resource": resource}



def _fhir_datetime(value) -> str | None:
    if value in (None, ""):
        return None
    raw = str(value).strip()
    if not raw or len(raw) > 64:
        return None
    try:
        normalized = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except (TypeError, ValueError, OverflowError):
        return None


def _medication_status(item: dict) -> str:
    """Map local medication-plan state to a safe R4 MedicationStatement status."""
    raw = str(item.get("status") or "").strip().lower()
    if raw in {"active", "completed", "entered-in-error", "intended", "stopped", "on-hold", "unknown", "not-taken"}:
        return raw
    active = item.get("active")
    if active is True or str(active).strip().lower() in {"1", "true", "yes", "on"}:
        return "active"
    if active is False or str(active).strip().lower() in {"0", "false", "no", "off"}:
        return "stopped"
    return "unknown"


def build_bundle(*, account_id: int, user: dict | None = None, health_profile: dict | None = None,
                 analyses: list[dict] | None = None, blood_tests: list[dict] | None = None,
                 medications: list[dict] | None = None) -> dict:
    user = user or {}
    health_profile = health_profile or {}
    analyses = analyses or []
    blood_tests = blood_tests or []
    medications = medications or []
    generated_at = datetime.now(timezone.utc).isoformat()

    patient = {
        "resourceType": "Patient",
        "id": _id("patient", account_id),
        "meta": {"tag": [{"system": f"{FHIR_BASE}/tags", "code": "user-export", "display": PROFILE_NOTE}]},
    }
    if user.get("name"):
        patient["name"] = [{"text": str(user.get("name"))[:120]}]
    if health_profile.get("gender") in {"male", "female", "other", "unknown"}:
        patient["gender"] = health_profile["gender"]

    device = {
        "resourceType": "Device",
        "id": _id("device", "symptosense-exporter"),
        "status": "active",
        "deviceName": [{"name": "SymptoSense", "type": "user-friendly-name"}],
        "type": {"text": "Non-diagnostic digital health software"},
    }

    entries: list[dict] = [_entry(patient), _entry(device)]
    section_refs: list[dict] = []

    for idx, item in enumerate(analyses[:100]):
        rid = item.get("id") or idx
        symptoms = item.get("symptoms") or []
        if isinstance(symptoms, str):
            symptoms = [symptoms]
        note_parts = [str(x).strip() for x in symptoms if str(x).strip()]
        obs = {
            "resourceType": "Observation",
            "id": _id("symptom", rid),
            "status": "final",
            "code": {"text": "User-reported symptoms"},
            "subject": {"reference": _ref(patient)},
            "valueString": "; ".join(note_parts)[:2000] or "User-reported symptom assessment",
            "note": [{"text": "Non-diagnostic SymptoSense assessment record."}],
        }
        effective = (_fhir_datetime(item.get("timestamp")) or _fhir_datetime(item.get("created_at")))
        if effective:
            obs["effectiveDateTime"] = effective
        entries.append(_entry(obs))
        section_refs.append({"reference": _ref(obs)})

    for idx, item in enumerate(blood_tests[:100]):
        rid = item.get("id") or idx
        obs = {
            "resourceType": "Observation",
            "id": _id("cbc", rid),
            "status": "final",
            "code": {"text": "CBC result imported by user"},
            "subject": {"reference": _ref(patient)},
            "note": [{"text": "User-provided laboratory data; verify against the original laboratory report."}],
        }
        data = item.get("data") if isinstance(item.get("data"), dict) else item
        components = []
        indicators = data.get("indicators")
        if isinstance(indicators, list):
            # The CBC upload route persists measurements inside indicators,
            # not as top-level fields. Keep each measured value and its unit.
            for indicator in indicators[:40]:
                if not isinstance(indicator, dict):
                    continue
                name = indicator.get("name") or indicator.get("key")
                value = indicator.get("value")
                if not name or isinstance(value, bool) or value is None:
                    continue
                try:
                    number = float(value)
                except (TypeError, ValueError, OverflowError):
                    continue
                if not math.isfinite(number):
                    continue
                quantity = {"value": number}
                if indicator.get("unit"):
                    quantity["unit"] = str(indicator["unit"])[:80]
                components.append({"code": {"text": str(name)[:80]}, "valueQuantity": quantity})
        else:
            # Compatibility with legacy flat laboratory dictionaries.
            metadata = {"id", "user_id", "created_at", "timestamp", "member_id",
                        "gender", "age", "level", "summary", "notes", "dangers"}
            for key, val in (data or {}).items():
                if key in metadata:
                    continue
                if isinstance(val, (str, int, float)) and not isinstance(val, bool) and str(val).strip():
                    components.append({"code": {"text": str(key)[:80]}, "valueString": str(val)[:200]})
        if components:
            obs["component"] = components[:40]
        effective = (_fhir_datetime(item.get("timestamp")) or _fhir_datetime(item.get("created_at")))
        if effective:
            obs["effectiveDateTime"] = effective
        entries.append(_entry(obs))
        section_refs.append({"reference": _ref(obs)})

    for idx, item in enumerate(medications[:100]):
        rid = item.get("id") or idx
        name = item.get("med_name") or item.get("name") or item.get("medication")
        if not name:
            continue
        med = {
            "resourceType": "MedicationStatement",
            "id": _id("med", rid),
            "status": _medication_status(item),
            "medicationCodeableConcept": {"text": str(name)[:200]},
            "subject": {"reference": _ref(patient)},
            "note": [{"text": "User-entered medication information."}],
        }
        entries.append(_entry(med))
        section_refs.append({"reference": _ref(med)})

    composition = {
        "resourceType": "Composition",
        "id": _id("composition", f"{account_id}:{generated_at}"),
        "status": "final",
        "type": {"text": "SymptoSense user health summary"},
        "subject": {"reference": _ref(patient)},
        "date": generated_at,
        "author": [{"reference": _ref(device), "display": "SymptoSense"}],
        "title": "SymptoSense user-controlled export",
        "section": [{
            "title": "Important limitation",
            "text": {
                "status": "generated",
                "div": "<div xmlns=\"http://www.w3.org/1999/xhtml\">This export is not a diagnosis and should be verified by a qualified healthcare professional.</div>",
            },
            **({"entry": section_refs} if section_refs else {}),
        }],
    }
    # Keep Composition first among summary resources but Bundle remains a
    # collection, not a clinical document requiring attestation semantics.
    entries.insert(0, _entry(composition))

    return {
        "resourceType": "Bundle",
        "id": _id("bundle", f"{account_id}:{generated_at}"),
        "type": "collection",
        "timestamp": generated_at,
        "meta": {"tag": [{"system": FHIR_BASE, "code": "r4-compatible", "display": FHIR_VERSION}]},
        "entry": entries,
    }
