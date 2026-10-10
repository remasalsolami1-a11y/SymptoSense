"""Structured, source-grounded medical knowledge for SymptoSense.

This module stores only general medical content.  It never reads or writes
patient records.  Matching is intentionally qualitative and explainable; it is
not a diagnostic probability model.
"""
from __future__ import annotations
import logging

import difflib
import json
import os
import re
import threading
import time
import unicodedata
import clinical_text
from datetime import datetime, timedelta, timezone
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
    "academic_medical_institution", "clinical_guideline_body", "other_trusted_source",
}
SOURCE_TYPE_PRIORITY = {
    "government": 10,
    "international_organization": 20,
    "national_health_service": 30,
    "academic_medical_institution": 40,
    "clinical_guideline_body": 15,
    "other_trusted_source": 50,
}
DEFAULT_ALLOWED_DOMAINS = {
    "moh.gov.sa", "who.int", "emro.who.int", "nhs.uk", "cdc.gov",
    "mayoclinic.org", "medlineplus.gov", "nih.gov", "nice.org.uk",
    "womenshealth.gov", "heart.org", "aad.org", "sfda.gov.sa",
}

# Keyed by db._database_identity() rather than a plain boolean so that a
# different/replaced database within the same process (e.g. isolated test
# suites each pointing at their own SQLite file) is detected and its schema
# is (re)created instead of being silently skipped. See db.py's _DB_READY_KEY
# for the same pattern.
_READY_KEY = None
_LOCK = threading.Lock()


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _json(value, default=None):
    if value is None:
        value = [] if default is None else default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError, OverflowError):
            logging.getLogger(__name__).debug("Handled exception in _json; fallback applied (handler 66)")
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
        logging.getLogger(__name__).warning("Handled exception in _url_is_trusted; fallback applied (handler 92)")
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
    global _READY_KEY
    current_key = db._database_identity()
    if _READY_KEY == current_key:
        return
    with _LOCK:
        current_key = db._database_identity()
        if _READY_KEY == current_key:
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
            # Anonymous coverage-gap log: no user identifiers, only the raw
            # symptom phrase (as typed) and whether it matched the knowledge
            # base. This is the data source for deciding which new symptoms
            # or aliases to add next, instead of guessing.
            c.execute(f"""CREATE TABLE IF NOT EXISTS mk_unmatched_log (
                id {serial}, phrase TEXT NOT NULL, lang TEXT NOT NULL DEFAULT 'ar',
                matched INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
            )""")
            c.execute("CREATE INDEX IF NOT EXISTS idx_mk_unmatched_created ON mk_unmatched_log(created_at)")
            for table in ("mk_sources", "mk_red_flags"):
                if "version" not in _columns(c, table):
                    c.execute(f"ALTER TABLE {table} ADD COLUMN version INTEGER NOT NULL DEFAULT 1")
            # V217: eligibility metadata lives with each condition so sex/age/context
            # filtering happens before scoring instead of hiding a result afterwards.
            disease_cols = _columns(c, "mk_diseases")
            for col, ddl in (
                ("sex_applicability", "TEXT NOT NULL DEFAULT 'any'"),
                ("min_age", "INTEGER"), ("max_age", "INTEGER"),
                ("pregnancy_relevant", "INTEGER NOT NULL DEFAULT 0"),
            ):
                if col not in disease_cols:
                    c.execute(f"ALTER TABLE mk_diseases ADD COLUMN {col} {ddl}")
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
            _READY_KEY = db._database_identity()
        finally:
            conn.close()


CATEGORIES = [
    ("pain", "الألم", "Pain"), ("respiratory", "الجهاز التنفسي", "Respiratory"),
    ("digestive", "الجهاز الهضمي", "Digestive"), ("neurological", "الجهاز العصبي", "Neurological"),
    ("skin", "الجلد", "Skin"), ("cardiovascular", "القلب والأوعية", "Cardiovascular"),
    ("mental-health", "الصحة النفسية", "Mental Health"), ("general", "أعراض عامة", "General Symptoms"),
    ("eye", "العين", "Eye"),
    ("ear", "الأذن والسمع", "Ear & Hearing"),
    ("mouth", "الفم والأسنان", "Mouth & Dental"),
    ("urinary", "المسالك البولية", "Urinary"),
    ("vascular", "الأوعية الدموية", "Vascular"),
    ("musculoskeletal", "العضلات والعظام", "Musculoskeletal"),
    ("womens_health", "صحة المرأة", "Women's Health"),
]

SOURCES = [
    ("saudi-moh", "وزارة الصحة السعودية", "Saudi Ministry of Health", "https://www.moh.gov.sa/", "government", 10, "المصدر الحكومي الرسمي للمعلومات والخدمات والتوعية الصحية في المملكة العربية السعودية.", "Saudi Arabia's official government source for health information, services, and public guidance."),
    ("cdc", "CDC", "Centers for Disease Control and Prevention", "https://www.cdc.gov/", "government", 11, "وكالة صحة عامة أمريكية تنشر إرشادات وبيانات موثوقة عن الأمراض والوقاية منها.", "A U.S. public-health agency publishing authoritative disease, prevention, and safety guidance."),
    ("medlineplus", "MedlinePlus", "U.S. National Library of Medicine", "https://medlineplus.gov/", "government", 12, "موسوعة صحية تثقيفية تابعة للمكتبة الوطنية الأمريكية للطب وموجّهة للجمهور.", "A consumer health resource from the U.S. National Library of Medicine."),
    ("who", "WHO", "World Health Organization", "https://www.who.int/", "international_organization", 20, "المنظمة الدولية التابعة للأمم المتحدة والمسؤولة عن إرشادات وسياسات الصحة العالمية.", "The United Nations agency responsible for international public-health guidance and policy."),
    ("who-emro", "WHO EMRO", "WHO Regional Office for the Eastern Mediterranean", "https://www.emro.who.int/", "international_organization", 21, "المكتب الإقليمي لمنظمة الصحة العالمية لشرق المتوسط ومصدر للإرشادات الصحية الإقليمية.", "WHO's Regional Office for the Eastern Mediterranean and a source of regional health guidance."),
    ("nhs", "NHS", "National Health Service", "https://www.nhs.uk/", "national_health_service", 30, "الخدمة الصحية الوطنية البريطانية ومصدر عام للإرشادات الصحية المبسطة.", "The United Kingdom's National Health Service and a public source of accessible health guidance."),
    ("mayo-clinic", "Mayo Clinic", "Mayo Foundation for Medical Education and Research", "https://www.mayoclinic.org/", "academic_medical_institution", 40, "مؤسسة طبية أكاديمية غير ربحية تنشر معلومات تثقيفية عن الحالات والأعراض.", "A nonprofit academic medical institution publishing educational information about symptoms and conditions."),
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
    ("runny-nose", "سيلان الأنف", "Runny nose", "respiratory", ["رشح", "زكام", "سيلان الانف"], ["runny nose", "nasal discharge"]),
    ("fatigue", "تعب وإرهاق", "Fatigue", "general", ["تعب", "ارهاق", "خمول"], ["tiredness", "exhausted"]),
    ("body-aches", "آلام الجسم", "Body aches", "pain", ["الم عضلات", "ألم العضلات", "جسمي يعورني"], ["muscle aches", "muscle pain"]),
    ("chills", "قشعريرة", "Chills", "general", ["قشعريره", "رجفة برد", "برد شديد"], ["chills", "shivering with cold"]),
    ("diarrhea", "إسهال", "Diarrhea", "digestive", ["اسهال", "براز مائي"], ["diarrhoea", "loose stools"]),
    ("abdominal-pain", "ألم البطن", "Abdominal pain", "digestive", ["الم المعده", "ألم المعدة", "بطني يعورني"], ["stomach pain", "belly pain"]),
    ("dizziness", "دوخة", "Dizziness", "neurological", ["دوار", "عدم توازن"], ["dizzy", "lightheaded"]),
    ("numbness", "تنميل أو خدر", "Numbness or tingling", "neurological", ["تنميل", "تنمل", "خدر", "وخز", "نمنمة", "تنميل المفاصل", "تنميل في المفاصل", "تنميل الاطراف", "تنميل الأطراف", "خدر الاطراف", "خدر الأطراف"], ["numbness", "tingling", "pins and needles", "numb joints", "numb limbs"]),
    ("hand-numbness", "تنميل اليدين أو الأصابع", "Hand or finger numbness", "neurological", ["تنميل اليد", "تنميل اليدين", "تنميل الاصابع", "تنميل الأصابع", "خدر اليد", "وخز الاصابع"], ["hand numbness", "finger numbness", "tingling fingers"]),
    ("foot-numbness", "تنميل القدمين أو أصابع القدم", "Foot or toe numbness", "neurological", ["تنميل القدم", "تنميل القدمين", "تنميل اصابع القدم", "خدر القدم", "وخز القدم"], ["foot numbness", "toe numbness", "tingling feet"]),
    ("facial-numbness", "تنميل الوجه", "Facial numbness", "neurological", ["خدر الوجه", "وخز الوجه", "تنميل في الوجه"], ["face numbness", "facial tingling"]),
    ("one-sided-numbness", "تنميل مفاجئ في جهة واحدة", "Sudden one-sided numbness", "neurological", ["تنميل جهة واحدة", "تنميل في جانب واحد", "خدر جهة واحدة", "نصف جسمي منمل"], ["one sided numbness", "sudden numbness on one side"]),
    ("widespread-numbness", "تنميل في أكثر من مكان", "Numbness in multiple areas", "neurological", ["تنميل منتشر", "تنميل في الجسم", "تنميل بعدة اماكن", "تنميل عدة أماكن"], ["widespread numbness", "numbness in several areas"]),
    ("joint-pain", "ألم المفاصل", "Joint pain", "pain", ["الم المفاصل", "ألم المفاصل", "مفاصلي تعورني", "وجع المفاصل", "مفاصلي توجعني", "توجعني مفاصلي"], ["joint pain", "aching joints"]),
    ("leg-pain", "ألم الرجل أو الساق", "Leg pain", "pain", ["الم الرجل", "ألم الساق", "وجع الرجل", "رجلي تعورني"], ["leg pain", "painful leg"]),
    ("itching", "حكة", "Itching", "skin", ["حكه", "هرش", "حكة الجلد"], ["itching", "itchy skin"]),
    ("eye-redness", "احمرار العين", "Eye redness", "general", ["احمرار العيون", "العين حمراء", "عيوني حمراء"], ["red eye", "eye redness"]),
    ("dehydration", "جفاف", "Dehydration", "general", ["جفاف", "جفاف شديد", "احس اني جاف"], ["dehydration", "dehydrated"]),
    ("wheezing", "صفير التنفس", "Wheezing", "respiratory", ["صفير في الصدر"], ["wheeze"]),
    ("shortness-of-breath", "ضيق التنفس", "Shortness of breath", "respiratory", ["صعوبة التنفس", "ما اقدر اتنفس", "لا استطيع التنفس", "ضيق شديد في التنفس", "ضيق شديد بالتنفس", "صعوبة شديدة في التنفس", "ضيق تنفس شديد", "ضيق تنفس", "ضيق في التنفس"], ["difficulty breathing", "trouble breathing", "breathless", "severe shortness of breath", "severe breathing difficulty"]),
    ("chest-tightness", "ضيق الصدر", "Chest tightness", "respiratory", ["شد في الصدر"], ["tight chest"]),
    ("chest-pain", "ألم الصدر", "Chest pain", "cardiovascular", ["الم في الصدر", "وجع الصدر", "الم بالصدر", "ألم بالصدر", "ألم صدر شديد", "الم صدر شديد", "ألم شديد في الصدر", "الم شديد بالصدر", "الم شديد في الصدر", "وجع شديد بالصدر"], ["pain in chest", "heart pain", "severe chest pain", "crushing chest pain", "squeezing chest pain"]),
    ("sweating", "تعرق غير معتاد", "Unusual sweating", "general", ["عرق بارد", "تعرق شديد"], ["cold sweat", "sweating heavily"]),
    ("one-sided-weakness", "ضعف في جانب واحد", "One-sided weakness", "neurological", ["ضعف جهة واحدة", "ضعف مفاجئ", "ضعف مفاجئ في جهة واحدة"], ["weakness on one side", "arm weakness", "sudden weakness", "sudden arm weakness"]),
    ("speech-difficulty", "صعوبة في الكلام", "Speech difficulty", "neurological", ["ثقل الكلام", "الكلام متداخل", "صعوبة مفاجئة في الكلام", "صعوبه مفاجئه في الكلام"], ["slurred speech", "trouble speaking", "speech difficulty", "sudden speech difficulty"]),
    ("face-drooping", "تدلي الوجه", "Face drooping", "neurological", ["اعوجاج الوجه"], ["facial droop"]),
    ("sudden-vision-loss", "فقدان مفاجئ للرؤية", "Sudden vision loss", "neurological", ["فقدت النظر فجأه", "فقدت الرؤية فجأة"], ["sudden loss of vision", "sudden blindness"]),
    ("loss-of-consciousness", "فقدان الوعي", "Loss of consciousness", "neurological", ["اغماء", "إغماء", "غيبوبه"], ["unconscious", "fainted", "passed out"]),
    ("severe-bleeding", "نزيف شديد", "Severe bleeding", "cardiovascular", ["نزيف لا يتوقف", "دم لا يتوقف"], ["heavy bleeding", "uncontrollable bleeding"]),
    ("suicidal-thoughts", "أفكار لإيذاء النفس", "Thoughts of self-harm", "mental-health", ["افكار انتحاريه", "أفكار انتحارية", "ابي اموت", "إيذاء النفس"], ["suicidal thoughts", "self harm", "want to die"]),
    # --- Expanded general symptom coverage ---
    ("back-pain", "ألم الظهر", "Back pain", "pain", ["الم الظهر", "ألم الظهر", "ظهري يعورني", "وجع الظهر"], ["back pain", "backache"]),
    ("neck-pain", "ألم الرقبة", "Neck pain", "pain", ["الم الرقبه", "ألم الرقبة", "رقبتي تعورني"], ["neck pain"]),
    ("ear-pain", "ألم الأذن", "Ear pain", "pain", ["الم الاذن", "ألم الأذن", "اذني تعورني", "وجع الاذن"], ["ear pain", "earache"]),
    ("tooth-pain", "ألم الأسنان", "Tooth pain", "pain", ["الم الاسنان", "ألم الأسنان", "سني يعورني", "وجع ضرس", "الم الضرس"], ["tooth pain", "toothache"]),
    ("shoulder-pain", "ألم الكتف", "Shoulder pain", "pain", ["الم الكتف", "ألم الكتف", "كتفي يعورني"], ["shoulder pain"]),
    ("knee-pain", "ألم الركبة", "Knee pain", "pain", ["الم الركبه", "ألم الركبة", "ركبتي تعورني"], ["knee pain"]),
    ("muscle-cramps", "تشنج عضلي", "Muscle cramps", "pain", ["تقلص عضلي", "شد عضلي", "كرامب", "تشنج بالعضل"], ["muscle cramp", "muscle spasm"]),
    ("menstrual-cramps", "ألم الدورة الشهرية", "Menstrual cramps", "pain", ["الم الدوره", "ألم الدورة", "مغص الدوره", "مغص الدورة", "تقلصات الدوره"], ["period pain", "menstrual cramps"]),
    ("eye-pain", "ألم العين", "Eye pain", "pain", ["عيني تعورني", "وجع العين", "الم العين"], ["eye pain"]),
    ("wrist-pain", "ألم الرسغ", "Wrist pain", "pain", ["الم المعصم", "ألم المعصم", "رسغي يعورني"], ["wrist pain"]),
    ("sneezing", "عطس", "Sneezing", "respiratory", ["عطاس", "عطسه", "عطسة متكرره"], ["sneezing"]),
    ("nasal-congestion", "احتقان الأنف", "Nasal congestion", "respiratory", ["انسداد الانف", "انفي مسدود", "انفي مسدوده"], ["stuffy nose", "blocked nose"]),
    ("loss-of-smell", "فقدان حاسة الشم", "Loss of smell", "respiratory", ["مو شام الريحه", "فقدان الشم", "ما اشم"], ["loss of smell", "anosmia"]),
    ("loss-of-taste", "فقدان حاسة التذوق", "Loss of taste", "respiratory", ["مو ذايق الاكل", "فقدان التذوق", "ما اتذوق"], ["loss of taste"]),
    ("hoarseness", "بحة الصوت", "Hoarseness", "respiratory", ["صوتي مبحوح", "بحه بالصوت", "بحة الصوت"], ["hoarse voice", "hoarseness"]),
    ("sinus-pressure", "ضغط الجيوب الأنفية", "Sinus pressure", "respiratory", ["ضغط بالجيوب", "الم الجيوب الانفيه", "ألم الجيوب الأنفية"], ["sinus pressure", "sinus pain"]),
    ("phlegm", "بلغم", "Phlegm", "respiratory", ["نخامه", "بلغم بالصدر", "نخامة"], ["phlegm", "mucus", "sputum"]),
    ("rapid-breathing", "تسارع التنفس", "Rapid breathing", "respiratory", ["تنفس سريع", "انفاسي سريعه", "أنفاسي سريعة"], ["rapid breathing", "fast breathing"]),
    ("constipation", "إمساك", "Constipation", "digestive", ["امساك", "إمساك", "صعوبة التبرز", "صعوبه بالتبرز", "براز قاسي", "براز ناشف"], ["constipation", "hard stools", "dry stools", "lumpy stools"]),
    ("bloating", "انتفاخ البطن", "Bloating", "digestive", ["نفخه", "غازات", "انتفاخ", "بطني منتفخ"], ["bloating", "gas"]),
    ("heartburn", "حرقة المعدة", "Heartburn", "digestive", ["حموضه", "حموضة", "حرقان بالمعده", "حرقان بالمعدة", "ارتجاع"], ["heartburn", "acid reflux"]),
    ("loss-of-appetite", "فقدان الشهية", "Loss of appetite", "digestive", ["مو جاي لي شهيه", "ما اشتهي الاكل", "فقدان الشهيه"], ["loss of appetite", "poor appetite"]),
    ("blood-in-stool", "دم في البراز", "Blood in stool", "digestive", ["دم مع البراز", "براز فيه دم"], ["blood in stool"]),
    ("difficulty-swallowing", "صعوبة البلع", "Difficulty swallowing", "digestive", ["صعوبه بالبلع", "صعوبة البلع", "اتعب وانا ابلع"], ["difficulty swallowing", "dysphagia"]),
    ("excessive-gas", "غازات زائدة", "Excessive gas", "digestive", ["غازات كثيره", "غازات كثيرة", "تكون غازات"], ["excessive gas", "flatulence"]),
    ("abdominal-cramps", "مغص البطن", "Abdominal cramps", "digestive", ["مغص", "مغص شديد بالبطن", "مغص بالبطن"], ["abdominal cramps", "stomach cramps"]),
    ("tremor", "رعشة اليد", "Tremor", "neurological", ["رعشه", "رعشة", "رجفه", "ايدي ترتجف", "يدي ترتجف", "رجفان اليد"], ["tremor", "shaking"]),
    ("confusion", "تشوش الذهن", "Confusion", "neurological", ["تشوش", "ما اقدر افكر صح", "تشتت ذهني"], ["confusion", "disorientation"]),
    ("memory-problems", "مشاكل الذاكرة", "Memory problems", "neurological", ["نسيان", "ضعف الذاكره", "ضعف الذاكرة"], ["memory problems", "forgetfulness"]),
    ("insomnia", "أرق واضطراب النوم", "Insomnia", "neurological", ["ارق", "أرق", "ما اقدر انام", "اضطراب النوم"], ["insomnia", "sleep problems", "trouble sleeping"]),
    ("tinnitus", "طنين الأذن", "Tinnitus", "neurological", ["طنين", "صفير بالاذن", "رنين بالاذن", "طنين بالاذن", "نبض بالاذن", "نبض خلف الاذن", "نبض غريب خلف الاذن", "احس بنبض بالاذن"], ["tinnitus", "ringing in ears", "pulsing in ear"]),
    ("blurred-vision", "تشوش الرؤية", "Blurred vision", "neurological", ["تشوش بالرؤيه", "ما اشوف زين", "رؤيه ضبابيه", "رؤية ضبابية"], ["blurred vision", "blurry vision"]),
    ("balance-problems", "اضطراب التوازن", "Balance problems", "neurological", ["اختلال التوازن", "ما اقدر اتزن"], ["balance problems", "unsteady"]),
    ("burning-sensation", "إحساس بالحرقان", "Burning sensation", "neurological", ["حرقان بالجلد", "احساس حرق", "إحساس بالحرق"], ["burning sensation", "burning feeling"]),
    ("seizure", "نوبة تشنجية", "Seizure", "neurological", ["تشنج", "نوبه صرع", "نوبة صرع", "تشنجات"], ["seizure", "convulsion"]),
    ("skin-rash", "طفح جلدي", "Skin rash", "skin", ["طفح", "حبوب بالجلد", "طفح جلدي"], ["rash", "skin rash"]),
    ("hives", "شرى جلدي", "Hives", "skin", ["شري", "ارتيكاريا", "حساسيه جلديه منتفخه"], ["hives", "urticaria"]),
    ("mouth-ulcers", "تقرحات الفم", "Mouth ulcers", "general", ["قرحة الفم", "حبة داخل الفم", "تقرحات اللسان", "قرح الفم"], ["mouth ulcer", "mouth ulcers", "mouth sore", "canker sore", "tongue ulcer"]),
    ("dry-skin", "جفاف الجلد", "Dry skin", "skin", ["جفاف البشره", "جفاف البشرة", "جلدي جاف"], ["dry skin"]),
    ("easy-bruising", "كدمات سهلة", "Easy bruising", "skin", ["كدمات بدون سبب", "ازرق بجلدي", "أزرق بجلدي"], ["easy bruising", "bruising easily"]),
    ("hair-loss", "تساقط الشعر", "Hair loss", "skin", ["تساقط شعر", "صلع", "شعري يتساقط"], ["hair loss", "hair fall"]),
    ("swelling", "تورم", "Swelling", "skin", ["تورم", "انتفاخ بالجسم"], ["swelling", "edema"]),
    ("pale-skin", "شحوب الجلد", "Pale skin", "skin", ["شحوب", "وجهي شاحب", "اصفرار الوجه"], ["pale skin", "paleness"]),
    ("palpitations", "خفقان القلب", "Palpitations", "cardiovascular", ["خفقان", "قلبي يدق بسرعه", "قلبي يدق بسرعة", "تسارع نبض"], ["heart palpitations", "racing heart"]),
    ("cold-extremities", "برودة الأطراف", "Cold extremities", "cardiovascular", ["ايدي بارده", "يدي باردة", "رجلي بارده", "رجلي باردة"], ["cold hands", "cold feet"]),
    ("leg-swelling", "تورم الساقين", "Leg swelling", "cardiovascular", ["تورم الرجلين", "رجلي متورمه", "رجلي متورمة"], ["leg swelling", "swollen legs"]),
    ("high-blood-pressure-symptoms", "أعراض ارتفاع ضغط الدم", "High blood pressure symptoms", "cardiovascular", ["ضغطي عالي", "ارتفاع الضغط"], ["high blood pressure symptoms"]),
    ("irregular-heartbeat", "عدم انتظام ضربات القلب", "Irregular heartbeat", "cardiovascular", ["نبض غير منتظم", "قلبي يتقطع"], ["irregular heartbeat", "arrhythmia"]),
    ("anxiety", "قلق", "Anxiety", "mental-health", ["توتر", "قلق شديد", "عصبيه زايده", "عصبية زايدة"], ["anxiety", "feeling anxious"]),
    ("low-mood", "مزاج منخفض", "Low mood", "mental-health", ["حزن", "مزاجي تعبان", "اكتئاب", "تعبت من كل شي", "تعبت من كل شيء", "ماني قادر اكمل", "ماني قادر أكمل", "ودي اختفي", "ودي أختفي", "احس اني عبء", "أحس أني عبء على الكل", "الكل احسن بدوني", "الكل أحسن بدوني", "ما فيه امل", "ما في أمل", "يائس", "تعبت من الحياة", "زهقت من الحياة", "كرهت حياتي"], ["low mood", "sadness", "feeling down", "tired of everything", "want to disappear", "feeling hopeless", "hopeless", "i am a burden", "everyone is better off without me"]),
    ("panic-attack", "نوبة هلع", "Panic attack", "mental-health", ["نوبه هلع", "نوبة هلع", "خوف مفاجئ شديد"], ["panic attack"]),
    ("irritability", "تهيج وعصبية", "Irritability", "mental-health", ["عصبيه", "عصبية", "سرعة انفعال"], ["irritability", "easily angered"]),
    ("difficulty-concentrating", "صعوبة التركيز", "Difficulty concentrating", "mental-health", ["صعوبة التركيز", "تشتت الانتباه"], ["difficulty concentrating", "poor focus"]),
    ("weight-loss", "نقص الوزن", "Unexplained weight loss", "general", ["نزل وزني", "خسارة وزن بدون سبب", "خسرت وزن"], ["weight loss", "losing weight"]),
    ("weight-gain", "زيادة الوزن", "Unexplained weight gain", "general", ["زاد وزني", "زيادة وزن"], ["weight gain"]),
    ("night-sweats", "تعرق ليلي", "Night sweats", "general", ["تعرق بالليل", "اتعرق وانا نايم"], ["night sweats"]),
    ("swollen-lymph-nodes", "تورم الغدد اللمفاوية", "Swollen lymph nodes", "general", ["تورم الغدد", "غدد منتفخه", "غدد منتفخة"], ["swollen glands", "swollen lymph nodes"]),
    ("general-weakness", "ضعف عام", "General weakness", "general", ["ضعف عام", "جسمي ضعيف"], ["general weakness", "feeling weak"]),
    ("increased-thirst", "زيادة العطش", "Increased thirst", "general", ["عطش شديد", "اعطش كثير", "أعطش كثير"], ["increased thirst", "excessive thirst"]),
    ("frequent-urination", "كثرة التبول", "Frequent urination", "general", ["تبول متكرر", "اروح الحمام كثير"], ["frequent urination"]),
    ("painful-urination", "ألم عند التبول", "Painful urination", "general", ["حرقان عند التبول", "الم بالتبول", "ألم بالتبول"], ["painful urination", "burning urination"]),
    ("joint-clicking", "طقطقة المفاصل", "Joint clicking (without pain)", "pain", ["تطقطق", "طقطقة الركبه", "طقطقة الركبة", "فرقعة المفصل", "صوت طقطقة بالمفصل", "ركبتي تطقطق"], ["joint clicking", "joint popping", "cracking joint"]),
]

