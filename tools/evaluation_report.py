"""Render evaluation/results/*.json into a self-contained, bilingual-friendly HTML report (V284).

    python tools/evaluate_engine.py --out evaluation/results
    python tools/evaluate_engine.py --severity-sweep --out evaluation/results
    python tools/evaluation_report.py            # -> evaluation/results/report.html

Inputs: results.json (current engine), baseline_v283.json (previous engine, optional),
severity_sweep.json (optional). Charts are inline SVG drawn on one 0–100 % scale with
Wilson 95 % intervals; colours come from CSS tokens so the page reads in light and dark.
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evaluation" / "results"

CONDITIONS = [
    ("en_test", "إنجليزي — مجموعة الاختبار", "120 حالة: مستقلة حتى V286، وتطوير من V287"),
    ("en_dev", "إنجليزي — مجموعة التطوير", "60 حالة استُخدمت في التطوير"),
    ("ar_msa", "عربي فصيح", "40 حالة"),
    ("ar_dialect", "لهجة سعودية", "40 حالة"),
    ("ar_dialect_typos", "لهجة + أخطاء إملائية", "40 حالة"),
]
ARCH = [("keyword", "بحث كلمات فقط (أساس)"), ("rules", "قواعد الخطر فقط"), ("rules_triage", "+ قواعد الفرز"), ("hybrid", "النظام الكامل")]
LEVEL_AR = {"high": "طارئ", "medium": "مراجعة", "low": "منخفض"}

esc = html.escape


def pct(m) -> str:
    v = m.get("value") if m else None
    return "—" if v is None else f"{100 * v:.1f}%"


def ci(m) -> str:
    if not m or m.get("value") is None:
        return ""
    lo, hi = m["ci95"]
    return f"{100 * lo:.0f}–{100 * hi:.0f}%"


# ------------------------------------------------------------------ SVG
def bar_chart(rows, metric, before, after) -> str:
    """Horizontal paired bars (before / after) with CI whiskers; one 0–100 % scale."""
    label_w, plot_w, row_h, top = 210, 440, 46, 30
    width, height = label_w + plot_w + 52, top + row_h * len(rows) + 26  # right margin fits a "100%" label
    x = lambda v: label_w + plot_w * v  # noqa: E731
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" class="chart" direction="ltr">']
    for t in (0, 0.25, 0.5, 0.75, 1.0):
        parts.append(f'<line x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{top - 8}" y2="{height - 22}" class="grid"/>')
        parts.append(f'<text x="{x(t):.1f}" y="{height - 6}" class="tick" text-anchor="middle">{int(t * 100)}%</text>')
    for i, (key, name, _sub) in enumerate(rows):
        y0 = top + i * row_h
        parts.append(f'<text x="{label_w - 12}" y="{y0 + 20}" class="rowlabel" text-anchor="end">{esc(name)}</text>')
        for j, (data, cls) in enumerate(((before, "before"), (after, "after"))):
            m = (data or {}).get("conditions", {}).get(key, {}).get("hybrid", {}).get(metric)
            if not m or m.get("value") is None:
                continue
            y = y0 + 4 + j * 16
            v, (lo, hi) = m["value"], m["ci95"]
            parts.append(f'<rect x="{label_w}" y="{y}" width="{max(plot_w * v, 1.5):.1f}" height="12" rx="2" class="bar {cls}"/>')
            parts.append(f'<line x1="{x(lo):.1f}" x2="{x(hi):.1f}" y1="{y + 6}" y2="{y + 6}" class="whisker"/>')
            for e in (lo, hi):
                parts.append(f'<line x1="{x(e):.1f}" x2="{x(e):.1f}" y1="{y + 2}" y2="{y + 10}" class="whisker"/>')
            parts.append(f'<text x="{x(hi) + 6:.1f}" y="{y + 10}" class="val {cls}" text-anchor="start">{100 * v:.0f}%</text>')
    parts.append("</svg>")
    return "".join(parts)


# ------------------------------------------------------------------ sections
def headline(after, before) -> str:
    a = after["conditions"]["en_test"]["hybrid"]
    b = (before or {}).get("conditions", {}).get("en_test", {}).get("hybrid")
    tiles = [
        ("الحالات الطارئة المكتشفة", "high_sensitivity", "كلما ارتفع أفضل"),
        ("طارئ عُرض كـ«منخفض»", "critical_under_triage", "أخطر خطأ — كلما انخفض أفضل"),
        ("المبالغة في الخطورة", "over_triage", "إنذارات زائدة — كلما انخفض أفضل"),
    ]
    out = []
    for title, key, hint in tiles:
        prev = f'<span class="from">{pct(b[key])} →</span>' if b else ""
        out.append(f'<div class="tile"><div class="tile-label">{esc(title)}</div>'
                   f'<div class="tile-num">{prev}<b>{pct(a[key])}</b></div>'
                   f'<div class="tile-ci">فترة ثقة 95%: {ci(a[key])}</div><div class="tile-hint">{esc(hint)}</div></div>')
    return '<div class="tiles">' + "".join(out) + "</div>"


def ablation_table(after) -> str:
    head = "".join(f"<th>{esc(n)}</th>" for _k, n in ARCH)
    body = []
    for key, name, sub in CONDITIONS:
        cells = []
        for arch, _n in ARCH:
            if arch not in after["conditions"][key]:
                cells.append('<td class="num">—</td>')
                continue
            m = after["conditions"][key][arch]["high_sensitivity"]
            cells.append(f'<td class="num">{pct(m)}<small>{ci(m)}</small></td>')
        body.append(f'<tr><th scope="row">{esc(name)}<small>{esc(sub)}</small></th>{"".join(cells)}</tr>')
    return (f'<div class="tablewrap"><table><thead><tr><th>نسبة اكتشاف الحالات الطارئة</th>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def confusion(after) -> str:
    cm = after["conditions"]["en_test"]["hybrid"]["confusion"]
    levels = ("high", "medium", "low")
    head = "".join(f"<th>{LEVEL_AR[p]}</th>" for p in levels)
    rows = []
    for e in levels:
        cells = []
        for p in levels:
            n = cm[e][p]
            cls = "diag" if e == p else ("danger" if (e == "high" and p == "low") else "")
            cells.append(f'<td class="num {cls}">{n}</td>')
        rows.append(f'<tr><th scope="row">{LEVEL_AR[e]}</th>{"".join(cells)}</tr>')
    return (f'<div class="tablewrap"><table class="cm"><thead><tr><th>المرجع ↓ / النظام →</th>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def severity_table(sweep) -> str:
    if not sweep:
        return "<p class='muted'>شغّلي <code>--severity-sweep</code> لإضافة هذا القسم.</p>"
    rows = []
    for s in sorted(sweep, key=int):
        m = sweep[s]["en_test"]["hybrid"]
        rows.append(f'<tr><th scope="row">{s} / 5</th><td class="num">{pct(m["high_sensitivity"])}</td>'
                    f'<td class="num">{pct(m["critical_under_triage"])}</td><td class="num">{pct(m["over_triage"])}</td></tr>')
    return ('<div class="tablewrap"><table><thead><tr><th>الشدة التي يُدخلها المستخدم</th><th>طارئ مكتشف</th>'
            '<th>طارئ عُرض كـ«منخفض»</th><th>مبالغة</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>")


def e2e_section(e2e) -> str:
    """V289: the same cases through the real website API, and the AI-reply guard."""
    if not e2e:
        return ""
    a, g, lat = e2e["api_engine_agreement"], e2e["ai_guard"], e2e["latency_ms"]
    return f"""<section>
  <h2>المسار الحقيقي في الموقع، وتطابق كلام الذكاء الاصطناعي مع القرار</h2>
  <p class="muted">أُرسلت كل الحالات إلى <code>POST /api/analyze</code> كما يرسلها المتصفح (بعد الموافقة)، وقورنت النتيجة بنتيجة المحرك نفسه. ثم جُرّبت ردود «مطمئنة» مكتوبة عمدًا مثل «لا داعي لزيارة الطبيب» على كل حالة تقول القواعد إنها تحتاج طبيبًا، للتأكد أن الحارس يحذفها ويضيف النصيحة الصحيحة.</p>
  <div class="tiles">
    <div class="tile"><div class="tile-label">نفس القرار عبر الموقع والمحرك</div><div class="tile-num"><b>{a['k']}/{a['n']}</b></div><div class="tile-hint">أي فرق يعني أن طبقة الموقع غيّرت القرار</div></div>
    <div class="tile"><div class="tile-label">ردود مطمئنة خاطئة صحّحها الحارس</div><div class="tile-num"><b>{g['k']}/{g['n']}</b></div><div class="tile-hint">answer_guard.py</div></div>
    <div class="tile"><div class="tile-label">زمن الاستجابة (الوسيط / 95%)</div><div class="tile-num"><b>{lat['median']:.0f} / {lat['p95']:.0f}</b></div><div class="tile-hint">ملي ثانية، بدون ذكاء اصطناعي</div></div>
  </div>
