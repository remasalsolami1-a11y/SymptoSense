"""Emergency warning signs for high-risk symptom pages in the health library.

DRAFT clinical content: written from widely published public-health guidance
(NHS, AHA/ASA, WHO) and still awaiting sign-off by a licensed clinician. See
CLINICAL_REVIEW_SAFETY_GAPS_V276.md. It only ADDS warning signs and an
emergency link; it never lowers or replaces an existing red-flag rule.
"""
import html
import re

_CHEST = {
    "ar": ["ألم أو ضغط أو ثقل في الصدر يستمر أكثر من بضع دقائق أو يعود بعد زواله",
           "ألم يمتد إلى الذراع أو الكتف أو الفك أو الرقبة أو الظهر",
           "ضيق في التنفس أو عدم القدرة على إكمال الجملة",
           "تعرّق بارد أو غثيان أو قيء",
           "دوخة شديدة أو إغماء أو خفقان شديد",
           "ألم صدر حاد ومفاجئ مع ضيق نفس، أو بعد إصابة أو رحلة طويلة"],
    "en": ["Chest pain, pressure or heaviness lasting more than a few minutes, or that comes back",
           "Pain spreading to the arm, shoulder, jaw, neck or back",
           "Shortness of breath or being unable to finish a sentence",
           "Cold sweat, nausea or vomiting",
           "Severe dizziness, fainting or a racing heartbeat",
           "Sudden sharp chest pain with breathlessness, or after an injury or a long journey"]}
_HEADACHE = {
    "ar": ["صداع مفاجئ وشديد جدًا يبلغ ذروته خلال دقائق، أو «أسوأ صداع في حياتك»",
           "صداع مع حمى وتيبس في الرقبة أو طفح جلدي",
           "صداع مع ضعف أو تنميل في جهة واحدة، أو صعوبة في الكلام، أو تشوش أو فقدان في الرؤية",
           "صداع بعد إصابة في الرأس",
           "صداع مع نوبة تشنجية أو إغماء أو تشوش في الوعي"],
    "en": ["A sudden, very severe headache that peaks within minutes, or the worst headache of your life",
           "Headache with fever and a stiff neck or a rash",
           "Headache with one-sided weakness or numbness, difficulty speaking, or blurred or lost vision",
           "Headache after a head injury",
           "Headache with a seizure, fainting or confusion"]}
_BREATH = {
    "ar": ["صعوبة في الكلام بجمل كاملة بسبب ضيق التنفس",
           "ازرقاق الشفتين أو الوجه أو الأظافر",
           "ضيق نفس مفاجئ وشديد أو يزداد بسرعة",
           "ألم أو ضغط في الصدر مع ضيق النفس",
           "تورم الوجه أو الشفتين أو اللسان، خاصة بعد دواء أو طعام",
           "إغماء أو تشوش أو نعاس شديد"],
    "en": ["Struggling to speak in full sentences because of breathlessness",
           "Blue or grey lips, face or nails",
           "Sudden, severe or fast-worsening breathlessness",
           "Chest pain or pressure with breathlessness",
           "Swelling of the face, lips or tongue, especially after a medicine or food",
           "Fainting, confusion or extreme drowsiness"]}
_STROKE = {
    "ar": ["ضعف أو تنميل مفاجئ في الوجه أو الذراع أو الساق، خاصة في جهة واحدة",
           "التواء في الفم أو تدلّي أحد جانبي الوجه",
           "صعوبة مفاجئة في الكلام أو الفهم",
           "فقدان أو تشوش مفاجئ في الرؤية",
           "دوار شديد مفاجئ أو فقدان التوازن أو صداع شديد مفاجئ",
           "سجّل وقت بدء الأعراض وأخبر الإسعاف به"],
    "en": ["Sudden weakness or numbness of the face, arm or leg, especially on one side",
           "A drooping face or crooked mouth",
           "Sudden trouble speaking or understanding",
           "Sudden loss of vision or blurred vision",
           "Sudden severe dizziness, loss of balance or a sudden severe headache",
           "Note the time the symptoms started and tell the ambulance crew"]}
