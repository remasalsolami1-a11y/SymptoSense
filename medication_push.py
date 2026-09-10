"""Backend-driven medication reminder and Web Push support for SymptoSense.

The reminder system only schedules user-entered reminders. It never recommends a
medication or dose. Push payloads are deliberately generic and contain no
medication name, diagnosis, symptom, email, or other health detail.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import time
import threading
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import db

PH = db.PH
log = logging.getLogger("SymptoSense.Push")
ALLOWED_SNOOZE = {5, 10, 15, 30}
ALLOWED_FREQ = {"daily", "specific_days"}


def _serial(): return "SERIAL PRIMARY KEY" if db.USE_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"
def _now(): return datetime.now(timezone.utc).isoformat()
def _token_hash(raw: str): return hashlib.sha256(str(raw).encode("utf-8")).hexdigest()


def _cols(c, table):
    if db.USE_POSTGRES:
        c.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s", (table,)); return {r[0] for r in c.fetchall()}
    c.execute(f"PRAGMA table_info({table})"); return {r[1] for r in c.fetchall()}


def _add_col(c, table, name, sql_type_default):
    if name not in _cols(c, table): c.execute(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type_default}")


def init_schema():
    db.init_db(); conn=db._conn(); c=conn.cursor()
    try:
        _add_col(c,"med_plans","end_date","TEXT")
        _add_col(c,"med_plans","notes","TEXT DEFAULT ''")
        _add_col(c,"med_plans","days_of_week","TEXT DEFAULT '[]'")
        _add_col(c,"med_plans","timezone","TEXT DEFAULT 'Asia/Riyadh'")
        _add_col(c,"med_plans","notifications_enabled","INTEGER DEFAULT 1")
        _add_col(c,"med_plans","updated_at","TEXT")
        c.execute("""
            CREATE TABLE IF NOT EXISTS med_notification_settings (
                user_hash TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 1,
                sound INTEGER NOT NULL DEFAULT 1, snooze_minutes INTEGER NOT NULL DEFAULT 10,
                timezone TEXT NOT NULL DEFAULT 'Asia/Riyadh', updated_at TEXT NOT NULL
            )
        """)
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS med_snoozes (
                id {_serial()}, user_hash TEXT NOT NULL, plan_id INTEGER NOT NULL,
                member_id INTEGER NOT NULL DEFAULT 0, log_date TEXT NOT NULL,
                log_time TEXT NOT NULL, due_at_utc TEXT NOT NULL, minutes INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_med_snooze_due ON med_snoozes(status,due_at_utc)")
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS push_action_tokens (
                id {_serial()}, token_hash TEXT UNIQUE NOT NULL, user_hash TEXT NOT NULL,
                plan_id INTEGER NOT NULL, member_id INTEGER NOT NULL DEFAULT 0,
                log_date TEXT NOT NULL, log_time TEXT NOT NULL, lang TEXT NOT NULL DEFAULT 'ar',
                expires_at TEXT NOT NULL, consumed_at TEXT, created_at TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_push_action_exp ON push_action_tokens(expires_at)")
        conn.commit()
    finally: conn.close()


def valid_timezone(value: str) -> str:
    value=(value or "Asia/Riyadh").strip()[:80]
    try: ZoneInfo(value); return value
    except (ZoneInfoNotFoundError, ValueError): return "Asia/Riyadh"


def _json_list(value):
    if isinstance(value,list): return value
    try: return json.loads(value or "[]")
    except Exception: return []


def _parse_times(values) -> list[str]:
    out=[]
    for raw in values or []:
        s=str(raw).strip()
        try:
            h,m=s.split(":",1); h=int(h);m=int(m)
            if 0<=h<=23 and 0<=m<=59:
                val=f"{h:02d}:{m:02d}"
                if val not in out: out.append(val)
        except Exception: pass
    return sorted(out)


def _parse_days(values) -> list[int]:
    out=[]
    for x in values or []:
        try:
            v=int(x)
            if 0<=v<=6 and v not in out: out.append(v)
        except Exception: pass
    return sorted(out)


def save_plan(user_id, data: dict, plan_id: int | None = None) -> int:
    init_schema(); uh=db._hash_user(user_id)
    med_name=str(data.get("med_name") or "").strip()[:120]; times=_parse_times(data.get("times") or [])
    if not med_name or not times: raise ValueError("medication_name_and_time_required")
    dose=str(data.get("dose") or "").strip()[:120]; notes=str(data.get("notes") or "").strip()[:600]
    frequency=str(data.get("frequency") or "daily").strip(); frequency=frequency if frequency in ALLOWED_FREQ else "daily"
    days_of_week=_parse_days(data.get("days_of_week") or []) if frequency=="specific_days" else []
    tz=valid_timezone(data.get("timezone")); start=str(data.get("start_date") or date.today().isoformat())[:10]
    end=str(data.get("end_date") or "")[:10] or None; notifications=1 if data.get("notifications_enabled",True) else 0
    try: member=int(data.get("member_id") or 0)
    except Exception: member=0
    days=data.get("days")
    try: days=int(days) if days else None
    except Exception: days=None
    now=_now(); conn=db._conn(); c=conn.cursor()
    try:
        if plan_id:
            c.execute(f"SELECT 1 FROM med_plans WHERE id={PH} AND user_hash={PH}",(int(plan_id),uh))
            if not c.fetchone(): raise PermissionError("plan_not_found_or_not_owned")
            c.execute(f"UPDATE med_plans SET member_id={PH},med_name={PH},dose={PH},times={PH},frequency={PH},start_date={PH},days={PH},end_date={PH},notes={PH},days_of_week={PH},timezone={PH},notifications_enabled={PH},active=1,updated_at={PH} WHERE id={PH} AND user_hash={PH}",
                      (member,med_name,dose,json.dumps(times),frequency,start,days,end,notes,json.dumps(days_of_week),tz,notifications,now,int(plan_id),uh)); pid=int(plan_id)
        else:
            c.execute(f"INSERT INTO med_plans(user_hash,member_id,med_name,dose,times,frequency,start_date,days,active,created,end_date,notes,days_of_week,timezone,notifications_enabled,updated_at) VALUES({','.join([PH]*16)})",
                      (uh,member,med_name,dose,json.dumps(times),frequency,start,days,1,now,end,notes,json.dumps(days_of_week),tz,notifications,now))
            if db.USE_POSTGRES: c.execute("SELECT lastval()"); pid=int(c.fetchone()[0])
            else: pid=int(c.lastrowid)
        conn.commit(); return pid
    finally: conn.close()


def list_plans(user_id, member_id=None, active_only=False) -> list[dict]:
    init_schema(); uh=db._hash_user(user_id); conn=db._conn(); c=conn.cursor()
    try:
        clauses=[f"user_hash={PH}"]; params=[uh]
        if member_id is not None: clauses.append(f"member_id={PH}");params.append(int(member_id))
        if active_only: clauses.append("active=1")
        c.execute("SELECT id,member_id,med_name,dose,times,frequency,start_date,days,active,created,end_date,notes,days_of_week,timezone,notifications_enabled,updated_at FROM med_plans WHERE "+" AND ".join(clauses)+" ORDER BY id DESC",tuple(params)); rows=c.fetchall()
    finally: conn.close()
    out=[]
    for r in rows:
        out.append({"id":r[0],"member_id":r[1],"med_name":r[2],"dose":r[3] or "","times":_parse_times(_json_list(r[4])),"frequency":r[5] or "daily","start_date":r[6] or "","days":r[7],"active":bool(r[8]),"created":r[9] or "","end_date":r[10] or "","notes":r[11] or "","days_of_week":_parse_days(_json_list(r[12])),"timezone":valid_timezone(r[13]),"notifications_enabled":bool(r[14]),"updated_at":r[15] or ""})
    return out


def disable_plan(user_id, plan_id):
    init_schema(); conn=db._conn(); c=conn.cursor()
    try:
        c.execute(f"UPDATE med_plans SET active=0,notifications_enabled=0,updated_at={PH} WHERE id={PH} AND user_hash={PH}",(_now(),int(plan_id),db._hash_user(user_id))); conn.commit()
        return c.rowcount>0
    finally: conn.close()


def get_settings(user_id) -> dict:
    return get_settings_by_hash(db._hash_user(user_id))


def get_settings_by_hash(user_hash: str) -> dict:
    init_schema(); conn=db._conn(); c=conn.cursor()
    try:
        c.execute(f"SELECT enabled,sound,snooze_minutes,timezone FROM med_notification_settings WHERE user_hash={PH}",(user_hash,)); r=c.fetchone()
        if not r: return {"enabled":True,"sound":True,"snooze_minutes":10,"timezone":"Asia/Riyadh"}
        return {"enabled":bool(r[0]),"sound":bool(r[1]),"snooze_minutes":int(r[2] or 10),"timezone":valid_timezone(r[3])}
    finally: conn.close()


def save_settings(user_id, data: dict) -> dict:
    init_schema(); uh=db._hash_user(user_id); enabled=1 if data.get("enabled",True) else 0; sound=1 if data.get("sound",True) else 0
    try: snooze=int(data.get("snooze_minutes") or 10)
    except Exception: snooze=10
    if snooze not in ALLOWED_SNOOZE: snooze=10
    tz=valid_timezone(data.get("timezone")); now=_now(); conn=db._conn(); c=conn.cursor()
    try:
        if db.USE_POSTGRES:
            c.execute("INSERT INTO med_notification_settings(user_hash,enabled,sound,snooze_minutes,timezone,updated_at) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(user_hash) DO UPDATE SET enabled=EXCLUDED.enabled,sound=EXCLUDED.sound,snooze_minutes=EXCLUDED.snooze_minutes,timezone=EXCLUDED.timezone,updated_at=EXCLUDED.updated_at",(uh,enabled,sound,snooze,tz,now))
        else:
            c.execute("INSERT INTO med_notification_settings(user_hash,enabled,sound,snooze_minutes,timezone,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(user_hash) DO UPDATE SET enabled=excluded.enabled,sound=excluded.sound,snooze_minutes=excluded.snooze_minutes,timezone=excluded.timezone,updated_at=excluded.updated_at",(uh,enabled,sound,snooze,tz,now))
        conn.commit()
    finally: conn.close()
    return get_settings(user_id)


def push_config() -> dict:
    return {"configured":bool(os.environ.get("VAPID_PUBLIC_KEY") and os.environ.get("VAPID_PRIVATE_KEY") and os.environ.get("VAPID_CLAIMS_EMAIL")),"public_key":os.environ.get("VAPID_PUBLIC_KEY","")}


def subscribe(user_id, subscription: dict, timezone_name="Asia/Riyadh", lang="ar"):
    init_schema(); db.save_push_subscription(user_id,subscription,valid_timezone(timezone_name),"en" if lang=="en" else "ar")


def unsubscribe(user_id, endpoint=None): db.delete_push_subscription(user_id,endpoint)


def subscription_status(user_id) -> dict:
    subs=db.list_push_subscriptions(user_id,True); cfg=push_config(); settings=get_settings(user_id)
    return {"configured":cfg["configured"],"subscribed":bool(subs),"device_count":len(subs),"settings":settings}


def _plan_active_on(plan: dict, local_date: date) -> bool:
    try: start=date.fromisoformat(str(plan.get("start_date") or local_date.isoformat())[:10])
    except Exception: start=local_date
    if local_date<start: return False
    end_raw=plan.get("end_date")
    if end_raw:
        try:
            if local_date>date.fromisoformat(str(end_raw)[:10]): return False
        except Exception: pass
    if plan.get("days"):
        try:
            if local_date >= start + timedelta(days=int(plan["days"])): return False
        except Exception: pass
    if plan.get("frequency")=="specific_days":
        days=plan.get("days_of_week") or []
        if days and local_date.weekday() not in days: return False
    return bool(plan.get("active",True))


def _all_active_plans() -> list[dict]:
    init_schema(); conn=db._conn(); c=conn.cursor()
    try:
        c.execute("SELECT id,user_hash,member_id,med_name,dose,times,frequency,start_date,days,active,end_date,notes,days_of_week,timezone,notifications_enabled FROM med_plans WHERE active=1 AND COALESCE(notifications_enabled,1)=1")
        rows=c.fetchall()
    finally: conn.close()
    out=[]
    for r in rows:
        out.append({"id":r[0],"user_hash":r[1],"member_id":r[2],"med_name":r[3],"dose":r[4] or "","times":_parse_times(_json_list(r[5])),"frequency":r[6] or "daily","start_date":r[7] or "","days":r[8],"active":bool(r[9]),"end_date":r[10] or "","notes":r[11] or "","days_of_week":_parse_days(_json_list(r[12])),"timezone":valid_timezone(r[13]),"notifications_enabled":bool(r[14])})
    return out


def _subs_for_hash(user_hash):
    return [s for s in db.list_push_subscriptions(None,True) if s.get("user_hash")==user_hash]


def _create_action_token(plan: dict, log_date: str, log_time: str, lang="ar") -> str:
    raw=secrets.token_urlsafe(32); now=datetime.now(timezone.utc); exp=(now+timedelta(hours=48)).isoformat(); conn=db._conn(); c=conn.cursor()
    try:
        c.execute(f"INSERT INTO push_action_tokens(token_hash,user_hash,plan_id,member_id,log_date,log_time,lang,expires_at,consumed_at,created_at) VALUES({','.join([PH]*10)})",(_token_hash(raw),plan["user_hash"],int(plan["id"]),int(plan.get("member_id") or 0),log_date,log_time,"en" if lang=="en" else "ar",exp,None,now.isoformat())); conn.commit()
    finally: conn.close()
    return raw


def _normalized_vapid_private(value: str) -> str:
    """Accept either a pywebpush-compatible key string/path or a PEM value from env."""
    value=(value or "").strip()
    if "-----BEGIN" not in value:
        return value
    try:
        from cryptography.hazmat.primitives import serialization
        key=serialization.load_pem_private_key(value.encode("utf-8"), password=None)
        der=key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        import base64 as _b64
        return _b64.urlsafe_b64encode(der).rstrip(b"=").decode("ascii")
    except Exception:
        return value


def _send(subscription: dict, payload: dict):
    from pywebpush import webpush, WebPushException
    private=_normalized_vapid_private(os.environ.get("VAPID_PRIVATE_KEY","")); claims=os.environ.get("VAPID_CLAIMS_EMAIL","")
    if not private or not claims: raise RuntimeError("VAPID_NOT_CONFIGURED")
    return webpush(subscription_info={"endpoint":subscription["endpoint"],"keys":{"p256dh":subscription["p256dh"],"auth":subscription["auth"]}},data=json.dumps(payload,ensure_ascii=False),vapid_private_key=private,vapid_claims={"sub":claims},ttl=3600,timeout=10)


def _generic_payload(token: str, lang="ar", sound=True, snooze_minutes=10, tag="symptosense-medication"):
    ar=lang!="en"
    return {"title":"💊 SymptoSense","body":"حان وقت تذكير الدواء المجدول." if ar else "It's time for your scheduled medication reminder.","icon":"/icons/icon-192.png","badge":"/icons/icon-192.png","tag":tag,"url":"/meds","token":token,"taken_label":"تم أخذه" if ar else "Taken","snooze_label":(("غفوة %s د" if ar else "Snooze %s min")%snooze_minutes),"silent":not bool(sound)}


def _scheduled_delta_seconds(now_utc: datetime, tz: str, local_date: date, hhmm: str):
    h,m=map(int,hhmm.split(":")); sched=datetime(local_date.year,local_date.month,local_date.day,h,m,tzinfo=ZoneInfo(tz)); return (now_utc-sched.astimezone(timezone.utc)).total_seconds()


def send_due_notifications(now_utc: datetime | None = None, grace_seconds=300) -> dict:
    init_schema(); cfg=push_config()
    if not cfg["configured"]: return {"sent":0,"failed":0,"skipped":0,"configured":False}
    now_utc=now_utc or datetime.now(timezone.utc); sent=failed=skipped=0
    for p in _all_active_plans():
        settings=get_settings_by_hash(p["user_hash"])
        if not settings.get("enabled"): skipped+=1; continue
        tz=valid_timezone(p.get("timezone") or settings.get("timezone")); local_now=now_utc.astimezone(ZoneInfo(tz)); local_date=local_now.date()
        if not _plan_active_on(p,local_date): continue
        subs=_subs_for_hash(p["user_hash"])
        if not subs: continue
        for tm in p["times"]:
            try: delta=_scheduled_delta_seconds(now_utc,tz,local_date,tm)
            except Exception: continue
            if delta<0 or delta>grace_seconds: continue
            for sub in subs:
                if not db.claim_push_delivery(sub["endpoint"],p["id"],local_date.isoformat(),tm): continue
                try:
                    token=_create_action_token(p,local_date.isoformat(),tm,sub.get("lang") or "ar")
                    _send(sub,_generic_payload(token,sub.get("lang") or "ar",settings.get("sound",True),settings.get("snooze_minutes",10),f"ss-med-{p['id']}-{local_date}-{tm}")); sent+=1
                except Exception as exc:
                    failed+=1; db.release_push_delivery(sub["endpoint"],p["id"],local_date.isoformat(),tm)
                    status=getattr(getattr(exc,"response",None),"status_code",None)
                    if status in (404,410): db.mark_push_subscription_inactive(sub["endpoint"])
                    log.warning("push send failed: %s", type(exc).__name__)
    # Snoozed occurrences
    sent2,failed2=_send_due_snoozes(now_utc); return {"sent":sent+sent2,"failed":failed+failed2,"skipped":skipped,"configured":True}


def _send_due_snoozes(now_utc):
    conn=db._conn(); c=conn.cursor()
    try:
        c.execute(f"SELECT id,user_hash,plan_id,member_id,log_date,log_time,due_at_utc,minutes FROM med_snoozes WHERE status='pending' AND due_at_utc<={PH} ORDER BY due_at_utc LIMIT 200",(now_utc.isoformat(),)); rows=c.fetchall()
    finally: conn.close()
    sent=failed=0
    for sid,uh,pid,mid,ld,lt,due,mins in rows:
        settings=get_settings_by_hash(uh)
        if not settings.get("enabled"): continue
        subs=_subs_for_hash(uh); plan={"id":pid,"user_hash":uh,"member_id":mid}
        success=False
        for sub in subs:
            key=f"snooze:{sid}"
            if not db.claim_push_delivery(sub["endpoint"],pid,ld,key): continue
            try:
                token=_create_action_token(plan,ld,lt,sub.get("lang") or "ar")
                _send(sub,_generic_payload(token,sub.get("lang") or "ar",settings.get("sound",True),settings.get("snooze_minutes",10),f"ss-snooze-{sid}")); sent+=1; success=True
            except Exception as exc:
                failed+=1; db.release_push_delivery(sub["endpoint"],pid,ld,key); status=getattr(getattr(exc,"response",None),"status_code",None)
                if status in (404,410): db.mark_push_subscription_inactive(sub["endpoint"])
        if success:
            conn=db._conn();c=conn.cursor();c.execute(f"UPDATE med_snoozes SET status='sent' WHERE id={PH}",(sid,));conn.commit();conn.close()
    return sent,failed


def _log_status_hash(user_hash, member_id, plan_id, log_date, log_time, status):
    conn=db._conn(); c=conn.cursor()
    try:
        c.execute(f"DELETE FROM med_logs WHERE user_hash={PH} AND plan_id={PH} AND log_date={PH} AND log_time={PH}",(user_hash,int(plan_id),log_date,log_time))
        c.execute(f"INSERT INTO med_logs(user_hash,member_id,plan_id,log_date,log_time,status,created) VALUES({','.join([PH]*7)})",(user_hash,int(member_id or 0),int(plan_id),log_date,log_time,status,_now()));conn.commit()
    finally: conn.close()


def schedule_snooze_by_hash(user_hash, plan_id, member_id, log_date, log_time, minutes=None):
    settings=get_settings_by_hash(user_hash)
    try: minutes=int(minutes or settings.get("snooze_minutes") or 10)
    except Exception: minutes=10
    if minutes not in ALLOWED_SNOOZE: minutes=10
    due=(datetime.now(timezone.utc)+timedelta(minutes=minutes)).isoformat(); conn=db._conn();c=conn.cursor()
    try:
        c.execute(f"INSERT INTO med_snoozes(user_hash,plan_id,member_id,log_date,log_time,due_at_utc,minutes,status,created_at) VALUES({','.join([PH]*9)})",(user_hash,int(plan_id),int(member_id or 0),log_date,log_time,due,minutes,"pending",_now()));conn.commit()
    finally: conn.close()
    _log_status_hash(user_hash,member_id,plan_id,log_date,log_time,"snoozed"); return minutes


def schedule_snooze(user_id, plan_id, member_id, log_date, log_time, minutes=None):
    # Ownership check before creating a background notification.
    plans={p["id"]:p for p in list_plans(user_id,active_only=True)}
    if int(plan_id) not in plans: raise PermissionError("plan_not_found_or_not_owned")
    return schedule_snooze_by_hash(db._hash_user(user_id),plan_id,member_id,log_date,log_time,minutes)


def handle_push_action(raw_token: str, action: str) -> dict:
    init_schema(); action=str(action or "").lower()
    if action not in {"taken","snooze"}: raise ValueError("unsupported_push_action")
    th=_token_hash(raw_token or ""); now=datetime.now(timezone.utc)
    conn=db._conn(); c=conn.cursor()
    try:
        c.execute(f"SELECT id,user_hash,plan_id,member_id,log_date,log_time,expires_at,consumed_at FROM push_action_tokens WHERE token_hash={PH}",(th,)); r=c.fetchone()
    finally:
        conn.close()
    if not r: raise PermissionError("invalid_action_token")
    tid,uh,pid,mid,ld,lt,exp,consumed=r
    if consumed: raise PermissionError("action_token_already_used")
    try:
        if datetime.fromisoformat(str(exp).replace("Z","+00:00"))<now: raise PermissionError("action_token_expired")
    except ValueError: raise PermissionError("action_token_expired")

    # Atomically claim the one-time action token *before* changing reminder state.
    # This prevents double Taken/Snooze actions when the OS/browser retries a click.
    claimed_at=_now(); conn=db._conn(); c=conn.cursor()
    try:
        c.execute(f"UPDATE push_action_tokens SET consumed_at={PH} WHERE id={PH} AND consumed_at IS NULL",(claimed_at,tid)); conn.commit()
        if not c.rowcount: raise PermissionError("action_token_already_used")
    finally:
        conn.close()
    try:
        if action=="taken":
            _log_status_hash(uh,mid,pid,ld,lt,"taken")
            conn=db._conn();c=conn.cursor()
            try:
                c.execute(f"UPDATE med_snoozes SET status='cancelled' WHERE user_hash={PH} AND plan_id={PH} AND log_date={PH} AND log_time={PH} AND status='pending'",(uh,pid,ld,lt)); conn.commit()
            finally: conn.close()
            return {"status":"taken"}
        mins=schedule_snooze_by_hash(uh,pid,mid,ld,lt)
        return {"status":"snoozed","minutes":mins}
    except Exception:
        # Allow a retry only when the server-side action itself failed.
        conn=db._conn(); c=conn.cursor()
        try:
            c.execute(f"UPDATE push_action_tokens SET consumed_at=NULL WHERE id={PH} AND consumed_at={PH}",(tid,claimed_at)); conn.commit()
        finally:
            conn.close()
        raise

def reminder_calendar(user_id, member_id=None, days=30) -> dict:
    init_schema(); days=max(1,min(90,int(days or 30))); plans=list_plans(user_id,member_id=member_id,active_only=False); logs=db.get_med_logs(user_id); logmap={(int(x["plan_id"]),x["log_date"],x["log_time"]):x["status"] for x in logs}; settings=get_settings(user_id); tz=ZoneInfo(settings["timezone"]); now=datetime.now(timezone.utc).astimezone(tz); start_day=now.date()-timedelta(days=days-1); entries=[]; counts=Counter()
    for i in range(days):
        d=start_day+timedelta(days=i)
        for p in plans:
            if not _plan_active_on(p,d): continue
            for tm in p["times"]:
                try:
                    h,m=map(int,tm.split(":")); occ=datetime(d.year,d.month,d.day,h,m,tzinfo=ZoneInfo(p.get("timezone") or settings["timezone"]))
                except Exception: continue
                if occ>now: status="scheduled"
                else: status=logmap.get((p["id"],d.isoformat(),tm),"scheduled")
                entries.append({"date":d.isoformat(),"time":tm,"plan_id":p["id"],"med_name":p["med_name"],"status":status}); counts[status]+=1
    expected=sum(1 for e in entries if e["date"]<now.date().isoformat() or (e["date"]==now.date().isoformat() and e["time"]<=now.strftime("%H:%M")))
    taken=counts["taken"]; adherence=round(taken*100.0/expected,1) if expected else 0.0
    return {"entries":entries,"summary":{"scheduled":expected,"taken":taken,"skipped":counts["skipped"],"snoozed":counts["snoozed"]+counts["deferred"],"adherence":adherence}}


def plans_today(user_id, member_id=None) -> list[dict]:
    """Return today's owned plan occurrences using each plan's schedule/timezone."""
    init_schema(); plans=list_plans(user_id,member_id=member_id,active_only=True); logs=db.get_med_logs(user_id)
    logmap={(int(x["plan_id"]),x["log_date"],x["log_time"]):x["status"] for x in logs}; settings=get_settings(user_id); out=[]
    for p in plans:
        tz=valid_timezone(p.get("timezone") or settings.get("timezone")); today=datetime.now(timezone.utc).astimezone(ZoneInfo(tz)).date()
        if not _plan_active_on(p,today): continue
        q=dict(p); q["today_date"]=today.isoformat(); q["logs"]={tm:logmap.get((p["id"],today.isoformat(),tm)) for tm in p["times"]}; out.append(q)
    return out


def weekly_summary(user_id, member_id=None) -> dict:
    cal=reminder_calendar(user_id,member_id=member_id,days=7); sm=cal["summary"]
    return {"expected":sm["scheduled"],"taken":sm["taken"],"skipped":sm["skipped"],"snoozed":sm["snoozed"],"percent":sm["adherence"],"days":7}


def send_test_to_user(user_id, lang="ar", endpoint=None) -> dict:
    """Send a generic test notification only to subscriptions owned by this user."""
    init_schema(); uh=db._hash_user(user_id); subs=_subs_for_hash(uh)
    if endpoint:
        subs=[x for x in subs if x.get("endpoint")==endpoint]
    if not subs:
        return {"ok":False,"error":"no_subscription","sent":0}
    cfg=push_config()
    if not cfg.get("configured"):
        return {"ok":False,"error":"push_not_configured","sent":0}
    payload={"title":"💊 SymptoSense","body":"اختبار إشعارات SymptoSense" if lang!="en" else "SymptoSense notification test","icon":"/icons/icon-192.png","badge":"/icons/icon-192.png","tag":"ss-test","url":"/meds","silent":False}
    sent=0; failed=0
    for sub in subs:
        try:
            _send(sub,payload); sent+=1
        except Exception as exc:
            failed+=1
            status=getattr(getattr(exc,"response",None),"status_code",None)
            if status in (404,410): db.mark_push_subscription_inactive(sub["endpoint"])
            log.warning("test push failed: %s", type(exc).__name__)
    return {"ok":sent>0,"sent":sent,"failed":failed,"error":None if sent else "push_failed"}


_EMBEDDED_STARTED=False
def start_embedded_worker_once():
    """Start one server-side scheduler thread for single-service deployments.

    This is independent of browser/page lifetime. Set PUSH_WORKER_MODE=external
    when a dedicated Railway worker service runs push_worker.py.
    """
    global _EMBEDDED_STARTED
    if _EMBEDDED_STARTED or os.environ.get("PUSH_WORKER_MODE","embedded").lower()=="external":
        return False
    _EMBEDDED_STARTED=True
    try: interval=max(15,min(60,int(os.environ.get("PUSH_WORKER_INTERVAL_SECONDS","20"))))
    except Exception: interval=20
    def _loop():
        log.info("embedded medication push worker started interval=%ss", interval)
        while True:
            try: send_due_notifications()
            except Exception as exc: log.exception("embedded push worker iteration failed: %s", type(exc).__name__)
            time.sleep(interval)
    threading.Thread(target=_loop,name="SymptoSensePushWorker",daemon=True).start()
    return True
