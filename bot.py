import os
import io
import json
import logging
import re
from datetime import datetime
from groq import Groq
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
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

LANG, AGE, GENDER, SYMPTOMS, DURATION, SEVERITY, CONDITIONS, NOTES = range(8)

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
        "signature": "\n💚 معكم ريماس، وأتمنى إني أفدتكم. لو عندكم أي استفسار أو سؤال، هذا حسابي: https://t.me/rms_2o",
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
        "signature": "\n💚 This is Reemas, I hope this was helpful. For any questions, reach me here: https://t.me/rms_2o",
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

def _md_safe(text: str) -> str:
    """Strip characters that would break Telegram's legacy Markdown parser."""
    if not text:
        return text
    return str(text).replace("*", "").replace("_", "").replace("`", "").replace("[", "(").replace("]", ")")


def _bar(pct: int, scale: int = 5) -> str:
    return "█" * max(1, pct // scale)


async def analyze_symptoms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    d = context.user_data
    tx = TEXTS[d.get("lang","ar")]
    lang = d.get("lang","ar")
    sev_label = tx["sev_labels"].get(d.get('severity',1), "")
    user_id = update.effective_user.id
    previous = db.get_last_record(user_id)

    if lang == "ar":
        prompt = f"""انت مساعد طبي توعوي متخصص. يجب أن تكتب ردك باللغة العربية فقط بدون أي كلمة بلغة أخرى إطلاقاً.
معلومات المريض:
- العمر: {d.get('age')} سنة، الجنس: {d.get('gender')}
- الأعراض: {', '.join(d.get('symptoms',[]))}
- المدة: {d.get('duration')}، الشدة: {sev_label} ({d.get('severity')}/5)
- أمراض سابقة: {d.get('conditions') or 'لا يوجد'}
- ملاحظات: {d.get('notes') or 'لا يوجد'}
اجب بـ JSON فقط. كل النصوص يجب أن تكون باللغة العربية فقط، ممنوع استخدام أي لغة أخرى:
{{"personal_note":"جملة أو جملتين متعاطفتين وشخصية تخاطب المريض مباشرة بناءً على حالته بالضبط (مو نص عام)","urgency":"low|medium|high","urgency_ar":"بسيط|يحتاج موعد طبيب|طوارئ","possible_conditions":"الاحتمالات بالعربية فقط (3 جمل)","recommendations":["نصيحة بالعربية","نصيحة بالعربية","نصيحة بالعربية","نصيحة بالعربية"],"danger_signs":"علامات الخطر بالعربية فقط","when_to_seek_care":"متى تراجع الطبيب بالعربية فقط","home_care":"الرعاية المنزلية بالعربية فقط"}}"""
    else:
        prompt = f"""You are a medical awareness assistant. Write your response in English ONLY. Do not use any other language.
Patient information:
- Age: {d.get('age')}, Gender: {d.get('gender')}
- Symptoms: {', '.join(d.get('symptoms',[]))}
- Duration: {d.get('duration')}, Severity: {sev_label} ({d.get('severity')}/5)
- Previous conditions: {d.get('conditions') or 'None'}
- Notes: {d.get('notes') or 'None'}
Reply with JSON only. All text must be in English only:
{{"personal_note":"one or two empathetic, personalized sentences addressing the patient directly based on their specific situation (not generic)","urgency":"low|medium|high","urgency_text":"Simple|Needs appointment|Emergency","possible_conditions":"Possible conditions in English only (3 sentences)","recommendations":["tip in English","tip in English","tip in English","tip in English"],"danger_signs":"Danger signs in English only","when_to_seek_care":"When to see a doctor in English only","home_care":"Home care tips in English only"}}"""

    try:
        client = Groq(api_key=os.environ["GROQ_API_KEY"])
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500
        )
        full_text = response.choices[0].message.content
        full_text = re.sub(r'```json|```', '', full_text).strip()
        m = re.search(r"\{[\s\S]*\}", full_text)
        if not m:
            raise ValueError(f"No JSON: {full_text[:100]}")
        result = json.loads(m.group())

        icon = {"low":"🟢","medium":"🟡","high":"🔴"}.get(result.get("urgency","low"),"🟢")
        urgency_text = _md_safe(result.get("urgency_ar") or result.get("urgency_text",""))
        recs = "\n".join(f"  {i+1}. {_md_safe(r)}" for i,r in enumerate(result.get("recommendations",[])))
        personal_note = _md_safe(result.get("personal_note", ""))
        possible_conditions = _md_safe(result.get('possible_conditions',''))
        home_care = _md_safe(result.get('home_care',''))
        danger_signs = _md_safe(result.get('danger_signs',''))
        when_to_seek_care = _md_safe(result.get('when_to_seek_care',''))

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
                lines = [f"_{tx['infermedica_note']}_", ""]
                for cond in verified:
                    pct = round(cond["score"] * 100)
                    name = _md_safe(cond[name_key])
                    lines.append(f"*{name}*: {_bar(pct)} {pct}% {match_word}")
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
            f"*{tx['result_title']}*\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"_{personal_note}_\n\n"
            f"{icon} *{tx['urgency_label']}:* {urgency_text}\n\n"
            f"*{tx['conditions_label']}*\n{possible_conditions}\n\n"
            + (f"*{tx['infermedica_label']}*\n{infermedica_block}\n\n" if infermedica_block else "")
            + f"*{tx['recommendations_label']}*\n{recs}\n\n"
            f"*{tx['home_care_label']}*\n{home_care}\n\n"
            f"*{tx['danger_label']}*\n{danger_signs}\n\n"
            f"*{tx['when_label']}*\n{when_to_seek_care}\n\n"
            f"*{tx['memory_label']}*\n{_md_safe(memory_block)}\n\n"
            f"*{tx['sources_label']}*\n{sources_text}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"_{tx['disclaimer']}_\n"
            f"{tx['signature']}"
        )

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(tx["new_analysis"], callback_data="restart")],
        ])

        async def _send(text, **kwargs):
            try:
                await update.message.reply_text(text, parse_mode="Markdown", **kwargs)
            except Exception as md_err:
                logger.warning(f"Markdown send failed, falling back to plain text: {md_err}")
                await update.message.reply_text(text.replace("*", "").replace("_", ""), **kwargs)

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

    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(t(context, "error"))
    return ConversationHandler.END

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
    csv_text = db.export_all_records_csv()
    buf = io.BytesIO(csv_text.encode("utf-8-sig"))
    filename = f"symptosense_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    await update.message.reply_document(
        document=buf, filename=filename,
        caption="📦 تصدير كامل للبيانات المجهولة الهوية — جاهز للتحليل"
    )

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
