"""Deterministic mental-wellbeing support for SymptoSense.

This module is intentionally non-diagnostic. It provides short supportive
responses and safety escalation that remain available even when the external
LLM provider is unavailable.
"""
from __future__ import annotations

import re
from typing import Dict, List

import clinical_text


def _norm(text: str) -> str:
    value = " ".join(str(text or "").strip().lower().split())
    value = re.sub(r"[\u064b-\u065f\u0670\u0640]", "", value)
    return value[:1000]


DIRECT_CRISIS_AR = (
    # Explicit first-person suicidal intent / self-harm language. Keep these
    # concrete so educational mentions of suicide do not become emergencies.
    "اقتل نفسي", "أقتل نفسي", "بقتل نفسي", "راح اقتل نفسي", "راح أقتل نفسي",
    "اؤذي نفسي", "أؤذي نفسي", "اذي نفسي", "أذي نفسي", "اضر بنفسي", "أضر بنفسي",
    "اجرح نفسي", "أجرح نفسي", "ابي اموت", "أبي أموت", "ابغى اموت", "أبغى أموت",
    "ودي اموت", "ودي أموت", "نفسي اموت", "نفسي أموت", "اريد الموت", "أريد الموت",
    "اتمنى اموت", "أتمنى أموت", "لا اريد العيش", "لا أريد العيش", "ما ابي اعيش",
    "ما أبي أعيش", "ما ابغى اعيش", "ما أبغى أعيش", "ما عاد ابي اعيش", "ما عاد أبي أعيش",
    "انهي حياتي", "أنهي حياتي", "اخلص من حياتي", "أخلص من حياتي",
    "ابي انتحر", "أبي أنتحر", "ابغى انتحر", "أبغى أنتحر", "ودي انتحر", "ودي أنتحر",
    "افكر انتحر", "أفكر أنتحر", "افكر بالانتحار", "أفكر بالانتحار", "افكر في الانتحار",
    "أفكر في الانتحار", "ناوي انتحر", "ناوية انتحر", "راح انتحر", "راح أنتحر",
    "سوف انتحر", "سوف أنتحر", "بنتحر", "اخطط للانتحار", "أخطط للانتحار",
    "عندي خطة للانتحار", "عندي خطة انتحر", "مخطط انتحر", "مخططة انتحر",
    # Inability to guarantee immediate safety is treated as direct crisis risk.
    "ما اقدر اضمن نفسي", "ما أقدر أضمن نفسي", "مو ضامن نفسي", "مو ضامنة نفسي",
    "اخاف اوذي نفسي", "أخاف أؤذي نفسي", "اخاف اذي نفسي", "أخاف أذي نفسي",
    "ما اقدر ابقى امن", "ما أقدر أبقى آمن", "ما اقدر ابقي امن", "ما أقدر أبقي آمن",
    "مو متأكد اقدر ابقى امن", "مو متأكدة أقدر أبقى آمنة",
)
DIRECT_CRISIS_EN = (
    "kill myself", "i will kill myself", "i'll kill myself", "i am going to kill myself", "i'm going to kill myself",
    "want to die", "i want to die", "i wanna die", "wish i were dead", "i wish i were dead",
    "don't want to live", "do not want to live", "i don't want to live", "i do not want to live",
    "don't want to be alive", "do not want to be alive", "end my life", "take my own life",
    "i am suicidal", "i'm suicidal", "im suicidal", "suicidal thoughts", "thinking about suicide",
    "thinking of suicide", "i have a suicide plan", "i have a plan to kill myself", "planning to kill myself",
    "i want to hurt myself", "i want to harm myself", "i'm going to hurt myself", "i am going to hurt myself",
    "self harm", "self-harm", "cut myself", "overdose to die", "overdose myself",
    "can't keep myself safe", "cannot keep myself safe", "not sure i can stay safe",
    "afraid i'll hurt myself", "afraid i will hurt myself",
)

# Explicit statements that negate otherwise high-risk phrases. We remove these
# before direct-crisis matching so "ما أبي أموت" / "I don't want to die" do
# not trigger an emergency card by substring alone.
SAFE_NEGATED_DIRECT_AR = (
    "ما ابي اموت", "ما أبي أموت", "ما ابغى اموت", "ما أبغى أموت", "ما ودي اموت", "ما ودي أموت",
    "لا اريد الموت", "لا أريد الموت", "ما اريد الموت", "ما أريد الموت",
    "ما افكر بالانتحار", "ما أفكر بالانتحار", "ما افكر في الانتحار", "ما أفكر في الانتحار",
    "ما راح انتحر", "ما راح أنتحر", "لن انتحر", "لن أنتحر",
)
SAFE_NEGATED_DIRECT_EN = (
    "i don't want to die", "i do not want to die", "i am not suicidal", "i'm not suicidal", "im not suicidal",
    "i am not thinking about suicide", "i'm not thinking about suicide", "not thinking about suicide",
    "i won't kill myself", "i will not kill myself",
)

