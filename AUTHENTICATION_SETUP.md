# SymptoSense Authentication Setup

## ما تم إصلاحه

تم تحويل مسار الحسابات الجديدة إلى:

Create Account → Verify Email → Login → User/Admin Dashboard

المستخدمون الموجودون قبل هذا التحديث لا يتم حذفهم أو تغيير كلمات مرورهم. Migration تضيف `email_verified` و`email_verified_at` بطريقة محافظة، وتعتبر الحسابات القديمة موثقة حتى تستمر بالعمل.

## إعداد البريد المطلوب على Railway

نظام التحقق واستعادة كلمة المرور يستخدم Resend عبر HTTPS API. أضف المتغيرات التالية في Railway Variables:

```text
RESEND_API_KEY=re_xxxxxxxxx
RESEND_FROM=SymptoSense <noreply@YOUR_VERIFIED_DOMAIN>
SITE_URL=https://YOUR-CURRENT-RAILWAY-DOMAIN   # optional on Railway; auto-detected from RAILWAY_PUBLIC_DOMAIN if omitted
WEB_SECRET=<LONG_RANDOM_STABLE_SECRET>
SESSION_COOKIE_SECURE=1
AUTH_EMAIL_DEBUG=0
```

### مهم

- يجب أن يكون الدومين المستخدم في `RESEND_FROM` مضافًا وموثقًا في Resend للإرسال في Production.
- `SITE_URL` إذا وضعته يجب أن يكون رابط الموقع الحالي بالضبط. في النسخة الحالية، إذا تركته فارغًا على Railway سيستخدم النظام `RAILWAY_PUBLIC_DOMAIN` تلقائيًا بدل رابط قديم ثابت.
- إذا كان `RESEND_FROM` يستخدم `@resend.dev` فهو مناسب للاختبار فقط، وعادةً لا يرسل إلى مستخدمين آخرين غير بريد حساب Resend. لإرسال Verification/Reset لكل المستخدمين، وثّق Domain في Resend واستخدم عنوانًا منه.
- لا تضع `RESEND_API_KEY` أو `WEB_SECRET` في Frontend أو GitHub.
- اترك `AUTH_EMAIL_DEBUG=0` في Production. القيمة `1` مخصصة للتطوير المحلي فقط وتعرض رابط الاختبار داخل الصفحة ولا تطبعه في logs.

## سلوك Email Verification

- الحساب الجديد يبدأ `email_verified = 0`.
- رابط التحقق عشوائي، ولا يُخزن Token الخام في قاعدة البيانات؛ المخزن هو SHA-256 hash فقط.
- الرابط صالح 24 ساعة.
- الرابط Single-use.
- Resend Verification محمي بـ cooldown 60 ثانية وبحد 5 طلبات/ساعة لكل حساب.
- تغيير البريد مسموح فقط للحساب غير الموثق ومن جلسة التسجيل/التحقق نفسها.

## Password Reset

- الرسالة العامة لا تكشف هل البريد لديه حساب أم لا.
- الرابط عشوائي وغير قابل للتخمين، والمخزن في DB هو hash فقط.
- الصلاحية 30 دقيقة.
- Single-use، وعند نجاح Reset تُبطل جميع روابط Reset الأخرى للحساب.
- لا يتم تسجيل Password أو Reset Token في logs.

## Admin

الحساب الإداري يبقى الحساب الموجود مسبقًا:

`remasalsolami2020@gmail.com`

لا يتم إنشاء بديل له. الحسابات القديمة تعتبر Verified عند Migration؛ لذلك لا يتوقف Admin بسبب إضافة Email Verification.

## فحص Production بعد النشر

1. أنشئ حساب User جديد ببريد تملكه.
2. تأكد أن `/profile` لا يفتح قبل التحقق.
3. افتح رسالة Verify Email واضغط الرابط.
4. سجل الدخول وتأكد أن User يذهب إلى `/profile`.
5. جرّب Forgot Password وتأكد أن Reset Link يصل ويعمل مرة واحدة فقط.
6. سجل الدخول بحساب Admin الموجود وتأكد أنه يذهب إلى `/admin`.
7. تأكد أن User العادي يحصل على 403 عند محاولة `/admin` أو Admin APIs.


## تشخيص Email Verification / Forgot Password

بعد تسجيل الدخول بحساب Admin افتح:

```text
/api/admin/auth-email-status
```

لا يعرض هذا المسار API key أو أي token. يعرض فقط هل إعداد البريد مكتمل، مصدر رابط الموقع، وهل المرسل ما زال يستخدم `resend.dev`.

ولإرسال رسالة اختبار إلى بريد حساب الـAdmin الحالي فقط:

```text
POST /api/admin/auth-email-test
```

في Railway Logs ابحث عن أحد الأكواد الآمنة التالية:

- `email_not_configured` → متغيرات Resend ناقصة.
- `email_invalid_api_key` → مفتاح API غير صالح.
- `email_test_domain_restricted` → تستخدم مرسل Resend التجريبي ولا يمكنه الإرسال لكل المستخدمين.
- `email_sender_domain_unverified` → الدومين الموجود في `RESEND_FROM` غير موثق.
- `Auth email accepted by provider` → Resend قبل الرسالة، وبعدها راجع Resend Email Logs/Spam إن لم تصل.
