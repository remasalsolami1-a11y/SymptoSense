#!/usr/bin/env python3
"""Mobile screen-by-screen audit (V257).

Starts the app on a temp database, seeds one signed-in user with data, then opens each key screen at
360x740 and 390x844 in real Chromium and reports, per screen:
  * horizontal overflow (page wider than the viewport)  -> FAIL
  * JS page errors                                      -> FAIL
  * visible tap targets smaller than 40x40 CSS px        -> WARN (count + first examples)
  * clipped/hidden primary text (elements wider than viewport) -> part of overflow
Screenshots go to --out. Usage: python tools/mobile_audit.py --out DIR  (CHROMIUM_PATH optional)
"""
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

from playwright.sync_api import Error as PwError, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
EMAIL, PASSWORD = "mobile-audit@example.test", "TestPassword123!"
SCREENS = [("home", "/ar/home"), ("chat", "/ar/chat"), ("blood", "/ar/blood"), ("search", "/ar/search"), ("meds", "/ar/meds"),
           ("emergency", "/ar/emergency"), ("health_file", "/ar/health-file"), ("doctor_page", "/ar/health-file?view=doctor"),
           ("vitals", "/ar/vitals"), ("assistant", "/ar/home?assistant=general")]
SIZES = [(360, 740), (390, 844)]
# --sizes all: small phone, phones, large phone, phone landscape, tablets, laptop, desktop, full HD.
ALL_SIZES = [(320, 568), (360, 740), (390, 844), (414, 896), (844, 390), (768, 1024), (1024, 768), (1280, 800), (1440, 900), (1920, 1080)]
SEED = r"""
import sys; sys.path.insert(0, %r)
import db
from datetime import datetime, timedelta, timezone
db.init_db()
uid, err = db.create_ss_user(%r, "Audit", %r)
conn = db._conn(); conn.execute("UPDATE ss_users SET email_verified=1 WHERE id=?", (uid,)); conn.commit(); conn.close()
owner = "account-%%s" %% uid
for s in (2, 3, 4):
    db.save_record(owner, "ar", 34, "female", ["صداع", "دوخة"], "يومين", s, "medium")
db.save_vital(owner, 0, "bp", 150, 95); db.save_vital(owner, 0, "spo2", 93); db.save_vital(owner, 0, "glucose", 99, None, "fasting")
db.save_med_plan(owner, 0, "mounjaro", ["08:00"], dose="2.5", start_date=(datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat())
db.save_blood_test(owner, {"report_meta": {"sample_date": "2026-01-01"}, "indicators": [{"key": "hgb", "name_ar": "هيموغلوبين", "name_en": "Hemoglobin", "value": 11.1, "unit": "g/dL", "status": "low"}]})
db.save_blood_test(owner, {"report_meta": {"sample_date": "2026-03-01"}, "indicators": [{"key": "hgb", "name_ar": "هيموغلوبين", "name_en": "Hemoglobin", "value": 12.3, "unit": "g/dL", "status": "low"}]})
"""
JS = """() => {
  const vw = window.innerWidth, over = document.documentElement.scrollWidth - vw;
  const small = [];
  document.querySelectorAll('a,button,input,select,summary,[role=button]').forEach(e => {
    const r = e.getBoundingClientRect(), cs = getComputedStyle(e);
    if (!r.width || !r.height || cs.visibility === 'hidden' || cs.display === 'none' || e.disabled || e.type === 'hidden') return;
    if (r.bottom <= 0 || r.right <= 0 || r.left >= vw) return;  // off-screen (e.g. the hidden offline banner)
    if (e.tagName === 'INPUT' && (e.type === 'checkbox' || e.type === 'radio')) return;
    if (e.tagName === 'A' && e.parentElement && e.parentElement.innerText.length > e.innerText.length + 12) return;  // inline link inside a sentence (WCAG 2.5.8 exception)
    if (r.width < 40 || r.height < 40) small.push((e.tagName + '.' + (e.className || '')).slice(0, 40) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height) + ' "' + (e.innerText || e.getAttribute('aria-label') || '').trim().slice(0, 18) + '"');
  });
  const outside = [], tiny = new Set();
  document.querySelectorAll('body *').forEach(e => {
    const r = e.getBoundingClientRect(), cs = getComputedStyle(e);
    if (!r.width || !r.height || cs.visibility === 'hidden' || cs.display === 'none' || cs.position === 'fixed' && r.bottom < 0) return;
    let p = e.parentElement, scroller = false;
    while (p) { const o = getComputedStyle(p).overflowX; if ((o === 'auto' || o === 'scroll' || o === 'hidden') && p.scrollWidth > p.clientWidth + 1) { scroller = true; break; } p = p.parentElement; }
    const hasText = Array.from(e.childNodes).some(n => n.nodeType === 3 && n.textContent.trim());
    if (!scroller && hasText && (r.right > vw + 1 || r.left < -1)) outside.push((e.tagName + '.' + (e.className || '')).slice(0, 30) + ' "' + e.innerText.trim().slice(0, 20) + '" ' + Math.round(r.left) + '..' + Math.round(r.right));
    if (hasText && parseFloat(cs.fontSize) < 12 && e.innerText.trim().length > 2) tiny.add(parseFloat(cs.fontSize) + 'px "' + e.innerText.trim().slice(0, 20) + '"');
  });
  return {over: over, small: small, outside: outside.slice(0, 5), tiny: Array.from(tiny).slice(0, 4)};
}"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="mobile_audit_out")
    ap.add_argument("--sizes", default="phone", choices=("phone", "all"))
    ap.add_argument("--lang", default="ar", choices=("ar", "en"))
    a = ap.parse_args()
    sizes = ALL_SIZES if a.sizes == "all" else SIZES
    screens = [(n, p.replace("/ar/", "/%s/" % a.lang)) for n, p in SCREENS]
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
    tmp = tempfile.TemporaryDirectory()
    env = dict(os.environ, DB_PATH=str(Path(tmp.name) / "audit.db"), WEB_SECRET="audit-secret-that-is-longer-than-32-characters",
               SESSION_COOKIE_SECURE="0", SITE_URL=f"http://localhost:{port}", SYMPTOSENSE_DISABLE_BACKUP_SCHEDULER="1")
    env.pop("DATABASE_URL", None)
    subprocess.run([sys.executable, "-c", SEED % (str(ROOT), EMAIL, PASSWORD)], env=env, cwd=ROOT, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    code = f"import sys;sys.path.insert(0,{str(ROOT)!r});import webapp;from waitress import serve;serve(webapp.app,host='127.0.0.1',port={port},threads=8)"
    server = subprocess.Popen([sys.executable, "-c", code], env=env, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    fails, warns = [], []
    try:
        for _ in range(60):
            try:
                if urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/health", headers={"Host": f"localhost:{port}"}), timeout=1).status == 200:
                    break
            except OSError:
                time.sleep(1)
        base = f"http://localhost:{port}"
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None)
            for w, h in sizes:
                touch = w <= 900
                ctx = browser.new_context(viewport={"width": w, "height": h}, is_mobile=touch, has_touch=touch)
                page = ctx.new_page()
                errs = []
                page.on("pageerror", lambda e: errs.append(str(e)[:200]))
                page.route("**/*", lambda r: r.abort() if any(x in r.request.url for x in ("googleapis", "gstatic", "google-analytics")) else r.continue_())
                page.goto(f"{base}/{a.lang}/login", wait_until="networkidle")
                page.fill("input[name=email]", EMAIL); page.fill("input[name=password]", PASSWORD)
                page.locator("form button[type=submit]").first.click(); page.wait_for_load_state("networkidle")
                page.goto(f"{base}/{a.lang}/consent", wait_until="networkidle")
                if page.locator("input[name=service_usage]").count():
                    page.locator("input[name=service_usage]").evaluate("e=>e.click()")
                    page.locator("form button").last.click(); page.wait_for_load_state("networkidle")
                for name, path in screens:
                    errs.clear()
                    try:
                        page.goto(base + path, wait_until="load")
                    except PwError as exc:  # a client-side redirect can abort the first navigation
                        if "ERR_ABORTED" not in str(exc):
                            raise
                    page.wait_for_load_state("networkidle"); page.wait_for_timeout(900)
                    res = None
                    for _ in range(4):
                        try:
                            res = page.evaluate(JS)
                            break
                        except PwError as exc:  # page navigated again (redirect); wait and retry
                            if "context was destroyed" not in str(exc):
                                raise
                            page.wait_for_load_state("networkidle"); page.wait_for_timeout(800)
                    if res is None:
                        fails.append(f"{name}@{w}x{h}: page kept navigating")
                        continue
                    landed = page.url.replace(base, "")
                    if landed.split("?")[0] != path.split("?")[0]:
                        warns.append(f"{name}@{w}x{h}: landed on {landed} (requested {path})")
                    page.screenshot(path=str(out / f"{name}_{a.lang}_{w}x{h}.png"), full_page=True)
                    tag = f"{name}@{w}x{h}"
                    if res["over"] > 1:
                        fails.append(f"{tag}: horizontal overflow {res['over']}px")
                    for e in errs:
                        fails.append(f"{tag}: JS error {e}")
                    if res.get("outside"):
                        fails.append(f"{tag}: text outside viewport, e.g. {res['outside'][:3]}")
                    if res.get("tiny"):
                        warns.append(f"{tag}: text under 12px, e.g. {res['tiny'][:3]}")
                    if res["small"]:
                        warns.append(f"{tag}: {len(res['small'])} small tap targets, e.g. {res['small'][:3]}")
                ctx.close()
            browser.close()
    finally:
        server.terminate()
    for x in warns:
        print("WARN", x)
    for x in fails:
        print("FAIL", x)
    print("RESULT:", "FAIL" if fails else "PASS", f"({len(fails)} failures, {len(warns)} warnings)")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
