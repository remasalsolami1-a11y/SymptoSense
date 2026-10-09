"""Bilingual typo-tolerant search over the curated SymptoSense knowledge base.

This engine never invents medical facts: it ranks only records already present
in medical_knowledge/health_search and returns source-grounded suggestions.
"""
from __future__ import annotations
import difflib
import re
import unicodedata
import time
from functools import lru_cache

import health_search
import medical_knowledge

_ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")
_SPACE = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s\u0600-\u06ff-]+", re.UNICODE)

_COMMON_AR = {
    "دوخه": "دوخة", "دوار": "دوخة", "الدنيا تلف": "دوخة", "الدنيا تدور": "دوخة", "راسي يلف": "دوخة",
    "وجع راس": "صداع", "راسي يوجعني": "صداع", "صداعه": "صداع", "راسي مصدع": "صداع",
    "ترجيع": "قيء", "استفراغ": "قيء", "تقيأت": "قيء", "لوعه": "غثيان", "لوعه معده": "غثيان", "نفسي تلوع": "غثيان",
    "حراره": "حمى", "سخونه": "حمى", "جسمي حار": "حمى", "كحه": "سعال", "كحة": "سعال", "اكح": "سعال",
    "ضيقه تنفس": "ضيق تنفس", "كتمه": "ضيق تنفس", "نهجان": "ضيق تنفس", "نفسي ضيق": "ضيق تنفس", "مو قادر اتنفس": "ضيق تنفس",
    "صدري مكتوم": "ضيق الصدر", "كتمه بالصدر": "ضيق الصدر", "وجع صدر": "ألم الصدر", "صدري يوجعني": "ألم الصدر",
    "خفقان قلب": "خفقان", "دقات سريعه": "خفقان", "قلبي يدق بسرعه": "خفقان", "قلبي يسرع": "خفقان", "نبضي سريع": "خفقان",
    "بطني يعورني": "ألم البطن", "بطني يوجعني": "ألم البطن", "مغص": "تقلصات البطن", "بطني منفوخ": "انتفاخ", "غازات كثيره": "غازات زائدة",
    "حرقه معده": "حرقة المعدة", "حرقة معده": "حرقة المعدة", "حموضه": "حرقة المعدة", "حرقان بول": "ألم عند التبول", "حرقة بول": "ألم عند التبول",
    "ادخل الحمام كثير": "كثرة التبول", "اتبول كثير": "كثرة التبول", "عطشان كثير": "زيادة العطش",
    "يدي تنمل": "تنميل اليد", "تنميل يدي": "تنميل اليد", "رجلي تنمل": "تنميل القدم", "تنميل رجلي": "تنميل القدم",
    "وجع ركبتي": "ألم الركبة", "ركبتي توجعني": "ألم الركبة", "ركبتي يعورني": "ألم الركبة", "ركبتي تطقطق": "طقطقة المفصل", "ركبتي تطق": "طقطقة المفصل",
    "كعبي يوجعني": "ألم الكعب", "كعبي يوجعني اول ما اقوم": "ألم الكعب مع أول خطوات", "اول خطوه توجع كعبي": "ألم الكعب مع أول خطوات",
    "كوعي يوجعني": "ألم الكوع", "يوجعني الكوع لما امسك": "ألم الكوع مع القبض", "فكي يطق": "طقطقة الفك", "فكي يوجعني": "ألم الفك",
    "اصبعي يعلق": "تعليق الإصبع", "اصبعي يتقفل": "تعليق الإصبع", "رجولي ما تهدا بالليل": "رغبة تحريك الساقين", "رجولي تزعجني وقت الراحه": "انزعاج الساق وقت الراحة",
    "اشخر": "شخير مرتفع", "شخيري عالي": "شخير مرتفع", "نفسي يوقف وانا نايم": "توقف التنفس أثناء النوم", "انعس بالنهار": "نعاس نهاري",
    "اذني تصفر": "طنين", "صوت باذني": "طنين", "نظري مشوش": "تشوش الرؤية", "اشوف مغبش": "تشوش الرؤية",
    "ما اقدر انام": "أرق", "نومي متقطع": "أرق", "مخي مشوش": "ارتباك", "نسياني كثير": "مشاكل الذاكرة",
    "جلدي يحكني": "حكة", "حكه بالجسم": "حكة", "طلعت لي حبوب": "طفح جلدي", "شرى": "شرى جلدي",
    "لثتي تنزف": "نزيف اللثة", "لثتي منتفخه": "تورم اللثة", "قشره الراس": "قشور فروة الرأس", "فروة راسي تحك": "حكة فروة الرأس",
    "قشور بالرموش": "قشور الرموش", "جفوني تحك": "حكة الجفن", "بين اصابع رجلي يحك": "حكة بين أصابع القدم", "تقشر بين الاصابع": "تقشر بين أصابع القدم",
    "صدري يصفر": "صفير التنفس", "في صدري صفير": "صفير التنفس", "صدري ضايق": "ضيق الصدر",
    "انفي مسدود": "احتقان الأنف", "خشمي مسدود": "احتقان الأنف", "عندي رشح": "سيلان الأنف", "اعطس كثير": "عطس",
    "حلقي يوجعني": "ألم الحلق", "صوتي مبحوح": "بحة الصوت", "اذني توجعني": "ألم الأذن", "رسغي يوجعني": "ألم الرسغ",
    "جلدي ناشف": "جفاف الجلد", "رجلي منتفخه": "تورم الساقين", "رجولي منتفخه": "تورم الساقين", "وزني زاد بدون سبب": "زيادة الوزن",
    "اطرافي بارده": "برودة الأطراف", "بردانه اطرافي": "برودة الأطراف", "ما اقدر اركز": "صعوبة التركيز", "تركيزي ضعيف": "صعوبة التركيز",
    "مزاجي منخفض": "مزاج منخفض", "متوتر كثير": "قلق", "جسمي يوجعني": "آلام الجسم", "ما لي نفس للاكل": "فقدان الشهية",
    "عيني حمراء": "احمرار العين", "عيني تحكني": "حكة", "كتفي يوجعني": "ألم الكتف", "ظهري يوجعني": "ألم الظهر",
    "منجارو": "مونجارو", "مونجارو": "تيرزيباتيد",
    "اذني مسدوده": "انسداد الأذن", "اذني مسدودة": "انسداد الأذن", "اذني فيها شمع": "شمع الأذن",
    "اشوف نقط سوداء": "عوائم العين", "اشوف ذباب بعيني": "عوائم العين", "اشوف ومضات": "ومضات العين",
    "فمي ناشف": "جفاف الفم", "فمي جاف": "جفاف الفم", "ريحة فمي": "رائحة الفم", "نفسي ريحته": "رائحة الفم",
    "لساني يحرق": "حرقة الفم", "فمي يحرق": "حرقة الفم", "فطريات بفمي": "فطريات الفم",
    "اطحن اسناني": "صرير الأسنان", "اضغط على اسناني بالنوم": "صرير الأسنان", "فكي مشدود الصباح": "ألم الفك",
    "الدوره متاخره": "تأخر الدورة", "الدورة متأخرة": "تأخر الدورة", "ما نزلت الدوره": "غياب الدورة",
    "هبات حراره": "هبات ساخنة", "يجيني حر فجأه": "هبات ساخنة", "جفاف بالمهبل": "جفاف مهبلي",
    "يتسرب البول": "سلس البول", "ينزل بول بدون تحكم": "سلس البول", "رجلي تتشنج بالليل": "تشنج الساق",
    "عروقي بارزه برجلي": "عروق بارزة برجلي", "عروق رجلي بارزه": "عروق بارزة برجلي", "عروقي بارزه": "عروق بارزة برجلي", "عروقي بارزة": "عروق بارزة برجلي", "شعري يطيح": "تساقط الشعر", "شعري يتساقط": "تساقط الشعر",
    "اصابعي تصير بيضا": "تغير لون الأصابع", "اصابعي تزرق بالبرد": "تغير لون الأصابع",
    "جلدي يحرق من الشمس": "حروق الشمس", "طفح من الحر": "طفح الحرارة", "قرصتني حشره": "لدغة حشرة",
    "كتفي متيبس": "تيبس الكتف", "ما اقدر ارفع كتفي": "تيبس الكتف", "قصبة رجلي توجعني بعد الجري": "ألم قصبة الساق",
    "اتعرق كثير": "تعرق مفرط", "عرقي كثير بدون سبب": "تعرق مفرط", "الحازوقه ما توقف": "حازوقة",
}
_COMMON_EN = {
    "tummy ache": "abdominal pain", "belly pain": "abdominal pain", "stomach ache": "abdominal pain",
    "throwing up": "vomiting", "feeling sick": "nausea", "queasy": "nausea",
    "dizzy": "dizziness", "light headed": "dizziness", "lightheaded": "dizziness", "room spinning": "dizziness",
    "short of breath": "shortness of breath", "can't breathe": "shortness of breath", "cant breathe": "shortness of breath", "breathless": "shortness of breath",
    "heart racing": "palpitations", "heart pounding": "palpitations", "fast heartbeat": "palpitations",
    "stuffy nose": "nasal congestion", "blocked nose": "nasal congestion", "nose blocked": "nasal congestion",
    "burning pee": "painful urination", "burning when i pee": "painful urination", "peeing a lot": "frequent urination", "very thirsty": "increased thirst",
    "pins and needles": "numbness", "hand tingling": "hand numbness", "foot tingling": "foot numbness",
    "knee clicking": "joint clicking", "knee popping": "joint clicking", "knee hurts": "knee pain", "my knee hurts": "knee pain", "heel hurts first steps": "first step heel pain",
    "jaw clicking": "jaw clicking", "finger gets stuck": "finger locking", "urge to move my legs": "urge move legs",
    "loud snoring": "loud snoring", "stop breathing in sleep": "sleep breathing pauses", "sleepy in daytime": "daytime sleepiness",
    "ringing in ears": "tinnitus", "blurry sight": "blurred vision", "can't sleep": "insomnia", "cant sleep": "insomnia",
    "itchy skin": "itching", "itchy scalp": "itchy scalp", "bleeding gums": "bleeding gums", "itchy eyelids": "itchy eyelids",
    "wheezing chest": "wheezing", "chest feels tight": "chest tightness", "blocked up nose": "nasal congestion", "runny nose all day": "runny nose",
    "sneezing a lot": "sneezing", "throat hurts": "sore throat", "voice is hoarse": "hoarseness", "ear hurts": "ear pain", "wrist hurts": "wrist pain",
    "skin is dry": "dry skin", "leg is swollen": "leg swelling", "legs are swollen": "leg swelling", "gaining weight for no reason": "weight gain",
    "hands and feet feel cold": "cold extremities", "can't concentrate": "difficulty concentrating", "cant concentrate": "difficulty concentrating",
    "low mood": "low mood", "feel anxious": "anxiety", "whole body aches": "body aches", "no appetite": "loss of appetite",
    "eye is red": "eye redness", "eye is itchy": "itching", "shoulder hurts": "shoulder pain", "back hurts": "back pain",
    "ear feels blocked": "blocked ear", "wax in my ear": "earwax", "black spots in vision": "eye floaters", "flashes in vision": "eye flashes",
    "mouth feels dry": "dry mouth", "bad breath": "bad breath", "mouth is burning": "burning mouth", "oral thrush": "oral thrush",
    "grind my teeth": "teeth grinding", "clench teeth at night": "teeth grinding", "period is late": "missed period", "period did not come": "missed period",
    "hot flashes": "hot flushes", "vaginal dryness": "vaginal dryness", "leaking urine": "urinary incontinence", "leg cramps at night": "leg cramps",
    "bulging veins in legs": "varicose veins", "hair falling out": "hair loss", "fingers turn white in cold": "finger color change",
    "sunburned skin": "sunburn", "rash from heat": "heat rash", "insect bite": "insect bite", "shoulder is stiff": "stiff shoulder",
    "shin hurts after running": "shin pain", "sweat too much": "excessive sweating", "hiccups won't stop": "hiccups",
}

