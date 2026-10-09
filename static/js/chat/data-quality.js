/* SymptoSense chat — Data-quality gate and blood-test context choice before the analysis runs.
   Classic script: shares the page's global scope with the other files in /static/js/chat/. Load order is fixed by chat_view.py. */
    let lastDataQuality = null;
    let qualityReturnKey = null;
    let selectedBloodId = null;
    let bloodChoiceMade = false;
    let latestBloodCandidate = null;
    function dataQualityPayload(){
      return {lang:LANG,age:state.age,gender:state.gender,symptoms:(state.symptoms||[]),duration:state.duration,severity:state.severity,conditions:state.conditions||'',medications:state.medications||'',allergies:state.allergies||'',notes:[state.notes||'',symptomPathContextNote()].filter(Boolean).join(' '),location:state.location||'',history_answered:!!state.history_answered,body_regions:(state.body_regions||[]),body_region_primary:state.body_region_primary||null,body_zone_primary:state.body_zone_primary||null};
    }
    function dataQualityHtml(q, compact){
      if(!q) return '';
      const pct=Math.max(0,Math.min(100,parseInt(q.score||0)));
      const levelIcon=q.user_state==='sufficient'?'🟢':(q.user_state==='improvable'?'🟡':'🟠');
      let h='<div class="data-quality-card"><div class="dq-head"><div><b>📊 '+esc(LANG==='ar'?'جودة المعلومات قبل التحليل':'Input quality before analysis')+'</b><div class="muted" style="margin-top:3px">'+esc(q.meaning||'')+'</div></div><div style="text-align:center"><div class="dq-score">'+pct+'%</div><div class="dq-level">'+levelIcon+' '+esc(q.user_state_label||q.level_label||'')+'</div></div></div><div class="dq-track"><div class="dq-fill" style="width:'+pct+'%"></div></div>';
      if(!compact){
        h+='<div class="dq-grid">'+(q.fields||[]).map(function(f){const icon=f.status==='provided'?'✅':(f.status==='needs_clarification'?'⚠️':'⚠️');const cls=f.status==='provided'?'':(f.status==='needs_clarification'?' clarify':' missing');const detail=(f.status!=='provided'&&f.detail)?'<div class="dq-item-detail">'+esc(f.detail)+'</div>':'';const suggestions=(f.suggestions&&f.suggestions.length)?('<div class="dq-suggest">'+esc(LANG==='ar'?'ربما تقصد: ':'Did you mean: ')+f.suggestions.map(function(s){return '<button type="button" class="dq-chip" data-dq-suggestion="'+escAttr(s.label)+'">'+esc(s.label)+'</button>';}).join('')+'</div>'):'';return '<div class="dq-item'+cls+'">'+icon+' <b>'+esc(f.label)+'</b><div class="muted">'+esc(f.status==='provided'?(LANG==='ar'?'مكتمل':'Complete'):(f.required?(LANG==='ar'?'مطلوب':'Required'):(LANG==='ar'?'موصى به':'Recommended')))+'</div>'+detail+suggestions+'</div>';}).join('')+'</div>';
      }
      const clarifySym=(q.fields||[]).find(function(f){return f.key==='main_symptom' && f.status==='needs_clarification';});
      const safeNote=(q.sufficient && clarifySym) ? '<div class="dq-safe-note">✅ '+esc(LANG==='ar'?'يمكن إجراء تحليل آمن، لكن العرض يحتاج توضيحًا.':'A safe analysis can be run, but the symptom needs clearer wording.')+'</div>' : '';
      h+='<div class="dq-meta"><span>'+esc(LANG==='ar'?'المطلوب مكتمل: ':'Required complete: ')+esc(String(q.required_completion||0))+'%</span><span>'+esc(LANG==='ar'?'السياق الموصى به: ':'Recommended context: ')+esc(String(q.recommended_completion||0))+'%</span></div>'+safeNote+'</div>';
      return h;
    }
    async function fetchDataQuality(){
      const r=await fetch('/api/analyze/data-quality',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(dataQualityPayload())});
      const d=await r.json();
      if(d.consent_required){location.href=d.consent_url||'/consent?next=/chat';throw new Error('consent_required');}
      if(!r.ok||!d.ok) throw new Error(d.error||'quality_failed');
      lastDataQuality=d.data_quality; return d.data_quality;
    }
    function applySymptomSuggestion(label){
      state.symptoms = Array.from(new Set((state.symptoms||[]).concat([label])));
      add((LANG==='ar'?'تمت إضافة: ':'Added: ')+label,'user');
      showDataQualityGate();
    }
    async function loadBloodCandidate(){
      if(state.demo_mode) return null;
      if(!document.body.dataset.loggedIn) return null;
      let preferred=null;
      try { preferred=parseInt(localStorage.getItem('symptosense_blood_id')||'0',10)||null; } catch(e) {}
      try {
        const r=await fetch('/api/blood/history',{headers:{'Accept':'application/json'}});
        if(!r.ok) return null;
        const d=await r.json();
        const tests=(d&&d.ok&&Array.isArray(d.tests))?d.tests:[];
        if(!tests.length) return null;
        return tests.find(function(x){return Number(x.id)===Number(preferred);}) || tests[0];
      }catch(e){ return null; }
    }
    async function chooseBloodContextThenAnalyze(){
      if(bloodChoiceMade){ runAnalysis(); return; }
      latestBloodCandidate=latestBloodCandidate||await loadBloodCandidate();
      if(!latestBloodCandidate){ bloodChoiceMade=true; selectedBloodId=null; runAnalysis(); return; }
      clearOpts();
      const stamp=String(latestBloodCandidate.timestamp||'').slice(0,10);
      const summary=String(latestBloodCandidate.summary||'').trim();
      add((LANG==='ar'?'لديك تحليل دم محفوظ'+(stamp?' بتاريخ '+stamp:'')+'. هل تريد استخدامه كسياق إضافي لهذا التحليل؟ لن يُستخدم تلقائيًا، ولن يغيّر قواعد الطوارئ أو ترتيب الاحتمالات.':'You have a saved blood test'+(stamp?' dated '+stamp:'')+'. Use it as additional context for this assessment? It will not be used automatically and will not change emergency rules or condition ranking.')+(summary?'\n'+summary:''),'bot');
      showOpts([
        {label:'🧪 '+(LANG==='ar'?'استخدام تحليل الدم':'Use blood test'),fn:function(){selectedBloodId=Number(latestBloodCandidate.id)||null;bloodChoiceMade=true;add(LANG==='ar'?'استخدم تحليل الدم كسياق إضافي':'Use the blood test as additional context','user');runAnalysis();}},
        {label:'➡️ '+(LANG==='ar'?'المتابعة بدونه':'Continue without it'),fn:function(){selectedBloodId=null;bloodChoiceMade=true;add(LANG==='ar'?'تابع بدون تحليل الدم':'Continue without the blood test','user');runAnalysis();}}
      ]);
    }
    async function showDataQualityGate(){
      clearOpts(); hideText();
      add(LANG==='ar'?'أراجع اكتمال المعلومات قبل التحليل…':'Checking information completeness before analysis…','bot');
      try{
        const q=await fetchDataQuality();
        addHtml(dataQualityHtml(q,false),'bot');
        const missing=(q.missing||[]);
        if(!q.sufficient){
          const symField=(q.fields||[]).find(function(f){return f.key==='main_symptom' && f.status!=='provided';});
          const specific=symField && symField.detail ? symField.detail : (LANG==='ar'?'أكمل المعلومات المطلوبة أولًا.':'Please complete the required information first.');
          add(specific+' '+(LANG==='ar'?'إذا ظهرت علامة خطر، ستظل طبقة الأمان لها الأولوية. وإذا تعذر إكمال المعلومات، فالأفضل اختيار تقييم بشري بدل افتراض أنها طوارئ حرجة.':'If a red flag appears, the safety layer still takes priority. If you cannot complete the information, choose human review rather than assuming a critical emergency.'),'bot');
          showOpts([
            {label:'➕ '+(LANG==='ar'?'تحسين معلوماتي':'Improve My Information'),fn:function(){improveDataQuality(q);}},
            {label:'☎️ '+(LANG==='ar'?'استشارة بشرية · 937':'Human advice · 937'),fn:function(){
              add(LANG==='ar'?'أفضّل تقييمًا بشريًا':'I prefer human review','user');
              add(LANG==='ar'?'يمكنك التواصل مع مركز 937 للحصول على توجيه صحي بشري. إذا ساءت الحالة أو ظهرت علامة خطر واضحة، استخدم خدمات الطوارئ فورًا.':'You can contact 937 for human health guidance. If the condition worsens or a clear red flag appears, use emergency services immediately.','bot');
              try{ window.location.href='tel:937'; }catch(e){}
            }}
          ]);
          return;
        }
        const opts=[{label:'🩺 '+(LANG==='ar'?'تحليل الأعراض':'Analyze symptoms'),fn:function(){chooseBloodContextThenAnalyze();}}];
        if(missing.length) opts.push({label:'➕ '+(LANG==='ar'?'تحسين معلوماتي':'Improve My Information'),fn:function(){improveDataQuality(q);}});
        showOpts(opts);
      }catch(e){
        if(String(e.message)!=='consent_required'){
          add(LANG==='ar'?'تعذر فحص اكتمال المعلومات الآن؛ سأتابع التحليل بالمعلومات المتاحة.':'The completeness check is unavailable; I’ll continue with the information available.','bot');
          updateFlow('review');
          setTimeout(chooseBloodContextThenAnalyze, 120);
        }
      }
    }
    function improveDataQuality(q){
      clearOpts();
      const missing=(q&&q.missing)||[];
      const required=missing.find(x=>x.required)||missing[0];
      if(!required){showDataQualityGate();return;}
      const key=required.key; qualityReturnKey=key;
      add((LANG==='ar'?'سنضيف: ':'Let’s add: ')+required.label,'bot');
      if(key==='age'){state.age=null;askAge();return;}
      if(key==='gender'){state.gender=null;askGender();return;}
      if(key==='main_symptom'||key==='associated_symptoms'){askSymptoms();return;}
      if(key==='duration'){state.duration=null;askDuration();return;}
      if(key==='severity'){state.severity=null;askSeverity();return;}
      if(key==='relevant_history'){state.history_answered=false;state.conditions=null;askConditions();return;}
      askSymptoms();
    }
