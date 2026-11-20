"""Critical ("panic") laboratory values for the blood-test page (V288).

Why: before V288 only haemoglobin, platelets and WBC had danger thresholds. A report
with potassium 7.2, sodium 116 or glucose 38 mg/dL was shown as "see a doctor" —
the same as a slightly high cholesterol. Laboratories phone the clinician
immediately for such values ("critical values"), so the app must not be calmer
than the lab.

Rules
  * Thresholds are the widely used adult critical-value limits published by
    hospital laboratories (e.g. potassium < 2.5 or > 6.0 mmol/L, sodium < 120 or
    > 160 mmol/L, glucose < 54 mg/dL — the ADA "level 2" hypoglycaemia limit —
    or > 450 mg/dL, total calcium < 6.5 or > 13 mg/dL, ANC < 0.5 x10^9/L).
    They are PENDING CLINICIAN SIGN-OFF (CLINICAL_REVIEW_PACKET_AR.md) and are
    applied to adults only; a child's report is never judged with them.
  * Values are converted to one canonical unit first. A value whose unit cannot be
    established (printed unit, or the scale of the printed reference range) is not
    judged — a critical rule never guesses between mg/dL and mmol/L.
  * Troponin has no universal cut-off (assays differ), so it is judged only against
    the laboratory's own printed upper limit.
  * Critical values only ADD urgency; they never lower a result.
"""
from __future__ import annotations

# key -> (canonical unit, {unit: factor to canonical}, [(level, op, threshold)])
CRITICAL = {
    "potassium": ("mmol/L", {"mmol/L": 1.0, "meq/L": 1.0}, [("urgent", "lt", 2.5), ("urgent", "gt", 6.0)]),
    "sodium": ("mmol/L", {"mmol/L": 1.0, "meq/L": 1.0}, [("urgent", "lt", 120.0), ("urgent", "gt", 160.0)]),
    "glucose": ("mg/dL", {"mg/dL": 1.0, "mmol/L": 18.016}, [("urgent", "lt", 54.0), ("urgent", "gt", 450.0)]),
    "calcium": ("mg/dL", {"mg/dL": 1.0, "mmol/L": 4.008}, [("urgent", "lt", 6.5), ("urgent", "gt", 13.0)]),
    "magnesium": ("mg/dL", {"mg/dL": 1.0, "mmol/L": 2.431}, [("urgent", "lt", 1.0)]),
    "anc": ("10^9/L", {"10^9/L": 1.0, "10^3/uL": 1.0}, [("urgent", "lt", 0.5)]),
    # V290. INR is a ratio (no unit). Published critical limits vary (University of Iowa ≥ 4.0; CHI Health ≥ 5.0);
    # the lower, more cautious one is used. Lactate: CHI Health ≥ 4.5 mmol/L, Iowa > 5.0; ≥ 4.0 is the Surviving
    # Sepsis Campaign threshold for urgent resuscitation, used here as the cautious limit.
    "inr": ("ratio", {"": 1.0, "ratio": 1.0, "inr": 1.0}, [("urgent", "ge", 4.0)]),
    "lactate": ("mmol/L", {"mmol/L": 1.0, "meq/L": 1.0, "mg/dL": 0.111}, [("urgent", "ge", 4.0)]),
}

# Plausible reference-range scale -> unit, for reports that print a range but no unit.
_RANGE_SCALE = {
    "glucose": (("mg/dL", 50.0, 200.0), ("mmol/L", 2.5, 12.0)),
    "calcium": (("mg/dL", 7.0, 11.5), ("mmol/L", 1.8, 2.9)),
    "magnesium": (("mg/dL", 1.3, 3.0), ("mmol/L", 0.5, 1.2)),
    "potassium": (("mmol/L", 2.5, 6.5),),
    "sodium": (("mmol/L", 120.0, 160.0),),
    "lactate": (("mmol/L", 0.3, 3.0), ("mg/dL", 4.0, 30.0)),
}

