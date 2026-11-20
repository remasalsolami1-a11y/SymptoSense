"""Generate SYSTEM_CARD.md (Arabic + English) from the measured results (V285).

A system card describes the WHOLE triage system: what it is for, who decides what,
how it was evaluated, how well it did and where it fails. MODEL_CARD.md covers only
the auxiliary Naive Bayes classifier.

Every number in the card is read from
    evaluation/results/results.json        (tools/evaluate_engine.py)
    evaluation/results/accessibility.json  (tools/accessibility_audit.py)
    ml_model.json                          (train_model.py)
so the card cannot drift from the measurements: re-run the tools, then

    python tools/system_card.py            # writes SYSTEM_CARD.md
    python tools/system_card.py --check    # exit 1 if SYSTEM_CARD.md is out of date

The prose in this file must not contain hand-typed results (tests/test_v285_system_card.py).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evaluation" / "results"
CARD = ROOT / "SYSTEM_CARD.md"


def _load(name: str) -> dict:
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def p(m: dict | None) -> str:
    """'57.5% (95% CI 42–71%; 23/40)' from a rate dict."""
    if not m or m.get("value") is None:
        return "—"
    lo, hi = m["ci95"]
    return f"{100 * m['value']:.1f}% (95% CI {100 * lo:.0f}–{100 * hi:.0f}%; {m['k']}/{m['n']})"


def short(m: dict | None) -> str:
    return "—" if not m or m.get("value") is None else f"{100 * m['value']:.1f}%"


ROWS = (
    ("en_test", "إنجليزي — مجموعة الاختبار", "English — test set", "inspected"),
    ("en_dev", "إنجليزي — مجموعة التطوير", "English — development set", "dev"),
    ("ar_msa", "عربي فصيح", "Arabic, Modern Standard", "dev"),
    ("ar_dialect", "لهجة سعودية", "Saudi dialect", "dev"),
    ("ar_dialect_typos", "لهجة + أخطاء كتابة", "Dialect + typos", "dev"),
    ("ar_code_switch", "عربي + كلمات إنجليزية", "Arabic + English words", "dev"),
    ("ar_arabizi", "عربيزي", "Arabizi (Latin letters + digits)", "dev"),
    ("taxonomy_dev", "أنواع الأخطاء (V287) + حالات بسيطة مشابهة", "Error-taxonomy cases + mild look-alikes", "dev"),
    ("pediatric", "أطفال بأعمارهم الحقيقية", "Children with their real age", "dev"),
    ("medium_combo", "تركيبات تحتاج طبيبًا + حالات مشابهة بسيطة", "See-a-doctor combinations + mild look-alikes", "dev"),
    ("ar_external", "مجموعة خارجية مختومة", "External sealed set", "held-out"),
)


def _table(res: dict, ar: bool) -> str:
    head = ("| المجموعة | النوع | n | طارئ مكتشف | طارئ عُرض «منخفض» | مبالغة | الدقة | κ |" if ar else
            "| Set | Type | n | Urgent caught | Urgent shown as low | Over-triage | Accuracy | κ |")
    lines = [head, "|---|---|---:|---:|---:|---:|---:|---:|"]
    for key, name_ar, name_en, kind in ROWS:
        m = res["conditions"].get(key, {}).get("hybrid")
        if not m:
            continue
        kind_txt = ({"held-out": "اختبار مستقل", "inspected": "تطوير (فُحصت في V287)"}.get(kind, "تطوير") if ar
                    else {"inspected": "dev (inspected in V287)"}.get(kind, kind))
        lines.append(f"| {name_ar if ar else name_en} | {kind_txt} | {m['n']} | {short(m['high_sensitivity'])} | "
                     f"{short(m['critical_under_triage'])} | {short(m['over_triage'])} | {short(m['accuracy'])} | {m['kappa']} |")
    return "\n".join(lines)


def _medium_low(res: dict) -> tuple[int, int]:
    cm = res["conditions"]["en_test"]["hybrid"]["confusion"]["medium"]
    return cm["low"], sum(cm.values())


def render(res: dict, a11y: dict, ml: dict, frozen: dict | None = None) -> str:
    meta = res["meta"]
    en = res["conditions"]["en_test"]["hybrid"]
    # the last clean held-out measurement (before en_test was inspected); falls back to current
    fz_res = frozen or res
    fz = fz_res["conditions"]["en_test"]["hybrid"]
    fz_kw = fz_res["conditions"]["en_test"].get("keyword")
    fz_ver = "V286" if frozen else "—"
    dev = res["conditions"]["en_dev"]["hybrid"]
    s = res["safety_suite"]
    abl = res.get("ablation_arabizi_off", {}).get("ar_arabizi")
    az = res["conditions"].get("ar_arabizi", {}).get("hybrid")
    med_low, med_n = _medium_low(res)
    tc_off = res.get("ablation_text_context_off", {}).get("en_test")
    med_low_off = tc_off["confusion"]["medium"]["low"] if tc_off else None
    rules_only = res["conditions"]["en_test"]["rules"]["high_sensitivity"]
    kw = {k: v.get("keyword") for k, v in res["conditions"].items()}
    neg_kw, neg_full = kw.get("negation"), res["conditions"]["negation"]["hybrid"]

    def false_alarms(m):
        return "—" if not m else f"{m['high_specificity']['n'] - m['high_specificity']['k']}/{m['high_specificity']['n']}"
    a = a11y["summary"]
    verified = str(meta.get("reference", "")).startswith("clinician")
    ref_ar = "تصنيف طبيب بمراجعة عمياء" if verified else "تصنيفات أولية كتبها الفريق — **غير مراجَعة طبيًا بعد**"
    ref_en = "clinician labels (blinded review)" if verified else "starter labels written by the team — **not yet clinician-verified**"
    ml_meta = ml.get("meta") or ml.get("metadata") or {}
    ml_acc = ml_meta.get("test_accuracy")
    ml_acc_txt = f"{100 * ml_acc:.2f}%" if isinstance(ml_acc, (int, float)) else "—"
    regions = res.get("regions", {})
    reg_names = {"najdi": "نجدية", "hejazi": "حجازية", "gulf": "خليجية/شرقية", "southern": "جنوبية", "northern": "شمالية"}
    reg_ar = "، ".join(f"{reg_names.get(k, k)}: {short(v['high_sensitivity'])} (n={v['high_sensitivity']['n']})" for k, v in regions.items())
    reg_en = ", ".join(f"{k}: {short(v['high_sensitivity'])} (n={v['high_sensitivity']['n']})" for k, v in regions.items())
    ext = meta.get("external_heldout")
    ext_ar = (f"جُمعت ({ext['n']} نصًا من {ext['writers']} كتّاب، البصمة `{ext['sha256'][:16]}…`)." if ext
              else "لم تُجمع بعد — البروتوكول في `evaluation/EXTERNAL_HELDOUT_PROTOCOL.md`.")
    ext_en = (f"collected ({ext['n']} texts from {ext['writers']} writers, seal `{ext['sha256'][:16]}…`)." if ext
              else "not collected yet — protocol in `evaluation/EXTERNAL_HELDOUT_PROTOCOL.md`.")

    return f"""# بطاقة النظام — SymptoSense / System Card

