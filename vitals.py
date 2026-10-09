"""Home Vitals Tracker (V257): a real log of blood pressure, glucose, temperature, pulse and SpO2.

Readings are validated (implausible values are rejected as typos), stored per user/member, shown over time and
checked against alert thresholds. The alert thresholds below are PRODUCT DEFAULTS pending clinical sign-off
(clinical_signoff area ``vitals_thresholds``); they only decide the wording of the notice ("ok / attention / urgent /
emergency") and never state a diagnosis. Glucose is stored in mg/dL; mmol/L input is converted (x 18.016).
"""
from __future__ import annotations

import html as _html
from datetime import datetime, timezone

import db

MMOL_TO_MGDL = 18.016
KINDS = ("bp", "glucose", "temp", "pulse", "spo2")
LABEL = {"bp": ("ضغط الدم", "Blood pressure", "mmHg"), "glucose": ("السكر", "Blood glucose", "mg/dL"),
         "temp": ("الحرارة", "Temperature", "°C"), "pulse": ("النبض", "Pulse", "bpm"), "spo2": ("الأكسجين SpO₂", "SpO₂", "%")}
GLUCOSE_CONTEXTS = ("fasting", "after_meal", "random")
# Plausibility bounds (reject typos); not clinical limits.
BOUNDS = {"bp": ((60, 260), (30, 160)), "glucose": ((20, 800), None), "temp": ((33, 43), None), "pulse": ((20, 250), None), "spo2": ((50, 100), None)}

_EMERG_AR = "اتصل بالإسعاف 997 أو توجّه لأقرب طوارئ الآن."
_EMERG_EN = "Call 997 or go to the nearest emergency department now."


def _msg(ar, en, lang):
    return en if lang == "en" else ar


def validate(kind, v1, v2=None, context=""):
    """Return (ok, v1, v2, context, error_code). Numbers are coerced; out-of-range values are rejected."""
    if kind not in KINDS:
        return False, None, None, "", "invalid_kind"
    try:
        a = float(v1)
        b = None if v2 in (None, "") else float(v2)
    except (TypeError, ValueError):
        return False, None, None, "", "invalid_number"
    (lo, hi), second = BOUNDS[kind]
    if not (lo <= a <= hi):
        return False, None, None, "", "out_of_range"
    if kind == "bp":
        if b is None or not (second[0] <= b <= second[1]) or b >= a:
            return False, None, None, "", "out_of_range"
    elif b is not None:
        return False, None, None, "", "unexpected_second_value"
    ctx = context if (kind == "glucose" and context in GLUCOSE_CONTEXTS) else ""
    return True, a, b, ctx, ""


