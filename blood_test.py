# -*- coding: utf-8 -*-
"""Blood test (CBC) parsing + awareness analysis for SymptoSense.
Awareness only - NOT a diagnosis. Reference ranges may vary by laboratory.
"""
import io
import re

REFS = {
    "hgb": ("هيموغلوبين", "Hemoglobin", "g/dL", (13.5, 17.5, 12.0, 15.5)),
    "wbc": ("كريات بيضاء", "WBC", "10^9/L", (4.0, 11.0, 4.0, 11.0)),
    "rbc": ("كريات حمراء", "RBC", "10^6/uL", (4.7, 6.1, 4.2, 5.4)),
    "hct": ("الهيماتوكريت", "Hematocrit", "%", (40.0, 54.0, 36.0, 48.0)),
    "mcv": ("متوسط حجم الكرية", "MCV", "fL", (80.0, 100.0, 80.0, 100.0)),
    "mch": ("متوسط هيموغلوبين الكرية", "MCH", "pg", (27.0, 33.0, 27.0, 33.0)),
    "mchc": ("متوسط تركيز الهيموغلوبين", "MCHC", "g/dL", (32.0, 36.0, 32.0, 36.0)),
    "plt": ("الصفائح", "Platelets", "10^9/L", (150.0, 400.0, 150.0, 400.0)),
    "neut": ("العدلات", "Neutrophils", "%", (40.0, 60.0, 40.0, 60.0)),
    "lymph": ("اللمفاويات", "Lymphocytes", "%", (20.0, 40.0, 20.0, 40.0)),
    "rdw": ("RDW", "RDW", "%", (11.5, 14.5, 11.5, 14.5)),
}

SYNONYMS = {
    "hgb": ["هيموغلوبين الدم", "هيموغلوبين", "هيموجلوبين", "hemoglobin", "haemoglobin", "hgb", "هب", "hb"],
    "wbc": ["كريات بيضاء", "خلايا بيضاء", "الخلايا البيضاء", "البيضاء", "white blood cell", "white cells", "wbc"],
    "rbc": ["كريات حمراء", "خلايا حمراء", "الخلايا الحمراء", "الحمراء", "red blood cell", "red cells", "rbc"],
    "hct": ["الهيماتوكريت", "هيماتوكريت", "hematocrit", "packed cell", "hct", "pcv"],
    "mcv": ["متوسط حجم الكرية", "mcv"],
    "mch": ["متوسط هيموغلوبين الكرية", "متوسط الهيموغلوبين الكرية", "mch"],
    "mchc": ["متوسط تركيز الهيموغلوبين", "mchc"],
    "plt": ["الصفائح", "صفائح", "البلاتين", "platelet", "platelets", "plt"],
    "neut": ["العدلات", "عدلات", "neutrophil", "neutrophils", "neut"],
    "lymph": ["اللمفاويات", "لمفاويات", "lymphocyte", "lymphocytes", "lymph"],
    "rdw": ["توزيع الكريات الحمراء", "rdw"],
}

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

# Emergency thresholds: (level, when value crosses).
DANGER_RULES = {
    "hgb": [("emergency", 5.0, "lt"), ("urgent", 7.0, "lt")],
    "plt": [("emergency", 10.0, "lt"), ("urgent", 20.0, "lt")],
    "wbc": [("urgent", 30.0, "gt"), ("urgent", 1.0, "lt")],
}


def _norm(text):
    return re.sub(r"\s+", " ", str(text)).translate(_AR_DIGITS).lower()


def parse_blood_text(text):
    """Extracts (key, value) pairs + optional child age from free text.
    Returns (entries, age_or_None)."""
    if not text:
        return [], None
    t = _norm(text)
    age = None
    m = re.search(r"(?:طفل|طفلة|child|age)\s*[:=]?\s*(\d+)", t)
    if m:
        age = int(m.group(1))
    entries = []
    for key, syns in SYNONYMS.items():
        for syn in sorted(syns, key=len, reverse=True):
            pos = t.find(syn)
            if pos == -1:
                continue
            after = t[pos + len(syn): pos + len(syn) + 14]
            nums = re.findall(r"\d+(?:[.,]\d+)?", after)
            if nums:
                entries.append((key, float(nums[0].replace(",", "."))))
                break
    return entries, age


