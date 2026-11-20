"""Clinical sign-off registry (V252).

``clinical_signoff.json`` lists every area of medical content and whether a named
clinician has reviewed it. Nothing is called "reviewed" unless reviewer, credentials
and date are all present, so the label users see can never overstate what was done.

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


def is_reviewed(area: dict) -> bool:
    return area.get("status") == "reviewed" and all(str(area.get(k) or "").strip() for k in ("reviewer", "credentials", "date"))


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
    if is_reviewed(area):
        label = ("راجعه %s (%s) بتاريخ %s" if ar else "Reviewed by %s (%s) on %s") % (area["reviewer"], area["credentials"], area["date"])
        return {"area": area_id, "reviewed": True, "label": label}
    return {"area": area_id, "reviewed": False,
            "label": "محتوى لم يُراجع سريريًا بعد — مبني على مصادر موثوقة معروضة أسفله" if ar else
                     "Not yet clinically reviewed — based on the trusted sources listed below"}


def show_badge() -> bool:
    return os.environ.get("SYMPTOSENSE_SHOW_REVIEW_STATUS", "1").strip().lower() not in {"0", "false", "no", "off"}


def summary() -> dict:
    areas = load().get("areas") or {}
    out = []
    for aid, a in areas.items():
        out.append({"id": aid, "title_ar": a.get("title_ar"), "title_en": a.get("title_en"), "reviewed": is_reviewed(a),
                    "reviewer": a.get("reviewer") if is_reviewed(a) else None, "date": a.get("date") if is_reviewed(a) else None})
    return {"areas": out, "reviewed": sum(1 for x in out if x["reviewed"]), "total": len(out)}


def validate(data: dict) -> list[str]:
    """Problems that make the registry untrustworthy (used by tests and tools/signoff.py)."""
    problems = []
    for aid, a in (data.get("areas") or {}).items():
        if a.get("status") not in {"pending", "reviewed"}:
            problems.append(f"{aid}: bad status {a.get('status')!r}")
        if a.get("status") == "reviewed":
            missing = [k for k in ("reviewer", "credentials", "date") if not str(a.get(k) or "").strip()]
            if missing:
                problems.append(f"{aid}: marked reviewed but missing {', '.join(missing)}")
        elif any(a.get(k) for k in ("reviewer", "credentials", "date")):
            problems.append(f"{aid}: reviewer details present while status is pending")
        for k in ("title_ar", "title_en"):
            if not a.get(k):
                problems.append(f"{aid}: missing {k}")
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
