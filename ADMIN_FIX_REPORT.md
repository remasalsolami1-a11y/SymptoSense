# SymptoSense Admin Fix Report

Date: 2026-08-28

## Root cause

The Admin authorization layer itself was already server-side, but the login flow and owner configuration were inconsistent:

1. The JSON login endpoint always returned `redirect_url: /profile`, even when the authenticated user had `role = admin`.
2. The normal HTML login followed the regular `next` target instead of redirecting an authenticated Admin directly to `/admin`.
3. A legacy Railway environment variable, `SYMPTOSENSE_ADMIN_EMAIL`, could override the intended owner account. If that value was stale or different, `remasalsolami2020@gmail.com` would be treated as a normal user even after successful authentication.
4. Legacy role casing such as `Admin` or `ADMIN` was not canonicalized in all effective-role reads.

## Fixes applied

- Fixed the only Admin owner account to `remasalsolami2020@gmail.com` in the backend authorization configuration.
- A conflicting legacy `SYMPTOSENSE_ADMIN_EMAIL` value is ignored.
- Existing owner account only: schema/startup synchronization looks up the existing `ss_users` row and changes only its persisted role to lowercase `admin` when required.
- No owner account is created if the row is missing.
- No password or credential is changed or stored.
- Legacy Admin-like roles on every non-owner account are canonicalized to `user`; a partial unique database index prevents more than one canonical `admin` row.
- Non-owner users have an effective role of `user` for Admin authorization even if a legacy database row incorrectly contains an Admin-like role.
- New accounts remain `role = user`.
- HTML login redirects an authenticated Admin to `/admin`.
- API login returns `redirect_url: /admin` and `is_admin: true` for the owner; normal users still return `/profile`.
- `/admin` keeps server-side session + database role protection and returns HTTP 403 for authenticated non-Admin users.
- All `/api/admin/*` routes remain protected by `admin_api_required`.
- Admin sessions now have a configurable idle timeout (`ADMIN_SESSION_TIMEOUT_MINUTES`, default 30 minutes), and write APIs require the session CSRF token.
- Admin password changes verify the current password, rotate the signed session, and write a credential-free audit event.
- Added real database-backed Overview, Users, Symptom, Medication, heatmap, AI performance, Explainable AI, Automatic Insights, Anomalies, Ask Your Data, System Health, profile/security, and audit views.
- The main Excel export now has exactly five sheets: Users, Symptom Analyses, Medications, Medication Analytics, and Symptom Analytics. It uses pseudonymous IDs, consent-eligible health data, privacy thresholds for aggregate rows, and spreadsheet formula-injection protection.
- The persisted BernoulliNB test accuracy and model fingerprint are shown as stored; unavailable Precision, Recall, and F1 values stay unavailable. Explainable AI is calculated from the real learned log-probability coefficients and is explicitly marked as auxiliary.
- Added temporary non-sensitive Admin authentication logs. They include only: authenticated state, numeric user id, effective role, owner-match, access granted/denied, and redirect. They do not include passwords, tokens, raw email addresses, request bodies, or medical data.

## Local tests completed

- Existing owner row with legacy role `Admin` -> canonical `role = admin`: PASS.
- Conflicting `SYMPTOSENSE_ADMIN_EMAIL=wrong@example.com` -> ignored: PASS.
- Existing owner authenticates with normalized email casing: PASS.
- Normal and stale non-owner Admin users persist as `role = user`: PASS.
- New user defaults to `role = user`: PASS.
- Attempt to assign Admin to a non-owner through the internal role setter: rejected: PASS.
- Owner-missing initialization does not create an account: PASS.
- 45 `/api/admin/*` routes checked; unprotected routes: 0.
- Logged-out requests to all 45 Admin APIs return 401; authenticated normal users return 403: PASS.
- Admin dashboard rendering in Arabic RTL and English LTR, required responsive breakpoints, and duplicate DOM IDs: PASS.
- Five-sheet Excel generation, safe headers, pseudonymous IDs, CSRF enforcement, Knowledge Base CRUD, Ask Your Data, model metrics/XAI, password rotation, and idle timeout: PASS.
- Python syntax compilation for project `.py` files: PASS.
- Login source checks confirm Admin -> `/admin`, normal user -> `/profile`.
- `/admin` source protection confirms authenticated non-Admin -> HTTP 403.

## Production verification

The Railway production database is not included in the project ZIP, so this environment cannot verify whether the real production row currently exists or perform a real login with the owner's password.

After deployment, sign in normally with the existing account and verify:

1. `/api/user-info` returns `role: "admin"` and `is_admin: true`.
2. Login redirects to `/admin`.
3. The navigation shows `Admin Dashboard`.
4. `/admin` loads.
5. An ordinary user receives HTTP 403 for `/admin` and `/api/admin/*`.

If the production owner row does not exist, startup logs will say that the Admin owner account was not found and no replacement account will be created.

Temporary debugging is enabled by default for this release. After verification set:

`ADMIN_AUTH_DEBUG=0`
