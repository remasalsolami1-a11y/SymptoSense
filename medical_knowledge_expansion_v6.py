"""V74 source-diversity and everyday symptom expansion for SymptoSense.

This pack adds common oral/dental, skin, musculoskeletal, menstrual and
other everyday presentations.  Every new condition has at least one direct
patient-information reference from an allow-listed health organization.
"""

EXTRA_SOURCES_V6 = [
    (
        "nidcr", "NIDCR", "National Institute of Dental and Craniofacial Research",
        "https://www.nidcr.nih.gov/", "government", 17,
        "معهد تابع للمعاهد الوطنية للصحة في الولايات المتحدة ومتخصص بصحة الفم والأسنان والوجه والفكين.",
        "A U.S. NIH institute focused on oral, dental, and craniofacial health.",
    ),
    (
        "niams", "NIAMS", "National Institute of Arthritis and Musculoskeletal and Skin Diseases",
        "https://www.niams.nih.gov/", "government", 18,
        "معهد تابع للمعاهد الوطنية للصحة ومتخصص بأمراض المفاصل والعضلات والعظام والجلد.",
        "A U.S. NIH institute focused on arthritis, musculoskeletal, and skin diseases.",
    ),
    (
        "womens-health", "Office on Women's Health", "U.S. Department of Health and Human Services",
        "https://womenshealth.gov/", "government", 19,
        "مكتب صحة المرأة التابع لوزارة الصحة والخدمات الإنسانية الأمريكية ويقدم مواد تثقيفية موثوقة لصحة المرأة.",
        "The U.S. HHS Office on Women's Health, providing trusted women's health education.",
    ),
    (
        "aha", "American Heart Association", "American Heart Association",
        "https://www.heart.org/", "other_trusted_source", 45,
        "منظمة صحية غير ربحية تنشر معلومات تثقيفية وإرشادات مرتبطة بصحة القلب والأوعية الدموية.",
        "A nonprofit health organization publishing cardiovascular education and guidance.",
    ),
    (
        "aad", "American Academy of Dermatology", "American Academy of Dermatology Association",
        "https://www.aad.org/", "other_trusted_source", 46,
        "جهة تخصصية مهنية في طب الجلد تنشر معلومات تثقيفية عن أمراض الجلد والشعر والأظافر.",
        "A dermatology professional organization publishing patient education on skin, hair, and nail conditions.",
    ),
]

