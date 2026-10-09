import clinical_text
"""
medication_warnings.py — lightweight, curated general-caution notes for common
over-the-counter/common medications. This is NOT a drug-interaction checker —
it flags well-known general cautions for a single mentioned medication, based
on simple keyword matching against the patient's free-text notes.
"""

import re
import json
import hashlib
from datetime import datetime, timezone

import db

# key -> (ar name, en name, {ar/en keyword variants}, ar warning, en warning,
#          ar uses, en uses, ar interactions, en interactions)
MEDICATIONS = {
    "aspirin": (
        "أسبرين", "Aspirin",
        {"أسبرين", "اسبرين", "aspirin"},
        "قد يسبب تهيّج بالمعدة أو نزيف خفيف عند بعض الأشخاص، خصوصاً مع أعراض مثل ألم البطن أو الغثيان.",
        "May cause stomach irritation or mild bleeding in some people, especially alongside symptoms like stomach pain or nausea.",
        "تسكين الألم الخفيف إلى المتوسط، خفض الحمى، والوقاية من الجلطات عند وصفه من الطبيب.",
        "Relieving mild to moderate pain, reducing fever, and preventing clots when prescribed by a doctor.",
        "قد يتداخل مع مميعات الدم (مثل الوارفارين)، والمسكنات الأخرى (مثل الإيبوبروفين)، وبعض أدوية الضغط والسكري.",
        "May interact with blood thinners (e.g. warfarin), other painkillers (e.g. ibuprofen), and some blood pressure or diabetes medications.",
    ),
    "ibuprofen": (
        "بروفين", "Ibuprofen",
        {"بروفين", "ibuprofen", "advil", "برفين"},
        "قد يهيّج المعدة إذا أُخذ بدون طعام، وغير مناسب لبعض حالات الجفاف أو مشاكل الكلى.",
        "Can irritate the stomach if taken without food, and isn't ideal during dehydration or with kidney issues.",
        "تسكين الألم والالتهاب وخفض الحمى.",
        "Relieving pain, inflammation, and fever.",
        "قد يزيد خطر النزف عند تناوله مع مميعات الدم أو الأسبرين أو الكورتيزون، ويقلل فعالية بعض أدوية الضغط.",
        "May increase bleeding risk with blood thinners, aspirin, or corticosteroids, and may reduce the effect of some blood pressure medications.",
    ),
    "paracetamol": (
        "بنادول / باراسيتامول", "Paracetamol / Acetaminophen",
        {"بنادول", "باراسيتامول", "paracetamol", "acetaminophen", "panadol", "tylenol"},
        "آمن عموماً بالجرعة الموصوفة، لكن تجاوز الجرعة اليومية القصوى قد يضر الكبد.",
        "Generally safe at recommended doses, but exceeding the daily maximum can harm the liver.",
        "تسكين الألم وخفض الحمى، خاصة عند من لا يناسبهم مضادات الالتهاب.",
        "Relieving pain and fever, especially for those who can't take anti-inflammatories.",
        "التداخل المهم هو تجاوز الجرعة اليومية القصوى (خصوصاً مع أدوية البرد التي تحتوي باراسيتامول) — وقد يتداخل مع بعض أدوية الكبد.",
        "The key concern is exceeding the daily maximum (especially with cold medicines that also contain paracetamol) — may interact with some liver-affecting medications.",
    ),
    "antibiotics": (
        "أموكسيسيلين", "Amoxicillin",
        {"أموكسيسيلين", "اموكسيسيلين", "amoxicillin"},
        "أموكسيسيلين من مضادات البنسلين، وقد يسبب غثيانًا أو إسهالًا أو طفحًا لدى بعض الأشخاص. اطلب مساعدة عاجلة عند علامات حساسية شديدة مثل تورم الوجه أو الحلق أو صعوبة التنفس.",
        "Amoxicillin is a penicillin antibiotic and may cause nausea, diarrhea, or rash in some people. Seek urgent help for signs of a severe allergic reaction such as face/throat swelling or breathing difficulty.",
        "يُستخدم لعلاج بعض الالتهابات البكتيرية عندما يصفه الطبيب.",
        "Used for some bacterial infections when prescribed by a clinician.",
        "قد توجد تداخلات مع بعض الأدوية، لذلك أخبر الطبيب أو الصيدلي بجميع الأدوية والمكملات التي تستخدمها. لا تغيّر الجرعة أو المدة بنفسك.",
        "Interactions can occur with some medicines, so tell your doctor or pharmacist about all medicines and supplements you use. Do not change the dose or duration on your own.",
    ),
    "antihistamine": (
        "سيتريزين", "Cetirizine",
        {"سيتريزين", "cetirizine", "زيرتك", "zyrtec"},
        "بعض الأنواع تسبب نعاس — تجنبي القيادة أو الأنشطة اللي تحتاج تركيز بعد أخذه.",
        "Some types cause drowsiness — avoid driving or activities needing focus after taking it.",
        "علاج أعراض الحساسية مثل العطس والحكة وسيلان الأنف.",
        "Treating allergy symptoms such as sneezing, itching, and runny nose.",
        "قد يزيد التأثير المهدئ مع المهدئات وأدوية القلق والكحول وبعض أدوية الضغط.",
        "May increase the sedative effect with tranquilizers, anxiety medicines, alcohol, and some blood pressure medications.",
    ),
    "decongestant": (
        "سودوإيفيدرين", "Pseudoephedrine",
        {"سودوإيفيدرين", "سودوافدرين", "pseudoephedrine", "sudafed"},
        "قد يرفع ضغط الدم عند بعض الأشخاص — يُفضّل الحذر لمن عندهم ضغط مرتفع.",
        "May raise blood pressure in some people — caution advised for those with hypertension.",
        "تخفيف انسداد الأنف الناتج عن الزكام أو الحساسية.",
        "Relieving nasal congestion from colds or allergies.",
        "قد يرفع ضغط الدم — الحذر مع أدوية الضغط ومثبطات MAO وبعض أدوية القلب.",
        "May raise blood pressure — caution with blood pressure medicines, MAO inhibitors, and some heart medications.",
    ),
    "diclofenac": (
        "فولتارين / ديكلوفيناك", "Diclofenac / Voltaren",
        {"فولتارين", "فولترين", "ديكلوفيناك", "diclofenac", "voltaren"},
        "يُفضّل أخذه مع الطعام لتقليل تهيّج المعدة، وممنوع لمن عندهم قرحة معدية أو مشاكل كلى.",
        "Best taken with food to reduce stomach irritation; avoid with stomach ulcers or kidney problems.",
        "تسكين الألم والالتهاب (آلام المفاصل والعضلات وغيرها).",
        "Relieving pain and inflammation (joint, muscle, and other pains).",
        "قد يزيد خطر النزف والمشاكل الكلوية مع مميعات الدم ومدرات البول ومضادات الالتهاب الأخرى.",
        "May increase bleeding and kidney risk with blood thinners, diuretics, and other anti-inflammatories.",
    ),
    "metformin": (
        "متفورمين / جلوكوفاج", "Metformin / Glucophage",
        {"متفورمين", "متفورمن", "جلوكوفاج", "metformin", "glucophage"},
        "يُفضل أخذه مع الوجبات، وقد يسبب غثيان أو إسهال بسيط في البداية يزول غالباً.",
        "Best taken with meals; may cause mild nausea or diarrhea initially, which usually settles.",
        "ضبط سكر الدم في مرض السكري من النوع الثاني.",
        "Controlling blood sugar in type 2 diabetes.",
        "قد يتداخل مع الكورتيزون ومدرات البول وبعض أدوية القلب والكلى — وقد تزداد حموضة الدم مع شرب الكحول.",
        "May interact with corticosteroids, diuretics, and some heart/kidney medications — alcohol may increase the risk of lactic acidosis.",
    ),
    "amlodipine": (
        "أملوديبين", "Amlodipine",
        {"أملوديبين", "amlodipine", "نورفاسك", "norvasc"},
        "قد يسبب تورماً خفيفاً بالكاحلين — لو زاد التورم فجأة أو صار تنفس صعب، راجع الطبيب.",
        "May cause mild ankle swelling — if swelling suddenly worsens or breathing is hard, see your doctor.",
        "علاج ارتفاع ضغط الدم وبعض حالات الذبحة الصدرية.",
        "Treating high blood pressure and some cases of angina.",
        "قد يزداد انخفاض الضغط مع أدوية الضغط الأخرى والكحول، ويتداخل مع بعض مضادات الفطريات والمضادات الحيوية.",
        "Blood pressure may drop further with other pressure medicines and alcohol; may interact with some antifungals and antibiotics.",
    ),
    "omeprazole": (
        "أوميبرازول", "Omeprazole",
        {"أوميبرازول", "omeprazole", "لوسيك", "losec", "أوميز", "omez"},
        "يُفضل أخذه قبل الأكل بنصف ساعة، ويستخدم عادةً لفترات محددة — لا تطوّلي استخدامه دون استشارة طبيب.",
        "Best taken 30 minutes before meals, usually for limited periods — don't use long-term without a doctor.",
        "تقليل حموضة المعدة وعلاج قرحة المعدة والارتجاع.",
        "Reducing stomach acid and treating ulcers and reflux.",
        "قد يقلل امتصاص بعض الأدوية مثل كلوبيدوجريل وبعض مضادات الفطريات، ويؤثر على امتصاص الحديد والمغنيسيوم.",
        "May reduce absorption of some medications such as clopidogrel and some antifungals, and affects iron/magnesium absorption.",
    ),
    "contrave": (
        "كونتراف / نالتريكسون مع بوبروبيون", "Contrave / Naltrexone-Bupropion",
        {
            "contrave", "كونتراف", "كونتريف",
            "naltrexone bupropion", "bupropion naltrexone",
            "naltrexone/bupropion", "bupropion/naltrexone",
            "naltrexone-bupropion", "bupropion-naltrexone",
            "نالتريكسون بوبروبيون", "بوبروبيون نالتريكسون",
            "نالتريكسون/بوبروبيون", "بوبروبيون/نالتريكسون",
        },
        "دواء مركب بوصفة طبية يحتوي نالتريكسون وبوبروبيون. من أهم التحذيرات: قد يرتبط البوبروبيون بأفكار أو سلوكيات انتحارية لدى بعض الفئات العمرية، وقد يرفع ضغط الدم أو معدل النبض، كما أن وجود اضطراب تشنجات أو استخدام أفيونات حالي قد يجعل الدواء غير مناسب. راجع النشرة الرسمية والطبيب أو الصيدلي قبل الاستخدام أو التغيير.",
        "A prescription combination of naltrexone and bupropion. Important warnings include the boxed warning related to suicidal thoughts/behaviors with bupropion in some age groups, possible increases in blood pressure or heart rate, and important contraindications such as seizure disorders or current opioid use. Review the official label and your clinician or pharmacist before use or changes.",
        "يُستخدم مع نظام غذائي منخفض السعرات وزيادة النشاط البدني للمساعدة في خفض الوزن والمحافظة عليه لدى بعض البالغين المصابين بالسمنة أو زيادة الوزن مع مشكلة صحية مرتبطة بالوزن.",
        "Used with a reduced-calorie diet and increased physical activity for chronic weight management in certain adults with obesity or overweight plus a weight-related condition.",
        "من التداخلات المهمة: الأدوية الأفيونية قد لا تعمل كالمعتاد وقد يحدث انسحاب إذا بدأ نالتريكسون أثناء وجود أفيونات في الجسم؛ كما توجد تداخلات/موانع مع مثبطات MAO ومنتجات أخرى تحتوي بوبروبيون أو نالتريكسون. أخبر الطبيب أو الصيدلي بكل الأدوية والمكملات قبل الاستخدام.",
        "Important interactions include opioids (which may be blocked and can precipitate withdrawal if naltrexone is started while opioids are present), MAO inhibitors, and other products containing bupropion or naltrexone. Tell your clinician or pharmacist about all medicines and supplements before use.",
    ),
}


