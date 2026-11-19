"""Duration, severity, worsening and functional impact read from free text (V286).

Why: the triage layer decides "needs a doctor soon" mostly from the structured
answers (duration, severity 1–5). When a person only writes a sentence —
«لي أربعة أيام والحرارة ما نزلت وتعبي يزيد» — those answers are missing and the
case fell to "low". This module reads them from the sentence itself.

Safety contract (enforced by tests/test_v286_text_context.py):
  * RAISE-ONLY. The result can only move a case up, never down. A severity read
    from text is combined with the selected severity by max(); text never lowers it.
  * CAPPED. Text alone can reach at most "medical assessment today" (severity 4);
    an emergency still needs a deterministic red-flag rule.
  * EXPLAINED. Every finding carries the user's own words (a slice of their text),
    which the triage reason quotes.
  * NEGATION-AWARE. "without severe pain", «مو قاعد يزيد» are ignored.
"""
from __future__ import annotations

import re
from functools import lru_cache

import clinical_text

ENABLED = True  # switched off only by the evaluator's ablation

# Arabic letter variants inside patterns (raw text is matched so quotes stay verbatim).
_A = "[اأإآ]"
_H = "[ةه]"
_Y = "[يى]"
_B = r"(?<![\w؀-ۿ])"   # word start
_E = r"(?![\w؀-ۿ])"    # word end

_NUM_WORDS = {
    # English
    "one": 1, "a": 1, "an": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "several": 3, "few": 3, "a few": 3, "couple of": 2, "a couple of": 2, "many": 4,
    # Arabic (normalised spelling; matching is done on normalised words)
    "واحد": 1, "يوم": 1, "ثلاث": 3, "ثلاثه": 3, "تلات": 3, "اربع": 4, "اربعه": 4, "خمس": 5, "خمسه": 5,
    "ست": 6, "سته": 6, "سبع": 7, "سبعه": 7, "ثمان": 8, "ثمانيه": 8, "تسع": 9, "تسعه": 9, "عشر": 10, "عشره": 10,
    "كم": 3, "كذا": 3, "عده": 3, "بضع": 3, "بضعه": 3,
}
_UNIT_DAYS = {
    "minute": 1 / 1440, "minutes": 1 / 1440, "hour": 1 / 24, "hours": 1 / 24, "day": 1, "days": 1,
    "week": 7, "weeks": 7, "month": 30, "months": 30, "year": 365, "years": 365,
    "دقيقه": 1 / 1440, "دقايق": 1 / 1440, "دقائق": 1 / 1440, "ساعه": 1 / 24, "ساعات": 1 / 24,
    "يوم": 1, "ايام": 1, "اسبوع": 7, "اسابيع": 7, "اسبوعين": 14, "يومين": 2, "شهر": 30, "اشهر": 30, "شهور": 30,
    "شهرين": 60, "سنه": 365, "سنين": 365, "سنوات": 365,
}

