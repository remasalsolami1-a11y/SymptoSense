"""Public, simplified "what people are searching for" health-trends page.

Reuses privacy_features.anonymous_health_analytics() exactly as-is -- no new
database queries are added here. That function already enforces a k-anonymity
style floor (a group is only ever shown if at least PRIVACY_THRESHOLD
*distinct users* contributed to it, not just record count), so it is already
safe to surface publicly. This module only adds a simpler, friendlier public
presentation of the symptom/age/risk-level breakdowns; it deliberately leaves
out medication_patterns and the internal consent/eligibility counters, which
are more useful to an admin than to a general visitor.
"""
from __future__ import annotations

import html as html_lib

import privacy_features


def render(lang: str) -> str:
    ar = lang != "en"
    esc = lambda s: html_lib.escape(str(s), quote=True)

    data = privacy_features.anonymous_health_analytics()
    threshold = data.get("privacy_threshold", 5)
    symptoms = data.get("most_reported_symptoms") or []
    age_groups = data.get("age_groups") or []
    risk = data.get("risk_distribution") or []

    title = "الأعراض الأكثر تسجيلًا هذه الفترة" if ar else "Most reported symptoms right now"
    subtitle = (
        f"بيانات مجهولة الهوية بالكامل، تُعرض فقط عندما يشارك {threshold} مستخدمين مختلفين على الأقل "
        "نفس النمط — حتى لا يظهر أي نمط نادر قد يدل على شخص بعينه."
        if ar else
        f"Fully anonymous. A pattern is only shown once at least {threshold} distinct users share it, "
        "so no rare pattern that could point to one specific person is ever displayed."
    )
    empty_msg = (
        "ما فيه بيانات كافية للعرض حاليًا — نحتاج مشاركة أكبر من المستخدمين أولًا."
        if ar else
        "Not enough data yet to show anything meaningfully anonymous — we need more participation first."
    )

    def bar_rows(items, label_fn, max_items=10):
        rows = items[:max_items]
        if not rows:
            return f'<p class="ss-muted" style="text-align:center;padding:20px 0">{esc(empty_msg)}</p>'
        peak = max((r.get("count", 0) for r in rows), default=1) or 1
        out = []
        for r in rows:
            pct = max(6, round((r.get("count", 0) / peak) * 100))
            out.append(
                '<div style="margin-bottom:10px">'
                f'<div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:4px">'
                f'<span>{esc(label_fn(r))}</span><span class="ss-muted">{r.get("count", 0)}</span></div>'
                f'<div style="height:8px;border-radius:6px;background:var(--primary-light,#EAF4FF);overflow:hidden">'
                f'<div style="height:100%;width:{pct}%;border-radius:6px;background:var(--primary,#1565c0)"></div></div>'
                '</div>'
            )
        return "".join(out)

    risk_labels = {
        "high": ("🔴 خطورة عالية" if ar else "🔴 High urgency"),
        "medium": ("🟠 خطورة متوسطة" if ar else "🟠 Medium urgency"),
        "low": ("🟢 خطورة منخفضة" if ar else "🟢 Low urgency"),
        "urgent": ("🚨 طارئ" if ar else "🚨 Emergency-flagged"),
        "unknown": ("⚪ غير محدد" if ar else "⚪ Unspecified"),
    }

    symptoms_html = bar_rows(symptoms, lambda r: r.get("label", ""))
    ages_html = bar_rows(age_groups, lambda r: r.get("label", ""))
    risk_html = bar_rows(risk, lambda r: risk_labels.get(str(r.get("label", "")).lower(), r.get("label", "")))

    footer_note = (
        "هذه لوحة توعوية عامة، وليست أداة تشخيص أو إحصاء طبي رسمي. البيانات مصدرها مستخدمو SymptoSense "
        "الذين وافقوا صراحة على المشاركة البحثية."
        if ar else
        "This is a general awareness panel, not a diagnostic or official medical statistic. Data comes only "
        "from SymptoSense users who explicitly opted into research participation."
    )

    return f'''<main class="container" style="max-width:820px;padding-top:24px;padding-bottom:60px">
<div class="ss-stack">
  <section class="ss-card" style="text-align:center">
    <span class="ss-badge">📈 {"صحة المجتمع" if ar else "Community Health"}</span>
    <h1 style="margin:8px 0 4px">{esc(title)}</h1>
    <p class="ss-muted">{esc(subtitle)}</p>
  </section>

  <section class="ss-card">
    <h2 style="margin-top:0">{"الأعراض الأكثر تسجيلًا" if ar else "Most reported symptoms"}</h2>
    {symptoms_html}
  </section>

  <section class="ss-card">
    <h2 style="margin-top:0">{"حسب الفئة العمرية" if ar else "By age group"}</h2>
    {ages_html}
  </section>

  <section class="ss-card">
    <h2 style="margin-top:0">{"توزيع مستوى الخطورة" if ar else "Urgency level breakdown"}</h2>
    {risk_html}
  </section>

  <p class="ss-muted" style="text-align:center;font-size:12px">{esc(footer_note)}</p>
</div>
</main>'''
