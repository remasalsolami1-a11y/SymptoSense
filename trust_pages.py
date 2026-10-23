"""Trust/accountability helpers (V68.15). Kept out of webapp.py to respect its size guard."""
import html as html_lib
import os

MEDICAL_REVIEWER_NAME = os.environ.get("MEDICAL_REVIEWER_NAME", "").strip()
MEDICAL_REVIEWER_TITLE = os.environ.get("MEDICAL_REVIEWER_TITLE", "").strip()
ACADEMIC_SUPERVISOR_NAME = os.environ.get("ACADEMIC_SUPERVISOR_NAME", "").strip()
ACADEMIC_SUPERVISOR_TITLE = os.environ.get("ACADEMIC_SUPERVISOR_TITLE", "").strip()
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "").strip()


def accountability_html(ar):
    """Footer lines for reviewer / supervisor / contact email; empty when nothing is configured."""
    esc = html_lib.escape
    rows = []
    for name, title, lab_ar, lab_en in (
        (MEDICAL_REVIEWER_NAME, MEDICAL_REVIEWER_TITLE, "المراجعة الطبية", "Medical review"),
        (ACADEMIC_SUPERVISOR_NAME, ACADEMIC_SUPERVISOR_TITLE, "الإشراف الأكاديمي", "Academic supervision"),
    ):
        if name:
            rows.append("<span>%s: %s%s</span>" % (esc(lab_ar if ar else lab_en), esc(name), (" — " + esc(title)) if title else ""))
    if CONTACT_EMAIL and "@" in CONTACT_EMAIL:
        rows.append('<span>%s: <a href="mailto:%s">%s</a></span>' % ("البريد" if ar else "Email", esc(CONTACT_EMAIL, quote=True), esc(CONTACT_EMAIL)))
    return ('<p class="f-accountability" style="margin:10px 0;font-size:13px;opacity:.85">' + " · ".join(rows) + "</p>") if rows else ""


def changelog_page():
    from webapp import _lang, _page
    ar = _lang() == "ar"
    title = "سجل التحديثات" if ar else "Changelog"
    entries = [
        ("V76", "مراجعة V76 الشاملة وجودة البيانات" if ar else "V76 full-site and data-quality audit",
         ["من 247 إلى 290 عرضًا نشطًا وفريدًا: +43 صافيًا منذ V74." if ar else "From 247 to 290 active unique symptoms: +43 net since V74.",
          "روابط الحالة–العرض: 715 ← 799 (+84) · أسماء ومرادفات البحث: 1,876 ← 2,281 (+405)." if ar else "Condition–symptom links: 715 → 799 (+84) · searchable name/alias entries: 1,876 → 2,281 (+405).",
          "أضيف مفهوم شائع مستقل، ودُمج مفهوم مكرر واحد، وحُلّت 5 تعارضات تطابق حرفي في المرادفات. ركّز التحديث على جودة مكتبة الأعراض لا تضخيم الأرقام." if ar else "One distinct common symptom concept added, one duplicate merged, and 5 exact alias collisions resolved. The audit focused on library quality rather than inflating counts."]),
        ("V75", "ما الذي أُضيف في V75؟" if ar else "What was added in V75?",
         ["أعراض جديدة في V75 · البحث الصحي يطابق مكتبة الأعراض النشطة ويجمع عدة أعراض في بحث واحد." if ar else "New symptom concepts in V75 · Health Search matches the active symptom library and combines multiple symptoms in one query.",
          "تم ربط البحث الصحي بمكتبة الأعراض النشطة كاملة، وإضافة مفاهيم شائعة ومرادفات عامية جديدة، مع إبقاء كل نتيجة مرتبطة بمصدرها بدل إنشاء علاقة تشخيصية بين الأعراض." if ar else "Health Search is now connected to the full active symptom library, with additional common concepts and colloquial aliases while keeping each result attached to its own source rather than implying a diagnosis between symptoms."]),
    ]
    cards = "".join(
        '<article class="card" style="margin-top:12px"><strong>%s · %s</strong><ul>%s</ul></article>' % (
            html_lib.escape(v), html_lib.escape(h), "".join("<li>%s</li>" % html_lib.escape(i) for i in items))
        for v, h, items in entries)
    intro = ("ملخص مختصر لتحديثات المحتوى وقاعدة المعرفة. الأرقام الحالية تظهر في صفحة «كيف نعمل»." if ar else
             "A short summary of content and knowledge-base updates. Current figures are on the “How we work” page.")
    body = '<main class="v2-info-page"><section><h1>%s</h1><p>%s</p>%s</section></main>' % (html_lib.escape(title), html_lib.escape(intro), cards)
    return _page(title, body)
