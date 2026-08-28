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
- No other user's database role is modified by the repair.
- Non-owner users have an effective role of `user` for Admin authorization even if a legacy database row incorrectly contains an Admin-like role.
- New accounts remain `role = user`.
- HTML login redirects an authenticated Admin to `/admin`.
- API login returns `redirect_url: /admin` and `is_admin: true` for the owner; normal users still return `/profile`.
- `/admin` keeps server-side session + database role protection and returns HTTP 403 for authenticated non-Admin users.
- All `/api/admin/*` routes remain protected by `admin_api_required`.
- Added temporary non-sensitive Admin authentication logs. They include only: authenticated state, numeric user id, effective role, owner-match, access granted/denied, and redirect. They do not include passwords, tokens, raw email addresses, request bodies, or medical data.

## Local tests completed

- Existing owner row with legacy role `Admin` -> canonical `role = admin`: PASS.
- Conflicting `SYMPTOSENSE_ADMIN_EMAIL=wrong@example.com` -> ignored: PASS.
- Existing owner authenticates with normalized email casing: PASS.
- Normal user remains effective `role = user`: PASS.
- New user defaults to `role = user`: PASS.
- Attempt to assign Admin to a non-owner through the internal role setter: rejected: PASS.
- Owner-missing initialization does not create an account: PASS.
- 41 `/api/admin/*` routes checked; unprotected routes: 0.
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
