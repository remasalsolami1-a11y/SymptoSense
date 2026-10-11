"""Extra legal sections for the Terms and Privacy pages.
DRAFT text: must be reviewed by a qualified Saudi legal adviser before launch."""
import html as _h

_TERMS = [
    ("الجهة المالكة والتشغيل", "Operator",
     "SymptoSense مشروع تجريبي (Pilot) يطوّره ويديره صاحب المشروع كمبادرة تثقيف صحي، وليس منشأة صحية مرخّصة.",
     "SymptoSense is a pilot health-education project run by its developer. It is not a licensed healthcare facility."),
    ("الحد الأدنى للعمر", "Minimum age",
     "الخدمة موجهة لمن بلغ 18 عامًا. يجوز لمن هم دون ذلك استخدامها بإشراف ولي الأمر فقط، ولا تُنشأ لهم حسابات دون موافقته.",
     "The service is intended for adults aged 18+. Younger users may use it only under a parent or guardian's supervision."),
    ("حدود المسؤولية", "Limitation of liability",
     "تُقدَّم الخدمة «كما هي» دون ضمان لدقة النتائج أو اكتمالها أو ملاءمتها لحالة بعينها. لا يتحمل SymptoSense مسؤولية قرارات صحية اتُّخذت اعتمادًا على محتوى الموقع، ولا مسؤولية انقطاع الخدمة أو أخطاء الجهات الخارجية، وذلك في الحدود التي تسمح بها الأنظمة المعمول بها.",
     "The service is provided “as is” with no warranty of accuracy, completeness or fitness for a particular case. SymptoSense is not liable for health decisions made on the basis of site content, nor for outages or third-party errors, to the extent permitted by applicable law."),
    ("الملكية الفكرية والمصادر", "Intellectual property and sources",
     "تصميم الموقع وبرمجته ونصوصه التحريرية مملوكة للمشروع. تبقى المواد المنقولة عن الجهات الصحية الرسمية (مثل وزارة الصحة ومنظمة الصحة العالمية) ملكًا لأصحابها وتُنسب إليهم برابط المصدر.",
     "The site design, code and editorial text belong to the project. Material drawn from health authorities (e.g. the Ministry of Health, WHO) remains the property of its owners and is attributed with a source link."),
    ("القانون الحاكم", "Governing law",
     "تخضع هذه الشروط لأنظمة المملكة العربية السعودية.",
     "These terms are governed by the laws of the Kingdom of Saudi Arabia."),
    ("تعديل الشروط", "Changes to these terms",
     "قد نحدّث هذه الشروط عند تغيّر الخدمة أو الأنظمة، ويُعدّ استمرارك في الاستخدام بعد النشر قبولًا للنسخة المحدّثة. يظهر تاريخ آخر تحديث أدناه.",
     "We may update these terms as the service or regulations change; continued use after publication means you accept the updated version. The last-update date is shown below."),
]
_DATE = ("آخر تحديث للشروط: 10 أكتوبر 2026", "Terms last updated: 10 October 2026")

_PDPL = ("الأساس النظامي ونقل البيانات (نظام حماية البيانات الشخصية)", "Legal basis and data transfers (Saudi PDPL)",
         "تُعامل المعلومات الصحية بوصفها بيانات شخصية حساسة بموجب نظام حماية البيانات الشخصية في المملكة العربية السعودية. لا نحفظ بياناتك الصحية إلا بموافقتك، ولك الحق في العلم بما نجمعه، والاطلاع عليه، وتصحيحه، وطلب إتلافه، والرجوع عن موافقتك في أي وقت من «مركز الخصوصية». قد تُعالَج بعض البيانات لدى مزودي خدمات خارج المملكة (مثل الاستضافة ومعالجة الذكاء الاصطناعي)، ونقتصر في ذلك على الحد الأدنى اللازم لتشغيل الميزة التي تستخدمها وبعد إتاحة الخيار لك.",
         "Health information is treated as sensitive personal data under the Saudi Personal Data Protection Law (PDPL). We keep your health data only with your consent, and you may ask what we hold, access it, correct it, request its deletion, and withdraw consent at any time from the Privacy Center. Some data may be processed by service providers outside the Kingdom (e.g. hosting and AI processing); we limit this to what the feature you use needs, and only after offering you the choice.")


def _sec(h, p):
    return f"<section><h2>{_h.escape(h)}</h2><p>{_h.escape(p)}</p></section>"


def extend_terms(body, ar):
    i = 0 if ar else 1
    extra = "".join(_sec(t[i], t[2 + i]) for t in _TERMS) + f'<section><p class="muted">{_h.escape(_DATE[i])}</p></section>'
    return body.replace("</main>", extra + "</main>", 1)


def extend_privacy(body, ar):
    i = 0 if ar else 1
    return body.replace("</main>", _sec(_PDPL[i], _PDPL[2 + i]) + "</main>", 1)
