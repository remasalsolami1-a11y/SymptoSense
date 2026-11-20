# PDF Report Download Fix

## Root cause
The symptom result UI linked to `/api/analyze/export/<record_id>`, but the route called `_pdf_report(result, lang)` even though `_pdf_report` was not defined in `webapp.py`. The unhandled exception was converted by the global API error handler into JSON, which Safari displayed as a black raw-response page.

## Changes
- Added `_pdf_report()` using the already-installed PyMuPDF dependency.
- The PDF is generated only from the saved analysis result; no medical scores or conditions are recalculated.
- Added Arabic/RTL-compatible HTML-to-PDF rendering with automatic pagination.
- Changed the result download action from direct API navigation to a fetch/blob download flow.
- Download errors are shown inside the result UI instead of navigating to raw JSON.
- Added a regression test asserting that the export endpoint returns `application/pdf`, starts with `%PDF`, and contains real file data.

## Verification performed
- `webapp.py` and the new regression test pass `py_compile`.
- The new download JavaScript passes `node --check`.
- A representative Arabic report was generated and rendered to PNG for visual inspection.
- PDF preflight confirmed the generated file opens correctly and contains two valid pages.

Full project pytest was not run in this sandbox because the environment does not include the project's Flask/Groq dependencies.
