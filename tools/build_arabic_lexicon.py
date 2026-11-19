"""Build arabic_lexicon.txt: real Arabic words, so typo correction never "fixes" them (V290).

    python tools/build_arabic_lexicon.py

The red-flag layer corrects one-letter slips ("انتفت" -> "انتفخت"). Without a list of
real words it also changed correct words into concept words: «الصغير» -> «الصفير»
(wheeze), «يوميه» -> «يغميه» (faint), «يربط» -> «يخربط» (garbled speech). Every
normalised Arabic word of 4+ letters that appears in the app's own content (knowledge
base, lab cards, pages, rule files) is taken as a real word. Evaluation sets, tests and
change logs are excluded, because they deliberately contain misspellings.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "arabic_lexicon.txt"
EXCLUDE_PREFIX = ("evaluation/", "tests/", "tools/", "clinical_review/doctor_review")
# live_demo.py shows deliberate typos ("شفيفي") as a demonstration, so it is not a source of real words.
EXCLUDE_FILES = {"arabic_lexicon.txt", "red_flag_concepts.py", "text_context.py", "arabizi.py", "emergency_lexicon.py", "live_demo.py"}
# Common words that the correction mistook for concept words, added explicitly in case the
# app's content stops using them.
EXTRA = ("صغير", "الصغير", "صغيره", "الصغيره", "يوميه", "يومي", "يربط", "يفهم", "يحميك", "يخفي", "ينتظر", "ينشر", "يشبه",
         "يصحح", "يسترجع", "يرجع", "السلامه", "المشي", "الوقت", "الموقع", "المرض", "الحكه", "السكر", "القلبيه", "الطفوله", "طفوله",
         "طفولتي", "الكلب", "كلب", "مايه", "رضاعته", "رضاعه", "كهربائي")


def build() -> list[str]:
    import clinical_text

    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    words: set[str] = set(EXTRA)
    for name in files:
        if name.startswith(EXCLUDE_PREFIX) or name.endswith(".md") or Path(name).name in EXCLUDE_FILES:
            continue
        try:
            text = (ROOT / name).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        words |= set(re.findall(r"[؀-ۿ]{4,}", text))
    out = set()
    for w in words:
        n = clinical_text.normalize_clinical_text(w).replace("|", "").strip()
        if len(n) >= 4 and " " not in n:
            out.add(n)
    return sorted(out)


def main() -> int:
    words = build()
    OUT.write_text("\n".join(words) + "\n", encoding="utf-8")
    print(f"{len(words)} words -> {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
