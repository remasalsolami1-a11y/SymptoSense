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
    # compositional concept rules (red_flag_concepts.py)
    "concept_anaphylaxis": ("تورم الفم أو الوجه أو الطفح المنتشر مع ضيق التنفس أو الدوخة نمط لحساسية شديدة (أنافيلاكسيس) قد تتطور خلال دقائق.",
                            "Mouth or face swelling or widespread hives with breathing difficulty or dizziness fits a severe allergic reaction (anaphylaxis) that can worsen within minutes."),
    "concept_gi_bleed": ("البراز الأسود مع الدوخة أو الإغماء أو الضعف قد يدل على نزيف في الجهاز الهضمي العلوي.",
                         "Black stool with dizziness, fainting or weakness can mean bleeding in the upper digestive tract."),
    "concept_head_injury": ("بعد إصابة الرأس، القيء المتكرر أو النعاس أو التشوش علامات قد تدل على نزيف داخل الجمجمة وتحتاج تقييمًا فوريًا.",
                            "After a head injury, repeated vomiting, drowsiness or confusion can signal bleeding inside the skull and need immediate assessment."),
    "concept_acute_abdomen": ("ألم البطن الشديد مع تيبّسه أو القيء المستمر قد يدل على حالة جراحية طارئة مثل الانثقاب أو الانسداد.",
                              "Severe abdominal pain with a rigid belly or persistent vomiting can point to a surgical emergency such as perforation or obstruction."),
    "concept_testicular_torsion": ("ألم الخصية المفاجئ أو الشديد قد يكون التواءً في الخصية، وإنقاذها يعتمد على العلاج خلال ساعات.",
                                   "Sudden or severe testicular pain can be torsion, and saving the testicle depends on treatment within hours."),
    "concept_diabetic_emergency": ("عند مريض السكري، التشوش أو التنفس السريع العميق أو القيء قد يدل على حماض كيتوني أو اضطراب سكر خطير.",
                                   "In someone with diabetes, confusion, fast deep breathing or vomiting can signal ketoacidosis or a dangerous sugar disturbance."),
    "concept_severe_asthma": ("نوبة الربو التي لا تتحسن بالبخاخ الإسعافي قد تكون نوبة شديدة تحتاج علاجًا في الطوارئ.",
                              "An asthma attack that does not improve with the reliever inhaler may be severe and need emergency treatment."),
    "concept_meningitis": ("الحمى مع تيبّس الرقبة أو الصداع الشديد أو التشوش من علامات التهاب السحايا، وهو حساس جدًا للوقت.",
                           "Fever with a stiff neck, severe headache or confusion are signs of meningitis, which is very time-sensitive."),
    "concept_bleeding_shock": ("النزيف الغزير مع الضعف أو الدوخة أو الإغماء قد يعني أن الجسم فقد كمية خطيرة من الدم.",
                               "Heavy bleeding with weakness, dizziness or fainting can mean a dangerous amount of blood has been lost."),
    "concept_sudden_vision_loss": ("فقدان الرؤية المفاجئ قد يرتبط بانسداد وعاء دموي أو انفصال الشبكية أو سكتة، ونتيجته تعتمد على سرعة العلاج.",
                                   "Sudden vision loss can come from a blocked vessel, retinal detachment or stroke, and the outcome depends on fast treatment."),
    "concept_cardiac_chest": ("ألم الصدر الشديد أو المصحوب بتعرّق أو انتشار أو ضيق نفس يُعامل كمؤشر محتمل على جلطة قلبية حتى يثبت العكس.",
                              "Chest pain that is severe or comes with sweating, spreading pain or breathlessness is treated as a possible heart attack until proven otherwise."),
    # V287 error-taxonomy rules
    "concept_respiratory_distress": ("ازرقاق الشفاه أو عدم القدرة على إكمال جملة من ضيق النفس أو سيلان اللعاب علامات أن الجسم لا يحصل على هواء كافٍ.",
                                     "Blue lips, being too breathless to finish a sentence, or drooling are signs the body is not getting enough air."),
    "concept_reduced_consciousness": ("نقص الاستجابة أو صعوبة الإيقاظ قد يدل على مشكلة خطيرة في الدماغ أو الدم أو الأكسجين، ويحتاج تقييمًا فوريًا.",
                                      "Reduced responsiveness or being hard to wake can signal a serious problem with the brain, blood or oxygen and needs immediate assessment."),
    "concept_sepsis": ("الحمى مع التشوش أو نقص الوعي، أو الطفح البنفسجي الذي لا يختفي بالضغط، من علامات تسمم الدم أو التهاب السحايا، وهي حالات حساسة للوقت.",
                       "Fever with confusion or reduced consciousness, or a purple rash that does not fade when pressed, are signs of sepsis or meningitis, which are time-critical."),
    "concept_cardiac_syncope": ("الإغماء أثناء المجهود أو مع ألم الصدر أو النبض غير المنتظم قد يكون سببه اضطرابًا خطيرًا في القلب.",
                                "Fainting during exertion, or with chest pain or an irregular heartbeat, can be caused by a dangerous heart rhythm or heart problem."),
    "concept_severe_dehydration": ("فقدان السوائل مع قلة البول والتشوش أو النعاس علامات جفاف شديد يحتاج سوائل وريدية.",
                                   "Losing fluids with little urine and confusion or drowsiness are signs of severe dehydration that may need intravenous fluids."),
    "concept_acute_glaucoma": ("ألم العين الشديد المفاجئ مع تشوش الرؤية أو القيء قد يكون ارتفاعًا حادًا في ضغط العين يهدد البصر خلال ساعات.",
                               "Sudden severe eye pain with blurred vision or vomiting can be acute glaucoma, which can threaten sight within hours."),
    "concept_cauda_equina": ("فقدان التحكم بالبول أو الخدر حول المقعدة مع ألم الظهر أو ضعف الساقين قد يعني ضغطًا على أعصاب أسفل الظهر يحتاج جراحة عاجلة.",
                             "Loss of bladder control or saddle numbness with back pain or leg weakness can mean pressure on the lower spinal nerves that needs urgent surgery."),
    "concept_limb_ischaemia": ("الطرف الذي يبرد فجأة ويشحب أو يخدر قد يكون انقطع عنه الدم، وإنقاذه يعتمد على الساعات الأولى.",
                               "A limb that suddenly turns cold and pale or numb may have lost its blood supply, and saving it depends on the first hours."),
    "concept_thunderclap_headache": ("الصداع المفاجئ الشديد أو «الأسوأ في حياتك» قد يكون نزيفًا في الدماغ ويحتاج تقييمًا فوريًا.",
                                     "A sudden severe or worst-ever headache can be a bleed in the brain and needs immediate assessment."),
    "concept_infant_bilious_vomit": ("القيء الأخضر عند الرضيع قد يعني انسدادًا أو التواءً في الأمعاء، وهي حالة جراحية طارئة.",
                                     "Green vomit in a baby can mean a blocked or twisted bowel, which is a surgical emergency."),
    "concept_stroke_speech": ("ثقل الكلام المفاجئ من علامات السكتة الدماغية (FAST)، وكل دقيقة تفرق.",
                              "Sudden slurred speech is a stroke sign (FAST), and every minute counts."),
    "concept_stroke_fast": ("ميلان الوجه أو عدم القدرة على رفع الذراع فجأة من علامات السكتة الدماغية (FAST)، وكل دقيقة تفرق.",
                            "Sudden facial droop or inability to lift an arm are stroke signs (FAST), and every minute counts."),
    # V290
    "concept_cannot_breathe": ("عدم القدرة على التنفس حالة إسعافية؛ اتصل بالإسعاف (997) فورًا.",
                               "Not being able to breathe is an emergency; call an ambulance (997) now."),
    "concept_choking": ("الاختناق مع عدم القدرة على التنفس أو الكلام أو السعال يعني أن مجرى الهواء مسدود؛ اطلب الإسعاف وابدأ ضربات الظهر.",
                        "Choking with no breathing, speaking or coughing means the airway is blocked; call an ambulance and start back blows."),
    "concept_dangerous_ingestion": ("بطاريات الأزرار والمغناطيس والمواد الكيميائية تسبب حروقًا أو ثقوبًا داخلية خلال ساعات؛ اذهب للطوارئ فورًا ولا تحاول التقيؤ.",
                                    "Button batteries, magnets and household chemicals can burn or pierce the gut within hours; go to the emergency department now and do not make the person vomit."),
    "concept_overdose": ("الجرعة الزائدة من الدواء (حتى البنادول) قد تضر الكبد أو القلب قبل ظهور أعراض؛ اذهب للطوارئ فورًا وخذ العلبة معك.",
                         "An overdose of medicine (even paracetamol) can harm the liver or heart before symptoms appear; go to the emergency department now and take the packet with you."),
    "concept_serious_burn": ("الحرق الكبير أو العميق أو الكهربائي أو الكيميائي، أو الحرق بفقاعات في الوجه أو اليدين، يحتاج الطوارئ. برّده بماء جارٍ فاتر 20 دقيقة.",
                             "A large, deep, electrical or chemical burn, or a blistering burn on the face or hands, needs the emergency department. Cool it under cool running water for 20 minutes."),
    "concept_fracture_deformity": ("الطرف المشوّه الشكل أو العظم الظاهر بعد إصابة، أو كبير السن الذي لا يستطيع القيام بعد سقوط، علامة كسر يحتاج الطوارئ. لا تحرّك الطرف.",
                                   "A deformed limb or visible bone after an injury, or an older person who cannot get up after a fall, suggests a fracture that needs the emergency department. Do not move the limb."),
    "concept_chest_crushing": ("الإحساس بعصر أو ثقل كبير على الصدر من أشهر أوصاف الجلطة القلبية؛ اتصل بالإسعاف (997).",
                               "A crushing or squeezing weight on the chest is a classic description of a heart attack; call an ambulance (997)."),
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