def analyze_blood(entries, gender="f", age=None):
    """Runs values against adult reference ranges (gender-aware).
    Returns (results, notes, dangers, level, child_note)."""
    is_male = str(gender).lower().startswith("m")
    results = []
    for key, value in entries:
        if key not in REFS:
            continue
        name_ar, name_en, unit, (lm, hm, lf, hf) = REFS[key]
        low = lm if is_male else lf
        high = hm if is_male else hf
        if value < low:
            status = "low"
        elif value > high:
            status = "high"
        else:
            status = "normal"
        results.append({"key": key, "name_ar": name_ar, "name_en": name_en,
                        "unit": unit, "value": value, "low": low, "high": high,
                        "status": status})
    by = {r["key"]: r for r in results}

    notes = []      # list of (ar, en)
    dangers = []    # list of (level, ar, en)

    h = by.get("hgb")
    mcv = by.get("mcv")
    wbc = by.get("wbc")
    plt = by.get("plt")
    neut = by.get("neut")
    lymph = by.get("lymph")

    if h and h["status"] == "low":
        if mcv and mcv["value"] < mcv["low"]:
            notes.append(("قد يشير النمط إلى فقر دم صغير الكريات (نقص الحديد هو الأكثر شيوعاً) — راجع طبيبك لفحص الفيريتين",
                          "The pattern may indicate microcytic anemia (iron deficiency is most common) — see your doctor to check ferritin"))
        elif mcv and mcv["value"] > mcv["high"]:
            notes.append(("قد يشير النمط إلى فقر دم كبير الكريات (نقص B12 أو حمض الفوليك محتمل) — راجع طبيبك",
                          "The pattern may indicate macrocytic anemia (possible B12/folate deficiency) — see your doctor"))
        else:
            notes.append(("قد تشير النتيجة إلى فقر دم (أنيميا) — راجع طبيبك لتحديد السبب",
                          "The result may indicate anemia — see your doctor to determine the cause"))
    if h and h["status"] == "high":
        notes.append(("قد تشير النتيجة إلى ارتفاع الهيموغلوبين (قد يكون جفاف أو سبباً آخر) — راجع طبيبك",
                      "The result may indicate high hemoglobin (could be dehydration or another cause) — see your doctor"))
    if wbc and wbc["status"] == "high":
        if neut and neut["value"] > neut["high"]:
            notes.append(("قد يشير ارتفاع كريات الدم البيضاء مع ارتفاع العدلات إلى التهاب أو عدوى (غالباً بكتيرية)",
                          "High WBC with high neutrophils may indicate infection/inflammation, often bacterial"))
        elif lymph and lymph["value"] > lymph["high"]:
            notes.append(("قد يشير ارتفاع كريات الدم البيضاء مع ارتفاع اللمفاويات إلى عدوى فيروسية محتملة",
                          "High WBC with high lymphocytes may indicate a possible viral infection"))
        else:
            notes.append(("قد يشير ارتفاع كريات الدم البيضاء إلى التهاب أو عدوى محتملة",
                          "High WBC may indicate possible infection or inflammation"))
    if wbc and wbc["status"] == "low":
        notes.append(("قد يشير انخفاض كريات الدم البيضاء إلى عدوى فيروسية أو سبب آخر؛ راجع طبيبك لو استمر",
                      "Low WBC may indicate a viral infection or another cause; see a doctor if it persists"))
    if plt and plt["status"] == "low":
        notes.append(("قد يشير انخفاض الصفائح إلى الحاجة لتقييم خطر النزف — راجع طبيبك",
                      "Low platelets may indicate the need to evaluate bleeding risk — see your doctor"))
    if plt and plt["status"] == "high":
        notes.append(("قد يشير ارتفاع الصفائح إلى الحاجة لتقييم السبب — راجع طبيبك",
                      "High platelets may indicate the need to evaluate the cause — see your doctor"))

    for key, rules in DANGER_RULES.items():
        r = by.get(key)
        if not r:
            continue
        for level, threshold, op in rules:
            crossed = r["value"] < threshold if op == "lt" else r["value"] > threshold
            if not crossed:
                continue
            if key == "hgb":
                if level == "emergency":
                    dangers.append((level, "🚨🚨 فقر دم خطير — طوارئ فورية", "🚨🚨 Critical anemia — immediate emergency"))
                else:
                    dangers.append((level, "🚨 فقر دم شديد جداً — تحتاجين تقييماً فورياً (نقل دم محتمل) — توجهي للطوارئ",
                                    "🚨 Severe anemia — needs immediate evaluation (possible transfusion) — go to the ER"))
            elif key == "plt":
                if level == "emergency":
                    dangers.append((level, "🚨🚨 صفائح حرجة — طوارئ فورية", "🚨🚨 Critical platelets — immediate emergency"))
                else:
                    dangers.append((level, "🚨 صفائح منخفضة جداً — خطر نزف — توجهي للطوارئ",
                                    "🚨 Very low platelets — bleeding risk — go to the ER"))
            elif key == "wbc":
                if threshold > 10:
                    dangers.append((level, "🚨 كريات بيضاء مرتفعة جداً — تحتاجين تقييماً طبياً قريباً",
                                    "🚨 Very high WBC — needs prompt medical evaluation"))
                else:
                    dangers.append((level, "🚨 كريات بيضاء منخفضة جداً — تحتاجين تقييماً فورياً",
                                    "🚨 Very low WBC — needs immediate evaluation"))
            break

    if any(d[0] == "emergency" for d in dangers):
        level = "emergency"
    elif any(d[0] == "urgent" for d in dangers):
        level = "urgent"
    elif notes or any(r["status"] != "normal" for r in results):
        level = "see_doctor"
    else:
        level = "normal"

    child_note = age is not None and int(age) < 18
    return results, notes, dangers, level, child_note


