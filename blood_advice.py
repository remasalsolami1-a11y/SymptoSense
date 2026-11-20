""""How can I improve this?" cards for out-of-range blood results (V290).

Before V290 each abnormal value had one generic sentence ("focus on iron sources…"),
written in the feminine form only, with a single generic English fallback, and it
ignored the rest of the report. These cards answer the user's real question — what
can I do now — while keeping the safety rules a clinician would expect:

  * NO DOSES, ever. Supplement doses depend on the cause and the level and are set by
    a clinician (vitamin D, iron and B12 overdoses are harmful). Tests enforce this.
  * No food advice for critical values, electrolytes, white cells, platelets, INR,
    lactate or troponin: trying to correct those with food or supplements is unsafe.
    Those get a "doctor only" card.
  * Pattern-aware: low haemoglobin is called iron deficiency only when the iron stores
    (ferritin) are low too; otherwise the card asks for the tests that find the cause.
    Taking iron without a cause can hide bleeding.
  * Context: pregnancy (no liver — vitamin A), children (no adult food lists),
    vegetarian diets (B12), medicines that change the advice (blood thinners,
    metformin, diabetes medicines).
  * Gender-neutral Arabic (impersonal wording) and full English.
  * Every card lists its sources; every card is pending clinician review and is part
    of the clinician review packet (tools/clinical_packet.py).

attach(indicators, results, …) adds indicator["advice"] for the page and API.
"""
from __future__ import annotations

import re

# ------------------------------------------------------------------ sources (checked 2026-11-16)
S = {
    "moh_iron": ("وزارة الصحة السعودية — فقر الدم بنقص الحديد", "Saudi Ministry of Health — Iron deficiency anemia",
                 "https://www.moh.gov.sa/en/HealthAwareness/EducationalContent/Diseases/Hematology/Pages/0010.aspx"),
    "ods_iron": ("المعاهد الوطنية للصحة الأمريكية — الحديد", "NIH Office of Dietary Supplements — Iron",
                 "https://ods.od.nih.gov/factsheets/Iron-Consumer/"),
    "ods_b12": ("المعاهد الوطنية للصحة الأمريكية — فيتامين B12", "NIH Office of Dietary Supplements — Vitamin B12",
                "https://ods.od.nih.gov/factsheets/VitaminB12-Consumer/"),
    "ods_folate": ("المعاهد الوطنية للصحة الأمريكية — الفولات", "NIH Office of Dietary Supplements — Folate",
                   "https://ods.od.nih.gov/factsheets/Folate-Consumer/"),
    "ods_vitd": ("المعاهد الوطنية للصحة الأمريكية — فيتامين د", "NIH Office of Dietary Supplements — Vitamin D",
                 "https://ods.od.nih.gov/factsheets/VitaminD-Consumer/"),
    "nhs_b12": ("NHS — فقر الدم بنقص B12 أو الفولات", "NHS — Vitamin B12 or folate deficiency anaemia",
                "https://www.nhs.uk/conditions/vitamin-b12-or-folate-deficiency-anaemia/"),
    "nhs_vitd": ("NHS — فيتامين د", "NHS — Vitamin D", "https://www.nhs.uk/conditions/vitamins-and-minerals/vitamin-d/"),
    "nhs_chol": ("NHS — الوقاية من ارتفاع الكوليسترول", "NHS — High cholesterol: prevention",
                 "https://www.nhs.uk/conditions/high-cholesterol/prevention/"),
    "dukprediab": ("Diabetes UK — مرحلة ما قبل السكري", "Diabetes UK — Prediabetes",
                   "https://www.diabetes.org.uk/preventing-type-2-diabetes/prediabetes"),
    "nhs_gout": ("NHS — أسباب النقرس", "NHS — Gout: causes", "https://www.nhs.uk/conditions/gout/causes/"),
    "nhs_nafld": ("NHS — الكبد الدهني غير الكحولي", "NHS — Non-alcoholic fatty liver disease",
                  "https://www.nhs.uk/conditions/non-alcoholic-fatty-liver-disease/"),
    "nhs_preg": ("NHS — الفيتامينات والتغذية أثناء الحمل", "NHS — Vitamins, supplements and nutrition in pregnancy",
                 "https://www.nhs.uk/pregnancy/keeping-well/vitamins-supplements-and-nutrition/"),
}

