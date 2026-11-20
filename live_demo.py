"""Public 3-minute demo (/live-demo; the older /demo opens the chat demo mode): four fixed scenarios run through the REAL engine.

Every result on the page is produced by the same code as a live analysis
(safety_engine.evaluate -> analysis_core.run_analysis), never a canned answer.
Nothing is saved: the patients are synthetic, user_id is None (run_analysis only
persists for signed-in accounts), and no consent-bound data is touched.

Offline: the page embeds the four results computed when it was rendered, so once it
has loaded the scenario buttons work without a network. "Run again" calls
/api/demo/run to prove the result is computed live and to show the latency.
"""
from __future__ import annotations

import html
import json
import threading
import time

import analysis_core
import clinical_text
import red_flag_concepts
import safety_engine

SCENARIOS = (
    {
        "id": "mild",
        "title_ar": "صداع خفيف", "title_en": "Mild headache",
        "point_ar": "حالة عادية: لا علامة خطر، والنتيجة رعاية ذاتية مع متى تراجع الطبيب.",
        "point_en": "An everyday case: no red flag, so the result is self-care plus when to see a doctor.",
        "text": "صداع خفيف من أمس بعد قلة نوم، ما عندي حرارة ولا تقيؤ",
        "text_en": "Mild headache since yesterday after poor sleep; no fever and no vomiting.",
        "age": 24, "severity": 2,
    },
    {
        "id": "msa",
        "title_ar": "طوارئ بالفصحى", "title_en": "Emergency (formal Arabic)",
        "point_ar": "نمط حساسية شديدة مكتوب بلغة طبية فصيحة: تتوقف المطابقة ويظهر تنبيه الطوارئ.",
        "point_en": "A severe allergic reaction written in formal Arabic: matching stops and the emergency alert appears.",
        "text": "تورم مفاجئ في الشفتين واللسان مع صعوبة شديدة في التنفس بعد تناول الطعام",
        "text_en": "Sudden swelling of the lips and tongue with severe difficulty breathing after eating.",
        "age": 35, "severity": 2,
    },
    {
        "id": "dialect",
        "title_ar": "نفس الطوارئ بالعامية وبأخطاء إملائية", "title_en": "Same emergency: dialect + typos",
        "point_ar": "نفس الحالة كما يكتبها شخص خائف: لهجة سعودية وخطأ إملائي («شفيفي»). النظام يصحح ويصل لنفس القرار.",
        "point_en": "The same case as a scared person types it: Saudi dialect and a typo (“شفيفي”). The engine corrects it and reaches the same decision.",
        "text": "بعد ما اكلت انتفخت شفيفي ولساني وصار نفسي ضيق مرره",
        "text_en": "(Saudi dialect, with a typo) After I ate my lips and tongue swelled up and my breath got really tight.",
        "age": 35, "severity": 2,
    },
    {
        "id": "negation",
        "title_ar": "نفي الأعراض", "title_en": "Denied symptoms",
        "point_ar": "الكلمات الخطرة موجودة لكن منفية («ما عندي ألم صدر»). نظام يبحث عن كلمات فقط كان سيطلق إنذارًا خاطئًا.",
        "point_en": "Dangerous words appear but are denied (“no chest pain”). A keyword matcher would raise a false alarm.",
        "text": "ما عندي ألم صدر ولا ضيق تنفس، بس عندي زكام وسيلان خفيف",
        "text_en": "I don't have chest pain or shortness of breath, just a cold and a mild runny nose.",
        "age": 35, "severity": 2,
    },
)
_BY_ID = {s["id"]: s for s in SCENARIOS}
_LEVEL = {"high": ("طوارئ الآن — اتصل 997", "Emergency now — call 997"),
          "medium": ("يحتاج تقييمًا طبيًا قريبًا", "Needs medical assessment soon"),
          "low": ("رعاية ذاتية ومراقبة", "Self-care and monitoring")}


