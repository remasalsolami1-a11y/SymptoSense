from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path

import analysis_core
import medical_knowledge
import search_engine_v2
import symptom_combo_intelligence


def _safe_pct(n: int, d: int) -> int:
    return round((n / d) * 100) if d else 0


def _knowledge_metrics():
    medical_knowledge.init_schema()
    symptoms = medical_knowledge.list_entities("symptoms", False, search="") or []
    diseases = medical_knowledge.list_entities("diseases", False, search="") or []
    sources = medical_knowledge.list_entities("sources", False, search="", verification="verified") or []
    categories = Counter()
    aliases_ar = aliases_en = links = red_rules = 0
    try:
        import db
        conn = db._conn(); c = conn.cursor()
        c.execute("SELECT COALESCE(cat.slug,'other'),COUNT(*) FROM mk_symptoms s LEFT JOIN mk_categories cat ON cat.id=s.category_id WHERE s.status='active' GROUP BY COALESCE(cat.slug,'other')")
        categories.update({str(k): int(v or 0) for k,v in c.fetchall()})
        c.execute("SELECT aliases_ar,aliases_en FROM mk_symptoms WHERE status='active'")
        for ar_raw,en_raw in c.fetchall():
            for raw, target in ((ar_raw, "ar"), (en_raw, "en")):
                try: vals = json.loads(raw) if isinstance(raw, str) else (raw or [])
                except Exception: vals = []
                if target == "ar": aliases_ar += len(vals or [])
                else: aliases_en += len(vals or [])
        c.execute("SELECT COUNT(*) FROM mk_disease_symptoms WHERE status='active'"); links = int(c.fetchone()[0] or 0)
        c.execute("SELECT COUNT(*) FROM mk_red_flags WHERE status='active'"); red_rules = int(c.fetchone()[0] or 0)
        conn.close()
    except Exception:
        categories["other"] = len(symptoms)
    return {
        "symptoms": len(symptoms), "diseases": len(diseases), "sources": len(sources),
        "aliases_ar": aliases_ar, "aliases_en": aliases_en, "links": links,
        "red_rules": red_rules, "combos": symptom_combo_intelligence.count(),
        "categories": categories,
    }


def _safety_twin_cases():
    root = Path(__file__).resolve().parent
    rows = []
    # tests/ is excluded from the production Docker image. Ship the synthetic
    # safety matrix as a runtime fixture so Safety Twin and Evidence Passport do
    # not silently report zero cases after deployment.
    for safety_path in (root / "safety_cases.json", root / "runtime_data" / "safety_cases.json", root / "tests" / "data" / "safety_cases.json"):
        try:
            rows = json.loads(safety_path.read_text(encoding="utf-8"))
            if isinstance(rows, list) and rows:
                break
        except Exception:
            rows = []
    results = []
    for case in rows:
        flags = analysis_core.detect_red_flags(case.get("symptoms") or [], case.get("notes") or "", case.get("lang") or "ar")
        actual = bool(flags)
        expected = bool(case.get("expect_red_flag"))
        results.append({**case, "actual": actual, "passed": actual is expected, "flags": flags[:3]})
    return results


_NLP_CASES = [
    ("الدنيا تلف", "ar", "dizziness"),
    ("قلبي يدق بسرعة", "ar", "palpitations"),
    ("ركبتي تطقطق وتوجعني", "ar", "joint-clicking"),
    ("عطشان كثير وادخل الحمام كثير وتعبان", "ar", "increased-thirst"),
    ("كعبي يوجعني اول ما اقوم", "ar", "first-step-heel-pain"),
    ("نفسي يوقف وانا نايم واشخر", "ar", "sleep-breathing-pauses"),
    ("room spinning", "en", "dizziness"),
    ("heart racing and dizzy", "en", "palpitations"),
    ("burning when I pee and peeing a lot", "en", "painful-urination"),
    ("knee clicking and my knee hurts", "en", "joint-clicking"),
]


def _nlp_stress_cases():
    out = []
    for query, lang, expected in _NLP_CASES:
        result = search_engine_v2.search(query, lang, 8)
        mentions = result.get("recognized_symptoms") or []
        slugs = [str(x.get("slug") or "") for x in mentions]
        out.append({
            "query": query, "lang": lang, "expected": expected,
            "passed": expected in slugs,
            "labels": [str(x.get("label") or x.get("slug") or "") for x in mentions[:4]],
            "patterns": [str(x.get("label") or "") for x in (result.get("pattern_insights") or [])[:2]],
        })
    return out



def _coverage_matrix():
    """Return runtime knowledge-graph coverage metrics without making clinical claims."""
    medical_knowledge.init_schema()
    out = {
        "symptoms_linked": 0, "symptoms_total": 0,
        "diseases_with_2_links": 0, "diseases_total": 0,
        "diseases_sourced": 0, "red_flags_sourced": 0, "red_flags_total": 0,
    }
    try:
        import db
        conn = db._conn(); c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM mk_symptoms WHERE status='active'"); out["symptoms_total"] = int(c.fetchone()[0] or 0)
        c.execute("SELECT COUNT(DISTINCT s.id) FROM mk_symptoms s JOIN mk_disease_symptoms ds ON ds.symptom_id=s.id AND ds.status='active' WHERE s.status='active'"); out["symptoms_linked"] = int(c.fetchone()[0] or 0)
        c.execute("SELECT COUNT(*) FROM mk_diseases WHERE status='active'"); out["diseases_total"] = int(c.fetchone()[0] or 0)
        c.execute("SELECT COUNT(*) FROM (SELECT d.id FROM mk_diseases d JOIN mk_disease_symptoms ds ON ds.disease_id=d.id AND ds.status='active' WHERE d.status='active' GROUP BY d.id HAVING COUNT(DISTINCT ds.symptom_id)>=2) q"); out["diseases_with_2_links"] = int(c.fetchone()[0] or 0)
        c.execute("SELECT COUNT(DISTINCT d.id) FROM mk_diseases d JOIN mk_disease_sources x ON x.disease_id=d.id AND x.status='active' WHERE d.status='active'"); out["diseases_sourced"] = int(c.fetchone()[0] or 0)
        c.execute("SELECT COUNT(*) FROM mk_red_flags WHERE status='active'"); out["red_flags_total"] = int(c.fetchone()[0] or 0)
        c.execute("SELECT COUNT(*) FROM mk_red_flags WHERE status='active' AND (source_id IS NOT NULL OR TRIM(COALESCE(reference_url,''))<>'')"); out["red_flags_sourced"] = int(c.fetchone()[0] or 0)
        conn.close()
    except Exception:
        pass
    return out


