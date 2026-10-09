"""Sourced search cards for blood-test analytes (V252).

Builds a search result for any analyte known to ``blood_test`` (names, synonyms,
short codes such as AST/ALT/CRP) from the same reviewed texts and verified source
links used by the blood-analysis page. No new medical wording is introduced:
descriptions, "possible factors" and "when to ask a doctor" come from
``blood_test`` tables. Direction words (high/low) only choose which of the
existing paragraphs is shown first.
"""
import re

import blood_test as bt

_AR_MAP = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ؤ": "و", "ئ": "ي", "ة": "ه"})

HIGH_WORDS = {"مرتفع", "ارتفاع", "عالي", "عاليه", "زياده", "زيادة", "زايد", "high", "elevated", "raised", "increased"}
LOW_WORDS = {"منخفض", "انخفاض", "نقص", "قليل", "قليله", "ناقص", "low", "decreased", "reduced", "deficiency"}
FILLER = {"تحليل", "فحص", "اختبار", "نسبه", "نسبة", "مستوي", "مستوى", "معدل", "نتيجه", "نتيجة", "قراءه", "قراءة",
          "في", "الدم", "دم", "طبيعي", "ما", "هو", "هي", "ايش", "وش", "يعني", "عن", "لل", "و",
          "test", "tests", "level", "levels", "blood", "serum", "result", "results", "what", "is", "the", "of",
          "my", "normal", "range", "meaning", "mean", "in", "a", "an", "and", "for"}

# Extra everyday names that are not in blood_test.SYNONYMS.
_EXTRA = {
    "hgb": ["هيموغلوبين", "خضاب الدم", "الهيموجلوبين", "hemoglobin", "haemoglobin", "hb", "hgb"],
    "glucose": ["سكر الدم", "سكر", "سكر صايم", "السكر", "الجلوكوز", "blood sugar", "blood glucose", "glucose", "fbs", "rbs"],
    "hba1c": ["السكر التراكمي", "سكر تراكمي", "هيموغلوبين سكري", "a1c", "hba1c", "glycated hemoglobin"],
    "creatinine": ["كرياتينين", "الكرياتينين", "creatinine"],
    "egfr": ["معدل الترشيح", "ترشيح الكلى", "egfr", "gfr"],
    "bun": ["bun", "نيتروجين اليوريا", "blood urea nitrogen", "urea nitrogen"],
    "urea": ["اليوريا", "يوريا", "urea"],
    "alt": ["alt", "sgpt", "انزيم alt", "انزيمات الكبد", "liver enzymes", "alanine aminotransferase"],
    "ast": ["ast", "sgot", "انزيم ast", "aspartate aminotransferase"],
    "alp": ["alp", "الكالين فوسفاتيز", "alkaline phosphatase"],
    "bilirubin": ["بيليروبين", "البيليروبين", "الصفراء", "bilirubin"],
    "albumin": ["الالبيومين", "البومين", "الألبومين", "albumin"],
    "total_protein": ["البروتين الكلي", "بروتين كلي", "total protein"],
    "chol_total": ["كوليسترول", "الكوليسترول", "الكوليستيرول", "cholesterol", "total cholesterol"],
    "ldl": ["ldl", "الكوليسترول الضار", "كوليسترول ضار", "bad cholesterol"],
    "hdl": ["hdl", "الكوليسترول النافع", "كوليسترول نافع", "الكوليسترول الجيد", "good cholesterol"],
    "triglycerides": ["الدهون الثلاثيه", "دهون ثلاثيه", "ترايغلسرايد", "ترايجليسرايد", "triglycerides", "triglyceride", "tg"],
    "sodium": ["صوديوم", "الصوديوم", "sodium", "na"],
    "potassium": ["بوتاسيوم", "البوتاسيوم", "potassium"],
    "chloride": ["كلورايد", "الكلورايد", "الكلوريد", "chloride"],
    "calcium": ["كالسيوم", "الكالسيوم", "calcium"],
    "co2": ["ثاني اكسيد الكربون", "بيكربونات", "bicarbonate", "co2"],
    "ferritin": ["فيريتين", "الفيريتين", "مخزون الحديد", "ferritin"],
    "b12": ["فيتامين ب12", "فيتامين b12", "ب12", "vitamin b12", "b12", "cobalamin"],
    "vitd": ["فيتامين د", "vitamin d", "vit d", "25-oh vitamin d", "25 oh vitamin d"],
    "tsh": ["tsh", "الغده الدرقيه", "هرمون الغده الدرقيه", "هرمون tsh", "thyroid stimulating hormone", "thyroid test"],
    "free_t4": ["free t4", "ft4", "t4", "ثيروكسين"],
    "iron": ["الحديد", "حديد الدم", "iron", "serum iron"],
    "crp": ["crp", "البروتين المتفاعل", "بروتين سي المتفاعل", "c reactive protein", "c-reactive protein"],
    "esr": ["esr", "سرعه الترسيب", "سرعة الترسيب", "معدل الترسيب", "sed rate", "sedimentation rate"],
    "magnesium": ["مغنيسيوم", "المغنيسيوم", "magnesium"],
    "phosphate": ["فوسفات", "الفوسفات", "الفسفور", "phosphate", "phosphorus"],
    "uric_acid": ["حمض اليوريك", "حمض اليورك", "اليوريك اسيد", "uric acid"],
    "ggt": ["ggt", "جاما جي تي", "gamma gt"],
    "lipase": ["الليباز", "ليباز", "انزيم الليباز", "lipase"],
    "folate": ["الفولات", "فولات", "حمض الفوليك", "folate", "folic acid"],
    "anc": ["anc", "العدد المطلق للعدلات", "absolute neutrophil count"],
    "troponin": ["تروبونين", "troponin", "cardiac troponin"],
    "plt": ["الصفائح الدمويه", "الصفائح الدموية", "platelet count"],
    "wbc": ["عدد الكريات البيضاء", "white blood cells"],
    "rbc": ["عدد الكريات الحمراء", "red blood cells"],
    "hct": ["hematocrit", "الهيماتوكريت"],
    "mcv": ["mcv"], "mch": ["mch"], "mchc": ["mchc"], "rdw": ["rdw"],
    "neut": ["العدلات", "neutrophils"], "lymph": ["الخلايا اللمفاويه", "lymphocytes"],
    "mono": ["الوحيدات", "monocytes", "mono"], "eos": ["الحمضات", "eosinophils", "eos"],
    "baso": ["القعدات", "basophils", "baso"], "mpv": ["mpv", "متوسط حجم الصفائح"],
}


