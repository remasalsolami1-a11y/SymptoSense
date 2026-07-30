"""
train_model.py — offline training pipeline for SymptoSense's ML condition classifier.

This is run ONCE (offline, here) to produce ml_model.json, which the bot loads
at runtime with pure-Python inference (no scikit-learn needed in production —
keeps the Railway deployment light).

Pipeline:
  1. Build a labeled synthetic dataset from the curated knowledge base
     (each condition -> typical symptom set), simulating realistic partial
     symptom reporting + occasional noise.
  2. Train/test split, train a Bernoulli Naive Bayes classifier.
  3. Evaluate (accuracy + per-class report) so the numbers are honest and
     reproducible, not just claimed.
  4. Export class priors + feature probabilities to JSON for lightweight
     pure-Python inference in the bot.
"""

import json
import random
import numpy as np
from sklearn.naive_bayes import BernoulliNB
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

random.seed(42)
np.random.seed(42)

# ---- 1. Knowledge base (condition -> ar/en names + typical symptom keywords) ----
KNOWLEDGE_BASE = {
    "common_cold": ("نزلة برد", "Common Cold",
        {"صداع", "سعال", "حمى", "تعب وإرهاق", "قشعريرة",
         "headache", "cough", "fever", "fatigue", "chills"}),
    "flu": ("إنفلونزا", "Influenza",
        {"حمى", "صداع", "تعب وإرهاق", "ألم المفاصل", "قشعريرة", "سعال",
         "fever", "headache", "fatigue", "joint pain", "chills", "cough"}),
    "migraine": ("شقيقة (صداع نصفي)", "Migraine",
        {"صداع", "غثيان", "دوار", "headache", "nausea", "dizziness"}),
    "gastroenteritis": ("التهاب معدي معوي", "Gastroenteritis",
        {"غثيان", "ألم في البطن", "حمى", "قشعريرة",
         "nausea", "stomach pain", "fever", "chills"}),
    "allergic_rhinitis": ("حساسية أنفية", "Allergic Rhinitis",
        {"سعال", "احمرار العيون", "صداع", "cough", "red eyes", "headache"}),
    "sinusitis": ("التهاب الجيوب الأنفية", "Sinusitis",
        {"صداع", "سعال", "حمى", "headache", "cough", "fever"}),
    "bronchitis": ("التهاب الشعب الهوائية", "Bronchitis",
        {"سعال", "ضيق التنفس", "تعب وإرهاق", "ألم في الصدر",
         "cough", "shortness of breath", "fatigue", "chest pain"}),
    "pharyngitis": ("التهاب الحلق", "Pharyngitis",
        {"حمى", "سعال", "تعب وإرهاق", "fever", "cough", "fatigue"}),
    "food_poisoning": ("تسمم غذائي", "Food Poisoning",
        {"غثيان", "ألم في البطن", "قشعريرة", "حمى",
         "nausea", "stomach pain", "chills", "fever"}),
    "anxiety": ("أعراض قلق", "Anxiety-related symptoms",
        {"دوار", "ضيق التنفس", "تعب وإرهاق", "ألم في الصدر",
         "dizziness", "shortness of breath", "fatigue", "chest pain"}),
    "vertigo": ("دوار (اضطراب توازن)", "Vertigo",
        {"دوار", "غثيان", "dizziness", "nausea"}),
    "muscle_strain": ("شد عضلي", "Muscle Strain",
        {"ألم المفاصل", "تعب وإرهاق", "joint pain", "fatigue"}),
    "conjunctivitis": ("التهاب ملتحمة العين", "Conjunctivitis",
        {"احمرار العيون", "حمى", "red eyes", "fever"}),
    "asthma_flare": ("نوبة ربو", "Asthma Flare-up",
        {"ضيق التنفس", "سعال", "ألم في الصدر",
         "shortness of breath", "cough", "chest pain"}),
    "dehydration": ("جفاف", "Dehydration",
        {"دوار", "تعب وإرهاق", "غثيان", "dizziness", "fatigue", "nausea"}),
}

# ---- Canonical 12-symptom vocabulary (matches the bot's fixed keyboard) ----
VOCAB = ["headache", "fever", "cough", "chest pain", "nausea", "fatigue",
         "shortness of breath", "dizziness", "joint pain", "stomach pain",
         "chills", "red eyes"]

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

def to_canonical(symptom_set):
    return {SYNONYMS[s] for s in symptom_set if s in SYNONYMS}

# ---- 2. Generate synthetic training data ----
SAMPLES_PER_CLASS = 200
X_rows, y_labels = [], []

condition_ids = list(KNOWLEDGE_BASE.keys())
condition_vocab_idx = {
    cid: [VOCAB.index(s) for s in to_canonical(kws)]
    for cid, (_, _, kws) in KNOWLEDGE_BASE.items()
}

for cid in condition_ids:
    idxs = condition_vocab_idx[cid]
    for _ in range(SAMPLES_PER_CLASS):
        vec = np.zeros(len(VOCAB), dtype=int)
        # simulate a patient reporting a realistic partial subset of the condition's symptoms
        k = random.randint(1, len(idxs))
        chosen = random.sample(idxs, k)
        for i in chosen:
            vec[i] = 1
        # small chance of one unrelated "noise" symptom (real patients aren't textbook-perfect)
        if random.random() < 0.15:
            noise_idx = random.randint(0, len(VOCAB) - 1)
            vec[noise_idx] = 1
        X_rows.append(vec)
        y_labels.append(cid)

X = np.array(X_rows)
y = np.array(y_labels)

# ---- 3. Train / evaluate ----
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

model = BernoulliNB(alpha=1.0)
model.fit(X_train, y_train)

y_pred = model.predict(X_test)
acc = accuracy_score(y_test, y_pred)
print(f"Test accuracy: {acc:.3f}\n")
print(classification_report(y_test, y_pred, zero_division=0))

# ---- 4. Export learned parameters for pure-Python inference ----
feature_log_prob = model.feature_log_prob_          # log P(x_i=1 | y), shape (n_classes, n_features)
feature_log_neg_prob = np.log1p(-np.exp(feature_log_prob))  # log P(x_i=0 | y), numerically stable
class_log_prior = model.class_log_prior_
classes = list(model.classes_)

export = {
    "vocab": VOCAB,
    "classes": classes,
    "class_names": {
        cid: {"ar": KNOWLEDGE_BASE[cid][0], "en": KNOWLEDGE_BASE[cid][1]}
        for cid in classes
    },
    "class_log_prior": class_log_prior.tolist(),
    "feature_log_prob": feature_log_prob.tolist(),
    "feature_log_neg_prob": feature_log_neg_prob.tolist(),
    "meta": {
        "algorithm": "BernoulliNB",
        "test_accuracy": round(acc, 4),
        "n_train_samples": int(len(X_train)),
        "n_test_samples": int(len(X_test)),
        "n_classes": len(classes),
        "n_features": len(VOCAB),
    },
}

with open("ml_model.json", "w", encoding="utf-8") as f:
    json.dump(export, f, ensure_ascii=False, indent=2)

print("\nSaved ml_model.json")
print(f"Classes: {len(classes)} | Features: {len(VOCAB)} | Test accuracy: {acc:.1%}")
