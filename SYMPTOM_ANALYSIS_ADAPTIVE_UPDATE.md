# SymptoSense — Adaptive Symptom Analysis Update

## What changed
- Added adaptive differential follow-up questions before the final analysis.
- Questions are selected from the active medical knowledge base to distinguish between the leading condition matches.
- Positive answers add supporting symptoms; negative answers reduce the relevance of conditions that normally include those symptoms.
- The differential questionnaire stops when one condition has a clearer lead or after a short safety cap to avoid an endless questionnaire.
- Emergency/red-flag handling remains separate and unchanged.
- The result screen was simplified so the closest condition is prominent, followed by urgency, a short reason, next step, important red flags, and collapsible trusted sources.
- Results continue to be worded as a closest match / possibility, not a confirmed diagnosis.

## Validation performed
- Python syntax compilation passed for `webapp.py` and `medical_knowledge.py`.
- Adaptive question logic was exercised against headache/migraine and numbness differentials using the bundled medical knowledge base.
- Full pytest collection could not run in this container because Flask and Groq are not installed in the execution environment.
