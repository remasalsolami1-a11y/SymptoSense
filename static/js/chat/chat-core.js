/* SymptoSense chat — State, DOM handles, message rendering, drafts, family members and startChat.
   Classic script: shares the page's global scope with the other files in /static/js/chat/. Load order is fixed by chat_view.py. */
    function TT(k) { return T[k] || k; }
    const state = { age:null, gender:null, symptoms:[], duration:null, severity:null, location:null, conditions:null, medications:null, allergies:null, notes:null, onset:null, course:null, raw_description:'', extracted_context:null, pattern_worse:null, pattern_relief:null, pattern_context_done:false, redflag_yes:[], history_answered:false, step:'age', member_id:0, member_name:TT('me'), smart_prompt_shown:false, previous_record_id:null, demo_mode:false, quick_mode:false, status_update:null, body_regions:[], body_region_primary:null, body_zone_primary:null, body_region_needs_symptom:null, body_region_custom_symptoms:{} };
    const requestedMemberId = (function(){
      try { return parseInt(new URLSearchParams(window.location.search).get('m') || '0', 10) || 0; }
      catch(e) { return 0; }
    })();
    let requestedMemberConsumed = false;
    function memberAgeLabel(raw) {
      const v = String(raw || '').trim();
      if (!v) return '';
      return /^\d{4}-\d{2}-\d{2}$/.test(v) ? v : (v + ' ' + TT('yrs'));
    }
    // Result rendering also uses this profile context. Keep it in the shared
    // chat-script scope instead of declaring it only inside runAnalysis().
    let useSaved = false;
    let profileMissing = [];
    let userInfo = null;
    // "Still analyzing..." notice timer. Shared on purpose: showEmergency() (red-flags.js) cancels it so the notice cannot
    // appear on top of an emergency screen.
    let progressTimer = null;
    let compareBase = null;
    let lastAnalysisInput = null;
    let adaptiveQuestionNo = 0;
    const bodyEl = document.getElementById('chatBody');
    const optsEl = document.getElementById('chatOptions');
    const inpEl = document.getElementById('chatInput');
    const textInp = document.getElementById('textInp');
    const famSelect = document.getElementById('famSelect');
    const sendBtn = document.getElementById('chatSendBtn');
    let highestFlowStep = 1;
    function updateFlow(step) {
      const quick=!!state.quick_mode;
      var map = quick
        ? {member:1,age:1,gender:1,symptoms:2,duration:3,severity:4,clarification:4,review:4,followup:4}
        : {member:1,age:1,gender:1,symptoms:2,duration:3,severity:4,symptom_path:5,symptom_path_worse_custom:5,symptom_path_relief_custom:5,notes:5,conditions:6,medications:6,allergies:6,clarification:6,review:7,followup:7};
      const total=quick?4:7;
      var number = Math.min(total, Math.max(highestFlowStep, map[step] || 1));
      highestFlowStep = number;
      var names = quick
        ? (LANG === 'ar' ? ['المعلومات الأساسية','الأعراض','المدة','فحص الأمان والنتيجة'] : ['Basics','Symptoms','Duration','Safety check & result'])
        : (LANG === 'ar' ? ['العمر والجنس','الأعراض','مدة الأعراض','شدة الأعراض','الأعراض المصاحبة','التاريخ الصحي والأدوية والحساسيات','النتيجة'] : ['Age and sex','Symptoms','Symptom duration','Symptom severity','Associated symptoms','History, medicines and allergies','Result']);
      document.getElementById('flowStepLabel').textContent = (LANG === 'ar' ? 'الخطوة ' : 'Step ') + number + (LANG === 'ar' ? ' من ' : ' of ') + total;
      document.getElementById('flowStepName').textContent = names[Math.max(0,number - 1)] + (quick ? (LANG==='ar'?' · مسار سريع':' · Quick mode') : '');
      document.getElementById('flowFill').style.width = ((number / total) * 100) + '%';
      var bar = document.getElementById('flowProgress'); if (bar) { bar.setAttribute('aria-label', LANG==='ar'?'تقدم التحليل':'Assessment progress'); bar.setAttribute('aria-valuenow', String(number)); bar.setAttribute('aria-valuemax', String(total)); }
      document.body.setAttribute('data-chat-step', step || '');
      document.body.classList.toggle('ss-quick-assessment', quick);
    }
    // Audio controls are synchronized after all audio state variables are
    // initialized. Calling them here would access `let` bindings before
    // initialization and stop the entire chat script on Safari/Chrome.
    // Load family members only after /api/user-info confirms the user is signed in.
    // This prevents expected guest sessions from generating 401 responses in the console.
    function loadFamilyMembers() {
      if (!(userInfo && userInfo.ok && userInfo.logged_in)) {
        return Promise.resolve({ok:true, members:[]});
      }
      return fetch('/api/family').then(function(r){
        if (r.status === 401) return {ok:true, members:[]};
        return r.json();
      }).then(function(d){
        const members = (d && d.ok && Array.isArray(d.members)) ? d.members : [];
        while (famSelect.options.length > 1) famSelect.remove(1);
        if (members.length) {
          const emojis = {'me':'👤','mother':'👩','father':'👨','daughter':'👧','son':'👦','grandparent':'👵','other':'🧑'};
          members.forEach(function(m) {
            const opt = document.createElement('option');
            opt.value = m.id;
            const em = emojis[m.relation] || '🧑';
            opt.textContent = em + ' ' + m.name;
            famSelect.appendChild(opt);
          });
        }
        return {ok:true, members:members};
      }).catch(function(){ return {ok:false, members:[]}; });
    }
    function switchFamilyMember(val) {
      const id = parseInt(val, 10) || 0;
      state.member_id = id;
      const m = (MEMBERS || []).find(function(x){ return Number(x.id) === id; }) || null;
      state.member = m ? {id:m.id, name:m.name, age:m.age, gender:m.gender, conditions:m.conditions, medications:m.medications, allergies:m.allergies} : null;
      state.member_name = m ? m.name : TT('me');
      state.age = m && m.age ? m.age : null;
      state.gender = m && m.gender ? m.gender : null;
      if (m) {
        if (!state.conditions && m.conditions) state.conditions = m.conditions;
        if (!state.medications && m.medications) state.medications = m.medications;
        if (!state.allergies && m.allergies) state.allergies = m.allergies;
      }
    }
    let lastUserAnswerText = '';
    let currentStepQuestionText = '';
    const answerHistory = [];
    function add(msg, cls) {
      if (cls === 'user') {
        lastUserAnswerText = String(msg || '').trim();
        if (currentStepQuestionText && lastUserAnswerText) {
          answerHistory.push({q: currentStepQuestionText, a: lastUserAnswerText});
          if (answerHistory.length > 12) answerHistory.shift();
        }
      }
      const d = document.createElement('div');
      d.className = 'bubble ' + cls;
      d.textContent = msg;
      bodyEl.appendChild(d);
      bodyEl.scrollTop = bodyEl.scrollHeight;
      if (cls === 'bot' && autoSpeak && msg !== lastSpokenMsg) {
        lastSpokenMsg = msg;
        speakText(msg);
      }
      return d;
    }
    function addHtml(html, cls) {
      const d = document.createElement('div');
      d.className = 'bubble ' + cls;
      d.innerHTML = html;
      bodyEl.appendChild(d);
      bodyEl.scrollTop = bodyEl.scrollHeight;
      const wrapEl1 = bodyEl.closest('.chat-wrap');
      if (wrapEl1) wrapEl1.scrollTop = wrapEl1.scrollHeight;
      d.scrollIntoView({ block: 'end' });
      return d;
    }
    function addQ(msg) {
      const d = document.createElement('div');
      d.className = 'bubble q';
      d.textContent = msg;
      bodyEl.appendChild(d);
      bodyEl.scrollTop = bodyEl.scrollHeight;
      const wrapEl2 = bodyEl.closest('.chat-wrap');
      if (wrapEl2) wrapEl2.scrollTop = wrapEl2.scrollHeight;
      d.scrollIntoView({ block: 'end' });
      if (autoSpeak && msg !== lastSpokenMsg) { lastSpokenMsg = msg; speakText(msg); }
      return d;
    }
    function focusStepQuestion(msg, answerOverride) {
      if (bodyEl.classList.contains('result-mode')) return addQ(msg);
      // Every new questionnaire step starts with a clean input state.
      // This prevents an old placeholder (for example allergies/medications)
      // from remaining visible during adaptive yes/no questions.
      hideText();
      currentStepQuestionText = String(msg || '').trim();
      bodyEl.textContent = '';
      const card = document.createElement('section');
      card.className = 'step-focus-card';
      const kicker = document.createElement('div');
      kicker.className = 'step-focus-kicker';
      kicker.textContent = LANG === 'ar' ? 'السؤال الحالي' : 'Current question';
      const q = document.createElement('div');
      q.className = 'step-focus-question';
      q.textContent = msg;
      card.appendChild(kicker);
      card.appendChild(q);
      const answer = answerOverride === undefined ? lastUserAnswerText : String(answerOverride || '').trim();
      if (answer) {
        const a = document.createElement('div');
        a.className = 'step-focus-answer';
        const b = document.createElement('b');
        b.textContent = LANG === 'ar' ? 'إجابتك السابقة: ' : 'Previous answer: ';
        a.appendChild(b);
        a.appendChild(document.createTextNode(answer));
        card.appendChild(a);
      }
      bodyEl.appendChild(card);
      if (answerHistory.length) {
        const details = document.createElement('details');
        details.className = 'step-answer-summary';
        const summary = document.createElement('summary');
        summary.textContent = LANG === 'ar' ? 'ملخص إجاباتك (' + answerHistory.length + ')' : 'Your answer summary (' + answerHistory.length + ')';
        details.appendChild(summary);
        const list = document.createElement('div');
        list.className = 'step-answer-summary-list';
        answerHistory.slice(-8).forEach(function(item){
          const row = document.createElement('div');
          row.className = 'step-answer-summary-row';
          const qq = document.createElement('b'); qq.textContent = item.q;
          const aa = document.createElement('span'); aa.textContent = item.a;
          row.appendChild(qq); row.appendChild(aa); list.appendChild(row);
        });
        details.appendChild(list); bodyEl.appendChild(details);
      }
      // Keep each new step aligned inside the questionnaire itself.
      // Avoid scrollIntoView here: on iPhone Safari it can move the whole page
      // and tuck the question underneath the blue header.
      const wrapEl = bodyEl.closest('.chat-wrap');
      requestAnimationFrame(function(){
        if (!wrapEl) return;
        const container = wrapEl.closest('.container');
        bodyEl.scrollTop = 0;
        wrapEl.scrollTop = 0;
        if (container) container.scrollTop = 0;
      });
      if (autoSpeak && msg !== lastSpokenMsg) { lastSpokenMsg = msg; speakText(msg); }
      return card;
    }
    function clearOpts() { stopSymptomTextMic(document.getElementById('smartTextMicBtn'), true); optsEl.textContent = ''; optsEl.classList.remove('symptom-picker'); }
    function showOpts(items) {
      clearOpts();
      items.forEach(it => {
        const b = document.createElement('button');
        b.className = 'opt' + (it.sel ? ' sel' : '') + (it.cls ? ' ' + it.cls : '');
        b.textContent = it.label;
        b.onclick = it.fn;
        optsEl.appendChild(b);
      });
    }
    function showText(placeholder, keepOpts) {
      if (!keepOpts) clearOpts();
      inpEl.style.display = 'flex';
      textInp.placeholder = placeholder;
      textInp.value = '';
      const ageMode = state.step === 'age';
      textInp.inputMode = ageMode ? 'numeric' : 'text';
      textInp.setAttribute('dir', ageMode ? 'ltr' : (LANG === 'ar' ? 'rtl' : 'ltr'));
      if (ageMode) {
        textInp.setAttribute('pattern','[0-9٠-٩۰-۹]*');
        textInp.setAttribute('maxlength','3');
        textInp.setAttribute('aria-label', LANG === 'ar' ? 'العمر بالسنوات من 1 إلى 120' : 'Age in years from 1 to 120');
        textInp.setAttribute('autocomplete','off');
      } else {
        textInp.removeAttribute('pattern');
        textInp.removeAttribute('maxlength');
        textInp.removeAttribute('aria-label');
        textInp.removeAttribute('autocomplete');
      }
      if (window.matchMedia('(hover:hover) and (pointer:fine)').matches) {
        try { textInp.focus({ preventScroll: true }); }
        catch (e) { /* Avoid legacy focus fallback because it can jump the analysis page. */ }
      }
    }
    function hideText() { inpEl.style.display = 'none'; }
    function send() {
      const v = textInp.value.trim();
      if (!v) return;
      hideText();
      add(v, 'user');
      textInp.value = '';
      return v;
    }
    // Unfinished-assessment draft: core answers only, this device only, expires after 24h.
    const DRAFT_KEY='ss_chat_draft_v1';
    function draftClear(){ try{ localStorage.removeItem(DRAFT_KEY); }catch(e){} }
    function draftSave(){
      try{
        if(state.demo_mode||state.previous_record_id||lastResult) return;
        if(!(state.age||(state.symptoms&&state.symptoms.length))) return;
        localStorage.setItem(DRAFT_KEY,JSON.stringify({t:Date.now(),lang:LANG,s:{age:state.age,gender:state.gender,symptoms:state.symptoms,duration:state.duration,severity:state.severity,quick_mode:!!state.quick_mode,member_id:state.member_id,member_name:state.member_name}}));
      }catch(e){}
    }
    function draftLoad(){
      try{
        const d=JSON.parse(localStorage.getItem(DRAFT_KEY)||'null');
        if(!d||!d.s||d.lang!==LANG||Date.now()-Number(d.t||0)>24*3600*1000){ if(d) draftClear(); return null; }
        return d;
      }catch(e){ return null; }
    }
    function offerDraftResume(draft,otherwise){
      const syms=(draft.s.symptoms||[]).join(LANG==='ar'?'، ':', ');
      add((LANG==='ar'?'عندك تحليل غير مكتمل'+(syms?' عن '+syms:'')+'. الإجابات محفوظة على جهازك فقط. تبي تكمل من حيث توقفت؟':'You have an unfinished assessment'+(syms?' about '+syms:'')+'. Your answers are saved on this device only. Continue where you left off?'),'bot');
      showOpts([
        {label:'↩️ '+(LANG==='ar'?'أكمل من حيث توقفت':'Continue where I left off'),fn:function(){
          clearOpts(); Object.assign(state,draft.s); highestFlowStep=1;
          if(!state.age) askAge(); else if(!state.gender) askGender(); else if(!(state.symptoms&&state.symptoms.length)) askSymptoms();
          else if(!state.duration) askDuration(); else if(!state.severity) askSeverity();
          else if(state.quick_mode) startClarify(); else askSymptomPath();
        }},
        {label:'🆕 '+(LANG==='ar'?'ابدأ من جديد':'Start over'),fn:function(){ clearOpts(); draftClear(); otherwise(); }}
      ]);
    }
    function startChat() {
      addHtml('<div class="chat-start"><div class="cs-logo">🩺</div><div class="cs-title">' + esc(TT('welcome')) + '</div><div class="cs-sub">' + esc(TT('start_sub')) + '</div><div class="cs-desc">' + esc(TT('start_desc')) + '</div></div>', 'q start');
      const params = new URLSearchParams(location.search);
      const demoMode = params.get('demo') === '1';
      if (demoMode) {
        state.demo_mode = true;
        state.age = 24;
        state.gender = 'f';
        state.symptoms = LANG === 'ar' ? ['🤕 صداع','🤢 غثيان'] : ['🤕 Headache','🤢 Nausea'];
        state.duration = LANG === 'ar' ? '📅 1-3 أيام' : '📅 1-3 days';
        state.severity = 2;
        state.conditions = LANG === 'ar' ? 'لا يوجد أمراض سابقة' : 'No previous conditions';
        state.history_answered = true;
        state.smart_prompt_shown = true;
        addHtml('<div class="ss-demo-flow-note"><b>⚡ '+esc(LANG==='ar'?'وضع التجربة السريعة':'Quick demo mode')+'</b><br>'+esc(LANG==='ar'?'تم تعبئة بيانات افتراضية للتجربة فقط. لن تُحفظ هذه النتيجة في سجلك الصحي أو ترتبط بملفك أو فحوصاتك.':'Fictional demo data is prefilled for this walkthrough. This result will not be saved to your health history or linked to your profile or tests.')+'</div>','bot');
        showOpts([
          {label:'⚡ '+(LANG==='ar'?'تشغيل المثال الآن':'Run demo assessment'), fn:function(){ runAnalysis(); }},
          {label:'✏️ '+(LANG==='ar'?'تعديل الأعراض أولًا':'Edit symptoms first'), fn:function(){ askSymptoms(); }}
        ]);
        return;
      }
      const reId = parseInt(params.get('reanalyze') || '0');
      if (reId) {
        fetch('/api/analysis/'+reId,{credentials:'same-origin',cache:'no-store'}).then(r=>r.json()).then(function(d){
          if (!d.ok || !d.analysis) throw new Error('not_found');
          const a=d.analysis, snap=(a.result&&a.result.input_snapshot)||{};
          const base={
            age:a.age??snap.age??null, gender:a.gender||snap.gender||null,
            symptoms:(a.symptoms&&a.symptoms.length?a.symptoms:(snap.symptoms||[])).slice(),
            duration:a.duration||snap.duration||null, severity:a.severity??snap.severity??null,
            conditions:a.conditions||snap.conditions||'', medications:a.medications||snap.medications||'',
            allergies:a.allergies||snap.allergies||'', notes:a.notes||snap.notes||(a.result||{}).notes||''
          };
          compareBase={record_id:a.id,symptoms:(base.symptoms||[]).slice(),duration:base.duration,severity:base.severity,urgency:a.urgency};
          state.previous_record_id=a.id; state.age=base.age; state.gender=base.gender; state.symptoms=(base.symptoms||[]).slice(); state.duration=base.duration; state.severity=base.severity;
          state.conditions=base.conditions; state.medications=base.medications; state.allergies=base.allergies; state.notes=base.notes; state.smart_prompt_shown=true;
          lastAnalysisInput=cloneAnalysisInput(Object.assign({},base,{lang:LANG}));
          add(LANG==='ar'?'تم تحميل إجابات التحليل السابق. يمكنك تعديل أي خانة مباشرة.':'Previous answers loaded. You can edit any field directly.','bot');
          renderAnswerEditor(a.id,base);
        }).catch(function(){ add(LANG==='ar'?'تعذر تحميل التحليل السابق.':'Unable to load the previous analysis.','bot'); askMember(); });
        return;
      }
      const beginContextFlow=function(){
        try {
          fetch('/api/user-info').then(function(r){ return r.json(); }).then(function(ui){
            // Reuse this already-loaded account/profile context at result time so
            // clicking Analyze does not incur another sequential network request.
            userInfo = ui || null;
            window.__USER_INFO__ = ui || null;
            const continueNormalFlow=function(){
              if (ui.ok && ui.logged_in && ui.has_profile && ui.privacy && ui.privacy.use_in_analysis && ui.profile) {
                smartCtxShow(ui.profile, function(action){
                  if (action === 'use') {
                    if (ui.profile.age) state.age = ui.profile.age;
                    if (ui.profile.gender === 'male' || ui.profile.gender === 'm') state.gender = 'm';
                    else if (ui.profile.gender === 'female' || ui.profile.gender === 'f') state.gender = 'f';
                    add((LANG==='ar'?'تم استخدام معلومات الملف الشخصي ✅':'Profile info loaded ✅'), 'bot');
                  }
                  askMember();
                }, ui);
              } else {
                askMember();
              }
            };
            maybeOfferSmartFollowup(ui,continueNormalFlow);
          }).catch(function(){ askMember(); });
        } catch(e) { askMember(); }
      };
      const savedDraft=draftLoad();
      if(savedDraft) offerDraftResume(savedDraft,function(){ offerAssessmentMode(beginContextFlow); });
      else offerAssessmentMode(beginContextFlow);
    }
    let MEMBERS = [];
    function askMember() {
      state.step = 'member';
      updateFlow(state.step);
      if (!(userInfo && userInfo.ok && userInfo.logged_in)) {
        MEMBERS = [];
        state.member = null;
        askAge();
        return;
      }
      loadFamilyMembers().then(function(d) {
        MEMBERS = (d && d.members) || [];
        if (!MEMBERS.length) { state.member = null; state.member_id = 0; askAge(); return; }
        if (requestedMemberId && !requestedMemberConsumed) {
          requestedMemberConsumed = true;
          const requested = MEMBERS.find(function(m){ return Number(m.id) === requestedMemberId; });
          if (requested) {
            state.member = {id: requested.id, name: requested.name, age: requested.age, gender: requested.gender, conditions: requested.conditions, medications: requested.medications, allergies: requested.allergies};
            state.member_id = Number(requested.id) || 0;
            state.member_name = requested.name;
            famSelect.value = String(requested.id);
            if (requested.age) state.age = requested.age;
            if (requested.gender) state.gender = requested.gender;
            if (requested.conditions) state.conditions = requested.conditions;
            if (requested.medications) state.medications = requested.medications;
            if (requested.allergies) state.allergies = requested.allergies;
            add(requested.name + (requested.age ? ' — ' + memberAgeLabel(requested.age) : ''), 'user');
            askAge();
            return;
          }
        }
        const items = [{label: TT('me_short'), fn:()=>{ state.member = null; state.member_id = 0; state.member_name=TT('me'); famSelect.value='0'; add(TT('me_short'),'user'); askAge(); }}];
        MEMBERS.forEach(m => items.push({label: m.name + (m.age ? ' — ' + memberAgeLabel(m.age) : ''), fn:()=>{
          state.member = {id: m.id, name: m.name, age: m.age, gender: m.gender, conditions: m.conditions, medications: m.medications, allergies: m.allergies};
          state.member_id = Number(m.id) || 0;
          state.member_name = m.name;
          famSelect.value = String(m.id);
          if (m.age) state.age = m.age;
          if (m.gender) state.gender = m.gender;
          if (m.conditions) state.conditions = m.conditions;
          if (m.medications) state.medications = m.medications;
          if (m.allergies) state.allergies = m.allergies;
          add(m.name + (m.age ? ' — ' + memberAgeLabel(m.age) : ''), 'user');
          askAge();
        }}));
        focusStepQuestion('👥 ' + TT('for_whom'));
        hideText();
        showOpts(items);
      }).catch(function() { state.member = null; askAge(); });
    }
    function appendStartBtn() {
      const s = document.createElement('button');
      s.className = 'start-btn is-next';
      const regionNeedsSymptom = !!(state.body_region_needs_symptom && !hasSymptomForBodyRegion(state.body_region_needs_symptom));
      s.textContent = regionNeedsSymptom
        ? (LANG === 'ar' ? 'اختر عرضًا من ' + bodyRegionLabel(state.body_region_needs_symptom) + ' أولًا' : 'Choose a symptom from ' + bodyRegionLabel(state.body_region_needs_symptom) + ' first')
        : (state.symptoms.length ? (LANG === 'ar' ? 'التالي: مدة الأعراض' : 'Next: symptom duration') : (LANG === 'ar' ? 'اختر عرضًا ثم متابعة' : 'Choose a symptom to continue'));
      s.disabled = !state.symptoms.length || regionNeedsSymptom;
      s.setAttribute('aria-disabled', (!state.symptoms.length || regionNeedsSymptom) ? 'true' : 'false');
      s.onclick = beginAssessment;
      /* Keep the action after the symptom choices. On phones this avoids the
         confusing layout where Continue appeared above the symptoms. */
      optsEl.appendChild(s);
    }
    function beginAssessment() {
      if (!state.symptoms.length) { add(TT('atleast'), 'bot'); return; }
      if (state.body_region_needs_symptom && !hasSymptomForBodyRegion(state.body_region_needs_symptom)) {
        add(LANG==='ar'?'اختر عرضًا محددًا من '+bodyRegionLabel(state.body_region_needs_symptom)+' قبل المتابعة.':'Choose a specific symptom from '+bodyRegionLabel(state.body_region_needs_symptom)+' before continuing.','bot');
        if (compactSymptomUI()) {
          symptomInputMethod='body'; askSymptoms(); setTimeout(function(){ if(state.body_region_needs_symptom) showBodyRegion(state.body_region_needs_symptom, false); },0);
        } else { ensureBodyMapCard(); showBodyRegion(state.body_region_needs_symptom, false); }
        return;
      }
      state.body_region_needs_symptom = null;
      add(TT('chosen') + state.symptoms.join(LANG === 'en' ? ', ' : '، '), 'user');
      clearOpts();
      if (qualityReturnKey === 'main_symptom' || qualityReturnKey === 'associated_symptoms') { qualityReturnKey=null; showDataQualityGate(); return; }
      askDuration();
    }
