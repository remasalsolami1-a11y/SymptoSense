"""Medication Context Engine (V257): links the user's own medicines to symptoms, other medicines and conditions.

NO new medical claims are written here. A link is produced only when
  * the medicine is in the sourced medication catalog (``medication_warnings.lookup_drug``), AND
  * the catalog's own warning/interaction text mentions the same category (e.g. gastrointestinal effects, bleeding,
    low blood sugar, kidney, liver) or names the other medicine.
Timing ("started N days before") comes from the user's own medication plan. The category keyword lists below are
only a vocabulary for matching free text and are listed in MEDICAL_REVIEW_NEEDED.md for pharmacist review.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

import db
import medication_warnings

# category -> (user symptom/condition words, catalog-text words).
# Categories whose label text is conditional (e.g. "hypoglycemia WITH insulin") are deliberately not included.
SYMPTOM_CATS = {
    "gi": (("غثيان", "قيء", "استفراغ", "اسهال", "إسهال", "ألم بطن", "الم بطن", "ألم المعدة", "إمساك", "امساك", "حرقة", "nausea", "vomit", "diarrhea", "stomach", "abdominal"),
           ("هضمي", "معدة", "غثيان", "إسهال", "اسهال", "قيء", "gastro", "stomach", "nausea", "diarrhea", "vomit")),
    "bleeding": (("نزيف", "كدمات", "كدمة", "bleeding", "bruis"), ("نزيف", "bleeding")),
    "rash": (("طفح", "حكة", "تورم الوجه", "rash", "itch", "hives"), ("طفح", "حساسية", "rash", "allerg")),
}
CONDITION_CATS = {
    "kidney": (("كلى", "كلية", "kidney", "renal"), ("كلى", "كلية", "kidney", "renal")),
    "liver": (("كبد", "liver", "hepatic"), ("كبد", "liver", "hepatic")),
    "pregnancy": (("حمل", "حامل", "pregnan"), ("حمل", "pregnan")),
    "asthma": (("ربو", "asthma"), ("ربو", "asthma")),
    "heart": (("قلب", "heart", "cardiac"), ("قلب", "heart", "cardiac")),
}
CAT_LABEL = {
    "gi": ("الأعراض الهضمية", "gastrointestinal effects"), "bleeding": ("النزف", "bleeding"),
    "rash": ("الطفح والحساسية", "rash and allergy"), "kidney": ("الكلى", "kidney"), "liver": ("الكبد", "liver"),
    "pregnancy": ("الحمل", "pregnancy"), "asthma": ("الربو", "asthma"), "heart": ("القلب", "heart"),
}
RECENT_DAYS = 21


def _has(text, words):
    t = (text or "").lower()
    return any(w.lower() in t for w in words)


_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_DUR_RE = re.compile(r"(\d{1,3})?\s*(شهرين|شهور|اشهر|شهر|اسبوعين|اسابيع|اسبوع|يومين|ايام|يوم|months?|weeks?|days?)(?![a-z\u0600-\u06ff])")
_DUR_UNIT_DAYS = {"شهر": 30, "شهور": 30, "اشهر": 30, "شهرين": 60, "اسبوع": 7, "اسابيع": 7, "اسبوعين": 14, "يوم": 1, "ايام": 1, "يومين": 2,
                  "month": 30, "months": 30, "week": 7, "weeks": 7, "day": 1, "days": 1}
_DUAL = {"شهرين", "اسبوعين", "يومين"}


def duration_days(text):
    """Best-effort length of the symptoms in days from the user's own duration words; None when it cannot be read.

    Used ONLY to avoid claiming that symptoms began after a medicine when they clearly began before it.
    """
    t = str(text or "").translate(_DIGITS).lower()
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ة", "ه")):
        t = t.replace(a, b)
    m = _DUR_RE.search(t)
    if not m:
        return None
    unit = m.group(2)
    n = int(m.group(1)) if m.group(1) else 1
    if unit in _DUAL:
        n = 1
    return n * _DUR_UNIT_DAYS[unit]


def _days_since(start_date, now=None):
    try:
        d = datetime.fromisoformat(str(start_date)[:10]).replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
    days = ((now or datetime.now(timezone.utc)) - d).days
    return days if days >= 0 else None


def active_meds(user_id, member_id=0, now=None):
    """The user's active medicines, each joined with its catalog entry when one exists."""
    out = []
    try:
        plans = db.list_med_plans(user_id, member_id=member_id, active_only=True)
    except db.DB_ERRORS:
        return out
    for p in plans:
        name = str(p.get("med_name") or "").strip()
        if not name:
            continue
        try:
            entry = medication_warnings.lookup_drug(name)
        except db.DB_ERRORS:
            entry = None
        out.append({"name": name, "start_date": p.get("start_date"), "days_ago": _days_since(p.get("start_date"), now), "entry": entry})
    return out


def _entry_text(entry, lang):
    if not entry:
        return ""
    sfx = "en" if lang == "en" else "ar"
    return " ".join(str(entry.get(k) or "") for k in ("warning_" + sfx, "interact_" + sfx))