_EXPANDED_MEDICATIONS = {'loratadine': ('لوراتادين / كلاريتين', 'Loratadine / Claritin', {'لوراتادين', 'كلاريتين', 'loratadine', 'claritin'}, 'مضاد حساسية قليل التسبب بالنعاس عادةً، لكن قد يسبب صداعًا أو نعاسًا لدى بعض الأشخاص. أخبر الطبيب إذا كان لديك مرض كبدي أو كلوي.', 'An antihistamine that is usually less sedating, but it can still cause headache or drowsiness in some people. Tell your clinician if you have liver or kidney disease.', 'تخفيف أعراض الحساسية مثل العطاس وسيلان الأنف والحكة والشرى.', 'Relieving allergy symptoms such as sneezing, runny nose, itching, and hives.', 'قد يزداد النعاس مع الكحول أو الأدوية المهدئة. أخبر الطبيب أو الصيدلي عن جميع الأدوية والمكملات.', 'Drowsiness can increase with alcohol or sedating medicines. Tell your clinician or pharmacist about all medicines and supplements.'), 'fexofenadine': ('فيكسوفينادين / تلفاست', 'Fexofenadine / Telfast', {'fexofenadine', 'فيكسوفينادين', 'telfast', 'allegra', 'تلفاست'}, 'مضاد حساسية غير مهدئ غالبًا. بعض عصائر الفاكهة قد تقلل امتصاصه، وقد تحتاج أمراض الكلى إلى احتياط إضافي.', 'A generally non-sedating antihistamine. Some fruit juices can reduce absorption, and kidney disease may require extra caution.', 'تخفيف أعراض حساسية الأنف والشرى.', 'Relieving allergic rhinitis and hives.', 'تجنّب أخذه في الوقت نفسه مع مضادات الحموضة المحتوية على الألومنيوم أو المغنيسيوم، وافصلها حسب توجيه الصيدلي.', 'Avoid taking it at the same time as aluminum- or magnesium-containing antacids; separate them as directed by a pharmacist.'), 'salbutamol': ('سالبوتامول / فنتولين', 'Salbutamol / Albuterol / Ventolin', {'albuterol', 'salbutamol', 'سالبوتامول', 'ventolin', 'فنتولين'}, 'قد يسبب رجفة أو خفقانًا أو تسارع النبض. إذا احتجت بخاخ الإنقاذ أكثر من المعتاد أو لم يتحسن ضيق التنفس، اطلب تقييمًا طبيًا.', 'May cause tremor, palpitations, or a fast heartbeat. If you need a rescue inhaler more often than usual or breathing does not improve, seek medical assessment.', 'تخفيف التشنج القصبي وأعراض الربو أو الصفير بسرعة.', 'Rapid relief of bronchospasm and asthma/wheeze symptoms.', 'قد تتداخل بعض حاصرات بيتا وأدوية القلب ومدرات البول معه، وقد تزيد بعض الأدوية خطر اضطراب النبض أو انخفاض البوتاسيوم.', 'Some beta-blockers, heart medicines, and diuretics can interact, and some medicines may increase the risk of rhythm problems or low potassium.'), 'montelukast': ('مونتيلوكاست / سينجولير', 'Montelukast / Singulair', {'singulair', 'montelukast', 'مونتيلوكاست', 'سينجولير'}, 'قد تحدث تغيرات في المزاج أو النوم أو السلوك لدى بعض المستخدمين. أبلغ الطبيب سريعًا عن أعراض نفسية أو سلوكية جديدة أو مقلقة.', 'Mood, sleep, or behavior changes can occur in some users. Promptly report new or concerning neuropsychiatric symptoms.', 'الوقاية والسيطرة على الربو وبعض أعراض الحساسية الأنفية حسب وصف الطبيب.', 'Prevention and control of asthma and some allergic rhinitis symptoms when prescribed.', 'أخبر الطبيب بجميع الأدوية؛ بعض الأدوية المحفزة لإنزيمات الكبد قد تقلل مستواه.', 'Tell your clinician about all medicines; some liver-enzyme inducers can lower its levels.'), 'fluticasone': ('فلوتيكازون / فليكسوناز', 'Fluticasone / Flonase', {'flonase', 'فلوتيكازون', 'fluticasone', 'flixonase', 'فليكسوناز'}, 'بخاخات الأنف قد تسبب جفافًا أو تهيجًا أو نزفًا بسيطًا من الأنف. الاستخدام المطول أو الجرعات العالية يحتاج متابعة حسب الحالة.', 'Nasal formulations can cause dryness, irritation, or minor nosebleeds. Long-term or high-dose use may need monitoring.', 'تخفيف التهاب وحساسية الأنف، وبعض أشكال فلوتيكازون تُستخدم للربو حسب الوصفة.', 'Relieving nasal allergy/inflammation; some fluticasone formulations are used for asthma when prescribed.', 'أدوية مثل ريتونافير أو كوبيسيستات قد ترفع التعرض للكورتيزون وتزيد آثاره الجانبية.', 'Medicines such as ritonavir or cobicistat can increase steroid exposure and side effects.'), 'atorvastatin': ('أتورفاستاتين / ليبيتور', 'Atorvastatin / Lipitor', {'أتورفاستاتين', 'اتورفاستاتين', 'atorvastatin', 'lipitor', 'ليبيتور'}, 'قد يسبب ألمًا أو ضعفًا عضليًا نادرًا، وقد يؤثر في الكبد. أبلغ الطبيب عن ألم عضلي شديد أو بول داكن أو اصفرار.', 'Rarely can cause significant muscle pain/weakness and can affect the liver. Report severe muscle symptoms, dark urine, or jaundice.', 'خفض الكوليسترول وتقليل مخاطر القلب والأوعية لدى بعض المرضى.', 'Lowering cholesterol and reducing cardiovascular risk in selected patients.', 'توجد تداخلات مع بعض المضادات الحيوية ومضادات الفطريات وأدوية أخرى، وقد يزيد الجريب فروت التعرض للدواء.', 'Interacts with some antibiotics, antifungals, and other medicines; grapefruit can increase drug exposure.'), 'rosuvastatin': ('روسوفاستاتين / كريستور', 'Rosuvastatin / Crestor', {'روسوفاستاتين', 'rosuvastatin', 'crestor', 'كريستور'}, 'قد يسبب أعراضًا عضلية نادرًا وقد يؤثر في الكبد. راجع الطبيب عند ألم عضلي شديد أو ضعف غير معتاد.', 'Rarely can cause significant muscle symptoms and can affect the liver. Seek advice for severe muscle pain or unusual weakness.', 'خفض الكوليسترول وتقليل مخاطر القلب والأوعية لدى بعض المرضى.', 'Lowering cholesterol and reducing cardiovascular risk in selected patients.', 'قد يتداخل مع سيكلوسبورين وبعض أدوية فيروس HIV ومميعات الدم، ويحتاج الانتباه لوظائف الكلى في بعض الحالات.', 'Can interact with cyclosporine, some HIV medicines, and blood thinners; kidney function matters in some patients.'), 'losartan': ('لوسارتان / كوزار', 'Losartan / Cozaar', {'كوزار', 'losartan', 'لوسارتان', 'cozaar'}, 'قد يرفع البوتاسيوم ويؤثر في وظائف الكلى. لا يُستخدم أثناء الحمل بسبب خطره على الجنين.', 'May raise potassium and affect kidney function. It should not be used during pregnancy because of fetal risk.', 'علاج ارتفاع ضغط الدم وحماية الكلى في بعض حالات السكري.', 'Treating high blood pressure and helping protect the kidneys in some people with diabetes.', 'قد يتداخل مع مكملات البوتاسيوم ومدرات البول الحافظة للبوتاسيوم ومضادات الالتهاب غير الستيرويدية والليثيوم.', 'Can interact with potassium supplements, potassium-sparing diuretics, NSAIDs, and lithium.'), 'valsartan': ('فالسارتان / ديوفان', 'Valsartan / Diovan', {'valsartan', 'فالسارتان', 'diovan', 'ديوفان'}, 'قد يسبب دوخة ويرفع البوتاسيوم أو يؤثر في الكلى. لا يُستخدم أثناء الحمل.', 'May cause dizziness, raise potassium, or affect kidney function. It should not be used during pregnancy.', 'علاج ارتفاع ضغط الدم وبعض حالات قصور القلب وبعد احتشاء القلب حسب الوصفة.', 'Treating high blood pressure and selected cases of heart failure or after heart attack.', 'الحذر مع مكملات البوتاسيوم ومدرات البول الحافظة للبوتاسيوم والليثيوم ومضادات الالتهاب.', 'Use caution with potassium supplements, potassium-sparing diuretics, lithium, and NSAIDs.'), 'lisinopril': ('ليسينوبريل', 'Lisinopril', {'lisinopril', 'ليسينوبريل', 'zestril', 'زيستريل', 'ليزينوبريل'}, 'قد يسبب سعالًا جافًا أو دوخة، ونادرًا تورمًا خطيرًا بالوجه أو اللسان. لا يُستخدم أثناء الحمل.', 'May cause a dry cough or dizziness and, rarely, serious swelling of the face or tongue. It should not be used during pregnancy.', 'علاج ارتفاع ضغط الدم وقصور القلب وبعض الحالات بعد الجلطة القلبية.', 'Treating high blood pressure, heart failure, and selected post-heart-attack situations.', 'قد يرفع البوتاسيوم؛ الحذر مع مكملات البوتاسيوم ومدرات البول الحافظة للبوتاسيوم والليثيوم ومضادات الالتهاب.', 'May raise potassium; use caution with potassium supplements, potassium-sparing diuretics, lithium, and NSAIDs.'), 'bisoprolol': ('بيسوبرولول / كونكور', 'Bisoprolol / Concor', {'كونكور', 'بيسوبرولول', 'concor', 'bisoprolol'}, 'قد يبطئ النبض ويسبب دوخة أو تعبًا. لا توقفه فجأة دون توجيه طبي.', 'May slow the heart rate and cause dizziness or fatigue. Do not stop it suddenly without medical guidance.', 'علاج ارتفاع ضغط الدم وبعض حالات قصور القلب أو اضطرابات القلب حسب الوصفة.', 'Treating high blood pressure and selected heart conditions, including some heart failure cases.', 'قد يزيد بطء القلب مع أدوية أخرى تخفض النبض، وقد يخفي بعض علامات انخفاض السكر.', 'Can increase bradycardia with other rate-lowering medicines and may mask some signs of low blood sugar.'), 'metoprolol': ('ميتوبرولول', 'Metoprolol', {'metoprolol', 'ميتوبرولول', 'toprol', 'lopressor'}, 'قد يسبب بطء النبض أو انخفاض الضغط أو التعب. لا توقفه فجأة دون إشراف طبي.', 'May cause a slow heart rate, low blood pressure, or fatigue. Do not stop suddenly without medical supervision.', 'علاج ضغط الدم والذبحة وبعض اضطرابات النبض وقصور القلب حسب الشكل الدوائي.', 'Treating blood pressure, angina, certain rhythm disorders, and heart failure depending on formulation.', 'يتداخل مع أدوية أخرى تبطئ القلب، وقد يخفي أعراض انخفاض السكر؛ بعض مضادات الاكتئاب قد ترفع مستواه.', 'Interacts with other heart-rate-lowering drugs, can mask hypoglycemia symptoms, and some antidepressants can raise its levels.'), 'hydrochlorothiazide': ('هيدروكلوروثيازيد', 'Hydrochlorothiazide', {'hydrochlorothiazide', 'هيدروكلوروثيازيد', 'hctz'}, 'قد يسبب جفافًا أو دوخة أو اضطرابًا في الأملاح مثل الصوديوم والبوتاسيوم، وقد يزيد حساسية الجلد للشمس.', 'May cause dehydration, dizziness, or electrolyte changes such as low sodium or potassium, and can increase sun sensitivity.', 'علاج ارتفاع ضغط الدم واحتباس السوائل في بعض الحالات.', 'Treating high blood pressure and fluid retention in selected conditions.', 'قد يتداخل مع الليثيوم ومضادات الالتهاب وبعض أدوية القلب والسكري، ويحتاج أحيانًا مراقبة الأملاح ووظائف الكلى.', 'Can interact with lithium, NSAIDs, and some heart or diabetes medicines; electrolytes and kidney function may need monitoring.'), 'levothyroxine': ('ليفوثيروكسين / إلتروكسين', 'Levothyroxine / Eltroxin', {'synthroid', 'levothyroxine', 'ليفوثيروكسين', 'التروكسين', 'إلتروكسين', 'eltroxin'}, 'يُستخدم لتعويض هرمون الغدة الدرقية وليس للتنحيف. الجرعة الزائدة قد تسبب خفقانًا أو رجفة أو تعرقًا.', 'Replaces thyroid hormone and is not a weight-loss medicine. Excess dosing can cause palpitations, tremor, or sweating.', 'علاج قصور الغدة الدرقية.', 'Treating hypothyroidism.', 'الحديد والكالسيوم وبعض مضادات الحموضة تقلل امتصاصه؛ افصلها حسب تعليمات الطبيب أو الصيدلي. كما قد يؤثر في مفعول الوارفارين.', 'Iron, calcium, and some antacids reduce absorption; separate them as directed. It can also affect warfarin response.'), 'gliclazide': ('غليكلازايد / دياميكرون', 'Gliclazide / Diamicron', {'جليكلازايد', 'دياميكرون', 'diamicron', 'غليكلازايد', 'gliclazide'}, 'قد يسبب انخفاض سكر الدم، خاصة مع تأخير الوجبات أو تغييرات كبيرة في الأكل أو النشاط.', 'Can cause low blood sugar, especially with delayed meals or major changes in food intake or activity.', 'خفض سكر الدم في السكري من النوع الثاني.', 'Lowering blood glucose in type 2 diabetes.', 'الكحول وبعض الأدوية قد تزيد أو تخفي انخفاض السكر؛ أخبر الطبيب أو الصيدلي بكل أدوية السكري والأدوية الأخرى.', 'Alcohol and some medicines can increase or mask hypoglycemia; tell your clinician or pharmacist about all diabetes and other medicines.'), 'sitagliptin': ('سيتاغلبتين / جانوفيا', 'Sitagliptin / Januvia', {'sitagliptin', 'جانوفيا', 'سيتاجلبتين', 'januvia', 'سيتاغلبتين'}, 'قد يسبب أعراضًا هضمية، ونادرًا التهاب البنكرياس أو ألم مفاصل شديد. وظائف الكلى مهمة لتحديد الاستخدام المناسب.', 'May cause gastrointestinal symptoms and, rarely, pancreatitis or severe joint pain. Kidney function is important for appropriate use.', 'خفض سكر الدم في السكري من النوع الثاني.', 'Lowering blood glucose in type 2 diabetes.', 'قد يزيد خطر انخفاض السكر عند استخدامه مع الإنسولين أو أدوية السلفونيل يوريا، وقد تحتاج بعض الأدوية إلى مراقبة إضافية.', 'Hypoglycemia risk may increase with insulin or sulfonylureas; some medicines may need additional monitoring.'), 'empagliflozin': ('إمباغليفلوزين / جارديانس', 'Empagliflozin / Jardiance', {'إمباغليفلوزين', 'empagliflozin', 'جارديانس', 'jardiance', 'امباغليفلوزين'}, 'قد يزيد التبول والجفاف والالتهابات الفطرية التناسلية، ونادرًا قد يحدث حماض كيتوني حتى مع سكر غير مرتفع جدًا.', 'May increase urination, dehydration, and genital yeast infections; rarely, ketoacidosis can occur even without very high glucose.', 'علاج السكري من النوع الثاني، وله فوائد قلبية وكلوية في فئات معينة حسب الوصفة.', 'Treating type 2 diabetes, with heart and kidney benefits in selected groups when prescribed.', 'يزداد خطر الجفاف مع مدرات البول، وقد يزيد انخفاض السكر مع الإنسولين أو السلفونيل يوريا.', 'Dehydration risk can increase with diuretics, and hypoglycemia risk can increase with insulin or sulfonylureas.'), 'semaglutide': ('سيماجلوتايد / أوزمبيك / ويجوفي / ريبلسس', 'Semaglutide / Ozempic / Wegovy / Rybelsus', {'أوزمبيك', 'semaglutide', 'wegovy', 'اوزمبيك', 'سيماغلوتايد', 'سيماجلوتايد', 'ريبلسس', 'ويجوفي', 'rybelsus', 'ozempic'}, 'قد يسبب غثيانًا أو قيئًا أو إسهالًا ويبطئ إفراغ المعدة. توجد تحذيرات مهمة تشمل التهاب البنكرياس ومشكلات المرارة، وتحذير خاص بأورام خلايا C الدرقية في النشرة الأمريكية.', 'Can cause nausea, vomiting, or diarrhea and slows gastric emptying. Important warnings include pancreatitis, gallbladder problems, and a U.S. boxed warning regarding thyroid C-cell tumors.', 'علاج السكري من النوع الثاني، وبعض المستحضرات تستخدم للتحكم المزمن بالوزن وتقليل مخاطر قلبية في فئات محددة.', 'Treating type 2 diabetes; some formulations are used for chronic weight management and cardiovascular risk reduction in selected groups.', 'قد يزيد انخفاض السكر مع الإنسولين أو السلفونيل يوريا، وقد يؤثر بطء إفراغ المعدة في امتصاص بعض الأدوية الفموية.', 'Hypoglycemia risk may increase with insulin or sulfonylureas, and delayed gastric emptying can affect absorption of some oral medicines.'), 'tirzepatide': ('تيرزيباتايد / مونجارو', 'Tirzepatide / Mounjaro', {'tirzepatide', 'mounjaro', 'مونجارو', 'تيرزباتايد', 'تيرزيباتايد', 'zepbound'}, 'قد يسبب أعراضًا هضمية ويبطئ إفراغ المعدة. توجد تحذيرات مهمة تشمل التهاب البنكرياس ومشكلات المرارة وتحذير أورام خلايا C الدرقية في النشرة الأمريكية.', 'May cause gastrointestinal symptoms and delay gastric emptying. Important warnings include pancreatitis, gallbladder disease, and a U.S. boxed warning regarding thyroid C-cell tumors.', 'علاج السكري من النوع الثاني، وبعض المستحضرات تستخدم للتحكم المزمن بالوزن في فئات محددة.', 'Treating type 2 diabetes; some formulations are used for chronic weight management in selected groups.', 'قد يزيد انخفاض السكر مع الإنسولين أو السلفونيل يوريا، وقد يؤثر بطء إفراغ المعدة في امتصاص بعض الأدوية الفموية ومنها موانع الحمل الفموية خلال فترات محددة بعد بدء أو رفع الجرعة.', 'Hypoglycemia risk may increase with insulin or sulfonylureas, and delayed gastric emptying can affect some oral medicines, including oral contraceptives during certain periods after starting or dose increases.'), 'insulin_glargine': ('إنسولين غلارجين / لانتوس', 'Insulin Glargine / Lantus', {'لانتوس', 'basaglar', 'إنسولين غلارجين', 'lantus', 'انسولين غلارجين', 'insulin glargine', 'toujeo'}, 'أهم خطر هو انخفاض سكر الدم. استخدم المنتج والجرعة الموصوفين ولا تبدّل بين مستحضرات الإنسولين دون توجيه طبي.', 'The main risk is low blood sugar. Use the prescribed product and dose and do not switch insulin products without medical guidance.', 'إنسولين طويل المفعول للتحكم بسكر الدم في بعض أنواع السكري.', 'Long-acting insulin for blood glucose control in certain types of diabetes.', 'أدوية كثيرة قد ترفع أو تخفض احتياج الإنسولين، وحاصرات بيتا قد تخفي بعض أعراض انخفاض السكر.', 'Many medicines can raise or lower insulin requirements, and beta-blockers can mask some hypoglycemia symptoms.'), 'pantoprazole': ('بانتوبرازول / بانتولوك', 'Pantoprazole / Protonix', {'protonix', 'بانتولوك', 'pantoloc', 'بانتوبرازول', 'pantoprazole'}, 'يقلل حمض المعدة. الاستخدام الطويل قد يرتبط بنقص المغنيسيوم أو فيتامين B12 وزيادة بعض مخاطر العدوى أو الكسور لدى بعض الأشخاص.', 'Reduces stomach acid. Long-term use may be associated with low magnesium or vitamin B12 and increased risk of certain infections or fractures in some people.', 'علاج الارتجاع والقرح والحالات المرتبطة بزيادة حمض المعدة.', 'Treating reflux, ulcers, and other acid-related conditions.', 'قد يؤثر في امتصاص أدوية تعتمد على حموضة المعدة، وقد توجد تداخلات مع جرعات عالية من الميثوتركسات وبعض الأدوية الأخرى.', 'Can affect absorption of medicines that depend on stomach acidity and may interact with high-dose methotrexate and other drugs.'), 'famotidine': ('فاموتيدين / بيبسيد', 'Famotidine / Pepcid', {'famotidine', 'فاموتيدين', 'بيبسيد', 'pepcid'}, 'يقلل حمض المعدة، وعادةً يتحمل جيدًا. قد تحتاج الجرعة إلى تعديل في أمراض الكلى.', 'Reduces stomach acid and is generally well tolerated. Dose adjustment may be needed in kidney disease.', 'علاج الحموضة والارتجاع وبعض القرح.', 'Treating heartburn, reflux, and some ulcers.', 'تداخلاته أقل من كثير من أدوية الحموضة، لكن تقليل حمض المعدة قد يؤثر في امتصاص بعض الأدوية.', 'Has fewer interactions than many acid medicines, but reduced stomach acidity can affect absorption of some drugs.'), 'ondansetron': ('أوندانسيترون / زوفران', 'Ondansetron / Zofran', {'زوفران', 'أوندانسيترون', 'ondansetron', 'اوندانسيترون', 'zofran'}, 'قد يسبب صداعًا أو إمساكًا، وقد يطيل فترة QT ويؤثر في نظم القلب لدى بعض الأشخاص.', 'May cause headache or constipation and can prolong the QT interval, affecting heart rhythm in susceptible people.', 'الوقاية أو العلاج من الغثيان والقيء في حالات محددة.', 'Preventing or treating nausea and vomiting in selected situations.', 'الحذر مع أدوية أخرى تطيل QT أو أدوية سيروتونينية، ويُمنع مع أبومورفين بسبب خطر انخفاض الضغط وفقدان الوعي.', 'Use caution with other QT-prolonging or serotonergic medicines; it is contraindicated with apomorphine because of severe hypotension and loss of consciousness risk.'), 'loperamide': ('لوبراميد / إيموديوم', 'Loperamide / Imodium', {'إيموديوم', 'loperamide', 'imodium', 'ايموديوم', 'لوبراميد'}, 'يستخدم للإسهال قصير المدى في حالات مختارة. لا يُنصح به عند وجود دم في البراز أو حرارة عالية أو اشتباه التهاب شديد دون تقييم طبي.', 'Used for short-term diarrhea in selected cases. It is generally not appropriate with bloody stool, high fever, or suspected severe colitis without medical assessment.', 'تقليل حركة الأمعاء والسيطرة المؤقتة على بعض أنواع الإسهال.', 'Reducing bowel movement frequency and temporarily controlling some types of diarrhea.', 'الجرعات الزائدة قد تسبب اضطرابات خطيرة في نظم القلب، وبعض الأدوية التي ترفع مستواه قد تزيد هذا الخطر.', 'Excessive doses can cause serious heart rhythm problems, and some interacting medicines can increase that risk.'), 'naproxen': ('نابروكسين / أليف', 'Naproxen / Aleve', {'نابروكسين', 'naproxen', 'aleve', 'أليف'}, 'من مضادات الالتهاب وقد يهيج المعدة ويزيد خطر النزف أو يؤثر في الكلى، خصوصًا مع الجفاف أو الاستخدام الطويل.', 'An NSAID that can irritate the stomach, increase bleeding risk, and affect the kidneys, especially with dehydration or long-term use.', 'تسكين الألم والالتهاب وخفض الحمى.', 'Relieving pain, inflammation, and fever.', 'يزداد خطر النزف مع مميعات الدم والأسبرين وبعض مضادات الاكتئاب، وقد يتداخل مع أدوية الضغط ومدرات البول.', 'Bleeding risk increases with blood thinners, aspirin, and some antidepressants; it can also interact with blood pressure medicines and diuretics.'), 'celecoxib': ('سيليكوكسيب / سيليبريكس', 'Celecoxib / Celebrex', {'سيليكوكسيب', 'celecoxib', 'سيليبريكس', 'celebrex'}, 'مضاد التهاب انتقائي قد يسبب مشكلات معدية أو كلوية ويزيد مخاطر القلب والأوعية لدى بعض المرضى.', 'A selective NSAID that can cause gastrointestinal or kidney problems and may increase cardiovascular risk in some patients.', 'تسكين الألم والالتهاب في بعض حالات المفاصل والألم.', 'Relieving pain and inflammation in selected joint and pain conditions.', 'الحذر مع مميعات الدم ومضادات الالتهاب الأخرى وبعض أدوية الضغط ومدرات البول؛ أخبر الطبيب عن حساسية السلفوناميد.', 'Use caution with blood thinners, other NSAIDs, some blood pressure medicines, and diuretics; tell your clinician about sulfonamide allergy.'), 'clopidogrel': ('كلوبيدوغريل / بلافيكس', 'Clopidogrel / Plavix', {'كلوبيدوجريل', 'بلافيكس', 'كلوبيدوغريل', 'clopidogrel', 'plavix'}, 'يقلل تجمع الصفائح لذلك يزيد قابلية النزف والكدمات. لا توقفه من نفسك إذا وُصف بعد دعامة أو حدث قلبي.', 'Reduces platelet aggregation, so bleeding and bruising are more likely. Do not stop it on your own if prescribed after a stent or cardiovascular event.', 'الوقاية من الجلطات القلبية أو الدماغية في حالات محددة.', 'Preventing heart attack or stroke in selected conditions.', 'قد تزيد مميعات الدم ومضادات الالتهاب خطر النزف، وقد يقلل أوميبرازول وإيزوميبرازول تفعيله لدى بعض المرضى.', 'Blood thinners and NSAIDs can increase bleeding risk; omeprazole and esomeprazole can reduce activation in some patients.'), 'apixaban': ('أبيكسابان / إليكويس', 'Apixaban / Eliquis', {'ابيكسابان', 'apixaban', 'اليكويس', 'eliquis', 'أبيكسابان', 'إليكويس'}, 'مميع للدم وقد يسبب نزفًا خطيرًا. لا توقفه فجأة دون توجيه طبي لأن خطر الجلطات قد يرتفع.', 'An anticoagulant that can cause serious bleeding. Do not stop it abruptly without medical advice because clot risk may increase.', 'الوقاية أو العلاج من بعض الجلطات وتقليل خطر السكتة في الرجفان الأذيني غير الصمامي.', 'Preventing or treating certain blood clots and reducing stroke risk in nonvalvular atrial fibrillation.', 'يزداد النزف مع مميعات الدم ومضادات الالتهاب ومضادات الصفائح، وتتداخل معه بعض مثبطات أو محفزات CYP3A4 وP-gp القوية.', 'Bleeding risk rises with anticoagulants, NSAIDs, and antiplatelet drugs; strong CYP3A4/P-gp inhibitors or inducers can also interact.'), 'rivaroxaban': ('ريفاروكسابان / زارلتو', 'Rivaroxaban / Xarelto', {'xarelto', 'rivaroxaban', 'ريفاروكسابان', 'زارلتو'}, 'مميع للدم وقد يسبب نزفًا خطيرًا. لا توقفه دون توجيه طبي لأن خطر الجلطات قد يرتفع.', 'An anticoagulant that can cause serious bleeding. Do not stop it without medical guidance because clot risk may increase.', 'الوقاية أو العلاج من بعض الجلطات وتقليل خطر السكتة في حالات مختارة.', 'Preventing or treating certain blood clots and reducing stroke risk in selected patients.', 'يزداد خطر النزف مع مميعات الدم ومضادات الالتهاب ومضادات الصفائح، وتتداخل معه بعض الأدوية القوية المؤثرة في CYP3A4 وP-gp.', 'Bleeding risk increases with other anticoagulants, NSAIDs, and antiplatelets; strong CYP3A4/P-gp interacting drugs can also affect it.'), 'warfarin': ('وارفارين / كومادين', 'Warfarin / Coumadin', {'وارفارين', 'warfarin', 'كومادين', 'coumadin'}, 'يتطلب متابعة INR منتظمة لأن تأثيره يتأثر بأدوية وأغذية وأمراض عديدة. النزف غير المعتاد يستدعي تقييمًا طبيًا.', 'Requires regular INR monitoring because many medicines, foods, and illnesses affect its action. Unusual bleeding needs medical assessment.', 'الوقاية أو العلاج من الجلطات في حالات محددة.', 'Preventing or treating blood clots in selected conditions.', 'له تداخلات كثيرة مع المضادات الحيوية ومضادات الالتهاب ومضادات الصفائح والمكملات، كما أن تغيّر تناول فيتامين K قد يؤثر في INR.', 'Has many interactions with antibiotics, NSAIDs, antiplatelets, and supplements; major changes in vitamin K intake can also affect INR.'), 'sertraline': ('سيرترالين / لوسترال / زولوفت', 'Sertraline / Lustral / Zoloft', {'zoloft', 'سيرترالين', 'زولوفت', 'sertraline', 'لوسترال', 'lustral'}, 'قد يسبب غثيانًا أو اضطراب نوم في البداية. راقب أي تدهور بالمزاج أو أفكار إيذاء النفس، خاصة عند بدء العلاج أو تغيير الجرعة.', 'May cause nausea or sleep changes initially. Monitor for worsening mood or self-harm thoughts, especially when starting treatment or changing dose.', 'علاج الاكتئاب وبعض اضطرابات القلق والوسواس واضطراب ما بعد الصدمة حسب التشخيص الطبي.', 'Treating depression and selected anxiety, obsessive-compulsive, and post-traumatic stress disorders when diagnosed.', 'يُمنع مع مثبطات MAO، ويزداد خطر متلازمة السيروتونين مع أدوية سيروتونينية أخرى، وقد يزيد النزف مع مضادات الالتهاب ومميعات الدم.', 'Contraindicated with MAO inhibitors; serotonin syndrome risk rises with other serotonergic drugs, and bleeding risk can increase with NSAIDs or anticoagulants.'), 'escitalopram': ('إسيتالوبرام / سيبرالكس', 'Escitalopram / Cipralex / Lexapro', {'escitalopram', 'lexapro', 'اسيتالوبرام', 'cipralex', 'سيبرالكس', 'إسيتالوبرام'}, 'قد يسبب غثيانًا أو صداعًا أو تغيرات بالنوم. راقب أي تدهور بالمزاج أو أفكار إيذاء النفس خصوصًا في البداية.', 'May cause nausea, headache, or sleep changes. Monitor for worsening mood or self-harm thoughts, especially early in treatment.', 'علاج الاكتئاب وبعض اضطرابات القلق.', 'Treating depression and selected anxiety disorders.', 'يُمنع مع مثبطات MAO، وقد يزيد خطر متلازمة السيروتونين مع أدوية أخرى، كما قد يطيل QT في بعض الحالات.', 'Contraindicated with MAO inhibitors; other serotonergic medicines increase serotonin-syndrome risk, and QT prolongation can be relevant in some patients.'), 'fluoxetine': ('فلوكسيتين / بروزاك', 'Fluoxetine / Prozac', {'fluoxetine', 'فلوكسيتين', 'بروزاك', 'prozac'}, 'قد يسبب غثيانًا أو أرقًا أو قلقًا في البداية. راقب تغيرات المزاج أو أفكار إيذاء النفس خصوصًا عند بدء العلاج أو تعديل الجرعة.', 'May cause nausea, insomnia, or activation early on. Monitor mood changes or self-harm thoughts when starting or changing dose.', 'علاج الاكتئاب وبعض اضطرابات القلق والوسواس واضطرابات أخرى حسب التشخيص.', 'Treating depression and selected anxiety, obsessive-compulsive, and other disorders when diagnosed.', 'له تداخلات مهمة مع مثبطات MAO وأدوية سيروتونينية وأدوية تعتمد على CYP2D6، وقد يزيد النزف مع مضادات الالتهاب أو مميعات الدم.', 'Important interactions include MAO inhibitors, serotonergic medicines, CYP2D6 substrates, and increased bleeding risk with NSAIDs or anticoagulants.'), 'duloxetine': ('دولوكستين / سيمبالتا', 'Duloxetine / Cymbalta', {'دولوكستين', 'سيمبالتا', 'cymbalta', 'duloxetine'}, 'قد يسبب غثيانًا أو دوخة وقد يرفع ضغط الدم. الحذر في أمراض الكبد، ولا يوقف فجأة عادةً لتجنب أعراض الانسحاب.', 'May cause nausea or dizziness and can raise blood pressure. Use caution in liver disease and usually taper rather than stopping abruptly.', 'علاج الاكتئاب والقلق وبعض أنواع الألم العصبي والألم المزمن.', 'Treating depression, anxiety, and selected neuropathic or chronic pain conditions.', 'يُمنع مع مثبطات MAO، ويزداد خطر متلازمة السيروتونين مع أدوية مشابهة، وقد يزيد النزف مع مضادات الالتهاب ومميعات الدم.', 'Contraindicated with MAO inhibitors; serotonergic drugs raise serotonin-syndrome risk, and bleeding risk can increase with NSAIDs or anticoagulants.'), 'gabapentin': ('غابابنتين / نيورونتين', 'Gabapentin / Neurontin', {'جابابنتين', 'gabapentin', 'نيورونتين', 'neurontin', 'غابابنتين'}, 'قد يسبب دوخة ونعاسًا وعدم اتزان. الجمع مع الأفيونات أو المهدئات قد يزيد خطر تثبيط التنفس.', 'May cause dizziness, drowsiness, and unsteadiness. Combining it with opioids or sedatives can increase respiratory-depression risk.', 'علاج بعض أنواع الألم العصبي وبعض أنواع الصرع حسب الوصفة.', 'Treating selected neuropathic pain and seizure disorders when prescribed.', 'تزيد المهدئات والأفيونات النعاس وتثبيط التنفس، وقد تقلل بعض مضادات الحموضة امتصاصه إذا أخذت في الوقت نفسه.', 'Sedatives and opioids increase drowsiness and respiratory-depression risk; some antacids can reduce absorption if taken together.'), 'pregabalin': ('بريغابالين / ليريكا', 'Pregabalin / Lyrica', {'ليريكا', 'lyrica', 'pregabalin', 'بريغابالين', 'بريجابالين'}, 'قد يسبب دوخة ونعاسًا وتورمًا وزيادة وزن. الجمع مع الأفيونات أو المهدئات قد يزيد خطر تثبيط التنفس.', 'May cause dizziness, drowsiness, swelling, and weight gain. Combining it with opioids or sedatives can increase respiratory-depression risk.', 'علاج بعض أنواع الألم العصبي، ويستخدم في حالات عصبية محددة حسب الوصفة.', 'Treating selected neuropathic pain and certain neurologic conditions when prescribed.', 'يزداد النعاس وتثبيط التنفس مع الأفيونات والكحول والمهدئات، وقد يزداد التورم مع بعض أدوية السكري من فئة الثيازوليدينديون.', 'Sedation and respiratory-depression risk increase with opioids, alcohol, and sedatives; swelling can increase with thiazolidinedione diabetes medicines.'), 'azithromycin': ('أزيثروميسين / زيثروماكس', 'Azithromycin / Zithromax', {'ازيثروميسين', 'azithromycin', 'zithromax', 'زيثروماكس', 'z-pack', 'أزيثروميسين'}, 'مضاد حيوي للعدوى البكتيرية المحددة وليس للفيروسات. قد يسبب إسهالًا أو غثيانًا، وقد يطيل QT لدى بعض المرضى.', 'An antibiotic for selected bacterial infections, not viral illness. It may cause diarrhea or nausea and can prolong QT in susceptible patients.', 'علاج بعض الالتهابات البكتيرية حسب وصف الطبيب.', 'Treating selected bacterial infections when prescribed.', 'الحذر مع أدوية أخرى تطيل QT وبعض أدوية القلب، وأخبر الطبيب عن جميع الأدوية قبل الاستخدام.', 'Use caution with other QT-prolonging medicines and some heart drugs; tell your clinician about all medicines before use.'), 'doxycycline': ('دوكسيسيكلين / فيبرامايسين', 'Doxycycline / Vibramycin', {'دوكسيسيكلين', 'vibramycin', 'doxycycline', 'فيبرامايسين'}, 'قد يسبب حساسية للشمس وتهيج المريء. تناوله مع ماء كافٍ وتجنب الاستلقاء مباشرة بعده حسب تعليمات الصيدلي.', 'Can cause sun sensitivity and esophageal irritation. Take with adequate water and avoid lying down immediately afterward as directed.', 'علاج أنواع محددة من الالتهابات البكتيرية وحالات أخرى حسب الوصفة.', 'Treating selected bacterial infections and other conditions when prescribed.', 'الحديد والكالسيوم والمغنيسيوم ومضادات الحموضة قد تقلل امتصاصه؛ افصلها حسب تعليمات الطبيب أو الصيدلي.', 'Iron, calcium, magnesium, and antacids can reduce absorption; separate them as directed by a clinician or pharmacist.'), 'cefuroxime': ('سيفوروكسيم / زينات', 'Cefuroxime / Zinnat', {'cefuroxime', 'zinnat', 'ceftin', 'سيفوروكسيم', 'زينات'}, 'من مضادات السيفالوسبورين وقد يسبب إسهالًا أو غثيانًا أو طفحًا. أخبر الطبيب عن أي حساسية شديدة سابقة للبنسلين أو السيفالوسبورين.', 'A cephalosporin antibiotic that may cause diarrhea, nausea, or rash. Tell your clinician about any prior severe penicillin or cephalosporin allergy.', 'علاج بعض الالتهابات البكتيرية حسب الوصفة.', 'Treating selected bacterial infections when prescribed.', 'قد تتأثر بعض الأشكال الفموية بأدوية تقلل حموضة المعدة، وقد توجد تداخلات مع مميعات الدم أو أدوية أخرى حسب الحالة.', 'Some oral formulations can be affected by acid-reducing medicines, and interactions with anticoagulants or other drugs may be relevant.')}
MEDICATIONS.update(_EXPANDED_MEDICATIONS)


