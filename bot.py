import os
import io
import json
import logging
import re
import threading
import urllib.parse
from datetime import datetime, timezone, timedelta, time as dt_time
from groq import Groq
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, CallbackQueryHandler, filters, ContextTypes, BasePersistence, PersistenceInput
import db
import ml_diagnosis
import geo_hospitals
import health_tips
import medication_warnings
import wellbeing
import blood_test

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

LANG, AGE, GENDER, SYMPTOMS, DURATION, SEVERITY, CONDITIONS, NOTES, MEDICATIONS, FOLLOWUP = range(10)
BLOOD_GENDER, BLOOD_VALUES = 100, 101

TEXTS = {
    "ar": {
        "welcome": "مرحباً بك في SymptoSense 🏥\nمساعدك الذكي لتحليل الأعراض وتقديم تقييم أولي بناءً على ممصادر طبية موثوقة.",
        "choose_lang": "لنبدأ. الرجاء اختيار اللغة\nPlease choose your language:",
        "ask_age": "كم عمرك؟ (اكتب رقم فقط، مثال: 28)\n🎤 تقدرين تردين بصوت أو كتابة",
        "invalid_age": "يرجى إدخال عمر صحيح بين 1 و 120",
        "ask_gender": "ما جنسك؟\n🎤 ردّي بصوت أو من الأزرار",
        "male": "👨 ذكر",
        "female": "👩 أنثى",
        "invalid_gender": "اختر أحد الخيارين",
        "ask_symptoms": "ما هي أعراضك؟\nاختر من الأزرار 👇\n\n🖊️ لو ما لقيت اللي تحسين فيه بالضبط، اكتبه بنفسك (مثال: ألم في الرجل)\nاضغط ✅ انتهيت عند الانتهاء",
        "symptom_added": "تمت الإضافة! ({} أعراض)\nاضف المزيد أو اضغط ✅ انتهيت",
        "symptom_typing_prompt": "✍️ اكتب اللي تحسين فيه بالضبط 👇\n(مثال: ألم في الساق، حكة في العين...)\nبعدها اضغطي ✅ انتهيت",
        "ask_duration": "كم مدة هذه الأعراض؟\n🎤 ردّي بصوت أو من الأزرار",
        "ask_severity": "ما شدة الألم؟\n1️⃣ خفيف جداً\n2️⃣ معتدل\n3️⃣ متوسط\n4️⃣ شديد\n5️⃣ حرج جداً\n🎤 أو ردّي بصوت",
        "ask_conditions": "هل لديك أمراض مزمنة سابقة؟",
        "ask_notes": "أي ملاحظات إضافية؟ (أو اضغط تخطي)",
        "ask_medications": "💊 هل تاخذين حالياً أي أدوية؟ اذكري اسمها (أو اضغطي تخطي لو ما تاخذين شي)",
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
        "signature": "\n💚 معكم ريماس السلمي، وأتمنى إني أفدتكم. لو عندكم أي استفسار أو سؤال، هذا حسابي: @rms_2o",
        "followup_prompt": "💬 للاستفسار عن حالتك الصحية، اكتبي سؤالك هنا وبجاوبك عليه.\n(أو اضغطي \"🔄 تحليل جديد\" للبدء من جديد)",
        "followup_thinking": "🤔 لحظة، أفكر بسؤالك...",
        "followup_error": "⚠️ صار خطأ بالرد على سؤالك، حاولي مرة ثانية أو اضغطي \"🔄 تحليل جديد\".",
        "share_location_prompt": "🚨 حالتك تحتاج انتباه. تبين أساعدك ألقى أقرب مستشفى؟ اضغطي الزر تحت لمشاركة موقعك.",
        "share_location_button": "📍 شارك موقعي وابحث عن أقرب مستشفى",
        "hospitals_title": "🏥 أقرب المستشفيات لموقعك",
        "hospitals_none": "ما قدرت ألقى مستشفيات قريبة منك بالبيانات المتوفرة. اتصلي بالطوارئ (997) أو دوّري بخرائط جوجل مباشرة.",
        "hospitals_footer": "\n📞 بالحالات الطارئة، لا تترددي بالاتصال بالطوارئ: 997",
        "unsubscribed": "✅ تم إلغاء اشتراكك من النصائح اليومية. تقدرين ترجعين تفعليها بأي وقت بإرسال /start.",
        "daily_tip_header": "🌤️ نصيحة اليوم من SymptoSense",
        "daily_tip_footer": "\n\n(لإيقاف هذي الرسائل اليومية، ابعتي /stop)",
        "medication_label": "💊 ملاحظة دوائية",
        "medication_disclaimer": "هذي تنبيهات عامة فقط، مو فحص تداخل دوائي دقيق. راجعي الصيدلي أو الطبيب لو عندك استفسار عن دوائك.",
        "medication_guidance_label": "🩺 هل أكمل دوائي؟",
        "voice_error": "⚠️ ما قدرت أفهم الرسالة الصوتية، حاولي تسجلينها مرة ثانية أو اكتبي بدلها.",
        "voice_empty": "🤔 ما سمعت أي كلام واضح بالتسجيل، جربي مرة ثانية.",
        "voice_symptoms_detected": "✅ تم تسجيل: {} (إجمالي {} عرض)\n\nكملي بالصوت أو الكتابة، أو اضغطي \"✅ انتهيت\"",
        "new_analysis": "🔄 تحليل جديد",
        "cancelled": "تم الإلغاء. /start للبدء من جديد",
        "skip": "⏭️ تخطي",
        "done": "✅ انتهيت",
        "no_conditions": "لا يوجد أمراض سابقة",
        "write_manually": "✏️ كتابة يدوية",
        "add_symptom_first": "أضف عرضاً واحداً على الأقل!",
        "invalid_choice": "اختر من الأزرار",
        "error": "حدث خطأ. اكتب /start للمحاولة مجدداً",
        "duration_options": [["⏰ أقل من 24 ساعة", "📅 1-3 أيام"], ["📅 4-7 أيام", "🗓️ 1-2 أسبوع"], ["🗓️ أكثر من أسبوعين", "📆 أكثر من شهر"]],
        "severity_options": [["1️⃣ خفيف جداً", "2️⃣ معتدل"], ["3️⃣ متوسط", "4️⃣ شديد"], ["5️⃣ حرج جداً"]],
        "severity_map": {"1️⃣ خفيف جداً": 1, "2️⃣ معتدل": 2, "3️⃣ متوسط": 3, "4️⃣ شديد": 4, "5️⃣ حرج جداً": 5},
        "conditions_kb": [["لا يوجد أمراض سابقة"], ["سكري", "ضغط الدم"], ["أمراض قلب", "ربو"], ["✏️ كتابة يدوية"]],
        "quick_symptoms": [["🤕 صداع", "🤒 حمى", "😷 سعال"], ["🫀 ألم في الصدر", "🤢 غثيان", "😴 تعب وإرهاق"], ["🫁 ضيق التنفس", "💫 دوار", "🦴 ألم المفاصل"], ["😖 ألم في البطن", "🥶 قشعريرة", "👁️ احمرار العيون"], ["🦵 ألم في الرجل", "😣 ألم الحلق", "🖐️ حكة"], ["✍️ ما لقيت اللي أحس فيه — اكتبه"], ["✅ انتهيت"]],
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
        "infermedica_label": "🤖 نموذج تعلم آلة (Naive Bayes)",
        "infermedica_note": "احتمالات مبنية على نموذج تعلم آلة مدرّب إحصائياً على بيانات الأعراض (دقة الاختبار: 63.5%) — للتوعية فقط، مو تشخيصاً نهائياً",
        "firstaid_title": "🚑 دليل الإسعاف الأولي السريع",
        "firstaid_choose": "🚑 دليل الإسعاف الأولي السريع\n\nاختر الحالة:",
        "firstaid_footer": "\n\n⚠️ إرشادات إسعاف أولي فقط، ولا تغني عن الاتصال بالطوارئ (997) عند الحاجة.",
        "relax_title": "🧘‍♂️ تمارين الاسترخاء والتنفس",
        "season_title": "🍂 نصائح الموسم",
        "fu_prompt": "👋 نسأل عنك: كيف حالتك بعد تحليلك الأخير؟\nاختيارك يسجّل حالتك ويظهر بالإحصائيات (بدون كشف هويتك).",
        "fu_improved_btn": "✅ تحسنت",
        "fu_same_btn": "➖ كما هي",
        "fu_worse_btn": "🔴 ازدادت سوءاً",
        "fu_thanks_improved": "🌟 خوش خبر! استمري بالعناية اللي تسوينها، ولو رجعت الأعراض لا تترددي في تحليل جديد.",
        "fu_thanks_same": "انتبهي: لو استمرت الأعراض على حالها أكثر من أسبوع، الأفضل تراجعين طبيب.",
        "fu_thanks_worse": "🚨 الأعراض ازدادت سوءاً — أنصحك بمراجعة طبيب أو أقرب طوارئ، ولا تترددي. اعتني بنفسك.",
        "home_welcome": "🏠 أهلاً بك في الرئيسية\nاختاري اللي تبينه 👇",
        "share_welcome": "🤝 أهلاً! صديقك شارك معك بوت SymptoSense\nحللي أعراضك بسهولة وأحصلي على نصائح صحية 👇",
        "home_start_btn": "▶️ ابدأ تحليل جديد",
        "home_tips_btn": "💡 نصائح صحية",
        "home_followup_btn": "📋 متابعة الحالة",
        "home_firstaid_btn": "🚑 إسعاف أولي",
        "home_relax_btn": "🧘 تمارين استرخاء",
        "home_back_btn": "🔙 الرجوع للرئيسية",
        "home_btn": "🏠 الرئيسية",
        "tips_menu_title": "💡 النصائح الصحية\nاختاري اللي تبينها:",
        "tips_today_btn": "🌤️ نصيحة اليوم",
        "tips_season_btn": "🍂 نصائح الموسم",
        "home_followup_title": "📋 متابعة حالتك",
        "home_followup_empty": "ما عندنا تحليل سابق لك بعد 🙏\nابدئي بـ \"ابدأ تحليل جديد\" أول.",
        "home_followup_last": "آخر تحليل: {}\nالشدة: {}/5\nالأعراض: {}\n\nكيف تحسين الحين؟",
        "home_meds_btn": "💊 تذكير دوائي",
        "home_drug_btn": "🔍 بحث عن دواء",
        "home_share_btn": "🔗 شارك البوت",
        "med_ask_name": "💊 أرسلي اسم الدواء (مثال: باراسيتامول)\nأو اضغطي 🔙 للرجوع",
        "med_ask_times": "أرسلي أوقات أخذه بتوقيت السعودية، مثال:\n08:00 14:00 20:00\n(أو: 8 صباحا، 2 مساء)",
        "med_invalid_times": "ما قدرت أفهم الأوقات 🤔\nأرسليها بصيغة مثل: 08:00 14:00 20:00",
        "med_saved": "✅ تم حفظ تذكيرك لدواء: {}\nالأوقات (بتوقيت السعودية): {}\nبكل يوم أذكّرك فيها.",
        "med_reminder_text": "💊 تذكير دوائي:\nحان وقت أخذ دواك \"{}\"",
        "med_recover_ask": "😊 حالتك هل تحسّنت وتعالجت؟",
        "med_recover_yes_btn": "✅ تعافيت — أوقف التذكير",
        "med_recover_no_btn": "😐 لسه تعبان — كمّل التذكير",
        "med_recovered_msg": "ألف مبروك! 🎉 بأسعدنا شفاؤك 💚\nأوقفنا تذكير الدواء.\nولو رجعت الأعراض، /start بيخدمك في أي وقت.",
        "med_continue_msg": "الله يعافيك، استمري على الدواء حسب وصف الطبيب 💊\nولو ما تحسّنت خلال فترة، راجعي طبيبك.\n\nنصيحة لك اليوم:",
        "checkin_prompt": "📋 متابعة يومية: كيف تشعرين اليوم؟\n(من 1 = سيء جداً إلى 5 = ممتاز)",
        "checkin_labels": ["1️⃣ سيء جداً", "2️⃣ سيء", "3️⃣ متوسط", "4️⃣ جيد", "5️⃣ ممتاز"],
        "checkin_thanks": "تم تسجيل حالتك ✅\n{label}\nبقدّرك كل يوم ليتابع تقدمك 💪",
        "checkin_emoji": ["😞", "😕", "😐", "🙂", "😊"],
        "progress_title": "📈 تقدمك آخر 7 أيام",
        "progress_empty": "ما عندي تسجيلات بعد 📋\nبسألك كل يوم عن حالتك، وبصير عندك مخطط تحسن. 💪",
        "rule_emergency_note": "🚨 هذه الأعراض ترتقي للأولوية العالية (طوارئ) — يُنصح بالتوجه الفوري للطوارئ أو أقرب مركز صحي.",
        "low_conf_note": "⚠️ المعلومات المتوفرة غير كافية لنتيجة دقيقة — يُنصح بمراجعة الطبيب للفحص.",
        "emergency_title": "🆘 أرقام الطوارئ في السعودية",
        "emergency_block": "🚑 الإسعاف (الهلال الأحمر): 997\n☎️ الطوارئ الموحد: 911\n🩺 استشارات وزارة الصحة (24/7): 937\n🚓 الشرطة: 999\n🚒 الدفاع المدني: 998",
        "home_emergency_btn": "🆘 أرقام الطوارئ",
        "home_blood_btn": "🩸 تحليل الدم",
        "home_voice_on_btn": "🔊 الرد الصوتي: مفعّل",
        "home_voice_off_btn": "🔇 الرد الصوتي: مطفأ",
        "voice_toggle_on_msg": "🎙️ تم تفعيل الرد الصوتي!\n\nالحين أحط ملخص النتيجة لك بصوت واضح بعد كل تحليل، وأصلاً أقدر أفهم صوتك في كل المراحل. جربي!",
        "voice_toggle_off_msg": "🔇 تم إيقاف الرد الصوتي.\n\nتقدرين ترجعينه متى ما ودك من نفس الزر.",
        "speak_btn": "🔊 اقرأ لي",
        "speak_expired": "🔇 هذه الرسالة انتهت صلاحيتها. أرسلي رسالة جديدة.",
        "speak_fail": "ما قدرت أجيب الصوت 🤔 جربي مرة ثانية.",
        "blood_voice_gender_ask": "ممتاز! الحين أرسلي قيم التحليل بالكتابة أو صورة أو صوت.",
        "voice_home_unknown": "🤔 ما فهمت الأمر. قولي مثلاً:\n• \"ابي أبدأ تحليل\"\n• \"ابي تحليل دم\"\n• \"ابي أرقام الطوارئ\"\n• \"ابي نصائح\"\n• \"ابي تذكير دوائي\"",
        "blood_ask_gender": "🩸 تحليل الدم\nنطاقات بعض القيم (مثل الهيموغلوبين) تختلف بين الجنسين.\nاختاري جنسك:\n• ذكر\n• أنثى",
        "blood_ask_values": "🩸 أرسلي التحليل بإحدى الطرق:\n1️⃣ صورة التقرير (صورية أو مرفقة كملف)\n2️⃣ ملف PDF للتقرير\n3️⃣ كتابة القيم بالشكل:\nهيموغلوبين 12.5، WBC 11، صفائح 150\n\n💡 لو التحليل لطفل، اكتبي عمره (مثال: طفل 4) في البداية.",
        "blood_empty": "ما قدرت أستخرج قيم واضحة 🤔\nأرسلي الصورة من جديد، أو اكتبي القيم بالشكل:\nهيموغلوبين 12.5، WBC 11.2، صفائح 150",
        "blood_pdf_unsupported": "📄 ما قدرت أقرأ ملف PDF هذا 🤔\nأرسلي الصورة بشكل واضح، أو اكتبي القيم بالشكل:\nهيموغلوبين 12.5، WBC 11",
        "blood_file_unsupported": "🤔 ما أقدر أقرأ هذا النوع من الملفات.\nأرسلي صورة واضحة للتقرير (صورة أو PDF)، أو اكتبي القيم.\nمثال: هيموغلوبين 12.5، WBC 11، صفائح 150",
        "blood_voice_urgent": "انتبهي! قراءات التحليل تحتاج تقييماً عاجلاً، هذه التفاصيل:",
        "blood_voice_seedoctor": "نصيحة: في قراءات خارج النطاق الطبيعي، وهي:",
        "blood_voice_normal": "أخبار ممتازة! كل قراءات التحليل ضمن النطاق الطبيعي.",
        "blood_retry_btn": "🔄 تحليل تحليل آخر",
        "blood_chart_caption": "📊 قيمك مقابل النطاق المرجعي (الأحمر = خارج النطاق)",
        "doctor_q_label": "📋 أسئلة اسأليها طبيبك",
        "checkin_deteriorate_msg": "⚠️ انتبهي: حالتك في تدهور مقارنة بالأيام الماضية.\nأنصحك بمراجعة طبيب قريباً، ولو ارتفعت الشدة زيادة راجعي الطوارئ.",
        "pdf_btn": "📄 ملف PDF للتقرير",
        "pdf_caption": "📄 تقرير SymptoSense — جاهز للمشاركة مع طبيبك",
        "drug_ask_name": "🔍 اكتبي اسم الدواء اللي تبين تعرفين عنه (مثال: بنادول)",
        "drug_found": "🔍 معلومات عن: {}",
        "drug_unknown": "🤔 ما لقيت هذا الدواء بقاعدة البيانات عندي. جرّبي اسم آخر، أو اسألي صيدلي.",
        "feedback_title": "⭐ هل أفادك التحليل اليوم؟",
        "feedback_opt_great": "😍 ممتاز",
        "feedback_opt_good": "🙂 جيد",
        "feedback_opt_ok": "😐 عادي",
        "feedback_opt_bad": "😞 لا",
        "feedback_thanks": "شكراً لتقييمك! يساعدنا نحسّن البوت 🌟",
        "feedback_ask_comment": "💬 نعتذر إن التجربة ما كانت ممتازة.\nأخبرينا وش كان السبب؟ ووش نقدر نعدّل عشان نتحسّن؟",
        "feedback_comment_thanks": "🙏 شكراً لصراحتك! راح نراجع ملاحظتك ونشتغل على تحسينها.",
        "share_title": "🔗 شاركي البوت مع اللي تحبينهم 👇",
    },
    "en": {
        "welcome": "Welcome to SymptoSense 🏥\nYour smart assistant for symptom analysis based on trusted medical sources.",
        "choose_lang": "Please choose your language:\nالرجاء اختيار اللغة:",
        "ask_age": "How old are you? (enter a number, e.g. 28)\n🎤 You can reply by voice or text",
        "invalid_age": "Please enter a valid age between 1 and 120",
        "ask_gender": "What is your gender?\n🎤 Reply by voice or tap the buttons",
        "male": "👨 Male",
        "female": "👩 Female",
        "invalid_gender": "Please choose one of the options",
        "ask_symptoms": "What are your symptoms?\nChoose from the buttons 👇\n\n🖊️ If you can't find your exact symptom, type it yourself (e.g., leg pain)\nPress ✅ Done when finished",
        "symptom_added": "Added! ({} symptoms)\nAdd more or press ✅ Done",
        "symptom_typing_prompt": "✍️ Type the exact symptom you feel below 👇\n(e.g., leg pain, itchy eyes...)\nThen press ✅ Done",
        "ask_duration": "How long have you had these symptoms?\n🎤 Reply by voice or tap the buttons",
        "ask_severity": "What is the severity of your pain?\n1️⃣ Very Mild\n2️⃣ Moderate\n3️⃣ Medium\n4️⃣ Severe\n5️⃣ Critical\n🎤 Or reply by voice",
        "ask_conditions": "Do you have any chronic medical conditions?",
        "ask_notes": "Any additional notes? (or press Skip)",
        "ask_medications": "💊 Are you currently taking any medications? Name them (or tap Skip if none)",
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
        "followup_prompt": "💬 For any questions about your health condition, type it here and I'll answer.\n(Or tap \"🔄 New Analysis\" to start over)",
        "followup_thinking": "🤔 One moment, thinking about your question...",
        "followup_error": "⚠️ Something went wrong answering your question. Try again or tap \"🔄 New Analysis\".",
        "share_location_prompt": "🚨 Your case needs attention. Want me to help find the nearest hospital? Tap the button below to share your location.",
        "share_location_button": "📍 Share my location & find nearest hospital",
        "hospitals_title": "🏥 Nearest hospitals to your location",
        "hospitals_none": "Couldn't find nearby hospitals in the available data. Please call emergency services (997) or search Google Maps directly.",
        "hospitals_footer": "\n📞 For emergencies, don't hesitate to call: 997",
        "unsubscribed": "✅ You've been unsubscribed from daily tips. You can re-enable them anytime by sending /start.",
        "daily_tip_header": "🌤️ Today's tip from SymptoSense",
        "daily_tip_footer": "\n\n(To stop these daily messages, send /stop)",
        "medication_label": "💊 Medication Note",
        "medication_disclaimer": "These are general cautions only, not a precise drug-interaction check. Consult your pharmacist or doctor with any medication questions.",
        "medication_guidance_label": "🩺 Should I continue my medication?",
        "voice_error": "⚠️ Couldn't understand the voice message, please try recording again or type instead.",
        "voice_empty": "🤔 Didn't catch any clear speech in that recording, please try again.",
        "voice_symptoms_detected": "✅ Recorded: {} (total {} symptoms)\n\nContinue by voice or text, or tap \"✅ Done\"",
        "new_analysis": "🔄 New Analysis",
        "cancelled": "Cancelled. Type /start to begin again",
        "skip": "⏭️ Skip",
        "done": "✅ Done",
        "no_conditions": "No previous conditions",
        "write_manually": "✏️ Type manually",
        "add_symptom_first": "Please add at least one symptom!",
        "invalid_choice": "Please choose from the buttons",
        "error": "An error occurred. Type /start to try again",
        "duration_options": [["⏰ Less than 24 hours", "📅 1-3 days"], ["📅 4-7 days", "🗓️ 1-2 weeks"], ["🗓️ More than 2 weeks", "📆 More than a month"]],
        "severity_options": [["1️⃣ Very Mild", "2️⃣ Moderate"], ["3️⃣ Medium", "4️⃣ Severe"], ["5️⃣ Critical"]],
        "severity_map": {"1️⃣ Very Mild": 1, "2️⃣ Moderate": 2, "3️⃣ Medium": 3, "4️⃣ Severe": 4, "5️⃣ Critical": 5},
        "conditions_kb": [["No previous conditions"], ["Diabetes", "Blood Pressure"], ["Heart Disease", "Asthma"], ["✏️ Type manually"]],
        "quick_symptoms": [["🤕 Headache", "🌡️ Fever", "😷 Cough"], ["💔 Chest Pain", "🤢 Nausea", "😴 Fatigue"], ["😤 Shortness of Breath", "💫 Dizziness", "🦴 Joint Pain"], ["🤰 Stomach Pain", "🥶 Chills", "👁️ Red Eyes"], ["🦵 Leg Pain", "😣 Sore Throat", "🖐️ Itching"], ["✍️ Not listed — I'll type it"], ["✅ Done"]],
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
        "infermedica_label": "🤖 Machine Learning Model (Naive Bayes)",
        "infermedica_note": "Probabilities from a statistically trained ML model on symptom data (test accuracy: 65.3%) — for awareness only, not a final diagnosis",
        "firstaid_title": "🚑 Quick First Aid Guide",
        "firstaid_choose": "🚑 Quick First Aid Guide\n\nChoose a situation:",
        "firstaid_footer": "\n\n⚠️ First aid guidance only — doesn't replace calling emergency services (997) when needed.",
        "relax_title": "🧘‍♂️ Relaxation & Breathing Exercises",
        "season_title": "🍂 Seasonal Tips",
        "fu_prompt": "👋 Checking in: how are you feeling after your last analysis?\nYour choice is tracked anonymously for statistics.",
        "fu_improved_btn": "✅ Improved",
        "fu_same_btn": "➖ Same",
        "fu_worse_btn": "🔴 Worse",
        "fu_thanks_improved": "🌟 Great to hear! Keep up the good care — if symptoms return, don't hesitate to run a new analysis.",
        "fu_thanks_same": "Note: if symptoms persist unchanged for more than a week, it's best to see a doctor.",
        "fu_thanks_worse": "🚨 Your symptoms have worsened — I recommend seeing a doctor or the nearest ER, and don't hesitate. Take care of yourself.",
        "home_welcome": "🏠 Welcome to the home menu\nPick what you need 👇",
        "share_welcome": "🤝 Hello! A friend shared SymptoSense with you\nAnalyze your symptoms easily and get health tips 👇",
        "home_start_btn": "▶️ Start New Analysis",
        "home_tips_btn": "💡 Health Tips",
        "home_followup_btn": "📋 Follow-up",
        "home_firstaid_btn": "🚑 First Aid",
        "home_relax_btn": "🧘 Relax & Breathe",
        "home_back_btn": "🔙 Back to Home",
        "home_btn": "🏠 Home",
        "tips_menu_title": "💡 Health Tips\nPick one:",
        "tips_today_btn": "🌤️ Today's Tip",
        "tips_season_btn": "🍂 Seasonal Tips",
        "home_followup_title": "📋 Your Follow-up",
        "home_followup_empty": "We don't have a previous analysis for you yet 🙏\nStart with \"Start New Analysis\" first.",
        "home_followup_last": "Last analysis: {}\nSeverity: {}/5\nSymptoms: {}\n\nHow do you feel now?",
        "home_meds_btn": "💊 Med Reminders",
        "home_drug_btn": "🔍 Drug Lookup",
        "home_share_btn": "🔗 Share Bot",
        "med_ask_name": "💊 Send the medication name (e.g., Paracetamol)\nOr tap 🔙 to go back",
        "med_ask_times": "Send the times in Saudi Arabia time, e.g.:\n08:00 14:00 20:00\n(or: 8 am, 2 pm)",
        "med_invalid_times": "Couldn't understand those times 🤔\nSend them like: 08:00 14:00 20:00",
        "med_saved": "✅ Reminder saved for: {}\nTimes (Saudi time): {}\nI'll remind you daily.",
        "med_reminder_text": "💊 Med reminder:\nTime to take your \"{}\"",
        "med_recover_ask": "😊 Are you feeling better and recovered?",
        "med_recover_yes_btn": "✅ Recovered — Stop reminders",
        "med_recover_no_btn": "😐 Still unwell — Keep reminding",
        "med_recovered_msg": "That's great news! 🎉 So glad you've recovered 💚\nMedication reminders are now stopped.\nIf symptoms return, /start is here for you anytime.",
        "med_continue_msg": "Get well soon! Keep taking your medication as prescribed 💊\nAnd if you don't improve, do see your doctor.\n\nA tip for you today:",
        "checkin_prompt": "📋 Daily check-in: How do you feel today?\n(1 = very bad to 5 = excellent)",
        "checkin_labels": ["1️⃣ Very bad", "2️⃣ Bad", "3️⃣ Okay", "4️⃣ Good", "5️⃣ Excellent"],
        "checkin_thanks": "Logged ✅\n{label}\nI'll check in daily to track your progress 💪",
        "checkin_emoji": ["😞", "😕", "😐", "🙂", "😊"],
        "progress_title": "📈 Your progress (last 7 days)",
        "progress_empty": "No check-ins yet 📋\nI'll ask you daily, then you'll have an improvement chart. 💪",
        "rule_emergency_note": "🚨 These symptoms raise the priority to Emergency — seek urgent care or the nearest ER.",
        "low_conf_note": "⚠️ Not enough information for an accurate result — a doctor's visit is recommended.",
        "emergency_title": "🆘 Emergency numbers in Saudi Arabia",
        "emergency_block": "🚑 Ambulance (Red Crescent): 997\n☎️ Unified Emergency: 911\n🩺 Ministry of Health hotline (24/7): 937\n🚓 Police: 999\n🚒 Civil Defense: 998",
        "home_emergency_btn": "🆘 Emergency numbers",
        "home_blood_btn": "🩸 Blood test",
        "home_voice_on_btn": "🔊 Voice reply: ON",
        "home_voice_off_btn": "🔇 Voice reply: OFF",
        "voice_toggle_on_msg": "🎙️ Voice reply is ON!\n\nNow I'll send you a clear voice summary after every analysis, and I can already understand your voice at every step. Try it!",
        "voice_toggle_off_msg": "🔇 Voice reply is OFF.\n\nYou can turn it back on anytime from the same button.",
        "speak_btn": "🔊 Read it",
        "speak_expired": "🔇 This message has expired. Send a new message.",
        "speak_fail": "I couldn't produce audio 🤔 Try again.",
        "blood_voice_gender_ask": "Great! Now send your test values by typing, photo, or voice.",
        "voice_home_unknown": "🤔 I didn't understand that. Try saying:\n• \"I want to start an analysis\"\n• \"Blood test\"\n• \"Emergency numbers\"\n• \"Health tips\"\n• \"Medication reminder\"",
        "blood_ask_gender": "🩸 Blood test analysis\nSome reference ranges (e.g. hemoglobin) differ by gender.\nChoose your gender:\n• Male\n• Female",
        "blood_ask_values": "🩸 Send your test any of these ways:\n1️⃣ A photo of the lab report (camera or as a file)\n2️⃣ A PDF file of the report\n3️⃣ Type the values like:\nHemoglobin 12.5, WBC 11, Platelets 150\n\n💡 For a child, add the age first (e.g. Child 4).",
        "blood_empty": "I couldn't extract clear values 🤔\nSend the photo again, or type the values like:\nHemoglobin 12.5, WBC 11.2, Platelets 150",
        "blood_pdf_unsupported": "📄 I couldn't read this PDF 🤔\nSend a clear photo, or type the values like:\nHemoglobin 12.5, WBC 11",
        "blood_file_unsupported": "🤔 I can't read this type of file.\nSend a clear image of the report (photo or PDF), or type the values.\nExample: Hemoglobin 12.5, WBC 11, Platelets 150",
        "blood_voice_urgent": "Attention! Your blood test needs urgent evaluation. Details:",
        "blood_voice_seedoctor": "Heads up: some readings are outside the normal range:",
        "blood_voice_normal": "Great news! All your blood readings are within the normal range.",
        "blood_retry_btn": "🔄 Another test",
        "blood_chart_caption": "📊 Your values vs. reference range (red = out of range)",
        "doctor_q_label": "📋 Questions to ask your doctor",
        "checkin_deteriorate_msg": "⚠️ Your condition is worsening compared to previous days.\nWe recommend seeing a doctor soon, and if severity rises further, go to the ER.",
        "pdf_btn": "📄 PDF report",
        "pdf_caption": "📄 SymptoSense report — ready to share with your doctor",
        "drug_ask_name": "🔍 Type the medication name you want to know about (e.g., Panadol)",
        "drug_found": "🔍 Info about: {}",
        "drug_unknown": "🤔 I couldn't find that medication in my database. Try another name or ask a pharmacist.",
        "feedback_title": "⭐ Was today's analysis helpful?",
        "feedback_opt_great": "😍 Great",
        "feedback_opt_good": "🙂 Good",
        "feedback_opt_ok": "😐 Okay",
        "feedback_opt_bad": "😞 No",
        "feedback_thanks": "Thanks for your feedback! It helps us improve 🌟",
        "feedback_ask_comment": "💬 Sorry your experience wasn't great.\nTell us what went wrong and how we can improve?",
        "feedback_comment_thanks": "🙏 Thanks for your honesty! We'll review your note and work on it.",
        "share_title": "🔗 Share the bot with people you love 👇",
    }
}

