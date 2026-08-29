# SymptoSense — Search, Medications, About & Authentication

## Root causes fixed

- `/search` used only the bundled glossary and could expose the untranslated `title_search` key.
- `/meds` depended on `FAM_CSS` declared later in the module and medication lookup used only an in-memory dictionary.
- Network/API failures had no actionable retry state.
- About Us repeated the same ideas and depended on an image without a safe fallback.
- Production verification email returns `401 email_brevo_auth_failed` when `BREVO_API_KEY` is not a valid Brevo v3 API key.

## Implemented

- Search now prefers active Medical Knowledge Base symptom records and returns only their linked active sources.
- Medication records seed once into `medical_medications`; runtime lookup reads the database.
- Medication search remains public; reminder create/update/delete APIs remain authenticated and consent-gated.
- Added loading, no-result, error, and retry states in Arabic and English.
- Rebuilt About Us around Remas Hameed Alsolami, with a safe personal-photo placeholder and project-image fallback.
- Kept Admin role behavior and authentication routes unchanged.

## Production variables

Required database/runtime variables remain `DATABASE_URL`, `WEB_SECRET`, `SITE_URL`, and `SESSION_COOKIE_SECURE=1`.

For Brevo email, use:

- `BREVO_API_KEY`: a newly generated **Brevo API v3 key** (not an SMTP key).
- `BREVO_FROM_EMAIL`: `remasalsolami1@gmail.com` (must be a verified Brevo sender).
- `BREVO_FROM_NAME`: `SymptoSense`.

Remove obsolete `SMTP_*`, `RESEND_API_KEY`, and `RESEND_FROM` variables when Brevo is the selected transport. Never commit or share the key.

## Verification completed locally

- `/search`, `/meds`, `/about-us`, both icon assets: HTTP 200 after language selection.
- Arabic and English `headache/صداع`: real KB result with linked sources.
- Unknown search: explicit no-result.
- English and Arabic `Paracetamol/باراسيتامول`: database-backed medication result.
- Guest reminder write: HTTP 401.
- Authenticated reminder create/list/edit/delete: successful against SQLite database.
- Authentication integration suite: 7 tests passed.

Production must be redeployed with this package, then verified against Railway. Email delivery cannot pass until Brevo accepts the configured API key.
