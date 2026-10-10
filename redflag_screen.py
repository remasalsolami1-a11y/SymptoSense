"""Red-flag screening questions chosen from the symptoms the user entered (V252).

Before the differential questions, the app asks a few yes/no screens that are
*only* about warning signs of the entered symptoms. A "yes" on an emergency-tier
screen stops the analysis (client shows the emergency overlay; the server also
re-checks the submitted ids). A "yes" on a today-tier screen raises the advice to
"see a clinician today". Nothing here names a disease.

CLINICAL REVIEW: every wording below is standard public warning-sign guidance
(NHS / MedlinePlus style) but has NOT been signed off by a clinician. ``clinical_signoff.json`` records whether a named clinician approved this area.
"""
from __future__ import annotations

import medical_knowledge as mk

MAX_SCREENS = 4
EMERGENCY, TODAY = "emergency", "today"

# id, canonical symptom slugs (any), tier, question ar/en, flag label ar/en, optional (min_age, max_age)
_ROWS = [
    ("cp_radiating", ("chest-pain", "chest-tightness"), EMERGENCY,
     "هل ينتشر ألم الصدر إلى الذراع أو الفك أو الظهر، أو يصاحبه عرق بارد أو ضيق نفس؟",
     "Does the chest pain spread to the arm, jaw or back, or come with cold sweat or breathlessness?",
     "ألم صدر ينتشر أو يصاحبه عرق/ضيق نفس", "Chest pain that spreads or comes with sweating/breathlessness", None),
    ("cp_pressure", ("chest-pain", "chest-tightness"), EMERGENCY,
     "هل هو ضغط أو عصر شديد في الصدر مستمر أكثر من 15 دقيقة؟",
     "Is it a severe pressure or squeezing in the chest lasting more than 15 minutes?",
     "ضغط شديد في الصدر أكثر من 15 دقيقة", "Severe chest pressure lasting over 15 minutes", None),
    ("sob_speech", ("shortness-of-breath",), EMERGENCY,
     "هل تعجز عن إكمال جملة كاملة بسبب ضيق النفس، أو يميل لون الشفاه إلى الأزرق؟",
     "Can you not finish a full sentence because of breathlessness, or are your lips turning blue?",
     "ضيق نفس شديد أو زرقة", "Severe breathlessness or blue lips", None),
    ("sob_legswell", ("shortness-of-breath",), TODAY,
     "هل يصاحب ضيق النفس تورم في الساقين أو ألم في إحداهما؟",
     "Is the breathlessness together with leg swelling or pain in one leg?",
     "ضيق نفس مع تورم/ألم في الساق", "Breathlessness with leg swelling or one-sided leg pain", None),
    ("ha_thunder", ("headache", "severe-headache"), EMERGENCY,
     "هل بدأ الصداع فجأة وبأشد درجة (كأسوأ صداع في حياتك)؟",
     "Did the headache start suddenly at full strength (the worst headache of your life)?",
     "صداع مفاجئ شديد جدًا", "Sudden, very severe headache", None),
    ("ha_neck_fever", ("headache", "severe-headache"), EMERGENCY,
     "هل يصاحب الصداع تيبس في الرقبة مع حرارة، أو طفح لا يختفي بالضغط؟",
     "Is the headache together with a stiff neck and fever, or a rash that does not fade when pressed?",
     "صداع مع تيبس رقبة وحرارة أو طفح", "Headache with stiff neck and fever or a rash", None),
    ("ha_neuro", ("headache", "severe-headache", "dizziness"), EMERGENCY,
     "هل ظهر مع العرض ضعف في جهة واحدة أو التواء في الوجه أو صعوبة في الكلام أو فقدان مفاجئ للرؤية؟",
     "Did weakness on one side, a drooping face, trouble speaking or sudden vision loss appear?",
     "علامات جلطة/سكتة محتملة (ضعف جهة واحدة، كلام، رؤية)", "Possible stroke signs (one-sided weakness, speech, vision)", None),
    ("ha_head_injury", ("headache",), TODAY,
     "هل بدأ الصداع بعد ضربة على الرأس؟",
     "Did the headache start after a blow to the head?",
     "صداع بعد إصابة في الرأس", "Headache after a head injury", None),
    ("ab_rigid", ("abdominal-pain",), EMERGENCY,
     "هل البطن قاسٍ ومؤلم جدًا عند اللمس بحيث لا تستطيع الحركة أو الاستقامة؟",
     "Is the abdomen hard and so painful to touch that you cannot move or straighten up?",
     "بطن قاسٍ مع ألم شديد", "Hard, very painful abdomen", None),
    ("ab_blood", ("abdominal-pain", "vomiting", "diarrhea", "blood-in-stool"), EMERGENCY,
     "هل هناك قيء فيه دم أو براز أسود لزج أو دم غزير في البراز؟",
     "Is there vomit containing blood, black tarry stool or heavy blood in the stool?",
     "دم في القيء أو براز أسود/غزير الدم", "Blood in vomit, black stool or heavy rectal blood", None),
    ("ab_fever", ("abdominal-pain",), TODAY,
     "هل يصاحب ألم البطن حرارة أو قيء متكرر لا يتوقف؟",
     "Does the abdominal pain come with fever or repeated vomiting that will not stop?",
     "ألم بطن مع حرارة أو قيء متكرر", "Abdominal pain with fever or persistent vomiting", None),
    ("fv_infant", ("fever",), EMERGENCY,
     "هل عمر الطفل أقل من 3 أشهر؟",
     "Is the baby younger than 3 months old?",
     "حرارة عند رضيع أقل من 3 أشهر", "Fever in a baby younger than 3 months", (0, 0.99)),
    ("fv_rash_neck", ("fever",), EMERGENCY,
     "هل تصاحب الحرارة رقبة متيبسة أو طفح لا يختفي بالضغط عليه أو ارتباك في الوعي؟",
     "Is the fever together with a stiff neck, a rash that does not fade on pressure, or confusion?",
     "حرارة مع تيبس رقبة/طفح/ارتباك", "Fever with stiff neck, rash or confusion", None),
    ("fv_long", ("fever",), TODAY,
     "هل استمرت الحرارة أكثر من 3 أيام أو تتكرر الارتفاعات فوق 39؟",
     "Has the fever lasted more than 3 days or keeps going above 39°C?",
     "حرارة تستمر أكثر من 3 أيام أو فوق 39", "Fever over 3 days or above 39°C", None),
    ("dz_faint", ("dizziness", "loss-of-consciousness", "palpitations"), EMERGENCY,
     "هل أغمي عليك أو شعرت أنك ستفقد الوعي مع ألم في الصدر أو خفقان شديد؟",
     "Did you faint, or feel you would, together with chest pain or a pounding heartbeat?",
     "إغماء مع ألم صدر أو خفقان", "Fainting with chest pain or palpitations", None),
    ("bk_cauda", ("back-pain",), EMERGENCY,
     "هل يصاحب ألم الظهر تنميل بين الساقين أو فقدان التحكم بالبول أو البراز أو ضعف في الساقين؟",
     "Is the back pain with numbness between the legs, loss of bladder/bowel control or leg weakness?",
     "ألم ظهر مع فقدان تحكم أو تنميل بين الساقين", "Back pain with loss of control or saddle numbness", None),
    ("vm_dehyd", ("vomiting", "diarrhea"), TODAY,
     "هل مرّت 8 ساعات أو أكثر دون تبول، أو لا تستطيع شرب السوائل دون قيء؟",
     "Has it been 8+ hours without urinating, or can you not keep fluids down?",
     "علامات جفاف", "Signs of dehydration", None),
    ("ur_flank", ("painful-urination",), TODAY,
     "هل يصاحب حرقان البول حرارة أو ألم في الجنب أو الظهر؟",
     "Is the burning urination with fever or flank/back pain?",
     "حرقان بول مع حرارة أو ألم جنب", "Burning urination with fever or flank pain", None),
    ("ey_sudden", ("eye-pain",), EMERGENCY,
     "هل فقدت الرؤية فجأة أو ظهرت ومضات وستارة سوداء في النظر؟",
     "Did you lose vision suddenly, or see flashes with a dark curtain?",
     "فقدان رؤية مفاجئ أو ومضات وستارة", "Sudden vision loss or flashes with a curtain", None),
    ("cf_acute", ("confusion",), EMERGENCY,
     "هل بدأ التشوش فجأة، أو يصاحبه حرارة أو صداع شديد أو ضعف في جهة واحدة أو إصابة حديثة في الرأس؟",
     "Did the confusion start suddenly, or come with fever, a severe headache, one-sided weakness or a recent head injury?",
     "تشوش ذهني مفاجئ أو مع علامات خطر", "Sudden confusion or confusion with warning signs", None),
    ("mh_selfharm", ("low-mood", "anxiety", "panic-attack"), EMERGENCY,
     "هل تراودك أفكار بإنهاء حياتك أو إيذاء نفسك؟",
     "Are you having thoughts of ending your life or hurting yourself?",
     "أفكار بإنهاء الحياة أو إيذاء النفس", "Thoughts of ending your life or hurting yourself", None),
    ("bl_heavy", ("severe-bleeding",), EMERGENCY,
     "هل النزيف غزير ولا يتوقف بالضغط المباشر عشر دقائق؟",
     "Is the bleeding heavy and not stopping after 10 minutes of direct pressure?",
     "نزيف غزير لا يتوقف", "Heavy bleeding that will not stop", None),
]

