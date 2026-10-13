"""release_check must count the real test files (they live in the project root, not tests/)."""
import json
import shutil
from pathlib import Path

import release_check

ROOT = Path(__file__).resolve().parent


def test_count_matches_the_tree_and_the_metrics_file():
    counted = release_check.count_test_files()
    assert counted == len(list(ROOT.glob("test_*.py"))) > 100
    assert json.loads((ROOT / "release_metrics.json").read_text(encoding="utf-8"))["test_files"] == counted


def test_a_wrong_metric_is_reported(tmp_path, monkeypatch):
    (tmp_path / "runtime_data").mkdir()
    shutil.copy(ROOT / "runtime_data" / "safety_cases.json", tmp_path / "runtime_data" / "safety_cases.json")
    for name in ("v50_wow.py", "v51_innovation.py"):
        shutil.copy(ROOT / name, tmp_path / name)
    metrics = json.loads((ROOT / "release_metrics.json").read_text(encoding="utf-8"))
    for n in range(3):
        (tmp_path / f"test_dummy_{n}.py").write_text("def test_x():\n    pass\n")
    metrics["test_files"] = 7
    (tmp_path / "release_metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    monkeypatch.setattr(release_check, "ROOT", tmp_path)
    monkeypatch.setattr(release_check, "FAILURES", [])
    release_check.check_runtime_competition_assets()
    assert any("test_files=7 but source tree has 3" in m for m in release_check.FAILURES), release_check.FAILURES
    release_check.FAILURES.clear()
    metrics["test_files"] = 3
    (tmp_path / "release_metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    release_check.check_runtime_competition_assets()
    assert not any("test_files" in m for m in release_check.FAILURES)
