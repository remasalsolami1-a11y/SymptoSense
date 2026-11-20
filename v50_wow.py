from __future__ import annotations

from collections import Counter
from datetime import datetime
from html import escape
import json
from pathlib import Path

import advanced_features
import db
import medical_knowledge
import symptom_combo_intelligence


def _risk_label(risk: str, ar: bool) -> tuple[str, str]:
    risk = (risk or "low").lower()
    mapping = {
        "low": (("منخفض" if ar else "Low"), "low"),
        "medium": (("يحتاج متابعة" if ar else "Follow-up"), "medium"),
        "high": (("عاجل" if ar else "Urgent"), "high"),
        "urgent": (("عاجل" if ar else "Urgent"), "high"),
        "emergency": (("طوارئ" if ar else "Emergency"), "high"),
    }
    return mapping.get(risk, ((escape(risk) or "—"), "medium"))


def _short_date(value: object, ar: bool) -> str:
    s = str(value or "").strip()
    if not s:
        return "—"
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return escape(s[:10])


def render_command_center(*, page, lang: str, account_uid: str, data_uid: str):
    ar = lang == "ar"
    bi = lambda a, e: a if ar else e
    user = db.get_ss_user(account_uid) or {}
    profile = db.load_health_profile(account_uid) or {}
    records = advanced_features.user_analysis_rows(data_uid, limit=50)
    latest = records[0] if records else None
    latest_result = (latest or {}).get("result") or {}
    risk_label, risk_cls = _risk_label(latest_result.get("risk_level") or (latest or {}).get("urgency") or "low", ar)
    latest_syms = ", ".join(str(x) for x in ((latest or {}).get("symptoms") or [])[:3]) or bi("لا يوجد تحليل محفوظ", "No saved analysis")
    latest_date = _short_date((latest or {}).get("timestamp"), ar) if latest else "—"

    bloods = db.get_blood_tests(data_uid, limit=5) or []
    latest_blood = bloods[0] if bloods else None
    blood_date = _short_date((latest_blood or {}).get("timestamp"), ar) if latest_blood else "—"

    meds = db.list_med_plans(data_uid, active_only=True) or []
    today_meds = db.med_plans_today(data_uid) or []
    next_med = None
    for plan in today_meds:
        statuses = plan.get("status") or {}
        for tm in plan.get("times") or []:
            if not statuses.get(tm):
                next_med = (plan.get("med_name") or "—", tm)
                break
        if next_med:
            break

    followup = db.get_latest_followup(data_uid)
    followup_label = bi("لا توجد متابعة بعد", "No follow-up yet")
    if followup:
        out = "new_symptoms" if followup.get("new_sign") else str(followup.get("outcome") or "")
        label_map_ar = {"better":"تحسن", "improved":"تحسن", "same":"كما هي", "worse":"أسوأ", "new_symptoms":"أعراض جديدة"}
        label_map_en = {"better":"Improved", "improved":"Improved", "same":"No change", "worse":"Worse", "new_symptoms":"New symptoms"}
        followup_label = (label_map_ar if ar else label_map_en).get(out, out or followup_label)

    display_name = escape(profile.get("display_name") or user.get("name") or bi("مرحبًا", "Welcome"))
    profile_bits = []
    if profile.get("dob"): profile_bits.append(bi("تاريخ الميلاد محفوظ", "Date of birth saved"))
    if profile.get("allergies"): profile_bits.append(bi("الحساسيات محفوظة", "Allergies saved"))
    if profile.get("medications"): profile_bits.append(bi("الأدوية محفوظة", "Medicines saved"))
    profile_completion = min(100, round((len(profile_bits) / 3) * 100))

    next_med_html = (
        f'<strong>{escape(str(next_med[0]))}</strong><span>{escape(str(next_med[1]))}</span>'
        if next_med else f'<strong>{bi("لا يوجد موعد دواء قادم", "No upcoming medicine time")}</strong><span>{bi("أضف أدويةك إذا رغبت", "Add medicines if you want")}</span>'
    )

    body = r'''
    <main class="cc-page">
      <section class="cc-hero">
        <div class="cc-orb cc-orb-a"></div><div class="cc-orb cc-orb-b"></div>
        <div class="cc-hero-copy">
          <span class="cc-kicker">HEALTH COMMAND CENTER</span>
          <h1>__HELLO__، __NAME__</h1>
          <p>__HERO_P__</p>
          <div class="cc-actions"><a class="cc-primary" href="/chat">__NEW_ANALYSIS__</a><a class="cc-secondary" href="/health-story">__STORY__</a></div>
        </div>
        <div class="cc-pulse" aria-label="__SNAPSHOT__">
          <div class="cc-pulse-ring"><span>__RISK__</span><b>__RISK_LABEL__</b></div>
          <small>__LAST__ · __LATEST_DATE__</small>
        </div>
      </section>

      <section class="cc-strip" aria-label="__QUICK_OVERVIEW__">
        <article><span>🩺</span><div><small>__LAST_ANALYSIS__</small><b>__LATEST_SYMS__</b></div></article>
        <article><span>🧪</span><div><small>__LAST_CBC__</small><b>__BLOOD_DATE__</b></div></article>
        <article><span>💊</span><div><small>__ACTIVE_MEDS__</small><b>__MED_COUNT__</b></div></article>
        <article><span>🔁</span><div><small>__FOLLOWUP__</small><b>__FOLLOWUP_LABEL__</b></div></article>
      </section>

      <section class="cc-grid">
        <article class="cc-card cc-card-feature">
          <div class="cc-card-head"><div><span class="cc-icon">🩺</span><small>__CURRENT_CASE__</small><h2>__LATEST_SYMS__</h2></div><span class="cc-risk __RISK_CLS__">__RISK_LABEL__</span></div>
          <div class="cc-mini-timeline"><i class="done"></i><span>__ANALYZED__</span><i class="done"></i><span>__SAFETY_CHECK__</span><i></i><span>__FOLLOWUP_STEP__</span></div>
          <div class="cc-card-actions">__LATEST_LINK__<a href="/chat">__RUN_AGAIN__</a></div>
        </article>

        <article class="cc-card cc-cbc-card">
          <div class="cc-card-head"><div><span class="cc-icon">🧪</span><small>CBC</small><h2>__CBC_TITLE__</h2></div><span class="cc-status">__BLOOD_DATE__</span></div>
          <div class="cc-bars" aria-hidden="true"><span style="height:56%"></span><span style="height:82%"></span><span style="height:68%"></span><span style="height:92%"></span><span style="height:74%"></span><span style="height:88%"></span></div>
          <p>__CBC_P__</p><a class="cc-link" href="/blood">__OPEN_CBC__ →</a>
        </article>

        <article class="cc-card">
          <div class="cc-card-head"><div><span class="cc-icon">💊</span><small>__MEDS__</small><h2>__MED_COUNT__ __ACTIVE__</h2></div></div>
          <div class="cc-next-med">__NEXT_MED__</div>
          <a class="cc-link" href="/meds">__MANAGE_MEDS__ →</a>
        </article>

        <article class="cc-card">
          <div class="cc-card-head"><div><span class="cc-icon">🧬</span><small>__HEALTH_PROFILE__</small><h2>__PROFILE_STATUS__</h2></div><b class="cc-percent">__PROFILE_COMPLETION__%</b></div>
          <div class="cc-progress"><span style="width:__PROFILE_COMPLETION__%"></span></div>
          <div class="cc-chips">__PROFILE_CHIPS__</div>
          <a class="cc-link" href="/profile">__COMPLETE_PROFILE__ →</a>
        </article>

        <article class="cc-card cc-follow-card">
          <div class="cc-card-head"><div><span class="cc-icon">✨</span><small>SMART FOLLOW-UP</small><h2>__CHECK_AGAIN__</h2></div></div>
          <p>__FOLLOW_P__</p><div class="cc-follow-actions"><a href="/health-story">__VIEW_CHANGES__</a><a href="/chat">__NEW_ANALYSIS__</a></div>
        </article>

        <article class="cc-card cc-privacy-card">
          <div class="cc-card-head"><div><span class="cc-icon">🛡️</span><small>__PRIVACY__</small><h2>__CONTROL__</h2></div><span class="cc-live">● __ACTIVE__</span></div>
          <p>__PRIVACY_P__</p><a class="cc-link" href="/privacy-center">__PRIVACY_CENTER__ →</a>
        </article>
      </section>
    </main>
    '''
    latest_link = f'<a href="/history/{int(latest["id"])}">{bi("عرض التفاصيل", "View details")}</a>' if latest else ''
    chips = ''.join(f'<span>✓ {escape(x)}</span>' for x in profile_bits) or f'<span>{bi("أضف بياناتك باختيارك", "Add information by choice")}</span>'
    repl = {
        "__HELLO__": bi("مرحبًا", "Welcome"), "__NAME__": display_name,
        "__HERO_P__": bi("نظرة واحدة تجمع آخر تحليلاتك، فحوصاتك، أدويتك، والمتابعات التي اخترت حفظها.", "One view for the analyses, lab results, medicines, and follow-ups you chose to save."),
        "__NEW_ANALYSIS__": bi("ابدأ تحليلًا جديدًا", "Start new analysis"), "__STORY__": bi("شاهد قصتي الصحية", "View my health story"),
        "__SNAPSHOT__": bi("ملخص الحالة", "Health snapshot"), "__RISK__": bi("آخر مستوى استعجال", "Latest urgency"), "__RISK_LABEL__": risk_label,
        "__LAST__": bi("آخر تحديث", "Last update"), "__LATEST_DATE__": latest_date,
        "__QUICK_OVERVIEW__": bi("ملخص سريع", "Quick overview"), "__LAST_ANALYSIS__": bi("آخر تحليل", "Latest analysis"), "__LATEST_SYMS__": escape(latest_syms),
        "__LAST_CBC__": bi("آخر CBC", "Latest CBC"), "__BLOOD_DATE__": blood_date, "__ACTIVE_MEDS__": bi("أدوية نشطة", "Active medicines"), "__MED_COUNT__": str(len(meds)),
        "__FOLLOWUP__": bi("آخر متابعة", "Latest follow-up"), "__FOLLOWUP_LABEL__": escape(followup_label), "__CURRENT_CASE__": bi("أحدث حالة محفوظة", "Latest saved case"),
        "__RISK_CLS__": risk_cls, "__ANALYZED__": bi("تم التحليل", "Analyzed"), "__SAFETY_CHECK__": bi("فحص السلامة", "Safety checked"), "__FOLLOWUP_STEP__": bi("المتابعة", "Follow-up"),
        "__LATEST_LINK__": latest_link, "__RUN_AGAIN__": bi("تحليل جديد", "New analysis"), "__CBC_TITLE__": bi("نتائج التحاليل", "Lab results"),
        "__CBC_P__": bi("اعرض نتائج CBC المحفوظة وافهم القيم بصريًا مع إبقاء التفسير توعويًا.", "Review saved CBC results and understand values visually while keeping interpretation educational."),
        "__OPEN_CBC__": bi("فتح تحليل CBC", "Open CBC analysis"), "__MEDS__": bi("الأدوية", "Medicines"), "__ACTIVE__": bi("نشط", "active"), "__NEXT_MED__": next_med_html,
        "__MANAGE_MEDS__": bi("إدارة الأدوية", "Manage medicines"), "__HEALTH_PROFILE__": bi("الملف الصحي", "Health profile"), "__PROFILE_STATUS__": bi("جاهزية السياق", "Context readiness"),
        "__PROFILE_COMPLETION__": str(profile_completion), "__PROFILE_CHIPS__": chips, "__COMPLETE_PROFILE__": bi("إدارة الملف الصحي", "Manage health profile"),
        "__CHECK_AGAIN__": bi("كيف تغيرت حالتك؟", "How has your case changed?"), "__FOLLOW_P__": bi("المتابعة الذكية تقارن ما تدخله أنت ببياناتك السابقة فقط عندما تسمح باستخدامها.", "Smart follow-up compares what you enter with your prior saved data only when you allow its use."),
        "__VIEW_CHANGES__": bi("عرض الرحلة", "View journey"), "__PRIVACY__": bi("الخصوصية", "Privacy"), "__CONTROL__": bi("أنت تتحكم في بياناتك", "You control your data"),
        "__PRIVACY_P__": bi("تستطيع مراجعة ما يتم حفظه واستخدامه في التحليل وتغييره في أي وقت.", "Review what is saved and used in analysis, and change it at any time."), "__PRIVACY_CENTER__": bi("مركز الخصوصية", "Privacy center"),
    }
    for key, value in repl.items():
        body = body.replace(key, str(value))
    return page(bi("مركز صحتي", "Health Command Center"), body, extra_css=COMMAND_CENTER_CSS)


