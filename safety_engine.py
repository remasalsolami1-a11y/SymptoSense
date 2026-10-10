"""Deterministic pre-analysis safety engine.

Runs before symptom matching/generative features. It only detects a narrow set of
high-concern red-flag patterns and never diagnoses a disease.
"""
from __future__ import annotations

import re

import clinical_text
import context_triage
import emergency_lexicon

ENGINE_VERSION = "deterministic-red-flag-v4-precision"

# --- V197: Gulf-dialect / colloquial coverage -------------------------------
# All phrases are matched through clinical_text, which normalises hamza, taa
# marbuta, alef maqsura and diacritics and is negation-aware, so spelling
# variants only need to be listed once.

_SEVERE_CHEST_EXTRA = (
    "ألم شديد في صدري", "الم قوي في صدري", "وجع شديد في صدري", "وجع قوي في صدري",
    "صدري يعورني مرة", "صدري يعورني كثير", "صدري يعورني بقوة",
    "صدري يوجعني مرة", "صدري يوجعني كثير", "صدري يوجعني بقوة",
    "crushing chest pressure", "crushing pressure in my chest",
    "ضغط قوي على صدري", "ضغط شديد على صدري", "ضغط قوي على الصدر",
    "كأن شي جاثم على صدري", "كان احد جالس على صدري", "حجر على صدري",
    "intense chest pain", "chest pain is severe", "severe pain in my chest",
    "elephant on my chest",
)
_CHEST_ANY = (
    "ألم في الصدر", "الم بالصدر", "ألم بالصدر", "وجع في الصدر", "وجع بالصدر", "ألم صدر",
    "ضغط في الصدر", "ضغط على الصدر", "ثقل في الصدر", "ثقل على الصدر", "انقباض في الصدر",
    "صدري يعورني", "صدري يوجعني", "يعورني صدري", "يوجعني صدري",
    "chest pain", "chest pressure", "chest tightness", "tightness in my chest",
    "pain in my chest", "pressure in my chest",
)
_CHEST_RADIATION = (
    "ينتشر", "يمتد", "ينزل", "يطلع", "ممتد", "منتشر",
    "الذراع الأيسر", "اليد اليسرى", "اليد اليسار", "الكتف الأيسر", "الفك",
    "spreading", "spreads", "radiating", "radiates", "left arm", "jaw",
    "down my arm", "into my arm", "to my arm",
)
_SWEATING = ("عرق بارد", "تعرق", "اتعرق", "أتعرق", "عرقان", "sweating", "cold sweat", "sweaty")

_BREATHING_EXTRA = (
    "نفسي مقطوع", "مقطوع نفسي", "نفسي ضايق مرة", "ما اقدر اخذ نفس", "ما أقدر آخذ نفس",
    "ما اقدر آخذ نفسي", "ما اقدر اخذ نفسي", "مو قادر اتنفس", "ماني قادر اتنفس", "مب قادر اتنفس",
    "نفسي ضايق جدا", "نفسي ضايق جدًا", "نفسي ضايق كثير", "can't breathe", "cant breathe", "can barely breathe", "cannot get air",
    "احس اني اختنق", "أحس إني أختنق", "اختنق", "ما اقدر اشهق",
    "gasping for air", "can't catch my breath", "cannot catch my breath", "unable to breathe",
    "not able to breathe", "choking",
)
_BREATHING_MILD = (
    "ضيق تنفس", "ضيق في التنفس", "ضيق التنفس", "صعوبة تنفس", "صعوبة في التنفس", "صعوبة التنفس",
    "صعب اتنفس", "صعب علي اتنفس", "صعب علي التنفس", "ما اقدر اتنفس", "ما أقدر أتنفس",
    "shortness of breath", "difficulty breathing", "trouble breathing", "can't breathe", "cannot breathe",
)

_UNCONSCIOUS_EXTRA = (
    "فاقد الوعي", "فاقدة الوعي", "فقد الوعي", "غاب عن الوعي", "غايب عن الوعي",
    "اغمي علي", "أغمي علي", "اغمى علي", "فقدت الوعي", "فقدت وعيي", "غبت عن الوعي",
    "مغمى عليه", "مغمى عليها", "مغمي عليه", "مغمي عليها", "أغمي عليه", "اغمي عليها",
    "collapsed",
)
_UNRESPONSIVE_EXTRA = (
    "طاح وما يرد", "طاح ومايرد", "طاحت وما ترد", "طاحت ومابترد", "طاح وما يتحرك",
    "طاح على الأرض وما يتحرك", "ما يتجاوب", "مايتجاوب", "ما تتجاوب", "ما يفتح عيونه",
    "not responding", "does not respond", "doesn't respond", "passed out and not waking",
    "collapsed and not responding",
)

