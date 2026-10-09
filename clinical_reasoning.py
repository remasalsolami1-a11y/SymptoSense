"""Clinical reasoning layer (V257): one connected picture instead of separate lists.

Inputs: the analysis result, the patient input, and (for signed-in users) what the user already saved
(medicines with start dates, recent blood tests, the previous analysis). Output (``result["reasoning"]``):

  possibilities  - each with "why it appeared" and "what lowers it"
  contributors   - medicine timing / catalog links, lab context, recurring symptom
  not_supported  - what the entered data does NOT point to
  escalate_if    - signs that should trigger immediate escalation
  missing_top2   - the two missing details most likely to change the advice
  what_changed   - differences from the previous analysis; may raise (never lower) the follow-up level one step
  next_step      - the current decision's action

Nothing here ranks causes or claims a diagnosis. Thresholds (severity rise >= 2, 21-day medicine window) are product
decisions listed in MEDICAL_REVIEW_NEEDED.md.
"""
from __future__ import annotations

import logging

import db
import decision_card
import health_file
import medication_context
import ops_metrics
import vitals

LEVEL_ORDER = ("monitor", "soon", "today", "emergency")
ANEMIA_SYMPTOMS = ("دوخة", "دوار", "تعب", "إرهاق", "ارهاق", "خفقان", "صداع", "شحوب", "dizz", "fatigue", "tired", "palpitation", "headache", "pallor")
_GAPS = ("onset", "duration", "severity", "history", "negatives", "age")
_Q = {
    "onset": ("هل بدأت الأعراض فجأة أم تدريجيًا؟", "Did it start suddenly or gradually?"),
    "duration": ("منذ متى بدأت الأعراض؟", "How long have the symptoms lasted?"),
    "severity": ("ما شدة العرض من 1 إلى 5؟", "How severe is it from 1 to 5?"),
    "history": ("هل تأخذ أدوية أو عندك أمراض مزمنة أو حساسية؟", "Do you take medicines or have chronic conditions or allergies?"),
    "negatives": ("هل ظهر معها إغماء أو ألم صدر أو ضيق نفس؟", "Has fainting, chest pain or breathlessness appeared with it?"),
    "age": ("كم عمرك؟", "How old are you?"),
}
_PRIOR = {"very_common", "common"}


def _t(ar, en, lang):
    return en if lang == "en" else ar


def _name(x, lang):
    return (x.get("name_en") if lang == "en" else x.get("name_ar")) or x.get("name_ar") or x.get("name_en") or ""


def _possibilities(matches, lang):
    out = []
    try:
        import medical_knowledge
    except ImportError:
        return out
    for m in (matches or [])[:3]:
        matched = [_name(s, lang) for s in m.get("matched_symptoms") or []]
        matched_slugs = {s.get("slug") for s in m.get("matched_symptoms") or []}
        against = [str(x) for x in (m.get("negative_evidence") or [])][:3]
        unreported = []
        try:
            ent = medical_knowledge.get_entity("disease", m.get("disease_id"), public=True) or {}
            for s in ent.get("symptoms") or []:
                if s.get("typicality") in _PRIOR and s.get("slug") not in matched_slugs:
                    unreported.append(_name(s, lang))
        except (KeyError, TypeError, ValueError) as exc:
            ops_metrics.event_error("reasoning_entity", type(exc).__name__)
        out.append({
            "name": _name(m, lang), "match_level": m.get("match_level"),
            "why": matched,
            "against": ([_t("غياب: ", "Denied: ", lang) + x for x in against]
                        + [_t("لم تذكر عرضًا شائعًا في هذا النمط: ", "Not reported, though common in this pattern: ", lang) + x for x in unreported[:2]])[:4],
        })
    return out


