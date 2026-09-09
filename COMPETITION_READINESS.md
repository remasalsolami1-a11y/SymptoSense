# SymptoSense — Competition Readiness Notes

Updated: 9 September 2026

## What this build fixes

- Public/PWA assets are no longer trapped behind the first-language redirect.
- Railway health checks use `/health` rather than the language-gated home page.
- Service Worker installation tolerates one missing optional asset instead of failing the entire install.
- Manifest language/direction follow the selected Arabic/English language.
- The assistant uses a bounded provider retry and a curated local fallback when the AI provider is unavailable.
- Fainting/presyncope phrases normalize to stable symptom concepts instead of creating an unrecognized new symptom phrase.
- Symptom-flow progress cannot move backwards; the current question is primary and previous answers are available in a collapsed summary.
- Report download keeps the Blob URL alive longer for mobile Safari and uses a simple ASCII filename.
- Public user metrics are explicitly labeled as a limited usability Pilot; individual public comments are hidden by default in the competition build.
- CSP is enforced, sensitive signed-in mutation APIs receive browser-session CSRF protection, and the owner Admin email is configuration-only.
- Privacy disclosure now covers retention/deletion, providers, international processing, minors, contact, and policy version.
- Methodology explicitly describes the hybrid architecture, evaluation scope, and current clinical limitations.
- Read-aloud and microphone controls are grouped inside a single Accessibility menu to keep the symptom interface calm.
- Legacy static tests were aligned with the current competition UI/PWA behavior; the dependency-light gate passes 86 tests in this review environment.
- Historical fix reports are archived under `docs/reports/` instead of cluttering the project root.

## Required Railway settings before the demo

Set at least:

- `DATABASE_URL`
- `WEB_SECRET`
- `SITE_URL`
- `SESSION_COOKIE_SECURE=1`
- `SYMPTOSENSE_ADMIN_EMAIL`

For the full AI assistant, also set `GROQ_API_KEY`. The project remains usable with a conservative local health fallback if the provider is unavailable.

If medication reminders must continue independently of the web process, create a separate Railway worker service with `python push_worker.py`.

## Live checks before judging

Open these exact URLs on the production domain and confirm HTTP 200:

- `/health`
- `/healthz`
- `/manifest.webmanifest`
- `/brand-icon.svg`
- `/icons/icon-192.png`
- `/icons/icon-512.png`
- `/static/images/symptosense-social-preview.png`

Then test:

1. Arabic and English first-language flow.
2. Fainting analysis and one ordinary non-urgent symptom.
3. Assistant question: `ركبتي تطقطق بدون ألم` with the AI provider both available and unavailable.
4. PDF report download in Safari iPhone, Chrome Android, and desktop Chrome/Edge.
5. Login + one saved analysis + deletion action.
6. PWA install banner / service-worker registration.

## Scientific claim boundary

This build is an educational hybrid decision-support prototype. It is not a diagnostic device, not clinically validated, and public pilot metrics are not evidence of medical accuracy. Emergency red-flag logic is deterministic and does not rely on the LLM alone. Independent clinician review and real-world validation are required before any clinical-use claim.
