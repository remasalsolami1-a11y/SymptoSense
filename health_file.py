"""Unified personal health file (V252): lab trends + recurring symptoms + medicines + a visit summary.

Everything is computed from what the signed-in user already saved. Trends are
descriptive only (up / down / about the same, and how many consecutive results were
outside the laboratory's own range); nothing here diagnoses or ranks conditions.
"""
from __future__ import annotations

import html as _html
from collections import Counter, OrderedDict
from datetime import datetime, timedelta, timezone

import db
import followup
import vitals

TOL = 0.02          # relative change treated as "about the same"
RECURRING_MIN = 3   # a symptom recorded in this many analyses counts as recurring
HIGH_URGENCY = {"high", "emergency", "urgent"}


def _parse(ts):
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _test_date(test):
    data = test.get("data") or {}
    meta = data.get("report_meta") if isinstance(data, dict) else None
    meta = meta if isinstance(meta, dict) else {}
    return _parse(meta.get("sample_date") or meta.get("report_date") or test.get("timestamp")) or _parse(test.get("timestamp"))


def trend_verdict(prev, last):
    """toward_reference / stable / away_from_reference / unknown for two consecutive readings of one analyte.

    Uses only the laboratory's own status flags (low / normal / high) and the direction of change;
    it never uses a clinical threshold of its own.
    """
    ps, ls = str(prev.get("status") or ""), str(last.get("status") or "")
    ok = {"low", "high", "normal"}
    if ps not in ok or ls not in ok:
        return "unknown"
    if ps == "normal" and ls == "normal":
        return "stable"
    if ps != "normal" and ls == "normal":
        return "toward_reference"
    if ps == "normal" and ls != "normal":
        return "away_from_reference"
    if ps != ls:  # moved from one abnormal side to the other
        return "away_from_reference"
    delta = last["value"] - prev["value"]
    if abs(delta) <= max(abs(prev["value"]) * TOL, 1e-9):
        return "stable"
    toward_normal = delta > 0 if ls == "low" else delta < 0
    return "toward_reference" if toward_normal else "away_from_reference"


def lab_trends(tests):
    """Per-analyte series (oldest first) with direction and out-of-range streak."""
    series = OrderedDict()
    for t in sorted(tests, key=lambda x: _test_date(x) or datetime.min.replace(tzinfo=timezone.utc)):
        when = _test_date(t)
        for ind in (t.get("data") or {}).get("indicators") or []:
            if not isinstance(ind, dict) or not ind.get("key"):
                continue
            try:
                value = float(ind.get("value"))
            except (TypeError, ValueError):
                continue
            k = (str(ind["key"]), str(ind.get("unit") or ""))
            row = series.setdefault(k, {"key": k[0], "unit": k[1], "name_ar": ind.get("name_ar") or ind.get("name"),
                                        "name_en": ind.get("name_en") or ind.get("name"), "points": []})
            row["points"].append({"date": when.date().isoformat() if when else "", "value": value,
                                  "status": str(ind.get("status") or "")})
    out = []
    for row in series.values():
        pts = row["points"]
        direction = "single"
        if len(pts) >= 2:
            prev, last = pts[-2]["value"], pts[-1]["value"]
            direction = "stable" if abs(last - prev) <= max(abs(prev) * TOL, 1e-9) else ("up" if last > prev else "down")
        streak = 0
        for p in reversed(pts):
            if p["status"] in {"low", "high"}:
                streak += 1
            else:
                break
        verdict = trend_verdict(pts[-2], pts[-1]) if len(pts) >= 2 else "single"
        row.update({"verdict": verdict, "direction": direction, "out_of_range_streak": streak, "persistent": streak >= 2,
                    "latest": pts[-1], "count": len(pts)})
        out.append(row)
    out.sort(key=lambda r: (-r["out_of_range_streak"], -r["count"]))
    return out


def symptom_patterns(records):
    c = Counter()
    for r in records:
        for s in set(r.get("symptoms") or []):
            c[s] += 1
    rows = [{"symptom": s, "count": n, "recurring": n >= RECURRING_MIN} for s, n in c.most_common(12)]
    return rows


_FU_WORDS = {"ar": {"better": "تحسنت", "same": "نفس الحال", "worse": "ساءت"}, "en": {"better": "better", "same": "same", "worse": "worse"}}