_QUERY_TOKEN_HINTS_AR = [
    ({"ركبتي", "توجعني"}, "knee-pain"), ({"ركبتي", "يعورني"}, "knee-pain"), ({"ركبتي", "تطقطق"}, "joint-clicking"),
    ({"قلبي", "يدق", "بسرعه"}, "palpitations"), ({"نفسي", "ضيق"}, "shortness-of-breath"), ({"صدري", "يوجعني"}, "chest-pain"),
    ({"بطني", "يوجعني"}, "abdominal-pain"), ({"بطني", "منفوخ"}, "bloating"), ({"يدي", "تنمل"}, "hand-numbness"), ({"رجلي", "تنمل"}, "foot-numbness"),
    ({"كعبي", "يوجعني"}, "heel-sole-pain"), ({"اول", "خطوه", "كعبي"}, "first-step-heel-pain"), ({"فكي", "يطق"}, "jaw-clicking"), ({"اصبعي", "يعلق"}, "finger-locking"),
    ({"نفسي", "يوقف", "نايم"}, "sleep-breathing-pauses"), ({"لثتي", "تنزف"}, "bleeding-gums"), ({"فروه", "راسي", "تحك"}, "itchy-scalp"),
    ({"بين", "اصابع", "رجلي", "يحك"}, "itch-between-toes"), ({"ادخل", "الحمام", "كثير"}, "frequent-urination"), ({"عطشان", "كثير"}, "increased-thirst"),
    ({"ظهري", "يوجعني", "رجلي"}, "back-pain"), ({"ظهري", "يوجعني", "رجلي"}, "leg-pain"),
    ({"جلدي", "بقع", "تحك"}, "skin-rash"), ({"جلدي", "بقع", "تحك"}, "itching"),
    ({"عيني", "حمراء", "تحكني"}, "eye-redness"), ({"عيني", "حمراء", "تحكني"}, "itching"),
    ({"حلقي", "يوجعني", "صوتي", "مبحوح"}, "sore-throat"), ({"حلقي", "يوجعني", "صوتي", "مبحوح"}, "hoarseness"),
    ({"رجلي", "منتفخه", "وزني", "زاد"}, "leg-swelling"), ({"رجلي", "منتفخه", "وزني", "زاد"}, "weight-gain"),
    ({"تعبان", "اطرافي", "بارده"}, "fatigue"), ({"تعبان", "اطرافي", "بارده"}, "cold-extremities"),
]
_QUERY_TOKEN_HINTS_EN = [
    ({"knee", "hurts"}, "knee-pain"), ({"knee", "clicking"}, "joint-clicking"), ({"heart", "racing"}, "palpitations"),
    ({"short", "breath"}, "shortness-of-breath"), ({"chest", "hurts"}, "chest-pain"), ({"belly", "hurts"}, "abdominal-pain"),
    ({"hand", "tingling"}, "hand-numbness"), ({"foot", "tingling"}, "foot-numbness"), ({"heel", "first", "steps"}, "first-step-heel-pain"),
    ({"finger", "stuck"}, "finger-locking"), ({"stop", "breathing", "sleep"}, "sleep-breathing-pauses"), ({"peeing", "lot"}, "frequent-urination"), ({"very", "thirsty"}, "increased-thirst"),
    ({"back", "hurts", "leg"}, "back-pain"), ({"back", "hurts", "leg"}, "leg-pain"),
    ({"skin", "rash", "itchy"}, "skin-rash"), ({"skin", "rash", "itchy"}, "itching"),
    ({"red", "itchy", "eye"}, "eye-redness"), ({"red", "itchy", "eye"}, "itching"),
    ({"sore", "throat", "hoarse"}, "sore-throat"), ({"sore", "throat", "hoarse"}, "hoarseness"),
    ({"swollen", "leg", "weight", "gain"}, "leg-swelling"), ({"swollen", "leg", "weight", "gain"}, "weight-gain"),
]


