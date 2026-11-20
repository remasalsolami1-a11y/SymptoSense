"""Clinical sign-off registry (V252).

``clinical_signoff.json`` lists every area of medical content and whether a named
clinician has reviewed it. Nothing is called "reviewed" unless reviewer, credentials
and date are all present, so the label users see can never overstate what was done.

V292.1 states: pending, in_review, approved, rejected, and expired (derived: an approval
older than the area's review interval). Dates in the future are rejected. Credentials
are recorded as the reviewer states them; no licence verification is claimed.

    python tools/signoff.py list
    python tools/signoff.py approve search_base --reviewer "Dr. Name" --credentials "MD, GP" --date 2026-10-20
"""
from __future__ import annotations

import json
import os
from pathlib import Path

PATH = Path(__file__).with_name("clinical_signoff.json")
_CACHE = {"mtime": None, "data": None}
_NEW_V251 = None


def load(path: Path | None = None) -> dict:
    p = Path(path or PATH)
    if path is None:
        try:
            m = p.stat().st_mtime
        except OSError:
            return {"areas": {}}
        if _CACHE["mtime"] == m and _CACHE["data"] is not None:
            return _CACHE["data"]
    data = json.loads(p.read_text(encoding="utf-8"))
    if path is None:
        _CACHE.update(mtime=p.stat().st_mtime, data=data)
    return data


# V292.1: stored statuses. "reviewed" is the pre-V292.1 spelling of "approved" and is still accepted.
# "expired" is never stored: it is an approval whose review interval has passed.
STATUSES = ("pending", "in_review", "approved", "rejected")
_APPROVED = {"approved", "reviewed"}
_NEEDS_REVIEWER = {"approved", "reviewed", "rejected"}
STATE_LABELS = {
    "pending": ("بانتظار المراجعة السريرية", "Pending clinical review"),
    "in_review": ("قيد المراجعة السريرية", "In clinical review"),
    "approved": ("معتمد سريريًا", "Clinically approved"),
    "rejected": ("لم يُعتمد في المراجعة السريرية", "Not approved in clinical review"),
    "expired": ("انتهت مدة الاعتماد", "Approval expired"),
}
# SymptoSense records what the reviewer states; it does not check licences with any authority.
CREDENTIALS_NOTE = ("المؤهلات كما ذكرها المراجِع، ولا يتحقق SymptoSense من الترخيص لدى أي جهة.",
                    "Credentials are as stated by the reviewer; SymptoSense does not verify licences with any authority.")


def _parse_date(value):
    from datetime import date
    try:
        return date.fromisoformat(str(value or "")[:10]) if len(str(value or "")) >= 10 else None
    except ValueError:
        return None


def is_reviewed(area: dict) -> bool:
    """Approved by a named clinician with credentials and a real (not future) date."""
    from datetime import date
    if area.get("status") not in _APPROVED or not all(str(area.get(k) or "").strip() for k in ("reviewer", "credentials", "date")):
        return False
    signed = _parse_date(area.get("date"))
    return signed is not None and signed <= date.today()


def state(area: dict, today=None) -> str:
    """One of pending / in_review / approved / rejected / expired (V292.1)."""
    st = area.get("status")
    if st in _APPROVED:
        if not is_reviewed(area):
            return "pending"
        return "approved" if is_current(area, today) else "expired"
    return st if st in ("in_review", "rejected") else "pending"


def review_age_days(area: dict, today=None):
    """Days since the clinician's sign-off date (None when the area was never signed off)."""
    from datetime import date
    if not is_reviewed(area):
        return None
    try:
        signed = date.fromisoformat(str(area["date"])[:10])
    except ValueError:
        return None
    return max(0, ((today or date.today()) - signed).days)


def is_current(area: dict, today=None) -> bool:
    """Reviewed by a named clinician and still within the area's review interval (V292)."""
    age = review_age_days(area, today)
    return age is not None and age <= int(area.get("review_every_days") or 365)


def area(area_id: str) -> dict:
    return dict((load().get("areas") or {}).get(area_id) or {})


def area_for(kind: str, key: str = "") -> str:
    """Map a piece of content to its sign-off area."""
    global _NEW_V251
    key = str(key or "")
    if kind == "redflag":
        return "redflag_screens"
    if kind in {"emergency", "emergency_rule"}:
        return "emergency_rules"
    if key.startswith("lab_"):
        return "lab_cards"
    if kind == "library":
        return "library_core"
    if _NEW_V251 is None:
        try:
            import health_search_expansion_v251 as x
            _NEW_V251 = set(x.EXTRA_SEARCH_KB_V251)
        except Exception:
            _NEW_V251 = set()
    if key in _NEW_V251:
        return "search_new_v251"
    try:
        import health_search
        if key in health_search.SEARCH_KB:
            return "search_base"
    except Exception:
        pass
    return "library_core"