# Markers whose numbers must never be "fixed" with food or supplements.
DOCTOR_ONLY = frozenset({"sodium", "potassium", "chloride", "calcium", "magnesium", "phosphate", "co2", "wbc", "neut", "lymph",
                         "mono", "eos", "baso", "anc", "plt", "mpv", "inr", "lactate", "troponin"})
_ANEMIA_KEYS = ("hgb", "rbc", "hct", "mcv", "mch", "mchc")
_LIPID_HIGH = ("ldl", "chol_total", "triglycerides")
_SUGAR = ("glucose", "hba1c")

_PREGNANT = re.compile(r"حامل|حمل|pregnan", re.I)
_VEGETARIAN = re.compile(r"نباتي|نباتيه|نباتية|vegan|vegetarian", re.I)
_THINNER = re.compile(r"warfarin|وارفارين|marevan|ماريفان|apixaban|eliquis|rivaroxaban|xarelto|مميع|مميّع|blood thinner", re.I)
_METFORMIN = re.compile(r"metformin|ميتفورمين|glucophage|جلوكوفاج|omeprazole|اوميبرازول|أوميبرازول|esomeprazole|nexium|نيكسيوم", re.I)
_DIAB_MEDS = re.compile(r"insulin|انسولين|إنسولين|gliclazide|diamicron|glimepiride|amaryl|sulfonylurea|سكري", re.I)


def _src(*ids):
    return [{"name_ar": S[i][0], "name_en": S[i][1], "url": S[i][2]} for i in ids]


# ------------------------------------------------------------------ card content
# Each card: title, foods, helps, blocks, dont, ask_first, retest — (ar, en) lists/strings.
def _iron_card(pregnant: bool) -> dict:
    foods_ar = ["اللحم الأحمر", "الدجاج والسمك", "العدس والحمص والفول", "السبانخ والملوخية والورقيات", "البيض", "الحبوب المدعّمة بالحديد"]
    foods_en = ["red meat", "chicken and fish", "lentils, chickpeas and fava beans", "spinach, molokhia and leafy greens", "eggs",
                "iron-fortified cereals"]
    if not pregnant:  # liver is rich in iron but contains a lot of vitamin A, which is avoided in pregnancy (NHS)
        foods_ar.insert(0, "الكبدة")
        foods_en.insert(0, "liver")
    return {
        "title": ("كيف يُرفع مخزون الحديد", "How to raise iron stores"),
        "foods": (foods_ar, foods_en),
        "helps": (["أكل برتقال أو ليمون أو فلفل أو طماطم مع الوجبة (فيتامين C يزيد امتصاص الحديد)"],
                  ["Having orange, lemon, peppers or tomatoes with the meal (vitamin C increases iron absorption)"]),
        "blocks": (["الشاي والقهوة مع الأكل؛ الأفضل بعد الوجبة بساعة إلى ساعتين",
                    "الحليب ومنتجات الألبان أو الكالسيوم مع وجبة الحديد نفسها"],
                   ["Tea and coffee with meals; better one to two hours after eating",
                    "Milk, dairy or calcium together with the iron-rich meal"]),
        "dont": (["لا يُبدأ بحبوب الحديد ولا تُحدَّد جرعتها دون طبيب",
                  "نقص الحديد له سبب (نزيف، دورة غزيرة، ضعف امتصاص…) ويحتاج الطبيب يبحث عنه"],
                 ["Do not start iron tablets or choose a dose without a doctor",
                  "Low iron has a cause (bleeding, heavy periods, poor absorption…) that a doctor needs to look for"]),
        "ask_first": (["الحمل", "مرض في الكلى أو الأمعاء", "تناول مميّع للدم", "وجود دم في البراز أو براز أسود"],
                      ["pregnancy", "kidney or bowel disease", "taking a blood thinner", "blood in the stool or black stool"]),
        "retest": ("يحدد الطبيب موعد الإعادة، وغالبًا بعد عدة أسابيع من بدء العلاج", "Your doctor sets the retest date, usually a few weeks after treatment starts"),
        "sources": _src("moh_iron", "ods_iron") + (_src("nhs_preg") if pregnant else []),
    }