_EN_DURATION = re.compile(
    r"\b(?:for|lasting|over|since|past|the\s+last|more\s+than|for\s+more\s+than|about|around)\s+(?:the\s+(?:past|last)\s+)?"
    r"(?P<num>\d+|one|two|three|four|five|six|seven|eight|nine|ten|several|a\s+few|few|a\s+couple\s+of|couple\s+of|many|a|an)\s+"
    r"(?P<unit>minutes?|hours?|days?|weeks?|months?|years?)\b"
    r"|\b(?P<num2>\d+|one|two|three|four|five|six|seven|eight|nine|ten|several)[-\s](?P<unit2>days?|weeks?|months?)\s+(?:of|long|now)\b"
    r"|\b(?P<num3>several|a\s+few|few|many|\d+|two|three|four|five|six|seven|eight|nine|ten)\s+(?P<unit3>days?|weeks?|months?)\b",
    re.IGNORECASE,
)
_AR_PREFIX = rf"(?:من|منذ|صار\s+لي|صار\s+له|صار\s+لها|لي|له|لها|لنا|خلال|طول|هال|اخر|آخر|قبل|من\s+قبل|ل{_A}كثر\s+من|{_A}كثر\s+من|حوالي|تقريبا)"
_AR_DURATION = re.compile(
    rf"{_B}(?:{_AR_PREFIX}\s+)+(?:(?P<num>\d+|[؀-ۿ]+)\s+)?(?P<unit>{_Y}وم|{_Y}ومين|{_A}{_Y}ام|{_A}سبوع|{_A}سبوعين|{_A}سابيع|شهر|شهرين|{_A}شهر|شهور|سن{_H}|سنين|سنوات|ساع{_H}|ساعات|دق{_Y}ق{_H}|دقا{_Y}ق){_E}"
    rf"|{_B}هال{_A}?(?P<unit2>{_A}{_Y}ام|{_A}سابيع|شهور|فتر{_H}){_E}",
)
# "for months", "over the last month", "this month": no number, but clearly a long duration
_EN_BARE = re.compile(r"\b(?:for|over|lasting|during)\s+(?:the\s+(?:last|past)\s+)?(?P<u>weeks|months|years|month|week|year)\b"
                      r"|\b(?P<u2>this|last|past)\s+(?P<u3>month|week|year)\b", re.I)
_SINCE_YESTERDAY = re.compile(rf"{_B}(?:من\s+{_A}مس|من\s+البارح{_H}?|since\s+yesterday|from\s+yesterday){_E}", re.IGNORECASE)

_WORSENING = (
    "worsening", "getting worse", "gets worse", "increasing", "keeps increasing", "not improving", "no better", "not getting better",
    "يزيد", "تزيد", "قاعد يزيد", "قاعده تزيد", "يزداد", "تزداد", "يسوء", "تسوء", "يتفاقم", "ازداد", "زاد", "زادت",
    "ما تحسن", "ما تحسنت", "ماتحسن", "ما نزلت", "ما نزل", "ما خفت", "ما خف", "ما راح", "ما راحت", "لم يتحسن", "لم تتحسن",
    "كل مره يزيد", "كل مره اسوا", "ازود", "اسوا",
)
_IMPACT = (
    "difficulty swallowing", "trouble swallowing", "painful swallowing", "can't swallow", "cannot swallow", "unable to swallow",
    "unable to bear weight", "can't bear weight", "cannot bear weight", "can't walk", "cannot walk", "unable to walk", "affecting walking",
    "can't sleep", "cannot sleep", "keeps me awake", "unable to work", "can't work", "missing work", "can't eat", "unable to eat",
    "ما اقدر ابلع", "ما اقدر ابلع الاكل", "صعوبه في البلع", "صعوبه البلع", "ما اقدر امشي", "ما اقدر ادوس", "ما اقدر اوقف عليها",
    "interferes with sleep", "interfering with sleep", "interferes with work", "interfering with study or work", "interfering with work",
    "affecting work", "affecting my work", "affecting daily life", "يأثر على نومي", "يأثر على شغلي", "مأثر على دراستي",
    "ما اقدر انام", "ما نمت من", "ما اقدر اشتغل", "ما رحت الدوام", "ما اقدر اكل", "ما لي نفس اكل", "مالي نفس اكل", "ما اقدر احرك",
)
_PERSISTENT = ("persistent", "persisting", "ongoing", "recurrent", "keeps coming back", "repeated episodes", "repeatedly",
               "مستمر", "مستمره", "متكرر", "متكرره", "كل شوي", "كل يوم", "يرجع", "ترجع", "يجيني كثير", "صار يجيني")
# V287: a fever together with one focal problem needs a doctor even when it is short (NHS: ear infection,
# urinary infection, tonsillitis with difficulty swallowing, dental abscess, cellulitis).
_FOCAL = ("ear pain", "earache", "pain in the ear", "burning urination", "burning when urinating", "pain when urinating", "painful urination",
          "side pain", "pain in the side", "flank pain", "tooth pain", "toothache", "facial swelling", "swollen face", "spreading redness",
          "rash", "swollen joint", "hot swollen",
          "اذنه توجعه", "اذنها توجعها", "اذني توجعني", "الم في الاذن", "وجع اذن", "حرقان في البول", "حرقه في البول", "يحرقني البول",
          "جنبي يعورني", "الم في الجنب", "ضرسي يعورني", "الم في الضرس", "وجهي منتفخ", "خدي منتفخ", "طفح", "احمرار يكبر", "مفصل منتفخ")
