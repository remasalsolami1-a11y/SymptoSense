# -*- coding: utf-8 -*-
"""Blood test (CBC) parsing + awareness analysis for SymptoSense.
Awareness only - NOT a diagnosis. Reference ranges may vary by laboratory.
"""
import io
import re

REFS = {
    "hgb": ("هيموغلوبين", "Hemoglobin", "g/dL", (13.5, 17.5, 12.0, 15.5)),
    "wbc": ("كريات بيضاء", "WBC", "10^9/L", (4.0, 11.0, 4.0, 11.0)),
    "rbc": ("كريات حمراء", "RBC", "10^6/uL", (4.7, 6.1, 4.2, 5.4)),
    "hct": ("الهيماتوكريت", "Hematocrit", "%", (40.0, 54.0, 36.0, 48.0)),
    "mcv": ("متوسط حجم الكرية", "MCV", "fL", (80.0, 100.0, 80.0, 100.0)),
    "mch": ("متوسط هيموغلوبين الكرية", "MCH", "pg", (27.0, 33.0, 27.0, 33.0)),
    "mchc": ("متوسط تركيز الهيموغلوبين", "MCHC", "g/dL", (32.0, 36.0, 32.0, 36.0)),
    "plt": ("الصفائح", "Platelets", "10^9/L", (150.0, 400.0, 150.0, 400.0)),
    "neut": ("العدلات", "Neutrophils", "%", (40.0, 60.0, 40.0, 60.0)),
    "lymph": ("اللمفاويات", "Lymphocytes", "%", (20.0, 40.0, 20.0, 40.0)),
    "rdw": ("RDW", "RDW", "%", (11.5, 14.5, 11.5, 14.5)),
}

SYNONYMS = {
    "hgb": ["هيموغلوبين الدم", "هيموغلوبين", "هيموجلوبين", "hemoglobin", "haemoglobin", "hgb", "هب", "hb"],
    "wbc": ["كريات بيضاء", "خلايا بيضاء", "الخلايا البيضاء", "البيضاء", "white blood cell", "white cells", "leukocytes", "leukocyte", "wbc"],
    "rbc": ["كريات حمراء", "خلايا حمراء", "الخلايا الحمراء", "الحمراء", "red blood cell", "red cells", "erythrocytes", "erythrocyte", "rbc"],
    "hct": ["الهيماتوكريت", "هيماتوكريت", "hematocrit", "packed cell", "hct", "pcv"],
    "mcv": ["متوسط حجم الكرية", "mcv"],
    "mch": ["متوسط هيموغلوبين الكرية", "متوسط الهيموغلوبين الكرية", "mch"],
    "mchc": ["متوسط تركيز الهيموغلوبين", "mchc"],
    "plt": ["الصفائح", "صفائح", "البلاتين", "platelet", "platelets", "plt"],
    "neut": ["العدلات", "عدلات", "neutrophil", "neutrophils", "neut"],
    "lymph": ["اللمفاويات", "لمفاويات", "lymphocyte", "lymphocytes", "lymph"],
    "rdw": ["توزيع الكريات الحمراء", "erythrocyte distribution width", "red cell distribution width", "rdw"],
}


# V139: common blood-test panels beyond CBC. These entries deliberately do not
# carry application-owned diagnostic ranges. When the laboratory range is not
# present in the uploaded report, the value remains unclassified instead of
# guessing a universal normal range.
EXTENDED_REFS = {
    "glucose": ("الجلوكوز", "Glucose", "mg/dL", (None, None, None, None)),
    "hba1c": ("السكر التراكمي HbA1c", "HbA1c", "%", (None, None, None, None)),
    "creatinine": ("الكرياتينين", "Creatinine", "mg/dL", (None, None, None, None)),
    "egfr": ("معدل الترشيح الكبيبي eGFR", "eGFR", "mL/min/1.73m2", (None, None, None, None)),
    "bun": ("نيتروجين اليوريا BUN", "BUN", "mg/dL", (None, None, None, None)),
    "urea": ("اليوريا", "Urea", "mg/dL", (None, None, None, None)),
    "alt": ("إنزيم ALT", "ALT", "U/L", (None, None, None, None)),
    "ast": ("إنزيم AST", "AST", "U/L", (None, None, None, None)),
    "alp": ("إنزيم ALP", "ALP", "U/L", (None, None, None, None)),
    "bilirubin": ("البيليروبين الكلي", "Total bilirubin", "mg/dL", (None, None, None, None)),
    "albumin": ("الألبومين", "Albumin", "g/dL", (None, None, None, None)),
    "total_protein": ("البروتين الكلي", "Total protein", "g/dL", (None, None, None, None)),
    "chol_total": ("الكوليسترول الكلي", "Total cholesterol", "mg/dL", (None, None, None, None)),
    "ldl": ("LDL", "LDL cholesterol", "mg/dL", (None, None, None, None)),
    "hdl": ("HDL", "HDL cholesterol", "mg/dL", (None, None, None, None)),
    "triglycerides": ("الدهون الثلاثية", "Triglycerides", "mg/dL", (None, None, None, None)),
    "sodium": ("الصوديوم", "Sodium", "mmol/L", (None, None, None, None)),
    "potassium": ("البوتاسيوم", "Potassium", "mmol/L", (None, None, None, None)),
    "chloride": ("الكلوريد", "Chloride", "mmol/L", (None, None, None, None)),
    "calcium": ("الكالسيوم", "Calcium", "mg/dL", (None, None, None, None)),
    "co2": ("ثاني أكسيد الكربون CO2", "CO2 / bicarbonate", "mmol/L", (None, None, None, None)),
    "ferritin": ("الفيريتين", "Ferritin", "ng/mL", (None, None, None, None)),
    "b12": ("فيتامين B12", "Vitamin B12", "pg/mL", (None, None, None, None)),
    "vitd": ("فيتامين D", "Vitamin D", "ng/mL", (None, None, None, None)),
    "tsh": ("هرمون TSH", "TSH", "mIU/L", (None, None, None, None)),
    "iron": ("الحديد", "Iron", "umol/L", (None, None, None, None)),
    "mpv": ("متوسط حجم الصفائح", "Mean platelet volume (MPV)", "fL", (None, None, None, None)),
    "mono": ("الوحيدات", "Monocytes", "%", (None, None, None, None)),
    "eos": ("الحمضات", "Eosinophils", "%", (None, None, None, None)),
    "baso": ("القاعديات", "Basophils", "%", (None, None, None, None)),
    "free_t4": ("هرمون Free T4", "Free T4", "ng/dL", (None, None, None, None)),
    "crp": ("البروتين المتفاعل C (CRP)", "C-reactive protein (CRP)", "mg/L", (None, None, None, None)),
    "esr": ("سرعة ترسيب الدم (ESR)", "Erythrocyte sedimentation rate (ESR)", "mm/hr", (None, None, None, None)),
    "magnesium": ("المغنيسيوم", "Magnesium", "mg/dL", (None, None, None, None)),
    "phosphate": ("الفوسفات", "Phosphate", "mg/dL", (None, None, None, None)),
    "uric_acid": ("حمض اليوريك", "Uric acid", "mg/dL", (None, None, None, None)),
    "ggt": ("إنزيم GGT", "GGT", "U/L", (None, None, None, None)),
    "lipase": ("إنزيم الليباز", "Lipase", "U/L", (None, None, None, None)),
    "folate": ("الفولات", "Folate", "ng/mL", (None, None, None, None)),
    "anc": ("العدد المطلق للعدلات (ANC)", "Absolute neutrophil count (ANC)", "10^9/L", (None, None, None, None)),
    "troponin": ("التروبونين القلبي", "Cardiac troponin", "ng/L", (None, None, None, None)),
}
REFS.update(EXTENDED_REFS)

SYNONYMS.update({
    "glucose": ["glucose", "fasting glucose", "fasting blood glucose", "blood sugar", "سكر صائم", "سكر الدم", "الجلوكوز", "جلوكوز"],
    "hba1c": ["hba1c", "hb a1c", "hemoglobin a1c", "a1c/hemoglobin", "a1c", "glycated hemoglobin", "glycosylated hemoglobin", "السكر التراكمي", "الهيموغلوبين السكري"],
    "creatinine": ["creatinine", "serum creatinine", "الكرياتينين", "كرياتينين"],
    "egfr": ["egfr", "estimated gfr", "glomerular filtration rate", "معدل الترشيح الكبيبي", "الترشيح الكبيبي"],
    "bun": ["bun", "blood urea nitrogen", "نيتروجين اليوريا"],
    "urea": ["urea", "serum urea", "اليوريا", "يوريا"],
    "alt": ["alt", "alanine aminotransferase", "sgpt", "انزيم alt", "إنزيم alt"],
    "ast": ["ast", "aspartate aminotransferase", "sgot", "انزيم ast", "إنزيم ast"],
    "alp": ["alp", "alkaline phosphatase", "الفوسفاتاز القلوي", "انزيم alp", "إنزيم alp"],
    "bilirubin": ["total bilirubin", "bilirubin total", "bilirubin", "البيليروبين الكلي", "البيليروبين"],
    "albumin": ["albumin", "الألبومين", "البومين"],
    "total_protein": ["total protein", "serum total protein", "البروتين الكلي"],
    "chol_total": ["total cholesterol", "cholesterol total", "total chol", "الكوليسترول الكلي"],
    "ldl": ["ldl cholesterol", "ldl-c", "ldl", "الكوليسترول الضار"],
    "hdl": ["hdl cholesterol", "hdl-c", "hdl", "الكوليسترول النافع"],
    "triglycerides": ["triglycerides", "triglyceride", "tg", "الدهون الثلاثية"],
    "sodium": ["sodium", "na+", "na", "الصوديوم"],
    "potassium": ["potassium", "k+", "البوتاسيوم"],
    "chloride": ["chloride", "cl-", "chloride serum", "الكلوريد"],
    "calcium": ["calcium", "ca", "الكالسيوم"],
    "co2": ["bicarbonate", "co2", "carbon dioxide", "hco3", "البيكربونات", "ثاني أكسيد الكربون"],
    "ferritin": ["ferritin", "serum ferritin", "الفيريتين", "مخزون الحديد"],
    "b12": ["vitamin b12", "b12", "cobalamin", "فيتامين b12", "فيتامين ب12"],
    "vitd": ["25-oh vitamin d", "25 hydroxy vitamin d", "vitamin d", "vit d2", "calciferol", "فيتامين d", "فيتامين د"],
    "tsh": ["tsh", "thyrotropin", "thyroid stimulating hormone", "هرمون tsh", "الهرمون المحفز للغدة الدرقية", "الهرمون المنبه للغدة الدرقية"],
    "iron": ["serum iron", "iron [mass/volume]", "iron", "الحديد"],
    "mpv": ["platelet mean volume", "mean platelet volume", "mpv", "متوسط حجم الصفائح"],
    "mono": ["monocytes/100 leukocytes", "monocyte percentage", "monocytes %", "وحيدة النوى", "مونوسايت"],
    "eos": ["eosinophils/100 leukocytes", "eosinophil percentage", "eosinophils %", "إيزينوفيل", "الخلايا الحمضية"],
    "baso": ["basophils/100 leukocytes", "basophil percentage", "basophils %", "بازوفيل", "الخلايا القاعدية"],
    "free_t4": ["free t4", "free thyroxine", "ft4", "t4 free", "ثيروكسين حر", "هرمون t4 الحر"],
    "crp": ["c-reactive protein", "c reactive protein", "crp", "البروتين المتفاعل c", "بروتين سي التفاعلي"],
    "esr": ["erythrocyte sedimentation rate", "sed rate", "esr", "سرعة الترسيب", "سرعة ترسيب الدم"],
    "magnesium": ["magnesium", "serum magnesium", "mg serum", "مغنيسيوم", "المغنيسيوم"],
    "phosphate": ["phosphate", "phosphorus", "serum phosphate", "فوسفات", "الفوسفات", "الفوسفور"],
    "uric_acid": ["uric acid", "serum urate", "urate", "حمض اليوريك", "حمض البول"],
    "ggt": ["gamma glutamyl transferase", "gamma-glutamyl transferase", "ggt", "gamma gt", "جاما جلوتاميل"],
    "lipase": ["lipase", "serum lipase", "ليباز", "انزيم الليباز", "إنزيم الليباز"],
    "folate": ["folate", "folic acid", "serum folate", "فولات", "حمض الفوليك"],
    "anc": ["absolute neutrophil count", "anc", "neutrophils absolute", "absolute neutrophils", "العدد المطلق للعدلات"],
    "troponin": ["troponin", "troponin i", "troponin t", "high sensitivity troponin", "hs troponin", "hs-troponin", "تروبونين"],
})

TEST_GROUPS = {
    "red_cells": {"hgb","rbc","hct","mcv","mch","mchc","rdw"},
    "white_cells": {"wbc","neut","lymph","mono","eos","baso","anc"},
    "platelets": {"plt","mpv"},
    "glucose": {"glucose","hba1c"},
    "kidney": {"creatinine","egfr","bun","urea","uric_acid"},
    "liver": {"alt","ast","alp","bilirubin","albumin","total_protein","ggt"},
    "lipids": {"chol_total","ldl","hdl","triglycerides"},
    "electrolytes": {"sodium","potassium","chloride","calcium","co2","magnesium","phosphate"},
    "nutrients": {"ferritin","b12","vitd","iron","folate"},
    "thyroid": {"tsh","free_t4"},
    "inflammation": {"crp","esr"},
    "pancreas": {"lipase"},
    "cardiac": {"troponin"},
}
GROUP_LABELS = {
    "red_cells": ("كريات الدم الحمراء", "Red-cell indices"),
    "white_cells": ("كريات الدم البيضاء", "White-cell indices"),
    "platelets": ("الصفائح", "Platelets"),
    "glucose": ("السكر", "Glucose"),
    "kidney": ("وظائف الكلى", "Kidney-related markers"),
    "liver": ("وظائف الكبد", "Liver-related markers"),
    "lipids": ("الدهون", "Lipids"),
    "electrolytes": ("الأملاح والمعادن", "Electrolytes & minerals"),
    "nutrients": ("الفيتامينات والمخزون", "Nutrients & stores"),
    "thyroid": ("الغدة الدرقية", "Thyroid"),
    "inflammation": ("مؤشرات الالتهاب", "Inflammation markers"),
    "pancreas": ("البنكرياس", "Pancreas"),
    "cardiac": ("مؤشرات قلبية", "Cardiac markers"),
}

def test_group(key):
    for group, keys in TEST_GROUPS.items():
        if key in keys:
            return group
    return "other"

# Production helper; the name is retained for compatibility with existing callers.
test_group.__test__ = False

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

# Emergency thresholds: (level, when value crosses).
DANGER_RULES = {
    "hgb": [("emergency", 5.0, "lt"), ("urgent", 7.0, "lt")],
    "plt": [("emergency", 10.0, "lt"), ("urgent", 20.0, "lt")],
    "wbc": [("urgent", 30.0, "gt"), ("urgent", 1.0, "lt")],
}


# V192 — interpretation context and patient-friendly explanation helpers.
# Context NEVER changes the laboratory's printed reference range. It only adds
# explanatory context and safer follow-up prompts.
_CONTEXT_FASTING_VALUES = {"unknown", "fasting", "non_fasting", "not_required"}
_CONTEXT_SENSITIVE_KEYS = {"glucose", "triglycerides", "chol_total", "ldl", "hdl", "iron"}


def normalize_analysis_context(context):
    """Return a small, bounded context object for lab interpretation.

    The app intentionally keeps this narrow: fasting status, sample time, and a
    short optional note about medicines/supplements or collection conditions.
    None of these fields are used to override the laboratory's own range.
    """
    src = context if isinstance(context, dict) else {}
    fasting = str(src.get("fasting_status") or "unknown").strip().lower()
    if fasting not in _CONTEXT_FASTING_VALUES:
        fasting = "unknown"
    sample_time = str(src.get("sample_time") or "").strip()
    if sample_time and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", sample_time):
        sample_time = ""
    notes = re.sub(r"\s+", " ", str(src.get("notes") or "")).strip()[:300]
    return {"fasting_status": fasting, "sample_time": sample_time, "notes": notes}


def build_context_notes(results, context=None, lang="ar"):
    ar = lang == "ar"
    ctx = normalize_analysis_context(context)
    present = {str(r.get("key") or "") for r in (results or [])}
    notes = []
    if present.intersection(_CONTEXT_SENSITIVE_KEYS):
        fasting = ctx.get("fasting_status")
        if fasting == "fasting":
            notes.append("ذكرت أن العينة أُخذت أثناء الصيام. يبقى التفسير مبنيًا على نطاق مختبرك ونوع الفحص." if ar else "You reported that the sample was taken while fasting. Interpretation still follows your laboratory range and the specific test.")
        elif fasting == "non_fasting":
            notes.append("ذكرت أن العينة لم تكن أثناء الصيام. بعض مؤشرات السكر والدهون والحديد قد تتأثر بتوقيت الطعام؛ لا نغيّر تصنيف المختبر بسبب ذلك، لكن نعرضه كسياق للطبيب." if ar else "You reported that the sample was not fasting. Some glucose, lipid, and iron-related values can be affected by meal timing; this does not override the lab classification, but it is useful clinical context.")
        elif fasting == "unknown":
            notes.append("حالة الصيام غير محددة. إذا كان المختبر طلب صيامًا لهذا الفحص، أخبر الطبيب عند تفسير النتيجة." if ar else "Fasting status is unknown. If the laboratory required fasting for this test, mention that when discussing the result with your clinician.")
    if ctx.get("sample_time") and present.intersection(_CONTEXT_SENSITIVE_KEYS):
        notes.append(("وقت سحب العينة المسجل: %s. بعض القيم قد تتأثر بتوقيت السحب، لذلك يُعرض الوقت كسياق فقط." if ar else "Recorded sample time: %s. Some values may vary with collection timing, so the time is shown as context only.") % ctx["sample_time"])
    if ctx.get("notes"):
        notes.append(("ملاحظة المستخدم عن ظروف الفحص/الأدوية أو المكملات: " if ar else "User note about test conditions, medicines, or supplements: ") + ctx["notes"])
    return notes[:4]


