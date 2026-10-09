#!/usr/bin/env python3
"""Forwarder: the maintained audit lives in tools/full_interaction_audit.py.

(An older static-only copy used to live here and drifted out of date: it knew
nothing about data-ss-* actions or the runtime url_map and reported false failures.)
"""
import runpy
import sys
from pathlib import Path

sys.argv[0] = str(Path(__file__).resolve().parent / "tools" / "full_interaction_audit.py")
runpy.run_path(sys.argv[0], run_name="__main__")
