"""V191 health-search expansion with bilingual, source-backed common topics."""
REVIEW_DATE = "2026-10-01"


def src(source_name, organization, title, url):
    return {"name": f"{title} — {source_name}", "title": title, "organization": organization,
            "source_name": source_name, "url": url, "last_verified": REVIEW_DATE}


def topic(emoji, aliases, source, ar_title, ar_what, ar_causes, ar_worry, ar_doctor,
          en_title, en_what, en_causes, en_worry, en_doctor):
    return {
        "emoji": emoji, "category": "symptom", "aliases": aliases,
        "sources": [source], "last_reviewed": REVIEW_DATE,
        "population_scope": "general educational information; age, pregnancy, medicines, and medical history can change interpretation",
        "causes_label": {"ar": "أسباب أو سياقات محتملة", "en": "Possible causes or contexts"},
        "ar": {"title": ar_title, "what": ar_what, "causes": ar_causes, "worry": ar_worry, "doctor": ar_doctor},
        "en": {"title": en_title, "what": en_what, "causes": en_causes, "worry": en_worry, "doctor": en_doctor},
    }

MOH = "Saudi Ministry of Health"
NHS = "National Health Service"
AHA = "American Heart Association"
NIDDK = "National Institute of Diabetes and Digestive and Kidney Diseases"

