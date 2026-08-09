"""
medication_warnings.py — lightweight, curated general-caution notes for common
over-the-counter/common medications. This is NOT a drug-interaction checker —
it flags well-known general cautions for a single mentioned medication, based
on simple keyword matching against the patient's free-text notes.
"""

import re

# key -> (ar name, en name, {ar/en keyword variants}, ar warning, en warning,
#          ar uses, en uses, ar interactions, en interactions)
MEDICATIONS = {
    "aspirin": (
        "أسبرين", "Aspirin",
        {"أسبرين", "اسبرين", "aspirin"},
        "قد يسبب تهيّج بالمعدة أو نزيف خفيف عند بعض الأشخاص، خصوصاً مع أعراض مثل ألم البطن أو الغثيان.",
        "May cause stomach irritation or mild bleeding in some people, especially alongside symptoms like stomach pain or nausea.",
        "تسكين الألم الخفيف إلى المتوسط، خفض الحمى، والوقاية من الجلطات عند وصفه من الطبيب.",
        "Relieving mild to moderate pain, reducing fever, and preventing clots when prescribed by a doctor.",
        "قد يتداخل مع مميعات الدم (مثل الوارفارين)، والمسكنات الأخرى (مثل الإيبوبروفين)، وبعض أدوية الضغط والسكري.",
        "May interact with blood thinners (e.g. warfarin), other painkillers (e.g. ibuprofen), and some blood pressure or diabetes medications.",
    ),
    "ibuprofen": (
        "بروفين", "Ibuprofen",
        {"بروفين", "ibuprofen", "advil", "برفين"},
        "قد يهيّج المعدة إذا أُخذ بدون طعام، وغير مناسب لبعض حالات الجفاف أو مشاكل الكلى.",
        "Can irritate the stomach if taken without food, and isn't ideal during dehydration or with kidney issues.",
        "تسكين الألم والالتهاب وخفض الحمى.",
        "Relieving pain, inflammation, and fever.",
        "قد يزيد خطر النزف عند تناوله مع مميعات الدم أو الأسبرين أو الكورتيزون، ويقلل فعالية بعض أدوية الضغط.",
        "May increase bleeding risk with blood thinners, aspirin, or corticosteroids, and may reduce the effect of some blood pressure medications.",
    ),
    "paracetamol": (
        "بنادول / باراسيتامول", "Paracetamol / Acetaminophen",
        {"بنادول", "باراسيتامول", "paracetamol", "acetaminophen", "panadol", "tylenol"},
        "آمن عموماً بالجرعة الموصوفة، لكن تجاوز الجرعة اليومية القصوى قد يضر الكبد.",
        "Generally safe at recommended doses, but exceeding the daily maximum can harm the liver.",
        "تسكين الألم وخفض الحمى، خاصة عند من لا يناسبهم مضادات الالتهاب.",
        "Relieving pain and fever, especially for those who can't take anti-inflammatories.",
        "التداخل المهم هو تجاوز الجرعة اليومية القصوى (خصوصاً مع أدوية البرد التي تحتوي باراسيتامول) — وقد يتداخل مع بعض أدوية الكبد.",
        "The key concern is exceeding the daily maximum (especially with cold medicines that also contain paracetamol) — may interact with some liver-affecting medications.",
    ),
    "antibiotics": (
        "مضاد حيوي", "Antibiotics",
        {"مضاد حيوي", "مضادات حيوية", "antibiotic", "antibiotics", "أموكسيسيلين", "amoxicillin"},
        "مهم إكمال الجرعة كاملة حسب وصف الطبيب حتى لو تحسنتِ، وعدم استخدامه بدون وصفة طبية.",
        "Important to complete the full prescribed course even if you feel better, and avoid use without a doctor's prescription.",
        "علاج الالتهابات البكتيرية التي يصفها الطبيب.",
        "Treating bacterial infections as prescribed by a doctor.",
        "قد يضعف فعالية حبوب منع الحمل، ويتداخل مع مميعات الدم وبعض أدوية المعدة — أبلغ طبيبك بكل ما تتناوله.",
        "May reduce the effectiveness of birth control pills and interact with blood thinners and some stomach medications — tell your doctor everything you take.",
    ),
    "antihistamine": (
        "مضاد هيستامين", "Antihistamine",
        {"مضاد هيستامين", "antihistamine", "زيرتك", "zyrtec", "كلاريتين", "claritin"},
        "بعض الأنواع تسبب نعاس — تجنبي القيادة أو الأنشطة اللي تحتاج تركيز بعد أخذه.",
        "Some types cause drowsiness — avoid driving or activities needing focus after taking it.",
        "علاج أعراض الحساسية مثل العطس والحكة وسيلان الأنف.",
        "Treating allergy symptoms such as sneezing, itching, and runny nose.",
        "قد يزيد التأثير المهدئ مع المهدئات وأدوية القلق والكحول وبعض أدوية الضغط.",
        "May increase the sedative effect with tranquilizers, anxiety medicines, alcohol, and some blood pressure medications.",
    ),
    "decongestant": (
        "مزيل احتقان", "Decongestant",
        {"مزيل احتقان", "decongestant", "سودافين", "sudafed"},
        "قد يرفع ضغط الدم عند بعض الأشخاص — يُفضّل الحذر لمن عندهم ضغط مرتفع.",
        "May raise blood pressure in some people — caution advised for those with hypertension.",
        "تخفيف انسداد الأنف الناتج عن الزكام أو الحساسية.",
        "Relieving nasal congestion from colds or allergies.",
        "قد يرفع ضغط الدم — الحذر مع أدوية الضغط ومثبطات MAO وبعض أدوية القلب.",
        "May raise blood pressure — caution with blood pressure medicines, MAO inhibitors, and some heart medications.",
    ),
    "diclofenac": (
        "فولتارين / ديكلوفيناك", "Diclofenac / Voltaren",
        {"فولتارين", "فولترين", "ديكلوفيناك", "diclofenac", "voltaren"},
        "يُفضّل أخذه مع الطعام لتقليل تهيّج المعدة، وممنوع لمن عندهم قرحة معدية أو مشاكل كلى.",
        "Best taken with food to reduce stomach irritation; avoid with stomach ulcers or kidney problems.",
        "تسكين الألم والالتهاب (آلام المفاصل والعضلات وغيرها).",
        "Relieving pain and inflammation (joint, muscle, and other pains).",
        "قد يزيد خطر النزف والمشاكل الكلوية مع مميعات الدم ومدرات البول ومضادات الالتهاب الأخرى.",
        "May increase bleeding and kidney risk with blood thinners, diuretics, and other anti-inflammatories.",
    ),
    "metformin": (
        "متفورمين / جلوكوفاج", "Metformin / Glucophage",
        {"متفورمين", "متفورمن", "جلوكوفاج", "metformin", "glucophage"},
        "يُفضل أخذه مع الوجبات، وقد يسبب غثيان أو إسهال بسيط في البداية يزول غالباً.",
        "Best taken with meals; may cause mild nausea or diarrhea initially, which usually settles.",
        "ضبط سكر الدم في مرض السكري من النوع الثاني.",
        "Controlling blood sugar in type 2 diabetes.",
        "قد يتداخل مع الكورتيزون ومدرات البول وبعض أدوية القلب والكلى — وقد تزداد حموضة الدم مع شرب الكحول.",
        "May interact with corticosteroids, diuretics, and some heart/kidney medications — alcohol may increase the risk of lactic acidosis.",
    ),
    "amlodipine": (
        "أملوديبين", "Amlodipine",
        {"أملوديبين", "amlodipine", "نورفاسك", "norvasc"},
        "قد يسبب تورماً خفيفاً بالكاحلين — لو زاد التورم فجأة أو صار تنفس صعب، راجعي طبيبك.",
        "May cause mild ankle swelling — if swelling suddenly worsens or breathing is hard, see your doctor.",
        "علاج ارتفاع ضغط الدم وبعض حالات الذبحة الصدرية.",
        "Treating high blood pressure and some cases of angina.",
        "قد يزداد انخفاض الضغط مع أدوية الضغط الأخرى والكحول، ويتداخل مع بعض مضادات الفطريات والمضادات الحيوية.",
        "Blood pressure may drop further with other pressure medicines and alcohol; may interact with some antifungals and antibiotics.",
    ),
    "omeprazole": (
        "أوميبرازول", "Omeprazole",
        {"أوميبرازول", "omeprazole", "لوسيك", "losec", "أوميز", "omez"},
        "يُفضل أخذه قبل الأكل بنصف ساعة، ويستخدم عادةً لفترات محددة — لا تطوّلي استخدامه دون استشارة طبيب.",
        "Best taken 30 minutes before meals, usually for limited periods — don't use long-term without a doctor.",
        "تقليل حموضة المعدة وعلاج قرحة المعدة والارتجاع.",
        "Reducing stomach acid and treating ulcers and reflux.",
        "قد يقلل امتصاص بعض الأدوية مثل كلوبيدوجريل وبعض مضادات الفطريات، ويؤثر على امتصاص الحديد والمغنيسيوم.",
        "May reduce absorption of some medications such as clopidogrel and some antifungals, and affects iron/magnesium absorption.",
    ),
}


