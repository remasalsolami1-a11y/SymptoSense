"""Curated multi-symptom interaction layer for SymptoSense.

The base medical knowledge engine already scores each symptom-disease relation.
This module adds small *interaction* bonuses when two or more independently
normalized symptoms form a clinically coherent pattern already represented in
that disease's source-grounded knowledge row.

It never creates a diagnosis and never changes emergency triage. Bonuses are
bounded and only applied when the disease already has at least two matched
symptoms, so a combo cannot manufacture a match from nothing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ComboPattern:
    slug: str
    symptoms: tuple[str, ...]
    targets: tuple[str, ...]
    bonus: float
    label_ar: str
    label_en: str
    note_ar: str
    note_en: str


PATTERNS: tuple[ComboPattern, ...] = (
    ComboPattern("headache-nausea", ("headache","nausea"), ("migraine",), .08, "صداع + غثيان", "Headache + nausea", "اجتماع العرضين يعطي المحرك سياقًا أقوى عند ترتيب الاحتمالات المرتبطة بالصداع.", "This pair gives the engine stronger context when ranking headache-related possibilities."),
    ComboPattern("headache-light-sensitivity", ("headache","light-sensitivity"), ("migraine",), .10, "صداع + حساسية للضوء", "Headache + light sensitivity", "نمط متعدد الأعراض يدعم ترتيب الاحتمالات المرتبطة بالصداع دون إثبات سبب محدد.", "A multi-symptom pattern that supports ranking headache-related possibilities without proving a cause."),
    ComboPattern("headache-neck", ("headache","neck-pain"), ("tension-type-headache",), .06, "صداع + ألم الرقبة", "Headache + neck pain", "يُستخدم كتفاعل إضافي صغير عندما تكون الأعراض نفسها مرتبطة أصلًا بالحالة.", "Used as a small interaction signal when the individual symptoms already support the condition."),
    ComboPattern("flu-pattern", ("fever","cough","body-aches"), ("influenza",), .10, "حمى + سعال + آلام جسم", "Fever + cough + body aches", "النمط يساعد على ترتيب احتمالات العدوى التنفسية الموثقة مع بقاء النتيجة غير تشخيصية.", "Helps rank source-grounded respiratory infection possibilities while remaining non-diagnostic."),
    ComboPattern("pneumonia-pattern", ("fever","cough","shortness-of-breath"), ("pneumonia",), .09, "حمى + سعال + ضيق تنفس", "Fever + cough + breathlessness", "يضيف سياقًا لترتيب الاحتمالات التنفسية؛ طبقة السلامة تبقى مستقلة ولها الأولوية.", "Adds context to respiratory ranking; the independent safety layer always keeps priority."),
    ComboPattern("bronchitis-pattern", ("cough","phlegm"), ("acute-bronchitis",), .07, "سعال + بلغم", "Cough + phlegm", "يدعم ترتيب الاحتمالات التي تتضمن السعال المصحوب بالبلغم عندما تكون بقية البيانات متوافقة.", "Supports ranking possibilities that include productive cough when the rest of the context fits."),
    ComboPattern("tonsillitis-pattern", ("sore-throat","fever"), ("tonsillitis",), .08, "ألم حلق + حمى", "Sore throat + fever", "تفاعل إضافي بين عرضين موجودين أصلًا في قاعدة المعرفة.", "An additional interaction between two symptoms already represented in the knowledge base."),
    ComboPattern("allergic-rhinitis-pattern", ("sneezing","nasal-congestion","runny-nose"), ("allergic-rhinitis",), .11, "عطاس + احتقان + سيلان الأنف", "Sneezing + congestion + runny nose", "تجميع الأعراض الأنفية يساعد على ترتيب الاحتمالات المرتبطة بالحساسية بصورة أوضح.", "Combining nasal symptoms helps rank allergy-related possibilities more clearly."),
    ComboPattern("sinus-pattern", ("sinus-pressure","nasal-congestion","headache"), ("acute-sinusitis",), .10, "ضغط الجيوب + احتقان + صداع", "Sinus pressure + congestion + headache", "نمط موحد للأعراض المتجاورة بدل التعامل مع كل عرض بمعزل عن الآخر.", "A unified pattern for related symptoms rather than treating each symptom in isolation."),
    ComboPattern("gastro-pattern", ("nausea","vomiting","diarrhea"), ("viral-gastroenteritis","food-poisoning"), .09, "غثيان + قيء + إسهال", "Nausea + vomiting + diarrhea", "يساعد المحرك على فهم أن الأعراض الهضمية تظهر كمجموعة مترابطة أحيانًا.", "Helps the engine understand that gastrointestinal symptoms can occur as a related cluster."),
    ComboPattern("abdominal-gastro-pattern", ("abdominal-pain","vomiting","diarrhea"), ("food-poisoning","viral-gastroenteritis"), .08, "ألم بطن + قيء + إسهال", "Abdominal pain + vomiting + diarrhea", "يضيف إشارة نمطية صغيرة فقط إذا كانت الحالة مرتبطة أصلًا بهذه الأعراض.", "Adds only a small pattern signal when the condition is already linked to these symptoms."),
    ComboPattern("reflux-pattern", ("heartburn","bloating"), ("gerd","gastritis"), .07, "حرقة + انتفاخ", "Heartburn + bloating", "يجمع أعراض الجهاز الهضمي العلوي لتحسين ترتيب النتائج المرتبطة.", "Combines upper-digestive symptoms to improve ranking of related results."),
    ComboPattern("ibs-pattern", ("abdominal-pain","bloating","constipation"), ("irritable-bowel-syndrome","functional-constipation"), .08, "ألم بطن + انتفاخ + إمساك", "Abdominal pain + bloating + constipation", "نمط وظيفي هضمي متعدد الأعراض يُستخدم كدعم للترتيب فقط.", "A multi-symptom digestive pattern used only as ranking support."),
    ComboPattern("uti-pattern", ("painful-urination","frequent-urination"), ("urinary-tract-infection",), .11, "حرقة بول + كثرة التبول", "Painful urination + frequency", "تفاعل واضح بين عرضين بوليين لتحسين ترتيب الاحتمالات المرتبطة.", "A clear interaction between two urinary symptoms to improve related ranking."),
    ComboPattern("kidney-infection-pattern", ("painful-urination","fever","back-pain"), ("kidney-infection",), .10, "أعراض بولية + حمى + ألم ظهر", "Urinary symptoms + fever + back pain", "هذا النمط لا يحدد التشخيص؛ وجود الشدة أو علامات الخطر يظل خاضعًا لقواعد السلامة.", "This pattern does not diagnose; severity and warning signs remain governed by safety rules."),
    ComboPattern("palpitation-dizziness", ("palpitations","dizziness"), ("heart-palpitations",), .07, "خفقان + دوخة", "Palpitations + dizziness", "اجتماع العرضين يرفع قيمة سؤال المتابعة والسياق، لا مستوى الطوارئ تلقائيًا.", "The pair increases contextual relevance, not emergency urgency automatically."),
    ComboPattern("thyroid-overactive", ("palpitations","tremor","sweating","weight-loss"), ("overactive-thyroid",), .12, "خفقان + رجفة + تعرّق + نقص وزن", "Palpitations + tremor + sweating + weight loss", "نمط متعدد الأجهزة يدعم ترتيب الاحتمالات التي تتضمن هذه المجموعة من الأعراض.", "A multi-system pattern supporting ranking of possibilities that include this symptom cluster."),
    ComboPattern("iron-pattern", ("fatigue","pale-skin","palpitations"), ("iron-deficiency-anaemia",), .10, "تعب + شحوب + خفقان", "Fatigue + pallor + palpitations", "يجمع مؤشرات عامة قد تظهر مع أكثر من سبب؛ النتيجة تبقى احتمالية وغير تشخيصية.", "Combines general findings that can have multiple causes; the result remains non-diagnostic."),
    ComboPattern("b12-pattern", ("fatigue","numbness","memory-problems"), ("vitamin-b12-folate-deficiency",), .09, "تعب + تنميل + مشاكل ذاكرة", "Fatigue + numbness + memory problems", "يساعد على ترتيب احتمال موثق عندما تكون الأعراض نفسها موجودة بالفعل.", "Helps rank a source-grounded possibility when the individual symptoms are already present."),
    ComboPattern("diabetes-pattern", ("increased-thirst","frequent-urination","fatigue"), ("type-2-diabetes-pattern",), .11, "عطش + كثرة تبول + تعب", "Thirst + frequent urination + fatigue", "تجميع الأعراض يحسن مطابقة النمط، لكنه لا يغني عن القياس أو الفحص الطبي.", "The cluster improves pattern matching but never replaces testing or medical assessment."),
    ComboPattern("diabetes-weight-pattern", ("increased-thirst","frequent-urination","weight-loss"), ("type-2-diabetes-pattern",), .12, "عطش + كثرة تبول + نقص وزن", "Thirst + frequent urination + weight loss", "نمط يستحق التقييم الطبي إذا استمر، ويستخدم هنا فقط لتحسين ترتيب الاحتمالات.", "A pattern that warrants medical assessment if persistent and is used here only to improve ranking."),
    ComboPattern("oa-knee-pattern", ("knee-pain","joint-clicking"), ("osteoarthritis",), .10, "ألم الركبة + طقطقة", "Knee pain + clicking", "يساعد في التعامل مع وصف المستخدم كتركيبة واحدة بدل عرضين منفصلين.", "Helps treat the user's description as one combined pattern rather than two isolated symptoms."),
    ComboPattern("plantar-pattern", ("heel-sole-pain","first-step-heel-pain"), ("plantar-fasciitis",), .14, "ألم الكعب + ألم أول خطوات", "Heel pain + first-step pain", "تركيبة عالية النوعية نسبيًا داخل قاعدة المعرفة لكنها لا تُعرض كتشخيص مؤكد.", "A relatively specific pattern within the knowledge base, but never presented as a confirmed diagnosis."),
    ComboPattern("tennis-elbow-pattern", ("outer-elbow-pain","elbow-pain-gripping"), ("tennis-elbow",), .14, "ألم خارج الكوع + ألم مع القبض", "Outer elbow pain + gripping pain", "تفاعل بين عرضين حركيين يحسن ترتيب الحالة المرتبطة عندما تكون المصادر متاحة.", "An interaction between two movement-related symptoms that improves ranking when sources are available."),
    ComboPattern("tmj-pattern", ("jaw-pain","jaw-clicking"), ("temporomandibular-disorder",), .14, "ألم الفك + طقطقة", "Jaw pain + clicking", "يعطي المحرك سياقًا أفضل للأسئلة المتعلقة بالفك والمضغ.", "Gives the engine better context for jaw and chewing-related questions."),
    ComboPattern("trigger-finger-pattern", ("finger-locking","finger-stiffness-pain"), ("trigger-finger",), .14, "تعليق الإصبع + تيبس/ألم", "Finger locking + stiffness/pain", "نمط حركي متكامل يساعد على ترتيب الاحتمال الموثق المرتبط.", "An integrated movement pattern that helps rank the associated source-grounded possibility."),
    ComboPattern("restless-legs-pattern", ("urge-move-legs","leg-discomfort-at-rest"), ("restless-legs-syndrome",), .14, "رغبة تحريك الساق + انزعاج وقت الراحة", "Urge to move legs + rest discomfort", "يجمع الأعراض المميزة في استعلام واحد لتحسين المطابقة.", "Combines characteristic symptoms in one pattern to improve matching."),
    ComboPattern("sleep-apnoea-pattern", ("loud-snoring","sleep-breathing-pauses","daytime-sleepiness"), ("obstructive-sleep-apnoea",), .14, "شخير + توقف تنفس أثناء النوم + نعاس نهاري", "Snoring + breathing pauses + daytime sleepiness", "نمط نوم متعدد العناصر يرفع جودة المطابقة دون أن يحول الموقع لأداة تشخيص.", "A multi-element sleep pattern that improves matching without turning the site into a diagnostic tool."),
    ComboPattern("blepharitis-pattern", ("eyelash-crusts","itchy-eyelids"), ("blepharitis",), .14, "قشور الرموش + حكة الجفن", "Eyelash crusting + itchy eyelids", "تجميع عرضين موضعيين يجعل نتيجة البحث والتحليل أكثر دقة.", "Combining two localized symptoms makes search and analysis matching more precise."),
    ComboPattern("gum-pattern", ("bleeding-gums","swollen-gums"), ("gum-disease",), .14, "نزيف اللثة + تورمها", "Bleeding + swollen gums", "نمط فموي متعدد الأعراض لتحسين المطابقة داخل قاعدة المعرفة.", "A multi-symptom oral pattern that improves knowledge-base matching."),
    ComboPattern("dandruff-pattern", ("scalp-flakes","itchy-scalp"), ("dandruff-pattern",), .14, "قشرة فروة الرأس + حكة", "Scalp flakes + itch", "يجمع الأعراض الشائعة في نمط واحد بدل نتائج منفصلة.", "Combines common symptoms into one pattern instead of separate results."),
    ComboPattern("athletes-foot-pattern", ("itch-between-toes","peeling-between-toes"), ("athletes-foot",), .14, "حكة بين الأصابع + تقشر", "Toe-web itch + peeling", "نمط جلدي موضعي يدعم ترتيب الاحتمال المرتبط فقط إذا كانت الأعراض نفسها مطابقة.", "A localized skin pattern supporting ranking only when the individual symptoms already match."),
    ComboPattern("urticaria-pattern", ("hives","itching"), ("urticaria",), .11, "شرى + حكة", "Hives + itching", "تفاعل جلدي يحسن ترتيب الاحتمال المرتبط مع بقاء قواعد صعوبة التنفس والتورم ذات أولوية أعلى.", "A skin interaction that improves ranking while breathing/swelling safety rules retain priority."),
    ComboPattern("vestibular-pattern", ("dizziness","balance-problems","nausea"), ("vertigo-pattern","labyrinthitis-vestibular-neuritis"), .09, "دوخة + اختلال توازن + غثيان", "Dizziness + imbalance + nausea", "نمط دهليزي يساعد على ترتيب الاحتمالات ذات الصلة دون تحديد السبب.", "A vestibular pattern that helps rank related possibilities without determining the cause."),
    ComboPattern("meniere-pattern", ("dizziness","tinnitus","balance-problems"), ("menieres-disease",), .10, "دوخة + طنين + اختلال توازن", "Dizziness + tinnitus + imbalance", "يضيف سياقًا متعدد الأعراض لترتيب الاحتمالات المرتبطة بالأذن الداخلية.", "Adds multi-symptom context for ranking inner-ear related possibilities."),
    ComboPattern("panic-pattern", ("anxiety","palpitations","sweating"), ("panic-disorder",), .08, "قلق + خفقان + تعرق", "Anxiety + palpitations + sweating", "لا يُستخدم لإسقاط الأسباب الجسدية؛ هو دعم ترتيب فقط بعد فحص السلامة.", "It never rules out physical causes; it is ranking support only after safety checks."),
    ComboPattern("depression-pattern", ("low-mood","insomnia","fatigue","difficulty-concentrating"), ("clinical-depression",), .10, "مزاج منخفض + أرق + تعب + ضعف تركيز", "Low mood + insomnia + fatigue + poor concentration", "نمط دعم لتجميع الأعراض المستمرة، مع إبقاء أسئلة السلامة النفسية مستقلة.", "A supportive cluster for persistent symptoms, while mental-health safety checks remain independent."),
    ComboPattern("asthma-pattern", ("wheezing","shortness-of-breath","chest-tightness"), ("asthma",), .10, "صفير + ضيق تنفس + ضيق صدر", "Wheeze + breathlessness + chest tightness", "يجمع ثلاثة أعراض تنفسية مترابطة لدعم الترتيب فقط؛ قواعد ضيق التنفس الخطير تظل مستقلة.", "Combines three related respiratory symptoms for ranking only; severe-breathlessness safety rules remain independent."),
    ComboPattern("common-cold-pattern", ("runny-nose","sore-throat","cough"), ("common-cold",), .08, "سيلان أنف + ألم حلق + سعال", "Runny nose + sore throat + cough", "نمط تنفسي علوي شائع يُستخدم لتحسين ترتيب النتائج الموثقة دون إثبات سبب.", "A common upper-respiratory cluster used to improve source-grounded ranking without establishing a cause."),
    ComboPattern("carpal-tunnel-pattern", ("hand-numbness","wrist-pain"), ("carpal-tunnel-syndrome",), .12, "تنميل اليد + ألم الرسغ", "Hand numbness + wrist pain", "تجميع عرضين في اليد والرسغ يعطي سياقًا موضعيًا أفضل للمطابقة.", "Combining hand and wrist symptoms provides better localized context for matching."),
    ComboPattern("sciatica-pattern", ("back-pain","leg-pain","numbness"), ("sciatica",), .11, "ألم ظهر + ألم ساق + تنميل", "Back pain + leg pain + numbness", "نمط متعدد المواضع يدعم ترتيب الاحتمالات المرتبطة بالعصب عندما تكون الأعراض مطابقة أصلًا.", "A multi-location pattern supporting nerve-related ranking when the individual symptoms already match."),
    ComboPattern("rheumatoid-pattern", ("joint-pain","swelling","fatigue"), ("rheumatoid-arthritis",), .09, "ألم مفاصل + تورم + تعب", "Joint pain + swelling + fatigue", "النمط يحسن تجميع الأعراض المفصلية والعامة ولا يحدد نوع التهاب المفصل تشخيصيًا.", "The cluster improves grouping of joint and general symptoms without diagnosing an arthritis subtype."),
    ComboPattern("eczema-pattern", ("itching","skin-rash","dry-skin"), ("atopic-eczema",), .10, "حكة + طفح + جفاف جلد", "Itch + rash + dry skin", "تجميع أعراض الجلد يدعم ترتيب الاحتمال المرتبط مع بقاء أسباب الطفح الأخرى ممكنة.", "Combining skin symptoms supports related ranking while other rash causes remain possible."),
    ComboPattern("psoriasis-pattern", ("skin-rash","dry-skin","itching"), ("psoriasis",), .07, "طفح + جفاف + حكة", "Rash + dry skin + itch", "نمط جلدي غير نوعي يُستخدم بإشارة صغيرة فقط لأنه قد يظهر مع أسباب متعددة.", "A nonspecific skin cluster used only as a small signal because it can occur with multiple causes."),
    ComboPattern("lactose-pattern", ("bloating","excessive-gas","diarrhea"), ("lactose-intolerance",), .10, "انتفاخ + غازات + إسهال", "Bloating + gas + diarrhea", "يجمع ثلاثة أعراض هضمية لتحسين المطابقة عندما تكون البيانات الأخرى متوافقة.", "Combines three digestive symptoms to improve matching when the rest of the context fits."),
    ComboPattern("laryngitis-pattern", ("hoarseness","sore-throat","cough"), ("laryngitis",), .11, "بحة + ألم حلق + سعال", "Hoarseness + sore throat + cough", "نمط صوتي وتنفس علوي يساعد على ترتيب الاحتمال المرتبط دون تشخيص.", "A voice and upper-airway pattern that helps rank the related possibility without diagnosing it."),
    ComboPattern("ear-infection-pattern", ("ear-pain","fever"), ("ear-infection",), .09, "ألم أذن + حمى", "Ear pain + fever", "تفاعل بسيط بين عرض موضعي وعرض عام لدعم الترتيب الموثق.", "A simple interaction between a localized and general symptom to support source-grounded ranking."),
    ComboPattern("underactive-thyroid-pattern", ("fatigue","cold-extremities","weight-gain"), ("underactive-thyroid",), .10, "تعب + برودة أطراف + زيادة وزن", "Fatigue + cold extremities + weight gain", "يجمع أعراضًا عامة قد تكون لها أسباب متعددة ويستخدمها كدعم ترتيب فقط.", "Combines general symptoms with many possible causes and uses them only as ranking support."),
    ComboPattern("peripheral-neuropathy-pattern", ("numbness","burning-sensation"), ("peripheral-neuropathy",), .10, "تنميل + إحساس بالحرقان", "Numbness + burning sensation", "تجميع أعراض الإحساس يساعد على فهم الوصف العصبي بصورة أفضل دون تحديد السبب.", "Combining sensory symptoms helps interpret the neurologic description without determining its cause."),
    ComboPattern("peripheral-oedema-pattern", ("leg-swelling","weight-gain"), ("peripheral-oedema",), .09, "تورم الساق + زيادة وزن", "Leg swelling + weight gain", "يدعم ترتيب الاحتمال المرتبط بالسوائل مع إبقاء ضيق التنفس ضمن طبقة السلامة المستقلة.", "Supports fluid-related ranking while breathlessness remains governed by the independent safety layer."),
    ComboPattern("shingles-pattern", ("skin-rash","burning-sensation"), ("shingles",), .10, "طفح + إحساس بالحرقان", "Rash + burning sensation", "نمط جلدي عصبي يدعم الترتيب فقط ولا يستبعد أسباب الطفح الأخرى.", "A skin-and-sensory cluster that supports ranking only and does not rule out other rash causes."),
    ComboPattern("swollen-glands-pattern", ("sore-throat","swollen-lymph-nodes"), ("swollen-glands","tonsillitis"), .08, "ألم حلق + تورم الغدد", "Sore throat + swollen glands", "يجمع عرضين مترابطين لتحسين ترتيب النتائج التي تمثلها قاعدة المعرفة والمصادر.", "Combines two related symptoms to improve ranking of source-grounded possibilities."),
)


def _slug_set(canonical: Iterable[dict | str]) -> set[str]:
    out: set[str] = set()
    for item in canonical or []:
        if isinstance(item, dict):
            slug = item.get("slug")
        else:
            slug = item
        if slug:
            out.add(str(slug))
    return out


def detect_patterns(canonical: Iterable[dict | str], lang: str = "ar") -> list[dict]:
    """Return matched combo metadata sorted by specificity.

    A pattern requires *all* listed symptoms. The result is explanatory metadata;
    it is never itself a diagnosis or urgency decision.
    """
    slugs = _slug_set(canonical)
    ar = lang != "en"
    hits = []
    for pattern in PATTERNS:
        required = set(pattern.symptoms)
        if required.issubset(slugs):
            hits.append({
                "slug": pattern.slug,
                "symptoms": list(pattern.symptoms),
                "targets": list(pattern.targets),
                "bonus": pattern.bonus,
                "label": pattern.label_ar if ar else pattern.label_en,
                "note": pattern.note_ar if ar else pattern.note_en,
                "symptom_count": len(pattern.symptoms),
            })
    hits.sort(key=lambda x: (x["symptom_count"], x["bonus"]), reverse=True)
    return hits[:8]


def target_bonuses(patterns: Iterable[dict]) -> dict[str, float]:
    """Collapse matched patterns to a bounded bonus per disease slug."""
    bonuses: dict[str, float] = {}
    for pattern in patterns or []:
        bonus = max(0.0, min(float(pattern.get("bonus") or 0.0), 0.15))
        for slug in pattern.get("targets") or []:
            bonuses[str(slug)] = min(0.18, bonuses.get(str(slug), 0.0) + bonus)
    return bonuses


def catalog_issues(valid_symptoms: Iterable[str], valid_diseases: Iterable[str]) -> list[dict]:
    """Validate curated combos against the active knowledge graph.

    This is used by release/tests so a typo or deleted KB slug cannot silently
    turn a competition-facing pattern into dead data.
    """
    symptoms = {str(x) for x in valid_symptoms or []}
    diseases = {str(x) for x in valid_diseases or []}
    issues = []
    seen = set()
    for pattern in PATTERNS:
        missing_symptoms = [x for x in pattern.symptoms if x not in symptoms]
        missing_targets = [x for x in pattern.targets if x not in diseases]
        duplicate = pattern.slug in seen
        seen.add(pattern.slug)
        if missing_symptoms or missing_targets or duplicate or not (0 < pattern.bonus <= 0.15):
            issues.append({
                "slug": pattern.slug,
                "missing_symptoms": missing_symptoms,
                "missing_targets": missing_targets,
                "duplicate": duplicate,
                "bonus": pattern.bonus,
            })
    return issues


def count() -> int:
    return len(PATTERNS)
