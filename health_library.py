"""Public health-library presentation layer.

The knowledge-base tables remain the source of truth. This module adds only
browse/detail presentation, anonymous click analytics, and source/review cues.
"""
from __future__ import annotations

import html as html_lib
import json
import re
import threading
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import db
import medical_knowledge as mk
import medical_taxonomy
import symptom_guidance

_CATEGORY_ORDER = [
    "pain", "respiratory", "digestive", "neurological", "cardiovascular",
    "skin", "eye", "musculoskeletal", "womens_health", "mental-health", "general",
]

_USAGE_SCHEMA_READY = None
_USAGE_SCHEMA_LOCK = threading.Lock()


def _serial():
    return "SERIAL PRIMARY KEY" if db.USE_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _categories():
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute("SELECT id, slug, name_ar, name_en FROM mk_categories")
        rows = c.fetchall()
    finally:
        conn.close()
    return {r[0]: {"slug": r[1], "name_ar": r[2], "name_en": r[3]} for r in rows}


def _entity_by_slug(kind, slug):
    mk.init_schema()
    table = "mk_diseases" if kind == "disease" else "mk_symptoms"
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute(f"SELECT id FROM {table} WHERE slug={db.PH} AND status='active'", (slug,))
        row = c.fetchone()
    finally:
        conn.close()
    if not row:
        return None
    # Public library pages must meet the stricter publication rule: at least
    # one verified Saudi source and one independent verified global source.
    # Non-compliant legacy knowledge can still support internal analysis, but
    # is not presented as a fully sourced public article.
    if not mk.public_source_ready(kind, int(row[0])):
        return None
    return mk.get_entity(kind, row[0], public=True)


