"""Official-source discovery queue for SymptoSense medical content.

This module intentionally does *not* publish medical content. It retrieves
candidate references only from documented official APIs and stores them in a
separate review queue for human verification before anything can enter the
public knowledge base.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from urllib.parse import quote
from defusedxml.ElementTree import fromstring as _safe_xml_fromstring   # untrusted XML: no entity-expansion attacks

import requests

import db

PH = db.PH


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _serial():
    return "SERIAL PRIMARY KEY" if db.USE_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"


def init_schema():
    db.init_db()
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS medical_source_review_queue (
                id {_serial()}, term TEXT NOT NULL, language TEXT NOT NULL,
                provider TEXT NOT NULL, source_key TEXT,
                payload_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft',
                created_at TEXT NOT NULL, reviewed_at TEXT, reviewed_by TEXT
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_med_source_review_status ON medical_source_review_queue(status,created_at)")
        conn.commit()
    finally:
        conn.close()


def _queue(term: str, language: str, provider: str, source_key: str, payload: dict) -> int:
    init_schema(); conn = db._conn(); c = conn.cursor()
    try:
        c.execute(
            f"INSERT INTO medical_source_review_queue(term,language,provider,source_key,payload_json,status,created_at) VALUES({','.join([PH]*7)})",
            (str(term)[:240], language, provider, str(source_key or "")[:500], json.dumps(payload, ensure_ascii=False), "draft", _now()),
        )
        rid = int(c.lastrowid) if not db.USE_POSTGRES else None
        if db.USE_POSTGRES:
            # psycopg2 cursor.lastrowid is not meaningful. Resolve by newest row
            # for this provider/key inside the same transaction.
            c.execute(f"SELECT id FROM medical_source_review_queue WHERE provider={PH} AND source_key={PH} ORDER BY id DESC LIMIT 1", (provider, str(source_key or "")[:500]))
            row = c.fetchone(); rid = int(row[0]) if row else 0
        conn.commit(); return rid or 0
    finally:
        conn.close()


def who_icd11_search(term: str, language: str = "ar", limit: int = 8) -> list[dict]:
    """Search the official WHO ICD-11 MMS API. Requires WHO ICD credentials."""
    client_id = os.getenv("WHO_ICD_CLIENT_ID", "").strip()
    client_secret = os.getenv("WHO_ICD_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError("who_icd_credentials_missing")
    token_resp = requests.post(
        "https://icdaccessmanagement.who.int/connect/token",
        data={"grant_type": "client_credentials", "scope": "icdapi_access"},
        auth=(client_id, client_secret), timeout=15,
    )
    token_resp.raise_for_status()
    token = (token_resp.json() or {}).get("access_token")
    if not token:
        raise RuntimeError("who_icd_token_missing")
    release = os.getenv("WHO_ICD_RELEASE", "2026-01").strip() or "2026-01"
    r = requests.get(
        f"https://id.who.int/icd/release/11/{quote(release)}/mms/search",
        params={"q": term, "useFlexisearch": "true", "flatResults": "true"},
        headers={"Authorization": f"Bearer {token}", "API-Version": "v2", "Accept-Language": "ar" if language == "ar" else "en"},
        timeout=20,
    )
    r.raise_for_status(); data = r.json() or {}
    items = data.get("destinationEntities") or data.get("entities") or []
    out=[]
    for x in items[:max(1, min(20, int(limit)) )]:
        out.append({
            "id": x.get("id") or x.get("theCode") or "",
            "code": x.get("theCode") or x.get("code") or "",
            "title": x.get("title") or x.get("label") or "",
            "chapter": x.get("chapter") or "",
            "provider": "WHO ICD-11",
        })
    return out


def medlineplus_search(term: str, limit: int = 8) -> list[dict]:
    """Search the official MedlinePlus Web Service (healthTopics database)."""
    r = requests.get(
        "https://wsearch.nlm.nih.gov/ws/query",
        params={"db": "healthTopics", "term": term, "rettype": "brief", "retmax": max(1, min(20, int(limit)))},
        timeout=15,
    )
    r.raise_for_status(); root = _safe_xml_fromstring(r.text)
    out=[]
    for doc in root.findall(".//document")[:max(1, min(20, int(limit)))]:
        fields={}
        for content in doc.findall("content"):
            fields[content.attrib.get("name", "")] = "".join(content.itertext()).strip()
        out.append({
            "url": doc.attrib.get("url", ""),
            "title": fields.get("title", ""),
            "snippet": fields.get("snippet", ""),
            "provider": "MedlinePlus",
        })
    return out


def nhs_content(section: str, slug: str, modules: bool = True) -> dict:
    """Fetch one NHS Website Content API v2 record. Requires NHS_CONTENT_API_KEY."""
    key = os.getenv("NHS_CONTENT_API_KEY", "").strip()
    if not key:
        raise RuntimeError("nhs_content_api_key_missing")
    allowed={"conditions", "symptoms", "medicines", "mental-health", "pregnancy"}
    section = str(section or "").strip().strip("/")
    if section not in allowed:
        raise ValueError("unsupported_nhs_section")
    slug = str(slug or "").strip().strip("/")
    if not slug:
        raise ValueError("missing_nhs_slug")
    base = os.getenv("NHS_CONTENT_API_BASE", "https://api.service.nhs.uk/nhs-website-content").rstrip("/")
    r = requests.get(f"{base}/{section}/{quote(slug)}", params={"modules": str(bool(modules)).lower()}, headers={"apikey": key}, timeout=20)
    r.raise_for_status(); data=r.json() or {}
    return {"provider":"NHS", "section":section, "slug":slug, "payload":data}


def queue_research_bundle(term: str, language: str = "ar", nhs_section: str | None = None, nhs_slug: str | None = None) -> dict:
    """Retrieve available official candidates and queue them for human review.

    Provider failures are reported independently. No result is auto-published.
    Mayo Clinic is intentionally not scraped because no public content API is
    assumed; it remains a manual cross-check source in the editorial workflow.
    """
    term = str(term or "").strip()
    if not term:
        raise ValueError("missing_term")
    lang = "en" if language == "en" else "ar"
    result={"term":term, "language":lang, "queued":[], "errors":[], "manual_cross_check":["Mayo Clinic"]}
    providers = [
        ("who_icd11", lambda: who_icd11_search(term, lang)),
        ("medlineplus", lambda: medlineplus_search(term)),
    ]
    if nhs_section and nhs_slug:
        providers.append(("nhs", lambda: [nhs_content(nhs_section, nhs_slug)]))
    for provider, fn in providers:
        try:
            items=fn() or []
            payload={"items":items, "retrieved_at":_now(), "auto_publish":False}
            rid=_queue(term,lang,provider,f"{term}:{nhs_section or ''}:{nhs_slug or ''}",payload)
            result["queued"].append({"provider":provider,"queue_id":rid,"count":len(items)})
        except Exception as exc:
            result["errors"].append({"provider":provider,"error":type(exc).__name__,"detail":str(exc)[:180]})
    return result


def pending(limit: int = 100) -> list[dict]:
    init_schema(); conn=db._conn(); c=conn.cursor()
    try:
        c.execute(f"SELECT id,term,language,provider,source_key,payload_json,status,created_at FROM medical_source_review_queue WHERE status='draft' ORDER BY id DESC LIMIT {max(1,min(500,int(limit)))}")
        rows=c.fetchall()
    finally:
        conn.close()
    out=[]
    for r in rows:
        try: payload=json.loads(r[5] or "{}")
        except Exception: payload={}
        out.append({"id":r[0],"term":r[1],"language":r[2],"provider":r[3],"source_key":r[4],"payload":payload,"status":r[6],"created_at":r[7]})
    return out