def assess(kind, v1, v2=None, context="", lang="ar"):
    """{'level': ok|attention|urgent|emergency, 'message': str}. Thresholds: product defaults pending sign-off."""
    level, ar, en = "ok", "ضمن النطاق المعتاد.", "Within the usual range."
    if kind == "bp":
        s, dia = v1, v2
        if s >= 180 or dia >= 120:
            level, ar, en = "urgent", "قراءة ضغط مرتفعة جدًا؛ أعد القياس بعد دقائق من الراحة، وإن بقيت كذلك فاطلب تقييمًا طبيًا اليوم، وإن صاحبها ألم صدر أو ضيق نفس أو ضعف مفاجئ فاتصل بالإسعاف.", "Very high reading; re-measure after resting a few minutes, seek medical assessment today if it stays high, and call emergency services if chest pain, breathlessness or sudden weakness appears."
        elif s < 90 or dia < 60:
            level, ar, en = "attention", "قراءة منخفضة؛ اجلس أو استلقِ واشرب سوائل، وراجع طبيبًا إن تكررت أو صاحبتها دوخة شديدة أو إغماء.", "Low reading; sit or lie down and drink fluids, and see a clinician if it repeats or comes with severe dizziness or fainting."
        elif s >= 140 or dia >= 90:
            level, ar, en = "attention", "قراءة أعلى من المعتاد؛ كرّر القياس في أوقات مختلفة وأخبر طبيبك إن تكررت.", "Above the usual range; repeat at different times and tell your doctor if it recurs."
    elif kind == "glucose":
        g = v1
        if g < 54:
            level, ar, en = "emergency", "سكر منخفض جدًا. إن كنت واعيًا تناول سكرًا سريع المفعول فورًا، وإن ظهر تشوش أو إغماء فاتصل بالإسعاف 997.", "Very low glucose. If you are alert take fast-acting sugar now; if confusion or fainting occurs call 997."
        elif g < 70:
            level, ar, en = "attention", "سكر منخفض؛ تناول سكرًا سريع المفعول وأعد القياس بعد 15 دقيقة، وأخبر طبيبك إن تكرر.", "Low glucose; take fast-acting sugar, re-check in 15 minutes and tell your doctor if it recurs."
        elif g > 300:
            level, ar, en = "urgent", "سكر مرتفع جدًا؛ اطلب تقييمًا طبيًا اليوم، وإن صاحبه قيء أو عطش شديد أو نفَس سريع فاذهب للطوارئ.", "Very high glucose; seek medical assessment today, and go to emergency if vomiting, extreme thirst or fast breathing occurs."
        elif (context == "fasting" and g >= 126) or (context in ("after_meal", "random") and g >= 200):
            level, ar, en = "attention", "قراءة أعلى من المعتاد؛ أخبر طبيبك وكرّر القياس.", "Above the usual range; tell your doctor and repeat the measurement."
    elif kind == "temp":
        t = v1
        if t >= 40 or t < 35:
            level, ar, en = "urgent", "حرارة شديدة الارتفاع أو الانخفاض؛ اطلب تقييمًا طبيًا اليوم.", "Very high or low temperature; seek medical assessment today."
        elif t >= 38:
            level, ar, en = "attention", "حمى؛ اشرب سوائل وارتح، وراجع طبيبًا إن استمرت أكثر من 3 أيام أو ظهرت علامات خطر.", "Fever; drink fluids and rest, and see a clinician if it lasts more than 3 days or warning signs appear."
    elif kind == "pulse":
        p = v1
        if p > 130 or p < 40:
            level, ar, en = "urgent", "نبض بعيد جدًا عن المعتاد؛ أعد القياس وهو جالس، وإن صاحبه ألم صدر أو إغماء أو ضيق نفس فاتصل بالإسعاف.", "Pulse far from usual; re-measure seated, and call emergency services if chest pain, fainting or breathlessness comes with it."
        elif p > 100 or p < 50:
            level, ar, en = "attention", "نبض خارج المعتاد أثناء الراحة؛ أعد القياس بعد راحة 5 دقائق وأخبر طبيبك إن تكرر.", "Resting pulse outside the usual range; re-measure after 5 minutes of rest and tell your doctor if it recurs."
    elif kind == "spo2":
        o = v1
        if o < 90:
            level, ar, en = "emergency", "نسبة أكسجين منخفضة جدًا. " + _EMERG_AR, "Very low oxygen. " + _EMERG_EN
        elif o < 95:
            level, ar, en = "urgent", "نسبة أكسجين أقل من المعتاد؛ أعد القياس بيد دافئة وبدون طلاء أظافر، واطلب تقييمًا طبيًا اليوم، وإن صاحبها ضيق نفس فاتصل بالإسعاف.", "Oxygen lower than usual; re-measure with a warm hand and no nail polish, seek medical assessment today, and call emergency services if breathless."
    return {"level": level, "message": _msg(ar, en, lang)}


def fmt(kind, v1, v2=None):
    if kind == "bp":
        return "%d/%d" % (round(v1), round(v2 or 0))
    return ("%.1f" % v1) if kind == "temp" else ("%d" % round(v1))


def latest_by_kind(rows):
    seen, out = set(), []
    for r in rows:  # newest first
        if r["kind"] not in seen:
            seen.add(r["kind"])
            out.append(r)
    return out


def latest_rows(user_id, member_id=0, lang="ar"):
    """Latest reading per kind as structured rows (so pages can isolate numbers from Arabic text)."""
    try:
        rows = db.get_vitals(user_id, member_id, days=30)
    except db.DB_ERRORS:
        return []
    out = []
    for r in latest_by_kind(rows):
        a = assess(r["kind"], r["v1"], r["v2"], r["context"], lang)
        ar, en, unit = LABEL[r["kind"]]
        out.append({"name": en if lang == "en" else ar, "value": fmt(r["kind"], r["v1"], r["v2"]), "unit": unit,
                    "date": r["measured_at"][:10], "level": a["level"]})
    return out


def summary_lines(user_id, member_id=0, lang="ar"):
    iso = (lambda x: "\u2066%s\u2069" % x) if lang != "en" else str
    return ["%s: %s (%s)%s" % (r["name"], iso("%s %s" % (r["value"], r["unit"])), iso(r["date"]), "" if r["level"] == "ok" else (" ⚠️" if r["level"] != "emergency" else " 🚨"))
            for r in latest_rows(user_id, member_id, lang)]