def init_usage_schema():
    """Create click-analytics storage once per process/database identity.

    Re-running CREATE TABLE/INDEX on every public library request adds a remote
    PostgreSQL round trip even though the schema almost never changes.
    """
    global _USAGE_SCHEMA_READY
    identity = db._database_identity()
    if _USAGE_SCHEMA_READY == identity:
        return
    with _USAGE_SCHEMA_LOCK:
        if _USAGE_SCHEMA_READY == identity:
            return
        db.init_db(); conn = db._conn(); c = conn.cursor()
        try:
            c.execute(f"""
                CREATE TABLE IF NOT EXISTS health_library_clicks (
                    id {_serial()}, kind TEXT NOT NULL, slug TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_hl_clicks_time ON health_library_clicks(created_at)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_hl_clicks_item ON health_library_clicks(kind,slug,created_at)")
            conn.commit()
            _USAGE_SCHEMA_READY = identity
        finally:
            conn.close()


def record_click(kind: str, slug: str):
    if kind not in {"disease", "symptom"} or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,150}", str(slug or ""), re.I):
        return False
    init_usage_schema(); conn = db._conn(); c = conn.cursor()
    try:
        c.execute(
            f"INSERT INTO health_library_clicks(kind,slug,created_at) VALUES({db.PH},{db.PH},{db.PH})",
            (kind, slug, _now()),
        )
        conn.commit(); return True
    finally:
        conn.close()


def popular_counts(days=7):
    init_usage_schema(); cutoff = (datetime.now(timezone.utc) - timedelta(days=max(1, int(days)))).replace(microsecond=0).isoformat()
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute(
            f"SELECT kind,slug,COUNT(*) FROM health_library_clicks WHERE created_at>={db.PH} GROUP BY kind,slug ORDER BY COUNT(*) DESC",
            (cutoff,),
        )
        return {(r[0], r[1]): int(r[2]) for r in c.fetchall()}
    finally:
        conn.close()


def _sort_key(name: str, ar: bool) -> str:
    text=str(name or "").strip().casefold()
    if ar:
        text=re.sub(r"[\u064b-\u065f\u0670]", "", text)
        text=text.translate(str.maketrans({"أ":"ا","إ":"ا","آ":"ا","ى":"ي","ؤ":"و","ئ":"ي","ة":"ه"}))
    return text


def _pain_bucket(name: str, ar: bool) -> str:
    n = str(name or "").lower()
    head = ("رأس", "راس", "صداع", "رقبة", "وجه", "فك", "head", "neck", "face", "jaw", "migraine")
    torso = ("صدر", "بطن", "معدة", "حوض", "خاصرة", "ضل", "chest", "abdomen", "abdominal", "stomach", "pelvic", "flank", "rib")
    limb = ("يد", "ذراع", "كتف", "ساق", "قدم", "كاحل", "فخذ", "ركبة", "arm", "hand", "leg", "foot", "ankle", "thigh", "knee")
    if any(k.lower() in n for k in head):
        return "ألم الرأس والرقبة" if ar else "Head & neck pain"
    if any(k.lower() in n for k in torso):
        return "ألم الصدر والبطن" if ar else "Chest & abdominal pain"
    if any(k.lower() in n for k in limb):
        return "ألم الأطراف" if ar else "Limb pain"
    return "ألم المفاصل والعضلات" if ar else "Joint & muscle pain"


def _short_description(value: str, limit: int = 118) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return ""
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip("،,.;؛: ")
    return (cut or text[:limit]).rstrip() + "…"


def _chip(item, kind, ar, prefix, popular=False):
    esc = lambda s: html_lib.escape(str(s or ""), quote=True)
    name = item.get("name_ar" if ar else "name_en") or item.get("slug")
    description = _short_description(item.get("description_ar" if ar else "description_en")) if kind == "symptom" else ""
    icon = "📋" if kind == "disease" else '<span class="hl-sym-dot" aria-hidden="true"></span>'
    pop = " hl-pop" if popular else ""
    search_text = (str(name or "") + " " + str(description or "")).strip()
    if kind == "symptom":
        content = (f'<span class="hl-kind-icon">{icon}</span><span class="hl-chip-main"><b>{esc(name)}</b>'
                   f'<small>{esc(description or ("شرح مختصر غير متوفر بعد." if ar else "A short description is not available yet."))}</small></span>')
    else:
        content = f'<span class="hl-kind-icon">{icon}</span><span>{esc(name)}</span>'
    return (
        f'<a class="hl-chip hl-chip-{kind}{pop}" data-hl-kind="{kind}" data-hl-slug="{esc(item["slug"])}" '
        f'data-hl-search="{esc(search_text)}" href="{prefix}/health-library/{kind}/{esc(item["slug"])}">{content}</a>'
    )


def index(lang: str) -> str:
    ar = lang != "en"; esc = lambda s: html_lib.escape(str(s or ""), quote=True)
    prefix = "/ar" if ar else "/en"
    mk.init_schema(); cats = _categories(); counts = popular_counts(7)
    # V208: evaluate publication readiness in two bulk queries instead of one
    # source-policy query per entity (hundreds of DB round trips on this page).
    ready_diseases = mk.public_source_ready_ids("disease")
    ready_symptoms = mk.public_source_ready_ids("symptom")
    diseases = [x for x in mk.list_entities("diseases", False, "") if int(x["id"]) in ready_diseases]
    symptoms = [x for x in mk.list_entities("symptoms", False, "") if int(x["id"]) in ready_symptoms]
    by_cat = {}
    for kind, items in (("disease", diseases), ("symptom", symptoms)):
        for item in items:
            cat = cats.get(item.get("category_id"), {"slug": "general", "name_ar": "أعراض عامة", "name_en": "General"})
            by_cat.setdefault(cat["slug"], {"cat": cat, "items": []})["items"].append((kind, item))
    ordered_slugs = [s for s in _CATEGORY_ORDER if s in by_cat] + [s for s in by_cat if s not in _CATEGORY_ORDER]
    title = "مكتبة SymptoSense الصحية" if ar else "SymptoSense Health Library"
    subtitle = (
        f"{len(diseases)} حالة طبية و{len(symptoms)} عرضًا، مع بحث فوري وتنظيم أوضح للوصول للمعلومة بسرعة."
        if ar else f"{len(diseases)} conditions and {len(symptoms)} symptoms, with instant search and clearer navigation."
    )
    nav = [] ; sections = []
    for slug in ordered_slugs:
        group = by_cat[slug]; cat = group["cat"]; cat_name = cat["name_ar"] if ar else cat["name_en"]
        items = sorted(group["items"], key=lambda ki: _sort_key(ki[1].get("name_ar" if ar else "name_en") or "", ar))
        if not items: continue
        nav.append(f'<a href="#{esc(slug)}">{esc(cat_name)} <span>{len(items)}</span></a>')
        ranked = sorted(items, key=lambda ki: counts.get((ki[0], ki[1]["slug"]), 0), reverse=True)
        hot = [ki for ki in ranked if counts.get((ki[0], ki[1]["slug"]), 0) > 0][:5]
        hot_html = ""
        if hot:
            hot_html = '<div class="hl-hot"><b>🔥 '+("الأكثر بحثًا هذا الأسبوع" if ar else "Most viewed this week")+'</b><div class="hl-chip-row">'+"".join(_chip(i,k,ar,prefix,True) for k,i in hot)+'</div></div>'
        if slug == "pain" and len(items) > 25:
            buckets = {}
            for kind, item in items:
                name = item.get("name_ar" if ar else "name_en") or item["slug"]
                buckets.setdefault(_pain_bucket(name, ar), []).append((kind,item))
            order = (["ألم الرأس والرقبة","ألم الصدر والبطن","ألم المفاصل والعضلات","ألم الأطراف"] if ar else ["Head & neck pain","Chest & abdominal pain","Joint & muscle pain","Limb pain"])
            lists = []
            for label in order:
                vals = buckets.get(label) or []
                if vals:
                    lists.append(f'<div class="hl-subgroup"><h3>{esc(label)}</h3><div class="hl-chip-row">'+"".join(_chip(i,k,ar,prefix) for k,i in vals)+'</div></div>')
            all_html = "".join(lists)
        else:
            all_html = '<div class="hl-chip-row">'+"".join(_chip(i,k,ar,prefix) for k,i in items)+'</div>'
        sections.append(f'<section class="ss-card hl-section" id="{esc(slug)}"><h2>{esc(cat_name)} <span class="ss-muted">({len(items)})</span></h2>{hot_html}{all_html}</section>')
    no_results = "لا توجد نتائج مطابقة." if ar else "No matching results."
    return f'''<main class="container hl-shell">
<section class="ss-card hl-head"><span class="ss-badge">📚 {"مكتبة" if ar else "Library"}</span><h1>{esc(title)}</h1><p class="ss-muted">{esc(subtitle)}</p>
<div class="hl-search"><span>🔎</span><input id="hlSearch" type="search" placeholder="{esc('ابحث عن عرض أو حالة طبية…' if ar else 'Search symptoms or conditions…')}" autocomplete="off"></div>
<div class="hl-key"><span>📋 {"حالة طبية" if ar else "Condition"}</span><span><i class="hl-sym-dot"></i> {"عرض" if ar else "Symptom"}</span></div></section>
<div class="hl-layout"><aside class="hl-sidebar"><b>{esc('الأقسام' if ar else 'Sections')}</b>{''.join(nav)}</aside><div class="hl-content">{''.join(sections)}<div id="hlEmpty" class="ss-card hl-empty" hidden>{esc(no_results)}</div></div></div>
<style>
.hl-shell{{max-width:1120px;padding-top:24px;padding-bottom:60px}}.hl-head{{text-align:center;margin-bottom:14px}}.hl-head h1{{margin:8px 0 4px}}.hl-search{{max-width:680px;margin:18px auto 6px;display:flex;align-items:center;gap:9px;border:1px solid #cfe0ea;border-radius:15px;padding:4px 13px;background:#fff}}.hl-search input{{width:100%;border:0;outline:0;padding:11px 2px;font:inherit;background:transparent}}.hl-key{{display:flex;justify-content:center;gap:18px;font-size:12px;color:#657c8b;margin-top:10px}}.hl-layout{{display:grid;grid-template-columns:210px minmax(0,1fr);gap:14px;align-items:start}}.hl-sidebar{{position:sticky;top:86px;background:#fff;border:1px solid var(--v2-line,#dceafa);border-radius:18px;padding:14px;max-height:calc(100vh - 110px);overflow:auto}}.hl-sidebar b{{display:block;color:#174e73;margin-bottom:8px}}.hl-sidebar a{{display:flex;justify-content:space-between;gap:8px;padding:8px 6px;text-decoration:none;color:#496477;border-radius:9px;font-size:12px}}.hl-sidebar a:hover{{background:#f2f8fc}}.hl-content{{min-width:0}}.hl-section{{scroll-margin-top:90px;margin-bottom:13px}}.hl-section h2{{margin-top:0}}.hl-section h2 .ss-muted{{font-size:13px;font-weight:600}}.hl-chip-row{{display:flex;flex-wrap:wrap;gap:8px}}.hl-chip{{display:inline-flex;align-items:center;gap:7px;padding:8px 12px;border-radius:13px;font-size:13px;font-weight:750;text-decoration:none;border:1px solid var(--border-card,#DCEBFA);transition:.16s}}.hl-chip-disease{{background:#f5f9ff;color:#123B70;border-color:#cfe0f1}}.hl-chip-symptom{{background:#F4FBF6;color:#1B6B3A;border-color:#D6EEDD;align-items:flex-start;width:calc(50% - 4px);min-width:260px;padding:11px 12px}}.hl-chip-main{{display:grid;gap:3px;min-width:0;text-align:start}}.hl-chip-main b{{font-size:13.5px;color:#185f35;line-height:1.45}}.hl-chip-main small{{font-size:11.5px;font-weight:500;color:#5e7467;line-height:1.6}}.hl-chip:hover{{transform:translateY(-1px);filter:brightness(.98)}}.hl-kind-icon{{display:inline-flex;align-items:center}}.hl-sym-dot{{display:inline-block;width:8px;height:8px;border-radius:50%;background:#38a169;vertical-align:middle}}.hl-hot{{margin:0 0 14px;padding:11px;border-radius:14px;background:#fff9ec;border:1px solid #f0dfad}}.hl-hot>b{{display:block;font-size:12px;color:#74591d;margin-bottom:8px}}.hl-chip.hl-pop{{background:#fff;border-color:#e7c769}}.hl-subgroup{{margin:15px 0}}.hl-subgroup h3{{font-size:14px;color:#47687c;margin:0 0 8px}}.hl-empty{{text-align:center;color:#667c8b}}@media(max-width:900px){{.hl-layout{{grid-template-columns:1fr}}.hl-sidebar{{display:none}}}}@media(max-width:520px){{.hl-chip{{font-size:12px;padding:7px 10px}}.hl-chip-symptom{{width:100%;min-width:0;padding:10px}}.hl-chip-main b{{font-size:13px}}.hl-chip-main small{{font-size:11px}}.hl-shell{{padding-inline:10px}}}}
</style>
<script>
(function(){{
 const q=document.getElementById('hlSearch'), chips=[...document.querySelectorAll('.hl-chip:not(.hl-pop)')], empty=document.getElementById('hlEmpty'), hotBlocks=[...document.querySelectorAll('.hl-hot')];
 function norm(v){{return String(v||'').toLowerCase().normalize('NFKD').replace(/[\u064B-\u065F\u0670]/g,'').replace(/[أإآ]/g,'ا').replace(/ى/g,'ي').trim()}}
 function run(){{const term=norm(q.value), sections=[...document.querySelectorAll('.hl-section')];let visible=0;hotBlocks.forEach(h=>h.style.display=term?'none':'block');chips.forEach(a=>{{const ok=!term||norm(a.dataset.hlSearch).includes(term);a.style.display=ok?'inline-flex':'none';if(ok)visible++}});sections.forEach(sec=>{{const any=[...sec.querySelectorAll('.hl-chip:not(.hl-pop)')].some(a=>a.style.display!=='none');sec.style.display=any?'block':'none'}});empty.hidden=visible!==0}}
 q.addEventListener('input',run);
 document.addEventListener('click',function(e){{const a=e.target.closest('.hl-chip[data-hl-kind]');if(!a)return;const body=JSON.stringify({{kind:a.dataset.hlKind,slug:a.dataset.hlSlug}});try{{if(navigator.sendBeacon)navigator.sendBeacon('/api/health-library/click',new Blob([body],{{type:'application/json'}}));else fetch('/api/health-library/click',{{method:'POST',headers:{{'Content-Type':'application/json'}},body,keepalive:true}})}}catch(_){{}}}});
}})();
</script></main>'''


def detail(kind: str, slug: str, lang: str):
    item = _entity_by_slug(kind, slug)
    if not item: return None
    ar = lang != "en"; esc = lambda s: html_lib.escape(str(s or ""), quote=True); suf = "_ar" if ar else "_en"; prefix = "/ar" if ar else "/en"
    name = item.get("name" + suf) or slug; description = item.get("description" + suf) or ""
    if kind != "disease":
        import symptom_page_safety as _sps
        description = _sps.description(description, name, ar)
    page_title = name; meta_desc = description[:155] if description else name
    def block(la,le,value):
        if not value: return ""
        text = value if isinstance(value,str) else " • ".join(str(v) for v in value)
        return f'<section class="ss-card"><h2>{esc(la if ar else le)}</h2><p style="white-space:pre-line">{esc(text)}</p></section>' if text.strip() else ""
    kind_label = (("حالة طبية" if ar else "Medical condition") if kind=="disease" else ("عرض" if ar else "Symptom"))
    body_parts=[f'<section class="ss-card" style="text-align:center"><span class="ss-badge">{esc(kind_label)}</span><h1>{esc(name)}</h1><p>{esc(description)}</p></section>']
    cats=_categories(); cat=cats.get(item.get("category_id"), {"slug":"general"})
    system=medical_taxonomy.category_system(cat.get("slug") or "general", "ar" if ar else "en")
    mapping=medical_taxonomy.approved_mapping(kind, int(item.get("id")))
    map_bits=[esc(system.get("label"))]
    if mapping and mapping.get("icd_code"):
        map_bits.append("ICD-11: "+esc(mapping.get("icd_code")))
    body_parts.append(f'<section class="ss-card hl-tax"><h2>{esc("التصنيف الطبي" if ar else "Medical taxonomy")}</h2><p>{" · ".join(map_bits)}</p><small>{esc("يستخدم التصنيف لتنظيم المحتوى، ولا يعني تشخيصًا." if ar else "Taxonomy is used to organize content and does not represent a diagnosis.")}</small></section>')
    if kind=="disease":
        body_parts += [block("الأسباب الشائعة","Common causes",item.get("common_causes"+suf)),block("عوامل الخطورة","Risk factors",item.get("risk_factors"+suf)),block("علامات الخطر — اطلب رعاية عاجلة","Red flags — seek urgent care",item.get("red_flags"+suf)),block("الخطوة التالية المقترحة","Suggested next step",item.get("recommended_next_step"+suf))]
    else:
        _sb, _ss = _sps.banner_and_section(slug, ar, prefix)
        if _sb: body_parts.insert(0, _sb)
        if _ss: body_parts.append(_ss)
        if slug in _sps.STRONG: body_parts.append(_sps.details_section(slug, ar))
        body_parts.append(block("علامات الخطر المرتبطة","Related red flags",item.get("red_flags"+suf)))
        guidance=symptom_guidance.ensure_for_symptom(int(item.get("id"))) or {}
        questions=guidance.get("followup_questions_ar" if ar else "followup_questions_en") or []
        if questions:
            lis="".join(f'<li>{esc(q)}</li>' for q in questions[:5])
            body_parts.append(f'<section class="ss-card"><h2>{esc("أسئلة تساعد على توضيح الصورة" if ar else "Questions that help clarify the picture")}</h2><ol class="hl-q">{lis}</ol></section>')
        body_parts.append(block("متى أطلب تقييمًا طبيًا؟","When should I seek medical care?",guidance.get("when_to_seek_care_ar" if ar else "when_to_seek_care_en")))
    sources = item.get("sources") or []
    source_cards=[]
    for src in sources:
        url=src.get("reference_url") or src.get("official_url") or "#"; title=src.get("reference_title_ar" if ar else "reference_title_en") or src.get("source_name") or src.get("organization")
        source_cards.append(f'<a class="hl-source" href="{esc(url)}" target="_blank" rel="noopener noreferrer"><b>{esc(__import__("source_names").display(src, ar))}</b><span>{esc(title)}</span></a>')
    reviewed = item.get("last_updated") or item.get("updated_at") or next((x.get("last_verified") for x in sources if x.get("last_verified")), None) or "—"
    source_note = '<p class="hl-source-ok">✓ '+esc("تتضمن الصفحة مصادر سعودية وعالمية داعمة للمحتوى." if ar else "At least one verified Saudi source and one independent global source are linked.")+'</p>'
    body_parts.append(f'<section class="ss-card"><div class="hl-review"><h2>{esc("المصادر والمراجعة" if ar else "Sources & review")}</h2><span>{esc("آخر مراجعة: " if ar else "Last reviewed: ")}{esc(str(reviewed)[:10])}</span></div><div class="hl-sources">{"".join(source_cards)}</div>{source_note}</section>')
    disclaimer=("هذه الصفحة توعوية عامة ولا تُغني عن استشارة طبية. إذا كانت أعراضك شديدة أو مقلقة، تواصل مع مختص صحي." if ar else "This page is general educational information, not a medical consultation. If symptoms are severe or worrying, contact a healthcare professional.")
    body_parts.append(f'<section class="ss-card" style="text-align:center"><a class="ss-btn ss-btn-primary" href="{prefix}/chat">{esc("افحص أعراضك الآن ←" if ar else "Check your symptoms now →")}</a><p class="ss-muted" style="font-size:12px;margin-top:10px">{esc(disclaimer)}</p></section>')
    body=f'''<main class="container" style="max-width:780px;padding-top:24px;padding-bottom:60px"><div class="ss-stack">{"".join(body_parts)}<p style="text-align:center"><a href="{prefix}/health-library">{esc("← رجوع للمكتبة" if ar else "← Back to the library")}</a></p></div><style>.hl-review{{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}}.hl-review h2{{margin:0}}.hl-review span{{font-size:12px;color:#6b7e8d}}.hl-sources{{display:grid;gap:8px;margin-top:12px}}.hl-source{{display:grid;gap:2px;text-decoration:none;border:1px solid #d9e8f1;border-radius:12px;padding:10px 12px;background:#f8fbfd;color:#36586d}}.hl-source b{{color:#176f9e}}.hl-source span{{font-size:12px}}.hl-source-gap{{margin-top:10px;padding:10px;border-radius:11px;background:#fff9ec;color:#755a18;font-size:12px;line-height:1.7}}.hl-source-ok{{margin-top:10px;padding:10px;border-radius:11px;background:#eef9f3;color:#246746;font-size:12px;line-height:1.7}}.hl-q{{line-height:1.9;padding-inline-start:22px}}.hl-tax small{{color:#6b7e8d}}</style></main>'''
    return page_title, meta_desc, body


def source_quality_audit():
    """Report legacy pages that do not yet meet the two-source publication policy.

    Existing pages are flagged for editorial review rather than being assigned
    made-up references. New active content is blocked at save time until it has
    both a Saudi source (MOH/SFDA) and an independent global source.
    """
    mk.init_schema(); rows=[]
    for kind, plural in (("disease","diseases"),("symptom","symptoms")):
        for item in mk.list_entities(plural, False, ""):
            full=mk.get_entity(kind,int(item["id"]),public=False); sources=(full or {}).get("sources") or []
            hosts=[]
            for src in sources:
                host=(urlparse(str(src.get("reference_url") or src.get("official_url") or "")).hostname or "").lower()
                hosts.append(host)
            has_local=any(h=="moh.gov.sa" or h.endswith(".moh.gov.sa") or h=="sfda.gov.sa" or h.endswith(".sfda.gov.sa") for h in hosts)
            has_global=any(h and not (h=="moh.gov.sa" or h.endswith(".moh.gov.sa") or h=="sfda.gov.sa" or h.endswith(".sfda.gov.sa")) for h in hosts)
            if len(sources)<2 or not has_local or not has_global:
                rows.append({"kind":kind,"slug":item["slug"],"source_count":len(sources),"has_local":has_local,"has_global":has_global,"needs_review":True})
    return rows


def all_slugs():
    mk.init_schema(); out=[]
    for d in mk.list_entities("diseases",False,""): out.append(("disease",d["slug"]))
    for s in mk.list_entities("symptoms",False,""): out.append(("symptom",s["slug"]))
    return out
