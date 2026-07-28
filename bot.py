import os
import json
import logging
import re
from groq import Groq
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, CallbackQueryHandler, filters, ContextTypes
import db

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

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
        "trends_period": "آخر 7 أيام | بناءً على {} حالة (بيانات مجهولة الهوية)",
        "trends_empty": "ما فيه بيانات كافية بعد لعرض الاتجاهات. جرب لاحقاً بعد ما يستخدم البوت أكثر الناس.",
        "trends_footer": "\n⚠️ إحصائيات عامة للتوعية فقط، ما تمثل تشخيصاً طبياً.",
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
        "trends_period": "Last 7 days | based on {} anonymized sessions",
        "trends_empty": "Not enough data yet to show trends. Check back once more people have used the bot.",
        "trends_footer": "\n⚠️ General statistics for awareness only, not a medical diagnosis.",
    }
}

def t(context, key):
    lang = context.user_data.get("lang", "ar")
    return TEXTS[lang][key]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    context.user_data["symptoms"] = []
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
    if tx["male"] in text: context.user_data["gender"] = tx["male"]
    elif tx["female"] in text: context.user_data["gender"] = tx["female"]
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
        urgency_text = result.get("urgency_ar") or result.get("urgency_text","")
        recs = "\n".join(f"  {i+1}. {r}" for i,r in enumerate(result.get("recommendations",[])))
        personal_note = result.get("personal_note", "")

        sources_text = "\n".join(
            f"🔗 [{name}]({url})" for name, url in tx["sources"]
        )

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
            f"{tx['result_title']}\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"{personal_note}\n\n"
            f"{icon} {tx['urgency_label']}: {urgency_text}\n\n"
            f"{tx['conditions_label']}\n{result.get('possible_conditions','')}\n\n"
            f"{tx['recommendations_label']}\n{recs}\n\n"
            f"{tx['home_care_label']}\n{result.get('home_care','')}\n\n"
            f"{tx['danger_label']}\n{result.get('danger_signs','')}\n\n"
            f"{tx['when_label']}\n{result.get('when_to_seek_care','')}\n\n"
            f"{tx['memory_label']}\n{memory_block}\n\n"
            f"{tx['sources_label']}\n{sources_text}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{tx['disclaimer']}"
        )

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(tx["new_analysis"], callback_data="restart")],
            [InlineKeyboardButton(tx["trends_button"], callback_data="trends")],
        ])

        if len(msg) > 4000:
            await update.message.reply_text(msg[:2000])
            await update.message.reply_text(msg[2000:], reply_markup=kb)
        else:
            await update.message.reply_text(msg, reply_markup=kb)

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
            lines.append(f"{symptom}: {bar} {pct}%")
        lines.append(tx["trends_footer"])
        text = "\n".join(lines)
    return text

async def trends_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ar")
    text = await show_trends(update, context, lang)
    await update.message.reply_text(text)

async def trends_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    lang = context.user_data.get("lang", "ar")
    text = await show_trends(update, context, lang)
    await update.callback_query.message.reply_text(text)

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
    db.init_db()
    logger.info("SymptoSense يعمل...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
