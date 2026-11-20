"""V292 doctor card endpoint (V292.1: the text itself is built by health_file.visit_summary).

Kept as a small route module so the chat can get the bilingual summary for an assessment that is
not saved yet (guests included, with service consent). There is one summary system: health_file.
"""
from __future__ import annotations

import health_file

build = health_file.visit_summary          # backwards-compatible name
_duration_en = health_file._duration_en


def register_routes(app, *, page=None, lang_getter=None, request_allowed=None, consent_ok=None):
    from flask import jsonify, request, session

    @app.route("/api/doctor-summary", methods=["POST"])
    def api_doctor_summary():
        if request_allowed and not request_allowed("doctor_summary", 30, 60):
            return jsonify({"ok": False, "error": "rate_limited"}), 429
        if consent_ok and not consent_ok():
            return jsonify({"ok": False, "consent_required": True, "consent_url": "/consent?next=/chat"}), 403
        out = {"ok": True, **health_file.visit_summary(request.get_json(silent=True) or {})}
        if session.get("ss_user_id"):  # signed in: the saved history has a fuller one-page summary
            out["full_page"] = "/health-file?view=doctor"
        return jsonify(out)