def _corrections(text: str) -> list[dict]:
    """Words the typo layer changed, shown as typed -> corrected (normalised forms)."""
    out = []
    for word in str(text or "").split():
        norm = clinical_text.normalize_clinical_text(word).replace("|", " ").split()
        for tok in norm:
            fixed = red_flag_concepts.correct_typos(tok)
            if fixed != tok and not any(c["typed"] == word for c in out):
                out.append({"typed": word.strip("،,.!?؟"), "corrected": fixed})
    return out


def run(scenario_id: str, lang: str = "ar") -> dict:
    """Trace one scenario through the engine. Raises KeyError for an unknown id."""
    sc = _BY_ID[scenario_id]
    ar = lang != "en"
    patient = {"symptoms": [sc["text"]], "notes": "", "age": sc["age"], "severity": sc["severity"],
               "duration": "", "gender": "", "user_id": None}
    t0 = time.perf_counter()
    safety = safety_engine.evaluate(patient, lang=lang)
    t1 = time.perf_counter()
    if safety.get("emergency"):
        result = safety_engine.emergency_result(safety, lang, patient)
        level, layer = "high", "safety"
    else:
        result = analysis_core.run_analysis(dict(patient), lang=lang)
        level = str(result.get("urgency") or "low")
        layer = "safety" if result.get("emergency") else "triage"
    t2 = time.perf_counter()
    labels = red_flag_concepts.CONCEPT_LABELS
    concept = lambda c: {"concept": c, "label": labels[c][0 if ar else 1]}  # noqa: E731
    rules = []
    for item in red_flag_concepts.explain(sc["text"]):
        rules.append({"rule_id": item["rule_id"], "label": item["label_ar" if ar else "label_en"],
                      "evidence": [{"label": e["label_ar" if ar else "label_en"], "quotes": e["quotes"]} for e in item["evidence"]]})
    explained = {r["rule_id"] for r in rules}
    for rid in safety.get("rule_ids") or []:  # phrase rules (no word-level evidence)
        if rid not in explained:
            rules.append({"rule_id": rid, "label": (safety.get("rule_labels") or {}).get(rid, rid), "evidence": []})
    return {
        "id": sc["id"],
        "text": sc["text"],
        "normalized": clinical_text.normalize_clinical_text(sc["text"]).replace(" | ", "، "),
        "corrections": _corrections(sc["text"]),
        "concepts": [concept(c) for c in sorted(red_flag_concepts.matched_concepts(sc["text"]))],
        "denied": [concept(c) for c in sorted(red_flag_concepts.denied_concepts(sc["text"]))],
        "rules": rules,
        "decision": {"level": level, "label": _LEVEL.get(level, _LEVEL["low"])[0 if ar else 1], "layer": layer,
                     "reason": str(result.get("triage_reason") or result.get("why_result") or "")[:400]},
        "timing_ms": {"safety": round((t1 - t0) * 1000, 1), "total": round((t2 - t0) * 1000, 1)},
        "engine": safety_engine.ENGINE_VERSION,
        "ai_used": False,
        "saved": bool(result.get("record_saved")),
    }


_CACHE: dict = {}
# The scenarios and rules are fixed for a given deploy, so the results only change when the
# code changes. A long cache plus one lock means a burst of first visitors waits for a single
# computation instead of each starting its own (V291.1: the cold page hung under load).
_TTL = 6 * 3600
_LOCK = threading.Lock()


def all_results(lang: str = "ar") -> dict:
    hit = _CACHE.get(lang)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]
    with _LOCK:
        hit = _CACHE.get(lang)
        if hit and time.time() - hit[0] < _TTL:
            return hit[1]
        data = {s["id"]: run(s["id"], lang) for s in SCENARIOS}
        _CACHE[lang] = (time.time(), data)
        return data


