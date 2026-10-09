from __future__ import annotations

from html import escape

import analysis_core
import medical_knowledge


CHALLENGE_SCENARIOS = [
    {
        "id": "red-flag-combo",
        "icon": "❤️‍🩹",
        "title_ar": "ألم صدر شديد مع ضيق تنفس",
        "title_en": "Severe chest pain with shortness of breath",
        "summary_ar": "شخص بالغ يصف ألمًا شديدًا في الصدر مع صعوبة واضحة في التنفس بدأت اليوم.",
        "summary_en": "An adult reports severe chest pain with clear breathing difficulty that started today.",
        "patient": {"age": 42, "gender": "m", "symptoms": ["ألم صدر شديد", "ضيق شديد بالتنفس"], "duration": "اليوم", "severity": 4, "history_answered": True, "notes": ""},
    },
    {
        "id": "mild-complete",
        "icon": "🤕",
        "title_ar": "صداع خفيف وغثيان",
        "title_en": "Mild headache and nausea",
        "summary_ar": "شخص بالغ لديه صداع خفيف مع غثيان منذ يومين، الشدة 2 من 5، ولا توجد علامة خطر مذكورة.",
        "summary_en": "An adult has a mild headache with nausea for two days, severity 2/5, with no reported red flag.",
        "patient": {"age": 24, "gender": "f", "symptoms": ["صداع", "غثيان"], "duration": "يومين", "severity": 2, "history_answered": True, "notes": ""},
    },
    {
        "id": "review-chest",
        "icon": "🫀",
        "title_ar": "ألم في الصدر دون أعراض إضافية",
        "title_en": "Chest pain without additional symptoms",
        "summary_ar": "شخص بالغ يذكر ألمًا في الصدر بدرجة 2 من 5، بدون ضيق تنفس أو إغماء.",
        "summary_en": "An adult reports chest pain at severity 2/5, without shortness of breath or fainting.",
        "patient": {"age": 35, "gender": "m", "symptoms": ["ألم في الصدر"], "duration": "منذ ساعات", "severity": 2, "history_answered": True, "notes": "لا يوجد ضيق تنفس ولا إغماء"},
    },
    {
        "id": "needs-context",
        "icon": "🧩",
        "title_ar": "عرض معروف لكن المعلومات ناقصة",
        "title_en": "Recognized symptom with missing context",
        "summary_ar": "تم إدخال صداع فقط، لكن مدة الأعراض وشدتها لم تُذكر بعد.",
        "summary_en": "A headache was entered, but duration and severity have not been provided yet.",
        "patient": {"age": 29, "gender": "f", "symptoms": ["صداع"], "duration": "", "severity": None, "history_answered": False, "notes": ""},
    },
    {
        "id": "neuro-red-flag",
        "icon": "🧠",
        "title_ar": "ضعف مفاجئ في جهة واحدة",
        "title_en": "Sudden one-sided weakness",
        "summary_ar": "شخص بالغ يصف ضعفًا مفاجئًا في أحد الأطراف بدأ قبل وقت قصير.",
        "summary_en": "An adult reports sudden weakness in one limb that began recently.",
        "patient": {"age": 58, "gender": "f", "symptoms": ["ضعف مفاجئ بالطرف"], "duration": "منذ ساعة", "severity": 3, "history_answered": True, "notes": ""},
    },
]

_OUTCOMES = {
    "emergency": {"ar": "تصعيد طارئ", "en": "Emergency escalation", "icon": "🚨"},
    "review": {"ar": "مراجعة طبية", "en": "Medical review", "icon": "🩺"},
    "monitor": {"ar": "متابعة غير طارئة", "en": "Non-urgent monitoring", "icon": "🟢"},
    "clarify": {"ar": "طلب معلومات إضافية", "en": "Ask for more information", "icon": "❓"},
}


def public_scenarios(lang: str = "ar") -> list[dict]:
    ar = lang != "en"
    return [
        {
            "id": row["id"],
            "icon": row["icon"],
            "title": row["title_ar"] if ar else row["title_en"],
            "summary": row["summary_ar"] if ar else row["summary_en"],
        }
        for row in CHALLENGE_SCENARIOS
    ]


def _scenario(scenario_id: str) -> dict | None:
    return next((row for row in CHALLENGE_SCENARIOS if row["id"] == str(scenario_id or "")), None)


