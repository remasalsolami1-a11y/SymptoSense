> **Status (V249): this file is now only a historical checklist.** The live review workflow is `/admin/clinical-review`
> (see `clinical_review.py`): edits to conditions, symptoms and red-flag rules are queued as proposals and are published
> only after a reviewer other than the author approves them. Rejections require a written note and every decision is audited.
> Set `SYMPTOSENSE_ALLOW_SELF_REVIEW=1` only for a single-admin deployment.

# MEDICAL REVIEW NEEDED — V217

This file lists medical eligibility/risk rules introduced or formalized in V217 that require clinician review before broad production expansion.

## Sex applicability
- `female_only`: period pain, endometriosis pattern, PCOS pattern, PMS pattern, heavy menstrual bleeding, irregular periods, vaginal thrush, bacterial vaginosis, perimenopause pattern, missed/late period, vaginal dryness, breast-pain pattern.
- `male_only`: no new disease row was invented because the current verified KB does not contain a reviewed prostate/testicular disease entity. Add such entities only after source + clinician review.
- `any`: all other current conditions remain sex-neutral by default. Sex must not add arbitrary score points.
- Unknown sex is conservative: sex-specific conditions are not surfaced unless a clearly sex-specific/anatomical symptom supplies the context.

## Age/context metadata
- Schema now supports `min_age`, `max_age`, and `pregnancy_relevant`.
- Age hard-exclusion must be used only for biologically impossible or explicitly reviewed bounds. Ordinary age associations should be scoring weights, not hard filters.
- No new disease age bounds were assigned in V217 without medical review.

## Negation evidence
- Free-text negation is merged with explicit negative follow-up answers before ranking.
- Negative evidence lowers compatibility proportionally and does not normally delete a condition.
- Emergency phrases such as Arabic “لا أستطيع التنفس” remain positive danger signals, not negated breathing symptoms.

## Safety-context rules
- Current mouth/throat/tongue swelling plus breathing difficulty remains emergency-level.
- A historical statement such as a past anaphylaxis history without current symptoms must not trigger the current-anaphylaxis emergency rule.
- Active/current seizure, current unresponsiveness, stroke-pattern focal deficit, and severe uncontrolled bleeding retain safety precedence over ranking.

## Review request
A licensed clinician should review all sex-specific slug assignments, any future male-only entities, any future age bounds, pregnancy relevance metadata, and changes to emergency context markers before production publication.

---

# V219 — Optional blood-context review

## Conservative blood-marker ↔ symptom links
V219 adds an **optional explanatory context layer only**. It does **not** change Safety Engine output, condition eligibility, compatibility scoring, negative penalties, or ranking.

The following conservative links are used only to decide which already-abnormal saved laboratory markers may be shown beside the symptom result:
- fatigue/tiredness/تعب/إرهاق → HGB, HCT, RBC, ferritin, iron, B12, folate, TSH, glucose/HbA1c
- dizziness/دوخة/دوار → HGB, HCT, RBC, ferritin, iron, glucose, sodium
- fever/حمى/حرارة → WBC, neutrophils, lymphocytes, CRP, ESR
- bleeding/نزيف → HGB, HCT, RBC, platelets
- bruising/كدمات → platelets, HGB, HCT
- thirst/عطش → glucose, HbA1c, sodium
- urinary-frequency wording/تبول → glucose, HbA1c, creatinine, eGFR

A licensed clinician should review these mappings before they are ever allowed to affect scoring or recommendations. In V219 they remain display-only context.

## Consent / UX rule
- A saved blood test is never auto-attached to symptom analysis.
- The user must explicitly choose **Use blood test** for the current assessment.
- Choosing **Continue without it** sends no `blood_id`.
- The choice resets when a new symptom-analysis flow starts.

## Input-quality layer
The three user-facing states (enough / improvable / limited) measure information completeness only. They are not diagnostic confidence, disease probability, or clinical severity.

## V221 — Body-map region → symptom suggestion mapping
- Review the symptom suggestions shown for each visual body zone (head/face, neck/throat, chest, upper/lower abdomen, arms/hands, thigh/knee/lower leg/foot, upper/lower back).
- These mappings are navigation aids only and do **not** change Safety Engine precedence, eligibility, scoring, ranking, or diagnosis logic.
- Disease names are intentionally not shown immediately after tapping a body area; the UI asks what the user feels in that area first.
- Confirm that each suggested symptom is reasonable for the zone and that no important high-risk symptom is obscured by the quick choices.