# --------------------------------------------------------------------------- page
_SCRIPT_AR = [
    ("0:00", "المشكلة", "في السعودية يكتب الناس أعراضهم بالعامية وبأخطاء، وأغلب أدوات فحص الأعراض مبنية للإنجليزية. الخطأ الأخطر: أن تفوت حالة طوارئ."),
    ("0:30", "الحالة 1 — صداع خفيف", "النظام لا يبالغ: لا علامة خطر، فالنتيجة رعاية ذاتية مع متى تراجع."),
    ("1:00", "الحالة 2 — طوارئ بالفصحى", "قواعد أمان ثابتة توقف التحليل وتطلب 997. الذكاء الاصطناعي لا يتخذ هذا القرار."),
    ("1:30", "الحالة 3 — نفس الحالة بالعامية", "«شفيفي» خطأ إملائي، و«نفسي ضيق» عامية. يصحح النظام الكلمة ويصل لنفس القرار، ويعرض الكلمات التي استند إليها."),
    ("2:05", "الحالة 4 — النفي", "«ما عندي ألم صدر»: الكلمة الخطرة موجودة لكنها منفية. النظام يفهم النفي ولا يطلق إنذارًا خاطئًا."),
    ("2:35", "الدليل", "قِسنا ذلك على 300+ حالة مع مجموعة اختبار مستقلة لم نعدّل عليها، وفترات ثقة 95%. التفاصيل في صفحة التقييم وبطاقة النظام."),
]
_SCRIPT_EN = [
    ("0:00", "The problem", "In Saudi Arabia people describe symptoms in dialect, with typos, and most symptom checkers are built for English. The worst error is missing an emergency."),
    ("0:30", "Case 1 — mild headache", "The system does not over-react: no red flag, so self-care plus when to seek care."),
    ("1:00", "Case 2 — formal Arabic emergency", "Fixed safety rules stop the analysis and ask for 997. AI does not make this decision."),
    ("1:30", "Case 3 — same case in dialect", "“شفيفي” is a typo and “نفسي ضيق” is dialect. The engine corrects the word, reaches the same decision, and shows the words it used."),
    ("2:05", "Case 4 — negation", "“No chest pain”: the dangerous word is there but denied. The engine understands the denial and raises no false alarm."),
    ("2:35", "The evidence", "We measured this on 300+ cases, with an untouched held-out test set and 95% confidence intervals. Details are in the evaluation report and the system card."),
]