def _followup_words(user_id, lang):
    try:
        rows = db.get_followups(user_id, limit=3)
    except db.DB_ERRORS:
        return []
    w = _FU_WORDS["en" if lang == "en" else "ar"]
    return ["%s (%s%s)" % (w.get(r["outcome"], r["outcome"]), r["timestamp"][:10], " + علامة جديدة" if r["new_sign"] and lang != "en" else (" + new sign" if r["new_sign"] else "")) for r in rows]


def build(user_id, member_id=0, days=365, lang="ar"):
    days = max(7, min(730, int(days)))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    member = int(member_id or 0)
    records = [r for r in db.get_records(user_id, limit=300, member_id=member) if (_parse(r.get("timestamp")) or since) >= since]
    tests = [t for t in db.get_blood_tests(user_id, limit=40, member_id=member) if (_test_date(t) or since) >= since]
    try:
        meds = [m for m in db.list_med_plans(user_id, member_id=member, active_only=True)]
    except Exception:
        meds = []
    labs = lab_trends(tests)
    try:
        due = followup.due(db.get_records(user_id, limit=20, member_id=member), db.get_followups(user_id))
    except Exception as exc:  # follow-up is a convenience; the file itself must still render
        import logging
        logging.getLogger(__name__).warning("followup lookup failed: %s", type(exc).__name__)
        due = None
    symptoms = symptom_patterns(records)
    high = [r for r in records if str(r.get("urgency") or "").lower() in HIGH_URGENCY]
    data = {
        "ok": True, "days": days, "member_id": member,
        "counts": {"analyses": len(records), "lab_reports": len(tests), "medicines": len(meds), "high_urgency": len(high)},
        "labs": labs, "attention_labs": [r for r in labs if r["persistent"]],
        "symptoms": symptoms, "recurring": [s for s in symptoms if s["recurring"]],
        "medicines": [{"name": m.get("med_name"), "dose": m.get("dose"), "frequency": m.get("frequency")} for m in meds],
        "vitals": vitals.summary_lines(user_id, member, lang),
        "vitals_rows": vitals.latest_rows(user_id, member, lang),
        "followup": due,
        "followup_outcomes": _followup_words(user_id, lang),
        "last_detail": ({"date": (records[0].get("timestamp") or "")[:10], "symptoms": list(records[0].get("symptoms") or [])[:5],
                         "duration": str(records[0].get("duration") or ""), "severity": str(records[0].get("severity") or ""),
                         "urgency": str(records[0].get("urgency") or "")} if records else None),
        "last_analysis": (records[0].get("timestamp") or "")[:10] if records else "",
        "high_urgency_dates": [(r.get("timestamp") or "")[:10] for r in high[:5]],
    }
    data["summary_text"] = summary_text(data, lang)
    return data


_DIR = {"ar": {"up": "ارتفع", "down": "انخفض", "stable": "قريب من السابق", "single": "قراءة واحدة"},
        "en": {"up": "increased", "down": "decreased", "stable": "about the same", "single": "single reading"}}


def _ltr(x, ar):
    """Isolate numbers/units/dates inside Arabic lines so they do not get visually reordered."""
    return "\u2066%s\u2069" % x if ar else str(x)