</section>"""


def blood_section(blood, before=None) -> str:
    """V288: the blood-report pipeline on the synthetic report benchmark."""
    if not blood:
        return ""
    rows = []
    for key, name in (("critical_sensitivity", "تقرير فيه قيمة حرجة ظهر «عاجل/طوارئ»"),
                      ("false_critical_alarms", "تقرير بلا قيمة حرجة ظهر «عاجل/طوارئ» (إنذار خاطئ)"),
                      ("level_accuracy", "مستوى التقرير صحيح"), ("status_accuracy", "تصنيف كل تحليل صحيح (منخفض/طبيعي/مرتفع)"),
                      ("extraction_recall", "قراءة اسم التحليل وقيمته من التقرير")):
        b = (before or {}).get(key)
        rows.append(f'<tr><th scope="row">{esc(name)}</th><td class="num">{pct(b) if b else "—"}<small>{ci(b) if b else ""}</small></td>'
                    f'<td class="num"><b>{pct(blood[key])}</b><small>{ci(blood[key])}</small></td></tr>')
    return f"""<section>
  <h2>تحليل الدم: القيم الحرجة، INR واللاكتات، والتحاليل غير المعروفة</h2>
  <p class="muted">{blood["meta"]["reports"]} تقريرًا اصطناعيًا بصيغ تصل للتطبيق فعلًا: سطور إنجليزية، وحدات SI، حدود من جهة واحدة مثل «&lt;5» و«&gt;60»، صفوف OCR، أسماء عربية وأرقام عربية، تقرير بلا نطاق، طفل، ومنذ V290: INR واللاكتات، وأرقام داخل اسم التحليل مثل «25-OH»، وتحاليل لا يعرفها التطبيق. كتبتها صاحبة المشروع مع التعديلات (مجموعة تطوير)، وحدود القيم الحرجة تنتظر موافقة الطبيب.</p>
  <div class="tablewrap"><table><thead><tr><th></th><th>V289</th><th>V290</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>
