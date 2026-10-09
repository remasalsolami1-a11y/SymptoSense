# بنية الكود (V261)

`webapp.py` كان ملفًا واحدًا (~1.93 MB، 23,878 سطر). صار نواةً صغيرة (التهيئة، الأمان، الـ hooks، المسارات الأساسية) والباقي في:

| المجلد | المحتوى |
|---|---|
| `routes/` | المسارات حسب المجال: `auth`، `admin`، `labs`، `medications`، `assistant`، `tracking`، `pages` (+ `vitals.py` و`followup.py` و`health_file.py` في الجذر) |
| `pagelib/` | بُناة صفحات HTML الكبيرة (`pages_html.py`) |
| `services/` | منطق الأعمال بلا Flask: `search_answers.py`، و`medication_service.py` (المسار → الخدمة → الاستمرارية) |
| `static/js/chat/` | سلوك صفحة الشات (8 ملفات تُحمَّل بترتيب ثابت، انظر أدناه) |
| `inline_assets/` | CSS/HTML/JSON الكبيرة التي كانت نصوصًا داخل `webapp.py` |

## كيف تعمل الوحدات المنقولة
- كل وحدة تعلن `DEPS` (الأسماء التي تأخذها من `webapp.py`) وتُحقن عند الإقلاع عبر `routes/_inject.py`. الدوال تُحقن كوكلاء يبحثون في `webapp` وقت الاستدعاء، فيبقى `mock.patch.object(webapp, ...)` يعمل.
- المزخرفات (`login_required`، `admin_api_required(...)`) تُطبَّق وقت التسجيل بنفس الترتيب الأصلي؛ أسماء الـ endpoints لم تتغير.
- الخريطة العامة محروسة بـ `route_map_baseline.json` و`test_routes_split.py`.

## نقل مجموعة جديدة
`python tools/extract_routes.py GROUP --prefix /api/xxx` (مسارات) أو `--package pagelib --helpers name1 name2` (دوال عادية)، ثم `python tools/fix_route_exports.py --apply` و`python tools/check_routes_modules.py`.

## قواعد
- لا مسارات جديدة في `webapp.py` (الحارس: ≤ 70 مسارًا، < 6500 سطر، < 400 KB).
- الاختبارات التي تقرأ الشيفرة نصيًا تستخدم `source_bundle.py` فلا ترتبط بمكان الملف.

## صفحة الشات (V261)
`chat_view.py` (373 KB → ~48 KB) يبني الصفحة فقط: الترجمات + HTML + سكربت صغير يمرّر بيانات الصفحة (`T`, `LANG`, `SYMS`, `DURS`, `SEVS`, `CONDS`, `REL`, `DEMO_RESULT`). السلوك في `static/js/chat/` وتُحمَّل بهذا الترتيب بالضبط (نصوص كلاسيكية تشارك النطاق العام، فالترتيب جزء من العقد):

`chat-core` ← `assistant` ← `symptom-flow` ← `red-flags` ← `followup` ← `data-quality` ← `analysis-result` ← `result-tracking` ← `result-actions` ← `doctor-summary` ← `chat-boot`

- `chat-core`: الحالة، عناصر DOM، عرض الرسائل، المسودة، الأفراد، `startChat`.
- `assistant`: القراءة الصوتية والإدخال الصوتي.
- `symptom-flow`: خريطة الجسم، أسئلة التوضيح، المدة/الشدة/التاريخ.
- `red-flags`: فحص العلامات الحمراء وشاشة الطوارئ.
- `followup`: أسئلة التمييز والمتابعة بعد النتيجة.
- `analysis-result`: بوابة جودة البيانات، تشغيل التحليل، عرض النتيجة.
- `doctor-summary`: ملخص الطبيب ونص الاتصال والتسليم.
- `chat-boot`: ربط الأحداث و`startChat()` (يجب أن يكون آخر ملف).
`test_chat_scripts_split.py` يحرس الترتيب، وأن كل ملف صالح لوحده (`node --check`)، وعدم تكرار أي تعريف عام، وأن ربط الأحداث لا يعمل قبل اكتمال التحميل. تحميل الملفات يتم من `chat_view.py` (لا من `PAGE_FRAME.html` لأنه إطار كل الصفحات).

## الخدمات (route ← service ← persistence)
`services/medication_service.py` يحمل قواعد التذكيرات (التحقق، الملكية، الأخطاء) ويُرجع قواميس أو يرفع `MedicationError(code, status)`؛ لا يستورد Flask. `routes/medications.py` يقرأ الطلب ويستدعي الخدمة ويضيف الرؤوس. الخطوة التالية لهذا النمط: `repositories/medication_repository.py` بدل النداء المباشر لـ `medication_email`/`db`.

## `routes/_inject.py` (مرحلي)
الحقن من `webapp.globals()` حلّ انتقالي يحفظ التوافق مع الاختبارات. كلما انتقلت ميزة إلى خدمة مستقلة قلّت أسماؤها في `DEPS` (الأدوية: 13 → 11 ولا يمر منها أي منطق). تنبيه: القيم غير الدوال تُحقن مرة واحدة عند التسجيل، لذا يمنع `test_routes_split` أي اسم يعيد `webapp.py` ربطه (`global`) من أن يكون في `DEPS` — يُقرأ عبر دالة.

## الأحداث في الواجهة (V262)
لا `on*` inline. استخدم `data-ss-click="fn"` (+ `data-ss-args='["a"]'`). الدالة يجب أن تكون عالمية ومدرجة في `ALLOWED_CALLS` داخل `static/js/interaction-bridge.js` (والنسخة الجذرية). `test_frontend_guards.py` يمنع عودة `on*` ويضع سقفًا لحجم ملفات `static/js/chat/`.

## لوحة ملفي (V263)
route (`webapp.user_profile_page`) ← `ProfileDashboardService` (تجميع قراءة فقط عبر `ProfileSources`) ← `pagelib/profile_dashboard_html.py` (رسم). الصفحة لا تتصل بأي نظام مباشرة. قاعدة ثابتة: لا قيمة طبية ولا مستوى قرار في المخرجات، والتنبيهات من `ALLOWED_ALERT_CODES` فقط.

## V265 — سكربتات الشات
الترتيب: chat-core, assistant, body-map, clarifications, symptom-flow, red-flags, followup, data-quality, analysis-result, result-tracking, result-actions, doctor-summary, chat-boot (نطاق عام مشترك، تحميل متزامن). الحالة المشتركة (`selectedBodyZone`، `clarQueue`) معرّفة في body-map/clarifications وتُقرأ وقت الاستدعاء.
