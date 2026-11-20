"""Curated 2026 knowledge expansion for SymptoSense.

The rows in this module are intentionally separated from the core seed so the
coverage pack can be reviewed, tested, and versioned independently.  Sources
are restricted to public-health/government/guideline organisations already
allowed by the medical-knowledge trust policy.
"""

EXTRA_SOURCES_V2 = [
    (
        "niddk", "NIDDK", "National Institute of Diabetes and Digestive and Kidney Diseases",
        "https://www.niddk.nih.gov/", "government", 13,
        "معهد وطني أمريكي تابع لـ NIH ينشر معلومات مراجعة علميًا عن أمراض الجهاز الهضمي والكلى والمسالك البولية.",
        "A U.S. NIH institute publishing expert-reviewed information on digestive, kidney, and urologic conditions.",
    ),
    (
        "nhlbi", "NHLBI", "National Heart, Lung, and Blood Institute",
        "https://www.nhlbi.nih.gov/", "government", 14,
        "معهد وطني أمريكي تابع لـ NIH مختص بأمراض القلب والرئة والدم.",
        "A U.S. NIH institute focused on heart, lung, and blood conditions.",
    ),
    (
        "ninds", "NINDS", "National Institute of Neurological Disorders and Stroke",
        "https://www.ninds.nih.gov/", "government", 15,
        "معهد وطني أمريكي تابع لـ NIH مختص بالاضطرابات العصبية والسكتة الدماغية.",
        "A U.S. NIH institute focused on neurological disorders and stroke.",
    ),
    (
        "nice", "NICE", "National Institute for Health and Care Excellence",
        "https://www.nice.org.uk/", "clinical_guideline_body", 16,
        "جهة وطنية بريطانية تصدر إرشادات سريرية قائمة على الدليل لتقييم وعلاج الحالات الصحية.",
        "A UK national body publishing evidence-based clinical guidance for health and care.",
    ),
]