# Common examples of factors that can be associated with an out-of-range lab
# result. These are deliberately framed as possibilities, not diagnoses.
_POSSIBLE_FACTORS_AR = {
    "hgb": {"low": ["نقص الحديد أو B12 أو الفولات", "فقدان الدم", "أمراض أو التهابات مزمنة"], "high": ["الجفاف", "التدخين أو الارتفاعات العالية", "زيادة إنتاج كريات الدم لأسباب متعددة"]},
    "mcv": {"low": ["نقص الحديد", "بعض اضطرابات الهيموغلوبين الوراثية"], "high": ["نقص B12 أو الفولات", "بعض الأدوية", "اضطرابات الكبد أو الغدة الدرقية ضمن أسباب أخرى"]},
    "wbc": {"low": ["بعض العدوى الفيروسية", "بعض الأدوية أو العلاجات", "اضطرابات نخاع العظم ضمن أسباب أخرى"], "high": ["عدوى أو التهاب", "الإجهاد الجسدي", "بعض الأدوية مثل الستيرويدات"]},
    "plt": {"low": ["عدوى أو أسباب مناعية", "بعض الأدوية", "انخفاض إنتاج الصفائح أو زيادة استهلاكها"], "high": ["التهاب أو عدوى", "نقص الحديد", "استجابة بعد نزف أو أسباب أخرى"]},
    "glucose": {"low": ["قلة الطعام أو الصيام الطويل", "أدوية خفض السكر", "مجهود أو أسباب صحية أخرى"], "high": ["وجبة قريبة من وقت الفحص", "السكري أو اضطراب تحمل الجلوكوز", "المرض الحاد أو بعض الأدوية"]},
    "hba1c": {"low": ["قصر عمر كريات الدم أو فقدان دم حديث", "عوامل تؤثر في دقة HbA1c"], "high": ["ارتفاع متوسط السكر خلال الأشهر السابقة", "بعض الحالات التي تؤثر في كريات الدم قد تغيّر دقة القراءة"]},
    "creatinine": {"low": ["كتلة عضلية منخفضة", "الحمل أو عوامل فردية ضمن أسباب أخرى"], "high": ["الجفاف", "انخفاض ترشيح الكلى", "كتلة عضلية/مجهود شديد أو بعض الأدوية"]},
    "egfr": {"low": ["انخفاض مؤقت أو مزمن في ترشيح الكلى", "الجفاف أو المرض الحاد قد يؤثران على الكرياتينين المستخدم بالحساب"], "high": ["قد يعكس عوامل حسابية أو فردية؛ يُفسر مع الكرياتينين والسياق"]},
    "alt": {"high": ["التهاب أو إجهاد خلايا الكبد", "بعض الأدوية أو المكملات", "الكبد الدهني أو أسباب أخرى"]},
    "ast": {"high": ["الكبد", "العضلات أو مجهود شديد", "بعض الأدوية أو أسباب أخرى"]},
    "alp": {"high": ["القنوات الصفراوية أو الكبد", "العظام", "الحمل أو النمو بحسب العمر والسياق"]},
    "bilirubin": {"high": ["زيادة تكسّر كريات الدم", "اضطراب معالجة البيليروبين بالكبد", "مشكلات تدفق الصفراء ضمن أسباب أخرى"]},
    "albumin": {"low": ["قلة المدخول أو سوء الامتصاص", "التهاب أو مرض مزمن", "الكبد أو فقد البروتين عن طريق الكلى ضمن أسباب أخرى"]},
    "ldl": {"high": ["النمط الغذائي والوراثة", "قلة النشاط أو عوامل استقلابية", "بعض الحالات الصحية أو الأدوية"]},
    "triglycerides": {"high": ["وجبة قريبة أو عدم الصيام إذا كان مطلوبًا", "السكريات المضافة والكحول", "السكري أو عوامل استقلابية وأدوية معينة"]},
    "sodium": {"low": ["تغير توازن السوائل", "القيء/الإسهال", "بعض الأدوية أو اضطرابات هرمونية/كلوية"], "high": ["الجفاف أو فقد الماء", "اضطراب توازن السوائل أو أسباب أخرى"]},
    "potassium": {"low": ["القيء أو الإسهال", "مدرات البول أو أدوية أخرى", "فقد البوتاسيوم لأسباب أخرى"], "high": ["وظائف الكلى", "بعض الأدوية", "أحيانًا مشكلة في العينة نفسها مثل تحلل الدم"]},
    "calcium": {"low": ["الألبومين المنخفض", "فيتامين D أو هرمونات الغدد جارات الدرقية", "الكلى أو أسباب أخرى"], "high": ["الجفاف", "اضطرابات جارات الدرقية", "أدوية أو أسباب أخرى"]},
    "ferritin": {"low": ["نقص مخزون الحديد", "فقد الدم", "احتياج زائد أو مدخول/امتصاص غير كافٍ"], "high": ["التهاب أو عدوى", "أمراض الكبد", "زيادة مخزون الحديد ضمن أسباب أخرى"]},
    "iron": {"low": ["نقص الحديد", "التهاب", "اختلاف توقيت السحب أو الطعام"], "high": ["مكملات الحديد أو توقيت السحب", "زيادة الحديد أو أسباب كبدية ضمن أسباب أخرى"]},
    "b12": {"low": ["مدخول غذائي منخفض", "سوء الامتصاص", "بعض الأدوية أو أمراض الجهاز الهضمي"]},
    "vitd": {"low": ["قلة التعرض للشمس", "مدخول غذائي منخفض", "سوء الامتصاص أو عوامل فردية"]},
    "tsh": {"low": ["زيادة نشاط الغدة أو تأثير دواء الغدة", "مرض حاد أو عوامل أخرى"], "high": ["قصور الغدة الدرقية", "جرعة دواء غير كافية إن كان مستخدمًا", "عوامل مناعية أو أخرى"]},
    "free_t4": {"low": ["قصور الغدة أو اضطرابات تنظيمية", "مرض حاد أو بعض الأدوية"], "high": ["زيادة نشاط الغدة", "جرعة زائدة من هرمون الغدة أو عوامل أخرى"]},
    "crp": {"high": ["التهاب أو عدوى", "إصابة أو جراحة حديثة", "حالات التهابية متعددة"]},
    "esr": {"high": ["التهاب أو عدوى", "فقر الدم", "العمر أو الحمل وعوامل أخرى"]},
    "uric_acid": {"high": ["الجفاف", "النظام الغذائي/الكحول", "وظائف الكلى أو بعض الأدوية"]},
    "ggt": {"high": ["الكبد أو القنوات الصفراوية", "الكحول", "بعض الأدوية"]},
    "lipase": {"high": ["التهاب البنكرياس ضمن أسباب محتملة", "أسباب هضمية أو كلوية وأدوية أخرى"]},
    "folate": {"low": ["مدخول غذائي منخفض", "سوء الامتصاص", "احتياج زائد أو بعض الأدوية"]},
    "anc": {"low": ["عدوى فيروسية", "بعض الأدوية أو العلاجات", "أسباب مناعية أو نخاعية أخرى"], "high": ["عدوى أو التهاب", "إجهاد جسدي", "بعض الأدوية"]},
    "troponin": {"high": ["أذية عضلة القلب لها أسباب متعددة", "توقيت السحب ونوع فحص التروبونين مهمان", "يُفسر دائمًا مع الأعراض وتخطيط القلب والسياق السريري"]},
}

_POSSIBLE_FACTORS_EN = {
    "hgb": {"low": ["iron, B12, or folate deficiency", "blood loss", "chronic illness or inflammation"], "high": ["dehydration", "smoking or high altitude", "increased red-cell production from several possible causes"]},
    "wbc": {"low": ["some viral infections", "certain medicines or treatments", "bone-marrow conditions among other causes"], "high": ["infection or inflammation", "physical stress", "certain medicines such as steroids"]},
    "plt": {"low": ["infection or immune causes", "certain medicines", "reduced production or increased platelet consumption"], "high": ["inflammation or infection", "iron deficiency", "recovery after bleeding or other causes"]},
    "glucose": {"low": ["low food intake or prolonged fasting", "glucose-lowering medicines", "exercise or other health factors"], "high": ["a recent meal", "diabetes or impaired glucose regulation", "acute illness or certain medicines"]},
    "creatinine": {"low": ["lower muscle mass", "pregnancy or individual factors"], "high": ["dehydration", "reduced kidney filtration", "muscle mass/exertion or some medicines"]},
    "ferritin": {"low": ["low iron stores", "blood loss", "increased need or inadequate intake/absorption"], "high": ["inflammation or infection", "liver conditions", "increased iron stores among other causes"]},
    "iron": {"low": ["iron deficiency", "inflammation", "collection timing or food intake"], "high": ["iron supplements or collection timing", "iron excess or liver-related causes among others"]},
    "tsh": {"low": ["thyroid overactivity or thyroid-medicine effect", "acute illness or other factors"], "high": ["thyroid underactivity", "insufficient replacement dose if used", "autoimmune or other causes"]},
    "troponin": {"high": ["heart-muscle injury has multiple possible causes", "timing and the specific troponin assay matter", "interpretation requires symptoms, ECG, and clinical context"]},
}

_GROUP_FACTORS_AR = {
    "red_cells": ["التغذية ومخزون الحديد/B12/الفولات", "فقد الدم أو الجفاف", "أمراض مزمنة أو عوامل وراثية بحسب المؤشر"],
    "white_cells": ["عدوى أو التهاب", "أدوية أو إجهاد جسدي", "عوامل مناعية أو نخاعية ضمن أسباب أخرى"],
    "platelets": ["عدوى أو التهاب", "أدوية أو عوامل مناعية", "تغير إنتاج/استهلاك الصفائح"],
    "kidney": ["حالة السوائل والجفاف", "وظائف الكلى", "العمر والكتلة العضلية وبعض الأدوية بحسب المؤشر"],
    "liver": ["الكبد أو القنوات الصفراوية", "الأدوية والمكملات", "المرض الحاد أو عوامل أخرى بحسب المؤشر"],
    "lipids": ["النمط الغذائي", "الوراثة والنشاط والوزن", "السكري أو بعض الأدوية والحالات الصحية"],
    "electrolytes": ["توازن السوائل", "الكلى", "القيء/الإسهال وبعض الأدوية أو الهرمونات"],
    "nutrients": ["المدخول الغذائي", "الامتصاص", "المكملات أو الالتهاب بحسب المؤشر"],
    "thyroid": ["وظيفة الغدة الدرقية", "أدوية الغدة", "المرض الحاد وعوامل فردية"],
    "inflammation": ["عدوى", "التهاب", "إصابة أو مرض حديث؛ هذه المؤشرات غير نوعية وحدها"],
    "pancreas": ["البنكرياس", "أمراض هضمية أو كلوية", "بعض الأدوية ضمن أسباب أخرى"],
    "cardiac": ["أذية عضلة القلب لها أسباب متعددة", "نوع الفحص وتوقيت السحب", "الأعراض وتخطيط القلب والسياق السريري"],
}

_GROUP_FACTORS_EN = {
    "red_cells": ["nutrition and iron/B12/folate stores", "blood loss or hydration", "chronic or inherited factors depending on the marker"],
    "white_cells": ["infection or inflammation", "medicines or physical stress", "immune or marrow-related factors among other causes"],
    "platelets": ["infection or inflammation", "medicines or immune factors", "changes in platelet production/consumption"],
    "kidney": ["hydration status", "kidney filtration", "age, muscle mass, and some medicines depending on the marker"],
    "liver": ["liver or bile-duct factors", "medicines and supplements", "acute illness or other marker-specific factors"],
    "lipids": ["dietary pattern", "genetics, activity, and weight", "diabetes, some medicines, or other health conditions"],
    "electrolytes": ["fluid balance", "kidney function", "vomiting/diarrhea, medicines, or hormonal factors"],
    "nutrients": ["dietary intake", "absorption", "supplements or inflammation depending on the marker"],
    "thyroid": ["thyroid function", "thyroid medicines", "acute illness and individual factors"],
    "inflammation": ["infection", "inflammation", "recent injury/illness; these markers are non-specific by themselves"],
    "pancreas": ["pancreatic factors", "gastrointestinal or kidney conditions", "some medicines among other causes"],
    "cardiac": ["heart-muscle injury has multiple causes", "assay type and sample timing", "symptoms, ECG, and clinical context"],
}


def possible_factors_for_result(key, status, lang="ar"):
    if status not in {"low", "high"}:
        return []
    ar = lang == "ar"
    key = str(key or "")
    specific = (_POSSIBLE_FACTORS_AR if ar else _POSSIBLE_FACTORS_EN).get(key, {}).get(status)
    if specific:
        return list(specific)[:4]
    group = test_group(key)
    return list((_GROUP_FACTORS_AR if ar else _GROUP_FACTORS_EN).get(group, []))[:4]


def possible_factors_note(lang="ar"):
    return ("أمثلة عامة قد ترتبط بهذه النتيجة وليست تشخيصًا أو قائمة كاملة؛ يحدد الطبيب الاحتمالات المناسبة من التاريخ المرضي والأعراض وبقية الفحوص." if lang == "ar" else
            "These are general examples that may be associated with the result, not a diagnosis or complete list. A clinician narrows the possibilities using history, symptoms, and other tests.")


def attention_level_for_result(result):
    """Return a display triage level without inventing test-specific cutoffs."""
    r = result or {}
    if r.get("verification_level") == "needs_review" or r.get("status") == "unclassified":
        return "needs_confirmation"
    if r.get("reported_critical"):
        return "urgent"
    key = str(r.get("key") or "")
    try:
        value = float(r.get("canonical_value")) if r.get("canonical_value") is not None else None
    except (TypeError, ValueError):
        value = None
    if value is not None and key in DANGER_RULES:
        for lvl, threshold, op in DANGER_RULES[key]:
            crossed = value < threshold if op == "lt" else value > threshold
            if crossed:
                return lvl
    if r.get("status") in {"low", "high"}:
        return "out_of_range"
    return "normal"


def _norm(text):
    return re.sub(r"\s+", " ", str(text)).translate(_AR_DIGITS).lower()

def _find_synonym(text, synonym):
    """Return a safe match index for an analyte synonym.

    Short Latin labels such as HB, Na and TG must match whole tokens; plain
    substring matching would misread HbA1c as hemoglobin (HB). Arabic phrases
    and longer free-text synonyms keep phrase matching.
    """
    line = _norm(text)
    syn = _norm(synonym)
    if not syn:
        return -1
    if re.fullmatch(r"[a-z0-9][a-z0-9+._/-]*", syn, flags=re.I):
        m = re.search(r"(?<![a-z0-9])" + re.escape(syn) + r"(?![a-z0-9])", line, flags=re.I)
        return m.start() if m else -1
    return line.find(syn)


def _normalize_unit(unit):
    raw = str(unit or "").strip().lower().replace(" ", "")
    # Normalize symbols commonly emitted by laboratory PDFs/OCR.  1 mm³ is
    # exactly 1 µL, so x10^n/mm3 and x10^n/µL are equivalent count units.
    raw = raw.replace("×", "x").replace("μ", "u").replace("µ", "u")
    raw = raw.translate(str.maketrans({"⁰":"0","¹":"1","²":"2","³":"3","⁴":"4","⁵":"5","⁶":"6","⁷":"7","⁸":"8","⁹":"9"}))
    raw = raw.replace("^", "")
    if raw.startswith("x10"):
        raw = raw[1:]
    aliases = {
        "g/dl": "g/dL", "gdl": "g/dL", "g/l": "g/L", "gl": "g/L",
        "%": "%", "percent": "%", "l/l": "L/L", "ll": "L/L",
        "fl": "fL", "pg": "pg",
        "10*9/l": "10^9/L", "10x9/l": "10^9/L", "109/l": "10^9/L", "10e9/l": "10^9/L",
        "10*12/l": "10^12/L", "10x12/l": "10^12/L", "1012/l": "10^12/L", "10e12/l": "10^12/L",
        "10*6/ul": "10^6/uL", "10x6/ul": "10^6/uL", "106/ul": "10^6/uL", "10e6/ul": "10^6/uL",
        "10*3/ul": "10^3/uL", "10x3/ul": "10^3/uL", "103/ul": "10^3/uL", "10e3/ul": "10^3/uL",
        "10*6/mm3": "10^6/uL", "10x6/mm3": "10^6/uL", "106/mm3": "10^6/uL",
        "10*3/mm3": "10^3/uL", "10x3/mm3": "10^3/uL", "103/mm3": "10^3/uL",
        "k/ul": "10^3/uL", "k/ul.": "10^3/uL", "thousand/ul": "10^3/uL",
        "m/ul": "10^6/uL", "million/ul": "10^6/uL",
        "mg/dl": "mg/dL", "mgdl": "mg/dL", "mg/l": "mg/L",
        "mmol/l": "mmol/L", "mmoll": "mmol/L",
        "umol/l": "umol/L", "umoll": "umol/L",
        "u/l": "U/L", "iu/l": "U/L", "unit/l": "U/L",
        "ng/ml": "ng/mL", "ngml": "ng/mL", "ng/dl": "ng/dL", "ngdl": "ng/dL", "ng/l": "ng/L", "ngl": "ng/L", "pg/ml": "pg/mL", "pgml": "pg/mL",
        "nmol/l": "nmol/L", "nmoll": "nmol/L", "pmol/l": "pmol/L", "pmoll": "pmol/L",
        "ug/l": "ug/L", "ug/liter": "ug/L", "mcg/l": "ug/L",
        "miu/l": "mIU/L", "mui/l": "mIU/L", "uiu/ml": "mIU/L",
        "mm/hr": "mm/hr", "mm/h": "mm/hr", "mmhour": "mm/hr",
        "ml/min/1.73m2": "mL/min/1.73m2", "ml/min/1.73m²": "mL/min/1.73m2",
    }
    # Unknown OCR/model-provided units are intentionally discarded rather than
    # echoed back. CBC classification may still use a laboratory-provided numeric
    # reference range, but unsupported units are never trusted for conversion or
    # presentation.
    return aliases.get(raw, "")


def _convert_value(key, value, unit):
    """Convert a value to the canonical unit used by REFS.

    Returns (converted_value, canonical_unit) or (None, None) when the unit is
    unknown/ambiguous. No guessing is performed for differential percentages.
    """
    unit = _normalize_unit(unit)
    value = float(value)
    if key == "hgb":
        if unit == "g/dL": return value, "g/dL"
        if unit == "g/L": return value / 10.0, "g/dL"
    elif key == "hct":
        if unit == "%": return value, "%"
        if unit == "L/L": return value * 100.0, "%"
    elif key == "mchc":
        if unit == "g/dL": return value, "g/dL"
        if unit == "g/L": return value / 10.0, "g/dL"
    elif key == "rbc":
        if unit in {"10^6/uL", "10^12/L"}: return value, "10^6/uL"
    elif key in {"wbc", "plt"}:
        if unit in {"10^9/L", "10^3/uL"}: return value, "10^9/L"
    elif key in {"neut", "lymph", "rdw"}:
        if unit == "%": return value, "%"
    elif key == "mcv" and unit == "fL":
        return value, "fL"
    elif key == "mch" and unit == "pg":
        return value, "pg"
    return None, None


def _plausible_default_unit(key, value):
    """Legacy/manual entry compatibility without silently misreading units."""
    value = float(value)
    if key == "hgb" and 2 <= value <= 30: return "g/dL"
    if key == "hct" and 5 <= value <= 80: return "%"
    if key == "rbc" and 1 <= value <= 10: return "10^6/uL"
    if key == "wbc" and 0.1 <= value <= 100: return "10^9/L"
    if key == "plt" and 1 <= value <= 1500: return "10^9/L"
    if key == "mcv" and 30 <= value <= 150: return "fL"
    if key == "mch" and 10 <= value <= 60: return "pg"
    if key == "mchc" and 15 <= value <= 50: return "g/dL"
    if key == "rdw" and 5 <= value <= 40: return "%"
    # Neutrophils/lymphocytes without a unit are ambiguous (% vs absolute).
    return None


def _parse_age_years(text):
    """Parse an age mentioned in years/months/weeks/days and return years.

    OCR/lab reports often show pediatric ages as e.g. ``18 months``. Treating
    that as 18 years can select the wrong adult fallback reference range, so
    the unit is preserved long enough to convert it safely.
    """
    t = _norm(text)
    age_re = re.compile(
        r"(?:العمر|(?<![a-z])age(?![a-z])|طفل|طفلة|(?<![a-z])child(?![a-z]))\s*[:=]?\s*"
        r"(\d+(?:[.,]\d+)?)\s*"
        r"(سن(?:ة|وات)?|عام|أعوام|اعوام|years?|yrs?|yr|y|"
        r"شهر|أشهر|اشهر|months?|mos?|mo|"
        r"أسبوع|اسبوع|أسابيع|اسابيع|weeks?|wks?|wk|"
        r"يوم|أيام|ايام|days?|day)?\b",
        re.I,
    )
    m = age_re.search(t)
    if not m:
        return None
    try:
        value = float(m.group(1).replace(",", "."))
    except (TypeError, ValueError):
        return None
    unit = (m.group(2) or "").strip().lower()
    if unit in {"شهر", "أشهر", "اشهر", "month", "months", "mo", "mos"}:
        years = value / 12.0
    elif unit in {"أسبوع", "اسبوع", "أسابيع", "اسابيع", "week", "weeks", "wk", "wks"}:
        years = value / 52.1429
    elif unit in {"يوم", "أيام", "ايام", "day", "days"}:
        years = value / 365.25
    else:
        # The CBC UI asks for years and the vision prompt emits an age unit when
        # it is visible. If a legacy OCR response says only "Child 7", years is
        # the least surprising backwards-compatible interpretation.
        years = value
    if years < 0 or years > 130:
        return None
    return int(years) if float(years).is_integer() else round(years, 3)



def _looks_like_simple_range(line):
    """Return (low, high) only for an unambiguous numeric lab range line."""
    x = _norm(line).strip()
    m = re.fullmatch(r"\s*([-+]?\d*\.?\d+)\s*(?:-|–|—|to)\s*([-+]?\d*\.?\d+)\s*", x, re.I)
    if not m:
        return None, None
    try:
        lo = float(m.group(1)); hi = float(m.group(2))
    except (TypeError, ValueError):
        return None, None
    if lo > hi:
        lo, hi = hi, lo
    return lo, hi


def _result_line_parts(line):
    """Parse the result cell emitted by text-based laboratory PDFs."""
    raw = str(line or "").strip().translate(_AR_DIGITS)
    m = re.match(r"^\s*([-+]?\d+(?:[.,]\d+)?)\s*(.*)$", raw)
    if not m:
        return None, ""
    try:
        value = float(m.group(1).replace(",", "."))
    except (TypeError, ValueError):
        return None, ""
    tail = m.group(2).strip()
    unit_match = re.search(
        r"(?:g\s*/\s*d[lL]|g\s*/\s*[lL]|mg\s*/\s*d[lL]|mg\s*/\s*[lL]|mmol\s*/\s*[lL]|(?:u|µ|μ)mol\s*/\s*[lL]|nmol\s*/\s*[lL]|pmol\s*/\s*[lL]|[iI]?[uU]\s*/\s*[lL]|ng\s*/\s*m[lL]|pg\s*/\s*m[lL]|(?:u|µ|μ)g\s*/\s*[lL]|m[iI][uU]\s*/\s*[lL]|%|f[lL]|pg)",
        tail, re.I,
    )
    return value, (_normalize_unit(unit_match.group(0)) if unit_match else "")


