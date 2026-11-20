# SymptoSense V233 — Landing Second Review

Second-pass review of the V232 landing screen.

## Fixed
- Added a real public `/contact` route; V232 linked to `/contact` but no route existed, which could return 404.
- Kept Privacy and Terms links unchanged and verified their routes exist.
- Increased legal-link text on <=360px screens for clearer reading while preserving the 3-column footer.
- Confirmed About and the long disclaimer remain removed from the language picker only.
- Updated release metadata and service-worker cache to V233.

## Scope
Landing/contact routing and small-screen clarity only. No medical engine or safety logic changed.
