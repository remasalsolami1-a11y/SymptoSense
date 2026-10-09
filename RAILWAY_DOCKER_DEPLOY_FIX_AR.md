# إصلاح نشر Railway — Dockerfile ثابت

تم تحويل إعداد الإنتاج من Nixpacks إلى Dockerfile صريح حتى لا يؤثر وجود `package.json` الخاص باختبارات Playwright على بناء خدمة الويب.

## المتوقع في Railway

عند رفع هذه النسخة يجب أن يظهر في سجل البناء ما يفيد استخدام Dockerfile، ولا يجب أن يظهر أمر `npm install` أو `npm ci` ضمن بناء خدمة SymptoSense.

## إعدادات الإنتاج

- Python 3.12
- تثبيت `requirements.txt` فقط
- تثبيت PostgreSQL client لتوفر `pg_dump` و`pg_restore` للنسخ الاحتياطي
- أمر التشغيل: `python webapp.py`
- Healthcheck: `/health`
- مهلة Healthcheck: 300 ثانية

## ملاحظة

تبقى ملفات Playwright و`package.json` في المشروع لأغراض الاختبار فقط، لكن Dockerfile لا يستخدمها في نشر خدمة الويب.
