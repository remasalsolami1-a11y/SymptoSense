# SymptoSense V238 — Inline Body Map Fix

- Mobile symptom step now defaults to the body-map path.
- Removed the extra body-map launcher/modal hop on mobile.
- Tapping "من الجسم" renders the body map inline immediately.
- Tapping a body area immediately shows common symptoms for that area.
- The "ما لقيت عرضك؟" custom description input remains directly below the common symptoms.
- The three input methods are now compact tabs instead of oversized cards.
- Existing selected-region clearing/editing and Next validation are preserved.
- CSS/service-worker cache version bumped to V238 so iPhone/Safari receives the new UI.
- No changes to Safety Engine, PDF, blood analysis, uploads, file_hash deduplication, or medical logic.
