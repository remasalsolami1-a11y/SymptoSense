"""
medication_warnings.py — lightweight, curated general-caution notes for common
over-the-counter/common medications. This is NOT a drug-interaction checker —
it flags well-known general cautions for a single mentioned medication, based
on simple keyword matching against the patient's free-text notes.
"""

import re
import json
from datetime import datetime, timezone

import db

# key -> (ar name, en name, {ar/en keyword variants}, ar warning, en warning,
#          ar uses, en uses, ar interactions, en interactions)
MEDICATIONS = {
    "aspirin": (
        "أسبرين", "Aspirin",
        {"أسبرين", "اسبرين", "aspirin"},
        "قد يسبب تهيّج بالمعدة أو نزيف خفيف عند بعض الأشخاص، خصوصاً مع أعراض مثل ألم البطن أو الغثيان.",
        "May cause stomach irritation or mild bleeding in some people, especially alongside symptoms like stomach pain or nausea.",
        "تسكين الألم الخفيف إلى المتوسط، خفض الحمى، والوقاية من الجلطات عند وصفه من الطبيب.",
        "Relieving mild to moderate pain, reducing fever, and preventing clots when prescribed by a doctor.",
        "قد يتداخل مع مميعات الدم (مثل الوارفارين)، والمسكنات الأخرى (مثل الإيبوبروفين)، وبعض أدوية الضغط والسكري.",
        "May interact with blood thinners (e.g. warfarin), other painkillers (e.g. ibuprofen), and some blood pressure or diabetes medications.",
    ),
    "ibuprofen": (
        "بروفين", "Ibuprofen",
        {"بروفين", "ibuprofen", "advil", "برفين"},
        "قد يهيّج المعدة إذا أُخذ بدون طعام، وغير مناسب لبعض حالات الجفاف أو مشاكل الكلى.",
        "Can irritate the stomach if taken without food, and isn't ideal during dehydration or with kidney issues.",
        "تسكين الألم والالتهاب وخفض الحمى.",
        "Relieving pain, inflammation, and fever.",
        "قد يزيد خطر النزف عند تناوله مع مميعات الدم أو الأسبرين أو الكورتيزون، ويقلل فعالية بعض أدوية الضغط.",
        "May increase bleeding risk with blood thinners, aspirin, or corticosteroids, and may reduce the effect of some blood pressure medications.",
    ),
    "paracetamol": (
        "بنادول / باراسيتامول", "Paracetamol / Acetaminophen",
        {"بنادول", "باراسيتامول", "paracetamol", "acetaminophen", "panadol", "tylenol"},
        "آمن عموماً بالجرعة الموصوفة، لكن تجاوز الجرعة اليومية القصوى قد يضر الكبد.",
        "Generally safe at recommended doses, but exceeding the daily maximum can harm the liver.",
        "تسكين الألم وخفض الحمى، خاصة عند من لا يناسبهم مضادات الالتهاب.",
        "Relieving pain and fever, especially for those who can't take anti-inflammatories.",
        "التداخل المهم هو تجاوز الجرعة اليومية القصوى (خصوصاً مع أدوية البرد التي تحتوي باراسيتامول) — وقد يتداخل مع بعض أدوية الكبد.",
        "The key concern is exceeding the daily maximum (especially with cold medicines that also contain paracetamol) — may interact with some liver-affecting medications.",
    ),
    "antibiotics": (
        "مضاد حيوي", "Antibiotics",
        {"مضاد حيوي", "مضادات حيوية", "antibiotic", "antibiotics", "أموكسيسيلين", "amoxicillin"},
        "مهم إكمال الجرعة كاملة حسب وصف الطبيب حتى لو تحسنتِ، وعدم استخدامه بدون وصفة طبية.",
        "Important to complete the full prescribed course even if you feel better, and avoid use without a doctor's prescription.",
        "علاج الالتهابات البكتيرية التي يصفها الطبيب.",
        "Treating bacterial infections as prescribed by a doctor.",
        "قد يضعف فعالية حبوب منع الحمل، ويتداخل مع مميعات الدم وبعض أدوية المعدة — أبلغ طبيبك بكل ما تتناوله.",
        "May reduce the effectiveness of birth control pills and interact with blood thinners and some stomach medications — tell your doctor everything you take.",
    ),
    "antihistamine": (
        "مضاد هيستامين", "Antihistamine",
        {"مضاد هيستامين", "antihistamine", "زيرتك", "zyrtec", "كلاريتين", "claritin"},
        "بعض الأنواع تسبب نعاس — تجنبي القيادة أو الأنشطة اللي تحتاج تركيز بعد أخذه.",
        "Some types cause drowsiness — avoid driving or activities needing focus after taking it.",
        "علاج أعراض الحساسية مثل العطس والحكة وسيلان الأنف.",
        "Treating allergy symptoms such as sneezing, itching, and runny nose.",
        "قد يزيد التأثير المهدئ مع المهدئات وأدوية القلق والكحول وبعض أدوية الضغط.",
        "May increase the sedative effect with tranquilizers, anxiety medicines, alcohol, and some blood pressure medications.",
    ),
    "decongestant": (
        "مزيل احتقان", "Decongestant",
        {"مزيل احتقان", "decongestant", "سودافين", "sudafed"},
        "قد يرفع ضغط الدم عند بعض الأشخاص — يُفضّل الحذر لمن عندهم ضغط مرتفع.",
        "May raise blood pressure in some people — caution advised for those with hypertension.",
        "تخفيف انسداد الأنف الناتج عن الزكام أو الحساسية.",
        "Relieving nasal congestion from colds or allergies.",
        "قد يرفع ضغط الدم — الحذر مع أدوية الضغط ومثبطات MAO وبعض أدوية القلب.",
        "May raise blood pressure — caution with blood pressure medicines, MAO inhibitors, and some heart medications.",
    ),
    "diclofenac": (
        "فولتارين / ديكلوفيناك", "Diclofenac / Voltaren",
        {"فولتارين", "فولترين", "ديكلوفيناك", "diclofenac", "voltaren"},
        "يُفضّل أخذه مع الطعام لتقليل تهيّج المعدة، وممنوع لمن عندهم قرحة معدية أو مشاكل كلى.",
        "Best taken with food to reduce stomach irritation; avoid with stomach ulcers or kidney problems.",
        "تسكين الألم والالتهاب (آلام المفاصل والعضلات وغيرها).",
        "Relieving pain and inflammation (joint, muscle, and other pains).",
        "قد يزيد خطر النزف والمشاكل الكلوية مع مميعات الدم ومدرات البول ومضادات الالتهاب الأخرى.",
        "May increase bleeding and kidney risk with blood thinners, diuretics, and other anti-inflammatories.",
    ),
    "metformin": (
        "متفورمين / جلوكوفاج", "Metformin / Glucophage",
        {"متفورمين", "متفورمن", "جلوكوفاج", "metformin", "glucophage"},
        "يُفضل أخذه مع الوجبات، وقد يسبب غثيان أو إسهال بسيط في البداية يزول غالباً.",
        "Best taken with meals; may cause mild nausea or diarrhea initially, which usually settles.",
        "ضبط سكر الدم في مرض السكري من النوع الثاني.",
        "Controlling blood sugar in type 2 diabetes.",
        "قد يتداخل مع الكورتيزون ومدرات البول وبعض أدوية القلب والكلى — وقد تزداد حموضة الدم مع شرب الكحول.",
        "May interact with corticosteroids, diuretics, and some heart/kidney medications — alcohol may increase the risk of lactic acidosis.",
    ),
    "amlodipine": (
        "أملوديبين", "Amlodipine",
        {"أملوديبين", "amlodipine", "نورفاسك", "norvasc"},
        "قد يسبب تورماً خفيفاً بالكاحلين — لو زاد التورم فجأة أو صار تنفس صعب، راجعي طبيبك.",
        "May cause mild ankle swelling — if swelling suddenly worsens or breathing is hard, see your doctor.",
        "علاج ارتفاع ضغط الدم وبعض حالات الذبحة الصدرية.",
        "Treating high blood pressure and some cases of angina.",
        "قد يزداد انخفاض الضغط مع أدوية الضغط الأخرى والكحول، ويتداخل مع بعض مضادات الفطريات والمضادات الحيوية.",
        "Blood pressure may drop further with other pressure medicines and alcohol; may interact with some antifungals and antibiotics.",
    ),
    "omeprazole": (
        "أوميبرازول", "Omeprazole",
        {"أوميبرازول", "omeprazole", "لوسيك", "losec", "أوميز", "omez"},
        "يُفضل أخذه قبل الأكل بنصف ساعة، ويستخدم عادةً لفترات محددة — لا تطوّلي استخدامه دون استشارة طبيب.",
        "Best taken 30 minutes before meals, usually for limited periods — don't use long-term without a doctor.",
        "تقليل حموضة المعدة وعلاج قرحة المعدة والارتجاع.",
        "Reducing stomach acid and treating ulcers and reflux.",
        "قد يقلل امتصاص بعض الأدوية مثل كلوبيدوجريل وبعض مضادات الفطريات، ويؤثر على امتصاص الحديد والمغنيسيوم.",
        "May reduce absorption of some medications such as clopidogrel and some antifungals, and affects iron/magnesium absorption.",
    ),
}


