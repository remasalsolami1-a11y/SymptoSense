# إعداد Authentication في SymptoSense

## المسارات الفعلية

- مستخدم جديد: `Create Account → Verify Email → Login → /profile`
- مستخدم موجود: `Login → /profile`
- استعادة كلمة المرور: `Forgot Password → Reset Email → Reset Password → Login`
- Admin: `Login → role=admin → /admin`

الحساب الإداري هو الحساب الموجود مسبقًا والمحفوظ في قاعدة البيانات بدور `admin`. ويُستخدم متغير البيئة التالي لتهيئة الحساب أو إصلاح دوره عند الحاجة:

`SYMPTOSENSE_ADMIN_EMAIL=<OWNER_ADMIN_EMAIL>`

لا تحتوي الشفرة على كلمة مرور له، ولا تنشئ بديلًا إذا لم يكن موجودًا. جميع الحسابات الجديدة تُنشأ بدور `user`. في النسخة المصححة، غياب المتغير مؤقتًا لا يحوّل حساب Admin الموجود إلى مستخدم عادي.

## متغيرات Railway المطلوبة — Brevo HTTPS API

أضيفي القيم التالية من Railway → Service → Variables، ثم أعيدي النشر:

```text
BREVO_API_KEY=<BREVO_API_KEY>
BREVO_FROM_EMAIL=remasalsolami1@gmail.com
BREVO_FROM_NAME=SymptoSense
SITE_URL=https://symptosense-production-b2e5.up.railway.app
WEB_SECRET=<LONG_RANDOM_STABLE_SECRET>
SYMPTOSENSE_ADMIN_EMAIL=<OWNER_ADMIN_EMAIL>
SESSION_COOKIE_SECURE=1
ADMIN_AUTH_DEBUG=0
```

`BREVO_API_KEY` مفتاح سري ينشأ من Brevo → SMTP & API → API Keys. لا تضعيه في GitHub أو ترسليه لأي شخص. يجب أن يكون البريد الموجود في `BREVO_FROM_EMAIL` بحالة Verified داخل Brevo.

عند وجود إعداد Brevo كامل يختار التطبيق Brevo تلقائيًا قبل SMTP وResend. يعمل Brevo عبر HTTPS، ولذلك هو الإعداد الموصى به لهذه النسخة على Railway. بعد نجاح اختبار Brevo احذفي متغيرات `SMTP_*` و`RESEND_*` القديمة من Railway لتفادي اختيار مزود مختلف بالخطأ أو تشخيص إعداد غير مقصود.

الكود ما زال يحتفظ بدعم SMTP وResend كتوافق قديم فقط، لكنهما **ليسا إعداد النشر الموصى به في v23**. لا تضعي أي API key أو `WEB_SECRET` في Frontend أو GitHub.

إذا لم تضبطي `SITE_URL`، يستخدم التطبيق `RAILWAY_PUBLIC_DOMAIN` تلقائيًا. ضبطه صراحة بالرابط أعلاه يمنع Redirect URL خاطئًا في رسائل Verification وReset.

## فحص إعداد البريد بعد النشر

بعد الدخول بحساب Admin:

1. افتحي `GET /api/admin/auth-email-status`.
2. يجب أن تكون القيم:
   - `configured: true`
   - `sender_address_valid: true`
   - `production_recipient_delivery_ready: true`
   - `site_url` مساويًا لرابط Railway الحالي.
3. من واجهة Admin أرسلي `POST /api/admin/auth-email-test` مع CSRF الإداري. الرسالة تُرسل إلى بريد Admin الحالي فقط.
4. راجعي Brevo → Transactional → Logs، ثم Inbox وSpam في البريد المستلم.

لا يعرض مسار التشخيص API key أو Password أو Token أو عنوان المرسل الكامل.

أكواد Logs الآمنة:

