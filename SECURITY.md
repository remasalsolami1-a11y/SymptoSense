# SymptoSense Security Notes

## Production baseline

- Railway requires `DATABASE_URL` and a stable `WEB_SECRET` of at least 32 characters.
- Set a stable, high-entropy `HASH_SALT` for pseudonymous user hashes. Keep it stable after launch; rotating an existing deployment requires a planned migration so historical pseudonymous records remain linkable to the correct account.
- HTTPS deployments use a `__Host-` prefixed session cookie with `Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/`, and no Domain attribute.
- Session lifetime is absolute rather than refreshed on every request.
- Browser mutation requests are protected by same-origin checks plus CSRF on authenticated health/account APIs.
- Public/auth/AI/analysis endpoints use server-side rate limits with a bounded process-local fallback.
- API JSON bodies, voice uploads, CBC uploads, and multipart form complexity are bounded before business logic.
- `TRUSTED_HOSTS` is derived from `SITE_URL`, Railway's public domain, and the optional explicit allow-list.
- Sensitive/account/health responses are `no-store`; private HTML is also marked `noindex`.

## XSS / CSP

User-controlled values must never be inserted into HTML without context-appropriate encoding. Values embedded inside JavaScript use `web_security.json_for_script()` rather than raw JSON serialization.

Executable JavaScript does not rely on `unsafe-inline` or `unsafe-eval`. Server-rendered inline `<script>` blocks receive a fresh per-request nonce, while `script-src-attr 'none'` blocks HTML event-attribute execution. `static/js/interaction-bridge.js` removes legacy event attributes and rebinds a restricted, allow-listed grammar through `addEventListener` without `eval` or `new Function`. Inline `<style>` blocks receive the same per-request nonce. Legacy `style="..."` attributes remain allowed only through the narrower `style-src-attr` directive; they are non-executable and tracked separately as a maintainability concern.

## Release checks

Run:

```bash
python release_check.py
python -m compileall -q .
python -m pytest -q tests
```

The first command is dependency-light and checks Python compilation, JSON syntax, SQLite integrity, release-version consistency, core security invariants, context-aware XSS/upload regressions, obvious committed secrets, and JavaScript syntax (standalone plus literal inline scripts) when Node.js is available.

## Reporting

Do not include real symptoms, medication names, account data, tokens, passwords, or uploaded medical files in bug reports. Use synthetic test data and the request ID returned by error responses when available.
