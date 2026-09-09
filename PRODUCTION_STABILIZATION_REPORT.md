# SymptoSense Production Stabilization Report

Date: 2026-08-30

## 1. Executive Summary

**Current readiness: NOT READY**

The supplied build is substantially safer and passes **25 automated tests**, but the release gate is not complete. Real Brevo inbox delivery, Railway deployment/restart, Production PostgreSQL integrity, restore testing, and real-browser/mobile tests have not been verified. The latest supplied Production evidence showed Brevo HTTP 401 (`email_brevo_auth_failed`).

No feature was added and no Production data was deleted or migrated.

## 2. Authentication

### Problems found and root causes

- Email delivery failed because the supplied Production evidence showed an invalid/non-v3 Brevo key.
- Verification needed proof of continuity with the registration browser before auto-login.
- HTML and JSON login paths did not share a database-backed throttle.
- PostgreSQL errors could silently activate ephemeral SQLite.

### Fixes and tests

- Same-browser auto-login requires the pending session user ID to match the consumed verification token. Other browsers verify only.
- Verification/reset tokens are random, hashed, expiring, and single-use; resend/reset issuance has cooldown and hourly limits.
- HTML and API login use a pseudonymous email/network throttle; raw email/IP are not stored in the throttle table.
- New users remain `role=user`; the owner account is not created and no Admin password is stored in code.
- Tested register, unverified block, same/different-browser verify, duplicate/missing account, wrong password, reset expiry/single use, old-password rejection, logout, and legacy-account compatibility.

Remaining: ⚠️ real inbox delivery and post-Railway-restart sessions are not verified.

## 3. Admin Security

- The authoritative owner remains `the email configured in `SYMPTOSENSE_ADMIN_EMAIL``.
- Normal users receive HTTP 403 from `/admin` and from static GET `/api/admin/*` routes at the backend.
- Admin mutations require session, server-side scope authorization, and CSRF.
- Self-role escalation is disabled; Admin debug logging defaults off.

⚠️ The Production PostgreSQL owner row was not inspected from this environment.

## 4. Routes

Flask discovery found **171 routes**: 53 GET page/static routes and 118 API routes, including 47 Admin APIs. Automated testing exercises every static GET rule without path parameters and rejects unexpected 500/502/503 responses.

| Route | Before | Problem | Fix | After |
|---|---|---|---|---|
| `/search` | Reported broken | renderer/API and error leakage risk | KB-backed search and sanitized errors | Local AR/EN/no-result/failure tests pass |
| `/meds` | Reported broken | DB/reminder integration | DB-backed search and authenticated CRUD | Local AR/EN/CRUD tests pass |
| `/about-us` | redirect/broken image history | route/assets | independent page and safe assets | Local route/asset test passes |
| `/profile` | private | auth required | verified-session guard | Guest redirects; user passes |
| `/history/<id>` | ownership needed proof | IDOR risk | owner-scoped retrieval/deletion | Cross-user test returns 404 |
| `/admin` | privileged | frontend hiding insufficient | backend enforcement | User 403; Admin test 200 |
| unknown route | inconsistent | no branded error | bilingual 404 | 404 test passes |

Parameterized routes were tested selectively according to ownership/security risk, not for every possible ID.

## 5. Buttons & Forms

Integration behavior covers Login, Register, Verify, Resend cooldown, Forgot/Reset Password, Logout, Search, medication Save/Edit/Delete, Admin routing, history view/delete, and privacy withdrawal/deletion. Core inline JavaScript passes `node --check`.

⚠️ Literal browser clicking of every UI control was not possible. Voice, notification permission, file picker, Excel/PDF download, and modal-focus flows remain manual checks.

## 6. Search

- `صداع` and `headache` return KB-grounded information and sources.
- Empty search returns suggestions; unknown search returns no result, not mock content.
- Forced backend failure returns HTTP 500 with a generic message and matching `X-Request-ID`; exception text is hidden.

## 7. Medications

- Arabic/English Paracetamol lookup reads the medication database.
- Unknown medicines return unavailable/no-result.
- Reminder CRUD is authenticated and consent-gated.
- Cross-user update is 403; cross-user delete is 404.
- Taken/skip/snooze ownership exists; duplicate Push delivery claim is rejected.

⚠️ Real Push delivery, timezone scheduling, worker restart, and duplicate-worker behavior require Railway testing.

## 8. Database

- Fixed the unsafe silent PostgreSQL-to-SQLite fallback. Production now fails clearly when `DATABASE_URL` is unavailable; `ALLOW_SQLITE_FALLBACK=1` is development-only.
- Initialization remains additive. No destructive migration, reset, DROP, or forced Alembic conversion was performed.
- Required auth/reminder tables exist in the test copy; SQLite foreign-key integrity passes.
- Added a compound login-throttle index `(key_hash, attempted_at)`.