# A single crisis keyword in the mental-support space is ambiguous but important
# enough to prompt a direct safety check rather than being ignored.
STANDALONE_CRISIS_AR = ("انتحار", "الانتحار", "افكار انتحارية", "أفكار انتحارية", "ايذاء النفس", "إيذاء النفس")
STANDALONE_CRISIS_EN = ("suicide", "suicidal", "self harm", "self-harm")

PASSIVE_RISK_AR = (
    "اتمنى ما اصحى", "أتمنى ما أصحى", "يا ليتني ما اصحى", "يا ليتني ما أصحى",
    "ودي ما اصحى", "ودي ما أصحى", "اتمنى اختفي", "أتمنى أختفي",
    "وجودي ماله فايدة", "وجودي ما له فايدة", "مالي فايدة", "ما لي فايدة",
    "ما عاد اقدر اكمل", "ما عاد أقدر أكمل", "تعبت من الحياة", "كرهت الحياة",
    "ودي اختفي", "ودي أختفي", "الكل افضل بدوني", "الكل أفضل بدوني",
    "الناس افضل بدوني", "الناس أفضل بدوني", "مالي داعي اعيش", "ما لي داعي أعيش",
)
PASSIVE_RISK_EN = (
    "wish i wouldn't wake up", "wish i would not wake up", "don't want to wake up", "do not want to wake up",
    "wish i could disappear", "better off without me", "everyone would be better without me",
    "everyone would be better off without me", "no point in living", "can't go on", "cannot go on", "tired of life",
)


PANIC_AR = ("نوبة هلع", "هلع", "خوف شديد", "قلبي يدق بسرعة", "خفقان من الخوف", "اختنق من القلق")
PANIC_EN = ("panic attack", "panicking", "panic", "heart racing from anxiety", "can't breathe from anxiety")

VENT_AR = ("ابي افضفض", "أبي أفضفض", "بس اسمعني", "اسمعني شوي", "بدون حلول", "ما ابي نصايح", "ما أبي نصايح")
VENT_EN = ("just need to vent", "just listen", "listen for a bit", "no advice", "don't give me advice", "do not give me advice")
SORT_AR = ("ساعدني افكر", "ساعدني أفكر", "رتب افكاري", "رتب أفكاري", "نرتب افكاري", "نرتب أفكاري")
SORT_EN = ("help me sort it out", "help me think", "sort my thoughts", "untangle this")

SOCIAL_ANXIETY_AR = ("اخاف من الناس", "أخاف من الناس", "توتر اجتماعي", "قلق اجتماعي", "اتوتر قدام الناس", "أتوتر قدام الناس", "اخاف اتكلم", "أخاف أتكلم")
SOCIAL_ANXIETY_EN = ("social anxiety", "nervous around people", "afraid to talk to people", "anxious around people")
PROCRASTINATION_AR = ("اسوف", "أسوف", "تسويف", "ما اقدر ابدا", "ما أقدر أبدأ", "متراكم علي", "متراكمه علي", "متراكمة علي", "مو قادر ابدا", "مو قادرة ابدأ")
PROCRASTINATION_EN = ("procrastinating", "procrastination", "can't start", "cannot start", "too much piled up", "everything is piling up")
INTRUSIVE_AR = ("افكار ملحه", "أفكار ملحة", "افكار مزعجه", "أفكار مزعجة", "فكرة تلاحقني", "وسواس", "افكار دخيله", "أفكار دخيلة")
INTRUSIVE_EN = ("intrusive thoughts", "obsessive thoughts", "thought keeps coming back", "unwanted thoughts")
DECISION_AR = ("محتار", "محتارة", "ما اعرف اقرر", "ما أعرف أقرر", "قرار صعب", "مو عارف اختار", "مو عارفة اختار")
DECISION_EN = ("can't decide", "cannot decide", "hard decision", "don't know what to choose", "stuck deciding")
BOUNDARY_AR = ("ما اعرف ارفض", "ما أعرف أرفض", "ما اقدر اقول لا", "ما أقدر أقول لا", "ارضّي الناس", "أرضي الناس", "حدود", "يستغلني")
BOUNDARY_EN = ("can't say no", "cannot say no", "people pleasing", "boundaries", "taking advantage of me")
PLAN_AR = ("ابي خطة", "أبي خطة", "عطني خطة", "ابغى خطة", "أبغى خطة", "وش اسوي خطوة خطوة", "وش أسوي خطوة خطوة")
PLAN_EN = ("give me a plan", "i need a plan", "step by step", "what should i do first")