def render_health_story(*, page, lang: str, uid: str):
    ar = lang == "ar"
    bi = lambda a, e: a if ar else e
    events = db.member_timeline(uid, 0, days=3650) or []
    followups = db.get_followups(uid, limit=200) or []
    for fu in followups:
        outcome = str(fu.get("outcome") or "")
        labels = {
            "better": bi("تحسنت الحالة", "Case improved"),
            "improved": bi("تحسنت الحالة", "Case improved"),
            "same": bi("الحالة كما هي", "No major change"),
            "worse": bi("الحالة أسوأ", "Case worsened"),
            "new_symptoms": bi("ظهرت أعراض جديدة", "New symptoms reported"),
        }
        events.append({"date": str(fu.get("timestamp") or "")[:10], "type":"followup", "title":labels.get(outcome, bi("متابعة", "Follow-up")), "detail":bi("متابعة مرتبطة بتحليل محفوظ", "Follow-up linked to a saved analysis"), "record_id":fu.get("record_id")})
    events.sort(key=lambda e: str(e.get("date") or ""), reverse=True)

    counts = Counter(e.get("type") or "other" for e in events)
    analysis_rows = advanced_features.user_analysis_rows(uid, limit=200)
    symptom_counts = Counter()
    for row in analysis_rows:
        for sym in row.get("symptoms") or []:
            symptom_counts[str(sym)] += 1
    common = symptom_counts.most_common(1)[0] if symptom_counts else None

    cards = []
    icon_map = {"analysis":"🩺", "blood":"🧪", "med":"💊", "followup":"✨"}
    label_map = {"analysis":bi("تحليل أعراض", "Symptom analysis"), "blood":bi("CBC", "CBC"), "med":bi("دواء", "Medication"), "followup":bi("متابعة", "Follow-up")}
    for idx, event in enumerate(events[:120]):
        typ = event.get("type") or "other"
        icon = icon_map.get(typ, "•")
        title = event.get("title") if ar else event.get("en_title") or event.get("title")
        detail = escape(str(event.get("detail") or ""))
        date = escape(str(event.get("date") or "—"))
        rid = event.get("id") or event.get("record_id")
        link = f'<a href="/history/{int(rid)}">{bi("عرض التفاصيل", "View details")} →</a>' if typ == "analysis" and rid else ''
        cards.append(f'''<article class="hs-event" data-type="{escape(typ)}"><div class="hs-node"><span>{icon}</span></div><div class="hs-event-card"><div class="hs-event-top"><span class="hs-kind">{escape(label_map.get(typ, typ))}</span><time>{date}</time></div><h3>{escape(str(title or label_map.get(typ, typ)))}</h3>{f'<p>{detail}</p>' if detail else ''}{link}</div></article>''')
    if not cards:
        cards.append(f'<div class="hs-empty"><span>✨</span><h2>{bi("قصتك الصحية تبدأ من أول تحليل", "Your health story starts with your first analysis")}</h2><p>{bi("احفظ ما تختاره من تحليلات وفحوصات لتظهر هنا كرحلة منظمة.", "Save the analyses and tests you choose to build a private, organized timeline here.")}</p><a href="/chat">{bi("ابدأ الآن", "Start now")}</a></div>')

    body = r'''
    <main class="hs-page">
      <section class="hs-hero">
        <div><span class="hs-kicker">HEALTH STORY</span><h1>__TITLE__</h1><p>__SUB__</p></div>
        <div class="hs-hero-badge"><span>__EVENTS_N__</span><b>__EVENTS__</b><small>__PRIVATE__</small></div>
      </section>
      <section class="hs-stats">
        <article><span>🩺</span><b>__AN_N__</b><small>__ANALYSES__</small></article>
        <article><span>🧪</span><b>__CBC_N__</b><small>CBC</small></article>
        <article><span>✨</span><b>__FU_N__</b><small>__FOLLOWUPS__</small></article>
        <article><span>🔎</span><b>__COMMON__</b><small>__COMMON_LABEL__</small></article>
      </section>
      <section class="hs-toolbar"><div class="hs-filter" role="group" aria-label="__FILTER_ARIA__"><button type="button" class="on" data-filter="all">__ALL__</button><button type="button" data-filter="analysis">__ANALYSES__</button><button type="button" data-filter="blood">CBC</button><button type="button" data-filter="followup">__FOLLOWUPS__</button><button type="button" data-filter="med">__MEDS__</button></div><a href="/command-center">__CENTER__ →</a></section>
      <section class="hs-timeline" id="healthStoryTimeline">__CARDS__</section>
    </main>
    <script>
    (function(){const buttons=[...document.querySelectorAll('.hs-filter button')];const events=[...document.querySelectorAll('.hs-event')];buttons.forEach(btn=>btn.addEventListener('click',function(){buttons.forEach(x=>x.classList.remove('on'));this.classList.add('on');const f=this.dataset.filter;events.forEach(ev=>ev.hidden=!(f==='all'||ev.dataset.type===f));}));})();
    </script>
    '''
    common_text = escape(common[0]) if common else bi("—", "—")
    repl = {
        "__TITLE__": bi("قصتي الصحية", "My Health Story"), "__SUB__": bi("خط زمني بصري يجمع فقط ما اخترت حفظه: التحليلات، CBC، الأدوية، والمتابعات.", "A visual timeline containing only what you chose to save: analyses, CBC, medicines, and follow-ups."),
        "__EVENTS_N__": str(len(events)), "__EVENTS__": bi("حدث محفوظ", "saved events"), "__PRIVATE__": bi("خاص بحسابك", "Private to your account"),
        "__AN_N__": str(counts.get("analysis", 0)), "__ANALYSES__": bi("التحليلات", "Analyses"), "__CBC_N__": str(counts.get("blood", 0)), "__FU_N__": str(counts.get("followup", 0)),
        "__FOLLOWUPS__": bi("المتابعات", "Follow-ups"), "__COMMON__": common_text, "__COMMON_LABEL__": bi("أكثر عرض تكرارًا", "Most repeated symptom"),
        "__FILTER_ARIA__": bi("تصفية القصة الصحية", "Filter health story"), "__ALL__": bi("الكل", "All"), "__MEDS__": bi("الأدوية", "Medicines"), "__CENTER__": bi("مركز صحتي", "Command center"), "__CARDS__": ''.join(cards),
    }
    for key, value in repl.items(): body = body.replace(key, str(value))
    return page(bi("قصتي الصحية", "My Health Story"), body, extra_css=HEALTH_STORY_CSS)