def summary_text(d, lang="ar"):
    ar = lang != "en"
    L = []
    L.append(("ملخص صحي للزيارة الطبية — آخر %d يومًا" if ar else "Health summary for a clinic visit — last %d days") % d["days"])
    c = d["counts"]
    L.append(("تحليلات أعراض: %d · تقارير دم: %d · أدوية حالية: %d" if ar else "Symptom analyses: %d · Lab reports: %d · Current medicines: %d")
             % (c["analyses"], c["lab_reports"], c["medicines"]))
    ld = d.get("last_detail")
    if ld and ld["symptoms"]:
        L.append(("آخر تحليل (%s): %s — المدة: %s، الشدة: %s، مستوى الاستعجال: %s" if ar else
                  "Latest analysis (%s): %s — duration: %s, severity: %s, urgency: %s")
                 % (_ltr(ld["date"], ar), ("، " if ar else ", ").join(ld["symptoms"]), ld["duration"] or "-", ld["severity"] or "-", _URG["ar" if ar else "en"].get(str(ld["urgency"]).lower(), ld["urgency"] or "-")))
    if d["recurring"]:
        L.append("أعراض متكررة:" if ar else "Recurring symptoms:")
        L += ["- %s (%d %s)" % (s["symptom"], s["count"], "مرات" if ar else "times") for s in d["recurring"][:6]]
    elif d["symptoms"]:
        L.append("الأعراض المسجلة: " + "، ".join(s["symptom"] for s in d["symptoms"][:6]) if ar else
                 "Recorded symptoms: " + ", ".join(s["symptom"] for s in d["symptoms"][:6]))
    if d["high_urgency_dates"]:
        L.append(("تنبيهات عالية الأولوية بتاريخ: " if ar else "High-priority alerts on: ") + ", ".join(_ltr(x, ar) for x in d["high_urgency_dates"]))
    if d["attention_labs"]:
        L.append("قيم خارج نطاق المختبر في أكثر من قراءة متتالية:" if ar else "Values outside the lab range in consecutive readings:")
        for r in d["attention_labs"][:8]:
            nm = r["name_ar"] if ar else r["name_en"]
            L.append("- %s: %s (%s، %d %s)" % (nm, _ltr("%s %s" % (r["latest"]["value"], r["unit"]), ar), _DIR["ar" if ar else "en"][r["direction"]],
                                                r["out_of_range_streak"], "قراءات" if ar else "readings"))
    if d["medicines"]:
        L.append("الأدوية الحالية:" if ar else "Current medicines:")
        L += ["- %s %s" % (m["name"], m["dose"] or "") for m in d["medicines"][:10]]
    if d.get("vitals"):
        L.append("آخر القياسات المنزلية:" if ar else "Latest home measurements:")
        L += ["- " + v for v in d["vitals"][:6]]
    L.append("أسئلة مقترحة للطبيب: هل تحتاج الأعراض المتكررة أو القيم المتكررة خارج النطاق إلى فحص أو متابعة؟ هل تتأثر أدويتي الحالية؟" if ar else
             "Suggested questions: do the recurring symptoms or repeated out-of-range values need tests or follow-up? Could my current medicines be involved?")
    L.append("هذا الملخص مبني على ما سجّلته أنت في التطبيق، وليس تشخيصًا؛ يُراجع مع التقارير الأصلية." if ar else
             "This summary is based only on what you recorded in the app. It is not a diagnosis; review it with the original reports.")
    return "\n".join(L)


_URG = {"ar": {"high": "مرتفع", "medium": "متوسط", "low": "منخفض"}, "en": {"high": "high", "medium": "medium", "low": "low"}}


