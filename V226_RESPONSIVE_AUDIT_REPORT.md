# SymptoSense V226 — Responsive Audit

## Scope

Reviewed the V225 codebase after the external medication fallback change, with special focus on the pages most recently changed: first-language selection, symptom analysis, guided body map, input-quality/result UI, medication information, and shared public/admin shells.

## Device matrix verified

Browser-based responsive smoke checks were executed across portrait and landscape viewport classes including:
- 320×568
- 360×640
- 375×667
- 390×844
- 412×915
- 430×932
- phone landscape 667×375
- phone landscape 844×390
- 768×1024
- 820×1180
- iPad landscape 1180×820
- 1024×768
- 1280×720
- 1366×768
- 1440×900
- 1920×1080

## Findings and fixes

- No horizontal overflow was detected in the representative public/admin responsive shell audit.
- Guided body-map, medication-card, external-source, and input-quality fixtures showed no clipping or horizontal overflow from 320px through 1920px widths.
- Primary body-map and symptom controls retain at least a 44px computed touch height in the audited mobile fixture.
- The first-language privacy/terms/about/contact links had a small touch area despite rendering without overlap. V226 increases their tap area while keeping the existing visual hierarchy.
- Added 360px portrait plus phone-landscape viewport profiles to the automated responsive smoke matrix.
- Phone-landscape welcome view remains vertically scrollable rather than clipping content; no horizontal overflow was observed.
- Root/static app-shell and design-system stylesheet copies remain byte-identical.

## Test results

- Responsive public/admin browser smoke: 60/60 checks passed.
- Focused mobile/body-map/medication component browser audit: no horizontal overflow or clipping in all audited viewports.
- Existing non-Flask pytest suite: 986 passed, 0 failed (run in bounded batches because of execution-time limits).
- Release check: PASS.
- Python compile: PASS.

## Environment limitation

The following seven application-integration test files still require Flask/application startup. Flask is not installed in this execution environment, so these are not reported as passing here:
- test_authentication.py
- test_search_expansion.py
- test_signature_review_regressions.py
- test_stabilization.py
- test_symptom_data_expansion.py
- test_v36_selected_improvements.py
- test_v44_review_fixes.py

Run them in the Railway/production-equivalent environment before final deployment approval.

## Release metadata

- APP_VERSION: 226.0.0
- RELEASE_CANDIDATE_ID: SymptoSense-v226-responsive-audit
- PWA cache: symptosense-shell-v226-responsive-audit