OTHER_HARM_AR = (
    "ابي اقتله", "أبي أقتله", "ابغى اقتله", "أبغى أقتله", "بقتله", "راح اقتله", "راح أقتله",
    "ابي اذبحه", "أبي أذبحه", "ابي اضربه", "أبي أضربه", "بأذيه", "باذيه",
    "ابي اقتل احد", "أبي أقتل أحد", "ابغى اقتل احد", "أبغى أقتل أحد", "بقتل احد", "بقتل أحد",
    "ابي اوذي احد", "أبي أؤذي أحد", "ابغى اوذي احد", "أبغى أؤذي أحد",
)
OTHER_HARM_EN = (
    "i'm going to kill him", "i'm going to kill her", "i am going to kill him", "i am going to kill her",
    "i want to kill him", "i want to kill her", "i want to kill someone", "i'm going to kill someone",
    "i am going to kill someone", "i want to hurt him", "i want to hurt her", "i want to hurt someone",
    "i'm going to hurt someone", "i am going to hurt someone",
)

MEDICAL_RED_FLAGS_AR = (
    "الم صدر شديد", "ألم صدر شديد", "ضيق تنفس شديد", "ما اقدر اتنفس", "ما أقدر أتنفس",
    "اغماء", "إغماء", "ضعف مفاجئ", "تنميل جهة", "فقدان الرؤية", "نزيف شديد",
)
MEDICAL_RED_FLAGS_EN = (
    "severe chest pain", "severe shortness of breath", "can't breathe", "cannot breathe",
    "fainted", "fainting", "sudden weakness", "one-sided weakness", "vision loss", "heavy bleeding",
)


def _remove_explicit_safe_negations(text: str) -> str:
    """Remove whole, explicit denials before crisis matching.

    This is deliberately narrow: we only remove phrases that clearly say the
    person does *not* want to die / is *not* suicidal. Phrases such as
    "لا أريد العيش" remain high risk because their meaning is the opposite.
    """
    cleaned = _norm(text)
    for phrase in SAFE_NEGATED_DIRECT_AR + SAFE_NEGATED_DIRECT_EN:
        candidate = _norm(phrase)
        if candidate:
            cleaned = cleaned.replace(candidate, " ")
    return " ".join(cleaned.split())


def safety_level(text: str) -> str:
    low = _norm(text)
    crisis_scan = _remove_explicit_safe_negations(low)
    # Match complete high-risk phrases first. Some high-risk phrases legitimately
    # contain words such as "don't" (for example "don't want to live"), so the
    # phrase itself remains positive while explicit safe denials are stripped.
    if clinical_text.contains_unnegated_any(crisis_scan, DIRECT_CRISIS_AR + DIRECT_CRISIS_EN):
        return "direct"
    if clinical_text.contains_unnegated_any(low, OTHER_HARM_AR + OTHER_HARM_EN):
        return "other_harm"
    if clinical_text.contains_unnegated_any(low, MEDICAL_RED_FLAGS_AR + MEDICAL_RED_FLAGS_EN):
        return "medical_red_flag"
    if clinical_text.contains_unnegated_any(low, PASSIVE_RISK_AR + PASSIVE_RISK_EN):
        return "passive"
    # A one- or two-word crisis query inside the mental-support feature deserves
    # a direct safety check, but a longer educational sentence such as
    # "I am reading about suicide" should not be treated as intent.
    normalized = clinical_text.normalize_clinical_text(low).replace(" | ", " ").strip()
    standalone = {clinical_text.normalize_clinical_text(x).replace(" | ", " ").strip()
                  for x in STANDALONE_CRISIS_AR + STANDALONE_CRISIS_EN}
    if normalized in standalone:
        return "passive"
    return "none"


