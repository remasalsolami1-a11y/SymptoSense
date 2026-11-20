"""Single source of truth for the release version: the ``VERSION`` file next to this module.

Runtime code (release_candidate, research_study) reads it from here. Static copies that cannot import Python
(service-worker cache name, .env.example, Dockerfile echo lines, release_metrics.json) are rewritten by
``tools/bump_version.py`` and verified by ``test_versioning.py``, so the version can never silently drift apart.
"""
from pathlib import Path

APP_VERSION = (Path(__file__).resolve().parent / "VERSION").read_text(encoding="utf-8").strip()
MAJOR = APP_VERSION.split(".")[0]
REVISION = "V" + MAJOR
RC_ID = "SymptoSense-v" + MAJOR
SW_CACHE = "symptosense-shell-v" + MAJOR