def render_competition_dashboard(*, page, lang: str):
    ar = lang == "ar"
    bi = lambda a, e: a if ar else e
    try:
        medical_knowledge.init_schema()
        symptoms = medical_knowledge.list_entities("symptoms", False)
        diseases = medical_knowledge.list_entities("diseases", False)
        sources = medical_knowledge.list_entities("sources", False, verification="verified")
    except Exception:
        symptoms, diseases, sources = [], [], []
    root = Path(__file__).resolve().parent
    # Production Docker images intentionally exclude tests/. Keep the competition
    # dashboard truthful by reading release metrics and synthetic safety fixtures
    # from runtime assets that are shipped with the application. Local source
    # trees still fall back to tests/ for developer convenience.
    try:
        release_metrics = json.loads((root / "release_metrics.json").read_text(encoding="utf-8"))
    except Exception:
        release_metrics = {}
    test_file_count = int(release_metrics.get("test_files") or 0)
    if test_file_count <= 0 and (root / "tests").exists():
        test_file_count = len(list((root / "tests").glob("test_*.py")))
    safety_cases = []
    for safety_path in (root / "safety_cases.json", root / "runtime_data" / "safety_cases.json", root / "tests" / "data" / "safety_cases.json"):
        try:
            safety_cases = json.loads(safety_path.read_text(encoding="utf-8"))
            if isinstance(safety_cases, list) and safety_cases:
                break
        except Exception:
            safety_cases = []

    features = [
        ("🧍", bi("خريطة الجسم التفاعلية", "Interactive Body Map"), bi("اختيار المنطقة ثم إضافة الأعراض بسرعة.", "Choose a body region and add related symptoms quickly."), "/chat"),
        ("🧪", bi("تحليل CBC", "CBC Analysis"), bi("تفسير توعوي للقيم وربط اختياري بتحليل الأعراض.", "Educational value interpretation with optional symptom-analysis linking."), "/blood"),
        ("✨", bi("المتابعة الذكية", "Smart Follow-up"), bi("متابعة تغير الحالة اعتمادًا على البيانات التي يسمح المستخدم بإعادة استخدامها.", "Track change using only prior data the user allows to be reused."), "/chat"),
        ("📚", bi("مصادر قابلة للتتبع", "Traceable Sources"), bi("بطاقات للمصدر وحالة التحقق وآخر مراجعة.", "Source cards with verification and review metadata."), "/sources"),
        ("🛡️", bi("طبقة سلامة مستقلة", "Independent Safety Layer"), bi("فحص علامات الخطر قبل عرض التفاصيل الثانوية.", "Red-flag checks before secondary detail."), "/methodology"),
        ("🌐", bi("عربي + English", "Arabic + English"), bi("واجهة ثنائية اللغة مع فحص ترجمة آلي.", "Bilingual interface with automated translation checks."), "/?choose=1"),
        ("🎯", bi("تحدي الحكم الحي", "Live Judge Challenge"), bi("الحكم يتوقع القرار أولًا ثم يشغّل محرك السلامة الحقيقي على سيناريوهات صناعية.", "The judge predicts first, then runs the real safety engine on synthetic scenarios."), "/admin/judge-challenge"),
        ("🧬", bi("Innovation Lab", "Innovation Lab"), bi("Safety Twin + Knowledge DNA + Arabic NLP Stress Test تعمل على المحرك الحقيقي وبيانات صناعية.", "Safety Twin + Knowledge DNA + Arabic NLP Stress Test on the real engine with synthetic cases."), "/admin/innovation-lab"),
        ("🧩", bi("ذكاء الأنماط المركبة", "Symptom Combo Intelligence"), bi("يفهم تفاعل عدة أعراض معًا كإشارة ترتيب محدودة دون تشخيص أو تغيير قواعد الطوارئ.", "Understands multi-symptom interactions as bounded ranking support without diagnosis or changing emergency rules."), "/admin/innovation-lab"),
    ]
    feature_html = ''.join(f'<article class="cd-feature"><div class="cd-feature-icon">{ic}</div><div><h3>{escape(title)}</h3><p>{escape(desc)}</p><a href="{href}">{bi("استكشف", "Explore")} →</a></div></article>' for ic,title,desc,href in features)

    body = r'''
    <main class="cd-page">
      <section class="cd-hero">
        <div class="cd-grid-bg"></div><div class="cd-glow a"></div><div class="cd-glow b"></div>
        <div class="cd-hero-copy"><span class="cd-kicker">AI · DATA SCIENCE · DIGITAL HEALTH</span><h1>SymptoSense<br><em>Competition Dashboard</em></h1><p>__SUB__</p><div class="cd-actions"><a class="cd-primary" href="/admin/judge-challenge">🎯 __CHALLENGE__</a><a class="cd-secondary" href="/demo">__DEMO__</a><a class="cd-secondary" href="/admin/innovation-lab">Innovation Lab</a><a class="cd-secondary" href="/methodology">__METHOD__</a><a class="cd-secondary" href="/admin">← Admin</a></div><div class="cd-trust"><span>🛡️ __NON_DIAG__</span><span>📚 __VERIFIED__</span><span>🌐 AR / EN</span></div></div>
        <div class="cd-visual"><div class="cd-core"><span>🩺</span><b>SymptoSense</b><small>__CORE__</small></div><div class="cd-float one">🧠 <b>AI</b></div><div class="cd-float two">📊 <b>Data</b></div><div class="cd-float three">🛡️ <b>Safety</b></div><div class="cd-float four">📚 <b>Sources</b></div></div>
      </section>

      <section class="cd-numbers">
        <article><strong data-count="__SYM_N__">0</strong><span>__SYM__</span></article>
        <article><strong data-count="__DIS_N__">0</strong><span>__DIS__</span></article>
        <article><strong data-count="__SRC_N__">0</strong><span>__SRC__</span></article>
        <article><strong data-count="__SAFE_N__">0</strong><span>__SAFE_CASES__</span></article>
        <article><strong data-count="__TEST_N__">0</strong><span>__TEST_FILES__</span></article>
        <article><strong data-count="__COMBO_N__">0</strong><span>__COMBO_L__</span></article>
      </section>

      <section class="cd-section"><div class="cd-section-head"><span>01</span><div><h2>__SHOWCASE__</h2><p>__SHOWCASE_P__</p></div></div><div class="cd-features">__FEATURES__</div></section>

      <section class="cd-quality"><div class="cd-section-head"><span>02</span><div><h2>__QUALITY__</h2><p>__QUALITY_P__</p></div></div><div class="cd-quality-grid"><article><i>✓</i><b>Safety Matrix</b><small>__AUTOMATED__</small></article><article><i>✓</i><b>Accessibility</b><small>axe + Playwright</small></article><article><i>✓</i><b>Translation Gate</b><small>Arabic / English</small></article><article><i>✓</i><b>Source Monitor</b><small>__SOURCE_REVIEW__</small></article><article><i>✓</i><b>Request Tracing</b><small>X-Request-ID</small></article><article><i>✓</i><b>Privacy Controls</b><small>__USER_CONTROL__</small></article></div></section>

      <section class="cd-flow"><div class="cd-section-head"><span>03</span><div><h2>__HOW__</h2><p>__HOW_P__</p></div></div><div class="cd-flowline"><article><b>1</b><span>__F1__</span></article><i>→</i><article><b>2</b><span>__F2__</span></article><i>→</i><article><b>3</b><span>__F3__</span></article><i>→</i><article><b>4</b><span>__F4__</span></article><i>→</i><article><b>5</b><span>__F5__</span></article></div></section>

      <section class="cd-demo"><div><span class="cd-kicker">LIVE EXPERIENCE</span><h2>__TRY_H__</h2><p>__TRY_P__</p></div><a href="/demo">__START_DEMO__ <span>↗</span></a></section>
    </main>
    <script>
    (function(){const items=[...document.querySelectorAll('[data-count]')];if(!('IntersectionObserver'in window)){items.forEach(x=>x.textContent=x.dataset.count);return;}const io=new IntersectionObserver(entries=>entries.forEach(e=>{if(!e.isIntersecting)return;const el=e.target;const target=parseInt(el.dataset.count||'0',10);if(window.matchMedia('(prefers-reduced-motion: reduce)').matches){el.textContent=target;io.unobserve(el);return;}let start=null;function tick(ts){if(!start)start=ts;const p=Math.min(1,(ts-start)/650);el.textContent=Math.round(target*p);if(p<1)requestAnimationFrame(tick);}requestAnimationFrame(tick);io.unobserve(el);}),{threshold:.4});items.forEach(x=>io.observe(x));})();
    </script>
    '''
    repl = {
        "__SUB__": bi("منصة صحية رقمية ثنائية اللغة تجمع تحليل الأعراض، قواعد سلامة مستقلة، قاعدة معرفة موثقة، تجربة مستخدم حديثة، وأدوات هندسية قابلة للاختبار.", "A bilingual digital-health platform combining symptom analysis, an independent safety layer, a curated knowledge base, modern UX, and testable engineering."),
        "__CHALLENGE__": bi("تحدي الحكم", "Judge Challenge"), "__DEMO__": bi("ابدأ التجربة الحية", "Start live demo"), "__METHOD__": bi("استكشف المنهجية", "Explore methodology"), "__NON_DIAG__": bi("غير تشخيصي", "Non-diagnostic"), "__VERIFIED__": bi("مصادر موثقة", "Verified sources"), "__CORE__": bi("منصة صحية ذكية", "Intelligent health platform"),
        "__SYM_N__": str(len(symptoms)), "__SYM__": bi("عرض في قاعدة المعرفة", "knowledge-base symptoms"), "__DIS_N__": str(len(diseases)), "__DIS__": bi("حالة معرفية", "knowledge conditions"), "__SRC_N__": str(len(sources)), "__SRC__": bi("مصدر طبي موثق", "verified medical sources"), "__SAFE_N__": str(len(safety_cases)), "__SAFE_CASES__": bi("حالة Safety Regression", "safety regression cases"), "__TEST_N__": str(test_file_count), "__TEST_FILES__": bi("ملف اختبارات", "test files"), "__COMBO_N__": str(symptom_combo_intelligence.count()), "__COMBO_L__": bi("نمط أعراض مركب", "curated symptom combos"),
        "__SHOWCASE__": bi("ما الذي يجعل التجربة مختلفة؟", "What makes the experience different?"), "__SHOWCASE_P__": bi("نحوّل المكونات التقنية إلى تجربة يراها المستخدم ويفهمها.", "Technical depth translated into an experience users can see and understand."), "__FEATURES__": feature_html,
        "__QUALITY__": bi("الجودة ليست خلف الكواليس فقط", "Quality is visible, not hidden"), "__QUALITY_P__": bi("أدوات آلية تساعد على منع رجوع أخطاء السلامة والواجهة والترجمة مع كل إصدار.", "Automated checks help prevent safety, interface, and translation regressions across releases."), "__AUTOMATED__": bi("اختبارات آلية", "Automated tests"), "__SOURCE_REVIEW__": bi("مراجعة دورية", "Review monitoring"), "__USER_CONTROL__": bi("تحكم المستخدم", "User control"),
        "__HOW__": bi("كيف تمر المعلومة داخل SymptoSense؟", "How information moves through SymptoSense"), "__HOW_P__": bi("مسار واضح يفصل بين الإدخال، السلامة، المطابقة المعرفية، والنتيجة.", "A clear flow separating input, safety, knowledge matching, and result presentation."), "__F1__": bi("إدخال الأعراض", "Symptom input"), "__F2__": bi("فحص السلامة", "Safety check"), "__F3__": bi("مطابقة المعرفة", "Knowledge matching"), "__F4__": bi("السياق والذكاء الاصطناعي", "Context & AI"), "__F5__": bi("نتيجة + مصادر", "Result + sources"),
        "__TRY_H__": bi("شاهد المشروع وهو يعمل، لا تقرأ عنه فقط.", "See the project work — don't just read about it."), "__TRY_P__": bi("جرّب سيناريو تجريبي داخل المحرك الحقيقي بدون حفظ بيانات شخصية.", "Run a demo scenario through the real engine without saving personal data."), "__START_DEMO__": bi("تشغيل Demo", "Launch demo"),
    }
    for key, value in repl.items(): body = body.replace(key, str(value))
    return page(bi("لوحة المسابقة", "Competition Dashboard"), body, extra_css=COMPETITION_CSS)