SCREENS = [
    {"id": r[0], "slugs": r[1], "tier": r[2], "q_ar": r[3], "q_en": r[4], "flag_ar": r[5], "flag_en": r[6], "ages": r[7]}
    for r in _ROWS
]
BY_ID = {s["id"]: s for s in SCREENS}


def _slugs(symptoms, lang="ar"):
    out = set()
    for raw in symptoms or []:
        try:
            for c in mk.normalize_symptoms([str(raw)], lang).get("canonical") or []:
                if c.get("slug"):
                    out.add(c["slug"])
        except Exception:
            continue
    return out


def next_screen(symptoms, asked=(), age=None, lang="ar"):
    """One unanswered screen, emergency tier first; ``None`` when finished."""
    asked = {str(x) for x in (asked or [])}
    if len(asked) >= MAX_SCREENS:
        return None
    slugs = _slugs(symptoms, lang)
    try:
        age = float(age) if age not in (None, "") else None
    except (TypeError, ValueError):
        age = None
    cands = []
    for s in SCREENS:
        if s["id"] in asked or not (slugs & set(s["slugs"])):
            continue
        if s["ages"] and age is not None and not (s["ages"][0] <= age <= s["ages"][1]):
            continue
        cands.append(s)
    if not cands:
        return None
    cands.sort(key=lambda s: (s["tier"] != EMERGENCY,))
    s = cands[0]
    en = lang == "en"
    return {"id": s["id"], "tier": s["tier"], "question": s["q_en"] if en else s["q_ar"],
            "flag": s["flag_en"] if en else s["flag_ar"],
            "reason": "Checking for warning signs first" if en else "نتأكد أولًا من عدم وجود علامات خطر",
            "number": len(asked) + 1, "max": MAX_SCREENS,
            "review": __import__("clinical_signoff").status_for("redflag", s["id"], lang)}


