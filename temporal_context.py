"""Past medical history is not a current symptom (V290).

"I had a seizure as a child, now I just have a headache" used to be triaged as a
seizure emergency, and "my chest pain from last year was checked and was fine"
as a chest-pain review. This module removes clauses that describe something that
happened in the past and is over, before the symptom layers read the text.

A clause is removed only when ALL of these hold:
  * it contains a clear past-time marker ("as a child", "years ago", "last year",
    «وانا صغير», «قبل سنتين», «السنة الماضية» …);
  * it contains NO present-time or ongoing marker ("now", "today", "still",
    "since", "again", "right now", «الحين», «اليوم», «للحين», «رجع», «من» + time …);
  * the text has another clause left (the whole message is never removed).

Clauses are split only on punctuation and on "but / however / لكن / بس", never on
"now", so "history of heart disease and chest pain now" stays one clause and is
kept. Anything uncertain is kept: this layer can only lower urgency for text that
clearly talks about the past, and its effect is measured with ablation
(ENABLED = False) on every evaluation set.
"""
from __future__ import annotations

import re

ENABLED = True

_PAST = re.compile(
    r"\b(?:as a (?:child|kid|baby|teen(?:ager)?)|when i was (?:a )?(?:child|kid|young|little|small|teen(?:ager)?|baby)|"
    r"in my (?:childhood|teens|twenties)|childhood|(?:\d+|a few|few|several|many|two|three|four|five|ten) years ago|years ago|"
    r"last year|a year ago|in the past|history of|previously|used to|once as a)\b|"
    r"(?:وانا|لما كنت|يوم كنت|وهو|وهي|لما كان|لما كانت) (?:صغير|صغيره|صغيرة|طفل|طفله|طفلة|بزر|ياهل)|"
    r"(?:في|ايام) (?:طفولتي|صغري|الطفوله|الطفولة)|"
    r"قبل (?:سنه|سنة|سنتين|سنين|سنوات|\d+ (?:سنه|سنة|سنين|سنوات))|"
    r"(?:السنه|السنة|العام) (?:الماضيه|الماضية|اللي فاتت|اللي راحت|الماضي)|في الماضي|سابقا|سابقًا|"
    r"عندي تاريخ|تاريخ مرضي",
    re.I)
_PRESENT = re.compile(
    r"\b(?:now|today|tonight|this (?:morning|evening|week)|currently|right now|still|since|again|ongoing|keeps?|"
    r"came back|coming back|returned|getting worse|worse|every (?:day|night)|at the moment|at present|"
    r"is having|am having|are having|has been|have been|i'?ve got|(?:i|he|she|we|they) (?:have|has)(?! (?:a |an )?(?:history|past)))\b|"
    r"(?<!كان )(?<!كانت )(?<!كانت )\bعندي\b|(?<!كان )\bعنده\b|(?<!كانت )\bعندها\b|"
    r"الحين|الحين|الآن|الان|اليوم|الليله|الليلة|هالاسبوع|للحين|لسا|لسه|ما زال|مازال|مازالت|رجع|رجعت|رجعتلي|مره ثانيه|مرة ثانية|"
    r"من (?:يوم|يومين|امس|أمس|اسبوع|أسبوع|شهر|سنه|سنة|ساعه|ساعة)|صار لي|صار له|صار لها|يزيد|تزيد|كل يوم|هالايام|هالأيام",
    re.I)
_SPLIT = re.compile(r"[.!?؟;؛,،\n]+|\s(?:but|however|لكن|بس|ولكن)\s", re.I)


def split_clauses(text: str) -> list[str]:
    return [c.strip() for c in _SPLIT.split(str(text or "")) if c and c.strip()]


def past_clauses(text: str) -> list[str]:
    """The clauses that describe a finished past event (empty when disabled)."""
    if not ENABLED:
        return []
    clauses = split_clauses(text)
    if len(clauses) < 2:
        return []
    return [c for c in clauses if _PAST.search(c) and not _PRESENT.search(c)]


def current_text(text: str) -> str:
    """The text without past-history clauses (unchanged when nothing is removed)."""
    past = past_clauses(text)
    if not past:
        return str(text or "")
    kept = [c for c in split_clauses(text) if c not in past]
    return "، ".join(kept) if re.search(r"[؀-ۿ]", " ".join(kept)) else ", ".join(kept)


def current_patient(patient: dict) -> dict:
    """A copy of the patient dict whose symptom and note texts are current_text()."""
    if not ENABLED:
        return patient
    syms = [current_text(s) for s in (patient.get("symptoms") or [])]
    syms = [s for s in syms if s.strip()] or list(patient.get("symptoms") or [])
    notes = current_text(patient.get("notes") or "")
    if syms == list(patient.get("symptoms") or []) and notes == str(patient.get("notes") or ""):
        return patient
    out = dict(patient)
    out["symptoms"], out["notes"] = syms, notes
    return out
