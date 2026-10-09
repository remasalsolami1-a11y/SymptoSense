"""V61 bilingual health-search expansion.

All entries are educational, non-diagnostic, and linked to official / high-
authority references. Reviewed 2026-09-20.
"""

REVIEW_DATE = "2026-09-20"


def src(org, title, url):
    return {
        "name": f"{title} — {org}", "title": title,
        "organization": org, "source_name": org,
        "url": url, "last_verified": REVIEW_DATE,
    }


def topic(emoji, category, aliases, source, ar, en):
    return {
        "emoji": emoji, "category": category, "aliases": aliases,
        "sources": [source], "last_reviewed": REVIEW_DATE,
        "population_scope": "general educational information; age, pregnancy, medicines, and medical history can change interpretation",
        "causes_label": {"ar": "أسباب أو سياقات محتملة", "en": "Possible causes or contexts"},
        "ar": ar, "en": en,
    }


EXTRA_SEARCH_KB_V3 = {
    "heat_exhaustion": topic(
        "☀️", "symptom", ["اجهاد حراري", "إجهاد حراري", "تعب من الحر", "دوخة من الحر", "صداع من الحر", "heat exhaustion", "heat illness"],
        src("CDC", "Heat-related illnesses", "https://www.cdc.gov/niosh/heat-stress/about/illnesses.html"),
        {"title":"الإجهاد الحراري","what":"قد يحدث بعد التعرض للحر وفقد الماء والملح، وقد يسبب تعرقًا شديدًا ودوخة وصداعًا وغثيانًا وضعفًا.","causes":["التعرض لحرارة مرتفعة","التعرق وفقد السوائل والأملاح","المجهود في بيئة حارة"],"worry":"الارتباك أو التشنج أو فقدان الوعي أو انهيار الشخص في الحر قد يشير إلى ضربة حر ويحتاج طوارئ.","doctor":"انتقل لمكان أبرد وأوقف المجهود، واطلب تقييمًا إذا لم تتحسن الأعراض سريعًا أو ظهرت علامات الخطر."},
        {"title":"Heat exhaustion","what":"Heat exhaustion can follow heat exposure with loss of water and salt, causing heavy sweating, dizziness, headache, nausea, and weakness.","causes":["High heat exposure","Fluid and salt loss from sweating","Exertion in hot conditions"],"worry":"Confusion, seizure, loss of consciousness, or collapse in heat can signal heat stroke and needs emergency care.","doctor":"Move to a cooler place, stop exertion, and seek care if symptoms do not improve promptly or warning signs appear."}),
    "heatstroke": topic(
        "🚨", "symptom", ["ضربة شمس", "ضربة حر", "حراره عاليه مع لخبطه", "heat stroke", "heatstroke"],
        src("CDC", "Heat-related illnesses", "https://www.cdc.gov/niosh/heat-stress/about/illnesses.html"),
        {"title":"ضربة الحر","what":"ضربة الحر أخطر أمراض الحرارة وتحدث عندما يفشل الجسم في التحكم بدرجته، وقد تسبب اضطراب الوعي أو تشنجًا أو فقدان الوعي.","causes":["التعرض الشديد للحر","المجهود في حرارة مرتفعة","فشل التبريد الطبيعي للجسم"],"worry":"هي حالة طبية طارئة؛ الارتباك أو التشنج أو فقدان الوعي مع الحر يستدعي الاتصال بالطوارئ فورًا.","doctor":"اطلب الطوارئ فورًا وابدأ التبريد الآمن أثناء انتظار المساعدة."},
        {"title":"Heat stroke","what":"Heat stroke is the most serious heat illness and occurs when the body can no longer control its temperature; confusion, seizures, or unconsciousness can occur.","causes":["Severe heat exposure","Exertion in high heat","Failure of normal body cooling"],"worry":"This is a medical emergency. Confusion, seizure, or loss of consciousness with heat exposure requires emergency services now.","doctor":"Call emergency services immediately and begin safe cooling while help arrives."}),
    "motion_sickness": topic(
        "🚗", "symptom", ["دوار الحركة", "دوخة بالسياره", "غثيان بالسيارة", "اغثي بالسفر", "motion sickness", "car sickness", "travel sickness"],
        src("NHS", "Motion sickness", "https://www.nhs.uk/conditions/motion-sickness/"),
        {"title":"دوار الحركة","what":"قد يسبب السفر بالسيارة أو القارب أو الطائرة دوخة أو غثيانًا أو قيئًا أو صداعًا.","causes":["الحركة المتكررة أثناء السفر","اختلاف إشارات الحركة بين العين والأذن الداخلية"],"worry":"إذا استمرت الدوخة خارج السفر أو ظهرت معها أعراض عصبية أو فقدان سمع مفاجئ فاطلب تقييمًا عاجلًا.","doctor":"يمكن تقليل الحركة والنظر لنقطة ثابتة؛ استشر مختصًا إذا كانت النوبات متكررة أو شديدة."},
        {"title":"Motion sickness","what":"Travel by car, boat, plane, or train can cause dizziness, nausea, vomiting, headache, and sweating.","causes":["Repeated movement during travel","Conflicting motion signals from the eyes and inner ear"],"worry":"Persistent dizziness outside travel, neurological symptoms, or sudden hearing loss needs urgent assessment.","doctor":"Reduce motion and focus on a fixed point; seek professional advice if episodes are frequent or severe."}),
    "peptic_ulcer": topic(
        "🫃", "symptom", ["قرحة المعدة", "قرحه المعده", "قرحة الاثني عشر", "حرقان فم المعدة", "peptic ulcer", "stomach ulcer"],
        src("NIDDK", "Symptoms & Causes of Peptic Ulcers", "https://www.niddk.nih.gov/health-information/digestive-diseases/peptic-ulcers-stomach-ulcers/symptoms-causes"),
        {"title":"قرحة المعدة أو الاثني عشر","what":"قد تسبب ألمًا أو حرقة أعلى البطن، أو الشبع بسرعة، أو الغثيان والانتفاخ، لكن الأعراض وحدها لا تؤكد القرحة.","causes":["عدوى H. pylori","بعض مضادات الالتهاب غير الستيرويدية","أسباب أقل شيوعًا"],"worry":"البراز الأسود القطراني أو القيء الدموي أو ألم شديد مفاجئ أو إغماء يستدعي تقييمًا عاجلًا.","doctor":"راجع الطبيب إذا كانت الأعراض متكررة أو مستمرة، وخاصة مع استخدام مسكنات مضادة للالتهاب."},
        {"title":"Peptic ulcer","what":"Peptic ulcers can cause upper abdominal pain or burning, early fullness, nausea, and bloating, but symptoms alone do not confirm an ulcer.","causes":["H. pylori infection","NSAID use","Less common causes"],"worry":"Black tarry stool, vomiting blood, sudden severe pain, or fainting needs urgent care.","doctor":"Seek medical review for recurrent or persistent symptoms, especially with NSAID use."}),
    "endometriosis": topic(
        "🌸", "symptom", ["بطانة الرحم المهاجرة", "اندومتريوزس", "الم دورة شديد", "الم الحوض مع الدورة", "endometriosis"],
        src("NICHD", "Endometriosis symptoms", "https://www.nichd.nih.gov/health/topics/endometri/conditioninfo/symptoms"),
        {"title":"بطانة الرحم المهاجرة","what":"قد تسبب ألمًا شديدًا مع الدورة، وألم الحوض أو أثناء/بعد الجماع، وأحيانًا أعراضًا هضمية أو بولية مرتبطة بالدورة.","causes":["نسيج شبيه ببطانة الرحم خارج الرحم","التهاب وندبات بالحوض"],"worry":"ألم حوض شديد مفاجئ أو نزيف غزير مع دوخة أو إغماء يحتاج تقييمًا عاجلًا.","doctor":"راجعي مختصًا إذا كانت آلام الدورة أو الحوض تؤثر في حياتك أو تزداد مع الوقت."},
        {"title":"Endometriosis","what":"Endometriosis can cause severe menstrual cramps, pelvic pain, pain during/after sex, and sometimes bowel or urinary symptoms linked to periods.","causes":["Endometrium-like tissue outside the uterus","Inflammation and pelvic scarring"],"worry":"Sudden severe pelvic pain or heavy bleeding with dizziness or fainting needs urgent assessment.","doctor":"Seek medical review if period or pelvic pain affects daily life or is worsening."}),
    "pcos": topic(
        "🩺", "symptom", ["تكيس المبايض", "متلازمة تكيس المبايض", "pcos", "pmos", "دورة غير منتظمة مع شعر زائد", "حب شباب مع دورة غير منتظمة", "دورتي غير منتظمة", "شعر زائد مع دورة غير منتظمة"],
        src("NICHD", "PCOS symptoms", "https://www.nichd.nih.gov/health/topics/pcos/conditioninfo/symptoms"),
        {"title":"متلازمة تكيس المبايض (PCOS/PMOS)","what":"قد ترتبط بعدم انتظام الدورة، وزيادة شعر الوجه أو الجسم، وحب الشباب أو البشرة الدهنية، وتغيرات الوزن. التشخيص يحتاج تقييمًا طبيًا.","causes":["اختلال هرموني متعدد العوامل","عوامل وراثية وبيئية"],"worry":"النزيف الغزير جدًا أو ألم الحوض الحاد المفاجئ يحتاج تقييمًا عاجلًا.","doctor":"راجعي الطبيب إذا تكرر عدم انتظام الدورة أو ظهرت علامات زيادة الأندروجين أو صعوبة حمل."},
        {"title":"PCOS/PMOS","what":"PCOS/PMOS may involve irregular periods, excess facial/body hair, acne or oily skin, and weight changes. Diagnosis requires clinical assessment.","causes":["Multifactorial hormonal imbalance","Genetic and environmental factors"],"worry":"Very heavy bleeding or sudden severe pelvic pain needs urgent assessment.","doctor":"Seek medical review for persistent menstrual irregularity, androgen-related symptoms, or fertility concerns."}),
    "food_allergy": topic(
        "🥜", "symptom", ["حساسية طعام", "حساسية اكل", "تحسس من الاكل", "فمي يحكني بعد الاكل", "تورم بعد الاكل", "food allergy", "allergic to food"],
        src("NIAID", "Food Allergy", "https://pubweb-prod.niaid.nih.gov/diseases-conditions/food-allergy"),
        {"title":"حساسية الطعام","what":"قد تسبب حساسية الطعام حكة بالفم أو شرى أو تورمًا أو أعراضًا هضمية بعد طعام معين. تحديد المسبب يحتاج تقييمًا.","causes":["استجابة مناعية لمكوّن غذائي معين"],"worry":"تورم اللسان أو الحلق أو صعوبة التنفس بعد الطعام حالة طارئة.","doctor":"تجنب الطعام المشتبه به حتى التقييم، واطلب مساعدة طبية عاجلة عند أعراض التنفس أو الحلق."},
        {"title":"Food allergy","what":"Food allergy can cause mouth itching, hives, swelling, or gastrointestinal symptoms after a particular food. The trigger needs proper assessment.","causes":["An immune response to a food component"],"worry":"Tongue/throat swelling or breathing difficulty after food is an emergency.","doctor":"Avoid the suspected food until assessed and get emergency help for airway or breathing symptoms."}),
    "dry_eye": topic(
        "👁️", "symptom", ["جفاف العين", "عيوني ناشفه", "حرقان العين", "احس رمل بعيني", "dry eye", "dry eyes", "gritty eyes"],
        src("NEI", "Dry Eye", "https://www.nei.nih.gov/eye-health-information/eye-conditions-and-diseases/dry-eye"),
        {"title":"جفاف العين","what":"قد يسبب الجفاف إحساسًا بالحرقة أو الرمل أو الخشونة، واحمرارًا أو ضبابية مؤقتة في الرؤية.","causes":["قلة أو ضعف جودة الدموع","العمر وبعض الأدوية","بيئة جافة أو شاشات لفترات طويلة"],"worry":"ألم شديد أو احمرار شديد أو فقدان/تغير مفاجئ في الرؤية يحتاج تقييمًا عاجلًا.","doctor":"راجع مختصًا إذا استمرت الأعراض أو أثرت في الرؤية، خصوصًا مع العدسات اللاصقة."},
        {"title":"Dry eye","what":"Dry eye can cause burning, scratchy or gritty sensations, redness, and temporary blurry vision.","causes":["Too few or poor-quality tears","Age or some medicines","Dry environments or prolonged screen use"],"worry":"Severe pain, intense redness, or sudden vision change needs urgent assessment.","doctor":"Seek review if symptoms persist or affect vision, especially if you wear contact lenses."}),
    "hearing_loss": topic(
        "👂", "symptom", ["ضعف السمع", "ما اسمع كويس", "السمع مكتوم", "hearing loss", "muffled hearing"],
        src("NIDCD", "Adult Hearing Health Care", "https://www.nidcd.nih.gov/health/adult-hearing-health-care"),
        {"title":"ضعف السمع","what":"قد يظهر ضعف السمع كصعوبة فهم الكلام أو الحاجة لرفع الصوت أو سماع الأصوات بشكل مكتوم.","causes":["التعرض للضوضاء","التقدم بالعمر","أسباب بالأذن الخارجية أو الوسطى أو الداخلية"],"worry":"فقدان السمع المفاجئ خلال ساعات أو أيام يحتاج تقييمًا طبيًا عاجلًا.","doctor":"اطلب فحص سمع إذا كان الضعف مستمرًا أو يؤثر في التواصل."},
        {"title":"Hearing loss","what":"Hearing loss may appear as difficulty understanding speech, needing higher volume, or muffled sound.","causes":["Noise exposure","Age-related changes","Outer, middle, or inner ear causes"],"worry":"Sudden hearing loss over hours or days needs urgent medical assessment.","doctor":"Arrange a hearing assessment if the change persists or affects communication."}),
    "sudden_hearing_loss": topic(
        "🚨", "symptom", ["فقدان سمع مفاجئ", "فقدت السمع فجأة", "السمع راح فجأة", "ما اسمع من اذن وحده فجأة", "sudden hearing loss", "sudden deafness"],
        src("NIDCD", "Sudden Deafness", "https://www.nidcd.nih.gov/health/sudden-deafness"),
        {"title":"فقدان السمع المفاجئ","what":"الفقدان السريع للسمع في أذن واحدة أو كلتيهما قد يحدث خلال ساعات أو أيام، ولا ينبغي افتراض أنه مجرد شمع أو احتقان.","causes":["أسباب متعددة وقد لا يُعرف السبب مباشرة"],"worry":"يحتاج تقييمًا طبيًا عاجلًا؛ التأخير قد يقلل فرصة الاستفادة من العلاج في بعض الحالات.","doctor":"اطلب تقييمًا طبيًا اليوم/فورًا عند فقدان السمع المفاجئ."},
        {"title":"Sudden hearing loss","what":"Rapid loss of hearing in one or both ears can occur over hours or days and should not be assumed to be wax or congestion.","causes":["Multiple possible causes; often no immediate cause is identified"],"worry":"Urgent medical assessment is needed; delay can reduce treatment effectiveness in some cases.","doctor":"Seek same-day/immediate medical evaluation for sudden hearing loss."}),
    "acne": topic(
        "🧴", "symptom", ["حب الشباب", "حبوب الوجه", "رؤوس سوداء", "رؤوس بيضاء", "acne", "pimples", "blackheads"],
        src("NHS", "Acne", "https://www.nhs.uk/conditions/acne/"),
        {"title":"حب الشباب","what":"حب الشباب حالة شائعة تسبب رؤوسًا سوداء أو بيضاء وبثورًا وقد تكون بعض البثور عميقة ومؤلمة.","causes":["انسداد بصيلات الشعر","زيادة الدهون","تغيرات هرمونية"],"worry":"العقد المؤلمة أو الندبات أو التأثير النفسي الكبير يستدعي مراجعة مختص.","doctor":"استشر الصيدلي للحالات الخفيفة وراجع الطبيب للحالات المتوسطة أو الشديدة أو التي تترك ندبات."},
        {"title":"Acne","what":"Acne is a common condition causing blackheads, whiteheads, pimples, and sometimes painful deep nodules.","causes":["Blocked hair follicles","Excess sebum","Hormonal changes"],"worry":"Painful nodules, scarring, or major psychological impact warrants professional review.","doctor":"Ask a pharmacist for mild acne and seek medical review for moderate/severe acne or scarring."}),
    "scabies": topic(
        "🧤", "symptom", ["الجرب", "حكة تزيد بالليل", "حكة بين الاصابع", "scabies", "itching worse at night"],
        src("NHS", "Scabies", "https://www.nhs.uk/conditions/Scabies/"),
        {"title":"الجرب","what":"الجرب طفح شديد الحكة يسببه عث صغير وينتقل غالبًا بالمخالطة الجلدية القريبة؛ الحكة غالبًا تزداد ليلًا.","causes":["عدوى بعث الجرب","المخالطة الجلدية القريبة"],"worry":"طفح متقشر شديد لدى ضعيف المناعة أو علامات التهاب جلدي يحتاج مراجعة طبية.","doctor":"استشر الصيدلي أو الطبيب للعلاج المناسب وللتعامل مع المخالطين وتقليل الانتقال."},
        {"title":"Scabies","what":"Scabies is an intensely itchy rash caused by mites and often spreads through close skin contact; itching is commonly worse at night.","causes":["Scabies mite infestation","Close skin contact"],"worry":"Crusted rash in an immunocompromised person or signs of skin infection need medical review.","doctor":"Seek pharmacist or medical advice for treatment and management of close contacts."}),
    "outer_ear_infection": topic(
        "👂", "symptom", ["التهاب الاذن الخارجية", "الم الاذن لما المسها", "صديد من الاذن", "otitis externa", "swimmer's ear", "outer ear infection"],
        src("NHS", "Ear infections", "https://www.nhs.uk/conditions/ear-infections/"),
        {"title":"التهاب قناة الأذن الخارجية","what":"قد يسبب ألمًا داخل قناة الأذن يزداد عند لمس الأذن أو تحريكها، وأحيانًا إفرازات أو سمعًا مكتومًا.","causes":["تهيّج قناة الأذن","دخول الماء","عدوى بكتيرية أو فطرية"],"worry":"ألم شديد أو تورم ممتد أو حرارة عامة أو ضعف مناعة يحتاج تقييمًا مبكرًا.","doctor":"تجنب إدخال أدوات داخل الأذن وراجع مختصًا إذا استمر الألم أو ظهرت إفرازات أو تغير سمع."},
        {"title":"Outer ear infection","what":"Otitis externa can cause ear-canal pain that worsens when the ear is touched or moved, sometimes with discharge or muffled hearing.","causes":["Ear-canal irritation","Water exposure","Bacterial or fungal infection"],"worry":"Severe pain, spreading swelling, fever, or immunocompromise needs prompt assessment.","doctor":"Avoid inserting objects into the ear and seek review for persistent pain, discharge, or hearing change."}),
    "sinusitis": topic(
        "🤧", "symptom", ["التهاب الجيوب", "الجيوب الانفية", "ضغط الجيوب", "sinusitis", "sinus infection"],
        src("NHS", "Sinusitis", "https://www.nhs.uk/conditions/sinusitis-sinus-infection/"),
        {"title":"التهاب الجيوب الأنفية","what":"قد يسبب احتقانًا وضغطًا أو ألمًا بالوجه مع إفرازات أنفية ونقص الشم، وغالبًا يأتي بعد نزلة برد.","causes":["عدوى فيروسية","التهاب الجيوب بعد الزكام","أسباب أقل شيوعًا"],"worry":"تورم حول العين أو تغير الرؤية أو صداع شديد جدًا أو تدهور سريع يحتاج تقييمًا عاجلًا.","doctor":"راجع مختصًا إذا استمرت الأعراض أو تكررت أو كانت شديدة."},
        {"title":"Sinusitis","what":"Sinusitis can cause nasal blockage, facial pressure/pain, discharge, and reduced smell, often after a cold.","causes":["Viral infection","Post-cold sinus inflammation","Less common causes"],"worry":"Swelling around the eye, vision changes, severe headache, or rapid deterioration needs urgent assessment.","doctor":"Seek review if symptoms persist, recur, or are severe."}),
    "kidney_stones": topic(
        "🪨", "symptom", ["حصوة كلى", "حصى الكلى", "الم الخاصرة مع دم بالبول", "kidney stone", "kidney stones"],
        src("NIDDK", "Symptoms & Causes of Kidney Stones", "https://www.niddk.nih.gov/health-information/urologic-diseases/kidney-stones/symptoms-causes"),
        {"title":"حصى الكلى","what":"قد تسبب حصى الكلى ألمًا شديدًا بالخاصرة أو الجانب يمتد أحيانًا للأسفل مع غثيان أو دم في البول.","causes":["تكوّن بلورات في البول","الجفاف وبعض عوامل الغذاء أو الاستعداد"],"worry":"ألم شديد مع حرارة أو قشعريرة أو قلة بول يحتاج تقييمًا عاجلًا.","doctor":"راجع الطبيب للألم الشديد أو المتكرر أو وجود دم بالبول."},
        {"title":"Kidney stones","what":"Kidney stones can cause severe flank/side pain, sometimes radiating downward, with nausea or blood in urine.","causes":["Crystal formation in urine","Dehydration and other risk factors"],"worry":"Severe pain with fever, chills, or reduced urination needs urgent assessment.","doctor":"Seek medical review for severe/recurrent pain or blood in urine."}),
    "gallstones": topic(
        "🟡", "symptom", ["حصوة المراره", "حصى المرارة", "الم تحت الضلع اليمين بعد الاكل", "gallstones", "gallstone pain"],
        src("NHS", "Gallstones", "https://www.nhs.uk/conditions/gallstones/"),
        {"title":"حصى المرارة","what":"قد تسبب حصى المرارة ألمًا قويًا أعلى يمين البطن أو منتصفه، وأحيانًا بعد الطعام، وقد يصاحبه غثيان.","causes":["حصوات داخل المرارة أو القنوات الصفراوية"],"worry":"ألم مستمر مع حرارة أو اصفرار الجلد/العين أو قيء متكرر يحتاج تقييمًا عاجلًا.","doctor":"راجع الطبيب إذا تكررت نوبات الألم أو كانت شديدة."},
        {"title":"Gallstones","what":"Gallstones can cause strong upper-right or central abdominal pain, sometimes after food, with nausea.","causes":["Stones in the gallbladder or bile ducts"],"worry":"Persistent pain with fever, jaundice, or repeated vomiting needs urgent assessment.","doctor":"Seek medical review for recurrent or severe attacks."}),
    "ibs": topic(
        "🫄", "symptom", ["القولون العصبي", "قولون عصبي", "ibs", "irritable bowel"],
        src("NHS", "Irritable bowel syndrome", "https://www.nhs.uk/conditions/irritable-bowel-syndrome-ibs/"),
        {"title":"متلازمة القولون العصبي","what":"قد تسبب ألمًا أو تقلصات بالبطن مع انتفاخ وتغير في التبرز بين الإسهال والإمساك، وغالبًا تتغير الأعراض مع الوقت.","causes":["اضطراب وظيفة الأمعاء","محفزات غذائية أو توتر لدى بعض الأشخاص"],"worry":"نزيف بالبراز أو نقص وزن غير مقصود أو كتلة بالبطن يحتاج تقييمًا طبيًا.","doctor":"راجع الطبيب إذا استمرت الأعراض عدة أسابيع أو أثرت في حياتك."},
        {"title":"Irritable bowel syndrome (IBS)","what":"IBS can cause abdominal pain/cramps, bloating, and changes between diarrhea and constipation, with symptoms varying over time.","causes":["Altered bowel function","Food or stress triggers in some people"],"worry":"Blood in stool, unintentional weight loss, or an abdominal lump needs medical review.","doctor":"Seek medical review if symptoms persist for several weeks or affect daily life."}),
    "eczema": topic(
        "🧴", "symptom", ["اكزيما", "إكزيما", "جلد جاف يحك", "eczema", "atopic eczema"],
        src("NHS", "Atopic eczema", "https://www.nhs.uk/conditions/atopic-eczema/"),
        {"title":"الإكزيما التأتبية","what":"الإكزيما قد تسبب جفافًا وحكة واحمرارًا أو تشققًا بالجلد، وقد تتفاقم على فترات.","causes":["حاجز جلدي حساس","عوامل وراثية وبيئية","مهيجات أو محفزات مختلفة"],"worry":"ألم شديد أو إفرازات/قشور مع حرارة قد تشير لعدوى جلدية وتحتاج تقييمًا.","doctor":"راجع مختصًا إذا كانت الأعراض واسعة أو لا تتحسن أو تؤثر في النوم."},
        {"title":"Atopic eczema","what":"Eczema can cause dry, itchy, red, or cracked skin and may flare periodically.","causes":["Sensitive skin barrier","Genetic and environmental factors","Different irritants or triggers"],"worry":"Severe pain, discharge/crusting, or fever can suggest infection and needs assessment.","doctor":"Seek review if symptoms are widespread, do not improve, or disturb sleep."}),
    "gout": topic(
        "🦶", "symptom", ["نقرس", "الم اصبع القدم الكبير فجاة", "مفصل حار ومتورم", "gout"],
        src("NHS", "Gout", "https://www.nhs.uk/conditions/gout/"),
        {"title":"النقرس","what":"قد يسبب ألمًا شديدًا مفاجئًا مع احمرار وسخونة وتورم في مفصل، وغالبًا إصبع القدم الكبير.","causes":["ارتفاع حمض اليوريك وتكوّن البلورات بالمفصل"],"worry":"مفصل حار ومتورم مع حرارة عامة قد يشبه عدوى المفصل ويحتاج تقييمًا عاجلًا.","doctor":"راجع الطبيب إذا كانت أول نوبة أو لم تتحسن أو ترافق معها حرارة."},
        {"title":"Gout","what":"Gout can cause sudden severe pain with redness, warmth, and swelling in a joint, often the big toe.","causes":["Uric acid crystal deposition in a joint"],"worry":"A hot swollen joint with fever can resemble joint infection and needs urgent assessment.","doctor":"Seek medical review for a first attack, persistent symptoms, or fever."}),
    "migraine": topic(
        "🤕", "symptom", ["صداع نصفي", "الصداع النصفي", "شقيقة", "الشقيقة", "migraine", "صداع مع حساسية الضوء", "صداع مع غثيان"],
        src("WHO", "Headache disorders", "https://www.who.int/news-room/fact-sheets/detail/headache-disorders"),
        {"title":"الصداع النصفي","what":"قد يسبب صداعًا نابضًا متوسطًا أو شديدًا مع غثيان وحساسية للضوء أو الصوت، وقد يتكرر على شكل نوبات.","causes":["اضطراب عصبي متعدد العوامل","محفزات تختلف بين الأشخاص"],"worry":"صداع مفاجئ شديد جدًا أو مع ضعف جهة واحدة أو صعوبة كلام أو فقدان رؤية يحتاج طوارئ.","doctor":"راجع الطبيب إذا كان الصداع جديدًا أو متكررًا أو يتغير نمطه أو يعطل حياتك."},
        {"title":"Migraine","what":"Migraine can cause moderate-to-severe throbbing headache with nausea and sensitivity to light or sound, often in recurrent attacks.","causes":["A multifactorial neurological disorder","Triggers vary by person"],"worry":"A sudden extremely severe headache or headache with one-sided weakness, speech difficulty, or vision loss needs emergency care.","doctor":"Seek review for new, recurrent, changing, or disabling headaches."}),
    "vertigo": topic(
        "🌀", "symptom", ["دوار", "الغرفة تدور", "دوخه لما احرك راسي", "vertigo", "room spinning"],
        src("NHS", "Vertigo", "https://www.nhs.uk/conditions/vertigo/"),
        {"title":"الدوار","what":"الدوار هو إحساس بأنك أو المكان يدور، وقد يرتبط بمشكلات في الأذن الداخلية أو أسباب أخرى.","causes":["اضطرابات الأذن الداخلية","دوار وضعي","أسباب أخرى تحتاج سياقًا وتقييمًا"],"worry":"الدوار مع ضعف أو تنميل جهة واحدة أو صعوبة الكلام أو فقدان الرؤية يحتاج طوارئ.","doctor":"راجع مختصًا إذا كان الدوار جديدًا أو متكررًا أو مصحوبًا بفقدان سمع."},
        {"title":"Vertigo","what":"Vertigo is the sensation that you or your surroundings are spinning and can relate to inner-ear or other causes.","causes":["Inner-ear disorders","Positional vertigo","Other causes requiring context and assessment"],"worry":"Vertigo with one-sided weakness/numbness, speech difficulty, or vision loss needs emergency care.","doctor":"Seek review for new/recurrent vertigo or associated hearing loss."}),
    "shingles": topic(
        "🔥", "symptom", ["حزام ناري", "الحزام الناري", "طفح مؤلم جهة وحده", "shingles", "herpes zoster"],
        src("NHS", "Shingles", "https://www.nhs.uk/conditions/shingles/"),
        {"title":"الحزام الناري","what":"قد يبدأ بألم أو وخز ثم يظهر طفح وبثور على جهة واحدة من الجسم غالبًا.","causes":["إعادة تنشيط فيروس جدري الماء"],"worry":"طفح قرب العين أو تغير الرؤية أو ضعف المناعة يحتاج تقييمًا سريعًا.","doctor":"راجع مختصًا مبكرًا عند الاشتباه، خصوصًا إذا كان الطفح بالوجه أو قرب العين."},
        {"title":"Shingles","what":"Shingles may begin with pain or tingling followed by a blistering rash, usually on one side of the body.","causes":["Reactivation of the chickenpox virus"],"worry":"Rash near the eye, vision change, or immunocompromise needs prompt assessment.","doctor":"Seek early medical review, especially for facial or eye-area rash."}),
    "hemorrhoids": topic(
        "🩸", "symptom", ["بواسير", "دم احمر بعد التبرز", "الم حول فتحة الشرج", "piles", "hemorrhoids", "haemorrhoids"],
        src("NHS", "Piles (haemorrhoids)", "https://www.nhs.uk/conditions/piles-haemorrhoids/"),
        {"title":"البواسير","what":"قد تسبب البواسير نزفًا أحمر فاتحًا بعد التبرز مع حكة أو ألم أو كتلة حول فتحة الشرج.","causes":["ضغط على أوعية الشرج","الإمساك والحزق","الحمل وعوامل أخرى"],"worry":"نزيف غزير أو براز أسود أو دوخة/إغماء يحتاج تقييمًا عاجلًا.","doctor":"راجع الطبيب إذا استمر النزيف أو تكرر أو لم تكن متأكدًا من مصدره."},
        {"title":"Piles (haemorrhoids)","what":"Haemorrhoids can cause bright-red bleeding after bowel movements with itching, pain, or a lump around the anus.","causes":["Pressure on rectal veins","Constipation and straining","Pregnancy and other factors"],"worry":"Heavy bleeding, black stool, dizziness, or fainting needs urgent assessment.","doctor":"Seek medical review if bleeding persists, recurs, or the source is uncertain."}),
    "sleep_apnea": topic(
        "😴", "symptom", ["انقطاع التنفس اثناء النوم", "انقطاع النفس بالنوم", "شخير قوي مع توقف نفس", "sleep apnea", "sleep apnoea"],
        src("NHS", "Sleep apnoea", "https://www.nhs.uk/conditions/sleep-apnoea/"),
        {"title":"انقطاع النفس أثناء النوم","what":"قد يظهر كشخير مرتفع مع توقف وعودة التنفس أثناء النوم ونعاس أو تعب بالنهار.","causes":["انسداد متكرر لمجرى التنفس أثناء النوم في النوع الشائع"],"worry":"اختناق شديد أو صعوبة تنفس حادة وأنت مستيقظ تحتاج تقييمًا عاجلًا.","doctor":"اطلب تقييمًا إذا لاحظ شخص توقف تنفسك أثناء النوم أو كان النعاس النهاري شديدًا."},
        {"title":"Sleep apnoea","what":"Sleep apnoea may appear as loud snoring with breathing pauses and daytime sleepiness or fatigue.","causes":["Repeated upper-airway obstruction during sleep in the common obstructive type"],"worry":"Severe choking or acute breathing difficulty while awake needs urgent assessment.","doctor":"Seek evaluation if someone notices breathing pauses during sleep or daytime sleepiness is marked."}),
    "restless_legs": topic(
        "🦵", "symptom", ["تململ الساقين", "رجولي لازم احركها بالليل", "انزعاج الساقين وقت النوم", "restless legs", "restless legs syndrome"],
        src("NHS", "Restless legs syndrome", "https://www.nhs.uk/conditions/restless-legs-syndrome/"),
        {"title":"متلازمة تململ الساقين","what":"تسبب رغبة قوية في تحريك الساقين مع إحساس مزعج يزداد غالبًا أثناء الراحة أو في الليل.","causes":["قد تكون بلا سبب واضح","قد ترتبط بنقص الحديد أو حالات أخرى لدى بعض الأشخاص"],"worry":"تورم ساق واحدة مع ألم أو ضيق نفس لا يشبه تململ الساقين ويحتاج تقييمًا عاجلًا.","doctor":"راجع الطبيب إذا كانت الأعراض تعطل النوم أو تتكرر كثيرًا."},
        {"title":"Restless legs syndrome","what":"Restless legs syndrome causes a strong urge to move the legs with unpleasant sensations, often worse at rest or at night.","causes":["Sometimes no clear cause","Can be associated with iron deficiency or other conditions"],"worry":"One-sided leg swelling with pain or shortness of breath is not typical restless legs and needs urgent assessment.","doctor":"Seek review if symptoms frequently disrupt sleep."}),
}