_STROKE_LIMB_EXTRA = (
    "لا اقدر احرك يدي", "لا أقدر أحرك يدي", "لا استطيع تحريك يدي", "لا اقدر احرك رجلي", "لا أقدر أحرك رجلي",
    "ما اقدر احرك يدي", "ما أقدر أحرك يدي", "ما اقدر احرك رجلي", "ما أقدر أحرك رجلي",
    "ما اقدر احرك ذراعي", "ما أقدر أحرك ذراعي", "ما اقدر احرك نص جسمي", "ما اقدر احرك النص",
    "يدي ما تتحرك", "رجلي ما تتحرك", "نص جسمي مخدر", "نص جسمي ضعيف", "نصف جسمي مخدر",
    "خدر في نص الوجه", "تنميل في نص الوجه", "خدر في نص جسمي", "تنميل في نص جسمي",
    "sudden weakness in my arm", "sudden weakness in my leg", "sudden weakness in my face",
    "sudden numbness in my face", "sudden numbness in my arm", "sudden numbness in my leg",
    "can't move my arm", "cannot move my arm", "can't move my leg", "cannot move my leg",
    "can't lift my arm", "cannot lift my arm", "weakness on one side of my body",
)
_STROKE_FACE_SPEECH_EXTRA = (
    "فمي مايل", "فمه مايل", "فمها مايل", "وجهي مايل", "وجهه مايل", "وجهها مايل", "الوجه مايل",
    "ميلان الوجه", "ميلان في الوجه", "ميلان بالوجه", "ميلان الفم", "تدلي الفم", "التواء الوجه",
    "التواء الفم", "انحراف الفم", "انحراف الوجه", "اعوجاج الفم",
    "كلامي ثقيل فجأة", "كلامي صار ثقيل", "كلامه صار ثقيل", "لساني ثقيل فجأة", "كلامي متلخبط",
    "ما اقدر اتكلم", "ما أقدر أتكلم", "ما يقدر يتكلم", "كلامي مو واضح فجأة", "كلامي غير واضح فجأة",
    "face is drooping", "my face is drooping", "drooping face", "facial droop", "mouth drooping",
    "mouth is drooping", "speech is slurred", "can't speak", "cannot speak", "sudden confusion speaking",
)

_BLEEDING_EXTRA = (
    "نزيف كثير", "ينزف دم كثير", "دم كثير ينزف", "دم كثير", "الدم ما يوقف", "الدم مايوقف",
    "دمه ما يوقف", "دمها ما يوقف", "ما يوقف الدم", "ما يوقف النزيف", "نزيف ما يوقف", "ينزف ومايوقف",
    "ينزف وما يوقف",
    "heavy bleeding", "bleeding a lot", "blood won't stop", "can't stop the bleeding",
    "cannot stop the bleeding", "losing a lot of blood",
)
_BLOOD_VOMIT_COUGH = (
    "ارجع دم", "يرجع دم", "ترجيع دم", "استفرغ دم", "يستفرغ دم", "قيء دم", "قيء دموي",
    "اتقيا دم", "يتقيا دم", "اكح دم", "يكح دم", "كحة دم", "سعال دم", "سعال دموي",
    "vomiting blood", "vomited blood", "throwing up blood", "coughing up blood",
    "coughing blood", "blood in vomit",
)

_SWELLING_EXTRA = (
    "تورم في الحلق", "تورم في اللسان", "تورم في الشفايف", "تورم في الشفاه", "تورم الوجه", "تورم في الوجه",
    "انتفاخ في الحلق", "انتفاخ الحلق", "انتفاخ في اللسان", "انتفاخ الوجه",
    "حلقي منتفخ", "لساني منتفخ", "شفايفي منتفخة", "وجهي منتفخ", "وجهه منتفخ", "حلقي يضيق", "حلقي مسكر",
    "tongue swelling", "lip swelling", "swollen throat", "swollen face", "face swelling",
    "throat tightness", "throat closing", "throat is closing",
)

_SEIZURE_PROLONGED_EXTRA = ("تشنج ما يوقف", "التشنج ما يوقف", "تشنجه ما يوقف")

_SELF_HARM_EXTRA = (
    "أفكر في الانتحار", "افكر انتحر", "أفكر أنهي حياتي", "افكر انهي حياتي", "أنهي حياتي", "انهي حياتي",
    "إنهاء حياتي", "انهاء حياتي", "أفكر في إنهاء حياتي", "انوي الانتحار", "أبي أقتل نفسي", "ابغى اقتل نفسي",
    "اتمنى اموت", "أتمنى لو أموت",
    "ودي اختفي من الدنيا", "ودي أختفي من الدنيا", "ابي اختفي من الدنيا", "ابي أختفي من الدنيا",
    "اختفي من الحياة", "أختفي من الحياة",
    "أفكر أأذي نفسي", "افكر اأذي نفسي", "ابي اأذي نفسي", "ابي أأذي نفسي", "أبي أأذي نفسي",
    "want to disappear from", "ending it all", "ending my life", "tired of life", "hurt myself",
    "suicidal", "thinking of suicide", "think about suicide", "commit suicide", "want to die", "wanna die",
    "wish i was dead", "wish i were dead", "end my life", "end it all", "take my own life", "better off dead",
    "no reason to live", "don't want to live", "do not want to live",
)
# "ابي اموت" / "ودي انتحر": handled by regex so that "ما ابي اموت" (I don't want
# to die) and the idiom "ابي اموت من الضحك/الجوع" do not trigger.
_SELF_HARM_AR_RE = re.compile(
    r"(?<![\u0600-\u06ff])(?<!ما )(?<!مو )(?<!ماني )(?<!مب )"
    r"(?:ابي|ابغي|ابغى|ودي|بغيت|اريد|ابا)\s+(?:ان\s+)?"
    r"(?:اموت|انتحر|اقتل نفسي|انهي حياتي|اخلص حياتي|اقتل روحي)"
    r"(?!\s+من\s)(?![\u0600-\u06ff])"
)

