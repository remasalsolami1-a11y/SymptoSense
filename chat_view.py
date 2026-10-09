"""Symptom-analysis chat view.

Extracted from the Flask application so the largest interactive page can evolve
without turning the routing/security module back into a monolith.
"""

CHAT = {
    "ar": {
        "me": "👤 أنا",
        "voice_mode_on": "🎙️ المحادثة الصوتية: مفعلة",
        "voice_mode_off": "🎙️ المحادثة الصوتية: متوقفة",
        "voice_mode_title": "المحادثة الصوتية: يستمع المساعد ثم يقرأ الرد بصوت عالٍ",
        "voice_listening": "🎧 جاري الاستماع...",
        "voice_processing": "⏳ جاري المعالجة...",
        "voice_speaking_state": "🔊 جاري القراءة...",
        "welcome": "🩺 مرحبًا بك في SymptoSense",
        "head_p": "مساعدك الذكي لفهم الأعراض الصحية",
        "muted": "يقدم SymptoSense معلومات وإرشادًا أوليًا، ولا يُعد تشخيصًا طبيًا أو بديلًا عن التقييم الطبي عند الحاجة.",
        "speak_on": "🔊 القراءة بصوت عالٍ: مفعلة", "speak_off": "🔊 القراءة بصوت عالٍ: متوقفة",
        "speak_title": "القراءة بصوت عالٍ: يقرأ SymptoSense النص لك",
        "input_ph": "اكتب هنا...", "send": "إرسال", "mic_title": "إدخال صوتي",
        "age": "كم عمرك؟ (اكتب الرقم فقط) 🧒👵", "age_ph": "مثال: 28",
        "age_invalid": "يرجى إدخال عمر صحيح بين 1 و 120.",
        "gender": "ما جنسك؟", "male": "👨 ذكر", "female": "👩 أنثى",
        "syms_f": "ما الأعراض الموجودة؟ اختر عرضًا أو أكثر. وإذا لم يظهر العرض المطلوب، يمكن كتابته في صندوق الإدخال. عند الانتهاء اختر: ✅ انتهيت",
        "syms_m": "ما الأعراض الموجودة؟ اختر عرضًا أو أكثر. وإذا لم يظهر العرض المطلوب، يمكن كتابته في صندوق الإدخال. عند الانتهاء اختر: ✅ انتهيت",
        "write_yourself": "✍️ اكتب عرضاً بنفسك",
        "sym_ph": "مثال: ألم في الساق",
        "custom_f": "لم يظهر العرض المطلوب؟ يمكن كتابته هنا:",
        "custom_m": "لم يظهر العرض المطلوب؟ يمكن كتابته هنا:",
        "atleast_f": "اختر عرضًا واحدًا على الأقل قبل المتابعة.",
        "atleast_m": "اختر عرضًا واحدًا على الأقل قبل المتابعة.",
        "done": "✅ انتهيت", "chosen": "✅ تم اختيار: ",
        "added_f": "✅ أُضيف العرض. اختر ✅ انتهيت عند الاكتفاء أو أضف المزيد.",
        "added_m": "✅ أُضيف العرض. اختر ✅ انتهيت عند الاكتفاء أو أضف المزيد.",
        "start_sub": "مساعدك الذكي لفهم الأعراض الصحية",
        "start_desc": "سأطرح عليك بعض الأسئلة عن الأعراض التي تشعر بها لمساعدتك في الحصول على تقييم أولي آمن وسهل.",
        "syms_q": "ما الأعراض التي تشعر بها؟",
        "syms_more": "هل لديك أعراض أخرى؟",
        "syms_hint": "اكتب الأعراض بالتفصيل، مثل: «أشعر بصداع شديد في الجهة اليمنى مع غثيان منذ يومين»",
        "write_yourself_n": "✍️ اكتب الأعراض بنفسك",
        "custom_n": "اكتب الأعراض هنا (أو استخدم الإدخال الصوتي 🎤):",
        "added_n": "✅ أُضيف العرض. أضف المزيد ثم اضغط «ابدأ التقييم».",
        "atleast": "اختر عرضًا واحدًا على الأقل قبل البدء.",
        "start_btn": "ابدأ التقييم ←",
        "for_whom": "لمن تريد إجراء التحليل؟",
        "me_short": "👤 أنا",
        "yrs": "سنة",
        "person_badge": "التحليل لـ: ",
        "result_card_title": "📋 نتيجة التحليل",
        "result_disclaimer": "⚠️ هذا التقييم لا يُعد تشخيصًا طبيًا، ولا يُغني عن استشارة الطبيب.",
        "duration": "كم مدة هذه الأعراض؟",
        "severity": "ما شدة الأعراض؟ (من 1 خفيف جدًا إلى 5 شديد جدًا)",
        "conditions_f": "هل توجد أمراض مزمنة سابقة؟",
        "conditions_m": "هل توجد أمراض مزمنة سابقة؟",
        "other_diseases": "✏️ أمراض أخرى",
        "other_diseases_f": "✏️ اكتب الأمراض:", "other_diseases_m": "✏️ اكتب الأمراض:",
        "cond_ph": "مثال: غدة درقية",
        "meds_f": "هل توجد أدوية مستخدمة حاليًا؟ اذكر أسماءها (أو اختر تخطي).",
        "meds_m": "هل توجد أدوية مستخدمة حاليًا؟ اذكر أسماءها (أو اختر تخطي).",
        "skip": "⏭️ تخطي", "meds_ph": "مثال: بنادول، فولتارين",
        "notes_f": "أي ملاحظات إضافية؟ (أو اختر تخطي)", "notes_m": "أي ملاحظات إضافية؟ (أو اختر تخطي)",
        "notes_ph": "مثال: أعاني منذ الصباح بعد الأكل",
        "analyzing": "جاري التحليل... ⏳", "answering": "جاري الإجابة... ⏳",
        "err": "حدث خطأ: ", "conn_err": "تعذر الاتصال، حاول مجدداً.",
        "em_t": "🚑 اطلب الطوارئ الآن",
        "em_sub": "تحتوي إجابتك على أعراض قد تكون خطيرة وتحتاج إلى رعاية طبية عاجلة. لا تتأخر في طلب المساعدة.",
        "em_flags": "الأعراض التي استدعت التنبيه:",
        "em_call": "📞 اتصل بالطوارئ",
        "em_proceed": "فهمت، اعرض التحليل",
        "em_in1": "توجّه الآن لأقرب قسم طوارئ (أو اتصل 997) ولا تنتظر.",
        "em_in2": "لا تعطِ الرضيع أي دواء قبل أن يقيّمه الطبيب.",
        "em_in3": "ابقَ معه، وراقب تنفسه ولونه ويقظته، وخذه معك دون تأخير.",
        "em_ap1": "اذهب الآن إلى الطوارئ، ولا تنتظر زوال الألم.",
        "em_ap2": "لا تأكل ولا تشرب، ولا تأخذ ملينًا أو مسكنًا قويًا قبل أن يفحصك الطبيب.",
        "em_ap3": "لا تقد سيارتك بنفسك إن كان الألم شديدًا؛ اطلب من أحد أن يوصلك.",
        "em_pg1": "اتصل 997 أو توجّه الآن لأقرب طوارئ (ويفضل مستشفى فيه قسم ولادة).",
        "em_pg2": "لا تقد سيارتك بنفسك، واطلب من شخص أن يرافقك.",
        "em_pg3": "اذكر للطبيب أنك حامل وعمر الحمل وآخر موعد للدورة.",
        "em_dv1": "اتصل 997 الآن؛ قد يكون السبب جلطة في الساق أو الرئة.",
        "em_dv2": "لا تدلّك الساق ولا تضغط عليها، وقلّل الحركة قدر الإمكان.",
        "em_dv3": "اجلس بوضع مريح وأبقِ هاتفك قريبًا، ولا تقد سيارتك بنفسك.",
        "em_steps_t": "افعل هذا الآن:",
        "em_step1": "اتصل بالإسعاف 997 الآن ولا تنتظر تحسن الأعراض.",
        "em_step2": "لا تقد سيارتك بنفسك ولا تذهب وحدك.",
        "em_step3": "اطلب من شخص قريب أن يبقى معك، وافتح الباب ليصل الإسعاف بسهولة.",
        "em_step4": "لا تأكل ولا تشرب ولا تأخذ أدوية جديدة حتى يقيّمك الطبيب.",
        "em_sh_t": "لست وحدك — اطلب مساعدة الآن",
        "em_sh1": "تواصل فورًا مع شخص تثق به، ولا تبقَ وحدك.",
        "em_sh2": "ابعد عن متناول يدك أي شيء قد تؤذي به نفسك.",
        "em_sh3": "اتصل بالصحة 937 أو بمركز الاستشارات النفسية 920033360، وإن كنت في خطر مباشر فاتصل 997.",
        "em_po1": "اتصل 997 الآن، واحتفظ بعبوة الدواء أو المادة معك لتُريها للمسعف.",
        "em_po2": "لا تحاول التقيؤ إلا إذا طلب منك ذلك الطبيب أو مركز السموم.",
        "em_called": "اتصلت / المساعدة في الطريق",
        "em_details": "اعرض التفاصيل رغم ذلك",
        "em_confirm_q": "الحالات الطارئة لا تنتظر. هل اتصلت بالإسعاف أو أنت في طريقك للطوارئ؟",
        "em_confirm_yes": "نعم، اعرض التفاصيل",
        "em_confirm_no": "رجوع واتصال بالإسعاف",
        "em_locked": "تم إيقاف التحليل لأن هناك علامة خطر. لا يُكمل التطبيق الأسئلة أثناء الحالة الطارئة.",
        "em_num": "997",
        "em_copy": "اضغط لنسخ الرقم",
        "em_copied": "✅ تم النسخ",
        "em_disc": "هذا التنبيه مبني على كلمات الأعراض فقط ولا يُغني عن الرأي الطبي الفوري.",
        "blood_banner": "🧪 لديك تحليل دم محفوظ — يمكنك اختيار استخدامه كسياق إضافي",
        "related_title": "أعراض مرتبطة قد تهمك — اضغط للإضافة",
        "dq_title": "أسئلة مقترحة لحالتك",
        "dq_danger": "متى أذهب للطوارئ فورًا؟",
        "dq_sev": "هل مستوى الخطورة يعني التوجه للطوارئ؟",
        "dq_home": "ما الذي يمكنني فعله الآن لتخفيف الأعراض؟",
        "dq_doc": "ما المعلومات التي يجب أن أحضرها للطبيب؟",
        "sim_btn": "اشرحها لي ببساطة",
        "det_btn": "أريد التفاصيل",
        "sim_fallback": "الأعراض تحتاج متابعة، والأفضل استشارة طبيب للتأكد من الحالة.",
        "voice_chip": "🎙️ صف أعراضك صوتيًا",
        "voice_btn": "🎙️ صف أعراضك صوتيًا",
        "voice_speaking": "استمع الآن... تحدث بوضوح عن أعراضك، ثم اضغط إيقاف",
        "voice_stop": "⏹️ إيقاف",
        "voice_cancel": "إلغاء",
        "voice_thinking": "🤔 أفهم كلامك...",
        "voice_no_audio": "لم يُلتقط صوت — حاول مرة أخرى",
        "voice_err": "تعذّر تحويل الصوت: ",
        "voice_none": "لم أتعرّف على أعراض محددة",
        "voice_confirm": "✅ تأكيد ومتابعة التحليل",
        "voice_edit": "✏️ أعدل يدوياً",
        "voice_retry": "🔁 أعد التسجيل",
        "voice_syms": "الأعراض:",
        "voice_confirm_q": "هل هذا صحيح؟",
        "voice_manual": "حسناً، اختر أعراضك يدوياً:",
        "clar_yes": "نعم", "clar_no": "لا",
        "result_title": "📋 نتيجة التحليل",
        "urg_label": "مستوى الخطورة",
        "triage_why": "لماذا تم تصنيف حالتك بهذا المستوى؟",
        "urg_high": "طوارئ", "urg_medium": "يحتاج إلى موعد طبي", "urg_low": "بسيط",
        "assessment_label": "التقييم الأولي:",
        "forced_high": "⚠️ تم رفع مستوى التنبيه تلقائيًا بسبب وجود علامة خطر في المعلومات المدخلة.",
        "low_conf": "⚖️ الثقة منخفضة — يُفضل مراجعة الطبيب.",
        "possible": "🩺 الاحتمالات المحتملة",
        "kb_title": "🧠 لماذا ظهرت هذه الاحتمالات؟",
        "kb_matched": "الأعراض المتوافقة",
        "match_strong": "توافق مرتفع", "match_moderate": "توافق متوسط", "match_weak": "توافق منخفض",
        "sources_title": "📚 المصادر الطبية",
        "view_source": "عرض المصدر", "verified_source": "مصدر موثّق",
        "last_updated_info": "آخر تحديث للمعلومات",
        "medwarn": "💊 تحذيرات الأدوية",
        "medwarn_note": "للتوعية فقط — لا توقف أو تغيّر أي دواء موصوف دون استشارة الطبيب أو الصيدلي.",
        "ml_title": "📊 تحليل نموذج التعلم الآلي",
        "ml_explain": "اشرحها ببساطة",
        "ml_note": "النسب تعبّر عن درجة توافق المعلومات المدخلة مع كل احتمال، وليست احتمالًا مؤكدًا لوجود الحالة.",
        "recs": "📌 ماذا يمكنك أن تفعل الآن؟", "danger": "🚨 متى تحتاج إلى مساعدة عاجلة؟",
        "when": "🩺 متى تراجع الطبيب؟", "rec_src": "المصدر",
        "home_care": "🏠 الرعاية المنزلية", "med_guid": "💊 إرشاد الدواء",
        "q_doc": "❓ أسئلة يمكنك طرحها على طبيبك",
        "listen_all": "🔊 استمع للتحليل كاملاً",
        "fb_title": "⭐ هل أفادك التحليل؟",
        "fb_excellent": "😍 ممتاز", "fb_good": "🙂 جيد", "fb_ok": "😐 عادي", "fb_no": "😞 لا",
        "fb_thanks": "شكراً لتقييمك 🌟",
        "ask_more": "💬 اسأل عن حالتك", "hospitals": "🏥 أقرب مستشفى", "new": "🔄 تحليل جديد",
        "share": "🔗 مشاركة", "share_txt": "تقييمي الأولي: ",
        "followup_f": "اكتب سؤالك عن الحالة 👇", "followup_m": "اكتب سؤالك عن الحالة 👇",
        "followup_ph": "مثال: هل هذا طبيعي؟ متى أتحسن؟",
        "another_q": "💬 سؤال آخر",
        "no_speech": "متصفحك لا يدعم القراءة الصوتية.",
        "no_mic": "الإدخال الصوتي غير مدعوم على هذا الجهاز أو المتصفح. يمكنك الاستمرار بالكتابة.",
        "locating": "جاري تحديد موقعك... 📍",
        "loc_err_f": "تعذر الوصول إلى الموقع — تحقق من تفعيل إذن الموقع في المتصفح.",
        "loc_err_m": "تعذر الوصول إلى الموقع — تحقق من تفعيل إذن الموقع في المتصفح.",
        "no_hosp": "ما لقينا مستشفيات قريبة.",
        "hosp_title": "🏥 أقرب المستشفيات", "map": "🗺️ فتح في الخريطة", "km": " كم",
        "sp_result": "نتيجة التحليل: الخطورة ", "sp_possible": "الاحتمالات المحتملة: ",
        "sp_recs": "التوصيات:", "sp_medwarn": "تحذيرات الأدوية:", "sp_danger": "علامات الخطر: ",
        "sp_when": "متى تراجع الطبيب: ", "sp_home": "الرعاية المنزلية: ",
        "sp_medguid": "إرشاد الدواء: ", "sp_qdoc": "أسئلة اسأل طبيبك: ",
        "assess_title": "ملخص التقييم", "assess_safety": "مستوى الخطورة",
        "assess_completion": "اكتمال المعلومات", "assess_followup": "المتابعة الموصى بها",
        "assess_followup_default": "راقب الأعراض واطلب تقييمًا طبيًا إذا استمرت أو ساءت.",
        "assess_missing": "معلومات لم تُضف بعد",
        "questions_title": "أسئلة قد تهمك", "questions_sub": "اختر سؤالًا لمعرفة المزيد عن النتيجة.",
        "q_urgent_1": "ماذا أفعل الآن؟", "q_urgent_2": "هل أحتاج إلى الذهاب للطوارئ؟",
        "q_med_1": "متى أراجع الطبيب؟", "q_med_2": "ماذا يمكنني فعله في المنزل؟",
        "q_low_1": "كم قد تستمر الأعراض؟", "q_low_2": "متى تستدعي الأعراض القلق؟",
        "q通用_1": "اشرح لي هذه النتيجة أكثر", "q通用_2": "ما الأسئلة التي أطرحها على الطبيب؟",
        "why_title": "لماذا ظهر هذا التقييم؟",
        "transparency_title": "ما الذي اعتمد عليه التقييم؟",
        "transparency_sub": "نوضح المعلومات المعروفة وما يحتاج إلى توضيح إضافي.",
        "trans_known": "معلومات مؤكدة من إجاباتك", "trans_known_none": "لا توجد معلومات مؤكدة إضافية.",
        "trans_unclear": "معلومات تحتاج إلى توضيح", "trans_unclear_confidence": "درجة الثقة محدودة",
        "trans_unclear_duration": "مدة الأعراض غير محددة", "trans_unclear_notes": "التفاصيل الإضافية مختصرة",
        "trans_unclear_none": "لا توجد معلومات غير واضحة.", "trans_add_info": "إضافة معلومات",
        "trans_notasked": "معلومات لم تُسأل بعد", "trans_notasked_sleep": "نمط النوم",
        "trans_notasked_appetite": "تغير الشهية", "trans_notasked_stress": "التوتر مؤخرًا",
        "trans_notasked_family": "التاريخ العائلي",
        "trans_notasked_note": "عدم سؤال هذه المعلومات لا يعني أنها غير مهمة طبيًا.",
        "trans_add_q": "ما المعلومة التي تريد إضافتها؟", "trans_add_duration": "مدة الأعراض",
        "trans_add_meds": "الأدوية الحالية", "trans_add_notes": "تفاصيل إضافية",
        "trans_add_meds_q": "اكتب أسماء الأدوية الحالية.", "trans_add_meds_hint": "مثال: اسم الدواء والجرعة إن عُرفت",
        "trans_add_notes_q": "أضف أي تفاصيل أخرى عن الأعراض.", "trans_add_notes_hint": "مثال: وقت البداية وما يزيد الأعراض أو يخففها",
        "trans_adding": "تمت إضافة المعلومة، جارٍ تحديث التقييم…", "trans_add_done": "تم تحديث المعلومات.",
        "incomplete_days": "منذ عدة أيام", "incomplete_today": "بدأت اليوم", "incomplete_yesterday": "بدأت أمس",
        "incomplete_week": "منذ أسبوع أو أكثر", "incomplete_done": "متابعة التحليل",
        "incomplete_reanalyzing": "جارٍ تحديث التحليل…", "new_analysis": "تحليل جديد",
        "save_profile": "حفظ في الملف الصحي", "save_success": "تم الحفظ بنجاح.",
        "save_error": "تعذر الحفظ حاليًا.", "save_login_required": "سجّل الدخول لحفظ المعلومات.",
        "save_nothing_new": "لا توجد معلومات جديدة للحفظ.",
        "no_speech_api": "القراءة الصوتية غير مدعومة في هذا المتصفح.",
        "fallback_chat": "تعذر إكمال الطلب الآن. حاول مرة أخرى.",
    },
    "en": {
        "me": "👤 Me",
        "voice_mode_on": "🎙️ Voice conversation: On",
        "voice_mode_off": "🎙️ Voice conversation: Off",
        "voice_mode_title": "Voice conversation: listens to you and reads the reply aloud",
        "voice_listening": "🎧 Listening...",
        "voice_processing": "⏳ Processing...",
        "voice_speaking_state": "🔊 Reading...",
        "welcome": "🩺 Welcome to SymptoSense",
        "head_p": "Your smart assistant to understand health symptoms",
        "muted": "Awareness only, not a final diagnosis — see a doctor if in any doubt.",
        "speak_on": "🔊 Read aloud: On", "speak_off": "🔊 Read aloud: Off",
        "speak_title": "Read aloud: SymptoSense reads text to you",
        "input_ph": "Type here...", "send": "Send", "mic_title": "Voice input",
        "age": "How old are you? (type the number only) 🧒👵", "age_ph": "Example: 28",
        "age_invalid": "Please enter a valid age between 1 and 120.",
        "gender": "What is your gender?", "male": "👨 Male", "female": "👩 Female",
        "syms_f": "What are your symptoms? Tap the ones you have (you can pick more than one). If you don't find what you feel, type it in the text box. When done, tap: ✅ Done",
        "syms_m": "What are your symptoms? Tap the ones you have (you can pick more than one). If you don't find what you feel, type it in the text box. When done, tap: ✅ Done",
        "write_yourself": "✍️ Write your own symptom",
        "sym_ph": "Example: leg pain",
        "custom_f": "Don't find what you feel? Type it here:",
        "custom_m": "Don't find what you feel? Type it here:",
        "atleast_f": "Please pick at least one symptom before continuing.",
        "atleast_m": "Please pick at least one symptom before continuing.",
        "done": "✅ Done", "chosen": "✅ Selected: ",
        "added_f": "✅ Symptom added. Tap ✅ Done when finished or add more.",
        "added_m": "✅ Symptom added. Tap ✅ Done when finished or add more.",
        "start_sub": "Your smart assistant to understand health symptoms",
        "start_desc": "I'll ask you a few questions about the symptoms you feel to help you get an initial, safe, and easy assessment.",
        "syms_q": "What symptoms are you feeling?",
        "syms_more": "Do you have any other symptoms?",
        "syms_hint": "Describe your symptoms in detail, e.g. “I've had a severe headache on the right side with nausea for two days”",
        "write_yourself_n": "✍️ Write your own symptom",
        "custom_n": "Type your symptoms here (or use voice input 🎤):",
        "added_n": "✅ Added. Add more, then tap “Start assessment”.",
        "atleast": "Please select at least one symptom before starting.",
        "start_btn": "Start assessment →",
        "for_whom": "Who is this assessment for?",
        "me_short": "👤 Me",
        "yrs": "yrs",
        "person_badge": "Assessment for: ",
        "result_card_title": "📋 Analysis Result",
        "result_disclaimer": "⚠️ This assessment is not a medical diagnosis and does not replace seeing a doctor.",
        "duration": "How long have you had these symptoms?",
        "severity": "How severe are the symptoms? (1 = very mild, 5 = critical)",
        "conditions_f": "Do you have any pre-existing chronic conditions?",
        "conditions_m": "Do you have any pre-existing chronic conditions?",
        "other_diseases": "✏️ Other conditions",
        "other_diseases_f": "✏️ Type your conditions:", "other_diseases_m": "✏️ Type your conditions:",
        "cond_ph": "Example: thyroid",
        "meds_f": "Are you currently taking any medications? List their names (or tap Skip).",
        "meds_m": "Are you currently taking any medications? List their names (or tap Skip).",
        "skip": "⏭️ Skip", "meds_ph": "Example: Paracetamol, Voltaren",
        "notes_f": "Any additional notes? (or tap Skip)", "notes_m": "Any additional notes? (or tap Skip)",
        "notes_ph": "Example: feeling unwell since the morning after eating",
        "analyzing": "Analyzing... ⏳", "answering": "Answering... ⏳",
        "err": "Error: ", "conn_err": "Connection failed, please try again.",
        "em_t": "🚑 Call emergency now",
        "em_sub": "Your input includes symptoms that may be critical and require urgent medical care. Please do not delay seeking help.",
        "em_flags": "Symptoms that triggered the alert:",
        "em_call": "📞 Call emergency",
        "em_proceed": "I understand, show the analysis",
        "em_in1": "Go to the nearest emergency department now (or call 997); do not wait.",
        "em_in2": "Do not give the baby any medicine before a clinician has assessed them.",
        "em_in3": "Stay with the baby, watch breathing, colour and alertness, and take them with you without delay.",
        "em_ap1": "Go to the emergency department now; do not wait for the pain to pass.",
        "em_ap2": "Do not eat or drink, and do not take laxatives or strong painkillers before you are examined.",
        "em_ap3": "Do not drive yourself if the pain is severe; ask someone to take you.",
        "em_pg1": "Call 997 or go to the nearest emergency department now (preferably a hospital with maternity care).",
        "em_pg2": "Do not drive yourself and ask someone to go with you.",
        "em_pg3": "Tell the doctor you are pregnant, how many weeks, and your last period date.",
        "em_dv1": "Call 997 now; this could be a blood clot in the leg or lung.",
        "em_dv2": "Do not massage or press the leg, and keep movement to a minimum.",
        "em_dv3": "Sit comfortably, keep your phone close, and do not drive yourself.",
        "em_steps_t": "Do this now:",
        "em_step1": "Call 997 now and do not wait for symptoms to improve.",
        "em_step2": "Do not drive yourself and do not go alone.",
        "em_step3": "Ask someone nearby to stay with you, and unlock the door so help can reach you.",
        "em_step4": "Do not eat, drink or take new medicines until a clinician has assessed you.",
        "em_sh_t": "You are not alone — reach out now",
        "em_sh1": "Contact someone you trust right away and do not stay alone.",
        "em_sh2": "Move anything you could hurt yourself with out of reach.",
        "em_sh3": "Call 937 (Ministry of Health) or 920033360 (mental-health line); if in immediate danger call 997.",
        "em_po1": "Call 997 now and keep the medicine or substance container to show the responders.",
        "em_po2": "Do not try to vomit unless a doctor or poison centre tells you to.",
        "em_called": "I called / help is on the way",
        "em_details": "Show details anyway",
        "em_confirm_q": "Emergencies should not wait. Have you called an ambulance or are you on your way to the ER?",
        "em_confirm_yes": "Yes, show details",
        "em_confirm_no": "Go back and call",
        "em_locked": "The assessment was stopped because a red flag was found. No further questions are asked during an emergency.",
        "em_num": "997",
        "em_copy": "Tap to copy the number",
        "em_copied": "✅ Copied",
        "em_disc": "This alert is based on symptom keywords only and is not a substitute for immediate medical advice.",
        "blood_banner": "🧪 You have a saved blood test — you can choose to use it as additional context",
        "related_title": "Related symptoms that may matter — tap to add",
        "dq_title": "Suggested questions for your case",
        "dq_danger": "When should I go to the ER immediately?",
        "dq_sev": "Does the severity level mean I should go to the ER?",
        "dq_home": "What can I do right now to ease the symptoms?",
        "dq_doc": "What information should I bring to the doctor?",
        "sim_btn": "Explain it simply",
        "det_btn": "I want the details",
        "sim_fallback": "The symptoms need monitoring, and it's best to consult a doctor to confirm the condition.",
        "voice_chip": "🎙️ Describe your symptoms by voice",
        "voice_btn": "🎙️ Describe your symptoms by voice",
        "voice_speaking": "Listening... describe your symptoms clearly, then tap Stop",
        "voice_stop": "⏹️ Stop",
        "voice_cancel": "Cancel",
        "voice_thinking": "🤔 Understanding you...",
        "voice_no_audio": "No audio captured — try again",
        "voice_err": "Voice conversion failed: ",
        "voice_none": "No specific symptoms recognized",
        "voice_confirm": "✅ Confirm & Analyze",
        "voice_edit": "✏️ Edit manually",
        "voice_retry": "🔁 Record again",
        "voice_syms": "Symptoms:",
        "voice_confirm_q": "Is this correct?",
        "voice_manual": "OK, choose your symptoms manually:",
        "clar_yes": "Yes", "clar_no": "No",
        "result_title": "📋 Analysis result",
        "urg_label": "Severity level",
        "triage_why": "Why was your case classified at this level?",
        "urg_high": "Emergency", "urg_medium": "Needs an appointment", "urg_low": "Mild",
        "assessment_label": "Initial assessment:",
        "forced_high": "⚠️ Urgency raised automatically based on red-flag symptoms.",
        "low_conf": "⚖️ Low confidence — a doctor visit is recommended.",
        "possible": "🩺 Possible conditions",
        "kb_title": "🧠 Why did these possibilities appear?",
        "kb_matched": "Matching symptoms",
        "match_strong": "Strong match", "match_moderate": "Moderate match", "match_weak": "Weak match",
        "sources_title": "📚 Medical sources",
        "view_source": "View source", "verified_source": "Verified source",
        "last_updated_info": "Information last updated",
        "medwarn": "💊 Medication warnings",
        "medwarn_note": "Awareness only — don't stop your prescribed medication without consulting your doctor.",
        "ml_title": "📊 Machine learning model analysis",
        "ml_explain": "Explain simply",
        "ml_note": "These percentages are model outputs, not confirmed diagnostic probabilities.",
        "recs": "📌 What can you do right now?", "danger": "🚨 When do you need urgent help?",
        "when": "🩺 When should you see a doctor?", "rec_src": "Source",
        "home_care": "🏠 Home care", "med_guid": "💊 Medication guidance",
        "q_doc": "❓ Questions you can ask your doctor",
        "listen_all": "🔊 Listen to the full analysis",
        "fb_title": "⭐ Was this analysis helpful?",
        "fb_excellent": "😍 Excellent", "fb_good": "🙂 Good", "fb_ok": "😐 Average", "fb_no": "😞 No",
        "fb_thanks": "Thanks for your feedback 🌟",
        "ask_more": "💬 Ask about your case", "hospitals": "🏥 Nearest hospital", "new": "🔄 New analysis",
        "share": "🔗 Share", "share_txt": "My initial assessment: ",
        "followup_f": "Type your question about your case 👇", "followup_m": "Type your question about your case 👇",
        "followup_ph": "Example: Is this normal? When will I improve?",
        "another_q": "💬 Another question",
        "no_speech": "Your browser does not support voice reading.",
        "no_mic": "Voice input is not supported on this device/browser. You can continue by typing.",
        "locating": "Locating you... 📍",
        "loc_err_f": "Could not access your location — please enable location services.",
        "loc_err_m": "Could not access your location — please enable location services.",
        "no_hosp": "No nearby hospitals found.",
        "hosp_title": "🏥 Nearest hospitals", "map": "🗺️ Open in map", "km": " km",
        "sp_result": "Analysis result: severity ", "sp_possible": "Possible conditions: ",
        "sp_recs": "Recommendations:", "sp_medwarn": "Medication warnings:", "sp_danger": "Danger signs: ",
        "sp_when": "When to see a doctor: ", "sp_home": "Home care: ",
        "sp_medguid": "Medication guidance: ", "sp_qdoc": "Questions for your doctor: ",
        "assess_title": "Assessment summary", "assess_safety": "Risk level",
        "assess_completion": "Information completeness", "assess_followup": "Recommended follow-up",
        "assess_followup_default": "Monitor your symptoms and seek medical evaluation if they persist or worsen.",
        "assess_missing": "Information not added yet",
        "questions_title": "Questions you may have", "questions_sub": "Choose a question to learn more about the result.",
        "q_urgent_1": "What should I do right now?", "q_urgent_2": "Do I need to go to the emergency department?",
        "q_med_1": "When should I see a doctor?", "q_med_2": "What can I do at home?",
        "q_low_1": "How long might the symptoms last?", "q_low_2": "When should I be concerned?",
        "q通用_1": "Explain this result in more detail", "q通用_2": "What should I ask my doctor?",
        "why_title": "Why did this assessment appear?",
        "transparency_title": "What did the assessment use?",
        "transparency_sub": "We show what is known and what may need more detail.",
        "trans_known": "Confirmed from your answers", "trans_known_none": "No additional confirmed information.",
        "trans_unclear": "Information needing clarification", "trans_unclear_confidence": "Confidence is limited",
        "trans_unclear_duration": "Symptom duration is not specified", "trans_unclear_notes": "Additional details are brief",
        "trans_unclear_none": "No unclear information.", "trans_add_info": "Add information",
        "trans_notasked": "Information not asked yet", "trans_notasked_sleep": "Sleep pattern",
        "trans_notasked_appetite": "Appetite changes", "trans_notasked_stress": "Recent stress",
        "trans_notasked_family": "Family history",
        "trans_notasked_note": "Not asking about these items does not mean they are medically unimportant.",
        "trans_add_q": "What information would you like to add?", "trans_add_duration": "Symptom duration",
        "trans_add_meds": "Current medications", "trans_add_notes": "Additional details",
        "trans_add_meds_q": "Enter your current medications.", "trans_add_meds_hint": "Example: medication name and dose, if known",
        "trans_add_notes_q": "Add any other details about your symptoms.", "trans_add_notes_hint": "Example: when they began and what makes them better or worse",
        "trans_adding": "Information added; updating the assessment…", "trans_add_done": "Information updated.",
        "incomplete_days": "For several days", "incomplete_today": "Started today", "incomplete_yesterday": "Started yesterday",
        "incomplete_week": "For a week or longer", "incomplete_done": "Continue assessment",
        "incomplete_reanalyzing": "Updating the assessment…", "new_analysis": "New assessment",
        "save_profile": "Save to health profile", "save_success": "Saved successfully.",
        "save_error": "Unable to save right now.", "save_login_required": "Sign in to save information.",
        "save_nothing_new": "There is no new information to save.",
        "no_speech_api": "Voice reading is not supported in this browser.",
        "fallback_chat": "Unable to complete the request right now. Please try again.",
    },
}


