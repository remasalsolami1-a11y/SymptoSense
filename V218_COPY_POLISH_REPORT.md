# SymptoSense V218 — Copy & Terminology Polish

## Scope
V218 is a wording/terminology release on top of V217. It does not intentionally change medical ranking, eligibility, negation, safety precedence, API behavior, or page layout.

## Applied changes
- Unified the main Arabic non-diagnostic disclaimer.
- Replaced broad wording such as "راجع الطبيب عند أي شك" with conditional, clearer care-seeking language.
- Reworded the safety escalation copy from "الأعراض الحمراء" to user-facing "علامة خطر" language.
- Standardized the 1–5 severity scale to: خفيف جدًا، خفيف، متوسط، شديد، شديد جدًا.
- Reworded percentage copy to explain compatibility rather than imply diagnostic probability.
- Reworded insufficient-result copy to avoid overclaiming understanding/certainty.
- Standardized user-facing "فحص الأعراض" to "تحليل الأعراض" in current web/PWA surfaces.
- Made medication warning gender-neutral.
- Reworded source verification copy to avoid implying a blanket guarantee.
- Replaced colloquial medication transcription question with formal Arabic.
- Simplified daily check-in copy to track change over time without emergency-like wording.
- Standardized common Arabic tanween spellings such as جدًا، طبيًا، تلقائيًا، فورًا in active user-facing modules.
- Kept root `chat_view.py` and `views/chat_view.py` byte-identical after the edits.

## Verification
- Python compileall: PASS.
- V218 copy-specific and regression tests: PASS.
- Non-Flask test suite runnable in the current environment: 961 passed, 0 failed, across four batches.
- 6 Flask-dependent test modules were not executed because Flask is not installed in this execution environment.
- No medical-engine logic or new network call was added in V218.

## Flask-dependent modules not executed here
- test_authentication.py
- test_search_expansion.py
- test_signature_review_regressions.py
- test_stabilization.py
- test_symptom_data_expansion.py
- test_v44_review_fixes.py
