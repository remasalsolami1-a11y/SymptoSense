"""Context-dependent red flags that a plain symptom list cannot express.

Four patterns that were missed by the phrase-only layers (found in the V251 audit):

* fever in an infant under 3 months            -> emergency (``infant_fever_under_3m``)
* right-lower abdominal pain + fever/vomiting  -> emergency (``suspected_appendicitis``)
* pain in pregnancy + a warning sign           -> emergency (``pregnancy_pain_warning``)
  and pre-eclampsia warning signs              -> emergency (``preeclampsia_warning``)
* one-leg swelling/pain + breathlessness/chest -> emergency (``dvt_pe_pattern``)

Weaker versions of the same patterns (e.g. one swollen calf without breathing
symptoms) return ``today`` items so the normal analysis raises the care level
without declaring an ambulance emergency.

``evaluate(patient, text)`` -> ``{"emergency": [(id, ar, en)], "today": [(id, ar, en)]}``.
Negation ("ما عندي ضيق نفس") and old/resolved appendix episodes are respected.
"""
from __future__ import annotations

import clinical_text
import emergency_lexicon as _lex

_rx = _lex._rx
_live = _lex._live

_FEVER = _rx(r"(?<![؀-ۿ])[وفب]?(?:حراره|حرارته|حرارتها|حرارتي|حمى|سخونيه|سخن\w*|سخونه|سخونته|سخونتها|محموم|مسخن|fever|febrile|high temperature)")
_VOMIT = _rx(r"(?<![؀-ۿ])[وفب]?(?:غثيان|استفراغ|ترجيع|يستفرغ|يترجع|اتقيا|تقيؤ|قيء|vomit\w*|nausea\w*)")
_APPETITE = _rx(r"(?:فقدان|قله|ما)\s*(?:ال)?(?:شهيه|اشتهي)", r"loss of appetite")
_MOVE = _rx(r"(?:يزيد|تزيد|يشتد|تشتد|اسوا)\s*(?:مع|عند|لما)?\s*(?:الحركه|المشي|السعال|الكحه|النزول|الوقوف)",
            r"(?:مع|عند)\s*(?:الحركه|المشي|السعال|الكحه|القفز)", r"worse (?:with|when) (?:moving|walking|coughing)")
_RLQ = _rx(r"(?:اسفل|تحت|سفل)\s*(?:ال)?بطن\w*.{0,30}?(?:يمين|ايمن|اليمين|اليمنى)",
           r"(?:يمين|ايمن|اليمين|اليمنى).{0,30}?(?:اسفل|تحت|سفل)\s*(?:ال)?بطن",
           r"(?:اسفل|تحت)\s*(?:ال)?يمين\s*(?:ال)?بطن",
           r"(?:ال)?بطن\w*\s*(?:ال)?(?:تحتاني|سفلي)\w*\s*(?:ال)?(?:يمين|ايمن)\w*",
           r"right\s+lower\s+(?:abdom\w*|belly|quadrant|side)", r"lower\s+right\s+(?:abdom\w*|belly|side)")
_APPENDIX = _rx(r"(?<![؀-ۿ])[وفب]?(?:ال)?زايده(?:\s*(?:ال)?دوديه)?", r"(?<![؀-ۿ])[وفب]?(?:ال)?زائده(?:\s*(?:ال)?دوديه)?", r"appendic\w*|appendix")
_PAIN = _rx(r"(?:الم|وجع|يوجع|توجع|يعور|تعور|مغص|حاد|طعن|ضربان|pain\w*|ache\w*|cramp\w*|hurts)")
_PAIN_SEVERE = _rx(r"(?:حاد|شديد|قوي|وايد|مره|جامد|مبرح|يقطع|sharp|severe|stabbing|intense)")