_CSS = """
.ldemo{max-width:980px;margin:0 auto;padding-block:24px 48px;padding-inline:max(16px,env(safe-area-inset-left,0px)) max(16px,env(safe-area-inset-right,0px));color:var(--ss-color-text,#23384a)}
.ldemo h1{font-size:clamp(24px,4.2vw,34px);line-height:1.25;margin:0 0 6px;color:var(--ss-color-primary-strong,#123B70);text-wrap:balance}
.ldemo .ld-lead{margin:0 0 18px;color:var(--ss-color-muted,#566a7d);max-width:65ch;line-height:1.8}
.ldemo .ld-facts{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 20px;padding:0;list-style:none}
.ldemo .ld-facts li{font-size:13px;font-weight:700;padding:6px 10px;border-radius:999px;background:var(--ss-color-primary-soft,#eaf5fc);color:var(--ss-color-primary-strong,#123B70)}
.ldemo .ld-tabs{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:16px}
.ldemo .ld-tab{min-height:64px;text-align:start;padding:10px 12px;border-radius:14px;border:1.5px solid var(--ss-color-border,#dce8f0);background:#fff;color:var(--ss-color-text,#23384a);font:inherit;font-weight:800;cursor:pointer;display:flex;gap:8px;align-items:center}
.ldemo .ld-tab .ld-n{flex:none;width:28px;height:28px;border-radius:50%;display:grid;place-items:center;background:var(--ss-color-primary-soft,#eaf5fc);color:var(--ss-color-primary-strong,#123B70);font-size:14px}
.ldemo .ld-tab[aria-selected=true]{border-color:var(--ss-color-primary,#1f6fae);box-shadow:0 0 0 3px rgba(31,111,174,.15)}
.ldemo .ld-tab[aria-selected=true] .ld-n{background:var(--ss-color-primary,#1f6fae);color:#fff}
.ldemo .ld-panel{background:#fff;border:1px solid var(--ss-color-border,#dce8f0);border-radius:18px;padding:20px;box-shadow:0 3px 12px rgba(31,86,127,.06)}
.ldemo .ld-point{margin:0 0 14px;font-weight:700;color:var(--ss-color-primary-strong,#123B70);line-height:1.7}
.ldemo .ld-typed{font-size:clamp(18px,2.6vw,22px);line-height:1.9;padding:14px 16px;border-radius:14px;background:#f7fafc;border:1px dashed #c9dbe8;margin:0 0 6px}
.ldemo .ld-typed mark{background:#fde2e2;color:#7f1d1d;border-radius:5px;padding:0 3px;font-weight:800}
.ldemo .ld-gloss{margin:0 0 16px;font-size:13.5px;color:var(--ss-color-muted,#566a7d)}
.ldemo ol.ld-steps{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;counter-reset:st}
.ldemo .ld-step{display:flex;flex-direction:column;gap:8px;align-items:stretch;text-align:start;padding:12px;border-radius:14px;border:1px solid var(--ss-color-border,#dce8f0);background:#fff;color:var(--ss-color-text,#23384a);opacity:1;min-width:0}
.ldemo .ld-step::before{counter-increment:st;content:counter(st);width:30px;height:30px;border-radius:50%;display:grid;place-items:center;background:#123B70;color:#fff;font-weight:800;font-size:14px}
.ldemo .ld-step h3{margin:2px 0 6px;font-size:15px;color:var(--ss-color-primary-strong,#123B70)}
.ldemo .ld-step p{margin:0;font-size:14px;line-height:1.7;min-width:0;overflow-wrap:anywhere}
.ldemo .ld-chips{display:flex;flex-wrap:wrap;gap:6px;margin:0;padding:0;list-style:none}
.ldemo .ld-chip{font-size:13px;padding:4px 9px;border-radius:10px;border:1px solid var(--ss-color-border,#dce8f0);background:#fff}
.ldemo .ld-chip.ld-ok{background:#edf8f2;border-color:#cde7d8;color:#1e5e3f}
.ldemo .ld-chip.ld-deny{background:#f3f4f6;border-color:#d9dde3;color:#3b4652;text-decoration:line-through;text-decoration-thickness:1.5px}
.ldemo .ld-chip.ld-fix{background:#fff8e7;border-color:#efdaa7;color:#5d4513}
.ldemo .ld-chip.ld-rule{display:inline-block;line-height:1.6;background:#fff1f1;border-color:#f2caca;color:#7f1d1d;font-weight:700}
.ldemo .ld-none{color:var(--ss-color-muted,#566a7d)}
.ldemo .ld-decision{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin-top:14px;padding:14px 16px;border-radius:14px;font-weight:900;font-size:18px}
.ldemo .ld-decision.high{background:#b91c1c;color:#fff}.ldemo .ld-decision.medium{background:#fff8e7;color:#5d4513;border:1px solid #efdaa7}.ldemo .ld-decision.low{background:#edf8f2;color:#1e5e3f;border:1px solid #cde7d8}
.ldemo .ld-decision small{font-weight:700;font-size:13px;opacity:.95}
.ldemo .ld-meta{display:flex;flex-wrap:wrap;gap:8px 16px;margin-top:12px;font-size:13px;color:var(--ss-color-muted,#566a7d)}
.ldemo .ld-meta b{color:var(--ss-color-text,#23384a)}
.ldemo .ld-again{margin-inline-start:auto;min-height:44px;padding:8px 14px;border-radius:12px;border:1px solid var(--ss-color-border,#dce8f0);background:#fff;color:var(--ss-color-primary-strong,#123B70);font:inherit;font-weight:800;cursor:pointer}
.ldemo details{margin-top:22px;background:#fff;border:1px solid var(--ss-color-border,#dce8f0);border-radius:16px;padding:6px 16px}
.ldemo summary{cursor:pointer;font-weight:800;padding:10px 0;min-height:44px;display:flex;align-items:center;color:var(--ss-color-primary-strong,#123B70)}
.ldemo .ld-script{list-style:none;margin:0 0 12px;padding:0;display:grid;gap:10px}
.ldemo .ld-script li{display:grid;grid-template-columns:52px minmax(0,1fr);gap:10px;font-size:14px;line-height:1.7}
.ldemo .ld-script time{font-variant-numeric:tabular-nums;font-weight:800;color:var(--ss-color-primary,#1f6fae)}
.ldemo .ld-foot{margin-top:16px;font-size:13px;color:var(--ss-color-muted,#566a7d);line-height:1.7}
@media(max-width:860px){.ldemo ol.ld-steps{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:760px){.ldemo .ld-tabs{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:420px){.ldemo .ld-tabs,.ldemo ol.ld-steps{grid-template-columns:minmax(0,1fr)}.ldemo .ld-panel{padding:14px}.ldemo .ld-again{margin-inline-start:0;width:100%}}
"""