</section>"""


def headline_sections(after, before, frozen) -> str:
    """Held-out headline. Once en_test has been inspected (V287), the honest held-out
    number is the frozen V285 one; the current numbers on the same cases are shown
    separately and labelled as development results."""
    status = after.get("meta", {}).get("en_test_status") or {}
    if not status.get("inspected_from") or not frozen:
        return f"""<section>
  <h2>النتيجة على حالات لم يرها النظام أثناء التطوير</h2>
  <p class="muted">120 حالة إنجليزية من مجموعة الاختبار المخفية، بالنظام الكامل، قبل التحسين وبعده.</p>
  {headline(after, before)}
</section>"""
    return f"""<section>
  <h2>آخر قياس على حالات لم يرها النظام (V286 — مختوم)</h2>
  <p class="muted">120 حالة إنجليزية لم تُفحص حالةً حالة حتى V286. هذا هو الرقم المستقل الذي يُستشهد به. المقارنة مع V283.</p>
  {headline(frozen, before)}
</section>

<section>
  <h2>نفس الحالات بعد التحسينات (V286–{esc(status["inspected_from"])}) — نتيجة تطوير</h2>
  <p class="muted"><b>تنبيه منهجي:</b> في {esc(status["inspected_from"])} فُحصت أخطاء هذه المجموعة لتصنيف أنواع الأخطاء، ثم بُنيت قواعد جديدة على حالات تطوير جديدة مكتوبة لكل نوع. لذلك هذه الأرقام <b>تطوير</b> ولا تُعرض كاختبار مستقل؛ التقدير المستقل القادم هو المجموعة الخارجية المختومة. المقارنة مع V286.</p>
  {headline(after, frozen)}
</section>"""


TAXONOMY_AR = {
    "respiratory_distress": "ضيق تنفس شديد (ازرقاق، لا يكمل الكلام، سيلان لعاب)", "reduced_consciousness": "نقص الوعي أو الاستجابة",
    "sepsis": "حمى مع تشوش أو طفح بنفسجي", "cardiac_syncope": "إغماء مع ألم صدر أو خفقان أو مجهود",
    "bleeding": "نزيف غزير مع دوخة أو ضعف", "dehydration": "جفاف شديد مع تشوش أو نعاس",
    "anaphylaxis_trigger": "لسعة حشرة مع ضيق تنفس", "glaucoma": "ألم عين شديد مع تشوش الرؤية أو قيء",
    "cauda_equina": "ألم ظهر مع فقدان التحكم بالبول", "limb_ischemia": "طرف بارد شاحب مفاجئ",
    "hypoglycemia": "مريض سكري مع رجفة وعرق وتشوش", "stroke_wording": "صياغات أخرى للسكتة",
    "thunderclap": "صداع مفاجئ هو الأسوأ", "asthma_wording": "صياغات أخرى للربو",
}


def taxonomy_section(after) -> str:
    """V287: missed emergencies grouped by error type, fixed on new development cases."""
    tx = after.get("taxonomy_by_category")
    if not tx:
        return ""
    rows = []
    for cat, r in tx.items():
        rows.append(f'<tr><th scope="row">{esc(TAXONOMY_AR.get(cat, cat))}</th>'
                    f'<td class="num">{r["urgent_caught_keyword"]}/{r["urgent"]}</td>'
                    f'<td class="num">{r["urgent_caught_before"]}/{r["urgent"]}</td>'
                    f'<td class="num"><b>{r["urgent_caught"]}/{r["urgent"]}</b></td>'
                    f'<td class="num">{r["mild_false_alarm"]}/{r["mild"]}</td></tr>')
    tot = {k: sum(r[k] for r in tx.values()) for k in next(iter(tx.values()))}
    rows.append(f'<tr><th scope="row"><b>المجموع</b></th><td class="num">{tot["urgent_caught_keyword"]}/{tot["urgent"]}</td>'
                f'<td class="num">{tot["urgent_caught_before"]}/{tot["urgent"]}</td><td class="num"><b>{tot["urgent_caught"]}/{tot["urgent"]}</b></td>'
                f'<td class="num">{tot["mild_false_alarm"]}/{tot["mild"]}</td></tr>')
    return f"""<section>
  <h2>الطوارئ التي كانت تفوت النظام — حسب نوع الخطأ (V287)</h2>
  <p class="muted">صُنّفت الحالات الطارئة التي فاتت النظام إلى أنواع، ثم كُتبت لكل نوع حالات <b>جديدة بصياغات مختلفة</b> (عربي وإنجليزي) مع حالات بسيطة تشبهها يجب ألا تُنذر، وبُنيت القواعد عليها. مجموعة تطوير: الأرقام تبيّن أن القواعد تعمل ولا تُنذر خطأً، لا أداءها على كلام جديد.</p>
  <div class="tablewrap"><table><thead><tr><th>نوع الخطأ</th><th>طارئ مكتشف — بحث الكلمات</th><th>طارئ مكتشف — قبل V287</th><th>طارئ مكتشف — V287</th><th>حالة بسيطة أُنذرت خطأً — V287</th></tr></thead>
  <tbody>{"".join(rows)}</tbody></table></div>