def _combo_catalog_status():
    medical_knowledge.init_schema()
    symptoms = {str(x.get("slug")) for x in (medical_knowledge.list_entities("symptoms", False, search="") or []) if x.get("slug")}
    diseases = {str(x.get("slug")) for x in (medical_knowledge.list_entities("diseases", False, search="") or []) if x.get("slug")}
    issues = symptom_combo_intelligence.catalog_issues(symptoms, diseases)
    return {"ok": not issues, "issues": issues}


def _combo_showcase(lang: str, limit: int = 10):
    ar = lang != "en"
    diseases = medical_knowledge.list_entities("diseases", False, search="") or []
    disease_names = {str(x.get("slug")): str(x.get("name_ar" if ar else "name_en") or x.get("name_en") or x.get("name_ar") or x.get("slug")) for x in diseases}
    ordered = sorted(symptom_combo_intelligence.PATTERNS, key=lambda p: (len(p.symptoms), p.bonus), reverse=True)
    rows = []
    for pattern in ordered[:max(1, min(int(limit), 16))]:
        rows.append({
            "slug": pattern.slug,
            "label": pattern.label_ar if ar else pattern.label_en,
            "note": pattern.note_ar if ar else pattern.note_en,
            "symptoms": list(pattern.symptoms),
            "targets": [disease_names.get(x, x) for x in pattern.targets],
        })
    return rows


def probe_phrase(text: str, lang: str = "ar") -> dict:
    """Run a non-persistent, bounded demo probe for the Innovation Lab."""
    lang = "en" if lang == "en" else "ar"
    raw = " ".join(str(text or "").replace("\x00", " " ).split()).strip()[:180]
    if not raw:
        return {"ok": False, "error": "empty_text"}
    result = search_engine_v2.search(raw, lang, 8) or {}
    recognized = []
    for row in (result.get("recognized_symptoms") or [])[:8]:
        recognized.append({
            "slug": str(row.get("slug") or "")[:80],
            "label": str(row.get("label") or row.get("slug") or "")[:120],
            "matched_text": str(row.get("matched_text") or "")[:120],
        })
    labels = [x["label"] for x in recognized if x["label"]]
    flags = analysis_core.detect_red_flags(labels, raw, lang) or []
    patterns = []
    for row in (result.get("pattern_insights") or [])[:5]:
        patterns.append({
            "slug": str(row.get("slug") or "")[:80],
            "label": str(row.get("label") or "")[:160],
            "note": str(row.get("note") or "")[:300],
        })
    answer = result.get("answer") if isinstance(result.get("answer"), dict) else {}
    source_names = []
    for src in (answer.get("sources") or [])[:4]:
        if isinstance(src, dict):
            name = str(src.get("source_name") or src.get("organization") or src.get("name") or "").strip()[:120]
            if name and name not in source_names:
                source_names.append(name)
    return {
        "ok": True, "engine_version": str(result.get("engine_version") or "")[:60],
        "normalized": str(result.get("normalized") or "")[:220],
        "coverage": str(result.get("coverage") or "")[:40],
        "recognized_symptoms": recognized, "pattern_insights": patterns,
        "red_flags": [str(x)[:220] for x in flags[:4]],
        "safety_alert": bool(flags),
        "source_names": source_names,
        "source_count": len(source_names),
    }


def evidence_snapshot() -> dict:
    """Public, non-sensitive engineering evidence for judges/reviewers."""
    metrics = _knowledge_metrics()
    coverage = _coverage_matrix()
    safety = _safety_twin_cases()
    nlp = _nlp_stress_cases()
    combo = _combo_catalog_status()
    try:
        version_path = Path(__file__).resolve().parent / "VERSION"
        if version_path.exists():
            version = version_path.read_text(encoding="utf-8").strip()
        else:
            import release_candidate
            version = str(release_candidate.APP_VERSION or "unknown")
    except Exception:
        version = "unknown"
    return {
        "project": "SymptoSense",
        "version": version,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": "engineering_evidence_only",
        "clinical_validation": False,
        "diagnostic_accuracy_claim": False,
        "knowledge": {
            "symptoms": metrics["symptoms"], "conditions": metrics["diseases"],
            "relations": metrics["links"], "verified_sources": metrics["sources"],
            "red_flag_rules": metrics["red_rules"], "combo_patterns": metrics["combos"],
            "search_aliases": metrics["aliases_ar"] + metrics["aliases_en"],
        },
        "coverage": coverage,
        "synthetic_safety": {"passed": sum(1 for x in safety if x["passed"]), "total": len(safety)},
        "nlp_stress": {"passed": sum(1 for x in nlp if x["passed"]), "total": len(nlp)},
        "combo_catalog": {"valid": bool(combo["ok"]), "issues": len(combo["issues"])},
        "limitations": [
            "Synthetic engineering tests are not clinical validation.",
            "The system provides educational, non-diagnostic guidance.",
            "Emergency red-flag logic is evaluated independently from condition ranking.",
        ],
    }

