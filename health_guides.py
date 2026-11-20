"""Saudi-context health guides (V283): indexable educational pages at
/health-library/guide/<slug>.

Editorial rules:
  * every statement comes from the sources listed on the same guide, which were
    opened on LAST_VERIFIED (exact figures — glucose thresholds, hours, dates — are
    copied from them, not from memory);
  * no medication doses or dose changes: the guides send the reader to their own
    clinician for that;
  * every guide ends with when to call 997.
Dated rules (the outdoor-work ban) carry their year; update them each season.
"""
from __future__ import annotations

import html as _h
import json

LAST_VERIFIED = "2026-11-12"

_MOH_HEAT = ("وزارة الصحة — حرارة الصيف", "Saudi MOH — Summer heat",
             "https://www.moh.gov.sa/HealthAwareness/EducationalContent/Miscellaneous/Pages/004.aspx")

GUIDES = {
    "diabetes-and-ramadan-fasting": {
        "title": ("السكري وصيام رمضان", "Diabetes and Ramadan fasting"),
        "seo_tail": ("كيف تصوم بأمان ومتى تفطر", "how to fast safely and when to break the fast"),
        "lead": (
            "الصيام مع السكري ممكن لكثير من المرضى، لكنه يحتاج تخطيطًا مسبقًا مع الطبيب ومتابعة للسكر خلال اليوم. هذه الصفحة تلخّص إرشادات عامة من جهات صحية سعودية، ولا تُغني عن خطة طبيبك.",
            "Many people with diabetes can fast, but it needs planning with a doctor beforehand and glucose monitoring during the day. This page summarises general guidance from Saudi health organisations and does not replace your doctor's plan.",
        ),
        "sections": [
            (("قبل رمضان", "Before Ramadan"), (
                ("راجع طبيبك قبل رمضان بستة إلى ثمانية أسابيع ليقيّم إن كان الصيام مناسبًا لك، ويراجع أدويتك وتجربتك السابقة مع الصيام.",
                 "See your doctor six to eight weeks before Ramadan to assess whether fasting is suitable for you and to review your medicines and past fasting experience."),
                ("مواعيد الأدوية وجرعاتها تُعدَّل حسب تقييم الطبيب لحالتك. لا تغيّر جرعة دواء السكري أو الإنسولين بنفسك.",
                 "Medicine timing and doses are adjusted according to your doctor's assessment. Do not change your diabetes medicine or insulin dose yourself."),
                ("مرضى السكري الذين لديهم أمراض قلب وأوعية دموية أو سبق لهم الإصابة بجلطة دماغية أو لديهم أمراض كلى يُعدّون أعلى خطورة عند الصيام، ويحتاجون تقييمًا شاملًا من الطبيب والتخصصات المعنية.",
                 "People with diabetes who also have heart or blood-vessel disease, a previous stroke, or kidney disease are at higher risk when fasting and need a full assessment by their doctor and the relevant specialists."),
            )),
            (("أثناء الصيام", "While fasting"), (
                ("قياس السكر بوخز الإصبع أو بجهاز المراقبة لا يُفطِّر، ويُنصح بالقياس بانتظام خلال ساعات الصيام.",
                 "Checking your blood sugar with a finger prick or a glucose monitor does not break the fast, and regular checks during fasting hours are advised."),
                ("تابع مع فريقك الصحي خلال الشهر، خصوصًا إذا تكررت قراءات منخفضة أو مرتفعة.",
                 "Stay in touch with your care team during the month, especially if low or high readings repeat."),
            )),
            (("السحور والإفطار", "Suhoor and iftar"), (
                ("أخّر السحور إلى ما قبل الفجر، واختر كربوهيدرات بطيئة الهضم مثل الحبوب الكاملة والشوفان والشعير والبقوليات.",
                 "Have suhoor as late as possible before dawn and choose slowly digested carbohydrates such as whole grains, oats, barley and legumes."),
                ("تجنّب تناول كميات كبيرة بسرعة عند الإفطار لأنها ترفع السكر فجأة، وفضّل المشوي أو المخبوز على المقلي، ولا تُكثر من الكربوهيدرات.",
                 "Avoid eating large amounts quickly at iftar, which causes sugar spikes; prefer grilled or baked food to fried food, and do not overload on carbohydrates."),
                ("اشرب كمية كافية من السوائل بين الإفطار والسحور.",
                 "Drink enough fluids between iftar and suhoor."),
            )),
        ],
        "warning": (("أفطر فورًا إذا", "Break your fast immediately if"), (
            ("كان السكر أقل من 70 ملغ/دل (3.9 مليمول/لتر)، حتى لو لم تشعر بأعراض.",
             "your blood sugar is below 70 mg/dL (3.9 mmol/L), even without symptoms."),
            ("كان السكر أعلى من 300 ملغ/دل (16.7 مليمول/لتر).",
             "your blood sugar is above 300 mg/dL (16.7 mmol/L)."),
            ("ظهرت أعراض انخفاض السكر: رجفة، تعرّق، تشوّش، دوخة، أو تسارع ضربات القلب.",
             "you have signs of low sugar: shakiness, sweating, confusion, dizziness or a fast heartbeat."),
            ("ظهرت أعراض ارتفاع السكر: عطش شديد، تبوّل متكرر، أو غثيان.",
             "you have signs of high sugar: extreme thirst, frequent urination or nausea."),
            ("أصابك جفاف أو حمّى أو إسهال أو أي مرض حاد.",
             "you become dehydrated or develop a fever, diarrhoea or any acute illness."),
        )),
        "emergency": (
            "اتصل بالإسعاف 997 فورًا إذا فقد المريض وعيه، أو كان مشوّشًا جدًا ولا يستطيع البلع، أو لم يتحسن بعد علاج انخفاض السكر.",
            "Call 997 immediately if the person loses consciousness, is too confused to swallow, or does not improve after treating low blood sugar.",
        ),
        "sources": [
            ("وزارة الصحة — السكري والأمراض المزمنة عند صيام رمضان", "Saudi MOH — Diabetes and chronic diseases when fasting in Ramadan",
             "https://www.moh.gov.sa/healthawareness/educationalcontent/diseases/diabetic/pages/diabetes-and-chronic-diseases-when-fasting-during-ramadan.aspx"),
            ("جونز هوبكنز أرامكو الطبية — إدارة السكري أثناء صيام رمضان", "Johns Hopkins Aramco Healthcare — Managing diabetes during Ramadan fasting",
             "https://www.jhah.com/en/health-wellbeing/ramadan-health-guide/managing-health-conditions-while-fasting/managing-diabetes-during-fasting-in-ramadan/"),
        ],
        "related": ["type-2-diabetes-pattern", "dehydration-pattern"],
    },
    "heat-illness-hajj-umrah": {
        "title": ("ضربة الشمس والإجهاد الحراري في الحج والعمرة", "Heat stroke and heat exhaustion during Hajj and Umrah"),
        "seo_tail": ("الأعراض والوقاية والإسعاف", "symptoms, prevention and first aid"),
        "lead": (
            "الحرارة والجهد البدني والزحام في المشاعر المقدسة ترفع خطر الإجهاد الحراري وضربة الشمس. ضربة الشمس حالة طارئة تهدد الحياة، والتعرف المبكر على العلامات يصنع الفرق.",
            "Heat, physical effort and crowds at the holy sites raise the risk of heat exhaustion and heat stroke. Heat stroke is a life-threatening emergency, and recognising the signs early makes the difference.",
        ),
        "sections": [
            (("علامات الإجهاد الحراري", "Signs of heat exhaustion"), (
                ("صداع، دوخة، تعرّق شديد، عطش مفرط، غثيان أو قيء، ضعف وإرهاق، وقلة التبول، وقد يحدث إغماء.",
                 "Headache, dizziness, heavy sweating, extreme thirst, nausea or vomiting, weakness and exhaustion, passing less urine, and sometimes fainting."),
                ("التشنجات الحرارية: تقلصات عضلية مؤلمة غالبًا في البطن أو الذراعين مع تعرق شديد.",
                 "Heat cramps: painful muscle cramps, often in the abdomen or arms, with heavy sweating."),
            )),
            (("الأكثر عرضة", "Who is most at risk"), (
                ("كبار السن، والرضّع والأطفال، والحوامل، ومن لديهم زيادة وزن أو أمراض مزمنة مثل ارتفاع ضغط الدم وأمراض القلب.",
                 "Older adults, infants and children, pregnant women, and people who are overweight or have long-term conditions such as high blood pressure or heart disease."),
                ("وحتى الشباب الأصحاء عند بذل جهد كبير في الحر.",
                 "Even young, healthy people when they exert themselves in the heat."),
            )),
            (("الوقاية أثناء المناسك", "Prevention during the rituals"), (
                ("تجنّب التعرض المباشر للشمس من الساعة 10 صباحًا حتى 4 عصرًا، واستخدم المظلة أثناء التنقل بين المشاعر.",
                 "Avoid direct sun from 10 a.m. to 4 p.m. and use an umbrella when moving between the holy sites."),
                ("اشرب الماء بانتظام حتى دون الشعور بالعطش، والبس ملابس خفيفة فاتحة اللون.",
                 "Drink water regularly even when you are not thirsty, and wear light, pale-coloured clothing."),
                ("تجنّب المشي على الأسطح الساخنة، وتجنّب صعود الجبال والمرتفعات يوم عرفة لما فيه من إجهاد شديد.",
                 "Avoid walking on hot surfaces, and avoid climbing mountains or heights on the Day of Arafah because of the severe strain."),
            )),
            (("الإسعاف الأولي", "First aid"), (
                ("انقل المصاب إلى مكان مظلل وبارد، وبرّد جسمه بالماء.",
                 "Move the person to a shaded, cool place and cool their body with water."),
                ("إذا كان واعيًا فاعطه ماءً باردًا، أما إذا كان غير واعٍ فلا تعطه أي سوائل لتجنب الاختناق.",
                 "If they are conscious, give them cold water; if they are not conscious, do not give any fluids, to avoid choking."),
                ("انقله سريعًا إلى أقرب مستشفى أو وحدة صحية ميدانية لاستكمال العلاج.",
                 "Get them quickly to the nearest hospital or field health unit to complete treatment."),
            )),
        ],
        "warning": (("علامات ضربة الشمس — حالة طارئة", "Signs of heat stroke — an emergency"), (
            ("ارتفاع حرارة الجسم مع جلد حار وجاف.", "High body temperature with hot, dry skin."),
            ("تغيّر في الوعي أو التصرف: تشوّش أو هذيان أو فقدان الوعي.", "A change in awareness or behaviour: confusion, delirium or loss of consciousness."),
            ("خفقان مع صداع وغثيان ودوخة.", "Palpitations with headache, nausea and dizziness."),
        )),
        "emergency": (
            "عند علامات ضربة الشمس اتصل بالإسعاف 997 فورًا، وابدأ التبريد والإسعاف الأولي حتى وصول المساعدة.",
            "With signs of heat stroke call 997 immediately, and start cooling and first aid until help arrives.",
        ),
        "sources": [
            ("وزارة الصحة — الصحة تدعو للوقاية من الإجهاد الحراري بالحج", "Saudi MOH — Preventing heat stress during Hajj",
             "https://www.moh.gov.sa/Ministry/MediaCenter/News/Pages/News-2025-06-3-001.aspx"),
            _MOH_HEAT,
        ],
        "related": ["heat-stroke-warning-pattern", "heat-exhaustion", "dehydration-pattern"],
    },
    "working-in-summer-heat": {
        "title": ("العمل في حرارة الصيف", "Working in the summer heat"),
        "seo_tail": ("حظر العمل تحت الشمس وعلامات الخطر", "the midday work ban and warning signs"),
        "lead": (
            "العمل في الأماكن المكشوفة أو الحارة دون تكييف من أهم أسباب الإجهاد الحراري في المملكة. هذه الصفحة تجمع ما يحميك صحيًا وما ينص عليه قرار حظر العمل تحت أشعة الشمس.",
            "Working outdoors or in hot spaces without air conditioning is a leading cause of heat illness in the Kingdom. This page brings together what protects your health and what the ban on working under the sun requires.",
        ),
        "sections": [
            (("قرار حظر العمل تحت أشعة الشمس (2026)", "The ban on working under the sun (2026)"), (
                ("يُمنع العمل تحت أشعة الشمس المباشرة من الساعة 12:00 ظهرًا حتى 3:00 عصرًا، من 15 يونيو حتى 15 سبتمبر 2026، في منشآت القطاع الخاص.",
                 "Work under direct sun is prohibited from 12:00 noon to 3:00 p.m., from 15 June to 15 September 2026, in private-sector establishments."),
                ("يمكن الإبلاغ عن المخالفات عبر الرقم الموحد لوزارة الموارد البشرية والتنمية الاجتماعية 19911 أو تطبيق الوزارة.",
                 "Violations can be reported on the Ministry of Human Resources and Social Development unified number 19911 or through the ministry's app."),
            )),
            (("كيف تحمي نفسك", "How to protect yourself"), (
                ("اشرب السوائل بانتظام دون انتظار العطش، وتجنّب المشروبات السكرية. إذا كان طبيبك قد حدّد لك كمية سوائل فاسأله عن الكمية المناسبة في الحر.",
                 "Drink fluids regularly without waiting to feel thirsty and avoid sugary drinks. If your doctor limits your fluids, ask how much is right in the heat."),
                ("البس ملابس واسعة خفيفة فاتحة اللون وقبعة عريضة، واستخدم واقي الشمس.",
                 "Wear loose, light, pale clothing and a wide-brimmed hat, and use sunscreen."),
                ("خذ فترات راحة في الظل، ونظّم الأعمال الشاقة خارج أوقات الذروة، وتجنّب الوجبات الثقيلة.",
                 "Rest in the shade, schedule heavy work outside peak hours, and avoid heavy meals."),
                ("تعرّف على علامات الإجهاد الحراري وراقب زملاءك، خصوصًا الجدد على العمل في الحر.",
                 "Learn the signs of heat illness and look out for your co-workers, especially those new to working in the heat."),
            )),
            (("علامات الإجهاد الحراري", "Signs of heat exhaustion"), (
                ("تعرّق شديد، ضعف وإرهاق، دوخة، صداع، غثيان أو قيء، عطش، وقلة التبول.",
                 "Heavy sweating, weakness and exhaustion, dizziness, headache, nausea or vomiting, thirst, and passing less urine."),
                ("عند ظهورها: توقف عن العمل، وانتقل إلى مكان بارد، وبرّد جسمك واشرب ماءً باردًا إذا كنت واعيًا.",
                 "If they appear: stop working, move somewhere cool, cool your body and drink cold water if you are conscious."),
            )),
        ],
        "warning": (("علامات ضربة الشمس — حالة طارئة", "Signs of heat stroke — an emergency"), (
            ("ارتفاع حرارة الجسم مع جلد حار وجاف.", "High body temperature with hot, dry skin."),
            ("تشوّش أو تغيّر في التصرف أو فقدان الوعي.", "Confusion, a change in behaviour or loss of consciousness."),
        )),
        "emergency": (
            "عند علامات ضربة الشمس اتصل بالإسعاف 997 فورًا، ولا تعطِ سوائل لشخص غير واعٍ.",
            "With signs of heat stroke call 997 immediately, and do not give fluids to someone who is not conscious.",
        ),
        "sources": [
            ("وزارة الموارد البشرية والتنمية الاجتماعية — تطبيق قرار حظر العمل تحت أشعة الشمس", "HRSD — Applying the ban on working under the sun",
             "https://www.hrsd.gov.sa/media-center/news/تطبيق-قرار-حظر-العمل-تحت-أشعة-الشمس"),
            _MOH_HEAT,
        ],
        "related": ["heat-exhaustion", "heat-stroke-warning-pattern", "dehydration-pattern"],
    },
}


