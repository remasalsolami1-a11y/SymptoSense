# SymptoSense — Competition Final Polish Fix

Implemented in this package:

- The global floating assistant is hidden on the symptom-analysis page at every viewport size so only one assistant experience is shown.
- Voice/read-aloud controls are grouped under the `Accessibility / إمكانية الوصول` menu.
- Removed the always-visible microphone beside the text field, the symptom voice chip, the start-card voice button, and the result-page listen button.
- Read-aloud is off by default and starts only after the user enables it from Accessibility.
- Removed the duplicated disclaimer at the bottom of the Home page; the calm trust strip remains.
- Added a public published-comments KPI to the Home community card and `/community-dashboard`.
- Added a database-level `comment_count` for opt-in anonymous public comments without exposing names, emails, or health data.
- Kept public comment redaction and explicit sharing consent behavior unchanged.

Validation performed:

- `python -m compileall -q .` — passed.
- Static test suite — 41/41 passed.
- Competition polish tests — 17/17 passed.
- Temporary SQLite runtime check for users/ratings/public comment count — passed.

Note: the full runtime pytest collection could not run in the review container because Flask and groq are not installed in that environment; this is an environment dependency issue, not a syntax or static-validation failure.