def t(context, key):
    lang = context.user_data.get("lang", "ar")
    return TEXTS[lang][key]


class DBUserDataPersistence(BasePersistence):
    """Stores only durable user_data (currently: language) in the DB so preferences survive
    restarts/redeploys without resuming any in-progress flow."""

    # Keys worth keeping across restarts. Everything else (analysis answers,
    # _await, med_name, ...) is transient and must not resume old flows.
    _PERSISTENT_KEYS = {"lang"}

    def __init__(self):
        super().__init__(
            store_data=PersistenceInput(
                user_data=True,
                chat_data=False,
                bot_data=False,
                callback_data=False,
            ),
            update_interval=10,
        )
        self._cache = {}
        self._seeded = False

    @staticmethod
    def _durable(data):
        if not data:
            return {}
        return {k: v for k, v in data.items() if k in DBUserDataPersistence._PERSISTENT_KEYS}

    async def get_user_data(self):
        if not self._seeded:
            try:
                self._cache = db.all_user_data()
            except Exception as e:
                logger.warning(f"all_user_data failed: {e}")
            self._seeded = True
        return self._cache

    async def get_chat_data(self):
        return {}

    async def get_bot_data(self):
        return {}

    async def get_callback_data(self):
        return None

    async def get_conversations(self, name):
        try:
            return db.all_conversations().get(name, {})
        except Exception as e:
            logger.warning(f"all_conversations failed: {e}")
            return {}

    async def update_conversation(self, name, key, new_state):
        try:
            db.save_conversation(name, key, new_state)
        except Exception as e:
            logger.warning(f"save_conversation failed: {e}")

    async def update_user_data(self, user_id, data):
        durable = self._durable(data)
        try:
            db.save_user_data(user_id, durable)
        except Exception as e:
            logger.warning(f"save_user_data failed: {e}")
        self._cache[user_id] = data

    async def update_chat_data(self, chat_id, data):
        pass

    async def update_bot_data(self, data):
        pass

    async def update_callback_data(self, data):
        pass

    async def refresh_user_data(self, user_id, user_data):
        if user_id in self._cache:
            return
        try:
            data = db.load_user_data(user_id)
            if data:
                self._cache[user_id] = data
                user_data.clear()
                user_data.update(data)
        except Exception as e:
            logger.warning(f"load_user_data failed: {e}")

    async def refresh_chat_data(self, chat_id, chat_data):
        pass

    async def refresh_bot_data(self, bot_data):
        pass

    async def drop_user_data(self, user_id):
        try:
            db.clear_user_data(user_id)
        except Exception as e:
            logger.warning(f"clear_user_data failed: {e}")
        self._cache.pop(user_id, None)

    async def drop_chat_data(self, chat_id):
        pass

    async def drop_bot_data(self):
        pass

    async def flush(self):
        pass

