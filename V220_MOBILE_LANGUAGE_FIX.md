# V220 Mobile Language Page Fix

## Root cause
The welcome/language page received new disclaimer and legal-link content without dedicated responsive CSS. On mobile, the page shell also kept `justify-content:center`; once the content exceeded the viewport height, Safari centered an oversized flex column and could place the top portion above the initial viewport. The unstyled legal anchors then rendered as large default inline links and visually ran together.

## Fix
- Mobile welcome shell now uses `justify-content:flex-start`.
- Added responsive styles for `.first-lang-disclaimer` and `.first-lang-legal`.
- Legal links wrap with explicit row/column gaps and mobile-safe font sizing.
- Added bottom safe-area padding for iPhone Safari.
- Added a compact short-height profile without clipping content.
- Reduced decorative leaf prominence so it does not compete with footer content.
- No symptom-engine, triage, blood-analysis, auth, or routing behavior changed.

## Verification
- Python compile: passed.
- Targeted regression suite: 62 passed, 0 failed.
