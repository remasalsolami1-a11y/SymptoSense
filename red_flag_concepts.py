"""Compositional red-flag concepts (V284).

Why this exists
---------------
The original red-flag layer matches fixed phrases. It passes its own regression
suite (47/47) but, on 180 independent vignettes, recognised only about half of the
urgent cases: a new wording ("انتفخت شفايفي ولساني" instead of "تورم اللسان") or a
dropped letter is enough to miss a rule.

This layer describes red flags the way clinical guidance does — as *combinations of
concepts* — and recognises each concept from interchangeable words that may appear
in any order inside the same clause:

    concept  = phrases  OR  (word from group A  +  word from group B, same clause)
    red flag = combination of concepts      e.g. head injury + (repeated vomiting |
                                                 drowsiness | confusion | seizure)

Robustness:
  * Arabic forms with attached pronouns / articles are generated (لسان -> لساني، اللسان…);
  * one-letter typing slips in long words are corrected against the concept
    vocabulary *before* matching (Levenshtein distance 1, same first letter);
  * negation uses clinical_text (the same rules as the rest of the engine), so
    "ما عندي ضيق تنفس" does not count.

It only ever ADDS emergency flags (it cannot clear one raised by another layer).
Every rule below is pending clinical sign-off (see CLINICAL_REVIEW_PACKET_AR.md);
its effect is measured by tools/evaluate_engine.py on a held-out test set.
"""
from __future__ import annotations

import re
from functools import lru_cache

import arabic_lexicon
import arabizi
import clinical_text

_AR = re.compile(r"[؀-ۿ]")
_SUFFIXES = ("", "ي", "ه", "ها", "هم", "نا", "ك")
_PREFIXES = ("", "ال", "بال", "ب", "لل", "وال")


def _forms(word: str) -> set[str]:
    """Normalised surface forms of a single Arabic noun/verb; English words as is."""
    w = clinical_text.normalize_clinical_text(word)
    if " " in w or not _AR.search(w):
        return {w}
    base = w[2:] if w.startswith("ال") else w
    out = {w}
    for p in _PREFIXES:
        for s in _SUFFIXES:
            # taa marbuta (normalised to ه) becomes ت before a pronoun: رقبه -> رقبتي
            stem = base[:-1] + "ت" if s and base.endswith("ه") else base
            out.add(p + stem + s)
            if stem != base:  # V290: a root ه (وجه -> وجهي، وجهه) is not a taa marbuta
                out.add(p + base + s)
    return out


def _group(*words: str) -> tuple[str, ...]:
    out: set[str] = set()
    for w in words:
        out |= _forms(w)
    return tuple(sorted(out))


# ------------------------------------------------------------------ vocabulary
SEVERE = _group("شديد", "شديده", "قوي", "قويه", "بقوه", "مره", "حيل", "فظيع", "فظيعه", "severe", "intense", "excruciating", "worst",
                "very bad", "terrible", "awful", "unbearable")
SUDDEN = ("فجاه", "فجأة", "مفاجئ", "مفاجئه", "بشكل مفاجئ", "suddenly", "sudden", "abruptly", "all of a sudden")

def _overdose_phrases() -> tuple[str, ...]:
    en_q = ("whole bottle of", "whole box of", "whole pack of", "whole packet of", "whole strip of", "entire bottle of", "entire box of",
            "entire pack of", "too many", "a handful of", "handful of")
    en_n = ("pills", "tablets", "paracetamol", "paracetamol tablets", "panadol", "painkillers", "sleeping tablets", "sleeping pills",
            "his pills", "her pills", "my pills", "medicine", "medication", "insulin")
    ar_n = ("حبوب", "بنادول", "حبوب بنادول", "حبوب منوم", "حبوب نوم", "مسكن", "مسكنات")
    ar_q = ("كثير", "وايد", "كثيره")
    out = {f"{q} {n}" for q in en_q for n in en_n}
    out |= {f"{n} {q}" for n in ar_n for q in ar_q}
    out |= {f"{c} {n} {q}" for c in ("علبه", "شريط", "باكيت") for n in ar_n + ("دوا", "دواء") for q in ("كامله", "كامل", "كلها", "كله")}
    out |= {"علبه كامله", "العلبه كلها", "شريط كامل", "الشريط كله", "باكيت كامل", "اكثر من الجرعه", "whole bottle", "whole box",
            "whole packet", "entire bottle"}
    return tuple(sorted(out))


_OVERDOSE_PHRASES = _overdose_phrases()