_RASH = {
    "ar": ["طفح لا يختفي أو لا يبهت عند الضغط عليه بكأس زجاجي شفاف",
           "طفح مع حمى أو تيبس في الرقبة أو نعاس شديد",
           "تورم الوجه أو الشفتين أو اللسان، أو صعوبة في التنفس",
           "طفح ينتشر بسرعة مع ألم شديد أو بثور أو تقرحات في الفم أو العينين"],
    "en": ["A rash that does not fade when pressed with a clear glass",
           "A rash with fever, a stiff neck or extreme drowsiness",
           "Swelling of the face, lips or tongue, or difficulty breathing",
           "A rash that spreads fast with severe pain, blisters or sores in the mouth or eyes"]}
_SELFHARM = {
    "ar": ["أفكار بإنهاء حياتك أو إيذاء نفسك، خاصة إذا كانت لديك خطة أو وسيلة",
           "شعور بأنك لا تستطيع البقاء آمنًا الآن",
           "إيذاء النفس فعليًا أو تناول دواء أو مادة بكمية زائدة",
           "لا تبقَ وحدك: اتصل بالإسعاف 997 أو توجه لأقرب طوارئ أو اطلب من شخص تثق به أن يبقى معك"],
    "en": ["Thoughts of ending your life or hurting yourself, especially with a plan or the means",
           "Feeling you cannot keep yourself safe right now",
           "Having harmed yourself or taken too much of a medicine or substance",
           "Do not stay alone: call 997, go to the nearest emergency department, or ask someone you trust to stay with you"]}
_STOOL = {
    "ar": ["دم كثير أو مستمر مع البراز",
           "براز أسود قطراني كريه الرائحة",
           "دوخة أو إغماء أو خفقان أو شحوب شديد",
           "ألم شديد في البطن",
           "قيء دموي أو يشبه القهوة المطحونة"],
    "en": ["A lot of blood, or bleeding that does not stop",
           "Black, tarry, foul-smelling stool",
           "Dizziness, fainting, a racing heart or severe paleness",
           "Severe abdominal pain",
           "Vomiting blood or material that looks like coffee grounds"]}
_NEURO = {
    "ar": ["تشنجات أو فقدان للوعي",
           "تشوش مفاجئ في الذهن أو عدم القدرة على الاستجابة بشكل طبيعي",
           "ضعف أو صعوبة كلام أو تشوش رؤية مفاجئ",
           "نوبة تستمر أكثر من 5 دقائق أو تتكرر دون استعادة الوعي"],
    "en": ["Seizures or loss of consciousness",
           "Sudden confusion or being unable to respond normally",
           "Sudden weakness, difficulty speaking or blurred vision",
           "A seizure lasting more than 5 minutes or repeating without recovery"]}

FLAGS = {
    "chest-pain": _CHEST, "chest-tightness": _CHEST,
    "severe-headache": _HEADACHE, "headache": _HEADACHE,
    "shortness-of-breath": _BREATH, "rapid-breathing": _BREATH,
    "one-sided-weakness": _STROKE, "one-sided-numbness": _STROKE,
    "speech-difficulty": _STROKE, "sudden-vision-loss": _STROKE,
    "skin-rash": _RASH, "suicidal-thoughts": _SELFHARM, "blood-in-stool": _STOOL,
    "seizure": _NEURO, "confusion": _NEURO,
}

# Red full-width alert only for symptoms that are dangerous by themselves.
# Common symptoms (plain headache, rash, mild breathlessness-type wording) get a calm
# amber box, so the strong alert keeps its meaning and is not shown for ordinary symptoms.
STRONG = {"chest-pain", "severe-headache", "shortness-of-breath", "one-sided-weakness",
          "one-sided-numbness", "speech-difficulty", "sudden-vision-loss",
          "suicidal-thoughts", "blood-in-stool", "seizure"}

_TEMPLATE = re.compile(r"^(?:عرض عام:|General symptom:)", re.I)


def has_flags(slug):
    return slug in FLAGS