_OVERDOSE_EXTRA = (
    "بلعت حبوب كثير", "بلعت حبوب كثيرة", "اخذت حبوب كثير", "أخذت حبوب كثيرة", "شربت حبوب كثيرة",
    "تناولت حبوب كثيرة", "بلعت علبة حبوب", "بلعت علبة دواء", "اخذت علبة حبوب", "اخذت علبة دواء كاملة",
    "بلعت كل الحبوب", "اخذت كل الحبوب", "اخذت كمية كبيرة من الدواء", "تناولت كمية كبيرة من الدواء",
    "شرب مادة سامة", "شربت مادة سامة", "بلع مادة سامة", "بلعت مادة سامة", "ابتلع مادة سامة",
    "شرب كلور", "شربت كلور", "شرب منظف", "شربت منظف", "بلع منظف", "بلعت منظف", "شرب بنزين",
    "شرب مبيد", "شربت مبيد", "بلع بطارية", "بلعت بطارية", "شرب سم", "شربت سم",
    "الطفل بلع حبوب", "طفلي بلع حبوب", "ابني بلع حبوب", "بنتي بلعت حبوب", "ولدي بلع حبوب",
    "took too many pills", "took too many tablets", "swallowed too many pills", "swallowed a lot of pills",
    "took a lot of pills", "swallowed bleach", "drank bleach", "drank poison", "ingested poison",
    "swallowed something toxic", "my child swallowed pills", "swallowed a battery",
)

_THUNDERCLAP_HEADACHE = (
    "أسوأ صداع في حياتي", "اسوأ صداع مريت فيه", "أقوى صداع في حياتي", "صداع مفاجئ شديد",
    "صداع مفاجئ وقوي", "صداع شديد ومفاجئ", "صداع شديد مفاجئ", "صداع قوي ومفاجئ", "صداع شديد جدا ومفاجئ", "صداع قوي فجأة", "صداع مثل الصاعقة",
    "worst headache of my life", "worst headache ever", "thunderclap headache",
    "sudden severe headache", "sudden worst headache",
)

_PREGNANCY = ("حامل", "حاملة", "أثناء الحمل", "اثناء الحمل", "في الحمل", "pregnant", "during pregnancy")
_PREG_BLEED = (
    "نزيف", "نزول دم", "ينزل دم", "ينزل علي دم", "ينزلني دم", "دم من المهبل",
    "bleeding", "vaginal bleeding", "blood loss",
)
_PREG_BLEED_EXCLUDE_RE = re.compile(r"(?<![\u0600-\u06ff])(?:انف|الانف|لثه|اللثه)(?![\u0600-\u06ff])|\b(?:nose|nosebleed|gum|gums)\b")

_INFANT = (
    "رضيع", "رضيعي", "مولود", "حديث الولادة", "newborn", "neonate", "infant",
    "weeks old", "week old", "days old", "day old",
    "عمره أسبوع", "عمره اسبوعين", "عمرها أسبوع", "عمرها اسبوعين", "عمره أيام", "عمرها أيام",
    "عمره شهر", "عمره شهرين", "عمرها شهر", "عمرها شهرين",
)
_FEVER = (
    "حرارة", "حرارته", "حرارتها", "حمى", "سخونة", "سخونته", "محموم",
    "fever", "high temperature", "febrile",
)

# V198: emergency precision.  These markers prevent a single ambiguous phrase
# from bypassing the adaptive questions.  Immediate red alerts are reserved for
# clearly current/high-risk patterns; unclear neurological, pregnancy-bleeding,
# infant-fever and bare seizure reports continue to the clinical triage layer.
_ACUTE_NEURO = (
    "فجأة", "مفاجئ", "مفاجئة", "بشكل مفاجئ", "توها بدأت", "توه بدأ", "بدأ الآن", "بدات الآن",
    "الآن", "الان", "حاليا", "حاليًا", "من شوي", "قبل قليل",
    "sudden", "suddenly", "just started", "started now", "right now", "currently",
)
_CHRONIC_NEURO = (
    "من سنوات", "من سنين", "من زمان", "من فترة طويلة", "مزمن", "مزمنة", "منذ سنوات",
    "for years", "for months", "long-standing", "longstanding", "chronic",
)
_MECHANICAL_LIMB_CONTEXT = (
    "بسبب الجبس", "من الجبس", "عليه جبس", "عليها جبس", "بعد كسر", "بسبب كسر",
    "بعد إصابة", "بعد اصابة", "بسبب إصابة", "بسبب اصابة",
    "because of a cast", "in a cast", "after a fracture", "because of an injury",
)
_PREG_IMMEDIATE = (
    "نزيف شديد", "نزيف غزير", "ينزف كثير", "الدم ما يوقف", "الدم مايوقف",
    "ألم شديد في البطن", "الم شديد في البطن", "ألم بطن شديد", "الم بطن شديد",
    "ألم شديد أسفل البطن", "الم شديد اسفل البطن", "ألم في الكتف", "الم في الكتف",
    "دوخة شديدة", "أشعر بالإغماء", "اشعر بالاغماء", "راح يغمى علي", "راح يغمى عليا",
    "heavy bleeding", "bleeding heavily", "severe abdominal pain", "severe tummy pain",
    "shoulder pain", "feel faint", "feeling faint", "severe dizziness",
)

