# SymptoSense — Symptom Result UI Refactor

## Scope
UI/UX refactor only for the symptom-analysis result screen. Medical analysis logic, risk calculation, matching, red-flag rules, APIs, database schema, authentication, and stored result data were not changed.

## What changed
- The result now replaces the questionnaire inside the same chat container instead of being appended below the questions.
- Result rendering no longer uses the chat `addHtml()` path that automatically scrolls to the newest message.
- No `window.scrollTo()`, `scrollIntoView()`, or `location.hash` behavior remains in the symptom-analysis page flow.
- The report is organized as: summary, entered information, possible conditions, next steps, warning signs, home care, suggested questions, explanation (collapsible), sources (collapsible), actions, feedback, and one disclaimer.
- Possible-condition cards use the existing `knowledge_matches` response order and existing `match_level`; no score is recalculated in the frontend.
- Data-quality percentage is explicitly labeled as information completeness, not diagnostic accuracy.
- The user-entered age/sex/symptoms/duration/severity are displayed from the same request payload sent to the existing API; medical outputs come from the API response.
- Existing functions are reused for new analysis, PDF export (`/api/analyze/export/{analysis_id}`), doctor handoff, speech playback, follow-up questions, and feedback.
- Buttons for record-dependent actions are only shown when a current `record_id` exists.
- The old page-level educational note is visually hidden in result mode (while preserving layout height) so the disclaimer appears once at the end of the report.

## Responsive behavior
- Desktop: bounded report width, two-column input/condition grids where appropriate.
- Mobile: single-column cards/actions/questions, larger touch targets, no intentional horizontal overflow.
- Report animations are disabled to avoid result-layout movement.

## Validation performed
- `python -m py_compile webapp.py` — passed.
- `python -m compileall -q .` — passed.
- Extracted symptom-page JavaScript parsed with `node --check` — passed.
- Static checks confirmed the symptom-analysis page contains no `window.scrollTo`, `scrollIntoView`, or `location.hash` calls.
- Static check confirmed result rendering uses `bodyEl.replaceChildren(...)` rather than appending via `addHtml(..., 'result')`.