EXTRA_SEARCH_KB_V7 = {
    "cold_intolerance": topic("🥶", ["حساسية للبرد","بردان طول الوقت","ما اتحمل البرد","cold intolerance","always cold"],
        src("Saudi MOH",MOH,"Hypothyroidism","https://www.moh.gov.sa/healthawareness/educationalcontent/diseases/endocrinology/pages/004.aspx"),
        "الحساسية للبرد", "الشعور بالبرد أكثر من المعتاد عرض غير نوعي وقد يظهر مع عوامل بيئية أو حالات صحية متعددة، ومنها قصور الغدة الدرقية.", ["الجو أو قلة الدهون بالجسم","فقر الدم أو نقص الحديد","قصور الغدة الدرقية أو أسباب أخرى"], "إذا ترافق مع تشوش شديد أو انخفاض واضح في الوعي أو تدهور سريع فاطلب تقييمًا عاجلًا.", "راجع الطبيب إذا كان جديدًا ومستمرًا أو ترافق مع تعب شديد أو تغير وزن أو أعراض أخرى.",
        "Cold intolerance", "Feeling unusually cold is non-specific and may occur with environmental factors or several health conditions, including hypothyroidism.", ["Environment or low body fat","Anemia or iron deficiency","Hypothyroidism or other causes"], "Marked confusion, reduced consciousness, or rapid deterioration needs urgent assessment.", "Seek medical review if it is new, persistent, or accompanied by significant fatigue, weight change, or other symptoms."),
    "heat_intolerance": topic("🌡️", ["حساسية للحرارة","ما اتحمل الحر","الحر يتعبني","heat intolerance","sensitive to heat"],
        src("Saudi MOH",MOH,"Hyperthyroidism","https://www.moh.gov.sa/healthawareness/educationalcontent/diseases/endocrinology/pages/006.aspx"),
        "الحساسية للحرارة", "عدم تحمل الحرارة قد يرتبط بالطقس والجفاف والأدوية أو حالات مثل فرط نشاط الغدة الدرقية، ولا يحدد السبب وحده.", ["الحر والجفاف","بعض الأدوية","فرط نشاط الغدة الدرقية أو أسباب أخرى"], "ارتباك شديد أو إغماء أو حرارة جسم شديدة مع التعرض للحر يستدعي الطوارئ.", "راجع الطبيب إذا تكرر دون سبب واضح أو ترافق مع خفقان أو نزول وزن أو تعرق ملحوظ.",
        "Heat intolerance", "Heat intolerance can relate to weather, dehydration, medicines, or conditions such as hyperthyroidism and does not identify a cause by itself.", ["Heat exposure and dehydration","Some medicines","Hyperthyroidism or other causes"], "Severe confusion, fainting, or very high body temperature after heat exposure is an emergency.", "Seek review if it recurs without a clear cause or comes with palpitations, weight loss, or marked sweating."),
    "orthopnea": topic("🫁", ["ضيق نفس عند الاستلقاء","اختناق لما انسدح","احتاج مخدات عشان اتنفس","orthopnea","breathless lying flat"],
        src("AHA",AHA,"Heart Failure Signs and Symptoms","https://www.heart.org/en/health-topics/heart-failure/warning-signs-of-heart-failure"),
        "ضيق التنفس عند الاستلقاء", "صعوبة التنفس التي تزيد عند الاستلقاء تستحق تقييمًا طبيًا لأنها قد ترتبط بحالات قلبية أو رئوية أو أسباب أخرى.", ["احتقان سوائل أو أسباب قلبية","حالات رئوية","أسباب أخرى تحتاج تقييمًا"], "إذا كان ضيق النفس شديدًا الآن أو ترافق مع ألم صدر شديد أو ازرقاق أو إغماء فاتصل بالطوارئ.", "رتّب تقييمًا طبيًا إذا كان العرض جديدًا أو متزايدًا، حتى لو تحسن عند الجلوس.",
        "Breathlessness when lying flat", "Breathing difficulty that worsens when lying flat deserves medical assessment because it can occur with cardiac, lung, or other conditions.", ["Fluid congestion or cardiac causes","Lung conditions","Other causes requiring assessment"], "Severe breathlessness now, severe chest pain, blue lips, or fainting requires emergency help.", "Arrange medical assessment if this is new or worsening, even if sitting up relieves it."),
    "ankle_swelling": topic("🦶", ["تورم الكاحلين","كواحيلي متورمة","انتفاخ الرجلين","ankle swelling","swollen ankles","leg swelling"],
        src("AHA",AHA,"Heart Failure Signs and Symptoms","https://www.heart.org/en/health-topics/heart-failure/warning-signs-of-heart-failure"),
        "تورم الكاحلين أو الساقين", "تورم الكاحلين أو الساقين قد ينتج عن الوقوف الطويل أو الأوردة أو الأدوية أو احتباس السوائل لأسباب قلبية أو كلوية وغيرها.", ["الوقوف الطويل أو مشاكل الأوردة","بعض الأدوية","احتباس السوائل لأسباب قلبية أو كلوية أو أخرى"], "تورم مفاجئ في ساق واحدة مع ألم أو ضيق نفس مفاجئ، أو تورم مع ضيق نفس شديد، يحتاج تقييمًا عاجلًا.", "راجع الطبيب إذا كان التورم جديدًا أو مستمرًا أو يزداد أو يصاحبه ضيق نفس.",
        "Ankle or leg swelling", "Ankle/leg swelling can result from prolonged standing, vein problems, medicines, or fluid retention from cardiac, kidney, or other causes.", ["Prolonged standing or vein problems","Some medicines","Fluid retention from cardiac, kidney, or other causes"], "Sudden one-sided painful swelling with sudden breathlessness, or swelling with severe breathlessness, needs urgent assessment.", "Seek medical review if swelling is new, persistent, worsening, or associated with breathlessness."),
    "foamy_urine": topic("🫧", ["بول رغوي","رغوة في البول","foamy urine","frothy urine"],
        src("NIDDK",NIDDK,"Chronic Kidney Disease","https://www.niddk.nih.gov/health-information/kidney-disease/chronic-kidney-disease-ckd/what-is-chronic-kidney-disease"),
        "البول الرغوي", "الرغوة قد تكون عابرة، لكن استمرارها قد يستدعي فحص البول ووظائف الكلى لأن البروتين في البول أحد الاحتمالات.", ["تدفق البول السريع أو رغوة عابرة","وجود بروتين في البول","أسباب بولية أو كلوية أخرى"], "قلة شديدة في البول مع تورم متزايد أو ضيق نفس شديد تحتاج تقييمًا سريعًا.", "راجع الطبيب إذا استمرت الرغوة أو ترافقت مع تورم أو ضغط أو سكري أو نتائج كلى غير طبيعية.",
        "Foamy urine", "Foam can be temporary, but persistent frothy urine may warrant urine and kidney testing because protein in urine is one possibility.", ["Fast urine stream or temporary foam","Protein in urine","Other urinary or kidney causes"], "Markedly reduced urine with increasing swelling or severe breathlessness needs prompt assessment.", "Seek review if foam persists or occurs with swelling, hypertension, diabetes, or abnormal kidney results."),
    "nighttime_urination": topic("🌙", ["اتبول كثير بالليل","اقوم للحمام بالليل","كثرة التبول ليلا","nocturia","urinating at night"],
        src("NIDDK",NIDDK,"Chronic Kidney Disease","https://www.niddk.nih.gov/health-information/kidney-disease/chronic-kidney-disease-ckd/what-is-chronic-kidney-disease"),
        "التبول المتكرر ليلًا", "الاستيقاظ المتكرر للتبول قد يرتبط بكمية السوائل أو أدوية أو مشكلات بولية أو اضطرابات نوم أو حالات صحية أخرى.", ["شرب سوائل متأخرًا","مدرات البول أو أدوية أخرى","أسباب بولية أو استقلابية أو كلوية أو نومية"], "عدم القدرة على التبول مع ألم شديد، أو تدهور عام شديد، يحتاج تقييمًا عاجلًا.", "راجع الطبيب إذا كان جديدًا ومستمرًا أو يؤثر على النوم أو ترافق مع عطش شديد أو تورم أو ألم بولي.",
        "Frequent nighttime urination", "Waking often to urinate may relate to fluid intake, medicines, urinary problems, sleep disorders, or other health conditions.", ["Late fluid intake","Diuretics or other medicines","Urinary, metabolic, kidney, or sleep-related causes"], "Inability to pass urine with severe pain or major systemic deterioration needs urgent assessment.", "Seek review if it is new, persistent, disrupts sleep, or comes with marked thirst, swelling, or urinary pain."),
    "pica": topic("🧊", ["اشتهي الثلج","اكل ثلج كثير","اشتهي التراب","pica","craving ice"],
        src("Saudi MOH",MOH,"Iron-deficiency anaemia","https://www.moh.gov.sa/healthawareness/educationalcontent/diseases/hematology/pages/0010.aspx"),
        "اشتهاء الثلج أو أشياء غير غذائية", "اشتهاء أشياء غير غذائية مثل الثلج أو التراب يسمى بيكا، وقد يرتبط أحيانًا بنقص الحديد لكنه لا يكفي للتشخيص.", ["نقص الحديد من الاحتمالات المعروفة","الحمل أو عوامل غذائية/سلوكية","أسباب أخرى"], "ابتلاع مواد سامة أو خطرة يستدعي طلب المساعدة الطبية فورًا.", "ناقش العرض مع الطبيب وخصوصًا إذا كان مستمرًا؛ قد يطلب فحوص الدم والحديد حسب السياق.",
        "Pica or craving ice/non-food items", "Craving non-food items such as ice or soil is called pica and can be associated with iron deficiency, but it is not diagnostic by itself.", ["Iron deficiency is one recognized association","Pregnancy or nutritional/behavioral factors","Other causes"], "Swallowing toxic or dangerous substances requires immediate medical help.", "Discuss persistent pica with a clinician; blood and iron tests may be considered based on context."),
}

