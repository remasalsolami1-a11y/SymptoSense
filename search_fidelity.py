"""Multi-word (2-3 word) search fidelity for SymptoSense (V252).

The glossary matcher can answer a short query with a related-but-wrong topic
("knee swelling" -> salivary-gland swelling, "ضغط الدم المنخفض" -> high blood
pressure). This module checks whether a result really covers *all* the words of
the query and, when it does not, finds the library entry (symptom, disease or
curated search topic) whose name/aliases cover every word.

It never writes medical text: it only chooses which existing, sourced entry to
show.
"""
import re

import search_engine_v2 as _v2

_AR_MAP = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ؤ": "و", "ئ": "ي", "ة": "ه"})

_FILLER = set("""
في عند مع بعد قبل من على عن الى الي ل و او خلال اثناء بسبب ما هو هي هل كيف وش ايش ليش لماذا بدون سبب
انا عندي اعاني يعني ابي ابغي احس احيانا دايما
with in of the and after before when during on at to for a an is are my i me have has do does what why how can or
""".split())

_GROUPS = [
    "وجع الم pain ache aches painful sore",
    "تورم منتفخ منتفخه swelling swollen puffy puffiness",
    "حرقان حرقه حرق burning burn stinging",
    "بول تبول urine urination urinary pee peeing",
    "دم نزيف blood bleeding bleed",
    "براز تبرز stool stools poop",
    "صداع headache",
    "حمي حراره سخونه fever temperature",
    "دوخه دوار دوران dizziness dizzy vertigo lightheaded lightheadedness",
    "كحه سعال cough coughing",
    "نفس تنفس breath breathing breathlessness",
    "يمين ايمن right",
    "يسار ايسر left",
    "اعلي علوي upper top",
    "اسفل سفلي lower bottom",
    "ليل ليلا ليلي ليله night nights nighttime nocturnal",
    "اذن اذان ear ears",
    "عين عيون عيني eye eyes",
    "سن اسنان ضرس ضروس tooth teeth dental",
    "تيبس يبوسه تصلب stiff stiffness",
    "تنميل خدر تنمل numb numbness tingling",
    "تعب ارهاق اجهاد fatigue tired tiredness exhaustion",
    "قيء استفراغ تقيؤ vomiting vomit",
    "اسهال diarrhea diarrhoea",
    "انف nose nasal",
    "شعر hair",
    "جلد جلدي skin",
    "طفح rash",
    "حكه هرش حكاك itch itching itchy",
    "يد ايدي يدين hand hands",
    "رجل ساق ساقين leg legs",
    "قدم قدمين قدمي foot feet",
    "ركبه ركبتي ركبتين knee knees",
    "بطن معده بطني abdomen abdominal stomach belly tummy",
    "ظهر ظهري back",
    "رقبه عنق neck",
    "كتف اكتاف shoulder",
    "صدر chest",
    "قلب heart cardiac",
    "ضغط pressure",
    "منخفض انخفاض هبوط low drop",
    "مرتفع ارتفاع عالي high elevated",
    "سكر sugar glucose",
    "طفل اطفال رضيع child children kid baby infant",
    "حمل حامل pregnancy pregnant",
    "حلق throat",
    "فم mouth",
    "وجه face",
    "راس head",
    "جفاف dry dryness",
    "غثيان nausea",
    "عطش thirst thirsty",
    "نبض ضربات pulse heartbeat heartbeats",
    "خفقان palpitations palpitation",
    "سريع تسارع fast rapid racing",
    "كدمه كدمات bruise bruises bruising",
    "ورم lump swelling",
]
_GROUP_OF = {}
for _i, _g in enumerate(_GROUPS):
    for _w in _g.split():
        _GROUP_OF.setdefault(_w, set()).add("g%d" % _i)


def _norm(text):
    t = " ".join(str(text or "").strip().lower().split())
    t = re.sub(r"[ً-ٰٟـ]", "", t).translate(_AR_MAP)
    t = re.sub(r"[^\w\s]", " ", t)
    return t