# concept -> (phrases, [(group A, group B), ...])
CONCEPTS: dict[str, tuple[tuple[str, ...], list[tuple[tuple[str, ...], tuple[str, ...]]]]] = {
    "mouth_swelling": ((), [(
        _group("تورم", "متورم", "متورمه", "تورمت", "انتفاخ", "انتفخ", "انتفخت", "منتفخ", "منتفخه", "ورم", "swelling", "swollen", "swelled", "swell"),
        _group("شفايف", "شفاه", "شفتين", "شفه", "لسان", "حلق", "وجه", "lips", "lip", "tongue", "throat", "face", "facial"))]),
    "breathing": (("ما اقدر اتنفس", "نفسي مقطوع", "can't breathe", "cannot breathe", "short of breath", "shortness of breath", "breathless"), [(
        _group("نفس", "تنفس", "التنفس", "انفاس", "breathing", "breath", "breaths", "breathe"),
        _group("ضيق", "صعوبه", "مقطوع", "ضايق", "صعب", "قصير", "قصيره", "difficulty", "difficult", "trouble", "hard", "short", "laboured",
               "labored", "noisy"))]),
    # V290: cannot breathe at all, in any person ("ما يقدر يتنفس" was only matched in the first person)
    "cannot_breathe": (("ما اقدر اتنفس", "ما يقدر يتنفس", "ما تقدر تتنفس", "ما قادر اتنفس", "مو قادر يتنفس", "مو قادره تتنفس",
                        "لا يستطيع التنفس", "لا تستطيع التنفس", "can't breathe", "cannot breathe", "can not breathe", "unable to breathe",
                        "isn't breathing", "is not breathing", "not breathing", "stopped breathing", "ما يتنفس", "ما تتنفس", "وقف نفسه"), []),
    "wheeze": (_group("صفير", "يصفر", "تصفر", "ازيز", "wheeze", "wheezing", "wheezy"), []),
    "hives": (("شري", "ارتيكاريا", "hives", "urticaria"), [(
        _group("طفح", "حبوب", "rash"), ("كل جسمي", "كل الجسم", "كل جسمه", "جسمي كله", "منتشر", "منتشره", "widespread", "all over", "whole body"))]),
    "faint": (_group("اغمي", "يغمي", "بيغمي", "مغمي", "اغماء", "دوخه شديده", "فقدت الوعي", "near-fainting", "nearly fainted", "بطيح", "faint", "fainted", "fainting", "faintness",
                     "passed out", "collapsed", "light-headed", "lightheaded"), []),
    "dizzy": (_group("دوخه", "دايخ", "دايخه", "دوار", "dizzy", "dizziness"), []),
    "weak": (("ضعف شديد", "تعب شديد", "severe weakness", "very weak", "extremely weak"), []),
    "head_injury": (("head injury", "head trauma", "اصابه في الراس", "ضربه على الراس"), [(
        _group("ضربه", "انضرب", "انضربت", "اصابه", "صدمه", "طاح", "طحت", "سقط", "صقع", "صقعت", "ارتطم", "hit", "injury", "trauma",
               "bump", "bumped", "fell", "blow", "struck"),
        _group("راس", "head"))]),
    "vomit_repeated": (("repeated vomiting", "persistent vomiting", "vomiting repeatedly", "keeps vomiting", "can't stop vomiting",
                        "vomiting several times"), [(
        _group("قيء", "استفراغ", "يستفرغ", "تستفرغ", "استفرغ", "vomiting", "vomit", "vomited", "throwing up"),
        ("متكرر", "مستمر", "اكثر من مره", "كثير", "ما وقف", "ما وقفت", "وايد", "repeated", "repeatedly", "persistent", "several",
         "keeps", "constant", "again and again", "all day", "طول اليوم", "ما يوقف", "ما توقف"))]),
    "drowsy": (_group("نعسان", "نعسانه", "نعاس", "خامل", "ما يصحصح", "drowsy", "drowsiness", "sleepy", "hard to wake"), []),
    "confusion": (_group("تشوش", "مشوش", "مشوشه", "متلخبط", "متلخبطه", "هذيان", "confused", "confusion", "disoriented", "delirious",
                         "ما تعرفنا", "ما يعرفنا", "not making sense", "doesn't recognise", "doesn't recognize"), []),
    "black_stool": (("black tarry", "tarry stool", "melena", "melaena"), [(
        _group("براز", "خروج", "stool", "stools", "poop"), _group("اسود", "سوداء", "قطراني", "قار", "black", "tarry"))]),
    "abdominal_pain": ((), [(
        _group("بطن", "بطني", "abdominal", "abdomen", "stomach", "belly"),
        _group("الم", "وجع", "يوجعني", "يعورني", "يألمني", "pain", "ache", "aching"))]),
    "rigid_abdomen": (("rigid abdomen", "board-like", "مثل الخشبه", "مثل الخشب"), [(
        _group("بطن", "abdomen", "belly"), _group("متيبس", "مشدود", "قاسي", "rigid", "hard", "board"))]),
    "testicle_pain": ((), [(
        _group("خصيه", "خصيتين", "testicle", "testicular", "scrotum", "testis"),
        _group("الم", "وجع", "انتفاخ", "تورم", "pain", "swelling", "swollen"))]),
    "diabetes": (_group("سكري", "عنده سكر", "عندها سكر", "عندي سكر", "diabetic", "diabetes"), []),
    "rapid_breathing": (("deep rapid breathing", "rapid breathing", "breathing fast", "deep breathing"), [(
        _group("تنفس", "يتنفس", "تتنفس", "breathing", "breathe"), _group("سريع", "بسرعه", "عميق", "بعمق", "rapid", "fast", "deep", "deeply"))]),
    "asthma": (_group("ربو", "asthma", "asthmatic"), []),
    "reliever_failing": ((), [(
        _group("بخاخ", "فنتولين", "inhaler", "reliever", "puffer", "ventolin"),
        ("ما تحسنت", "ما تحسن", "ما نفع", "ما فاد", "ما يفيد", "لا يتحسن", "دون تحسن", "بدون فايده", "not improving", "no relief",
         "not helping", "didn't help", "not working", "doesn't help", "no better", "ما تتحسن", "لا تتحسن", "لم تتحسن", "ما يتحسن", "لم يتحسن"))]),
    "fever": (_group("حراره", "حرارتي", "حمي", "سخونه", "fever", "febrile", "high temperature"), []),
    "stiff_neck": (("stiff neck", "can't bend my neck", "cannot bend my neck", "can't touch chin to chest", "can't touch my chin to my chest",
                    "ما يقدر يحني راسه", "ما تقدر تحني راسها", "ما اقدر احني راسي"), [(
        _group("رقبه", "neck"), ("متيبسه", "متيبس", "تيبس", "stiff", "stiffness", "ما اقدر احركها", "ما يقدر يحركها", "ما تقدر تحركها",
                                 "ما اقدر احرك", "can't move", "cannot move", "can't bend", "cannot bend"))]),
    "severe_headache": ((), [(_group("صداع", "راس", "headache"), SEVERE)]),
    "photophobia": (("النور يضايقني", "حساسيه من الضوء", "light sensitivity", "sensitive to light", "photophobia"), []),
    "heavy_bleeding": ((), [(
        _group("نزيف", "نزف", "دم", "bleeding", "bleed", "blood"), _group("غزير", "قوي", "شديد", "كثير", "heavy", "heavily", "severe", "profuse", "lots"))]),
    "vision_loss": (("ما اشوف", "ما صرت اشوف", "فقدت البصر", "فقدان الرؤيه", "فقدان النظر", "can't see", "cannot see", "vision loss",
                     "lost vision", "lost my vision", "loss of vision", "went blind"), []),
    "face_droop": (("فمي مال", "فمي مايل", "وجهي مال", "وجهي مايل", "فمه مال", "وجهه مال", "تدلي الوجه", "ميلان الفم", "face droop",
                    "facial droop", "face drooping", "mouth drooped", "mouth drooping"), [(
        _group("ميلان", "مايل", "مايله", "مال", "اعوجاج", "معوج", "تدلي", "متدلي", "droop", "drooping", "drooped"),
        _group("وجه", "فم", "face", "mouth"))]),
    "limb_weak_one_side": (("weakness on one side", "one-sided weakness", "ضعف في جهه وحده", "ضعف بجهه وحده", "تنميل بجهه وحده"), [(
        _group("ضعف", "تنميل", "خدر", "weakness", "numbness"),
        _group("ذراع", "يد", "جهه وحده", "جانب واحد", "arm", "one side"))]),
    "arm_cannot_lift": (("ما اقدر ارفع يدي", "ما اقدر احرك يدي", "ما يقدر يرفع يده", "ما تقدر ترفع يدها", "can't lift my arm",
                         "cannot lift my arm", "can't raise my arm", "arm weakness"), []),
    "chest_pain": (("chest pain", "chest pressure", "chest tightness", "pain in my chest"), [(
        _group("صدر", "صدري", "chest"), _group("الم", "وجع", "يعورني", "يوجعني", "ضغط", "ضيقه", "pain", "pressure", "tightness", "ache"))]),
    "sweating": (_group("تعرق", "اعرق", "يعرق", "تعرقت", "عرق", "عرق بارد", "sweating", "sweaty", "cold sweat", "sweats"), []),
    "radiating": (("ينتشر للذراع", "ينتشر لليد", "ينتشر للفك", "يمتد لليد", "radiating", "spreading to", "spreads to", "goes to my arm",
                   "to the jaw", "to my jaw", "to the left arm", "to my left arm"), []),
    "sudden": (SUDDEN, []),
    "severe": (SEVERE, []),
    # ---- V287: error-taxonomy concepts (evaluation/taxonomy_dev_cases.json)
    "cyanosis": (("blue lips", "lips turning blue", "شفايف زرقا", "شفايفه زرقا"), [(
        _group("شفايف", "شفاه", "شفتين", "اظافر", "وجه", "lips", "lip", "face", "fingertips"),
        _group("ازرق", "زرقا", "زرقاء", "مزرقه", "blue", "bluish", "grey", "gray"))]),
    "cant_speak_breath": (("ما يقدر يكمل جمله", "ما اقدر اكمل جمله", "ما تقدر تكمل جمله", "ما يقدر يتكلم من ضيق النفس",
                           "can't finish sentences", "cannot finish sentences", "unable to finish sentences", "inability to finish sentences",
                           "can't speak full sentences", "cannot speak full sentences", "unable to speak in full sentences",
                           "too breathless to speak", "struggling for breath", "struggling to breathe", "gasping for air", "gasping for breath"), []),
    # V287 children: grunting / chest indrawing / stridor at rest are distress signs on their own
    "child_breathing_distress": (("grunting", "ribs sucks in", "ribs suck in", "ribs pulling in", "chest indrawing", "sucking in under the ribs",
                                  "retractions", "noise when breathing in even while resting", "stridor at rest",
                                  "ضلوعه تنسحب", "ضلوعها تنسحب", "صدره ينسحب", "صدرها ينسحب", "ينخر وهو يتنفس", "صوت مع النفس وهو مرتاح"), []),
    "drooling": (("drooling", "can't swallow saliva", "يسيل لعابه", "ما يقدر يبلع ريقه", "ما اقدر ابلع ريقي"), []),
    "reduced_consciousness": (("barely responsive", "reduced responsiveness", "reduced consciousness", "responds only to pain",
                               "not responding normally", "no normal response", "hard to rouse", "difficult to wake", "keeps drifting off",
                               "صعب نصحيه", "صعب يصحى", "ما يرد علينا", "ما ترد علينا", "ما يستجيب زين", "ما تستجيب زين",
                               "floppy", "hard to wake", "very hard to wake", "won't wake properly", "مرتخي", "مرتخيه", "جسمه مرتخي",
                               "ما يصحى زين", "ما تصحى زين"), []),
    "purple_rash": (("purple rash", "purple spots", "rash that does not fade", "rash doesn't fade", "does not fade when pressed",
                     "non-blanching", "بقع بنفسجيه", "طفح بنفسجي", "ما تختفي لما اضغط", "ما يختفي لما اضغط", "ما تختفي بالضغط"), [(
        _group("طفح", "بقع", "rash", "spots", "spotty"), _group("بنفسجي", "بنفسجيه", "purple"))]),
    "syncope": (_group("اغمي", "يغمي", "مغمي", "اغماء", "فقدت الوعي", "fainted", "fainting", "passed out", "collapsed", "collapse",
                       "blacked out", "lost consciousness"), []),
    "palpitations_irregular": (("irregular heartbeat", "heartbeat feels irregular", "heart racing", "خفقان", "نبض غير منتظم",
                                "دقات قلب غير منتظمه"), [(
        _group("قلب", "نبض", "دقات", "heart", "heartbeat", "pulse"),
        _group("منتظم", "غير منتظم", "سريع", "بسرعه", "irregular", "racing", "pounding", "erratic"))]),
    "exertion": (("while running", "during exercise", "on exertion", "during physical exertion", "while exercising", "وانا العب",
                  "وانا اركض", "وقت الرياضه", "مع المجهود", "اثناء الرياضه"), []),
    "no_urine": (("no urine", "hardly peeing", "barely peeing", "not peeing", "very little urine", "minimal urine", "hardly any urine",
                  "no wet nappy", "no wet nappies", "no wet diaper", "no wet diapers", "ما بلل الحفاض", "ما بللت الحفاض", "ما بلل الحفاضه",
                  "ما يتبول", "ما تتبول", "ما اتبول", "ما بال", "ما يبول", "ما بلل الحفاض", "قليل التبول"), []),
    "fluids_not_kept": (("can't keep fluids down", "can't keep any fluids down", "unable to keep fluids down", "inability to keep fluids down",
                         "can't keep anything down", "كل ما يشرب يستفرغ", "ما يثبت شي في بطنه", "يستفرغ كل شي يشربه",
                         "won't drink", "refusing to drink", "refuses to drink", "رافض يشرب", "ما يبي يشرب", "ما يرضع ابد"), []),
    "sting": (_group("لسعه", "لسعتني", "لسعني", "قرصه", "قرصتني", "قرصني", "sting", "stung"), []),
    "vomit_any": (_group("قيء", "استفراغ", "استفرغ", "يستفرغ", "تستفرغ", "vomiting", "vomit", "vomited", "throwing up"), []),
    "eye_pain": ((), [(_group("عين", "عيني", "eye"), _group("الم", "وجع", "يعورني", "توجعني", "تعورني", "pain", "ache", "painful"))]),
    "vision_blur": (("blurred vision", "blurry vision", "reduction in vision", "reduced vision", "seeing halos", "halos around lights",
                     "نظري ضبابي", "نظري صار ضبابي", "زغلله", "نظري ضعف فجاه"), []),
    "back_pain": (("back pain",), [(_group("ظهر", "ظهري", "back"), _group("الم", "وجع", "يعورني", "يوجعني", "pain", "ache"))]),
    "bladder_loss": (("loss of bladder control", "can't control my bladder", "cannot control my bladder", "can't control urine",
                      "urinary retention", "can't pee", "numbness around the groin", "saddle numbness",
                      "ما اقدر اتحكم في البول", "ما اقدر اتحكم بالبول", "فقدان التحكم في البول", "تبولت على نفسي", "خدر حول المقعده"), []),
    "leg_weak": ((), [(_group("رجل", "رجلي", "ساق", "leg", "legs"), _group("ضعيفه", "ضعيف", "ضعف", "weak", "weakness", "numb"))]),
    "cold_limb": ((), [(_group("رجل", "رجلي", "ساق", "قدم", "يد", "ذراع", "leg", "foot", "arm", "hand"),
                        _group("بارده", "بارد", "cold"))]),
    "pale_or_numb_limb": (("ما احس فيها", "ما احس فيه", "white and numb"), [(
        _group("رجل", "رجلي", "ساق", "قدم", "يد", "ذراع", "leg", "foot", "arm", "hand"),
        _group("شاحبه", "شاحب", "بيضاء", "pale", "white", "numb", "خدر", "مخدره"))]),
    "bilious_vomit": (("green vomit", "vomiting green", "vomits green", "bile-stained vomit", "يستفرغ اخضر", "استفراغ اخضر", "قيء اخضر",
                       "ترجع اخضر", "يترجع اخضر"), []),
    "infant": (_group("رضيع", "رضيعي", "رضيعه", "مولود", "baby", "infant", "newborn", "neonate"), []),
    "shaky": (_group("رجفه", "ارتجاف", "ارجف", "يرجف", "shaky", "shaking", "trembling", "tremor"), []),
    "worst_headache": (("worst headache", "the worst i have ever had", "worst i've ever had", "explosive headache",
                        "ما صار لي مثله", "ما جاني مثله", "اقوى صداع", "اسوا صداع"), []),
    "slurred_speech": (("slurred speech", "can't get words out", "can't get her words out", "can't get his words out", "words came out jumbled",
                        "words come out wrong", "words came out wrong", "يخربط بالكلام", "تخربط بالكلام", "يخربط في الكلام", "تخربط في الكلام",
                        "ما ينفهم كلامه", "ما ينفهم كلامها"), [(
        _group("كلام", "كلامي", "كلامه", "كلامها", "speech", "words"),
        ("ثقيل", "متلخبط", "متلخبطه", "مو مفهوم", "غير مفهوم", "مب مفهوم", "ما ينفهم", "مخربط", "slurred", "garbled", "jumbled", "nonsense",
         "unclear", "muddled"))]),
    # ---- V290: error types from the sealed fresh probe set (evaluation/v290_dev_cases.json)
    "grip_loss": (("ما يقدر يمسك", "ما تقدر تمسك", "ما اقدر امسك", "can't hold", "cannot hold", "can't grip", "dropping things",
                   "drops things", "يطيح الاشياء من يده", "تطيح الاشياء من يدها"), []),
    "choking": (_group("غص", "غصت", "غصيت", "شرق", "شرقت", "شرقان", "شرقانه", "انشرق", "choking", "choked", "choke") + (
        "stuck in his throat", "stuck in her throat", "stuck in my throat", "stuck in the throat", "علق في حلقه", "علق في حلقها",
        "علق في حلقي", "عالق في حلقه", "عالق في حلقي"), []),
    "swallowed_object": ((), [(
        _group("بلع", "بلعت", "بلعه", "ابتلع", "ابتلعت", "swallowed", "swallow", "inhaled"),
        _group("حبه", "قطعه", "عمله", "خرزه", "فول", "فوله", "فستق", "عنب", "peanut", "nut", "grape", "coin", "bead", "piece", "toy"))]),
    "cant_speak_or_cough": (("can't cough or speak", "cannot cough or speak", "can't speak or cough", "making no sound", "no sound",
                             "can't cry or cough", "ما يقدر يتكلم ولا يكح", "ما تقدر تتكلم ولا تكح", "ما يطلع صوت", "ما تطلع صوت",
                             "ما يقدر يتكلم", "ما تقدر تتكلم"), []),
    "dangerous_ingestion": ((), [(
        _group("بلع", "بلعت", "ابتلع", "ابتلعت", "شرب", "شربت", "اكل", "اكلت", "swallowed", "swallow", "drank", "drunk", "ate", "ingested"),
        _group("بطاريه", "بطاريات", "مغناطيس", "مغناطيسات", "مبيض", "كلوركس", "فلاش", "منظف", "كاز", "بنزين", "تنر", "مبيد",
               "battery", "batteries", "magnet", "magnets", "bleach", "detergent", "kerosene", "petrol", "gasoline", "antifreeze",
               "pesticide") + ("مويه نار", "detergent pod", "drain cleaner", "oven cleaner", "weed killer"))]),
    "pills_taken": ((), [(
        _group("اخذ", "اخذت", "بلع", "بلعت", "شرب", "شربت", "took", "taken", "swallowed", "ate"),
        _group("حبوب", "حبه", "دوا", "دواء", "بنادول", "شريط", "علبه", "pills", "tablets", "paracetamol", "panadol", "painkillers",
               "medicine", "medication") + ("sleeping tablets", "sleeping pills"))]),
    # V290: an amount word directly next to a medicine word ("too many tablets", «حبوب كثير», «علبة بنادول كاملة»);
    # the rule also needs "took / swallowed" (pills_taken). "a lot of medicine" / «دوا كثير» are too loose and are not used.
    "large_quantity": (_OVERDOSE_PHRASES, []),
    "burn": (_group("حرق", "حروق", "احترق", "احترقت", "انحرق", "انحرقت", "محروق", "محروقه", "burn", "burnt", "burned", "scald",
                    "scalded") + ("ماي حار", "مويه حاره", "ماء مغلي", "boiling water"), []),
    "burn_serious": (("bigger than my hand", "bigger than his hand", "bigger than her hand", "larger than my hand", "white and leathery",
                      "leathery", "charred", "skin looks white", "جلده ابيض", "الجلد ابيض"), [(
        _group("حرق", "حروق", "احترق", "احترقت", "انحرق", "انحرقت", "محروق", "محروقه", "فقاعات", "burn", "burnt", "burned",
               "scald", "scalded", "blisters"),
        ("كلها", "كله", "كبير", "كبيره", "large", "big", "whole", "all over", "huge"))]),
    "burn_cause_serious": (_group("كهرباء", "كهربا", "سلك", "اسيد", "حمض", "electric", "electrical", "electricity", "acid", "chemical")
                           + ("مويه نار", "oven cleaner", "drain cleaner"), []),
    "burn_site_blister": ((), [(
        _group("وجه", "يد", "كف", "رجل", "قدم", "صدر", "رقبه", "face", "hand", "hands", "foot", "feet", "chest", "neck", "genitals"),
        _group("فقاعات", "فقاعه", "نفاطات", "blisters", "blister", "blistering"))]),
    "limb_deformity": (("odd angle", "strange angle", "wrong way", "out of shape", "deformed", "bone sticking out", "bone through the skin",
                        "bone is showing", "looks shorter and turned out", "turned outwards", "turned out", "العظم طالع", "العظم بارز",
                        "بشكل غريب", "ملتويه لبرا", "ملتوي لبرا", "ملتويه للخارج", "معوجه", "معوج", "مو في مكانها", "مقلوبه"), []),
    "fall_or_injury": (_group("طاح", "طاحت", "طحت", "سقط", "سقطت", "وقع", "وقعت", "انكسر", "انكسرت", "حادث",
                              "fell", "fall", "fallen", "crash", "accident", "injury", "broke", "broken"), []),
    "cannot_get_up": (("ما تقدر تقوم", "ما يقدر يقوم", "ما اقدر اقوم", "ما تقدر توقف", "ما يقدر يوقف", "can't get up", "cannot get up",
                       "unable to get up", "can't stand", "cannot stand", "can't put weight", "cannot put weight"), []),
    "elderly": (_group("جدتي", "جدي", "جده", "الشايب", "العجوز", "grandmother", "grandfather", "grandma", "grandpa", "granny", "elderly"), []),
    "chest_crushing": (("crushing chest", "chest crushing", "يعصر صدري", "شي ثقيل على صدري", "حجر على صدري"), [(
        _group("صدر", "صدري", "chest"),
        ("crushing", "squeezing", "elephant", "heavy weight", "tight band", "vice", "clamp", "قاعد عليه", "قاعد على", "عليه حجر", "يعصر",
         "يعصرني", "ينعصر", "حجر ثقيل"))]),
}