def _unpack(entry):
    name_ar, name_en, keywords, warn_ar, warn_en, uses_ar, uses_en, interact_ar, interact_en = entry
    return name_ar, name_en, keywords, warn_ar, warn_en, uses_ar, uses_en, interact_ar, interact_en


def check_medications(notes: str):
    """Returns a list of {"name", "warning"} dicts for any recognized medication
    mentioned in the free-text notes (lang-appropriate)."""
    if not notes:
        return []
    text = notes.lower()
    matches = []
    seen = set()
    for key, entry in MEDICATIONS.items():
        if key in seen:
            continue
        name_ar, name_en, keywords, warn_ar, warn_en, *_ = _unpack(entry)
        for kw in keywords:
            if kw.lower() in text:
                matches.append({
                    "name_ar": name_ar, "name_en": name_en,
                    "warning_ar": warn_ar, "warning_en": warn_en,
                })
                seen.add(key)
                break
    return matches


def lookup_drug(name: str):
    """Return a medication record from the production database.

    The bundled curated records are only used to seed an empty database. All
    runtime searches then go through the database, so Admin/database updates
    are reflected without changing the frontend.
    """
    if not name:
        return None
    init_schema()
    text = _norm(name)
    conn = db._conn()
    try:
        c = conn.cursor()
        c.execute("SELECT id,name_ar,name_en,aliases,warning_ar,warning_en,uses_ar,uses_en,interactions_ar,interactions_en,updated_at FROM medical_medications WHERE status='active'")
        for row in c.fetchall():
            aliases = json.loads(row[3] or "[]")
            choices = [row[1], row[2], *aliases]
            if any(text == _norm(x) or (len(text) >= 3 and text in _norm(x)) for x in choices):
                return {"id":row[0],"name_ar":row[1],"name_en":row[2],"warning_ar":row[4],"warning_en":row[5],"uses_ar":row[6],"uses_en":row[7],"interact_ar":row[8],"interact_en":row[9],"updated_at":row[10]}
    finally:
        conn.close()
    return None


