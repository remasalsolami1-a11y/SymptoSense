"""Keyword baseline for the evaluation (V286): "better than what?"

A deliberately simple, but FAIR, comparison system: it knows exactly the same
emergency vocabulary as SymptoSense and differs only in what it does with it.

Vocabulary (built automatically, never hand-picked to look weak):
    every quoted phrase in safety_engine.py, emergency_lexicon.py and red_flag_concepts.py
    that SymptoSense ITSELF treats as an emergency when written on its own.

Matching: the same text normalisation (letter folding, lower case) and the same
whole-word phrase boundaries as the engine, so the baseline is not penalised for
trivial spelling differences. What it does NOT have, by design:
    * negation ("ما عندي ألم صدر" still matches "ألم صدر" if that phrase is in the list)
    * one-letter typo correction, Arabizi, and compositional concepts (two signs
      that are only an emergency together, e.g. head injury + repeated vomiting)
    * triage rules and the knowledge base (output is high or low only)

Compare it with the "rules" architecture, which has the same output space.
"""
from __future__ import annotations

import ast
import json
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SOURCES = ("safety_engine.py", "emergency_lexicon.py", "red_flag_concepts.py")
CACHE = ROOT / "evaluation" / "keyword_baseline_vocabulary.json"


def _string_constants(path: Path) -> set[str]:
    out = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            s = node.value.strip()
            # phrases only: skip regexes, docstrings, ids and format strings
            if 2 < len(s) <= 60 and "\n" not in s and not any(ch in s for ch in "\\()[]{}|^$?*+%=_") and any(c.isalpha() for c in s):
                out.add(s)
    return out


def build_vocabulary() -> list[str]:
    """Phrases that SymptoSense flags as an emergency on their own."""
    import safety_engine

    candidates = set()
    for name in SOURCES:
        candidates |= _string_constants(ROOT / name)
    vocab = []
    for phrase in sorted(candidates):
        lang = "en" if phrase.isascii() else "ar"
        if safety_engine.evaluate({"symptoms": [phrase], "notes": ""}, lang=lang).get("emergency"):
            vocab.append(phrase)
    return vocab


@lru_cache(maxsize=1)
def vocabulary() -> tuple[str, ...]:
    if CACHE.exists():
        return tuple(json.loads(CACHE.read_text(encoding="utf-8"))["phrases"])
    return tuple(build_vocabulary())


def write_vocabulary() -> Path:
    phrases = build_vocabulary()
    CACHE.write_text(json.dumps({"about": __doc__.strip().splitlines()[0], "n": len(phrases), "phrases": phrases},
                                ensure_ascii=False, indent=1), encoding="utf-8")
    vocabulary.cache_clear()
    return CACHE


def predict(text: str) -> tuple[str, str]:
    """('high' | 'low', matched phrase)."""
    import clinical_text

    norm = clinical_text.normalize_clinical_text(text).replace(" | ", " ")
    for phrase in vocabulary():
        if clinical_text._phrase_pattern(phrase).search(norm):
            return "high", phrase
    return "low", ""


if __name__ == "__main__":
    print(f"{len(json.loads(write_vocabulary().read_text(encoding='utf-8'))['phrases'])} phrases -> {CACHE}")
