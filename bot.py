import os
import io
import json
import logging
import re
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from groq import Groq
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, CallbackQueryHandler, filters, ContextTypes
import db
import local_diagnosis

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

ADMIN_ID = os.environ.get("ADMIN_TELEGRAM_ID", "")

def is_admin(update: Update) -> bool:
    return bool(ADMIN_ID) and str(update.effective_user.id) == str(ADMIN_ID)

# Used only to render readable chart labels (matplotlib can't shape Arabic script).
SYMPTOM_EN = {
    "صداع": "Headache", "حمى": "Fever", "سعال": "Cough",
    "ألم في الصدر": "Chest Pain", "غثيان": "Nausea", "تعب وإرهاق": "Fatigue",
    "ضيق التنفس": "Shortness of Breath", "دوار": "Dizziness", "ألم المفاصل": "Joint Pain",
    "ألم في البطن": "Stomach Pain", "قشعريرة": "Chills", "احمرار العيون": "Red Eyes",
}

LANG, AGE, GENDER, SYMPTOMS, DURATION, SEVERITY, CONDITIONS, NOTES, FOLLOWUP, LOCATION = range(10)

TEXTS = {
    "ar": {
        "welcome": "مرحباً بك في SymptoSense 🏥\nمساعدك الذكي لتحليل الأعراض وتقديم تقييم أولي بناءً على ممصادر طبية موثوقة.",
        "choose_lang": "لنبدأ. الرجاء اختيار اللغة\nPlease choose your language:",
        "ask_age": "كم عمرك؟ (اكتب رقم فقط، مثال: 28)",
        "invalid_age": "يرجى إدخال عمر صحيح بين 1 و 120",
        "ask_gender": "ما جنسك؟",
        "male": "👨 ذكر",
        "female": "👩 أنثى",
        "invalid_gender": "اختر أحد الخيارين",
        "ask_symptoms": "ما هي أعراضك؟\nاختر من الأزرار أو اكتب بنفسك.\nاضغط ✅ انتهيت عند الانتهاء",
        "symptom_added": "تمت الإضافة! ({} أعراض)\nاضف المزيد أو اضغط ✅ انتهيت",
        "ask_duration": "كم مدة هذه الأعراض؟",
        "ask_severity": "ما شدة الألم؟\n1️⃣ خفيف جداً\n2️⃣ معتدل\n3️⃣ متوسط\n4️⃣ شديد\n5️⃣ حرج جداً",
        "ask_conditions": "هل لديك أمراض مزمنة سابقة؟",
        "ask_notes": "أي ملاحظات إضافية؟ (أو اضغط تخطي)",
        "analyzing": "جاري التحليل... ⏳",
        "summary": "ملخص: عمر {} | {} | أعراض: {}",
        "result_title": "نتيجة التحليل - SymptoSense 🏥",
        "urgency_label": "مستوى الخطورة",
        "conditions_label": "الاحتمالات المحتملة 🔬",
        "recommendations_label": "التوصيات 📋",
        "home_care_label": "الرعاية المنزلية 🏠",
        "danger_label": "علامات خطر 🚨",
        "when_label": "متى تراجع الطبيب 📅",
        "sources_label": "مصادر موثوقة 📚",
        "disclaimer": "⚠️ هذا التحليل للتوعية فقط ولا يغني عن استشارة طبيب مختص.",
        "signature": "\n💚 معكم ريماس، وأتمنى إني أفدتكم. لو عندكم أي استفسار أو سؤال، هذا حسابي: @rms_2o",
        "followup_prompt": "💬 عندك سؤال متابعة عن حالتك؟ اكتبه هنا وبجاوبك عليه.\n(أو اضغطي \"🔄 تحليل جديد\" للبدء من جديد)",
        "followup_thinking": "🤔 لحظة، أفكر بسؤالك...",
        "followup_error": "⚠️ صار خطأ بالرد على سؤالك، حاولي مرة ثانية أو اضغطي \"🔄 تحليل جديد\".",
        "new_analysis": "🔄 تحليل جديد",
        "cancelled": "تم الإلغاء. /start للبدء من جديد",
        "skip": "⏭️ تخطي",
        "done": "✅ انتهيت",
        "no_conditions": "لا يوجد أمراض سابقة",
        "write_manually": "✏️ كتابة يدوية",
        "add_symptom_first": "أضف عرضاً واحداً على الأقل!",
        "invalid_choice": "اختر من الأزرار",
        "error": "حدث خطأ. اكتب /start للمحاولة مجدداً",
        "duration_options": [["أقل من 24 ساعة", "1-3 أيام"], ["4-7 أيام", "1-2 أسبوع"], ["أكثر من أسبوعين", "أكثر من شهر"]],
        "severity_options": [["1️⃣ خفيف جداً", "2️⃣ معتدل"], ["3️⃣ متوسط", "4️⃣ شديد"], ["5️⃣ حرج جداً"]],
        "severity_map": {"1️⃣ خفيف جداً": 1, "2️⃣ معتدل": 2, "3️⃣ متوسط": 3, "4️⃣ شديد": 4, "5️⃣ حرج جداً": 5},
        "conditions_kb": [["لا يوجد أمراض سابقة"], ["سكري", "ضغط الدم"], ["أمراض قلب", "ربو"], ["✏️ كتابة يدوية"]],
        "quick_symptoms": [["صداع", "حمى", "سعال"], ["ألم في الصدر", "غثيان", "تعب وإرهاق"], ["ضيق التنفس", "دوار", "ألم المفاصل"], ["ألم في البطن", "قشعريرة", "احمرار العيون"], ["✅ انتهيت"]],
        "sev_labels": {1:"خفيف جداً", 2:"معتدل", 3:"متوسط", 4:"شديد", 5:"حرج جداً"},
        "sources": [
            ("Mayo Clinic", "https://www.mayoclinic.org"),
            ("MedlinePlus", "https://medlineplus.gov"),
            ("World Health Organization", "https://www.who.int"),
            ("NHS", "https://www.nhs.uk"),
        ],
        "prompt_lang": "ar",
        "memory_label": "🕐 مقارنة بزيارتك السابقة",
        "memory_same": "راجعتنا قبل {} يوم بأعراض مشابهة ({}). ",
        "memory_worse": "لاحظنا إن الشدة زادت من {}/5 إلى {}/5 منذ آخر مرة. ",
        "memory_better": "يبدو إن الشدة تحسّنت من {}/5 إلى {}/5 منذ آخر مرة. ",
        "memory_new": "هذي أول مرة تسجّل فيها هالأعراض معنا.",
        "trends_button": "📊 اتجاهات هذا الأسبوع",
        "trends_title": "رادار الأعراض المجتمعي 📊",
        "trends_period": "هذي أكثر الأعراض اللي أبلغ عنها مستخدمين البوت خلال آخر 7 أيام (عدد الحالات: {})",
        "trends_empty": "ما فيه بيانات كافية بعد لعرض الاتجاهات. جرب لاحقاً بعد ما يستخدم البوت أكثر الناس.",
        "trends_footer": "\n⚠️ هذي إحصائية عامة للتوعية فقط، ما تمثل تشخيصاً طبياً.",
        "trends_small_sample": "\nℹ️ ملاحظة: العدد لسا قليل، فالنسب المئوية بتتغير بسرعة كل ما يستخدم البوت أشخاص أكثر.",
        "infermedica_label": "🔬 تحقق من قاعدة معرفة طبية",
        "infermedica_note": "درجة التطابق بين الأعراض اللي ذكرتها وأعراض شائعة لكل حالة (مو نسبة تشخيص دقيقة أو احتمال طبي)",
    },
    "en": {
        "welcome": "Welcome to SymptoSense 🏥\nYour smart assistant for symptom analysis based on trusted medical sources.",
        "choose_lang": "Please choose your language:\nالرجاء اختيار اللغة:",
        "ask_age": "How old are you? (enter a number, e.g. 28)",
        "invalid_age": "Please enter a valid age between 1 and 120",
        "ask_gender": "What is your gender?",
        "male": "👨 Male",
        "female": "👩 Female",
        "invalid_gender": "Please choose one of the options",
        "ask_symptoms": "What are your symptoms?\nChoose from the buttons or type your own.\nPress ✅ Done when finished",
        "symptom_added": "Added! ({} symptoms)\nAdd more or press ✅ Done",
        "ask_duration": "How long have you had these symptoms?",
        "ask_severity": "What is the severity of your pain?\n1️⃣ Very Mild\n2️⃣ Moderate\n3️⃣ Medium\n4️⃣ Severe\n5️⃣ Critical",
        "ask_conditions": "Do you have any chronic medical conditions?",
        "ask_notes": "Any additional notes? (or press Skip)",
        "analyzing": "Analyzing... ⏳",
        "summary": "Summary: Age {} | {} | Symptoms: {}",
        "result_title": "Analysis Result - SymptoSense 🏥",
        "urgency_label": "Urgency Level",
        "conditions_label": "Possible Conditions 🔬",
        "recommendations_label": "Recommendations 📋",
        "home_care_label": "Home Care 🏠",
        "danger_label": "Danger Signs 🚨",
        "when_label": "When to See a Doctor 📅",
        "sources_label": "Trusted Sources 📚",
        "disclaimer": "⚠️ This analysis is for awareness only and does not replace consulting a doctor.",
        "signature": "\n💚 This is Reemas, I hope this was helpful. For any questions, reach me here: @rms_2o",
        "followup_prompt": "💬 Have a follow-up question about your case? Type it here and I'll answer.\n(Or tap \"🔄 New Analysis\" to start over)",
        "followup_thinking": "🤔 One moment, thinking about your question...",
        "followup_error": "⚠️ Something went wrong answering your question. Try again or tap \"🔄 New Analysis\".",
        "new_analysis": "🔄 New Analysis",
        "cancelled": "Cancelled. Type /start to begin again",
        "skip": "⏭️ Skip",
        "done": "✅ Done",
        "no_conditions": "No previous conditions",
        "write_manually": "✏️ Type manually",
        "add_symptom_first": "Please add at least one symptom!",
        "invalid_choice": "Please choose from the buttons",
        "error": "An error occurred. Type /start to try again",
        "duration_options": [["Less than 24 hours", "1-3 days"], ["4-7 days", "1-2 weeks"], ["More than 2 weeks", "More than a month"]],
        "severity_options": [["1️⃣ Very Mild", "2️⃣ Moderate"], ["3️⃣ Medium", "4️⃣ Severe"], ["5️⃣ Critical"]],
        "severity_map": {"1️⃣ Very Mild": 1, "2️⃣ Moderate": 2, "3️⃣ Medium": 3, "4️⃣ Severe": 4, "5️⃣ Critical": 5},
        "conditions_kb": [["No previous conditions"], ["Diabetes", "Blood Pressure"], ["Heart Disease", "Asthma"], ["✏️ Type manually"]],
        "quick_symptoms": [["Headache", "Fever", "Cough"], ["Chest Pain", "Nausea", "Fatigue"], ["Shortness of Breath", "Dizziness", "Joint Pain"], ["Stomach Pain", "Chills", "Red Eyes"], ["✅ Done"]],
        "sev_labels": {1:"Very Mild", 2:"Moderate", 3:"Medium", 4:"Severe", 5:"Critical"},
        "sources": [
            ("Mayo Clinic", "https://www.mayoclinic.org"),
            ("MedlinePlus", "https://medlineplus.gov"),
            ("World Health Organization", "https://www.who.int"),
            ("NHS", "https://www.nhs.uk"),
        ],
        "prompt_lang": "en",
        "memory_label": "🕐 Compared to your last check-in",
        "memory_same": "You checked in {} day(s) ago with similar symptoms ({}). ",
        "memory_worse": "Severity increased from {}/5 to {}/5 since last time. ",
        "memory_better": "Severity improved from {}/5 to {}/5 since last time. ",
        "memory_new": "This is the first time you've logged these symptoms with us.",
        "trends_button": "📊 This Week's Trends",
        "trends_title": "Community Symptom Radar 📊",
        "trends_period": "Here's what symptoms other users have reported in the last 7 days (sessions: {})",
        "trends_empty": "Not enough data yet to show trends. Check back once more people have used the bot.",
        "trends_footer": "\n⚠️ General statistics for awareness only, not a medical diagnosis.",
        "trends_small_sample": "\nℹ️ Note: the sample is still small, so these percentages will shift quickly as more people use the bot.",
        "infermedica_label": "🔬 Checked against medical knowledge base",
        "infermedica_note": "Match score between your reported symptoms and typical symptoms of each condition (not a precise diagnosis or medical probability)",
    }
}

