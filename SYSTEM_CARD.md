# بطاقة النظام — SymptoSense / System Card

> يُولَّد هذا الملف آليًا من نتائج القياس (`python tools/system_card.py`). لا تعدّليه يدويًا.
> Generated from the measured results. Do not edit by hand.
>
> الإصدار / version **281.0.0** · محرك الأمان / safety engine **`deterministic-red-flag-v8-review-fixes`** · القياس / measured **2026-11-16T21:41:18+00:00**

---

## بالعربية

### ما هو؟
أداة **تثقيف صحي وفرز أولي** بالعربية (والإنجليزية): يصف الشخص أعراضه بكلماته، فيجيب النظام بمستوى الرعاية المناسب — **طوارئ الآن (997)**، أو **تقييم طبي قريب**، أو **رعاية ذاتية مع متى تراجع** — مع السبب والمصادر.
**ليس** تشخيصًا، ولا بديلًا عن الطبيب، ولا جهازًا طبيًا معتمدًا، ولا يُستخدم لتحديد علاج أو جرعة.

### من يتخذ القرار؟
| الطبقة | ماذا تفعل | هل تحدد مستوى الخطورة؟ |
|---|---|---|
| قواعد الأمان الثابتة (عبارات + مفاهيم مركّبة) | تكتشف علامات الخطر حتى بالعامية والأخطاء والعربيزي، وتفهم النفي | **نعم** — وتوقف التحليل وتطلب الطوارئ |
| قواعد الفرز (العمر، الشدة، المدة) | ترفع المستوى عند الحاجة | **نعم** — ترفع فقط |
| قاعدة المعرفة الطبية | تقترح احتمالات من مصادر موثقة | تساهم في المستوى غير الطارئ |
| المصنّف المساعد (Naive Bayes، `MODEL_CARD.md`) | ترتيب احتمالات تعليمي؛ دقته على بيانات اصطناعية 65.28% | **لا** |
| الذكاء الاصطناعي التوليدي | يكتب الشرح بلغة بسيطة فقط | **لا** — معطّل تمامًا في كل القياسات أدناه |

كل تنبيه طوارئ يعرض **«لماذا ظهر هذا التنبيه؟»**: الكلمات التي كتبها الشخص نفسها (مقتطعة من نصه حرفيًا)، والمفهوم الطبي الذي تعنيه، والقاعدة التي اشتغلت.

### كيف قيس؟
- حالات افتراضية (vignettes) وليست مرضى؛ لا مشاركين بشريين في هذا القياس.
- المرجع: تصنيفات أولية كتبها الفريق — **غير مراجَعة طبيًا بعد**.
- ضبط المتغيرات: الشدة 2/5، العمر 35، بدون مدة، الذكاء الاصطناعي معطّل.
- فصل التطوير عن الاختبار: مجموعة الاختبار الإنجليزية لم تُفحص حالةً حالة حتى V286 (نتائجها مختومة)؛ ابتداءً من V287 تُعدّ نتائجها تطويرًا (`evaluation/HELDOUT_LOG.md`). كل المجموعات العربية كتبتها صاحبة المشروع فهي **مجموعات تطوير** تبالغ في تقدير الأداء.
- فترات ثقة Wilson 95%، ومعامل كابا (κ).