def build_text(results, gender, lang="ar", notes=None, dangers=None, child_note=False):
    """Builds the readable report message (plain text, no HTML)."""
    notes = notes or []
    dangers = dangers or []
    is_male = str(gender).lower().startswith("m")
    if lang == "en":
        gen = "Male" if is_male else "Female"
        lines = ["🩸 <b>Blood Test Report</b>", f"Reference: {gen} (adult)", ""]
        status_ar = {"normal": "Normal ✅", "low": "Low 🔻", "high": "High 🔺"}
        for r in results:
            lines.append(f"{r['name_en']}: {r['value']} ({r['low']}-{r['high']}) {status_ar[r['status']]}")
        if notes:
            lines += ["", "📋 <b>Notes:</b>"] + [f"• {n[1]}" for n in notes]
        if dangers:
            lines += ["", "🚨 <b>Alert:</b>"] + [d[2] for d in dangers]
        if child_note:
            lines += ["", "👶 Pediatric ranges differ from adult ranges — please show the report to a pediatrician."]
        lines += ["", "⚠️ Awareness only — not a diagnosis. Ranges vary by lab; confirm any result with your doctor."]
    else:
        gen = "ذكر" if is_male else "أنثى"
        lines = ["🩸 <b>تحليل الدم</b>", f"المرجع: {gen} (بالغ)", ""]
        status_ar = {"normal": "طبيعي ✅", "low": "منخفض 🔻", "high": "مرتفع 🔺"}
        for r in results:
            lines.append(f"{r['name_ar']}: {r['value']} ({r['low']}-{r['high']}) {status_ar[r['status']]}")
        if notes:
            lines += ["", "📋 <b>ملاحظات:</b>"] + [f"• {n[0]}" for n in notes]
        if dangers:
            lines += ["", "🚨 <b>تنبيه:</b>"] + [d[1] for d in dangers]
        if child_note:
            lines += ["", "👶 نطاقات الأطفال تختلف عن نطاقات البالغين — ننصح بعرض النتيجة على طبيب أطفال."]
        lines += ["", "⚠️ توعية فقط — ليس تشخيصاً طبياً. النطاقات تختلف حسب المختبر، وراجعي طبيبك لتأكيد أي نتيجة."]
    return "\n".join(lines)