def t(context, key):
    lang = context.user_data.get("lang", "ar")
    return TEXTS[lang][key]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    context.user_data["symptoms"] = []
    try:
        db.log_visit(update.effective_user.id)
    except Exception as visit_err:
        logger.warning(f"Visit logging failed: {visit_err}")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar"),
         InlineKeyboardButton("English 🇺🇸", callback_data="lang_en")]
    ])
    await update.message.reply_text(
        "مرحباً بك في SymptoSense 🏥\nYour smart health assistant.\n\nالرجاء اختيار اللغة\nPlease choose your language:",
        reply_markup=kb
    )
    return LANG

async def set_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = "ar" if query.data == "lang_ar" else "en"
    context.user_data["lang"] = lang
    tx = TEXTS[lang]
    await query.message.reply_text(tx["ask_age"], reply_markup=ReplyKeyboardRemove())
    return AGE

async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text.isdigit() or not (1 <= int(text) <= 120):
        await update.message.reply_text(t(context, "invalid_age"))
        return AGE
    context.user_data["age"] = int(text)
    tx = TEXTS[context.user_data.get("lang","ar")]
    await update.message.reply_text(
        tx["ask_gender"],
        reply_markup=ReplyKeyboardMarkup([[tx["male"], tx["female"]]], resize_keyboard=True, one_time_keyboard=True)
    )
    return GENDER

