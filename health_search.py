# health_search.py — SymptoSense Smart Health Search & "Explain Simply" glossary.
# Educational health content only. Never presents results as a diagnosis.

import re

# ---------------------------------------------------------------------------
# Search knowledge base
# category: symptom | test | term | medication
# ---------------------------------------------------------------------------
SEARCH_KB = {
    "dizziness": {
        "emoji": "🤕", "category": "symptom",
        "aliases": ["دوخة", "دوخه", "الدوخة", "دوار", "الدوار", "دوخة الراس", "دوخه الراس",
                    "الدنيا تلف", "الدنيا تدور", "الدنيا طايرة", "راسي يلف", "راسي يطيش",
                    "dizziness", "dizzy", "vertigo", "lightheaded", "feeling lightheaded",
                    "world is spinning", "room spinning", "head spins"],
        "causes_label": {"ar": "💡 الأسباب الشائعة", "en": "💡 Common causes"},
        "ar": {
            "title": "الدوخة",
            "what": "الدوخة هي إحساس بعدم الثبات أو أن كل شيء حولك يتحرك أو يدور، أو الشعور بخفة الرأس وعدم الاتزان. حالة شائعة جداً وقد تكون خفيفة وتزول وحدها، لكن يجب الانتباه عندما تتكرر أو تصبح شديدة.",
            "causes": ["الجفاف وعدم شرب كمية كافية من الماء", "قلة النوم أو الإرهاق",
                       "انخفاض مستوى السكر في الدم", "بعض الأدوية",
                       "مشاكل التوازن أو الأذن الداخلية", "الوقوف المفاجئ (هبوط الضغط الانتصابي)",
                       "فقر الدم", "القلق أو التوتر"],
            "worry": "اطلب رعاية طبية عاجلة فوراً إذا ظهرت الدوخة بشكل مفاجئ وشديد، أو كانت مصحوبة بألم في الصدر، أو ضيق في التنفس، أو صداع شديد، أو صعوبة في الكلام، أو ضعف أو تنميل في جانب واحد من الجسم، أو تشوش، أو فقدان الوعي.",
            "doctor": "راجع الطبيب إذا استمرت الدوخة أكثر من يومين، أو تكررت بشكل متكرر، أو صاحبتها أعراض مثل ألم الأذن أو ضعف السمع، أو القيء المتكرر، أو إذا كنت تتناول أدوية جديدة قد تكون السبب.",
        },
        "en": {
            "title": "Dizziness",
            "what": "Dizziness is a feeling of unsteadiness, lightheadedness, or that the world is spinning. It is very common and often mild, but it deserves attention when it is severe, frequent, or persistent.",
            "causes": ["Dehydration or not drinking enough water", "Lack of sleep or exhaustion",
                       "Low blood sugar", "Certain medications",
                       "Inner ear or balance problems", "Sudden standing (postural low blood pressure)",
                       "Anemia", "Anxiety or stress"],
            "worry": "Seek urgent care if dizziness is sudden and severe, or comes with chest pain, shortness of breath, severe headache, trouble speaking, weakness or numbness on one side of the body, confusion, or fainting.",
            "doctor": "See a doctor if dizziness lasts more than a couple of days, keeps coming back, or is accompanied by ear pain, hearing loss, repeated vomiting, or if you started a new medication that might be the cause.",
        },
    },
    "fever": {
        "emoji": "🤒", "category": "symptom",
        "aliases": ["حمى", "الحمى", "حرارة", "سخونة", "سخونه", "fever", "high temperature", "temp", "hot"],
        "causes_label": {"ar": "💡 الأسباب الشائعة", "en": "💡 Common causes"},
        "ar": {
            "title": "الحمى",
            "what": "الحمى هي ارتفاع درجة حرارة الجسم عن المعدل الطبيعي (عادة أكثر من 37.5°م)، وعادة ما تكون استجابة الجسم الطبيعية لمقاومة العدوى مثل الفيروسات أو البكتيريا.",
            "causes": ["عدوى فيروسية مثل نزلات البرد والإنفلونزا", "عدوى بكتيرية مثل التهاب الحلق أو الأذن",
                       "التهابات الجهاز التنفسي أو البولي", "التسنين عند الأطفال",
                       "الضربات الحرارية في الطقس الحار", "بعض اللقاحات أو الأدوية"],
            "worry": "الحمى المرتفعة جداً (أكثر من 40°م) أو المصحوبة بتصلب الرقبة، أو صداع شديد، أو طفح جلدي، أو صعوبة التنفس، أو تشنجات، أو فقدان الوعي، أو عدم التحسن — تستدعي طلب رعاية طبية عاجلة، خصوصاً عند الرضع والأطفال.",
            "doctor": "راجع الطبيب إذا استمرت الحمى أكثر من 3 أيام، أو تخطت 39°م لدى البالغين، أو كانت عند رضيع أقل من 3 أشهر، أو صاحبتها أعراض أخرى مثل الألم الشديد أو القيء المستمر أو الجفاف.",
        },
        "en": {
            "title": "Fever",
            "what": "A fever is a body temperature above the normal range (usually above 37.5°C). It is the body's natural response to fighting infections such as viruses or bacteria.",
            "causes": ["Viral infections like colds and flu", "Bacterial infections such as strep throat or ear infections",
                       "Respiratory or urinary infections", "Teething in babies",
                       "Heat exposure in hot weather", "Some vaccines or medications"],
            "worry": "Very high fever (above 40°C), or fever with a stiff neck, severe headache, rash, trouble breathing, seizures, fainting, or no improvement — requires urgent care, especially in babies and children.",
            "doctor": "See a doctor if fever lasts more than 3 days, exceeds 39°C in adults, occurs in an infant under 3 months, or is accompanied by severe pain, persistent vomiting, or dehydration.",
        },
    },
    "eye_redness": {
        "emoji": "👁️", "category": "symptom",
        "aliases": ["احمرار العين", "احمرار العيون", "احمرار عين", "عيون حمراء", "عين محمره", "red eye",
                    "red eyes", "eye redness", "bloodshot eyes", "pink eye"],
        "causes_label": {"ar": "💡 الأسباب الشائعة", "en": "💡 Common causes"},
        "ar": {
            "title": "احمرار العين",
            "what": "احمرار العين هو تمدد الأوعية الدموية في الجزء الأبيض من العين فيبدو سطحها محمراً. غالباً ما يكون بسيطاً ومؤقتاً، لكنه قد يشير أحياناً إلى التهاب أو مشكلة تحتاج تقييماً.",
            "causes": ["التهاب الملتحمة (الفيروسي أو البكتيري أو التحسسي)", "إرهاق العين وقلة النوم",
                       "جفاف العين", "الحساسية والغبار", "دخول جسم غريب في العين",
                       "ارتداء العدسات اللاصقة لفترات طويلة"],
            "worry": "راجع الطوارئ فوراً إذا صاحب الاحمرار ألم شديد في العين، أو فقدان مفاجئ للرؤية، أو حساسية شديدة للضوء، أو رؤية هالات، أو قيء مع صداع (قد يشير لضغط العين المرتفع)، أو إصابة مباشرة بالعين.",
            "doctor": "راجع الطبيب إذا استمر الاحمرار أكثر من يومين، أو زاد سوءاً، أو صاحبه إفرازات كثيفة أو قشور على الرموش، أو تشوش الرؤية، أو حكة شديدة متكررة.",
        },
        "en": {
            "title": "Eye redness",
            "what": "Eye redness happens when the small blood vessels on the white part of the eye widen, making the surface look red. It is often mild and temporary, but it can sometimes signal inflammation or a problem that needs evaluation.",
            "causes": ["Conjunctivitis (viral, bacterial, or allergic)", "Eye strain or lack of sleep",
                       "Dry eyes", "Allergies and dust", "A foreign object in the eye",
                       "Wearing contact lenses too long"],
            "worry": "Get urgent care if redness is accompanied by severe eye pain, sudden vision loss, extreme light sensitivity, halos around lights, vomiting with headache (possible high eye pressure), or a direct injury to the eye.",
            "doctor": "See a doctor if redness lasts more than two days, worsens, or comes with heavy discharge, crusts on the lashes, blurry vision, or frequent severe itching.",
        },
    },
    "headache": {
        "emoji": "🤕", "category": "symptom",
        "aliases": ["صداع", "الصداع", "راسي يوجع", "راسي يعور", "صداع الراس", "headache", "head ache",
                    "my head hurts", "head pain", "migraine"],
        "causes_label": {"ar": "💡 الأسباب الشائعة", "en": "💡 Common causes"},
        "ar": {
            "title": "الصداع",
            "what": "الصداع هو ألم في الرأس أو منطقة الوجه، وهو من أكثر الشكاوى الصحية شيوعاً. معظم الصداع يكون بسيطاً ويستجيب للراحة والمسكنات، لكن بعض الأنواع تستدعي الانتباه.",
            "causes": ["التوتر والإجهاد", "قلة النوم أو الإرهاق", "الجفاف",
                       "الصداع النصفي (الشقيقة)", "إجهاد العين", "نزلات البرد والجيوب الأنفية",
                       "تناول الكافيين بكثرة أو الانقطاع عنه"],
            "worry": "اطلب رعاية عاجلة إذا جاء الصداع فجأة وبشدة غير معتادة («أسوأ صداع في حياتك»)، أو صاحبه صداع مع تشوش ذهني، أو تصلب رقبة مع حمى، أو ضعف أو تنميل في جانب، أو صعوبة كلام، أو بعد إصابة في الرأس.",
            "doctor": "راجع الطبيب إذا تكرر الصداع كثيراً، أو استمر أكثر من عدة أيام دون تحسن، أو ازداد مع الحركة، أو منعك من النوم، أو رافقك دواء مسكن بشكل يومي.",
        },
        "en": {
            "title": "Headache",
            "what": "A headache is pain in the head or face, one of the most common health complaints. Most headaches are mild and respond to rest and pain relievers, but some types need attention.",
            "causes": ["Stress and tension", "Lack of sleep or fatigue", "Dehydration",
                       "Migraine", "Eye strain", "Colds and sinus problems",
                       "Too much caffeine or suddenly stopping it"],
            "worry": "Seek urgent care if the headache starts suddenly and is unusually severe (a \"worst-ever\" headache), or comes with confusion, a stiff neck and fever, weakness or numbness on one side, trouble speaking, or after a head injury.",
            "doctor": "See a doctor if headaches are frequent, last for several days without improving, get worse with movement, keep you from sleeping, or if you rely on painkillers almost every day.",
        },
    },
    "chest_pain": {
        "emoji": "🫀", "category": "symptom",
        "aliases": ["الم الصدر", "الم في الصدر", "ألم في الصدر", "ألم الصدر", "صدر", "وجع الصدر",
                    "chest pain", "chest tightness", "pain in chest", "heart pain"],
        "causes_label": {"ar": "💡 الأسباب الشائعة", "en": "💡 Common causes"},
        "ar": {
            "title": "ألم الصدر",
            "what": "ألم الصدر هو شعور بألم أو ضغط أو ضيق في منطقة الصدر. لا يجب الاستخفاف بأي ألم صدر، خاصةً إذا كان جديداً أو شديداً، لأن بعض أسبابه طارئة وخطيرة.",
            "causes": ["مشاكل عضلية في جدار الصدر", "حرقة المعدة أو ارتجاع المريء",
                       "القلق والتوتر", "التهابات الجهاز التنفسي",
                       "أسباب قلبية (ذبحة أو نوبة قلبية)", "التهاب الغشاء حول الرئة"],
            "worry": "اطلب الإسعاف فوراً إذا كان ألم الصدر مفاجئاً أو شديداً، أو امتد إلى الذراع أو الفك أو الظهر، أو صاحبه ضيق تنفس أو عرق غزير أو غثيان أو دوخة، أو استمر أكثر من دقائق وتكرر مع المجهود.",
            "doctor": "إذا لم تكن هناك علامات طارئة، راجع الطبيب لتقييم ألم الصدر خصوصاً مع عوامل خطر مثل التدخين أو الضغط أو السكري أو السمنة أو تاريخ عائلي قلبي.",
        },
        "en": {
            "title": "Chest pain",
            "what": "Chest pain is discomfort, pressure, or tightness in the chest area. No chest pain should be taken lightly, especially if it is new or severe, because some causes are emergencies.",
            "causes": ["Muscle strain in the chest wall", "Heartburn or acid reflux",
                       "Anxiety and stress", "Respiratory infections",
                       "Cardiac causes (angina or heart attack)", "Inflammation of the lining around the lungs"],
            "worry": "Call emergency services immediately if chest pain is sudden or severe, spreads to the arm, jaw, or back, or comes with shortness of breath, heavy sweating, nausea, or dizziness, or lasts more than a few minutes and recurs with effort.",
            "doctor": "If there are no emergency signs, see a doctor for evaluation, especially with risk factors such as smoking, high blood pressure, diabetes, obesity, or a family history of heart disease.",
        },
    },
    "shortness_of_breath": {
        "emoji": "🫁", "category": "symptom",
        "aliases": ["ضيق التنفس", "ضيق نفس", "صعوبة التنفس", "صعوبه التنفس", "لا استطيع التنفس",
                    "ما اقدر اتنفس", "نهجه", "shortness of breath", "difficulty breathing", "trouble breathing",
                    "can't breathe", "breathlessness", "short of breath", "breathing problem"],
        "causes_label": {"ar": "💡 الأسباب الشائعة", "en": "💡 Common causes"},
        "ar": {
            "title": "ضيق التنفس",
            "what": "ضيق التنفس هو الإحساس بعدم القدرة على أخذ نفس كافٍ أو أن التنفس صعب. قد يحدث فجأة أو تدريجياً، ويتراوح بين مجهود عادي وحالة طارئة.",
            "causes": ["الجهد البدني الشديد", "الربو أو الحساسية الصدرية", "التهابات الجهاز التنفسي",
                       "القلق ونوبات الهلع", "فقر الدم", "مشاكل القلب أو الرئة",
                       "السمنة أو قلة اللياقة"],
            "worry": "اطلب الإسعاف فوراً إذا كان ضيق التنفس مفاجئاً وشديداً، أو صاحبه ألم في الصدر، أو زرقة الشفاه أو الأظافر، أو تشوش، أو صافرة تنفس شديدة، أو لم يتحسن بعد دقائق من الراحة.",
            "doctor": "راجع الطبيب إذا استمر ضيق التنفس أو ازداد تدريجياً، أو حدث مع مجهود بسيط كان يتحمله سابقاً، أو صاحبه سعال مزمن أو تورم في القدمين.",
        },
        "en": {
            "title": "Shortness of breath",
            "what": "Shortness of breath is the feeling that you cannot get enough air or that breathing is hard. It can come on suddenly or gradually and can range from a normal response to exercise to a medical emergency.",
            "causes": ["Heavy physical exertion", "Asthma or chest allergies", "Respiratory infections",
                       "Anxiety and panic attacks", "Anemia", "Heart or lung conditions",
                       "Obesity or poor fitness"],
            "worry": "Call emergency services immediately if shortness of breath is sudden and severe, or comes with chest pain, bluish lips or nails, confusion, severe wheezing, or does not improve after a few minutes of rest.",
            "doctor": "See a doctor if it persists or gradually worsens, happens with effort you used to tolerate easily, or is accompanied by a chronic cough or swelling in the feet.",
        },
    },
    "fatigue": {
        "emoji": "😴", "category": "symptom",
        "aliases": ["تعب", "ارهاق", "إرهاق", "خمول", "كسل", "لا طاقه", "fatigue", "tired", "exhaustion",
                    "no energy", "weakness", "low energy"],
        "causes_label": {"ar": "💡 الأسباب الشائعة", "en": "💡 Common causes"},
        "ar": {
            "title": "التعب والإرهاق",
            "what": "التعب أو الإرهاق هو شعور بفقدان الطاقة والطاقة الذهنية والجسدية. يختلف عن النعاس، ويحدث لأسباب يومية كثيرة وقد يكون أحياناً مؤشراً على حالة صحية.",
            "causes": ["قلة النوم أو سوء جودته", "الجفاف", "فقر الدم (نقص الحديد)",
                       "نقص الفيتامينات مثل فيتامين د أو ب12", "الضغط النفسي والقلق",
                       "قلة النشاط البدني", "مشاكل الغدة الدرقية أو السكري"],
            "worry": "راجع الطبيب سريعاً إذا كان الإرهاق شديداً وظهر فجأة، أو صاحبه خفقان وألم صدر، أو فقدان وزن غير مبرر، أو شحوب شديد، أو نزيف غير طبيعي، أو حمى مستمرة.",
            "doctor": "راجع الطبيب إذا استمر التعب أكثر من أسبوعين دون سبب واضح، أو تأثرت به حياتك اليومية، أو رافقك أعراض مثل صعوبة النوم أو تغير الوزن أو تساقط الشعر.",
        },
        "en": {
            "title": "Fatigue",
            "what": "Fatigue is a feeling of low physical and mental energy. It is different from sleepiness and can be caused by everyday factors or, sometimes, an underlying health condition.",
            "causes": ["Poor or insufficient sleep", "Dehydration", "Anemia (iron deficiency)",
                       "Vitamin deficiencies such as vitamin D or B12", "Stress and anxiety",
                       "Lack of physical activity", "Thyroid problems or diabetes"],
            "worry": "See a doctor promptly if fatigue is severe and sudden, or comes with palpitations and chest pain, unexplained weight loss, marked paleness, unusual bleeding, or a persistent fever.",
            "doctor": "See a doctor if tiredness lasts more than two weeks without a clear reason, affects your daily life, or is accompanied by sleep problems, weight changes, or hair loss.",
        },
    },
    "nausea": {
        "emoji": "🤢", "category": "symptom",
        "aliases": ["غثيان", "الغثيان", "ميلي", "قرفه", "nausea", "sick to stomach", "feel like vomiting", "queasy"],
        "causes_label": {"ar": "💡 الأسباب الشائعة", "en": "💡 Common causes"},
        "ar": {
            "title": "الغثيان",
            "what": "الغثيان هو الإحساس بعدم الراحة في المعدة مع رغبة في التقيؤ، وقد يحدث قبل القيء أو بدونه. عادةً ما يكون مؤقتاً ويحل من تلقاء نفسه.",
            "causes": ["اضطراب المعدة بعد الأكل أو الأطعمة الفاسدة", "التهاب المعدة أو ارتجاع المريء",
                       "العدوى الفيروسية", "الحمل", "القلق والتوتر",
                       "بعض الأدوية", "دوخة الحركة (في السيارة أو البحر)"],
            "worry": "اطلب رعاية عاجلة إذا صاحب الغثيان قيء دم أو قهوة، أو ألم بطن شديد، أو دم في البراز، أو صداع شديد مع تصلب رقبة، أو تشوش، أو علامات جفاف شديد مثل قلة البول.",
            "doctor": "راجع الطبيب إذا استمر الغثيان أكثر من 48 ساعة، أو منعك من شرب السوائل، أو صاحبه فقدان وزن أو ألم مستمر في البطن.",
        },
        "en": {
            "title": "Nausea",
            "what": "Nausea is an uneasy feeling in the stomach with the urge to vomit, which may or may not happen. It is usually temporary and resolves on its own.",
            "causes": ["Stomach upset after eating or spoiled food", "Gastritis or acid reflux",
                       "Viral infection", "Pregnancy", "Anxiety and stress",
                       "Certain medications", "Motion sickness"],
            "worry": "Get urgent care if nausea comes with vomiting blood or material like coffee grounds, severe abdominal pain, blood in stool, severe headache with a stiff neck, confusion, or signs of severe dehydration such as little urine.",
            "doctor": "See a doctor if nausea lasts more than 48 hours, stops you from keeping fluids down, or is accompanied by weight loss or persistent abdominal pain.",
        },
    },
    "sore_throat": {
        "emoji": "😣", "category": "symptom",
        "aliases": ["الم الحلق", "الم في الحلق", "ألم الحلق", "زور", "التهاب الحلق", "التهاب اللوز",
                    "sore throat", "throat pain", "scratchy throat", "tonsillitis", "swollen throat"],
        "causes_label": {"ar": "💡 الأسباب الشائعة", "en": "💡 Common causes"},
        "ar": {
            "title": "ألم الحلق",
            "what": "ألم الحلق هو إحساس بالتهيج أو الخشونة أو الألم عند البلع. غالباً ما ينتج عن عدوى فيروسية بسيطة، لكن العدوى البكتيرية تحتاج مضاداً حيوياً موصوفاً من الطبيب.",
            "causes": ["عدوى فيروسية مثل نزلات البرد", "التهاب الحلق البكتيري (بكتيريا العقديات)",
                       "الحساسية والغبار", "جفاف الهواء أو التنفس من الفم", "التدخين",
                       "ارتداد حمض المعدة"],
            "worry": "اطلب رعاية عاجلة إذا كان ألم الحلق شديداً مع صعوبة في التنفس أو البلع أو فتح الفم، أو سيلان لعاب، أو تورم واضح في الرقبة، أو صوت مكتوم فجأة.",
            "doctor": "راجع الطبيب إذا استمر الألم أكثر من أسبوع، أو صاحبه حمى مرتفعة بدون أعراض برد، أو بقع بيضاء على اللوزتين، أو انتفاخ الغدد، أو تكرر التهاب الحلق كثيراً.",
        },
        "en": {
            "title": "Sore throat",
            "what": "A sore throat is a feeling of irritation, scratchiness, or pain when swallowing. It is often caused by a simple viral infection, but a bacterial infection needs a doctor-prescribed antibiotic.",
            "causes": ["Viral infections such as colds", "Strep throat (bacterial)",
                       "Allergies and dust", "Dry air or mouth breathing", "Smoking",
                       "Acid reflux"],
            "worry": "Get urgent care if the sore throat is severe with trouble breathing, swallowing, or opening the mouth, drooling, noticeable neck swelling, or a suddenly muffled voice.",
            "doctor": "See a doctor if the pain lasts more than a week, or comes with a high fever without cold symptoms, white patches on the tonsils, swollen glands, or if you get sore throats very often.",
        },
    },
    "cough": {
        "emoji": "😷", "category": "symptom",
        "aliases": ["سعال", "كحه", "كحة", "الكحة", "cough", "coughing", "hacking", "chesty cough"],
        "causes_label": {"ar": "💡 الأسباب الشائعة", "en": "💡 Common causes"},
        "ar": {
            "title": "السعال",
            "what": "السعال هو رد فعل طبيعي من الجسم لطرد المهيجات أو المخاط من المجاري التنفسية. معظم حالات السعال بسيطة وتزول خلال أيام أو أسابيع.",
            "causes": ["نزلات البرد والتهابات الجهاز التنفسي", "الحساسية والغبار",
                       "التدخين", "التهاب الجيوب وتنقيط الأنف الخلفي", "الربو",
                       "ارتجاع المريء", "الجو البارد أو الجاف"],
            "worry": "اطلب رعاية عاجلة إذا صاحب السعال ألم في الصدر، أو ضيق تنفس، أو سعال دم، أو زرقة الشفاه، أو أزيز تنفس شديد، أو فقدان مفاجئ للوعي أثناء السعال.",
            "doctor": "راجع الطبيب إذا استمر السعال أكثر من 3 أسابيع، أو صاحبه حمى مستمرة، أو مخاط ملون أو دموي، أو فقدان وزن غير مبرر، أو سعال ليلي يمنع النوم.",
        },
        "en": {
            "title": "Cough",
            "what": "A cough is the body's natural way to clear irritants or mucus from the airways. Most coughs are mild and resolve within days or a few weeks.",
            "causes": ["Colds and respiratory infections", "Allergies and dust",
                       "Smoking", "Sinusitis and post-nasal drip", "Asthma",
                       "Acid reflux", "Cold or dry air"],
            "worry": "Get urgent care if the cough comes with chest pain, shortness of breath, coughing blood, bluish lips, severe wheezing, or passing out while coughing.",
            "doctor": "See a doctor if the cough lasts more than three weeks, or comes with a persistent fever, colored or bloody mucus, unexplained weight loss, or a nighttime cough that prevents sleep.",
        },
    },
    "stomach_ache": {
        "emoji": "😖", "category": "symptom",
        "aliases": ["الم البطن", "الم في البطن", "ألم في البطن", "وجع بطن", "مغص", "المعده", "ألم المعدة",
                    "stomach pain", "abdominal pain", "stomach ache", "belly ache", "cramps"],
        "causes_label": {"ar": "💡 الأسباب الشائعة", "en": "💡 Common causes"},
        "ar": {
            "title": "ألم البطن",
            "what": "ألم البطن هو ألم أو تشنج في منطقة البطن، ويختلف حسب موقعه وشدته ومدته. معظم الألم البطني خفيف ومؤقت، لكن بعض الحالات تحتاج تقييماً عاجلاً.",
            "causes": ["عسر الهضم أو الأكل الدسم", "الغازات والانتفاخ", "الإمساك أو الإسهال",
                       "التهاب المعدة", "الالتهابات الفيروسية", "عسر الطمث عند النساء",
                       "حساسية أو عدم تحمل بعض الأطعمة"],
            "worry": "اطلب رعاية عاجلة إذا كان الألم شديداً ومفاجئاً، أو في الجزء السفلي الأيمن مع حمى (قد يشير لالتهاب الزائدة)، أو صاحبه قيء دم أو براز دموي، أو انتفاخ شديد وتصلب في البطن، أو بعد إصابة.",
            "doctor": "راجع الطبيب إذا استمر الألم أكثر من عدة أيام، أو تكرر بشكل متزايد، أو صاحبه فقدان وزن، أو حمى مستمرة، أو تغير في عادات الأمعاء.",
        },
        "en": {
            "title": "Stomach pain",
            "what": "Abdominal pain is discomfort or cramping in the belly area, which varies by location, severity, and duration. Most abdominal pain is mild and temporary, but some cases need urgent evaluation.",
            "causes": ["Indigestion or fatty meals", "Gas and bloating", "Constipation or diarrhea",
                       "Gastritis", "Viral infections", "Menstrual cramps in women",
                       "Food sensitivities or intolerances"],
            "worry": "Get urgent care if the pain is sudden and severe, in the lower right side with fever (possible appendicitis), or comes with vomiting blood, bloody stool, severe bloating, a rigid abdomen, or after an injury.",
            "doctor": "See a doctor if the pain lasts more than a few days, keeps getting worse, or comes with weight loss, persistent fever, or a change in bowel habits.",
        },
    },
    "dehydration": {
        "emoji": "💧", "category": "symptom",
        "aliases": ["جفاف", "الجفاف", "عطشان", "dehydration", "dehydrated", "thirst", "dry mouth"],
        "causes_label": {"ar": "💡 الأسباب الشائعة", "en": "💡 Common causes"},
        "ar": {
            "title": "الجفاف",
            "what": "الجفاف هو فقدان الجسم للماء والأملاح أكثر مما يدخل إليه. قد يحدث مع الطقس الحار أو المجهود أو الإسهال والقيء، ويؤثر على وظائف الجسم الأساسية.",
            "causes": ["عدم شرب كمية كافية من الماء", "الإسهال والقيء", "الحمى",
                       "التعرق الشديد في الحر أو الرياضة", "بعض الأدوية المدرة للبول",
                       "مرض السكري غير المنضبط"],
            "worry": "اطلب رعاية عاجلة إذا ظهرت علامات الجفاف الشديد: قلة البول أو غيابه، جفاف شديد في الفم، دوخة وعدم توازن، تشوش أو نعاس، عيون غائرة، أو جلد لا يعود لمكانه عند القرص.",
            "doctor": "راجع الطبيب إذا لم تتحسن الأعراض بعد تعويض السوائل، أو إذا كان الجفاف لدى رضيع أو مسن، أو كان مصحوباً بقيء يمنع شرب السوائل.",
        },
        "en": {
            "title": "Dehydration",
            "what": "Dehydration happens when the body loses more water and salts than it takes in. It can occur in hot weather, with exertion, or with diarrhea and vomiting, and it affects basic body functions.",
            "causes": ["Not drinking enough water", "Diarrhea and vomiting", "Fever",
                       "Heavy sweating in heat or sport", "Some diuretic medications",
                       "Uncontrolled diabetes"],
            "worry": "Get urgent care if you notice signs of severe dehydration: little or no urine, very dry mouth, dizziness and unsteadiness, confusion or drowsiness, sunken eyes, or skin that stays pinched instead of bouncing back.",
            "doctor": "See a doctor if symptoms do not improve after replacing fluids, if the affected person is a baby or elderly, or if vomiting prevents drinking fluids.",
        },
    },
    "conjunctivitis": {
        "emoji": "👁️", "category": "term",
        "aliases": ["التهاب الملتحمة", "رمد", "عين ورديه", "pink eye", "conjunctivitis", "red eye infection"],
        "causes_label": {"ar": "💡 الأسباب الشائعة", "en": "💡 Common causes"},
        "ar": {
            "title": "التهاب الملتحمة",
            "what": "التهاب الملتحمة هو التهاب أو تهيج في الغشاء الرقيق الذي يغطي الجزء الأبيض من العين والسطح الداخلي للجفن، ويسبب احمرار العين وتهيجها.",
            "causes": ["عدوى فيروسية (الأكثر شيوعاً)", "عدوى بكتيرية (إفرازات صفراء/خضراء)",
                       "حساسية من الغبار أو حبوب اللقاح", "مهيجات مثل الدخان أو الكلور",
                       "ملامسة العين بأيدٍ ملوثة"],
            "worry": "اطلب رعاية عاجلة إذا صاحب الالتهاب ألم شديد في العين، أو ضبابية مفاجئة في الرؤية، أو حساسية شديدة للضوء، أو ألم مع حركة العين.",
            "doctor": "راجع الطبيب إذا لم يتحسن الالتهاب خلال بضعة أيام، أو كانت إفرازات العين كثيفة، أو تكرر الالتهاب كثيراً، أو أصيب طفل عمره أقل من سنة.",
        },
        "en": {
            "title": "Conjunctivitis",
            "what": "Conjunctivitis is inflammation or irritation of the thin membrane covering the white part of the eye and the inside of the eyelid, causing redness and discomfort.",
            "causes": ["Viral infection (most common)", "Bacterial infection (yellow/green discharge)",
                       "Allergies to dust or pollen", "Irritants like smoke or chlorine",
                       "Touching the eye with dirty hands"],
            "worry": "Get urgent care if the inflammation is accompanied by severe eye pain, sudden blurry vision, extreme light sensitivity, or pain with eye movement.",
            "doctor": "See a doctor if it does not improve within a few days, discharge becomes thick, it keeps coming back, or if a child under one year is affected.",
        },
    },
    "anemia": {
        "emoji": "🩸", "category": "term",
        "aliases": ["فقر الدم", "انيميا", "الانيميا", "anemia", "anaemia", "low hemoglobin"],
        "causes_label": {"ar": "💡 الأسباب الشائعة", "en": "💡 Common causes"},
        "ar": {
            "title": "فقر الدم",
            "what": "فقر الدم هو حالة ينخفض فيها مستوى الهيموجلوبين أو كريات الدم الحمراء في الدم، فتصبح قدرة الدم على حمل الأكسجين أقل. من أكثر أنواعه شيوعاً فقر الدم بسبب نقص الحديد.",
            "causes": ["نقص الحديد في الغذاء أو امتصاصه", "نقص فيتامين ب12 أو حمض الفوليك",
                       "فقدان الدم المزمن (مثل الدورة الشهرية الغزيرة)", "الأمراض المزمنة",
                       "أمراض تكسر الدم الوراثية مثل الثلاسيميا أو المنجلية"],
            "worry": "اطلب رعاية عاجلة إذا صاحب فقر الدم ألم صدر، أو ضيق تنفس شديد، أو تسارع خفقان القلب، أو دوخة وإغماء، أو نزيف مفاجئ.",
            "doctor": "راجع الطبيب لإجراء فحص الدم إذا شعرت بتعب مستمر، أو شحوب، أو خفقان، أو تساقط شعر، أو برودة الأطراف — خاصةً مع دورة شهرية غزيرة أو نظام غذائي ناقص الحديد.",
        },
        "en": {
            "title": "Anemia",
            "what": "Anemia is a condition in which hemoglobin or red blood cells are below normal, so the blood carries less oxygen. Iron-deficiency anemia is the most common type.",
            "causes": ["Low iron in the diet or poor absorption", "Vitamin B12 or folate deficiency",
                       "Chronic blood loss (e.g. heavy periods)", "Chronic diseases",
                       "Inherited red blood cell disorders such as thalassemia or sickle cell disease"],
            "worry": "Get urgent care if anemia is accompanied by chest pain, severe shortness of breath, rapid palpitations, dizziness and fainting, or sudden bleeding.",
            "doctor": "See a doctor for a blood test if you feel persistent tiredness, paleness, palpitations, hair loss, or cold hands and feet — especially with heavy periods or a low-iron diet.",
        },
    },
    "diabetes": {
        "emoji": "🩸", "category": "term",
        "aliases": ["سكري", "السكر", "السكري", "مرض السكر", "diabetes", "diabetic", "high blood sugar", "blood glucose"],
        "causes_label": {"ar": "💡 الأسباب الشائعة", "en": "💡 Common causes"},
        "ar": {
            "title": "مرض السكري",
            "what": "السكري هو حالة ترتفع فيها نسبة السكر في الدم لأن الجسم لا ينتج كمية كافية من الأنسولين أو لا يستخدمه بشكل فعال، ما يؤثر على تحويل الغذاء إلى طاقة.",
            "causes": ["مقاومة الأنسولين (النوع الثاني — الأكثر شيوعاً)", "عدم إنتاج الأنسولين (النوع الأول)",
                       "العامل الوراثي والعائلي", "السمنة وقلة النشاط", "التغذية غير المتوازنة",
                       "سكري الحمل"],
            "worry": "اطلب رعاية عاجلة إذا ظهرت علامات ارتفاع أو انخفاض شديد في السكر: تشوش ذهني، فقدان وعي، تنفس سريع، عطش شديد مع تبول متكرر، أو رائحة فواكه في النفس.",
            "doctor": "راجع الطبيب لإجراء فحص سكر الدم إذا شعرت بعطش متكرر، أو تبول متكرر، أو خسارة وزن غير مبررة، أو جروح لا تلتئم، أو تشوش رؤية — أو إذا كان لديك عوامل خطر.",
        },
        "en": {
            "title": "Diabetes",
            "what": "Diabetes is a condition in which blood sugar stays high because the body does not produce enough insulin or cannot use it effectively, affecting how food is turned into energy.",
            "causes": ["Insulin resistance (type 2 — most common)", "No insulin production (type 1)",
                       "Family and genetic factors", "Obesity and low activity", "Unbalanced diet",
                       "Gestational diabetes"],
            "worry": "Get urgent care if signs of very high or very low sugar appear: confusion, loss of consciousness, rapid breathing, extreme thirst with frequent urination, or a fruity breath smell.",
            "doctor": "See a doctor for a blood sugar test if you have frequent thirst, frequent urination, unexplained weight loss, slow-healing wounds, or blurry vision — or if you have risk factors.",
        },
    },
    "hypertension": {
        "emoji": "🩺", "category": "term",
        "aliases": ["ضغط", "الضغط", "ضغط الدم", "الضغط المرتفع", "high blood pressure", "hypertension", "raised blood pressure"],
        "causes_label": {"ar": "💡 الأسباب الشائعة", "en": "💡 Common causes"},
        "ar": {
            "title": "ارتفاع ضغط الدم",
            "what": "ارتفاع ضغط الدم هو قوة ضخ الدم على جدران الشرايين أعلى من المعدل الطبيعي بشكل مستمر. غالباً لا تظهر له أعراض، ولهذا يسمى «القاتل الصامت»، ويُكتشف بالقياس المنتظم.",
            "causes": ["العامل الوراثي", "زيادة الملح في الطعام", "السمنة وقلة الحركة",
                       "التدخين والكحول", "التوتر المزمن", "تقدم العمر",
                       "بعض الأمراض مثل الكلى أو الغدة الدرقية"],
            "worry": "اطلب رعاية عاجلة إذا صاحب الضغط المرتفع صداع شديد، أو ألم صدر، أو ضيق تنفس، أو تشوش، أو تنميل أو ضعف في جانب، أو اضطراب رؤية — خاصةً مع قراءة مرتفعة جداً.",
            "doctor": "راجع الطبيب للقياس والتقييم إذا تكررت القراءات مرتفعة، أو كان لديك عوامل خطر (تدخين، سمنة، تاريخ عائلي)، أو رافقك صداع مستمر أو دوخة.",
        },
        "en": {
            "title": "High blood pressure",
            "what": "High blood pressure means the force of blood against your artery walls is higher than normal over time. It often has no symptoms, which is why it is called the \"silent killer,\" and it is found by regular measurement.",
            "causes": ["Genetics", "Too much salt in the diet", "Obesity and inactivity",
                       "Smoking and alcohol", "Chronic stress", "Aging",
                       "Conditions such as kidney or thyroid disease"],
            "worry": "Get urgent care if high readings come with a severe headache, chest pain, shortness of breath, confusion, numbness or weakness on one side, or vision changes — especially with a very high reading.",
            "doctor": "See a doctor for measurement and evaluation if readings are repeatedly high, you have risk factors (smoking, obesity, family history), or you have persistent headache or dizziness.",
        },
    },
    "asthma": {
        "emoji": "🫁", "category": "term",
        "aliases": ["ربو", "الربو", "حساسية الصدر", "asthma", "wheezing"],
        "causes_label": {"ar": "💡 الأسباب الشائعة", "en": "💡 Common causes"},
        "ar": {
            "title": "الربو",
            "what": "الربو هو حالة مزمنة تلتهب فيها المجاري الهوائية وتضيق، فيسبب صعوبة التنفس وأزيزاً (صوت صفير) وسعالاً، خاصةً في الليل أو مع النشاط.",
            "causes": ["حساسية من الغبار أو العفن أو الحيوانات", "حبوب اللقاح",
                       "المواد المهيجة مثل الدخان والروائح القوية", "العدوى التنفسية",
                       "التمرين الشاق", "التغيرات الجوية الباردة"],
            "worry": "اطلب الإسعاف فوراً إذا كان الأزيز شديداً أو مفاجئاً، أو صعب على المريض الكلام أو التنفس، أو ظهرت زرقة الشفاه أو الأظافر، أو لم تتحسن بعد استخدام البخاخة.",
            "doctor": "راجع الطبيب لوضع خطة علاجية إذا تكررت النوبات، أو استيقظت من النوم بسبب السعال أو ضيق التنفس، أو استخدمت البخاخة أكثر من المعتاد.",
        },
        "en": {
            "title": "Asthma",
            "what": "Asthma is a chronic condition in which the airways become inflamed and narrow, causing difficulty breathing, wheezing, and coughing, especially at night or during activity.",
            "causes": ["Allergies to dust, mold, or animals", "Pollen",
                       "Irritants such as smoke and strong smells", "Respiratory infections",
                       "Strenuous exercise", "Cold weather changes"],
            "worry": "Call emergency services immediately if wheezing is severe or sudden, the person cannot talk or breathe normally, lips or nails turn blue, or symptoms do not improve after using the inhaler.",
            "doctor": "See a doctor for a treatment plan if attacks recur, you wake up at night with coughing or breathlessness, or you use your inhaler more often than usual.",
        },
    },
    "wbc": {
        "emoji": "🩸", "category": "test",
        "aliases": ["wbc", "كريات بيضاء", "كورات بيضاء", "خلايا الدم البيضاء", "خلايا بيضاء",
                    "white blood cells", "leukocytes"],
        "causes_label": {"ar": "💡 لماذا يُطلب هذا الفحص؟", "en": "💡 Why is this measured?"},
        "ar": {
            "title": "WBC — كريات الدم البيضاء",
            "what": "WBC هو اختصار لعدد كريات الدم البيضاء (خلايا الدم البيضاء). هذه الخلايا جزء من جهاز المناعة وتساعد الجسم على مقاومة العدوى، ويُقاس عددها ضمن فحص تعداد الدم الكامل (CBC).",
            "causes": ["تقييم وجود عدوى أو التهاب", "المساعدة في تشخيص بعض الأمراض",
                       "متابعة علاجات معينة", "الكشف الروتيني في الفحوصات العامة"],
            "worry": "القيم المرتفعة جداً أو المنخفضة جداً قد تشير إلى حالة تحتاج تقييماً طبيباً سريعاً، خاصةً مع حمى أو تعب شديد أو نزيف. أي قراءة خارج الطبيعي تستدعي مراجعة الطبيب لتفسيرها.",
            "doctor": "راجع الطبيب لفهم نتيجتك: الارتفاع أو الانخفاض وحده لا يكفي للتشخيص، ويحتاج تفسيره إلى النظر في بقية النتائج والسياق الصحي.",
        },
        "en": {
            "title": "WBC — White blood cells",
            "what": "WBC stands for the white blood cell count. These cells are part of the immune system and help the body fight infections. They are measured as part of the complete blood count (CBC).",
            "causes": ["Checking for infection or inflammation", "Helping diagnose certain conditions",
                       "Monitoring some treatments", "Routine screening in general check-ups"],
            "worry": "Very high or very low values may point to a condition that needs prompt medical evaluation, especially with fever, severe tiredness, or bleeding. Any out-of-range reading should be discussed with a doctor.",
            "doctor": "See a doctor to understand your result: a high or low value alone is not a diagnosis and must be interpreted with the rest of the results and your health context.",
        },
    },
    "rbc": {
        "emoji": "🩸", "category": "test",
        "aliases": ["rbc", "كريات حمراء", "كورات حمراء", "خلايا الدم الحمراء", "خلايا حمراء", "red blood cells", "erythrocytes"],
        "causes_label": {"ar": "💡 لماذا يُطلب هذا الفحص؟", "en": "💡 Why is this measured?"},
        "ar": {
            "title": "RBC — كريات الدم الحمراء",
            "what": "RBC هو عدد كريات الدم الحمراء، وهي الخلايا التي تحمل الأكسجين من الرئتين إلى جميع أنحاء الجسم عبر الهيموجلوبين.",
            "causes": ["تقييم فقر الدم", "التحقق من قدرة الدم على حمل الأكسجين",
                       "متابعة الأمراض المزمنة", "الفحص الروتيني"],
            "worry": "القيم المنخفضة جداً تشير غالباً لفقر دم وقد تسبب دوخة وتعباً وخفقاناً، والقيم المرتفعة جداً قد تشير لحالات تحتاج تقييماً — راجع الطبيب لتفسير النتيجة.",
            "doctor": "راجع الطبيب إذا كانت نتيجتك خارج النطاق، خاصةً مع أعراض مثل التعب والشحوب وضيق التنفس.",
        },
        "en": {
            "title": "RBC — Red blood cells",
            "what": "RBC is the red blood cell count. These cells carry oxygen from the lungs to the rest of the body using hemoglobin.",
            "causes": ["Assessing anemia", "Checking the blood's oxygen-carrying ability",
                       "Monitoring chronic conditions", "Routine screening"],
            "worry": "Very low values usually suggest anemia and may cause dizziness, tiredness, and palpitations; very high values may point to conditions needing evaluation — see a doctor to interpret the result.",
            "doctor": "See a doctor if your result is out of range, especially with symptoms such as tiredness, paleness, and shortness of breath.",
        },
    },
    "hgb": {
        "emoji": "🩸", "category": "test",
        "aliases": ["hgb", "hb", "هيموجلوبين", "هيموغلوبين", "خضاب الدم", "hemoglobin", "haemoglobin"],
        "causes_label": {"ar": "💡 لماذا يُطلب هذا الفحص؟", "en": "💡 Why is this measured?"},
        "ar": {
            "title": "HGB — الهيموجلوبين",
            "what": "الهيموجلوبين هو البروتين الموجود داخل كريات الدم الحمراء الذي يحمل الأكسجين ويعطي الدم لونه الأحمر. انخفاضه هو المقياس الرئيسي لفقر الدم.",
            "causes": ["تشخيص فقر الدم وتحديد شدته", "متابعة نزيف أو فقدان دم",
                       "متابعة الأمراض المزمنة", "فحص الحمل والولادة", "الفحص الروتيني"],
            "worry": "الانخفاض الشديد قد يسبب تعباً ودوخة وضيق تنفس وخفقاناً ويحتاج تقييماً سريعاً، خاصةً مع نزيف. الارتفاع الشديد يحتاج أيضاً تقييماً.",
            "doctor": "راجع الطبيب لتفسير النتيجة — تختلف القيم الطبيعية حسب العمر والجنس والحمل، ولا تُفسر منفردة عن باقي الفحوصات.",
        },
        "en": {
            "title": "HGB — Hemoglobin",
            "what": "Hemoglobin is the protein inside red blood cells that carries oxygen and gives blood its red color. Low levels are the main measure of anemia.",
            "causes": ["Diagnosing anemia and its severity", "Following up bleeding or blood loss",
                       "Monitoring chronic conditions", "Pregnancy and delivery checks", "Routine screening"],
            "worry": "Very low levels can cause tiredness, dizziness, shortness of breath, and palpitations and need prompt evaluation, especially with bleeding. Very high levels also need evaluation.",
            "doctor": "See a doctor to interpret the result — normal ranges depend on age, sex, and pregnancy, and should not be read in isolation.",
        },
    },
    "platelets": {
        "emoji": "🩸", "category": "test",
        "aliases": ["plt", "صفائح", "الصفائح", "الصفائح الدمويه", "platelets", "thrombocytes", "platelet count"],
        "causes_label": {"ar": "💡 لماذا يُطلب هذا الفحص؟", "en": "💡 Why is this measured?"},
        "ar": {
            "title": "PLT — الصفائح الدموية",
            "what": "الصفائح الدموية هي أجزاء صغيرة في الدم تساعد على تجلط الدم وإيقاف النزيف عند الجروح. تُقاس ضمن فحص تعداد الدم الكامل.",
            "causes": ["تقييم اضطرابات التجلط والنزيف", "الكشف قبل العمليات", "متابعة بعض العلاجات",
                       "الفحص الروتيني"],
            "worry": "الانخفاض الشديد قد يزيد خطر النزيف والكدمات، والارتفاع الشديد قد يزيد خطر الجلطات — أي انحراف كبير يحتاج تقييماً طبياً.",
            "doctor": "راجع الطبيب إذا كانت النتيجة خارج النطاق، أو لاحظت كدمات أو نزيفاً غير معتاد أو نزيف لثة.",
        },
        "en": {
            "title": "PLT — Platelets",
            "what": "Platelets are tiny blood cells that help the blood clot and stop bleeding after injuries. They are measured as part of the complete blood count.",
            "causes": ["Assessing bleeding and clotting disorders", "Pre-surgery screening", "Monitoring some treatments",
                       "Routine screening"],
            "worry": "Very low levels may increase the risk of bleeding and bruising; very high levels may increase clot risk — any major deviation needs medical evaluation.",
            "doctor": "See a doctor if the result is out of range, or if you notice unusual bruising, bleeding, or bleeding gums.",
        },
    },
    "neutrophils": {
        "emoji": "🩸", "category": "test",
        "aliases": ["neut", "نيتروفيلز", "النيتروفيل", "نيتروفيلات", "neutrophils", "neutrophil"],
        "causes_label": {"ar": "💡 لماذا يُطلب هذا الفحص؟", "en": "💡 Why is this measured?"},
        "ar": {
            "title": "NEUT — النيتروفيلز",
            "what": "النيتروفيلز هي أكثر أنواع كريات الدم البيضاء عدداً، وهي خط الدفاع الأول ضد العدوى البكتيرية. يُعطى عددها كنسبة مئوية ضمن تحليل صورة الدم.",
            "causes": ["تقييم وجود عدوى بكتيرية", "متابعة الالتهابات", "تقييم استجابة الجسم للعلاج"],
            "worry": "الارتفاع الكبير قد يشير لعدوى أو التهاب نشط، والانخفاض الشديد قد يزيد خطر العدوى — القيم الشديدة تحتاج تقييماً طبياً.",
            "doctor": "راجع الطبيب لتفسير النتيجة: ارتفاع أو انخفاض النيتروفيلز قد يحدث لأسباب متعددة ولا يُشخَّص بمفرده.",
        },
        "en": {
            "title": "NEUT — Neutrophils",
            "what": "Neutrophils are the most common type of white blood cell and the first line of defense against bacterial infections. Their number is given as a percentage in a differential blood count.",
            "causes": ["Checking for bacterial infection", "Monitoring inflammation", "Assessing response to treatment"],
            "worry": "Large increases may point to active infection or inflammation; very low levels may increase infection risk — severe values need medical evaluation.",
            "doctor": "See a doctor to interpret the result: high or low neutrophils can have many causes and are not a diagnosis by themselves.",
        },
    },
    "lymphocytes": {
        "emoji": "🩸", "category": "test",
        "aliases": ["lymph", "ليمف", "اللمفاويات", "lymphocytes", "lymphocyte"],
        "causes_label": {"ar": "💡 لماذا يُطلب هذا الفحص؟", "en": "💡 Why is this measured?"},
        "ar": {
            "title": "LYMPH — اللمفاويات",
            "what": "اللمفاويات نوع من كريات الدم البيضاء المسؤولة عن المناعة ومواجهة العدوى الفيروسية وإنتاج الأجسام المضادة.",
            "causes": ["تقييم العدوى الفيروسية", "متابعة الجهاز المناعي", "الفحص الروتيني"],
            "worry": "الارتفاع عادة ما يرتبط بعدوى فيروسية، والانخفاض الشديد يحتاج تقييماً — راجع الطبيب لتفسير النتيجة في سياقها.",
            "doctor": "راجع الطبيب إذا كانت النسبة خارج النطاق، خصوصاً مع أعراض مثل الحمى المستمرة أو تضخم الغدد.",
        },
        "en": {
            "title": "LYMPH — Lymphocytes",
            "what": "Lymphocytes are a type of white blood cell responsible for immunity, fighting viral infections, and producing antibodies.",
            "causes": ["Assessing viral infections", "Monitoring the immune system", "Routine screening"],
            "worry": "A rise is usually linked to a viral infection; a severe drop needs evaluation — see a doctor to interpret the result in context.",
            "doctor": "See a doctor if the percentage is out of range, especially with symptoms such as persistent fever or swollen glands.",
        },
    },
    "mcv": {
        "emoji": "🩸", "category": "test",
        "aliases": ["mcv", "متوسط حجم الكريه", "متوسط حجم الخلية", "mean corpuscular volume"],
        "causes_label": {"ar": "💡 لماذا يُطلب هذا الفحص؟", "en": "💡 Why is this measured?"},
        "ar": {
            "title": "MCV — متوسط حجم الكرية الحمراء",
            "what": "MCV يقيس متوسط حجم كريات الدم الحمراء، ويساعد في تحديد نوع فقر الدم (نقص الحديد مثلاً أو نقص الفيتامينات).",
            "causes": ["تحديد سبب فقر الدم", "تقييم نقص الفيتامينات", "الفحص الروتيني"],
            "worry": "الارتفاع أو الانخفاض وحده لا يشخص شيئاً، لكنه يوجّه الطبيب لنوع التحاليل المكملة — القيم الشاذة تحتاج تقييماً.",
            "doctor": "راجع الطبيب لتفسير MCV مع الهيموجلوبين وبقية المؤشرات معاً.",
        },
        "en": {
            "title": "MCV — Mean corpuscular volume",
            "what": "MCV measures the average size of red blood cells and helps identify the type of anemia (such as iron deficiency or vitamin deficiency).",
            "causes": ["Identifying the cause of anemia", "Assessing vitamin deficiencies", "Routine screening"],
            "worry": "A high or low value alone does not diagnose anything, but it guides which follow-up tests a doctor needs — unusual values need evaluation.",
            "doctor": "See a doctor to interpret MCV together with hemoglobin and the other indices.",
        },
    },
    "paracetamol": {
        "emoji": "💊", "category": "medication",
        "aliases": ["باراسيتامول", "بنادول", "بانادول", "باراسيتومول", "اسيتامينوفين", "panadol", "paracetamol",
                    "acetaminophen", "tylenol", "calpol"],
        "causes_label": {"ar": "💊 الاستخدامات الشائعة", "en": "💊 Common uses"},
        "ar": {
            "title": "الباراسيتامول (بنادول)",
            "what": "الباراسيتامول مسكن ألم وخافض للحرارة من أكثر الأدوية شيوعاً وأماناً عند الالتزام بالجرعة الموصوفة. مناسب لمن لا يناسبهم مضادات الالتهاب مثل الأسبرين أو البروفين.",
            "causes": ["تسكين الألم الخفيف إلى المتوسط (صداع، عضلات، ألم أسنان)", "خفض الحمى",
                       "المسكن الأول أثناء الحمل (حسب إرشاد الطبيب)"],
            "worry": "أهم خطر هو تجاوز الجرعة اليومية القصوى (عادة 4 جرامات للبالغين الأصحاء) لأنه قد يضر الكبد. لا تجمع بين عدة أدوية تحتوي باراسيتامول، واطلب رعاية طبية فورية إذا شككت بتجاوز الجرعة.",
            "doctor": "راجع الطبيب أو الصيدلي قبل الاستخدام المنتظم إذا كنت تعاني من أمراض كبد، أو تتناول مميعات دم، أو كنت حاملاً أو مرضعة، أو إذا استمر الألم أو الحمى أكثر من 3 أيام.",
        },
        "en": {
            "title": "Paracetamol (Panadol)",
            "what": "Paracetamol is a pain reliever and fever reducer, one of the most common and safest medications when used at the recommended dose. It suits people who cannot take anti-inflammatories such as aspirin or ibuprofen.",
            "causes": ["Relieving mild to moderate pain (headache, muscles, toothache)", "Reducing fever",
                       "A common painkiller during pregnancy (as directed by a doctor)"],
            "worry": "The main risk is exceeding the daily maximum dose (usually 4 grams for healthy adults) because it can harm the liver. Do not combine several products containing paracetamol, and seek urgent care if you suspect an overdose.",
            "doctor": "Check with a doctor or pharmacist before regular use if you have liver disease, take blood thinners, are pregnant or breastfeeding, or if pain or fever lasts more than 3 days.",
        },
    },
    "ibuprofen": {
        "emoji": "💊", "category": "medication",
        "aliases": ["بروفين", "بروفن", "ادفيل", "ibuprofen", "advil", "motrin", "nurofen"],
        "causes_label": {"ar": "💊 الاستخدامات الشائعة", "en": "💊 Common uses"},
        "ar": {
            "title": "البروفين (إيبوبروفين)",
            "what": "البروفين مسكن ألم ومضاد التهاب وخافض حرارة من مجموعة مضادات الالتهاب غير الستيرويدية (NSAIDs)، ويعمل على تقليل الالتهاب والألم والتورم.",
            "causes": ["تسكين الألم والالتهاب (مفاصل، عضلات، صداع)", "خفض الحمى",
                       "تخفيف آلام الدورة الشهرية"],
            "worry": "قد يهيج المعدة إذا أُخذ بدون طعام، وغير مناسب لمن لديهم قرحة معدة أو نزيف أو مشاكل كلى، أو أثناء الجفاف. تجنبه إذا كنت تتناول مميعات دم أو كورتيزون — واطلب رعاية طبية عند أعراض النزف.",
            "doctor": "راجع الطبيب قبل استخدامه المنتظم إذا كنت حاملاً، أو لديك ربو تحسسي، أو أمراض كلى أو معدة، أو كنت مسناً، أو إذا استمر الألم أكثر من 3 أيام.",
        },
        "en": {
            "title": "Ibuprofen (Advil)",
            "what": "Ibuprofen is a pain reliever, anti-inflammatory, and fever reducer from the NSAID family that reduces inflammation, pain, and swelling.",
            "causes": ["Relieving pain and inflammation (joints, muscles, headache)", "Reducing fever",
                       "Easing menstrual cramps"],
            "worry": "It can irritate the stomach if taken without food and is not suitable for people with ulcers, bleeding, kidney problems, or dehydration. Avoid it with blood thinners or steroids — seek care if you notice bleeding symptoms.",
            "doctor": "Check with a doctor before regular use if you are pregnant, have aspirin-sensitive asthma, kidney or stomach disease, or are older, or if pain lasts more than 3 days.",
        },
    },
    "antibiotics": {
        "emoji": "💊", "category": "medication",
        "aliases": ["مضاد حيوي", "مضادات حيوية", "مضاد حيوي", "antibiotic", "antibiotics", "اموكسيسيلين", "amoxicillin"],
        "causes_label": {"ar": "💊 الاستخدامات الشائعة", "en": "💊 Common uses"},
        "ar": {
            "title": "المضادات الحيوية",
            "what": "المضادات الحيوية أدوية تعالج الالتهابات التي تسببها البكتيريا فقط، ولا تعمل ضد الفيروسات مثل نزلات البرد والإنفلونزا. يجب استخدامها فقط بوصفة طبية.",
            "causes": ["علاج الالتهابات البكتيرية (التهاب الحلق البكتيري، التهاب الأذن، التهاب المسالك البولية)"],
            "worry": "أكمل الجرعة كاملة كما وصفها الطبيب حتى لو تحسنت. لا تشارك المضاد الحيوي مع الآخرين ولا تحتفظ به للاستخدام لاحقاً، فالاستخدام غير الصحيح يزيد مقاومة البكتيريا. اطلب رعاية فورية عند طفح جلد شديد أو صعوبة تنفس أو تورم وجه بعد الجرعة.",
            "doctor": "راجع الطبيب إذا استمرت الأعراض أو ساءت بعد بدء المضاد، أو ظهرت إسهال شديد، أو كانت الأعراض فيروسية لا تحتاج أصلاً للمضاد.",
        },
        "en": {
            "title": "Antibiotics",
            "what": "Antibiotics treat infections caused by bacteria only. They do not work against viruses such as colds and flu, and should be used only with a prescription.",
            "causes": ["Treating bacterial infections (strep throat, ear infection, urinary tract infection)"],
            "worry": "Finish the full course as prescribed even if you feel better. Do not share antibiotics or save them for later — improper use increases bacterial resistance. Seek urgent care for a severe rash, trouble breathing, or facial swelling after a dose.",
            "doctor": "See a doctor if symptoms persist or worsen after starting the antibiotic, you develop severe diarrhea, or the illness is viral and did not need antibiotics.",
        },
    },
    "cbc": {
        "emoji": "🧪", "category": "test",
        "aliases": ["cbc", "تعداد الدم الكامل", "تعداد الدم", "تحليل الدم الكامل", "فحص الدم", "عد دم",
                    "complete blood count", "blood count", "full blood count", "فحص cbc"],
        "causes_label": {"ar": "💡 ماذا يكشف؟", "en": "💡 What does it reveal?"},
        "ar": {
            "title": "تحليل CBC — تعداد الدم الكامل",
            "what": "تحليل CBC هو فحص دم شامل يقيس مكونات الدم الرئيسية: كريات الدم الحمراء والهيموجلوبين، كريات الدم البيضاء، والصفائح الدموية، ويستخدم لتقييم الصحة العامة وكشف اضطرابات مثل فقر الدم والعدوى.",
            "causes": ["قياس كريات الدم الحمراء والهيموجلوبين (فقر الدم)", "قياس كريات الدم البيضاء (العدوى والالتهاب)",
                       "قياس الصفائح الدموية (التجلط والنزيف)", "متابعة الأمراض المزمنة",
                       "الفحص الروتيني قبل العمليات"],
            "worry": "CBC لا يشخص بمفرده، لكن القيم الحرجة (مرتفعة أو منخفضة جداً) قد تستدعي تقييماً عاجلاً — اتبع توجيهات الطبيب المعالج.",
            "doctor": "راجع الطبيب لتفسير النتيجة كاملة: التفسير الصحيح يعتمد على بقية النتائج معاً، وليس على قيمة واحدة منفردة.",
        },
        "en": {
            "title": "CBC — Complete Blood Count",
            "what": "A CBC is a comprehensive blood test that measures the main blood components: red blood cells and hemoglobin, white blood cells, and platelets. It is used to assess general health and detect conditions such as anemia and infection.",
            "causes": ["Measuring red blood cells and hemoglobin (anemia)", "Measuring white blood cells (infection and inflammation)",
                       "Measuring platelets (clotting and bleeding)", "Monitoring chronic conditions",
                       "Routine pre-surgery screening"],
            "worry": "A CBC does not diagnose by itself, but critical values (very high or very low) may require urgent evaluation — follow your treating doctor's guidance.",
            "doctor": "See a doctor to interpret the full result: correct interpretation depends on all results together, not on a single value in isolation.",
        },
    },
    "bmi": {
        "emoji": "⚖️", "category": "term",
        "aliases": ["bmi", "مؤشر كتلة الجسم", "كتلة الجسم", "body mass index"],
        "causes_label": {"ar": "💡 ماذا يكشف؟", "en": "💡 What does it reveal?"},
        "ar": {
            "title": "مؤشر كتلة الجسم (BMI)",
            "what": "مؤشر كتلة الجسم هو رقم يُحسب من الطول والوزن لتقييم ما إذا كان الوزن في نطاق طبيعي، ناقصاً، زائداً، أو سمنة. مؤشر تقريبي ولا يقيس تكوين الجسم مباشرة.",
            "causes": ["تقييم الوزن نسبة للطول", "كشف خطر الوزن الزائد المرتبط بأمراض مثل السكري والضغط",
                       "تحديد أهداف صحية"],
            "worry": "BMI لا يقيس العضلات ولا توزيع الدهون، ولا ينطبق على الأطفال بنفس الطريقة — لا تتخذ قرارات صحية خطرة بناءً عليه وحده، واستشر مختصاً.",
            "doctor": "استشر الطبيب أو أخصائي التغذية إذا كان مؤشرك في نطاق السمنة أو النحافة، أو لضبط خطة صحية تناسب جسمك.",
        },
        "en": {
            "title": "Body Mass Index (BMI)",
            "what": "Body Mass Index is a number calculated from height and weight to assess whether weight is in a normal, underweight, overweight, or obese range. It is a rough measure and does not directly measure body composition.",
            "causes": ["Assessing weight relative to height", "Flagging overweight risk linked to conditions such as diabetes and high blood pressure",
                       "Setting health goals"],
            "worry": "BMI does not measure muscle or fat distribution and does not apply to children the same way — do not make risky health decisions based on it alone; consult a professional.",
            "doctor": "Consult a doctor or dietitian if your index is in the obesity or underweight range, or to set a healthy plan that fits your body.",
        },
    },
    "cholesterol": {
        "emoji": "🧪", "category": "test",
        "aliases": ["كوليسترول", "الكوليسترول", "الدهون", "كولسترول", "cholesterol", "lipids", "ldl", "hdl", "triglycerides"],
        "causes_label": {"ar": "💡 ماذا يكشف؟", "en": "💡 What does it reveal?"},
        "ar": {
            "title": "الكوليسترول",
            "what": "الكوليسترول مادة دهنية ضرورية لبناء الخلايا، لكن ارتفاعه في الدم (خاصةً النوع الضار LDL) يزيد خطر تراكم الدهون في الشرايين وأمراض القلب والجلطات.",
            "causes": ["قياس الكوليسترول الكلي", "قياس الكوليسترول الضار (LDL) والنافع (HDL)",
                       "قياس الدهون الثلاثية (Triglycerides)", "تقييم خطر أمراض القلب"],
            "worry": "ارتفاع LDL والدهون الثلاثية يزيد خطر الجلطات وأمراض القلب — خاصةً مع التدخين أو الضغط أو السكري. راجع طبيبك لوضع خطة، ولا تتوقف عن أدوية الدهون دون استشارته.",
            "doctor": "راجع الطبيب لإجراء فحص الدهون إذا كان عمرك فوق 40، أو لديك تاريخ عائلي لأمراض القلب، أو سكري، أو ضغط، أو تدخين، أو سمنة — وكرر الفحص دورياً حسب التوصية.",
        },
        "en": {
            "title": "Cholesterol",
            "what": "Cholesterol is a fatty substance needed to build cells, but high levels in the blood (especially the harmful LDL type) increase the risk of fat building up in arteries, heart disease, and clots.",
            "causes": ["Measuring total cholesterol", "Measuring LDL (bad) and HDL (good) cholesterol",
                       "Measuring triglycerides", "Assessing heart disease risk"],
            "worry": "High LDL and triglycerides increase the risk of clots and heart disease — especially with smoking, high blood pressure, or diabetes. See your doctor for a plan and do not stop cholesterol medications without advice.",
            "doctor": "See a doctor for a lipid panel if you are over 40, have a family history of heart disease, diabetes, high blood pressure, smoking, or obesity — and repeat it periodically as recommended.",
        },
    },
}