def evaluate_scenario(scenario_id: str, guess: str, lang: str = "ar") -> dict:
    row = _scenario(scenario_id)
    if not row:
        return {"ok": False, "error": "unknown_scenario"}
    lang = "en" if lang == "en" else "ar"
    patient = dict(row["patient"])
    bundle = medical_knowledge.knowledge_bundle(
        patient.get("symptoms") or [], patient.get("severity", 1), patient.get("age"),
        patient.get("notes", ""), lang, analytics_consent=False,
    )
    triage = analysis_core._triage(patient, lang)
    quality = analysis_core.assess_data_quality(patient, lang, bundle=bundle)
    level = str(triage.get("level") or "monitor")
    kb_risk = str((bundle.get("risk") or {}).get("level") or "low")
    if level == "emergency" or kb_risk == "urgent":
        actual = "emergency"
    elif not quality.get("sufficient"):
        actual = "clarify"
    elif level in {"today", "soon"} or kb_risk == "review":
        actual = "review"
    else:
        actual = "monitor"
    valid_guess = guess if guess in _OUTCOMES else ""
    flags = analysis_core.detect_red_flags(patient.get("symptoms") or [], patient.get("notes") or "", lang)
    missing = [x.get("label") for x in (quality.get("missing") or []) if x.get("required")]
    return {
        "ok": True,
        "scenario_id": row["id"],
        "guess": valid_guess,
        "actual": actual,
        "matched": bool(valid_guess and valid_guess == actual),
        "actual_label": _OUTCOMES[actual][lang],
        "actual_icon": _OUTCOMES[actual]["icon"],
        "triage_level": level,
        "knowledge_risk": kb_risk,
        "triage_label": str(triage.get("label") or ""),
        "reason": str(triage.get("reason") or ""),
        "red_flags": flags[:4],
        "information_complete": bool(quality.get("sufficient")),
        "missing_required": [str(x) for x in missing[:4] if x],
        "quality_score": int(quality.get("score") or 0),
        "quality_meaning": str(quality.get("meaning") or ""),
        "engineering_note": (
            "هذه نتيجة اختبار هندسي بسيناريو صناعي لطبقة السلامة واكتمال المعلومات، وليست تحققًا سريريًا أو تشخيصًا."
            if lang == "ar" else
            "This is an engineering test on a synthetic scenario for safety and information-completeness logic; it is not clinical validation or a diagnosis."
        ),
    }