Migration strategy: backup → schema snapshot → staging restore → additive migration → integrity check → deploy → rollback verification.

Backup/restore: ⚠️ Railway backup location, schedule, retention, and restore were not accessible. A restore into an isolated database is required before release.

## 9. Security

- Reviewed password hashing, cookies, local redirects, CSRF, RBAC, token security, rate limits, IDOR, and export scoping.
- Added `nosniff`, frame denial, referrer policy, permissions policy, request ID, and HSTS with secure cookies.
- Credential-pattern scan found no embedded API keys, private keys, or database credentials.
- Critical Search/Medications/Authentication/Analysis errors are sanitized and log request ID plus exception type only.

Known limitation: some legacy non-critical handlers still catch exceptions individually; migrate them only after route-specific tests exist.

## 10. Email

- Provider: Brevo HTTPS API when configured; SMTP remains a compatibility fallback.
- Verification/reset construction and token behavior pass with captured test transport.
- Verification and password-reset messages use bilingual, responsive, table-based HTML with the requested subjects, RTL/LTR direction, action buttons, and complete fallback URLs. Authentication flow, token handling, expiry, database, and transport were not changed.
- Automated template checks cover both languages, Production-origin links, no JavaScript, and absence of named sensitive fields.
- **Delivery: NOT VERIFIED.** The latest Production evidence was Brevo 401; API 200 alone would not prove inbox delivery.

Required: valid Brevo API v3 key, exact Verified sender, `BREVO_FROM_NAME=SymptoSense`, and correct `SITE_URL`.

## 11. Mobile

Responsive CSS and core rendering were reviewed without introducing fixed desktop widths.

⚠️ 375, 390, 768, and 1024 px screenshots and touch interactions were not executed against the deployed build.

## 12. Accessibility

- Auth fields use labels/autocomplete; toast uses `role=status` and `aria-live`.
- Navigation has labels/focus behavior, Escape close, and reduced-motion support.

⚠️ Full tab order, modal focus trapping, axe/WCAG contrast, and screen-reader tests remain.

## 13. Performance

- No speculative upgrades or big refactor was performed.
- `pip check` reports no broken installed requirements.
- No new heavy frontend dependency was added.

⚠️ Lighthouse, Web Vitals, Railway percentiles, query plans, and load tests were unavailable. Performance is not certified.

## 14. Medical Safety

- Deterministic Knowledge Base and safety rules execute before AI.
- Red flags override AI confidence, withhold possible conditions, and produce urgent guidance.
- Insufficient/low-confidence input suppresses condition output.
- Medication reminders do not recommend medication or dosage.
- Sources and non-diagnostic disclaimers remain.
- Severe chest pain plus breathing difficulty automated test confirms urgent override.

## 15. Railway Production

- **Production tested: NO** for this build.
- **Restart tested: NO**.
- Direct inspection was blocked and no Railway deployment authority was available.

Required gate: identify stable deployment → confirm backup → deploy → inspect logs → smoke/email/login → restart → repeat DB/Search/Meds/Admin/email → rollback on critical failure.

## 16. Automated Tests

- **Passed: 23**
- **Failed: 0**
- Core Python compilation: passed.
- Installed dependency consistency: passed.

Coverage: auth lifecycle, verification contexts, reset, legacy users, Admin authorization, all static GET routes, Search, medication CRUD, analysis/reminder IDOR, red flags, consent withdrawal, health-data deletion, double actions, Push idempotency, DB integrity, JS parsing, translation keys, security headers/404, and validation.

## 17. Remaining Issues

### Critical

1. Brevo delivery not verified; latest Production evidence was 401.
2. Build not deployed/restarted on Railway.
3. Production PostgreSQL backup/restore/integrity not verified.

### High

1. Browser/mobile matrix not executed.
2. Push worker restart/multiple-worker behavior not verified.
3. External AI timing/failure behavior not tested in Production.

### Medium

1. Full dynamic-route/button click audit needs browser QA.
2. Remaining legacy exception handlers need tests before cleanup.
3. Load and query-plan tests are pending.

### Low

1. Full WCAG/axe and screen-reader checks are pending.
2. Advisory vulnerability scanning needs an updated vulnerability database; only dependency consistency was checked.

## 18. Release Recommendation

**NOT READY — FIX THESE FIRST**

1. Validate Brevo v3 credentials and prove Gmail/Outlook delivery.
2. Confirm and restore-test a PostgreSQL backup.
3. Deploy this exact build and run the full Production smoke suite.
4. Restart Railway and re-test sessions, persistence, Search, Medications, Admin, and email.
5. Complete desktop/mobile browser smoke testing.

Current honest status: **Stabilized locally; Production release not verified.**
