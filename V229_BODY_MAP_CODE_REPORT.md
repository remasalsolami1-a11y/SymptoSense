# V229 — Body Map Applied in Code

## What changed
- The approved body-map look is implemented as interactive SVG/CSS/JavaScript, not as a screenshot or static raster mockup.
- The mobile sheet header now says **اختر المنطقة** with the instruction **اضغط على الجزء الذي تشعر فيه بأعراض**.
- Front/back switching remains interactive.
- Region labels, connector lines, and tap points remain real controls wired to the existing symptom-region flow.
- The currently selected region is shown in an accessible live summary.
- iPhone Safari uses dynamic viewport units (`dvh`), safe-area bottom padding, and internal scrolling so the body map does not disappear behind browser chrome.
- Mobile entry tabs remain short: **اختيار سريع | من الجسم | اكتب بنفسك**.

## Medical engine impact
No Safety Engine, eligibility, scoring, ranking, or diagnostic logic was changed. This release is presentation/responsive/UI wiring only.

## Verification
- Body-map / symptom-flow targeted tests: **26 passed, 0 failed**.
- `release_check.py`: **PASS**.
- Python source compile check: **PASS**.
- Duplicate runtime files (`chat_view.py` and CSS copies) were synchronized and regression-tested.