async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    tx = TEXTS[context.user_data.get("lang","ar")]
    if tx["male"] in text:
        context.user_data["gender"] = tx["male"]
        context.user_data["sex"] = "male"
    elif tx["female"] in text:
        context.user_data["gender"] = tx["female"]
        context.user_data["sex"] = "female"
    else:
        await update.message.reply_text(tx["invalid_gender"])
        return GENDER
    await update.message.reply_text(
        tx["ask_symptoms"],
        reply_markup=ReplyKeyboardMarkup(tx["quick_symptoms"], resize_keyboard=True)
    )
    return SYMPTOMS

async def get_symptoms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    tx = TEXTS[context.user_data.get("lang","ar")]
    if "✅" in text or "Done" in text or "انتهيت" in text:
        if not context.user_data["symptoms"]:
            await update.message.reply_text(tx["add_symptom_first"])
            return SYMPTOMS
        await update.message.reply_text(
            tx["summary"].format(context.user_data['age'], context.user_data['gender'], ', '.join(context.user_data['symptoms'])) + "\n\n" + tx["ask_duration"],
            reply_markup=ReplyKeyboardMarkup(tx["duration_options"], resize_keyboard=True, one_time_keyboard=True)
        )
        return DURATION
    clean = re.sub(r'[^\w\s\u0600-\u06FF]', '', text).strip()
    if clean and clean not in context.user_data["symptoms"] and len(context.user_data["symptoms"]) < 15:
        context.user_data["symptoms"].append(clean)
        await update.message.reply_text(tx["symptom_added"].format(len(context.user_data["symptoms"])))
    return SYMPTOMS