_PREG = _rx(r"(?<![؀-ۿ])[وفب]?حامل\w*", r"(?:اثناء|فتره|بدايه)\s*(?:ال)?حمل", r"تاخر\w*\s*(?:ال)?دوره", r"(?:تاخرت|تاخر)\s*دورت\w*",
            r"متاخر\w*\s*(?:ال)?(?:دوره|دورت\w*)", r"دورتي\s*متاخر\w*", r"اختبار\s*(?:ال)?حمل\s*(?:ايجابي|موجب)", r"اسبوع\s*\d+\s*(?:من\s*)?(?:ال)?حمل", r"pregnan\w*")
_PELVIC = _rx(r"(?:ال)?بطن\w*", r"(?:ال)?حوض\w*", r"(?:ال)?خاصره\w*", r"abdom\w*|pelvi\w*|belly|stomach")
_ONE_SIDE = _rx(r"جهه\s*واحده", r"(?:ب|في)?جنب\s*واحد", r"(?:ب|في)?جنب\s*(?:ال)?(?:يمين|يسار)", r"جانب\s*واحد", r"طرف\s*واحد", r"(?:من|في|ناحيه)\s*(?:ال)?(?:يمين|يسار|ايمن|ايسر)",
                r"(?:يمين|يسار)ي?\b", r"one\s*side\w*", r"one-sided", r"(?:right|left)\s*side")
_DIZZY = _rx(r"(?:دوخ\w*|دوار|دايخ\w*|دخت|يدوخ|اغماء|اغمى|اغمي|هبوط|وقعت|اغشى|زغلله|dizz\w*|faint\w*|light-?headed)")
_SHOULDER = _rx(r"(?:الم|وجع)\s*(?:في\s*)?(?:ال)?(?:كتف|اكتاف)\w*", r"shoulder")
_PREG_BLEED = _rx(r"(?:نزيف|نزول\s*دم|بقع\s*دم|دم\s*(?:من|في)\s*(?:ال)?(?:مهبل|رحم)|spotting|bleeding)")
_HEAD_SEVERE = _rx(r"(?:صداع)\s*\w*\s*(?:شديد|قوي|حاد|مره|وايد|جامد)\w*", r"(?:شديد|قوي|حاد)\w*\s*صداع", r"severe\s+headache")
_VISION_BLUR = _rx(r"(?:زغلله|زغللت|رؤي\w*\s*(?:مشوش|ضبابي)\w*|نظري\s*(?:مشوش|ضبابي)|اشوف\s*(?:ضبابي|نقاط|ومض)\w*|blurr?ed\s+vision|seeing\s+spots|flashing)")
_UPPER_ABD = _rx(r"(?:الم|وجع)\s*(?:في\s*)?(?:اعلى|فوق)\s*(?:ال)?بطن", r"(?:الم|وجع)\s*(?:في\s*)?(?:ال)?(?:معده|فم\s*المعده)", r"upper\s+abdom\w*|epigastric")
_FACE_SWELL = _rx(r"تورم\s*(?:ال)?(?:وجه|يدين|اليدين)", r"face\s+swelling|swollen\s+face")

_LEG = _rx(r"(?<![؀-ۿ])[وفب]?(?:ال)?(?:ساق|ساقي|رجلي|رجل|سمانه|بطه\s*(?:ال)?رجل|فخذ)\w*", r"(?:\bleg\b|calf)")
_BOTH_LEGS = _rx(r"(?:ساقين|رجلين|قدمين|الساقين|الرجلين|القدمين|both\s+(?:legs|feet|ankles))")
_SWELL = _rx(r"(?:تورم|ورم|انتفاخ|منتفخ\w*|متورم\w*|swell\w*|swollen)")
_ONE_LEG = _rx(r"(?:ساق|رجل)\s*(?:واحده|وحده)", r"(?:ساق|رجل)\w*\s*(?:ال)?(?:يمين|يسار|يمنى|يسرى|ايمن|ايسر)", r"(?:يمين|يسار|ايمن|ايسر)\w*\s*(?:ال)?(?:ساق|رجل)",
               r"(?:فقط|بس)\s*(?:في\s*)?(?:ساق|رجل)", r"(?:one|single)\s+(?:leg|calf)", r"(?:right|left)\s+(?:leg|calf)", r"في\s*(?:ال)?(?:ساق|رجل)\s*(?:ال)?(?:واحده|وحده)")