def _share_url(context):
    username = context.bot_data.get("username", "")
    if not username:
        return "https://t.me/"
    bot_link = f"https://t.me/{username}"
    return f"https://t.me/share/url?url={urllib.parse.quote(bot_link, safe='')}"


async def _reset_conv_core(chat_id, user_id, context):
    """Ends any active analysis conversation so stale state can't hijack other flows."""
    key = (chat_id, user_id)
    changed = False
    for group in context.application.handlers.values():
        for handler in group:
            if isinstance(handler, ConversationHandler):
                try:
                    if key in handler._conversations:
                        handler._update_state(ConversationHandler.END, key)
                        changed = True
                except Exception as e:
                    logger.warning(f"Conversation reset failed: {e}")
    if changed:
        try:
            await context.application.update_persistence()
        except Exception as e:
            logger.warning(f"Conversation persistence flush failed: {e}")


async def _reset_conversation(update, context):
    chat_id = update.effective_chat.id if update.effective_chat else None
    user_id = update.effective_user.id if update.effective_user else None
    if not chat_id or not user_id:
        return
    await _reset_conv_core(chat_id, user_id, context)


async def _set_conv_state(chat_id, user_id, context, state):
    """Moves the active conversation to a specific state (used by voice routing)."""
    key = (chat_id, user_id)
    for group in context.application.handlers.values():
        for handler in group:
            if isinstance(handler, ConversationHandler):
                try:
                    handler._update_state(state, key)
                    await context.application.update_persistence()
                except Exception as e:
                    logger.warning(f"Conversation state set failed: {e}")


def _menu_read_text(context) -> str:
    """Readable list of the main-menu options so the 🔊 button can read them."""
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS[lang]
    toggle = tx["home_voice_on_btn"] if context.user_data.get("voice_on") else tx["home_voice_off_btn"]
    labels = [
        tx["home_start_btn"], tx["home_tips_btn"], tx["home_followup_btn"],
        tx["home_firstaid_btn"], tx["home_relax_btn"], tx["home_meds_btn"],
        tx["home_drug_btn"], tx["home_emergency_btn"], tx["home_blood_btn"], toggle,
    ]
    return "\n".join("• " + label for label in labels if label)