COMMAND_CENTER_CSS = r'''
.cc-page{width:min(1180px,100%);margin:auto;display:grid;gap:18px}.cc-hero{position:relative;overflow:hidden;min-height:330px;padding:clamp(24px,5vw,54px);border:1px solid #D9E9F3;border-radius:30px;background:linear-gradient(135deg,#F8FCFF 0%,#ECF7FE 58%,#F2FBF7 100%);display:grid;grid-template-columns:minmax(0,1.2fr) minmax(270px,.8fr);align-items:center;gap:28px;box-shadow:0 22px 70px rgba(25,84,126,.09)}.cc-orb{position:absolute;border-radius:50%;filter:blur(3px);opacity:.55}.cc-orb-a{width:280px;height:280px;background:radial-gradient(circle,#A7DDF7,transparent 68%);right:-100px;top:-90px}.cc-orb-b{width:220px;height:220px;background:radial-gradient(circle,#BFEBD7,transparent 68%);left:34%;bottom:-120px}.cc-hero-copy,.cc-pulse{position:relative;z-index:1}.cc-kicker{display:inline-flex;padding:7px 11px;border-radius:999px;background:rgba(255,255,255,.75);border:1px solid #D6E9F4;color:#1E6E9F;font-size:11px;font-weight:900;letter-spacing:.12em}.cc-hero h1{font-size:clamp(34px,5vw,58px);line-height:1.08;color:#123B70;margin:14px 0}.cc-hero p{color:#566a7d;max-width:650px;font-size:15px}.cc-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:22px}.cc-primary,.cc-secondary{min-height:48px;padding:11px 18px;border-radius:14px;font-weight:900;text-decoration:none;display:inline-flex;align-items:center}.cc-primary{background:#1f6fae;color:#fff;box-shadow:0 12px 26px rgba(40,127,193,.2)}.cc-secondary{background:rgba(255,255,255,.78);border:1px solid #CFE3F2;color:#155D8B}.cc-pulse{justify-self:center;text-align:center}.cc-pulse-ring{width:220px;height:220px;border-radius:50%;display:grid;place-content:center;background:radial-gradient(circle,#fff 58%,transparent 59%),conic-gradient(#1f6fae 0 72%,#DCECF5 72% 100%);box-shadow:0 20px 50px rgba(24,91,136,.15)}.cc-pulse-ring span{font-size:11px;color:#566a7d;font-weight:800}.cc-pulse-ring b{font-size:28px;color:#123B70;margin-top:4px}.cc-pulse small{display:block;margin-top:12px;color:#566a7d}.cc-strip{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.cc-strip article{display:flex;align-items:center;gap:11px;padding:15px;border:1px solid #DCE8F0;background:#fff;border-radius:18px;box-shadow:0 6px 18px rgba(22,59,92,.04)}.cc-strip article>span{width:42px;height:42px;display:grid;place-items:center;border-radius:14px;background:#F0F8FD;font-size:20px}.cc-strip small{display:block;color:#718899;font-size:10px;font-weight:800}.cc-strip b{display:block;color:#24445F;margin-top:2px;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.cc-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.cc-card{background:#fff;border:1px solid #DCE8F0;border-radius:22px;padding:20px;box-shadow:0 8px 26px rgba(22,59,92,.055);min-width:0}.cc-card-feature{grid-column:span 2;background:linear-gradient(135deg,#fff,#F8FCFF)}.cc-card-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}.cc-card-head small{display:block;color:#718899;font-size:10px;font-weight:900;letter-spacing:.05em}.cc-card-head h2{font-size:18px;color:#163B5C;margin:4px 0}.cc-icon{font-size:24px;display:block;margin-bottom:8px}.cc-risk,.cc-status,.cc-live{display:inline-flex;padding:6px 10px;border-radius:999px;font-size:10px;font-weight:900}.cc-risk.low{background:#EDF8F2;color:#1E6846}.cc-risk.medium{background:#FFF8E7;color:#7B5A18}.cc-risk.high{background:#FFF1F1;color:#8E3333}.cc-status{background:#F1F7FA;color:#526B7E}.cc-live{background:#EDF8F2;color:#1E6846}.cc-mini-timeline{display:grid;grid-template-columns:auto 1fr auto 1fr auto 1fr;align-items:center;gap:7px;margin:18px 0;color:#566a7d;font-size:11px}.cc-mini-timeline i{width:11px;height:11px;border-radius:50%;background:#D9E5EC}.cc-mini-timeline i.done{background:#42A57A;box-shadow:0 0 0 4px #E8F7EF}.cc-card-actions,.cc-follow-actions{display:flex;gap:8px;flex-wrap:wrap}.cc-card-actions a,.cc-follow-actions a,.cc-link{display:inline-flex;align-items:center;min-height:40px;padding:8px 12px;border-radius:11px;border:1px solid #D5E5EE;background:#F8FCFF;color:#1F6E9F;font-size:11px;font-weight:900;text-decoration:none}.cc-bars{height:94px;display:flex;align-items:flex-end;gap:8px;padding:12px 0}.cc-bars span{flex:1;max-width:30px;border-radius:8px 8px 3px 3px;background:linear-gradient(180deg,#58AFE2,#CDE9F8)}.cc-card p{color:#566a7d;font-size:12px;line-height:1.75}.cc-next-med{display:flex;justify-content:space-between;gap:10px;padding:13px;border-radius:14px;background:#F8FCFF;border:1px solid #E1EDF4;margin:13px 0}.cc-next-med strong{color:#29485F}.cc-next-med span{color:#1f6fae;font-weight:900}.cc-percent{color:#1f6fae;font-size:21px}.cc-progress{height:8px;background:#E6EFF5;border-radius:999px;overflow:hidden;margin:12px 0}.cc-progress span{display:block;height:100%;background:linear-gradient(90deg,#1f6fae,#57B7D9);border-radius:inherit}.cc-chips{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px}.cc-chips span{padding:6px 9px;border-radius:999px;background:#F2F8FB;color:#526B7E;font-size:10px;font-weight:800}.cc-follow-card{background:linear-gradient(135deg,#FAFDFF,#F3F9FF)}.cc-privacy-card{background:linear-gradient(135deg,#FBFEFC,#F4FBF7)}@media(max-width:840px){.cc-hero{grid-template-columns:1fr;text-align:center}.cc-hero-copy p{margin-inline:auto}.cc-actions{justify-content:center}.cc-strip{grid-template-columns:repeat(2,minmax(0,1fr))}.cc-pulse-ring{width:180px;height:180px}.cc-grid{grid-template-columns:1fr}.cc-card-feature{grid-column:auto}}@media(max-width:520px){.cc-page{gap:12px}.cc-hero{padding:24px 16px;border-radius:22px}.cc-hero h1{font-size:34px}.cc-strip{grid-template-columns:1fr 1fr;gap:8px}.cc-strip article{padding:12px 9px}.cc-strip article>span{width:36px;height:36px}.cc-strip b{font-size:11px}.cc-card{padding:16px;border-radius:18px}.cc-mini-timeline{grid-template-columns:auto 1fr}.cc-mini-timeline i:nth-of-type(n+2),.cc-mini-timeline i:nth-of-type(n+2)+span{display:none}}@media(prefers-reduced-motion:reduce){.cc-page *{animation:none!important;transition:none!important}}
'''

