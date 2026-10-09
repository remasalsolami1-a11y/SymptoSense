# حزمة المراجعة السريرية — SymptoSense

> **مولَّدة تلقائيًا من الكود** بـ `python tools/clinical_packet.py` — لا تعدّلها يدويًا. تصف **ما يفعله المنتج الآن** ولا تقترح قيمًا طبية.
> لا يوجد أي اعتماد حتى الآن. الاعتماد يُسجَّل فقط ببيانات المراجِع نفسه:
> `python tools/signoff.py approve <area> --reviewer "الاسم" --credentials "الترخيص" --date YYYY-MM-DD --notes "..."`
> كل ملف CSV في `clinical_review/` فيه عمودان فارغان للقرار والملاحظات.

## 4) clinical_reasoning — منطق الصورة السريرية ورفع المستوى
القواعد في `clinical_reasoning.py` (تُرفع المستويات ولا تُخفض أبدًا):
- المستويات بالترتيب: monitor → soon → today → emergency.
- زيادة في الشدة أو عَرَض جديد أو دواء جديد أو تحليل أسوأ ⇒ رفع خطوة واحدة (من monitor/soon فقط).
- تنبيه قياس منزلي «urgent» خلال 24 ساعة ⇒ today كحد أدنى.
- تنبيه قياس منزلي «emergency» ⇒ emergency دائمًا ولا يُخفَّف.

حالات الانحدار الثابتة (المستوى الحالي للمراجعة):
| الحالة | الأعراض | المدخلات | المستوى الحالي | مسار الطوارئ | قرار الطبيب |
|---|---|---|---|---|---|
| knee_click_no_pain | طقطقة الركبة | {"notes": "بدون ألم"} | monitor | لا |  |
| mild_headache | صداع | {} | monitor | لا |  |
| mild_cough | كحة | {} | monitor | لا |  |
| period_nausea | غثيان | {"notes": "مع بداية الدورة الشهرية"} | monitor | لا |  |
| sore_throat | ألم الحلق | {} | monitor | لا |  |
| fainting | إغماء | {"severity": "4"} | emergency | نعم |  |
| chest_pain_severe | ألم في الصدر | {"severity": "5", "notes": "ألم شديد ينتشر للذراع مع تعرق"} | emergency | نعم |  |
| breathing_difficulty | صعوبة في التنفس | {"severity": "5"} | emergency | نعم |  |
| breathing_difficulty_4of5 | صعوبة في التنفس | {"severity": "4"} | today | لا |  |
| sudden_weakness_speech | ضعف مفاجئ في جانب واحد | {"notes": "صعوبة في الكلام"} | emergency | نعم |  |
| suicidal_note | حزن | {"notes": "أفكر أنهي حياتي"} | emergency | نعم |  |
| child_high_fever | حمى | {"age": "1", "severity": "4"} | today | لا |  |
| english_chest_pain | chest pain | {"severity": "5", "notes": "crushing pain, sweating"} | emergency | نعم |  |

تطابق اللقطة المعتمدة مع السلوك الحالي: **نعم**.

> **قرار مفتوح (من نسخة سابقة):** «صعوبة التنفس + شدة 5/5» تُصنَّف طوارئ تعديلًا مؤقتًا من مالك المنتج، و4/5 ⇒ اليوم. يحتاج قرار الطبيب.

---
القرار النهائي بعد المراجعة يُسجَّل فقط عبر `tools/signoff.py approve` ببيانات المراجِع.
