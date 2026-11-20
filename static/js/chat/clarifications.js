/* SymptoSense chat — Generic clarification question banks and the clarification walk.
   Classic script: shares the page's global scope with the other files in /static/js/chat/. Load order is fixed by chat_view.py. */

    const GENERIC_CLAR={prompt:['أين تشعر بهذا العرض أو في أي جزء من الجسم يظهر؟','Where do you feel this symptom, or which part of the body does it affect?'],options:[
      {label:['الرأس أو الوجه','Head or face']},{label:['الصدر أو التنفس','Chest or breathing']},
      {label:['البطن أو الجهاز الهضمي','Abdomen or digestion']},{label:['الذراعان أو الساقان','Arms or legs']},
      {label:['أكثر من مكان','More than one area']},{label:['سأكتب المكان بالتفصيل','I will type the location'],custom:true}
    ]};
    const GENERIC_CONTEXT_CLAR={q:['هل بدأ هذا العرض فجأة أو أصبح أسوأ بسرعة؟','Did this symptom start suddenly or worsen quickly?'],
      yes:{q:['هل يصاحبه إغماء، تشوش شديد، ألم صدر، صعوبة تنفس، ضعف مفاجئ، نزيف شديد، أو صداع مفاجئ شديد؟','Does it come with fainting, severe confusion, chest pain, breathing difficulty, sudden weakness, heavy bleeding, or a sudden severe headache?'],
        yes:{safety:['عرض مفاجئ مع علامة خطر مصاحبة','Sudden symptom with an associated red flag']},no:{end:true}},no:{end:true}};
    const GENERIC_NEURO_CLAR={q:['هل بدأ العرض العصبي فجأة أو في جهة واحدة من الجسم؟','Did the neurological symptom start suddenly or affect one side of the body?'],
      yes:{q:['هل يوجد ضعف بالوجه أو الذراع أو الساق، صعوبة بالكلام، فقدان مفاجئ للرؤية، تشوش شديد، أو صداع مفاجئ شديد؟','Is there facial/arm/leg weakness, trouble speaking, sudden vision loss, severe confusion, or a sudden severe headache?'],
        yes:{safety:['عرض عصبي مفاجئ مع علامة خطر — يحتاج تقييمًا عاجلًا','Sudden neurological symptom with a red flag — needs urgent assessment']},no:{end:true}},
      no:{q:['هل العرض مستمر أو يتكرر ويؤثر في المشي أو التوازن أو النشاط المعتاد؟','Is it persistent or recurring and affecting walking, balance, or usual activity?'],yes:{end:true},no:{end:true}}};
    const GENERIC_CARDIO_RESP_CLAR={q:['هل يوجد الآن ألم أو ضغط شديد في الصدر، صعوبة شديدة في التنفس، ازرقاق الشفاه، أو إغماء؟','Is there severe chest pain/pressure, severe breathing difficulty, blue lips, or fainting right now?'],
      yes:{safety:['أعراض صدر أو تنفس مع علامة خطر — تحتاج تقييمًا عاجلًا','Chest or breathing symptoms with a red flag — need urgent assessment']},
      no:{q:['هل يظهر العرض مع المجهود أو يوقظك من النوم أو يزداد عند الاستلقاء؟','Does it happen with exertion, wake you from sleep, or worsen when lying down?'],yes:{end:true},no:{end:true}}};
    const GENERIC_GI_CLAR={q:['هل يوجد ألم بطن شديد جدًا أو مفاجئ، دم في القيء، براز أسود أو دموي، أو عدم القدرة على الاحتفاظ بالسوائل؟','Is there sudden/very severe abdominal pain, blood in vomit, black/bloody stool, or inability to keep fluids down?'],
      yes:{safety:['أعراض هضمية مع علامة خطر — تحتاج تقييمًا عاجلًا','Digestive symptoms with a red flag — need urgent assessment']},
      no:{q:['هل يرتبط العرض بالأكل أو دواء جديد، أو يتكرر بعد نوع معين من الطعام؟','Is it related to meals, a new medicine, or a particular food?'],yes:{end:true},no:{end:true}}};
    const GENERIC_URINARY_CLAR={q:['هل يوجد مع العرض حرارة أو قشعريرة أو ألم في الخاصرة/الظهر تحت الأضلاع؟','Is there fever, chills, or pain in the side/back under the ribs?'],
      yes:{end:true},no:{q:['هل يوجد دم في البول أو صعوبة شديدة أو عدم قدرة على التبول؟','Is there blood in the urine or major difficulty/inability to urinate?'],yes:{end:true},no:{end:true}}};
    const GENERIC_SKIN_CLAR={q:['هل يصاحب العرض الجلدي صعوبة تنفس أو تورم في الشفاه أو اللسان أو الحلق؟','Does the skin symptom come with breathing difficulty or swelling of the lips, tongue, or throat?'],
      yes:{safety:['علامة تحسس شديد محتملة — تحتاج مساعدة عاجلة','Possible severe allergic reaction — urgent help is needed']},
      no:{q:['هل ينتشر بسرعة، أو يصاحبه حمى شديدة، أو ألم شديد، أو تقرحات في الفم/العين؟','Is it spreading quickly or accompanied by high fever, severe pain, or sores in the mouth/eyes?'],yes:{end:true},no:{end:true}}};
    const GENERIC_EYE_CLAR={q:['هل حدث فقدان مفاجئ للنظر أو ألم شديد في العين أو إصابة كيميائية/جسم غريب؟','Was there sudden vision loss, severe eye pain, or a chemical/foreign-body injury?'],
      yes:{safety:['عرض عيني مع علامة خطر — يحتاج تقييمًا عاجلًا','Eye symptom with a red flag — needs urgent assessment']},
      no:{q:['هل يوجد احمرار أو إفرازات أو حساسية شديدة للضوء؟','Is there redness, discharge, or marked sensitivity to light?'],yes:{end:true},no:{end:true}}};
    const GENERIC_ENT_CLAR={q:['هل توجد صعوبة في التنفس أو البلع، سيلان لعاب لعدم القدرة على البلع، أو تورم سريع في الوجه/الرقبة؟','Is there breathing or swallowing difficulty, drooling because you cannot swallow, or rapidly increasing face/neck swelling?'],
      yes:{safety:['عرض في الحلق أو الوجه مع علامة خطر — يحتاج مساعدة عاجلة','Throat/face symptom with a red flag — urgent help is needed']},
      no:{q:['هل توجد حرارة، إفرازات، فقدان سمع مفاجئ، أو ألم شديد مستمر؟','Is there fever, discharge, sudden hearing loss, or persistent severe pain?'],yes:{end:true},no:{end:true}}};
    const GENERIC_FEMALE_REPRODUCTIVE_CLAR={q:['هل يوجد احتمال حمل أو حمل مؤكد مع نزيف أو ألم في الحوض/البطن؟','Is pregnancy possible or confirmed with bleeding or pelvic/abdominal pain?'],
      yes:{q:['هل النزيف غزير، الألم شديد أو في جهة واحدة، أو يوجد دوخة شديدة أو إغماء؟','Is bleeding heavy, pain severe or one-sided, or is there severe dizziness/fainting?'],yes:{safety:['نزيف أو ألم مع احتمال حمل وعلامة خطر — يحتاج تقييمًا عاجلًا','Bleeding/pain with possible pregnancy and a red flag — needs urgent assessment']},no:{end:true}},
      no:{q:['هل يوجد نزيف غير معتاد جدًا، ألم شديد، حرارة، أو إفرازات ذات رائحة غير معتادة؟','Is there very unusual bleeding, severe pain, fever, or unusual-smelling discharge?'],yes:{end:true},no:{end:true}}};
    const GENERIC_MALE_REPRODUCTIVE_CLAR={q:['هل يوجد ألم شديد ومفاجئ في خصية واحدة، أو تورم واضح، أو غثيان/قيء مع ألم الخصية؟','Is there sudden severe pain in one testicle, obvious swelling, or nausea/vomiting with testicular pain?'],
      yes:{safety:['ألم خصية مفاجئ وشديد قد يحتاج تقييمًا عاجلًا الآن','Sudden severe testicular pain may need urgent assessment now']},
      no:{q:['هل يوجد تورم أو كتلة جديدة، إفرازات، حرارة، حرقة أو صعوبة في التبول، أو ألم يمتد للأربية/أسفل البطن؟','Is there a new swelling/lump, discharge, fever, burning or difficulty urinating, or pain spreading to the groin/lower abdomen?'],yes:{end:true},no:{end:true}}};
    const GENERIC_MSK_CLAR={q:['هل بدأ الألم أو التورم بعد إصابة، سقوط، التواء، أو مجهود واضح؟','Did the pain or swelling start after an injury, fall, twist, or clear exertion?'],
      yes:{q:['هل يوجد تشوه واضح، نزيف شديد، خدر/ضعف جديد، أو عدم القدرة على استخدام الطرف؟','Is there obvious deformity, heavy bleeding, new numbness/weakness, or inability to use the limb?'],yes:{safety:['إصابة مع علامة خطر — تحتاج تقييمًا عاجلًا','Injury with a red flag — needs urgent assessment']},no:{end:true}},
      no:{q:['هل المنطقة حمراء أو ساخنة أو متورمة جدًا أو يصاحبها حمى؟','Is the area red, hot, very swollen, or accompanied by fever?'],yes:{end:true},no:{end:true}}};
    const GENERIC_METABOLIC_CLAR={q:['هل يوجد عطش شديد مع تبول كثير، قيء، نعاس أو تشوش، أو تنفس سريع/عميق؟','Is there marked thirst with frequent urination, vomiting, drowsiness/confusion, or fast/deep breathing?'],
      yes:{q:['هل لديك سكري معروف أو قراءة سكر مرتفعة جدًا/منخفضة جدًا؟','Do you have known diabetes or a very high/very low glucose reading?'],yes:{safety:['أعراض عامة/سكر مع علامة خطر — تحتاج تقييمًا عاجلًا','General/glucose-related symptoms with a red flag — need urgent assessment']},no:{end:true}},no:{end:true}};
    const GENERIC_SLEEP_MOOD_CLAR={q:['هل هذا التغير مستمر ويؤثر بوضوح على النوم أو الدراسة/العمل أو نشاطك اليومي؟','Is this change persistent and clearly affecting sleep, study/work, or daily activity?'],
      yes:{q:['هل تشعر أنك غير آمن على نفسك أو لديك أفكار بإيذاء نفسك؟','Do you feel unsafe with yourself or have thoughts of self-harm?'],yes:{safety:['أفكار إيذاء النفس تحتاج دعماً عاجلًا الآن','Thoughts of self-harm need urgent support now']},no:{end:true}},no:{end:true}};
    function genericClarForSymptom(symptom){
      const x=String(symptom||'').toLowerCase();
      const neuro=/إغماء|اغماء|فقدان الوعي|غشي|دوخ|دوار|تنميل|خدر|ضعف|تشنج|اختلاج|ارتباك|تشوش|توازن|ذاكر|كلام|رؤي|نظر|faint|syncope|dizz|numb|tingl|weak|seizure|convuls|confus|balance|memory|speech|vision/i;
      const cardioResp=/صدر|خفقان|نبض|تنفس|نفس|صفير|أزيز|ازيز|زرقة|ازرقاق|سعال دم|بلغم دم|chest|palpitat|heartbeat|breath|wheez|cyanosis|coughing blood|blood in phlegm/i;
      const gi=/بطن|معد|حموض|ارتجاع|غثيان|قيء|استفراغ|اسهال|إسهال|امساك|إمساك|براز|غازات|انتفاخ البطن|بلع|abdom|stomach|heartburn|reflux|nause|vomit|diarr|constipat|stool|bloat|gas|swallow|dysphagia/i;
      const urinary=/بول|تبول|خاصر|كلو|كلى|urine|urinat|dysuria|flank|kidney/i;
      const femaleReproductive=/دور[هة]|حيض|طمث|مهبل|حمل|نزيف مهبلي|period|menstrual|vaginal|pregnan/i;
      const maleReproductive=/خصي|خصية|خصيت|صفن|قضيب|بروستات|أربي|اربي|testic|scrot|penis|prostat|groin/i;
      const pelvic=/حوض|pelvic/i;
      const skin=/جلد|طفح|حكة|حساسي|شرى|ارتكار|كتلة|جرح|حرق|skin|rash|itch|hives|urticaria|lump|wound|burn/i;
      const eye=/عين|عيون|نظر|رؤية|زغلل|eye|vision|blurred/i;
      const ent=/أذن|اذن|سمع|طنين|حلق|بلع|صوت|اسنان|أسنان|فم|ear|hearing|tinnitus|throat|swallow|hoarse|tooth|mouth/i;
      const msk=/ظهر|رقب|مفصل|عضل|كتف|ذراع|ركب|كاحل|قدم|رجل|ساق|اصاب|إصاب|كدم|التواء|سقوط|back|neck|joint|muscle|shoulder|arm|knee|ankle|foot|leg|injury|bruise|sprain|fall/i;
      const metabolic=/عطش|تعرق|وزن|شهية|سكر|رجفة|رعشة|thirst|sweat|weight|appetite|glucose|tremor|shak/i;
      const sleepMood=/أرق|نوم|نعاس|قلق|هلع|توتر|حزن|مزاج|insomnia|sleep|sleepiness|anxiety|panic|mood|depress/i;
      const nonLocal=/إغماء|اغماء|فقدان الوعي|غشي|دوخ|غثيان|قيء|استفراغ|اسهال|إسهال|امساك|إمساك|حمى|حرارة|تعب|ارهاق|إرهاق|خفقان|تشنج|اختلاج|ارتباك|تشوش|فقدان الشهية|نقص وزن|تعرق|رجفة|faint|syncope|dizz|nause|vomit|diarr|constipat|fever|fatigue|palpitat|seizure|convuls|confus|appetite|weight loss|sweat|tremor/i;
      const locationUseful=/ألم|الم|وجع|حكة|طفح|تورم|تنميل|خدر|جرح|كتلة|حرقان|حرقة|pain|ache|itch|rash|swelling|numb|tingl|wound|lump|burning/i;
      if(sexIsMale() && (maleReproductive.test(x) || pelvic.test(x))) return GENERIC_MALE_REPRODUCTIVE_CLAR;
      if(sexIsFemale() && (femaleReproductive.test(x) || pelvic.test(x))) return GENERIC_FEMALE_REPRODUCTIVE_CLAR;
      // If sex is unavailable, keep explicit reproductive wording grounded in the
      // symptom instead of guessing; otherwise continue with the generic path.
      if(!sexIsMale() && !sexIsFemale() && femaleReproductive.test(x)) return GENERIC_FEMALE_REPRODUCTIVE_CLAR;
      if(!sexIsMale() && !sexIsFemale() && maleReproductive.test(x)) return GENERIC_MALE_REPRODUCTIVE_CLAR;
      if(eye.test(x)) return GENERIC_EYE_CLAR;
      if(cardioResp.test(x)) return GENERIC_CARDIO_RESP_CLAR;
      if(neuro.test(x)) return GENERIC_NEURO_CLAR;
      if(urinary.test(x)) return GENERIC_URINARY_CLAR;
      if(gi.test(x)) return GENERIC_GI_CLAR;
      if(skin.test(x)) return GENERIC_SKIN_CLAR;
      if(ent.test(x)) return GENERIC_ENT_CLAR;
      if(msk.test(x)) return GENERIC_MSK_CLAR;
      if(metabolic.test(x)) return GENERIC_METABOLIC_CLAR;
      if(sleepMood.test(x)) return GENERIC_SLEEP_MOOD_CLAR;
      if(nonLocal.test(x)) return GENERIC_CONTEXT_CLAR;
      return locationUseful.test(x) ? GENERIC_CLAR : GENERIC_CONTEXT_CLAR;
    }
    // ---------------- Missing-symptom clarification ----------------
    let clarQueue = [], clarIndex = 0, clarCustomNext = null;
    let followupTotal = 0;
    function nextClarNode() {
      if (clarIndex < clarQueue.length) walkClarNode(clarQueue[clarIndex++]);
      else if(state.quick_mode) showDataQualityGate(); else startRedflagScreens();
    }
    function walkClarNode(node) {
      if (!node) { nextClarNode(); return; }
      if (node.safety) {
        const label = LANG === 'en' ? node.safety[1] : node.safety[0];
        addHtml('<div class="warn">🚨 ' + esc(label) + '</div>', 'bot');
        showEmergency(clarEmergencyResult(label));
        return;
      }
      if (node.options) {
        const prompt=node.prompt?(LANG==='en'?node.prompt[1]:node.prompt[0]):(LANG==='ar'?'أين تشعر بالتنميل أو الخدر؟ اختر الوصف الأقرب.':'Where do you feel the numbness or tingling? Choose the closest description.');
        focusStepQuestion('📍 ' + prompt);
        showOpts(node.options.map(function(opt){
          const label=LANG==='en'?opt.label[1]:opt.label[0];
          return {label:label,fn:function(){
            add(label,'user');
            if(opt.remove){const rm=(Array.isArray(opt.remove)?opt.remove:[]);state.symptoms=state.symptoms.filter(function(x){return rm.indexOf(x)===-1;});}
            if(opt.add){const symptom=LANG==='en'?opt.add[1]:opt.add[0];if(state.symptoms.indexOf(symptom)===-1)state.symptoms.push(symptom);}
            if(opt.note){const note=LANG==='en'?opt.note[1]:opt.note[0];state.notes += (state.notes?' ':'') + note;}
            if(opt.location !== false) state.location=label;
            if(opt.custom){state.step='clarification';clarCustomNext=opt.next||null;showText(LANG==='ar'?'اكتب المكان أو التفصيل الذي تقصده':'Type the location or detail you mean');return;}
            walkClarNode(opt.next||null);
          }};
        }));
        return;
      }
      if (node.q) {
        if (followupTotal >= FOLLOWUP_TOTAL_MAX) { nextClarNode(); return; }
        const q = LANG === 'en' ? node.q[1] : node.q[0];
        adaptiveQuestionNo += 1;
        followupTotal += 1;
        addHtml('<div class="adaptive-step">'+esc((LANG==='ar'?'السؤال ':'Question ')+adaptiveQuestionNo+(LANG==='ar'?' · يتكيف حسب إجاباتك':' · adapts to your answers'))+'</div>','bot');
        focusStepQuestion('🧩 ' + q);
        showOpts([
          {label:TT('clar_yes'), fn:()=>{
            add(TT('clar_yes'),'user');
            state.notes += (state.notes ? ' ' : '') + q + ' -> ' + (LANG==='en' ? 'Yes' : 'نعم');
            walkClarNode(node.yes || null);
          }},
          {label:TT('clar_no'), fn:()=>{
            add(TT('clar_no'),'user');
            state.notes += (state.notes ? ' ' : '') + (LANG==='en' ? 'A follow-up symptom was denied.' : 'تم نفي عرض متابعة.');
            walkClarNode(node.no || null);
          }}
        ]);
        return;
      }
      nextClarNode();
    }