def normalize(text: str, lang: str = "ar") -> str:
    s = unicodedata.normalize("NFKC", str(text or "")).strip().lower()
    s = _ARABIC_DIACRITICS.sub("", s)
    s = s.translate(str.maketrans({"أ":"ا","إ":"ا","آ":"ا","ى":"ي","ة":"ه","ؤ":"و","ئ":"ي","ـ":""}))
    s = _PUNCT.sub(" ", s)
    s = _SPACE.sub(" ", s).strip()
    s = _collapse_elongation(s)
    mapping = _COMMON_AR if lang == "ar" else _COMMON_EN
    # Phrase normalization first, longest phrases first.
    for src, dst in sorted(mapping.items(), key=lambda x: len(x[0]), reverse=True):
        src_n = normalize_basic(src)
        if src_n and src_n in s:
            s = s.replace(src_n, normalize_basic(dst))
    return _SPACE.sub(" ", s).strip()


def normalize_basic(text: str) -> str:
    s = unicodedata.normalize("NFKC", str(text or "")).strip().lower()
    s = _ARABIC_DIACRITICS.sub("", s)
    s = s.translate(str.maketrans({"أ":"ا","إ":"ا","آ":"ا","ى":"ي","ة":"ه","ؤ":"و","ئ":"ي","ـ":""}))
    s = _PUNCT.sub(" ", s)
    return _SPACE.sub(" ", s).strip()


