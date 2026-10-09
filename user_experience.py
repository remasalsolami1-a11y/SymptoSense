"""User-facing follow-up utilities for SymptoSense.

These endpoints record only user-observed patterns. They never infer treatment
effectiveness and are scoped to the authenticated user's own analysis records.
"""
from __future__ import annotations

import re
from flask import Blueprint, jsonify, request

import db

_ALLOWED_RELIEF_FACTORS = {"rest", "fluids", "food", "position", "sleep", "medication", "other"}


def _symptom_key(record: dict) -> str:
    symptoms = record.get("symptoms") or []
    raw = str(symptoms[0] if symptoms else "general").strip().lower()
    raw = re.sub(r"\s+", " ", raw)
    # Keep Arabic/Latin words and numbers; strip emoji/punctuation so the same
    # symptom remains grouped even if display decoration changes.
    cleaned = re.sub(r"[^\w\u0600-\u06ff ]+", "", raw, flags=re.UNICODE).strip()
    return (cleaned or "general")[:120]


def register(app, current_user_id, data_user_id_getter, consent_ok, consent_required_json):
    if "user_experience" in app.blueprints:
        return
    bp = Blueprint("user_experience", __name__)

    @bp.route("/api/relief-log", methods=["GET", "POST"])
    def relief_log():
        uid = current_user_id()
        if not uid:
            return jsonify({"ok": True, "logged_in": False, "stored": False, "summary": []})
        if not consent_ok():
            if request.method == "POST":
                return consent_required_json("/chat")
            return jsonify({"ok": True, "logged_in": True, "stored": False, "summary": [], "reason": "consent_required"})
        db.init_db()
        user_key = data_user_id_getter()
        if request.method == "GET":
            try:
                record_id = int(request.args.get("record_id") or 0)
            except (TypeError, ValueError):
                return jsonify({"ok": False, "error": "invalid_record_id"}), 400
            if record_id <= 0:
                return jsonify({"ok": True, "logged_in": True, "stored": False, "summary": []})
            owned = db.get_record_owned(user_key, record_id)
            if not owned:
                return jsonify({"ok": False, "error": "not_found"}), 404
            key = _symptom_key(owned)
            return jsonify({"ok": True, "logged_in": True, "stored": True, "symptom_key": key, "summary": db.get_symptom_relief_summary(user_key, key)})

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"ok": False, "error": "invalid_json_object"}), 400
        try:
            record_id = int(data.get("record_id") or 0)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "invalid_record_id"}), 400
        factor = str(data.get("factor") or "").strip().lower()
        if factor not in _ALLOWED_RELIEF_FACTORS:
            return jsonify({"ok": False, "error": "invalid_factor"}), 400
        owned = db.get_record_owned(user_key, record_id)
        if not owned:
            return jsonify({"ok": False, "error": "not_found"}), 404
        key = _symptom_key(owned)
        db.save_symptom_relief_log(user_key, record_id, key, factor)
        return jsonify({
            "ok": True,
            "logged_in": True,
            "stored": True,
            "symptom_key": key,
            "summary": db.get_symptom_relief_summary(user_key, key),
            "causality_note": "observation_only",
        })

    app.register_blueprint(bp)
