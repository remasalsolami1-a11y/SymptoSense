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
    "ألم في الرجل": "leg pain", "leg pain": "leg pain",
    "ألم في الساق": "leg pain", "ألم الساق": "leg pain",
    "pain in the leg": "leg pain", "leg ache": "leg pain",
    "ألم الحلق": "sore throat", "sore throat": "sore throat",
    "التهاب الحلق": "sore throat", "throat pain": "sore throat",
    "حكة": "itching", "حكّة": "itching", "itching": "itching",
    "حكة جلدية": "itching", "حكة بالجلد": "itching",
    "itchy": "itching", "itching skin": "itching",
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



def explain_prediction(symptoms):
    """Explain the auxiliary BernoulliNB prediction using its real learned parameters.

    The user-facing assessment in SymptoSense is grounded in the Medical Knowledge
    Base and safety rules. This helper therefore returns an *auxiliary* model
    explanation only; callers must not present it as the reason for the displayed
    medical assessment unless that model is explicitly used for that output.

    Contributions are exact log-likelihood margin contributions for the predicted
    class versus the runner-up class. No synthetic feature importance is created.
    """
    x = _vectorize(symptoms)
    if sum(x) == 0:
        return {"available": False, "reason": "no_recognized_model_features", "used_for_display": False}

    log_scores = []
    for ci in range(len(CLASSES)):
        score = CLASS_LOG_PRIOR[ci]
        for fi, xi in enumerate(x):
            score += FEATURE_LOG_PROB[ci][fi] if xi else FEATURE_LOG_NEG_PROB[ci][fi]
        log_scores.append(score)
    order = sorted(range(len(log_scores)), key=lambda i: log_scores[i], reverse=True)
    top = order[0]
    runner = order[1] if len(order) > 1 else order[0]

    contributions = []
    for fi, xi in enumerate(x):
        if not xi:
            continue
        value = float(FEATURE_LOG_PROB[top][fi]) - float(FEATURE_LOG_PROB[runner][fi])
        contributions.append({"feature": VOCAB[fi], "log_margin_contribution": round(value, 6)})
    contributions.sort(key=lambda row: abs(row["log_margin_contribution"]), reverse=True)

    max_abs = max((abs(x["log_margin_contribution"]) for x in contributions), default=0.0)
    for row in contributions:
        ratio = abs(row["log_margin_contribution"]) / max_abs if max_abs else 0.0
        row["influence"] = "high" if ratio >= 0.67 else ("medium" if ratio >= 0.34 else "low")
        row["direction"] = "supports_top" if row["log_margin_contribution"] >= 0 else "supports_runner_up"

    return {
        "available": True,
        "used_for_display": False,
        "algorithm": META.get("algorithm", "BernoulliNB"),
        "top_class": CLASSES[top],
        "top_name_ar": CLASS_NAMES[CLASSES[top]]["ar"],
        "top_name_en": CLASS_NAMES[CLASSES[top]]["en"],
        "runner_up_class": CLASSES[runner],
        "runner_up_name_ar": CLASS_NAMES[CLASSES[runner]]["ar"],
        "runner_up_name_en": CLASS_NAMES[CLASSES[runner]]["en"],
        "log_margin": round(float(log_scores[top] - log_scores[runner]), 6),
        "contributions": contributions,
    }


def model_info():
    return META