# Words that turn "can't see" into blurred vision rather than vision loss.
_BLURRED = ("زين", "كويس", "عدل", "واضح", "well", "clearly", "properly")

# (rule_id, label_ar, label_en, predicate over the set of matched concepts)
RULES = (
    ("concept_anaphylaxis", "تورم بالفم/الوجه أو طفح منتشر مع صعوبة تنفس أو صفير أو دوخة",
     "Mouth/face swelling or widespread hives with breathing difficulty, wheeze or dizziness",
     lambda c: bool(c & {"mouth_swelling", "hives", "sting"}) and bool(c & {"breathing", "wheeze", "faint", "dizzy"})),
    ("concept_gi_bleed", "براز أسود قطراني مع دوخة أو إغماء أو ضعف", "Black tarry stool with dizziness, faintness or weakness",
     lambda c: "black_stool" in c and bool(c & {"faint", "dizzy", "weak"})),
    ("concept_head_injury", "إصابة في الرأس مع قيء متكرر أو نعاس أو تشوش", "Head injury with repeated vomiting, drowsiness or confusion",
     lambda c: "head_injury" in c and bool(c & {"vomit_repeated", "drowsy", "confusion", "faint"})),
    ("concept_acute_abdomen", "ألم شديد في البطن مع تيبّس البطن أو قيء مستمر", "Severe abdominal pain with a rigid abdomen or persistent vomiting",
     lambda c: "abdominal_pain" in c and ("rigid_abdomen" in c or ("severe" in c and "vomit_repeated" in c))),
    ("concept_testicular_torsion", "ألم أو تورم مفاجئ/شديد في الخصية", "Sudden or severe testicular pain or swelling",
     lambda c: "testicle_pain" in c and bool(c & {"sudden", "severe"})),
    ("concept_diabetic_emergency", "مريض سكري مع تشوش أو تنفس سريع عميق أو قيء متكرر", "Diabetic with confusion, deep rapid breathing or repeated vomiting",
     lambda c: "diabetes" in c and (len(c & {"confusion", "rapid_breathing", "vomit_repeated", "drowsy"}) >= 2
                                    or (bool(c & {"confusion", "drowsy", "reduced_consciousness"}) and bool(c & {"sweating", "shaky"})))),
    ("concept_severe_asthma", "نوبة ربو لا تتحسن مع البخاخ المعتاد", "Asthma attack not improving with the usual reliever",
     lambda c: "asthma" in c and "reliever_failing" in c),
    ("concept_meningitis", "حمى وتيبّس الرقبة مع تشوش أو صداع شديد أو حساسية للضوء", "Fever and stiff neck with confusion, severe headache or light sensitivity",
     lambda c: "fever" in c and "stiff_neck" in c and bool(c & {"confusion", "severe_headache", "photophobia", "drowsy"})),
    ("concept_bleeding_shock", "نزيف غزير مع إغماء أو ضعف شديد", "Heavy bleeding with fainting or severe weakness",
     lambda c: "heavy_bleeding" in c and bool(c & {"faint", "weak", "dizzy"})),
    ("concept_sudden_vision_loss", "فقدان مفاجئ للرؤية", "Sudden loss of vision",
     lambda c: "vision_loss" in c and "sudden" in c),
    ("concept_cardiac_chest", "ألم في الصدر مع شدة أو تعرّق أو انتشار للذراع/الفك أو ضيق تنفس",
     "Chest pain that is severe, or with sweating, spreading to the arm/jaw or breathlessness",
     lambda c: "chest_pain" in c and bool(c & {"severe", "sweating", "radiating", "breathing"})),
    ("concept_stroke_fast", "ميلان مفاجئ في الوجه أو عدم القدرة على رفع الذراع", "Sudden facial droop or inability to lift an arm",
     lambda c: "face_droop" in c or (bool(c & ({"arm_cannot_lift", "limb_weak_one_side"} | ({"grip_loss"} if V290_ENABLED else set())))
                                     and "sudden" in c)),
    # ---- V287 error-taxonomy rules
    ("concept_respiratory_distress", "ضيق تنفس مع ازرقاق أو عدم القدرة على إكمال الكلام أو سيلان اللعاب",
     "Breathing difficulty with blue lips, inability to speak in sentences, or drooling",
     lambda c: bool(c & {"cant_speak_breath", "child_breathing_distress"})
     or (bool(c & {"cyanosis", "drooling"}) and bool(c & {"breathing", "wheeze", "rapid_breathing"}))),
    ("concept_reduced_consciousness", "استجابة أو وعي أقل من الطبيعي", "Reduced responsiveness or consciousness",
     lambda c: "reduced_consciousness" in c),
    ("concept_sepsis", "حمى مع تشوش أو نقص الوعي أو طفح بنفسجي لا يختفي بالضغط",
     "Fever with confusion, reduced consciousness, or a purple rash that does not fade",
     lambda c: "purple_rash" in c or ("fever" in c and bool(c & {"confusion", "reduced_consciousness"}))),
    ("concept_cardiac_syncope", "إغماء مع ألم صدر أو خفقان غير منتظم أو أثناء مجهود",
     "Fainting with chest pain, an irregular heartbeat, or during exertion",
     lambda c: "syncope" in c and bool(c & {"chest_pain", "palpitations_irregular", "exertion"})),
    ("concept_severe_dehydration", "قيء أو عدم احتفاظ بالسوائل مع قلة البول وتشوش أو نعاس",
     "Vomiting or not keeping fluids down, with little urine and confusion or drowsiness",
     lambda c: bool(c & {"vomit_repeated", "fluids_not_kept", "no_urine"}) and bool(c & {"no_urine", "fluids_not_kept"})
     and bool(c & {"confusion", "drowsy", "reduced_consciousness"})),
    ("concept_acute_glaucoma", "ألم شديد أو مفاجئ في العين مع تشوش الرؤية أو قيء",
     "Severe or sudden eye pain with blurred vision or vomiting",
     lambda c: "eye_pain" in c and bool(c & {"severe", "sudden"}) and bool(c & {"vision_blur", "vision_loss", "vomit_any"})),
    ("concept_cauda_equina", "ألم ظهر أو ضعف الساقين مع فقدان التحكم بالبول أو خدر حول المقعدة",
     "Back pain or leg weakness with loss of bladder control or saddle numbness",
     lambda c: "bladder_loss" in c and bool(c & {"back_pain", "leg_weak"})),
    ("concept_limb_ischaemia", "طرف بارد مفاجئ مع شحوب أو خدر", "A suddenly cold limb that is pale or numb",
     lambda c: "cold_limb" in c and "pale_or_numb_limb" in c and bool(c & {"sudden", "severe"})),
    ("concept_thunderclap_headache", "صداع مفاجئ شديد أو الأسوأ في الحياة", "Sudden severe or worst-ever headache",
     lambda c: "worst_headache" in c or ("severe_headache" in c and "sudden" in c)),
    ("concept_stroke_speech", "ثقل مفاجئ في الكلام مع ضعف في طرف", "Sudden slurred speech with limb weakness",
     lambda c: "slurred_speech" in c and "sudden" in c),
    ("concept_infant_bilious_vomit", "قيء أخضر عند رضيع", "Green (bile) vomiting in a baby",
     lambda c: "bilious_vomit" in c and "infant" in c),
    # ---- V290 rules (error types of the sealed fresh probe set; built on evaluation/v290_dev_cases.json)
    ("concept_cannot_breathe", "لا يستطيع التنفس", "Cannot breathe",
     lambda c: "cannot_breathe" in c),
    ("concept_choking", "اختناق بطعام أو جسم مع صعوبة تنفس أو عدم القدرة على الكلام أو السعال",
     "Choking on food or an object with breathing difficulty or unable to speak or cough",
     lambda c: bool(c & {"choking", "swallowed_object"}) and bool(c & {"cannot_breathe", "breathing", "cant_speak_or_cough", "cyanosis"})),
    ("concept_dangerous_ingestion", "بلع بطارية أو مغناطيس أو مادة كيميائية", "Swallowed a battery, magnets or a household chemical",
     lambda c: "dangerous_ingestion" in c),
    ("concept_overdose", "تناول كمية كبيرة من الدواء", "Took a large amount of medicine",
     lambda c: "pills_taken" in c and "large_quantity" in c),
    ("concept_serious_burn", "حرق كبير أو عميق أو كهربائي/كيميائي، أو بفقاعات في الوجه أو اليد أو القدم",
     "A large, deep, electrical or chemical burn, or a blistering burn on the face, hands or feet",
     lambda c: "burn" in c and bool(c & {"burn_serious", "burn_cause_serious", "burn_site_blister"})),
    ("concept_fracture_deformity", "بعد سقوط أو إصابة: طرف شكله غير طبيعي أو عظم ظاهر، أو كبير سن لا يستطيع القيام",
     "After a fall or injury: a deformed limb or visible bone, or an older person who cannot get up",
     lambda c: "fall_or_injury" in c and ("limb_deformity" in c or ("cannot_get_up" in c and "elderly" in c))),
    ("concept_chest_crushing", "ضغط أو عصر على الصدر", "Crushing or squeezing chest pressure",
     lambda c: "chest_crushing" in c),
)
_NEURO_RULES = {"concept_stroke_fast", "concept_stroke_speech"}
# V287 rules built from the error taxonomy; the evaluator can switch them off to measure their effect.
V287_RULES = frozenset({"concept_respiratory_distress", "concept_reduced_consciousness", "concept_sepsis", "concept_cardiac_syncope",
                        "concept_severe_dehydration", "concept_acute_glaucoma", "concept_cauda_equina", "concept_limb_ischaemia",
                        "concept_thunderclap_headache", "concept_stroke_speech", "concept_infant_bilious_vomit"})