DISEASES = [
    {"slug":"migraine","name_ar":"الصداع النصفي (الشقيقة)","name_en":"Migraine","category":"neurological","severity":"moderate",
     "description_ar":"اضطراب صداع أولي قد يسبب نوبات من صداع نابض، غالبًا في جانب واحد، وقد يصاحبه غثيان وحساسية للضوء أو الصوت.",
     "description_en":"A primary headache disorder that can cause attacks of throbbing head pain, often on one side, with nausea or sensitivity to light and sound.",
     "risk_ar":"التاريخ العائلي، اضطراب النوم، التوتر وبعض المحفزات الشخصية.","risk_en":"Family history, sleep disruption, stress, and individual triggers.",
     "causes_ar":"السبب الدقيق غير معروف؛ قد تشارك تغيرات عصبية ووعائية وتوجد محفزات تختلف بين الأشخاص.","causes_en":"The exact cause is unknown; neurological and vascular changes may contribute, with triggers varying by person.",
     "red_ar":"صداع مفاجئ شديد جدًا، ضعف في جانب واحد، صعوبة كلام، فقدان رؤية أو تشوش.","red_en":"A sudden extremely severe headache, one-sided weakness, speech difficulty, vision loss, or confusion.",
     "next_ar":"راقب نمط الصداع ومحفزاته واطلب تقييمًا طبيًا إذا كان جديدًا أو متكررًا أو يزداد سوءًا.","next_en":"Track the headache pattern and triggers, and seek medical review if it is new, recurrent, or worsening.",
     "symptoms":{"headache":1.0,"nausea":0.75,"vomiting":0.45,"light-sensitivity":0.9,"sound-sensitivity":0.85,"dizziness":0.35,"blurred-vision":0.3},
     "sources":[("saudi-moh","الصداع النصفي — وزارة الصحة","Migraine — Saudi MOH","https://www.moh.gov.sa/healthawareness/educationalcontent/diseases/nervous-system/pages/migraine.aspx"),("who","اضطرابات الصداع — منظمة الصحة العالمية","Headache disorders — WHO","https://www.who.int/news-room/fact-sheets/detail/headache-disorders"),("nhs","الصداع النصفي — NHS","Migraine — NHS","https://www.nhs.uk/conditions/migraine/"),("mayo-clinic","الصداع النصفي — مايو كلينك","Migraine — Mayo Clinic","https://www.mayoclinic.org/diseases-conditions/migraine-headache/symptoms-causes/syc-20360201")]},
    {"slug":"influenza","name_ar":"الإنفلونزا","name_en":"Influenza (flu)","category":"respiratory","severity":"moderate",
     "description_ar":"عدوى تنفسية فيروسية تبدأ غالبًا بصورة مفاجئة وقد تسبب الحمى والسعال وآلام الجسم والتعب.","description_en":"A viral respiratory infection that often starts suddenly and may cause fever, cough, body aches, and fatigue.",
     "risk_ar":"العمر الصغير أو الكبير، الحمل وبعض الأمراض المزمنة أو ضعف المناعة.","risk_en":"Young or older age, pregnancy, chronic conditions, or weakened immunity.",
     "causes_ar":"فيروسات الإنفلونزا التي تنتقل أساسًا عبر الرذاذ والمخالطة.","causes_en":"Influenza viruses spread mainly through respiratory droplets and close contact.",
     "red_ar":"صعوبة تنفس، ألم صدر، تشوش، جفاف شديد أو تحسن ثم تدهور مفاجئ.","red_en":"Breathing difficulty, chest pain, confusion, severe dehydration, or improvement followed by sudden worsening.",
     "next_ar":"راقب التنفس والترطيب واطلب تقييمًا طبيًا مبكرًا عند وجود عوامل خطورة أو تدهور.","next_en":"Monitor breathing and hydration and seek early medical review if risk factors or worsening are present.",
     "symptoms":{"fever":0.9,"cough":0.8,"sore-throat":0.45,"runny-nose":0.35,"fatigue":0.75,"body-aches":0.85,"headache":0.6,"chills":0.7,"loss-of-appetite":0.4,"night-sweats":0.3},
     "sources":[("cdc","علامات وأعراض الإنفلونزا — CDC","Flu signs and symptoms — CDC","https://www.cdc.gov/flu/signs-symptoms/index.html")]},
    {"slug":"common-cold","name_ar":"نزلة البرد الشائعة","name_en":"Common cold","category":"respiratory","severity":"mild",
     "description_ar":"عدوى فيروسية شائعة في الجهاز التنفسي العلوي تبدأ أعراضها عادةً تدريجيًا.","description_en":"A common viral upper-respiratory infection whose symptoms usually begin gradually.",
     "risk_ar":"المخالطة القريبة وقلة غسل اليدين وبعض حالات ضعف المناعة.","risk_en":"Close contact, limited hand hygiene, and some states of weakened immunity.",
     "causes_ar":"فيروسات تنفسية متعددة تنتقل بالمخالطة والرذاذ والأسطح الملوثة.","causes_en":"Multiple respiratory viruses spread by contact, droplets, and contaminated surfaces.",
     "red_ar":"ضيق تنفس، ألم صدر، حرارة مرتفعة مستمرة أو تدهور بعد عدة أيام.","red_en":"Shortness of breath, chest pain, persistent high fever, or worsening after several days.",
     "next_ar":"راقب الأعراض واطلب مراجعة طبية إذا لم تتحسن خلال المدة المتوقعة أو ظهرت علامة خطر.","next_en":"Monitor symptoms and seek review if they do not improve as expected or a red flag appears.",
     "symptoms":{"runny-nose":0.95,"sore-throat":0.75,"cough":0.65,"fatigue":0.35,"fever":0.25,"body-aches":0.2,"sneezing":0.7,"nasal-congestion":0.6,"loss-of-smell":0.3},
     "sources":[("nhs","نزلة البرد الشائعة — NHS","Common cold — NHS","https://www.nhs.uk/conditions/common-cold/")]},
    {"slug":"viral-gastroenteritis","name_ar":"التهاب المعدة والأمعاء الفيروسي","name_en":"Viral gastroenteritis","category":"digestive","severity":"moderate",
     "description_ar":"التهاب في المعدة أو الأمعاء يسبب القيء أو الإسهال وقد يؤدي إلى الجفاف.","description_en":"Inflammation of the stomach or intestines causing vomiting or diarrhea and sometimes dehydration.",
     "risk_ar":"العمر الصغير أو الكبير، ضعف المناعة والمخالطة أو الطعام الملوث.","risk_en":"Young or older age, weakened immunity, close contact, or contaminated food.",
     "causes_ar":"فيروسات معوية شديدة العدوى مثل نوروفيروس.","causes_en":"Highly contagious enteric viruses such as norovirus.",
     "red_ar":"جفاف شديد، قلة بول، خمول غير معتاد، دم في القيء أو البراز أو ألم بطن شديد.","red_en":"Severe dehydration, reduced urination, unusual drowsiness, blood in vomit or stool, or severe abdominal pain.",
     "next_ar":"عوّض السوائل تدريجيًا واطلب تقييمًا طبيًا عند علامات الجفاف أو استمرار الأعراض أو تدهورها.","next_en":"Replace fluids gradually and seek medical review for dehydration, persistent symptoms, or worsening.",
     "symptoms":{"diarrhea":0.95,"vomiting":0.85,"nausea":0.7,"abdominal-pain":0.7,"fever":0.3,"headache":0.2,"body-aches":0.25,"dehydration":0.55,"abdominal-cramps":0.6,"loss-of-appetite":0.4},
     "sources":[("cdc","حول نوروفيروس — CDC","About norovirus — CDC","https://www.cdc.gov/norovirus/about/index.html")]},
    {"slug":"asthma","name_ar":"الربو","name_en":"Asthma","category":"respiratory","severity":"moderate",
     "description_ar":"مرض رئوي مزمن يسبب التهابًا وضيقًا في الشعب الهوائية، وقد تتفاوت أعراضه مع الوقت.","description_en":"A chronic lung disease involving inflamed and narrowed airways, with symptoms that can vary over time.",
     "risk_ar":"التاريخ العائلي، الحساسية، التعرض للدخان أو الملوثات وبعض العدوى التنفسية.","risk_en":"Family history, allergies, smoke or pollution exposure, and some respiratory infections.",
     "causes_ar":"تشارك عوامل وراثية وبيئية، وقد تحفز الأعراض مهيجات مختلفة.","causes_en":"Genetic and environmental factors contribute, with symptoms triggered by different irritants.",
     "red_ar":"صعوبة تنفس شديدة، عدم القدرة على الكلام بصورة طبيعية أو ازرقاق الشفاه.","red_en":"Severe breathing difficulty, inability to speak normally, or blue lips.",
     "next_ar":"تحدث مع مختص صحي لتقييم الأعراض ووضع خطة واضحة، واطلب رعاية عاجلة عند صعوبة التنفس الشديدة.","next_en":"Speak with a health professional for assessment and an action plan; seek urgent care for severe breathing difficulty.",
     "symptoms":{"wheezing":1.0,"shortness-of-breath":0.95,"chest-tightness":0.85,"cough":0.7,"fatigue":0.2,"rapid-breathing":0.4},
     "sources":[("who","الربو — منظمة الصحة العالمية","Asthma — WHO","https://www.who.int/news-room/fact-sheets/detail/asthma")]},
    {"slug":"peripheral-neuropathy","name_ar":"اعتلال الأعصاب الطرفية","name_en":"Peripheral neuropathy","category":"neurological","severity":"moderate",
     "description_ar":"مصطلح يصف تضرر الأعصاب الطرفية، وقد يسبب تنميلًا أو وخزًا أو تغيرًا في الإحساس، غالبًا في اليدين أو القدمين.","description_en":"Damage to peripheral nerves that may cause numbness, tingling, or altered sensation, often in the hands or feet.",
     "risk_ar":"توجد أسباب متعددة، لذلك يحتاج التنميل المستمر أو المتكرر إلى تقييم صحي.","risk_en":"There are multiple possible causes, so persistent or recurrent numbness needs clinical assessment.",
     "causes_ar":"قد يرتبط بحالات صحية أو إصابات أو أدوية، ولا يمكن تحديد السبب من عرض واحد.","causes_en":"It may relate to health conditions, injuries, or medicines; one symptom alone cannot identify the cause.",
     "red_ar":"تنميل مفاجئ في جهة واحدة، ضعف، تدلي الوجه أو صعوبة الكلام.","red_en":"Sudden one-sided numbness, weakness, facial droop, or speech difficulty.",
     "next_ar":"اطلب تقييمًا طبيًا إذا استمر التنميل أو تكرر، واطلب الطوارئ عند ظهوره فجأة في جهة واحدة.","next_en":"Seek medical review if numbness persists or recurs; seek emergency help for sudden one-sided symptoms.",
     "symptoms":{"numbness":1.0,"hand-numbness":0.85,"foot-numbness":0.9,"widespread-numbness":0.55,"burning-sensation":0.6},
     "sources":[("nhs","اعتلال الأعصاب الطرفية — NHS","Peripheral neuropathy — NHS","https://www.nhs.uk/conditions/peripheral-neuropathy/")]},
    {"slug":"carpal-tunnel-syndrome","name_ar":"متلازمة النفق الرسغي","name_en":"Carpal tunnel syndrome","category":"neurological","severity":"mild",
     "description_ar":"ضغط على عصب في الرسغ قد يسبب تنميلًا أو وخزًا وألمًا في اليد والأصابع.","description_en":"Pressure on a nerve at the wrist that can cause numbness, tingling, and pain in the hand and fingers.",
     "risk_ar":"قد تزيد بعض الحالات أو الأعمال المتكررة احتمال الأعراض، لكن يلزم التقييم لتأكيد السبب.","risk_en":"Some conditions or repetitive activities may increase symptoms, but assessment is needed to confirm the cause.",
     "causes_ar":"ضغط العصب المتوسط أثناء مروره عبر الرسغ.","causes_en":"Compression of the median nerve as it passes through the wrist.",
     "red_ar":"ضعف متزايد أو فقدان إحساس مستمر أو أعراض مفاجئة في جهة كاملة.","red_en":"Increasing weakness, persistent sensory loss, or sudden symptoms affecting a whole side.",
     "next_ar":"راجع مختصًا إذا استمرت الأعراض أو أثرت في استخدام اليد أو النوم.","next_en":"Seek clinical review if symptoms persist or affect hand use or sleep.",
     "symptoms":{"hand-numbness":1.0,"numbness":0.55,"wrist-pain":0.7},
     "sources":[("nhs","متلازمة النفق الرسغي — NHS","Carpal tunnel syndrome — NHS","https://www.nhs.uk/conditions/carpal-tunnel-syndrome/")]},
    {"slug":"sciatica","name_ar":"عرق النسا","name_en":"Sciatica","category":"neurological","severity":"moderate",
     "description_ar":"أعراض تنتج عن تهيج أو ضغط العصب الوركي، وقد تشمل ألمًا يمتد في الساق مع تنميل أو وخز.","description_en":"Symptoms from irritation or compression of the sciatic nerve, including pain down a leg with numbness or tingling.",
     "risk_ar":"قد ترتبط الأعراض بمشكلات أسفل الظهر، ويحتاج التشخيص إلى تقييم سريري.","risk_en":"Symptoms may relate to lower-back problems and require clinical assessment.",
     "causes_ar":"تهيج أو ضغط العصب الوركي.","causes_en":"Irritation or compression of the sciatic nerve.",
     "red_ar":"خدر حول منطقة العجان، فقد التحكم بالبول أو البراز، أو ضعف شديد متزايد.","red_en":"Numbness around the saddle area, loss of bladder or bowel control, or worsening severe weakness.",
     "next_ar":"راجع مختصًا عند استمرار الألم أو التنميل، واطلب رعاية عاجلة عند علامات الخطر.","next_en":"Seek clinical review for persistent pain or numbness and urgent care for red flags.",
     "symptoms":{"leg-pain":1.0,"foot-numbness":0.65,"numbness":0.4,"back-pain":0.85},
     "sources":[("nhs","عرق النسا — NHS","Sciatica — NHS","https://www.nhs.uk/conditions/sciatica/")]},
    {"slug":"acute-sinusitis","name_ar":"التهاب الجيوب الأنفية","name_en":"Sinusitis","category":"respiratory","severity":"mild",
     "description_ar":"التهاب في الجيوب الأنفية قد يسبب انسداد الأنف وألمًا أو ضغطًا في الوجه وصداعًا.","description_en":"Inflammation of the sinuses that may cause nasal blockage, facial pressure, and headache.",
     "risk_ar":"قد يحدث بعد الزكام، وتحتاج الأعراض الشديدة أو المطولة إلى مراجعة.","risk_en":"It can follow a cold; severe or prolonged symptoms need review.",
     "causes_ar":"غالبًا عدوى فيروسية، وقد توجد أسباب أخرى.","causes_en":"Often a viral infection, though other causes exist.",
     "red_ar":"تورم حول العين أو تغير الرؤية أو صداع شديد جدًا.","red_en":"Swelling around the eye, vision changes, or an extremely severe headache.",
     "next_ar":"راقب الأعراض وراجع مختصًا إذا كانت شديدة أو لم تتحسن.","next_en":"Monitor symptoms and seek review if severe or not improving.",
     "symptoms":{"runny-nose":0.9,"headache":0.7,"fever":0.35,"cough":0.3,"sinus-pressure":0.85,"nasal-congestion":0.6},
     "sources":[("nhs","التهاب الجيوب الأنفية — NHS","Sinusitis — NHS","https://www.nhs.uk/conditions/sinusitis-sinus-infection/")]},
    {"slug":"acute-bronchitis","name_ar":"التهاب الشعب الهوائية","name_en":"Bronchitis","category":"respiratory","severity":"moderate",
     "description_ar":"التهاب في الممرات الهوائية يسبب السعال وقد يصاحبه تعب أو صفير أو ضيق تنفس.","description_en":"Inflammation of the airways causing cough, sometimes with fatigue, wheezing, or breathlessness.",
     "risk_ar":"التدخين وبعض الحالات الرئوية قد تزيد المخاطر.","risk_en":"Smoking and some lung conditions can increase risk.",
     "causes_ar":"غالبًا عدوى، وقد تؤثر المهيجات التنفسية أيضًا.","causes_en":"Often infection-related; respiratory irritants can also contribute.",
     "red_ar":"صعوبة تنفس شديدة، ازرقاق، ألم صدر أو سعال مصحوب بدم.","red_en":"Severe breathing difficulty, blue lips, chest pain, or coughing blood.",
     "next_ar":"راجع مختصًا إذا كان السعال شديدًا أو مستمرًا أو صاحبه ضيق تنفس.","next_en":"Seek review if cough is severe, persistent, or accompanied by breathlessness.",
     "symptoms":{"cough":1.0,"wheezing":0.55,"fatigue":0.45,"fever":0.35,"shortness-of-breath":0.4,"phlegm":0.6},
     "sources":[("nhs","التهاب الشعب الهوائية — NHS","Bronchitis — NHS","https://www.nhs.uk/conditions/bronchitis/")]},
    {"slug":"food-poisoning","name_ar":"التسمم الغذائي","name_en":"Food poisoning","category":"digestive","severity":"moderate",
     "description_ar":"مرض ينتج عن تناول طعام ملوث، وقد يسبب الغثيان والقيء والإسهال وألم البطن.","description_en":"Illness from contaminated food that may cause nausea, vomiting, diarrhoea, and abdominal pain.",
     "risk_ar":"يزداد خطر المضاعفات لدى بعض الفئات ومع الجفاف.","risk_en":"Complication risk is higher in some groups and with dehydration.",
     "causes_ar":"جراثيم أو سموم موجودة في طعام ملوث.","causes_en":"Germs or toxins in contaminated food.",
     "red_ar":"جفاف شديد، دم في القيء أو البراز، ألم شديد أو تدهور عام.","red_en":"Severe dehydration, blood in vomit or stool, severe pain, or marked deterioration.",
     "next_ar":"اهتم بالسوائل واطلب تقييمًا عند علامات الجفاف أو استمرار الأعراض أو شدتها.","next_en":"Maintain fluids and seek review for dehydration, persistent symptoms, or severe illness.",
     "symptoms":{"nausea":0.8,"vomiting":0.9,"diarrhea":0.95,"abdominal-pain":0.8,"fever":0.35,"dehydration":0.5,"abdominal-cramps":0.7},
     "sources":[("nhs","التسمم الغذائي — NHS","Food poisoning — NHS","https://www.nhs.uk/conditions/food-poisoning/")]},
    {"slug":"gerd","name_ar":"ارتجاع المريء (حرقة المعدة المزمنة)","name_en":"Gastroesophageal reflux disease (GERD)","category":"digestive","severity":"mild",
     "description_ar":"عودة حمض المعدة إلى المريء بشكل متكرر، وأبرز أعراضه حرقة المعدة، وقد يرافقه صعوبة بلع أو بحة صوت.","description_en":"Frequent backflow of stomach acid into the esophagus; heartburn is the cardinal symptom and it may include swallowing trouble or hoarseness.",
     "risk_ar":"زيادة الوزن، التدخين، وجبات كبيرة أو النوم بعد الأكل مباشرة.","risk_en":"Excess weight, smoking, large meals, or lying down soon after eating.",
     "causes_ar":"ضعف في العضلة العاصرة السفلية للمريء يسمح بارتداد الحمض.","causes_en":"A weakened lower esophageal sphincter allows stomach acid to flow back up.",
     "red_ar":"صعوبة بلع شديدة، فقدان وزن غير مبرر، قيء دموي أو براز أسود.","red_en":"Severe difficulty swallowing, unexplained weight loss, vomiting blood, or black stools.",
     "next_ar":"جرّب تعديل الوجبات ورفع الرأس أثناء النوم، واطلب تقييمًا إذا تكررت الأعراض أكثر من مرتين أسبوعيًا.","next_en":"Try meal adjustments and elevating the head while sleeping; seek review if symptoms occur more than twice a week.",
     "symptoms":{"heartburn":1.0,"difficulty-swallowing":0.45,"hoarseness":0.3,"nausea":0.3,"bloating":0.25},
     "sources":[("mayo-clinic","الحرقة وارتجاع المريء — مايو كلينك","Heartburn and GERD — Mayo Clinic","https://www.mayoclinic.org/diseases-conditions/heartburn/symptoms-causes/syc-20373223")]},
    {"slug":"laryngitis","name_ar":"التهاب الحنجرة","name_en":"Laryngitis","category":"respiratory","severity":"mild",
     "description_ar":"التهاب في الحنجرة غالبًا بسبب عدوى فيروسية أو إجهاد الصوت، يسبب بحة أو فقدانًا مؤقتًا للصوت.","description_en":"Inflammation of the voice box, usually from a viral infection or voice overuse, causing hoarseness or temporary voice loss.",
     "risk_ar":"عدوى تنفسية علوية حديثة، إجهاد الصوت، أو التدخين.","risk_en":"A recent upper-respiratory infection, voice overuse, or smoking.",
     "causes_ar":"عدوى فيروسية غالبًا، وأحيانًا إجهاد الصوت أو ارتجاع الحمض.","causes_en":"Usually viral infection; sometimes voice strain or acid reflux.",
     "red_ar":"صعوبة تنفس، صعوبة بلع اللعاب، أو استمرار البحة أكثر من أسبوعين.","red_en":"Breathing difficulty, difficulty swallowing saliva, or hoarseness lasting more than two weeks.",
     "next_ar":"أرح صوتك ورطّب الجو، واطلب تقييمًا إذا استمرت البحة أكثر من أسبوعين.","next_en":"Rest your voice and use humidified air; seek review if hoarseness lasts more than two weeks.",
     "symptoms":{"hoarseness":1.0,"sore-throat":0.55,"cough":0.4,"fever":0.2},
     "sources":[("mayo-clinic","التهاب الحنجرة — مايو كلينك","Laryngitis — Mayo Clinic","https://www.mayoclinic.org/diseases-conditions/laryngitis/symptoms-causes/syc-20374262")]},
    {"slug":"ear-infection","name_ar":"التهاب الأذن","name_en":"Ear infection (otitis)","category":"general","severity":"mild",
     "description_ar":"التهاب أو تجمّع سوائل في الأذن الوسطى أو الخارجية، يسبب ألمًا وأحيانًا طنينًا أو حمى خفيفة.","description_en":"Inflammation or fluid buildup in the middle or outer ear, causing pain and sometimes tinnitus or mild fever.",
     "risk_ar":"عدوى تنفسية حديثة، السباحة، أو التعرض للماء داخل الأذن.","risk_en":"A recent respiratory infection, swimming, or water trapped in the ear.",
     "causes_ar":"عدوى فيروسية أو بكتيرية أو تهيّج الأذن الخارجية بالماء أو الأجسام الغريبة.","causes_en":"Viral or bacterial infection, or outer-ear irritation from water or foreign objects.",
     "red_ar":"تورم أو احمرار خلف الأذن، حمى شديدة، أو خروج إفرازات أو دم.","red_en":"Swelling or redness behind the ear, high fever, or discharge/blood from the ear.",
     "next_ar":"راقب الألم والحمى، واطلب تقييمًا إذا استمر الألم أكثر من يومين أو ظهرت إفرازات.","next_en":"Monitor pain and fever; seek review if pain lasts more than two days or discharge appears.",
     "symptoms":{"ear-pain":1.0,"tinnitus":0.35,"fever":0.3,"balance-problems":0.2},
     "sources":[("nhs","التهابات الأذن — NHS","Ear infections — NHS","https://www.nhs.uk/conditions/ear-infections/")]},
    {"slug":"contact-dermatitis","name_ar":"التهاب الجلد التماسي (حساسية جلدية)","name_en":"Contact dermatitis","category":"skin","severity":"mild",
     "description_ar":"تهيّج جلدي ناتج عن ملامسة مادة مهيّجة أو مسببة للحساسية، يظهر كطفح جلدي مع حكة وأحيانًا جفاف أو تورم موضعي.","description_en":"Skin irritation from contact with an irritant or allergen, appearing as an itchy rash with sometimes dryness or localized swelling.",
     "risk_ar":"التعرض لمواد تنظيف، معادن، نباتات، أو مستحضرات جديدة.","risk_en":"Exposure to cleaning products, metals, plants, or new cosmetic products.",
     "causes_ar":"تلامس مباشر مع مادة مهيّجة أو مادة تسبب استجابة تحسسية.","causes_en":"Direct contact with an irritant or a substance triggering an allergic response.",
     "red_ar":"تورم الوجه أو الشفتين أو الحلق، صعوبة تنفس، أو انتشار الطفح بسرعة على كامل الجسم.","red_en":"Swelling of the face, lips, or throat, breathing difficulty, or a rash spreading rapidly over the whole body.",
     "next_ar":"ابتعد عن المادة المسببة ونظّف المنطقة، واطلب تقييمًا إذا ساء الطفح أو انتشر.","next_en":"Avoid the trigger substance and clean the area; seek review if the rash worsens or spreads.",
     "symptoms":{"skin-rash":0.85,"dry-skin":0.3,"swelling":0.35},
     "sources":[("mayo-clinic","التهاب الجلد التماسي — مايو كلينك","Contact dermatitis — Mayo Clinic","https://www.mayoclinic.org/diseases-conditions/contact-dermatitis/symptoms-causes/syc-20352742")]},
    {"slug":"urticaria","name_ar":"الشرى الجلدي (الأرتيكاريا)","name_en":"Hives (urticaria)","category":"skin","severity":"mild",
     "description_ar":"بقع أو انتفاخات جلدية مرتفعة تظهر فجأة وتكون غالبًا شديدة الحكة، وقد تتغير أماكنها أو تندمج معًا.","description_en":"Raised skin welts or bumps that appear suddenly, are often very itchy, and may change location or join together.",
     "risk_ar":"حساسية تجاه طعام أو دواء أو لدغة حشرة، أو محفزات مثل الحرارة أو البرد أو التوتر.","risk_en":"Allergy to a food, medication, or insect sting, or triggers such as heat, cold, or stress.",
     "causes_ar":"استجابة تحسسية أو مناعية تُطلق مواد تسبب تورم سطحي في الجلد؛ وأحيانًا دون سبب واضح.","causes_en":"An allergic or immune response that releases substances causing superficial skin swelling; sometimes with no clear cause.",
     "red_ar":"تورم الوجه أو الشفتين أو الحلق أو اللسان، صعوبة تنفس أو بلع، أو دوخة — قد تكون علامات حساسية شديدة (تأق).","red_en":"Swelling of the face, lips, throat, or tongue, difficulty breathing or swallowing, or dizziness — these can be signs of a severe allergic reaction (anaphylaxis).",
     "next_ar":"ابتعد عن المحفز المحتمل، ومضادات الهيستامين قد تخفف الأعراض؛ اطلب تقييمًا إذا استمر الشرى أكثر من أيام قليلة أو تكرر، واطلب الطوارئ فورًا مع أي علامة خطر.","next_en":"Avoid the likely trigger; antihistamines may ease symptoms. Seek review if hives last more than a few days or recur, and seek emergency care immediately with any red-flag sign.",
     "symptoms":{"hives":1.0,"skin-rash":0.4,"swelling":0.35},
     "sources":[("mayo-clinic","الشرى والوذمة الوعائية — مايو كلينك","Hives and angioedema — Mayo Clinic","https://www.mayoclinic.org/diseases-conditions/hives-and-angioedema/symptoms-causes/syc-20354908")]},
    {"slug":"urinary-tract-infection","name_ar":"التهاب المسالك البولية","name_en":"Urinary tract infection (UTI)","category":"general","severity":"mild",
     "description_ar":"عدوى بكتيرية في المسالك البولية، تسبب حرقانًا عند التبول وكثرة التبول وأحيانًا ألمًا أسفل البطن.","description_en":"A bacterial infection of the urinary tract causing painful, frequent urination and sometimes lower abdominal pain.",
     "risk_ar":"النساء أكثر عرضة، وكذلك قلة شرب الماء أو حصى الكلى السابقة.","risk_en":"More common in women; also low fluid intake or a history of kidney stones.",
     "causes_ar":"دخول بكتيريا إلى المسالك البولية، غالبًا من الجهاز الهضمي.","causes_en":"Bacteria entering the urinary tract, often from the digestive tract.",
     "red_ar":"حمى مع قشعريرة، ألم الخاصرة، أو دم واضح في البول.","red_en":"Fever with chills, flank pain, or visible blood in the urine.",
     "next_ar":"اشرب سوائل كافية واطلب تقييمًا طبيًا للعلاج المناسب، خصوصًا مع الحمى أو ألم الخاصرة.","next_en":"Drink adequate fluids and seek medical review for appropriate treatment, especially with fever or flank pain.",
     "symptoms":{"painful-urination":1.0,"frequent-urination":0.75,"abdominal-pain":0.3,"fever":0.25},
     "sources":[("nhs","التهابات المسالك البولية — NHS","Urinary tract infections (UTIs) — NHS","https://www.nhs.uk/conditions/urinary-tract-infections-utis/")]},
    {"slug":"heart-palpitations","name_ar":"خفقان القلب — أسباب محتملة متعددة","name_en":"Heart palpitations — multiple possible causes","category":"cardiovascular","severity":"mild",
     "description_ar":"إحساس بتسارع أو خفقان أو عدم انتظام نبض القلب. غالبًا ما يكون مرتبطًا بالتوتر أو القلق أو الكافيين وغير خطير، لكنه قد يرتبط أحيانًا باضطراب في نظم القلب، خصوصًا مع ألم الصدر أو الإغماء أو ضيق التنفس.","description_en":"A sensation of a racing, pounding, or irregular heartbeat. It is often linked to stress, anxiety, or caffeine and is not dangerous, but it can sometimes be related to a heart rhythm disorder, especially alongside chest pain, fainting, or shortness of breath.",
     "risk_ar":"التوتر والقلق، الكافيين، قلة النوم، أو وجود مشكلة سابقة في نظم القلب.","risk_en":"Stress and anxiety, caffeine, lack of sleep, or a pre-existing heart rhythm condition.",
     "causes_ar":"استجابة الجسم للتوتر أو المنبهات في أغلب الحالات؛ وأحيانًا اضطراب فعلي في نظم القلب يحتاج تقييمًا.","causes_en":"Usually the body's response to stress or stimulants; sometimes an actual heart rhythm disorder that needs evaluation.",
     "red_ar":"خفقان مصحوب بألم صدر، إغماء، ضيق تنفس شديد، أو خفقان لا يهدأ ويستمر لدقائق طويلة.","red_en":"Palpitations with chest pain, fainting, severe breathlessness, or a racing heart that does not settle for many minutes.",
     "next_ar":"قلّل الكافيين والتوتر وراقب النمط، واطلب تقييمًا قلبيًا إذا تكرر الخفقان أو صاحبته أعراض أخرى — ولا يُفترض اعتباره حميدًا دون تقييم إذا تكرر.","next_en":"Reduce caffeine and stress and monitor the pattern; seek a cardiac review if palpitations recur or come with other symptoms — it should not be assumed benign without evaluation if it recurs.",
     "symptoms":{"palpitations":1.0,"anxiety":0.4,"irregular-heartbeat":0.45},
     "sources":[("mayo-clinic","خفقان القلب — مايو كلينك","Heart palpitations — Mayo Clinic","https://www.mayoclinic.org/diseases-conditions/heart-palpitations/symptoms-causes/syc-20373196")]},
    {"slug":"osteoarthritis","name_ar":"خشونة المفاصل (الفصال العظمي)","name_en":"Osteoarthritis","category":"pain","severity":"mild",
     "description_ar":"تآكل تدريجي في غضروف المفصل يسبب ألمًا وتيبسًا، وغالبًا يزداد مع الاستخدام ويتحسن بالراحة.","description_en":"Gradual wear of joint cartilage causing pain and stiffness that often worsens with use and eases with rest.",
     "risk_ar":"التقدم بالعمر، زيادة الوزن، أو إصابات مفصلية سابقة.","risk_en":"Older age, excess weight, or previous joint injury.",
     "causes_ar":"تآكل الغضروف الواقي للمفصل مع مرور الوقت.","causes_en":"Wear of the protective cartilage in the joint over time.",
     "red_ar":"تورم شديد ومفاجئ، احمرار وحرارة موضعية، أو حمى مصاحبة لألم المفصل.","red_en":"Sudden severe swelling, redness and warmth over the joint, or fever accompanying joint pain.",
     "next_ar":"مارس نشاطًا خفيفًا منتظمًا وحافظ على وزن صحي، واطلب تقييمًا إذا أثّر الألم على الحركة اليومية.","next_en":"Stay lightly active regularly and maintain a healthy weight; seek review if pain affects daily movement.",
     "symptoms":{"joint-pain":0.9,"knee-pain":0.55,"shoulder-pain":0.3,"joint-clicking":0.4},
     "sources":[("mayo-clinic","الفصال العظمي — مايو كلينك","Osteoarthritis — Mayo Clinic","https://www.mayoclinic.org/diseases-conditions/osteoarthritis/symptoms-causes/syc-20351925")]},
    {"slug":"insomnia-disorder","name_ar":"الأرق واضطراب النوم","name_en":"Insomnia and sleep disturbance","category":"neurological","severity":"mild",
     "description_ar":"صعوبة في بدء النوم أو الاستمرار فيه تؤثر على الأداء خلال النهار. تُسمى قصيرة المدى إذا استمرت أقل من 3 أشهر، وطويلة المدى إذا استمرت 3 أشهر أو أكثر.","description_en":"Difficulty falling or staying asleep that affects daytime functioning. It is called short-term if it lasts less than 3 months, and long-term if it lasts 3 months or more.",
     "risk_ar":"التوتر والقلق، جداول نوم غير منتظمة، أو الكافيين المتأخر.","risk_en":"Stress and anxiety, irregular sleep schedules, or late caffeine intake.",
     "causes_ar":"غالبًا مرتبط بالتوتر أو عادات النوم؛ وأحيانًا حالة نفسية أو طبية أخرى.","causes_en":"Often linked to stress or sleep habits; sometimes another underlying medical or mental-health condition.",
     "red_ar":"أرق مصحوب بأفكار إيذاء النفس أو تدهور واضح في الأداء اليومي.","red_en":"Insomnia accompanied by thoughts of self-harm or marked decline in daily functioning.",
     "next_ar":"حافظ على موعد نوم ثابت وقلّل الكافيين مساءً، واطلب تقييمًا طبيًا إذا استمر الأرق 3 أشهر أو أكثر أو أثّر بشدة على حياتك اليومية.","next_en":"Keep a consistent sleep schedule and reduce evening caffeine; seek medical review if insomnia lasts 3 months or more, or is severely affecting daily life.",
     "symptoms":{"insomnia":1.0,"general-weakness":0.4,"difficulty-concentrating":0.4,"irritability":0.3,"anxiety":0.25},
     "sources":[("nhs","الأرق — NHS","Insomnia — NHS","https://www.nhs.uk/conditions/insomnia/")]},
]

