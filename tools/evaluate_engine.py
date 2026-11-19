"""Reproducible offline evaluation of the SymptoSense triage engine (V284).

What it measures
----------------
Every vignette has a reference urgency (high / medium / low). The engine's urgency
is compared with it under several *conditions* (same clinical content, different
input form) and for several *architectures* (ablation):

  conditions     en_dev           60 English starter vignettes used during development
                 en_test          120 held-out English vignettes (never inspected case by case)
                 ar_msa           Arabic, Modern Standard
                 ar_dialect       Arabic, Saudi/Gulf colloquial
                 ar_dialect_typos the dialect text with realistic keyboard variations
                 negation         red-flag words that are explicitly denied ("no chest pain")
                 ar_code_switch   Arabic mixed with English medical words (V285, author-written dev set)
                 ar_arabizi       Arabic typed in Latin letters and digits (V285, author-written dev set)
                 taxonomy_dev     V287 error-taxonomy cases, Arabic + English, with mild look-alikes (dev set)
                 pediatric        V287 children with their real age (dev set; labels need clinician review)
                 medium_combo     V289 'see a doctor soon' combinations with mild look-alikes (dev set)
                 v290_dev         V290 error types from the sealed fresh probe set, new wording + look-alikes (dev set)
                 safety_suite     safety_engine.validation_report() regression matrix
  architectures  keyword          V286 comparison baseline: same emergency vocabulary, plain keyword
                                   matching, no negation / typos / concepts / Arabizi (tools/keyword_baseline.py)
                 rules            deterministic red-flag rules only (high / low)
                 rules_triage     + pre-triage rules (high / medium / low)
                 hybrid           full pipeline: + knowledge-base risk (what users get)

Metrics: accuracy, Cohen's kappa, sensitivity for "high" (urgent cases caught),
critical under-triage (urgent case shown as low), under/over-triage rates, all with
Wilson 95% confidence intervals.

Controlled variables: severity (default 2 of 5 — 3 alone forces "review", 4–5 force "today"), age (35), no duration, no AI provider
(urgency is computed by the deterministic layers only; the AI layer only writes text),
fresh temporary database. Run:

    python tools/evaluate_engine.py --out evaluation/results
    python tools/evaluate_engine.py --severity-sweep          # effect of reported severity

Reference labels are the starter-benchmark labels until a clinician fills
evaluation/doctor_labels.csv (see tools/doctor_review_packet.py); then the doctor's
labels become the reference and agreement is reported.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import sys
import tempfile
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "evaluation"
LEVELS = ("low", "medium", "high")
RANK = {lvl: i for i, lvl in enumerate(LEVELS)}
ARCHITECTURES = ("keyword", "rules", "rules_triage", "hybrid")
# en_test was a clean held-out set up to V285. Its misses were inspected in V287 to build the
# error taxonomy (evaluation/HELDOUT_LOG.md), so from then on its numbers are development numbers.
EN_TEST_INSPECTED_FROM = "V287"
FROZEN_HELDOUT = EVAL_DIR / "frozen" / "results_V286_last_clean_en_test.json"


# ------------------------------------------------------------------ statistics
def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    """95% Wilson score interval for k successes out of n (robust for small n and p near 0/1)."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def cohen_kappa(pairs: list[tuple[str, str]]) -> float | None:
    n = len(pairs)
    if not n:
        return None
    observed = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    expected = sum(ca[x] * cb[x] for x in LEVELS) / (n * n)
    return None if expected == 1 else (observed - expected) / (1 - expected)


def rate(k: int, n: int) -> dict:
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "value": (k / n) if n else None, "ci95": [round(lo, 4), round(hi, 4)]}