_FEEDING = ("less than half", "feeding less", "eating less than half", "not feeding", "poor feeding", "fewer wet nappies", "fewer wet diapers",
            "dry mouth", "ما يرضع زين", "رضاعته قلت", "يرضع اقل", "قلت الحفاضات", "فمه ناشف", "فمها ناشف")
_CROUP = ("barking cough", "كحه نباحيه", "كحه زي النباح", "كحته زي الكلب")
_PAIN = ("pain", "painful", "ache", "aching", "hurts", "sore", "limping", "الم", "وجع", "يعور", "يعوره", "يعورني", "توجعه", "يوجع", "يوجعني",
         "توجعني", "تعورني", "اعرج", "يعرج", "تعرج")
# V290: diarrhoea lasting 3 days or more (CDC / Mayo Clinic: adults with diarrhoea beyond 2 days should contact a doctor)
_DIARRHOEA = ("diarrhea", "diarrhoea", "loose stools", "loose stool", "runny stools", "اسهال", "إسهال", "اسهال شديد", "بطني ماشي")
_VOMIT = ("vomit", "vomiting", "يستفرغ", "استفراغ", "تستفرغ", "قيء")
# V289: symptom combinations that need a doctor within a day or two even without a duration.
# Each combination: (id, reason_ar, reason_en, [word groups that must ALL be present, unnegated]).
_C = {
    "red_eye": ("red eye", "red eyes", "eye is red", "عيني محمره", "عيني حمرا", "عيوني حمرا", "احمرار في العين", "عيني محمرة"),
    "eye_pain": ("painful red eye", "eye pain", "eye hurts", "painful eye", "توجعني", "تعورني", "الم في العين", "عيني توجعني", "عيني تعورني"),
    "light": ("light sensitivity", "sensitive to light", "light hurts", "bright light hurts", "الضوء يزعجني", "النور يضايقني", "الضوء يضايقني",
              "حساسيه من الضوء", "النور يزعجني"),
    "palp": ("palpitations", "racing heart", "heart racing", "heart pounding", "خفقان", "قلبي يدق بسرعه", "قلبي يدق بسرعة"),
    "recurrent": ("recurrent", "repeatedly", "keeps happening", "episodes", "كل شوي", "يجيني", "كثير", "متكرر", "هالفتره"),
    "dizzy": ("dizzy", "dizziness", "lightheaded", "lightheadedness", "light-headed", "دوخه", "دايخ", "دوار", "احس بدوخه"),
    "burning_pee": ("burning when urinating", "burning urination", "stinging when i pee", "pain when urinating", "painful urination",
                    "it burns when i pee", "burning when i pee", "burning when i wee", "burns when i pee", "pain when i pee", "stings when i urinate",
                    "stings when i pee", "it stings when i urinate", "يحرقني وقت التبول", "حرقان في البول", "حرقه في البول", "يحرقني البول",
                    "الم وقت التبول", "حرقان البول", "حرقان مع التبول", "حرقه مع التبول", "حرقان مع البول", "حرقان وقت التبول"),
    "frequent_pee": ("needing to go all the time", "frequent urination", "going to the toilet a lot", "passing a lot of urine", "urinating a lot",
                     "اروح الحمام كل شوي", "اروح الحمام كثير", "اتبول كثير", "كثره التبول"),
    "thirst": ("very thirsty", "thirsty all the time", "excessive thirst", "persistent thirst", "constant thirst", "اعطش كثير", "عطشان دايم", "اعطش", "عطش شديد"),
    "skin_red": ("red, warm", "red and warm", "redness is spreading", "redness spreading", "احمر وحار", "صار احمر وحار", "احمرار يكبر"),
    "skin_swollen_spread": ("swollen", "spreading", "منتفخ", "يكبر", "يتوسع"),
    "blood_urine_stool": ("blood in my urine", "blood in urine", "blood in my stool", "blood in stool", "دم في البول", "دم في البراز", "دم مع البراز"),
    "lump": ("new lump", "a lump", "lump in", "كتله", "كتلة", "ورم جديد"),
    "lump_persist": ("hasn't gone away", "has not gone away", "not going away", "growing", "ما راحت", "ما راح", "تكبر", "يكبر"),
    "breast_lump": ("breast lump", "lump in my breast", "lump in the breast", "كتله في الثدي", "كتلة في الثدي"),
    "blister_rash": ("blistering rash", "rash with blisters", "blisters", "طفح فيه فقاعات", "حبوب مايه", "فقاعات"),
    "one_side_pain": ("one-sided", "one side", "painful", "burning skin pain", "جهه وحده", "يحرق", "مؤلم"),
    "recurrent_symptom": ("recurrent", "recurring", "repeated", "keeps coming back", "repeatedly", "يتكرر", "متكرر", "يرجع كل شوي"),
    # V290: pus / abscess, and a toothache with swelling (NHS: see a GP for a skin abscess; a dentist urgently for a dental abscess)
    "pus": ("pus", "leaking pus", "abscess", "a boil", "صديد", "قيح", "خراج", "دمل", "دمله"),
    "tooth": ("tooth", "teeth", "toothache", "molar", "gum", "gums", "سن", "سني", "اسنان", "اسناني", "ضرس", "ضرسي", "لثه", "لثتي"),
    "face_swelling": ("swollen", "swelling", "منتفخ", "منتفخه", "متورم", "متورمه", "تورم", "انتفاخ", "وارم"),
    "weight_loss": ("losing weight without trying", "unexplained weight loss", "weight loss without", "وزني ينزل بدون سبب", "نزل وزني بدون سبب",
                    "نزل وزني كثير", "ينزل وزني"),
}
_COMBOS = (
    ("red_eye", "عين حمراء مؤلمة مع حساسية من الضوء تحتاج فحص عيون قريبًا", "A painful red eye with light sensitivity needs an eye check soon",
     (("red_eye", "eye_pain"), ("light",))),
    ("palpitations", "خفقان متكرر مع دوخة يحتاج تقييم القلب قريبًا", "Recurrent palpitations with dizziness need a heart check soon",
     (("palp",), ("recurrent",), ("dizzy",))),
    ("urinary", "حرقان التبول مع كثرته قد يكون التهاب مسالك يحتاج طبيبًا أو صيدليًا قريبًا",
     "Burning and frequent urination may be a urinary infection that needs a doctor or pharmacist soon",
     (("burning_pee",), ("frequent_pee",))),
    ("cellulitis", "احمرار حار متورم يتوسع في الجلد قد يكون التهابًا جلديًا يحتاج طبيبًا قريبًا",
     "Red, warm skin that is swollen and spreading may be a skin infection that needs a doctor soon",
     (("skin_red",), ("skin_swollen_spread",))),
    ("diabetes_signs", "العطش الشديد مع كثرة التبول قد يكونان علامة سكري ويحتاجان فحصًا قريبًا",
     "Strong thirst with passing a lot of urine can be a sign of diabetes and needs a check soon",
     (("thirst",), ("frequent_pee",))),
    ("blood", "الدم في البول أو البراز يحتاج مراجعة طبيب قريبًا حتى لو لم يكن معه ألم",
     "Blood in the urine or stool needs a doctor's review soon, even without pain",
     (("blood_urine_stool",),)),
    ("lump", "كتلة جديدة لا تختفي تحتاج فحصًا عند الطبيب", "A new lump that does not go away needs a doctor's examination",
     (("lump",), ("lump_persist",))),
    ("weight_loss", "نزول الوزن بدون سبب يحتاج تقييمًا طبيًا", "Unexplained weight loss needs medical assessment",
     (("weight_loss",),)),
    ("breast_lump", "كتلة في الثدي تحتاج فحصًا عند الطبيب", "A breast lump needs a doctor's examination",
     (("breast_lump",),)),
    ("shingles", "طفح مؤلم فيه فقاعات في جهة واحدة قد يكون حزامًا ناريًا، وعلاجه أفضل في أول أيام",
     "A painful blistering rash on one side may be shingles, and treatment works best in the first days",
     (("blister_rash",), ("one_side_pain",))),
    ("urinary_single", "حرقان أو ألم التبول يحتاج طبيبًا أو صيدليًا قريبًا", "Burning or painful urination needs a doctor or pharmacist soon",
     (("burning_pee",),)),
    ("abscess", "صديد أو خراج يحتاج فحص طبيب قريبًا، وقد يحتاج تصريفًا أو علاجًا", "Pus or an abscess needs a doctor's examination soon; it may need draining or treatment",
     (("pus",),)),
    ("dental_swelling", "ألم الأسنان مع انتفاخ قد يكون خراجًا يحتاج طبيب أسنان قريبًا", "Tooth pain with swelling may be an abscess that needs a dentist soon",
     (("tooth",), ("face_swelling",))),
    ("recurrent", "أعراض تتكرر تحتاج تقييمًا عند الطبيب لمعرفة السبب", "Symptoms that keep coming back need a doctor's assessment to find the cause",
     (("recurrent_symptom",),)),
)
COMBOS_ENABLED = True