def render_judge_challenge(*, page, lang: str, csrf_token: str):
    ar = lang != "en"
    scenarios = public_scenarios(lang)
    cards = "".join(
        '<article class="jc-case%s" data-case="%s"><div class="jc-case-num">%d</div><span class="jc-case-icon">%s</span><div><h3>%s</h3><p>%s</p></div></article>'
        % (" on" if i == 0 else "", escape(row["id"], quote=True), i + 1, escape(row["icon"]), escape(row["title"]), escape(row["summary"]))
        for i, row in enumerate(scenarios)
    )
    title = "تحدَّ محرك السلامة" if ar else "Challenge the Safety Engine"
    sub = (
        "خمسة سيناريوهات صناعية. توقّع مسار المحرك، ثم شغّل طبقة السلامة الحقيقية وشاهد لماذا اتخذت هذا المسار."
        if ar else
        "Five synthetic scenarios. Predict the engine path, then run the real safety layer and see why it took that path."
    )
    choose = "ما المسار الذي تتوقعه؟" if ar else "Which path do you predict?"
    run = "شغّل المحرك" if ar else "Run the engine"
    next_label = "الحالة التالية" if ar else "Next scenario"
    reset_label = "إعادة التحدي" if ar else "Restart challenge"
    result_title = "نتيجة المحرك" if ar else "Engine result"
    score_label = "توقعاتك الصحيحة" if ar else "Correct predictions"
    note = (
        "التحدي يقيس قدرتك على توقع سلوك النظام في سيناريوهات صناعية؛ لا يقيس قدرتك على تشخيص مرض."
        if ar else
        "This challenge measures whether you can predict system behavior on synthetic cases; it does not test disease diagnosis."
    )
    outcomes = [
        ("emergency", "🚨", "تصعيد طارئ" if ar else "Emergency escalation"),
        ("review", "🩺", "مراجعة طبية" if ar else "Medical review"),
        ("monitor", "🟢", "متابعة غير طارئة" if ar else "Non-urgent monitoring"),
        ("clarify", "❓", "معلومات إضافية" if ar else "Ask for more information"),
    ]
    outcome_buttons = "".join('<button type="button" class="jc-choice" data-guess="%s"><span>%s</span>%s</button>' % (key, icon, escape(label)) for key, icon, label in outcomes)
    body = '''
    <main class="jc-page">
      <section class="jc-hero">
        <div><span class="jc-kicker">JUDGE CHALLENGE · SAFETY ENGINE</span><h1>__TITLE__</h1><p>__SUB__</p><div class="jc-hero-links"><a href="/admin/competition-dashboard">← Competition Dashboard</a><a href="/admin/innovation-lab">Innovation Lab</a><a href="/admin">Admin</a></div></div>
        <div class="jc-score"><small>__SCORE_LABEL__</small><strong id="jcScore">0 / 0</strong><div class="jc-score-track"><i id="jcScoreBar"></i></div><span id="jcProgress">1 / 5</span></div>
      </section>
      <section class="jc-layout">
        <aside class="jc-cases">__CARDS__</aside>
        <section class="jc-stage">
          <div class="jc-stage-head"><span id="jcStageIcon">__ICON__</span><div><small id="jcStageNo">SCENARIO 01</small><h2 id="jcStageTitle">__FIRST_TITLE__</h2><p id="jcStageSummary">__FIRST_SUMMARY__</p></div></div>
          <div class="jc-question"><h3>__CHOOSE__</h3><div class="jc-choices">__CHOICES__</div></div>
          <button id="jcRun" class="jc-run" type="button" disabled>▶ __RUN__</button>
          <div id="jcResult" class="jc-result" hidden><div class="jc-result-top"><span id="jcResultIcon">✓</span><div><small>__RESULT_TITLE__</small><h3 id="jcResultLabel"></h3></div><b id="jcMatchBadge"></b></div><div id="jcTrace" class="jc-trace"></div><p id="jcEngineeringNote" class="jc-note"></p></div>
          <div class="jc-footer"><button id="jcNext" class="jc-next" type="button" hidden>__NEXT__ →</button><button id="jcReset" class="jc-reset" type="button">↻ __RESET__</button></div>
        </section>
      </section>
      <section class="jc-disclaimer">🧪 __NOTE__</section>
    </main>
    '''
    first = scenarios[0]
    replacements = {
        "__TITLE__": title, "__SUB__": sub, "__SCORE_LABEL__": score_label, "__CARDS__": cards,
        "__ICON__": first["icon"], "__FIRST_TITLE__": first["title"], "__FIRST_SUMMARY__": first["summary"],
        "__CHOOSE__": choose, "__CHOICES__": outcome_buttons, "__RUN__": run, "__RESULT_TITLE__": result_title,
        "__NEXT__": next_label, "__RESET__": reset_label, "__NOTE__": note,
    }
    for key, value in replacements.items():
        body = body.replace(key, value)
    script = r'''
    <script>
    (function(){
      const SCENARIOS=__SCENARIOS__;
      const AR=document.documentElement.lang!=='en';
      let index=0, guess='', correct=0, answered=0;
      const cases=[...document.querySelectorAll('.jc-case')], choices=[...document.querySelectorAll('.jc-choice')];
      const run=document.getElementById('jcRun'), next=document.getElementById('jcNext'), reset=document.getElementById('jcReset'), result=document.getElementById('jcResult');
      function esc(v){return String(v==null?'':v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
      function render(){
        const s=SCENARIOS[index]; guess=''; result.hidden=true; next.hidden=true; run.disabled=true;
        choices.forEach(b=>b.classList.remove('on')); cases.forEach((c,i)=>c.classList.toggle('on',i===index));
        document.getElementById('jcStageIcon').textContent=s.icon; document.getElementById('jcStageNo').textContent='SCENARIO '+String(index+1).padStart(2,'0');
        document.getElementById('jcStageTitle').textContent=s.title; document.getElementById('jcStageSummary').textContent=s.summary;
        document.getElementById('jcProgress').textContent=(index+1)+' / '+SCENARIOS.length;
      }
      choices.forEach(btn=>btn.addEventListener('click',()=>{guess=btn.dataset.guess||'';choices.forEach(b=>b.classList.toggle('on',b===btn));run.disabled=!guess;}));
      run.addEventListener('click',async()=>{
        if(!guess||run.disabled)return;run.disabled=true;run.textContent=AR?'جاري تشغيل طبقة السلامة…':'Running safety layer…';
        try{
          const r=await fetch('/api/admin/judge-challenge/evaluate',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':(document.querySelector('meta[name=admin-csrf]')||{}).content||''},body:JSON.stringify({scenario_id:SCENARIOS[index].id,guess:guess,lang:AR?'ar':'en'})});
          const d=await r.json(); if(!r.ok||!d.ok)throw new Error('challenge_failed');
          answered++; if(d.matched)correct++;
          document.getElementById('jcScore').textContent=correct+' / '+answered;document.getElementById('jcScoreBar').style.width=(answered?Math.round(correct/answered*100):0)+'%';
          document.getElementById('jcResultIcon').textContent=d.actual_icon||'✓';document.getElementById('jcResultLabel').textContent=d.actual_label||'';
          const badge=document.getElementById('jcMatchBadge');badge.textContent=d.matched?(AR?'توقّع صحيح ✓':'Correct prediction ✓'):(AR?'شاهد الفرق':'See the difference');badge.className=d.matched?'ok':'miss';
          let trace='<article><span>1</span><div><b>'+(AR?'مدخل صناعي':'Synthetic input')+'</b><small>'+esc(SCENARIOS[index].summary)+'</small></div></article>';
          trace+='<article><span>2</span><div><b>'+(AR?'اكتمال المعلومات':'Information completeness')+'</b><small>'+(d.information_complete?(AR?'المعلومات الأساسية مكتملة':'Required information complete'):(AR?'يحتاج: ':'Needs: ')+esc((d.missing_required||[]).join(AR?'، ':', ')))+'</small></div></article>';
          trace+='<article><span>3</span><div><b>'+(AR?'طبقة السلامة':'Safety layer')+'</b><small>'+esc(d.triage_label||'')+(d.red_flags&&d.red_flags.length?'<br>'+esc(d.red_flags.join(AR?'، ':', ')):'')+'</small></div></article>';
          trace+='<article><span>4</span><div><b>'+(AR?'المسار النهائي':'Final path')+'</b><small>'+esc(d.actual_label||'')+'</small></div></article>';
          document.getElementById('jcTrace').innerHTML=trace;document.getElementById('jcEngineeringNote').textContent=d.engineering_note||'';
          result.hidden=false; next.hidden=index>=SCENARIOS.length-1; if(index>=SCENARIOS.length-1)next.hidden=true;
          if(index<SCENARIOS.length-1){next.hidden=false;} else {next.hidden=true;}
        }catch(e){alert(AR?'تعذر تشغيل التحدي الآن.':'Unable to run the challenge right now.');}
        run.textContent='▶ '+(AR?'شغّل المحرك':'Run the engine');
      });
      next.addEventListener('click',()=>{if(index<SCENARIOS.length-1){index++;render();}});
      reset.addEventListener('click',()=>{index=0;guess='';correct=0;answered=0;document.getElementById('jcScore').textContent='0 / 0';document.getElementById('jcScoreBar').style.width='0%';render();});
      render();
    })();
    </script>
    '''.replace('__SCENARIOS__', __import__('json').dumps(scenarios, ensure_ascii=False).replace('</', '<\\/'))
    css = r'''
    .jc-page{width:min(1180px,100%);margin:auto;display:grid;gap:18px}.jc-hero{position:relative;overflow:hidden;display:grid;grid-template-columns:minmax(0,1fr) 210px;gap:28px;align-items:center;padding:clamp(28px,5vw,54px);border-radius:30px;background:linear-gradient(135deg,#071C31,#0D3D69 58%,#0A5A64);color:#fff;box-shadow:0 26px 70px rgba(5,31,53,.2)}.jc-hero:after{content:'';position:absolute;width:360px;height:360px;border-radius:50%;right:-140px;top:-170px;background:radial-gradient(circle,rgba(83,197,236,.3),transparent 68%)}.jc-hero>div{position:relative;z-index:1}.jc-kicker{display:inline-flex;padding:7px 10px;border-radius:999px;border:1px solid rgba(255,255,255,.2);background:rgba(255,255,255,.07);color:#9EE2F7;font-size:10px;font-weight:900;letter-spacing:.13em}.jc-hero h1{margin:14px 0 9px;color:#fff;font-size:clamp(34px,5vw,58px);line-height:1}.jc-hero p{max-width:720px;color:#C1D8E6;line-height:1.8}.jc-hero-links{display:flex;gap:8px;flex-wrap:wrap;margin-top:18px}.jc-hero-links a{padding:8px 11px;border-radius:10px;border:1px solid rgba(255,255,255,.18);color:#fff;font-size:10.5px;font-weight:800;text-decoration:none}.jc-score{padding:18px;border:1px solid rgba(255,255,255,.15);border-radius:20px;background:rgba(255,255,255,.08);backdrop-filter:blur(12px)}.jc-score small,.jc-score span{display:block;color:#B8D5E5;font-size:10px}.jc-score strong{display:block;margin:6px 0;color:#fff;font-size:32px}.jc-score-track{height:7px;border-radius:999px;background:rgba(255,255,255,.13);overflow:hidden;margin:10px 0}.jc-score-track i{display:block;width:0;height:100%;background:#72D0F4;border-radius:inherit;transition:width .25s ease}.jc-layout{display:grid;grid-template-columns:320px minmax(0,1fr);gap:14px}.jc-cases,.jc-stage{border:1px solid #DCE8F0;border-radius:24px;background:#fff}.jc-cases{padding:12px;display:grid;gap:8px;align-content:start}.jc-case{display:grid;grid-template-columns:28px 38px 1fr;gap:8px;align-items:center;padding:12px;border-radius:16px;border:1px solid transparent;background:#F9FCFE;cursor:default;transition:.18s}.jc-case.on{border-color:#9ECBE5;background:#EFF8FD;transform:translateY(-1px)}.jc-case-num{width:24px;height:24px;display:grid;place-items:center;border-radius:8px;background:#EAF5FC;color:#1f6fae;font-size:10px;font-weight:900}.jc-case-icon{font-size:24px}.jc-case h3{margin:0;color:#1C405E;font-size:12px}.jc-case p{margin:3px 0 0;color:#718899;font-size:9px;line-height:1.5}.jc-stage{padding:clamp(20px,4vw,34px)}.jc-stage-head{display:grid;grid-template-columns:64px 1fr;gap:15px;align-items:start;padding-bottom:18px;border-bottom:1px solid #E7EFF4}.jc-stage-head>span{width:62px;height:62px;border-radius:19px;background:#EEF8FD;display:grid;place-items:center;font-size:30px}.jc-stage-head small{font-size:9px;color:#1f6fae;font-weight:900;letter-spacing:.1em}.jc-stage-head h2{margin:5px 0;color:#163B5C;font-size:clamp(22px,3vw,31px)}.jc-stage-head p{margin:0;color:#60788B;line-height:1.8}.jc-question{margin-top:20px}.jc-question h3{color:#29485F;font-size:14px}.jc-choices{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.jc-choice{min-height:56px;padding:10px 13px;border:1px solid #DCE8F0;border-radius:15px;background:#F9FCFE;color:#29485F;text-align:start;font:inherit;font-size:12px;font-weight:850;cursor:pointer}.jc-choice span{font-size:18px;margin-inline-end:7px}.jc-choice:hover,.jc-choice.on{border-color:#69ADDA;background:#EAF5FC;color:#155D8B}.jc-run{width:100%;min-height:54px;margin-top:14px;border:0;border-radius:15px;background:linear-gradient(135deg,#1f6fae,#155D8B);color:#fff;font:inherit;font-weight:900;cursor:pointer}.jc-run:disabled{opacity:.45;cursor:not-allowed}.jc-result{margin-top:18px;padding:18px;border-radius:20px;border:1px solid #CFE3F2;background:#F7FCFF}.jc-result-top{display:grid;grid-template-columns:46px 1fr auto;gap:10px;align-items:center}.jc-result-top>span{width:44px;height:44px;border-radius:14px;background:#EAF5FC;display:grid;place-items:center;font-size:23px}.jc-result-top small{color:#718899;font-size:9px}.jc-result-top h3{margin:2px 0;color:#163B5C}.jc-result-top b{padding:6px 9px;border-radius:999px;font-size:9.5px}.jc-result-top b.ok{background:#EAF7EF;color:#1D6A45}.jc-result-top b.miss{background:#FFF4E5;color:#8A5A00}.jc-trace{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:15px}.jc-trace article{position:relative;padding:12px;border-radius:14px;background:#fff;border:1px solid #E1EBF2}.jc-trace span{width:25px;height:25px;display:grid;place-items:center;border-radius:8px;background:#1f6fae;color:#fff;font-size:10px;font-weight:900;margin-bottom:7px}.jc-trace b{display:block;color:#29485F;font-size:10px}.jc-trace small{display:block;margin-top:4px;color:#718899;font-size:9px;line-height:1.55}.jc-note{margin:12px 0 0;padding:10px 11px;border-radius:12px;background:#F3F7FA;color:#566a7d;font-size:10px;line-height:1.7}.jc-footer{display:flex;justify-content:space-between;gap:9px;margin-top:15px}.jc-next,.jc-reset{min-height:44px;padding:8px 14px;border-radius:12px;font:inherit;font-size:11px;font-weight:900;cursor:pointer}.jc-next{border:0;background:#1f6fae;color:#fff}.jc-reset{border:1px solid #DCE8F0;background:#fff;color:#526B7E}.jc-disclaimer{padding:14px 17px;border-radius:17px;border:1px solid #E2EAF0;background:#F8FAFC;color:#566a7d;font-size:11px;line-height:1.7}@media(max-width:900px){.jc-hero{grid-template-columns:1fr}.jc-score{max-width:300px}.jc-layout{grid-template-columns:1fr}.jc-cases{display:flex;overflow-x:auto}.jc-case{flex:0 0 240px}.jc-trace{grid-template-columns:1fr 1fr}}@media(max-width:560px){.jc-hero{padding:26px 17px;border-radius:23px}.jc-stage{padding:18px 14px}.jc-choices,.jc-trace{grid-template-columns:1fr}.jc-stage-head{grid-template-columns:50px 1fr}.jc-stage-head>span{width:48px;height:48px;border-radius:15px;font-size:24px}.jc-result-top{grid-template-columns:42px 1fr}.jc-result-top>b{grid-column:1/-1;width:max-content}.jc-footer{flex-direction:column}.jc-next,.jc-reset{width:100%}}@media(prefers-reduced-motion:reduce){.jc-page *{animation:none!important;transition:none!important}}
    '''
    csrf_meta = '<meta name="admin-csrf" content="%s">' % escape(csrf_token, quote=True)
    return page(title, csrf_meta + body + script, extra_css=css)


