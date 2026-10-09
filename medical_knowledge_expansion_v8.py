"""V76 data-quality audit extension for SymptoSense.

This pack adds a distinct common symptom concept after V76 merged a duplicate
mouth-ulcer concept introduced by an earlier expansion. It intentionally adds
no new diagnosis or source organization; acid/food regurgitation is linked to
the already sourced GERD pattern (including the reviewed NIDDK enrichment).
"""

EXTRA_SOURCES_V8 = []
EXTRA_SYMPTOMS_V8 = [
    ("acid-regurgitation", "رجوع الحمض أو الطعام إلى الفم", "Acid or food regurgitation", "digestive",
     ["يرجع الحمض لفمي", "يرجع الاكل لفمي", "يرجع الأكل لفمي", "رجوع طعم حامض للفم", "ارتجاع الحمض للفم"],
     ["acid regurgitation", "food comes back up", "acid comes up into mouth", "regurgitation into mouth"]),
]
EXTRA_DISEASES_V8 = []
EXISTING_DISEASE_SOURCE_ENRICHMENT_V8 = {}
EXISTING_DISEASE_SYMPTOM_ENRICHMENT_V8 = {
    "gerd": {"acid-regurgitation": 0.80},
}
EXTRA_RED_RULES_V8 = []
EXTRA_RED_RULE_DETAILS_V8 = {}
