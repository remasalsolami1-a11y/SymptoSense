"""
ml_diagnosis.py — real, trained Naive Bayes classifier for symptom-based
condition prediction, with pure-Python inference (no scikit-learn required
at runtime — the model was trained offline with scikit-learn and its
learned parameters were exported to ml_model.json).

See ml_training/train_model.py for the training pipeline, dataset
generation, and evaluation (accuracy + classification report).
"""

import os
import json
import math

_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ml_model.json")

with open(_MODEL_PATH, encoding="utf-8") as f:
    _MODEL = json.load(f)

VOCAB = _MODEL["vocab"]
CLASSES = _MODEL["classes"]
CLASS_NAMES = _MODEL["class_names"]
CLASS_LOG_PRIOR = _MODEL["class_log_prior"]
FEATURE_LOG_PROB = _MODEL["feature_log_prob"]
FEATURE_LOG_NEG_PROB = _MODEL["feature_log_neg_prob"]
META = _MODEL.get("meta", {})

SYNONYMS = {
    "صداع": "headache", "headache": "headache",
    "حمى": "fever", "fever": "fever",
    "سعال": "cough", "cough": "cough",
    "ألم في الصدر": "chest pain", "chest pain": "chest pain",
    "غثيان": "nausea", "nausea": "nausea",
    "تعب وإرهاق": "fatigue", "fatigue": "fatigue",
    "ضيق التنفس": "shortness of breath", "shortness of breath": "shortness of breath",
    "دوار": "dizziness", "dizziness": "dizziness",
    "ألم المفاصل": "joint pain", "joint pain": "joint pain",
    "ألم في البطن": "stomach pain", "stomach pain": "stomach pain",
    "قشعريرة": "chills", "chills": "chills",
    "احمرار العيون": "red eyes", "red eyes": "red eyes",
}


def _vectorize(symptoms):
    reported = {SYNONYMS.get(s.strip().lower()) for s in symptoms}
    reported.discard(None)
    return [1 if v in reported else 0 for v in VOCAB]


def predict_conditions(symptoms, top_n=3, min_probability=0.08):
    """
    symptoms: list of reported symptom strings (Arabic or English).
    Returns up to top_n conditions as
      [{"name_ar", "name_en", "probability"}], sorted by probability desc.
    Probabilities are true Bayesian posteriors P(condition | symptoms),
    normalized to sum to 1 across all known classes (Naive Bayes assumption).
    """
    x = _vectorize(symptoms)
    if sum(x) == 0:
        return []

    log_scores = []
    for ci in range(len(CLASSES)):
        score = CLASS_LOG_PRIOR[ci]
        for fi, xi in enumerate(x):
            score += FEATURE_LOG_PROB[ci][fi] if xi else FEATURE_LOG_NEG_PROB[ci][fi]
        log_scores.append(score)

    # softmax normalize (log-sum-exp trick for numerical stability)
    max_score = max(log_scores)
    exp_scores = [math.exp(s - max_score) for s in log_scores]
    total = sum(exp_scores)
    probs = [s / total for s in exp_scores]

    results = [
        {"name_ar": CLASS_NAMES[cls]["ar"], "name_en": CLASS_NAMES[cls]["en"], "probability": p}
        for cls, p in zip(CLASSES, probs)
        if p >= min_probability
    ]
    results.sort(key=lambda r: r["probability"], reverse=True)
    return results[:top_n]


def model_info():
    return META