# Spasm of a named body part is not a seizure: "تشنج في الساق", "عضلاتي تتشنج".
_BODY = r"(?:عضل|ساق|قدم|رجلي|رجله|رجلها|ظهر|رقب|معد|قولون|فك|اصابع|يد|بطن|كتف|حيض|دور|اسنان)"
_SEIZURE_AR = ("تشنجات", "تشنج", "يتشنج", "تتشنج", "اختلاج", "اختلاجات", "نوبة تشنجية")
_MUSCLE_SPASM_RES = (
    re.compile(r"(?:تشنج\w*|اختلاج\w*)\s+(?:في\s+|ب)?(?:ال)?" + _BODY + r"\w{0,3}(?![\u0600-\u06ff])"),
    re.compile(r"(?<![\u0600-\u06ff])" + _BODY + r"\w{0,3}\s+[يت]تشنج"),
)


def _arabic_bare_seizure(text):
    """True for a bare Arabic seizure word that is not a muscle spasm."""
    normalized = clinical_text.normalize_clinical_text(text)
    for clause in normalized.split("|"):
        clause = clause.strip()
        if not clause:
            continue
        if any(rx.search(clause) for rx in _MUSCLE_SPASM_RES):
            continue
        if clinical_text.contains_unnegated_any(clause, _SEIZURE_AR):
            return True
    return False


def _arabic_active_convulsion(text):
    """Detect present-tense whole-body convulsion language without body-part spasms."""
    normalized = clinical_text.normalize_clinical_text(text)
    for clause in normalized.split("|"):
        clause = clause.strip()
        if not clause or any(rx.search(clause) for rx in _MUSCLE_SPASM_RES):
            continue
        if re.search(r"(?<![\u0600-\u06ff])(?:يتشنج|تتشنج|يختلج|تختلج)(?![\u0600-\u06ff])", clause):
            return True
    return False


def _arabic_self_harm(text):
    normalized = clinical_text.normalize_clinical_text(text)
    for clause in normalized.split("|"):
        if _SELF_HARM_AR_RE.search(clause.strip()):
            return True
    return False


