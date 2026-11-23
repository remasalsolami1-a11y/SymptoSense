"""V292: Health knowledge graph — the links the engine already uses, made explorable.

Nodes: symptoms, health conditions, blood-test indicators, medicine-effect groups and medical
sources. Every edge comes from data the engine itself reads; nothing is added for display:

  condition -> symptom   medical_knowledge.DISEASES[*]["symptoms"] (weight = how typical)
  condition -> source    medical_knowledge.DISEASES[*]["sources"]
  lab       -> symptom   blood_test.CBC_ASSOCIATED_SYMPTOMS (a low/high value may come with it)
  lab       -> source    blood_test.DIRECT_SOURCES / CBC_SOURCE
  medicine  -> symptom   medication_context.SYMPTOM_CATS (a group-level link, not per medicine, not causation)

It is a curated knowledge graph, not a learned model, and the page says so. The explorer shows
one node and its direct links at a time (an "ego network"), never the whole hairball.
"""
from __future__ import annotations

import hashlib
import html
import json
import logging
import threading
from pathlib import Path

_LOCK = threading.Lock()
_GRAPH: dict | None = None
TYPES = ("symptom", "condition", "lab", "medicine", "source")
_TYPE_LABEL = {"symptom": ("عرض", "Symptom"), "condition": ("حالة صحية", "Health condition"), "lab": ("مؤشر تحليل دم", "Blood-test indicator"),
               "medicine": ("مجموعة آثار دوائية", "Medicine effect group"), "source": ("مصدر طبي", "Medical source")}
# V292.1: every link says what kind of relation it is, how strong (only where the knowledge base
# carries a weight), where its source comes from, and what it does NOT mean.
KINDS = {
    "typical_symptom": ("عرض مرتبط بالحالة", "Symptom linked to the condition"),
    "condition_source": ("مصدر الحالة", "Condition source"),
    "lab_symptom": ("ارتباط عام بنتيجة تحليل", "General link to a test result"),
    "indicator_source": ("مرجع المؤشر", "Indicator reference"),
    "medicine_group": ("مجموعة آثار دوائية", "Medicine effect group"),
}
_SCOPE = {  # what the source link next to a relation actually documents
    "condition": ("مصدر الحالة", "Condition source"),
    "indicator": ("مرجع المؤشر", "Indicator reference"),
}
_LIMITS = {
    "typical_symptom": ("المصدر يخص الحالة عمومًا وليس هذا الرابط وحده. درجة الشيوع تقدير منظّم في قاعدة المعرفة وليست نسبة إحصائية، ولا تعني تشخيصًا.",
                        "The source covers the condition as a whole, not this link alone. How common it is is a curated estimate, not a statistic, and not a diagnosis."),
    "lab_symptom": ("ارتباط عام قد يحدث مع هذه النتيجة، وليس دليلًا على السبب. تفسير التحليل يحتاج طبيبًا.",
                    "A general link that may occur with this result, not proof of cause. A doctor interprets the test."),
    "medicine_group": ("الرابط على مستوى المجموعة: ينطبق على بعض الأدوية الموثقة في الكتالوج وليس على كل دواء، ولا يعني أن الدواء هو سبب العرض.",
                       "A group-level link: it applies to some medicines in the sourced catalog, not to every medicine, and does not mean the medicine caused the symptom."),
}


def build() -> dict:
    import blood_test
    import medical_knowledge as mk
    import medication_context as mc

    import db
    # V292.1: one database connection for the whole build (was one per phrase: ~70 round trips,
    # which made the first page load time out on the hosted PostgreSQL).
    conn = db._conn()
    try:
        return _build(conn, mk, blood_test, mc)
    finally:
        conn.close()


