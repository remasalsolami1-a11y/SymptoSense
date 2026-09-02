# Urgent possibilities + daily check-in repair

## Scope
This patch is based on `SymptoSense-Smart-Health-Search-Context-Fixed.zip`.

### 1) Symptom result when a red flag is detected
- Risk/triage remains urgent and is not downgraded.
- The legacy safety layer no longer deletes already-grounded knowledge-base matches or their sources.
- When grounded matches exist, they remain visible as non-diagnostic possibilities.
- Urgent cases still suppress ordinary recommendation cards/home-care guidance that could encourage waiting.
- The result UI shows an explicit warning above possible conditions that these matches do not confirm the cause of the red flag and must not delay urgent care.
- If no grounded match exists, no condition is invented.

### 2) Daily health tracking on older databases
- Added `db.ensure_daily_checkins_schema()` as a targeted, retry-safe schema guard for the daily check-in feature.
- It is cached per actual database identity, separate from the broader DB initialization cache.
- A failed repair is not cached, allowing the next request to retry.
- Legacy rows are backfilled using `CAST(timestamp AS TEXT)` before `SUBSTR`, making migration safer for older PostgreSQL timestamp column types as well as SQLite.
- `/api/checkin` now invokes the targeted check-in schema guard for GET and POST.
- Existing one-record-per-user-per-day behavior and user isolation are preserved.

## Verification performed
- `python -m py_compile db.py analysis_core.py webapp.py` passed.
- `python -m unittest tests.test_daily_checkin tests.test_health_search_compound -v`: 10/10 passed.
- Targeted urgent-result runtime check passed with a mocked grounded KB match: urgency stayed high/emergency, the KB match remained visible, and ordinary recommendations stayed empty.
- Full Flask test collection was not run in this container because Flask/Groq are not installed here.