def _key_from_test_name(name_text, unit=""):
    """Map a table's test-name cell to one supported marker.

    Differential absolute counts and percentages share names. For the current
    educational model, neutrophils/lymphocytes/mono/eos/baso are percentage
    markers, so prefer rows whose result unit is %.
    """
    text = _norm(name_text)
    # "Granulocytes/100 leukocytes" and other differential rows contain the
    # word leukocytes as a denominator; they are not the WBC count itself.
    wbc_denominator_only = bool(re.search(r"/\s*100\s+leukocytes", text))
    candidates = []
    for key, syns in SYNONYMS.items():
        for syn in sorted(syns, key=len, reverse=True):
            if _find_synonym(text, syn) >= 0:
                candidates.append((len(_norm(syn)), key))
                break
    if not candidates:
        return None
    candidates.sort(reverse=True)
    for _, key in candidates:
        if key == "wbc" and wbc_denominator_only:
            continue
        if key in {"neut", "lymph", "mono", "eos", "baso"} and unit != "%":
            continue
        return key
    return None


def _parse_native_lab_table(raw_text):
    """Parse native PDF table text where columns are emitted vertically.

    Common lab PDFs expose rows as: REFERENCE RANGE -> INTERPRETATION -> RESULT
    -> TEST NAME. The older generic parser searched only *after* the test name,
    so it missed values that appear before it and could then latch onto unrelated
    numbers such as '/100 leukocytes'. This parser reconstructs those rows first.
    """
    lines = [str(x).strip() for x in re.split(r"[\r\n]+", str(raw_text or "")) if str(x).strip()]
    rows = []
    seen = {}
    interp_words = {"normal", "low", "high", "critical", "abnormal", "طبيعي", "منخفض", "منخفضة", "مرتفع", "مرتفعة"}
    stop_markers = {"reference range", "interpretation", "result", "test name", "المدى الطبيعي", "التصنيف", "النتيجة", "اسم الفحص"}
    i = 0
    while i < len(lines) - 2:
        low_line = _norm(lines[i])
        # A row anchor is usually either an unambiguous numeric range or a
        # categorical range line (e.g. HbA1c/Vitamin D). In both cases the next
        # standalone line is the lab interpretation and the following line is
        # the numeric result.
        lo, hi = _looks_like_simple_range(lines[i])
        possible_category_range = bool(re.search(r"(?:normal|deficien|insufficien|sufficien|prediabetes|diabetes|male\s*:|female\s*:)", low_line, re.I))
        j = i + 1
        # Some categorical ranges span more than one line. Look ahead a little
        # for the interpretation cell but do not cross into another header.
        found_interp = None
        for cand in range(j, min(len(lines), i + 5)):
            if _norm(lines[cand]) in interp_words:
                found_interp = cand
                break
            if _norm(lines[cand]) in stop_markers:
                break
        if (lo is None and not possible_category_range) or found_interp is None:
            i += 1; continue
        result_idx = found_interp + 1
        if result_idx >= len(lines):
            break
        value, unit = _result_line_parts(lines[result_idx])
        if value is None:
            i += 1; continue
        # Test name continues until the next obvious row/header or Arabic mirror.
        name_parts = []
        k = result_idx + 1
        while k < len(lines) and len(name_parts) < 4:
            normk = _norm(lines[k])
            if normk in stop_markers or normk in interp_words:
                break
            next_lo, next_hi = _looks_like_simple_range(lines[k])
            if next_lo is not None and name_parts:
                break
            if re.match(r"^(?:version:|printed date:|page\s+\d+\s+of\s+\d+)", normk):
                break
            # Native PDFs often duplicate the table in Arabic after all English
            # rows. Stop before those mirrored labels when we already have a name.
            if name_parts and re.search(r"[\u0600-\u06FF]", lines[k]):
                break
            name_parts.append(lines[k])
            k += 1
        name_text = " ".join(name_parts)
        key = _key_from_test_name(name_text, unit)
        if key:
            entry = {"key": key, "value": value, "unit": unit, "reference_low": lo, "reference_high": hi}
            # Prefer the percentage differential row over an absolute-count row,
            # and prefer rows carrying a clear laboratory reference range.
            score = (2 if lo is not None and hi is not None else 0) + (1 if unit else 0)
            prev = seen.get(key)
            if prev is None or score > prev[0]:
                seen[key] = (score, entry)
        i = max(i + 1, result_idx)
    for key in REFS:
        if key in seen:
            rows.append(seen[key][1])
    return rows

def _parse_blood_text_v142(text):
    """Extract CBC value + unit + laboratory reference range when available.

    Entries are dictionaries with ``key``, ``value``, ``unit``,
    ``reference_low`` and ``reference_high``. ``analyze_blood`` still accepts
    legacy ``(key, value)`` tuples for backwards compatibility.
    """
    if not text:
        return [], None
    raw_text = str(text).translate(_AR_DIGITS)
    t = _norm(raw_text)
    age = _parse_age_years(t)

    entries = _parse_native_lab_table(raw_text)
    occupied = {e.get("key") for e in entries if isinstance(e, dict) and e.get("key")}
    # Preserve original line boundaries. `_norm` intentionally collapses
    # whitespace, so normalizing the entire report before splitting would merge
    # neighboring analytes and can attach the wrong reference range.
    lines = [_norm(ln) for ln in re.split(r"[\r\n]+", raw_text) if ln.strip()]
    for key, syns in SYNONYMS.items():
        best = None
        if key in occupied:
            continue
        for line in lines:
            for syn in sorted(syns, key=len, reverse=True):
                idx = _find_synonym(line, syn)
                if idx < 0:
                    continue
                # Preferred OCR format: TEST | VALUE | UNIT | REF_LOW | REF_HIGH
                parts = [part.strip() for part in line.split("|")]
                if len(parts) >= 2 and _find_synonym(parts[0], syn) >= 0:
                    try:
                        value = float(parts[1].replace(",", "."))
                    except (TypeError, ValueError):
                        value = None
                    if value is not None:
                        unit = _normalize_unit(parts[2]) if len(parts) > 2 else ""
                        try: lo = float(parts[3].replace(",", ".")) if len(parts) > 3 and parts[3] else None
                        except (TypeError, ValueError): lo = None
                        try: hi = float(parts[4].replace(",", ".")) if len(parts) > 4 and parts[4] else None
                        except (TypeError, ValueError): hi = None
                        best = {"key": key, "value": value, "unit": unit, "reference_low": lo, "reference_high": hi}
                        break
                after = line[idx + len(_norm(syn)):].strip(" :|=-")
                nums = re.findall(r"[-+]?\d+(?:[.,]\d+)?", after)
                if not nums:
                    continue
                value = float(nums[0].replace(",", "."))
                # Avoid false positives from test-name text such as
                # "lymphocytes/100 leukocytes" or "Vitamin B12".
                if key in {"neut", "lymph", "mono", "eos", "baso"} and value == 100 and "%" not in after:
                    continue
                if key == "b12" and value == 12 and not re.search(r"\b(?:pmol|pg|ng|ug|µg|μg)\b", after, re.I):
                    continue
                unit_match = re.search(
                    r"(?:g\s*/\s*d[lL]|g\s*/\s*[lL]|mg\s*/\s*d[lL]|mg\s*/\s*[lL]|mmol\s*/\s*[lL]|(?:u|µ|μ)mol\s*/\s*[lL]|nmol\s*/\s*[lL]|pmol\s*/\s*[lL]|[iI]?[uU]\s*/\s*[lL]|ng\s*/\s*m[lL]|pg\s*/\s*m[lL]|(?:u|µ|μ)g\s*/\s*[lL]|m[iI][uU]\s*/\s*[lL]|m[lL]\s*/\s*min\s*/\s*1[.]73\s*m(?:2|²)|%|[lL]\s*/\s*[lL]|f[lL]|pg|"
                    r"(?:[x×]\s*)?10\s*(?:\^|x|\*)?\s*(?:3|6|9|12|³|⁶|⁹|¹²)\s*/\s*(?:u[lL]|µ[lL]|μ[lL]|[lL]|mm(?:3|³))|"
                    r"[kKmM]\s*/\s*(?:u[lL]|µ[lL]|μ[lL]))",
                    after, re.I,
                )
                unit = _normalize_unit(unit_match.group(0)) if unit_match else ""
                range_match = re.search(r"(?:ref(?:erence)?(?:\s*range)?|range|المرجع|الطبيعي)?\s*[:=]?\s*([-+]?\d+(?:[.,]\d+)?)\s*(?:-|–|—|to)\s*([-+]?\d+(?:[.,]\d+)?)", after[len(nums[0]):], re.I)
                lo = hi = None
                if range_match:
                    lo = float(range_match.group(1).replace(",", ".")); hi = float(range_match.group(2).replace(",", "."))
                best = {"key": key, "value": value, "unit": unit, "reference_low": lo, "reference_high": hi}
                break
            if best:
                break
        if best and key not in occupied:
            occupied.add(key); entries.append(best)
    return entries, age


def _entry_dict(entry):
    if isinstance(entry, dict):
        return dict(entry)
    if isinstance(entry, (tuple, list)) and len(entry) >= 2:
        return {"key": entry[0], "value": entry[1], "unit": "", "reference_low": None, "reference_high": None}
    return {}


def _gender_key(gender):
    value = str(gender or "").strip().lower()
    if value in {"m", "male", "ذكر"}:
        return "m"
    if value in {"f", "female", "أنثى", "انثى"}:
        return "f"
    if value in {"c", "child", "pediatric", "paediatric", "طفل", "طفلة"}:
        return "child"
    return "unknown"


def _adult_reference_bounds(key, gender_key):
    """Return an adult fallback range only when it is safe to choose one."""
    _ar, _en, _unit, (lm, hm, lf, hf) = REFS[key]
    if gender_key == "m":
        return lm, hm
    if gender_key == "f":
        return lf, hf
    # Some CBC reference ranges in this simplified educational fallback are the
    # same for both sexes. Those can still be used if sex is not specified.
    if lm == lf and hm == hf:
        return lm, hm
    return None, None


def _analyze_blood_v142_base(entries, gender="", age=None):
    """Classify CBC values safely.

    Priority: laboratory range from the report -> trusted unit conversion and
    application adult range -> unclassified. Pediatric results are never judged
    with adult application ranges when the report does not provide its own range.
    Sex-specific adult fallbacks are not used when sex is unknown.
    """
    gender_key = _gender_key(gender)
    try:
        age_years = float(age) if age not in (None, "") else None
    except (TypeError, ValueError):
        age_years = None
    is_child = gender_key == "child" or (age_years is not None and age_years < 18)
    is_adult = gender_key != "child" and age_years is not None and age_years >= 18
    results = []
    for raw in entries:
        e = _entry_dict(raw)
        key = str(e.get("key") or "").lower()
        if key not in REFS:
            continue
        try:
            raw_value = float(e.get("value"))
        except (TypeError, ValueError):
            continue
        name_ar, name_en, default_unit, (lm, hm, lf, hf) = REFS[key]
        input_unit = _normalize_unit(e.get("unit"))
        ref_low = e.get("reference_low"); ref_high = e.get("reference_high")
        try: ref_low = float(ref_low) if ref_low not in (None, "") else None
        except (TypeError, ValueError): ref_low = None
        try: ref_high = float(ref_high) if ref_high not in (None, "") else None
        except (TypeError, ValueError): ref_high = None

        status = "unclassified"
        source = "unclassified"
        display_value = raw_value
        display_unit = input_unit or ""
        low = high = None
        canonical_value = canonical_unit = None

        # Lab-provided range wins and stays in the lab's own scale/unit.
        if ref_low is not None and ref_high is not None and ref_low <= ref_high:
            low, high = ref_low, ref_high
            status = "low" if raw_value < low else "high" if raw_value > high else "normal"
            source = "lab_reference"
            if input_unit:
                canonical_value, canonical_unit = _convert_value(key, raw_value, input_unit)
        elif is_adult:
            unit_for_conversion = input_unit or _plausible_default_unit(key, raw_value)
            if unit_for_conversion:
                converted, canon = _convert_value(key, raw_value, unit_for_conversion)
                low, high = _adult_reference_bounds(key, gender_key)
                if converted is not None and low is not None and high is not None:
                    canonical_value, canonical_unit = converted, canon
                    display_value = converted; display_unit = canon
                    status = "low" if converted < low else "high" if converted > high else "normal"
                    source = "app_adult_reference"
                elif converted is not None:
                    # Keep a canonical value for safety checks, but do not label
                    # a sex-specific analyte high/low without a known sex.
                    canonical_value, canonical_unit = converted, canon
                    display_value = converted; display_unit = canon

        results.append({
            "key": key, "name_ar": name_ar, "name_en": name_en,
            "unit": display_unit, "value": display_value, "low": low, "high": high,
            "status": status, "reference_source": source,
            "raw_value": raw_value, "raw_unit": input_unit,
            "canonical_value": canonical_value, "canonical_unit": canonical_unit,
        })
    by = {r["key"]: r for r in results}
    notes, dangers = [], []

    h = by.get("hgb"); mcv = by.get("mcv"); wbc = by.get("wbc")
    plt = by.get("plt"); neut = by.get("neut"); lymph = by.get("lymph")

    if h and h["status"] == "low":
        if mcv and mcv["status"] != "unclassified" and mcv["value"] < mcv["low"]:
            notes.append(("قد يشير النمط إلى فقر دم صغير الكريات؛ نقص الحديد أحد الأسباب الشائعة — راجع الطبيب لتحديد السبب وفحص الفيريتين عند الحاجة",
                          "The pattern may indicate microcytic anemia; iron deficiency is one common cause — see a doctor to determine the cause and whether ferritin testing is needed"))
        elif mcv and mcv["status"] != "unclassified" and mcv["value"] > mcv["high"]:
            notes.append(("قد يشير النمط إلى فقر دم كبير الكريات؛ توجد أسباب متعددة مثل نقص B12 أو الفولات — راجع الطبيب لتحديد السبب",
                          "The pattern may indicate macrocytic anemia; causes include B12 or folate deficiency among others — see a doctor to determine the cause"))
        else:
            notes.append(("قد تشير النتيجة إلى انخفاض الهيموغلوبين (فقر دم محتمل) — راجع الطبيب لتحديد السبب",
                          "The result may indicate low hemoglobin (possible anemia) — see a doctor to determine the cause"))
    if h and h["status"] == "high":
        notes.append(("قد تشير النتيجة إلى ارتفاع الهيموغلوبين؛ توجد أسباب متعددة منها الجفاف — راجع الطبيب للتفسير",
                      "The result may indicate high hemoglobin; there are multiple possible causes including dehydration — see a doctor for interpretation"))
    if wbc and wbc["status"] == "high":
        if neut and neut["status"] == "high":
            notes.append(("قد يترافق ارتفاع كريات الدم البيضاء والعدلات مع التهاب أو عدوى، لكن النتيجة وحدها لا تحدد السبب.",
                          "High WBC and neutrophils can occur with infection or inflammation, but the result alone does not determine the cause."))
        elif lymph and lymph["status"] == "high":
            notes.append(("قد يترافق ارتفاع كريات الدم البيضاء واللمفاويات مع بعض العدوى أو أسباب أخرى؛ يلزم تفسيرها مع الأعراض.",
                          "High WBC and lymphocytes can occur with some infections or other causes; interpretation depends on symptoms and context."))
        else:
            notes.append(("قد يشير ارتفاع كريات الدم البيضاء إلى التهاب أو عدوى أو أسباب أخرى.",
                          "High WBC may be associated with infection, inflammation, or other causes."))
    if wbc and wbc["status"] == "low":
        notes.append(("قد يشير انخفاض كريات الدم البيضاء إلى أسباب متعددة؛ راجع الطبيب إذا استمر أو ترافق مع أعراض.",
                      "Low WBC can have multiple causes; see a doctor if it persists or is accompanied by symptoms."))
    if plt and plt["status"] == "low":
        notes.append(("قد يشير انخفاض الصفائح إلى الحاجة لتقييم خطر النزف — راجع الطبيب.",
                      "Low platelets may require assessment of bleeding risk — see a doctor."))
    if plt and plt["status"] == "high":
        notes.append(("قد يشير ارتفاع الصفائح إلى الحاجة لتقييم السبب — راجع الطبيب.",
                      "High platelets may require evaluation of the cause — see a doctor."))

    # Critical thresholds are applied only after a trusted canonical conversion.
    for key, rules in DANGER_RULES.items():
        r = by.get(key)
        value = r.get("canonical_value") if r else None
        if value is None:
            continue
        for level, threshold, op in rules:
            crossed = value < threshold if op == "lt" else value > threshold
            if not crossed:
                continue
            if key == "hgb":
                dangers.append((level,
                    "🚨🚨 فقر دم شديد الخطورة — يلزم تقييم طارئ فورًا" if level == "emergency" else "🚨 فقر دم شديد — يلزم تقييم طبي عاجل وقد يتطلب علاجًا بالمستشفى",
                    "🚨🚨 Critically low hemoglobin — immediate emergency evaluation is needed" if level == "emergency" else "🚨 Severely low hemoglobin — urgent medical evaluation is needed and hospital treatment may be required"))
            elif key == "plt":
                dangers.append((level,
                    "🚨🚨 صفائح حرجة — يلزم تقييم طارئ فورًا" if level == "emergency" else "🚨 صفائح منخفضة جدًا — يوجد خطر نزف ويجب طلب تقييم عاجل",
                    "🚨🚨 Critically low platelets — immediate emergency evaluation is needed" if level == "emergency" else "🚨 Very low platelets — bleeding risk requires urgent evaluation"))
            elif key == "wbc":
                dangers.append((level,
                    "🚨 كريات بيضاء مرتفعة جدًا — يلزم تقييم طبي عاجل" if threshold > 10 else "🚨 كريات بيضاء منخفضة جدًا — يلزم تقييم طبي عاجل",
                    "🚨 Very high WBC — urgent medical evaluation is needed" if threshold > 10 else "🚨 Very low WBC — urgent medical evaluation is needed"))
            break

    if any(d[0] == "emergency" for d in dangers): level = "emergency"
    elif any(d[0] == "urgent" for d in dangers): level = "urgent"
    elif notes or any(r["status"] in {"low", "high"} for r in results): level = "see_doctor"
    elif results and any(r["status"] == "unclassified" for r in results): level = "unclassified"
    else: level = "normal"
    return results, notes, dangers, level, is_child

def build_text(results, gender, lang="ar", notes=None, dangers=None, child_note=False):
    """Builds the readable report message (plain text, no HTML)."""
    notes = notes or []
    dangers = dangers or []
    gender_key = _gender_key(gender)
    if lang == "en":
        gen = {"m": "Male", "f": "Female"}.get(gender_key, "Sex not specified")
        ref_label = "Laboratory/pediatric reference where available" if child_note else f"Reference: {gen} (adult fallback only when age, sex and unit are clear)"
        lines = ["🩸 Blood Test Report", ref_label, ""]
        status_ar = {"normal": "Normal ✅", "low": "Low 🔻", "high": "High 🔺", "unclassified": "Not classified ⚪"}
        for r in results:
            rng = f" ({r['low']}-{r['high']})" if r.get("low") is not None and r.get("high") is not None else ""
            lines.append(f"{r['name_en']}: {r['value']} {r.get('unit','')}{rng} {status_ar.get(r['status'], r['status'])}")
        if notes:
            lines += ["", "📋 Notes:"] + [f"• {n[1]}" for n in notes]
        if dangers:
            lines += ["", "🚨 Alert:"] + [d[2] for d in dangers]
        if child_note:
            lines += ["", "👶 Pediatric ranges differ from adult ranges — please show the report to a pediatrician."]
        lines += ["", "⚠️ Awareness only — not a diagnosis. Ranges vary by lab; confirm any result with your doctor."]
    else:
        gen = {"m": "ذكر", "f": "أنثى"}.get(gender_key, "الجنس غير محدد")
        ref_label = "المرجع: نطاق المختبر/الأطفال عند توفره" if child_note else f"المرجع: {gen} (نطاق البالغين الاحتياطي فقط عند وضوح العمر والجنس والوحدة)"
        lines = ["🩸 تحليل الدم", ref_label, ""]
        status_ar = {"normal": "طبيعي ✅", "low": "منخفض 🔻", "high": "مرتفع 🔺", "unclassified": "غير مصنف ⚪"}
        for r in results:
            rng = f" ({r['low']}-{r['high']})" if r.get("low") is not None and r.get("high") is not None else ""
            lines.append(f"{r['name_ar']}: {r['value']} {r.get('unit','')}{rng} {status_ar.get(r['status'], r['status'])}")
        if notes:
            lines += ["", "📋 ملاحظات:"] + [f"• {n[0]}" for n in notes]
        if dangers:
            lines += ["", "🚨 تنبيه:"] + [d[1] for d in dangers]
        if child_note:
            lines += ["", "👶 نطاقات الأطفال تختلف عن نطاقات البالغين — ننصح بعرض النتيجة على طبيب أطفال."]
        lines += ["", "⚠️ للتوعية فقط — لا يُعد هذا تشخيصًا طبيًا. تختلف النطاقات المرجعية حسب المختبر، ويُنصح بمراجعة الطبيب لتفسير النتائج في سياق حالتك."]
    return "\n".join(lines)