EXTRA_SYMPTOMS_V2 = [
    ("cloudy-urine", "بول عكر", "Cloudy urine", "general", ["البول عكر", "بول غائم", "البول غائم"], ["cloudy urine"]),
    ("blood-in-urine", "دم في البول", "Blood in urine", "general", ["دم بالبول", "البول فيه دم", "بول احمر", "بول أحمر"], ["blood in urine", "hematuria", "red urine"]),
    ("flank-pain", "ألم الخاصرة", "Flank pain", "pain", ["الم الخاصرة", "وجع الجنب تحت الضلع", "ألم الجنب تحت الأضلاع"], ["flank pain", "side pain below ribs"]),
    ("reduced-smell", "ضعف حاسة الشم", "Reduced sense of smell", "general", ["ما اشم كويس", "ضعف الشم", "فقدان جزئي للشم"], ["reduced smell", "reduced sense of smell"]),
    ("thick-nasal-discharge", "إفرازات أنفية سميكة", "Thick nasal discharge", "respiratory", ["مخاط اصفر", "مخاط أخضر", "افرازات انف سميكة"], ["thick nasal discharge", "yellow nasal mucus", "green nasal mucus"]),
    ("eye-discharge", "إفرازات من العين", "Eye discharge", "general", ["صديد بالعين", "افرازات العين", "رموشي تلصق"], ["eye discharge", "sticky eyes", "pus from eye"]),
    ("gritty-eyes", "إحساس برمل أو خشونة في العين", "Gritty eyes", "general", ["احس رمل بعيني", "العين تحرق وتخشن"], ["gritty eyes", "gritty feeling in eye"]),
    ("watery-eyes", "دموع زائدة", "Watery eyes", "general", ["عيوني تدمع", "دموع كثيرة"], ["watery eyes", "tearing eyes"]),
    ("straining-stool", "الحزق أثناء التبرز", "Straining to pass stool", "digestive", ["احزق كثير", "صعوبة اخراج البراز", "اتعب وقت التبرز"], ["straining to poop", "straining to pass stool"]),
    ("incomplete-evacuation", "إحساس بعدم إفراغ الأمعاء", "Incomplete bowel emptying", "digestive", ["احس ما خلصت تبرز", "ما تفرغت بالكامل"], ["incomplete bowel movement", "incomplete evacuation"]),
    ("greasy-stools", "براز دهني أو زيتي", "Greasy stools", "digestive", ["براز دهني", "براز زيتي", "البراز يطفو ودهني"], ["greasy stools", "fatty stools"]),
    ("right-upper-abdominal-pain", "ألم أعلى يمين البطن", "Right upper abdominal pain", "pain", ["الم اعلى يمين البطن", "وجع تحت الضلع اليمين"], ["right upper abdominal pain", "pain under right ribs"]),
    ("right-lower-abdominal-pain", "ألم أسفل يمين البطن", "Right lower abdominal pain", "pain", ["الم اسفل يمين البطن", "وجع الجهة اليمنى اسفل البطن"], ["right lower abdominal pain", "right lower quadrant pain"]),
    ("left-lower-abdominal-pain", "ألم أسفل يسار البطن", "Left lower abdominal pain", "pain", ["الم اسفل يسار البطن", "وجع الجهة اليسرى اسفل البطن"], ["left lower abdominal pain", "left lower quadrant pain"]),
    ("hot-swollen-joint", "مفصل حار ومتورم", "Hot swollen joint", "pain", ["المفصل حار ومتورم", "تورم مفصل مع حرارة"], ["hot swollen joint", "warm swollen joint"]),
    ("big-toe-pain", "ألم شديد في إصبع القدم الكبير", "Big-toe pain", "pain", ["الم اصبع القدم الكبير", "وجع ابهام القدم"], ["big toe pain", "painful big toe"]),
    ("joint-redness", "احمرار حول المفصل", "Joint redness", "pain", ["احمرار المفصل", "المفصل احمر"], ["red joint", "joint redness"]),
    ("hot-swollen-skin", "جلد حار ومتورم", "Hot swollen skin", "skin", ["الجلد حار ومتورم", "منطقة حارة ومنتفخة بالجلد"], ["hot swollen skin", "warm swollen skin"]),
    ("skin-warmth", "سخونة موضعية في الجلد", "Localized skin warmth", "skin", ["سخونة بالجلد", "المنطقة حارة"], ["skin warmth", "warm skin"]),
    ("throat-swelling", "تورم الحلق", "Throat swelling", "respiratory", ["حلقي متورم", "تورم بالحلق", "الحلق يقفل"], ["throat swelling", "swollen throat"]),
    ("tongue-swelling", "تورم اللسان", "Tongue swelling", "respiratory", ["لساني متورم", "تورم اللسان"], ["tongue swelling", "swollen tongue"]),
    ("stiff-neck", "تيبس شديد في الرقبة", "Stiff neck", "neurological", ["رقبتي متيبسة", "تيبس شديد بالرقبة", "ما اقدر احرك رقبتي"], ["stiff neck", "neck stiffness"]),
    ("non-blanching-rash", "طفح لا يختفي بالضغط", "Non-blanching rash", "skin", ["طفح ما يختفي بالضغط", "بقع بنفسجية ما تروح بالضغط"], ["non blanching rash", "rash that does not fade under pressure"]),
    ("orthostatic-lightheadedness", "دوخة عند الوقوف", "Lightheadedness on standing", "neurological", ["ادوخ لما اقوم", "دوخة عند القيام", "دوخة اذا وقفت"], ["dizzy when standing", "lightheaded on standing"]),
    ("chronic-cough", "سعال مزمن", "Chronic cough", "respiratory", ["كحة مزمنة", "سعال مستمر"], ["chronic cough", "persistent cough"]),
    ("chronic-phlegm", "بلغم مزمن", "Chronic phlegm", "respiratory", ["بلغم مستمر", "بلغم مزمن"], ["chronic phlegm", "persistent sputum"]),
    ("breathlessness-on-exertion", "ضيق نفس مع المجهود", "Breathlessness on exertion", "respiratory", ["اتعب بالتنفس مع المشي", "ضيق نفس مع الحركة", "انهج مع الدرج"], ["shortness of breath on exertion", "breathless with activity"]),
    ("dry-mouth", "جفاف الفم", "Dry mouth", "general", ["فمي ناشف", "جفاف بالفم"], ["dry mouth"]),
    ("dark-urine", "بول داكن", "Dark urine", "general", ["البول غامق", "بول داكن"], ["dark urine"]),
    ("reduced-urination", "قلة التبول", "Reduced urination", "general", ["اتبول قليل", "قلة البول", "ما اتبول كثير"], ["reduced urination", "urinating less"]),
    ("chest-wall-tenderness", "ألم عند الضغط على جدار الصدر", "Chest-wall tenderness", "pain", ["صدري يوجع اذا ضغطت عليه", "ألم عند لمس الصدر"], ["chest tenderness", "pain when pressing chest"]),
    ("pain-on-deep-breath", "ألم يزداد مع النفس العميق", "Pain worse with deep breathing", "pain", ["الالم يزيد مع النفس", "صدري يوجع مع الشهيق"], ["pain worse with deep breath", "pain on deep breathing"]),
    ("position-triggered-vertigo", "دوار مع تغيير وضع الرأس", "Position-triggered vertigo", "neurological", ["ادوخ اذا حركت راسي", "دوار لما اتقلب بالسرير"], ["vertigo with head movement", "positional vertigo"]),
]

