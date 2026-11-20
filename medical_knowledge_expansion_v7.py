"""V75 common-symptom expansion for broader Health Search coverage.

This pack intentionally reuses conditions and references that are already
curated in SymptoSense.  It adds symptom concepts/aliases and links them to
existing source-grounded conditions; it does not create new diagnoses or
unsourced medical claims.
"""

EXTRA_SYMPTOMS_V7 = [
    ("dry-cough", "سعال جاف بدون بلغم", "Dry cough without phlegm", "respiratory", ["كحة ناشفة", "كحه ناشفه", "سعال ناشف", "اكح بدون بلغم"], ["dry cough", "cough without phlegm", "non productive cough"]),
    ("productive-cough", "سعال مع بلغم", "Cough with phlegm", "respiratory", ["كحة ببلغم", "كحه مع بلغم", "سعال فيه بلغم", "اطلع بلغم مع الكحة"], ["productive cough", "cough with phlegm", "chesty cough"]),
    ("throat-clearing", "الحاجة المتكررة لتنظيف الحلق", "Frequent throat clearing", "respiratory", ["انحنح كثير", "اتنحنح كثير", "احتاج انظف حلقي كثير", "تنحنح مستمر"], ["frequent throat clearing", "keep clearing my throat", "constant throat clearing"]),
    ("nasal-itching", "حكة داخل الأنف", "Itchy nose", "respiratory", ["انفي يحكني", "خشمي يحكني", "حكة داخل الانف", "حكه بالانف"], ["itchy nose", "nose itching", "itch inside nose"]),
    ("eye-itching", "حكة في العين", "Itchy eyes", "eye", ["عيني تحكني", "عيوني تحكني", "حكة بالعين", "حكه بالعين"], ["itchy eyes", "eye itching", "eyes itch"]),
    ("eyelid-swelling", "تورم أو انتفاخ الجفن", "Swollen eyelid", "eye", ["جفني منتفخ", "تورم الجفن", "انتفاخ الجفن", "عيني منفخه من الجفن"], ["swollen eyelid", "eyelid swelling", "puffy eyelid"]),
    ("dry-eye-feeling", "إحساس بجفاف العين", "Dry-eye sensation", "eye", ["عيني ناشفة", "عيوني جافة", "احس عيني ناشفه", "جفاف بالعين"], ["dry eyes", "eyes feel dry", "dry eye feeling"]),
    ("ear-itching", "حكة داخل الأذن", "Itchy ear canal", "ear", ["اذني تحكني", "حكة داخل الاذن", "حكه بالاذن", "احك اذني كثير"], ["itchy ear", "ear canal itching", "ear itching"]),
    ("ear-pressure", "ضغط أو امتلاء داخل الأذن", "Ear pressure or fullness", "ear", ["ضغط باذني", "احس اذني مليانه", "امتلاء الاذن", "ضغط داخل الاذن"], ["ear pressure", "ear fullness", "pressure in ear"]),
    ("gum-pain", "ألم أو وجع اللثة", "Gum pain or soreness", "mouth", ["لثتي توجعني", "الم باللثة", "وجع اللثه", "اللثة تؤلمني"], ["gum pain", "sore gums", "gums hurt"]),
    ("tongue-soreness", "ألم أو حساسية اللسان", "Sore or tender tongue", "mouth", ["لساني يوجعني", "لساني مؤلم", "الم باللسان", "حساسية اللسان"], ["sore tongue", "tongue pain", "tender tongue"]),
    ("abdominal-fullness", "إحساس بالامتلاء أو الثقل في البطن", "Abdominal fullness", "digestive", ["بطني ممتلئ", "احس بطني ثقيل", "امتلاء بالبطن", "ثقل بالمعدة"], ["abdominal fullness", "stomach feels full", "heavy stomach"]),
    ("post-meal-nausea", "غثيان بعد الأكل", "Nausea after eating", "digestive", ["يجيني غثيان بعد الاكل", "الوعه بعد الاكل", "اتلوع بعد ما اكل", "غثيان بعد الوجبة"], ["nausea after eating", "feel sick after meals", "post meal nausea"]),
    ("mucus-in-stool", "مخاط ظاهر مع البراز", "Mucus in stool", "digestive", ["مخاط بالبراز", "البراز فيه مخاط", "اشوف مخاط مع البراز"], ["mucus in stool", "mucus with bowel movement", "mucus in poop"]),
    ("bowel-urgency", "حاجة ملحّة ومفاجئة للتبرز", "Bowel urgency", "digestive", ["لازم ادخل الحمام بسرعه", "حاجة مفاجئة للتبرز", "الحاجه للحمام فجأة", "استعجال بالتبرز"], ["bowel urgency", "urgent need to poop", "sudden need for bowel movement"]),
    ("rectal-itching", "حكة حول فتحة الشرج", "Anal or rectal itching", "digestive", ["حكة حول الشرج", "حكه بفتحة الشرج", "الشرج يحكني"], ["anal itching", "itchy anus", "rectal itching"]),
    ("hip-pain", "ألم الورك", "Hip pain", "musculoskeletal", ["وركي يوجعني", "الم بالورك", "وجع مفصل الورك"], ["hip pain", "my hip hurts", "pain in hip"]),
    ("ankle-pain", "ألم الكاحل", "Ankle pain", "musculoskeletal", ["كاحلي يوجعني", "الم بالكاحل", "وجع الكاحل"], ["ankle pain", "my ankle hurts", "pain in ankle"]),
    ("morning-joint-stiffness", "تيبس المفاصل عند الاستيقاظ", "Morning joint stiffness", "musculoskeletal", ["مفاصلي متيبسه الصباح", "تيبس المفاصل الصباح", "اصحى ومفاصلي يابسه"], ["morning joint stiffness", "joints stiff in morning", "stiff joints on waking"]),
    ("muscle-soreness", "ألم أو وجع العضلات", "Muscle soreness or aching", "musculoskeletal", ["عضلاتي توجعني", "وجع بالعضلات", "الم عضلي", "عضلاتي مكسرة"], ["muscle soreness", "aching muscles", "muscles hurt"]),
    ("jaw-locking", "قفل أو صعوبة فتح الفك", "Jaw locking or difficulty opening", "mouth", ["فكي يقفل", "ما اقدر افتح فمي كويس", "الفك يعلق", "صعوبة فتح الفك"], ["jaw locking", "jaw gets stuck", "difficulty opening jaw"]),
    ("skin-redness", "احمرار موضعي في الجلد", "Localized skin redness", "skin", ["جلدي احمر", "احمرار بالجلد", "بقعة حمراء بالجلد"], ["skin redness", "red skin patch", "localized redness"]),
    ("cracked-skin", "تشقق الجلد", "Cracked skin", "skin", ["جلدي متشقق", "تشقق بالجلد", "شقوق بالجلد", "جلدي يتشقق"], ["cracked skin", "skin cracks", "skin is cracked"]),
    ("scalp-redness", "احمرار أو تهيج فروة الرأس", "Red or irritated scalp", "skin", ["فروة راسي حمراء", "احمرار فروة الرأس", "فروة راسي متهيجة"], ["red scalp", "scalp redness", "irritated scalp"]),
    ("restless-sleep", "نوم مضطرب أو غير مستقر", "Restless sleep", "general", ["نومي مضطرب", "اتقلب كثير بالنوم", "نومي مو مستقر", "ما انام براحه"], ["restless sleep", "tossing and turning", "sleep is unsettled"]),
    ("waking-unrefreshed", "الاستيقاظ دون الشعور بالراحة", "Waking unrefreshed", "general", ["اصحى تعبان", "انام واصحى مو مرتاح", "اصحى كاني ما نمت", "النوم ما يريحني"], ["wake up tired", "waking unrefreshed", "sleep does not refresh me"]),
    ("radiating-leg-pain", "ألم يمتد من الظهر أو الورك إلى الساق", "Pain radiating from back or hip down the leg", "musculoskeletal", ["الم ينزل من ظهري لرجلي", "وجع يمتد للساق", "الم من الورك الى الرجل", "الالم ينزل على رجلي"], ["pain shoots down leg", "radiating leg pain", "back pain down the leg"]),
    ("knee-stiffness", "تيبس الركبة", "Knee stiffness", "musculoskeletal", ["ركبتي متيبسه", "تيبس الركبة", "ركبتي يابسه", "صعوبة تحريك الركبة"], ["knee stiffness", "stiff knee", "knee feels stiff"]),
    ("foot-burning", "حرقان أو لسع في القدمين", "Burning feet", "neurological", ["رجولي تحرق", "حرقان بالقدم", "باطن رجلي يحرق", "قدمي تحرقني"], ["burning feet", "feet burning", "burning sensation in feet"]),
    ("hand-weakness", "ضعف في اليد أو القبضة", "Hand or grip weakness", "neurological", ["يدي ضعيفه", "قبضتي ضعفت", "الاشياء تطيح من يدي", "ضعف باليد"], ["hand weakness", "weak grip", "dropping things from hand"]),
    ("neck-muscle-tightness", "شد عضلات الرقبة", "Neck muscle tightness", "musculoskeletal", ["رقبتي مشدوده", "شد بالرقبة", "عضلات رقبتي مشدودة"], ["neck tightness", "tight neck muscles", "neck muscle tension"]),
    ("shoulder-night-pain", "ألم الكتف ليلًا أو عند النوم عليه", "Shoulder pain at night", "musculoskeletal", ["كتفي يوجعني بالليل", "الكتف يوجع لما انام عليه", "الم الكتف وقت النوم"], ["shoulder pain at night", "shoulder hurts when lying on it", "night shoulder pain"]),
    ("calf-ache-standing", "وجع أو ثقل بطة الساق مع الوقوف", "Calf ache or heaviness with standing", "vascular", ["بطه رجلي توجع مع الوقوف", "ساقي تثقل لما اوقف", "وجع الساق مع الوقوف الطويل"], ["calf ache standing", "legs ache after standing", "calf heaviness standing"]),
]

