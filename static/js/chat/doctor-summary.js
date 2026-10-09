/* SymptoSense chat — Doctor summary, call script and doctor hand-off.
   Classic script: shares the page's global scope with the other files in /static/js/chat/. Load order is fixed by chat_view.py. */
    // V135: Keep the clinic text in the report itself. A modal layered over the
    // iPhone's fixed navigation / nested result scroller was unreliable on Safari.
    function careCallScriptText(){
      const d=lastResult||{};
      const input=lastAnalysisInput||state||{};
      const urgent=(d.urgency||'low')==='high';
      const syms=Array.isArray(input.symptoms)?input.symptoms.filter(Boolean).map(String):[];
      const risk=Array.isArray(d.risk_reasons)?d.risk_reasons.map(function(r){
        return typeof r==='string'?r:(r&&typeof r==='object'?(r.message||r.description||r.name||''):'');
      }).filter(Boolean):[];
      const value=function(x){return Array.isArray(x)?x.filter(Boolean).join(LANG==='ar'?'، ':', '):String(x==null?'':x).trim();};
      const lines=[];
      lines.push(urgent?(LANG==='ar'?'مرحبًا، أحتاج مساعدة طبية عاجلة الآن.':'Hello, I need urgent medical help now.'):(LANG==='ar'?'مرحبًا، أريد حجز تقييم طبي بسبب أعراض أعاني منها.':'Hello, I would like to arrange medical assessment for my symptoms.'));
      if(input.age)lines.push((LANG==='ar'?'العمر: ':'Age: ')+value(input.age));
      const gender=value(input.gender);
      if(gender&&gender!=='unknown'&&gender!=='غير محدد')lines.push((LANG==='ar'?'الجنس: ':'Sex: ')+(gender==='m'?(LANG==='ar'?'ذكر':'Male'):(gender==='f'?(LANG==='ar'?'أنثى':'Female'):gender)));
      lines.push((LANG==='ar'?'الأعراض: ':'Symptoms: ')+(syms.length?syms.join(LANG==='ar'?'، ':', '):(LANG==='ar'?'لم تُسجَّل أعراض محددة':'No specific symptoms recorded'))+'.');
      if(input.duration)lines.push((LANG==='ar'?'مدة الأعراض: ':'Symptom duration: ')+value(input.duration)+'.');
      if(input.severity)lines.push((LANG==='ar'?'الشدة المسجلة: ':'Recorded severity: ')+value(input.severity)+'/5.');
      if(input.pattern_worse)lines.push((LANG==='ar'?'تزداد مع/عند: ':'Worse with/when: ')+value(input.pattern_worse)+'.');
      if(input.pattern_relief)lines.push((LANG==='ar'?'تخف مع: ':'Relieved by: ')+value(input.pattern_relief)+'.');
      if(input.notes)lines.push((LANG==='ar'?'ملاحظات إضافية: ':'Additional notes: ')+value(input.notes)+'.');
      if(input.conditions)lines.push((LANG==='ar'?'تاريخ صحي ذكرته: ':'Health history I mentioned: ')+value(input.conditions)+'.');
      if(input.medications)lines.push((LANG==='ar'?'الأدوية الحالية التي ذكرتها: ':'Current medicines I mentioned: ')+value(input.medications)+'.');
      if(risk.length)lines.push((LANG==='ar'?'علامة مهمة ظهرت في التقييم: ':'Important finding from the assessment: ')+risk.slice(0,2).join(LANG==='ar'?'، ':', ')+'.');
      if(!urgent)lines.push(LANG==='ar'?'هل أحتاج موعدًا قريبًا أو تقييمًا عاجلًا بناءً على هذه الأعراض؟':'Do I need an appointment soon or urgent assessment for these symptoms?');
      return lines.join('\n');
    }
    function doctorSummaryText() {
      const d=lastResult||{}; const input=lastAnalysisInput||state||{};
      const syms=Array.isArray(input.symptoms)?input.symptoms.filter(Boolean):[];
      const matches=Array.isArray(d.knowledge_matches)?d.knowledge_matches.slice(0,3):[];
      const riskReasons=Array.isArray(d.risk_reasons)?d.risk_reasons:[];
      const yes=(differentialAnswers||[]).filter(function(x){return x.answer==='yes';}).map(function(x){return x.name;}).filter(Boolean);
      const no=(differentialAnswers||[]).filter(function(x){return x.answer==='no';}).map(function(x){return x.name;}).filter(Boolean);
      const qs=resultQuestionList(d).slice(0,3);
      const lines=[];
      lines.push(LANG==='ar'?'ملخص SymptoSense لزيارة الطبيب':'SymptoSense doctor-visit summary');
      lines.push('');
      lines.push((LANG==='ar'?'الأعراض: ':'Symptoms: ')+(syms.length?syms.join(LANG==='ar'?'، ':', '):(LANG==='ar'?'غير محدد':'Not specified')));
      if(input.duration) lines.push((LANG==='ar'?'البداية/المدة: ':'Onset/duration: ')+input.duration);
      if(input.severity) lines.push((LANG==='ar'?'الشدة: ':'Severity: ')+input.severity+'/5');
      if(input.pattern_worse) lines.push((LANG==='ar'?'يزيد مع/وقت: ':'Worse with/when: ')+input.pattern_worse);
      if(input.pattern_relief) lines.push((LANG==='ar'?'يخف مع: ':'Relieved by: ')+input.pattern_relief);
      const contextPattern=contextualSymptomPattern(input);
      if(contextPattern) lines.push((LANG==='ar'?'نمط الأعراض الملحوظ: ':'Observed symptom pattern: ')+contextPattern.label);
      if(input.medications) lines.push((LANG==='ar'?'الأدوية المذكورة: ':'Medicines mentioned: ')+input.medications);
      if(input.conditions) lines.push((LANG==='ar'?'تاريخ صحي مذكور: ':'Health history mentioned: ')+input.conditions);
      if(yes.length) lines.push((LANG==='ar'?'أعراض متابعة مؤكدة: ':'Confirmed follow-up symptoms: ')+yes.join(LANG==='ar'?'، ':', '));
      if(no.length) lines.push((LANG==='ar'?'أعراض متابعة منفية: ':'Denied follow-up symptoms: ')+no.join(LANG==='ar'?'، ':', '));
      lines.push((LANG==='ar'?'مستوى الاستعجال في التقييم: ':'Assessment urgency: ')+(d.urgency_text||d.triage_label||d.risk_label||d.urgency||''));
      if(riskReasons.length) lines.push((LANG==='ar'?'علامات/أسباب الأمان: ':'Safety findings: ')+riskReasons.slice(0,3).map(function(r){return r.message||r.description||r.name||'';}).filter(Boolean).join(LANG==='ar'?'، ':', '));
      if(matches.length) lines.push((LANG==='ar'?'احتمالات غير تشخيصية ظهرت: ':'Non-diagnostic matches shown: ')+matches.map(function(m){return NAME(m,'name_ar','name_en')||'';}).filter(Boolean).join(LANG==='ar'?'، ':', '));
      if(qs.length){ lines.push(''); lines.push(LANG==='ar'?'أسئلة مقترحة للطبيب:':'Questions to ask the doctor:'); qs.forEach(function(q){lines.push('• '+q);}); }
      lines.push('');
      lines.push(LANG==='ar'?'هذا ملخص توعوي من SymptoSense وليس تشخيصًا طبيًا.':'This is an educational SymptoSense summary, not a medical diagnosis.');
      return lines.join('\n');
    }
    function openDoctorCard() {
      const urgent=((lastResult||{}).urgency||'low')==='high';
      const clinic=careCallScriptText();
      const summary=doctorSummaryText();
      const combined=(LANG==='ar'?'نص التواصل\n':'Contact script\n')+clinic+'\n\n'+(LANG==='ar'?'ملخص للطبيب\n':'Clinician summary\n')+summary;
      const overlay=document.createElement('div'); overlay.className='doctor-card-overlay'; overlay.id='doctorCardOverlay';
      const canShare=!!(lastResult&&lastResult.record_id);
      const title=urgent?(LANG==='ar'?'ملخص للطوارئ والطبيب':'Emergency & clinician summary'):(LANG==='ar'?'ملخص للعيادة والطبيب':'Clinic & clinician summary');
      const clinicTitle=urgent?(LANG==='ar'?'ماذا أقول للطوارئ؟':'What to say to emergency services'):(LANG==='ar'?'ماذا أقول عند التواصل مع العيادة؟':'What to say when contacting the clinic');
      overlay.innerHTML='<div class="doctor-card"><div class="doctor-card-head"><div><h2>🩺 '+esc(title)+'</h2><p>'+esc(LANG==='ar'?'مكان واحد للتواصل مع العيادة وتسليم ملخص منظم للطبيب. راجعه قبل النسخ أو المشاركة.':'One place for the clinic contact script and a structured clinician summary. Review it before copying or sharing.')+'</p></div><button type="button" class="doctor-card-close" data-doctor-close>✕</button></div>'+
        '<div class="doctor-card-section"><b>'+esc(clinicTitle)+'</b><pre class="doctor-card-summary">'+esc(clinic)+'</pre></div>'+
        '<div class="doctor-card-section"><b>'+esc(LANG==='ar'?'الملخص المنظم للطبيب':'Structured clinician summary')+'</b><pre class="doctor-card-summary" id="doctorCardSummary">'+esc(summary)+'</pre></div>'+
        '<div class="doctor-card-actions"><button type="button" class="ss-report-action primary" data-doctor-copy>📋 '+esc(LANG==='ar'?'نسخ الملخص كاملًا':'Copy full summary')+'</button>'+(canShare?'<button type="button" class="ss-report-action" data-doctor-share>🔐 '+esc(LANG==='ar'?'مشاركة آمنة مؤقتة':'Secure temporary share')+'</button>':'')+'</div><div class="doctor-card-status" aria-live="polite"></div></div>';
      document.body.appendChild(overlay);
      overlay.addEventListener('click',function(e){
        if(e.target===overlay||e.target.closest('[data-doctor-close]')){overlay.remove();return;}
        if(e.target.closest('[data-doctor-copy]')){
          const done=function(ok){const st=overlay.querySelector('.doctor-card-status');if(st)st.textContent=ok?(LANG==='ar'?'تم نسخ النص والملخص.':'Contact script and summary copied.'):(LANG==='ar'?'تعذر النسخ؛ يمكنك تحديد النص يدويًا.':'Copy failed; you can select the text manually.');};
          if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(combined).then(function(){done(true);}).catch(function(){done(false);});}else done(false); return;
        }
        if(e.target.closest('[data-doctor-share]')&&lastResult&&lastResult.record_id){const id=Number(lastResult.record_id);overlay.remove();openDoctorHandoff(id);}
      });
    }
    async function openDoctorHandoff(recordId){
      let candidates=[];try{const d=await fetch('/api/handoff/candidates').then(r=>r.json());candidates=(d.analyses||[]).filter(x=>x.id!==recordId);}catch(e){}
      const overlay=document.createElement('div');overlay.id='handoffOverlay';overlay.style.cssText='position:fixed;inset:0;background:rgba(15,35,55,.45);z-index:1005;display:flex;align-items:center;justify-content:center;padding:16px;overflow:auto';
      const fields=[['symptoms',LANG==='ar'?'الأعراض':'Symptoms'],['duration',LANG==='ar'?'المدة':'Duration'],['severity',LANG==='ar'?'الشدة':'Severity'],['location',LANG==='ar'?'المكان':'Location'],['notes',LANG==='ar'?'الملاحظات':'Notes'],['medications',LANG==='ar'?'معلومات الأدوية':'Medication information']];
      const choices=fields.map(x=>'<label style="display:flex;gap:8px;align-items:center;padding:8px 0"><input type="checkbox" data-share="'+x[0]+'"> '+esc(x[1])+'</label>').join('');
      const prev=candidates.length?'<div style="margin-top:10px"><label style="display:flex;gap:8px;align-items:center"><input type="checkbox" data-share="previous_assessments" id="includePrevious"> '+esc(LANG==='ar'?'تقييمات سابقة مختارة':'Selected previous assessments')+'</label><div id="prevChoices" style="display:none;margin:8px 0;padding:10px;background:var(--v2-bg);border-radius:12px">'+candidates.slice(0,6).map(x=>'<label style="display:block;padding:5px"><input type="checkbox" data-prev="'+x.id+'"> '+esc((x.symptoms||[]).join(LANG==='ar'?'، ':', '))+' · '+esc(String(x.timestamp||'').slice(0,10))+'</label>').join('')+'</div></div>':'';
      overlay.innerHTML='<div style="width:min(620px,100%);background:#fff;border-radius:20px;padding:22px;border:1px solid var(--v2-line);box-shadow:0 24px 70px rgba(20,50,80,.22)"><div style="display:flex;justify-content:space-between;gap:10px"><div><h2>🗣️ '+esc(LANG==='ar'?'تجهيز ملخص لزيارة الطبيب':'Prepare for a Doctor Visit')+'</h2><p class="muted">'+esc(LANG==='ar'?'اختر فقط المعلومات التي تريد مشاركتها. لا يتم اختيار أي حقل تلقائيًا.':'Choose only what you want to share. No field is selected by default.')+'</p></div><button type="button" class="opt" id="closeHandoff">✕</button></div><div style="margin-top:12px"><b>'+esc(LANG==='ar'?'اختر ما تريد مشاركته':'Choose what to share')+'</b>'+choices+prev+'</div><label style="display:block;margin-top:12px"><b>'+esc(LANG==='ar'?'مدة صلاحية الرابط':'Link expiration')+'</b><select id="handoffExpiry" style="width:100%;margin-top:6px"><option value="15">15 '+esc(LANG==='ar'?'دقيقة':'minutes')+'</option><option value="60">1 '+esc(LANG==='ar'?'ساعة':'hour')+'</option><option value="1440">24 '+esc(LANG==='ar'?'ساعة':'hours')+'</option></select></label><div id="handoffStatus" class="muted" style="margin-top:10px"></div><button type="button" class="btn pri" id="generateHandoff" style="width:100%;margin-top:12px">📱 '+esc(LANG==='ar'?'إنشاء QR مؤقت':'Generate Temporary QR')+'</button><div id="handoffResult"></div></div>';
      document.body.appendChild(overlay);document.getElementById('closeHandoff').onclick=()=>overlay.remove();const ip=document.getElementById('includePrevious');if(ip)ip.onchange=()=>document.getElementById('prevChoices').style.display=ip.checked?'block':'none';
      document.getElementById('generateHandoff').onclick=async function(){const selected={};overlay.querySelectorAll('[data-share]').forEach(x=>selected[x.dataset.share]=x.checked);if(!Object.values(selected).some(Boolean)){document.getElementById('handoffStatus').textContent=LANG==='ar'?'اختر معلومة واحدة على الأقل.':'Select at least one item.';return;}const previous_ids=Array.from(overlay.querySelectorAll('[data-prev]:checked')).map(x=>parseInt(x.dataset.prev));document.getElementById('handoffStatus').textContent=LANG==='ar'?'جاري إنشاء الرابط المؤقت…':'Generating temporary link…';try{const r=await fetch('/api/handoff/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({record_id:recordId,selected:selected,previous_ids:previous_ids,expires_minutes:parseInt(document.getElementById('handoffExpiry').value)})});const d=await r.json();if(!r.ok||!d.ok)throw new Error(d.error||'failed');window.__handoffToken=d.token;const qr=d.qr_data_uri?'<img alt="QR" src="'+escAttr(safeDataImage(d.qr_data_uri))+'" style="width:220px;max-width:100%;margin:12px auto;display:block">':'';document.getElementById('handoffResult').innerHTML='<div class="res-assess" style="margin-top:12px;text-align:center">'+qr+'<a class="v2-source-link" href="'+escAttr(safeLink(d.share_url))+'" target="_blank" rel="noopener">'+esc(LANG==='ar'?'فتح رابط المشاركة':'Open share link')+'</a><div class="muted" id="handoffCountdown" style="margin:8px 0"></div><button type="button" class="btn ghost" id="copyHandoff">🔗 '+esc(LANG==='ar'?'نسخ الرابط':'Copy Link')+'</button> <button type="button" class="btn ghost danger-lite" id="revokeHandoff">'+esc(LANG==='ar'?'إلغاء الرابط':'Revoke Link')+'</button></div>';document.getElementById('copyHandoff').onclick=()=>navigator.clipboard&&navigator.clipboard.writeText(d.share_url);document.getElementById('revokeHandoff').onclick=()=>revokeDoctorLink(d.token);startHandoffCountdown(d.expires_at);document.getElementById('handoffStatus').textContent='';}catch(e){const m=String((e&&e.message)||'');document.getElementById('handoffStatus').textContent=m.includes('selected_information_empty')?(LANG==='ar'?'المعلومة التي اخترتها غير موجودة في هذا التحليل. اختر معلومة أخرى للمشاركة.':'The selected item has no saved value in this analysis. Choose another item to share.'):(LANG==='ar'?'تعذر إنشاء الرابط.':'Unable to create the link.');}};
    }
    function startHandoffCountdown(expiresAt){const el=document.getElementById('handoffCountdown');if(!el)return;const tick=()=>{const ms=new Date(expiresAt).getTime()-Date.now();if(ms<=0){el.textContent=LANG==='ar'?'انتهت صلاحية الرابط.':'Link expired.';return;}const m=Math.ceil(ms/60000);el.textContent=(LANG==='ar'?'ينتهي الرابط خلال ':'Link expires in ')+m+(LANG==='ar'?' دقيقة':' min');setTimeout(tick,30000)};tick();}
    async function revokeDoctorLink(token){if(!confirm(LANG==='ar'?'إلغاء الرابط الآن؟':'Revoke this link now?'))return;const r=await fetch('/api/handoff/revoke',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:token})});const d=await r.json();if(d.ok){const box=document.getElementById('handoffResult');if(box)box.innerHTML='<div class="v2-safe-note">'+esc(LANG==='ar'?'تم إلغاء الرابط ولم يعد متاحًا.':'The link was revoked and is no longer available.')+'</div>';}}