EXTRA_DISEASES_V2 = [
    {
        "slug": "appendicitis", "name_ar": "التهاب الزائدة الدودية", "name_en": "Appendicitis", "category": "digestive", "severity": "severe",
        "symptoms": {"right-lower-abdominal-pain": 1.0, "abdominal-pain": 0.75, "nausea": 0.6, "vomiting": 0.4, "loss-of-appetite": 0.65, "fever": 0.45},
        "description_ar": "قد يبدأ الألم قرب السرة ثم ينتقل إلى أسفل يمين البطن ويزداد. هذا احتمال توعوي يحتاج تقييمًا عاجلًا للتأكيد.",
        "description_en": "Pain may start near the navel and move to the lower right abdomen and worsen. This is an educational possibility requiring urgent assessment.",
        "risk_ar": "التهاب وانسداد الزائدة قد يتطور ويحتاج علاجًا بالمستشفى.", "risk_en": "Inflammation and obstruction of the appendix can progress and need hospital treatment.",
        "causes_ar": "يحدث عندما تلتهب الزائدة، وغالبًا بعد انسداد داخلها.", "causes_en": "It occurs when the appendix becomes inflamed, often after blockage inside it.",
        "red_ar": "ألم متزايد أو شديد أسفل يمين البطن، خاصة مع قيء أو حرارة، يحتاج تقييمًا عاجلًا.", "red_en": "Worsening or severe lower-right abdominal pain, especially with vomiting or fever, needs urgent assessment.",
        "next_ar": "اطلب تقييمًا طبيًا عاجلًا اليوم إذا كان النمط متوافقًا، ولا تعتمد على المسكنات وحدها.", "next_en": "Seek urgent same-day medical assessment if the pattern fits; do not rely on pain relief alone.",
        "sources": [("nhs", "التهاب الزائدة الدودية — NHS", "Appendicitis — NHS", "https://www.nhs.uk/conditions/appendicitis/")],
    },
    {
        "slug": "cellulitis", "name_ar": "التهاب النسيج الخلوي", "name_en": "Cellulitis", "category": "skin", "severity": "moderate",
        "symptoms": {"hot-swollen-skin": 1.0, "skin-warmth": 0.85, "skin-rash": 0.6, "fever": 0.35, "swollen-lymph-nodes": 0.3},
        "description_ar": "عدوى في طبقات الجلد الأعمق قد تسبب منطقة مؤلمة وحارة ومتورمة. تحتاج علاجًا طبيًا سريعًا.",
        "description_en": "An infection of deeper skin layers can cause a painful, hot, swollen area and needs prompt medical treatment.",
        "risk_ar": "قد تنتشر العدوى إذا لم تُعالج مبكرًا.", "risk_en": "The infection can spread if not treated promptly.",
        "causes_ar": "غالبًا تدخل البكتيريا عبر جرح أو تشقق صغير بالجلد.", "causes_en": "Bacteria often enter through a small cut or break in the skin.",
        "red_ar": "حرارة شديدة، دوخة، سرعة تنفس أو نبض، ارتباك أو فقد وعي مع التهاب الجلد تستدعي الطوارئ.", "red_en": "High fever, dizziness, fast breathing or pulse, confusion, or loss of consciousness with cellulitis needs emergency care.",
        "next_ar": "اطلب تقييمًا طبيًا في نفس اليوم إذا كان الجلد مؤلمًا وحارًا ومتورمًا.", "next_en": "Seek same-day medical assessment for painful, hot, swollen skin.",
        "sources": [("nhs", "التهاب النسيج الخلوي — NHS", "Cellulitis — NHS", "https://www.nhs.uk/conditions/cellulitis/")],
    },
    {
        "slug": "gout", "name_ar": "النقرس", "name_en": "Gout", "category": "pain", "severity": "moderate",
        "symptoms": {"hot-swollen-joint": 1.0, "big-toe-pain": 0.95, "joint-redness": 0.8, "joint-pain": 0.65},
        "description_ar": "قد يسبب النقرس ألمًا مفاجئًا شديدًا مع سخونة وتورم واحمرار بمفصل، وغالبًا إصبع القدم الكبير.",
        "description_en": "Gout can cause sudden severe pain with heat, swelling, and redness in a joint, often the big toe.",
        "risk_ar": "ارتفاع حمض اليوريك قد يؤدي إلى ترسب بلورات حول المفاصل.", "risk_en": "High uric acid can lead to crystal deposits around joints.",
        "causes_ar": "ترتبط النوبات بارتفاع حمض اليوريك وقد تحفزها بعض الأمراض أو الجفاف أو أدوية معينة.", "causes_en": "Attacks are linked to high uric acid and can be triggered by illness, dehydration, or some medicines.",
        "red_ar": "مفصل حار ومتورم مع حرارة عامة قد يشبه عدوى المفصل ويحتاج تقييمًا عاجلًا.", "red_en": "A hot swollen joint with fever can resemble a joint infection and needs urgent assessment.",
        "next_ar": "راجع طبيبًا إذا كانت هذه أول نوبة أو إذا لم يتحسن الألم أو صاحبتها حرارة.", "next_en": "Seek medical review for a first attack, symptoms that are not improving, or fever.",
        "sources": [("nhs", "النقرس — NHS", "Gout — NHS", "https://www.nhs.uk/conditions/gout/")],
    },
    {
        "slug": "celiac-disease", "name_ar": "الداء البطني (السيلياك)", "name_en": "Celiac disease", "category": "digestive", "severity": "moderate",
        "symptoms": {"bloating": 0.75, "diarrhea": 0.65, "constipation": 0.45, "abdominal-pain": 0.6, "nausea": 0.35, "fatigue": 0.45, "greasy-stools": 0.6, "weight-loss": 0.35},
        "description_ar": "اضطراب مناعي مزمن يتأثر بالغلوتين وقد يسبب أعراضًا هضمية أو عامة متعددة؛ لا يُشخّص من الأعراض وحدها.",
        "description_en": "A chronic immune disorder triggered by gluten that can cause varied digestive and non-digestive symptoms; symptoms alone do not diagnose it.",
        "risk_ar": "قد يسبب سوء امتصاص ونقص عناصر غذائية عند عدم العلاج.", "risk_en": "Untreated disease may lead to malabsorption and nutrient deficiencies.",
        "causes_ar": "استجابة مناعية للغلوتين لدى أشخاص لديهم قابلية للإصابة.", "causes_en": "An immune reaction to gluten in susceptible people.",
        "red_ar": "فقدان وزن غير مفسر أو دم بالبراز أو أعراض مستمرة تحتاج تقييمًا طبيًا.", "red_en": "Unexplained weight loss, blood in stool, or persistent symptoms need medical assessment.",
        "next_ar": "راجع الطبيب للفحوص المناسبة قبل بدء حمية خالية من الغلوتين بشكل صارم، لأن الاختبارات قد تتأثر بتغيير الغذاء.", "next_en": "Seek medical testing before starting a strict gluten-free diet because dietary changes can affect diagnostic tests.",
        "sources": [("niddk", "أعراض وأسباب الداء البطني — NIDDK", "Symptoms & Causes of Celiac Disease — NIDDK", "https://www.niddk.nih.gov/health-information/digestive-diseases/celiac-disease/symptoms-causes")],
    },
    {
        "slug": "copd-pattern", "name_ar": "نمط قد يتوافق مع مرض الانسداد الرئوي المزمن", "name_en": "Pattern compatible with COPD", "category": "respiratory", "severity": "moderate",
        "symptoms": {"chronic-cough": 0.85, "chronic-phlegm": 0.8, "breathlessness-on-exertion": 1.0, "wheezing": 0.55, "fatigue": 0.3},
        "description_ar": "السعال المزمن والبلغم وضيق النفس مع الجهد قد تظهر في أمراض رئوية مزمنة منها COPD، ويحتاج الأمر تقييمًا للتأكيد.",
        "description_en": "Chronic cough, phlegm, and exertional breathlessness can occur in chronic lung disease including COPD and require assessment to confirm the cause.",
        "risk_ar": "الأعراض المزمنة قد تؤثر في القدرة على التنفس والنشاط وتحتاج فحصًا وظيفيًا للرئة.", "risk_en": "Persistent symptoms can limit breathing and activity and may require lung-function testing.",
        "causes_ar": "يرتبط غالبًا بالتعرض الطويل لمهيجات الرئة مثل دخان التبغ أو الملوثات.", "causes_en": "It is commonly associated with long-term exposure to lung irritants such as tobacco smoke or pollutants.",
        "red_ar": "ضيق نفس شديد أو متفاقم بسرعة، زرقة أو ارتباك يستدعي رعاية عاجلة.", "red_en": "Severe or rapidly worsening breathlessness, blue/grey discoloration, or confusion needs urgent care.",
        "next_ar": "احجز تقييمًا طبيًا إذا كان السعال أو البلغم أو ضيق النفس مستمرًا، خصوصًا مع تاريخ تدخين أو تعرض مهني.", "next_en": "Arrange medical assessment for persistent cough, phlegm, or breathlessness, especially with smoking or occupational exposure.",
        "sources": [("nhlbi", "أعراض COPD — NHLBI", "COPD Symptoms — NHLBI", "https://www.nhlbi.nih.gov/health/copd/symptoms")],
    },
    {
        "slug": "orthostatic-hypotension", "name_ar": "هبوط الضغط عند الوقوف", "name_en": "Orthostatic hypotension", "category": "cardiovascular", "severity": "moderate",
        "symptoms": {"orthostatic-lightheadedness": 1.0, "dizziness": 0.65, "blurred-vision": 0.45, "fatigue": 0.3},
        "description_ar": "قد يحدث دوار أو خفة بالرأس عند الانتقال للوقوف بسبب انخفاض ضغط الدم، لكن توجد أسباب أخرى للدوخة أيضًا.",
        "description_en": "Lightheadedness on standing can occur with a blood-pressure drop, although dizziness has many other possible causes.",
        "risk_ar": "قد يزيد خطر السقوط، وقد يرتبط بالجفاف أو الأدوية أو حالات أخرى.", "risk_en": "It can increase fall risk and may relate to dehydration, medicines, or other conditions.",
        "causes_ar": "تتعدد الأسباب وتشمل الجفاف وبعض الأدوية واضطرابات القلب أو الأعصاب.", "causes_en": "Causes include dehydration, some medicines, and cardiovascular or neurological conditions.",
        "red_ar": "الإغماء أو ألم الصدر أو ضيق النفس أو نبض غير منتظم يحتاج تقييمًا سريعًا.", "red_en": "Fainting, chest pain, shortness of breath, or an irregular heartbeat needs prompt assessment.",
        "next_ar": "انهض ببطء واطلب تقييمًا إذا تكررت الدوخة أو حدث إغماء؛ لا تغيّر دواء موصوفًا دون استشارة.", "next_en": "Rise slowly and seek review for recurrent symptoms or fainting; do not change prescribed medicines without advice.",
        "sources": [("medlineplus", "انخفاض ضغط الدم — MedlinePlus", "Low blood pressure — MedlinePlus", "https://www.medlineplus.gov/ency/article/007278.htm")],
    },
    {
        "slug": "dehydration-pattern", "name_ar": "الجفاف", "name_en": "Dehydration", "category": "general", "severity": "moderate",
        "symptoms": {"increased-thirst": 0.75, "dry-mouth": 0.8, "reduced-urination": 0.9, "dark-urine": 0.75, "dizziness": 0.55, "fatigue": 0.4, "dehydration": 1.0},
        "description_ar": "فقدان السوائل أكثر من تعويضها قد يسبب عطشًا وجفاف الفم وقلة البول والدوخة والتعب.",
        "description_en": "Losing more fluid than is replaced can cause thirst, dry mouth, reduced urination, dizziness, and fatigue.",
        "risk_ar": "الجفاف الشديد قد يؤثر في الدورة الدموية والوعي.", "risk_en": "Severe dehydration can affect circulation and alertness.",
        "causes_ar": "من أسبابه الإسهال والقيء والحمى والتعرق وقلة شرب السوائل.", "causes_en": "Causes include diarrhea, vomiting, fever, heavy sweating, and inadequate fluid intake.",
        "red_ar": "ارتباك أو إغماء أو انقطاع البول أو سرعة شديدة في النبض أو التنفس تستدعي مساعدة عاجلة.", "red_en": "Confusion, fainting, no urination, or very rapid pulse or breathing needs urgent medical help.",
        "next_ar": "ابدأ بتعويض السوائل تدريجيًا إذا كنت قادرًا على الشرب، واطلب تقييمًا إذا تعذر الاحتفاظ بالسوائل أو ظهرت علامات شديدة.", "next_en": "Replace fluids gradually if you can drink, and seek care if you cannot keep fluids down or severe signs appear.",
        "sources": [("medlineplus", "الجفاف — MedlinePlus", "Dehydration — MedlinePlus", "https://medlineplus.gov/dehydration.html")],
    },
    {
        "slug": "costochondritis", "name_ar": "التهاب غضاريف القفص الصدري", "name_en": "Costochondritis", "category": "pain", "severity": "moderate",
        "symptoms": {"chest-pain": 0.75, "chest-wall-tenderness": 1.0, "pain-on-deep-breath": 0.7},
        "description_ar": "قد يسبب التهاب منطقة اتصال الأضلاع بعظمة الصدر ألمًا حادًا يزداد بالحركة أو التنفس أو الضغط على الصدر.",
        "description_en": "Inflammation where ribs meet the breastbone can cause sharp pain worsened by movement, breathing, or chest pressure.",
        "risk_ar": "ألم الصدر يحتاج أولًا لاستبعاد الأسباب الأخطر قبل اعتباره عضليًا أو غضروفيًا.", "risk_en": "Chest pain should first be assessed for more serious causes before assuming a chest-wall cause.",
        "causes_ar": "قد يرتبط بإجهاد أو سعال متكرر أو إصابة، وأحيانًا لا يُعرف السبب.", "causes_en": "It may follow strain, repeated coughing, or injury, and sometimes no cause is found.",
        "red_ar": "ألم صدر مفاجئ أو ضغط/ثقل أو ألم ينتشر للذراع أو الفك أو مع ضيق نفس يستدعي الطوارئ.", "red_en": "Sudden chest pain, pressure/heaviness, pain spreading to the arm or jaw, or breathlessness needs emergency care.",
        "next_ar": "احصل على تقييم طبي لألم الصدر غير المفسر، حتى لو كان يزداد بالضغط أو الحركة.", "next_en": "Get medical assessment for unexplained chest pain, even when it is reproducible with pressure or movement.",
        "sources": [("nhs", "التهاب غضاريف القفص الصدري — NHS", "Costochondritis — NHS", "https://www.nhs.uk/conditions/costochondritis/")],
    },
    {
        "slug": "diverticulitis", "name_ar": "التهاب الرتوج", "name_en": "Diverticulitis", "category": "digestive", "severity": "moderate",
        "symptoms": {"left-lower-abdominal-pain": 1.0, "abdominal-pain": 0.65, "constipation": 0.45, "diarrhea": 0.35, "fever": 0.55, "bloating": 0.35},
        "description_ar": "التهاب الجيوب الصغيرة في جدار الأمعاء قد يسبب ألمًا مستمرًا غالبًا أسفل يسار البطن مع حرارة أو تغير في التبرز.",
        "description_en": "Inflammation of small pouches in the bowel wall can cause persistent lower-left abdominal pain with fever or bowel changes.",
        "risk_ar": "قد تحدث مضاعفات مثل خراج أو ثقب أو انسداد، لذلك يحتاج الألم المستمر أو المتفاقم تقييمًا.", "risk_en": "Complications can include abscess, perforation, or obstruction, so persistent or worsening pain needs assessment.",
        "causes_ar": "تحدث عندما تلتهب أو تُصاب الرتوج الموجودة في جدار القولون.", "causes_en": "It occurs when diverticula in the colon wall become inflamed or infected.",
        "red_ar": "ألم شديد مع قيء أو انتفاخ وعدم القدرة على إخراج غازات أو براز، أو نزيف شديد، يستدعي الطوارئ.", "red_en": "Severe pain with vomiting, abdominal swelling and inability to pass stool/gas, or heavy rectal bleeding needs emergency care.",
        "next_ar": "اطلب تقييمًا طبيًا إذا كان الألم مستمرًا أو يزداد أو ترافق مع حرارة أو قيء.", "next_en": "Seek medical assessment for persistent or worsening pain, fever, or vomiting.",
        "sources": [("nhs", "مرض الرتوج والتهاب الرتوج — NHS", "Diverticular disease and diverticulitis — NHS", "https://www.nhs.uk/conditions/diverticular-disease-and-diverticulitis/")],
    },
    {
        "slug": "bppv", "name_ar": "الدوار الوضعي الانتيابي الحميد", "name_en": "Benign paroxysmal positional vertigo (BPPV)", "category": "neurological", "severity": "moderate",
        "symptoms": {"position-triggered-vertigo": 1.0, "dizziness": 0.65, "nausea": 0.4, "balance-problems": 0.35},
        "description_ar": "نوبات دوار قصيرة قد تُثار بحركات محددة للرأس، لكن الدوار الجديد يحتاج تقييمًا لاستبعاد أسباب أخرى.",
        "description_en": "Brief vertigo episodes may be triggered by particular head movements, but new vertigo needs assessment to exclude other causes.",
        "risk_ar": "يزيد الدوار خطر السقوط وقد يشبه أحيانًا حالات عصبية أخطر.", "risk_en": "Vertigo can increase fall risk and can occasionally resemble more serious neurological conditions.",
        "causes_ar": "يرتبط غالبًا بحركة بلورات صغيرة داخل الأذن الداخلية.", "causes_en": "It is commonly related to displaced inner-ear crystals.",
        "red_ar": "الدوار مع ضعف أو تنميل جهة واحدة أو صعوبة الكلام أو فقدان الرؤية يحتاج طوارئ.", "red_en": "Vertigo with one-sided weakness/numbness, speech difficulty, or vision loss needs emergency care.",
        "next_ar": "راجع مختصًا إذا كان الدوار جديدًا أو متكررًا، وتجنب القيادة أثناء النوبات.", "next_en": "Seek assessment for new or recurrent vertigo and avoid driving during attacks.",
        "sources": [("nhs", "الدوار — NHS", "Vertigo — NHS", "https://www.nhs.uk/conditions/vertigo/")],
    },
]

