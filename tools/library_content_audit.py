"""Editorial audit of health-library condition pages (read-only).

Reads the live knowledge base (SQLite locally, PostgreSQL when DATABASE_URL is set)
and reports, per active condition:
  * words per section and in total (thin pages);
  * a "risk factors" field that does not describe who is at risk — it reads like a
    complication, a red flag or an instruction instead (the appendicitis case);
  * whether the only Saudi reference is the generic MOH 937 care-navigation link.

Nothing is changed. Fixes go through the admin knowledge editor so they pass the
clinical review queue. Usage:
    python tools/library_content_audit.py [--csv report.csv] [--min-words 150] [--fail-on-misplaced]
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SECTIONS = ("description", "common_causes", "risk_factors", "red_flags", "recommended_next_step")

# Phrases that describe a complication, a warning sign or an instruction rather than
# who is more likely to get the condition.  Matched on the Arabic text.
_NOT_RISK = re.compile(
    r"(يحتاج|يلزم|تحتاج|اطلب|راجع|طوارئ|عاجل|تقييم|مضاعفات|قد يسبب|قد تسبب|قد يؤدي|قد تؤدي|قد يتطور|قد تتطور|"
    r"قد ينتشر|قد تنتشر|خطر السقوط|الوفاة|تلفًا|نزيف|ثقب|خراج|إذا أثرت|ظهور مفاجئ)"
)
# Phrases that do describe a population, exposure or predisposing condition.
_IS_RISK = re.compile(
    r"(أكثر شيوع|أكثر عرضة|يزيد احتمال|تزيد احتمال|يزيد خطر|تزيد خطر|لدى|كبار السن|الأطفال|النساء|الرجال|الحمل|"
    r"السمنة|زيادة الوزن|التدخين|التاريخ العائلي|تاريخ عائلي|الوراث|السكري|ضعف المناعة|العمر|بعد سن|التعرض|"
    r"الإفراط|قلة|نقص|الجلوس|الحرارة|الرطوبة|المهن|الأعمال المتكررة|تكرار|ممارسة|الرياضة|السفر|مشاركة|الأدوية|"
    r"التوتر|القلق|الكافيين|الأحذية|زيادة المشي)"
)


def words(text) -> int:
    return len(str(text or "").split())


def classify_risk(text: str) -> str:
    """'ok' | 'misplaced' (reads like a complication/red flag/instruction; no at-risk group) | 'mixed' | 'empty'.

    A triage heuristic for human editors, not a medical judgement."""
    text = str(text or "").strip()
    if not text:
        return "empty"
    not_risk, is_risk = bool(_NOT_RISK.search(text)), bool(_IS_RISK.search(text))
    if not_risk and not is_risk:
        return "misplaced"
    if not_risk and is_risk:
        return "mixed"
    return "ok" if is_risk else "misplaced"


def audit(min_words: int = 150) -> list[dict]:
    import health_library
    import medical_knowledge as mk

    rows = []
    for d in mk.list_entities("diseases", False, ""):
        item = health_library._entity_by_slug("disease", d["slug"]) or d
        sources = item.get("sources") or []
        per = {s: words(item.get(s + "_ar")) for s in SECTIONS}
        total = sum(per.values())
        local = [s for s in sources if str(s.get("slug", "")).startswith("saudi-")]
        rows.append({
            "slug": d["slug"],
            "name_ar": d.get("name_ar"),
            "total_words_ar": total,
            **{f"{s}_words": n for s, n in per.items()},
            "thin": total < min_words,
            "risk_factors_check": classify_risk(item.get("risk_factors_ar")),
            "risk_factors_ar": str(item.get("risk_factors_ar") or "").strip(),
            "sources": len(sources),
            "saudi_specific_source": any(s.get("slug") != "saudi-moh-937" for s in local),
        })
    rows.sort(key=lambda r: (r["risk_factors_check"] != "misplaced", r["total_words_ar"]))
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--csv", help="write the full report to this CSV file")
    ap.add_argument("--min-words", type=int, default=150)
    ap.add_argument("--fail-on-misplaced", action="store_true", help="exit 1 if any risk-factors field is misplaced")
    args = ap.parse_args(argv)
    rows = audit(args.min_words)
    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as fh:  # BOM so Excel shows Arabic
            w = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["slug"])
            w.writeheader()
            w.writerows(rows)
    n = len(rows) or 1
    totals = sorted(r["total_words_ar"] for r in rows)
    count = lambda key, val: sum(1 for r in rows if r[key] == val)
    print(f"Conditions audited: {len(rows)}")
    print(f"Median words per page (AR): {totals[len(totals) // 2] if totals else 0}")
    print(f"Thin pages (< {args.min_words} words): {count('thin', True)} ({100 * count('thin', True) // n}%)")
    print(f"Risk factors misplaced: {count('risk_factors_check', 'misplaced')} · mixed: {count('risk_factors_check', 'mixed')} · empty: {count('risk_factors_check', 'empty')}")
    print(f"Pages whose only Saudi link is MOH 937: {count('saudi_specific_source', False)}")
    for r in rows:
        if r["risk_factors_check"] == "misplaced":
            print(f"  - {r['slug']}: {r['risk_factors_ar'][:90]}")
    return 1 if args.fail_on_misplaced and count("risk_factors_check", "misplaced") else 0


if __name__ == "__main__":
    raise SystemExit(main())