> يُولَّد هذا الملف آليًا من نتائج القياس (`python tools/system_card.py`). لا تعدّليه يدويًا.
> Generated from the measured results. Do not edit by hand.
>
> الإصدار / version **{meta.get('app_version')}** · محرك الأمان / safety engine **`{meta.get('safety_engine')}`** · القياس / measured **{meta.get('generated_at')}**

---

## بالعربية

### ما هو؟
أداة **تثقيف صحي وفرز أولي** بالعربية (والإنجليزية): يصف الشخص أعراضه بكلماته، فيجيب النظام بمستوى الرعاية المناسب — **طوارئ الآن (997)**، أو **تقييم طبي قريب**، أو **رعاية ذاتية مع متى تراجع** — مع السبب والمصادر.
**ليس** تشخيصًا، ولا بديلًا عن الطبيب، ولا جهازًا طبيًا معتمدًا، ولا يُستخدم لتحديد علاج أو جرعة.

### من يتخذ القرار؟
| الطبقة | ماذا تفعل | هل تحدد مستوى الخطورة؟ |
|---|---|---|
| قواعد الأمان الثابتة (عبارات + مفاهيم مركّبة) | تكتشف علامات الخطر حتى بالعامية والأخطاء والعربيزي، وتفهم النفي | **نعم** — وتوقف التحليل وتطلب الطوارئ |
| قواعد الفرز (العمر، الشدة، المدة) | ترفع المستوى عند الحاجة | **نعم** — ترفع فقط |
| قاعدة المعرفة الطبية | تقترح احتمالات من مصادر موثقة | تساهم في المستوى غير الطارئ |
| المصنّف المساعد (Naive Bayes، `MODEL_CARD.md`) | ترتيب احتمالات تعليمي؛ دقته على بيانات اصطناعية {ml_acc_txt} | **لا** |
| الذكاء الاصطناعي التوليدي | يكتب الشرح بلغة بسيطة فقط | **لا** — معطّل تمامًا في كل القياسات أدناه |

