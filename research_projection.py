"""Structured research projection; patient prose is never an export field.

Regex redaction cannot reliably remove names. Only exact catalog terms, bounded
numbers and enumerations cross this boundary. Stored narrative outputs can echo
patient input, so they are omitted too. Personal health records are not changed.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

import clinical_text
import medical_knowledge

WITHHELD = "[نص حر محجوب لحماية الخصوصية | Free text excluded for privacy]"
POLICY = "structured-catalog-only-v1"


def _parts(value):
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if isinstance(v, (str, int, float))]
    return [v.strip() for v in re.split(r"[,،;\n•]+", str(value or "")) if v.strip()]


def _bounded_number(value, low, high):
    if isinstance(value, bool):
        return ""
    try:
        number = float(value)
        return number if low <= number <= high else ""
    except (TypeError, ValueError, OverflowError):
        return ""


def _choice(value, choices, default="unknown"):
    return value if isinstance(value, str) and value in choices else default


class ResearchProjection:
    """Read general KB vocabularies once for a whole export; never patient text."""

    def __init__(self):
        self.symptoms = self._index(medical_knowledge.list_entities("symptoms"))
        self.conditions = self._index(medical_knowledge.list_entities("diseases"))
        self.sources = {}
        for source in medical_knowledge.list_entities("sources"):
            url = str(source.get("official_url") or "")
            host = urlsplit(url).hostname
            if host:
                self.sources[host.lower()] = {"name": source["source_name"], "url": url}

    @staticmethod
    def _index(rows):
        index = {}
        for row in rows:
            aliases = [row.get(k) for k in ("slug", "name_ar", "name_en")]
            aliases += list(row.get("aliases_ar") or []) + list(row.get("aliases_en") or [])
            for alias in aliases:
                if alias:
                    index[clinical_text.normalize_clinical_text(str(alias))] = row
        return index

    @staticmethod
    def terms(value, index, lang):
        labels = []
        for item in _parts(value):
            row = index.get(clinical_text.normalize_clinical_text(item))
            label = (row.get("name_en") if lang == "en" else row.get("name_ar")) if row else WITHHELD
            if label and label not in labels:
                labels.append(label)
        return labels

    def result(self, raw, lang):
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (TypeError, ValueError):
                raw = {}
        if not isinstance(raw, dict) or not raw:
            return {}
        safe = {
            "research_privacy_policy": POLICY,
            "narrative_withheld": True,
            "emergency": raw.get("emergency") is True,
            "urgency": _choice(raw.get("urgency"), {"low", "medium", "high", "followup"}),
            "confidence": _choice(raw.get("confidence"), {"low", "medium", "high", "limited", "insufficient"}),
            "assessment_status": _choice(raw.get("assessment_status"), {
                "general_assessment", "insufficient_information", "emergency", "needs_review",
                "needs_more_information", "supported", "limited", "partial", "complete", "unmatched",
            }),
            "data_quality": {}, "knowledge_matches": [],
            "medical_sources": [], "recommendations": [],
        }
        quality = raw.get("data_quality")
        if isinstance(quality, dict):
            for key in ("score", "completeness_score", "symptom_count", "matched_count", "unmatched_count"):
                number = _bounded_number(quality.get(key), 0, 100)
                if number != "":
                    safe["data_quality"][key] = number
        for match in raw.get("knowledge_matches") or []:
            if not isinstance(match, dict):
                continue
            candidate = match.get("slug") or match.get("name_en") or match.get("name_ar") or match.get("name")
            known = self.conditions.get(clinical_text.normalize_clinical_text(str(candidate or "")))
            if known:
                safe["knowledge_matches"].append({k: known[k] for k in ("slug", "name_ar", "name_en")})
        for source in raw.get("medical_sources") or []:
            if not isinstance(source, dict):
                continue
            try:
                url = urlsplit(str(source.get("url") or source.get("official_url") or source.get("source_url") or ""))
                known = self.sources.get((url.hostname or "").lower()) if url.scheme in {"https", "http"} else None
            except ValueError:
                known = None
            # Return the catalog's name and root URL, never an arbitrary path,
            # query, title or credential copied from the stored output.
            if known and known not in safe["medical_sources"]:
                safe["medical_sources"].append(dict(known))
        # No saved prose, even generated prose, is assumed to be identifier-free.
        for key in ("possible_conditions", "why_result", "danger_signs", "when_to_seek_care", "home_care",
                    "medication_guidance", "questions_for_doctor", "risk_reasons", "needed_information", "risk_label"):
            safe[key] = WITHHELD if raw.get(key) else ""
        if safe["knowledge_matches"]:
            field = "name_en" if lang == "en" else "name_ar"
            safe["possible_conditions"] = "; ".join(dict.fromkeys(m[field] for m in safe["knowledge_matches"]))
        return safe

    def row(self, row):
        """Project the shared 15-column research SELECT used by JSON and Excel."""
        values = list(row)
        lang = _choice(values[3], {"ar", "en"})
        values[3] = lang
        values[6] = ", ".join(self.terms(values[6], self.symptoms, lang))
        values[7] = ", ".join(self.terms(values[7], self.conditions, lang))
        # Medication narratives (dose, prescriber, contacts) are not research text.
        values[8] = WITHHELD if values[8] else ""
        values[9] = self.duration(values[9])
        values[10] = _bounded_number(values[10], 1, 10)
        values[11] = _choice(values[11], {"low", "medium", "high", "followup"})
        values[14] = self.result(values[14], lang)
        return tuple(values)

    @staticmethod
    def duration(value):
        text = str(value or "").lower()
        for label, words in (
            ("Hours", ("hour", "ساعة", "ساعات")), ("Days", ("day", "يوم", "أيام", "ايام")),
            ("Weeks", ("week", "أسبوع", "اسبوع", "أسابيع")), ("Months+", ("month", "شهر", "أشهر", "اشهر")),
        ):
            if any(word in text for word in words):
                return label
        return "Other / unspecified" if text else ""
