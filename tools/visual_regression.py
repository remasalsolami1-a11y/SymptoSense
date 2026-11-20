"""Visual regression check for CSS refactors (V283).

The stylesheets carry hundreds of `!important` overrides layered across releases,
so removing or merging a rule can move something on one page at one width without
any test noticing. Use this before and after every CSS clean-up step:

    python tools/visual_regression.py capture --base http://127.0.0.1:5000 --out shots/before
    # ... change CSS, restart the server ...
    python tools/visual_regression.py capture --base http://127.0.0.1:5000 --out shots/after
    python tools/visual_regression.py compare shots/before shots/after --report shots/diff

`compare` exits 1 when any page/width/language differs by more than --threshold
changed pixels and writes a red-highlighted diff image for each one. Animations are
frozen and the page settled before capture so identical CSS gives identical pixels.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PAGES = ["/", "/chat", "/blood", "/meds", "/search", "/calculators", "/firstaid", "/emergency", "/tips",
         "/relax", "/health-library", "/health-library/disease/appendicitis",
         "/health-library/guide/diabetes-and-ramadan-fasting", "/how-we-work", "/about", "/privacy", "/terms",
         "/contact", "/login"]
WIDTHS = [360, 390, 768, 1024, 1280, 1440]
LANGS = ["ar", "en"]

_FREEZE = """*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}
.asst-fab,#pwaInstall,.ss-offline-banner{visibility:hidden!important}"""


def _name(lang, path, width):
    slug = path.strip("/").replace("/", "_") or "home"
    return f"{lang}__{slug}__{width}.png"


def capture(base, out, pages, widths, langs):
    from playwright.sync_api import sync_playwright

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    meta = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width in widths:
            ctx = browser.new_context(viewport={"width": width, "height": 900}, device_scale_factor=1, reduced_motion="reduce",
                                  bypass_csp=True)  # test-only: lets the animation-freeze style in; the site CSP is unchanged
            page = ctx.new_page()
            for lang in langs:
                for path in pages:
                    url = base.rstrip("/") + f"/{lang}" + (path if path != "/" else "/")
                    resp = page.goto(url, wait_until="networkidle")
                    page.add_style_tag(content=_FREEZE)
                    page.evaluate("document.fonts && document.fonts.ready")
                    page.wait_for_timeout(250)
                    name = _name(lang, path, width)
                    page.screenshot(path=str(out / name), full_page=True)
                    meta[name] = {"url": url, "status": resp.status if resp else None}
            ctx.close()
        browser.close()
    (out / "capture.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"captured {len(meta)} screenshots into {out}")


def compare(before, after, report, threshold):
    from PIL import Image, ImageChops

    before, after = Path(before), Path(after)
    report = Path(report) if report else None
    if report:
        report.mkdir(parents=True, exist_ok=True)
    changed, missing = [], []
    for a in sorted(before.glob("*.png")):
        b = after / a.name
        if not b.exists():
            missing.append(a.name)
            continue
        ia, ib = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
        if ia.size != ib.size:
            changed.append((a.name, f"size {ia.size} -> {ib.size}"))
            continue
        diff = ImageChops.difference(ia, ib).convert("L").point(lambda v: 255 if v > 40 else 0)
        n = diff.histogram()[255]  # pixels marked as changed
        if n > threshold:
            changed.append((a.name, f"{n} px changed, box {diff.getbbox()}"))
            if report:
                overlay = ib.copy()
                overlay.paste((230, 30, 30), mask=diff)
                overlay.save(report / a.name)
    for name, why in changed:
        print(f"CHANGED  {name}: {why}")
    for name in missing:
        print(f"MISSING  {name}")
    total = len(list(before.glob("*.png")))
    print(f"{total - len(changed) - len(missing)}/{total} identical (threshold {threshold} px)")
    return 1 if changed or missing else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Screenshot-diff guard for CSS changes")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("capture")
    c.add_argument("--base", required=True, help="running site, e.g. http://127.0.0.1:5000")
    c.add_argument("--out", required=True)
    c.add_argument("--pages", nargs="*", default=PAGES)
    c.add_argument("--widths", nargs="*", type=int, default=WIDTHS)
    c.add_argument("--langs", nargs="*", default=LANGS)
    d = sub.add_parser("compare")
    d.add_argument("before")
    d.add_argument("after")
    d.add_argument("--report", help="folder for highlighted diff images")
    d.add_argument("--threshold", type=int, default=0, help="changed pixels tolerated per screenshot")
    a = ap.parse_args(argv)
    if a.cmd == "capture":
        capture(a.base, a.out, a.pages, a.widths, a.langs)
        return 0
    return compare(a.before, a.after, a.report, a.threshold)


if __name__ == "__main__":
    sys.exit(main())