def recent_alerts(user_id, member_id=0, hours=24, lang="ar"):
    """Readings from the last ``hours`` whose level is urgent/emergency (used by the reasoning layer)."""
    try:
        rows = db.get_vitals(user_id, member_id, days=2)
    except db.DB_ERRORS:
        return []
    now = datetime.now(timezone.utc)
    out = []
    for r in rows:
        try:
            when = datetime.fromisoformat(r["measured_at"].replace("Z", "+00:00"))
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if (now - when).total_seconds() > hours * 3600:
            continue
        a = assess(r["kind"], r["v1"], r["v2"], r["context"], lang)
        if a["level"] in ("urgent", "emergency"):
            out.append({"kind": r["kind"], "level": a["level"], "value": fmt(r["kind"], r["v1"], r["v2"]), "message": a["message"]})
    return out


_LEVEL_ICON = {"ok": "✅", "attention": "⚠️", "urgent": "🟠", "emergency": "🚨"}


def render(rows, lang="ar"):
    ar = lang != "en"
    e = lambda x: _html.escape(str(x if x is not None else ""), quote=True)
    kind_opts = "".join('<option value="%s">%s</option>' % (k, e(LABEL[k][0] if ar else LABEL[k][1])) for k in KINDS)
    parts = ['<main class="container" style="max-width:860px;padding-top:24px;padding-bottom:60px"><div class="ss-stack">',
             '<section class="ss-card"><span class="ss-badge">🩺 %s</span><h1 style="margin:8px 0 4px">%s</h1><p class="ss-muted">%s</p></section>' % (
                 "قياسات منزلية" if ar else "Home vitals", "سجل القياسات المنزلية" if ar else "Home vitals log",
                 e("سجّل قياساتك لتظهر في ملفك الصحي وملخص الطبيب. التنبيهات إرشادية وليست تشخيصًا." if ar else "Log readings so they appear in your health file and doctor summary. Alerts are guidance, not a diagnosis."))]
    parts.append(
        '<section class="ss-card"><h2 style="margin-top:0">%s</h2>'
        '<form id="vitalsForm" style="display:grid;gap:10px;grid-template-columns:1fr;align-items:end">'
        '<label style="display:block">%s<select id="vKind" required style="min-height:44px;width:100%%">%s</select></label>'
        '<label>%s<input id="vV1" type="number" step="any" inputmode="decimal" required style="min-height:44px;width:100%%"></label>'
        '<label id="vV2Wrap" hidden>%s<input id="vV2" type="number" step="any" inputmode="decimal" style="min-height:44px;width:100%%"></label>'
        '<label id="vUnitWrap" hidden>%s<select id="vUnit" style="min-height:44px;width:100%%"><option value="mgdl">mg/dL</option><option value="mmol">mmol/L</option></select></label>'
        '<label id="vCtxWrap" hidden>%s<select id="vCtx" style="min-height:44px;width:100%%"><option value="fasting">%s</option><option value="after_meal">%s</option><option value="random">%s</option></select></label>'
        '<button type="submit" style="min-height:48px;border:0;border-radius:12px;background:#1565c0;color:#fff;font-weight:700;font-size:16px;cursor:pointer">%s</button></form>'
        '<p id="vMsg" role="status" hidden></p><script src="/static/js/vitals.js" defer></script></section>' % (
            "إضافة قياس" if ar else "Add a reading", "النوع" if ar else "Type", kind_opts, "القيمة (الانقباضي للضغط)" if ar else "Value (systolic for BP)",
            "الانبساطي" if ar else "Diastolic", "الوحدة" if ar else "Unit", "حالة القياس" if ar else "Context",
            "صائم" if ar else "Fasting", "بعد الأكل" if ar else "After a meal", "عشوائي" if ar else "Random", "حفظ" if ar else "Save"))
    if not rows:
        parts.append('<section class="ss-card"><p class="ss-muted" style="text-align:center">%s</p></section>' % e("لا توجد قياسات بعد." if ar else "No readings yet."))
    for k in KINDS:
        krows = [r for r in rows if r["kind"] == k]
        if not krows:
            continue
        a = assess(k, krows[0]["v1"], krows[0]["v2"], krows[0]["context"], "ar" if ar else "en")
        name = LABEL[k][0] if ar else LABEL[k][1]
        lines = "".join('<li style="display:flex;align-items:center;gap:10px;justify-content:space-between"><span><bdi dir="ltr"><b>%s %s</b></bdi> <bdi dir="ltr" class="ss-muted">%s</bdi></span> <button type="button" data-del="%d" aria-label="%s" style="min-height:44px;min-width:44px;border:1px solid #cbd5e1;background:#fff;border-radius:10px;cursor:pointer">✕</button></li>' % (
            e(fmt(k, r["v1"], r["v2"])), e(LABEL[k][2]), e(r["measured_at"][:16].replace("T", " ")), r["id"], e("حذف" if ar else "Delete")) for r in krows[:8])
        spark = ""
        try:
            import health_file
            spark = health_file._spark([{"value": r["v1"]} for r in reversed(krows[:20])])
        except (ImportError, AttributeError):
            spark = ""
        parts.append('<section class="ss-card"><h2 style="margin-top:0">%s %s</h2><p style="margin:4px 0"><b><bdi dir="ltr">%s %s</bdi></b>%s%s</p>'
                     '<p%s>%s %s</p><ul style="list-style:none;padding:0;margin:8px 0 0">%s</ul></section>' % (
                         e(name), spark, e(fmt(k, krows[0]["v1"], krows[0]["v2"])), e(LABEL[k][2]), "", "",
                         ' role="alert"' if a["level"] in ("urgent", "emergency") else "", _LEVEL_ICON[a["level"]], e(a["message"]), lines))
    parts.append("</div></main>")
    return "".join(parts)