# ---------------------------------------------------------------- structured card data
INDICATOR_INFO = {
    "hgb": {
        "what_ar": "البروتين الحامل للأكسجين داخل كريات الدم الحمراء.",
        "what_en": "The oxygen-carrying protein inside red blood cells.",
        "low_ar": "قد تشير النتيجة إلى انخفاض الهيموغلوبين (فقر دم محتمل). لا يعني ذلك بالضرورة وجود مرض — راجع طبيبك لتحديد السبب.",
        "low_en": "The result may indicate low hemoglobin (possible anemia). It doesn't necessarily mean a disease — see your doctor to determine the cause.",
        "high_ar": "قد تشير النتيجة إلى ارتفاع الهيموغلوبين، وقد يرتبط بالجفاف أو عوامل أخرى — راجع طبيبك للتحقق.",
        "high_en": "The result may indicate high hemoglobin, possibly linked to dehydration or other factors — see your doctor to check.",
        "when_ar": "راجع طبيبك إذا استمر الانخفاض أو رافقته دوخة، تعب، شحوب، أو تسارع نبض.",
        "when_en": "See your doctor if the low level persists or comes with dizziness, fatigue, paleness, or a fast heartbeat.",
    },
    "wbc": {
        "what_ar": "كريات الدم البيضاء — خلايا المناعة التي تحارب العدوى.",
        "what_en": "White blood cells — immune cells that fight infection.",
        "low_ar": "قد تشير النتيجة إلى انخفاض كريات الدم البيضاء، وقد يرتبط بعدوى فيروسية أو أسباب أخرى.",
        "low_en": "The result may indicate low white blood cells, possibly linked to a viral infection or other causes.",
        "high_ar": "قد تشير النتيجة إلى ارتفاع كريات الدم البيضاء، وغالبًا ما يرتبط بالتهاب أو عدوى.",
        "high_en": "The result may indicate high white blood cells, often linked to infection or inflammation.",
        "when_ar": "راجع طبيبك إذا رافقت النتيجة حمى، ألم، أو عدوى متكررة، أو إذا استمر الارتفاع.",
        "when_en": "See your doctor if the result comes with fever, pain, or repeated infections, or if the high level persists.",
    },
    "rbc": {
        "what_ar": "كريات الدم الحمراء — الخلايا الحاملة للأكسجين.",
        "what_en": "Red blood cells — the cells that carry oxygen.",
        "low_ar": "قد تشير النتيجة إلى انخفاض عدد كريات الدم الحمراء، وقد يرتبط بفقر دم أو أسباب أخرى.",
        "low_en": "The result may indicate a low red blood cell count, possibly linked to anemia or other causes.",
        "high_ar": "قد تشير النتيجة إلى ارتفاع عدد كريات الدم الحمراء، وقد يرتبط بالجفاف أو عوامل أخرى.",
        "high_en": "The result may indicate a high red blood cell count, possibly linked to dehydration or other factors.",
        "when_ar": "راجع طبيبك إذا رافق الانخفاض تعب أو دوخة، أو إذا استمرت النتيجة خارج النطاق.",
        "when_en": "See your doctor if the low count comes with fatigue or dizziness, or if the result stays out of range.",
    },
    "hct": {
        "what_ar": "نسبة كريات الدم الحمراء في حجم الدم الكلي.",
        "what_en": "The proportion of red blood cells in total blood volume.",
        "low_ar": "قد تشير النتيجة إلى انخفاض الهيماتوكريت، وقد يرتبط بفقر دم أو نزيف خفيف.",
        "low_en": "The result may indicate a low hematocrit, possibly linked to anemia or mild bleeding.",
        "high_ar": "قد تشير النتيجة إلى ارتفاع الهيماتوكريت، وقد يرتبط بالجفاف أو أسباب أخرى.",
        "high_en": "The result may indicate a high hematocrit, possibly linked to dehydration or other causes.",
        "when_ar": "راجع طبيبك إذا رافق الانخفاض دوخة أو تعب، أو إذا كانت النتيجة خارج النطاق مع أعراض.",
        "when_en": "See your doctor if the low result comes with dizziness or fatigue, or if it's out of range with symptoms.",
    },
    "mcv": {
        "what_ar": "متوسط حجم كرية الدم الحمراء الواحدة.",
        "what_en": "The average size of a single red blood cell.",
        "low_ar": "قد تشير النتيجة إلى صغر حجم الكريات، وهو شائع مع نقص الحديد.",
        "low_en": "The result may indicate small red cells, common with iron deficiency.",
        "high_ar": "قد تشير النتيجة إلى كبر حجم الكريات، وقد يرتبط بنقص فيتامين ب12 أو حمض الفوليك.",
        "high_en": "The result may indicate large red cells, possibly linked to vitamin B12 or folate deficiency.",
        "when_ar": "راجع طبيبك إذا كانت النتيجة خارج النطاق مع فقر دم أو أعراض تعب.",
        "when_en": "See your doctor if the result is out of range with anemia or fatigue symptoms.",
    },
    "mch": {
        "what_ar": "متوسط كمية الهيموغلوبين داخل الكرية الواحدة.",
        "what_en": "Average hemoglobin amount inside one red blood cell.",
        "low_ar": "قد تشير النتيجة إلى انخفاض كمية الهيموغلوبين في الكريات، وغالبًا ما يرتبط بنقص الحديد.",
        "low_en": "The result may indicate low hemoglobin per cell, often linked to iron deficiency.",
        "high_ar": "قد تشير النتيجة إلى ارتفاع كمية الهيموغلوبين في الكريات.",
        "high_en": "The result may indicate a high hemoglobin amount per cell.",
        "when_ar": "راجع طبيبك إذا رافقت النتيجة أعراض فقر دم مثل التعب أو الشحوب.",
        "when_en": "See your doctor if the result comes with anemia symptoms like fatigue or paleness.",
    },
    "mchc": {
        "what_ar": "متوسط تركيز الهيموغلوبين داخل الكريات.",
        "what_en": "Average hemoglobin concentration inside the red cells.",
        "low_ar": "قد تشير النتيجة إلى انخفاض تركيز الهيموغلوبين، وقد يرتبط بفقر دم.",
        "low_en": "The result may indicate a low hemoglobin concentration, possibly linked to anemia.",
        "high_ar": "قد تشير النتيجة إلى ارتفاع تركيز الهيموغلوبين، وهو نادر ويحتاج تقييمًا.",
        "high_en": "The result may indicate a high hemoglobin concentration, which is rare and needs evaluation.",
        "when_ar": "راجع طبيبك إذا كانت النتيجة خارج النطاق مع أعراض تعب أو شحوب.",
        "when_en": "See your doctor if the result is out of range with fatigue or paleness.",
    },
    "plt": {
        "what_ar": "الصفائح الدموية — خلايا تساعد على تخثر الدم ووقف النزيف.",
        "what_en": "Platelets — cells that help blood clot and stop bleeding.",
        "low_ar": "قد تشير النتيجة إلى انخفاض الصفائح، وقد يزيد ذلك من خطر النزف.",
        "low_en": "The result may indicate low platelets, which may increase bleeding risk.",
        "high_ar": "قد تشير النتيجة إلى ارتفاع الصفائح، وقد يرتبط بالتهاب أو عوامل أخرى.",
        "high_en": "The result may indicate high platelets, possibly linked to inflammation or other factors.",
        "when_ar": "راجع الطبيب فورًا إذا كانت الصفائح منخفضة جدًا أو رافقتها كدمات أو نزيف بلا سبب.",
        "when_en": "See your doctor promptly if platelets are very low or come with unexplained bruising or bleeding.",
    },
    "neut": {
        "what_ar": "نسبة العدلات — النوع الأكثر شيوعاً من كريات الدم البيضاء.",
        "what_en": "Neutrophil percentage — the most common type of white blood cells.",
        "low_ar": "قد تشير النتيجة إلى انخفاض العدلات، وقد يرتبط بعدوى فيروسية أو أسباب أخرى.",
        "low_en": "The result may indicate low neutrophils, possibly linked to a viral infection or other causes.",
        "high_ar": "قد تشير النتيجة إلى ارتفاع العدلات، وغالبًا ما يرتبط بعدوى بكتيرية أو التهاب.",
        "high_en": "The result may indicate high neutrophils, often linked to bacterial infection or inflammation.",
        "when_ar": "راجع طبيبك إذا رافقت النتيجة حمى أو ألم، أو إذا كانت خارج النطاق مع أعراض.",
        "when_en": "See your doctor if the result comes with fever or pain, or if it's out of range with symptoms.",
    },
    "lymph": {
        "what_ar": "نسبة اللمفاويات — نوع من كريات الدم البيضاء مهم للمناعة.",
        "what_en": "Lymphocyte percentage — a type of white blood cell important for immunity.",
        "low_ar": "قد تشير النتيجة إلى انخفاض اللمفاويات، وقد يرتبط بإجهاد أو عدوى أو أسباب أخرى.",
        "low_en": "The result may indicate low lymphocytes, possibly linked to stress, infection, or other causes.",
        "high_ar": "قد تشير النتيجة إلى ارتفاع اللمفاويات، وقد يرتبط بعدوى فيروسية.",
        "high_en": "The result may indicate high lymphocytes, possibly linked to a viral infection.",
        "when_ar": "راجع طبيبك إذا كانت النتيجة خارج النطاق بشكل واضح أو رافقها أعراض مستمرة.",
        "when_en": "See your doctor if the result is clearly out of range or comes with persistent symptoms.",
    },
    "rdw": {
        "what_ar": "مقياس التباين في أحجام كريات الدم الحمراء.",
        "what_en": "A measure of variation in red blood cell sizes.",
        "low_ar": "قد تشير النتيجة إلى تباين ضعيف في أحجام الكريات.",
        "low_en": "The result may indicate low variation in red cell sizes.",
        "high_ar": "قد تشير النتيجة إلى تباين كبير في أحجام الكريات، وغالبًا ما يظهر مع فقر دم.",
        "high_en": "The result may indicate high variation in red cell sizes, often seen with anemia.",
        "when_ar": "راجع طبيبك إذا كانت النتيجة مرتفعة مع فقر دم أو أعراض تعب.",
        "when_en": "See your doctor if the result is high with anemia or fatigue.",
    },
}

# Symptoms that can accompany *conditions associated with* an abnormal CBC pattern.
# They are deliberately not framed as symptoms caused by the number itself.
CBC_ASSOCIATED_SYMPTOMS = {
    "hgb": {
        "low_ar": ["تعب أو ضعف", "دوخة أو خفة رأس", "شحوب", "صداع", "ضيق نفس مع المجهود", "خفقان"],
        "low_en": ["Fatigue or weakness", "Dizziness or lightheadedness", "Paleness", "Headache", "Shortness of breath with exertion", "Palpitations"],
        "high_ar": ["قد لا توجد أعراض", "صداع أو دوخة أحيانًا", "احمرار أو شعور بالامتلاء أحيانًا"],
        "high_en": ["There may be no symptoms", "Sometimes headache or dizziness", "Sometimes flushing or a sense of fullness"],
    },
    "rbc": {
        "low_ar": ["تعب", "ضعف", "دوخة", "شحوب", "ضيق نفس مع المجهود"],
        "low_en": ["Fatigue", "Weakness", "Dizziness", "Paleness", "Shortness of breath with exertion"],
        "high_ar": ["قد لا توجد أعراض", "صداع أو دوخة أحيانًا"],
        "high_en": ["There may be no symptoms", "Sometimes headache or dizziness"],
    },
    "hct": {
        "low_ar": ["تعب أو ضعف", "دوخة", "شحوب", "ضيق نفس مع المجهود"],
        "low_en": ["Fatigue or weakness", "Dizziness", "Paleness", "Shortness of breath with exertion"],
        "high_ar": ["قد لا توجد أعراض", "صداع أو دوخة أحيانًا", "عطش أو علامات جفاف إذا كان السبب جفافًا"],
        "high_en": ["There may be no symptoms", "Sometimes headache or dizziness", "Thirst or dehydration symptoms when dehydration is the cause"],
    },
    "mcv": {
        "low_ar": ["المؤشر نفسه لا يسبب أعراضًا", "إذا ترافق مع فقر دم: تعب، شحوب، دوخة، ضيق نفس أو خفقان"],
        "low_en": ["The index itself does not cause symptoms", "If associated with anemia: fatigue, paleness, dizziness, breathlessness, or palpitations"],
        "high_ar": ["المؤشر نفسه لا يسبب أعراضًا", "إذا ترافق مع فقر دم: تعب أو ضعف", "قد تظهر أعراض عصبية في بعض أسباب نقص B12 مثل التنميل"],
        "high_en": ["The index itself does not cause symptoms", "If associated with anemia: fatigue or weakness", "Some B12-related causes may also involve numbness/neurological symptoms"],
    },
    "mch": {
        "low_ar": ["المؤشر نفسه لا يسبب أعراضًا", "إذا ترافق مع فقر دم: تعب، شحوب، دوخة أو ضيق نفس"],
        "low_en": ["The index itself does not cause symptoms", "If associated with anemia: fatigue, paleness, dizziness, or breathlessness"],
        "high_ar": ["غالبًا لا توجد أعراض من ارتفاع MCH نفسه", "الأعراض — إن وجدت — تعتمد على السبب وبقية مؤشرات الدم"],
        "high_en": ["High MCH itself often causes no symptoms", "Any symptoms depend on the cause and the rest of the CBC"],
    },
    "mchc": {
        "low_ar": ["المؤشر نفسه لا يسبب أعراضًا", "إذا ترافق مع فقر دم: تعب، ضعف، شحوب أو دوخة"],
        "low_en": ["The index itself does not cause symptoms", "If associated with anemia: fatigue, weakness, paleness, or dizziness"],
        "high_ar": ["غالبًا لا توجد أعراض من الرقم وحده", "الأعراض تعتمد على السبب ويحتاج الارتفاع الواضح للتحقق"],
        "high_en": ["The number itself often causes no symptoms", "Symptoms depend on the cause; a clear elevation should be verified"],
    },
    "rdw": {
        "low_ar": ["عادة لا يسبب RDW المنخفض أعراضًا بحد ذاته"],
        "low_en": ["A low RDW usually does not cause symptoms by itself"],
        "high_ar": ["المؤشر نفسه لا يسبب أعراضًا", "إذا ترافق مع فقر دم: تعب، ضعف، دوخة، شحوب أو ضيق نفس"],
        "high_en": ["The index itself does not cause symptoms", "If associated with anemia: fatigue, weakness, dizziness, paleness, or breathlessness"],
    },
    "wbc": {
        "low_ar": ["قد لا توجد أعراض من الانخفاض نفسه", "حمى أو قشعريرة عند وجود عدوى", "التهابات متكررة أو تقرحات بالفم في بعض الحالات"],
        "low_en": ["Low WBC itself may cause no symptoms", "Fever or chills when infection is present", "Repeated infections or mouth sores in some cases"],
        "high_ar": ["قد لا توجد أعراض من الارتفاع نفسه", "حمى", "قشعريرة أو آلام بالجسم", "أعراض التهاب أو عدوى بحسب السبب"],
        "high_en": ["High WBC itself may cause no symptoms", "Fever", "Chills or body aches", "Inflammation/infection symptoms depending on the cause"],
    },
    "neut": {
        "low_ar": ["قد لا توجد أعراض من الانخفاض نفسه", "حمى", "التهابات متكررة", "قرح أو ألم بالفم/الحلق في بعض الحالات"],
        "low_en": ["Low neutrophils may cause no symptoms themselves", "Fever", "Repeated infections", "Mouth/throat sores in some cases"],
        "high_ar": ["قد لا توجد أعراض من الارتفاع نفسه", "حمى أو ألم أو أعراض عدوى/التهاب بحسب السبب"],
        "high_en": ["High neutrophils may cause no symptoms themselves", "Fever, pain, or infection/inflammation symptoms depending on the cause"],
    },
    "lymph": {
        "low_ar": ["قد لا توجد أعراض من الانخفاض نفسه", "التهابات متكررة في بعض الحالات"],
        "low_en": ["Low lymphocytes may cause no symptoms themselves", "Repeated infections in some cases"],
        "high_ar": ["قد لا توجد أعراض من الارتفاع نفسه", "حمى أو تعب", "تورم الغدد أو أعراض عدوى بحسب السبب"],
        "high_en": ["High lymphocytes may cause no symptoms themselves", "Fever or fatigue", "Swollen glands or infection symptoms depending on the cause"],
    },
    "plt": {
        "low_ar": ["سهولة ظهور الكدمات", "نقط حمراء/بنفسجية صغيرة بالجلد", "نزيف الأنف أو اللثة", "طول مدة النزف", "غزارة الدورة"],
        "low_en": ["Easy bruising", "Small red/purple skin spots", "Nose or gum bleeding", "Prolonged bleeding", "Heavy periods"],
        "high_ar": ["كثيرًا لا توجد أعراض", "صداع أو دوخة أحيانًا", "أي ألم صدر أو ضيق نفس أو ضعف مفاجئ يحتاج تقييمًا عاجلًا"],
        "high_en": ["Often there are no symptoms", "Sometimes headache or dizziness", "Chest pain, breathlessness, or sudden weakness needs urgent assessment"],
    },
}

# V139: source-backed explanations for common panels.
# V146: direct, authoritative medical references for laboratory explanations.
# IMPORTANT: these references explain what a marker measures and how clinicians
# commonly use it. They do not replace the reference interval printed by the
# user's own laboratory report, which remains the classification source.
PANEL_SOURCES = {
    "cbc": {
        "name": "MedlinePlus — Complete Blood Count (CBC)",
        "url": "https://medlineplus.gov/lab-tests/complete-blood-count-cbc/",
        "organization": "NIH / U.S. National Library of Medicine",
        "authority": "government",
        "use_ar": "مرجع مباشر لشرح مكونات CBC ووظيفة كريات الدم والهيموغلوبين والصفائح.",
        "use_en": "Direct reference for CBC components, blood cells, hemoglobin, and platelets.",
    },
    "metabolic": {
        "name": "MedlinePlus — Comprehensive Metabolic Panel (CMP)",
        "url": "https://medlineplus.gov/lab-tests/comprehensive-metabolic-panel-cmp/",
        "organization": "NIH / U.S. National Library of Medicine",
        "authority": "government",
        "use_ar": "مرجع لمؤشرات الاستقلاب والكلى والكبد والجلوكوز وبعض الأملاح ضمن لوحة CMP.",
        "use_en": "Reference for metabolic, kidney, liver, glucose, and electrolyte markers included in CMP.",
    },
    "lipids": {
        "name": "MedlinePlus — Cholesterol Levels",
        "url": "https://medlineplus.gov/lab-tests/cholesterol-levels/",
        "organization": "NIH / U.S. National Library of Medicine",
        "authority": "government",
        "use_ar": "مرجع مباشر لقراءة LDL وHDL والكوليسترول الكلي والدهون الثلاثية.",
        "use_en": "Direct reference for LDL, HDL, total cholesterol, and triglycerides.",
    },
    "liver": {
        "name": "MedlinePlus — Liver Function Tests",
        "url": "https://medlineplus.gov/lab-tests/liver-function-tests/",
        "organization": "NIH / U.S. National Library of Medicine",
        "authority": "government",
        "use_ar": "مرجع مباشر لمؤشرات وظائف الكبد مثل ALT وAST وALP والبيليروبين والألبومين.",
        "use_en": "Direct reference for liver markers such as ALT, AST, ALP, bilirubin, and albumin.",
    },
    "electrolytes": {
        "name": "MedlinePlus — Electrolyte Panel",
        "url": "https://medlineplus.gov/lab-tests/electrolyte-panel/",
        "organization": "NIH / U.S. National Library of Medicine",
        "authority": "government",
        "use_ar": "مرجع مباشر للصوديوم والبوتاسيوم والكلوريد والبيكربونات وتوازن السوائل والأحماض والقواعد.",
        "use_en": "Direct reference for sodium, potassium, chloride, bicarbonate, fluid, and acid-base balance.",
    },
    "general": {
        "name": "MedlinePlus — How to Understand Your Lab Results",
        "url": "https://medlineplus.gov/lab-tests/how-to-understand-your-lab-results/",
        "organization": "NIH / U.S. National Library of Medicine",
        "authority": "government",
        "use_ar": "مرجع عام لفهم نتائج المختبر ولماذا يجب مقارنة القيمة بالنطاق الموجود في نفس تقرير المختبر.",
        "use_en": "General reference for lab results and why values should be compared with the range on the same report.",
    },
}

