/* SymptoSense chat — Read-aloud and voice input (speech synthesis, recognition, recorded-audio fallback).
   Classic script: shares the page's global scope with the other files in /static/js/chat/. Load order is fixed by chat_view.py. */
    let autoSpeak = false;
    let lastSpokenMsg = '';
    function setAudioStatus(msg) {
      const el = document.getElementById('audioState');
      if (el) el.textContent = msg || '';
    }
    function syncSpeakerButton() {
      const b = document.getElementById('spkBtn');
      if (!b) return;
      const label = autoSpeak
        ? (LANG === 'ar' ? 'القراءة الصوتية مفعلة. اضغط لإيقافها.' : 'Read aloud is on. Press to turn it off.')
        : (LANG === 'ar' ? 'القراءة الصوتية متوقفة. اضغط لتفعيلها.' : 'Read aloud is off. Press to turn it on.');
      b.setAttribute('aria-pressed', autoSpeak ? 'true' : 'false');
      b.setAttribute('aria-label', label);
      b.title = label;
      b.classList.toggle('is-on', autoSpeak);
      const textEl = document.getElementById('spkText');
      if (textEl) textEl.textContent = autoSpeak
        ? (LANG === 'ar' ? 'القراءة بصوت عالٍ: مفعلة' : 'Read aloud: On')
        : (LANG === 'ar' ? 'القراءة بصوت عالٍ' : 'Read aloud');
    }
    function currentSpeakableText() {
      const focused = bodyEl && bodyEl.querySelector('.step-focus-question');
      if (focused && focused.textContent.trim()) return focused.textContent.trim();
      const bubbles = bodyEl ? bodyEl.querySelectorAll('.bubble.q,.bubble.bot') : [];
      for (let i = bubbles.length - 1; i >= 0; i--) {
        const text = (bubbles[i].innerText || bubbles[i].textContent || '').trim();
        if (text) return text;
      }
      return LANG === 'ar' ? 'تم تفعيل القراءة بصوت عالٍ.' : 'Read aloud enabled.';
    }
    function toggleSpeak() {
      if (!('speechSynthesis' in window) || typeof SpeechSynthesisUtterance === 'undefined') {
        setAudioStatus(LANG === 'ar' ? 'القراءة الصوتية غير مدعومة في هذا المتصفح.' : 'Read aloud is not supported in this browser.');
        add(TT('no_speech'), 'bot');
        return;
      }
      autoSpeak = !autoSpeak;
      if (!autoSpeak) speechSynthesis.cancel();
      syncSpeakerButton();
      setAudioStatus(autoSpeak
        ? (LANG === 'ar' ? 'تم تفعيل القراءة بصوت عالٍ.' : 'Read aloud enabled.')
        : (LANG === 'ar' ? 'تم إيقاف القراءة بصوت عالٍ.' : 'Read aloud disabled.'));
      // iOS Safari requires speech to be initiated from the user's tap.
      // Read the current question immediately so the control gives instant feedback.
      if (autoSpeak) speakText(currentSpeakableText());
    }
    function speakText(txt) {
      if (!('speechSynthesis' in window) || typeof SpeechSynthesisUtterance === 'undefined') return;
      const clean = s => String(s || '').replace(/\s{2,}/g, ' ').trim();
      const t = clean(txt);
      if (!t) return;
      speechSynthesis.cancel();
      const uu = new SpeechSynthesisUtterance(t);
      uu.lang = LANG === 'en' ? 'en-GB' : 'ar-SA';
      const pre = LANG === 'en' ? 'en' : 'ar';
      const v = speechSynthesis.getVoices().find(v => v.lang && v.lang.toLowerCase().indexOf(pre) === 0);
      if (v) uu.voice = v;
      uu.rate = 0.95;
      try { speechSynthesis.resume(); } catch(e) {}
      speechSynthesis.speak(uu);
    }
    if ('speechSynthesis' in window) {
      try { speechSynthesis.getVoices(); } catch(e) {}
      if ('onvoiceschanged' in speechSynthesis) {
        speechSynthesis.onvoiceschanged = function(){ try { speechSynthesis.getVoices(); } catch(e) {} };
      }
    }
    // ---------------- On-demand microphone ----------------
    // The microphone is OFF by default and starts only after a user tap.
    // Chrome/Android can use SpeechRecognition directly; Safari/iPhone falls
    // back to MediaRecorder and a short server-side transcription. Audio is
    // processed for the request only and is not stored by SymptoSense.
    let quickMicRec = null;
    let quickMicActive = false;
    let quickMicTranscript = '';
    let quickMicMode = '';
    let quickMediaRecorder = null;
    let quickMediaStream = null;
    let quickMediaChunks = [];
    function syncMicButton(active) {
      quickMicActive = !!active;
      const b = document.getElementById('micBtn');
      if (!b) return;
      const label = quickMicActive
        ? (LANG === 'ar' ? 'الميكروفون يسجل الآن. اضغط لإيقاف التسجيل.' : 'Microphone is recording. Press to stop.')
        : (LANG === 'ar' ? 'الميكروفون متوقف. اضغط لبدء تسجيل إجابتك.' : 'Microphone is off. Press to record your answer.');
      b.setAttribute('aria-pressed', quickMicActive ? 'true' : 'false');
      b.setAttribute('aria-label', label);
      b.title = label;
      b.classList.toggle('is-recording', quickMicActive);
      const textEl = document.getElementById('micText');
      if (textEl) textEl.textContent = quickMicActive
        ? (LANG === 'ar' ? 'إيقاف التسجيل' : 'Stop recording')
        : (LANG === 'ar' ? 'الإدخال الصوتي' : 'Voice input');
      setAudioStatus(quickMicActive
        ? (LANG === 'ar' ? 'جاري تسجيل إجابتك… اضغط مرة أخرى للإيقاف.' : 'Recording your answer… press again to stop.')
        : (LANG === 'ar' ? 'الميكروفون متوقف.' : 'Microphone stopped.'));
    }
    function closeQuickMediaStream() {
      if (quickMediaStream) {
        try { quickMediaStream.getTracks().forEach(function(t){ t.stop(); }); } catch(e) {}
      }
      quickMediaStream = null;
    }
    function recordedFileName(mime) {
      const m = String(mime || '').toLowerCase();
      if (m.indexOf('mp4') !== -1 || m.indexOf('m4a') !== -1) return 'symptosense-voice.m4a';
      if (m.indexOf('ogg') !== -1) return 'symptosense-voice.ogg';
      if (m.indexOf('wav') !== -1) return 'symptosense-voice.wav';
      return 'symptosense-voice.webm';
    }
    async function sendRecordedAudio(blob) {
      if (!blob || !blob.size) {
        add(LANG === 'ar' ? 'لم يتم التقاط صوت. حاول مرة أخرى أو اكتب إجابتك.' : 'No audio was captured. Try again or type your answer.', 'bot');
        return;
      }
      setAudioStatus(LANG === 'ar' ? 'جاري تحويل الصوت إلى نص…' : 'Converting speech to text…');
      const fd = new FormData();
      fd.append('audio', blob, recordedFileName(blob.type));
      fd.append('lang', LANG);
      try {
        const r = await fetch('/api/voice', {method:'POST', body:fd});
        const d = await r.json().catch(function(){ return {}; });
        if (d.consent_required && d.consent_url) { location.href = d.consent_url; return; }
        if (!r.ok || !d.ok || !String(d.text || '').trim()) throw new Error(d.error || 'transcription_failed');
        setAudioStatus(LANG === 'ar' ? 'تم فهم التسجيل.' : 'Recording understood.');
        await submitVoiceText(String(d.text).trim());
      } catch(e) {
        add(LANG === 'ar' ? 'تعذّر فهم التسجيل الآن. يمكنك المحاولة مرة أخرى أو الاستمرار بالكتابة.' : 'Unable to understand the recording right now. Try again or continue by typing.', 'bot');
        setAudioStatus(LANG === 'ar' ? 'تعذّر تحويل الصوت.' : 'Voice transcription failed.');
      }
    }
    async function startMediaRecorderFallback() {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || typeof MediaRecorder === 'undefined') {
        add(TT('no_mic'), 'bot');
        return false;
      }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({audio:true});
        quickMediaStream = stream;
        quickMediaChunks = [];
        let mime = '';
        const choices = ['audio/mp4;codecs=mp4a.40.2','audio/mp4','audio/webm;codecs=opus','audio/webm'];
        if (typeof MediaRecorder.isTypeSupported === 'function') {
          for (const choice of choices) { if (MediaRecorder.isTypeSupported(choice)) { mime = choice; break; } }
        }
        quickMediaRecorder = mime ? new MediaRecorder(stream, {mimeType:mime}) : new MediaRecorder(stream);
        quickMicMode = 'media';
        quickMediaRecorder.ondataavailable = function(ev){ if (ev.data && ev.data.size) quickMediaChunks.push(ev.data); };
        quickMediaRecorder.onerror = function(){
          syncMicButton(false);
          closeQuickMediaStream();
          quickMediaRecorder = null; quickMicMode = ''; quickMediaChunks = [];
          add(LANG === 'ar' ? 'تعذر تشغيل الميكروفون. تحقق من الإذن ثم حاول مرة أخرى.' : 'Unable to use the microphone. Check permission and try again.', 'bot');
        };
        quickMediaRecorder.onstop = async function(){
          const type = quickMediaRecorder && quickMediaRecorder.mimeType ? quickMediaRecorder.mimeType : (quickMediaChunks[0] ? quickMediaChunks[0].type : 'audio/webm');
          const blob = new Blob(quickMediaChunks, {type:type || 'audio/webm'});
          syncMicButton(false);
          closeQuickMediaStream();
          quickMediaRecorder = null; quickMicMode = ''; quickMediaChunks = [];
          await sendRecordedAudio(blob);
        };
        quickMediaRecorder.start();
        syncMicButton(true);
        return true;
      } catch(e) {
        syncMicButton(false);
        closeQuickMediaStream();
        quickMediaRecorder = null; quickMicMode = '';
        const denied = e && (e.name === 'NotAllowedError' || e.name === 'SecurityError');
        add(denied
          ? (LANG === 'ar' ? 'لم يتم منح إذن الميكروفون. فعّل الإذن من إعدادات المتصفح ثم حاول مرة أخرى.' : 'Microphone permission was not granted. Enable it in browser settings and try again.')
          : TT('no_mic'), 'bot');
        return false;
      }
    }
    // Independent, self-contained mic control for the free-text symptom box
    // (does not share state with the main quickMic* voice-reply system above,
    // so it cannot interfere with or be interfered with by that flow). On
    // result it fills the textarea rather than auto-submitting, since the
    // user still reviews/edits before pressing "Find symptoms" either way.
    let symptomMicRec = null;
    let symptomMicStream = null;
    let symptomMicPending = false;
    let symptomMicGeneration = 0;
    function symptomMicError() {
      add(LANG === 'ar'
        ? 'تعذّر الإدخال الصوتي. تحقق من إذن الميكروفون والاتصال، أو اكتب أعراضك.'
        : 'Voice input failed. Check microphone permission and your connection, or type your symptoms.', 'bot');
    }
    function toggleSymptomTextMic(btn, textarea) {
      if (!textarea) return;
      if (symptomMicRec || symptomMicStream || symptomMicPending) {
        stopSymptomTextMic(btn);
        return;
      }
      const generation = ++symptomMicGeneration;
      const active = function(){ return generation === symptomMicGeneration && textarea.isConnected; };
      const fill = function(text){
        if (!active() || !String(text || '').trim()) return;
        textarea.value = (textarea.value ? textarea.value + ' ' : '') + String(text).trim();
        textarea.dispatchEvent(new Event('input', {bubbles:true}));
      };
      const reset = function(){
        symptomMicRec = null;
        if (symptomMicStream) symptomMicStream.getTracks().forEach(function(t){ t.stop(); });
        symptomMicStream = null; symptomMicPending = false;
        btn.classList.remove('is-recording'); btn.setAttribute('aria-pressed','false');
      };
      const recording = function(){btn.classList.add('is-recording');btn.setAttribute('aria-pressed','true');};
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (SR && !prefersRecordedAudioFallback()) {
        let finalText = '';
        try {
          const rec = new SR();
          symptomMicRec = rec;
          rec.lang = LANG === 'en' ? 'en-GB' : 'ar-SA';
          rec.continuous = false; rec.interimResults = false; rec.maxAlternatives = 1;
          rec.onstart = recording;
          rec.onresult = function(ev){
            const parts = [];
            for (let i = ev.resultIndex || 0; i < ev.results.length; i++) {
              const t = ev.results[i] && ev.results[i][0] ? ev.results[i][0].transcript : '';
              if (t) parts.push(t);
            }
            finalText = parts.join(' ').trim();
          };
          rec.onerror = function(ev){
            if (active() && (!ev || ev.error !== 'aborted')) symptomMicError();
          };
          rec.onend = function(){ if (generation !== symptomMicGeneration) return; reset(); fill(finalText); };
          rec.start(); return;
        } catch(e) { reset(); }
      }
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || typeof MediaRecorder === 'undefined') {
        symptomMicError(); return;
      }
      symptomMicPending = true;
      navigator.mediaDevices.getUserMedia({audio:true}).then(function(stream){
        if (!active()) { stream.getTracks().forEach(function(t){t.stop();}); return; }
        symptomMicStream = stream; symptomMicPending = false;
        const chunks = [];
        const rec = new MediaRecorder(stream);
        symptomMicRec = rec;
        rec.ondataavailable = function(e){ if (e.data && e.data.size) chunks.push(e.data); };
        rec.onerror = function(){ if (active()) { reset(); symptomMicError(); } };
        rec.onstop = async function(){
          if (generation !== symptomMicGeneration) return;
          const blob = new Blob(chunks, {type:rec.mimeType || 'audio/webm'});
          reset();
          if (!active()) return;
          if (!blob.size) { symptomMicError(); return; }
          const fd = new FormData();
          fd.append('audio', blob, recordedFileName(blob.type));
          fd.append('lang', LANG);
          try {
            const r = await fetch('/api/voice', {method:'POST', body:fd});
            const d = await r.json().catch(function(){return {};});
            if (!active()) return;
            if (d.consent_required && d.consent_url) { location.href=d.consent_url; return; }
            if (!r.ok || !d.ok || !String(d.text || '').trim()) throw new Error('voice_failed');
            fill(d.text);
          } catch(e) { if (active()) symptomMicError(); }
        };
        rec.start(); recording();
      }).catch(function(){ if (generation === symptomMicGeneration) { reset(); symptomMicError(); } });
    }
    function stopSymptomTextMic(btn, cancel) {
      const rec = symptomMicRec;
      if (cancel || symptomMicPending) ++symptomMicGeneration;
      symptomMicRec = null; symptomMicPending = false;
      try { if (rec && rec.stop) rec.stop(); } catch(e) {}
      try { if (symptomMicStream) symptomMicStream.getTracks().forEach(function(t){t.stop();}); } catch(e) {}
      symptomMicStream = null;
      if (btn) {btn.classList.remove('is-recording');btn.setAttribute('aria-pressed','false');}
    }
    function startSpeechRecognition() {
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SR) return false;
      quickMicTranscript = '';
      quickMicMode = 'speech';
      quickMicRec = new SR();
      quickMicRec.lang = LANG === 'en' ? 'en-GB' : 'ar-SA';
      quickMicRec.continuous = false;
      quickMicRec.interimResults = false;
      quickMicRec.maxAlternatives = 1;
      quickMicRec.onstart = function(){ syncMicButton(true); };
      quickMicRec.onresult = function(ev){
        const parts = [];
        for (let i = ev.resultIndex || 0; i < ev.results.length; i++) {
          const t = ev.results[i] && ev.results[i][0] ? ev.results[i][0].transcript : '';
          if (t) parts.push(t);
        }
        quickMicTranscript = parts.join(' ').trim();
      };
      quickMicRec.onerror = function(ev){
        const code = (ev && ev.error) || '';
        syncMicButton(false);
        quickMicRec = null; quickMicMode = '';
        if (code === 'aborted' || code === 'no-speech') return;
        if (code === 'not-allowed' || code === 'service-not-allowed') {
          add(LANG === 'ar' ? 'لم يتم منح إذن الميكروفون. يمكنك الاستمرار بالكتابة.' : 'Microphone permission was not granted. You can continue by typing.', 'bot');
          return;
        }
        // If native recognition is unavailable at runtime, use real recording
        // instead (important on Safari/iPhone and some embedded browsers).
        startMediaRecorderFallback();
      };
      quickMicRec.onend = function(){
        if (quickMicMode !== 'speech') return;
        const text = String(quickMicTranscript || '').trim();
        syncMicButton(false);
        quickMicRec = null; quickMicMode = ''; quickMicTranscript = '';
        if (text) submitVoiceText(text);
      };
      try { quickMicRec.start(); return true; }
      catch(e) { quickMicRec = null; quickMicMode = ''; return false; }
    }
    function prefersRecordedAudioFallback() {
      // iPhone/iPad Safari may expose webkitSpeechRecognition even when the
      // remote recognition service cannot start. Recording locally and sending
      // the short clip to /api/voice is substantially more reliable there.
      const ua = String(navigator.userAgent || '');
      const appleMobile = /iPhone|iPad|iPod/i.test(ua) ||
        (navigator.platform === 'MacIntel' && Number(navigator.maxTouchPoints || 0) > 1);
      return appleMobile && typeof MediaRecorder !== 'undefined';
    }
    async function toggleQuickMic() {
      if (quickMicActive) {
        if (quickMicMode === 'speech' && quickMicRec) { try { quickMicRec.stop(); } catch(e) {} return; }
        if (quickMicMode === 'media' && quickMediaRecorder) {
          try { if (quickMediaRecorder.state !== 'inactive') quickMediaRecorder.stop(); } catch(e) {}
          return;
        }
      }
      if (prefersRecordedAudioFallback()) {
        await startMediaRecorderFallback();
        return;
      }
      const nativeStarted = startSpeechRecognition();
      if (!nativeStarted) await startMediaRecorderFallback();
    }
    async function submitVoiceText(text) {
      const spoken = String(text || '').trim();
      if (!spoken) return;
      add(spoken, 'user');
      hideText();
      clearOpts();
      if (state.step === 'age') {
        const normalizedAge = spoken.replace(/[٠-٩]/g,function(d){return String('٠١٢٣٤٥٦٧٨٩'.indexOf(d));}).replace(/[۰-۹]/g,function(d){return String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d));});
        const num = parseInt(normalizedAge, 10);
        if (num > 0 && num < 121) { state.age = num; askGender(); }
        else { add(TT('age_invalid'), 'bot'); showText(TT('age_ph')); }
      } else if (state.step === 'gender') {
        const v = spoken.toLowerCase();
        if (/أنثى|انثى|female|woman|بنت/.test(v)) { state.gender='f'; add(TT('female'),'bot'); askSymptoms(); }
        else if (/ذكر|male|man|ولد/.test(v)) { state.gender='m'; add(TT('male'),'bot'); askSymptoms(); }
        else { add(LANG==='ar'?'قل «ذكر» أو «أنثى»، أو اختر الزر المناسب.':'Say “male” or “female”, or choose the matching button.','bot'); askGender(); }
      } else if (state.step === 'symptoms') {
        await extractSmartSymptoms(spoken);
      } else if (state.step === 'duration') {
        state.duration = spoken; askSeverity();
      } else if (state.step === 'severity') {
        const normalized = spoken.replace(/[٠-٩]/g,function(d){return String('٠١٢٣٤٥٦٧٨٩'.indexOf(d));}).replace(/[۰-۹]/g,function(d){return String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d));});
        const num = parseInt(normalized, 10);
        if (num >= 1 && num <= 5) { state.severity = String(num); if(state.quick_mode) startClarify(); else askSymptomPath(); }
        else { add(LANG==='ar'?'اذكر الشدة من 1 إلى 5، أو اختر أحد الأزرار.':'Say a severity from 1 to 5, or choose one of the buttons.','bot'); askSeverity(); }
      } else if (state.step === 'conditions') {
        state.conditions = spoken; state.history_answered = true; askMeds();
      } else if (state.step === 'medications') {
        state.medications = spoken; askAllergies();
      } else if (state.step === 'allergies') {
        state.allergies = spoken; startClarify();
      } else if (state.step === 'notes') {
        state.notes = spoken; askConditions();
      } else if (state.step === 'clarification') {
        state.location = spoken;
        state.notes += (state.notes?' ':'') + (LANG==='ar'?'تفصيل إضافي: ':'Additional detail: ') + spoken;
        const next = clarCustomNext; clarCustomNext = null; walkClarNode(next);
      } else if (state.step === 'followup') {
        submitFollowup(spoken);
      } else {
        state.notes = ((state.notes || '') + ' ' + spoken).trim();
        showDataQualityGate();
      }
    }
