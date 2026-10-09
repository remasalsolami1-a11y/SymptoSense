"""Negation-aware clinical phrase matching shared across SymptoSense.

This module is deliberately small and deterministic.  It prevents a phrase such
as ``no chest pain`` / ``لا يوجد ألم في الصدر`` from being treated as a
positive symptom while preserving genuinely urgent phrases such as ``can't
breathe`` and ``لا أستطيع التنفس`` when those phrases themselves are matched.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from datetime import date, datetime
from typing import Iterable

_WORD = r"A-Za-z0-9_\u0600-\u06ff"
_CLAUSE_BREAK_RE = re.compile(r"[.!?;:\n\r،؛]+")
_CONTRAST_RE = re.compile(r"\b(?:لكن|ولكن|بس|الا|إلا|but|however|except|although|though)\b", re.IGNORECASE)


def parse_age_years(value, *, today: date | None = None, max_age: int = 130) -> int | None:
    """Return an integer age from either an age value or an ISO date of birth.

    Family profiles intentionally accept either an age (``48``) or a date of
    birth (``1978-04-12``).  Keeping the conversion here gives every clinical
    rule the same interpretation and prevents a DOB string from reaching
    integer database columns unchanged.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, datetime):
        born = value.date()
    elif isinstance(value, date):
        born = value
    else:
        text = str(value).strip().translate(str.maketrans(
            "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹",
            "01234567890123456789",
        ))
        if not text:
            return None
        # Accept the common user-entered variants shown by the family form,
        # while still keeping this deterministic and unambiguous.
        age_match = re.fullmatch(r"(\d{1,3})(?:\s*(?:سنه|سنة|سنوات|عام|اعوام|أعوام|years?|yrs?|yr))?", text, re.IGNORECASE)
        if age_match:
            years = int(age_match.group(1))
            return years if 0 <= years <= max_age else None
        # Numeric ages are deliberately whole years. This mirrors the existing
        # symptom flow and avoids silently truncating values such as 12.7.
        try:
            numeric = float(text)
            if numeric.is_integer():
                years = int(numeric)
                return years if 0 <= years <= max_age else None
        except (TypeError, ValueError, OverflowError):
            pass
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return None
        try:
            born = date.fromisoformat(text)
        except ValueError:
            return None

    current = today or date.today()
    if born > current:
        return None
    years = current.year - born.year - ((current.month, current.day) < (born.month, born.day))
    return years if 0 <= years <= max_age else None


def normalize_clinical_text(value: str) -> str:
    return _normalize_cached(str(value or ""))


