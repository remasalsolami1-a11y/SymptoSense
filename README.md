# SymptoSense

SymptoSense is a bilingual Arabic/English educational health web application that helps users understand symptoms and common laboratory results, identify warning signs, and reach trusted medical information. It is designed for awareness and initial guidance only and does **not** provide a medical diagnosis or replace a clinician or emergency service.

## Main capabilities

- Symptom analysis with adaptive follow-up questions and safety triage.
- Emergency red-flag handling and Saudi emergency/health contact guidance.
- Blood/laboratory result extraction from images or PDFs, user confirmation of extracted values, laboratory-range-first interpretation, context notes, clinician questions, and clinic summaries.
- Medical search, health library, medication information and reminders.
- First-aid information, health calculators, mental-wellbeing support, health history, and family profiles.
- Arabic and English interfaces with RTL/LTR support.

## Safety principles

- Outputs are educational and non-diagnostic.
- The laboratory reference range printed on the user's own report is prioritized when available.
- A single abnormal laboratory value is not treated as a diagnosis.
- Emergency escalation is reserved for explicit red flags or urgent safety conditions rather than severity alone.
- Sensitive flows include consent, account protection, and privacy controls.

## Runtime

The production web application is served by Flask and deployed through Railway using `railway_entrypoint.py` and the included `Dockerfile`.

```bash
python -m pip install -r requirements.txt
python railway_entrypoint.py
```

For local direct development, `python webapp.py` is also available.

## Important environment variables

Configure secrets in the deployment platform, never in source control. Common variables include:

- `WEB_SECRET`
- `DATABASE_URL`
- `GROQ_API_KEY`
- `BREVO_API_KEY`, `BREVO_FROM_EMAIL`, `BREVO_FROM_NAME`
- `SITE_URL`
- Telegram variables when Telegram reminders are enabled
- VAPID variables only for features that still use Web Push

See `.env.example` and the project setup documents for the full list. Do not commit real secret values.

## Quality checks

Useful dependency-light checks included in the repository:

```bash
python release_check.py
python tools/check_translations.py
python tools/full_interaction_audit.py
node tools/test_interaction_bridge.js
node tools/test_symptom_microphone.js
```

The complete test suite requires the development/runtime dependencies listed by the project.

## Privacy and medical disclaimer

SymptoSense is an educational/research-oriented project, not an approved medical device and not a substitute for professional medical evaluation. Do not use it to start, stop, or change prescribed treatment without a qualified clinician or pharmacist.