# ---------------------------------------------------------------------------
# "Explain Simply" glossary — three levels per term
# ---------------------------------------------------------------------------
GLOSSARY = {
    "wbc": {
        "aliases": ["wbc", "كريات بيضاء", "كورات بيضاء", "خلايا الدم البيضاء", "خلايا بيضاء", "white blood cells", "leukocytes"],
        "ar": {
            "title": "WBC — كريات الدم البيضاء",
            "very_simple": "خلايا الدم البيضاء هي «جنود الدفاع» في جسمك، تساعد جسمك على محاربة العدوى والمرض. نسميها «بيضاء» فقط لأن مظهرها يميزها عن خلايا الدم الحمراء التي تحمل الأكسجين.",
            "basic": "WBC اختصار لعدد خلايا الدم البيضاء، وهي جزء من جهاز المناعة تساعد الجسم على مقاومة العدوى. ارتفاع أو انخفاض هذه القيمة قد يحدث لعدة أسباب، ولا يمكن تحديد السبب من هذه النتيجة وحدها.",
            "advanced": "كثرة الكريات البيض (WBC) تعكس إجمالي خلايا الدم البيضاء، وتشمل أنواعاً مثل النيتروفيلز واللمفاويات. ارتفاعها قد يترافق مع عدوى أو التهاب أو حالات أخرى، وانخفاضها قد يترافق مع أسباب فيروسية أو دوائية أو نخاعية — ويتطلب تفسيره النظر في صورة الدم الكاملة والسياق السريري.",
        },
        "en": {
            "title": "WBC — White blood cells",
            "very_simple": "White blood cells are your body's defenders — they help fight infections and illness. They are called \"white\" only because of how they look compared with the red cells that carry oxygen.",
            "basic": "WBC stands for the white blood cell count, part of the immune system that helps the body fight infection. A high or low value can happen for many reasons, and the cause cannot be determined from this single result.",
            "advanced": "The white blood cell (WBC) count reflects the total number of leukocytes, including subtypes such as neutrophils and lymphocytes. Elevation may accompany infection, inflammation, or other conditions, while a reduction may relate to viral, drug-related, or marrow causes — interpretation requires the full blood picture and clinical context.",
        },
    },
    "rbc": {
        "aliases": ["rbc", "كريات حمراء", "كورات حمراء", "خلايا الدم الحمراء", "خلايا حمراء", "red blood cells", "erythrocytes"],
        "ar": {
            "title": "RBC — كريات الدم الحمراء",
            "very_simple": "خلايا الدم الحمراء هي «شاحنات التوصيل» في جسمك، تحمل الأكسجين من الرئتين وتوصله لكل أجزاء الجسم.",
            "basic": "RBC هو عدد خلايا الدم الحمراء التي تحمل الأكسجين عبر الهيموجلوبين. انخفاضها يرتبط غالباً بفقر الدم، وارتفاعها قد يكون طبيعياً أو لأسباب تحتاج تقييماً.",
            "advanced": "عديد كريات الدم الحمراء (RBC) يعكس خلايا نقل الأكسجين. انخفاضه قد يرافق فقر الدم باختلاف آلياته، وارتفاعه قد يكون تعويضياً (ارتفاع المناطق أو نقص الأكسجين) أو أولي — ويتطلب تفسيره الهيموجلوبين والمؤشرات الكرية والفروقات الخلوية.",
        },
        "en": {
            "title": "RBC — Red blood cells",
            "very_simple": "Red blood cells are the delivery trucks of your body — they pick up oxygen from the lungs and carry it to every part of the body.",
            "basic": "RBC is the red blood cell count, which carries oxygen using hemoglobin. A low count is usually linked to anemia; a high count can be normal or need evaluation.",
            "advanced": "The red blood cell (RBC) count reflects oxygen-carrying cells. A reduction may accompany anemia of various mechanisms, and an elevation may be compensatory (high altitude, hypoxia) or primary — interpretation requires hemoglobin, red cell indices, and the differential.",
        },
    },
    "hgb": {
        "aliases": ["hgb", "hb", "هيموجلوبين", "هيموغلوبين", "خضاب الدم", "hemoglobin", "haemoglobin"],
        "ar": {
            "title": "HGB — الهيموجلوبين",
            "very_simple": "الهيموجلوبين هو الجزء «الناقل للأكسجين» داخل خلايا الدم الحمراء، ويساعد الدم على حمل الأكسجين من رئتيك لكل جسمك.",
            "basic": "الهيموجلوبين بروتين داخل كريات الدم الحمراء يحمل الأكسجين ويعطي الدم لونه الأحمر. انخفاضه هو المؤشر الرئيسي لفقر الدم، وتختلف القيم الطبيعية حسب العمر والجنس.",
            "advanced": "الهيموجلوبين (HGB) هو البروتين الحامل للأكسجين داخل الكريات الحمراء، ويُعد المقياس الأساسي لقدرة الدم النقلية. نقصه يعرف بفقر الدم وقد ينجم عن نقص الحديد أو الفيتامينات أو فقدان الدم أو أمراض مزمنة أو خضابية — والتفسير يتطلب سياق المريض الكامل.",
        },
        "en": {
            "title": "HGB — Hemoglobin",
            "very_simple": "Hemoglobin is the oxygen-carrying part inside your red blood cells — it helps your blood bring oxygen from your lungs to your whole body.",
            "basic": "Hemoglobin is a protein inside red blood cells that carries oxygen and gives blood its red color. A low level is the main indicator of anemia, and normal values depend on age and sex.",
            "advanced": "Hemoglobin (HGB) is the oxygen-carrying protein within red cells and the primary measure of blood oxygen capacity. A deficiency defines anemia, which may result from iron or vitamin deficiency, blood loss, chronic disease, or hemoglobinopathies — interpretation requires the full patient context.",
        },
    },
    "plt": {
        "aliases": ["plt", "صفائح", "الصفائح", "الصفائح الدمويه", "platelets", "thrombocytes", "platelet count"],
        "ar": {
            "title": "PLT — الصفائح الدموية",
            "very_simple": "الصفائح الدموية هي «رقع الإسعاف» في دمك — تسد الجروح وتوقف النزيف.",
            "basic": "الصفائح الدموية أجزاء صغيرة تساعد الدم على التجلط وإيقاف النزيف. انخفاضها يزيد خطر النزيف، وارتفاعها يزيد خطر الجلطات — وكلاهما يحتاج تقييماً.",
            "advanced": "الصفيحات (PLT) عناصر خلوية صغيرة تلعب دوراً محورياً في التجلط. قلة الصفيحات قد ترافق أسباباً مناعية أو دوائية أو نقوية، وكثرة الصفيحات قد تكون تفاعلية أو أولية — وتتطلب متابعة وفحص لطاخة الدم عند الشك.",
        },
        "en": {
            "title": "PLT — Platelets",
            "very_simple": "Platelets are the \"plaster team\" of your blood — they plug wounds and stop bleeding.",
            "basic": "Platelets are tiny cells that help blood clot and stop bleeding. A low count raises bleeding risk; a high count raises clot risk — both need evaluation.",
            "advanced": "Platelets (PLT) are small cell fragments with a central role in hemostasis. Thrombocytopenia may accompany immune, drug-related, or marrow causes, while thrombocytosis may be reactive or primary — follow-up and a blood smear are often warranted.",
        },
    },
    "neut": {
        "aliases": ["neut", "نيتروفيلز", "النيتروفيل", "نيتروفيلات", "neutrophils", "neutrophil"],
        "ar": {
            "title": "NEUT — النيتروفيلز",
            "very_simple": "النيتروفيلز هي «الجيش الأول» في دفاعات جسمك ضد العدوى — أول من يصل عند وجود جرثومة.",
            "basic": "النيتروفيلز أكثر أنواع خلايا الدم البيضاء عدداً، وهي خط الدفاع الأول ضد العدوى البكتيرية. ارتفاعها قد يشير لعدوى أو التهاب، وانخفاضها الشديد قد يزيد خطر العدوى.",
            "advanced": "النيتروفيلز (NEUT) أكثر الخلايا المحببة العدلة عدداً وهي أول استجابة خلوية للعدوى البكتيرية. ارتفاعها قد يرافق عدوى أو التهاباً أو استجابة إجهاد، ونقصها الشديد (قلة العدلات) قد يكون دوائي المنشأ أو مناعياً أو نخاعياً — ويستدعي تقييماً عاجلاً.",
        },
        "en": {
            "title": "NEUT — Neutrophils",
            "very_simple": "Neutrophils are the \"first army\" of your body's defenses — the first to arrive when there's an infection.",
            "basic": "Neutrophils are the most common type of white blood cell and the first line of defense against bacterial infections. A high count may point to infection or inflammation; a very low count may raise infection risk.",
            "advanced": "Neutrophils are the most numerous granulocytes and the first cellular response to bacterial infection. Elevation may accompany infection, inflammation, or stress responses; severe reduction (neutropenia) may be drug-induced, immune, or marrow-related — and warrants prompt evaluation.",
        },
    },
    "lymph": {
        "aliases": ["lymph", "ليمف", "اللمفاويات", "lymphocytes", "lymphocyte"],
        "ar": {
            "title": "LYMPH — اللمفاويات",
            "very_simple": "اللمفاويات هي «ذاكرة» جهاز المناعة — تتذكر الميكروبات السابقة وتساعد جسمك على محاربتها.",
            "basic": "اللمفاويات نوع من خلايا الدم البيضاء تعمل ضد العدوى الفيروسية وتنتج الأجسام المضادة. ارتفاعها شائع مع العدوى الفيروسية.",
            "advanced": "اللمفاويات (LYMPH) ركيزة المناعة التكيفية، وارتفاعها يرافق العدوى الفيروسية وبعض الاضطرابات الدموية، بينما نقصها قد يرافق حالات نقص المناعة أو الأمراض المزمنة — ويحتاج تفسيره إلى صورة الدم الكاملة.",
        },
        "en": {
            "title": "LYMPH — Lymphocytes",
            "very_simple": "Lymphocytes are the \"memory\" of your immune system — they remember past germs and help your body fight them.",
            "basic": "Lymphocytes are a type of white blood cell that fights viral infections and makes antibodies. A rise is common with viral infections.",
            "advanced": "Lymphocytes are the backbone of adaptive immunity; elevation accompanies viral infections and some blood disorders, while depletion may relate to immunodeficiency states or chronic disease — interpretation requires the full blood picture.",
        },
    },
    "mcv": {
        "aliases": ["mcv", "متوسط حجم الكريه", "متوسط حجم الخلية", "mean corpuscular volume"],
        "ar": {
            "title": "MCV — متوسط حجم الكرية الحمراء",
            "very_simple": "هذا المقياس يخبرنا عن «حجم» خلايا الدم الحمراء لديك — كبيرة أم صغيرة — ويساعد في معرفة نوع فقر الدم.",
            "basic": "MCV يقيس متوسط حجم كريات الدم الحمراء ويساعد في تحديد نوع فقر الدم: صغير الحجم قد يرتبط بنقص الحديد، وكبير الحجم قد يرتبط بنقص فيتامين ب12.",
            "advanced": "متوسط حجم الكرية (MCV) مؤشر كريّ يستخدم لتصنيف فقر الدم: فقر دم صغير الكريات (نقص حديد أو ثلاسيميا)، سويّ، أو كبير الكريات (نقص ب12 أو حمض فوليك) — ويُفسر مع الهيموجلوبين وMCH وMCHC.",
        },
        "en": {
            "title": "MCV — Mean corpuscular volume",
            "very_simple": "This measurement tells us the \"size\" of your red blood cells — small or large — and helps figure out the type of anemia.",
            "basic": "MCV measures the average red blood cell size and helps identify the anemia type: small cells often link to iron deficiency, large cells to vitamin B12 deficiency.",
            "advanced": "Mean corpuscular volume (MCV) is a red cell index used to classify anemia as microcytic (iron deficiency or thalassemia), normocytic, or macrocytic (B12 or folate deficiency) — interpreted with hemoglobin, MCH, and MCHC.",
        },
    },
    "hct": {
        "aliases": ["hct", "هيماتوكريت", "الهيماتوكريت", "hematocrit", "packed cell volume", "pcv"],
        "ar": {
            "title": "HCT — الهيماتوكريت",
            "very_simple": "الهيماتوكريت يقيس «النسبة» — كم من دمك عبارة عن خلايا حمراء مقارنة بالسوائل.",
            "basic": "الهيماتوكريت نسبة كريات الدم الحمراء إلى حجم الدم الكلي. ينخفض مع فقر الدم ويرتفع مع الجفاف أو نقص الأكسجين.",
            "advanced": "الهيماتوكريت (HCT) النسبة المئوية لحجم الكريات الحمراء من حجم الدم، ويعكس تركيزها. انخفاضه يترافق مع فقر الدم، وارتفاعه مع الجفاف أو كثرة الكريات الحمراء الثانوية أو الأولية.",
        },
        "en": {
            "title": "HCT — Hematocrit",
            "very_simple": "Hematocrit measures the \"proportion\" — how much of your blood is red cells compared with the liquid part.",
            "basic": "Hematocrit is the proportion of red blood cells in total blood volume. It drops with anemia and rises with dehydration or low oxygen.",
            "advanced": "Hematocrit (HCT) is the percentage of red cell volume in whole blood, reflecting red cell mass. A decrease accompanies anemia; an increase accompanies dehydration or secondary/primary erythrocytosis.",
        },
    },
    "conjunctivitis": {
        "aliases": ["التهاب الملتحمة", "رمد", "عين ورديه", "pink eye", "conjunctivitis"],
        "ar": {
            "title": "التهاب الملتحمة",
            "very_simple": "هو التهاب أو تهيج في الغشاء الذي يغطي الجزء الأبيض من العين والجزء الداخلي من الجفن، وله عدة أسباب محتملة. يسبب احمرار العين والشعور بالرمش والحكة.",
            "basic": "التهاب الملتحمة هو التهاب الغشاء الرقيق الذي يغطي العين، وأسبابه فيروسية أو بكتيرية أو تحسسية. غالباً ما يزول وحده خلال أسبوعين، مع النظافة وتجنب نقل العدوى.",
            "advanced": "التهاب الملتحمة (Conjunctivitis) التهاب الغشاء الملتحمي، ويصنف فيروسياً أو بكتيرياً أو تحسسياً أو كيميائياً. تتميز الصورة البكتيرية بإفرازات قيحية، والتحسسية بحكة وازدواج الجفن — ويشمل العلاج العناية والنظافة وقد يشمل مضادات موضعية حسب السبب.",
        },
        "en": {
            "title": "Conjunctivitis",
            "very_simple": "It's inflammation or irritation of the membrane that covers the white of the eye and the inner eyelid, and it has several possible causes. It makes the eye red and feel gritty or itchy.",
            "basic": "Conjunctivitis is inflammation of the thin membrane covering the eye, caused by viruses, bacteria, or allergies. It usually clears on its own within two weeks, with good hygiene to avoid spreading it.",
            "advanced": "Conjunctivitis is inflammation of the conjunctival membrane, classified as viral, bacterial, allergic, or chemical. Bacterial forms show purulent discharge, and allergic forms show itching and chemosis — management includes hygiene and may include topical agents depending on the cause.",
        },
    },
    "anemia": {
        "aliases": ["فقر الدم", "انيميا", "الانيميا", "anemia", "anaemia", "low hemoglobin"],
        "ar": {
            "title": "فقر الدم",
            "very_simple": "فقر الدم يعني أن دمك لا يحمل كمية كافية من الأكسجين، لأنه لا يوجد ما يكفي من «الناقلات» (خلايا الدم الحمراء) أو أن «المحمول» (الهيموجلوبين) قليل.",
            "basic": "فقر الدم انخفاض الهيموجلوبين أو كريات الدم الحمراء في الدم، فيقل الأكسجين الواصل للجسم. أكثر الأسباب شيوعاً نقص الحديد، وعلاجه يعتمد على معرفة السبب.",
            "advanced": "فقر الدم انخفاض في الهيموجلوبين أو الكتلة الكرية عن المعدل حسب العمر والجنس، وتصنيفه يتبع المؤشرات الكرية (MCV) إلى صغير/سوي/كبير الكريات، مما يوجه نحو نقص الحديد أو المزمنة أو نقص الفيتامينات أو الأمراض الدموية.",
        },
        "en": {
            "title": "Anemia",
            "very_simple": "Anemia means your blood doesn't carry enough oxygen because there aren't enough \"carriers\" (red blood cells) or the \"load\" (hemoglobin) is low.",
            "basic": "Anemia is a low hemoglobin or red blood cell level, so less oxygen reaches the body. The most common cause is iron deficiency, and treatment depends on finding the cause.",
            "advanced": "Anemia is a reduction in hemoglobin or red cell mass below age- and sex-specific norms. Classification by red cell indices (MCV) into micro/normo/macrocytic guides the workup toward iron deficiency, chronic disease, vitamin deficiency, or hematologic disease.",
        },
    },
    "erythema": {
        "aliases": ["erythematous", "erythema", "حمامى", "احمرار الجلد", "erythematous lesion"],
        "ar": {
            "title": "Erythematous (احمرار)",
            "very_simple": "تعني ببساطة أن الجلد في هذه المنطقة «أحمر». يحدث ذلك عندما يتدفق دم أكثر إلى المكان أو عندما يكون الجلد متهيجاً أو ملتهباً.",
            "basic": "Erythematous صفة طبية تعني وجود احمرار في منطقة معينة نتيجة زيادة تدفق الدم أو حدوث تهيج أو التهاب. الاحمرار نفسه ليس تشخيصاً، بل وصفٌ لمظهر يُفسر ضمن سياق الحالة.",
            "advanced": "Erythema هو احمرار الجلد أو الأغشية المخاطية الناتج عن توسع الأوعية الجلدية (Vasodilation) غالباً ضمن استجابة التهابية أو مناعية أو انعكاس عصبي — ويُستخدم كعلامة سريرية لا كتشخيص نهائي، ويقيَّم حسب الانتشار والحدود والاستجابة للضغط.",
        },
        "en": {
            "title": "Erythematous (redness)",
            "very_simple": "It simply means the skin in this area \"is red.\" That happens when more blood flows to the spot or when the skin is irritated or inflamed.",
            "basic": "Erythematous is a medical word meaning there is redness in an area due to increased blood flow or irritation and inflammation. The redness itself is not a diagnosis, just a description interpreted within the case context.",
            "advanced": "Erythema is redness of the skin or mucous membranes caused mainly by cutaneous vasodilation, often part of an inflammatory, immune, or neurogenic response — it is a clinical sign rather than a final diagnosis, assessed by extent, borders, and blanching.",
        },
    },
    "edema": {
        "aliases": ["edema", "oedema", "وذمه", "وذمة", "تورم", "تجمع سوائل", "swelling", "water retention"],
        "ar": {
            "title": "الوذمة (تورم)",
            "very_simple": "الوذمة تعني أن «سوائل زائدة» تجمعت في مكان من جسمك فصار منتفخاً، مثل انتفاخ القدمين بعد الجلوس الطويل.",
            "basic": "الوذمة تجمع سوائل في الأنسجة يسبب تورماً، وغالباً في القدمين والكاحلين والساقين. أسبابها متعددة من الوقوف الطويل والحرارة إلى مشاكل القلب أو الكلى أو الوريدية.",
            "advanced": "الوذمة (Edema) تسرب وتجمع السائل الخلالي، وقد تكون عامة أو موضعية، ومن أسبابها القصور الوريدي، القصور القلبي، القصور الكلوي، نقص الألبومين، أو الأدوية — وتقييمها يتطلب فحص العلامة (godet) وتحديد السبب.",
        },
        "en": {
            "title": "Edema (swelling)",
            "very_simple": "Edema means \"extra fluid\" has collected in a part of your body so it becomes puffy, like swollen feet after sitting for a long time.",
            "basic": "Edema is fluid building up in tissues, causing swelling, often in the feet, ankles, and legs. Causes range from standing too long and heat to heart, kidney, or vein problems.",
            "advanced": "Edema is leakage and accumulation of interstitial fluid, which may be generalized or localized. Causes include venous insufficiency, cardiac or renal failure, hypoalbuminemia, or medications — assessment includes the pitting sign and identifying the underlying cause.",
        },
    },
    "dyspnea": {
        "aliases": ["dyspnea", "dyspnoea", "ضيق النفس", "ضيق تنفس", "shortness of breath", "difficulty breathing"],
        "ar": {
            "title": "عسر التنفس (Dyspnea)",
            "very_simple": "كلمة طبية تعني ببساطة «ضيق النفس» — الشعور بأن التنفس صعب أو أن النفس ما يكفي.",
            "basic": "عسر التنفس هو الإحساس بصعوبة أو عدم كفاية التنفس. قد يكون بسبب الجهد أو القلق أو فقر الدم أو مشاكل القلب أو الرئة، ويقيَّم حسب الظهور المفاجئ أو التدريجي.",
            "advanced": "عسر التنفس (Dyspnea) إحساس شخصي بضيق أو صعوبة في التنفس، وينشأ عن خلل في العلاقة بين المطالب التنفسية والقدرة — وأسبابه قلبية، رئوية، دموية، أو نفسية — ويتطلب تقييم ظهوره وعوامله المصاحبة.",
        },
        "en": {
            "title": "Dyspnea",
            "very_simple": "A medical word that simply means \"shortness of breath\" — feeling that breathing is hard or that you can't get enough air.",
            "basic": "Dyspnea is the feeling that breathing is difficult or insufficient. It may be due to exertion, anxiety, anemia, or heart or lung problems, and is assessed by whether it came on suddenly or gradually.",
            "advanced": "Dyspnea is a subjective sensation of breathlessness arising from a mismatch between respiratory demand and capacity — causes are cardiac, pulmonary, hematologic, or psychogenic — and evaluation considers onset and associated factors.",
        },
    },
    "hypertension": {
        "aliases": ["hypertension", "high blood pressure", "ضغط", "الضغط", "ارتفاع ضغط الدم"],
        "ar": {
            "title": "ارتفاع ضغط الدم",
            "very_simple": "هي أن «قوة ضخ الدم» على جدران الأوعية أعلى من الطبيعي لفترة طويلة، ولهذا يسمى القاتل الصامت لأنه غالباً بدون أعراض.",
            "basic": "ارتفاع ضغط الدم حالة يظل فيها ضغط الدم مرتفعاً مع مرور الوقت، ويزيد خطر أمراض القلب والكلى والجلطات. يكتشف بالقياس المنتظم ويُدار بالتغذية والحركة والأدوية عند الحاجة.",
            "advanced": "ارتفاع ضغط الدم (Hypertension) ارتفاع مستمر في ضغط الدم الانقباضي أو الانبساطي فوق الحدود المعتمدة، وهو عامل خطر رئيسي لأمراض القلب والأوعية والكلية — ويصنف ويُدار حسب المستوى والمخاطر القلبية الكلية.",
        },
        "en": {
            "title": "High blood pressure",
            "very_simple": "It means the \"pumping force\" of your blood on the vessel walls is higher than normal over time, which is why it's called the silent killer — it usually has no symptoms.",
            "basic": "High blood pressure is a condition where blood pressure stays high over time, raising the risk of heart, kidney, and stroke problems. It is found by regular measurement and managed with diet, activity, and medication when needed.",
            "advanced": "Hypertension is a persistent elevation of systolic or diastolic blood pressure above accepted thresholds, a major risk factor for cardiovascular and renal disease — staged and managed according to level and overall cardiovascular risk.",
        },
    },
}

