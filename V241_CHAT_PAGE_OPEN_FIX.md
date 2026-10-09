# V241 — Symptom analysis page open regression fix

## Root cause addressed
The V240 front-body artwork was embedded as a large base64 data URI inside `chat_view.py`. This unnecessarily inflated the symptom-analysis page JavaScript payload and made the `/chat` page more fragile during load/deployment.

## Fix
- Moved the fixed front-body artwork to a normal production static asset:
  `/static/images/body-map-front-v241.png`
- Kept the body artwork fixed while region buttons remain dynamic and clickable.
- Added the asset to the Docker static-image copy step.
- Added the asset to the Service Worker precache list.
- Bumped app-shell/cache identifiers to V241 so browsers do not keep V239/V240 assets.
- Preserved common-symptom buttons and custom symptom entry.

## Validation
- Python syntax: passed (`chat_view.py`, mirror, `webapp.py`).
- Service Worker JavaScript syntax: passed.
- Focused V238/V239/V241 body-map regression suite: 13 passed.
