# Daily Check-in consent helper fix

## Root cause
Production Railway logs showed `/api/checkin` returning HTTP 500 with:

`NameError: name '_consent_required_json' is not defined`

The route reached the service-consent guard, but the shared JSON helper referenced by the route did not exist in `webapp.py`.

## Fix
- Added a single shared `_consent_required_json(next_path)` helper.
- Returns the API contract expected by the frontend:
  - `ok: false`
  - `consent_required: true`
  - `consent_url`
  - HTTP 403
- Uses Flask `url_for("consent", next=...)`.
- Rejects external/protocol-relative `next` destinations.
- Did not change check-in storage, medical logic, database migrations, authentication, or UI behavior.

## Regression coverage
Added a regression guard that verifies the helper exists and `/api/checkin` uses it.

Targeted daily check-in unittest suite: **12/12 passed**.
`py_compile` also passed for the modified Python source.