V287_ENABLED = True
# V290 rules from the sealed fresh probe set's error types; the evaluator switches them off for the ablation.
V290_RULES = frozenset({"concept_cannot_breathe", "concept_choking", "concept_dangerous_ingestion", "concept_overdose",
                        "concept_serious_burn", "concept_fracture_deformity", "concept_chest_crushing"})
V290_ENABLED = True


def _active(rid: str) -> bool:
    return (V287_ENABLED or rid not in V287_RULES) and (V290_ENABLED or rid not in V290_RULES)

# Plain names shown to the user next to the words that matched each concept.
CONCEPT_LABELS = {
    "mouth_swelling": ("تورم في الفم أو الوجه", "mouth or face swelling"), "breathing": ("صعوبة في التنفس", "breathing difficulty"),
    "wheeze": ("صفير في الصدر", "wheeze"), "hives": ("طفح منتشر", "widespread rash"), "faint": ("إغماء أو شعور به", "fainting"),
    "dizzy": ("دوخة", "dizziness"), "weak": ("ضعف شديد", "severe weakness"), "head_injury": ("إصابة في الرأس", "head injury"),
    "vomit_repeated": ("قيء متكرر", "repeated vomiting"), "drowsy": ("نعاس غير معتاد", "unusual drowsiness"),
    "confusion": ("تشوش", "confusion"), "black_stool": ("براز أسود", "black stool"), "abdominal_pain": ("ألم في البطن", "abdominal pain"),
    "rigid_abdomen": ("تيبّس البطن", "rigid abdomen"), "testicle_pain": ("ألم أو تورم في الخصية", "testicular pain or swelling"),
    "diabetes": ("السكري", "diabetes"), "rapid_breathing": ("تنفس سريع أو عميق", "rapid or deep breathing"), "asthma": ("الربو", "asthma"),
    "reliever_failing": ("البخاخ لم يساعد", "reliever not helping"), "fever": ("حمى", "fever"), "stiff_neck": ("تيبّس الرقبة", "stiff neck"),
    "severe_headache": ("صداع شديد", "severe headache"), "photophobia": ("حساسية للضوء", "light sensitivity"),
    "heavy_bleeding": ("نزيف غزير", "heavy bleeding"), "vision_loss": ("فقدان الرؤية", "loss of vision"),
    "face_droop": ("ميلان الوجه", "facial droop"), "arm_cannot_lift": ("عدم القدرة على رفع الذراع", "cannot lift an arm"),
    "chest_pain": ("ألم في الصدر", "chest pain"), "sweating": ("تعرّق", "sweating"), "radiating": ("انتشار الألم", "spreading pain"),
    "sudden": ("بداية مفاجئة", "sudden onset"), "severe": ("شدة عالية", "high severity"),
    "cyanosis": ("ازرقاق الشفاه أو الوجه", "blue lips or face"), "cant_speak_breath": ("لا يكمل الكلام من ضيق النفس", "too breathless to speak"),
    "drooling": ("سيلان اللعاب وصعوبة البلع", "drooling"), "reduced_consciousness": ("وعي أو استجابة أقل من الطبيعي", "reduced responsiveness"),
    "purple_rash": ("طفح بنفسجي لا يختفي بالضغط", "purple rash that does not fade"), "syncope": ("إغماء", "fainting"),
    "palpitations_irregular": ("خفقان أو نبض غير منتظم", "irregular or racing heartbeat"), "exertion": ("أثناء مجهود", "during exertion"),
    "no_urine": ("قلة البول أو انعدامه", "little or no urine"), "fluids_not_kept": ("لا يحتفظ بالسوائل", "not keeping fluids down"),
    "sting": ("لسعة حشرة", "insect sting"), "vomit_any": ("قيء", "vomiting"), "eye_pain": ("ألم في العين", "eye pain"),
    "vision_blur": ("تشوش الرؤية", "blurred vision"), "back_pain": ("ألم في الظهر", "back pain"),
    "bladder_loss": ("فقدان التحكم بالبول أو خدر حول المقعدة", "loss of bladder control or saddle numbness"),
    "leg_weak": ("ضعف أو خدر في الساق", "leg weakness or numbness"), "cold_limb": ("طرف بارد", "cold limb"),
    "pale_or_numb_limb": ("طرف شاحب أو مخدر", "pale or numb limb"), "shaky": ("رجفة", "shakiness"),
    "worst_headache": ("أسوأ صداع", "worst-ever headache"), "slurred_speech": ("ثقل في الكلام", "slurred speech"),
    "child_breathing_distress": ("علامات ضيق تنفس عند طفل (انسحاب الضلوع، أنين، صوت مع الشهيق)", "child breathing distress (indrawing, grunting, stridor)"),
    "bilious_vomit": ("قيء أخضر", "green vomit"), "infant": ("رضيع", "baby"),
    "limb_weak_one_side": ("ضعف أو تنميل في ذراع أو جهة واحدة", "weakness or numbness in an arm or one side"),
    "cannot_breathe": ("لا يستطيع التنفس", "cannot breathe"), "grip_loss": ("لا يستطيع الإمساك بالأشياء", "cannot hold things"),
    "choking": ("اختناق أو شرقة", "choking"), "swallowed_object": ("بلع طعام أو جسم صغير", "swallowed food or a small object"),
    "cant_speak_or_cough": ("لا يتكلم ولا يسعل", "cannot speak or cough"),
    "dangerous_ingestion": ("بلع بطارية أو مغناطيس أو مادة كيميائية", "swallowed a battery, magnet or chemical"),
    "pills_taken": ("تناول دواء", "took medicine"), "large_quantity": ("كمية كبيرة", "a large amount"),
    "burn": ("حرق", "burn"), "burn_serious": ("حرق كبير أو عميق", "large or deep burn"),
    "burn_cause_serious": ("حرق كهربائي أو كيميائي", "electrical or chemical burn"),
    "burn_site_blister": ("فقاعات في الوجه أو اليد أو القدم", "blisters on the face, hands or feet"),
    "limb_deformity": ("شكل الطرف غير طبيعي أو العظم ظاهر", "deformed limb or visible bone"),
    "fall_or_injury": ("سقوط أو إصابة", "fall or injury"), "cannot_get_up": ("لا يستطيع القيام", "cannot get up"),
    "elderly": ("كبير في السن", "older person"), "chest_crushing": ("ضغط أو عصر على الصدر", "crushing chest pressure"),
}


