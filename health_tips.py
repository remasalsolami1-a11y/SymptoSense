import random

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


def get_random_tip(lang="ar"):
    tips = TIPS.get(lang, TIPS["ar"])
    return random.choice(tips)
