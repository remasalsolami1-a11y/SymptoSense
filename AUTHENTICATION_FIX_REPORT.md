# SymptoSense Authentication Fix Report

Date: 2026-08-29

## المشاكل الموجودة قبل الإصلاح

1. إنشاء الحساب كان يضع `ss_user_id` مباشرة في Session، أي أن المستخدم الجديد يصبح Logged In بدون Email Verification.
2. لم يكن هناك `email_verified` أو `email_verified_at` في `ss_users`.
3. لم يكن هناك جدول أو Token flow للتحقق من البريد.
4. لم يكن هناك Resend Verification أو Change Email للحساب غير الموثق.
5. Login كان يعيد حالة عامة عند الفشل ولم يكن يمنع حسابًا جديدًا غير موثق لأنه لم يكن يوجد Verification state أصلًا.
6. Forgot Password كان موجودًا، لكن إرسال البريد كان اختياريًا ويمكن أن يفشل بصمت إذا لم تُضبط `RESEND_API_KEY` / `RESEND_FROM`.
7. Reset Link لم يكن يتم فحص صلاحيته في GET قبل عرض نموذج كلمة المرور.
8. Password Reset لم يكن يطبق resend throttling.

## التعديلات

### Database

أضيف إلى `ss_users`:

- `email_verified`
- `email_verified_at`

وأضيف جدول:

- `ss_email_verifications`

الحسابات القديمة تحصل على `email_verified = 1` أثناء Migration للحفاظ على التوافق وعدم تعطيلها. الحسابات الجديدة تُنشأ صراحة بـ `email_verified = 0`.

### Registration

- Name + Email + Password + Confirm Password.
- Password minimum: 8 characters for new accounts.
- لا يتم إنشاء Session تسجيل دخول بعد التسجيل.
- يتم إنشاء Verification Token وإرسال الرسالة.
- الانتقال إلى `/verify-email`.

### Verification

- 24-hour expiry.
- Single-use.
- Random `secrets.token_urlsafe(36)` token.
- SHA-256 token hash stored in DB; raw token is never stored.
- Resend cooldown 60 seconds.
- Maximum 5 verification requests/hour/account.
- Change Email متاح فقط للحساب غير الموثق في pending verification session.

### Login

الحالات:

- Missing account → `account_not_found` + Create Account action.
- Wrong password → `incorrect_credentials`.
- Unverified → `verification_required` → Verify Email.
- Verified user → `/profile`.
- Verified Admin → `/admin`.

### Password Reset

- Generic outward response to avoid account enumeration in Forgot Password.
- 30-minute token.
- Single-use with atomic claim before password change.
- Earlier reset links are invalidated.
- 60-second cooldown / 5 requests per hour.
- Passwords continue to use PBKDF2-SHA256; legacy hashes remain supported and are upgraded after successful authentication.

### Route protection

`login_required` and `api_login_required` now require both:

- valid authenticated session
- `email_verified = true`

An unverified session is removed from authenticated state and moved into the pending verification flow.

### Admin

Admin RBAC was preserved. The owner account is not recreated and existing role logic remains unchanged.

## Automated isolated tests performed

Passed:

- New account starts unverified.
- Unverified account cannot authenticate.
- Verification token created and consumed.
- Verification token becomes used.
- Invalid verification token rejected.
- Expired verification token rejected.
- Immediate resend blocked by cooldown.
- Change Email works only before verification.
- Verified account cannot change email through verification flow.
- Missing account returns `account_not_found` at auth core.
- Wrong password returns `incorrect_credentials`.
- Password reset token valid once.
- Used reset token rejected.
- Invalid reset token rejected.
- Expired reset token rejected.
- Existing legacy account remains usable with the same password.
- Legacy password hash upgrades after successful login.
- Existing Admin remains `admin` and verified after migration.
- Existing normal User remains `user` and verified after migration.
- All project Python files pass `py_compile`.
- All 45 `/api/admin/*` endpoints retain backend admin authorization.
- Admin Dashboard JavaScript passes `node --check` after rendering placeholder substitution.

## لم يمكن اختباره داخل بيئة العمل

لا توجد قاعدة بيانات Railway Production داخل ZIP، لذلك لا يمكن التأكد من سجلات المستخدمين الحقيقية من هنا.

كما أن بيئة التنفيذ الحالية لا تحتوي Flask ولا تسمح بتنزيل الحزم من PyPI، لذلك لم يتم تشغيل HTTP Flask test client على المشروع كاملًا. تم اختبار طبقة Database/token/auth state فعليًا على SQLite معزولة، وفحص Python/JS statically.

ولا توجد `RESEND_API_KEY` أو sender domain حقيقي في بيئة الاختبار، لذلك لم يتم إرسال Email حقيقي. Production delivery يتطلب إعداد متغيرات Railway الموضحة في `AUTHENTICATION_SETUP.md`.
