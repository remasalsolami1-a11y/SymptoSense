# Symptom Analysis Speed Fix

## Problem
The final symptom-analysis step could remain on “Analyzing…” for a long time in production.

## Root causes fixed
1. The `/api/analyze` path synchronously waited for an external Groq LLM response (up to 45 seconds) even though the displayed condition matches, risk level, sources, and grounded guidance were already determined by the medical knowledge base and deterministic safety rules.
2. `db.init_db()` repeated remote PostgreSQL validation/DDL work during request-time calls even though application startup already initializes the schema.
3. The Analyze button performed a second sequential `/api/user-info` request although the same profile context had already been fetched when the chat started.

## Changes
- Final symptom assessment no longer waits for Groq. It uses the verified medical knowledge base + safety rules immediately.
- Generative AI remains available in the separate assistant/follow-up chat and other existing AI features.
- Database/schema initialization is cached per **database identity** after successful startup initialization. SQLite uses canonical path + file identity; PostgreSQL uses a non-secret one-way DSN digest. A failed critical migration is never cached as ready and is retried on the next `init_db()` call.
- Reuses the user/profile context already loaded by the chat instead of fetching it again before `/api/analyze`.
- Added a 15-second client abort guard so a genuine network/backend failure cannot leave the UI spinning indefinitely.

## Safety and compatibility
- No routes were removed or renamed.
- Medical knowledge matching, red-flag checks, risk rules, sources, adaptive questions, saved results, history, and consent remain intact.
- The result remains non-diagnostic and source-grounded.

## Migration-cache safety
- Security-critical account migrations are no longer hidden by a broad `except Exception: pass`.
- Readiness is set only after `role`, `status`, `email_verified`, and `email_verified_at` are verified and the one-time email verification migration marker exists.
- Switching to a legacy SQLite database in the same process now triggers migration instead of reusing readiness from a different database.
- Replacing a SQLite file at the same path is also detected by file identity.

## Verification
- Python syntax compilation passed for `analysis_core.py`, `db.py`, and `webapp.py`.
- Direct local test with a fake Groq client that throws if instantiated confirmed symptom analysis completes without invoking Groq.
- Test case: headache + nausea + light sensitivity produced migraine as the strongest grounded match.
- Local warm analysis calls completed in about 0.03s (production timing will also include network/database latency).

- Added a regression test proving a failed critical migration is not cached and succeeds on retry.
- Existing legacy-account migration test now exercises database-identity-aware readiness after the primary test DB has already been initialized.
- In this editing environment, full pytest collection cannot run because Flask and Groq are not installed and package download is unavailable; targeted database regression checks passed locally.
