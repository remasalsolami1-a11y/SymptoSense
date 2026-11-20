# V240 — Static front body map with dynamic symptom buttons

## Applied change
- Kept the body illustration fixed for the **front view**.
- The **region buttons remain dynamic and selectable**.
- Pressing a body-region button still shows the common symptoms for that area.
- The custom text field remains available if the user does not find the right symptom.
- The **back view** remains functional with the existing interactive rendering.

## Files changed
- Part-05/0418__chat_view.py
- Part-01/0039__chat_view.py
- Part-02/0183__app-shell-v111.css
- Part-01/0024__app-shell-v111.css

## Validation
- Python syntax check passed.
- Regression tests passed:
  - 0429__test_v239_reference_body_map.py
  - 0427__test_v238_inline_body_map.py