def render_doctor(d, lang="ar"):
    """One printable page for the clinician: symptoms, duration, medicines, labs, red flags, current decision."""
    ar = lang != "en"
    e = lambda x: _html.escape(str(x if x is not None else ""), quote=True)
    iso = lambda x: '<bdi dir="ltr">%s</bdi>' % e(x)
    ld = d.get("last_detail") or {}
    row = lambda k, v: '<tr><th style="text-align:start;width:32%%;padding:6px;border-bottom:1px solid #ddd">%s</th><td style="padding:6px;border-bottom:1px solid #ddd">%s</td></tr>' % (e(k), v)
    sep = "، " if ar else ", "
    rows = []
    rows.append(row("الأعراض والمدة والشدة" if ar else "Symptoms, duration, severity",
                    e(sep.join(ld.get("symptoms") or []) or "-") + "<br>" + e("المدة: " if ar else "Duration: ") + iso(ld.get("duration") or "-") + e(" · الشدة: " if ar else " · Severity: ") + iso("%s/5" % (ld.get("severity") or "-"))))
    urg = _URG["ar" if ar else "en"].get(str(ld.get("urgency") or "").lower(), "-")
    flags = ", ".join(d.get("high_urgency_dates") or []) or ("لا يوجد" if ar else "none recorded")
    rows.append(row("القرار/الاستعجال المسجّل" if ar else "Recorded urgency / decision", e(urg) + " — " + e("تنبيهات عالية بتاريخ: " if ar else "High alerts on: ") + iso(flags)))
    rec = [s for s in d.get("recurring") or []]
    if rec:
        rows.append(row("أعراض متكررة" if ar else "Recurring symptoms", e(sep.join("%s ×%d" % (s["symptom"], s["count"]) for s in rec[:5]))))
    meds = d.get("medicines") or []
    rows.append(row("الأدوية الحالية" if ar else "Current medicines", e(sep.join(("%s %s" % (m["name"], m["dose"] or "")).strip() for m in meds) or "-")))
    names = _DIR_VERDICT["ar" if ar else "en"]
    labs = [r for r in d.get("labs") or [] if r.get("persistent") or r.get("verdict") in ("away_from_reference", "toward_reference")][:8]
    iso = lambda x: '<bdi dir="ltr">%s</bdi>' % e(x)
    lab_lines = ["%s: %s — %s" % (e((r["name_ar"] if ar else r["name_en"]) or r["key"]), iso("%s %s" % (r["latest"]["value"], r["unit"])), e(names.get(r.get("verdict"), ""))) for r in labs]
    rows.append(row("التحاليل المهمة" if ar else "Key lab results", "<br>".join(lab_lines) or "-"))
    vit = d.get("vitals_rows") or []
    if vit:
        flag = {"ok": "", "attention": " ⚠️", "urgent": " ⚠️", "emergency": " 🚨"}
        rows.append(row("آخر القياسات المنزلية" if ar else "Latest home measurements",
                        "<br>".join("%s: %s %s%s" % (e(v["name"]), iso("%s %s" % (v["value"], v["unit"])), iso(v["date"]), flag.get(v["level"], "")) for v in vit[:6])))
    fu = d.get("followup_outcomes") or []
    if fu:
        rows.append(row("متابعة الأعراض" if ar else "Symptom follow-up", e(sep.join(fu[:3]))))
    note = ("مبني على ما سجّله المستخدم في التطبيق وليس تشخيصًا." if ar else "Based on what the user recorded in the app; not a diagnosis.")
    return ('<main class="container" style="max-width:760px;padding:16px 16px 40px"><section class="ss-card">'
            '<h1 style="margin:0 0 8px;font-size:22px">%s</h1><table style="width:100%%;border-collapse:collapse">%s</table>'
            '<p class="ss-muted" style="font-size:12px">%s</p>'
            '<p class="no-print"><a class="btn" style="display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:0 16px;margin:4px 0;border-radius:12px;border:1px solid #1565c0;background:#fff;color:#1565c0;font-weight:700;text-decoration:none;cursor:pointer" href="%s">%s</a> <button class="btn" style="display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:0 16px;margin:4px 0;border-radius:12px;border:1px solid #1565c0;background:#fff;color:#1565c0;font-weight:700;text-decoration:none;cursor:pointer" type="button" data-ss-click="ssPrint">%s</button></p>'
            '</section></main>') % ("ملخص للطبيب — صفحة واحدة" if ar else "One-page summary for your clinician", "".join(rows), e(note),
                                     "/health-file", "رجوع" if ar else "Back", "طباعة" if ar else "Print")


# Descriptive only: direction relative to the laboratory's own reference range, not a clinical judgement of "improvement".
_DIR_VERDICT = {"ar": {"toward_reference": "يتجه نحو النطاق المرجعي", "away_from_reference": "يبتعد عن النطاق المرجعي", "stable": "قريب من القراءة السابقة", "single": "قراءة واحدة", "unknown": ""},
                "en": {"toward_reference": "moving toward the reference range", "away_from_reference": "moving away from the reference range", "stable": "close to the previous reading", "single": "single reading", "unknown": ""}}


def _spark(points, w=110, h=28):
    vals = [p["value"] for p in points]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    xs = [i * (w - 4) / (len(vals) - 1) + 2 for i in range(len(vals))]
    ys = [h - 3 - (v - lo) / span * (h - 6) for v in vals]
    pts = " ".join("%.1f,%.1f" % (x, y) for x, y in zip(xs, ys))
    return ('<svg width="%d" height="%d" viewBox="0 0 %d %d" role="img" aria-hidden="true"><polyline fill="none" stroke="currentColor" '
            'stroke-width="2" points="%s"/><circle cx="%.1f" cy="%.1f" r="3" fill="currentColor"/></svg>' % (w, h, w, h, pts, xs[-1], ys[-1]))


