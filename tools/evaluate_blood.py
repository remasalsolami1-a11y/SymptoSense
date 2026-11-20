"""Offline evaluation of the blood-report pipeline (V288).

    python tools/evaluate_blood.py                 # -> evaluation/results/blood_results.json
    python tools/evaluate_blood.py --root OTHER    # run another checkout (e.g. a previous version)

For every synthetic report in evaluation/blood_reports.json the real code runs:
parse_blood_text -> analyze_blood -> describe_results. Measured:
  * extraction: expected tests found with the right value (recall) and extra tests (precision);
  * status: low / normal / high / unclassified against the printed laboratory range;
  * report level: normal / see_doctor / unclassified / urgent / emergency;
  * critical sensitivity: reports that need urgent or emergency care shown as such;
  * false critical alarms: other reports shown as urgent or emergency.
Wilson 95% intervals (same code as tools/evaluate_engine.py).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
BENCH = HERE / "evaluation" / "blood_reports.json"
OUT = HERE / "evaluation" / "results" / "blood_results.json"
CRITICAL = {"urgent", "emergency"}


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return max(0.0, (c - m) / d), min(1.0, (c + m) / d)


def rate(k: int, n: int) -> dict:
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "value": (k / n) if n else None, "ci95": [round(lo, 4), round(hi, 4)]}


def run(root: Path = HERE, bench: Path = BENCH) -> dict:
    sys.path.insert(0, str(root))
    os.environ.setdefault("DB_PATH", str(Path(tempfile.mkdtemp()) / "blood_eval.db"))
    import blood_test

    reports = json.loads(bench.read_text(encoding="utf-8"))["reports"]
    found = expected_n = value_ok = status_ok = extra = 0
    level_ok = crit_k = crit_n = alarm_k = alarm_n = 0
    by_format: dict[str, Counter] = {}
    rows = []
    for rep in reports:
        entries, _age = blood_test.parse_blood_text(rep["text"])
        results, _notes, dangers, level, _child = blood_test.analyze_blood(entries, rep["gender"], rep["age"])
        got = {str(r.get("key")): r for r in results}
        fmt = by_format.setdefault(rep["format"], Counter())
        ok_all = True
        for e in rep["expected"]:
            expected_n += 1
            r = got.get(e["key"])
            if r is None:
                ok_all = False
                continue
            found += 1
            raw = r.get("raw_value", r.get("value"))
            v_ok = raw is not None and abs(float(raw) - float(e["value"])) < 1e-6
            s_ok = r.get("status") == e["status"]
            value_ok += v_ok
            status_ok += v_ok and s_ok
            ok_all &= v_ok and s_ok
        extra += len([k for k in got if k not in {e["key"] for e in rep["expected"]}])
        l_ok = level == rep["expected_level"]
        level_ok += l_ok
        if rep["expected_level"] in CRITICAL:
            crit_n += 1
            crit_k += level in CRITICAL
        else:
            alarm_n += 1
            alarm_k += level in CRITICAL
        fmt["reports"] += 1
        fmt["fully_correct"] += ok_all and l_ok
        rows.append({"id": rep["id"], "format": rep["format"], "expected_level": rep["expected_level"], "level": level,
                     "rows_correct": ok_all, "got": {k: [r.get("raw_value", r.get("value")), r.get("status")] for k, r in got.items()}})
    return {
        "meta": {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "root": root.name,
                 "reports": len(reports), "expected_rows": expected_n},
        "extraction_recall": rate(value_ok, expected_n),
        "extra_rows": extra,
        "status_accuracy": rate(status_ok, expected_n),
        "level_accuracy": rate(level_ok, len(reports)),
        "critical_sensitivity": rate(crit_k, crit_n),
        "false_critical_alarms": rate(alarm_k, alarm_n),
        "by_format": {k: dict(v) for k, v in sorted(by_format.items())},
        "reports": rows,
    }


def _pct(m: dict) -> str:
    return "—" if m["value"] is None else f"{100 * m['value']:.1f}% [{100 * m['ci95'][0]:.0f}–{100 * m['ci95'][1]:.0f}] ({m['k']}/{m['n']})"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=str(HERE))
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    res = run(Path(a.root).resolve())
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for k in ("extraction_recall", "status_accuracy", "level_accuracy", "critical_sensitivity", "false_critical_alarms"):
        print(f"{k:24} {_pct(res[k])}")
    print("by format:", res["by_format"])
    for r in res["reports"]:
        if not r["rows_correct"] or r["level"] != r["expected_level"]:
            print("MISS", r["id"], r["format"], r["expected_level"], "->", r["level"], r["got"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
