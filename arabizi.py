"""Arabizi (Arabic typed in Latin letters and digits) -> Arabic script, for the red-flag
concept layer only (V285).

Many Saudi users type "9dri y3awrni" for «صدري يعورني». Arabizi has no standard spelling:
short vowels are optional, and one Latin letter can stand for several Arabic letters
(9 = ص or ض, d = د / ذ / ض …). So a token is not transliterated letter by letter;
instead the candidate spellings are generated and the first one that is a word the
concept layer knows is chosen (lexicon-guided). Tokens with no known candidate get a
plain default spelling and then go through the normal one-letter typo correction.

Scope and safety:
  * A token is treated as Arabizi only if it mixes Latin letters with the digits Arabizi
    uses for Arabic letters (2 3 5 6 7 8 9), e.g. "y3awrni", and is not a quantity
    such as "3rd", "5mg" or "24h". Plain Latin words in the same message ("nfsi") are
    converted only when the message already contains such a token AND the word maps to
    a known Arabic word AND it is not a known English word — so English text is left
    untouched.
  * Used only by red_flag_concepts, which can only ADD emergency flags.
"""
from __future__ import annotations

import itertools
import re
from functools import lru_cache

_TOKEN = re.compile(r"[A-Za-z0-9']+")
_DIGITS = set("2356789")
_QUANTITY = re.compile(r"^\d+(st|nd|rd|th|mg|mcg|ml|kg|g|h|hr|hrs|x|cm|mm|am|pm|min|mins|day|days|wk|wks|week|weeks|yo|y|s)?$")

# Frequent function words with an agreed spelling.
_FIXED = {
    "w": "و", "wa": "و", "ma": "ما", "la": "لا", "mo": "مو", "mu": "مو", "mb": "مب", "mn": "من", "min": "من",
    "3la": "على", "3ala": "على", "fi": "في", "fe": "في", "b3d": "بعد", "ba3d": "بعد", "al": "ال", "el": "ال",
    "3ndi": "عندي", "3indi": "عندي", "3nda": "عنده", "3ndha": "عندها", "shwy": "شوي", "shwai": "شوي", "shway": "شوي",
    "wayed": "وايد", "wayd": "وايد", "waid": "وايد", "kthir": "كثير", "ktheer": "كثير", "katheer": "كثير",
    "mra": "مره", "mara": "مره", "marra": "مره", "mrra": "مره", "gwi": "قوي", "gawi": "قوي", "qwi": "قوي",
    "9ar": "صار", "9art": "صرت", "fj2a": "فجاه", "faj2a": "فجاه", "fja2a": "فجاه", "bs": "بس", "bas": "بس",
    "ana": "انا", "a7s": "احس", "a7is": "احس", "akthr": "اكثر", "aktar": "اكثر", "akthar": "اكثر",
}

# Latin unit -> alternative Arabic letters, most frequent first. Two-character units first.
_UNITS = (
    ("sh", ("ش",)), ("kh", ("خ",)), ("gh", ("غ",)), ("th", ("ث", "ذ")), ("dh", ("ذ", "ض", "ظ")),
    ("3'", ("غ",)), ("9'", ("ض",)), ("6'", ("ظ",)), ("7'", ("خ",)),
    ("aa", ("ا",)), ("ee", ("ي",)), ("ii", ("ي",)), ("oo", ("و",)), ("ou", ("و",)),
    ("2", ("ء", "ا")), ("3", ("ع",)), ("5", ("خ",)), ("6", ("ط", "ظ")), ("7", ("ح",)), ("8", ("ق", "غ")), ("9", ("ص", "ض")),
    ("b", ("ب",)), ("p", ("ب",)), ("t", ("ت", "ط")), ("j", ("ج",)), ("g", ("ق", "ج", "غ")), ("q", ("ق",)), ("d", ("د", "ذ", "ض")),
    ("r", ("ر",)), ("z", ("ز", "ظ", "ذ")), ("s", ("س", "ص")), ("f", ("ف",)), ("v", ("ف",)), ("k", ("ك",)), ("c", ("ك",)),
    ("l", ("ل",)), ("m", ("م",)), ("n", ("ن",)), ("h", ("ه", "ح")), ("w", ("و",)), ("y", ("ي",)), ("x", ("كس",)),
    ("'", ("ء", "")),
)
_MAX_CANDIDATES = 4096
ENABLED = True  # switched off only by the evaluator's ablation