_REDWARM = _rx(r"(?:احمرار|حمار|محمر\w*|سخونه|دافي\w*|redness|warm\w*)")
_SOB = _rx(r"(?:ضيق\s*(?:ال)?(?:نفس|تنفس)|نهجان|اهج|يقطع\s*نفسي|تقل\s*(?:ال)?نفس|صعوبه\s*(?:ال)?تنفس|صعوبه\s*في\s*(?:ال)?تنفس|short(?:ness)?\s+of\s+breath|breathless\w*|difficulty\s+breathing)")
_CHEST_PAIN = _rx(r"(?:الم|وجع|ضغط)\s*(?:في\s*)?(?:ال)?صدر", r"(?:ال)?صدر\w*\s*(?:يوجع|توجع|يعور|يؤلم|يضغط|ضاغط)\w*", r"chest\s+pain")
_COUGH_BLOOD = _rx(r"(?:سعال|كحه|كحة)\s*(?:مع\s*)?دم", r"دم\s*(?:مع|في)\s*(?:ال)?(?:سعال|كحه|بلغم)", r"coughing\s+(?:up\s+)?blood")
_OLD_APPENDIX = _rx(r"(?:شلت|ازلت|ازالو|ازالوا|استاصل\w*|استئصال|مستاصل\w*)\s*(?:ال)?(?:زايده|زائده)", r"(?:عمليه|عملية)\s*(?:ال)?(?:زايده|زائده)",
                    r"(?:ما|بدون|مافي)\s*(?:عندي)?\s*(?:ال)?(?:زايده|زائده)", r"(?:قبل|من)\s*(?:\d+\s*)?(?:سنه|سنين|سنوات|اشهر|شهور|زمان)",
                    r"years\s+ago|appendectomy|appendix\s+(?:removed|out)|no\s+appendix")
_RISK = _rx(r"(?:رحل\w*\s*(?:طويل\w*|سفر)|سفر\s*طويل|سفر\w*\s*(?:طويل|بالطياره)|جلوس\s*طويل|طيران\s*طويل|عمليه|جراحه|جبس|راقد|طريح|حبوب\s*منع|منع\s*(?:ال)?حمل|سرطان|long\s+(?:flight|trip|journey)|surgery|immobili\w*|cast)")


def _txt(patient, text):
    if text is None:
        symptoms = [str(x) for x in (patient.get("symptoms") or [])]
        text = " ; ".join(symptoms + [str(patient.get("notes") or "")])
    return text


def _infant_under_3m(patient, text):
    try:
        import analysis_core
        months = analysis_core._extract_age_months(None, text)  # text-only: age=0 alone is ambiguous
    except Exception:
        months = None
    if months is None:
        return False
    return months < 3