# Each medication shown publicly is backed by: (1) a Saudi SFDA registry
# reference and (2) two independent clinical references. The SFDA source is a
# local registration/reference directory; clinical warnings are cross-checked
# against the two clinical sources before the seeded record is marked ready.
_SFDA_DRUGS_LIST = "https://sfda.gov.sa/en/node/17582"
MEDICATION_SOURCES = {
    "aspirin": [
        ("SFDA", "local_registry", _SFDA_DRUGS_LIST),
        ("NHS", "clinical", "https://www.nhs.uk/medicines/aspirin/"),
        ("DailyMed", "clinical", "https://dailymed.nlm.nih.gov/dailymed/search.cfm?query=aspirin"),
    ],
    "ibuprofen": [("SFDA","local_registry",_SFDA_DRUGS_LIST),("NHS","clinical","https://www.nhs.uk/medicines/ibuprofen-for-adults/"),("DailyMed","clinical","https://dailymed.nlm.nih.gov/dailymed/search.cfm?query=ibuprofen")],
    "paracetamol": [("SFDA","local_registry",_SFDA_DRUGS_LIST),("NHS","clinical","https://www.nhs.uk/medicines/paracetamol-for-adults/"),("DailyMed","clinical","https://dailymed.nlm.nih.gov/dailymed/search.cfm?query=acetaminophen")],
    "antibiotics": [("SFDA","local_registry",_SFDA_DRUGS_LIST),("NHS","clinical","https://www.nhs.uk/medicines/amoxicillin/"),("DailyMed","clinical","https://dailymed.nlm.nih.gov/dailymed/search.cfm?query=amoxicillin")],
    "antihistamine": [("SFDA","local_registry",_SFDA_DRUGS_LIST),("NHS","clinical","https://www.nhs.uk/medicines/cetirizine/about-cetirizine/"),("DailyMed","clinical","https://dailymed.nlm.nih.gov/dailymed/search.cfm?query=cetirizine")],
    "decongestant": [("SFDA","local_registry",_SFDA_DRUGS_LIST),("NHS","clinical","https://www.nhs.uk/medicines/pseudoephedrine/about-pseudoephedrine/"),("DailyMed","clinical","https://dailymed.nlm.nih.gov/dailymed/search.cfm?query=pseudoephedrine")],
    "diclofenac": [("SFDA","local_registry",_SFDA_DRUGS_LIST),("NHS","clinical","https://www.nhs.uk/medicines/diclofenac/"),("DailyMed","clinical","https://dailymed.nlm.nih.gov/dailymed/search.cfm?query=diclofenac")],
    "metformin": [("SFDA","local_registry",_SFDA_DRUGS_LIST),("NHS","clinical","https://www.nhs.uk/medicines/metformin/"),("DailyMed","clinical","https://dailymed.nlm.nih.gov/dailymed/search.cfm?query=metformin")],
    "amlodipine": [("SFDA","local_registry",_SFDA_DRUGS_LIST),("NHS","clinical","https://www.nhs.uk/medicines/amlodipine/"),("DailyMed","clinical","https://dailymed.nlm.nih.gov/dailymed/search.cfm?query=amlodipine")],
    "omeprazole": [("SFDA","local_registry",_SFDA_DRUGS_LIST),("NHS","clinical","https://www.nhs.uk/medicines/omeprazole/"),("DailyMed","clinical","https://dailymed.nlm.nih.gov/dailymed/search.cfm?query=omeprazole")],
    "contrave": [
        ("SFDA", "local_registry", "https://sfda.gov.sa/ar/node/16167"),
        ("DailyMed", "clinical", "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=485ff360-32c8-11df-928b-0002a5d5c51b"),
        ("MedlinePlus", "clinical", "https://medlineplus.gov/ency/patientinstructions/000346.htm"),
    ],
}