EXTRA_SYMPTOMS_V6 = [
    ("tooth-sensitivity", "حساسية أو ألم الأسنان مع البارد أو الحلو", "Tooth sensitivity with cold or sweet foods", "mouth", ["اسناني تتحسس من البارد", "أسناني تتحسس من البارد", "سنّي يوجع مع الحلو", "الم سن مع البارد", "ألم سن مع البارد"], ["tooth sensitivity", "tooth hurts with cold", "sensitive teeth"]),
    ("visible-tooth-cavity", "حفرة أو بقعة واضحة في السن", "Visible tooth cavity or spot", "mouth", ["حفرة بالسن", "تسوس واضح", "بقعة سوداء بالسن", "سن فيه حفرة"], ["tooth cavity", "visible cavity", "dark spot on tooth"]),
    ("teeth-grinding", "صرير أو طحن الأسنان", "Teeth grinding or clenching", "mouth", ["اطحن اسناني بالنوم", "أطحن أسناني بالنوم", "اصك اسناني", "أضغط على أسناني", "صرير الأسنان"], ["teeth grinding", "bruxism", "clenching teeth"]),
    ("morning-jaw-tightness", "شد أو تعب الفك عند الاستيقاظ", "Morning jaw tightness", "mouth", ["فكي مشدود الصباح", "فكي متعب لما اصحى", "أصحى وفكي يوجع", "شد بالفك الصباح"], ["morning jaw tightness", "jaw sore on waking"]),
    ("burning-mouth", "حرقة مستمرة في الفم أو اللسان", "Burning mouth or tongue", "mouth", ["لساني يحرق", "حرقان اللسان", "فمي يحرق", "حرقة بالفم بدون جرح"], ["burning mouth", "burning tongue", "mouth burning"]),
    ("metallic-taste", "طعم معدني أو غريب مستمر", "Persistent metallic taste", "mouth", ["طعم معدني بفمي", "احس طعم حديد", "أحس طعم حديد", "طعم غريب مستمر"], ["metallic taste", "persistent strange taste"]),
    ("meal-triggered-jaw-swelling", "تورم تحت الفك أو قرب الأذن مع الأكل", "Jaw or cheek swelling around meals", "mouth", ["انتفاخ تحت الفك وقت الاكل", "انتفاخ تحت الفك وقت الأكل", "خدي ينتفخ مع الاكل", "تورم تحت الاذن مع الأكل"], ["swelling under jaw with meals", "cheek swelling when eating", "salivary gland swelling"]),
    ("prickly-heat-rash", "طفح حاك أو لاذع مع الحر", "Prickly itchy rash in heat", "skin", ["طفح من الحر", "حبوب من الحر", "حمو النيل", "جلدي يحك مع الحر"], ["heat rash", "prickly heat", "rash from heat"]),
    ("sunburned-skin", "احمرار وألم الجلد بعد الشمس", "Red painful skin after sun exposure", "skin", ["انحرقت من الشمس", "جلدي محروق من الشمس", "احمرار بعد الشمس", "حرق شمس"], ["sunburn", "skin burned by sun", "red skin after sun"]),
    ("sunburn-blisters", "فقاعات أو بثور بعد حرق الشمس", "Blisters after sunburn", "skin", ["فقاعات بعد الشمس", "حرق الشمس فيه فقاعات", "بثور بعد الشمس"], ["sunburn blisters", "blisters after sunburn"]),
    ("insect-bite-lump", "حبة أو تورم بعد قرصة حشرة", "Lump or swelling after an insect bite", "skin", ["قرصة حشرة", "لدغة حشرة", "حبة بعد قرصة", "انتفاخ بعد لدغة"], ["insect bite", "bug bite", "swelling after insect bite"]),
    ("painful-pus-lump", "كتلة جلدية مؤلمة فيها صديد", "Painful pus-filled skin lump", "skin", ["دمل", "حبة كبيرة فيها صديد", "كتلة مؤلمة فيها صديد", "خراج صغير بالجلد"], ["boil", "painful pus lump", "skin abscess lump"]),
    ("cold-itchy-toes", "حكة أو تورم أصابع بعد البرد", "Itchy swollen toes after cold exposure", "skin", ["اصابع رجلي تحك بعد البرد", "أصابع رجلي تحك بعد البرد", "تورم الاصابع من البرد", "حكة الأصابع مع البرد"], ["itchy toes after cold", "chilblains", "swollen toes after cold"]),
    ("postnasal-drip", "نزول مخاط خلف الأنف إلى الحلق", "Post-nasal drip", "respiratory", ["مخاط ينزل للحلق", "بلغم من الانف للحلق", "أحس مخاط خلف الأنف", "تنقيط خلف الانف"], ["post nasal drip", "mucus down throat", "catarrh"]),
    ("throat-mucus", "إحساس بمخاط أو بلغم عالق في الحلق", "Mucus feeling in the throat", "respiratory", ["مخاط عالق بالحلق", "بلغم عالق بالحلق", "احس شي ينزل من الانف للحلق"], ["mucus in throat", "phlegm stuck in throat"]),
    ("excessive-sweating", "تعرق زائد عن المعتاد", "Excessive sweating", "general", ["اتعرق كثير بدون سبب", "أتعرق كثير بدون سبب", "عرق كثير", "تعرق مفرط", "يدي تعرق كثير"], ["excessive sweating", "hyperhidrosis", "sweat too much"]),
    ("shoulder-stiffness", "تيبس واضح في الكتف", "Shoulder stiffness", "musculoskeletal", ["كتفي متيبس", "الكتف ما يتحرك كويس", "تيبس الكتف"], ["shoulder stiffness", "stiff shoulder"]),
    ("limited-shoulder-motion", "صعوبة تحريك الكتف في عدة اتجاهات", "Limited shoulder movement", "musculoskeletal", ["ما اقدر ارفع يدي بسبب الكتف", "ما أقدر أرفع يدي بسبب الكتف", "حركة كتفي محدودة"], ["limited shoulder movement", "cannot raise arm because of shoulder"]),
    ("repetitive-use-pain", "ألم يزيد مع الحركة المتكررة", "Pain linked to repetitive use", "musculoskeletal", ["يدي توجع من استخدام الماوس", "الم من الكتابة المتكررة", "ألم من الحركة المتكررة", "وجع من استخدام الكمبيوتر"], ["pain from repetitive use", "repetitive strain pain", "mouse use pain"]),
    ("overuse-tingling", "تنميل أو وخز مع الاستخدام المتكرر", "Tingling with repetitive use", "neurological", ["تنميل مع استخدام الماوس", "وخز بعد الكتابة", "يدي تنمل من الكمبيوتر"], ["tingling with repetitive use", "pins and needles from overuse"]),
    ("shin-exercise-pain", "ألم قصبة الساق مع أو بعد الجري", "Shin pain with or after exercise", "musculoskeletal", ["الم قصبة الساق بعد الجري", "ألم قصبة الساق بعد الجري", "وجع عظمة الساق مع الركض", "shin pain after running"], ["shin pain after running", "shin splints", "shin pain exercise"]),
    ("missed-period", "تأخر أو غياب الدورة", "Missed or late period", "general", ["الدورة متأخرة", "الدوره متاخره", "ما نزلت الدورة", "تأخرت علي الدورة", "غياب الدورة"], ["missed period", "late period", "period is late"]),
    ("vaginal-dryness", "جفاف مهبلي", "Vaginal dryness", "general", ["جفاف مهبلي", "جفاف بالمهبل", "المنطقة جافة", "vaginal dryness"], ["vaginal dryness", "vaginal feels dry"]),
]