def _gather(d, user_id, previous, lang):
    """Saved-data context for signed-in users; any failure degrades to 'no saved data' and is counted."""
    ctx = {"meds": [], "tests": [], "labs": [], "history": [], "vit_alerts": []}
    if not user_id or not str(user_id).startswith("account-"):
        return ctx
    member = int(d.get("member_id") or 0)
    try:
        ctx["meds"] = medication_context.active_meds(user_id, member)
        ctx["tests"] = db.get_blood_tests(user_id, limit=6, member_id=member)
        ctx["labs"] = health_file.lab_trends(ctx["tests"])
        ctx["history"] = db.get_records(user_id, limit=20, member_id=member)
        ctx["vit_alerts"] = vitals.recent_alerts(user_id, member, 24, lang)
    except db.DB_ERRORS + (ValueError, TypeError) as exc:
        logging.getLogger(__name__).warning("reasoning context unavailable: %s", type(exc).__name__)
        ops_metrics.event_error("reasoning_context", type(exc).__name__)
    return ctx


def _what_changed(d, previous, ctx, lang):
    """Return (items, step_up). Only differences that were actually observed are reported.

    step_up is 1 when severity rose by >= 2 points, or when at least two independent change signals exist
    (rise in severity, a new symptom, a newly started medicine, a worse blood test). It never lowers a level.
    """
    items, signals, strong = [], 0, False
    if not previous:
        return items, 0
    try:
        sev_now, sev_prev = int(d.get("severity") or 0), int(previous.get("severity") or 0)
    except (TypeError, ValueError):
        sev_now = sev_prev = 0
    if sev_now > sev_prev:
        items.append(_t("الشدة زادت من %d/5 إلى %d/5", "Severity rose from %d/5 to %d/5", lang) % (sev_prev, sev_now))
        signals += 1
        strong = sev_now - sev_prev >= 2
    elif 0 < sev_now < sev_prev:
        items.append(_t("الشدة انخفضت من %d/5 إلى %d/5", "Severity fell from %d/5 to %d/5", lang) % (sev_prev, sev_now))
    new = [s for s in d.get("symptoms") or [] if s not in set(previous.get("symptoms") or [])]
    if new:
        items.append(_t("ظهر عرض جديد: ", "New symptom: ", lang) + "، ".join(new[:4]))
        signals += 1
    since = str(previous.get("timestamp") or "")[:10]
    for m in ctx["meds"]:
        if m["start_date"] and str(m["start_date"])[:10] > since:
            items.append(_t("بدأتَ دواءً جديدًا: ", "A new medicine was started: ", lang) + m["name"])
            signals += 1
            break
    worse = [r for r in ctx["labs"] if r.get("verdict") == "away_from_reference" and (r["latest"].get("date") or "") > since]
    if worse:
        items.append(_t("تحليل الدم الأحدث أسوأ في: ", "The newest blood test is worse in: ", lang) + "، ".join((r["name_en"] if lang == "en" else r["name_ar"]) or r["key"] for r in worse[:3]))
        signals += 1
    return items, (1 if strong or signals >= 2 else 0)