def _home_keyboard(context):
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS[lang]
    share_url = _share_url(context)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(tx["home_start_btn"], callback_data="home_start")],
        [InlineKeyboardButton(tx["home_tips_btn"], callback_data="home_tips"),
         InlineKeyboardButton(tx["home_followup_btn"], callback_data="home_followup")],
        [InlineKeyboardButton(tx["home_firstaid_btn"], callback_data="home_firstaid"),
         InlineKeyboardButton(tx["home_relax_btn"], callback_data="home_relax")],
        [InlineKeyboardButton(tx["home_meds_btn"], callback_data="home_meds"),
         InlineKeyboardButton(tx["home_drug_btn"], callback_data="home_drug")],
        [InlineKeyboardButton(tx["home_emergency_btn"], callback_data="home_emergency")],
        [InlineKeyboardButton(tx["home_blood_btn"], callback_data="home_blood")],
        [InlineKeyboardButton(tx["home_voice_on_btn"] if context.user_data.get("voice_on") else tx["home_voice_off_btn"], callback_data="home_voice_toggle")],
        [InlineKeyboardButton(tx["home_share_btn"], url=share_url)],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows the main menu. A new analysis starts via the home_start button."""
    lang = context.user_data.get("lang", "ar")
    context.user_data.clear()
    context.user_data["symptoms"] = []
    context.user_data["lang"] = lang
    try:
        db.log_visit(update.effective_user.id)
    except Exception as visit_err:
        logger.warning(f"Visit logging failed: {visit_err}")
    await _reset_conversation(update, context)
    from_share = bool(context.args) and context.args[0] == "share"
    welcome = TEXTS[lang]["share_welcome"] if from_share else TEXTS[lang]["home_welcome"]
    _SPEAK_OVERRIDE[update.effective_chat.id] = welcome + "\n\n" + _menu_read_text(context)
    await update.message.reply_text(welcome, reply_markup=_home_keyboard(context))


async def home_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.pop("_await", None)
    await _reset_conversation(update, context)
    lang = context.user_data.get("lang", "ar")
    _SPEAK_OVERRIDE[update.effective_chat.id] = TEXTS[lang]["home_welcome"] + "\n\n" + _menu_read_text(context)
    await query.message.reply_text(TEXTS[lang]["home_welcome"], reply_markup=_home_keyboard(context))

async def home_meds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await _reset_conversation(update, context)
    await _home_action_meds(query.message, context)

async def home_drug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await _reset_conversation(update, context)
    await _home_action_drug(query.message, context)

def parse_med_times(text):
    """Extracts times from free text (KSA time) and returns them in UTC 'HH:MM'."""
    results = []
    for m in re.finditer(
        r"(\d{1,2})(?:\s*:\s*(\d{1,2}))?\s*(صباحا|ص|مساء|م|ام|pm|am)?", text, re.IGNORECASE
    ):
        h = int(m.group(1))
        mi = int(m.group(2) or 0)
        if h > 24 or mi > 59:
            continue
        suffix = (m.group(3) or "").lower()
        if suffix in ("م", "مساء", "pm"):
            if h < 12:
                h += 12
        elif suffix in ("ص", "صباحا", "am"):
            if h == 12:
                h = 0
        elif h == 24:
            h = 0
        if h > 23:
            continue
        results.append(f"{(h - 3) % 24:02d}:{mi:02d}")
    return results

async def handle_tool_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await_flag = context.user_data.get("_await")
    if not await_flag:
        return
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS[lang]
    text = update.message.text.strip()
    try:
        if await_flag == "med_name":
            context.user_data["med_name"] = text
            context.user_data["_await"] = "med_times"
            await update.message.reply_text(tx["med_ask_times"])
        elif await_flag == "med_times":
            times = parse_med_times(text)
            if not times:
                await update.message.reply_text(tx["med_invalid_times"])
                return
            times = sorted(set(times))[:6]
            med = context.user_data.get("med_name", "؟")
            for t in times:
                try:
                    db.add_med_reminder(update.effective_user.id, med, t, lang)
                except Exception as e:
                    logger.warning(f"Med reminder save failed: {e}")
            context.user_data.pop("_await", None)
            ksa_times = ", ".join(f"{((int(t[:2]) + 3) % 24):02d}:{t[3:]}" for t in times)
            await update.message.reply_text(tx["med_saved"].format(med, ksa_times))
            await _reschedule_meds(context)
        elif await_flag == "drug":
            info = medication_warnings.lookup_drug(text)
            context.user_data.pop("_await", None)
            if info:
                name = info["name_ar"] if lang == "ar" else info["name_en"]
                warning = info["warning_ar"] if lang == "ar" else info["warning_en"]
                await update.message.reply_text(
                    f"{tx['drug_found'].format(name)}\n\n{warning}\n\n⚠️ للتوعية فقط — راجعي الصيدلي أو الطبيب."
                    if lang == "ar" else
                    f"{tx['drug_found'].format(name)}\n\n{warning}\n\n⚠️ For awareness only — consult a pharmacist or doctor."
                )
            else:
                await update.message.reply_text(tx["drug_unknown"])
        elif await_flag == "feedback_comment":
            context.user_data.pop("_await", None)
            record_id = context.user_data.get("_last_record_id")
            try:
                db.update_feedback_comment(update.effective_user.id, record_id, text[:500])
            except Exception as e:
                logger.warning(f"Feedback comment save failed: {e}")
            await update.message.reply_text(tx["feedback_comment_thanks"])
    except Exception as e:
        logger.error(f"Tool text error: {e}")

async def send_med_reminder(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    tx = TEXTS.get(data.get("lang", "ar"), TEXTS["ar"])
    text = tx["med_reminder_text"].format(data["med"])
    try:
        await context.bot.send_message(chat_id=data["chat_id"], text=text)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(tx["med_recover_yes_btn"], callback_data="med_recovered")],
            [InlineKeyboardButton(tx["med_recover_no_btn"], callback_data="med_continue")],
        ])
        await context.bot.send_message(
            chat_id=data["chat_id"], text=tx["med_recover_ask"], reply_markup=kb
        )
    except Exception as e:
        logger.warning(f"Med reminder send failed: {e}")

async def med_recover_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS.get(lang, TEXTS["ar"])
    user_id = update.effective_user.id
    if query.data == "med_recovered":
        try:
            db.remove_med_reminders(user_id)
        except Exception as e:
            logger.warning(f"Med reminder removal failed: {e}")
        await _reschedule_meds(context)
        await query.message.reply_text(tx["med_recovered_msg"])
    else:
        tip = health_tips.get_random_tip(lang)
        await query.message.reply_text(tx["med_continue_msg"] + "\n\n" + tip)

async def send_daily_checkin(context: ContextTypes.DEFAULT_TYPE):
    try:
        subscribers = db.get_subscribers()
    except Exception as e:
        logger.warning(f"Could not load subscribers for check-in: {e}")
        return
    for user_id, lang in subscribers:
        tx = TEXTS.get(lang, TEXTS["ar"])
        emojis = tx["checkin_emoji"]
        labels = tx["checkin_labels"]
        row1 = [InlineKeyboardButton(f"{emojis[i]} {labels[i]}", callback_data=f"ci_{i+1}") for i in range(3)]
        row2 = [InlineKeyboardButton(f"{emojis[i]} {labels[i]}", callback_data=f"ci_{i+1}") for i in range(3, 5)]
        kb = InlineKeyboardMarkup([row1, row2])
        try:
            await context.bot.send_message(chat_id=user_id, text=tx["checkin_prompt"], reply_markup=kb)
        except Exception as e:
            logger.warning(f"Daily check-in send failed for {user_id}: {e}")

async def checkin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS.get(lang, TEXTS["ar"])
    try:
        sev = int(query.data.split("_", 1)[1])
    except Exception:
        sev = 3
    sev = max(1, min(5, sev))
    try:
        db.save_daily_checkin(update.effective_user.id, sev)
    except Exception as e:
        logger.warning(f"Daily check-in save failed: {e}")
    label = tx["checkin_labels"][sev - 1]
    await query.message.reply_text(tx["checkin_thanks"].format(label=label))
    try:
        hist = db.get_daily_checkins(update.effective_user.id, days=7)
        vals = [h[1] for h in hist]
        if _is_deteriorating(vals):
            await query.message.reply_text(tx["checkin_deteriorate_msg"])
    except Exception as det_err:
        logger.warning(f"Trend check failed: {det_err}")

def generate_progress_chart(data, lang="ar"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    days = [d[0][5:] for d in data]
    vals = [d[1] for d in data]
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.plot(range(len(vals)), vals, marker="o", color="#00b4d8", linewidth=2)
    ax.set_ylim(0.5, 5.5)
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_xticks(range(len(days)))
    ax.set_xticklabels(days, fontsize=9)
    ax.set_title("تقدمك آخر 7 أيام" if lang == "ar" else "Your progress (last 7 days)")
    ax.set_ylabel("الشدة" if lang == "ar" else "Severity")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf

async def progress_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS.get(lang, TEXTS["ar"])
    try:
        data = db.get_daily_checkins(update.effective_user.id, days=7)
    except Exception as e:
        logger.warning(f"Progress load failed: {e}")
        data = []
    if not data:
        await update.message.reply_text(tx["progress_empty"])
        return
    try:
        chart = generate_progress_chart(data, lang)
        await update.message.reply_photo(photo=chart, caption=tx["progress_title"])
    except Exception as chart_err:
        logger.warning(f"Progress chart failed: {chart_err}")
        lines = [f"{d[0]}: {d[1]}/5" for d in data]
        await update.message.reply_text(tx["progress_title"] + "\n" + "\n".join(lines))

async def _reschedule_meds(context: ContextTypes.DEFAULT_TYPE):
    jq = context.application.job_queue
    if not jq:
        return
    for job in list(jq.jobs()):
        if job.name and job.name.startswith("med_"):
            job.schedule_removal()
    try:
        reminders = db.get_active_med_reminders()
    except Exception as e:
        logger.error(f"Could not load med reminders: {e}")
        return
    now = datetime.now(timezone.utc)
    for user_id, med, time_utc, lang in reminders:
        try:
            h, mi = map(int, time_utc.split(":"))
        except Exception:
            continue
        when = now.replace(hour=h, minute=mi, second=0, microsecond=0)
        if when <= now:
            when += timedelta(days=1)
        jq.run_once(
            send_med_reminder, when,
            name=f"med_{user_id}_{time_utc}_{med[:15]}",
            data={"chat_id": user_id, "med": med, "lang": lang},
        )

async def feedback_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS.get(lang, TEXTS["ar"])
    rating = query.data.split("_", 1)[1] if "_" in query.data else "ok"
    record_id = context.user_data.get("_last_record_id")
    try:
        db.save_feedback(update.effective_user.id, record_id, rating)
    except Exception as e:
        logger.warning(f"Feedback save failed: {e}")
    if rating == "bad":
        context.user_data["_await"] = "feedback_comment"
        await query.message.reply_text(tx["feedback_ask_comment"])
    else:
        await query.message.reply_text(tx["feedback_thanks"])

async def _home_action_start(message, context, user_id) -> int:
    """Starts a fresh analysis: clears state, asks language. Works with buttons or voice."""
    try:
        db.log_visit(user_id)
    except Exception as visit_err:
        logger.warning(f"Visit logging failed: {visit_err}")
    lang = context.user_data.get("lang", "ar")
    context.user_data.clear()
    context.user_data["symptoms"] = []
    context.user_data["lang"] = lang
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar"),
         InlineKeyboardButton("English 🇺🇸", callback_data="lang_en")]
    ])
    await message.reply_text(
        "الرجاء اختيار اللغة\nPlease choose your language:",
        reply_markup=kb,
    )
    return LANG

async def _home_action_blood(message, context) -> int:
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS[lang]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(tx["male"], callback_data="bg_m"),
         InlineKeyboardButton(tx["female"], callback_data="bg_f")],
        [InlineKeyboardButton(tx["home_btn"], callback_data="home_menu")],
    ])
    await message.reply_text(tx["blood_ask_gender"], reply_markup=kb)
    return BLOOD_GENDER

async def home_tips(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await _reset_conversation(update, context)
    await _home_action_tips(query.message, context)

async def tips_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS[lang]
    tip = health_tips.get_random_tip(lang)
    await query.message.reply_text(f"{tx['daily_tip_header']}\n\n{tip}")

async def tips_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS[lang]
    code, label, tips = health_tips.get_season(lang)
    lines = [f"{tx['season_title']} — {label}", ""] + tips
    await query.message.reply_text("\n\n".join(lines))

async def _home_action_tips(message, context):
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS[lang]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(tx["tips_today_btn"], callback_data="tips_today")],
        [InlineKeyboardButton(tx["tips_season_btn"], callback_data="tips_season")],
        [InlineKeyboardButton(tx["home_back_btn"], callback_data="home_menu")],
    ])
    await message.reply_text(tx["tips_menu_title"], reply_markup=kb)

async def _home_action_followup(message, context, user_id):
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS[lang]
    rec = None
    try:
        rec = db.get_last_record(user_id)
    except Exception as fu_err:
        logger.warning(f"Follow-up home error: {fu_err}")
    if not rec:
        text = tx["home_followup_empty"]
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(tx["home_start_btn"], callback_data="home_start")]])
    else:
        text = tx["home_followup_title"] + "\n\n" + tx["home_followup_last"].format(
            rec["timestamp"][:16].replace("T", " "), rec["severity"], ", ".join(rec["symptoms"])
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(tx["fu_improved_btn"], callback_data=f"fu_improved_{rec['id']}"),
             InlineKeyboardButton(tx["fu_same_btn"], callback_data=f"fu_same_{rec['id']}")],
            [InlineKeyboardButton(tx["fu_worse_btn"], callback_data=f"fu_worse_{rec['id']}")],
            [InlineKeyboardButton(tx["home_back_btn"], callback_data="home_menu")],
        ])
    await message.reply_text(text, reply_markup=kb)

async def _home_action_firstaid(message, context):
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS[lang]
    rows = [[InlineKeyboardButton(label, callback_data=f"fa_{key}")] for key, (label, _) in wellbeing.first_aid_categories(lang)]
    rows.append([InlineKeyboardButton(tx["home_back_btn"], callback_data="home_menu")])
    await message.reply_text(tx["firstaid_choose"], reply_markup=InlineKeyboardMarkup(rows))

async def _home_action_relax(message, context):
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS[lang]
    await message.reply_text(tx["relax_title"] + "\n\n" + wellbeing.relax_guide(lang))

async def _home_action_emergency(message, context):
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS[lang]
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(tx["home_back_btn"], callback_data="home_menu")]])
    await message.reply_text(
        f"<b>{_html_escape(tx['emergency_title'])}</b>\n\n{_html_escape(tx['emergency_block'])}",
        parse_mode="HTML", reply_markup=kb,
    )

async def _home_action_voice_toggle(message, context):
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS[lang]
    context.user_data["voice_on"] = not context.user_data.get("voice_on")
    msg = tx["voice_toggle_on_msg"] if context.user_data["voice_on"] else tx["voice_toggle_off_msg"]
    await message.reply_text(msg, reply_markup=_home_keyboard(context))

async def _home_action_meds(message, context):
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS[lang]
    context.user_data["_await"] = "med_name"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(tx["home_back_btn"], callback_data="home_menu")]])
    await message.reply_text(tx["med_ask_name"], reply_markup=kb)

async def _home_action_drug(message, context):
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS[lang]
    context.user_data["_await"] = "drug"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(tx["home_back_btn"], callback_data="home_menu")]])
    await message.reply_text(tx["drug_ask_name"], reply_markup=kb)

async def home_followup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await _reset_conversation(update, context)
    await _home_action_followup(query.message, context, update.effective_user.id)

async def home_firstaid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await _reset_conversation(update, context)
    await _home_action_firstaid(query.message, context)

async def home_relax(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await _reset_conversation(update, context)
    await _home_action_relax(query.message, context)

async def home_emergency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await _reset_conversation(update, context)
    await _home_action_emergency(query.message, context)

async def home_voice_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await _home_action_voice_toggle(query.message, context)

def _downscale_jpeg(image_bytes, max_side=1600, quality=85):
    """Downscales and re-encodes an image to JPEG to keep Groq vision payloads small."""
    from PIL import Image
    img = Image.open(io.BytesIO(image_bytes))
    img = img.convert("RGB")
    w, h = img.size
    scale = min(1.0, max_side / max(w, h))
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=quality)
    return out.getvalue()


def _extract_blood_from_image(client, image_bytes):
    """Best-effort OCR of CBC values from a lab-report photo using Groq vision."""
    import base64
    b64 = base64.b64encode(image_bytes).decode("ascii")
    resp = client.chat.completions.create(
        model="llama-3.2-90b-vision-preview",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": (
                    "Extract ALL blood test (CBC) values from this lab report image. "
                    "Return ONLY lines in this exact form, one per line, no explanations: "
                    "HGB 13.5\nWBC 11.2\nRBC 4.8\nHCT 40\nMCV 90\nMCH 30\nMCHC 33\n"
                    "PLT 250\nNeut 55\nLymph 30\nRDW 12.5\n"
                    "If a value is missing or unreadable, skip that line. "
                    "If the patient is a child, start with: Child <age>.")},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ],
        }],
        max_tokens=500,
        temperature=0,
    )
    return resp.choices[0].message.content or ""


async def _send_blood_report(message, context, entries, age):
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS.get(lang, TEXTS["ar"])
    gender = context.user_data.get("blood_gender", "f")
    results, notes, dangers, level, child_note = blood_test.analyze_blood(entries, gender, age)
    text = blood_test.build_text(results, gender, lang, notes, dangers, child_note)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(tx["blood_retry_btn"], callback_data="blood_restart")],
        [InlineKeyboardButton(tx["home_btn"], callback_data="home_menu")],
    ])
    await message.reply_text(text, parse_mode="HTML", reply_markup=kb)
    try:
        chart = blood_test.generate_blood_chart(results)
        if chart:
            await message.reply_photo(photo=chart, caption=tx["blood_chart_caption"])
    except Exception as chart_err:
        logger.warning(f"Blood chart failed: {chart_err}")
    if level in ("urgent", "emergency"):
        await message.reply_text(
            f"<b>{_html_escape(tx['emergency_title'])}</b>\n\n{_html_escape(tx['emergency_block'])}",
            parse_mode="HTML",
        )
    # --- Spoken voice summary (only when voice reply is enabled) ---
    try:
        if level in ("urgent", "emergency"):
            spoken = tx["blood_voice_urgent"] + " " + "، ".join(
                (ar if lang == "ar" else en) for _lv, ar, en in dangers
            )
        else:
            abnormal = [r for r in results if r["status"] != "normal"]
            if abnormal:
                spoken = tx["blood_voice_seedoctor"] + " " + "، ".join(
                    (r["name_ar"] if lang == "ar" else r["name_en"])
                    + (" منخفض" if r["status"] == "low" else " مرتفع") for r in abnormal
                )
            else:
                spoken = tx["blood_voice_normal"]
        await _send_voice_summary(message, context, spoken)
    except Exception as voice_err:
        logger.warning(f"Blood voice failed: {voice_err}")


async def home_blood(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await _reset_conversation(update, context)
    return await _home_action_blood(query.message, context)


async def blood_gender_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS[lang]
    context.user_data["blood_gender"] = "m" if query.data == "bg_m" else "f"
    await query.message.reply_text(tx["blood_ask_values"])
    return BLOOD_VALUES


async def blood_values(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS.get(lang, TEXTS["ar"])
    entries, age = blood_test.parse_blood_text(update.message.text)
    if not entries:
        await update.message.reply_text(tx["blood_empty"])
        return BLOOD_VALUES
    await _send_blood_report(update.message, context, entries, age)
    return BLOOD_VALUES


async def blood_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS.get(lang, TEXTS["ar"])
    try:
        tg_file = await update.message.photo[-1].get_file()
        raw = await tg_file.download_as_bytearray()
        img = _downscale_jpeg(bytes(raw))
        client = Groq(api_key=os.environ["GROQ_API_KEY"])
        extracted = _extract_blood_from_image(client, img)
    except Exception as e:
        logger.warning(f"Blood vision failed: {e}")
        extracted = ""
    entries, age = blood_test.parse_blood_text(extracted)
    if not entries:
        await update.message.reply_text(tx["blood_empty"])
        return BLOOD_VALUES
    await _send_blood_report(update.message, context, entries, age)
    return BLOOD_VALUES


async def blood_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS.get(lang, TEXTS["ar"])
    doc = update.message.document
    mime = (doc.mime_type or "").lower()
    fname = (doc.file_name or "").lower()
    try:
        if mime.startswith("image/") or fname.endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")):
            tg_file = await doc.get_file()
            raw = await tg_file.download_as_bytearray()
            img = _downscale_jpeg(bytes(raw))
            client = Groq(api_key=os.environ["GROQ_API_KEY"])
            extracted = _extract_blood_from_image(client, img)
        elif mime == "application/pdf" or fname.endswith(".pdf"):
            try:
                import fitz
                tg_file = await doc.get_file()
                raw = bytes(await tg_file.download_as_bytearray())
                pdf = fitz.open(stream=raw, filetype="pdf")
                pix = pdf[0].get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                img = _downscale_jpeg(pix.tobytes("png"))
                client = Groq(api_key=os.environ["GROQ_API_KEY"])
                extracted = _extract_blood_from_image(client, img)
            except Exception as pdf_err:
                logger.warning(f"Blood PDF failed: {pdf_err}")
                await update.message.reply_text(tx["blood_pdf_unsupported"])
                return BLOOD_VALUES
        else:
            await update.message.reply_text(tx["blood_file_unsupported"])
            return BLOOD_VALUES
    except Exception as e:
        logger.warning(f"Blood document failed: {e}")
        extracted = ""
    entries, age = blood_test.parse_blood_text(extracted)
    if not entries:
        await update.message.reply_text(tx["blood_empty"])
        return BLOOD_VALUES
    await _send_blood_report(update.message, context, entries, age)
    return BLOOD_VALUES


async def blood_restart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS.get(lang, TEXTS["ar"])
    await query.message.reply_text(tx["blood_ask_values"])
    return BLOOD_VALUES

async def voice_blood_gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS.get(lang, TEXTS["ar"])
    try:
        text = await _transcribe_voice(update, context)
    except Exception as e:
        logger.error(f"Voice blood gender failed: {e}")
        await update.message.reply_text(tx["voice_error"])
        return BLOOD_GENDER
    if not text:
        await update.message.reply_text(tx["voice_empty"])
        return BLOOD_GENDER
    await update.message.reply_text(f"🎤 \"{text}\"")
    t = text.lower()
    if any(w in t for w in ["ذكر", "ولد", "رجل", "male", "man", "boy"]):
        context.user_data["blood_gender"] = "m"
    elif any(w in t for w in ["انثى", "أنثى", "بنت", "امرأة", "female", "woman", "girl"]):
        context.user_data["blood_gender"] = "f"
    else:
        await update.message.reply_text(tx["blood_ask_gender"])
        return BLOOD_GENDER
    await update.message.reply_text(tx["blood_voice_gender_ask"])
    return BLOOD_VALUES

async def voice_blood_values(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS.get(lang, TEXTS["ar"])
    try:
        text = await _transcribe_voice(update, context)
    except Exception as e:
        logger.error(f"Voice blood values failed: {e}")
        await update.message.reply_text(tx["voice_error"])
        return BLOOD_VALUES
    if not text:
        await update.message.reply_text(tx["voice_empty"])
        return BLOOD_VALUES
    await update.message.reply_text(f"🎤 \"{text}\"")
    update.message._unfreeze()
    update.message.text = text
    return await blood_values(update, context)

async def _apply_lang(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str) -> int:
    context.user_data["lang"] = lang
    tx = TEXTS[lang]
    try:
        db.add_subscriber(update.effective_user.id, lang)
    except Exception as sub_err:
        logger.warning(f"Subscriber registration failed: {sub_err}")
    reply = update.callback_query.message if update.callback_query else update.message
    await reply.reply_text(tx["ask_age"], reply_markup=ReplyKeyboardRemove())
    return AGE

async def set_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = "ar" if query.data == "lang_ar" else "en"
    return await _apply_lang(update, context, lang)

async def voice_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS[lang]
    try:
        text = await _transcribe_voice(update, context, language=None)
    except Exception as e:
        logger.error(f"Voice lang transcription failed: {e}")
        await update.message.reply_text(tx["voice_error"])
        return LANG
    if not text:
        await update.message.reply_text(tx["voice_empty"])
        return LANG
    detected = "ar" if re.search(r"[\u0600-\u06FF]", text) else "en"
    await update.message.reply_text(
        f"🎤 \"{text}\"\n\n→ {'🇸🇦 العربية' if detected == 'ar' else '🇺🇸 English'}"
    )
    return await _apply_lang(update, context, detected)


def _flat_syms(tx):
    return [item for row in tx["quick_symptoms"] for item in row
            if not (item.startswith("✍️") or item.startswith("✅"))]


def _sex_buttons(tx):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(tx["male"], callback_data="sex_m"),
         InlineKeyboardButton(tx["female"], callback_data="sex_f")]
    ])


def _sym_buttons(tx):
    rows, i = [], 0
    for r in tx["quick_symptoms"]:
        brow = []
        for item in r:
            if item.startswith("✍️"):
                brow.append(InlineKeyboardButton(item, callback_data="sym_typing"))
            elif item.startswith("✅"):
                brow.append(InlineKeyboardButton(item, callback_data="sym_done"))
            else:
                brow.append(InlineKeyboardButton(item, callback_data=f"sym_{i}"))
                i += 1
        rows.append(brow)
    return InlineKeyboardMarkup(rows)


def _dur_buttons(tx):
    opts = [o for row in tx["duration_options"] for o in row]
    return InlineKeyboardMarkup([[InlineKeyboardButton(o, callback_data=f"dur_{i}")] for i, o in enumerate(opts)])


def _sev_buttons(tx):
    opts = [o for row in tx["severity_options"] for o in row]
    return InlineKeyboardMarkup([[InlineKeyboardButton(o, callback_data=f"sev_{i}")] for i, o in enumerate(opts)])


def _flat_conds(tx):
    return [item for row in tx["conditions_kb"] for item in row
            if not (item.startswith("✏️") or "type" in item.lower())]


def _cond_buttons(tx):
    rows, i = [], 0
    for r in tx["conditions_kb"]:
        brow = []
        for item in r:
            if item.startswith("✏️") or "type" in item.lower():
                brow.append(InlineKeyboardButton(item, callback_data="cond_typing"))
            else:
                brow.append(InlineKeyboardButton(item, callback_data=f"cond_{i}"))
                i += 1
        rows.append(brow)
    return InlineKeyboardMarkup(rows)


def _skip_button(tx, cb):
    return InlineKeyboardMarkup([[InlineKeyboardButton(tx["skip"], callback_data=cb)]])


async def _edit_remove_buttons(message):
    try:
        await message.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass


async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    m = re.search(r"\d+", text)
    if m:
        text = m.group()
    if not text.isdigit() or not (1 <= int(text) <= 120):
        await update.message.reply_text(t(context, "invalid_age"))
        return AGE
    context.user_data["age"] = int(text)
    tx = TEXTS[context.user_data.get("lang","ar")]
    gender_opts = "• " + tx["male"] + "\n• " + tx["female"]
    _SPEAK_OVERRIDE[update.effective_chat.id] = tx["ask_gender"] + "\n\n" + gender_opts
    await update.message.reply_text(
        tx["ask_gender"],
        reply_markup=_sex_buttons(tx)
    )
    return GENDER

async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    tx = TEXTS[context.user_data.get("lang","ar")]
    t_l = text.lower()
    is_male = tx["male"] in text or any(w in t_l for w in ("ذكر", "رجل", "رجال", "ولد", "male"))
    is_female = tx["female"] in text or any(w in t_l for w in ("أنثى", "انثى", "امرأة", "حريم", "بنت", "female"))
    if is_male:
        context.user_data["gender"] = tx["male"]
        context.user_data["sex"] = "male"
    elif is_female:
        context.user_data["gender"] = tx["female"]
        context.user_data["sex"] = "female"
    else:
        await update.message.reply_text(tx["invalid_gender"])
        return GENDER
    sym_opts = "\n".join("• " + item for row in tx["quick_symptoms"] for item in row)
    _SPEAK_OVERRIDE[update.effective_chat.id] = tx["ask_symptoms"] + "\n\n" + sym_opts
    await update.message.reply_text(
        tx["ask_symptoms"],
        reply_markup=_sym_buttons(tx)
    )
    return SYMPTOMS

async def get_symptoms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    tx = TEXTS[context.user_data.get("lang","ar")]
    if "✍️" in text or "ما لقيت" in text or "Not listed" in text or "أكتبه" in text:
        await update.message.reply_text(tx["symptom_typing_prompt"])
        return SYMPTOMS
    if "✅" in text or "Done" in text or "انتهيت" in text:
        if not context.user_data["symptoms"]:
            await update.message.reply_text(tx["add_symptom_first"])
            return SYMPTOMS
        dur_opts = "\n".join("• " + item for row in tx["duration_options"] for item in row)
        _SPEAK_OVERRIDE[update.effective_chat.id] = tx["ask_duration"] + "\n\n" + dur_opts
        await update.message.reply_text(
            tx["summary"].format(context.user_data['age'], context.user_data['gender'], ', '.join(context.user_data['symptoms'])) + "\n\n" + tx["ask_duration"],
            reply_markup=_dur_buttons(tx)
        )
        return DURATION
    clean = re.sub(r'[^\w\s\u0600-\u06FF]', '', text).strip()
    if clean and clean not in context.user_data["symptoms"] and len(context.user_data["symptoms"]) < 15:
        context.user_data["symptoms"].append(clean)
        await update.message.reply_text(tx["symptom_added"].format(len(context.user_data["symptoms"])))
    return SYMPTOMS

def _match_duration(text, tx):
    """Maps free-form speech/text to one of the duration option labels."""
    t = text.lower()
    num = None
    m = re.search(r"\d+", t)
    if m:
        num = int(m.group())
    opts = tx["duration_options"]
    if any(w in t for w in ("شهر", "شهور", "أشهر", "اشهر", "month", "months")):
        return opts[2][1]
    if any(w in t for w in ("أسبوع", "اسبوع", "أسابيع", "اسابيع", "week", "weeks")):
        if num and num >= 3:
            return opts[2][0]
        return opts[1][1]
    if any(w in t for w in ("يوم", "يومين", "أيام", "ايام", "day", "days")):
        if num and num >= 8:
            return opts[2][0]
        if num and num >= 4:
            return opts[1][0]
        return opts[0][1]
    if any(w in t for w in ("ساعة", "ساعات", "ساعه", "hour", "hours", "أمس", "امس", "yesterday")):
        return opts[0][0]
    return None


def _match_severity(text, lang):
    """Maps free-form speech/text to a severity number 1-5."""
    t = text.lower()
    m = re.search(r"\d+", t)
    if m and 1 <= int(m.group()) <= 5:
        return int(m.group())
    arabic_words = {"واحد": 1, "اثنين": 2, "اثنان": 2, "ثلاثة": 3, "ثلاث": 3,
                    "أربعة": 4, "أربع": 4, "اربع": 4, "خمسة": 5, "خمس": 5}
    for k, v in arabic_words.items():
        if k in t:
            return v
    if lang == "ar":
        if any(w in t for w in ("حرج", "خطير", "قصوى")):
            return 5
        if any(w in t for w in ("شديد", "شديدة", "قوي", "قوية")):
            return 4
        if any(w in t for w in ("متوسط", "متوسطة")):
            return 3
        if any(w in t for w in ("معتدل", "معتدلة")):
            return 2
        if any(w in t for w in ("خفيف", "خفيفة", "بسيط", "بسيطة", "طفيف")):
            return 1
    else:
        if any(w in t for w in ("critical", "extreme", "worst")):
            return 5
        if any(w in t for w in ("severe", "intense", "strong")):
            return 4
        if any(w in t for w in ("medium",)):
            return 3
        if any(w in t for w in ("moderate",)):
            return 2
        if any(w in t for w in ("mild", "light", "slight")):
            return 1
    return None


async def get_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tx = TEXTS[context.user_data.get("lang","ar")]
    valid = [opt for row in tx["duration_options"] for opt in row]
    text = update.message.text
    if text not in valid:
        mapped = _match_duration(text, tx)
        if not mapped:
            await update.message.reply_text(tx["invalid_choice"])
            return DURATION
        text = mapped
    context.user_data["duration"] = text
    sev_opts = "\n".join("• " + item for row in tx["severity_options"] for item in row)
    _SPEAK_OVERRIDE[update.effective_chat.id] = tx["ask_severity"] + "\n\n" + sev_opts
    await update.message.reply_text(
        tx["ask_severity"],
        reply_markup=_sev_buttons(tx)
    )
    return SEVERITY

async def get_severity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tx = TEXTS[context.user_data.get("lang","ar")]
    text = update.message.text
    if text not in tx["severity_map"]:
        mapped = _match_severity(text, context.user_data.get("lang","ar"))
        if not mapped:
            await update.message.reply_text(tx["invalid_choice"])
            return SEVERITY
        context.user_data["severity"] = mapped
        context.user_data["severity_label"] = tx["sev_labels"][mapped]
    else:
        context.user_data["severity"] = tx["severity_map"][text]
        context.user_data["severity_label"] = text
    await update.message.reply_text(
        tx["ask_conditions"],
        reply_markup=_cond_buttons(tx)
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
        reply_markup=_skip_button(tx, "notes_skip")
    )
    return NOTES

async def get_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tx = TEXTS[context.user_data.get("lang","ar")]
    context.user_data["notes"] = "" if tx["skip"].replace("⏭️ ","") in update.message.text else update.message.text.strip()
    await update.message.reply_text(
        tx["ask_medications"],
        reply_markup=_skip_button(tx, "meds_skip")
    )
    return MEDICATIONS

async def get_medications(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tx = TEXTS[context.user_data.get("lang","ar")]
    context.user_data["medications"] = "" if tx["skip"].replace("⏭️ ","") in update.message.text else update.message.text.strip()
    d = context.user_data
    await update.message.reply_text(
        tx["summary"].format(d.get('age'), d.get('gender'), ', '.join(d.get('symptoms',[]))) + "\n\n" + tx["analyzing"],
        reply_markup=ReplyKeyboardRemove()
    )
    return await analyze_symptoms(update, context)


async def analysis_inline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    tx = TEXTS[context.user_data.get("lang", "ar")]
    chat_id = query.message.chat_id
    msg = query.message

    if data.startswith("sex_"):
        context.user_data["gender"] = tx["male"] if data == "sex_m" else tx["female"]
        context.user_data["sex"] = "male" if data == "sex_m" else "female"
        await _edit_remove_buttons(msg)
        sym_opts = "\n".join("• " + item for row in tx["quick_symptoms"] for item in row)
        _SPEAK_OVERRIDE[chat_id] = tx["ask_symptoms"] + "\n\n" + sym_opts
        await msg.reply_text(tx["ask_symptoms"], reply_markup=_sym_buttons(tx))
        return SYMPTOMS

    if data.startswith("sym_"):
        if data == "sym_typing":
            await _edit_remove_buttons(msg)
            await msg.reply_text(tx["symptom_typing_prompt"], reply_markup=ReplyKeyboardRemove())
            return SYMPTOMS
        if data == "sym_done":
            if not context.user_data.get("symptoms"):
                await msg.reply_text(tx["add_symptom_first"])
                return SYMPTOMS
            await _edit_remove_buttons(msg)
            dur_opts = "\n".join("• " + item for row in tx["duration_options"] for item in row)
            _SPEAK_OVERRIDE[chat_id] = tx["ask_duration"] + "\n\n" + dur_opts
            await msg.reply_text(
                tx["summary"].format(context.user_data['age'], context.user_data['gender'], ', '.join(context.user_data['symptoms'])) + "\n\n" + tx["ask_duration"],
                reply_markup=_dur_buttons(tx)
            )
            return DURATION
        symptom = _flat_syms(tx)[int(data[4:])]
        if symptom not in context.user_data.get("symptoms", []) and len(context.user_data.get("symptoms", [])) < 15:
            context.user_data["symptoms"].append(symptom)
        await msg.reply_text(
            tx["symptom_added"].format(len(context.user_data.get("symptoms", []))),
            reply_markup=_sym_buttons(tx)
        )
        return SYMPTOMS

    if data.startswith("dur_"):
        opts = [o for row in tx["duration_options"] for o in row]
        context.user_data["duration"] = opts[int(data[4:])]
        await _edit_remove_buttons(msg)
        sev_opts = "\n".join("• " + item for row in tx["severity_options"] for item in row)
        _SPEAK_OVERRIDE[chat_id] = tx["ask_severity"] + "\n\n" + sev_opts
        await msg.reply_text(tx["ask_severity"], reply_markup=_sev_buttons(tx))
        return SEVERITY

    if data.startswith("sev_"):
        opts = [o for row in tx["severity_options"] for o in row]
        label = opts[int(data[4:])]
        context.user_data["severity"] = tx["severity_map"][label]
        context.user_data["severity_label"] = label
        await _edit_remove_buttons(msg)
        await msg.reply_text(tx["ask_conditions"], reply_markup=_cond_buttons(tx))
        return CONDITIONS

    if data.startswith("cond_"):
        if data == "cond_typing":
            await _edit_remove_buttons(msg)
            context.user_data["_wait"] = True
            await msg.reply_text(tx["write_manually"], reply_markup=ReplyKeyboardRemove())
            return CONDITIONS
        cond = _flat_conds(tx)[int(data[4:])]
        context.user_data["conditions"] = "" if ("لا يوجد" in cond or "No previous" in cond) else cond
        await _edit_remove_buttons(msg)
        await msg.reply_text(tx["ask_notes"], reply_markup=_skip_button(tx, "notes_skip"))
        return NOTES

    if data == "notes_skip":
        context.user_data["notes"] = ""
        await _edit_remove_buttons(msg)
        await msg.reply_text(tx["ask_medications"], reply_markup=_skip_button(tx, "meds_skip"))
        return MEDICATIONS

    if data == "meds_skip":
        context.user_data["medications"] = ""
        await _edit_remove_buttons(msg)
        d = context.user_data
        await msg.reply_text(
            tx["summary"].format(d.get('age'), d.get('gender'), ', '.join(d.get('symptoms', []))) + "\n\n" + tx["analyzing"],
            reply_markup=ReplyKeyboardRemove()
        )
        return await analyze_symptoms(update, context)
    return None


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


def _rule_urgency(symptoms, severity, age):
    """Rule-based safety net: certain symptom combinations always force high urgency."""
    en = set()
    for s in symptoms or []:
        s = s.strip().lower()
        mapped = ml_diagnosis.SYNONYMS.get(s)
        if mapped:
            en.add(mapped)
        elif s in ml_diagnosis.SYNONYMS.values():
            en.add(s)
    sev = int(severity or 1)
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


def _is_deteriorating(vals):
    """True when severity rose for two consecutive days (worsening trend)."""
    return len(vals) >= 3 and vals[-1] > vals[-2] >= vals[-3]


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
قواعد الموثوقية (إلزامية):
- اعتمد فقط على المعرفة الطبية من مصادر موثوقة: Mayo Clinic, NHS, WHO, CDC, MedlinePlus.
- لا تخترع أعراضاً أو أمراضاً. لو ما كنت متأكداً، قل "قد يكون" ولا تعطِ تشخيصاً قطعياً أبداً.
- هذا التحليل للتوعية فقط وليس تشخيصاً نهائياً، والمريض يجب أن يراجع الطبيب عند أي شك.
معلومات المريض:
- العمر: {d.get('age')} سنة، الجنس: {d.get('gender')}
- الأعراض: {', '.join(d.get('symptoms',[])[:6])}
- المدة: {d.get('duration')}، الشدة: {sev_label} ({d.get('severity')}/5)
- أمراض سابقة: {d.get('conditions') or 'لا يوجد'}
- الأدوية الحالية: {d.get('medications') or 'لا يوجد'}
- ملاحظات: {d.get('notes') or 'لا يوجد'}
{age_context}
{time_context}
ملاحظة مهمة عن الأدوية: لا تخبري المريض أبداً بإيقاف دواء موصوف من طبيب بشكل قطعي. لو ذكر أدوية، اعطي إرشاد عام حذر (زي: كمّلي حسب وصف الطبيب إلا لو تدهورت الأعراض، أو راجعي الصيدلي/الطبيب قبل أي تغيير). لو ما ذكر أدوية، اترك الحقل فارغ "".
اجب بـ JSON فقط. كل النصوص يجب أن تكون باللغة العربية فقط، ممنوع استخدام أي لغة أخرى:
{{"personal_note":"جملة أو جملتين متعاطفتين وشخصية تخاطب المريض مباشرة بناءً على حالته بالضبط (مو نص عام)","urgency":"low|medium|high","urgency_ar":"بسيط|يحتاج موعد طبيب|طوارئ","confidence":"high|medium|low","possible_conditions":"الاحتمالات بالعربية فقط (3 جمل، بدون تشخيص قطعي)","recommendations":[{{"tip":"نصيحة بالعربية","source":"اسم المصدر مثل Mayo Clinic","source_url":"رابط المصدر https://..."}},{{"tip":"نصيحة بالعربية","source":"اسم المصدر","source_url":"https://..."}},{{"tip":"نصيحة بالعربية","source":"اسم المصدر","source_url":"https://..."}},{{"tip":"نصيحة بالعربية","source":"اسم المصدر","source_url":"https://..."}}],"danger_signs":"علامات الخطر بالعربية فقط","when_to_seek_care":"متى تراجع الطبيب بالعربية فقط","home_care":"الرعاية المنزلية بالعربية فقط","medication_guidance":"إرشاد حذر عن الاستمرار بالدواء أو مراجعة الطبيب/الصيدلي، أو فارغ لو ما ذكر أدوية","questions_for_doctor":"3-4 أسئلة ذكية بالعربية يسألها المريض طبيبه بناءً على حالته"}}"""
    else:
        prompt = f"""You are a medical awareness assistant. Write your response in English ONLY. Do not use any other language.
Reliability rules (mandatory):
- Rely only on established medical knowledge from trusted sources: Mayo Clinic, NHS, WHO, CDC, MedlinePlus.
- Never invent symptoms or diseases. If uncertain, say "might be" and never give a definitive diagnosis.
- This is awareness only, not a final diagnosis; the patient should see a doctor if in doubt.
Patient information:
- Age: {d.get('age')}, Gender: {d.get('gender')}
- Symptoms: {', '.join(d.get('symptoms',[])[:6])}
- Duration: {d.get('duration')}, Severity: {sev_label} ({d.get('severity')}/5)
- Previous conditions: {d.get('conditions') or 'None'}
- Current medications: {d.get('medications') or 'None'}
- Notes: {d.get('notes') or 'None'}
{age_context}
{time_context}
Important note about medications: never tell the patient to stop a doctor-prescribed medication outright. If they mentioned medications, give cautious general guidance (e.g., continue as prescribed unless symptoms worsen, or consult a pharmacist/doctor before any change). If no medications were mentioned, leave the field as "".
Reply with JSON only. All text must be in English only:
{{"personal_note":"one or two empathetic, personalized sentences addressing the patient directly based on their specific situation (not generic)","urgency":"low|medium|high","urgency_text":"Simple|Needs appointment|Emergency","confidence":"high|medium|low","possible_conditions":"Possible conditions in English only (3 sentences, no definitive diagnosis)","recommendations":[{{"tip":"tip in English","source":"source name like Mayo Clinic","source_url":"https://..."}},{{"tip":"tip in English","source":"source name","source_url":"https://..."}},{{"tip":"tip in English","source":"source name","source_url":"https://..."}},{{"tip":"tip in English","source":"source name","source_url":"https://..."}}],"danger_signs":"Danger signs in English only","when_to_seek_care":"When to see a doctor in English only","home_care":"Home care tips in English only","medication_guidance":"cautious guidance about continuing medication or consulting a doctor/pharmacist, or empty if no medications mentioned","questions_for_doctor":"3-4 smart questions in English the patient should ask their doctor based on their case"}}"""

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
        recs_lines = []
        for i, r in enumerate(result.get("recommendations", [])):
            if isinstance(r, dict):
                tip_text = _md_safe(r.get("tip") or r.get("text") or "", lang)
                src = r.get("source") or ""
                url = r.get("source_url") or r.get("url") or ""
                recs_lines.append(f"  {i+1}. {tip_text}")
                if src and url:
                    recs_lines.append(f"     🔗 {_md_safe(src, lang)}: {url}")
            else:
                recs_lines.append(f"  {i+1}. {_md_safe(r, lang)}")
        recs = "\n".join(recs_lines)
        personal_note = _md_safe(result.get("personal_note", ""), lang)
        possible_conditions = _md_safe(result.get('possible_conditions',''), lang)
        home_care = _md_safe(result.get('home_care',''), lang)
        danger_signs = _md_safe(result.get('danger_signs',''), lang)
        when_to_seek_care = _md_safe(result.get('when_to_seek_care',''), lang)
        questions_for_doctor = _md_safe(result.get('questions_for_doctor',''), lang)

        # --- Rule-based safety net: red-flag combos always force high urgency ---
        rule_flag = False
        if _rule_urgency(d.get('symptoms', []), d.get('severity', 1), d.get('age')) == "high":
            result["urgency"] = "high"
            rule_flag = True
            icon = "🔴"
            urgency_text = "طوارئ" if lang == "ar" else "Emergency"
        low_conf = (result.get("confidence") or "medium").lower() == "low"

        sources_text = "\n".join(
            f"🔗 {name} — {url}" for name, url in tx["sources"]
        )

        # --- Cross-check against a real, trained ML classifier (Bernoulli Naive Bayes) ---
        infermedica_block = ""
        try:
            predicted = ml_diagnosis.predict_conditions(d.get('symptoms', []))
            if predicted:
                name_key = "name_ar" if lang == "ar" else "name_en"
                prob_word = "احتمال" if lang == "ar" else "probability"
                lines = [f"<i>{_html_escape(tx['infermedica_note'])}</i>", ""]
                for cond in predicted:
                    pct = round(cond["probability"] * 100)
                    name = _md_safe(cond[name_key], lang)
                    lines.append(f"<b>{name}</b>: {_bar(pct)} {pct}% {prob_word}")
                infermedica_block = "\n".join(lines)
        except Exception as inf_err:
            logger.warning(f"ML diagnosis prediction error: {inf_err}")

        # --- Check patient's free-text notes for recognized medications ---
        medication_block = ""
        try:
            med_matches = medication_warnings.check_medications(
                f"{d.get('medications', '')} {d.get('notes', '')}"
            )
            if med_matches:
                name_key = "name_ar" if lang == "ar" else "name_en"
                warn_key = "warning_ar" if lang == "ar" else "warning_en"
                lines = []
                for med in med_matches:
                    name = _md_safe(med[name_key], lang)
                    warning = _md_safe(med[warn_key], lang)
                    lines.append(f"<b>{name}</b>: {warning}")
                lines.append(f"<i>{_html_escape(tx['medication_disclaimer'])}</i>")
                medication_block = "\n".join(lines)
        except Exception as med_err:
            logger.warning(f"Medication check error: {med_err}")

        medication_guidance = _md_safe(result.get("medication_guidance", ""), lang)

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
        rec_id = None
        try:
            rec_id = db.save_record(
                user_id, lang, d.get('age'), d.get('gender'),
                d.get('symptoms', []), d.get('duration'),
                d.get('severity'), result.get('urgency', 'low'),
                d.get('conditions', ''), d.get('medications', ''),
            )
        except Exception as db_err:
            logger.error(f"DB save error: {db_err}")

        # --- Schedule a 48-hour follow-up check-in to track recovery ---
        if rec_id:
            context.user_data["_last_record_id"] = rec_id
        if rec_id and context.application.job_queue:
            try:
                context.application.job_queue.run_once(
                    send_followup_reminder,
                    when=timedelta(hours=48),
                    data={"chat_id": update.effective_chat.id, "record_id": rec_id, "lang": lang},
                )
            except Exception as fu_sched_err:
                logger.warning(f"Followup scheduling failed: {fu_sched_err}")

        msg = (
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>{_html_escape(tx['result_title'])}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"<i>{personal_note}</i>\n\n"
            f"{icon} <b>{_html_escape(tx['urgency_label'])}:</b> {urgency_text}\n\n"
            + (f"<b>{_html_escape(tx['rule_emergency_note'])}</b>\n\n" if rule_flag else "")
            + (f"<i>{_html_escape(tx['low_conf_note'])}</i>\n\n" if low_conf else "")
            + f"<b>{_html_escape(tx['conditions_label'])}</b>\n{possible_conditions}\n\n"
            + (f"<b>{_html_escape(tx['infermedica_label'])}</b>\n{infermedica_block}\n\n" if infermedica_block else "")
            + (f"<b>{_html_escape(tx['medication_label'])}</b>\n{medication_block}\n\n" if medication_block else "")
            + (f"<b>{_html_escape(tx['medication_guidance_label'])}</b>\n{medication_guidance}\n\n" if medication_guidance else "")
            + f"<b>{_html_escape(tx['recommendations_label'])}</b>\n{recs}\n\n"
            f"<b>{_html_escape(tx['home_care_label'])}</b>\n{home_care}\n\n"
            f"<b>{_html_escape(tx['danger_label'])}</b>\n{danger_signs}\n\n"
            f"<b>{_html_escape(tx['when_label'])}</b>\n{when_to_seek_care}\n\n"
            + (f"<b>{_html_escape(tx['doctor_q_label'])}</b>\n{questions_for_doctor}\n\n" if questions_for_doctor else "")
            + (f"<b>{_html_escape(tx['emergency_title'])}</b>\n{_html_escape(tx['emergency_block'])}\n\n" if result.get('urgency') == 'high' else "")
            + f"<b>{_html_escape(tx['memory_label'])}</b>\n{_md_safe(memory_block, lang)}\n\n"
            f"<b>{_html_escape(tx['sources_label'])}</b>\n{sources_text}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<i>{_html_escape(tx['disclaimer'])}</i>\n"
            f"{_html_escape(tx['signature'])}"
        )

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(tx["new_analysis"], callback_data="restart")],
            [InlineKeyboardButton(tx["home_share_btn"], url=_share_url(context))],
            [InlineKeyboardButton(tx["home_btn"], callback_data="home_menu")],
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

        # --- Shareable summary card image ---
        try:
            card = generate_result_image(d, result, predicted)
            await update.message.reply_photo(
                photo=card, caption="🏥 " + _html_escape(tx["result_title"])
            )
        except Exception as img_err:
            logger.warning(f"Result card send failed: {img_err}")

        # --- Shareable PDF report ---
        try:
            pdf_buf = generate_pdf_report(d, result, predicted, lang)
            if pdf_buf:
                await update.message.reply_document(
                    document=pdf_buf, filename="SymptoSense_report.pdf",
                    caption=_html_escape(tx["pdf_caption"])
                )
        except Exception as pdf_err:
            logger.warning(f"PDF report send failed: {pdf_err}")

        # --- Spoken voice summary (only when voice reply is enabled) ---
        try:
            spoken = " · ".join(filter(None, [
                f"{urgency_text}",
                f"{_tts_plain(tx['conditions_label'])}: {_tts_plain(possible_conditions)}",
                f"{_tts_plain(tx['recommendations_label'])}: {_tts_plain(recs)}",
            ]))
            await _send_voice_summary(update.message, context, spoken)
        except Exception as voice_err:
            logger.warning(f"Voice summary failed: {voice_err}")

        # --- Save context so follow-up questions can reference this exact case ---
        context.user_data["last_case_summary"] = (
            f"Age: {d.get('age')}, Gender: {d.get('gender')}, "
            f"Symptoms: {', '.join(d.get('symptoms', []))}, "
            f"Duration: {d.get('duration')}, Severity: {d.get('severity')}/5, "
            f"Urgency: {result.get('urgency')}, "
            f"Possible conditions: {result.get('possible_conditions','')}"
        )

        await update.message.reply_text(tx["followup_prompt"])

        # --- Quick satisfaction survey after each analysis ---
        try:
            fb_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(tx["feedback_opt_great"], callback_data="fb_great"),
                 InlineKeyboardButton(tx["feedback_opt_good"], callback_data="fb_good")],
                [InlineKeyboardButton(tx["feedback_opt_ok"], callback_data="fb_ok"),
                 InlineKeyboardButton(tx["feedback_opt_bad"], callback_data="fb_bad")],
            ])
            await update.message.reply_text(tx["feedback_title"], reply_markup=fb_kb)
        except Exception as fb_err:
            logger.warning(f"Feedback prompt failed: {fb_err}")

        if result.get("urgency") == "high":
            loc_kb = ReplyKeyboardMarkup(
                [[KeyboardButton(tx["share_location_button"], request_location=True)]],
                resize_keyboard=True, one_time_keyboard=True,
            )
            await update.message.reply_text(tx["share_location_prompt"], reply_markup=loc_kb)

    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(t(context, "error"))
        return ConversationHandler.END
    return FOLLOWUP

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS[lang]
    loc = update.message.location
    await update.message.reply_text(tx["hospitals_title"], reply_markup=ReplyKeyboardRemove())
    try:
        hospitals = geo_hospitals.find_nearby_hospitals(loc.latitude, loc.longitude)
        if not hospitals:
            await update.message.reply_text(tx["hospitals_none"] + tx["hospitals_footer"])
        else:
            lines = []
            for h in hospitals:
                dist_word = "كم" if lang == "ar" else "km"
                lines.append(f"🏥 <b>{_html_escape(h['name'])}</b> — {h['distance_km']} {dist_word}\n{h['maps_url']}")
            await update.message.reply_text(
                "\n\n".join(lines) + tx["hospitals_footer"], parse_mode="HTML", disable_web_page_preview=True
            )
    except Exception as e:
        logger.error(f"Hospital search error: {e}")
        await update.message.reply_text(tx["hospitals_none"] + tx["hospitals_footer"])
    return FOLLOWUP