### النتائج (النظام الكامل)
| المجموعة | النوع | n | طارئ مكتشف | طارئ عُرض «منخفض» | مبالغة | الدقة | κ |
|---|---|---:|---:|---:|---:|---:|---:|
| إنجليزي — مجموعة الاختبار | تطوير (فُحصت في V287) | 120 | 97.5% | 0.0% | 2.5% | 95.0% | 0.925 |
| إنجليزي — مجموعة التطوير | تطوير | 60 | 100.0% | 0.0% | 1.7% | 98.3% | 0.975 |
| عربي فصيح | تطوير | 40 | 100.0% | 0.0% | 0.0% | 97.5% | 0.96 |
| لهجة سعودية | تطوير | 40 | 100.0% | 0.0% | 0.0% | 100.0% | 1.0 |
| لهجة + أخطاء كتابة | تطوير | 40 | 100.0% | 0.0% | 0.0% | 100.0% | 1.0 |
| عربي + كلمات إنجليزية | تطوير | 24 | 91.7% | 8.3% | 0.0% | 91.7% | 0.8689 |
| عربيزي | تطوير | 8 | 100.0% | 0.0% | 0.0% | 100.0% | 1.0 |
| أنواع الأخطاء (V287) + حالات بسيطة مشابهة | تطوير | 56 | 100.0% | 0.0% | 0.0% | 100.0% | 1.0 |
| أطفال بأعمارهم الحقيقية | تطوير | 30 | 100.0% | 0.0% | 0.0% | 100.0% | 1.0 |
| تركيبات تحتاج طبيبًا + حالات مشابهة بسيطة | تطوير | 26 | — | — | 0.0% | 100.0% | 1.0 |

- **أهم رقم — آخر قياس مستقل (V286، مختوم في `evaluation/frozen/`):** على 120 حالة لم تُفحص أثناء التطوير اكتشف النظام 57.5% (95% CI 42–71%; 23/40) من الحالات الطارئة؛ طارئ عُرض «منخفض» (أخطر خطأ): 5.0% (95% CI 1–16%; 2/40). نظام يبحث عن الكلمات فقط اكتشف 25.0% على نفس الحالات.
- **بعد V287 على نفس الحالات (تطوير — فُحصت أخطاؤها):** طارئ مكتشف 97.5% (95% CI 87–100%; 39/40)، وطارئ عُرض «منخفض» 0.0%. لا يُعرض هذا كاختبار مستقل؛ التقدير المستقل القادم هو المجموعة الخارجية.
- مجموعة التطوير الإنجليزية: 100.0%. قواعد الخطر وحدها (الحالي): 92.5%.
- **مقارنة ببحث الكلمات في النفي والعربيزي:** في حالات النفي أطلق نظام الكلمات 4/10 إنذار طوارئ خاطئ مقابل 0/10 لنظامنا؛ وفي العربيزي اكتشف 0.0%.
- طبقة العربيزي: اكتشاف الطوارئ في العربيزي 0.0% بدونها ← 100.0% معها (عدد صغير جدًا).
- حسب مفردات المنطقة (خليط + عربيزي): خليجية/شرقية: 80.0% (n=5)، حجازية: 100.0% (n=4)، نجدية: 100.0% (n=6)، جنوبية: 100.0% (n=2).
- مجموعة اختبارات الأمان المدمجة: 47/47؛ إنذارات خاطئة 0.0%.
- المجموعة الخارجية المختومة: لم تُجمع بعد — البروتوكول في `evaluation/EXTERNAL_HELDOUT_PROTOCOL.md`.

### حدود معروفة (بصراحة)
1. **الحالات المتوسطة:** في مجموعة الاختبار ما زالت 2 من 40 حالة «تحتاج تقييمًا قريبًا» تظهر «منخفضة» (كانت 36 قبل طبقة قراءة المدة والشدة من النص في V286). أغلب الباقي يحتاج معرفة تركيبات أعراض (مثل حرارة مع حرقان بول)، لا مدة.
2. **ما زال يفوّت حالات طارئة** في صياغات لم يُبنَ عليها: آخر رقم مستقل أعلاه وفترة ثقته هو المرجع، لا رقم التطوير.
3. **التصنيفات المرجعية غير مراجَعة طبيًا** حتى يُكمل الطبيب `evaluation/doctor_review.csv`.
4. **العربي كله بيانات تطوير** حتى تُجمع المجموعة الخارجية.
5. قاعدة «حمى + تيبّس رقبة» تشترط علامة ثالثة (تشوش أو صداع شديد…)؛ مسألة سريرية مفتوحة للطبيب المراجِع.
6. تحويل العربيزي يغذّي طبقة المفاهيم فقط، لا قواعد العبارات.
7. **حالات الأطفال** كتبتها صاحبة المشروع من قوائم علامات الخطر المنشورة (NICE وNHS)، و**تصنيفها يحتاج طبيبًا** قبل الاستشهاد بها.
8. لم يُختبر مع مستخدمين حقيقيين؛ أي اختبار كهذا يحتاج موافقة لجنة أخلاقيات البحث أولًا.

