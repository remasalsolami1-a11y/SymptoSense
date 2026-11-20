# V232 Landing Reference Match

## Scope
Landing / language-selection redesign only. No symptom engine, Safety Engine, medication engine, ranking, scoring, or medical-rule changes.

## Implemented
- Rebuilt the welcome/language page to match the approved reference composition.
- Kept the stethoscope logo, SymptoSense wordmark, and `Your Health, Smarter` tagline.
- Kept the bilingual hero title and short Arabic/English description.
- Replaced flag emoji language badges with `SA` and `EN` text badges.
- Added three compact benefits: trusted medical sources, your next step, easy to use.
- Removed the long bilingual disclaimer card from the welcome page.
- Removed the About link from this welcome page.
- Footer now contains only Privacy, Terms, and Contact.
- Privacy links to `/privacy`; Terms links to `/terms`; Contact links to `/contact`.
- Mobile layout intentionally allows a small natural vertical scroll instead of compressing content.
- Added `100dvh`, safe-area top/bottom padding, and narrow-phone rules down to 320px-class widths.
- Bumped release metadata to 232.0.0 and PWA cache to `symptosense-shell-v232-landing-reference-match`.

## Verification
| Check | Result |
|---|---|
| V232 landing + prior landing/body-map regressions | 33 passed, 0 failed |
| Release check | PASS |
| Python compile via release gate | PASS |
| JavaScript syntax via release gate | PASS |
| Translation quality gate | PASS |
| Privacy / Terms / Contact href assertions | PASS |
| About absent from welcome-page block | PASS |
| Long disclaimer absent from welcome-page block | PASS |

## Environment limitation
A full pytest collection still has 7 integration/regression files that import `webapp` directly or through a subprocess. Flask is not installed in the execution environment, so those Flask-dependent checks cannot be truthfully marked as passed here. The release gate and landing-specific static/regression tests do not require Flask and passed.

## Medical review
Not required for this release: no medical content/rule logic was changed. The disclaimer was removed only from the first language-selection screen; site policies and medical safety behavior elsewhere are unchanged.