# ---------------------------------------------------------------- structured card data
INDICATOR_INFO = {
    "hgb": {
        "what_ar": "البروتين الحامل للأكسجين داخل كريات الدم الحمراء.",
        "what_en": "The oxygen-carrying protein inside red blood cells.",
        "low_ar": "قد تشير النتيجة إلى انخفاض الهيموغلوبين (فقر دم محتمل). لا يعني ذلك بالضرورة وجود مرض — راجع طبيبك لتحديد السبب.",
        "low_en": "The result may indicate low hemoglobin (possible anemia). It doesn't necessarily mean a disease — see your doctor to determine the cause.",
        "high_ar": "قد تشير النتيجة إلى ارتفاع الهيموغلوبين، وقد يرتبط بالجفاف أو عوامل أخرى — راجع طبيبك للتحقق.",
        "high_en": "The result may indicate high hemoglobin, possibly linked to dehydration or other factors — see your doctor to check.",
        "when_ar": "راجع طبيبك إذا استمر الانخفاض أو رافقته دوخة، تعب، شحوب، أو تسارع نبض.",
        "when_en": "See your doctor if the low level persists or comes with dizziness, fatigue, paleness, or a fast heartbeat.",
    },
    "wbc": {
        "what_ar": "كريات الدم البيضاء — خلايا المناعة التي تحارب العدوى.",
        "what_en": "White blood cells — immune cells that fight infection.",
        "low_ar": "قد تشير النتيجة إلى انخفاض كريات الدم البيضاء، وقد يرتبط بعدوى فيروسية أو أسباب أخرى.",
        "low_en": "The result may indicate low white blood cells, possibly linked to a viral infection or other causes.",
        "high_ar": "قد تشير النتيجة إلى ارتفاع كريات الدم البيضاء، وغالباً ما يرتبط بالتهاب أو عدوى.",
        "high_en": "The result may indicate high white blood cells, often linked to infection or inflammation.",
        "when_ar": "راجع طبيبك إذا رافقت النتيجة حمى، ألم، أو عدوى متكررة، أو إذا استمر الارتفاع.",
        "when_en": "See your doctor if the result comes with fever, pain, or repeated infections, or if the high level persists.",
    },
    "rbc": {
        "what_ar": "كريات الدم الحمراء — الخلايا الحاملة للأكسجين.",
        "what_en": "Red blood cells — the cells that carry oxygen.",
        "low_ar": "قد تشير النتيجة إلى انخفاض عدد كريات الدم الحمراء، وقد يرتبط بفقر دم أو أسباب أخرى.",
        "low_en": "The result may indicate a low red blood cell count, possibly linked to anemia or other causes.",
        "high_ar": "قد تشير النتيجة إلى ارتفاع عدد كريات الدم الحمراء، وقد يرتبط بالجفاف أو عوامل أخرى.",
        "high_en": "The result may indicate a high red blood cell count, possibly linked to dehydration or other factors.",
        "when_ar": "راجع طبيبك إذا رافق الانخفاض تعب أو دوخة، أو إذا استمرت النتيجة خارج النطاق.",
        "when_en": "See your doctor if the low count comes with fatigue or dizziness, or if the result stays out of range.",
    },
    "hct": {
        "what_ar": "نسبة كريات الدم الحمراء في حجم الدم الكلي.",
        "what_en": "The proportion of red blood cells in total blood volume.",
        "low_ar": "قد تشير النتيجة إلى انخفاض الهيماتوكريت، وقد يرتبط بفقر دم أو نزيف خفيف.",
        "low_en": "The result may indicate a low hematocrit, possibly linked to anemia or mild bleeding.",
        "high_ar": "قد تشير النتيجة إلى ارتفاع الهيماتوكريت، وقد يرتبط بالجفاف أو أسباب أخرى.",
        "high_en": "The result may indicate a high hematocrit, possibly linked to dehydration or other causes.",
        "when_ar": "راجع طبيبك إذا رافق الانخفاض دوخة أو تعب، أو إذا كانت النتيجة خارج النطاق مع أعراض.",
        "when_en": "See your doctor if the low result comes with dizziness or fatigue, or if it's out of range with symptoms.",
    },
    "mcv": {
        "what_ar": "متوسط حجم كرية الدم الحمراء الواحدة.",
        "what_en": "The average size of a single red blood cell.",
        "low_ar": "قد تشير النتيجة إلى صغر حجم الكريات، وهو شائع مع نقص الحديد.",
        "low_en": "The result may indicate small red cells, common with iron deficiency.",
        "high_ar": "قد تشير النتيجة إلى كبر حجم الكريات، وقد يرتبط بنقص فيتامين ب12 أو حمض الفوليك.",
        "high_en": "The result may indicate large red cells, possibly linked to vitamin B12 or folate deficiency.",
        "when_ar": "راجع طبيبك إذا كانت النتيجة خارج النطاق مع فقر دم أو أعراض تعب.",
        "when_en": "See your doctor if the result is out of range with anemia or fatigue symptoms.",
    },
    "mch": {
        "what_ar": "متوسط كمية الهيموغلوبين داخل الكرية الواحدة.",
        "what_en": "Average hemoglobin amount inside one red blood cell.",
        "low_ar": "قد تشير النتيجة إلى انخفاض كمية الهيموغلوبين في الكريات، وغالباً ما يرتبط بنقص الحديد.",
        "low_en": "The result may indicate low hemoglobin per cell, often linked to iron deficiency.",
        "high_ar": "قد تشير النتيجة إلى ارتفاع كمية الهيموغلوبين في الكريات.",
        "high_en": "The result may indicate a high hemoglobin amount per cell.",
        "when_ar": "راجع طبيبك إذا رافقت النتيجة أعراض فقر دم مثل التعب أو الشحوب.",
        "when_en": "See your doctor if the result comes with anemia symptoms like fatigue or paleness.",
    },
    "mchc": {
        "what_ar": "متوسط تركيز الهيموغلوبين داخل الكريات.",
        "what_en": "Average hemoglobin concentration inside the red cells.",
        "low_ar": "قد تشير النتيجة إلى انخفاض تركيز الهيموغلوبين، وقد يرتبط بفقر دم.",
        "low_en": "The result may indicate a low hemoglobin concentration, possibly linked to anemia.",
        "high_ar": "قد تشير النتيجة إلى ارتفاع تركيز الهيموغلوبين، وهو نادر ويحتاج تقييماً.",
        "high_en": "The result may indicate a high hemoglobin concentration, which is rare and needs evaluation.",
        "when_ar": "راجع طبيبك إذا كانت النتيجة خارج النطاق مع أعراض تعب أو شحوب.",
        "when_en": "See your doctor if the result is out of range with fatigue or paleness.",
    },
    "plt": {
        "what_ar": "الصفائح الدموية — خلايا تساعد على تخثر الدم ووقف النزيف.",
        "what_en": "Platelets — cells that help blood clot and stop bleeding.",
        "low_ar": "قد تشير النتيجة إلى انخفاض الصفائح، وقد يزيد ذلك من خطر النزف.",
        "low_en": "The result may indicate low platelets, which may increase bleeding risk.",
        "high_ar": "قد تشير النتيجة إلى ارتفاع الصفائح، وقد يرتبط بالتهاب أو عوامل أخرى.",
        "high_en": "The result may indicate high platelets, possibly linked to inflammation or other factors.",
        "when_ar": "راجع الطبيب فوراً إذا كانت الصفائح منخفضة جداً أو رافقتها كدمات أو نزيف بلا سبب.",
        "when_en": "See your doctor promptly if platelets are very low or come with unexplained bruising or bleeding.",
    },
    "neut": {
        "what_ar": "نسبة العدلات — النوع الأكثر شيوعاً من كريات الدم البيضاء.",
        "what_en": "Neutrophil percentage — the most common type of white blood cells.",
        "low_ar": "قد تشير النتيجة إلى انخفاض العدلات، وقد يرتبط بعدوى فيروسية أو أسباب أخرى.",
        "low_en": "The result may indicate low neutrophils, possibly linked to a viral infection or other causes.",
        "high_ar": "قد تشير النتيجة إلى ارتفاع العدلات، وغالباً ما يرتبط بعدوى بكتيرية أو التهاب.",
        "high_en": "The result may indicate high neutrophils, often linked to bacterial infection or inflammation.",
        "when_ar": "راجع طبيبك إذا رافقت النتيجة حمى أو ألم، أو إذا كانت خارج النطاق مع أعراض.",
        "when_en": "See your doctor if the result comes with fever or pain, or if it's out of range with symptoms.",
    },
    "lymph": {
        "what_ar": "نسبة اللمفاويات — نوع من كريات الدم البيضاء مهم للمناعة.",
        "what_en": "Lymphocyte percentage — a type of white blood cell important for immunity.",
        "low_ar": "قد تشير النتيجة إلى انخفاض اللمفاويات، وقد يرتبط بإجهاد أو عدوى أو أسباب أخرى.",
        "low_en": "The result may indicate low lymphocytes, possibly linked to stress, infection, or other causes.",
        "high_ar": "قد تشير النتيجة إلى ارتفاع اللمفاويات، وقد يرتبط بعدوى فيروسية.",
        "high_en": "The result may indicate high lymphocytes, possibly linked to a viral infection.",
        "when_ar": "راجع طبيبك إذا كانت النتيجة خارج النطاق بشكل واضح أو رافقها أعراض مستمرة.",
        "when_en": "See your doctor if the result is clearly out of range or comes with persistent symptoms.",
    },
    "rdw": {
        "what_ar": "مقياس التباين في أحجام كريات الدم الحمراء.",
        "what_en": "A measure of variation in red blood cell sizes.",
        "low_ar": "قد تشير النتيجة إلى تباين ضعيف في أحجام الكريات.",
        "low_en": "The result may indicate low variation in red cell sizes.",
        "high_ar": "قد تشير النتيجة إلى تباين كبير في أحجام الكريات، وغالباً ما يظهر مع فقر دم.",
        "high_en": "The result may indicate high variation in red cell sizes, often seen with anemia.",
        "when_ar": "راجع طبيبك إذا كانت النتيجة مرتفعة مع فقر دم أو أعراض تعب.",
        "when_en": "See your doctor if the result is high with anemia or fatigue.",
    },
}