_NAMES = {
    "potassium": ("البوتاسيوم", "Potassium"), "sodium": ("الصوديوم", "Sodium"), "glucose": ("سكر الدم", "Blood glucose"),
    "calcium": ("الكالسيوم", "Calcium"), "magnesium": ("المغنيسيوم", "Magnesium"),
    "anc": ("العدد المطلق للعدلات", "Absolute neutrophil count"), "troponin": ("التروبونين القلبي", "Cardiac troponin"),
    "inr": ("سيولة الدم INR", "INR"), "lactate": ("اللاكتات", "Lactate"),
}
_WHY = {
    ("potassium", "gt"): ("ارتفاع البوتاسيوم الشديد قد يسبب اضطرابًا خطيرًا في نبض القلب.", "Very high potassium can cause a dangerous heart rhythm."),
    ("potassium", "lt"): ("انخفاض البوتاسيوم الشديد قد يسبب ضعفًا شديدًا في العضلات واضطرابًا في نبض القلب.", "Very low potassium can cause severe muscle weakness and an abnormal heart rhythm."),
    ("sodium", "lt"): ("انخفاض الصوديوم الشديد قد يسبب تشوشًا وتشنجات.", "Very low sodium can cause confusion and seizures."),
    ("sodium", "gt"): ("ارتفاع الصوديوم الشديد يدل غالبًا على جفاف شديد وقد يؤثر على الدماغ.", "Very high sodium usually means severe dehydration and can affect the brain."),
    ("glucose", "lt"): ("هبوط السكر بهذه الدرجة خطير: إذا كنت واعيًا تناول سكرًا سريعًا الآن، واطلب الإسعاف إذا ظهر تشوش أو نعاس.", "Glucose this low is dangerous: if you are awake take fast sugar now, and call an ambulance if confusion or drowsiness appears."),
    ("glucose", "gt"): ("ارتفاع السكر بهذه الدرجة قد يسبب جفافًا شديدًا أو حماضًا كيتونيًا.", "Glucose this high can cause severe dehydration or ketoacidosis."),
    ("calcium", "gt"): ("ارتفاع الكالسيوم الشديد قد يسبب جفافًا واضطرابًا في القلب والوعي.", "Very high calcium can cause dehydration and problems with the heart and alertness."),
    ("calcium", "lt"): ("انخفاض الكالسيوم الشديد قد يسبب تشنجات واضطرابًا في نبض القلب.", "Very low calcium can cause spasms, seizures and an abnormal heart rhythm."),
    ("magnesium", "lt"): ("انخفاض المغنيسيوم الشديد قد يسبب اضطرابًا في نبض القلب وتشنجات.", "Very low magnesium can cause an abnormal heart rhythm and seizures."),
    ("anc", "lt"): ("انخفاض العدلات بهذه الدرجة يعني خطرًا عاليًا للعدوى؛ أي حرارة تحتاج طوارئ فورًا.", "Neutrophils this low mean a high infection risk; any fever needs emergency care immediately."),
    ("inr", "ge"): ("ارتفاع INR بهذه الدرجة يعني أن الدم بطيء التجلط جدًا وخطر النزيف عالٍ؛ إذا كنت تأخذ مميّعًا للدم فتواصل مع طبيبك أو عيادة السيولة اليوم قبل جرعتك التالية.",
                    "An INR this high means blood clots very slowly and the bleeding risk is high; if you take a blood thinner, contact your doctor or anticoagulation clinic today, before your next dose."),
    ("lactate", "ge"): ("ارتفاع اللاكتات بهذه الدرجة قد يدل على نقص تروية أو عدوى شديدة إذا لم يكن بعد مجهود عنيف مباشرة.",
                        "Lactate this high can mean poor blood flow or a severe infection, unless it was taken right after very hard exercise."),
    ("troponin", "gt"): ("التروبونين أعلى من حد المختبر قد يعني أذية في عضلة القلب، ويحتاج تقييمًا في الطوارئ اليوم.", "Troponin above the laboratory limit can mean heart-muscle injury and needs emergency assessment today."),
}


def _unit_key(unit: str) -> str:
    u = str(unit or "").strip().lower().replace(" ", "").replace("µ", "u").replace("μ", "u")
    return {"mmol/l": "mmol/L", "meq/l": "meq/L", "mg/dl": "mg/dL", "": "", "ratio": "ratio", "inr": "inr", "10^9/l": "10^9/L", "10^3/ul": "10^3/uL",
            "109/l": "10^9/L", "103/ul": "10^3/uL", "k/ul": "10^3/uL"}.get(u, str(unit or "").strip())


def _infer_unit(key: str, low, high) -> str | None:
    if low is None and high is None:
        return None
    probe = [x for x in (low, high) if x is not None]
    for unit, lo, hi in _RANGE_SCALE.get(key, ()):
        if all(lo <= x <= hi for x in probe):
            return unit
    return None


def canonical(key: str, value: float, unit: str, low=None, high=None) -> float | None:
    """Value in the canonical unit, or None if the unit cannot be established."""
    if key not in CRITICAL:
        return None
    _canon, factors, _rules = CRITICAL[key]
    u = _unit_key(unit)
    if u not in factors:
        u = _infer_unit(key, low, high)
    if u not in factors:
        return None
    return float(value) * factors[u]


def check(result: dict, source: dict | None = None, *, adult: bool = True) -> tuple[str, str, str] | None:
    """(level, message_ar, message_en) when a result is a critical value, else None."""
    r, src = result or {}, source or {}
    key = str(r.get("key") or "").lower()
    try:
        value = float(r.get("raw_value", r.get("value")))
    except (TypeError, ValueError):
        return None
    name_ar, name_en = _NAMES.get(key, (key, key))
    if key == "troponin":
        hi = src.get("reference_high", r.get("high"))
        try:
            hi = float(hi) if hi not in (None, "") else None
        except (TypeError, ValueError):
            hi = None
        if hi is None or value <= hi:
            return None
        why_ar, why_en = _WHY[("troponin", "gt")]
        return ("emergency", f"🚨🚨 {name_ar} {value:g} أعلى من حد المختبر ({hi:g}) — {why_ar}",
                f"🚨🚨 {name_en} {value:g} is above the laboratory limit ({hi:g}) — {why_en}")
    if not adult or key not in CRITICAL:
        return None
    unit = src.get("unit") or r.get("raw_unit") or r.get("unit") or ""
    v = canonical(key, value, unit, src.get("reference_low"), src.get("reference_high"))
    if v is None:
        return None
    canon_unit, _f, rules = CRITICAL[key]
    for level, op, threshold in rules:
        if (op == "lt" and v < threshold) or (op == "gt" and v > threshold) or (op == "ge" and v >= threshold):
            why_ar, why_en = _WHY[(key, op)]
            return (level,
                    f"🚨 قيمة حرجة: {name_ar} {value:g} — {why_ar} تواصل مع طبيب أو توجّه للطوارئ اليوم، واتصل 997 إذا ظهرت أعراض شديدة.",
                    f"🚨 Critical value: {name_en} {value:g} — {why_en} Contact a doctor or go to the emergency department today; call 997 if severe symptoms appear.")
    return None
