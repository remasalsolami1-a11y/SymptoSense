"""Keep the AI assistant's wording consistent with the deterministic triage (V289).

The urgency of a symptom description is decided by fixed rules (safety_engine,
then text_context). The assistant chat lets a language model write the reply,
and a model can reassure where the rules say "see a doctor soon" ("nothing to
worry about", «لا داعي لزيارة الطبيب»). This guard runs on every generated
reply before it is returned:

  * if the rules say the person should see a doctor (soon / today), sentences
    that tell them NOT to are removed, and one deterministic line with the reason
    is appended (unless the reply already advises seeing a doctor);
  * otherwise the reply is returned unchanged.

Emergencies never reach the model at all: the assistant route answers them with
the fixed emergency message first.
"""
from __future__ import annotations

import re

_DISMISSIVE = re.compile(
    r"no need (?:to|for) (?:see|seeing|visit|visiting|a) (?:a )?(?:doctor|clinic|physician)|nothing to worry about|"
    r"not (?:anything )?serious|no need to worry|you don'?t need (?:to see )?(?:a )?doctor|it will go away on its own|"
    r"لا داعي (?:لزياره|لزيارة|لمراجعه|لمراجعة|للطبيب|للقلق)|لا تحتاج (?:الى |إلى )?(?:طبيب|زياره|زيارة|مراجعه|مراجعة)|"
    r"ما يحتاج (?:طبيب|دكتور|مراجعه|مراجعة)|ليس خطير|ليست خطيره|ليست خطيرة|مو خطير|بيروح لحاله|سيزول من تلقاء نفسه",
    re.I)
_ADVISES_DOCTOR = re.compile(
    r"see a (?:doctor|gp|clinician)|visit a (?:doctor|clinic)|medical (?:review|assessment|evaluation)|consult a (?:doctor|physician)|"
    r"راجع(?:ي)? (?:ال)?طبيب|مراجعه طبيب|مراجعة طبيب|زياره الطبيب|زيارة الطبيب|تقييم طبي|استشر(?:ي)? (?:ال)?طبيب",
    re.I)
_SENTENCE = re.compile(r"[^.!?؟\n]+[.!?؟]?\s*")


def required_care(text: str, lang: str = "ar") -> tuple[str, str] | None:
    """("soon" | "today", reason) when the deterministic layers want a doctor, else None."""
    import text_context
    return text_context.triage_signal(text, lang)


def guard(answer: str, user_text: str, lang: str = "ar") -> tuple[str, bool]:
    """(answer, changed). Never weakens advice; only removes dismissive sentences and adds one line."""
    need = required_care(user_text, lang)
    if not need or not answer:
        return answer, False
    level, reason = need
    kept = [s for s in _SENTENCE.findall(answer) if not _DISMISSIVE.search(s)]
    changed = len(kept) != len(_SENTENCE.findall(answer))
    out = "".join(kept).strip()
    if changed or not _ADVISES_DOCTOR.search(out):
        when = ("اليوم" if level == "today" else "خلال يوم أو يومين") if lang != "en" else ("today" if level == "today" else "within a day or two")
        line = (f"بناءً على ما كتبته، يُنصح بمراجعة طبيب {when}: {reason}." if lang != "en"
                else f"Based on what you wrote, please see a doctor {when}: {reason}.")
        out = (out + "\n\n" + line).strip()
        changed = True
    return out, changed
