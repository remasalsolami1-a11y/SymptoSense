# Database Initialization Cache Safety Fix

## Scope
This update fixes the initialization-cache edge case found after the symptom-analysis speed optimization. It does not remove the speed optimization and does not change medical analysis logic, APIs, stored user data, or authentication flows.

## What changed
- Replaced the process-wide `_DB_READY` boolean with `_DB_READY_KEY`, keyed to the active database identity.
- SQLite readiness uses canonical path plus device/inode when available, so a different or replaced database does not inherit another database's ready state.
- PostgreSQL readiness uses a SHA-256 digest of `DATABASE_URL`; the DSN itself is not logged or placed in the cache key.
- Added a process lock so concurrent request threads cannot race through schema migration.
- Security-critical email-verification/RBAC migration errors now propagate instead of being swallowed.
- Added `_verify_critical_account_schema()` before readiness is cached. It verifies `role`, `status`, `email_verified`, `email_verified_at`, and the `email_otp_all_accounts_v1` migration marker.
- If initialization/migration raises, `_DB_READY_KEY` is left unchanged, so the same database is retried on the next call.
- Optional health-profile column migration remains best-effort, preserving prior compatibility behavior.

## Regression coverage
- Existing legacy database test covers: warm cache on one DB -> switch to an older DB in the same process -> automatic account-schema migration.
- Added `test_failed_critical_migration_is_not_cached_and_retries` to cover: first critical migration fails -> database is not marked ready -> second call retries and completes.
- Direct targeted checks also verified same-database cache hits remain no-ops and a copy of the bundled SQLite DB initializes without deleting users.

## Full pytest note
The repository now contains 42 test functions (41 original + 1 new regression test). Full pytest collection could not be executed in the editing container because `flask` and `groq` are not installed, and the container cannot reach PyPI to install them. This limitation is environment-related, not a test failure. The database-specific regression checks and Python syntax compilation passed.
