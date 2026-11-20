# SymptoSense V227 — Arabic External Drug Summary

## Problem reproduced
On the Arabic `/ar/meds` page, an external drug search could return a verified openFDA/DailyMed label while the visible `General information`, `Important warnings`, and `Interactions` content remained long English source text. This produced a mixed-language Arabic page and poor readability.

## Implementation
- Kept the source hierarchy unchanged: local curated catalog first, then trusted external fallback.
- Added `localize_external_result()` in `external_drug_lookup.py`.
- Arabic external results are translated and summarized from the retrieved official-label sections only.
- The prompt forbids adding diagnoses, doses, treatment duration, or medication start/stop advice.
- Serious/boxed warnings present in the source are explicitly required to survive summarization.
- Arabic summaries are cached with the existing external-drug cache.
- If a verified Arabic summary cannot be generated, no English paragraph is silently inserted into the Arabic page. The UI stays Arabic, explains that a verified Arabic translation is temporarily unavailable, and keeps the official source links.
- English external results are also compacted so the page no longer dumps very long label paragraphs.
- Added a visible Arabic note distinguishing translated/summarized official-label content from the original source.

## UX / responsive verification
- The new language-status note uses the existing medication-card visual system and wraps safely.
- Existing responsive browser smoke matrix: **60/60 passed** across 320×568 through 1920×1080, including phone landscape and iPad landscape.

## Automated verification
- V227 + V225 focused medication tests: **14 passed**.
- Non-Flask pytest suite, executed in bounded parallel groups: **993 passed, 0 failed**.
- `release_check.py`: **PASS** after cleanup.
- Python compile: **PASS**.

## Test updates
Existing tests that intentionally pin the active release ID/version/PWA cache/Docker build marker were updated from V226 to V227. No behavioral or safety test was deleted.

## Environment limitations
The same seven application-integration files require Flask/application startup and are not reported as passing in this container:
- `test_authentication.py`
- `test_search_expansion.py`
- `test_signature_review_regressions.py`
- `test_stabilization.py`
- `test_symptom_data_expansion.py`
- `test_v36_selected_improvements.py`
- `test_v44_review_fixes.py`

Live production verification should search at least one external-only drug on `/ar/meds` after deployment and confirm the Arabic summary provider is configured and reachable.
