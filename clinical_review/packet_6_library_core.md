# حزمة المراجعة السريرية — SymptoSense

> **مولَّدة تلقائيًا من الكود** بـ `python tools/clinical_packet.py` — لا تعدّلها يدويًا. تصف **ما يفعله المنتج الآن** ولا تقترح قيمًا طبية.
> لا يوجد أي اعتماد حتى الآن. الاعتماد يُسجَّل فقط ببيانات المراجِع نفسه:
> `python tools/signoff.py approve <area> --reviewer "الاسم" --credentials "الترخيص" --date YYYY-MM-DD --notes "..."`
> كل ملف CSV في `clinical_review/` فيه عمودان فارغان للقرار والملاحظات.

## 6) library_core — مكتبة الأعراض والأمراض
158 مرضًا، 290 عرضًا، 23 قاعدة علامات خطر (نصوص عربية في CSV؛ الإنجليزية في قاعدة المعرفة). الملف: `clinical_review/library_core.csv`.

---
القرار النهائي بعد المراجعة يُسجَّل فقط عبر `tools/signoff.py approve` ببيانات المراجِع.