def render_innovation_lab(*, page, lang: str):
    ar = lang == "ar"
    bi = lambda a, e: a if ar else e
    metrics = _knowledge_metrics()
    safety = _safety_twin_cases()
    nlp = _nlp_stress_cases()
    safe_pass = sum(1 for x in safety if x["passed"])
    nlp_pass = sum(1 for x in nlp if x["passed"])
    coverage = _coverage_matrix()
    combo_status = _combo_catalog_status()
    combo_rows = _combo_showcase(lang, 10)

    cats = metrics["categories"]
    top_cats = cats.most_common(6)
    max_cat = max((v for _, v in top_cats), default=1)
    cat_html = ''.join(
        f'<div class="iv-dna-row"><span>{escape(k.replace("-"," ").title())}</span><div><i style="width:{max(8,round(v/max_cat*100))}%"></i></div><b>{v}</b></div>'
        for k, v in top_cats
    ) or '<div class="iv-empty">—</div>'

    safety_html = ''
    for row in safety:
        status = 'pass' if row['passed'] else 'fail'
        title = row.get('id') or 'case'
        syms = ' · '.join(str(x) for x in (row.get('symptoms') or []))
        actual = bi('التقط علامة خطر' if row['actual'] else 'لم يلتقط علامة خطر', 'Red flag detected' if row['actual'] else 'No red flag detected')
        expected = bi('متوقع: تنبيه' if row.get('expect_red_flag') else 'متوقع: بدون تنبيه', 'Expected: alert' if row.get('expect_red_flag') else 'Expected: no alert')
        flag_text = ' · '.join(str(x) for x in (row.get('flags') or [])) or bi('لا توجد علامة خطر', 'No red flag')
        replay_label = bi('عرض مسار الاختبار', 'Replay test path')
        safety_html += (f'<article class="iv-case {status}"><div class="iv-case-top"><span>{"✓" if row["passed"] else "!"}</span><b>{escape(title)}</b><small>{escape(expected)}</small></div>'
                        f'<p>{escape(syms)}</p><strong>{escape(actual)}</strong><details class="iv-replay"><summary>{escape(replay_label)}</summary>'
                        f'<div><span>INPUT</span><p>{escape(syms or "—")}</p><span>DETECTOR</span><p>{escape(flag_text)}</p><span>CHECK</span><p>{escape(expected)} → {escape(actual)}</p></div></details></article>')

    nlp_html = ''
    for row in nlp:
        mapping = ' + '.join(row['labels']) or '—'
        patterns = ' · '.join(row['patterns'])
        nlp_html += f'<article class="iv-nlp {"pass" if row["passed"] else "fail"}"><div><span>{"✓" if row["passed"] else "!"}</span><b>{escape(row["query"])}</b></div><p>→ {escape(mapping)}</p>{f"<small>🧩 {escape(patterns)}</small>" if patterns else ""}</article>'

    coverage_specs = [
        (bi("الأعراض المرتبطة بحالات", "Symptoms linked to conditions"), coverage["symptoms_linked"], coverage["symptoms_total"]),
        (bi("الحالات المرتبطة بعرضين أو أكثر", "Conditions with 2+ symptom links"), coverage["diseases_with_2_links"], coverage["diseases_total"]),
        (bi("الحالات ذات مرجع مباشر", "Conditions with direct references"), coverage["diseases_sourced"], coverage["diseases_total"]),
        (bi("قواعد السلامة ذات مرجع", "Safety rules with references"), coverage["red_flags_sourced"], coverage["red_flags_total"]),
    ]
    coverage_html = ''
    for label, n, d in coverage_specs:
        pct = _safe_pct(n, d)
        cls = 'strong' if pct >= 90 else ('mid' if pct >= 70 else 'gap')
        coverage_html += f'<article class="iv-coverage {cls}"><div><b>{escape(label)}</b><span>{n}/{d}</span></div><div class="iv-coverage-track"><i style="width:{pct}%"></i></div><small>{pct}%</small></article>'

    combo_html = ''
    for row in combo_rows:
        symptom_line = ' + '.join(row['symptoms'])
        target_line = ' · '.join(row['targets'])
        combo_html += (f'<article class="iv-combo-card"><span class="iv-combo-tag">🧩 {escape(row["label"])}</span>'
                       f'<p>{escape(symptom_line)}</p><div class="iv-combo-target"><small>{escape(bi("يدعم ترتيب", "Supports ranking"))}</small><b>{escape(target_line)}</b></div>'
                       f'<em>{escape(row["note"])}</em></article>')

    safety_pct = _safe_pct(safe_pass, len(safety))
    nlp_pct = _safe_pct(nlp_pass, len(nlp))
    source_pct = _safe_pct(coverage['diseases_sourced'], coverage['diseases_total'])
    red_source_pct = _safe_pct(coverage['red_flags_sourced'], coverage['red_flags_total'])
    gates = [
        ("Safety Twin", safety_pct == 100, f"{safe_pass}/{len(safety)}"),
        ("NLP Stress", nlp_pct == 100, f"{nlp_pass}/{len(nlp)}"),
        ("Combo Integrity", bool(combo_status['ok']), bi('سليم', 'Clean') if combo_status['ok'] else str(len(combo_status['issues']))),
        (bi('مرجعية الحالات', 'Condition traceability'), source_pct >= 90, f"{source_pct}%"),
        (bi('مرجعية قواعد السلامة', 'Safety-rule traceability'), red_source_pct >= 90, f"{red_source_pct}%"),
    ]
    gate_html = ''.join(
        f'<article class="iv-gate {"pass" if ok else "review"}"><span>{"✓" if ok else "!"}</span><div><b>{escape(label)}</b><small>{escape(value)}</small></div></article>'
        for label, ok, value in gates
    )

    body = r'''
    <main class="iv-page">
      <section class="iv-hero">
        <div class="iv-grid"></div><div class="iv-glow a"></div><div class="iv-glow b"></div>
        <div class="iv-copy"><span class="iv-kicker">SYMPtoSENSE · INNOVATION LAB</span><h1>__TITLE__<em>__TITLE2__</em></h1><p>__SUB__</p><div class="iv-actions"><a class="primary" href="/demo">__DEMO__</a><a href="/admin/competition-dashboard">__COMP__</a><a href="/api/admin/innovation-lab/evidence" target="_blank" rel="noopener">__PASSPORT__</a><a href="/admin">← Admin</a></div><div class="iv-badges"><span>Safety Twin</span><span>Knowledge DNA</span><span>Arabic NLP</span><span>Combo Intelligence</span></div></div>
        <div class="iv-orbit"><div class="iv-core"><span>✦</span><b>V51</b><small>Innovation Layer</small></div><i class="one">🛡️</i><i class="two">🧬</i><i class="three">🧠</i><i class="four">🧩</i></div>
      </section>

      <section class="iv-score-row">
        <article><span>🧩</span><b>__COMBOS__</b><small>__COMBO_L__</small></article>
        <article><span>🗣️</span><b>__ALIASES__</b><small>__ALIAS_L__</small></article>
        <article><span>🛡️</span><b>__SAFE_SCORE__</b><small>Safety Twin</small></article>
        <article><span>🧠</span><b>__NLP_SCORE__</b><small>NLP Stress Test</small></article>
      </section>

      <section class="iv-panel iv-live"><div class="iv-head"><span>LIVE</span><div><h2>__LIVE_H__</h2><p>__LIVE_P__</p></div><div class="iv-live-status"><i></i>LOCAL ENGINE</div></div>
        <div class="iv-live-shell">
          <div class="iv-console">
            <div class="iv-console-title"><span></span><span></span><span></span><b>SymptoSense · Language Console</b></div>
            <label for="ivProbeText">__LIVE_LABEL__</label>
            <div class="iv-probe-row"><input id="ivProbeText" maxlength="180" autocomplete="off" value="__LIVE_EXAMPLE__"><button type="button" id="ivProbeBtn">__RUN__</button></div>
            <div class="iv-examples"><button type="button" data-iv-example="الدنيا تلف">الدنيا تلف</button><button type="button" data-iv-example="ركبتي تطقطق وتوجعني">ركبتي تطقطق وتوجعني</button><button type="button" data-iv-example="قلبي يدق بسرعة واحس بدوخة">قلبي يدق بسرعة واحس بدوخة</button></div>
            <div class="iv-live-privacy">🔒 __LIVE_PRIVACY__</div>
          </div>
          <div class="iv-pipeline" id="ivProbeOutput" aria-live="polite">
            <article><span>01</span><small>INPUT</small><b id="ivOutInput">—</b></article>
            <article><span>02</span><small>NORMALIZE</small><b id="ivOutNorm">—</b></article>
            <article><span>03</span><small>UNDERSTAND</small><b id="ivOutSymptoms">—</b></article>
            <article><span>04</span><small>COMBO</small><b id="ivOutCombo">—</b></article>
            <article class="safety"><span>05</span><small>SAFETY</small><b id="ivOutSafety">—</b></article>
            <article><span>06</span><small>EVIDENCE TRACE</small><b id="ivOutTrace">—</b></article>
          </div>
        </div>
      </section>

      <section class="iv-panel iv-twin"><div class="iv-head"><span>01</span><div><h2>Safety Twin</h2><p>__TWIN_P__</p></div><div class="iv-ring"><b>__SAFE_PCT__%</b><small>synthetic pass</small></div></div><div class="iv-case-grid">__SAFETY_CASES__</div><div class="iv-note">__TWIN_NOTE__</div></section>

      <section class="iv-panel"><div class="iv-head"><span>02</span><div><h2>Knowledge DNA</h2><p>__DNA_P__</p></div></div><div class="iv-dna-layout"><div class="iv-dna-metrics"><article><b>__SYM__</b><span>Symptoms</span></article><article><b>__DIS__</b><span>Conditions</span></article><article><b>__LINKS__</b><span>Relations</span></article><article><b>__RED__</b><span>Safety rules</span></article><article><b>__SRC__</b><span>Verified sources</span></article><article><b>__COMBOS__</b><span>Combo patterns</span></article></div><div class="iv-dna-bars"><h3>__COVERAGE__</h3>__CAT_HTML__</div></div><div class="iv-coverage-head"><div><h3>__MATRIX_H__</h3><p>__MATRIX_P__</p></div><span>TRACEABILITY · COVERAGE</span></div><div class="iv-coverage-grid">__MATRIX_HTML__</div></section>

      <section class="iv-panel iv-nlp-panel"><div class="iv-head"><span>03</span><div><h2>Arabic NLP Stress Test</h2><p>__NLP_P__</p></div><div class="iv-ring cyan"><b>__NLP_PCT__%</b><small>sample pass</small></div></div><div class="iv-nlp-grid">__NLP_CASES__</div></section>

      <section class="iv-panel iv-combo"><div class="iv-head"><span>04</span><div><h2>__COMBO_H__</h2><p>__COMBO_P__</p></div></div><div class="iv-combo-flow"><article><span>1</span><b>__C1__</b></article><i>→</i><article><span>2</span><b>__C2__</b></article><i>→</i><article><span>3</span><b>__C3__</b></article><i>→</i><article><span>4</span><b>__C4__</b></article></div><div class="iv-note">__COMBO_NOTE__</div><div class="iv-combo-explorer-head"><h3>__EXPLORER_H__</h3><span>__EXPLORER_S__</span></div><div class="iv-combo-grid">__COMBO_HTML__</div></section>

      <section class="iv-panel iv-trust"><div class="iv-head"><span>06</span><div><h2>__TRUST_H__</h2><p>__TRUST_P__</p></div></div><div class="iv-gate-grid">__GATE_HTML__</div><div class="iv-trust-foot"><b>__LIMIT_H__</b><p>__LIMIT_P__</p></div></section>
    </main>
    <script>
    (function(){
      const input=document.getElementById('ivProbeText'),run=document.getElementById('ivProbeBtn');
      const ids={input:'ivOutInput',norm:'ivOutNorm',symptoms:'ivOutSymptoms',combo:'ivOutCombo',safety:'ivOutSafety',trace:'ivOutTrace'};
      function put(key,value){const el=document.getElementById(ids[key]);if(el)el.textContent=value||'—';}
      async function probe(){
        const text=String(input&&input.value||'').trim(); if(!text)return;
        run.disabled=true;run.textContent=__JS_CHECKING__;put('input',text);put('norm','…');put('symptoms','…');put('combo','…');put('safety','…');put('trace','…');
        try{
          const r=await fetch('/api/admin/innovation-lab/probe',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':(document.querySelector('meta[name=admin-csrf]')||{}).content||''},body:JSON.stringify({text:text,lang:document.documentElement.lang==='en'?'en':'ar'})});
          const d=await r.json(); if(!r.ok||!d.ok)throw new Error(d.error||'probe_failed');
          put('norm',d.normalized||'—');
          put('symptoms',(d.recognized_symptoms||[]).map(x=>x.label).join(' + ')||__JS_NONE__);
          put('combo',(d.pattern_insights||[]).map(x=>x.label).join(' · ')||__JS_NO_COMBO__);
          put('safety',d.safety_alert?__JS_ALERT__:__JS_NO_ALERT__);
          const traceParts=[]; if(d.engine_version)traceParts.push(d.engine_version); if(d.coverage)traceParts.push(__JS_COVERAGE__+' '+d.coverage); traceParts.push(String(d.source_count||0)+' '+__JS_SOURCES__); put('trace',traceParts.join(' · '));
          const safety=document.getElementById('ivOutSafety'); if(safety){safety.closest('article').classList.toggle('alert',!!d.safety_alert);}
        }catch(e){put('norm',__JS_ERROR__);put('symptoms','—');put('combo','—');put('safety','—');put('trace','—');}
        finally{run.disabled=false;run.textContent=__JS_RUN__;}
      }
      if(run)run.addEventListener('click',probe);
      if(input)input.addEventListener('keydown',function(e){if(e.key==='Enter'){e.preventDefault();probe();}});
      document.querySelectorAll('[data-iv-example]').forEach(function(btn){btn.addEventListener('click',function(){if(input){input.value=btn.getAttribute('data-iv-example')||'';probe();}});});
    })();
    </script>
    '''
    repl = {
        '__TITLE__': bi('مختبر الابتكار', 'Innovation '), '__TITLE2__': bi('والسلامة', 'Lab'),
        '__SUB__': bi('صفحة تُظهر للحكم كيف نختبر السلامة، نفهم اللغة العربية اليومية، ونقيس تغطية قاعدة المعرفة — باستخدام المحرك الحقيقي وبيانات صناعية فقط.', 'A judge-facing lab showing how safety, everyday Arabic language understanding, and knowledge coverage are tested — using the real engine and synthetic cases only.'),
        '__DEMO__': bi('جرّب المحرك', 'Try the engine'), '__COMP__': bi('لوحة المسابقة', 'Competition dashboard'),
        '__PASSPORT__': bi('Evidence Passport ↗', 'Evidence Passport ↗'),
        '__LIVE_H__': bi('مختبر اللغة الحي', 'Live Language Lab'), '__LIVE_P__': bi('اكتب جملة طبيعية وشاهد — لحظيًا — ماذا فهم محرك البحث، أي نمط مركب اكتشف، وهل فعّلت الجملة طبقة السلامة.', 'Type a natural phrase and watch — live — what the search engine understands, which combo it detects, and whether the safety layer activates.'),
        '__LIVE_LABEL__': bi('جرّب عبارة يومية أو عامية', 'Try an everyday phrase'), '__LIVE_EXAMPLE__': bi('ركبتي تطقطق وتوجعني', 'my knee clicks and hurts'), '__RUN__': bi('شغّل التحليل', 'Run probe'), '__LIVE_PRIVACY__': bi('هذا المختبر لا يحفظ النص ولا يرسله إلى نموذج ذكاء اصطناعي خارجي؛ يستخدم محركات المطابقة والسلامة المحلية فقط.', 'This lab does not save the text or send it to an external AI model; it uses local matching and safety engines only.'),
        '__MATRIX_H__': bi('Coverage Matrix', 'Coverage Matrix'), '__MATRIX_P__': bi('لا نخفي فجوات المعرفة: هذه النسب محسوبة من العلاقات والمراجع الموجودة فعليًا في قاعدة البيانات.', 'Knowledge gaps are not hidden: these percentages are computed from relationships and references actually present in the database.'), '__MATRIX_HTML__': coverage_html,
        '__EXPLORER_H__': bi('Combo Explorer', 'Combo Explorer'), '__EXPLORER_S__': bi('عينات من الأنماط الفعلية داخل المحرك', 'Samples from the real engine catalog'), '__COMBO_HTML__': combo_html,
        '__TRUST_H__': bi('Why trust the process?', 'Why trust the process?'), '__TRUST_P__': bi('بدل رقم دقة تسويقي، نعرض اختبارات السلامة، قابلية التتبع، سلامة الـCombo، وفجوات التغطية كما هي.', 'Instead of a marketing accuracy number, we expose safety tests, traceability, combo integrity, and coverage gaps as they are.'), '__GATE_HTML__': gate_html,
        '__LIMIT_H__': bi('حدود واضحة', 'Explicit limitations'), '__LIMIT_P__': bi('هذه المؤشرات هندسية وتعليمية وليست تحققًا سريريًا أو اعتمادًا طبيًا. أي نتيجة صحية للمستخدم تبقى غير تشخيصية، وعلامات الخطر تتجاوز ترتيب الاحتمالات.', 'These are engineering and educational indicators, not clinical validation or medical certification. User-facing health results remain non-diagnostic, and red flags override condition ranking.'),
        '__JS_CHECKING__': json.dumps(bi('جاري الفحص…','Checking…'), ensure_ascii=False), '__JS_NONE__': json.dumps(bi('لم يتعرف على عرض محدد','No specific symptom recognized'), ensure_ascii=False), '__JS_NO_COMBO__': json.dumps(bi('لا يوجد نمط مركب','No combo pattern'), ensure_ascii=False), '__JS_ALERT__': json.dumps(bi('تنبيه سلامة — ظهرت علامة خطر','Safety alert — red flag detected'), ensure_ascii=False), '__JS_NO_ALERT__': json.dumps(bi('لا توجد علامة خطر في هذه العبارة','No red flag detected in this phrase'), ensure_ascii=False), '__JS_ERROR__': json.dumps(bi('تعذر تشغيل المختبر','Unable to run the lab'), ensure_ascii=False), '__JS_RUN__': json.dumps(bi('شغّل التحليل','Run probe'), ensure_ascii=False), '__JS_COVERAGE__': json.dumps(bi('تغطية','coverage'), ensure_ascii=False), '__JS_SOURCES__': json.dumps(bi('مراجع','sources'), ensure_ascii=False),
        '__COMBOS__': str(metrics['combos']), '__COMBO_L__': bi('نمط أعراض مركب', 'curated symptom combos'),
        '__ALIASES__': str(metrics['aliases_ar'] + metrics['aliases_en']), '__ALIAS_L__': bi('مرادف/صياغة بحث', 'search aliases / phrasings'),
        '__SAFE_SCORE__': f'{safe_pass}/{len(safety)}', '__NLP_SCORE__': f'{nlp_pass}/{len(nlp)}', '__SAFE_PCT__': str(_safe_pct(safe_pass,len(safety))), '__NLP_PCT__': str(_safe_pct(nlp_pass,len(nlp))),
        '__TWIN_P__': bi('سيناريوهات صناعية تمر عبر كاشف علامات الخطر الحقيقي لمراقبة أي Regression في السلامة.', 'Synthetic scenarios run through the real red-flag detector to catch safety regressions.'),
        '__TWIN_NOTE__': bi('هذا Benchmark هندسي على حالات صناعية، وليس دراسة سريرية أو قياسًا للدقة التشخيصية.', 'This is an engineering benchmark on synthetic cases, not a clinical study or diagnostic-accuracy claim.'),
        '__SAFETY_CASES__': safety_html,
        '__DNA_P__': bi('بصمة رقمية توضح حجم قاعدة المعرفة وترابطها بدل عرض رقم واحد مبهم.', 'A digital fingerprint showing the size and connectedness of the knowledge base instead of one vague metric.'),
        '__SYM__': str(metrics['symptoms']), '__DIS__': str(metrics['diseases']), '__LINKS__': str(metrics['links']), '__RED__': str(metrics['red_rules']), '__SRC__': str(metrics['sources']), '__COVERAGE__': bi('أكثر فئات الأعراض تغطية', 'Most-covered symptom categories'), '__CAT_HTML__': cat_html,
        '__NLP_P__': bi('اختبارات لعبارات عامية وأخطاء وصياغات طبيعية لمعرفة هل يصل البحث إلى المفهوم الطبي المقصود.', 'Stress tests with colloquial phrases, typos, and natural language to see whether search reaches the intended medical concept.'), '__NLP_CASES__': nlp_html,
        '__COMBO_H__': bi('Symptom Combination Intelligence', 'Symptom Combination Intelligence'),
        '__COMBO_P__': bi('بدل اعتبار كل عرض منفصلًا، يكتشف المحرك الأنماط متعددة الأعراض ويضيف دعمًا صغيرًا لترتيب النتائج الموثقة.', 'Instead of treating every symptom independently, the engine detects multi-symptom patterns and adds a small bounded signal to source-grounded ranking.'),
        '__C1__': bi('توحيد الأعراض', 'Normalize symptoms'), '__C2__': bi('اكتشاف النمط', 'Detect combo'), '__C3__': bi('دعم الترتيب', 'Bounded ranking support'), '__C4__': bi('فحص السلامة أولًا', 'Safety remains first'),
        '__COMBO_NOTE__': bi('الـCombo لا ينشئ تشخيصًا، لا يخلق تطابقًا من الصفر، ولا يرفع أو يخفض الطوارئ. قواعد السلامة مستقلة ولها الأولوية.', 'A combo never creates a diagnosis, never manufactures a match from zero, and never changes emergency triage. Safety rules are independent and take priority.'),
    }
    for k,v in repl.items(): body = body.replace(k, str(v))
    return page(bi('مختبر الابتكار والسلامة', 'Innovation & Safety Lab'), body, extra_css=INNOVATION_CSS)


