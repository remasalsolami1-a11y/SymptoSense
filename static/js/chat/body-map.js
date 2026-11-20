/* SymptoSense chat — Body map and body-region selection for the symptom step. State (selectedBodyZone, bodyMapView, ...) lives here; symptom-flow.js reads it at call time.
   Classic script: shares the page's global scope with the other files in /static/js/chat/. Load order is fixed by chat_view.py. */

    let selectedBodyZone = null;
    let bodyMapView = 'front';
    let symptomOptionsExpanded = false;
    let bodyMapOpen = false;
    let symptomInputMethod = 'body';
    function cleanBodyTerm(value) {
      return String(value || '').toLowerCase()
        .replace(/[ً-ٰٟ]/g,'')
        .replace(/[أإآٱ]/g,'ا').replace(/ى/g,'ي').replace(/ة/g,'ه').replace(/ؤ/g,'و').replace(/ئ/g,'ي')
        .replace(/[^a-z0-9؀-ۿ]+/g,' ').replace(/\s+/g,' ').trim();
    }
    function bodyRegionLabel(regionKey) {
      return BODY_MAP_REGIONS[regionKey] ? BODY_MAP_REGIONS[regionKey].label : regionKey;
    }
    function bodyZoneLabel(zoneKey) {
      return BODY_MAP_ZONES[zoneKey] ? BODY_MAP_ZONES[zoneKey].label : '';
    }
    function regionDetailZones(regionKey) {
      return Object.keys(BODY_MAP_ZONES).filter(function(key){ return BODY_MAP_ZONES[key].parent === regionKey; });
    }
    function symptomMatchesBodyRegion(symptom, regionKey) {
      const region = BODY_MAP_REGIONS[regionKey];
      if (!region) return false;
      const value = cleanBodyTerm(symptom);
      if (!value) return false;
      return (region.symptoms || []).some(function(item){
        const candidate = cleanBodyTerm(item);
        return candidate && (value === candidate || value.indexOf(candidate) !== -1 || candidate.indexOf(value) !== -1);
      });
    }
    function inferBodyRegions(raw, found) {
      const regions = [];
      function addRegion(key){ if (BODY_MAP_REGIONS[key] && regions.indexOf(key) === -1) regions.push(key); }
      (found || []).forEach(function(symptom){
        Object.keys(BODY_MAP_REGIONS).forEach(function(key){ if (symptomMatchesBodyRegion(symptom, key)) addRegion(key); });
      });
      const text = cleanBodyTerm(raw);
      const keywordMap = LANG === 'ar' ? {
        head:['راس','صداع','دوخه','دوار','عين','عيون','وجه'],
        throat:['حلق','بلع','لوز'],
        chest:['صدر','خفقان','قلب','تنفس','ضيق نفس','نفس'],
        abdomen:['بطن','معده','مغص','غثيان','قيء','استفراغ','تقيؤ','اسهال'],
        arms:['ذراع','يد','كتف','مرفق','رسغ'],
        legs:['رجل','ساق','ركبه','قدم','كاحل','فخذ','سمانه'],
        skin:['جلد','طفح','حكه','احمرار'],
        back:['ظهر','اسفل الظهر','عمود فقري']
      } : {
        head:['head','headache','dizziness','dizzy','eye','face'],
        throat:['throat','swallow','tonsil'],
        chest:['chest','palpitation','heart','breath','breathing','shortness of breath'],
        abdomen:['abdomen','abdominal','stomach','belly','nausea','vomit','vomiting','diarrhea','diarrhoea'],
        arms:['arm','hand','shoulder','elbow','wrist'],
        legs:['leg','knee','foot','ankle','thigh','calf'],
        skin:['skin','rash','itch','itching','redness'],
        back:['back','lower back','spine']
      };
      Object.keys(keywordMap).forEach(function(key){
        if ((keywordMap[key] || []).some(function(word){
          const w = cleanBodyTerm(word);
          return w && (LANG === 'ar' ? text.indexOf(w) !== -1 : (' ' + text + ' ').indexOf(' ' + w + ' ') !== -1);
        })) addRegion(key);
      });
      return regions;
    }
    function setBodyRegionSelection(regionKey, keepExisting) {
      if (!BODY_MAP_REGIONS[regionKey]) return;
      state.body_region_primary = regionKey;
      if (keepExisting) {
        state.body_regions = Array.from(new Set((state.body_regions || []).concat([regionKey])));
      } else {
        state.body_regions = [regionKey];
      }
    }
    function rememberBodyRegionSymptoms(regionKey, symptoms) {
      if (!BODY_MAP_REGIONS[regionKey]) return;
      if (!state.body_region_custom_symptoms || typeof state.body_region_custom_symptoms !== 'object') state.body_region_custom_symptoms = {};
      const current = Array.isArray(state.body_region_custom_symptoms[regionKey]) ? state.body_region_custom_symptoms[regionKey] : [];
      state.body_region_custom_symptoms[regionKey] = Array.from(new Set(current.concat((symptoms || []).map(function(x){ return String(x || '').trim(); }).filter(Boolean))));
      if (state.body_region_needs_symptom === regionKey && state.body_region_custom_symptoms[regionKey].length) state.body_region_needs_symptom = null;
    }
    function forgetBodyRegionSymptom(symptom) {
      const target = String(symptom || '').trim();
      if (!target || !state.body_region_custom_symptoms || typeof state.body_region_custom_symptoms !== 'object') return;
      Object.keys(state.body_region_custom_symptoms).forEach(function(regionKey){
        const remaining = (state.body_region_custom_symptoms[regionKey] || []).filter(function(x){ return x !== target; });
        if (remaining.length) state.body_region_custom_symptoms[regionKey] = remaining;
        else delete state.body_region_custom_symptoms[regionKey];
      });
    }
    function hasSymptomForBodyRegion(regionKey) {
      const known = (state.symptoms || []).some(function(symptom){ return symptomMatchesBodyRegion(symptom, regionKey); });
      const custom = state.body_region_custom_symptoms && Array.isArray(state.body_region_custom_symptoms[regionKey])
        ? state.body_region_custom_symptoms[regionKey].some(function(symptom){ return (state.symptoms || []).includes(symptom); })
        : false;
      return known || custom;
    }
    function withoutBodyRegionSymptoms(symptoms, regionKeys) {
      const keys = regionKeys || [];
      return (symptoms || []).filter(function(symptom){
        return !keys.some(function(key){ return symptomMatchesBodyRegion(symptom, key); });
      });
    }
    function continueAfterBodyRegionChoice(regionKey) {
      if (regionKey && !hasSymptomForBodyRegion(regionKey)) {
        state.body_region_needs_symptom = regionKey;
        askSymptoms();
        setTimeout(function(){ showBodyRegion(regionKey, false); }, 0);
        return;
      }
      state.body_region_needs_symptom = null;
      askDuration();
    }
    function showBodyRegionConflict(raw, found, typedRegions) {
      const selected = state.body_region_primary;
      if (!selected || !typedRegions || !typedRegions.length || typedRegions.indexOf(selected) !== -1) return false;
      const typedPrimary = typedRegions[0];
      const selectedLabel = bodyRegionLabel(selected);
      const typedLabel = bodyRegionLabel(typedPrimary);
      const resolvedSymptoms = (found && found.length) ? found.slice() : [raw];
      state.step = 'symptoms';
      updateFlow(state.step);
      const question = LANG === 'ar'
        ? 'اخترت ' + selectedLabel + ' من خريطة الجسم، لكن وصفك يشير إلى ' + typedLabel + '. أيهما تريد تحليله كعرض أساسي الآن؟'
        : 'You selected ' + selectedLabel + ' on the body map, but your description points to ' + typedLabel + '. Which should be the main symptom area now?';
      const card = focusStepQuestion('🧭 ' + question);
      if (card) {
        const note = document.createElement('div');
        note.className = 'body-region-conflict-note';
        note.innerHTML = '<span>📍 '+esc(selectedLabel)+'</span><span>✍️ '+esc(typedLabel)+'</span>';
        card.appendChild(note);
      }
      showOpts([
        {label:(LANG==='ar'?'📍 '+selectedLabel+' فقط':'📍 '+selectedLabel+' only'),fn:function(){
          add(LANG==='ar'?selectedLabel+' هو المقصود':selectedLabel+' is the intended area','user');
          state.body_regions=[selected]; state.body_region_primary=selected;
          state.symptoms=withoutBodyRegionSymptoms(state.symptoms, typedRegions);
          continueAfterBodyRegionChoice(selected);
        }},
        {label:(LANG==='ar'?'✍️ '+typedLabel+' فقط':'✍️ '+typedLabel+' only'),fn:function(){
          add(LANG==='ar'?typedLabel+' هو المقصود':typedLabel+' is the intended area','user');
          state.symptoms=Array.from(new Set(withoutBodyRegionSymptoms(state.symptoms,[selected]).concat(resolvedSymptoms)));
          state.body_regions=typedRegions.slice(); state.body_region_primary=typedPrimary; state.body_region_needs_symptom=null;
          askDuration();
        }},
        {label:(LANG==='ar'?'➕ الاثنين معًا':'➕ Both areas'),fn:function(){
          add(LANG==='ar'?'الاثنان معًا':'Both areas','user');
          state.symptoms=Array.from(new Set((state.symptoms||[]).concat(resolvedSymptoms)));
          state.body_regions=Array.from(new Set((state.body_regions||[]).concat(typedRegions)));
          state.body_region_primary=selected;
          continueAfterBodyRegionChoice(selected);
        }}
      ]);
      return true;
    }
    function closeBodyMapSheet() {
      const old=document.getElementById('symptomBodySheet');
      if(old) old.remove();
      bodyMapOpen=false;
      document.body.classList.remove('symptom-sheet-open');
    }
    function openBodyMapSheet(regionKey) {
      if(!compactSymptomUI()) return;
      closeBodyMapSheet();
      symptomInputMethod='body';
      const pane=document.getElementById('symptomMethodPane');
      if(!pane) return;
      pane.classList.add('symptom-method-pane-body');
      pane.innerHTML=renderBodyMapCard();
      bodyMapOpen=true;
      bindBodyMapCard();
      if (selectedBodyZone && BODY_MAP_ZONES[selectedBodyZone]) showBodyZone(selectedBodyZone, false);
      else if(regionKey && BODY_MAP_REGIONS[regionKey]) showBodyRegion(regionKey,false);
    }
    function bmX(px){ return +(BM_OX + px*BM_SC).toFixed(1); }
    function bmY(py){ return +(BM_OY + py*BM_SC).toFixed(1); }
    function bmShape(view, key) {
      const axis = BM_ART[view].axis, list = BM_SHAPES[view][key] || [];
      let h = '';
      list.forEach(function(e){
        h += '<ellipse class="bm-hl bm-hl-f" cx="'+e[0]+'" cy="'+e[1]+'" rx="'+e[2]+'" ry="'+e[3]+'"'+(e[4]?' transform="rotate('+e[4]+' '+e[0]+' '+e[1]+')"':'')+'/>';
        if (e[5]) { const mx = 2*axis - e[0]; h += '<ellipse class="bm-hl bm-hl-f" cx="'+mx+'" cy="'+e[1]+'" rx="'+e[2]+'" ry="'+e[3]+'"'+(e[4]?' transform="rotate('+(-e[4])+' '+mx+' '+e[1]+')"':'')+'/>'; }
      });
      return h;
    }
    function bmBody(view) {
      const art = BM_ART[view];
      return '<image class="bm-art" href="'+art.src+'" x="'+BM_OX.toFixed(1)+'" y="'+BM_OY+'" width="'+(355*BM_SC).toFixed(1)+'" height="'+(869*BM_SC).toFixed(1)+'" preserveAspectRatio="xMidYMid meet" aria-hidden="true"/>';
    }
    function renderBodySilhouette(view) {
      const v = view === 'back' ? 'back' : 'front';
      const layout = BM_LAYOUT[v];
      let lines = '', zones = '', labels = '';
      Object.keys(layout).forEach(function(key){
        const z = BODY_MAP_ZONES[key], l = layout[key];
        if (!z) return;
        const on = selectedBodyZone === key;
        const px = l.side === 'L' ? 90 : 270, dx = bmX(l.dot[0]), dy = bmY(l.dot[1]);
        lines += '<path class="bm-line'+(on?' on':'')+'" d="M'+dx+' '+dy+' L'+px+' '+l.ly+'"/>';
        zones += '<g class="bm-zone'+(on?' on':'')+'" data-body-zone="'+escAttr(key)+'" role="button" tabindex="0" aria-pressed="'+(on?'true':'false')+'" aria-label="'+escAttr(z.label)+'">'
          + '<g transform="translate('+BM_OX.toFixed(2)+' '+BM_OY+') scale('+BM_SC.toFixed(5)+')">' + bmShape(v, l.shape) + '</g>'
          + '<circle class="bm-halo" cx="'+dx+'" cy="'+dy+'" r="'+(on?13:10)+'"/><circle class="bm-dot" cx="'+dx+'" cy="'+dy+'" r="5.5"/>'
          + '<circle class="bm-hit" cx="'+dx+'" cy="'+dy+'" r="22"/></g>';
        labels += '<button type="button" class="bm-label bm-'+l.side+(on?' on':'')+'" data-body-zone="'+escAttr(key)+'" style="top:'+(l.ly/540*100).toFixed(2)+'%" aria-pressed="'+(on?'true':'false')+'">'+(on?'<i aria-hidden="true">✓</i>':'')+'<span>'+esc(z.label)+'</span></button>';
      });
      return '<svg class="bm-svg" viewBox="0 0 360 540" role="group" aria-label="'+escAttr(LANG==='ar'?'خريطة الجسم':'Body map')+'" focusable="false">'
        + bmBody(v) + lines + zones + '</svg>' + labels;
    }
    function renderBodyZoneButtons() { return ''; }
    function renderBodyMapCard() {
      const viewFront = LANG === 'ar' ? 'أمام الجسم' : 'Front';
      const viewBack = LANG === 'ar' ? 'خلف الجسم' : 'Back';
      const title = LANG === 'ar' ? 'أين تشعر بالعرض؟' : 'Where do you feel it?';
      const sub = LANG === 'ar' ? 'اضغط على المكان الأقرب لما تشعر به، وبعدها سنعرض لك أوصافًا مناسبة لهذه المنطقة.' : 'Tap the closest area, then we will show symptom descriptions that fit that region.';
      const prompt = LANG === 'ar' ? 'اختر منطقة من الرسم' : 'Choose an area on the body';
      const resultsPrompt = LANG === 'ar' ? 'بعد اختيار المنطقة سيظهر هنا سؤال: «وش تحس في هذا المكان؟»' : 'After choosing an area, you will see: “What do you feel here?”';
      return '<div class="smart-body-card v221" id="smartBodyCard">'
        + '<div class="smart-body-copy"><b>'+esc(title)+'</b><p class="muted">'+esc(sub)+'</p></div>'
        + '<div class="smart-body-shell">'
        +   '<div class="smart-body-stage" id="smartBodyStage" data-view="'+escAttr(bodyMapView)+'">'
        +     '<div class="smart-body-toolbar"><span class="smart-body-hint">'+esc(prompt)+'</span><div class="smart-body-toggle"><button type="button" class="smart-toggle-btn'+(bodyMapView==='front'?' on':'')+'" data-body-view="front">'+esc(viewFront)+'</button><button type="button" class="smart-toggle-btn'+(bodyMapView==='back'?' on':'')+'" data-body-view="back">'+esc(viewBack)+'</button></div></div>'
        +     '<div class="bm-visual" data-body-visual="'+escAttr(bodyMapView)+'">'+renderBodySilhouette(bodyMapView)+renderBodyZoneButtons()+'</div>'
        +     '<small class="smart-body-visual-help">'+esc(LANG==='ar'?'اضغط على النقطة أو على اسم المنطقة.':'Tap a dot or an area name.')+'</small>'
        +     '<div class="smart-body-selection-note" aria-live="polite">'+esc(selectedBodyZone ? ((LANG==='ar'?'المنطقة المختارة: ':'Selected area: ')+bodyZoneLabel(selectedBodyZone)) : (LANG==='ar'?'لم تختر منطقة بعد':'No area selected yet'))+'</div>'
        +     '<div class="smart-body-selection-tray" data-body-selection-tray>'
        +       '<div class="smart-body-selection-tray-head"><b>'+esc(LANG==='ar'?'المنطقة المختارة':'Selected area')+'</b><span data-body-selection-count>'+(selectedBodyZone?'(1)':'(0)')+'</span><button type="button" class="smart-body-clear" data-body-clear '+(selectedBodyZone?'':'disabled')+'>'+esc(LANG==='ar'?'مسح':'Clear')+'</button></div>'
        +       '<div class="smart-body-selection-chip '+(selectedBodyZone?'is-selected':'is-empty')+'" data-body-selection-chip>'+esc(selectedBodyZone ? bodyZoneLabel(selectedBodyZone) : (LANG==='ar'?'اختر منطقة من الجسم':'Choose an area'))+'</div>'
        +       '<button type="button" class="smart-body-next" data-body-next '+(selectedBodyZone?'':'disabled')+'>'+esc(LANG==='ar'?'التالي':'Next')+' <span aria-hidden="true">‹</span></button>'
        +     '</div>'
        +   '</div>'
        +   '<div class="smart-body-results" id="smartBodyResults"><div class="smart-body-empty">'+esc(resultsPrompt)+'</div></div>'
        + '</div>'
        + '</div>';
    }
    function bindBodyMapCard() {
      const host = document.getElementById('smartBodyCard');
      if (!host || host.dataset.bound === '1') return;
      host.dataset.bound = '1';
      host.addEventListener('keydown', function(e){
        if (e.key !== 'Enter' && e.key !== ' ') return;
        const z = e.target.closest && e.target.closest('g[data-body-zone]');
        if (z && host.contains(z)) { e.preventDefault(); showBodyZone(z.dataset.bodyZone, true); }
      });
      host.addEventListener('click', function(e){
        const viewBtn = e.target.closest('[data-body-view]');
        if (viewBtn && host.contains(viewBtn)) { setBodyMapView(viewBtn.dataset.bodyView); return; }
        const zoneBtn = e.target.closest('[data-body-zone]');
        if (zoneBtn && host.contains(zoneBtn)) { showBodyZone(zoneBtn.dataset.bodyZone, true); return; }
        const regionBtn = e.target.closest('[data-body-region]');
        if (regionBtn && host.contains(regionBtn)) { showBodyRegion(regionBtn.dataset.bodyRegion, true); return; }
        const refineBtn = e.target.closest('[data-body-refine-zone]');
        if (refineBtn && host.contains(refineBtn)) { showBodyZone(refineBtn.dataset.bodyRefineZone, true); return; }
        const symptomBtn = e.target.closest('[data-body-symptom]');
        if (symptomBtn && host.contains(symptomBtn)) { toggleBodyMapSymptom(symptomBtn.dataset.bodySymptom); return; }
        const clearBtn = e.target.closest('[data-body-clear]');
        if (clearBtn && host.contains(clearBtn) && !clearBtn.disabled) { selectedBodyZone=null; state.body_zone_primary=null; refreshBodyMapCard(); return; }
        const nextBtn = e.target.closest('[data-body-next]');
        if (nextBtn && host.contains(nextBtn) && !nextBtn.disabled && selectedBodyZone) { showBodyZone(selectedBodyZone, true); const box=document.getElementById('smartBodyResults'); if(box) box.scrollIntoView({behavior:'smooth',block:'nearest'}); return; }
        const otherBtn = e.target.closest('[data-body-other-submit]');
        if (otherBtn && host.contains(otherBtn)) {
          const input=host.querySelector('[data-body-other-input]');
          const value=String(input&&input.value||'').trim();
          const selectedRegion = selectedBodyZone && BODY_MAP_ZONES[selectedBodyZone] ? BODY_MAP_ZONES[selectedBodyZone].parent : state.body_region_primary;
          if(value){ extractSmartSymptoms(value, selectedRegion || null); }
        }
      });
    }
    function ensureBodyMapCard() {
      if (compactSymptomUI()) { showMobileBodyLauncher(); return; }
      const card = bodyEl.querySelector('.step-focus-card');
      if (!card) return;
      let disclosure = card.querySelector('#symptomBodyMapDisclosure');
      if (!disclosure) {
        disclosure = document.createElement('section');
        disclosure.id = 'symptomBodyMapDisclosure';
        disclosure.className = 'symptom-bodymap-disclosure symptom-bodymap-always-open';
        disclosure.innerHTML = '<div class="symptom-bodymap-header"><span class="symptom-bodymap-summary-icon">🧍</span><span class="symptom-bodymap-summary-copy"><b>'+esc(LANG==='ar'?'استخدام خريطة الجسم · حدد مكان العرض':'Use the body map · choose the symptom area')+'</b><small>'+esc(LANG==='ar'?'اختر المنطقة أولًا، ثم أضف العرض أو اكتبه بطريقتك. إذا اختلفت الخريطة عن وصفك سنسألك أيهما تقصد.':'Choose the area first, then add or describe the symptom. If the map and your description differ, we will ask which one you mean.')+'</small></span></div><div class="symptom-bodymap-inline"></div>';
        const entry = card.querySelector('.symptom-entry-card');
        if (entry) entry.insertAdjacentElement('afterend', disclosure); else card.appendChild(disclosure);
      }
      bodyMapOpen = true;
      const inline = disclosure.querySelector('.symptom-bodymap-inline');
      if (!inline) return;
      if (!inline.querySelector('#smartBodyCard')) inline.innerHTML = renderBodyMapCard();
      else refreshBodyMapCard();
      bindBodyMapCard();
      if (selectedBodyZone && BODY_MAP_ZONES[selectedBodyZone]) showBodyZone(selectedBodyZone, false);
      else if (state.body_region_primary) showBodyRegion(state.body_region_primary, false);
      if (state.body_region_needs_symptom) {
        let reminder = disclosure.querySelector('.body-region-specific-reminder');
        if (!reminder) {
          reminder = document.createElement('div');
          reminder.className = 'body-region-specific-reminder';
          disclosure.appendChild(reminder);
        }
        reminder.textContent = LANG==='ar'
          ? 'اختر عرضًا محددًا من ' + bodyRegionLabel(state.body_region_needs_symptom) + ' حتى نكمل تحليل المنطقتين.'
          : 'Choose a specific symptom from ' + bodyRegionLabel(state.body_region_needs_symptom) + ' so we can continue with both areas.';
      }
    }
    function refreshBodyMapCard() {
      const host = document.getElementById('smartBodyCard');
      if (!host) return;
      host.outerHTML = renderBodyMapCard();
      bindBodyMapCard();
      if (selectedBodyZone && BODY_MAP_ZONES[selectedBodyZone]) showBodyZone(selectedBodyZone, false);
      else if (state.body_region_primary) showBodyRegion(state.body_region_primary, false);
    }
    function setBodyMapView(view) {
      bodyMapView = view === 'back' ? 'back' : 'front';
      if (selectedBodyZone && BODY_MAP_ZONES[selectedBodyZone] && BODY_MAP_ZONES[selectedBodyZone].view !== bodyMapView) selectedBodyZone = null;
      refreshBodyMapCard();
    }
    function toggleBodyMapSymptom(symptom) {
      bodyMapOpen = true;
      const region = Object.keys(BODY_MAP_REGIONS).find(function(key){ return (BODY_MAP_REGIONS[key].symptoms||[]).includes(symptom); });
      if (region) setBodyRegionSelection(region, (state.body_regions||[]).length > 1);
      if (state.symptoms.includes(symptom)) state.symptoms = state.symptoms.filter(function(x){ return x !== symptom; });
      else state.symptoms.push(symptom);
      if (region) state.body_region_needs_symptom = hasSymptomForBodyRegion(region) ? null : region;
      if (compactSymptomUI()) {
        refreshBodyMapCard();
        if (selectedBodyZone && BODY_MAP_ZONES[selectedBodyZone]) showBodyZone(selectedBodyZone, false);
        else if (region) showBodyRegion(region, false);
        updateMobileSelectedSummary(); refreshMobileStartButton();
        return;
      }
      askSymptoms();
      if (region) showBodyRegion(region, false);
    }
    function showBodyZone(zoneKey, selectRegion) {
      const zone = BODY_MAP_ZONES[zoneKey];
      const box = document.getElementById('smartBodyResults');
      if (!zone || !box) return;
      selectedBodyZone = zoneKey;
      state.body_zone_primary = zoneKey;
      bodyMapView = zone.view;
      const visual = document.querySelector('[data-body-visual]');
      if (visual) visual.innerHTML = renderBodySilhouette(bodyMapView) + renderBodyZoneButtons();
      if (selectRegion !== false) {
        setBodyRegionSelection(zone.parent, false);
        if (compactSymptomUI()) state.body_region_needs_symptom = hasSymptomForBodyRegion(zone.parent) ? null : zone.parent;
      }
      const question = LANG === 'ar' ? 'ما الأعراض التي تشعر بها في هذه المنطقة؟' : 'What symptoms do you feel in this area?';
      const intro = LANG === 'ar' ? 'الأعراض الأكثر شيوعًا في هذه المنطقة:' : 'Common symptoms in this area:';
      const alreadyHasSymptom = hasSymptomForBodyRegion(zone.parent);
      let h = '<div class="smart-body-region-card v221"><div class="smart-body-region-head"><div><b>'+esc(zone.label)+'</b><small>'+esc(question)+'</small></div><span class="smart-body-selected-badge">✓ '+esc(LANG==='ar'?'تم تحديد المكان':'Area selected')+'</span></div>';
      if(alreadyHasSymptom) h += '<div class="smart-body-existing">✓ '+esc(LANG==='ar'?'عندك عرض مرتبط بهذه المنطقة محدد مسبقًا؛ لن نكرر عليك نفس السؤال. يمكنك إضافة عرض آخر فقط إذا احتجت.':'You already selected a symptom linked to this area, so we will not ask the same thing again. Add another only if needed.')+'</div>';
      h += '<div class="smart-body-zone-intro">'+esc(intro)+'</div><div class="smart-body-symptom-chips">';
      (zone.symptoms || []).forEach(function(symptom){
        const on = state.symptoms.includes(symptom);
        h += '<button type="button" class="smart-body-symptom'+(on?' on':'')+'" data-body-symptom="'+escAttr(symptom)+'">'+(on?'✓ ':'＋ ')+esc(symptom)+'</button>';
      });
      h += '</div><div class="smart-body-other"><b>'+esc(LANG==='ar'?'ما لقيت الوصف المناسب؟':'Not seeing the right description?')+'</b><small>'+esc(LANG==='ar'?'اكتب وش تحس في هذه المنطقة بطريقتك.':'Describe what you feel in this area in your own words.')+'</small><div><input type="text" data-body-other-input placeholder="'+escAttr(LANG==='ar'?'مثال: طقطقة مع ألم عند الحركة':'Example: clicking with pain on movement')+'"><button type="button" data-body-other-submit>'+esc(LANG==='ar'?'إضافة الوصف':'Add description')+'</button></div></div></div>';
      box.innerHTML = h;
      const stage = document.getElementById('smartBodyStage');
      if (stage) stage.querySelectorAll('[data-body-zone]').forEach(function(btn){ btn.classList.toggle('on', btn.dataset.bodyZone === zoneKey); });
      const selNote = document.querySelector('#smartBodyCard .smart-body-selection-note');
      if (selNote) selNote.textContent = (LANG==='ar'?'المنطقة المختارة: ':'Selected area: ') + zone.label;
      const selCount = document.querySelector('#smartBodyCard [data-body-selection-count]');
      if (selCount) selCount.textContent = '(1)';
      const selChip = document.querySelector('#smartBodyCard [data-body-selection-chip]');
      if (selChip) { selChip.textContent = zone.label; selChip.classList.add('is-selected'); selChip.classList.remove('is-empty'); }
      document.querySelectorAll('#smartBodyCard [data-body-clear],#smartBodyCard [data-body-next]').forEach(function(b){ b.disabled = false; });
      if (compactSymptomUI()) { updateMobileSelectedSummary(); refreshMobileStartButton(); }
    }
    function showBodyRegion(regionKey, selectRegion) {
      const region = BODY_MAP_REGIONS[regionKey];
      const box = document.getElementById('smartBodyResults');
      if (!region || !box) return;
      if (selectRegion !== false) {
        setBodyRegionSelection(regionKey, false);
        if (compactSymptomUI()) state.body_region_needs_symptom = hasSymptomForBodyRegion(regionKey) ? null : regionKey;
      }
      const intro = LANG === 'ar' ? 'الأعراض المرتبطة بهذه المنطقة:' : 'Symptoms often linked to this region:';
      const tip = LANG === 'ar' ? 'يمكنك الضغط على العرض لإضافته أو إزالته.' : 'Tap a symptom to add or remove it.';
      const selectedText = LANG === 'ar' ? 'المنطقة المحددة' : 'Selected area';
      const detailZones = regionDetailZones(regionKey);
      let h = '<div class="smart-body-region-card"><div class="smart-body-region-head"><div><b>'+esc(region.label)+'</b><small>'+esc(intro)+'</small></div><span class="smart-body-selected-badge">✓ '+esc(selectedText)+'</span></div>';
      if(detailZones.length>1){
        h += '<div class="smart-body-refine"><b>'+esc(LANG==='ar'?'حدد المكان بدقة أكثر (اختياري)':'Refine the exact area (optional)')+'</b><div>'+detailZones.slice(0,8).map(function(key){return '<button type="button" data-body-refine-zone="'+escAttr(key)+'">'+esc(BODY_MAP_ZONES[key].label)+'</button>';}).join('')+'</div></div>';
      }
      h += '<div class="smart-body-symptom-chips">';
      (region.symptoms || []).forEach(function(symptom){
        const on = state.symptoms.includes(symptom);
        h += '<button type="button" class="smart-body-symptom'+(on?' on':'')+'" data-body-symptom="'+escAttr(symptom)+'">'+(on?'✓ ':'＋ ')+esc(symptom)+'</button>';
      });
      h += '</div><small class="smart-body-tip">'+esc(tip)+'</small>'
        + '<div class="smart-body-other"><b>'+esc(LANG==='ar'?'ما لقيت عرضك؟':'Not seeing your symptom?')+'</b><small>'+esc(LANG==='ar'?'اكتب العرض أو الإحساس الذي تشعر به في هذه المنطقة بطريقتك.':'Describe the symptom or sensation you feel in this area in your own words.')+'</small><div><input type="text" data-body-other-input placeholder="'+escAttr(LANG==='ar'?'مثال: طقطقة، شد، حرقان أو ألم عند الحركة':'Example: clicking, tightness, burning, or pain with movement')+'"><button type="button" data-body-other-submit>'+esc(LANG==='ar'?'إضافة العرض':'Add symptom')+'</button></div></div></div>';
      box.innerHTML = h;
      const stage = document.getElementById('smartBodyStage');
      if (stage) {
        stage.querySelectorAll('.smart-body-part').forEach(function(btn){ btn.classList.toggle('on', btn.classList.contains(regionKey)); });
      }
      if (compactSymptomUI()) { updateMobileSelectedSummary(); refreshMobileStartButton(); }
    }
