"""Behavioural browser test for the emergency stop overlay (tools/e2e_emergency_stop.py).

Skipped automatically when Playwright/Chromium is unavailable (CI's browser-e2e
job runs the same tool unconditionally, so a skip here cannot hide a failure there).
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
            b = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None)
            b.close()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _chromium_ok(), reason="Chromium not available")
def test_emergency_overlay_is_a_hard_stop():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    tmp = tempfile.TemporaryDirectory()
    env = dict(os.environ, DB_PATH=str(Path(tmp.name) / "e2e.db"), WEB_SECRET="e2e-secret-that-is-longer-than-32-characters",
               SESSION_COOKIE_SECURE="0", SITE_URL=f"http://localhost:{port}", SYMPTOSENSE_DISABLE_BACKUP_SCHEDULER="1")
    env.pop("DATABASE_URL", None)
    code = f"import sys;sys.path.insert(0,{str(ROOT)!r});import webapp;from waitress import serve;serve(webapp.app,host='127.0.0.1',port={port},threads=8)"
    server = subprocess.Popen([sys.executable, "-c", code], env=env, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
        sys.path.insert(0, str(ROOT / "tools"))
        import e2e_emergency_stop
        problems = e2e_emergency_stop.run(f"http://localhost:{port}")
        assert not problems, problems
    finally:
        server.terminate()
        server.wait(timeout=10)
        tmp.cleanup()
