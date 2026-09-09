# SymptoSense — Admin + Safety + Results + Design Fix Report

## 1) Admin issue found

The existing Authentication flow itself was valid. The main failure came from the previous Admin assignment flow:

- Admin depended on a separate `ADMIN_CLAIM_TOKEN` flow after normal login.
- An older RBAC migration could reset roles before the owner claim completed.
- The critical `role` schema migration lived inside a broad `except: pass`, so a schema failure could be hidden.
- Frontend role state could therefore remain `user` even after the correct owner signed in.

### Fix

- Keep the existing login/session (`ss_user_id`).
- The already-authenticated existing owner row is the only row eligible for promotion.
- Owner email: `the email configured in `SYMPTOSENSE_ADMIN_EMAIL`` (fixed; conflicting legacy `SYMPTOSENSE_ADMIN_EMAIL` values are ignored).
- No Admin account is created if that row is missing.
- New ordinary accounts default to `role=user`.
- `/admin` and all `/api/admin/*` permissions are checked server-side.
- Role editing through the Admin UI/API remains disabled.
- `/api/user-info` exposes `role` and `is_admin` so the UI can reflect the server state.
- Admin navigation is rendered only for the authenticated Admin.
- No bulk update of other users is performed.

## 2) Safety / Red Flags

The project already contained a safety layer, so it was extended rather than duplicated.

`mk_red_flags` now supports:

- Arabic / English name
- Arabic / English description
- Related/required symptoms
- Severity / minimum severity
- Risk level
- Arabic / English recommended action
- Verified source
- Official reference URL
- Active / Disabled status
- Last updated

Safety runs before disease matching. Urgent red flags suppress possible-condition matching and AI diagnosis-style output.

Verified rule examples include:

- Chest pain + shortness of breath → urgent warning (NHS)
- Sudden one-sided weakness + speech difficulty → urgent warning (CDC)
- Severe breathing difficulty → urgent warning (NHS)
- Sudden stroke warning signs → urgent warning (CDC)
- Immediate self-harm danger → urgent support guidance (WHO)

Normalization was also extended so phrases such as `sudden weakness` and `speech difficulty` map to the canonical stroke-warning symptoms.

## 3) Analysis results UI

The current result flow was reorganized without removing follow-up, speech, feedback, sharing, transparency, or history features.

The result now emphasizes:

1. Risk level
2. Entered symptoms
3. Urgent health alert when needed
4. Possible conditions using Strong / Moderate / Weak match labels (no diagnosis percentage)
5. "Why did this appear?" matched-symptom explanation per condition
6. Safe next steps
7. Detected red flags, or an explicit green "no red flags identified" state
8. Related verified medical sources
9. Medical-awareness disclaimer

## 4) Unified design system

The global V2 CSS now standardizes cards, buttons, forms, result cards, status states, Profile surfaces, footer, spacing, shadows, radius, mobile behavior, and reduced-motion support. The main desktop navigation now includes Profile for signed-in users while Admin remains visible only to Admin.

## 5) Tests completed locally

Using disposable SQLite databases (never the production database):

- Existing owner-like account: login succeeds → owner promotion succeeds → effective role `admin`.
- Ordinary user: login succeeds → effective role remains `user`.
- Attempt to assign Admin to ordinary user: rejected.
- New ordinary account: defaults to `user`.
- Old schema without `role/status`: migration adds both and preserves the existing user.
- 27 Admin API routes detected: all 27 have server-side `admin_api_required` protection.
- Chest pain + shortness of breath: urgent, no disease matches, NHS sources retained.
- Sudden weakness + speech difficulty: urgent, no disease matches, CDC source retained.
- Headache + nausea + light sensitivity: non-urgent, Migraine appears as a strong explainable match.
- Red Flag CRUD: Active accepted; invalid Draft status rejected.
- All Python files compile successfully.
- The generated symptom-results JavaScript and Admin Dashboard JavaScript pass `node --check` after rendering/extraction.

## Production limitation

The uploaded project ZIP does not contain the Railway production database or the live browser session. Therefore this workspace cannot truthfully verify that `the email configured in `SYMPTOSENSE_ADMIN_EMAIL`` exists in the live Railway database or perform a real login with that account.

The deployed code is intentionally fail-safe: if the existing owner row is missing, it does not create a replacement account and Admin access remains forbidden.

After deployment with the existing Railway database preserved, sign in normally and check `/api/user-info`. The expected owner response is `role: "admin"` and `is_admin: true`; an ordinary user's expected response is `role: "user"` and `is_admin: false`.