HEALTH_STORY_CSS = r'''
.hs-page{width:min(1060px,100%);margin:auto;display:grid;gap:16px}.hs-hero{position:relative;overflow:hidden;padding:clamp(24px,4vw,42px);border:1px solid #DCE8F0;border-radius:28px;background:linear-gradient(135deg,#F8FCFF,#EFF8FD 55%,#F8FCFA);display:flex;justify-content:space-between;align-items:center;gap:24px;box-shadow:0 16px 50px rgba(22,59,92,.07)}.hs-hero:after{content:'';position:absolute;width:280px;height:280px;border-radius:50%;background:radial-gradient(circle,rgba(83,183,217,.18),transparent 68%);right:-100px;bottom:-140px}.hs-kicker{font-size:11px;letter-spacing:.14em;color:#1f6fae;font-weight:900}.hs-hero h1{font-size:clamp(31px,4vw,48px);color:#123B70;margin:8px 0}.hs-hero p{color:#566a7d;max-width:650px}.hs-hero-badge{position:relative;z-index:1;width:160px;height:160px;flex:none;border-radius:50%;display:grid;place-content:center;text-align:center;background:#fff;border:1px solid #D5E7F1;box-shadow:0 16px 35px rgba(29,93,136,.11)}.hs-hero-badge span{font-size:34px;font-weight:900;color:#1f6fae}.hs-hero-badge b{font-size:11px;color:#29485F}.hs-hero-badge small{color:#718899;font-size:9px;margin-top:4px}.hs-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.hs-stats article{padding:17px;border:1px solid #DCE8F0;border-radius:18px;background:#fff;display:grid;gap:2px;box-shadow:0 5px 16px rgba(22,59,92,.035)}.hs-stats span{font-size:20px}.hs-stats b{font-size:20px;color:#163B5C;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.hs-stats small{color:#718899;font-size:10px}.hs-toolbar{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;padding:12px 14px;border:1px solid #DCE8F0;border-radius:17px;background:#fff}.hs-filter{display:flex;gap:6px;flex-wrap:wrap}.hs-filter button{border:0;background:#F2F7FA;color:#526B7E;border-radius:999px;padding:7px 11px;font-size:10.5px;font-weight:900;cursor:pointer}.hs-filter button.on{background:#1f6fae;color:#fff}.hs-toolbar>a{color:#1f6fae;font-weight:900;font-size:11px;text-decoration:none}.hs-timeline{position:relative;display:grid;gap:0;padding:8px 0}.hs-timeline:before{content:'';position:absolute;top:18px;bottom:18px;inset-inline-start:32px;width:2px;background:linear-gradient(#9CCCE7,#DCE8F0)}.hs-event{position:relative;display:grid;grid-template-columns:66px minmax(0,1fr);gap:12px;padding:8px 0}.hs-event[hidden]{display:none}.hs-node{position:relative;z-index:1;display:flex;justify-content:center;padding-top:16px}.hs-node span{width:42px;height:42px;border-radius:14px;display:grid;place-items:center;background:#fff;border:1px solid #CFE3F2;box-shadow:0 6px 16px rgba(22,59,92,.08);font-size:19px}.hs-event-card{background:#fff;border:1px solid #DCE8F0;border-radius:20px;padding:17px 18px;box-shadow:0 7px 22px rgba(22,59,92,.045);transition:transform .18s ease,border-color .18s ease}.hs-event-card:hover{transform:translateY(-2px);border-color:#BFD9EA}.hs-event-top{display:flex;align-items:center;justify-content:space-between;gap:10px}.hs-kind{font-size:9.5px;font-weight:900;letter-spacing:.04em;color:#1f6fae;background:#EAF5FC;border-radius:999px;padding:5px 8px}.hs-event time{font-size:10px;color:#718899}.hs-event h3{margin:9px 0 4px;color:#163B5C;font-size:15px}.hs-event p{margin:0;color:#566a7d;font-size:12px}.hs-event a{display:inline-flex;margin-top:10px;color:#1f6fae;font-size:11px;font-weight:900;text-decoration:none}.hs-empty{margin-left:66px;text-align:center;padding:38px;border:1px dashed #C8DFEC;border-radius:22px;background:#F9FCFE}.hs-empty>span{font-size:38px}.hs-empty h2{color:#163B5C}.hs-empty p{color:#566a7d}.hs-empty a{display:inline-flex;padding:10px 15px;border-radius:12px;background:#1f6fae;color:#fff;text-decoration:none;font-weight:900}@media(max-width:700px){.hs-hero{align-items:flex-start;flex-direction:column}.hs-hero-badge{width:130px;height:130px}.hs-stats{grid-template-columns:1fr 1fr}.hs-toolbar{align-items:flex-start;flex-direction:column}.hs-filter{overflow-x:auto;flex-wrap:nowrap;width:100%;padding-bottom:3px}.hs-filter button{white-space:nowrap}.hs-event{grid-template-columns:52px minmax(0,1fr);gap:7px}.hs-timeline:before{inset-inline-start:25px}.hs-node span{width:36px;height:36px;border-radius:12px}.hs-event-card{padding:14px}.hs-empty{margin-left:0}}@media(prefers-reduced-motion:reduce){.hs-event-card{transition:none}}
'''

