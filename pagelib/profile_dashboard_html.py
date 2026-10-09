"""HTML for the personal health dashboard ("My profile").

Pure rendering: it receives a ``ProfileDashboardData`` (see services/profile_dashboard_service.py) and returns markup.
It never reads a database or another subsystem, and it has no medical wording: every sentence here is descriptive
("latest CBC - 3 Oct") or administrative ("a follow-up is due"). Nothing is derived from a medical value.
"""
from __future__ import annotations

from datetime import date
from html import escape

MONTHS = {
    "ar": ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"],
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
}

T = {
    "ar": {
        "title": "ملفي", "hello": "مرحبًا", "edit": "تعديل الملف", "edit_small": "تعديل", "not_added": "غير مضاف",
        "age": "العمر", "gender": "الجنس", "years": "سنة", "profile_updated": "آخر تحديث للملف الصحي",
        "never_updated": "لم يُحدَّث بعد",
        "missing": "ينقص ملفك", "missing_cta": "إضافة",
        "f_dob": "تاريخ الميلاد", "f_gender": "الجنس", "f_allergies": "الحساسية", "f_health_conditions": "الحالات الصحية",
        "f_medications": "الأدوية الحالية",
        "g_male": "ذكر", "g_female": "أنثى", "g_other": "آخر", "g_prefer_not_to_say": "أفضّل ألا أذكر",
        "alerts": "تنبيهات تحتاج انتباه",
        "a_followup_pending": "يمكنك تحديث حالتك الآن.",
        "a_no_active_medications": "لا توجد أدوية مفعلة حاليًا.",
        "a_followup_pending_cta": "تحديث الحالة", "a_no_active_medications_cta": "إدارة الأدوية",
        "now": "حالتي الآن", "now_hint": "آخر ما سجّلته في SymptoSense، بالتواريخ فقط.",
        "k_symptom_analysis": "آخر تحليل أعراض", "k_cbc": "آخر CBC", "k_vital": "آخر قراءة حيوية", "k_followup": "آخر متابعة",
        "none_yet": "لا يوجد بعد", "open": "عرض", "start": "ابدأ",
        "now_empty": "ستظهر هنا آخر تحليلاتك وقراءاتك بعد أن تستخدم أدوات الموقع.",
        "quick": "اختصارات سريعة", "q_edit_profile": "تحديث الملف الصحي", "q_add_vital": "إضافة قراءة حيوية",
        "q_medications": "إدارة الأدوية", "q_doctor_summary": "تجهيز ملخص للطبيب",
        "meds": "الأدوية", "meds_active": "مفعّلة", "meds_none": "لا توجد أدوية مسجلة", "meds_manage": "إدارة الأدوية",
        "meds_note": "قائمة الأدوية تُدار من قسم الأدوية فقط.",
        "privacy": "الخصوصية", "p_analysis": "تحليل الأعراض",
        "p_assistant": "المساعد", "p_optional": "المشاركة الاختيارية",
        "on": "مفعّل", "off": "متوقف", "p_review": "إعدادات الموافقة تحتاج مراجعتك.",
        "p_center": "مركز الخصوصية الكامل",
        "basics": "معلوماتي الأساسية", "b_height": "الطول", "b_weight": "الوزن", "cm": "سم", "kg": "كجم",
        "degraded": "تعذّر تحميل بعض الأقسام مؤقتًا. أعد تحميل الصفحة بعد قليل.",
        "optional_note": "معلوماتك الصحية اختيارية، ولا يمنعك نقصها من استخدام الموقع.",
        "d_symptom_analysis": "تحليل الأعراض", "d_cbc": "تحليل الدم", "d_vital": "القراءات الحيوية", "d_followup": "المتابعة",
    },
    "en": {
        "title": "My Profile", "hello": "Welcome", "edit": "Edit profile", "edit_small": "Edit", "not_added": "Not added",
        "age": "Age", "gender": "Gender", "years": "years", "profile_updated": "Health profile last updated",
        "never_updated": "Not updated yet",
        "missing": "Your profile is missing", "missing_cta": "Add",
        "f_dob": "Date of birth", "f_gender": "Gender", "f_allergies": "Allergies", "f_health_conditions": "Health conditions",
        "f_medications": "Current medications",
        "g_male": "Male", "g_female": "Female", "g_other": "Other", "g_prefer_not_to_say": "Prefer not to say",
        "alerts": "Worth a look",
        "a_followup_pending": "You can update how you are doing now.",
        "a_no_active_medications": "There are no active medications right now.",
        "a_followup_pending_cta": "Update status", "a_no_active_medications_cta": "Manage medications",
        "now": "My status now", "now_hint": "What you last recorded in SymptoSense, dates only.",
        "k_symptom_analysis": "Latest symptom analysis", "k_cbc": "Latest CBC", "k_vital": "Latest vital reading",
        "k_followup": "Latest follow-up",
        "none_yet": "None yet", "open": "View", "start": "Start",
        "now_empty": "Your latest analyses and readings will appear here once you use the tools.",
        "quick": "Quick actions", "q_edit_profile": "Update health profile", "q_add_vital": "Add a vital reading",
        "q_medications": "Manage medications", "q_doctor_summary": "Prepare a clinician summary",
        "meds": "Medications", "meds_active": "active", "meds_none": "No medications recorded", "meds_manage": "Manage medications",
        "meds_note": "Your medication list is managed only in the Medications section.",
        "privacy": "Privacy", "p_analysis": "Symptom analysis",
        "p_assistant": "Assistant", "p_optional": "Optional sharing",
        "on": "On", "off": "Off", "p_review": "Your consent settings need your review.",
        "p_center": "Full privacy center",
        "basics": "My basic information", "b_height": "Height", "b_weight": "Weight", "cm": "cm", "kg": "kg",
        "degraded": "Some sections could not be loaded right now. Please reload in a moment.",
        "optional_note": "Your health information is optional, and missing details never stop you from using the site.",
        "d_symptom_analysis": "Symptom analysis", "d_cbc": "Blood test", "d_vital": "Vital readings", "d_followup": "Follow-up",
    },
}

