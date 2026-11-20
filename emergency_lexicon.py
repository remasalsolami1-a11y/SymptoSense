"""Dialect-aware emergency phrase layer (Gulf / Hejazi / Egyptian / MSA / typos).

Complements the literal phrase lists in ``safety_engine`` with regular
expressions that understand colloquial wording ("صدري ينعصر", "مش قادر اتنفس",
"قلبي واقف", "عيوني ما ترى").  It is deliberately conservative in one direction
only: a missed emergency is worse than an extra warning, but every rule still
respects negation ("ما في نزيف") and clearly-resolved past episodes.

All patterns are written in normal Arabic spelling and normalised at import time
with the same character folding used by ``clinical_text.normalize_clinical_text``.

Use ``evaluate(text)`` -> list of ``(rule_id, ar_label, en_label)``.
"""
from __future__ import annotations

import re

import clinical_text

_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"})


def _rx(*patterns: str) -> re.Pattern:
    folded = "|".join("(?:%s)" % p.translate(_FOLD) for p in patterns)
    return re.compile(folded)


_W = r"[؀-ۿa-z0-9]"
_SP = r"\s+"

# --- shared fragments ------------------------------------------------------
_CHEST = r"(?<![؀-ۿ])[بكل]?(?:ال)?(?:صدر|قلب)\w*"
_PAIN = (r"(?:يوجع|بيوجع|يعور|بيعور|واجع|وجع|الم|ضغط|ضغطه|ثقل|ثقيل|تقيل|ينعصر|بينعصر|معصور|"
         r"مضغوط|مخنوق|ينضغط|انقباض|ساحق|يحرق|حارق|تعصر|عاصر)\w*")
_INTENSE = (r"(?:وايد|مره|مرة|قوي|قويه|شديد|جامد|اوي|كتير|كثير|جدا|جدآ|ساحق|"
            r"ما\s+(?:قدرت|اقدر)\s+اتحمل|مش\s+قادر|مو\s+قادر|مب\s+قادر|لا\s+يحتمل|ما\s+يتحمل)\w*")
_RADIATE = (r"(?:يمتد|ينتشر|يروح|رايح|ينزل|يطلع|يوصل|ممتد|منتشر)\w*|(?:الفك|فكي|كتفي|الكتف|"
            r"ذراعي|دراعي|الذراع|الدراع)")
_SWEAT = r"(?:عرق\w*|تعرق|اتعرق|بارد)"
_NUMB = r"(?:تنمل|تنميل|مخدر|خدر|خدران|منمل)\w*"

_PAST = _rx(r"(?<![؀-ۿ])(?:امس|البارح\w*|قبل\s+(?:\w+\s+)?(?:ساعه|ساعتين|ساعات|يوم|يومين|ايام|اسبوع|سنه|سنتين|شهر)|"
            r"من\s+زمان|earlier|yesterday)(?![؀-ۿ])")
_NOW = _rx(r"(?<![؀-ۿ])(?:الان|الحين|دلوقتي|دلوقت|حاليا|هسا|توه|الساعه|now|currently)(?![؀-ۿ])")
_RESOLVED_NOW = re.compile(
    r"(?:و?(?:الان|الحين|دلوقتي|هسا)\s+(?:انا\s+|هي\s+|هو\s+)?(?:طبيعي|طبيعيه|احسن|تمام|بخير|الحمدلله|الحمد لله)"
    r"|(?:بخير|تمام|طبيعي|طبيعيه)\s+(?:الان|الحين|دلوقتي|هسا))")


def resolved_past(text: str) -> bool:
    """Public helper: does the text describe an earlier episode that is over?"""
    return _resolved_past(clinical_text.normalize_clinical_text(text))


def speech_is_explained(text: str) -> bool:
    """Speech difficulty explained by an ordinary cause (sore throat, hoarseness...)."""
    return bool(_RX_SPEECH_EXPLAINED.search(clinical_text.normalize_clinical_text(text)))


