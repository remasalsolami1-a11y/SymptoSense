# SymptoSense — Email Verification & Password Reset Delivery Fix

## السبب الذي تم إصلاحه في الكود

كان `_site_url()` يستخدم رابطًا افتراضيًا ثابتًا قديمًا:

`https://symptosense.up.railway.app`

بينما خدمة المشروع الحالية تستخدم نطاق Railway مختلفًا. إذا لم يكن `SITE_URL` مضبوطًا، تصل رسالة Verification/Reset برابط إلى Deployment خاطئ.

تم تغيير بناء الروابط إلى الترتيب التالي:

1. `SITE_URL` إن كان مضبوطًا.
2. `RAILWAY_PUBLIC_DOMAIN` الذي توفره Railway تلقائيًا.
3. نطاق الطلب الحالي عند التطوير.
4. `localhost` فقط كـfallback محلي.

لم يعد هناك نطاق Production ثابت داخل الكود.

## تحسين تشخيص Resend

لم يعد Log يكتفي بـHTTP status فقط. أصبح يصنف الأخطاء بدون تسجيل البريد أو Password أو Verification/Reset token:

- invalid API key
- Resend test-domain restriction
- unverified sender domain
- validation/provider error

وأضيف Admin-only diagnostics:

- `GET /api/admin/auth-email-status`
- `POST /api/admin/auth-email-test`

## ما تم اختباره محليًا

- إنشاء User جديد: `email_verified=false`.
- Login قبل التحقق: `verification_required`.
- Verification token: valid → single-use → used.
- Login بعد التحقق: يعمل.
- Password reset token: valid → reset → used.
- كلمة المرور القديمة بعد Reset: مرفوضة.
- كلمة المرور الجديدة: تعمل.
- Python compilation للملفات المعدلة.

## ما يتطلب إعداد Production خارجي

إرسال الرسائل الفعلي يعتمد على Resend ولا يمكن ضمانه من الكود إذا كانت Variables أو Domain غير مضبوطة. يلزم في Railway:

- `RESEND_API_KEY`
- `RESEND_FROM`
- `WEB_SECRET`
- `SESSION_COOKIE_SECURE=1`

ولإرسال البريد إلى حسابات عامة يجب أن يستخدم `RESEND_FROM` Domain موثق في Resend.
