# Mobile Symptom Analysis Layout Fix

## Scope
Presentation-only refinement for the symptom analysis/chat page on small screens. Medical logic, adaptive questioning, routes, APIs, authentication, database behavior, and analysis logic were not changed.

## Changes
- Removed the duplicated global mobile header only while the symptom-analysis page is open on phones; the page keeps its own compact header and the bottom navigation remains available.
- Reworked the chat header into a compact responsive grid with small voice/read controls.
- Kept the family/member selector on its own clean row to avoid collisions.
- Increased the usable conversation area and prevented page-level scrolling/overlap with the bottom navigation.
- Regular question choices use one clear full-width button per row on phones.
- Symptom selection uses a two-column grid on wider phones and automatically switches to one column on narrow phones.
- The primary “Next” action remains visible at the top of the scrollable symptom choices.
- Refined chat bubbles, text input, related-symptom chips, progress bar, and result cards for small screens.
- Added a compact visual treatment for adaptive follow-up question labels.
- Added safer wrapping rules to prevent long Arabic/English text from causing horizontal overflow.

## QA
- `webapp.py` passes Python bytecode compilation.
- Responsive visual mock checked at 360×800, 390×844, and 430×932.
- No horizontal document overflow was detected at those widths.