def banner_and_section(slug, ar, prefix):
    """Strong, CSS-independent warning. Inline styles on purpose: the alert must
    stay prominent even if the stylesheet fails to load or is cached stale."""
    data = FLAGS.get(slug)
    if not data:
        return "", ""
    esc = lambda s: html.escape(str(s), quote=True)
    items = data["ar" if ar else "en"]
    if slug not in STRONG:
        return _caution(items, ar, prefix, esc)
    lis = "".join(
        '<li style="margin:0 0 10px;padding:10px 12px;background:#FFF;border:1px solid #F3B8B8;'
        'border-radius:10px;list-style:none;font-weight:700;line-height:1.7">🔴 %s</li>' % esc(x) for x in items)
    head = "علامات تستدعي الطوارئ فورًا" if ar else "Signs that need emergency care now"
    lead = ("إذا كانت أي علامة منها موجودة الآن: اتصل بالإسعاف فورًا، ولا تنتظر ولا تكمل القراءة." if ar
            else "If any of these is happening now: call the ambulance immediately. Do not wait and do not keep reading.")
    call = ("📞 اتصل بالإسعاف 997 الآن" if ar else "📞 Call ambulance 997 now")
    more = ("صفحة الطوارئ وخطوات الإسعاف ←" if ar else "Emergency page and first steps →")
    notalone = ("لا تقد السيارة بنفسك إن كان الألم أو الدوخة شديدين." if ar
                else "Do not drive yourself if the pain or dizziness is severe.")
    banner = (
        '<section role="alert" aria-live="assertive" data-ss-redflag-banner="1" '
        'style="position:sticky;top:0;z-index:40;border:3px solid #B71C1C;border-radius:16px;'
        'background:#FFEBEE;padding:16px;text-align:center;box-shadow:0 6px 22px rgba(183,28,28,.28)">'
        '<div style="font-size:19px;font-weight:900;color:#B71C1C;line-height:1.6">🚨 %s</div>'
        '<div style="margin:6px 0 12px;color:#7F1D1D;font-weight:700;line-height:1.7">%s</div>'
        '<a href="tel:997" style="display:block;width:100%%;box-sizing:border-box;min-height:56px;'
        'line-height:56px;border-radius:14px;background:#C62828;color:#fff;font-size:20px;font-weight:900;'
        'text-decoration:none">%s</a>'
        '<div style="margin-top:10px;font-size:14px"><a href="%s/emergency" style="color:#B71C1C;'
        'font-weight:800;text-decoration:underline">%s</a></div></section>'
        % (esc(head), esc(lead), esc(call), prefix, esc(more)))
    section = (
        '<section class="ss-card" data-ss-redflag-list="1" style="border:2px solid #C62828;'
        'border-inline-start:8px solid #C62828;background:#FFF8F8"><h2 style="color:#B71C1C">🚨 %s</h2>'
        '<ul style="padding:0;margin:0">%s</ul>'
        '<p style="margin:10px 0 0;font-weight:700;color:#7F1D1D">%s</p></section>'
        % (esc(head), lis, esc(notalone)))
    return banner, section


def _caution(items, ar, prefix, esc):
    head = "متى تحتاج إلى رعاية عاجلة؟" if ar else "When to seek urgent care"
    lead = ("معظم الحالات بسيطة، لكن إذا ظهرت إحدى العلامات التالية فاطلب الرعاية العاجلة أو اتصل بالإسعاف 997."
            if ar else "Most cases are minor, but if any of these signs appear, seek urgent care or call 997.")
    more = "صفحة الطوارئ ←" if ar else "Emergency page →"
    lis = "".join('<li style="margin:0 0 8px;line-height:1.7">%s</li>' % esc(x) for x in items)
    section = ('<section class="ss-card" data-ss-caution-list="1" style="border:1px solid #F9A825;'
               'border-inline-start:6px solid #EF6C00;background:#FFF8E1"><h2 style="color:#8D4B00">⚠️ %s</h2>'
               '<p style="margin:0 0 10px">%s</p><ul style="margin:0;padding-inline-start:20px">%s</ul>'
               '<p style="margin:10px 0 0"><a href="%s/emergency" style="font-weight:800">%s</a></p></section>'
               % (esc(head), esc(lead), lis, prefix, esc(more)))
    return "", section


def description(text, name, ar):
    """Replace the thin auto-generated description with a useful, non-diagnostic one."""
    if text and not _TEMPLATE.match(text.strip()):
        return text
    if ar:
        return ("%s عرض صحي قد تكون له أسباب متعددة، بعضها بسيط وبعضها يحتاج تقييمًا طبيًا. "
                "تعرّف هنا على علامات الخطر والأسئلة التي تساعد على توضيح الصورة ومتى تطلب رعاية طبية." % name)
    return ("%s is a health symptom with many possible causes, some minor and some needing medical assessment. "
            "Learn the warning signs, helpful questions to consider, and when to seek care." % name)


