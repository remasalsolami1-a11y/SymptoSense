"""Structured follow-up and care guidance for each symptom concept.

Every active symptom gets a small, consistent question set and a "when to seek
care" field. Defaults are intentionally generic and non-diagnostic. Editors can
replace them with reviewed symptom-specific wording later without changing the
analysis engine.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import db
import medical_knowledge as mk

PH = db.PH


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def init_schema():
    mk.init_schema(); conn = db._conn(); c = conn.cursor()
    try:
        c.execute("""
            CREATE TABLE IF NOT EXISTS mk_symptom_guidance (
                symptom_id INTEGER PRIMARY KEY,
                followup_questions_ar TEXT NOT NULL DEFAULT '[]',
                followup_questions_en TEXT NOT NULL DEFAULT '[]',
                when_to_seek_care_ar TEXT NOT NULL DEFAULT '',
                when_to_seek_care_en TEXT NOT NULL DEFAULT '',
                review_status TEXT NOT NULL DEFAULT 'generated',
                last_reviewed TEXT,
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()


def _defaults(item: dict):
    name_ar = str(item.get("name_ar") or "هذا العرض")
    name_en = str(item.get("name_en") or "this symptom")
    red_ar = str(item.get("red_flags_ar") or "").strip()
    red_en = str(item.get("red_flags_en") or "").strip()
    ar = [
        f"متى بدأ {name_ar}؟ وهل بدأ فجأة أم تدريجيًا؟",
        "ما شدة العرض الآن؟ وهل يمنعك من نشاطك المعتاد أو النوم؟",
        "هل يزداد أو يتحسن مع الحركة أو الطعام أو الوقوف أو الراحة أو وقت معين؟",
        "هل ظهرت معه أعراض أخرى جديدة أو غير معتادة؟",
    ]
    en = [
        f"When did {name_en} start, and was the onset sudden or gradual?",
        "How severe is it now, and does it limit normal activity or sleep?",
        "Does it get better or worse with movement, food, standing, rest, or a particular time?",
        "Did any other new or unusual symptoms start with it?",
    ]
    if red_ar:
        ar.append("هل ظهرت أي علامة خطر مذكورة في هذه الصفحة، أو تدهور سريع ومفاجئ؟")
    if red_en:
        en.append("Have any red flags listed on this page appeared, or has there been a rapid sudden worsening?")
    ar = ar[:5]; en = en[:5]
    care_ar = "اطلب تقييمًا طبيًا إذا كان العرض شديدًا، جديدًا بشكل مقلق، مستمرًا أو يزداد سوءًا. إذا ظهرت علامة خطر واضحة فتوجّه للطوارئ فورًا."
    care_en = "Seek medical review if the symptom is severe, concerningly new, persistent, or worsening. If a clear red flag appears, seek emergency care immediately."
    return ar, en, care_ar, care_en


def ensure_for_symptom(symptom_id: int):
    init_schema(); item = mk.get_entity("symptom", int(symptom_id), public=False)
    if not item:
        return None
    conn = db._conn(); c = conn.cursor(); now = _now()
    try:
        c.execute(f"SELECT symptom_id,followup_questions_ar,followup_questions_en,when_to_seek_care_ar,when_to_seek_care_en,review_status,last_reviewed,updated_at FROM mk_symptom_guidance WHERE symptom_id={PH}", (int(symptom_id),))
        row = c.fetchone()
        if not row:
            q_ar, q_en, care_ar, care_en = _defaults(item)
            c.execute(
                f"INSERT INTO mk_symptom_guidance(symptom_id,followup_questions_ar,followup_questions_en,when_to_seek_care_ar,when_to_seek_care_en,review_status,last_reviewed,updated_at) VALUES({','.join([PH]*8)})",
                (int(symptom_id), json.dumps(q_ar, ensure_ascii=False), json.dumps(q_en, ensure_ascii=False), care_ar, care_en, "generated", None, now),
            )
            conn.commit()
            row = (int(symptom_id), json.dumps(q_ar, ensure_ascii=False), json.dumps(q_en, ensure_ascii=False), care_ar, care_en, "generated", None, now)
        keys = ["symptom_id","followup_questions_ar","followup_questions_en","when_to_seek_care_ar","when_to_seek_care_en","review_status","last_reviewed","updated_at"]
        out = dict(zip(keys, row))
        for k in ("followup_questions_ar","followup_questions_en"):
            try: out[k] = json.loads(out[k] or "[]")
            except Exception: out[k] = []
        return out
    finally:
        conn.close()


def backfill_all() -> dict:
    mk.init_schema(); items = mk.list_entities("symptoms", False, "")
    created = 0
    for item in items:
        before = get(int(item["id"]))
        ensure_for_symptom(int(item["id"]))
        if before is None:
            created += 1
    return {"total": len(items), "created": created}


def get(symptom_id: int):
    init_schema(); conn = db._conn(); c = conn.cursor()
    try:
        c.execute(f"SELECT symptom_id,followup_questions_ar,followup_questions_en,when_to_seek_care_ar,when_to_seek_care_en,review_status,last_reviewed,updated_at FROM mk_symptom_guidance WHERE symptom_id={PH}", (int(symptom_id),))
        row = c.fetchone()
        if not row: return None
        keys=["symptom_id","followup_questions_ar","followup_questions_en","when_to_seek_care_ar","when_to_seek_care_en","review_status","last_reviewed","updated_at"]
        out=dict(zip(keys,row))
        for k in ("followup_questions_ar","followup_questions_en"):
            try: out[k]=json.loads(out[k] or "[]")
            except Exception: out[k]=[]
        return out
    finally:
        conn.close()


def save(symptom_id: int, data: dict, reviewer: str):
    item = mk.get_entity("symptom", int(symptom_id), public=False)
    if not item: raise ValueError("symptom_not_found")
    q_ar = [str(x).strip()[:350] for x in (data.get("followup_questions_ar") or []) if str(x).strip()][:5]
    q_en = [str(x).strip()[:350] for x in (data.get("followup_questions_en") or []) if str(x).strip()][:5]
    if len(q_ar) < 3 or len(q_en) < 3:
        raise ValueError("three_to_five_followup_questions_required")
    care_ar = str(data.get("when_to_seek_care_ar") or "").strip()[:2000]
    care_en = str(data.get("when_to_seek_care_en") or "").strip()[:2000]
    if not care_ar or not care_en:
        raise ValueError("when_to_seek_care_required")
    init_schema(); conn=db._conn(); c=conn.cursor(); now=_now()
    try:
        payload=(json.dumps(q_ar,ensure_ascii=False),json.dumps(q_en,ensure_ascii=False),care_ar,care_en,"reviewed",now,now,int(symptom_id))
        c.execute(f"UPDATE mk_symptom_guidance SET followup_questions_ar={PH},followup_questions_en={PH},when_to_seek_care_ar={PH},when_to_seek_care_en={PH},review_status={PH},last_reviewed={PH},updated_at={PH} WHERE symptom_id={PH}", payload)
        if c.rowcount == 0:
            c.execute(f"INSERT INTO mk_symptom_guidance(symptom_id,followup_questions_ar,followup_questions_en,when_to_seek_care_ar,when_to_seek_care_en,review_status,last_reviewed,updated_at) VALUES({','.join([PH]*8)})", (int(symptom_id),*payload[:-1]))
        conn.commit()
    finally:
        conn.close()
    return get(symptom_id)
