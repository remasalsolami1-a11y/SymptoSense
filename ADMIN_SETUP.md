# SymptoSense Admin — existing owner account

This release uses the **existing SymptoSense authentication session**. It does not create a second Admin login and never stores or asks for the owner's password.

## Owner account

The only account eligible for Admin is the existing user whose email is:

`<OWNER_ADMIN_EMAIL>`

Set `SYMPTOSENSE_ADMIN_EMAIL=<OWNER_ADMIN_EMAIL>` in the production environment. The source code does not contain the owner email, and Admin access fails closed if the variable is missing.

## How assignment works

1. Keep the existing production database when deploying this version.
2. Deploy while preserving the existing production database. During schema initialization, the server checks whether that exact existing owner row is present and synchronizes only that row to the canonical lowercase `role = admin`. No account is created if it is missing.
3. Sign in through the normal SymptoSense login using the already-existing owner account.
4. After authentication succeeds, the server reads the authenticated `ss_user_id`, re-verifies the database row and role, and redirects the Admin directly to `/admin`.
5. `/admin` and every `/api/admin/*` endpoint verify the authenticated session and persisted role again on the server.

No `ADMIN_CLAIM_TOKEN` is needed anymore.

## If the owner account does not exist

The code does **not** create a replacement owner/Admin account. Registration using the reserved owner email is refused with `owner_account_must_exist`, and `/admin` remains unavailable until that existing production account is present.

The project ZIP does not contain the Railway production database, so existence of the real production row must be verified after deployment against the preserved Railway database.

## Verification

After signing in with the owner account:

- `/api/user-info` should return `role: "admin"` and `is_admin: true`.
- The Profile menu should show `⚙️ Admin Dashboard`.
- `/admin` should open normally.

For an ordinary user:

- `/api/user-info` should return `role: "user"` and `is_admin: false`.
- Admin navigation is not rendered.
- Direct `/admin` access returns `403`.
- `/api/admin/*` requests return `403` (or `401` when logged out).

## Security behavior

- New ordinary accounts always receive `role = user`.
- Non-owner accounts are always canonicalized to `role = user`; a database index allows only one canonical `admin` row.
- Only the configured owner email can have an effective Admin role.
- Admin write APIs require authenticated Admin role plus a session CSRF token.
- Admin Excel downloads also require the session CSRF token and never include emails, passwords, tokens, secrets, or chat content.
- The Admin idle timeout defaults to 30 minutes and can be adjusted with `ADMIN_SESSION_TIMEOUT_MINUTES` (5–240 minutes).
- Frontend/API role editing is disabled (`403 role_management_disabled`).
- Passwords and authentication secrets are never exposed in Admin code or audit logs.
- Admin analytics remain operational/aggregate and do not expose personal health records by default.


## Temporary Admin authentication diagnostics

This release logs only non-sensitive Admin auth diagnostics: authenticated state, numeric user ID, effective role, owner-match result, Admin authorization result, and redirect target. It never logs passwords, tokens, raw email addresses, medical data, or request bodies.

After the production flow is verified, set:

`ADMIN_AUTH_DEBUG=0`

to disable these temporary diagnostic messages.