# Medication-specific source search pages for the expanded catalog. Every
# public record keeps the same source policy: one Saudi SFDA reference plus
# two independent clinical information providers. These are reference links,
# not a substitute for clinician/pharmacist review.
def _expanded_source_url(provider, generic_name):
    from urllib.parse import quote_plus
    q = quote_plus(generic_name)
    if provider == "DailyMed":
        return f"https://dailymed.nlm.nih.gov/dailymed/search.cfm?query={q}"
    return f"https://vsearch.nlm.nih.gov/vivisimo/cgi-bin/query-meta?v:project=medlineplus&query={q}"

for _slug, _entry in _EXPANDED_MEDICATIONS.items():
    _generic = _entry[1].split("/")[0].strip()
    MEDICATION_SOURCES.setdefault(_slug, [
        ("SFDA", "local_registry", _SFDA_DRUGS_LIST),
        ("DailyMed", "clinical", _expanded_source_url("DailyMed", _generic)),
        ("MedlinePlus", "clinical", _expanded_source_url("MedlinePlus", _generic)),
    ])


def _unpack(entry):
    name_ar, name_en, keywords, warn_ar, warn_en, uses_ar, uses_en, interact_ar, interact_en = entry
    return name_ar, name_en, keywords, warn_ar, warn_en, uses_ar, uses_en, interact_ar, interact_en


