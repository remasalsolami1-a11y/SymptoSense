#!/usr/bin/env python3
"""Print / save-as-PDF audit: in print media the page chrome (nav, footer, buttons, bottom bar) must be hidden and the
one-page doctor summary must produce a PDF. Usage: python tools/print_audit.py [--out DIR]  (CHROMIUM_PATH optional)"""
from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from profile_ui_audit import SEED  # noqa: E402

PAGES = ("health-file?view=doctor", "health-file", "profile", "vitals")


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="print_out"); a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
    tmp = tempfile.TemporaryDirectory()
    env = dict(os.environ, DB_PATH=str(Path(tmp.name) / "a.db"), WEB_SECRET="print-audit-secret-that-is-longer-than-32-chars", SESSION_COOKIE_SECURE="0",
               SITE_URL=f"http://localhost:{port}", SYMPTOSENSE_DISABLE_BACKUP_SCHEDULER="1")
    env.pop("DATABASE_URL", None)
    cookie = subprocess.run([sys.executable, "-c", SEED % str(ROOT)], env=env, cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip().splitlines()[-1].split()[0]
    code = f"import sys;sys.path.insert(0,{str(ROOT)!r});import webapp;from waitress import serve;serve(webapp.app,host='127.0.0.1',port={port})"
    server = subprocess.Popen([sys.executable, "-c", code], env=env, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://localhost:{port}"; fails: list[str] = []
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/health", headers={"Host": f"localhost:{port}"}), timeout=1); break
            except OSError:
                time.sleep(1)
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None)
            for lang in ("ar", "en"):
                for path in PAGES:
                    ctx = browser.new_context()
                    ctx.add_cookies([{"name": "symptosense_session", "value": cookie, "url": base}, {"name": "lang", "value": lang, "url": base}])
                    pg = ctx.new_page(); pg.goto(f"{base}/{lang}/{path}", wait_until="networkidle"); pg.emulate_media(media="print")
                    vis = pg.evaluate("() => ['nav','.footer','.ss-bnav','.ss-mobile-head','button','.btn'].map(s => [s, Array.from(document.querySelectorAll(s)).filter(e => getComputedStyle(e).display !== 'none').length])")
                    for sel, n in vis:
                        if n: fails.append(f"{lang}/{path}: {n} visible '{sel}' in print")
                    pdf = out / f"{lang}_{path.replace('/', '_').replace('?', '_').replace('=', '_')}.pdf"
                    pg.pdf(path=str(pdf), format="A4")
                    if pdf.stat().st_size < 5000: fails.append(f"{lang}/{path}: PDF suspiciously small")
                    ctx.close()
            browser.close()
    finally:
        server.terminate()
    for f in fails:
        print("FAIL", f)
    print("PRINT AUDIT:", "FAILED" if fails else "PASS")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