كل تنبيه طوارئ يعرض **«لماذا ظهر هذا التنبيه؟»**: الكلمات التي كتبها الشخص نفسها (مقتطعة من نصه حرفيًا)، والمفهوم الطبي الذي تعنيه، والقاعدة التي اشتغلت.

### كيف قيس؟
- حالات افتراضية (vignettes) وليست مرضى؛ لا مشاركين بشريين في هذا القياس.
- المرجع: {ref_ar}.
- ضبط المتغيرات: الشدة {meta['controlled'].get('severity')}/5، العمر {meta['controlled'].get('age')}، بدون مدة، الذكاء الاصطناعي معطّل.
- فصل التطوير عن الاختبار: مجموعة الاختبار الإنجليزية لم تُفحص حالةً حالة حتى V286 (نتائجها مختومة)؛ ابتداءً من V287 تُعدّ نتائجها تطويرًا (`evaluation/HELDOUT_LOG.md`). كل المجموعات العربية كتبتها صاحبة المشروع فهي **مجموعات تطوير** تبالغ في تقدير الأداء.
- فترات ثقة Wilson 95%، ومعامل كابا (κ).

### النتائج (النظام الكامل)
{_table(res, True)}

- **أهم رقم — آخر قياس مستقل ({fz_ver}، مختوم في `evaluation/frozen/`):** على 120 حالة لم تُفحص أثناء التطوير اكتشف النظام {p(fz['high_sensitivity'])} من الحالات الطارئة؛ طارئ عُرض «منخفض» (أخطر خطأ): {p(fz['critical_under_triage'])}. نظام يبحث عن الكلمات فقط اكتشف {short(fz_kw['high_sensitivity']) if fz_kw else '—'} على نفس الحالات.
- **بعد V287 على نفس الحالات (تطوير — فُحصت أخطاؤها):** طارئ مكتشف {p(en['high_sensitivity'])}، وطارئ عُرض «منخفض» {short(en['critical_under_triage'])}. لا يُعرض هذا كاختبار مستقل؛ التقدير المستقل القادم هو المجموعة الخارجية.
- مجموعة التطوير الإنجليزية: {short(dev['high_sensitivity'])}. قواعد الخطر وحدها (الحالي): {short(rules_only)}.
- **مقارنة ببحث الكلمات في النفي والعربيزي:** في حالات النفي أطلق نظام الكلمات {false_alarms(neg_kw)} إنذار طوارئ خاطئ مقابل {false_alarms(neg_full)} لنظامنا؛ وفي العربيزي اكتشف {short(kw['ar_arabizi']['high_sensitivity']) if kw.get('ar_arabizi') else '—'}.
- طبقة العربيزي: اكتشاف الطوارئ في العربيزي {short(abl['high_sensitivity']) if abl else '—'} بدونها ← {short(az['high_sensitivity']) if az else '—'} معها (عدد صغير جدًا).
- حسب مفردات المنطقة (خليط + عربيزي): {reg_ar}.
- مجموعة اختبارات الأمان المدمجة: {s['passed']['k']}/{s['n']}؛ إنذارات خاطئة {short(s['false_alarm_rate'])}.
- المجموعة الخارجية المختومة: {ext_ar}

### حدود معروفة (بصراحة)
1. **الحالات المتوسطة:** في مجموعة الاختبار ما زالت {med_low} من {med_n} حالة «تحتاج تقييمًا قريبًا» تظهر «منخفضة» (كانت {med_low_off} قبل طبقة قراءة المدة والشدة من النص في V286). أغلب الباقي يحتاج معرفة تركيبات أعراض (مثل حرارة مع حرقان بول)، لا مدة.
2. **ما زال يفوّت حالات طارئة** في صياغات لم يُبنَ عليها: آخر رقم مستقل أعلاه وفترة ثقته هو المرجع، لا رقم التطوير.
3. **التصنيفات المرجعية غير مراجَعة طبيًا** حتى يُكمل الطبيب `evaluation/doctor_review.csv`.
4. **العربي كله بيانات تطوير** حتى تُجمع المجموعة الخارجية.
5. قاعدة «حمى + تيبّس رقبة» تشترط علامة ثالثة (تشوش أو صداع شديد…)؛ مسألة سريرية مفتوحة للطبيب المراجِع.
6. تحويل العربيزي يغذّي طبقة المفاهيم فقط، لا قواعد العبارات.
7. **حالات الأطفال** كتبتها صاحبة المشروع من قوائم علامات الخطر المنشورة (NICE وNHS)، و**تصنيفها يحتاج طبيبًا** قبل الاستشهاد بها.
8. لم يُختبر مع مستخدمين حقيقيين؛ أي اختبار كهذا يحتاج موافقة لجنة أخلاقيات البحث أولًا.

