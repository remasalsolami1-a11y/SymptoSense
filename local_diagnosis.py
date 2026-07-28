"""
local_diagnosis.py
A lightweight, locally-computed symptom-matching model.

Instead of depending on a paid/gated third-party diagnosis API, this module
holds a small curated knowledge base of common primary-care conditions and
their typical symptoms, and scores how well a patient's reported symptoms
match each condition using Jaccard similarity:

    similarity(A, B) = |A ∩ B| / |A ∪ B|

This is an honest, explainable statistical matching score — NOT a clinical
diagnosis or a calibrated probability. It's meant as a transparent, offline
cross-check alongside the LLM's own reasoning.
"""

import re

# condition -> (display name ar, display name en, {keywords in ar/en})
KNOWLEDGE_BASE = {
    "common_cold": (
        "نزلة برد", "Common Cold",
        {"صداع", "سعال", "حمى", "تعب وإرهاق", "قشعريرة",
         "headache", "cough", "fever", "fatigue", "chills"},
    ),
    "flu": (
        "إنفلونزا", "Influenza",
        {"حمى", "صداع", "تعب وإرهاق", "ألم المفاصل", "قشعريرة", "سعال",
         "fever", "headache", "fatigue", "joint pain", "chills", "cough"},
    ),
    "migraine": (
        "شقيقة (صداع نصفي)", "Migraine",
        {"صداع", "غثيان", "دوار",
         "headache", "nausea", "dizziness"},
    ),
    "gastroenteritis": (
        "التهاب معدي معوي", "Gastroenteritis",
        {"غثيان", "ألم في البطن", "حمى", "قشعريرة",
         "nausea", "stomach pain", "fever", "chills"},
    ),
    "allergic_rhinitis": (
        "حساسية أنفية", "Allergic Rhinitis",
        {"سعال", "احمرار العيون", "صداع",
         "cough", "red eyes", "headache"},
    ),
    "sinusitis": (
        "التهاب الجيوب الأنفية", "Sinusitis",
        {"صداع", "سعال", "حمى",
         "headache", "cough", "fever"},
    ),
    "bronchitis": (
        "التهاب الشعب الهوائية", "Bronchitis",
        {"سعال", "ضيق التنفس", "تعب وإرهاق", "ألم في الصدر",
         "cough", "shortness of breath", "fatigue", "chest pain"},
    ),
    "pharyngitis": (
        "التهاب الحلق", "Pharyngitis",
        {"حمى", "سعال", "تعب وإرهاق",
         "fever", "cough", "fatigue"},
    ),
    "food_poisoning": (
        "تسمم غذائي", "Food Poisoning",
        {"غثيان", "ألم في البطن", "قشعريرة", "حمى",
         "nausea", "stomach pain", "chills", "fever"},
    ),
    "anxiety": (
        "أعراض قلق", "Anxiety-related symptoms",
        {"دوار", "ضيق التنفس", "تعب وإرهاق", "ألم في الصدر",
         "dizziness", "shortness of breath", "fatigue", "chest pain"},
    ),
    "vertigo": (
        "دوار (اضطراب توازن)", "Vertigo",
        {"دوار", "غثيان",
         "dizziness", "nausea"},
    ),
    "muscle_strain": (
        "شد عضلي", "Muscle Strain",
        {"ألم المفاصل", "تعب وإرهاق",
         "joint pain", "fatigue"},
    ),
    "conjunctivitis": (
        "التهاب ملتحمة العين", "Conjunctivitis",
        {"احمرار العيون", "حمى",
         "red eyes", "fever"},
    ),
    "asthma_flare": (
        "نوبة ربو", "Asthma Flare-up",
        {"ضيق التنفس", "سعال", "ألم في الصدر",
         "shortness of breath", "cough", "chest pain"},
    ),
    "dehydration": (
        "جفاف", "Dehydration",
        {"دوار", "تعب وإرهاق", "غثيان",
         "dizziness", "fatigue", "nausea"},
    ),
}


def _normalize(symptoms):
    """Lowercase + strip so Arabic/English keyword matching is consistent."""
    return {re.sub(r'\s+', ' ', s).strip().lower() for s in symptoms if s}


def get_verified_conditions(symptoms, age=None, sex=None, top_n=3, min_score=0.15):
    """
    symptoms: list of reported symptom strings (Arabic or English)
    Returns up to top_n conditions as [{"name_ar", "name_en", "score"}], sorted desc.
    Only conditions with Jaccard similarity >= min_score are returned, to avoid
    showing noisy/irrelevant matches when overlap is too weak.
    """
    reported = _normalize(symptoms)
    if not reported:
        return []

    results = []
    for _, (name_ar, name_en, keywords) in KNOWLEDGE_BASE.items():
        kb = _normalize(keywords)
        intersection = reported & kb
        if not intersection:
            continue
        union = reported | kb
        score = len(intersection) / len(union)
        if score >= min_score:
            results.append({"name_ar": name_ar, "name_en": name_en, "score": score})

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_n]
