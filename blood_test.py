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
            notes.append(("فقر دم صغير الكريات (نقص حديد هو الأكثر شيوعاً) — راجعي طبيبك لفحص الفيريتين",
                          "Microcytic anemia (iron deficiency is most common) — see your doctor to check ferritin"))
        elif mcv and mcv["value"] > mcv["high"]:
            notes.append(("فقر دم كبير الكريات (نقص B12 أو حمض الفوليك محتمل) — راجعي طبيبك",
                          "Macrocytic anemia (possible B12/folate deficiency) — see your doctor"))
        else:
            notes.append(("فقر دم (أنيميا) — راجعي طبيبك لتحديد السبب",
                          "Anemia — see your doctor to determine the cause"))
    if h and h["status"] == "high":
        notes.append(("ارتفاع الهيموغلوبين (قد يكون جفاف أو سبباً آخر) — راجعي طبيبك",
                      "High hemoglobin (may be dehydration or another cause) — see your doctor"))
    if wbc and wbc["status"] == "high":
        if neut and neut["value"] > neut["high"]:
            notes.append(("ارتفاع كريات بيضاء مع ارتفاع العدلات — غالباً التهاب أو عدوى بكتيرية",
                          "High WBC with high neutrophils — usually infection/inflammation, often bacterial"))
        elif lymph and lymph["value"] > lymph["high"]:
            notes.append(("ارتفاع كريات بيضاء مع ارتفاع اللمفاويات — عدوى فيروسية محتملة",
                          "High WBC with high lymphocytes — possible viral infection"))
        else:
            notes.append(("ارتفاع كريات بيضاء — التهاب أو عدوى محتملة",
                          "High WBC — possible infection or inflammation"))
    if wbc and wbc["status"] == "low":
        notes.append(("انخفاض كريات بيضاء — قد يكون عدوى فيروسية أو سبباً آخر؛ راجعي طبيبك لو استمر",
                      "Low WBC — may be a viral infection or another cause; see a doctor if it persists"))
    if plt and plt["status"] == "low":
        notes.append(("انخفاض الصفائح — راجعي طبيبك لتقييم خطر النزف",
                      "Low platelets — see your doctor to evaluate bleeding risk"))
    if plt and plt["status"] == "high":
        notes.append(("ارتفاع الصفائح — راجعي طبيبك لتقييم السبب",
                      "High platelets — see your doctor to evaluate the cause"))

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