ICON = {"symptom_analysis": "🩺", "cbc": "🩸", "vital": "❤️", "followup": "🔁"}
QUICK_ICON = {"edit_profile": "📝", "add_vital": "➕", "medications": "💊", "doctor_summary": "📄"}
STYLE = """<style>
.pd{max-width:860px;margin:0 auto;display:grid;gap:14px}
.pd section{background:#fff;border:1px solid var(--v2-line,#DCE9F4);border-radius:20px;padding:clamp(16px,3vw,22px);box-shadow:var(--v2-shadow,0 8px 24px rgba(31,86,127,.06))}
.pd h1{margin:0;font-size:clamp(22px,4vw,28px);color:#0F2F63}.pd h2{margin:0 0 4px;font-size:18px;color:#0F2F63}
.pd .sub{margin:0 0 12px;color:#475569;font-size:14px}
.pd-id{display:flex;gap:14px;align-items:center;flex-wrap:wrap}.pd-av{width:56px;height:56px;border-radius:50%;background:#EAF4FF;display:grid;place-items:center;font-size:28px}
.pd-id-main{flex:1;min-width:200px}.pd-meta{display:flex;flex-wrap:wrap;gap:6px 16px;margin-top:6px;color:#334155;font-size:14px}
.pd-meta b{color:#0F2F63}.pd-na{color:#64748B}
.pd .btn,.pd a.btn{display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:0 16px;border-radius:12px;text-decoration:none;font-weight:700}
.pd-missing{display:flex;gap:10px;align-items:center;flex-wrap:wrap;background:#F4F9FE}.pd-missing p{margin:0;flex:1;min-width:200px;color:#0F2F63;font-size:15px}
.pd-note{font-size:13px;color:#475569;margin:6px 0 0}
.pd-alert{display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:10px 0;border-top:1px solid #EDF2F6}.pd-alert:first-of-type{border-top:0}.pd-alert p{margin:0;flex:1;min-width:200px;font-size:15px;color:#0F2F63}
.pd-now{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.pd-card{display:flex;flex-direction:column;gap:6px;border:1px solid #E3EDF6;border-radius:16px;padding:14px;background:#FBFDFF}
.pd-card .k{font-weight:800;color:#0F2F63;font-size:14px}.pd-card .d{font-size:18px;font-weight:800;color:#12365F}.pd-card .d.na{color:#64748B;font-weight:600;font-size:15px}
.pd-card a{margin-top:auto;font-weight:700;color:#1b66a3;text-decoration:none;min-height:44px;display:inline-flex;align-items:center}
.pd-quick{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.pd-quick a{flex-direction:column;gap:4px;min-height:76px;background:#EAF4FF;color:#0F2F63;border:1px solid #DCEBFA;text-align:center;padding:10px}
.pd-quick a span{font-size:22px}
.pd-kv{display:grid;grid-template-columns:1fr auto;gap:8px 12px;align-items:center;font-size:15px}.pd-kv .v{font-weight:700;color:#0F2F63}
.pd-pills{display:flex;flex-wrap:wrap;gap:8px}.pd-pill{display:inline-flex;gap:6px;align-items:center;border:1px solid #E3EDF6;border-radius:999px;padding:6px 12px;font-size:14px;background:#FBFDFF;color:#0F2F63}.pd-pill b{font-weight:800}
.pd-on b{color:#166534}.pd-off b{color:#475569}
.pd-actions{margin-top:12px;display:flex;gap:10px;flex-wrap:wrap}
.pd-ghost{background:#fff;border:1px solid #DCEBFA;color:#0F2F63}
@media (min-width:700px){.pd-now{grid-template-columns:repeat(4,minmax(0,1fr))}.pd-quick{grid-template-columns:repeat(4,minmax(0,1fr))}}
@media (prefers-color-scheme:dark){.pd section{background:#1E293B;border-color:#334155}.pd h1,.pd h2,.pd-card .k,.pd-card .d,.pd-meta b,.pd-kv .v,.pd-alert p,.pd-missing p{color:#E2E8F0}.pd-card{background:#0F172A;border-color:#334155}.pd-missing{background:#0F172A}.pd .sub,.pd-meta,.pd-note,.pd-na,.pd-off,.pd-card .d.na{color:#CBD5E1}.pd-quick a,.pd-ghost{background:#0F172A;color:#E2E8F0;border-color:#334155}.pd-card a{color:#7DB8F0}.pd-on b{color:#86EFAC}.pd-pill{background:#0F172A;border-color:#334155;color:#E2E8F0}}
</style>"""


