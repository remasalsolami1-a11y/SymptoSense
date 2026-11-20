/* SymptoSense chat — Symptom questions: input chooser, duration/severity/history steps, symptom path, ambiguity. (Body map -> body-map.js; clarification banks -> clarifications.js.)
   Classic script: shares the page's global scope with the other files in /static/js/chat/. Load order is fixed by chat_view.py. */
    const BODY_MAP_REGIONS = LANG === 'ar' ? {
      head:{label:'الرأس', symptoms:['🤕 صداع','💫 دوار','👁️ احمرار العيون','🧠 تشوش أو ارتباك']},
      throat:{label:'الحلق', symptoms:['😣 ألم الحلق','😷 سعال']},
      chest:{label:'الصدر', symptoms:['🫀 ألم في الصدر','💓 خفقان القلب','🫁 ضيق التنفس']},
      abdomen:{label:'البطن', symptoms:['😖 ألم في البطن','🤢 غثيان','🤮 قيء','🚽 إسهال']},
      arms:{label:'الذراعان', symptoms:['🦴 ألم المفاصل','🖐️ تنميل أو خدر','🖐️ حكة']},
      legs:{label:'الساقان', symptoms:['🦵 ألم في الرجل','🦴 ألم المفاصل','🖐️ تنميل أو خدر']},
      skin:{label:'الجلد والجسم', symptoms:['🩹 طفح جلدي','🖐️ حكة','🥶 قشعريرة','😴 تعب وإرهاق']},
      back:{label:'الظهر والجسم', symptoms:['😴 تعب وإرهاق','🥶 قشعريرة','🦴 ألم المفاصل']}
    } : {
      head:{label:'Head', symptoms:['🤕 Headache','💫 Dizziness','👁️ Eye redness','🧠 Confusion']},
      throat:{label:'Throat', symptoms:['😣 Sore throat','😷 Cough']},
      chest:{label:'Chest', symptoms:['🫀 Chest pain','💓 Heart palpitations','🫁 Shortness of breath']},
      abdomen:{label:'Abdomen', symptoms:['😖 Stomach pain','🤢 Nausea','🤮 Vomiting','🚽 Diarrhea']},
      arms:{label:'Arms', symptoms:['🦴 Joint pain','🖐️ Numbness or tingling','🖐️ Itching']},
      legs:{label:'Legs', symptoms:['🦵 Leg pain','🦴 Joint pain','🖐️ Numbness or tingling']},
      skin:{label:'Skin & whole body', symptoms:['🩹 Skin rash','🖐️ Itching','🥶 Chills','😴 Fatigue']},
      back:{label:'Back & whole body', symptoms:['😴 Fatigue','🥶 Chills','🦴 Joint pain']}
    };
    // V221: visual body zones are intentionally separate from the medical
    // region model above. The UI can be specific (e.g. knee / upper abdomen)
    // without changing the backend eligibility or safety semantics.
    const BODY_MAP_FRONT_STATIC = '/static/images/body-map-front-v241.png';
    const BODY_MAP_ZONES = LANG === 'ar' ? {
      head_front:{label:'الرأس والوجه',parent:'head',view:'front',x:50,y:10,symptoms:['🤕 صداع','💫 دوار','👁️ احمرار العيون','🧠 تشوش أو ارتباك']},
      neck_front:{label:'الرقبة والحلق',parent:'throat',view:'front',x:50,y:21,symptoms:['😣 ألم الحلق','😷 سعال','🖐️ تنميل أو خدر']},
      chest_front:{label:'الصدر',parent:'chest',view:'front',x:50,y:33,symptoms:['🫀 ألم في الصدر','💓 خفقان القلب','🫁 ضيق التنفس','😷 سعال']},
      upper_abdomen:{label:'أعلى البطن',parent:'abdomen',view:'front',x:50,y:45,symptoms:['😖 ألم في البطن','🤢 غثيان','🤮 قيء']},
      lower_abdomen:{label:'أسفل البطن',parent:'abdomen',view:'front',x:50,y:55,symptoms:['😖 ألم في البطن','🤢 غثيان','🚽 إسهال']},
      arms_front:{label:'الكتف والذراع',parent:'arms',view:'front',x:23,y:37,symptoms:['🦴 ألم المفاصل','🖐️ تنميل أو خدر','🖐️ حكة']},
      hands_front:{label:'اليد والأصابع',parent:'arms',view:'front',x:15,y:57,symptoms:['🖐️ تنميل أو خدر','🖐️ حكة','🦴 ألم المفاصل']},
      thigh_front:{label:'الفخذ',parent:'legs',view:'front',x:39,y:68,symptoms:['🦵 ألم في الرجل','🦴 ألم المفاصل','🖐️ تنميل أو خدر']},
      knee_front:{label:'الركبة',parent:'legs',view:'front',x:40,y:80,symptoms:['🦴 ألم المفاصل','🦵 ألم في الرجل']},
      lower_leg_front:{label:'الساق',parent:'legs',view:'front',x:40,y:89,symptoms:['🦵 ألم في الرجل','🖐️ تنميل أو خدر']},
      foot_front:{label:'القدم والكاحل',parent:'legs',view:'front',x:40,y:97,symptoms:['🦵 ألم في الرجل','🦴 ألم المفاصل','🖐️ تنميل أو خدر']},
      head_back:{label:'خلف الرأس',parent:'head',view:'back',x:50,y:10,symptoms:['🤕 صداع','💫 دوار']},
      neck_back:{label:'الرقبة',parent:'back',view:'back',x:50,y:22,symptoms:['🦴 ألم المفاصل','🖐️ تنميل أو خدر']},
      upper_back:{label:'أعلى الظهر والكتف',parent:'back',view:'back',x:50,y:34,symptoms:['🦴 ألم المفاصل','🖐️ تنميل أو خدر']},
      lower_back:{label:'أسفل الظهر',parent:'back',view:'back',x:50,y:52,symptoms:['🦴 ألم المفاصل','🖐️ تنميل أو خدر','🦵 ألم في الرجل']},
      arms_back:{label:'خلف الذراع',parent:'arms',view:'back',x:23,y:39,symptoms:['🦴 ألم المفاصل','🖐️ تنميل أو خدر']},
      thigh_back:{label:'خلف الفخذ',parent:'legs',view:'back',x:39,y:69,symptoms:['🦵 ألم في الرجل','🖐️ تنميل أو خدر']},
      knee_back:{label:'خلف الركبة',parent:'legs',view:'back',x:40,y:81,symptoms:['🦴 ألم المفاصل','🦵 ألم في الرجل']},
      calf_back:{label:'بطة الساق',parent:'legs',view:'back',x:40,y:90,symptoms:['🦵 ألم في الرجل','🖐️ تنميل أو خدر']},
      foot_back:{label:'الكعب والقدم',parent:'legs',view:'back',x:40,y:97,symptoms:['🦵 ألم في الرجل','🦴 ألم المفاصل']}
    } : {
      head_front:{label:'Head & face',parent:'head',view:'front',x:50,y:10,symptoms:['🤕 Headache','💫 Dizziness','👁️ Eye redness','🧠 Confusion']},
      neck_front:{label:'Neck & throat',parent:'throat',view:'front',x:50,y:21,symptoms:['😣 Sore throat','😷 Cough','🖐️ Numbness or tingling']},
      chest_front:{label:'Chest',parent:'chest',view:'front',x:50,y:33,symptoms:['🫀 Chest pain','💓 Heart palpitations','🫁 Shortness of breath','😷 Cough']},
      upper_abdomen:{label:'Upper abdomen',parent:'abdomen',view:'front',x:50,y:45,symptoms:['😖 Stomach pain','🤢 Nausea','🤮 Vomiting']},
      lower_abdomen:{label:'Lower abdomen',parent:'abdomen',view:'front',x:50,y:55,symptoms:['😖 Stomach pain','🤢 Nausea','🚽 Diarrhea']},
      arms_front:{label:'Shoulder & arm',parent:'arms',view:'front',x:23,y:37,symptoms:['🦴 Joint pain','🖐️ Numbness or tingling','🖐️ Itching']},
      hands_front:{label:'Hand & fingers',parent:'arms',view:'front',x:15,y:57,symptoms:['🖐️ Numbness or tingling','🖐️ Itching','🦴 Joint pain']},
      thigh_front:{label:'Thigh',parent:'legs',view:'front',x:39,y:68,symptoms:['🦵 Leg pain','🦴 Joint pain','🖐️ Numbness or tingling']},
      knee_front:{label:'Knee',parent:'legs',view:'front',x:40,y:80,symptoms:['🦴 Joint pain','🦵 Leg pain']},
      lower_leg_front:{label:'Lower leg',parent:'legs',view:'front',x:40,y:89,symptoms:['🦵 Leg pain','🖐️ Numbness or tingling']},
      foot_front:{label:'Foot & ankle',parent:'legs',view:'front',x:40,y:97,symptoms:['🦵 Leg pain','🦴 Joint pain','🖐️ Numbness or tingling']},
      head_back:{label:'Back of head',parent:'head',view:'back',x:50,y:10,symptoms:['🤕 Headache','💫 Dizziness']},
      neck_back:{label:'Neck',parent:'back',view:'back',x:50,y:22,symptoms:['🦴 Joint pain','🖐️ Numbness or tingling']},
      upper_back:{label:'Upper back & shoulder',parent:'back',view:'back',x:50,y:34,symptoms:['🦴 Joint pain','🖐️ Numbness or tingling']},
      lower_back:{label:'Lower back',parent:'back',view:'back',x:50,y:52,symptoms:['🦴 Joint pain','🖐️ Numbness or tingling','🦵 Leg pain']},
      arms_back:{label:'Back of arm',parent:'arms',view:'back',x:23,y:39,symptoms:['🦴 Joint pain','🖐️ Numbness or tingling']},
      thigh_back:{label:'Back of thigh',parent:'legs',view:'back',x:39,y:69,symptoms:['🦵 Leg pain','🖐️ Numbness or tingling']},
      knee_back:{label:'Back of knee',parent:'legs',view:'back',x:40,y:81,symptoms:['🦴 Joint pain','🦵 Leg pain']},
      calf_back:{label:'Calf',parent:'legs',view:'back',x:40,y:90,symptoms:['🦵 Leg pain','🖐️ Numbness or tingling']},
      foot_back:{label:'Heel & foot',parent:'legs',view:'back',x:40,y:97,symptoms:['🦵 Leg pain','🦴 Joint pain']}
    };
    function compactSymptomUI(){ return true; }
 // V245: one unified symptom UI on every device
    const CLAR = [
      {syms:['🖐️ تنميل أو خدر','🖐️ Numbness or tingling','تنميل أو خدر','Numbness or tingling','تنميل','خدر','Numbness'],
       node:{q:['هل بدأ التنميل فجأة في جهة واحدة من الوجه أو الذراع أو الساق؟','Did the numbness start suddenly on one side of the face, arm, or leg?'],
         yes:{safety:['تنميل مفاجئ في جهة واحدة — يحتاج تقييمًا طارئاً','Sudden one-sided numbness — needs emergency assessment']},
         no:{options:[
           {label:['في اليدين أو الأصابع','Hands or fingers'],add:['تنميل اليدين أو الأصابع','Hand or finger numbness']},
           {label:['في القدمين أو أصابع القدم','Feet or toes'],add:['تنميل القدمين أو أصابع القدم','Foot or toe numbness']},
           {label:['في الوجه، وليس بشكل مفاجئ','Face, not sudden'],add:['تنميل الوجه','Facial numbness']},
           {label:['في أكثر من مكان أو في الجهتين','Several areas or both sides'],add:['تنميل في أكثر من مكان','Numbness in multiple areas']},
           {label:['في مكان آخر — سأكتبه','Another area — I will type it'],custom:true}
         ]}}},
      {syms:['😵 إغماء أو فقدان وعي','😵 Fainting or loss of consciousness','إغماء','اغماء','فقدان الوعي','غشيان','Fainting','Syncope','Loss of consciousness'],
       node:{prompt:['لما تقول إغماء، أي وصف أقرب لما حدث؟','When you say fainting, which description is closer to what happened?'],options:[
         {label:['فقدت الوعي فعلًا ولو لثوانٍ','I actually lost consciousness, even briefly'],location:false,
          add:[],note:['حدث فقدان وعي فعلي.','Actual loss of consciousness occurred.'],
          next:{q:['هل استعدت وعيك بالكامل خلال أقل من دقيقة؟','Did you fully regain consciousness within about a minute?'],
            yes:{q:['هل صاحب الإغماء ألم صدر، خفقان قوي أو غير منتظم، ضيق تنفس، صعوبة في الكلام أو الحركة، تشنج، أو إصابة شديدة؟','Was the faint accompanied by chest pain, strong or irregular palpitations, shortness of breath, trouble speaking or moving, a seizure, or a serious injury?'],
              yes:{safety:['إغماء مع علامة خطر مصاحبة — يحتاج تقييمًا عاجلًا','Fainting with an associated red flag — needs urgent assessment']},
              no:{q:['هل حدث الإغماء أثناء الرياضة أو وأنت مستلقٍ؟','Did the fainting happen during exercise or while you were lying down?'],
                yes:{safety:['إغماء أثناء المجهود أو أثناء الاستلقاء — يحتاج تقييمًا عاجلًا','Fainting during exertion or while lying down — needs urgent assessment']},
                no:{end:true}}},
            no:{safety:['عدم استعادة الوعي سريعًا بعد الإغماء — يحتاج مساعدة عاجلة','Not regaining consciousness quickly after fainting — needs urgent help']}
          }
         },
         {label:['شعرت أني سأُغمى علي لكن لم أفقد الوعي','I felt like I might faint but did not lose consciousness'],location:false,
          remove:['😵 إغماء أو فقدان وعي','😵 Fainting or loss of consciousness','إغماء','اغماء','فقدان الوعي','غشيان','Fainting','Syncope','Loss of consciousness'],
          add:['قرب الإغماء أو خفة شديدة بالرأس','Near-fainting or severe lightheadedness'],note:['شعور بقرب الإغماء دون فقدان وعي.','Near-fainting without loss of consciousness.'],
          next:{q:['هل يصاحب ذلك ألم صدر، ضيق تنفس، خفقان مستمر، ضعف أو خدر مفاجئ، تشوش شديد، أو صداع مفاجئ شديد؟','Does it come with chest pain, shortness of breath, persistent palpitations, sudden weakness or numbness, severe confusion, or a sudden severe headache?'],
            yes:{safety:['قرب الإغماء مع علامة خطر مصاحبة — يحتاج تقييمًا عاجلًا','Near-fainting with an associated red flag — needs urgent assessment']},
            no:{end:true}}
         }
       ]}},
      {syms:['💓 خفقان القلب','💓 Heart palpitations','خفقان','خفقان القلب','تسارع دقات القلب','Heart palpitations','Palpitations','Racing heart'],
       node:{q:['هل الخفقان موجود الآن ولا يختفي، أو يصاحبه ألم صدر أو ضيق تنفس أو إغماء؟','Are the palpitations happening now and not settling, or accompanied by chest pain, shortness of breath, or fainting?'],
         yes:{safety:['خفقان مستمر مع علامة خطر مصاحبة','Persistent palpitations with an associated red flag']},
         no:{q:['هل يتكرر الخفقان كثيرًا أو يستمر أكثر من عدة دقائق؟','Do the palpitations keep recurring or last more than a few minutes?'],yes:{end:true},no:{end:true}}}},
      {syms:['🤮 قيء','🤮 Vomiting','قيء','استفراغ','تقيؤ','ترجيع','Vomiting'],
       node:{q:['هل يوجد دم في القيء، أو لون أخضر واضح، أو ألم بطن مفاجئ وشديد جدًا؟','Is there blood in the vomit, clearly green vomit, or sudden very severe abdominal pain?'],
         yes:{safety:['قيء مع علامة خطر تحتاج تقييمًا عاجلًا','Vomiting with a red flag requiring urgent assessment']},
         no:{q:['هل يتكرر القيء لدرجة أنك لا تستطيع الاحتفاظ بالسوائل؟','Is the vomiting repeated enough that you cannot keep fluids down?'],yes:{end:true},no:{end:true}}}},
      {syms:['🚽 إسهال','🚽 Diarrhea','إسهال','اسهال','Diarrhea','Diarrhoea'],
       node:{q:['هل يوجد دم واضح أو براز أسود، أو ألم شديد جدًا في البطن، أو علامات جفاف شديدة؟','Is there visible blood or black stool, very severe abdominal pain, or severe dehydration?'],
         yes:{q:['هل يوجد أيضًا إغماء أو تشوش شديد أو صعوبة في التنفس؟','Is there also fainting, severe confusion, or breathing difficulty?'],yes:{safety:['إسهال مع علامات خطر شديدة','Diarrhea with severe red flags']},no:{end:true}},no:{end:true}}},
      {syms:['🩹 طفح جلدي','🩹 Skin rash','طفح جلدي','طفح','Rash','Skin rash'],
       node:{q:['هل يصاحب الطفح صعوبة تنفس أو تورم في الشفاه أو اللسان أو الحلق؟','Does the rash come with trouble breathing or swelling of the lips, tongue, or throat?'],
         yes:{safety:['طفح مع صعوبة تنفس أو تورم بالفم أو الحلق','Rash with breathing difficulty or mouth/throat swelling']},
         no:{q:['هل الطفح أرجواني أو أحمر داكن ولا يبهت عند الضغط عليه، خصوصًا مع حرارة أو شعور شديد بالمرض؟','Is the rash purple or dark red and does not fade when pressed, especially with fever or feeling very unwell?'],yes:{safety:['طفح لا يبهت بالضغط مع أعراض مقلقة','Non-blanching rash with concerning symptoms']},no:{end:true}}}},
      {syms:['🔥 حرقة أو ألم عند التبول','🔥 Pain or burning when urinating','حرقة البول','حرقة بول','حرقان البول','حرقان بول','ألم عند التبول','Painful urination','Burning urination','Dysuria'],
       node:{q:['هل توجد حرارة أو قشعريرة أو ألم في الخاصرة أو الظهر تحت الأضلاع؟','Do you have fever, chills, or pain in the side/back under the ribs?'],yes:{end:true},no:{q:['هل يوجد دم في البول أو صعوبة شديدة في التبول؟','Is there blood in the urine or major difficulty passing urine?'],yes:{end:true},no:{end:true}}}},
      {syms:['🧠 تشوش أو ارتباك','🧠 Confusion','تشوش','ارتباك','تغير الوعي','Confusion','Disorientation'],
       node:{q:['هل التشوش جديد وبدأ فجأة أو يزداد بسرعة؟','Is the confusion new, sudden, or rapidly worsening?'],yes:{safety:['تشوش أو تغير وعي مفاجئ — يحتاج تقييمًا عاجلًا','Sudden confusion or altered awareness — needs urgent assessment']},no:{end:true}}},
      {syms:['⚡ نوبة تشنج','⚡ Seizure','نوبة تشنج','تشنج','اختلاج','Seizure','Convulsion'],
       node:{q:['هل النوبة مستمرة الآن، تكررت دون استعادة الوعي بالكامل، أو لم تستعد وعيك طبيعيًا بعدها؟','Is the seizure ongoing, repeating without full recovery, or have you not returned to normal awareness afterward?'],yes:{safety:['نوبة تشنج مستمرة أو دون تعافٍ كامل — تحتاج مساعدة عاجلة','Ongoing/repeated seizure or incomplete recovery — needs urgent help']},no:{end:true}}},
      {syms:['🫀 ألم في الصدر','🫀 Chest pain','ألم الصدر','Chest pain'],
       node:{q:['هل بدأ ألم الصدر فجأة أو هو شديد الآن؟','Did the chest pain start suddenly, or is it severe now?'],
         yes:{safety:['ألم صدر مفاجئ أو شديد — يحتاج تقييمًا عاجلًا','Sudden or severe chest pain — needs urgent assessment']},
         no:{q:['هل يصاحب الألم ضيق تنفس أو تعرّق بارد أو دوخة شديدة؟','Does it come with breathlessness, cold sweating, or severe dizziness?'],yes:{safety:['ألم الصدر مع أعراض مصاحبة مقلقة','Chest pain with concerning associated symptoms']},no:{end:true}}}},
      {syms:['🤢 غثيان','🤢 Nausea','غثيان','Nausea'],
       node:{q:['هل يوجد قيء متكرر أو لا تستطيع الاحتفاظ بالسوائل؟','Are you vomiting repeatedly or unable to keep fluids down?'],
         yes:{q:['هل يوجد دم في القيء أو ألم شديد جدًا في البطن؟','Is there blood in the vomit or very severe abdominal pain?'],yes:{safety:['قيء مع دم أو ألم بطن شديد جدًا','Vomiting blood or very severe abdominal pain']},no:{end:true}},
         no:{q:['هل بدأ الغثيان بعد طعام معين أو دواء جديد؟','Did the nausea begin after a particular food or a new medicine?'],yes:{end:true},no:{end:true}}}},
      {syms:['😴 تعب وإرهاق','😴 Fatigue','تعب وإرهاق','Fatigue'],
       node:{q:['هل التعب شديد ومفاجئ أو يصاحبه إغماء أو ضيق تنفس؟','Is the fatigue sudden and severe, or accompanied by fainting or breathlessness?'],
         yes:{safety:['تعب شديد مفاجئ مع علامة مقلقة','Sudden severe fatigue with a concerning sign']},
         no:{q:['هل يستمر التعب رغم النوم والراحة؟','Does the fatigue continue despite sleep and rest?'],yes:{end:true},no:{end:true}}}},
      {syms:['🦴 ألم المفاصل','🦴 Joint pain','ألم المفاصل','Joint pain'],
       node:{q:['هل المفصل متورم أو أحمر أو ساخن؟','Is the joint swollen, red, or hot?'],
         yes:{q:['هل يصاحب ذلك حمى أو عدم القدرة على تحريك المفصل؟','Is there fever or inability to move the joint?'],yes:{safety:['مفصل ساخن أو متورم مع حمى أو صعوبة حركة','Hot or swollen joint with fever or inability to move it']},no:{end:true}},
         no:{q:['هل بدأ الألم بعد إصابة أو مجهود واضح؟','Did the pain start after an injury or clear physical strain?'],yes:{end:true},no:{end:true}}}},
      {syms:['🥶 قشعريرة','🥶 Chills','قشعريرة','Chills'],
       node:{q:['هل توجد حمى مقاسة أو شعور واضح بارتفاع الحرارة؟','Do you have a measured fever or clearly feel feverish?'],
         yes:{q:['هل يصاحبها ضيق تنفس أو تشوش أو تيبس في الرقبة؟','Is there breathlessness, confusion, or neck stiffness?'],yes:{safety:['قشعريرة وحمى مع علامة خطر','Chills and fever with a red flag']},no:{end:true}},
         no:{q:['هل القشعريرة مستمرة أو تتكرر؟','Are the chills persistent or recurring?'],yes:{end:true},no:{end:true}}}},
      {syms:['🖐️ حكة','🖐️ Itching','حكة','Itching'],
       node:{q:['هل توجد صعوبة تنفس أو تورم في الشفاه أو اللسان أو الحلق؟','Is there trouble breathing or swelling of the lips, tongue, or throat?'],
         yes:{safety:['حكة مع صعوبة تنفس أو تورم بالفم أو الحلق','Itching with breathing difficulty or mouth/throat swelling']},
         no:{prompt:['أين تظهر الحكة؟','Where is the itching?'],options:[
           {label:['في مكان محدد','One specific area']},{label:['في أكثر من مكان','Several areas']},
           {label:['منتشرة في معظم الجسم','Across most of the body']},{label:['مكان آخر — سأكتبه','Another area — I will type it'],custom:true}
         ]}}},
      {syms:['👁️ احمرار العيون','👁️ Eye redness','احمرار العين','Eye redness'],
       node:{q:['هل تشعر بألم في العين؟','Do you feel pain in the eye?'],
         yes:{q:['هل الألم شديد؟','Is the pain severe?'],
           yes:{safety:['ألم شديد في العين مع احمرار','Severe eye pain with redness']},
           no:{q:['هل لديك إفرازات من العين؟','Do you have eye discharge?'],yes:{end:true},no:{end:true}}},
         no:{q:['هل لديك حكة في العين؟','Do you have itching in the eye?'],yes:{end:true},no:{end:true}}}},
      {syms:['🤕 صداع','🤕 Headache','صداع','Headache'],
       node:{q:['هل بدأ الصداع بشكل مفاجئ وشديد جدًا؟','Did the headache start suddenly and very severely?'],
         yes:{safety:['صداع مفاجئ وشديد — يحتاج تقييمًا عاجلًا','Sudden severe headache — needs urgent evaluation']},
         no:{q:['هل لديك حرارة؟','Do you have a fever?'],
           yes:{q:['هل لديك تيبس في الرقبة؟','Do you have neck stiffness?'],
             yes:{safety:['حرارة مع تيبس الرقبة — يحتاج تقييمًا عاجلًا','Fever with neck stiffness — needs urgent evaluation']},
             no:{end:true}},
           no:{end:true}}}},
      {syms:['🤒 حمى','🤒 Fever','حمى','Fever'],
       node:{q:['هل لديك تيبس في الرقبة؟','Do you have neck stiffness?'],
         yes:{safety:['حرارة مع تيبس الرقبة','Fever with neck stiffness']},
         no:{q:['هل تشعر بصعوبة في التنفس؟','Do you have difficulty breathing?'],
           yes:{safety:['حرارة مع صعوبة تنفس','Fever with difficulty breathing']},
           no:{end:true}}}},
      {syms:['😷 سعال','😷 Cough','سعال','Cough'],
       node:{q:['هل يوجد دم مع السعال؟','Is there blood with the cough?'],
         yes:{safety:['سعال مصحوب بدم','Cough with blood']},
         no:{q:['هل تعاني من ضيق تنفس مع السعال؟','Do you have shortness of breath with the cough?'],
           yes:{safety:['سعال مع ضيق تنفس','Cough with shortness of breath']},
           no:{end:true}}}},
      {syms:['💫 دوار','💫 Dizziness','دوخة','Dizziness'],
       node:{q:['هل فقدت الوعي أو شعرت بالإغماء؟','Did you lose consciousness or feel like fainting?'],
         yes:{safety:['دوار مع إغماء','Dizziness with fainting']},
         no:{end:true}}},
      {syms:['🫁 ضيق التنفس','🫁 Shortness of breath','ضيق التنفس','Shortness of breath'],
       node:{q:['هل يزداد ضيق التنفس عند الاستلقاء؟','Does the breathlessness worsen when lying down?'],
         yes:{safety:['ضيق تنفس يزداد عند الاستلقاء','Breathlessness that worsens when lying down']},
         no:{end:true}}},
      {syms:['🦵 ألم في الرجل','🦵 Leg pain','ألم الرجل أو الساق','Leg pain'],
       node:{q:['هل هناك تورم أو حرارة في الساق؟','Is there swelling or warmth in the leg?'],
         yes:{safety:['تورم أو حرارة في الساق مع ألم','Swelling or warmth in the leg with pain']},
         no:{end:true}}},
      {syms:['😖 ألم في البطن','😖 Stomach pain','ألم البطن','Abdominal pain'],
       node:{q:['هل الألم شديد جدًا؟','Is the pain very severe?'],
         yes:{q:['هل يمنعك الألم من الوقوف أو الحركة؟','Does the pain stop you from standing or moving?'],
           yes:{safety:['ألم بطن شديد يمنع الحركة','Severe stomach pain preventing movement']},
           no:{end:true}},
         no:{end:true}}},
      {syms:['😣 ألم الحلق','😣 Sore throat','ألم الحلق','Sore throat'],
       node:{q:['هل تجد صعوبة في البلع أو التنفس؟','Do you have trouble swallowing or breathing?'],
         yes:{safety:['صعوبة بلع أو تنفس مع ألم حلق','Difficulty swallowing or breathing with sore throat']},
         no:{end:true}}},
    ];
    function offerAssessmentMode(continueFn) {
      addHtml('<div class="ss-mode-card"><div class="ss-mode-icon">⚡</div><div><b>'+esc(LANG==='ar'?'كيف تبي التحليل؟':'How would you like to assess your symptoms?')+'</b><p>'+esc(LANG==='ar'?'اختر المسار المناسب الآن. المسار السريع يركز على علامات الخطر والخطوة التالية، ويمكنك إكمال التفاصيل لاحقًا.':'Choose the path that fits right now. Quick mode focuses on safety and the next step, and you can add the full details later.')+'</p></div></div>','bot');
      showOpts([
        {label:'🩺 '+(LANG==='ar'?'تحليل كامل':'Full assessment'),fn:function(){state.quick_mode=false;highestFlowStep=1;trackJourney('full_start');clearOpts();continueFn();}},
        {label:'⚡ '+(LANG==='ar'?'أنا مستعجل · مسار سريع':'I’m in a hurry · Quick mode'),fn:function(){state.quick_mode=true;highestFlowStep=1;trackJourney('quick_start');clearOpts();addHtml('<div class="ss-quick-note"><b>'+esc(LANG==='ar'?'المسار السريع مفعّل':'Quick mode is on')+'</b><span>'+esc(LANG==='ar'?'سنأخذ المعلومات الأساسية وأسئلة الأمان فقط. إذا كانت النتيجة غير طارئة يمكنك الانتقال للتحليل الكامل من النتيجة نفسها.':'We’ll ask only the essentials and safety questions. If the result is not urgent, you can continue into the full assessment from the result.')+'</span></div>','bot');continueFn();}}
      ]);
    }
    const SMART_FOLLOWUP_MAX = 5;
    const FOLLOWUP_TOTAL_MAX = 7;
    let differentialAsked = [], differentialNegatives = [], differentialCount = 0, differentialCandidates = [], differentialAnswers = [], differentialLastAnswer = null;
    async function startClarify() {
      // Red Flag Bypass: run the narrow deterministic safety engine before
      // ordinary clarification/differential questions. A matching emergency
      // signal stops the normal flow immediately.
      state.step = 'clarification';
      clearOpts();
      focusStepQuestion('🛡️ ' + (LANG==='ar'?'أتحقق أولًا من علامات الخطر…':'Checking for urgent red flags first…'));
      try {
        const sr = await fetch('/api/analyze/safety-check', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body:JSON.stringify(dataQualityPayload())
        });
        const sd = await sr.json();
        if (sd.consent_required) { location.href=sd.consent_url||'/consent?next=/chat'; return; }
        if (sr.ok && sd.ok && sd.emergency) {
          showEmergency(sd.result || {emergency:true, emergency_flags:(sd.safety_engine&&sd.safety_engine.flags)||[]});
          return;
        }
      } catch(e) {
        // Fail open to the existing flow; the final /api/analyze endpoint runs
        // the same deterministic safety layer again before analysis.
      }
      clarQueue = [];
      clarIndex = 0;
      adaptiveQuestionNo = 0;
      followupTotal = 0;
      redflagAsked = []; state.redflag_yes = []; differentialAsked = []; differentialNegatives = []; differentialCount = 0; differentialCandidates = []; differentialAnswers = []; differentialLastAnswer = null;
      (state.symptoms || []).forEach(function(s){
        var matched=false;
        for (var i = 0; i < CLAR.length; i++) {
          if (CLAR[i].syms.indexOf(s) !== -1) { clarQueue.push(CLAR[i].node); matched=true; break; }
        }
        if(!matched) clarQueue.push(genericClarForSymptom(s));
      });
      nextClarNode();
    }
    function askAge() {
      if (state.age) { askGender(); return; }
      state.step = 'age';
      updateFlow(state.step);
      focusStepQuestion(TT('age'));
      showText(TT('age_ph'));
    }
    function askGender() {
      if (state.gender) { askSymptoms(); return; }
      state.step = 'gender';
      updateFlow(state.step);
      focusStepQuestion(TT('gender'));
      hideText();
      showOpts([
        {label:TT('male'), fn:()=>{ state.gender='m'; add(TT('male'),'user'); if(qualityReturnKey==='gender'){qualityReturnKey=null;showDataQualityGate();}else askSymptoms(); }},
        {label:TT('female'), fn:()=>{ state.gender='f'; add(TT('female'),'user'); if(qualityReturnKey==='gender'){qualityReturnKey=null;showDataQualityGate();}else askSymptoms(); }}
      ]);
    }
    function G(f, m) { return state.gender === 'm' ? m : f; }
    function sexIsMale() { return state.gender === 'm' || state.gender === 'male'; }
    function sexIsFemale() { return state.gender === 'f' || state.gender === 'female'; }
    function cycleContextRelevant() {
      const hay=((state.symptoms||[]).join(' ')+' '+String(state.raw_description||'')).toLowerCase();
      return /غثيان|مغص|بطن|حوض|صداع|شقيق|دوخ|تعب|ارهاق|إرهاق|انتفاخ|ثدي|مزاج|تشنج|الم اسفل الظهر|ألم أسفل الظهر|nause|cramp|abdom|pelvic|headache|migraine|dizz|fatigue|bloat|breast|mood|lower back/i.test(hay);
    }
    function symptomWorseOptions() {
      // Common context choices stay available to everyone. Menstrual timing is
      // only offered for a female profile *and* a symptom where cycle timing can
      // reasonably help interpretation. This prevents irrelevant questions such
      // as "وقت الدورة / During period" for a male user or for unrelated symptoms.
      const common = LANG==='ar'
        ? ['مع الحركة','بعد الأكل','عند الوقوف','بالليل','بعد المجهود','مع التوتر','غير واضح']
        : ['Movement','After eating','Standing up','At night','After exertion','Stress','Not clear'];
      if (!sexIsFemale() || !cycleContextRelevant()) return common;
      const cycle = LANG==='ar' ? 'وقت الدورة' : 'During period';
      const out = common.slice();
      out.splice(3, 0, cycle);
      return out;
    }
    function trackJourney(stage) {
      try { fetch('/api/analytics/journey',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({stage:stage}),keepalive:true}).catch(function(){}); } catch(e) {}
    }
    function contextLabelList(ctx) {
      const rows=[];
      if(!ctx) return rows;
      if(ctx.duration) rows.push((LANG==='ar'?'المدة: ':'Duration: ')+ctx.duration);
      if(ctx.onset) rows.push((LANG==='ar'?'البداية: ':'Onset: ')+ctx.onset);
      if(ctx.course) rows.push((LANG==='ar'?'المسار: ':'Course: ')+ctx.course);
      if(Array.isArray(ctx.worse) && ctx.worse.length) rows.push((LANG==='ar'?'يزيد مع: ':'Worse with: ')+ctx.worse.slice(0,2).join(LANG==='ar'?'، ':', '));
      if(Array.isArray(ctx.relief) && ctx.relief.length) rows.push((LANG==='ar'?'يخف مع: ':'Relieved by: ')+ctx.relief.slice(0,2).join(LANG==='ar'?'، ':', '));
      if(ctx.medication_context) rows.push((LANG==='ar'?'سياق دوائي: ':'Medication context: ')+ctx.medication_context);
      return rows;
    }
    function applyExtractedContext(ctx, raw) {
      if(!ctx || typeof ctx!=='object') { state.raw_description=String(raw||''); return; }
      state.raw_description=String(raw||ctx.raw_description||'');
      state.extracted_context=ctx;
      if(!state.duration && ctx.duration) state.duration=ctx.duration;
      if(!state.onset && ctx.onset) state.onset=ctx.onset;
      if(!state.course && ctx.course) state.course=ctx.course;
      if(!state.pattern_worse && Array.isArray(ctx.worse) && ctx.worse.length) state.pattern_worse=ctx.worse.slice(0,2).join(LANG==='ar'?'، ':', ');
      if(!state.pattern_relief && Array.isArray(ctx.relief) && ctx.relief.length) state.pattern_relief=ctx.relief.slice(0,2).join(LANG==='ar'?'، ':', ');
      if(!state.location && Array.isArray(ctx.locations) && ctx.locations.length) state.location=ctx.locations.slice(0,2).join(LANG==='ar'?'، ':', ');
    }
    function contextFoundHtml(ctx) {
      const rows=contextLabelList(ctx);
      if(!rows.length) return '';
      return '<div class="smart-context-found"><b>🧭 '+esc(LANG==='ar'?'فهمنا من وصفك أيضًا:':'We also understood:')+'</b><div class="smart-context-chips">'+rows.map(function(x){return '<span>'+esc(x)+'</span>';}).join('')+'</div><small>'+esc(LANG==='ar'?'ستُراجع هذه المعلومات في مسار الأعراض، ويمكنك تعديلها.':'You can review and change these details in the symptom path.')+'</small></div>';
    }
    async function extractSmartSymptoms(text, sourceBodyRegion) {
      const raw = String(text || '').trim();
      if (!raw) return;
      clearOpts(); add(LANG==='ar'?'أفهم وصفك وأطابقه مع قاعدة الأعراض…':'Understanding your description and matching it to the symptom knowledge base…','bot');
      try {
        const r = await fetch('/api/symptoms/extract',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:raw,lang:LANG})});
        const d = await r.json();
        applyExtractedContext(d.context || null, raw);
        const found = (d.found || []).map(function(x){ return LANG==='ar' ? (x.name_ar || x.name_en || x.slug) : (x.name_en || x.name_ar || x.slug); }).filter(Boolean);
        const typedRegions = inferBodyRegions(raw, found);
        if (showBodyRegionConflict(raw, found, typedRegions)) return;
        if (!found.length) {
          state.symptoms=Array.from(new Set((state.symptoms||[]).concat([raw])));
          if (sourceBodyRegion) rememberBodyRegionSymptoms(sourceBodyRegion, [raw]);
          addHtml('<div>'+esc(LANG==='ar'?'تم اعتماد وصفك كما كتبته.':'Your description was saved as written.')+contextFoundHtml(d.context||null)+'</div>','bot');
          if (compactSymptomUI()) askSymptoms(); else askDuration();
          return;
        }
        addHtml('<div class="smart-found"><b>🧠 '+esc(LANG==='ar'?'وجدنا:':'We found:')+'</b><div style="margin-top:8px">'+found.map(x=>'✓ '+esc(x)).join('<br>')+'</div>'+contextFoundHtml(d.context||null)+'<p class="muted" style="margin:8px 0 0">'+esc(LANG==='ar'?'هل هذا صحيح؟':'Is this correct?')+'</p></div>','bot');
        if (compactSymptomUI()) {
          showOpts([
            {label:LANG==='ar'?'✅ إضافة الأعراض':'✅ Add symptoms',fn:function(){ state.symptoms=Array.from(new Set((state.symptoms||[]).concat(found))); if(sourceBodyRegion) rememberBodyRegionSymptoms(sourceBodyRegion, found); add(LANG==='ar'?'تمت إضافة الأعراض':'Symptoms added','user'); askSymptoms(); }},
            {label:LANG==='ar'?'✏️ تعديل':'✏️ Edit',fn:function(){ state.symptoms=Array.from(new Set((state.symptoms||[]).concat(found))); if(sourceBodyRegion) rememberBodyRegionSymptoms(sourceBodyRegion, found); askSymptoms(); }}
          ]);
        } else {
          showOpts([
            {label:LANG==='ar'?'✅ نعم، متابعة':'✅ Yes, continue',fn:function(){ state.symptoms=Array.from(new Set((state.symptoms||[]).concat(found))); add(LANG==='ar'?'تم تأكيد الأعراض':'Symptoms confirmed','user'); askDuration(); }},
            {label:LANG==='ar'?'✏️ تعديل الأعراض':'✏️ Edit symptoms',fn:function(){ state.symptoms=Array.from(new Set((state.symptoms||[]).concat(found))); askSymptoms(); }}
          ]);
        }
      } catch(e) {
        const typedRegions = inferBodyRegions(raw, []);
        if (showBodyRegionConflict(raw, [raw], typedRegions)) return;
        state.raw_description=raw;
        state.symptoms=Array.from(new Set((state.symptoms||[]).concat([raw])));
        if (sourceBodyRegion) rememberBodyRegionSymptoms(sourceBodyRegion, [raw]);
        add(LANG==='ar'?'تم حفظ وصفك كما كتبته.':'Your description was saved as written.','bot');
        if (compactSymptomUI()) askSymptoms(); else askDuration();
      }
    }
    function showSmartSymptomInput() {
      state.smart_prompt_shown=true;
      if (compactSymptomUI()) hideText();
      else showText(LANG==='ar'?'اكتب عرضًا أو اختر من الخيارات أدناه…':'Type a symptom or choose from the options below…', true);
      const card = bodyEl.querySelector('.step-focus-card');
      if (!card) return;
      const host = compactSymptomUI() ? (card.querySelector('#symptomMethodPane') || card) : card;
      if (!host.querySelector('.symptom-entry-card')) {
        const quickSymptoms = LANG==='ar'
          ? ['صداع','حرارة','سعال','غثيان','اسهال','ألم البطن','دوخة','تعب']
          : ['Headache','Fever','Cough','Nausea','Diarrhea','Abdominal pain','Dizziness','Fatigue'];
        const entry = document.createElement('div');
        entry.className = 'symptom-entry-card';
        const quickChipsHtml = compactSymptomUI() ? '' : ('<div class="quick-symptom-chips">'
          + quickSymptoms.map(function(symptom){return '<button type="button" class="quick-symptom-chip" data-quick-symptom="'+escAttr(symptom)+'">'+esc(symptom)+'</button>';}).join('')
          + '</div>');
        entry.innerHTML = '<div class="symptom-section-head"><span class="symptom-section-icon">✍️</span><div><b>'+esc(LANG==='ar'?'صف الأعراض بطريقتك':'Describe your symptoms in your own words')+'</b><small>'+esc(LANG==='ar'?'مثال: من أمس عندي صداع قوي وأحس بغثيان.':'Example: Since yesterday I have a strong headache and feel nauseous.')+'</small></div></div>'
          + '<div class="symptom-text-row"><textarea id="smartSymptomText" class="field symptom-main-text" rows="3" placeholder="'+escAttr(LANG==='ar'?'صف الأعراض بطريقتك…':'Describe your symptoms in your own words…')+'"></textarea>'
          + '<button type="button" id="smartTextMicBtn" class="symptom-mic-btn" aria-pressed="false" aria-label="'+escAttr(LANG==='ar'?'تكلم بدل الكتابة':'Speak instead of typing')+'" title="'+escAttr(LANG==='ar'?'تكلم بدل الكتابة':'Speak instead of typing')+'"><span aria-hidden="true">🎙️</span></button></div>'
          + '<button type="button" class="ss-btn-primary symptom-understand-btn" data-smart-extract>'+esc(LANG==='ar'?'فهم الأعراض':'Find symptoms')+'</button>'
          + (compactSymptomUI() ? '' : '<div class="symptom-mini-label">'+esc(LANG==='ar'?'أو اختر عرضًا شائعًا:':'Or pick a common symptom:')+'</div>'+quickChipsHtml);
        entry.addEventListener('click', function(e){
          const quick=e.target.closest('[data-quick-symptom]');
          if(quick&&entry.contains(quick)){ extractSmartSymptoms(quick.dataset.quickSymptom||''); return; }
          const extract=e.target.closest('[data-smart-extract]');
          if(extract&&entry.contains(extract)){ const ta=entry.querySelector('#smartSymptomText'); extractSmartSymptoms(ta?ta.value:''); }
          const micBtn2=e.target.closest('#smartTextMicBtn');
          if(micBtn2&&entry.contains(micBtn2)){ toggleSymptomTextMic(micBtn2, entry.querySelector('#smartSymptomText')); }
        });
        host.appendChild(entry);
      }
      if (!compactSymptomUI()) ensureBodyMapCard();
    }
    function updateMobileSelectedSummary() {
      if (!compactSymptomUI()) return;
      const box = document.getElementById('symptomSelectedSummary');
      if (!box) return;
      const list = Array.isArray(state.symptoms) ? state.symptoms : [];
      if (!list.length) {
        box.className='symptom-selected-summary is-empty';
        box.innerHTML='<div class="symptom-selected-head"><span>'+esc(LANG==='ar'?'الأعراض المختارة':'Selected symptoms')+'</span><b>0</b></div>';
        return;
      }
      box.className='symptom-selected-summary';
      box.innerHTML='<div class="symptom-selected-head"><span>'+esc(LANG==='ar'?'الأعراض التي سنحللها':'Symptoms to analyze')+'</span><b>'+list.length+'</b></div><div class="symptom-selected-chips">'+list.map(function(s){ return '<span class="symptom-selected-chip"><span>'+esc(s)+'</span><button type="button" data-remove-symptom="'+escAttr(s)+'" aria-label="'+escAttr((LANG==='ar'?'إزالة ':'Remove ')+s)+'">×</button></span>'; }).join('')+'</div>';
    }
    function refreshMobileStartButton() {
      if (!compactSymptomUI()) return;
      const s = optsEl.querySelector('.start-btn');
      if (!s) return;
      const regionNeedsSymptom = !!(state.body_region_needs_symptom && !hasSymptomForBodyRegion(state.body_region_needs_symptom));
      s.textContent = regionNeedsSymptom
        ? (LANG === 'ar' ? 'اختر عرضًا من ' + bodyRegionLabel(state.body_region_needs_symptom) + ' أولًا' : 'Choose a symptom from ' + bodyRegionLabel(state.body_region_needs_symptom) + ' first')
        : (state.symptoms.length ? (LANG === 'ar' ? 'متابعة التحليل' : 'Continue assessment') : (LANG === 'ar' ? 'أضف عرضًا للمتابعة' : 'Add a symptom to continue'));
      s.disabled = !state.symptoms.length || regionNeedsSymptom;
      s.setAttribute('aria-disabled', s.disabled ? 'true' : 'false');
    }
    function showSymptomMethodChooser() {
      const card = bodyEl.querySelector('.step-focus-card');
      if (!card || !compactSymptomUI()) return;
      const panel=document.createElement('section');
      panel.className='symptom-method-switcher symptom-method-switcher-v238';
      panel.innerHTML='<div class="symptom-method-tabs symptom-method-tabs-compact" role="tablist" aria-label="'+escAttr(LANG==='ar'?'طريقة إدخال الأعراض':'Symptom input method')+'">'
        + '<button type="button" class="symptom-method-btn '+(symptomInputMethod==='pick'?'active':'')+'" data-symptom-method="pick" role="tab" aria-selected="'+(symptomInputMethod==='pick'?'true':'false')+'"><span aria-hidden="true">⚡</span><span class="symptom-method-copy"><b>'+esc(LANG==='ar'?'اختيار سريع':'Quick pick')+'</b></span></button>'
        + '<button type="button" class="symptom-method-btn '+(symptomInputMethod==='body'?'active':'')+'" data-symptom-method="body" role="tab" aria-selected="'+(symptomInputMethod==='body'?'true':'false')+'"><span aria-hidden="true">🧍</span><span class="symptom-method-copy"><b>'+esc(LANG==='ar'?'من الجسم':'Body map')+'</b></span></button>'
        + '<button type="button" class="symptom-method-btn '+(symptomInputMethod==='describe'?'active':'')+'" data-symptom-method="describe" role="tab" aria-selected="'+(symptomInputMethod==='describe'?'true':'false')+'"><span aria-hidden="true">✍️</span><span class="symptom-method-copy"><b>'+esc(LANG==='ar'?'اكتب بنفسك':'Type it')+'</b></span></button>'
        + '</div><div id="symptomSelectedSummary" class="symptom-selected-summary is-empty"></div><div id="symptomMethodPane" class="symptom-method-pane"></div>';
      panel.addEventListener('click',function(e){
        const method=e.target.closest('[data-symptom-method]');
        if(method&&panel.contains(method)){
          closeBodyMapSheet();
          symptomInputMethod=method.dataset.symptomMethod||'describe';
          symptomOptionsExpanded=false;
          askSymptoms();
          return;
        }
        const remove=e.target.closest('[data-remove-symptom]');
        if(remove&&panel.contains(remove)){ const removedSymptom=remove.dataset.removeSymptom||''; state.symptoms=state.symptoms.filter(function(x){return x!==removedSymptom;}); forgetBodyRegionSymptom(removedSymptom); if(state.body_region_needs_symptom && hasSymptomForBodyRegion(state.body_region_needs_symptom)) state.body_region_needs_symptom=null; askSymptoms(); }
      });
      card.appendChild(panel);
      updateMobileSelectedSummary();
    }
    function showMobileBodyLauncher() {
      const pane=document.getElementById('symptomMethodPane');
      if(!pane) return;
      closeBodyMapSheet();
      pane.classList.add('symptom-method-pane-body');
      pane.innerHTML=renderBodyMapCard();
      bodyMapOpen=true;
      bindBodyMapCard();
      if (selectedBodyZone && BODY_MAP_ZONES[selectedBodyZone]) showBodyZone(selectedBodyZone, false);
      else if (state.body_region_primary) showBodyRegion(state.body_region_primary, false);
    }
    function showMobilePickIntro() {
      const pane=document.getElementById('symptomMethodPane');
      if(!pane) return;
      pane.innerHTML='<div class="symptom-pick-note">'+esc(LANG==='ar'?'اختر عرضًا أو أكثر من القائمة. نعرض الأكثر شيوعًا أولًا لتبقى الصفحة خفيفة.':'Choose one or more symptoms. Common options appear first to keep the page compact.')+'</div>';
    }
    // خريطة الجسم التفاعلية / Interactive body map — V230 approved-reference presentation.
    // ---- V244 body map: clean inline SVG (no raster art, no baked-in label stubs) ----
    // V245: real anatomical art (front/back) + SVG hotspots. All numbers below are in the artwork's own pixel space (355x869).
    const BM_ART = {front:{src:'/static/images/body-front-v245.webp', axis:186}, back:{src:'/static/images/body-back-v245.webp', axis:171}};
    const BM_SC = 504/869, BM_OX = 180 - (355*504/869)/2, BM_OY = 14;
    // dot:[px,py] in art px; m:true puts the dot on the viewer-right limb; side/ly = label column and its y in the 360x540 box.
    const BM_LAYOUT = {
      front:{
        head_front:{dot:[187,50],side:'R',ly:40,shape:'head'},
        neck_front:{dot:[188,133],side:'R',ly:92,shape:'neck'},
        chest_front:{dot:[225,198],side:'R',ly:142,shape:'chest'},
        upper_abdomen:{dot:[188,290],side:'R',ly:198,shape:'upper'},
        lower_abdomen:{dot:[188,388],side:'R',ly:254,shape:'lower'},
        arms_front:{dot:[72,235],side:'L',ly:150,shape:'arms'},
        hands_front:{dot:[30,445],side:'L',ly:282,shape:'hands'},
        thigh_front:{dot:[135,515],side:'L',ly:342,shape:'thigh'},
        knee_front:{dot:[225,625],side:'R',ly:388,shape:'knee'},
        lower_leg_front:{dot:[138,735],side:'L',ly:442,shape:'leg'},
        foot_front:{dot:[217,845],side:'R',ly:498,shape:'foot'}
      },
      back:{
        head_back:{dot:[170,50],side:'R',ly:40,shape:'head'},
        neck_back:{dot:[170,122],side:'R',ly:92,shape:'neck'},
        upper_back:{dot:[205,200],side:'R',ly:150,shape:'upback'},
        lower_back:{dot:[172,330],side:'R',ly:240,shape:'lowback'},
        arms_back:{dot:[75,245],side:'L',ly:150,shape:'arms'},
        thigh_back:{dot:[128,520],side:'L',ly:342,shape:'thigh'},
        knee_back:{dot:[205,630],side:'R',ly:388,shape:'knee'},
        calf_back:{dot:[133,740],side:'L',ly:442,shape:'leg'},
        foot_back:{dot:[207,848],side:'R',ly:498,shape:'foot'}
      }
    };
    // Hotspot shapes: [cx,cy,rx,ry,rotation,mirror]; mirror=true also draws the opposite limb.
    const BM_SHAPES = {
      front:{head:[[187,52,40,50,0,0]],neck:[[188,133,26,24,0,0]],chest:[[188,200,100,58,0,0]],upper:[[188,287,58,52,0,0]],lower:[[188,388,60,52,0,0]],
        arms:[[72,240,26,98,13,1]],hands:[[30,442,22,38,15,1]],thigh:[[135,515,42,100,0,1]],knee:[[147,625,33,38,0,1]],leg:[[140,737,30,88,0,1]],foot:[[153,845,30,22,0,1]]},
      back:{head:[[170,52,40,50,0,0]],neck:[[170,122,26,24,0,0]],upback:[[172,200,100,70,0,0]],lowback:[[172,325,62,70,0,0]],
        arms:[[75,245,26,98,13,1]],hands:[[32,440,22,38,15,1]],thigh:[[128,520,44,100,0,1]],knee:[[140,630,33,38,0,1]],leg:[[133,740,32,88,0,1]],foot:[[135,848,30,22,0,1]]}
    };
    function askSymptoms() {
      trackJourney('symptoms');
      state.step = 'symptoms';
      updateFlow(state.step);
      const compact = compactSymptomUI();
      const selectedSummary = (!compact && state.symptoms.length)
        ? (TT('chosen') + ' ' + state.symptoms.join(LANG === 'en' ? ', ' : '، '))
        : undefined;
      focusStepQuestion('🩺 ' + (state.symptoms.length ? TT('syms_more') : TT('syms_q')), selectedSummary);
      if (compact) {
        hideText();
        showSymptomMethodChooser();
        if (symptomInputMethod === 'describe') showSmartSymptomInput();
        else if (symptomInputMethod === 'body') showMobileBodyLauncher();
        else showMobilePickIntro();
      } else {
        if (!state.symptoms.length) showSmartSymptomInput(); else hideText();
      }
      let visibleSyms = SYMS;
      if (compact && !symptomOptionsExpanded) {
        visibleSyms = SYMS.slice(0, 8);
        state.symptoms.forEach(function(s){ if (SYMS.includes(s) && !visibleSyms.includes(s)) visibleSyms.push(s); });
      }
      const items = visibleSyms.map((s,i)=>({
        label:s,
        sel: state.symptoms.includes(s),
        fn:()=>{
          if (state.symptoms.includes(s)) { state.symptoms = state.symptoms.filter(x=>x!==s); askSymptoms(); return; }
          const optionRegions = inferBodyRegions(s, [s]);
          if (showBodyRegionConflict(s, [s], optionRegions)) return;
          state.symptoms.push(s);
          askSymptoms();
        }
      }));
      const customs = state.symptoms.filter(s => !SYMS.includes(s));
      customs.forEach(s => items.push({
        label: s, sel: true, fn:()=>{ state.symptoms = state.symptoms.filter(x=>x!==s); askSymptoms(); }
      }));
      if (!compact) items.push({label:TT('write_yourself_n'), fn:()=>{ addQ(TT('custom_n')); showText(TT('syms_hint'), true); }});

      if (compact && symptomInputMethod !== 'pick') {
        showOpts([]); optsEl.classList.add('symptom-picker','method-actions-only');
      } else {
        showOpts(items); optsEl.classList.add('symptom-picker');
        if (compact && SYMS.length > 8) {
          const more = document.createElement('button');
          more.type = 'button'; more.className = 'opt symptom-more-toggle';
          more.textContent = symptomOptionsExpanded ? (LANG==='ar'?'عرض أقل':'Show fewer') : (LANG==='ar'?'عرض المزيد':'Show more');
          more.onclick = function(){ symptomOptionsExpanded = !symptomOptionsExpanded; askSymptoms(); };
          optsEl.appendChild(more);
        }
        renderRelated();
      }
      appendStartBtn();
      if (!compact) ensureBodyMapCard();
      else { updateMobileSelectedSummary(); refreshMobileStartButton(); }
    }
    function renderRelated() {
      const rel = [];
      (state.symptoms || []).forEach(function(s) {
        (REL[s] || []).forEach(function(r) {
          if (rel.indexOf(r) === -1 && state.symptoms.indexOf(r) === -1) rel.push(r);
        });
      });
      const old = document.getElementById('relBlock');
      if (old) old.remove();
      if (!rel.length) return;
      const blk = document.createElement('div');
      blk.id = 'relBlock';
      let h = '<div class="rel-title">💡 ' + esc(TT('related_title')) + '</div>';
      h += '<div class="rel-chips">';
      rel.slice(0, compactSymptomUI() ? 4 : 8).forEach(function(r) {
        h += '<button type="button" class="rel-chip" data-related-symptom="' + escAttr(r) + '">' + esc(r) + '</button>';
      });
      h += '</div>';
      blk.innerHTML = h;
      blk.addEventListener('click', function(e){
        const btn=e.target.closest('[data-related-symptom]');
        if(btn&&blk.contains(btn)) addRelated(btn, btn.dataset.relatedSymptom||'');
      });
      optsEl.appendChild(blk);
    }
    function addRelated(btn, label) {
      if (state.symptoms.indexOf(label) !== -1) return;
      const relatedRegions = inferBodyRegions(label, [label]);
      if (showBodyRegionConflict(label, [label], relatedRegions)) return;
      state.symptoms.push(label);
      askSymptoms();
    }
    let earlySafetyChecked=false, earlySafetyRunning=false;
    async function askDuration() {
      // Check immediate red flags as soon as the user has committed their
      // symptom list, before asking ordinary duration/severity questions.
      if(!earlySafetyChecked && !earlySafetyRunning){
        earlySafetyRunning=true;
        try{
          const sr=await fetch('/api/analyze/safety-check',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(dataQualityPayload())});
          const sd=await sr.json();
          if(sd.consent_required){location.href=sd.consent_url||'/consent?next=/chat';return;}
          if(sr.ok&&sd.ok&&sd.emergency){showEmergency(sd.result||{emergency:true,emergency_flags:(sd.safety_engine&&sd.safety_engine.flags)||[]});return;}
        }catch(e){/* final analysis repeats the same deterministic safety check */}
        finally{earlySafetyRunning=false;}
        earlySafetyChecked=true;
      }
      trackJourney('questionnaire');
      if (state.duration) { askSeverity(); return; }
      state.step = 'duration';
      updateFlow(state.step);
      const durationCard = focusStepQuestion(TT('duration'));
      if (durationCard && Array.isArray(state.symptoms) && state.symptoms.length) {
        const understood = document.createElement('div');
        understood.className = 'v2-safe-note';
        understood.style.cssText = 'margin-top:14px;display:flex;align-items:flex-start;justify-content:space-between;gap:10px;flex-wrap:wrap';
        const understoodText = document.createElement('div');
        const understoodLabel = document.createElement('b');
        understoodLabel.textContent = LANG==='ar' ? 'تم فهم الأعراض: ' : 'Symptoms understood: ';
        understoodText.appendChild(understoodLabel);
        understoodText.appendChild(document.createTextNode(state.symptoms.join(LANG==='ar'?'، ':', ')));
        const editSymptoms = document.createElement('button');
        editSymptoms.type='button'; editSymptoms.className='opt';
        editSymptoms.style.cssText='width:auto;min-height:38px;padding:7px 12px;margin:0';
        editSymptoms.textContent = LANG==='ar' ? '✏️ تعديل الأعراض' : '✏️ Edit symptoms';
        editSymptoms.onclick = function(){ state.duration=null; askSymptoms(); };
        understood.appendChild(understoodText); understood.appendChild(editSymptoms);
        durationCard.appendChild(understood);
      }
      hideText();
      showOpts(DURS.map(d=>({label:d, fn:()=>{ state.duration=d; add(d,'user'); if(qualityReturnKey==='duration'){qualityReturnKey=null;showDataQualityGate();}else askSeverity(); }})));
    }
    function askSeverity() {
      if (state.severity) { if(state.quick_mode) startClarify(); else if(state.pattern_context_done) askNotes(); else askSymptomPath(); return; }
      state.step = 'severity';
      updateFlow(state.step);
      focusStepQuestion(TT('severity'));
      hideText();
      showOpts(SEVS.map(([v,l])=>({label:l, fn:()=>{ state.severity=v; add(l,'user'); if(qualityReturnKey==='severity'){qualityReturnKey=null;showDataQualityGate();}else if(state.quick_mode) startClarify(); else askSymptomPath(); }})));
    }
    function symptomPathAssociatedText() {
      const syms=(state.symptoms||[]).filter(Boolean);
      if(syms.length>1) return syms.slice(1,4).join(LANG==='ar'?'، ':', ');
      return syms.length ? (LANG==='ar'?'لا يوجد عرض إضافي محدد':'No additional symptom specified') : (LANG==='ar'?'غير محدد':'Not specified');
    }
    function symptomPathItems() {
      return [
        {icon:'⏱️',label:LANG==='ar'?'بدأ العرض':'Started',value:state.duration||''},
        {icon:'⚡',label:LANG==='ar'?'طريقة البداية':'Onset',value:state.onset||''},
        {icon:'〰️',label:LANG==='ar'?'المسار':'Course',value:state.course||''},
        {icon:'↗️',label:LANG==='ar'?'متى يزيد':'Worsens with',value:state.pattern_worse||''},
        {icon:'＋',label:LANG==='ar'?'ما يصاحبه':'Comes with',value:symptomPathAssociatedText()},
        {icon:'↘️',label:LANG==='ar'?'ما يخففه':'Relieved by',value:state.pattern_relief||''}
      ];
    }
    function symptomPathRailHtml(compact) {
      const empty=LANG==='ar'?'لم يُحدد بعد':'Not set yet';
      const items=symptomPathItems();
      return '<div class="symptom-path-rail'+(compact?' compact':'')+'">'+items.map(function(item,index){
        const active=!!String(item.value||'').trim();
        return '<div class="symptom-path-node'+(active?' done':'')+'"><span class="symptom-path-dot">'+esc(item.icon)+'</span><div><b>'+esc(item.label)+'</b><small>'+esc(active?item.value:empty)+'</small></div></div>'+(index<items.length-1?'<span class="symptom-path-line" aria-hidden="true"></span>':'');
      }).join('')+'</div>';
    }
    function refreshSymptomPathCard() {
      const host=document.getElementById('symptomPathLive');
      if(!host) return;
      const rail=host.querySelector('[data-path-rail]'); if(rail) rail.innerHTML=symptomPathRailHtml(false);
      host.querySelectorAll('[data-path-onset]').forEach(function(btn){btn.classList.toggle('on',(btn.dataset.pathOnset||'')===String(state.onset||''));});
      host.querySelectorAll('[data-path-course]').forEach(function(btn){btn.classList.toggle('on',(btn.dataset.pathCourse||'')===String(state.course||''));});
      host.querySelectorAll('[data-path-worse]').forEach(function(btn){btn.classList.toggle('on',(btn.dataset.pathWorse||'')===String(state.pattern_worse||''));});
      host.querySelectorAll('[data-path-relief]').forEach(function(btn){btn.classList.toggle('on',(btn.dataset.pathRelief||'')===String(state.pattern_relief||''));});
      const next=host.querySelector('[data-path-next]'); if(next) next.disabled=!(state.onset&&state.course&&state.pattern_worse&&state.pattern_relief);
    }
    function beginSymptomPathCustom(kind) {
      state.step = kind==='worse' ? 'symptom_path_worse_custom' : 'symptom_path_relief_custom';
      showText(kind==='worse' ? (LANG==='ar'?'اكتب متى أو مع ماذا يزيد العرض…':'Type when or what makes it worse…') : (LANG==='ar'?'اكتب ما الذي يخفف العرض…':'Type what relieves it…'), true);
      try{ textInp.focus(); }catch(e){}
    }
    function finishSymptomPath() {
      state.pattern_context_done=true;
      hideText();
      add(LANG==='ar'?'تم تحديث مسار الأعراض':'Symptom path updated','user');
      askNotes();
    }
    function askSymptomPath() {
      if (state.pattern_context_done) { askNotes(); return; }
      state.step='symptom_path'; updateFlow(state.step); clearOpts(); hideText();
      const card=focusStepQuestion(LANG==='ar'?'🧭 مسار الأعراض':'🧭 Symptom path');
      if(!card){ askNotes(); return; }
      const onset=LANG==='ar'?['فجأة','تدريجيًا','غير واضح']:['Sudden','Gradual','Not clear'];
      const course=LANG==='ar'?['مستمر','يجي ويروح','يزداد تدريجيًا','يتحسن تدريجيًا','غير واضح']:['Continuous','Comes and goes','Progressively worsening','Gradually improving','Not clear'];
      const worse=symptomWorseOptions();
      const relief=LANG==='ar'?['الراحة','شرب السوائل','الأكل','تغيير الوضعية','النوم','لا شيء واضح','غير واضح']:['Rest','Fluids','Eating','Changing position','Sleep','Nothing clear','Not clear'];
      const host=document.createElement('div'); host.id='symptomPathLive'; host.className='symptom-path-live';
      host.innerHTML='<p class="symptom-path-intro">'+esc(LANG==='ar'?'بدل أسئلة متفرقة، نبني مسارًا مختصرًا يوضح نمط العرض. اختر الأقرب، ويمكنك كتابة خيار آخر.':'Instead of scattered questions, build a short visual path for the symptom pattern. Choose the closest option or add your own.')+'</p>'
        +'<div data-path-rail>'+symptomPathRailHtml(false)+'</div>'
                +'<div class="symptom-path-picker"><b>'+esc(LANG==='ar'?'كيف بدأ؟':'How did it start?')+'</b><div class="symptom-path-chips">'+onset.map(function(v){return '<button type="button" data-path-onset="'+escAttr(v)+'">'+esc(v)+'</button>';}).join('')+'</div></div>'
        +'<div class="symptom-path-picker"><b>'+esc(LANG==='ar'?'هل هو مستمر أو يجي ويروح؟':'What is the course?')+'</b><div class="symptom-path-chips">'+course.map(function(v){return '<button type="button" data-path-course="'+escAttr(v)+'">'+esc(v)+'</button>';}).join('')+'</div></div>'
        +'<div class="symptom-path-picker"><b>'+esc(LANG==='ar'?'متى يزيد؟':'When is it worse?')+'</b><div class="symptom-path-chips">'+worse.map(function(v){return '<button type="button" data-path-worse="'+escAttr(v)+'">'+esc(v)+'</button>';}).join('')+'<button type="button" data-path-custom="worse">'+esc(LANG==='ar'?'شيء آخر':'Other')+'</button></div></div>'
        +'<div class="symptom-path-picker"><b>'+esc(LANG==='ar'?'ما الذي يخففه؟':'What relieves it?')+'</b><div class="symptom-path-chips">'+relief.map(function(v){return '<button type="button" data-path-relief="'+escAttr(v)+'">'+esc(v)+'</button>';}).join('')+'<button type="button" data-path-custom="relief">'+esc(LANG==='ar'?'شيء آخر':'Other')+'</button></div></div>'
        +'<div class="symptom-path-actions"><button type="button" class="symptom-path-skip" data-path-skip>'+esc(LANG==='ar'?'تخطي هذا الجزء':'Skip this')+'</button><button type="button" class="ss-btn-primary symptom-path-next" data-path-next disabled>'+esc(LANG==='ar'?'متابعة':'Continue')+'</button></div>';
      host.addEventListener('click',function(e){
        const o=e.target.closest('[data-path-onset]'); if(o){state.onset=o.dataset.pathOnset||'';refreshSymptomPathCard();return;}
        const cr=e.target.closest('[data-path-course]'); if(cr){state.course=cr.dataset.pathCourse||'';refreshSymptomPathCard();return;}
        const w=e.target.closest('[data-path-worse]'); if(w){state.pattern_worse=w.dataset.pathWorse||'';refreshSymptomPathCard();return;}
        const r=e.target.closest('[data-path-relief]'); if(r){state.pattern_relief=r.dataset.pathRelief||'';refreshSymptomPathCard();return;}
        const c=e.target.closest('[data-path-custom]'); if(c){beginSymptomPathCustom(c.dataset.pathCustom||'');return;}
        if(e.target.closest('[data-path-skip]')){state.onset=state.onset||(LANG==='ar'?'غير واضح':'Not clear');state.course=state.course||(LANG==='ar'?'غير واضح':'Not clear');state.pattern_worse=state.pattern_worse||(LANG==='ar'?'غير محدد':'Not specified');state.pattern_relief=state.pattern_relief||(LANG==='ar'?'غير محدد':'Not specified');finishSymptomPath();return;}
        if(e.target.closest('[data-path-next]') && state.onset && state.course && state.pattern_worse && state.pattern_relief){finishSymptomPath();}
      });
      card.appendChild(host); refreshSymptomPathCard();
    }
    function symptomPathContextNote() {
      const bits=[];
      if(state.onset && !/غير واضح|Not clear/i.test(state.onset)) bits.push((LANG==='ar'?'طريقة البداية: ':'Onset: ')+state.onset);
      if(state.course && !/غير واضح|Not clear/i.test(state.course)) bits.push((LANG==='ar'?'المسار: ':'Course: ')+state.course);
      if(state.pattern_worse && !/غير محدد|Not specified/i.test(state.pattern_worse)) bits.push((LANG==='ar'?'يزيد مع/وقت: ':'Worse with/when: ')+state.pattern_worse);
      if(state.pattern_relief && !/غير محدد|Not specified/i.test(state.pattern_relief)) bits.push((LANG==='ar'?'يخف مع: ':'Relieved by: ')+state.pattern_relief);
      return bits.join(' | ');
    }
    function askConditions() {
      if (state.conditions && state.member && state.member.conditions) { askMeds(); return; }
      state.step = 'conditions';
      updateFlow(state.step);
      focusStepQuestion(G(TT('conditions_f'), TT('conditions_m')));
      hideText();
      const items = CONDS.map(c=>({label:c, fn:()=>{ state.conditions=c; state.history_answered=true; add(c,'user'); if(qualityReturnKey==='relevant_history'){qualityReturnKey=null;showDataQualityGate();}else askMeds(); }}));
      items.push({label:TT('other_diseases'), fn:()=>{ addQ(G(TT('other_diseases_f'), TT('other_diseases_m'))); showText(TT('cond_ph')); }});
      showOpts(items);
    }
    function askMeds() {
      state.history_answered = true;
      if (state.medications && state.member && state.member.medications) { askAllergies(); return; }
      state.step = 'medications';
      updateFlow(state.step);
      focusStepQuestion(G(TT('meds_f'), TT('meds_m')));
      showOpts([{label:TT('skip'), fn:()=>{ add(TT('skip'),'user'); state.medications=''; askAllergies(); }}]);
      showText(TT('meds_ph'), true);
    }
    function askAllergies() {
      state.step = 'allergies'; updateFlow(state.step);
      focusStepQuestion(LANG === 'ar' ? 'هل لديك أي حساسية معروفة؟ اذكرها أو اضغط تخطي.' : 'Do you have any known allergies? Add them or skip.');
      showOpts([{label:TT('skip'), fn:()=>{ add(TT('skip'),'user'); state.allergies=''; startClarify(); }}]);
      showText(LANG === 'ar' ? 'مثال: حساسية البنسلين' : 'Example: penicillin allergy', true);
    }
    function askNotes() {
      state.step = 'notes';
      updateFlow(state.step);
      focusStepQuestion(G(TT('notes_f'), TT('notes_m')));
      showOpts([{label:TT('skip'), fn:()=>{ add(TT('skip'),'user'); state.notes=''; askConditions(); }}]);
      showText(TT('notes_ph'), true);
    }
    function submitText() {
      const v = send();
      if (!v) return;
      if (state.step === 'age') {
        const normalizedAge = String(v).replace(/[٠-٩]/g,function(d){return String('٠١٢٣٤٥٦٧٨٩'.indexOf(d));}).replace(/[۰-۹]/g,function(d){return String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d));});
        const n = /^[0-9]{1,3}$/.test(normalizedAge.trim()) ? Number(normalizedAge.trim()) : NaN;
        if (!n || n < 1 || n > 120) { add(TT('age_invalid'), 'bot'); showText(TT('age_ph')); return; }
        state.age = n; if(qualityReturnKey==='age'){qualityReturnKey=null;showDataQualityGate();}else askGender();
      } else if (state.step === 'symptoms') {
        if (checkAmbiguous(v)) return;
        extractSmartSymptoms(v);
      } else if (state.step === 'conditions') {
        state.conditions = v; state.history_answered=true; if(qualityReturnKey==='relevant_history'){qualityReturnKey=null;showDataQualityGate();}else askMeds();
      } else if (state.step === 'medications') {
        state.medications = v; askAllergies();
      } else if (state.step === 'allergies') {
        state.allergies = v; startClarify();
      } else if (state.step === 'notes') {
        state.notes = v; askConditions();
      } else if (state.step === 'symptom_path_worse_custom') {
        state.pattern_worse=v; hideText(); state.step='symptom_path'; askSymptomPath();
      } else if (state.step === 'symptom_path_relief_custom') {
        state.pattern_relief=v; hideText(); state.step='symptom_path'; askSymptomPath();
      } else if (state.step === 'clarification') {
        state.location=v;
        state.notes += (state.notes?' ':'') + (LANG==='ar'?'مكان التنميل: ':'Numbness location: ') + v;
        const next=clarCustomNext; clarCustomNext=null; walkClarNode(next);
      } else if (state.step === 'followup') {
        submitFollowup(v);
      }
    }
    var AMBIG_PATTERNS = [
      {re:/(شوي كثير|كثير شوي|شوية كثير|كثير شوية)/i, type:'severity', opts:[
        {label:'🟢 خفيف', val:'خفيف', en:'Mild'},
        {label:'🟡 متوسط', val:'متوسط', en:'Moderate'},
        {label:'🔴 شديد', val:'شديد', en:'Severe'}
      ]},
      {re:/(دوخة لما أقوم|دوخة عند الوقوف|دوخة وأقوم)/i, type:'timing', opts:[
        {label:'🪑 حتى وأنا جالس', val:'مستمرة حتى بالجلوس', en:'Even while sitting'},
        {label:'🚶 فقط عند الوقوف', val:'فقط عند الوقوف', en:'Only when standing'},
        {label:'🔄 الاثنين', val:'الاثنين', en:'Both'},
        {label:'🤷 مو متأكد', val:'غير متأكد', en:'Not sure'}
      ]},
      {re:/(يعورني شوي|قليلاً|شوية|خفيف شوي)/i, type:'severity_mild', opts:[
        {label:'🟢 خفيف', val:'خفيف', en:'Mild'},
        {label:'🟡 متوسط', val:'متوسط', en:'Moderate'},
        {label:'🔴 شديد', val:'شديد', en:'Severe'}
      ]},
      {re:/(ألم صدر|胸口痛|chest pain)/i, type:'chest', opts:[
        {label:'🔴 شديد جدًا', val:'شديد جدًا', en:'Very severe'},
        {label:'🟡 متوسط', val:'متوسط', en:'Moderate'},
        {label:'🟢 خفيف', val:'خفيف', en:'Mild'}
      ]},
      {re:/(أحياناً|أكيد أحياناً|بعض الأحيان|من حين لآخر)/i, type:'frequency', opts:[
        {label:'📅 يومياً', val:'يومياً', en:'Daily'},
        {label:'📅 عدة مرات بالأسبوع', val:'عدة مرات بالأسبوع', en:'Several times a week'},
        {label:'📅 نادراً', val:'نادراً', en:'Rarely'}
      ]},
      {re:/(أحس بـ|أشعر بـ|عندي شعور)/i, type:'vague_feeling', opts:[
        {label:'😣 ألم', val:'ألم', en:'Pain'},
        {label:'😰 ضيق', val:'ضيق', en:'Tightness'},
        {label:'🤢 غثيان', val:'غثيان', en:'Nausea'},
        {label:'🔥 حرقة', val:'حرقة', en:'Burning'}
      ]},
      {re:/(تعبان|تعبانة|متأثر|متأثرة|مو تمام|مو بخير)/i, type:'general', opts:[
        {label:'🤕 رأس', val:'صداع', en:'Headache'},
        {label:'🤒 حرارة', val:'حرارة', en:'Fever'},
        {label:'🤢 بطن', val:'ألم بطن', en:'Stomach'},
        {label:'💪 عضلات', val:'ألم عضلات', en:'Muscles'},
        {label:'🫁 تنفس', val:'ضيق تنفس', en:'Breathing'}
      ]}
    ];
    var _ambigState = null;
    function checkAmbiguous(text) {
      for (var i = 0; i < AMBIG_PATTERNS.length; i++) {
        var p = AMBIG_PATTERNS[i];
        if (p.re.test(text)) {
          _ambigState = {pattern: p, original: text};
          showClarifyUI(p, text);
          return true;
        }
      }
      return false;
    }
    function showClarifyUI(pattern, originalText) {
      var clarMsg = LANG === 'ar'
        ? '🤍 أبي أتأكد إني فهمتك صح.\n\nلما تقول **"' + esc(originalText) + '"**، تقصد:'
        : '🤍 I want to make sure I understand you.\n\nWhen you say **"' + esc(originalText) + '"**, you mean:';
      var clarMsgShort = LANG === 'ar'
        ? 'بس خليني أتأكد من نقطة صغيرة 🤍\nوش تقصد أكثر؟'
        : 'Just making sure I understand 🤍\nWhat do you mean exactly?';
      add(clarMsg, 'bot');
      var items = pattern.opts.map(function(o) {
        return {
          label: o.label,
          fn: function() {
            add(o.label, 'user');
            clearOpts();
            var resolved = o.val;
            if (pattern.type === 'severity' || pattern.type === 'severity_mild') {
              var symptomPart = originalText.replace(/(شوي كثير|كثير شوي|شوية كثير|كثير شوية|يعورني شوي|قليلاً|شوية|خفيف شوي)/gi, '').trim();
              if (symptomPart) resolved = symptomPart + ' ' + o.val;
              else resolved = o.val;
            } else if (pattern.type === 'timing') {
              resolved = 'دوخة ' + o.val;
            } else if (pattern.type === 'chest') {
              resolved = 'ألم صدر ' + o.val;
            } else if (pattern.type === 'general') {
              resolved = o.val;
            } else if (pattern.type === 'vague_feeling') {
              var bodyPart = originalText.replace(/(أحس بـ|أشعر بـ|عندي شعور)/gi, '').trim();
              resolved = o.val + (bodyPart ? ' ' + bodyPart : '');
            }
            state.symptoms.push(resolved);
            add(TT('added_n'), 'bot');
            _ambigState = null;
            askSymptoms();
          }
        };
      });
      items.push({
        label: TT('write_yourself_n'),
        fn: function() {
          add(TT('write_yourself_n'), 'user');
          clearOpts();
          addQ(TT('custom_n'));
          showText(TT('syms_hint'), true);
        }
      });
      showOpts(items);
    }
