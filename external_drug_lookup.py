"""Trusted external medication fallback for SymptoSense.

Flow:
    local curated database (handled by medication_warnings) -> cache ->
    openFDA label lookup -> optional RxNorm name resolution -> openFDA retry.

This module intentionally does not diagnose, recommend treatment, or infer a
missing label section. If an official label cannot be retrieved, no medication
summary is returned.
"""
from __future__ import annotations

import json
import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import db

RXNORM_DRUGS_URL = "https://rxnav.nlm.nih.gov/REST/drugs.json"
RXNORM_APPROX_URL = "https://rxnav.nlm.nih.gov/REST/approximateTerm.json"
RXNORM_PROPERTIES_URL = "https://rxnav.nlm.nih.gov/REST/rxcui/{rxcui}/properties.json"
OPENFDA_LABEL_URL = "https://api.fda.gov/drug/label.json"
DAILYMED_SEARCH_URL = "https://dailymed.nlm.nih.gov/dailymed/search.cfm"

_MAX_QUERY_LEN = 120
_MAX_FIELD_CHARS = 1400
_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60
_MISS_CACHE_TTL_SECONDS = 60 * 60
_TIMEOUT_SECONDS = float(os.getenv("EXTERNAL_DRUG_LOOKUP_TIMEOUT_SECONDS", "2.8") or 2.8)

_ARABIC_SUMMARY_TIMEOUT_SECONDS = float(os.getenv("DRUG_ARABIC_SUMMARY_TIMEOUT_SECONDS", "5.0") or 5.0)
_ARABIC_SUMMARY_MAX_CHARS = 650


def _has_arabic(value: str) -> bool:
    return bool(re.search(r"[\u0600-\u06FF]", str(value or "")))


