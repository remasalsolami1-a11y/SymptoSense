"""One clear decision per result (V253): monitor at home / book an appointment / see someone today / emergency.

``analysis_core`` already computes ``triage_level`` (emergency | today | soon | monitor) from
deterministic rules. This module only presents it in four unmistakable states and explains
the *uncertainty*: which pieces of information were missing and what would change the advice.
No new medical judgement is made here.
"""
from __future__ import annotations

LEVELS = ("emergency", "today", "soon", "monitor")

_TEXT = {
    "emergency": {"icon": "🚨", "ar": ("طوارئ — اتصل الآن", "اتصل بالإسعاف 997 أو توجّه لأقرب طوارئ فورًا. لا تنتظر نتيجة إضافية."),
                  "en": ("Emergency — call now", "Call 997 or go to the nearest emergency department immediately. Do not wait for more results."),
                  "window_ar": "الآن", "window_en": "Now"},
    "today": {"icon": "🟠", "ar": ("راجع طبيبًا اليوم", "رتّب تقييمًا طبيًا خلال اليوم (طوارئ أو عيادة اليوم نفسه). ولا تؤجّله إذا ساءت الأعراض."),
              "en": ("See a clinician today", "Arrange a medical assessment today (same-day clinic or emergency). Do not delay if symptoms worsen."),
              "window_ar": "خلال اليوم", "window_en": "Today"},
    "soon": {"icon": "🟡", "ar": ("احجز موعدًا قريبًا", "احجز موعدًا مع طبيب في الأيام القادمة، وراقب الأعراض حتى ذلك الوقت."),
             "en": ("Book an appointment soon", "Book an appointment with a doctor in the coming days and keep monitoring until then."),
             "window_ar": "خلال الأيام القادمة", "window_en": "In the coming days"},
    "monitor": {"icon": "🟢", "ar": ("راقب في المنزل", "لا تظهر علامة خطر واضحة من المعلومات المدخلة. اتبع خطة الرعاية وراقب الأعراض."),
                "en": ("Monitor at home", "No clear warning sign from the information you entered. Follow the care plan and keep watching your symptoms."),
                "window_ar": "مراقبة مع شروط", "window_en": "Monitor with safeguards"},
}

_WOULD_CHANGE = {
    "ar": ["ظهور ألم صدر أو صعوبة تنفس أو إغماء أو ضعف مفاجئ في جانب من الجسم", "ارتفاع شديد أو مستمر في الحرارة", "تفاقم الأعراض أو عدم تحسنها خلال المدة المتوقعة",
           "ظهور عرض جديد غير معتاد"],
    "en": ["Chest pain, trouble breathing, fainting or sudden one-sided weakness", "A very high or persistent fever", "Symptoms getting worse or not improving as expected",
           "A new, unusual symptom"],
}

_MISSING = [
    ("duration", "مدة الأعراض", "How long the symptoms have lasted"),
    ("severity", "شدة العرض", "How severe it is"),
    ("age", "العمر", "Age"),
    ("onset", "هل بدأ فجأة أم تدريجيًا", "Whether it started suddenly or gradually"),
    ("history", "الأدوية والأمراض المزمنة والحساسية", "Medicines, chronic conditions and allergies"),
    ("negatives", "الأعراض المصاحبة التي لا تعاني منها", "Related symptoms you do NOT have"),
]


def _present(d, key):
    if key == "history":
        return bool(d.get("history_answered") or str(d.get("conditions") or "").strip() or str(d.get("medications") or "").strip())
    if key == "negatives":
        return bool(d.get("negative_symptoms") or d.get("negatives"))
    return str(d.get(key) if d.get(key) is not None else "").strip() not in {"", "None", "0"}


def missing_keys(d):
    return [key for key, _ar, _en in _MISSING if not _present(d, key)]


def missing_information(d, lang="ar"):
    en = lang == "en"
    return [(en_ if en else ar) for key, ar, en_ in _MISSING if not _present(d, key)]


def build(result, d, lang="ar"):
    """``result`` is the dict returned by run_analysis, ``d`` the patient input."""
    en = lang == "en"
    level = result.get("triage_level")
    if level not in LEVELS:
        level = "emergency" if result.get("emergency") else ("soon" if result.get("urgency") == "medium" else "monitor")
    if result.get("emergency"):
        level = "emergency"
    t = _TEXT[level]
    headline, action = t["en"] if en else t["ar"]
    missing = missing_information(d or {}, lang)
    conf = str(result.get("confidence") or "medium")
    reasons = []
    if result.get("low_confidence") or conf == "low":
        reasons.append("Confidence is limited" if en else "الثقة بالنتيجة محدودة")
    if missing:
        reasons.append(("%d useful details were not provided" if en else "%d معلومات مفيدة لم تُدخل") % len(missing))
    if result.get("assessment_status") in {"insufficient", "low_confidence"}:
        reasons.append("Not enough information to show reliable possibilities" if en else "المعلومات لا تكفي لعرض احتمالات موثوقة")
    return {
        "level": level, "icon": t["icon"], "headline": headline, "action": action,
        "window": t["window_en"] if en else t["window_ar"],
        "why": result.get("triage_reason") or "",
        "would_change": list(_WOULD_CHANGE["en" if en else "ar"]) if level != "emergency" else [],
        "uncertainty": {"confidence": conf, "reasons": reasons, "missing": missing,
                        "tip": ("Adding the missing details can make the advice more precise." if en else "إضافة المعلومات الناقصة تجعل التوصية أدق.") if missing else ""},
    }