async def get_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tx = TEXTS[context.user_data.get("lang","ar")]
    valid = [opt for row in tx["duration_options"] for opt in row]
    if update.message.text not in valid:
        await update.message.reply_text(tx["invalid_choice"])
        return DURATION
    context.user_data["duration"] = update.message.text
    await update.message.reply_text(
        tx["ask_severity"],
        reply_markup=ReplyKeyboardMarkup(tx["severity_options"], resize_keyboard=True, one_time_keyboard=True)
    )
    return SEVERITY

async def get_severity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tx = TEXTS[context.user_data.get("lang","ar")]
    if update.message.text not in tx["severity_map"]:
        await update.message.reply_text(tx["invalid_choice"])
        return SEVERITY
    context.user_data["severity"] = tx["severity_map"][update.message.text]
    context.user_data["severity_label"] = update.message.text
    await update.message.reply_text(
        tx["ask_conditions"],
        reply_markup=ReplyKeyboardMarkup(tx["conditions_kb"], resize_keyboard=True, one_time_keyboard=True)
    )
    return CONDITIONS

async def get_conditions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    tx = TEXTS[context.user_data.get("lang","ar")]
    if "✏️" in text:
        await update.message.reply_text(tx["write_manually"], reply_markup=ReplyKeyboardRemove())
        context.user_data["_wait"] = True
        return CONDITIONS
    if context.user_data.get("_wait"):
        context.user_data["conditions"] = text
        context.user_data.pop("_wait", None)
    elif "No previous" in text or "لا يوجد" in text:
        context.user_data["conditions"] = ""
    else:
        context.user_data["conditions"] = text
    await update.message.reply_text(
        tx["ask_notes"],
        reply_markup=ReplyKeyboardMarkup([[tx["skip"]]], resize_keyboard=True, one_time_keyboard=True)
    )
    return NOTES

async def get_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tx = TEXTS[context.user_data.get("lang","ar")]
    context.user_data["notes"] = "" if tx["skip"].replace("⏭️ ","") in update.message.text else update.message.text.strip()
    d = context.user_data
    await update.message.reply_text(
        tx["summary"].format(d.get('age'), d.get('gender'), ', '.join(d.get('symptoms',[]))) + "\n\n" + tx["analyzing"],
        reply_markup=ReplyKeyboardRemove()
    )
    return await analyze_symptoms(update, context)

_ARABIC_RE = re.compile("[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]+")
_NON_ARABIC_LETTERS_RE = re.compile(
    "["
    "A-Za-z"
    "\u00C0-\u024F"   # Latin Extended (French/Spanish accented letters, etc.)
    "\u1E00-\u1EFF"   # Latin Extended Additional (Vietnamese)
    "\u0590-\u05FF"   # Hebrew
    "\u0400-\u04FF"   # Cyrillic
    "\u4e00-\u9fff"   # CJK Unified Ideographs
    "\u3040-\u30ff"   # Hiragana + Katakana
    "\uac00-\ud7af"   # Hangul
    "\u3400-\u4dbf"   # CJK Extension A
    "\uff00-\uffef"   # Fullwidth forms
    "]+"
)