def _combo(raw: str) -> dict | None:
    for cid, ar, en, groups in _COMBOS:
        quotes = []
        for alternatives in groups:
            hit = None
            for name in alternatives:
                hit = _find(raw, _C[name])
                if hit:
                    break
            if not hit:
                break
            quotes.append(hit["quote"])
        else:
            return {"id": cid, "ar": ar, "en": en, "quotes": quotes}
    return None


_SEVERE = ("severe", "intense", "terrible", "unbearable", "excruciating", "very bad", "really bad", "a lot of pain",
           "شديد", "شديده", "قوي", "قويه", "بقوه", "بشده", "ما يتحمل", "ما ينطاق", "ما اتحمل", "فظيع", "مره قوي")
_MODERATE = ("moderate", "متوسط", "متوسطه")


def _neg(raw: str, start: int) -> bool:
    norm = clinical_text.normalize_clinical_text(raw[:start]).replace("|", " | ")
    return clinical_text.occurrence_is_negated(norm + " x", len(norm) + 1)


def _find(raw: str, phrases) -> dict | None:
    """First unnegated phrase occurrence, with its verbatim slice."""
    norm = clinical_text.normalize_clinical_text(raw)
    for phrase in phrases:
        for m in clinical_text._phrase_pattern(phrase).finditer(norm):
            if clinical_text.occurrence_is_negated(norm, m.start()) or _in_negated_list(norm, m.start()):
                continue
            quote = _verbatim(raw, m.group(0))
            return {"quote": quote or m.group(0)}
    return None


