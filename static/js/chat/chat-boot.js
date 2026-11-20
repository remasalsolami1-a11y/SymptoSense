/* SymptoSense chat — Event wiring and startChat(): must be loaded last.
   Classic script: shares the page's global scope with the other files in /static/js/chat/. Load order is fixed by chat_view.py. */
    document.getElementById('headP').textContent = TT('head_p');
    try { if (new URLSearchParams(location.search).get('demo') !== '1' && localStorage.getItem('symptosense_blood_id')) { const bb = document.getElementById('bloodBanner'); bb.textContent = TT('blood_banner'); bb.style.display = 'block'; } } catch (e) {}
    textInp.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') { e.preventDefault(); submitText(); }
    });
    if (famSelect) famSelect.addEventListener('change', function(){ switchFamilyMember(famSelect.value); });
    if (sendBtn) sendBtn.addEventListener('click', submitText);
    bodyEl.addEventListener('click', function(e){
      const suggestion=e.target.closest('[data-dq-suggestion]');
      if(suggestion&&bodyEl.contains(suggestion)){applySymptomSuggestion(suggestion.dataset.dqSuggestion||'');}
    });
    optsEl.addEventListener('click', function(e){
      const suggested=e.target.closest('[data-dq-index]');
      if(suggested&&optsEl.contains(suggested)) dqAsk(Number(suggested.dataset.dqIndex||0));
    });
    window.addEventListener('pagehide',draftSave);
    document.addEventListener('visibilitychange',function(){ if(document.hidden) draftSave(); });
    window.addEventListener('pagehide', function(){stopSymptomTextMic(null, true);});
    // Initialize audio controls only now, after autoSpeak / quickMicActive
    // and the related functions have been created. Bind with addEventListener
    // instead of relying on inline onclick so Safari/CSP cannot drop the tap.
    const speakerControl = document.getElementById('spkBtn');
    if (speakerControl) speakerControl.addEventListener('click', toggleSpeak);
    const micControl = document.getElementById('micBtn');
    if (micControl) micControl.addEventListener('click', toggleQuickMic);
    syncSpeakerButton();
    syncMicButton(false);
    startChat();