def _b12_card(vegetarian: bool, metformin: bool) -> dict:
    ask_ar = ["تنميل أو وخز في اليدين أو القدمين، أو تغيّر في الذاكرة أو المشي — هذه تحتاج طبيبًا قريبًا", "الحمل",
              "عملية سابقة في المعدة أو الأمعاء"]
    ask_en = ["numbness or tingling in hands or feet, or changes in memory or walking — these need a doctor soon", "pregnancy",
              "previous stomach or bowel surgery"]
    if metformin:
        ask_ar.append("الأدوية الحالية (الميتفورمين وأدوية حموضة المعدة قد تقلل امتصاص B12)")
        ask_en.append("your current medicines (metformin and stomach-acid medicines can lower B12 absorption)")
    helps_ar, helps_en = ["توزيع مصادر B12 على الوجبات خلال الأسبوع"], ["Spreading B12 sources across meals through the week"]
    if vegetarian:
        helps_ar.append("للنباتيين: الأطعمة المدعّمة بـB12 مهمة، وغالبًا يحتاج النباتي الصارم مكمّلًا يحدده الطبيب")
        helps_en.append("For vegetarians: B12-fortified foods matter, and a strict vegan diet usually needs a supplement chosen by a doctor")
    return {
        "title": ("كيف يُرفع فيتامين B12", "How to raise vitamin B12"),
        "foods": (["اللحم والدجاج", "السمك والتونة", "البيض", "الحليب واللبن والجبن", "الحبوب المدعّمة"],
                  ["meat and chicken", "fish and tuna", "eggs", "milk, laban and cheese", "fortified cereals"]),
        "helps": (helps_ar, helps_en),
        "blocks": ([], []),
        "dont": (["لا تُؤخذ حقن أو جرعات عالية دون طبيب؛ النقص الواضح قد يكون من ضعف الامتصاص ولا يكفيه الأكل"],
                 ["Do not take injections or high doses without a doctor; a clear deficiency can be an absorption problem that food alone will not fix"]),
        "ask_first": (ask_ar, ask_en),
        "retest": ("يحدد الطبيب موعد الإعادة حسب السبب والعلاج", "Your doctor sets the retest date based on the cause and treatment"),
        "sources": _src("nhs_b12", "ods_b12"),
    }


def _folate_card(pregnant: bool) -> dict:
    ask_ar, ask_en = ["الحمل أو التخطيط له (حمض الفوليك مهم جدًا، وجرعته يحددها الطبيب)", "أدوية الصرع أو الميثوتريكسات"], [
        "pregnancy or planning one (folic acid matters a lot, and the doctor sets the dose)", "epilepsy medicines or methotrexate"]
    return {
        "title": ("كيف يُرفع الفولات", "How to raise folate"),
        "foods": (["السبانخ والورقيات الخضراء", "البروكلي", "العدس والحمص والفاصوليا", "البرتقال", "الخبز والحبوب المدعّمة"],
                  ["spinach and leafy greens", "broccoli", "lentils, chickpeas and beans", "oranges", "fortified bread and cereals"]),
        "helps": (["أكل الخضار طازجة أو مطهوة قليلًا (الطبخ الطويل يتلف الفولات)"],
                  ["Eating vegetables fresh or lightly cooked (long cooking destroys folate)"]),
        "blocks": ([], []),
        "dont": (["لا يُبدأ بحمض الفوليك بجرعة عالية قبل فحص B12؛ الفوليك قد يخفي نقص B12 بينما يستمر ضرره على الأعصاب"],
                 ["Do not start high-dose folic acid before B12 is checked; folic acid can hide a B12 deficiency while its nerve damage continues"]),
        "ask_first": (ask_ar, ask_en),
        "retest": ("يحدد الطبيب موعد الإعادة", "Your doctor sets the retest date"),
        "sources": _src("nhs_b12", "ods_folate") + (_src("nhs_preg") if pregnant else []),
    }