_LIST_NEGATOR = re.compile(r"(?:^|\s)(?:without|no|not|بدون|ولا|لا|ما فيه|ما فيها|ما عندي|ما عنده|ما عندها)\s+((?:\S+\s+){0,3})$")
_LIST_BREAK = re.compile(r"(?:^|\s)(?:but|with|and now|لكن|بس|مع)(?:\s|$)")


def _in_negated_list(norm: str, start: int) -> bool:
    """V290: an item later in a negated list — "without pain, pus or hair loss" — is negated too.
    The negator must be in the same clause, at most three words earlier, with no "but / with" between."""
    before = norm[:start].split("|")[-1]
    m = _LIST_NEGATOR.search(before)
    return bool(m) and not _LIST_BREAK.search(m.group(1))


def _verbatim(raw: str, normalized_piece: str) -> str:
    """Locate the original words for a normalised match (same word count)."""
    words = normalized_piece.split()
    raw_words = re.findall(r"\S+", raw)
    norm_words = [clinical_text.normalize_clinical_text(w).replace("|", "").strip() for w in raw_words]
    n = len(words)
    for i in range(len(raw_words) - n + 1):
        window = " ".join(w for w in norm_words[i:i + n] if w)
        if words and window == " ".join(words):
            return " ".join(raw_words[i:i + n]).strip("،,.;:!?؟")
    return ""


