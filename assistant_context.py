"""Opt-in personal context for the assistant (V253).

Only used when the signed-in user switched on "use my health file" for the conversation.
It sends the language model a SHORT, minimised summary: recent symptom names, the urgency
of the last analysis, current medicine names (no doses) and lab markers that were outside
range in consecutive readings. No names, e-mails, notes or free text are included.
"""
from __future__ import annotations

import health_file

MAX_CHARS = 700


def build(user_id, lang="ar", member_id=0):
    d = health_file.build(user_id, member_id, 180, lang)
    en = lang == "en"
    parts = []
    if d["symptoms"]:
        parts.append(("Recently recorded symptoms: " if en else "أعراض مسجلة مؤخرًا: ") + ("; " if en else "، ").join(s["symptom"] for s in d["symptoms"][:5]))
    if d["high_urgency_dates"]:
        parts.append("A high-priority analysis was recorded recently." if en else "سُجّل مؤخرًا تحليل عالي الأولوية.")
    if d["medicines"]:
        parts.append(("Current medicines: " if en else "أدوية حالية: ") + ("; " if en else "، ").join(str(m["name"]) for m in d["medicines"][:6] if m.get("name")))
    if d["attention_labs"]:
        parts.append(("Lab markers outside range in consecutive readings: " if en else "مؤشرات خارج النطاق في قراءات متتالية: ")
                     + ("; " if en else "، ").join(str(r["name_en"] if en else r["name_ar"]) for r in d["attention_labs"][:5]))
    return " ".join(parts)[:MAX_CHARS]


def system_addendum(context, lang="ar"):
    if not context:
        return ""
    if lang == "en":
        return (" The signed-in user chose to share this minimal summary of their own saved health data: " + context +
                " Use it only to make the answer relevant (for example, mention a possible link to a current medicine or a recurring symptom), "
                "never to diagnose, never claim a cause, and say they should ask a clinician or pharmacist about medicine questions.")
    return (" المستخدم المسجّل اختار مشاركة هذا الملخص المختصر من بياناته المحفوظة: " + context +
            " استخدمه فقط لجعل الإجابة أقرب لحالته (مثل التنبيه لاحتمال علاقة بدواء حالي أو عرض متكرر)، ولا تشخّص ولا تجزم بسبب، "
            "وقل له أن يسأل الطبيب أو الصيدلي في أسئلة الأدوية.")