# Existing entries gain a second independent high-authority reference where it
# materially improves traceability.  These additions are idempotent because the
# DB relation is unique per disease/source.
EXISTING_DISEASE_SOURCE_ENRICHMENT = {
    "migraine": [("ninds", "الصداع النصفي — NINDS", "Migraine — NINDS", "https://www.ninds.nih.gov/sites/default/files/2025-07/NINDS_Headache_Booklet_Digital_508c%20%281%29.pdf")],
    "gerd": [("niddk", "أعراض وأسباب الارتجاع المعدي المريئي — NIDDK", "Symptoms & Causes of GER & GERD — NIDDK", "https://www.niddk.nih.gov/health-information/digestive-diseases/acid-reflux-ger-gerd-adults/symptoms-causes")],
    "irritable-bowel-syndrome": [("niddk", "متلازمة القولون العصبي — NIDDK", "Irritable Bowel Syndrome — NIDDK", "https://www.niddk.nih.gov/health-information/digestive-diseases/irritable-bowel-syndrome")],
    "functional-constipation": [("niddk", "أعراض وأسباب الإمساك — NIDDK", "Symptoms & Causes of Constipation — NIDDK", "https://www.niddk.nih.gov/health-information/digestive-diseases/constipation/symptoms-causes")],
    "kidney-stones": [("niddk", "أعراض وأسباب حصى الكلى — NIDDK", "Symptoms & Causes of Kidney Stones — NIDDK", "https://www.niddk.nih.gov/health-information/urologic-diseases/kidney-stones/symptoms-causes")],
    "asthma": [("nhlbi", "الربو — NHLBI", "Asthma — NHLBI", "https://www.nhlbi.nih.gov/health/asthma")],
}

