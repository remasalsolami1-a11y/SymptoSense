"""
analysis_core.py - مشترك بين البوت والموقع: محرك تحليل الأعراض.
نفس المنطق (نفس الـ prompt ونفس استدعاء Groq ونفس الفحوصات) لأي واجهة.
"""
import os
import re
import json
from datetime import datetime, timezone, timedelta

from groq import Groq

import db
import ml_diagnosis
import medication_warnings

_ARABIC_RE = re.compile("[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]+")
_NON_ARABIC_LETTERS_RE = re.compile(
    "["
    "A-Za-z"
    "\u00C0-\u024F"
    "\u1E00-\u1EFF"
    "\u0590-\u05FF"
    "\u0400-\u04FF"
    "\u4e00-\u9fff"
    "\u3040-\u30ff"
    "\uac00-\ud7af"
    "\u3400-\u4dbf"
    "\uff00-\uffef"
    "]+"
)


def _html_escape(text):
    if not text:
        return text
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _normalize_symptoms(symptoms):
    """Strips emojis/punctuation so symptoms match the ML model's vocabulary."""
    out = []
    for s in symptoms or []:
        clean = re.sub(r"[^\u0600-\u06FF\sA-Za-z]", "", str(s)).strip().lower()
        if clean:
            out.append(clean)
    return out