def is_affirmative_crisis_followup(messages) -> bool:
    """Detect a short affirmative reply to a direct safety question.

    This prevents a user replying only "نعم" / "yes" after a safety check from
    falling back into ordinary conversation because the current message itself
    contains no self-harm keyword.
    """
    if not isinstance(messages, (list, tuple)) or len(messages) < 2:
        return False
    current = messages[-1] if isinstance(messages[-1], dict) else {}
    previous = messages[-2] if isinstance(messages[-2], dict) else {}
    if current.get("role") != "user" or previous.get("role") != "assistant":
        return False
    prev = _norm(previous.get("content") or "")
    cur = _norm(current.get("content") or "")
    safety_questions = (
        "هل تفكر الآن في ايذاء نفسك", "هل تفكر الآن في إيذاء نفسك", "او انهاء حياتك", "أو إنهاء حياتك",
        "هل انت امن", "هل أنت آمن", "تقدر تبقى امن", "تقدر تبقى آمن",
        "are you thinking about hurting yourself", "are you thinking about ending your life",
        "can you stay safe", "are you safe right now",
    )
    if not any(_norm(marker) in prev for marker in safety_questions):
        return False
    affirmatives = {
        "نعم", "ايوه", "أيوه", "ايه", "إيه", "اي", "إي", "صح", "صحيح", "يمكن", "ممكن",
        "مو متاكد", "مو متأكد", "مو متاكده", "مو متأكدة", "ما ادري", "ما أدري", "لا اقدر اضمن", "لا أقدر أضمن",
        "yes", "yeah", "yep", "i am", "i do", "maybe", "possibly", "not sure", "i'm not sure", "im not sure",
    }
    cur_norm = clinical_text.normalize_clinical_text(cur).replace(" | ", " ").strip()
    return cur_norm in {clinical_text.normalize_clinical_text(x).replace(" | ", " ").strip() for x in affirmatives}


def crisis_message(lang: str = "ar") -> str:
    if lang == "en":
        return (
            "I'm concerned about your safety, and what you said matters. If you might hurt yourself or you are in immediate danger, "
            "please do not stay alone: move away from anything you could use to hurt yourself, stay with someone you trust, and call "
            "Saudi ambulance services on 997 or the unified emergency number 911 now. You can also call the Ministry of Health on 937 for 24/7 health support."
        )
    return (
        "أنا قلق على سلامتك الآن، وكلامك مهم. إذا كنت قد تؤذي نفسك أو كنت في خطر مباشر، لا تبق وحدك: "
        "ابتعد عن أي شيء قد تستخدمه لإيذاء نفسك، وابقَ مع شخص تثق به، واتصل بالإسعاف 997 أو بالطوارئ الموحدة 911 الآن. "
        "وتقدر أيضًا تتواصل مع وزارة الصحة على 937 للدعم والاستشارة الصحية على مدار الساعة."
    )


def passive_risk_message(lang: str = "ar") -> str:
    if lang == "en":
        return (
            "That sounds painfully heavy, and I want to check your safety directly. Are you thinking about hurting yourself or ending your life right now? "
            "If yes, or if you are not sure you can stay safe, do not stay alone—call 997 or the unified emergency number 911 now. You can also contact the Ministry of Health on 937."
        )
    return (
        "هذا الكلام يدل أن الحمل عليك ثقيل جدًا، وأحتاج أتأكد من سلامتك بشكل مباشر: هل تفكر الآن في إيذاء نفسك أو إنهاء حياتك؟ "
        "إذا نعم، أو مو متأكد أنك تقدر تبقى آمن، لا تبق وحدك واتصل بالإسعاف 997 أو بالطوارئ الموحدة 911 الآن. وتقدر أيضًا تتواصل مع وزارة الصحة على 937."
    )


def other_harm_message(lang: str = "ar") -> str:
    if lang == "en":
        return (
            "I hear how intense this is. Put some distance between you and the person right now, and move away from any weapon or object you could use to hurt them. "
            "If you think you may act on it, move away from weapons or other means of harm and call the unified emergency number 911 now; call 997 as well if anyone needs urgent medical help. Stay with a trusted person who can help keep everyone safe."
        )
    return (
        "أسمع قد إيش الغضب عالي الآن. أبعد نفسك عن الشخص للحظة، وابتعد عن أي سلاح أو شيء ممكن تستخدمه لإيذائه. "
        "إذا تحس إنك ممكن تتصرف فعلًا، ابتعد عن أي سلاح أو وسيلة أذى واتصل بالطوارئ الموحدة 911 الآن؛ وإذا احتاج أحد إسعافًا عاجلًا فاتصل بـ997 أيضًا. خلك مع شخص تثق به يساعد يحافظ على سلامتك وسلامة غيرك."
    )


