# SymptoSense V224 — Bilingual Medication Catalog Expansion

## Scope
Expanded the curated medication-information catalog from 11 to exactly 50 medications.

Each record includes:
- Arabic display name
- English display name
- Arabic and English aliases / common brand-name search terms
- concise general warning text in Arabic and English
- general uses in Arabic and English
- major interaction/caution summary in Arabic and English
- source-policy references: Saudi SFDA reference + DailyMed + MedlinePlus

No dosing or personalized treatment recommendations were added.

## Coverage added
39 new medication records covering allergy/respiratory, cardiovascular, diabetes/weight, gastrointestinal, anticoagulant/antiplatelet, mental-health/neuropathic-pain, and antibiotic categories.

## Search behavior
Arabic and English brand/generic aliases are searchable. Representative verified examples include:
- كونكور / Concor -> bisoprolol
- أوزمبيك / Ozempic -> semaglutide
- مونجارو / Mounjaro -> tirzepatide
- إليكويس / Eliquis -> apixaban
- سيبرالكس / Cipralex -> escitalopram
- زينات / Zinnat -> cefuroxime
- فنتولين / Ventolin -> salbutamol
- كريستور / Crestor -> rosuvastatin
- جارديانس / Jardiance -> empagliflozin
- ليريكا / Lyrica -> pregabalin

## Verification
- Catalog count: 50 medications exactly.
- Source maps: 50/50 records have source-policy mappings.
- Fresh-database lookup test validates every medication record and source policy.
- Medication/reminder/knowledge targeted regression suite: 29 passed, 0 failed.
- `release_check.py`: PASS after release-tree cleanup.
- Python compile gate: PASS via release check.
- JavaScript syntax/security/release metadata gates: PASS via release check.

## Environment limitation
The full Flask-dependent integration suite could not be run in this execution environment because Flask is not installed. This limitation is environmental and is not counted as a passing test. The medication-specific tests do not require Flask and were run successfully.

## Medical review
See `MEDICAL_REVIEW_NEEDED.md`. The 39 newly added concise clinical summaries and Saudi-market brand/transliteration aliases should be reviewed by a physician or pharmacist before final clinical sign-off.
