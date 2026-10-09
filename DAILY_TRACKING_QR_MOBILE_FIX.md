# Daily Tracking + QR Share + Mobile Data Quality Fix

## Scope
This patch is based on `SymptoSense-Professional-Result-UI-Fixed-Matching-DB-Safe` and addresses three reported production issues without adding medical analysis logic.

## 1) Daily Health Tracking

### Root cause
`api_checkin()` existed in `webapp.py`, but the `/api/checkin` route decorator was missing, so the visible mood buttons had no working endpoint to persist records.

### Fix
- Registered `GET/POST /api/checkin`.
- Daily tracking is account-bound; guests are directed to sign in.
- Added `checkin_date` to `daily_checkins` and a safe migration for existing databases.
- Backfills dates for legacy rows and collapses duplicate rows for the same user/day, keeping the newest entry.
- Enforces one row per user/day with a unique database index.
- Saving again on the same day updates the existing row instead of inserting a duplicate.
- Added real history loading from the database, newest first.
- Desktop uses a table; mobile uses stacked cards to avoid horizontal scrolling.
- Added a lightweight summary: today, average for the last 7 calendar days, and total check-ins.

## 2) Temporary QR health summary

### Fix
- The QR now encodes the dedicated public HTML route `/share/health/<token>?lang=...`, never an API endpoint.
- Public health-summary URLs are exempt from first-language-picker redirects, so a recipient can open a QR in a fresh browser.
- Share modal buttons are explicit `type="button"` controls.
- A QR is no longer created when the selected field contains no saved information; the UI asks the user to choose another field.
- Legacy empty share links render a clear message instead of a blank summary.

## 3) Symptom-analysis 100% mobile layout

### Fix
- The data-quality header now uses a stable grid layout.
- The numeric percentage uses `white-space: nowrap`, LTR isolation, and a fixed mobile score column.
- Prevents `100%` and the quality badge from stacking vertically on narrow iPhone screens.

## Verification performed
- `python -m py_compile db.py webapp.py privacy_features.py` — passed.
- Targeted regression suite: `tests/test_daily_checkin.py` + `tests/test_symptom_matching.py` — **7 passed**.
- SQLite same-day update + account isolation — passed.
- Legacy daily-checkin migration + duplicate collapse + unique index — passed.
- QR PNG encode/decode round-trip — passed.
- Temporary health-summary valid/empty-selection behavior — passed.
- Existing original `db.py` top-level functions were compared after the patch; none are missing.

## Full test-suite limitation
The full pytest suite cannot be collected in this execution environment because the environment does not have the project's `Flask` and `groq` dependencies installed. The collection failure is dependency-related, not a reported assertion failure from these changes.