def _vitd_card() -> dict:
    return {
        "title": ("كيف يُرفع فيتامين د", "How to raise vitamin D"),
        "foods": (["الأسماك الدهنية مثل السلمون والسردين", "صفار البيض", "الحليب واللبن المدعّم بفيتامين د", "الحبوب المدعّمة"],
                  ["oily fish such as salmon and sardines", "egg yolks", "vitamin D-fortified milk and laban", "fortified cereals"]),
        "helps": (["تعرّض قصير ومنتظم للشمس على الذراعين والساقين مع تجنّب حروق الشمس",
                   "إذا وصف الطبيب مكمّلًا: يُؤخذ مع وجبة فيها دهون لأن امتصاصه أفضل"],
                  ["Short, regular sun exposure on the arms and legs while avoiding sunburn",
                   "If a doctor prescribes a supplement: take it with a meal that has some fat, which improves absorption"]),
        "blocks": ([], []),
        "dont": (["لا تُؤخذ جرعات عالية دون طبيب؛ زيادة فيتامين د ترفع الكالسيوم وقد تضر الكلى"],
                 ["Do not take high doses without a doctor; too much vitamin D raises calcium and can harm the kidneys"]),
        "ask_first": (["مرض في الكلى أو حصى كلى", "ارتفاع الكالسيوم", "الحمل أو الرضاعة"],
                      ["kidney disease or kidney stones", "high calcium", "pregnancy or breastfeeding"]),
        "retest": ("غالبًا بعد نحو 3 أشهر من بدء العلاج، حسب الطبيب", "Usually about 3 months after treatment starts, as your doctor advises"),
        "sources": _src("nhs_vitd", "ods_vitd"),
    }


def _lipid_card(tg_high: bool, hdl_low: bool) -> dict:
    helps_ar = ["الشوفان والشعير والبقول (ألياف تخفض الكوليسترول الضار)", "زيت الزيتون والمكسرات غير المملحة والأفوكادو بدل الدهون الحيوانية",
                "السمك مرتين أسبوعيًا", "المشي السريع أو أي نشاط معظم أيام الأسبوع"]
    helps_en = ["oats, barley and pulses (fibre lowers LDL)", "olive oil, unsalted nuts and avocado instead of animal fats",
                "fish twice a week", "brisk walking or any activity on most days"]
    blocks_ar = ["السمن والزبدة والشحوم واللحوم الدهنية", "المقليات والوجبات السريعة والمعجنات"]
    blocks_en = ["ghee, butter, animal fat and fatty meat", "fried food, fast food and pastries"]
    if tg_high:
        blocks_ar.append("المشروبات المحلّاة والعصائر والحلويات والأرز والخبز الأبيض بكميات كبيرة (ترفع الدهون الثلاثية)")
        blocks_en.append("sugary drinks, juices, sweets, and large portions of white rice and bread (they raise triglycerides)")
    if hdl_low:
        helps_ar.append("ترك التدخين إن وُجد، والنشاط المنتظم يرفعان الكوليسترول النافع")
        helps_en.append("stopping smoking, if you smoke, and regular activity raise HDL")
    return {
        "title": ("كيف تتحسّن دهون الدم", "How to improve blood fats"),
        "foods": ([], []),
        "helps": (helps_ar, helps_en),
        "blocks": (blocks_ar, blocks_en),
        "dont": (["لا يُوقف دواء الكوليسترول الموصوف دون الطبيب"], ["Do not stop a prescribed cholesterol medicine without your doctor"]),
        "ask_first": (["وجود مرض قلب أو سكري أو تاريخ عائلي لأمراض القلب المبكرة — قد يحتاج علاجًا لا يكفيه الأكل"],
                      ["heart disease, diabetes, or a family history of early heart disease — treatment beyond diet may be needed"]),
        "retest": ("غالبًا بعد نحو 3 أشهر من تغيير نمط الحياة", "Usually about 3 months after lifestyle changes"),
        "sources": _src("nhs_chol"),
    }