def slugs():
    return list(GUIDES)


def seo_title(slug: str, ar: bool) -> str:
    g = GUIDES[slug]
    i = 0 if ar else 1
    return f"{g['title'][i]}: {g['seo_tail'][i]} | SymptoSense"


def index_section(ar: bool, prefix: str) -> str:
    """Card listing all guides, for the library index page."""
    i = 0 if ar else 1
    esc = lambda s: _h.escape(str(s), quote=True)
    links = "".join(
        f'<a class="hl-chip hl-chip-disease" href="{prefix}/health-library/guide/{esc(slug)}">{esc(g["title"][i])}</a>'
        for slug, g in GUIDES.items())
    title = "أدلة صحية بسياق سعودي" if ar else "Saudi-context health guides"
    return f'<section class="ss-card hl-guides"><h2>{esc(title)}</h2><div class="hl-chip-row">{links}</div></section>'


def render(slug: str, lang: str):
    """(title, meta description, body html) or None."""
    g = GUIDES.get(slug)
    if not g:
        return None
    ar = lang != "en"
    i = 0 if ar else 1
    prefix = "/ar" if ar else "/en"
    esc = lambda s: _h.escape(str(s), quote=True)
    lis = lambda items: "".join(f"<li>{esc(item[i])}</li>" for item in items)
    parts = [
        f'<section class="ss-card" style="text-align:center"><span class="ss-badge">{esc("دليل صحي" if ar else "Health guide")}</span>'
        f'<h1>{esc(g["title"][i])}</h1><p>{esc(g["lead"][i])}</p></section>'
    ]
    for heading, items in g["sections"]:
        parts.append(f'<section class="ss-card"><h2>{esc(heading[i])}</h2><ul class="hg-list">{lis(items)}</ul></section>')
    w_heading, w_items = g["warning"]
    parts.append(
        f'<section class="ss-card hg-warn" role="note"><h2>⚠️ {esc(w_heading[i])}</h2><ul class="hg-list">{lis(w_items)}</ul>'
        f'<p class="hg-emergency"><b>{esc(g["emergency"][i])}</b></p>'
        f'<a class="ss-btn ss-btn-primary" href="tel:997">🚑 {esc("اتصل بالإسعاف 997" if ar else "Call 997")}</a></section>'
    )
    related_names = _related_names(g["related"], ar)
    if related_names:
        related = "".join(
            f'<a class="hl-chip hl-chip-disease" href="{prefix}/health-library/disease/{esc(s)}">{esc(n)}</a>' for s, n in related_names)
        parts.append(f'<section class="ss-card"><h2>{esc("صفحات ذات صلة" if ar else "Related pages")}</h2><div class="hl-chip-row">{related}</div></section>')
    cards = "".join(
        f'<a class="hl-source" href="{esc(url)}" target="_blank" rel="noopener noreferrer"><b>{esc(t_ar if ar else t_en)}</b></a>'
        for t_ar, t_en, url in g["sources"])
    parts.append(
        f'<section class="ss-card"><div class="hl-review"><h2>{esc("المصادر" if ar else "Sources")}</h2>'
        f'<span>{esc("آخر تحقق من المصادر: " if ar else "Sources last checked: ")}<bdi dir="ltr">{esc(LAST_VERIFIED)}</bdi></span></div>'
        f'<div class="hl-sources">{cards}</div></section>'
    )
    disclaimer = ("هذه الصفحة توعوية عامة ولا تُغني عن استشارة طبية أو عن خطة طبيبك." if ar else
                  "This page is general education and does not replace medical advice or your doctor's plan.")
    parts.append(f'<p class="ss-muted" style="font-size:12px;text-align:center">{esc(disclaimer)}</p>')
    style = ("<style>.hg-list{line-height:1.95;padding-inline-start:22px;margin:0}.hg-warn{border:1.5px solid #F4B4B4;background:#FFF7F7}"
             ".hg-warn h2{color:#8B1E2D}.hg-emergency{margin:12px 0}.hl-review{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}"
             ".hl-review h2{margin:0}.hl-review span{font-size:12px;color:#6b7e8d}.hl-sources{display:grid;gap:8px;margin-top:12px}"
             ".hl-source{display:block;text-decoration:none;border:1px solid #d9e8f1;border-radius:12px;padding:10px 12px;background:#f8fbfd}"
             ".hl-source b{color:#176f9e}.hl-chip-row{display:flex;flex-wrap:wrap;gap:8px}"
             ".hl-chip{display:inline-flex;align-items:center;padding:8px 12px;border-radius:13px;font-size:13px;font-weight:750;text-decoration:none;"
             "border:1px solid #cfe0f1;background:#f5f9ff;color:#123B70}</style>")
    body = (f'<main class="container" style="max-width:780px;padding-top:24px;padding-bottom:60px"><div class="ss-stack">{"".join(parts)}'
            f'<p style="text-align:center"><a href="{prefix}/health-library">{esc("← رجوع للمكتبة" if ar else "← Back to the library")}</a></p></div>{style}</main>')
    body += _jsonld(g, ar, f"{prefix}/health-library/guide/{slug}")
    return seo_title(slug, ar), g["lead"][i][:155], body


def _related_names(slugs_, ar):
    """[(slug, display name)] for related conditions that exist; empty if the KB is unavailable."""
    import db
    try:
        import health_library
        out = []
        for s in slugs_:
            item = health_library._entity_by_slug("disease", s)
            if item:
                out.append((s, item.get("name_ar" if ar else "name_en") or s))
        return out
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) + tuple(db.DB_ERRORS):  # guide renders even if the KB is down
        return []


def _jsonld(g, ar, url):
    import seo_extras
    i = 0 if ar else 1
    data = {
        "@context": "https://schema.org",
        "@type": "MedicalWebPage",
        "name": g["title"][i],
        "description": g["lead"][i][:300],
        "url": seo_extras._absolute(url),
        "inLanguage": "ar" if ar else "en",
        "dateModified": LAST_VERIFIED,
        "publisher": {"@type": "Organization", "name": "SymptoSense"},
        "citation": [u for _a, _e, u in g["sources"]],
    }
    return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False).replace("</", "<\\/") + "</script>"