## V222 note
V222 did not add or alter medical classification, eligibility, emergency, or scoring rules. It refines symptom-entry UX, precise body-zone capture, result summarization, and field-specific editing only.

## V224 — Expanded bilingual medication catalog (50 medicines)

The medication information catalog was expanded from 11 to 50 curated entries. The 39 newly added entries cover common allergy/respiratory, cardiovascular, diabetes/weight, gastrointestinal, anticoagulant/antiplatelet, mental-health/neuropathic-pain, and antibiotic medicines.

Clinical review requested before treating the text as final production medical copy:

- Confirm Arabic transliterations and common brand aliases used in Saudi Arabia.
- Confirm the concise `warning`, `uses`, and `interactions` summaries for each medicine.
- Confirm that warnings are appropriately prioritized and not overly broad or falsely reassuring.
- Confirm wording for pregnancy-related warnings, bleeding risk, hypoglycemia, QT prolongation, serotonergic risk, opioid/sedative respiratory risk, and GLP-1/GIP safety notes.
- Confirm whether any brand aliases should be removed because local availability/branding can change.
- The catalog intentionally contains no dosing or personalized treatment instructions.
- Source links are references for verification; a pharmacist/physician should approve the final clinical wording.

New entries: loratadine, fexofenadine, salbutamol/albuterol, montelukast, fluticasone, atorvastatin, rosuvastatin, losartan, valsartan, lisinopril, bisoprolol, metoprolol, hydrochlorothiazide, levothyroxine, gliclazide, sitagliptin, empagliflozin, semaglutide, tirzepatide, insulin glargine, pantoprazole, famotidine, ondansetron, loperamide, naproxen, celecoxib, clopidogrel, apixaban, rivaroxaban, warfarin, sertraline, escitalopram, fluoxetine, duloxetine, gabapentin, pregabalin, azithromycin, doxycycline, cefuroxime.

## V225 — External medication fallback

The medication information page now keeps the curated local catalog first, then optionally queries official external medication data only after a local miss.

Medical/pharmacy review requested for:
- The presentation of external openFDA label excerpts under "uses", "warnings", and "interactions".
- The wording shown when a source lacks a structured interaction or indication section.
- The user-facing distinction between a locally curated bilingual record and an externally retrieved official label.
- The policy that external results are informational only and must never be used to recommend starting, stopping, changing, or dosing a medicine.

Engineering safeguards already present:
- No result is fabricated when an official label cannot be retrieved.
- Only the medication search term is sent to the external lookup; account and symptom context are not sent.
- External calls have strict timeouts and success/miss caching.
- Local curated records always take precedence over external data.

## V227 — Arabic summarization of external official drug labels

V227 changes **presentation only** for medication records retrieved from trusted external sources. It does not change the local 50-drug catalog, interaction engine, dosing logic, or symptom-analysis engine.

Clinical/pharmacy review requested for:
- The Arabic translation/summarization prompt used for official-label sections (`uses`, `warnings`, `interactions`).
- The requirement that boxed/serious warnings present in the source must not be dropped merely to shorten the text.
- The fallback wording shown when a reliable Arabic summary cannot be produced.
- The maximum summary length, to confirm that concision does not remove clinically important qualifiers.

Engineering safeguards:
- The summarizer receives only the retrieved public drug-label text and drug identity, not the user's account, symptoms, blood results, or reminder history.
- The summarizer is instructed not to add diagnoses, doses, treatment duration, or start/stop recommendations.
- Arabic output is accepted only when all required fields contain Arabic text; otherwise the page remains Arabic and shows a transparent unavailable-translation message plus the official source links.
- Successfully generated Arabic summaries are cached with the external record so repeat searches do not repeatedly invoke the language model.
- English pages also use compact excerpts rather than dumping long official-label paragraphs verbatim.

## V251 additions needing clinician sign-off
- `context_triage.py`: infant fever <3 months (threshold 38.0 C), suspected appendicitis, pregnancy pain warning signs / pre-eclampsia pattern, one-leg swelling with breathing symptoms (DVT/PE), plus the AR/EN first-aid steps shown in the emergency overlay for each.
- `health_search_expansion_v251.py`: allergy, sciatica, panic attack, low blood pressure, blurred vision, depression (text follows the cited pages; needs clinician sign-off). `trusted_sources_v251.py`: ~400 added references — link-verified but not clinically reviewed.