COMPETITION_CSS = r'''
.cd-page{width:min(1180px,100%);margin:auto;display:grid;gap:22px}.cd-hero{position:relative;overflow:hidden;min-height:540px;padding:clamp(30px,5vw,64px);border-radius:32px;border:1px solid #CFE0EC;background:linear-gradient(135deg,#071C31 0%,#0C3156 56%,#0A4B55 100%);color:#fff;display:grid;grid-template-columns:minmax(0,1.1fr) minmax(340px,.9fr);align-items:center;gap:36px;box-shadow:0 30px 80px rgba(3,26,47,.22)}.cd-grid-bg{position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.035) 1px,transparent 1px);background-size:34px 34px;mask-image:linear-gradient(to bottom,#000,transparent)}.cd-glow{position:absolute;border-radius:50%;filter:blur(6px)}.cd-glow.a{width:380px;height:380px;background:radial-gradient(circle,rgba(42,162,239,.28),transparent 68%);right:-120px;top:-120px}.cd-glow.b{width:320px;height:320px;background:radial-gradient(circle,rgba(49,207,166,.2),transparent 68%);left:30%;bottom:-180px}.cd-hero-copy,.cd-visual{position:relative;z-index:1}.cd-kicker{display:inline-flex;padding:7px 11px;border-radius:999px;border:1px solid rgba(255,255,255,.18);background:rgba(255,255,255,.07);font-size:10px;font-weight:900;letter-spacing:.16em;color:#A9DDF7}.cd-hero h1{font-size:clamp(40px,6vw,72px);line-height:.98;margin:16px 0 20px;letter-spacing:-.045em}.cd-hero h1 em{font-style:normal;color:#72D0F4}.cd-hero p{color:#BCD0DF;max-width:690px;font-size:15px}.cd-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:24px}.cd-primary,.cd-secondary{min-height:50px;padding:11px 18px;border-radius:14px;text-decoration:none;font-weight:900;display:inline-flex;align-items:center}.cd-primary{background:#fff;color:#0C3156}.cd-secondary{border:1px solid rgba(255,255,255,.22);background:rgba(255,255,255,.07);color:#fff}.cd-trust{display:flex;gap:8px;flex-wrap:wrap;margin-top:18px}.cd-trust span{font-size:9.5px;color:#BFD6E6;padding:6px 9px;border-radius:999px;background:rgba(255,255,255,.055)}.cd-visual{min-height:380px;display:grid;place-items:center}.cd-core{width:220px;height:220px;border-radius:50%;display:grid;place-content:center;text-align:center;background:radial-gradient(circle at 40% 30%,#1F6090,#0C3156 62%,#081D31);border:1px solid rgba(255,255,255,.18);box-shadow:0 0 0 24px rgba(59,167,226,.04),0 0 0 48px rgba(59,167,226,.025),0 30px 60px rgba(0,0,0,.22)}.cd-core span{font-size:44px}.cd-core b{font-size:20px}.cd-core small{color:#9EC6DB}.cd-float{position:absolute;min-width:112px;padding:13px;border-radius:16px;border:1px solid rgba(255,255,255,.15);background:rgba(255,255,255,.09);backdrop-filter:blur(12px);box-shadow:0 18px 35px rgba(0,0,0,.16);font-size:12px}.cd-float.one{left:0;top:44px}.cd-float.two{right:2px;top:82px}.cd-float.three{left:18px;bottom:38px}.cd-float.four{right:24px;bottom:46px}.cd-numbers{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px}.cd-numbers article{padding:21px 14px;border-radius:20px;background:#fff;border:1px solid #DCE8F0;text-align:center;box-shadow:0 6px 18px rgba(22,59,92,.04)}.cd-numbers strong{display:block;font-size:32px;color:#123B70}.cd-numbers span{display:block;color:#718899;font-size:10px;font-weight:800}.cd-section,.cd-quality,.cd-flow{padding:clamp(22px,4vw,36px);border:1px solid #DCE8F0;border-radius:26px;background:#fff}.cd-section-head{display:flex;gap:14px;align-items:flex-start;margin-bottom:20px}.cd-section-head>span{width:38px;height:38px;display:grid;place-items:center;border-radius:12px;background:#EAF5FC;color:#1f6fae;font-weight:900}.cd-section-head h2{margin:0;color:#163B5C;font-size:clamp(23px,3vw,32px)}.cd-section-head p{margin:5px 0 0;color:#718899}.cd-features{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.cd-feature{display:grid;grid-template-columns:54px minmax(0,1fr);gap:12px;padding:17px;border:1px solid #E0EBF2;border-radius:18px;background:linear-gradient(135deg,#fff,#FAFDFF)}.cd-feature-icon{width:52px;height:52px;border-radius:16px;background:#EEF8FD;display:grid;place-items:center;font-size:24px}.cd-feature h3{margin:0;color:#24445F;font-size:15px}.cd-feature p{margin:4px 0;color:#718899;font-size:11.5px}.cd-feature a{color:#1f6fae;font-weight:900;font-size:10.5px;text-decoration:none}.cd-quality{background:linear-gradient(135deg,#F9FCFE,#F5FAFD)}.cd-quality-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.cd-quality-grid article{padding:15px;border-radius:16px;background:#fff;border:1px solid #DCE8F0;display:grid;grid-template-columns:30px 1fr;align-items:center;gap:3px 8px}.cd-quality-grid i{grid-row:1/3;width:28px;height:28px;border-radius:50%;display:grid;place-items:center;background:#EDF8F2;color:#1E6846;font-style:normal;font-weight:900}.cd-quality-grid b{font-size:12px;color:#29485F}.cd-quality-grid small{font-size:9.5px;color:#718899}.cd-flowline{display:grid;grid-template-columns:1fr auto 1fr auto 1fr auto 1fr auto 1fr;align-items:center;gap:8px}.cd-flowline article{padding:15px;border-radius:16px;background:#F8FCFF;border:1px solid #DCE8F0;text-align:center}.cd-flowline article b{width:30px;height:30px;border-radius:10px;background:#1f6fae;color:#fff;display:grid;place-items:center;margin:0 auto 8px}.cd-flowline article span{font-size:10.5px;font-weight:800;color:#526B7E}.cd-flowline>i{color:#9BBFD4}.cd-demo{padding:clamp(26px,4vw,42px);border-radius:26px;background:linear-gradient(135deg,#0C3156,#0B5663);color:#fff;display:flex;justify-content:space-between;align-items:center;gap:20px}.cd-demo h2{margin:8px 0;color:#fff;font-size:clamp(24px,3vw,36px)}.cd-demo p{color:#BBD4DF}.cd-demo>a{display:inline-flex;gap:10px;align-items:center;min-height:54px;padding:12px 18px;border-radius:15px;background:#fff;color:#0C3156;font-weight:900;text-decoration:none;white-space:nowrap}.cd-demo>a span{font-size:20px}@media(max-width:900px){.cd-hero{grid-template-columns:1fr;min-height:0}.cd-visual{min-height:320px}.cd-numbers{grid-template-columns:repeat(3,minmax(0,1fr))}.cd-quality-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.cd-flowline{grid-template-columns:1fr}.cd-flowline>i{transform:rotate(90deg);text-align:center}.cd-demo{align-items:flex-start;flex-direction:column}}@media(max-width:600px){.cd-page{gap:14px}.cd-hero{padding:28px 17px;border-radius:23px}.cd-hero h1{font-size:42px}.cd-visual{min-height:280px}.cd-core{width:170px;height:170px}.cd-float{min-width:96px;padding:10px;font-size:10px}.cd-numbers{grid-template-columns:repeat(2,minmax(0,1fr))}.cd-numbers article{padding:17px 10px}.cd-numbers strong{font-size:28px}.cd-features,.cd-quality-grid{grid-template-columns:1fr}.cd-section,.cd-quality,.cd-flow{padding:20px 14px;border-radius:20px}.cd-feature{grid-template-columns:46px minmax(0,1fr);padding:14px}.cd-feature-icon{width:44px;height:44px}.cd-demo{padding:24px 17px}.cd-demo>a{width:100%;justify-content:center}}@media(prefers-reduced-motion:reduce){.cd-page *{animation:none!important;transition:none!important}}
'''
