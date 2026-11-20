# حزمة المراجعة السريرية — SymptoSense

> **مولَّدة تلقائيًا من الكود** بـ `python tools/clinical_packet.py` — لا تعدّلها يدويًا. تصف **ما يفعله المنتج الآن** ولا تقترح قيمًا طبية.
> لا يوجد أي اعتماد حتى الآن. الاعتماد يُسجَّل فقط ببيانات المراجِع نفسه:
> `python tools/signoff.py approve <area> --reviewer "الاسم" --credentials "الترخيص" --date YYYY-MM-DD --notes "..."`
> كل ملف CSV في `clinical_review/` فيه عمودان فارغان للقرار والملاحظات.

## 8) medication_context — ربط الأدوية بالأعراض والحالات
لا توجد ادعاءات طبية مكتوبة هنا: يُنتَج الربط فقط إذا كان الدواء في كتالوج الأدوية الموثَّق **و**نص تحذيرات الكتالوج نفسه يذكر الفئة. المطلوب من **صيدلاني/طبيب**: مراجعة قوائم الكلمات التي تُطابَق بها الفئات ونافذة «بدأ حديثًا».
| النوع | الفئة | الاسم | كلمات المستخدم | كلمات نص الكتالوج | قرار |
|---|---|---|---|---|---|
| symptom | gi | الأعراض الهضمية | غثيان، قيء، استفراغ، اسهال، إسهال، ألم بطن، الم بطن، ألم المعدة، إمساك، امساك، حرقة، nausea، vomit، diarrhea، stomach، abdominal | هضمي، معدة، غثيان، إسهال، اسهال، قيء، gastro، stomach، nausea، diarrhea، vomit |  |
| symptom | bleeding | النزف | نزيف، كدمات، كدمة، bleeding، bruis | نزيف، bleeding |  |
| symptom | rash | الطفح والحساسية | طفح، حكة، تورم الوجه، rash، itch، hives | طفح، حساسية، rash، allerg |  |
| condition | kidney | الكلى | كلى، كلية، kidney، renal | كلى، كلية، kidney، renal |  |
| condition | liver | الكبد | كبد، liver، hepatic | كبد، liver، hepatic |  |
| condition | pregnancy | الحمل | حمل، حامل، pregnan | حمل، pregnan |  |
| condition | asthma | الربو | ربو، asthma | ربو، asthma |  |
| condition | heart | القلب | قلب، heart، cardiac | قلب، heart، cardiac |  |

نافذة «دواء بدأ حديثًا»: **21 يومًا**.

> **لا تُكتب تداخلات دوائية أو شدّتها من الذاكرة.** مصدرها الوحيد كتالوج مرخّص يراجعه صيدلاني. انظر `MEDICAL_REVIEW_NEEDED.md` للبنود المفتوحة.

---
القرار النهائي بعد المراجعة يُسجَّل فقط عبر `tools/signoff.py approve` ببيانات المراجِع.
