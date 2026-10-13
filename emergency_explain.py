"""Plain-language explanation of WHY a result was flagged as an emergency:
which red flag matched, what the person entered that triggered it, and why that
pattern needs urgent care. Display only; it never changes the safety decision."""

import re

_WHY = {
    "severe_chest_pain": ("الألم أو الضغط الشديد في الصدر قد يكون من أعراض مشكلة قلبية أو رئوية حادة، ولا يمكن استبعادها دون فحص عاجل.",
                          "Severe chest pain or pressure can be a sign of an acute heart or lung problem that cannot be ruled out without urgent examination."),
    "chest_pain_cardiac_features": ("اجتماع ألم الصدر مع انتشاره أو التعرق أو ضيق النفس نمط يُعامل كمؤشر محتمل على مشكلة قلبية حتى يثبت العكس.",
                                    "Chest pain together with spreading pain, sweating or breathlessness is treated as a possible heart warning until proven otherwise."),
    "severe_breathing": ("صعوبة التنفس الشديدة قد تعني نقص الأكسجين أو مشكلة تنفسية أو قلبية حادة وتحتاج تقييمًا فوريًا.",
                         "Severe difficulty breathing can mean low oxygen or an acute lung or heart problem and needs immediate assessment."),
    "loss_of_consciousness": ("فقدان الوعي أو عدم الاستجابة قد يكون بسبب مشكلة في القلب أو الدماغ أو السكر، ولا يُنتظر معه تحليل الأعراض.",
                              "Loss of consciousness or unresponsiveness can come from a heart, brain or blood-sugar problem; symptom analysis should not delay care."),
    "stroke_pattern": ("الضعف أو التنميل المفاجئ في جهة واحدة، أو اضطراب الكلام أو الوجه، من العلامات المعروفة للسكتة الدماغية، والعلاج فيها حساس للوقت.",
                       "Sudden one-sided weakness or numbness, or speech or face changes, are known stroke signs, and treatment is time-sensitive."),
    "sudden_vision_loss": ("فقدان الرؤية المفاجئ قد يرتبط بمشكلة في الشبكية أو الأوعية أو الدماغ وتتوقف نتيجته على سرعة العلاج.",
                           "Sudden vision loss may involve the retina, blood vessels or brain, and the outcome depends on how fast it is treated."),
    "severe_bleeding": ("النزيف الشديد أو غير المتوقف قد يؤدي إلى فقدان دم خطير في وقت قصير.",
                        "Severe or uncontrolled bleeding can cause dangerous blood loss quickly."),
    "blood_vomit_or_cough": ("القيء أو السعال المصحوب بدم قد يدل على نزيف داخلي في الجهاز الهضمي أو التنفسي.",
                             "Vomiting or coughing blood can point to internal bleeding in the digestive or respiratory tract."),
    "anaphylaxis_pattern": ("تورم الفم أو الحلق مع صعوبة التنفس نمط لحساسية شديدة (أنافيلاكسيس) قد تُغلق معها المجاري التنفسية.",
                            "Mouth or throat swelling with breathing difficulty fits a severe allergic reaction (anaphylaxis) that can close the airway."),
    "prolonged_seizure": ("التشنج المستمر أو المطوّل حالة طارئة لأنه قد يضر الدماغ ويحتاج علاجًا فوريًا.",
                          "A prolonged seizure is an emergency because it can injure the brain and needs immediate treatment."),
    "active_seizure": ("التشنج الجاري الآن يحتاج حماية الشخص وطلب الإسعاف.",
                       "A seizure happening now needs the person protected and an ambulance called."),
    "self_harm_risk": ("ذكرتَ أفكارًا أو نية لإيذاء النفس، وسلامتك هي الأولوية الآن قبل أي تحليل. لست وحدك، والتواصل مع شخص تثق به أو جهة مختصة يساعد.",
                       "You mentioned thoughts or intent of self-harm. Your safety comes before any analysis. You are not alone; reaching out to someone you trust or a professional helps."),
    "overdose_poisoning": ("اشتباه الجرعة الزائدة أو التسمم قد يتطور بسرعة ويحتاج مركز سموم أو طوارئ فورًا.",
                           "Suspected overdose or poisoning can worsen quickly and needs poison control or emergency care right away."),
    "thunderclap_headache": ("الصداع المفاجئ الشديد جدًا (الأسوأ في الحياة) قد يرتبط بنزيف في الدماغ ويُفحص عاجلًا حتى لو زال سريعًا.",
                             "A sudden, worst-ever headache can be linked to bleeding in the brain and is checked urgently even if it fades."),
    "pregnancy_bleeding_severe": ("النزيف أثناء الحمل مع علامة خطر شديدة قد يهدد الأم والجنين ويحتاج تقييمًا فوريًا.",
                                  "Bleeding in pregnancy with a severe warning sign can threaten mother and baby and needs immediate assessment."),
    "infant_fever_under_3m": ("الحمى في رضيع عمره أقل من 3 أشهر تُعامل كحالة عاجلة لأن العدوى قد تتطور بسرعة عند هذا العمر.",
                              "Fever in a baby under 3 months is treated as urgent because infection can progress quickly at this age."),
    "clarification_red_flag": ("إجابتك عن سؤال فحص علامات الخطر أظهرت علامة تحتاج تقييمًا عاجلًا، فتوقفنا عن مطابقة الأمراض.",
                               "Your answer to a warning-sign question showed a sign that needs urgent assessment, so we stopped matching conditions."),
}
_GENERIC = ("هذه العلامة من العلامات التي لا يُنتظر معها تحليل الأعراض، لأن التأخير فيها قد يكون خطيرًا.",
            "This is a sign for which symptom analysis should not delay care, because delay could be dangerous.")


def _clean(x):
    x = re.sub(r"[^\w\s\-/,.()'\u0600-\u06FF]", " ", str(x or ""), flags=re.UNICODE).replace("_", " ")
    return " ".join(x.split())


def _inputs(patient, ar):
    patient = patient or {}
    syms = [c for c in (_clean(s) for s in (patient.get("symptoms") or [])) if c][:5]
    notes = " ".join(str(patient.get("notes") or "").split())[:100]
    parts = []
    if syms:
        parts.append(("الأعراض: " if ar else "symptoms: ") + ("، " if ar else ", ").join(syms))
    if notes:
        parts.append(("ملاحظتك: «" if ar else "your note: “") + notes + ("»" if ar else "”"))
    return ("؛ " if ar else "; ").join(parts)


def reasons(safety, lang="ar", patient=None):
    """Return (risk_reasons list, why_result text) for an emergency result."""
    ar = lang != "en"
    flags = list((safety or {}).get("flags") or [])
    ids = list((safety or {}).get("rule_ids") or [])
    seen = _inputs(patient, ar)
    out = []
    for i, flag in enumerate(flags):
        rid = ids[i] if i < len(ids) else ""
        why = _WHY.get(rid, _GENERIC)[0 if ar else 1]
        if ar:
            lead = f"ما أدخلتَه ({seen}) طابق علامة الخطر «{flag}». " if seen else f"طابقت إجاباتك علامة الخطر «{flag}». "
        else:
            lead = f"What you entered ({seen}) matched the red flag “{flag}”. " if seen else f"Your answers matched the red flag “{flag}”. "
        out.append({"name": flag, "message": lead + why, "risk_level": "urgent", "slug": rid or "red-flag"})
    why_result = "\n".join(r["message"] for r in out)
    return out, why_result
