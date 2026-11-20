# اختبار Release Candidate النهائي — SymptoSense v37-rc1

## اختبارات آلية قبل النشر
- Python syntax لكل الملفات.
- pytest كامل.
- Service Worker syntax.
- ZIP integrity.
- فحص مسارات التسجيل/التحليل/Admin/Research/Push الموجودة.

## اختبارات حية بعد النشر — يجب تنفيذها على Production
1. تسجيل حساب جديد من بريد حقيقي → وصول OTP → إدخال الرمز → نجاح تسجيل الدخول.
2. Admin > Production Readiness → إرسال Email Test → التأكد من وصوله → الضغط على «وصلتني الرسالة».
3. iPhone Home Screen + Notifications enabled → Test Push → ظهور الإشعار → Production Readiness = verified.
4. Sentry → Safe Test Event → التأكد من وجود Event ID، ثم مراجعة الحدث في Sentry للتأكد من غياب بيانات المستخدم/الصحة.
5. تجميد Research Version قبل بداية جمع بيانات الدراسة.
6. تحليل أعراض عربي: العمر → الأعراض → المتابعة → النتيجة → المصادر.
7. تحليل أعراض إنجليزي بنفس المسار.
8. حالة Red Flag → ظهور توجيه طوارئ قبل الاحتمالات.
9. تصدير Research Excel → 4 أوراق → وجود Study Version/App Version في التحليلات.
10. الأجهزة: iPhone صغير/كبير، Android، iPad، Laptop؛ لا تداخل ولا تمرير مزدوج داخل خطوة التحليل.

> لا يتم إعلان النسخة Public Release قبل نجاح البنود الحية، لأنها تعتمد على Railway، مزود البريد، Sentry، والجهاز الحقيقي.
