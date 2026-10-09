# حزمة المراجعة السريرية — SymptoSense

> **مولَّدة تلقائيًا من الكود** بـ `python tools/clinical_packet.py` — لا تعدّلها يدويًا. تصف **ما يفعله المنتج الآن** ولا تقترح قيمًا طبية.
> لا يوجد أي اعتماد حتى الآن. الاعتماد يُسجَّل فقط ببيانات المراجِع نفسه:
> `python tools/signoff.py approve <area> --reviewer "الاسم" --credentials "الترخيص" --date YYYY-MM-DD --notes "..."`
> كل ملف CSV في `clinical_review/` فيه عمودان فارغان للقرار والملاحظات.

## 7) search_base و search_new_v251 — مواضيع البحث
6 موضوعًا جديدًا (V251) و143 أساسيًا، لكل موضوع مصادر ملحقة. ملفان: `search_new_v251.csv` و`search_base.csv` (العمود `sources` يسهّل التحقق من أن النص يطابق المصدر).

---
القرار النهائي بعد المراجعة يُسجَّل فقط عبر `tools/signoff.py approve` ببيانات المراجِع.
