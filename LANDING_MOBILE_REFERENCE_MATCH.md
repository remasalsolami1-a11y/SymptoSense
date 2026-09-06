# Landing Mobile Reference Match

The public language-selection landing screen was redesigned to match the approved mobile reference while preserving existing language-selection behavior.

## Visual changes
- Removed the old top brand header/card presentation from the landing screen.
- Full-screen white + soft medical-blue background.
- Custom blue/cyan stethoscope mark and SymptoSense wordmark.
- `Your Health, Smarter` subtitle.
- Large Arabic headline followed by the English headline.
- Bilingual explanatory text kept visible on mobile.
- Large rounded gradient `ابدأ الآن / Get Started` CTA.
- Side-by-side Saudi and UK language cards with real flag emoji.
- Three-part trust card: trusted information, easy to use, educational only.
- Bottom trusted-medical-sources note.
- Soft layered wave background and subtle leaf accent.
- Compact responsive rules for 480px, 380px, 335px and short-height mobile screens.

## Behavior preserved
- Arabic and English selection continues to set the existing `lang` cookie and `ss_lang` localStorage value.
- Redirect destination remains the existing safe next page / `/home`.
- No authentication, database, API, symptom analysis, or other site logic was changed.