def medical_red_flag_message(lang: str = "ar") -> str:
    if lang == "en":
        return (
            "Because you mentioned a potentially serious physical symptom, please do not assume this is only anxiety. "
            "If the symptom is severe, new, or worsening—especially severe chest pain, severe breathing difficulty, fainting, or sudden weakness—call 997 now."
        )
    return (
        "لأنك ذكرت عرضًا جسديًا قد يكون مهمًا، لا نفترض أنه قلق فقط. إذا كان العرض شديدًا أو جديدًا أو يزداد—خصوصًا ألم صدر شديد، "
        "صعوبة شديدة في التنفس، إغماء، أو ضعف مفاجئ—اتصل بالإسعاف 997 الآن."
    )


def grounding_54321(lang: str = "ar") -> str:
    if lang == "en":
        return (
            "🧭 5-4-3-2-1 grounding\n"
            "Look around slowly and name: 5 things you can see, 4 things you can feel, 3 things you can hear, "
            "2 things you can smell (or remember the smell of), and 1 thing you can taste. "
            "No need to do it perfectly—just bring your attention back to the room you're in."
        )
    return (
        "🧭 تمرين التثبيت 5-4-3-2-1\n"
        "انظر حولك بهدوء وسمِّ: 5 أشياء تشوفها، 4 أشياء تقدر تلمسها أو تحس بها، 3 أصوات تسمعها، "
        "شيئين تقدر تشمهم أو تتذكر رائحتهم، وشيئًا واحدًا تقدر تتذوقه. ما يحتاج تسويه بشكل مثالي؛ الهدف ترجع انتباهك للحظة والمكان اللي أنت فيه."
    )


def calm_breathing(lang: str = "ar") -> str:
    if lang == "en":
        return (
            "🌿 Try a gentle breathing rhythm for one minute: breathe in comfortably through your nose for about 4 seconds, "
            "then let the breath out slowly for about 6 seconds. Do not force a deep breath or hold it. If you feel dizzy or uncomfortable, return to normal breathing."
        )
    return (
        "🌿 جرّب تنفسًا هادئًا لمدة دقيقة: خذ شهيقًا مريحًا من الأنف قرابة 4 ثوانٍ، ثم أخرج النفس ببطء قرابة 6 ثوانٍ. "
        "لا تجبر نفسك على نفس عميق ولا تحبس النفس. إذا حسيت بدوخة أو عدم ارتياح، ارجع لتنفسك الطبيعي."
    )


def urgent_support(lang: str = "ar") -> str:
    if lang == "en":
        return (
            "🚨 If you feel you may not be safe with yourself, do not stay alone. Stay with someone you trust, move away from anything you could use to hurt yourself, "
            "and call 997 or the unified emergency number 911 now. For 24/7 health consultation in Saudi Arabia, you can also call the Ministry of Health on 937."
        )
    return (
        "🚨 إذا كنت تشعر أنك قد لا تكون آمنًا على نفسك، لا تبق وحدك. خلك مع شخص تثق به، وابتعد عن أي شيء قد تستخدمه لإيذاء نفسك، "
        "واتصل بالإسعاف 997 أو بالطوارئ الموحدة 911 الآن. وللاستشارة الصحية على مدار الساعة داخل السعودية يمكنك الاتصال بوزارة الصحة على 937."
    )


def _has(low: str, words) -> bool:
    return any(w in low for w in words)


