"""V191 professional clinical-content expansion for SymptoSense.

Adds common symptom concepts and source-grounded heart/kidney patterns while
reusing authoritative sources already vetted by the main knowledge layer.
Content is educational and non-diagnostic.
"""

EXTRA_SOURCES_V9 = []

EXTRA_SYMPTOMS_V9 = [
    ("cold-intolerance", "الحساسية للبرد", "Cold intolerance", "general",
     ["احس بالبرد بسرعة", "بردان طول الوقت", "ما اتحمل البرد", "حساسية للبرد", "برودة غير معتادة"],
     ["cold intolerance", "always feel cold", "unusually cold", "sensitive to cold"]),
    ("heat-intolerance", "الحساسية للحرارة", "Heat intolerance", "general",
     ["ما اتحمل الحر", "اتعب من الحر بسرعة", "حساسية للحرارة", "الحر يتعبني"],
     ["heat intolerance", "cannot tolerate heat", "sensitive to heat", "heat makes me unwell"]),
    ("muscle-weakness", "ضعف العضلات", "Muscle weakness", "musculoskeletal",
     ["عضلاتي ضعيفة", "ضعف بالعضلات", "احس عضلاتي ما فيها قوة", "ضعف عضلي"],
     ["muscle weakness", "weak muscles", "muscles feel weak"]),
    ("pica", "اشتهاء أشياء غير غذائية", "Pica", "general",
     ["اشتهي الثلج", "اكل ثلج كثير", "اشتهي التراب", "اشتهي اشياء مو اكل", "رغبة بأكل الثلج"],
     ["pica", "craving ice", "eat ice", "craving non food items"]),
    ("brittle-nails", "تقصف أو هشاشة الأظافر", "Brittle nails", "skin",
     ["اظافري تتكسر", "أظافري تتكسر", "اظافر هشة", "تقصف الاظافر", "أظافري هشة"],
     ["brittle nails", "nails break easily", "fragile nails"]),
    ("ankle-swelling", "تورم الكاحلين", "Ankle swelling", "cardiovascular",
     ["كواحيلي متورمة", "تورم الكاحل", "انتفاخ الكاحلين", "ورم حول الكاحل"],
     ["ankle swelling", "swollen ankles", "ankles are swollen"]),
    ("orthopnea", "ضيق التنفس عند الاستلقاء", "Shortness of breath when lying flat", "respiratory",
     ["اتنفس بصعوبة لما انسدح", "ضيق نفس اذا نمت على ظهري", "احتاج مخدات عشان اتنفس", "اختناق عند الاستلقاء"],
     ["shortness of breath lying flat", "breathless when lying down", "need pillows to breathe", "orthopnea"]),
    ("reduced-exercise-tolerance", "انخفاض تحمل المجهود", "Reduced exercise tolerance", "cardiovascular",
     ["اتعب من مجهود بسيط", "ما اقدر امشي مثل قبل", "نفسي يقصر مع مجهود بسيط", "تعب سريع مع المشي"],
     ["reduced exercise tolerance", "tired with little activity", "breathless with mild exertion"]),
    ("foamy-urine", "بول رغوي", "Foamy urine", "urinary",
     ["بول رغوي", "البول فيه رغوة", "رغوة كثيرة في البول"],
     ["foamy urine", "frothy urine", "bubbles in urine"]),
    ("nighttime-urination", "التبول المتكرر ليلًا", "Frequent nighttime urination", "urinary",
     ["اقوم للحمام كثير بالليل", "اتبول كثير بالليل", "كثرة التبول ليلا", "اصحى اتبول اكثر من مرة"],
     ["nighttime urination", "urinating often at night", "nocturia", "wake to pee at night"]),
]

