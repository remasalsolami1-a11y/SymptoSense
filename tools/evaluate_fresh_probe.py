"""Measure the sealed fresh-wording probe set (V290).

    python tools/evaluate_fresh_probe.py     # -> evaluation/results/fresh_probe_results.json

evaluation/fresh_probe_sealed.json was written for the V289 code review and sealed
before any V290 change (sha256 in evaluation/HELDOUT_LOG.md). Its errors were seen
once, so it is reported as an *inspected probe set*, not a blind held-out estimate.
Labels are never edited; remaining differences are listed with the engine's answer.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
SEALED = ROOT / "evaluation" / "fresh_probe_sealed.json"
SEALED_SHA256 = "987ad78ec0e56ada74654fd9f6a61c99ce1d1ded202e2db01697b7b75755b0a1"
OUT = ROOT / "evaluation" / "results" / "fresh_probe_results.json"


def run() -> dict:
    import evaluate_engine as ev

    ev.isolated_environment()
    import blood_test

    raw = SEALED.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    sym_wrong = []
    for c in data["symptoms"]:
        got, why = ev.predict({"text": c["text"], "lang": c["lang"]}, "hybrid", 2, 35)
        if got != c["expected"]:
            sym_wrong.append({"id": c["id"], "expected": c["expected"], "got": got, "text": c["text"], "engine_reason": why})
    blood_wrong = []
    for c in data["blood"]:
        entries, _ = blood_test.parse_blood_text(c["text"])
        results, _notes, _d, level, _x = blood_test.analyze_blood(entries, c["gender"], c["age"])
        got = {r["key"]: (float(r.get("raw_value", r.get("value"))), r["status"]) for r in results}
        ok = level == c["expected_level"] and all(
            k in got and abs(got[k][0] - float(v["value"])) < 1e-6 and got[k][1] == v["status"] for k, v in c["expected"].items())
        if not ok:
            blood_wrong.append({"id": c["id"], "text": c["text"], "expected": c["expected"], "expected_level": c["expected_level"],
                                "got": {k: list(v) for k, v in got.items()}, "got_level": level})
    nsym, nblood = len(data["symptoms"]), len(data["blood"])
    return {
        "meta": {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "sealed_sha256_ok": hashlib.sha256(raw).hexdigest() == SEALED_SHA256,
                 "status": "inspected probe set (errors seen once at V289); not a blind held-out estimate"},
        "baseline_v289": data["baseline_v289"],
        "symptoms": {"correct": nsym - len(sym_wrong), "n": nsym, "wrong": sym_wrong},
        "blood": {"correct": nblood - len(blood_wrong), "n": nblood, "wrong": blood_wrong},
    }


def main() -> int:
    res = run()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    b = res["baseline_v289"]
    print(f"seal ok: {res['meta']['sealed_sha256_ok']}")
    print(f"symptoms {res['symptoms']['correct']}/{res['symptoms']['n']} (V289: {b['symptoms_n'] - b['symptoms_wrong']}/{b['symptoms_n']})")
    print(f"blood    {res['blood']['correct']}/{res['blood']['n']} (V289: {b['blood_n'] - b['blood_wrong']}/{b['blood_n']})")
    for w in res["symptoms"]["wrong"]:
        print("  SYM", w["id"], w["expected"], "->", w["got"], "|", w["text"])
    for w in res["blood"]["wrong"]:
        print("  BLD", w["id"], w["expected_level"], "->", w["got_level"], w["got"], "|", w["text"][:50])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