async def _transcribe_voice(update: Update, context: ContextTypes.DEFAULT_TYPE, language: str = "default") -> str:
    """Downloads a Telegram voice note and transcribes it via Groq's Whisper API.
    Pass language="default" (or nothing) to use the user's UI language, or None for auto-detect."""
    voice = update.message.voice
    tg_file = await context.bot.get_file(voice.file_id)
    file_bytes = await tg_file.download_as_bytearray()
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    if language == "default":
        language = context.user_data.get("lang", "ar")
    kwargs = {}
    if language:
        kwargs["language"] = language
    transcription = client.audio.transcriptions.create(
        file=("voice.ogg", bytes(file_bytes)),
        model="whisper-large-v3",
        **kwargs,
    )
    return transcription.text.strip()

_EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FAFF"
    "\U00002702-\U000027B0"
    "\U00002600-\U000026FF"
    "\U0000FE0F"
    "\U0000200D"
    "\U0000E000-\U0000F8FF"
    "\U0001F000-\U0001F0FF"
    "]+",
    re.UNICODE,
)

def _tts_plain(text: str, lang: str) -> str:
    """Strips HTML tags/entities, emojis and decorative symbols so spoken text stays clean."""
    plain = re.sub(r"<[^>]+>", "", text)
    plain = plain.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
    plain = _EMOJI_RE.sub(" ", plain)
    plain = re.sub(r"[•·▪■□➤▶◀★☆✦✧✚✖✓✔⏭]+", " ", plain)
    plain = re.sub(r"\s+", " ", plain)
    return plain.strip()