</section>"""


def text_context_section(after) -> str:
    """V286: what reading duration / severity / worsening from the sentence changes."""
    off = after.get("ablation_text_context_off")
    if not off:
        return ""
    names = dict((k, n) for k, n, _s in CONDITIONS)
    names.update({"ar_code_switch": "عربي + إنجليزي", "ar_arabizi": "عربيزي", "pediatric": "أطفال بأعمارهم", "medium_combo": "تركيبات تحتاج طبيبًا (V289)"})
    rows = []
    for key in [k for k, _n, _s in CONDITIONS] + ["ar_code_switch", "pediatric", "medium_combo"]:
        if key not in off or key not in after["conditions"]:
            continue
        on, of = after["conditions"][key]["hybrid"]["confusion"], off[key]["confusion"]
        med_n = sum(on["medium"].values())
        low_n = sum(on["low"].values())
        high_n = sum(on["high"].values())
        rows.append(f'<tr><th scope="row">{esc(names.get(key, key))}</th>'
                    f'<td class="num">{of["medium"]["medium"]}/{med_n} ← <b>{on["medium"]["medium"]}/{med_n}</b></td>'
                    f'<td class="num">{of["high"]["low"]}/{high_n} ← <b>{on["high"]["low"]}/{high_n}</b></td>'
                    f'<td class="num">{low_n - of["low"]["low"]}/{low_n} ← <b>{low_n - on["low"]["low"]}/{low_n}</b></td></tr>')
    return f"""<section>
  <h2>قراءة المدة والشدة من الكلام نفسه</h2>
  <p class="muted">«لي أربعة أيام والحرارة ما نزلت» — V286 يقرأ المدة والشدة وزيادة الأعراض وتأثيرها على الحياة اليومية من الجملة، ويقتبس الكلمات في سبب النتيجة. يرفع المستوى فقط ولا يصل للطوارئ وحده. الرقم قبل السهم = الطبقة مطفأة، وبعده = مفعّلة.</p>
  <div class="tablewrap"><table><thead><tr><th></th><th>«يحتاج تقييمًا قريبًا» صُنّف صحيحًا</th><th>طارئ ظهر «منخفض» (أخطر خطأ)</th><th>حالة بسيطة رُفعت أعلى من مستواها</th></tr></thead>
  <tbody>{"".join(rows)}</tbody></table></div>
</section>"""


def false_alarm(m) -> dict:
    """Non-urgent cases shown as an emergency (1 - specificity for 'high')."""
    sp = m["high_specificity"]
    if not sp.get("n"):
        return {"n": 0}
    lo, hi = sp["ci95"]
    return {"value": 1 - sp["value"], "ci95": [1 - hi, 1 - lo], "k": sp["n"] - sp["k"], "n": sp["n"]}


def baseline_section(after) -> str:
    """V286: the full system against a keyword matcher with the same vocabulary."""
    conds = after.get("conditions", {})
    if not any("keyword" in v for v in conds.values()):
        return ""
    rows = []
    names = dict((k, n) for k, n, _s in CONDITIONS)
    names.update({"negation": "أعراض منفية صراحة", "ar_code_switch": "عربي + إنجليزي", "ar_arabizi": "عربيزي",
                  "taxonomy_dev": "أنواع الأخطاء (V287)", "pediatric": "أطفال بأعمارهم"})
    for key in [k for k, _n, _s in CONDITIONS] + ["negation", "ar_code_switch", "ar_arabizi", "taxonomy_dev", "pediatric"]:
        c = conds.get(key, {})
        if "keyword" not in c or "hybrid" not in c:
            continue
        kw, full = c["keyword"], c["hybrid"]
        def cell(r):
            return f'<td class="num">{pct(r)}<small>{ci(r)}</small></td>' if r.get("n") else '<td class="num">—</td>'
        rows.append(f'<tr><th scope="row">{esc(names.get(key, key))}<small>{full["n"]} حالة</small></th>'
                    f'{cell(kw["high_sensitivity"])}{cell(full["high_sensitivity"])}{cell(false_alarm(kw))}{cell(false_alarm(full))}</tr>')
    return f"""<section>
  <h2>أفضل من إيش؟ مقارنة ببحث الكلمات</h2>
  <p class="muted">نظام مقارنة يعرف <b>نفس كلمات الطوارئ</b> التي يعرفها SymptoSense (تُستخرج آليًا: كل عبارة يعتبرها المحرك طارئة لوحدها)، ونفس توحيد الحروف، لكنه يبحث عن الكلمة فقط: بلا فهم للنفي، ولا تصحيح إملاء، ولا مفاهيم مركّبة، ولا عربيزي، ولا قواعد فرز. «إنذار طوارئ خاطئ» = حالة غير طارئة ظهر لها تنبيه طوارئ.</p>
  <div class="tablewrap"><table><thead><tr><th></th><th>طارئ مكتشف — بحث الكلمات</th><th>طارئ مكتشف — النظام الكامل</th><th>إنذار طوارئ خاطئ — بحث الكلمات</th><th>إنذار طوارئ خاطئ — النظام الكامل</th></tr></thead>
  <tbody>{"".join(rows)}</tbody></table></div>
