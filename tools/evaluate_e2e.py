"""End-to-end check through the real website API (V289).

    python tools/evaluate_e2e.py      # -> evaluation/results/e2e_results.json

tools/evaluate_engine.py calls the analysis functions directly. This tool sends the
same cases the way the chat page does — consent first, then POST /api/analyze with
the JSON the browser sends — and compares the urgency the API returns with the
engine-level result. Any difference means the web layer (validation, gating,
emergency short-cut, response shaping) changes the decision.

It also measures the AI-reply guard (answer_guard.py): for every case the rules say
needs a doctor soon or today, a set of dismissive model replies ("nothing to worry
about", «لا داعي لزيارة الطبيب») must come back without the dismissive sentence and
with advice to see a doctor.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
OUT = ROOT / "evaluation" / "results" / "e2e_results.json"

DISMISSIVE_REPLIES = {
    "ar": ["هذا غالبًا شيء بسيط ولا داعي لزيارة الطبيب.", "لا داعي للقلق، ارتح واشرب سوائل.",
           "الحالة ليست خطيرة وستزول من تلقاء نفسها.", "ما يحتاج طبيب، بيروح لحاله."],
    "en": ["This is usually minor and there is no need to see a doctor.", "Nothing to worry about, just rest and drink fluids.",
           "It is not serious and it will go away on its own.", "You don't need a doctor for this."],
}


def run() -> dict:
    import evaluate_engine as ev

    ev.isolated_environment()
    import answer_guard
    import webapp

    client = webapp.app.test_client()
    assert client.post("/api/consent/preferences", json={"service_usage": True, "analytics_research": False}).status_code == 200
    cases = ev.load_cases()
    n = agree = 0
    diffs, per_cond, times = [], {}, []
    guard_cases = guard_ok = 0
    ip = 0
    for cond, items in cases.items():
        c_n = c_agree = 0
        for case in items:
            ip += 1
            body = {"symptoms": [case["text"]], "age": case.get("age", 35), "gender": "", "duration": "", "severity": 2,
                    "notes": "", "lang": case["lang"]}
            t0 = time.perf_counter()
            resp = client.post("/api/analyze", json=body,
                               environ_overrides={"REMOTE_ADDR": "198.19.%d.%d" % (ip // 250, ip % 250 + 1)})
            times.append(time.perf_counter() - t0)
            d = resp.get_json() or {}
            api_level = str(d.get("urgency") or "low") if d.get("ok") else "error"
            engine_level = ev.predict(case, "hybrid", 2, case.get("age", 35))[0]
            n += 1
            c_n += 1
            if api_level == engine_level:
                agree += 1
                c_agree += 1
            else:
                diffs.append({"condition": cond, "id": case["id"], "engine": engine_level, "api": api_level, "text": case["text"]})
            # AI-reply guard on cases the rules send to a doctor
            if answer_guard.required_care(case["text"], case["lang"]):
                for reply in DISMISSIVE_REPLIES["en" if case["lang"] == "en" else "ar"]:
                    guard_cases += 1
                    out, _changed = answer_guard.guard(reply, case["text"], case["lang"])
                    guard_ok += (not answer_guard._DISMISSIVE.search(out)) and bool(answer_guard._ADVISES_DOCTOR.search(out))
        per_cond[cond] = {"n": c_n, "agree": c_agree}
    times.sort()
    return {
        "meta": {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "route": "POST /api/analyze",
                 "controlled": {"severity": 2, "duration": "", "ai_provider": "disabled"}},
        "api_engine_agreement": {"k": agree, "n": n},
        "by_condition": per_cond,
        "differences": diffs,
        "latency_ms": {"median": round(1000 * times[len(times) // 2], 1), "p95": round(1000 * times[int(len(times) * 0.95)], 1)},
        "ai_guard": {"k": guard_ok, "n": guard_cases},
    }


def main() -> int:
    res = run()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    a, g = res["api_engine_agreement"], res["ai_guard"]
    print(f"API vs engine agreement: {a['k']}/{a['n']}  latency median {res['latency_ms']['median']} ms, p95 {res['latency_ms']['p95']} ms")
    print(f"AI-reply guard: {g['k']}/{g['n']} dismissive replies corrected")
    for d in res["differences"][:40]:
        print("DIFF", d["condition"], d["id"], d["engine"], "->", d["api"], "|", d["text"][:70])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
