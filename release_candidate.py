"""Release-candidate metadata and launch gates for SymptoSense."""
from __future__ import annotations

import os

import versioning

RC_ID = os.environ.get("RELEASE_CANDIDATE_ID", versioning.RC_ID).strip() or versioning.RC_ID
APP_VERSION = os.environ.get("APP_VERSION", versioning.APP_VERSION)
RELEASE_CHANNEL = os.environ.get("RELEASE_CHANNEL", "final").strip().lower() or "final"
FEATURE_FREEZE = os.environ.get("FEATURE_FREEZE", "1").strip().lower() not in {"0","false","no","off"}


def metadata():
    return {
        "release_candidate_id": RC_ID,
        "app_version": APP_VERSION,
        "release_channel": RELEASE_CHANNEL,
        "feature_freeze": FEATURE_FREEZE,
        "policy": "Bug fixes, safety fixes, documentation, and launch verification only while feature freeze is active.",
    }
