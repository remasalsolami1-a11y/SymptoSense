"""ICD-11-backed taxonomy support for SymptoSense.

The public analysis engine still works from the local reviewed knowledge base.
This module adds a standards layer: each condition can be mapped to an official
ICD-11 entity, while symptoms inherit an ICD-oriented body-system chapter from
their local category. WHO API results are stored as candidates until reviewed;
no external result is auto-published.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import db
import medical_knowledge as mk
import medical_source_pipeline as source_pipeline

PH = db.PH

# Current SymptoSense categories aligned to the closest ICD-11 chapter/system.
# This mapping is for navigation only; it is not an ICD diagnosis/code assignment.
CATEGORY_ICD_SYSTEM = {
    "respiratory": {"chapter": "12", "ar": "أمراض الجهاز التنفسي", "en": "Diseases of the respiratory system"},
    "digestive": {"chapter": "13", "ar": "أمراض الجهاز الهضمي", "en": "Diseases of the digestive system"},
    "neurological": {"chapter": "08", "ar": "أمراض الجهاز العصبي", "en": "Diseases of the nervous system"},
    "cardiovascular": {"chapter": "11", "ar": "أمراض الجهاز الدوري", "en": "Diseases of the circulatory system"},
    "skin": {"chapter": "14", "ar": "أمراض الجلد", "en": "Diseases of the skin"},
    "musculoskeletal": {"chapter": "15", "ar": "أمراض الجهاز العضلي الهيكلي والنسيج الضام", "en": "Diseases of the musculoskeletal system or connective tissue"},
    "mental-health": {"chapter": "06", "ar": "الاضطرابات النفسية والسلوكية والعصبية النمائية", "en": "Mental, behavioural or neurodevelopmental disorders"},
    "eye": {"chapter": "09", "ar": "أمراض الجهاز البصري", "en": "Diseases of the visual system"},
    "womens_health": {"chapter": "17", "ar": "حالات متعلقة بالصحة الجنسية والإنجابية", "en": "Conditions related to sexual health"},
    # Pain is a symptom grouping rather than a single ICD disease chapter.
    "pain": {"chapter": "21", "ar": "الأعراض والعلامات والنتائج السريرية غير المصنفة في موضع آخر", "en": "Symptoms, signs or clinical findings, not elsewhere classified"},
    "general": {"chapter": "21", "ar": "الأعراض والعلامات والنتائج السريرية غير المصنفة في موضع آخر", "en": "Symptoms, signs or clinical findings, not elsewhere classified"},
}


def _serial():
    return "SERIAL PRIMARY KEY" if db.USE_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def init_schema():
    mk.init_schema()
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS mk_icd11_mappings (
                id {_serial()}, entity_type TEXT NOT NULL, entity_id INTEGER NOT NULL,
                icd_uri TEXT NOT NULL, icd_code TEXT, title TEXT NOT NULL,
                chapter TEXT, status TEXT NOT NULL DEFAULT 'candidate',
                confidence REAL, source_payload TEXT NOT NULL DEFAULT '{{}}',
                created_at TEXT NOT NULL, reviewed_at TEXT, reviewed_by TEXT,
                UNIQUE(entity_type,entity_id,icd_uri)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_icd11_entity ON mk_icd11_mappings(entity_type,entity_id,status)")
        conn.commit()
    finally:
        conn.close()


def category_system(category_slug: str, lang: str = "ar") -> dict:
    row = CATEGORY_ICD_SYSTEM.get(str(category_slug or "").strip(), CATEGORY_ICD_SYSTEM["general"])
    return {"chapter": row["chapter"], "label": row["en" if lang == "en" else "ar"], "category": category_slug or "general"}


def _entity_name(kind: str, entity_id: int) -> str:
    item = mk.get_entity(kind, int(entity_id), public=False)
    if not item:
        raise ValueError("entity_not_found")
    return str(item.get("name_en") or item.get("name_ar") or item.get("slug") or "").strip()


def queue_entity_candidates(kind: str, entity_id: int, limit: int = 5) -> list[dict]:
    """Query WHO ICD-11 and store candidates for editorial review."""
    if kind not in {"disease", "symptom"}:
        raise ValueError("invalid_entity_type")
    init_schema()
    term = _entity_name(kind, entity_id)
    results = source_pipeline.who_icd11_search(term, "en", limit=max(1, min(10, int(limit))))
    conn = db._conn(); c = conn.cursor(); now = _now(); stored = []
    try:
        for rank, item in enumerate(results, start=1):
            uri = str(item.get("id") or "").strip()
            if not uri:
                continue
            code = str(item.get("code") or "").strip()
            title = str(item.get("title") or term).strip()
            chapter = str(item.get("chapter") or "").strip()
            confidence = max(0.05, 1.0 - ((rank - 1) * 0.12))
            payload = json.dumps(item, ensure_ascii=False)
            if db.USE_POSTGRES:
                c.execute(
                    f"INSERT INTO mk_icd11_mappings(entity_type,entity_id,icd_uri,icd_code,title,chapter,status,confidence,source_payload,created_at) "
                    f"VALUES({','.join([PH]*10)}) ON CONFLICT(entity_type,entity_id,icd_uri) DO UPDATE SET icd_code=EXCLUDED.icd_code,title=EXCLUDED.title,chapter=EXCLUDED.chapter,confidence=EXCLUDED.confidence,source_payload=EXCLUDED.source_payload",
                    (kind, int(entity_id), uri, code, title, chapter, "candidate", confidence, payload, now),
                )
            else:
                c.execute(
                    f"INSERT OR IGNORE INTO mk_icd11_mappings(entity_type,entity_id,icd_uri,icd_code,title,chapter,status,confidence,source_payload,created_at) VALUES({','.join([PH]*10)})",
                    (kind, int(entity_id), uri, code, title, chapter, "candidate", confidence, payload, now),
                )
                c.execute(
                    f"UPDATE mk_icd11_mappings SET icd_code={PH},title={PH},chapter={PH},confidence={PH},source_payload={PH} WHERE entity_type={PH} AND entity_id={PH} AND icd_uri={PH}",
                    (code, title, chapter, confidence, payload, kind, int(entity_id), uri),
                )
            stored.append({"uri": uri, "code": code, "title": title, "chapter": chapter, "confidence": confidence})
        conn.commit()
    finally:
        conn.close()
    return stored


def approve_mapping(mapping_id: int, reviewer: str) -> dict:
    init_schema(); conn = db._conn(); c = conn.cursor(); now = _now()
    try:
        c.execute(f"SELECT entity_type,entity_id FROM mk_icd11_mappings WHERE id={PH}", (int(mapping_id),))
        row = c.fetchone()
        if not row:
            raise ValueError("mapping_not_found")
        kind, entity_id = row[0], int(row[1])
        c.execute(f"UPDATE mk_icd11_mappings SET status='rejected',reviewed_at={PH},reviewed_by={PH} WHERE entity_type={PH} AND entity_id={PH} AND status='approved'", (now, reviewer, kind, entity_id))
        c.execute(f"UPDATE mk_icd11_mappings SET status='approved',reviewed_at={PH},reviewed_by={PH} WHERE id={PH}", (now, reviewer, int(mapping_id)))
        conn.commit()
        c.execute(f"SELECT id,entity_type,entity_id,icd_uri,icd_code,title,chapter,status,confidence,reviewed_at,reviewed_by FROM mk_icd11_mappings WHERE id={PH}", (int(mapping_id),))
        vals = c.fetchone()
        keys = ["id","entity_type","entity_id","icd_uri","icd_code","title","chapter","status","confidence","reviewed_at","reviewed_by"]
        return dict(zip(keys, vals))
    finally:
        conn.close()


def approved_mapping(kind: str, entity_id: int):
    init_schema(); conn = db._conn(); c = conn.cursor()
    try:
        c.execute(f"SELECT icd_uri,icd_code,title,chapter,confidence,reviewed_at FROM mk_icd11_mappings WHERE entity_type={PH} AND entity_id={PH} AND status='approved' ORDER BY id DESC LIMIT 1", (kind, int(entity_id)))
        row = c.fetchone()
        if not row:
            return None
        return dict(zip(["icd_uri","icd_code","title","chapter","confidence","reviewed_at"], row))
    finally:
        conn.close()


def coverage_report() -> dict:
    init_schema(); conn = db._conn(); c = conn.cursor()
    try:
        counts = {}
        for kind, table in (("disease", "mk_diseases"), ("symptom", "mk_symptoms")):
            c.execute(f"SELECT COUNT(*) FROM {table} WHERE status='active'")
            total = int(c.fetchone()[0])
            c.execute(f"SELECT COUNT(DISTINCT entity_id) FROM mk_icd11_mappings WHERE entity_type={PH} AND status='approved'", (kind,))
            approved = int(c.fetchone()[0])
            c.execute(f"SELECT COUNT(DISTINCT entity_id) FROM mk_icd11_mappings WHERE entity_type={PH} AND status='candidate'", (kind,))
            candidate = int(c.fetchone()[0])
            counts[kind] = {"active": total, "approved": approved, "candidate": candidate, "unmapped": max(0, total-approved)}
        return counts
    finally:
        conn.close()