def _tokens(s: str) -> set[str]:
    return {t for t in s.split() if len(t) >= 2}


def _collapse_elongation(text: str) -> str:
    """Collapse obvious typing elongation without changing normal doubled letters."""
    return re.sub(r"(.)\1{2,}", r"\1", str(text or ""))


def _best_query_variant_score(query: str, candidate: str) -> float:
    """Score a candidate against the full query *and* nearby token windows.

    Full-sentence similarity is weak for natural questions such as
    ``ليش يجيني غثين وقت الحر``. Window scoring keeps typo tolerance useful
    without promoting an unrelated fuzzy topic.
    """
    query = _collapse_elongation(query)
    candidate = _collapse_elongation(candidate)
    if not query or not candidate:
        return 0.0
    best = _score(query, candidate)
    qtokens = query.split()
    ctokens = candidate.split()
    if not qtokens or not ctokens:
        return best
    target = max(1, len(ctokens))
    for width in sorted({max(1, target - 1), target, target + 1}):
        if width > len(qtokens):
            continue
        for i in range(len(qtokens) - width + 1):
            window = " ".join(qtokens[i:i+width])
            best = max(best, _score(window, candidate))
    return best


def detect_intent(query: str, lang: str = "ar") -> str:
    """Classify the user's search intent without inventing medical content."""
    q = normalize_basic(query)
    if not q:
        return "explain"
    if lang == "en":
        groups = [
            ("causes", ("why ", "cause", "causes", "reason")),
            ("care", ("what should i do", "what can i do", "how to manage", "how can i help", "treatment")),
            ("urgency", ("is it serious", "is this serious", "when should i", "when to see", "emergency", "dangerous")),
            ("meaning", ("what is", "what does", "meaning", "explain")),
        ]
    else:
        groups = [
            ("causes", ("ليش", "لماذا", "ما سبب", "وش سبب", "ايش سبب", "اسباب", "سبب ")),
            ("care", ("وش اسوي", "وش اسوي", "ماذا افعل", "ايش اسوي", "كيف اتصرف", "كيف اخفف", "علاج")),
            ("urgency", ("هل خطير", "هل هذا خطير", "متى اراجع", "متى اروح", "متى يحتاج", "طوارئ", "خطر")),
            ("normality", ("هل طبيعي", "طبيعي ولا", "هل هذا طبيعي")),
            ("meaning", ("وش يعني", "ما معنى", "ما هو", "ما هي", "معنى", "اشرح")),
        ]
    for intent, phrases in groups:
        if any(p in q for p in phrases):
            return intent
    return "explain"


