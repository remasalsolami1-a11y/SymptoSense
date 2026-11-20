# Daily Tracking — Production Root Cause Fix

## Root cause addressed
`/api/checkin` previously called the full `db.init_db()` migration pass before reading or saving a daily check-in. On an older Railway database, an unrelated legacy migration (especially `daily_checkins`) could fail and block the feature before the new storage code was reached.

## Changes
- `/api/checkin` no longer runs full database migrations.
- Web daily tracking only ensures/uses the minimal existing `user_data` storage it needs.
- PostgreSQL `user_data` discovery follows the active `search_path` rather than relying only on `current_schema()`.
- Legacy `user_data` layouts without `updated_at` remain supported.
- Errors are logged with the request ID and the UI shows the request ID if a production failure remains.
- No medical-analysis logic was changed.

## Regression coverage
Targeted daily-tracking tests: 11 passed.
Combined daily-tracking + compound-health-search tests: 15 passed.
Includes a regression case where `daily_checkins` is deliberately incompatible; web tracking still saves and loads successfully.