@lru_cache(maxsize=2048)
def _normalize_cached(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).lower().replace("’", "'").replace("‘", "'")
    text = re.sub(r"[\u064b-\u065f\u0670\u0640]", "", text)
    text = text.translate(str.maketrans({"أ":"ا","إ":"ا","آ":"ا","ى":"ي","ة":"ه","ؤ":"و","ئ":"ي"}))
    text = _CLAUSE_BREAK_RE.sub(" | ", text)
    text = re.sub(r"[^a-z0-9\u0600-\u06ff\s|'-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@lru_cache(maxsize=4096)
def _phrase_pattern(phrase: str) -> re.Pattern:
    phrase_n = normalize_clinical_text(phrase).replace(" | ", " ").strip()
    # Spaces in an alias tolerate repeated whitespace, but phrase boundaries are
    # mandatory so short aliases never match inside unrelated words.
    inner = r"\s+".join(re.escape(part) for part in phrase_n.split())
    # Arabic conjunctions و / ف are commonly attached directly to the first
    # word ("وأبي أقتله", "فألم الصدر"). Treat them as optional clause
    # prefixes without weakening the actual word boundaries of the phrase.
    arabic_prefix = r"(?:[وف]\s*)?" if re.match(r"[\u0600-\u06ff]", phrase_n) else ""
    return re.compile(rf"(?<![{_WORD}]){arabic_prefix}{inner}(?![{_WORD}])", re.IGNORECASE)


_NEGATION_SUFFIXES = (
    # Arabic — all strings are normalized by normalize_clinical_text first.
    r"(?:لا\s+يوجد(?:\s+لدي)?|لا\s+يوجد\s+عندي|لا\s+اتناول|لا\s+اخذ|لا\s+استخدم|ما\s+اتناول|ما\s+اخذ|ما\s+استخدم|لا\s+اعاني\s+من|لا\s+اشعر\s+ب|لا\s+احس\s+ب|لا\s+لدي|لا\s+عندي|ما\s+عندي|ما\s+لدي|ما\s+في|مافي|ليس\s+لدي|ليست\s+لدي|بدون|دون|انفي\s+وجود|ينفي\s+وجود|ما\s+(?:عنده|عندها|عندهم|لديه|لديها|فيه|فيها|يعاني\s+من|تعاني\s+من|يشتكي\s+من|تشتكي\s+من|يحس\s+ب|تحس\s+ب)|مافيه|مافيها|ليس\s+(?:لديه|لديها|عنده|عندها)|لا\s+(?:يعاني\s+من|تعاني\s+من|يشتكي\s+من|تشتكي\s+من)|لا\s+يوجد\s+(?:عنده|عندها|لديه|لديها))\s*(?:اي\s*)?$",
    # A direct Arabic لا before the symptom: "لا ألم في الصدر".
    r"(?:^|\s)(?:لا|ولا)\s*$",
    # English.
    r"(?:no|without|deny|denies|denied|do\s+not\s+take|don't\s+take|does\s+not\s+take|doesn't\s+take|did\s+not\s+take|didn't\s+take|not\s+taking|not\s+on|do\s+not|don't|does\s+not|doesn't|did\s+not|didn't|do\s+not\s+have|don't\s+have|does\s+not\s+have|doesn't\s+have|did\s+not\s+have|didn't\s+have|not\s+experiencing|not\s+feeling|am\s+not|i'm\s+not|im\s+not|is\s+not|isn't|are\s+not|aren't|was\s+not|wasn't|were\s+not|weren't|no\s+longer|not)\s*(?:any\s*)?$",
)
_NEGATION_SUFFIX_RE = [re.compile(p, re.IGNORECASE) for p in _NEGATION_SUFFIXES]
_NEGATION_ANY_RE = re.compile(
    r"\b(?:لا يوجد|لا اتناول|لا اخذ|لا استخدم|ما اتناول|ما اخذ|ما استخدم|لا اعاني من|لا اشعر ب|لا احس ب|ما عندي|ما لدي|ليس لدي|ليست لدي|بدون|دون|انفي وجود|ينفي وجود|ما عنده|ما عندها|ما لديه|ما لديها|ما فيه|ما فيها|ما يعاني من|ما تعاني من|ليس لديه|ليس لديها|"
    r"no|without|deny|denies|denied|do not take|don't take|does not take|doesn't take|did not take|didn't take|not taking|not on|do not|don't|does not|doesn't|did not|didn't|do not have|don't have|does not have|doesn't have|did not have|didn't have|not experiencing|not feeling|no longer)\b",
    re.IGNORECASE,
)


def _prefix_clause(text_n: str, start: int) -> str:
    prefix = text_n[max(0, start - 120):start]
    if "|" in prefix:
        prefix = prefix.rsplit("|", 1)[-1]
    # A contrast word starts a new semantic clause: "no chest pain, but dizzy".
    matches = list(_CONTRAST_RE.finditer(prefix))
    if matches:
        prefix = prefix[matches[-1].end():]
    return prefix.strip()


def occurrence_is_negated(normalized_text: str, start: int) -> bool:
    prefix = _prefix_clause(normalized_text, start)
    if not prefix:
        return False
    # Keep only a compact suffix so an earlier negation about a different symptom
    # cannot leak across several words into the current phrase.
    prefix = re.sub(r"\b(?:(?:any|severe|mild|moderate|new|sudden|significant)\s*)+$", "", prefix).strip()
    suffix = " ".join(prefix.split()[-8:])
    if any(rx.search(suffix) for rx in _NEGATION_SUFFIX_RE):
        return True
    # A coordinated list shares its negation: "no fever or cough". Do not
    # carry it through punctuation, a contrast, or a new affirmative clause.
    connector = re.search(r"\b(?:or|nor|and|ولا|و)\s*$", prefix)
    if connector:
        cues = list(_NEGATION_ANY_RE.finditer(prefix[:connector.start()]))
        if cues:
            tail = prefix[cues[-1].end():connector.start()].strip()
            affirmative = re.search(r"\b(?:i|he|she|they|we|have|has|feel|feels|developed|عندي|لدي|اشعر|اعاني|ظهر)\b", tail)
            if tail and len(tail.split()) <= 8 and not affirmative:
                return True
    return False


def phrase_occurrences(text: str, phrase: str):
    text_n = normalize_clinical_text(text)
    phrase_n = normalize_clinical_text(phrase).replace(" | ", " ").strip()
    if not text_n or not phrase_n:
        return text_n, []
    rx = _phrase_pattern(phrase_n)
    return text_n, list(rx.finditer(text_n))


def contains_phrase(text: str, phrase: str) -> bool:
    _, matches = phrase_occurrences(text, phrase)
    return bool(matches)


def contains_unnegated_phrase(text: str, phrase: str) -> bool:
    text_n, matches = phrase_occurrences(text, phrase)
    return any(not occurrence_is_negated(text_n, m.start()) for m in matches)


def contains_only_negated_phrase(text: str, phrase: str) -> bool:
    text_n, matches = phrase_occurrences(text, phrase)
    return bool(matches) and all(occurrence_is_negated(text_n, m.start()) for m in matches)


def contains_unnegated_any(text: str, phrases: Iterable[str]) -> bool:
    return any(contains_unnegated_phrase(text, p) for p in phrases if p)


def has_negation_cue(text: str) -> bool:
    return bool(_NEGATION_ANY_RE.search(normalize_clinical_text(text)))
