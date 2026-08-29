# SymptoSense Production Stabilization Report

Date: 2026-08-30

## Authentication

- Registration creates an unverified account and sends a verification link through the configured Brevo transport.
- Unverified accounts cannot sign in. Resend is protected by database-backed cooldown and hourly limits.
- Verification and password-reset tokens are random, stored only as hashes, expiring, and single-use.
- Same-browser verification can create a session only when the pending user ID in that browser matches the verified token. A different browser verifies the account but does not receive a session.
- Login success redirects users to `/profile` and the fixed owner Admin to `/admin`, with a one-time in-site toast.
- Login attempts are throttled by a pseudonymous hash of email plus network origin; raw email/IP values are not stored in the throttle table.

## Routes and APIs

- Public route smoke coverage includes Home, About Us, Search, Medications, Chat, calculators, auth pages, content pages, manifest, service worker, and core images.
- Private user pages require a session.
- `/admin` rejects a normal user, and every static GET `/api/admin/*` route rejects a normal user with HTTP 403 from the backend.
- Admin mutation routes additionally require the Admin CSRF header.

## Search and medications

- Search reads the medical knowledge database and returns linked medical sources; Arabic and English terms are covered.
- Medication search reads the medication database; Arabic and English Paracetamol searches are covered.
- Medication reminder create/list/edit/delete is covered with an authenticated, consented user. Guests receive HTTP 401 when saving.

## Database

- Schema initialization remains additive (`CREATE TABLE IF NOT EXISTS` and guarded column additions). No destructive migration or database recreation was introduced.
- PostgreSQL failures no longer silently switch Production to ephemeral SQLite. When `DATABASE_URL` is configured, the application now fails clearly unless the explicitly development-only `ALLOW_SQLITE_FALLBACK=1` is set.
- Required authentication and reminder tables and SQLite foreign-key integrity are included in automated checks.
- Moving to Alembic/Flask-Migrate was intentionally not forced. First baseline the current Production schema, back it up, then adopt migrations incrementally.

## Security

- Password hashing, HttpOnly/SameSite cookies, safe local redirects, form CSRF, Admin API RBAC/CSRF, token hashing/expiry/single use, and login throttling are covered.
- Security response headers include `nosniff`, frame denial, referrer policy, permissions policy, and HSTS when secure cookies are enabled.
- Admin authentication debug logging now defaults off.
- A repository scan found no credential-shaped API keys, private keys, or embedded database credentials.

## Automated test baseline

Run:

```bash
python -m unittest discover -s tests -v
```

Result in the supplied build: **16 tests passed**.

Coverage includes account lifecycle, same/different-browser verification, forgot/reset password, legacy users, Admin redirect/RBAC, email-provider selection and safe diagnostics, public routes, search, medications, reminder CRUD, login throttling, database integrity, JavaScript parsing, translation-key leakage checks, and analysis input validation.

## Remaining Issues

These items are **not claimed as fixed** until the supplied build is deployed:

1. Railway was not deployed or restarted from this workspace, so post-deployment Production smoke tests remain required.
2. Real email delivery was not completed end-to-end here. The last supplied Production evidence showed Brevo HTTP 401 (`email_brevo_auth_failed`). Railway must contain a newly generated valid **Brevo API v3 key**, and `BREVO_FROM_EMAIL` must exactly match the verified Brevo Sender.
3. Delivery to a real inbox, clicking the Production verification/reset URLs, and confirming database changes must be tested after deployment.
4. Production PostgreSQL integrity, indexes, row counts, and restart persistence require authorized read-only database access or Railway console access. No Production data was modified.
5. Mobile/tablet behavior was reviewed through responsive CSS and route rendering, but real-device/browser screenshots of the deployed build remain required.
6. Valid AI symptom-analysis output was not called against the paid/external Production model; input validation and failure containment were tested locally.
7. Sentry was not added because sending health data to a new third party requires an explicit privacy configuration and scrubbing review. Existing operational logging remains content-free.

## Required Railway values before Production verification

- `WEB_SECRET`: one stable random value of at least 32 bytes; never change it casually because doing so invalidates active sessions.
- `DATABASE_URL`: Railway PostgreSQL connection string.
- `SITE_URL=https://symptosense-production-b2e5.up.railway.app`
- `SESSION_COOKIE_SECURE=1`
- `BREVO_API_KEY`: a current Brevo API v3 key (not an SMTP key and not a placeholder).
- `BREVO_FROM_EMAIL=remasalsolami1@gmail.com` only if this exact sender shows **Verified** in Brevo.
- `BREVO_FROM_NAME=SymptoSense`
- `ADMIN_AUTH_DEBUG=0`
- Do not set `ALLOW_SQLITE_FALLBACK=1` in Production.