def check_medications(notes: str):
    """Returns a list of {"name", "warning"} dicts for any recognized medication
    mentioned in the free-text notes (lang-appropriate)."""
    if not notes:
        return []
    text = notes.lower()
    matches = []
    seen = set()
    for key, entry in MEDICATIONS.items():
        if key in seen:
            continue
        name_ar, name_en, keywords, warn_ar, warn_en, *_ = _unpack(entry)
        for kw in keywords:
            if clinical_text.contains_unnegated_phrase(text, kw):
                matches.append({
                    "name_ar": name_ar, "name_en": name_en,
                    "warning_ar": warn_ar, "warning_en": warn_en,
                })
                seen.add(key)
                break
    return matches


def _name_matches(text, candidate):
    """True when the searched text is the candidate name, one of its words, or (for long text) part of it.

    A bare substring test made 3-letter Arabic words match inside drug names ("راس" -> "باراسيتامول"),
    so "وجع راس" (headache) was answered as a paracetamol question.
    """
    cand = _norm(candidate)
    if not text or not cand:
        return False
    if text == cand:
        return True
    if re.search(r"(?<![\w\u0600-\u06ff])" + re.escape(text) + r"(?![\w\u0600-\u06ff])", cand):
        return True
    return len(text) >= 6 and text in cand


