# SymptoSense Admin — one-time owner setup

This version uses the existing SymptoSense authentication session. It does **not** create a second Admin login and it does not store an email address or password in source code.

## First deployment only

1. Deploy this version while preserving the existing production database.
2. In Railway Variables, add `ADMIN_CLAIM_TOKEN` with a long private value (at least 24 characters). Do not put this value in the repository.
3. Sign in to SymptoSense using the **existing account that must become Admin**.
4. Open `/admin`. If no Admin has been assigned yet, the server redirects that authenticated account to `/admin/claim`.
5. Enter the private `ADMIN_CLAIM_TOKEN` once. The server promotes the current authenticated `ss_user_id` to `role = admin`.
6. Confirm `/admin` opens and the Admin navigation is visible.
7. Remove `ADMIN_CLAIM_TOKEN` from Railway after the claim succeeds. The database role remains `admin`.

## Security behavior

- New accounts always receive `role = user`.
- The first V3 RBAC migration resets existing roles to `user` once, without deleting users or other data.
- A database unique partial index allows at most one Admin account, regardless of account status.
- The owner claim can only succeed when there is no Admin account yet.
- `/admin` is checked server-side against the current authenticated session and database role.
- Admin write APIs require authenticated Admin role plus a session CSRF token.
- Role changes from the dashboard/API are disabled (`403`).
- Admin user listings expose only User ID, status, role, registration date, and last login.
- No password, login secret, health profile, chat text, or personal medical result is exposed in Admin analytics.