def register_routes(app, *, page_gate, page, lang_getter, csrf_token_getter,
                    admin_api_required, request_allowed, request, jsonify,
                    redirect, url_for):
    """Register V52 competition routes without growing the main webapp monolith."""

    @app.route('/admin/judge-challenge')
    def admin_judge_challenge_v52():
        denied = page_gate('/admin/judge-challenge')
        if denied is not None:
            return denied
        return render_judge_challenge(page=page, lang=lang_getter(), csrf_token=csrf_token_getter())

    @app.route('/judge-challenge')
    def judge_challenge_legacy_v52():
        denied = page_gate('/admin/judge-challenge')
        if denied is not None:
            return denied
        return redirect(url_for('admin_judge_challenge_v52'))

    @app.route('/api/admin/judge-challenge/evaluate', methods=['POST'])
    @admin_api_required('analytics')
    def api_admin_judge_challenge_evaluate_v52():
        if not request_allowed('judge_challenge', 40, 60):
            return jsonify({'ok': False, 'error': 'rate_limited'}), 429
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({'ok': False, 'error': 'invalid_json'}), 400
        result = evaluate_scenario(
            str(data.get('scenario_id') or ''), str(data.get('guess') or ''),
            str(data.get('lang') or lang_getter()),
        )
        response = jsonify(result)
        response.headers['Cache-Control'] = 'private, no-store'
        return response, (200 if result.get('ok') else 400)
