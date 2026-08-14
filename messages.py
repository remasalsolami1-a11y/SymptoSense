from ..database.symptoms import get_symptoms_list


def get_welcome_message(lang: str) -> str:
    if lang == "ar":
        return (
            "🩺 مرحباً بك في فاحص الأعراض الطبية\n\n"
            "أنا مساعدك الصحي الذكي. سأساعدك في تحليل أعراضك\n"
            "وتقديم احتمالات عامة ونصائح طبية.\n\n"
            "⚠️ تنبيه: هذا البوت لأغراض تعليمية فقط\n"
            "ولا يغني عن استشارة الطبيب المختص.\n\n"
            "ما هو عمرك؟ (أدخل رقم)"
        )
    return (
        "🩺 Welcome to Medical Symptom Checker\n\n"
        "I'm your smart health assistant. I'll help you analyze\n"
        "your symptoms and provide general possibilities and medical advice.\n\n"
        "⚠️ Notice: This bot is for educational purposes only\n"
        "and does not replace consulting a doctor.\n\n"
        "What is your age? (Enter a number)"
    )


def get_age_message(lang: str, error: bool = False) -> str:
    if lang == "ar":
        msg = "ما هو عمرك؟ (أدخل رقم من 1 إلى 120)"
        if error:
            msg = "❌يرجى إدخال رقم صحيح من 1 إلى 120\n\n" + msg
        return msg
    msg = "What is your age? (Enter a number from 1 to 120)"
    if error:
        msg = "❌ Please enter a valid number from 1 to 120\n\n" + msg
    return msg


def get_gender_message(lang: str) -> str:
    if lang == "ar":
        return "ما هو جنسك؟ (ذكر / أنثى)"
    return "What is your gender? (Male / Female)"


def get_symptoms_message(lang: str) -> str:
    symptoms = get_symptoms_list()
    if lang == "ar":
        symptoms_list = "\n".join([f"• {s}" for s in symptoms])
        return (
            "الآن أدخل الأعراض التي تعاني منها.\n"
            "اكتب اسم العرض ثم ENTER لكل عرض.\n"
            "اكتب 'تم' عند الانتهاء.\n\n"
            "الأعراض المتاحة:\n"
            f"{symptoms_list}"
        )
    symptoms_list_en = "\n".join([f"• {s}" for s in symptoms])
    return (
        "Now enter the symptoms you're experiencing.\n"
        "Type each symptom name and press ENTER.\n"
        "Type 'done' when finished.\n\n"
        "Available symptoms:\n"
        f"{symptoms_list_en}"
    )


def get_duration_message(lang: str) -> str:
    if lang == "ar":
        return (
            "منذ متى وأنت تعاني من هذه الأعراض؟\n\n"
            "اختر من القائمة:\n"
            "• ساعات\n"
            "• يوم\n"
            "• أيام\n"
            "• أسبوع\n"
            "• أسبوعين\n"
            "• أكثر من أسبوع\n"
            "• أكثر من أسبوعين\n"
            "• شهر\n"
            "• أشهر\n"
            "• سنوات"
        )
    return (
        "How long have you been experiencing these symptoms?\n\n"
        "Choose from the list:\n"
        "• hours\n"
        "• day\n"
        "• days\n"
        "• week\n"
        "• weeks\n"
        "• more than a week\n"
        "• more than two weeks\n"
        "• month\n"
        "• months\n"
        "• years"
    )


def get_pain_message(lang: str) -> str:
    if lang == "ar":
        return "ما هي شدة الألم؟ (أدخل رقم من 1 إلى 10)\n\n1 = ألم خفيف جداً\n10 = ألم شديد جداً"
    return "What is the pain severity? (Enter a number from 1 to 10)\n\n1 = Very mild pain\n10 = Severe pain"


def get_history_message(lang: str) -> str:
    if lang == "ar":
        return (
            "هل تعاني من أي أمراض سابقة أو حالية؟\n"
            "أدخلها مفصولة بفاصلة (مثال: سكري, ضغط, ربو)\n"
            "أكتب 'لا' إذا لم تعاني من أي أمراض"
        )
    return (
        "Do you have any previous or current medical conditions?\n"
        "Enter them separated by commas (e.g., diabetes, asthma)\n"
        "Type 'no' if you don't have any conditions"
    )