# Common, source-grounded possibilities added for symptoms that previously had
# no disease relationship. They deliberately use cautious wording: matching a
# pattern is not a diagnosis, and warning signs are handled independently by
# RED_RULES below.
def _common_condition(slug, ar, en, category, symptoms, url, next_ar, next_en, severity="mild"):
    # Keep the source identity aligned with the actual reference URL.  This
    # matters because the knowledge-layer validator checks official domains.
    source_key = "cdc" if "cdc.gov" in str(url).lower() else "nhs"
    source_label = "CDC" if source_key == "cdc" else "NHS"
    return {
        "slug": slug, "name_ar": ar, "name_en": en, "category": category, "severity": severity,
        "description_ar": f"حالة شائعة قد تتوافق بعض أعراضها مع نمط {ar}، لكن يلزم تقييم مناسب لتأكيد السبب.",
        "description_en": f"A common condition whose symptom pattern may fit {en}; appropriate assessment is needed to confirm the cause.",
        "risk_ar": "تختلف عوامل الخطورة بحسب العمر والتاريخ الصحي والأدوية ونمط الحياة.",
        "risk_en": "Risk factors vary with age, health history, medicines, and lifestyle.",
        "causes_ar": "توجد أسباب متعددة محتملة، ولا يمكن تحديد السبب من عرض واحد فقط.",
        "causes_en": "Several causes are possible, and one symptom alone cannot establish the cause.",
        "red_ar": "اطلب رعاية عاجلة عند ظهور عرض شديد أو مفاجئ، إغماء، ضيق تنفس، نزيف واضح أو تدهور سريع.",
        "red_en": "Seek urgent care for severe or sudden symptoms, fainting, breathing difficulty, obvious bleeding, or rapid deterioration.",
        "next_ar": next_ar, "next_en": next_en, "symptoms": symptoms,
        "sources": [(source_key, f"{ar} — {source_label}", f"{en} — {source_label}", url)],
    }