_T = {
    "ar": {"title": "عرض مباشر في 3 دقائق", "lead": "أربع حالات ثابتة تمر على المحرك الحقيقي نفسه الذي يحلل أعراض المستخدمين. لا شيء محفوظ مسبقًا، ولا يُحفظ شيء.",
           "facts": ["المحرك الحقيقي — ليس نتائج جاهزة", "لا ذكاء اصطناعي في قرار الطوارئ", "لا يُحفظ أي شيء", "يعمل دون إنترنت بعد التحميل"],
           "typed": "ما كتبه الشخص", "s1": "تنظيف النص وتصحيح الإملاء", "s2": "المفاهيم الطبية التي فهمها", "s3": "قواعد الأمان", "s4": "القرار",
           "nofix": "لا أخطاء تحتاج تصحيحًا.", "noconcept": "لا مفهوم خطر.", "denied": "منفي — لم يُحتسب:", "norule": "لم تنطبق أي قاعدة طوارئ، فانتقل القرار لطبقة الفرز.",
           "layer_safety": "قررته: قواعد الأمان الثابتة", "layer_triage": "قرّرته: طبقة الفرز (العمر والشدة والمدة)",
           "time": "الزمن", "ms": "ملي ثانية", "engine": "قواعد أمان ثابتة", "ai": "ذكاء اصطناعي: لا", "saved": "محفوظ: لا", "again": "شغّل مرة أخرى مباشرة",
           "live": "حُسبت الآن من الخادم", "offline": "بدون اتصال — المعروض محسوب عند تحميل الصفحة", "script": "نص العرض (3 دقائق)",
           "foot": "حالات تجريبية لأغراض العرض. SymptoSense أداة توعية وفرز أولي وليست تشخيصًا طبيًا. في الطوارئ اتصل 997.",
           "evidence_link": "تقرير التقييم", "rule": "قاعدة", "words": "كلماتك"},
    "en": {"title": "A 3-minute live demo", "lead": "Four fixed cases go through the same real engine that analyses users' symptoms. Nothing is pre-recorded and nothing is saved.",
           "facts": ["The real engine — not canned output", "No AI in the emergency decision", "Nothing is saved", "Works offline once loaded"],
           "typed": "What the person typed", "s1": "Clean the text and fix typos", "s2": "Medical concepts understood", "s3": "Safety rules", "s4": "Decision",
           "nofix": "No typos needed fixing.", "noconcept": "No danger concept.", "denied": "Denied — not counted:", "norule": "No emergency rule applied, so the decision passed to the triage layer.",
           "layer_safety": "Decided by: fixed safety rules", "layer_triage": "Decided by: triage layer (age, severity, duration)",
           "time": "Time", "ms": "ms", "engine": "Fixed safety rules", "ai": "AI: no", "saved": "Saved: no", "again": "Run again live",
           "live": "just computed by the server", "offline": "offline — showing the result computed at page load", "script": "Presenter script (3 minutes)",
           "foot": "Synthetic demo cases. SymptoSense is a health-awareness and triage aid, not a medical diagnosis. In an emergency call 997.",
           "evidence_link": "Evaluation report", "rule": "rule", "words": "your words"},
}