INNOVATION_CSS = r'''
.iv-page{width:min(1180px,100%);margin:auto;display:grid;gap:18px}.iv-hero{position:relative;overflow:hidden;min-height:480px;border-radius:32px;padding:clamp(28px,5vw,60px);background:linear-gradient(135deg,#061A2B,#0B3153 55%,#074A50);color:#fff;display:grid;grid-template-columns:minmax(0,1.15fr) minmax(320px,.85fr);gap:32px;align-items:center;box-shadow:0 30px 80px rgba(3,26,47,.24)}.iv-grid{position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.035) 1px,transparent 1px);background-size:32px 32px;mask-image:linear-gradient(#000,transparent)}.iv-glow{position:absolute;border-radius:50%}.iv-glow.a{width:360px;height:360px;right:-120px;top:-120px;background:radial-gradient(circle,rgba(54,178,241,.25),transparent 68%)}.iv-glow.b{width:300px;height:300px;left:30%;bottom:-160px;background:radial-gradient(circle,rgba(55,210,166,.18),transparent 68%)}.iv-copy,.iv-orbit{position:relative;z-index:1}.iv-kicker{display:inline-flex;padding:7px 11px;border:1px solid rgba(255,255,255,.16);border-radius:999px;background:rgba(255,255,255,.06);font-size:10px;font-weight:900;letter-spacing:.15em;color:#9ED9F6}.iv-hero h1{font-size:clamp(42px,6vw,72px);line-height:1;margin:16px 0}.iv-hero h1 em{display:block;font-style:normal;color:#70D1C4}.iv-hero p{max-width:690px;color:#BDD1DF;font-size:14px}.iv-actions{display:flex;gap:9px;flex-wrap:wrap;margin-top:22px}.iv-actions a{min-height:48px;padding:11px 17px;border-radius:14px;border:1px solid rgba(255,255,255,.2);color:#fff;text-decoration:none;font-weight:900;display:inline-flex;align-items:center}.iv-actions .primary{background:#fff;color:#0B3153}.iv-badges{display:flex;gap:7px;flex-wrap:wrap;margin-top:16px}.iv-badges span{padding:6px 9px;border-radius:999px;background:rgba(255,255,255,.06);font-size:9.5px;color:#C2D9E6}.iv-orbit{height:330px;display:grid;place-items:center}.iv-core{width:190px;height:190px;border-radius:50%;display:grid;place-content:center;text-align:center;background:radial-gradient(circle at 35% 30%,#2076A4,#0A365B 62%,#061C30);border:1px solid rgba(255,255,255,.16);box-shadow:0 0 0 22px rgba(64,170,226,.04),0 0 0 46px rgba(64,170,226,.025)}.iv-core span{font-size:42px}.iv-core b{font-size:24px}.iv-core small{color:#A5C8DA}.iv-orbit>i{position:absolute;width:58px;height:58px;border-radius:18px;display:grid;place-items:center;background:rgba(255,255,255,.09);border:1px solid rgba(255,255,255,.14);font-style:normal;font-size:24px;backdrop-filter:blur(10px)}.iv-orbit .one{left:7%;top:18%}.iv-orbit .two{right:5%;top:24%}.iv-orbit .three{left:11%;bottom:13%}.iv-orbit .four{right:9%;bottom:12%}.iv-score-row{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.iv-score-row article{background:#fff;border:1px solid #DCE8F0;border-radius:20px;padding:18px;display:grid;grid-template-columns:38px 1fr;gap:2px 10px;align-items:center;box-shadow:0 7px 20px rgba(22,59,92,.045)}.iv-score-row span{grid-row:1/3;width:38px;height:38px;border-radius:12px;background:#EEF8FD;display:grid;place-items:center}.iv-score-row b{font-size:24px;color:#123B70}.iv-score-row small{color:#718899;font-size:9.5px}.iv-panel{background:#fff;border:1px solid #DCE8F0;border-radius:26px;padding:clamp(20px,4vw,34px);box-shadow:0 8px 24px rgba(22,59,92,.04)}.iv-head{display:grid;grid-template-columns:42px minmax(0,1fr) auto;gap:12px;align-items:center;margin-bottom:20px}.iv-head>span{width:40px;height:40px;border-radius:13px;background:#EAF5FC;color:#1f6fae;display:grid;place-items:center;font-weight:900}.iv-head h2{margin:0;color:#163B5C;font-size:clamp(23px,3vw,32px)}.iv-head p{margin:4px 0 0;color:#718899;font-size:12px}.iv-ring{width:78px;height:78px;border-radius:50%;border:8px solid #D7EEDF;display:grid;place-content:center;text-align:center;background:#F8FCFA}.iv-ring b{font-size:18px;color:#1E6846}.iv-ring small{font-size:7.5px;color:#668174}.iv-ring.cyan{border-color:#D4EAF5}.iv-ring.cyan b{color:#1F6E9F}.iv-case-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.iv-case{border:1px solid #E1EBF1;border-radius:16px;padding:13px;background:#FBFDFE}.iv-case.pass{border-color:#D4E9DD;background:#F9FCFA}.iv-case.fail{border-color:#F0D0D0;background:#FFF8F8}.iv-case-top{display:grid;grid-template-columns:28px minmax(0,1fr) auto;gap:7px;align-items:center}.iv-case-top>span{width:27px;height:27px;border-radius:9px;background:#EAF7F0;color:#21835D;display:grid;place-items:center;font-weight:900}.iv-case.fail .iv-case-top>span{background:#FFF0F0;color:#B33E3E}.iv-case-top b{color:#29485F;font-size:11px}.iv-case-top small{font-size:8.5px;color:#718899}.iv-case p{margin:8px 0 4px;color:#566a7d;font-size:10.5px}.iv-case strong{font-size:10px;color:#315C48}.iv-note{margin-top:12px;padding:11px 13px;border-radius:13px;background:#F6F9FB;color:#566a7d;font-size:10.5px;line-height:1.7}.iv-dna-layout{display:grid;grid-template-columns:minmax(300px,.9fr) minmax(0,1.1fr);gap:18px}.iv-dna-metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.iv-dna-metrics article{padding:16px;border-radius:16px;background:linear-gradient(135deg,#F8FCFF,#fff);border:1px solid #DCE8F0}.iv-dna-metrics b{display:block;font-size:27px;color:#123B70}.iv-dna-metrics span{font-size:9.5px;color:#718899}.iv-dna-bars{padding:17px;border:1px solid #E1EBF1;border-radius:18px;background:#FBFDFE}.iv-dna-bars h3{margin:0 0 12px;color:#29485F;font-size:13px}.iv-dna-row{display:grid;grid-template-columns:110px minmax(0,1fr) 30px;gap:8px;align-items:center;margin:8px 0}.iv-dna-row>span{font-size:9.5px;color:#566a7d;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.iv-dna-row>div{height:7px;background:#E7EFF4;border-radius:999px;overflow:hidden}.iv-dna-row i{display:block;height:100%;background:linear-gradient(90deg,#1f6fae,#57B8D7);border-radius:999px}.iv-dna-row b{font-size:9px;color:#526B7E}.iv-nlp-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.iv-nlp{padding:13px;border:1px solid #E1EBF1;border-radius:16px;background:#FBFDFE}.iv-nlp>div{display:grid;grid-template-columns:26px 1fr;align-items:center;gap:7px}.iv-nlp>div span{width:25px;height:25px;border-radius:8px;background:#EAF7F0;color:#21835D;display:grid;place-items:center;font-weight:900}.iv-nlp.fail>div span{background:#FFF0F0;color:#B33E3E}.iv-nlp b{color:#29485F;font-size:11px}.iv-nlp p{margin:7px 0 0;color:#1f6fae;font-size:10.5px;font-weight:800}.iv-nlp small{display:block;margin-top:5px;color:#566a7d;font-size:9.5px}.iv-combo-flow{display:grid;grid-template-columns:1fr auto 1fr auto 1fr auto 1fr;gap:8px;align-items:center}.iv-combo-flow article{padding:15px;border:1px solid #DCE8F0;border-radius:16px;background:#F8FCFF;text-align:center}.iv-combo-flow article span{width:29px;height:29px;border-radius:10px;background:#1f6fae;color:#fff;display:grid;place-items:center;margin:0 auto 8px;font-weight:900}.iv-combo-flow article b{font-size:10.5px;color:#526B7E}.iv-combo-flow>i{font-style:normal;color:#9BBFD4}@media(max-width:900px){.iv-hero{grid-template-columns:1fr}.iv-orbit{height:280px}.iv-score-row{grid-template-columns:repeat(2,minmax(0,1fr))}.iv-dna-layout{grid-template-columns:1fr}.iv-case-grid,.iv-nlp-grid{grid-template-columns:1fr}.iv-combo-flow{grid-template-columns:1fr}.iv-combo-flow>i{transform:rotate(90deg);text-align:center}.iv-head{grid-template-columns:40px 1fr}.iv-ring{grid-column:1/-1;justify-self:start}}@media(max-width:560px){.iv-hero{border-radius:23px;padding:28px 16px}.iv-hero h1{font-size:42px}.iv-score-row{grid-template-columns:1fr 1fr}.iv-score-row article{grid-template-columns:32px 1fr;padding:14px}.iv-score-row span{width:32px;height:32px}.iv-score-row b{font-size:20px}.iv-panel{padding:18px 13px;border-radius:20px}.iv-dna-metrics{grid-template-columns:1fr 1fr}.iv-dna-row{grid-template-columns:90px minmax(0,1fr) 26px}}@media(prefers-reduced-motion:reduce){.iv-page *{animation:none!important;transition:none!important}}

.iv-live{background:linear-gradient(145deg,#061A2B,#092A45);border-color:#123B58;color:#fff;overflow:hidden}.iv-live .iv-head h2{color:#fff}.iv-live .iv-head p{color:#9DB9CA}.iv-live .iv-head>span{background:rgba(112,209,196,.12);color:#70D1C4}.iv-live-status{display:inline-flex;align-items:center;gap:7px;color:#9ED9F6;font-size:9px;font-weight:900;letter-spacing:.12em}.iv-live-status i{width:8px;height:8px;border-radius:50%;background:#5DD6A8;box-shadow:0 0 0 5px rgba(93,214,168,.09)}.iv-live-shell{display:grid;grid-template-columns:minmax(300px,.82fr) minmax(0,1.18fr);gap:14px}.iv-console{background:#03111D;border:1px solid #17384F;border-radius:20px;padding:16px;box-shadow:inset 0 1px rgba(255,255,255,.03)}.iv-console-title{display:flex;align-items:center;gap:6px;color:#7695A8;font-size:9px;margin-bottom:18px}.iv-console-title>span{width:8px;height:8px;border-radius:50%;background:#36556A}.iv-console-title>span:first-child{background:#E06C75}.iv-console-title>span:nth-child(2){background:#E6C07B}.iv-console-title>span:nth-child(3){background:#62C494}.iv-console-title b{margin-inline-start:6px}.iv-console label{display:block;color:#9DB9CA;font-size:10px;font-weight:800;margin-bottom:7px}.iv-probe-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:7px}.iv-probe-row input{min-height:48px;border-radius:13px;border:1px solid #21465F;background:#071D2D;color:#fff;padding:10px 12px;font-family:inherit;outline:none}.iv-probe-row input:focus{border-color:#4E9ECB;box-shadow:0 0 0 3px rgba(78,158,203,.12)}.iv-probe-row button{border:0;border-radius:13px;background:#70D1C4;color:#063238;font-family:inherit;font-weight:900;padding:9px 14px;cursor:pointer}.iv-probe-row button:disabled{opacity:.55}.iv-examples{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}.iv-examples button{border:1px solid #21465F;border-radius:999px;background:#09263A;color:#AFC9D7;font-family:inherit;font-size:9px;padding:6px 9px;cursor:pointer}.iv-live-privacy{margin-top:13px;color:#6F91A6;font-size:9.5px;line-height:1.7}.iv-pipeline{display:grid;gap:7px}.iv-pipeline article{display:grid;grid-template-columns:34px 92px minmax(0,1fr);gap:10px;align-items:center;padding:11px 12px;border-radius:14px;border:1px solid #17384F;background:rgba(5,27,43,.82)}.iv-pipeline article>span{width:30px;height:30px;border-radius:9px;background:#0C3A58;color:#70D1C4;display:grid;place-items:center;font-size:9px;font-weight:900}.iv-pipeline small{color:#64869A;font-size:8px;font-weight:900;letter-spacing:.1em}.iv-pipeline b{color:#D9EAF3;font-size:10.5px;line-height:1.55;overflow-wrap:anywhere}.iv-pipeline article.safety{border-color:#1D4C55}.iv-pipeline article.safety.alert{border-color:#7D4545;background:rgba(86,31,31,.28)}.iv-pipeline article.safety.alert b{color:#FFB3B3}.iv-replay{margin-top:9px;border-top:1px solid #E7EFF3;padding-top:8px}.iv-replay summary{cursor:pointer;color:#1f6fae;font-size:9px;font-weight:900}.iv-replay div{padding-top:8px}.iv-replay div>span{display:block;color:#8AA0AF;font-size:7.5px;font-weight:900;letter-spacing:.12em}.iv-replay div>p{margin:2px 0 7px;color:#526B7E;font-size:9px}.iv-coverage-head{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin:20px 0 10px;padding-top:18px;border-top:1px solid #EDF2F5}.iv-coverage-head h3{margin:0;color:#29485F;font-size:15px}.iv-coverage-head p{margin:3px 0 0;color:#718899;font-size:10px}.iv-coverage-head>span{font-size:8px;font-weight:900;letter-spacing:.12em;color:#85A0B3}.iv-coverage-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.iv-coverage{padding:13px;border:1px solid #E1EBF1;border-radius:15px;background:#FBFDFE}.iv-coverage>div:first-child{display:flex;justify-content:space-between;gap:8px}.iv-coverage b{color:#40566F;font-size:10px}.iv-coverage span,.iv-coverage small{color:#718899;font-size:9px}.iv-coverage-track{height:7px!important;background:#E7EFF4!important;border-radius:999px;overflow:hidden;margin:8px 0 4px}.iv-coverage-track i{display:block;height:100%;border-radius:inherit;background:#50B99A}.iv-coverage.mid .iv-coverage-track i{background:#D7A642}.iv-coverage.gap .iv-coverage-track i{background:#D56B6B}.iv-combo-explorer-head{display:flex;justify-content:space-between;align-items:end;gap:10px;margin:20px 0 10px}.iv-combo-explorer-head h3{margin:0;color:#29485F;font-size:15px}.iv-combo-explorer-head span{color:#8AA0AF;font-size:9px}.iv-combo-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.iv-combo-card{padding:14px;border:1px solid #E1EBF1;border-radius:16px;background:linear-gradient(145deg,#FBFDFE,#fff)}.iv-combo-tag{display:inline-flex;padding:5px 8px;border-radius:999px;background:#EAF5FC;color:#225C86;font-size:9px;font-weight:900}.iv-combo-card>p{margin:8px 0;color:#566a7d;font-size:9.5px}.iv-combo-target{padding:9px;border-radius:11px;background:#F7FAFC}.iv-combo-target small{display:block;color:#8AA0AF;font-size:8px}.iv-combo-target b{display:block;margin-top:2px;color:#29485F;font-size:10px}.iv-combo-card em{display:block;margin-top:7px;color:#718899;font-size:8.5px;font-style:normal;line-height:1.6}.iv-trust{background:linear-gradient(145deg,#F9FCFF,#F8FCFA)}.iv-gate-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px}.iv-gate{display:flex;align-items:center;gap:9px;padding:13px;border:1px solid #DCE8F0;border-radius:15px;background:#fff}.iv-gate>span{width:30px;height:30px;border-radius:10px;display:grid;place-items:center;background:#EAF7F0;color:#21835D;font-weight:900;flex:none}.iv-gate.review>span{background:#FFF6E6;color:#9A6810}.iv-gate b{display:block;color:#40566F;font-size:9.5px}.iv-gate small{color:#718899;font-size:9px}.iv-trust-foot{margin-top:12px;padding:13px 15px;border-radius:15px;background:#102B41;color:#C7DCE8}.iv-trust-foot b{color:#fff;font-size:11px}.iv-trust-foot p{margin:4px 0 0;font-size:9.5px;line-height:1.7;color:#A9C2D1}@media(max-width:900px){.iv-live-shell{grid-template-columns:1fr}.iv-gate-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.iv-combo-grid,.iv-coverage-grid{grid-template-columns:1fr}}@media(max-width:560px){.iv-probe-row{grid-template-columns:1fr}.iv-pipeline article{grid-template-columns:30px 74px minmax(0,1fr);padding:9px}.iv-gate-grid{grid-template-columns:1fr 1fr}.iv-coverage-head,.iv-combo-explorer-head{align-items:flex-start;flex-direction:column}}
'''
