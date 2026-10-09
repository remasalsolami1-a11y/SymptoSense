# Daily Tracking — Existing DB Store Fix

The website daily-tracking API no longer depends on `daily_checkins` or `ss_daily_checkins`.

## Production fix
- Uses the long-standing `user_data` table already present in the core database.
- Each web account gets a reserved negative `user_data.user_id` namespace.
- The row stores a compact JSON map of `YYYY-MM-DD -> rating`.
- One rating per account/day; saving again updates the same day.
- PostgreSQL save path locks the reserved row (`FOR UPDATE`) to avoid two-tab lost updates.
- `/api/checkin` calls cached `db.init_db()` before access so the core table is guaranteed.
- Account deletion removes the reserved daily-tracking row.
- No new daily-tracking DDL or migration is required for the web feature.

## Verification
- Python compilation passed for `db.py` and `webapp.py`.
- SQLite integration check passed: create, same-day update, second date, newest-first history, and user isolation.