- `email_not_configured`: متغير مطلوب ناقص.
- `email_api_key_placeholder`: قيمة API key ما زالت مثالًا.
- `email_sender_placeholder`: قيمة sender ما زالت مثالًا.
- `email_invalid_api_key`: مفتاح مزود Resend القديم مرفوض (يظهر فقط إذا استُخدم ذلك المسار الاحتياطي).
- `email_test_domain_restricted`: إعداد Resend القديم يستخدم نطاق اختبار لا يسمح بهذا المستلم.
- `email_sender_domain_unverified`: دومين مرسل Resend القديم غير موثق.
- `email_smtp_not_configured`: أحد متغيرات SMTP المطلوبة ناقص.
- `email_smtp_auth_failed`: Gmail رفض البريد أو App Password.
- `email_smtp_connection_failed`: تعذر الاتصال بخادم SMTP أو TLS.
- `email_smtp_sender_invalid`: صيغة SMTP_FROM غير صحيحة.
- `email_brevo_not_configured`: أحد متغيرات Brevo الثلاثة ناقص.
- `email_brevo_auth_failed`: مفتاح Brevo مرفوض.
- `email_brevo_sender_invalid`: البريد المرسل غير صالح أو غير موثق.
- `email_brevo_rate_limited`: تم بلوغ حد الإرسال.
- `email_brevo_connection_failed`: تعذر الوصول إلى Brevo API.
- `Auth email accepted by provider`: مزود البريد الاحتياطي قبل الطلب؛ راجعي سجلات ذلك المزود إذا لم تظهر الرسالة في Inbox.
- `Auth email accepted by SMTP provider`: Gmail قبل الرسالة للإرسال.

## خصائص الأمان

- الحساب الجديد يبدأ `email_verified=0`، بينما Migration تعتبر الحسابات القديمة موثقة حتى لا تتوقف.
- Verification token عشوائي، مخزن كـSHA-256 hash، صالح 24 ساعة، وأحادي الاستخدام.
- Reset token عشوائي، مخزن كـSHA-256 hash، صالح 30 دقيقة، وأحادي الاستخدام.
- استهلاك أي Reset token يبطل جميع روابط Reset الأخرى للحساب.
- طلبات إعادة الإرسال محدودة بـ60 ثانية بين الطلبات و5 طلبات في الساعة لكل حساب، بغض النظر عن مزود البريد.
- تغيير بريد الحساب غير الموثق يحتاج Pending Verification Session وكلمة المرور الحالية.
- كلمات المرور تستخدم PBKDF2-SHA256 بـ600,000 دورة؛ الحسابات القديمة تستمر وتُرقّى بعد Login صحيح.
- Login/Registration/Verification/Reset HTML Forms محمية بـCSRF.
- الجلسات `HttpOnly` و`SameSite=Lax`، ومع `SESSION_COOKIE_SECURE=1` لا تُرسل إلا عبر HTTPS.
- لا تُعرض أو تُسجل روابط Debug أو Passwords أو raw tokens.

## اختبار القبول على Production

استخدمي بريدًا حقيقيًا تملكينه ونفذي بالترتيب:

1. Create Account، ثم تأكدي أن `/profile` محجوب قبل التحقق.
2. افتحي رسالة Verify واضغطي الرابط؛ المحاولة الثانية للرابط يجب أن تُرفض.
3. سجلي الدخول؛ يجب أن يظهر Toast مرة واحدة ثم يفتح `/profile`.
4. نفذي Forgot Password؛ استخدمي الرابط مرة واحدة، ثم تأكدي أن كلمة المرور القديمة رُفضت والجديدة عملت.
5. سجلي دخول Admin؛ يجب أن يظهر Toast الخاص بريماس ويكون Redirect إلى `/admin`.
6. من User عادي، يجب أن يعيد `/admin` حالة 403، وأن تعيد Admin APIs حالة 403/401.

قبول أي مزود للطلب لا يثبت وحده وصول الرسالة إلى Inbox. في إعداد v23 الموصى به، يكون التحقق النهائي من Brevo → Transactional → Logs ثم من صندوق البريد المستلم.


## Admin 2FA — v32

حساب Admin يستخدم TOTP 2FA بشكل افتراضي. بعد إدخال كلمة المرور الصحيحة في أول دخول بعد التحديث، سيظهر QR لإضافته إلى Google Authenticator أو Microsoft Authenticator أو 1Password. بعد تأكيد أول رمز ستظهر 8 رموز استرداد لمرة واحدة؛ احفظيها خارج الموقع.

المتغير الموصى به في Railway:

```env
ADMIN_2FA_REQUIRED=1
```

يتطلب 2FA وجود `WEB_SECRET` ثابت. يتم تشفير سر TOTP في قاعدة البيانات بمفتاح مشتق من `WEB_SECRET`، لذلك **لا تغيّري WEB_SECRET بعد تفعيل 2FA** إلا ضمن خطة ترحيل/استرداد واضحة.
