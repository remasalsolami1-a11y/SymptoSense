# Daily Tracking Stable Store Fix

## Why the previous Railway fix could still fail
The previous implementation still repaired and then queried the historical `daily_checkins` table. Production databases created by older releases can have a different shape, so a legacy migration/read could keep `/api/checkin` unavailable even while the rest of the app worked.

## Fix
- Daily tracking now reads and writes `ss_daily_checkins`, a small stable table dedicated to the account/day feature.
- Primary key: `(user_hash, checkin_date)`, guaranteeing one row per user per day.
- Re-saving the same day updates the existing row through `ON CONFLICT`.
- The old `daily_checkins` table is never required for the feature to work.
- Old usable rows are copied into the stable table on a best-effort basis after the stable table is committed.
- A malformed legacy table is logged and skipped rather than returning a 500 to the user.
- No LocalStorage/mock data is used; records remain in the configured persistent database.

## Verification
`python -m unittest tests.test_daily_checkin -v`: 7/7 targeted tests passed, including a deliberately incompatible legacy table that does not block new saves/reads.
