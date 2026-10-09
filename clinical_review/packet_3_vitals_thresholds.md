# حزمة المراجعة السريرية — SymptoSense

> **مولَّدة تلقائيًا من الكود** بـ `python tools/clinical_packet.py` — لا تعدّلها يدويًا. تصف **ما يفعله المنتج الآن** ولا تقترح قيمًا طبية.
> لا يوجد أي اعتماد حتى الآن. الاعتماد يُسجَّل فقط ببيانات المراجِع نفسه:
> `python tools/signoff.py approve <area> --reviewer "الاسم" --credentials "الترخيص" --date YYYY-MM-DD --notes "..."`
> كل ملف CSV في `clinical_review/` فيه عمودان فارغان للقرار والملاحظات.

## 3) vitals_thresholds — حدود تنبيهات القياسات المنزلية
الجداول **مستخرجة بتشغيل `vitals.assess` فعليًا** (السلوك الحالي)، وليست مقترحات. المطلوب: هل كل حد ومستوى ورسالة مقبول؟
| النوع | السياق | المدى | المستوى |
|---|---|---|---|
| glucose | random | 20 – 53 mg/dL | emergency |
| glucose | random | 54 – 69 mg/dL | attention |
| glucose | random | 70 – 199 mg/dL | ok |
| glucose | random | 200 – 300 mg/dL | attention |
| glucose | random | 301 – 800 mg/dL | urgent |
| glucose | fasting | 20 – 53 mg/dL | emergency |
| glucose | fasting | 54 – 69 mg/dL | attention |
| glucose | fasting | 70 – 125 mg/dL | ok |
| glucose | fasting | 126 – 300 mg/dL | attention |
| glucose | fasting | 301 – 800 mg/dL | urgent |
| glucose | after_meal | 20 – 53 mg/dL | emergency |
| glucose | after_meal | 54 – 69 mg/dL | attention |
| glucose | after_meal | 70 – 199 mg/dL | ok |
| glucose | after_meal | 200 – 300 mg/dL | attention |
| glucose | after_meal | 301 – 800 mg/dL | urgent |
| temp |  | 33 – 34.9 °C | urgent |
| temp |  | 35 – 37.9 °C | ok |
| temp |  | 38 – 39.9 °C | attention |
| temp |  | 40 – 43 °C | urgent |
| pulse |  | 20 – 39 bpm | urgent |
| pulse |  | 40 – 49 bpm | attention |
| pulse |  | 50 – 100 bpm | ok |
| pulse |  | 101 – 130 bpm | attention |
| pulse |  | 131 – 250 bpm | urgent |
| spo2 |  | 50 – 89 % | emergency |
| spo2 |  | 90 – 94 % | urgent |
| spo2 |  | 95 – 100 % | ok |
| bp (systolic, diastolic=70) |  | 60 – 89 mmHg systolic | attention |
| bp (systolic, diastolic=70) |  | 90 – 139 mmHg systolic | ok |
| bp (systolic, diastolic=70) |  | 140 – 179 mmHg systolic | attention |
| bp (systolic, diastolic=70) |  | 180 – 260 mmHg systolic | urgent |
| bp (diastolic, systolic=110) |  | 30 – 59 mmHg diastolic | attention |
| bp (diastolic, systolic=110) |  | 60 – 89 mmHg diastolic | ok |
| bp (diastolic, systolic=110) |  | 90 – 119 mmHg diastolic | attention |
| bp (diastolic, systolic=110) |  | 120 – 160 mmHg diastolic | urgent |

**نصوص الرسائل** (AR/EN) لكل نوع في `vitals.assess` — راجعها في `vitals.py` (الدالة `assess`)؛ تتضمن تعليمات (إسعاف 997، سكر سريع المفعول، إعادة القياس). تأكد من سلامة كل تعليمة.

---
القرار النهائي بعد المراجعة يُسجَّل فقط عبر `tools/signoff.py approve` ببيانات المراجِع.