EXTRA_SEARCH_KB_V7.update({
    "wheezing": topic("🫁", ["صفير الصدر","صفير بالتنفس","أزيز الصدر","wheezing","wheeze","whistling breathing"],
        src("MedlinePlus","U.S. National Library of Medicine","Wheezing","https://medlineplus.gov/ency/article/003070.htm"),
        "صفير أو أزيز أثناء التنفس", "الصفير صوت عالي النبرة أثناء التنفس وقد يظهر مع تضيق أو تهيج مجرى الهواء. لا يحدد السبب وحده، وقد يرتبط بالربو أو التهاب الشعب أو الحساسية أو أسباب تنفسية أخرى.", ["الربو أو تهيج مجرى الهواء","التهاب الشعب أو عدوى تنفسية","حساسية أو أسباب قلبية/تنفسية أخرى"], "الصفير الشديد أو المصحوب بضيق نفس شديد أو ازرقاق أو تشوش يحتاج مساعدة طبية عاجلة.", "راجع الطبيب إذا ظهر الصفير لأول مرة، أو تكرر دون تفسير، أو صاحبه ضيق نفس ملحوظ.",
        "Wheezing", "Wheezing is a high-pitched breathing sound that can occur when the airways are narrowed or irritated. It does not identify a cause by itself and can occur with asthma, bronchitis, allergy, or other respiratory conditions.", ["Asthma or airway irritation","Bronchitis or respiratory infection","Allergy or other cardiopulmonary causes"], "Severe wheezing or wheezing with severe breathlessness, blue skin/lips, or confusion needs urgent medical help.", "Seek medical review if wheezing is new, keeps recurring without explanation, or is accompanied by significant shortness of breath."),
})

