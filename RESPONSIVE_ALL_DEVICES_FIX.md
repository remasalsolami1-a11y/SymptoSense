# SymptoSense — Responsive All Devices Fix

Updated the bilingual landing page so the same health-tech design adapts cleanly across devices instead of rendering as a narrow mobile column on desktop.

## Breakpoints
- Mobile: <= 480px
- Tablet: 481–899px
- Laptop/Desktop: 900–1399px
- Large desktop: >= 1400px
- Short browser windows: height <= 760px
- Landscape phones/tablets: landscape + height <= 650px

## Key fixes
- Removed the normal site container width/padding constraints from the bare landing page.
- Added dedicated sizing for typography, logo, CTA, language cards, trust strip, benefits, and decorative elements.
- Preserved iPhone/Safari safe-area and `svh` behavior.
- Added vertical scrolling fallback on desktop and landscape so content is never clipped.
- Kept touch targets large on mobile and reduced crowding on short screens.
- Kept all language-selection behavior unchanged.