def _resolved_past(text_n: str) -> bool:
    """True when the text describes an earlier episode that is over."""
    if not _PAST.search(text_n):
        return False
    cleaned = _RESOLVED_NOW.sub(" ", text_n)
    return not _NOW.search(cleaned)


# --- rule patterns ---------------------------------------------------------
_RX_CHEST = _rx(_CHEST)
_RX_PAIN = _rx(_PAIN)
_RX_INTENSE = _rx(_INTENSE)
_RX_RADIATE = _rx(_RADIATE)
_RX_SWEAT = _rx(_SWEAT)
_RX_NUMB = _rx(_NUMB)
_RX_CHEST_HEAVY = _rx(r"(?:تقيل|ثقيل|ثقل|جاثم|حجر)\w*\s+(?:\w+\s+){0,2}(?:على|في|ب)\s*(?:ال)?صدر")
_RX_HEART_STOP = _rx(r"قلبي\s+(?:واقف|بيوقف|راح\s+يوقف|بيقف|بيتوقف|يوقف)(?!\s+(?:على|عند|مع|في|من\s+(?:ال)?(?:ضحك|فرح|خوف)))")

_RX_DYING = _rx(r"(?:احس|حاسس|حاس|حاسه|اشعر|شعور|احساس)\s+(?:ب)?ان[يه]?\s+(?:بموت|ساموت|راح\s+اموت|رح\s+اموت|هموت|اموت|ميت)(?!\s+من)")

_RX_BREATH = _rx(
    r"(?<![؀-ۿ])(?:مش|مب|مو|ماني|ما+)\s*(?:قادر\w*|عارف\w*|اقدر|اعرف)\s+(?:ا?تنفس|ا+خذ\s+نفس|اشهق)",
    r"(?<![؀-ۿ])(?:بخنق|بختنق|مختنق|مخنوق\s+ومش)",
    r"(?<![؀-ۿ])[بل]?(?:ال)?اختناق(?![؀-ۿ])",
    r"نفس\w*\s+(?:اتقطع|انقطع|مقطوع|وقف|بيقطع|ضايق\s+وايد|ضايق\s+مره)",
    r"شف[ايه]\w*\s+(?:زرق|ازرق\w*|زرقاء|زرقا)",
    r"(?:مفيش|مافي|ما\s+في|ما\s+يدخل|ما\s+بيدخل)\s+(?:ال)?هوا",
    r"(?:ال)?هوا\s+(?:ما|مش|مو)\s+(?:يدخل|بيدخل)",
    r"ضيق\s+شديد\s+(?:ب|في\s+)?(?:ال)?تنفس",
)