# ---------------------------------------------------------------------------
# Richer data for the STRONG symptoms: what to do while waiting, serious
# conditions clinicians rule out first (non-diagnostic wording), and sources.
# Source URLs were confirmed to exist (NHS / WHO). DRAFT until clinician sign-off.
# ---------------------------------------------------------------------------
_NHS = "https://www.nhs.uk/"
_SRC = {
    "chest": [("NHS", "Chest pain", _NHS + "symptoms/chest-pain/"),
              ("NHS", "Heart attack", _NHS + "conditions/heart-attack/")],
    "stroke": [("NHS", "Symptoms of a stroke (FAST)", _NHS + "conditions/stroke/symptoms/")],
    "breath": [("NHS", "Shortness of breath", _NHS + "symptoms/shortness-of-breath/")],
    "headache": [("NHS", "Headaches", _NHS + "symptoms/headaches/"),
                 ("NHS", "Subarachnoid haemorrhage", _NHS + "conditions/subarachnoid-haemorrhage/")],
    "stool": [("NHS", "Bleeding from the bottom (rectal bleeding)", _NHS + "symptoms/bleeding-from-the-bottom-rectal-bleeding/")],
    "selfharm": [("WHO", "Suicide fact sheet", "https://www.who.int/news-room/fact-sheets/detail/suicide")],
    "seizure": [("NHS", "What to do if someone has a seizure (fit)", _NHS + "symptoms/what-to-do-if-someone-has-a-seizure-fit/")],
}
_FAMILY = {"chest-pain": "chest", "severe-headache": "headache", "shortness-of-breath": "breath",
           "one-sided-weakness": "stroke", "one-sided-numbness": "stroke", "speech-difficulty": "stroke",
           "sudden-vision-loss": "stroke", "suicidal-thoughts": "selfharm", "blood-in-stool": "stool",
           "seizure": "seizure"}
