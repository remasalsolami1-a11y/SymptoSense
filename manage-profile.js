// Profile editing uses DOM properties so user text is never parsed as HTML.
// Typed inputs: real date for date of birth, a select for gender, numeric inputs for height/weight. The same plausibility
// rules run on the server (services/profile_dashboard_service.py: validate_profile_field), so the checks here are only
// for fast feedback.
    var MANAGE_AR = (typeof LANG_M !== 'undefined' ? LANG_M : 'ar') === 'ar';
    var GENDER_OPTIONS = [
      ['', MANAGE_AR ? 'غير محدد' : 'Not set'],
      ['male', MANAGE_AR ? 'ذكر' : 'Male'],
      ['female', MANAGE_AR ? 'أنثى' : 'Female'],
      ['other', MANAGE_AR ? 'آخر' : 'Other'],
      ['prefer_not_to_say', MANAGE_AR ? 'أفضّل ألا أذكر' : 'Prefer not to say']
    ];
    var NUMBER_RULES = { height: { min: 30, max: 260, unit: 'cm' }, weight: { min: 2, max: 400, unit: 'kg' } };
    var MANAGE_ERRORS = {
      invalid_dob: ['تاريخ الميلاد غير صحيح', 'That date of birth is not valid'],
      dob_in_future: ['تاريخ الميلاد لا يمكن أن يكون في المستقبل', 'Date of birth cannot be in the future'],
      dob_out_of_range: ['تاريخ الميلاد غير منطقي', 'That date of birth is not plausible'],
      invalid_gender: ['اختر قيمة من القائمة', 'Choose a value from the list'],
      invalid_height: ['اكتب الطول بالأرقام (سم)', 'Enter height as a number (cm)'],
      height_out_of_range: ['الطول يجب أن يكون بين 30 و260 سم', 'Height must be between 30 and 260 cm'],
      invalid_weight: ['اكتب الوزن بالأرقام (كجم)', 'Enter weight as a number (kg)'],
      weight_out_of_range: ['الوزن يجب أن يكون بين 2 و400 كجم', 'Weight must be between 2 and 400 kg']
    };
    function manageErrorText(code) {
      var pair = MANAGE_ERRORS[code];
      if (pair) return MANAGE_AR ? pair[0] : pair[1];
      if (/_too_long$/.test(code || '')) return MANAGE_AR ? 'النص أطول من المسموح' : 'That text is too long';
      return MANAGE_AR ? 'تعذّر الحفظ، تحقق من القيمة' : 'Could not save, please check the value';
    }
    function manageValidate(key, value) {
      var v = String(value || '').trim();
      if (!v) return '';
      if (key === 'dob') {
        var d = new Date(v + 'T00:00:00');
        if (isNaN(d.getTime())) return 'invalid_dob';
        if (d.getTime() > Date.now()) return 'dob_in_future';
        if ((Date.now() - d.getTime()) / 31557600000 > 120) return 'dob_out_of_range';
      } else if (NUMBER_RULES[key]) {
        var n = parseFloat(v.replace(',', '.'));
        if (isNaN(n)) return 'invalid_' + key;
        if (n < NUMBER_RULES[key].min || n > NUMBER_RULES[key].max) return key + '_out_of_range';
      }
      return '';
    }
    function buildEditor(key, current) {
      var input;
      if (key === 'gender') {
        input = document.createElement('select');
        GENDER_OPTIONS.forEach(function(opt){
          var o = document.createElement('option'); o.value = opt[0]; o.textContent = opt[1]; input.appendChild(o);
        });
        input.value = current;
      } else if (key === 'dob') {
        input = document.createElement('input'); input.type = 'date'; input.value = current;
        input.max = new Date().toISOString().slice(0, 10); input.min = '1900-01-01';
      } else if (NUMBER_RULES[key]) {
        input = document.createElement('input'); input.type = 'number'; input.inputMode = 'decimal'; input.step = '0.1';
        input.min = NUMBER_RULES[key].min; input.max = NUMBER_RULES[key].max; input.value = current;
        input.setAttribute('aria-label', NUMBER_RULES[key].unit);
      } else {
        input = document.createElement('input'); input.type = 'text'; input.value = current;
        input.maxLength = key === 'display_name' ? 80 : 1000;
      }
      input.id = 'edit_' + key;
      input.style.cssText = 'width:100%;min-height:44px;padding:10px;border:2px solid #1565c0;border-radius:10px;font-size:16px;margin:4px 0;';
      return input;
    }
    function editField(key) {
      var valEl = document.getElementById('val_' + key);
      var current = valEl.dataset.raw !== undefined ? valEl.dataset.raw : valEl.textContent.trim();
      if (current === (LANG_M==='ar' ? 'غير محدد' : 'Not set')) current = '';
      valEl.dataset.original = valEl.textContent.trim();
      valEl.textContent = '';
      var input = buildEditor(key, current);
      var err = document.createElement('div');
      err.id = 'err_' + key; if (err.setAttribute) err.setAttribute('role', 'alert');
      err.style.cssText = 'color:#B91C1C;font-size:13px;margin-top:4px;order:1;';
      var controls = document.createElement('div');
      controls.style.cssText = 'display:flex;gap:8px;margin-top:8px;order:2;';
      var save = document.createElement('button');
      save.type = 'button'; save.textContent = '✅ ' + (LANG_M==='ar' ? 'حفظ' : 'Save');
      save.style.cssText = 'flex:1;min-height:44px;padding:10px;background:#1565c0;color:#fff;border:none;border-radius:10px;font-weight:700;cursor:pointer;';
      save.addEventListener('click', function(){ saveField(key); });
      var cancel = document.createElement('button');
      cancel.type = 'button'; cancel.textContent = '✕ ' + (LANG_M==='ar' ? 'إلغاء' : 'Cancel');
      cancel.style.cssText = 'flex:1;min-height:44px;padding:10px;background:#EAF4FF;color:#123B70;border:1px solid #DCEBFA;border-radius:10px;font-weight:600;cursor:pointer;';
      cancel.addEventListener('click', function(){ cancelEdit(key); });
      controls.appendChild(save); controls.appendChild(cancel);
      valEl.style.display = 'flex'; valEl.style.flexDirection = 'column';
      valEl.appendChild(input); valEl.appendChild(controls); valEl.appendChild(err); input.focus();
    }
