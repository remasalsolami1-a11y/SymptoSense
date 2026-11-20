"""Blinded clinician review packet for the evaluation set (V284).

    python tools/doctor_review_packet.py make     # -> evaluation/doctor_review.csv (+ instructions)
    # the clinician fills the doctor_label column (high / medium / low) and saves the file as
    # evaluation/doctor_labels.csv
    python tools/doctor_review_packet.py check    # validates the filled file
    python tools/evaluate_engine.py               # now uses the clinician labels as reference

Blinding: the packet shows only the case text under a neutral id (R001…). Case ids
such as BENCH-H07 encode the expected level (H/M/L), so they are kept in a separate key
file that is not sent to the reviewer. The packet contains neither the starter label nor
anything the engine produced, and the order is shuffled with a fixed seed so urgent
cases are not grouped together. Arabic cases are reviewed once in their
colloquial form; the label is applied to the MSA and typo variants of the same case.
"""
from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

EVAL = ROOT / "evaluation"
PACKET = EVAL / "doctor_review.csv"
KEY = EVAL / "doctor_review_key.csv"   # review_id -> case_id; never sent to the reviewer
FILLED = EVAL / "doctor_labels.csv"
FIELDS = ["review_id", "language", "case_text", "doctor_label", "doctor_note"]

INSTRUCTIONS = """# مراجعة الحالات — تعليمات للطبيب المراجِع / Reviewer instructions

لكل حالة، اختر مستوى الرعاية المناسب **لشخص بالغ يصف هذه الأعراض الآن**، بناءً على النص وحده:

| القيمة في عمود doctor_label | المعنى |
|---|---|
| `high` | طوارئ الآن: اتصل بالإسعاف 997 أو توجّه للطوارئ فورًا |
| `medium` | يحتاج تقييمًا طبيًا خلال 24–48 ساعة (موعد عاجل / عيادة) |
| `low` | رعاية ذاتية ومراقبة، مع معرفة متى تعود |

- اكتب القيمة بالإنجليزية كما في الجدول (high / medium / low).
- لا توجد إجابة من النظام في هذا الملف عمدًا (مراجعة عمياء).
- إذا كانت الحالة غامضة، اختر المستوى الأكثر أمانًا واكتب السبب في `doctor_note`.
- الوقت المتوقع: 20–30 ثانية لكل حالة.

For each case choose the appropriate level of care for an adult describing these symptoms now:
`high` = emergency now (call 997 / ER), `medium` = medical assessment within 24–48 h, `low` = self-care and monitoring.
The file intentionally contains no system output (blinded review).
"""


def packet_rows() -> list[dict]:
    import evaluate_engine as ev

    cases = ev.load_cases()
    rows = [{"case_id": c["id"], "language": "en", "case_text": c["text"]} for c in cases["en_dev"] + cases["en_test"]]
    rows += [{"case_id": c["id"], "language": "ar", "case_text": c["text"]} for c in cases["ar_dialect"]]
    random.Random(20261112).shuffle(rows)
    # V285 cases are appended after the V284 ones (shuffled among themselves) so that
    # R001–R220 keep the same meaning in a packet that may already be with the reviewer.
    extra = [{"case_id": c["id"], "language": "ar", "case_text": c["text"]}
             for cond in ("ar_code_switch", "ar_arabizi") for c in cases.get(cond, [])]
    random.Random(20261113).shuffle(extra)
    rows += extra
    # V287 error-taxonomy cases, appended again so earlier ids keep their meaning
    tx = [{"case_id": c["id"], "language": c["lang"], "case_text": c["text"]} for c in cases.get("taxonomy_dev", [])]
    random.Random(20261114).shuffle(tx)
    rows += tx
    # V287 children: the age is part of the case, so the reviewer sees it
    ped = [{"case_id": c["id"], "language": c["lang"], "case_text": f"[{'العمر' if c['lang'] == 'ar' else 'age'}: {c['age']}] {c['text']}"}
           for c in cases.get("pediatric", [])]
    random.Random(20261115).shuffle(ped)
    rows += ped
    # V289 'see a doctor soon' combinations and their look-alikes
    mc = [{"case_id": c["id"], "language": c["lang"], "case_text": c["text"]} for c in cases.get("medium_combo", [])]
    random.Random(20261116).shuffle(mc)
    rows += mc
    # V290 error types from the sealed fresh probe set, new wording, with look-alikes
    vd = [{"case_id": c["id"], "language": c["lang"], "case_text": c["text"]} for c in cases.get("v290_dev", [])]
    random.Random(20261117).shuffle(vd)
    rows += vd
    for i, r in enumerate(rows, 1):
        r["review_id"] = "R%03d" % i
    return rows


def key() -> dict[str, str]:
    return {r["review_id"]: r["case_id"] for r in packet_rows()}


def make() -> Path:
    EVAL.mkdir(exist_ok=True)
    rows = packet_rows()
    with PACKET.open("w", newline="", encoding="utf-8-sig") as fh:  # BOM: Excel shows Arabic correctly
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({"review_id": r["review_id"], "language": r["language"], "case_text": r["case_text"],
                        "doctor_label": "", "doctor_note": ""})
    with KEY.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["review_id", "case_id"])
        w.writerows((r["review_id"], r["case_id"]) for r in rows)
    (EVAL / "DOCTOR_REVIEW_INSTRUCTIONS.md").write_text(INSTRUCTIONS, encoding="utf-8")
    print(f"{len(rows)} cases -> {PACKET}")
    return PACKET


def check(path: Path = FILLED) -> int:
    if not path.exists():
        print(f"missing {path} (save the completed packet under this name)")
        return 1
    expected = set(key())
    seen, bad = set(), []
    with path.open(encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            cid = (row.get("review_id") or "").strip()
            label = (row.get("doctor_label") or "").strip().lower()
            if cid not in expected:
                bad.append(f"unknown review_id {cid!r}")
            elif label not in ("high", "medium", "low"):
                bad.append(f"{cid}: doctor_label {label!r} is not high/medium/low")
            seen.add(cid)
    missing = sorted(expected - seen)
    for msg in bad[:20]:
        print("ERROR", msg)
    if missing:
        print(f"{len(missing)} cases not labelled, e.g. {missing[:5]}")
    print(f"{len(seen) - len(bad)} valid labels of {len(expected)}")
    return 1 if bad or missing else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=["make", "check"])
    a = ap.parse_args(argv)
    if a.action == "make":
        make()
        return 0
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
