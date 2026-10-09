"""Usage: python tools/bump_version.py 260.0.0  - rewrites VERSION and the static copies that cannot import it."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# NOTE: the shared stylesheet is served "immutable" for a year, so its URL version MUST change whenever the CSS does.
def main(new):
    if not re.fullmatch(r"\d+\.\d+\.\d+", new):
        raise SystemExit("version must look like 260.0.0")
    major = new.split(".")[0]
    old = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    old_major = old.split(".")[0]
    (ROOT / "VERSION").write_text(new + "\n", encoding="utf-8")
    edits = {
        "service-worker.js": [("symptosense-shell-v" + old_major, "symptosense-shell-v" + major), ("app-shell-v112.css?v=" + old_major, "app-shell-v112.css?v=" + major)],
        "inline_assets/PAGE_FRAME.html": [("app-shell-v112.css?v=" + old_major, "app-shell-v112.css?v=" + major)],
        "webapp.py": [("symptosense-app-shell-v112-v" + old_major, "symptosense-app-shell-v112-v" + major)],
        ".env.example": [("APP_VERSION=" + old, "APP_VERSION=" + new), ("SymptoSense-v" + old_major, "SymptoSense-v" + major)],
        "Dockerfile": [("build profile: V" + old_major, "build profile: V" + major), ("SymptoSense V" + old_major + " production", "SymptoSense V" + major + " production")],
        "release_metrics.json": [('"delivery_revision": "V' + old_major + '"', '"delivery_revision": "V' + major + '"')],
    }
    for name, pairs in edits.items():
        p = ROOT / name
        text = p.read_text(encoding="utf-8")
        for a, b in pairs:
            if a not in text:
                raise SystemExit("%s: expected %r" % (name, a))
            text = text.replace(a, b)
        p.write_text(text, encoding="utf-8")
    # tests that pin the stylesheet URL version follow the bump (otherwise every bump breaks them by hand)
    for tp in sorted(ROOT.glob("test_*.py")):
        t = tp.read_text(encoding="utf-8")
        t2 = t.replace("app-shell-v112.css?v=" + old_major, "app-shell-v112.css?v=" + major).replace("symptosense-app-shell-v112-v" + old_major, "symptosense-app-shell-v112-v" + major)
        if t2 != t:
            tp.write_text(t2, encoding="utf-8")
    print("bumped", old, "->", new)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")
