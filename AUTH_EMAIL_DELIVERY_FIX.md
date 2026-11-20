# إصلاح Email Verification وForgot Password

تاريخ المراجعة: 2026-08-29

## الأسباب الفعلية التي عالجها التحديث

1. روابط الرسائل كانت قد تعتمد على Production URL قديم. أصبح البناء بالترتيب: `SITE_URL` ثم `RAILWAY_PUBLIC_DOMAIN` ثم نطاق الطلب في التطوير فقط.
2. إعداد Resend كان يُعتبر مكتملًا حتى لو احتوى `RESEND_FROM` أو `RESEND_API_KEY` على Placeholder. أصبح التطبيق يرفض هذه القيم ويعرض كود تشخيص آمن.
3. `resend.dev` كان يبدو كأنه إعداد Production صالح رغم أنه Test Sender محدود. يعرض تشخيص Admin الآن `production_recipient_delivery_ready=false` لهذه الحالة.
4. كان مسارا تشخيص البريد يستخدمان Admin decorator بطريقة خاطئة، ما كان يسبب Flask endpoint collision عند تحميل التطبيق. تم إصلاحهما ليستخدما Backend RBAC الفعلي.
5. Login لحساب غير موثق كان قد يعيد إرسال Verification تلقائيًا في كل محاولة. أصبح يعرض صفحة التحقق فقط، والإرسال الجديد يتم من زر Resend المحدود.
6. كانت روابط Debug قد تُعرض داخل صفحات Verification/Reset عند تفعيل متغير تطوير. أزيل هذا السلوك بالكامل حتى لا يظهر raw token في الصفحة أو Logs.
7. نماذج Login/Register/Verify/Forgot/Reset أصبحت محمية بـCSRF.
8. تغيير البريد قبل التحقق أصبح يتطلب كلمة المرور الحالية، وليس Pending Session وحدها.
9. فشل مزود البريد أثناء Resend لم يعد يُبطل رابطًا أقدم ما زال صالحًا. عند استهلاك أي رابط بنجاح تُبطل الروابط الأخرى.

## الاختبار الآلي المنفذ

`python -m unittest -v tests/test_authentication.py`

يغطي الاختبار الحقيقي على Flask + SQLite مع استبدال نقل البريد بـin-memory capture:

- إنشاء حساب جديد وحالة Unverified.
- منع Login قبل Verification وعدم إرسال رسالة مكررة تلقائيًا.
- Resend cooldown.
- Verification valid / used / invalid.
- Forgot Password برسالة عامة لا تكشف وجود الحساب.
- Reset valid / expired / invalid / single-use.
- رفض كلمة المرور القديمة وقبول الجديدة.
- استمرار الحسابات القديمة وكلمات مرورها بعد Migration.
- Toast مستخدم وAdmin مرة واحدة فقط.
- Redirect Admin إلى `/admin` وحماية الخادم من User عادي.
- العربية والإنجليزية والمسارات المحمية.
- اكتشاف Placeholder و`resend.dev` في إعداد البريد.

كما مرّت جميع ملفات Python عبر `py_compile`.

## ما لا يمكن إثباته من الحزمة وحدها

لا توجد داخل ZIP أسرار Railway، أو حساب Resend، أو Inbox يمكن الوصول إليه. لذلك يمكن إثبات منطق التطبيق محليًا، لكن لا يمكن الادعاء بوصول رسالة Production قبل:

- نشر هذه النسخة على Railway.
- ضبط القيم الموضحة في `AUTHENTICATION_SETUP.md`.
- تنفيذ Admin email test.
- رؤية `delivered` في Resend ووصول الرسالة إلى البريد المستلم.

لم يتم تغيير أو حذف قاعدة بيانات Production أو المستخدمين الموجودين في هذه الحزمة.
