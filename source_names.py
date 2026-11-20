"""English pages must show English source names.

Some trusted sources are stored with an Arabic ``source_name`` and an English
``organization``. In English, prefer the English organisation name.
"""
import re

_AR = re.compile(r"[؀-ۿ]")


def display(src, ar, fallback=""):
    src = src or {}
    name = str(src.get("source_name") or "").strip()
    org = str(src.get("organization") or "").strip()
    other = str(src.get("name") or "").strip()
    if ar:
        return name or org or other or fallback
    for cand in (name, org, other):
        if cand and not _AR.search(cand):
            return cand
    return name or org or other or fallback


def _known():
    out = {"وزارة الصحة السعودية": "Saudi Ministry of Health",
           "وزارة الصحة السعودية — 937": "Saudi Ministry of Health (937)"}
    try:
        import trusted_sources_wiring as w
        for row in w.EXTRA_SOURCES:
            out[row[1]] = row[2]
    except (ImportError, AttributeError, IndexError):
        pass
    return out


_KNOWN = None


def localize(obj, lang):
    """Recursively replace an Arabic ``source_name`` by the English organisation (English output only)."""
    if lang == "ar":
        return obj
    global _KNOWN
    if _KNOWN is None:
        _KNOWN = _known()
    if isinstance(obj, dict):
        for key in ("source", "source_name"):
            val = obj.get(key)
            if isinstance(val, str) and val in _KNOWN:
                obj[key] = _KNOWN[val]
        name, org = obj.get("source_name"), obj.get("organization")
        if isinstance(name, str) and _AR.search(name) and isinstance(org, str) and org and not _AR.search(org):
            obj["source_name"] = org
        for v in obj.values():
            if isinstance(v, (dict, list)):
                localize(v, lang)
    elif isinstance(obj, list):
        for v in obj:
            localize(v, lang)
    return obj
