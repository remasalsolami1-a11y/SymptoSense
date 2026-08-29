# تقرير إصلاح Authentication

التاريخ: 2026-08-29

## النتيجة

أصبح تدفق الحساب في الكود مرتبطًا فعليًا بـFrontend وFlask وDatabase وResend transport:

- Account جديد لا يحصل على جلسة Login قبل Verification.
- Verification وReset tokens عشوائية، مخزنة كـhash، مؤقتة وأحادية الاستخدام.
- Resend Verification محدود بـ60 ثانية و5 طلبات/ساعة.
- Forgot Password يعرض رسالة عامة تمنع كشف وجود الحساب.
- Login يميز في الواجهة بين الحساب المفقود، البيانات الخاطئة، والحساب غير الموثق حسب المطلوب.
- Login الناجح يعرض Toast داخل الموقع مرة واحدة؛ Admin يذهب إلى `/admin` وUser إلى وجهته الخاصة.
- `login_required` و`api_login_required` يرفضان الحساب المحذوف/المعطل وغير الموثق.
- `/profile` و`/my-results` و`/health-report` محمية من الخادم.
- Admin APIs محمية بالجلسة والدور وCSRF؛ المستخدم العادي لا يكفيه معرفة الرابط.

## إصلاحات إضافية اكتُشفت أثناء الفحص

- إصلاح Admin decorator لمساري Email Diagnostics؛ الخطأ السابق كان يمنع تحميل Flask بسبب endpoint duplicate.
- منع تغيير البريد في Pending Verification Session بدون كلمة المرور الحالية.
- إزالة عرض روابط Verification/Reset الخام من صفحات Debug.
- منع Placeholder في `RESEND_API_KEY` و`RESEND_FROM` من أن يظهر كإعداد صالح.
- إضافة تشخيص آمن يفرق بين Test Sender وبين Sender جاهز لمستلمي Production.
- عدم إبطال رابط سابق صالح إذا فشل مزود البريد في إرسال Resend جديد.
- الحفاظ على كلمات مرور وحسابات المستخدمين القديمة؛ Migration يضيف Verification status بقيمة متوافقة.

## الاختبار

الملف: `tests/test_authentication.py`

تم تمرير:

- New account / unverified login / verify / replay rejection.
- Resend cooldown.
- Missing account / wrong password.
- Forgot / reset / expired / invalid / single use.
- Old password rejected and new password accepted.
- Existing legacy account migration without changing its password hash.
- User Toast and Admin Toast shown once.
- Admin redirect and Backend RBAC.
- Arabic/English auth pages and protected route redirects.
- Provider configuration diagnostics.
- Python compilation.

## حدود التحقق من Production

تعذر فتح نطاق Railway من بيئة الفحص، ولا تحتوي الحزمة على صلاحية Railway أو Resend أو Inbox. لذلك لم يتم ادعاء إرسال رسالة حقيقية. يلزم نشر النسخة وضبط المتغيرات ثم إجراء قبول Production من `AUTHENTICATION_SETUP.md`.