def _forms(word):
    out = {word}
    cur = word
    for _ in range(2):
        if cur.startswith("ال") and len(cur) > 4:
            cur = cur[2:]
            out.add(cur)
        elif len(cur) > 4 and cur[0] in "وبلفك" and not cur.startswith("ال"):
            cur = cur[1:]
            out.add(cur)
        else:
            break
    for w in list(out):
        if len(w) > 4 and re.search(r"(ين|ان|ات)$", w):
            out.add(w[:-2])
        if len(w) > 4 and w.endswith("ي"):
            out.add(w[:-1])
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            out.add(w[:-1])
    return out


def _ids(word):
    ids = set()
    for f in _forms(word):
        ids.add("w:" + f)
        ids |= _GROUP_OF.get(f, set())
    return ids


def content_tokens(text):
    return [w for w in _norm(text).split() if w and w not in _FILLER and len(w) > 1]


def _token_sets(text):
    return [_ids(w) for w in content_tokens(text)]


def coverage(query, text):
    """Fraction of the query's content words found (same word/synonym) in text."""
    q = _token_sets(query)
    if not q:
        return 1.0
    t = set()
    for s in _token_sets(text):
        t |= s
    hit = sum(1 for s in q if s & t)
    return hit / len(q)


def _precision(query, text):
    t = _token_sets(text)
    if not t:
        return 0.0
    qa = set()
    for s in _token_sets(query):
        qa |= s
    return sum(1 for s in t if s & qa) / len(t)


_MODIFIERS = set("""
ليل ليلا ليلي night nights nighttime nocturnal شديد شديده severe مستمر مستمره constant persistent chronic مزمن
خفيف mild مفاجئ مفاجئه sudden مؤلم متكرر متكرره frequent recurrent
""".split())


def _drop_modifiers(query):
    toks = content_tokens(query)
    kept = [w for w in toks if not (_ids(w) & {"w:" + m for m in _MODIFIERS}) and w not in _MODIFIERS]
    return " ".join(kept) if kept else query


def _scan(query, lang, need):
    scored = []
    for cand in _v2._all_candidates(lang):
        texts = [cand.get("label") or ""] + list(cand.get("aliases") or [])
        top = 0.0
        for tx in texts:
            if not tx:
                continue
            cov = coverage(query, tx)
            if cov < need:
                continue
            score = cov + 0.5 * _precision(query, tx) + (0.01 if cand.get("kind") == "symptom" else 0.0)
            top = max(top, score)
        if top:
            scored.append((top, cand))
    scored.sort(key=lambda x: -x[0])
    return scored


def best_candidates(query, lang="ar", min_tokens=2, limit=3):
    """Entries whose label/alias covers every query word (best first, ties kept).

    1. all words; 2. all words except generic modifiers (night, severe, sudden...);
    3. a small set (<=3) of entries that together cover every word (multi-symptom).
    """
    ntok = len(content_tokens(query))
    if ntok < min_tokens or ntok > 5:
        return []
    for q in (query, _drop_modifiers(query)):
        if len(content_tokens(q)) < 1:
            continue
        scored = _scan(q, lang, 1.0)
        if scored:
            top = scored[0][0]
            out, seen = [], set()
            for sc, cand in scored:
                if sc < top - 0.02:
                    break
                if cand.get("slug") in seen:
                    continue
                seen.add(cand.get("slug"))
                out.append(cand)
                if len(out) >= limit:
                    break
            return out
    # greedy cover with entries that are fully contained in the query
    q_sets = _token_sets(query)
    uncovered = set(range(len(q_sets)))
    picks = []
    for _ in range(3):
        best, best_key = None, (0, 0.0)
        for cand in _v2._all_candidates(lang):
            if cand.get("kind") != "symptom":
                continue
            for tx in [cand.get("label") or ""] + list(cand.get("aliases") or []):
                if not tx or _precision(query, tx) < 1.0:
                    continue
                t = set()
                for st in _token_sets(tx):
                    t |= st
                gain = sum(1 for i in uncovered if q_sets[i] & t)
                key = (gain, len(content_tokens(tx)))
                if gain and key > best_key:
                    best, best_key = cand, key
        if not best:
            break
        picks.append(best)
        t = set()
        for tx in [best.get("label") or ""] + list(best.get("aliases") or []):
            if _precision(query, tx) >= 1.0:
                for st in _token_sets(tx):
                    t |= st
        uncovered = {i for i in uncovered if not (q_sets[i] & t)}
        if not uncovered:
            return picks
    return []