DISEASES.extend([
    _common_condition("underactive-thyroid", "قصور الغدة الدرقية", "Underactive thyroid", "general",
        {"hair-loss":.65,"weight-gain":.8,"cold-extremities":.55,"constipation":.6,"memory-problems":.45,"low-mood":.4,"fatigue":.75,"dry-skin":.5,"general-weakness":.4},
        "https://www.nhs.uk/conditions/underactive-thyroid-hypothyroidism/", "احجز موعدًا طبيًا إذا استمرت الأعراض؛ قد يلزم فحص دم للغدة.", "Book a medical review if symptoms persist; a thyroid blood test may be needed.", "moderate"),
    _common_condition("iron-deficiency-anaemia", "فقر الدم بنقص الحديد", "Iron deficiency anaemia", "general",
        {"pale-skin":.8,"hair-loss":.45,"cold-extremities":.35,"general-weakness":.7,"headache":.35,"fatigue":.9,"palpitations":.45,"dizziness":.35},
        "https://www.nhs.uk/conditions/iron-deficiency-anaemia/", "اطلب تقييمًا طبيًا وفحص دم قبل تناول الحديد بجرعات علاجية.", "Seek medical review and a blood test before taking treatment-dose iron.", "moderate"),
    _common_condition("functional-constipation", "الإمساك", "Constipation", "digestive",
        {"constipation":1.0,"excessive-gas":.55,"abdominal-pain":.45},
        "https://www.nhs.uk/conditions/constipation/", "زد السوائل والألياف تدريجيًا وراجع مختصًا إذا استمر أو صاحبه دم أو نقص وزن.", "Increase fluids and fibre gradually; seek review if it persists or comes with blood or weight loss."),
    _common_condition("conjunctivitis", "التهاب الملتحمة", "Conjunctivitis", "general",
        {"eye-redness":1.0,"itching":.6,"eye-pain":.25},
        "https://www.nhs.uk/conditions/conjunctivitis/", "تجنب فرك العين واطلب تقييمًا عاجلًا إذا وُجد ألم شديد أو حساسية للضوء أو تغير رؤية.", "Avoid rubbing the eye; seek urgent review for severe pain, light sensitivity, or vision change."),
    _common_condition("dental-abscess", "خراج أو التهاب الأسنان", "Dental abscess", "pain",
        {"tooth-pain":1.0,"swollen-lymph-nodes":.45},
        "https://www.nhs.uk/conditions/dental-abscess/", "احجز طبيب أسنان؛ اطلب رعاية عاجلة عند تورم الوجه أو صعوبة التنفس أو البلع.", "See a dentist; obtain urgent care for facial swelling or trouble breathing or swallowing.", "moderate"),
    _common_condition("period-pain", "آلام الدورة الشهرية", "Period pain", "pain",
        {"menstrual-cramps":1.0,"abdominal-pain":.5},
        "https://www.nhs.uk/conditions/period-pain/", "راجع مختصًا إذا كان الألم شديدًا أو جديدًا أو يعطل نشاطك المعتاد.", "Seek review if pain is severe, new, or disrupts normal activities."),
    _common_condition("panic-disorder", "نوبات الهلع", "Panic disorder", "mental-health",
        {"panic-attack":1.0,"sweating":.6,"tremor":.55,"palpitations":.65,"shortness-of-breath":.4},
        "https://www.nhs.uk/mental-health/conditions/panic-disorder/", "اطلب تقييمًا لاستبعاد الأسباب الجسدية ووضع خطة علاج، والطوارئ للأعراض الشديدة أو غير المعتادة.", "Seek assessment to exclude physical causes and plan treatment; use emergency care for severe or unusual symptoms.", "moderate"),
    _common_condition("clinical-depression", "الاكتئاب", "Clinical depression", "mental-health",
        {"low-mood":1.0,"memory-problems":.4,"difficulty-concentrating":.55,"insomnia":.45},
        "https://www.nhs.uk/mental-health/conditions/clinical-depression/overview/", "تحدث مع مختص إذا استمر انخفاض المزاج أسبوعين أو أكثر؛ اطلب مساعدة فورية عند أفكار إيذاء النفس.", "Speak with a professional if low mood lasts 2 weeks or more; get immediate help for self-harm thoughts.", "moderate"),
    _common_condition("peripheral-oedema", "الوذمة الطرفية", "Peripheral oedema", "cardiovascular",
        {"leg-swelling":1.0,"weight-gain":.35,"shortness-of-breath":.25},
        "https://www.nhs.uk/conditions/oedema/", "اطلب تقييمًا، وبشكل عاجل إذا كان التورم مفاجئًا في ساق واحدة أو ترافق مع ضيق تنفس.", "Seek assessment, urgently if swelling is sudden in one leg or occurs with breathlessness.", "moderate"),
    _common_condition("mechanical-neck-pain", "ألم أو شد الرقبة", "Neck pain or strain", "pain",
        {"neck-pain":1.0,"muscle-cramps":.35,"shoulder-pain":.35},
        "https://www.nhs.uk/conditions/neck-pain-and-stiff-neck/", "حافظ على حركة لطيفة واطلب تقييمًا إذا استمر الألم أو صاحبه ضعف أو خدر.", "Keep gently mobile; seek review if pain persists or comes with weakness or numbness."),
    _common_condition("taste-disorder", "فقدان أو تغير التذوق", "Lost or changed sense of taste", "general",
        {"loss-of-taste":1.0}, "https://www.nhs.uk/conditions/lost-or-changed-sense-smell/",
        "راقب الأعراض واطلب تقييمًا إذا لم تعد الحاسة خلال أسابيع أو ظهرت علامات عصبية.", "Monitor symptoms and seek review if the sense does not return within weeks or neurological signs appear."),
    _common_condition("unintentional-weight-loss", "نقصان الوزن غير المقصود", "Unintentional weight loss", "general",
        {"weight-loss":1.0,"increased-thirst":.25}, "https://www.nhs.uk/conditions/unintentional-weight-loss/",
        "احجز موعدًا طبيًا إذا استمر فقدان الوزن دون تغيير مقصود في الغذاء أو النشاط.", "Book a medical review if weight loss continues without an intentional diet or activity change.", "moderate"),
    _common_condition("easy-bruising-pattern", "سهولة ظهور الكدمات", "Easy bruising", "skin",
        {"easy-bruising":1.0,"pale-skin":.25}, "https://www.nhs.uk/conditions/bruises/",
        "راجع الأدوية واطلب تقييمًا إذا كثرت الكدمات دون سبب أو ترافق معها نزيف.", "Review medicines and seek assessment for frequent unexplained bruises or associated bleeding.", "moderate"),
    _common_condition("essential-tremor", "الرعاش الأساسي", "Essential tremor", "neurological",
        {"tremor":1.0,"muscle-cramps":.2}, "https://www.nhs.uk/conditions/tremor-or-shaking-hands/",
        "اطلب تقييمًا إذا كانت الرعشة جديدة أو تزداد أو تؤثر في النشاط اليومي.", "Seek assessment if tremor is new, worsening, or affects daily activities.", "moderate"),
    _common_condition("itchy-skin", "حكة الجلد", "Itchy skin", "skin",
        {"itching":1.0}, "https://www.nhs.uk/conditions/itchy-skin/",
        "تجنب المهيجات واطلب تقييمًا إذا كانت الحكة شديدة أو منتشرة أو مستمرة.", "Avoid irritants and seek review if itching is severe, widespread, or persistent."),
    _common_condition("type-2-diabetes-pattern", "السكري من النوع الثاني", "Type 2 diabetes", "general",
        {"increased-thirst":1.0,"frequent-urination":.95,"weight-loss":.55,"general-weakness":.35,"fatigue":.45,"blurred-vision":.35}, "https://www.nhs.uk/conditions/type-2-diabetes/",
        "اطلب فحص سكر إذا استمر العطش أو ترافق مع تبول متكرر أو نقص وزن.", "Ask for a glucose test if thirst persists or occurs with frequent urination or weight loss.", "moderate"),
    _common_condition("rectal-bleeding-causes", "نزيف المستقيم وأسبابه", "Rectal bleeding and its causes", "digestive",
        {"blood-in-stool":1.0,"constipation":.3,"abdominal-pain":.25}, "https://www.nhs.uk/conditions/bleeding-from-the-bottom-rectal-bleeding/",
        "اطلب تقييمًا طبيًا؛ والطوارئ للنزيف الغزير أو البراز الأسود أو الدوخة الشديدة.", "Seek medical assessment; use emergency care for heavy bleeding, black stool, or severe dizziness.", "moderate"),
    _common_condition("swollen-glands", "تورم الغدد اللمفاوية", "Swollen glands", "general",
        {"swollen-lymph-nodes":1.0,"sore-throat":.35,"fever":.3}, "https://www.nhs.uk/conditions/swollen-glands/",
        "راقبها وراجع مختصًا إذا كبرت أو كانت صلبة أو استمرت أكثر من أسبوعين.", "Monitor them and seek review if they enlarge, feel hard, or persist beyond 2 weeks."),
    _common_condition("high-blood-pressure", "ارتفاع ضغط الدم", "High blood pressure", "cardiovascular",
        {"high-blood-pressure-symptoms":1.0,"headache":.2,"blurred-vision":.2}, "https://www.nhs.uk/conditions/high-blood-pressure-hypertension/",
        "قِس الضغط بطريقة صحيحة واطلب تقييمًا؛ الأعراض وحدها لا تؤكد ارتفاعه.", "Measure blood pressure correctly and seek review; symptoms alone do not confirm hypertension.", "moderate"),
    _common_condition("acute-confusion-pattern", "التشوش الذهني الحاد", "Sudden confusion", "neurological",
        {"confusion":1.0,"memory-problems":.25}, "https://www.nhs.uk/conditions/confusion/",
        "التشوش المفاجئ يحتاج تقييمًا عاجلًا، خصوصًا إذا كان الشخص غير قادر على الإجابة أو التصرف كالمعتاد.", "Sudden confusion needs urgent assessment, especially if the person cannot answer or behave normally.", "urgent"),
    _common_condition("facial-numbness-pattern", "تنميل الوجه", "Facial numbness", "neurological",
        {"facial-numbness":1.0}, "https://www.nhs.uk/conditions/stroke/symptoms/",
        "إذا بدأ التنميل فجأة أو ترافق مع تدلي الوجه أو ضعف أو صعوبة كلام فاتصل بالطوارئ فورًا.", "If numbness starts suddenly or comes with facial droop, weakness, or speech difficulty, call emergency services now.", "urgent"),

    _common_condition("tension-type-headache", "صداع التوتر", "Tension-type headache", "neurological",
        {"headache":1.0,"neck-pain":.55,"fatigue":.25,"insomnia":.35},
        "https://www.nhs.uk/conditions/tension-headaches/",
        "دوّن نمط الصداع ومحفزاته واطلب تقييمًا إذا تكرر عدة مرات أسبوعيًا أو أصبح شديدًا أو ظهرت علامة عصبية.",
        "Track the headache pattern and triggers; seek review if it occurs several times a week, becomes severe, or a neurological warning sign appears.", "mild"),
    _common_condition("allergic-rhinitis", "التهاب الأنف التحسسي", "Allergic rhinitis", "respiratory",
        {"sneezing":1.0,"runny-nose":.9,"nasal-congestion":.85,"cough":.35,"loss-of-smell":.35},
        "https://www.nhs.uk/conditions/allergic-rhinitis/",
        "راقب ارتباط الأعراض بالمهيجات واطلب تقييمًا إذا أثرت في النوم أو النشاط أو ترافقت مع تدهور في التنفس.",
        "Track whether symptoms follow allergen exposure and seek review if they affect sleep or daily activity, or breathing worsens.", "mild"),
    _common_condition("irritable-bowel-syndrome", "متلازمة القولون العصبي", "Irritable bowel syndrome (IBS)", "digestive",
        {"abdominal-pain":.85,"abdominal-cramps":.9,"bloating":1.0,"diarrhea":.65,"constipation":.65,"excessive-gas":.6,"nausea":.25,"back-pain":.2},
        "https://www.nhs.uk/conditions/irritable-bowel-syndrome-ibs/symptoms/",
        "راجع مختصًا إذا استمرت الأعراض أكثر من عدة أسابيع، واطلب رعاية أسرع عند نزيف أو نقص وزن غير مقصود أو كتلة بالبطن.",
        "Seek review if symptoms persist for several weeks, and sooner for bleeding, unintended weight loss, or an abdominal lump.", "moderate"),
    _common_condition("overactive-thyroid", "فرط نشاط الغدة الدرقية", "Overactive thyroid (hyperthyroidism)", "general",
        {"weight-loss":.75,"palpitations":.8,"irregular-heartbeat":.55,"tremor":.7,"sweating":.65,"anxiety":.55,"irritability":.45,"insomnia":.45,"diarrhea":.35,"increased-thirst":.3,"frequent-urination":.3,"hair-loss":.25},
        "https://www.nhs.uk/conditions/overactive-thyroid-hyperthyroidism/",
        "اطلب تقييمًا طبيًا إذا اجتمعت هذه الأعراض أو استمرت؛ قد يلزم فحص وظائف الغدة الدرقية.",
        "Seek medical review if these symptoms cluster or persist; thyroid-function testing may be needed.", "moderate"),
    _common_condition("covid-19", "كوفيد-19", "COVID-19", "respiratory",
        {"fever":.65,"cough":.75,"shortness-of-breath":.45,"sore-throat":.5,"runny-nose":.45,"loss-of-taste":.8,"loss-of-smell":.85,"fatigue":.65,"body-aches":.5,"headache":.45,"nausea":.25,"vomiting":.2,"diarrhea":.25},
        "https://www.cdc.gov/covid/signs-symptoms/",
        "إذا كانت الأعراض متوافقة مع عدوى تنفسية ففكّر في الاختبار وفق الإرشادات المحلية، واطلب تقييمًا مبكرًا إذا كان لديك عامل خطورة أو ظهرت صعوبة تنفس.",
        "If symptoms fit a respiratory infection, consider testing according to local guidance and seek early review if you have risk factors or develop breathing difficulty.", "moderate"),
    _common_condition("pneumonia", "الالتهاب الرئوي", "Pneumonia", "respiratory",
        {"cough":.8,"fever":.75,"chills":.55,"fatigue":.55,"shortness-of-breath":.65,"nausea":.2,"vomiting":.2,"diarrhea":.15,"confusion":.25},
        "https://www.cdc.gov/pneumonia/about/index.html",
        "اطلب تقييمًا طبيًا عند الحمى مع سعال وتعب أو ضيق تنفس، وبشكل عاجل عند صعوبة التنفس أو التشوش أو التدهور السريع.",
        "Seek medical assessment for fever with cough and fatigue or breathlessness, urgently for breathing difficulty, confusion, or rapid deterioration.", "moderate"),
    _common_condition("vertigo-pattern", "الدوار المرتبط باضطراب التوازن", "Vertigo / balance disorder pattern", "neurological",
        {"dizziness":1.0,"balance-problems":.8,"nausea":.45},
        "https://www.nhs.uk/conditions/vertigo/",
        "تجنب القيادة أثناء الدوار واطلب تقييمًا إذا كان جديدًا أو متكررًا، والطوارئ إذا ترافق مع ضعف أو تنميل أو صعوبة كلام أو فقدان وعي.",
        "Avoid driving while dizzy and seek review if it is new or recurrent; seek emergency care if it comes with weakness, numbness, speech difficulty, or loss of consciousness.", "moderate"),

    # --- V33: broader source-grounded coverage for common presentations ---
    _common_condition("tonsillitis", "التهاب اللوزتين", "Tonsillitis", "respiratory",
        {"sore-throat":1.0,"difficulty-swallowing":.8,"fever":.65,"cough":.35,"headache":.35,"nausea":.25,"ear-pain":.25,"fatigue":.45,"swollen-lymph-nodes":.65},
        "https://www.nhs.uk/conditions/tonsillitis/",
        "راقب القدرة على البلع والترطيب واطلب تقييمًا إذا استمرت الأعراض أو أصبح البلع صعبًا؛ اطلب رعاية عاجلة إذا تعذر البلع أو التنفس.",
        "Monitor swallowing and hydration and seek review if symptoms persist or swallowing becomes difficult; seek urgent care if swallowing or breathing becomes impossible.", "moderate"),
    _common_condition("labyrinthitis-vestibular-neuritis", "التهاب الأذن الداخلية أو العصب الدهليزي", "Labyrinthitis / vestibular neuritis", "neurological",
        {"dizziness":1.0,"balance-problems":.9,"nausea":.65,"vomiting":.45,"tinnitus":.55,"fatigue":.2},
        "https://www.nhs.uk/conditions/labyrinthitis/",
        "تجنب القيادة أثناء الدوار واطلب تقييمًا إذا لم تتحسن الأعراض خلال أيام أو ساءت، وبشكل عاجل عند فقدان سمع مفاجئ أو علامة عصبية.",
        "Avoid driving while dizzy and seek review if symptoms do not improve within days or worsen; seek urgent assessment for sudden hearing loss or neurological signs.", "moderate"),
    _common_condition("menieres-disease", "مرض منيير", "Ménière's disease", "neurological",
        {"dizziness":.95,"balance-problems":.9,"tinnitus":1.0,"nausea":.55,"vomiting":.35,"ear-pain":.25},
        "https://www.nhs.uk/conditions/menieres-disease/",
        "اطلب تقييمًا طبيًا لنوبات الدوار المتكررة المصحوبة بطنين أو أعراض أذن، ولا تقد السيارة أثناء النوبة.",
        "Seek medical review for recurrent vertigo with tinnitus or ear symptoms, and do not drive during an attack.", "moderate"),
    _common_condition("atopic-eczema", "الإكزيما التأتبية", "Atopic eczema", "skin",
        {"itching":1.0,"dry-skin":.95,"skin-rash":.9},
        "https://www.nhs.uk/conditions/atopic-eczema/",
        "استخدم عناية لطيفة بالبشرة واطلب تقييمًا إذا لم تتحسن الحالة أو ظهرت حرارة أو ألم أو إفرازات قد تدل على عدوى.",
        "Use gentle skin care and seek review if it does not improve or if fever, pain, or discharge suggests infection.", "mild"),
    _common_condition("psoriasis", "الصدفية", "Psoriasis", "skin",
        {"skin-rash":1.0,"dry-skin":.9,"itching":.7,"joint-pain":.25},
        "https://www.nhs.uk/conditions/psoriasis/",
        "اطلب تقييمًا إذا كانت البقع متكررة أو واسعة أو مؤلمة، أو إذا ترافق الطفح مع ألم وتورم مستمر في المفاصل.",
        "Seek review if patches are recurrent, widespread, or painful, or if rash occurs with persistent joint pain and swelling.", "moderate"),
    _common_condition("shingles", "الحزام الناري", "Shingles", "skin",
        {"skin-rash":1.0,"burning-sensation":.85,"itching":.55,"headache":.25,"fatigue":.3},
        "https://www.nhs.uk/conditions/shingles/",
        "اطلب نصيحة صحية مبكرًا عند طفح مؤلم أحادي الجانب، وبشكل عاجل إذا كان الطفح قرب العين أو حدث تغير في الرؤية أو كان لديك ضعف شديد في المناعة.",
        "Seek early medical advice for a painful one-sided rash, urgently if it is near the eye, vision changes occur, or immunity is severely weakened.", "moderate"),
    _common_condition("haemorrhoids", "البواسير", "Haemorrhoids (piles)", "digestive",
        {"blood-in-stool":.9,"constipation":.55,"itching":.45},
        "https://www.nhs.uk/conditions/piles-haemorrhoids/",
        "لا تفترض أن النزف سببه البواسير دون تقييم إذا كان جديدًا أو متكررًا؛ اطلب رعاية عاجلة للنزيف الغزير أو المستمر.",
        "Do not assume new or recurrent bleeding is from haemorrhoids without assessment; seek urgent care for heavy or ongoing bleeding.", "moderate"),
    _common_condition("lactose-intolerance", "عدم تحمل اللاكتوز", "Lactose intolerance", "digestive",
        {"abdominal-pain":.75,"bloating":1.0,"excessive-gas":.95,"diarrhea":.75,"constipation":.3,"nausea":.4,"vomiting":.15},
        "https://www.nhs.uk/conditions/lactose-intolerance/",
        "راقب ارتباط الأعراض بمنتجات الحليب واطلب تقييمًا إذا كانت مستمرة أو تسبب نقص وزن أو تؤثر في التغذية.",
        "Track whether symptoms follow dairy intake and seek review if they persist, cause weight loss, or affect nutrition.", "mild"),
    _common_condition("gastritis", "التهاب المعدة", "Gastritis", "digestive",
        {"abdominal-pain":.85,"bloating":.65,"nausea":.75,"vomiting":.45,"loss-of-appetite":.55,"heartburn":.45},
        "https://www.nhs.uk/conditions/gastritis/",
        "اطلب تقييمًا إذا استمر ألم المعدة أو عسر الهضم أكثر من أسبوع أو تكرر، وبشكل أسرع مع قيء مستمر أو نقص وزن أو صعوبة بلع.",
        "Seek review if stomach pain or indigestion lasts more than a week or keeps returning, sooner for persistent vomiting, weight loss, or swallowing difficulty.", "moderate"),
    _common_condition("gallstones", "حصوات المرارة", "Gallstones", "digestive",
        {"abdominal-pain":1.0,"nausea":.55,"vomiting":.45,"fever":.2},
        "https://www.nhs.uk/conditions/gallstones/",
        "اطلب تقييمًا عند ألم بطني يستمر أكثر من 30 دقيقة، وبشكل عاجل إذا كان الألم شديدًا أو ترافق مع قيء متكرر أو حرارة أو اصفرار.",
        "Seek assessment for abdominal pain lasting over 30 minutes, urgently if severe or accompanied by repeated vomiting, fever, or jaundice.", "moderate"),
    _common_condition("kidney-stones", "حصوات الكلى", "Kidney stones", "digestive",
        {"abdominal-pain":.9,"back-pain":.75,"nausea":.6,"vomiting":.45,"painful-urination":.35,"frequent-urination":.25},
        "https://www.nhs.uk/conditions/kidney-stones/",
        "اطلب تقييمًا للألم الشديد أو المتكرر في الجانب أو الظهر، وبشكل عاجل إذا ترافق مع حرارة أو قشعريرة أو دم واضح في البول.",
        "Seek assessment for severe or recurrent side/back pain, urgently if accompanied by fever, chills, or visible blood in urine.", "moderate"),
    _common_condition("kidney-infection", "التهاب الكلى", "Kidney infection", "digestive",
        {"fever":.85,"nausea":.55,"vomiting":.4,"back-pain":.8,"painful-urination":.75,"frequent-urination":.7,"chills":.65,"body-aches":.35},
        "https://www.nhs.uk/conditions/kidney-infection/",
        "التهاب الكلى يحتاج تقييمًا وعلاجًا طبيًا؛ اطلب مساعدة عاجلة عند حرارة شديدة أو تدهور أو تشوش أو عدم القدرة على التبول.",
        "Kidney infection needs medical assessment and treatment; seek urgent help for high fever, deterioration, confusion, or inability to urinate.", "moderate"),
    _common_condition("generalised-anxiety-disorder", "اضطراب القلق العام", "Generalised anxiety disorder", "mental-health",
        {"anxiety":1.0,"irritability":.65,"difficulty-concentrating":.75,"insomnia":.7,"fatigue":.55,"palpitations":.4,"dizziness":.3,"low-mood":.3},
        "https://www.nhs.uk/mental-health/conditions/generalised-anxiety-disorder-gad/",
        "تحدث مع مختص إذا كان القلق مستمرًا ويؤثر في حياتك اليومية، واطلب دعمًا فوريًا عند وجود خطر على سلامتك.",
        "Speak with a professional if anxiety is persistent and affects daily life; get immediate support if there is a safety risk.", "moderate"),
    _common_condition("fibromyalgia", "الألم العضلي الليفي", "Fibromyalgia", "pain",
        {"body-aches":1.0,"back-pain":.55,"neck-pain":.55,"fatigue":.85,"insomnia":.65,"difficulty-concentrating":.55,"headache":.35,"burning-sensation":.25},
        "https://www.nhs.uk/conditions/fibromyalgia/symptoms/",
        "اطلب تقييمًا إذا كان الألم واسع الانتشار ومستمرًا مع تعب أو اضطراب نوم، لأن التشخيص يتطلب استبعاد أسباب أخرى.",
        "Seek review for persistent widespread pain with fatigue or sleep problems because diagnosis requires other causes to be excluded.", "moderate"),
    _common_condition("rheumatoid-arthritis", "التهاب المفاصل الروماتويدي", "Rheumatoid arthritis", "pain",
        {"joint-pain":1.0,"swelling":.75,"fatigue":.55,"weight-loss":.25,"wrist-pain":.65,"knee-pain":.45,"general-weakness":.25},
        "https://www.nhs.uk/conditions/rheumatoid-arthritis/",
        "اطلب تقييمًا مبكرًا عند ألم وتورم أو تيبس مفاصل مستمر، لأن العلاج المبكر يساعد على الحد من تلف المفاصل.",
        "Seek early assessment for persistent joint pain, swelling, or stiffness because early treatment can limit joint damage.", "moderate"),
    _common_condition("dry-eyes", "جفاف العين", "Dry eyes", "general",
        {"eye-redness":.7,"eye-pain":.35,"blurred-vision":.55,"light-sensitivity":.4,"itching":.45},
        "https://www.nhs.uk/symptoms/dry-eyes/",
        "جرّب إراحة العين وتجنب المهيجات، واطلب تقييمًا إذا استمرت الأعراض لأسابيع؛ الألم مع احمرار أو تغير الرؤية يحتاج تقييمًا أسرع.",
        "Rest the eyes and avoid irritants; seek review if symptoms persist for weeks, and sooner for a painful red eye or vision change.", "mild"),
    _common_condition("bursitis", "التهاب الجراب", "Bursitis", "pain",
        {"joint-pain":.75,"shoulder-pain":.75,"knee-pain":.75,"swelling":.65},
        "https://www.nhs.uk/conditions/bursitis/",
        "خفف الضغط على المفصل واطلب تقييمًا إذا لم يتحسن خلال أسبوعين أو كان الألم شديدًا أو ظهرت حرارة أو عدم قدرة على الحركة.",
        "Reduce pressure on the joint and seek review if it does not improve within two weeks, pain is severe, fever develops, or movement is limited.", "mild"),
    _common_condition("sprain-strain", "التواء أو شد عضلي", "Sprain or strain", "pain",
        {"wrist-pain":.6,"knee-pain":.65,"leg-pain":.65,"back-pain":.55,"shoulder-pain":.45,"muscle-cramps":.35,"swelling":.45},
        "https://www.nhs.uk/conditions/sprains-and-strains/",
        "إذا كان الألم بعد إصابة بسيطة فخفف النشاط وراقب التحسن؛ اطلب تقييمًا إذا كان الألم شديدًا أو لا تستطيع استخدام الطرف أو ظهرت خدر أو تغيرات لون.",
        "For minor injury-related pain, reduce activity and monitor improvement; seek assessment for severe pain, inability to use the limb, numbness, or colour change.", "mild"),
    _common_condition("vitamin-b12-folate-deficiency", "نقص فيتامين B12 أو الفولات", "Vitamin B12 or folate deficiency", "general",
        {"fatigue":.85,"general-weakness":.75,"numbness":.7,"hand-numbness":.45,"foot-numbness":.45,"memory-problems":.55,"difficulty-concentrating":.45,"blurred-vision":.35,"palpitations":.35,"loss-of-appetite":.3,"balance-problems":.35},
        "https://www.nhs.uk/conditions/vitamin-b12-or-folate-deficiency-anaemia/",
        "اطلب تقييمًا وفحص دم إذا كانت الأعراض مستمرة؛ لا تعتمد على المكملات وحدها قبل معرفة السبب، خصوصًا مع أعراض عصبية.",
        "Seek assessment and blood testing for persistent symptoms; do not rely on supplements alone before identifying the cause, especially with neurological symptoms.", "moderate"),
    _common_condition("me-cfs", "التهاب الدماغ والنخاع العضلي / متلازمة التعب المزمن", "ME/CFS", "general",
        {"fatigue":1.0,"insomnia":.7,"difficulty-concentrating":.75,"memory-problems":.6,"body-aches":.45,"joint-pain":.35,"headache":.35,"dizziness":.3},
        "https://www.nhs.uk/conditions/chronic-fatigue-syndrome-cfs/",
        "اطلب تقييمًا إذا كان التعب شديدًا ومستمرًا ويؤثر في النشاط؛ التشخيص يحتاج استبعاد أسباب أخرى ولا يعتمد على عرض واحد.",
        "Seek review if fatigue is severe, persistent, and limits activity; diagnosis requires other causes to be excluded and cannot be based on one symptom.", "moderate"),
])

# These additions use the existing normalization, source validation, seeding,
# and differential-question pipeline; no diagnostic thresholds are changed.
from medical_knowledge_extra import EXTRA_SYMPTOMS, EXTRA_DISEASES

def _merge_symptom_rows(base_rows, extra_rows):
    """Merge extension symptoms by slug instead of creating duplicate concepts.

    Extension packs are intentionally easy to grow.  Treating a repeated slug as
    a second symptom would duplicate aliases and can distort matching/scoring.
    This keeps one canonical row while preserving every curated alias.
    """
    merged = list(base_rows)
    by_slug = {row[0]: i for i, row in enumerate(merged)}
    for row in extra_rows:
        slug, ar, en, category, aliases_ar, aliases_en = row
        idx = by_slug.get(slug)
        if idx is None:
            by_slug[slug] = len(merged)
            merged.append(row)
            continue
        old = merged[idx]
        merged[idx] = (
            old[0], old[1] or ar, old[2] or en, old[3] or category,
            list(dict.fromkeys(list(old[4]) + list(aliases_ar))),
            list(dict.fromkeys(list(old[5]) + list(aliases_en))),
        )
    return merged

SYMPTOMS = _merge_symptom_rows(SYMPTOMS, EXTRA_SYMPTOMS)
DISEASES.extend(EXTRA_DISEASES)

# 2026-09 expansion: additional symptom concepts, independent authoritative
# sources, and source-grounded conditions.  Keeping the pack separate makes it
# reviewable/versionable while the seed remains idempotent.
from medical_knowledge_expansion_v2 import (
    EXTRA_SOURCES_V2, EXTRA_SYMPTOMS_V2, EXTRA_DISEASES_V2,
    EXISTING_DISEASE_SOURCE_ENRICHMENT, EXISTING_DISEASE_SYMPTOM_ENRICHMENT,
    EXTRA_RED_RULES_V2, EXTRA_RED_RULE_DETAILS_V2,
)

SOURCES.extend(EXTRA_SOURCES_V2)
SYMPTOMS = _merge_symptom_rows(SYMPTOMS, EXTRA_SYMPTOMS_V2)
DISEASES.extend(EXTRA_DISEASES_V2)

# V61: broader official-source expansion for search/symptom coverage.
from medical_knowledge_expansion_v3 import (
    EXTRA_SOURCES_V3, EXTRA_SYMPTOMS_V3, EXTRA_DISEASES_V3,
    EXISTING_DISEASE_SOURCE_ENRICHMENT_V3, EXISTING_DISEASE_SYMPTOM_ENRICHMENT_V3,
    EXTRA_RED_RULES_V3, EXTRA_RED_RULE_DETAILS_V3,
)

SOURCES.extend(EXTRA_SOURCES_V3)
SYMPTOMS = _merge_symptom_rows(SYMPTOMS, EXTRA_SYMPTOMS_V3)
DISEASES.extend(EXTRA_DISEASES_V3)

# V62: high-frequency everyday topics for search and symptom analysis.
from medical_knowledge_expansion_v4 import (
    EXTRA_SOURCES_V4, EXTRA_SYMPTOMS_V4, EXTRA_DISEASES_V4,
    EXISTING_DISEASE_SOURCE_ENRICHMENT_V4, EXISTING_DISEASE_SYMPTOM_ENRICHMENT_V4,
    EXTRA_RED_RULES_V4, EXTRA_RED_RULE_DETAILS_V4,
)

SOURCES.extend(EXTRA_SOURCES_V4)
SYMPTOMS = _merge_symptom_rows(SYMPTOMS, EXTRA_SYMPTOMS_V4)
DISEASES.extend(EXTRA_DISEASES_V4)

# V73: common everyday symptom coverage with direct NHS references.
from medical_knowledge_expansion_v5 import (
    EXTRA_SOURCES_V5, EXTRA_SYMPTOMS_V5, EXTRA_DISEASES_V5,
    EXISTING_DISEASE_SOURCE_ENRICHMENT_V5, EXISTING_DISEASE_SYMPTOM_ENRICHMENT_V5,
    EXTRA_RED_RULES_V5, EXTRA_RED_RULE_DETAILS_V5,
)

SOURCES.extend(EXTRA_SOURCES_V5)
SYMPTOMS = _merge_symptom_rows(SYMPTOMS, EXTRA_SYMPTOMS_V5)
DISEASES.extend(EXTRA_DISEASES_V5)

