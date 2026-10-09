"""Smart follow-up (V253): "did it improve? did a new warning sign appear?".

Deterministic. An analysis becomes *due* for follow-up after ``MIN_AGE_H`` hours and stays
due for ``MAX_AGE_D`` days, until the user answers once. A "worse" answer or a new warning
sign never produces reassurance: it returns the same-day-care message.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import db

# Follow-up window by the urgency of the analysis being followed up: (hours before asking, days it stays open).
# A product decision, pending clinical review (see MEDICAL_REVIEW_NEEDED.md).
POLICY = {"high": (6, 3), "medium": (24, 7), "low": (48, 14)}
DEFAULT_POLICY = POLICY["medium"]


def window(record):
    """(min_hours, max_days) for one analysis record."""
    return POLICY.get(str(record.get("urgency") or "").lower(), DEFAULT_POLICY)

_MSG = {
    "better": {"ar": "الحمد لله على التحسن. استمر على الراحة والمراقبة، وراجع طبيبًا إذا رجعت الأعراض أو ظهر شيء جديد.",
               "en": "Glad it is improving. Keep resting and monitoring, and see a clinician if it comes back or something new appears.",
               "level": "monitor"},
    "same": {"ar": "إذا لم تتحسن الأعراض بعد يوم أو يومين من الرعاية المنزلية فالأفضل حجز موعد مع طبيب قريبًا.",
             "en": "If symptoms have not improved after a day or two of home care, book an appointment with a doctor soon.",
             "level": "soon"},
    "worse": {"ar": "تفاقم الأعراض سبب كافٍ لمراجعة طبيب اليوم. إذا ظهر ألم صدر أو صعوبة تنفس أو إغماء أو ضعف مفاجئ فاتصل بالإسعاف 997 فورًا.",
              "en": "Worsening symptoms are a reason to see a clinician today. If chest pain, trouble breathing, fainting or sudden weakness appears, call 997 immediately.",
              "level": "today"},
    "new_sign": {"ar": "ظهور علامة جديدة يستدعي تقييمًا طبيًا اليوم. وإذا كانت العلامة ألم صدر أو صعوبة تنفس أو إغماء أو ضعفًا مفاجئًا فاتصل بالإسعاف 997 فورًا.",
                 "en": "A new warning sign needs a medical assessment today. If it is chest pain, trouble breathing, fainting or sudden weakness, call 997 immediately.",
                 "level": "today"},
}


def _parse(ts):
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def due(records, followups, now=None):
    """The newest analysis inside its own follow-up window that has no answer yet, else None."""
    now = now or datetime.now(timezone.utc)
    answered = {f["record_id"] for f in followups}
    for r in records:  # newest first
        when = _parse(r.get("timestamp"))
        if when is None or r.get("id") in answered:
            continue
        min_h, max_d = window(r)
        age = now - when
        if timedelta(hours=min_h) <= age <= timedelta(days=max_d):
            return {"record_id": r["id"], "date": when.date().isoformat(), "symptoms": list(r.get("symptoms") or [])[:4],
                    "urgency": str(r.get("urgency") or ""), "ask_after_hours": min_h, "closes_after_days": max_d}
    return None


def reply(outcome, new_sign, lang="ar"):
    key = "new_sign" if new_sign else outcome
    m = _MSG[key]
    return {"level": m["level"], "message": m["en" if lang == "en" else "ar"]}


def register(app, api_login_required, data_user_id, lang_fn, mk_error):
    from flask import jsonify, request

    @app.route("/api/followup/status", methods=["GET"])
    @api_login_required
    def api_followup_due():
        try:
            db.init_db()
            uid = data_user_id()
            return jsonify({"ok": True, "due": due(db.get_records(uid, limit=20), db.get_followups(uid))})
        except Exception as exc:
            return mk_error(exc, 500)

    @app.route("/api/followup/answer", methods=["POST"])
    @api_login_required
    def api_followup_answer():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"ok": False, "error": "invalid_json_object"}), 400
        outcome = str(data.get("outcome") or "")
        try:
            record_id = int(data.get("record_id"))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "invalid_record_id"}), 400
        try:
            outcome, new_sign = db.normalize_followup(outcome, data.get("new_sign"))
        except ValueError:
            return jsonify({"ok": False, "error": "invalid_outcome"}), 400
        try:
            db.init_db()
            if not db.save_followup(data_user_id(), record_id, outcome, new_sign):
                return jsonify({"ok": False, "error": "not_found"}), 404
            out = reply(outcome, new_sign, lang_fn())
            return jsonify({"ok": True, **out})
        except Exception as exc:
            return mk_error(exc, 500)
