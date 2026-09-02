# Consent Transition Speed Fix

## Problem
The privacy consent page could take noticeably long after clicking **Save choices & continue**, especially on Railway/PostgreSQL.

## Root cause
`save_consent()` performed multiple database connection cycles for a single submission: schema checks, previous-state read, consent write/logs, several privacy-event writes, and a final state read.

## Fix
- Privacy schema initialization is cached per application process after successful startup initialization.
- Consent state, consent audit logs, and privacy events are now written in one database transaction/connection.
- The returned consent state is built from the committed values instead of opening another connection to re-read it.
- The Continue button immediately enters a disabled `aria-busy` state with a "Continuing…" / "جاري المتابعة…" label.
- A 12-second client timeout prevents an indefinitely stuck button if the request truly fails.
- Redirect uses `location.replace()` after a successful save.

## Safety preserved
- Required service consent remains enforced.
- Optional analytics consent remains optional.
- Consent audit logging remains intact.
- Privacy event logging remains intact.
- No medical-analysis logic, authentication, routes, or database structure was removed.

## Verification
- Python syntax compilation passed for `privacy_features.py` and `webapp.py`.
- Local SQLite transaction test passed.
- Verified one DB connection per warmed consent save while preserving expected consent logs and privacy events.
