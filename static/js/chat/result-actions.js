/* SymptoSense chat — Result actions: read aloud, feedback, nearby hospitals, restart.
   Classic script: shares the page's global scope with the other files in /static/js/chat/. Load order is fixed by chat_view.py. */
    function speakResult() {
      if (!lastResult) return;
      if (!('speechSynthesis' in window)) { add(TT('no_speech'), 'bot'); return; }
      const clean = s => String(s || '').replace(/\s{2,}/g, ' ').trim();
      const d = lastResult;
      const u = d.urgency;
      const pill = u==='high' ? TT('urg_high') : (u==='medium' ? TT('urg_medium') : TT('urg_low'));
      let parts = [];
      parts.push(TT('urg_label') + ' ' + clean(pill) + '.');
      if (d.personal_note) parts.push(TT('assessment_label') + ' ' + clean(d.personal_note));
      if (d.possible_conditions) parts.push(TT('sp_possible') + clean(d.possible_conditions));
      if (d.recommendations && d.recommendations.length) {
        parts.push(TT('sp_recs'));
        d.recommendations.forEach(r => {
          const t = ((r.title ? r.title + ': ' : '') + (r.tip || ''));
          if (t) parts.push('- ' + clean(t));
        });
      }
      if (d.med_warnings && d.med_warnings.length) {
        parts.push(TT('sp_medwarn'));
        d.med_warnings.forEach(m => { const w = NAME(m, 'warning_ar', 'warning_en'); if (w) parts.push('- ' + clean(w)); });
      }
      if (d.danger_signs) parts.push(TT('sp_danger') + clean(d.danger_signs));
      if (d.when_to_seek_care) parts.push(TT('sp_when') + clean(d.when_to_seek_care));
      if (d.home_care) parts.push(TT('sp_home') + clean(d.home_care));
      if (d.medication_guidance) parts.push(TT('sp_medguid') + clean(d.medication_guidance));
      if (d.questions_for_doctor) parts.push(TT('sp_qdoc') + clean(d.questions_for_doctor));
      speakText(parts.join(' '));
    }
    let selectedFeedbackStar = 0;
    let selectedFeedbackReason = '';
    function selectFeedbackStar(rating) {
      selectedFeedbackStar = Number(rating) || 0;
      document.querySelectorAll('.ss-star-btn').forEach(function(btn){const on=Number(btn.dataset.star)<=selectedFeedbackStar;btn.textContent=on?'★':'☆';btn.classList.toggle('on',on);});
      const submit=document.getElementById('fbSubmit'); if(submit) submit.disabled=!selectedFeedbackStar;
    }
    function selectFeedbackReason(reason){
      selectedFeedbackReason=String(reason||'');
      document.querySelectorAll('.ss-feedback-reason').forEach(function(btn){btn.classList.toggle('on',btn.dataset.reason===selectedFeedbackReason);});
    }
    async function submitFeedback() {
      if(!selectedFeedbackStar)return;
      const btn=document.getElementById('fbSubmit'),msg=document.getElementById('fbMsg');
      const comment=(document.getElementById('fbComment')||{}).value||'';
      const publicComment=!!((document.getElementById('fbPublic')||{}).checked);
      const recordId=(lastResult&&lastResult.record_id)?Number(lastResult.record_id):0;
      if(btn)btn.disabled=true;if(msg)msg.textContent=LANG==='ar'?'جاري الإرسال…':'Sending…';
      try{const r=await fetch('/api/feedback',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','Accept':'application/json'},body:JSON.stringify({rating:selectedFeedbackStar,reason_code:selectedFeedbackReason||null,context:'analysis_result',record_id:recordId||null,comment:comment,public_comment:publicComment})});const d=await r.json();if(!r.ok||!d.ok)throw new Error(d.error||'feedback_failed');if(msg)msg.textContent=TT('fb_thanks');if(btn){btn.textContent=LANG==='ar'?'تم الإرسال ✓':'Submitted ✓';btn.disabled=true;}}catch(e){if(msg)msg.textContent=LANG==='ar'?'تعذر إرسال التقييم الآن.':'Unable to submit feedback right now.';if(btn)btn.disabled=false;}
    }
    async function findHospitals() {
      clearOpts();
      add(TT('locating'), 'bot');
      const mapsFallback = 'https://www.google.com/maps/search/hospitals+near+me';
      if (!window.isSecureContext || !navigator.geolocation) {
        addHtml(esc(G(TT('loc_err_f'), TT('loc_err_m'))) + '<br><a class="btn ghost small" href="'+mapsFallback+'" target="_blank" rel="noopener noreferrer">'+esc(TT('map'))+'</a>', 'bot');
        return;
      }
      navigator.geolocation.getCurrentPosition(async pos => {
        try {
          const r = await fetch('/api/hospitals', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({lat:pos.coords.latitude,lng:pos.coords.longitude})});
          const d = await r.json();
          if (!d.ok || !d.hospitals || !d.hospitals.length) throw new Error('no_hospitals');
          let h = '<div class="sec-title">' + TT('hosp_title') + '</div>';
          d.hospitals.forEach(function(x){
            const dist = (x.distance_km===null || x.distance_km===undefined || x.distance_km==='') ? '' : (' — ' + esc(x.distance_km) + TT('km'));
            h += '<div class="rec-item"><b>' + esc(x.name) + '</b>' + dist + '<br><a href="' + escAttr(safeLink(x.maps_url)) + '" target="_blank" rel="noopener noreferrer">' + TT('map') + '</a></div>';
          });
          addHtml(h,'result');
        } catch(e) { addHtml(esc(TT('no_hosp'))+'<br><a class="btn ghost small" href="'+mapsFallback+'" target="_blank" rel="noopener noreferrer">'+esc(TT('map'))+'</a>','bot'); }
      }, function(err) {
        const reason = err && err.code===1 ? (LANG==='ar'?'لم يتم السماح بالوصول للموقع. فعّل إذن الموقع من إعدادات Safari ثم حاول مرة أخرى.':'Location permission is off. Enable it in Safari settings and try again.') : G(TT('loc_err_f'), TT('loc_err_m'));
        addHtml(esc(reason)+'<br><a class="btn ghost small" href="'+mapsFallback+'" target="_blank" rel="noopener noreferrer">'+esc(TT('map'))+'</a>','bot');
      }, {enableHighAccuracy:false, timeout:20000, maximumAge:300000});
    }
    function restart() {
      draftClear();
      Object.assign(state, {age:null,gender:null,symptoms:[],duration:null,severity:null,location:null,conditions:null,medications:null,allergies:null,notes:null,onset:null,course:null,raw_description:'',extracted_context:null,pattern_worse:null,pattern_relief:null,pattern_context_done:false,history_answered:false,previous_record_id:null,smart_prompt_shown:false,demo_mode:false,quick_mode:false,status_update:null,body_regions:[],body_region_primary:null,body_zone_primary:null,body_region_needs_symptom:null,body_region_custom_symptoms:{}}); symptomInputMethod='describe'; symptomOptionsExpanded=false; closeBodyMapSheet(); document.body.classList.remove('ss-quick-assessment'); if(new URLSearchParams(location.search).get('demo')==='1'){history.replaceState(null,'','/chat');} compareBase=null; qualityReturnKey=null; lastDataQuality=null; selectedBloodId=null; bloodChoiceMade=false; latestBloodCandidate=null; lastAnalysisInput=null; lastUserAnswerText=''; currentStepQuestionText=''; answerHistory.length=0; highestFlowStep=1;
      earlySafetyChecked=false; earlySafetyRunning=false;
      bodyEl.textContent = '';
      bodyEl.classList.remove('result-mode');
      bodyEl.scrollTop = 0;
      optsEl.hidden = false;
      const wrap = bodyEl.closest('.chat-wrap'); if (wrap) wrap.classList.remove('report-mode');
      const safetyNote = document.getElementById('chatSafetyNote'); if (safetyNote) safetyNote.style.visibility = 'visible';
      startChat();
    }