# ------------------------------------------------------------------ matching
# Thousands of generated word forms: match by token set lookup (O(words)) instead of
# compiling one regex per form, which overflowed clinical_text's pattern cache.
_WORD_BOUNDARY_L, _WORD_BOUNDARY_R = r"(?<!\w)", r"(?!\w)"


class _Group:
    """A set of interchangeable words/phrases, matched on normalised text."""

    def __init__(self, phrases):
        norm = {clinical_text.normalize_clinical_text(p) for p in phrases}
        norm.discard("")
        self.single = frozenset(p for p in norm if " " not in p)
        multi = sorted((p for p in norm if " " in p), key=len, reverse=True)
        # optional attached conjunction (و/ف) and preposition (ب/ل): "وبضعف شديد"
        self.multi = (re.compile(_WORD_BOUNDARY_L + r"(?:[وف]?[بل]?)(" + "|".join(r"\s+".join(map(re.escape, m.split())) for m in multi)
                                 + ")" + _WORD_BOUNDARY_R) if multi else None)

    def spans(self, clause: str):
        """(start, end) of every occurrence in a normalised clause."""
        for m in re.finditer(r"\S+", clause):
            tok = m.group()
            if tok in self.single:
                yield m.start(), m.end()
            else:
                for cut in (1, 2):  # و/ف/ب/ل, or two of them ("وب")
                    if len(tok) > cut + 1 and all(ch in "وفبل" for ch in tok[:cut]) and tok[cut:] in self.single:
                        yield m.start() + cut, m.end()
                        break
        if self.multi is not None:
            for m in self.multi.finditer(clause):
                yield m.start(1), m.end(1)

    def starts(self, clause: str):
        for start, _end in self.spans(clause):
            yield start

    def present(self, clause: str) -> bool:
        return next(self.starts(clause), None) is not None

    def present_unnegated(self, clause: str) -> bool:
        return any(not clinical_text.occurrence_is_negated(clause, i) for i in self.starts(clause))


