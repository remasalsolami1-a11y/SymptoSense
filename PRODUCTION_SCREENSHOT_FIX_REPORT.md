# Production Screenshot Fix Report

Fixes based on the real Railway screenshots supplied after deployment:

- Moved About/Home visual references to the existing explicit `/icons/<filename>` Flask route and copied the visual assets there.
- Added graceful visual fallback so a missing image never renders a broken-image glyph or alt-text block.
- Reworked the footer to a light, high-contrast surface consistent with the premium design system.
- Reduced the floating assistant launcher visual weight.
- Improved Web Push activation UX: inline status, disabled state while subscribing, reuse existing subscription, clear browser/configuration errors, no browser `alert()` for normal failures.
- No authentication, database, medical logic, API contract, or route semantics were changed.

## Railway requirement for real notification delivery
Web Push still requires these Railway variables:

- `VAPID_PUBLIC_KEY`
- `VAPID_PRIVATE_KEY`
- `VAPID_CLAIMS_EMAIL`

Without them the UI now explains that server push is not configured instead of appearing broken.