def extract_contexts(query: str, lang: str = "ar") -> list[str]:
    """Return neutral context tags used to preserve query modifiers."""
    q = normalize_basic(query)
    groups = (
        [("heat", ("الحر", "بالحر", "مع الحر", "في الحر", "وقت الحر", "الشمس", "جو حار", "الجو الحار", "حراره الجو")),
         ("exercise", ("رياضه", "تمرين", "مجهود", "جري", "مشي")),
         ("fasting", ("صيام", "صايم", "صائم")),
         ("period", ("الدوره", "الحيض", "الطمث")),
         ("pregnancy", ("حامل", "حمل")),
         ("food", ("بعد الاكل", "قبل الاكل", "اكل", "وجبه")),
         ("sleep", ("نوم", "نايم", "بالليل", "الصباح")),
         ("medicine", ("دواء", "حبوب", "جرعه", "علاج"))]
        if lang != "en" else
        [("heat", ("heat", "hot weather", "sun")),
         ("exercise", ("exercise", "workout", "running", "walking", "exertion")),
         ("fasting", ("fasting", "fasted")),
         ("period", ("period", "menstrual", "menses")),
         ("pregnancy", ("pregnant", "pregnancy")),
         ("food", ("after eating", "before eating", "food", "meal")),
         ("sleep", ("sleep", "night", "morning")),
         ("medicine", ("medicine", "medication", "drug", "dose"))]
    )
    return [name for name, terms in groups if any(normalize_basic(t) in q for t in terms)]


def _mention_is_negated(normalized_query: str, normalized_variant: str, lang: str) -> bool:
    """Avoid presenting explicitly denied symptoms as active recognized symptoms."""
    if not normalized_query or not normalized_variant:
        return False
    q = " " + normalized_query + " "
    v = normalized_variant
    if lang == "en":
        patterns = (f" no {v}", f" without {v}", f" do not have {v}", f" dont have {v}", f" not having {v}")
    else:
        patterns = (f" ما عندي {v}", f" ماعندي {v}", f" ما في {v}", f" مافي {v}", f" بدون {v}", f" من غير {v}", f" لا يوجد {v}", f" مافيه {v}")
    return any(p in q for p in patterns)


@lru_cache(maxsize=2)
def _token_lexicon(lang: str) -> tuple[str, ...]:
    """Single-token medical lexicon used only for conservative typo repair."""
    blocked_ar = {"عندي","يجيني","يجي","احس","وقت","مع","بعد","قبل","بدون","بس","مره","كثير","اليوم","امس","الحين","الان","الحر","الشمس"}
    blocked_en = {"have","feel","with","after","before","without","very","today","yesterday","now","when","why","what","heat","sun"}
    blocked = blocked_en if lang == "en" else blocked_ar
    words = set()
    for item in _all_candidates(lang):
        for variant in [item.get("label") or "", *(item.get("aliases") or [])]:
            for token in normalize_basic(variant).split():
                if len(token) >= 4 and token not in blocked and not token.isdigit():
                    words.add(token)
    return tuple(sorted(words))