EXTRA_DISEASES_V9 = [
    {
        "slug": "heart-failure-pattern", "name_ar": "نمط أعراض قد يرتبط بقصور القلب", "name_en": "Heart-failure symptom pattern",
        "category": "cardiovascular", "severity": "moderate",
        "symptoms": {
            "shortness-of-breath": 0.82, "orthopnea": 0.92, "ankle-swelling": 0.82,
            "leg-swelling": 0.72, "fatigue": 0.50, "reduced-exercise-tolerance": 0.72,
            "palpitations": 0.30, "weight-gain": 0.35, "nighttime-urination": 0.24,
        },
        "description_ar": "قد يجتمع ضيق النفس مع تورم الساقين أو الكاحلين والتعب وصعوبة التنفس عند الاستلقاء في حالات قلبية متعددة، ومنها قصور القلب. هذا النمط لا يثبت التشخيص ويحتاج تقييمًا سريريًا.",
        "description_en": "Breathlessness with ankle/leg swelling, fatigue, and difficulty breathing when lying flat can occur in several cardiac conditions, including heart failure. This pattern is not diagnostic and needs clinical assessment.",
        "risk_ar": "ضيق التنفس الشديد أو ألم الصدر الشديد أو الإغماء أو ازرقاق الشفاه يستدعي الطوارئ فورًا.",
        "risk_en": "Severe breathing difficulty, severe chest pain, fainting, or blue lips requires emergency help now.",
        "causes_ar": "قصور القلب أحد الاحتمالات ضمن أسباب قلبية ورئوية وكلوية وأسباب أخرى لاحتباس السوائل وضيق النفس.",
        "causes_en": "Heart failure is one possibility among cardiac, lung, kidney, and other causes of fluid retention and breathlessness.",
        "red_ar": "ضيق نفس شديد في الراحة، ألم صدر شديد، فقد الوعي، أو تدهور سريع يحتاج رعاية طارئة.",
        "red_en": "Severe breathlessness at rest, severe chest pain, loss of consciousness, or rapid deterioration needs emergency care.",
        "next_ar": "احجز تقييمًا طبيًا إذا كان ضيق النفس أو التورم جديدًا أو متزايدًا، واطلب الطوارئ فورًا عند علامات الخطر.",
        "next_en": "Arrange medical assessment for new or worsening breathlessness/swelling; seek emergency help immediately for red flags.",
        "sources": [
            ("saudi-moh", "فشل القلب (قصور القلب) — وزارة الصحة السعودية", "Heart failure — Saudi Ministry of Health", "https://www.moh.gov.sa/healthawareness/educationalcontent/diseases/heartcirculatory/pages/006.aspx"),
            ("aha", "علامات وأعراض قصور القلب — AHA", "Heart Failure Signs and Symptoms — AHA", "https://www.heart.org/en/health-topics/heart-failure/warning-signs-of-heart-failure"),
        ],
    },
    {
        "slug": "chronic-kidney-disease-pattern", "name_ar": "نمط أعراض قد يرتبط بمرض الكلى المزمن", "name_en": "Chronic kidney disease symptom pattern",
        "category": "urinary", "severity": "moderate",
        "symptoms": {
            "fatigue": 0.45, "ankle-swelling": 0.68, "leg-swelling": 0.60, "foamy-urine": 0.72,
            "nighttime-urination": 0.42, "itching": 0.34, "muscle-cramps": 0.32,
            "weight-loss": 0.22, "loss-of-appetite": 0.30, "shortness-of-breath": 0.24,
        },
        "description_ar": "مرض الكلى المزمن قد لا يسبب أعراضًا مبكرًا، وعندما يتقدم قد تظهر تغيرات في البول أو تورم أو تعب وأعراض أخرى. لا يمكن تأكيده بالأعراض وحدها ويعتمد التقييم على فحوص الدم والبول والسياق الطبي.",
        "description_en": "Chronic kidney disease may cause no early symptoms; later it can be associated with urine changes, swelling, fatigue, and other symptoms. Symptoms alone cannot confirm it; assessment relies on blood/urine tests and clinical context.",
        "risk_ar": "ضيق نفس شديد، ألم صدر، تشوش شديد، أو تدهور حاد يستدعي تقييمًا عاجلًا أو طارئًا حسب الشدة.",
        "risk_en": "Severe breathlessness, chest pain, marked confusion, or acute deterioration needs urgent or emergency assessment depending on severity.",
        "causes_ar": "ترتبط أمراض الكلى المزمنة بأسباب متعددة، ومن عوامل الخطورة الشائعة السكري وارتفاع ضغط الدم وأمراض أخرى.",
        "causes_en": "Chronic kidney disease has multiple causes; common risk factors include diabetes, high blood pressure, and other conditions.",
        "red_ar": "قلة بول شديدة مع تدهور عام أو ضيق نفس شديد أو تورم سريع يحتاج تقييمًا سريعًا.",
        "red_en": "Markedly reduced urine with systemic deterioration, severe breathlessness, or rapidly increasing swelling needs prompt assessment.",
        "next_ar": "راجع الطبيب إذا كانت تغيرات البول أو التورم أو التعب مستمرة، خاصةً مع السكري أو الضغط أو نتائج كلى غير طبيعية.",
        "next_en": "Seek medical review for persistent urine changes, swelling, or fatigue, especially with diabetes, hypertension, or abnormal kidney tests.",
        "sources": [
            ("saudi-moh", "أمراض الكلى المزمنة — وزارة الصحة السعودية", "Chronic kidney disease — Saudi Ministry of Health", "https://www.moh.gov.sa/awarenessplateform/chronicdisease/pages/ckd.aspx"),
            ("niddk", "ما مرض الكلى المزمن؟ — NIDDK", "What Is Chronic Kidney Disease? — NIDDK", "https://www.niddk.nih.gov/health-information/kidney-disease/chronic-kidney-disease-ckd/what-is-chronic-kidney-disease"),
        ],
    },
]

EXISTING_DISEASE_SOURCE_ENRICHMENT_V9 = {
    "underactive-thyroid": [
        ("saudi-moh", "كسل الغدة الدرقية — وزارة الصحة السعودية", "Hypothyroidism — Saudi Ministry of Health", "https://www.moh.gov.sa/healthawareness/educationalcontent/diseases/endocrinology/pages/004.aspx"),
    ],
    "overactive-thyroid": [
        ("saudi-moh", "فرط نشاط الغدة الدرقية — وزارة الصحة السعودية", "Hyperthyroidism — Saudi Ministry of Health", "https://www.moh.gov.sa/healthawareness/educationalcontent/diseases/endocrinology/pages/006.aspx"),
    ],
    "iron-deficiency-anaemia": [
        ("saudi-moh", "فقر الدم الناجم عن نقص الحديد — وزارة الصحة السعودية", "Iron-deficiency anaemia — Saudi Ministry of Health", "https://www.moh.gov.sa/healthawareness/educationalcontent/diseases/hematology/pages/0010.aspx"),
    ],
}

EXISTING_DISEASE_SYMPTOM_ENRICHMENT_V9 = {
    "underactive-thyroid": {"cold-intolerance": 0.82, "muscle-weakness": 0.34},
    "overactive-thyroid": {"heat-intolerance": 0.85, "muscle-weakness": 0.55},
    "iron-deficiency-anaemia": {"pica": 0.82, "brittle-nails": 0.55, "cold-intolerance": 0.38},
}

EXTRA_RED_RULES_V9 = []
EXTRA_RED_RULE_DETAILS_V9 = {}