def result_text(result):
    parts = [result.get("title") or ""]
    parts += [str(x) for x in (result.get("recognized_topics") or [])]
    for t in (result.get("matched_topics") or []):
        if isinstance(t, dict):
            parts.append(t.get("title") or "")
    return " ".join(parts)


_RED_FLAG_KEYS = {"chest_pain"}


def rescue(q, lang, result, health_search, lib_topic, dis_topic, enrich):
    """Swap a card that misses words of a 2-3 word query for one that covers them all."""
    if not result or result.get("matched_topics") or result.get("contextual") or result.get("relation_query") \
            or str(result.get("key") or "").startswith(("lab_", "medic")):
        return result
    if len(content_tokens(q)) < 2:
        return result
    shell = result.get("key") == "free_health_query" or result.get("query_only")
    text = "" if shell else result_text(result)
    entry = (getattr(health_search, "SEARCH_KB", {}) or {}).get(result.get("key"))
    if entry:
        text += " " + " ".join(str(x) for x in (entry.get("aliases") or []))
    if str(result.get("key") or "") in _RED_FLAG_KEYS:
        return result
    if not shell and coverage(q, text) >= 1.0:
        return result
    cands = best_candidates(q, lang)
    curated = [c for c in cands if c.get("curated")]
    if curated:
        cands = curated[:1]
    topics, seen = [], set()
    for c in cands:
        slug = str(c.get("slug") or "")
        topic = None
        if c.get("curated"):
            kb = (health_search.SEARCH_KB or {}).get(slug)
            if kb:
                topic = enrich(health_search._entry(kb, lang, slug))
        elif c.get("kind") == "disease":
            topic = dis_topic({"kind": "disease", "score": 1.0, "slug": slug})
        else:
            topic = lib_topic({"slug": slug})
        key = str((topic or {}).get("key") or "")
        if topic and key and key not in seen and topic.get("sources"):
            seen.add(key)
            topics.append(topic)
    if not topics:
        return _partial(q, lang, result, shell, text, lib_topic, enrich)
    new = dict(topics[0])
    if len(topics) > 1:
        new["matched_topics"] = topics
    new.update({"original_query": q, "query_first": True, "query_only": False, "fidelity_v252": True})
    return new


def _partial(q, lang, result, shell, text, lib_topic, enrich):
    """No entry covers every word: if the card covers at most half of them, show the
    most specific entry fully contained in the query (e.g. "knee swelling" -> Swelling)
    and say it is the closest topic, instead of an unrelated card."""
    if not shell and coverage(q, text) > 0.5:
        return result
    q_sets = _token_sets(q)
    best, best_key = None, (0, 0)
    for cand in _v2._all_candidates(lang):
        if cand.get("kind") != "symptom" or cand.get("curated"):
            continue
        for tx in [cand.get("label") or ""] + list(cand.get("aliases") or []):
            if not tx or _precision(q, tx) < 1.0:
                continue
            t = set()
            for st in _token_sets(tx):
                t |= st
            gain = sum(1 for st in q_sets if st & t)
            key = (gain, len(content_tokens(tx)))
            if gain and key > best_key:
                best, best_key = cand, key
    if not best or best_key[0] < max(1, (len(q_sets) + 1) // 2):
        return result
    topic = lib_topic({"slug": str(best.get("slug") or "")})
    if not topic or not topic.get("sources"):
        return result
    topic.update({"original_query": q, "query_first": True, "query_only": False, "fidelity_v252": True,
                  "closest_match": True})
    return topic


def exact_library_hit(v2_search, query):
    """True when the query is exactly the name of a library symptom (score >= 0.95).

    Such a query has no extra context to preserve, so the library card must win over
    the generic heat/exercise/"relation" handlers that match single words inside the name.
    """
    nq = " ".join(_norm(query).split())
    for hit in (v2_search or {}).get("results") or []:
        if hit.get("kind") == "symptom" and float(hit.get("score") or 0) >= 0.95 \
                and " ".join(_norm(hit.get("label")).split()) == nq:
            return True
    return False