### إمكانية الوصول (قياس آلي)
{a['pages']} صفحة × لغتين × شاشتين = {a['page_checks']} فحصًا بأداة axe-core (WCAG 2.2 A/AA): **{a['checks_without_serious_or_critical']} بلا مخالفة جدية**، تباين ألوان غير كافٍ: {a['contrast_violation_nodes']}، أهداف لمس أصغر من 24px: {a['touch_targets_below_24px']}. الأدوات الآلية لا تغني عن الفحص اليدوي (`ACCESSIBILITY_CHECKLIST_AR.md`).

### الخصوصية والسلامة
- لا يُحفظ تحليل الزائر في سجل صحي. تُحفظ نسخة مجهولة مختصرة (العمر، الجنس، الأعراض، المدة، الشدة، المستوى — دون ملاحظات أو اسم أو بريد أو عنوان IP) **فقط** إذا وافق الزائر اختياريًا على التحليلات أو المشاركة البحثية، ويمكنه سحب الموافقة. صاحب الحساب تُحفظ نتائجه في سجله.
- صفحة العرض `/live-demo` تشغّل المحرك الحقيقي على 4 حالات ثابتة ولا تحفظ شيئًا.
- كل تغيير في ملفات المحرك يغيّر بصمة الخوارزمية (`research_study.py`)، فلا تُخلط نتائج نسختين.

---

## In English

### What it is
An Arabic-first **health-education and triage aid**. A person describes symptoms in their own words; the system answers with a level of care — **emergency now (997)**, **medical assessment soon**, or **self-care with when to seek help** — plus the reason and sources. It is **not** a diagnosis, not a substitute for a clinician, not a certified medical device, and not for treatment or dosing decisions.

### Who decides
Fixed safety rules (phrases + compositional concepts, with typo, dialect, Arabizi and negation handling) can force an emergency and stop the analysis. Triage rules (age, severity, duration) can only raise the level. The knowledge base proposes non-urgent possibilities. The auxiliary Naive Bayes classifier (synthetic-data accuracy {ml_acc_txt}, see `MODEL_CARD.md`) never sets the level. Generative AI only writes explanations and was disabled for every measurement below. Every emergency alert shows **"Why are you seeing this alert?"** with the person's own words (exact slices of their text), the concept each one maps to, and the rule that fired.

### Evaluation
Vignettes, not patients; no human participants. Reference: {ref_en}. Controlled: severity {meta['controlled'].get('severity')}/5, age {meta['controlled'].get('age')}, no duration, AI off. The English test set was not inspected case by case up to V286 (frozen); from V287 it is a development set; all Arabic sets were written by the author and are **development** sets. Wilson 95% CIs; Cohen's κ.

{_table(res, False)}

- **Last clean held-out measurement ({fz_ver}, frozen):** urgent caught {p(fz['high_sensitivity'])}; urgent shown as low {p(fz['critical_under_triage'])}; keyword baseline {short(fz_kw['high_sensitivity']) if fz_kw else '—'}.
- **After V287 on the same cases (development — misses were inspected):** urgent caught {p(en['high_sensitivity'])}, urgent shown as low {short(en['critical_under_triage'])}. Not a held-out estimate.
- English development set {short(dev['high_sensitivity'])}; red-flag rules alone (current) {short(rules_only)}. Keyword baseline on denied symptoms: {false_alarms(neg_kw)} false emergency alarms vs {false_alarms(neg_full)}; on Arabizi {short(kw['ar_arabizi']['high_sensitivity']) if kw.get('ar_arabizi') else '—'}.
- Arabizi layer: urgent caught {short(abl['high_sensitivity']) if abl else '—'} without it → {short(az['high_sensitivity']) if az else '—'} with it (very small n).
- By regional vocabulary (code-switching + Arabizi): {reg_en}.
- Built-in safety suite {s['passed']['k']}/{s['n']}; false alarms {short(s['false_alarm_rate'])}. External sealed set: {ext_en}

### Known limitations
{med_low} of {med_n} test-set "assess soon" cases are still shown as low ({med_low_off} before the V286 free-text duration/severity layer); urgent cases are still missed in unseen wording; reference labels await blinded clinician review; all Arabic results are development results; the fever + stiff-neck rule requires a third sign (open clinical question); Arabizi feeds only the concept layer; pediatric cases were written by the author from NICE/NHS warning-sign lists and need clinician labels; no real-user testing (would require ethics-committee approval first).