DIRECT_SOURCES = {
    "glucose": {
        "name": "MedlinePlus — Blood Glucose Test",
        "url": "https://medlineplus.gov/lab-tests/blood-glucose-test/",
        "organization": "NIH / U.S. National Library of Medicine",
        "authority": "government",
        "use_ar": "مرجع مباشر لقياس جلوكوز الدم وتأثير الصيام وتوقيت القياس على التفسير.",
        "use_en": "Direct reference for blood glucose testing and the role of fasting and test timing.",
    },
    "hba1c": {
        "name": "NIDDK — The A1C Test & Diabetes",
        "url": "https://www.niddk.nih.gov/health-information/diagnostic-tests/a1c-test",
        "organization": "NIH / NIDDK",
        "authority": "government",
        "use_ar": "مرجع NIH مباشر لفحص HbA1c واستخدامه في متابعة متوسط سكر الدم وتفسيره ضمن السياق.",
        "use_en": "Direct NIH reference for HbA1c, average glucose, and clinical interpretation context.",
    },
    "creatinine": {
        "name": "MedlinePlus — Creatinine Test",
        "url": "https://medlineplus.gov/lab-tests/creatinine-test/",
        "organization": "NIH / U.S. National Library of Medicine",
        "authority": "government",
        "use_ar": "مرجع مباشر للكرياتينين ودوره في تقييم وظائف الكلى مع eGFR ومعلومات أخرى.",
        "use_en": "Direct reference for creatinine and its use with eGFR and other information to assess kidney function.",
    },
    "egfr": {
        "name": "NIDDK — Estimated GFR Calculators",
        "url": "https://www.niddk.nih.gov/health-information/professionals/clinical-tools-patient-management/kidney-disease/laboratory-evaluation/estimated-gfr-calculators",
        "organization": "NIH / NIDDK",
        "authority": "government",
        "use_ar": "مرجع تخصصي من NIDDK يوضح أن eGFR تقدير لوظائف الكلى وله حدود دقة ويُفهم مع السياق.",
        "use_en": "Specialist NIDDK reference explaining that eGFR estimates kidney function and has accuracy limitations.",
    },
    "iron": {
        "name": "MedlinePlus — Iron Tests",
        "url": "https://medlineplus.gov/lab-tests/iron-tests/",
        "organization": "NIH / U.S. National Library of Medicine",
        "authority": "government",
        "use_ar": "مرجع مباشر لفحوص الحديد وعلاقتها بالهيموغلوبين ومخزون الحديد.",
        "use_en": "Direct reference for iron tests and their relationship to hemoglobin and iron stores.",
    },
    "ferritin": {
        "name": "MedlinePlus — Ferritin Blood Test",
        "url": "https://medlineplus.gov/lab-tests/ferritin-blood-test/",
        "organization": "NIH / U.S. National Library of Medicine",
        "authority": "government",
        "use_ar": "مرجع مباشر للفريتين بوصفه مؤشرًا لمخزون الحديد مع ضرورة فهمه ضمن السياق.",
        "use_en": "Direct reference for ferritin as a marker of iron stores interpreted in context.",
    },
    "b12": {
        "name": "NIH ODS — Vitamin B12",
        "url": "https://ods.od.nih.gov/factsheets/VitaminB12-HealthProfessional/",
        "organization": "NIH / Office of Dietary Supplements",
        "authority": "government",
        "use_ar": "مرجع NIH تخصصي لفيتامين B12 ودوره في تكوين الدم ووظائف الجهاز العصبي.",
        "use_en": "Specialist NIH reference for vitamin B12, blood-cell formation, and nervous-system function.",
    },
    "vitd": {
        "name": "MedlinePlus — Vitamin D Test",
        "url": "https://medlineplus.gov/lab-tests/vitamin-d-test/",
        "organization": "NIH / U.S. National Library of Medicine",
        "authority": "government",
        "use_ar": "مرجع مباشر لفحص فيتامين D وما يقيسه الاختبار المخبري.",
        "use_en": "Direct reference for vitamin D blood testing and what the laboratory test measures.",
    },
    "tsh": {
        "name": "MedlinePlus — TSH Test",
        "url": "https://medlineplus.gov/lab-tests/tsh-thyroid-stimulating-hormone-test/",
        "organization": "NIH / U.S. National Library of Medicine",
        "authority": "government",
        "use_ar": "مرجع مباشر لفحص TSH مع توضيح أنه لا يحدد سبب اضطراب الغدة بمفرده.",
        "use_en": "Direct reference for TSH, including why TSH alone does not establish the cause of a thyroid problem.",
    },    "free_t4": {"name":"MedlinePlus — Free T4 Test","url":"https://medlineplus.gov/ency/article/003517.htm","organization":"NIH / U.S. National Library of Medicine","authority":"government","use_ar":"مرجع مباشر لفحص Free T4 وتأثر تفسيره بالأدوية والحمل وبعض الحالات.","use_en":"Direct reference for free T4 testing and factors that can affect interpretation."},
    "crp": {"name":"MedlinePlus — C-Reactive Protein (CRP) Test","url":"https://medlineplus.gov/lab-tests/c-reactive-protein-crp-test/","organization":"NIH / U.S. National Library of Medicine","authority":"government","use_ar":"مرجع مباشر لـ CRP كمؤشر للالتهاب لا يحدد السبب أو المكان بمفرده.","use_en":"Direct reference for CRP as an inflammation marker that does not identify cause or location by itself."},
    "esr": {"name":"MedlinePlus — Erythrocyte Sedimentation Rate (ESR)","url":"https://www.medlineplus.gov/lab-tests/erythrocyte-sedimentation-rate-esr/","organization":"NIH / U.S. National Library of Medicine","authority":"government","use_ar":"مرجع مباشر لـ ESR كمؤشر غير نوعي للالتهاب ويُفسر مع السياق والفحوص الأخرى.","use_en":"Direct reference for ESR as a non-specific inflammation marker interpreted with context and other tests."},
    "magnesium": {"name":"MedlinePlus — Magnesium Blood Test","url":"https://www.medlineplus.gov/ency/article/003487.htm","organization":"NIH / U.S. National Library of Medicine","authority":"government","use_ar":"مرجع مباشر لفحص المغنيسيوم ووظيفته العصبية والعضلية والقلبية.","use_en":"Direct reference for magnesium testing and its neuromuscular and cardiac roles."},
    "phosphate": {"name":"MedlinePlus — Phosphate in Blood","url":"https://medlineplus.gov/lab-tests/phosphate-in-blood/","organization":"NIH / U.S. National Library of Medicine","authority":"government","use_ar":"مرجع مباشر لفحص الفوسفات في الدم وعلاقته بالكلى والعظام والكالسيوم وفيتامين D وهرمون جار الدرقية.","use_en":"Direct reference for blood phosphate testing and its relationship with kidney function, bone health, calcium, vitamin D, and parathyroid hormone."},
    "uric_acid": {"name":"MedlinePlus — Uric Acid Test","url":"https://medlineplus.gov/lab-tests/uric-acid-test/","organization":"NIH / U.S. National Library of Medicine","authority":"government","use_ar":"مرجع مباشر لفحص حمض اليوريك وعلاقته بالنقرس وحصى الكلى ضمن السياق.","use_en":"Direct reference for uric acid testing in the context of gout and kidney stones."},
    "ggt": {"name":"MedlinePlus — GGT Test","url":"https://medlineplus.gov/lab-tests/gamma-glutamyl-transferase-ggt-test/","organization":"NIH / U.S. National Library of Medicine","authority":"government","use_ar":"مرجع مباشر لـ GGT كمؤشر يُقرأ مع بقية اختبارات الكبد ولا يحدد السبب بمفرده.","use_en":"Direct reference for GGT, interpreted with other liver tests and not diagnostic by itself."},
    "lipase": {"name":"MedlinePlus — Lipase Tests","url":"https://www.medlineplus.gov/lab-tests/lipase-tests/","organization":"NIH / U.S. National Library of Medicine","authority":"government","use_ar":"مرجع مباشر لفحص الليباز واستخدامه ضمن تقييم البنكرياس والسياق السريري.","use_en":"Direct reference for lipase testing in pancreatic assessment and clinical context."},
    "folate": {"name":"MedlinePlus — Folic Acid Test","url":"https://www.medlineplus.gov/ency/article/003686.htm","organization":"NIH / U.S. National Library of Medicine","authority":"government","use_ar":"مرجع مباشر لفحص الفولات (فيتامين B9) في الدم وعلاقته بتكوين خلايا الدم، ويُفسر مع B12 والتغذية والسياق السريري.","use_en":"Direct reference for blood folate (vitamin B9) testing and its role in blood-cell formation, interpreted with B12, nutrition, and clinical context."},
    "anc": {"name":"NCI — Absolute Neutrophil Count (ANC)","url":"https://www.cancer.gov/publications/dictionaries/cancer-terms/def/absolute-neutrophil-count","organization":"U.S. National Cancer Institute","authority":"government","use_ar":"مرجع حكومي مباشر لتعريف العدد المطلق للعدلات (ANC) ودوره في تقدير عدد العدلات ومخاطر العدوى عند الانخفاض الشديد.","use_en":"Direct government reference defining absolute neutrophil count (ANC) and its role in assessing neutrophil quantity and infection risk when markedly low."},
    "troponin": {"name":"MedlinePlus — Troponin Test","url":"https://www.medlineplus.gov/lab-tests/troponin-test/","organization":"NIH / U.S. National Library of Medicine","authority":"government","use_ar":"مرجع مباشر للتروبونين القلبي؛ نوع الفحص والحدود المرجعية والتوقيت والسياق السريري أساسية للتفسير.","use_en":"Direct reference for cardiac troponin; assay, reference limit, timing, and clinical context are essential to interpretation."},
}


EXTENDED_INFO = {
    "glucose": ("يقيس مستوى الجلوكوز في الدم في وقت سحب العينة؛ تفسيره يتأثر بالصيام وتوقيت الوجبة.", "Measures blood glucose at the time of sampling; interpretation depends on fasting and meal timing."),
    "hba1c": ("يعكس متوسط سكر الدم تقريبًا خلال آخر شهرين إلى ثلاثة أشهر، وقد تتأثر دقته ببعض اضطرابات كريات الدم.", "Reflects average blood glucose over roughly the previous two to three months and can be affected by some red-cell conditions."),
    "creatinine": ("ناتج فضلات يُستخدم مع معلومات أخرى لتقييم ترشيح الكلى.", "A waste product used with other information to assess kidney filtration."),
    "egfr": ("تقدير لمعدل ترشيح الكلى محسوب من الكرياتينين وعوامل أخرى؛ يُفسر حسب العمر والسياق.", "An estimate of kidney filtration calculated from creatinine and other factors; it is interpreted in context."),
    "bun": ("يقيس نيتروجين اليوريا، وهو ناتج فضلات يتأثر بوظائف الكلى والترطيب وعوامل أخرى.", "Measures urea nitrogen, a waste product affected by kidney function, hydration, and other factors."),
    "urea": ("يقيس اليوريا في الدم؛ يتأثر بالترطيب ووظائف الكلى وعوامل غذائية وسريرية أخرى.", "Measures blood urea; it can vary with hydration, kidney function, diet, and other clinical factors."),
    "alt": ("إنزيم يوجد بكثرة في الكبد ويُقرأ عادةً مع AST وبقية مؤشرات الكبد.", "An enzyme abundant in the liver, usually interpreted with AST and other liver-related markers."),
    "ast": ("إنزيم يوجد في الكبد والعضلات وأنسجة أخرى؛ لا يُفسر منفردًا.", "An enzyme found in liver, muscle, and other tissues; it should not be interpreted alone."),
    "alp": ("إنزيم يرتبط بالكبد والقنوات الصفراوية والعظام؛ يعتمد تفسيره على بقية التحاليل والسياق.", "An enzyme related to the liver, bile ducts, and bone; interpretation depends on other tests and context."),
    "bilirubin": ("ناتج من تكسير كريات الدم الحمراء ويتعامل معه الكبد؛ يُقرأ مع بقية مؤشرات الكبد.", "A product of red-cell breakdown processed by the liver; interpreted with other liver-related markers."),
    "albumin": ("بروتين رئيسي في الدم يصنعه الكبد ويتأثر بعوامل متعددة.", "A major blood protein made by the liver and influenced by multiple factors."),
    "total_protein": ("يقيس إجمالي البروتينات الرئيسية في الدم، ومنها الألبومين والغلوبولينات.", "Measures the major proteins in blood, including albumin and globulins."),
    "chol_total": ("يقيس إجمالي الكوليسترول ويُفسر مع LDL وHDL والدهون الثلاثية.", "Measures total cholesterol and is interpreted with LDL, HDL, and triglycerides."),
    "ldl": ("جزء من دهون الدم يرتبط تقييمه بخطر القلب والسياق الصحي العام.", "A blood lipid fraction interpreted in the context of cardiovascular risk and overall health."),
    "hdl": ("جزء من دهون الدم؛ يُقرأ ضمن صورة الدهون كاملة وليس منفردًا.", "A blood lipid fraction best interpreted as part of the full lipid profile."),
    "triglycerides": ("نوع من الدهون في الدم وقد تتأثر النتيجة بالطعام والصيام وعوامل أخرى.", "A type of blood fat that can be affected by meals, fasting, and other factors."),
    "sodium": ("أحد أهم أملاح الدم ويساعد في توازن السوائل ووظائف الأعصاب والعضلات.", "A major blood electrolyte important for fluid balance, nerves, and muscles."),
    "potassium": ("إلكتروليت مهم لعمل العضلات والقلب؛ العينة المتحللة قد تؤثر في القراءة أحيانًا.", "An electrolyte important for muscle and heart function; sample hemolysis can sometimes affect the result."),
    "chloride": ("إلكتروليت يشارك في توازن السوائل والأحماض والقواعد.", "An electrolyte involved in fluid and acid-base balance."),
    "calcium": ("معدن مهم للأعصاب والعضلات والعظام؛ يعتمد تفسيره على الألبومين وعوامل أخرى أحيانًا.", "A mineral important for nerves, muscles, and bone; interpretation can depend on albumin and other factors."),
    "co2": ("غالبًا يعكس البيكربونات ويساعد في تقييم توازن الأحماض والقواعد.", "Usually reflects bicarbonate and helps assess acid-base balance."),
    "ferritin": ("مؤشر لمخزون الحديد، لكنه قد يتغير أيضًا مع الالتهاب وعوامل أخرى.", "A marker of iron stores that can also change with inflammation and other factors."),
    "b12": ("يقيس مستوى فيتامين B12 الذي يرتبط بتكوين الدم ووظائف الأعصاب.", "Measures vitamin B12, which is related to blood-cell formation and nerve function."),
    "vitd": ("يقيس عادة 25-OH vitamin D لتقدير حالة فيتامين D.", "Usually measures 25-OH vitamin D to assess vitamin D status."),
    "tsh": ("هرمون تنظيمي للغدة الدرقية ويُفسر غالبًا مع Free T4 والسياق السريري.", "A thyroid-regulating hormone usually interpreted with Free T4 and clinical context."),
    "free_t4": ("يقيس الثيروكسين الحر ويُفسر عادةً مع TSH والأعراض والأدوية وعوامل أخرى.", "Measures free thyroxine and is usually interpreted with TSH, symptoms, medicines, and other factors."),
    "crp": ("مؤشر للالتهاب قد يرتفع لأسباب متعددة ولا يحدد مكان الالتهاب أو سببه بمفرده.", "An inflammation marker that can rise for many reasons and does not identify the site or cause by itself."),
    "esr": ("مؤشر غير نوعي للالتهاب يعتمد تفسيره على العمر والسياق والفحوص الأخرى.", "A non-specific inflammation marker interpreted with age, context, and other tests."),
    "magnesium": ("معدن مهم للأعصاب والعضلات والقلب، ويُفسر مستوى الدم ضمن السياق السريري.", "A mineral important for nerves, muscles, and the heart; blood levels are interpreted in clinical context."),
    "phosphate": ("معدن يرتبط بالعظام والطاقة ووظائف الكلى، ويُقرأ مع الكالسيوم ووظائف الكلى وعوامل أخرى.", "A mineral related to bone, energy, and kidney function, interpreted with calcium, kidney markers, and context."),
    "uric_acid": ("ناتج فضلات من استقلاب البيورينات ويُفسر ضمن سياق النقرس أو حصى الكلى وعوامل أخرى.", "A purine-breakdown waste product interpreted in the context of gout, kidney stones, and other factors."),
    "ggt": ("إنزيم يرتبط بالكبد والقنوات الصفراوية ويُقرأ عادةً مع ALP وبقية اختبارات الكبد.", "An enzyme related to the liver and bile ducts, usually interpreted with ALP and other liver tests."),
    "lipase": ("إنزيم هضمي يُنتج معظمه في البنكرياس ويُفسر مع الأعراض وبقية الفحوص.", "A digestive enzyme produced mainly by the pancreas and interpreted with symptoms and other tests."),
    "folate": ("يقيس الفولات المرتبط بتكوين الخلايا والدم؛ يجب تفسيره مع التغذية وB12 والسياق.", "Measures folate, which is involved in cell and blood formation; interpret with nutrition, B12, and context."),
    "anc": ("يمثل العدد المطلق للعدلات، وهو أدق من النسبة وحدها عند تقييم عدد العدلات.", "The absolute neutrophil count; more informative than percentage alone when assessing neutrophil quantity."),
    "troponin": ("بروتين قلبي يُستخدم عند الاشتباه بأذية عضلة القلب. لا تُفسر قيمة واحدة دون نوع الفحص وحد المختبر وتوقيت السحب والأعراض وتخطيط القلب.", "A cardiac protein used when heart-muscle injury is suspected. A single value should not be interpreted without the assay, lab limit, timing, symptoms, and ECG context."),
}
for _k, (_ar_desc, _en_desc) in EXTENDED_INFO.items():
    INDICATOR_INFO.setdefault(_k, {
        "what_ar": _ar_desc, "what_en": _en_desc,
        "low_ar": "القيمة أقل من نطاق المختبر في التقرير؛ لا تحدد السبب بمفردها.",
        "low_en": "The value is below the laboratory range on the report; it does not identify the cause by itself.",
        "high_ar": "القيمة أعلى من نطاق المختبر في التقرير؛ لا تحدد السبب بمفردها.",
        "high_en": "The value is above the laboratory range on the report; it does not identify the cause by itself.",
        "when_ar": "ناقش النتيجة مع الطبيب إذا كانت خارج النطاق، خاصةً إذا كانت جديدة أو متكررة أو ترافقها أعراض.",
        "when_en": "Discuss the result with a clinician if it is out of range, especially if it is new, persistent, or accompanied by symptoms.",
    })

# High-stakes marker: symptoms always outrank a single lab value.
INDICATOR_INFO.setdefault("troponin", {}).update({
    "when_ar": "إذا لديك ألم صدر شديد أو ضيق تنفس شديد أو إغماء/عدم استجابة، اطلب الطوارئ فورًا بغض النظر عن قراءة التروبونين. وإلا فناقش أي نتيجة خارج نطاق المختبر مع الطبيب دون تأخير.",
    "when_en": "If you have severe chest pain, severe breathing difficulty, or fainting/unresponsiveness, seek emergency help immediately regardless of the troponin value. Otherwise, discuss any out-of-range result promptly with a clinician.",
})