def evaluate(patient, lang="ar"):
    """Evaluate a narrow set of high-concern red flags before normal analysis.

    This is intentionally deterministic and conservative.  It never diagnoses a
    disease; it only decides whether the normal symptom-matching flow should stop
    in favor of urgent-care guidance.
    """
    symptoms = [str(x) for x in (patient.get("symptoms") or [])]
    notes = str(patient.get("notes") or "")
    text = " ; ".join(symptoms + [notes])

    def anyp(*phrases):
        return clinical_text.contains_unnegated_any(text, phrases)

    flags = []
    rule_ids = []

    def add(rule_id, ar, en):
        label = en if lang == "en" else ar
        if label not in flags:
            flags.append(label)
        if rule_id not in rule_ids:
            rule_ids.append(rule_id)

    if anyp(
        "ألم شديد في الصدر", "الم شديد في الصدر", "ألم صدر شديد", "ألم شديد بالصدر", "الم شديد بالصدر",
        "ضغط شديد في الصدر", "ضغط شديد بالصدر", "ألم قوي في الصدر", "وجع صدر شديد",
        "severe chest pain", "crushing chest pain", "severe chest pressure",
        "squeezing chest pain", "chest feels tight or heavy",
        *_SEVERE_CHEST_EXTRA,
    ):
        add("severe_chest_pain", "ألم أو ضغط شديد في الصدر", "Severe chest pain or pressure")

    if anyp(
        "ضيق شديد في التنفس", "ضيق تنفس شديد", "صعوبة شديدة في التنفس", "صعوبة تنفس شديدة", "لا أستطيع التنفس",
        "لا استطيع التنفس", "ما اقدر اتنفس", "ما أقدر أتنفس", "اختناق شديد",
        "لا أقدر أتنفس", "لا اقدر اتنفس", "لا اقدر أتنفس", "لا أقدر اتنفس",
        "severe shortness of breath", "severe difficulty breathing", "can't breathe",
        "cannot breathe", "struggling to breathe",
        *_BREATHING_EXTRA,
    ):
        add("severe_breathing", "صعوبة شديدة في التنفس", "Severe breathing difficulty")

    if anyp(*_CHEST_ANY) and (anyp(*_CHEST_RADIATION) or anyp(*_SWEATING) or anyp(*_BREATHING_MILD)):
        add("chest_pain_cardiac_features", "ألم في الصدر مع انتشار أو تعرق أو ضيق تنفس",
            "Chest pain with spreading, sweating or breathlessness")

    # Current unresponsiveness is an emergency. A bare report of loss of
    # consciousness is treated as current/uncertain unless the same text clearly
    # says the episode happened earlier and the person recovered; resolved fainting
    # is handled as same-day review by the clinical triage layer instead.
    _lower_text = text.lower()
    _resolved_faint = any(mark in _lower_text for mark in (
        "قبل ساعة", "قبل ساعت", "قبل يوم", "أمس", "امس", "earlier", "yesterday",
        "والآن طبيعي", "والان طبيعي", "صحيت", "استعدت الوعي", "recovered", "awake now", "now fine",
    )) and not any(mark in _lower_text for mark in (
        "الآن", "الان", "حاليا", "حاليًا", "now", "currently", "لا يستجيب", "ما يستجيب",
        "لا يصحى", "ما يصحى", "unresponsive", "not waking", "won't wake",
    ))
    _resolved_faint = _resolved_faint or emergency_lexicon.resolved_past(text)
    if anyp(
        "فاقد الوعي الآن", "الآن فاقد الوعي", "فاقد الوعي حاليا", "حاليا فاقد الوعي", "حاليًا فاقد الوعي",
        "فقد الوعي ولم يستيقظ", "فقد الوعي وما صحى",
        "لا يستجيب", "ما يستجيب", "لا يصحى", "ما يصحى", "لم يستيقظ",
        "unconscious now", "now unconscious", "currently unconscious", "unresponsive", "won't wake up",
        "will not wake up", "not waking up", "lost consciousness and has not woken",
        *_UNRESPONSIVE_EXTRA,
    ) or (not _resolved_faint and anyp("فقدان الوعي", "loss of consciousness", "unconscious", *_UNCONSCIOUS_EXTRA)):
        add("loss_of_consciousness", "فقدان وعي حالي أو غير محدد الزمن / عدم استجابة", "Current or time-unspecified loss of consciousness / unresponsiveness")

    one_side = anyp(
        "ضعف في جانب", "ضعف جهة واحدة", "ضعف في جهة واحدة", "ضعف مفاجئ في جهة واحدة", "ضعف مفاجئ في جهة واحدة من الجسم", "تنميل في جانب",
        "خدر في جانب", "ضعف مفاجئ في يد", "ضعف مفاجئ في رجل", "ضعف مفاجئ بالطرف", "ضعف مفاجئ في الطرف",
        "ضعف مفاجئ بالذراع", "ضعف مفاجئ في الذراع", "ضعف مفاجئ بالساق", "ضعف مفاجئ في الساق",
        "weakness on one side", "numbness on one side", "one-sided weakness", "sudden arm weakness", "sudden leg weakness", "sudden limb weakness",
        *_STROKE_LIMB_EXTRA,
    )
    speech_face = anyp(
        "صعوبة مفاجئة في الكلام", "صعوبة في الكلام", "تلعثم مفاجئ", "تدلي الوجه",
        "اعوجاج الوجه", "slurred speech", "sudden trouble speaking", "face drooping",
        *_STROKE_FACE_SPEECH_EXTRA,
    )
    if speech_face and emergency_lexicon.speech_is_explained(text):
        # "I can't talk much because my throat is inflamed" is not a stroke sign.
        speech_face = anyp("فمي مايل", "وجهي مايل", "ميلان الوجه", "التواء الوجه", "اعوجاج الوجه", "تدلي الوجه", "face drooping", "face is drooping")
    acute_neuro = anyp(*_ACUTE_NEURO)
    chronic_neuro = anyp(*_CHRONIC_NEURO)
    mechanical_limb = anyp(*_MECHANICAL_LIMB_CONTEXT)
    # Do not turn a single ambiguous/chronic/mechanical phrase into an ambulance
    # alert.  A clearly sudden/current FAST feature, or two focal FAST features
    # together, still bypasses immediately.
    stroke_emergency = False
    if not chronic_neuro:
        # FAST-type focal deficits remain immediate unless the text explicitly
        # gives a mechanical explanation (for example a cast/fracture).  The
        # chronic marker prevents long-standing facial/limb findings from being
        # mislabelled as a new stroke.
        if speech_face:
            stroke_emergency = True
        elif one_side and not mechanical_limb:
            stroke_emergency = True
    if stroke_emergency:
        add("stroke_pattern", "أعراض عصبية مفاجئة قد توافق نمط السكتة الدماغية", "Sudden focal neurological symptoms that may match a stroke pattern")

    if anyp(
        "فقدان مفاجئ للرؤية", "فقدان مفاجئ للنظر", "suddenly cannot see", "suddenly can't see", "cannot see suddenly", "ما اشوف فجأة", "ما أشوف فجأة",
        "sudden vision loss", "suddenly lost vision",
    ):
        add("sudden_vision_loss", "فقدان مفاجئ للرؤية", "Sudden vision loss")

    if anyp(
        "نزيف شديد", "نزيف لا يتوقف", "دم لا يتوقف", "ينزف كثير", "نزيف غزير",
        "severe bleeding", "uncontrollable bleeding", "bleeding heavily", "won't stop bleeding",
        *_BLEEDING_EXTRA,
    ):
        add("severe_bleeding", "نزيف شديد أو غير متوقف", "Severe or uncontrolled bleeding")

    if anyp(*_BLOOD_VOMIT_COUGH):
        add("blood_vomit_or_cough", "قيء دموي أو سعال مصحوب بدم", "Vomiting or coughing up blood")

    swelling = anyp(
        "تورم اللسان", "تورم الشفاه", "تورم الحلق", "انتفاخ اللسان", "انتفاخ الشفايف",
        "swollen tongue", "swollen lips", "throat swelling",
        *_SWELLING_EXTRA,
    )
    breathing = anyp(
        "ضيق التنفس", "صعوبة التنفس", "ما اقدر اتنفس", "ما أقدر أتنفس",
        "shortness of breath", "difficulty breathing", "can't breathe", "cannot breathe",
        *_BREATHING_MILD, *_BREATHING_EXTRA,
    )
    historical_allergy = any(mark in text.lower() for mark in (
        "تاريخ حساسية", "حساسية مفرطة قبل", "قبل سنتين", "قبل سنة", "منذ سنتين", "منذ سنة",
        "history of anaphylaxis", "anaphylaxis two years ago", "previous anaphylaxis", "past anaphylaxis",
    )) and not any(mark in text.lower() for mark in (
        "الآن", "الان", "حاليا", "حاليًا", "اليوم", "now", "currently", "today",
    ))
    if swelling and breathing and not historical_allergy:
        add("anaphylaxis_pattern", "تورم بالفم/الحلق مع صعوبة تنفس", "Mouth/throat swelling with breathing difficulty")

    if anyp(
        "تشنج مستمر", "نوبة تشنج طويلة", "نوبة تشنجية مستمرة", "النوبة التشنجية مستمرة",
        "نوبة تشنجية ما توقفت", "النوبة ما وقفت", "تشنجات مستمرة", "ما وقف التشنج",
        "prolonged seizure", "seizure won't stop", "continuous seizure",
        *_SEIZURE_PROLONGED_EXTRA,
    ):
        add("prolonged_seizure", "تشنج مستمر أو نوبة مطولة", "Prolonged or ongoing seizure")

    # A clearly current seizure/convulsion is time-sensitive.  V198 deliberately
    # does NOT treat a bare word such as "تشنج / seizure" as an ambulance-level
    # emergency; the adaptive flow may clarify whether it is happening now, was
    # prolonged, was a first seizure, or was simply a muscle spasm.
    _t = text.lower()
    _past_resolved_seizure = any(mark in _t for mark in (
        "أمس", "امس", "قبل ساعة", "قبل ساعت", "قبل يوم", "من يوم", "انتهى", "انتهت",
        "والآن طبيعي", "والان طبيعي", "earlier", "yesterday", "ended", "resolved", "now fine",
    )) and not any(mark in _t for mark in (
        "الآن", "الان", "حاليا", "حاليًا", "now", "currently", "won't stop", "مستمر", "مستمرة",
    ))
    if (anyp(
        "عندي تشنج الآن", "عندي تشنجات الآن", "تشنج الآن", "تشنجات الآن",
        "نوبة تشنج الآن", "نوبة تشنجية الآن", "النوبة التشنجية الآن", "اختلاج الآن", "اختلاجات الآن", "يتشنج الحين", "يتشنج الآن",
        "having a seizure", "seizure now", "seizures now", "convulsing now", "currently convulsing",
    ) or _arabic_active_convulsion(text)) and not _past_resolved_seizure:
        add("active_seizure", "تشنج أو اختلاج يحدث الآن", "Seizure or convulsion happening now")

    if anyp(
        "أفكر بالانتحار", "افكر بالانتحار", "أفكار انتحارية", "افكار انتحارية",
        "أفكر أقتل نفسي", "افكر اقتل نفسي", "أقتل نفسي", "اقتل نفسي",
        "أؤذي نفسي", "اؤذي نفسي", "إيذاء النفس", "ايذاء النفس",
        "suicidal thoughts", "thinking about suicide", "kill myself",
        "hurt myself", "self harm", "self-harm",
        *_SELF_HARM_EXTRA,
    ) or _arabic_self_harm(text):
        add("self_harm_risk", "أفكار أو نية لإيذاء النفس", "Thoughts or intent to self-harm")

    if anyp(
        "جرعة زائدة", "تناولت جرعة زائدة", "اخذت جرعة زائدة", "أخذت جرعة زائدة",
        "تسمم دوائي", "ابتلعت مادة سامة", "overdose", "drug overdose", "poisoning",
        "swallowed poison", "toxic ingestion",
        *_OVERDOSE_EXTRA,
    ):
        add("overdose_poisoning", "اشتباه جرعة زائدة أو تسمم", "Possible overdose or poisoning")

    if anyp(*_THUNDERCLAP_HEADACHE):
        add("thunderclap_headache", "صداع مفاجئ شديد جدًا (الأسوأ في الحياة)", "Sudden, worst-ever headache")

    # Pregnancy bleeding is NOT automatically an ambulance emergency.  Light or
    # unspecified bleeding continues to same-day clinical triage.  Immediate
    # bypass is reserved for bleeding with clearly high-risk accompanying signs.
    pregnancy_bleeding = (anyp(*_PREGNANCY) and anyp(*_PREG_BLEED)
            and not _PREG_BLEED_EXCLUDE_RE.search(clinical_text.normalize_clinical_text(text)))
    if pregnancy_bleeding and anyp(*_PREG_IMMEDIATE):
        add("pregnancy_bleeding_severe", "نزيف أثناء الحمل مع علامة خطر شديدة", "Bleeding during pregnancy with a severe warning sign")

    # Colloquial / dialect wording (Gulf, Hejazi, Egyptian, typos, free phrasing).
    for _rid, _ar, _en in emergency_lexicon.evaluate(text, skip_stroke=bool(chronic_neuro or mechanical_limb)):
        add(_rid, _ar, _en)

    # Context-dependent patterns (infant fever, appendicitis, pregnancy pain, DVT/PE).
    for _rid, _ar, _en in context_triage.evaluate(patient, text)["emergency"]:
        add(_rid, _ar, _en)

    # Fever in a baby is important, but temperature alone should not produce an
    # ambulance instruction here.  The clinical triage layer handles age and
    # temperature thresholds and asks for further context.

    return {
        "emergency": bool(flags),
        "flags": flags,
        "rule_ids": rule_ids,
        "engine": ENGINE_VERSION,
    }


