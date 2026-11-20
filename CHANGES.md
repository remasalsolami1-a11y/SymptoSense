# SymptoSense — CHANGES

## V68.15 (Phases 1 + 2 of the improvements prompt)

### Done
- **Emergency (Phase 1):** 997 ambulance first; 911 shown with the regions where it works (Riyadh, Makkah, Madinah, Eastern Province);
  937 health line; police 999 and civil defense 998 have tap-to-call buttons; mental-support box links 997/911/937 with a regional note.
  The same regional wording was applied to every crisis/other-harm message (`mental_support.py`, assistant system prompt,
  in-page crisis cards, `bot.py`, emergency CT strings) — none of them says 911 works everywhere any more.
- **One source for knowledge-base numbers (Phase 2):** new `kb_stats.get_kb_stats()` (active rows only; verified sources only).
  Home and trust now read from it, so both show 30 sources / 290 symptoms / 158 conditions / 23 red-flag rules.
  "288 of 290 symptoms linked" is a different, labelled metric (linked vs total), not a contradiction.
- **Changelog:** new `/ar/changelog` and `/en/changelog` (footer link + sitemap). The V75/V76 text now lives there; the sources page no longer carries it.
- **Accountability settings:** env vars `MEDICAL_REVIEWER_NAME/TITLE`, `ACADEMIC_SUPERVISOR_NAME/TITLE`, `CONTACT_EMAIL`.
  Shown in the footer (every page, including about and privacy) only when set. Nothing is invented.
- **Library duplicates:** checked the live library output — 448 unique items (158 conditions + 290 symptoms), no duplicates by link or title.
- **Already fine, no change needed:** "0 tests" counter (hidden when zero), offline banner (hidden), no `meta keywords`, x-default hreflang exists, first-aid/tips are server-rendered.

### Not done / decisions
- `/ar/chat` and `/en/blood` still redirect visitors to the consent gate (kept on purpose — they process health data).
- Community reviews: production data is not available in this workspace, so the review list could not be produced here. Nothing was deleted.

### Needs your decision
- Fill `MEDICAL_REVIEWER_NAME/TITLE`, `ACADEMIC_SUPERVISOR_NAME/TITLE`, `CONTACT_EMAIL` on Railway when real names are confirmed.

### Needs human review
- The regional 911 wording should be confirmed by a person against the official MOH/SRCA announcement.
- Clinical sign-off (`signoff_cli.py check --strict`) is still pending for 9 domains.