# Extra links between existing diseases and the richer symptom vocabulary.
EXISTING_DISEASE_SYMPTOM_ENRICHMENT = {
    "urinary-tract-infection": {"cloudy-urine": 0.7, "blood-in-urine": 0.45, "flank-pain": 0.35},
    "kidney-stones": {"flank-pain": 1.0, "blood-in-urine": 0.8, "cloudy-urine": 0.3},
    "kidney-infection": {"flank-pain": 0.85, "cloudy-urine": 0.45},
    "acute-sinusitis": {"sinus-pressure": 1.0, "nasal-congestion": 0.8, "reduced-smell": 0.6, "thick-nasal-discharge": 0.85},
    "conjunctivitis": {"eye-discharge": 0.85, "gritty-eyes": 0.7, "watery-eyes": 0.65},
    "functional-constipation": {"constipation": 1.0, "straining-stool": 0.85, "incomplete-evacuation": 0.75},
    "gallstones": {"right-upper-abdominal-pain": 0.95},
    "gerd": {"hoarseness": 0.35, "difficulty-swallowing": 0.25},
}

EXTRA_RED_RULES_V2 = [
    (
        "anaphylaxis-airway", "تورم مفاجئ بالحلق أو اللسان", "Sudden throat or tongue swelling",
        ["throat-swelling", "tongue-swelling"], "any", ["تورم الحلق", "تورم اللسان", "الحلق يقفل", "صعوبة بلع مفاجئة"],
        ["throat swelling", "tongue swelling", "swollen throat", "swollen tongue"],
        1, "urgent", "تورم الحلق أو اللسان قد يكون علامة تحسس شديد يهدد التنفس.",
        "Throat or tongue swelling can be a sign of a severe allergic reaction threatening the airway.", "nhs",
    ),
    (
        "meningitis-pattern", "صداع شديد مع تيبس الرقبة والحمى", "Severe headache with stiff neck and fever",
        ["severe-headache", "stiff-neck", "fever"], "all", [], [],
        1, "urgent", "الصداع الشديد مع تيبس الرقبة والحمى يحتاج تقييمًا طبيًا عاجلًا لاحتمال عدوى خطيرة.",
        "Severe headache with a stiff neck and fever needs urgent medical assessment for a potentially serious infection.", "nhs",
    ),
    (
        "non-blanching-rash", "طفح لا يختفي بالضغط", "Non-blanching rash",
        ["non-blanching-rash"], "any", [], [],
        1, "urgent", "الطفح الذي لا يختفي بالضغط مع المرض العام قد يكون علامة خطيرة ويحتاج مساعدة عاجلة.",
        "A non-blanching rash with systemic illness can be a serious warning sign and needs urgent help.", "nhs",
    ),
    (
        "severe-dehydration", "علامات جفاف شديد", "Severe dehydration signs",
        [], "any", ["لا اتبول", "انقطاع البول", "جفاف شديد مع اغماء", "جفاف مع ارتباك"],
        ["no urination", "severe dehydration with fainting", "dehydration with confusion"],
        1, "urgent", "الارتباك أو الإغماء أو انقطاع البول مع الجفاف علامات تستدعي مساعدة طبية عاجلة.",
        "Confusion, fainting, or no urination with dehydration are warning signs requiring urgent medical help.", "medlineplus",
    ),
    (
        "hot-swollen-joint-fever", "مفصل حار ومتورم مع حرارة", "Hot swollen joint with fever",
        ["hot-swollen-joint", "fever"], "all", [], [],
        1, "urgent", "المفصل الحار والمتورم مع حرارة قد يشير إلى عدوى بالمفصل ويحتاج تقييمًا عاجلًا.",
        "A hot swollen joint with fever may indicate joint infection and needs urgent assessment.", "nhs",
    ),
]