def status_for(kind: str, key: str = "", lang: str = "ar") -> dict:
    """Public, user-facing review status for one card."""
    area_id = area_for(kind, key)
    area = (load().get("areas") or {}).get(area_id) or {}
    ar = lang != "en"
    st = state(area)
    if st == "approved":
        label = ("راجعه %s (%s) بتاريخ %s" if ar else "Reviewed by %s (%s) on %s") % (area["reviewer"], area["credentials"], area["date"])
        return {"area": area_id, "state": st, "reviewed": True, "label": label, "credentials_note": CREDENTIALS_NOTE[0 if ar else 1]}
    if st == "in_review":
        return {"area": area_id, "state": st, "reviewed": False,
                "label": "قيد المراجعة السريرية ولم يُعتمد بعد — مبني على مصادر موثوقة معروضة أسفله" if ar else
                         "In clinical review, not yet approved — based on the trusted sources listed below"}
    if st == "rejected":
        return {"area": area_id, "state": st, "reviewed": False,
                "label": "لم يُعتمد في المراجعة السريرية ويجري تصحيحه — راجع المصادر المعروضة أسفله" if ar else
                         "Not approved in clinical review and being corrected — see the sources listed below"}
    if st == "expired":
        return {"area": area_id, "state": st, "reviewed": False, "expired": True,
                "label": ("انتهت مدة المراجعة السريرية (آخر مراجعة %s) — بانتظار مراجعة جديدة" if ar else
                          "Clinical review has lapsed (last reviewed %s) — awaiting a new review") % area["date"]}
    return {"area": area_id, "state": "pending", "reviewed": False,
            "label": "محتوى لم يُراجع سريريًا بعد — مبني على مصادر موثوقة معروضة أسفله" if ar else
                     "Not yet clinically reviewed — based on the trusted sources listed below"}


def show_badge() -> bool:
    return os.environ.get("SYMPTOSENSE_SHOW_REVIEW_STATUS", "1").strip().lower() not in {"0", "false", "no", "off"}


def summary() -> dict:
    areas = load().get("areas") or {}
    out = []
    for aid, a in areas.items():
        st = state(a)
        out.append({"id": aid, "title_ar": a.get("title_ar"), "title_en": a.get("title_en"), "state": st,
                    "state_ar": STATE_LABELS[st][0], "state_en": STATE_LABELS[st][1],
                    "reviewed": st == "approved", "expired": st == "expired",
                    "organization": a.get("organization") if st != "pending" else None, "scope": a.get("scope") or None,
                    "reviewer": a.get("reviewer") if is_reviewed(a) else None, "date": a.get("date") if is_reviewed(a) else None,
                    "review_every_days": int(a.get("review_every_days") or 365), "history_count": len(a.get("history") or [])})
    by_state = {k: sum(1 for x in out if x["state"] == k) for k in STATE_LABELS}
    return {"areas": out, "reviewed": by_state["approved"], "total": len(out), "by_state": by_state,
            "credentials_note_ar": CREDENTIALS_NOTE[0], "credentials_note_en": CREDENTIALS_NOTE[1]}


def validate(data: dict, today=None) -> list[str]:
    """Problems that make the registry untrustworthy (used by tests and tools/signoff.py)."""
    from datetime import date
    today = today or date.today()
    problems = []
    for aid, a in (data.get("areas") or {}).items():
        st = a.get("status")
        if st not in set(STATUSES) | _APPROVED:
            problems.append(f"{aid}: bad status {st!r}")
        if st in _NEEDS_REVIEWER:
            missing = [k for k in ("reviewer", "credentials", "date") if not str(a.get(k) or "").strip()]
            if missing:
                problems.append(f"{aid}: marked {st} but missing {', '.join(missing)}")
        elif st == "in_review":
            if not str(a.get("reviewer") or "").strip():
                problems.append(f"{aid}: in_review needs the reviewer's name")
        elif any(a.get(k) for k in ("reviewer", "credentials", "date", "organization")):
            problems.append(f"{aid}: reviewer details present while status is pending")
        if a.get("date"):
            d = _parse_date(a.get("date"))
            if d is None:
                problems.append(f"{aid}: date must be YYYY-MM-DD")
            elif d > today:
                problems.append(f"{aid}: date {a.get('date')} is in the future")
        for k in ("title_ar", "title_en"):
            if not a.get(k):
                problems.append(f"{aid}: missing {k}")
        every = a.get("review_every_days", 365)
        if not isinstance(every, int) or not 30 <= every <= 1095:
            problems.append(f"{aid}: review_every_days must be a whole number of days between 30 and 1095")
        hist = a.get("history", [])
        if not isinstance(hist, list):
            problems.append(f"{aid}: history must be a list")
        else:
            for i, h in enumerate(hist):
                hd = _parse_date((h or {}).get("date")) if (h or {}).get("date") else None
                if hd is not None and hd > today:
                    problems.append(f"{aid}: history[{i}] date is in the future")
    return problems


def annotate(result: dict, lang: str = "ar") -> dict:
    """Attach a ``review`` status to a search result and its matched topics."""
    if not isinstance(result, dict) or not show_badge():
        return result
    kind = "library"
    result["review"] = status_for(kind, result.get("key"), lang)
    for t in result.get("matched_topics") or []:
        if isinstance(t, dict):
            t["review"] = status_for(kind, t.get("key"), lang)
    return result


def register(app):
    from flask import jsonify

    @app.route("/api/clinical-signoff", methods=["GET"])
    def api_clinical_signoff():
        return jsonify({"ok": True, **summary()})
    return api_clinical_signoff
