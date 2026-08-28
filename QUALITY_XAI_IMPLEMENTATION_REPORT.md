# SymptoSense — Voice, Doctor Handoff, Data Quality & Explainability

Date: 2026-08-28

## Scope

This build extends the existing SymptoSense codebase without replacing Authentication, Admin RBAC, Medical Knowledge Base, Safety/Red Flags, Privacy/Consent, analysis history, medication reminders, or the existing analysis engine.

Implemented/verified user-facing capabilities in this build:

- Voice Symptom Input (Arabic/English browser speech recognition; raw audio is not uploaded/stored).
- Doctor Handoff with user-selected fields, temporary randomized QR/share links, backend expiration, and backend revoke.
- Low-confidence / "I Don't Know" behavior that withholds medical possibilities when required information or grounded knowledge is insufficient.
- Data Quality Score before analysis, including required/recommended field status and direct "Improve My Information" flow.
- Explainable Assessment showing the real factors used by the displayed assessment.
- Private History pages repaired so stored Data Quality and explanation can be reviewed later by the owning user only.

## Data Quality logic

The score measures information completeness/validity only. It is not a disease probability, model confidence, diagnosis accuracy estimate, or measure of health.

Current weights are derived from the actual analysis flow:

| Field | Type | Weight |
|---|---|---:|
| Recognized main symptom | Required | 30 |
| Symptom duration | Required | 20 |
| Symptom severity | Required | 20 |
| Age | Recommended/context | 10 |
| Gender | Recommended/context | 5 |
| Associated symptoms | Recommended/context | 10 |
| Relevant health history answered | Recommended/context | 5 |

Required sufficiency is checked separately from the numeric score. Therefore a high completeness score cannot override a missing required field.

Levels:

- 90–100: Excellent
- 70–89: Good
- 50–69: Limited
- 0–49: Insufficient

An entered but unrecognized main symptom receives a `needs_clarification` state rather than being treated as fully valid.

## Explainability architecture

A key architectural finding is that the medical possibilities displayed to users are not direct predictions from the bundled ML classifier. The displayed assessment is grounded in:

1. Medical Knowledge Base disease/symptom relationships and their persisted weights.
2. Deterministic Safety / Red Flag rules.
3. Existing clinical-review rules when they are actually triggered.

Accordingly, the user-facing "Why this assessment?" explanation uses those real mechanisms only. It does not invent SHAP values, feature importance, probabilities, or causal claims.

The bundled Bernoulli Naive Bayes model is retained as an auxiliary model. `ml_diagnosis.explain_prediction()` can calculate exact learned log-likelihood margin contributions for symptoms from the persisted model parameters, but the output is explicitly marked `used_for_display = false` because that model is not the source of the displayed medical possibilities.

The UI uses qualitative Higher / Moderate / Lower contribution indicators. The visual meter is categorical (three segments), not a fabricated percentage.

## Low-confidence / safety behavior

- Missing required duration or severity => assessment status `insufficient`; medical possibilities are withheld and only the missing information is requested.
- Unrecognized symptom with no grounded Knowledge Base match => insufficient/low-confidence behavior; no fabricated diagnosis/probability.
- Red Flag detection has priority over Data Quality and Low Confidence. An urgent safety rule is still shown when some routine fields are missing.

## Voice privacy

- The browser performs speech recognition when supported.
- The server receives only the transcript for structured parsing.
- `/api/voice` raw audio upload is intentionally disabled (HTTP 410).
- Unsupported browser / denied microphone permission leaves text input available.
- Arabic and English voice parsing were tested with equivalent abdominal-pain examples.

## Doctor Handoff security

- Only an authenticated owner can create/revoke a handoff from their stored analysis.
- No email or User ID is placed in the public URL.
- Token uses `secrets.token_urlsafe(32)` and only its hash is stored.
- Recipient view is read-only.
- Expiration is verified by the backend (15 min / 1 hour / 24 hours).
- Revoke is verified by the backend and is owner-scoped.
- No share fields are selected by default; the user chooses what to include.
- Public payload contains only selected summary sections.

## Admin analytics

AI Performance now includes anonymized/aggregate Data Quality metrics for analytics-eligible records only:

- Average Data Quality Score
- Percentage with sufficient required information
- Percentage requiring additional information
- Most frequently missing fields

No user email/name/private health record is exposed by these metrics.

## Regression repair

The current source had `/history` and `/history/<record_id>` routes calling missing page functions. This build restores those pages and keeps SQL ownership scoping. A different user cannot load another user's stored analysis.

## Validation performed

- All 23 Python files: `py_compile` passed.
- Main symptom-analysis JavaScript: Node syntax check passed.
- Admin Dashboard JavaScript: Node syntax check passed after rendering Jinja placeholders to test values.
- All 41 `/api/admin...` routes: backend `admin_api_required` guard present.
- Data Quality tests:
  - Complete information: 100 / Excellent / sufficient.
  - Missing age: 90 / sufficient (age is recommended context).
  - Missing duration: 80 / not sufficient.
  - Missing severity: 80 / not sufficient.
  - Unknown symptom: 75 / not sufficient / clarification required.
- Explainability test: factors came from persisted Knowledge Base relationship matching; auxiliary BernoulliNB was not used as the displayed result source.
- Red Flag override: Chest pain + shortness of breath remained Urgent even with missing duration/severity.
- Insufficient case: possible conditions were withheld and missing fields returned.
- History ownership: Owner A could read the record; Owner B could not.
- Voice parser: Arabic and English abdominal-pain sentences extracted symptom, duration, right-side location, and severity 7/10.
- Doctor Handoff: selected-field minimization, random token, invalid owner revoke rejection, valid owner revoke, active/revoked status, and QR generation passed.
- Auxiliary model explanation: exact model-parameter contribution calculation passed and remained explicitly marked as not used for the displayed assessment.

## Environment limitation

This execution environment does not have Flask or Groq installed, so a full HTTP/browser end-to-end run of the Flask application was not possible here. Python/JavaScript static checks and isolated database/business-logic tests passed. A final smoke test after Railway deployment should verify the browser speech-recognition permission flow, real session behavior, and the QR public URL under the production domain.
