import random
from datetime import datetime

TIPS = {
    "ar": [
        "💧 احرص على شرب كمية كافية من الماء اليوم، خصوصًا في الجو الحار — الجفاف قد يسبب صداعًا وتعبًا.",
        "😴 حاول الحصول على 7-8 ساعات من النوم. قلة النوم قد تزيد التعب والتوتر.",
        "🚶 عشر دقائق من المشي الخفيف قد تساعد على تحسين المزاج والدورة الدموية.",
        "📱 قلل وقت الشاشة قبل النوم بساعة للمساعدة على نوم أفضل.",
        "🥗 حاول إضافة خضار أو فاكهة إلى الوجبة القادمة.",
        "🧴 عند جفاف العين بسبب الشاشة، يُنصح باستراحة كل 20 دقيقة وفق قاعدة 20-20-20.",
        "🫁 ثلاث مرات من التنفس العميق والهادئ قد تساعد على خفض التوتر.",
        "☀️ التعرض المعتدل لضوء النهار قد يساعد على دعم المزاج والنوم.",
        "🧂 عند وجود انتفاخ أو صداع متكرر، قد يفيد تقليل الملح الزائد ومراجعة مختص إذا استمرت الأعراض.",
        "🩺 عند استمرار أعراض متكررة لفترة، يُنصح بحجز موعد طبي للتقييم.",
        "🧘 دقيقتان من التنفس الهادئ أو التأمل قد تساعدان خلال يوم مزدحم.",
        "🍬 يمكن تقليل السكريات المصنّعة ضمن نمط غذائي متوازن.",
        "🦷 يُنصح بتنظيف الأسنان مرتين يوميًا ضمن العناية بصحة الفم.",
        "💪 عند الجلوس لفترات طويلة، تساعد الحركة والتمدد دوريًا على تقليل تيبس الظهر والرقبة.",
        "❤️ العناية بالصحة النفسية والعاطفية جزء من الصحة العامة.",
    ],
    "en": [
        "💧 Drink enough water today, especially if it's hot — dehydration causes headaches and fatigue without you noticing.",
        "😴 Try to get 7-8 hours of sleep tonight. Poor sleep weakens immunity and increases stress.",
        "🚶 Just ten minutes of walking can boost your mood and circulation.",
        "📱 Reduce screen time an hour before bed — it helps you fall asleep faster and deeper.",
        "🥗 Try adding a vegetable or fruit to your next meal.",
        "🧴 If your eyes feel dry from screens, take a break every 20 minutes (the 20-20-20 rule).",
        "🫁 Take 3 deep breaths right now — it reduces stress within seconds.",
        "☀️ If you can, step outside and get a bit of sunlight — it improves mood and sleep.",
        "🧂 Cut back on extra salt if you've been feeling bloated or getting frequent headaches.",
        "🩺 If you've had recurring symptoms for a while and haven't seen a doctor, now's a good time to book an appointment.",
        "🧘 Two minutes of calm breathing or meditation can make a real difference in a busy day.",
        "🍬 Cut back on processed sugar today — your body will thank you in a few hours.",
        "🦷 Don't forget to brush your teeth twice today — oral health is linked to heart health.",
        "💪 If you've been sitting a lot, stand and stretch every hour — it reduces back and neck pain.",
        "❤️ Take care of your emotional wellbeing like you do your body — mental health is part of overall health.",
    ],
}

# Seasonal guidance for Saudi Arabia's two main seasons.
SEASONAL_TIPS = {
    "winter": {
        "ar": [
            "🦠 في موسم نزلات البرد والإنفلونزا، يفيد غسل اليدين بانتظام والحفاظ على الترطيب والتغذية المتوازنة.",
            "🧣 البرد يجفف البشرة — استخدم مرطبًا مناسبًا يوميًا، واستمر بشرب الماء حتى دون الشعور بالعطش.",
            "☀️ مع قصر النهار، قد يفيد التعرض المعتدل لضوء الشمس ومناقشة فيتامين D مع الطبيب عند الحاجة.",
            "🥘 السوائل الدافئة (شوربات، أعشاب) تخفف البرد وتهدئ الحلق وترطب الجسم.",
            "🛌 عند بداية أعراض الزكام، تساعد الراحة والنوم الكافي على التعافي.",
        ],
        "en": [
            "🦠 It's cold and flu season — wash your hands often and support your immunity with warm fluids and vitamin C.",
            "🧣 Cold weather dries out your skin — moisturize daily and keep drinking water even if you don't feel thirsty.",
            "☀️ With shorter days, get midday sunlight or discuss vitamin D with your doctor.",
            "🥘 Warm fluids (soups, herbal teas) ease cold symptoms, soothe your throat, and hydrate you.",
            "🛌 If you feel a cold coming on, rest and sleep more early — your body heals during sleep.",
        ],
    },
    "summer": {
        "ar": [
            "🥵 الحرارة مرتفعة — احرص على شرب الماء وتجنب الخروج وقت الظهيرة (11 صباحًا إلى 4 عصرًا).",
            "🧊 علامات ضربة الشمس: دوار، غثيان، صداع، بشرة حارة — عند ظهورها، انتقل إلى مكان بارد واشرب الماء إذا كان ذلك آمنًا.",
            "🍔 في الصيف يفسد الطعام أسرع؛ لذلك يجب الانتباه لسلامة حفظ الدجاج والأرز والسندويشات.",
            "😴 يمكن ضبط المكيف على درجة مريحة (24-26°م) مع الحفاظ على تهوية مناسبة أثناء النوم.",
            "☀️ عند الاضطرار للخروج نهارًا، يُنصح بغطاء مناسب للرأس وتجنب التعرض المباشر للشمس قدر الإمكان.",
        ],
        "en": [
            "🥵 Heat is intense — drink plenty of water and avoid going out at midday (11 AM to 4 PM).",
            "🧊 Heat stroke signs: dizziness, nausea, headache, hot skin — if you feel them, go somewhere cool and drink water.",
            "🍔 Food spoils faster in summer — watch out for food poisoning, especially chicken, rice and sandwiches.",
            "😴 Set your AC to a comfortable 24-26°C and sleep in a well-ventilated place.",
            "☀️ Wet your skin or wear a head cover if you must go out during the day — protection from dehydration and heat stroke.",
        ],
    },
}


