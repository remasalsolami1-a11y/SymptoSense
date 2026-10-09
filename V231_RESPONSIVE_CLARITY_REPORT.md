# V231 Responsive Clarity Review

Focused follow-up on the V230 body-map mobile presentation.

## Fixes
- Edge-region labels now open inward toward the center of the screen instead of toward the viewport edge.
- The body-map stage no longer clips connector labels on small phones.
- Minimum label text on <=380 px screens increased from 8.7 px to 10 px, with slightly wider label cards.
- Existing `dvh`, internal scrolling, and iOS safe-area handling are preserved.
- No medical engine, safety, scoring, or ranking logic changed.

## Verification
See `test_v231_body_map_responsive_clarity.py` plus V229/V230 body-map regression tests and release check.