def _evidence(items, ar):
    """[{concept, label, quotes:[str]}] using the words the user actually typed."""
    out = []
    for e in items or []:
        quotes = []
        for q in e.get("quotes") or []:
            t = " ".join(str(q.get("text") or "").split())[:60]
            if t and t not in quotes:
                quotes.append(t)
        if quotes:
            out.append({"concept": e.get("concept", ""), "label": e.get("label_ar" if ar else "label_en", ""), "quotes": quotes[:2]})
    return out


def _quoted_lead(flag, ev, ar):
    if ar:
        parts = "، و".join("«" + "» و«".join(e["quotes"]) + "» (" + e["label"] + ")" for e in ev)
        return f"كتبتَ {parts}، وهذا يطابق علامة الخطر «{flag}». "
    parts = ", and ".join("“" + "” and “".join(e["quotes"]) + "” (" + e["label"] + ")" for e in ev)
    return f"You wrote {parts}, which matches the red flag “{flag}”. "


def _rule_pairs(safety):
    """(rule_id, label) pairs. Flags are de-duplicated by label, so pair rule ids with their
    own label when the engine provides it rather than by list position."""
    flags = list(safety.get("flags") or [])
    ids = list(safety.get("rule_ids") or [])
    labels = safety.get("rule_labels") or {}
    if labels:
        pairs, seen = [], set()
        for rid in ids:
            label = labels.get(rid)
            if label and label not in seen:
                seen.add(label)
                pairs.append((rid, label))
        pairs += [("", f) for f in flags if f not in seen]
        return pairs
    return [(ids[i] if i < len(ids) else "", f) for i, f in enumerate(flags)]