def register(app, login_required, api_login_required, data_user_id, page, lang_fn, mk_error):
    from flask import jsonify, request

    def _member():
        try:
            return max(0, int(request.args.get("member") or 0))
        except (TypeError, ValueError):
            return None

    @app.route("/api/vitals", methods=["GET"])
    @api_login_required
    def api_vitals_list():
        try:
            db.init_db()
            member = _member()
            kind = request.args.get("kind") or None
            if member is None or (kind and kind not in KINDS):
                return jsonify({"ok": False, "error": "invalid_query"}), 400
            rows = db.get_vitals(data_user_id(), member, kind)
            lang = lang_fn()
            for r in rows:
                r["alert"] = assess(r["kind"], r["v1"], r["v2"], r["context"], lang)
            return jsonify({"ok": True, "rows": rows})
        except db.DB_ERRORS + (ValueError, TypeError) as exc:
            return mk_error(exc, 500)

    @app.route("/api/vitals", methods=["POST"])
    @api_login_required
    def api_vitals_add():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"ok": False, "error": "invalid_json_object"}), 400
        v1, v2 = data.get("v1"), data.get("v2")
        if data.get("kind") == "glucose" and data.get("unit") == "mmol":
            try:
                v1 = float(v1) * MMOL_TO_MGDL
            except (TypeError, ValueError):
                return jsonify({"ok": False, "error": "invalid_number"}), 400
        ok, a, b, ctx, err = validate(data.get("kind"), v1, v2, str(data.get("context") or ""))
        if not ok:
            return jsonify({"ok": False, "error": err}), 400
        try:
            db.init_db()
            try:
                member = max(0, int(data.get("member_id") or 0))
            except (TypeError, ValueError):
                return jsonify({"ok": False, "error": "invalid_member"}), 400
            db.save_vital(data_user_id(), member, data["kind"], a, b, ctx)
            return jsonify({"ok": True, "alert": assess(data["kind"], a, b, ctx, lang_fn())})
        except db.DB_ERRORS + (ValueError, TypeError) as exc:
            return mk_error(exc, 500)

    @app.route("/api/vitals/<int:vital_id>", methods=["DELETE"])
    @api_login_required
    def api_vitals_delete(vital_id):
        try:
            db.init_db()
            if not db.delete_vital(data_user_id(), vital_id):
                return jsonify({"ok": False, "error": "not_found"}), 404
            return jsonify({"ok": True})
        except db.DB_ERRORS + (ValueError, TypeError) as exc:
            return mk_error(exc, 500)

    @app.route("/vitals", methods=["GET"])
    @login_required
    def vitals_page():
        db.init_db()
        lang = lang_fn()
        member = _member() or 0
        rows = db.get_vitals(data_user_id(), member, days=180)
        return page("القياسات المنزلية" if lang != "en" else "Home vitals", render(rows, lang))