def _aliases(entry):
    names = {str(entry.get("slug") or "").replace("_", " ")}
    for n in (str(entry.get("name_en") or "") + " / " + str(entry.get("name_ar") or "")).split("/"):
        n = n.strip().lower()
        if len(n) >= 4:
            names.add(n)
    return {n for n in names if len(n) >= 4}


def links(meds, symptoms, conditions_text="", lang="ar", symptom_days=None):
    """Return a list of {kind, med, other?, category, basis, days_ago}. ``basis`` is always 'catalog_text' or 'timing'."""
    found = []
    sym_text = " ".join(symptoms or [])
    for m in meds:
        entry = m["entry"]
        text_ar, text_en = _entry_text(entry, "ar"), _entry_text(entry, "en")
        label_name = ((entry.get("name_en") if lang == "en" else entry.get("name_ar")) if entry else None) or m["name"]
        cat_label = lambda c: CAT_LABEL[c][1 if lang == "en" else 0]
        if entry:
            for cat, (sym_words, text_words) in SYMPTOM_CATS.items():
                if _has(sym_text, sym_words) and (_has(text_ar, text_words) or _has(text_en, text_words)):
                    found.append({"kind": "drug_symptom", "med": m["name"], "med_label": label_name, "category": cat, "label": cat_label(cat), "basis": "catalog_text", "days_ago": m["days_ago"]})
            for cat, (cond_words, text_words) in CONDITION_CATS.items():
                if _has(conditions_text, cond_words) and (_has(text_ar, text_words) or _has(text_en, text_words)):
                    found.append({"kind": "drug_condition", "med": m["name"], "med_label": label_name, "category": cat, "label": cat_label(cat), "basis": "catalog_text", "days_ago": m["days_ago"]})
            for o in meds:
                if o is m or not o["entry"]:
                    continue
                if any(re.search(r"(?<![\w؀-ۿ])" + re.escape(a) + r"(?![\w؀-ۿ])", (text_ar + " " + text_en).lower()) for a in _aliases(o["entry"])):
                    found.append({"kind": "drug_drug", "other_key": o["name"], "med": m["name"], "med_label": label_name, "other": (o["entry"].get("name_en") if lang == "en" else o["entry"].get("name_ar")) or o["name"], "category": "interaction", "label": "", "basis": "catalog_text", "days_ago": m["days_ago"]})
        if m["days_ago"] is not None and m["days_ago"] <= RECENT_DAYS and sym_text:
            # If the symptoms clearly began BEFORE the medicine was started, timing is not a lead at all: no link.
            if symptom_days is not None and symptom_days > m["days_ago"] + 1:
                continue
            found.append({"kind": "timing", "med": m["name"], "med_label": label_name, "in_catalog": bool(entry), "category": "timing", "label": "", "basis": "timing",
                          "days_ago": m["days_ago"], "onset_known": symptom_days is not None})
    # drug_drug appears from both sides; keep one per unordered pair
    seen, unique = set(), []
    for f in found:
        key = (f["kind"], frozenset([f["med"], f.get("other_key", "")]), f["category"])
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique


def describe(link, lang="ar"):
    en = lang == "en"
    med, days = link.get("med_label") or link["med"], link.get("days_ago")
    when = ((" (started %d days ago)" if en else " (بدأته قبل %d يومًا)") % days) if days is not None else ""
    k = link["kind"]
    if k == "timing":
        # Timing is information for the doctor, never evidence of cause. We never write "began after" without a date comparison.
        if en:
            base = "You started %s%s within the last 21 days%s. The timing may be useful for your doctor, but timing alone does not show a link between the medicine and your symptoms." % (
                med, when, " and you reported symptoms that are no older than that" if link.get("onset_known") else "")
            tail = " Ask your doctor or pharmacist before changing anything." if link.get("in_catalog") else " We do not have enough information about this medicine to say whether it is related. Ask your doctor or pharmacist."
        else:
            base = "بدأتَ استخدام %s%s خلال آخر 21 يومًا%s. قد يكون التوقيت معلومة مفيدة للطبيب، لكن التزامن وحده لا يثبت وجود علاقة بين الدواء وأعراضك." % (
                med, when, " وأعراضك المذكورة ليست أقدم من ذلك" if link.get("onset_known") else "")
            tail = " اسأل الطبيب أو الصيدلي قبل تغيير أي شيء." if link.get("in_catalog") else " لا تتوفر لدينا معلومات كافية عن هذا الدواء لتحديد ما إذا كان مرتبطًا بها. اسأل الطبيب أو الصيدلي."
        return base + tail
    if k == "drug_symptom":
        return ("The label information for %s mentions %s, which matches what you reported%s." if en else
                "معلومات النشرة لدواء %s تذكر %s وهو يتوافق مع ما ذكرته%s.") % (med, link["label"], when)
    if k == "drug_condition":
        return ("The label information for %s mentions %s, and you listed a related condition. Tell your doctor or pharmacist." if en else
                "معلومات النشرة لدواء %s تذكر %s، وقد ذكرتَ حالة مرتبطة. أخبر الطبيب أو الصيدلي.") % (med, link["label"])
    return ("The label information for %s mentions %s. Ask your pharmacist whether using them together is suitable for you." if en else
            "معلومات النشرة لدواء %s تذكر %s. اسأل الصيدلي هل استخدامهما معًا مناسب لك.") % (med, link.get("other", ""))