# V148: specialist references layered on top of the government/NIH primary source.
# These sources provide context and guideline-level interpretation. They NEVER
# replace the patient's own laboratory reference interval for high/low/normal.
SPECIALIST_SOURCES = {
    "glucose": [
        {"name":"ADA — Standards of Care in Diabetes 2026: Diagnosis & Classification","url":"https://diabetesjournals.org/care/article/49/Supplement_1/S27/163926/2-Diagnosis-and-Classification-of-Diabetes","organization":"American Diabetes Association","authority":"specialty_guideline","use_ar":"مرجع تخصصي حديث لمعايير تشخيص اضطرابات سكر الدم وحدود استخدام الجلوكوز وHbA1c.","use_en":"Current specialty guideline for diagnostic use and limitations of glucose and HbA1c."},
    ],
    "hba1c": [
        {"name":"ADA — Standards of Care in Diabetes 2026: Diagnosis & Classification","url":"https://diabetesjournals.org/care/article/49/Supplement_1/S27/163926/2-Diagnosis-and-Classification-of-Diabetes","organization":"American Diabetes Association","authority":"specialty_guideline","use_ar":"مرجع تخصصي حديث يوضح استخدام HbA1c، الحاجة للتأكيد في بعض الحالات، والعوامل التي قد تؤثر في دقته.","use_en":"Current guideline covering HbA1c use, confirmatory testing, and factors that can affect accuracy."},
    ],
    "creatinine": [
        {"name":"KDIGO 2024 — CKD Evaluation and Management","url":"https://kdigo.org/guidelines/ckd-evaluation-and-management/","organization":"KDIGO","authority":"international_specialty_guideline","use_ar":"مرجع عالمي تخصصي لتقييم وظائف الكلى وتصنيف مرض الكلى المزمن ضمن السياق السريري.","use_en":"International kidney guideline for CKD evaluation, classification, and clinical context."},
    ],
    "egfr": [
        {"name":"KDIGO 2024 — CKD Evaluation and Management","url":"https://kdigo.org/guidelines/ckd-evaluation-and-management/","organization":"KDIGO","authority":"international_specialty_guideline","use_ar":"مرجع عالمي تخصصي لاستخدام eGFR في تقييم وتصنيف وظائف الكلى مع مراعاة السياق والقياسات المتكررة.","use_en":"International kidney guideline for interpreting eGFR in CKD evaluation and classification."},
    ],
    "bun": [
        {"name":"KDIGO 2024 — CKD Evaluation and Management","url":"https://kdigo.org/guidelines/ckd-evaluation-and-management/","organization":"KDIGO","authority":"international_specialty_guideline","use_ar":"مرجع تخصصي لوضع مؤشرات وظائف الكلى ضمن تقييم كُلوي متكامل بدل تفسير قيمة منفردة.","use_en":"Specialty guideline supporting integrated interpretation of kidney markers rather than isolated values."},
    ],
    "urea": [
        {"name":"KDIGO 2024 — CKD Evaluation and Management","url":"https://kdigo.org/guidelines/ckd-evaluation-and-management/","organization":"KDIGO","authority":"international_specialty_guideline","use_ar":"مرجع تخصصي لوضع مؤشرات وظائف الكلى ضمن تقييم كُلوي متكامل بدل تفسير قيمة منفردة.","use_en":"Specialty guideline supporting integrated interpretation of kidney markers rather than isolated values."},
    ],
    "iron": [
        {"name":"NIH ODS — Iron: Health Professional Fact Sheet","url":"https://ods.od.nih.gov/factsheets/Iron-HealthProfessional/","organization":"NIH / Office of Dietary Supplements","authority":"government","use_ar":"مرجع NIH تخصصي عن الحديد، الاحتياج الغذائي، النقص، التداخلات ومخاطر الإفراط بالمكملات.","use_en":"NIH professional reference for iron requirements, deficiency, interactions, and supplement safety."},
    ],
    "ferritin": [
        {"name":"WHO — Guideline on Ferritin Concentrations","url":"https://www.who.int/publications/i/item/9789240000124","organization":"World Health Organization","authority":"international_guideline","use_ar":"إرشاد WHO لاستخدام الفيريتين كمؤشر لحالة الحديد مع التأكيد على تفسيره ضمن السياق.","use_en":"WHO guideline on using ferritin to assess iron status and interpret it in context."},
        {"name":"NIH ODS — Iron: Health Professional Fact Sheet","url":"https://ods.od.nih.gov/factsheets/Iron-HealthProfessional/","organization":"NIH / Office of Dietary Supplements","authority":"government","use_ar":"مرجع NIH عن الحديد والنقص والمصادر الغذائية والمكملات.","use_en":"NIH reference for iron deficiency, dietary sources, and supplementation."},
    ],
    "b12": [
        {"name":"NIH ODS — Vitamin B12: Health Professional Fact Sheet","url":"https://ods.od.nih.gov/factsheets/VitaminB12-HealthProfessional/","organization":"NIH / Office of Dietary Supplements","authority":"government","use_ar":"مرجع NIH المهني لفيتامين B12 وأسباب النقص والعوامل المؤثرة والتداخلات.","use_en":"NIH professional reference for vitamin B12 deficiency, risk factors, and interactions."},
    ],
    "vitd": [
        {"name":"NIH ODS — Vitamin D: Health Professional Fact Sheet","url":"https://ods.od.nih.gov/factsheets/VitaminD-HealthProfessional/","organization":"NIH / Office of Dietary Supplements","authority":"government","use_ar":"مرجع NIH المهني لفيتامين D وحالة 25(OH)D والمصادر والمكملات والسلامة.","use_en":"NIH professional reference for vitamin D status, 25(OH)D, sources, supplementation, and safety."},
    ],
    "tsh": [
        {"name":"American Thyroid Association — Thyroid Function Tests","url":"https://www.thyroid.org/thyroid-function-tests/","organization":"American Thyroid Association","authority":"specialty_society","use_ar":"مرجع تخصصي يوضح مكانة TSH ضمن تقييم وظائف الغدة وضرورة قراءة اختبارات الغدة معًا عند الحاجة.","use_en":"Specialty reference explaining TSH in thyroid assessment and when other thyroid tests add context."},
    ],
}

GROUP_SPECIALIST_SOURCES = {
    "lipids": [
        {"name":"AHA/ACC — 2026 Guideline on the Management of Dyslipidemia","url":"https://professional.heart.org/en/science-news/2026-guideline-on-the-management-of-dyslipidemia","organization":"American Heart Association / American College of Cardiology","authority":"specialty_guideline","use_ar":"الإرشاد التخصصي الأحدث لتقييم وإدارة اضطرابات الدهون، بما يشمل LDL والدهون الثلاثية وعوامل الخطورة.","use_en":"Current specialty guideline for dyslipidemia, LDL, triglycerides, and cardiovascular risk assessment."},
    ],
    "liver": [
        {"name":"AASLD — How to Approach Elevated Liver Enzymes","url":"https://www.aasld.org/liver-fellow-network/core-series/back-basics/how-approach-elevated-liver-enzymes","organization":"American Association for the Study of Liver Diseases","authority":"specialty_society","use_ar":"مرجع تخصصي لتفسير أنماط إنزيمات الكبد وربط ALT وAST وALP والبيليروبين ضمن نمط متكامل.","use_en":"Specialty reference for interpreting liver-enzyme patterns across ALT, AST, ALP, and bilirubin."},
    ],
}

# V251: a direct MedlinePlus page for every analyte that only had a generic panel link, plus a second
# independent reference (Testing.com, NKF, NIH ...) shown under "additional references".
import trusted_sources_wiring as _tsw
_V251_DIRECT, _V251_EXTRA = _tsw.blood_direct_and_extra()
for _k, _v in _V251_DIRECT.items():
    DIRECT_SOURCES.setdefault(_k, _v)
for _k, _rows in _V251_EXTRA.items():
    SPECIALIST_SOURCES.setdefault(_k, [])
    SPECIALIST_SOURCES[_k] = list(SPECIALIST_SOURCES[_k]) + [r for r in _rows if r["url"] not in {x.get("url") for x in SPECIALIST_SOURCES[_k]}]


def specialist_sources_for_key(key):
    key = str(key or "").strip().lower()
    out = [dict(x) for x in SPECIALIST_SOURCES.get(key, [])]
    group = test_group(key)
    out.extend(dict(x) for x in GROUP_SPECIALIST_SOURCES.get(group, []))
    # De-duplicate by URL while preserving order.
    seen, clean = set(), []
    for src in out:
        url = str(src.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url); clean.append(src)
    return clean

def source_for_key(key):
    key = str(key or "").strip().lower()
    if key in DIRECT_SOURCES:
        src = dict(DIRECT_SOURCES[key])
    elif key in {"hgb","wbc","rbc","hct","mcv","mch","mchc","plt","mpv","neut","lymph","mono","eos","baso","rdw"}:
        src = dict(PANEL_SOURCES["cbc"])
    elif key in TEST_GROUPS["lipids"]:
        src = dict(PANEL_SOURCES["lipids"])
    elif key in TEST_GROUPS["liver"]:
        src = dict(PANEL_SOURCES["liver"])
    elif key in TEST_GROUPS["electrolytes"]:
        src = dict(PANEL_SOURCES["electrolytes"])
    elif key in TEST_GROUPS["kidney"] or key in TEST_GROUPS["glucose"]:
        src = dict(PANEL_SOURCES["metabolic"])
    else:
        src = dict(PANEL_SOURCES["general"])
    src["additional_sources"] = specialist_sources_for_key(key)
    return src


