"""Extra legal sections for the Terms and Privacy pages.
DRAFT text: must be reviewed by a qualified Saudi legal adviser before launch.

The four opening sections (purpose, not a diagnostic tool, urgent situations,
responsible use) live in webapp.terms_page(); everything here is appended after
them.  Keep wording consistent with the privacy policy (providers, minors,
data deletion) so the two documents never contradict each other.
"""
import html as _h

TERMS_VERSION = "1.1"
_DATE = ("الإصدار %s — آخر تحديث للشروط: 12 نوفمبر 2026" % TERMS_VERSION,
         "Version %s — Terms last updated: 12 November 2026" % TERMS_VERSION)

# (heading_ar, heading_en, body_ar, body_en[, (href, label_ar, label_en)])
_TERMS = [
    ("الجهة المالكة والتشغيل", "Operator",
     "SymptoSense مشروع تجريبي (Pilot) يطوّره ويديره صاحب المشروع كمبادرة تثقيف صحي، وليس منشأة صحية مرخّصة.",
     "SymptoSense is a pilot health-education project run by its developer. It is not a licensed healthcare facility."),
    ("قبول الشروط", "Accepting these terms",
     "باستخدامك الموقع أو إنشائك حسابًا فيه فإنك توافق على هذه الشروط وعلى سياسة الخصوصية. إذا لم توافق عليها فيرجى عدم استخدام الخدمة.",
     "By using the site or creating an account you agree to these terms and to the privacy policy. If you do not agree, please do not use the service."),
    ("الحد الأدنى للعمر", "Minimum age",
     "الخدمة موجهة لمن بلغ 18 عامًا. يجوز لمن هم دون ذلك استخدامها بإشراف ولي الأمر فقط، ولا تُنشأ لهم حسابات دون موافقته.",
     "The service is intended for adults aged 18+. Younger users may use it only under a parent or guardian's supervision."),
    ("الحساب ومسؤولية المستخدم", "Your account and responsibilities",
     "أنت مسؤول عن صحة البيانات التي تدخلها وعن سرية كلمة المرور ووسائل الدخول الخاصة بك، وعن أي نشاط يتم من حسابك. عند إضافة ملف لأحد أفراد العائلة، تؤكد أن لديك الصلاحية لإدخال بياناته الصحية. أبلغنا فورًا إذا اشتبهت في استخدام حسابك دون إذنك.",
     "You are responsible for the accuracy of what you enter, for keeping your password and sign-in methods confidential, and for activity on your account. When you add a family member's profile, you confirm you are authorised to enter their health information. Tell us promptly if you suspect unauthorised use of your account."),
    ("الذكاء الاصطناعي والمحتوى الآلي", "AI and automated content",
     "تستخدم بعض الخدمات (مثل المساعد الذكي وصياغة نتائج التحليل) نماذج ذكاء اصطناعي قد تخطئ أو تُنتج معلومات غير دقيقة أو غير مكتملة، ولا يراجع إنسانٌ كل رد قبل عرضه. تُفحص علامات الخطر بقواعد مستقلة عن الذكاء الاصطناعي، لكن لا تعتمد على أي رد آلي وحده في قرار صحي.",
     "Some features (such as the assistant and the wording of analysis results) use AI models that can be wrong, inaccurate or incomplete, and no human reviews each reply before it is shown. Red flags are checked by rules that do not depend on AI, but do not rely on any automated reply alone for a health decision."),
    ("الاستخدام المحظور", "Prohibited use",
     "لا يجوز استخدام الخدمة في: محاولة اختراقها أو تعطيلها أو تجاوز ضوابط الأمان فيها؛ جمع بياناتها آليًا أو إعادة نشرها تجاريًا دون إذن مكتوب؛ إدخال بيانات صحية لشخص دون إذنه؛ إساءة استخدام قنوات التواصل أو التقييمات؛ أو الاعتماد عليها في قرارات سريرية مهنية.",
     "You may not use the service to: attempt to breach, disrupt or bypass its security controls; scrape or commercially republish its content without written permission; enter someone's health information without their permission; misuse contact channels or reviews; or rely on it for professional clinical decisions."),
    ("الخدمات والروابط الخارجية", "Third-party services and links",
     "تعتمد بعض الميزات على مزودين خارجيين (مثل الاستضافة، ومعالجة الذكاء الاصطناعي، والبريد، وTelegram للتذكيرات، وخرائط OpenStreetMap لميزة «أقرب مستشفى») كما هو موضح في سياسة الخصوصية. الروابط إلى المصادر والجهات الخارجية تخضع لشروطها وسياساتها، ولا نتحكم في محتواها أو توفرها.",
     "Some features rely on third-party providers (such as hosting, AI processing, email, Telegram for reminders, and OpenStreetMap for the nearest-hospital feature) as described in the privacy policy. Links to external sources and organisations are governed by their own terms and policies; we do not control their content or availability.",
     ("/privacy", "سياسة الخصوصية", "Privacy policy")),
    ("حدود المسؤولية", "Limitation of liability",
     "تُقدَّم الخدمة «كما هي» دون ضمان لدقة النتائج أو اكتمالها أو ملاءمتها لحالة بعينها. لا يتحمل SymptoSense مسؤولية قرارات صحية اتُّخذت اعتمادًا على محتوى الموقع، ولا مسؤولية انقطاع الخدمة أو أخطاء الجهات الخارجية، وذلك في الحدود التي تسمح بها الأنظمة المعمول بها.",
     "The service is provided “as is” with no warranty of accuracy, completeness or fitness for a particular case. SymptoSense is not liable for health decisions made on the basis of site content, nor for outages or third-party errors, to the extent permitted by applicable law."),
    ("الملكية الفكرية والمصادر", "Intellectual property and sources",
     "تصميم الموقع وبرمجته ونصوصه التحريرية مملوكة للمشروع. تبقى المواد المنقولة عن الجهات الصحية الرسمية (مثل وزارة الصحة ومنظمة الصحة العالمية) ملكًا لأصحابها وتُنسب إليهم برابط المصدر.",
     "The site design, code and editorial text belong to the project. Material drawn from health authorities (e.g. the Ministry of Health, WHO) remains the property of its owners and is attributed with a source link."),
    ("إيقاف الحساب وإنهاؤه", "Suspension and termination",
     "يمكنك حذف حسابك وبياناتك في أي وقت من «إدارة بياناتي». ويجوز لنا تعليق حساب أو تقييد الوصول عند مخالفة هذه الشروط أو لحماية الخدمة ومستخدميها، أو إيقاف الخدمة التجريبية كليًا أو جزئيًا مع إشعار مسبق معقول متى أمكن.",
     "You can delete your account and data at any time from “Manage my data”. We may suspend an account or restrict access when these terms are breached or to protect the service and its users, and may discontinue the pilot service in whole or in part with reasonable prior notice where possible.",
     ("/manage", "إدارة بياناتي", "Manage my data")),
    ("القانون الحاكم", "Governing law",
     "تخضع هذه الشروط لأنظمة المملكة العربية السعودية، وتختص الجهات القضائية المختصة في المملكة بنظر أي نزاع ينشأ عنها.",
     "These terms are governed by the laws of the Kingdom of Saudi Arabia, and the competent courts of the Kingdom have jurisdiction over any dispute arising from them."),
    ("تعديل الشروط", "Changes to these terms",
     "قد نحدّث هذه الشروط عند تغيّر الخدمة أو الأنظمة، ونرفع رقم الإصدار عند كل تعديل جوهري. يُعدّ استمرارك في الاستخدام بعد النشر قبولًا للنسخة المحدّثة. يظهر رقم الإصدار وتاريخ آخر تحديث أدناه.",
     "We may update these terms as the service or regulations change, and we increase the version number for every material change. Continued use after publication means you accept the updated version. The version and last-update date are shown below."),
    ("التواصل", "Contact",
     "للاستفسار عن هذه الشروط أو لطلبات الخصوصية والحذف استخدم صفحة «تواصل معنا». لا ترسل أعراضًا أو نتائج تحاليل أو معلومات صحية حساسة عبر قنوات التواصل.",
     "For questions about these terms, or for privacy and deletion requests, use the Contact page. Do not send symptoms, lab results or sensitive health information through contact channels.",
     ("/contact", "تواصل معنا", "Contact us")),
]

