"""V291.1: tidy an assistant reply before it is shown.

* Site paths the model mentions (``/chat``, ``/checkin``...) become the page names a visitor
  reads ("تحليل الأعراض"), never raw URLs in the middle of an Arabic sentence.
* A reply cut off by the token limit loses its unfinished last sentence instead of ending
  mid-word ("تذكّر إن هالمعلومات توعوية"). Emergency numbers are never removed: a cut is
  only made when the dropped tail holds no phone number.
"""
import re

_PAGES = {
    "/chat": ("صفحة تحليل الأعراض", "the symptom check page"),
    "/checkin": ("المتابعة اليومية", "the daily check-in"),
    "/blood": ("تحليل التحاليل", "the lab results page"),
    "/meds": ("صفحة الأدوية", "the medicines page"),
    "/family": ("صحة العائلة", "the family page"),
    "/search": ("البحث الصحي", "health search"),
    "/calculators": ("الحاسبات الصحية", "the health calculators"),
    "/emergency": ("صفحة الطوارئ", "the emergency page"),
    "/vitals": ("قياساتي المنزلية", "home readings"),
    "/health-library": ("المكتبة الصحية", "the health library"),
    "/firstaid": ("الإسعافات الأولية", "first aid"),
}
_PATH_RE = re.compile(r"(?<![\w/.])(/(?:ar|en)?/?(?:" + "|".join(p.strip("/") for p in sorted(_PAGES, key=len, reverse=True)) + r"))(?![\w/-])")
_END = ".!?؟…"


def _page_name(match, en):
    path = "/" + match.group(1).rstrip("/").split("/")[-1]
    names = _PAGES.get(path)
    return names[1 if en else 0] if names else match.group(1)


def tidy(answer, lang="ar"):
    text = str(answer or "").strip()
    if not text:
        return text
    en = lang == "en"
    text = _PATH_RE.sub(lambda m: _page_name(m, en), text)
    if text[-1] not in _END and not text.endswith((")", "»", "\"")):
        cut = max(text.rfind(ch) for ch in _END)
        tail = text[cut + 1:] if cut >= 0 else ""
        if cut >= len(text) * 0.4 and not re.search(r"\d{3,}", tail):
            text = text[:cut + 1].rstrip()
    return text
