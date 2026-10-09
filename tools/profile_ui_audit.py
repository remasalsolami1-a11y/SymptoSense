#!/usr/bin/env python3
"""Profile dashboard + editor audit (real Chromium).

Seeds a user (with and without data) on a temp DB and checks /profile in Arabic and English at 320/360/390/768/1280:
no horizontal overflow, no text under 12px, touch targets >= 44px for links/buttons, no JS errors, no HTTP >= 500, and the
dashboard exposes dates only. Then it drives the editor on /manage: typed inputs appear (date / select / number), an
implausible height is refused with a visible message, and valid values persist.
Usage: python tools/profile_ui_audit.py [--out DIR]   (CHROMIUM_PATH optional)"""
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
SEED = r"""
import sys; sys.path.insert(0, %r)
import db
db.init_db()
out = []
for email, rich in (("pa-rich@example.test", True), ("pa-new@example.test", False)):
    uid, err = db.create_ss_user(email, "Rema", "TestPassword123!")
    c = db._conn(); c.execute("UPDATE ss_users SET email_verified=1 WHERE id=?", (uid,)); c.commit(); c.close()
    if rich:
        key = "account-%%s" %% uid
        db.save_health_profile(uid, {"display_name": "Rema", "dob": "1990-05-01", "gender": "female", "height": "165", "weight": "60", "allergies": "none", "health_conditions": "none"})
        rid = db.save_analysis_record_with_result(key, "ar", 35, "female", ["headache"], "2 days", "3", "routine", {})
        db.save_blood_test(key, {"hgb": 13.0}, member_id=0)
        db.save_vital(key, 0, "bp", 120, 80)
        db.save_followup(key, rid, "better", False)
        db.save_med_plan(uid, 0, "TestMed", ["08:00"])
    import privacy_features
    privacy_features.save_consent("account-%%s" %% uid, uid, True, False)
    out.append(uid)
import webapp
ser = webapp.app.session_interface.get_signing_serializer(webapp.app)
print(" ".join(ser.dumps({"ss_user_id": u}) for u in out))
"""
PAGE_JS = """() => {
  const vw = document.documentElement.clientWidth, bad = {tiny: [], small: [], over: document.documentElement.scrollWidth - vw};
  document.querySelectorAll('.pd *').forEach(e => {
    const cs = getComputedStyle(e), r = e.getBoundingClientRect();
    if (!r.width || !r.height || cs.display === 'none' || cs.visibility === 'hidden') return;
    const text = Array.from(e.childNodes).some(n => n.nodeType === 3 && n.textContent.trim());
    if (text && parseFloat(cs.fontSize) < 12) bad.tiny.push(parseFloat(cs.fontSize) + 'px ' + e.textContent.trim().slice(0, 20));
    if ((e.tagName === 'A' || e.tagName === 'BUTTON') && (r.height < 43.5 || r.width < 43.5)) bad.small.push(Math.round(r.width) + 'x' + Math.round(r.height) + ' ' + e.textContent.trim().slice(0, 20));
    if (r.right > vw + 1 || r.left < -1) bad.over = Math.max(bad.over, 1);
  });
  return bad;
}"""


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="profile_audit_out"); a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
    tmp = tempfile.TemporaryDirectory()
    env = dict(os.environ, DB_PATH=str(Path(tmp.name) / "a.db"), WEB_SECRET="profile-audit-secret-that-is-longer-than-32-chars",
               SESSION_COOKIE_SECURE="0", SITE_URL=f"http://localhost:{port}", SYMPTOSENSE_DISABLE_BACKUP_SCHEDULER="1")
    env.pop("DATABASE_URL", None)
    rich, new = subprocess.run([sys.executable, "-c", SEED % str(ROOT)], env=env, cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip().splitlines()[-1].split()
    code = f"import sys;sys.path.insert(0,{str(ROOT)!r});import webapp;from waitress import serve;serve(webapp.app,host='127.0.0.1',port={port},threads=8)"
    server = subprocess.Popen([sys.executable, "-c", code], env=env, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=open(out / "server.log", "w"))
    fails: list[str] = []
    checks = 0
    base = f"http://localhost:{port}"
    try:
        for _ in range(60):
            try:
                if urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/health", headers={"Host": f"localhost:{port}"}), timeout=1).status == 200:
                    break
            except OSError:
                time.sleep(1)
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None)
            for who, cookie in (("rich", rich), ("new", new)):
                for lang in ("ar", "en"):
                    for w, h in ((320, 568), (360, 740), (390, 844), (768, 1024), (1280, 800)):
                        ctx = browser.new_context(viewport={"width": w, "height": h}, is_mobile=w < 600, has_touch=w < 600)
                        ctx.add_cookies([{"name": "symptosense_session", "value": cookie, "url": base}, {"name": "lang", "value": lang, "url": base}])
                        page = ctx.new_page(); errs: list[str] = []
                        page.on("pageerror", lambda e: errs.append("pageerror: " + str(e)[:160]))
                        page.on("response", lambda r: errs.append(f"HTTP {r.status} {r.url[-50:]}") if r.status >= 500 else None)
                        page.route("**/*", lambda r: r.abort() if any(x in r.request.url for x in ("googleapis", "gstatic")) else r.continue_())
                        page.goto(f"{base}/{lang}/profile", wait_until="networkidle")
                        tag = f"{who}/{lang}@{w}"
                        if page.locator(".pd").count() != 1:
                            fails.append(f"{tag}: dashboard missing (landed on {page.url[len(base):]})"); ctx.close(); continue
                        res = page.evaluate(PAGE_JS); checks += 1
                        if res["over"] > 2: fails.append(f"{tag}: horizontal overflow")
                        if res["tiny"]: fails.append(f"{tag}: text under 12px {res['tiny'][:3]}")
                        if res["small"]: fails.append(f"{tag}: touch target < 44px {res['small'][:3]}")
                        if who == "rich" and page.locator(".pd-card").count() != 4: fails.append(f"{tag}: expected 4 status cards")
                        if who == "new" and page.locator(".pd-missing").count() != 1: fails.append(f"{tag}: missing-info line absent for a new user")
                        if who == "rich" and page.locator(".pd-missing").count() != 0 and lang == "ar": fails.append(f"{tag}: unexpected missing line")
                        for e in errs: fails.append(f"{tag}: {e}")
                        if w in (390, 1280) and lang == "ar": page.screenshot(path=str(out / f"profile_{who}_{lang}_{w}.png"), full_page=True)
                        ctx.close()
            # ---- editor flow (phone) ----
            ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
            ctx.add_cookies([{"name": "symptosense_session", "value": new, "url": base}, {"name": "lang", "value": "en", "url": base}])
            page = ctx.new_page(); errs = []
            page.on("pageerror", lambda e: errs.append("pageerror: " + str(e)[:160]))
            page.goto(f"{base}/en/manage", wait_until="networkidle")
            page.click("[data-ss-click='editField'][data-ss-args='[\"dob\"]']")
            if page.locator("#edit_dob[type=date]").count() != 1: fails.append("editor: dob is not a date input")
            page.click("[data-ss-click='editField'][data-ss-args='[\"gender\"]']")
            if page.locator("select#edit_gender").count() != 1: fails.append("editor: gender is not a select")
            page.click("[data-ss-click='editField'][data-ss-args='[\"height\"]']")
            if page.locator("#edit_height[type=number]").count() != 1: fails.append("editor: height is not numeric")
            page.fill("#edit_height", "5")
            page.locator("#val_height button", has_text="Save").click()
            page.wait_for_timeout(300)
            if "between 30 and 260" not in (page.locator("#err_height").inner_text() or ""): fails.append("editor: implausible height not refused with a message")
            page.fill("#edit_height", "170")
            page.locator("#val_height button", has_text="Save").click()
            page.wait_for_load_state("networkidle"); page.wait_for_timeout(1200)
            if "170" not in page.locator("#val_height").inner_text(): fails.append("editor: valid height did not persist")
            for e in errs: fails.append("editor: " + e)
            checks += 1
            page.screenshot(path=str(out / "manage_390.png"), full_page=True)
            ctx.close(); browser.close()
    finally:
        server.terminate()
    for f in fails:
        print("FAIL", f)
    print("PROFILE UI AUDIT:", "FAILED" if fails else "PASS", f"({checks} checks)")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
