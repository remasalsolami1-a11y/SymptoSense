"""Privacy-by-design consent, user data controls, doctor handoff, and anonymous analytics.

This module never treats aggregate associations as medical causality. Consent logs contain
no health content. Temporary handoff links store only the user-selected summary payload.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import os
import secrets
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import db

PH = db.PH
CONSENT_VERSION = os.environ.get("CONSENT_VERSION", "1.0")
PRIVACY_POLICY_VERSION = os.environ.get("PRIVACY_POLICY_VERSION", "1.0")
try:
    PRIVACY_THRESHOLD = max(3, min(20, int(os.environ.get("ANALYTICS_PRIVACY_THRESHOLD", "5") or 5)))
except (TypeError, ValueError):
    PRIVACY_THRESHOLD = 5
_EPHEMERAL_CONSENT_SECRET = secrets.token_bytes(32)
# This project does not currently train/fine-tune an AI model from user health records.
AI_IMPROVEMENT_ACTIVE = False


def _now():
    return datetime.now(timezone.utc).isoformat()


def _secret():
    configured = os.environ.get("CONSENT_HASH_SECRET") or os.environ.get("WEB_SECRET")
    return configured.encode() if configured else _EPHEMERAL_CONSENT_SECRET


def _subject_hash(subject_key: str) -> str:
    return hmac.new(_secret(), str(subject_key or "guest").encode(), hashlib.sha256).hexdigest()


def _token_hash(token: str) -> str:
    return hashlib.sha256((token or "").encode()).hexdigest()


def _rows(c):
    cols = [d[0] for d in c.description]
    return [dict(zip(cols, row)) for row in c.fetchall()]


def init_schema():
    db.init_db()
    conn = db._conn(); c = conn.cursor()
    serial = "SERIAL PRIMARY KEY" if db.USE_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"
    try:
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS ss_consent_state (
                subject_hash TEXT PRIMARY KEY,
                user_id INTEGER,
                service_usage INTEGER NOT NULL DEFAULT 0,
                analytics_research INTEGER NOT NULL DEFAULT 0,
                consent_version TEXT NOT NULL,
                privacy_policy_version TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS ss_consent_log (
                id {serial}, subject_hash TEXT NOT NULL, user_id INTEGER,
                consent_type TEXT NOT NULL, consent_status TEXT NOT NULL,
                consent_version TEXT NOT NULL, privacy_policy_version TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_consent_log_subject ON ss_consent_log(subject_hash,timestamp)")
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS ss_privacy_events (
                id {serial}, subject_hash TEXT NOT NULL, action TEXT NOT NULL,
                metadata TEXT, timestamp TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_privacy_events_time ON ss_privacy_events(timestamp)")
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS ss_handoff_links (
                id {serial}, owner_hash TEXT NOT NULL, token_hash TEXT UNIQUE NOT NULL,
                payload_json TEXT NOT NULL, created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL, revoked_at TEXT
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_handoff_exp ON ss_handoff_links(expires_at)")
        # Mark whether an analysis was eligible for optional health analytics at collection time.
        if db.USE_POSTGRES:
            c.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s", ("records",))
            cols = {r[0] for r in c.fetchall()}
        else:
            c.execute("PRAGMA table_info(records)")
            cols = {r[1] for r in c.fetchall()}
        if "analytics_eligible" not in cols:
            c.execute("ALTER TABLE records ADD COLUMN analytics_eligible INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    finally:
        conn.close()


def get_consent(subject_key: str, user_id=None) -> dict:
    init_schema(); sh = _subject_hash(subject_key)
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute("SELECT service_usage,analytics_research,consent_version,privacy_policy_version,updated_at FROM ss_consent_state WHERE subject_hash=%s" % PH, (sh,))
        row = c.fetchone()
    finally:
        conn.close()
    if not row:
        return {"service_usage": False, "analytics_research": False, "ai_improvement": False,
                "consent_version": CONSENT_VERSION, "privacy_policy_version": PRIVACY_POLICY_VERSION,
                "needs_review": True, "updated_at": None}
    return {"service_usage": bool(row[0]), "analytics_research": bool(row[1]), "ai_improvement": False,
            "consent_version": row[2], "privacy_policy_version": row[3], "updated_at": row[4],
            "needs_review": row[2] != CONSENT_VERSION or row[3] != PRIVACY_POLICY_VERSION}


def _log_consent(c, sh, user_id, consent_type, status):
    c.execute(
        "INSERT INTO ss_consent_log(subject_hash,user_id,consent_type,consent_status,consent_version,privacy_policy_version,timestamp) "
        f"VALUES ({','.join([PH]*7)})",
        (sh, int(user_id) if user_id else None, consent_type, status, CONSENT_VERSION, PRIVACY_POLICY_VERSION, _now()),
    )


def log_privacy_event(subject_key: str, action: str, metadata=None):
    init_schema(); sh = _subject_hash(subject_key)
    safe = {}
    for k, v in (metadata or {}).items():
        if k in {"status", "consent_type", "format", "scope", "period", "count"}:
            safe[k] = v
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute("INSERT INTO ss_privacy_events(subject_hash,action,metadata,timestamp) VALUES(%s,%s,%s,%s)".replace("%s", PH),
                  (sh, str(action)[:80], json.dumps(safe, ensure_ascii=False), _now()))
        conn.commit()
    finally:
        conn.close()


def save_consent(subject_key: str, user_id, service_usage: bool, analytics_research: bool) -> dict:
    init_schema(); sh = _subject_hash(subject_key)
    previous = get_consent(subject_key, user_id)
    now = _now(); conn = db._conn(); c = conn.cursor()
    try:
        vals = (sh, int(user_id) if user_id else None, int(bool(service_usage)), int(bool(analytics_research)), CONSENT_VERSION, PRIVACY_POLICY_VERSION, now)
        if db.USE_POSTGRES:
            c.execute("INSERT INTO ss_consent_state(subject_hash,user_id,service_usage,analytics_research,consent_version,privacy_policy_version,updated_at) VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(subject_hash) DO UPDATE SET user_id=EXCLUDED.user_id,service_usage=EXCLUDED.service_usage,analytics_research=EXCLUDED.analytics_research,consent_version=EXCLUDED.consent_version,privacy_policy_version=EXCLUDED.privacy_policy_version,updated_at=EXCLUDED.updated_at", vals)
        else:
            c.execute("INSERT INTO ss_consent_state(subject_hash,user_id,service_usage,analytics_research,consent_version,privacy_policy_version,updated_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(subject_hash) DO UPDATE SET user_id=excluded.user_id,service_usage=excluded.service_usage,analytics_research=excluded.analytics_research,consent_version=excluded.consent_version,privacy_policy_version=excluded.privacy_policy_version,updated_at=excluded.updated_at", vals)
        # Each explicit choice is logged; false after true is a withdrawal, otherwise a decline.
        _log_consent(c, sh, user_id, "service_usage", "granted" if service_usage else ("withdrawn" if previous.get("service_usage") else "declined"))
        _log_consent(c, sh, user_id, "analytics_research", "granted" if analytics_research else ("withdrawn" if previous.get("analytics_research") else "declined"))
        conn.commit()
    finally:
        conn.close()
    log_privacy_event(subject_key, "privacy_settings_changed", {"status": "saved"})
    if bool(previous.get("analytics_research")) != bool(analytics_research):
        log_privacy_event(subject_key, "analytics_consent_granted" if analytics_research else "analytics_consent_withdrawn", {"status": "granted" if analytics_research else "withdrawn"})
    elif not analytics_research and not previous.get("updated_at"):
        log_privacy_event(subject_key, "analytics_consent_declined", {"status": "declined"})
    if bool(previous.get("service_usage")) != bool(service_usage):
        log_privacy_event(subject_key, "service_consent_granted" if service_usage else "service_consent_withdrawn", {"status": "granted" if service_usage else "withdrawn"})
    return get_consent(subject_key, user_id)


def withdraw_analytics(subject_key: str, user_id=None) -> dict:
    cur = get_consent(subject_key, user_id)
    updated = save_consent(subject_key, user_id, cur.get("service_usage", False), False)
    # Privacy-by-design: once analytics consent is withdrawn, records that are
    # still retained in the live database stop being eligible for future
    # aggregate analytics. This cannot undo already-produced anonymous
    # aggregates, but it prevents subsequent queries from including them.
    uh = db._hash_user(subject_key)
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute("UPDATE records SET analytics_eligible=0 WHERE user_hash=%s" % PH, (uh,))
        conn.commit()
    finally:
        conn.close()
    return updated


def consent_history(subject_key: str, limit=50):
    init_schema(); sh = _subject_hash(subject_key)
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute("SELECT consent_type,consent_status,consent_version,privacy_policy_version,timestamp FROM ss_consent_log WHERE subject_hash=%s ORDER BY timestamp DESC LIMIT %s" % (PH, PH), (sh, int(limit)))
        rows = c.fetchall()
    finally:
        conn.close()
    return [{"consent_type":r[0],"status":r[1],"consent_version":r[2],"privacy_policy_version":r[3],"timestamp":r[4]} for r in rows]


def set_record_analytics_eligibility(record_id: int, eligible: bool):
    init_schema(); conn = db._conn(); c = conn.cursor()
    try:
        c.execute("UPDATE records SET analytics_eligible=%s WHERE id=%s" % (PH, PH), (int(bool(eligible)), int(record_id)))
        conn.commit()
    finally:
        conn.close()


def stored_data_types(account_user_id: int, data_owner_key: str) -> dict:
    """Report only categories that are actually present for this account."""
    init_schema(); uid=int(account_user_id); uh=db._hash_user(data_owner_key)
    conn=db._conn(); c=conn.cursor()
    def exists(sql, params):
        try:
            c.execute(sql, params); return bool(c.fetchone()[0])
        except Exception:
            return False
    try:
        return {
            "profile_information": bool(db.get_ss_user(uid)),
            "health_profile": exists("SELECT COUNT(*) FROM ss_health_profiles WHERE user_id=%s" % PH,(uid,)),
            "symptom_information": exists("SELECT COUNT(*) FROM records WHERE user_hash=%s" % PH,(uh,)),
            "analysis_history": exists("SELECT COUNT(*) FROM records WHERE user_hash=%s" % PH,(uh,)),
            "medication_reminders": exists("SELECT COUNT(*) FROM med_plans WHERE user_hash=%s" % PH,(uh,)),
            "assistant_history": exists("SELECT COUNT(*) FROM ss_chat_history WHERE user_id=%s" % PH,(uid,)),
            "reports": exists("SELECT COUNT(*) FROM ss_handoff_links WHERE owner_hash=%s" % PH,(uh,)),
        }
    finally:
        conn.close()


def delete_health_data(account_user_id: int, data_owner_key: str) -> dict:
    """Delete health content while retaining the account and minimal consent/audit records."""
    init_schema(); uh = db._hash_user(data_owner_key); uid = int(account_user_id)
    conn = db._conn(); c = conn.cursor(); deleted = 0
    try:
        # Remove delivery metadata before deleting plans/subscriptions so no endpoint or
        # medication-plan linkage remains after a health-data deletion request.
        try:
            c.execute("SELECT id FROM med_plans WHERE user_hash=%s" % PH, (uh,))
            plan_ids = [int(r[0]) for r in c.fetchall()]
        except Exception:
            plan_ids = []
        try:
            c.execute("SELECT endpoint FROM push_subscriptions WHERE user_hash=%s" % PH, (uh,))
            push_endpoints = [str(r[0]) for r in c.fetchall() if r and r[0]]
        except Exception:
            push_endpoints = []
        for endpoint in push_endpoints:
            try:
                c.execute("DELETE FROM push_delivery_log WHERE endpoint=%s" % PH, (endpoint,))
                deleted += max(0, int(c.rowcount or 0))
            except Exception:
                pass
        for plan_id in plan_ids:
            try:
                c.execute("DELETE FROM push_delivery_log WHERE plan_id=%s" % PH, (plan_id,))
                deleted += max(0, int(c.rowcount or 0))
            except Exception:
                pass
        # results first because they reference record ids by convention.
        for table, col in [
            ("results", "user_hash"), ("records", "user_hash"), ("profiles", "user_hash"),
            ("blood_tests", "user_hash"), ("daily_checkins", "user_hash"), ("feedback", "user_hash"),
            ("assistant_feedback", "user_hash"), ("family_members", "user_hash"), ("med_logs", "user_hash"),
            ("med_plans", "user_hash"), ("push_subscriptions", "user_hash"),
        ]:
            try:
                c.execute(f"DELETE FROM {table} WHERE {col}={PH}", (uh,)); deleted += max(0, int(c.rowcount or 0))
            except Exception:
                pass
        for table in ("ss_health_profiles", "ss_chat_history"):
            try:
                c.execute(f"DELETE FROM {table} WHERE user_id={PH}", (uid,)); deleted += max(0, int(c.rowcount or 0))
            except Exception:
                pass
        # Optional advanced feature tables are removed only when present and owned by this user.
        for table, col in [
            ("ss_user_preferences","user_id"),
            ("ss_analysis_links","user_hash"),
            ("med_notification_settings","user_hash"),
            ("med_snoozes","user_hash"),
            ("push_action_tokens","user_hash"),
        ]:
            try:
                value = uid if col == "user_id" else uh
                c.execute(f"DELETE FROM {table} WHERE {col}={PH}", (value,)); deleted += max(0, int(c.rowcount or 0))
            except Exception:
                pass
        # Handoff links are sensitive temporary health summaries.
        try:
            c.execute("DELETE FROM ss_handoff_links WHERE owner_hash=%s" % PH, (uh,)); deleted += max(0, int(c.rowcount or 0))
        except Exception:
            pass
        conn.commit()
    finally:
        conn.close()
    log_privacy_event(data_owner_key, "health_data_deletion_requested", {"status":"completed", "count": deleted})
    return {"deleted_items": deleted}


def _safe_user_export(account_user_id: int, data_owner_key: str) -> dict:
    """Return only data belonging to the requester. Never include password hashes/tokens/secrets."""
    init_schema(); uid = int(account_user_id)
    user = db.get_ss_user(uid) or {}
    out = {
        "generated_at": _now(),
        "account": {k:user.get(k) for k in ("id","email","name","role","status","created_at","last_login")},
        "health_profile": db.load_health_profile(uid) or {},
        "privacy_settings": db.load_privacy_settings(uid) or {},
        "consent": get_consent(data_owner_key, uid),
        "consent_history": consent_history(data_owner_key),
        "analysis_history": [],
        "assistant_history": db.get_chat_history(uid, limit=500),
        "medication_reminders": [],
    }
    try:
        records = db.get_records(data_owner_key, limit=1000)
        for r in records:
            item = dict(r); result = db.load_result(data_owner_key, r.get("id")) or {}
            item["result"] = result
            out["analysis_history"].append(item)
    except Exception:
        pass
    conn = db._conn(); c = conn.cursor()
    try:
        try:
            c.execute("SELECT id,member_id,med_name,dose,times,frequency,start_date,end_date,days_of_week,timezone,notes,active,created FROM med_plans WHERE user_hash=%s ORDER BY id" % PH, (db._hash_user(data_owner_key),))
            out["medication_reminders"] = _rows(c)
        except Exception:
            pass
    finally:
        conn.close()
    return out


def user_export_bytes(account_user_id: int, data_owner_key: str) -> io.BytesIO:
    raw = json.dumps(_safe_user_export(account_user_id, data_owner_key), ensure_ascii=False, indent=2, default=str).encode("utf-8")
    log_privacy_event(data_owner_key, "data_export_requested", {"status":"completed", "format":"json"})
    return io.BytesIO(raw)


def _parse_dt(v):
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except Exception:
        return None


def create_handoff(owner_key: str, record_id: int, selected: dict, previous_ids=None, expires_minutes=60) -> dict:
    init_schema(); result = db.load_result(owner_key, int(record_id))
    if not result:
        raise PermissionError("analysis_not_found")
    expires_minutes = int(expires_minutes)
    if expires_minutes not in (15, 60, 1440):
        raise ValueError("invalid_expiration")
    allowed = {"symptoms","duration","severity","location","notes","previous_assessments","medications"}
    selected = {k: bool(v) for k,v in (selected or {}).items() if k in allowed}
    if not any(selected.values()):
        raise ValueError("select_at_least_one_field")
    payload = {"created_at": _now(), "lang": result.get("lang") or "ar", "sections": {}}
    sec = payload["sections"]
    if selected.get("symptoms"): sec["symptoms"] = result.get("symptoms") or []
    if selected.get("duration"): sec["duration"] = result.get("duration") or ""
    if selected.get("severity"): sec["severity"] = result.get("severity")
    if selected.get("location"): sec["location"] = result.get("location") or ""
    if selected.get("notes"): sec["notes"] = result.get("notes") or ""
    if selected.get("medications"): sec["medications"] = result.get("medications") or ""
    if selected.get("previous_assessments"):
        previous=[]
        for rid in (previous_ids or [])[:5]:
            try:
                rid=int(rid); old=db.load_result(owner_key,rid)
            except Exception:
                old=None
            if old:
                previous.append({"symptoms":old.get("symptoms") or [],"duration":old.get("duration") or "","severity":old.get("severity"),"risk_level":old.get("risk_level") or old.get("urgency") or ""})
        sec["previous_assessments"] = previous
    token = secrets.token_urlsafe(32); th = _token_hash(token); owner_hash = db._hash_user(owner_key)
    exp = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    conn = db._conn(); c=conn.cursor()
    try:
        c.execute("INSERT INTO ss_handoff_links(owner_hash,token_hash,payload_json,created_at,expires_at,revoked_at) VALUES(%s,%s,%s,%s,%s,%s)".replace("%s",PH),
                  (owner_hash, th, json.dumps(payload, ensure_ascii=False), _now(), exp.isoformat(), None))
        conn.commit()
    finally:
        conn.close()
    log_privacy_event(owner_key, "temporary_health_summary_created", {"status":"completed", "expiration_minutes":expires_minutes})
    return {"token": token, "expires_at": exp.isoformat(), "payload": payload}


def get_handoff(token: str) -> dict | None:
    init_schema(); th = _token_hash(token)
    conn=db._conn(); c=conn.cursor()
    try:
        c.execute("SELECT payload_json,expires_at,revoked_at FROM ss_handoff_links WHERE token_hash=%s" % PH,(th,)); row=c.fetchone()
    finally:
        conn.close()
    if not row: return None
    exp=_parse_dt(row[1]); now=datetime.now(timezone.utc)
    if row[2]: return {"status":"revoked"}
    if not exp or exp <= now: return {"status":"expired"}
    try: payload=json.loads(row[0])
    except Exception: return None
    return {"status":"active","payload":payload,"expires_at":row[1]}


def revoke_handoff(owner_key: str, token: str) -> bool:
    init_schema(); conn=db._conn(); c=conn.cursor()
    try:
        c.execute("UPDATE ss_handoff_links SET revoked_at=%s WHERE owner_hash=%s AND token_hash=%s AND revoked_at IS NULL" % (PH,PH,PH),
                  (_now(), db._hash_user(owner_key), _token_hash(token)))
        changed = bool(c.rowcount)
        conn.commit()
    finally:
        conn.close()
    if changed:
        log_privacy_event(owner_key, "temporary_health_summary_revoked", {"status":"completed"})
    return changed


def qr_png_data_uri(url: str) -> str:
    try:
        import qrcode
        img=qrcode.make(url); bio=io.BytesIO(); img.save(bio, format="PNG")
        return "data:image/png;base64,"+base64.b64encode(bio.getvalue()).decode("ascii")
    except Exception:
        return ""


def privacy_audit_events(limit=200) -> list[dict]:
    """Return privacy actions without subject identifiers or health content."""
    init_schema(); conn=db._conn(); c=conn.cursor()
    try:
        c.execute("SELECT id,action,metadata,timestamp FROM ss_privacy_events ORDER BY id DESC LIMIT %s" % PH,(max(1,min(500,int(limit))),))
        rows=c.fetchall()
    finally:
        conn.close()
    out=[]
    for rid,action,metadata,ts in rows:
        try: meta=json.loads(metadata or "{}")
        except Exception: meta={}
        safe={k:v for k,v in meta.items() if k in {"status","format","count"}}
        out.append({"id":"privacy-%s"%rid,"admin_id":None,"action":action,"entity_type":"privacy","entity_id":None,"previous_value":None,"new_value":json.dumps(safe,ensure_ascii=False) if safe else None,"timestamp":ts,"source":"privacy"})
    return out


def anonymous_health_analytics() -> dict:
    """Admin-safe aggregate health analytics from explicitly consented records.

    Small groups are suppressed using *distinct users*, not record count, so one
    prolific account cannot make a group appear privacy-safe by itself.
    """
    init_schema(); k=PRIVACY_THRESHOLD
    conn=db._conn(); c=conn.cursor()
    try:
        c.execute("SELECT user_hash,age,gender,symptoms,medications,urgency,timestamp FROM records WHERE analytics_eligible=1")
        records=c.fetchall()
        c.execute("SELECT subject_hash,consent_status,timestamp FROM ss_consent_log WHERE consent_type='analytics_research' ORDER BY timestamp")
        consent_rows=c.fetchall()
    finally:
        conn.close()
    syms=Counter(); risks=Counter(); ages=Counter(); meds=Counter()
    users_by={"symptom":defaultdict(set),"risk":defaultdict(set),"age":defaultdict(set),"med":defaultdict(set)}
    def age_group(a):
        try:a=int(a)
        except Exception:return "Unknown"
        if a<18:return "Under 18"
        if a<=25:return "18–25"
        if a<=35:return "26–35"
        if a<=45:return "36–45"
        if a<=55:return "46–55"
        return "56+"
    for uh,age,gender,symptoms,medications,urgency,ts in records:
        ag=age_group(age); ages[ag]+=1; users_by["age"][ag].add(uh)
        rk=str(urgency or "unknown"); risks[rk]+=1; users_by["risk"][rk].add(uh)
        for sym in {x.strip() for x in str(symptoms or "").split(",") if x.strip()}:
            syms[sym]+=1; users_by["symptom"][sym].add(uh)
        for med in {x.strip() for x in str(medications or "").replace(";",",").split(",") if x.strip()}:
            meds[med]+=1; users_by["med"][med].add(uh)
    def safe_counter(counter, key):
        return [{"label":x,"count":n,"distinct_users":len(users_by[key][x])} for x,n in counter.most_common(20) if len(users_by[key][x])>=k]
    latest={}
    for sh,status,ts in consent_rows: latest[sh]=status
    consent=Counter(latest.values()); total_consents=sum(consent.values())
    metrics={x:(round(consent.get(x,0)*100/total_consents,1) if total_consents else 0) for x in ("granted","declined","withdrawn")}
    return {
        "privacy_threshold":k,
        "eligible_records":len(records),
        "eligible_users":len({r[0] for r in records}),
        "most_reported_symptoms":safe_counter(syms,"symptom"),
        "age_groups":safe_counter(ages,"age"),
        "medication_patterns":safe_counter(meds,"med"),
        "risk_distribution":safe_counter(risks,"risk"),
        "consent_metrics":metrics,
        "consent_subjects":total_consents,
    }