def _norm(text):
    t = " ".join(str(text or "").strip().lower().split())
    t = re.sub(r"[ً-ٰٟـ]", "", t).translate(_AR_MAP)
    t = re.sub(r"[^\w\s\-]", " ", t)
    return " ".join(t.split())


def _strip_al(word):
    return word[2:] if word.startswith("ال") and len(word) > 4 else word


_INDEX = None


def _index():
    """phrase -> key (longest phrases are tried first)."""
    global _INDEX
    if _INDEX is None:
        idx = {}
        for key, ref in bt.REFS.items():
            names = [ref[0], ref[1], key.replace("_", " ")]
            names += list(bt.SYNONYMS.get(key, []))
            names += _EXTRA.get(key, [])
            for n in names:
                p = _norm(n)
                if p:
                    core = " ".join(w for w in p.split() if w not in FILLER and w not in HIGH_WORDS and w not in LOW_WORDS)
                    for form in (p, core):
                        if form:
                            idx.setdefault(form, key)
                            idx.setdefault(" ".join(_strip_al(w) for w in form.split()), key)
        _INDEX = idx
    return _INDEX


def _tokens(query):
    return [w for w in _norm(query).split() if w]


def find_key(query, exact_only=False):
    """Return (key, direction) or (None, None).

    exact_only: the query must be (after removing filler/direction words) exactly
    an analyte name. Otherwise a name may appear inside a longer 2-3 word query.
    """
    toks = _tokens(query)
    if not toks:
        return None, None
    direction = None
    if any(t in HIGH_WORDS for t in toks):
        direction = "high"
    if any(t in LOW_WORDS for t in toks):
        direction = None if direction == "high" else "low"
    core = [t for t in toks if t not in HIGH_WORDS and t not in LOW_WORDS and t not in FILLER]
    if not core or len(core) > 4:
        return None, None
    idx = _index()
    phrase = " ".join(core)
    for cand in (phrase, " ".join(_strip_al(w) for w in core)):
        if cand in idx:
            return idx[cand], direction
    if exact_only:
        return None, None
    # contiguous sub-phrases, longest first (multi-word analyte names inside a longer query)
    n = len(core)
    for size in range(n, 0, -1):
        for i in range(0, n - size + 1):
            sub = core[i:i + size]
            cand = " ".join(sub)
            cand2 = " ".join(_strip_al(w) for w in sub)
            for c in (cand, cand2):
                if c in idx and (size > 1 or len(c) >= 3):
                    return idx[c], direction
    return None, None