_RX_FACE = _rx(
    r"(?:وجه|وش)\w*\s+(?:مايل|مايله|معوج|متدلي|منحرف|ملتوي)\w*",
    r"(?:نص|نصف)\s+(?:ال)?(?:وجه|وش)\w*\s+(?:نايم|مخدر|خدران|مايل|ميت|متدلي)",
    r"(?:التواء|تدلي|اعوجاج|ميلان)\s+(?:في\s+|ب)?(?:جانب\s+)?(?:ال)?(?:وجه|وش)",
)
_RX_SPEECH = _rx(
    r"(?:كلام|لسان)\w*\s+(?:\w+\s+)?(?:ثقيل|تقيل|ثقيله|غريب|غريبه|ملخبط|متلعثم|مش\s+واضح|مو\s+واضح)\w*",
    r"(?<![؀-ۿ])(?:مش|مب|مو|ما)\s*(?:عارف|قادر|اقدر|اعرف)\w*\s+(?:ا)?تكلم",
    r"صعوبه\s+(?:في\s+|ب)?(?:ال)?(?:نطق|كلام)",
)
_RX_SPEECH_EXPLAINED = _rx(r"(?<![\u0600-\u06ff])(?:لان|بسبب|ملتهب|التهاب|بحه|رشح|زكام|حلقي\s+يعور)")
_RX_LIMB = _rx(
    r"(?:مش|مب|مو|ما)\s*(?:اقدر|قادر\w*)\s+(?:احرك|اتحرك)\s+(?:ال)?(?:ايد|يد|ذراع|دراع|رجل|ساق|جسم)\w*",
    r"(?<![؀-ۿ])[وف]?(?:ايد|يد|دراع|ذراع|رجل|جسم)\w*\s+(?:ما|مش)\s+(?:بتتحرك|تتحرك|بيتحرك|يتحرك)",
    r"(?:نص|نصف)\s+(?:ال)?(?:جسم|جسمي)\w*\s+(?:\w+\s+)?(?:مخدر|خدران|نايم|مش\s+بيتحرك|ما\s+يتحرك|مشلول)",
    r"ضعف\s+(?:مفاجي\s+)?(?:في\s+)?(?:جانب|جهه|طرف)\s+واحد",
)
_RX_VISION = _rx(
    r"(?:عيون\w*|نظر\w*|بصر\w*)\s+(?:ما|مش)?\s*(?:ترا|ترى|بتشوف|تشوف|راح|راحت|اسود\w*|ضاع\w*|انطفا\w*)",
    r"(?<![؀-ۿ])(?:ما|مش)\s+(?:اشوف|ارى|ارا)\s+(?:زين|شي|فجاه|فجاءه)",
)

_RX_COLLAPSE = _rx(r"(?<![؀-ۿ])[وف]?(?:طاح|وقع|سقط|انهار|مغمي|اغمي|فاقد|غاب)\w*")
_RX_NOT_RESPONDING = _rx(
    r"(?:ما|مش)\s+(?:يصحي|يصحى|بيصحي|بيفوق|يفوق|بتصحي|بتفوق|تصحي|تفوق|يرد|بيرد|بترد|ترد|"
    r"يستجيب|بيستجيب|بتستجيب|تستجيب|يتحرك|بيتحرك)(?![؀-ۿ])",
)
_RX_UNRESP_STRONG = _rx(r"(?:ما|مش)\s+(?:يرد|بيرد|بترد)\s+(?:علي\s+)?ولا\s+(?:يتحرك|بيتحرك|بتتحرك)")

_RX_SEIZE_VERB = _rx(r"(?<![؀-ۿ])(?:بي|ي|بت|ت)?تشنج\w*")
_RX_SEIZE_FOAM = _rx(r"(?:بي|ب|ي|ت)?زبد|زبد\s+من\s+(?:ال)?فم\w*|رغو[هة]\s+من\s+(?:ال)?فم")
_RX_SEIZE_EYES = _rx(r"عيون\w*\s+(?:قالبه|مقلوبه|قلبت|بتقلب|ترجع\s+لورا)")
_RX_SEIZE_SHAKE = _rx(r"\w*(?:رتجف|رجف|رتعش|ترعش)\w*")
_RX_SEIZE_PROLONGED = _rx(r"تشنج\w*\s+مستمر\w*", r"مستمر\w*\s+(?:ال)?تشنج\w*")

_RX_BLEED_QUAL = _rx(
    r"(?:دم|نزيف|الدم|النزيف)\s+(?:\w+\s+)?(?:وايد|كتير|كثير|غزير\w*|جامد|قوي\w*|شديد\w*|حاد)(?![؀-ۿ])",
    r"(?:ال)?دم\s+(?:نازل|بينزل|ينزل|يسيل|سايل)\s+(?:وايد|كتير|جامد|بغزاره|بقوه)",
)
_RX_BLEED_NOSTOP = _rx(
    r"(?:دم|نزيف)\w*\s+(?:\w+\s+){0,2}(?:ما|مش|مو|لا)\s+(?:راضي\s+)?(?:يوقف|بيوقف|بيقف|يقف|يتوقف|ينقطع|بينقطع)",
)
_RX_BLOOD_FROM_MOUTH = _rx(
    r"(?:سعل|اسعل|بسعل|بكح|اكح|يكح|تكح|اتقيا\w*|يتقيا\w*|ارجع|يرجع|ترجع|بترجع|برجع|بطلع|اطلع|يطلع|تطلع|بتطلع|يسعل|تسعل)\s+(?:\w+\s+){0,1}دم",
    r"سعال\s+(?:مصحوب\s+)?(?:ب)?(?:دم|دموي)",
    r"قي[ءي]?\s+دموي",
)