DETAILS = {
    "chest": {
        "wait": {"ar": ["اتصل بالإسعاف 997 ولا تقد السيارة بنفسك.",
                        "اجلس أو استلقِ في وضع مريح وحاول البقاء هادئًا، وفُكّ الملابس الضيقة.",
                        "لا تأكل ولا تشرب، ولا تجهد نفسك بالمشي أو الصعود.",
                        "اتبع تعليمات مشغّل الإسعاف بخصوص الأسبرين، ولا تتناوله من تلقاء نفسك إن كانت لديك حساسية منه أو مشكلة نزيف.",
                        "أخبر من حولك وافتح الباب للمسعفين إن كنت وحدك."],
                 "en": ["Call 997 and do not drive yourself.",
                        "Sit or lie in a comfortable position, stay calm and loosen tight clothing.",
                        "Do not eat or drink, and avoid exertion such as walking or climbing stairs.",
                        "Follow the dispatcher's advice about aspirin; do not take it on your own if you are allergic or have a bleeding problem.",
                        "Tell someone nearby, and unlock the door for the paramedics if you are alone."]},
        "rule_out": {"ar": ["نوبة قلبية أو ذبحة صدرية", "جلطة رئوية", "انفصال أو تمزق في الشريان الأورطي", "التهاب غشاء القلب أو الغشاء المحيط بالرئة", "استرواح الصدر (تسرّب هواء حول الرئة)"],
                     "en": ["Heart attack or angina", "Pulmonary embolism", "Aortic dissection", "Pericarditis or pleurisy", "Collapsed lung (pneumothorax)"]},
    },
    "stroke": {
        "wait": {"ar": ["اتصل بالإسعاف 997 فورًا، فكل دقيقة تهم في السكتة الدماغية.",
                        "سجّل الوقت الذي بدأت فيه الأعراض أو آخر مرة كان فيها الشخص طبيعيًا.",
                        "اجعل الشخص يجلس أو يستلقي بأمان، ولا تعطه أكلًا أو شرابًا أو دواءً.",
                        "إذا فقد الوعي ولا يتنفس بشكل طبيعي فاتبع تعليمات مشغّل الإسعاف."],
                 "en": ["Call 997 immediately: every minute counts in a stroke.",
                        "Note the time the symptoms started or when the person was last normal.",
                        "Keep the person safe sitting or lying down; give no food, drink or medicine.",
                        "If they lose consciousness and are not breathing normally, follow the dispatcher's instructions."]},
        "rule_out": {"ar": ["سكتة دماغية إقفارية أو نزفية", "نوبة إقفارية عابرة (جلطة مصغّرة تحذّيرية)", "هبوط شديد في سكر الدم", "نوبة تشنجية"],
                     "en": ["Ischaemic or haemorrhagic stroke", "Transient ischaemic attack (warning mini-stroke)", "Very low blood sugar", "A seizure"]},
    },
    "breath": {
        "wait": {"ar": ["اتصل بالإسعاف 997 إن كانت الأعراض شديدة أو تزداد.",
                        "اجلس منتصبًا مائلًا قليلًا للأمام، وافتح النافذة أو اطلب هواءً نقيًا.",
                        "إن كان لديك بخاخ ربو موصوف فاستخدمه كما وُصف لك.",
                        "تنفّس ببطء من الأنف وازفر من الفم، ولا تبقَ وحدك."],
                 "en": ["Call 997 if it is severe or getting worse.",
                        "Sit upright, leaning slightly forward, and get fresh air.",
                        "If you have a prescribed asthma inhaler, use it as directed.",
                        "Breathe slowly in through the nose and out through the mouth, and do not stay alone."]},
        "rule_out": {"ar": ["نوبة ربو شديدة أو حساسية مفرطة", "جلطة رئوية", "التهاب رئوي شديد", "فشل القلب أو مشكلة في نظم القلب", "استرواح الصدر"],
                     "en": ["Severe asthma or anaphylaxis", "Pulmonary embolism", "Severe pneumonia", "Heart failure or a heart rhythm problem", "Collapsed lung (pneumothorax)"]},
    },
    "headache": {
        "wait": {"ar": ["اتصل بالإسعاف 997 إن كان الصداع مفاجئًا وشديدًا جدًا أو معه إحدى العلامات أعلاه.",
                        "استلقِ في مكان هادئ، ولا تقد السيارة.",
                        "لا تتناول أدوية إضافية قبل أن يقيّمك الطبيب إن كنت تشك بنزيف أو إصابة."],
                 "en": ["Call 997 if the headache is sudden and very severe or comes with any sign above.",
                        "Lie down somewhere quiet, and do not drive.",
                        "Do not take extra medicine before a doctor assesses you if you suspect bleeding or injury."]},
        "rule_out": {"ar": ["نزيف تحت العنكبوتية (نزيف حول الدماغ)", "التهاب السحايا", "جلطة أو نزيف دماغي", "ارتفاع حاد في ضغط الدم"],
                     "en": ["Subarachnoid haemorrhage (bleeding around the brain)", "Meningitis", "Stroke or brain bleed", "Severely high blood pressure"]},
    },
    "stool": {
        "wait": {"ar": ["اذهب إلى الطوارئ أو اتصل بالإسعاف 997 إن كان النزف كثيرًا أو معه دوخة أو إغماء.",
                        "استلقِ ولا تقف فجأة.",
                        "لا تأكل ولا تشرب إلى أن يقيّمك الطبيب.",
                        "اذكر للطبيب أدويتك، خاصة مميعات الدم ومسكنات الألم."],
                 "en": ["Go to emergency or call 997 if bleeding is heavy or you feel dizzy or faint.",
                        "Lie down and do not stand up suddenly.",
                        "Do not eat or drink until a doctor has assessed you.",
                        "Tell the doctor your medicines, especially blood thinners and painkillers."]},
        "rule_out": {"ar": ["نزيف في الجهاز الهضمي العلوي أو السفلي", "قرحة المعدة", "التهاب القولون أو الأمراض الالتهابية للأمعاء", "البواسير أو الشق الشرجي (الأكثر شيوعًا)", "أورام القولون (أقل شيوعًا)"],
                     "en": ["Upper or lower gastrointestinal bleeding", "Stomach ulcer", "Colitis or inflammatory bowel disease", "Haemorrhoids or an anal fissure (most common)", "Bowel tumours (less common)"]},
    },
    "selfharm": {
        "wait": {"ar": ["اتصل بالإسعاف 997 أو توجه لأقرب طوارئ الآن.",
                        "أبعد الأدوية والأدوات التي قد تؤذيك عن متناولك، أو اطلب من شخص أن يبعدها.",
                        "لا تبقَ وحدك: تواصل مع شخص تثق به ليبقى معك.",
                        "يمكنك أيضًا الاتصال بمركز اتصال وزارة الصحة 937 للمساعدة في التوجيه."],
                 "en": ["Call 997 or go to the nearest emergency department now.",
                        "Move medicines and anything you could use to hurt yourself out of reach, or ask someone to.",
                        "Do not stay alone: contact someone you trust to stay with you.",
                        "You can also call the Ministry of Health call centre on 937 for guidance."]},
        "rule_out": {"ar": ["أزمة نفسية حادة تحتاج تقييمًا عاجلًا", "اكتئاب شديد", "تأثير مادة أو دواء", "ضغط نفسي شديد مؤقت"],
                     "en": ["An acute mental-health crisis needing urgent assessment", "Severe depression", "The effect of a substance or medicine", "Severe temporary distress"]},
    },
    "seizure": {
        "wait": {"ar": ["أبعد الأشياء الحادة عن الشخص واحمِ رأسه بشيء ناعم.",
                        "لا تُدخل شيئًا في فمه ولا تحاول تثبيته.",
                        "بعد انتهاء التشنج اجعله على جنبه (وضع الإفاقة).",
                        "اتصل بالإسعاف 997 إن استمرت النوبة أكثر من 5 دقائق أو كانت الأولى أو تكررت أو لم يستعد وعيه."],
                 "en": ["Move sharp objects away and cushion the person's head.",
                        "Do not put anything in the mouth and do not hold them down.",
                        "When the jerking stops, turn them onto their side (recovery position).",
                        "Call 997 if it lasts over 5 minutes, is a first seizure, repeats, or they do not recover."]},
        "rule_out": {"ar": ["الصرع", "هبوط شديد في سكر الدم", "إصابة أو نزيف في الرأس", "التهاب الدماغ أو السحايا", "اضطراب في نظم القلب"],
                     "en": ["Epilepsy", "Very low blood sugar", "Head injury or bleeding", "Brain or meningeal infection", "A heart rhythm problem"]},
    },
}