def _norm(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def init_schema():
    db.init_db()
    conn = db._conn()
    try:
        c = conn.cursor()
        serial = "SERIAL PRIMARY KEY" if db.USE_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"
        c.execute(f"""CREATE TABLE IF NOT EXISTS medical_medications (
            id {serial}, slug TEXT UNIQUE NOT NULL, name_ar TEXT NOT NULL,
            name_en TEXT NOT NULL, aliases TEXT NOT NULL, warning_ar TEXT,
            warning_en TEXT, uses_ar TEXT, uses_en TEXT, interactions_ar TEXT,
            interactions_en TEXT, status TEXT NOT NULL DEFAULT 'active',
            updated_at TEXT NOT NULL
        )""")
        now = datetime.now(timezone.utc).isoformat()
        for slug, entry in MEDICATIONS.items():
            name_ar,name_en,keywords,warn_ar,warn_en,uses_ar,uses_en,interact_ar,interact_en = _unpack(entry)
            values=(slug,name_ar,name_en,json.dumps(sorted(keywords),ensure_ascii=False),warn_ar,warn_en,uses_ar,uses_en,interact_ar,interact_en,"active",now)
            c.execute(f"INSERT INTO medical_medications(slug,name_ar,name_en,aliases,warning_ar,warning_en,uses_ar,uses_en,interactions_ar,interactions_en,status,updated_at) VALUES({','.join([db.PH]*12)}) ON CONFLICT(slug) DO NOTHING", values)
        conn.commit()
    finally:
        conn.close()