_RX_PREGNANT = _rx(r"(?<![؀-ۿ])(?:حامل|حامله|حمل)(?![؀-ۿ])")
_RX_BLEED_ANY = _rx(r"(?<![؀-ۿ])[وف]?(?:ال)?(?:دم|نزيف|نزف|بنزف|ننزف|انزف)(?![؀-ۿ])")
_RX_PREG_SEVERE = _rx(r"(?:وايد|كتير|كثير|غزير\w*|جامد|قوي\w*|شديد\w*|حاد)(?![؀-ۿ])")
_RX_FETAL_NOMOVE = _rx(r"(?:ما|مش|لا)\s+(?:احس|اشعر|بحس|اجد)\s+(?:ب)?حركه?\s+(?:ال)?جنين")
_RX_SEVERE_HEADACHE = _rx(r"صداع\s+(?:\w+\s+)?(?:قوي|شديد|جامد|وايد)\w*")

_RX_AIRWAY_SWELL = _rx(
    r"(?<![؀-ۿ])[وف]?(?:حلق|لسان)\w*\s+(?:\w+\s+)?(?:ورم|ورمت|متورم|بيتورم|يتورم|تورم|منتفخ|ينتفخ|بينتفخ|اتورم|سكر|بيقفل|يقفل|مسكر|مسكور)\w*",
    r"تورم\s+(?:في\s+|ب)?(?:ال)?(?:حلق|لسان)",
    r"(?:ال)?(?:حلق|لسان)\w*\s+(?:ي|ب)?قفل",
)
_RX_TONGUE_FACE = _rx(r"(?:وجه|وش)\w*\s+(?:ورم|متورم|منتفخ)\w*")
_RX_ALLERGY_SEVERE = _rx(r"حساسيه\s+(?:شديده|مفرطه|قويه)")
_RX_BREATH_MILD = _rx(r"(?:ضيق|صعوبه)\s+(?:في\s+|ب)?(?:ال)?تنفس", r"صعب\s+(?:علي\s+)?(?:ا)?(?:ل)?تنفس")

_RX_SELF_HARM = _rx(
    r"(?:ابي|ابغى|ابغي|ودي|عايز\w*|عاوز\w*|ناوي|بدي|اريد|ارغب|قررت|حاب|نفسي)\s+(?:في\s+)?(?:ان\s+)?"
    r"(?:انتحر|اقتل\s+(?:نفسي|ذاتي)|اموت\s+نفسي|انهي\s+حياتي|انهي\s+حياتي|اخلص\s+(?:من\s+)?حياتي|اذي\s+نفسي|اؤذي\s+نفسي|"
    r"ايذاء\s+نفسي|اجرح\s+نفسي|اذيه\s+نفسي)",
    r"(?:هقتل|راح\s+اقتل|رح\s+اقتل|ساقتل|سا?قتل|بقتل)\s+نفسي",
    r"(?<![؀-ۿ])(?:مش|مو|ما|مب)\s*(?:عايز\w*|عاوز\w*|ابي|ابغى|ابغي|اريد|ودي|حاب)\s+(?:ان\s+)?اعيش(?!\s+(?:في|ب|مع|هنا|هناك|عند|لوحدي|بعيد))",
    r"(?:اخلص|اخلصت)\s+(?:من\s+)?حيات[يه]",
)
_RX_LIFE_WEARY = _rx(r"(?:تعبت|زهقت|مليت|كرهت|طفشت)\s+(?:من\s+)?(?:ال)?حيا[هة]\w*")
_RX_WISH_END = _rx(r"(?:ابي|ابغى|ابغي|ودي|عايز\w*|عاوز\w*|بدي|اريد)\s+(?:ان\s+)?(?:اخلص|ارتاح|اموت|انتهي|اختفي)")