def validation_report():
    """Run a built-in regression matrix for the deterministic safety engine."""
    cases = [
        ("ar_severe_chest", "ar", ["ألم شديد في الصدر"], "", True),
        ("ar_breathing", "ar", ["ضيق شديد في التنفس"], "", True),
        ("ar_current_unresponsive", "ar", ["فاقد الوعي الآن ولا يستجيب"], "", True),
        ("ar_resolved_faint", "ar", ["أغمي علي قبل ساعتين والآن طبيعي"], "", False),
        ("ar_stroke", "ar", ["ضعف في جهة واحدة", "صعوبة في الكلام"], "", True),
        ("ar_sudden_limb_weakness", "ar", ["ضعف مفاجئ بالطرف"], "", True),
        ("ar_vision", "ar", ["فقدان مفاجئ للرؤية"], "", True),
        ("ar_bleeding", "ar", ["نزيف لا يتوقف"], "", True),
        ("ar_allergy", "ar", ["تورم اللسان", "صعوبة التنفس"], "", True),
        ("ar_overdose", "ar", ["أخذت جرعة زائدة"], "", True),
        ("ar_active_seizure", "ar", ["عندي تشنجات الآن"], "", True),
        ("ar_self_harm", "ar", ["أفكر بالانتحار"], "", True),
        ("en_active_seizure", "en", ["having a seizure"], "", True),
        ("ar_resolved_seizure", "ar", ["صار لي تشنج أمس وانتهى"], "", False),
        ("en_self_harm", "en", ["suicidal thoughts"], "", True),
        ("en_unresponsive", "en", ["unresponsive and not waking up"], "", True),
        ("en_unconscious", "en", ["unconscious"], "", True),
        ("en_resolved_faint", "en", ["fainted earlier and I am awake now"], "", False),
        ("en_overdose", "en", ["overdose"], "", True),
        ("en_stroke", "en", ["one-sided weakness", "slurred speech"], "", True),
        ("neg_benign_clicking", "ar", ["ركبتي تطقطق بدون ألم"], "", False),
        ("neg_mild_headache", "en", ["mild headache"], "", False),
        ("neg_denied_breathing", "ar", ["صداع"], "هل لديك صعوبة شديدة في التنفس؟ -> لا", False),
        # V197 colloquial / Gulf-dialect coverage
        ("ar_bare_unconscious", "ar", ["فاقد الوعي"], "", True),
        ("ar_collapsed_not_replying", "ar", ["أخوي طاح ومايرد"], "", True),
        ("ar_bare_seizure", "ar", ["تشنج"], "", False),
        ("ar_chest_radiating", "ar", ["ألم في الصدر ينتشر لليد اليسار"], "", True),
        ("ar_colloquial_chest", "ar", ["صدري يعورني مرة"], "", True),
        ("ar_colloquial_breathing", "ar", ["نفسي مقطوع"], "", True),
        ("ar_throat_swelling_breathing", "ar", ["تورم في الحلق", "ضيق تنفس"], "", True),
        ("ar_face_droop", "ar", ["فمي مايل"], "", True),
        ("ar_cannot_move_arm", "ar", ["ما اقدر احرك يدي اليمين"], "", True),
        ("ar_colloquial_self_harm", "ar", ["ابي اموت"], "", True),
        ("ar_pill_overdose", "ar", ["بلعت حبوب كثير"], "", True),
        ("ar_pregnancy_bleeding", "ar", ["حامل ونزيف"], "", False),
        ("ar_pregnancy_bleeding_severe", "ar", ["حامل ونزيف وألم شديد في البطن"], "", True),
        ("ar_infant_fever", "ar", ["رضيع حرارته 40"], "", False),
        ("ar_thunderclap_headache", "ar", ["أسوأ صداع في حياتي"], "", True),
        ("en_took_too_many_pills", "en", ["took too many pills"], "", True),
        ("en_chest_radiating", "en", ["chest pain spreading to left arm"], "", True),
        ("neg_ar_muscle_spasm", "ar", ["تشنج في الساق"], "", False),
        ("neg_ar_idiom_die_laughing", "ar", ["ابي اموت من الضحك"], "", False),
        ("neg_ar_dont_want_to_die", "ar", ["ما ابي اموت"], "", False),
        ("neg_ar_denied_seizure", "ar", ["ما عندي تشنج"], "", False),
        ("neg_ar_nosebleed_pregnant", "ar", ["حامل ونزيف من الأنف"], "", False),
        ("neg_ar_food_poisoning", "ar", ["تسمم غذائي"], "", False),
        ("neg_ar_chest_pain_alone", "ar", ["ألم في الصدر"], "", False),
    ]
    details = []
    passed = 0
    for case_id, lang, symptoms, notes, expected in cases:
        got = bool(evaluate({"symptoms": symptoms, "notes": notes}, lang=lang).get("emergency"))
        ok = got == expected
        passed += int(ok)
        details.append({"id": case_id, "expected": expected, "actual": got, "passed": ok})
    return {
        "passed": passed,
        "total": len(cases),
        "pass_rate": round((passed * 100.0 / len(cases)), 1) if cases else 0.0,
        "all_passed": passed == len(cases),
        "engine": ENGINE_VERSION,
        "cases": details,
    }


