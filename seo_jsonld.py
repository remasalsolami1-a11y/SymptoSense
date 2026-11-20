"""Schema.org JSON-LD for the public home pages (Organization + WebSite only).

Deliberately minimal and factual: no medical claims, ratings, reviews or FAQ markup,
because structured data must match what is visible on the page.
"""
from __future__ import annotations

import json

_NAMES = {"ar": "SymptoSense", "en": "SymptoSense"}
_DESC = {
    "ar": "منصة إرشاد صحي أولي غير تشخيصي تساعدك على فهم الأعراض ومعرفة الخطوة التالية.",
    "en": "A non-diagnostic health guidance platform that helps you understand symptoms and decide the next step.",
}


def _script(data):
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    raw = raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return '<script type="application/ld+json">%s</script>' % raw


def for_path(path, base):
    """Return JSON-LD markup for /ar/ and /en/ (empty string elsewhere)."""
    lang = {"/ar/": "ar", "/en/": "en"}.get(path)
    if not lang:
        return ""
    base = str(base or "").rstrip("/")
    graph = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "Organization", "@id": base + "/#organization", "name": _NAMES[lang], "url": base + "/",
             "logo": base + "/brand-icon.svg"},
            {"@type": "WebSite", "@id": base + "/#website", "url": base + "/%s/" % lang, "name": _NAMES[lang],
             "description": _DESC[lang], "inLanguage": lang, "publisher": {"@id": base + "/#organization"}},
        ],
    }
    return _script(graph)