### المسار الحقيقي في الموقع
كل الحالات عبر `POST /api/analyze` كما يرسلها المتصفح: نفس قرار المحرك في **525/525**. حارس ردود الذكاء الاصطناعي (`answer_guard.py`) صحّح **780/780** ردًا مطمئنًا خاطئًا مكتوبًا عمدًا.


### تحليل الدم
55 تقريرًا اصطناعيًا (تطوير): التقارير التي فيها قيمة حرجة وظهرت «عاجل/طوارئ» 17.6% في V287 ← 100.0% (95% CI 85–100%; 21/21)؛ إنذارات حرجة خاطئة 0.0% (95% CI 0–10%; 0/34)؛ تصنيف كل تحليل 83.6% ← 100.0%. حدود القيم الحرجة (`blood_critical.py`) تنتظر موافقة الطبيب.

### إمكانية الوصول (قياس آلي)
21 صفحة × لغتين × شاشتين = 84 فحصًا بأداة axe-core (WCAG 2.2 A/AA): **84 بلا مخالفة جدية**، تباين ألوان غير كافٍ: 0، أهداف لمس أصغر من 24px: 0. الأدوات الآلية لا تغني عن الفحص اليدوي (`ACCESSIBILITY_CHECKLIST_AR.md`).

### الخصوصية والسلامة
- لا يُحفظ تحليل الزائر في سجل صحي. تُحفظ نسخة مجهولة مختصرة (العمر، الجنس، الأعراض، المدة، الشدة، المستوى — دون ملاحظات أو اسم أو بريد أو عنوان IP) **فقط** إذا وافق الزائر اختياريًا على التحليلات أو المشاركة البحثية، ويمكنه سحب الموافقة. صاحب الحساب تُحفظ نتائجه في سجله.
- صفحة العرض `/live-demo` تشغّل المحرك الحقيقي على 4 حالات ثابتة ولا تحفظ شيئًا.
- كل تغيير في ملفات المحرك يغيّر بصمة الخوارزمية (`research_study.py`)، فلا تُخلط نتائج نسختين.

---

## In English

### What it is
An Arabic-first **health-education and triage aid**. A person describes symptoms in their own words; the system answers with a level of care — **emergency now (997)**, **medical assessment soon**, or **self-care with when to seek help** — plus the reason and sources. It is **not** a diagnosis, not a substitute for a clinician, not a certified medical device, and not for treatment or dosing decisions.

### Who decides
Fixed safety rules (phrases + compositional concepts, with typo, dialect, Arabizi and negation handling) can force an emergency and stop the analysis. Triage rules (age, severity, duration) can only raise the level. The knowledge base proposes non-urgent possibilities. The auxiliary Naive Bayes classifier (synthetic-data accuracy 65.28%, see `MODEL_CARD.md`) never sets the level. Generative AI only writes explanations and was disabled for every measurement below. Every emergency alert shows **"Why are you seeing this alert?"** with the person's own words (exact slices of their text), the concept each one maps to, and the rule that fired.

### Evaluation
Vignettes, not patients; no human participants. Reference: starter labels written by the team — **not yet clinician-verified**. Controlled: severity 2/5, age 35, no duration, AI off. The English test set was not inspected case by case up to V286 (frozen); from V287 it is a development set; all Arabic sets were written by the author and are **development** sets. Wilson 95% CIs; Cohen's κ.

