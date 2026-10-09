"""Conservative one-token typo repair shared by the health-search stack.

Arabic keeps the long-standing similarity rule (V4).  English is now repaired too, but only under
stricter rules because short English words are dangerously close to unrelated medical terms
(heat/heart, pain/paint):

* tokens shorter than 5 letters are only fixed when they are an adjacent-letter swap of a lexicon word
  ("pian" -> "pain") and are not a lexicon word themselves;
* longer tokens need a high similarity ratio AND a clear margin over the runner-up;
* repeated-letter stretching ("دووخه", "صدااع", "heeadache") is collapsed first.
"""
from __future__ import annotations

import difflib
import re

# Ordinary English words that sit one edit away from a medical term; never "repair" these.
COMMON_EN = frozenset("""paint form from heat hate hart part rate cure care pair pins ping rash? rush arm? farm warm worm word work
world wound would could should about above after again being below between both bring burn? chain chair chest? child clear close
cough? count dance death drink drive early eight every fever? field first floor focus force found front glass grade green group
happy heard heavy human large later laugh learn least leave light local lucky might money month mouth? music never night noise
north often order other paper party peace phone piece place plain plane plant point power press price quick quiet reach ready
right river round scale scene sense serve seven shape share sharp short sight skill sleep? small smell? smile smoke? sound south
space speak speed spend sport stage stand start state still stone store story study style sugar? super sweet table taste? teach
thank their there these thing think third those three throw tired? today touch tough tower track trade train treat trial truck
trust truth twice under until upper usual value video voice waste watch water wheel where which while white whole whose woman
women write wrong young""".replace("?", "").split())
_SQUEEZE = re.compile(r"(.)\1+")


def squeeze(token: str) -> str:
    return _SQUEEZE.sub(r"\1", token)


def _is_adjacent_swap(a: str, b: str) -> bool:
    if len(a) != len(b) or a == b:
        return False
    diff = [i for i in range(len(a)) if a[i] != b[i]]
    return len(diff) == 2 and diff[1] == diff[0] + 1 and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]]


def _one_edit(a: str, b: str) -> bool:
    """True when a and b differ by exactly one substitution, insertion or deletion."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(1 for x, y in zip(a, b) if x != y) == 1
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    i = 0
    while i < len(short) and short[i] == long_[i]:
        i += 1
    return short[i:] == long_[i + 1:]


def repair(normalized_query: str, lexicon, lang: str = "ar", blocked=()):
    """Return (repaired_query, [{"from","to","score"}]). ``lexicon`` is an iterable of normalized tokens."""
    lex = tuple(sorted(set(lexicon)))
    lex_set = set(lex)
    squeezed = {}
    for cand in lex:
        squeezed.setdefault(squeeze(cand), []).append(cand)
    out, corrections = [], []
    for token in normalized_query.split():
        if len(token) < 4 or token in lex_set or token.isdigit() or token in blocked or (lang == "en" and token in COMMON_EN):
            out.append(token)
            continue
        sq = squeeze(token)
        same = squeezed.get(sq)
        if same and len(same) == 1 and same[0] != token and (lang != "en" or len(token) >= 5):
            out.append(same[0])
            corrections.append({"from": token, "to": same[0], "score": 1.0})
            continue
        best = None
        if lang == "en" and len(token) < 5:
            swaps = [c for c in lex if _is_adjacent_swap(token, c)]
            if len(swaps) == 1:
                best = (0.99, swaps[0])
        else:
            scored = []
            first = token[0]
            for cand in lex:
                if not cand or cand[0] != first or abs(len(cand) - len(token)) > 2:
                    continue
                ratio = difflib.SequenceMatcher(a=token, b=cand).ratio()
                if ratio >= (0.86 if lang == "en" else 0.84):
                    scored.append((ratio, cand))
            scored.sort(reverse=True)
            if scored:
                top, cand = scored[0]
                second = scored[1][0] if len(scored) > 1 else 0.0
                need = 0.88
                if top >= need and (top - second >= 0.055 or top >= 0.96):
                    best = (top, cand)
        if best is None and lang == "en" and len(token) >= 6:
            ones = [c for c in lex if c[:1] == token[:1] and _one_edit(token, c)]
            if len(ones) == 1:
                best = (0.9, ones[0])
        if best:
            out.append(best[1])
            corrections.append({"from": token, "to": best[1], "score": round(best[0], 4)})
        else:
            out.append(token)
    return " ".join(out), corrections
