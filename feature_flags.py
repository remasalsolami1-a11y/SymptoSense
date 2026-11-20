"""Runtime feature flags for large optional SymptoSense capabilities.

Flags default to ON for the V47 release, but every capability is designed to
fail closed/fallback safely when its optional infrastructure is unavailable.
"""
from __future__ import annotations
import os


def _enabled(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() not in {"0", "false", "no", "off", "disabled"}


SYMPTOM_ENGINE_V2 = _enabled("FEATURE_SYMPTOM_ENGINE_V2", True)
SEARCH_ENGINE_V2 = _enabled("FEATURE_SEARCH_ENGINE_V2", True)
FHIR_EXPORT = _enabled("FEATURE_FHIR_EXPORT", True)
PASSKEYS = _enabled("FEATURE_PASSKEYS", True)
SOURCE_MONITOR = _enabled("FEATURE_SOURCE_MONITOR", True)
BACKGROUND_JOBS = _enabled("FEATURE_BACKGROUND_JOBS", True)
API_V1 = _enabled("FEATURE_API_V1", True)
REQUEST_TRACING = _enabled("FEATURE_REQUEST_TRACING", True)


def public_state() -> dict:
    return {
        "symptom_engine_v2": SYMPTOM_ENGINE_V2,
        "search_engine_v2": SEARCH_ENGINE_V2,
        "fhir_export": FHIR_EXPORT,
        "passkeys": PASSKEYS,
        "source_monitor": SOURCE_MONITOR,
        "background_jobs": BACKGROUND_JOBS,
        "api_v1": API_V1,
        "request_tracing": REQUEST_TRACING,
    }
