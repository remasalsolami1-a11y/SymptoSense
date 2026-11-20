# SymptoSense V217 Engineering Report

## Scope completed
- Eligibility is evaluated before condition scoring. Conditions now support `sex_applicability`, `min_age`, `max_age`, and `pregnancy_relevant` metadata.
- Current reviewed female-specific disease rows are marked `female_only`. No unreviewed prostate/testicular disease was invented; the current verified KB has no such disease row.
- Unknown sex is conservative; a clearly sex-specific symptom can provide anatomical context without assuming a sex.
- Parsed free-text negatives are merged with explicit negative follow-up answers before ranking.
- Negative evidence lowers compatibility; it does not normally hard-delete a condition.
- Safety remains before ranking. Current breathing failure, unresponsiveness, active seizure, stroke-pattern focal findings, severe bleeding, and current anaphylaxis patterns retain precedence.
- Historical anaphylaxis wording is separated from a current mouth/throat swelling + breathing emergency pattern.
- Result UI shows understood present/absent symptoms and negative evidence in the explanation.
- Changing sex in “Edit my answers” resets sex-sensitive adaptive-question context before re-analysis.
- Docker-deployed `app-shell-v111.css` is synchronized with `static/css/app-shell-v111.css`, including `.doctor-card-section`.
- Language picker separates the non-diagnostic warning from benefit cards and uses source-grounded trust wording.
- Arabic active UI/core copy was normalized for `تشخيصًا`, `طبيًا`, and `فورًا` in the edited runtime surfaces.
- Release metadata was bumped to V217 / `APP_VERSION=217.0.0`; the PWA cache key was bumped.
- `.env.example` documents `SYMPTOSENSE_ADMIN_EMAIL` as required for automatic owner bootstrap/recovery without including a real address.

## Test results

| Stage | Result | Notes |
|---|---:|---|
| Relevant baseline before engine changes | 31 passed | Existing sex/safety/V216 targeted set |
| Expanded V217 regression set | 53 passed | Includes eligibility, negation, safety context, UI, CSS and release checks |
| Performance/static speed checks | 18 passed | Existing login/chat/library/search/performance guards |
| Existing suite batch 1 | 465 passed | All non-Flask-dependent tests in first half |
| Existing suite batch 2A | 263 passed | All non-Flask-dependent tests in first half of second batch |
| Existing suite batch 2B | 225 passed | All non-Flask-dependent tests in second half of second batch |
| Total executable existing tests | **953 passed** | No failures in tests runnable in this environment |
| Python compile check | Passed | `compileall` completed successfully |

## Local engine timing
After schema warm-up, 30 deterministic `knowledge_bundle` runs for `صداع + غثيان + بدون حرارة` measured:
- median: **127.45 ms**
- p95: **140.15 ms**
- max: **144.21 ms**

No external network/LLM call was added to the symptom-result path or initial-page path.

## Tests not executable in this environment
The complete pytest collection could not be executed because this tool environment does not have Flask installed. Installing Flask was attempted, but outbound package download failed because DNS/network access is unavailable. The files identified as directly Flask-dependent are:
- `test_authentication.py`
- `test_search_expansion.py`
- `test_signature_review_regressions.py`
- `test_stabilization.py`
- `test_symptom_data_expansion.py`
- `test_v44_review_fixes.py`

These were not marked passed. They must be run in the normal project/Railway environment after `pip install -r requirements.txt`.

## Runtime verification not claimed
- Live Railway/browser response time was not measured from this container.
- Live `/ar/` and `/en/` cookie/bot redirect requests were not executed because Flask is unavailable here; existing static language-loop guards remain passing.
- No clinician review was performed. See `MEDICAL_REVIEW_NEEDED.md`.
- No new male-only disease content was created without reviewed sources/clinical approval.

## Repository hygiene for the delivery archive
The V217 delivery archive excludes generated caches (`__pycache__`, `.pytest_cache`, `*.pyc`), local SQLite databases, historical Vxx change reports, audit-preview artifacts, and other generated QA report files. Source code, runtime assets, current tests, deployment files, `MEDICAL_REVIEW_NEEDED.md`, and this report are retained.