def _build(conn, mk, blood_test, mc) -> dict:
    nodes, edges, index = {}, [], {}
    norm_cache = {}

    def canonical(words):
        key = tuple(words)
        if key not in norm_cache:
            norm_cache[key] = mk.normalize_symptoms(list(words), "ar", conn=conn).get("canonical") or []
        return norm_cache[key]

    def node(nid, ntype, ar, en, **extra):
        nodes.setdefault(nid, {"id": nid, "type": ntype, "ar": ar, "en": en, **extra})
        return nid

    def edge(a, b, kind, ar, en, weight=None, source=None, scope=None, **extra):
        # one edge per (a, b, kind): a repeated link (two words for the same symptom) is merged
        key = (a, b, kind)
        if key in index:
            e = edges[index[key]]
            if weight is not None and (e["w"] is None or weight > e["w"]):
                e["w"] = round(float(weight), 2)
            for k, v in extra.items():
                if isinstance(v, (set, frozenset)):
                    e[k] = set(e.get(k) or ()) | set(v)
            return
        index[key] = len(edges)
        edges.append({"a": a, "b": b, "kind": kind, "ar": ar, "en": en,
                      "w": None if weight is None else round(float(weight), 2), "src": source, "scope": scope, **extra})

    sym = {row[0]: (row[1], row[2]) for row in mk.SYMPTOMS}
    for slug, (ar, en) in sym.items():
        node("symptom:" + slug, "symptom", ar, en)

    def source_node(name_ar, name_en, url):
        key = "source:" + (url or name_en).split("//")[-1].split("/")[0].replace("www.", "") + ":" + hashlib.sha1(str(url or name_en).encode("utf-8")).hexdigest()[:8]
        return node(key, "source", name_ar, name_en, url=url)

    for d in mk.DISEASES:
        cid = node("condition:" + d["slug"], "condition", d["name_ar"], d["name_en"], severity=d.get("severity"))
        srcs = []
        for s in d.get("sources") or []:
            if isinstance(s, (list, tuple)) and len(s) >= 4:
                sid = source_node(s[1], s[2], s[3])
                srcs.append(s[3])
                edge(cid, sid, "condition_source", "مصدر هذه الحالة", "Source for this condition", None, s[3])
        for slug, w in (d.get("symptoms") or {}).items():
            if slug in sym and float(w or 0) > 0:
                _k, tar, ten = mk.symptom_link_band(w)
                edge(cid, "symptom:" + slug, "typical_symptom", f"عرض {tar} في هذه الحالة", f"A {ten} symptom of this condition",
                     float(w), srcs[0] if srcs else None, "condition" if srcs else None)

    refs = blood_test.REFS
    for key, links in blood_test.CBC_ASSOCIATED_SYMPTOMS.items():
        if key not in refs:
            continue
        lid = node("lab:" + key, "lab", refs[key][0], refs[key][1], unit=refs[key][2])
        src = blood_test.DIRECT_SOURCES.get(key) or blood_test.CBC_SOURCE
        sid = source_node(src.get("name"), src.get("name"), src.get("url"))
        edge(lid, sid, "indicator_source", "مرجع هذا المؤشر", "Reference for this indicator", None, src.get("url"))
        for direction in ("low", "high"):
            for phrase in links.get(direction + "_ar") or []:
                for c in canonical([phrase]):
                    if c["slug"] in sym:
                        edge(lid, "symptom:" + c["slug"], "lab_symptom", "", "", None, src.get("url"), "indicator", directions={direction})

    for cat, (user_words, _catalog_words) in mc.SYMPTOM_CATS.items():
        ar, en = mc.CAT_LABEL[cat]
        mid = node("medicine:" + cat, "medicine", "أدوية قد تسبب " + ar, "Medicines that may cause " + en)
        for c in canonical(user_words):
            if c["slug"] in sym:
                edge(mid, "symptom:" + c["slug"], "medicine_group",
                     "ضمن مجموعة " + ar + " في تحذيرات كتالوج الأدوية الموثّق",
                     "Part of the " + en + " group in the sourced medicine catalog warnings")

    _DIR = {frozenset({"low"}): ("انخفاضه قد يصاحبه", "A low value may come with"),
            frozenset({"high"}): ("ارتفاعه قد يصاحبه", "A high value may come with"),
            frozenset({"low", "high"}): ("انخفاضه أو ارتفاعه قد يصاحبه", "A low or high value may come with")}
    for e in edges:
        if e["kind"] == "lab_symptom":
            e["ar"], e["en"] = _DIR[frozenset(e.pop("directions"))]

    linked = {e["a"] for e in edges} | {e["b"] for e in edges}
    # Every symptom in the knowledge base stays (the count matches the health library). A symptom with
    # no condition link is one the red-flag rules send straight to emergency care, and the page says so.
    red, alone = {}, {}
    for rule in mk.RED_RULES:
        for slug in rule[3] or ():
            red.setdefault(slug, (rule[9], rule[10]))
            if rule[4] == "any":
                alone.setdefault(slug, (rule[9], rule[10]))
    for k, v in nodes.items():
        slug = k.split(":", 1)[1] if v["type"] == "symptom" else ""
        if slug and k not in linked and slug in red:
            v["red_flag"] = red[slug]
        if slug in alone:
            v["alarm"] = alone[slug]  # this symptom alone makes the safety rules stop the analysis
    nodes = {k: v for k, v in nodes.items() if k in linked or v.get("red_flag")}
    return _index(nodes, edges)


