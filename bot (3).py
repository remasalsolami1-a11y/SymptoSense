import os
import json
import logging
import re
from groq import Groq
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, ConversationHandler, CallbackQueryHandler, Filters

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

AGE, GENDER, SYMPTOMS, DURATION, SEVERITY, CONDITIONS, NOTES = range(7)

SEVERITY_MAP = {
    "1 خفيف جدا": 1, "2 معتدل": 2, "3 متوسط": 3, "4 شديد": 4, "5 حرج جدا": 5,
}
DURATION_OPTIONS = [
    ["اقل من 24 ساعة", "1-3 ايام"],
    ["4-7 ايام", "1-2 اسبوع"],
    ["اكثر من اسبوعين", "اكثر من شهر"],
]
QUICK_SYMPTOMS = [
    ["صداع", "حمى", "سعال"],
    ["الم في الصدر", "غثيان", "تعب وارهاق"],
    ["ضيق التنفس", "دوار", "الم المفاصل"],
    ["الم في البطن", "قشعريرة", "احمرار العيون"],
    ["انتهيت من الاعراض"],
]
CONDITIONS_KB = [
    ["لا يوجد امراض سابقة"],
    ["سكري", "ضغط الدم"],
    ["امراض قلب", "ربو"],
    ["كتابة يدوية"],
]

def start(update, context):
    context.user_data.clear()
    context.user_data["symptoms"] = []
    update.message.reply_text(
        "مرحبا في PulseCheck AI - مساعد تحليل الاعراض!\n\n"
        "تنبيه: هذا البوت للتوعية فقط ولا يغني عن الطبيب.\n"
        "طوارئ: اتصل بـ 911\n\n"
        "كم عمرك؟ (اكتب رقم فقط، مثال: 28)",
        reply_markup=ReplyKeyboardRemove()
    )
    return AGE

def get_age(update, context):
    text = update.message.text.strip()
    if not text.isdigit() or not (1 <= int(text) <= 120):
        update.message.reply_text("يرجى ادخال عمر صحيح بين 1 و 120")
        return AGE
    context.user_data["age"] = int(text)
    update.message.reply_text(
        "ما جنسك؟",
        reply_markup=ReplyKeyboardMarkup([["ذكر", "انثى"]], resize_keyboard=True, one_time_keyboard=True)
    )
    return GENDER

def get_gender(update, context):
    text = update.message.text
    if "ذكر" in text: context.user_data["gender"] = "ذكر"
    elif "انثى" in text: context.user_data["gender"] = "انثى"
    else:
        update.message.reply_text("اختر احد الخيارين")
        return GENDER
    update.message.reply_text(
        "ما هي اعراضك؟\nاختر من الازرار او اكتب بنفسك.\nاضغط 'انتهيت من الاعراض' عند الانتهاء",
        reply_markup=ReplyKeyboardMarkup(QUICK_SYMPTOMS, resize_keyboard=True)
    )
    return SYMPTOMS

def get_symptoms(update, context):
    text = update.message.text.strip()
    if "انتهيت" in text:
        if not context.user_data["symptoms"]:
            update.message.reply_text("اضف عرضا واحدا على الاقل!")
            return SYMPTOMS
        update.message.reply_text(
            f"الاعراض: {' - '.join(context.user_data['symptoms'])}\n\nكم مدة هذه الاعراض؟",
            reply_markup=ReplyKeyboardMarkup(DURATION_OPTIONS, resize_keyboard=True, one_time_keyboard=True)
        )
        return DURATION
    clean = re.sub(r'[^\w\s\u0600-\u06FF]', '', text).strip()
    if clean and clean not in context.user_data["symptoms"] and len(context.user_data["symptoms"]) < 15:
        context.user_data["symptoms"].append(clean)
        update.message.reply_text(f"تمت الاضافة! ({len(context.user_data['symptoms'])} اعراض)\nاضف المزيد او اضغط 'انتهيت من الاعراض'")
    return SYMPTOMS

def get_duration(update, context):
    valid = [opt for row in DURATION_OPTIONS for opt in row]
    if update.message.text not in valid:
        update.message.reply_text("اختر من الازرار")
        return DURATION
    context.user_data["duration"] = update.message.text
    update.message.reply_text(
        "ما شدة الالم؟\n1=خفيف جدا  2=معتدل  3=متوسط  4=شديد  5=حرج جدا",
        reply_markup=ReplyKeyboardMarkup([[k] for k in SEVERITY_MAP], resize_keyboard=True, one_time_keyboard=True)
    )
    return SEVERITY

def get_severity(update, context):
    if update.message.text not in SEVERITY_MAP:
        update.message.reply_text("اختر من الازرار")
        return SEVERITY
    context.user_data["severity"] = SEVERITY_MAP[update.message.text]
    context.user_data["severity_label"] = update.message.text
    update.message.reply_text(
        "هل لديك امراض مزمنة سابقة؟",
        reply_markup=ReplyKeyboardMarkup(CONDITIONS_KB, resize_keyboard=True, one_time_keyboard=True)
    )
    return CONDITIONS

def get_conditions(update, context):
    text = update.message.text.strip()
    if "كتابة يدوية" in text:
        update.message.reply_text("اكتب امراضك:", reply_markup=ReplyKeyboardRemove())
        context.user_data["_wait"] = True
        return CONDITIONS
    if context.user_data.get("_wait"):
        context.user_data["conditions"] = text
        context.user_data.pop("_wait", None)
    elif "لا يوجد" in text:
        context.user_data["conditions"] = ""
    else:
        context.user_data["conditions"] = text
    update.message.reply_text(
        "اي ملاحظات اضافية؟ (او اضغط تخطي)",
        reply_markup=ReplyKeyboardMarkup([["تخطي"]], resize_keyboard=True, one_time_keyboard=True)
    )
    return NOTES