_PILLS = r"(?:حبوب|اقراص|حبات|ادويه|دوا|دواء)"
_RX_OVERDOSE = _rx(
    r"(?:بلع|ابتلع|شرب|اخذ|اخد|واخد|تناول|اكل)\w*\s+(?:\w+\s+){0,2}"
    r"(?:" + _PILLS + r"\s+(?:وايد|كتير|كثير\w*|منومه|زايده|زياده|كبيره)|عده\s+" + _PILLS + r"|كميه\s+كبيره\s+من)",
    r"جرعه\s+(?:زايده|زياده|زائده)",
    r"واخد\s+جرعه\s+زيا?ده",
)
_RX_TOXIC = _rx(
    r"(?:بلع|ابتلع|شرب|لحس|اكل)\w*\s+(?:\w+\s+){0,2}(?:منظف|كلور|كلوركس|مبيد|بنزين|جاز|مبيض|ديتول|زئبق|زيبق|"
    r"ماده\s+(?:منظفه|سامه)|مواد\s+منظفه|سايل\s+تنظيف|مزيل)\w*",
    r"تسمم\s+ب(?:ال)?(?:مبيد|غاز|دوا|دواء|كحول|سم|اقراص|حبوب)",
)

_RULES = {
    "chest": ("severe_chest_pain", "ألم أو ضغط شديد في الصدر", "Severe chest pain or pressure"),
    "heart": ("severe_chest_pain", "ألم أو ضغط شديد في الصدر", "Severe chest pain or pressure"),
    "breath": ("severe_breathing", "صعوبة شديدة في التنفس", "Severe breathing difficulty"),
    "stroke": ("stroke_pattern", "أعراض عصبية مفاجئة قد توافق نمط السكتة الدماغية",
               "Sudden focal neurological symptoms that may match a stroke pattern"),
    "vision": ("sudden_vision_loss", "فقدان مفاجئ للرؤية", "Sudden vision loss"),
    "uncon": ("loss_of_consciousness", "فقدان وعي حالي أو غير محدد الزمن / عدم استجابة",
              "Current or time-unspecified loss of consciousness / unresponsiveness"),
    "seizure": ("active_seizure", "تشنج أو اختلاج يحدث الآن", "Seizure or convulsion happening now"),
    "seizure_long": ("prolonged_seizure", "تشنج مستمر أو نوبة مطولة", "Prolonged or ongoing seizure"),
    "bleed": ("severe_bleeding", "نزيف شديد أو غير متوقف", "Severe or uncontrolled bleeding"),
    "blood_mouth": ("blood_vomit_or_cough", "قيء دموي أو سعال مصحوب بدم", "Vomiting or coughing up blood"),
    "preg": ("pregnancy_bleeding_severe", "نزيف أثناء الحمل مع علامة خطر شديدة",
             "Bleeding during pregnancy with a severe warning sign"),
    "preg_neuro": ("pregnancy_danger_signs", "حمل مع نقص حركة الجنين وصداع شديد",
                   "Pregnancy with reduced fetal movement and severe headache"),
    "airway": ("anaphylaxis_pattern", "تورم بالفم/الحلق مع صعوبة تنفس أو تورم الحلق/اللسان",
               "Mouth/throat swelling or severe allergic reaction"),
    "self_harm": ("self_harm_risk", "أفكار أو نية لإيذاء النفس", "Thoughts or intent to self-harm"),
    "dying": ("feeling_of_dying", "شعور شديد بقرب الموت", "Overwhelming feeling of impending death"),
    "overdose": ("overdose_poisoning", "اشتباه جرعة زائدة أو تسمم", "Possible overdose or poisoning"),
}