# Additional high-frequency topics from NHS patient guidance.
EXTRA_SEARCH_KB_V7.update({
    "night_sweats": topic("🌙", ["تعرق ليلي","عرق كثير بالليل","اصحى مبلل عرق","night sweats","sweating at night"],
        src("NHS",NHS,"Night sweats","https://www.nhs.uk/symptoms/night-sweats/"),
        "التعرق الليلي", "التعرق أثناء النوم قد يحدث بسبب حرارة الغرفة أو عوامل مؤقتة، لكن التعرق الغزير المتكرر قد تكون له أسباب طبية متعددة.", ["حرارة الغرفة أو أغطية ثقيلة","القلق أو بعض الأدوية","عدوى أو تغيرات هرمونية أو أسباب أخرى"], "إذا ترافق مع تدهور شديد أو ضيق نفس شديد أو أعراض طارئة أخرى فاطلب المساعدة العاجلة.", "راجع الطبيب إذا كان يتكرر بانتظام ويوقظك أو يبلل الملابس/الفراش، أو ترافق مع حرارة أو نقص وزن غير مفسر.",
        "Night sweats", "Sweating during sleep can reflect room temperature or temporary factors, but recurrent drenching sweats can have many medical causes.", ["Warm room or heavy bedding","Anxiety or some medicines","Infection, hormonal changes, or other causes"], "Seek urgent help if it occurs with severe deterioration, severe breathlessness, or other emergency symptoms.", "See a clinician if it regularly wakes you or soaks clothes/bedding, or occurs with fever or unexplained weight loss."),
    "dysphagia": topic("🥤", ["صعوبة البلع","الاكل يعلق بحلقي","الأكل يعلق","dysphagia","difficulty swallowing","food gets stuck"],
        src("NHS",NHS,"Swallowing problems (dysphagia)","https://www.nhs.uk/symptoms/swallowing-problems-dysphagia/"),
        "صعوبة البلع", "صعوبة بلع الطعام أو السوائل قد تكون مؤقتة أو تحتاج تقييمًا لمعرفة السبب، خاصة إذا تكررت أو شعر الشخص بأن الطعام يعلق.", ["التهاب أو تهيج بالحلق أو المريء","ارتجاع أو اضطرابات حركة البلع","أسباب عصبية أو بنيوية أخرى"], "اختناق أو عدم القدرة على التنفس أو بلع اللعاب يستدعي الطوارئ فورًا.", "راجع الطبيب إذا تكررت صعوبة البلع أو نقص الوزن أو حدث سعال/اختناق متكرر مع الأكل.",
        "Difficulty swallowing", "Difficulty swallowing food or liquids may be temporary or need assessment, especially when recurrent or when food feels stuck.", ["Throat or oesophageal irritation","Reflux or swallowing-movement problems","Other neurological or structural causes"], "Choking, inability to breathe, or inability to swallow saliva requires emergency help now.", "Seek medical review for recurrent swallowing difficulty, weight loss, or repeated coughing/choking with meals."),
    "urinary_incontinence": topic("🚻", ["سلس بول","يتسرب البول","ما اقدر امسك البول","urinary incontinence","urine leakage","leaking urine"],
        src("NHS",NHS,"Urinary incontinence","https://www.nhs.uk/conditions/urinary-incontinence/symptoms/"),
        "تسرّب البول أو سلس البول", "تسرّب البول شائع وله أنماط وأسباب متعددة، مثل التسرب مع الكحة أو الضحك أو الحاجة المفاجئة الشديدة للتبول.", ["سلس إجهادي مع الكحة أو الجهد","فرط نشاط المثانة أو إلحاح البول","أدوية أو أسباب بولية/عصبية أخرى"], "فقدان التحكم بالبول فجأة مع ضعف أو خدر جديد بالساقين أو منطقة العجان وألم ظهر شديد يحتاج تقييمًا عاجلًا.", "راجع الطبيب إذا كان التسرب متكررًا أو جديدًا أو يؤثر على حياتك؛ توجد خيارات تقييم وعلاج متعددة.",
        "Urinary incontinence", "Urine leakage is common and has several patterns and causes, including leakage with coughing/exertion or a sudden strong urge to urinate.", ["Stress incontinence","Overactive bladder/urge incontinence","Medicines or other urinary/neurological causes"], "Sudden loss of bladder control with new leg/saddle weakness or numbness and severe back pain needs urgent assessment.", "Seek medical review if leakage is recurrent, new, or affects daily life; several assessment and treatment options exist."),
})