def render_page(lang: str = "ar") -> tuple[str, str, str]:
    """(title, body_html, css) for the page shell."""
    ar = lang != "en"
    t = _T["ar" if ar else "en"]
    esc = html.escape
    data = all_results(lang)
    tabs = "".join(
        '<button type="button" class="ld-tab" role="tab" id="tab-%s" aria-controls="ldemo-panel" aria-selected="%s" data-demo="%s">'
        '<span class="ld-n" aria-hidden="true">%d</span><span>%s</span></button>'
        % (s["id"], "true" if i == 0 else "false", s["id"], i + 1, esc(s["title_ar"] if ar else s["title_en"]))
        for i, s in enumerate(SCENARIOS))
    script = "".join('<li><time>%s</time><span><b>%s.</b> %s</span></li>' % (esc(a), esc(b), esc(c))
                     for a, b, c in (_SCRIPT_AR if ar else _SCRIPT_EN))
    facts = "".join("<li>%s</li>" % esc(f) for f in t["facts"])
    meta = {s["id"]: {"point": s["point_ar"] if ar else s["point_en"], "gloss": "" if ar else s["text_en"]} for s in SCENARIOS}
    payload = json.dumps({"results": data, "meta": meta, "t": t}, ensure_ascii=False).replace("</", "<\\/")
    body = f"""<main class="ldemo" id="main">
<h1>{esc(t['title'])}</h1>
<p class="ld-lead">{esc(t['lead'])}</p>
<ul class="ld-facts">{facts}</ul>
<div class="ld-tabs" role="tablist" aria-label="{esc(t['title'])}">{tabs}</div>
<section class="ld-panel" id="ldemo-panel" role="tabpanel" aria-live="polite" data-ldemo-panel></section>
<details><summary>{esc(t['script'])}</summary><ol class="ld-script">{script}</ol></details>
<p class="ld-foot">{esc(t['foot'])}</p>
</main>
<script type="application/json" id="ldemo-data">{payload}</script>
<script>{_JS}</script>"""
    return t["title"], body, _CSS


