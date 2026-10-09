# SymptoSense V219 — Blood Context + Input Quality

## Implemented
- Added per-assessment explicit opt-in before a saved blood test can be attached to symptom analysis.
- Removed automatic `blood_id` attachment from `localStorage`.
- `/api/blood/history` is queried only when the user chooses to proceed from the pre-analysis gate; it is not part of initial page load.
- Backend still scopes `blood_id` lookup to the authenticated owner via `db.get_blood_test(_data_user_id(), blood_id)`.
- Added `build_blood_symptom_context()` as a non-diagnostic explanatory layer.
- Linked blood context does **not** change Safety Engine output, eligibility, scoring, negative penalties, or condition ranking.
- The result can show up to four relevant abnormal/attention markers and explicitly states that ranking/emergency level were not changed.
- Added three user-facing input-quality states while preserving the legacy numeric score/level for API compatibility:
  - Enough information to analyze
  - Usable information that can be improved
  - Limited information — more details are needed
- Input quality remains before symptom analysis and never overrides emergency safety.
- Updated release metadata to V219 / 219.0.0.

## Regression test updates
Two older static tests expected the Analyze button to call `runAnalysis()` directly. V219 intentionally inserts `chooseBloodContextThenAnalyze()` so the user can explicitly opt in/out before analysis. Those assertions were updated rather than deleted.

Release-version assertions were updated from V218/218.0.0 to V219/219.0.0 where they explicitly track the current delivery version.

## Test results
Targeted V219 + V217/V218 safety/copy regression set: 51/51 passed during implementation.

Broader non-Flask batches after final fixes:
- Batch 1: 196 passed
- Batch 2: 140 passed
- Batch 3: 282 passed
- Batch 4 (excluding Flask-dependent `test_v44_review_fixes.py`): 224 passed
- Batch 5: 125 passed

Total across these non-Flask batches: **967 passed, 0 failed**.

Python compilation for modified Python files passed.

## Not verified in this execution environment
The full single-command pytest collection cannot complete because Flask is not installed in the tool environment. The following known test modules require Flask directly or through an integration subprocess and were therefore not executed here as part of the 967-pass total:
- `test_authentication.py`
- `test_search_expansion.py`
- `test_stabilization.py`
- `test_symptom_data_expansion.py`
- `test_signature_review_regressions.py` integration subprocess
- `test_v44_review_fixes.py`

This limitation is environmental; it is not counted as a passing result. These tests should be run in the normal project/Railway environment with `requirements.txt` installed before production deployment.

## Performance note
V219 adds no blood-history request during initial page load. The history lookup is deferred until the user reaches the pre-analysis gate and chooses to analyze, so this feature does not add a new network dependency to opening the symptom-analysis page.
