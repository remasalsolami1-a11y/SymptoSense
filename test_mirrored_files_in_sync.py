"""Files that intentionally exist twice (flat runtime copy + static/views copy)
must stay byte-identical so one copy is never edited and the stale one shipped."""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXCLUDE_DIRS = {"__pycache__", "node_modules", ".git", "tools", "chat"}  # tools/ copies differ on purpose (paths); static/js/chat/ are split parts of one page script, not mirrors


def _digest(p):
    return hashlib.md5(p.read_bytes()).hexdigest()


def test_mirrored_files_are_identical():
    by_name = {}
    for p in ROOT.rglob("*"):
        if not p.is_file() or (set(p.relative_to(ROOT).parts) & EXCLUDE_DIRS):
            continue
        if p.suffix not in {".py", ".css", ".js", ".png", ".webp"} or p.name.startswith("test_") or p.name == "__init__.py":
            continue
        by_name.setdefault(p.name, []).append(p)
    drift = [[str(x.relative_to(ROOT)) for x in paths] for paths in by_name.values()
             if len(paths) > 1 and len({_digest(x) for x in paths}) > 1]
    assert not drift, f"mirrored copies differ: {drift}"