def _related_map(ar):
    if ar:
        return {
            "🤕 صداع": ["💫 دوار", "🤢 غثيان", "😴 تعب وإرهاق", "👁️ احمرار العيون", "🤒 حمى"],
            "🤒 حمى": ["🥶 قشعريرة", "😴 تعب وإرهاق", "😷 سعال", "😣 ألم الحلق"],
            "😷 سعال": ["🤒 حمى", "🫁 ضيق التنفس", "😣 ألم الحلق", "🫀 ألم في الصدر"],
            "🫀 ألم في الصدر": ["🫁 ضيق التنفس", "💫 دوار", "🤢 غثيان", "😴 تعب وإرهاق"],
            "🤢 غثيان": ["😖 ألم في البطن", "💫 دوار", "🤕 صداع"],
            "😴 تعب وإرهاق": ["🤒 حمى", "💫 دوار", "🫁 ضيق التنفس", "🦴 ألم المفاصل"],
            "🫁 ضيق التنفس": ["🫀 ألم في الصدر", "💫 دوار", "😷 سعال"],
            "💫 دوار": ["🤕 صداع", "🤢 غثيان", "😵 إغماء أو فقدان وعي", "💓 خفقان القلب", "😴 تعب وإرهاق"],
            "😵 إغماء أو فقدان وعي": ["💫 دوار", "💓 خفقان القلب", "🫀 ألم في الصدر", "🫁 ضيق التنفس"],
            "💓 خفقان القلب": ["💫 دوار", "😵 إغماء أو فقدان وعي", "🫀 ألم في الصدر", "🫁 ضيق التنفس"],
            "🤮 قيء": ["🤢 غثيان", "🚽 إسهال", "😖 ألم في البطن", "💫 دوار"],
            "🚽 إسهال": ["🤮 قيء", "🤢 غثيان", "😖 ألم في البطن", "💫 دوار"],
            "🦴 ألم المفاصل": ["😴 تعب وإرهاق", "🤒 حمى"],
            "😖 ألم في البطن": ["🤢 غثيان", "🤒 حمى"],
            "🥶 قشعريرة": ["🤒 حمى", "😴 تعب وإرهاق"],
            "👁️ احمرار العيون": ["🖐️ حكة", "🤕 صداع"],
            "🦵 ألم في الرجل": ["🫁 ضيق التنفس", "😴 تعب وإرهاق"],
            "😣 ألم الحلق": ["😷 سعال", "🤒 حمى"],
            "🖐️ حكة": ["👁️ احمرار العيون", "🤒 حمى"],
        }
    return {
        "🤕 Headache": ["💫 Dizziness", "🤢 Nausea", "😴 Fatigue", "👁️ Eye redness", "🤒 Fever"],
        "🤒 Fever": ["🥶 Chills", "😴 Fatigue", "😷 Cough", "😣 Sore throat"],
        "😷 Cough": ["🤒 Fever", "🫁 Shortness of breath", "😣 Sore throat", "🫀 Chest pain"],
        "🫀 Chest pain": ["🫁 Shortness of breath", "💫 Dizziness", "🤢 Nausea", "😴 Fatigue"],
        "🤢 Nausea": ["😖 Stomach pain", "💫 Dizziness", "🤕 Headache"],
        "😴 Fatigue": ["🤒 Fever", "💫 Dizziness", "🫁 Shortness of breath", "🦴 Joint pain"],
        "🫁 Shortness of breath": ["🫀 Chest pain", "💫 Dizziness", "😷 Cough"],
        "💫 Dizziness": ["🤕 Headache", "🤢 Nausea", "😵 Fainting or loss of consciousness", "💓 Heart palpitations", "😴 Fatigue"],
        "😵 Fainting or loss of consciousness": ["💫 Dizziness", "💓 Heart palpitations", "🫀 Chest pain", "🫁 Shortness of breath"],
        "💓 Heart palpitations": ["💫 Dizziness", "😵 Fainting or loss of consciousness", "🫀 Chest pain", "🫁 Shortness of breath"],
        "🤮 Vomiting": ["🤢 Nausea", "🚽 Diarrhea", "😖 Stomach pain", "💫 Dizziness"],
        "🚽 Diarrhea": ["🤮 Vomiting", "🤢 Nausea", "😖 Stomach pain", "💫 Dizziness"],
        "🦴 Joint pain": ["😴 Fatigue", "🤒 Fever"],
        "😖 Stomach pain": ["🤢 Nausea", "🤒 Fever"],
        "🥶 Chills": ["🤒 Fever", "😴 Fatigue"],
        "👁️ Eye redness": ["🖐️ Itching", "🤕 Headache"],
        "🦵 Leg pain": ["🫁 Shortness of breath", "😴 Fatigue"],
        "😣 Sore throat": ["😷 Cough", "🤒 Fever"],
        "🖐️ Itching": ["👁️ Eye redness", "🤒 Fever"],
    }


