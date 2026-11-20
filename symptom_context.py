"""Deterministic symptom-context extraction for natural-language symptom descriptions.

This module deliberately does not diagnose. It extracts structured context that is
already present in the user's text so the questionnaire can avoid repetitive
questions and the analysis can explain which context it used.
"""
from __future__ import annotations

import re

_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def _norm(text: str) -> str:
    s = str(text or "").translate(_ARABIC_DIGITS).lower()
    s = re.sub(r"[\u064b-\u065f\u0670]", "", s)
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ى", "ي").replace("ة", "ه")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _first_label(text: str, definitions):
    for label_ar, label_en, pattern in definitions:
        if re.search(pattern, text, re.I):
            return label_ar, label_en
    return None


def _duration(text: str, lang: str):
    # Preserve exactly what the user said where possible, rather than converting
    # to a guessed number of days.
    patterns = [
        r"(?:منذ|من)\s+(?:حوالي\s+)?(?:\d+|يومين|يوم|اسبوعين|اسبوع|شهرين|شهر|ساعتين|ساعه|دقيقتين|دقيقه)(?:\s+(?:دقيقه|دقائق|ساعه|ساعات|يوم|ايام|اسبوع|اسابيع|شهر|اشهر))?",
        r"(?:صار\s+لي|لي)\s+(?:حوالي\s+)?(?:\d+|يومين|يوم|اسبوعين|اسبوع|شهرين|شهر|ساعتين|ساعه)(?:\s+(?:ساعه|ساعات|يوم|ايام|اسبوع|اسابيع|شهر|اشهر))?",
        r"(?:for|since)\s+(?:about\s+)?\d+\s*(?:minutes?|hours?|days?|weeks?|months?)",
        r"(?:since)\s+(?:today|yesterday|this morning|last night)",
        r"(?:من\s+)?(?:اليوم|امس|الصباح|البارح|الليل)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            return m.group(0).strip()
    return None


def extract_context(text, found=None, lang="ar"):
    """Return context explicitly stated in free text.

    Keys are descriptive only; none are disease probabilities or diagnoses.
    """
    raw = str(text or "").strip()
    hay = _norm(raw)
    out = {
        "raw_description": raw,
        "duration": None,
        "onset": None,
        "course": None,
        "worse": [],
        "relief": [],
        "timing": [],
        "locations": [],
        "medication_context": None,
        "severity_text": None,
        "associated_count": len(found or []),
    }
    if not hay:
        return out

    out["duration"] = _duration(hay, lang)

    onset = _first_label(hay, [
        ("فجأة", "Sudden", r"\bفجاه\b|بشكل مفاجئ|مره وحده|sudden(?:ly)?|all of a sudden"),
        ("تدريجيًا", "Gradual", r"تدريج|بالتدريج|شوي شوي|gradual(?:ly)?|slowly developed"),
    ])
    if onset:
        out["onset"] = onset[0 if lang != "en" else 1]

    course = _first_label(hay, [
        ("مستمر", "Continuous", r"مستمر|طول الوقت|ما يوقف|continuous|constant|all the time"),
        ("يجي ويروح", "Comes and goes", r"يجي ويروح|يروح ويرجع|متقطع|على فترات|comes? and goes?|intermittent|on and off"),
        ("يزداد تدريجيًا", "Progressively worsening", r"قاعد يزيد|يزداد|اسوا مع الوقت|worsen(?:ing)? over time|getting worse"),
        ("يتحسن تدريجيًا", "Gradually improving", r"قاعد يخف|يتحسن|افضل مع الوقت|getting better|improving"),
    ])
    if course:
        out["course"] = course[0 if lang != "en" else 1]

    worse_defs = [
        ("مع الحركة", "Movement", r"مع الحرك|اذا تحرك|المشي|الجري|movement|moving|walking|running"),
        ("بعد الأكل", "After eating", r"بعد الاكل|بعد الطعام|بعد الوجبه|after eating|after food|after meals?"),
        ("مع الأكل", "With food", r"مع الاكل|وقت الاكل|with food|while eating"),
        ("عند الوقوف", "Standing up", r"عند الوقوف|لما اقوم|اذا وقفت|standing up|when i stand"),
        ("وقت الدورة", "During period", r"وقت الدوره|مع الدوره|قبل الدوره|بعد الدوره|menstrual|during (?:my )?period|menses"),
        ("بالليل", "At night", r"بالليل|ليلا|وقت النوم|at night|bedtime"),
        ("بعد المجهود", "After exertion", r"بعد المجهود|مع المجهود|رياضه|exercise|exertion"),
        ("مع التوتر", "Stress", r"مع التوتر|وقت القلق|ضغط نفسي|stress|anxiety"),
        ("مع الاستلقاء", "Lying down", r"مع الاستلقاء|اذا انسدحت|lying down|when lying"),
    ]
    for ar, en, pat in worse_defs:
        if re.search(pat, hay, re.I):
            label = ar if lang != "en" else en
            if label not in out["worse"]:
                out["worse"].append(label)

    relief_defs = [
        ("الراحة", "Rest", r"يخف.*راح|يرتاح.*راح|مع الراحه|rest helps|better with rest"),
        ("شرب السوائل", "Fluids", r"يخف.*سوائل|بعد شرب|المويه تساعد|الماء يساعد|fluids? help|after drinking"),
        ("الأكل", "Eating", r"يخف.*اكل|بعد ما اكل|eating helps|better after eating"),
        ("تغيير الوضعية", "Changing position", r"يخف.*وضعي|تغيير الوضعي|position helps|changing position"),
        ("النوم", "Sleep", r"يخف.*نوم|بعد النوم|sleep helps|better after sleep"),
    ]
    for ar, en, pat in relief_defs:
        if re.search(pat, hay, re.I):
            label = ar if lang != "en" else en
            if label not in out["relief"]:
                out["relief"].append(label)

    timing_defs = [
        ("الصباح", "Morning", r"الصباح|morning"),
        ("المساء", "Evening", r"المساء|evening"),
        ("الليل", "Night", r"الليل|ليلا|night"),
        ("بعد الاستيقاظ", "After waking", r"بعد ما اصحى|بعد الاستيقاظ|after waking|upon waking"),
    ]
    for ar, en, pat in timing_defs:
        if re.search(pat, hay, re.I):
            label = ar if lang != "en" else en
            if label not in out["timing"]:
                out["timing"].append(label)

    location_defs = [
        ("الرأس", "Head", r"راس|صداع|head|headache"),
        ("الحلق", "Throat", r"حلق|throat"),
        ("الصدر", "Chest", r"صدر|chest"),
        ("البطن", "Abdomen", r"بطن|معده|مغص|abdomen|abdominal|stomach|belly"),
        ("الظهر", "Back", r"ظهر|back"),
        ("الذراع", "Arm", r"ذراع|كتف|(?:^|\s)(?:يد|يدي|اليد)(?:\s|$)|arm|shoulder|(?:^|\s)hand(?:\s|$)"),
        ("الساق", "Leg", r"ساق|رجل|ركبه|ركبتي|قدم|كاحل|فخذ|leg|knee|foot|ankle|thigh"),
        ("الجلد", "Skin", r"جلد|طفح|حكه|skin|rash|itch"),
    ]
    for ar, en, pat in location_defs:
        if re.search(pat, hay, re.I):
            label = ar if lang != "en" else en
            if label not in out["locations"]:
                out["locations"].append(label)

    med = _first_label(hay, [
        ("دواء جديد", "New medication", r"دواء جديد|علاج جديد|بديت دواء|بعد الدواء|new medication|new medicine|started .*med"),
        ("بعد جرعة دواء", "After a medication dose", r"بعد الجرعه|بعد جرعه|after (?:a )?dose"),
    ])
    if med:
        out["medication_context"] = med[0 if lang != "en" else 1]

    sev = _first_label(hay, [
        ("شديد", "Severe", r"شديد|قوي(?: جدا)?|لا يحتمل|severe|very bad|unbearable"),
        ("متوسط", "Moderate", r"متوسط|moderate"),
        ("خفيف", "Mild", r"خفيف|بسيط|mild|slight"),
    ])
    if sev:
        out["severity_text"] = sev[0 if lang != "en" else 1]

    return out


def pattern_summary(patient, lang="ar"):
    """Build a concise, non-diagnostic summary of the symptom pattern."""
    symptoms = [str(x).strip() for x in (patient.get("symptoms") or []) if str(x).strip()]
    onset = str(patient.get("onset") or "").strip()
    course = str(patient.get("course") or "").strip()
    worse = str(patient.get("pattern_worse") or "").strip()
    relief = str(patient.get("pattern_relief") or "").strip()
    duration = str(patient.get("duration") or "").strip()
    parts = []
    if len(symptoms) > 1:
        parts.append(("أعراض مترابطة: " if lang != "en" else "Combined symptoms: ") + ("، ".join(symptoms[:5]) if lang != "en" else ", ".join(symptoms[:5])))
    if duration:
        parts.append(("المدة: " if lang != "en" else "Duration: ") + duration)
    if onset:
        parts.append(("البداية: " if lang != "en" else "Onset: ") + onset)
    if course:
        parts.append(("المسار: " if lang != "en" else "Course: ") + course)
    if worse and worse.lower() not in {"غير محدد", "not specified", "غير واضح", "not clear"}:
        parts.append(("يزداد مع: " if lang != "en" else "Worse with: ") + worse)
    if relief and relief.lower() not in {"غير محدد", "not specified", "غير واضح", "not clear"}:
        parts.append(("يخف مع: " if lang != "en" else "Relieved by: ") + relief)
    if not parts:
        return None
    return {
        "title": "ملخص نمط الأعراض" if lang != "en" else "Symptom pattern summary",
        "text": " · ".join(parts),
        "note": ("هذا تلخيص للسياق الذي أدخلته وليس تشخيصًا." if lang != "en" else "This summarizes the context you entered; it is not a diagnosis."),
    }