def _sources(key):
    src = bt.source_for_key(key)
    out, seen = [], set()
    for s in [src] + list(src.get("additional_sources") or []):
        url = s.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        out.append({"name": s.get("name"), "organization": s.get("organization"), "url": url})
    return out


def card(key, direction, lang="ar"):
    ref = bt.REFS[key]
    en = lang == "en"
    title = ref[1] if en else ref[0]
    info = bt.INDICATOR_INFO.get(key) or {}
    ext = bt.EXTENDED_INFO.get(key)
    sfx = "en" if en else "ar"
    what = info.get("what_" + sfx) or ((ext[1] if en else ext[0]) if ext else "")
    if not what:
        what = ("A blood test that is read together with the rest of the report, your symptoms, and the lab's own reference range."
                if en else "فحص دم يُقرأ مع بقية نتائج التقرير والأعراض ونطاق المرجع الخاص بالمختبر.")
    status_txt = {}
    for st in ("low", "high"):
        status_txt[st] = info.get(st + "_" + sfx) or ""
    order = [direction] if direction in ("low", "high") else ["low", "high"]
    parts = []
    for st in order:
        if status_txt[st]:
            label = ("If high: " if en else "إذا كانت مرتفعة: ") if st == "high" else ("If low: " if en else "إذا كانت منخفضة: ")
            parts.append(label + status_txt[st])
    causes = []
    for st in (order if direction else ["high", "low"]):
        causes += bt.possible_factors_for_result(key, st, sfx)
    seen, clean = set(), []
    for c in causes:
        if c not in seen:
            seen.add(c)
            clean.append(c)
    doctor = info.get("when_" + sfx) or (
        "Discuss the result with a clinician, especially if it is new, persistent, or comes with symptoms." if en else
        "ناقش النتيجة مع الطبيب خاصةً إذا كانت جديدة أو متكررة أو ترافقها أعراض.")
    note = bt.possible_factors_note(sfx) if clean else ""
    return {
        "key": "lab_" + key, "emoji": "🧪", "category": "test",
        "title": title,
        "what": what,
        "causes": clean[:4],
        "causes_label": "💡 Possible factors" if en else "💡 عوامل قد ترتبط بالنتيجة",
        "worry": " ".join(parts),
        "doctor": doctor + ((" — " + note) if note else ""),
        "sources": _sources(key),
        "recognized_topics": [title],
        "lab_key": key,
        "lab_direction": direction,
    }


_CONTEXT_WORDS = {"تحليل", "فحص", "اختبار", "نسبه", "مستوي", "معدل", "نتيجه", "قراءه",
                  "test", "level", "levels", "result", "results", "range"}


def has_lab_context(query):
    toks = set(_tokens(query))
    return bool(toks & (HIGH_WORDS | LOW_WORDS | _CONTEXT_WORDS))


def lookup(query, lang="ar", exact_only=None):
    if exact_only is None:
        exact_only = not has_lab_context(query)
    key, direction = find_key(query, exact_only=exact_only)
    if not key or key not in bt.REFS:
        return None
    return card(key, direction, lang)
