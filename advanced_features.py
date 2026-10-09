"""Privacy-preserving data science and user-insight helpers for SymptoSense.

All user-facing health insights are descriptive only. Admin analytics use aggregated
or anonymized data and never expose credentials, emails, names, private health
profiles, or private conversations.
"""
from __future__ import annotations
import logging
import threading

import io
import json
import math
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta

import db
import medical_knowledge
import clinical_text
import platform_v2
import privacy_features

PH = db.PH
_SCHEMA_READY_KEY = None
_SCHEMA_LOCK = threading.Lock()


def _now():
    return datetime.now(timezone.utc).isoformat()


def _rows(cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _table_exists(cur, name: str) -> bool:
    if db.USE_POSTGRES:
        cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name=%s", (name,))
    else:
        cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return bool(cur.fetchone())


def init_schema() -> None:
    """Create optional feature tables once per database identity.

    V216 keeps PostgreSQL DDL out of ordinary page rendering.  In V215 every
    signed-in page called get_preferences(), which called this function and
    executed CREATE TABLE/INDEX statements again. Under concurrent traffic or
    background maintenance that can contend on PostgreSQL catalog locks and
    exhaust Waitress threads.
    """
    global _SCHEMA_READY_KEY
    db.init_db()
    key = db._database_identity()
    if _SCHEMA_READY_KEY == key:
        return
    with _SCHEMA_LOCK:
        if _SCHEMA_READY_KEY == key:
            return
        conn = db._conn(); c = conn.cursor()
        try:
            c.execute("""
                CREATE TABLE IF NOT EXISTS ss_user_preferences (
                    user_id INTEGER PRIMARY KEY,
                    accessibility_mode INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                )
            """)
            serial = "SERIAL PRIMARY KEY" if db.USE_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"
            c.execute(f"""
                CREATE TABLE IF NOT EXISTS ss_analysis_links (
                    id {serial}, user_hash TEXT NOT NULL,
                    previous_record_id INTEGER NOT NULL,
                    current_record_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_ss_analysis_links_user ON ss_analysis_links(user_hash, current_record_id)")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        _SCHEMA_READY_KEY = key


def get_preferences(user_id: int | None) -> dict:
    init_schema()
    if not user_id:
        return {"accessibility_mode": False}
    conn=db._conn(); c=conn.cursor()
    try:
        c.execute(f"SELECT accessibility_mode FROM ss_user_preferences WHERE user_id={PH}", (int(user_id),))
        row=c.fetchone()
        return {"accessibility_mode": bool(row[0]) if row else False}
    finally: conn.close()


def save_preferences(user_id: int, accessibility_mode: bool) -> None:
    init_schema(); conn=db._conn(); c=conn.cursor(); now=_now()
    try:
        if db.USE_POSTGRES:
            c.execute("""INSERT INTO ss_user_preferences(user_id,accessibility_mode,updated_at) VALUES(%s,%s,%s)
                       ON CONFLICT(user_id) DO UPDATE SET accessibility_mode=EXCLUDED.accessibility_mode,updated_at=EXCLUDED.updated_at""",
                      (int(user_id), int(bool(accessibility_mode)), now))
        else:
            c.execute("""INSERT INTO ss_user_preferences(user_id,accessibility_mode,updated_at) VALUES(?,?,?)
                       ON CONFLICT(user_id) DO UPDATE SET accessibility_mode=excluded.accessibility_mode,updated_at=excluded.updated_at""",
                      (int(user_id), int(bool(accessibility_mode)), now))
        conn.commit()
    finally: conn.close()


def link_reanalysis(user_key: str, previous_record_id: int, current_record_id: int) -> None:
    if not user_key or not previous_record_id or not current_record_id:
        return
    init_schema(); conn=db._conn(); c=conn.cursor(); owner=db._hash_user(user_key)
    try:
        # Keep relationship metadata tenant-safe as well as the underlying
        # analysis reads. A guessed record id must never be linkable to another
        # account, even if this table is only used internally today.
        c.execute(
            f"SELECT id FROM records WHERE user_hash={PH} AND id IN ({PH},{PH})",
            (owner, int(previous_record_id), int(current_record_id)),
        )
        owned = {int(row[0]) for row in c.fetchall()}
        if {int(previous_record_id), int(current_record_id)} - owned:
            raise PermissionError("analysis_not_owned")
        c.execute(f"INSERT INTO ss_analysis_links(user_hash,previous_record_id,current_record_id,created_at) VALUES({','.join([PH]*4)})",
                  (owner, int(previous_record_id), int(current_record_id), _now()))
        conn.commit()
    finally: conn.close()


def _parse_result(value):
    if not value: return {}
    if isinstance(value, dict): return value
    try: return json.loads(value)
    except Exception: logging.getLogger(__name__).debug("Handled exception in _parse_result; fallback applied (handler 111)"); return {}


def user_analysis_rows(user_key: str, limit: int = 500) -> list[dict]:
    """Return only the supplied user's analyses, merged with stored result JSON."""
    owner=db._hash_user(user_key)
    conn=db._conn(); c=conn.cursor()
    try:
        c.execute(
            "SELECT r.id,r.timestamp,r.lang,r.age,r.gender,r.symptoms,r.duration,r.severity,r.urgency,r.conditions,r.medications,res.data "
            "FROM records r LEFT JOIN results res ON res.record_id=r.id AND res.user_hash=r.user_hash "
            f"WHERE r.user_hash={PH} AND COALESCE(r.member_id,0)=0 ORDER BY r.id DESC LIMIT {PH}",
            (owner, max(1,min(1000,int(limit))))
        )
        out=[]
        for row in c.fetchall():
            result=_parse_result(row[11])
            snapshot=result.get("input_snapshot") if isinstance(result.get("input_snapshot"),dict) else {}
            syms=[s.strip() for s in str(row[5] or '').split(',') if s.strip()]
            if not syms:
                syms=[str(s).strip() for s in (snapshot.get("symptoms") or result.get("symptoms") or []) if str(s).strip()]
            out.append({
                "id": int(row[0]), "timestamp": row[1], "lang": row[2], "age": row[3], "gender": row[4],
                "symptoms": syms, "duration": row[6], "severity": row[7], "urgency": row[8],
                "conditions": row[9] or snapshot.get("conditions") or "",
                "medications": row[10] or snapshot.get("medications") or "",
                "allergies": snapshot.get("allergies") or result.get("allergies") or "",
                "notes": snapshot.get("notes") or result.get("notes") or "",
                "result": result,
            })
        return out
    finally: conn.close()


def get_user_analysis(user_key: str, record_id: int) -> dict | None:
    for row in user_analysis_rows(user_key, limit=1000):
        if row["id"] == int(record_id):
            return row
    return None


def delete_user_analysis(user_key: str, record_id: int) -> bool:
    """Delete exactly one analysis owned by this user. No cross-user delete is possible."""
    owner=db._hash_user(user_key); rid=int(record_id)
    conn=db._conn(); c=conn.cursor()
    try:
        c.execute(f"SELECT 1 FROM records WHERE id={PH} AND user_hash={PH} AND COALESCE(member_id,0)=0", (rid,owner))
        if not c.fetchone(): return False
        c.execute(f"DELETE FROM results WHERE record_id={PH} AND user_hash={PH}", (rid,owner))
        c.execute(f"DELETE FROM feedback WHERE record_id={PH} AND user_hash={PH}", (rid,owner))
        c.execute(f"DELETE FROM followups WHERE record_id={PH} AND user_hash={PH}", (rid,owner))
        c.execute(f"DELETE FROM ss_analysis_links WHERE user_hash={PH} AND (previous_record_id={PH} OR current_record_id={PH})", (owner,rid,rid))
        c.execute(f"DELETE FROM records WHERE id={PH} AND user_hash={PH}", (rid,owner))
        conn.commit(); return True
    finally: conn.close()


def _risk_label(value: str, lang="en") -> str:
    m={
        "en":{"low":"Low risk","medium":"Needs follow-up","high":"Urgent"},
        "ar":{"low":"منخفض","medium":"يحتاج متابعة","high":"عاجل"},
    }
    return m["ar" if lang=="ar" else "en"].get((value or "low").lower(), value or "—")


def personal_health_summary(user_key: str, lang="en") -> dict:
    rows=user_analysis_rows(user_key)
    if not rows:
        return {"total":0,"enough_data":False,"top_symptoms":[],"insights":[],"risk_distribution":{},"activity":[],"timeline":[],"duration_distribution":{}}
    symptoms=Counter(); risks=Counter(); durations=Counter(); months=Counter(); weekly=Counter(); red_count=0
    for row in rows:
        symptoms.update(row["symptoms"]); risks[(row.get("urgency") or "low").lower()]+=1
        if row.get("duration"): durations[str(row["duration"])]+=1
        ts=str(row.get("timestamp") or '')
        if len(ts)>=7: months[ts[:7]]+=1
        if len(ts)>=10:
            try:
                d=datetime.fromisoformat(ts.replace('Z','+00:00')).date()
                y,w,_=d.isocalendar(); weekly[f"{y}-W{w:02d}"]+=1
            except Exception: logging.getLogger(__name__).debug("Handled exception in personal_health_summary; fallback applied (handler 182)"); pass
        res=row.get("result") or {}
        if res.get("risk_level") == "urgent" or res.get("emergency") or res.get("risk_reasons"):
            red_count += int(bool(res.get("emergency") or any((x or {}).get("risk_level")=="urgent" for x in (res.get("risk_reasons") or []) if isinstance(x,dict))))
    latest=rows[0]
    now=datetime.now(timezone.utc)
    this=now.strftime('%Y-%m'); prev=(now.replace(day=1)-timedelta(days=1)).strftime('%Y-%m')
    ar=lang=="ar"; insights=[]
    if symptoms:
        name,count=symptoms.most_common(1)[0]
        insights.append({"type":"most_reported","icon":"💡","title":"الأكثر تسجيلًا" if ar else "Most Reported","text":(f"{name} هو أكثر عرض سجلته، وظهر {count} مرات." if ar else f"{name} was your most frequently reported symptom and appeared {count} times."),"evidence":{"symptom":name,"count":count}})
    insights.append({"type":"activity","icon":"📈","title":"النشاط" if ar else "Activity","text":(f"سجلت {months[this]} تحليلات خلال هذا الشهر." if ar else f"You completed {months[this]} analyses this month."),"evidence":{"month":this,"count":months[this]}})
    if durations:
        dur,count=durations.most_common(1)[0]
        insights.append({"type":"duration","icon":"📅","title":"نمط المدة" if ar else "Duration Pattern","text":(f"{dur} كانت مدة الأعراض الأكثر تسجيلًا ({count} مرات)." if ar else f"{dur} was the most frequently recorded symptom duration ({count} times)."),"evidence":{"duration":dur,"count":count}})
    if risks:
        risk,count=risks.most_common(1)[0]
        label=_risk_label(risk,"ar" if ar else "en")
        insights.append({"type":"risk","icon":"🟡","title":"نمط الخطورة" if ar else "Risk Pattern","text":(f"{label} كان مستوى الخطورة الأكثر تسجيلًا ({count} مرات)." if ar else f"{label} was the most frequently recorded risk level ({count} times)."),"evidence":{"risk":risk,"count":count}})
    if months[this] or months[prev]:
        if months[this] > months[prev]: cmp="أعلى" if ar else "higher"
        elif months[this] < months[prev]: cmp="أقل" if ar else "lower"
        else: cmp="مماثل" if ar else "the same as"
        insights.append({"type":"comparison","icon":"📊","title":"مقارنة الاستخدام" if ar else "Usage Comparison","text":(f"عدد تحليلاتك هذا الشهر {cmp} من الشهر الماضي ({months[this]} مقابل {months[prev]})." if ar else f"Your analysis count this month is {cmp} last month ({months[this]} vs {months[prev]})."),"evidence":{"current":months[this],"previous":months[prev]}})
    return {
        "total":len(rows), "enough_data":len(rows)>=2,
        "top_symptoms":[{"name":k,"count":v} for k,v in symptoms.most_common(8)],
        "latest":{"id":latest["id"],"date":latest["timestamp"],"urgency":latest["urgency"],"risk_label":_risk_label(latest["urgency"],"ar" if ar else "en"),"symptoms":latest["symptoms"]},
        "most_frequent_risk": _risk_label(risks.most_common(1)[0][0],"ar" if ar else "en") if risks else None,
        "red_flag_alerts":red_count,
        "risk_distribution":dict(risks), "duration_distribution":dict(durations),
        "activity":[{"period":k,"count":v} for k,v in sorted(months.items())],
        "weekly_activity":[{"period":k,"count":v} for k,v in sorted(weekly.items())],
        "timeline":[{"id":r["id"],"date":r["timestamp"],"symptoms":r["symptoms"],"urgency":r["urgency"],"risk_label":_risk_label(r["urgency"],"ar" if ar else "en")} for r in rows[:50]],
        "insights": insights if len(rows)>=2 else [],
    }


def smart_extract_symptoms(text: str, lang="ar") -> dict:
    """Deterministic bilingual extraction using the active Knowledge Base aliases.

    It never creates a new KB symptom. Unmatched text is returned for manual entry.
    """
    text=(text or '').strip()[:2000]
    if not text: return {"found":[],"unmatched":[],"confidence":"low"}
    # First ask the existing normalizer to resolve the entire utterance and common chunks.
    chunks=[text]
    for sep in [",","،"," and "," و ",";","؛",".","\n"]:
        chunks=[part for chunk in chunks for part in chunk.split(sep)]
    candidates=[p.strip() for p in chunks if p.strip()]
    # Add lightweight phrase windows so colloquial sentences can match aliases.
    tokens=re.findall(r"[\w\u0600-\u06FF-]+", text.lower())
    for n in (2,3,4,5):
        for i in range(max(0,len(tokens)-n+1)):
            candidates.append(" ".join(tokens[i:i+n]))
    found=[]; unmatched=[]; seen=set()
    for candidate in candidates:
        try: norm=medical_knowledge.normalize_symptoms([candidate], "en" if lang=="en" else "ar")
        except Exception: logging.getLogger(__name__).warning("Handled exception in smart_extract_symptoms; fallback applied (handler 240)"); continue
        for item in norm.get("canonical",[]) or []:
            slug=item.get("slug") if isinstance(item,dict) else str(item)
            if slug and slug not in seen:
                seen.add(slug); found.append(item)
    # Extra safe colloquial aliases mapped only to canonical symptoms that already exist.
    phrase_aliases={
        "بطني يعورني":"abdominal-pain","ألم في البطن":"abdominal-pain","أشعر بألم بطني":"abdominal-pain",
        "راسي يعورني":"headache","رأسي يعورني":"headache","ألم في الرأس":"headache","صداع":"headache",
        "غثيان":"nausea","ابي استفرغ":"vomiting","أبي أستفرغ":"vomiting","استفراغ":"vomiting",
        "تنميل":"numbness","تنمل":"numbness","خدر":"numbness","وخز":"numbness","نمنمة":"numbness",
        "ضيق نفس":"shortness-of-breath","صعوبة تنفس":"shortness-of-breath","ألم صدر":"chest-pain",
        "head pain":"headache","stomach pain":"abdominal-pain","belly pain":"abdominal-pain","feel sick":"nausea",
    }
    for phrase,slug in phrase_aliases.items():
        if clinical_text.contains_unnegated_phrase(text, phrase) and slug not in seen:
            try:
                norm=medical_knowledge.normalize_symptoms([slug], "en")
                item=(norm.get("canonical") or [None])[0]
                if item: seen.add(slug); found.append(item)
            except Exception: logging.getLogger(__name__).warning("Handled exception in smart_extract_symptoms; fallback applied (handler 261)"); pass
    # Keep only active KB entries; no auto-create.
    if not found: unmatched=[text]
    return {"found":found,"unmatched":unmatched,"confidence":"high" if len(found)>=1 else "low"}


def knowledge_graph_data() -> dict:
    """Return a true graph built only from persisted Medical Knowledge rows."""
    medical_knowledge.init_schema(); conn=db._conn(); c=conn.cursor()
    try:
        nodes=[]; edges=[]; linked_symptoms=set()
        c.execute("SELECT id,name_ar,name_en,description_ar,description_en,last_updated,status FROM mk_diseases WHERE status='active'")
        diseases=_rows(c)
        for d in diseases: nodes.append({"id":f"disease:{d['id']}","type":"disease",**d})
        c.execute("SELECT id,name_ar,name_en,description_ar,description_en,updated_at,status FROM mk_symptoms WHERE status='active'")
        symptoms=_rows(c)
        for s in symptoms: nodes.append({"id":f"symptom:{s['id']}","type":"symptom",**s})
        c.execute("SELECT id,name_ar,name_en,description_ar,description_en,last_updated,status FROM mk_red_flags WHERE status='active'")
        flags=_rows(c)
        for f in flags: nodes.append({"id":f"red_flag:{f['id']}","type":"red_flag",**f})
        c.execute("SELECT id,source_name,organization,official_url,source_type,verification_status,last_verified,status FROM mk_sources WHERE status='active'")
        sources=_rows(c)
        for s in sources: nodes.append({"id":f"source:{s['id']}","type":"source",**s})
        c.execute("SELECT disease_id,symptom_id,weight,typicality FROM mk_disease_symptoms WHERE status='active'")
        for d,s,w,t in c.fetchall():
            linked_symptoms.add(int(s)); edges.append({"from":f"disease:{d}","to":f"symptom:{s}","type":"has_symptom","weight":w,"label":t})
        if _table_exists(c,"mk_disease_sources"):
            c.execute("SELECT disease_id,source_id FROM mk_disease_sources")
            for d,s in c.fetchall(): edges.append({"from":f"disease:{d}","to":f"source:{s}","type":"supported_by"})
        if _table_exists(c,"mk_symptom_sources"):
            c.execute("SELECT symptom_id,source_id FROM mk_symptom_sources")
            for s,src in c.fetchall(): edges.append({"from":f"symptom:{s}","to":f"source:{src}","type":"supported_by"})
        # Red-flag required symptom relationships are stored as JSON slugs.
        slug_to_id={}
        c.execute("SELECT id,slug FROM mk_symptoms WHERE status='active'")
        for sid,slug in c.fetchall(): slug_to_id[str(slug)]=int(sid)
        c.execute("SELECT id,required_symptoms,source_id FROM mk_red_flags WHERE status='active'")
        for fid,req,src in c.fetchall():
            try: req=json.loads(req or '[]') if isinstance(req,str) else (req or [])
            except Exception: logging.getLogger(__name__).debug("Handled exception in knowledge_graph_data; fallback applied (handler 300)"); req=[]
            for slug in req:
                sid=slug_to_id.get(str(slug))
                if sid: edges.append({"from":f"red_flag:{fid}","to":f"symptom:{sid}","type":"triggered_by"})
            if src: edges.append({"from":f"red_flag:{fid}","to":f"source:{src}","type":"supported_by"})
        verified=sum(1 for s in sources if s.get("verification_status")=="verified")
        return {"nodes":nodes,"edges":edges,"stats":{"diseases":len(diseases),"symptoms":len(symptoms),"red_flags":len(flags),"sources":len(sources),"relationships":len(edges),"verified_sources":verified,"unlinked_symptoms":sum(1 for s in symptoms if int(s['id']) not in linked_symptoms)}}
    finally: conn.close()


def _safe_unknown_label(value: str) -> str:
    """Return a privacy-minimized unknown-symptom label for aggregate Admin metrics.

    Free text can accidentally contain identifiers. Only short symptom-like phrases
    without email/URL/phone patterns are surfaced; everything else is grouped.
    """
    text = re.sub(r"\s+", " ", str(value or "")).strip()[:160]
    if not text:
        return "Unrecognized input"
    if re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text):
        return "Unrecognized free-text symptom"
    if re.search(r"https?://|www\.", text, re.I):
        return "Unrecognized free-text symptom"
    digits = re.sub(r"\D", "", text)
    if len(digits) >= 7:
        return "Unrecognized free-text symptom"
    words = re.findall(r"[\w\u0600-\u06FF-]+", text)
    if len(words) > 8 or len(text) > 70:
        return "Unrecognized free-text symptom"
    return text


def ai_performance(days=30) -> dict:
    platform_v2.init_schema(); privacy_features.init_schema(); days=max(1,min(365,int(days)))
    since=(datetime.now(timezone.utc)-timedelta(days=days)).isoformat()
    conn=db._conn(); c=conn.cursor()
    try:
        c.execute(f"SELECT service,path,response_status,response_ms,created_at FROM ss_usage_events WHERE created_at>={PH} AND service IN ('assistant','symptom_analysis') ORDER BY created_at",(since,))
        events=_rows(c)
        c.execute("SELECT res.data FROM results res JOIN records r ON r.id=res.record_id AND r.user_hash=res.user_hash WHERE COALESCE(r.analytics_eligible,0)=1")
        result_rows=[_parse_result(r[0]) for r in c.fetchall()]
    finally: conn.close()
    total=len(events); failed=sum(1 for e in events if int(e.get('response_status') or 0)>=400); success=total-failed
    response=[int(e['response_ms']) for e in events if e.get('response_ms') is not None]
    daily=Counter(str(e.get('created_at') or '')[:10] for e in events)
    daily_response=defaultdict(list)
    for e in events:
        if e.get('response_ms') is not None:
            daily_response[str(e.get('created_at') or '')[:10]].append(int(e.get('response_ms') or 0))
    feature=Counter(e.get('service') or 'unknown' for e in events)
    error_types=Counter(str(e.get('response_status') or 'unknown') for e in events if int(e.get('response_status') or 0)>=400)
    recent_failures=[{"timestamp":e.get("created_at"),"service":e.get("service") or "unknown","status":int(e.get("response_status") or 0)} for e in events if int(e.get('response_status') or 0)>=400][-20:][::-1]
    unknown=Counter(); quality_scores=[]; quality_sufficient=0; quality_missing=Counter()
    for res in result_rows:
        norm=res.get('symptom_normalization') or {}
        for item in norm.get('unmatched') or []: unknown[_safe_unknown_label(item)]+=1
        q=res.get('data_quality') or {}
        if isinstance(q,dict) and q.get('score') is not None:
            try: quality_scores.append(float(q.get('score')))
            except Exception: logging.getLogger(__name__).debug("Handled exception in ai_performance; fallback applied (handler 359)"); pass
            if q.get('sufficient'): quality_sufficient += 1
            for item in q.get('missing') or []:
                if isinstance(item,dict):
                    label=str(item.get('key') or item.get('label') or '').strip()
                    if label: quality_missing[label]+=1
    qn=len(quality_scores)
    return {"days":days,"total_ai_requests":total,"successful":success,"failed":failed,"avg_response_ms":round(sum(response)/len(response)) if response else None,"fastest_ms":min(response) if response else None,"slowest_ms":max(response) if response else None,"success_rate":round(success*100/total,1) if total else 0,"failure_rate":round(failed*100/total,1) if total else 0,"timeline":[{"date":k,"count":v} for k,v in sorted(daily.items())],"response_timeline":[{"date":k,"count":round(sum(v)/len(v),1)} for k,v in sorted(daily_response.items()) if v],"features":[{"name":k,"count":v} for k,v in feature.most_common()],"errors":[{"type":k,"count":v} for k,v in error_types.most_common()],"recent_failures":recent_failures,"unrecognized":[{"name":k,"count":v} for k,v in unknown.most_common(20)],"data_quality":{"sample_size":qn,"average_score":round(sum(quality_scores)/qn,1) if qn else None,"sufficient_pct":round(quality_sufficient*100/qn,1) if qn else 0,"additional_info_pct":round((qn-quality_sufficient)*100/qn,1) if qn else 0,"most_missing":[{"name":k,"count":v,"percentage":round(v*100/qn,1) if qn else 0} for k,v in quality_missing.most_common(10)]}}


def _daily_metric(metric: str, days=30):
    privacy_features.init_schema()
    since=datetime.now(timezone.utc)-timedelta(days=days)
    conn=db._conn(); c=conn.cursor(); counts=Counter(); samples=defaultdict(list)
    try:
        if metric=='analyses':
            c.execute(f"SELECT timestamp FROM records WHERE timestamp>={PH} AND COALESCE(analytics_eligible,0)=1",(since.isoformat(),)); rows=c.fetchall()
            for (ts,) in rows: counts[str(ts)[:10]]+=1
        elif metric in {'errors','ai_requests'}:
            where="service IN ('assistant','symptom_analysis')"
            if metric=='errors': where += " AND response_status>=400"
            c.execute(f"SELECT created_at FROM ss_usage_events WHERE created_at>={PH} AND {where}",(since.isoformat(),)); rows=c.fetchall()
            for (ts,) in rows: counts[str(ts)[:10]]+=1
        elif metric=='response_time':
            c.execute(f"SELECT created_at,response_ms FROM ss_usage_events WHERE created_at>={PH} AND service IN ('assistant','symptom_analysis') AND response_ms IS NOT NULL",(since.isoformat(),))
            for ts,ms in c.fetchall(): samples[str(ts)[:10]].append(float(ms))
            for day,vals in samples.items(): counts[day]=sum(vals)/len(vals)
        elif metric=='unknown_symptoms':
            c.execute(f"SELECT r.timestamp,res.data FROM records r JOIN results res ON res.record_id=r.id AND res.user_hash=r.user_hash WHERE r.timestamp>={PH} AND COALESCE(r.analytics_eligible,0)=1",(since.isoformat(),))
            for ts,raw in c.fetchall():
                res=_parse_result(raw); unmatched=((res.get('symptom_normalization') or {}).get('unmatched') or [])
                counts[str(ts)[:10]] += len(unmatched)
        return counts
    finally: conn.close()

def anomaly_detection() -> dict:
    """Simple transparent baseline detector. It refuses to infer when history is sparse."""
    findings=[]
    for metric in ('analyses','ai_requests','errors','unknown_symptoms','response_time'):
        counts=_daily_metric(metric,30)
        ordered=sorted(counts.items())
        if len(ordered)<7:
            continue
        values=[v for _,v in ordered[:-1]]; current=ordered[-1][1]
        if len(values)<6: continue
        mean=sum(values)/len(values); variance=sum((v-mean)**2 for v in values)/len(values); sd=math.sqrt(variance)
        low=max(0,mean-2*sd); high=mean+2*sd
        if current<low or current>high:
            findings.append({"metric":metric,"date":ordered[-1][0],"current":current,"expected_low":round(low,1),"expected_high":round(high,1),"severity":"critical" if sd and abs(current-mean)>3*sd else "warning","status":"unusual_activity"})
    return {"sufficient_data":bool(findings) or any(len(_daily_metric(m,30))>=7 for m in ('analyses','ai_requests','errors','unknown_symptoms','response_time')),"findings":findings}


def automatic_insights() -> dict:
    privacy_features.init_schema()
    now=datetime.now(timezone.utc); cur_start=now-timedelta(days=30); prev_start=now-timedelta(days=60)
    conn=db._conn(); c=conn.cursor()
    try:
        c.execute(f"SELECT timestamp,symptoms,urgency FROM records WHERE timestamp>={PH} AND COALESCE(analytics_eligible,0)=1",(prev_start.isoformat(),)); rows=c.fetchall()
        c.execute(f"SELECT created_at,service,response_status FROM ss_usage_events WHERE created_at>={PH}",(prev_start.isoformat(),)); events=c.fetchall()
    finally: conn.close()
    cur=[r for r in rows if str(r[0])>=cur_start.isoformat()]; prev=[r for r in rows if str(r[0])<cur_start.isoformat()]
    insights=[]
    def compare(label,curv,prevv,category='trend'):
        total=curv+prevv
        if total<10: return
        change=((curv-prevv)/prevv*100) if prevv else (100.0 if curv else 0.0)
        if abs(change)<20: return
        conf='high' if total>=100 else 'moderate'
        insights.append({"category":category,"title":label,"current":curv,"previous":prevv,"change_pct":round(change,1),"direction":"increase" if change>0 else "decrease","confidence":conf})
    compare('Symptom analyses',len(cur),len(prev),'trend')
    cur_ai=sum(1 for e in events if str(e[0])>=cur_start.isoformat() and e[1] in ('assistant','symptom_analysis'))
    prev_ai=sum(1 for e in events if str(e[0])<cur_start.isoformat() and e[1] in ('assistant','symptom_analysis'))
    compare('AI usage',cur_ai,prev_ai,'ai_usage')
    cur_err=sum(1 for e in events if str(e[0])>=cur_start.isoformat() and int(e[2] or 0)>=400)
    prev_err=sum(1 for e in events if str(e[0])<cur_start.isoformat() and int(e[2] or 0)>=400)
    compare('Failed requests',cur_err,prev_err,'comparison')
    # Data quality: unmatched symptom phrases, counted without user identity.
    try:
        conn=db._conn(); c=conn.cursor(); c.execute(f"SELECT r.timestamp,res.data FROM records r JOIN results res ON res.record_id=r.id AND res.user_hash=r.user_hash WHERE r.timestamp>={PH} AND COALESCE(r.analytics_eligible,0)=1",(prev_start.isoformat(),)); rr=c.fetchall(); conn.close()
        cur_unknown=prev_unknown=0
        for ts,raw in rr:
            n=len(((_parse_result(raw).get('symptom_normalization') or {}).get('unmatched') or []))
            if str(ts)>=cur_start.isoformat(): cur_unknown+=n
            else: prev_unknown+=n
        compare('Unknown symptoms',cur_unknown,prev_unknown,'data_quality')
    except Exception:
        logging.getLogger(__name__).warning("Handled exception in automatic_insights; fallback applied (handler 444)")
        pass
    return {"sufficient_data":len(rows)+len(events)>=10,"insights":insights}


def ask_your_data(question: str, lang='en') -> dict:
    """Natural-language query router over a strict allow-list of aggregate queries.

    No user-provided SQL is ever executed. Only predefined read-only aggregations run.
    """
    privacy_features.init_schema(); platform_v2.init_schema()
    q=(question or '').strip().lower()[:500]
    if not q: return {"ok":False,"error":"empty_question"}
    # Explicitly reject SQL-like administrative verbs even though no SQL path exists.
    if re.search(r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke)\b",q,re.I):
        return {"ok":False,"error":"read_only_only"}
    conn=db._conn(); c=conn.cursor(); ar=lang=='ar'
    try:
        threshold=max(3,min(20,int(os.environ.get('ANALYTICS_PRIVACY_THRESHOLD','5') or 5)))
    except (TypeError,ValueError):
        threshold=5
    def not_enough():
        return {"ok":True,"type":"bar","sufficient_data":False,"answer":("البيانات غير كافية للإجابة عن هذا السؤال." if ar else "Not enough data to answer this question."),"data":[]}
    try:
        if any(x in q for x in ['أكثر','top','most common']) and any(x in q for x in ['عرض','symptom']):
            params=[]; where="COALESCE(analytics_eligible,0)=1"
            if any(x in q for x in ['هذا الشهر','this month']):
                start=datetime.now(timezone.utc).replace(day=1,hour=0,minute=0,second=0,microsecond=0).isoformat();where+=f" AND timestamp>={PH}";params.append(start)
            c.execute("SELECT user_hash,symptoms FROM records WHERE "+where,tuple(params)); counter=Counter();users=defaultdict(set)
            for user_hash,raw in c.fetchall():
                for symptom in {s.strip() for s in str(raw or '').split(',') if s.strip()}:
                    counter[symptom]+=1;users[symptom].add(str(user_hash))
            data=[{"label":k,"value":v} for k,v in counter.most_common() if len(users[k])>=threshold][:5]
            if not data:return not_enough()
            return {"ok":True,"type":"bar","sufficient_data":True,"answer":("أكثر الأعراض تسجيلًا موضحة في الرسم أدناه." if ar else "The most frequently recorded symptoms are shown below."),"data":data}
        if any(x in q for x in ['هذا الشهر','this month','الشهر الماضي','last month','compare']) and any(x in q for x in ['تحليل','analys']):
            now=datetime.now(timezone.utc); start=now.replace(day=1,hour=0,minute=0,second=0,microsecond=0); prev_start=(start-timedelta(days=1)).replace(day=1)
            c.execute(f"SELECT timestamp FROM records WHERE timestamp>={PH} AND COALESCE(analytics_eligible,0)=1",(prev_start.isoformat(),)); ts=[str(r[0]) for r in c.fetchall()]
            cur=sum(1 for x in ts if x>=start.isoformat()); prev=sum(1 for x in ts if x<start.isoformat())
            if not ts:return not_enough()
            return {"ok":True,"type":"bar","sufficient_data":True,"answer":(f"هذا الشهر: {cur} تحليل، الشهر الماضي: {prev}." if ar else f"This month: {cur} analyses; last month: {prev}."),"data":[{"label":"Current","value":cur},{"label":"Previous","value":prev}]}
        if any(x in q for x in ['فئة عمرية','age group','age']) and any(x in q for x in ['متوسط','average','mean']) and any(x in q for x in ['شدة','severity']):
            c.execute("SELECT user_hash,age,severity FROM records WHERE age IS NOT NULL AND severity IS NOT NULL AND COALESCE(analytics_eligible,0)=1");groups=defaultdict(list);users=defaultdict(set)
            for user_hash,age,severity in c.fetchall():
                try:a=int(age);sev=float(severity)
                except (TypeError,ValueError):continue
                key='0-17' if a<18 else '18-25' if a<=25 else '26-35' if a<=35 else '36-45' if a<=45 else '46-55' if a<=55 else '56+'
                groups[key].append(sev);users[key].add(str(user_hash))
            data=[{"label":key,"value":round(sum(vals)/len(vals),2)} for key,vals in groups.items() if len(users[key])>=threshold]
            data.sort(key=lambda item:item['value'],reverse=True)
            if not data:return not_enough()
            top=data[0]
            return {"ok":True,"type":"bar","sufficient_data":True,"answer":(f"أعلى متوسط شدة كان في الفئة {top['label']} وبلغ {top['value']}." if ar else f"The highest average severity was {top['value']} in age group {top['label']}."),"data":data}
        if any(x in q for x in ['فئة عمرية','age group','age']) and any(x in q for x in ['أكثر','most','top']):
            c.execute("SELECT user_hash,age FROM records WHERE age IS NOT NULL AND COALESCE(analytics_eligible,0)=1"); groups=Counter();users=defaultdict(set)
            for user_hash,age in c.fetchall():
                try:a=int(age)
                except (TypeError, ValueError, OverflowError):continue
                key='0-17' if a<18 else '18-29' if a<30 else '30-44' if a<45 else '45-59' if a<60 else '60+'
                groups[key]+=1;users[key].add(str(user_hash))
            data=[{"label":k,"value":v} for k,v in groups.most_common() if len(users[k])>=threshold]
            if not data:return not_enough()
            return {"ok":True,"type":"bar","sufficient_data":True,"answer":("توزيع استخدام تحليل الأعراض حسب الفئة العمرية." if ar else "Symptom-analysis usage by age group."),"data":data}
        if any(x in q for x in ['عاجل','urgent']) and any(x in q for x in ['نسبة','percent','rate']):
            c.execute("SELECT urgency FROM records WHERE COALESCE(analytics_eligible,0)=1"); vals=[str(r[0] or '').lower() for r in c.fetchall()]; n=len(vals); urgent=sum(1 for v in vals if v=='high'); pct=round(urgent*100/n,1) if n else 0
            if n<threshold:return not_enough()
            return {"ok":True,"type":"donut","sufficient_data":True,"answer":(f"نسبة التحليلات المصنفة عاجلة: {pct}% ({urgent} من {n})." if ar else f"Urgent assessments: {pct}% ({urgent} of {n})."),"data":[{"label":"Urgent","value":urgent},{"label":"Other","value":n-urgent}]}
        if any(x in q for x in ['لغة','language','arabic','english','العربية','الإنجليزية']):
            c.execute("SELECT lang,COUNT(*) FROM records WHERE COALESCE(analytics_eligible,0)=1 GROUP BY lang"); data=[{"label":r[0] or 'unknown',"value":int(r[1])} for r in c.fetchall()]
            if not data:return not_enough()
            return {"ok":True,"type":"donut","sufficient_data":True,"answer":("توزيع التحليلات حسب اللغة." if ar else "Analysis distribution by language."),"data":data}
        if any(x in q for x in ['جوال','mobile','desktop','device']):
            c.execute("SELECT device_type,COUNT(*) FROM ss_usage_events GROUP BY device_type"); data=[{"label":r[0] or 'unknown',"value":int(r[1])} for r in c.fetchall()]
            if not data:return not_enough()
            return {"ok":True,"type":"bar","sufficient_data":True,"answer":("توزيع الاستخدام حسب نوع الجهاز." if ar else "Usage distribution by device type."),"data":data}
        return {"ok":False,"error":"unsupported_question","examples":["ما أكثر 5 أعراض تم تسجيلها؟","قارن عدد التحليلات هذا الشهر بالشهر الماضي.","ما أكثر فئة عمرية استخدمت تحليل الأعراض؟","ما نسبة الحالات العاجلة؟"]}
    finally: conn.close()


def _sources_export_rows(cur):
    cur.execute("SELECT id,source_name,official_url,source_type,verification_status,last_verified,status FROM mk_sources ORDER BY id")
    rows=_rows(cur); out=[]
    for s in rows:
        related_d=[]; related_s=[]
        if _table_exists(cur,'mk_disease_sources'):
            cur.execute(f"SELECT d.name_en FROM mk_disease_sources l JOIN mk_diseases d ON d.id=l.disease_id WHERE l.source_id={PH}",(s['id'],)); related_d=[r[0] for r in cur.fetchall()]
        if _table_exists(cur,'mk_symptom_sources'):
            cur.execute(f"SELECT x.name_en FROM mk_symptom_sources l JOIN mk_symptoms x ON x.id=l.symptom_id WHERE l.source_id={PH}",(s['id'],)); related_s=[r[0] for r in cur.fetchall()]
        out.append([s['id'],s['source_name'],s['official_url'],', '.join(related_d),', '.join(related_s),s['source_type'],s['verification_status'],s['last_verified'],s['status']])
    return out


def export_admin_excel() -> io.BytesIO:
    """Create a fresh anonymized workbook from the current database."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

    medical_knowledge.init_schema(); platform_v2.init_schema(); privacy_features.init_schema()
    conn=db._conn(); c=conn.cursor()
    try:
        c.execute("SELECT r.id,r.age,r.gender,r.symptoms,r.duration,r.severity,r.urgency,r.timestamp,res.data FROM records r LEFT JOIN results res ON res.record_id=r.id AND res.user_hash=r.user_hash WHERE COALESCE(r.analytics_eligible,0)=1 ORDER BY r.id")
        analyses=[]; symptom_counter=Counter(); risk_counter=Counter(); age_counter=Counter(); gender_counter=Counter(); duration_counter=Counter(); condition_counter=Counter(); analyses_by_date=Counter()
        for rid,age,gender,syms,dur,sev,urg,ts,res_raw in c.fetchall():
            res=_parse_result(res_raw); sym_list=[s.strip() for s in str(syms or '').split(',') if s.strip()]
            symptom_counter.update(sym_list); risk_counter[str(urg or 'unknown')]+=1; gender_counter[str(gender or 'unknown')]+=1; duration_counter[str(dur or 'unknown')]+=1
            try:
                a=int(age); age_key='0-17' if a<18 else '18-29' if a<30 else '30-44' if a<45 else '45-59' if a<60 else '60+'
            except (TypeError, ValueError, OverflowError): age_key='unknown'
            age_counter[age_key]+=1; analyses_by_date[str(ts or '')[:10]]+=1
            matches=res.get('knowledge_matches') or []
            for m in matches:
                if isinstance(m,dict): condition_counter[str(m.get('name_en') or m.get('name_ar') or m.get('slug') or '')]+=1
            flags=[]
            for rr in res.get('risk_reasons') or []:
                if isinstance(rr,dict): flags.append(str(rr.get('name') or rr.get('message') or ''))
            analyses.append([rid,age,gender,', '.join(sym_list),dur,sev,urg,res.get('possible_conditions',''),'; '.join(x for x in flags if x),ts])
        c.execute("SELECT id,name_ar,name_en,description_ar,description_en,severity,red_flags_ar,red_flags_en,status,last_updated FROM mk_diseases ORDER BY id")
        diseases=[]
        for row in c.fetchall():
            did=row[0]; c.execute(f"SELECT s.name_en FROM mk_disease_symptoms ds JOIN mk_symptoms s ON s.id=ds.symptom_id WHERE ds.disease_id={PH} AND ds.status='active'",(did,)); rel=', '.join(r[0] for r in c.fetchall())
            src=''
            if _table_exists(c,'mk_disease_sources'):
                c.execute(f"SELECT src.source_name FROM mk_disease_sources l JOIN mk_sources src ON src.id=l.source_id WHERE l.disease_id={PH}",(did,)); src=', '.join(r[0] for r in c.fetchall())
            diseases.append([did,row[1],row[2],row[3] or row[4],rel,row[5],row[6] or row[7],src,row[8],row[9]])
        sources=_sources_export_rows(c)
        has_meds=_table_exists(c,'mk_medications')
        medications=[]
        if has_meds:
            c.execute("SELECT * FROM mk_medications ORDER BY id"); cols=[d[0] for d in c.description]
            for raw in c.fetchall(): medications.append(dict(zip(cols,raw)))
    finally: conn.close()

    wb=Workbook(); wb.remove(wb.active)
    navy='163B5C'; 
    def add_sheet(name, headers, rows):
        ws=wb.create_sheet(name); ws.append(headers)
        for row in rows: ws.append(row)
        for cell in ws[1]: cell.font=Font(bold=True,color='FFFFFF'); cell.fill=PatternFill('solid',fgColor=navy); cell.alignment=Alignment(horizontal='center')
        ws.freeze_panes='A2'; ws.auto_filter.ref=ws.dimensions
        for col in range(1,len(headers)+1):
            max_len=max([len(str(ws.cell(r,col).value or '')) for r in range(1,min(ws.max_row,200)+1)] or [10]); ws.column_dimensions[get_column_letter(col)].width=min(42,max(12,max_len+2))
        for row in ws.iter_rows():
            for cell in row: cell.alignment=Alignment(vertical='top',wrap_text=True)
        return ws
    add_sheet('Analyses',['Analysis ID','Age','Gender','Symptoms','Symptom Duration','Pain Severity','Risk Level','Possible Conditions / Analysis Result','Red Flags Detected','Analysis Date'],analyses)
    if has_meds:
        headers=['Medication ID','Medication Name','Category','Related Condition','General Use','Source','Last Updated','Status']
        rows=[]
        for m in medications: rows.append([m.get('id'),m.get('name') or m.get('name_en') or m.get('medication_name'),m.get('category'),m.get('related_condition'),m.get('general_use'),m.get('source'),m.get('last_updated') or m.get('updated_at'),m.get('status')])
        add_sheet('Medications',headers,rows)
    add_sheet('Diseases',['Disease ID','Arabic Name','English Name','Description','Related Symptoms','Severity','Red Flags','Source','Status','Last Updated'],diseases)
    add_sheet('Medical Sources',['Source ID','Source Name','URL','Related Disease','Related Symptoms','Source Type','Verification Status','Last Verified','Status'],sources)
    analytics_rows=[['Total Users',platform_v2.analytics_summary(30).get('total_users',0)],['Total Analyses',len(analyses)],['AI Assistant Usage',platform_v2.analytics_summary(30).get('assistant_uses',0)]]
    analytics_rows += [[f"Most Common Symptom: {k}",v] for k,v in symptom_counter.most_common(10)]
    analytics_rows += [[f"Most Common Possible Condition: {k}",v] for k,v in condition_counter.most_common(10) if k]
    analytics_rows += [[f"Risk: {k}",v] for k,v in risk_counter.items()]
    analytics_rows += [[f"Age: {k}",v] for k,v in age_counter.items()]
    analytics_rows += [[f"Gender: {k}",v] for k,v in gender_counter.items()]
    analytics_rows += [[f"Duration: {k}",v] for k,v in duration_counter.items()]
    analytics_rows += [[f"Analyses {k}",v] for k,v in sorted(analyses_by_date.items())]
    add_sheet('Analytics',['Metric','Value'],analytics_rows)
    out=io.BytesIO(); wb.save(out); out.seek(0); return out


def export_audit_excel() -> io.BytesIO:
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill
    rows=platform_v2.audit_log(limit=1000)
    wb=Workbook(); ws=wb.active; ws.title='Audit Log'; headers=['Event ID','Timestamp','Admin User ID','Admin Account','Action','Entity Type','Entity ID','Result']
    ws.append(headers)
    for r in rows:
        action=str(r.get('action') or '')
        result='failed' if ('failed' in action or 'denied' in action) else ('expired' if 'timeout' in action else 'success')
        ws.append([r.get('id'),r.get('timestamp'),r.get('admin_id'),db.OWNER_ADMIN_EMAIL if r.get('admin_id') else 'System',action,r.get('entity_type'),r.get('entity_id'),result])
    for c in ws[1]: c.font=Font(bold=True,color='FFFFFF'); c.fill=PatternFill('solid',fgColor='163B5C')
    out=io.BytesIO(); wb.save(out); out.seek(0); return out