def metrics(rows: list[dict]) -> dict:
    """rows: dicts with 'expected' and 'predicted' in LEVELS."""
    pairs = [(r["expected"], r["predicted"]) for r in rows]
    n = len(pairs)
    high = [p for e, p in pairs if e == "high"]
    not_high = [p for e, p in pairs if e != "high"]
    return {
        "n": n,
        "accuracy": rate(sum(e == p for e, p in pairs), n),
        "kappa": None if cohen_kappa(pairs) is None else round(cohen_kappa(pairs), 4),
        "high_sensitivity": rate(sum(p == "high" for p in high), len(high)),
        "high_specificity": rate(sum(p != "high" for p in not_high), len(not_high)),
        "critical_under_triage": rate(sum(p == "low" for p in high), len(high)),
        "under_triage": rate(sum(RANK[p] < RANK[e] for e, p in pairs), n),
        "over_triage": rate(sum(RANK[p] > RANK[e] for e, p in pairs), n),
        "confusion": {e: {p: sum(1 for a, b in pairs if a == e and b == p) for p in LEVELS} for e in LEVELS},
    }


# ------------------------------------------------------------------ input conditions
_ARABIC_VARIANTS = (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ة ", "ه "), ("ى ", "ي "))


def arabic_typos(text: str, seed: str) -> str:
    """Deterministic, realistic Arabic typing variation: unnormalised hamza / taa marbuta /
    alef maqsura, plus one dropped letter in one long word. Same seed -> same output."""
    rng = random.Random(seed)
    out = text + " "
    for a, b in _ARABIC_VARIANTS:
        out = out.replace(a, b)
    words = out.split()
    long_words = [i for i, w in enumerate(words) if len(w) >= 5]
    if long_words:
        i = rng.choice(long_words)
        j = rng.randrange(1, len(words[i]) - 1)
        words[i] = words[i][:j] + words[i][j + 1:]
    return unicodedata.normalize("NFC", " ".join(words))


def load_cases() -> dict[str, list[dict]]:
    import research_validation as rv

    def english(rows):
        return [{"id": cid, "text": text, "expected": label, "lang": "en", "group": grp} for cid, text, label, _ref, grp in rows]
    data = json.loads((EVAL_DIR / "arabic_cases.json").read_text(encoding="utf-8"))
    msa, dialect, typos = [], [], []
    for c in data["cases"]:
        base = {"expected": c["label"], "lang": "ar", "source": c["source"]}
        msa.append({**base, "id": c["source"] + "-MSA", "text": c["msa"]})
        dialect.append({**base, "id": c["source"] + "-DIA", "text": c["dialect"]})
        typos.append({**base, "id": c["source"] + "-TYP", "text": arabic_typos(c["dialect"], c["source"])})
    negation = [{"id": c["id"], "text": c["text"], "expected": c["label_max"], "lang": "en" if c["text"].isascii() else "ar",
                 "max_ok": c["label_max"]} for c in data["negation"]]
    # en_dev (60) was used while developing red_flag_concepts; en_test (120) was not looked
    # at case by case, so it estimates performance on wording the rules were not tuned to.
    out = {"en_dev": english(rv._STARTER), "en_test": english(rv._STARTER_V2 + rv._STARTER_V3), "ar_msa": msa, "ar_dialect": dialect, "ar_dialect_typos": typos, "negation": negation}
    # V285: code-switching (Arabic + English words) and Arabizi. Author-written DEV sets.
    cs_path = EVAL_DIR / "code_switching_cases.json"
    if cs_path.exists():
        cs = json.loads(cs_path.read_text(encoding="utf-8"))["cases"]
        for form, cond in (("code_switch", "ar_code_switch"), ("arabizi", "ar_arabizi")):
            out[cond] = [{"id": c["id"], "text": c["text"], "expected": c["label"], "lang": "ar", "region": c["region"]}
                         for c in cs if c["form"] == form]
    tx_path = EVAL_DIR / "taxonomy_dev_cases.json"
    if tx_path.exists():  # V287 error-taxonomy development cases (both languages)
        out["taxonomy_dev"] = [{"id": c["id"], "text": c["text"], "expected": c["label"], "lang": c["lang"], "category": c["category"]}
                               for c in json.loads(tx_path.read_text(encoding="utf-8"))["cases"]]
    mc_path = EVAL_DIR / "medium_combo_cases.json"
    if mc_path.exists():  # V289 'see a doctor soon' combinations with mild look-alikes (dev set)
        out["medium_combo"] = [{"id": c["id"], "text": c["text"], "expected": c["label"], "lang": c["lang"], "category": c["category"]}
                               for c in json.loads(mc_path.read_text(encoding="utf-8"))["cases"]]
    v290_path = EVAL_DIR / "v290_dev_cases.json"
    if v290_path.exists():  # V290 error types from the sealed fresh probe set, new wording (dev set)
        out["v290_dev"] = [{"id": c["id"], "text": c["text"], "expected": c["label"], "lang": c["lang"], "category": c["category"]}
                           for c in json.loads(v290_path.read_text(encoding="utf-8"))["cases"]]
    ped_path = EVAL_DIR / "pediatric_cases.json"
    if ped_path.exists():  # V287 children, each with its own age (dev set; labels need a clinician)
        out["pediatric"] = [{"id": c["id"], "text": c["text"], "expected": c["label"], "lang": c["lang"], "age": c["age"]}
                            for c in json.loads(ped_path.read_text(encoding="utf-8"))["cases"]]
    external = load_external()
    if external:
        out["ar_external"] = external
    return out


def load_external() -> list[dict]:
    """Externally written held-out texts (EXTERNAL_HELDOUT_PROTOCOL.md), if collected."""
    path = EVAL_DIR / "external_heldout.csv"
    if not path.exists():
        return []
    with (EVAL_DIR / "external_heldout_labels.csv").open(encoding="utf-8") as fh:
        labels = {r["scenario_id"]: r["label"] for r in csv.DictReader(fh)}
    rows = []
    with path.open(encoding="utf-8-sig") as fh:
        for i, r in enumerate(csv.DictReader(fh), 1):
            text, sid = str(r.get("text") or "").strip(), str(r.get("scenario_id") or "").strip()
            if text and sid in labels:
                rows.append({"id": f"EXT-{i:03d}", "text": text, "expected": labels[sid], "lang": "ar",
                             "region": str(r.get("region") or "unknown").strip() or "unknown",
                             "form": str(r.get("form") or "").strip(), "writer": str(r.get("writer_id") or "").strip()})
    return rows


def external_seal() -> dict | None:
    """SHA-256 of the held-out file at measurement time: shows it was not edited afterwards."""
    import hashlib
    path = EVAL_DIR / "external_heldout.csv"
    if not path.exists():
        return None
    rows = load_external()
    return {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "n": len(rows),
            "writers": len({r["writer"] for r in rows}), "regions": sorted({r["region"] for r in rows})}


# ------------------------------------------------------------------ predictors
def predict(case: dict, architecture: str, severity: int, age: int) -> tuple[str, str]:
    """(level, reason) for one case under one architecture."""
    import analysis_core
    import safety_engine

    if architecture == "keyword":
        import keyword_baseline
        return keyword_baseline.predict(case["text"])
    patient = {"symptoms": [case["text"]], "severity": severity, "age": case.get("age", age), "notes": ""}
    lang = case["lang"]
    safety = safety_engine.evaluate(patient, lang=lang)
    if architecture == "rules":
        return ("high", "red-flag rules") if safety.get("emergency") else ("low", "")
    if architecture == "rules_triage":
        if safety.get("emergency"):
            return "high", "red-flag rules"
        tri = analysis_core._triage(dict(patient), lang)
        level = {"emergency": "high", "today": "medium", "soon": "medium"}.get(tri.get("level"), "low")
        return level, str(tri.get("reason") or "")[:200]
    result = analysis_core.run_analysis(dict(patient), lang)
    reason = "; ".join(str(f) for f in (result.get("emergency_flags") or [])) or str(result.get("assessment_status") or "")
    return result.get("urgency") or "low", reason[:200]


def run(severity: int = 2, age: int = 35, architectures=ARCHITECTURES, reference: dict | None = None,
        extras: bool = True) -> dict:
    """extras=False skips ablations and breakdowns (used by the severity sweep)."""
    cases = load_cases()
    out = {"conditions": {}, "misses": []}
    for cond, items in cases.items():
        out["conditions"][cond] = {}
        for arch in architectures:
            rows = []
            for case in items:
                expected = (reference or {}).get(case["id"], case["expected"])
                predicted, why = predict(case, arch, severity, age)
                if cond == "negation":  # denied red flags: anything up to label_max is correct
                    expected = predicted if RANK[predicted] <= RANK[case["max_ok"]] else case["max_ok"]
                rows.append({"expected": expected, "predicted": predicted})
                if arch == "hybrid" and predicted != expected:
                    out["misses"].append({"condition": cond, "id": case["id"], "text": case["text"],
                                          "expected": expected, "predicted": predicted, "engine_reason": why})
            out["conditions"][cond][arch] = metrics(rows)
    out["safety_suite"] = _safety_suite()
    if "hybrid" in architectures and extras:
        out["ablation_text_context_off"] = _without_text_context(cases, severity, age, reference)
        out["ablation_v287_rules_off"] = _without_v287_rules(cases, severity, age, reference)
        out["ablation_combos_off"] = _without_combos(cases, severity, age, reference)
        out["ablation_v290_rules_off"] = _without_v290_rules(cases, severity, age, reference)
        out["ablation_past_history_off"] = _without_past_history(cases, severity, age, reference)
    if "taxonomy_dev" in cases and extras:
        out["taxonomy_by_category"] = _taxonomy_breakdown(cases["taxonomy_dev"], severity, age, reference)
    if "ar_arabizi" in cases and "hybrid" in architectures and extras:
        out["regions"] = _region_breakdown(cases, severity, age, reference)
        out["ablation_arabizi_off"] = _without_arabizi(cases, severity, age, reference)
    return out


def _hybrid_rows(items, severity, age, reference):
    return [{"expected": (reference or {}).get(c["id"], c["expected"]), "predicted": predict(c, "hybrid", severity, age)[0]}
            for c in items]


def _region_breakdown(cases, severity, age, reference) -> dict:
    """Full-system metrics per regional vocabulary (code-switching + Arabizi sets). Small n: read the CIs."""
    by_region: dict[str, list[dict]] = {}
    for cond in ("ar_code_switch", "ar_arabizi"):  # ar_external is reported on its own, never pooled with dev sets
        for c in cases.get(cond, []):
            by_region.setdefault(c["region"], []).append(c)
    return {r: metrics(_hybrid_rows(items, severity, age, reference)) for r, items in sorted(by_region.items())}


def _without_combos(cases, severity, age, reference) -> dict:
    """Ablation: the V289 'see a doctor soon' combinations switched off."""
    import text_context

    text_context.COMBOS_ENABLED = False
    text_context._extract.cache_clear()
    try:
        return {cond: metrics(_hybrid_rows(items, severity, age, reference)) for cond, items in cases.items()}
    finally:
        text_context.COMBOS_ENABLED = True
        text_context._extract.cache_clear()


def _without_v287_rules(cases, severity, age, reference) -> dict:
    """Ablation: the ten V287 error-taxonomy rules switched off."""
    import red_flag_concepts

    red_flag_concepts.V287_ENABLED = False
    try:
        return {cond: metrics(_hybrid_rows(items, severity, age, reference)) for cond, items in cases.items()}
    finally:
        red_flag_concepts.V287_ENABLED = True


def _without_v290_rules(cases, severity, age, reference) -> dict:
    """Ablation: the seven V290 rules (sealed fresh-probe error types) switched off."""
    import red_flag_concepts

    red_flag_concepts.V290_ENABLED = False
    red_flag_concepts.matched_concepts.cache_clear()
    try:
        return {cond: metrics(_hybrid_rows(items, severity, age, reference)) for cond, items in cases.items()}
    finally:
        red_flag_concepts.V290_ENABLED = True
        red_flag_concepts.matched_concepts.cache_clear()


def _without_past_history(cases, severity, age, reference) -> dict:
    """Ablation: V290 past-history handling (temporal_context.py) switched off."""
    import temporal_context
    import text_context

    temporal_context.ENABLED = False
    text_context._extract.cache_clear()
    try:
        return {cond: metrics(_hybrid_rows(items, severity, age, reference)) for cond, items in cases.items()}
    finally:
        temporal_context.ENABLED = True
        text_context._extract.cache_clear()


def _taxonomy_breakdown(items, severity, age, reference) -> dict:
    """Per error type: urgent cases caught and mild look-alikes NOT raised to emergency."""
    import red_flag_concepts

    out: dict[str, dict] = {}
    for c in items:
        row = out.setdefault(c["category"], {"urgent": 0, "urgent_caught": 0, "urgent_caught_before": 0,
                                              "urgent_caught_keyword": 0, "mild": 0, "mild_false_alarm": 0})
        expected = (reference or {}).get(c["id"], c["expected"])
        pred = predict(c, "hybrid", severity, age)[0]
        if expected == "high":
            row["urgent"] += 1
            row["urgent_caught"] += pred == "high"
            row["urgent_caught_keyword"] += predict(c, "keyword", severity, age)[0] == "high"
            red_flag_concepts.V287_ENABLED = False
            try:
                row["urgent_caught_before"] += predict(c, "hybrid", severity, age)[0] == "high"
            finally:
                red_flag_concepts.V287_ENABLED = True
        else:
            row["mild"] += 1
            row["mild_false_alarm"] += pred == "high"
    return out


def _without_text_context(cases, severity, age, reference) -> dict:
    """Ablation: the full system with duration/severity/worsening read from text switched off."""
    import text_context

    text_context.ENABLED = False
    text_context._extract.cache_clear()
    try:
        return {cond: metrics(_hybrid_rows(items, severity, age, reference)) for cond, items in cases.items() if cond != "negation"}
    finally:
        text_context.ENABLED = True


def _without_arabizi(cases, severity, age, reference) -> dict:
    """Ablation: the same sets with the Arabizi transliteration layer switched off."""
    import arabizi
    import red_flag_concepts

    arabizi.ENABLED = False
    red_flag_concepts.matched_concepts.cache_clear()
    try:
        return {cond: metrics(_hybrid_rows(cases[cond], severity, age, reference)) for cond in ("ar_code_switch", "ar_arabizi")}
    finally:
        arabizi.ENABLED = True
        red_flag_concepts.matched_concepts.cache_clear()


def _safety_suite() -> dict:
    import safety_engine

    rep = safety_engine.validation_report()
    must_fire = [c for c in rep["cases"] if c["expected"]]
    must_not = [c for c in rep["cases"] if not c["expected"]]
    return {
        "n": rep["total"],
        "passed": rate(rep["passed"], rep["total"]),
        "red_flag_sensitivity": rate(sum(c["actual"] for c in must_fire), len(must_fire)),
        "false_alarm_rate": rate(sum(c["actual"] for c in must_not), len(must_not)),
        "failed_ids": [c["id"] for c in rep["cases"] if not c["passed"]],
    }


def load_reference() -> dict | None:
    """Doctor labels (case_id -> level) when evaluation/doctor_labels.csv has been filled in."""
    path = EVAL_DIR / "doctor_labels.csv"
    if not path.exists():
        return None
    import doctor_review_packet
    review_key = doctor_review_packet.key()  # blinded R001… ids back to case ids
    ref = {}
    with path.open(encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            label = str(row.get("doctor_label") or "").strip().lower()
            rid = str(row.get("review_id") or "").strip()
            if label in LEVELS and rid in review_key:
                cid = review_key[rid]
                ref[cid] = label
                if cid.endswith("-DIA"):  # same clinical content in MSA and typo variants
                    ref[cid[:-4] + "-MSA"] = ref[cid[:-4] + "-TYP"] = label
    return ref or None


def label_agreement(reference: dict) -> dict:
    """How far the starter labels agree with the clinician (the starter labels' own reliability)."""
    pairs = [(reference[c["id"]], c["expected"]) for items in load_cases().values() for c in items
             if c["id"] in reference and not c["id"].startswith("NEG-") and not c["id"].endswith(("-MSA", "-TYP"))]
    return {"n": len(pairs), "kappa": None if not pairs else round(cohen_kappa(pairs), 4),
            "agreement": rate(sum(a == b for a, b in pairs), len(pairs))}


# ------------------------------------------------------------------ environment
def isolated_environment():
    """Fresh SQLite database and no AI provider, so results are reproducible."""
    tmp = tempfile.mkdtemp(prefix="ss-eval-")
    os.environ["DB_PATH"] = os.path.join(tmp, "eval.sqlite3")
    os.environ.pop("DATABASE_URL", None)
    for key in ("GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        os.environ.pop(key, None)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import logging
    logging.disable(logging.WARNING)
    import db
    import medical_knowledge
    db.init_db()
    medical_knowledge.init_schema()


def engine_fingerprint() -> dict:
    import release_candidate
    import safety_engine
    return {"app_version": release_candidate.metadata()["app_version"],
            "safety_engine": safety_engine.ENGINE_VERSION}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Offline triage evaluation")
    ap.add_argument("--out", default=str(EVAL_DIR / "results"))
    ap.add_argument("--severity", type=int, default=2,
                    help="2 = the highest value that triggers no severity rule, so results reflect the text alone")
    ap.add_argument("--age", type=int, default=35)
    ap.add_argument("--severity-sweep", action="store_true", help="hybrid architecture at severity 1..5")
    a = ap.parse_args(argv)
    isolated_environment()
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    reference = load_reference()
    if a.severity_sweep:
        sweep = {s: run(s, a.age, ("hybrid",), reference, extras=False)["conditions"] for s in range(1, 6)}
        (out_dir / "severity_sweep.json").write_text(json.dumps(sweep, ensure_ascii=False, indent=1), encoding="utf-8")
        for s, conds in sweep.items():
            m = conds["en_test"]["hybrid"]
            print(f"severity {s}: high sensitivity {m['high_sensitivity']['value']:.3f}  over-triage {m['over_triage']['value']:.3f}")
        return 0
    res = run(a.severity, a.age, ARCHITECTURES, reference)
    res["meta"] = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "controlled": {"severity": a.severity, "age": a.age, "ai_provider": "disabled", "duration": None},
                   "reference": "clinician (doctor_labels.csv)" if reference else "starter benchmark labels (not clinician-verified)",
                   **engine_fingerprint()}
    if reference:
        res["meta"]["starter_vs_clinician"] = label_agreement(reference)
    seal = external_seal()
    if seal:
        res["meta"]["external_heldout"] = seal
    res["meta"]["en_test_status"] = {"inspected_from": EN_TEST_INSPECTED_FROM,
                                     "last_clean": FROZEN_HELDOUT.relative_to(ROOT).as_posix() if FROZEN_HELDOUT.exists() else None}
    (out_dir / "results.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    with (out_dir / "misses.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["condition", "id", "expected", "predicted", "text", "engine_reason"])
        w.writeheader()
        w.writerows(res["misses"])
    _print_summary(res)
    return 0


def _pct(m):
    v = m["value"]
    return "  —  " if v is None else f"{100 * v:5.1f}% [{100 * m['ci95'][0]:.0f}–{100 * m['ci95'][1]:.0f}]"


def _print_summary(res):
    print(f"reference: {res['meta']['reference']}")
    print(f"{'condition':18} {'arch':13} {'n':>4}  {'accuracy':>18}  {'urgent caught':>18}  {'critical under':>18}  {'over-triage':>18}")
    for cond, archs in res["conditions"].items():
        for arch, m in archs.items():
            print(f"{cond:18} {arch:13} {m['n']:>4}  {_pct(m['accuracy']):>18}  {_pct(m['high_sensitivity']):>18}  "
                  f"{_pct(m['critical_under_triage']):>18}  {_pct(m['over_triage']):>18}")
    s = res["safety_suite"]
    print(f"safety suite: {s['passed']['k']}/{s['n']} passed; red-flag sensitivity {_pct(s['red_flag_sensitivity'])}; "
          f"false alarms {_pct(s['false_alarm_rate'])}")


if __name__ == "__main__":
    raise SystemExit(main())