def _number(token: str | None) -> float:
    if not token:
        return 1
    t = clinical_text.normalize_clinical_text(token).strip()
    if t.isdigit():
        return float(t)
    t = re.sub(r"\s+", " ", t)
    return float(_NUM_WORDS.get(t, _NUM_WORDS.get(t.replace("ه", ""), 1)))


def _duration(raw: str) -> dict | None:
    best = None
    text = raw.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    for m in _EN_DURATION.finditer(text):
        num = m.group("num") or m.group("num2") or m.group("num3")
        unit = (m.group("unit") or m.group("unit2") or m.group("unit3")).lower()
        days = _number(num) * _UNIT_DAYS.get(unit, _UNIT_DAYS.get(unit.rstrip("s"), 1))
        if "more than" in m.group(0).lower():
            days += 0.5
        if best is None or days > best["days"]:
            best = {"days": days, "quote": m.group(0).strip()}
    for m in _AR_DURATION.finditer(text):
        unit = clinical_text.normalize_clinical_text(m.group("unit") or m.group("unit2") or "")
        if m.group("unit2"):
            days = {"ايام": 3, "اسابيع": 14, "شهور": 60, "فتره": 7}.get(unit, 3)
        else:
            num = m.group("num")
            n_norm = clinical_text.normalize_clinical_text(num or "")
            if num and not n_norm.isdigit() and n_norm not in _NUM_WORDS:
                num = None  # a word that is not a number ("من بطني يوم ..."): count as 1
            fixed = {"يومين": 2, "اسبوعين": 14, "شهرين": 60}
            days = fixed[unit] if unit in fixed else _number(num) * _UNIT_DAYS.get(unit, 1)
            if re.search(rf"{_A}كثر\s+من", m.group(0)):
                days += 0.5
        if best is None or days > best["days"]:
            best = {"days": days, "quote": m.group(0).strip()}
    for m in _EN_BARE.finditer(text):
        unit = (m.group("u") or m.group("u3") or "").lower().rstrip("s")
        days = {"week": 7, "month": 30, "year": 365}[unit] * (2 if (m.group("u") or "").lower().endswith("s") else 1)
        if best is None or days > best["days"]:
            best = {"days": days, "quote": m.group(0).strip()}
    if best is None:
        m = _SINCE_YESTERDAY.search(text)
        if m:
            best = {"days": 1, "quote": m.group(0).strip()}
    return best


_UNIT_WORDS_AR = ("يوم", "يومين", "ايام", "اسبوع", "اسبوعين", "اسابيع", "شهر", "شهرين", "اشهر", "شهور", "سنه", "سنين", "سنوات",
                  "ساعه", "ساعات", "دقيقه", "دقائق", "حراره", "حرارتي", "حرارته", "الحراره", "من", "منذ", "لي", "صار")


@lru_cache(maxsize=1)
def known_words() -> frozenset[str]:
    """Normalised Arabic words this layer reads (for typo correction and Arabizi)."""
    words: set[str] = set(_UNIT_WORDS_AR) | {w for w in _NUM_WORDS if re.search(r"[\u0600-\u06ff]", w)}
    for group in (_WORSENING, _IMPACT, _PERSISTENT, _SEVERE, _MODERATE, _FOCAL, _FEEDING, _CROUP, _PAIN, _VOMIT, _DIARRHOEA, *_C.values()):
        for phrase in group:
            words |= {t for t in clinical_text.normalize_clinical_text(phrase).split() if re.search(r"[\u0600-\u06ff]", t)}
    return frozenset(words)


