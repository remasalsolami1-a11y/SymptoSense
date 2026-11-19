# evaluation/ — قياس دقة محرك الفرز

| الملف | المحتوى |
|---|---|
| `arabic_cases.json` | 40 حالة بالفصحى واللهجة السعودية (ترجمة لحالات التطوير) + 10 حالات نفي |
| `results/results.json` | نتائج الإصدار الحالي (كل الظروف × كل البدائل) |
| `results/baseline_v283.json` | نفس التقييم على الإصدار السابق (للمقارنة قبل/بعد) |
| `results/severity_sweep.json` | تجربة أثر الشدة 1–5 |
| `results/misses.csv` | كل حالة اختلف فيها النظام عن المرجع |
| `results/report.html` | التقرير المرئي (يُولَّد من الملفات أعلاه) |
| `doctor_review.csv` | حزمة المراجعة العمياء للطبيب (معرّفات محايدة R001…) |
| `doctor_review_key.csv` | مفتاح ربط R001… بالحالات — **لا يُرسل للطبيب** |
| `DOCTOR_REVIEW_INSTRUCTIONS.md` | تعليمات الطبيب |
| `code_switching_cases.json` | V285: 24 خليط عربي/إنجليزي + 8 عربيزي، موسومة بالمنطقة (مجموعة تطوير) |
| `EXTERNAL_HELDOUT_PROTOCOL.md` | بروتوكول مجموعة الاختبار الخارجية المختومة + `external_heldout_scenarios.csv` (للكتّاب) و`external_heldout_labels.csv` (لا يُعطى للكتّاب) و`external_heldout_template.csv` |
| `results/accessibility.json` | نتائج `tools/accessibility_audit.py` |

## التشغيل
```bash
python tools/evaluate_engine.py --out evaluation/results
python tools/evaluate_engine.py --severity-sweep --out evaluation/results
python tools/evaluation_report.py
```

## بعد مراجعة الطبيب
احفظي الملف المعبّأ باسم `evaluation/doctor_labels.csv` ثم:
```bash
python tools/doctor_review_packet.py check
python tools/evaluate_engine.py --out evaluation/results && python tools/evaluation_report.py
```
يصبح تصنيف الطبيب هو المرجع، ويُحسب اتفاقه مع التصنيفات الأولية (Cohen's kappa).

## قاعدة منهجية مهمة
`en_test` (120 حالة) **مجموعة اختبار مخفية**: لا تعدّلي القواعد بناءً على صفوفها في `misses.csv`.
لو عدّلتِ بناءً عليها تصبح مجموعة تطوير، وتحتاجين مجموعة اختبار جديدة لم تُفحص (يُفضّل أن يكتبها شخص آخر).