def _vowel(ch: str, pos: int, last: bool) -> tuple[str, ...]:
    if pos == 0:
        return ("ا",)
    if ch == "a":
        return ("ه", "ا", "") if last else ("", "ا")
    if ch in "ie":
        return ("ي", "") if last or ch == "i" else ("", "ي")
    return ("و", "")  # o / u


def _slots(token: str) -> list[tuple[str, ...]]:
    out, i = [], 0
    while i < len(token):
        last_index = len(token) - 1
        if token[i] in "aeiou" and token[i:i + 2] not in ("aa", "ee", "ii", "oo", "ou"):
            out.append(_vowel(token[i], i, i == last_index))
            i += 1
            continue
        for unit, letters in _UNITS:
            if token.startswith(unit, i):
                if unit in ("aa", "ee", "ii", "oo", "ou") and i == 0:
                    letters = ("ا",) if unit == "aa" else ("ا" + letters[0],)
                out.append(letters)
                i += len(unit)
                break
        else:
            i += 1  # unknown character: skip
    return out


@lru_cache(maxsize=1)
def _text_context_words() -> frozenset[str]:
    """V289: duration / severity words too, so "mn thlath ayam" becomes «من ثلاث ايام»."""
    import text_context
    return text_context.known_words()


def is_arabizi(token: str) -> bool:
    t = token.lower()
    return (bool(re.search(r"[a-z]", t)) and any(ch in _DIGITS for ch in t)
            and not _QUANTITY.match(t) and _TOKEN.fullmatch(t) is not None)


@lru_cache(maxsize=4096)
def _convert(token: str, lexicon_only: bool) -> str | None:
    """Arabic spelling for one Latin token; None if lexicon_only and no known word fits."""
    import red_flag_concepts as rfc

    t = token.lower()
    if t in _FIXED:
        return _FIXED[t]
    slots = _slots(t)
    if not slots:
        return None
    known = rfc.known_words() | _text_context_words()
    total = 1
    for s in slots:
        total *= len(s)
    if total <= _MAX_CANDIDATES:
        # second pass: an omitted initial alef/hamza ("ntf5at" = انتفخت, "stfrg" = استفرغ)
        for prefix in ("", "ا") if slots[0] != ("ا",) else ("",):
            for combo in itertools.product(*slots):
                word = prefix + "".join(combo)
                if word in known:
                    return word
    if lexicon_only:
        return None
    return "".join(s[0] for s in slots)


def convert_tokens(text: str) -> list[tuple[int, int, str]]:
    """[(start, end, arabic)] for every Latin token in `text` that should be read as Arabizi."""
    import red_flag_concepts as rfc

    if not ENABLED:
        return []
    tokens = list(_TOKEN.finditer(str(text or "")))
    if not any(is_arabizi(m.group()) for m in tokens):
        return []
    english = rfc.english_words()
    out = []
    for m in tokens:
        tok = m.group()
        if is_arabizi(tok):
            ar = _convert(tok, False)
        elif tok.lower() in english or tok.isdigit():
            continue
        else:
            ar = _convert(tok, True)
        if ar:
            out.append((m.start(), m.end(), ar))
    return out


def to_arabic(text: str) -> str:
    """`text` with its Arabizi tokens replaced by Arabic script (other text unchanged)."""
    text = str(text or "")
    out, pos = [], 0
    for start, end, ar in convert_tokens(text):
        out.append(text[pos:start])
        out.append(ar)
        pos = end
    out.append(text[pos:])
    return "".join(out)