def _safe_typo_correct(normalized_query: str, lang: str) -> tuple[str, list[dict]]:
    """Correct only highly confident, unique one-token health typos (see typo_repair for the rules)."""
    import typo_repair
    return typo_repair.repair(normalized_query, _token_lexicon(lang), lang)


def _score(query: str, candidate: str) -> float:
    if not query or not candidate:
        return 0.0
    if query == candidate:
        return 1.0
    if query in candidate or candidate in query:
        containment = min(len(query), len(candidate)) / max(len(query), len(candidate))
        return min(0.98, 0.78 + 0.20 * containment)
    qt, ct = _tokens(query), _tokens(candidate)
    token_score = len(qt & ct) / max(1, len(qt | ct))
    char_score = difflib.SequenceMatcher(a=query, b=candidate).ratio()
    return 0.62 * char_score + 0.38 * token_score


_ENTITY_CACHE = {}
_ENTITY_CACHE_TTL = 60.0

def _entity_candidates(lang: str) -> list[dict]:
    lang = "en" if lang == "en" else "ar"
    now = time.monotonic()
    cached = _ENTITY_CACHE.get(lang)
    if cached and (now - cached[0]) < _ENTITY_CACHE_TTL:
        return [dict(x) for x in cached[1]]
    items = []
    for kind in ("symptoms", "diseases"):
        try:
            rows = medical_knowledge.list_entities(kind, include_inactive=False, search="") or []
        except Exception:
            rows = []
        for row in rows:
            label = str(row.get("name_ar" if lang == "ar" else "name_en") or row.get("name_en") or row.get("name_ar") or "")
            aliases = row.get("aliases_ar" if lang == "ar" else "aliases_en") or []
            if isinstance(aliases, str):
                try:
                    import json
                    aliases = json.loads(aliases)
                except Exception:
                    aliases = [aliases]
            items.append({
                "kind": kind[:-1] if kind.endswith("s") else kind,
                "id": row.get("id"), "slug": row.get("slug"), "label": label,
                "aliases": [str(x) for x in (aliases or []) if str(x).strip()],
                "status": row.get("status"), "version": row.get("version"),
            })
    _ENTITY_CACHE[lang] = (now, [dict(x) for x in items])
    return items


def _curated_candidates(lang: str) -> list[dict]:
    """Expose curated search-only topics (medicines/tests/terms) to ranking."""
    items = []
    ar = lang != "en"
    for key, entry in (getattr(health_search, "SEARCH_KB", {}) or {}).items():
        detail = entry.get("ar" if ar else "en") or {}
        label = str(detail.get("title") or key).strip()
        aliases = [str(x) for x in (entry.get("aliases") or []) if str(x).strip()]
        items.append({
            "kind": str(entry.get("category") or "term"),
            "id": None, "slug": str(key), "label": label, "aliases": aliases,
            "status": "active", "version": None, "curated": True,
        })
    return items


def _all_candidates(lang: str) -> list[dict]:
    rows = _entity_candidates(lang) + _curated_candidates(lang)
    dedup = []
    seen = set()
    for row in rows:
        identity = str(row.get("slug") or "").strip() or normalize_basic(row.get("label") or "")
        marker = (str(row.get("kind") or ""), identity)
        if not marker[1] or marker in seen:
            continue
        seen.add(marker); dedup.append(row)
    return dedup


def _mention_candidates(lang: str) -> list[dict]:
    """Symptom-only variants used to recover multiple concepts from one query."""
    return [x for x in _entity_candidates(lang) if x.get("kind") == "symptom"]


