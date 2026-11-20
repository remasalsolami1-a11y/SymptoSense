"""Wires the generated verified sources (trusted_sources_v251) into the knowledge base, the health-search
library and the blood-test references.  Kept separate from the generated data file."""
from __future__ import annotations

import trusted_sources_v251 as _t

# Hosts a source link may point to (checked by tests; add a host here only after reviewing the organisation).
ALLOWED_HOSTS = {
    "medlineplus.gov", "www.mayoclinic.org", "my.clevelandclinic.org", "health.clevelandclinic.org", "www.cdc.gov", "www.who.int",
    "www.nhs.uk", "www.hopkinsmedicine.org", "www.testing.com", "www.kidney.org", "www.healthychildren.org", "diabetes.org",
    "ods.od.nih.gov", "www.acog.org", "www.heart.org", "www.aad.org", "www.niddk.nih.gov", "www.nhlbi.nih.gov", "www.ninds.nih.gov",
    "www.niams.nih.gov", "www.nidcr.nih.gov", "www.nimh.nih.gov", "www.nidcd.nih.gov",
}

# (slug, name_ar, name_en, url, type, priority, description_ar, description_en)
EXTRA_SOURCES = [
    ("cleveland-clinic", "كليفلاند كلينك", "Cleveland Clinic", "https://my.clevelandclinic.org/health", "academic_medical_institution", 20,
     "مركز طبي أكاديمي يقدّم مقالات صحية للمرضى تراجعها كوادر طبية.", "Academic medical centre publishing clinician-reviewed patient health articles."),
    ("johns-hopkins", "جونز هوبكنز للطب", "Johns Hopkins Medicine", "https://www.hopkinsmedicine.org/health", "academic_medical_institution", 21,
     "مؤسسة طبية أكاديمية تنشر معلومات صحية للمرضى والأطباء.", "Academic medical institution publishing health information for patients and clinicians."),
    ("testing-com", "Testing.com (Lab Tests Online سابقًا)", "Testing.com (formerly Lab Tests Online)", "https://www.testing.com/tests/", "other_trusted_source", 22,
     "موقع تثقيفي عن الفحوص المخبرية يشرح الغرض من الفحص وكيفية قراءة النتائج.", "Patient-education site explaining what laboratory tests are for and how results are read."),
    ("national-kidney-foundation", "المؤسسة الوطنية للكلى (الولايات المتحدة)", "National Kidney Foundation", "https://www.kidney.org/", "other_trusted_source", 23,
     "منظمة صحية غير ربحية متخصصة في أمراض الكلى وفحوصها.", "Non-profit health organisation focused on kidney disease and kidney tests."),
    ("aap-healthychildren", "الأكاديمية الأمريكية لطب الأطفال — HealthyChildren", "American Academy of Pediatrics — HealthyChildren", "https://www.healthychildren.org/", "other_trusted_source", 24,
     "موقع الأكاديمية الأمريكية لطب الأطفال للأسر.", "American Academy of Pediatrics site for families."),
    ("ada", "جمعية السكري الأمريكية", "American Diabetes Association", "https://diabetes.org/", "other_trusted_source", 25,
     "منظمة طبية متخصصة في السكري ومعايير رعايته.", "Medical organisation specialising in diabetes and standards of care."),
    ("nih-ods", "مكتب المكملات الغذائية — NIH", "NIH Office of Dietary Supplements", "https://ods.od.nih.gov/", "government", 26,
     "مصدر حكومي أمريكي عن الفيتامينات والمعادن والمكملات.", "US government source on vitamins, minerals and supplements."),
]

_ORG_NAMES = {s[0]: s[2] for s in EXTRA_SOURCES}
_ORG_NAMES.update({
    "medlineplus": "MedlinePlus (U.S. National Library of Medicine)", "mayo-clinic": "Mayo Clinic", "cdc": "CDC", "who": "WHO", "nhs": "NHS",
    "acog": "ACOG", "aha": "American Heart Association", "aad": "American Academy of Dermatology", "niddk": "NIDDK (NIH)",
    "nhlbi": "NHLBI (NIH)", "ninds": "NINDS (NIH)", "niams": "NIAMS (NIH)", "nidcr": "NIDCR (NIH)", "nimh": "NIMH (NIH)",
})


def org_name(org):
    return _ORG_NAMES.get(org, org)


def disease_source_rows():
    """{disease slug: [(org, title_ar, title_en, url), ...]} for medical_knowledge enrichment."""
    return {slug: [tuple(r) for r in rows] for slug, rows in _t.DISEASE_SOURCES.items()}


def apply_to_search_kbs(*kbs):
    """Append verified extra sources to search entries (de-duplicated by URL)."""
    for key, rows in _t.SEARCH_SOURCES.items():
        for kb in kbs:
            entry = kb.get(key)
            if not isinstance(entry, dict):
                continue
            sources = entry.setdefault("sources", [])
            seen = {str(s.get("url") or "") for s in sources if isinstance(s, dict)}
            for org, title_ar, title_en, url in rows:
                if url in seen:
                    continue
                seen.add(url)
                sources.append({"name": title_en, "title": title_en, "title_ar": title_ar, "organization": org_name(org),
                                "source_name": org_name(org), "url": url, "last_verified": _t.LAST_VERIFIED})


def blood_direct_and_extra():
    """(direct_by_key, extra_by_key) shaped like blood_test.DIRECT_SOURCES / SPECIALIST_SOURCES entries."""
    direct, extra = {}, {}
    for key, v in _t.BLOOD_SOURCES.items():
        for part in ("primary", "secondary"):
            row = v.get(part)
            if not row:
                continue
            org, title_ar, title_en, url = row
            item = {"name": title_en, "url": url, "organization": org_name(org), "authority": "trusted",
                    "use_ar": "مرجع مباشر عن هذا الفحص: " + title_ar, "use_en": "Direct reference for this test: " + title_en}
            if part == "primary":
                direct[key] = item
            else:
                extra.setdefault(key, []).append(item)
    return direct, extra