def supportive_answer(text: str, lang: str = "ar") -> str:
    query = _norm(text)
    if not query:
        return ""

    level = safety_level(query)
    if level == "direct":
        return crisis_message(lang)
    if level == "other_harm":
        return other_harm_message(lang)
    if level == "medical_red_flag":
        return medical_red_flag_message(lang)
    if level == "passive":
        return passive_risk_message(lang)

    ar = lang != "en"
    if ar and _has(query, VENT_AR):
        return "أكيد 🤍 خذ راحتك وقل اللي بخاطرك مثل ما هو. ما راح أقفز للحلول؛ أنا أسمعك. وش صار؟"
    if (not ar) and _has(query, VENT_EN):
        return "Of course 🤍 Say it exactly as it is. I won't jump into solutions; I'm listening. What happened?"
    if ar and _has(query, SORT_AR):
        return "أكيد، نرتبها سوا بهدوء. لا تعطيني كل شيء مرة وحدة—ابدأ بالجزء اللي مضايقك أكثر، ونمشي منه."
    if (not ar) and _has(query, SORT_EN):
        return "Sure. We can untangle it without trying to solve everything at once. Start with the part that's bothering you most, and we'll go from there."
    if ar:
        if _has(query, SOCIAL_ANXIETY_AR):
            return (
                "التوتر قدام الناس يخلي العقل يراقب كل كلمة وحركة كأنها اختبار. بدل ما يكون هدفك «أكون طبيعي 100%»، جرّب هدفًا أصغر: موقف اجتماعي قصير واحد، وركّز على الشخص أو الموضوع بدل مراقبة نفسك طول الوقت. "
                "وش أكثر موقف يرفع التوتر عندك: الكلام، التجمعات، ولا الخوف من حكم الناس؟"
            )
        if _has(query, PROCRASTINATION_AR):
            return (
                "إذا الشيء متراكم، البداية نفسها تصير أصعب من المهمة. خلها خطة 10 دقائق فقط: افتح المطلوب، اختر أصغر جزء ممكن، واشتغل عليه 10 دقائق بدون شرط تكمله. "
                "إذا كتبت لي الشيء المتراكم عليك، أقسمه لك لأول 3 خطوات صغيرة."
            )
        if _has(query, INTRUSIVE_AR):
            return (
                "الفكرة المزعجة إذا حاولت تطردها بالقوة ممكن ترجع أعلى. سمّها ببساطة «هذه فكرة مزعجة، مو حقيقة ولا أمر لازم أنفذه»، ثم رجّع انتباهك لشيء موجود قدامك الآن. "
                "هل اللي يزعجك محتوى الفكرة نفسها، أو خوفك من أنها ترجع كثير؟"
            )
        if _has(query, DECISION_AR):
            return (
                "إذا القرار ملخبطك، لا نحاول نضمن القرار المثالي. اكتب خيارين فقط، وتحت كل واحد: أهم فائدة، أهم خسارة، وشيء واحد قابل للتراجع لو ما ناسبك. "
                "وش القرار اللي محتار فيه؟"
            )
        if _has(query, BOUNDARY_AR):
            return (
                "قول «لا» ما يحتاج يكون قاسي. تقدر تبدأ بجملة قصيرة مثل: «ما أقدر ألتزم بهذا الآن» بدون تبرير طويل. "
                "إذا تحب، اكتب لي الموقف وأنا أساعدك نصيغ رد يحافظ على حدودك بدون تصعيد."
            )
        if _has(query, PLAN_AR):
            return (
                "تمام، نخليها عملية: 1) حدّد الشيء الأكثر إلحاحًا الآن، 2) اختر خطوة مدتها 10 دقائق فقط، 3) بعد ما تخلصها قرر الخطوة التالية بدل ما تحمل الخطة كلها مرة وحدة. "
                "اكتب لي المشكلة بجملة واحدة وأبني لك الخطة عليها."
            )
        if _has(query, PANIC_AR + ("قلق", "خايف", "خوف", "متوتر", "قلبي سريع")):
            return (
                "القلق إذا ارتفع يحسسك إن كل شيء صار كثير مرة. خلنا نبطّيها شوي: ثبت رجولك على الأرض وخذ زفيرًا أطول من الشهيق. "
                "وش اللي شغّل القلق اليوم؟\n\n"
                "وإذا معه ألم صدر شديد أو صعوبة شديدة في التنفس أو إغماء، لا نحسبه قلق وبس—اتصل بـ997."
            )
        if _has(query, ("حزين", "حزن", "مزاج منخفض", "ضايق", "ضيقة", "مكتئب", "انهار", "منهار")):
            return (
                "يبان إن اليوم ثقيل عليك 🤍 وما يحتاج تكون مرتب أو قوي هنا. إذا ودك، قل لي وش أكثر شيء وجعك أو ضغط عليك اليوم—وأسمعك من هناك. "
                "إذا هذا الشعور مستمر من فترة ومأثر على يومك بشكل واضح، وقتها يستاهل تاخذ دعم من مختص كمان."
            )
        if _has(query, ("ضغط", "مضغوط", "توتر", "مرهق", "ارهاق", "إرهاق", "احتراق", "منضغط", "جامعة", "اختبار", "دوام", "شغل")):
            return (
                "الضغط إذا تكوّم فوق بعض يخلي حتى الأشياء الصغيرة ثقيلة. خلنا ما نحاول نحل كل شيء مرة وحدة—وش أكثر شيء مستنزفك اليوم؟ "
                "إذا تبغى، نرتبه سوا."
            )
        if _has(query, ("ما اقدر انام", "ما أقدر أنام", "ارق", "أرق", "نوم", "اصحى كثير", "أصحى كثير", "كوابيس")):
            return (
                "إذا النوم ما جاء، كل شيء يصير أثقل شوي. ما راح أعطيك قائمة طويلة؛ بس قل لي: المشكلة إنك ما تقدر تبدأ تنام، ولا تنام وبعدها تصحى كثير؟ "
                "إذا الموضوع مستمر ومأثر على يومك، يستاهل تناقشه مع مختص."
            )
        if _has(query, ("افكاري كثيرة", "أفكاري كثيرة", "تفكير كثير", "افكار متزاحمة", "أفكار متزاحمة", "ما اقدر اوقف التفكير", "ما أقدر أوقف التفكير", "اوسوس", "أوسوس")):
            return (
                "خلنا نطلع الأفكار من راسك وحدة وحدة بدل ما تلف كلها مع بعض. اكتب لي أكثر فكرة قاعدة ترجع لك، حتى لو تحسها بسيطة أو ملخبطة—ما راح أحكم."
            )
        if _has(query, ("وحيد", "وحده", "وحدة", "ما عندي احد", "ما عندي أحد", "محد يفهمني", "مافي احد", "ما في أحد")):
            return (
                "الوحدة ثقيلة، خصوصًا لما تحس إن محد فاهمك. أنا أسمعك هنا، وإذا فيه شخص آمن قريب منك حاول ما تشيلها لحالك. "
                "وش خلا الإحساس قوي اليوم؟"
            )
        if _has(query, ("عصبي", "معصب", "غضب", "منفعل", "عصبية", "ابغى اكسر", "ابي اكسر")):
            return (
                "واضح إن الغضب واصل معك لآخره. قبل أي رد أو رسالة، خذ لك دقيقة بعيد عن الموقف بس عشان ما يزيد الموضوع. "
                "وش صار بالضبط؟"
            )
        if _has(query, ("انفصال", "فراق", "تركني", "تركتني", "علاقة", "مشكلة مع", "خلاف")):
            return (
                "مشاكل العلاقات أو الفقد ممكن تستنزفك حتى لو كنت تحاول تبان طبيعي. حاول اليوم تفصل بين اللي حدث وبين قيمتك أنت كشخص، وخذ قرارك الكبير بعد ما يهدأ اندفاع اللحظة. "
                "هل تحتاج الآن أحد يسمعك، أو تبغى نرتب الأفكار حول اللي حصل؟"
            )
        if _has(query, ("وفاة", "مات", "توفى", "فقدت", "حزن على", "اشتقت له", "اشتقت لها")):
            return (
                "الفقد موجع وما له طريقة واحدة «صحيحة» للحزن. حاول تعطي نفسك مساحة للمشاعر بدون ضغط أنك لازم تتحسن بسرعة، وخلك قريبًا من شخص ترتاح له إذا قدرت. "
                "وش أكثر لحظة أو شيء صار صعب عليك اليوم؟"
            )
        if _has(query, ("اكره نفسي", "أكره نفسي", "فاشل", "فاشلة", "مالي قيمة", "ما لي قيمة", "لوم نفسي", "جلد ذات")):
            return (
                "لما يكون صوت النقد الداخلي عالي، يصير الحكم على نفسك أقسى من الواقع. جرّب تصف اللي حصل كأنك تتكلم عن شخص تحبه بدل ما تحكم على نفسك بكلمة واحدة. "
                "وش الشيء اللي تلوم نفسك عليه الآن؟"
            )
        return (
            "خذ راحتك 🤍 قولها مثل ما هي، حتى لو الكلام ملخبط. تبغى بس أسمعك، ولا تبغى نرتبها سوا؟"
        )

    if _has(query, SOCIAL_ANXIETY_EN):
        return (
            "Social situations can make your attention turn inward, as if every word is being graded. Try one smaller goal instead of 'I must look completely confident': stay in one short interaction and put your attention on the other person or topic. "
            "What is hardest for you: speaking, groups, or fear of being judged?"
        )
    if _has(query, PROCRASTINATION_EN):
        return (
            "When things pile up, starting can feel harder than the task itself. Make it a 10-minute start: open the task, choose the smallest visible piece, and work on only that for 10 minutes. "
            "Tell me what is piled up and I can break it into the first three small steps."
        )
    if _has(query, INTRUSIVE_EN):
        return (
            "Trying to force an unwanted thought away can make it feel louder. Label it as 'an unwanted thought, not a fact or command,' then bring your attention back to something concrete around you. "
            "Is the content of the thought more distressing, or the fact that it keeps returning?"
        )
    if _has(query, DECISION_EN):
        return (
            "You do not need a perfectly certain decision. Put the two main options side by side and write one benefit, one cost, and one thing you could reverse for each. "
            "What decision are you stuck on?"
        )
    if _has(query, BOUNDARY_EN):
        return (
            "Saying no does not have to sound harsh. A short line like 'I can't commit to that right now' can be enough without a long explanation. "
            "If you tell me the situation, I can help you word a boundary without escalating it."
        )
    if _has(query, PLAN_EN):
        return (
            "Let's make it practical: 1) name the most urgent problem, 2) choose one 10-minute action, 3) decide the next step only after that one is done. "
            "Give me the problem in one sentence and I can build the plan around it."
        )
    if _has(query, PANIC_EN + ("anxious", "anxiety", "worried", "scared")):
        return (
            "Anxiety or panic can feel frightening. For now, plant your feet on the floor and make your exhale a little slower than your inhale, or try the 5-4-3-2-1 grounding exercise. "
            "What feels strongest right now: a scary thought, a situation, or a body sensation?\n\n"
            "If you have severe chest pain, severe breathing difficulty, fainting, or a strong new physical symptom, do not assume it is only anxiety—call 997."
        )
    if _has(query, ("sad", "sadness", "low mood", "depressed", "down", "hopeless")):
        return (
            "It sounds heavy right now. You do not need to organize everything before talking, and it is okay to make today smaller rather than solve everything at once. "
            "Did this start after something specific, or has it been building for a while?\n\n"
            "If it persists or is clearly affecting sleep, work/study, or daily life, consider speaking with a mental-health professional."
        )
    if _has(query, ("stress", "stressed", "overwhelmed", "burned out", "burnt out", "exam", "work pressure", "study pressure")):
        return (
            "When pressure piles up, everything can start to feel urgent. Pick just one next move: one small task, one thing to postpone, or ten minutes of real rest. "
            "What part of the pressure is draining you the most today?"
        )
    if _has(query, ("sleep", "insomnia", "can't sleep", "cannot sleep", "waking up", "nightmare")):
        return (
            "Poor sleep can make thoughts and stress feel louder. Tonight, do not force sleep: dim the lights, reduce stimulation, and use gentle breathing without breath-holding. "
            "Is the main issue falling asleep, or waking repeatedly?\n\n"
            "If it persists or affects your days, consider discussing it with a professional."
        )
    if _has(query, ("racing thoughts", "too many thoughts", "can't stop thinking", "cannot stop thinking", "overthinking")):
        return (
            "When thoughts race, trying to solve all of them at once usually adds pressure. Write the most persistent thought in one sentence, then sort it into: something I can act on now / something I cannot control right now. "
            "Which thought keeps returning the most?"
        )
    if _has(query, ("lonely", "alone", "no one understands me", "nobody understands")):
        return (
            "Loneliness can hurt, especially when explaining it feels difficult. If there is one safe person you trust, a simple message like “I need someone to listen for a bit” is enough to start. "
            "Has this loneliness followed something specific, or has it been there for a while?"
        )
    if _has(query, ("angry", "anger", "furious", "rage", "irritated")):
        return (
            "Anger often reaches the body before your thoughts catch up. If you can, step away for a few minutes, unclench your jaw and hands, and slow your exhale before replying or sending a message. "
            "What happened just before the anger rose?"
        )
    if _has(query, ("breakup", "relationship", "argument", "conflict", "left me")):
        return (
            "Relationship conflict or loss can be exhausting even when you are trying to function normally. Try not to make your biggest decision at the peak of the emotion. "
            "Would it help more to be heard right now, or to sort through what happened step by step?"
        )
    if _has(query, ("grief", "died", "death", "lost someone", "bereavement")):
        return (
            "Grief does not have one correct timeline or shape. Give yourself room for the feeling without forcing yourself to be okay quickly, and stay connected with someone safe if you can. "
            "What has felt hardest today?"
        )
    if _has(query, ("hate myself", "failure", "worthless", "self blame", "blame myself")):
        return (
            "When your inner critic is loud, it can turn one painful event into a judgment about your whole worth. Try describing what happened as if you were speaking about someone you care about instead of labeling yourself. "
            "What are you blaming yourself for right now?"
        )
    return (
        "Take your time 🤍 Say it however it comes out. Do you want me to mostly listen, or help you sort it out?"
    )


def quick_tools(lang: str = "ar") -> List[Dict[str, str]]:
    if lang == "en":
        return [
            {"key": "calm", "label": "🌿 Calm breathing"},
            {"key": "ground", "label": "🧭 5-4-3-2-1 grounding"},
            {"key": "urgent", "label": "🚨 I need urgent support"},
        ]
    return [
        {"key": "calm", "label": "🌿 تنفس هادئ"},
        {"key": "ground", "label": "🧭 تثبيت 5-4-3-2-1"},
        {"key": "urgent", "label": "🚨 أحتاج دعمًا عاجلًا"},
    ]