def extract_symptom_mentions(query: str, lang: str = "ar", limit: int = 8) -> list[dict]:
    """Find several symptom concepts inside one free-text sentence.

    Exact/contained aliases are preferred. Fuzzy fallback is conservative and
    only used for tokens/phrases long enough to avoid noisy medical matches.
    """
    lang = "en" if lang == "en" else "ar"
    raw = str(query or "").strip()[:500]
    nq = normalize(raw, lang)
    nq, _ = _safe_typo_correct(nq, lang)
    if len(nq) < 2:
        return []
    hits = []
    for item in _mention_candidates(lang):
        best = 0.0
        best_variant = ""
        for variant in [item.get("label") or "", *(item.get("aliases") or [])]:
            nv = normalize(variant, lang)
            if not nv:
                continue
            if nv in nq and len(nv) >= 3:
                if _mention_is_negated(nq, nv, lang):
                    continue
                score = min(1.0, 0.92 + min(len(nv), 24) / 300.0)
            elif len(nv) >= 5:
                qtokens = nq.split()
                vlen = max(1, len(nv.split()))
                windows = [" ".join(qtokens[i:i+vlen]) for i in range(max(1, len(qtokens)-vlen+1))]
                score = max((_score(w, nv) for w in windows), default=0.0)
                min_fuzzy = 0.90 if len(nv.split()) == 1 else 0.80
                if score < min_fuzzy:
                    continue
            else:
                continue
            if score > best:
                best, best_variant = score, variant
        if best:
            hits.append({"slug": item.get("slug"), "label": item.get("label") or "", "kind": "symptom", "score": round(best,4), "matched_text": best_variant})
    # Token-set hints recover colloquial phrases whose words are separated by
    # extra text (for example: "ركبتي تطقطق وتوجعني").
    token_set = set(normalize_basic(raw).split())
    if lang == "ar":
        token_set |= {t[1:] for t in list(token_set) if t.startswith("و") and len(t) > 3}
    hint_rows = _QUERY_TOKEN_HINTS_AR if lang == "ar" else _QUERY_TOKEN_HINTS_EN
    by_slug = {str(x.get("slug")): x for x in _mention_candidates(lang)}
    for required, slug in hint_rows:
        req_norm = {normalize_basic(x) for x in required}
        if req_norm.issubset(token_set) and slug in by_slug:
            item = by_slug[slug]
            hits.append({"slug": slug, "label": item.get("label") or slug, "kind": "symptom", "score": 0.96, "matched_text": " ".join(sorted(required))})
    # Resolve common specificity conflicts. A body-part cramp should not be
    # promoted to a seizure merely because the generic Arabic word "تشنج" is
    # contained in the phrase. Likewise, dry mouth alone should not imply
    # whole-body dehydration unless the query also contains dehydration clues.
    slugs = {str(h.get("slug") or "") for h in hits}
    basic_raw = normalize_basic(raw)
    if {"leg-cramps", "muscle-cramps"} & slugs:
        seizure_context = (
            any(k in basic_raw for k in ("صرع", "نوبه", "نوبة", "اختلاج", "فقدان وعي"))
            if lang == "ar" else
            any(k in basic_raw for k in ("seizure", "convulsion", "lost consciousness", "loss of consciousness"))
        )
        if not seizure_context:
            hits = [h for h in hits if h.get("slug") != "seizure"]
    if "dry-mouth" in slugs:
        dehydration_context = (
            any(k in basic_raw for k in ("عطش", "جفاف الجسم", "نقص سوائل", "ما اشرب", "قلة شرب"))
            if lang == "ar" else
            any(k in basic_raw for k in ("dehydr", "thirst", "not drinking", "low fluids"))
        )
        if not dehydration_context:
            hits = [h for h in hits if h.get("slug") != "dehydration"]

    # Prefer the more specific concept when it fully contains the generic one.
    # This keeps a multi-symptom search from counting "dry cough" as both
    # "cough" and "dry cough", or "itchy eyes" as both generic itching and an
    # eye-specific symptom.
    slugs = {str(h.get("slug") or "") for h in hits}
    redundant = set()
    if {"dry-cough", "productive-cough"} & slugs:
        redundant.add("cough")
    if {"eye-itching", "nasal-itching", "ear-itching", "rectal-itching", "itchy-eyelids", "itchy-scalp", "itch-between-toes"} & slugs:
        redundant.add("itching")
    if {"post-meal-nausea", "motion-triggered-nausea"} & slugs:
        redundant.add("nausea")
    if "foot-burning" in slugs:
        redundant.add("burning-sensation")
    if "radiating-leg-pain" in slugs:
        redundant.update({"leg-pain", "back-pain", "lower-back-pain", "hip-pain"})
    if "shoulder-night-pain" in slugs:
        redundant.add("shoulder-pain")
    if redundant:
        hits = [h for h in hits if h.get("slug") not in redundant]

    hits.sort(key=lambda x: (-x["score"], -len(x.get("matched_text") or ""), x["label"]))
    dedup=[]; seen=set()
    for hit in hits:
        if hit["slug"] in seen: continue
        seen.add(hit["slug"]); dedup.append(hit)
        if len(dedup) >= max(1,min(int(limit or 8),12)): break
    return dedup