DATA_PATH = Path(__file__).with_name("knowledge_graph_data.json")


def _index(nodes: dict, edges: list) -> dict:
    adj: dict[str, list[int]] = {}
    for i, e in enumerate(edges):
        adj.setdefault(e["a"], []).append(i)
        adj.setdefault(e["b"], []).append(i)
    counts = {t: sum(1 for n in nodes.values() if n["type"] == t) for t in TYPES}
    return {"nodes": nodes, "edges": edges, "adj": adj, "counts": counts}


def snapshot() -> dict:
    """What tools/build_knowledge_graph.py writes: nodes and edges only (adjacency is rebuilt on load)."""
    g = build()
    return {"nodes": g["nodes"], "edges": g["edges"]}


def write_snapshot(path: Path | None = None) -> Path:
    path = Path(path or DATA_PATH)
    path.write_text(json.dumps(snapshot(), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return path


def graph() -> dict:
    """V292.1: read the pre-built graph shipped with the code (milliseconds, no database, no matching).

    Building it inside a request took seconds of CPU and, if anything failed, was retried by every
    request while holding the lock; on the hosted server that tied up all request threads. A test
    checks that the file equals build(), so it cannot drift from the knowledge base.
    """
    global _GRAPH
    if _GRAPH is None:
        with _LOCK:
            if _GRAPH is None:
                try:
                    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
                    _GRAPH = _index(data["nodes"], data["edges"])
                except (OSError, ValueError, KeyError) as exc:
                    logging.getLogger(__name__).error("knowledge graph data unavailable: %s", type(exc).__name__)
                    _GRAPH = _index({}, [])  # an empty page, never a rebuild storm
    return _GRAPH


def _public(n, lang):
    en = lang == "en"
    out = {"id": n["id"], "type": n["type"], "label": n["en" if en else "ar"], "type_label": _TYPE_LABEL[n["type"]][1 if en else 0]}
    if n.get("url"):
        out["url"] = n["url"]
    if n.get("red_flag"):
        out["note"] = (_RED_NOTE[1] if en else _RED_NOTE[0]) + " " + n["red_flag"][1 if en else 0]
    return out


_RED_NOTE = ("علامة خطر: قواعد الأمان توقف التحليل عند هذا العرض بدل ربطه بحالات.",
             "Red flag: the safety rules stop the analysis at this symptom instead of matching it to conditions.")


def _link(e, n, lang):
    i = 1 if lang == "en" else 0
    out = {"node": _public(n, lang), "kind": e["kind"], "kind_label": KINDS[e["kind"]][i],
           "relation": e["en" if i else "ar"], "weight": e["w"], "evidence_url": e["src"]}
    if e["w"] is not None:
        out["strength"] = __import__("medical_knowledge").symptom_link_band(e["w"])[1 + i]
    if e.get("scope") and e["src"]:
        out["evidence_label"] = _SCOPE[e["scope"]][i]
    if e["kind"] in _LIMITS:
        out["limit"] = _LIMITS[e["kind"]][i]
    return out


def neighborhood(node_id: str, lang: str = "ar", limit: int = 24) -> dict | None:
    g = graph()
    center = g["nodes"].get(node_id)
    if not center:
        return None
    links = []
    for i in g["adj"].get(node_id, []):
        e = g["edges"][i]
        other = e["b"] if e["a"] == node_id else e["a"]
        if other in g["nodes"]:
            links.append((e, g["nodes"][other]))
    # strongest links first, sources last, one link per neighbour
    links.sort(key=lambda x: (x[1]["type"] == "source", -(x[0]["w"] or 0)))
    seen, out = set(), []
    for e, n in links:
        if n["id"] in seen:
            continue
        seen.add(n["id"])
        out.append(_link(e, n, lang))
    by_type = {}
    for x in out:
        by_type[x["node"]["type"]] = by_type.get(x["node"]["type"], 0) + 1
    return {"center": _public(center, lang), "links": out[:limit], "total_links": len(out), "by_type": by_type}


def explore(ids, lang: str = "ar", limit: int = 6) -> dict:
    """V292.1: the conditions that several chosen symptoms share in the knowledge base.

    Only existing condition-symptom links are used (no new medical claims). Conditions that match more
    of the chosen symptoms come first, then the stronger links. A chosen symptom that is a red flag on
    its own is reported separately: the analysis would stop there and send the person for urgent help.
    """
    g = graph()
    i = 1 if lang == "en" else 0
    band = __import__("medical_knowledge").symptom_link_band
    chosen = [x for x in dict.fromkeys(str(v) for v in ids or ()) if g["nodes"].get(x, {}).get("type") == "symptom"][:5]
    found = {}
    for sid in chosen:
        for ei in g["adj"].get(sid, []):
            e = g["edges"][ei]
            if e["kind"] != "typical_symptom":
                continue
            cid = e["a"] if e["b"] == sid else e["b"]
            row = found.setdefault(cid, {"matched": [], "src": e["src"], "score": 0.0})
            row["matched"].append({"symptom": _public(g["nodes"][sid], lang), "strength": band(e["w"])[1 + i]})
            row["score"] += float(e["w"] or 0)
    ranked = sorted(found.items(), key=lambda kv: (-len(kv[1]["matched"]), -kv[1]["score"], g["nodes"][kv[0]]["en"]))
    results = [{"condition": _public(g["nodes"][cid], lang), "count": len(v["matched"]), "matched": v["matched"],
                "source": v["src"], "source_label": _SCOPE["condition"][i]} for cid, v in ranked[:limit]]
    alarms = [{"label": g["nodes"][s]["en" if i else "ar"], "advice": g["nodes"][s]["alarm"][i]} for s in chosen if g["nodes"][s].get("alarm")]
    slugs = {s.split(":", 1)[1] for s in chosen}
    for rule in __import__("medical_knowledge").RED_RULES:  # combinations, e.g. fever + headache + stiff neck
        if rule[4] == "all" and rule[3] and set(rule[3]) <= slugs:
            alarms.append({"label": rule[2] if i else rule[1], "advice": rule[10] if i else rule[9]})
    return {"chosen": [_public(g["nodes"][s], lang) for s in chosen], "results": results, "total": len(found), "alarms": alarms}


def search(q: str, lang: str = "ar", limit: int = 8, only: str | None = None) -> list:
    q = " ".join(str(q or "").split()).lower()
    if not q:
        return []
    g = graph()
    hits = []
    for n in g["nodes"].values():
        if n["type"] == "source" or (only and n["type"] != only):
            continue
        names = (n["ar"] or "").lower(), (n["en"] or "").lower()
        rank = 0 if q in names else (1 if any(x.startswith(q) for x in names) else (2 if any(q in x for x in names) else 9))
        if rank < 9:
            hits.append((rank, len(g["adj"].get(n["id"], [])) * -1, n))
    hits.sort(key=lambda x: (x[0], x[1]))
    return [_public(n, lang) for _r, _d, n in hits[:limit]]


def stats() -> dict:
    g = graph()
    return {"nodes": len(g["nodes"]), "edges": len(g["edges"]), "by_type": g["counts"]}


# ----------------------------------------------------------------------------- page
_T = {
    "ar": {"title": "شبكة المعرفة الصحية", "kicker": "كيف يربط SymptoSense المعلومات",
           "lead": "الروابط نفسها التي يستخدمها محرك التحليل: الأعراض والحالات الصحية ومؤشرات تحليل الدم وآثار الأدوية والمصادر الطبية. اختر أي عنصر لترى ما يرتبط به ولماذا، ومن أي مصدر.",
           "honest": "هذه شبكة معرفة منظّمة من مصادر موثوقة، وليست نموذج ذكاء اصطناعي متعلّم. كل رابط فيها له أصل في قاعدة المعرفة، ولا تُستخدم للتشخيص.",
           "search": "ابحث عن عرض أو حالة أو تحليل…", "try": "جرّب:", "links": "الروابط", "source": "المصدر", "open": "استكشف",
           "nodes": "عنصر", "edges": "رابط", "empty": "لا توجد نتائج. جرّب كلمة أخرى.", "more": "رابطًا آخر غير معروض",
           "chips": [("symptom:dizziness", "دوخة"), ("symptom:headache", "صداع"), ("lab:hgb", "الهيموغلوبين"), ("condition:influenza", "الإنفلونزا"), ("medicine:gi", "آثار دوائية هضمية")]},
    "en": {"title": "Health knowledge graph", "kicker": "How SymptoSense links information",
           "lead": "The same links the analysis engine uses: symptoms, health conditions, blood-test indicators, medicine side-effect groups and medical sources. Pick anything to see what it links to, why, and from which source.",
           "honest": "This is a curated knowledge graph built from trusted sources, not a learned AI model. Every link comes from the knowledge base, and it is not used to diagnose.",
           "search": "Search a symptom, condition or test…", "try": "Try:", "links": "Links", "source": "Source", "open": "Explore",
           "nodes": "items", "edges": "links", "empty": "No results. Try another word.", "more": "more links not shown",
           "chips": [("symptom:dizziness", "Dizziness"), ("symptom:headache", "Headache"), ("lab:hgb", "Hemoglobin"), ("condition:influenza", "Influenza"), ("medicine:gi", "Digestive side effects")]},
}
_TYPE_ORDER = ("condition", "symptom", "lab", "medicine", "source")

CSS = """
.kg{max-width:1080px;margin:0 auto;padding:8px 0 28px}
.kg-kicker{color:#1F6FAE;font-weight:800;font-size:13px;letter-spacing:.3px}
.kg h1{margin:6px 0 8px;font-size:clamp(24px,4vw,34px);line-height:1.3;text-wrap:balance}
.kg-lead{font-size:15.5px;line-height:1.85;color:#334155;max-width:52em;margin:0}
.kg-honest{margin:12px 0 0;font-size:13.5px;line-height:1.75;color:#5B3FA8;background:#F5F1FD;border:1px solid #E4DAF8;border-radius:12px;padding:9px 12px}
.kg-stats{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}
.kg-stat{background:#fff;border:1px solid #E3EAF2;border-radius:12px;padding:6px 12px;font-size:13px;color:#334155}
.kg-stat b{font-size:15px;color:#0F2A44;margin-inline-end:4px}
.kg-search{position:relative;margin-top:6px}
.kg-search input{width:100%;min-height:48px;border-radius:14px;border:1px solid #CFDCEA;padding:0 14px;font-size:16px;background:#fff}
.kg-sugg{position:absolute;inset-inline:0;top:52px;background:#fff;border:1px solid #DCE6F0;border-radius:14px;box-shadow:0 14px 30px rgba(16,42,74,.12);z-index:5;overflow:hidden}
.kg-sugg button{display:flex;justify-content:space-between;gap:10px;width:100%;text-align:start;padding:11px 14px;border:0;background:#fff;font-size:15px;cursor:pointer}
.kg-sugg button:hover,.kg-sugg button:focus{background:#F1F6FB}
.kg-sugg small{color:#64748B}
.kg-chips{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:12px 0 16px;font-size:13.5px;color:#475569}
.kg-chip{border:1px solid #CFDCEA;background:#fff;border-radius:999px;padding:6px 12px;font-size:13.5px;font-weight:700;color:#1F3F5C;cursor:pointer}
.kg-stage{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr);gap:16px;align-items:start}
.kg-canvas{background:#fff;border:1px solid #E3EAF2;border-radius:20px;padding:8px;min-height:420px}
.kg-canvas svg{display:block;width:100%;height:auto}
.kg-canvas .kg-edge{stroke:#CBD7E4;stroke-width:1.4}
.kg-canvas .kg-n{cursor:pointer}
.kg-canvas .kg-n text{font-size:12px;fill:#1E293B;paint-order:stroke;stroke:#fff;stroke-width:4px;stroke-linejoin:round}
.kg-canvas .kg-n:focus circle,.kg-canvas .kg-n:hover circle{stroke:#0F2A44;stroke-width:2.5}
.kg-panel{background:#fff;border:1px solid #E3EAF2;border-radius:20px;padding:16px}
.kg-center-type{font-size:12.5px;font-weight:800}
.kg-center h2{margin:2px 0 10px;font-size:21px;line-height:1.4}
.kg-group h3{font-size:13.5px;color:#475569;margin:14px 0 6px;display:flex;align-items:center;gap:6px}
.kg-group ul{list-style:none;margin:0;padding:0;display:grid;gap:6px}
.kg-link{display:grid;grid-template-columns:1fr auto;gap:2px 10px;align-items:center;border:1px solid #E8EEF5;border-radius:12px;padding:8px 10px}
.kg-link button{all:unset;cursor:pointer;font-weight:700;color:#0F2A44;font-size:14.5px}
.kg-link button:focus-visible{outline:2px solid #1F6FAE;outline-offset:2px;border-radius:4px}
.kg-link small{grid-column:1/2;color:#64748B;font-size:12.5px;line-height:1.6}
.kg-link a{grid-row:1/3;grid-column:2;font-size:12px;font-weight:700;color:#1F6FAE;text-decoration:none;white-space:nowrap}
.kg-dot{width:10px;height:10px;border-radius:50%;display:inline-block;flex:none}
.kg-t-condition{color:#B45309}.kg-t-symptom{color:#1F6FAE}.kg-t-lab{color:#B42318}.kg-t-medicine{color:#6D4BC4}.kg-t-source{color:#15803D}
.kg-d-condition{background:#F59E0B}.kg-d-symptom{background:#3B82C4}.kg-d-lab{background:#E5484D}.kg-d-medicine{background:#8B6CDB}.kg-d-source{background:#22A35A}
.kg-more{font-size:12.5px;color:#64748B;margin-top:8px}
.kg-limit{margin:6px 0 0;font-size:12.5px;line-height:1.7;color:#5B6B7F;background:#F6F8FB;border-radius:10px;padding:6px 10px}
.kg-x{background:#fff;border:1px solid #E3ECF6;border-radius:20px;padding:18px 20px;margin:6px 0 18px;box-shadow:0 8px 24px rgba(15,52,96,.06)}
.kg-x h2{margin:0 0 4px;font-size:20px}.kg-x-lead{margin:0 0 12px;color:#475569;font-size:14.5px;line-height:1.7}
.kg-x-row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.kg-x-search{flex:1 1 260px;margin:0}
.kg-x-chosen{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 4px}
.kg-x-tag{display:inline-flex;align-items:center;gap:6px;background:#EAF3FD;color:#1F6FAE;border-radius:999px;padding:6px 8px 6px 12px;font-weight:700;font-size:14px}
.kg-x-tag button{border:0;background:#fff;color:#1F6FAE;width:24px;height:24px;border-radius:50%;cursor:pointer;font-size:15px;line-height:1}
.kg-x-out{margin-top:10px}.kg-x-hint{color:#64748B;font-size:14px;margin:6px 0}
.kg-x-alarm{background:#FDECEA;color:#8A1C12;border-radius:12px;padding:10px 12px;font-size:14px;line-height:1.7;margin:8px 0}
.kg-x-list{list-style:none;margin:8px 0 0;padding:0;display:grid;gap:8px}
.kg-x-item{border:1px solid #E8EEF5;border-radius:14px;padding:10px 12px;display:grid;gap:6px}
.kg-x-head{display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap}
.kg-x-head button{border:0;background:none;padding:0;font:inherit;font-weight:800;font-size:15.5px;color:#0F2C4C;cursor:pointer;text-align:start}
.kg-x-count{font-size:12.5px;font-weight:800;color:#1F6FAE;background:#EAF3FD;border-radius:999px;padding:3px 10px;white-space:nowrap}
.kg-x-m{display:flex;flex-wrap:wrap;gap:6px;font-size:13px;color:#475569}.kg-x-m span{background:#F6F8FB;border-radius:8px;padding:3px 8px}
.kg-x-src{font-size:12.5px;font-weight:700;color:#1F6FAE;text-decoration:none}
@media (max-width:767px){.kg-x{padding:14px;border-radius:16px}.kg-stage{grid-template-columns:1fr}.kg-canvas{display:none}.kg-panel{padding:14px;border-radius:16px}.kg-lead{font-size:15px}.kg-honest{font-size:13px;padding:8px 10px}.kg-stats{gap:6px;margin:10px 0}.kg-stat{font-size:12px;padding:4px 9px;border-radius:10px}.kg-stat b{font-size:13px}.kg-chips{flex-wrap:nowrap;overflow-x:auto;padding-bottom:4px;margin:10px 0 12px;scrollbar-width:none}.kg-chip{white-space:nowrap;flex:none}.kg-chips>span{flex:none;white-space:nowrap}}
"""


# V292.1: the multi-symptom explorer ("which conditions do these symptoms share?")
_X = {
    "ar": {"title": "قارن عدة أعراض", "lead": "اختر حتى ٥ أعراض لترى الحالات التي تجمعها في قاعدة المعرفة، وقوة كل رابط، ومصدره.",
           "ph": "أضف عرضًا…", "try": "جرّب: صداع + حمى", "remove": "إزالة", "pick": "اختر عرضًا واحدًا على الأقل.",
           "none": "لا توجد حالة في قاعدة المعرفة تجمع هذه الأعراض.", "match": "يجمع {n} من {m}", "open": "افتح في الشبكة",
           "more": "حالة أخرى ترتبط بعرض واحد على الأقل", "alarm": "تنبيه أمان",
           "note": "هذه روابط من قاعدة المعرفة لتفهم العلاقة بين الأعراض، وليست تشخيصًا. لتقييم حالتك استخدم تحليل الأعراض.",
           "cta": "حلّل أعراضي", "cta_href": "/ar/chat"},
    "en": {"title": "Compare several symptoms", "lead": "Pick up to 5 symptoms to see the conditions they share in the knowledge base, how strong each link is, and its source.",
           "ph": "Add a symptom…", "try": "Try: headache + fever", "remove": "Remove", "pick": "Pick at least one symptom.",
           "none": "No condition in the knowledge base links these symptoms together.", "match": "{n} of {m} match", "open": "Open in the graph",
           "more": "more conditions linked to at least one symptom", "alarm": "Safety note",
           "note": "These are knowledge-base links to help you understand how symptoms relate, not a diagnosis. To assess your own case, use the symptom analysis.",
           "cta": "Analyse my symptoms", "cta_href": "/en/chat"},
}


def render_page(lang: str = "ar") -> tuple[str, str, str]:
    t = _T["en" if lang == "en" else "ar"]
    esc = html.escape
    st = stats()
    stat_html = "".join('<span class="kg-stat"><b>%d</b>%s</span>' % (st["by_type"][k], esc(_TYPE_LABEL[k][1 if lang == "en" else 0]))
                        for k in _TYPE_ORDER if st["by_type"].get(k))
    stat_html += '<span class="kg-stat"><b>%d</b>%s</span>' % (st["edges"], esc(t["edges"]))
    chips = "".join('<button type="button" class="kg-chip" data-kg-node="%s">%s</button>' % (esc(nid), esc(label)) for nid, label in t["chips"])
    labels = {k: _TYPE_LABEL[k][1 if lang == "en" else 0] for k in TYPES}
    x = _X["en" if lang == "en" else "ar"]
    body = f"""<main class="kg" id="kgRoot" data-lang="{'en' if lang == 'en' else 'ar'}" data-start="symptom:dizziness">
<p class="kg-kicker">{esc(t['kicker'])}</p>
<h1>{esc(t['title'])}</h1>
<p class="kg-lead">{esc(t['lead'])}</p>
<p class="kg-honest">{esc(t['honest'])}</p>
<div class="kg-stats">{stat_html}</div>
<div class="kg-search"><label class="sr-only" for="kgSearch">{esc(t['search'])}</label>
<input id="kgSearch" type="search" autocomplete="off" placeholder="{esc(t['search'])}" aria-controls="kgSugg"><div class="kg-sugg" id="kgSugg" hidden></div></div>
<div class="kg-chips"><span>{esc(t['try'])}</span>{chips}</div>
<section class="kg-x" id="kgX" aria-labelledby="kgXTitle">
<h2 id="kgXTitle">{esc(x['title'])}</h2><p class="kg-x-lead">{esc(x['lead'])}</p>
<div class="kg-x-row"><div class="kg-search kg-x-search"><label class="sr-only" for="kgXInput">{esc(x['ph'])}</label>
<input id="kgXInput" type="search" autocomplete="off" placeholder="{esc(x['ph'])}" aria-controls="kgXSugg"><div class="kg-sugg" id="kgXSugg" hidden></div></div>
<button type="button" class="kg-chip kg-x-try" id="kgXTry">{esc(x['try'])}</button></div>
<div class="kg-x-chosen" id="kgXChosen"></div>
<div class="kg-x-out" id="kgXOut" aria-live="polite"><p class="kg-x-hint">{esc(x['pick'])}</p></div>
<p class="kg-limit">{esc(x['note'])} <a href="{esc(x['cta_href'])}">{esc(x['cta'])}</a></p>
</section>
<div class="kg-stage"><div class="kg-canvas" id="kgCanvas" aria-hidden="true"></div><section class="kg-panel" id="kgPanel" aria-live="polite"></section></div>
<script type="application/json" id="kgText">{html.escape(__import__('json').dumps({"labels": labels, "source": t["source"], "links": t["links"], "empty": t["empty"], "more": t["more"], "x": x}, ensure_ascii=False), quote=False)}</script>
<script src="/static/js/knowledge-graph.js?v=__ASSET_VERSION__"></script>
</main>"""
    return t["title"], body, CSS


def register_routes(app, *, page, lang_getter, request_allowed, **_):
    from flask import jsonify, request

    @app.route("/knowledge-graph")
    def knowledge_graph_page():
        title, body, css = render_page(lang_getter())
        return page(title, body, extra_css=css)

    @app.route("/api/knowledge-graph")
    def api_knowledge_graph():
        if not request_allowed("knowledge_graph", 120, 60):
            return jsonify({"ok": False, "error": "rate_limited"}), 429
        lang = "en" if str(request.args.get("lang") or "").startswith("en") else "ar"
        q = request.args.get("q")
        if q is not None:
            only = "symptom" if request.args.get("type") == "symptom" else None
            return jsonify({"ok": True, "results": search(q[:60], lang, only=only)})
        if request.args.get("explore") is not None:
            ids = [x.strip() for x in str(request.args.get("explore"))[:600].split(",") if x.strip()]
            return jsonify({"ok": True, **explore(ids, lang)})
        data = neighborhood(str(request.args.get("node") or "")[:120], lang)
        if data is None:
            return jsonify({"ok": False, "error": "not_found"}), 404
        return jsonify({"ok": True, **data})
