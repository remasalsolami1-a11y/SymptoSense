#!/usr/bin/env python3
"""Generate the clinician review packet from the LIVE code (so it cannot drift).

    python tools/clinical_packet.py            # rewrite CLINICAL_REVIEW_PACKET_AR.md and clinical_review/*.csv
    python tools/clinical_packet.py --check    # exit 1 if the committed packet differs from the code

The packet only REPORTS what the product currently does (rules, thresholds, wording, expected vs actual
behaviour). It never writes sign-off: approval is recorded only with ``tools/signoff.py approve`` by the
clinician's own details. Output is deterministic (no timestamps) so ``--check`` is meaningful.
"""
from __future__ import annotations

import csv
import io
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["DB_PATH"] = str(Path(tempfile.mkdtemp(prefix="ss_packet_")) / "packet.db")  # seeded defaults only, never a live DB
os.environ.pop("DATABASE_URL", None)

PACKET = ROOT / "CLINICAL_REVIEW_PACKET_AR.md"
OUT = ROOT / "clinical_review"
DECISION_COLS = ["decision (approve / edit / reject)", "clinician notes"]


def _csv(rows: list[list], header: list[str]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header + DECISION_COLS)
    for r in rows:
        w.writerow([("" if v is None else v) for v in r] + ["", ""])
    return buf.getvalue()


