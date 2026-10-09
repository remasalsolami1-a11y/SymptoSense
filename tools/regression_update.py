"""Regenerate medical_regression_snapshot.json. Review the diff with a clinician before committing."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import medical_regression  # noqa: E402

path = os.path.join(ROOT, "medical_regression_snapshot.json")
with open(path, "w", encoding="utf-8") as fh:
    json.dump(medical_regression.snapshot(), fh, ensure_ascii=False, indent=2, sort_keys=True)
    fh.write("\n")
print("wrote", path)