EXTRA_DISEASES_V6 = [
    {
        "slug":"tooth-decay-pattern","name_ar":"نمط تسوس الأسنان","name_en":"Tooth decay pattern","category":"mouth","severity":"mild",
        "symptoms":{"tooth-sensitivity":0.92,"visible-tooth-cavity":0.88,"tooth-pain":0.72,"bad-breath":0.25},
        "description_ar":"قد يبدأ تسوس الأسنان دون أعراض، ثم يسبب حساسية أو ألمًا أو حفرة/بقعة في السن مع تطوره. لا يمكن تأكيده من الأعراض فقط.",
        "description_en":"Tooth decay may begin without symptoms, then cause sensitivity, pain, or a visible cavity/spot as it progresses. Symptoms alone cannot confirm it.",
        "risk_ar":"تورم الوجه أو الفك، حرارة، صعوبة بلع أو تنفس، أو ألم شديد متفاقم يحتاج تقييمًا سريعًا.","risk_en":"Facial/jaw swelling, fever, swallowing or breathing difficulty, or rapidly worsening severe pain needs prompt assessment.",
        "causes_ar":"تراكم البلاك والأحماض التي تضر مينا الأسنان مع عوامل غذائية وصحية أخرى.","causes_en":"Plaque and acids can damage tooth enamel, with diet and other oral-health factors contributing.",
        "red_ar":"تورم سريع أو صعوبة التنفس/البلع مع أعراض سنية تستدعي رعاية عاجلة.","red_en":"Rapid swelling or breathing/swallowing difficulty with dental symptoms needs urgent care.",
        "next_ar":"احجز فحص أسنان إذا استمرت الحساسية أو الألم أو لاحظت حفرة؛ الوقاية تشمل تنظيف الأسنان بالفلورايد وتقليل السكريات المتكررة.","next_en":"Arrange a dental check if sensitivity/pain persists or you notice a cavity; prevention includes fluoride brushing and limiting frequent sugars.",
        "sources":[("nidcr","تسوس الأسنان — NIDCR","Tooth Decay — NIDCR","https://www.nidcr.nih.gov/health-info/tooth-decay")],
    },
    {
        "slug":"bruxism-pattern","name_ar":"نمط صرير أو ضغط الأسنان","name_en":"Bruxism pattern","category":"mouth","severity":"mild",
        "symptoms":{"teeth-grinding":0.98,"morning-jaw-tightness":0.82,"jaw-pain":0.62,"headache":0.35},
        "description_ar":"صرير أو ضغط الأسنان قد يحدث أثناء النوم أو اليقظة وقد يرتبط بتعب الفك أو ألم الرأس أو تآكل الأسنان.","description_en":"Teeth grinding or clenching can occur during sleep or while awake and may be linked to jaw fatigue, headaches, or tooth wear.",
        "risk_ar":"ألم شديد، كسر سن، تورم أو صعوبة فتح الفم يحتاج تقييمًا لدى طبيب أسنان أو طبيب.","risk_en":"Severe pain, a fractured tooth, swelling, or difficulty opening the mouth needs dental or medical assessment.",
        "causes_ar":"قد يرتبط بالتوتر أو النوم أو بعض الأدوية وعوامل الفم والفك، وقد لا يكون له سبب واحد واضح.","causes_en":"Stress, sleep factors, some medicines, and oral/jaw factors can contribute; there may not be one clear cause.",
        "red_ar":"تورم الوجه أو ألم شديد متفاقم أو صعوبة البلع/التنفس تستدعي تقييمًا سريعًا.","red_en":"Facial swelling, rapidly worsening severe pain, or swallowing/breathing difficulty needs prompt assessment.",
        "next_ar":"إذا كان الصرير متكررًا أو يسبب ألمًا صباحيًا أو تآكلًا بالأسنان، راجع طبيب الأسنان للتقييم وخيارات الحماية.","next_en":"If grinding is frequent or causes morning pain or tooth wear, see a dentist for assessment and protective options.",
        "sources":[("nidcr","صرير الأسنان — NIDCR","Bruxism — NIDCR","https://www.nidcr.nih.gov/health-info/bruxism")],
    },
    {
        "slug":"burning-mouth-syndrome-pattern","name_ar":"نمط حرقة الفم","name_en":"Burning mouth syndrome pattern","category":"mouth","severity":"mild",
        "symptoms":{"burning-mouth":0.98,"altered-taste":0.58,"metallic-taste":0.48,"dry-mouth":0.42},
        "description_ar":"حرقة الفم أو اللسان المستمرة قد ترتبط بمتلازمة حرقة الفم، لكن توجد أسباب أخرى مثل جفاف الفم أو العدوى أو نقص بعض العناصر أو الأدوية.","description_en":"Persistent burning of the mouth or tongue can fit burning mouth syndrome, but dry mouth, infection, deficiencies, medicines and other causes can mimic it.",
        "risk_ar":"قرحة أو بقعة لا تلتئم، صعوبة بلع، تورم، فقد وزن غير مفسر أو ألم متفاقم يحتاج تقييمًا.","risk_en":"A non-healing ulcer/patch, swallowing difficulty, swelling, unexplained weight loss, or worsening pain needs assessment.",
        "causes_ar":"قد يرتبط باضطراب أعصاب الألم والطعم أو بأسباب فموية وطبية أخرى يجب استبعادها.","causes_en":"It may involve altered pain/taste nerves or other oral and medical causes that need evaluation.",
        "red_ar":"تورم سريع أو صعوبة التنفس/البلع تستدعي رعاية عاجلة.","red_en":"Rapid swelling or breathing/swallowing difficulty needs urgent care.",
        "next_ar":"راجع طبيب الأسنان أو الطبيب إذا استمرت الحرقة، خاصة دون سبب واضح، لتقييم الفم والأدوية والعوامل الأخرى.","next_en":"See a dentist or clinician if burning persists, especially without a clear trigger, to review oral, medicine, and other factors.",
        "sources":[("nidcr","حرقة الفم — NIDCR","Burning Mouth — NIDCR","https://www.nidcr.nih.gov/health-info/burning-mouth")],
    },
    {
        "slug":"salivary-gland-obstruction-pattern","name_ar":"نمط انسداد أو اضطراب الغدة اللعابية","name_en":"Salivary gland obstruction pattern","category":"mouth","severity":"moderate",
        "symptoms":{"meal-triggered-jaw-swelling":0.98,"dry-mouth":0.35,"mouth-pain":0.48},
        "description_ar":"تورم أو ألم تحت الفك أو قرب الأذن يزداد مع الأكل قد يرتبط بانسداد قناة لعابية أو اضطراب بالغدة، لكن يحتاج فحصًا للتأكد.","description_en":"Swelling or pain under the jaw or near the ear that worsens with meals can fit salivary-duct obstruction or another gland disorder and needs examination to confirm.",
        "risk_ar":"حمى، احمرار شديد، قيح، تورم سريع أو صعوبة البلع/التنفس يحتاج تقييمًا عاجلًا.","risk_en":"Fever, marked redness, pus, rapid swelling, or swallowing/breathing difficulty needs urgent assessment.",
        "causes_ar":"حصوة في قناة اللعاب، التهاب أو اضطرابات أخرى في الغدد اللعابية.","causes_en":"A salivary duct stone, infection, or other salivary-gland disorders.",
        "red_ar":"تورم سريع بالرقبة أو الفم مع صعوبة البلع أو التنفس يستدعي الطوارئ.","red_en":"Rapid neck/mouth swelling with swallowing or breathing difficulty is an emergency.",
        "next_ar":"إذا تكرر التورم مع الوجبات أو استمر، راجع طبيب الأسنان أو الأنف والأذن أو الطبيب للتقييم.","next_en":"If swelling recurs with meals or persists, seek dental, ENT, or medical assessment.",
        "sources":[("nidcr","اللعاب واضطرابات الغدد اللعابية — NIDCR","Saliva and Salivary Gland Disorders — NIDCR","https://www.nidcr.nih.gov/health-info/saliva-salivary-gland-disorders")],
    },
    {
        "slug":"heat-rash-pattern","name_ar":"الطفح الحراري","name_en":"Heat rash pattern","category":"skin","severity":"mild",
        "symptoms":{"prickly-heat-rash":0.98,"itching":0.55,"skin-rash":0.52},
        "description_ar":"الطفح الحراري يسبب حبوبًا صغيرة مع حكة أو إحساس لاذع بعد التعرض للحر والتعرق، وغالبًا يتحسن مع تبريد الجلد.","description_en":"Heat rash can cause small itchy or prickly bumps after heat and sweating and often improves when the skin is kept cool.",
        "risk_ar":"حمى، ألم شديد، انتشار سريع، قيح أو تدهور عام يحتاج تقييمًا طبيًا.","risk_en":"Fever, severe pain, rapid spread, pus, or systemic illness needs medical assessment.",
        "causes_ar":"انسداد قنوات العرق مع الحرارة والتعرق.","causes_en":"Blocked sweat ducts during heat and sweating.",
        "red_ar":"علامات عدوى أو تدهور عام تستدعي تقييمًا طبيًا سريعًا.","red_en":"Signs of infection or systemic deterioration need prompt assessment.",
        "next_ar":"حافظ على برودة وجفاف الجلد وارتدِ ملابس خفيفة؛ اطلب المشورة إذا لم يتحسن أو ظهرت علامات عدوى.","next_en":"Keep skin cool and dry and wear light clothing; seek advice if it does not improve or infection signs appear.",
        "sources":[("nhs","الطفح الحراري — NHS","Heat rash — NHS","https://www.nhs.uk/conditions/heat-rash-prickly-heat/")],
    },
    {
        "slug":"sunburn-pattern","name_ar":"حرق الشمس","name_en":"Sunburn pattern","category":"skin","severity":"mild",
        "symptoms":{"sunburned-skin":0.98,"sunburn-blisters":0.58,"skin-rash":0.30},
        "description_ar":"حرق الشمس يسبب جلدًا أحمر أو مؤلمًا بعد التعرض للأشعة فوق البنفسجية، وقد تظهر فقاعات في الحالات الأشد.","description_en":"Sunburn causes red or painful skin after UV exposure and can blister when more severe.",
        "risk_ar":"فقاعات واسعة، تورم شديد، دوخة، غثيان، صداع شديد أو علامات ضربة حرارة تحتاج تقييمًا سريعًا.","risk_en":"Extensive blistering, severe swelling, dizziness, nausea, severe headache, or heat-illness signs need prompt assessment.",
        "causes_ar":"التعرض الزائد للأشعة فوق البنفسجية من الشمس أو مصادر صناعية.","causes_en":"Excess ultraviolet exposure from the sun or artificial sources.",
        "red_ar":"ارتباك، إغماء أو أعراض ضربة حرارة مع التعرض للشمس تستدعي رعاية عاجلة.","red_en":"Confusion, fainting, or heat-stroke symptoms with sun exposure need urgent care.",
        "next_ar":"ابتعد عن الشمس، برّد الجلد بلطف واشرب السوائل، وتجنب فرقعة الفقاعات؛ اطلب المساعدة إذا كان الحرق شديدًا.","next_en":"Get out of the sun, cool the skin gently, hydrate, and do not burst blisters; seek help for severe burns.",
        "sources":[("nhs","حرق الشمس — NHS","Sunburn — NHS","https://www.nhs.uk/conditions/sunburn/")],
    },
    {
        "slug":"insect-bite-sting-pattern","name_ar":"قرصة أو لسعة حشرة","name_en":"Insect bite or sting pattern","category":"skin","severity":"mild",
        "symptoms":{"insect-bite-lump":0.98,"itching":0.65,"swelling":0.38},
        "description_ar":"قرصات ولسعات الحشرات غالبًا تسبب حبة أو تورمًا موضعيًا مع حكة أو ألم بسيط، لكنها قد تسبب حساسية أو عدوى أحيانًا.","description_en":"Insect bites and stings commonly cause a local itchy or mildly painful lump, but allergy or infection can occasionally occur.",
        "risk_ar":"صعوبة تنفس، تورم اللسان/الحلق، دوخة شديدة أو انتشار تورم سريع يستدعي الطوارئ.","risk_en":"Breathing difficulty, tongue/throat swelling, severe dizziness, or rapidly spreading swelling is an emergency.",
        "causes_ar":"تفاعل الجلد مع لدغة أو لسعة حشرة.","causes_en":"A skin reaction to an insect bite or sting.",
        "red_ar":"علامات الحساسية الشديدة مثل صعوبة التنفس أو تورم الفم/الحلق تستدعي الطوارئ فورًا.","red_en":"Severe allergy signs such as breathing difficulty or mouth/throat swelling need emergency help now.",
        "next_ar":"نظف المنطقة وتجنب الحك، واطلب نصيحة إذا زاد الاحمرار أو الألم أو ظهرت علامات حساسية أو عدوى.","next_en":"Clean the area and avoid scratching; seek advice if redness/pain increases or allergy/infection signs appear.",
        "sources":[("nhs","قرصات ولسعات الحشرات — NHS","Insect bites and stings — NHS","https://www.nhs.uk/conditions/insect-bites-and-stings/")],
    },
    {
        "slug":"boil-skin-abscess-pattern","name_ar":"دمل أو خراج جلدي سطحي","name_en":"Boil or superficial skin abscess pattern","category":"skin","severity":"moderate",
        "symptoms":{"painful-pus-lump":0.98,"skin-warmth":0.42,"fever":0.22},
        "description_ar":"الدمل كتلة جلدية مؤلمة مملوءة بالقيح بسبب عدوى حول بصيلة الشعر، وقد تكبر أو تنتشر أحيانًا.","description_en":"A boil is a painful pus-filled skin lump caused by infection around a hair follicle and may sometimes enlarge or spread.",
        "risk_ar":"حمى، انتشار احمرار سريع، ألم شديد، دمل بالوجه، أو ضعف مناعة يحتاج تقييمًا طبيًا سريعًا.","risk_en":"Fever, rapidly spreading redness, severe pain, a facial boil, or immunocompromise needs prompt assessment.",
        "causes_ar":"عدوى بكتيرية في الجلد أو بصيلة الشعر.","causes_en":"A bacterial infection of the skin or hair follicle.",
        "red_ar":"تدهور عام أو انتشار سريع للالتهاب مع حرارة يحتاج رعاية عاجلة.","red_en":"Systemic deterioration or rapidly spreading inflammation with fever needs urgent care.",
        "next_ar":"لا تعصر الدمل؛ يمكن استخدام كمادات دافئة بلطف، وراجع مختصًا إذا كان كبيرًا أو مؤلمًا جدًا أو لم يتحسن.","next_en":"Do not squeeze a boil; gentle warm compresses may help, and seek care if large, very painful, or not improving.",
        "sources":[("nhs","الدمامل — NHS","Boils — NHS","https://www.nhs.uk/conditions/boils/")],
    },
    {
        "slug":"chilblains-pattern","name_ar":"تورمات البرد (الشرث)","name_en":"Chilblains pattern","category":"skin","severity":"mild",
        "symptoms":{"cold-itchy-toes":0.98,"itching":0.55,"swelling":0.45},
        "description_ar":"قد تظهر بقع حاكة أو مؤلمة ومتورمة على أصابع اليدين أو القدمين بعد التعرض للبرد، وغالبًا تتحسن خلال أسابيع.","description_en":"Itchy, painful, swollen patches can appear on fingers or toes after cold exposure and often improve within weeks.",
        "risk_ar":"تقرح الجلد، صديد، حرارة أو استمرار الأعراض مع عوامل خطورة للدورة الدموية يحتاج تقييمًا.","risk_en":"Skin breakdown, pus, fever, or persistent symptoms with circulation risk factors needs assessment.",
        "causes_ar":"استجابة الأوعية الدموية الصغيرة للتغير من البرد إلى الدفء.","causes_en":"A small-vessel response to changing from cold to warmth.",
        "red_ar":"اسوداد الأصابع أو ألم شديد مستمر يحتاج تقييمًا عاجلًا للدورة الدموية.","red_en":"Blackening of digits or severe persistent pain needs urgent circulation assessment.",
        "next_ar":"حافظ على دفء الجسم تدريجيًا وتجنب التسخين المباشر الشديد؛ راجع الطبيب إذا لم تتحسن أو تكررت كثيرًا.","next_en":"Warm up gradually and avoid intense direct heat; seek review if they do not improve or recur frequently.",
        "sources":[("nhs","تورمات البرد — NHS","Chilblains — NHS","https://www.nhs.uk/conditions/chilblains/")],
    },
    {
        "slug":"catarrh-postnasal-pattern","name_ar":"نمط احتقان ومخاط خلف الأنف","name_en":"Catarrh / post-nasal mucus pattern","category":"respiratory","severity":"mild",
        "symptoms":{"postnasal-drip":0.92,"throat-mucus":0.82,"nasal-congestion":0.54,"cough":0.30},
        "description_ar":"تجمع المخاط في الأنف والجيوب أو نزوله خلف الحلق قد يسبب إحساسًا بانسداد الأنف أو بلغم عالق أو تنحنح متكرر.","description_en":"Mucus in the nose/sinuses or dripping down the throat can cause congestion, a mucus sensation, or frequent throat clearing.",
        "risk_ar":"ضيق تنفس شديد، تورم الوجه مع حرارة شديدة، أو تدهور سريع يحتاج تقييمًا عاجلًا.","risk_en":"Severe breathlessness, facial swelling with high fever, or rapid deterioration needs urgent assessment.",
        "causes_ar":"نزلات البرد، الحساسية أو تهيج الأنف والجيوب من الأسباب الشائعة.","causes_en":"Colds, allergy, or nasal/sinus irritation are common contexts.",
        "red_ar":"صعوبة التنفس الشديدة أو تورم الوجه السريع تستدعي رعاية عاجلة.","red_en":"Severe breathing difficulty or rapidly progressive facial swelling needs urgent care.",
        "next_ar":"السوائل وغسل الأنف بالمحلول الملحي قد يساعدان؛ راجع مختصًا إذا استمرت الأعراض لأسابيع أو كانت شديدة.","next_en":"Fluids and saline nasal rinsing may help; seek review if symptoms persist for weeks or are severe.",
        "sources":[("nhs","الاحتقان والمخاط (Catarrh) — NHS","Catarrh — NHS","https://www.nhs.uk/conditions/catarrh/")],
    },
    {
        "slug":"hyperhidrosis-pattern","name_ar":"نمط التعرق المفرط","name_en":"Hyperhidrosis pattern","category":"general","severity":"mild",
        "symptoms":{"excessive-sweating":0.98,"night-sweats":0.28},
        "description_ar":"التعرق المفرط يعني تعرقًا أكثر مما يحتاجه الجسم للتبريد وقد يصيب الإبطين أو اليدين أو القدمين أو مناطق أخرى.","description_en":"Hyperhidrosis means sweating more than the body needs for cooling and can affect the armpits, hands, feet, or other areas.",
        "risk_ar":"تعرق مفاجئ جديد مع ألم صدر أو ضيق تنفس أو إغماء، أو تعرق ليلي مع فقد وزن/حمى مستمرة يحتاج تقييمًا.","risk_en":"New sudden sweating with chest pain, breathlessness or fainting, or night sweats with persistent fever/weight loss needs assessment.",
        "causes_ar":"قد يكون أوليًا دون سبب مرضي واضح أو ثانويًا لدواء أو حالة صحية.","causes_en":"It can be primary without a clear medical cause or secondary to a medicine or health condition.",
        "red_ar":"التعرق مع ألم صدر أو ضيق نفس أو إغماء يستدعي تقييمًا عاجلًا.","red_en":"Sweating with chest pain, breathlessness, or fainting needs urgent assessment.",
        "next_ar":"راجع الطبيب إذا بدأ فجأة أو يزعج الحياة اليومية أو يحدث أثناء النوم دون سبب واضح.","next_en":"Seek medical review if it starts suddenly, disrupts daily life, or occurs at night without a clear reason.",
        "sources":[("nhs","التعرق المفرط — NHS","Excessive sweating (hyperhidrosis) — NHS","https://www.nhs.uk/conditions/excessive-sweating-hyperhidrosis/")],
    },
    {
        "slug":"frozen-shoulder-pattern","name_ar":"نمط الكتف المتجمد","name_en":"Frozen shoulder pattern","category":"musculoskeletal","severity":"moderate",
        "symptoms":{"shoulder-stiffness":0.94,"limited-shoulder-motion":0.90,"shoulder-pain":0.72},
        "description_ar":"الكتف المتجمد يسبب ألمًا وتيبسًا متزايدين مع محدودية حركة الكتف، وغالبًا يتطور تدريجيًا.","description_en":"Frozen shoulder causes increasing pain and stiffness with restricted shoulder movement, usually developing gradually.",
        "risk_ar":"إصابة حديثة قوية، تشوه، فقد إحساس/قوة مفاجئ أو ألم شديد مع أعراض صدرية يحتاج تقييمًا سريعًا.","risk_en":"Major recent injury, deformity, sudden loss of sensation/strength, or shoulder pain with chest symptoms needs prompt assessment.",
        "causes_ar":"يحدث عندما تصبح محفظة مفصل الكتف ملتهبة ومشدودة، وقد يظهر بعد قلة الحركة أو دون سبب واضح.","causes_en":"It occurs when the shoulder capsule becomes inflamed and tight and can follow immobility or arise without a clear trigger.",
        "red_ar":"ألم الكتف مع ألم صدر أو ضيق نفس، أو ضعف مفاجئ بالذراع يحتاج تقييمًا عاجلًا.","red_en":"Shoulder pain with chest pain/breathlessness or sudden arm weakness needs urgent assessment.",
        "next_ar":"راجع الطبيب أو العلاج الطبيعي إذا استمر التيبس أو صعّب الحركة؛ الحركة المناسبة تدريجيًا جزء مهم من العلاج.","next_en":"See a clinician or physiotherapist if stiffness persists or limits movement; appropriate gradual movement is an important part of care.",
        "sources":[("nhs","الكتف المتجمد — NHS","Frozen shoulder — NHS","https://www.nhs.uk/conditions/frozen-shoulder/")],
    },
    {
        "slug":"repetitive-strain-injury-pattern","name_ar":"إجهاد الحركة المتكررة","name_en":"Repetitive strain injury pattern","category":"musculoskeletal","severity":"mild",
        "symptoms":{"repetitive-use-pain":0.96,"overuse-tingling":0.58,"wrist-pain":0.48,"hand-numbness":0.32},
        "description_ar":"الألم أو التيبس أو الوخز المرتبط بحركة متكررة في العمل أو الدراسة قد يتوافق مع إصابة إجهاد متكرر، لكن توجد أسباب أخرى للألم والتنميل.","description_en":"Pain, stiffness, or tingling linked to repetitive work/study movements can fit repetitive strain injury, though pain and numbness have other causes.",
        "risk_ar":"ضعف مفاجئ، فقد إحساس واضح، تورم شديد أو إصابة قوية يحتاج تقييمًا سريعًا.","risk_en":"Sudden weakness, marked sensory loss, severe swelling, or major injury needs prompt assessment.",
        "causes_ar":"تكرار الحركة، وضعية غير مريحة أو حمل متكرر على العضلات والأوتار.","causes_en":"Repeated movement, awkward posture, or repeated load on muscles and tendons.",
        "red_ar":"ضعف متزايد أو فقد إحساس مستمر يستدعي تقييمًا طبيًا.","red_en":"Progressive weakness or persistent loss of sensation needs medical assessment.",
        "next_ar":"قلل الحركة المحفزة مؤقتًا وحسّن الوضعية وفترات الراحة، وراجع مختصًا إذا استمر الألم أو التنميل.","next_en":"Temporarily reduce the trigger, improve ergonomics and breaks, and seek review if pain or tingling persists.",
        "sources":[("nhs","إصابة الإجهاد المتكرر — NHS","Repetitive strain injury (RSI) — NHS","https://www.nhs.uk/conditions/repetitive-strain-injury-rsi/")],
    },
    {
        "slug":"shin-splints-pattern","name_ar":"نمط ألم قصبة الساق مع الرياضة","name_en":"Shin splints pattern","category":"musculoskeletal","severity":"mild",
        "symptoms":{"shin-exercise-pain":0.98,"pain-after-activity":0.55},
        "description_ar":"ألم مقدمة الساق أو جانب القصبة بعد الجري أو زيادة التمرين قد يتوافق مع shin splints، خاصة بعد تغير مفاجئ في الحمل الرياضي.","description_en":"Pain along the shin after running or increased training can fit shin splints, especially after a sudden change in exercise load.",
        "risk_ar":"عدم القدرة على تحمل الوزن، تورم شديد، تشوه أو ألم شديد موضّع بعد إصابة يحتاج تقييمًا لاستبعاد كسر.","risk_en":"Inability to bear weight, marked swelling, deformity, or severe focal pain after injury needs assessment for fracture.",
        "causes_ar":"زيادة الحمل الرياضي بسرعة، الجري على أسطح صلبة أو عوامل الحذاء والميكانيكا الحركية.","causes_en":"Rapid training-load increases, hard surfaces, footwear, and movement mechanics can contribute.",
        "red_ar":"ألم شديد بعد إصابة أو عدم القدرة على المشي يحتاج تقييمًا عاجلًا نسبيًا.","red_en":"Severe pain after injury or inability to walk needs prompt assessment.",
        "next_ar":"أوقف النشاط المسبب مؤقتًا وارجع له تدريجيًا بعد التحسن؛ راجع مختصًا إذا استمر الألم أو كان شديدًا.","next_en":"Pause the provoking activity and return gradually after improvement; seek review if pain persists or is severe.",
        "sources":[("nhs","ألم قصبة الساق (Shin splints) — NHS","Shin splints — NHS","https://www.nhs.uk/conditions/shin-splints/")],
    },
    {
        "slug":"missed-late-period-pattern","name_ar":"تأخر أو غياب الدورة","name_en":"Missed or late period pattern","category":"general","severity":"mild",
        "symptoms":{"missed-period":0.98,"irregular-periods":0.62},
        "description_ar":"تأخر الدورة أو غيابها شائع وله أسباب متعددة تشمل الحمل والتوتر وتغير الوزن والرياضة وبعض الحالات الهرمونية.","description_en":"Late or missed periods are common and can have many causes, including pregnancy, stress, weight change, exercise, and hormonal conditions.",
        "risk_ar":"ألم شديد أسفل البطن مع نزيف أو دوخة/إغماء مع احتمال حمل يحتاج تقييمًا عاجلًا.","risk_en":"Severe lower-abdominal pain with bleeding or dizziness/fainting when pregnancy is possible needs urgent assessment.",
        "causes_ar":"الحمل، التوتر، تغير الوزن، التمرين الشديد، موانع الحمل، PCOS، تغيرات الغدة الدرقية وغيرها.","causes_en":"Pregnancy, stress, weight changes, intense exercise, contraception, PCOS, thyroid changes and other causes.",
        "red_ar":"ألم شديد أو إغماء أو نزيف غير معتاد مع احتمال حمل يحتاج رعاية عاجلة.","red_en":"Severe pain, fainting, or unusual bleeding with possible pregnancy needs urgent care.",
        "next_ar":"إذا كان الحمل ممكنًا فاختبار الحمل خطوة أولى مناسبة؛ راجعي الطبيب إذا تكرر الغياب أو ظهرت أعراض أخرى.","next_en":"If pregnancy is possible, a pregnancy test is a reasonable first step; seek review if missed periods recur or other symptoms appear.",
        "sources":[("nhs","تأخر أو غياب الدورة — NHS","Missed or late periods — NHS","https://www.nhs.uk/symptoms/missed-or-late-periods/")],
    },
    {
        "slug":"vaginal-dryness-pattern","name_ar":"نمط الجفاف المهبلي","name_en":"Vaginal dryness pattern","category":"general","severity":"mild",
        "symptoms":{"vaginal-dryness":0.98,"pain-during-sex":0.55,"urinary-urgency":0.22},
        "description_ar":"الجفاف المهبلي قد يسبب انزعاجًا أو حكة أو ألمًا أثناء العلاقة، وقد يرتبط بتغيرات هرمونية أو أدوية أو عوامل أخرى.","description_en":"Vaginal dryness can cause discomfort, itching, or pain during sex and may relate to hormonal changes, medicines, or other factors.",
        "risk_ar":"نزيف غير معتاد، ألم حوض شديد، إفرازات مع حرارة، أو نزيف بعد انقطاع الدورة يحتاج تقييمًا طبيًا.","risk_en":"Unusual bleeding, severe pelvic pain, discharge with fever, or bleeding after menopause needs medical assessment.",
        "causes_ar":"انخفاض الإستروجين حول سن اليأس أو بعد الولادة/الرضاعة، بعض الأدوية، أو تهيج موضعي وعوامل أخرى.","causes_en":"Lower estrogen around menopause or after birth/breastfeeding, some medicines, local irritation, and other factors.",
        "red_ar":"نزيف بعد انقطاع الدورة أو ألم شديد مع حرارة يحتاج تقييمًا سريعًا.","red_en":"Bleeding after menopause or severe pain with fever needs prompt assessment.",
        "next_ar":"تجنب المنتجات المعطرة المهيجة، ويمكن مناقشة المرطبات أو المزلقات المناسبة مع الصيدلي/الطبيب إذا استمر الجفاف.","next_en":"Avoid irritating perfumed products; discuss appropriate moisturizers or lubricants with a pharmacist/clinician if dryness persists.",
        "sources":[("nhs","الجفاف المهبلي — NHS","Vaginal dryness — NHS","https://www.nhs.uk/symptoms/vaginal-dryness/")],
    },

    {
        "slug":"tinnitus-pattern","name_ar":"نمط طنين الأذن","name_en":"Tinnitus pattern","category":"ear","severity":"mild",
        "symptoms":{"tinnitus":0.98,"hearing-loss":0.38,"ear-blocked":0.25},
        "description_ar":"سماع رنين أو أزيز أو صوت دون مصدر خارجي يسمى طنين الأذن. قد يكون مؤقتًا أو مستمرًا وله أسباب متعددة.","description_en":"Hearing ringing, buzzing, or another sound without an external source is called tinnitus. It can be temporary or persistent and has many possible causes.",
        "risk_ar":"طنين نابض مع النبض، فقد سمع مفاجئ، ضعف أو دوار عصبي شديد، أو طنين بعد إصابة رأس يحتاج تقييمًا سريعًا.","risk_en":"Pulsatile tinnitus, sudden hearing loss, severe neurological vertigo/weakness, or tinnitus after head injury needs prompt assessment.",
        "causes_ar":"التعرض للضوضاء، تغيرات السمع، شمع الأذن وبعض الأدوية والحالات الصحية من الأسباب الممكنة.","causes_en":"Noise exposure, hearing changes, earwax, some medicines, and health conditions are possible causes.",
        "red_ar":"فقد السمع المفاجئ أو أعراض عصبية جديدة مع الطنين تحتاج تقييمًا عاجلًا.","red_en":"Sudden hearing loss or new neurological symptoms with tinnitus need urgent assessment.",
        "next_ar":"راجع مختصًا إذا كان الطنين مستمرًا أو يزداد أو يؤثر على النوم والتركيز، خصوصًا إذا كان في أذن واحدة.","next_en":"Seek review if tinnitus persists, worsens, or affects sleep/concentration, especially if one-sided.",
        "sources":[("nidcd","طنين الأذن — NIDCD","Tinnitus — NIDCD","https://www.nidcd.nih.gov/health/tinnitus")],
    },
]