def _pair_present(a: _Group, b: _Group, clause: str) -> bool:
    """Both groups in the clause, and the pair is not negated where it begins:
    "ما عندي ضيق تنفس" negates the pair (ضيق … تنفس) even though تنفس itself is not
    directly preceded by a negator."""
    a_starts, b_starts = list(a.starts(clause)), list(b.starts(clause))
    return any(not clinical_text.occurrence_is_negated(clause, min(i, j)) for i in a_starts for j in b_starts)


_COMPILED = {name: (_Group(phrases) if phrases else None, [(_Group(a), _Group(b)) for a, b in pairs])
             for name, (phrases, pairs) in CONCEPTS.items()}
_BLURRED_GROUP = _Group(_BLURRED)


def _build_vocabulary() -> dict[tuple[str, int], tuple[str, ...]]:
    """Concept words of 5+ letters indexed by (first letter, length) for typo correction."""
    words: set[str] = set()
    groups = [g for ph, pairs in _COMPILED.values() for g in ([ph] if ph else []) + [x for pair in pairs for x in pair]]
    for g in groups:
        words |= {w for w in g.single if len(w) >= 5}
        if g.multi is not None:
            for alt in g.multi.pattern.split("|"):
                words |= {t for t in re.findall(r"[\w\u0600-\u06ff]+", alt) if len(t) >= 5}
    index: dict[tuple[str, int], list[str]] = {}
    for w in words:
        index.setdefault((w[0], len(w)), []).append(w)
    return {k: tuple(v) for k, v in index.items()}