def _self_harm_support(safety, lang):
    """Extra line for self-harm flags: Saudi MOH 937 and mental-health consultation line."""
    if "self_harm_risk" not in (safety.get("rule_ids") or []):
        return ""
    if lang == "en":
        return (" If you are thinking about harming yourself, do not stay alone: contact someone you trust now, "
                "and you can call the Ministry of Health line 937 or the mental-health consultation line 920033360.")
    return (" إذا كانت لديك أفكار لإيذاء نفسك فلا تبقَ وحدك: تواصل الآن مع شخص تثق به، "
            "ويمكنك الاتصال بالصحة 937 أو بمركز الاستشارات النفسية 920033360.")


def emergency_result(safety, lang="ar"):
    flags = list(safety.get("flags") or [])
    if lang == "en":
        return {
            "ok": True,
            "emergency": True,
            "emergency_flags": flags,
            "urgency": "high",
            "urgency_text": "Emergency",
            "confidence": "high",
            "personal_note": "A deterministic safety rule matched a red-flag symptom pattern.",
            "simple_explanation": "For safety, the symptom-matching assessment stops here. Seek urgent medical evaluation now rather than waiting for a diagnostic explanation.",
            "possible_conditions": "No condition is named because a red-flag pattern takes priority over symptom matching.",
            "recommendations": [],
            "danger_signs": "\n".join(flags),
            "when_to_seek_care": "Seek emergency care now. In Saudi Arabia, ambulance service is 997." + _self_harm_support(safety, "en"),
            "home_care": "",
            "medication_guidance": "",
            "questions_for_doctor": "",
            "safety_engine": safety,
        }
    return {
        "ok": True,
        "emergency": True,
        "emergency_flags": flags,
        "urgency": "high",
        "urgency_ar": "طوارئ",
        "confidence": "high",
        "personal_note": "طابقت قاعدة أمان مستقلة نمط علامة خطر في الأعراض المدخلة.",
        "simple_explanation": "للسلامة يتوقف تحليل الاحتمالات هنا. اطلب تقييمًا طبيًا عاجلًا الآن بدل انتظار تفسير تشخيصي.",
        "possible_conditions": "لن يُعرض اسم حالة محددة لأن علامة الخطر لها الأولوية على مطابقة الأمراض.",
        "recommendations": [],
        "danger_signs": "\n".join(flags),
        "when_to_seek_care": "اطلب الرعاية الطارئة الآن. في السعودية رقم الإسعاف 997." + _self_harm_support(safety, "ar"),
        "home_care": "",
        "medication_guidance": "",
        "questions_for_doctor": "",
        "safety_engine": safety,
    }
