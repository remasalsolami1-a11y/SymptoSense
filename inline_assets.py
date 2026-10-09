"""Large static text/data blocks that used to live inside webapp.py as Python string literals.

They are plain files under ``inline_assets/`` so they can be diffed, reviewed and edited without opening a 1.9 MB
module. Content is loaded once at import time and is byte-identical to the former literals.
"""
import json
from pathlib import Path

_DIR = Path(__file__).resolve().parent / "inline_assets"
_CACHE = {}


def text(name):
    if name not in _CACHE:
        with open(_DIR / name, "r", encoding="utf-8", newline="") as fh:
            _CACHE[name] = fh.read()
    return _CACHE[name]


def data(name):
    return json.loads(text(name))
