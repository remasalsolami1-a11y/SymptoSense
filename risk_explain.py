"""Specific, plain-language reason for a 'needs medical review' result that came from severity/age rather than
a named red-flag rule. Display text only; it never changes the risk level."""
import re

_AGE_SYMPTOMS = {"shortness-of-breath", "chest-pain", "fever", "dehydration"}


def _clean(x):
    x = re.sub(r"[^\w\s\-/,.()'؀-ۿ]", " ", str(x or ""), flags=re.UNICODE).replace("_", " ")
    return " ".join(x.split())


def _names(canonical, slugs, lang):
    out = []
    for c in canonical or []:
        if isinstance(c, dict) and c.get("slug") in slugs:
            n = c.get("name_en" if lang == "en" else "name_ar") or c.get("name") or c.get("slug")
            if n and n not in out:
                out.append(str(n))
    return out[:3]


def review_hit(severity, age, canonical, raw_symptoms, lang="ar"):
    ar = lang != "en"
    slugs = {c.get("slug") for c in (canonical or []) if isinstance(c, dict)}
    parts = []
    if severity and int(severity) >= 4:
        parts.append((f"اخترتَ شدة الأعراض {int(severity)} من 5" if ar else f"you rated the severity {int(severity)} out of 5"))
    if age and age >= 65 and slugs & _AGE_SYMPTOMS:
        names = _names(canonical, slugs & _AGE_SYMPTOMS, lang) or [c for c in (_clean(s) for s in (raw_symptoms or [])) if c][:2]
        sym = ("، " if ar else ", ").join(names)
        parts.append((f"عمرك {int(age)} سنة مع {sym}، وهذا العمر يرفع الحذر مع هذه الأعراض" if ar else
                      f"you are {int(age)} with {sym}, and at this age these symptoms call for more caution"))
    joined = ("، و" if ar else "; and ").join(parts)
    if ar:
        msg = (f"ظهرت هذه النتيجة لأنك {joined}. " if joined else "") + "لا توجد علامة خطر حادة، لكن هذه العوامل تستدعي تقييمًا طبيًا."
    else:
        msg = (f"This result appeared because {joined}. " if joined else "") + "No acute red flag was found, but these factors warrant a medical review."
    return {"slug": "clinical-review", "name": "تقييم طبي" if ar else "Medical review", "risk_level": "review",
            "message": msg, "description": msg}