### Privacy
A guest analysis is never kept as a health record. A minimal anonymous copy (age, gender, symptoms, duration, severity, level — no notes, name, e-mail or IP address) is kept **only** if the visitor opts in to analytics or research, and the consent can be withdrawn. `/live-demo` runs the real engine on four fixed cases and saves nothing.

### Accessibility (automated)
{a['page_checks']} checks ({a['pages']} pages × 2 languages × 2 viewports), axe-core WCAG 2.2 A/AA: {a['checks_without_serious_or_critical']} without serious violations, contrast issues {a['contrast_violation_nodes']}, touch targets under 24 px {a['touch_targets_below_24px']}. Manual checks: `ACCESSIBILITY_CHECKLIST_AR.md`.
"""


def blood_lines(blood: dict | None, before: dict | None, ar: bool) -> str:
    if not blood:
        return ""
    b = lambda k: short(before[k]) if before else "—"  # noqa: E731
    if ar:
        return (f"\n### تحليل الدم\n{blood['meta']['reports']} تقريرًا اصطناعيًا (تطوير): التقارير التي فيها قيمة حرجة وظهرت «عاجل/طوارئ» "
                f"{b('critical_sensitivity')} في V287 ← {p(blood['critical_sensitivity'])}؛ إنذارات حرجة خاطئة {p(blood['false_critical_alarms'])}؛ "
                f"تصنيف كل تحليل {b('status_accuracy')} ← {short(blood['status_accuracy'])}. حدود القيم الحرجة (`blood_critical.py`) تنتظر موافقة الطبيب.\n")
    return (f"\n### Blood reports\n{blood['meta']['reports']} synthetic reports (development): reports with a critical value shown as urgent/emergency "
            f"{b('critical_sensitivity')} in V287 → {p(blood['critical_sensitivity'])}; false critical alarms {p(blood['false_critical_alarms'])}; "
            f"per-test status {b('status_accuracy')} → {short(blood['status_accuracy'])}. Critical limits (`blood_critical.py`) await clinician sign-off.\n")


def build() -> str:
    ml = json.loads((ROOT / "ml_model.json").read_text(encoding="utf-8"))
    frozen_path = ROOT / "evaluation" / "frozen" / "results_V286_last_clean_en_test.json"
    frozen = json.loads(frozen_path.read_text(encoding="utf-8")) if frozen_path.exists() else None
    text = render(_load("results.json"), _load("accessibility.json"), ml, frozen)
    load = lambda n: json.loads((RESULTS / n).read_text(encoding="utf-8")) if (RESULTS / n).exists() else None  # noqa: E731
    blood, before = load("blood_results.json"), load("blood_results_v287.json")
    e2e = load("e2e_results.json")
    if e2e:
        a, g = e2e["api_engine_agreement"], e2e["ai_guard"]
        text = text.replace("### إمكانية الوصول (قياس آلي)",
                            f"### المسار الحقيقي في الموقع\nكل الحالات عبر `POST /api/analyze` كما يرسلها المتصفح: نفس قرار المحرك في **{a['k']}/{a['n']}**. "
                            f"حارس ردود الذكاء الاصطناعي (`answer_guard.py`) صحّح **{g['k']}/{g['n']}** ردًا مطمئنًا خاطئًا مكتوبًا عمدًا.\n\n### إمكانية الوصول (قياس آلي)", 1)
        text = text.replace("### Accessibility (automated)",
                            f"### Real website path\nAll cases through `POST /api/analyze` as the browser sends them: same decision as the engine in **{a['k']}/{a['n']}**. "
                            f"The AI-reply guard (`answer_guard.py`) corrected **{g['k']}/{g['n']}** deliberately dismissive replies.\n\n### Accessibility (automated)", 1)
    marker_ar, marker_en = "### إمكانية الوصول (قياس آلي)", "### Accessibility (automated)"
    text = text.replace(marker_ar, blood_lines(blood, before, True) + "\n" + marker_ar, 1)
    return text.replace(marker_en, blood_lines(blood, before, False) + "\n" + marker_en, 1)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    text = build()
    if a.check:
        ok = CARD.exists() and CARD.read_text(encoding="utf-8") == text
        print("SYSTEM_CARD.md is up to date" if ok else "SYSTEM_CARD.md is out of date: run python tools/system_card.py")
        return 0 if ok else 1
    CARD.write_text(text, encoding="utf-8")
    print(f"wrote {CARD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