def _html_escape(text: str) -> str:
    if not text:
        return text
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def _md_safe(text, lang: str = "ar") -> str:
    """Strip stray foreign-script words the LLM occasionally leaks, then
    HTML-escape the result (we send messages with parse_mode='HTML')."""
    if not text:
        return text
    text = str(text)
    if lang == "ar":
        text = _NON_ARABIC_LETTERS_RE.sub("", text)
    else:
        text = _ARABIC_RE.sub("", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return _html_escape(text)


def _bar(pct: int, scale: int = 5) -> str:
    return "█" * max(1, pct // scale)


def _get_age_context(age, lang: str) -> str:
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


def _get_time_context(lang: str) -> str:
    ksa_now = datetime.now(timezone(timedelta(hours=3)))
    hour = ksa_now.hour
    if 0 <= hour < 6:
        return ("سياق مهم: الوقت الحالي بعد منتصف الليل بتوقيت السعودية. لو الحالة بسيطة (غير طارئة)، اقترح بلطف الراحة الليلة ومراقبة الأعراض بدل الحث على الخروج فوراً، إلا لو الحالة فعلاً طارئة."
                if lang == "ar" else
                "IMPORTANT CONTEXT: It is currently late night/early morning in Saudi Arabia. If the case is low urgency (non-emergency), gently suggest resting tonight and monitoring symptoms rather than urging them to go out immediately, unless it's truly urgent.")
    return ""


async def analyze_symptoms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    d = context.user_data
    tx = TEXTS[d.get("lang","ar")]
    lang = d.get("lang","ar")
    sev_label = tx["sev_labels"].get(d.get('severity',1), "")
    user_id = update.effective_user.id
    previous = db.get_last_record(user_id)

    age_context = _get_age_context(d.get('age'), lang)
    time_context = _get_time_context(lang)

    if lang == "ar":
        prompt = f"""انت مساعد طبي توعوي متخصص. يجب أن تكتب ردك باللغة العربية فقط بدون أي كلمة بلغة أخرى إطلاقاً.
معلومات المريض:
- العمر: {d.get('age')} سنة، الجنس: {d.get('gender')}
- الأعراض: {', '.join(d.get('symptoms',[])[:6])}
- المدة: {d.get('duration')}، الشدة: {sev_label} ({d.get('severity')}/5)
- أمراض سابقة: {d.get('conditions') or 'لا يوجد'}
- ملاحظات: {d.get('notes') or 'لا يوجد'}
{age_context}
{time_context}
اجب بـ JSON فقط. كل النصوص يجب أن تكون باللغة العربية فقط، ممنوع استخدام أي لغة أخرى:
{{"personal_note":"جملة أو جملتين متعاطفتين وشخصية تخاطب المريض مباشرة بناءً على حالته بالضبط (مو نص عام)","urgency":"low|medium|high","urgency_ar":"بسيط|يحتاج موعد طبيب|طوارئ","possible_conditions":"الاحتمالات بالعربية فقط (3 جمل)","recommendations":["نصيحة بالعربية","نصيحة بالعربية","نصيحة بالعربية","نصيحة بالعربية"],"danger_signs":"علامات الخطر بالعربية فقط","when_to_seek_care":"متى تراجع الطبيب بالعربية فقط","home_care":"الرعاية المنزلية بالعربية فقط"}}"""
    else:
        prompt = f"""You are a medical awareness assistant. Write your response in English ONLY. Do not use any other language.
Patient information:
- Age: {d.get('age')}, Gender: {d.get('gender')}
- Symptoms: {', '.join(d.get('symptoms',[])[:6])}
- Duration: {d.get('duration')}, Severity: {sev_label} ({d.get('severity')}/5)
- Previous conditions: {d.get('conditions') or 'None'}
- Notes: {d.get('notes') or 'None'}
{age_context}
{time_context}
Reply with JSON only. All text must be in English only:
{{"personal_note":"one or two empathetic, personalized sentences addressing the patient directly based on their specific situation (not generic)","urgency":"low|medium|high","urgency_text":"Simple|Needs appointment|Emergency","possible_conditions":"Possible conditions in English only (3 sentences)","recommendations":["tip in English","tip in English","tip in English","tip in English"],"danger_signs":"Danger signs in English only","when_to_seek_care":"When to see a doctor in English only","home_care":"Home care tips in English only"}}"""

    try:
        client = Groq(api_key=os.environ["GROQ_API_KEY"])
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            response_format={"type": "json_object"},
            temperature=0.3
        )
        full_text = response.choices[0].message.content
        full_text = re.sub(r'```json|```', '', full_text).strip()
        m = re.search(r"\{[\s\S]*\}", full_text)
        if not m:
            raise ValueError(f"No JSON: {full_text[:100]}")
        result = json.loads(m.group())

        icon = {"low":"🟢","medium":"🟡","high":"🔴"}.get(result.get("urgency","low"),"🟢")
        urgency_text = _md_safe(result.get("urgency_ar") or result.get("urgency_text",""), lang)
        recs = "\n".join(f"  {i+1}. {_md_safe(r, lang)}" for i,r in enumerate(result.get("recommendations",[])))
        personal_note = _md_safe(result.get("personal_note", ""), lang)
        possible_conditions = _md_safe(result.get('possible_conditions',''), lang)
        home_care = _md_safe(result.get('home_care',''), lang)
        danger_signs = _md_safe(result.get('danger_signs',''), lang)
        when_to_seek_care = _md_safe(result.get('when_to_seek_care',''), lang)

        sources_text = "\n".join(
            f"🔗 {name} — {url}" for name, url in tx["sources"]
        )

        # --- Cross-check against a local, curated medical knowledge base ---
        infermedica_block = ""
        try:
            verified = local_diagnosis.get_verified_conditions(d.get('symptoms', []))
            if verified:
                name_key = "name_ar" if lang == "ar" else "name_en"
                match_word = "تطابق" if lang == "ar" else "match"
                lines = [f"<i>{_html_escape(tx['infermedica_note'])}</i>", ""]
                for cond in verified:
                    pct = round(cond["score"] * 100)
                    name = _md_safe(cond[name_key], lang)
                    lines.append(f"<b>{name}</b>: {_bar(pct)} {pct}% {match_word}")
                infermedica_block = "\n".join(lines)
        except Exception as inf_err:
            logger.warning(f"Local diagnosis matching error: {inf_err}")

        # --- Memory: compare with the user's previous check-in, if any ---
        memory_block = ""
        current_symptoms = set(d.get('symptoms', []))
        if previous:
            overlap = current_symptoms & set(previous["symptoms"])
            cur_sev = d.get('severity', 1)
            prev_sev = previous.get("severity") or cur_sev
            if overlap:
                memory_block += tx["memory_same"].format(previous["days_ago"], ", ".join(list(overlap)[:3]))
            if cur_sev > prev_sev:
                memory_block += tx["memory_worse"].format(prev_sev, cur_sev)
            elif cur_sev < prev_sev:
                memory_block += tx["memory_better"].format(prev_sev, cur_sev)
            if not memory_block:
                memory_block = tx["memory_new"]
        else:
            memory_block = tx["memory_new"]

        # --- Save this session (anonymized) for future memory & community trends ---
        try:
            db.save_record(
                user_id, lang, d.get('age'), d.get('gender'),
                d.get('symptoms', []), d.get('duration'),
                d.get('severity'), result.get('urgency', 'low'),
            )
        except Exception as db_err:
            logger.error(f"DB save error: {db_err}")

        msg = (
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>{_html_escape(tx['result_title'])}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"<i>{personal_note}</i>\n\n"
            f"{icon} <b>{_html_escape(tx['urgency_label'])}:</b> {urgency_text}\n\n"
            f"<b>{_html_escape(tx['conditions_label'])}</b>\n{possible_conditions}\n\n"
            + (f"<b>{_html_escape(tx['infermedica_label'])}</b>\n{infermedica_block}\n\n" if infermedica_block else "")
            + f"<b>{_html_escape(tx['recommendations_label'])}</b>\n{recs}\n\n"
            f"<b>{_html_escape(tx['home_care_label'])}</b>\n{home_care}\n\n"
            f"<b>{_html_escape(tx['danger_label'])}</b>\n{danger_signs}\n\n"
            f"<b>{_html_escape(tx['when_label'])}</b>\n{when_to_seek_care}\n\n"
            f"<b>{_html_escape(tx['memory_label'])}</b>\n{_md_safe(memory_block, lang)}\n\n"
            f"<b>{_html_escape(tx['sources_label'])}</b>\n{sources_text}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<i>{_html_escape(tx['disclaimer'])}</i>\n"
            f"{_html_escape(tx['signature'])}"
        )

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(tx["new_analysis"], callback_data="restart")],
        ])

        async def _send(text, **kwargs):
            try:
                await update.message.reply_text(text, parse_mode="HTML", **kwargs)
            except Exception as md_err:
                logger.warning(f"HTML send failed, falling back to plain text: {md_err}")
                plain = re.sub(r"<[^>]+>", "", text).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                await update.message.reply_text(plain, **kwargs)

        if len(msg) > 4000:
            await _send(msg[:2000])
            await _send(msg[2000:], reply_markup=kb)
        else:
            await _send(msg, reply_markup=kb)

        # --- Automatically show the community trend chart after every analysis ---
        try:
            chart = await generate_trends_chart(days=7)
            if chart:
                caption = tx["trends_title"] + "\n" + tx["trends_period"].format(
                    db.get_trends(days=7)[1]
                )
                await update.message.reply_photo(photo=chart, caption=caption)
        except Exception as chart_err:
            logger.warning(f"Auto chart send failed: {chart_err}")

        # --- Save context so follow-up questions can reference this exact case ---
        context.user_data["last_case_summary"] = (
            f"Age: {d.get('age')}, Gender: {d.get('gender')}, "
            f"Symptoms: {', '.join(d.get('symptoms', []))}, "
            f"Duration: {d.get('duration')}, Severity: {d.get('severity')}/5, "
            f"Urgency: {result.get('urgency')}, "
            f"Possible conditions: {result.get('possible_conditions','')}"
        )

        await update.message.reply_text(tx["followup_prompt"])

    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(t(context, "error"))
        return ConversationHandler.END
    return FOLLOWUP