_PDPL = ("الأساس النظامي ونقل البيانات (نظام حماية البيانات الشخصية)", "Legal basis and data transfers (Saudi PDPL)",
         "تُعامل المعلومات الصحية بوصفها بيانات شخصية حساسة بموجب نظام حماية البيانات الشخصية في المملكة العربية السعودية. لا نحفظ بياناتك الصحية إلا بموافقتك، ولك الحق في العلم بما نجمعه، والاطلاع عليه، وتصحيحه، وطلب إتلافه، والرجوع عن موافقتك في أي وقت من «مركز الخصوصية». قد تُعالَج بعض البيانات لدى مزودي خدمات خارج المملكة (مثل الاستضافة ومعالجة الذكاء الاصطناعي)، ونقتصر في ذلك على الحد الأدنى اللازم لتشغيل الميزة التي تستخدمها وبعد إتاحة الخيار لك.",
         "Health information is treated as sensitive personal data under the Saudi Personal Data Protection Law (PDPL). We keep your health data only with your consent, and you may ask what we hold, access it, correct it, request its deletion, and withdraw consent at any time from the Privacy Center. Some data may be processed by service providers outside the Kingdom (e.g. hosting and AI processing); we limit this to what the feature you use needs, and only after offering you the choice.")


def _sec(h, p, link=None, ar=True):
    more = ""
    if link:
        href, label_ar, label_en = link
        more = ' <a href="%s">%s</a>' % (_h.escape(href, quote=True), _h.escape(label_ar if ar else label_en))
    return f"<section><h2>{_h.escape(h)}</h2><p>{_h.escape(p)}{more}</p></section>"


def extend_terms(body, ar):
    i = 0 if ar else 1
    extra = "".join(_sec(t[i], t[2 + i], t[4] if len(t) > 4 else None, ar) for t in _TERMS)
    extra += f'<section><p class="muted">{_h.escape(_DATE[i])}</p></section>'
    return body.replace("</main>", extra + "</main>", 1)


def extend_privacy(body, ar):
    i = 0 if ar else 1
    return body.replace("</main>", _sec(_PDPL[i], _PDPL[2 + i]) + "</main>", 1)