@lru_cache(maxsize=1)
def _vocab_index() -> dict[tuple[str, int], tuple[str, ...]]:
    idx: dict[tuple[str, int], list[str]] = {}
    numbers = set(_NUM_WORDS)
    for w in known_words():
        if len(w) >= 5 and w not in numbers:  # short words and numbers are too close to ordinary words
            idx.setdefault((w[0], len(w)), []).append(w)
    return {k: tuple(v) for k, v in idx.items()}


def _one_edit(a: str, b: str) -> bool:
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    if len(a) > len(b):
        a, b = b, a
    return any(a == b[:i] + b[i + 1:] for i in range(len(b)))


def _fix_word(word: str) -> str:
    """One-letter typo in an Arabic duration/severity word ("اسابع" -> "اسابيع"); prefixes kept."""
    norm = clinical_text.normalize_clinical_text(word)
    if not norm or " " in norm or not re.search(r"[\u0600-\u06ff]", norm) or norm in known_words():
        return word
    prefixes = [p for p in ("", "و", "هال", "ال", "وال", "ب", "ل") if norm.startswith(p)]
    if any(norm[len(p):] in known_words() for p in prefixes):
        return word
    import arabic_lexicon
    if arabic_lexicon.is_real_word(norm):  # V290: real words are never "corrected"
        return word
    for prefix in prefixes:
        core = norm[len(prefix):]
        if len(core) < 4:
            continue
        idx = _vocab_index()
        near = [w for n in (len(core) - 1, len(core), len(core) + 1) for w in idx.get((core[0], n), ()) if _one_edit(core, w)]
        if len(near) == 1:
            return prefix + near[0]
    return word


def _prepare(raw: str) -> str:
    """Arabizi -> Arabic, then one-letter typo fixes, word count preserved."""
    import arabizi
    text = arabizi.to_arabic(raw)
    out = []
    for w in text.split(" "):
        m = re.match(r"^(.*?)([.,،؛;:!?؟]*)$", w)
        out.append(_fix_word(m.group(1)) + m.group(2))
    return " ".join(out)


@lru_cache(maxsize=1024)
def _extract(raw: str) -> dict:
    raw = _prepare(raw)
    fever = clinical_text.contains_unnegated_any(raw, (
        "fever", "high temperature", "febrile", "حراره", "الحراره", "حرارتي", "حرارته", "حرارتها", "حمى", "سخونه", "مسخن", "مسخنه"))
    severe = _find(raw, _SEVERE)
    moderate = None if severe else _find(raw, _MODERATE)
    return {
        "duration": _duration(raw),
        "worsening": _find(raw, _WORSENING),
        "impact": _find(raw, _IMPACT),
        "persistent": _find(raw, _PERSISTENT),
        "combo": _combo(raw) if COMBOS_ENABLED else None,
        "focal": _find(raw, _FOCAL),
        "feeding": _find(raw, _FEEDING),
        "croup": _find(raw, _CROUP),
        "pain": _find(raw, _PAIN),
        "vomit": _find(raw, _VOMIT),
        "diarrhoea": _find(raw, _DIARRHOEA),
        "severity": ({"level": 4, **severe} if severe else ({"level": 3, **moderate} if moderate else None)),
        "fever": fever,
    }


def extract(text: str) -> dict:
    """Findings read from free text. Empty findings when the layer is switched off."""
    if not ENABLED:
        return {"duration": None, "worsening": None, "impact": None, "persistent": None, "severity": None, "fever": False,
                "focal": None, "feeding": None, "croup": None, "pain": None, "vomit": None, "combo": None}
    return _extract(str(text or ""))