def evaluate(patient, text=None):
    out = {"emergency": [], "today": []}
    patient = patient or {}
    # Answers to the red-flag screening questions (ids validated against the bank).
    # No try/except: if this cannot run, the caller's safety check fails closed.
    import redflag_screen
    _em, _td = redflag_screen.resolve(patient.get("redflag_yes"))
    out["emergency"] += [("redflag_" + i, a, e) for i, a, e in _em]
    out["today"] += [("redflag_" + i, a, e) for i, a, e in _td]
    text = _txt(patient, text)
    t = clinical_text.normalize_clinical_text(text)
    if not t:
        return out
    try:
        sev = int(patient.get("severity") or 0)
    except (TypeError, ValueError):
        sev = 0
    old_appendix = _live(_OLD_APPENDIX, t)

    def emerg(rid, ar, en):
        out["emergency"].append((rid, ar, en))

    def today(rid, ar, en):
        out["today"].append((rid, ar, en))

    # 1. Fever in a baby younger than 3 months.
    if _live(_FEVER, t) and _infant_under_3m(patient, text):
        try:
            import analysis_core
            temp = analysis_core._extract_temperature_c(text)
        except Exception:
            temp = None
        if temp is None or temp >= 38.0:
            emerg("infant_fever_under_3m", "حرارة عند رضيع عمره أقل من 3 أشهر", "Fever in an infant younger than 3 months")

    # 2. Suspected appendicitis.
    appendix_pain = _live(_APPENDIX, t) and _live(_PAIN, t)
    rlq = _live(_RLQ, t)
    if (rlq or appendix_pain) and not old_appendix:
        warn = (_live(_FEVER, t) or _live(_VOMIT, t) or _live(_APPETITE, t) or _live(_MOVE, t)
                or sev >= 4 or _live(_PAIN_SEVERE, t))
        if warn or appendix_pain:
            emerg("suspected_appendicitis", "ألم أسفل البطن من الجهة اليمنى مع حرارة أو غثيان أو ألم شديد (اشتباه التهاب الزائدة)",
                  "Right lower abdominal pain with fever, nausea or severe pain (possible appendicitis)")
        else:
            today("right_lower_abdominal_pain", "ألم أسفل البطن من اليمين", "Right lower abdominal pain")

    # 3. Pain in pregnancy / pre-eclampsia warning signs.
    if _live(_PREG, t):
        pelvic_pain = _live(_PAIN, t) and (_live(_PELVIC, t) or _live(_ONE_SIDE, t) or _live(_SHOULDER, t))
        if pelvic_pain:
            if (_live(_ONE_SIDE, t) or _live(_DIZZY, t) or _live(_SHOULDER, t) or _live(_PREG_BLEED, t)
                    or _live(_PAIN_SEVERE, t) or sev >= 4):
                emerg("pregnancy_pain_warning",
                      "ألم في البطن أو الحوض أثناء الحمل مع علامة خطر (ألم حاد أو من جهة واحدة أو دوخة أو نزيف) — قد يكون حملًا خارج الرحم أو مضاعفات أخرى",
                      "Abdominal/pelvic pain in pregnancy with a warning sign (sharp or one-sided pain, dizziness or bleeding) - possible ectopic pregnancy or other complication")
            else:
                today("pregnancy_pain", "ألم في البطن أثناء الحمل", "Abdominal pain during pregnancy")
        if _live(_HEAD_SEVERE, t) and (_live(_VISION_BLUR, t) or _live(_UPPER_ABD, t) or _live(_FACE_SWELL, t)):
            emerg("preeclampsia_warning", "صداع شديد مع اضطراب الرؤية أو ألم أعلى البطن أو تورم الوجه أثناء الحمل (علامات تسمم الحمل)",
                  "Severe headache with visual disturbance, upper abdominal pain or facial swelling in pregnancy (pre-eclampsia warning signs)")

    # 4. One-leg swelling/pain with breathing symptoms (DVT / pulmonary embolism).
    leg = _live(_LEG, t)
    swelling = leg and _live(_SWELL, t)
    one_leg = _live(_ONE_LEG, t) or (swelling and not _live(_BOTH_LEGS, t) and (_live(_PAIN, t) or _live(_REDWARM, t)))
    breathing = _live(_SOB, t) or _live(_CHEST_PAIN, t) or _live(_COUGH_BLOOD, t)
    if leg and (swelling or _live(_REDWARM, t)) and one_leg:
        if breathing:
            emerg("dvt_pe_pattern", "تورم أو ألم في ساق واحدة مع ضيق نفس أو ألم صدر (اشتباه جلطة في الساق أو الرئة)",
                  "One-leg swelling or pain with breathlessness or chest pain (possible blood clot in the leg or lung)")
        else:
            today("possible_dvt", "تورم أو ألم في ساق واحدة" + (" مع عامل خطر للجلطات" if _live(_RISK, t) else ""),
                  "One-leg swelling or pain" + (" with a clot risk factor" if _live(_RISK, t) else ""))
    elif breathing and _live(_RISK, t) and leg and (_live(_PAIN, t) or swelling):
        emerg("dvt_pe_pattern", "ألم أو تورم في الساق مع ضيق نفس أو ألم صدر بعد عامل خطر للجلطات",
              "Leg pain or swelling with breathlessness or chest pain after a clot risk factor")
    return out