# ---------------------------------------------------------------------------
# matching helpers
# ---------------------------------------------------------------------------
_AR_REPLACE = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ئ": "ي", "ة": "ه"})


def _norm(s):
    s = (s or "").strip().lower()
    s = re.sub(r"[\u064B-\u0652\u0640]", "", s)  # diacritics
    s = re.sub(r"[^\w\s\u0600-\u06FF]", " ", s)  # punctuation
    s = s.translate(_AR_REPLACE)
    return re.sub(r"\s+", " ", s).strip()


_QUESTION_PREFIXES = [
    "وش معنى", "ش معنى", "معنى", "ما معنى", "ما هو", "ما هي", "شنو معنى", "وش هي",
    "what does", "what is", "what's", "what are", "meaning of", "what means", "explain",
    "وش يعني", "ش يعني", "يعني ايش", "ايش معنى", "تفسير",
]


def _strip_question(q):
    for pre in _QUESTION_PREFIXES:
        p = _norm(pre)
        if q.startswith(p):
            rest = q[len(p):].strip()
            if rest:
                return rest
    return None


def search_health(query, lang="ar"):
    """Match a free-text query to a knowledge base entry (in the requested language)."""
    q = _norm(query)
    if not q:
        return None
    candidates = []
    stripped = _strip_question(q)
    if stripped:
        candidates.append(stripped)
    candidates.append(q)
    # 1) exact alias match
    for c in candidates:
        if not c:
            continue
        for e in SEARCH_KB.values():
            for al in e["aliases"]:
                if _norm(al) == c:
                    return _entry(e, lang)
    # 2) contains match, prefer longest alias
    best = None
    best_len = -1
    for c in candidates:
        for e in SEARCH_KB.values():
            for al in e["aliases"]:
                a = _norm(al)
                if len(a) < 3:
                    continue
                if a in c or c in a:
                    if len(a) > best_len:
                        best = e
                        best_len = len(a)
    return _entry(best, lang) if best else None


