# Landing Mobile Safari Fix

Adjusted the SymptoSense welcome/language screen after real iPhone browser screenshots.

- Uses `100svh` in addition to dynamic viewport units so content fits Safari's smallest visible viewport.
- Reduced mobile vertical spacing, logo/headline sizes, CTA height, language-card height, and benefits-card height.
- Added a compact layout for phone viewports under 900px and an extra compact layout under 760px.
- Removed the CTA's `scrollIntoView(... block: center)` behavior that caused the page to jump and hide the logo/header on iPhone.
- CTA now highlights the two language choices without shifting the page viewport.
- Benefit subtitles now wrap inside their own columns instead of overlapping neighbouring columns.
- Landing-only browser theme color changed to a very light blue/white to better match the medical visual identity on mobile Safari/Chrome.
- Added scroll-restoration reset so returning to the welcome screen starts at the top.
- Existing Arabic/English selection, cookie, localStorage, and redirect behavior remains unchanged.

Validation:
- Python syntax compile passed.
- 56 static UI/regression tests passed.