def resolve(ids):
    """Split submitted 'yes' ids into (emergency, today) lists of (id, flag_ar, flag_en)."""
    em, td = [], []
    for rid in list(ids or [])[:12]:
        s = BY_ID.get(str(rid))
        if not s:
            continue
        (em if s["tier"] == EMERGENCY else td).append((s["id"], s["flag_ar"], s["flag_en"]))
    return em, td


def register(app, consent_ok, consent_required, mk_error):
    """Attach POST /api/analyze/redflag-next (called once from webapp)."""
    from flask import jsonify, request

    @app.route("/api/analyze/redflag-next", methods=["POST"])
    def api_analyze_redflag_next():
        try:
            if not consent_ok():
                return consent_required("/chat")
            data = request.get_json(silent=True) or {}
            lang = "en" if data.get("lang") == "en" else "ar"
            symptoms = data.get("symptoms") or []
            if isinstance(symptoms, str):
                symptoms = [symptoms]
            asked = [str(x)[:40] for x in (data.get("asked") or [])][:20]
            nxt = next_screen([str(x)[:120] for x in symptoms][:30], asked, data.get("age"), lang)
            return jsonify({"ok": True, "done": nxt is None, "screen": nxt})
        except Exception as exc:
            return mk_error(exc, 500)
    return api_analyze_redflag_next