# Link every new concept to already sourced conditions.  Weights are kept
# conservative because these symptoms are non-specific and are used for
# retrieval/context, not for diagnosis.
EXISTING_DISEASE_SYMPTOM_ENRICHMENT_V7 = {
    "common-cold": {"dry-cough": 0.45},
    "asthma": {"dry-cough": 0.40},
    "acute-bronchitis": {"productive-cough": 0.82},
    "pneumonia": {"productive-cough": 0.52},
    "laryngitis": {"throat-clearing": 0.42},
    "allergic-rhinitis": {"throat-clearing": 0.30, "nasal-itching": 0.86},
    "gerd": {"throat-clearing": 0.28},
    "allergic-conjunctivitis": {"eye-itching": 0.92, "eyelid-swelling": 0.35},
    "blepharitis": {"eyelid-swelling": 0.48},
    "stye": {"eyelid-swelling": 0.72},
    "dry-eyes": {"dry-eye-feeling": 0.98},
    "otitis-externa": {"ear-itching": 0.72},
    "earwax-build-up": {"ear-pressure": 0.62},
    "ear-infection": {"ear-pressure": 0.48},
    "gum-disease": {"gum-pain": 0.62},
    "dental-abscess": {"gum-pain": 0.58},
    "mouth-ulcer-pattern": {"tongue-soreness": 0.45},
    "burning-mouth-syndrome-pattern": {"tongue-soreness": 0.38},
    "functional-dyspepsia-pattern": {"abdominal-fullness": 0.78, "post-meal-nausea": 0.58},
    "irritable-bowel-syndrome": {"abdominal-fullness": 0.35, "mucus-in-stool": 0.42, "bowel-urgency": 0.55},
    "gastritis": {"post-meal-nausea": 0.42},
    "viral-gastroenteritis": {"bowel-urgency": 0.42},
    "haemorrhoids": {"rectal-itching": 0.52},
    "osteoarthritis": {"hip-pain": 0.55, "ankle-pain": 0.28, "morning-joint-stiffness": 0.42, "knee-stiffness": 0.72},
    "bursitis": {"hip-pain": 0.52, "shoulder-night-pain": 0.62},
    "sprain-strain": {"ankle-pain": 0.62, "muscle-soreness": 0.55},
    "rheumatoid-arthritis": {"morning-joint-stiffness": 0.86},
    "influenza": {"muscle-soreness": 0.52},
    "temporomandibular-disorder": {"jaw-locking": 0.72},
    "contact-dermatitis": {"skin-redness": 0.62, "cracked-skin": 0.36},
    "cellulitis": {"skin-redness": 0.72},
    "atopic-eczema": {"cracked-skin": 0.68},
    "athletes-foot": {"cracked-skin": 0.45},
    "dandruff-pattern": {"scalp-redness": 0.48},
    "psoriasis": {"scalp-redness": 0.40},
    "insomnia-disorder": {"restless-sleep": 0.82},
    "obstructive-sleep-apnoea": {"restless-sleep": 0.35, "waking-unrefreshed": 0.78},
    "me-cfs": {"waking-unrefreshed": 0.52},
    "sciatica": {"radiating-leg-pain": 0.92},
    "common-knee-pain-pattern": {"knee-stiffness": 0.52},
    "peripheral-neuropathy": {"foot-burning": 0.82, "hand-weakness": 0.32},
    "carpal-tunnel-syndrome": {"hand-weakness": 0.52},
    "mechanical-neck-pain": {"neck-muscle-tightness": 0.78},
    "common-shoulder-pain-pattern": {"shoulder-night-pain": 0.42},
    "varicose-veins": {"calf-ache-standing": 0.68},
}

# No new source organizations or red-flag rules are introduced in this pack;
# all symptom-source links are inherited from the reviewed conditions above.
EXTRA_SOURCES_V7 = []
EXTRA_DISEASES_V7 = []
EXISTING_DISEASE_SOURCE_ENRICHMENT_V7 = {}
EXTRA_RED_RULES_V7 = []
EXTRA_RED_RULE_DETAILS_V7 = {}