</section>"""


REGION_AR = {"najdi": "نجدية", "hejazi": "حجازية", "gulf": "خليجية/شرقية", "southern": "جنوبية", "northern": "شمالية", "unknown": "غير محددة"}


def real_typing(after) -> str:
    """V285: code-switching and Arabizi, with the Arabizi layer on/off, and the regional breakdown."""
    conds = after.get("conditions", {})
    if "ar_arabizi" not in conds:
        return ""
    off = after.get("ablation_arabizi_off", {})
    rows = []
    for key, name in (("ar_code_switch", "عربي + كلمات إنجليزية"), ("ar_arabizi", "عربيزي (9dri y3awrni)")):
        on_m, off_m = conds[key]["hybrid"], off.get(key)
        cells = "".join(f'<td class="num">{pct(m[k]) if m else "—"}<small>{ci(m[k]) if m else ""}</small></td>'
                        for m in (off_m, on_m) for k in ("high_sensitivity", "accuracy"))
        rows.append(f'<tr><th scope="row">{esc(name)}<small>{on_m["n"]} حالة</small></th>{cells}</tr>')
    table = ('<div class="tablewrap"><table><thead><tr><th></th><th>طارئ مكتشف — بدون طبقة العربيزي</th><th>الدقة — بدون</th>'
             '<th>طارئ مكتشف — مع الطبقة</th><th>الدقة — مع</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>")
    reg = after.get("regions") or {}
    reg_rows = "".join(f'<tr><th scope="row">{esc(REGION_AR.get(r, r))}<small>{m["n"]} حالة</small></th>'
                       f'<td class="num">{pct(m["high_sensitivity"])}<small>{ci(m["high_sensitivity"])}</small></td>'
                       f'<td class="num">{pct(m["accuracy"])}<small>{ci(m["accuracy"])}</small></td></tr>' for r, m in reg.items())
    reg_table = ('<div class="tablewrap"><table><thead><tr><th>مفردات المنطقة</th><th>طارئ مكتشف</th><th>الدقة</th></tr></thead><tbody>'
                 + reg_rows + "</tbody></table></div>") if reg_rows else ""
    ext = conds.get("ar_external", {}).get("hybrid")
    seal = after.get("meta", {}).get("external_heldout")
    ext_html = (f'<p><b>مجموعة خارجية مختومة:</b> طارئ مكتشف {pct(ext["high_sensitivity"])} ({ci(ext["high_sensitivity"])})، '
                f'الدقة {pct(ext["accuracy"])}، n = {ext["n"]} من {seal["writers"]} كاتبًا. البصمة <code>{esc(seal["sha256"][:16])}…</code></p>'
                if ext and seal else '<p class="muted">لم تُجمع المجموعة الخارجية بعد (انظري EXTERNAL_HELDOUT_PROTOCOL.md).</p>')
    return f"""<section>
  <h2>كما يكتب الناس فعلًا: خليط إنجليزي وعربيزي</h2>
  <p class="muted">حالات كتبتها صاحبة المشروع أثناء التطوير (مجموعة تطوير، العدد صغير والفترات واسعة). العمود الأول يطفئ طبقة تحويل العربيزي لقياس أثرها وحدها.</p>
  {table}
  <h2 style="margin-top:8px">حسب مفردات المنطقة</h2>
  {reg_table}
  {ext_html}
