# مراجعة الحالات — تعليمات للطبيب المراجِع / Reviewer instructions

لكل حالة، اختر مستوى الرعاية المناسب **لشخص بالغ يصف هذه الأعراض الآن**، بناءً على النص وحده:

| القيمة في عمود doctor_label | المعنى |
|---|---|
| `high` | طوارئ الآن: اتصل بالإسعاف 997 أو توجّه للطوارئ فورًا |
| `medium` | يحتاج تقييمًا طبيًا خلال 24–48 ساعة (موعد عاجل / عيادة) |
| `low` | رعاية ذاتية ومراقبة، مع معرفة متى تعود |

- اكتب القيمة بالإنجليزية كما في الجدول (high / medium / low).
- لا توجد إجابة من النظام في هذا الملف عمدًا (مراجعة عمياء).
- إذا كانت الحالة غامضة، اختر المستوى الأكثر أمانًا واكتب السبب في `doctor_note`.
- الوقت المتوقع: 20–30 ثانية لكل حالة.

For each case choose the appropriate level of care for an adult describing these symptoms now:
`high` = emergency now (call 997 / ER), `medium` = medical assessment within 24–48 h, `low` = self-care and monitoring.
The file intentionally contains no system output (blinded review).