def search(query: str, lang: str = "ar", limit: int = 8) -> dict:
    lang = "en" if lang == "en" else "ar"
    raw = str(query or "").strip()
    if len(raw) < 2:
        return {"query": raw, "normalized": "", "results": [], "answer": None, "coverage": "empty"}
    if len(raw) > 500:
        raw = raw[:500]
    nq = normalize(raw, lang)
    nq, typo_corrections = _safe_typo_correct(nq, lang)
    mentions = extract_symptom_mentions(raw, lang, 10)
    try:
        import symptom_combo_intelligence
        pattern_insights = symptom_combo_intelligence.detect_patterns([{"slug": x.get("slug")} for x in mentions], lang)
    except Exception:
        pattern_insights = []
    ranked = []
    for item in _all_candidates(lang):
        variants = [item["label"], *item.get("aliases", [])]
        best = max((_score(nq, normalize_basic(v)) for v in variants if v), default=0.0)
        if best >= 0.40:
            out = dict(item)
            out["score"] = round(best, 4)
            ranked.append(out)
    ranked.sort(key=lambda x: (-x["score"], x.get("kind", ""), x.get("label", "")))
    try:
        answer = health_search.search_health(raw, lang)
    except Exception:
        answer = None
    try:
        parsed_limit = int(limit or 8)
    except (TypeError, ValueError):
        parsed_limit = 8
    top = ranked[:max(1, min(parsed_limit, 20))]
    top_score = top[0]["score"] if top else 0.0
    coverage = "strong" if top_score >= 0.72 else "partial" if top_score >= 0.48 else "weak"
    # Explicitly recognized symptom mentions are promoted ahead of generic fuzzy
    # candidates so multi-symptom sentences remain understandable to the UI.
    mention_slugs = {str(m.get("slug") or "") for m in mentions if m.get("slug")}
    promoted = [dict(m) for m in mentions]
    promoted.extend(x for x in top if str(x.get("slug") or "") not in mention_slugs)
    top = promoted[:max(1, min(parsed_limit, 20))]
    if len(mentions) >= 2 and coverage == "weak":
        coverage = "partial"
    did_you_mean = None
    if typo_corrections:
        target = mentions[0] if mentions else (top[0] if top else None)
        if target:
            did_you_mean = {
                "label": target.get("label"), "slug": target.get("slug"),
                "kind": target.get("kind"), "score": target.get("score"),
                "corrections": typo_corrections,
            }
    return {
        "query": raw, "normalized": nq, "results": top,
        "recognized_symptoms": mentions, "pattern_insights": pattern_insights,
        "answer": answer, "coverage": coverage,
        "query_intent": detect_intent(raw, lang),
        "contexts": extract_contexts(raw, lang),
        "typo_corrections": typo_corrections,
        "did_you_mean": did_you_mean,
        "engine_version": "v4-intent-context-typo-aware",
    }


def suggestions(query: str, lang: str = "ar", limit: int = 6) -> list[dict]:
    """Fast type-ahead suggestions from curated KB entities only.

    Unlike :func:`search`, this function never calls the explanatory health-search
    pipeline, which keeps per-keystroke requests cheap and deterministic.
    """
    lang = "en" if lang == "en" else "ar"
    raw = str(query or "").strip()[:120]
    if len(raw) < 2:
        return []
    nq = normalize(raw, lang)
    nq, _ = _safe_typo_correct(nq, lang)
    ranked = []
    for item in _all_candidates(lang):
        variants = [item.get("label") or "", *(item.get("aliases") or [])]
        score = max((_score(nq, normalize_basic(v)) for v in variants if v), default=0.0)
        # Typeahead is strict enough to avoid noisy medical substitutions, but
        # token-window scoring still catches a one-letter typo inside a sentence.
        if score >= 0.58:
            ranked.append({
                "label": item.get("label") or "",
                "kind": item.get("kind") or "",
                "slug": item.get("slug"),
                "score": round(score, 4),
            })
    ranked.sort(key=lambda x: (-x["score"], x["label"]))
    if ranked:
        top_score = float(ranked[0].get("score") or 0.0)
        floor = max(0.58, top_score - 0.18)
        ranked = [x for x in ranked if float(x.get("score") or 0.0) >= floor]
        # If the query has an exact/near-exact topic, keep typeahead focused on
        # labels that visibly match it instead of showing conditions that merely
        # list that symptom deep in their aliases.
        if top_score >= 0.98:
            focused = []
            for x in ranked:
                label_n = normalize_basic(x.get("label") or "")
                if nq in label_n or label_n in nq:
                    focused.append(x)
            if focused:
                ranked = focused
    dedup = []
    seen = set()
    for item in ranked:
        marker = (str(item.get("kind") or ""), str(item.get("slug") or "") or normalize_basic(item.get("label") or ""))
        if marker in seen:
            continue
        seen.add(marker); dedup.append(item)
    try:
        n = max(1, min(int(limit or 6), 10))
    except (TypeError, ValueError):
        n = 6
    return dedup[:n]
