# SymptoSense Auxiliary Classifier — Model Card

## Purpose

SymptoSense includes an auxiliary symptom classifier that ranks possible condition labels from a small set of recognized symptoms. It is an educational support component, not a diagnostic system. The user-facing assessment remains governed by the medical knowledge base and rule-based safety checks.

## Model

- Algorithm: Bernoulli Naive Bayes (`BernoulliNB`)
- Runtime: pure-Python inference from parameters stored in `ml_model.json`
- Training: offline through `train_model.py`
- Features: 15 binary symptom indicators
- Classes: 18 condition labels

## Inputs and outputs

The input is a list of supported Arabic or English symptom terms. Terms are normalized to the model vocabulary and converted to a binary vector. The output is a ranked list of condition labels and normalized model probabilities. These probabilities are model scores and must not be presented as a diagnosis or a person's probability of having a disease.

## Training and evaluation information

`train_model.py` generates a synthetic dataset from its curated condition-to-symptom mapping. Each class receives 200 generated samples with partial symptom reporting and limited random noise. The fixed split and random seed recorded in the script produce:

| Item | Value |
|---|---:|
| Training samples | 2,880 |
| Test samples | 720 |
| Classes | 18 |
| Features | 15 |
| Test accuracy | 65.28% |

These values are read from the exported `ml_model.json` metadata. No precision, recall, F1, external validation, or clinical performance claim is made here.

## Limitations

- Training data is synthetic and derived from a small curated mapping.
- The vocabulary and condition set are limited.
- Symptoms shared by several conditions can be difficult to distinguish.
- Missing context such as examination findings, laboratory results, medical history, and symptom progression limits the model.
- The reported test accuracy is internal performance on synthetic held-out data and does not represent clinical accuracy or real-world validation.
- The model must not be used for emergency triage, definitive diagnosis, treatment selection, or personalized dosage.

## Medical safety

Rule-based red-flag checks and the Medical Knowledge Base take priority over the auxiliary model. When information is insufficient or urgent warning signs are present, the product should show the appropriate safety guidance rather than force a condition prediction. SymptoSense does not replace a physician or qualified healthcare professional.

## Product architecture context

The deployed product is a **hybrid decision-support prototype**, not an LLM diagnostic system. Deterministic red-flag rules are evaluated independently of the language model; curated knowledge and explainable matching support the result; an optional AI provider improves natural-language interaction. If the provider is unavailable, local conservative fallbacks remain available for common health questions. Public usage/feedback metrics are a usability **pilot**, not clinical validation.

Independent clinician review and real-world clinical validation are required before any clinical-use claim.

## Reproducibility

The training procedure, seed, curated mappings, split, evaluation call, and export logic are available in `train_model.py`. The deployed parameters and evaluation metadata are stored in `ml_model.json`.