def build_medical_source_summary(indicators, lang="ar"):
    """Return de-duplicated authoritative references used by indicator cards."""
    ar = lang == "ar"
    seen, out = set(), []
    for item in indicators or []:
        src = item.get("source") if isinstance(item, dict) else None
        if not isinstance(src, dict):
            continue
        url = str(src.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        out.append({
            "name": str(src.get("name") or "Medical source"),
            "url": url,
            "organization": str(src.get("organization") or ""),
            "authority": str(src.get("authority") or "trusted"),
            "why": str(src.get("use_ar" if ar else "use_en") or ""),
        })
        for extra in (src.get("additional_sources") or []):
            if not isinstance(extra, dict):
                continue
            eurl = str(extra.get("url") or "").strip()
            if not eurl or eurl in seen:
                continue
            seen.add(eurl)
            out.append({
                "name": str(extra.get("name") or "Medical source"),
                "url": eurl,
                "organization": str(extra.get("organization") or ""),
                "authority": str(extra.get("authority") or "trusted"),
                "why": str(extra.get("use_ar" if ar else "use_en") or ""),
            })
    return out


def build_pattern_insights(results, lang="ar"):
    """Describe relationships between values without diagnosing a disease."""
    ar = lang == "ar"
    by_group = {}
    for r in results or []:
        group = test_group(r.get("key"))
        by_group.setdefault(group, []).append(r)
    out = []
    for group, rows in by_group.items():
        abnormal = [r for r in rows if r.get("status") in {"low","high"}]
        if len(abnormal) < 2:
            continue
        label = GROUP_LABELS.get(group, ("مجموعة مؤشرات", "Marker group"))[0 if ar else 1]
        names = [(r.get("name_ar") if ar else r.get("name_en")) for r in abnormal][:5]
        out.append({
            "group": group, "label": label, "keys": [r.get("key") for r in abnormal],
            "title": ("نمط مترابط في " + label) if ar else ("Related pattern in " + label),
            "text": (("خرجت عدة مؤشرات مرتبطة عن نطاق المختبر معًا (%s). الأفضل تفسيرها كمجموعة مع السياق والأعراض بدل قراءة كل رقم منفردًا." % "، ".join(names)) if ar else
                     ("Several related markers are outside the laboratory range together (%s). They are better interpreted as a group with symptoms and context rather than as isolated numbers." % ", ".join(names))),
        })
    # A few high-value relationships get an additional neutral explanation.
    by = {r.get("key"): r for r in results or []}
    if by.get("hgb") and by.get("mcv") and by["hgb"].get("status")=="low" and by["mcv"].get("status") in {"low","high"}:
        out.insert(0,{
            "group":"red_cells","label":GROUP_LABELS["red_cells"][0 if ar else 1],"keys":["hgb","mcv"],
            "title":"الهيموغلوبين وMCV يُقرآن معًا" if ar else "Hemoglobin and MCV are interpreted together",
            "text":"انخفاض الهيموغلوبين مع تغيّر حجم الكريات يعطي نمطًا أكثر فائدة للطبيب من كل قيمة وحدها، لكنه لا يحدد السبب دون تاريخ مرضي وفحوص إضافية." if ar else "Low hemoglobin together with a change in red-cell size is more informative than either value alone, but it does not identify a cause without history and additional testing."
        })
    return out[:6]

def build_relationships(results, lang="ar"):
    ar = lang == "ar"
    present = {r.get("key") for r in results or []}
    edges = []
    templates = [
        ("hgb","hct","يحملان معلومات مترابطة عن كتلة كريات الدم الحمراء","Both reflect related aspects of red-cell mass"),
        ("hgb","mcv","يُقرأ مستوى الهيموغلوبين مع حجم الكريات لفهم نمط كريات الدم الحمراء","Hemoglobin and cell size are read together to understand the red-cell pattern"),
        ("mcv","mch","مؤشران مرتبطان بحجم الكرية ومحتواها من الهيموغلوبين","Related indices of cell size and hemoglobin content"),
        ("wbc","neut","العدلات جزء من كريات الدم البيضاء","Neutrophils are part of the white-cell count"),
        ("wbc","lymph","اللمفاويات جزء من كريات الدم البيضاء","Lymphocytes are part of the white-cell count"),
        ("creatinine","egfr","يُستخدم الكرياتينين في تقدير eGFR","Creatinine is used when estimating eGFR"),
        ("alt","ast","إنزيمان يُقرآن غالبًا معًا ضمن سياق الكبد والأنسجة الأخرى","Two enzymes commonly reviewed together in liver and tissue context"),
        ("albumin","total_protein","الألبومين جزء من البروتين الكلي","Albumin contributes to total protein"),
        ("chol_total","ldl","LDL أحد مكونات صورة الدهون المرتبطة بالكوليسترول","LDL is part of the cholesterol-related lipid profile"),
        ("chol_total","hdl","HDL أحد مكونات صورة الدهون المرتبطة بالكوليسترول","HDL is part of the cholesterol-related lipid profile"),
        ("glucose","hba1c","الجلوكوز لقطة زمنية وHbA1c يعكس متوسطًا أطول","Glucose is a point-in-time value while HbA1c reflects a longer average"),
        ("sodium","potassium","إلكتروليتان مهمان ويُفسران ضمن توازن السوائل ووظائف الجسم","Two key electrolytes interpreted in fluid and physiologic context"),
    ]
    for a,b,ta,te in templates:
        if a in present and b in present:
            edges.append({"from":a,"to":b,"text":ta if ar else te})
    return edges[:12]

def build_doctor_questions(indicators, context=None, lang="ar"):
    """Generate 3–5 neutral questions tailored to the actual lab result."""
    ar = lang == "ar"
    inds = [i for i in (indicators or []) if isinstance(i, dict)]
    abnormal = [i for i in inds if i.get("status") in {"low", "high"}]
    unclear = [i for i in inds if i.get("status") == "unclassified" or i.get("attention_level") == "needs_confirmation"]
    urgent = [i for i in inds if i.get("attention_level") in {"urgent", "emergency"}]
    groups = {str(i.get("group") or "") for i in inds}
    ctx = normalize_analysis_context(context)
    q = []
    if urgent:
        q.append("هل أحتاج تقييمًا اليوم أو الآن بسبب هذه النتيجة؟" if ar else "Do I need evaluation today or right now because of this result?")
    if abnormal:
        name = str(abnormal[0].get("name") or abnormal[0].get("key") or "النتيجة")
        q.append(("ما الأسباب الأكثر احتمالًا لنتيجة %s في حالتي، وما الذي يساعد على التفريق بينها؟" if ar else "What are the most likely explanations for my %s result in my situation, and what helps distinguish them?") % name)
    if unclear:
        name = str(unclear[0].get("name") or unclear[0].get("key") or "هذا الفحص")
        q.append(("ما النطاق المرجعي الصحيح لـ %s في مختبري، وهل تحتاج القيمة لإعادة تأكيد؟" if ar else "What is the correct laboratory reference range for %s, and does the value need confirmation?") % name)
    if "nutrients" in groups or "red_cells" in groups:
        q.append("هل تنصح بمراجعة فحوص الحديد/الفيريتين أو B12/الفولات لفهم صورة الدم بشكل أفضل؟" if ar else "Would reviewing iron/ferritin or B12/folate help put the blood-count pattern in context?")
    if "thyroid" in groups:
        q.append("هل تحتاج نتائج الغدة أن تُقرأ مع TSH وFree T4 معًا أو مع أدوية الغدة التي أستخدمها؟" if ar else "Should the thyroid results be interpreted together with TSH/Free T4 and any thyroid medicine I use?")
    if "kidney" in groups:
        q.append("هل أحتاج إعادة وظائف الكلى أو مقارنتها بنتائج سابقة مع مراعاة الترطيب والأدوية؟" if ar else "Should kidney markers be repeated or compared with prior results while considering hydration and medicines?")
    if "liver" in groups:
        q.append("هل نمط إنزيمات الكبد يحتاج إعادة فحص أو مراجعة الأدوية والمكملات التي أستخدمها؟" if ar else "Does the liver-test pattern need repeat testing or a review of medicines and supplements?")
    if groups.intersection({"glucose", "lipids"}) or any(str(i.get("key") or "") in _CONTEXT_SENSITIVE_KEYS for i in inds):
        if ctx.get("fasting_status") == "unknown":
            q.append("هل كان هذا الفحص يحتاج صيامًا، وهل يؤثر ذلك على تفسير النتيجة؟" if ar else "Did this test require fasting, and does that affect how the result should be interpreted?")
    q.append("هل توجد نتيجة تحتاج إعادة فحص، ومتى يكون التوقيت المناسب لذلك؟" if ar else "Does any result need repeat testing, and when would be the right time?")
    q.append("هل توجد أدوية أو مكملات أو حالة صحية قد تفسر جزءًا من هذه النتائج؟" if ar else "Could any medicine, supplement, or health condition explain part of these results?")
    clean = []
    for item in q:
        if item and item not in clean:
            clean.append(item)
    return clean[:5]


def build_doctor_summary(results, patterns=None, lang="ar", age=None, gender="", context=None, level=None, questions=None):
    ar = lang == "ar"
    abnormal = [r for r in results or [] if r.get("status") in {"low","high"}]
    unclassified = [r for r in results or [] if r.get("status")=="unclassified"]
    ctx = normalize_analysis_context(context)
    lines = ["ملخص التحاليل للعيادة" if ar else "Lab summary for clinic"]
    if age not in (None,""):
        lines.append(("العمر: %s سنة" if ar else "Age: %s years") % age)
    if gender:
        lines.append(("الجنس: " if ar else "Sex: ") + ({"m":"ذكر","f":"أنثى"}.get(str(gender),str(gender)) if ar else {"m":"Male","f":"Female"}.get(str(gender),str(gender))))
    if level:
        level_label_ar = {"normal":"ضمن النطاق","see_doctor":"مراجعة طبية","urgent":"تقييم عاجل","emergency":"طوارئ","unclassified":"يحتاج تأكيد"}.get(level, level)
        level_label_en = {"normal":"Within range","see_doctor":"Medical review","urgent":"Urgent evaluation","emergency":"Emergency","unclassified":"Needs confirmation"}.get(level, level)
        lines.append(("مستوى المتابعة: " if ar else "Follow-up level: ") + (level_label_ar if ar else level_label_en))
    ctx_parts = []
    fasting_map_ar = {"fasting":"صائم","non_fasting":"غير صائم","not_required":"الصيام غير مطلوب/غير منطبق","unknown":"غير محدد"}
    fasting_map_en = {"fasting":"fasting","non_fasting":"not fasting","not_required":"fasting not required/not applicable","unknown":"not specified"}
    if ctx.get("fasting_status") != "unknown":
        ctx_parts.append(("الصيام: " if ar else "Fasting: ") + (fasting_map_ar if ar else fasting_map_en)[ctx["fasting_status"]])
    if ctx.get("sample_time"):
        ctx_parts.append(("وقت السحب: " if ar else "Sample time: ") + ctx["sample_time"])
    if ctx.get("notes"):
        ctx_parts.append(("ملاحظة المستخدم: " if ar else "User note: ") + ctx["notes"])
    if ctx_parts:
        lines.append("سياق الفحص:" if ar else "Test context:")
        lines.extend("- "+x for x in ctx_parts)
    if abnormal:
        lines.append("القيم المصنفة خارج نطاق المختبر/التصنيف المطبوع:" if ar else "Values classified outside the laboratory range/printed status:")
        for r in abnormal:
            name=r.get("name_ar") if ar else r.get("name_en")
            rng=(f"{r.get('low')}–{r.get('high')}" if r.get('low') is not None and r.get('high') is not None else ("غير متاح" if ar else "not available"))
            status=("منخفض" if r.get("status")=="low" else "مرتفع") if ar else ("low" if r.get("status")=="low" else "high")
            critical = ("؛ معلّم كحرج في تقرير المختبر" if ar else "; marked critical by the laboratory") if r.get("reported_critical") else ""
            lines.append(f"- {name}: {r.get('value')} {r.get('unit') or ''} ({status}; ref {rng}{critical})")
    else:
        lines.append("لا توجد قيم مصنفة خارج النطاق ضمن القيم المقروءة." if ar else "No classified values are outside range among the extracted markers.")
    if unclassified:
        names=", ".join((r.get("name_ar") if ar else r.get("name_en")) for r in unclassified[:8])
        lines.append(("قيم تحتاج تأكيد الوحدة/النطاق: " if ar else "Values needing unit/range confirmation: ")+names)
    if patterns:
        lines.append("أنماط مترابطة:" if ar else "Related patterns:")
        for p in patterns[:3]: lines.append("- "+str(p.get("title") or ""))
    if questions:
        lines.append("أسئلة مقترحة للطبيب:" if ar else "Suggested questions for the clinician:")
        for item in questions[:5]: lines.append("- "+str(item))
    lines.append("هذا الملخص لا يمثل تشخيصًا؛ يُراجع مع التقرير الأصلي والتاريخ المرضي والأعراض." if ar else "This summary is not a diagnosis; review it with the original report, medical history, and symptoms.")
    return "\n".join(lines)

def compare_with_history(current_indicators, prior_tests, lang="ar", current_report_meta=None):
    """Compare current markers with multiple prior saved tests using matching units.

    Direction is descriptive only (increased/decreased/about the same), not a
    clinical improvement/worsening label. The UI can render the returned series
    as a small sparkline without implying diagnosis.
    """
    ar = lang == "ar"
    history = []
    for item in prior_tests or []:
        if not isinstance(item, dict):
            continue
        data = item.get("data") or {}
        inds = data.get("indicators") if isinstance(data, dict) else None
        if inds:
            history.append(item)
    if not history:
        return {"available":False,"items":[],"message":"لا يوجد تحليل سابق محفوظ للمقارنة." if ar else "No previous saved test is available for comparison."}

    items=[]
    for cur in current_indicators or []:
        key=str(cur.get("key") or "")
        unit=str(cur.get("unit") or "")
        try:
            newv=float(cur.get("value"))
        except (TypeError,ValueError):
            continue
        series=[]
        # Database results are normally newest first. Walk oldest -> newest so
        # the sparkline reads naturally from left to right.
        for old_test in reversed(history[:8]):
            old_inds=(old_test.get("data") or {}).get("indicators") or []
            old=next((x for x in old_inds if isinstance(x,dict) and str(x.get("key") or "")==key),None)
            if not old or str(old.get("unit") or "") != unit:
                continue
            try:
                oldv=float(old.get("value"))
            except (TypeError,ValueError):
                continue
            old_data = old_test.get("data") or {}
            old_meta = old_data.get("report_meta") if isinstance(old_data, dict) else {}
            old_meta = old_meta if isinstance(old_meta, dict) else {}
            old_when = old_meta.get("sample_date") or old_meta.get("report_date") or old_test.get("timestamp") or ""
            series.append({"value":oldv,"timestamp":old_when})
        if not series:
            continue
        previous=series[-1]["value"]
        diff=newv-previous
        tol=max(abs(previous)*0.02,1e-9)
        direction="stable" if abs(diff)<=tol else ("up" if diff>0 else "down")
        current_meta = current_report_meta if isinstance(current_report_meta, dict) else {}
        current_when = current_meta.get("sample_date") or current_meta.get("report_date") or "current"
        series.append({"value":newv,"timestamp":current_when})
        items.append({
            "key":key,"name":cur.get("name"),"previous":previous,"current":newv,"unit":unit,"direction":direction,
            "label":({"up":"ارتفع","down":"انخفض","stable":"قريب من السابق"}[direction] if ar else {"up":"increased","down":"decreased","stable":"about the same"}[direction]),
            "series":series[-6:],
        })
    return {"available":bool(items),"items":items[:12],"message":"" if items else ("لا توجد مؤشرات مشتركة بوحدات متطابقة للمقارنة." if ar else "No shared markers with matching units were available for comparison.")}

CBC_SOURCE = {
    "name": "MedlinePlus — Complete Blood Count (CBC)",
    "url": "https://medlineplus.gov/lab-tests/complete-blood-count-cbc/",
}


def _describe_results_v142_base(results, lang="ar"):
    """Builds localized per-indicator detail for the interactive card/table."""
    ar = lang == "ar"
    out = []
    for r in results:
        key = r["key"]
        info = INDICATOR_INFO.get(key, {})
        name = r["name_ar"] if ar else r["name_en"]
        status = r["status"]
        if status == "normal":
            meaning = ("النتيجة ضمن النطاق الطبيعي لهذا المؤشر." if ar
                       else "The result is within the normal range for this indicator.")
        elif status == "low":
            meaning = info.get("low_ar") or ("قد تشير النتيجة إلى انخفاض %s — راجع طبيبك لتأكيد السبب." % name)
            if not ar:
                meaning = info.get("low_en") or ("The result may indicate a low %s — see your doctor to confirm the cause." % name)
        elif status == "high":
            meaning = info.get("high_ar") or ("قد تشير النتيجة إلى ارتفاع %s — راجع طبيبك لتأكيد السبب." % name)
            if not ar:
                meaning = info.get("high_en") or ("The result may indicate a high %s — see your doctor to confirm the cause." % name)
        else:
            meaning = ("لم يُصنّف المؤشر لأن الوحدة أو النطاق المرجعي غير واضحين. اعتمد نطاق المختبر الظاهر في التقرير أو راجع الطبيب." if ar
                       else "This indicator was not classified because its unit or reference range is unclear. Use the laboratory range shown on the report or ask a clinician.")
        what = info.get("what_ar" if ar else "what_en", "")
        if key in {"neut", "lymph"}:
            unit = str(r.get("unit") or "")
            is_percent = unit == "%"
            if key == "neut":
                what = ("نسبة العدلات — النوع الأكثر شيوعاً من كريات الدم البيضاء." if is_percent else "عدد العدلات المطلق — النوع الأكثر شيوعاً من كريات الدم البيضاء.") if ar else ("Neutrophil percentage — the most common type of white blood cells." if is_percent else "Absolute neutrophil count — the most common type of white blood cells.")
            else:
                what = ("نسبة اللمفاويات — نوع من كريات الدم البيضاء مهم للمناعة." if is_percent else "عدد اللمفاويات المطلق — نوع من كريات الدم البيضاء مهم للمناعة.") if ar else ("Lymphocyte percentage — a type of white blood cell important for immunity." if is_percent else "Absolute lymphocyte count — a type of white blood cell important for immunity.")
        out.append({
            "key": key, "name": name, "unit": r["unit"],
            "value": r["value"], "low": r["low"], "high": r["high"], "status": status,
            "what": what,
            "meaning": meaning,
            "when": info.get("when_ar" if ar else "when_en", ""),
            "symptoms": (CBC_ASSOCIATED_SYMPTOMS.get(key, {}).get((status + ("_ar" if ar else "_en")), []) if status in {"low", "high"} else []),
            "symptoms_context": (
                "هذه أعراض قد تترافق مع بعض الأسباب المحتملة لهذا النمط، وليست أعراضًا يسببها الرقم وحده."
                if ar else
                "These symptoms may accompany some causes of this pattern; they are not symptoms caused by the number itself."
            ),
            "source": source_for_key(key),
            "group": test_group(key),
            "group_label": GROUP_LABELS.get(test_group(key), ("أخرى", "Other"))[0 if ar else 1],
            "reference_source": r.get("reference_source") or "unclassified",
            "reference_source_label": (("نطاق المختبر من التقرير" if r.get("reference_source")=="lab_reference" else "نطاق تطبيقي احتياطي للبالغين" if r.get("reference_source")=="app_adult_reference" else "النطاق غير واضح") if ar else ("Laboratory range from report" if r.get("reference_source")=="lab_reference" else "Adult app fallback range" if r.get("reference_source")=="app_adult_reference" else "Reference range unclear")),
        })
    return out


def summary_text(level, lang="ar"):
    ar = lang == "ar"
    if level == "unclassified":
        return ("تعذر تصنيف بعض القيم بأمان لعدم وضوح الوحدة أو النطاق المرجعي. استخدم نطاق المختبر الظاهر في التقرير أو راجع الطبيب." if ar
                else "Some values could not be safely classified because the unit or reference range is unclear. Use the laboratory range shown on the report or ask a clinician.")
    if level == "emergency":
        return ("توجد قيم حرجة تتطلب تقييمًا فوريًا — يُنصح بالتوجه إلى أقرب طوارئ الآن." if ar
                else "There are critical values requiring immediate evaluation — go to the nearest emergency department now.")
    if level == "urgent":
        return ("توجد قيم تحتاج تقييمًا طبيًا عاجلًا خلال ساعات — راجع أقرب منشأة صحية." if ar
                else "There are values that need prompt medical evaluation within hours — visit the nearest health facility.")
    if level == "see_doctor":
        return ("توجد مؤشرات خارج النطاق المرجعي المستخدم — يُنصح بمناقشتها مع الطبيب مع التقرير الأصلي والسياق الصحي." if ar
                else "Some indicators are outside the reference range used — discuss them with a clinician alongside the original report and clinical context.")
    return ("جميع المؤشرات التي أمكن تصنيفها ضمن النطاق المرجعي المستخدم. لا يعني ذلك أن التحليل وحده يقيّم الصحة بالكامل." if ar
            else "All markers that could be classified are within the reference range used. This does not mean the lab report alone fully assesses health.")


def disclaimer_text(lang="ar"):
    return ("للتوعية فقط — لا يُعد هذا تشخيصًا طبيًا. تختلف النطاقات المرجعية حسب المختبر والعمر، ويُنصح بمراجعة الطبيب لتفسير النتائج في سياق حالتك." if lang == "ar"
            else "Awareness only — not a medical diagnosis. Reference ranges vary by laboratory and age; confirm any result with your doctor.")


def child_note_text(lang="ar"):
    return ("نطاقات الأطفال تختلف عن نطاقات البالغين — ننصح بعرض النتيجة على طبيب أطفال." if lang == "ar"
            else "Pediatric ranges differ from adult ranges — please show the report to a pediatrician.")


def generate_blood_chart(results):
    """Render a unit-safe CBC chart using each test's own reference range.

    CBC analytes use incompatible units and scales, so plotting raw HGB, WBC,
    platelets, etc. on one numeric x-axis is misleading. Each classified value
    is normalized to its own laboratory/application range where 0=low limit and
    1=high limit. Unclassified rows are intentionally omitted from the chart.
    """
    if not results:
        return None
    rows = []
    for r in results:
        lo, hi = r.get("low"), r.get("high")
        try:
            value = float(r.get("value"))
            lo = float(lo); hi = float(hi)
        except (TypeError, ValueError):
            continue
        if hi <= lo or r.get("status") == "unclassified":
            continue
        rows.append((r, (value - lo) / (hi - lo)))
    if not rows:
        return None

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, max(2.5, 0.6 * len(rows) + 1)))
    positions = list(range(len(rows)))
    labels = [r["name_en"] for r, _ in rows]
    rel_values = [rel for _, rel in rows]
    for i, (r, rel) in enumerate(rows):
        ax.plot([0, 1], [i, i], color="#c8d6e5", lw=7, solid_capstyle="round", zorder=1)
        color = "#27ae60" if r["status"] == "normal" else "#e74c3c"
        ax.plot(rel, i, "o", color=color, ms=13, zorder=3)
        unit = str(r.get("unit") or "")
        label = f"{r['value']} {unit}".strip()
        ax.annotate(label, (rel, i), textcoords="offset points", xytext=(7, 0), fontsize=8, color="#2c3e50")

    min_x = min([-0.25] + rel_values)
    max_x = max([1.25] + rel_values)
    pad = max(0.1, (max_x - min_x) * 0.08)
    ax.set_xlim(min_x - pad, max_x + pad)
    ax.axvline(0, color="#95a5a6", lw=1, alpha=0.6)
    ax.axvline(1, color="#95a5a6", lw=1, alpha=0.6)
    ax.set_yticks(positions)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("Relative to each test's reference range (0 = low limit, 1 = high limit)")
    ax.set_title("CBC — Relative to Reference Range")
    ax.grid(True, axis="x", alpha=0.25)
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf

# ---------------------------------------------------------------------------
# V143 — full-report extraction + all-row classification + focus guidance.
# These overrides deliberately preserve V142 behaviour for known markers while
# retaining unfamiliar laboratory rows when the report itself provides a value
# and reference range/status.  Unknown rows are never given guessed ranges.
import hashlib as _hashlib

_V142_analyze_blood = _analyze_blood_v142_base
_V142_describe_results = _describe_results_v142_base


def _v143_status(text):
    t = _norm(text or "").strip()
    if t in {"normal", "طبيعي", "طبيعية"}: return "normal"
    if t in {"low", "منخفض", "منخفضة"}: return "low"
    if t in {"high", "مرتفع", "مرتفعة"}: return "high"
    if "critical" in t or "حرج" in t: return "high"
    return ""


def _v143_is_critical(text):
    t = _norm(text or "").strip()
    return bool("critical" in t or "حرج" in t)


def _v143_generic_key(name):
    clean = _norm(name or "")[:300]
    return "other_" + _hashlib.sha1(clean.encode("utf-8", "ignore"), usedforsecurity=False).hexdigest()[:12]


def _v143_safe_name(name):
    name = re.sub(r"\s+", " ", str(name or "")).strip()
    return name[:180]


def _v143_safe_unit(unit):
    raw = re.sub(r"\s+", " ", str(unit or "")).strip()[:32]
    if not raw or not re.fullmatch(r"[A-Za-z0-9%µμuU/.*^+\- ]{1,32}", raw):
        return ""
    return raw


def _v143_pipe_rows(raw_text):
    """Read generic vision/OCR rows: TEST | VALUE | UNIT | LOW | HIGH | STATUS."""
    rows = []
    for raw in re.split(r"[\r\n]+", str(raw_text or "")):
        if "|" not in raw:
            continue
        parts = [p.strip() for p in raw.split("|")]
        if len(parts) < 2:
            continue
        name = _v143_safe_name(parts[0])
        if not name or _norm(name).startswith("age "):
            continue
        try:
            value = float(str(parts[1]).replace(",", "."))
        except (TypeError, ValueError):
            continue
        raw_unit = _v143_safe_unit(parts[2] if len(parts) > 2 else "")
        normalized_unit = _normalize_unit(raw_unit)
        key = _key_from_test_name(name, normalized_unit)
        known_key = bool(key)
        if not key:
            key = _v143_generic_key(name)
        def num(i):
            if len(parts) <= i or not parts[i]: return None
            try: return float(parts[i].replace(",", "."))
            except (TypeError, ValueError): return None
        lo, hi = num(3), num(4)
        if lo is not None and hi is not None and lo > hi:
            lo, hi = hi, lo
        reported = _v143_status(parts[5] if len(parts) > 5 else "")
        rows.append({
            "key": key, "name": name, "value": value,
            "unit": normalized_unit if known_key else raw_unit,
            "reference_low": lo, "reference_high": hi,
            "reported_status": reported,
            "reported_critical": _v143_is_critical(parts[5] if len(parts) > 5 else ""),
        })
    return rows


def _v143_native_rows(raw_text):
    """Reconstruct every numeric laboratory row from native PDF table text."""
    lines = [str(x).strip() for x in re.split(r"[\r\n]+", str(raw_text or "")) if str(x).strip()]
    interp_words = {"normal", "low", "high", "critical", "abnormal", "طبيعي", "طبيعية", "منخفض", "منخفضة", "مرتفع", "مرتفعة"}
    stop_markers = {"reference range", "interpretation", "result", "test name", "المدى الطبيعي", "التصنيف", "النتيجة", "اسم الفحص"}
    rows = []
    i = 0
    while i < len(lines) - 2:
        low_line = _norm(lines[i])
        lo, hi = _looks_like_simple_range(lines[i])
        categorical = bool(re.search(r"(?:normal|deficien|insufficien|sufficien|prediabetes|diabetes|male\s*:|female\s*:)", low_line, re.I))
        interp_idx = None
        for cand in range(i + 1, min(len(lines), i + 6)):
            if _norm(lines[cand]) in interp_words:
                interp_idx = cand; break
            if _norm(lines[cand]) in stop_markers:
                break
        if (lo is None and not categorical) or interp_idx is None:
            i += 1; continue
        result_idx = interp_idx + 1
        if result_idx >= len(lines): break
        value, unit = _result_line_parts(lines[result_idx])
        if value is None:
            i += 1; continue
        name_parts = []
        k = result_idx + 1
        while k < len(lines) and len(name_parts) < 6:
            normk = _norm(lines[k])
            if normk in stop_markers or normk in interp_words:
                break
            next_lo, _ = _looks_like_simple_range(lines[k])
            if next_lo is not None and name_parts:
                break
            if re.match(r"^(?:version:|printed date:|page\s+\d+\s+of\s+\d+)", normk):
                break
            if name_parts and re.search(r"[\u0600-\u06FF]", lines[k]):
                break
            name_parts.append(lines[k]); k += 1
        name = _v143_safe_name(" ".join(name_parts))
        if not name:
            i += 1; continue
        key = _key_from_test_name(name, unit) or _v143_generic_key(name)
        rows.append({
            "key": key, "name": name, "value": value, "unit": unit,
            "reference_low": lo, "reference_high": hi,
            "reported_status": _v143_status(lines[interp_idx]),
            "reported_critical": _v143_is_critical(lines[interp_idx]),
        })
        i = max(i + 1, result_idx)
    return rows


def parse_blood_text(text):
    """V143: retain all readable test rows, not only the built-in marker list."""
    base, age = _parse_blood_text_v142(text)
    extras = _v143_native_rows(text) + _v143_pipe_rows(text)
    merged = []
    index = {}
    for row in list(base) + extras:
        if not isinstance(row, dict):
            continue
        key = str(row.get("key") or "").strip().lower()
        if not key:
            continue
        # Absolute and percentage differentials are different rows. Generic
        # keys are name-derived, while known keys are deduplicated normally.
        old_i = index.get(key)
        if old_i is None:
            index[key] = len(merged); merged.append(dict(row)); continue
        old = merged[old_i]
        old_score = int(old.get("reference_low") is not None and old.get("reference_high") is not None) * 3 + int(bool(old.get("unit"))) + int(bool(old.get("reported_status")))
        new_score = int(row.get("reference_low") is not None and row.get("reference_high") is not None) * 3 + int(bool(row.get("unit"))) + int(bool(row.get("reported_status")))
        # Enrich the existing row even when it remains the preferred value.
        if row.get("name") and not old.get("name"): old["name"] = row.get("name")
        if row.get("reported_status") and not old.get("reported_status"): old["reported_status"] = row.get("reported_status")
        if row.get("reported_critical"): old["reported_critical"] = True
        if new_score > old_score:
            keep = dict(row)
            if old.get("name") and not keep.get("name"): keep["name"] = old.get("name")
            merged[old_i] = keep
    return merged, age


