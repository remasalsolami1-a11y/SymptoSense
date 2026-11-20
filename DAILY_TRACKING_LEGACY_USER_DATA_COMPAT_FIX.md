# Daily Tracking — Legacy `user_data` Compatibility Fix

## Root cause found
The previous website daily-tracking implementation reused the long-standing `user_data` table, but still assumed the current schema included `updated_at`. An older Railway database can legitimately have only `user_id` and `data`, because `CREATE TABLE IF NOT EXISTS` does not add missing columns to an existing table.

That made the GET request fail immediately when the page loaded, before the user could save a check-in.

## Fix
- Detect the actual `user_data` column layout at runtime.
- Never select `updated_at` for the website check-in read path.
- Include/update `updated_at` only when that column exists.
- Support legacy text-like `user_id` columns as well as numeric ids.
- Support PostgreSQL JSON/JSONB `data` columns where applicable.
- Keep one check-in per account/day in the existing database; no new tracking-table migration is required.

## Regression coverage
Added tests for:
1. Legacy `user_data(user_id INTEGER PRIMARY KEY, data TEXT NOT NULL)` with no `updated_at`.
2. Legacy `user_data(user_id TEXT PRIMARY KEY, data TEXT NOT NULL)`.

Targeted daily-checkin test suite: 9/9 passed locally.