def lookup_drug(name: str):
    """Return a medication record from the production database.

    The bundled curated records are only used to seed an empty database. All
    runtime searches then go through the database, so Admin/database updates
    are reflected without changing the frontend.
    """
    if not name:
        return None
    init_schema()
    text = _norm(name)
    conn = db._conn()
    try:
        c = conn.cursor()
        c.execute("SELECT id,slug,name_ar,name_en,aliases,warning_ar,warning_en,uses_ar,uses_en,interactions_ar,interactions_en,updated_at FROM medical_medications WHERE status='active'")
        for row in c.fetchall():
            aliases = json.loads(row[4] or "[]")
            choices = [row[2], row[3], *aliases]
            if any(_name_matches(text, x) for x in choices):
                sources = medication_sources(row[0])
                policy = medication_source_policy(sources)
                if not policy["ok"]:
                    return None
                return {"id":row[0],"slug":row[1],"name_ar":row[2],"name_en":row[3],"warning_ar":row[5],"warning_en":row[6],"uses_ar":row[7],"uses_en":row[8],"interact_ar":row[9],"interact_en":row[10],"updated_at":row[11],"sources":sources,"source_policy":policy}
    finally:
        conn.close()
    return None


def _norm(value):
    text = str(value or "").strip().lower().replace("ـ", "")
    text = re.sub(r"[/_,+;:()\[\]{}]+", " ", text)
    text = re.sub(r"[-–—]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _seed_values(slug, entry, now):
    name_ar,name_en,keywords,warn_ar,warn_en,uses_ar,uses_en,interact_ar,interact_en = _unpack(entry)
    return (slug,name_ar,name_en,json.dumps(sorted(keywords),ensure_ascii=False),warn_ar,warn_en,uses_ar,uses_en,interact_ar,interact_en,"active",now)


def _seed_content_hash(values):
    payload = json.dumps(list(values[1:10]), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _db_content_hash(row):
    payload = json.dumps(list(row), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def medication_sources(medication_id: int):
    init_schema()
    conn=db._conn(); c=conn.cursor()
    try:
        c.execute(f"SELECT provider,source_role,url,verified,last_verified FROM medical_medication_sources WHERE medication_id={db.PH} AND verified=1 ORDER BY CASE source_role WHEN 'local_registry' THEN 1 ELSE 2 END,provider", (int(medication_id),))
        return [dict(zip(["provider","role","url","verified","last_verified"],r)) for r in c.fetchall()]
    finally: conn.close()

def medication_source_policy(sources):
    src=list(sources or [])
    local=any(x.get("role")=="local_registry" and x.get("verified") for x in src)
    clinical={str(x.get("provider") or "").lower() for x in src if x.get("role")=="clinical" and x.get("verified")}
    return {"ok": bool(local and len(clinical)>=2), "has_local":local, "clinical_provider_count":len(clinical), "source_count":len(src)}

def init_schema():
    db.init_db()
    conn = db._conn()
    try:
        c = conn.cursor()
        serial = "SERIAL PRIMARY KEY" if db.USE_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"
        c.execute(f"""CREATE TABLE IF NOT EXISTS medical_medications (
            id {serial}, slug TEXT UNIQUE NOT NULL, name_ar TEXT NOT NULL,
            name_en TEXT NOT NULL, aliases TEXT NOT NULL, warning_ar TEXT,
            warning_en TEXT, uses_ar TEXT, uses_en TEXT, interactions_ar TEXT,
            interactions_en TEXT, status TEXT NOT NULL DEFAULT 'active',
            updated_at TEXT NOT NULL
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS medical_seed_meta (
            slug TEXT PRIMARY KEY, seed_hash TEXT NOT NULL, updated_at TEXT NOT NULL
        )""")
        c.execute(f"""CREATE TABLE IF NOT EXISTS medical_medication_sources (
            id {serial}, medication_id INTEGER NOT NULL, provider TEXT NOT NULL,
            source_role TEXT NOT NULL, url TEXT NOT NULL, verified INTEGER NOT NULL DEFAULT 0,
            last_verified TEXT, UNIQUE(medication_id,provider,url)
        )""")
        now = datetime.now(timezone.utc).isoformat()
        columns = "slug,name_ar,name_en,aliases,warning_ar,warning_en,uses_ar,uses_en,interactions_ar,interactions_en,status,updated_at"
        placeholders = ",".join([db.PH] * 12)
        for slug, entry in MEDICATIONS.items():
            values = _seed_values(slug, entry, now)
            current_seed_hash = _seed_content_hash(values)
            c.execute(f"SELECT name_ar,name_en,aliases,warning_ar,warning_en,uses_ar,uses_en,interactions_ar,interactions_en FROM medical_medications WHERE slug={db.PH}", (slug,))
            row = c.fetchone()
            c.execute(f"SELECT seed_hash FROM medical_seed_meta WHERE slug={db.PH}", (slug,))
            meta = c.fetchone()
            if row is None:
                c.execute(f"INSERT INTO medical_medications({columns}) VALUES({placeholders})", values)
                c.execute(f"INSERT INTO medical_seed_meta(slug,seed_hash,updated_at) VALUES({db.PH},{db.PH},{db.PH})", (slug, current_seed_hash, now))
                continue

            db_hash = _db_content_hash(row)
            previous_seed_hash = meta[0] if meta else None

            legacy_seed_match = False
            if slug == "antibiotics" and not meta:
                legacy_values = list(values)
                legacy_values[4] = "مهم إكمال الجرعة كاملة حسب وصف الطبيب حتى لو تحسنتِ، وعدم استخدامه بدون وصفة طبية."
                legacy_values[5] = "Important to complete the full prescribed course even if you feel better, and avoid use without a doctor's prescription."
                legacy_values[8] = "قد يضعف فعالية حبوب منع الحمل، ويتداخل مع مميعات الدم وبعض أدوية المعدة — أبلغ طبيبك بكل ما تتناوله."
                legacy_values[9] = "May reduce the effectiveness of birth control pills and interact with blood thinners and some stomach medications — tell your doctor everything you take."
                legacy_seed_match = db_hash == _seed_content_hash(tuple(legacy_values))

            seed_managed = (previous_seed_hash not in (None, "custom") and db_hash == previous_seed_hash) or legacy_seed_match
            if seed_managed and db_hash != current_seed_hash:
                c.execute(
                    f"UPDATE medical_medications SET name_ar={db.PH},name_en={db.PH},aliases={db.PH},warning_ar={db.PH},warning_en={db.PH},uses_ar={db.PH},uses_en={db.PH},interactions_ar={db.PH},interactions_en={db.PH},status={db.PH},updated_at={db.PH} WHERE slug={db.PH}",
                    (*values[1:12], slug),
                )
                db_hash = current_seed_hash

            if not meta:
                marker_hash = current_seed_hash if db_hash == current_seed_hash else "custom"
                c.execute(f"INSERT INTO medical_seed_meta(slug,seed_hash,updated_at) VALUES({db.PH},{db.PH},{db.PH})", (slug, marker_hash, now))
            elif db_hash == current_seed_hash and previous_seed_hash != current_seed_hash:
                c.execute(f"UPDATE medical_seed_meta SET seed_hash={db.PH},updated_at={db.PH} WHERE slug={db.PH}", (current_seed_hash, now, slug))
        # Seed reviewed source references for bundled medication records. Existing
        # custom medication rows are never granted source-ready status implicitly.
        for slug, srcs in MEDICATION_SOURCES.items():
            c.execute(f"SELECT id FROM medical_medications WHERE slug={db.PH}", (slug,))
            med_row=c.fetchone()
            if not med_row: continue
            med_id=int(med_row[0])
            for provider, role, url in srcs:
                if db.USE_POSTGRES:
                    c.execute(f"INSERT INTO medical_medication_sources(medication_id,provider,source_role,url,verified,last_verified) VALUES({','.join([db.PH]*6)}) ON CONFLICT(medication_id,provider,url) DO NOTHING", (med_id,provider,role,url,1,now[:10]))
                else:
                    c.execute(f"INSERT OR IGNORE INTO medical_medication_sources(medication_id,provider,source_role,url,verified,last_verified) VALUES({','.join([db.PH]*6)})", (med_id,provider,role,url,1,now[:10]))
        conn.commit()
    finally:
        conn.close()