def _md_safe(text, lang="ar"):
    if not text:
        return text
    text = str(text)
    if lang == "ar":
        text = _NON_ARABIC_LETTERS_RE.sub("", text)
    else:
        text = _ARABIC_RE.sub("", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return _html_escape(text)


def _get_age_context(age, lang):
    try:
        age = int(age)
    except (TypeError, ValueError):
        return ""
    if age < 12:
        return ("مهم: المريض طفل (أقل من 12 سنة). شدد على ضرورة إشراك أحد الوالدين أو ولي الأمر ومراجعة طبيب أطفال، وكن أكثر حذراً بالنصائح."
                if lang == "ar" else
                "IMPORTANT: This patient is a child (under 12). Emphasize that a parent/guardian must be involved and a pediatrician consulted; be extra cautious with advice.")
    elif age < 20:
        return ("المريض مراهق (13-19 سنة). خلي أسلوب الرد قريب ومناسب لعمره، بدون تعقيد."
                if lang == "ar" else
                "This patient is a teenager (13-19). Keep the tone approachable and age-appropriate, not overly clinical.")
    elif age >= 60:
        return ("مهم: المريض من كبار السن (60 سنة فأكثر). كبار السن أكثر عرضة لمخاطر الجفاف والسقوط وأعراض القلب الخفية — كن أكثر حذراً بالتوصيات، واقترح إحضار مرافق له عند مراجعة الطبيب لو يلزم."
                if lang == "ar" else
                "IMPORTANT: This patient is a senior (60+). Seniors face higher risk from dehydration, falls, and subtle cardiac symptoms — be more cautious in recommendations, and suggest having someone accompany them to medical visits if needed.")
    return ""


def _get_time_context(lang):
    ksa_now = datetime.now(timezone(timedelta(hours=3)))
    hour = ksa_now.hour
    if 0 <= hour < 6:
        return ("سياق مهم: الوقت الحالي بعد منتصف الليل بتوقيت السعودية. لو الحالة بسيطة (غير طارئة)، اقترح بلطف الراحة الليلة ومراقبة الأعراض بدل الحث على الخروج فوراً، إلا لو الحالة فعلاً طارئة."
                if lang == "ar" else
                "IMPORTANT CONTEXT: It is currently late night/early morning in Saudi Arabia. If the case is low urgency (non-emergency), gently suggest resting tonight and monitoring symptoms rather than urging them to go out immediately, unless it's truly urgent.")
    return ""


def _rule_urgency(symptoms, severity, age):
    en = set()
    for s in _normalize_symptoms(symptoms):
        mapped = ml_diagnosis.SYNONYMS.get(s)
        if mapped:
            en.add(mapped)
        elif s in ml_diagnosis.SYNONYMS.values():
            en.add(s)
    try:
        sev = int(severity or 1)
    except (TypeError, ValueError):
        sev = 1
    if "chest pain" in en and ("shortness of breath" in en or "dizziness" in en or "nausea" in en):
        return "high"
    if "chest pain" in en and sev >= 4:
        return "high"
    if "shortness of breath" in en and sev >= 5:
        return "high"
    if sev == 5 and ("chest pain" in en or "shortness of breath" in en or "dizziness" in en):
        return "high"
    if age and int(age) >= 60 and "chest pain" in en:
        return "high"
    return None


def _build_prompt(d, lang):
    sev_labels = {1: "خفيفة جداً", 2: "خفيفة", 3: "متوسطة", 4: "شديدة", 5: "شديدة جداً"} if lang == "ar" \
        else {1: "very mild", 2: "mild", 3: "moderate", 4: "severe", 5: "very severe"}
    sev_label = sev_labels.get(int(d.get("severity", 1) or 1), "")
    age_context = _get_age_context(d.get("age"), lang)
    time_context = _get_time_context(lang)

    if lang == "ar":
        return f"""انت مساعد طبي توعوي متخصص. يجب أن تكتب ردك باللغة العربية فقط بدون أي كلمة بلغة أخرى إطلاقاً.
قواعد الموثوقية (إلزامية):
- اعتمد فقط على المعرفة الطبية من مصادر موثوقة: Mayo Clinic, NHS, WHO, CDC, MedlinePlus.
- لا تخترع أعراضاً أو أمراضاً. لو ما كنت متأكداً، قل "قد يكون" ولا تعطِ تشخيصاً قطعياً أبداً.
- هذا التحليل للتوعية فقط وليس تشخيصاً نهائياً، والمريض يجب أن يراجع الطبيب عند أي شك.
معلومات المريض:
- العمر: {d.get('age')} سنة، الجنس: {d.get('gender')}
- الأعراض: {', '.join(d.get('symptoms', [])[:6])}
- المدة: {d.get('duration')}، الشدة: {sev_label} ({d.get('severity')}/5)
- أمراض سابقة: {d.get('conditions') or 'لا يوجد'}
- الأدوية الحالية: {d.get('medications') or 'لا يوجد'}
- ملاحظات: {d.get('notes') or 'لا يوجد'}
{age_context}
{time_context}
ملاحظة مهمة عن الأدوية: لا تخبري المريض أبداً بإيقاف دواء موصوف من طبيب بشكل قطعي. لو ذكر أدوية، اعطي إرشاد عام حذر (زي: كمّلي حسب وصف الطبيب إلا لو تدهورت الأعراض، أو راجعي الصيدلي/الطبيب قبل أي تغيير). لو ما ذكر أدوية، اترك الحقل فارغ "".
اجب بـ JSON فقط. كل النصوص يجب أن تكون باللغة العربية فقط، ممنوع استخدام أي لغة أخرى:
{{"personal_note":"جملة أو جملتين متعاطفتين وشخصية تخاطب المريض مباشرة بناءً على حالته بالضبط (مو نص عام)","urgency":"low|medium|high","urgency_ar":"بسيط|يحتاج موعد طبيب|طوارئ","confidence":"high|medium|low","possible_conditions":"الاحتمالات بالعربية فقط (3 جمل، بدون تشخيص قطعي)","recommendations":[{{"tip":"نصيحة بالعربية","source":"اسم المصدر مثل Mayo Clinic","source_url":"رابط المصدر https://..."}},{{"tip":"نصيحة بالعربية","source":"اسم المصدر","source_url":"https://..."}},{{"tip":"نصيحة بالعربية","source":"اسم المصدر","source_url":"https://..."}},{{"tip":"نصيحة بالعربية","source":"اسم المصدر","source_url":"https://..."}}],"danger_signs":"علامات الخطر بالعربية فقط","when_to_seek_care":"متى تراجع الطبيب بالعربية فقط","home_care":"الرعاية المنزلية بالعربية فقط","medication_guidance":"إرشاد حذر عن الاستمرار بالدواء أو مراجعة الطبيب/الصيدلي، أو فارغ لو ما ذكر أدوية","questions_for_doctor":"3-4 أسئلة ذكية بالعربية يسألها المريض طبيبه بناءً على حالته"}}"""
    return f"""You are a medical awareness assistant. Write your response in English ONLY. Do not use any other language.
Reliability rules (mandatory):
- Rely only on established medical knowledge from trusted sources: Mayo Clinic, NHS, WHO, CDC, MedlinePlus.
- Never invent symptoms or diseases. If uncertain, say "might be" and never give a definitive diagnosis.
- This is awareness only, not a final diagnosis; the patient should see a doctor if in doubt.
Patient information:
- Age: {d.get('age')}, Gender: {d.get('gender')}
- Symptoms: {', '.join(d.get('symptoms', [])[:6])}
- Duration: {d.get('duration')}, Severity: {sev_label} ({d.get('severity')}/5)
- Previous conditions: {d.get('conditions') or 'None'}
- Current medications: {d.get('medications') or 'None'}
- Notes: {d.get('notes') or 'None'}
{age_context}
{time_context}
Important note about medications: never tell the patient to stop a doctor-prescribed medication outright. If they mentioned medications, give cautious general guidance (e.g., continue as prescribed unless symptoms worsen, or consult a pharmacist/doctor before any change). If no medications were mentioned, leave the field as "".
Reply with JSON only. All text must be in English only:
{{"personal_note":"one or two empathetic, personalized sentences addressing the patient directly based on their specific situation (not generic)","urgency":"low|medium|high","urgency_text":"Simple|Needs appointment|Emergency","confidence":"high|medium|low","possible_conditions":"Possible conditions in English only (3 sentences, no definitive diagnosis)","recommendations":[{{"tip":"tip in English","source":"source name like Mayo Clinic","source_url":"https://..."}},{{"tip":"tip in English","source":"source name","source_url":"https://..."}},{{"tip":"tip in English","source":"source name","source_url":"https://..."}},{{"tip":"tip in English","source":"source name","source_url":"https://..."}}],"danger_signs":"Danger signs in English only","when_to_seek_care":"When to see a doctor in English only","home_care":"Home care tips in English only","medication_guidance":"cautious guidance about continuing medication or consulting a doctor/pharmacist, or empty if no medications mentioned","questions_for_doctor":"3-4 smart questions in English the patient should ask their doctor based on their case"}}"""


def _extract_json(text):
    text = re.sub(r"```json|```", "", str(text or "")).strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise ValueError("No JSON in Groq response")
    return json.loads(m.group())


def _groq_client():
    return Groq(api_key=os.environ["GROQ_API_KEY"])


def run_analysis(patient, lang="ar"):
    """
    patient: dict with keys age, gender, symptoms(list), duration, severity,
             conditions, medications, notes, user_id
    Returns a structured dict ready for any frontend.
    """
    d = dict(patient)
    d.setdefault("symptoms", [])
    lang = "en" if lang == "en" else "ar"
    user_id = d.get("user_id") or "web-anon"

    prompt = _build_prompt(d, lang)
    client = _groq_client()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
        response_format={"type": "json_object"},
        temperature=0.3,
        timeout=45,
    )
    full_text = response.choices[0].message.content
    result = _extract_json(full_text)

    rule_flag = False
    if _rule_urgency(d.get("symptoms"), d.get("severity", 1), d.get("age")) == "high":
        result["urgency"] = "high"
        rule_flag = True

    low_conf = (result.get("confidence") or "medium").lower() == "low"

    predicted = []
    try:
        predicted = ml_diagnosis.predict_conditions(_normalize_symptoms(d.get("symptoms", []))) or []
    except Exception:
        predicted = []

    med_matches = []
    try:
        med_matches = medication_warnings.check_medications(
            f"{d.get('medications', '')} {d.get('notes', '')}"
        ) or []
    except Exception:
        med_matches = []

    record_id = None
    try:
        db.init_db()
        record_id = db.save_record(
            user_id, lang, d.get("age"), d.get("gender"),
            d.get("symptoms", []), d.get("duration"),
            d.get("severity"), result.get("urgency", "low"),
            d.get("conditions", ""), d.get("medications", ""),
        )
    except Exception:
        record_id = None

    return {
        "ok": True,
        "lang": lang,
        "personal_note": _md_safe(result.get("personal_note", ""), lang),
        "urgency": result.get("urgency", "low"),
        "urgency_text": _md_safe(result.get("urgency_ar") or result.get("urgency_text", ""), lang),
        "confidence": result.get("confidence", "medium"),
        "low_confidence": low_conf,
        "rule_forced_high": rule_flag,
        "possible_conditions": _md_safe(result.get("possible_conditions", ""), lang),
        "recommendations": [
            {
                "tip": _md_safe((r.get("tip") or r.get("text") or ""), lang),
                "source": r.get("source") or "",
                "url": r.get("source_url") or r.get("url") or "",
            }
            for r in result.get("recommendations", []) if isinstance(r, dict)
        ],
        "danger_signs": _md_safe(result.get("danger_signs", ""), lang),
        "when_to_seek_care": _md_safe(result.get("when_to_seek_care", ""), lang),
        "home_care": _md_safe(result.get("home_care", ""), lang),
        "medication_guidance": _md_safe(result.get("medication_guidance", ""), lang),
        "questions_for_doctor": _md_safe(result.get("questions_for_doctor", ""), lang),
        "ml_predictions": predicted,
        "med_warnings": med_matches,
        "record_id": record_id,
    }