async def _text_to_speech(text: str, lang: str) -> bytes:
    """Synthesizes speech via edge-tts (natural Arabic voices), falling back to gTTS."""
    text = _tts_plain(text, lang)[:1200]
    if not text:
        return b""
    try:
        import edge_tts
        voice = "ar-SA-ZariyahNeural" if lang == "ar" else "en-US-AriaNeural"
        buffer = b""
        async for chunk in edge_tts.Communicate(text, voice).stream():
            if chunk["type"] == "audio":
                buffer += chunk["data"]
        if buffer:
            return buffer
    except Exception as tts_err:
        logger.warning(f"edge-tts failed: {tts_err}")
    try:
        from gtts import gTTS
        buf = io.BytesIO()
        gTTS(text=text, lang="ar" if lang == "ar" else "en").write_to_fp(buf)
        return buf.getvalue()
    except Exception as tts2_err:
        logger.warning(f"gTTS failed: {tts2_err}")
    return b""

async def _send_voice_summary(message, context, text: str):
    """Sends a spoken summary voice note when voice reply is enabled."""
    if not context.user_data.get("voice_on"):
        return
    try:
        lang = context.user_data.get("lang", "ar")
        audio = await _text_to_speech(text, lang)
        if audio:
            await message.reply_voice(voice=io.BytesIO(audio), filename="symptosense_voice.ogg")
    except Exception as vo_err:
        logger.warning(f"Voice summary failed: {vo_err}")