def analyze(result, d, user_id=None, previous=None, lang="ar"):
    ctx = _gather(d, user_id, previous, lang)
    symptoms = list(d.get("symptoms") or [])
    contributors = []
    meds = ctx["meds"]
    for link in medication_context.links(meds, symptoms, str(d.get("conditions") or ""), lang, symptom_days=medication_context.duration_days(d.get("duration"))):
        contributors.append({"kind": link["kind"], "text": medication_context.describe(link, lang), "basis": link["basis"]})
    hb = next((r for r in ctx["labs"] if r["key"] == "hgb"), None)
    if hb and hb["latest"]["status"] == "low" and any(w in " ".join(symptoms).lower() for w in ANEMIA_SYMPTOMS):
        tail = {"toward_reference": _t(" (يتجه نحو النطاق المرجعي مقارنة بالسابق)", " (moving toward the reference range vs previous)", lang), "away_from_reference": _t(" (يبتعد عن النطاق المرجعي مقارنة بالسابق)", " (moving away from the reference range vs previous)", lang)}.get(hb.get("verdict"), "")
        contributors.append({"kind": "lab", "basis": "lab",
                             "text": _t("الهيموغلوبين منخفض في آخر تحليل (%s)%s وقد يساهم في هذه الأعراض.", "Hemoglobin was low in the latest test (%s)%s and may contribute to these symptoms.", lang) % (hb["latest"]["date"], tail)})
    repeats = sum(1 for r in ctx["history"] if set(symptoms) & set(r.get("symptoms") or []))
    if repeats >= health_file.RECURRING_MIN:
        contributors.append({"kind": "history", "basis": "history", "text": _t("سبق أن سجّلتَ هذه الأعراض %d مرات.", "You have recorded these symptoms %d times before.", lang) % repeats})

    vit_note = None
    vit_emergency = [al for al in ctx["vit_alerts"] if al["level"] == "emergency"]
    for al in ctx["vit_alerts"][:3]:
        name = vitals.LABEL[al["kind"]][1 if lang == "en" else 0]
        contributors.append({"kind": "vitals", "basis": "vitals", "text": _t("قراءتك المنزلية لـ%s (%s) خلال آخر 24 ساعة تحتاج انتباهًا: ", "Your home reading for %s (%s) in the last 24 hours needs attention: ", lang) % (name, al["value"]) + al["message"]})
        vit_note = vit_note or _t("قراءة منزلية تحتاج انتباهًا: ", "A home reading needs attention: ", lang) + name + " " + al["value"]

    # effective emergency = every safety source merged (analysis result OR an emergency-class home reading),
    # computed once so the explanation text can never contradict the final triage level.
    emergency = bool(result.get("emergency")) or result.get("triage_level") == "emergency" or bool(vit_emergency)
    not_supported = []
    if not emergency:
        not_supported.append(_t("لا توجد في ما أدخلتَه علامات خطر تستدعي الطوارئ الآن.", "Nothing you entered points to an emergency right now.", lang))
    negs = list(d.get("negative_symptoms") or d.get("negatives") or [])
    if negs:
        not_supported.append(_t("ذكرتَ غياب: ", "You reported no: ", lang) + "، ".join(map(str, negs[:5])))

    gaps = [k for k in _GAPS if k in set(decision_card.missing_keys(d))]
    missing_top2 = [{"key": k, "question": _t(*_Q[k], lang)} for k in gaps[:2]]

    changed, step_up = _what_changed(d, previous, ctx, lang)
    if vit_note:
        changed = changed + [vit_note]
        step_up = 1
    level = result.get("triage_level")
    new_level = level
    if step_up and level in LEVEL_ORDER[:2]:
        new_level = LEVEL_ORDER[LEVEL_ORDER.index(level) + 1]
    if vit_note and level in LEVEL_ORDER[:2]:
        new_level = "today"  # an urgent home reading in the last 24h means same-day assessment at least
    if vit_emergency and level != "emergency":
        new_level = "emergency"  # the vitals tracker already classed a reading as an emergency; reasoning must never soften it
    return {
        "possibilities": _possibilities(result.get("knowledge_matches"), lang),
        "contributors": contributors,
        "not_supported": not_supported,
        "escalate_if": [] if emergency else list(decision_card._WOULD_CHANGE["en" if lang == "en" else "ar"][:3]),
        "missing_top2": missing_top2,
        "missing_note": _t("معلومتان لو عرفناهما قد تغيّران النتيجة.", "Two details that could change the result.", lang) if missing_top2 else "",
        "what_changed": {"items": changed, "level_raised_from": level if new_level != level else None, "level": new_level},
        "vitals_emergency": [_t("قراءة منزلية: %s %s (%s)", "Home reading: %s %s (%s)", lang) % (vitals.LABEL[a["kind"]][1 if lang == "en" else 0], a["value"], vitals.LABEL[a["kind"]][2]) for a in vit_emergency],
        "review_status": "pending_clinical_review",
    }, new_level
