"""
medication_warnings.py — lightweight, curated general-caution notes for common
over-the-counter/common medications. This is NOT a drug-interaction checker —
it flags well-known general cautions for a single mentioned medication, based
on simple keyword matching against the patient's free-text notes.
"""

import re

# key -> (ar name, en name, {ar/en keyword variants}, ar warning, en warning)
MEDICATIONS = {
    "aspirin": (
        "أسبرين", "Aspirin",
        {"أسبرين", "اسبرين", "aspirin"},
        "قد يسبب تهيّج بالمعدة أو نزيف خفيف عند بعض الأشخاص، خصوصاً مع أعراض مثل ألم البطن أو الغثيان.",
        "May cause stomach irritation or mild bleeding in some people, especially alongside symptoms like stomach pain or nausea.",
    ),
    "ibuprofen": (
        "بروفين", "Ibuprofen",
        {"بروفين", "ibuprofen", "advil", "برفين"},
        "قد يهيّج المعدة إذا أُخذ بدون طعام، وغير مناسب لبعض حالات الجفاف أو مشاكل الكلى.",
        "Can irritate the stomach if taken without food, and isn't ideal during dehydration or with kidney issues.",
    ),
    "paracetamol": (
        "بنادول / باراسيتامول", "Paracetamol / Acetaminophen",
        {"بنادول", "باراسيتامول", "paracetamol", "acetaminophen", "panadol", "tylenol"},
        "آمن عموماً بالجرعة الموصوفة، لكن تجاوز الجرعة اليومية القصوى قد يضر الكبد.",
        "Generally safe at recommended doses, but exceeding the daily maximum can harm the liver.",
    ),
    "antibiotics": (
        "مضاد حيوي", "Antibiotics",
        {"مضاد حيوي", "مضادات حيوية", "antibiotic", "antibiotics", "أموكسيسيلين", "amoxicillin"},
        "مهم إكمال الجرعة كاملة حسب وصف الطبيب حتى لو تحسنتِ، وعدم استخدامه بدون وصفة طبية.",
        "Important to complete the full prescribed course even if you feel better, and avoid use without a doctor's prescription.",
    ),
    "antihistamine": (
        "مضاد هيستامين", "Antihistamine",
        {"مضاد هيستامين", "antihistamine", "زيرتك", "zyrtec", "كلاريتين", "claritin"},
        "بعض الأنواع تسبب نعاس — تجنبي القيادة أو الأنشطة اللي تحتاج تركيز بعد أخذه.",
        "Some types cause drowsiness — avoid driving or activities needing focus after taking it.",
    ),
    "decongestant": (
        "مزيل احتقان", "Decongestant",
        {"مزيل احتقان", "decongestant", "سودافين", "sudafed"},
        "قد يرفع ضغط الدم عند بعض الأشخاص — يُفضّل الحذر لمن عندهم ضغط مرتفع.",
        "May raise blood pressure in some people — caution advised for those with hypertension.",
    ),
}


def check_medications(notes: str):
    """Returns a list of {"name", "warning"} dicts for any recognized medication
    mentioned in the free-text notes (lang-appropriate)."""
    if not notes:
        return []
    text = notes.lower()
    matches = []
    seen = set()
    for key, (name_ar, name_en, keywords, warn_ar, warn_en) in MEDICATIONS.items():
        if key in seen:
            continue
        for kw in keywords:
            if kw.lower() in text:
                matches.append({
                    "name_ar": name_ar, "name_en": name_en,
                    "warning_ar": warn_ar, "warning_en": warn_en,
                })
                seen.add(key)
                break
    return matches