def details_section(slug, ar):
    """Extra cards (what to do while waiting / what doctors rule out / sources)."""
    fam = _FAMILY.get(slug)
    d = DETAILS.get(fam)
    if not d:
        return ""
    esc = lambda s: html.escape(str(s), quote=True)
    k = "ar" if ar else "en"
    ul = lambda items: '<ul style="margin:0;padding-inline-start:20px;line-height:1.9">%s</ul>' % "".join(
        "<li>%s</li>" % esc(x) for x in items)
    note = ("هذه قائمة بما يهتم الطبيب باستبعاده، وليست تشخيصًا لحالتك."
            if ar else "This is what a clinician rules out first; it is not a diagnosis of your case.")
    srcs = "".join(
        '<li><a href="%s" target="_blank" rel="noopener noreferrer"><b>%s</b> — %s</a></li>'
        % (esc(u), esc(o), esc(t)) for o, t, u in _SRC[fam])
    return (
        '<section class="ss-card" data-ss-wait-steps="1"><h2>%s</h2>%s</section>'
        '<section class="ss-card" data-ss-rule-out="1"><h2>%s</h2>%s<small class="muted">%s</small></section>'
        '<section class="ss-card" data-ss-flag-sources="1"><h2>%s</h2><ul style="margin:0;padding-inline-start:20px;line-height:1.9">%s</ul>'
        '<small class="muted">%s</small></section>'
        % (esc("ماذا تفعل حتى يصل الإسعاف؟" if ar else "What to do until help arrives"), ul(d["wait"][k]),
           esc("حالات خطيرة يهتم الطبيب باستبعادها" if ar else "Serious conditions doctors rule out first"),
           ul(d["rule_out"][k]), esc(note),
           esc("مصادر علامات الخطر" if ar else "Sources for the warning signs"), srcs,
           esc("محتوى توعوي عام قيد المراجعة الطبية، ولا يغني عن تعليمات الإسعاف أو الطبيب." if ar
               else "General educational content pending clinical review; it never replaces dispatcher or doctor instructions.")))
