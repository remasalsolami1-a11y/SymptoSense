"""Fast, deterministic demo/preview result for /api/analyze's demo_mode.

This module was missing from the uploaded project (webapp.py imports
``demo_analysis_result`` but the file did not exist, which would have made
the whole application fail to start). Rather than fabricate a JSON shape by
hand and risk missing a field the frontend depends on, this reuses the real,
already-tested triage engine (analysis_core.run_analysis) against a fixed,
clearly-synthetic patient -- a fixed, clearly-synthetic headache/nausea walkthrough matching the public demo UI.
That keeps the demo path on the exact same code as real analyses (so it
never silently drifts out of sync with the real result shape), while still
being fast and side-effect-free: demo_mode's caller in webapp.py never
reaches the code that saves a record or touches consent/user data.
"""
from __future__ import annotations

import copy
import time

import analysis_core

_DEMO_PATIENT = {
    # Keep this in sync with the public "ready-made demo" UI.  The scenario is
    # deliberately non-emergency so visitors see the normal result structure
    # immediately, while emergency handling is covered by separate tests.
    "age": 24,
    "gender": "f",
    "symptoms": ["صداع", "غثيان"],
    "duration": "1-3 أيام",
    "severity": 2,
    "conditions": "",
    "medications": "",
    "allergies": "",
    "notes": "",
    "user_id": None,
}


_CACHE: dict = {}
_TTL = 600  # seconds; the demo is fixed, so recomputing it per page view only costs time


def demo_analysis_result(lang: str = "ar") -> dict:
    """Return the demo result, cached briefly: rendering /chat used to run a
    full analysis (160+ database queries) on every page view."""
    now = time.time()
    hit = _CACHE.get(lang)
    if hit and now - hit[0] < _TTL:
        return copy.deepcopy(hit[1])
    result = analysis_core.run_analysis(dict(_DEMO_PATIENT), lang=lang)
    result["demo_mode"] = True
    _CACHE[lang] = (now, copy.deepcopy(result))
    return result
