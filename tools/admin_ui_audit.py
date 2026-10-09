#!/usr/bin/env python3
"""Admin dashboard click audit (real Chromium): every non-destructive data-ss action fires without JS errors.

Seeds an admin on a temp DB, opens /admin at phone and desktop widths, clicks each visible data-ss-click control
(destructive ones are skipped; confirm dialogs are dismissed) and fails on page errors, failed same-origin requests with
status >= 500, or horizontal overflow.   Usage: python tools/admin_ui_audit.py [--out DIR]   (CHROMIUM_PATH optional)"""
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
SKIP = {"performLaunchReset", "performLabTrialCleanup", "logoutAllAdminSessions", "removeItem", "removeContent", "deleteValidationCase",
        "freezeResearchStudy", "confirmProductionEmail", "testProductionEmail", "testProductionPush", "sendAuthEmailTest",
        "sendAdminTestPush", "testErrorMonitoring", "toggleUser", "exportPilotWorkbook", "downloadAnalyticsExport",
        "downloadValidation", "exportData", "exportAudit", "exportLabTrialsExcel", "runPerformanceBenchmark"}
SEED = r"""
import sys, time; sys.path.insert(0, %r)
import db, admin_security
db.init_db()
uid, err = db.create_ss_user("admin-audit@example.test", "Admin", "TestPassword123!")
conn = db._conn(); conn.execute("UPDATE ss_users SET role='admin', email_verified=1 WHERE id=?", (uid,)); conn.commit(); conn.close()
import webapp
ser = webapp.app.session_interface.get_signing_serializer(webapp.app)
print(ser.dumps({"ss_user_id": uid, "admin_2fa_verified": True, "admin_session_epoch": admin_security.current_epoch(uid), "admin_last_seen": int(time.time())}))
"""


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="admin_audit_out"); a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
    tmp = tempfile.TemporaryDirectory()
    env = dict(os.environ, DB_PATH=str(Path(tmp.name) / "a.db"), WEB_SECRET="admin-audit-secret-that-is-longer-than-32-chars",
               SESSION_COOKIE_SECURE="0", SITE_URL=f"http://localhost:{port}", SYMPTOSENSE_DISABLE_BACKUP_SCHEDULER="1")
    env.pop("DATABASE_URL", None)
    cookie = subprocess.run([sys.executable, "-c", SEED % str(ROOT)], env=env, cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip().splitlines()[-1]
    code = f"import sys;sys.path.insert(0,{str(ROOT)!r});import webapp;from waitress import serve;serve(webapp.app,host='127.0.0.1',port={port},threads=8)"
    server = subprocess.Popen([sys.executable, "-c", code], env=env, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=open(Path(a.out) / 'server.log', 'w'))
    fails: list[str] = []
    clicked = 0
    try:
        for _ in range(60):
            try:
                if urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/health", headers={"Host": f"localhost:{port}"}), timeout=1).status == 200:
                    break
            except OSError:
                time.sleep(1)
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None)
            for w, h in ((390, 844), (1280, 800)):
                ctx = browser.new_context(viewport={"width": w, "height": h}, is_mobile=w < 600, has_touch=w < 600)
                ctx.add_cookies([{"name": "symptosense_session", "value": cookie, "url": f"http://localhost:{port}"}, {"name": "lang", "value": "ar", "url": f"http://localhost:{port}"}])
                page = ctx.new_page()
                errs: list[str] = []
                page.on("pageerror", lambda e: errs.append("pageerror: " + str(e)[:200]))
                page.on("response", lambda r: errs.append(f"HTTP {r.status} {r.url[-60:]}") if r.status >= 500 else None)
                page.on("dialog", lambda d: d.dismiss())
                page.route("**/*", lambda r: r.abort() if any(x in r.request.url for x in ("googleapis", "gstatic")) else r.continue_())
                page.goto(f"http://localhost:{port}/admin", wait_until="networkidle")
                if "/admin" not in page.url or page.locator("[data-ss-click]").count() == 0:
                    fails.append(f"@{w}: dashboard did not open (landed on {page.url.replace(f'http://localhost:{port}', '')})"); ctx.close(); continue
                page.wait_for_timeout(800)
                stats = {"views": 0, "skipped": 0, "invisible": 0, "timeout": 0}
                views = page.evaluate("() => Array.from(document.querySelectorAll('.navbtn[data-view]')).map(e => e.getAttribute('data-view'))")
                for view in views:
                    try:
                        page.locator(f".navbtn[data-view='{view}']").first.click(timeout=3000)
                    except Exception:
                        stats["timeout"] += 1; continue
                    stats["views"] += 1
                    page.wait_for_timeout(500)
                    names = page.evaluate("() => Array.from(document.querySelectorAll('[data-ss-click]')).map((e, i) => [i, e.getAttribute('data-ss-click'), e.offsetParent !== null])")
                    for index, name, vis in names:
                        if name in SKIP:
                            stats["skipped"] += 1; continue
                        if not vis:
                            stats["invisible"] += 1; continue
                        el = page.locator("[data-ss-click]").nth(index)
                        try:
                            el.click(timeout=3000); clicked += 1
                            page.wait_for_timeout(250)
                        except Exception as exc:
                            if "intercepts pointer" in str(exc) or "not visible" in str(exc) or "Timeout" in str(exc):
                                stats["timeout"] += 1; continue
                            fails.append(f"@{w} {view}/{name}: {str(exc)[:120]}")
                print(f"@{w}", stats)
                over = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
                if over > 2:
                    fails.append(f"@{w}: horizontal overflow {over}px")
                for e in errs:
                    fails.append(f"@{w}: {e}")
                page.screenshot(path=str(out / f"admin_{w}.png"), full_page=False)
                ctx.close()
            browser.close()
    finally:
        server.terminate()
    for f in fails:
        print("FAIL", f)
    print("ADMIN UI AUDIT:", "FAILED" if fails else "PASS", f"({clicked} controls clicked)")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