## V252 — بحث التحاليل والعبارات المركبة
- بطاقات التحاليل في البحث تعرض نصوص `blood_test` (INDICATOR_INFO/EXTENDED_INFO/عوامل محتملة) كما هي؛ لا نص جديد، لكن يلزم مراجعة طبيب لصياغة «إذا كانت مرتفعة/منخفضة».
- عند تساوي عنصرين (مثل ألم أعلى/أسفل يمين البطن) يعرض البحث الاثنين معًا ولا يرجح أحدهما؛ يلزم قرار سريري إن أُريد ترتيب مختلف.

## V253
- `redflag_screen.py`: صياغة الأسئلة الـ19 وتصنيفها (طارئ/اليوم) والعتبات (15 دقيقة، 8 ساعات، 3 أيام، 39°) تحتاج اعتماد طبيب، ثم `tools/signoff.py approve redflag_screens …`.
- `health_file.py`: عتبة «متكرر = 3 مرات» و«قريب من السابق = 2%» و«خارج النطاق في قراءتين متتاليتين = يحتاج انتباه» قرارات تصميمية تحتاج رأي سريري.
- الأولوية المقترحة للمراجعة: emergency_rules ثم redflag_screens ثم search_new_v251 ثم lab_cards.

## V254 (القرار الرباعي والمتابعة والسياق)
- `decision_card.py`: نصوص الحالات الأربع (راقب/احجز/اليوم/طوارئ)، وقائمة «ما الذي قد يغيّر القرار» وقائمة المعلومات الناقصة تحتاج مراجعة سريرية.
- `followup.py`: نافذة المتابعة (24 ساعة – 14 يومًا) ونصوص الردود، وقاعدة أن «ساءت» أو «علامة جديدة» ⇒ تقييم اليوم دائمًا.
- `medical_regression_snapshot.json`: **عُدّل بطلب المالك (V256) وينتظر اعتماد طبيب** — صعوبة التنفس بشدة 5/5 صارت «طوارئ» (اتجاه احترازي)؛ وبشدة 4/5 تبقى «اليوم». كان سابقًا «اليوم» دائمًا (تصميم قائم في `analysis_core._triage`: الطوارئ محجوزة لأنماط الخطر المحددة وتسأل الشاشات أسئلة علامات الخطر). هل يجب رفعه إلى طوارئ؟ لم أغيّره دون موافقة سريرية.
- `assistant_context.py`: ما يُرسل لمزوّد النموذج (أسماء أعراض/أدوية/مؤشرات مختبر فقط، بموافقة المستخدم لكل محادثة).
- لم يُنفَّذ: تعارضات دواء×دواء/مرض/عرض (تحتاج مصدرًا مرخّصًا مثل RxNorm/NIH + مراجعة صيدلاني).

## V257 — محرك الاستدلال والقياسات المنزلية (كلها بانتظار مراجعة)
- `vitals.py`: حدود التنبيه (ضغط ≥140/90 انتباه، ≥180/120 عاجل، <90/60 انتباه؛ سكر <70 انتباه، <54 طوارئ، >300 عاجل، صائم ≥126 / بعد الأكل ≥200 انتباه؛ حرارة ≥38 انتباه، ≥40 أو <35 عاجل؛ نبض >100 أو <50 انتباه، >130 أو <40 عاجل؛ SpO₂ <95 عاجل، <90 طوارئ). مجال الاعتماد: `vitals_thresholds`.
- `medication_context.py`: القوائم الكلمات المفتاحية (هضمي، نزف، طفح، كلى، كبد، حمل، ربو، قلب) وقاعدة «21 يومًا بعد بدء الدواء». لا توجد علاقات دواء×عرض مكتوبة يدويًا؛ الربط يتم فقط حين يذكر نص النشرة في الكتالوج الفئة نفسها. حُذفت فئات مشروطة (انخفاض السكر/الضغط). مجال: `medication_context`.
- `clinical_reasoning.py`: رفع مستوى المتابعة درجة واحدة (راقب→قريبًا→اليوم، لا يصل للطوارئ ولا يخفض) عند ارتفاع الشدة ≥2 أو إشارتين مستقلتين على الأقل (ارتفاع شدة، عرض جديد، دواء جديد، CBC أسوأ، قراءة منزلية عاجلة). مجال: `clinical_reasoning`.
- `followup.py`: نوافذ المتابعة حسب الخطورة (عالية 6س–3أيام، متوسطة 24س–7أيام، منخفضة 48س–14يومًا).
