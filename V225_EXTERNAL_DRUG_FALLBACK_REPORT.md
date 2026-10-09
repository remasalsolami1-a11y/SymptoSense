# SymptoSense V225 — External Drug Fallback

## What changed

- Preserved the 50-drug bilingual curated catalog as the first lookup layer.
- Added a database-backed cache for successful external results (7 days) and misses (1 hour).
- Added official external lookup on local miss:
  1. openFDA label lookup using the user-entered name.
  2. RxNorm identity resolution only if the direct official-label lookup misses.
  3. openFDA retry using the resolved drug name.
- Added DailyMed and RxNorm source links alongside the openFDA official label source.
- Added clear external-source disclosure in the medication UI.
- The external request sends only the medication search term; no account, symptom, reminder, or lab context is sent.
- No generated/guessed medication content is shown when an official label cannot be verified.
- Added environment settings for enabling/disabling the fallback, network timeout, and optional openFDA API key.

## Safety behavior

- No dose recommendations.
- No treatment-start/stop/change recommendation.
- Missing label sections are identified as unavailable rather than inferred.
- External data never replaces a locally curated record with the same search match.

## Test results

- V225 external lookup + medication/reminder regressions: 24 passed.
- Existing non-Flask suite executed in bounded batches: 986 passed, 0 failed.
- Release check: PASS after removing generated pytest/Python cache artifacts.
- Seven Flask-dependent integration test files could not run in this environment because Flask is not installed.
- Live outbound HTTP from the packaged app could not be executed in this container environment; external HTTP behavior is covered with deterministic mocked-response tests. Production deployment should perform one live smoke test against RxNorm/openFDA.

## Release metadata

- APP_VERSION: 225.0.0
- RELEASE_CANDIDATE_ID: SymptoSense-v225-external-drug-fallback
- PWA cache: symptosense-shell-v225-external-drug-fallback