def render_chat_page(*, lang, page, t, json_for_script):
    ar = lang == "ar"
    # Embed the ready-made demo result in the page so the demo never depends on
    # a network/DB round-trip. It still comes from the real deterministic
    # analysis engine, keeping its result shape aligned with production.
    from demo_analysis import demo_analysis_result
    demo_result = demo_analysis_result("ar" if ar else "en")
    if ar:
        syms = [
            "🤕 صداع", "🤒 حمى", "😷 سعال", "🫀 ألم في الصدر", "🤢 غثيان", "😴 تعب وإرهاق",
            "🫁 ضيق التنفس", "💫 دوار", "😵 إغماء أو فقدان وعي", "💓 خفقان القلب", "🦴 ألم المفاصل", "😖 ألم في البطن",
            "🤮 قيء", "🚽 إسهال", "🥶 قشعريرة", "👁️ احمرار العيون", "🩹 طفح جلدي", "🔥 حرقة أو ألم عند التبول",
            "🦵 ألم في الرجل", "😣 ألم الحلق", "🖐️ حكة", "🖐️ تنميل أو خدر", "🧠 تشوش أو ارتباك", "⚡ نوبة تشنج",
        ]
        durs = ["⏰ أقل من 24 ساعة", "📅 1-3 أيام", "📅 4-7 أيام", "🗓️ 1-2 أسبوع", "🗓️ أكثر من أسبوعين", "📆 أكثر من شهر"]
        sevs = [("1", "1️⃣ خفيف جدًا"), ("2", "2️⃣ خفيف"), ("3", "3️⃣ متوسط"), ("4", "4️⃣ شديد"), ("5", "5️⃣ شديد جدًا")]
        conds = ["لا يوجد أمراض سابقة", "سكري", "ضغط الدم", "أمراض قلب", "ربو"]
    else:
        syms = [
            "🤕 Headache", "🤒 Fever", "😷 Cough", "🫀 Chest pain", "🤢 Nausea", "😴 Fatigue",
            "🫁 Shortness of breath", "💫 Dizziness", "😵 Fainting or loss of consciousness", "💓 Heart palpitations", "🦴 Joint pain", "😖 Stomach pain",
            "🤮 Vomiting", "🚽 Diarrhea", "🥶 Chills", "👁️ Eye redness", "🩹 Skin rash", "🔥 Pain or burning when urinating",
            "🦵 Leg pain", "😣 Sore throat", "🖐️ Itching", "🖐️ Numbness or tingling", "🧠 Confusion", "⚡ Seizure",
        ]
        durs = ["⏰ Less than 24 hours", "📅 1-3 days", "📅 4-7 days", "🗓️ 1-2 weeks", "🗓️ More than 2 weeks", "📆 More than a month"]
        sevs = [("1", "1️⃣ Very mild"), ("2", "2️⃣ Mild"), ("3", "3️⃣ Moderate"), ("4", "4️⃣ Severe"), ("5", "5️⃣ Critical")]
        conds = ["No previous conditions", "Diabetes", "High blood pressure", "Heart disease", "Asthma"]

    body = """
    <link rel="stylesheet" href="/static/css/v83_user_tools.css?v=193">
    <div class="chat-wrap">
      <div class="chat-head">
        <div class="avatar" id="chatAvatar">🏥</div>
        <div><h3>SymptoSense</h3><p id="headP"></p></div>
        <div id="profileSwitcher" style="margin-left:auto;display:flex;align-items:center;gap:6px;">
          <select id="famSelect" style="background:#fff;color:#0F2F63;border:1px solid #fff;border-radius:8px;padding:6px 10px;font-size:13px;font-family:inherit;cursor:pointer;max-width:140px;" aria-label="Select family member">
            <option value="0">__ME__</option>
          </select>
        </div>
        <details class="chat-access" id="chatAccess">
          <summary aria-label="__ACCESSIBILITY_ARIA__">🔊 __ACCESSIBILITY__</summary>
          <div class="chat-access-menu" role="group" aria-label="__AUDIO_CONTROLS__">
            <button id="spkBtn" type="button" class="spk-btn" aria-pressed="false" aria-label="__SPEAKER_OFF_ARIA__" title="__SPEAKER_OFF_ARIA__">
              <span aria-hidden="true">🔊</span><span id="spkText">__SPEAK_OFF__</span>
            </button>
            <button id="micBtn" type="button" class="spk-btn" aria-pressed="false" aria-label="__MIC_READY_ARIA__" title="__MIC_READY_ARIA__">
              <span aria-hidden="true">🎙️</span><span id="micText">__VOICE_INPUT__</span>
            </button>
            <span id="audioState" class="sr-only" aria-live="polite"></span>
          </div>
        </details>
      </div>
      <div class="ss-flow" aria-live="polite"><div class="ss-flow-copy"><span id="flowStepLabel">__FLOW_STEP__</span><span id="flowStepName">__FLOW_DEMO__</span></div><div class="ss-flow-track" role="progressbar" aria-label="__FLOW_STEP__" aria-valuemin="1" aria-valuemax="7" aria-valuenow="1" id="flowProgress"><div class="ss-flow-fill" id="flowFill"></div></div></div>
      <div class="chat-body" id="chatBody"></div>
      <div class="chat-options" id="chatOptions"></div>
      <div class="chat-input" id="chatInput" style="display:none;" role="search" aria-label="Message input">
        <input type="text" id="textInp" placeholder="__INPUT_PH__" autocomplete="off" aria-label="Type your message">
        <button type="button" id="chatSendBtn" aria-label="__SEND__">__SEND__</button>
      </div>
    </div>
    <div class="muted" id="chatSafetyNote" style="text-align:center;margin-top:10px;">__MUTED__</div>
    <div class="blood-banner" id="bloodBanner" style="display:none;"></div>
    <div class="em-overlay" id="emOverlay"></div>

    <style>
    .smart-context-found{margin-top:10px;padding:10px 11px;border:1px solid #d7e8f2;border-radius:12px;background:#f8fcff}.smart-context-found>b{display:block;color:#123b70;font-size:12px}.smart-context-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:7px}.smart-context-chips span{display:inline-flex;padding:5px 8px;border-radius:999px;background:#eaf5fc;color:#225c86;font-size:10.5px;font-weight:800}.smart-context-found small{display:block;margin-top:7px;color:#566a7d;font-size:10.5px;line-height:1.6}.ss-pattern-summary-v151 p{margin:8px 0;color:#24445f;line-height:1.85}.ss-pattern-summary-v151 small{color:#566a7d;line-height:1.6}.symptom-path-rail.compact{overflow-x:auto;padding-bottom:4px}
    </style>
    <style id="bm-v244">
    .bm-visual{position:relative;width:100%;max-width:380px;aspect-ratio:360/540;margin:8px auto 0;direction:ltr}
    .bm-svg{position:absolute;inset:0;width:100%;height:100%;display:block;overflow:visible}
    .bm-svg .bm-out{fill:none;stroke:#AFCBE8;stroke-linecap:round}
    .bm-svg .bm-limb{fill:none;stroke:#E6F1FB;stroke-linecap:round}
    .bm-svg .bm-edge{fill:#E6F1FB;stroke:#AFCBE8;stroke-width:1.5}
    .bm-svg .bm-detail{fill:none;stroke:#BBD3EC;stroke-width:1.5;stroke-linecap:round}
    .bm-svg .bm-hl-f{fill:transparent;stroke:none}
    .bm-svg .bm-hl-s{fill:none;stroke:transparent;stroke-linecap:round}
    .bm-svg .bm-zone.on .bm-hl-f{fill:#2A78D0;fill-opacity:.38}
    .bm-svg .bm-zone.on .bm-hl-s{stroke:#2A78D0;stroke-opacity:.38}
    .bm-svg .bm-zone{cursor:pointer;outline:none}
    .bm-svg .bm-zone:hover .bm-hl-f{fill:#2A78D0;fill-opacity:.16}
    .bm-svg .bm-zone:hover .bm-hl-s{stroke:#2A78D0;stroke-opacity:.16}
    .bm-svg .bm-zone.on:hover .bm-hl-f{fill-opacity:.38}
    .bm-svg .bm-zone.on:hover .bm-hl-s{stroke-opacity:.38}
    .bm-svg .bm-zone:focus-visible .bm-halo{stroke:#0F2F63;stroke-width:2.5}
    .bm-svg .bm-halo{fill:rgba(31,111,208,.18)}
    .bm-svg .bm-dot{fill:#1F6FD0;stroke:#fff;stroke-width:2}
    .bm-svg .bm-zone.on .bm-halo{fill:rgba(31,111,208,.32)}
    .bm-svg .bm-zone.on .bm-dot{fill:#0B4FA8}
    .bm-svg .bm-hit{fill:transparent}
    .bm-svg .bm-line{fill:none;stroke:#8DB6E3;stroke-width:1.5;stroke-linecap:round}
    .bm-svg .bm-line.on{stroke:#1F6FD0;stroke-width:2}
    .bm-label{position:absolute;transform:translateY(-50%);width:25%;min-height:40px;padding:5px 9px;box-sizing:border-box;border-radius:12px;border:1.5px solid #C2D9EF;background:#fff;color:#0F2F63;font-family:'Tajawal','Poppins','Segoe UI',sans-serif;font-size:13.5px;font-weight:700;line-height:1.25;text-align:center;box-shadow:0 2px 6px rgba(31,111,208,.10);cursor:pointer;display:flex;align-items:center;justify-content:center;gap:4px;direction:inherit;-webkit-tap-highlight-color:transparent}
    .bm-label.bm-L{left:0}.bm-label.bm-R{right:0}
    .bm-label i{font-style:normal;font-size:13px}
    .bm-label:hover{border-color:#1F6FD0}
    .bm-label.on{background:#1F6FD0;border-color:#1F6FD0;color:#fff}
    .bm-label:focus-visible{outline:3px solid #0F2F63;outline-offset:2px}
    .bm-label{word-break:normal;overflow-wrap:normal;hyphens:none}
    @media(max-width:420px){.bm-label{width:27%;font-size:13px;padding:4px 5px;min-height:44px}}
    @media(max-width:350px){.bm-label{width:30%;font-size:13px;padding:2px 4px;min-height:36px;line-height:1.15;letter-spacing:-.2px}}
    body.ss-chat-page #smartBodyCard{font-family:'Tajawal','Poppins','Segoe UI',sans-serif!important;color:#0F2F63!important}
    body.ss-chat-page #smartBodyCard .smart-body-copy b{font-size:21px!important;font-weight:800!important;color:#0F2F63!important}
    body.ss-chat-page #smartBodyCard .smart-body-copy p,body.ss-chat-page #smartBodyCard .smart-body-copy .muted{font-size:15px!important;line-height:1.7!important;color:#3F5B7B!important}
    body.ss-chat-page #smartBodyCard .smart-body-hint{font-size:14.5px!important;font-weight:700!important;color:#3F5B7B!important}
    body.ss-chat-page #smartBodyCard .smart-toggle-btn{min-height:46px!important;font-size:16px!important;font-weight:800!important;color:#0F2F63!important}
    body.ss-chat-page #smartBodyCard .smart-toggle-btn.on{color:#0B4FA8!important}
    body.ss-chat-page #smartBodyCard .smart-body-visual-help{font-size:14px!important;font-weight:600!important;color:#3F5B7B!important;margin-top:6px!important}
    body.ss-chat-page #smartBodyCard .smart-body-selection-note{font-size:15px!important;font-weight:700!important;color:#0F2F63!important}
    body.ss-chat-page #smartBodyCard .smart-body-selection-tray-head b{font-size:16px!important;font-weight:800!important;color:#0F2F63!important}
    body.ss-chat-page #smartBodyCard .smart-body-selection-tray-head span{font-size:15px!important;color:#3F5B7B!important}
    body.ss-chat-page #smartBodyCard .smart-body-selection-chip{font-size:15px!important;font-weight:700!important;min-height:42px!important;color:#0F2F63!important}
    body.ss-chat-page #smartBodyCard .smart-body-clear{min-height:44px!important;font-size:15px!important;font-weight:700!important;color:#3F5B7B!important}
    body.ss-chat-page #smartBodyCard .smart-body-next{min-height:48px!important;font-size:17px!important;font-weight:800!important}
    body.ss-chat-page #smartBodyCard .smart-body-empty{font-size:15px!important;color:#3F5B7B!important;line-height:1.7!important}
    body.ss-chat-page #smartBodyCard .smart-body-region-head b{font-size:21px!important;font-weight:800!important;color:#0F2F63!important}
    body.ss-chat-page #smartBodyCard .smart-body-region-head small{font-size:15px!important;color:#3F5B7B!important;line-height:1.6!important}
    body.ss-chat-page #smartBodyCard .smart-body-selected-badge{font-size:13.5px!important;font-weight:800!important}
    body.ss-chat-page #smartBodyCard .smart-body-existing{font-size:14px!important;line-height:1.6!important;color:#1D5A3A!important}
    body.ss-chat-page #smartBodyCard .smart-body-zone-intro{font-size:16.5px!important;font-weight:800!important;color:#0F2F63!important;margin:12px 0 8px!important}
    body.ss-chat-page #smartBodyCard .smart-body-symptom{min-height:50px!important;font-size:16.5px!important;font-weight:700!important;line-height:1.3!important;color:#0F2F63!important}
    body.ss-chat-page #smartBodyCard .smart-body-symptom.on{color:#fff!important}
    body.ss-chat-page #smartBodyCard .smart-body-other{margin-top:14px!important;padding:14px!important;border:1.5px dashed #9BBFE6!important;border-radius:16px!important;background:#F5FAFF!important}
    body.ss-chat-page #smartBodyCard .smart-body-other b{display:block!important;font-size:16.5px!important;font-weight:800!important;color:#0F2F63!important}
    body.ss-chat-page #smartBodyCard .smart-body-other small{display:block!important;font-size:14.5px!important;line-height:1.6!important;color:#3F5B7B!important;margin:2px 0 10px!important}
    body.ss-chat-page #smartBodyCard .smart-body-other input{min-height:50px!important;font-size:16px!important;color:#0F2F63!important;width:100%!important;box-sizing:border-box!important}
    body.ss-chat-page #smartBodyCard .smart-body-other button{min-height:50px!important;font-size:16px!important;font-weight:800!important}
    body.ss-chat-page #smartBodyCard .smart-body-other>div{display:flex!important;flex-direction:column!important;gap:10px!important}
    body.ss-chat-page #smartBodyCard .smart-body-other button{background:#1F6FD0!important;color:#fff!important;border:0!important;border-radius:12px!important;padding:0 18px!important;width:100%!important}
    body.ss-chat-page #smartBodyCard .smart-body-next{background:#1F6FD0!important;color:#fff!important;border:0!important;border-radius:12px!important;padding:0 22px!important;cursor:pointer}
    body.ss-chat-page #smartBodyCard .smart-body-next:disabled{background:#C9D9EA!important;color:#566E8A!important;cursor:not-allowed}
    body.ss-chat-page #smartBodyCard .smart-body-clear{background:#fff!important;border:1.5px solid #C2D9EF!important;border-radius:12px!important;padding:0 14px!important;cursor:pointer}
    body.ss-chat-page #smartBodyCard .smart-body-clear:disabled{opacity:.55;cursor:not-allowed}
    body.ss-chat-page #smartBodyCard .smart-body-selection-tray{display:flex!important;flex-wrap:wrap!important;align-items:center!important;gap:10px!important}
    body.ss-chat-page #smartBodyCard .smart-body-selection-tray-head{flex:1 1 100%!important;display:flex!important;align-items:center!important;gap:8px!important;justify-content:space-between!important}
    body.ss-chat-page #smartBodyCard .smart-body-selection-chip{flex:1 1 140px!important}
    body.ss-chat-page .symptom-method-btn{font-size:15px!important;font-weight:800!important;color:#0F2F63!important}
    body.ss-chat-page .symptom-method-btn.active{color:#0B4FA8!important}
    </style>
    <script>
    document.body.classList.add('ss-chat-page');
    // Page data only. All behaviour lives in /static/js/chat/*.js (loaded below, in this order).
    const T = __T__;
    const LANG = "__LANG__";
    const SYMS = __SYMS__;
    const DURS = __DURS__;
    const SEVS = __SEVS__;
    const CONDS = __CONDS__;
    const REL = __REL__;
    const DEMO_RESULT = __DEMO_RESULT__;
    </script>
    <script src="/static/js/chat/chat-core.js?v=__ASSET_VERSION__"></script>
    <script src="/static/js/chat/assistant.js?v=__ASSET_VERSION__"></script>
    <script src="/static/js/chat/body-map.js?v=__ASSET_VERSION__"></script>
    <script src="/static/js/chat/clarifications.js?v=__ASSET_VERSION__"></script>
    <script src="/static/js/chat/symptom-flow.js?v=__ASSET_VERSION__"></script>
    <script src="/static/js/chat/red-flags.js?v=__ASSET_VERSION__"></script>
    <script src="/static/js/chat/followup.js?v=__ASSET_VERSION__"></script>
    <script src="/static/js/chat/data-quality.js?v=__ASSET_VERSION__"></script>
    <script src="/static/js/chat/analysis-result.js?v=__ASSET_VERSION__"></script>
    <script src="/static/js/chat/result-tracking.js?v=__ASSET_VERSION__"></script>
    <script src="/static/js/chat/result-actions.js?v=__ASSET_VERSION__"></script>
    <script src="/static/js/chat/doctor-summary.js?v=__ASSET_VERSION__"></script>
    <script src="/static/js/chat/chat-boot.js?v=__ASSET_VERSION__"></script>
    """
    return page(t("title_chat"), body
        .replace("__T__", json_for_script(CHAT["ar"] if ar else CHAT["en"], ensure_ascii=False))
        .replace("__DEMO_RESULT__", json_for_script(demo_result, ensure_ascii=False))
        .replace("__LANG__", "ar" if ar else "en")
        .replace("__SYMS__", json_for_script(syms, ensure_ascii=False))
        .replace("__DURS__", json_for_script(durs, ensure_ascii=False))
        .replace("__SEVS__", json_for_script(sevs, ensure_ascii=False))
        .replace("__CONDS__", json_for_script(conds, ensure_ascii=False))
        .replace("__REL__", json_for_script(_related_map(ar), ensure_ascii=False))
        .replace("__ME__", CHAT["ar" if ar else "en"]["me"])
        .replace("__ACCESSIBILITY__", "إمكانية الوصول" if ar else "Accessibility")
        .replace("__ACCESSIBILITY_ARIA__", "فتح خيارات إمكانية الوصول" if ar else "Open accessibility options")
        .replace("__VOICE_INPUT__", "الإدخال الصوتي" if ar else "Voice input")
        .replace("__AUDIO_CONTROLS__", "خيارات القراءة والإدخال الصوتي" if ar else "Read-aloud and voice-input options")
        .replace("__SPEAKER_OFF_ARIA__", "القراءة الصوتية متوقفة. اضغط لتفعيلها." if ar else "Read aloud is off. Press to turn it on.")
        .replace("__MIC_READY_ARIA__", "الميكروفون متوقف. اضغط لبدء تسجيل إجابتك." if ar else "Microphone is off. Press to record your answer.")
        .replace("__VOICE_MODE_TITLE__", CHAT["ar" if ar else "en"]["voice_mode_title"])
        .replace("__VOICE_MODE_OFF__", CHAT["ar" if ar else "en"]["voice_mode_off"])
        .replace("__SPEAK_OFF__", CHAT["ar" if ar else "en"]["speak_off"])
        .replace("__SPEAK_TITLE__", CHAT["ar" if ar else "en"]["speak_title"])
        .replace("__INPUT_PH__", CHAT["ar" if ar else "en"]["input_ph"])
        .replace("__MIC_TITLE__", CHAT["ar" if ar else "en"]["mic_title"])
        .replace("__SEND__", CHAT["ar" if ar else "en"]["send"])
        .replace("__MUTED__", CHAT["ar" if ar else "en"]["muted"])
        .replace("__FLOW_STEP__", "الخطوة 1 من 7" if ar else "Step 1 of 7")
        .replace("__FLOW_DEMO__", "العمر والجنس" if ar else "Age and sex")
        .replace("__VOICE_SP__", CHAT["ar" if ar else "en"]["voice_speaking"])
        .replace("__VOICE_PRIVACY__", "لا يحفظ SymptoSense التسجيل الصوتي؛ يتم إرسال النص الناتج فقط للمعالجة." if ar else "SymptoSense does not store the audio recording; only the resulting transcript is sent for parsing.")
        .replace("__VOICE_STOP__", CHAT["ar" if ar else "en"]["voice_stop"])
        .replace("__VOICE_CANCEL__", CHAT["ar" if ar else "en"]["voice_cancel"]))