def _sugar_card(on_diabetes_meds: bool) -> dict:
    ask_ar, ask_en = ["عند تناول أدوية السكري أو الإنسولين: تغيير الأكل فجأة قد يسبب هبوطًا، فالأفضل سؤال الطبيب أولًا"], [
        "If you take diabetes medicines or insulin: a sudden change in eating can cause a low, so ask your doctor first"]
    if on_diabetes_meds:
        ask_ar.insert(0, "مذكور في الملف دواء للسكري — تلزم مراجعة الطبيب قبل أي تغيير كبير")
        ask_en.insert(0, "A diabetes medicine is listed in your profile — check with your doctor before any big change")
    return {
        "title": ("كيف يتحسّن السكر", "How to improve blood sugar"),
        "foods": (["الخضار في نصف الطبق", "البروتين مثل الدجاج والسمك والبقول", "الحبوب الكاملة بدل الأبيض"],
                  ["vegetables on half the plate", "protein such as chicken, fish and pulses", "whole grains instead of white"]),
        "helps": (["المشي بعد الوجبات", "النوم الكافي", "خسارة جزء من الوزن إن كان زائدًا"],
                  ["Walking after meals", "Enough sleep", "Losing some weight if you are overweight"]),
        "blocks": (["المشروبات المحلّاة والعصائر والحلويات", "التمر بكميات كبيرة", "الأرز والخبز الأبيض بكميات كبيرة"],
                   ["sugary drinks, juices and sweets", "large amounts of dates", "large portions of white rice and white bread"]),
        "dont": (["لا يُبدأ دواء سكري أو أعشاب لخفض السكر دون طبيب"], ["Do not start diabetes medicines or herbal remedies without a doctor"]),
        "ask_first": (ask_ar, ask_en),
        "retest": ("السكر التراكمي يُعاد غالبًا بعد نحو 3 أشهر، حسب الطبيب", "HbA1c is usually repeated after about 3 months, as your doctor advises"),
        "sources": _src("dukprediab"),
    }


def _uric_card() -> dict:
    return {
        "title": ("كيف يقل حمض اليوريك", "How to lower uric acid"),
        "foods": ([], []),
        "helps": (["شرب الماء بانتظام خلال اليوم", "الحفاظ على وزن صحي تدريجيًا"], ["Drinking water regularly through the day", "Reaching a healthy weight gradually"]),
        "blocks": (["الأعضاء مثل الكبدة والكلاوي", "اللحوم الحمراء بكميات كبيرة", "السردين والأنشوجة والمأكولات البحرية",
                    "المشروبات المحلّاة بسكر الفاكهة (الفركتوز)"],
                   ["organ meats such as liver and kidney", "large amounts of red meat", "sardines, anchovies and seafood",
                    "drinks sweetened with fructose"]),
        "dont": (["لا يُبدأ دواء النقرس أو يُوقف دون طبيب"], ["Do not start or stop gout medicines without a doctor"]),
        "ask_first": (["مرض في الكلى", "ألم وتورم مفاجئ في مفصل — قد يكون نوبة نقرس تحتاج طبيبًا"],
                      ["kidney disease", "sudden pain and swelling in a joint — it may be a gout attack that needs a doctor"]),
        "retest": ("يحدد الطبيب موعد الإعادة", "Your doctor sets the retest date"),
        "sources": _src("nhs_gout"),
    }


# ------------------------------------------------------------------ helpers
def _status(results_by_key: dict, key: str) -> str:
    return str((results_by_key.get(key) or {}).get("status") or "")


def _pick(card: dict, lang: str) -> dict:
    i = 0 if lang == "ar" else 1
    return {
        "kind": "advice",
        "title": card["title"][i],
        "foods": list(card["foods"][i]),
        "helps": list(card["helps"][i]),
        "blocks": list(card["blocks"][i]),
        "dont": list(card["dont"][i]),
        "ask_first": list(card["ask_first"][i]),
        "retest": card["retest"][i],
        "sources": [{"name": s["name_ar" if lang == "ar" else "name_en"], "url": s["url"]} for s in card["sources"]],
        "reviewed_by_clinician": False,
    }


def _message(kind: str, text_ar: str, text_en: str, lang: str, sources=()) -> dict:
    return {"kind": kind, "message": text_ar if lang == "ar" else text_en,
            "sources": [{"name": s["name_ar" if lang == "ar" else "name_en"], "url": s["url"]} for s in sources],
            "reviewed_by_clinician": False}


_DOCTOR_ONLY_MSG = (
    "هذه القيمة لا تُعدَّل بالأكل أو المكمّلات، ومحاولة ذلك قد تكون خطرة. سببها يحتاج طبيبًا، وهو من يقرر العلاج.",
    "This value is not corrected with food or supplements, and trying to do so can be unsafe. Its cause needs a doctor, who decides the treatment.")
_CRITICAL_MSG = (
    "قيمة حرجة: لا تُعدَّل بالأكل أو المكمّلات. تحتاج تقييمًا طبيًا اليوم — يلزم التواصل مع الطبيب أو الطوارئ، والاتصال بـ997 إذا ظهرت أعراض شديدة.",
    "Critical value: do not try to correct it with food or supplements. It needs medical assessment today — contact your doctor or the emergency department, and call 997 if severe symptoms appear.")