async def handle_followup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS[lang]
    question = update.message.text
    case_summary = context.user_data.get("last_case_summary", "")

    thinking_msg = await update.message.reply_text(tx["followup_thinking"])
    try:
        client = Groq(api_key=os.environ["GROQ_API_KEY"])
        lang_instruction = "Reply in Arabic only." if lang == "ar" else "Reply in English only."
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": (
                    f"You are a careful medical-awareness assistant continuing a conversation. "
                    f"The patient's case so far: {case_summary}\n"
                    f"Answer their follow-up question briefly (3-5 sentences), staying consistent with "
                    f"the case above. Never give definitive diagnoses or specific drug dosages. "
                    f"If the question suggests something urgent, tell them to seek medical care. {lang_instruction}"
                )},
                {"role": "user", "content": question},
            ],
            temperature=0.4,
            max_tokens=400,
        )
        answer = _md_safe(response.choices[0].message.content, lang)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(tx["new_analysis"], callback_data="restart")]])
        await thinking_msg.edit_text(answer)
        await update.message.reply_text(tx["followup_prompt"], reply_markup=kb)
    except Exception as e:
        logger.error(f"Follow-up error: {e}")
        await thinking_msg.edit_text(tx["followup_error"])
    return FOLLOWUP

async def restart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    lang = context.user_data.get("lang", "ar")
    context.user_data.clear()
    context.user_data["symptoms"] = []
    context.user_data["lang"] = lang
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar"),
         InlineKeyboardButton("English 🇺🇸", callback_data="lang_en")]
    ])
    await update.callback_query.message.reply_text(
        "الرجاء اختيار اللغة\nPlease choose your language:",
        reply_markup=kb
    )
    return LANG