_VOCAB = _build_vocabulary()
_VOCAB_ALL = frozenset(w for ws in _VOCAB.values() for w in ws)


def _build_word_groups() -> dict[str, frozenset[int]]:
    """word -> the groups it belongs to. Two typo candidates in exactly the same groups mean
    the same thing for matching ("انتفت" -> انتفخ / انتفخت), so either can be used."""
    out: dict[str, set[int]] = {}
    groups = [g for ph, pairs in _COMPILED.values() for g in ([ph] if ph else []) + [x for pair in pairs for x in pair]]
    for g in groups:
        words = set(g.single)
        if g.multi is not None:
            for alt in g.multi.pattern.split("|"):
                words |= set(re.findall(r"[\w\u0600-\u06ff]+", alt))
        for w in words:
            out.setdefault(w, set()).add(id(g))
    return {w: frozenset(v) for w, v in out.items()}


_WORD_GROUPS = _build_word_groups()


_FUNCTION_WORDS_AR = ("ما", "لا", "مو", "و", "من", "في", "على", "بعد", "عندي", "شوي", "مره", "وايد", "كثير", "اكثر", "صار", "صرت", "احس")
_ENGLISH_STOP = frozenset("""a an and the i my me is am are was were have has had no not with without of in on to at for from
after before since very so but or it its this that he she his her they them we you your yes ok okay pain help please""".split())


@lru_cache(maxsize=1)
def known_words() -> frozenset[str]:
    """Every Arabic word the concept layer can match (normalised), for Arabizi transliteration."""
    words: set[str] = set(_FUNCTION_WORDS_AR)
    groups = [g for ph, pairs in _COMPILED.values() for g in ([ph] if ph else []) + [x for pair in pairs for x in pair]]
    groups.append(_BLURRED_GROUP)
    for g in groups:
        words |= set(g.single)
        if g.multi is not None:
            words |= set(re.findall(r"[\u0600-\u06ff]+", g.multi.pattern))
    return frozenset(w for w in words if _AR.search(w))


@lru_cache(maxsize=1)
def english_words() -> frozenset[str]:
    """Latin words of the concept vocabulary plus common English words: never read as Arabizi."""
    words: set[str] = set(_ENGLISH_STOP)
    for phrases, pairs in CONCEPTS.values():
        for item in list(phrases) + [w for a, b in pairs for w in a + b]:
            words |= {t for t in re.findall(r"[a-z']+", item.lower())}
    return frozenset(words)


def _arabic_text(text: str) -> str:
    """Text with Arabizi tokens in Arabic script (unchanged when there is none)."""
    return arabizi.to_arabic(text)


def _one_edit(a: str, b: str) -> bool:
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1:]


def correct_typos(normalized: str) -> str:
    """Replace an Arabic token of 4+ letters that is one edit away from exactly one concept
    word of 5+ letters (same first letter). Tokens with no unique near neighbour are kept."""
    out = []
    for tok in normalized.split(" "):
        # Arabic only: English words are short and dense ("back" is one letter from "black").
        # V290: a real word (arabic_lexicon) is never "corrected": «الصغير» is not «الصفير».
        if (len(tok) >= 4 and tok not in _VOCAB_ALL and tok not in _WORD_GROUPS and tok != "|" and _AR.search(tok)
                and not arabic_lexicon.is_real_word(tok)):
            near = [w for n in (len(tok) - 1, len(tok), len(tok) + 1) for w in _VOCAB.get((tok[0], n), ())
                    if _one_edit(tok, w)]
            if len(near) == 1:
                tok = near[0]
            elif near and len({_WORD_GROUPS.get(w, frozenset()) for w in near}) == 1:
                tok = sorted(near, key=lambda w: (-len(w), w))[0]  # V289: several spellings of one meaning
        out.append(tok)
    return " ".join(out)


def _clauses(normalized: str) -> list[str]:
    return [c.strip() for c in normalized.split("|") if c.strip()]


@lru_cache(maxsize=512)
def matched_concepts(text: str) -> frozenset[str]:
    norm = correct_typos(clinical_text.normalize_clinical_text(_arabic_text(text)))
    clauses = _clauses(norm)
    found = set()
    for name, (phrases, pairs) in _COMPILED.items():
        if phrases is not None and any(phrases.present_unnegated(cl) for cl in clauses):
            found.add(name)
            continue
        if any(_pair_present(a, b, cl) for a, b in pairs for cl in clauses):
            found.add(name)
    if "vision_loss" in found and any(_BLURRED_GROUP.present(cl) for cl in clauses):
        found.discard("vision_loss")
    if "fever" not in found and V290_ENABLED and _TEMP_FEVER.search(norm):
        found.add("fever")  # V290: "temperature of 39" / «حرارته 39.5» without the word fever
    return frozenset(found)


# A measured temperature of 38.0–42.9 °C next to a temperature word.
_TEMP_FEVER = re.compile(r"(?:temp\w*|حراره\w*|حرار\w*)\D{0,12}(?<![\d.])(?:3[89]|4[0-2])(?:[.,]\d)?(?![\d])")


def denied_concepts(text: str) -> frozenset[str]:
    """Concepts the text mentions only in negated form ("ما عندي ضيق تنفس"). Display only:
    used to show that a denial was understood; the decision never reads it."""
    clauses = _clauses(correct_typos(clinical_text.normalize_clinical_text(_arabic_text(str(text or "")))))
    mentioned = set()
    for name, (phrases, pairs) in _COMPILED.items():
        if (phrases is not None and any(phrases.present(cl) for cl in clauses)) or any(
                a.present(cl) and b.present(cl) for a, b in pairs for cl in clauses):
            mentioned.add(name)
    return frozenset(mentioned - matched_concepts(str(text or "")))


