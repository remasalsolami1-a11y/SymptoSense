# SymptoSense — النسخ الاحتياطي المشفر واختبار الاستعادة

هذه الآلية مخصصة لقاعدة بيانات الإنتاج ولا تعرض ملفات النسخ الاحتياطي من أي صفحة HTTP.

## 1) الإعداد على Railway

أضيفي Volume دائمًا إلى **خدمة الويب نفسها** واجعلي **Mount Path = `/data`** (لا `/srv/symptosense` ولا `/app`) ثم اضبطي:

```text
BACKUP_SCHEDULER_ENABLED=1
BACKUP_DIR=/data/backups
BACKUP_ENCRYPTION_KEY=<FERNET KEY>
BACKUP_INTERVAL_HOURS=24
BACKUP_KEEP_COUNT=7
BACKUP_MAX_AGE_HOURS=30
```

ولإنشاء مفتاح تشفير مستقل مرة واحدة:

```bash
python backup_restore.py generate-key
```

احفظي المفتاح في Railway Variables فقط. لا تضعيه داخل GitHub ولا تستخدمي `WEB_SECRET` بدلًا منه.

النسخة تستخدم `pg_dump` بصيغة PostgreSQL custom ثم تشفّر الملف قبل الاحتفاظ به. ملفات النسخ والصلاحيات المحلية تُنشأ بوضع مقيد، ولا يطبع الكود `DATABASE_URL` أو محتوى قاعدة البيانات في السجلات.

## 2) التحقق من النسخة

يدويًا:

```bash
python backup_restore.py backup
python backup_restore.py verify
python backup_restore.py status
```

لو `BACKUP_SCHEDULER_ENABLED=1` فخدمة الويب تنشئ النسخة وتتحقق منها دوريًا تلقائيًا.

## 3) اختبار Restore حقيقي

أنشئي قاعدة PostgreSQL **منفصلة تمامًا عن قاعدة الإنتاج**، ثم ضعي رابطها فقط في:

```text
RESTORE_TEST_DATABASE_URL=postgresql://...
RESTORE_TEST_MAX_AGE_DAYS=14
```

ثم:

```bash
python backup_restore.py restore-test
```

الكود يرفض تنفيذ الاختبار إذا كان رابط قاعدة الاختبار مطابقًا لقاعدة الإنتاج. اختبار الاستعادة يتحقق من وجود الجداول الحرجة بعد الاسترجاع.

> لا تعيدي الاستعادة إلى `DATABASE_URL` الخاص بالإنتاج من هذا السكربت. الهدف هو إثبات أن النسخة قابلة للاسترجاع في قاعدة معزولة.

## 4) لوحة Admin

`Production Readiness` لا تعتبر وجود تاريخ يدوي دليلًا على النسخ الاحتياطي. تعرض الآن حالة آخر Backup، التحقق من الملف، وآخر Restore Test. الحالة تصبح جاهزة فقط عندما تكون النسخة حديثة واختبار الاستعادة حديثًا.