def describe_results(results, lang="ar"):
    """Builds localized per-indicator detail for the interactive card/table."""
    ar = lang == "ar"
    out = []
    for r in results:
        key = r["key"]
        info = INDICATOR_INFO.get(key, {})
        name = r["name_ar"] if ar else r["name_en"]
        status = r["status"]
        if status == "normal":
            meaning = ("النتيجة ضمن النطاق الطبيعي لهذا المؤشر." if ar
                       else "The result is within the normal range for this indicator.")
        elif status == "low":
            meaning = info.get("low_ar") or ("قد تشير النتيجة إلى انخفاض %s — راجع طبيبك لتأكيد السبب." % name)
            if not ar:
                meaning = info.get("low_en") or ("The result may indicate a low %s — see your doctor to confirm the cause." % name)
        else:
            meaning = info.get("high_ar") or ("قد تشير النتيجة إلى ارتفاع %s — راجع طبيبك لتأكيد السبب." % name)
            if not ar:
                meaning = info.get("high_en") or ("The result may indicate a high %s — see your doctor to confirm the cause." % name)
        out.append({
            "key": key, "name": name, "unit": r["unit"],
            "value": r["value"], "low": r["low"], "high": r["high"], "status": status,
            "what": info.get("what_ar" if ar else "what_en", ""),
            "meaning": meaning,
            "when": info.get("when_ar" if ar else "when_en", ""),
        })
    return out


