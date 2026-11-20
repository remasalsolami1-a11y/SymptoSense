#!/usr/bin/env python3
"""Page weight + accessibility (axe-core) audit in real Chromium, on a temp DB.

For each main screen (ar/en, phone viewport) it records transferred bytes by type, request count, DOMContentLoaded/load
timings, and runs axe-core. Exit 1 on serious/critical axe violations or when a page exceeds the byte budgets below.
Usage: python tools/perf_a11y_audit.py [--out DIR] [--report]   (CHROMIUM_PATH optional)"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from profile_ui_audit import SEED  # noqa: E402

SCREENS = [("home", "home"), ("chat", "chat"), ("blood", "blood"), ("search", "search"), ("meds", "meds"), ("emergency", "emergency"),
           ("health_file", "health-file"), ("vitals", "vitals"), ("profile", "profile"), ("manage", "manage")]
# Budgets on the uncompressed bytes a first visit downloads (script+style); fonts/images are reported only.
BUDGET_JS_CSS = 900_000
BLOCKING = {"serious", "critical"}


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="perf_a11y_out"); ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
    tmp = tempfile.TemporaryDirectory()
    env = dict(os.environ, DB_PATH=str(Path(tmp.name) / "a.db"), WEB_SECRET="perf-audit-secret-that-is-longer-than-32-chars",
               SESSION_COOKIE_SECURE="0", SITE_URL=f"http://localhost:{port}", SYMPTOSENSE_DISABLE_BACKUP_SCHEDULER="1")
    env.pop("DATABASE_URL", None)
    cookie = subprocess.run([sys.executable, "-c", SEED % str(ROOT)], env=env, cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip().splitlines()[-1].split()[0]
    code = f"import sys;sys.path.insert(0,{str(ROOT)!r});import webapp;from waitress import serve;serve(webapp.app,host='127.0.0.1',port={port},threads=8)"
    server = subprocess.Popen([sys.executable, "-c", code], env=env, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=open(out / "server.log", "w"))
    base = f"http://localhost:{port}"
    rows, fails, axe_all = [], [], {}
    try:
        for _ in range(60):
            try:
                if urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/health", headers={"Host": f"localhost:{port}"}), timeout=1).status == 200:
                    break
            except OSError:
                time.sleep(1)
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None)
            for lang in ("ar", "en"):
                for name, path in SCREENS:
                    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
                    ctx.add_cookies([{"name": "symptosense_session", "value": cookie, "url": base}, {"name": "lang", "value": lang, "url": base}])
                    page = ctx.new_page(); sizes: dict[str, int] = {}; count = [0]

                    def on_resp(r, sizes=sizes, count=count):
                        try:
                            body = len(r.body())
                        except Exception:
                            return
                        kind = (r.headers.get("content-type", "") or "").split(";")[0].split("/")[-1] or "other"
                        kind = {"javascript": "js", "x-javascript": "js", "css": "css", "html": "html", "woff2": "font", "woff": "font"}.get(kind, "img" if kind in ("png", "jpeg", "webp", "svg+xml", "gif") else "other")
                        sizes[kind] = sizes.get(kind, 0) + body; count[0] += 1
                    page.on("response", on_resp)
                    page.route("**/*", lambda r: r.abort() if any(x in r.request.url for x in ("googleapis", "gstatic")) else r.continue_())
                    page.goto(f"{base}/{lang}/{path}", wait_until="networkidle")
                    nav = page.evaluate("() => { const n = performance.getEntriesByType('navigation')[0]; return n ? {dcl: Math.round(n.domContentLoadedEventEnd), load: Math.round(n.loadEventEnd)} : {} }")
                    tag = f"{lang}/{name}"
                    jscss = sizes.get("js", 0) + sizes.get("css", 0)
                    rows.append({"page": tag, "requests": count[0], "html": sizes.get("html", 0), "js": sizes.get("js", 0), "css": sizes.get("css", 0), "img": sizes.get("img", 0), "font": sizes.get("font", 0), **nav})
                    if jscss > BUDGET_JS_CSS:
                        fails.append(f"{tag}: js+css {jscss // 1024} KB over budget {BUDGET_JS_CSS // 1024} KB")
                    res = Axe().run(page).response
                    axe_all[tag] = [{"id": v["id"], "impact": v["impact"], "help": v["help"], "nodes": len(v["nodes"]), "targets": [n["target"] for n in v["nodes"][:3]], "data": [ (n.get("any") or [{}])[0].get("data") for n in v["nodes"][:30]] if v["id"] == "color-contrast" else []} for v in res["violations"]]
                    for v in axe_all[tag]:
                        if v["impact"] in BLOCKING:
                            fails.append(f"{tag}: axe {v['impact']} {v['id']} ({v['nodes']} nodes) {v['targets'][:2]}")
                    ctx.close()
            browser.close()
    finally:
        server.terminate()
    (out / "report.json").write_text(json.dumps({"pages": rows, "axe": axe_all}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{'page':16}{'req':>5}{'html':>8}{'js':>9}{'css':>9}{'img':>9}{'font':>9}{'dcl':>6}{'load':>6}")
    for r in rows:
        print(f"{r['page']:16}{r['requests']:>5}{r['html'] // 1024:>7}K{r['js'] // 1024:>8}K{r['css'] // 1024:>8}K{r['img'] // 1024:>8}K{r['font'] // 1024:>8}K{r.get('dcl', 0):>6}{r.get('load', 0):>6}")
    agg: dict[tuple, int] = {}
    for tag, vs in axe_all.items():
        for v in vs:
            agg[(v["impact"], v["id"])] = agg.get((v["impact"], v["id"]), 0) + v["nodes"]
    for (imp, vid), n in sorted(agg.items(), key=lambda kv: (kv[0][0] != "critical", kv[0][0] != "serious", -kv[1])):
        print(f"axe {imp:9} {vid:36} nodes={n}")
    for f in fails:
        print("FAIL", f)
    print("PERF/A11Y AUDIT:", "FAILED" if fails else "PASS")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