def _entry(e, lang):
    ar = lang == "ar"
    lang_data = e["ar"] if ar else e["en"]
    cat = e["category"]
    causes_label = (e.get("causes_label") or {}).get("ar" if ar else "en",
                                                      "الأسباب الشائعة" if ar else "Common causes")
    return {
        "key": None,
        "emoji": e["emoji"],
        "category": cat,
        "title": lang_data["title"],
        "what": lang_data["what"],
        "causes": lang_data["causes"],
        "worry": lang_data["worry"],
        "doctor": lang_data["doctor"],
        "causes_label": causes_label,
    }


def explain_term(term, lang="ar"):
    """Find a glossary explanation for a term. Returns None if not covered."""
    t = _norm(term)
    if not t:
        return None
    for e in GLOSSARY.values():
        for al in e["aliases"]:
            a = _norm(al)
            if a and (a == t or a in t or t in a):
                ar = lang == "ar"
                return {
                    "term": term,
                    "title": e["ar"]["title"] if ar else e["en"]["title"],
                    "levels": {
                        "very_simple": e["ar"]["very_simple"] if ar else e["en"]["very_simple"],
                        "basic": e["ar"]["basic"] if ar else e["en"]["basic"],
                        "advanced": e["ar"]["advanced"] if ar else e["en"]["advanced"],
                    },
                }
    return None


def suggestion_terms(lang="ar"):
    """Popular search suggestions shown when focusing the search box."""
    if lang == "ar":
        return [
            ("🤕", "الدوخة"), ("🤒", "الحمى"), ("👁️", "احمرار العين"),
            ("🩸", "WBC"), ("💊", "الباراسيتامول"), ("🧪", "تحليل CBC"),
        ]
    return [
        ("🤕", "Dizziness"), ("🤒", "Fever"), ("👁️", "Eye redness"),
        ("🩸", "WBC"), ("💊", "Paracetamol"), ("🧪", "CBC test"),
    ]