async def generate_trends_chart(days=7):
    counter, total = db.get_trends(days=days)
    if not counter:
        return None
    top = counter.most_common(8)
    labels = [SYMPTOM_EN.get(k, k) for k, _ in top]
    values = [v for _, v in top]

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4.5))
    bars = ax.barh(labels[::-1], values[::-1], color="#2E9E5B")
    ax.set_xlabel("Sessions")
    ax.set_title(f"Top Symptoms — Last {days} Days (n={total})")
    for bar in bars:
        w = bar.get_width()
        ax.text(w + 0.05, bar.get_y() + bar.get_height() / 2, str(int(w)), va="center")
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf


async def show_trends(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str):
    tx = TEXTS[lang]
    counter, total = db.get_trends(days=7)
    if total == 0:
        text = f"{tx['trends_title']}\n\n{tx['trends_empty']}"
    else:
        lines = [f"{tx['trends_title']}", tx["trends_period"].format(total), ""]
        for symptom, count in counter.most_common(8):
            pct = round(100 * count / total)
            bar = "█" * max(1, pct // 5)
            lines.append(f"{symptom}: {bar} {pct}%  ({count}/{total})")
        if total < 5:
            lines.append(tx["trends_small_sample"])
        lines.append(tx["trends_footer"])
        text = "\n".join(lines)
    return text

async def trends_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ar")
    text = await show_trends(update, context, lang)
    await update.message.reply_text(text)
    try:
        chart = await generate_trends_chart(days=7)
        if chart:
            await update.message.reply_photo(photo=chart)
    except Exception as chart_err:
        logger.warning(f"Chart generation failed: {chart_err}")

async def trends_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    lang = context.user_data.get("lang", "ar")
    text = await show_trends(update, context, lang)
    await update.callback_query.message.reply_text(text)
    try:
        chart = await generate_trends_chart(days=7)
        if chart:
            await update.callback_query.message.reply_photo(photo=chart)
    except Exception as chart_err:
        logger.warning(f"Chart generation failed: {chart_err}")

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("🔒 هذا الأمر للمشرف فقط | Admin only command")
        return
    s = db.get_usage_stats(days=7)
    text = (
        f"📊 إحصائيات SymptoSense\n\n"
        f"👥 إجمالي الزيارات (كل الوقت): {s['total_visits']}\n"
        f"👤 مستخدمين فريدين دخلوا البوت: {s['unique_visitors']}\n"
        f"✅ تحليلات مكتملة (كل الوقت): {s['total_sessions']}\n"
        f"👤 مستخدمين فريدين أكملوا تحليل: {s['unique_users_completed']}\n\n"
        f"📅 آخر {s['period_days']} أيام:\n"
        f"  • زيارات: {s['visits_this_period']}\n"
        f"  • تحليلات مكتملة: {s['sessions_this_period']}"
    )
    await update.message.reply_text(text)

async def export_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("🔒 هذا الأمر للمشرف فقط | Admin only command")
        return
    xlsx_buf = db.export_all_records_xlsx()
    filename = f"symptosense_export_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    await update.message.reply_document(
        document=xlsx_buf, filename=filename,
        caption="📦 تصدير كامل للبيانات المجهولة الهوية (Excel) — جاهز لـ Power BI"
    )


def find_nearby_hospitals(lat, lon, urgency="low", lang="ar"):
    """البحث عن أقرب مستشفيات باستخدام Overpass API (OpenStreetMap) - مجاني 100%"""
    radius = 3000 if urgency == "low" else 5000
    amenity = "hospital|clinic" if urgency == "high" else "clinic|hospital"
    
    query = f"""
    [out:json][timeout:10];
    (
      node["amenity"~"hospital|clinic"](around:{radius},{lat},{lon});
      way["amenity"~"hospital|clinic"](around:{radius},{lat},{lon});
    );
    out center 5;
    """
    
    try:
        url = "https://overpass-api.de/api/interpreter"
        data = urllib.parse.urlencode({"data": query}).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("User-Agent", "SymptoSenseBot/1.0")
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
        
        hospitals = []
        for el in result.get("elements", [])[:5]:
            tags = el.get("tags", {})
            name = tags.get("name") or tags.get("name:ar") or tags.get("name:en")
            if not name:
                continue
            if el.get("type") == "node":
                elat, elon = el.get("lat"), el.get("lon")
            else:
                elat = el.get("center", {}).get("lat")
                elon = el.get("center", {}).get("lon")
            if not elat or not elon:
                continue
            hospitals.append({
                "name": name,
                "lat": elat,
                "lon": elon,
                "type": tags.get("amenity", "hospital"),
                "phone": tags.get("phone") or tags.get("contact:phone", ""),
            })
        return hospitals
    except Exception as e:
        logger.error(f"Overpass error: {e}")
        return []

