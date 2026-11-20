"""Small helpers for the health-search endpoint (moved out of webapp.py in V252)."""

def _normalize_health_query_text(value):
    """Normalize Arabic/English health-search text for robust context matching."""
    import re as _re
    text = " ".join(str(value or "").strip().lower().split())
    # Arabic diacritics/tatweel and common letter variants.
    text = _re.sub(r"[\u064b-\u065f\u0670\u0640]", "", text)
    text = text.translate(str.maketrans({"أ":"ا","إ":"ا","آ":"ا","ى":"ي","ؤ":"و","ئ":"ي","ة":"ه"}))
    return text

def _health_search_topic_meta(query, lang):
    """Choose a neutral label/icon from the *whole* query, not one fuzzy symptom hit."""
    q = _normalize_health_query_text(query)
    groups = [
        (("دواء", "ادويه", "حبوب", "جرعه", "باراسيتامول", "مضاد", "منجارو", "مونجارو", "تيرزيباتيد", "mounjaro", "tirzepatide", "medication", "medicine", "drug", "dose"), "💊", "medication"),
        (("تحليل", "فحص", "cbc", "wbc", "هيموغلوبين", "سكر تراكمي", "lab", "test", "blood", "cbc", "hba1c"), "🧪", "test"),
        (("حمل", "حامل", "الدوره", "الحيض", "الطمث", "pregnan", "period", "menstrual"), "🌸", "question"),
        (("نفسي", "قلق", "توتر", "مزاج", "اكتئاب", "نوم", "mental", "anxiety", "stress", "mood", "sleep"), "🧠", "question"),
        (("غذاء", "اكل", "تغذيه", "فيتامين", "ماء", "وزن", "سعرات", "nutrition", "food", "vitamin", "weight", "calorie"), "🥗", "question"),
        (("اسعاف", "جرح", "حرق", "نزيف", "اختناق", "first aid", "burn", "bleeding", "choking"), "🩹", "question"),
    ]
    for terms, emoji, category in groups:
        if any(_normalize_health_query_text(t) in q for t in terms):
            return emoji, category
    return "🩺", "question"

def _health_search_tokens(value, lang):
    """Meaningful tokens used only to reject clearly unrelated fuzzy results."""
    import re as _re
    text = _normalize_health_query_text(value)
    words = _re.findall(r"[a-z0-9\u0621-\u064a]+", text)
    stop_ar = {"ما","هو","هي","هل","ليش","لماذا","كيف","متى","وش","ايش","ماذا","مع","بعد","قبل","في","من","على","عن","الى","عند","وقت","خلال","اثناء","او","و","انا","عندي","يجيني","يجي","يصير"}
    stop_en = {"what","why","how","when","is","are","do","does","can","could","with","after","before","during","in","on","at","of","the","a","an","i","my","me"}
    stop = stop_en if lang == "en" else stop_ar
    out=[]
    for w in words:
        if w in stop or len(w) < 3:
            continue
        # Arabic definite article should not make two otherwise-identical words differ.
        if lang != "en" and w.startswith("ال") and len(w) > 4:
            w = w[2:]
        out.append(w)
    return out

def _health_search_result_relevant(query, result, lang):
    """Reject only *clearly unrelated* glossary hits; query-first answer still works without them."""
    if not isinstance(result, dict):
        return False
    if result.get("contextual"):
        return True
    q_tokens = _health_search_tokens(query, lang)
    if not q_tokens:
        return True
    parts = [result.get("title") or ""]
    parts += [str(x) for x in (result.get("recognized_topics") or [])]
    for t in (result.get("matched_topics") or []):
        if isinstance(t, dict):
            parts.append(t.get("title") or "")
    r_tokens = _health_search_tokens(" ".join(parts), lang)
    if not r_tokens:
        return False
    for q in q_tokens:
        for r in r_tokens:
            if q == r or (len(q) >= 4 and len(r) >= 4 and (q in r or r in q)):
                return True
    return False

def _health_search_query_shell(query, lang):
    """A neutral result container for any health topic the curated glossary does not cover."""
    emoji, category = _health_search_topic_meta(query, lang)
    return {
        "key": "free_health_query",
        "emoji": emoji,
        "category": category,
        "title": str(query or "").strip(),
        "what": "",
        "causes": [],
        "worry": "",
        "doctor": "",
        "sources": [],
        "recognized_topics": [],
        "original_query": str(query or "").strip(),
        "query_first": True,
        "query_only": True,
    }