def _analyze_blood_v143_base(entries, gender="", age=None):
    """V143: classify known markers plus report-defined unfamiliar rows."""
    known = [e for e in entries or [] if str(_entry_dict(e).get("key") or "").lower() in REFS]
    known_results, notes, dangers, level, child_note = _V142_analyze_blood(known, gender, age)
    original_by = {str(_entry_dict(e).get("key") or "").lower(): _entry_dict(e) for e in known}
    # A printed lab interpretation is useful when the range is categorical
    # (e.g. some HbA1c/Vitamin D reports). It is never invented by the app.
    for r in known_results:
        src = original_by.get(r.get("key"), {})
        rep = _v143_status(src.get("reported_status"))
        if r.get("status") == "unclassified" and rep:
            r["status"] = rep
            r["reference_source"] = "lab_reported_status"
        r["reported_critical"] = bool(src.get("reported_critical"))
        if src.get("name"):
            # Keep the localized built-in display name, but preserve report name.
            r["report_name"] = _v143_safe_name(src.get("name"))

    generic_results = []
    for raw in entries or []:
        e = _entry_dict(raw)
        key = str(e.get("key") or "").strip().lower()
        if key in REFS or not key.startswith("other_"):
            continue
        try: value = float(e.get("value"))
        except (TypeError, ValueError): continue
        name = _v143_safe_name(e.get("name") or "فحص مخبري")
        raw_unit = _v143_safe_unit(e.get("unit") or "")
        try: lo = float(e.get("reference_low")) if e.get("reference_low") not in (None, "") else None
        except (TypeError, ValueError): lo = None
        try: hi = float(e.get("reference_high")) if e.get("reference_high") not in (None, "") else None
        except (TypeError, ValueError): hi = None
        if lo is not None and hi is not None and lo > hi: lo, hi = hi, lo
        status, source = "unclassified", "unclassified"
        if lo is not None and hi is not None:
            status = "low" if value < lo else "high" if value > hi else "normal"
            source = "lab_reference"
        else:
            rep = _v143_status(e.get("reported_status"))
            if rep:
                status, source = rep, "lab_reported_status"
        generic_results.append({
            "key": key, "name_ar": name, "name_en": name, "report_name": name,
            "unit": raw_unit, "value": value, "low": lo, "high": hi,
            "status": status, "reference_source": source,
            "raw_value": value, "raw_unit": raw_unit,
            "canonical_value": None, "canonical_unit": None,
            "reported_critical": bool(e.get("reported_critical")),
        })
    results = known_results + generic_results
    if any(r.get("status") in {"low", "high"} for r in results) and level in {"normal", "unclassified"}:
        level = "see_doctor"
    elif results and all(r.get("status") == "normal" for r in results):
        level = "normal"
    return results, notes, dangers, level, child_note


_V143_FOCUS_LOW_AR = {
    "hgb": "ركّزي على معرفة سبب الانخفاض أولًا وربطه بالفيريتين والحديد وB12 والفولات عند الحاجة. الغذاء الغني بالحديد والبروتين قد يساعد إذا كان النقص غذائيًا، لكن لا تبدئي مكمل الحديد قبل تأكيد السبب.",
    "rbc": "يُربط عادةً بالهيموغلوبين وMCV والحديد/B12 والفولات. التركيز يكون على السبب وليس رفع العدد مباشرة.",
    "hct": "يُفسَّر مع الهيموغلوبين وكريات الدم الحمراء. إذا كان منخفضًا، راجعي أسباب فقر الدم أو فقدان الدم مع مختص بدل محاولة رفعه وحده.",
    "mcv": "إذا كان منخفضًا فركّزي على تقييم الحديد والفيريتين؛ وإذا كان مرتفعًا فغالبًا يحتاج ربطه بـB12 والفولات وأسباب أخرى. لا يعتمد على الغذاء وحده.",
    "mch": "يُقرأ مع MCV وMCHC والهيموغلوبين. انخفاضه يستحق تقييم الحديد/الفيريتين قبل أي مكمل.",
    "mchc": "انخفاضه قد يتماشى مع نقص صبغة الهيموغلوبين داخل الكريات؛ ركّزي على تقييم الحديد والفيريتين وربطه ببقية CBC بدل محاولة رفع الرقم مباشرة.",
    "ferritin": "ركّزي على مصادر الحديد الغذائية مثل اللحوم والبقول والخضار الورقية مع فيتامين C، وعلى البحث عن سبب نقص المخزون. مكمل الحديد يفضّل بعد تأكيد السبب والجرعة مع مختص.",
    "iron": "ركّزي على الغذاء الغني بالحديد وربط النتيجة بالفيريتين وCBC. قراءة الحديد تتغير خلال اليوم، لذلك لا يُعالج الرقم منفردًا.",
    "b12": "ركّزي على مصادر B12 مثل اللحوم والبيض ومنتجات الألبان أو الأغذية المدعمة، مع تقييم الامتصاص أو النظام الغذائي إذا كان الانخفاض واضحًا. جرعة المكمل تُحدد حسب السبب.",
    "vitd": "ركّزي على المصادر الغذائية المدعمة والتعرض الآمن للشمس بما يناسبك؛ جرعة مكمل فيتامين D تعتمد على مستوى النقص والحالة الصحية ويحددها مختص.",
    "albumin": "ركّزي على كفاية البروتين والطاقة في الغذاء، لكن الانخفاض قد يرتبط أيضًا بالكبد أو الكلى أو الالتهاب؛ لذلك يحتاج تفسير السبب.",
    "total_protein": "راجعي كفاية البروتين الغذائي مع الطبيب، لأن انخفاض البروتين الكلي قد يكون له أسباب غير غذائية أيضًا.",
    "hdl": "النشاط البدني المنتظم، الدهون غير المشبعة، وتجنب التدخين إن وجد عوامل تساعد عادةً على تحسين HDL ضمن خطة صحة القلب.",
}
_V143_FOCUS_HIGH_AR = {
    "glucose": "ركّزي على نمط الوجبات، تقليل السكريات المضافة والكربوهيدرات المكررة، الحركة المنتظمة، ومتابعة القياس حسب توجيه الطبيب.",
    "hba1c": "ركّزي على نمط الأكل، النشاط، الوزن الصحي إن كان مناسبًا، ومراجعة الطبيب لوضع هدف فردي للسكر؛ لا يعتمد القرار على قراءة واحدة فقط.",
    "ldl": "ركّزي على تقليل الدهون المشبعة والمتحولة، زيادة الألياف والنشاط البدني، وتقييم عوامل خطورة القلب مع الطبيب.",
    "chol_total": "يُفهم مع LDL وHDL والدهون الثلاثية. التركيز يكون على نمط غذائي صحي للقلب والنشاط ومراجعة عوامل الخطورة.",
    "triglycerides": "ركّزي على تقليل السكريات المضافة والكحول إن وُجد، تحسين النشاط والوزن إن كان مناسبًا، والتأكد من شروط الصيام إذا طلبها المختبر.",
    "ferritin": "لا تتناولي مكملات الحديد بهدف تعديل الرقم قبل معرفة السبب؛ ارتفاع الفيريتين قد يتأثر بالالتهاب وعوامل أخرى ويحتاج تفسيرًا.",
    "iron": "تجنبي إضافة مكمل الحديد دون تقييم السبب، واربطِي النتيجة بالفيريتين وCBC وبقية فحوص الحديد.",
    "mpv": "لا توجد طريقة غذائية موثوقة لخفض MPV مباشرة؛ الأهم ربطه بعدد الصفائح وبقية CBC والسياق السريري.",
}


def focus_guidance(key, status, lang="ar"):
    ar = lang == "ar"
    key = str(key or "")
    if status == "normal":
        return ("لا يحتاج هذا المؤشر إلى رفعه أو خفضه بناءً على التقرير وحده؛ حافظي على نمط صحي واتبعي خطة طبيبك إن وجدت." if ar else
                "This marker does not need to be raised or lowered based on the report alone; maintain healthy habits and follow your clinician's plan if applicable.")
    if status == "low":
        if key in _V143_FOCUS_LOW_AR:
            return _V143_FOCUS_LOW_AR[key] if ar else "Focus on confirming the cause of the low value with related tests and your clinician before starting supplements or trying to raise the number directly."
        if key in {"sodium", "potassium", "calcium", "co2", "chloride"}:
            return ("لا تحاولي رفع الأملاح أو المعادن ذاتيًا بمكملات أو كميات كبيرة؛ بعض الانخفاضات تحتاج تقييمًا سريعًا حسب الدرجة والأعراض." if ar else
                    "Do not try to raise electrolytes on your own with supplements or large amounts; some low results need prompt assessment depending on severity and symptoms.")
        if key in {"wbc", "neut", "lymph", "mono", "eos", "baso", "plt"}:
            return ("هذا النوع من القيم لا يُرفع بالغذاء بشكل مباشر عادةً؛ التركيز يكون على معرفة السبب ومراجعة الأدوية/العدوى/السياق مع الطبيب." if ar else
                    "These counts are not usually corrected directly with food; focus on finding the cause and reviewing medications, infections, and context with a clinician.")
        return ("لا توجد طريقة آمنة لرفع هذه القيمة تلقائيًا دون معرفة السبب. ركّزي على تأكيد النتيجة والنطاق المرجعي ومناقشة السبب مع الطبيب." if ar else
                "There is no safe universal way to raise this value without knowing the cause. Confirm the result/reference range and discuss the cause with a clinician.")
    if status == "high":
        if key in _V143_FOCUS_HIGH_AR:
            return _V143_FOCUS_HIGH_AR[key] if ar else "Focus on the underlying cause and the related markers rather than trying to lower the number directly; discuss persistent elevation with a clinician."
        if key in {"sodium", "potassium", "calcium", "co2", "chloride"}:
            return ("لا تحاولي خفض الإلكتروليت ذاتيًا؛ الارتفاع قد يحتاج تقييمًا طبيًا بحسب الدرجة والأعراض والأدوية." if ar else
                    "Do not try to lower an electrolyte on your own; elevation may need medical assessment depending on severity, symptoms, and medications.")
        return ("الهدف ليس خفض الرقم عشوائيًا؛ ركّزي على معرفة السبب وربطه بالفحوص الأخرى وإعادة القياس أو المتابعة حسب توجيه الطبيب." if ar else
                "The goal is not to lower the number blindly; focus on the cause, related tests, and repeat testing/follow-up as advised by a clinician.")
    return ("يلزم أولًا تأكيد الوحدة أو النطاق المرجعي قبل إعطاء توجيه لرفع أو خفض هذه القيمة." if ar else
            "Confirm the unit or reference range before giving advice to raise or lower this value.")


def _describe_results_v143_base(results, lang="ar"):
    out = _V142_describe_results(results, lang)
    for item in out:
        item["focus"] = focus_guidance(item.get("key"), item.get("status"), lang)
        if item.get("reference_source") == "lab_reported_status":
            item["reference_source_label"] = "تصنيف المختبر المطبوع في التقرير" if lang == "ar" else "Laboratory classification printed on the report"
        if str(item.get("key") or "").startswith("other_") and not item.get("what"):
            item["what"] = "فحص مخبري كما ورد اسمه في التقرير المرفوع؛ لم يطابق اسمًا قياسيًا في قاعدة التطبيق، لذلك نعتمد فقط على نطاق/تصنيف المختبر المطبوع." if lang == "ar" else "A laboratory test retained exactly from the uploaded report. Its name did not match a built-in marker, so only the report's printed range/status is used."
    return out

# ---------------------------------------------------------------------------
# V145 — stricter verification layer for laboratory interpretation.
# This layer does NOT claim diagnostic certainty. It grades how well each
# classification is verified against the uploaded laboratory report and refuses
# to choose a high/low/normal label when the report signals conflict.
_V143_analyze_blood_strict_base = _analyze_blood_v143_base
_V143_describe_results_strict_base = _describe_results_v143_base


def _v145_verification_meta(result, source_entry):
    """Return verification metadata and whether the row has a hard conflict.

    Strongest evidence is agreement between the numeric reference range printed
    on the report and the report's own printed status. A report range alone is
    still strong. App-owned adult fallback ranges are intentionally labelled as
    estimates, never as equivalent to the patient's own laboratory range.
    """
    src = source_entry or {}
    computed = str(result.get("status") or "unclassified")
    ref_source = str(result.get("reference_source") or "unclassified")
    reported = _v143_status(src.get("reported_status"))
    raw_unit = str(src.get("unit") or result.get("raw_unit") or "").strip()

    if ref_source == "lab_reference":
        if reported:
            if computed == reported:
                return {
                    "level": "double_verified",
                    "score": 4,
                    "label_ar": "تحقق مزدوج من تقرير المختبر",
                    "label_en": "Double-verified from the lab report",
                    "issue_ar": "",
                    "issue_en": "",
                    "conflict": False,
                }
            return {
                "level": "needs_review",
                "score": 0,
                "label_ar": "يحتاج مراجعة قبل الاعتماد",
                "label_en": "Needs review before relying on it",
                "issue_ar": "يوجد تعارض بين موقع القيمة داخل النطاق المرجعي وتصنيف المختبر المطبوع. لم نعتمد تصنيفًا تلقائيًا لهذه القيمة.",
                "issue_en": "The value's position in the reference range conflicts with the status printed by the laboratory. No automatic classification was accepted.",
                "conflict": True,
            }
        return {
            "level": "lab_range_verified",
            "score": 3,
            "label_ar": "متحقق من نطاق المختبر",
            "label_en": "Verified against the laboratory range",
            "issue_ar": "",
            "issue_en": "",
            "conflict": False,
        }

    if ref_source == "lab_reported_status":
        return {
            "level": "lab_status_only",
            "score": 2,
            "label_ar": "بحسب تصنيف المختبر المطبوع",
            "label_en": "Based on the laboratory's printed status",
            "issue_ar": "لم يتوفر نطاق رقمي كامل للمقارنة المزدوجة؛ اعتمدنا تصنيف المختبر المطبوع فقط.",
            "issue_en": "A complete numeric range was not available for a second check; only the laboratory's printed status was used.",
            "conflict": False,
        }

    if ref_source == "app_adult_reference":
        return {
            "level": "needs_review",
            "score": 0,
            "label_ar": "لا نعتمد نطاقًا عامًا بدل مختبرك",
            "label_en": "A general range is not accepted in place of your lab range",
            "issue_ar": "لم يظهر نطاق مختبر واضح لهذه القيمة. حفاظًا على الدقة، أوقفنا التصنيف التلقائي حتى تؤكد النطاق المرجعي المكتوب في تقريرك.",
            "issue_en": "No clear laboratory range was available. To protect accuracy, automatic classification was stopped until the reference range printed on your report is confirmed.",
            "conflict": True,
        }

    return {
        "level": "needs_review",
        "score": 0,
        "label_ar": "يحتاج تأكيد",
        "label_en": "Needs confirmation",
        "issue_ar": "لم يتوفر نطاق مرجعي واضح أو تصنيف مختبر كافٍ لتأكيد هذه القيمة.",
        "issue_en": "There was not enough clear reference-range or laboratory-status information to verify this value.",
        "conflict": False,
    }


def analyze_blood(entries, gender="", age=None):
    """V145: run the full analysis, then verify every classification strictly."""
    results, notes, dangers, level, child_note = _V143_analyze_blood_strict_base(entries, gender, age)
    source_by_key = {}
    for raw in entries or []:
        e = _entry_dict(raw)
        key = str(e.get("key") or "").strip().lower()
        if key:
            source_by_key[key] = e

    conflict_keys = set()
    for r in results:
        key = str(r.get("key") or "").strip().lower()
        meta = _v145_verification_meta(r, source_by_key.get(key, {}))
        r["verification_level"] = meta["level"]
        r["verification_score"] = meta["score"]
        r["verification_label_ar"] = meta["label_ar"]
        r["verification_label_en"] = meta["label_en"]
        r["verification_issue_ar"] = meta["issue_ar"]
        r["verification_issue_en"] = meta["issue_en"]
        if meta.get("conflict"):
            conflict_keys.add(key)
            r["status"] = "unclassified"
            r["reference_source"] = "verification_conflict"

    # If an extraction/status conflict exists, do not keep causal/pattern notes
    # that may have been generated from the disputed classification.
    if conflict_keys:
        notes = []
        if conflict_keys.intersection(DANGER_RULES):
            dangers = []

    # A laboratory-printed Critical flag is treated as an urgent clinician
    # signal, not as a universal numeric emergency threshold. If extraction
    # conflicts with the printed range/status, we require manual confirmation
    # instead of escalating automatically.
    for r in results:
        if r.get("reported_critical") and r.get("verification_level") != "needs_review":
            name_ar = r.get("name_ar") or r.get("report_name") or "قيمة مخبرية"
            name_en = r.get("name_en") or r.get("report_name") or "Laboratory value"
            if not any((d[0] == "urgent" and (name_ar in str(d[1]) or name_en in str(d[2]))) for d in dangers):
                dangers.append((
                    "urgent",
                    "🚨 صنّف المختبر %s كقيمة حرجة — تواصل مع جهة طبية اليوم واتبع تعليمات المختبر، ولا تعتمد على التطبيق وحده." % name_ar,
                    "🚨 The laboratory marked %s as critical — contact a medical service today and follow the laboratory's instructions; do not rely on the app alone." % name_en,
                ))

    if any(d[0] == "emergency" for d in dangers):
        level = "emergency"
    elif any(d[0] == "urgent" for d in dangers):
        level = "urgent"
    elif any(r.get("status") in {"low", "high"} for r in results):
        level = "see_doctor"
    elif results and any(r.get("status") == "unclassified" for r in results):
        level = "unclassified"
    else:
        level = "normal"
    return results, notes, dangers, level, child_note


def build_verification_summary(results, lang="ar"):
    ar = lang == "ar"
    counts = {
        "double_verified": 0,
        "lab_range_verified": 0,
        "lab_status_only": 0,
        "fallback_reference": 0,
        "needs_review": 0,
    }
    for r in results or []:
        lvl = str(r.get("verification_level") or "needs_review")
        counts[lvl if lvl in counts else "needs_review"] += 1
    total = sum(counts.values())
    if counts["needs_review"]:
        overall = "needs_review"
        title = "بعض القيم تحتاج تأكيد يدوي" if ar else "Some values need manual confirmation"
    elif counts["fallback_reference"]:
        overall = "good"
        title = "تحقق جيد مع قيم تحتاج نطاق مختبرك" if ar else "Good verification with values that still need your lab range"
    elif counts["lab_status_only"]:
        overall = "strong"
        title = "تحقق قوي من التقرير؛ بعض القيم اعتمدت تصنيف المختبر المطبوع" if ar else "Strong report verification; some values use the laboratory's printed status"
    else:
        overall = "strong"
        title = "تحقق قوي من تصنيف التقرير" if ar else "Strong verification of report classification"
    message = (
        "نقيس هنا قوة التحقق من قراءة القيمة وتصنيفها مقابل تقرير المختبر، وليس اليقين بالتشخيص الطبي. أقوى حالة هي توافق النطاق الرقمي المطبوع مع تصنيف المختبر نفسه."
        if ar else
        "This measures how strongly the value and classification were verified against the laboratory report, not diagnostic certainty. The strongest case is agreement between the printed numeric range and the laboratory's own status."
    )
    return {"overall": overall, "title": title, "message": message, "counts": counts, "total": total}


def describe_results(results, lang="ar"):
    out = _V143_describe_results_strict_base(results, lang)
    by_key = {str(r.get("key") or ""): r for r in results or []}
    ar = lang == "ar"
    for item in out:
        r = by_key.get(str(item.get("key") or ""), {})
        item["verification_level"] = r.get("verification_level") or "needs_review"
        item["verification_label"] = r.get("verification_label_ar" if ar else "verification_label_en") or ("يحتاج تأكيد" if ar else "Needs confirmation")
        item["verification_issue"] = r.get("verification_issue_ar" if ar else "verification_issue_en") or ""
        item["reported_critical"] = bool(r.get("reported_critical"))
        item["attention_level"] = attention_level_for_result(r)
        item["attention_label"] = ({
            "normal": "ضمن النطاق", "out_of_range": "خارج النطاق", "urgent": "تقييم عاجل", "emergency": "طوارئ", "needs_confirmation": "يحتاج تأكيد"
        }.get(item["attention_level"], "يحتاج متابعة") if ar else {
            "normal": "Within range", "out_of_range": "Out of range", "urgent": "Urgent evaluation", "emergency": "Emergency", "needs_confirmation": "Needs confirmation"
        }.get(item["attention_level"], "Needs follow-up"))
        item["possible_factors"] = possible_factors_for_result(item.get("key"), item.get("status"), lang)
        item["possible_factors_note"] = possible_factors_note(lang) if item["possible_factors"] else ""
        if r.get("reference_source") == "verification_conflict":
            item["reference_source_label"] = "تعارض يحتاج مراجعة مع التقرير الأصلي" if ar else "Conflict requiring review against the original report"
            item["meaning"] = (
                "لم نعتمد تصنيفًا تلقائيًا لأن البيانات المستخرجة من التقرير متعارضة. راجع القيمة والنطاق وتصنيف المختبر في الملف الأصلي ثم صححها في شاشة المراجعة."
                if ar else
                "No automatic classification was accepted because the extracted report data conflict. Review the value, range, and laboratory status in the original file and correct them on the review screen."
            )
            item["focus"] = (
                "الأولوية هنا لتأكيد القراءة من التقرير الأصلي، وليس محاولة رفع أو خفض الرقم."
                if ar else
                "The priority is to verify the reading from the original report, not to raise or lower the number."
            )
    return out