_JS = r"""
(function(){
  var D = JSON.parse(document.getElementById('ldemo-data').textContent), T = D.t;
  var panel = document.querySelector('[data-ldemo-panel]'), tabs = [].slice.call(document.querySelectorAll('.ldemo .ld-tab'));
  var lang = document.documentElement.getAttribute('lang') === 'en' ? 'en' : 'ar';
  // Built with DOM nodes and textContent only: user-visible strings are never parsed as HTML.
  function h(tag, attrs, kids){
    var el = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function(k){ el.setAttribute(k, attrs[k]); });
    (kids || []).forEach(function(c){ if (c != null) el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return el;
  }
  var arrow = lang === 'ar' ? ' ← ' : ' → ';
  function highlight(text, rules){
    var spans = [], out = [], pos = 0;
    rules.forEach(function(r){ r.evidence.forEach(function(e){ e.quotes.forEach(function(q){ spans.push([q.start, q.end]); }); }); });
    spans.sort(function(a,b){ return a[0]-b[0]; });
    spans.forEach(function(s){ if (s[0] < pos) return; out.push(text.slice(pos, s[0]), h('mark', {}, [text.slice(s[0], s[1])])); pos = s[1]; });
    out.push(text.slice(pos));
    return out;
  }
  function chips(list, cls){ return h('ul', {'class': 'ld-chips'}, list.map(function(x){ return h('li', {'class': 'ld-chip' + (cls ? ' ld-' + cls : '')}, [x]); })); }
  function none(msg){ return h('p', {'class': 'ld-none'}, [msg]); }
  function step(title, body){ return h('li', {'class': 'ld-step'}, [h('div', {}, [h('h3', {}, [title])].concat(body))]); }
  function render(id, r, status){
    var m = D.meta[id], d = r.decision;
    var fixes = r.corrections.length ? [chips(r.corrections.map(function(c){ return c.typed + arrow + c.corrected; }), 'fix')] : [none(T.nofix)];
    var concepts = r.concepts.length ? [chips(r.concepts.map(function(c){ return c.label; }), 'ok')] : [none(T.noconcept)];
    if (r.denied.length) concepts.push(h('p', {style: 'margin-top:8px'}, [T.denied]), chips(r.denied.map(function(c){ return c.label; }), 'deny'));
    var rules = [];
    r.rules.forEach(function(x){
      rules.push(h('p', {}, [h('span', {'class': 'ld-chip ld-rule'}, [x.label])]));
      var ev = [];
      x.evidence.forEach(function(e){ e.quotes.forEach(function(q){ ev.push('«' + q.text + '»' + arrow + e.label); }); });
      if (ev.length) rules.push(chips(ev, ''));
    });
    if (!rules.length) rules.push(none(T.norule));
    var meta = h('div', {'class': 'ld-meta'}, [
      h('span', {}, [T.time + ': ', h('b', {}, [r.timing_ms.total + ' ' + T.ms])]),
      h('span', {}, [h('b', {}, [T.engine])]),
      h('span', {}, [T.ai]), h('span', {}, [T.saved]),
      status ? h('span', {'data-ldemo-status': ''}, [status]) : null,
      h('button', {type: 'button', 'class': 'ld-again', 'data-again': id}, ['↻ ' + T.again])]);
    panel.replaceChildren(
      h('p', {'class': 'ld-point'}, [m.point]),
      h('div', {'class': 'ld-typed', dir: 'rtl', lang: 'ar', 'aria-label': T.typed}, highlight(r.text, r.rules)),
      h('p', {'class': 'ld-gloss'}, [m.gloss || T.typed]),
      h('ol', {'class': 'ld-steps'}, [step(T.s1, fixes), step(T.s2, concepts), step(T.s3, rules),
                                      step(T.s4, [h('p', {}, [d.layer === 'safety' ? T.layer_safety : T.layer_triage])])]),
      h('div', {'class': 'ld-decision ' + d.level, 'data-level': d.level}, [d.label]),
      meta);
  }
  function select(id, focus){
    tabs.forEach(function(b){ var on = b.getAttribute('data-demo') === id; b.setAttribute('aria-selected', on ? 'true' : 'false'); b.tabIndex = on ? 0 : -1; if (on && focus) b.focus(); });
    panel.setAttribute('aria-labelledby', 'tab-' + id);
    render(id, D.results[id]);
  }
  tabs.forEach(function(b, i){
    b.addEventListener('click', function(){ select(b.getAttribute('data-demo')); });
    b.addEventListener('keydown', function(e){
      var k = e.key, rtl = document.documentElement.getAttribute('dir') === 'rtl', step = 0;
      if (k === 'ArrowRight') step = rtl ? -1 : 1; else if (k === 'ArrowLeft') step = rtl ? 1 : -1;
      else if (k === 'Home') { e.preventDefault(); select(tabs[0].getAttribute('data-demo'), true); return; }
      else if (k === 'End') { e.preventDefault(); select(tabs[tabs.length-1].getAttribute('data-demo'), true); return; }
      if (!step) return; e.preventDefault();
      select(tabs[(i + step + tabs.length) % tabs.length].getAttribute('data-demo'), true);
    });
  });
  panel.addEventListener('click', function(e){
    var b = e.target.closest('[data-again]'); if (!b) return;
    var id = b.getAttribute('data-again'); b.disabled = true;
    fetch('/api/demo/run?id=' + encodeURIComponent(id) + '&lang=' + lang, {headers:{'Accept':'application/json'}})
      .then(function(r){ if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function(r){ D.results[id] = r; render(id, r, T.live); })
      .catch(function(){ render(id, D.results[id], T.offline); });
  });
  select(tabs[0].getAttribute('data-demo'));
})();
"""


def register_routes(app, *, page, lang_getter, request_allowed):
    from flask import abort, jsonify, request

    @app.route("/live-demo")
    def live_demo_page():
        title, body, css = render_page(lang_getter())
        return page(title, body, extra_css=css)

    @app.route("/api/demo/run")
    def api_live_demo_run():
        if not request_allowed("live_demo", 60, 60):
            return jsonify({"ok": False, "error": "rate_limited"}), 429
        sid = str(request.args.get("id") or "")
        if sid not in _BY_ID:
            abort(404)
        lang = "en" if str(request.args.get("lang") or "").startswith("en") else "ar"
        resp = jsonify(run(sid, lang))
        resp.headers["Cache-Control"] = "no-store"
        return resp