_CHILD_MSG = (
    "احتياجات الأطفال الغذائية وجرعاتهم تختلف عن الكبار، لذلك لا نعرض قائمة نصائح عامة. الأفضل مناقشة النتيجة مع طبيب الأطفال، وهو يحدد الأكل المناسب وأي مكمّل.",
    "Children's nutritional needs and doses differ from adults', so no general advice list is shown. Discuss the result with the child's doctor, who decides the right foods and any supplement.")


def advice_for(key: str, result: dict, results_by_key: dict, *, age=None, pregnant=False, vegetarian=False,
               medications: str = "", lang: str = "ar") -> dict | None:
    """The card for one result, or None when no card applies (normal or unclassified values)."""
    lang = "ar" if lang == "ar" else "en"
    status = str(result.get("status") or "")
    if status not in {"low", "high"}:
        return None
    if str(result.get("attention_level") or "") in {"urgent", "emergency"} or result.get("critical_level"):
        return _message("critical", *_CRITICAL_MSG, lang)
    if key in DOCTOR_ONLY:
        return _message("doctor_only", *_DOCTOR_ONLY_MSG, lang)
    if age is not None and age < 18:
        return _message("child", *_CHILD_MSG, lang)
    ferritin = _status(results_by_key, "ferritin")
    b12, folate = _status(results_by_key, "b12"), _status(results_by_key, "folate")

    if key == "ferritin" and status == "low":
        return _pick(_iron_card(pregnant), lang) | {"pattern": ("الفيريتين منخفض: مخزون الحديد ناقص" if lang == "ar"
                                                                else "Low ferritin: iron stores are low")}
    if key == "ferritin" and status == "high":
        return _message("cause_first", "لا يُؤخذ حديد لتعديل هذا الرقم. ارتفاع الفيريتين قد يكون من التهاب أو الكبد أو زيادة الحديد، وسببه يحتاج طبيبًا.",
                        "Do not take iron to change this number. A high ferritin can come from inflammation, the liver or iron overload, and the cause needs a doctor.", lang)
    if key == "iron" and status == "low":
        if ferritin == "low":
            return None  # the ferritin card covers it
        return _message("cause_first", "حديد الدم يتغيّر خلال اليوم ومع الأكل، فلا يكفي وحده. الأدق فحص الفيريتين (مخزون الحديد) قبل أي علاج.",
                        "Blood iron changes through the day and with meals, so it is not enough alone. Ferritin (iron stores) is the better test before any treatment.", lang)
    if key in _ANEMIA_KEYS and status == "low":
        if ferritin == "low":
            return _message("pattern", "مع الفيريتين المنخفض في نفس التقرير، النمط يتوافق مع نقص الحديد — النصائح في بطاقة الفيريتين.",
                            "With low ferritin in the same report, the pattern fits iron deficiency — see the advice on the ferritin card.", lang)
        if b12 == "low" or folate == "low":
            return _message("pattern", "مع انخفاض B12 أو الفولات في نفس التقرير، قد يكون هذا سبب فقر الدم — النصائح في بطاقتهما.",
                            "With low B12 or folate in the same report, that may explain the anaemia — see the advice on those cards.", lang)
        mcv_low = _status(results_by_key, "mcv") == "low"
        return _message("cause_first",
                        ("فقر الدم له أسباب كثيرة، و«تناول الحديد» ليس دائمًا الحل الصحيح؛ تناول الحديد دون سبب قد يُخفي نزيفًا. "
                         + ("صِغر حجم الكريات (MCV منخفض) يجعل نقص الحديد محتملًا، لكن يلزم تأكيده. " if mcv_low else "")
                         + "يُطلب من الطبيب: الفيريتين وB12 والفولات، وبعدها تُعرض النصيحة المناسبة."),
                        ("Anaemia has many causes, and \"eat iron\" is not always right; taking iron without a cause can hide bleeding. "
                         + ("Small red cells (low MCV) make iron deficiency likely, but it needs confirming. " if mcv_low else "")
                         + "Ask your doctor for ferritin, B12 and folate; the right advice can be shown after that."), lang)
    if key == "b12" and status == "low":
        return _pick(_b12_card(vegetarian, bool(_METFORMIN.search(medications or ""))), lang)
    if key == "folate" and status == "low":
        return _pick(_folate_card(pregnant), lang)
    if key == "vitd" and status == "low":
        return _pick(_vitd_card(), lang)
    if key == "vitd" and status == "high":
        return _message("cause_first", "فيتامين د مرتفع: يُوقف أي مكمّل لفيتامين د حتى مراجعة الطبيب، فالزيادة ترفع الكالسيوم.",
                        "High vitamin D: pause any vitamin D supplement until you see your doctor, because too much raises calcium.", lang)
    if (key in _LIPID_HIGH and status == "high") or (key == "hdl" and status == "low"):
        return _pick(_lipid_card(_status(results_by_key, "triglycerides") == "high", _status(results_by_key, "hdl") == "low"), lang)
    if key in _SUGAR and status == "high":
        return _pick(_sugar_card(bool(_DIAB_MEDS.search(medications or ""))), lang)
    if key == "glucose" and status == "low":
        return _message("doctor_only", "انخفاض السكر يحتاج معرفة السبب مع الطبيب. إذا ظهرت رجفة أو تعرّق أو دوخة: يؤخذ سكر سريع مثل عصير أو تمر، ويُطلب الإسعاف إذا ظهر تشوش.",
                        "Low glucose needs its cause found with a doctor. If shakiness, sweating or dizziness appear: take fast sugar such as juice or dates, and call an ambulance if confusion appears.", lang)
    if key == "uric_acid" and status == "high":
        return _pick(_uric_card(), lang)
    if key in {"alt", "ast", "ggt"} and status == "high":
        return _message("cause_first",
                        "ارتفاع إنزيمات الكبد له أسباب كثيرة: أدوية (منها البنادول بجرعات عالية) أو التهاب فيروسي أو كبد دهني. إذا أكّد الطبيب أنه كبد دهني، فخسارة الوزن تدريجيًا وتقليل السكريات والمقليات والنشاط المنتظم هي الأساس.",
                        "Raised liver enzymes have many causes: medicines (including high doses of paracetamol), viral hepatitis or fatty liver. If your doctor confirms fatty liver, gradual weight loss, less sugar and fried food, and regular activity are the basis.",
                        lang, sources=_src("nhs_nafld"))
    return None