def _compact_label_text(value: str, limit: int = 520) -> str:
    """Keep label excerpts readable when no language model is available."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return ""
    # Prefer one or two complete sentences and keep a hard upper bound.
    parts = re.split(r"(?<=[.!?])\s+", text)
    out = ""
    for part in parts:
        candidate = (out + " " + part).strip()
        if out and len(candidate) > limit:
            break
        out = candidate
        if len(out) >= min(260, limit):
            break
    if not out:
        out = text[:limit]
    if len(out) > limit:
        out = out[: limit - 1].rstrip() + "…"
    return out


def _parse_json_object(raw: str):
    text = str(raw or "").strip()
    if not text:
        return None
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.S).strip()
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except (TypeError, ValueError, OverflowError):
        m = re.search(r"\{.*\}", text, flags=re.S)
        if not m:
            return None
        try:
            obj = json.loads(m.group(0))
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None


def _generate_arabic_summary(result: dict):
    """Translate/summarize only the retrieved official-label excerpts.

    The model is explicitly forbidden from adding facts, doses, or treatment
    recommendations. Failure returns None so the caller can show the original
    official text rather than inventing a translation.
    """
    if str(os.getenv("DRUG_ARABIC_SUMMARY_ENABLED", "1")).strip().lower() in {"0", "false", "no", "off"}:
        return None
    try:
        import analysis_core
        client = analysis_core._groq_client()
    except Exception:
        return None

    source = {
        "drug_name": result.get("name_en") or result.get("query") or "",
        "generic_name": result.get("generic_name") or "",
        "uses": result.get("uses_en") or "",
        "warnings": result.get("warning_en") or "",
        "interactions": result.get("interact_en") or "",
    }
    prompt = (
        "أنت محرر طبي ثنائي اللغة داخل SymptoSense. ترجم ولخّص النصوص التالية إلى العربية الفصحى الواضحة، "
        "مع الالتزام الحرفي بالمعلومات الموجودة في المصدر فقط. لا تضف تشخيصًا، جرعة، مدة علاج، توصية ببدء أو إيقاف الدواء، "
        "ولا تستنتج معلومة غير مذكورة. حافظ على أي تحذير خطير أو تحذير صندوقي مذكور ولا تحذفه بسبب الاختصار. "
        "اجعل كل حقل جملة أو جملتين قصيرتين قدر الإمكان. إذا كان قسم التداخلات غير موجود فعلًا، اكتب العبارة التالية: "
        "لم تتوفر معلومات منظمة عن التداخلات في السجل المسترجع؛ راجع النشرة الرسمية أو الصيدلي. "
        "أعد JSON فقط بالمفاتيح uses_ar و warning_ar و interact_ar.\n\n"
        + json.dumps(source, ensure_ascii=False)
    )
    try:
        response = client.chat.completions.create(
            model=os.environ.get("GROQ_TEXT_MODEL", "openai/gpt-oss-120b").strip() or "openai/gpt-oss-120b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_completion_tokens=320,
            timeout=min(_ARABIC_SUMMARY_TIMEOUT_SECONDS, 6.0),
        )
        raw = str(response.choices[0].message.content or "")
        obj = _parse_json_object(raw)
    except Exception:
        return None
    if not obj:
        return None
    cleaned = {}
    for key in ("uses_ar", "warning_ar", "interact_ar"):
        val = re.sub(r"\s+", " ", str(obj.get(key) or "")).strip()
        if not val or not _has_arabic(val):
            return None
        cleaned[key] = val[:_ARABIC_SUMMARY_MAX_CHARS].rstrip()
    return cleaned


def localize_external_result(result: dict, lang: str = "ar") -> dict:
    """Return a presentation-safe external result for the requested language."""
    if not isinstance(result, dict) or not result.get("external"):
        return result
    out = dict(result)
    # Keep English pages concise too; never dump a long label paragraph.
    out["uses_en"] = _compact_label_text(out.get("uses_en") or "")
    out["warning_en"] = _compact_label_text(out.get("warning_en") or "", 620)
    out["interact_en"] = _compact_label_text(out.get("interact_en") or "", 520)
    if lang != "ar":
        return out

    ready = all(_has_arabic(out.get(k) or "") for k in ("uses_ar_summary", "warning_ar_summary", "interact_ar_summary"))
    if ready:
        out["uses_ar"] = out["uses_ar_summary"]
        out["warning_ar"] = out["warning_ar_summary"]
        out["interact_ar"] = out["interact_ar_summary"]
        out["arabic_summary_status"] = "cached"
        return out

    generated = _generate_arabic_summary(out)
    if generated:
        out.update(generated)
        out["uses_ar_summary"] = generated["uses_ar"]
        out["warning_ar_summary"] = generated["warning_ar"]
        out["interact_ar_summary"] = generated["interact_ar"]
        out["arabic_summary_status"] = "generated"
        query = str(out.get("query") or "").strip()
        if query:
            try:
                _cache_put(query, out)
            except Exception:
                pass
        return out

    # Arabic pages must not silently switch to English. If translation is
    # unavailable, show a transparent Arabic fallback and keep the official
    # source links so the user can inspect the original label.
    out["uses_ar"] = "تعذر إنشاء ملخص عربي موثوق لهذا القسم الآن. يمكنك فتح النشرة الرسمية من المصادر أدناه."
    out["warning_ar"] = "تعذر ترجمة التحذيرات آليًا دون ضمان الدقة، لذلك لم نعرض ترجمة غير متحقق منها. راجع النشرة الرسمية أو الصيدلي."
    out["interact_ar"] = "تعذر إنشاء ملخص عربي موثوق للتداخلات الآن. راجع النشرة الرسمية أو الصيدلي قبل اتخاذ أي قرار دوائي."
    out["arabic_summary_status"] = "unavailable"
    return out


def _enabled() -> bool:
    return str(os.getenv("EXTERNAL_DRUG_LOOKUP_ENABLED", "1")).strip().lower() not in {"0", "false", "no", "off"}


def _normalize_query(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    if not text or len(text) > _MAX_QUERY_LEN:
        return ""
    # Reject control characters. Arabic/Latin letters, numbers, spaces and
    # ordinary medicine-name punctuation remain allowed.
    if any(ord(ch) < 32 for ch in text):
        return ""
    return text


def _cache_key(query: str) -> str:
    return re.sub(r"\s+", " ", query.casefold()).strip()


def _init_cache_schema() -> None:
    conn = db._conn()
    try:
        c = conn.cursor()
        c.execute(
            """CREATE TABLE IF NOT EXISTS external_drug_cache (
                query_key TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            )"""
        )
        conn.commit()
    finally:
        conn.close()


def _cache_get(query: str):
    _init_cache_schema()
    conn = db._conn()
    try:
        c = conn.cursor()
        c.execute(f"SELECT payload_json,fetched_at FROM external_drug_cache WHERE query_key={db.PH}", (_cache_key(query),))
        row = c.fetchone()
        if not row:
            return None
        try:
            fetched = datetime.fromisoformat(str(row[1]).replace("Z", "+00:00"))
            if fetched.tzinfo is None:
                fetched = fetched.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - fetched.astimezone(timezone.utc)).total_seconds()
            payload = json.loads(row[0])
            if not isinstance(payload, dict):
                return None
            ttl = _MISS_CACHE_TTL_SECONDS if payload.get("_miss") else _CACHE_TTL_SECONDS
            if age > ttl:
                return None
            payload["cache_hit"] = True
            return payload
        except Exception:
            return None
    finally:
        conn.close()
    return None


def _cache_put(query: str, payload: dict) -> None:
    if not payload:
        return
    _init_cache_schema()
    key = _cache_key(query)
    now = datetime.now(timezone.utc).isoformat()
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    conn = db._conn()
    try:
        c = conn.cursor()
        c.execute(f"DELETE FROM external_drug_cache WHERE query_key={db.PH}", (key,))
        c.execute(
            f"INSERT INTO external_drug_cache(query_key,payload_json,fetched_at) VALUES({db.PH},{db.PH},{db.PH})",
            (key, encoded, now),
        )
        conn.commit()
    finally:
        conn.close()


def _http_json(base_url: str, params: dict) -> dict | None:
    query = urllib.parse.urlencode(params)
    url = f"{base_url}?{query}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "SymptoSense/225 medication-information-fallback",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as response:
            if getattr(response, "status", 200) != 200:
                return None
            raw = response.read(1_500_000)
            return json.loads(raw.decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, socket.timeout, ValueError, json.JSONDecodeError):
        return None


def _first_text(label: dict, *keys: str) -> str:
    for key in keys:
        value = label.get(key)
        if isinstance(value, list):
            value = " ".join(str(x) for x in value if x)
        if value:
            text = re.sub(r"\s+", " ", str(value)).strip()
            if text:
                if len(text) > _MAX_FIELD_CHARS:
                    text = text[: _MAX_FIELD_CHARS - 1].rstrip() + "…"
                return text
    return ""


def _list_first(mapping: dict, key: str) -> str:
    value = mapping.get(key)
    if isinstance(value, list) and value:
        return str(value[0]).strip()
    if isinstance(value, str):
        return value.strip()
    return ""


def _openfda_search(term: str):
    # Search three harmonized identity fields. Quoting is escaped for the
    # openFDA query language, then urlencoded by _http_json.
    safe_term = term.replace('"', "").strip()
    if not safe_term:
        return None, None
    search = (
        f'openfda.brand_name:"{safe_term}" OR '
        f'openfda.generic_name:"{safe_term}" OR '
        f'openfda.substance_name:"{safe_term}"'
    )
    params = {"search": search, "limit": 1}
    api_key = str(os.getenv("OPENFDA_API_KEY") or "").strip()
    if api_key:
        params["api_key"] = api_key
    data = _http_json(OPENFDA_LABEL_URL, params)
    if not data or not isinstance(data.get("results"), list) or not data["results"]:
        return None, None
    return data["results"][0], params


def _rxnorm_exact_name(term: str):
    data = _http_json(RXNORM_DRUGS_URL, {"name": term})
    groups = ((data or {}).get("drugGroup") or {}).get("conceptGroup") or []
    # Prefer named branded/clinical drug concepts, then any usable concept.
    preferred = ("SBD", "SCD", "BPCK", "GPCK")
    concepts = []
    for group in groups:
        tty = str(group.get("tty") or "")
        for item in group.get("conceptProperties") or []:
            name = str(item.get("name") or "").strip()
            rxcui = str(item.get("rxcui") or "").strip()
            if name:
                concepts.append((0 if tty in preferred else 1, name, rxcui))
    if not concepts:
        return None
    concepts.sort(key=lambda x: (x[0], len(x[1])))
    return {"name": concepts[0][1], "rxcui": concepts[0][2]}


def _rxnorm_approx_name(term: str):
    data = _http_json(RXNORM_APPROX_URL, {"term": term, "maxEntries": 3, "option": 1})
    candidates = ((data or {}).get("approximateGroup") or {}).get("candidate") or []
    if not candidates:
        return None
    candidates = sorted(candidates, key=lambda x: int(x.get("rank") or 999999))
    rxcui = str(candidates[0].get("rxcui") or "").strip()
    if not rxcui:
        return None
    props = _http_json(RXNORM_PROPERTIES_URL.format(rxcui=urllib.parse.quote(rxcui, safe="")), {})
    properties = (props or {}).get("properties") or {}
    name = str(properties.get("name") or "").strip()
    return {"name": name, "rxcui": rxcui} if name else None


def _canonical_search_terms(query: str):
    terms = [query]
    exact = _rxnorm_exact_name(query)
    if exact and exact.get("name") and exact["name"].casefold() != query.casefold():
        terms.append(exact["name"])
    elif not exact:
        approximate = _rxnorm_approx_name(query)
        if approximate and approximate.get("name") and approximate["name"].casefold() != query.casefold():
            terms.append(approximate["name"])
            exact = approximate
    # Deduplicate while preserving order.
    out = []
    seen = set()
    for term in terms:
        key = term.casefold()
        if key not in seen:
            seen.add(key)
            out.append(term)
    return out, exact


def _result_from_label(query: str, matched_term: str, label: dict, fda_params: dict, rxnorm: dict | None):
    ofda = label.get("openfda") or {}
    brand = _list_first(ofda, "brand_name")
    generic = _list_first(ofda, "generic_name") or _list_first(ofda, "substance_name")
    display = brand or generic or matched_term or query
    scientific = generic or matched_term or query

    uses = _first_text(label, "indications_and_usage", "purpose", "uses")
    warnings = _first_text(label, "boxed_warning", "warnings_and_cautions", "warnings", "do_not_use", "ask_doctor")
    interactions = _first_text(label, "drug_interactions", "ask_doctor_or_pharmacist")
    adverse = _first_text(label, "adverse_reactions")

    # An official label must contain at least one clinically useful section.
    if not any((uses, warnings, interactions, adverse)):
        return None

    fda_url = OPENFDA_LABEL_URL + "?" + urllib.parse.urlencode(fda_params)
    daily_url = DAILYMED_SEARCH_URL + "?" + urllib.parse.urlencode({"query": scientific})
    rx_url = RXNORM_DRUGS_URL + "?" + urllib.parse.urlencode({"name": query})
    sources = [
        {"provider": "openFDA", "role": "official_label", "url": fda_url, "verified": True},
        {"provider": "DailyMed", "role": "official_label_index", "url": daily_url, "verified": True},
        {"provider": "RxNorm", "role": "drug_identity", "url": rx_url, "verified": bool(rxnorm)},
    ]
    return {
        "external": True,
        "cache_hit": False,
        "query": query,
        "matched_term": matched_term,
        "name_en": display,
        "name_ar": display,
        "generic_name": generic,
        "uses_en": uses or "Official label section not available for this record.",
        "uses_ar": uses or "قسم الاستخدامات غير متاح في النشرة الرسمية المسترجعة.",
        "warning_en": warnings or adverse or "Review the official label and ask a clinician or pharmacist for medication-specific warnings.",
        "warning_ar": warnings or adverse or "راجع النشرة الرسمية واسأل الطبيب أو الصيدلي عن التحذيرات الخاصة بهذا الدواء.",
        "interact_en": interactions or "No structured interaction section was returned in this label record; check the official label or pharmacist.",
        "interact_ar": interactions or "لم يُرجع المصدر قسم تداخلات منظمًا لهذا السجل؛ راجع النشرة الرسمية أو الصيدلي.",
        "sources": sources,
        "source_policy": {
            "ok": True,
            "external_verified": True,
            "official_label": True,
            "identity_resolved": bool(rxnorm),
        },
        "notice_ar": "هذه المعلومات مسترجعة من مصادر دوائية خارجية رسمية. يُرسل اسم الدواء فقط لخدمة البحث الخارجية، ثم تُترجم وتُلخّص النصوص الطبية إلى العربية من المصدر نفسه عند توفر خدمة التلخيص.",
        "notice_en": "This information was retrieved from official external drug sources. Only the medication search term is sent to the external lookup service; account and symptom data are not sent. Long label sections are shortened for readability.",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def lookup_external_drug(name: str):
    """Return a verified external medication result, or None.

    No network call is made when the feature is disabled, the query is invalid,
    or a fresh cache entry is available.
    """
    if not _enabled():
        return None
    query = _normalize_query(name)
    if not query:
        return None
    cached = _cache_get(query)
    if cached:
        return None if cached.get("_miss") else cached

    # Fast external path: try the user-supplied brand/generic term against the
    # official FDA labeling first. Only spend another network round trip on
    # RxNorm when that direct lookup misses.
    label, params = _openfda_search(query)
    if label:
        result = _result_from_label(query, query, label, params, None)
        if result:
            _cache_put(query, result)
            return result

    terms, rxnorm = _canonical_search_terms(query)
    for term in terms:
        if term.casefold() == query.casefold():
            continue
        label, params = _openfda_search(term)
        if not label:
            continue
        result = _result_from_label(query, term, label, params, rxnorm)
        if result:
            _cache_put(query, result)
            return result
    _cache_put(query, {"_miss": True})
    return None
