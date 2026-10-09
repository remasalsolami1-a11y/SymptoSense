"""Content-gap prioritization using first-party site data and optional Google inputs.

- SymptoSense library clicks: always available.
- Google Search Console: official API when credentials/token are configured.
- Google Trends: import an exported CSV; no undocumented scraper is used.

Signals are advisory only and never auto-publish medical content.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
from datetime import date, datetime, timedelta, timezone

import requests

import db
import health_library
import medical_knowledge as mk

PH = db.PH


def _serial():
    return "SERIAL PRIMARY KEY" if db.USE_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(text: str) -> str:
    t = str(text or "").lower().strip()
    t = re.sub(r"[\u064b-\u065f\u0670]", "", t)
    t = t.translate(str.maketrans({"أ":"ا","إ":"ا","آ":"ا","ى":"ي","ؤ":"و","ئ":"ي","ة":"ه"}))
    return re.sub(r"[^\w\u0600-\u06ff]+", " ", t).strip()


def init_schema():
    db.init_db(); conn=db._conn(); c=conn.cursor()
    try:
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS content_priority_signals (
                id {_serial()}, source TEXT NOT NULL, query_text TEXT NOT NULL,
                normalized_query TEXT NOT NULL, metric REAL NOT NULL DEFAULT 0,
                clicks REAL NOT NULL DEFAULT 0, impressions REAL NOT NULL DEFAULT 0,
                country TEXT, signal_date TEXT NOT NULL, payload_json TEXT NOT NULL DEFAULT '{{}}',
                created_at TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_priority_signal ON content_priority_signals(source,signal_date,normalized_query)")
        conn.commit()
    finally: conn.close()


def _insert(source, query, metric=0, clicks=0, impressions=0, country=None, signal_date=None, payload=None):
    init_schema(); q=str(query or "").strip()
    if not q: return
    conn=db._conn(); c=conn.cursor()
    try:
        c.execute(f"INSERT INTO content_priority_signals(source,query_text,normalized_query,metric,clicks,impressions,country,signal_date,payload_json,created_at) VALUES({','.join([PH]*10)})",
                  (source,q,_norm(q),float(metric or 0),float(clicks or 0),float(impressions or 0),country,signal_date or str(date.today()),json.dumps(payload or {},ensure_ascii=False),_now()))
        conn.commit()
    finally: conn.close()


def import_google_trends_csv(csv_text: str, country: str = "SA") -> dict:
    """Import a CSV exported from Google Trends. No unofficial scraping."""
    text=str(csv_text or "").lstrip("\ufeff")
    reader=csv.reader(io.StringIO(text))
    rows=list(reader)
    imported=0
    for row in rows:
        if not row: continue
        term=str(row[0] or "").strip()
        if not term or _norm(term) in {"term","query","search term","موضوع","عباره البحث","عبارة البحث"}: continue
        raw=str(row[1] if len(row)>1 else "0").replace(",","").replace("%","").strip()
        try: metric=float(re.sub(r"[^0-9.]","",raw) or 0)
        except Exception: metric=0
        _insert("google_trends_csv",term,metric=metric,country=country,payload={"row":row})
        imported+=1
    return {"imported":imported,"country":country}


def import_search_console_rows(rows: list[dict], country: str | None = None) -> dict:
    n=0
    for row in rows or []:
        keys=row.get("keys") or []
        if not keys: continue
        query=str(keys[0] or "").strip()
        if not query: continue
        _insert("search_console",query,metric=float(row.get("impressions") or 0),clicks=row.get("clicks") or 0,impressions=row.get("impressions") or 0,country=country,payload=row)
        n+=1
    return {"imported":n}


def fetch_search_console(days: int = 28, country: str = "sau") -> dict:
    """Fetch query data from the official Search Console API.

    Configure GSC_ACCESS_TOKEN and GSC_SITE_URL. OAuth/service-account token
    creation remains an external deployment responsibility.
    """
    token=os.getenv("GSC_ACCESS_TOKEN","").strip(); site=os.getenv("GSC_SITE_URL","").strip()
    if not token or not site: raise RuntimeError("gsc_credentials_missing")
    end=date.today()-timedelta(days=1); start=end-timedelta(days=max(1,int(days))-1)
    url="https://www.googleapis.com/webmasters/v3/sites/%s/searchAnalytics/query" % requests.utils.quote(site,safe="")
    payload={"startDate":str(start),"endDate":str(end),"dimensions":["query"],"rowLimit":25000,"dimensionFilterGroups":[{"filters":[{"dimension":"country","operator":"equals","expression":country}]}]}
    r=requests.post(url,headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"},json=payload,timeout=30)
    r.raise_for_status(); data=r.json() or {}
    result=import_search_console_rows(data.get("rows") or [],country=country)
    result.update({"start":str(start),"end":str(end),"rows_returned":len(data.get("rows") or [])})
    return result


def _known_terms():
    mk.init_schema(); terms=[]
    for plural,kind in (("symptoms","symptom"),("diseases","disease")):
        for item in mk.list_entities(plural,False,""):
            aliases=[]
            if kind=="symptom": aliases=(item.get("aliases_ar") or [])+(item.get("aliases_en") or [])
            for txt in [item.get("name_ar"),item.get("name_en"),*aliases]:
                n=_norm(txt)
                if n: terms.append((n,kind,item.get("slug")))
    return terms


def content_gap_report(days: int = 90, limit: int = 100) -> list[dict]:
    init_schema(); cutoff=(datetime.now(timezone.utc)-timedelta(days=max(1,int(days)))).date().isoformat()
    conn=db._conn(); c=conn.cursor()
    try:
        # Aggregate in Python so this works identically on SQLite and PostgreSQL
        # Keep aggregation in Python for identical SQLite/PostgreSQL behavior.
        c.execute(f"SELECT normalized_query,query_text,metric,clicks,impressions,signal_date,source FROM content_priority_signals WHERE signal_date>={PH}", (cutoff,))
        raw=c.fetchall()
    finally: conn.close()
    agg={}
    for nq,q,metric,clicks,impressions,last_date,source in raw:
        row=agg.setdefault(nq,{"query":q,"metric":0.0,"clicks":0.0,"impressions":0.0,"last_seen":last_date,"sources":set()})
        row["metric"]+=float(metric or 0); row["clicks"]+=float(clicks or 0); row["impressions"]+=float(impressions or 0)
        if str(last_date or "")>str(row.get("last_seen") or ""): row["last_seen"]=last_date; row["query"]=q
        if source: row["sources"].add(str(source))
    ranked=sorted(agg.items(),key=lambda kv:(kv[1]["impressions"]+kv[1]["metric"]+kv[1]["clicks"]*5),reverse=True)
    known=_known_terms(); out=[]
    for nq,row in ranked:
        match=None
        for term,kind,slug in known:
            if nq==term or (len(nq)>=4 and (nq in term or term in nq)):
                match={"kind":kind,"slug":slug}; break
        if not match:
            out.append({"query":row["query"],"priority_score":round(row["metric"]+row["impressions"]+row["clicks"]*5,2),"metric":row["metric"],"clicks":row["clicks"],"impressions":row["impressions"],"last_seen":row["last_seen"],"sources":sorted(row["sources"]),"gap":True})
        if len(out)>=max(1,min(500,int(limit))): break
    return out