def get_notes(update, context):
    context.user_data["notes"] = "" if "تخطي" in update.message.text else update.message.text.strip()
    d = context.user_data
    update.message.reply_text(
        f"ملخص: عمر {d.get('age')} | {d.get('gender')} | اعراض: {', '.join(d.get('symptoms',[]))}\n\nجاري التحليل...",
        reply_markup=ReplyKeyboardRemove()
    )
    return analyze_symptoms(update, context)

def analyze_symptoms(update, context):
    d = context.user_data
    sev_labels = {1:"خفيف جدا",2:"معتدل",3:"متوسط",4:"شديد",5:"حرج جدا"}
    prompt = f"""انت مساعد طبي توعوي متخصص. معلومات المريض:
- العمر: {d.get('age')} سنة، الجنس: {d.get('gender')}
- الاعراض: {', '.join(d.get('symptoms',[]))}
- المدة: {d.get('duration')}، الشدة: {sev_labels.get(d.get('severity',1))} ({d.get('severity')}/5)
- امراض سابقة: {d.get('conditions') or 'لا يوجد'}
- ملاحظات: {d.get('notes') or 'لا يوجد'}

اجب بـ JSON فقط بدون اي نص خارجه:
{{"urgency":"low|medium|high","urgency_ar":"بسيط|يحتاج موعد طبيب|طوارئ","possible_conditions":"الاحتمالات (3 جمل)","recommendations":["نصيحة1","نصيحة2","نصيحة3","نصيحة4"],"danger_signs":"علامات خطر","when_to_seek_care":"متى تراجع الطبيب","home_care":"رعاية منزلية","trusted_sources":"مصادر موثوقة"}}"""
    try:
        client = Groq(api_key=os.environ["GROQ_API_KEY"])
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500
        )
        full_text = response.choices[0].message.content
        m = re.search(r"\{[\s\S]*\}", full_text)
        result = json.loads(m.group())
        icon = {"low":"🟢","medium":"🟡","high":"🔴"}.get(result.get("urgency","low"),"🟢")
        recs = "\n".join(f"  {i+1}. {r}" for i,r in enumerate(result.get("recommendations",[])))
        msg = (
            f"نتيجة التحليل - PulseCheck AI\n\n"
            f"{icon} مستوى الخطورة: {result.get('urgency_ar','')}\n\n"
            f"الاحتمالات:\n{result.get('possible_conditions','')}\n\n"
            f"التوصيات:\n{recs}\n\n"
            f"الرعاية المنزلية:\n{result.get('home_care','')}\n\n"
            f"علامات خطر:\n{result.get('danger_signs','')}\n\n"
            f"متى تراجع الطبيب:\n{result.get('when_to_seek_care','')}\n\n"
            f"مصادر:\n{result.get('trusted_sources','')}\n\n"
            f"تذكير: هذا التحليل للتوعية فقط."
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("تحليل جديد", callback_data="restart")]])
        if len(msg) > 4000:
            update.message.reply_text(msg[:2000])
            update.message.reply_text(msg[2000:], reply_markup=kb)
        else:
            update.message.reply_text(msg, reply_markup=kb)
    except Exception as e:
        logger.error(f"Error: {e}")
        update.message.reply_text("حدث خطا. اكتب /start للمحاولة مجددا")
    return ConversationHandler.END

def restart_callback(update, context):
    update.callback_query.answer()
    context.user_data.clear()
    context.user_data["symptoms"] = []
    update.callback_query.message.reply_text("بدء تحليل جديد...\n\nكم عمرك؟", reply_markup=ReplyKeyboardRemove())
    return AGE

def cancel(update, context):
    update.message.reply_text("تم الالغاء. /start للبدء من جديد", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def help_cmd(update, context):
    update.message.reply_text("PulseCheck AI\n\n/start - تحليل جديد\n/cancel - الغاء\n/help - مساعدة\n\nللتوعية فقط ولا يغني عن الطبيب.")

def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token: raise ValueError("TELEGRAM_BOT_TOKEN غير موجود")
    if not os.environ.get("GROQ_API_KEY"): raise ValueError("GROQ_API_KEY غير موجود")

    updater = Updater(token)
    dp = updater.dispatcher

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            AGE:[MessageHandler(Filters.text & ~Filters.command, get_age)],
            GENDER:[MessageHandler(Filters.text & ~Filters.command, get_gender)],
            SYMPTOMS:[MessageHandler(Filters.text & ~Filters.command, get_symptoms)],
            DURATION:[MessageHandler(Filters.text & ~Filters.command, get_duration)],
            SEVERITY:[MessageHandler(Filters.text & ~Filters.command, get_severity)],
            CONDITIONS:[MessageHandler(Filters.text & ~Filters.command, get_conditions)],
            NOTES:[MessageHandler(Filters.text & ~Filters.command, get_notes)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    dp.add_handler(conv)
    dp.add_handler(CallbackQueryHandler(restart_callback, pattern="^restart$"))
    dp.add_handler(CommandHandler("help", help_cmd))

    logger.info("PulseCheck AI يعمل...")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
