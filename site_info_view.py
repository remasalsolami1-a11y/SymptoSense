"""Public combined site-information renderer.

Extracted from the Flask monolith so public content can evolve without making
``webapp.py`` harder to audit. Route wiring remains in ``webapp.py``.
"""

def render_site_info_page(*, lang, page, medical_knowledge, logger):
    """Single public competition-friendly page collecting the project's key information."""
    from html import escape
    ar = lang == "ar"
    bi = lambda a, e: a if ar else e

    # Reuse the verified medical-source store so this page stays in sync with /sources.
    try:
        medical_knowledge.init_schema()
        source_rows = medical_knowledge.list_entities("sources", False, verification="verified")
    except Exception:
        logger.warning("Handled exception in site_info; fallback applied")
        source_rows = []

    type_labels = {
        "government": bi("جهة حكومية", "Government health authority"),
        "international_organization": bi("منظمة صحية دولية", "International health organization"),
        "national_health_service": bi("خدمة صحية وطنية", "National health service"),
        "academic_medical_institution": bi("مؤسسة طبية أكاديمية", "Academic medical institution"),
        "clinical_guideline_body": bi("جهة إرشادات سريرية", "Clinical guideline body"),
        "other_trusted_source": bi("مصدر صحي موثوق", "Trusted health source"),
        "trusted": bi("مصدر صحي موثوق", "Trusted health source"),
    }
    english_names = {"saudi-moh": "Saudi Ministry of Health"}
    source_cards = []
    for src in source_rows:
        slug = src.get("slug") or ""
        name = english_names.get(slug) if not ar else None
        name = escape(name or src.get("source_name") or src.get("organization") or "")
        description = escape((src.get("description_ar") if ar else src.get("description_en")) or "")
        url = escape(src.get("official_url") or "", quote=True)
        label = escape(type_labels.get(src.get("source_type") or "trusted", type_labels["trusted"]))
        verified = escape(str(src.get("last_verified") or ""))
        verified_html = (f'<small>{bi("آخر تحقق", "Last verified")}: {verified}</small>' if verified else "")
        link_html = (f'<a href="{url}" target="_blank" rel="noopener noreferrer">{bi("الموقع الرسمي ↗", "Official site ↗")}</a>' if url else "")
        source_cards.append(f'''<article class="si-source"><span>{label}</span><h3>{name}</h3><p>{description}</p>{verified_html}{link_html}</article>''')
    sources_html = "".join(source_cards) or ('<p class="si-muted">%s</p>' % bi("لا توجد مصادر موثقة متاحة للعرض حاليًا.", "No verified sources are currently available to display."))

    body = r'''
    <main class="site-info-page" aria-labelledby="siteInfoTitle">
      <section class="si-hero">
        <span class="si-kicker">AI + Data Science + Digital Health</span>
        <h1 id="siteInfoTitle">__TITLE__</h1>
        <p>__INTRO__</p>
        <nav class="si-jumps" aria-label="__JUMP_ARIA__">
          <a href="#about">__NAV_ABOUT__</a><a href="#method">__NAV_METHOD__</a><a href="#privacy">__NAV_PRIVACY__</a><a href="#terms">__NAV_TERMS__</a><a href="#sources">__NAV_SOURCES__</a>
        </nav>
      </section>

      <section class="si-section" id="about">
        <div class="si-heading"><span>01</span><div><h2>👤 __ABOUT_H__</h2><p>__ABOUT_SUB__</p></div></div>
        <div class="si-about-grid">
          <article class="si-card"><h3>SymptoSense 🩺</h3><p>__WHAT__</p></article>
          <article class="si-card"><h3>__CREATOR_H__</h3><p>__CREATOR_P__</p></article>
          <article class="si-card"><h3>__PURPOSE_H__</h3><p>__PURPOSE_P__</p></article>
        </div>
      </section>

      <section class="si-section" id="method">
        <div class="si-heading"><span>02</span><div><h2>🧠 __METHOD_H__</h2><p>__METHOD_SUB__</p></div></div>
        <div class="si-flow">
          <article><b>1</b><h3>__M1__</h3><p>__M1P__</p></article>
          <article><b>2</b><h3>__M2__</h3><p>__M2P__</p></article>
          <article><b>3</b><h3>__M3__</h3><p>__M3P__</p></article>
          <article><b>4</b><h3>__M4__</h3><p>__M4P__</p></article>
        </div>
        <div class="si-note"><strong>__SAFETY_H__</strong><p>__SAFETY_P__</p></div>
      </section>

      <section class="si-section" id="privacy">
        <div class="si-heading"><span>03</span><div><h2>🔒 __PRIVACY_H__</h2><p>__PRIVACY_SUB__</p></div></div>
        <div class="si-list-grid">
          <article class="si-card"><h3>__PC1H__</h3><p>__PC1P__</p></article>
          <article class="si-card"><h3>__PC2H__</h3><p>__PC2P__</p></article>
          <article class="si-card"><h3>__PC3H__</h3><p>__PC3P__</p></article>
          <article class="si-card"><h3>__PC4H__</h3><p>__PC4P__</p></article>
          <article class="si-card"><h3>__PC5H__</h3><p>__PC5P__</p></article>
          <article class="si-card"><h3>__PC6H__</h3><p>__PC6P__</p></article>
        </div>
      </section>

      <section class="si-section" id="terms">
        <div class="si-heading"><span>04</span><div><h2>📄 __TERMS_H__</h2><p>__TERMS_SUB__</p></div></div>
        <div class="si-terms">
          <article><span>🩺</span><div><h3>__T1H__</h3><p>__T1P__</p></div></article>
          <article><span>🚑</span><div><h3>__T2H__</h3><p>__T2P__</p></div></article>
          <article><span>💊</span><div><h3>__T3H__</h3><p>__T3P__</p></div></article>
          <article><span>🤝</span><div><h3>__T4H__</h3><p>__T4P__</p></div></article>
        </div>
      </section>

      <section class="si-section" id="sources">
        <div class="si-heading"><span>05</span><div><h2>📚 __SOURCES_H__</h2><p>__SOURCES_SUB__</p></div></div>
        <div class="si-sources">__SOURCES_HTML__</div>
      </section>

      <section class="si-final">
        <div><strong>__FINAL_H__</strong><p>__FINAL_P__</p></div>
        <a class="btn pri" href="/community-dashboard">__COMMUNITY__</a>
      </section>
    </main>
    '''
    vals = {
        "__TITLE__": bi("معلومات SymptoSense", "About SymptoSense"),
        "__INTRO__": bi("صفحة واحدة تجمع فكرة المشروع، المنهجية، الخصوصية، شروط الاستخدام، والمصادر الطبية الموثوقة.", "One page bringing together the project idea, methodology, privacy, terms of use, and trusted medical sources."),
        "__JUMP_ARIA__": bi("التنقل داخل معلومات الموقع", "Navigate site information"),
        "__NAV_ABOUT__": bi("من نحن", "About"), "__NAV_METHOD__": bi("المنهجية", "Methodology"), "__NAV_PRIVACY__": bi("الخصوصية", "Privacy"), "__NAV_TERMS__": bi("الشروط", "Terms"), "__NAV_SOURCES__": bi("المصادر", "Sources"),
        "__ABOUT_H__": bi("عن المشروع", "About the project"), "__ABOUT_SUB__": bi("الفكرة والهدف ومن يقف خلف تطوير SymptoSense.", "The idea, purpose, and creator behind SymptoSense."),
        "__WHAT__": bi("مساعد صحي ذكي يساعد المستخدم على فهم الأعراض، تقييم مستوى الخطورة، والتعرّف على الخطوة التالية بطريقة مبسطة وتوعوية دون تقديم تشخيص طبي قطعي.", "An intelligent health assistant that helps users understand symptoms, assess risk level, and identify an appropriate next step through simple, educational guidance without providing a definitive medical diagnosis."),
        "__CREATOR_H__": bi("صاحبة الفكرة", "Creator"), "__CREATOR_P__": bi("ريماس حميد السلمي — طالبة علوم البيانات وتحليلها، وصاحبة فكرة SymptoSense. يجمع المشروع بين علوم البيانات والذكاء الاصطناعي والصحة الرقمية.", "Remas Hameed Alsolami — Data Science and Analytics student and creator of SymptoSense. The project brings together data science, AI, and digital health."),
        "__PURPOSE_H__": bi("الهدف", "Purpose"), "__PURPOSE_P__": bi("تحويل وصف الأعراض إلى تجربة واضحة تساعد المستخدم على فهم مستوى الخطورة وما الذي يمكن فعله بعد ذلك، مع إبراز علامات الخطر والمصادر الموثوقة.", "To turn symptom descriptions into a clear experience that helps users understand risk and what to do next, while surfacing red flags and trusted sources."),
        "__METHOD_H__": bi("كيف يعمل SymptoSense؟", "How SymptoSense works"), "__METHOD_SUB__": bi("منهجية منظمة تجمع السياق، التحليل، قواعد الأمان والمصادر الطبية.", "A structured methodology combining context, analysis, safety rules, and medical sources."),
        "__M1__": bi("جمع السياق", "Collect context"), "__M1P__": bi("الأعراض والعمر والجنس والمدة والشدة مع أسئلة متابعة تتكيف مع الإجابات.", "Symptoms, age, sex, duration, and severity, with follow-up questions that adapt to responses."),
        "__M2__": bi("تحليل منظم", "Structured analysis"), "__M2P__": bi("مطابقة المعلومات المدخلة مع قاعدة المعرفة وقواعد الخطورة المتاحة.", "Submitted information is matched against the available knowledge base and risk rules."),
        "__M3__": bi("تقييم الخطورة", "Risk triage"), "__M3P__": bi("إظهار مستوى الخطورة وعلامات الخطر بوضوح قبل التفاصيل الثانوية.", "Risk level and warning signs are surfaced clearly before secondary detail."),
        "__M4__": bi("الخطوة التالية", "Next-step guidance"), "__M4P__": bi("عرض احتمالات توعوية غير تشخيصية، إرشاد عملي، ومصادر طبية ذات صلة.", "Non-diagnostic educational possibilities, practical guidance, and relevant medical sources are presented."),
        "__SAFETY_H__": bi("السلامة أولًا", "Safety first"), "__SAFETY_P__": bi("إذا ظهرت علامات خطر، يقدّم النظام تنبيهًا واضحًا للرعاية العاجلة. النتيجة لا تؤكد مرضًا ولا تنفيه ولا تستبدل الطبيب أو الطوارئ.", "When red flags are detected, the system clearly directs the user toward urgent care. Results neither confirm nor rule out disease and do not replace clinicians or emergency services."),
        "__PRIVACY_H__": bi("الخصوصية وحماية البيانات", "Privacy & data protection"), "__PRIVACY_SUB__": bi("مبادئ واضحة حول ما يُجمع وما يُحفظ وكيف يتحكم المستخدم ببياناته.", "Clear principles for what is collected, what is stored, and how users control their data."),
        "__PC1H__": bi("بيانات الحساب", "Account data"), "__PC1P__": bi("عند إنشاء حساب، تُستخدم بيانات أساسية مثل الاسم والبريد الإلكتروني، وتُحفظ كلمة المرور باستخدام تجزئة آمنة ولا تُخزن كنص قابل للقراءة.", "When an account is created, basic details such as name and email are used, while passwords are stored as secure hashes rather than readable text."),
        "__PC2H__": bi("البيانات الصحية", "Health information"), "__PC2P__": bi("لا تُطلب بيانات صحية أثناء التسجيل. تُعالج المعلومات الصحية عندما يُدخلها المستخدم داخل الخدمة أو يختار حفظها.", "Health data is not requested at sign-up. It is processed when a user enters it in a service or explicitly chooses to save it."),
        "__PC3H__": bi("التحليلات الاختيارية", "Optional analytics"), "__PC3P__": bi("إحصاءات الاستخدام الاختيارية لا تُحفظ إلا بعد موافقة المستخدم، وتُستخدم بصورة مجمعة ومجهولة الهوية قدر الإمكان.", "Optional usage analytics are stored only with user consent and are used in aggregated, anonymized form where possible."),
        "__PC4H__": bi("خدمات الذكاء الاصطناعي", "AI services"), "__PC4P__": bi("عند استخدام بعض وظائف المساعد أو التحليل قد يُرسل النص اللازم إلى مزود الذكاء الاصطناعي المهيأ للمشروع. يُنصح بعدم إدخال معرفات شخصية داخل وصف الحالة.", "For some assistant or analysis functions, the text needed to generate a response may be sent to the AI provider configured for the project. Users should avoid including personal identifiers in health descriptions."),
        "__PC5H__": bi("التحكم والحذف", "Control & deletion"), "__PC5P__": bi("يمكن للمستخدم التحكم في البيانات المحفوظة ومسح السجل أو حذف البيانات الصحية والحساب من أدوات الخصوصية المتاحة.", "Users can manage stored information, clear history, or delete health data and their account using the available privacy controls."),
        "__PC6H__": bi("نتائج الاختبار الأولي", "Pilot results"), "__PC6P__": bi("لوحة الاختبار الأولي تعرض أرقامًا مجمعة فقط في نسخة المسابقة، وتبقى التعليقات الفردية مخفية افتراضيًا. لا تُعرض أسماء أو عناوين بريد أو سجلات صحية شخصية.", "The pilot dashboard shows aggregate results only in the competition build; individual comments stay hidden by default. Names, emails, and personal health records are never shown."),
        "__TERMS_H__": bi("شروط الاستخدام", "Terms of use"), "__TERMS_SUB__": bi("النقاط الأساسية لاستخدام SymptoSense بصورة آمنة ومسؤولة.", "The core rules for using SymptoSense safely and responsibly."),
        "__T1H__": bi("ليس أداة تشخيص", "Not a diagnostic tool"), "__T1P__": bi("النتائج احتمالات تثقيفية قابلة للخطأ ولا تؤكد مرضًا أو تنفيه.", "Results are fallible educational possibilities and neither confirm nor rule out disease."),
        "__T2H__": bi("الحالات العاجلة", "Urgent situations"), "__T2P__": bi("عند وجود علامة خطر أو تدهور الحالة، يجب طلب الرعاية العاجلة بدل انتظار نتيجة الموقع.", "If danger signs appear or the condition worsens, urgent care should be sought instead of waiting for a website result."),
        "__T3H__": bi("الأدوية", "Medicines"), "__T3P__": bi("لا تغيّر دواءً موصوفًا أو جرعته اعتمادًا على نتيجة SymptoSense دون الرجوع إلى مختص.", "Do not change a prescribed medicine or dose based on a SymptoSense result without professional advice."),
        "__T4H__": bi("الاستخدام المسؤول", "Responsible use"), "__T4P__": bi("لا تدخل بيانات تعريفية لشخص آخر دون إذنه، وتخضع المصادر الخارجية لسياسات الجهات المالكة لها.", "Do not enter another person's identifying information without permission; external sources remain subject to their owners' policies."),
        "__SOURCES_H__": bi("المصادر الطبية الموثوقة", "Trusted medical sources"), "__SOURCES_SUB__": bi("يعرض SymptoSense الروابط الرسمية للمصادر الطبية الموثقة المستخدمة في قاعدة المعرفة.", "SymptoSense displays official links for verified medical sources used by the knowledge base."),
        "__SOURCES_HTML__": sources_html,
        "__FINAL_H__": bi("معلومة مهمة", "Important note"), "__FINAL_P__": bi("SymptoSense مشروع للصحة الرقمية والتوعية ودعم اتخاذ الخطوة التالية، وليس بديلًا عن التشخيص أو الرعاية الطبية المهنية.", "SymptoSense is a digital-health project for education and next-step support, not a substitute for diagnosis or professional medical care."),
        "__COMMUNITY__": bi("عرض لوحة المستخدمين", "View community dashboard"),
    }
    for key, value in vals.items():
        body = body.replace(key, str(value))

    css = r'''
    .site-info-page{width:min(1080px,100%);margin:auto;display:grid;gap:18px;scroll-behavior:smooth}.site-info-page section[id]{scroll-margin-top:92px}.si-hero,.si-section,.si-final{border:1px solid #DCE8F0;border-radius:24px;background:#fff;box-shadow:0 6px 22px rgba(31,86,127,.055)}.si-hero{padding:clamp(26px,5vw,48px);text-align:center;background:linear-gradient(135deg,#F8FCFF,#EDF7FC)}.si-kicker{display:inline-flex;padding:7px 12px;border-radius:999px;background:#E8F4FB;color:#1f6fae;font-size:12px;font-weight:900}.si-hero h1{margin:12px 0 8px;color:#163B5C;font-size:clamp(30px,5vw,48px)}.si-hero>p{max-width:760px;margin:0 auto;color:#60788B;line-height:1.9}.si-jumps{display:flex;justify-content:center;gap:8px;flex-wrap:wrap;margin-top:20px}.si-jumps a{padding:8px 12px;border:1px solid #D4E6F0;border-radius:999px;background:#fff;color:#1f6fae;font-size:13px;font-weight:800;text-decoration:none}.si-jumps a:hover{border-color:#1f6fae}.si-section{padding:clamp(20px,4vw,32px)}.si-heading{display:flex;gap:13px;align-items:flex-start;margin-bottom:18px}.si-heading>span{width:38px;height:38px;display:grid;place-items:center;flex:0 0 38px;border-radius:12px;background:#1f6fae;color:#fff;font-weight:900}.si-heading h2{margin:0;color:#163B5C;font-size:clamp(22px,3vw,29px)}.si-heading p{margin:5px 0 0;color:#60788B}.si-about-grid,.si-list-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.si-list-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.si-card,.si-flow article,.si-terms article,.si-source{border:1px solid #DCE8F0;border-radius:18px;background:#F9FCFE;padding:18px}.si-card h3,.si-flow h3,.si-terms h3,.si-source h3{margin:0 0 7px;color:#163B5C}.si-card p,.si-flow p,.si-terms p,.si-source p{margin:0;color:#60788B;line-height:1.8}.si-flow{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.si-flow b{width:32px;height:32px;display:grid;place-items:center;border-radius:50%;background:#1f6fae;color:#fff;margin-bottom:12px}.si-note{margin-top:12px;padding:16px 18px;border-radius:17px;background:#FFF8E8;border:1px solid #F0DDAF}.si-note strong{color:#755710}.si-note p{margin:5px 0 0;color:#6D6247;line-height:1.8}.si-terms{display:grid;grid-template-columns:1fr 1fr;gap:10px}.si-terms article{display:flex;gap:12px;align-items:flex-start}.si-terms article>span{font-size:25px}.si-sources{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.si-source>span{display:inline-flex;padding:5px 8px;border-radius:999px;background:#EAF5FC;color:#1f6fae;font-size:11px;font-weight:900;margin-bottom:10px}.si-source small{display:block;color:#718899;margin-top:8px}.si-source a{display:inline-block;margin-top:12px;color:#1f6fae;font-weight:800;text-decoration:none}.si-final{padding:22px 24px;display:flex;align-items:center;justify-content:space-between;gap:18px;background:#F6FBFE}.si-final strong{color:#163B5C;font-size:18px}.si-final p{margin:5px 0 0;color:#60788B;line-height:1.75}.si-credit{text-align:center;color:#718899;font-size:12.5px;margin:0 0 8px}.si-muted{color:#718899}.site-info-page p{overflow-wrap:anywhere}@media(max-width:820px){.si-about-grid{grid-template-columns:1fr}.si-flow{grid-template-columns:1fr 1fr}.si-list-grid,.si-sources{grid-template-columns:1fr}.si-final{align-items:flex-start;flex-direction:column}.si-final .btn{width:100%;text-align:center}}@media(max-width:520px){.si-hero{padding:24px 16px}.si-section{padding:18px 14px}.si-jumps{gap:6px}.si-jumps a{font-size:12px;padding:7px 10px}.si-flow,.si-terms{grid-template-columns:1fr}.si-heading>span{width:34px;height:34px;flex-basis:34px}.si-card,.si-flow article,.si-terms article,.si-source{padding:15px}.si-final{padding:18px 14px}}
    '''
    return page(bi("معلومات SymptoSense", "About SymptoSense"), body, extra_css=css)
