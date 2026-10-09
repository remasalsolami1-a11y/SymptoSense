"""The clinician packet is generated from the code; this fails when the committed copy is stale."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_packet_in_sync_with_code():
    r = subprocess.run([sys.executable, "-I", str(ROOT / "tools/clinical_packet.py"), "--check"], capture_output=True, text=True, cwd=str(ROOT), timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr


def test_packet_lists_every_area_and_has_decision_columns():
    import clinical_signoff as cs
    text = (ROOT / "CLINICAL_REVIEW_PACKET_AR.md").read_text(encoding="utf-8")
    areas = cs.load(cs.PATH)["areas"]
    for k in areas:
        assert k in text
    for csvf in (ROOT / "clinical_review").glob("*.csv"):
        assert "clinician notes" in csvf.read_text(encoding="utf-8").splitlines()[0]


def test_readiness_check_reports_missing_without_leaking_values(monkeypatch):
    sys.path.insert(0, str(ROOT / "tools"))
    import prod_readiness_check as p
    monkeypatch.setenv("WEB_SECRET", "super-secret-value")
    monkeypatch.delenv("SYMPTOSENSE_ADMIN_EMAIL", raising=False)
    rows = {n: ok for n, ok, _ in p.checks()}
    assert rows["WEB_SECRET"] is True and rows["SYMPTOSENSE_ADMIN_EMAIL"] is False
    assert "super-secret-value" not in repr(p.checks())


def test_backup_status_json_is_one_parseable_last_line():
    import json
    r = subprocess.run([sys.executable, str(ROOT / "backup_restore.py"), "status", "--json"], capture_output=True, text=True, cwd=str(ROOT), timeout=60)
    assert r.returncode == 0, r.stderr
    last = [ln for ln in r.stdout.splitlines() if ln.strip()][-1]
    data = json.loads(last)
    assert "ready" in data and "\n" not in last
