"""Condition-specific Saudi references (V282).

Every URL below was opened on LAST_VERIFIED and its heading matched the
condition (heading recorded in the comment). They attach to the existing
"saudi-moh" source organisation, so the public "verified sources" count does not
change; what changes is that these pages now cite a Saudi page about the condition
itself, not only the generic MOH 937 care-navigation link.

Rules for additions:
  * one page per condition, about that condition (not a category index, PDF or news item);
  * open the URL and record its heading before adding it;
  * host must be in ALLOWED_HOSTS (official Saudi government health domains).
"""
from __future__ import annotations

LAST_VERIFIED = "2026-11-12"
ALLOWED_HOSTS = {"www.moh.gov.sa"}
ORG = "saudi-moh"

# slug: (title_ar, title_en, url)
DISEASE_REFERENCES = {
    # «ارتفاع ضغط الدم»
    "high-blood-pressure": ("ارتفاع ضغط الدم — وزارة الصحة", "High blood pressure — Saudi MOH",
                            "https://www.moh.gov.sa/HealthAwareness/EducationalContent/Diseases/Heartcirculatory/Pages/0011.aspx"),
    # «السكري من النوع الثاني»
    "type-2-diabetes-pattern": ("السكري من النوع الثاني — وزارة الصحة", "Type 2 diabetes — Saudi MOH",
                                "https://www.moh.gov.sa/HealthAwareness/EducationalContent/Diseases/diabetic/Pages/008.aspx"),
    # «التوعية بالربو»
    "asthma": ("التوعية بالربو — وزارة الصحة", "Asthma awareness — Saudi MOH",
               "https://www.moh.gov.sa/awarenessplateform/chronicdisease/pages/asthma.aspx"),
    # «حصيات الكلى»
    "kidney-stones": ("حصيات الكلى — وزارة الصحة", "Kidney stones — Saudi MOH",
                      "https://www.moh.gov.sa/HealthAwareness/EducationalContent/Diseases/Urology/Pages/010.aspx"),
    # «الاكتئاب»
    "clinical-depression": ("الاكتئاب — وزارة الصحة", "Depression — Saudi MOH",
                            "https://www.moh.gov.sa/HealthAwareness/EducationalContent/Diseases/Mental/Pages/Depression.aspx"),
    # «اضطراب القلق العام»
    "generalised-anxiety-disorder": ("اضطراب القلق العام — وزارة الصحة", "Generalised anxiety disorder — Saudi MOH",
                                     "https://www.moh.gov.sa/awarenessplateform/varioustopics/pages/anxietydisorder.aspx"),
    # «حرارة الصيف» — covers heat stroke, heat exhaustion, at-risk groups and first aid
    "heat-stroke-warning-pattern": ("حرارة الصيف: ضربة الشمس والإجهاد الحراري — وزارة الصحة", "Summer heat: heat stroke and heat exhaustion — Saudi MOH",
                                    "https://www.moh.gov.sa/HealthAwareness/EducationalContent/Miscellaneous/Pages/004.aspx"),
    "heat-exhaustion": ("حرارة الصيف: ضربة الشمس والإجهاد الحراري — وزارة الصحة", "Summer heat: heat stroke and heat exhaustion — Saudi MOH",
                        "https://www.moh.gov.sa/HealthAwareness/EducationalContent/Miscellaneous/Pages/004.aspx"),
    # «التوعية بالارتجاع المريئي»
    "gerd": ("التوعية بالارتجاع المريئي — وزارة الصحة", "Gastro-oesophageal reflux awareness — Saudi MOH",
             "https://www.moh.gov.sa/awarenessplateform/VariousTopics/Pages/GERD.aspx"),
    # «متلازمة تكيس المبايض»
    "polycystic-ovary-syndrome-pattern": ("متلازمة تكيس المبايض — وزارة الصحة", "Polycystic ovary syndrome — Saudi MOH",
                                          "https://www.moh.gov.sa/HealthAwareness/EducationalContent/wh/Pages/0014.aspx"),
    # «الإنفلونزا»
    "influenza": ("الإنفلونزا — وزارة الصحة", "Influenza — Saudi MOH",
                  "https://www.moh.gov.sa/awarenessplateform/VariousTopics/Pages/Influenza.aspx"),
    # «التوعية بالتهاب المسالك البولية» (all age groups)
    "urinary-tract-infection": ("التوعية بالتهاب المسالك البولية — وزارة الصحة", "Urinary tract infection awareness — Saudi MOH",
                                "https://www.moh.gov.sa/awarenessplateform/VariousTopics/Pages/UrinaryTractInfection.aspx"),
}
# Already linked to a condition-specific MOH page before V282 (kept as they are):
# iron-deficiency-anaemia, migraine, underactive-thyroid.


def disease_source_rows() -> dict:
    """{slug: [(org, title_ar, title_en, url)]} in the EXISTING_DISEASE_SOURCE_ENRICHMENT shape."""
    return {slug: [(ORG, ar, en, url)] for slug, (ar, en, url) in DISEASE_REFERENCES.items()}
