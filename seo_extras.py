"""SEO helpers: sitemap (lastmod + indexable disease pages), robots decision for
library pages, and schema.org JSON-LD for condition pages."""
import html as _h
import json
import os
import re
from datetime import datetime, timezone

import db

_DISEASE = re.compile(r"^/health-library/disease/[a-z0-9][a-z0-9-]*$")
_PAGES = ["/", "/search", "/calculators", "/meds", "/emergency", "/firstaid", "/tips", "/relax", "/about",
          "/how-we-work", "/health-trends", "/health-library", "/privacy", "/terms"]
_PRIORITY = {"/": 1.0, "/how-we-work": 0.8, "/about": 0.8, "/health-library": 0.8}


def indexable(logical_path):
    """Condition pages are the richest library pages and are indexable; thin
    symptom pages stay noindex until they have enough content."""
    return bool(_DISEASE.match(str(logical_path or "").rstrip("/")))


def _site_date():
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        ts = os.path.getmtime(os.path.join(here, "VERSION"))
    except OSError:
        ts = datetime.now(timezone.utc).timestamp()
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


def _disease_rows():
    import health_library as hl
    import medical_knowledge as mk
    mk.init_schema()
    ready = mk.public_source_ready_ids("disease")
    out = []
    for d in mk.list_entities("diseases", False, ""):
        if int(d["id"]) in ready and d.get("slug"):
            out.append((d["slug"], str(d.get("last_updated") or d.get("updated_at") or "")[:10]))
    return out


def sitemap_xml(base):
    base = base.rstrip("/")
    e = lambda s: _h.escape(s, quote=True)
    site_date = _site_date()
    rows = []

    def add(suffix, lastmod, priority, root=False):
        ar_p = "/ar/" if root else "/ar" + suffix
        en_p = "/en/" if root else "/en" + suffix
        xdef = base + "/" if root else base + ar_p
        for loc in (ar_p, en_p):
            rows.append(
                f'  <url><loc>{e(base + loc)}</loc>'
                f'<xhtml:link rel="alternate" hreflang="ar" href="{e(base + ar_p)}"/>'
                f'<xhtml:link rel="alternate" hreflang="en" href="{e(base + en_p)}"/>'
                f'<xhtml:link rel="alternate" hreflang="x-default" href="{e(xdef)}"/>'
                f'<lastmod>{lastmod}</lastmod><priority>{priority:.1f}</priority></url>')

    for s in _PAGES:
        add(s, site_date, _PRIORITY.get(s, 0.7), root=(s == "/"))
    try:
        for slug, lm in _disease_rows():
            add("/health-library/disease/" + slug, lm if re.match(r"^\d{4}-\d{2}-\d{2}$", lm) else site_date, 0.6)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) + db.DB_ERRORS:  # sitemap must never fail because of the library
        pass
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            + "\n".join(rows) + "\n</urlset>\n")


def condition_jsonld(item, name, description, url, ar, sources):
    data = {
        "@context": "https://schema.org",
        "@type": "MedicalWebPage",
        "name": name,
        "description": description,
        "url": url,
        "inLanguage": "ar" if ar else "en",
        "lastReviewed": str(item.get("last_updated") or "")[:10] or None,
        "about": {"@type": "MedicalCondition", "name": name,
                  "signOrSymptom": [{"@type": "MedicalSymptom", "name": s.get("name_ar" if ar else "name_en")}
                                    for s in (item.get("symptoms") or []) if s.get("name_ar" if ar else "name_en")][:12]},
        "publisher": {"@type": "Organization", "name": "SymptoSense"},
        "citation": [s.get("reference_url") or s.get("official_url") for s in (sources or [])
                     if (s.get("reference_url") or s.get("official_url"))][:6],
    }
    data = {k: v for k, v in data.items() if v}
    text = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return '<script type="application/ld+json">' + text + "</script>"


def related_symptoms(item, ar, prefix):
    rows = item.get("symptoms") or []
    links = []
    for s in rows[:14]:
        n = s.get("name_ar" if ar else "name_en")
        if n and s.get("slug"):
            links.append(f'<a class="hl-chip hl-chip-symptom" href="{prefix}/health-library/symptom/{_h.escape(s["slug"], quote=True)}">{_h.escape(n)}</a>')
    if not links:
        return ""
    title = "الأعراض المرتبطة بهذه الحالة" if ar else "Symptoms linked to this condition"
    return f'<section class="ss-card"><h2>{title}</h2><div class="hl-chip-row">{"".join(links)}</div></section>'