def triage_signal(text: str, lang: str = "ar") -> tuple[str, str] | None:
    """("soon" | "today", reason quoting the user's words) or None.

    Order is from the most to the least specific; only one reason is returned so the
    message stays readable. Never returns "emergency"."""
    import temporal_context
    f = extract(temporal_context.current_text(text))  # V290: past history is not a current duration
    ar = lang != "en"
    days = (f["duration"] or {}).get("days") or 0
    q = lambda d: "«" + d["quote"] + "»" if ar else "“" + d["quote"] + "”"  # noqa: E731
    if f["severity"] and f["severity"]["level"] >= 4:
        return "today", (f"وصفتَ الأعراض بأنها شديدة ({q(f['severity'])})، وتحتاج تقييمًا طبيًا اليوم" if ar
                         else f"You described the symptoms as severe ({q(f['severity'])}); this needs medical assessment today")
    if f["fever"] and days >= 3:
        return "soon", (f"حرارة مستمرة ({q(f['duration'])}) — الحمى التي تستمر 3 أيام أو أكثر تحتاج مراجعة طبيب" if ar
                        else f"Fever ({q(f['duration'])}) — a fever that lasts 3 days or more needs a doctor's review")
    if f["fever"] and f["focal"]:
        return "soon", (f"حرارة مع {q(f['focal'])} — قد تكون عدوى تحتاج فحص طبيب" if ar
                        else f"Fever with {q(f['focal'])} — this may be an infection that needs a doctor's examination")
    if f["combo"]:
        c = f["combo"]
        words = ("، ".join("«" + x + "»" for x in c["quotes"])) if ar else (", ".join("\u201c" + x + "\u201d" for x in c["quotes"]))
        return "soon", (f"{c['ar']} ({words})" if ar else f"{c['en']} ({words})")
    if f["feeding"]:
        return "soon", (f"قلة الرضاعة أو الشرب أو علامات جفاف بسيطة ({q(f['feeding'])}) تحتاج تقييمًا قريبًا" if ar
                        else f"Reduced feeding or drinking, or mild dehydration signs ({q(f['feeding'])}), need assessment soon")
    if f["croup"]:
        return "soon", (f"الكحة النباحية ({q(f['croup'])}) قد تكون خانوقًا؛ يحتاج تقييمًا، واطلب الطوارئ إذا ظهر صوت مع النفس وهو مرتاح" if ar
                        else f"A barking cough ({q(f['croup'])}) may be croup; get it assessed, and call emergency if there is noisy breathing at rest")
    if f["impact"]:
        return "soon", (f"الأعراض تؤثر على حياتك اليومية ({q(f['impact'])})، فتحتاج مراجعة طبيب قريبًا" if ar
                        else f"The symptoms affect daily activities ({q(f['impact'])}), so they need a doctor's review soon")
    if f["worsening"] and (days >= 2 or f["fever"] or f["persistent"]):
        return "soon", (f"الأعراض تزداد ({q(f['worsening'])})، وتحتاج مراجعة طبيب قريبًا" if ar
                        else f"The symptoms are getting worse ({q(f['worsening'])}) and need a doctor's review soon")
    if f["persistent"] and days >= 3:
        return "soon", (f"الأعراض مستمرة ({q(f['persistent'])}، {q(f['duration'])})، وتحتاج مراجعة طبيب قريبًا" if ar
                        else f"The symptoms are persistent ({q(f['persistent'])}, {q(f['duration'])}) and need a doctor's review soon")
    if days >= 3 and (f["pain"] or f["vomit"]):
        return "soon", (f"ألم أو قيء مستمر {q(f['duration'])} يحتاج مراجعة طبيب" if ar
                        else f"Pain or vomiting lasting {q(f['duration'])} needs a doctor's review")
    if days >= 3 and f.get("diarrhoea"):
        return "soon", (f"إسهال مستمر {q(f['duration'])} يحتاج مراجعة طبيب، واشرب سوائل كافية" if ar
                        else f"Diarrhoea lasting {q(f['duration'])} needs a doctor's review; keep drinking fluids")
    if days >= 7:
        return "soon", (f"الأعراض مستمرة منذ مدة ({q(f['duration'])})، والأعراض التي تستمر أسبوعًا أو أكثر تحتاج مراجعة طبيب" if ar
                        else f"Symptoms have lasted a while ({q(f['duration'])}); symptoms lasting a week or more need a doctor's review")
    if f["severity"] and f["severity"]["level"] == 3:
        return "soon", (f"وصفتَ الأعراض بأنها متوسطة ({q(f['severity'])})" if ar
                        else f"You described the symptoms as moderate ({q(f['severity'])})")
    return None