# ---------------------------------------------------------------------------
# 🔊 Global "Read it aloud" button on every text message (accessibility)
# ---------------------------------------------------------------------------
_SPEAK_POOL = {}
_SPEAK_COUNTER = {}
_SPEAK_OVERRIDE = {}

async def speak_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS[lang]
    try:
        idx = int(query.data.split("_", 1)[1])
        text = _SPEAK_POOL.get(query.message.chat_id, {}).get(idx, "")
    except Exception:
        text = ""
    if not text:
        await query.message.reply_text(tx["speak_expired"])
        return
    audio = await _text_to_speech(text, lang)
    if audio:
        await query.message.reply_voice(voice=io.BytesIO(audio), filename="read_aloud.ogg")
    else:
        await query.message.reply_text(tx["speak_fail"])

async def _attach_speak_button(chat_id, text, reply_markup):
    """Registers the message text for the speak button and returns merged markup."""
    idx = _SPEAK_COUNTER.get(chat_id, 0) + 1
    _SPEAK_COUNTER[chat_id] = idx
    _SPEAK_POOL.setdefault(chat_id, {})[idx] = text
    if len(_SPEAK_POOL[chat_id]) > 20:
        oldest = next(iter(_SPEAK_POOL[chat_id]))
        _SPEAK_POOL[chat_id].pop(oldest, None)
    is_ar = bool(re.search(r"[\u0600-\u06FF]", text))
    label = "🔊 اقرأ لي" if is_ar else "🔊 Read it"
    btn = InlineKeyboardButton(label, callback_data=f"speak_{idx}")
    if reply_markup is None or isinstance(reply_markup, ReplyKeyboardRemove):
        return InlineKeyboardMarkup([[btn]])
    if isinstance(reply_markup, InlineKeyboardMarkup):
        return InlineKeyboardMarkup(list(reply_markup.inline_keyboard) + [[btn]])
    return reply_markup

_ORIG_SEND_MESSAGE = None

async def _patched_send_message(self, chat_id, text=None, reply_markup=None, **kwargs):
    if _ORIG_SEND_MESSAGE is None:
        raise RuntimeError("speak patch not initialised")
    if isinstance(text, str) and text:
        try:
            override = _SPEAK_OVERRIDE.pop(chat_id, None)
            reply_markup = await _attach_speak_button(chat_id, override or text, reply_markup)
        except Exception as sp_err:
            logger.warning(f"Speak button attach failed: {sp_err}")
    return await _ORIG_SEND_MESSAGE(self, chat_id, text=text, reply_markup=reply_markup, **kwargs)

def _install_speak_patch():
    global _ORIG_SEND_MESSAGE
    from telegram import Bot
    if _ORIG_SEND_MESSAGE is None:
        _ORIG_SEND_MESSAGE = Bot.send_message
        Bot.send_message = _patched_send_message
        logger.info("🔊 Speak button patched onto every text message.")

# ---------------------------------------------------------------------------
# 🎙️ Global voice fallback for home flows (med reminders, drug lookup, ...)
# ---------------------------------------------------------------------------
async def voice_tool(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles voice at home: answers home-flow questions OR routes main-menu commands."""
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS.get(lang, TEXTS["ar"])
    if context.user_data.get("_await"):
        try:
            text = await _transcribe_voice(update, context)
        except Exception as e:
            logger.error(f"Voice tool transcription failed: {e}")
            return
        if not text:
            return
        await update.message.reply_text(f"🎤 \"{text}\"")
        update.message._unfreeze()
        update.message.text = text
        try:
            await handle_tool_text(update, context)
        except Exception as e:
            logger.error(f"Voice tool handling failed: {e}")
        return

    # --- Main-menu voice commands ---
    try:
        text = await _transcribe_voice(update, context)
    except Exception as e:
        logger.error(f"Voice home command transcription failed: {e}")
        await update.message.reply_text(tx["voice_error"])
        return
    if not text:
        await update.message.reply_text(tx["voice_empty"])
        return
    await update.message.reply_text(f"🎤 \"{text}\"")
    t = text.lower()
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    msg = update.message

    def reset():
        return _reset_conv_core(chat_id, user_id, context)

    if any(w in t for w in ("ابدأ تحليل", "تحليل جديد", "ابغى تحليل", "ابي تحليل", "أبي تحليل", "أبدأ", "ابدا", "ابدء", "start", "تحليل الأعراض")):
        await reset()
        await _home_action_start(msg, context, user_id)
        await _set_conv_state(chat_id, user_id, context, LANG)
    elif any(w in t for w in ("تحليل دم", "فحص دم", "blood test", "blood")):
        await reset()
        await _home_action_blood(msg, context)
        await _set_conv_state(chat_id, user_id, context, BLOOD_GENDER)
    elif any(w in t for w in ("نصائح", "نصيحة", "tip")):
        await reset()
        await _home_action_tips(msg, context)
    elif any(w in t for w in ("متابعة", "حالتي", "تطمني", "تطم", "follow")):
        await reset()
        await _home_action_followup(msg, context, user_id)
    elif any(w in t for w in ("إسعاف", "اسعاف", "first aid")):
        await reset()
        await _home_action_firstaid(msg, context)
    elif any(w in t for w in ("استرخاء", "استراحة", "راحة", "relax")):
        await reset()
        await _home_action_relax(msg, context)
    elif any(w in t for w in ("تذكير دوائي", "تذكيري", "دوائي", "تذكير الدواء", "med reminder", "medication")):
        await reset()
        await _home_action_meds(msg, context)
    elif any(w in t for w in ("بحث عن دواء", "دواء", "drug", "تفاعل دواء")):
        await reset()
        await _home_action_drug(msg, context)
    elif any(w in t for w in ("طوارئ", "طواري", "emergency")):
        await reset()
        await _home_action_emergency(msg, context)
    elif any(w in t for w in ("رد صوتي", "الصوت", "صوتي", "voice")):
        await _home_action_voice_toggle(msg, context)
    else:
        await update.message.reply_text(tx["voice_home_unknown"])

async def _voice_to_text_step(update: Update, context: ContextTypes.DEFAULT_TYPE, next_handler):
    """Transcribes a voice note, echoes it back for confirmation, then feeds the
    transcribed text into the same handler used for typed messages at this step."""
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS[lang]
    try:
        text = await _transcribe_voice(update, context)
        if not text:
            await update.message.reply_text(tx["voice_empty"])
            return None
        await update.message.reply_text(f"🎤 \"{text}\"")
    except Exception as e:
        logger.error(f"Voice transcription failed: {e}")
        await update.message.reply_text(tx["voice_error"])
        return None
    update.message._unfreeze()
    update.message.text = text
    return await next_handler(update, context)

_SYMPTOM_KEYWORDS_AR = ["صداع","حمى","سعال","ألم في الصدر","غثيان","تعب وإرهاق","ضيق التنفس","دوار","ألم المفاصل","ألم في البطن","قشعريرة","احمرار العيون"]
_SYMPTOM_KEYWORDS_EN = ["headache","fever","cough","chest pain","nausea","fatigue","shortness of breath","dizziness","joint pain","stomach pain","chills","red eyes"]

def _extract_symptoms_from_text(text: str, lang: str):
    keywords = _SYMPTOM_KEYWORDS_AR if lang == "ar" else _SYMPTOM_KEYWORDS_EN
    text_l = text.lower()
    return [kw for kw in keywords if kw.lower() in text_l]

async def voice_symptoms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS[lang]
    try:
        text = await _transcribe_voice(update, context)
        if not text:
            await update.message.reply_text(tx["voice_empty"])
            return SYMPTOMS
        await update.message.reply_text(f"🎤 \"{text}\"")
    except Exception as e:
        logger.error(f"Voice transcription failed: {e}")
        await update.message.reply_text(tx["voice_error"])
        return SYMPTOMS

    found = _extract_symptoms_from_text(text, lang)
    added = []
    for f in found:
        if f not in context.user_data["symptoms"] and len(context.user_data["symptoms"]) < 15:
            context.user_data["symptoms"].append(f)
            added.append(f)

    if added:
        await update.message.reply_text(tx["voice_symptoms_detected"].format(", ".join(added), len(context.user_data["symptoms"])))
    else:
        clean = re.sub(r'[^\w\s\u0600-\u06FF]', '', text).strip()
        if clean and clean not in context.user_data["symptoms"] and len(context.user_data["symptoms"]) < 15:
            context.user_data["symptoms"].append(clean)
            await update.message.reply_text(tx["symptom_added"].format(len(context.user_data["symptoms"])))
    return SYMPTOMS

async def voice_conditions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _voice_to_text_step(update, context, get_conditions) or CONDITIONS

async def voice_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _voice_to_text_step(update, context, get_notes) or NOTES

async def voice_medications(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _voice_to_text_step(update, context, get_medications) or MEDICATIONS

async def voice_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _voice_to_text_step(update, context, get_age) or AGE

async def voice_gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _voice_to_text_step(update, context, get_gender) or GENDER

async def voice_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _voice_to_text_step(update, context, get_duration) or DURATION

async def voice_severity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _voice_to_text_step(update, context, get_severity) or SEVERITY

async def voice_followup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _voice_to_text_step(update, context, handle_followup) or FOLLOWUP


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
    return await _home_action_start(update.callback_query.message, context, update.effective_user.id)

def generate_result_image(d, result, ml_predictions):
    """Renders a shareable summary card as a PNG (structured content in English
    so it renders correctly on any matplotlib font; works for both bot languages)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    syms = [SYMPTOM_EN.get(s, s) for s in d.get("symptoms", [])]
    urgency = result.get("urgency", "low")
    urg_label = {"low": "Low", "medium": "Medium", "high": "Emergency"}.get(urgency, "Low")
    date_str = datetime.now(timezone.utc).strftime("%d %b %Y")

    lines = ["Sympto·Sense", ""]
    lines.append("Symptom summary")
    lines.append(f"Date: {date_str}")
    lines.append("")
    lines.append("Symptoms: " + ", ".join(syms[:8]) if syms else "None reported")
    lines.append(f"Severity: {d.get('severity')}/5")
    lines.append(f"Urgency: {urg_label}")
    lines.append("")
    if ml_predictions:
        lines.append("Likely conditions (ML):")
        for row in ml_predictions[:3]:
            lines.append(f"  • {row['name_en']}: {round(row['probability'] * 100)}%")
        lines.append("")
    lines.append("For awareness only — not a medical diagnosis.")
    lines.append("Consult a doctor if symptoms persist.")

    text = "\n".join(lines)
    fig = plt.figure(figsize=(8, 5.5), facecolor="#0b3d5c")
    fig.text(0.06, 0.94, text, va="top", ha="left", fontsize=13,
             family="DejaVu Sans", color="#ffffff", linespacing=1.6,
             wrap=True)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf


def _pdf_font_path():
    base = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base, "fonts", "NotoSansArabic-Regular.ttf"),
        os.path.join(base, "NotoSansArabic-Regular.ttf"),
        r"C:\Windows\Fonts\Tahoma.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def _ar_shape(text):
    if not text:
        return ""
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(str(text)))
    except Exception:
        return str(text)


