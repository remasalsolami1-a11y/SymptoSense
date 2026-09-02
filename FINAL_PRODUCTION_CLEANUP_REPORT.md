# SymptoSense — Final Production Cleanup

This pass applies the concrete fixes found in the full-site review without rebuilding the project or changing medical matching/risk logic.

## Fixed

1. **Geolocation / nearest hospital**
   - `Permissions-Policy` now allows geolocation for this origin only: `geolocation=(self)`.
   - Emergency page explains that location is used only for the nearby-facility search and is not saved to the account.
   - Hospital names/links are escaped before insertion into HTML.
   - Map links are restricted to known HTTPS map hosts.

2. **Public API error privacy**
   - User-facing routes no longer return raw exception type/database/provider text.
   - Unexpected errors use the existing request-ID response (`_mk_error`) so Railway logs hold details while users receive a generic message + reference ID.
   - Expected handoff validation codes remain explicit and safe.
   - Blood-report extraction errors no longer reveal provider/OCR internals.

3. **Optional Analytics consent**
   - Product usage/page-view/journey telemetry is gated by `_analytics_consent_ok()`.
   - Essential reliability/security server logs remain separate from optional product Analytics.
   - Privacy copy now explicitly explains this difference.

4. **Secure session cookie on Railway**
   - `SESSION_COOKIE_SECURE` defaults to `True` automatically on Railway/HTTPS production unless explicitly overridden.
   - `HttpOnly` + `SameSite=Lax` remain enabled.

5. **PWA / iPhone install polish**
   - Manifest product name changed from `SymptoSense V2` to `SymptoSense`.
   - 192px and 512px PNG icons are declared in the manifest.
   - `apple-touch-icon` is declared in the global page head.
   - Service-worker cache version bumped so updated manifest/icons replace stale cached copies.

6. **Neutral Arabic copy**
   - Removed feminine-only prompts from the main web symptom flow.
   - Updated iPhone install wording, location errors, health tips, first-aid guidance, blood-test copy, and medication warnings to neutral/impersonal wording.
   - Corrected old About/Privacy text that inaccurately claimed all data was anonymous or never shared with a configured AI provider.

7. **Assistant responsiveness**
   - Web AI calls previously using 45-second waits now use a 20-second timeout/fallback path.
   - Shared bot AI waits were reduced to the same bound.

8. **CSP compatibility**
   - CSP remains Report-Only as intended.
   - `youtube-nocookie.com` is now allowed in `frame-src` so enabling CSP later will not unexpectedly block the existing first-aid videos.

9. **Observability / maintainability**
   - Inline silent `except Exception: pass` cases in `webapp.py` were replaced with debug logging where safe.
   - Public error handling is more centralized through `_mk_error` rather than exposing exception strings.
   - No large `webapp.py` split was attempted in this pass because that would be a broad refactor with unnecessary regression risk.

10. **Production package hygiene**
    - The local `symptosense.db` development database is intentionally excluded from the deployment ZIP.
    - Railway PostgreSQL remains the production datastore.
    - `__pycache__` is preserved in the package per the project owner's request.

## Validation

- All top-level Python files: `py_compile` passed.
- `manifest.webmanifest`: valid JSON.
- Focused regression suite: **26/26 passed**:
  - daily tracking
  - compound health search
  - symptom matching
  - production-cleanup static/security assertions
- Full pytest collection could not run in this execution environment because `flask` and `groq` are not installed here. This is an environment dependency limitation, not reported as a passing full suite.

## Not changed

- Medical analysis logic
- Risk calculation / red-flag logic
- Matching scores
- Knowledge-base medical data
- Authentication model or user roles
- Existing database schema as part of this cleanup
