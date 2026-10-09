/* SymptoSense chat — Red-flag screens and the emergency overlay.
   Classic script: shares the page's global scope with the other files in /static/js/chat/. Load order is fixed by chat_view.py. */
    // Red-flag screens (V252): up to 4 yes/no warning-sign questions chosen from the entered symptoms,
    // asked before the differential questions. Fails open: if the request is slow the flow continues.
    let redflagAsked = [];
    async function startRedflagScreens() {
      if (redflagAsked.length >= 4) { startDifferentialQuestions(); return; }
      clearOpts();
      const controller = new AbortController();
      const timer = setTimeout(function(){ controller.abort(); }, 3500);
      let d = null;
      try {
        const r = await fetch('/api/analyze/redflag-next', {
          method:'POST', headers:{'Content-Type':'application/json'}, signal:controller.signal,
          body:JSON.stringify({symptoms:state.symptoms, asked:redflagAsked, age:state.age, lang:LANG})
        });
        d = await r.json();
        if (d && d.consent_required) { location.href=d.consent_url||'/consent?next=/chat'; return; }
      } catch(e) { d = null; } finally { clearTimeout(timer); }
      if (!d || !d.ok || d.done || !d.screen) { startDifferentialQuestions(); return; }
      const sc = d.screen;
      redflagAsked.push(sc.id);
      state.step = 'clarification';
      addHtml('<div class="adaptive-step">'+esc((LANG==='ar'?'فحص علامات الخطر · ':'Warning-sign check · ')+sc.number+(LANG==='ar'?' من ':' of ')+sc.max)+'</div>','bot');
      addHtml('<div class="muted" style="font-size:11.5px;line-height:1.65;margin-top:-4px">'+esc(sc.reason)+'</div>','bot');
      focusStepQuestion('⚠️ ' + sc.question);
      showOpts([
        {label:TT('clar_yes'), fn:function(){
          add(TT('clar_yes'),'user');
          if (state.redflag_yes.indexOf(sc.id) === -1) state.redflag_yes.push(sc.id);
          if (sc.tier === 'emergency') { addHtml('<div class="warn">🚨 ' + esc(sc.flag) + '</div>', 'bot'); showEmergency(clarEmergencyResult(sc.flag)); return; }
          state.notes += (state.notes?' ':'') + sc.flag;
          startRedflagScreens();
        }},
        {label:TT('clar_no'), fn:function(){ add(TT('clar_no'),'user'); startRedflagScreens(); }}
      ]);
    }
    function clarEmergencyResult(label) {
      var ar = LANG === 'ar';
      return {
        ok:true, emergency:true, emergency_flags:[label], urgency:'high',
        urgency_ar: ar ? 'طوارئ' : undefined, urgency_text: ar ? undefined : 'Emergency', confidence:'high',
        personal_note: ar ? 'طابقت إجابتك علامة خطر في مسار الأسئلة التوضيحية.' : 'Your answer matched a red flag during the follow-up questions.',
        simple_explanation: ar ? 'للسلامة توقفت الأسئلة وتحليل الاحتمالات هنا. اطلب تقييمًا طبيًا عاجلًا الآن.' : 'For safety, the questions and condition matching stop here. Seek urgent medical evaluation now.',
        possible_conditions: ar ? 'لن يُعرض اسم حالة محددة لأن علامة الخطر لها الأولوية.' : 'No condition is named because a red flag takes priority.',
        recommendations: [], danger_signs: label,
        when_to_seek_care: ar ? 'اطلب الرعاية الطارئة الآن. في السعودية رقم الإسعاف 997.' : 'Seek emergency care now. In Saudi Arabia, ambulance service is 997.',
        home_care:'', medication_guidance:'', questions_for_doctor:'', safety_engine:{rule_ids:['clarification_red_flag'], flags:[label]}
      };
    }
    var emLockedEls = [];
    function emCategory(d) {
      var ids = ((d && d.safety_engine && d.safety_engine.rule_ids) || []).map(String);
      if (ids.indexOf('self_harm_risk') >= 0) return 'selfharm';
      if (ids.indexOf('overdose_poisoning') >= 0) return 'poison';
      if (ids.indexOf('infant_fever_under_3m') >= 0) return 'infant';
      if (ids.indexOf('pregnancy_pain_warning') >= 0 || ids.indexOf('preeclampsia_warning') >= 0 || ids.indexOf('pregnancy_bleeding_severe') >= 0) return 'pregnancy';
      if (ids.indexOf('dvt_pe_pattern') >= 0) return 'clot';
      if (ids.indexOf('suspected_appendicitis') >= 0) return 'appendix';
      return 'general';
    }
    function emLock(ov) {
      // showEmergency can run twice (safety-check then analysis): keep the first lock list so unlock restores everything.
      // Make everything except the overlay and its ancestors inert (the overlay lives inside the page container).
      var node = ov;
      while (node && node !== document.body) {
        var parent = node.parentElement;
        if (!parent) break;
        Array.prototype.forEach.call(parent.children, function(el){
          if (el === node || el.tagName === 'SCRIPT' || el.tagName === 'STYLE') return;
          if (!el.hasAttribute('inert')) { el.setAttribute('inert', ''); emLockedEls.push(el); }
        });
        node = parent;
      }
      document.body.classList.add('ss-em-open');
      try { clearOpts(); } catch(e) {}
      try { if (progressTimer) clearTimeout(progressTimer); } catch(e) {}
    }
    function emUnlock() {
      emLockedEls.forEach(function(el){ el.removeAttribute('inert'); });
      emLockedEls = [];
      document.body.classList.remove('ss-em-open');
    }
    function showEmergency(d) {
      lastResult = d;
      const ov = document.getElementById('emOverlay');
      const cat = emCategory(d);
      const list = (d.emergency_flags || []).map(function(f){ return '<span class="em-chip">🚨 ' + esc(f) + '</span>'; }).join('');
      var steps = [];
      if (cat === 'selfharm') {
        steps = ['em_sh1','em_sh2','em_sh3'];
      } else if (cat === 'poison') {
        steps = ['em_po1','em_po2','em_step2','em_step3'];
      } else if (cat === 'infant') {
        steps = ['em_in1','em_in2','em_in3'];
      } else if (cat === 'appendix') {
        steps = ['em_ap1','em_ap2','em_ap3'];
      } else if (cat === 'pregnancy') {
        steps = ['em_pg1','em_pg2','em_pg3'];
      } else if (cat === 'clot') {
        steps = ['em_dv1','em_dv2','em_dv3'];
      } else {
        steps = ['em_step1','em_step2','em_step3','em_step4'];
      }
      const stepsT = cat === 'selfharm' ? TT('em_sh_t') : TT('em_steps_t');
      const stepsHtml = '<div class="em-steps"><div class="em-steps-t">' + esc(stepsT) + '</div><ol>' + steps.map(function(k){ return '<li>' + esc(TT(k)) + '</li>'; }).join('') + '</ol></div>';
      const extraCall = cat === 'selfharm'
        ? '<a class="em-call em-call-alt" href="tel:937">📞 937</a><a class="em-call em-call-alt" href="tel:920033360">📞 920033360</a>' : '';
      ov.setAttribute('role', 'alertdialog');
      ov.setAttribute('aria-modal', 'true');
      ov.setAttribute('aria-labelledby', 'emTitle');
      ov.setAttribute('aria-describedby', 'emSub');
      ov.innerHTML = '<div class="em-card" data-em-cat="' + cat + '"><div class="em-icon">🚑</div><h3 id="emTitle">' + esc(TT('em_t')) + '</h3><p id="emSub">' + esc(TT('em_sub')) + '</p><div class="em-flags">' + list + '</div>' +
        '<div class="em-btns"><a class="em-call em-call-main" data-em-callbtn href="tel:' + escAttr(String(TT('em_num')||'').replace(/[^0-9+]/g,'')) + '">' + esc(TT('em_call')) + ' ' + esc(TT('em_num')) + '</a>' + extraCall + '</div>' +
        stepsHtml +
        '<div class="em-num" role="button" tabindex="0" data-em-copy title="' + escAttr(TT('em_copy')) + '">☎️ ' + esc(TT('em_num')) + '</div>' +
        '<div class="em-btns em-exit" data-em-exit><button type="button" class="em-proceed em-ghost" data-em-proceed>' + esc(TT('em_details')) + '</button></div>' +
        '<div class="em-confirm" data-em-confirm hidden><p class="em-confirm-q">' + esc(TT('em_confirm_q')) + '</p><div class="em-btns"><button type="button" class="em-proceed" data-em-yes>' + esc(TT('em_confirm_yes')) + '</button><button type="button" class="em-call em-back" data-em-no>' + esc(TT('em_confirm_no')) + '</button></div></div>' +
        '<div class="em-disc">' + esc(TT('em_disc')) + '</div></div>';
      const exitRow = ov.querySelector('[data-em-exit]');
      const confirmRow = ov.querySelector('[data-em-confirm]');
      const callBtn = ov.querySelector('[data-em-callbtn]');
      const proceedBtn = ov.querySelector('[data-em-proceed]');
      if (proceedBtn) proceedBtn.addEventListener('click', function(){
        exitRow.hidden = true; confirmRow.hidden = false;
        const yes = confirmRow.querySelector('[data-em-yes]'); if (yes) yes.focus();
      });
      const noBtn = ov.querySelector('[data-em-no]');
      if (noBtn) noBtn.addEventListener('click', function(){
        confirmRow.hidden = true; exitRow.hidden = false; if (callBtn) callBtn.focus();
      });
      const yesBtn = ov.querySelector('[data-em-yes]');
      if (yesBtn) yesBtn.addEventListener('click', closeEmergency);
      // The overlay cannot be dismissed by Escape or by clicking outside it.
      ov.onclick = function(ev){ ev.stopPropagation(); };
      ov.onkeydown = function(ev){
        if (ev.key === 'Escape') { ev.preventDefault(); ev.stopPropagation(); return; }
        if (ev.key === 'Tab') {
          const f = Array.prototype.filter.call(ov.querySelectorAll('a[href],button,[tabindex="0"]'), function(el){ return !el.closest('[hidden]'); });
          if (!f.length) return;
          const first = f[0], last = f[f.length-1];
          if (ev.shiftKey && document.activeElement === first) { ev.preventDefault(); last.focus(); }
          else if (!ev.shiftKey && document.activeElement === last) { ev.preventDefault(); first.focus(); }
        }
      };
      const copyBtn = ov.querySelector('[data-em-copy]');
      if (copyBtn) {
        copyBtn.addEventListener('click', function(){ copyEmNum(copyBtn); });
        copyBtn.addEventListener('keydown', function(ev){
          if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); copyEmNum(copyBtn); }
        });
      }
      ov.style.display = 'flex';
      emLock(ov);
      try { if (navigator.vibrate) navigator.vibrate([200, 100, 200]); } catch(e) {}
      if (callBtn) setTimeout(function(){ try { callBtn.focus(); } catch(e) {} }, 50);
    }
    function copyEmNum(el) {
      const num = (TT('em_num') || '').trim();
      const done = function(){ const o = el.textContent; el.textContent = TT('em_copied'); setTimeout(function(){ el.textContent = o; }, 1400); };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(num).then(done, done);
      } else {
        try { const ta = document.createElement('textarea'); ta.value = num; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); document.body.removeChild(ta); } catch(e) {}
        done();
      }
    }
    function reAnalyzeWithMoreInfo(previousD) {
      add(TT('incomplete_reanalyzing'), 'bot');
      clearOpts();
      var payload = Object.assign({}, state, {lang: LANG});
      payload.member_id = (state.member && state.member.id) ? Number(state.member.id) : (state.member_id || 0);
      fetch('/api/analyze', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify(payload)
      }).then(function(r){return r.json();}).then(function(d2){
        if(d2.consent_required){location.href=d2.consent_url||'/consent?next=/chat';return;}
        if (d2.ok && !d2.emergency) {
          add(TT('incomplete_done'), 'bot');
          renderResult(d2);
        } else if (d2.emergency) {
          showEmergency(d2);
        } else {
          renderResult(previousD);
        }
      }).catch(function(){ renderResult(previousD); });
    }
    function closeEmergency() {
      const ov = document.getElementById('emOverlay');
      if (ov) { ov.style.display = 'none'; ov.textContent = ''; ov.onkeydown = null; ov.onclick = null; }
      emUnlock();
      if (lastResult && lastResult._clar) { lastResult = null; nextClarNode(); return; }
      const resultToShow = lastResult;
      if (resultToShow) {
        renderResult(resultToShow);
        // Keep the report visible inside the analysis container immediately
        // after the emergency warning is dismissed, including on iOS Safari.
        requestAnimationFrame(function(){
          try { bodyEl.scrollTop = 0; } catch(e) {}
          const report = document.getElementById('symptomResultReport');
          if (report) report.setAttribute('tabindex', '-1');
        });
      }
    }