def evaluate(text: str, skip_neuro: bool = False) -> list[tuple[str, str, str]]:
    """[(rule_id, label_ar, label_en)] for every red-flag combination present."""
    concepts = matched_concepts(str(text or ""))
    return [(rid, ar, en) for rid, ar, en, rule in RULES if _active(rid)
            if rule(concepts) and not (skip_neuro and rid in _NEURO_RULES)]


# ------------------------------------------------------------------ evidence
def _word_map(text: str):
    """Clauses of (normalised, typo-corrected token, (start, end) in the ORIGINAL text).
    Normalising word by word keeps a link from every token back to what the user typed."""
    clauses, current = [], []
    text = str(text or "")
    conversions = arabizi.convert_tokens(text)
    for m in re.finditer(r"\S+", text):
        raw, offset = m.group(), m.start()
        for start, end, ar in reversed([c for c in conversions if m.start() <= c[0] < m.end()]):
            raw = raw[:start - offset] + " " + ar + " " + raw[end - offset:]
        norm = clinical_text.normalize_clinical_text(raw)
        for tok in norm.replace("|", " ").split():
            current.append((correct_typos(tok), (m.start(), m.end())))
        if "|" in norm and current:
            clauses.append(current)
            current = []
    if current:
        clauses.append(current)
    return clauses


def _clause_index(tokens):
    """Joined clause text plus, for each character, the index of its token."""
    text, owner = "", []
    for i, (tok, _span) in enumerate(tokens):
        if text:
            text += " "
            owner.append(i)
        text += tok
        owner.extend([i] * len(tok))
    return text, owner


def _quote(text: str, tokens, owner, start: int, end: int) -> tuple[int, int, str]:
    first, last = owner[start], owner[max(start, end - 1)]
    s0, e0 = tokens[first][1][0], tokens[last][1][1]
    piece = text[s0:e0]
    trimmed = piece.rstrip(".,!?؟،؛:;)»\"'")
    return s0, s0 + len(trimmed), trimmed


def explain(text: str, skip_neuro: bool = False) -> list[dict]:
    """For every concept rule that fires: which concepts made it fire and the user's own
    words for each (quoted from the original text, with character offsets).

    Faithful by construction: quotes are slices of `text`, and only non-negated
    occurrences of concepts the decision actually used are reported."""
    text = str(text or "")
    concepts = matched_concepts(text)
    rules = [(rid, ar, en, rule) for rid, ar, en, rule in RULES
             if _active(rid) and rule(concepts) and not (skip_neuro and rid in _NEURO_RULES)]
    if not rules:
        return []
    clauses = [(_clause_index(toks), toks) for toks in _word_map(text)]
    quotes: dict[str, list[tuple[int, int, str]]] = {}
    for name in concepts:
        phrases, pairs = _COMPILED[name]
        found = []
        for (ctext, owner), toks in clauses:
            if phrases is not None:
                found += [_quote(text, toks, owner, a, b) for a, b in phrases.spans(ctext)
                          if not clinical_text.occurrence_is_negated(ctext, a)]
            for ga, gb in pairs:
                sa, sb = list(ga.spans(ctext)), list(gb.spans(ctext))
                for a in sa:
                    for b in sb:
                        if not clinical_text.occurrence_is_negated(ctext, min(a[0], b[0])):
                            lo, hi = min(a[0], b[0]), max(a[1], b[1])
                            found.append(_quote(text, toks, owner, lo, hi))
        # keep the shortest quote per position; drop duplicates and quotes inside others
        uniq = sorted(set(found), key=lambda q: (q[0], q[1] - q[0]))
        kept = [q for q in uniq if not any(o != q and o[0] >= q[0] and o[1] <= q[1] for o in uniq)]
        merged: list[tuple[int, int, str]] = []
        for q in sorted(kept):  # overlapping quotes ("black tarry" + "tarry stool") become one
            if merged and q[0] < merged[-1][1]:
                s0, e0 = merged[-1][0], max(merged[-1][1], q[1])
                merged[-1] = (s0, e0, text[s0:e0])
            else:
                merged.append(q)
        kept = merged
        if kept:
            quotes[name] = kept
    out = []
    for rid, ar, en, _rule in rules:
        names = [c for c in _RULE_CONCEPTS[rid] if c in quotes]
        out.append({"rule_id": rid, "label_ar": ar, "label_en": en,
                    "evidence": [{"concept": c, "label_ar": CONCEPT_LABELS[c][0], "label_en": CONCEPT_LABELS[c][1],
                                  "quotes": [{"start": q[0], "end": q[1], "text": q[2]} for q in quotes[c]]} for c in names]})
    return out


# Concepts each rule can use (for the explanation; the decision itself is the lambda in RULES).
_RULE_CONCEPTS = {
    "concept_anaphylaxis": ("mouth_swelling", "hives", "sting", "breathing", "wheeze", "faint", "dizzy"),
    "concept_gi_bleed": ("black_stool", "faint", "dizzy", "weak"),
    "concept_head_injury": ("head_injury", "vomit_repeated", "drowsy", "confusion", "faint"),
    "concept_acute_abdomen": ("abdominal_pain", "rigid_abdomen", "severe", "vomit_repeated"),
    "concept_testicular_torsion": ("testicle_pain", "sudden", "severe"),
    "concept_diabetic_emergency": ("diabetes", "confusion", "rapid_breathing", "vomit_repeated", "drowsy", "reduced_consciousness", "sweating", "shaky"),
    "concept_severe_asthma": ("asthma", "reliever_failing"),
    "concept_meningitis": ("fever", "stiff_neck", "confusion", "severe_headache", "photophobia", "drowsy"),
    "concept_bleeding_shock": ("heavy_bleeding", "faint", "weak", "dizzy"),
    "concept_sudden_vision_loss": ("vision_loss", "sudden"),
    "concept_cardiac_chest": ("chest_pain", "severe", "sweating", "radiating", "breathing"),
    "concept_stroke_fast": ("face_droop", "arm_cannot_lift", "limb_weak_one_side", "grip_loss", "sudden"),
    "concept_respiratory_distress": ("cant_speak_breath", "child_breathing_distress", "cyanosis", "drooling", "breathing", "wheeze", "rapid_breathing"),
    "concept_infant_bilious_vomit": ("bilious_vomit", "infant"),
    "concept_reduced_consciousness": ("reduced_consciousness",),
    "concept_sepsis": ("fever", "purple_rash", "confusion", "reduced_consciousness"),
    "concept_cardiac_syncope": ("syncope", "chest_pain", "palpitations_irregular", "exertion"),
    "concept_severe_dehydration": ("vomit_repeated", "fluids_not_kept", "no_urine", "confusion", "drowsy", "reduced_consciousness"),
    "concept_acute_glaucoma": ("eye_pain", "severe", "sudden", "vision_blur", "vision_loss", "vomit_any"),
    "concept_cauda_equina": ("bladder_loss", "back_pain", "leg_weak"),
    "concept_limb_ischaemia": ("cold_limb", "pale_or_numb_limb", "sudden", "severe"),
    "concept_thunderclap_headache": ("worst_headache", "severe_headache", "sudden"),
    "concept_stroke_speech": ("slurred_speech", "sudden"),
    "concept_cannot_breathe": ("cannot_breathe",),
    "concept_choking": ("choking", "swallowed_object", "cannot_breathe", "breathing", "cant_speak_or_cough", "cyanosis"),
    "concept_dangerous_ingestion": ("dangerous_ingestion",),
    "concept_overdose": ("pills_taken", "large_quantity"),
    "concept_serious_burn": ("burn", "burn_serious", "burn_cause_serious", "burn_site_blister"),
    "concept_fracture_deformity": ("fall_or_injury", "limb_deformity", "cannot_get_up", "elderly"),
    "concept_chest_crushing": ("chest_crushing",),
}