def _fmt_date(iso: str, lang: str, today: date) -> str:
    try:
        d = date.fromisoformat(iso)
    except (TypeError, ValueError):
        return ""
    months = MONTHS["en" if lang == "en" else "ar"]
    year = "" if d.year == today.year else " %d" % d.year
    return ("%s %d%s" % (months[d.month - 1], d.day, year)) if lang == "en" else ("%d %s%s" % (d.day, months[d.month - 1], year))


def _e(value) -> str:
    return escape(str(value), quote=True)


def render(data, lang: str = "ar", today: date | None = None) -> str:
    lang = "en" if lang == "en" else "ar"
    t = T[lang]
    today = today or date.today()
    ident = data.identity
    na = '<span class="pd-na">%s</span>' % _e(t["not_added"])

    gender = t.get("g_" + ident.gender) if ident.gender else None
    age = ("%d %s" % (ident.age, t["years"])) if ident.age is not None else None
    updated = _fmt_date(ident.updated_at, lang, today) if ident.updated_at else t["never_updated"]
    edit_url = data.quick_actions[0].url if data.quick_actions else "/manage"

    out = ['<main class="pd" dir="%s">' % ("rtl" if lang == "ar" else "ltr")]
    out.append(
        '<section class="pd-id"><div class="pd-av" aria-hidden="true">👤</div><div class="pd-id-main">'
        '<p class="sub" style="margin:0">%s</p><h1>%s</h1><div class="pd-meta"><span>%s: <b>%s</b></span><span>%s: <b>%s</b></span>'
        '<span>%s: <b>%s</b></span></div></div><a class="btn" href="%s">✏️ %s</a></section>' % (
            _e(t["hello"]), _e(ident.name or t["title"]), _e(t["age"]), _e(age) if age else na, _e(t["gender"]),
            _e(gender) if gender else na, _e(t["profile_updated"]), _e(updated), _e(edit_url), _e(t["edit"])))

    if data.missing_fields:
        names = "، " if lang == "ar" else ", "
        listed = names.join(_e(t["f_" + k]) for k in data.missing_fields)
        out.append('<section class="pd-missing"><p>%s: <b>%s</b></p><a class="btn pd-ghost" href="%s">%s</a></section>' % (
            _e(t["missing"]), listed, _e(edit_url), _e(t["missing_cta"])))

    shown_alerts = [a for a in data.alerts if a.code != "profile_basics_missing"]   # already shown as the line above
    if shown_alerts:
        rows = "".join('<div class="pd-alert"><p>%s</p><a class="btn pd-ghost" href="%s">%s</a></div>' % (
            _e(t["a_" + a.code]), _e(a.url), _e(t["a_" + a.code + "_cta"])) for a in shown_alerts)
        out.append('<section aria-label="%s"><h2>%s</h2>%s</section>' % (_e(t["alerts"]), _e(t["alerts"]), rows))

    items = [("symptom_analysis", data.latest_symptom_analysis, "/chat"), ("cbc", data.latest_cbc, "/blood"),
             ("vital", data.latest_vital, "/vitals"), ("followup", data.latest_followup, "/history")]
    cards = []
    for kind, item, start_url in items:
        if item:
            when = '<div class="d">%s</div>' % _e(_fmt_date(item.date, lang, today))
            link = '<a href="%s">%s ›</a>' % (_e(item.url), _e(t["open"]))
        else:
            when = '<div class="d na">%s</div>' % _e(t["none_yet"])
            link = ('<a href="%s">%s ›</a>' % (_e(start_url), _e(t["start"]))) if kind != "followup" else ""
        cards.append('<div class="pd-card"><div class="k">%s %s</div>%s%s</div>' % (ICON[kind], _e(t["k_" + kind]), when, link))
    empty_hint = "" if data.has_any_activity() else '<p class="pd-note">%s</p>' % _e(t["now_empty"])
    out.append('<section><h2>%s</h2><p class="sub">%s</p><div class="pd-now">%s</div>%s</section>' % (
        _e(t["now"]), _e(t["now_hint"]), "".join(cards), empty_hint))

    quick = "".join('<a class="btn" href="%s"><span aria-hidden="true">%s</span>%s</a>' % (
        _e(a.url), QUICK_ICON.get(a.key, "•"), _e(t["q_" + a.key])) for a in data.quick_actions)
    out.append('<section><h2>%s</h2><div class="pd-quick">%s</div></section>' % (_e(t["quick"]), quick))

    m = data.medications
    meds_line = ("%d %s" % (m.active_count, t["meds_active"])) if m.total_count else t["meds_none"]
    out.append('<section><h2>💊 %s</h2><div class="pd-kv"><span>%s</span><span class="v">%s</span></div><p class="pd-note">%s</p>'
               '<div class="pd-actions"><a class="btn pd-ghost" href="%s">%s</a></div></section>' % (
                   _e(t["meds"]), _e(t["meds"]), _e(meds_line), _e(t["meds_note"]), _e(m.url), _e(t["meds_manage"])))

    p = data.privacy_summary

    def pill(label, flag):
        return '<span class="pd-pill %s"><span>%s</span><b>%s</b></span>' % ("pd-on" if flag else "pd-off", _e(label), _e(t["on"] if flag else t["off"]))
    review = '<p class="pd-note">%s</p>' % _e(t["p_review"]) if p.needs_review else ""
    out.append('<section><h2>🔐 %s</h2><div class="pd-pills">%s%s%s</div>%s'
               '<div class="pd-actions"><a class="btn pd-ghost" href="%s">%s</a></div></section>' % (
                   _e(t["privacy"]), pill(t["p_analysis"], p.use_in_analysis), pill(t["p_assistant"], p.use_in_assistant),
                   pill(t["p_optional"], p.analytics_research or p.research_participation), review, _e(p.url), _e(t["p_center"])))

    def val(text, suffix=""):
        return ('<span class="v">%s %s</span>' % (_e(text), _e(suffix))) if text else '<span class="v pd-na">%s</span>' % _e(t["not_added"])
    dob_text = _fmt_date(ident.dob, lang, date(1900, 1, 1)) if ident.dob else ""
    out.append('<section><h2>👤 %s</h2><div class="pd-kv"><span>%s</span>%s<span>%s</span>%s<span>%s</span>%s<span>%s</span>%s</div>'
               '<div class="pd-actions"><a class="btn pd-ghost" href="%s">%s</a></div></section>' % (
                   _e(t["basics"]), _e(t["f_dob"]), val(dob_text), _e(t["gender"]), val(gender), _e(t["b_height"]),
                   val(ident.height_cm, t["cm"]), _e(t["b_weight"]), val(ident.weight_kg, t["kg"]), _e(edit_url), _e(t["edit_small"])))

    if data.degraded:
        out.append('<p class="pd-note" role="status">%s</p>' % _e(t["degraded"]))
    out.append('<p class="pd-note">%s</p></main>' % _e(t["optional_note"]))
    return STYLE + "".join(out)