def render(d, lang="ar"):
    ar = lang != "en"
    e = lambda s: _html.escape(str(s if s is not None else ""), quote=True)
    c = d["counts"]
    stat = lambda n, lab: '<div class="ss-card" style="text-align:center;padding:12px"><div style="font-size:26px;font-weight:700">%s</div><div class="ss-muted" style="font-size:12px">%s</div></div>' % (e(n), e(lab))
    parts = ['<main class="container" style="max-width:860px;padding-top:24px;padding-bottom:60px"><div class="ss-stack">',
             '<section class="ss-card"><span class="ss-badge">🗂️ %s</span><h1 style="margin:8px 0 4px">%s</h1><p class="ss-muted">%s</p></section>' % (
                 "ملفك الصحي" if ar else "Your health file", "ملفك الصحي الموحّد" if ar else "Your unified health file",
                 e(("آخر %d يومًا من بياناتك المحفوظة. الاتجاهات وصفية فقط وليست تشخيصًا." if ar else
                    "The last %d days of what you saved. Trends are descriptive only, not a diagnosis.") % d["days"])),
             '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px">%s%s%s%s</div>' % (
                 stat(c["analyses"], "تحليل أعراض" if ar else "Symptom analyses"), stat(c["lab_reports"], "تقرير دم" if ar else "Lab reports"),
                 stat(c["medicines"], "دواء حالي" if ar else "Current medicines"), stat(c["high_urgency"], "تنبيه عالي" if ar else "High alerts"))]
    fu = d.get("followup")
    if fu:
        sy = "، ".join(fu["symptoms"]) if ar else ", ".join(fu["symptoms"])
        parts.append(
            '<section class="ss-card" id="ssFollowup" data-record="%d" data-error="%s"><h2 style="margin-top:0">%s</h2><p>%s</p>'
            '<p><label><input type="checkbox" id="ssFollowupSign"> %s</label></p>'
            '<p><button class="btn" style="display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:0 16px;margin:4px 0;border-radius:12px;border:1px solid #1565c0;background:#fff;color:#1565c0;font-weight:700;text-decoration:none;cursor:pointer" type="button" data-outcome="better">%s</button> <button class="btn" style="display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:0 16px;margin:4px 0;border-radius:12px;border:1px solid #1565c0;background:#fff;color:#1565c0;font-weight:700;text-decoration:none;cursor:pointer" type="button" data-outcome="same">%s</button> '
            '<button class="btn" style="display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:0 16px;margin:4px 0;border-radius:12px;border:1px solid #1565c0;background:#fff;color:#1565c0;font-weight:700;text-decoration:none;cursor:pointer" type="button" data-outcome="worse">%s</button></p><p id="ssFollowupOut" role="status" hidden></p>'
            '<script src="/static/js/followup.js" defer></script></section>' % (
                int(fu["record_id"]), e("تعذر الحفظ، حاول مرة أخرى." if ar else "Could not save, please try again."),
                "هل تحسنت؟" if ar else "Did it improve?",
                e(("تحليلك بتاريخ %s (%s). كيف حالك الآن؟" if ar else "Your analysis on %s (%s). How are you now?") % (fu["date"], sy)),
                "ظهرت علامة جديدة مقلقة" if ar else "A new worrying sign appeared",
                "تحسنت" if ar else "Better", "نفس الحال" if ar else "The same", "ساءت" if ar else "Worse"))
    if d["recurring"] or d["symptoms"]:
        rows = "".join('<li>%s <span class="ss-muted">× %d</span>%s</li>' % (e(s["symptom"]), s["count"], (" 🔁" if s["recurring"] else "")) for s in d["symptoms"])
        parts.append('<section class="ss-card"><h2 style="margin-top:0">%s</h2><ul>%s</ul><p class="ss-muted" style="font-size:12px">%s</p></section>' % (
            "الأعراض المسجلة" if ar else "Recorded symptoms", rows,
            "🔁 = تكرر %d مرات أو أكثر" % RECURRING_MIN if ar else "🔁 = recorded %d or more times" % RECURRING_MIN))
    if d["labs"]:
        names = _DIR["ar" if ar else "en"]
        rows = ""
        for r in d["labs"][:24]:
            nm = r["name_ar"] if ar else r["name_en"]
            flag = ("⚠️ " + (("خارج النطاق في %d قراءات متتالية" if ar else "outside range in %d consecutive readings") % r["out_of_range_streak"])) if r["persistent"] else ""
            rows += ('<tr><td>%s</td><td dir="ltr">%s %s</td><td>%s</td><td style="color:var(--primary,#1565c0)">%s</td><td>%s</td></tr>'
                     % (e(nm), e(r["latest"]["value"]), e(r["unit"]), e(names[r["direction"]]), _spark(r["points"]), e(flag)))
        parts.append('<section class="ss-card" style="overflow-x:auto"><h2 style="margin-top:0">%s</h2><table style="width:100%%;min-width:520px;border-collapse:collapse"><thead><tr><th>%s</th><th>%s</th><th>%s</th><th></th><th></th></tr></thead><tbody>%s</tbody></table></section>' % (
            "اتجاهات التحاليل" if ar else "Lab trends", "المؤشر" if ar else "Marker", "آخر قيمة" if ar else "Latest", "مقارنة بالسابق" if ar else "vs previous", rows))
    if d["medicines"]:
        parts.append('<section class="ss-card"><h2 style="margin-top:0">%s</h2><ul>%s</ul></section>' % (
            "الأدوية الحالية" if ar else "Current medicines", "".join("<li>%s %s</li>" % (e(m["name"]), e(m["dose"] or "")) for m in d["medicines"])))
    if not (d["symptoms"] or d["labs"] or d["medicines"]):
        parts.append('<section class="ss-card"><p class="ss-muted" style="text-align:center">%s</p></section>' % e(
            "ما فيه بيانات محفوظة بعد. بعد أول تحليل أعراض أو رفع تحليل دم يظهر ملفك هنا." if ar else "Nothing saved yet. Your file appears here after your first symptom analysis or lab upload."))
    parts.append('<section class="ss-card"><h2 style="margin-top:0">%s</h2><pre id="hfSummary" style="white-space:pre-wrap;font-family:inherit;line-height:1.8">%s</pre>'
                 '<p><button class="btn" style="display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:0 16px;margin:4px 0;border-radius:12px;border:1px solid #1565c0;background:#fff;color:#1565c0;font-weight:700;text-decoration:none;cursor:pointer" type="button" data-ss-click="ssCopyText" data-ss-args="[&quot;hfSummary&quot;]">%s</button> '
                 '<button class="btn" style="display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:0 16px;margin:4px 0;border-radius:12px;border:1px solid #1565c0;background:#fff;color:#1565c0;font-weight:700;text-decoration:none;cursor:pointer" type="button" data-ss-click="ssPrint">%s</button> <a class="btn" style="display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:0 16px;margin:4px 0;border-radius:12px;border:1px solid #1565c0;background:#fff;color:#1565c0;font-weight:700;text-decoration:none;cursor:pointer" href="?view=doctor">%s</a> <a class="btn" style="display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:0 16px;margin:4px 0;border-radius:12px;border:1px solid #1565c0;background:#fff;color:#1565c0;font-weight:700;text-decoration:none;cursor:pointer" href="/vitals">%s</a></p></section>' % (
                     "ملخص للطبيب" if ar else "Summary for your doctor", e(d["summary_text"]), "نسخ الملخص" if ar else "Copy summary", "طباعة" if ar else "Print",
                     "صفحة واحدة للطبيب" if ar else "One page for the doctor", "قياساتي المنزلية" if ar else "My home vitals"))
    parts.append("</div></main>")
    return "".join(parts)


def register(app, login_required, api_login_required, data_user_id, page, lang_fn, mk_error):
    from flask import jsonify, request

    def _args():
        try:
            return max(0, int(request.args.get("member") or 0)), int(request.args.get("days") or 365)
        except (TypeError, ValueError):
            return None, None

    @app.route("/api/health-file", methods=["GET"])
    @api_login_required
    def api_health_file():
        try:
            db.init_db()
            member, days = _args()
            if member is None:
                return jsonify({"ok": False, "error": "invalid_query"}), 400
            return jsonify(build(data_user_id(), member, days, lang_fn()))
        except Exception as exc:
            return mk_error(exc, 500)

    @app.route("/health-file", methods=["GET"])
    @login_required
    def health_file_page():
        db.init_db()
        member, days = _args()
        lang = lang_fn()
        data = build(data_user_id(), member or 0, days or 365, lang)
        if request.args.get("view") == "doctor":
            return page("ملخص للطبيب" if lang != "en" else "Clinician summary", render_doctor(data, lang))
        return page("ملفك الصحي" if lang != "en" else "Your health file", render(data, lang))