# V74: broader specialty-source coverage + more common everyday topics.
from medical_knowledge_expansion_v6 import (
    EXTRA_SOURCES_V6, EXTRA_SYMPTOMS_V6, EXTRA_DISEASES_V6,
    EXISTING_DISEASE_SOURCE_ENRICHMENT_V6, EXISTING_DISEASE_SYMPTOM_ENRICHMENT_V6,
    EXTRA_RED_RULES_V6, EXTRA_RED_RULE_DETAILS_V6,
)

SOURCES.extend(EXTRA_SOURCES_V6)
SYMPTOMS = _merge_symptom_rows(SYMPTOMS, EXTRA_SYMPTOMS_V6)
DISEASES.extend(EXTRA_DISEASES_V6)

# V75: broaden everyday symptom vocabulary and connect Health Search to more
# source-grounded symptom concepts without creating new diagnoses.
from medical_knowledge_expansion_v7 import (
    EXTRA_SOURCES_V7, EXTRA_SYMPTOMS_V7, EXTRA_DISEASES_V7,
    EXISTING_DISEASE_SOURCE_ENRICHMENT_V7, EXISTING_DISEASE_SYMPTOM_ENRICHMENT_V7,
    EXTRA_RED_RULES_V7, EXTRA_RED_RULE_DETAILS_V7,
)
SOURCES.extend(EXTRA_SOURCES_V7)
SYMPTOMS = _merge_symptom_rows(SYMPTOMS, EXTRA_SYMPTOMS_V7)
DISEASES.extend(EXTRA_DISEASES_V7)

# V76: post-audit cleanup/addition pack. Keep release-level changes separate
# so growth metrics remain truthful instead of mutating the V75 pack.
from medical_knowledge_expansion_v8 import (
    EXTRA_SOURCES_V8, EXTRA_SYMPTOMS_V8, EXTRA_DISEASES_V8,
    EXISTING_DISEASE_SOURCE_ENRICHMENT_V8, EXISTING_DISEASE_SYMPTOM_ENRICHMENT_V8,
    EXTRA_RED_RULES_V8, EXTRA_RED_RULE_DETAILS_V8,
)
SOURCES.extend(EXTRA_SOURCES_V8)
SYMPTOMS = _merge_symptom_rows(SYMPTOMS, EXTRA_SYMPTOMS_V8)
DISEASES.extend(EXTRA_DISEASES_V8)

# V191: professional source/data expansion for cardiovascular, renal, thyroid,
# and iron-deficiency symptom patterns.
from medical_knowledge_expansion_v9 import (
    EXTRA_SOURCES_V9, EXTRA_SYMPTOMS_V9, EXTRA_DISEASES_V9,
    EXISTING_DISEASE_SOURCE_ENRICHMENT_V9, EXISTING_DISEASE_SYMPTOM_ENRICHMENT_V9,
    EXTRA_RED_RULES_V9, EXTRA_RED_RULE_DETAILS_V9,
)
SOURCES.extend(EXTRA_SOURCES_V9)
SYMPTOMS = _merge_symptom_rows(SYMPTOMS, EXTRA_SYMPTOMS_V9)
DISEASES.extend(EXTRA_DISEASES_V9)

# Merge V61+ enrichments into the existing reviewed enrichment maps.
for _slug, _rows in EXISTING_DISEASE_SOURCE_ENRICHMENT_V3.items():
    EXISTING_DISEASE_SOURCE_ENRICHMENT.setdefault(_slug, []).extend(_rows)
for _slug, _rows in EXISTING_DISEASE_SYMPTOM_ENRICHMENT_V3.items():
    EXISTING_DISEASE_SYMPTOM_ENRICHMENT.setdefault(_slug, {}).update(_rows)
for _slug, _rows in EXISTING_DISEASE_SOURCE_ENRICHMENT_V4.items():
    EXISTING_DISEASE_SOURCE_ENRICHMENT.setdefault(_slug, []).extend(_rows)
for _slug, _rows in EXISTING_DISEASE_SYMPTOM_ENRICHMENT_V4.items():
    EXISTING_DISEASE_SYMPTOM_ENRICHMENT.setdefault(_slug, {}).update(_rows)
for _slug, _rows in EXISTING_DISEASE_SOURCE_ENRICHMENT_V5.items():
    EXISTING_DISEASE_SOURCE_ENRICHMENT.setdefault(_slug, []).extend(_rows)
for _slug, _rows in EXISTING_DISEASE_SYMPTOM_ENRICHMENT_V5.items():
    EXISTING_DISEASE_SYMPTOM_ENRICHMENT.setdefault(_slug, {}).update(_rows)
for _slug, _rows in EXISTING_DISEASE_SOURCE_ENRICHMENT_V6.items():
    EXISTING_DISEASE_SOURCE_ENRICHMENT.setdefault(_slug, []).extend(_rows)
for _slug, _rows in EXISTING_DISEASE_SYMPTOM_ENRICHMENT_V6.items():
    EXISTING_DISEASE_SYMPTOM_ENRICHMENT.setdefault(_slug, {}).update(_rows)
for _slug, _rows in EXISTING_DISEASE_SOURCE_ENRICHMENT_V7.items():
    EXISTING_DISEASE_SOURCE_ENRICHMENT.setdefault(_slug, []).extend(_rows)
for _slug, _rows in EXISTING_DISEASE_SYMPTOM_ENRICHMENT_V7.items():
    EXISTING_DISEASE_SYMPTOM_ENRICHMENT.setdefault(_slug, {}).update(_rows)
for _slug, _rows in EXISTING_DISEASE_SOURCE_ENRICHMENT_V8.items():
    EXISTING_DISEASE_SOURCE_ENRICHMENT.setdefault(_slug, []).extend(_rows)
for _slug, _rows in EXISTING_DISEASE_SYMPTOM_ENRICHMENT_V8.items():
    EXISTING_DISEASE_SYMPTOM_ENRICHMENT.setdefault(_slug, {}).update(_rows)
for _slug, _rows in EXISTING_DISEASE_SOURCE_ENRICHMENT_V9.items():
    EXISTING_DISEASE_SOURCE_ENRICHMENT.setdefault(_slug, []).extend(_rows)
for _slug, _rows in EXISTING_DISEASE_SYMPTOM_ENRICHMENT_V9.items():
    EXISTING_DISEASE_SYMPTOM_ENRICHMENT.setdefault(_slug, {}).update(_rows)

# V251: verified second/third sources (MedlinePlus, Mayo Clinic, Cleveland Clinic, NIH ...) for conditions that had one.
import trusted_sources_wiring as _tsw
SOURCES.extend(row for row in _tsw.EXTRA_SOURCES if not any(r[0] == row[0] for r in SOURCES))
_SUPPLEMENTARY_URLS = frozenset(_r[3] for _rows in _tsw.disease_source_rows().values() for _r in _rows)
for _slug, _rows in _tsw.disease_source_rows().items():
    EXISTING_DISEASE_SOURCE_ENRICHMENT.setdefault(_slug, []).extend(_rows)

# Enrich existing conditions without duplicating a disease row.  The stronger
# weight wins for a repeated symptom and source tuples are de-duplicated by
# (source slug, reference URL).
for _disease in DISEASES:
    _slug = _disease.get("slug")
    for _symptom_slug, _weight in EXISTING_DISEASE_SYMPTOM_ENRICHMENT.get(_slug, {}).items():
        _disease.setdefault("symptoms", {})[_symptom_slug] = max(
            float(_disease.get("symptoms", {}).get(_symptom_slug, 0.0)), float(_weight)
        )
    if _slug in EXISTING_DISEASE_SOURCE_ENRICHMENT:
        _seen = {(row[0], row[3]) for row in _disease.get("sources", [])}
        for _source_row in EXISTING_DISEASE_SOURCE_ENRICHMENT[_slug]:
            if (_source_row[0], _source_row[3]) not in _seen:
                _disease.setdefault("sources", []).append(_source_row)
                _seen.add((_source_row[0], _source_row[3]))

RED_RULES = [
    ("severe-chest-pain", "ألم صدر شديد", "Severe chest pain", [], "any", ["ألم صدر شديد", "الم صدر شديد", "ألم شديد في الصدر", "الم شديد في الصدر", "ضغط شديد في الصدر"], ["severe chest pain", "crushing chest pain", "squeezing chest pain", "chest feels tight or heavy"], 1, "urgent", "ألم الصدر الشديد أو الضغط الشديد في الصدر يحتاج تقييمًا عاجلًا.", "Severe chest pain or severe chest pressure needs urgent assessment.", "nhs"),
    ("sudden-one-sided-numbness", "تنميل مفاجئ في جهة واحدة", "Sudden one-sided numbness", ["one-sided-numbness"], "any", [], [], 1, "urgent", "التنميل المفاجئ في جهة واحدة قد يكون علامة عصبية طارئة.", "Sudden numbness on one side can be a neurological emergency sign.", "cdc"),
    ("sudden-one-sided-weakness", "ضعف مفاجئ في جهة واحدة", "Sudden one-sided weakness", ["one-sided-weakness"], "any", [], [], 1, "urgent", "الضعف المفاجئ في جهة واحدة من الجسم قد يكون علامة سكتة دماغية.", "Sudden weakness on one side of the body can be a stroke warning sign.", "cdc"),
    ("sudden-facial-numbness", "تنميل مفاجئ في الوجه", "Sudden facial numbness", ["facial-numbness"], "any", [], [], 1, "urgent", "التنميل المفاجئ في الوجه من علامات السكتة الدماغية المعروفة (اختبار FAST) ويستدعي تقييمًا طارئًا.", "Sudden facial numbness is a recognized stroke warning sign (the FAST test) and requires urgent evaluation.", "cdc"),
    ("chest-breathing", "ألم الصدر مع ضيق التنفس", "Chest pain with breathing difficulty", ["chest-pain","shortness-of-breath"], "all", [], [], 1, "urgent", "ألم الصدر مع صعوبة التنفس قد يحتاج رعاية عاجلة.", "Chest pain with breathing difficulty may require urgent care.", "nhs"),
    ("stroke-combination", "علامات سكتة دماغية محتملة", "Possible stroke signs", ["one-sided-weakness","speech-difficulty"], "all", [], [], 1, "urgent", "ضعف جانب واحد مع صعوبة الكلام علامة طارئة محتملة.", "One-sided weakness with speech difficulty is a possible emergency.", "cdc"),
    ("face-droop", "تدلي الوجه المفاجئ", "Sudden face drooping", ["face-drooping"], "any", [], [], 1, "urgent", "تدلي الوجه المفاجئ يحتاج طلب الطوارئ فورًا.", "Sudden face drooping needs emergency help now.", "cdc"),
    ("sudden-vision", "فقدان الرؤية المفاجئ", "Sudden vision loss", ["sudden-vision-loss"], "any", [], [], 1, "urgent", "فقدان الرؤية المفاجئ يحتاج تقييمًا عاجلًا.", "Sudden vision loss needs urgent assessment.", "cdc"),
    ("unconscious", "فقدان الوعي", "Loss of consciousness", ["loss-of-consciousness"], "any", [], [], 1, "urgent", "فقدان الوعي علامة تستدعي طلب الطوارئ.", "Loss of consciousness requires emergency help.", "nhs"),
    ("seizure-event", "نوبة تشنجية", "Seizure", ["seizure"], "any", [], [], 1, "urgent", "النوبة التشنجية علامة تستدعي طلب الطوارئ، خصوصًا إن كانت الأولى أو استمرت طويلًا.", "A seizure is a sign that requires emergency help, especially if it is the first one or lasts a long time.", "cdc"),
    ("severe-bleeding", "نزيف شديد", "Severe bleeding", ["severe-bleeding"], "any", [], [], 1, "urgent", "النزيف الشديد أو الذي لا يتوقف يحتاج طوارئ.", "Severe or uncontrolled bleeding needs emergency care.", "nhs"),
    ("severe-head-neuro", "صداع شديد مع علامة عصبية", "Severe headache with neurological sign", ["severe-headache","one-sided-weakness"], "all", [], [], 1, "urgent", "الصداع الشديد المفاجئ مع ضعف في جانب واحد علامة طارئة.", "A sudden severe headache with one-sided weakness is an emergency sign.", "cdc"),
    ("self-harm", "خطر إيذاء النفس", "Risk of self-harm", ["suicidal-thoughts"], "any", [], [], 1, "urgent", "أفكار إيذاء النفس تحتاج دعمًا فوريًا وعدم البقاء وحيدًا.", "Thoughts of self-harm need immediate support; do not stay alone.", "who"),
    ("severe-breathing", "ضيق تنفس شديد", "Severe breathing difficulty", ["shortness-of-breath"], "any", [], [], 4, "urgent", "ضيق التنفس الشديد يحتاج تقييمًا عاجلًا.", "Severe breathing difficulty needs urgent assessment.", "nhs"),
    ("chest-review", "ألم في الصدر", "Chest pain", ["chest-pain"], "any", [], [], 1, "review", "ألم الصدر يحتاج تقييمًا طبيًا حتى دون علامات أخرى.", "Chest pain needs medical assessment even without other signs.", "nhs"),
]
RED_RULES.extend(EXTRA_RED_RULES_V2)
RED_RULES.extend(EXTRA_RED_RULES_V3)
RED_RULES.extend(EXTRA_RED_RULES_V4)
RED_RULES.extend(EXTRA_RED_RULES_V5)
RED_RULES.extend(EXTRA_RED_RULES_V6)
RED_RULES.extend(EXTRA_RED_RULES_V7)
RED_RULES.extend(EXTRA_RED_RULES_V8)
RED_RULES.extend(EXTRA_RED_RULES_V9)

# Source-grounded metadata for the independent safety layer. These references
# point to official pages and are never generated by the AI model.
RED_RULE_DETAILS = {
    "severe-chest-pain": {
        "description_ar": "ألم الصدر الشديد أو الإحساس بضغط أو ثقل شديد قد يكون علامة تستدعي رعاية طارئة، خصوصًا إذا كان مفاجئًا أو مستمرًا أو ترافق مع أعراض أخرى.",
        "description_en": "Severe chest pain or severe pressure/heaviness can be an emergency warning sign, especially when sudden, persistent, or accompanied by other symptoms.",
        "action_ar": "اطلب خدمات الطوارئ المناسبة فورًا إذا كان ألم الصدر شديدًا أو مفاجئًا، ولا تنتظر زواله.",
        "action_en": "Contact the appropriate emergency service immediately for severe or sudden chest pain; do not wait for it to pass.",
        "url": "https://www.nhs.uk/symptoms/chest-pain/",
    },
    "sudden-one-sided-numbness": {
        "description_ar": "التنميل أو الضعف المفاجئ في الوجه أو الذراع أو الساق، خصوصًا في جهة واحدة، من علامات السكتة الدماغية المعروفة.",
        "description_en": "Sudden numbness or weakness of the face, arm, or leg, especially on one side, is a recognized stroke warning sign.",
        "action_ar": "اطلب خدمات الطوارئ فورًا ولا تنتظر زوال الأعراض.",
        "action_en": "Contact emergency services immediately and do not wait for symptoms to pass.",
        "url": "https://www.cdc.gov/stroke/signs-symptoms/index.html",
    },
    "sudden-one-sided-weakness": {
        "description_ar": "الضعف المفاجئ في الوجه أو الذراع أو الساق، خصوصًا في جهة واحدة، من علامات السكتة الدماغية المعروفة (اختبار FAST).",
        "description_en": "Sudden weakness of the face, arm, or leg, especially on one side, is a recognized stroke warning sign (the FAST test).",
        "action_ar": "اطلب خدمات الطوارئ فورًا ولا تنتظر زوال الأعراض.",
        "action_en": "Contact emergency services immediately and do not wait for symptoms to pass.",
        "url": "https://www.cdc.gov/stroke/signs-symptoms/index.html",
    },
    "sudden-facial-numbness": {
        "description_ar": "التنميل المفاجئ في الوجه، خصوصًا في جانب واحد، من علامات السكتة الدماغية المعروفة (اختبار FAST).",
        "description_en": "Sudden numbness of the face, especially on one side, is a recognized stroke warning sign (the FAST test).",
        "action_ar": "اطلب خدمات الطوارئ فورًا ولا تنتظر زوال الأعراض.",
        "action_en": "Contact emergency services immediately and do not wait for symptoms to pass.",
        "url": "https://www.cdc.gov/stroke/signs-symptoms/index.html",
    },
    "chest-breathing": {
        "description_ar": "ألم الصدر المصحوب بضيق تنفس قد يكون علامة تستدعي تقييمًا طارئاً.",
        "description_en": "Chest pain with shortness of breath can be a sign requiring emergency assessment.",
        "action_ar": "اطلب الرعاية الطبية العاجلة أو تواصل مع خدمات الطوارئ المناسبة.",
        "action_en": "Seek urgent medical care or contact the appropriate emergency service.",
        "url": "https://www.nhs.uk/symptoms/chest-pain/"},
    "stroke-combination": {
        "description_ar": "الضعف المفاجئ في جانب واحد مع صعوبة الكلام من علامات السكتة الدماغية المعروفة.",
        "description_en": "Sudden one-sided weakness with speech difficulty is a recognized stroke warning sign.",
        "action_ar": "اطلب خدمات الطوارئ فورًا ولا تنتظر زوال الأعراض.",
        "action_en": "Contact emergency services immediately and do not wait for symptoms to pass.",
        "url": "https://www.cdc.gov/stroke/signs-symptoms/index.html"},
    "face-droop": {
        "description_ar": "تدلي الوجه المفاجئ قد يكون من علامات السكتة الدماغية.",
        "description_en": "Sudden facial drooping can be a stroke warning sign.",
        "action_ar": "اطلب خدمات الطوارئ فورًا.", "action_en": "Contact emergency services immediately.",
        "url": "https://www.cdc.gov/stroke/signs-symptoms/index.html"},
    "sudden-vision": {
        "description_ar": "التغير أو الفقدان المفاجئ للرؤية قد يظهر ضمن علامات السكتة الدماغية.",
        "description_en": "Sudden vision trouble or loss can occur among stroke warning signs.",
        "action_ar": "اطلب تقييمًا طبيًا طارئاً فورًا.", "action_en": "Seek emergency medical assessment immediately.",
        "url": "https://www.cdc.gov/stroke/signs-symptoms/index.html"},
    "unconscious": {
        "description_ar": "فقدان الوعي أو عدم الاستجابة قد يمثل حالة مهددة للحياة.",
        "description_en": "Loss of consciousness or abnormal unresponsiveness can represent a life-threatening emergency.",
        "action_ar": "تواصل مع خدمات الطوارئ المناسبة فورًا.", "action_en": "Contact the appropriate emergency service immediately.",
        "url": "https://www.nhs.uk/nhs-services/urgent-and-emergency-care-services/when-to-call-999/"},
    "seizure-event": {
        "description_ar": "النوبة التشنجية، خصوصًا الأولى أو المطوّلة أو المتكررة، قد تكون علامة طارئة تستدعي تقييمًا فوريًا.",
        "description_en": "A seizure — especially a first, prolonged, or repeated one — can be an emergency sign requiring immediate assessment.",
        "action_ar": "اطلب الطوارئ فورًا، خصوصًا إن استمرت النوبة أكثر من 5 دقائق أو تكررت أو لم يستعد الوعي بعدها.",
        "action_en": "Seek emergency help immediately, especially if the seizure lasts more than 5 minutes, repeats, or consciousness does not return afterward.",
        "url": "https://www.cdc.gov/epilepsy/about/first-aid.htm"},
    "severe-bleeding": {
        "description_ar": "النزيف الغزير أو الذي لا يمكن إيقافه يحتاج إلى رعاية طارئة.",
        "description_en": "Heavy or uncontrolled bleeding requires emergency care.",
        "action_ar": "اطلب الطوارئ أو توجّه للرعاية العاجلة المناسبة.", "action_en": "Contact emergency services or obtain appropriate emergency care.",
        "url": "https://www.nhs.uk/conditions/cuts-and-grazes/"},
    "severe-head-neuro": {
        "description_ar": "الصداع الشديد المفاجئ مع ضعف في جانب واحد من علامات الخطر العصبية.",
        "description_en": "A sudden severe headache with one-sided weakness is a neurological red flag.",
        "action_ar": "اطلب خدمات الطوارئ فورًا.", "action_en": "Contact emergency services immediately.",
        "url": "https://www.cdc.gov/stroke/signs-symptoms/index.html"},
    "self-harm": {
        "description_ar": "وجود أفكار لإيذاء النفس يحتاج دعماً فوريًا وتقييمًا للسلامة.",
        "description_en": "Thoughts of self-harm require immediate support and a safety assessment.",
        "action_ar": "إذا كان الخطر مباشراً فلا تبقَ وحيداً وتواصل مع خدمات الطوارئ أو جهة دعم مناسبة فورًا.",
        "action_en": "If danger is immediate, do not stay alone and contact emergency services or an appropriate crisis service now.",
        "url": "https://www.who.int/news-room/questions-and-answers/item/suicide"},
    "severe-breathing": {
        "description_ar": "صعوبة التنفس الشديدة، مثل اللهاث أو عدم القدرة على إخراج الكلمات، تحتاج رعاية طارئة.",
        "description_en": "Severe breathing difficulty, such as gasping or being unable to get words out, needs emergency care.",
        "action_ar": "تواصل مع خدمات الطوارئ المناسبة فورًا.", "action_en": "Contact the appropriate emergency service immediately.",
        "url": "https://www.nhs.uk/symptoms/shortness-of-breath/"},
    "chest-review": {
        "description_ar": "ألم الصدر يحتاج إلى تقييم طبي لتحديد درجة الاستعجال حتى عند غياب علامات إضافية.",
        "description_en": "Chest pain needs medical assessment to determine urgency even when other warning signs are absent.",
        "action_ar": "اطلب تقييمًا طبيًا، واطلب الطوارئ فورًا إذا كان الألم مفاجئًا أو مستمراً أو ترافق مع ضيق تنفس أو دوار.",
        "action_en": "Seek medical assessment; obtain emergency help if pain is sudden, persistent, or accompanied by breathlessness or light-headedness.",
        "url": "https://www.nhs.uk/symptoms/chest-pain/"},
}


# Aliases retired because they represented a different symptom and could cause
# one user phrase to normalize into two distinct clinical concepts. This is
# also an idempotent migration for databases seeded by older releases.
SYMPTOM_ALIAS_REMOVALS = {
    "dehydration": {
        "ar": ["قلة البول", "قله البول", "جفاف الفم"],
        "en": ["dry mouth", "reduced urination"],
    },
    "neck-pain": {
        "ar": ["تيبس الرقبه", "تيبس الرقبة"],
        "en": ["stiff neck", "neck stiffness"],
    },
    "runny-nose": {
        "ar": ["انسداد الانف", "احتقان الانف"],
        "en": ["stuffy nose", "blocked nose", "nasal congestion"],
    },
    "one-sided-weakness": {
        "ar": ["تنميل في جانب", "خدر في جانب", "تنميل مفاجئ في جانب"],
        "en": ["one sided numbness"],
    },
    "chills": {
        "ar": ["رعشه", "رجفه"],
        "en": [],
    },
    # V65: these aliases now belong to the dedicated lower-back-pain concept.
    # Remove them from existing production rows for the broader back-pain concept
    # so one phrase cannot resolve to two different symptoms.
    "back-pain": {
        "ar": ["الم اسفل الظهر", "ألم أسفل الظهر"],
        "en": ["lower back pain"],
    },
    # V76: keep generic mouth pain separate from the dedicated tongue-soreness concept.
    "mouth-pain": {
        "ar": ["لساني يوجع"],
        "en": ["sore tongue"],
    },
    # V76: colloquial heavy-sweating wording belongs to the more specific
    # excessive-sweating concept rather than the generic sweating concept.
    "sweating": {
        "ar": ["عرق كثير"],
        "en": [],
    },
}

RED_RULE_DETAILS.update(EXTRA_RED_RULE_DETAILS_V2)
RED_RULE_DETAILS.update(EXTRA_RED_RULE_DETAILS_V3)
RED_RULE_DETAILS.update(EXTRA_RED_RULE_DETAILS_V4)
RED_RULE_DETAILS.update(EXTRA_RED_RULE_DETAILS_V5)
RED_RULE_DETAILS.update(EXTRA_RED_RULE_DETAILS_V6)
RED_RULE_DETAILS.update(EXTRA_RED_RULE_DETAILS_V7)
RED_RULE_DETAILS.update(EXTRA_RED_RULE_DETAILS_V8)
RED_RULE_DETAILS.update(EXTRA_RED_RULE_DETAILS_V9)

# Canonical-concept migration for releases that briefly seeded overlapping
# symptom slugs.  We preserve any historical relationships/sources by moving
# them to the established canonical concept, then retire the duplicate slug.
# This keeps production databases clean without deleting audit history.
SYMPTOM_CANONICAL_MIGRATIONS = {
    "blocked-nose": "nasal-congestion",
    "facial-pressure": "sinus-pressure",
    "hard-stools": "constipation",
    "swallowing-difficulty": "difficulty-swallowing",
    "hoarse-voice": "hoarseness",
    # V76: V74 briefly reintroduced a singular duplicate of the established
    # mouth-ulcers concept. Merge any deployed copy into the canonical row.
    "mouth-ulcer": "mouth-ulcers",
}

def _remove_retired_aliases(values, slug, language):
    retired = {
        _normalize_text(v) for v in (SYMPTOM_ALIAS_REMOVALS.get(slug, {}).get(language, []) or [])
        if _normalize_text(v)
    }
    return [v for v in (values or []) if _normalize_text(v) not in retired]

def _seed(c):

    now = _now()
    # V177: every public health page carries a Saudi-local care-navigation
    # reference in addition to its condition-specific global source. This
    # does NOT claim MOH 937 is condition-specific evidence; it documents
    # the local consultation/escalation pathway used by the UI.
    _moh937 = (
        "saudi-moh-937",
        "وزارة الصحة السعودية — 937",
        "Saudi Ministry of Health",
        "https://www.moh.gov.sa/937/pages/default.aspx",
        "government",
        9,
        "مرجع محلي رسمي للاستشارة الصحية وتوجيه المستخدم إلى مسار الرعاية المناسب عبر خدمات 937.",
        "Official Saudi local reference for health consultation and care navigation through MOH 937 services.",
    )
    if not any(row[0] == _moh937[0] for row in SOURCES):
        SOURCES.append(_moh937)
    for slug, ar, en in CATEGORIES:
        c.execute(f"INSERT INTO mk_categories (slug,name_ar,name_en,status,created_at,updated_at) VALUES ({db.PH},{db.PH},{db.PH},'active',{db.PH},{db.PH}) ON CONFLICT(slug) DO NOTHING", (slug, ar, en, now, now))
    for slug, name, org, url, typ, priority, description_ar, description_en in SOURCES:
        c.execute(f"INSERT INTO mk_sources (slug,source_name,organization,official_url,description_ar,description_en,language,source_type,reliability_level,verification_status,last_verified,status,priority,version,created_at,updated_at) VALUES ({','.join([db.PH]*16)}) ON CONFLICT(slug) DO NOTHING",
                  (slug,name,org,url,description_ar,description_en,"multiple",typ,"high","verified",now[:10],"active",priority,1,now,now))
        # Upgrade only the old generic seed copy. Preserve descriptions edited
        # by an administrator in an existing production database.
        c.execute(
            f"UPDATE mk_sources SET description_ar={db.PH},description_en={db.PH},updated_at={db.PH} "
            f"WHERE slug={db.PH} AND (TRIM(COALESCE(description_ar,'')) IN ('','مصدر طبي رسمي موثوق.') "
            f"OR TRIM(COALESCE(description_en,'')) IN ('','Official trusted medical source.'))",
            (description_ar, description_en, now, slug),
        )
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
            existing_ar = _remove_retired_aliases(_json(current_aliases[0], []), slug, "ar")
            existing_en = _remove_retired_aliases(_json(current_aliases[1], []), slug, "en")
            merged_ar = list(dict.fromkeys(existing_ar + list(aliases_ar)))
            merged_en = list(dict.fromkeys(existing_en + list(aliases_en)))
            c.execute(f"UPDATE mk_symptoms SET aliases_ar={db.PH},aliases_en={db.PH} WHERE slug={db.PH}", (_dump(merged_ar), _dump(merged_en), slug))
        # Backfill categories that were introduced by later expansion packs.
        # Only fill NULL values so an administrator's explicit category choice is preserved.
        category_id = cats.get(cat)
        if category_id is not None:
            c.execute(
                f"UPDATE mk_symptoms SET category_id={db.PH},updated_at={db.PH} WHERE slug={db.PH} AND category_id IS NULL",
                (category_id, now, slug),
            )

    # Merge stale duplicate concepts created by older expansion packs. This is
    # intentionally idempotent and works on both SQLite and PostgreSQL.
    for old_slug, canonical_slug in SYMPTOM_CANONICAL_MIGRATIONS.items():
        c.execute(f"SELECT id FROM mk_symptoms WHERE slug={db.PH}", (old_slug,))
        old_row = c.fetchone()
        c.execute(f"SELECT id FROM mk_symptoms WHERE slug={db.PH}", (canonical_slug,))
        canonical_row = c.fetchone()
        if not old_row or not canonical_row:
            continue
        old_id, canonical_id = int(old_row[0]), int(canonical_row[0])
        if old_id == canonical_id:
            continue
        c.execute(f"SELECT disease_id,weight,typicality,notes_ar,notes_en,status FROM mk_disease_symptoms WHERE symptom_id={db.PH}", (old_id,))
        for disease_id, weight, typicality, notes_ar, notes_en, rel_status in c.fetchall():
            c.execute(f"SELECT id,weight FROM mk_disease_symptoms WHERE disease_id={db.PH} AND symptom_id={db.PH}", (disease_id, canonical_id))
            existing = c.fetchone()
            if existing:
                if float(weight or 0) > float(existing[1] or 0):
                    c.execute(f"UPDATE mk_disease_symptoms SET weight={db.PH},typicality={db.PH},notes_ar={db.PH},notes_en={db.PH},status={db.PH},updated_at={db.PH} WHERE id={db.PH}",
                              (float(weight or 0), typicality, notes_ar or '', notes_en or '', rel_status or 'active', now, int(existing[0])))
            else:
                c.execute(f"INSERT INTO mk_disease_symptoms (disease_id,symptom_id,weight,typicality,notes_ar,notes_en,status,created_at,updated_at) VALUES ({','.join([db.PH]*9)})",
                          (disease_id, canonical_id, float(weight or 0), typicality, notes_ar or '', notes_en or '', rel_status or 'active', now, now))
        c.execute(f"SELECT source_id,reference_title_ar,reference_title_en,reference_url,last_verified,status FROM mk_symptom_sources WHERE symptom_id={db.PH}", (old_id,))
        for source_id, title_ar, title_en, ref_url, last_verified, src_status in c.fetchall():
            c.execute(f"SELECT id FROM mk_symptom_sources WHERE symptom_id={db.PH} AND source_id={db.PH}", (canonical_id, source_id))
            if not c.fetchone():
                c.execute(f"INSERT INTO mk_symptom_sources (symptom_id,source_id,reference_title_ar,reference_title_en,reference_url,last_verified,status,created_at,updated_at) VALUES ({','.join([db.PH]*9)})",
                          (canonical_id, source_id, title_ar or '', title_en or '', ref_url or '', last_verified or now[:10], src_status or 'active', now, now))
        c.execute(f"UPDATE mk_disease_symptoms SET status='inactive',updated_at={db.PH} WHERE symptom_id={db.PH}", (now, old_id))
        c.execute(f"UPDATE mk_symptom_sources SET status='inactive',updated_at={db.PH} WHERE symptom_id={db.PH}", (now, old_id))
        c.execute(f"UPDATE mk_symptoms SET status='inactive',updated_at={db.PH} WHERE id={db.PH}", (now, old_id))

    c.execute("SELECT id,slug FROM mk_symptoms")
    symptoms = {slug:int(i) for i,slug in c.fetchall()}
    for disease in DISEASES:
        c.execute(f"INSERT INTO mk_diseases (slug,name_ar,name_en,description_ar,description_en,category_id,severity,risk_factors_ar,risk_factors_en,common_causes_ar,common_causes_en,red_flags_ar,red_flags_en,related_diseases,recommended_next_step_ar,recommended_next_step_en,last_updated,status,version,created_at,updated_at) VALUES ({','.join([db.PH]*21)}) ON CONFLICT(slug) DO NOTHING",
                  (disease['slug'],disease['name_ar'],disease['name_en'],disease['description_ar'],disease['description_en'],cats.get(disease['category']),disease['severity'],disease['risk_ar'],disease['risk_en'],disease['causes_ar'],disease['causes_en'],disease['red_ar'],disease['red_en'],"[]",disease['next_ar'],disease['next_en'],now[:10],"active",1,now,now))
        category_id = cats.get(disease.get('category'))
        if category_id is not None:
            c.execute(
                f"UPDATE mk_diseases SET category_id={db.PH},updated_at={db.PH} WHERE slug={db.PH} AND category_id IS NULL",
                (category_id, now, disease['slug']),
            )
    # Idempotent eligibility backfill for existing and newly seeded rows.
    for slug, meta in DISEASE_ELIGIBILITY.items():
        c.execute(
            f"UPDATE mk_diseases SET sex_applicability={db.PH},pregnancy_relevant={db.PH},updated_at={db.PH} WHERE slug={db.PH}",
            (meta.get("sex_applicability", "any"), 1 if meta.get("pregnancy_relevant") else 0, now, slug),
        )
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
        # A red-flag symptom may intentionally have no disease relationship
        # (for example severe bleeding or thoughts of self-harm). Link the
        # reviewed safety reference directly to that symptom so Health Search
        # and the symptom library never show an unsourced safety concept.
        _rule_source_id = sources.get(source_slug)
        _rule_url = meta.get("url", "")
        if _rule_source_id and _rule_url:
            for _required_slug in (req or []):
                _required_sid = symptoms.get(_required_slug)
                if not _required_sid:
                    continue
                c.execute(
                    f"INSERT INTO mk_symptom_sources (symptom_id,source_id,reference_title_ar,reference_title_en,reference_url,last_verified,status,created_at,updated_at) VALUES ({','.join([db.PH]*9)}) ON CONFLICT(symptom_id,source_id) DO NOTHING",
                    (_required_sid,_rule_source_id,ar,en,_rule_url,now[:10],"active",now,now),
                )

    # V177: attach the Saudi MOH 937 *care-navigation* reference to every
    # active disease and symptom. Each entity already retains its own
    # condition-specific global references; this link supplies the local
    # Saudi escalation/consultation source required by the public quality
    # policy without pretending 937 is evidence for the medical description.
    _local_source_id = sources.get("saudi-moh-937")
    _local_url = "https://www.moh.gov.sa/937/pages/default.aspx"
    if _local_source_id:
        _title_ar = "خدمات 937 — مرجع محلي للاستشارة ومسار الرعاية"
        _title_en = "MOH 937 — local consultation and care-navigation reference"
        c.execute("SELECT id FROM mk_diseases WHERE status='active'")
        for (_entity_id,) in c.fetchall():
            c.execute(
                f"INSERT INTO mk_disease_sources (disease_id,source_id,reference_title_ar,reference_title_en,reference_url,last_verified,status,created_at,updated_at) VALUES ({','.join([db.PH]*9)}) ON CONFLICT(disease_id,source_id) DO NOTHING",
                (int(_entity_id),_local_source_id,_title_ar,_title_en,_local_url,now[:10],"active",now,now),
            )
        c.execute("SELECT id FROM mk_symptoms WHERE status='active'")
        for (_entity_id,) in c.fetchall():
            c.execute(
                f"INSERT INTO mk_symptom_sources (symptom_id,source_id,reference_title_ar,reference_title_en,reference_url,last_verified,status,created_at,updated_at) VALUES ({','.join([db.PH]*9)}) ON CONFLICT(symptom_id,source_id) DO NOTHING",
                (int(_entity_id),_local_source_id,_title_ar,_title_en,_local_url,now[:10],"active",now,now),
            )


def _normalize_text(value):
    text = unicodedata.normalize("NFKC", str(value or "")).lower()
    text = re.sub(r"[\u064b-\u065f\u0670]", "", text)
    text = text.translate(str.maketrans({"أ":"ا","إ":"ا","آ":"ا","ى":"ي","ة":"ه","ؤ":"و","ئ":"ي"}))
    text = re.sub(r"[^a-z0-9\u0600-\u06ff\s-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _fetch_symptoms(active_only=True, conn=None):
    init_schema()
    owns_conn = conn is None
    conn = conn or db._conn()
    try:
        c = conn.cursor()
        sql = "SELECT id,slug,name_ar,name_en,description_ar,description_en,category_id,severity_min,severity_max,aliases_ar,aliases_en,red_flags_ar,red_flags_en,status,version,created_at,updated_at FROM mk_symptoms"
        if active_only:
            sql += " WHERE status='active'"
        c.execute(sql + " ORDER BY name_en")
        rows = c.fetchall()
    finally:
        if owns_conn:
            conn.close()
    keys = ["id","slug","name_ar","name_en","description_ar","description_en","category_id","severity_min","severity_max","aliases_ar","aliases_en","red_flags_ar","red_flags_en","status","version","created_at","updated_at"]
    out = []
    for row in rows:
        item = dict(zip(keys,row)); item["aliases_ar"]=_json(item["aliases_ar"],[]); item["aliases_en"]=_json(item["aliases_en"],[]); out.append(item)
    return out


def _light_stem(text):
    """Strip a single leading Arabic proclitic (و ف ب ل ك) from each word of
    length >= 3, e.g. "وتوتر" -> "توتر", "بقلق" -> "قلق". This is a
    conservative, widely-used light-stemming step used only to help match
    free-text phrasing against the symptom dictionary; it never changes what
    is stored or displayed.
    """
    words = text.split(" ")
    out = []
    for w in words:
        if len(w) >= 3 and w[0] in "وفبلك":
            out.append(w[1:])
        else:
            out.append(w)
    return " ".join(out)


# Natural-language aliases shared by symptom analysis and the broader health-search
# vocabulary.  Keep these here (rather than substring matching in the web layer) so
# all analysis paths use the same phrase-boundary logic and cannot re-introduce
# matches such as ``fit`` inside ``benefit``.
SYMPTOM_ALIAS_EXTENSIONS = {
    "constipation": ["الإمساك", "براز قاسي", "ما اقدر اتبرز", "hard stools", "difficulty passing stool", "constipated"],
    "bloating": ["بطني منفوخ", "نفخة البطن", "انتفاخ بعد الاكل", "trapped wind", "bloated stomach", "bloating after eating"],
    "heartburn": ["حرقة بعد الاكل", "طعم حامض بالفم", "heartburn after eating", "acid reflux after eating", "sour taste in mouth"],
    "diarrhea": ["الإسهال", "اسهال وترجيع", "إسهال وقيء", "watery stools", "diarrhea", "diarrhoea and vomiting"],
    "hair-loss": ["شعري يتساقط", "شعري يطيح", "شعري يتساقط كثير", "فراغات الشعر", "hair shedding", "my hair is falling out", "thinning hair"],
    "menstrual-cramps": ["دورتي توجعني", "painful periods", "period cramps"],
    "palpitations": ["قلبي يدق بسرعة", "دقات قلبي سريعة", "خفقان بعد القهوة", "نبضي سريع", "racing heartbeat", "heart fluttering", "palpitations after coffee"],
    "numbness": ["تنميل بعد النوم", "pins and needles after sleeping"],
    "hand-numbness": ["يدي تنمل", "tingling hands"],
    "foot-numbness": ["numb feet"],
    "back-pain": ["ظهري يوجعني", "وجع الظهر", "my back hurts", "backache"],
    "neck-pain": ["رقبتي توجعني", "شد الرقبة", "وجع الرقبة", "my neck hurts"],
    "tooth-pain": ["ضرس يوجعني", "ضرسي يوجعني", "وجع الاسنان", "tooth pain", "my tooth hurts", "dental pain"],
    "ear-pain": ["اذني توجعني", "وجع الاذن", "الم الاذنين", "my ear hurts", "aching ear"],
    "tinnitus": ["صفير الاذن", "اذني تصفر", "ازيز الاذن", "buzzing in ears", "ear ringing"],
    "insomnia": ["الأرق", "صعوبة النوم", "نومي متقطع", "اصحى كثير بالليل", "cannot sleep", "waking at night"],
    "increased-thirst": ["العطش الزائد", "عطشان طول الوقت", "عطش مستمر", "اشرب كثير ولسى عطشان", "كثرة العطش", "always thirsty", "constant thirst", "thirsty all the time"],
    "painful-urination": ["حرقة البول", "حرقان البول", "ألم عند التبول", "burning urination", "pain when peeing", "painful urination"],
    "frequent-urination": ["كثرة التبول", "اتبول كثير", "frequent urination"],
    "hives": ["الشرى", "الارتيكاريا", "طفح مرتفع وحكة", "شرى", "raised itchy rash", "nettle rash"],
}


def _aliases_for_symptom(item):
    """Return one de-duplicated alias list for every symptom matching surface."""
    aliases = [item["name_ar"], item["name_en"], item["slug"], item["slug"].replace("-", " ")]
    aliases += list(item.get("aliases_ar") or []) + list(item.get("aliases_en") or [])
    aliases += list(SYMPTOM_ALIAS_EXTENSIONS.get(item.get("slug"), []))
    out, seen = [], set()
    for value in aliases:
        norm = _normalize_text(value)
        if norm and norm not in seen:
            seen.add(norm)
            out.append(value)
    return out


def normalize_symptoms(raw_symptoms, lang="ar", conn=None):
    symptoms = _fetch_symptoms(True, conn=conn)
    candidates = []
    for item in symptoms:
        aliases = _aliases_for_symptom(item)
        for alias in aliases:
            norm = _normalize_text(alias)
            if norm:
                candidates.append((len(norm), norm, item))
    candidates.sort(key=lambda x: x[0], reverse=True)
    found, unmatched, negated, seen = [], [], [], set()
    for original in raw_symptoms or []:
        original_s = str(original)
        text = clinical_text.normalize_clinical_text(original_s)
        text_loose = _light_stem(text)
        local = []
        local_negated = []
        for _, alias, item in candidates:
            if item["id"] in seen:
                continue
            direct = (alias == text or alias == text_loose)
            matched = direct or clinical_text.contains_phrase(text, alias) or clinical_text.contains_phrase(text_loose, alias)
            if not matched:
                continue
            # Direct equality still needs a negation check because phrases such as
            # "no chest pain" contain the alias but assert its absence.
            # Never let stemming erase a negation seen in the original text.
            semantic_text = text if clinical_text.contains_phrase(text, alias) else text_loose
            positive = clinical_text.contains_unnegated_phrase(semantic_text, alias)
            if positive:
                local.append((alias, item))
            else:
                local_negated.append((alias, item))
        if not local and text and not clinical_text.has_negation_cue(text):
            best = None
            # SequenceMatcher.ratio() is comparatively expensive across the full
            # alias catalog. real_quick_ratio()/quick_ratio() are guaranteed
            # upper bounds, so rejecting a candidate below the same .86 cutoff
            # cannot change which fuzzy match would have been accepted.
            matcher = difflib.SequenceMatcher(None, text, "")
            for _, alias, item in candidates:
                matcher.set_seq2(alias)
                if matcher.real_quick_ratio() < .86 or matcher.quick_ratio() < .86:
                    continue
                ratio = matcher.ratio()
                if ratio >= .86 and (best is None or ratio > best[0]):
                    best = (ratio,alias,item)
            if best:
                local = [(best[1],best[2])]
        if local and len(local) > 1:
            # Prefer a longer exact phrase over a generic word contained inside
            # it for the same user phrase (e.g. Arabic "حبة حرارة على الشفايف"
            # should map to a cold-sore blister, not also to generic fever).
            # Independent symptoms such as "fever and cough" remain because
            # neither matched alias contains the other.
            pruned = []
            for alias, item in local:
                if any(alias != other_alias and alias in other_alias and len(other_alias) > len(alias)
                       for other_alias, _other_item in local):
                    continue
                pruned.append((alias, item))
            local = pruned or local

            # Prefer the most specific alias inside a hierarchy for this single
            # user phrase. Example: "one sided numbness" should not also emit
            # the generic "numbness" concept. Unrelated symptoms in the same
            # sentence are preserved because they have different groups.
            grouped = {}
            for alias, item in local:
                slug = str(item.get("slug") or "")
                group = _SYMPTOM_CONCEPT_GROUPS.get(slug, "symptom:" + slug)
                current = grouped.get(group)
                if current is None or len(alias) > len(current[0]):
                    grouped[group] = (alias, item)
            local = list(grouped.values())
        if not local:
            unmatched.append(original_s)
        for alias,item in local_negated:
            rec={"symptom_id":item["id"],"slug":item["slug"],"name_ar":item["name_ar"],"name_en":item["name_en"],"original":original_s,"matched_alias":alias}
            if not any(x["symptom_id"] == item["id"] and x["original"] == original_s for x in negated):
                negated.append(rec)
        for alias,item in local:
            if item["id"] in seen:
                continue
            seen.add(item["id"])
            found.append({"symptom_id":item["id"],"slug":item["slug"],"name_ar":item["name_ar"],"name_en":item["name_en"],"original":original_s,"matched_alias":alias})
    return {"canonical":found,"unmatched":unmatched,"negated":negated}


def suggest_similar_symptoms(text, lang="ar", limit=3, conn=None):
    """Return up to `limit` known symptoms whose name/aliases are closest to
    free-text `text` that did not match anything in normalize_symptoms().

    This is a soft "did you mean" convenience only: it never blocks analysis
    and never auto-selects anything on its own. A lower similarity floor than
    normalize_symptoms() is used on purpose, since here we want plausible
    nearby options for the user to pick from, not an automatic match.
    """
    text_norm = _normalize_text(text)
    if not text_norm:
        return []
    text_loose = _light_stem(text_norm)
    symptoms = _fetch_symptoms(True, conn=conn)
    scored = {}
    for item in symptoms:
        display = item["name_ar"] if lang == "ar" else item["name_en"]
        if not display:
            continue
        aliases = _aliases_for_symptom(item)
        best_ratio = 0.0
        for alias in aliases:
            alias_norm = _normalize_text(alias)
            if not alias_norm:
                continue
            ratio = max(
                difflib.SequenceMatcher(None, text_norm, alias_norm).ratio(),
                difflib.SequenceMatcher(None, text_loose, alias_norm).ratio(),
            )
            if alias_norm in text_norm or text_norm in alias_norm or alias_norm in text_loose:
                ratio = max(ratio, 0.6)
            if ratio > best_ratio:
                best_ratio = ratio
        if best_ratio >= 0.4:
            prev = scored.get(item["id"])
            if prev is None or best_ratio > prev[0]:
                scored[item["id"]] = (best_ratio, display, item["slug"])
    ranked = sorted(scored.values(), key=lambda x: x[0], reverse=True)[:limit]
    return [{"label": label, "slug": slug} for _ratio, label, slug in ranked]


def _source_rows_for_disease(c, disease_id):
    c.execute(f"""SELECT s.id,s.slug,s.source_name,s.organization,s.official_url,s.source_type,s.reliability_level,s.verification_status,s.last_verified,s.priority,
                         ds.reference_title_ar,ds.reference_title_en,ds.reference_url,ds.last_verified
                  FROM mk_disease_sources ds JOIN mk_sources s ON s.id=ds.source_id
                  WHERE ds.disease_id={db.PH} AND ds.status='active' AND s.status='active' AND s.verification_status='verified'
                  ORDER BY CASE WHEN s.slug='saudi-moh-937' THEN 1 ELSE 0 END, s.priority, s.source_name""", (int(disease_id),))
    keys=["id","slug","source_name","organization","official_url","source_type","reliability_level","verification_status","source_last_verified","priority","reference_title_ar","reference_title_en","reference_url","last_verified"]
    rows = [dict(zip(keys,r)) for r in c.fetchall()]
    # V251: references added by the multi-source pass are supplementary; the originally curated source stays
    # the primary one used for explanations (stable sort keeps priority order inside each group).
    supplementary = _supplementary_urls()
    rows.sort(key=lambda r: (r["slug"] == "saudi-moh-937", (r.get("reference_url") or "") in supplementary))
    return rows


def _supplementary_urls():
    try:
        return _SUPPLEMENTARY_URLS
    except NameError:
        return frozenset()



# Symptoms in the same concept group may be alternative labels or clinically
# overlapping concepts. They can all remain visible for clarification, but they
# must never increase a disease score more than once for one user phrase.
_SYMPTOM_CONCEPT_GROUPS = {
    # A one-sided numbness phrase can also match the generic word "numbness".
    # Keep only that hierarchy grouped; weakness vs numbness, chills vs tremor,
    # and congestion vs runny nose remain independent clinical findings.
    "one-sided-numbness": "numbness_hierarchy",
    "numbness": "numbness_hierarchy",
    "vaginal-itching": "itching_hierarchy",
    "itching": "itching_hierarchy",
}

def _dedupe_matched_by_concept(matched, ids):
    """Keep only the highest-weight disease relation per overlapping concept."""
    best = {}
    for rel in matched:
        sid = int(rel[0])
        slug = str((ids.get(sid) or {}).get("slug") or sid)
        group = _SYMPTOM_CONCEPT_GROUPS.get(slug, "symptom:" + slug)
        if group not in best or float(rel[1] or 0) > float(best[group][1] or 0):
            best[group] = rel
    return list(best.values())

def match_diseases(canonical, lang="ar", limit=5, negatives=None, conn=None, pattern_bonuses=None, gender="", age=None):
    init_schema()
    ids = {int(x["symptom_id"]):x for x in canonical or []}
    if not ids:
        return []
    negative_slugs = {str(x).strip() for x in (negatives or []) if str(x).strip()}
    owns_conn = conn is None
    conn = conn or db._conn()
    try:
        c = conn.cursor()
        neg_ids = set()
        if negative_slugs:
            c.execute("SELECT id,slug FROM mk_symptoms WHERE status='active'")
            neg_ids = {int(row[0]) for row in c.fetchall() if str(row[1]) in negative_slugs}
        c.execute("SELECT id,slug,name_ar,name_en,description_ar,description_en,severity,red_flags_ar,red_flags_en,recommended_next_step_ar,recommended_next_step_en,last_updated,sex_applicability,min_age,max_age,pregnancy_relevant FROM mk_diseases WHERE status='active'")
        diseases = c.fetchall()
        out=[]
        for row in diseases:
            if not _condition_is_eligible(sex_applicability=row[12], gender=gender, age=age, canonical=canonical):
                continue
            parsed_age = clinical_text.parse_age_years(age)
            if parsed_age is not None and ((row[13] is not None and parsed_age < int(row[13])) or (row[14] is not None and parsed_age > int(row[14]))):
                continue
            did=int(row[0])
            c.execute(f"SELECT symptom_id,weight,typicality,notes_ar,notes_en FROM mk_disease_symptoms WHERE disease_id={db.PH} AND status='active'",(did,))
            rels=c.fetchall()
            total=sum(max(float(r[1] or 0),0) for r in rels) or 1
            matched=[r for r in rels if int(r[0]) in ids]
            matched=_dedupe_matched_by_concept(matched, ids)
            if not matched:
                continue
            coverage=sum(float(r[1] or 0) for r in matched)/total
            max_weight=max((float(r[1] or 0) for r in rels), default=0) or 1
            avg_matched_weight=sum(float(r[1] or 0) for r in matched)/max(len(matched),1)
            specificity=min(avg_matched_weight/max_weight,1.0)
            base_score=.75*coverage+.25*specificity

            # Explicitly denied follow-up symptoms are negative evidence.  This is
            # especially important for broad digestive conditions: nausea alone
            # should not keep food poisoning high after vomiting/diarrhea were
            # denied.  Penalty is proportional to both the total denied disease
            # weight and whether a hallmark (high-weight) symptom was denied.
            neg_rels=[r for r in rels if int(r[0]) in neg_ids]
            neg_weight=sum(float(r[1] or 0) for r in neg_rels)
            neg_ratio=min(neg_weight/total,1.0)
            max_neg=max((float(r[1] or 0) for r in neg_rels), default=0.0)
            hallmark_neg=min(max_neg/max_weight,1.0) if max_weight else 0.0
            score=max(0.0, base_score - (0.85*neg_ratio) - (0.22*hallmark_neg))

            # V51 multi-symptom interaction support. A pattern can only add a
            # small bounded bonus when this disease already has >=2 independently
            # matched symptoms. It can never create a match or affect triage.
            pattern_bonus = 0.0
            if len(matched) >= 2 and pattern_bonuses:
                try:
                    pattern_bonus = max(0.0, min(float(pattern_bonuses.get(str(row[1]), 0.0) or 0.0), 0.18))
                except (TypeError, ValueError):
                    pattern_bonus = 0.0
                score = min(1.0, score + pattern_bonus)

            # Do not surface extremely weak residual matches merely because one
            # nonspecific symptom overlaps.
            if score < .16:
                continue
            if score>=.63 and len(matched)>=2:
                level="strong"
            elif score>=.34 and len(matched)>=2:
                level="moderate"
            elif score>=.46:
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
            out.append({"disease_id":did,"slug":row[1],"name_ar":row[2],"name_en":row[3],"description":row[4] if lang=="ar" else row[5],"severity":row[6],"red_flags":row[7] if lang=="ar" else row[8],"recommended_next_step":row[9] if lang=="ar" else row[10],"last_updated":row[11],"sex_applicability":row[12] or "any","min_age":row[13],"max_age":row[14],"pregnancy_relevant":bool(row[15]),"match_level":level,"matched_symptoms":matched_symptoms,"negative_evidence":sorted(negative_slugs),"pattern_bonus":round(pattern_bonus,4),"sources":sources,"explanation_source":sources[0],"_score":score})
        out.sort(key=lambda x:(x["_score"],len(x["matched_symptoms"])),reverse=True)
        for item in out:
            item.pop("_score",None)
        return out[:max(1,min(int(limit),10))]
    finally:
        if owns_conn:
            conn.close()


FEMALE_ONLY_DISEASE_SLUGS = {
    "period-pain", "endometriosis-pattern", "polycystic-ovary-syndrome-pattern",
    "premenstrual-syndrome-pattern", "heavy-menstrual-bleeding-pattern",
    "irregular-periods-pattern", "vaginal-thrush-pattern",
    "bacterial-vaginosis-pattern", "perimenopause-symptom-pattern",
    "missed-late-period-pattern", "vaginal-dryness-pattern",
    "breast-pain-pattern",
}
# The current verified knowledge set does not yet contain a prostate/testicular
# disease row. Keep this explicit rather than inventing one without review.
MALE_ONLY_DISEASE_SLUGS = set()
FEMALE_ONLY_SYMPTOM_SLUGS = {
    "premenstrual-pattern", "menstrual-cramps", "heavy-periods",
    "irregular-periods", "vaginal-itching", "vaginal-discharge",
    "vaginal-odor", "vaginal-dryness", "missed-period",
}
MALE_ONLY_SYMPTOM_SLUGS = {"testicular-pain", "testicular-swelling", "prostate-pain"}

# Reviewed eligibility metadata. New rows default to 'any' and must be added to
# MEDICAL_REVIEW_NEEDED.md before a stricter rule is introduced.
DISEASE_ELIGIBILITY = {
    **{slug: {"sex_applicability": "female_only", "pregnancy_relevant": False}
       for slug in FEMALE_ONLY_DISEASE_SLUGS},
    **{slug: {"sex_applicability": "male_only", "pregnancy_relevant": False}
       for slug in MALE_ONLY_DISEASE_SLUGS},
}

def _normalized_binary_sex(value):
    raw = str(value or "").strip().lower()
    if raw in {"m", "male", "ذكر"}:
        return "m"
    if raw in {"f", "female", "أنثى", "انثى"}:
        return "f"
    return ""

def _inferred_sex_from_symptoms(canonical):
    slugs = {str(x.get("slug") or "") for x in (canonical or [])}
    if slugs & FEMALE_ONLY_SYMPTOM_SLUGS:
        return "f"
    if slugs & MALE_ONLY_SYMPTOM_SLUGS:
        return "m"
    return ""

def _condition_is_eligible(*, sex_applicability="any", gender="", age=None, canonical=None):
    sex = _normalized_binary_sex(gender) or _inferred_sex_from_symptoms(canonical)
    applicability = str(sex_applicability or "any").strip().lower()
    if applicability == "female_only" and sex != "f":
        return False
    if applicability == "male_only" and sex != "m":
        return False
    # Only explicit biological/impossibility bounds are hard filters. Ordinary
    # age associations belong in scoring, not eligibility.
    parsed_age = clinical_text.parse_age_years(age)
    if parsed_age is not None:
        # Bounds are read from the caller through metadata-specific checks in
        # match_diseases; this helper intentionally keeps age neutral otherwise.
        pass
    return True

def _filter_matches_for_sex(matches, gender, canonical=None):
    """Defense-in-depth only; source-of-truth filtering occurs pre-score."""
    return [m for m in (matches or []) if _condition_is_eligible(
        sex_applicability=m.get("sex_applicability", "any"), gender=gender, canonical=canonical
    )]


def differential_question(raw_symptoms, asked=None, negatives=None, gender="", lang="ar"):
    """Return one high-value follow-up question and a re-ranked differential.

    Positive answers add evidence; negative answers reduce the relevance of
    diseases that normally include that symptom. The result remains qualitative
    and is never presented as a confirmed diagnosis.
    """
    asked = {str(x) for x in (asked or []) if x}
    negatives = {str(x) for x in (negatives or []) if x}
    max_questions = 5
    canonical_info = normalize_symptoms(raw_symptoms or [], lang)
    canonical = canonical_info.get("canonical") or []
    current_slugs = {x.get("slug") for x in canonical if x.get("slug")}
    sex = _normalized_binary_sex(gender)
    is_male = sex == "m"
    is_female = sex == "f"

    ranked_candidates = []
    inferred_sex = sex or _inferred_sex_from_symptoms(canonical)
    for disease in DISEASES:
        meta = DISEASE_ELIGIBILITY.get(disease.get("slug"), {})
        if not _condition_is_eligible(sex_applicability=meta.get("sex_applicability", "any"), gender=inferred_sex, canonical=canonical):
            continue
        rel = disease.get("symptoms") or {}
        # Score at most one symptom per overlapping concept group. This keeps a
        # single phrase such as "blocked nose" or "one-sided numbness" from
        # inflating the differential merely because normalization emitted sibling
        # canonical labels. The strongest disease-specific relation wins.
        concept_weights = {}
        for slug in current_slugs:
            weight = float(rel.get(slug, 0.0) or 0.0)
            if weight <= 0:
                continue
            group = _SYMPTOM_CONCEPT_GROUPS.get(slug, "symptom:" + slug)
            concept_weights[group] = max(concept_weights.get(group, 0.0), weight)
        positive_weights = list(concept_weights.values())
        if not positive_weights:
            continue
        total = sum(max(float(v), 0.0) for v in rel.values()) or 1.0
        pos = sum(positive_weights) / total
        max_weight = max((float(v) for v in rel.values()), default=0.0) or 1.0
        avg_matched_weight = sum(positive_weights) / max(len(positive_weights), 1)
        specificity = min(avg_matched_weight / max_weight, 1.0)
        neg_penalty = sum(float(rel.get(slug, 0.0)) for slug in negatives if rel.get(slug, 0.0) > 0) / total
        score = max(0.0, (0.75 * pos) + (0.25 * specificity) - (0.62 * neg_penalty))
        matched_count = len(positive_weights)
        if score >= .63 and matched_count >= 2:
            level = "strong"
        elif score >= .34:
            level = "moderate"
        else:
            level = "weak"
        ranked_candidates.append({
            "slug": disease["slug"],
            "name": disease["name_ar"] if lang == "ar" else disease["name_en"],
            "match_level": level,
            "matched_count": matched_count,
            "_score": score,
        })
    ranked_candidates.sort(key=lambda x: (x["_score"], x["matched_count"]), reverse=True)
    public_candidates = [{k:v for k,v in x.items() if k != "_score"} for x in ranked_candidates[:3]]
    # Even after the final allowed answer, return the newly re-ranked candidates
    # so the UI can explain the qualitative effect of that answer without
    # exposing diagnostic probabilities or private model scores.
    if len(asked) >= max_questions:
        return {
            "done": True, "candidates": public_candidates, "reason": "question_limit",
            "question_number": max_questions, "max_questions": max_questions,
        }
    if not ranked_candidates:
        return {"done": True, "candidates": public_candidates, "reason": "no_match", "question_number": len(asked), "max_questions": max_questions}

    top_score = ranked_candidates[0]["_score"]
    second_score = ranked_candidates[1]["_score"] if len(ranked_candidates) > 1 else 0.0
    top_count = ranked_candidates[0]["matched_count"]
    # Ask at least three discriminating questions before stopping for a clear lead.
    # This reduces premature conclusions from sparse symptom descriptions while
    # still capping the adaptive flow at five questions.
    if len(asked) >= 3 and top_count >= 3 and top_score >= .48 and (top_score - second_score) >= .12:
        return {"done": True, "candidates": public_candidates, "reason": "clear_lead", "question_number": len(asked), "max_questions": max_questions}

    disease_map = {d["slug"]: d for d in DISEASES}
    candidate_defs = [disease_map.get(m.get("slug")) for m in ranked_candidates[:4]]
    candidate_defs = [d for d in candidate_defs if d]
    symptom_meta = {row[0]: {"name_ar": row[1], "name_en": row[2]} for row in SYMPTOMS}
    pool = set()
    for d in candidate_defs:
        pool.update((d.get("symptoms") or {}).keys())
    pool -= current_slugs
    active_groups = {_SYMPTOM_CONCEPT_GROUPS.get(slug, "symptom:" + slug) for slug in current_slugs}
    pool = {slug for slug in pool if _SYMPTOM_CONCEPT_GROUPS.get(slug, "symptom:" + slug) not in active_groups}
    pool -= asked
    pool -= negatives
    unsafe_slugs = {
        "one-sided-weakness", "speech-difficulty", "face-drooping",
        "sudden-vision-loss", "loss-of-consciousness", "severe-bleeding",
        "suicidal-thoughts", "severe-headache",
    }
    pool -= unsafe_slugs
    if inferred_sex == "m":
        pool -= FEMALE_ONLY_SYMPTOM_SLUGS
    elif inferred_sex == "f":
        pool -= MALE_ONLY_SYMPTOM_SLUGS
    else:
        pool -= FEMALE_ONLY_SYMPTOM_SLUGS | MALE_ONLY_SYMPTOM_SLUGS
    if not pool:
        return {"done": True, "candidates": public_candidates, "reason": "questions_exhausted", "question_number": len(asked), "max_questions": max_questions}

    ranked_questions = []
    for slug in pool:
        weights = [float((d.get("symptoms") or {}).get(slug, 0.0)) for d in candidate_defs]
        top_weight = weights[0] if weights else 0.0
        spread = (max(weights) - min(weights)) if weights else 0.0
        represented = sum(1 for w in weights if w > 0)
        rarity_bonus = 0.20 if represented <= max(1, len(weights)//2) else 0.0
        score = top_weight * 1.20 + spread + rarity_bonus + max(weights or [0]) * 0.20
        ranked_questions.append((score, slug))
    ranked_questions.sort(reverse=True)
    slug = ranked_questions[0][1]
    meta = symptom_meta.get(slug) or {"name_ar": slug, "name_en": slug}
    name = meta["name_ar"] if lang == "ar" else meta["name_en"]
    question = (f"هل لديك أيضًا {name}؟" if lang == "ar" else f"Do you also have {name}?")
    return {
        "done": False,
        "question": question,
        "symptom_slug": slug,
        "symptom_name": name,
        "candidates": public_candidates,
        "question_number": min(len(asked) + 1, max_questions),
        "max_questions": max_questions,
        "question_reason": (
            "يساعد هذا السؤال على التفريق بين الاحتمالات الأقرب بناءً على إجاباتك، دون تشخيص."
            if lang == "ar" else
            "This question helps distinguish the closest possibilities from your answers without making a diagnosis."
        ),
    }


# Only these knowledge-base rules are ambulance/emergency bypasses by themselves.
# Other clinically urgent rules remain same-day/urgent medical review unless the
# deterministic safety engine sees a truly immediate red flag. This prevents
# common but important symptoms from being over-triaged as "call emergency now".
IMMEDIATE_EMERGENCY_RULES = {
    "severe-chest-pain", "sudden-one-sided-numbness", "sudden-one-sided-weakness",
    "sudden-facial-numbness", "chest-breathing", "stroke-combination", "face-droop",
    "sudden-vision", "severe-bleeding", "severe-head-neuro", "self-harm",
    "anaphylaxis-airway", "meningitis-pattern", "heat-stroke-pattern",
    # Their own messages already say "emergency help"; the level must match the text.
    "unconscious", "seizure-event",
}

def evaluate_risk(canonical, raw_symptoms=None, notes="", severity=1, age=None, lang="ar", conn=None):
    init_schema()
    slugs={x["slug"] for x in canonical or []}
    text=clinical_text.normalize_clinical_text(" ; ".join(str(x) for x in (raw_symptoms or []))+" ; "+str(notes or ""))
    try: severity=max(1,min(5,int(severity or 1)))
    except Exception: logging.getLogger(__name__).debug("Handled exception in evaluate_risk; fallback applied (handler 1215)"); severity=1
    age = clinical_text.parse_age_years(age)
    owns_conn = conn is None
    conn = conn or db._conn()
    try:
        c=conn.cursor(); c.execute("""SELECT rf.id,rf.slug,rf.name_ar,rf.name_en,rf.required_symptoms,rf.match_mode,rf.keywords_ar,rf.keywords_en,
                                      rf.min_severity,rf.risk_level,rf.message_ar,rf.message_en,rf.description_ar,rf.description_en,
                                      rf.recommended_action_ar,rf.recommended_action_en,rf.source_id,rf.reference_url,rf.last_updated,
                                      s.source_name,s.organization,s.official_url,s.verification_status,s.status
                               FROM mk_red_flags rf LEFT JOIN mk_sources s ON s.id=rf.source_id
                               WHERE rf.status='active'""")
        rows=c.fetchall()
    finally:
        if owns_conn:
            conn.close()
    hits=[]
    for r in rows:
        req=set(_json(r[4],[])); mode=r[5] or "all"; kws=_json(r[6],[])+_json(r[7],[]); min_sev=int(r[8] or 1)
        req_hit=bool(req) and (req.issubset(slugs) if mode=="all" else bool(req & slugs))
        kw_hit=clinical_text.contains_unnegated_any(text, kws)
        if severity>=min_sev and (req_hit or kw_hit):
            source = None
            if r[16] and r[19] and r[22] == "verified" and r[23] == "active":
                ref_url = r[17] if _url_is_trusted(r[17]) else r[21]
                source = {"id": r[16], "source_name": r[19], "organization": r[20],
                          "official_url": r[21], "reference_url": ref_url, "last_verified": r[18]}
            effective_risk = r[9]
            if effective_risk == "urgent" and r[1] not in IMMEDIATE_EMERGENCY_RULES:
                effective_risk = "review"
            hits.append({"rule_id":r[0],"slug":r[1],"name":r[2] if lang=="ar" else r[3],"risk_level":effective_risk,
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


def _log_symptom_coverage(unmatched, lang, conn):
    """Best-effort analytics log for *unmatched* symptom wording only.

    This helper must be called only after explicit, current analytics consent.
    Matched symptom text is intentionally not retained because it provides no
    value to the unmatched-coverage report and would unnecessarily increase the
    amount of free-text health data stored. No account/user identifier is stored.
    """
    if not unmatched:
        return
    try:
        c = conn.cursor()
        now = _now()
        for phrase in unmatched:
            text = str(phrase or "").strip()
            if not text:
                continue
            c.execute(
                f"INSERT INTO mk_unmatched_log (phrase, lang, matched, created_at) VALUES ({db.PH},{db.PH},{db.PH},{db.PH})",
                (text[:300], lang, 0, now)
            )
        conn.commit()
    except Exception:
        # Coverage logging is optional analytics; it must never interrupt the
        # user's symptom analysis.
        logging.getLogger(__name__).warning("Handled exception in _log_symptom_coverage; optional analytics skipped")


def unmatched_symptom_report(limit=50, days=30, conn=None):
    """Aggregate the coverage log into a ranked list of the most common
    symptom phrases that failed to match anything, for admin review. Returns
    a list of {"phrase": str, "count": int, "lang": str} sorted by frequency.
    """
    init_schema()
    own_conn = conn is None
    conn = conn or db._conn()
    try:
        c = conn.cursor()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).replace(microsecond=0).isoformat()
        c.execute(
            f"SELECT phrase, lang, COUNT(*) as n FROM mk_unmatched_log "
            f"WHERE matched=0 AND created_at >= {db.PH} "
            f"GROUP BY phrase, lang ORDER BY n DESC LIMIT {db.PH}",
            (cutoff, limit)
        )
        rows = c.fetchall()
        return [{"phrase": r[0], "lang": r[1], "count": int(r[2])} for r in rows]
    finally:
        if own_conn:
            conn.close()


def knowledge_bundle(raw_symptoms, severity=1, age=None, notes="", lang="ar", negatives=None, analytics_consent=False, gender=""):
    lang="en" if lang=="en" else "ar"
    # PERFORMANCE: use one database connection for normalization, red-flag rules,
    # condition ranking, and source lookup. Hosted PostgreSQL connection setup can
    # dominate request time when each stage opens a fresh connection.
    init_schema()
    conn = db._conn()
    try:
        norm=normalize_symptoms(raw_symptoms,lang,conn=conn)
        if analytics_consent:
            _log_symptom_coverage(norm.get("unmatched"), lang, conn)
        risk=evaluate_risk(norm["canonical"],raw_symptoms,notes,severity,age,lang,conn=conn)
        try:
            import symptom_combo_intelligence
            pattern_insights = symptom_combo_intelligence.detect_patterns(norm["canonical"], lang)
            pattern_bonuses = symptom_combo_intelligence.target_bonuses(pattern_insights)
        except Exception:
            logging.getLogger(__name__).warning("Handled exception in combo intelligence; base matching retained")
            pattern_insights, pattern_bonuses = [], {}
        parsed_negatives = {str(x.get("slug") or "") for x in (norm.get("negated") or []) if x.get("slug")}
        explicit_negatives = {str(x).strip() for x in (negatives or []) if str(x).strip()}
        all_negatives = sorted(parsed_negatives | explicit_negatives)
        matches=[] if risk["level"]=="urgent" else match_diseases(
            norm["canonical"], lang, negatives=all_negatives, conn=conn,
            pattern_bonuses=pattern_bonuses, gender=gender, age=age,
        )
        # Defense-in-depth only. match_diseases already filters before scoring.
        matches=_filter_matches_for_sex(matches, gender, norm["canonical"])
    finally:
        conn.close()
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
    return {"normalization":norm,"matches":matches,"sources":sources,"risk":risk,"pattern_insights":pattern_insights,"last_updated":max(dates) if dates else None}


def _admin(admin):
    return int((admin or {}).get("id") or 0) or None, str((admin or {}).get("email") or "system")


def _audit(c, admin, action, entity_type, entity_id, old, new):
    aid,_email=_admin(admin); now=_now()
    c.execute(f"INSERT INTO mk_audit_log (admin_id,admin_email,action,entity_type,entity_id,previous_value,new_value,timestamp) VALUES ({','.join([db.PH]*8)})",(aid,_email,action,entity_type,entity_id,_dump(old) if old is not None else None,_dump(new) if new is not None else None,now))
    version=int((new or old or {}).get("version") or 1)
    if new is not None and entity_type in {"disease","symptom","source","red_flag"}:
        c.execute(f"INSERT INTO mk_versions (entity_type,entity_id,version,snapshot,admin_id,admin_email,timestamp) VALUES ({','.join([db.PH]*7)})",(entity_type,int(entity_id),version,_dump(new),aid,_email,now))


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


def _source_mix_policy(c, ids):
    """Require two verified references for newly published public content.

    One source must be local (Saudi MOH or SFDA) and one must be an independent
    trusted global source. This applies at publication time; existing legacy
    pages are audited separately so we do not invent citations just to pass a
    numeric rule.
    """
    local_hosts = {"moh.gov.sa", "www.moh.gov.sa", "sfda.gov.sa", "www.sfda.gov.sa"}
    rows=[]
    for sid in ids or []:
        c.execute(f"SELECT id,official_url,source_name,organization FROM mk_sources WHERE id={db.PH} AND status='active' AND verification_status='verified'", (int(sid),))
        row=c.fetchone()
        if not row or not _url_is_trusted(row[1]):
            continue
        host=(urlparse(str(row[1] or '')).hostname or '').lower()
        rows.append({"id":int(row[0]),"host":host,"local":host in local_hosts or host.endswith('.moh.gov.sa') or host.endswith('.sfda.gov.sa')})
    return {
        "count": len(rows),
        "has_local": any(x["local"] for x in rows),
        "has_global": any(not x["local"] for x in rows),
        "ok": len(rows) >= 2 and any(x["local"] for x in rows) and any(not x["local"] for x in rows),
    }


def _enforce_publication_source_policy(c, source_ids):
    policy=_source_mix_policy(c, source_ids)
    if policy["count"] < 2:
        raise ValueError("two_verified_sources_required")
    if not policy["has_local"]:
        raise ValueError("local_saudi_source_required")
    if not policy["has_global"]:
        raise ValueError("independent_global_source_required")
    return policy


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
            c.execute(f"SELECT s.id,s.source_name,s.organization,s.official_url,ss.reference_title_ar,ss.reference_title_en,ss.reference_url,ss.last_verified FROM mk_symptom_sources ss JOIN mk_sources s ON s.id=ss.source_id WHERE ss.symptom_id={db.PH} AND ss.status='active' AND s.status='active' AND s.verification_status='verified'",(int(entity_id),))
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


def source_mix_for_entity(kind, entity_id):
    """Return the verified Saudi+global source-policy status for one entity.

    This intentionally does not change the entity status. The analysis engine may
    continue using reviewed local knowledge while the public library applies the
    stricter publication gate.
    """
    if kind not in {"disease", "symptom"}:
        raise ValueError("invalid_entity")
    init_schema(); conn=db._conn()
    try:
        c=conn.cursor(); ids=_entity_sources(c,kind,int(entity_id)); trusted=_verified_source_ids(c,ids)
        policy=_source_mix_policy(c,trusted)
        policy["source_ids"]=trusted
        return policy
    finally: conn.close()


def public_source_ready(kind, entity_id):
    try:
        return bool(source_mix_for_entity(kind,entity_id).get("ok"))
    except Exception:
        return False


def public_source_ready_ids(kind):
    """Return all active entity IDs that satisfy the public source policy.

    The old health-library index called ``public_source_ready`` once for every
    disease and symptom. With hundreds of entities on hosted PostgreSQL this
    became an N+1 query pattern and could turn one page view into hundreds of
    connections/queries. This bulk helper evaluates the same Saudi + independent
    global source rule from one joined query per entity kind.
    """
    if kind not in {"disease", "symptom"}:
        raise ValueError("invalid_entity")
    init_schema()
    if kind == "disease":
        entity_table, link_table, entity_col = "mk_diseases", "mk_disease_sources", "disease_id"
    else:
        entity_table, link_table, entity_col = "mk_symptoms", "mk_symptom_sources", "symptom_id"
    local_hosts = {"moh.gov.sa", "www.moh.gov.sa", "sfda.gov.sa", "www.sfda.gov.sa"}
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute(
            f"SELECT e.id,s.official_url FROM {entity_table} e "
            f"JOIN {link_table} l ON l.{entity_col}=e.id "
            f"JOIN mk_sources s ON s.id=l.source_id "
            "WHERE e.status='active' AND l.status='active' "
            "AND s.status='active' AND s.verification_status='verified'"
        )
        grouped = {}
        for entity_id, url in c.fetchall():
            if not _url_is_trusted(url):
                continue
            host = (urlparse(str(url or "")).hostname or "").lower()
            local = host in local_hosts or host.endswith(".moh.gov.sa") or host.endswith(".sfda.gov.sa")
            state = grouped.setdefault(int(entity_id), {"count": 0, "local": False, "global": False})
            state["count"] += 1
            state["local"] = state["local"] or local
            state["global"] = state["global"] or (not local)
        return {eid for eid, state in grouped.items() if state["count"] >= 2 and state["local"] and state["global"]}
    finally:
        conn.close()


def save_disease(data, admin, entity_id=None):
    init_schema(); ar=str(data.get("name_ar") or "").strip(); en=str(data.get("name_en") or "").strip(); source_ids=[int(x) for x in (data.get("source_ids") or [])]
    if not ar or not en or not str(data.get("description_ar") or "").strip() or not str(data.get("description_en") or "").strip(): raise ValueError("missing_required_fields")
    status=str(data.get("status") or "draft"); severity=str(data.get("severity") or "moderate")
    sex_applicability=str(data.get("sex_applicability") or "any").strip().lower()
    if sex_applicability not in {"any", "female_only", "male_only"}: raise ValueError("invalid_sex_applicability")
    min_age = None if data.get("min_age") in (None, "") else int(data.get("min_age"))
    max_age = None if data.get("max_age") in (None, "") else int(data.get("max_age"))
    if min_age is not None and not 0 <= min_age <= 130: raise ValueError("invalid_min_age")
    if max_age is not None and not 0 <= max_age <= 130: raise ValueError("invalid_max_age")
    if min_age is not None and max_age is not None and min_age > max_age: raise ValueError("invalid_age_range")
    pregnancy_relevant = 1 if bool(data.get("pregnancy_relevant")) else 0
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
        if status == "active" and (not entity_id or source_ids):
            _enforce_publication_source_policy(c, trusted)
        now=_now(); slug=str(data.get("slug") or _normalize_text(en).replace(" ","-")); version=int((old or {}).get("version") or 0)+1
        vals=(slug,ar,en,str(data.get("description_ar")),str(data.get("description_en")),data.get("category_id"),severity,str(data.get("risk_factors_ar") or ""),str(data.get("risk_factors_en") or ""),str(data.get("common_causes_ar") or ""),str(data.get("common_causes_en") or ""),str(data.get("red_flags_ar") or ""),str(data.get("red_flags_en") or ""),_dump(data.get("related_diseases") or []),str(data.get("recommended_next_step_ar") or ""),str(data.get("recommended_next_step_en") or ""),str(data.get("last_updated") or now[:10]),status,version,now)
        if not vals[14] or not vals[15]: raise ValueError("next_step_required")
        if entity_id:
            c.execute(f"UPDATE mk_diseases SET slug={db.PH},name_ar={db.PH},name_en={db.PH},description_ar={db.PH},description_en={db.PH},category_id={db.PH},severity={db.PH},risk_factors_ar={db.PH},risk_factors_en={db.PH},common_causes_ar={db.PH},common_causes_en={db.PH},red_flags_ar={db.PH},red_flags_en={db.PH},related_diseases={db.PH},recommended_next_step_ar={db.PH},recommended_next_step_en={db.PH},last_updated={db.PH},status={db.PH},version={db.PH},updated_at={db.PH} WHERE id={db.PH}",vals+(int(entity_id),)); eid=int(entity_id)
        else:
            c.execute(f"INSERT INTO mk_diseases (slug,name_ar,name_en,description_ar,description_en,category_id,severity,risk_factors_ar,risk_factors_en,common_causes_ar,common_causes_en,red_flags_ar,red_flags_en,related_diseases,recommended_next_step_ar,recommended_next_step_en,last_updated,status,version,created_at,updated_at) VALUES ({','.join([db.PH]*21)})",vals[:-1]+(now,now)); eid=_id(c)
        c.execute(
            f"UPDATE mk_diseases SET sex_applicability={db.PH},min_age={db.PH},max_age={db.PH},pregnancy_relevant={db.PH},updated_at={db.PH} WHERE id={db.PH}",
            (sex_applicability, min_age, max_age, pregnancy_relevant, now, eid),
        )
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
        if status == "active" and (not entity_id or source_ids):
            _enforce_publication_source_policy(c, trusted)
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


def periodic_review_status(max_age_days: int = 365, red_flag_max_age_days: int = 180) -> dict:
    """Return a review queue for medical content without changing any records.

    Active diseases/symptoms should have at least one active verified source.
    Sources and clinical content are flagged when their recorded review date is
    missing or older than the configured age. Red-flag rules use a shorter
    default review interval because they drive urgent triage.
    """
    init_schema()
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).date()

    def age_days(value):
        if not value:
            return None
        raw = str(value).strip()[:10]
        try:
            d = datetime.fromisoformat(raw).date()
            return max(0, (today - d).days)
        except (TypeError, ValueError, OverflowError):
            logging.getLogger(__name__).debug("Handled exception in age_days; fallback applied (handler 1804)")
            return None

    conn=db._conn(); c=conn.cursor()
    try:
        c.execute("SELECT id,name_ar,name_en,last_updated,status FROM mk_diseases ORDER BY id")
        diseases=c.fetchall()
        c.execute("SELECT id,name_ar,name_en,updated_at,status FROM mk_symptoms ORDER BY id")
        symptoms=c.fetchall()
        c.execute("SELECT id,source_name,organization,last_verified,verification_status,status FROM mk_sources ORDER BY id")
        sources=c.fetchall()
        c.execute("SELECT id,name_ar,name_en,last_updated,status,source_id,reference_url FROM mk_red_flags ORDER BY id")
        red_flags=c.fetchall()
        c.execute("SELECT ds.disease_id,COUNT(*) FROM mk_disease_sources ds JOIN mk_sources s ON s.id=ds.source_id WHERE ds.status='active' AND s.status='active' AND s.verification_status='verified' GROUP BY ds.disease_id")
        disease_sources={int(r[0]):int(r[1]) for r in c.fetchall()}
        c.execute("SELECT ss.symptom_id,COUNT(*) FROM mk_symptom_sources ss JOIN mk_sources s ON s.id=ss.source_id WHERE ss.status='active' AND s.status='active' AND s.verification_status='verified' GROUP BY ss.symptom_id")
        symptom_sources={int(r[0]):int(r[1]) for r in c.fetchall()}
    finally:
        conn.close()

    items=[]
    def add(kind,entity_id,name_ar,name_en,status,last_date,source_count=None,max_days=max_age_days,source_missing=False,reason=None):
        age=age_days(last_date)
        if status not in {'active','verified'}:
            review='needs_review'; why=reason or 'inactive_or_draft'
        elif source_missing:
            review='source_missing'; why='no_active_verified_source'
        elif age is None:
            review='needs_review'; why='missing_review_date'
        elif age>max_days:
            review='outdated'; why='review_date_expired'
        else:
            review='verified'; why='current'
        items.append({'entity_type':kind,'entity_id':entity_id,'name_ar':name_ar or '', 'name_en':name_en or '', 'review_status':review,'reason':why,'last_reviewed':last_date,'age_days':age,'source_count':source_count})

    for r in diseases:
        did=int(r[0]); add('disease',did,r[1],r[2],r[4],r[3],disease_sources.get(did,0),source_missing=(r[4]=='active' and disease_sources.get(did,0)==0))
    for r in symptoms:
        sid=int(r[0]); add('symptom',sid,r[1],r[2],r[4],r[3],symptom_sources.get(sid,0),source_missing=(r[4]=='active' and symptom_sources.get(sid,0)==0))
    for r in sources:
        sid=int(r[0]); status='verified' if r[4]=='verified' and r[5]=='active' else 'needs_review'; add('source',sid,r[1],r[2],status,r[3],None,reason='source_verification_needed' if status!='verified' else None)
    for r in red_flags:
        rid=int(r[0]); source_ok=bool(r[5] or str(r[6] or '').strip()); add('red_flag',rid,r[1],r[2],r[4],r[3],1 if source_ok else 0,max_days=red_flag_max_age_days,source_missing=(r[4]=='active' and not source_ok))

    counts={k:0 for k in ('verified','needs_review','source_missing','outdated')}
    for x in items: counts[x['review_status']]=counts.get(x['review_status'],0)+1
    queue=[x for x in items if x['review_status']!='verified']
    queue.sort(key=lambda x: ({'source_missing':0,'outdated':1,'needs_review':2}.get(x['review_status'],3), -(x['age_days'] or 0), x['entity_type'], x['entity_id']))
    return {'counts':counts,'total':len(items),'queue':queue,'all':items,'max_age_days':int(max_age_days),'red_flag_max_age_days':int(red_flag_max_age_days),'generated_at':_now()}


def statistics():
    """Return a compact quality snapshot for Admin and competition evidence.

    The metrics intentionally distinguish *size* from *coverage*: a larger
    knowledge base is useful only when symptoms are linked to conditions and
    active conditions are backed by verified sources.
    """
    init_schema(); conn=db._conn()
    try:
        c=conn.cursor()
        def count(table, where="1=1"):
            c.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}")
            return int(c.fetchone()[0])
        def scalar(sql, params=()):
            c.execute(sql, params)
            row=c.fetchone()
            return int((row or [0])[0] or 0)

        total_diseases=count("mk_diseases")
        total_symptoms=count("mk_symptoms")
        active_diseases=count("mk_diseases","status='active'")
        active_symptoms=count("mk_symptoms","status='active'")
        total_sources=count("mk_sources")
        verified_sources=count("mk_sources","status='active' AND verification_status='verified'")
        sources_needing_review=count("mk_sources","verification_status='needs_review'")
        total_relationships=count("mk_disease_symptoms","status='active'")
        total_red_flags=count("mk_red_flags")
        active_red_flags=count("mk_red_flags","status='active'")
        c.execute("SELECT DISTINCT symptom_id FROM mk_disease_symptoms WHERE status='active'")
        mapped_symptom_ids={int(row[0]) for row in c.fetchall()}
        mapped_symptoms=len(mapped_symptom_ids)
        # A small number of concepts are intentionally safety-only (for example
        # severe bleeding and self-harm thoughts) and should not be forced into
        # a disease pattern just to make the mapping percentage look complete.
        # Track source/safety support separately so quality metrics distinguish
        # intentional safety concepts from genuinely unsupported content.
        c.execute("SELECT DISTINCT ss.symptom_id FROM mk_symptom_sources ss JOIN mk_sources src ON src.id=ss.source_id WHERE ss.status='active' AND src.status='active' AND src.verification_status='verified'")
        directly_sourced_symptom_ids={int(row[0]) for row in c.fetchall()}
        c.execute("SELECT required_symptoms FROM mk_red_flags WHERE status='active' AND (source_id IS NOT NULL OR TRIM(COALESCE(reference_url,''))<>'')")
        safety_supported_slugs=set()
        for (_required_json,) in c.fetchall():
            safety_supported_slugs.update(str(x) for x in _json(_required_json, []) if x)
        safety_supported_ids=set()
        if safety_supported_slugs:
            _safe_ph=",".join([db.PH]*len(safety_supported_slugs))
            c.execute(f"SELECT id FROM mk_symptoms WHERE status='active' AND slug IN ({_safe_ph})", tuple(sorted(safety_supported_slugs)))
            safety_supported_ids={int(row[0]) for row in c.fetchall()}
        supported_symptom_ids=directly_sourced_symptom_ids | safety_supported_ids
        supported_symptoms=len(supported_symptom_ids)
        safety_only_symptoms=len(safety_supported_ids - mapped_symptom_ids)
        unsupported_symptoms=max(0, active_symptoms-supported_symptoms)
        diseases_with_sources=scalar("SELECT COUNT(DISTINCT disease_id) FROM mk_disease_sources WHERE status='active'")
        disease_source_links=count("mk_disease_sources","status='active'")
        high_authority_sources=scalar(
            "SELECT COUNT(*) FROM mk_sources WHERE status='active' AND verification_status='verified' "
            "AND source_type IN ('government','international_organization','national_health_service','clinical_guideline_body')"
        )
        # Sources added in the current V53 knowledge expansion.  Keeping the
        # slugs explicit makes the metric auditable instead of deriving it from
        # timestamps that can change after a content review.
        recent_expansion_source_slugs=('niddk','nhlbi','ninds','nice','nei','nimh','niaid','nidcd','nichd')
        _recent_ph = ",".join([db.PH] * len(recent_expansion_source_slugs))
        recent_source_additions=scalar(
            "SELECT COUNT(*) FROM mk_sources WHERE status='active' AND verification_status='verified' "
            f"AND slug IN ({_recent_ph})", recent_expansion_source_slugs
        )
        c.execute("SELECT source_type,COUNT(*) FROM mk_sources WHERE status='active' AND verification_status='verified' GROUP BY source_type ORDER BY source_type")
        source_type_distribution={str(row[0]):int(row[1]) for row in c.fetchall()}
        c.execute("SELECT MAX(updated_at) FROM (SELECT updated_at FROM mk_diseases UNION ALL SELECT updated_at FROM mk_symptoms UNION ALL SELECT updated_at FROM mk_sources) x")
        last=c.fetchone()[0]

        symptom_coverage_pct=round((mapped_symptoms/max(1,active_symptoms))*100.0,1)
        symptom_support_coverage_pct=round((supported_symptoms/max(1,active_symptoms))*100.0,1)
        source_coverage_pct=round((diseases_with_sources/max(1,active_diseases))*100.0,1)
        avg_sources_per_disease=round(disease_source_links/max(1,active_diseases),2)

        # V76 growth metrics use the last pre-multi-symptom-search release (V74)
        # as an auditable baseline. ``search_term_entries`` is a transparent
        # content-size metric: two display names plus every stored Arabic/English
        # alias for each active symptom concept. It is intentionally not a claim
        # about model accuracy or diagnostic coverage.
        c.execute("SELECT aliases_ar,aliases_en FROM mk_symptoms WHERE status='active'")
        alias_entries = 0
        for _aliases_ar, _aliases_en in c.fetchall():
            alias_entries += len(_json(_aliases_ar, [])) + len(_json(_aliases_en, []))
        search_term_entries = (active_symptoms * 2) + alias_entries
        v74_baseline_symptoms = 247
        v74_baseline_relationships = 715
        v74_baseline_search_terms = 1876
        symptom_growth_since_v74 = active_symptoms - v74_baseline_symptoms
        relationship_growth_since_v74 = total_relationships - v74_baseline_relationships
        search_term_growth_since_v74 = search_term_entries - v74_baseline_search_terms

        return {
            "knowledge_version":"2026.09-v76-full-site-audit",
            "total_diseases":total_diseases,
            "total_symptoms":total_symptoms,
            "total_sources":total_sources,
            "active_diseases":active_diseases,
            "active_symptoms":active_symptoms,
            "verified_sources":verified_sources,
            "sources_needing_review":sources_needing_review,
            "total_relationships":total_relationships,
            "total_red_flags":total_red_flags,
            "active_red_flags":active_red_flags,
            "mapped_symptoms":mapped_symptoms,
            "unlinked_symptoms":max(0,active_symptoms-mapped_symptoms),
            "supported_symptoms":supported_symptoms,
            "safety_only_symptoms":safety_only_symptoms,
            "unsupported_symptoms":unsupported_symptoms,
            "symptom_coverage_pct":symptom_coverage_pct,
            "symptom_support_coverage_pct":symptom_support_coverage_pct,
            "diseases_with_sources":diseases_with_sources,
            "disease_source_links":disease_source_links,
            "source_coverage_pct":source_coverage_pct,
            "avg_sources_per_disease":avg_sources_per_disease,
            "high_authority_sources":high_authority_sources,
            "recent_source_additions":recent_source_additions,
            "source_type_distribution":source_type_distribution,
            "search_alias_entries":alias_entries,
            "search_term_entries":search_term_entries,
            "v74_baseline_symptoms":v74_baseline_symptoms,
            "v74_baseline_relationships":v74_baseline_relationships,
            "v74_baseline_search_terms":v74_baseline_search_terms,
            "symptom_growth_since_v74":symptom_growth_since_v74,
            "relationship_growth_since_v74":relationship_growth_since_v74,
            "search_term_growth_since_v74":search_term_growth_since_v74,
            "v76_duplicate_concepts_merged":1,
            "v76_alias_collisions_resolved":5,
            "last_knowledge_update":last,
        }
    finally:
        conn.close()


def system_health():
    """Run live, read-only health checks without exposing credentials."""
    init_schema(); checked=_now(); health={}
    start=time.perf_counter()
    try:
        conn=db._conn(); c=conn.cursor(); c.execute("SELECT 1"); c.fetchone(); conn.close()
        health["database"]={"status":"online","response_ms":round((time.perf_counter()-start)*1000,1),"error":None}
    except Exception as e:
        logging.getLogger(__name__).warning("Handled exception in system_health; fallback applied (handler 1874)")
        health["database"]={"status":"offline","response_ms":round((time.perf_counter()-start)*1000,1),"error":"database_check_failed"}

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
            health["ai_service"]={"status":"offline","response_ms":round((time.perf_counter()-start)*1000,1),"error":f"provider_http_{int(e.code or 0)}"}
        except (URLError, TimeoutError, OSError) as e:
            health["ai_service"]={"status":"offline","response_ms":round((time.perf_counter()-start)*1000,1),"error":"provider_connection_failed"}

    start=time.perf_counter()
    try:
        conn=db._conn(); c=conn.cursor(); c.execute("SELECT id,status,role FROM ss_users LIMIT 1"); c.fetchone(); conn.close()
        health["authentication"]={"status":"online","response_ms":round((time.perf_counter()-start)*1000,1),"error":None}
    except Exception as e:
        logging.getLogger(__name__).warning("Handled exception in system_health; fallback applied (handler 1895)")
        health["authentication"]={"status":"offline","response_ms":round((time.perf_counter()-start)*1000,1),"error":"authentication_check_failed"}
    return {"checked_at":checked,"components":health}


def rollback_version(entity_type: str, entity_id: int, version: int, admin: dict) -> dict:
    """Restore a prior medical-content snapshot as a *new* version.

    Rollback never deletes history. The restored snapshot is validated through
    the same save functions as a normal Admin edit and therefore creates a new
    audit/version entry while preserving an immutable trail.
    """
    entity_type=str(entity_type or "").strip().lower()
    if entity_type not in {"disease","symptom","source","red_flag"}:
        raise ValueError("invalid_entity")
    history=versions(entity_type,int(entity_id))
    selected=next((x for x in history if int(x.get("version") or -1)==int(version)),None)
    if not selected:
        raise ValueError("version_not_found")
    snapshot=dict(selected.get("snapshot") or {})
    # Server-controlled fields must never be trusted from a historical payload.
    for key in ("id","version","created_at","updated_at"):
        snapshot.pop(key,None)
    if entity_type=="disease": restored=save_disease(snapshot,admin,int(entity_id))
    elif entity_type=="symptom": restored=save_symptom(snapshot,admin,int(entity_id))
    elif entity_type=="source": restored=save_source(snapshot,admin,int(entity_id))
    else: restored=save_red_flag(snapshot,admin,int(entity_id))
    conn=db._conn()
    try:
        c=conn.cursor(); aid,email=_admin(admin); now=_now()
        previous={"from_version":max(0,int(restored.get("version") or 0)-1)}
        current={"restored_from_version":int(version),"new_version":int(restored.get("version") or 0)}
        c.execute(f"INSERT INTO mk_audit_log (admin_id,admin_email,action,entity_type,entity_id,previous_value,new_value,timestamp) VALUES ({','.join([db.PH]*8)})",(aid,email,"rolled_back",entity_type,int(entity_id),_dump(previous),_dump(current),now))
        conn.commit()
    finally: conn.close()
    return {"entity":restored,"restored_from_version":int(version),"new_version":int(restored.get("version") or 0)}


def versioning_summary() -> dict:
    """Explain version/review state for the Admin dashboard and API."""
    init_schema(); conn=db._conn()
    try:
        c=conn.cursor(); out={}
        for kind,table in (("disease","mk_diseases"),("symptom","mk_symptoms"),("source","mk_sources"),("red_flag","mk_red_flags")):
            c.execute(f"SELECT COUNT(*),COALESCE(MAX(version),0),COALESCE(AVG(version),0) FROM {table}")
            row=c.fetchone(); out[kind]={"entities":int(row[0] or 0),"max_version":int(row[1] or 0),"average_version":round(float(row[2] or 0),2)}
        c.execute("SELECT COUNT(*) FROM mk_versions"); total_versions=int(c.fetchone()[0] or 0)
        c.execute("SELECT COUNT(*) FROM mk_audit_log"); total_audits=int(c.fetchone()[0] or 0)
        return {"entities":out,"version_snapshots":total_versions,"audit_events":total_audits,"review":periodic_review_status()}
    finally: conn.close()