def _md_table(header: list[str], rows: list[list]) -> str:
    esc = lambda v: str(v if v is not None else "").replace("|", "\\|").replace("\n", " ")
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(esc(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def _runs(values, fn):
    """Collapse a sweep into [(first, last, level)] runs."""
    runs = []
    for v in values:
        lv = fn(v)
        if runs and runs[-1][2] == lv:
            runs[-1][1] = v
        else:
            runs.append([v, v, lv])
    return runs


def build() -> tuple[str, dict[str, str]]:
    import analysis_core
    import blood_test as bt
    import clinical_signoff as cs
    import health_search as hs
    import health_search_expansion_v251 as x251
    import medical_knowledge as mk
    import medical_regression
    import medication_context as mc
    import redflag_screen as rf
    import safety_engine
    import vitals

    files: dict[str, str] = {}
    signoff = cs.load(cs.PATH)["areas"]
    L: list[str] = []
    A = L.append

    A("# حزمة المراجعة السريرية — SymptoSense")
    A("")
    A("> **مولَّدة تلقائيًا من الكود** بـ `python tools/clinical_packet.py` — لا تعدّلها يدويًا. تصف **ما يفعله المنتج الآن** ولا تقترح قيمًا طبية.")
    A("> لا يوجد أي اعتماد حتى الآن. الاعتماد يُسجَّل فقط ببيانات المراجِع نفسه:")
    A("> `python tools/signoff.py approve <area> --reviewer \"الاسم\" --credentials \"الترخيص\" --date YYYY-MM-DD --notes \"...\"`")
    A("> كل ملف CSV في `clinical_review/` فيه عمودان فارغان للقرار والملاحظات.")
    A("")
    A("## حالة المجالات")
    A(_md_table(["المجال", "الاسم", "الحالة", "ملف المراجعة"], [
        [k, v["title_ar"], "✔ معتمد" if cs.is_reviewed(v) else "… بانتظار الاعتماد", f"`clinical_review/{k}.csv`" if k != "medication_context" else "القسم 8"]
        for k, v in signoff.items()]))
    A("")

    # 1 emergency rules ------------------------------------------------------
    cases = json.loads((ROOT / "runtime_data/emergency_golden.json").read_text(encoding="utf-8"))

    def fires(text):
        patient = {"symptoms": [], "notes": text, "severity": 3}
        return safety_engine.evaluate(patient, "ar")["emergency"] or bool(analysis_core.detect_red_flags([], text, "ar"))

    rows = []
    mism = 0
    for c in cases:
        actual = fires(c["text"])
        mism += actual != c["expect_emergency"]
        rows.append([c["id"], c["category"], c["dialect"], c["text"], "طوارئ" if c["expect_emergency"] else "ليس طوارئ", "طوارئ" if actual else "ليس طوارئ"])
    files["emergency_rules.csv"] = _csv(rows, ["id", "category", "dialect", "text", "expected", "actual"])
    A("## 1) emergency_rules — قواعد الطوارئ وشاشة التوقف")
    A(f"مجموعة ذهبية من **{len(cases)}** عبارة (لهجات وأخطاء إملائية وضوابط سلبية). الفرق بين المتوقع والفعلي: **{mism}**. القواعد نفسها تعبيرات نمطية في `emergency_lexicon.py` و`safety_engine.py`؛ المراجعة الفعلية: هل **المتوقع** في كل صف صحيح سريريًا؟ وما العبارات المفقودة؟")
    A(f"الملف: `clinical_review/emergency_rules.csv`")
    A("")

    # 2 red-flag screens -----------------------------------------------------
    rows = [[s["id"], ",".join(s.get("symptoms") or s.get("slugs") or []), s["tier"], s.get("q_ar") or s.get("question_ar") or s.get("ar"), s.get("q_en") or s.get("question_en") or s.get("en"), s.get("ages") or ""]
            for s in rf.SCREENS]
    files["redflag_screens.csv"] = _csv(rows, ["id", "symptoms", "tier", "question_ar", "question_en", "ages"])
    A("## 2) redflag_screens — أسئلة علامات الخطر")
    A(f"**{len(rf.SCREENS)}** سؤال؛ «نعم» على مستوى emergency توقف التحليل، وعلى today ترفع النصيحة إلى «راجع طبيبًا اليوم». حد أقصى {rf.MAX_SCREENS} أسئلة لكل تحليل.")
    A(_md_table(["#", "المعرّف", "المستوى", "السؤال", "قرار الطبيب"], [[i + 1, r[0], r[2], r[3], ""] for i, r in enumerate(rows)]))
    A("")

    # 3 vitals ---------------------------------------------------------------
    A("## 3) vitals_thresholds — حدود تنبيهات القياسات المنزلية")
    A("الجداول **مستخرجة بتشغيل `vitals.assess` فعليًا** (السلوك الحالي)، وليست مقترحات. المطلوب: هل كل حد ومستوى ورسالة مقبول؟")
    vrows = []

    def sweep(kind, vals, fn, unit, ctx_label=""):
        for a, b, lv in _runs(vals, fn):
            vrows.append([kind, ctx_label, f"{a:g} – {b:g} {unit}", lv])

    sweep("glucose", list(range(20, 801)), lambda v: vitals.assess("glucose", v, None, "random")["level"], "mg/dL", "random")
    sweep("glucose", [i for i in range(20, 801)], lambda v: vitals.assess("glucose", v, None, "fasting")["level"], "mg/dL", "fasting")
    sweep("glucose", [i for i in range(20, 801)], lambda v: vitals.assess("glucose", v, None, "after_meal")["level"], "mg/dL", "after_meal")
    sweep("temp", [round(33 + i / 10, 1) for i in range(0, 101)], lambda v: vitals.assess("temp", v)["level"], "°C")
    sweep("pulse", list(range(20, 251)), lambda v: vitals.assess("pulse", v)["level"], "bpm")
    sweep("spo2", list(range(50, 101)), lambda v: vitals.assess("spo2", v)["level"], "%")
    sweep("bp (systolic, diastolic=70)", list(range(60, 261)), lambda v: vitals.assess("bp", v, 70)["level"], "mmHg systolic")
    sweep("bp (diastolic, systolic=110)", list(range(30, 161)), lambda v: vitals.assess("bp", 110, v)["level"], "mmHg diastolic")
    files["vitals_thresholds.csv"] = _csv(vrows, ["kind", "context", "range", "level"])
    A(_md_table(["النوع", "السياق", "المدى", "المستوى"], vrows))
    A("")
    A("**نصوص الرسائل** (AR/EN) لكل نوع في `vitals.assess` — راجعها في `vitals.py` (الدالة `assess`)؛ تتضمن تعليمات (إسعاف 997، سكر سريع المفعول، إعادة القياس). تأكد من سلامة كل تعليمة.")
    A("")

    # 4 clinical reasoning ---------------------------------------------------
    snap = json.loads((ROOT / "medical_regression_snapshot.json").read_text(encoding="utf-8"))
    cur = medical_regression.snapshot()
    rows = []
    for cid, symptoms, ov, must in medical_regression.CASES:
        rows.append([cid, "، ".join(symptoms), json.dumps(ov, ensure_ascii=False), cur.get(cid, {}).get("level"), "نعم" if cur.get(cid, {}).get("emergency") else "لا"])
    files["clinical_reasoning.csv"] = _csv(rows, ["case", "symptoms", "inputs", "current_level", "emergency_path"])
    A("## 4) clinical_reasoning — منطق الصورة السريرية ورفع المستوى")
    A("القواعد في `clinical_reasoning.py` (تُرفع المستويات ولا تُخفض أبدًا):")
    A("- المستويات بالترتيب: monitor → soon → today → emergency.")
    A("- زيادة في الشدة أو عَرَض جديد أو دواء جديد أو تحليل أسوأ ⇒ رفع خطوة واحدة (من monitor/soon فقط).")
    A("- تنبيه قياس منزلي «urgent» خلال 24 ساعة ⇒ today كحد أدنى.")
    A("- تنبيه قياس منزلي «emergency» ⇒ emergency دائمًا ولا يُخفَّف.")
    A("")
    A("حالات الانحدار الثابتة (المستوى الحالي للمراجعة):")
    A(_md_table(["الحالة", "الأعراض", "المدخلات", "المستوى الحالي", "مسار الطوارئ", "قرار الطبيب"], [r + [""] for r in rows]))
    A(f"\nتطابق اللقطة المعتمدة مع السلوك الحالي: **{'نعم' if all(snap.get(k) == v for k, v in cur.items()) and set(snap) == set(cur) else 'لا — شغّل tools/regression_update.py وراجع الفرق'}**.")
    A("")
    A("> **قرار مفتوح (من نسخة سابقة):** «صعوبة التنفس + شدة 5/5» تُصنَّف طوارئ تعديلًا مؤقتًا من مالك المنتج، و4/5 ⇒ اليوم. يحتاج قرار الطبيب.")
    A("")

    # 5 lab cards ------------------------------------------------------------
    rows = []
    for key, ref in bt.REFS.items():
        lo_m, hi_m, lo_f, hi_f = ref[3]
        danger = "; ".join(f"{lv} {op} {val:g}" for lv, val, op in bt.DANGER_RULES.get(key, []))
        info = bt.INDICATOR_INFO.get(key) or {}
        rows.append([key, ref[0], ref[1], ref[2], f"{lo_m}–{hi_m}", f"{lo_f}–{hi_f}", danger, info.get("low_ar", ""), info.get("high_ar", "")])
    for key, ref in bt.EXTENDED_REFS.items():
        rng = ref[3] if len(ref) > 3 else ()
        info = bt.INDICATOR_INFO.get(key) or {}
        rows.append([key, ref[0], ref[1], ref[2], "/".join(str(v) for v in rng), "", "; ".join(f"{lv} {op} {val:g}" for lv, val, op in bt.DANGER_RULES.get(key, [])), info.get("low_ar", ""), info.get("high_ar", "")])
    files["lab_cards.csv"] = _csv(rows, ["key", "name_ar", "name_en", "unit", "range_male", "range_female", "danger_rules", "text_if_low_ar", "text_if_high_ar"])
    A("## 5) lab_cards — بطاقات التحاليل")
    A(f"**{len(rows)}** مؤشرًا. النطاقات الظاهرة مرجع افتراضي؛ التطبيق يعتمد نطاق المختبر المطبوع في التقرير عند وجوده. حدود الخطر المبرمجة:")
    A(_md_table(["المؤشر", "قاعدة الخطر"], [[r[1], r[6]] for r in rows if r[6]]))
    A("وحدات SI (nmol/L و pmol/L) تُقرأ وتُوسَم لكنها تبقى **unclassified** حتى تُحدَّد نطاقات مرجعية معتمدة.")
    A("")

    # 6 library core ---------------------------------------------------------
    d = mk.list_entities("diseases")
    s = mk.list_entities("symptoms")
    r = mk.list_entities("red_flags")
    rows = ([["disease", e["slug"], e["name_ar"], e["name_en"], e["severity"], e["description_ar"], e["red_flags_ar"], e["recommended_next_step_ar"]] for e in d]
            + [["symptom", e["slug"], e["name_ar"], e["name_en"], f'{e["severity_min"]}-{e["severity_max"]}', e["description_ar"], e["red_flags_ar"], ""] for e in s]
            + [["red_flag", e["slug"], e["name_ar"], e["name_en"], e["risk_level"], e["message_ar"], e["keywords_ar"], e["recommended_action_ar"]] for e in r])
    files["library_core.csv"] = _csv(rows, ["type", "slug", "name_ar", "name_en", "severity/level", "description_or_message_ar", "red_flags_or_keywords_ar", "next_step_ar"])
    A("## 6) library_core — مكتبة الأعراض والأمراض")
    A(f"{len(d)} مرضًا، {len(s)} عرضًا، {len(r)} قاعدة علامات خطر (نصوص عربية في CSV؛ الإنجليزية في قاعدة المعرفة). الملف: `clinical_review/library_core.csv`.")
    A("")

    # 7 search ---------------------------------------------------------------
    def search_rows(keys):
        out = []
        for k in keys:
            e = hs.SEARCH_KB[k]
            srcs = "; ".join(f'{x.get("organization", "")}: {x.get("url", "")}' for x in e.get("sources", []))
            ar = e.get("ar", {})
            out.append([k, e.get("category"), ar.get("title"), ar.get("what"), e.get("last_reviewed"), srcs])
        return out

    new = set(x251.EXTRA_SEARCH_KB_V251)
    hdr = ["key", "category", "title_ar", "text_ar", "last_reviewed", "sources"]
    files["search_new_v251.csv"] = _csv(search_rows(sorted(new)), hdr)
    files["search_base.csv"] = _csv(search_rows([k for k in hs.SEARCH_KB if k not in new]), hdr)
    A("## 7) search_base و search_new_v251 — مواضيع البحث")
    A(f"{len(new)} موضوعًا جديدًا (V251) و{len(hs.SEARCH_KB) - len(new)} أساسيًا، لكل موضوع مصادر ملحقة. ملفان: `search_new_v251.csv` و`search_base.csv` (العمود `sources` يسهّل التحقق من أن النص يطابق المصدر).")
    A("")

    # 8 medication context ---------------------------------------------------
    A("## 8) medication_context — ربط الأدوية بالأعراض والحالات")
    A("لا توجد ادعاءات طبية مكتوبة هنا: يُنتَج الربط فقط إذا كان الدواء في كتالوج الأدوية الموثَّق **و**نص تحذيرات الكتالوج نفسه يذكر الفئة. المطلوب من **صيدلاني/طبيب**: مراجعة قوائم الكلمات التي تُطابَق بها الفئات ونافذة «بدأ حديثًا».")
    rows = []
    for name, table in (("symptom", mc.SYMPTOM_CATS), ("condition", mc.CONDITION_CATS)):
        for cat, (user_words, cat_words) in table.items():
            rows.append([name, cat, mc.CAT_LABEL[cat][0], "، ".join(user_words), "، ".join(cat_words), ""])
    A(_md_table(["النوع", "الفئة", "الاسم", "كلمات المستخدم", "كلمات نص الكتالوج", "قرار"], rows))
    A(f"\nنافذة «دواء بدأ حديثًا»: **{mc.RECENT_DAYS} يومًا**.")
    A("")
    A("> **لا تُكتب تداخلات دوائية أو شدّتها من الذاكرة.** مصدرها الوحيد كتالوج مرخّص يراجعه صيدلاني. انظر `MEDICAL_REVIEW_NEEDED.md` للبنود المفتوحة.")
    A("")
    # one standalone, short file per section so a reviewer can take a single area at a time
    import re as _re
    head = "\n".join(L[:L.index("## حالة المجالات")]).rstrip()
    body = "\n".join(L)
    parts = _re.split(r"(?m)^(?=## \d\) )", body)[1:]
    for part in parts:
        m = _re.match(r"## (\d)\) (\w+)", part)
        files[f"packet_{m.group(1)}_{m.group(2)}.md"] = head + "\n\n" + part.rstrip() + "\n\n---\nالقرار النهائي بعد المراجعة يُسجَّل فقط عبر `tools/signoff.py approve` ببيانات المراجِع.\n"
    return "\n".join(L).rstrip() + "\n", files


def main(argv=None) -> int:
    check = "--check" in (argv or sys.argv[1:])
    text, files = build()
    expected = {PACKET: text, **{OUT / n: c for n, c in files.items()}}
    if check:
        bad = [str(p.relative_to(ROOT)) for p, c in expected.items() if not p.exists() or p.read_text(encoding="utf-8") != c]
        if bad:
            print("STALE (run: python tools/clinical_packet.py):", ", ".join(bad))
            return 1
        print("clinical packet is in sync with the code")
        return 0
    OUT.mkdir(exist_ok=True)
    for p, c in expected.items():
        p.write_text(c, encoding="utf-8")
    print(f"wrote {PACKET.name} and {len(files)} CSV files in {OUT.name}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