def _pdf_wrap(text, font, size, max_w):
    from reportlab.pdfbase import pdfmetrics
    words = str(text).split()
    lines, cur = [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if pdfmetrics.stringWidth(t, font, size) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def generate_pdf_report(d, result, ml_predictions, lang="ar"):
    """Builds a shareable PDF report (Arabic-shaped, Noto Sans Arabic font).
    Returns a BytesIO or None if the font/reportlab is unavailable."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font_path = _pdf_font_path()
    if not font_path:
        return None
    try:
        pdfmetrics.registerFont(TTFont("ArFont", font_path))
    except Exception:
        return None

    tx = TEXTS.get(lang, TEXTS["ar"])
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    M = 45
    max_w = W - 2 * M
    y = H - 55
    font = "ArFont"
    HEAD = (0.043, 0.239, 0.361)

    def emit(text, size=11, color=(0, 0, 0), space=17, gap=3):
        nonlocal y
        c.setFillColorRGB(*color)
        c.setFont(font, size)
        for ln in _pdf_wrap(_ar_shape(text), font, size, max_w):
            if y < 55:
                c.showPage()
                y = H - 55
            c.drawString(M, y, ln)
            y -= space
        y -= gap

    def section(title, body):
        emit("▪ " + title, 12, color=HEAD, space=20)
        if body:
            emit(body, 11)

    emit("SymptoSense", 20, color=HEAD, space=26)
    emit(datetime.now(timezone.utc).strftime("%d %b %Y"), 9, color=(0.4, 0.4, 0.4), space=18)

    urgency = result.get("urgency", "low")
    urg_ar = {"low": "بسيط", "medium": "يحتاج موعد طبيب", "high": "طوارئ"}.get(urgency, "بسيط")
    if lang == "en":
        urg_ar = {"low": "Low", "medium": "Needs appointment", "high": "Emergency"}.get(urgency, "Low")

    syms = "، ".join(d.get("symptoms", [])) if lang == "ar" else ", ".join(SYMPTOM_EN.get(s, s) for s in d.get("symptoms", []))
    emit(tx["urgency_label"] + ": " + urg_ar, 12, color=(0.8, 0, 0) if urgency == "high" else (0, 0, 0))
    emit(tx["conditions_label"] + ": " + (result.get("possible_conditions") or "-"), 11)
    emit("الأعراض: " + syms if lang == "ar" else "Symptoms: " + syms, 11)
    emit("الشدة: " + str(d.get("severity")) + "/5" if lang == "ar" else "Severity: " + str(d.get("severity")) + "/5", 11)
    if ml_predictions:
        emit("احتمالات التشخيص (ذكاء اصطناعي):" if lang == "ar" else "Likely conditions (ML):", 11, color=HEAD, space=18)
        for row in ml_predictions[:3]:
            emit("• " + row["name_en"] + ": " + str(round(row["probability"] * 100)) + "%", 11)

    recs = result.get("recommendations", [])
    if recs:
        section(tx["recommendations_label"], "")
        for i, r in enumerate(recs, 1):
            if isinstance(r, dict):
                tip = r.get("tip") or r.get("text") or ""
                src = r.get("source") or ""
                url = r.get("source_url") or r.get("url") or ""
                line = f"{i}. {tip}"
                if src and url:
                    line += f"  [{src}: {url}]"
                emit(line, 11)
            else:
                emit(f"{i}. {r}", 11)
    if result.get("home_care"):
        section(tx["home_care_label"], result["home_care"])
    if result.get("danger_signs"):
        section(tx["danger_label"], result["danger_signs"])
    if result.get("when_to_seek_care"):
        section(tx["when_label"], result["when_to_seek_care"])
    if result.get("questions_for_doctor"):
        section(tx["doctor_q_label"], result["questions_for_doctor"])
    if result.get("medication_guidance"):
        section(tx["medication_guidance_label"], result["medication_guidance"])
    if urgency == "high":
        section(tx["emergency_title"], tx["emergency_block"])
    emit(tx["disclaimer"], 8, color=(0.4, 0.4, 0.4), space=14)
    emit(tx["signature"], 8, color=(0.4, 0.4, 0.4), space=14)

    c.save()
    buf.seek(0)
    return buf


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

async def firstaid_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS[lang]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=f"fa_{key}")]
        for key, (label, _) in wellbeing.first_aid_categories(lang)
    ])
    await update.message.reply_text(tx["firstaid_choose"], reply_markup=kb)

async def firstaid_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS[lang]
    key = query.data.split("_", 1)[1]
    _, text = wellbeing.first_aid_text(key, lang)
    await query.message.reply_text(text + tx["firstaid_footer"])

async def relax_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS[lang]
    await update.message.reply_text(tx["relax_title"] + "\n\n" + wellbeing.relax_guide(lang))

async def season_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS[lang]
    code, label, tips = health_tips.get_season(lang)
    lines = [f"{tx['season_title']} — {label}", ""] + tips
    await update.message.reply_text("\n\n".join(lines))

async def send_followup_reminder(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    chat_id = data["chat_id"]
    record_id = data["record_id"]
    lang = data.get("lang", "ar")
    tx = TEXTS.get(lang, TEXTS["ar"])
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(tx["fu_improved_btn"], callback_data=f"fu_improved_{record_id}")],
        [InlineKeyboardButton(tx["fu_same_btn"], callback_data=f"fu_same_{record_id}")],
        [InlineKeyboardButton(tx["fu_worse_btn"], callback_data=f"fu_worse_{record_id}")],
    ])
    await context.bot.send_message(chat_id=chat_id, text=tx["fu_prompt"], reply_markup=kb)

async def followup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data  # e.g. fu_improved_123
    parts = data.split("_")
    outcome = parts[1] if len(parts) > 1 else "same"
    record_id = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS.get(lang, TEXTS["ar"])
    try:
        db.save_followup(update.effective_user.id, record_id, outcome)
    except Exception as fu_err:
        logger.warning(f"Followup save failed: {fu_err}")
    await query.message.reply_text(tx.get("fu_thanks_" + outcome, ""))

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

async def csv_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("🔒 هذا الأمر للمشرف فقط | Admin only command")
        return
    csv_str = db.export_all_records_csv()
    csv_buf = io.BytesIO(csv_str.encode("utf-8-sig"))
    filename = f"symptosense_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    await update.message.reply_document(
        document=csv_buf, filename=filename,
        caption="📦 تصدير كامل للبيانات المجهولة الهوية (CSV) — جاهز لـ Power BI"
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(t(context, "cancelled"), reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "SymptoSense 🏥\n\n/menu أو /start - الرئيسية | Home menu\n/trends - اتجاهات المجتمع | Community trends\n/firstaid - إسعاف أولي | First aid\n/relax - تمارين استرخاء وتنفس | Relaxation & breathing\n/season - نصائح الموسم | Seasonal tips\n/stop - إيقاف النصائح اليومية | Stop daily tips\n/cancel - إلغاء | Cancel\n/export - ملف Excel (مشرف) | Excel export (admin)\n/csv - ملف CSV (مشرف) | CSV export (admin)\n/help - مساعدة | Help\n\nللتوعية فقط | For awareness only"
    )

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ar")
    tx = TEXTS[lang]
    try:
        db.unsubscribe(update.effective_user.id)
    except Exception as e:
        logger.warning(f"Unsubscribe failed: {e}")
    await update.message.reply_text(tx["unsubscribed"])

async def send_daily_tip(context: ContextTypes.DEFAULT_TYPE):
    try:
        subscribers = db.get_subscribers()
    except Exception as e:
        logger.error(f"Could not load subscribers for daily tip: {e}")
        return
    for user_id, lang in subscribers:
        tx = TEXTS.get(lang, TEXTS["ar"])
        tip = health_tips.get_random_tip(lang)
        text = f"{tx['daily_tip_header']}\n\n{tip}{tx['daily_tip_footer']}"
        try:
            await context.bot.send_message(chat_id=user_id, text=text)
        except Exception as send_err:
            logger.warning(f"Daily tip send failed for {user_id}: {send_err}")

async def _post_init(app):
    try:
        me = await app.bot.get_me()
        app.bot_data["username"] = me.username
    except Exception as e:
        logger.warning(f"Could not fetch bot username: {e}")

def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token: raise ValueError("TELEGRAM_BOT_TOKEN missing")
    if not os.environ.get("GROQ_API_KEY"): raise ValueError("GROQ_API_KEY missing")

    _install_speak_patch()

    app = (
        Application.builder()
        .token(token)
        .post_init(_post_init)
        .persistence(DBUserDataPersistence())
        .build()
    )
    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(restart_callback, pattern="^(home_start|restart)$"),
            CallbackQueryHandler(home_blood, pattern="^home_blood$"),
        ],
        states={
            LANG:[
                CallbackQueryHandler(set_lang, pattern="^lang_"),
                MessageHandler(filters.VOICE, voice_lang),
            ],
            BLOOD_GENDER:[
                CallbackQueryHandler(blood_gender_callback, pattern="^bg_(m|f)$"),
                MessageHandler(filters.VOICE, voice_blood_gender),
            ],
            BLOOD_VALUES:[
                CallbackQueryHandler(blood_restart_callback, pattern="^blood_restart$"),
                MessageHandler(filters.PHOTO, blood_photo),
                MessageHandler(filters.Document.ALL, blood_document),
                MessageHandler(filters.VOICE, voice_blood_values),
                MessageHandler(filters.TEXT & ~filters.COMMAND, blood_values),
            ],
            AGE:[
                MessageHandler(filters.VOICE, voice_age),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_age),
            ],
            GENDER:[
                CallbackQueryHandler(analysis_inline, pattern="^(sex_|sym_|dur_|sev_|cond_|notes_skip|meds_skip)"),
                MessageHandler(filters.VOICE, voice_gender),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_gender),
            ],
            SYMPTOMS:[
                CallbackQueryHandler(analysis_inline, pattern="^(sex_|sym_|dur_|sev_|cond_|notes_skip|meds_skip)"),
                MessageHandler(filters.VOICE, voice_symptoms),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_symptoms),
            ],
            DURATION:[
                CallbackQueryHandler(analysis_inline, pattern="^(sex_|sym_|dur_|sev_|cond_|notes_skip|meds_skip)"),
                MessageHandler(filters.VOICE, voice_duration),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_duration),
            ],
            SEVERITY:[
                CallbackQueryHandler(analysis_inline, pattern="^(sex_|sym_|dur_|sev_|cond_|notes_skip|meds_skip)"),
                MessageHandler(filters.VOICE, voice_severity),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_severity),
            ],
            CONDITIONS:[
                CallbackQueryHandler(analysis_inline, pattern="^(sex_|sym_|dur_|sev_|cond_|notes_skip|meds_skip)"),
                MessageHandler(filters.VOICE, voice_conditions),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_conditions),
            ],
            NOTES:[
                CallbackQueryHandler(analysis_inline, pattern="^(sex_|sym_|dur_|sev_|cond_|notes_skip|meds_skip)"),
                MessageHandler(filters.VOICE, voice_notes),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_notes),
            ],
            MEDICATIONS:[
                CallbackQueryHandler(analysis_inline, pattern="^(sex_|sym_|dur_|sev_|cond_|notes_skip|meds_skip)"),
                MessageHandler(filters.VOICE, voice_medications),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_medications),
            ],
            FOLLOWUP:[
                MessageHandler(filters.LOCATION, handle_location),
                MessageHandler(filters.VOICE, voice_followup),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup),
                CallbackQueryHandler(restart_callback, pattern="^restart$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", start))
    app.add_handler(CallbackQueryHandler(home_menu, pattern="^home_menu$"))
    app.add_handler(CallbackQueryHandler(home_tips, pattern="^home_tips$"))
    app.add_handler(CallbackQueryHandler(tips_today, pattern="^tips_today$"))
    app.add_handler(CallbackQueryHandler(tips_season, pattern="^tips_season$"))
    app.add_handler(CallbackQueryHandler(home_followup, pattern="^home_followup$"))
    app.add_handler(CallbackQueryHandler(home_firstaid, pattern="^home_firstaid$"))
    app.add_handler(CallbackQueryHandler(home_relax, pattern="^home_relax$"))
    app.add_handler(CallbackQueryHandler(home_emergency, pattern="^home_emergency$"))
    app.add_handler(CallbackQueryHandler(home_voice_toggle, pattern="^home_voice_toggle$"))
    app.add_handler(CallbackQueryHandler(home_meds, pattern="^home_meds$"))
    app.add_handler(CallbackQueryHandler(home_drug, pattern="^home_drug$"))
    app.add_handler(CallbackQueryHandler(feedback_callback, pattern="^fb_"))
    app.add_handler(MessageHandler(filters.VOICE, voice_tool))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_tool_text))
    app.add_handler(CallbackQueryHandler(speak_callback, pattern="^speak_"), group=1)
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("trends", trends_cmd))
    app.add_handler(CallbackQueryHandler(trends_callback, pattern="^trends$"))
    app.add_handler(CommandHandler("firstaid", firstaid_cmd))
    app.add_handler(CallbackQueryHandler(firstaid_callback, pattern="^fa_"))
    app.add_handler(CommandHandler("relax", relax_cmd))
    app.add_handler(CommandHandler("season", season_cmd))
    app.add_handler(CallbackQueryHandler(followup_callback, pattern="^fu_"))
    app.add_handler(CallbackQueryHandler(med_recover_callback, pattern="^med_"))
    app.add_handler(CallbackQueryHandler(checkin_callback, pattern="^ci_"))
    app.add_handler(CommandHandler("progress", progress_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("export", export_cmd))
    app.add_handler(CommandHandler("csv", csv_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    db.init_db()
    logger.info(f"DB backend active: {'PostgreSQL' if db.USE_POSTGRES else 'SQLite (DATABASE_URL missing or empty)'}")

    if app.job_queue:
        # 07:00 UTC = 10:00 AM Saudi Arabia time
        app.job_queue.run_daily(send_daily_tip, time=dt_time(hour=7, minute=0, tzinfo=timezone.utc))
        # Reschedule medication reminders: daily at 00:05 UTC + right after startup
        app.job_queue.run_daily(_reschedule_meds, time=dt_time(hour=0, minute=5, tzinfo=timezone.utc))
        app.job_queue.run_once(_reschedule_meds, when=timedelta(seconds=5))
        # 19:00 UTC = 22:00 Saudi Arabia time — daily check-in for recovery tracking
        app.job_queue.run_daily(send_daily_checkin, time=dt_time(hour=19, minute=0, tzinfo=timezone.utc))
    else:
        logger.warning("JobQueue not available — daily tips disabled. Install python-telegram-bot[job-queue].")

    if os.environ.get("START_DASHBOARD_IN_BOT", "1") == "1":
        try:
            import dashboard
            threading.Thread(target=dashboard.run_dashboard, daemon=True).start()
            logger.info("Dashboard started in background thread.")
        except Exception as dash_err:
            logger.warning(f"Dashboard failed to start (bot will continue normally): {dash_err}")

    logger.info("SymptoSense يعمل...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