async def ask_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "ar")
    if lang == "ar":
        msg = "📍 أرسل موقعك لنجد أقرب مستشفى أو عيادة لك\n\nاضغط الزر أدناه لمشاركة موقعك"
        btn_text = "📍 مشاركة موقعي"
        skip_text = "⏭️ تخطي"
    else:
        msg = "📍 Share your location to find the nearest hospital or clinic\n\nTap the button below"
        btn_text = "📍 Share my location"
        skip_text = "⏭️ Skip"
    
    location_btn = KeyboardButton(btn_text, request_location=True)
    skip_btn = KeyboardButton(skip_text)
    kb = ReplyKeyboardMarkup([[location_btn], [skip_btn]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(msg, reply_markup=kb)
    return LOCATION

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "ar")
    urgency = context.user_data.get("last_urgency", "low")
    
    # تخطي
    if update.message.text and ("تخطي" in update.message.text or "Skip" in update.message.text):
        if lang == "ar":
            await update.message.reply_text("تم! يمكنك دائماً استخدام /hospital للبحث لاحقاً.", reply_markup=ReplyKeyboardRemove())
        else:
            await update.message.reply_text("OK! You can always use /hospital to search later.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    
    if not update.message.location:
        if lang == "ar":
            await update.message.reply_text("يرجى مشاركة موقعك أو اضغط تخطي")
        else:
            await update.message.reply_text("Please share your location or press Skip")
        return LOCATION
    
    lat = update.message.location.latitude
    lon = update.message.location.longitude
    
    await update.message.reply_text("🔍 جاري البحث..." if lang == "ar" else "🔍 Searching...", reply_markup=ReplyKeyboardRemove())
    
    hospitals = find_nearby_hospitals(lat, lon, urgency, lang)
    
    if not hospitals:
        if lang == "ar":
            msg = "❌ لم نجد مستشفيات قريبة. جرب البحث يدوياً على خرائط Google."
        else:
            msg = "❌ No nearby hospitals found. Try searching manually on Google Maps."
        await update.message.reply_text(msg)
        return ConversationHandler.END
    
    if lang == "ar":
        lines = [f"🏥 أقرب {'مستشفيات' if urgency == 'high' else 'عيادات ومستشفيات'} لك:\n"]
    else:
        lines = [f"🏥 Nearest {'hospitals' if urgency == 'high' else 'clinics & hospitals'} near you:\n"]
    
    for i, h in enumerate(hospitals, 1):
        maps_url = f"https://www.google.com/maps/search/?api=1&query={h['lat']},{h['lon']}"
        htype = "🏥 مستشفى" if h["type"] == "hospital" else "🏨 عيادة"
        if lang == "en":
            htype = "🏥 Hospital" if h["type"] == "hospital" else "🏨 Clinic"
        phone_line = f"\n   📞 {h['phone']}" if h.get("phone") else ""
        lines.append(f"{i}. {htype}: {h['name']}{phone_line}\n   📍 [فتح في الخرائط]({maps_url})" if lang == "ar" else f"{i}. {htype}: {h['name']}{phone_line}\n   📍 [Open in Maps]({maps_url})")
    
    if urgency == "high":
        lines.append("\n🚨 حالتك تستدعي الذهاب للطوارئ فوراً!" if lang == "ar" else "\n🚨 Your condition requires immediate emergency care!")
    
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True)
    return ConversationHandler.END

async def hospital_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """أمر /hospital مستقل للبحث عن مستشفى في أي وقت"""
    return await ask_location(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(t(context, "cancelled"), reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "SymptoSense 🏥\n\n/start - تحليل جديد | New analysis\n/trends - اتجاهات المجتمع | Community trends\n/cancel - إلغاء | Cancel\n/help - مساعدة | Help\n\nللتوعية فقط | For awareness only"
    )

def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token: raise ValueError("TELEGRAM_BOT_TOKEN missing")
    if not os.environ.get("GROQ_API_KEY"): raise ValueError("GROQ_API_KEY missing")

    app = Application.builder().token(token).build()
    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(restart_callback, pattern="^restart$"),
        ],
        states={
            LANG:[CallbackQueryHandler(set_lang, pattern="^lang_")],
            AGE:[MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
            GENDER:[MessageHandler(filters.TEXT & ~filters.COMMAND, get_gender)],
            SYMPTOMS:[MessageHandler(filters.TEXT & ~filters.COMMAND, get_symptoms)],
            DURATION:[MessageHandler(filters.TEXT & ~filters.COMMAND, get_duration)],
            SEVERITY:[MessageHandler(filters.TEXT & ~filters.COMMAND, get_severity)],
            CONDITIONS:[MessageHandler(filters.TEXT & ~filters.COMMAND, get_conditions)],
            NOTES:[MessageHandler(filters.TEXT & ~filters.COMMAND, get_notes)],
            FOLLOWUP:[
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup),
                CallbackQueryHandler(restart_callback, pattern="^restart$"),
            ],
            LOCATION:[
                MessageHandler(filters.LOCATION, handle_location),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_location),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("trends", trends_cmd))
    app.add_handler(CallbackQueryHandler(trends_callback, pattern="^trends$"))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("export", export_cmd))
    db.init_db()
    logger.info("SymptoSense يعمل...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