def _unpack(entry):
    name_ar, name_en, keywords, warn_ar, warn_en, uses_ar, uses_en, interact_ar, interact_en = entry
    return name_ar, name_en, keywords, warn_ar, warn_en, uses_ar, uses_en, interact_ar, interact_en


def check_medications(notes: str):
    """Returns a list of {"name", "warning"} dicts for any recognized medication
    mentioned in the free-text notes (lang-appropriate)."""
    if not notes:
        return []
    text = notes.lower()
    matches = []
    seen = set()
    for key, entry in MEDICATIONS.items():
        if key in seen:
            continue
        name_ar, name_en, keywords, warn_ar, warn_en, *_ = _unpack(entry)
        for kw in keywords:
            if kw.lower() in text:
                matches.append({
                    "name_ar": name_ar, "name_en": name_en,
                    "warning_ar": warn_ar, "warning_en": warn_en,
                })
                seen.add(key)
                break
    return matches


def lookup_drug(name: str):
    """Returns the full medication info dict if the given name matches a known drug, else None."""
    if not name:
        return None
    text = name.lower()
    for entry in MEDICATIONS.values():
        name_ar, name_en, keywords, warn_ar, warn_en, uses_ar, uses_en, interact_ar, interact_en = _unpack(entry)
        for kw in keywords:
            if kw.lower() in text or text in kw.lower():
                return {
                    "name_ar": name_ar, "name_en": name_en,
                    "warning_ar": warn_ar, "warning_en": warn_en,
                    "uses_ar": uses_ar, "uses_en": uses_en,
                    "interact_ar": interact_ar, "interact_en": interact_en,
                }
    return None