def summary_text(level, lang="ar"):
    ar = lang == "ar"
    if level == "emergency":
        return ("توجد قيم حرجة تتطلب تقييماً فورياً — يُنصح بالتوجه إلى أقرب طوارئ الآن." if ar
                else "There are critical values requiring immediate evaluation — go to the nearest emergency department now.")
    if level == "urgent":
        return ("توجد قيم تحتاج تقييماً طبياً عاجلاً خلال ساعات — راجع أقرب منشأة صحية." if ar
                else "There are values that need prompt medical evaluation within hours — visit the nearest health facility.")
    if level == "see_doctor":
        return ("توجد مؤشرات خارج النطاق الطبيعي — يُنصح بمراجعة الطبيب لتفسيرها وفحصها." if ar
                else "Some indicators are outside the normal range — we recommend seeing a doctor to interpret and check them.")
    return ("جميع المؤشرات المقروءة ضمن النطاق الطبيعي. لا يعني ذلك إلغاء الفحوصات الدورية." if ar
            else "All read indicators are within the normal range. This doesn't replace routine check-ups.")


def disclaimer_text(lang="ar"):
    return ("توعية فقط — ليس تشخيصاً طبياً. النطاقات المرجعية تختلف حسب المختبر والعمر، وراجع طبيبك لتأكيد أي نتيجة." if lang == "ar"
            else "Awareness only — not a medical diagnosis. Reference ranges vary by laboratory and age; confirm any result with your doctor.")


def child_note_text(lang="ar"):
    return ("نطاقات الأطفال تختلف عن نطاقات البالغين — ننصح بعرض النتيجة على طبيب أطفال." if lang == "ar"
            else "Pediatric ranges differ from adult ranges — please show the report to a pediatrician.")


def generate_blood_chart(results):
    """Renders a value-vs-reference-range chart as a PNG buffer."""
    if not results:
        return None
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = results
    fig, ax = plt.subplots(figsize=(8, max(2.5, 0.6 * len(rows) + 1)))
    positions = list(range(len(rows)))
    labels = [r["name_en"] for r in rows]
    for i, r in enumerate(rows):
        lo, hi = r["low"], r["high"]
        ax.plot([lo, hi], [i, i], color="#c8d6e5", lw=7, solid_capstyle="round", zorder=1)
        color = "#e74c3c" if r["status"] != "normal" else "#27ae60"
        ax.plot(r["value"], i, "o", color=color, ms=13, zorder=3)
        ax.annotate(f"{r['value']}", (r["value"], i), textcoords="offset points",
                    xytext=(7, 0), fontsize=8, color="#2c3e50")
    ax.set_yticks(positions)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("Value")
    ax.set_title("CBC — Blood Test Report")
    ax.grid(True, axis="x", alpha=0.3)
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf
