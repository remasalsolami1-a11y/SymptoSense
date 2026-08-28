"""Structured, source-grounded medical knowledge for SymptoSense.

This module stores only general medical content.  It never reads or writes
patient records.  Matching is intentionally qualitative and explainable; it is
not a diagnostic probability model.
"""
from __future__ import annotations

import difflib
import json
import os
import re
import threading
import time
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

import db


ACTIVE = "active"
VALID_CONTENT_STATUS = {"active", "draft", "disabled"}
VALID_VERIFICATION = {"verified", "needs_review", "disabled"}
VALID_ROLES = {"admin"}
VALID_SEVERITY = {"mild", "moderate", "severe"}
VALID_RELIABILITY = {"high", "medium", "low"}
VALID_SOURCE_LANGUAGES = {"ar", "en", "multiple"}
ALLOWED_SOURCE_TYPES = {
    "government", "international_organization", "national_health_service",
    "academic_medical_institution", "other_trusted_source",
}
SOURCE_TYPE_PRIORITY = {
    "government": 10,
    "international_organization": 20,
    "national_health_service": 30,
    "academic_medical_institution": 40,
    "other_trusted_source": 50,
}
DEFAULT_ALLOWED_DOMAINS = {
    "moh.gov.sa", "who.int", "emro.who.int", "nhs.uk", "cdc.gov",
    "mayoclinic.org", "medlineplus.gov", "nih.gov",
}

_READY = False
_LOCK = threading.Lock()


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _json(value, default=None):
    if value is None:
        value = [] if default is None else default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def _dump(value):
    return json.dumps(value if value is not None else [], ensure_ascii=False)


def _id(c):
    if db.USE_POSTGRES:
        c.execute("SELECT lastval()")
        return int(c.fetchone()[0])
    return int(c.lastrowid)


def _allowed_domains():
    extra = {x.strip().lower() for x in os.environ.get("MEDICAL_SOURCE_ALLOWED_DOMAINS", "").split(",") if x.strip()}
    return DEFAULT_ALLOWED_DOMAINS | extra


def _url_is_trusted(url):
    try:
        parsed = urlparse((url or "").strip())
        host = (parsed.hostname or "").lower()
        return parsed.scheme == "https" and bool(host) and any(host == d or host.endswith("." + d) for d in _allowed_domains())
    except Exception:
        return False


def _source_url_matches(source_url, reference_url):
    if not _url_is_trusted(reference_url):
        return False
    source_host = (urlparse(source_url).hostname or "").lower()
    ref_host = (urlparse(reference_url).hostname or "").lower()
    return ref_host == source_host or ref_host.endswith("." + source_host) or source_host.endswith("." + ref_host)


def _columns(c, table):
    if db.USE_POSTGRES:
        c.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s", (table,))
        return {r[0] for r in c.fetchall()}
    c.execute(f"PRAGMA table_info({table})")
    return {r[1] for r in c.fetchall()}


def init_schema():
    """Create the knowledge schema and idempotently load the verified starter set."""
    global _READY
    if _READY:
        return
    with _LOCK:
        if _READY:
            return
        db.init_db()
        conn = db._conn()
        try:
            c = conn.cursor()
            serial = "SERIAL PRIMARY KEY" if db.USE_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"
            c.execute(f"""CREATE TABLE IF NOT EXISTS mk_categories (
                id {serial}, slug TEXT UNIQUE NOT NULL, name_ar TEXT NOT NULL, name_en TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )""")
            c.execute(f"""CREATE TABLE IF NOT EXISTS mk_sources (
                id {serial}, slug TEXT UNIQUE NOT NULL, source_name TEXT NOT NULL, organization TEXT NOT NULL,
                official_url TEXT NOT NULL, description_ar TEXT DEFAULT '', description_en TEXT DEFAULT '',
                language TEXT DEFAULT 'multiple', source_type TEXT NOT NULL, reliability_level TEXT NOT NULL DEFAULT 'high',
                verification_status TEXT NOT NULL DEFAULT 'needs_review', last_verified TEXT, status TEXT NOT NULL DEFAULT 'draft',
                priority INTEGER NOT NULL DEFAULT 50, version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )""")
            c.execute(f"""CREATE TABLE IF NOT EXISTS mk_diseases (
                id {serial}, slug TEXT UNIQUE NOT NULL, name_ar TEXT NOT NULL, name_en TEXT NOT NULL,
                description_ar TEXT NOT NULL, description_en TEXT NOT NULL, category_id INTEGER,
                severity TEXT NOT NULL DEFAULT 'moderate', risk_factors_ar TEXT DEFAULT '', risk_factors_en TEXT DEFAULT '',
                common_causes_ar TEXT DEFAULT '', common_causes_en TEXT DEFAULT '', red_flags_ar TEXT DEFAULT '', red_flags_en TEXT DEFAULT '',
                related_diseases TEXT DEFAULT '[]', recommended_next_step_ar TEXT NOT NULL, recommended_next_step_en TEXT NOT NULL,
                last_updated TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft', version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                FOREIGN KEY(category_id) REFERENCES mk_categories(id)
            )""")
            c.execute(f"""CREATE TABLE IF NOT EXISTS mk_symptoms (
                id {serial}, slug TEXT UNIQUE NOT NULL, name_ar TEXT NOT NULL, name_en TEXT NOT NULL,
                description_ar TEXT NOT NULL, description_en TEXT NOT NULL, category_id INTEGER,
                severity_min INTEGER NOT NULL DEFAULT 1, severity_max INTEGER NOT NULL DEFAULT 5,
                aliases_ar TEXT NOT NULL DEFAULT '[]', aliases_en TEXT NOT NULL DEFAULT '[]',
                red_flags_ar TEXT DEFAULT '', red_flags_en TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'draft',
                version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                FOREIGN KEY(category_id) REFERENCES mk_categories(id)
            )""")
            c.execute(f"""CREATE TABLE IF NOT EXISTS mk_disease_symptoms (
                id {serial}, disease_id INTEGER NOT NULL, symptom_id INTEGER NOT NULL, weight REAL NOT NULL DEFAULT 0.5,
                typicality TEXT NOT NULL DEFAULT 'common', notes_ar TEXT DEFAULT '', notes_en TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(disease_id, symptom_id), FOREIGN KEY(disease_id) REFERENCES mk_diseases(id) ON DELETE CASCADE,
                FOREIGN KEY(symptom_id) REFERENCES mk_symptoms(id) ON DELETE CASCADE
            )""")
            c.execute(f"""CREATE TABLE IF NOT EXISTS mk_disease_sources (
                id {serial}, disease_id INTEGER NOT NULL, source_id INTEGER NOT NULL,
                reference_title_ar TEXT NOT NULL, reference_title_en TEXT NOT NULL, reference_url TEXT NOT NULL,
                last_verified TEXT, status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(disease_id, source_id), FOREIGN KEY(disease_id) REFERENCES mk_diseases(id) ON DELETE CASCADE,
                FOREIGN KEY(source_id) REFERENCES mk_sources(id) ON DELETE CASCADE
            )""")
            c.execute(f"""CREATE TABLE IF NOT EXISTS mk_symptom_sources (
                id {serial}, symptom_id INTEGER NOT NULL, source_id INTEGER NOT NULL,
                reference_title_ar TEXT NOT NULL, reference_title_en TEXT NOT NULL, reference_url TEXT NOT NULL,
                last_verified TEXT, status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(symptom_id, source_id), FOREIGN KEY(symptom_id) REFERENCES mk_symptoms(id) ON DELETE CASCADE,
                FOREIGN KEY(source_id) REFERENCES mk_sources(id) ON DELETE CASCADE
            )""")
            c.execute(f"""CREATE TABLE IF NOT EXISTS mk_red_flags (
                id {serial}, slug TEXT UNIQUE NOT NULL, name_ar TEXT NOT NULL, name_en TEXT NOT NULL,
                description_ar TEXT DEFAULT '', description_en TEXT DEFAULT '',
                required_symptoms TEXT NOT NULL DEFAULT '[]', match_mode TEXT NOT NULL DEFAULT 'all',
                keywords_ar TEXT NOT NULL DEFAULT '[]', keywords_en TEXT NOT NULL DEFAULT '[]',
                min_severity INTEGER NOT NULL DEFAULT 1, severity TEXT NOT NULL DEFAULT 'urgent', risk_level TEXT NOT NULL DEFAULT 'urgent',
                message_ar TEXT NOT NULL, message_en TEXT NOT NULL,
                recommended_action_ar TEXT DEFAULT '', recommended_action_en TEXT DEFAULT '',
                source_id INTEGER, reference_url TEXT DEFAULT '', last_updated TEXT,
                status TEXT NOT NULL DEFAULT 'active', version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                FOREIGN KEY(source_id) REFERENCES mk_sources(id)
            )""")
            c.execute(f"""CREATE TABLE IF NOT EXISTS mk_audit_log (
                id {serial}, admin_id INTEGER, admin_email TEXT NOT NULL, action TEXT NOT NULL,
                entity_type TEXT NOT NULL, entity_id INTEGER, previous_value TEXT, new_value TEXT, timestamp TEXT NOT NULL
            )""")
            c.execute(f"""CREATE TABLE IF NOT EXISTS mk_versions (
                id {serial}, entity_type TEXT NOT NULL, entity_id INTEGER NOT NULL, version INTEGER NOT NULL,
                snapshot TEXT NOT NULL, admin_id INTEGER, admin_email TEXT NOT NULL, timestamp TEXT NOT NULL
            )""")
            c.execute("CREATE INDEX IF NOT EXISTS idx_mk_disease_status ON mk_diseases(status)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_mk_symptom_status ON mk_symptoms(status)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_mk_source_status ON mk_sources(status, verification_status)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_mk_audit_time ON mk_audit_log(timestamp)")
            for table in ("mk_sources", "mk_red_flags"):
                if "version" not in _columns(c, table):
                    c.execute(f"ALTER TABLE {table} ADD COLUMN version INTEGER NOT NULL DEFAULT 1")
            # Non-destructive Red Flag schema upgrade. Existing rules remain in
            # place and receive the new metadata fields without deleting data.
            rf_cols = _columns(c, "mk_red_flags")
            for col, ddl in (
                ("description_ar", "TEXT DEFAULT ''"), ("description_en", "TEXT DEFAULT ''"),
                ("severity", "TEXT NOT NULL DEFAULT 'urgent'"),
                ("recommended_action_ar", "TEXT DEFAULT ''"), ("recommended_action_en", "TEXT DEFAULT ''"),
                ("reference_url", "TEXT DEFAULT ''"), ("last_updated", "TEXT")
            ):
                if col not in rf_cols:
                    c.execute(f"ALTER TABLE mk_red_flags ADD COLUMN {col} {ddl}")
            _seed(c)
            conn.commit()
            _READY = True
        finally:
            conn.close()


CATEGORIES = [
    ("pain", "الألم", "Pain"), ("respiratory", "الجهاز التنفسي", "Respiratory"),
    ("digestive", "الجهاز الهضمي", "Digestive"), ("neurological", "الجهاز العصبي", "Neurological"),
    ("skin", "الجلد", "Skin"), ("cardiovascular", "القلب والأوعية", "Cardiovascular"),
    ("mental-health", "الصحة النفسية", "Mental Health"), ("general", "أعراض عامة", "General Symptoms"),
]

SOURCES = [
    ("saudi-moh", "وزارة الصحة السعودية", "Saudi Ministry of Health", "https://www.moh.gov.sa/", "government", 10),
    ("who", "WHO", "World Health Organization", "https://www.who.int/", "international_organization", 20),
    ("who-emro", "WHO EMRO", "WHO Regional Office for the Eastern Mediterranean", "https://www.emro.who.int/", "international_organization", 21),
    ("nhs", "NHS", "National Health Service", "https://www.nhs.uk/", "national_health_service", 30),
    ("cdc", "CDC", "Centers for Disease Control and Prevention", "https://www.cdc.gov/", "government", 11),
    ("mayo-clinic", "Mayo Clinic", "Mayo Foundation for Medical Education and Research", "https://www.mayoclinic.org/", "academic_medical_institution", 40),
]

SYMPTOMS = [
    ("headache", "صداع", "Headache", "pain", ["الصداع", "الم في الراس", "ألم في الرأس", "راسي يعورني", "راسي يوجعني"], ["head pain", "head ache"]),
    ("severe-headache", "صداع شديد مفاجئ", "Sudden severe headache", "neurological", ["اسوأ صداع", "أسوأ صداع", "صداع مفاجئ شديد"], ["worst headache", "thunderclap headache"]),
    ("nausea", "غثيان", "Nausea", "digestive", ["لوعه", "لوعه بالمعده", "أشعر بالغثيان"], ["feeling sick", "queasy"]),
    ("vomiting", "قيء", "Vomiting", "digestive", ["استفراغ", "ترجيع"], ["being sick", "throwing up"]),
    ("light-sensitivity", "حساسية للضوء", "Sensitivity to light", "neurological", ["الضوء يزعجني", "حساسيه من الضوء"], ["photophobia", "light sensitivity"]),
    ("sound-sensitivity", "حساسية للصوت", "Sensitivity to sound", "neurological", ["الصوت يزعجني", "حساسيه من الاصوات"], ["phonophobia", "sound sensitivity"]),
    ("fever", "حمى", "Fever", "general", ["حرارة", "سخونه", "ارتفاع الحراره"], ["high temperature", "feverish"]),
    ("cough", "سعال", "Cough", "respiratory", ["كحه", "كحة"], ["coughing"]),
    ("sore-throat", "ألم الحلق", "Sore throat", "respiratory", ["احتقان الحلق", "حلقي يعورني"], ["throat pain"]),
    ("runny-nose", "سيلان الأنف", "Runny nose", "respiratory", ["رشح", "زكام", "انسداد الانف", "احتقان الانف"], ["stuffy nose", "blocked nose", "nasal congestion"]),
    ("fatigue", "تعب وإرهاق", "Fatigue", "general", ["تعب", "ارهاق", "خمول"], ["tiredness", "exhausted"]),
    ("body-aches", "آلام الجسم", "Body aches", "pain", ["الم عضلات", "ألم العضلات", "جسمي يعورني"], ["muscle aches", "muscle pain"]),
    ("chills", "قشعريرة", "Chills", "general", ["رعشه", "رجفه", "برد شديد"], ["shivering"]),
    ("diarrhea", "إسهال", "Diarrhea", "digestive", ["اسهال", "براز مائي"], ["diarrhoea", "loose stools"]),
    ("abdominal-pain", "ألم البطن", "Abdominal pain", "digestive", ["الم المعده", "ألم المعدة", "بطني يعورني"], ["stomach pain", "belly pain"]),
    ("dizziness", "دوخة", "Dizziness", "neurological", ["دوار", "عدم توازن"], ["dizzy", "lightheaded"]),
    ("dehydration", "جفاف", "Dehydration", "general", ["قلة البول", "جفاف الفم"], ["dry mouth", "reduced urination"]),
    ("wheezing", "صفير التنفس", "Wheezing", "respiratory", ["صفير في الصدر"], ["wheeze"]),
    ("shortness-of-breath", "ضيق التنفس", "Shortness of breath", "respiratory", ["صعوبة التنفس", "ما اقدر اتنفس", "لا استطيع التنفس", "ضيق شديد في التنفس", "ضيق شديد بالتنفس", "صعوبة شديدة في التنفس"], ["difficulty breathing", "trouble breathing", "breathless", "severe shortness of breath", "severe breathing difficulty"]),
    ("chest-tightness", "ضيق الصدر", "Chest tightness", "respiratory", ["شد في الصدر"], ["tight chest"]),
    ("chest-pain", "ألم الصدر", "Chest pain", "cardiovascular", ["الم في الصدر", "وجع الصدر"], ["pain in chest", "heart pain"]),
    ("sweating", "تعرق غير معتاد", "Unusual sweating", "general", ["عرق بارد", "تعرق شديد"], ["cold sweat", "sweating heavily"]),
    ("one-sided-weakness", "ضعف في جانب واحد", "One-sided weakness", "neurological", ["ضعف جهة واحدة", "تنميل في جانب", "خدر في جانب", "ضعف مفاجئ", "ضعف مفاجئ في جهة واحدة", "تنميل مفاجئ في جانب"], ["weakness on one side", "one sided numbness", "arm weakness", "sudden weakness", "sudden arm weakness"]),
    ("speech-difficulty", "صعوبة في الكلام", "Speech difficulty", "neurological", ["ثقل الكلام", "الكلام متداخل", "صعوبة مفاجئة في الكلام", "صعوبه مفاجئه في الكلام"], ["slurred speech", "trouble speaking", "speech difficulty", "sudden speech difficulty"]),
    ("face-drooping", "تدلي الوجه", "Face drooping", "neurological", ["اعوجاج الوجه"], ["facial droop"]),
    ("sudden-vision-loss", "فقدان مفاجئ للرؤية", "Sudden vision loss", "neurological", ["فقدت النظر فجأه", "فقدت الرؤية فجأة"], ["sudden loss of vision", "sudden blindness"]),
    ("loss-of-consciousness", "فقدان الوعي", "Loss of consciousness", "neurological", ["اغماء", "إغماء", "غيبوبه"], ["unconscious", "fainted", "passed out"]),
    ("severe-bleeding", "نزيف شديد", "Severe bleeding", "cardiovascular", ["نزيف لا يتوقف", "دم لا يتوقف"], ["heavy bleeding", "uncontrollable bleeding"]),
    ("suicidal-thoughts", "أفكار لإيذاء النفس", "Thoughts of self-harm", "mental-health", ["افكار انتحاريه", "أفكار انتحارية", "ابي اموت", "إيذاء النفس"], ["suicidal thoughts", "self harm", "want to die"]),
]

DISEASES = [
    {"slug":"migraine","name_ar":"الصداع النصفي (الشقيقة)","name_en":"Migraine","category":"neurological","severity":"moderate",
     "description_ar":"اضطراب صداع أولي قد يسبب نوبات من صداع نابض، غالبًا في جانب واحد، وقد يصاحبه غثيان وحساسية للضوء أو الصوت.",
     "description_en":"A primary headache disorder that can cause attacks of throbbing head pain, often on one side, with nausea or sensitivity to light and sound.",
     "risk_ar":"التاريخ العائلي، اضطراب النوم، التوتر وبعض المحفزات الشخصية.","risk_en":"Family history, sleep disruption, stress, and individual triggers.",
     "causes_ar":"السبب الدقيق غير معروف؛ قد تشارك تغيرات عصبية ووعائية وتوجد محفزات تختلف بين الأشخاص.","causes_en":"The exact cause is unknown; neurological and vascular changes may contribute, with triggers varying by person.",
     "red_ar":"صداع مفاجئ شديد جدًا، ضعف في جانب واحد، صعوبة كلام، فقدان رؤية أو تشوش.","red_en":"A sudden extremely severe headache, one-sided weakness, speech difficulty, vision loss, or confusion.",
     "next_ar":"راقب نمط الصداع ومحفزاته واطلب تقييمًا طبيًا إذا كان جديدًا أو متكررًا أو يزداد سوءًا.","next_en":"Track the headache pattern and triggers, and seek medical review if it is new, recurrent, or worsening.",
     "symptoms":{"headache":1.0,"nausea":0.75,"vomiting":0.45,"light-sensitivity":0.9,"sound-sensitivity":0.85,"dizziness":0.35},
     "sources":[("saudi-moh","الصداع النصفي — وزارة الصحة","Migraine — Saudi MOH","https://www.moh.gov.sa/healthawareness/educationalcontent/diseases/nervous-system/pages/migraine.aspx"),("who","اضطرابات الصداع — منظمة الصحة العالمية","Headache disorders — WHO","https://www.who.int/news-room/fact-sheets/detail/headache-disorders"),("nhs","الصداع النصفي — NHS","Migraine — NHS","https://www.nhs.uk/conditions/migraine/"),("mayo-clinic","الصداع النصفي — مايو كلينك","Migraine — Mayo Clinic","https://www.mayoclinic.org/diseases-conditions/migraine-headache/symptoms-causes/syc-20360201")]},
    {"slug":"influenza","name_ar":"الإنفلونزا","name_en":"Influenza (flu)","category":"respiratory","severity":"moderate",
     "description_ar":"عدوى تنفسية فيروسية تبدأ غالبًا بصورة مفاجئة وقد تسبب الحمى والسعال وآلام الجسم والتعب.","description_en":"A viral respiratory infection that often starts suddenly and may cause fever, cough, body aches, and fatigue.",
     "risk_ar":"العمر الصغير أو الكبير، الحمل وبعض الأمراض المزمنة أو ضعف المناعة.","risk_en":"Young or older age, pregnancy, chronic conditions, or weakened immunity.",
     "causes_ar":"فيروسات الإنفلونزا التي تنتقل أساسًا عبر الرذاذ والمخالطة.","causes_en":"Influenza viruses spread mainly through respiratory droplets and close contact.",
     "red_ar":"صعوبة تنفس، ألم صدر، تشوش، جفاف شديد أو تحسن ثم تدهور مفاجئ.","red_en":"Breathing difficulty, chest pain, confusion, severe dehydration, or improvement followed by sudden worsening.",
     "next_ar":"راقب التنفس والترطيب واطلب تقييمًا طبيًا مبكرًا عند وجود عوامل خطورة أو تدهور.","next_en":"Monitor breathing and hydration and seek early medical review if risk factors or worsening are present.",
     "symptoms":{"fever":0.9,"cough":0.8,"sore-throat":0.45,"runny-nose":0.35,"fatigue":0.75,"body-aches":0.85,"headache":0.6,"chills":0.7},
     "sources":[("cdc","علامات وأعراض الإنفلونزا — CDC","Flu signs and symptoms — CDC","https://www.cdc.gov/flu/signs-symptoms/index.html")]},
    {"slug":"common-cold","name_ar":"نزلة البرد الشائعة","name_en":"Common cold","category":"respiratory","severity":"mild",
     "description_ar":"عدوى فيروسية شائعة في الجهاز التنفسي العلوي تبدأ أعراضها عادةً تدريجيًا.","description_en":"A common viral upper-respiratory infection whose symptoms usually begin gradually.",
     "risk_ar":"المخالطة القريبة وقلة غسل اليدين وبعض حالات ضعف المناعة.","risk_en":"Close contact, limited hand hygiene, and some states of weakened immunity.",
     "causes_ar":"فيروسات تنفسية متعددة تنتقل بالمخالطة والرذاذ والأسطح الملوثة.","causes_en":"Multiple respiratory viruses spread by contact, droplets, and contaminated surfaces.",
     "red_ar":"ضيق تنفس، ألم صدر، حرارة مرتفعة مستمرة أو تدهور بعد عدة أيام.","red_en":"Shortness of breath, chest pain, persistent high fever, or worsening after several days.",
     "next_ar":"راقب الأعراض واطلب مراجعة طبية إذا لم تتحسن خلال المدة المتوقعة أو ظهرت علامة خطر.","next_en":"Monitor symptoms and seek review if they do not improve as expected or a red flag appears.",
     "symptoms":{"runny-nose":0.95,"sore-throat":0.75,"cough":0.65,"fatigue":0.35,"fever":0.25,"body-aches":0.2},
     "sources":[("nhs","نزلة البرد الشائعة — NHS","Common cold — NHS","https://www.nhs.uk/conditions/common-cold/")]},
    {"slug":"viral-gastroenteritis","name_ar":"التهاب المعدة والأمعاء الفيروسي","name_en":"Viral gastroenteritis","category":"digestive","severity":"moderate",
     "description_ar":"التهاب في المعدة أو الأمعاء يسبب القيء أو الإسهال وقد يؤدي إلى الجفاف.","description_en":"Inflammation of the stomach or intestines causing vomiting or diarrhea and sometimes dehydration.",
     "risk_ar":"العمر الصغير أو الكبير، ضعف المناعة والمخالطة أو الطعام الملوث.","risk_en":"Young or older age, weakened immunity, close contact, or contaminated food.",
     "causes_ar":"فيروسات معوية شديدة العدوى مثل نوروفيروس.","causes_en":"Highly contagious enteric viruses such as norovirus.",
     "red_ar":"جفاف شديد، قلة بول، خمول غير معتاد، دم في القيء أو البراز أو ألم بطن شديد.","red_en":"Severe dehydration, reduced urination, unusual drowsiness, blood in vomit or stool, or severe abdominal pain.",
     "next_ar":"عوّض السوائل تدريجيًا واطلب تقييمًا طبيًا عند علامات الجفاف أو استمرار الأعراض أو تدهورها.","next_en":"Replace fluids gradually and seek medical review for dehydration, persistent symptoms, or worsening.",
     "symptoms":{"diarrhea":0.95,"vomiting":0.85,"nausea":0.7,"abdominal-pain":0.7,"fever":0.3,"headache":0.2,"body-aches":0.25,"dehydration":0.55},
     "sources":[("cdc","حول نوروفيروس — CDC","About norovirus — CDC","https://www.cdc.gov/norovirus/about/index.html")]},
    {"slug":"asthma","name_ar":"الربو","name_en":"Asthma","category":"respiratory","severity":"moderate",
     "description_ar":"مرض رئوي مزمن يسبب التهابًا وضيقًا في الشعب الهوائية، وقد تتفاوت أعراضه مع الوقت.","description_en":"A chronic lung disease involving inflamed and narrowed airways, with symptoms that can vary over time.",
     "risk_ar":"التاريخ العائلي، الحساسية، التعرض للدخان أو الملوثات وبعض العدوى التنفسية.","risk_en":"Family history, allergies, smoke or pollution exposure, and some respiratory infections.",
     "causes_ar":"تشارك عوامل وراثية وبيئية، وقد تحفز الأعراض مهيجات مختلفة.","causes_en":"Genetic and environmental factors contribute, with symptoms triggered by different irritants.",
     "red_ar":"صعوبة تنفس شديدة، عدم القدرة على الكلام بصورة طبيعية أو ازرقاق الشفاه.","red_en":"Severe breathing difficulty, inability to speak normally, or blue lips.",
     "next_ar":"تحدث مع مختص صحي لتقييم الأعراض ووضع خطة واضحة، واطلب رعاية عاجلة عند صعوبة التنفس الشديدة.","next_en":"Speak with a health professional for assessment and an action plan; seek urgent care for severe breathing difficulty.",
     "symptoms":{"wheezing":1.0,"shortness-of-breath":0.95,"chest-tightness":0.85,"cough":0.7,"fatigue":0.2},
     "sources":[("who","الربو — منظمة الصحة العالمية","Asthma — WHO","https://www.who.int/news-room/fact-sheets/detail/asthma")]},
]

RED_RULES = [
    ("chest-breathing", "ألم الصدر مع ضيق التنفس", "Chest pain with breathing difficulty", ["chest-pain","shortness-of-breath"], "all", [], [], 1, "urgent", "ألم الصدر مع صعوبة التنفس قد يحتاج رعاية عاجلة.", "Chest pain with breathing difficulty may require urgent care.", "nhs"),
    ("stroke-combination", "علامات سكتة دماغية محتملة", "Possible stroke signs", ["one-sided-weakness","speech-difficulty"], "all", [], [], 1, "urgent", "ضعف جانب واحد مع صعوبة الكلام علامة طارئة محتملة.", "One-sided weakness with speech difficulty is a possible emergency.", "cdc"),
    ("face-droop", "تدلي الوجه المفاجئ", "Sudden face drooping", ["face-drooping"], "any", [], [], 1, "urgent", "تدلي الوجه المفاجئ يحتاج طلب الطوارئ فورًا.", "Sudden face drooping needs emergency help now.", "cdc"),
    ("sudden-vision", "فقدان الرؤية المفاجئ", "Sudden vision loss", ["sudden-vision-loss"], "any", [], [], 1, "urgent", "فقدان الرؤية المفاجئ يحتاج تقييمًا عاجلًا.", "Sudden vision loss needs urgent assessment.", "cdc"),
    ("unconscious", "فقدان الوعي", "Loss of consciousness", ["loss-of-consciousness"], "any", [], [], 1, "urgent", "فقدان الوعي علامة تستدعي طلب الطوارئ.", "Loss of consciousness requires emergency help.", "nhs"),
    ("severe-bleeding", "نزيف شديد", "Severe bleeding", ["severe-bleeding"], "any", [], [], 1, "urgent", "النزيف الشديد أو الذي لا يتوقف يحتاج طوارئ.", "Severe or uncontrolled bleeding needs emergency care.", "nhs"),
    ("severe-head-neuro", "صداع شديد مع علامة عصبية", "Severe headache with neurological sign", ["severe-headache","one-sided-weakness"], "all", [], [], 1, "urgent", "الصداع الشديد المفاجئ مع ضعف في جانب واحد علامة طارئة.", "A sudden severe headache with one-sided weakness is an emergency sign.", "cdc"),
    ("self-harm", "خطر إيذاء النفس", "Risk of self-harm", ["suicidal-thoughts"], "any", [], [], 1, "urgent", "أفكار إيذاء النفس تحتاج دعمًا فوريًا وعدم البقاء وحيدًا.", "Thoughts of self-harm need immediate support; do not stay alone.", "who"),
    ("severe-breathing", "ضيق تنفس شديد", "Severe breathing difficulty", ["shortness-of-breath"], "any", [], [], 4, "urgent", "ضيق التنفس الشديد يحتاج تقييمًا عاجلًا.", "Severe breathing difficulty needs urgent assessment.", "nhs"),
    ("chest-review", "ألم في الصدر", "Chest pain", ["chest-pain"], "any", [], [], 1, "review", "ألم الصدر يحتاج تقييمًا طبيًا حتى دون علامات أخرى.", "Chest pain needs medical assessment even without other signs.", "nhs"),
]

# Source-grounded metadata for the independent safety layer. These references
# point to official pages and are never generated by the AI model.
RED_RULE_DETAILS = {
    "chest-breathing": {
        "description_ar": "ألم الصدر المصحوب بضيق تنفس قد يكون علامة تستدعي تقييماً طارئاً.",
        "description_en": "Chest pain with shortness of breath can be a sign requiring emergency assessment.",
        "action_ar": "اطلب الرعاية الطبية العاجلة أو تواصل مع خدمات الطوارئ المناسبة.",
        "action_en": "Seek urgent medical care or contact the appropriate emergency service.",
        "url": "https://www.nhs.uk/symptoms/chest-pain/"},
    "stroke-combination": {
        "description_ar": "الضعف المفاجئ في جانب واحد مع صعوبة الكلام من علامات السكتة الدماغية المعروفة.",
        "description_en": "Sudden one-sided weakness with speech difficulty is a recognized stroke warning sign.",
        "action_ar": "اطلب خدمات الطوارئ فوراً ولا تنتظر زوال الأعراض.",
        "action_en": "Contact emergency services immediately and do not wait for symptoms to pass.",
        "url": "https://www.cdc.gov/stroke/signs-symptoms/index.html"},
    "face-droop": {
        "description_ar": "تدلي الوجه المفاجئ قد يكون من علامات السكتة الدماغية.",
        "description_en": "Sudden facial drooping can be a stroke warning sign.",
        "action_ar": "اطلب خدمات الطوارئ فوراً.", "action_en": "Contact emergency services immediately.",
        "url": "https://www.cdc.gov/stroke/signs-symptoms/index.html"},
    "sudden-vision": {
        "description_ar": "التغير أو الفقدان المفاجئ للرؤية قد يظهر ضمن علامات السكتة الدماغية.",
        "description_en": "Sudden vision trouble or loss can occur among stroke warning signs.",
        "action_ar": "اطلب تقييماً طبياً طارئاً فوراً.", "action_en": "Seek emergency medical assessment immediately.",
        "url": "https://www.cdc.gov/stroke/signs-symptoms/index.html"},
    "unconscious": {
        "description_ar": "فقدان الوعي أو عدم الاستجابة قد يمثل حالة مهددة للحياة.",
        "description_en": "Loss of consciousness or abnormal unresponsiveness can represent a life-threatening emergency.",
        "action_ar": "تواصل مع خدمات الطوارئ المناسبة فوراً.", "action_en": "Contact the appropriate emergency service immediately.",
        "url": "https://www.nhs.uk/nhs-services/urgent-and-emergency-care-services/when-to-call-999/"},
    "severe-bleeding": {
        "description_ar": "النزيف الغزير أو الذي لا يمكن إيقافه يحتاج إلى رعاية طارئة.",
        "description_en": "Heavy or uncontrolled bleeding requires emergency care.",
        "action_ar": "اطلب الطوارئ أو توجّه للرعاية العاجلة المناسبة.", "action_en": "Contact emergency services or obtain appropriate emergency care.",
        "url": "https://www.nhs.uk/conditions/cuts-and-grazes/"},
    "severe-head-neuro": {
        "description_ar": "الصداع الشديد المفاجئ مع ضعف في جانب واحد من علامات الخطر العصبية.",
        "description_en": "A sudden severe headache with one-sided weakness is a neurological red flag.",
        "action_ar": "اطلب خدمات الطوارئ فوراً.", "action_en": "Contact emergency services immediately.",
        "url": "https://www.cdc.gov/stroke/signs-symptoms/index.html"},
    "self-harm": {
        "description_ar": "وجود أفكار لإيذاء النفس يحتاج دعماً فورياً وتقييماً للسلامة.",
        "description_en": "Thoughts of self-harm require immediate support and a safety assessment.",
        "action_ar": "إذا كان الخطر مباشراً فلا تبقَ وحيداً وتواصل مع خدمات الطوارئ أو جهة دعم مناسبة فوراً.",
        "action_en": "If danger is immediate, do not stay alone and contact emergency services or an appropriate crisis service now.",
        "url": "https://www.who.int/news-room/questions-and-answers/item/suicide"},
    "severe-breathing": {
        "description_ar": "صعوبة التنفس الشديدة، مثل اللهاث أو عدم القدرة على إخراج الكلمات، تحتاج رعاية طارئة.",
        "description_en": "Severe breathing difficulty, such as gasping or being unable to get words out, needs emergency care.",
        "action_ar": "تواصل مع خدمات الطوارئ المناسبة فوراً.", "action_en": "Contact the appropriate emergency service immediately.",
        "url": "https://www.nhs.uk/symptoms/shortness-of-breath/"},
    "chest-review": {
        "description_ar": "ألم الصدر يحتاج إلى تقييم طبي لتحديد درجة الاستعجال حتى عند غياب علامات إضافية.",
        "description_en": "Chest pain needs medical assessment to determine urgency even when other warning signs are absent.",
        "action_ar": "اطلب تقييماً طبياً، واطلب الطوارئ فوراً إذا كان الألم مفاجئاً أو مستمراً أو ترافق مع ضيق تنفس أو دوار.",
        "action_en": "Seek medical assessment; obtain emergency help if pain is sudden, persistent, or accompanied by breathlessness or light-headedness.",
        "url": "https://www.nhs.uk/symptoms/chest-pain/"},
}


def _seed(c):

    now = _now()
    for slug, ar, en in CATEGORIES:
        c.execute(f"INSERT INTO mk_categories (slug,name_ar,name_en,status,created_at,updated_at) VALUES ({db.PH},{db.PH},{db.PH},'active',{db.PH},{db.PH}) ON CONFLICT(slug) DO NOTHING", (slug, ar, en, now, now))
    for slug, name, org, url, typ, priority in SOURCES:
        c.execute(f"INSERT INTO mk_sources (slug,source_name,organization,official_url,description_ar,description_en,language,source_type,reliability_level,verification_status,last_verified,status,priority,version,created_at,updated_at) VALUES ({','.join([db.PH]*16)}) ON CONFLICT(slug) DO NOTHING",
                  (slug,name,org,url,"مصدر طبي رسمي موثوق.","Official trusted medical source.","multiple",typ,"high","verified",now[:10],"active",priority,1,now,now))
    c.execute("SELECT id,slug FROM mk_categories")
    cats = {slug:int(i) for i,slug in c.fetchall()}
    c.execute("SELECT id,slug FROM mk_sources")
    sources = {slug:int(i) for i,slug in c.fetchall()}
    for slug, ar, en, cat, aliases_ar, aliases_en in SYMPTOMS:
        c.execute(f"INSERT INTO mk_symptoms (slug,name_ar,name_en,description_ar,description_en,category_id,severity_min,severity_max,aliases_ar,aliases_en,red_flags_ar,red_flags_en,status,version,created_at,updated_at) VALUES ({','.join([db.PH]*16)}) ON CONFLICT(slug) DO NOTHING",
                  (slug,ar,en,f"عرض عام: {ar}.",f"General symptom: {en}.",cats.get(cat),1,5,_dump(aliases_ar),_dump(aliases_en),"","","active",1,now,now))
        # Add newly curated normalization aliases without deleting any aliases
        # that an administrator may already have added in production.
        c.execute(f"SELECT aliases_ar,aliases_en FROM mk_symptoms WHERE slug={db.PH}", (slug,))
        current_aliases = c.fetchone()
        if current_aliases:
            merged_ar = list(dict.fromkeys(_json(current_aliases[0], []) + list(aliases_ar)))
            merged_en = list(dict.fromkeys(_json(current_aliases[1], []) + list(aliases_en)))
            c.execute(f"UPDATE mk_symptoms SET aliases_ar={db.PH},aliases_en={db.PH} WHERE slug={db.PH}", (_dump(merged_ar), _dump(merged_en), slug))
    c.execute("SELECT id,slug FROM mk_symptoms")
    symptoms = {slug:int(i) for i,slug in c.fetchall()}
    for disease in DISEASES:
        c.execute(f"INSERT INTO mk_diseases (slug,name_ar,name_en,description_ar,description_en,category_id,severity,risk_factors_ar,risk_factors_en,common_causes_ar,common_causes_en,red_flags_ar,red_flags_en,related_diseases,recommended_next_step_ar,recommended_next_step_en,last_updated,status,version,created_at,updated_at) VALUES ({','.join([db.PH]*21)}) ON CONFLICT(slug) DO NOTHING",
                  (disease['slug'],disease['name_ar'],disease['name_en'],disease['description_ar'],disease['description_en'],cats.get(disease['category']),disease['severity'],disease['risk_ar'],disease['risk_en'],disease['causes_ar'],disease['causes_en'],disease['red_ar'],disease['red_en'],"[]",disease['next_ar'],disease['next_en'],now[:10],"active",1,now,now))
    c.execute("SELECT id,slug FROM mk_diseases")
    diseases = {slug:int(i) for i,slug in c.fetchall()}
    for disease in DISEASES:
        did = diseases[disease['slug']]
        for symptom_slug, weight in disease['symptoms'].items():
            sid = symptoms[symptom_slug]
            typicality = "very_common" if weight >= .85 else ("common" if weight >= .5 else "less_common")
            c.execute(f"INSERT INTO mk_disease_symptoms (disease_id,symptom_id,weight,typicality,notes_ar,notes_en,status,created_at,updated_at) VALUES ({','.join([db.PH]*9)}) ON CONFLICT(disease_id,symptom_id) DO NOTHING", (did,sid,float(weight),typicality,"","","active",now,now))
        for source_slug, title_ar, title_en, ref_url in disease['sources']:
            source_id = sources[source_slug]
            c.execute(f"INSERT INTO mk_disease_sources (disease_id,source_id,reference_title_ar,reference_title_en,reference_url,last_verified,status,created_at,updated_at) VALUES ({','.join([db.PH]*9)}) ON CONFLICT(disease_id,source_id) DO NOTHING", (did,source_id,title_ar,title_en,ref_url,now[:10],"active",now,now))
            for symptom_slug in disease['symptoms']:
                sid = symptoms[symptom_slug]
                c.execute(f"INSERT INTO mk_symptom_sources (symptom_id,source_id,reference_title_ar,reference_title_en,reference_url,last_verified,status,created_at,updated_at) VALUES ({','.join([db.PH]*9)}) ON CONFLICT(symptom_id,source_id) DO NOTHING", (sid,source_id,title_ar,title_en,ref_url,now[:10],"active",now,now))
    for slug, ar, en, req, mode, kw_ar, kw_en, min_sev, risk, msg_ar, msg_en, source_slug in RED_RULES:
        meta = RED_RULE_DETAILS.get(slug, {})
        c.execute(f"INSERT INTO mk_red_flags (slug,name_ar,name_en,description_ar,description_en,required_symptoms,match_mode,keywords_ar,keywords_en,min_severity,severity,risk_level,message_ar,message_en,recommended_action_ar,recommended_action_en,source_id,reference_url,last_updated,status,version,created_at,updated_at) VALUES ({','.join([db.PH]*23)}) ON CONFLICT(slug) DO NOTHING",
                  (slug,ar,en,meta.get("description_ar",msg_ar),meta.get("description_en",msg_en),_dump(req),mode,_dump(kw_ar),_dump(kw_en),min_sev,risk,risk,msg_ar,msg_en,meta.get("action_ar",msg_ar),meta.get("action_en",msg_en),sources.get(source_slug),meta.get("url", ""),now[:10],"active",1,now,now))
        # Idempotently backfill metadata for rules created by older releases.
        c.execute(f"UPDATE mk_red_flags SET description_ar={db.PH},description_en={db.PH},severity={db.PH},recommended_action_ar={db.PH},recommended_action_en={db.PH},reference_url={db.PH},last_updated={db.PH} WHERE slug={db.PH}",
                  (meta.get("description_ar",msg_ar),meta.get("description_en",msg_en),risk,meta.get("action_ar",msg_ar),meta.get("action_en",msg_en),meta.get("url", ""),now[:10],slug))


def _normalize_text(value):
    text = unicodedata.normalize("NFKC", str(value or "")).lower()
    text = re.sub(r"[\u064b-\u065f\u0670]", "", text)
    text = text.translate(str.maketrans({"أ":"ا","إ":"ا","آ":"ا","ى":"ي","ة":"ه","ؤ":"و","ئ":"ي"}))
    text = re.sub(r"[^a-z0-9\u0600-\u06ff\s-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _fetch_symptoms(active_only=True):
    init_schema()
    conn = db._conn()
    try:
        c = conn.cursor()
        sql = "SELECT id,slug,name_ar,name_en,description_ar,description_en,category_id,severity_min,severity_max,aliases_ar,aliases_en,red_flags_ar,red_flags_en,status,version,created_at,updated_at FROM mk_symptoms"
        if active_only:
            sql += " WHERE status='active'"
        c.execute(sql + " ORDER BY name_en")
        rows = c.fetchall()
    finally:
        conn.close()
    keys = ["id","slug","name_ar","name_en","description_ar","description_en","category_id","severity_min","severity_max","aliases_ar","aliases_en","red_flags_ar","red_flags_en","status","version","created_at","updated_at"]
    out = []
    for row in rows:
        item = dict(zip(keys,row)); item["aliases_ar"]=_json(item["aliases_ar"],[]); item["aliases_en"]=_json(item["aliases_en"],[]); out.append(item)
    return out


def normalize_symptoms(raw_symptoms, lang="ar"):
    symptoms = _fetch_symptoms(True)
    candidates = []
    for item in symptoms:
        aliases = [item["name_ar"], item["name_en"], item["slug"].replace("-", " ")] + item["aliases_ar"] + item["aliases_en"]
        for alias in aliases:
            norm = _normalize_text(alias)
            if norm:
                candidates.append((len(norm), norm, item))
    candidates.sort(key=lambda x: x[0], reverse=True)
    found, unmatched, seen = [], [], set()
    for original in raw_symptoms or []:
        text = _normalize_text(original)
        local = []
        for _, alias, item in candidates:
            if item["id"] in seen:
                continue
            if alias == text or (len(alias) >= 4 and re.search(r"(?:^|\s)" + re.escape(alias) + r"(?:$|\s)", text)):
                local.append((alias,item))
        if not local and text:
            best = None
            for _, alias, item in candidates:
                ratio = difflib.SequenceMatcher(None,text,alias).ratio()
                if ratio >= .86 and (best is None or ratio > best[0]):
                    best = (ratio,alias,item)
            if best:
                local = [(best[1],best[2])]
        if not local:
            unmatched.append(str(original))
        for alias,item in local:
            if item["id"] in seen:
                continue
            seen.add(item["id"])
            found.append({"symptom_id":item["id"],"slug":item["slug"],"name_ar":item["name_ar"],"name_en":item["name_en"],"original":str(original),"matched_alias":alias})
    return {"canonical":found,"unmatched":unmatched}


def _source_rows_for_disease(c, disease_id):
    c.execute(f"""SELECT s.id,s.slug,s.source_name,s.organization,s.official_url,s.source_type,s.reliability_level,s.verification_status,s.last_verified,s.priority,
                         ds.reference_title_ar,ds.reference_title_en,ds.reference_url,ds.last_verified
                  FROM mk_disease_sources ds JOIN mk_sources s ON s.id=ds.source_id
                  WHERE ds.disease_id={db.PH} AND ds.status='active' AND s.status='active' AND s.verification_status='verified'
                  ORDER BY s.priority,s.source_name""", (int(disease_id),))
    keys=["id","slug","source_name","organization","official_url","source_type","reliability_level","verification_status","source_last_verified","priority","reference_title_ar","reference_title_en","reference_url","last_verified"]
    return [dict(zip(keys,r)) for r in c.fetchall()]


def match_diseases(canonical, lang="ar", limit=5):
    init_schema()
    ids = {int(x["symptom_id"]):x for x in canonical or []}
    if not ids:
        return []
    conn = db._conn()
    try:
        c = conn.cursor()
        c.execute("SELECT id,slug,name_ar,name_en,description_ar,description_en,severity,red_flags_ar,red_flags_en,recommended_next_step_ar,recommended_next_step_en,last_updated FROM mk_diseases WHERE status='active'")
        diseases = c.fetchall()
        out=[]
        for row in diseases:
            did=int(row[0])
            c.execute(f"SELECT symptom_id,weight,typicality,notes_ar,notes_en FROM mk_disease_symptoms WHERE disease_id={db.PH} AND status='active'",(did,))
            rels=c.fetchall()
            total=sum(max(float(r[1] or 0),0) for r in rels) or 1
            matched=[r for r in rels if int(r[0]) in ids]
            if not matched:
                continue
            coverage=sum(float(r[1] or 0) for r in matched)/total
            user_coverage=len(matched)/max(len(ids),1)
            score=.78*coverage+.22*user_coverage
            if score>=.63 and len(matched)>=2:
                level="strong"
            elif score>=.34 or len(matched)>=3:
                level="moderate"
            else:
                level="weak"
            matched_symptoms=[]
            for sid,weight,typicality,notes_ar,notes_en in matched:
                sym=ids[int(sid)]
                matched_symptoms.append({"slug":sym["slug"],"name_ar":sym["name_ar"],"name_en":sym["name_en"],"weight":float(weight or 0),"typicality":typicality,"notes":notes_ar if lang=="ar" else notes_en})
            sources=_source_rows_for_disease(c,did)
            if not sources:
                continue
            out.append({"disease_id":did,"slug":row[1],"name_ar":row[2],"name_en":row[3],"description":row[4] if lang=="ar" else row[5],"severity":row[6],"red_flags":row[7] if lang=="ar" else row[8],"recommended_next_step":row[9] if lang=="ar" else row[10],"last_updated":row[11],"match_level":level,"matched_symptoms":matched_symptoms,"sources":sources,"_score":score})
        out.sort(key=lambda x:(x["_score"],len(x["matched_symptoms"])),reverse=True)
        for item in out:
            item.pop("_score",None)
        return out[:max(1,min(int(limit),10))]
    finally:
        conn.close()


def evaluate_risk(canonical, raw_symptoms=None, notes="", severity=1, age=None, lang="ar"):
    init_schema()
    slugs={x["slug"] for x in canonical or []}
    text=_normalize_text(" ".join(str(x) for x in (raw_symptoms or []))+" "+str(notes or ""))
    try: severity=max(1,min(5,int(severity or 1)))
    except Exception: severity=1
    try: age=int(age) if age not in (None,"") else None
    except Exception: age=None
    conn=db._conn()
    try:
        c=conn.cursor(); c.execute("""SELECT rf.id,rf.slug,rf.name_ar,rf.name_en,rf.required_symptoms,rf.match_mode,rf.keywords_ar,rf.keywords_en,
                                      rf.min_severity,rf.risk_level,rf.message_ar,rf.message_en,rf.description_ar,rf.description_en,
                                      rf.recommended_action_ar,rf.recommended_action_en,rf.source_id,rf.reference_url,rf.last_updated,
                                      s.source_name,s.organization,s.official_url,s.verification_status,s.status
                               FROM mk_red_flags rf LEFT JOIN mk_sources s ON s.id=rf.source_id
                               WHERE rf.status='active'""")
        rows=c.fetchall()
    finally: conn.close()
    hits=[]
    for r in rows:
        req=set(_json(r[4],[])); mode=r[5] or "all"; kws=_json(r[6] if lang=="ar" else r[7],[]); min_sev=int(r[8] or 1)
        req_hit=(not req) or (req.issubset(slugs) if mode=="all" else bool(req & slugs))
        kw_hit=any(_normalize_text(k) in text for k in kws if _normalize_text(k))
        if severity>=min_sev and (req_hit or kw_hit):
            source = None
            if r[16] and r[19] and r[22] == "verified" and r[23] == "active":
                ref_url = r[17] if _url_is_trusted(r[17]) else r[21]
                source = {"id": r[16], "source_name": r[19], "organization": r[20],
                          "official_url": r[21], "reference_url": ref_url, "last_verified": r[18]}
            hits.append({"rule_id":r[0],"slug":r[1],"name":r[2] if lang=="ar" else r[3],"risk_level":r[9],
                         "message":r[10] if lang=="ar" else r[11],
                         "description":r[12] if lang=="ar" else r[13],
                         "recommended_action":r[14] if lang=="ar" else r[15],
                         "source": source, "last_updated": r[18]})
    level="urgent" if any(h["risk_level"]=="urgent" for h in hits) else ("review" if hits else "low")
    if level=="low" and (severity>=4 or (age and age>=65 and bool(slugs & {"shortness-of-breath","chest-pain","fever","dehydration"}))):
        level="review"
        hits.append({"slug":"clinical-review","name":"تقييم طبي" if lang=="ar" else "Medical review","risk_level":"review","message":"شدة الأعراض أو عوامل العمر تستدعي تقييمًا طبيًا." if lang=="ar" else "Symptom severity or age factors warrant medical review."})
    labels={"ar":{"low":"🟢 خطورة منخفضة","review":"🟡 يحتاج مراجعة طبية","urgent":"🔴 يحتاج رعاية عاجلة"},"en":{"low":"🟢 Low risk","review":"🟡 Needs medical review","urgent":"🔴 Urgent"}}
    return {"level":level,"label":labels["en" if lang=="en" else "ar"][level],"reasons":hits,"emergency":level=="urgent"}


def knowledge_bundle(raw_symptoms, severity=1, age=None, notes="", lang="ar"):
    lang="en" if lang=="en" else "ar"
    norm=normalize_symptoms(raw_symptoms,lang)
    risk=evaluate_risk(norm["canonical"],raw_symptoms,notes,severity,age,lang)
    matches=[] if risk["level"]=="urgent" else match_diseases(norm["canonical"],lang)
    sources=[]; seen=set(); dates=[]
    # Safety sources are included even when urgent risk intentionally suppresses
    # disease matching. This keeps every emergency warning source-grounded.
    for reason in risk.get("reasons", []):
        source = reason.get("source") if isinstance(reason, dict) else None
        if source:
            source_key=(source.get("id"),source.get("reference_url") or source.get("official_url"))
            if source_key not in seen:
                seen.add(source_key); sources.append(source)
        if isinstance(reason, dict) and reason.get("last_updated"):
            dates.append(reason["last_updated"])
    for match in matches:
        if match.get("last_updated"): dates.append(match["last_updated"])
        for source in match["sources"]:
            source_key=(source["id"],source.get("reference_url") or source.get("official_url"))
            if source_key not in seen:
                seen.add(source_key); sources.append(source)
            if source.get("last_verified"): dates.append(source["last_verified"])
    return {"normalization":norm,"matches":matches,"sources":sources,"risk":risk,"last_updated":max(dates) if dates else None}


def _admin(admin):
    return int((admin or {}).get("id") or 0) or None, str((admin or {}).get("email") or "system")


def _audit(c, admin, action, entity_type, entity_id, old, new):
    aid,_email=_admin(admin); now=_now()
    c.execute(f"INSERT INTO mk_audit_log (admin_id,admin_email,action,entity_type,entity_id,previous_value,new_value,timestamp) VALUES ({','.join([db.PH]*8)})",(aid,None,action,entity_type,entity_id,_dump(old) if old is not None else None,_dump(new) if new is not None else None,now))
    version=int((new or old or {}).get("version") or 1)
    if new is not None and entity_type in {"disease","symptom","source","red_flag"}:
        c.execute(f"INSERT INTO mk_versions (entity_type,entity_id,version,snapshot,admin_id,admin_email,timestamp) VALUES ({','.join([db.PH]*7)})",(entity_type,int(entity_id),version,_dump(new),aid,None,now))


def _record(c, table, entity_id):
    allowed={"mk_diseases","mk_symptoms","mk_sources","mk_red_flags"}
    if table not in allowed: raise ValueError("invalid_entity")
    c.execute(f"SELECT * FROM {table} WHERE id={db.PH}",(int(entity_id),)); row=c.fetchone()
    if not row: return None
    cols=[d[0] for d in c.description]
    item=dict(zip(cols,row))
    for key in ("aliases_ar","aliases_en","related_diseases","required_symptoms","keywords_ar","keywords_en"):
        if key in item: item[key]=_json(item[key],[])
    return item


def _duplicates(c, table, name_ar, name_en, entity_id=None):
    params=[name_ar.strip().lower(),name_en.strip().lower()]
    sql=f"SELECT id FROM {table} WHERE (LOWER(name_ar)={db.PH} OR LOWER(name_en)={db.PH})"
    if entity_id:
        sql+=f" AND id<>{db.PH}"; params.append(int(entity_id))
    c.execute(sql,tuple(params)); return bool(c.fetchone())


def _verified_source_ids(c, ids):
    good=[]
    for sid in ids or []:
        c.execute(f"SELECT official_url FROM mk_sources WHERE id={db.PH} AND status='active' AND verification_status='verified'",(int(sid),))
        row=c.fetchone()
        if row and _url_is_trusted(row[0]): good.append(int(sid))
    return good


def list_entities(kind, include_inactive=False, search="", category=None, severity=None, verification=None):
    init_schema(); table={"diseases":"mk_diseases","symptoms":"mk_symptoms","sources":"mk_sources","red_flags":"mk_red_flags"}.get(kind)
    if not table: raise ValueError("invalid_entity")
    conn=db._conn()
    try:
        c=conn.cursor(); c.execute(f"SELECT * FROM {table} ORDER BY id DESC"); rows=c.fetchall(); cols=[d[0] for d in c.description]
        out=[]; q=_normalize_text(search)
        for row in rows:
            item=dict(zip(cols,row))
            if not include_inactive and item.get("status")!="active": continue
            if q and q not in _normalize_text(" ".join(str(item.get(k) or "") for k in ("name_ar","name_en","source_name","organization","slug"))): continue
            if category and str(item.get("category_id"))!=str(category): continue
            if severity and item.get("severity")!=severity: continue
            if verification and item.get("verification_status")!=verification: continue
            for key in ("aliases_ar","aliases_en","related_diseases","required_symptoms","keywords_ar","keywords_en"):
                if key in item: item[key]=_json(item[key],[])
            out.append(item)
        return out
    finally: conn.close()


def get_entity(kind, entity_id, public=False):
    init_schema(); table={"disease":"mk_diseases","symptom":"mk_symptoms","source":"mk_sources","red_flag":"mk_red_flags"}.get(kind)
    if not table: raise ValueError("invalid_entity")
    conn=db._conn()
    try:
        c=conn.cursor(); item=_record(c,table,entity_id)
        if not item or (public and item.get("status")!="active"): return None
        if kind=="disease":
            c.execute(f"SELECT ds.id,s.id,s.slug,s.name_ar,s.name_en,ds.weight,ds.typicality,ds.notes_ar,ds.notes_en FROM mk_disease_symptoms ds JOIN mk_symptoms s ON s.id=ds.symptom_id WHERE ds.disease_id={db.PH} AND ds.status='active' ORDER BY ds.weight DESC",(int(entity_id),))
            item["symptoms"]=[dict(zip(["relationship_id","symptom_id","slug","name_ar","name_en","weight","typicality","notes_ar","notes_en"],r)) for r in c.fetchall()]
            item["sources"]=_source_rows_for_disease(c,int(entity_id))
        elif kind=="symptom":
            c.execute(f"SELECT d.id,d.slug,d.name_ar,d.name_en,ds.weight,ds.typicality FROM mk_disease_symptoms ds JOIN mk_diseases d ON d.id=ds.disease_id WHERE ds.symptom_id={db.PH} AND ds.status='active'",(int(entity_id),))
            item["diseases"]=[dict(zip(["disease_id","slug","name_ar","name_en","weight","typicality"],r)) for r in c.fetchall()]
            c.execute(f"SELECT s.id,s.source_name,s.organization,s.official_url,ss.reference_title_ar,ss.reference_title_en,ss.reference_url,ss.last_verified FROM mk_symptom_sources ss JOIN mk_sources s ON s.id=ss.source_id WHERE ss.symptom_id={db.PH} AND ss.status='active' AND s.status='active'",(int(entity_id),))
            item["sources"]=[dict(zip(["id","source_name","organization","official_url","reference_title_ar","reference_title_en","reference_url","last_verified"],r)) for r in c.fetchall()]
        return item
    finally: conn.close()


def save_source(data, admin, entity_id=None):
    init_schema(); name=str(data.get("source_name") or "").strip(); org=str(data.get("organization") or "").strip(); url=str(data.get("official_url") or "").strip()
    if not name or not org or not _url_is_trusted(url): raise ValueError("invalid_or_untrusted_source")
    typ=str(data.get("source_type") or ""); status=str(data.get("status") or "draft"); verification=str(data.get("verification_status") or "needs_review")
    reliability=str(data.get("reliability_level") or "high"); language=str(data.get("language") or "multiple")
    try: priority=max(1,min(999,int(data.get("priority") or SOURCE_TYPE_PRIORITY.get(typ,50))))
    except Exception: raise ValueError("invalid_priority")
    if typ not in ALLOWED_SOURCE_TYPES or status not in VALID_CONTENT_STATUS or verification not in VALID_VERIFICATION or reliability not in VALID_RELIABILITY or language not in VALID_SOURCE_LANGUAGES: raise ValueError("invalid_status_or_type")
    if verification=="verified" and not data.get("last_verified"): data["last_verified"]=_now()[:10]
    conn=db._conn()
    try:
        c=conn.cursor(); old=_record(c,"mk_sources",entity_id) if entity_id else None; now=_now(); slug=str(data.get("slug") or _normalize_text(name).replace(" ","-") or "source"); version=int((old or {}).get("version") or 0)+1
        if entity_id:
            # Published diseases may never be left without at least one active,
            # verified, allow-listed source.  Link a replacement before
            # disabling or de-verifying the last source.
            if status != "active" or verification != "verified":
                c.execute(
                    f"SELECT DISTINCT d.id FROM mk_disease_sources ds "
                    f"JOIN mk_diseases d ON d.id=ds.disease_id "
                    f"WHERE ds.source_id={db.PH} AND ds.status='active' AND d.status='active'",
                    (int(entity_id),),
                )
                for disease_row in c.fetchall():
                    c.execute(
                        f"SELECT s.official_url FROM mk_disease_sources ds "
                        f"JOIN mk_sources s ON s.id=ds.source_id "
                        f"WHERE ds.disease_id={db.PH} AND ds.source_id<>{db.PH} "
                        f"AND ds.status='active' AND s.status='active' "
                        f"AND s.verification_status='verified'",
                        (int(disease_row[0]), int(entity_id)),
                    )
                    if not any(_url_is_trusted(r[0]) for r in c.fetchall()):
                        raise ValueError("source_is_only_trusted_reference")
                c.execute(
                    f"SELECT DISTINCT s.id FROM mk_symptom_sources ss "
                    f"JOIN mk_symptoms s ON s.id=ss.symptom_id "
                    f"WHERE ss.source_id={db.PH} AND ss.status='active' AND s.status='active'",
                    (int(entity_id),),
                )
                for symptom_row in c.fetchall():
                    c.execute(
                        f"SELECT src.official_url FROM mk_symptom_sources ss "
                        f"JOIN mk_sources src ON src.id=ss.source_id "
                        f"WHERE ss.symptom_id={db.PH} AND ss.source_id<>{db.PH} "
                        f"AND ss.status='active' AND src.status='active' "
                        f"AND src.verification_status='verified'",
                        (int(symptom_row[0]), int(entity_id)),
                    )
                    if not any(_url_is_trusted(r[0]) for r in c.fetchall()):
                        raise ValueError("source_is_only_trusted_reference")
            # A source organization cannot be silently moved to another host
            # while its disease/symptom citations still point at the old host.
            c.execute(
                f"SELECT reference_url FROM mk_disease_sources WHERE source_id={db.PH} "
                f"UNION ALL SELECT reference_url FROM mk_symptom_sources WHERE source_id={db.PH}",
                (int(entity_id), int(entity_id)),
            )
            if any(not _source_url_matches(url, row[0]) for row in c.fetchall()):
                raise ValueError("linked_reference_url_must_match_source")
        fields=(slug,name,org,url,str(data.get("description_ar") or ""),str(data.get("description_en") or ""),language,typ,reliability,verification,data.get("last_verified"),status,priority,version,now)
        if entity_id:
            c.execute(f"UPDATE mk_sources SET slug={db.PH},source_name={db.PH},organization={db.PH},official_url={db.PH},description_ar={db.PH},description_en={db.PH},language={db.PH},source_type={db.PH},reliability_level={db.PH},verification_status={db.PH},last_verified={db.PH},status={db.PH},priority={db.PH},version={db.PH},updated_at={db.PH} WHERE id={db.PH}",fields+(int(entity_id),)); eid=int(entity_id)
        else:
            c.execute(f"INSERT INTO mk_sources (slug,source_name,organization,official_url,description_ar,description_en,language,source_type,reliability_level,verification_status,last_verified,status,priority,version,created_at,updated_at) VALUES ({','.join([db.PH]*16)})",fields[:-1]+(now,now)); eid=_id(c)
        new=_record(c,"mk_sources",eid); _audit(c,admin,"updated" if old else "created","source",eid,old,new); conn.commit(); return new
    finally: conn.close()


def _entity_sources(c, kind, entity_id):
    table="mk_disease_sources" if kind=="disease" else "mk_symptom_sources"; col="disease_id" if kind=="disease" else "symptom_id"
    c.execute(f"SELECT source_id FROM {table} WHERE {col}={db.PH} AND status='active'",(int(entity_id),)); return [int(r[0]) for r in c.fetchall()]


def save_disease(data, admin, entity_id=None):
    init_schema(); ar=str(data.get("name_ar") or "").strip(); en=str(data.get("name_en") or "").strip(); source_ids=[int(x) for x in (data.get("source_ids") or [])]
    if not ar or not en or not str(data.get("description_ar") or "").strip() or not str(data.get("description_en") or "").strip(): raise ValueError("missing_required_fields")
    status=str(data.get("status") or "draft"); severity=str(data.get("severity") or "moderate")
    if status not in VALID_CONTENT_STATUS or severity not in VALID_SEVERITY: raise ValueError("invalid_status_or_severity")
    conn=db._conn()
    try:
        c=conn.cursor(); old=_record(c,"mk_diseases",entity_id) if entity_id else None
        if _duplicates(c,"mk_diseases",ar,en,entity_id): raise ValueError("duplicate_disease")
        if data.get("category_id"):
            c.execute(f"SELECT 1 FROM mk_categories WHERE id={db.PH} AND status='active'",(int(data.get("category_id")),))
            if not c.fetchone(): raise ValueError("invalid_category")
        existing=_entity_sources(c,"disease",entity_id) if entity_id else []
        trusted=_verified_source_ids(c,source_ids or existing)
        if not trusted: raise ValueError("trusted_source_required")
        now=_now(); slug=str(data.get("slug") or _normalize_text(en).replace(" ","-")); version=int((old or {}).get("version") or 0)+1
        vals=(slug,ar,en,str(data.get("description_ar")),str(data.get("description_en")),data.get("category_id"),severity,str(data.get("risk_factors_ar") or ""),str(data.get("risk_factors_en") or ""),str(data.get("common_causes_ar") or ""),str(data.get("common_causes_en") or ""),str(data.get("red_flags_ar") or ""),str(data.get("red_flags_en") or ""),_dump(data.get("related_diseases") or []),str(data.get("recommended_next_step_ar") or ""),str(data.get("recommended_next_step_en") or ""),str(data.get("last_updated") or now[:10]),status,version,now)
        if not vals[14] or not vals[15]: raise ValueError("next_step_required")
        if entity_id:
            c.execute(f"UPDATE mk_diseases SET slug={db.PH},name_ar={db.PH},name_en={db.PH},description_ar={db.PH},description_en={db.PH},category_id={db.PH},severity={db.PH},risk_factors_ar={db.PH},risk_factors_en={db.PH},common_causes_ar={db.PH},common_causes_en={db.PH},red_flags_ar={db.PH},red_flags_en={db.PH},related_diseases={db.PH},recommended_next_step_ar={db.PH},recommended_next_step_en={db.PH},last_updated={db.PH},status={db.PH},version={db.PH},updated_at={db.PH} WHERE id={db.PH}",vals+(int(entity_id),)); eid=int(entity_id)
        else:
            c.execute(f"INSERT INTO mk_diseases (slug,name_ar,name_en,description_ar,description_en,category_id,severity,risk_factors_ar,risk_factors_en,common_causes_ar,common_causes_en,red_flags_ar,red_flags_en,related_diseases,recommended_next_step_ar,recommended_next_step_en,last_updated,status,version,created_at,updated_at) VALUES ({','.join([db.PH]*21)})",vals[:-1]+(now,now)); eid=_id(c)
        if source_ids: _replace_source_links(c,"disease",eid,trusted,data.get("source_references") or {},now)
        new=_record(c,"mk_diseases",eid); _audit(c,admin,"updated" if old else "created","disease",eid,old,new); conn.commit(); return new
    finally: conn.close()


def save_symptom(data, admin, entity_id=None):
    init_schema(); ar=str(data.get("name_ar") or "").strip(); en=str(data.get("name_en") or "").strip(); source_ids=[int(x) for x in (data.get("source_ids") or [])]
    if not ar or not en or not str(data.get("description_ar") or "").strip() or not str(data.get("description_en") or "").strip(): raise ValueError("missing_required_fields")
    status=str(data.get("status") or "draft")
    if status not in VALID_CONTENT_STATUS: raise ValueError("invalid_status")
    conn=db._conn()
    try:
        c=conn.cursor(); old=_record(c,"mk_symptoms",entity_id) if entity_id else None
        if _duplicates(c,"mk_symptoms",ar,en,entity_id): raise ValueError("duplicate_symptom")
        if data.get("category_id"):
            c.execute(f"SELECT 1 FROM mk_categories WHERE id={db.PH} AND status='active'",(int(data.get("category_id")),))
            if not c.fetchone(): raise ValueError("invalid_category")
        existing=_entity_sources(c,"symptom",entity_id) if entity_id else []; trusted=_verified_source_ids(c,source_ids or existing)
        if not trusted: raise ValueError("trusted_source_required")
        now=_now(); slug=str(data.get("slug") or _normalize_text(en).replace(" ","-")); version=int((old or {}).get("version") or 0)+1
        sev_min=max(1,min(5,int(data.get("severity_min") or 1))); sev_max=max(1,min(5,int(data.get("severity_max") or 5)))
        if sev_min>sev_max: raise ValueError("invalid_severity_range")
        vals=(slug,ar,en,str(data.get("description_ar")),str(data.get("description_en")),data.get("category_id"),sev_min,sev_max,_dump(data.get("aliases_ar") or []),_dump(data.get("aliases_en") or []),str(data.get("red_flags_ar") or ""),str(data.get("red_flags_en") or ""),status,version,now)
        if entity_id:
            c.execute(f"UPDATE mk_symptoms SET slug={db.PH},name_ar={db.PH},name_en={db.PH},description_ar={db.PH},description_en={db.PH},category_id={db.PH},severity_min={db.PH},severity_max={db.PH},aliases_ar={db.PH},aliases_en={db.PH},red_flags_ar={db.PH},red_flags_en={db.PH},status={db.PH},version={db.PH},updated_at={db.PH} WHERE id={db.PH}",vals+(int(entity_id),)); eid=int(entity_id)
        else:
            c.execute(f"INSERT INTO mk_symptoms (slug,name_ar,name_en,description_ar,description_en,category_id,severity_min,severity_max,aliases_ar,aliases_en,red_flags_ar,red_flags_en,status,version,created_at,updated_at) VALUES ({','.join([db.PH]*16)})",vals[:-1]+(now,now)); eid=_id(c)
        if source_ids: _replace_source_links(c,"symptom",eid,trusted,data.get("source_references") or {},now)
        new=_record(c,"mk_symptoms",eid); _audit(c,admin,"updated" if old else "created","symptom",eid,old,new); conn.commit(); return new
    finally: conn.close()


def _replace_source_links(c, kind, entity_id, source_ids, references, now):
    table="mk_disease_sources" if kind=="disease" else "mk_symptom_sources"; col="disease_id" if kind=="disease" else "symptom_id"
    c.execute(
        f"SELECT source_id,reference_title_ar,reference_title_en,reference_url FROM {table} "
        f"WHERE {col}={db.PH}", (int(entity_id),),
    )
    existing = {
        str(r[0]): {"reference_title_ar": r[1], "reference_title_en": r[2], "reference_url": r[3]}
        for r in c.fetchall()
    }
    c.execute(f"DELETE FROM {table} WHERE {col}={db.PH}",(int(entity_id),))
    for sid in source_ids:
        c.execute(f"SELECT source_name,official_url FROM mk_sources WHERE id={db.PH}",(int(sid),)); src=c.fetchone()
        if not src: continue
        supplied = references.get(str(sid), {}) if isinstance(references, dict) else {}
        ref = supplied or existing.get(str(sid), {})
        url=str(ref.get("reference_url") or src[1])
        if not _source_url_matches(src[1],url): raise ValueError("reference_url_must_match_source")
        title_ar=str(ref.get("reference_title_ar") or src[0]); title_en=str(ref.get("reference_title_en") or src[0])
        c.execute(f"INSERT INTO {table} ({col},source_id,reference_title_ar,reference_title_en,reference_url,last_verified,status,created_at,updated_at) VALUES ({','.join([db.PH]*9)})",(int(entity_id),int(sid),title_ar,title_en,url,now[:10],"active",now,now))


def save_relationship(data, admin, relationship_id=None):
    init_schema(); did=int(data.get("disease_id")); sid=int(data.get("symptom_id")); weight=float(data.get("weight") or .5)
    if not 0 < weight <= 1: raise ValueError("weight_out_of_range")
    typicality=str(data.get("typicality") or "common")
    status=str(data.get("status") or "active")
    if typicality not in {"very_common","common","less_common"} or status not in VALID_CONTENT_STATUS: raise ValueError("invalid_relationship")
    conn=db._conn()
    try:
        c=conn.cursor(); now=_now(); old=None
        c.execute(f"SELECT 1 FROM mk_diseases WHERE id={db.PH}",(did,))
        if not c.fetchone(): raise ValueError("disease_not_found")
        c.execute(f"SELECT 1 FROM mk_symptoms WHERE id={db.PH}",(sid,))
        if not c.fetchone(): raise ValueError("symptom_not_found")
        if relationship_id:
            c.execute(f"SELECT id,disease_id,symptom_id,weight,typicality,notes_ar,notes_en,status FROM mk_disease_symptoms WHERE id={db.PH}",(int(relationship_id),)); r=c.fetchone(); old=dict(zip(["id","disease_id","symptom_id","weight","typicality","notes_ar","notes_en","status"],r)) if r else None
            c.execute(f"UPDATE mk_disease_symptoms SET disease_id={db.PH},symptom_id={db.PH},weight={db.PH},typicality={db.PH},notes_ar={db.PH},notes_en={db.PH},status={db.PH},updated_at={db.PH} WHERE id={db.PH}",(did,sid,weight,typicality,str(data.get("notes_ar") or ""),str(data.get("notes_en") or ""),status,now,int(relationship_id))); rid=int(relationship_id)
        else:
            c.execute(f"INSERT INTO mk_disease_symptoms (disease_id,symptom_id,weight,typicality,notes_ar,notes_en,status,created_at,updated_at) VALUES ({','.join([db.PH]*9)}) ON CONFLICT(disease_id,symptom_id) DO UPDATE SET weight=excluded.weight,typicality=excluded.typicality,notes_ar=excluded.notes_ar,notes_en=excluded.notes_en,status=excluded.status,updated_at=excluded.updated_at",(did,sid,weight,typicality,str(data.get("notes_ar") or ""),str(data.get("notes_en") or ""),status,now,now))
            c.execute(f"SELECT id FROM mk_disease_symptoms WHERE disease_id={db.PH} AND symptom_id={db.PH}",(did,sid)); rid=int(c.fetchone()[0])
        new={"id":rid,"disease_id":did,"symptom_id":sid,"weight":weight,"typicality":typicality,"notes_ar":str(data.get("notes_ar") or ""),"notes_en":str(data.get("notes_en") or ""),"status":status}; _audit(c,admin,"updated" if old else "created","relationship",rid,old,new); conn.commit(); return new
    finally: conn.close()


def list_relationships(search=""):
    init_schema(); conn=db._conn()
    try:
        c=conn.cursor(); c.execute("""SELECT ds.id,ds.disease_id,d.name_ar,d.name_en,ds.symptom_id,s.name_ar,s.name_en,
                                             ds.weight,ds.typicality,ds.notes_ar,ds.notes_en,ds.status,ds.updated_at
                                      FROM mk_disease_symptoms ds
                                      JOIN mk_diseases d ON d.id=ds.disease_id
                                      JOIN mk_symptoms s ON s.id=ds.symptom_id
                                      ORDER BY d.name_en,ds.weight DESC""")
        keys=["id","disease_id","disease_name_ar","disease_name_en","symptom_id","symptom_name_ar","symptom_name_en","weight","typicality","notes_ar","notes_en","status","updated_at"]
        out=[]; q=_normalize_text(search)
        for row in c.fetchall():
            item=dict(zip(keys,row))
            if q and q not in _normalize_text(" ".join(str(item.get(k) or "") for k in ("disease_name_ar","disease_name_en","symptom_name_ar","symptom_name_en"))): continue
            out.append(item)
        return out
    finally: conn.close()


def save_red_flag(data, admin, entity_id=None):
    init_schema(); ar=str(data.get("name_ar") or "").strip(); en=str(data.get("name_en") or "").strip()
    if not ar or not en or not str(data.get("message_ar") or "").strip() or not str(data.get("message_en") or "").strip(): raise ValueError("missing_required_fields")
    risk=str(data.get("risk_level") or data.get("severity") or "urgent"); mode=str(data.get("match_mode") or "all"); status=str(data.get("status") or "active")
    if risk not in {"urgent","review"} or mode not in {"all","any"} or status not in {"active","disabled"}: raise ValueError("invalid_red_flag")
    required=[str(x).strip() for x in (data.get("required_symptoms") or []) if str(x).strip()]
    keywords_ar=[str(x).strip() for x in (data.get("keywords_ar") or []) if str(x).strip()]
    keywords_en=[str(x).strip() for x in (data.get("keywords_en") or []) if str(x).strip()]
    if not required and not keywords_ar and not keywords_en: raise ValueError("red_flag_trigger_required")
    source_id=data.get("source_id")
    if not source_id: raise ValueError("verified_source_required")
    conn=db._conn()
    try:
        c=conn.cursor(); old=_record(c,"mk_red_flags",entity_id) if entity_id else None; now=_now(); slug=str(data.get("slug") or _normalize_text(en).replace(" ","-")); version=int((old or {}).get("version") or 0)+1
        for symptom_slug in required:
            c.execute(f"SELECT 1 FROM mk_symptoms WHERE slug={db.PH} AND status='active'",(symptom_slug,))
            if not c.fetchone(): raise ValueError("invalid_red_flag_symptom")
        c.execute(f"SELECT official_url FROM mk_sources WHERE id={db.PH} AND status='active' AND verification_status='verified'",(int(source_id),))
        source_row=c.fetchone()
        if not source_row or not _url_is_trusted(source_row[0]): raise ValueError("verified_source_required")
        reference_url=str(data.get("reference_url") or source_row[0]).strip()
        if not _source_url_matches(source_row[0], reference_url): raise ValueError("reference_url_must_match_source")
        description_ar=str(data.get("description_ar") or data.get("message_ar") or "").strip()
        description_en=str(data.get("description_en") or data.get("message_en") or "").strip()
        action_ar=str(data.get("recommended_action_ar") or data.get("message_ar") or "").strip()
        action_en=str(data.get("recommended_action_en") or data.get("message_en") or "").strip()
        last_updated=str(data.get("last_updated") or now[:10])
        vals=(slug,ar,en,description_ar,description_en,_dump(required),mode,_dump(keywords_ar),_dump(keywords_en),max(1,min(5,int(data.get("min_severity") or 1))),risk,risk,str(data.get("message_ar")),str(data.get("message_en")),action_ar,action_en,int(source_id),reference_url,last_updated,status,version,now)
        if entity_id:
            c.execute(f"UPDATE mk_red_flags SET slug={db.PH},name_ar={db.PH},name_en={db.PH},description_ar={db.PH},description_en={db.PH},required_symptoms={db.PH},match_mode={db.PH},keywords_ar={db.PH},keywords_en={db.PH},min_severity={db.PH},severity={db.PH},risk_level={db.PH},message_ar={db.PH},message_en={db.PH},recommended_action_ar={db.PH},recommended_action_en={db.PH},source_id={db.PH},reference_url={db.PH},last_updated={db.PH},status={db.PH},version={db.PH},updated_at={db.PH} WHERE id={db.PH}",vals+(int(entity_id),)); eid=int(entity_id)
        else:
            c.execute(f"INSERT INTO mk_red_flags (slug,name_ar,name_en,description_ar,description_en,required_symptoms,match_mode,keywords_ar,keywords_en,min_severity,severity,risk_level,message_ar,message_en,recommended_action_ar,recommended_action_en,source_id,reference_url,last_updated,status,version,created_at,updated_at) VALUES ({','.join([db.PH]*23)})",vals[:-1]+(now,now)); eid=_id(c)
        new=_record(c,"mk_red_flags",eid); _audit(c,admin,"updated" if old else "created","red_flag",eid,old,new); conn.commit(); return new
    finally: conn.close()


def save_source_link(kind, entity_id, data, admin):
    init_schema()
    if kind not in {"disease","symptom"}: raise ValueError("invalid_entity")
    source_id=int(data.get("source_id")); table="mk_disease_sources" if kind=="disease" else "mk_symptom_sources"; col="disease_id" if kind=="disease" else "symptom_id"
    conn=db._conn()
    try:
        c=conn.cursor(); c.execute(f"SELECT source_name,official_url,verification_status,status FROM mk_sources WHERE id={db.PH}",(source_id,)); src=c.fetchone()
        if not src or src[2]!="verified" or src[3]!="active": raise ValueError("verified_source_required")
        url=str(data.get("reference_url") or src[1]);
        if not _source_url_matches(src[1],url): raise ValueError("reference_url_must_match_source")
        now=_now(); title_ar=str(data.get("reference_title_ar") or src[0]); title_en=str(data.get("reference_title_en") or src[0])
        c.execute(f"SELECT id,reference_title_ar,reference_title_en,reference_url,status FROM {table} WHERE {col}={db.PH} AND source_id={db.PH}",(int(entity_id),source_id)); row=c.fetchone(); old=dict(zip(["id","reference_title_ar","reference_title_en","reference_url","status"],row)) if row else None
        c.execute(f"INSERT INTO {table} ({col},source_id,reference_title_ar,reference_title_en,reference_url,last_verified,status,created_at,updated_at) VALUES ({','.join([db.PH]*9)}) ON CONFLICT({col},source_id) DO UPDATE SET reference_title_ar=excluded.reference_title_ar,reference_title_en=excluded.reference_title_en,reference_url=excluded.reference_url,last_verified=excluded.last_verified,status='active',updated_at=excluded.updated_at",(int(entity_id),source_id,title_ar,title_en,url,now[:10],"active",now,now))
        c.execute(f"SELECT id FROM {table} WHERE {col}={db.PH} AND source_id={db.PH}",(int(entity_id),source_id)); link_id=int(c.fetchone()[0]); new={"id":link_id,"source_id":source_id,"reference_title_ar":title_ar,"reference_title_en":title_en,"reference_url":url,"status":"active"}; _audit(c,admin,"updated" if old else "linked",kind+"_source",link_id,old,new); conn.commit(); return new
    finally: conn.close()


def delete_source_link(kind, entity_id, source_id, admin):
    init_schema()
    if kind not in {"disease","symptom"}: raise ValueError("invalid_entity")
    table="mk_disease_sources" if kind=="disease" else "mk_symptom_sources"; col="disease_id" if kind=="disease" else "symptom_id"
    conn=db._conn()
    try:
        c=conn.cursor(); c.execute(f"SELECT id,source_id,reference_url,status FROM {table} WHERE {col}={db.PH} AND source_id={db.PH}",(int(entity_id),int(source_id))); row=c.fetchone()
        if not row: return False
        if kind=="disease":
            c.execute(f"SELECT COUNT(*) FROM {table} WHERE {col}={db.PH} AND status='active' AND source_id<>{db.PH}",(int(entity_id),int(source_id)))
            if int(c.fetchone()[0])<1: raise ValueError("disease_requires_one_trusted_source")
        old={"id":row[0],"source_id":row[1],"reference_url":row[2],"status":row[3]}; c.execute(f"DELETE FROM {table} WHERE id={db.PH}",(int(row[0]),)); _audit(c,admin,"unlinked",kind+"_source",int(row[0]),old,None); conn.commit(); return True
    finally: conn.close()


def delete_entity(kind, entity_id, admin):
    init_schema(); table={"disease":"mk_diseases","symptom":"mk_symptoms","source":"mk_sources","red_flag":"mk_red_flags","relationship":"mk_disease_symptoms"}.get(kind)
    if not table: raise ValueError("invalid_entity")
    conn=db._conn()
    try:
        c=conn.cursor()
        if kind=="source":
            c.execute(f"SELECT COUNT(*) FROM mk_disease_sources WHERE source_id={db.PH}",(int(entity_id),))
            disease_links=int(c.fetchone()[0] or 0)
            c.execute(f"SELECT COUNT(*) FROM mk_symptom_sources WHERE source_id={db.PH}",(int(entity_id),))
            symptom_links=int(c.fetchone()[0] or 0)
            # Sources with relationships are historical medical evidence. Keep
            # the row/URLs intact and disable it instead of breaking old links.
            if disease_links or symptom_links:
                old=_record(c,table,entity_id)
                if not old: return False
                c.execute(f"UPDATE mk_sources SET status='disabled',updated_at={db.PH} WHERE id={db.PH}",(_now(),int(entity_id)))
                new=_record(c,table,entity_id); _audit(c,admin,"disabled","source",int(entity_id),old,new); conn.commit(); return True
        if kind=="relationship":
            c.execute(f"SELECT id,disease_id,symptom_id,weight,typicality,notes_ar,notes_en,status FROM mk_disease_symptoms WHERE id={db.PH}",(int(entity_id),)); row=c.fetchone(); old=dict(zip(["id","disease_id","symptom_id","weight","typicality","notes_ar","notes_en","status"],row)) if row else None
        else: old=_record(c,table,entity_id)
        if not old: return False
        c.execute(f"DELETE FROM {table} WHERE id={db.PH}",(int(entity_id),)); _audit(c,admin,"deleted",kind,int(entity_id),old,None); conn.commit(); return True
    finally: conn.close()


def categories(search="", include_inactive=True):
    init_schema(); conn=db._conn()
    try:
        c=conn.cursor(); c.execute("SELECT id,slug,name_ar,name_en,status,created_at,updated_at FROM mk_categories ORDER BY id")
        rows=[dict(zip(["id","slug","name_ar","name_en","status","created_at","updated_at"],r)) for r in c.fetchall()]
        q=_normalize_text(search)
        out=[]
        for item in rows:
            if not include_inactive and item.get("status") != "active": continue
            if q and q not in _normalize_text(" ".join(str(item.get(k) or "") for k in ("slug","name_ar","name_en"))): continue
            out.append(item)
        return out
    finally: conn.close()


def save_category(data, admin, entity_id=None):
    init_schema()
    ar=str(data.get("name_ar") or "").strip(); en=str(data.get("name_en") or "").strip()
    status=str(data.get("status") or "active").strip()
    slug=str(data.get("slug") or _normalize_text(en).replace(" ","-")).strip().lower()
    slug=re.sub(r"[^a-z0-9-]+","-",slug).strip("-")
    if not ar or not en or not slug: raise ValueError("missing_required_fields")
    if status not in VALID_CONTENT_STATUS: raise ValueError("invalid_status")
    conn=db._conn()
    try:
        c=conn.cursor(); now=_now()
        old=None
        if entity_id:
            c.execute(f"SELECT id,slug,name_ar,name_en,status,created_at,updated_at FROM mk_categories WHERE id={db.PH}",(int(entity_id),))
            r=c.fetchone(); old=dict(zip(["id","slug","name_ar","name_en","status","created_at","updated_at"],r)) if r else None
            if not old: raise ValueError("category_not_found")
            c.execute(f"UPDATE mk_categories SET slug={db.PH},name_ar={db.PH},name_en={db.PH},status={db.PH},updated_at={db.PH} WHERE id={db.PH}",(slug,ar,en,status,now,int(entity_id)))
            eid=int(entity_id)
        else:
            if db.USE_POSTGRES:
                c.execute(f"INSERT INTO mk_categories (slug,name_ar,name_en,status,created_at,updated_at) VALUES ({','.join([db.PH]*6)}) RETURNING id",(slug,ar,en,status,now,now)); eid=int(c.fetchone()[0])
            else:
                c.execute(f"INSERT INTO mk_categories (slug,name_ar,name_en,status,created_at,updated_at) VALUES ({','.join([db.PH]*6)})",(slug,ar,en,status,now,now)); eid=int(c.lastrowid)
        c.execute(f"SELECT id,slug,name_ar,name_en,status,created_at,updated_at FROM mk_categories WHERE id={db.PH}",(eid,))
        r=c.fetchone(); new=dict(zip(["id","slug","name_ar","name_en","status","created_at","updated_at"],r))
        _audit(c,admin,"updated" if old else "created","category",eid,old,new); conn.commit(); return new
    except Exception:
        conn.rollback(); raise
    finally: conn.close()


def delete_category(entity_id, admin):
    init_schema(); conn=db._conn()
    try:
        c=conn.cursor(); c.execute(f"SELECT id,slug,name_ar,name_en,status,created_at,updated_at FROM mk_categories WHERE id={db.PH}",(int(entity_id),)); r=c.fetchone()
        if not r: return False
        old=dict(zip(["id","slug","name_ar","name_en","status","created_at","updated_at"],r))
        c.execute(f"SELECT COUNT(*) FROM mk_diseases WHERE category_id={db.PH}",(int(entity_id),)); d=int(c.fetchone()[0] or 0)
        c.execute(f"SELECT COUNT(*) FROM mk_symptoms WHERE category_id={db.PH}",(int(entity_id),)); sy=int(c.fetchone()[0] or 0)
        if d or sy: raise ValueError("category_in_use_disable_instead")
        c.execute(f"DELETE FROM mk_categories WHERE id={db.PH}",(int(entity_id),)); _audit(c,admin,"deleted","category",int(entity_id),old,None); conn.commit(); return True
    except Exception:
        conn.rollback(); raise
    finally: conn.close()


def audit_log(limit=100):
    init_schema(); conn=db._conn()
    try:
        c=conn.cursor(); c.execute(f"SELECT id,admin_id,action,entity_type,entity_id,previous_value,new_value,timestamp FROM mk_audit_log ORDER BY id DESC LIMIT {db.PH}",(max(1,min(int(limit),500)),)); return [dict(zip(["id","admin_id","action","entity_type","entity_id","previous_value","new_value","timestamp"],r)) for r in c.fetchall()]
    finally: conn.close()


def versions(entity_type, entity_id):
    init_schema(); conn=db._conn()
    try:
        c=conn.cursor(); c.execute(f"SELECT id,version,snapshot,admin_id,admin_email,timestamp FROM mk_versions WHERE entity_type={db.PH} AND entity_id={db.PH} ORDER BY version DESC",(entity_type,int(entity_id))); return [{"id":r[0],"version":r[1],"snapshot":_json(r[2],{}),"admin_id":r[3],"admin_email":r[4],"timestamp":r[5]} for r in c.fetchall()]
    finally: conn.close()


def statistics():
    init_schema(); conn=db._conn()
    try:
        c=conn.cursor()
        def count(table, where="1=1"):
            c.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}"); return int(c.fetchone()[0])
        c.execute("SELECT MAX(updated_at) FROM (SELECT updated_at FROM mk_diseases UNION ALL SELECT updated_at FROM mk_symptoms UNION ALL SELECT updated_at FROM mk_sources) x")
        last=c.fetchone()[0]
        return {"total_diseases":count("mk_diseases"),"total_symptoms":count("mk_symptoms"),"total_sources":count("mk_sources"),"active_diseases":count("mk_diseases","status='active'"),"active_symptoms":count("mk_symptoms","status='active'"),"verified_sources":count("mk_sources","status='active' AND verification_status='verified'"),"sources_needing_review":count("mk_sources","verification_status='needs_review'"),"last_knowledge_update":last}
    finally: conn.close()


def system_health():
    """Run live, read-only health checks without exposing credentials."""
    init_schema(); checked=_now(); health={}
    start=time.perf_counter()
    try:
        conn=db._conn(); c=conn.cursor(); c.execute("SELECT 1"); c.fetchone(); conn.close()
        health["database"]={"status":"online","response_ms":round((time.perf_counter()-start)*1000,1),"error":None}
    except Exception as e:
        health["database"]={"status":"offline","response_ms":round((time.perf_counter()-start)*1000,1),"error":str(e)[:160]}

    start=time.perf_counter(); key=os.environ.get("GROQ_API_KEY","").strip()
    if not key:
        health["ai_service"]={"status":"not_configured","response_ms":round((time.perf_counter()-start)*1000,1),"error":"GROQ_API_KEY is not configured"}
    else:
        try:
            req=Request("https://api.groq.com/openai/v1/models",headers={"Authorization":"Bearer "+key,"User-Agent":"SymptoSense-HealthCheck/1.0"})
            with urlopen(req, timeout=4) as response:
                ok=200 <= int(getattr(response,"status",200)) < 300
            health["ai_service"]={"status":"online" if ok else "offline","response_ms":round((time.perf_counter()-start)*1000,1),"error":None if ok else "Unexpected AI service response"}
        except HTTPError as e:
            health["ai_service"]={"status":"offline","response_ms":round((time.perf_counter()-start)*1000,1),"error":f"HTTP {e.code}: {str(e.reason)[:100]}"}
        except (URLError, TimeoutError, OSError) as e:
            health["ai_service"]={"status":"offline","response_ms":round((time.perf_counter()-start)*1000,1),"error":str(getattr(e,"reason",e))[:160]}

    start=time.perf_counter()
    try:
        conn=db._conn(); c=conn.cursor(); c.execute("SELECT id,status,role FROM ss_users LIMIT 1"); c.fetchone(); conn.close()
        health["authentication"]={"status":"online","response_ms":round((time.perf_counter()-start)*1000,1),"error":None}
    except Exception as e:
        health["authentication"]={"status":"offline","response_ms":round((time.perf_counter()-start)*1000,1),"error":str(e)[:160]}
    return {"checked_at":checked,"components":health}

