# قائمة تشغيل الإنتاج — SymptoSense

كل بند هنا يتطلب **وصولك إلى Railway** ولا يمكن إنجازه من الكود. للتحقق من الحالة في أي وقت داخل بيئة الإنتاج:

```bash
python tools/prod_readiness_check.py   # يطبع MISSING/OK دون إظهار أي قيمة سرية
```

## 1) متغيرات البيئة (Railway → Variables)
| المتغير | الغرض |
|---|---|
| `DATABASE_URL` | قاعدة PostgreSQL |
| `WEB_SECRET` | توقيع الجلسات؛ ثابت وقوي |
| `HASH_SALT` | ثابت؛ لا يُغيَّر بعد وجود بيانات |
| `SYMPTOSENSE_ADMIN_EMAIL` | بريد مالك الأدمن (للترقية/الاستعادة التلقائية للمالك) |
| `BACKUP_SCHEDULER_ENABLED=1` · `BACKUP_DIR=/data/backups` · `BACKUP_ENCRYPTION_KEY` | النسخ المشفر المجدول (Volume على `/data`) |
| `RESTORE_TEST_DATABASE_URL` | قاعدة **منفصلة** لاختبار الاستعادة (ليست الإنتاج) |

## 2) إثبات النسخ الاحتياطي (Backup → Verify → Restore test)
```bash
python backup_restore.py generate-key      # مرة واحدة، يُحفظ في Variables فقط
python backup_restore.py backup
python backup_restore.py verify
python backup_restore.py restore-test      # على RESTORE_TEST_DATABASE_URL فقط
python backup_restore.py status            # المطلوب: "ready": true
```
التفاصيل الكاملة: `BACKUP_RESTORE_SETUP_AR.md`. كرري `restore-test` دوريًا (النافذة `RESTORE_TEST_MAX_AGE_DAYS`).

## 2.1) المراقبة
- `SENTRY_DSN` (اختياري لكنه موصى به): تنبيه عند الأخطاء. الكود يمسح البيانات الحساسة قبل الإرسال (`_scrub_sentry_event`).
- أضيفي مراقب توفّر خارجيًا (UptimeRobot أو Better Stack) على `https://<نطاقك>/healthz` كل دقيقة، وعلى `/readyz` للفحص الصارم.
- كل خطأ 500 يعرض للمستخدم Request ID ويسجَّل بنفس المعرّف للبحث عنه في السجلات.

## 3) بوابة الإطلاق
1. `python tools/clinical_packet.py` ثم تسليم `CLINICAL_REVIEW_PACKET_AR.md` و`clinical_review/*.csv` للمراجِع.
2. بعد قرار المراجِع فقط: `python tools/signoff.py approve <area> --reviewer ... --credentials ... --date ...` (ينفذه المراجِع أو يُسجَّل بياناته هو).
3. `python tools/signoff.py check --strict` يجب أن يمر.
4. `RELEASE_TARGET=production python release_check.py` يجب أن يمر.

## 4) GitHub
فعّلي Branch protection → *Require status checks*: `tests` و`browser` (من `.github/workflows/ci.yml`)، وراجعي أول تشغيل فعلي لـ CI.