def attach(indicators: list[dict], results: list[dict], *, age=None, context: dict | None = None, medications: str = "",
           lang: str = "ar") -> list[dict]:
    """Add indicator["advice"] (or nothing) to every indicator; returns the indicators."""
    by_key = {str(r.get("key") or ""): r for r in results or []}
    notes = " ".join([str((context or {}).get("notes") or ""), str(medications or "")])
    pregnant = bool(_PREGNANT.search(notes))
    vegetarian = bool(_VEGETARIAN.search(notes))
    for item in indicators or []:
        key = str(item.get("key") or "")
        merged = dict(by_key.get(key) or {}, **{k: item.get(k) for k in ("status", "attention_level") if item.get(k) is not None})
        card = advice_for(key, merged, by_key, age=age, pregnant=pregnant, vegetarian=vegetarian, medications=medications, lang=lang)
        if card:
            if card.get("kind") == "advice" and _THINNER.search(medications or "") and key in {"vitd", "ldl", "chol_total", "triglycerides", "hdl"}:
                card["ask_first"].insert(0, "مذكور في الملف مميّع للدم: أي مكمّل أو تغيير كبير في الأكل يُراجع مع الطبيب أولًا" if lang == "ar"
                                         else "You take a blood thinner: check any supplement or big diet change with your doctor first")
            item["advice"] = card
    return indicators


def all_cards_for_review(lang: str = "ar") -> list[tuple[str, dict]]:
    """Every card text, for the clinician review packet and the safety tests."""
    out = [("iron", _pick(_iron_card(False), lang)), ("iron_pregnant", _pick(_iron_card(True), lang)),
           ("b12", _pick(_b12_card(True, True), lang)), ("folate", _pick(_folate_card(True), lang)), ("vitd", _pick(_vitd_card(), lang)),
           ("lipids", _pick(_lipid_card(True, True), lang)), ("sugar", _pick(_sugar_card(True), lang)), ("uric_acid", _pick(_uric_card(), lang))]
    for kind, (ar, en) in (("critical", _CRITICAL_MSG), ("doctor_only", _DOCTOR_ONLY_MSG), ("child", _CHILD_MSG)):
        out.append((kind, _message(kind, ar, en, lang)))
    return out
