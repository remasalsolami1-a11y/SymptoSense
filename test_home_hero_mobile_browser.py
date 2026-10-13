"""Real-browser regression: the home hero must not collapse on phones (English and Arabic).

Found in the V68 final audit: `html[dir="ltr"] ... .ss-hero-demo{grid-column:2!important}` had no media query, so on the
English home page at 390px the hero columns became 0px / 26px wide (call-to-action buttons 26px wide, page 13,000px tall).
"""
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
playwright = pytest.importorskip("playwright.sync_api")


def _chromium_ok():
    try:
        with playwright.sync_playwright() as p:
            p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None).close()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _chromium_ok(), reason="Chromium not available (set CHROMIUM_PATH)")
def test_home_hero_keeps_usable_buttons_at_every_phone_width_in_both_languages():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
    tmp = tempfile.TemporaryDirectory()
    env = dict(os.environ, DB_PATH=str(Path(tmp.name) / "hero.db"), WEB_SECRET="hero-secret-that-is-longer-than-32-characters",
               SESSION_COOKIE_SECURE="0", SITE_URL=f"http://localhost:{port}", SYMPTOSENSE_DISABLE_BACKUP_SCHEDULER="1")
    env.pop("DATABASE_URL", None)
    code = f"import sys;sys.path.insert(0,{str(ROOT)!r});import webapp;from waitress import serve;serve(webapp.app,host='127.0.0.1',port={port},threads=4)"
    server = subprocess.Popen([sys.executable, "-c", code], env=env, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    problems = []
    try:
        for _ in range(60):
            try:
                req = urllib.request.Request(f"http://127.0.0.1:{port}/health", headers={"Host": f"localhost:{port}"})
                if urllib.request.urlopen(req, timeout=1).status == 200:
                    break
            except Exception:
                time.sleep(1)
        else:
            pytest.fail("server did not start")
        with playwright.sync_playwright() as p:
            b = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None)
            for lang in ("en", "ar"):
                for width in (320, 360, 390, 430, 600):
                    pg = b.new_page(viewport={"width": width, "height": 800})
                    pg.goto(f"http://localhost:{port}/{lang}/", wait_until="load"); pg.wait_for_timeout(500)
                    m = pg.evaluate("""() => { const r = s => { const e = document.querySelector(s); return e ? e.getBoundingClientRect() : null; };
                        const a = r('.ss-hero-primary'), c = r('.ss-hero-secondary');
                        return {cta: a && [a.width, a.height], second: c && [c.width, c.height],
                                over: document.documentElement.scrollWidth - window.innerWidth, h: document.documentElement.scrollHeight}; }""")
                    pg.close()
                    tag = f"{lang}@{width}"
                    if not m["cta"] or m["cta"][0] < 0.6 * width or m["cta"][1] > 90:
                        problems.append((tag, "primary button collapsed", m["cta"]))
                    if not m["second"] or m["second"][0] < 0.6 * width:
                        problems.append((tag, "secondary button collapsed", m["second"]))
                    if m["over"] > 1:
                        problems.append((tag, "horizontal overflow", m["over"]))
                    if m["h"] > 9000:
                        problems.append((tag, "page absurdly tall", m["h"]))
            b.close()
    finally:
        server.terminate(); server.wait(timeout=10); tmp.cleanup()
    assert not problems, problems
