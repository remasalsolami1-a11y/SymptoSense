# V223 Medication Search Hotfix

## Issue
Medication information search returned no trusted result for `Contrave` because the curated medication knowledge base did not include the brand/generic combination.

## Fix
- Added a reviewed Contrave / naltrexone-bupropion medication record.
- Added Arabic and English aliases for brand and generic-name variants.
- Improved medication-name normalization so slash, dash, and punctuation variants resolve consistently.
- Added sources meeting the existing source policy: SFDA local reference plus DailyMed and MedlinePlus clinical references.
- Added regression coverage for brand, Arabic spelling, generic order, slash and hyphen variants.

## Verification
- `release_check.py`: PASS
- Medication/source/safety targeted suite: 26 passed, 0 failed
- Fresh-database lookups verified for Contrave, كونتراف, كونتريف, naltrexone bupropion, bupropion/naltrexone, naltrexone-bupropion, and نالتريكسون/بوبروبيون.

## Scope
This hotfix expands the curated medication library for this drug and improves name matching. It does not turn the medication search into an unrestricted live internet drug database; unknown medicines still return the safe no-result state until reviewed/seeded in the knowledge base.
