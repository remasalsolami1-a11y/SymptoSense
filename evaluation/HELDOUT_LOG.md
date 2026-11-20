# سجل مجموعات الاختبار المخفية / Held-out log

هذا السجل يوثّق متى استُخدمت كل مجموعة اختبار، حتى لا يُعرض رقم تطوير على أنه رقم اختبار مستقل.

## en_test (120 حالة إنجليزية)
- **قياس نزيه: V285** (قبل طبقات V286) — `evaluation/frozen/results_V285_last_clean_en_test.json`، محرك `deterministic-red-flag-v5-concepts`، بتاريخ 2026-11-12T11:30:14+00:00.
  - طارئ مكتشف: 57.5% (95% CI 42–71%; 23/40)
  - طارئ عُرض «منخفض»: 17.5% (95% CI 9–32%; 7/40)
  - الدقة: 54.2% (95% CI 45–63%; 65/120)
- **V286 — آخر قياس نزيه فعليًا:** طبقة قراءة المدة والشدة ومقارنة بحث الكلمات قيستا قبل فحص أي حالة من en_test (انظري الاستثناء أدناه). محفوظ في `evaluation/frozen/results_V286_last_clean_en_test.json`.
- **من V287 فصاعدًا:** فُحصت أخطاء هذه المجموعة حالةً حالة لتصنيف أنواع الأخطاء (قرار صاحبة المشروع، 2026-11-13). لذلك **كل رقم en_test من V287 هو رقم تطوير** ولا يُعرض كاختبار مستقل. القواعد الجديدة بُنيت على `evaluation/taxonomy_dev_cases.json` (حالات جديدة بصياغات مختلفة لكل نوع خطأ)، لا على نصوص en_test.
- **استثناء موثّق — V286 (قراءة المدة والشدة من النص، `text_context.py`):** صُمّمت بالنظر إلى حالات `en_dev` و`ar_dialect` فقط، وقيست على en_test **قبل** فحص أي حالة منها. لذلك تحسّن en_test في V286 من هذه الطبقة وحدها قياس خارج عيّنة التطوير، ويمكن عرضه كذلك مع ذكر هذا الشرط. أي تعديل بعد فحص أخطاء en_test (الخطوة 3) لا يشمله هذا الاستثناء.
- القواعد الجديدة تُبنى على حالات تطوير جديدة مكتوبة لكل نوع خطأ، لا على نصوص en_test نفسها.

## الاختبار المستقل الجديد
- `ar_external` — المجموعة الخارجية المختومة (`EXTERNAL_HELDOUT_PROTOCOL.md`). لم تُجمع بعد؛ تحتاج موافقة لجنة الأخلاقيات.

## fresh_probe (V290) — مجموعة صياغات جديدة مختومة
- `evaluation/fresh_probe_sealed.json`: ‏35 وصف أعراض و23 سطر تحليل دم، كُتبت لمراجعة الكود بعد V289 وخُتمت **قبل أي تعديل في V290**.
- البصمة (sha256): `987ad78ec0e56ada74654fd9f6a61c99ce1d1ded202e2db01697b7b75755b0a1` — يتحقق منها `tools/evaluate_fresh_probe.py`.
- خط الأساس V289: الأعراض 19/35، الدم 19/23.
- **حالتها: مجموعة فُحصت أخطاؤها مرة واحدة**، فلا تُعرض كاختبار مستقل أعمى. إصلاحات V290 كُتبت على حالات تطوير منفصلة لكل نوع خطأ (`evaluation/v290_dev_cases.json`) وبمفردات عامة، والتسميات لا تُعدّل بعد القياس؛ أي خلاف في التسمية يُذكر كخلاف.

## Log (English)
en_test was a clean held-out set up to and including V286 (frozen files for V285 and V286). From V287 its misses were inspected to build an error taxonomy, so every later en_test number is a development number. The new held-out estimate is the sealed external set.

fresh_probe (V290): 35 symptom texts + 23 blood lines written for the post-V289 review and sealed before any V290 change (sha256 above). Its errors were seen once, so it is an inspected probe set, not a blind held-out estimate. Fixes were built on separate development cases (evaluation/v290_dev_cases.json); labels are never edited.
