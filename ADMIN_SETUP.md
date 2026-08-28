# SymptoSense Admin — existing owner account

This release uses the **existing SymptoSense authentication session**. It does not create a second Admin login and never stores or asks for the owner's password.

## Owner account

The only account eligible for Admin is the existing user whose email is:

`remasalsolami2020@gmail.com`

The email can be overridden at deployment with `SYMPTOSENSE_ADMIN_EMAIL`, but the default is already set for this project.

## How assignment works

1. Keep the existing production database when deploying this version.
2. Sign in through the normal SymptoSense login using the already-existing owner account.
3. After authentication succeeds, the server reads the current `ss_user_id` from the session and verifies that the database row for that ID belongs to the configured owner email.
4. Only that existing row is updated to `role = admin` when needed.
5. Open `/admin`. Access is checked again server-side from the current authenticated session and database role.

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
- No bulk role reset is performed and no other user's database row is modified during owner promotion.
- Only the configured owner email can have an effective Admin role.
- Admin write APIs require authenticated Admin role plus a session CSRF token.
- Frontend/API role editing is disabled (`403 role_management_disabled`).
- Passwords and authentication secrets are never exposed in Admin code or audit logs.
- Admin analytics remain operational/aggregate and do not expose personal health records by default.