def get_season(lang="ar"):
    """Returns (season_code, season_label, [tips]) based on the current month."""
    month = datetime.now().month
    if 10 <= month or month <= 3:
        code = "winter"
    else:
        code = "summer"
    label = ("🍂 الشتاء" if code == "winter" else "☀️ الصيف") if lang == "ar" else ("🍂 Winter" if code == "winter" else "☀️ Summer")
    tips = SEASONAL_TIPS[code].get(lang, SEASONAL_TIPS[code]["ar"])
    return code, label, tips


def get_random_tip(lang="ar"):
    """Returns a random tip; ~60% of the time it's seasonal, otherwise general."""
    general = TIPS.get(lang, TIPS["ar"])
    if random.random() < 0.6:
        _, _, seasonal = get_season(lang)
        return random.choice(seasonal)
    return random.choice(general)


# Categorized tip cards for the web tips center.
TIP_CARDS = [
    {"icon": "🥗", "cat_ar": "التغذية", "cat_en": "Nutrition",
     "title_ar": "وازن طبقك", "title_en": "Balance your plate",
     "text_ar": "الاعتماد على طبق متوازن يحتوي خضاراً وفاكهة وبروتيناً وحبوباً كاملة يحافظ على طاقتك وصحتك على المدى الطويل.",
     "text_en": "Relying on a balanced plate with vegetables, fruit, protein, and whole grains keeps your energy and health in the long run.",
     "tip_ar": "نصف الطبق خضار، ربع بروتين، وربع حبوب كاملة.",
     "tip_en": "Half the plate vegetables, a quarter protein, and a quarter whole grains."},
    {"icon": "🥗", "cat_ar": "التغذية", "cat_en": "Nutrition",
     "title_ar": "قلل السكريات المصنعة", "title_en": "Cut back on added sugar",
     "text_ar": "المشروبات والحلويات عالية السكر تسبب تقلبات في الطاقة وزيادة الوزن مع الوقت.",
     "text_en": "Sugary drinks and sweets cause energy swings and gradual weight gain over time.",
     "tip_ar": "استبدل المشروب الغازي بالماء المنكّه بالفواكه أو الشاي غير المحلى.",
     "tip_en": "Swap sugary drinks for fruit-infused water or unsweetened tea."},
    {"icon": "💧", "cat_ar": "الترطيب", "cat_en": "Hydration",
     "title_ar": "اشرب كفايتك من الماء", "title_en": "Drink enough water",
     "text_ar": "الجفاف البسيط يسبب صداعاً وتعباً وضعف تركيز دون أن تنتبه له.",
     "text_en": "Mild dehydration causes headaches, fatigue, and poor focus without you noticing.",
     "tip_ar": "احمل زجاجة ماء معك واشرب قبل أن تشعر بالعطش.",
     "tip_en": "Carry a water bottle and drink before you feel thirsty."},
    {"icon": "💧", "cat_ar": "الترطيب", "cat_en": "Hydration",
     "title_ar": "رطب بشرتك", "title_en": "Moisturize your skin",
     "text_ar": "الجلد الجاف شائع في الأجواء الحارة أو المكيفة؛ الترطيب الخارجي والداخلي يحمي بشرتك.",
     "text_en": "Dry skin is common in hot or air-conditioned environments; inner and outer hydration protects it.",
     "tip_ar": "ضع مرطباً بعد الاستحمام واشرب ماءً كافياً طوال اليوم.",
     "tip_en": "Apply moisturizer after showering and drink enough water all day."},
    {"icon": "😴", "cat_ar": "النوم", "cat_en": "Sleep",
     "title_ar": "نم من 7 إلى 8 ساعات", "title_en": "Sleep 7–8 hours",
     "text_ar": "قلة النوم تضعف المناعة وترفع التوتر وتؤثر على المزاج والتركيز.",
     "text_en": "Poor sleep weakens immunity, increases stress, and affects mood and focus.",
     "tip_ar": "ثبّت موعد نومك واجعل غرفتك مظلمة وهادئة.",
     "tip_en": "Keep a fixed bedtime and make your room dark and quiet."},
    {"icon": "😴", "cat_ar": "النوم", "cat_en": "Sleep",
     "title_ar": "ابتعد عن الشاشات قبل النوم", "title_en": "Avoid screens before bed",
     "text_ar": "الضوء الأزرق يؤخر إفراز هرمون النوم ويصعّب الاستغراق في النوم.",
     "text_en": "Blue light delays the sleep hormone and makes it harder to fall asleep.",
     "tip_ar": "أطفئ الشاشات قبل النوم بساعة واقرأ كتاباً بدلاً منها.",
     "tip_en": "Turn off screens an hour before bed and read a book instead."},
    {"icon": "🏃", "cat_ar": "النشاط", "cat_en": "Activity",
     "title_ar": "امشِ عشر دقائق", "title_en": "Walk ten minutes",
     "text_ar": "المشي البسيط يحسّن الدورة الدموية والمزاج ويخفف أثر الجلوس الطويل.",
     "text_en": "Simple walking improves circulation and mood and offsets long sitting.",
     "tip_ar": "قسّم المشي إلى فترتين من خمس دقائق بعد الوجبات.",
     "tip_en": "Split it into two five-minute walks after meals."},
    {"icon": "🏃", "cat_ar": "النشاط", "cat_en": "Activity",
     "title_ar": "تحرك كل ساعة", "title_en": "Move every hour",
     "text_ar": "الجلوس الطويل يسبب آلاماً في الظهر والرقبة ويبطئ الدورة الدموية.",
     "text_en": "Long sitting causes back and neck pain and slows circulation.",
     "tip_ar": "قف وتمدد دقيقة واحدة كل ساعة عمل.",
     "tip_en": "Stand and stretch for one minute every work hour."},
    {"icon": "🧘", "cat_ar": "الصحة النفسية", "cat_en": "Mental Health",
     "title_ar": "تنفس بعمق", "title_en": "Breathe deeply",
     "text_ar": "التنفس البطيء يهدئ الجهاز العصبي ويخفض التوتر خلال دقائق.",
     "text_en": "Slow breathing calms the nervous system and lowers stress within minutes.",
     "tip_ar": "استنشق 4 ثوانٍ، احبس 4 ثوانٍ، وزفر 6 ثوانٍ.",
     "tip_en": "Breathe in for 4 seconds, hold for 4, and exhale for 6."},
    {"icon": "🧘", "cat_ar": "الصحة النفسية", "cat_en": "Mental Health",
     "title_ar": "خصص وقتاً لنفسك", "title_en": "Make time for yourself",
     "text_ar": "الصحة النفسية جزء من الصحة العامة؛ خصص وقتاً للراحة والنشاط الذي تحبه.",
     "text_en": "Mental health is part of overall health; set aside time for rest and activities you enjoy.",
     "tip_ar": "خمس دقائق هادئة لنفسك يومياً بداية جيدة للعناية النفسية.",
     "tip_en": "Five quiet minutes for yourself daily is a good start to self-care."},
    {"icon": "🛡️", "cat_ar": "الوقاية", "cat_en": "Prevention",
     "title_ar": "اغسل يديك باستمرار", "title_en": "Wash your hands often",
     "text_ar": "غسل اليدين بالماء والصابون يقلل انتقال العدوى الموسمية بشكل كبير.",
     "text_en": "Washing hands with soap and water significantly reduces seasonal infections.",
     "tip_ar": "اغسل يديك لمدة 20 ثانية بعد المواصلات وقبل الأكل.",
     "tip_en": "Wash your hands for 20 seconds after transit and before eating."},
    {"icon": "🛡️", "cat_ar": "الوقاية", "cat_en": "Prevention",
     "title_ar": "راقب أعراضك المتكررة", "title_en": "Watch recurring symptoms",
     "text_ar": "الأعراض المستمرة أو المتكررة تستحق مراجعة الطبيب وليس التسويف.",
     "text_en": "Persistent or recurring symptoms deserve a doctor's visit, not postponement.",
     "tip_ar": "إذا استمر عرض ما أكثر من أسبوعين، احجز موعداً للمراجعة.",
     "tip_en": "If a symptom lasts more than two weeks, book a check-up."},
]


def get_tip_card(lang="ar"):
    """Returns a categorized tip card as a dict {icon, cat, title, text, tip}."""
    card = random.choice(TIP_CARDS)
    key = "ar" if lang != "en" else "en"
    return {
        "icon": card["icon"],
        "cat": card["cat_" + key],
        "title": card["title_" + key],
        "text": card["text_" + key],
        "tip": card["tip_" + key],
    }
