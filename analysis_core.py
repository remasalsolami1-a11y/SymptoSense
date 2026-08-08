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
    if isinstance(text, (list, tuple)):
        text = "\n".join(str(x) for x in text if x)
    elif not isinstance(text, str):
        text = str(text)
    if lang == "ar":
        text = _NON_ARABIC_LETTERS_RE.sub("", text)
    else:
        text = _ARABIC_RE.sub("", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return _html_escape(text)


# ---------------------------------------------------------------- recommendations quality
# Canonical source names + their homepages. Only these are accepted; any other
# URL/source the model returns is replaced with the canonical homepage.
TRUSTED_SOURCES = {
    "mayo clinic": ("Mayo Clinic", "https://www.mayoclinic.org/"),
    "mayoclinic": ("Mayo Clinic", "https://www.mayoclinic.org/"),
    "nhs": ("NHS", "https://www.nhs.uk/"),
    "national health service": ("NHS", "https://www.nhs.uk/"),
    "who": ("WHO", "https://www.who.int/"),
    "world health organization": ("WHO", "https://www.who.int/"),
    "cdc": ("CDC", "https://www.cdc.gov/"),
    "centers for disease control": ("CDC", "https://www.cdc.gov/"),
    "medlineplus": ("MedlinePlus", "https://medlineplus.gov/"),
    "medline plus": ("MedlinePlus", "https://medlineplus.gov/"),
}
_TRUSTED_DOMAINS = ("mayoclinic.org", "nhs.uk", "who.int", "cdc.gov", "medlineplus.gov")

# Generic filler tips (or duplicated doctor-visit tips, or medication advice)
# that must never appear as "recommendations".
_GENERIC_MARKERS = {
    "ar": ["شرب الماء", "شرب سوائل", "طعاماً خفيفاً", "أطعمة خفيفة", "وجبات خفيفة",
           "قسط كافٍ من الراحة", "قسط كافٍ من النوم", "راجع الطبيب إذا لم تتحسن",
           "تحديد سبب الأعراض", "أدوية تخفيف", "مسكن", "باراسيتامول", "بنادول",
           "ايبوبروفين", "بروفين", "أسبرين"],
    "en": ["drink water", "stay hydrated", "eat light", "light food", "enough rest",
           "enough sleep", "see a doctor if", "determine the cause", "painkiller",
           "pain relief", "medication", "paracetamol", "ibuprofen", "aspirin"],
}

# Symptom-specific padding tips (used when the model returns too few valid tips).
SYMPTOM_TIPS = [
    (["صداع"], ["headache"],
     "سجّل متى يبدأ الصداع وشدته ومدته وما يخففه — وراجع الطبيب إذا تكرر أو رافقه زغللة أو تنميل أو تصلب في الرقبة.",
     "Note when the headache starts, its severity and what relieves it — see a doctor if it recurs or comes with blurred vision, numbness, or a stiff neck.",
     "Mayo Clinic"),
    (["حمى", "حرارة"], ["fever", "feverish", "temperature"],
     "راقب درجة حرارتك، اشرب سوائل كافية على مدار اليوم، وخفف الملابس — وراجع الطبيب إذا استمرت الحمى أكثر من يومين.",
     "Monitor your temperature, drink plenty of fluids through the day, and lighten clothing — see a doctor if the fever lasts more than two days.",
     "NHS"),
    (["سعال", "كحة"], ["cough", "coughing"],
     "اشرب سوائل دافئة وارتح، ومرّق حلقك بالعسل (للبالغين فقط) — وراجع الطبيب إذا استمر السعال أكثر من ثلاثة أسابيع أو خرج دم.",
     "Drink warm fluids, rest, and soothe your throat with honey (adults only) — see a doctor if the cough lasts over three weeks or you cough up blood.",
     "NHS"),
    (["حلق"], ["throat", "sore throat"],
     "تغرغر بماء دافئ وملح خفيف واشرب سوائل دافئة — وراجع الطبيب إذا صار البلع صعباً جداً أو ظهرت صعوبة تنفس.",
     "Gargle with warm salty water and drink warm fluids — see a doctor if swallowing becomes very difficult or you get breathing trouble.",
     "MedlinePlus"),
    (["غثيان", "قيء", "استفراغ"], ["nausea", "vomiting", "throw up"],
     "اشرب السوائل بكميات صغيرة ومتكررة لتعويض ما فقده الجسم ثم ابدأ بأكل خفيف — وراجع الطبيب إذا استمر التقيؤ أكثر من يوم أو ظهر جفاف.",
     "Sip fluids little and often to replace losses, then start with light food — see a doctor if vomiting lasts more than a day or dehydration appears.",
     "CDC"),
    (["إسهال"], ["diarrhea"],
     "اشرب الكثير من السوائل لتعويض الجفاف وتجنّب الأطعمة الدسمة واللبن لفترة — وراجع الطبيب إذا صار هناك دم أو علامات جفاف شديد.",
     "Drink plenty of fluids to replace losses and avoid greasy food and dairy for a while — see a doctor if there is blood or severe dehydration.",
     "WHO"),
    (["دوخة", "دوار", "دوران"], ["dizziness", "dizzy", "lightheaded"],
     "اجلس أو استلقِ فوراً، قم ببطء عند الوقوف، واشرب الماء — وراجع الطبيب إذا تكررت الدوخة أو رافقها خفقان أو تشوش.",
     "Sit or lie down right away, stand up slowly, and drink water — see a doctor if dizziness repeats or comes with palpitations or confusion.",
     "Mayo Clinic"),
    (["تعب", "إرهاق", "ضعف"], ["fatigue", "tired", "exhaustion", "weakness"],
     "خذ فترات راحة قصيرة ونم ساعات كافية وراقب طاقتك — وراجع الطبيب إذا استمر الإرهاق دون سبب واضح أكثر من أسبوع.",
     "Take short breaks, get enough sleep and monitor your energy — see a doctor if exhaustion persists without a clear reason for over a week.",
     "NHS"),
    (["بطن", "معدة", "آلام معدة"], ["abdominal", "stomach", "belly"],
     "تجنّب الأطعمة الدسمة والحارة والكافيين حتى تتحسن واشرب السوائل — وراجع الطبيب إذا كان الألم شديداً أو مستمراً أو رافقه حمى.",
     "Avoid greasy, spicy foods and caffeine until you improve, and stay hydrated — see a doctor if the pain is severe, persistent, or comes with fever.",
     "MedlinePlus"),
    (["ظهر", "عضلات", "المفاصل"], ["back", "muscle", "joint"],
     "قلّل من الحركات المجهدة وضع كمادة دافئة على مكان الألم — وراجع الطبيب إذا امتد الألم إلى الساق أو رافقه ضعف أو تنميل.",
     "Reduce strenuous movements and apply a warm compress — see a doctor if pain radiates to the leg or comes with weakness or numbness.",
     "Mayo Clinic"),
    (["طفح", "حكة", "حساسية جلدية"], ["rash", "itching", "itchy", "hives"],
     "تجنّب الحكّ واستخدم كمادة باردة، ولاحظ أي طعام أو مادة أثارتها — وراجع الطبيب إذا انتشر أو رافقه صعوبة تنفس.",
     "Avoid scratching, use a cool compress, and note any food or substance that triggered it — see a doctor if it spreads or comes with breathing trouble.",
     "MedlinePlus"),
    (["رشح", "زكام", "برد"], ["runny nose", "cold", "congestion", "sneezing"],
     "اشرب سوائل دافئة وارتح، واستخدم بخار الماء لتخفيف الاحتقان — وراجع الطبيب إذا صار التنفس صعباً أو ارتفعت الحمى.",
     "Drink warm fluids, rest, and use steam to ease congestion — see a doctor if breathing becomes difficult or fever rises.",
     "CDC"),
]
_GENERAL_MONITOR = (
    "راقب تطور الأعراض وسجّل أي تغيّر حتى تزور طبيبك بملاحظات واضحة.",
    "Track how your symptoms change and note any shift so you can visit your doctor with clear observations.",
)


def _is_generic_tip(tip, lang="ar"):
    tip_l = tip.lower()
    for marker in _GENERIC_MARKERS["ar"] + _GENERIC_MARKERS["en"]:
        if marker.lower() in tip_l:
            return True
    # a pure doctor-visit tip with no actionable content
    visit = ("راجع الطبيب", "see your doctor", "see a doctor", "go to the doctor")
    if any(v in tip_l for v in visit) and len(tip_l) < 30:
        return True
    return False


def _canonical_source(src):
    key = (src or "").strip().lower()
    if key in TRUSTED_SOURCES:
        return TRUSTED_SOURCES[key]
    for k, v in TRUSTED_SOURCES.items():
        if k in key:
            return v
    return None


def _is_trusted_url(url):
    url = (url or "").strip().lower()
    if not url.startswith("http"):
        return False
    for dom in _TRUSTED_DOMAINS:
        if dom in url:
            return True
    return False


def _sanitize_recommendations(recs, lang="ar"):
    out = []
    seen = set()
    for r in recs or []:
        if not isinstance(r, dict):
            continue
        tip = (r.get("tip") or r.get("text") or "").strip()
        if not tip or _is_generic_tip(tip, lang):
            continue
        canon = _canonical_source(r.get("source"))
        name, homepage = canon if canon else ("Mayo Clinic", "https://www.mayoclinic.org/")
        url = (r.get("source_url") or r.get("url") or "").strip()
        if not _is_trusted_url(url):
            url = homepage
        dedupe = tip.lower()
        if dedupe in seen:
            continue
        seen.add(dedupe)
        out.append({"tip": tip, "source": name, "url": url})
    return out


def _symptom_tips(symptoms, lang="ar"):
    """Builds symptom-specific padding recommendations from the trusted pool."""
    norm = []
    for s in symptoms or []:
        c = re.sub(r"[^\u0600-\u06FF\sA-Za-z]", "", str(s)).strip().lower()
        if c:
            norm.append(c)
    joined = " " + " ".join(norm) + " "
    ar = lang == "ar"
    tips = []
    for ar_keys, en_keys, tip_ar, tip_en, src in SYMPTOM_TIPS:
        keys = ar_keys if ar else en_keys
        if any(k.lower() in joined for k in keys):
            tips.append({"tip": tip_ar if ar else tip_en,
                         "source": src,
                         "url": TRUSTED_SOURCES[src.lower()][1]})
        if len(tips) >= 3:
            break
    tips.append({"tip": _GENERAL_MONITOR[0] if ar else _GENERAL_MONITOR[1],
                 "source": "WHO",
                 "url": TRUSTED_SOURCES["who"][1]})
    return tips


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
قواعد التوصيات (recommendations) إلزامية:
- كل توصية يجب أن تكون مرتبطة مباشرة بأعراض المريض ومدتها وشدته وعمره — ممنوع نصائح عامة فارغة مثل "اشرب الماء" أو "تناول طعاماً خفيفاً" أو "خذ قسطاً من الراحة" أو "راجع الطبيب لتحديد سبب الأعراض".
- لا تكرر نصيحة "راجع الطبيب لتحديد السبب" في التوصيات، فهي تظهر في حقل when_to_seek_care.
- لا توصِ بأدوية محددة أو جرعات أو مسكنات أبداً.
- المصدر يجب أن يكون واحداً فقط من: Mayo Clinic أو NHS أو WHO أو CDC أو MedlinePlus.
- source_url يجب أن يكون رابطاً حقيقياً يبدأ بـ https:// على نفس النطاق الموثوق (مثال: مقال عن الصداع على mayoclinic.org) وليس الصفحة الرئيسية للنطاق وليس رابطاً مخترعاً.
- اكتب 4 توصيات مختلفة وكلها ذات صلة محددة بهذه الحالة.
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
Recommendation rules (mandatory):
- Each recommendation must be directly tied to the patient's specific symptoms, duration, severity, and age — no empty generic tips like "drink water", "eat light food", "get enough rest", or "see your doctor to determine the cause".
- Do not repeat a "see your doctor to determine the cause" tip in recommendations; that belongs in when_to_seek_care.
- Never recommend specific drugs, doses, or painkillers.
- Source must be one of: Mayo Clinic, NHS, WHO, CDC, or MedlinePlus only.
- source_url must be a real https:// link on that same trusted domain (e.g., a Mayo Clinic article about the symptom) — not the domain homepage and never an invented URL.
- Write 4 distinct recommendations, each specifically relevant to this case.
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


def _fallback_result(d, lang):
    ar = lang == "ar"
    try:
        sev = int(d.get("severity", 1) or 1)
    except (TypeError, ValueError):
        sev = 1
    syms = ", ".join(d.get("symptoms", [])[:6]) or "الأعراض"
    u = _rule_urgency(d.get("symptoms"), sev, d.get("age"))
    if not u:
        u = "high" if sev >= 5 else ("medium" if sev >= 3 else "low")
    if ar:
        ur_ar = {"high": "طوارئ", "medium": "يحتاج موعد طبيب", "low": "بسيط"}[u]
        note = (f"بناءً على ما ذكرته ({syms}) مع شدّة {sev}/5، يُنصح بالحذر وعدم "
                "التردد في مراجعة الطبيب. هذه معلومات توعوية وليست تشخيصاً نهائياً.")
        conditions = ("قد تكون الأعراض ناتجة عن حالة بسيطة قابلة للعلاج، لكن يُفضل "
                      "مراجعة الطبيب للتأكد خصوصاً مع شدة الأعراض الحالية.")
        tips = [
            {"tip": "احصل على قسط كافٍ من الراحة والنوم.", "source": "Mayo Clinic", "url": "https://www.mayoclinic.org/"},
            {"tip": "اشرب سوائل بانتظام وتناول طعاماً خفيفاً.", "source": "NHS", "url": "https://www.nhs.uk/"},
            {"tip": "راقب حرارتك وشدة الألم وسجّل أي تغيّر.", "source": "CDC", "url": "https://www.cdc.gov/"},
            {"tip": "راجع الطبيب إذا لم تتحسن الأعراض خلال أيام.", "source": "WHO", "url": "https://www.who.int/"},
        ]
        return {
            "personal_note": note, "urgency": u, "urgency_ar": ur_ar, "confidence": "low",
            "possible_conditions": conditions, "recommendations": tips,
            "danger_signs": "ضيق تنفس شديد، ألم في الصدر، تشوش، إغماء، أو تدهور مفاجئ.",
            "when_to_seek_care": "راجع الطبيب فوراً أو الطوارئ إذا استمرت الأعراض أو ازدادت سوءاً.",
            "home_care": "خذ قسطاً من الراحة، اشرب سوائل كافية، وراقب الأعراض.",
            "medication_guidance": ("استمر بدوائك الموصوف كما وصفه الطبيب، وراجع الطبيب أو "
                                    "الصيدلي قبل أي تغيير." if d.get("medications") else ""),
            "questions_for_doctor": "متى يجب أن أقلق من هذه الأعراض؟ ما الفحوصات المطلوبة؟ متى أتحسن؟",
        }
    ur_en = {"high": "Emergency", "medium": "Needs appointment", "low": "Simple"}[u]
    return {
        "personal_note": f"Based on what you reported ({syms}) with severity {sev}/5, caution is advised; do not hesitate to see a doctor. This is awareness information, not a final diagnosis.",
        "urgency": u, "urgency_text": ur_en, "confidence": "low",
        "possible_conditions": "Symptoms may come from a simple treatable condition, but a doctor visit is recommended given the current severity.",
        "recommendations": [
            {"tip": "Get enough rest and sleep.", "source": "Mayo Clinic", "url": "https://www.mayoclinic.org/"},
            {"tip": "Stay hydrated and eat light food.", "source": "NHS", "url": "https://www.nhs.uk/"},
            {"tip": "Monitor temperature and pain and note any change.", "source": "CDC", "url": "https://www.cdc.gov/"},
            {"tip": "See a doctor if symptoms do not improve in a few days.", "source": "WHO", "url": "https://www.who.int/"},
        ],
        "danger_signs": "Severe shortness of breath, chest pain, confusion, fainting, or sudden worsening.",
        "when_to_seek_care": "See a doctor or emergency care immediately if symptoms persist or worsen.",
        "home_care": "Rest, drink enough fluids, and monitor symptoms.",
        "medication_guidance": "Continue your prescribed medication as directed and consult your doctor or pharmacist before any change." if d.get("medications") else "",
        "questions_for_doctor": "When should I worry about these symptoms? What tests are needed? When will I improve?",
    }


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
    try:
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
    except Exception:
        result = _fallback_result(d, lang)

    recs = _sanitize_recommendations(result.get("recommendations", []), lang)
    if len(recs) < 2:
        recs = recs + _symptom_tips(d.get("symptoms", []), lang)
    result["recommendations"] = recs[:4]

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
        if record_id:
            db.save_result(
                user_id, record_id,
                {
                    "lang": lang,
                    "age": d.get("age"),
                    "gender": d.get("gender"),
                    "symptoms": d.get("symptoms", []),
                    "urgency": result.get("urgency", "low"),
                    "possible_conditions": result.get("possible_conditions", ""),
                    "recommendations": [
                        {
                            "tip": (r.get("tip") or r.get("text") or ""),
                            "source": r.get("source") or "",
                            "url": r.get("source_url") or r.get("url") or "",
                        }
                        for r in result.get("recommendations", []) if isinstance(r, dict)
                    ],
                    "personal_note": result.get("personal_note", ""),
                    "danger_signs": result.get("danger_signs", ""),
                    "when_to_seek_care": result.get("when_to_seek_care", ""),
                    "home_care": result.get("home_care", ""),
                    "medication_guidance": result.get("medication_guidance", ""),
                    "questions_for_doctor": result.get("questions_for_doctor", ""),
                },
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
