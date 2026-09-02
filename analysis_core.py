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
import medical_knowledge

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
    # Generated prose must never surface diagnostic percentages or links;
    # source URLs are supplied separately from verified database records.
    text = re.sub(r"https?://\S+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\b\d+(?:[.,]\d+)?\s*%", "", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return _html_escape(text)


# ---------------------------------------------------------------- recommendations quality
# Canonical source names + their homepages. Only these are accepted; any other
# URL/source the model returns is replaced with the canonical homepage.
TRUSTED_SOURCES = {
    "saudi ministry of health": ("Saudi Ministry of Health", "https://www.moh.gov.sa/"),
    "وزارة الصحة السعودية": ("وزارة الصحة السعودية", "https://www.moh.gov.sa/"),
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
_TRUSTED_DOMAINS = ("moh.gov.sa", "mayoclinic.org", "nhs.uk", "who.int", "cdc.gov", "medlineplus.gov")

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
     "سجل الصداع وخصائصه",
     "سجّل متى يبدأ الصداع وشدته ومدته وما يخففه — وراجع الطبيب إذا تكرر أو رافقه زغللة أو تنميل أو تصلب في الرقبة.",
     "Track the headache",
     "Note when the headache starts, its severity and what relieves it — see a doctor if it recurs or comes with blurred vision, numbness, or a stiff neck.",
     "Mayo Clinic"),
    (["حمى", "حرارة"], ["fever", "feverish", "temperature"],
     "راقب حرارتك وترطيبك",
     "راقب درجة حرارتك، اشرب سوائل كافية على مدار اليوم، وخفف الملابس — وراجع الطبيب إذا استمرت الحمى أكثر من يومين.",
     "Monitor fever and fluids",
     "Monitor your temperature, drink plenty of fluids through the day, and lighten clothing — see a doctor if the fever lasts more than two days.",
     "NHS"),
    (["سعال", "كحة"], ["cough", "coughing"],
     "عناية لطيفة بالسعال",
     "اشرب سوائل دافئة وارتح، ومرّق حلقك بالعسل (للبالغين فقط) — وراجع الطبيب إذا استمر السعال أكثر من ثلاثة أسابيع أو خرج دم.",
     "Soothe the cough gently",
     "Drink warm fluids, rest, and soothe your throat with honey (adults only) — see a doctor if the cough lasts over three weeks or you cough up blood.",
     "NHS"),
    (["حلق"], ["throat", "sore throat"],
     "تخفيف تهيج الحلق",
     "تغرغر بماء دافئ وملح خفيف واشرب سوائل دافئة — وراجع الطبيب إذا صار البلع صعباً جداً أو ظهرت صعوبة تنفس.",
     "Ease throat irritation",
     "Gargle with warm salty water and drink warm fluids — see a doctor if swallowing becomes very difficult or you get breathing trouble.",
     "MedlinePlus"),
    (["غثيان", "قيء", "استفراغ"], ["nausea", "vomiting", "throw up"],
     "تعويض السوائل بلطف",
     "اشرب السوائل بكميات صغيرة ومتكررة لتعويض ما فقده الجسم ثم ابدأ بأكل خفيف — وراجع الطبيب إذا استمر التقيؤ أكثر من يوم أو ظهر جفاف.",
     "Rehydrate gently",
     "Sip fluids little and often to replace losses, then start with light food — see a doctor if vomiting lasts more than a day or dehydration appears.",
     "CDC"),
    (["إسهال"], ["diarrhea"],
     "تعويض السوائل وتجنب الدسم",
     "اشرب الكثير من السوائل لتعويض الجفاف وتجنّب الأطعمة الدسمة واللبن لفترة — وراجع الطبيب إذا صار هناك دم أو علامات جفاف شديد.",
     "Replace fluids, avoid greasy food",
     "Drink plenty of fluids to replace losses and avoid greasy food and dairy for a while — see a doctor if there is blood or severe dehydration.",
     "WHO"),
    (["دوخة", "دوار", "دوران"], ["dizziness", "dizzy", "lightheaded"],
     "تعامل آمن مع الدوخة",
     "اجلس أو استلقِ فوراً، قم ببطء عند الوقوف، واشرب الماء — وراجع الطبيب إذا تكررت الدوخة أو رافقها خفقان أو تشوش.",
     "Handle dizziness safely",
     "Sit or lie down right away, stand up slowly, and drink water — see a doctor if dizziness repeats or comes with palpitations or confusion.",
     "Mayo Clinic"),
    (["تعب", "إرهاق", "ضعف"], ["fatigue", "tired", "exhaustion", "weakness"],
     "تنظيم الراحة والطاقة",
     "خذ فترات راحة قصيرة ونم ساعات كافية وراقب طاقتك — وراجع الطبيب إذا استمر الإرهاق دون سبب واضح أكثر من أسبوع.",
     "Manage rest and energy",
     "Take short breaks, get enough sleep and monitor your energy — see a doctor if exhaustion persists without a clear reason for over a week.",
     "NHS"),
    (["بطن", "معدة", "آلام معدة"], ["abdominal", "stomach", "belly"],
     "حمية مريحة للمعدة",
     "تجنّب الأطعمة الدسمة والحارة والكافيين حتى تتحسن واشرب السوائل — وراجع الطبيب إذا كان الألم شديداً أو مستمراً أو رافقه حمى.",
     "Gentle diet for the stomach",
     "Avoid greasy, spicy foods and caffeine until you improve, and stay hydrated — see a doctor if the pain is severe, persistent, or comes with fever.",
     "MedlinePlus"),
    (["ظهر", "عضلات", "المفاصل"], ["back", "muscle", "joint"],
     "تخفيف ألم العضلات والظهر",
     "قلّل من الحركات المجهدة وضع كمادة دافئة على مكان الألم — وراجع الطبيب إذا امتد الألم إلى الساق أو رافقه ضعف أو تنميل.",
     "Relieve muscle and back pain",
     "Reduce strenuous movements and apply a warm compress — see a doctor if pain radiates to the leg or comes with weakness or numbness.",
     "Mayo Clinic"),
    (["طفح", "حكة", "حساسية جلدية"], ["rash", "itching", "itchy", "hives"],
     "تخفيف الطفح والحكة",
     "تجنّب الحكّ واستخدم كمادة باردة، ولاحظ أي طعام أو مادة أثارتها — وراجع الطبيب إذا انتشر أو رافقه صعوبة تنفس.",
     "Soothe rash and itching",
     "Avoid scratching, use a cool compress, and note any food or substance that triggered it — see a doctor if it spreads or comes with breathing trouble.",
     "MedlinePlus"),
    (["رشح", "زكام", "برد"], ["runny nose", "cold", "congestion", "sneezing"],
     "تخفيف احتقان الزكام",
     "اشرب سوائل دافئة وارتح، واستخدم بخار الماء لتخفيف الاحتقان — وراجع الطبيب إذا صار التنفس صعباً أو ارتفعت الحمى.",
     "Ease cold congestion",
     "Drink warm fluids, rest, and use steam to ease congestion — see a doctor if breathing becomes difficult or fever rises.",
     "CDC"),
    (["احمرار العيون", "احمرار العين", "حكة العين"], ["eye redness", "red eyes", "itchy eyes"],
     "تجنب المهيجات ومسببات الحساسية",
     "إذا كان الاحمرار مرتبطاً بالحساسية، تجنب الغبار والعطور والملوثات التي قد تزيد الأعراض، وتجنب فرك العين واغسل يديك قبل لمسها.",
     "Avoid irritants and allergens",
     "If the redness is allergy-related, avoid dust, perfumes, and pollutants that may worsen it; avoid rubbing your eyes and wash your hands before touching them.",
     "Mayo Clinic"),
]
_GENERAL_MONITOR = (
    "راقب تطور الأعراض",
    "راقب تطور الأعراض وسجّل أي تغيّر حتى تزور طبيبك بملاحظات واضحة.",
    "Monitor your symptoms",
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
        title = (r.get("title") or "").strip()
        if not title:
            words = tip.split()
            title = " ".join(words[:6])
        canon = _canonical_source(r.get("source"))
        name, homepage = canon if canon else ("Mayo Clinic", "https://www.mayoclinic.org/")
        url = (r.get("source_url") or r.get("url") or "").strip()
        if not _is_trusted_url(url):
            url = homepage
        dedupe = tip.lower()
        if dedupe in seen:
            continue
        seen.add(dedupe)
        out.append({"title": title, "tip": tip, "source": name, "url": url})
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
    for ar_keys, en_keys, title_ar, tip_ar, title_en, tip_en, src in SYMPTOM_TIPS:
        keys = ar_keys if ar else en_keys
        if any(k.lower() in joined for k in keys):
            tips.append({"title": title_ar if ar else title_en,
                         "tip": tip_ar if ar else tip_en,
                         "source": src,
                         "url": TRUSTED_SOURCES[src.lower()][1]})
        if len(tips) >= 3:
            break
    tips.append({"title": _GENERAL_MONITOR[0] if ar else _GENERAL_MONITOR[2],
                 "tip": _GENERAL_MONITOR[1] if ar else _GENERAL_MONITOR[3],
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


RED_FLAGS = {
    "en": [
        ("chest pain", "Chest pain"), ("chest tightness", "Chest tightness"),
        ("pain in the chest", "Chest pain"), ("heart pain", "Chest pain"),
        ("shortness of breath", "Shortness of breath"), ("difficulty breathing", "Difficulty breathing"),
        ("difficulty in breathing", "Difficulty breathing"), ("trouble breathing", "Difficulty breathing"),
        ("can't breathe", "Difficulty breathing"), ("cannot breathe", "Difficulty breathing"),
        ("breathing trouble", "Difficulty breathing"), ("breathless", "Shortness of breath"),
        ("confusion", "Confusion"), ("confused", "Confusion"), ("disoriented", "Confusion"),
        ("unconscious", "Loss of consciousness"), ("fainting", "Fainting"), ("fainted", "Fainting"),
        ("passed out", "Fainting"), ("passing out", "Fainting"),
        ("seizure", "Seizure"), ("convulsion", "Seizure"),
        ("severe bleeding", "Severe bleeding"), ("bleeding heavily", "Severe bleeding"),
        ("uncontrollable bleeding", "Severe bleeding"),
        ("vomiting blood", "Vomiting blood"), ("coughing blood", "Coughing blood"),
        ("blood in vomit", "Vomiting blood"), ("blood in stool", "Blood in stool"),
        ("slurred speech", "Slurred speech"), ("face drooping", "Face drooping"),
        ("weakness on one side", "One-sided weakness"), ("numbness on one side", "One-sided numbness"),
        ("arm weakness", "One-sided weakness"), ("choking", "Choking"),
        ("severe headache", "Severe headache"), ("worst headache", "Severe headache"),
        ("stiff neck", "Stiff neck"), ("stroke", "Possible stroke"), ("heart attack", "Possible heart attack"),
        ("suicidal", "Suicidal thoughts"), ("self-harm", "Self-harm"),
        ("overdose", "Overdose"), ("poisoning", "Poisoning"), ("poisoned", "Poisoning"),
    ],
    "ar": [
        ("ألم في الصدر", "ألم في الصدر"), ("ألم بالصدر", "ألم في الصدر"), ("ألم الصدر", "ألم في الصدر"),
        ("ضيق في التنفس", "ضيق في التنفس"), ("ضيق التنفس", "ضيق في التنفس"), ("صعوبة في التنفس", "صعوبة في التنفس"),
        ("صعوبة التنفس", "صعوبة في التنفس"), ("لا أستطيع التنفس", "صعوبة في التنفس"), ("لا أقدر أتنفس", "صعوبة في التنفس"),
        ("تشوش", "تشوش ذهني"), ("تشوش ذهني", "تشوش ذهني"), ("ارتباك", "تشوش ذهني"), ("حيرة ذهنية", "تشوش ذهني"),
        ("فقدان الوعي", "فقدان الوعي"), ("غيبوبة", "فقدان الوعي"), ("إغماء", "إغماء"), ("أغمي علي", "إغماء"),
        ("تشنجات", "تشنجات"), ("نزيف شديد", "نزيف شديد"), ("نزيف حاد", "نزيف شديد"), ("دم لا يتوقف", "نزيف شديد"),
        ("قيء دم", "قيء دم"), ("دم في القيء", "قيء دم"), ("سعال دم", "سعال دم"), ("دم مع البلغم", "سعال دم"),
        ("دم في البراز", "دم في البراز"), ("صعوبة في الكلام", "صعوبة في الكلام"), ("تدلي الوجه", "تدلي الوجه"),
        ("ضعف في جانب", "ضعف في جانب"), ("تنميل في جانب", "تنميل في جانب"), ("خدر في جانب", "تنميل في جانب"),
        ("اختناق", "اختناق"), ("صداع شديد", "صداع شديد"), ("صداع مفاجئ شديد", "صداع شديد"), ("تصلب الرقبة", "تصلب الرقبة"),
        ("جلطة", "احتمال جلطة"), ("سكتة", "احتمال سكتة دماغية"), ("نوبة قلبية", "احتمال نوبة قلبية"),
        ("أفكار انتحارية", "أفكار انتحارية"), ("انتحار", "أفكار انتحارية"), ("إيذاء النفس", "إيذاء النفس"),
        ("جرعة زائدة", "جرعة زائدة"), ("تسمم", "تسمم"), ("مسموم", "تسمم"),
    ],
}


def detect_red_flags(symptoms, notes="", lang="ar"):
    text = (" ".join(symptoms or []) + " " + (notes or "")).lower()
    flags = []
    for kw, label in RED_FLAGS.get("en" if lang == "en" else "ar", RED_FLAGS["ar"]):
        if kw in text and label not in flags:
            flags.append(label)
    return flags


def _triage_label(level, lang):
    labels = {
        "emergency": ("🔴 طوارئ الآن", "🔴 Emergency now"),
        "today": ("🟠 يحتاج تقييم طبي اليوم", "🟠 Needs medical evaluation today"),
        "soon": ("🟡 احجز موعداً قريباً", "🟡 Book an appointment soon"),
        "monitor": ("🟢 يمكن المتابعة والمراقبة", "🟢 Monitor and follow up"),
    }
    return labels.get(level, labels["monitor"])[0 if lang == "ar" else 1]


def _triage(d, lang):
    syms = d.get("symptoms") or []
    text = (" ".join(syms) + " " + (d.get("notes") or "")).lower()
    try:
        sev = int(d.get("severity") or 1)
    except (TypeError, ValueError):
        sev = 1
    age = d.get("age")
    try:
        age = int(age) if age else None
    except (TypeError, ValueError):
        age = None
    duration = (d.get("duration") or "").lower()
    long_ago = ("week" in duration or "month" in duration or "أسبوع" in duration or "شهر" in duration)

    has_chest = ("chest" in text or "heart pain" in text) or ("الصدر" in text or "صدر" in text)
    has_breath = ("breath" in text) or ("تنفس" in text)
    has_dizzy = ("dizzy" in text) or ("دوار" in text or "دوخة" in text)
    has_confuse = ("confus" in text) or ("تشوش" in text or "ارتباك" in text)
    has_faint = ("faint" in text or "unconscious" in text or "passed out" in text) or ("إغماء" in text or "وعي" in text or "غيبوبة" in text)
    has_seizure = ("seizure" in text or "convulsion" in text) or ("تشنج" in text or "صرع" in text)
    has_bleed = ("bleed" in text) or ("نزيف" in text or "دم" in text)
    has_weak = ("weakness" in text or "numbness" in text or "droop" in text or "slurred" in text) or ("ضعف" in text or "تنميل" in text or "تدلي" in text or "كلام" in text)

    red = detect_red_flags(syms, d.get("notes") or "", lang)

    reasons = []
    level = "monitor"

    def add(lev, msg):
        if lev not in ("emergency", "today", "soon", "monitor"):
            return
        nonlocal level
        level = lev
        reasons.append(msg)

    if red:
        if lang == "ar":
            add("emergency", "علامات خطر تستدعي رعاية عاجلة: " + "، ".join(red))
        else:
            add("emergency", "Red-flag symptoms require urgent care: " + ", ".join(red))
    elif sev == 5:
        add("emergency", "شدة الأعراض حرجة (5/5)" if lang == "ar" else "Symptom severity is critical (5/5)")

    if level == "monitor":
        if has_chest and (has_breath or has_dizzy or has_faint):
            add("today", "ألم الصدر مع ضيق تنفس أو دوار أو إغماء" if lang == "ar" else "Chest pain with shortness of breath, dizziness, or fainting")
        elif has_chest:
            add("today", "وجود ألم في الصدر" if lang == "ar" else "Chest pain reported")
        elif has_breath:
            add("today", "صعوبة في التنفس" if lang == "ar" else "Difficulty breathing")
        elif has_faint or has_seizure:
            add("today", "نوبة إغماء أو تشنج" if lang == "ar" else "A fainting episode or seizure")
        elif has_bleed:
            add("today", "نزيف غير معتاد" if lang == "ar" else "Unusual bleeding")
        elif has_confuse or has_weak:
            add("today", "أعراض عصبية جديدة" if lang == "ar" else "New neurological symptoms")
        elif sev == 4:
            add("today", "شدة الأعراض عالية (4/5)" if lang == "ar" else "High symptom severity (4/5)")
        elif age and age >= 60 and (has_chest or has_breath or has_dizzy):
            add("today", "العمر فوق 60 عاماً مع أعراض تستدعي الحذر" if lang == "ar" else "Age over 60 with symptoms that require caution")
        elif sev == 3:
            add("soon", "شدة الأعراض متوسطة (3/5)" if lang == "ar" else "Moderate symptom severity (3/5)")
        elif long_ago:
            add("soon", "استمرار الأعراض لأكثر من أسبوع" if lang == "ar" else "Symptoms persisting for more than a week")
        elif len(syms) >= 3:
            add("soon", "تعدد الأعراض (3 أو أكثر) يحتاج متابعة" if lang == "ar" else "Multiple symptoms (3+) need follow-up")
        else:
            add("monitor", "أعراض بسيطة يمكن مراقبتها مع الرعاية المنزلية" if lang == "ar" else "Mild symptoms can be monitored with home care")

    reason = "\n".join("• " + r for r in reasons)
    return {"level": level, "reason": reason, "label": _triage_label(level, lang)}


def _blood_context(d, lang):
    b = d.get("blood") or {}
    if not b or not b.get("indicators"):
        return ""
    inds = []
    for it in (b.get("indicators") or [])[:12]:
        try:
            inds.append(f"{it.get('name','?')}: {it.get('value','')} ({it.get('status','')})")
        except Exception:
            continue
    if lang == "ar":
        txt = "- نتائج فحص الدم: " + "، ".join(inds)
        if b.get("summary"):
            txt += "\n- ملخص الفحص: " + str(b.get("summary"))
        return txt + "\nاستخدم نتائج الدم كسياق إضافي عند تفسير الأعراض، واذكر في الاحتمالات أن فحص الدم يُظهر: " + str(b.get("level", "")) if inds else ""
    txt = "- Blood test results: " + ", ".join(inds)
    if b.get("summary"):
        txt += "\n- Test summary: " + str(b.get("summary"))
    return txt + "\nUse the blood results as additional context when interpreting the symptoms, and mention in the assessment that the blood test shows: " + str(b.get("level", "")) if inds else ""


def _match_label(level, lang):
    labels = {
        "ar": {"strong": "توافق مرتفع", "moderate": "توافق متوسط", "weak": "توافق منخفض"},
        "en": {"strong": "Strong match", "moderate": "Moderate match", "weak": "Weak match"},
    }
    return labels["en" if lang == "en" else "ar"].get(level, labels["en" if lang == "en" else "ar"]["weak"])


def _knowledge_prompt_context(bundle, lang):
    """A compact, bounded context.  Only these diseases and URLs may reach AI output."""
    rows = []
    for match in (bundle.get("matches") or [])[:4]:
        rows.append({
            "name": match.get("name_en") if lang == "en" else match.get("name_ar"),
            "match": _match_label(match.get("match_level"), lang),
            "matched_symptoms": [
                s.get("name_en") if lang == "en" else s.get("name_ar")
                for s in match.get("matched_symptoms", [])
            ],
            "description": match.get("description"),
            "red_flags": match.get("red_flags"),
            "next_step": match.get("recommended_next_step"),
            "sources": [
                {"name": s.get("source_name"), "url": s.get("reference_url")}
                for s in match.get("sources", [])
            ],
        })
    return json.dumps(rows, ensure_ascii=False)


def _render_possible_conditions(matches, lang):
    if not matches:
        return ("لا توجد معلومات كافية في قاعدة المعرفة لعرض احتمالات موثوقة. لا يعني ذلك عدم وجود سبب طبي؛ راجع مختصًا إذا استمرت الأعراض أو ساءت."
                if lang == "ar" else
                "There is not enough information in the knowledge base to show source-grounded possibilities. This does not rule out a medical cause; seek review if symptoms persist or worsen.")
    lines = []
    for match in matches[:3]:
        name = match.get("name_ar") if lang == "ar" else match.get("name_en")
        label = _match_label(match.get("match_level"), lang)
        if lang == "ar":
            lines.append(f"{name} — {label}. الأعراض المذكورة تتوافق معه بهذا المستوى، لكن هذا لا يُعد تشخيصًا طبيًا.")
        else:
            lines.append(f"{name} — {label}. The symptoms align at this level, but this is not a medical diagnosis.")
    return "\n".join(lines)


def _knowledge_recommendations(bundle, lang):
    recs, seen = [], set()
    for match in (bundle.get("matches") or [])[:3]:
        tip = (match.get("recommended_next_step") or "").strip()
        if not tip or tip.lower() in seen:
            continue
        seen.add(tip.lower())
        sources = match.get("sources") or []
        source = sources[0] if sources else {}
        name = match.get("name_ar") if lang == "ar" else match.get("name_en")
        recs.append({
            "title": (("خطوة آمنة لـ " + name) if lang == "ar" else ("Safe next step: " + name)),
            "tip": tip,
            "source": source.get("source_name") or "",
            "url": source.get("reference_url") or "",
        })
    if not recs and bundle.get("risk", {}).get("level") != "urgent":
        recs.append({
            "title": "راقب وسجّل الأعراض" if lang == "ar" else "Monitor and record symptoms",
            "tip": ("دوّن وقت بدء الأعراض ومدتها وما يزيدها أو يخففها، واطلب تقييمًا طبيًا إذا استمرت أو ازدادت."
                    if lang == "ar" else
                    "Record when symptoms started, their duration, and what changes them; seek medical review if they persist or worsen."),
            "source": "", "url": "",
        })
    return recs[:4]


def _grounded_guidance(bundle, patient, lang):
    """Return safety and follow-up copy without relying on generated facts."""
    risk = bundle.get("risk", {}).get("level", "low")
    matches = bundle.get("matches") or []
    red_flags = []
    for match in matches[:3]:
        text = (match.get("red_flags") or "").strip()
        if text and text not in red_flags:
            red_flags.append(text)
    if not red_flags:
        red_flags.append(
            "اطلب مساعدة عاجلة عند تدهور مفاجئ أو ظهور صعوبة تنفس أو إغماء أو علامة عصبية جديدة."
            if lang == "ar" else
            "Seek urgent help for sudden deterioration, breathing difficulty, fainting, or a new neurological sign."
        )
    if risk == "review":
        when = (
            "يوصى بالتواصل مع طبيب أو الحصول على تقييم طبي قريب، وبشكل أسرع إذا ازدادت الأعراض أو ظهرت علامة خطر."
            if lang == "ar" else
            "Contact a clinician or arrange medical assessment soon, and seek help sooner if symptoms worsen or a red flag appears."
        )
    else:
        when = (
            "راقب الأعراض واطلب تقييمًا طبيًا إذا استمرت أو ازدادت أو ظهرت علامة خطر."
            if lang == "ar" else
            "Monitor symptoms and seek medical assessment if they persist, worsen, or a red flag appears."
        )
    home = (
        "• سجّل الأعراض ومدتها وشدتها وأي تغير واضح.\n• اتبع الخطوات الآمنة المرتبطة بالمصادر أعلاه، ولا تؤخر التقييم عند التدهور."
        if lang == "ar" else
        "• Record symptoms, duration, severity, and clear changes.\n• Follow the source-linked safe steps above, and do not delay assessment if symptoms worsen."
    )
    medications = ""
    if patient.get("medications"):
        medications = (
            "استمر على الأدوية الموصوفة وفق تعليمات طبيبك، ولا تغيّرها أو توقفها قبل سؤال الطبيب أو الصيدلي."
            if lang == "ar" else
            "Continue prescribed medicines as directed; do not change or stop them before asking your clinician or pharmacist."
        )
    questions = (
        "ما التفسيرات التي تناسب هذه الأعراض؟ ما علامات الخطر التي أراقبها؟ متى أحتاج متابعة أو فحوصًا؟"
        if lang == "ar" else
        "What explanations fit these symptoms? Which red flags should I watch for? When do I need follow-up or tests?"
    )
    return {
        "danger_signs": "\n".join("• " + item for item in red_flags),
        "when_to_seek_care": when,
        "home_care": home,
        "medication_guidance": medications,
        "questions_for_doctor": questions,
    }


def _why_result(bundle, lang):
    matches = bundle.get("matches") or []
    if not matches:
        unmatched = bundle.get("normalization", {}).get("unmatched") or []
        if unmatched:
            return ("لم تتمكن قاعدة المعرفة من توحيد بعض الأعراض: " + "، ".join(unmatched[:4])
                    if lang == "ar" else
                    "The knowledge base could not normalize some symptoms: " + ", ".join(unmatched[:4]))
        return "لم يظهر تطابق موثوق كافٍ من العلاقات الطبية المتاحة." if lang == "ar" else "No sufficiently grounded match was found in the available medical relationships."
    parts = []
    for match in matches[:3]:
        name = match.get("name_ar") if lang == "ar" else match.get("name_en")
        symptoms = [s.get("name_ar") if lang == "ar" else s.get("name_en") for s in match.get("matched_symptoms", [])]
        parts.append((f"{name}: ظهر بسبب " if lang == "ar" else f"{name}: shown because of ") + "، ".join(symptoms))
    return "\n".join(parts)


def _urgent_result(bundle, lang):
    reasons = bundle.get("risk", {}).get("reasons") or []
    reason_text = "\n".join("• " + str(r.get("message") or r.get("name") or "") for r in reasons if (r.get("message") or r.get("name")))
    actions = []
    for r in reasons:
        action = r.get("recommended_action")
        if action and action not in actions:
            actions.append(str(action))
    if lang == "ar":
        default_action = "اطلب الرعاية الطبية العاجلة أو تواصل مع خدمات الطوارئ المناسبة."
        return {
            "personal_note": "الأعراض التي أدخلتها قد تشير إلى حالة تستدعي تقييمًا طبيًا عاجلًا. لا تعتمد على هذا التحليل وحده، واطلب المساعدة الطبية المناسبة.",
            "possible_conditions": _render_possible_conditions(bundle.get("matches") or [], "ar"),
            "recommendations": [], "danger_signs": reason_text,
            "when_to_seek_care": "\n".join(actions[:3]) if actions else default_action,
            "home_care": "", "medication_guidance": "", "questions_for_doctor": "",
            "simple_explanation": "الأولوية الآن هي الأمان والحصول على تقييم طبي عاجل عند الحاجة. هذه النتيجة لا تعني تشخيصًا محددًا.",
            "confidence": "high", "urgency": "high", "urgency_ar": "عاجل",
        }
    default_action = "Seek urgent medical care or contact the appropriate emergency service."
    return {
        "personal_note": "The symptoms you entered may indicate a situation that needs urgent medical assessment. Do not rely on this assessment alone; seek appropriate medical help.",
        "possible_conditions": _render_possible_conditions(bundle.get("matches") or [], "en"),
        "recommendations": [], "danger_signs": reason_text,
        "when_to_seek_care": "\n".join(actions[:3]) if actions else default_action,
        "home_care": "", "medication_guidance": "", "questions_for_doctor": "",
        "simple_explanation": "The priority is safety and timely medical assessment when needed. This result does not establish a diagnosis.",
        "confidence": "high", "urgency": "high", "urgency_text": "Urgent",
    }


def _build_prompt(d, lang):
    sev_labels = {1: "خفيفة جداً", 2: "خفيفة", 3: "متوسطة", 4: "شديدة", 5: "شديدة جداً"} if lang == "ar" \
        else {1: "very mild", 2: "mild", 3: "moderate", 4: "severe", 5: "very severe"}
    sev_label = sev_labels.get(int(d.get("severity", 1) or 1), "")
    age_context = _get_age_context(d.get("age"), lang)
    time_context = _get_time_context(lang)
    blood_context = _blood_context(d, lang)
    knowledge_context = d.get("_knowledge_context") or "[]"

    if lang == "ar":
        return f"""انت مساعد طبي توعوي متخصص. يجب أن تكتب ردك باللغة العربية فقط بدون أي كلمة بلغة أخرى إطلاقاً.
قواعد الموثوقية (إلزامية):
- استخدم فقط الأمراض والمصادر والروابط الموجودة في سياق قاعدة المعرفة أدناه.
- لا تخترع أعراضاً أو أمراضاً أو نسباً أو مصادر أو روابط. إذا لم يكفِ السياق فقل إن المعلومة غير متوفرة.
- هذا التحليل للتوعية فقط وليس تشخيصاً نهائياً، والمريض يجب أن يراجع الطبيب عند أي شك.
سياق قاعدة المعرفة الطبية الموثقة:
{knowledge_context}
معلومات المريض:
- العمر: {d.get('age')} سنة، الجنس: {d.get('gender')}
- الأعراض: {', '.join(d.get('symptoms', [])[:6])}
- المدة: {d.get('duration')}، الشدة: {sev_label} ({d.get('severity')}/5)
- أمراض سابقة: {d.get('conditions') or 'لا يوجد'}
- الأدوية الحالية: {d.get('medications') or 'لا يوجد'}
- ملاحظات: {d.get('notes') or 'لا يوجد'}
{blood_context}
{age_context}
{time_context}
ملاحظة مهمة عن الأدوية: لا تخبري المريض أبداً بإيقاف دواء موصوف من طبيب بشكل قطعي. لو ذكر أدوية، اعطي إرشاد عام حذر (زي: كمّلي حسب وصف الطبيب إلا لو تدهورت الأعراض، أو راجعي الصيدلي/الطبيب قبل أي تغيير). لو ما ذكر أدوية، اترك الحقل فارغ "".
قواعد التوصيات (recommendations) إلزامية:
- كل توصية يجب أن تكون مرتبطة مباشرة بأعراض المريض ومدتها وشدته وعمره — ممنوع نصائح عامة فارغة مثل "اشرب الماء" أو "تناول طعاماً خفيفاً" أو "خذ قسطاً من الراحة" أو "راجع الطبيب لتحديد سبب الأعراض".
- لا تكرر نصيحة "راجع الطبيب لتحديد السبب" في التوصيات، فهي تظهر في حقل when_to_seek_care.
- title يجب أن يكون عنواناً قصيراً جداً (3-5 كلمات)، وtip شرح التوصية بجملة أو جملتين.
- لا توصِ بأدوية محددة أو جرعات أو مسكنات أبداً.
- عند الحديث عن مهيجات العين أو الأنف أو الحساسية لا تستخدم كلمة "اللقاحات" أبداً — استخدم "الملوثات" أو "المهيجات".
- المصدر والرابط يجب أن يكونا من سياق قاعدة المعرفة أعلاه فقط وبنفس الكتابة والرابط تمامًا.
- اكتب 4 توصيات مختلفة وكلها ذات صلة محددة بهذه الحالة.
اجب بـ JSON فقط. كل النصوص يجب أن تكون باللغة العربية فقط، ممنوع استخدام أي لغة أخرى:
{{"personal_note":"جملة أو جملتين متعاطفتين وشخصية تخاطب المريض مباشرة بناءً على حالته بالضبط (مو نص عام)","urgency":"low|medium|high","urgency_ar":"بسيط|يحتاج موعد طبيب|طوارئ","confidence":"high|medium|low","simple_explanation":"شرح بسيط جداً بالعربية بجملة أو جملتين لغير المتخصصين، بدون مصطلحات طبية معقدة، بلغة واضحة وسهلة","possible_conditions":"الاحتمالات بالعربية فقط (3 جمل، بدون تشخيص قطعي)","recommendations":[{{"title":"عنوان قصير جداً (3-5 كلمات)","tip":"شرح التوصية بجملة أو جملتين مرتبطاً بالأعراض","source":"اسم المصدر مثل Mayo Clinic","source_url":"https://..."}},{{"title":"عنوان قصير","tip":"شرح التوصية","source":"اسم المصدر","source_url":"https://..."}},{{"title":"عنوان قصير","tip":"شرح التوصية","source":"اسم المصدر","source_url":"https://..."}},{{"title":"عنوان قصير","tip":"شرح التوصية","source":"اسم المصدر","source_url":"https://..."}}],"danger_signs":"علامات الخطر بالعربية فقط","when_to_seek_care":"متى تراجع الطبيب بالعربية فقط","home_care":"الرعاية المنزلية بالعربية كقائمة نقاط قصيرة (كل نقطة بجملة آمنة حذرة — ممنوع ذكر منتجات أو أدوية أو قطرات عينية محددة)","medication_guidance":"إرشاد حذر عن الاستمرار بالدواء أو مراجعة الطبيب/الصيدلي، أو فارغ لو ما ذكر أدوية","questions_for_doctor":"3-4 أسئلة ذكية بالعربية يسألها المريض طبيبه بناءً على حالته"}}"""
    return f"""You are a medical awareness assistant. Write your response in English ONLY. Do not use any other language.
Reliability rules (mandatory):
- Use only the diseases, sources, and exact URLs in the knowledge-base context below.
- Never invent symptoms, diseases, percentages, sources, or links. If context is insufficient, say the information is unavailable.
- This is awareness only, not a final diagnosis; the patient should see a doctor if in doubt.
Trusted medical knowledge-base context:
{knowledge_context}
Patient information:
- Age: {d.get('age')}, Gender: {d.get('gender')}
- Symptoms: {', '.join(d.get('symptoms', [])[:6])}
- Duration: {d.get('duration')}, Severity: {sev_label} ({d.get('severity')}/5)
- Previous conditions: {d.get('conditions') or 'None'}
- Current medications: {d.get('medications') or 'None'}
- Notes: {d.get('notes') or 'None'}
{blood_context}
{age_context}
{time_context}
Important note about medications: never tell the patient to stop a doctor-prescribed medication outright. If they mentioned medications, give cautious general guidance (e.g., continue as prescribed unless symptoms worsen, or consult a pharmacist/doctor before any change). If no medications were mentioned, leave the field as "".
Recommendation rules (mandatory):
- Each recommendation must be directly tied to the patient's specific symptoms, duration, severity, and age — no empty generic tips like "drink water", "eat light food", "get enough rest", or "see your doctor to determine the cause".
- Do not repeat a "see your doctor to determine the cause" tip in recommendations; that belongs in when_to_seek_care.
- title must be a very short heading (3-5 words), and tip is the explanation in one or two sentences.
- Never recommend specific drugs, doses, or painkillers.
- When talking about eye/nose irritants or allergies, never use the word "vaccines" — use "pollutants" or "irritants" instead.
- The source and URL must be copied exactly from the knowledge-base context above.
- Write 4 distinct recommendations, each specifically relevant to this case.
Reply with JSON only. All text must be in English only:
{{"personal_note":"one or two empathetic, personalized sentences addressing the patient directly based on their specific situation (not generic)","urgency":"low|medium|high","urgency_text":"Simple|Needs appointment|Emergency","confidence":"high|medium|low","simple_explanation":"a very simple explanation in English, one or two sentences for non-experts, no complex medical jargon, clear and friendly","possible_conditions":"Possible conditions in English only (3 sentences, no definitive diagnosis)","recommendations":[{{"title":"very short heading (3-5 words)","tip":"explanation in one or two sentences tied to the symptoms","source":"source name like Mayo Clinic","source_url":"https://..."}},{{"title":"short heading","tip":"explanation","source":"source name","source_url":"https://..."}},{{"title":"short heading","tip":"explanation","source":"source name","source_url":"https://..."}},{{"title":"short heading","tip":"explanation","source":"source name","source_url":"https://..."}}],"danger_signs":"Danger signs in English only","when_to_seek_care":"When to see a doctor in English only","home_care":"Home care in English as a list of short safe cautious bullet points (never name specific products, drugs, or eye drops)","medication_guidance":"cautious guidance about continuing medication or consulting a doctor/pharmacist, or empty if no medications mentioned","questions_for_doctor":"3-4 smart questions in English the patient should ask their doctor based on their case"}}"""


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
            {"title": "الراحة والاسترخاء", "tip": "احصل على قسط كافٍ من الراحة والنوم.", "source": "Mayo Clinic", "url": "https://www.mayoclinic.org/"},
            {"title": "الترطيب الجيد", "tip": "اشرب سوائل بانتظام على مدار اليوم.", "source": "NHS", "url": "https://www.nhs.uk/"},
            {"title": "مراقبة الأعراض", "tip": "راقب حرارتك وشدة الألم وسجّل أي تغيّر.", "source": "CDC", "url": "https://www.cdc.gov/"},
            {"title": "المتابعة الطبية", "tip": "راجع الطبيب إذا لم تتحسن الأعراض خلال أيام.", "source": "WHO", "url": "https://www.who.int/"},
        ]
        return {
            "personal_note": note, "urgency": u, "urgency_ar": ur_ar, "confidence": "low",
            "possible_conditions": conditions, "recommendations": tips,
            "danger_signs": "ضيق تنفس شديد، ألم في الصدر، تشوش، إغماء، أو تدهور مفاجئ.",
            "when_to_seek_care": "راجع الطبيب فوراً أو الطوارئ إذا استمرت الأعراض أو ازدادت سوءاً.",
            "home_care": "• امنح نفسك قسطاً كافياً من الراحة.\n• اشرب سوائل كافية على مدار اليوم.\n• راقب الأعراض وسجّل أي تغيّر.\n• ارجع للطبيب إذا استمرت الأعراض أو ازدادت سوءاً.",
            "medication_guidance": ("استمر بدوائك الموصوف كما وصفه الطبيب، وراجع الطبيب أو "
                                    "الصيدلي قبل أي تغيير." if d.get("medications") else ""),
            "simple_explanation": "الأعراض التي تشعر بها تحتاج انتباهك، والأفضل مراجعة طبيب لتقييم الحالة بدقة والتأكد من عدم وجود شيء خطير.",
            "questions_for_doctor": "متى يجب أن أقلق من هذه الأعراض؟ ما الفحوصات المطلوبة؟ متى أتحسن؟",
        }
    ur_en = {"high": "Emergency", "medium": "Needs appointment", "low": "Simple"}[u]
    return {
        "personal_note": f"Based on what you reported ({syms}) with severity {sev}/5, caution is advised; do not hesitate to see a doctor. This is awareness information, not a final diagnosis.",
        "urgency": u, "urgency_text": ur_en, "confidence": "low",
        "possible_conditions": "Symptoms may come from a simple treatable condition, but a doctor visit is recommended given the current severity.",
        "recommendations": [
            {"title": "Rest and relax", "tip": "Get enough rest and sleep.", "source": "Mayo Clinic", "url": "https://www.mayoclinic.org/"},
            {"title": "Stay hydrated", "tip": "Drink fluids regularly through the day.", "source": "NHS", "url": "https://www.nhs.uk/"},
            {"title": "Monitor symptoms", "tip": "Monitor temperature and pain and note any change.", "source": "CDC", "url": "https://www.cdc.gov/"},
            {"title": "Medical follow-up", "tip": "See a doctor if symptoms do not improve in a few days.", "source": "WHO", "url": "https://www.who.int/"},
        ],
        "danger_signs": "Severe shortness of breath, chest pain, confusion, fainting, or sudden worsening.",
        "when_to_seek_care": "See a doctor or emergency care immediately if symptoms persist or worsen.",
        "home_care": "• Get enough rest.\n• Drink enough fluids through the day.\n• Monitor symptoms and note any change.\n• See a doctor if symptoms persist or worsen.",
        "medication_guidance": "Continue your prescribed medication as directed and consult your doctor or pharmacist before any change." if d.get("medications") else "",
        "simple_explanation": "The symptoms you're feeling need attention, and it's best to see a doctor for an accurate assessment to rule out anything serious.",
        "questions_for_doctor": "When should I worry about these symptoms? What tests are needed? When will I improve?",
    }


def _needed_information(d, bundle, lang):
    ar = lang == "ar"
    items = []
    if not d.get("duration"):
        items.append("مدة الأعراض" if ar else "Symptom duration")
    if d.get("severity") in (None, "", 0):
        items.append("شدة الأعراض" if ar else "Symptom severity")
    if not d.get("location") and any(x in " ".join(map(str, d.get("symptoms") or [])).lower() for x in ("pain", "ألم", "وجع")):
        items.append("مكان الألم" if ar else "Symptom/pain location")
    if not d.get("notes"):
        items.append("الأعراض المصاحبة أو تفاصيل إضافية" if ar else "Associated symptoms or additional details")
    if not d.get("conditions"):
        items.append("التاريخ الصحي ذي الصلة، إن وجد" if ar else "Relevant medical history, if any")
    unmatched = ((bundle.get("normalization") or {}).get("unmatched") or [])
    if unmatched:
        items.append("توضيح وصف بعض الأعراض غير المعروفة" if ar else "Clarification of unrecognized symptom wording")
    # Keep the request focused rather than asking for everything.
    return items[:5]



def assess_data_quality(patient, lang="ar", bundle=None):
    """Return a transparent completeness/validity score for the current analysis input.

    This score measures only whether information needed by the existing analysis flow
    is available. It is NOT a disease probability, diagnostic accuracy estimate, or
    statement about the user's health.
    """
    d = dict(patient or {})
    lang = "en" if lang == "en" else "ar"
    ar = lang == "ar"
    if bundle is None:
        try:
            bundle = medical_knowledge.knowledge_bundle(
                d.get("symptoms") or [], d.get("severity", 1), d.get("age"),
                d.get("notes", ""), lang,
            )
        except Exception:
            bundle = {"normalization": {"canonical": [], "unmatched": d.get("symptoms") or []}}
    norm = bundle.get("normalization") or {}
    canonical = norm.get("canonical") or []
    raw_symptoms = [str(x).strip() for x in (d.get("symptoms") or []) if str(x).strip()]

    try:
        age = int(d.get("age")) if d.get("age") not in (None, "") else None
    except Exception:
        age = None
    try:
        severity = int(d.get("severity")) if d.get("severity") not in (None, "") else None
    except Exception:
        severity = None
    gender = str(d.get("gender") or "").strip().lower()
    duration = str(d.get("duration") or "").strip()
    history_answered = bool(d.get("history_answered")) or any(
        str(d.get(k) or "").strip() for k in ("conditions", "medications", "allergies")
    )

    fields = []
    def add(key, label_ar, label_en, weight, required, status, detail_ar="", detail_en=""):
        fields.append({
            "key": key,
            "label": label_ar if ar else label_en,
            "weight": int(weight),
            "required": bool(required),
            "status": status,
            "provided": status == "provided",
            "detail": detail_ar if ar else detail_en,
        })

    # Required fields reflect the current production analysis path.
    if canonical:
        add("main_symptom", "العرض الرئيسي", "Main symptom", 30, True, "provided",
            "تم التعرف على عرض واحد على الأقل في قاعدة المعرفة.",
            "At least one symptom was recognized in the medical knowledge base.")
    elif raw_symptoms:
        add("main_symptom", "العرض الرئيسي", "Main symptom", 30, True, "needs_clarification",
            "تم إدخال عرض لكن يحتاج إلى صياغة أو تحديد أوضح.",
            "A symptom was entered but needs clearer wording or selection.")
    else:
        add("main_symptom", "العرض الرئيسي", "Main symptom", 30, True, "missing")

    add("duration", "مدة الأعراض", "Symptom duration", 20, True,
        "provided" if duration else "missing")
    add("severity", "شدة الأعراض", "Symptom severity", 20, True,
        "provided" if severity is not None and 1 <= severity <= 5 else "missing")

    # Recommended context used by risk/safety or to reduce ambiguity.
    add("age", "العمر", "Age", 10, False,
        "provided" if age is not None and 1 <= age <= 120 else "missing")
    add("gender", "الجنس", "Gender", 5, False,
        "provided" if gender in {"m", "f", "male", "female", "ذكر", "أنثى", "انثى"} else "missing")
    add("associated_symptoms", "الأعراض المصاحبة", "Associated symptoms", 10, False,
        "provided" if len(canonical) >= 2 else "missing",
        "وجود أكثر من عرض معروف يعطي سياقًا إضافيًا عند توفره.",
        "More than one recognized symptom provides additional context when available.")
    add("relevant_history", "التاريخ الصحي ذي الصلة", "Relevant medical history", 5, False,
        "provided" if history_answered else "missing",
        "يكفي أن يذكر المستخدم المعلومات ذات الصلة أو يوضح عدم وجودها.",
        "It is enough for the user to provide relevant history or explicitly indicate none.")

    total_weight = sum(x["weight"] for x in fields)
    earned = 0.0
    for item in fields:
        if item["status"] == "provided":
            earned += item["weight"]
        elif item["status"] == "needs_clarification":
            # The information exists, but its validity for analysis is incomplete.
            earned += item["weight"] * 0.5
    score = int(round(earned * 100 / total_weight)) if total_weight else 0

    required = [x for x in fields if x["required"]]
    recommended = [x for x in fields if not x["required"]]
    req_total = sum(x["weight"] for x in required) or 1
    rec_total = sum(x["weight"] for x in recommended) or 1
    req_earned = sum(x["weight"] if x["status"] == "provided" else (x["weight"] * .5 if x["status"] == "needs_clarification" else 0) for x in required)
    rec_earned = sum(x["weight"] if x["status"] == "provided" else 0 for x in recommended)
    required_completion = int(round(req_earned * 100 / req_total))
    recommended_completion = int(round(rec_earned * 100 / rec_total))

    sufficient = all(x["status"] == "provided" for x in required)
    level = "excellent" if score >= 90 else ("good" if score >= 70 else ("limited" if score >= 50 else "insufficient"))
    labels = {
        "ar": {"excellent": "ممتاز", "good": "جيد", "limited": "محدود", "insufficient": "غير كافٍ"},
        "en": {"excellent": "Excellent", "good": "Good", "limited": "Limited", "insufficient": "Insufficient"},
    }
    missing = [x for x in fields if x["status"] != "provided"]
    return {
        "score": score,
        "level": level,
        "level_label": labels[lang][level],
        "sufficient": sufficient,
        "required_completion": required_completion,
        "recommended_completion": recommended_completion,
        "fields": fields,
        "missing": [{"key": x["key"], "label": x["label"], "status": x["status"], "required": x["required"]} for x in missing],
        "meaning": (
            "تقيس هذه النسبة اكتمال المعلومات المتاحة للتحليل فقط، ولا تمثل احتمال مرض أو دقة تشخيص."
            if ar else
            "This score measures information completeness only; it is not a disease probability or diagnostic accuracy score."
        ),
    }


def _influence_from_weight(weight, max_weight):
    try:
        ratio = float(weight or 0) / float(max_weight or 1)
    except Exception:
        ratio = 0
    return "high" if ratio >= .67 else ("medium" if ratio >= .34 else "low")


def build_explainability(patient, bundle, lang="ar", ml_explanation=None):
    """Explain the *actual displayed assessment* without inventing feature importance.

    Displayed conditions come from the Medical Knowledge Base matching engine and
    displayed risk comes from deterministic safety/triage rules. The auxiliary
    BernoulliNB model is explicitly marked as not used for the displayed result.
    """
    d = dict(patient or {})
    lang = "en" if lang == "en" else "ar"
    ar = lang == "ar"
    factors = []
    condition_evidence = []
    risk = bundle.get("risk") or {}
    matches = bundle.get("matches") or []

    for reason in risk.get("reasons") or []:
        factors.append({
            "key": "safety_rule",
            "label": reason.get("name") or ("قاعدة أمان" if ar else "Safety rule"),
            "influence": "high" if reason.get("risk_level") == "urgent" else "medium",
            "source": "safety_rules",
            "detail": reason.get("description") or reason.get("message") or "",
        })

    top = matches[0] if matches else None
    if top:
        matched = top.get("matched_symptoms") or []
        max_w = max((float(x.get("weight") or 0) for x in matched), default=1.0)
        for symptom in matched:
            nm = symptom.get("name_ar") if ar else symptom.get("name_en")
            factors.append({
                "key": "symptom_match",
                "label": nm or symptom.get("slug") or ("عرض مطابق" if ar else "Matched symptom"),
                "influence": _influence_from_weight(symptom.get("weight"), max_w),
                "source": "knowledge_match",
                "detail": symptom.get("notes") or (
                    "هذا العرض مرتبط بهذه الإمكانية داخل قاعدة المعرفة الطبية."
                    if ar else
                    "This symptom is linked to this possibility in the medical knowledge base."
                ),
            })

    for match in matches[:3]:
        condition_evidence.append({
            "condition": match.get("name_ar") if ar else match.get("name_en"),
            "match_level": match.get("match_level"),
            "matched_symptoms": [
                (x.get("name_ar") if ar else x.get("name_en")) for x in (match.get("matched_symptoms") or [])
                if (x.get("name_ar") or x.get("name_en"))
            ],
        })

    # Severity and age are shown only when they actually triggered the existing
    # clinical-review rule. They are not falsely attributed to the ML model.
    if any((r.get("slug") == "clinical-review") for r in (risk.get("reasons") or [])):
        try:
            sev = int(d.get("severity") or 0)
        except Exception:
            sev = 0
        if sev >= 4:
            factors.append({
                "key": "severity_rule", "label": "شدة الأعراض" if ar else "Symptom severity",
                "influence": "high", "source": "clinical_review_rule",
                "detail": "ساهمت الشدة المرتفعة في رفع مستوى المتابعة وفق قاعدة التقييم الحالية." if ar else "Higher severity contributed to the follow-up level under the current review rule.",
            })
        try:
            age = int(d.get("age")) if d.get("age") not in (None, "") else None
        except Exception:
            age = None
        if age is not None and age >= 65:
            factors.append({
                "key": "age_rule", "label": "العمر" if ar else "Age",
                "influence": "medium", "source": "clinical_review_rule",
                "detail": "دخل العمر في قاعدة المراجعة الطبية عندما اقترن بأعراض محددة." if ar else "Age was used by the medical-review rule when combined with specific symptoms.",
            })

    return {
        "basis": "medical_knowledge_and_safety_rules",
        "basis_label": "مطابقة قاعدة المعرفة + قواعد الأمان" if ar else "Medical knowledge matching + safety rules",
        "factors": factors,
        "condition_evidence": condition_evidence,
        "auxiliary_model": ml_explanation or {"available": False, "used_for_display": False},
        "auxiliary_model_note": (
            "يوجد نموذج Bernoulli Naive Bayes مساعد، لكن الاحتمالات الطبية المعروضة للمستخدم لا تُبنى عليه مباشرة؛ لذلك لا نعرض درجاته كأسباب لهذا التقييم."
            if ar else
            "An auxiliary Bernoulli Naive Bayes model exists, but the medical possibilities shown to the user are not directly determined by it, so its scores are not presented as reasons for this assessment."
        ),
        "meaning": (
            "العوامل المعروضة هي معلومات ساهمت في المطابقة أو قواعد الأمان. وهي لا تؤكد تشخيصًا ولا تحدد سبب الأعراض."
            if ar else
            "The factors shown contributed to matching or safety rules. They do not confirm a diagnosis or identify the cause of symptoms."
        ),
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

    # The structured knowledge and rule-based safety layers always run before AI.
    # They are the authority for possible conditions, sources, and risk level.
    try:
        bundle = medical_knowledge.knowledge_bundle(
            d.get("symptoms", []), d.get("severity", 1), d.get("age"),
            d.get("notes", ""), lang,
        )
    except Exception:
        bundle = {"normalization": {"canonical": [], "unmatched": d.get("symptoms", [])},
                  "matches": [], "sources": [],
                  "risk": {"level": "review", "label": "🟡 يحتاج مراجعة طبية" if lang == "ar" else "🟡 Needs medical review", "reasons": [], "emergency": False},
                  "last_updated": None}

    data_quality = assess_data_quality(d, lang, bundle=bundle)

    # Preserve the app's existing broad red-flag detector as a second,
    # independent rule layer. If either ruleset says emergency, safety/urgency
    # overrides the action advice, but grounded knowledge-base matches are kept
    # visible as non-diagnostic possibilities so the user still understands what
    # may fit the reported symptoms. They must never delay urgent care.
    pre_triage = _triage(d, lang)
    if pre_triage.get("level") == "emergency" and bundle.get("risk", {}).get("level") != "urgent":
        safety_reason = pre_triage.get("reason") or (
            "بعض الأعراض المذكورة قد تستدعي رعاية طبية عاجلة."
            if lang == "ar" else
            "Some reported symptoms may require urgent medical care."
        )
        bundle["risk"] = {
            "level": "urgent",
            "label": "🔴 يحتاج رعاية عاجلة" if lang == "ar" else "🔴 Urgent",
            "reasons": [{
                "slug": "legacy-safety-layer",
                "name": "علامة خطر" if lang == "ar" else "Red flag",
                "risk_level": "urgent",
                "message": safety_reason,
            }],
            "emergency": True,
        }
    elif pre_triage.get("level") in {"today", "soon"} and bundle.get("risk", {}).get("level") == "low":
        bundle["risk"] = {
            "level": "review",
            "label": "🟡 يحتاج مراجعة طبية" if lang == "ar" else "🟡 Needs medical review",
            "reasons": [{
                "slug": "legacy-clinical-review-layer",
                "name": "تقييم طبي" if lang == "ar" else "Medical review",
                "risk_level": "review",
                "message": pre_triage.get("reason") or (
                    "تحتاج الأعراض إلى متابعة طبية."
                    if lang == "ar" else
                    "The symptoms need medical follow-up."
                ),
            }],
            "emergency": False,
        }

    d["_knowledge_context"] = _knowledge_prompt_context(bundle, lang)
    if bundle.get("risk", {}).get("level") == "urgent":
        result = _urgent_result(bundle, lang)
    elif not bundle.get("matches"):
        result = _fallback_result(d, lang)
    else:
        # PERFORMANCE + RELIABILITY: the symptom-result screen must not wait for
        # an external LLM call. The medical possibilities, risk, sources and
        # follow-up guidance are already produced by the verified knowledge base
        # and deterministic safety rules below. Waiting up to 45 seconds for Groq
        # only delayed the UI and did not determine the displayed condition.
        # Keep generative AI for the separate assistant/follow-up chat instead.
        top = (bundle.get("matches") or [{}])[0]
        top_name = top.get("name_ar") if lang == "ar" else top.get("name_en")
        matched_names = [
            (x.get("name_ar") if lang == "ar" else x.get("name_en"))
            for x in (top.get("matched_symptoms") or [])
            if (x.get("name_ar") or x.get("name_en"))
        ]
        if lang == "ar":
            result = {
                "personal_note": ("الحالة الأقرب حسب المعلومات الحالية: " + str(top_name or "—") + "."),
                "simple_explanation": (("ظهر هذا الاحتمال بسبب توافق: " + "، ".join(matched_names[:4]) + ".") if matched_names else "ظهر هذا الاحتمال من مطابقة الأعراض مع قاعدة المعرفة الطبية."),
                "urgency": "low", "urgency_ar": "بسيط", "confidence": "medium",
                "possible_conditions": "", "recommendations": [],
                "danger_signs": "", "when_to_seek_care": "", "home_care": "",
                "medication_guidance": "", "questions_for_doctor": "",
            }
        else:
            result = {
                "personal_note": ("Closest current match: " + str(top_name or "—") + "."),
                "simple_explanation": (("This match was supported by: " + ", ".join(matched_names[:4]) + ".") if matched_names else "This possibility comes from matching the reported symptoms with the medical knowledge base."),
                "urgency": "low", "urgency_text": "Simple", "confidence": "medium",
                "possible_conditions": "", "recommendations": [],
                "danger_signs": "", "when_to_seek_care": "", "home_care": "",
                "medication_guidance": "", "questions_for_doctor": "",
            }

    # These fields are always deterministic and grounded in active, verified KB rows.
    if bundle.get("risk", {}).get("level") == "urgent":
        # Keep source-grounded possibilities visible even in urgent cases. Risk
        # remains urgent and treatment/home-care recommendations stay withheld so
        # the possibilities cannot be mistaken for permission to wait.
        result["possible_conditions"] = _render_possible_conditions(bundle.get("matches") or [], lang)
        result["recommendations"] = []
        if bundle.get("matches"):
            result["simple_explanation"] = (
                "توجد احتمالات متوافقة مع بعض الأعراض، لكنها لا تفسر علامة الخطر بشكل مؤكد ولا تُعد تشخيصًا. الأولوية الآن للتقييم الطبي العاجل."
                if lang == "ar" else
                "Some possibilities match parts of the symptom pattern, but they do not confirm the cause of the red flag or establish a diagnosis. Urgent medical assessment remains the priority."
            )
    else:
        result["possible_conditions"] = _render_possible_conditions(bundle.get("matches") or [], lang)
        result["recommendations"] = _knowledge_recommendations(bundle, lang)
        # Safety, medication, follow-up, and red-flag wording must come from
        # deterministic data/rules rather than generated model output.
        result.update(_grounded_guidance(bundle, d, lang))
    top_match_level = ((bundle.get("matches") or [{}])[0]).get("match_level")
    result["confidence"] = ({"strong": "high", "moderate": "medium", "weak": "low"}.get(top_match_level, "low"))
    assessment_status = "complete"
    needed_information = []
    # Safe uncertainty mode: incomplete required information or weak/no grounded
    # match never becomes a forced diagnosis. Red flags still override this gate.
    if bundle.get("risk", {}).get("level") != "urgent" and (not data_quality.get("sufficient") or not bundle.get("matches") or result.get("confidence") == "low"):
        assessment_status = "insufficient" if (not data_quality.get("sufficient") or not bundle.get("matches")) else "low_confidence"
        needed_information = _needed_information(d, bundle, lang)
        quality_missing = [x.get("label") for x in (data_quality.get("missing") or []) if x.get("required") and x.get("label")]
        for item in quality_missing:
            if item not in needed_information:
                needed_information.insert(0, item)
        needed_information = needed_information[:5]
        result["possible_conditions"] = ""
        result["recommendations"] = []
        result["personal_note"] = (
            "🧠 المعلومات المتوفرة غير كافية لإجراء تقييم موثوق. أضف معلومات إضافية أو راجع المصادر الطبية الموثوقة، واطلب تقييمًا طبيًا إذا استمرت الأعراض أو ساءت."
            if lang == "ar" else
            "🧠 The available information is not sufficient for a reliable assessment. Add more information or review trusted medical sources, and seek professional evaluation if symptoms persist or worsen."
        )
        result["simple_explanation"] = (
            "لن يعرض SymptoSense احتمالًا طبيًا عندما تكون المعلومات أو المطابقة غير كافية."
            if lang == "ar" else
            "SymptoSense will not show a medical possibility when the information or grounded match is insufficient."
        )

    display_matches = [] if assessment_status in {"insufficient", "low_confidence"} else (bundle.get("matches") or [])

    triage = pre_triage
    risk_level = bundle.get("risk", {}).get("level", "low")
    if risk_level == "urgent":
        triage = {"level": "emergency", "label": _triage_label("emergency", lang),
                  "reason": "\n".join("• " + str(r.get("message") or r.get("name") or "") for r in bundle.get("risk", {}).get("reasons", []))}
    elif risk_level == "review" and triage.get("level") == "monitor":
        triage = {"level": "soon", "label": _triage_label("soon", lang),
                  "reason": "\n".join("• " + str(r.get("message") or r.get("name") or "") for r in bundle.get("risk", {}).get("reasons", []))}

    # The displayed urgency is derived only from the independent safety/triage layers.
    urgency = "high" if triage["level"] == "emergency" else ("medium" if triage["level"] in ("today", "soon") else "low")
    result["urgency"] = urgency
    result["urgency_ar" if lang == "ar" else "urgency_text"] = ({
        "ar": {"high": "طوارئ", "medium": "يحتاج مراجعة طبية", "low": "خطورة منخفضة"},
        "en": {"high": "Urgent", "medium": "Needs medical review", "low": "Low risk"},
    })[lang][urgency]
    rule_flag = urgency == "high"
    low_conf = result.get("confidence") == "low"

    predicted = []
    ml_explanation = {"available": False, "used_for_display": False}
    try:
        normalized_for_ml = _normalize_symptoms(d.get("symptoms", []))
        predicted = ml_diagnosis.predict_conditions(normalized_for_ml) or []
        ml_explanation = ml_diagnosis.explain_prediction(normalized_for_ml)
    except Exception:
        predicted = []
        ml_explanation = {"available": False, "used_for_display": False}
    explainability = build_explainability(d, bundle, lang, ml_explanation=ml_explanation)

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
            d.get("member_id", 0),
        )
        if record_id:
            db.save_result(
                user_id, record_id,
                {
                    "lang": lang,
                    "age": d.get("age"),
                    "gender": d.get("gender"),
                    "symptoms": d.get("symptoms", []),
                    "duration": d.get("duration"),
                    "severity": d.get("severity"),
                    "conditions": d.get("conditions", ""),
                    "medications": d.get("medications", ""),
                    "allergies": d.get("allergies", ""),
                    "notes": d.get("notes", ""),
                    "urgency": result.get("urgency", "low"),
                    "possible_conditions": result.get("possible_conditions", ""),
                    "recommendations": [
                        {
                            "title": (r.get("title") or ""),
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
                    "risk_level": risk_level,
                    "risk_label": bundle.get("risk", {}).get("label", ""),
                    "risk_reasons": bundle.get("risk", {}).get("reasons", []),
                    "emergency": bool(bundle.get("risk", {}).get("emergency")),
                    "knowledge_matches": display_matches,
                    "medical_sources": bundle.get("sources", []),
                    "symptom_normalization": bundle.get("normalization", {}),
                    "knowledge_last_updated": bundle.get("last_updated"),
                    "why_result": _why_result(bundle, lang),
                    "assessment_status": assessment_status,
                    "needed_information": needed_information,
                    "confidence": result.get("confidence", "low"),
                    "data_quality": data_quality,
                    "explainability": explainability,
                    "location": d.get("location", ""),
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
        "data_quality": data_quality,
        "explainability": explainability,
        "assessment_status": assessment_status,
        "needed_information": needed_information,
        "rule_forced_high": rule_flag,
        "possible_conditions": _md_safe(result.get("possible_conditions", ""), lang),
        "recommendations": [
            {
                "title": (r.get("title") or ""),
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
        "simple_explanation": _md_safe(result.get("simple_explanation", ""), lang),
        "questions_for_doctor": _md_safe(result.get("questions_for_doctor", ""), lang),
        "risk_level": risk_level,
        "risk_label": bundle.get("risk", {}).get("label", ""),
        "risk_reasons": bundle.get("risk", {}).get("reasons", []),
        "knowledge_matches": display_matches,
        "medical_sources": bundle.get("sources", []),
        "symptom_normalization": bundle.get("normalization", {}),
        "knowledge_last_updated": bundle.get("last_updated"),
        "why_result": _md_safe(_why_result(bundle, lang), lang),
        "emergency": bool(bundle.get("risk", {}).get("emergency")),
        "emergency_flags": [r.get("name") or r.get("message") for r in bundle.get("risk", {}).get("reasons", []) if r.get("name") or r.get("message")],
        "ml_predictions": predicted,
        # Kept for backward-compatible API consumers, but never presented as
        # a medical possibility until mapped to active KB rows and sources.
        "ml_grounded": False,
        "med_warnings": med_matches,
        "record_id": record_id,
        "triage_level": triage["level"],
        "triage_label": triage["label"],
        "triage_reason": triage["reason"],
    }