def reasons(safety, lang="ar", patient=None):
    """Return (risk_reasons list, why_result text) for an emergency result.

    When the concept layer supplies evidence, the reason quotes the user's own words for
    each concept the rule used (faithful: quotes are slices of what was typed). Otherwise
    it falls back to echoing the inputs."""
    ar = lang != "en"
    safety = safety or {}
    evidence = safety.get("evidence") or {}
    seen = _inputs(patient, ar)
    out = []
    for rid, flag in _rule_pairs(safety):
        why = _WHY.get(rid, _GENERIC)[0 if ar else 1]
        ev = _evidence(evidence.get(rid), ar)
        if ev:
            lead = _quoted_lead(flag, ev, ar)
        elif ar:
            lead = f"ما أدخلتَه ({seen}) طابق علامة الخطر «{flag}». " if seen else f"طابقت إجاباتك علامة الخطر «{flag}». "
        else:
            lead = f"What you entered ({seen}) matched the red flag “{flag}”. " if seen else f"Your answers matched the red flag “{flag}”. "
        out.append({"name": flag, "message": lead + why, "risk_level": "urgent", "slug": rid or "red-flag",
                    "rule_id": rid, "evidence": ev,
                    "source": ("قاعدة أمان ثابتة (لا تعتمد على الذكاء الاصطناعي)" if ar
                               else "Fixed safety rule (does not use AI)")})
    why_result = "\n".join(r["message"] for r in out)
    return out, why_result
