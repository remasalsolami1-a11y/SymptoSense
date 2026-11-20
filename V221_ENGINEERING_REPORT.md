# V221 Engineering Report — Guided Body Map Flow

## Implemented
- Mobile symptom entry now exposes three clear methods: **اختيار سريع / من الجسم / اكتب بنفسك**.
- Replaced the cramped mobile body-map controls with a larger neutral silhouette and tappable visual zones.
- Added front/back switching.
- Tapping a visual zone asks **«وش تحس في هذا المكان؟»** and shows symptom descriptions relevant to that zone.
- Added a permanent fallback: **«ما لقيت الوصف المناسب؟ اكتب وش تحس في هذه المنطقة بطريقتك.»**
- Visual sub-zones map to the existing broad backend medical regions, so the UI can be more specific without changing safety/eligibility/scoring semantics.
- No disease names are displayed at body-area selection time.
- Existing Quick Pick and free-text paths remain available.

## Safety / architecture
- Safety Engine precedence is unchanged.
- Sex eligibility, negatives, scoring, ranking, blood-context opt-in, and input-quality logic are unchanged.
- Body-map zones are presentation/navigation context only.

## Verification
- 974 tests passed across all non-Flask-dependent test files, run in batches.
- 0 failures in those runnable tests.
- Python compileall passed.
- Root/views `chat_view.py` copies match exactly.
- Root/static `app-shell-v111.css` copies match exactly.

## Not verified in this environment
Six integration test files could not be executed because Flask is not installed in the execution environment:
- test_authentication.py
- test_search_expansion.py
- test_signature_review_regressions.py
- test_stabilization.py
- test_symptom_data_expansion.py
- test_v44_review_fixes.py

These should be run in the normal project environment before production deployment.