# Add more direct, specialty-specific citations to conditions that already
# existed in the curated knowledge base.  This improves citation density
# without creating duplicate condition rows.
EXISTING_DISEASE_SOURCE_ENRICHMENT_V6 = {
    "dry-mouth-pattern": [
        ("nidcr","جفاف الفم — NIDCR","Dry Mouth — NIDCR","https://www.nidcr.nih.gov/health-info/dry-mouth"),
    ],
    "gum-disease": [
        ("nidcr","أمراض اللثة — NIDCR","Periodontal (Gum) Disease — NIDCR","https://www.nidcr.nih.gov/health-info/gum-disease"),
    ],
    "temporomandibular-disorder": [
        ("nidcr","اضطرابات المفصل الفكي الصدغي — NIDCR","TMD — NIDCR","https://www.nidcr.nih.gov/health-info/tmd"),
    ],
    "fibromyalgia": [
        ("niams","الألم العضلي الليفي — NIAMS","Fibromyalgia — NIAMS","https://www.niams.nih.gov/health-topics/fibromyalgia"),
    ],
    "osteoarthritis": [
        ("niams","الفصال العظمي — NIAMS","Osteoarthritis — NIAMS","https://www.niams.nih.gov/health-topics/osteoarthritis"),
    ],
    "rheumatoid-arthritis": [
        ("niams","التهاب المفاصل الروماتويدي — NIAMS","Rheumatoid Arthritis — NIAMS","https://www.niams.nih.gov/health-topics/rheumatoid-arthritis"),
    ],
    "gout": [
        ("niams","النقرس — NIAMS","Gout — NIAMS","https://www.niams.nih.gov/health-topics/gout"),
    ],
    "endometriosis-pattern": [
        ("womens-health","بطانة الرحم المهاجرة — Office on Women's Health","Endometriosis — Office on Women's Health","https://womenshealth.gov/a-z-topics/endometriosis"),
    ],
    "polycystic-ovary-syndrome-pattern": [
        ("womens-health","متلازمة تكيس المبايض — Office on Women's Health","Polycystic Ovary Syndrome — Office on Women's Health","https://womenshealth.gov/a-z-topics/polycystic-ovary-syndrome"),
    ],
    "syncope-fainting-pattern": [
        ("aha","الإغماء — American Heart Association","Syncope (Fainting) — American Heart Association","https://www.heart.org/en/health-topics/arrhythmia/symptoms-diagnosis--monitoring-of-arrhythmia/syncope-fainting"),
    ],
    "heart-palpitations": [
        ("aha","أعراض اضطراب النظم ومراقبته — American Heart Association","Arrhythmia symptoms and monitoring — American Heart Association","https://www.heart.org/en/health-topics/arrhythmia/symptoms-diagnosis--monitoring-of-arrhythmia"),
    ],
    "acne-vulgaris": [
        ("aad","معلومات أمراض الجلد — AAD","Skin disease information — AAD","https://www.aad.org/public/diseases"),
    ],
    "atopic-eczema": [
        ("aad","معلومات أمراض الجلد — AAD","Skin disease information — AAD","https://www.aad.org/public/diseases"),
    ],
    "common-hair-loss-pattern": [
        ("aad","معلومات أمراض الشعر والجلد — AAD","Hair and skin disease information — AAD","https://www.aad.org/public/diseases"),
    ],
}

EXISTING_DISEASE_SYMPTOM_ENRICHMENT_V6 = {
    "mouth-ulcer-pattern": {"mouth-pain": 0.55},
}
EXTRA_RED_RULES_V6 = []
EXTRA_RED_RULE_DETAILS_V6 = {}