EXTRA_RED_RULE_DETAILS_V2 = {
    "anaphylaxis-airway": {
        "description_ar": "التحسس الشديد قد يبدأ بسرعة ويسبب تورم اللسان أو الحلق وصعوبة التنفس أو البلع.",
        "description_en": "Anaphylaxis can develop rapidly and cause tongue or throat swelling with breathing or swallowing difficulty.",
        "action_ar": "اطلب خدمات الطوارئ فورًا إذا ظهر تورم مفاجئ بالحلق أو اللسان أو صعوبة تنفس/بلع.",
        "action_en": "Contact emergency services immediately for sudden throat/tongue swelling or breathing/swallowing difficulty.",
        "url": "https://www.nhs.uk/conditions/anaphylaxis/",
    },
    "meningitis-pattern": {
        "description_ar": "التهاب السحايا قد يتطور بسرعة ولا تظهر كل العلامات لدى كل شخص.",
        "description_en": "Meningitis can progress quickly and not everyone develops every classic sign.",
        "action_ar": "اطلب مساعدة طبية عاجلة ولا تنتظر ظهور طفح جلدي.",
        "action_en": "Seek urgent medical help and do not wait for a rash to appear.",
        "url": "https://www.nhs.uk/conditions/meningitis/",
    },
    "non-blanching-rash": {
        "description_ar": "الطفح الأحمر أو البنفسجي الذي لا يبهت عند الضغط عليه قد يرافق حالات خطيرة، خصوصًا مع تدهور عام.",
        "description_en": "A red or purple rash that does not fade under pressure can accompany serious illness, especially with systemic deterioration.",
        "action_ar": "اطلب مساعدة طبية فورية إذا كان الشخص مريضًا بوضوح أو ظهرت علامات التهاب السحايا أو تدهور سريع.",
        "action_en": "Seek immediate medical help if the person is clearly unwell, has meningitis signs, or is rapidly deteriorating.",
        "url": "https://www.nhs.uk/conditions/meningitis/",
    },
    "severe-dehydration": {
        "description_ar": "الجفاف الشديد قد يؤدي إلى اضطراب الوعي أو انقطاع البول أو تسارع النبض والتنفس.",
        "description_en": "Severe dehydration can cause altered alertness, absent urination, or rapid pulse and breathing.",
        "action_ar": "اطلب تقييمًا طبيًا عاجلًا إذا ظهرت علامات الجفاف الشديد.",
        "action_en": "Seek urgent medical assessment for signs of severe dehydration.",
        "url": "https://medlineplus.gov/dehydration.html",
    },
    "hot-swollen-joint-fever": {
        "description_ar": "ألم وتورم وسخونة مفصل مع حرارة عامة قد يكون من أسباب التهابية أو عدوى تحتاج تمييزًا سريعًا.",
        "description_en": "A painful hot swollen joint with fever can have inflammatory or infectious causes that need prompt differentiation.",
        "action_ar": "اطلب تقييمًا طبيًا عاجلًا في نفس اليوم.",
        "action_en": "Seek urgent same-day medical assessment.",
        "url": "https://www.nhs.uk/conditions/gout/",
    },
}