</section>"""


CSS = """
/* Layout: one reading column of lab-report sections; charts and tables scroll inside their own box. */
:root{
  --paper:#F6F8F9; --sheet:#FFFFFF; --ink:#132430; --muted:#5B6B76; --rule:#D8E0E5;
  --after:#0E6E6A; --before:#A9B6BE; --danger:#B3261E; --danger-bg:#FBEAE8; --good-bg:#E4F2F0;
  --ff-text:"IBM Plex Sans Arabic","Segoe UI",Tahoma,sans-serif; --ff-num:"IBM Plex Mono",ui-monospace,Menlo,monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --paper:#0E161B; --sheet:#152129; --ink:#E3ECF0; --muted:#97A8B2; --rule:#2A3943;
  --after:#4CC2B9; --before:#5A6B75; --danger:#FF8A80; --danger-bg:#3A1D1B; --good-bg:#17332F; color-scheme:dark}}
:root[data-theme="dark"]{
  --paper:#0E161B; --sheet:#152129; --ink:#E3ECF0; --muted:#97A8B2; --rule:#2A3943;
  --after:#4CC2B9; --before:#5A6B75; --danger:#FF8A80; --danger-bg:#3A1D1B; --good-bg:#17332F; color-scheme:dark}
body{background:var(--paper);color:var(--ink);font-family:var(--ff-text);font-size:15px;line-height:1.75;
  padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
main{max-width:860px;margin:0 auto;padding-block:32px 56px;display:grid;gap:28px}
header{display:grid;gap:6px}
.eyebrow{font-size:12px;letter-spacing:.06em;color:var(--muted)}
h1{font-size:clamp(24px,4vw,32px);line-height:1.3;margin:0;text-wrap:balance}
h2{font-size:19px;margin:0 0 4px;text-wrap:balance}
p{margin:0;max-width:65ch}
.muted,small{color:var(--muted)}
section{background:var(--sheet);border:1px solid var(--rule);border-radius:10px;padding:20px;display:grid;gap:12px;min-width:0}
.meta{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:13px;color:var(--muted)}
.meta b{color:var(--ink);font-weight:600}
.flag{display:inline-block;font-size:12px;padding:2px 10px;border-radius:999px;background:var(--danger-bg);color:var(--danger)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.tile{border:1px solid var(--rule);border-radius:8px;padding:14px;display:grid;gap:2px;background:var(--sheet)}
.tile-label{font-size:13px;color:var(--muted)}
.tile-num{font-family:var(--ff-num);font-size:30px;line-height:1.2;display:flex;align-items:baseline;gap:8px;direction:ltr;justify-content:flex-end}
.tile-num b{color:var(--after);font-weight:600}
.from{font-size:16px;color:var(--muted)}
.tile-ci,.tile-hint{font-size:12px;color:var(--muted)}
.legend{display:flex;gap:16px;font-size:13px;color:var(--muted);flex-wrap:wrap}
.key{display:inline-block;width:12px;height:12px;border-radius:2px;margin-inline-end:6px;vertical-align:-1px}
.key.before{background:var(--before)}.key.after{background:var(--after)}
.chartwrap,.tablewrap{overflow-x:auto;min-width:0}
.chartwrap{direction:ltr}  /* scroll starts where the row labels are */
svg.chart{width:100%;min-width:560px;height:auto;display:block;font-family:var(--ff-text)}
.grid{stroke:var(--rule);stroke-width:1}
.tick{fill:var(--muted);font-size:11px;font-family:var(--ff-num)}
.rowlabel{fill:var(--ink);font-size:13px}
.bar.before{fill:var(--before)}.bar.after{fill:var(--after)}
.whisker{stroke:var(--ink);stroke-width:1;opacity:.55}
.val{font-size:11px;font-family:var(--ff-num);fill:var(--muted)}.val.after{fill:var(--after);font-weight:600}
table{border-collapse:collapse;width:100%;min-width:520px;font-size:14px}
th,td{padding:8px 10px;border-bottom:1px solid var(--rule);text-align:start;vertical-align:top}
thead th{font-size:12px;color:var(--muted);font-weight:600}
th small,td small{display:block;font-size:11px}
td.num{font-family:var(--ff-num);font-variant-numeric:tabular-nums;direction:ltr;text-align:right}
td.diag{background:var(--good-bg)}td.danger{background:var(--danger-bg);color:var(--danger);font-weight:600}
table.cm{min-width:360px;max-width:520px}
ul{margin:0;padding-inline-start:20px;display:grid;gap:6px}
code{font-family:var(--ff-num);font-size:13px;background:var(--paper);padding:1px 5px;border-radius:4px}
footer{font-size:12px;color:var(--muted);text-align:center}
"""


V290_CATEGORIES = {
    "choking": "اختناق بطعام أو جسم", "ingestion": "بلع بطارية أو مغناطيس أو مادة كيميائية", "overdose": "جرعة دواء زائدة",
    "burn": "حرق كبير أو عميق أو كهربائي", "fracture": "كسر بتشوّه أو كبير سن لا يقوم", "chest_pressure": "عصر أو ثقل على الصدر",
    "speech_grip": "كلام غير مفهوم أو عدم الإمساك فجأة", "meningitis": "حمى وصداع ورقبة لا تتحرك", "past_history": "حدث قديم يُقرأ كأنه الآن",
    "abscess": "صديد أو خراج", "dental": "ألم أسنان مع انتفاخ", "diarrhoea": "إسهال 3 أيام فأكثر", "urinary": "حرقان التبول",
    "sprain": "التواء مع عرج أيام",
}


def v290_section(after, fresh) -> str:
    """V290: the sealed fresh-probe set and the per-type development cases."""
    if not fresh or "v290_dev" not in after.get("conditions", {}):
        return ""
    b = fresh["baseline_v289"]
    import json as _json
    cases = _json.loads((RESULTS.parent / "v290_dev_cases.json").read_text(encoding="utf-8"))["cases"]
    miss = {m["id"] for m in after.get("misses", []) if m.get("condition") == "v290_dev"}
    by: dict[str, list[int]] = {}
    for c in cases:
        row = by.setdefault(c["category"], [0, 0])
        row[0] += c["id"] not in miss
        row[1] += 1
    rows = "".join(f'<tr><th scope="row">{esc(V290_CATEGORIES.get(k, k))}</th><td class="num">{v[0]}/{v[1]}</td></tr>' for k, v in by.items())
    off = after.get("ablation_v290_rules_off", {}).get("v290_dev", {}).get("accuracy", {})
    past_off = after.get("ablation_past_history_off", {}).get("v290_dev", {}).get("accuracy", {})
    on = after["conditions"]["v290_dev"]["hybrid"]["accuracy"]
    return f"""<section>
  <h2>مراجعة بصياغات جديدة: مجموعة مختومة قبل التعديل</h2>
  <p class="muted">بعد V289 كُتبت 35 وصف أعراض و23 سطر تحليل دم بصياغات لم يرها النظام، وخُتمت ببصمة (sha256) <b>قبل</b> أي تعديل. فُحصت أخطاؤها مرة واحدة، لذلك هي «مجموعة مفحوصة» وليست اختبارًا أعمى؛ الإصلاحات بُنيت على حالات تطوير منفصلة لكل نوع خطأ، والتسميات لم تُعدَّل.</p>
  <div class="tiles">
    <div class="tile"><div class="tile-label">الأعراض — المجموعة المختومة</div><div class="tile-num"><b>{fresh['symptoms']['correct']}/{fresh['symptoms']['n']}</b></div><div class="tile-hint">V289: {b['symptoms_n'] - b['symptoms_wrong']}/{b['symptoms_n']}</div></div>
    <div class="tile"><div class="tile-label">تحليل الدم — المجموعة المختومة</div><div class="tile-num"><b>{fresh['blood']['correct']}/{fresh['blood']['n']}</b></div><div class="tile-hint">V289: {b['blood_n'] - b['blood_wrong']}/{b['blood_n']} · الباقي خلاف تسمية موثّق</div></div>
    <div class="tile"><div class="tile-label">حالات التطوير الجديدة (مع حالات مشابهة خفيفة)</div><div class="tile-num"><b>{on['k']}/{on['n']}</b></div><div class="tile-hint">بدون القواعد الجديدة: {off.get('k', '—')}/{off.get('n', '—')} · بدون فهم الماضي: {past_off.get('k', '—')}/{past_off.get('n', '—')}</div></div>
  </div>
  <div class="tablewrap"><table><thead><tr><th>نوع الخطأ</th><th>صحيح</th></tr></thead><tbody>{rows}</tbody></table></div>
  <p class="muted">لم تتغير نتيجة أي حالة في المجموعات الأخرى إلى الأسوأ (مقارنة حالةً حالة قبل وبعد)، ولا زادت المبالغة.</p>
</section>"""


def render(after, before=None, sweep=None, frozen=None, blood=None, blood_before=None, e2e=None, fresh=None) -> str:
    meta = after.get("meta", {})
    ref = meta.get("reference", "")
    # exact match: the unverified wording also contains the word "clinician" ("not clinician-verified")
    verified = ref.startswith("clinician")
    ref_badge = ('<span class="flag">المرجع: تصنيفات أولية غير مراجَعة طبيًا بعد</span>' if not verified
                 else '<span class="flag" style="background:var(--good-bg);color:var(--after)">المرجع: تصنيف طبيب (مراجعة عمياء)</span>')
    ctl = meta.get("controlled", {})
    s = after["safety_suite"]
    agree = meta.get("starter_vs_clinician")
    agree_html = (f"<li>اتفاق التصنيفات الأولية مع الطبيب: {pct(agree['agreement'])} (Cohen's κ = {agree['kappa']})، n = {agree['n']}.</li>"
                  if agree else "")
    legend = '<div class="legend"><span><i class="key before"></i>قبل (V283)</span><span><i class="key after"></i>بعد (الإصدار الحالي)</span><span>الخط الأسود = فترة ثقة 95%</span></div>'
    return f"""<title>تقييم محرك الفرز SymptoSense</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;600&family=IBM+Plex+Mono:wght@400;600&display=swap">
<style>{CSS}</style>
<main dir="rtl" lang="ar">
<header>
  <div class="eyebrow">تقرير تحقق آلي · ISEF · قابل لإعادة الإنتاج</div>
  <h1>هل يكتشف SymptoSense الحالات الطارئة؟</h1>
  <div class="meta"><span>الإصدار <b>{esc(str(meta.get("app_version", "")))}</b></span>
  <span>محرك الأمان <b>{esc(str(meta.get("safety_engine", "")))}</b></span>
  <span>أُنشئ <b dir="ltr">{esc(str(meta.get("generated_at", "")))}</b></span></div>
  <div>{ref_badge}</div>
</header>

{headline_sections(after, before, frozen)}

<section>
  <h2>اكتشاف الحالات الطارئة حسب شكل الإدخال</h2>
  <p class="muted">نفس المحتوى السريري بصيغ مختلفة: إنجليزي، فصحى، لهجة سعودية، ولهجة بأخطاء كتابة.</p>
  {legend}
  <div class="chartwrap">{bar_chart(CONDITIONS, "high_sensitivity", before, after)}</div>
</section>

<section>
  <h2>أخطر خطأ: حالة طارئة عُرضت بخطورة منخفضة</h2>
  <p class="muted">كلما قصر الشريط كان أفضل.</p>
  {legend}
  <div class="chartwrap">{bar_chart(CONDITIONS, "critical_under_triage", before, after)}</div>
</section>

{v290_section(after, fresh)}

{taxonomy_section(after)}

{e2e_section(e2e)}

{blood_section(blood, blood_before)}

{text_context_section(after)}

{baseline_section(after)}

{real_typing(after)}

<section>
  <h2>مقارنة البدائل (Ablation)</h2>
  <p class="muted">كل طبقة تُضاف فوق التي قبلها. يوضح أين يأتي التحسن.</p>
  {ablation_table(after)}
</section>

<section>
  <h2>أثر الشدة التي يُدخلها المستخدم</h2>
  <p class="muted">التقييم الأساسي يثبّت الشدة عند 2 من 5 حتى يقيس فهم النص وحده. الشدة 3 فأعلى تمنع ظهور أي حالة طارئة كـ«منخفض»، مقابل مبالغة أكبر.</p>
  {severity_table(sweep)}
</section>

<section>
  <h2>مصفوفة الالتباس — مجموعة الاختبار (الإصدار الحالي)</h2>
  <p class="muted">الخلية الحمراء: حالات طارئة عُرضت كـ«منخفض».</p>
  {confusion(after)}
</section>

<section>
  <h2>المنهجية والحدود</h2>
  <ul>
    <li>الحالات أوصاف افتراضية (vignettes) وليست بيانات مرضى؛ لا مشاركين بشريين في هذا التقييم.</li>
    <li>المتغيرات المضبوطة: الشدة {esc(str(ctl.get("severity")))}/5، العمر {esc(str(ctl.get("age")))}، بدون مدة، ومزوّد الذكاء الاصطناعي معطّل (مستوى الخطورة تحدده الطبقات الحتمية فقط).</li>
    <li>قُسّمت الحالات الإنجليزية قبل التحسين: 60 للتطوير و120 للاختبار لم تُفحص حالةً حالة. الفرق بين المجموعتين يقيس الإفراط في التخصيص.</li>
    <li>الحالات العربية (فصحى، لهجة، خليط، عربيزي) كتبتها صاحبة المشروع، فنتائجها نتائج تطوير وليست اختبارًا مستقلًا؛ الاختبار المستقل هو المجموعة الخارجية المختومة.</li>
    <li>الحالات «متوسطة الخطورة» تحسّنت بقراءة المدة والشدة من النص (V286) لكن جزءًا منها ما زال يظهر «منخفضًا»؛ أغلبه يحتاج معرفة تركيبات أعراض لا مدة.</li>
    <li>مجموعة اختبارات الأمان المدمجة: {s["passed"]["k"]}/{s["n"]} ناجحة.</li>
    {agree_html}
    <li>إعادة الإنتاج: <code>python tools/evaluate_engine.py</code> ثم <code>python tools/evaluation_report.py</code></li>
  </ul>
</section>
<footer>SymptoSense — أداة تثقيف صحي وليست جهازًا طبيًا معتمدًا.</footer>
</main>"""


def main(argv=None) -> int:
    load = lambda name: json.loads((RESULTS / name).read_text(encoding="utf-8")) if (RESULTS / name).exists() else None  # noqa: E731
    after = load("results.json")
    if after is None:
        print("run tools/evaluate_engine.py first")
        return 1
    out = RESULTS / "report.html"
    frozen_path = RESULTS.parent / "frozen" / "results_V286_last_clean_en_test.json"
    frozen = json.loads(frozen_path.read_text(encoding="utf-8")) if frozen_path.exists() else None
    out.write_text(render(after, load("baseline_v283.json"), load("severity_sweep.json"), frozen,
                          load("blood_results.json"), load("blood_results_v289.json"), load("e2e_results.json"),
                          load("fresh_probe_results.json")), encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
