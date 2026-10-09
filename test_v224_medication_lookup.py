import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_contrave_brand_generic_and_arabic_aliases_work_in_fresh_database(tmp_path):
    code = r'''
import medication_warnings as m
queries = [
    "Contrave", "contrave", "كونتراف", "كونتريف",
    "naltrexone bupropion", "bupropion/naltrexone",
    "naltrexone-bupropion", "نالتريكسون/بوبروبيون",
]
for q in queries:
    r = m.lookup_drug(q)
    assert r is not None, q
    assert r["slug"] == "contrave", (q, r.get("slug"))
    assert r["source_policy"]["ok"] is True
    assert r["source_policy"]["has_local"] is True
    assert r["source_policy"]["clinical_provider_count"] >= 2
assert m.lookup_drug("not-a-real-medicine") is None
'''
    env = os.environ.copy()
    env.pop("DATABASE_URL", None)
    env["DB_PATH"] = str(tmp_path / "v224-meds.db")
    cp = subprocess.run(
        [sys.executable, "-c", code], cwd=str(ROOT), env=env,
        capture_output=True, text=True, timeout=60,
    )
    assert cp.returncode == 0, cp.stdout + "\n" + cp.stderr


def test_medication_normalization_handles_common_name_separators():
    sys.path.insert(0, str(ROOT))
    import medication_warnings as m
    assert m._norm("Naltrexone/Bupropion") == "naltrexone bupropion"
    assert m._norm("Naltrexone-Bupropion") == "naltrexone bupropion"
    assert m._norm("Bupropion — Naltrexone") == "bupropion naltrexone"
