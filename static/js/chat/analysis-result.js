/* SymptoSense chat — Running the analysis and rendering the result (data-quality gate, relief tracker and result actions live in their own files).
   Classic script: shares the page's global scope with the other files in /static/js/chat/. Load order is fixed by chat_view.py. */

    function heartbeatLoader(label) {
      const sub=LANG==='ar'?'نراجع الأعراض ونجهّز لك النتيجة.':'Reviewing your symptoms and preparing the result.';
      return '<div class="ss-analysis-pulse" role="status" aria-live="polite"><div class="ss-analysis-loader__row"><span class="ss-analysis-loader__spinner" aria-hidden="true"></span><div class="ss-analysis-loader__copy"><b>'+esc(label)+'</b><small>'+esc(sub)+'</small></div></div><div class="ss-analysis-loader__dots" aria-hidden="true"><i></i><i></i><i></i></div></div>';
    }
    function finishAnalysisLoading() {
      bodyEl.querySelectorAll('.heartbeat-bubble').forEach(function(el){ el.remove(); });
    }
    async function runAnalysis() {
      trackJourney(state.previous_record_id ? 'reanalyze' : 'analysis');
      hideText();
      clearOpts();
      updateFlow('review');
      addHtml(heartbeatLoader(TT('analyzing')), 'bot heartbeat-bubble');

      // The public demo is embedded from the real deterministic engine at page
      // render time. It therefore works even if Railway/PostgreSQL/Groq is
      // temporarily unavailable and never writes health data.
      if (state.demo_mode) {
        const d = JSON.parse(JSON.stringify(DEMO_RESULT || {}));
        setTimeout(function(){
          finishAnalysisLoading();
          if (!d || !d.ok) {
            add(TT('err'), 'bot');
            showOpts([{label:'🔄 '+(LANG==='ar'?'إعادة المثال':'Retry demo'),fn:runAnalysis}]);
            return;
          }
          trackJourney('result');
          if (d.emergency) showEmergency(d); else renderResult(d);
        }, 180);
        return;
      }

      progressTimer = null;
      try {
        const payload = Object.assign({}, state, {lang: LANG});
        const pathContext = symptomPathContextNote();
        if (pathContext) payload.notes = [payload.notes||'', pathContext].filter(Boolean).join(' ');
        payload.followup_answers = (differentialAnswers||[]).slice(0, SMART_FOLLOWUP_MAX);
        payload.member_id = (state.member && state.member.id) ? Number(state.member.id) : (state.member_id || 0);
        payload.negative_symptoms = Array.from(new Set(differentialNegatives || []));
        lastAnalysisInput = JSON.parse(JSON.stringify(payload));
        if (state.previous_record_id) payload.previous_record_id = state.previous_record_id;
        if (selectedBloodId) payload.blood_id = Number(selectedBloodId) || null;
        useSaved = false;
        profileMissing = [];
        userInfo = userInfo || window.__USER_INFO__ || null;
        if (userInfo && userInfo.ok && userInfo.logged_in && userInfo.has_profile && userInfo.privacy && userInfo.privacy.use_in_analysis) {
          useSaved = true;
          payload.use_saved = true;
          profileMissing = userInfo.missing_fields || [];
        }

        progressTimer = setTimeout(function(){
          add(LANG==='ar'?'ما زلت أحلل إجاباتك بأمان… قد يستغرق الاتصال بضع ثوانٍ.':'Still analyzing your answers safely… the connection may take a few seconds.','bot');
        }, 7000);
        const analysisController = new AbortController();
        const analysisTimer = setTimeout(function(){ analysisController.abort(); }, 45000);
        let r;
        try {
          r = await fetch('/api/analyze', {
            method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify(payload), signal: analysisController.signal
          });
        } finally {
          clearTimeout(analysisTimer);
        }
        let d={};
        try { d = await r.json(); } catch (_) { throw new Error('invalid_response'); }
        if (d.consent_required) { location.href=d.consent_url||'/consent?next=/chat'; return; }
        if (!r.ok || !d.ok) throw new Error(d.error||d.error_code||'analysis_failed');

        trackJourney('result');
        if (d.emergency) {
          showEmergency(d);
        } else {
          renderResult(d);
          if (useSaved && profileMissing.length > 0 && userInfo && userInfo.profile) {
            var missingLabels = profileMissing.map(function(m){ return m.label; }).join(', ');
            var msg = LANG === 'ar'
              ? '💡 ملاحظة: لم تتم إضافة ' + missingLabels + ' بعد. يمكنك إضافتها من <a href="/profile" style="color:#1565c0;font-weight:700;">ملفي الصحي</a> لجعل السياق أكمل.'
              : '💡 Note: ' + missingLabels + ' were not included. Add them in your <a href="/profile" style="color:#1565c0;font-weight:700;">health profile</a> for more complete context.';
            addHtml(msg, 'bot');
          }
        }
      } catch(e) {
        const timedOut = e && (e.name === 'AbortError' || String(e.message).includes('AbortError'));
        add(timedOut ? (LANG==='ar'?'استغرق التحليل وقتًا أطول من المتوقع. إجاباتك محفوظة هنا ويمكنك إعادة المحاولة.':'The assessment took longer than expected. Your answers are still here; you can retry.') : TT('conn_err'), 'bot');
        showOpts([{label:'🔄 '+(LANG==='ar'?'إعادة محاولة التحليل':'Retry assessment'),fn:runAnalysis}]);
      } finally {
        if (progressTimer) clearTimeout(progressTimer);
        finishAnalysisLoading();
      }
    }
    function esc(s) { const div=document.createElement('div'); div.textContent=s||''; return div.innerHTML; }
    function escAttr(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function(ch){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]; }); }
    function sourceInitials(name) {
      const clean = String(name || '').replace(/[^A-Za-z0-9؀-ۿ ]+/g, ' ').trim();
      if (!clean) return 'S';
      const parts = clean.split(/\s+/).filter(Boolean).slice(0, 2);
      return parts.map(function(p){ return p.charAt(0); }).join('').toUpperCase() || 'S';
    }
    function safeLink(raw) {
      try {
        const u = new URL(String(raw || ''), window.location.origin);
        if (u.protocol === 'https:' || (u.origin === window.location.origin && (u.protocol === 'http:' || u.protocol === 'https:'))) return u.href;
      } catch(e) {}
      return '';
    }
    function safeDataImage(raw) { const v=String(raw||''); return /^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(v) ? v : ''; }
    function NAME(x, arKey, enKey) { return LANG === 'en' ? (x[enKey] || x[arKey]) : (x[arKey] || x[enKey]); }
    function pillLabel(u) { return u==='high' ? TT('urg_high') : (u==='medium' ? TT('urg_medium') : TT('urg_low')); }
    function explainabilityHtml(d){
      const x=d&&d.explainability; if(!x) return '';
      const factors=(x.factors||[]);
      const infLabel={high:(LANG==='ar'?'تأثير أعلى':'Higher contribution'),medium:(LANG==='ar'?'تأثير متوسط':'Moderate contribution'),low:(LANG==='ar'?'تأثير أقل':'Lower contribution')};
      let body='<details class="xai-card"><summary><span>🔍 '+esc(LANG==='ar'?'لماذا ظهر هذا التقييم؟':'Why this assessment?')+'</span><span>⌄</span></summary><div class="xai-body"><div class="xai-basis">'+esc(x.basis_label||'')+'</div>';
      if(factors.length){
        body+='<div><b>'+esc(LANG==='ar'?'العوامل التي استخدمها التقييم':'Factors used in this assessment')+'</b></div>';
        factors.forEach(function(f){const inf=['high','medium','low'].includes(String(f.influence||''))?String(f.influence):'low';const n=inf==='high'?3:(inf==='medium'?2:1);let meter='<span class="xai-meter" aria-label="'+escAttr(infLabel[inf]||inf)+'">';for(let i=1;i<=3;i++)meter+='<i class="'+(i<=n?'on':'')+'"></i>';meter+='</span>';body+='<div class="xai-factor"><div class="xai-factor-head"><b>'+esc(f.label||'')+'</b><span><span class="xai-influence '+esc(inf)+'">'+esc(infLabel[inf]||inf)+'</span>'+meter+'</span></div>'+(f.detail?'<div class="xai-detail">'+esc(f.detail)+'</div>':'')+'</div>';});
      } else {
        body+='<div class="muted">'+esc(LANG==='ar'?'لا توجد عوامل إضافية يمكن نسبها بشكل موثوق إلى التقييم الحالي.':'No additional factors can be reliably attributed to the current assessment.')+'</div>';
      }
      body+='<div class="xai-note"><b>'+esc(LANG==='ar'?'ماذا يعني ذلك؟':'What does this mean?')+'</b><br>'+esc(x.meaning||'')+'</div>';
      if(x.auxiliary_model_note) body+='<div class="xai-note">🤖 '+esc(x.auxiliary_model_note)+'</div>';
      body+='</div></details>'; return body;
    }
    function reportLines(value) {
      const raw = String(value || '').replace(/\r/g, '').trim();
      if (!raw) return [];
      return raw.split(/\n+/).map(function(x){ return x.replace(/^\s*[•–—-]\s*/, '').trim(); }).filter(Boolean);
    }
    function displayGender(value) {
      const v = String(value || '').toLowerCase();
      if (v === 'f' || v === 'female' || v === 'أنثى') return LANG === 'ar' ? 'أنثى' : 'Female';
      if (v === 'm' || v === 'male' || v === 'ذكر') return LANG === 'ar' ? 'ذكر' : 'Male';
      return value || '—';
    }
    function matchLevelLabel(level) {
      const map = LANG === 'ar'
        ? {strong:'توافق مرتفع', moderate:'توافق متوسط', weak:'توافق منخفض'}
        : {strong:'Strong match', moderate:'Moderate match', weak:'Weak match'};
      return map[level] || level || (LANG === 'ar' ? 'غير محدد' : 'Not specified');
    }
    function resultQuestionList(d) {
      const u = (d || {}).urgency || 'low';
      if (u === 'high') return [TT('q_urgent_1'), TT('q_urgent_2'), TT('q通用_1'), TT('q通用_2')];
      if (u === 'medium') return [TT('q_med_1'), TT('q_med_2'), TT('q通用_1'), TT('q通用_2')];
      return [TT('q_low_1'), TT('q_low_2'), TT('q通用_1'), TT('q通用_2')];
    }
    async function askResultQuestion(question) {
      const box = document.getElementById('reportQuestionAnswer');
      if (!box || !question) return;
      box.hidden = false;
      box.textContent = TT('answering');
      try {
        const ctx = Object.assign({}, lastResult || {}, {lang: LANG});
        const r = await fetch('/api/analysis/followup-question', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({question:question, context:ctx})});
        const d = await r.json();
        box.textContent = d.ok ? (d.answer || '') : (TT('err') + (d.error || '?'));
      } catch(e) {
        box.textContent = TT('conn_err');
      }
    }
    function contextualSymptomPattern(input) {
      input=input||{};
      const syms=Array.isArray(input.symptoms)?input.symptoms.filter(Boolean):[];
      const worse=String(input.pattern_worse||'').trim();
      const notes=String(input.notes||'').trim();
      const hay=[worse,notes,syms.join(' ')].join(' ').toLowerCase();
      if(!hay || /^(غير محدد|not specified|not clear|غير واضح)$/i.test(worse)) {
        return null;
      }
      const defs=[
        {id:'movement',icon:'↔️',ar:'بالحركة أو المجهود',en:'movement or exertion',re:/مع الحركة|بعد المجهود|المشي|الجري|الرياض|الحرك|مجهود|movement|moving|walking|running|exercise|exertion/i},
        {id:'food',icon:'🍽️',ar:'بالطعام أو توقيت الوجبات',en:'food or meal timing',re:/بعد الأكل|مع الأكل|قبل الأكل|وجبة|طعام|اكل|الأكل|after eating|with food|before eating|meal|food/i},
        {id:'standing',icon:'↕️',ar:'بالوقوف أو تغيّر الوضعية',en:'standing or position changes',re:/عند الوقوف|لما اقوم|لما أقوم|عند القيام|تغيير الوضعية|الوضعية|standing up|standing|position|posture/i},
        {id:'sleep',icon:'🌙',ar:'بالليل أو نمط النوم',en:'night-time or sleep pattern',re:/بالليل|أثناء النوم|وقت النوم|بعد النوم|قلة النوم|النوم|ليلاً|ليلا|at night|during sleep|bedtime|after sleep|lack of sleep|sleep/i},
        {id:'cycle',icon:'◷',ar:'بالدورة الشهرية',en:'the menstrual cycle',re:/وقت الدورة|مع الدورة|قبل الدورة|بعد الدورة|الدورة الشهرية|حيض|طمث|period|menstrual|menses/i},
        {id:'stress',icon:'◌',ar:'بالتوتر أو الضغط',en:'stress or emotional strain',re:/مع التوتر|توتر|ضغط نفسي|قلق|stress|anxiety|emotional strain/i}
      ];
      let best=null; let bestScore=0;
      defs.forEach(function(def){
        let score=0;
        if(def.re.test(worse)) score+=4;
        if(def.re.test(notes)) score+=2;
        if(def.re.test(syms.join(' '))) score+=1;
        if(score>bestScore){best=def;bestScore=score;}
      });
      if(!best || bestScore<=0) return null;
      let evidence='';
      if(worse && !/غير محدد|not specified|not clear|غير واضح/i.test(worse)) {
        evidence = LANG==='ar' ? ('لأنك ذكرت أن العرض يزيد: '+worse+'.') : ('Because you said the symptom is worse: '+worse+'.');
      } else if(notes) {
        evidence = LANG==='ar' ? 'لأن وصفك الإضافي ذكر هذا السياق بوضوح.' : 'Because your additional description clearly mentioned this context.';
      } else {
        evidence = LANG==='ar' ? 'لأن وصف الأعراض الذي أدخلته ذكر هذا السياق.' : 'Because the symptom description you entered mentioned this context.';
      }
      return {id:best.id,icon:best.icon,label:LANG==='ar'?best.ar:best.en,evidence:evidence};
    }
    function contextualSymptomPatternHtml(input) {
      const p=contextualSymptomPattern(input);
      if(!p) return '';
      return '<section class="ss-report-card ss-context-pattern"><div class="ss-context-pattern-icon">'+esc(p.icon)+'</div><div class="ss-context-pattern-copy"><span>'+esc(LANG==='ar'?'نمط الأعراض الحالي':'Current symptom pattern')+'</span><h3>'+esc((LANG==='ar'?'يبدو مرتبطًا أكثر ':'Appears more related to ')+p.label)+'</h3><p>'+esc(p.evidence)+'</p><small>'+esc(LANG==='ar'?'هذا وصف للسياق الذي أدخلته، وليس تشخيصًا أو سببًا مؤكدًا.':'This describes the context you entered; it is not a diagnosis or a confirmed cause.')+'</small></div></section>';
    }
    function next24PlanHtml(d, input, dangerLines, homeLines, recs) {
      const urgent=(d.urgency||'low')==='high';
      const symptoms=Array.isArray(input.symptoms)?input.symptoms.filter(Boolean):[];
      const main=symptoms.slice(0,3).join(LANG==='ar'?'، ':', ');
      if(urgent){
        const immediate=(recs[0]&&(recs[0].tip||recs[0].title))||d.when_to_seek_care||(LANG==='ar'?'اتبع توجيه الطوارئ الظاهر في النتيجة الآن.':'Follow the emergency guidance shown in the result now.');
        return '<section class="ss-report-card ss-next24 urgent"><div class="ss-report-heading"><h3>⏱️ '+esc(LANG==='ar'?'لا تنتظر 24 ساعة':'Do not wait 24 hours')+'</h3></div><div class="ss-next24-alert">'+esc(immediate)+'</div></section>';
      }
      const care=(homeLines&&homeLines[0])||(recs[0]&&(recs[0].tip||recs[0].title))||(LANG==='ar'?'التزم بالإرشادات الظاهرة في النتيجة وراقب التغيّر.':'Follow the guidance shown above and monitor for change.');
      const danger=(dangerLines&&dangerLines[0])||(LANG==='ar'?'إذا ظهرت علامة خطر جديدة أو ساءت الأعراض بوضوح، اطلب تقييمًا طبيًا مناسبًا.':'If a new warning sign appears or symptoms clearly worsen, seek appropriate medical evaluation.');
      const monitor=(LANG==='ar'?'راقب تغيّر الشدة وظهور أعراض جديدة'+(main?' مع '+main:'')+'.':'Watch for changes in severity and any new symptoms'+(main?' alongside '+main:'')+'.');
      const log=(LANG==='ar'?'سجّل وقت التغيّر، وما الذي يزيد العرض أو يخففه، وأي دواء تناولته.':'Note when things change, what worsens or relieves the symptom, and any medicine you take.');
      return '<section class="ss-report-card ss-next24"><div class="ss-report-heading"><h3>🕒 '+esc(LANG==='ar'?'خطة الـ24 ساعة القادمة':'Your next 24 hours')+'</h3><span class="ss-count">'+esc(LANG==='ar'?'مراقبة عملية':'Practical monitoring')+'</span></div><div class="ss-next24-grid">'
        +'<article><span>1</span><div><b>'+esc(LANG==='ar'?'الآن':'Now')+'</b><p>'+esc(care)+'</p></div></article>'
        +'<article><span>2</span><div><b>'+esc(LANG==='ar'?'راقب':'Monitor')+'</b><p>'+esc(monitor)+'</p></div></article>'
        +'<article><span>3</span><div><b>'+esc(LANG==='ar'?'سجّل':'Log')+'</b><p>'+esc(log)+'</p></div></article>'
        +'<article class="watch"><span>!</span><div><b>'+esc(LANG==='ar'?'لا تنتظر إذا':'Do not wait if')+'</b><p>'+esc(danger)+'</p></div></article>'
        +'</div></section>';
    }
    function careTimingHtml(d, dangerLines) {
      const u=(d&&d.urgency)||'low';
      let cls='low', badge='', title='', body='';
      if(u==='high'){
        cls='high'; badge=LANG==='ar'?'لا تنتظر':'Do not wait'; title=LANG==='ar'?'اطلب رعاية عاجلة الآن':'Seek urgent care now';
        body=d.when_to_seek_care||(LANG==='ar'?'النتيجة الحالية تتضمن علامة خطر. لا تؤخر طلب الرعاية الطارئة بسبب استمرار التحليل أو تحسن مؤقت.':'The current result includes a warning sign. Do not delay urgent care for more analysis or because symptoms briefly improve.');
      }else if(u==='medium'){
        cls='medium'; badge=LANG==='ar'?'لا تؤجل التقييم':'Do not delay assessment'; title=LANG==='ar'?'رتّب تقييمًا طبيًا وفق التوصية الحالية':'Arrange medical assessment as recommended';
        body=d.when_to_seek_care||(LANG==='ar'?'المعلومات الحالية تستدعي مراجعة طبية. اتبع توقيت المراجعة الظاهر في النتيجة، واطلب مساعدة أسرع إذا ساءت الأعراض أو ظهرت علامة خطر.':'The current information warrants medical review. Follow the timing shown in your result and seek faster care if symptoms worsen or a warning sign appears.');
      }else{
        cls='low'; badge=LANG==='ar'?'مراقبة بشروط':'Monitor with safeguards'; title=LANG==='ar'?'يمكن اتباع خطة المراقبة الحالية':'You can follow the current monitoring plan';
        body=LANG==='ar'?'المعلومات التي أدخلتها لا تُظهر حاليًا علامة خطر واضحة. اتبع خطة المراقبة والرعاية المعروضة، لكن لا تعتبر النتيجة ضمانًا للأمان: إذا ساءت الأعراض أو ظهرت علامة خطر فاطلب تقييمًا طبيًا.':'The information you entered does not currently show a clear warning sign. Follow the monitoring and care plan shown, but do not treat this result as a guarantee of safety: seek medical evaluation if symptoms worsen or a warning sign appears.';
      }
      const flags=(dangerLines||[]).slice(0,4);
      return '<section class="ss-report-card ss-care-timing '+cls+'"><div class="ss-report-heading"><h3>⏳ '+esc(LANG==='ar'?'هل أقدر أنتظر؟':'Can I wait?')+'</h3><span class="ss-care-badge">'+esc(badge)+'</span></div><div class="ss-care-decision"><b>'+esc(title)+'</b><p>'+esc(body)+'</p></div>'+(flags.length?'<details><summary>'+esc(LANG==='ar'?'ما الذي يغيّر هذه الخطوة؟':'What would change this next step?')+'</summary><div class="ss-care-flags">'+flags.map(function(x){return '<div>• '+esc(x)+'</div>';}).join('')+'</div></details>':'')+'</section>';
    }
    function renderResult(d) {
      lastResult = d;
      draftClear();
      selectedFeedbackStar = 0;
      selectedFeedbackReason = '';
      state.step = 'review';
      updateFlow(state.step);
      hideText();
      clearOpts();

      // Result mode replaces the questionnaire inside the SAME chat container.
      // The page viewport is left untouched while the report replaces the questionnaire.
      const wrap = bodyEl.closest('.chat-wrap');
      if (wrap) wrap.classList.add('report-mode');
      bodyEl.classList.add('result-mode');
      optsEl.hidden = true;
      const safetyNote = document.getElementById('chatSafetyNote');
      if (safetyNote) safetyNote.style.visibility = 'hidden'; // preserve page height / viewport position

      const u = d.urgency || 'low';
      const riskClass = u === 'high' ? 'hi' : (u === 'medium' ? 'med' : 'low');
      const riskEmoji = u === 'high' ? '🔴' : (u === 'medium' ? '🟡' : '🟢');
      const riskValue = d.urgency_text || pillLabel(u);
      const input = lastAnalysisInput || state || {};
      const q = d.data_quality || {};
      const qScoreRaw = Number(q.score);
      const hasQScore = Number.isFinite(qScoreRaw);
      const qScore = hasQScore ? Math.max(0, Math.min(100, Math.round(qScoreRaw))) : null;
      const qLabel = q.user_state_label || ((qScore === 100 || Number(q.required_completion) === 100)
        ? (LANG === 'ar' ? 'المعلومات المطلوبة مكتملة' : 'Required information complete')
        : (q.level_label || ''));
      const recs = (d.recommendations || []).filter(function(r){ return r && (r.tip || r.title); });
      const summaryRec = recs.length ? (recs[0].title || recs[0].tip) : (d.triage_label || d.risk_label || riskValue);
      const matches = Array.isArray(d.knowledge_matches) ? d.knowledge_matches : [];
      const sources = Array.isArray(d.medical_sources) ? d.medical_sources : [];
      const riskReasons = Array.isArray(d.risk_reasons) ? d.risk_reasons : [];
      const dangerLines = reportLines(d.danger_signs);
      const homeLines = reportLines(d.home_care);
      const questions = resultQuestionList(d);

      let h = '<div class="ss-report" id="symptomResultReport">';

      // 0) Four-state decision card + uncertainty (all text escaped)
      const dec = d.decision;
      if (dec && dec.level) {
        h += '<section class="ss-report-card ss-decision ss-decision-'+escAttr(dec.level)+'" role="status" aria-label="'+escAttr(dec.headline||'')+'" style="border-inline-start:6px solid '+(dec.level==='emergency'?'#c62828':(dec.level==='today'?'#ef6c00':(dec.level==='soon'?'#f9a825':'#2e7d32')))+'">'
          + '<div class="ss-decision-head"><span aria-hidden="true">'+esc(dec.icon||'')+'</span> <strong>'+esc(dec.headline||'')+'</strong></div>'
          + (dec.action ? '<p class="ss-decision-action">'+esc(dec.action)+'</p>' : '')
          + (dec.window ? '<p class="ss-decision-window"><small>'+esc(dec.window)+'</small></p>' : '');
        if (dec.why) h += '<p class="ss-decision-why"><small>'+esc(Array.isArray(dec.why)?dec.why.join(' · '):dec.why)+'</small></p>';
        if (Array.isArray(dec.would_change) && dec.would_change.length) h += '<details class="ss-decision-change"><summary style="min-height:44px;padding:10px 0;cursor:pointer">'+esc(LANG==='ar'?'ما الذي قد يغيّر هذا القرار؟':'What could change this?')+'</summary><ul>'+dec.would_change.map(function(x){return '<li>'+esc(x)+'</li>';}).join('')+'</ul></details>';
        const unc = dec.uncertainty || {};
        if (unc.confidence || (unc.reasons && unc.reasons.length) || (unc.missing && unc.missing.length)) {
          h += '<details class="ss-decision-unc"><summary style="min-height:44px;padding:10px 0;cursor:pointer">'+esc(LANG==='ar'?'مدى الثقة بهذه النتيجة':'How confident is this result?')+(unc.confidence?' — '+esc(unc.confidence):'')+'</summary>';
          if (unc.reasons && unc.reasons.length) h += '<ul>'+unc.reasons.map(function(x){return '<li>'+esc(x)+'</li>';}).join('')+'</ul>';
          if (unc.missing && unc.missing.length) h += '<p><b>'+esc(LANG==='ar'?'معلومات ناقصة تحسّن الدقة:':'Missing info that would improve accuracy:')+'</b> '+unc.missing.map(esc).join('، ')+'</p>';
          if (unc.tip) h += '<p><small>'+esc(unc.tip)+'</small></p>';
          h += '</details>';
        }
        h += '</section>';
      }

      // 0b) Connected clinical picture (reasoning). All text is escaped.
      const rs = d.reasoning;
      if (rs) {
        const L = function(a, e){ return LANG==='ar' ? a : e; };
        const ul = function(arr){ return '<ul>'+arr.map(function(x){return '<li>'+esc(x)+'</li>';}).join('')+'</ul>'; };
        h += '<section class="ss-report-card ss-reasoning">';
        h += '<div class="ss-report-heading"><h2>🧠 '+esc(L('الصورة السريرية المترابطة','Connected clinical picture'))+'</h2></div>';
        const ch = rs.what_changed || {};
        if (ch.items && ch.items.length) h += '<div class="ss-rs-block"><b>'+esc(L('ما الذي تغيّر منذ المرة السابقة؟','What changed since last time?'))+'</b>'+ul(ch.items)+'</div>';
        if (rs.contributors && rs.contributors.length) h += '<div class="ss-rs-block"><b>'+esc(L('عوامل مرتبطة ببياناتك','Factors linked to your data'))+'</b>'+ul(rs.contributors.map(function(c){return c.text;}))+'</div>';
        if (rs.possibilities && rs.possibilities.length) {
          h += '<div class="ss-rs-block"><b>'+esc(L('الاحتمالات: لماذا ظهرت وما الذي يقلل احتمالها','Possibilities: why they appeared and what lowers them'))+'</b>';
          rs.possibilities.forEach(function(p){
            h += '<details style="margin:6px 0"><summary style="min-height:44px;padding:10px 0;cursor:pointer">'+esc(p.name)+'</summary>';
            if (p.why && p.why.length) h += '<p><small><b>'+esc(L('ظهر بسبب: ','Appeared because of: '))+'</b>'+p.why.map(esc).join(' + ')+'</small></p>';
            if (p.against && p.against.length) h += '<p><small><b>'+esc(L('ما يقلل احتماله:','What lowers it:'))+'</b></small></p>'+ul(p.against);
            h += '</details>';
          });
          h += '<p><small>'+esc(L('هذه أنماط متوافقة مع ما أدخلته وليست تشخيصًا.','These are patterns that fit what you entered, not a diagnosis.'))+'</small></p></div>';
        }
        if (rs.not_supported && rs.not_supported.length) h += '<div class="ss-rs-block"><b>'+esc(L('ما لا تدعمه بياناتك حاليًا','What your data does not point to'))+'</b>'+ul(rs.not_supported)+'</div>';
        if (rs.escalate_if && rs.escalate_if.length) h += '<div class="ss-rs-block"><b>'+esc(L('تصعيد فوري إذا ظهر:','Escalate right away if:'))+'</b>'+ul(rs.escalate_if)+'</div>';
        if (rs.missing_top2 && rs.missing_top2.length) h += '<div class="ss-rs-block"><b>'+esc(rs.missing_note||'')+'</b>'+ul(rs.missing_top2.map(function(m){return m.question;}))+'</div>';
        h += '<p><small>'+esc(L('قيد المراجعة السريرية؛ لا يغني عن الطبيب أو الصيدلي.','Pending clinical review; it does not replace your doctor or pharmacist.'))+'</small></p>';
        h += '</section>';
      }

      // 1) Summary
      h += '<section class="ss-report-card ss-report-summary">'
        + '<div class="ss-report-heading"><h2>📋 '+esc(LANG==='ar'?'نتيجة التحليل':'Analysis result')+'</h2></div>'
        + '<div class="ss-risk-row '+riskClass+'"><div><div class="ss-risk-label">'+esc(LANG==='ar'?'مستوى الخطورة':'Risk level')+'</div><div class="ss-risk-value">'+riskEmoji+' '+esc(riskValue)+'</div></div></div>';
      if (hasQScore) {
        h += '<div class="ss-quality"><div class="ss-quality-top"><strong>'+esc(LANG==='ar'?'اكتمال المعلومات المدخلة':'Information completeness')+'</strong><span class="ss-quality-score">'+qScore+'%'+(qLabel?' — '+esc(qLabel):'')+'</span></div><div class="ss-quality-track" aria-hidden="true"><div class="ss-quality-fill" style="width:'+qScore+'%"></div></div></div>';
      }
      const bc=d.blood_context||{};
      if(bc.used){
        h+='<div class="ss-blood-context"><b>🧪 '+esc(LANG==='ar'?'سياق تحليل الدم المستخدم':'Blood-test context used')+'</b><p>'+esc(bc.note||'')+'</p>';
        const bis=Array.isArray(bc.relevant_indicators)?bc.relevant_indicators:[];
        if(bis.length){h+='<ul>'+bis.map(function(x){const val=(x.value===null||x.value===undefined)?'':(' · '+String(x.value)+(x.unit?' '+x.unit:''));return '<li>'+esc(x.name||x.key||'')+esc(val)+'</li>';}).join('')+'</ul>';}
        else if(bc.no_direct_link_note){h+='<small>'+esc(bc.no_direct_link_note)+'</small>';}
        h+='</div>';
      }
      // First screen: risk level (text, not colour alone), what to do now, call button, disclaimer.
      h += '<div class="ss-emergency-strip'+(u==='high'?' urgent':'')+'"><a class="ss-call-btn" href="tel:997">📞 '+esc(LANG==='ar'?'اتصل بالإسعاف 997':'Call ambulance 997')+'</a><p>'+esc(u==='high'
        ? (LANG==='ar'?'لا تنتظر ولا تقد السيارة بنفسك إذا كنت متعبًا. اتصل الآن أو اطلب من شخص قريب أن يتصل.':'Do not wait, and do not drive yourself if you feel unwell. Call now or ask someone nearby to call.')
        : (LANG==='ar'?'اتصل بالإسعاف فورًا إذا ظهر ألم صدر شديد، أو صعوبة في التنفس، أو إغماء، أو ضعف مفاجئ في جانب من الجسم، أو نزيف شديد.':'Call the ambulance immediately for severe chest pain, trouble breathing, fainting, sudden one-sided weakness, or heavy bleeding.'))+'</p></div>';
      if (summaryRec) h += '<div class="ss-summary-recommendation"><b>'+esc(LANG==='ar'?'التوصية الحالية':'Current recommendation')+'</b>'+esc(summaryRec)+'</div>';
      h += '<p class="ss-disclaimer">'+esc(LANG==='ar'?'هذا التحليل توعوي ولا يغني عن الطبيب أو التقييم الطبي المباشر.':'This analysis is educational and does not replace a doctor or an in-person medical assessment.')+'</p>';
      h += '</section>';


      if (u !== 'high' && (d.assessment_status === 'insufficient' || d.assessment_status === 'low_confidence' || d.low_confidence)) {
        h += '<div class="v2-low-confidence-card">'
          + '<b>' + esc(
              LANG === 'ar'
                ? 'تم التعرف على العرض، لكن المعلومات الحالية لا تكفي لعرض احتمالات مناسبة بدرجة ثقة كافية'
                : 'The symptom was understood, but there is not enough information to show trusted possibilities'
            ) + '</b>'
          + '<p>' + esc(
              LANG === 'ar'
                ? 'إليك مستوى الخطورة والخطوة المناسبة بدلًا من ذلك.'
                : 'Here is the risk level and the appropriate next step instead.'
            ) + '</p>'
          + '</div>';
      }

      // Keep entered information available, but prioritize the decision dashboard first.
      const inputRows = [
        [LANG==='ar'?'الأعراض':'Symptoms', Array.isArray(input.symptoms) ? input.symptoms.join(LANG==='ar'?'، ':', ') : input.symptoms],
        [LANG==='ar'?'المدة':'Duration', input.duration],
        [LANG==='ar'?'شدة الأعراض':'Symptom severity', input.severity ? String(input.severity)+'/5' : ''],
        [LANG==='ar'?'العمر':'Age', input.age ? String(input.age) : ''],
        [LANG==='ar'?'الجنس':'Sex', displayGender(input.gender)]
      ].filter(function(x){ return x[1] !== null && x[1] !== undefined && String(x[1]).trim() !== ''; });

      // 2) What to do now — the immediate action comes before possibilities.
      h += '<section class="ss-report-card"><div class="ss-report-heading"><h3>🧭 '+esc(LANG==='ar'?'ماذا أفعل الآن؟':'What should I do now?')+'</h3></div><div class="ss-step-list">';
      let stepNo = 1;
      recs.forEach(function(r){
        const title = r.title || (LANG==='ar'?'الآن':'Now');
        const tip = r.tip || '';
        h += '<div class="ss-step"><span class="ss-step-no">'+stepNo+'</span><div class="ss-step-body"><b>'+esc(title)+'</b>'+(tip?'<p>'+esc(tip)+'</p>':'')+(r.url?'<a class="ss-step-source" href="'+escAttr(safeLink(r.url))+'" target="_blank" rel="noopener noreferrer">'+esc(LANG==='ar'?'عرض المصدر':'View source')+'</a>':'')+'</div></div>';
        stepNo += 1;
      });
      if (d.medication_guidance) {
        h += '<div class="ss-step"><span class="ss-step-no">'+stepNo+'</span><div class="ss-step-body"><b>💊 '+esc(LANG==='ar'?'إرشاد الدواء':'Medication guidance')+'</b><p>'+esc(d.medication_guidance)+'</p></div></div>'; stepNo += 1;
      }
      if (d.when_to_seek_care) {
        h += '<div class="ss-step"><span class="ss-step-no">'+stepNo+'</span><div class="ss-step-body"><b>'+esc(LANG==='ar'?'متى أراجع الطبيب؟':'When should I see a doctor?')+'</b><p>'+esc(d.when_to_seek_care)+'</p></div></div>'; stepNo += 1;
      }
      if (stepNo === 1) h += '<div class="ss-empty-note">'+esc(LANG==='ar'?'لا توجد توصيات إضافية في النتيجة الحالية.':'No additional recommendations are available in the current result.')+'</div>';
      h += '</div></section>';

      // Practical next-24-hours card; urgent results explicitly tell the user not to wait.
      h += next24PlanHtml(d, input, dangerLines, homeLines, recs);
      h += careTimingHtml(d, dangerLines);
      h += '<div class="ss-details-divider" role="separator"><span>'+esc(LANG==='ar'?'التفاصيل':'Details')+'</span></div>';
      // V222: concise "what we understood" dashboard before deeper details.
      const understoodNorm=d.symptom_normalization||{};
      const understoodPresent=(understoodNorm.canonical||[]).map(function(x){return LANG==='ar'?(x.name_ar||x.slug):(x.name_en||x.slug);}).filter(Boolean);
      const understoodAbsent=(understoodNorm.negated||[]).map(function(x){return LANG==='ar'?(x.name_ar||x.slug):(x.name_en||x.slug);}).filter(Boolean);
      const preciseArea=bodyZoneLabel(input.body_zone_primary||state.body_zone_primary)||(input.body_region_primary?bodyRegionLabel(input.body_region_primary):'');
      h += '<section class="ss-report-card ss-understood-card"><div class="ss-report-heading"><h3>✅ '+esc(LANG==='ar'?'وش فهمنا من حالتك؟':'What we understood')+'</h3><span class="ss-count">'+esc(LANG==='ar'?'راجعها بسرعة':'Quick check')+'</span></div><div class="ss-understood-grid">';
      if(understoodPresent.length) h += '<div><b>'+esc(LANG==='ar'?'الأعراض':'Symptoms')+'</b><span>'+esc(understoodPresent.join(LANG==='ar'?'، ':', '))+'</span></div>';
      else if(Array.isArray(input.symptoms)&&input.symptoms.length) h += '<div><b>'+esc(LANG==='ar'?'الأعراض':'Symptoms')+'</b><span>'+esc(input.symptoms.join(LANG==='ar'?'، ':', '))+'</span></div>';
      if(preciseArea) h += '<div><b>'+esc(LANG==='ar'?'المكان':'Area')+'</b><span>'+esc(preciseArea)+'</span></div>';
      if(input.duration) h += '<div><b>'+esc(LANG==='ar'?'المدة':'Duration')+'</b><span>'+esc(input.duration)+'</span></div>';
      if(input.severity) h += '<div><b>'+esc(LANG==='ar'?'الشدة':'Severity')+'</b><span>'+esc(String(input.severity))+'/5</span></div>';
      if(understoodAbsent.length) h += '<div class="wide"><b>'+esc(LANG==='ar'?'أعراض نفيتها':'Symptoms reported absent')+'</b><span>'+esc(understoodAbsent.join(LANG==='ar'?'، ':', '))+'</span></div>';
      h += '</div><div class="ss-inline-edit-actions"><button type="button" data-quick-edit="symptoms">✏️ '+esc(LANG==='ar'?'تعديل العرض':'Edit symptom')+'</button><button type="button" data-quick-edit="location">📍 '+esc(LANG==='ar'?'تعديل المكان':'Edit area')+'</button><button type="button" data-quick-edit="duration">⏱️ '+esc(LANG==='ar'?'تعديل المدة':'Edit duration')+'</button><button type="button" data-quick-edit="severity">⚡ '+esc(LANG==='ar'?'تعديل الشدة':'Edit severity')+'</button></div></section>';

      // Live symptom path — the same four-part pattern collected during the questionnaire.
      h += '<section class="ss-report-card ss-result-path"><div class="ss-report-heading"><h3>🧭 '+esc(LANG==='ar'?'مسار الأعراض':'Symptom path')+'</h3><span class="ss-count">'+esc(LANG==='ar'?'نمط بصري':'Visual pattern')+'</span></div>'+symptomPathRailHtml(true)+'</section>';
      if(d.symptom_pattern_summary && d.symptom_pattern_summary.text && u !== 'high'){
        h += '<section class="ss-report-card ss-pattern-summary-v151"><div class="ss-report-heading"><h3>🔗 '+esc(d.symptom_pattern_summary.title|| (LANG==='ar'?'ملخص نمط الأعراض':'Symptom pattern summary'))+'</h3><span class="ss-count">'+esc(LANG==='ar'?'عدة أعراض معًا':'Combined context')+'</span></div><p>'+esc(d.symptom_pattern_summary.text)+'</p><small>'+esc(d.symptom_pattern_summary.note||'')+'</small></section>';
      }

      // Context pattern summarizes the user's own timing/trigger context; never shown ahead of urgent care.
      if (u !== 'high') h += contextualSymptomPatternHtml(input);

      // 3) Symptom assessment. In emergencies, show the matched red-flag
      // assessment as the result instead of an empty "no possibilities" box.
      h += '<section class="ss-report-card"><div class="ss-report-heading"><h3>🩺 '+esc(
        u === 'high'
          ? (LANG==='ar'?'نتيجة تحليل الأعراض':'Symptom analysis result')
          : (LANG==='ar'?'الاحتمالات المحتملة':'Possible conditions')
      )+'</h3></div><div class="ss-condition-list">';
      if (u === 'high') {
        h += '<div class="ss-empty-note" style="border-color:#F2CACA;background:#FFF7F7;color:#7A3535">🚨 '+esc(
          matches.length
            ? (LANG==='ar'?'هذه احتمالات ممكنة مبنية على مطابقة الأعراض، وليست تفسيرًا مؤكدًا لعلامة الخطر ولا تشخيصًا. لا تؤخر طلب الرعاية العاجلة بسبب هذه الاحتمالات.':'These are possible matches based on the reported symptoms, not a confirmed explanation of the red flag or a diagnosis. Do not delay urgent care because of these possibilities.')
            : (LANG==='ar'?'اكتشف التحليل علامة خطر واضحة في الأعراض المدخلة. هذه نتيجة تقييم أولي وليست تشخيصًا، والأولوية الآن لطلب الرعاية الطارئة.':'The analysis detected a clear warning sign in the entered symptoms. This is an initial assessment, not a diagnosis; seeking emergency care is the priority now.')
        )+'</div>';
      }
      if (matches.length) {
        matches.forEach(function(m,idx){
          const name = NAME(m,'name_ar','name_en') || '';
          const matched = (m.matched_symptoms || []).map(function(x){ return NAME(x,'name_ar','name_en'); }).filter(Boolean);
          const condSource = m.explanation_source || (Array.isArray(m.sources) && m.sources.length ? m.sources[0] : null);
          let directSource = '';
          if (condSource) {
            const curl = condSource.reference_url || condSource.official_url || '';
            const cname = (LANG==='en' && /[\u0600-\u06FF]/.test(condSource.source_name||'') && condSource.organization) || condSource.source_name || condSource.organization || '';
            if (curl && cname) {
              const sourceTitle = LANG==='ar' ? (condSource.reference_title_ar || condSource.reference_title_en || cname) : (condSource.reference_title_en || condSource.reference_title_ar || cname);
              const verifiedAt = condSource.last_verified || condSource.source_last_verified || '';
              const verifiedStatus = String(condSource.verification_status || '').toLowerCase();
              let sourceMeta = '';
              if (verifiedStatus === 'verified') sourceMeta += ' · '+esc(LANG==='ar'?'موثق':'Verified');
              if (verifiedAt) sourceMeta += ' · '+esc((LANG==='ar'?'مراجعة: ':'Reviewed: ')+verifiedAt);
              const isContextFallback=String(condSource.source_scope||'')==='symptom_context_fallback';
              const sourceLabel=isContextFallback?(LANG==='ar'?'مرجع داعم للسياق: ':'Context-supporting source: '):(LANG==='ar'?'مرجع هذا التفسير: ':'Source for this explanation: ');
              directSource = '<div class="ss-condition-source" style="margin-top:8px">📚 '+esc(sourceLabel)+'<a href="'+escAttr(safeLink(curl))+'" target="_blank" rel="noopener noreferrer">'+esc(sourceTitle)+'</a>'+sourceMeta+'</div>';
            }
          }
          h += '<article class="ss-condition"><div class="ss-condition-head"><div class="ss-condition-name">'+esc(name)+'</div><span class="ss-match">'+esc(matchLevelLabel(m.match_level))+'</span></div>';
          if (matched.length) { const neg=(m.negative_evidence||[]).filter(Boolean); h += '<div class="ss-condition-why"><b>'+esc(LANG==='ar'?'لماذا ظهر هذا الاحتمال؟':'Why did this appear?')+'</b><br>'+esc(LANG==='ar'?'يتوافق مع: ':'Matches: ')+esc(matched.join(LANG==='ar'?'، ':', '))+(neg.length?'<div style="margin-top:6px">'+esc(LANG==='ar'?'والأعراض المنفية خفّضت التوافق عند ارتباطها بهذه الحالة: ':'Denied symptoms reduced the match when relevant: ')+esc(neg.join(LANG==='ar'?'، ':', '))+'</div>':'')+(m.description?'<div style="margin-top:6px">'+esc(m.description)+'</div>':'')+directSource+'</div>'; }
          else if (m.description) h += '<div class="ss-condition-why"><b>'+esc(LANG==='ar'?'لماذا ظهر هذا الاحتمال؟':'Why did this appear?')+'</b><br>'+esc(m.description)+directSource+'</div>';
          else if (directSource) h += '<div class="ss-condition-why">'+directSource+'</div>';
          const simpleId='simpleCondition'+idx;
          h += '</article>';
        });
      } else if (u === 'high') {
        const emergencyRows = riskReasons.length ? riskReasons : [{
          name: LANG === 'ar' ? 'علامة خطر تستدعي الطوارئ' : 'Emergency warning sign',
          message: d.simple_explanation || d.personal_note || riskValue
        }];
        emergencyRows.forEach(function(reason){
          const title = reason.name || reason.label || (LANG === 'ar' ? 'علامة خطر تستدعي الطوارئ' : 'Emergency warning sign');
          const detail = reason.message || reason.description || d.simple_explanation || '';
          h += '<article class="ss-condition" style="border-inline-start-color:#C62828">'
            + '<div class="ss-condition-head"><div class="ss-condition-name">🔴 '+esc(title)+'</div><span class="ss-match">'+esc(LANG==='ar'?'نتيجة طارئة':'Urgent result')+'</span></div>'
            + (detail ? '<div class="ss-condition-why"><b>'+esc(LANG==='ar'?'لماذا ظهرت هذه النتيجة؟':'Why did this result appear?')+'</b><br>'+esc(detail)+'</div>' : '')
            + '</article>';
        });
      } else if (d.possible_conditions) {
        reportLines(d.possible_conditions).forEach(function(line){ h += '<article class="ss-condition"><div class="ss-condition-why" style="margin-top:0">'+esc(line)+'</div></article>'; });
      } else {
        h += '<div class="ss-empty-note">'+esc(LANG==='ar'?'لا توجد احتمالات موثوقة إضافية في النتيجة الحالية.':'No additional trusted possibilities are available in the current result.')+'</div>';
      }
      h += '</div></section>';

      const normSummary=d.symptom_normalization||{};
      const presentSymptoms=(normSummary.canonical||[]).map(function(x){return LANG==='ar'?(x.name_ar||x.slug):(x.name_en||x.slug);}).filter(Boolean);
      const absentSymptoms=(normSummary.negated||[]).map(function(x){return LANG==='ar'?(x.name_ar||x.slug):(x.name_en||x.slug);}).filter(Boolean);
      if(presentSymptoms.length||absentSymptoms.length){
        h += '<section class="ss-report-card"><div class="ss-report-heading"><h3>🧾 '+esc(LANG==='ar'?'ملخص الأعراض المفهومة':'Understood symptom summary')+'</h3></div>';
        if(presentSymptoms.length) h += '<div class="ss-details-block"><b>'+esc(LANG==='ar'?'الأعراض الموجودة:':'Present symptoms:')+'</b> '+esc(presentSymptoms.join(LANG==='ar'?'، ':', '))+'</div>';
        if(absentSymptoms.length) h += '<div class="ss-details-block"><b>'+esc(LANG==='ar'?'أعراض غير موجودة حسب إجابتك:':'Symptoms you reported as absent:')+'</b> '+esc(absentSymptoms.join(LANG==='ar'?'، ':', '))+'</div>';
        h += '</section>';
      }

      // 3.5) Multi-symptom pattern intelligence — deterministic KB interaction data only.
      const patterns = Array.isArray(d.pattern_insights) ? d.pattern_insights : [];
      if (patterns.length && u !== 'high') {
        h += '<section class="ss-report-card ss-pattern-card"><div class="ss-report-heading"><h3>🧩 '+esc(LANG==='ar'?'ذكاء نمط الأعراض':'Symptom pattern intelligence')+'</h3><span class="ss-count">'+patterns.length+' '+esc(LANG==='ar'?'نمط':'patterns')+'</span></div>';
        h += '<div class="ss-pattern-intro">'+esc(LANG==='ar'?'يلاحظ المحرك الأعراض التي تظهر معًا ويستخدمها كإشارة صغيرة لتحسين ترتيب الاحتمالات الموثقة — بدون تحويلها إلى تشخيص.':'The engine notices symptoms that occur together and uses them as a small signal to improve ranking of source-grounded possibilities — never as a diagnosis.')+'</div><div class="ss-pattern-grid">';
        patterns.slice(0,4).forEach(function(p){ h += '<article><span>✦</span><div><b>'+esc(p.label||'')+'</b><small>'+esc(p.note||'')+'</small></div></article>'; });
        h += '</div><div class="ss-pattern-foot">🛡️ '+esc(LANG==='ar'?'علامات الخطر وقواعد الاستعجال مستقلة ولها الأولوية دائمًا.':'Red-flag and urgency rules are independent and always take priority.')+'</div></section>';
      }

      // 4) Why this assessment — collapsible, API data only.
      h += '<details class="ss-report-details"><summary>🧠 '+esc(LANG==='ar'?'لماذا ظهر هذا التقييم؟':'Why did this assessment appear?')+'</summary><div class="ss-details-body">';
      if (d.why_result) h += '<div class="ss-details-block">'+esc(d.why_result)+'</div>';
      const xai = d.explainability || {};
      if (xai.basis_label) h += '<div class="ss-details-block"><b>'+esc(xai.basis_label)+'</b></div>';
      (xai.factors || []).forEach(function(f){ const sr=f.source_ref||{}; const su=sr.reference_url||sr.official_url||''; const sn=LANG==='ar'?(sr.reference_title_ar||sr.reference_title_en||sr.source_name||''):(sr.reference_title_en||sr.reference_title_ar||sr.source_name||''); h += '<div class="ss-factor"><strong>'+esc(f.label || '')+'</strong>'+(f.detail?'<small>'+esc(f.detail)+'</small>':'')+(su&&sn?'<small>📚 <a href="'+escAttr(safeLink(su))+'" target="_blank" rel="noopener noreferrer">'+esc(sn)+'</a></small>':'')+'</div>'; });
      if (xai.meaning) h += '<div class="ss-details-block"><b>'+esc(LANG==='ar'?'ماذا يعني ذلك؟':'What does this mean?')+'</b><br>'+esc(xai.meaning)+'</div>';
      if (d.risk_reasons && d.risk_reasons.length) {
        h += '<div class="ss-details-block"><b>'+esc(LANG==='ar'?'عوامل أثرت على مستوى الخطورة':'Factors affecting the risk level')+'</b>';
        d.risk_reasons.forEach(function(r){ const txt=r.message||r.description||r.name||''; if(txt) h += '<div class="ss-factor">'+esc(txt)+'</div>'; });
        h += '</div>';
      }
      h += '</div></details>';



      // 5) Danger signs
      h += '<section class="ss-report-card"><div class="ss-report-heading"><h3>🚨 '+esc(LANG==='ar'?'علامات تستدعي الانتباه':'Warning signs')+'</h3></div>';
      if (dangerLines.length) { h += '<div class="ss-flag-list">'; dangerLines.forEach(function(line){ h += '<div class="ss-flag"><span>•</span><span>'+esc(line)+'</span></div>'; }); h += '</div>'; }
      else h += '<div class="ss-empty-note">'+esc(LANG==='ar'?'لم يتم تحديد علامات خطر من المعلومات المدخلة.':'No warning signs were identified from the information entered.')+'</div>';
      h += '</section>';

      // 6) Medical sources — collapsible, URLs hidden behind explicit buttons.
      h += '<details class="ss-report-details"><summary><span>📚 '+esc(LANG==='ar'?'المصادر الطبية':'Medical sources')+' — '+sources.length+' '+esc(LANG==='ar'?'مصادر':'sources')+'</span></summary><div class="ss-details-body"><div class="ss-source-list">';
      if (sources.length) {
        sources.forEach(function(src){
          const url = src.reference_url || src.official_url || '';
          const title = LANG==='ar' ? (src.reference_title_ar || src.reference_title_en || '') : (src.reference_title_en || src.reference_title_ar || '');
          const label = (LANG==='en' && /[\u0600-\u06FF]/.test(src.source_name||'') && src.organization) || src.source_name || src.organization || 'Source';
          const org = src.organization && src.organization !== label ? src.organization : '';
          const typeMap = {government:['جهة حكومية','Government health authority'],international_organization:['منظمة صحية دولية','International health organization'],national_health_service:['خدمة صحية وطنية','National health service'],academic_medical_institution:['مؤسسة طبية أكاديمية','Academic medical institution'],other_trusted_source:['مصدر صحي موثوق','Trusted health source']};
          const typePair = typeMap[String(src.source_type)] || [LANG==='ar'?'مصدر صحي موثوق':'Trusted health source', LANG==='ar'?'مصدر صحي موثوق':'Trusted health source'];
          const typeLabel = typePair[LANG==='ar'?0:1];
          const verified = String(src.verification_status||'').toLowerCase()==='verified';
          const verifiedAt = src.last_verified || src.source_last_verified || '';
          h += '<article class="ss-source-card">';
          h += '<div class="ss-source-top">';
          h += '<div class="ss-source-brand"><div class="ss-source-mark">'+esc(sourceInitials(label))+'</div><div><div class="ss-source-name">'+esc(label)+'</div>'+(org?'<div class="ss-source-org">'+esc(org)+'</div>':'')+'</div></div>';
          h += '<div class="ss-source-badges"><span class="ss-source-badge ss-type">'+esc(typeLabel)+'</span>'+(verified?'<span class="ss-source-badge ss-verified">'+esc(LANG==='ar'?'موثّق':'Verified')+'</span>':'')+'</div>';
          h += '</div>';
          if(title) h += '<div class="ss-source-title">'+esc(title)+'</div>';
          if(verifiedAt) h += '<div class="ss-source-meta"><span>🕒 '+esc((LANG==='ar'?'آخر مراجعة: ':'Last reviewed: ')+verifiedAt)+'</span></div>';
          h += '<div class="ss-source-actions">'+(url?'<a class="ss-source-link" href="'+escAttr(safeLink(url))+'" target="_blank" rel="noopener noreferrer">'+esc(LANG==='ar'?'عرض المصدر الأصلي':'Open source')+'</a>':'')+'</div>';
          h += '</article>';
        });
      } else h += '<div class="ss-empty-note">'+esc(LANG==='ar'?'لا توجد مصادر إضافية مرفقة بهذه النتيجة.':'No additional sources are attached to this result.')+'</div>';
      h += '</div></div></details>';

      // 7) Home care — only if the API already provides it.
      if (homeLines.length) {
        h += '<section class="ss-report-card"><div class="ss-report-heading"><h3>🏠 '+esc(LANG==='ar'?'الرعاية المنزلية':'Home care')+'</h3></div><div class="ss-care-list">';
        homeLines.forEach(function(line){ h += '<div class="ss-care"><span>•</span><span>'+esc(line)+'</span></div>'; });
        h += '</div></section>';
      }
      h += reliefTrackerHtml(d,input);

      // 8) Existing follow-up assistant prompts
      h += '<section class="ss-report-card"><div class="ss-report-heading"><h3>💡 '+esc(TT('questions_title'))+'</h3></div><div class="ss-question-chips">';
      questions.filter(Boolean).forEach(function(question){ h += '<button type="button" class="ss-question-chip" data-question="'+escAttr(question)+'">'+esc(question)+'</button>'; });
      h += '</div><div class="ss-question-answer" id="reportQuestionAnswer" aria-live="polite" hidden></div></section>';

      h += '<section class="ss-report-card"><div class="ss-report-heading"><h3>👤 '+esc(LANG==='ar'?'المعلومات المدخلة':'Entered information')+'</h3></div><div class="ss-input-grid">';
      inputRows.forEach(function(row){ h += '<div class="ss-input-item"><span class="ss-input-label">'+esc(row[0])+'</span><span class="ss-input-value">'+esc(String(row[1]))+'</span></div>'; });
      h += '</div></section>';

      // Existing actions only.
      h += '<section class="ss-report-card ss-user-actions"><div class="ss-report-heading"><h3>'+esc(LANG==='ar'?'أدوات المتابعة':'Follow-up tools')+'</h3></div><div class="ss-report-actions">';
      h += '<button type="button" class="ss-report-action primary" data-result-action="status"><span class="ss-action-icon" aria-hidden="true">🔄</span><span class="ss-action-label">'+esc(LANG==='ar'?'تحديث حالتي':'Update my status')+'</span></button>';
      if(state.quick_mode&&u!=='high') h += '<button type="button" class="ss-report-action" data-result-action="detailed"><span class="ss-action-icon" aria-hidden="true">🩺</span><span class="ss-action-label">'+esc(LANG==='ar'?'إكمال التحليل المفصل':'Continue full assessment')+'</span></button>';
      h += '<button type="button" class="ss-report-action" data-result-action="restart"><span class="ss-action-icon" aria-hidden="true">➕</span><span class="ss-action-label">'+esc(LANG==='ar'?'تحليل جديد':'New analysis')+'</span></button>';
      if (d.record_id) h += '<button type="button" class="ss-report-action" data-result-action="reanalyze" data-record-id="'+Number(d.record_id)+'"><span class="ss-action-icon" aria-hidden="true">✏️</span><span class="ss-action-label">'+esc(LANG==='ar'?'تعديل إجاباتي':'Edit my answers')+'</span></button>';
      h += '<button type="button" class="ss-report-action" data-result-action="download" data-record-id="'+Number(d.record_id||0)+'"><span class="ss-action-icon" aria-hidden="true">📄</span><span class="ss-action-label">'+esc(LANG==='ar'?'تحميل التقرير':'Download report')+'</span></button>';
      h += '<button type="button" class="ss-report-action" data-doctor-card-action><span class="ss-action-icon" aria-hidden="true">🩺</span><span class="ss-action-label">'+esc(u==='high'?(LANG==='ar'?'ملخص للطوارئ والطبيب':'Emergency & clinician summary'):(LANG==='ar'?'ملخص للعيادة والطبيب':'Clinic & clinician summary'))+'</span></button>';
      h += '</div><div id="statusUpdateStatus" class="ss-feedback-msg" aria-live="polite" hidden></div><div id="reportActionStatus" class="ss-feedback-msg" aria-live="polite" hidden></div></section>';

      // Feedback: 1–5 stars + optional comment. Public sharing requires explicit opt-in.
      h += '<section class="ss-report-card ss-feedback"><p>'+esc(LANG==='ar'?'كيف تقيّم نتيجة التحليل؟':'How would you rate this analysis result?')+'</p><div class="ss-star-rating" role="group" aria-label="Rating out of 5">';
      for(let star=1;star<=5;star++) h += '<button type="button" class="ss-star-btn" data-star="'+star+'" aria-label="'+star+'/5">☆</button>';
      h += '</div><div class="ss-feedback-reasons" id="fbReasons" aria-label="'+esc(LANG==='ar'?'سبب التقييم':'Feedback reason')+'">';
      const feedbackReasons=[['clear',LANG==='ar'?'واضحة':'Clear'],['helpful',LANG==='ar'?'مفيدة':'Helpful'],['missing_detail',LANG==='ar'?'أحتاج تفاصيل أكثر':'Need more detail'],['unclear',LANG==='ar'?'غير واضحة':'Unclear'],['not_relevant',LANG==='ar'?'غير مرتبطة بما أدخلت':'Not relevant'],['other',LANG==='ar'?'سبب آخر':'Other']];
      feedbackReasons.forEach(function(x){h+='<button type="button" class="ss-feedback-reason" data-reason="'+escAttr(x[0])+'">'+esc(x[1])+'</button>';});
      h += '</div><textarea id="fbComment" class="ss-feedback-comment" maxlength="500" placeholder="'+esc(LANG==='ar'?'ملاحظة إضافية (اختياري)':'Additional comment (optional)')+'"></textarea><label class="ss-feedback-public"><input type="checkbox" id="fbPublic"> <span>'+esc(LANG==='ar'?'أوافق على عرض تعليقي بشكل مجهول في لوحة مستخدمي الموقع.':'I agree to show my comment anonymously on the public community dashboard.')+'</span></label><button type="button" class="ss-feedback-submit" id="fbSubmit" disabled>'+esc(LANG==='ar'?'إرسال التقييم':'Submit rating')+'</button><div id="fbMsg" class="ss-feedback-msg" aria-live="polite"></div></section>';

      // 12) One disclaimer only.
      h += '<div class="ss-report-disclaimer">⚠️ '+esc(LANG==='ar'?'هذه النتيجة توعوية ولا تقدم تشخيصًا طبيًا، ولا تغني عن استشارة مختص صحي عند الحاجة.':'This result is educational and does not provide a medical diagnosis or replace professional medical advice when needed.')+'</div>';
      h += '</div>';

      const host = document.createElement('div');
      host.className = 'bubble result';
      host.innerHTML = h;
      bodyEl.replaceChildren(host);
      // Bind result actions directly instead of relying on legacy inline handlers.
      // This remains reliable under the site's strict CSP (script-src-attr 'none')
      // and on browsers where MutationObserver delivery can lag behind a quick tap.
      host.querySelectorAll('[data-quick-edit]').forEach(function(btn){
        btn.addEventListener('click',function(){
          const field=btn.dataset.quickEdit||'';
          const rid=Number((lastResult||{}).record_id||0);
          leaveResultModeForEditor(); optsEl.hidden=false; state.previous_record_id=rid||state.previous_record_id;
          if(field==='symptoms'){ symptomInputMethod='pick'; bodyEl.textContent=''; askSymptoms(); return; }
          if(field==='location'){ symptomInputMethod='body'; bodyEl.textContent=''; askSymptoms(); setTimeout(function(){openBodyMapSheet(state.body_region_primary||null);},0); return; }
          if(field==='duration'){ state.duration=null; bodyEl.textContent=''; askDuration(); return; }
          if(field==='severity'){ state.severity=null; bodyEl.textContent=''; askSeverity(); return; }
        });
      });
      host.querySelectorAll('[data-result-action]').forEach(function(btn){
        btn.addEventListener('click', function(){
          const action=btn.dataset.resultAction||'';
          const recordId=Number(btn.dataset.recordId||0);
          if(action==='restart') return restart();
          if(action==='reanalyze') return beginReanalysis(recordId);
          if(action==='download') return downloadAnalysisReport(btn,recordId);
          if(action==='status') return openStatusUpdate();
          if(action==='detailed') return upgradeToDetailedAssessment();
        });
      });
      host.querySelectorAll('.ss-star-btn').forEach(function(btn){
        btn.addEventListener('click',function(){selectFeedbackStar(Number(btn.dataset.star||0));});
      });
      host.querySelectorAll('.ss-feedback-reason').forEach(function(btn){btn.addEventListener('click',function(){selectFeedbackReason(btn.dataset.reason||'');});});
      const feedbackSubmitBtn=host.querySelector('#fbSubmit');
      if(feedbackSubmitBtn) feedbackSubmitBtn.addEventListener('click',submitFeedback);
      // iOS Safari can preserve a previous nested scroll offset even after the
      // questionnaire DOM is replaced. Reset every possible scroll surface more
      // than once so the report always opens at "Analysis result" rather than
      // halfway through the summary card.
      const scrollContainer = bodyEl.closest('.container');
      function resetResultScroll(){
        try { bodyEl.scrollTop = 0; } catch(e) {}
        try { if (wrap) wrap.scrollTop = 0; } catch(e) {}
        try { if (scrollContainer) scrollContainer.scrollTop = 0; } catch(e) {}
        try { document.documentElement.scrollTop = 0; document.body.scrollTop = 0; } catch(e) {}
        try { window.scrollTo(0, 0); } catch(e) {}
      }
      resetResultScroll();
      requestAnimationFrame(function(){ resetResultScroll(); requestAnimationFrame(resetResultScroll); });
      setTimeout(resetResultScroll, 80);
      setTimeout(resetResultScroll, 220);

      host.querySelectorAll('.ss-question-chip').forEach(function(btn){ btn.addEventListener('click', function(){ askResultQuestion(btn.dataset.question || ''); }); });
      host.querySelectorAll('[data-relief-factor]').forEach(function(btn){btn.addEventListener('click',function(){saveReliefFactor(btn.dataset.reliefFactor||'',btn);});});
      if(host.querySelector('#reliefTracker')) loadReliefSummary();
      const doctorCardBtn=host.querySelector('[data-doctor-card-action]'); if(doctorCardBtn) doctorCardBtn.addEventListener('click', openDoctorCard);
      host.querySelectorAll('details.ss-report-details').forEach(function(detail){
        detail.addEventListener('toggle', function(){
          const keep = bodyEl.scrollTop;
          requestAnimationFrame(function(){ bodyEl.scrollTop = keep; });
        });
      });
    }
    async function downloadAnalysisReport(btn, recordId){
      const original = btn ? btn.innerHTML : '';
      const status = document.getElementById('reportActionStatus');
      if (status) { status.hidden = true; status.textContent = ''; }
      if (btn) { btn.disabled = true; btn.textContent = LANG==='ar' ? '⏳ جاري تجهيز التقرير…' : '⏳ Preparing report…'; }
      try {
        // The report is built from the result currently shown (plus the user's follow-up answers); the saved record is only a fallback.
        const exportBody = JSON.stringify({result:Object.assign({}, lastResult||{}, {followup_answers:(typeof differentialAnswers!=='undefined'&&Array.isArray(differentialAnswers))?differentialAnswers.slice(0,20):[]}),lang:LANG});
        let response = lastResult ? await fetch('/api/analyze/export-current', {method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:exportBody}) : null;
        let type = response ? (response.headers.get('content-type') || '').toLowerCase() : '';
        if ((!response || !response.ok || !type.includes('application/pdf')) && recordId) {
          response = await fetch('/api/analyze/export/'+encodeURIComponent(String(recordId)), {credentials:'same-origin'});
          type = (response.headers.get('content-type') || '').toLowerCase();
        }
        if (!response) { response = await fetch('/api/analyze/export-current', {method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:exportBody}); type = (response.headers.get('content-type') || '').toLowerCase(); }
        if (!response.ok || !type.includes('application/pdf')) {
          let message = LANG==='ar' ? 'تعذر تجهيز التقرير حاليًا. حاول مرة أخرى.' : 'Unable to prepare the report right now. Please try again.';
          try { const data = await response.json(); if (data && data.error) message = data.error; } catch(e) {}
          throw new Error(message);
        }
        const blob = await response.blob();
        if (!blob.size) throw new Error(LANG==='ar' ? 'ملف التقرير فارغ.' : 'The report file is empty.');
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'SymptoSense_Report_'+(recordId||'current')+'.pdf';
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        setTimeout(function(){ URL.revokeObjectURL(url); link.remove(); }, 60000);
      } catch (err) {
        const msg = (err && err.message) || (LANG==='ar' ? 'تعذر تحميل التقرير حاليًا.' : 'Unable to download the report.');
        if (status) { status.textContent = msg; status.hidden = false; } else { alert(msg); }
      } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = original; }
      }
    }
    let lastResult = null;
    function cloneAnalysisInput(value){
      try{return JSON.parse(JSON.stringify(value||{}));}catch(e){return {}}
    }
    function editedSymptomsFromText(value){
      return Array.from(new Set(String(value||'').replace(/[،؛;\n]+/g,',').split(',').map(x=>x.trim()).filter(Boolean))).slice(0,20).map(x=>x.slice(0,300));
    }
    function leaveResultModeForEditor(){
      const wrap=bodyEl.closest('.chat-wrap'); if(wrap){wrap.classList.remove('report-mode');wrap.style.removeProperty('overflow')}
      bodyEl.classList.remove('result-mode'); bodyEl.hidden=false; bodyEl.style.display='block'; bodyEl.textContent=''; bodyEl.scrollTop=0;
      clearOpts(); optsEl.hidden=true; hideText();
      const safetyNote=document.getElementById('chatSafetyNote'); if(safetyNote)safetyNote.style.visibility='visible';
      try{window.scrollTo(0,0)}catch(e){}
    }
    function renderAnswerEditor(id,base){
      leaveResultModeForEditor();
      const current=Object.assign({},cloneAnalysisInput(state),cloneAnalysisInput(base||{}));
      const durationValue=current.duration||state.duration||'';
      const severityValue=Number(current.severity||state.severity||0);
      const genderValue=String(current.gender||state.gender||'').toLowerCase();
      const symptomValues=(current.symptoms&&current.symptoms.length?current.symptoms:state.symptoms||[]).filter(Boolean);
      const durationOptions=[''].concat(DURS).map(function(v){return '<option value="'+escAttr(v)+'" '+(String(v)===String(durationValue)?'selected':'')+'>'+esc(v|| (LANG==='ar'?'اختر المدة':'Choose duration'))+'</option>';}).join('');
      const severityOptions=['<option value="">'+esc(LANG==='ar'?'اختر الشدة':'Choose severity')+'</option>'].concat(SEVS.map(function(x){return '<option value="'+Number(x[0])+'" '+(Number(x[0])===severityValue?'selected':'')+'>'+esc(x[1])+'</option>';})).join('');
      const host=document.createElement('div'); host.className='answer-edit-panel'; host.id='answerEditPanel';
      host.innerHTML='<div class="answer-edit-head"><div><h3>✏️ '+esc(LANG==='ar'?'تعديل إجاباتي':'Edit my answers')+'</h3><p>'+esc(LANG==='ar'?'عدّل أي خانة ثم اضغط «حفظ وإعادة التحليل». القيم الحالية معبأة لك مسبقًا.':'Change any field, then press “Save & re-analyze”. Your current answers are pre-filled.')+'</p></div></div>'
        +'<div class="answer-edit-grid">'
        +'<div class="answer-edit-field"><label for="editAnswerAge">'+esc(LANG==='ar'?'العمر':'Age')+'</label><input id="editAnswerAge" type="number" min="0" max="120" inputmode="numeric" value="'+escAttr(current.age==null?'':current.age)+'"></div>'
        +'<div class="answer-edit-field"><label for="editAnswerGender">'+esc(LANG==='ar'?'الجنس':'Sex')+'</label><select id="editAnswerGender"><option value="">'+esc(LANG==='ar'?'غير محدد':'Not specified')+'</option><option value="m" '+(genderValue==='m'||genderValue==='male'?'selected':'')+'>'+esc(LANG==='ar'?'ذكر':'Male')+'</option><option value="f" '+(genderValue==='f'||genderValue==='female'?'selected':'')+'>'+esc(LANG==='ar'?'أنثى':'Female')+'</option></select></div>'
        +'<div class="answer-edit-field wide"><label for="editAnswerSymptoms">'+esc(LANG==='ar'?'الأعراض':'Symptoms')+'</label><textarea id="editAnswerSymptoms" placeholder="'+escAttr(LANG==='ar'?'اكتب الأعراض وافصل بينها بفاصلة، مثال: صداع، غثيان':'Enter symptoms separated by commas, e.g. headache, nausea')+'">'+esc(symptomValues.join(LANG==='ar'?'، ':', '))+'</textarea></div>'
        +'<div class="answer-edit-field"><label for="editAnswerDuration">'+esc(LANG==='ar'?'مدة الأعراض':'Symptom duration')+'</label><select id="editAnswerDuration">'+durationOptions+'</select></div>'
        +'<div class="answer-edit-field"><label for="editAnswerSeverity">'+esc(LANG==='ar'?'شدة الأعراض':'Severity')+'</label><select id="editAnswerSeverity">'+severityOptions+'</select></div>'
        +'<div class="answer-edit-field wide"><label for="editAnswerConditions">'+esc(LANG==='ar'?'أمراض أو حالات سابقة':'Health conditions')+'</label><textarea id="editAnswerConditions">'+esc(current.conditions||state.conditions||'')+'</textarea></div>'
        +'<div class="answer-edit-field wide"><label for="editAnswerMeds">'+esc(LANG==='ar'?'الأدوية الحالية':'Current medications')+'</label><textarea id="editAnswerMeds">'+esc(current.medications||state.medications||'')+'</textarea></div>'
        +'<div class="answer-edit-field wide"><label for="editAnswerAllergies">'+esc(LANG==='ar'?'الحساسية':'Allergies')+'</label><textarea id="editAnswerAllergies">'+esc(current.allergies||state.allergies||'')+'</textarea></div>'
        +'<div class="answer-edit-field wide"><label for="editAnswerNotes">'+esc(LANG==='ar'?'ملاحظات إضافية':'Additional notes')+'</label><textarea id="editAnswerNotes">'+esc(current.notes||state.notes||'')+'</textarea></div>'
        +'</div><div id="answerEditError" class="answer-edit-error" role="alert"></div>'
        +'<div class="answer-edit-actions"><button type="button" class="ss-btn-primary" data-answer-edit-save>✓ '+esc(LANG==='ar'?'حفظ وإعادة التحليل':'Save & re-analyze')+'</button><button type="button" class="opt" data-answer-edit-step>🩺 '+esc(LANG==='ar'?'تعديل خطوة بخطوة':'Edit step by step')+'</button><button type="button" class="opt" data-answer-edit-cancel>'+esc(LANG==='ar'?'الرجوع للنتيجة':'Back to result')+'</button></div>';
      bodyEl.appendChild(host);
      requestAnimationFrame(function(){try{host.scrollIntoView({behavior:'auto',block:'start'});}catch(e){}});
      function applyEditor(){
        const err=host.querySelector('#answerEditError'); if(err)err.textContent='';
        const rawAge=String(host.querySelector('#editAnswerAge').value||'').trim();
        const age=rawAge===''?null:Number(rawAge);
        const syms=editedSymptomsFromText(host.querySelector('#editAnswerSymptoms').value);
        const duration=host.querySelector('#editAnswerDuration').value||null;
        const severity=Number(host.querySelector('#editAnswerSeverity').value||0)||null;
        if(age!==null&&(!Number.isFinite(age)||age<0||age>120)){if(err)err.textContent=LANG==='ar'?'أدخل عمرًا صحيحًا بين 0 و120.':'Enter a valid age from 0 to 120.';return false}
        if(!syms.length){if(err)err.textContent=LANG==='ar'?'أدخل عرضًا واحدًا على الأقل.':'Enter at least one symptom.';return false}
        if(!duration){if(err)err.textContent=LANG==='ar'?'اختر مدة الأعراض.':'Choose symptom duration.';return false}
        if(!severity){if(err)err.textContent=LANG==='ar'?'اختر شدة الأعراض.':'Choose symptom severity.';return false}
        const oldSymptoms=(state.symptoms||[]).join('||');
        const oldGender=String(state.gender||'').toLowerCase();
        const newGender=String(host.querySelector('#editAnswerGender').value||'').toLowerCase();
        state.age=age; state.gender=newGender||null; state.symptoms=syms; state.duration=duration; state.severity=severity;
        state.conditions=host.querySelector('#editAnswerConditions').value.trim(); state.medications=host.querySelector('#editAnswerMeds').value.trim(); state.allergies=host.querySelector('#editAnswerAllergies').value.trim(); state.notes=host.querySelector('#editAnswerNotes').value.trim();
        state.history_answered=true; state.previous_record_id=id; state.smart_prompt_shown=true;
        if(oldSymptoms!==state.symptoms.join('||')||oldGender!==newGender){state.onset=null;state.course=null;state.pattern_worse=null;state.pattern_relief=null;state.pattern_context_done=false;differentialAnswers=[];differentialNegatives=[];differentialCount=0;}
        lastAnalysisInput=cloneAnalysisInput(Object.assign({},state,{lang:LANG}));
        return true;
      }
      host.querySelector('[data-answer-edit-save]').addEventListener('click',function(){
        if(!applyEditor())return;
        bodyEl.textContent=''; optsEl.hidden=false; add(LANG==='ar'?'تم تحديث إجاباتك. سأعيد التحليل بالقيم الجديدة.':'Your answers were updated. I’ll re-run the assessment with the new values.','bot'); runAnalysis();
      });
      host.querySelector('[data-answer-edit-step]').addEventListener('click',function(){
        if(!applyEditor())return;
        bodyEl.textContent=''; optsEl.hidden=false; add(LANG==='ar'?'تم حفظ التعديلات الحالية. يمكنك الآن مراجعة الأعراض وبقية الخطوات بالتفصيل.':'Current edits saved. You can now review symptoms and the remaining steps in detail.','bot'); askSymptoms();
      });
      host.querySelector('[data-answer-edit-cancel]').addEventListener('click',function(){
        const q=new URLSearchParams(location.search);
        if(q.get('from')==='history'){history.back();return;}
        if(lastResult)renderResult(lastResult);else restart();
      });
      setTimeout(function(){const f=host.querySelector('#editAnswerSymptoms');if(f)f.focus();},50);
    }
    async function beginReanalysis(id) {
      trackJourney('reanalyze');
      compareBase={record_id:id,symptoms:(state.symptoms||[]).slice(),duration:state.duration,severity:state.severity,urgency:(lastResult||{}).urgency||'low'};
      state.previous_record_id=id; state.smart_prompt_shown=true;
      let base=cloneAnalysisInput(lastAnalysisInput||{});
      if(!Array.isArray(base.symptoms)||!base.symptoms.length){
        try{
          const r=await fetch('/api/analysis/'+id,{credentials:'same-origin',cache:'no-store'}),d=await r.json();
          if(r.ok&&d.ok&&d.analysis){const a=d.analysis;base={age:a.age,gender:a.gender,symptoms:a.symptoms||[],duration:a.duration,severity:a.severity,notes:(a.result||{}).notes||'',location:(a.result||{}).location||''};}
        }catch(e){}
      }
      renderAnswerEditor(id,base);
    }