| Set | Type | n | Urgent caught | Urgent shown as low | Over-triage | Accuracy | κ |
|---|---|---:|---:|---:|---:|---:|---:|
| English — test set | dev (inspected in V287) | 120 | 97.5% | 0.0% | 2.5% | 95.0% | 0.925 |
| English — development set | dev | 60 | 100.0% | 0.0% | 1.7% | 98.3% | 0.975 |
| Arabic, Modern Standard | dev | 40 | 100.0% | 0.0% | 0.0% | 97.5% | 0.96 |
| Saudi dialect | dev | 40 | 100.0% | 0.0% | 0.0% | 100.0% | 1.0 |
| Dialect + typos | dev | 40 | 100.0% | 0.0% | 0.0% | 100.0% | 1.0 |
| Arabic + English words | dev | 24 | 91.7% | 8.3% | 0.0% | 91.7% | 0.8689 |
| Arabizi (Latin letters + digits) | dev | 8 | 100.0% | 0.0% | 0.0% | 100.0% | 1.0 |
| Error-taxonomy cases + mild look-alikes | dev | 56 | 100.0% | 0.0% | 0.0% | 100.0% | 1.0 |
| Children with their real age | dev | 30 | 100.0% | 0.0% | 0.0% | 100.0% | 1.0 |
| See-a-doctor combinations + mild look-alikes | dev | 26 | — | — | 0.0% | 100.0% | 1.0 |

- **Last clean held-out measurement (V286, frozen):** urgent caught 57.5% (95% CI 42–71%; 23/40); urgent shown as low 5.0% (95% CI 1–16%; 2/40); keyword baseline 25.0%.
- **After V287 on the same cases (development — misses were inspected):** urgent caught 97.5% (95% CI 87–100%; 39/40), urgent shown as low 0.0%. Not a held-out estimate.
- English development set 100.0%; red-flag rules alone (current) 92.5%. Keyword baseline on denied symptoms: 4/10 false emergency alarms vs 0/10; on Arabizi 0.0%.
- Arabizi layer: urgent caught 0.0% without it → 100.0% with it (very small n).
- By regional vocabulary (code-switching + Arabizi): gulf: 80.0% (n=5), hejazi: 100.0% (n=4), najdi: 100.0% (n=6), southern: 100.0% (n=2).
- Built-in safety suite 47/47; false alarms 0.0%. External sealed set: not collected yet — protocol in `evaluation/EXTERNAL_HELDOUT_PROTOCOL.md`.

### Known limitations
2 of 40 test-set "assess soon" cases are still shown as low (36 before the V286 free-text duration/severity layer); urgent cases are still missed in unseen wording; reference labels await blinded clinician review; all Arabic results are development results; the fever + stiff-neck rule requires a third sign (open clinical question); Arabizi feeds only the concept layer; pediatric cases were written by the author from NICE/NHS warning-sign lists and need clinician labels; no real-user testing (would require ethics-committee approval first).

### Privacy
A guest analysis is never kept as a health record. A minimal anonymous copy (age, gender, symptoms, duration, severity, level — no notes, name, e-mail or IP address) is kept **only** if the visitor opts in to analytics or research, and the consent can be withdrawn. `/live-demo` runs the real engine on four fixed cases and saves nothing.

### Real website path
All cases through `POST /api/analyze` as the browser sends them: same decision as the engine in **525/525**. The AI-reply guard (`answer_guard.py`) corrected **780/780** deliberately dismissive replies.


### Blood reports
55 synthetic reports (development): reports with a critical value shown as urgent/emergency 17.6% in V287 → 100.0% (95% CI 85–100%; 21/21); false critical alarms 0.0% (95% CI 0–10%; 0/34); per-test status 83.6% → 100.0%. Critical limits (`blood_critical.py`) await clinician sign-off.

### Accessibility (automated)
84 checks (21 pages × 2 languages × 2 viewports), axe-core WCAG 2.2 A/AA: 84 without serious violations, contrast issues 0, touch targets under 24 px 0. Manual checks: `ACCESSIBILITY_CHECKLIST_AR.md`.
