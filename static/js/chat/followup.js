/* SymptoSense chat — Differential/follow-up questions and the smart follow-up after a result.
   Classic script: shares the page's global scope with the other files in /static/js/chat/. Load order is fixed by chat_view.py. */
    // One wire schema: better|same|worse + new_sign (local UI words improved/new_symptoms are mapped here).
    function fuWire(id,o){return {record_id:id,outcome:o==='improved'?'better':(o==='new_symptoms'?'worse':o),new_sign:o==='new_symptoms'};}
    async function recordSmartFollowup(rec, outcome, continueFn) {
      try {
        const r=await fetch('/api/smart-followup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(fuWire(rec.id,outcome))});
        const d=await r.json(); if(!r.ok||!d.ok) throw new Error(d.error||'followup_failed');
      } catch(e) { /* Follow-up logging must never block the assessment flow. */ }
      if(outcome==='improved'){
        add(LANG==='ar'?'جميل أن الأعراض تحسنت. إذا عندك عرض جديد نبدأ تحليلًا جديدًا، وإذا رجعت أو ساءت الأعراض أعد التقييم.':'Glad the symptoms improved. Start a new assessment for a new symptom, and reassess if symptoms return or worsen.','bot');
        continueFn(); return;
      }
      compareBase={record_id:rec.id,symptoms:(rec.symptoms||[]).slice(),duration:rec.duration,severity:rec.severity,urgency:rec.urgency};
      state.previous_record_id=rec.id; state.age=rec.age||null; state.gender=rec.gender||null; state.symptoms=(rec.symptoms||[]).slice(); state.duration=null; state.severity=null; state.smart_prompt_shown=true;
      add(LANG==='ar'?'بنقارن حالتك بالتحليل السابق. عدّل الأعراض إذا تغيرت، ثم جاوب عن المدة والشدة من جديد.':'We will compare with your previous assessment. Update symptoms if they changed, then answer duration and severity again.','bot');
      askSymptoms();
    }
    function maybeOfferSmartFollowup(ui, continueFn){
      if(!(ui&&ui.ok&&ui.logged_in)){continueFn();return;}
      fetch('/api/smart-followup',{cache:'no-store'}).then(r=>r.json()).then(function(d){
        if(!d.ok||!d.eligible||!d.analysis){continueFn();return;}
        const rec=d.analysis; const syms=(rec.symptoms||[]).join(LANG==='ar'?'، ':', ');
        const when=String(rec.timestamp||'').slice(0,10);
        add((LANG==='ar'?'متابعة ذكية: آخر تحليل لك كان '+when+(syms?' عن '+syms:'')+'. كيف أصبحت الأعراض؟':'Smart follow-up: your last assessment was on '+when+(syms?' for '+syms:'')+'. How are the symptoms now?'),'bot');
        showOpts([
          {label:'✅ '+(LANG==='ar'?'تحسنت':'Improved'),fn:function(){clearOpts();recordSmartFollowup(rec,'improved',continueFn);}},
          {label:'➖ '+(LANG==='ar'?'مثل ما هي':'About the same'),fn:function(){clearOpts();recordSmartFollowup(rec,'same',continueFn);}},
          {label:'📈 '+(LANG==='ar'?'أسوأ':'Worse'),cls:'danger',fn:function(){clearOpts();recordSmartFollowup(rec,'worse',continueFn);}},
          {label:'➕ '+(LANG==='ar'?'ظهرت أعراض جديدة':'New symptoms appeared'),fn:function(){clearOpts();recordSmartFollowup(rec,'new_symptoms',continueFn);}},
          {label:'🆕 '+(LANG==='ar'?'أبدأ تحليلًا جديدًا':'Start a new assessment'),fn:function(){clearOpts();continueFn();}}
        ]);
      }).catch(function(){continueFn();});
    }
    function renderDifferentialImpact(previous, current, answerInfo) {
      if (!answerInfo || !Array.isArray(previous) || !previous.length || !Array.isArray(current) || !current.length) return;
      const oldRank = {}; const newRank = {};
      previous.forEach(function(x,i){ if(x&&x.slug) oldRank[x.slug]=i; });
      current.forEach(function(x,i){ if(x&&x.slug) newRank[x.slug]=i; });
      const closer=[]; const lower=[];
      current.forEach(function(x,i){
        if(!x||!x.slug) return;
        if(oldRank[x.slug] === undefined || i < oldRank[x.slug]) closer.push(x.name||x.slug);
      });
      previous.forEach(function(x,i){
        if(!x||!x.slug) return;
        if(newRank[x.slug] === undefined || newRank[x.slug] > i) lower.push(x.name||x.slug);
      });
      let detail='';
      if (closer.length || lower.length) {
        const parts=[];
        if(closer.length) parts.push((LANG==='ar'?'أصبح أقرب في الترتيب: ':'Moved closer in the ranking: ')+closer.slice(0,2).join(LANG==='ar'?'، ':', '));
        if(lower.length) parts.push((LANG==='ar'?'تراجع في الترتيب: ':'Moved lower in the ranking: ')+lower.slice(0,2).join(LANG==='ar'?'، ':', '));
        detail=parts.join(LANG==='ar'?' · ':' · ');
      } else {
        const top=current[0] && (current[0].name||current[0].slug);
        detail = top
          ? ((LANG==='ar'?'لم تغيّر الإجابة ترتيب أبرز الاحتمالات بشكل واضح؛ ما زال ':'The answer did not clearly change the leading order; ')+top+(LANG==='ar'?' ضمن الأقرب.':' remains among the closest matches.'))
          : (LANG==='ar'?'لم يظهر تغير واضح في ترتيب الاحتمالات.':'No clear ranking change was detected.');
      }
      const answerLabel = answerInfo.answer==='yes' ? (LANG==='ar'?'نعم':'Yes') : (LANG==='ar'?'لا':'No');
      addHtml('<div class="followup-impact"><div class="followup-impact-title">↕ '+esc(LANG==='ar'?'كيف غيّرت إجابتك النتيجة؟':'How did your answer change the result?')+'</div><div class="followup-impact-answer">'+esc(answerLabel+' — '+(answerInfo.symptom_name||answerInfo.question||''))+'</div><div class="followup-impact-detail">'+esc(detail)+'</div><div class="followup-impact-note">'+esc(LANG==='ar'?'تغيير في ترتيب المطابقة فقط، وليس نسبة تشخيص.':'This is only a change in match ordering, not a diagnostic probability.')+'</div></div>','bot');
    }
    async function startDifferentialQuestions() {
      // Smart follow-up re-ranks the differential after every Yes/No answer.
      // It asks up to five high-value questions and does not stop for a clear
      // lead before at least three have been answered. Slow/unavailable refinement fails
      // open so the user can always reach the assessment.
      if (differentialCount >= SMART_FOLLOWUP_MAX || followupTotal >= FOLLOWUP_TOTAL_MAX) { showDataQualityGate(); return; }
      state.step = 'clarification';
      updateFlow('conditions');
      clearOpts();
      focusStepQuestion('⏳ ' + (LANG==='ar'?'أراجع إجاباتك لتحديد سؤال متابعة مفيد…':'Reviewing your answers for one useful follow-up…'));
      const controller = new AbortController();
      const timer = setTimeout(function(){ controller.abort(); }, 4500);
      try {
        const r = await fetch('/api/analyze/differential-question', {
          method:'POST', headers:{'Content-Type':'application/json'}, signal:controller.signal,
          body:JSON.stringify({symptoms:state.symptoms, asked:differentialAsked, negatives:differentialNegatives, gender:state.gender, lang:LANG})
        });
        const d = await r.json();
        if (d.consent_required) { location.href=d.consent_url||'/consent?next=/chat'; return; }
        const previousCandidates = Array.isArray(differentialCandidates) ? differentialCandidates.slice() : [];
        const nextCandidates = Array.isArray(d.candidates) ? d.candidates.slice() : [];
        if (differentialLastAnswer && previousCandidates.length && nextCandidates.length) renderDifferentialImpact(previousCandidates, nextCandidates, differentialLastAnswer);
        differentialLastAnswer = null;
        if (nextCandidates.length) differentialCandidates = nextCandidates;
        if (!r.ok || !d.ok || d.done || !d.question || !d.symptom_slug) { showDataQualityGate(); return; }
        differentialCount += 1;
        followupTotal += 1;
        differentialAsked.push(d.symptom_slug);
        const qNo = Number(d.question_number || differentialCount);
        const qMax = Number(d.max_questions || SMART_FOLLOWUP_MAX);
        addHtml('<div class="adaptive-step">'+esc((LANG==='ar'?'ساعدنا نفهم أكثر · سؤال ':'Help us understand better · Question ')+qNo+(LANG==='ar'?' من ':' of ')+qMax)+'</div>','bot');
        if (d.question_reason) addHtml('<div class="muted" style="font-size:11.5px;line-height:1.65;margin-top:-4px">'+esc(d.question_reason)+'</div>','bot');
        focusStepQuestion('🩺 ' + d.question);
        const answerOpts=[
          {label:TT('clar_yes'), fn:function(){
            add(TT('clar_yes'),'user');
            differentialLastAnswer={question:d.question,symptom_name:d.symptom_name||d.symptom_slug,answer:'yes'};
            differentialAnswers.push({slug:d.symptom_slug,name:d.symptom_name||d.symptom_slug,answer:'yes'});
            if (d.symptom_name && state.symptoms.indexOf(d.symptom_name) === -1) state.symptoms.push(d.symptom_name);
            state.notes += (state.notes?' ':'') + d.question + ' -> ' + (LANG==='ar'?'نعم':'Yes');
            startDifferentialQuestions();
          }},
          {label:TT('clar_no'), fn:function(){
            add(TT('clar_no'),'user');
            differentialLastAnswer={question:d.question,symptom_name:d.symptom_name||d.symptom_slug,answer:'no'};
            differentialAnswers.push({slug:d.symptom_slug,name:d.symptom_name||d.symptom_slug,answer:'no'});
            differentialNegatives.push(d.symptom_slug);
            state.notes += (state.notes?' ':'') + (LANG==='ar'?'تم نفي عرض متابعة.':'A follow-up symptom was denied.');
            startDifferentialQuestions();
          }}
        ];
        // Let the user end the adaptive sequence after three answered questions;
        // before that, continue gathering enough context unless no question exists.
        if(differentialCount >= 3) answerOpts.push({label:'➡️ '+(LANG==='ar'?'إظهار التحليل الآن':'Show assessment now'), fn:function(){
          add(LANG==='ar'?'إظهار التحليل الآن':'Show assessment now','user');
          showDataQualityGate();
        }});
        showOpts(answerOpts);
      } catch(e) {
        showDataQualityGate();
      } finally {
        clearTimeout(timer);
      }
    }
    function askQuestionFromResult(q) {
      add('💬 ' + q, 'user');
      clearOpts();
      const lr = lastResult || {};
      const rawMatches = Array.isArray(lr.knowledge_matches) ? lr.knowledge_matches : (Array.isArray(lr.possible_conditions) ? lr.possible_conditions : []);
      const safeContext = {
        urgency: lr.urgency || lr.risk_level || lr.risk || null,
        possible_conditions: rawMatches.slice(0,3).map(function(x){
          return {
            name: x.name_ar || x.name_en || x.name || x.condition || '',
            match_level: x.match_level || x.match || x.score || null
          };
        }),
        red_flags: Array.isArray(lr.red_flags) ? lr.red_flags.slice(0,5) : [],
        recommendations: Array.isArray(lr.recommendations) ? lr.recommendations.slice(0,4) : []
      };
      const contextLabel = LANG === 'ar' ? 'سياق مختصر من نتيجة التحليل الحالية:' : 'Brief context from the current analysis result:';
      const prompt = q + '\n\n' + contextLabel + ' ' + JSON.stringify(safeContext);
      fetch('/api/assistant', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({lang:LANG, messages:[{role:'user', content:prompt}]})
      }).then(function(r){return r.json();}).then(function(d){
        if (d.consent_required) { location.href = d.consent_url || '/consent?next=/chat'; return; }
        if (d.ok) add(d.answer || TT('fallback_chat'), 'bot');
        else add(TT('err'), 'bot');
        const followOpts = [
          {label:TT('ask_more'), fn:askFollowup},
          {label:TT('new_analysis'), fn:function(){ restart(); }}
        ];
        if (!(state.member && state.member.id) && !state.member_id) followOpts.push({label:TT('save_profile'), fn:saveMissingToProfile});
        showOpts(followOpts);
      }).catch(function(){ add(TT('conn_err'), 'bot'); });
    }
    function addMissingInfo() {
      add(TT('trans_adding'), 'user');
      clearOpts();
      addQ(TT('trans_add_q'));
      showOpts([
        {label:'📅 ' + TT('trans_add_duration'), fn:function(){
          add(TT('trans_add_duration'), 'user'); clearOpts();
          showOpts([
            {label:'📅 ' + TT('incomplete_today'), fn:function(){ state.duration = LANG==='ar'?'اليوم':'Today'; reAnalyzeWithMoreInfo(lastResult); }},
            {label:'📅 ' + TT('incomplete_yesterday'), fn:function(){ state.duration = LANG==='ar'?'أمس':'Yesterday'; reAnalyzeWithMoreInfo(lastResult); }},
            {label:'📅 ' + TT('incomplete_days'), fn:function(){ state.duration = LANG==='ar'?'عدة أيام':'Several days'; reAnalyzeWithMoreInfo(lastResult); }},
            {label:'📅 ' + TT('incomplete_week'), fn:function(){ state.duration = LANG==='ar'?'أكثر من أسبوع':'More than a week'; reAnalyzeWithMoreInfo(lastResult); }}
          ]);
        }},
        {label:'💊 ' + TT('trans_add_meds'), fn:function(){
          add(TT('trans_add_meds'), 'user'); clearOpts();
          addQ(TT('trans_add_meds_q')); showText(TT('trans_add_meds_hint'), true);
        }},
        {label:'📝 ' + TT('trans_add_notes'), fn:function(){
          add(TT('trans_add_notes'), 'user'); clearOpts();
          addQ(TT('trans_add_notes_q')); showText(TT('trans_add_notes_hint'), true);
        }},
        {label:'✅ ' + TT('trans_add_done'), fn:function(){
          add(TT('trans_add_done'), 'user'); clearOpts();
        }}
      ]);
    }
    function saveMissingToProfile() {
      if (!window.__USER_INFO__ || !window.__USER_INFO__.logged_in) {
        add(TT('save_login_required'), 'bot');
        return;
      }
      if ((state.member && state.member.id) || state.member_id) {
        add(LANG === 'ar' ? 'هذا التحليل مرتبط بملف فرد من العائلة، لذلك لن ننسخ بياناته إلى ملفك الصحي الشخصي.' : 'This assessment belongs to a family profile, so its details will not be copied into your personal health profile.', 'bot');
        return;
      }
      var updates = {};
      const saved = window.__USER_INFO__.profile || {};
      const normalizedGender = state.gender === 'm' ? 'male' : (state.gender === 'f' ? 'female' : state.gender);
      if (normalizedGender && !saved.gender) updates.gender = normalizedGender;
      if (state.weight && !saved.weight) updates.weight = state.weight;
      if (state.height && !saved.height) updates.height = state.height;
      if (Object.keys(updates).length === 0) {
        add(TT('save_nothing_new'), 'bot');
        return;
      }
      fetch('/api/health-profile', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify(updates)
      }).then(function(r){return r.json();}).then(function(d){
        if (d.ok) add(TT('save_success'), 'bot');
        else add(TT('save_error'), 'bot');
      }).catch(function(){ add(TT('conn_err'), 'bot'); });
    }
    function askFollowup() {
      state.step = 'followup';
      add(G(TT('followup_f'), TT('followup_m')), 'bot');
      showText(TT('followup_ph'));
      renderSuggestedQs();
    }
    function setSim(v) {
      const s = document.getElementById('resSimple'), d = document.getElementById('resDetail');
      const sb = document.getElementById('simBtn'), db = document.getElementById('detBtn');
      if (s) s.style.display = v ? 'block' : 'none';
      if (d) d.style.display = v ? 'none' : 'block';
      if (sb) sb.style.display = v ? 'none' : 'inline-block';
      if (db) db.style.display = v ? 'inline-block' : 'none';
    }
    function renderSuggestedQs() {
      const old = document.getElementById('dqBlock');
      if (old) old.remove();
      const qs = [TT('dq_danger'), TT('dq_sev'), TT('dq_home'), TT('dq_doc')];
      if ((lastResult || {}).triage_level === 'emergency' || (lastResult || {}).triage_level === 'today') {
        qs[0] = TT('dq_danger');
      }
      const blk = document.createElement('div');
      blk.id = 'dqBlock';
      let h = '<div class="rel-title">💡 ' + esc(TT('dq_title')) + '</div>';
      h += '<div class="rel-chips">';
      qs.forEach(function(q, i) {
        h += '<button type="button" class="rel-chip" data-dq-index="' + i + '">' + esc(q) + '</button>';
      });
      h += '</div>';
      blk.innerHTML = h;
      optsEl.appendChild(blk);
    }
    function dqAsk(i) {
      const qs = [TT('dq_danger'), TT('dq_sev'), TT('dq_home'), TT('dq_doc')];
      add(qs[i], 'user');
      submitFollowup(qs[i]);
    }
    async function submitFollowup(q) {
      add(TT('answering'), 'bot');
      try {
        const ctx = Object.assign({}, lastResult || {}, {lang: LANG});
        const r = await fetch('/api/analysis/followup-question', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({question:q, context:ctx})});
        const d = await r.json();
        if (d.ok) add(d.answer, 'bot'); else add(TT('err') + (d.error||'?'), 'bot');
      } catch(e) { add(TT('conn_err'), 'bot'); }
      showOpts([
        {label:TT('another_q'), fn:askFollowup},
        {label:TT('new'), fn:restart}
      ]);
    }
