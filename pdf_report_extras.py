"""Formatting-only helpers for the symptom-analysis PDF.

Nothing here computes or changes medical results: it only formats fields that
already exist in the displayed analysis (risk reasons, the user's follow-up
answers) and sanitises the optional follow-up list sent by the browser.
"""
from __future__ import annotations

import html as _html

DISCLAIMER_AR = "هذا ملخص للمعلومات المقدمة من المستخدم، ولا يمثل تشخيصًا طبيًا أو تقريرًا صادرًا عن طبيب."
DISCLAIMER_EN = "This is a summary of the information provided by the user. It is not a medical diagnosis or a report issued by a physician."

_EXTRA_KEYS = ("why_result", "risk_reasons", "followup_answers")


def _text(value, limit=300):
    return " ".join(str(value or "").split())[:limit]


def risk_reason_lines(result):
    lines = []
    why = _text(result.get("why_result"), 600)
    if why:
        lines.append(why)
    reasons = result.get("risk_reasons")
    if isinstance(reasons, list):
        for item in reasons[:8]:
            if isinstance(item, dict):
                txt = _text(item.get("message") or item.get("description") or item.get("name"))
            else:
                txt = _text(item)
            if txt and txt not in lines:
                lines.append(txt)
    return lines


def followup_pairs(result):
    out = []
    items = result.get("followup_answers")
    if isinstance(items, list):
        for item in items[:20]:
            if isinstance(item, dict):
                name = _text(item.get("name"), 120)
                answer = str(item.get("answer") or "").lower()
                if name and answer in ("yes", "no"):
                    out.append((name, answer))
    return out


def sections(result, ar):
    """HTML cards inserted after the summary card (empty string when no data)."""
    esc = lambda v: _html.escape(str(v))
    parts = []
    lines = risk_reason_lines(result)
    if lines:
        parts.append('<div class="card"><h2>%s</h2><ul>%s</ul></div>' % (
            esc("سبب مستوى الخطورة" if ar else "Why this risk level"),
            "".join("<li>%s</li>" % esc(x) for x in lines)))
    pairs = followup_pairs(result)
    if pairs:
        yes, no = ("نعم", "لا") if ar else ("Yes", "No")
        parts.append('<div class="card"><h2>%s</h2><ul>%s</ul></div>' % (
            esc("إجابات أسئلة المتابعة" if ar else "Follow-up answers"),
            "".join("<li>%s: <b>%s</b></li>" % (esc(n), esc(yes if a == "yes" else no)) for n, a in pairs)))
    return "".join(parts)


def prepare_export(raw, allowed):
    """Whitelist the client-supplied result and sanitise the follow-up list."""
    out = {key: raw.get(key) for key in set(allowed) | set(_EXTRA_KEYS[:2]) if key in raw}
    pairs = followup_pairs(raw)
    if pairs:
        out["followup_answers"] = [{"name": n, "answer": a} for n, a in pairs]
    return out
