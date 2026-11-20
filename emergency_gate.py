"""Red-flag notice for every free-text entry point (V253).

The symptom flow stops the analysis on a red flag. Other pages that accept free
text (health search, medicine lookup, blood-test notes) are not diagnoses, so they
must not be replaced by an emergency screen; instead the JSON response gets a
``safety_notice`` and ``static/js/safety-notice.js`` shows a call-now banner above
the page. The check is the same deterministic ``safety_engine`` used everywhere.
Educational questions ("what causes chest pain?") do not trigger it.
"""
from __future__ import annotations

import json

import ops_metrics
import safety_engine

# path -> (method, where to read text from)
WATCHED = {
    "/api/search": ("GET", ("q",)),
    "/api/drug": ("GET", ("name",)),
    "/api/meds": ("POST", ("text",)),
    "/api/blood": ("POST", None),   # any short form field (notes / context)
}


def _lang(raw):
    return "en" if str(raw or "").lower().startswith("en") else "ar"


def notice(text, lang="ar"):
    text = str(text or "").strip()[:1500]
    if not text:
        return None
    res = safety_engine.evaluate({"symptoms": [], "notes": text}, lang=lang)
    if not res.get("emergency"):
        return None
    em = safety_engine.emergency_result(res, lang=lang)
    self_harm = "self_harm_risk" in (res.get("rule_ids") or [])
    return {"rule_ids": list(res.get("rule_ids") or []), "flags": list(res.get("flags") or [])[:4],
            "message": em.get("when_to_seek_care"), "number": "937" if self_harm else "997",
            "category": "selfharm" if self_harm else "general"}


def _collect_text(rule):
    from flask import request
    method, fields = rule
    if method == "GET":
        return " ".join(str(request.args.get(f) or "") for f in fields)
    if fields is None:                                   # multipart form (blood upload)
        return " ".join(str(v) for v in request.form.values() if 3 <= len(str(v)) <= 1500)
    data = request.get_json(silent=True) or {}
    return " ".join(str(data.get(f) or "") for f in fields) if isinstance(data, dict) else ""


def register(app):
    from flask import request

    @app.after_request
    def attach_safety_notice(response):
        try:
            rule = WATCHED.get(request.path)
            if not rule or request.method != rule[0] or response.status_code != 200 or not response.is_json:
                return response
            n = notice(_collect_text(rule), _lang(request.args.get("lang") or request.cookies.get("lang")))
            if not n:
                return response
            body = response.get_json(silent=True)
            if isinstance(body, dict):
                body["safety_notice"] = n
                response.set_data(json.dumps(body, ensure_ascii=False))
                ops_metrics.incr("safety_notice_shown")
        except Exception as exc:     # never break the page, but never hide it either
            ops_metrics.event_error("safety_notice_failure", type(exc).__name__)
            app.logger.error("safety notice could not be attached", exc_info=True)
        return response
    return attach_safety_notice
