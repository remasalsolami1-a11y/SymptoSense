import random
from datetime import datetime

TIPS = {
    "ar": [
        "💧 اشربي كمية كافية من الماء اليوم، خصوصاً لو الجو حار — الجفاف يسبب صداع وتعب بدون ما تنتبهين.",
        "😴 حاولي تنامين 7-8 ساعات الليلة. قلة النوم تضعف المناعة وتزيد التوتر.",
        "🚶 عشر دقايق مشي بسيطة تكفي تحسّن مزاجك ودورتك الدموية.",
        "📱 قللي وقت الشاشة قبل النوم بساعة — يساعدك تنامين أسرع وأعمق.",
        "🥗 حاولي تضيفين خضار أو فاكهة لوجبتك القادمة.",
        "🧴 لو تحسين بجفاف بالعين من الشاشة، خذي استراحة كل 20 دقيقة (قاعدة 20-20-20).",
        "🫁 خذي نفس عميق 3 مرات الحين — يقلل التوتر بثواني.",
        "☀️ لو تقدرين، اطلعي بره وتعرضي لضوء الشمس شوي — يحسن المزاج والنوم.",
        "🧂 قللي الملح الزايد لو تحسين بانتفاخ أو صداع متكرر.",
        "🩺 لو عندك أعراض متكررة من فترة وما راجعتي طبيب، هذا وقت مناسب تسوين موعد.",
        "🧘 دقيقتين تأمل أو تنفس هادئ تقدر تفرق كثير بيوم مزحوم.",
        "🍬 قللي السكريات المصنّعة اليوم، جسمك بيشكرك بعد كم ساعة.",
        "🦷 لا تنسين تنظيف أسنانك مرتين اليوم — صحة الفم مرتبطة بصحة القلب.",
        "💪 لو قاعدة كثير، قومي تمططي كل ساعة — يقلل آلام الظهر والرقبة.",
        "❤️ اعتني بنفسك عاطفياً زي ما تعتنين بجسمك — الصحة النفسية جزء من الصحة العامة.",
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
            "🦠 موسم نزلات البرد والإنفلونزا — غسلي يديك باستمرار، وادعمي مناعتك بالسوائل الدافئة وفيتامين C.",
            "🧣 البرد يجفف البشرة — رطبيها بكريم مرطب يومي، واستمري بشرب الماء حتى لو ما تحسين بالعطش.",
            "☀️ مع قصر النهار، احرصي على التعرض للشمس وقت الظهيرة أو ناقشي مع طبيبك فيتامين D.",
            "🥘 السوائل الدافئة (شوربات، أعشاب) تخفف البرد وتهدئ الحلق وترطب الجسم.",
            "🛌 لو حسيتي ببداية زكام، ابدئي براحة ونوم أطول — الجسد يشفى أثناء النوم.",
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
            "🥵 الحرارة مرتفعة — اشربي ماء كثير، وتجنبي الخروج وقت الظهيرة (11 صباحاً إلى 4 عصراً).",
            "🧊 علامات ضربة الشمس: دوار، غثيان، صداع، بشرة حارة — لو حسيتي بيها ادخلي مكان بارد واشربي ماء.",
            "🍔 في الصيف الأكل يفسد أسرع — انتبهي من التسمم الغذائي، خصوصاً الدجاج والأرز والسندويشات.",
            "😴 اضبطي المكيف على حرارة مريحة (24-26) ونمي في مكان جيد التهوية.",
            "☀️ بلّي نفسك أو ارتدي غطاء رأس لو اضطررت للخروج نهاراً — حماية من الجفاف وضربة الشمس.",
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
    label = "🍂 الشتاء / Winter" if code == "winter" else "☀️ الصيف / Summer"
    tips = SEASONAL_TIPS[code].get(lang, SEASONAL_TIPS[code]["ar"])
    return code, label, tips


def get_random_tip(lang="ar"):
    """Returns a random tip; ~60% of the time it's seasonal, otherwise general."""
    general = TIPS.get(lang, TIPS["ar"])
    if random.random() < 0.6:
        _, _, seasonal = get_season(lang)
        return random.choice(seasonal)
    return random.choice(general)