def _live(rx: re.Pattern, text_n: str) -> bool:
    """True if ``rx`` matches at least once without being negated."""
    for m in rx.finditer(text_n):
        if not clinical_text.occurrence_is_negated(text_n, m.start()):
            return True
    return False


def evaluate(text: str, *, skip_stroke: bool = False) -> list[tuple[str, str, str]]:
    """Return emergency rules triggered by colloquial wording in ``text``."""
    text_n = clinical_text.normalize_clinical_text(text)
    if not text_n:
        return []
    hits: list[str] = []
    past = _resolved_past(text_n)

    if not past:
        # Chest: chest word + pain word + (intensity | radiation | sweating | numbness)
        if _live(_RX_CHEST, text_n) and _live(_RX_PAIN, text_n) and (
            _live(_RX_INTENSE, text_n) or _live(_RX_RADIATE, text_n)
            or _live(_RX_SWEAT, text_n) or _live(_RX_NUMB, text_n)
        ):
            hits.append("chest")
        elif _live(_RX_CHEST_HEAVY, text_n):
            hits.append("chest")
        if _live(_RX_HEART_STOP, text_n):
            hits.append("heart")
        if _live(_RX_BREATH, text_n):
            hits.append("breath")
        if not skip_stroke and (_live(_RX_FACE, text_n) or _live(_RX_LIMB, text_n)
                                or (_live(_RX_SPEECH, text_n) and not _RX_SPEECH_EXPLAINED.search(text_n))):
            hits.append("stroke")
        if _live(_RX_VISION, text_n):
            hits.append("vision")
        if (_live(_RX_COLLAPSE, text_n) and _live(_RX_NOT_RESPONDING, text_n)) or _live(_RX_UNRESP_STRONG, text_n):
            hits.append("uncon")
        if _live(_RX_SEIZE_FOAM, text_n) or (
            _live(_RX_SEIZE_EYES, text_n) and (_live(_RX_SEIZE_SHAKE, text_n) or _live(_RX_SEIZE_VERB, text_n))
        ) or (_live(_RX_SEIZE_VERB, text_n) and _NOW.search(text_n)):
            hits.append("seizure")
        if _live(_RX_SEIZE_PROLONGED, text_n):
            hits.append("seizure_long")
        if _live(_RX_BLEED_QUAL, text_n) or _live(_RX_BLEED_NOSTOP, text_n):
            hits.append("bleed")
        if _live(_RX_BLOOD_FROM_MOUTH, text_n):
            hits.append("blood_mouth")
        if _live(_RX_PREGNANT, text_n):
            if _live(_RX_BLEED_ANY, text_n) and _live(_RX_PREG_SEVERE, text_n):
                hits.append("preg")
            if _live(_RX_FETAL_NOMOVE, text_n) and _live(_RX_SEVERE_HEADACHE, text_n):
                hits.append("preg_neuro")
        if _live(_RX_AIRWAY_SWELL, text_n) or (_live(_RX_ALLERGY_SEVERE, text_n) and _live(_RX_BREATH_MILD, text_n)):
            hits.append("airway")
        if _live(_RX_DYING, text_n):
            hits.append("dying")

    # Self-harm and ingestion stay urgent even when the wording sounds past-tense.
    if _live(_RX_SELF_HARM, text_n) or (_live(_RX_LIFE_WEARY, text_n) and _live(_RX_WISH_END, text_n)):
        hits.append("self_harm")
    if _live(_RX_OVERDOSE, text_n) or _live(_RX_TOXIC, text_n):
        hits.append("overdose")

    out, seen = [], set()
    for key in hits:
        rule = _RULES[key]
        if rule[0] not in seen:
            seen.add(rule[0])
            out.append(rule)
    return out
