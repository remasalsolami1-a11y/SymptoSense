# Smart Health Search — Context & Causes Fix

## What changed

- Fixed `/api/search` so the editable Medical Knowledge Base no longer replaces a useful curated search result with an empty `causes` list.
- Existing curated explanations and possible/common causes are preserved; Medical Knowledge Base data only enriches missing fields and trusted sources.
- Added compound-query recognition. A phrase containing more than one known symptom/concept now returns separate topic cards instead of silently choosing one word.
- Added an educational `sweet_taste` / altered-taste search concept for Arabic and English queries such as `طعم سكر`, `طعم حلو في الفم`, and `sweet taste in mouth`.
- Added guard logic so `طعم السكر` is not incorrectly treated as a separate diabetes search just because the word `السكر` appears inside the taste phrase.
- Compound results explicitly state that multiple symptoms do not imply one shared cause.
- Compound results offer the existing assistant and existing symptom-analysis flow; no new AI or diagnosis logic was added.
- Trusted sources remain attached to the specific symptom/concept they support instead of being merged into a misleading compound source list.
- Mobile compound-result layout is single-column.

## Verification

- `python -m py_compile health_search.py webapp.py` — passed.
- Search-page runtime JavaScript extracted from the Python template and checked with `node --check` — passed.
- 11 targeted regression tests passed, including 4 new smart-health-search tests:
  - single dizziness search retains causes;
  - `أحس بطعم سكر عند الدوخة` recognizes both concepts;
  - `طعم السكر` does not falsely add diabetes;
  - English compound query works.

No symptom-analysis scoring, risk logic, database schema, authentication, or AI backend was changed.
