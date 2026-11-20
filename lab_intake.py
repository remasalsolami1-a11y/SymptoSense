"""High-confidence lab-report intake helpers for SymptoSense.

This module intentionally separates document intake quality and extraction
agreement from medical interpretation. It does not diagnose or classify lab
values. It only helps decide whether the uploaded document can be read safely,
merges two independent vision passes, preserves report metadata/evidence, and
builds conservative cross-context notices for the UI.
"""
from __future__ import annotations

import base64
import io
import math
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from PIL import Image, ImageFilter, ImageOps, ImageStat

import blood_test
import medication_warnings


MAX_PHOTO_PAGES = 5
MAX_COMBINED_IMAGE_BYTES = 25 * 1024 * 1024


def _clean_text(value: Any, limit: int = 180) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _norm_name(value: Any) -> str:
    s = _clean_text(value, 200).lower()
    s = re.sub(r"[^0-9a-z\u0600-\u06ff]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _num(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        n = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def _close_num(a: Any, b: Any) -> bool:
    x, y = _num(a), _num(b)
    if x is None or y is None:
        return x is None and y is None
    return abs(x - y) <= max(1e-7, max(abs(x), abs(y)) * 1e-6)


def assess_image_quality(raw: bytes) -> Dict[str, Any]:
    """Return deterministic document-photo quality signals.

    Hard failure is deliberately conservative. Border/crop detection is not
    guessed from pixels; that signal is left to the two independent vision
    passes and reported as a warning when both agree.
    """
    out: Dict[str, Any] = {
        "ok": False,
        "blocking": True,
        "issues": [],
        "warnings": [],
        "metrics": {},
    }
    try:
        with Image.open(io.BytesIO(raw)) as src:
            w0, h0 = src.size
            if w0 <= 0 or h0 <= 0 or w0 > 12000 or h0 > 12000 or (w0 * h0) > 25_000_000:
                out["issues"] = ["image_dimensions_too_large"]
                return out
            src.load()
            img = ImageOps.exif_transpose(src).convert("RGB")
    except Exception:
        out["issues"] = ["invalid_image"]
        return out

    w, h = img.size
    pixels = w * h
    sample = img.copy()
    sample.thumbnail((640, 640), Image.Resampling.LANCZOS)
    gray = ImageOps.grayscale(sample)
    stat = ImageStat.Stat(gray)
    brightness = float(stat.mean[0])
    contrast = float(stat.stddev[0])
    edge_img = gray.filter(ImageFilter.FIND_EDGES)
    edge_stat = ImageStat.Stat(edge_img)
    edge_energy = float(edge_stat.mean[0])
    edge_variance = float(edge_stat.var[0])
    hist = gray.histogram()
    total = max(1, sum(hist))
    shadow_ratio = sum(hist[:18]) / total
    highlight_ratio = sum(hist[245:]) / total

    issues: List[str] = []
    warnings: List[str] = []
    # A report can be portrait or landscape. Pixel count is more useful than a
    # single-side threshold and keeps ordinary 720p camera images acceptable.
    if pixels < 420_000 or min(w, h) < 420:
        issues.append("low_resolution")
    elif pixels < 850_000 or min(w, h) < 650:
        warnings.append("resolution_could_be_better")

    if brightness < 28 or shadow_ratio > 0.72:
        issues.append("too_dark")
    elif brightness < 52 or shadow_ratio > 0.48:
        warnings.append("dark")

    # White paper naturally has many near-white pixels, so highlight ratio by
    # itself is not treated as glare. We require weak document detail too; this
    # avoids warning on a normal, well-lit lab report simply because the page is
    # mostly white.
    if brightness > 250 and contrast < 8 and edge_energy < 5.0:
        issues.append("overexposed")
    elif highlight_ratio > 0.96 and contrast < 14 and edge_energy < 9.0:
        warnings.append("glare_or_overexposure")

    # Edge energy is a document-friendly blur heuristic. Require multiple weak
    # signals before warning/failing to reduce false positives on sparse forms.
    if contrast < 9 and edge_energy < 5.0:
        issues.append("very_blurry_or_low_contrast")
    elif contrast < 14 and edge_energy < 10.0:
        warnings.append("possible_blur_or_low_contrast")

    out.update({
        "ok": not issues,
        "blocking": bool(issues),
        "issues": sorted(set(issues)),
        "warnings": sorted(set(warnings)),
        "metrics": {
            "width": w,
            "height": h,
            "pixels": pixels,
            "brightness": round(brightness, 1),
            "contrast": round(contrast, 1),
            "edge_energy": round(edge_energy, 1),
            "highlight_ratio": round(highlight_ratio, 3),
            "shadow_ratio": round(shadow_ratio, 3),
        },
    })
    return out


def quality_message(quality: Dict[str, Any], lang: str = "ar") -> str:
    ar = lang == "ar"
    labels_ar = {
        "invalid_image": "ملف الصورة غير صالح",
        "image_dimensions_too_large": "أبعاد الصورة أكبر من الحد الآمن",
        "low_resolution": "دقة الصورة منخفضة جدًا",
        "too_dark": "الصورة مظلمة جدًا",
        "overexposed": "الإضاءة زائدة وتخفي التفاصيل",
        "very_blurry_or_low_contrast": "الصورة غير واضحة أو التباين ضعيف جدًا",
        "resolution_could_be_better": "يفضل التصوير بدقة أعلى",
        "dark": "الإضاءة منخفضة",
        "glare_or_overexposure": "قد يوجد انعكاس ضوء أو سطوع زائد",
        "possible_blur_or_low_contrast": "قد تكون بعض الأرقام غير حادة بما يكفي",
        "page_may_be_cropped": "قد يكون جزء من التقرير خارج الصورة",
        "vision_quality_disagreement": "اختلف فحصا جودة الصورة ويجب مراجعة الصفحة بعناية",
        "vision_reported_unreadable": "فحص الصورة البصري أشار إلى أن الصفحة غير مقروءة بما يكفي",
    }
    labels_en = {
        "invalid_image": "The image file is invalid",
        "image_dimensions_too_large": "The image dimensions exceed the safe limit",
        "low_resolution": "The image resolution is too low",
        "too_dark": "The image is too dark",
        "overexposed": "The image is overexposed",
        "very_blurry_or_low_contrast": "The image is too blurry or low-contrast",
        "resolution_could_be_better": "A higher-resolution photo would be better",
        "dark": "Lighting is low",
        "glare_or_overexposure": "There may be glare or overexposure",
        "possible_blur_or_low_contrast": "Some numbers may not be sharp enough",
        "page_may_be_cropped": "Part of the report may be outside the photo",
        "vision_quality_disagreement": "The two image-quality checks disagreed; review the page carefully",
        "vision_reported_unreadable": "The visual quality check reported that the page is not readable enough",
    }
    labels = labels_ar if ar else labels_en
    keys = list(quality.get("issues") or []) + list(quality.get("warnings") or [])
    readable = [labels.get(k, k) for k in keys]
    if not readable:
        return "جودة الصورة مناسبة للقراءة." if ar else "Image quality is suitable for reading."
    prefix = "؛ ".join(readable)
    if quality.get("blocking"):
        return (prefix + ". أعد التصوير مع إظهار الورقة كاملة وبإضاءة ثابتة ومن دون اهتزاز.") if ar else (prefix + ". Retake the photo with the full page visible, steady lighting, and no motion blur.")
    return (prefix + ". يمكنك المتابعة، لكن راجع القيم المستخرجة بعناية.") if ar else (prefix + ". You can continue, but review the extracted values carefully.")


def make_page_preview(raw: bytes, max_width: int = 1100, quality: int = 76) -> str:
    """Return a compact JPEG preview as base64, without persisting the source."""
    with Image.open(io.BytesIO(raw)) as src:
        img = ImageOps.exif_transpose(src).convert("RGB")
        if img.width > max_width:
            h = max(1, int(img.height * (max_width / img.width)))
            img = img.resize((max_width, h), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=quality, optimize=True)
        return base64.b64encode(out.getvalue()).decode("ascii")


def parse_bbox(value: Any) -> Optional[List[int]]:
    nums = re.findall(r"-?\d+(?:\.\d+)?", str(value or ""))
    if len(nums) < 4:
        return None
    try:
        vals = [int(round(float(x))) for x in nums[:4]]
    except ValueError:
        return None
    x1, y1, x2, y2 = vals
    x1, x2 = sorted((max(0, min(1000, x1)), max(0, min(1000, x2))))
    y1, y2 = sorted((max(0, min(1000, y1)), max(0, min(1000, y2))))
    if x2 - x1 < 8 or y2 - y1 < 5:
        return None
    return [x1, y1, x2, y2]


def normalize_report_meta(meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    meta = meta if isinstance(meta, dict) else {}
    def date_value(v: Any) -> str:
        s = _clean_text(v, 24)
        # Keep an explicitly printed date but never invent one. ISO is preferred.
        return s if re.fullmatch(r"[0-9A-Za-z\u0600-\u06ff ./\-]{1,24}", s or "") else ""
    return {
        "lab_name": _clean_text(meta.get("lab_name"), 120),
        "sample_date": date_value(meta.get("sample_date")),
        "report_date": date_value(meta.get("report_date")),
        "report_type": _clean_text(meta.get("report_type"), 80),
        "age_text": _clean_text(meta.get("age_text"), 48),
    }


def parse_vision_payload(text: str) -> Dict[str, Any]:
    """Parse metadata/quality/evidence while preserving parser-compatible rows."""
    meta: Dict[str, Any] = {}
    quality: Dict[str, Any] = {"status": "", "issues": []}
    evidence: List[Dict[str, Any]] = []
    clean_lines: List[str] = []
    for raw_line in re.split(r"[\r\n]+", str(text or "")):
        line = raw_line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        tag = parts[0].upper() if parts else ""
        if tag == "META":
            # Preferred positional format from the prompt. Also tolerate KEY=VALUE.
            kv = {}
            for p in parts[1:]:
                if "=" in p:
                    k, v = p.split("=", 1)
                    kv[k.strip().upper()] = v.strip()
            if kv:
                meta = {
                    "lab_name": kv.get("LAB", ""),
                    "sample_date": kv.get("SAMPLE_DATE", ""),
                    "report_date": kv.get("REPORT_DATE", ""),
                    "report_type": kv.get("REPORT_TYPE", ""),
                    "age_text": kv.get("AGE", ""),
                }
            elif len(parts) >= 6:
                meta = {
                    "lab_name": parts[1], "sample_date": parts[2],
                    "report_date": parts[3], "report_type": parts[4],
                    "age_text": parts[5],
                }
            continue
        if tag == "QUALITY":
            kv = {}
            for p in parts[1:]:
                if "=" in p:
                    k, v = p.split("=", 1)
                    kv[k.strip().upper()] = v.strip()
            status = (kv.get("STATUS") or (parts[1] if len(parts) > 1 else "")).strip().lower()
            issues = kv.get("ISSUES") or (parts[2] if len(parts) > 2 else "")
            quality = {
                "status": status if status in {"good", "warn", "fail"} else "",
                "issues": [x.strip() for x in re.split(r"[;,]", issues) if x.strip()][:8],
            }
            continue
        if tag == "TEST" and len(parts) >= 7:
            # TEST | NAME | VALUE | UNIT | LOW | HIGH | STATUS | BBOX
            row = parts[1:7]
            bbox = parse_bbox(parts[7]) if len(parts) > 7 else None
            evidence.append({
                "name": row[0], "value": row[1], "bbox": bbox,
                "row_index": len(evidence),
            })
            clean_lines.append(" | ".join(row))
            continue
        # Backward-compatible six-column output from older/model fallback.
        clean_lines.append(line)
    return {
        "clean_text": "\n".join(clean_lines),
        "meta": normalize_report_meta(meta),
        "quality": quality,
        "evidence": evidence,
    }


def _entry_id(page: int, entry: Dict[str, Any]) -> str:
    base = f"{page}|{entry.get('key','')}|{_norm_name(entry.get('name'))}|{entry.get('value','')}"
    import hashlib
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:18]


def _evidence_for(entry: Dict[str, Any], evidence: List[Dict[str, Any]], index: int) -> Optional[Dict[str, Any]]:
    en = _norm_name(entry.get("name"))
    ev = None
    for item in evidence:
        if _norm_name(item.get("name")) == en and _close_num(item.get("value"), entry.get("value")):
            ev = item
            break
    if ev is None and index < len(evidence):
        ev = evidence[index]
    return ev


def merge_double_pass(first_payload: Dict[str, Any], second_payload: Dict[str, Any], page: int = 1) -> Tuple[List[Dict[str, Any]], Optional[float]]:
    """Merge two independent extraction passes and expose disagreements.

    The chosen value is merely a review default. Any disagreement is marked
    ``review_required`` and must be explicitly confirmed by the user later.
    """
    first, age1 = blood_test.parse_blood_text(first_payload.get("clean_text") or "")
    second, age2 = blood_test.parse_blood_text(second_payload.get("clean_text") or "")

    def bucket(rows: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        out: Dict[str, List[Dict[str, Any]]] = {}
        for r in rows or []:
            k = str(r.get("key") or "") or _norm_name(r.get("name"))
            out.setdefault(k, []).append(r)
        return out

    b1, b2 = bucket(first), bucket(second)
    keys = list(dict.fromkeys(list(b1.keys()) + list(b2.keys())))
    merged: List[Dict[str, Any]] = []
    for key in keys:
        r1 = (b1.get(key) or [None])[0]
        r2 = (b2.get(key) or [None])[0]
        chosen = dict(r1 or r2 or {})
        reasons: List[str] = []
        if r1 is None or r2 is None:
            reasons.append("seen_in_one_pass_only")
        else:
            if not _close_num(r1.get("value"), r2.get("value")):
                reasons.append("value_disagreement")
            u1, u2 = _clean_text(r1.get("unit"), 32).lower(), _clean_text(r2.get("unit"), 32).lower()
            if u1 and u2 and u1 != u2:
                reasons.append("unit_disagreement")
            for field in ("reference_low", "reference_high"):
                a, b = r1.get(field), r2.get(field)
                if a not in (None, "") and b not in (None, "") and not _close_num(a, b):
                    reasons.append("range_disagreement")
                    break
            s1, s2 = _clean_text(r1.get("reported_status"), 20).lower(), _clean_text(r2.get("reported_status"), 20).lower()
            if s1 and s2 and s1 != s2:
                reasons.append("status_disagreement")

        ev = _evidence_for(chosen, first_payload.get("evidence") or [], len(merged))
        if not ev:
            ev = _evidence_for(chosen, second_payload.get("evidence") or [], len(merged))
        review_id = _entry_id(page, chosen)
        chosen.update({
            "source_page": int(page),
            "source_bbox": (ev or {}).get("bbox"),
            "review_required": bool(reasons),
            "review_id": review_id,
            "review_reasons": sorted(set(reasons)),
            "pass1_value": (r1 or {}).get("value"),
            "pass2_value": (r2 or {}).get("value"),
            "pass1_unit": (r1 or {}).get("unit") or "",
            "pass2_unit": (r2 or {}).get("unit") or "",
        })
        merged.append(chosen)
    return merged, age1 if age1 is not None else age2



def canonical_vision_quality_issues(values: Iterable[Any]) -> List[str]:
    """Map free-form vision quality notes to deterministic UI issue codes.

    Vision text is treated only as a supporting quality signal. Unknown wording
    falls back to a generic unreadable-page code rather than inventing a more
    specific failure reason.
    """
    text = normalize_symptom_text(" ".join(str(x or "") for x in (values or [])))
    codes: List[str] = []
    groups = [
        (("crop", "cut off", "outside", "مقص", "خارج الصوره", "خارج الصورة"), "page_may_be_cropped"),
        (("blur", "blurry", "out of focus", "غير واضح", "ضباب", "مهزوز"), "very_blurry_or_low_contrast"),
        (("dark", "underexposed", "مظلم", "اضاءه منخفض", "إضاءة منخفض"), "too_dark"),
        (("glare", "overexposed", "reflection", "انعكاس", "سطوع زائد", "اضاءه زائده", "إضاءة زائدة"), "overexposed"),
        (("low resolution", "pixelated", "دقه منخفض", "دقة منخفض"), "low_resolution"),
    ]
    for needles, code in groups:
        if any(normalize_symptom_text(n) in text for n in needles):
            codes.append(code)
    if text.strip() and not codes:
        codes.append("vision_reported_unreadable")
    return sorted(set(codes))


def vision_evidence_rows(payload: Dict[str, Any], page: int) -> List[Dict[str, Any]]:
    """Return parsed rows annotated with page/bounding-box evidence."""
    rows, _ = blood_test.parse_blood_text((payload or {}).get("clean_text") or "")
    evidence = list((payload or {}).get("evidence") or [])
    out: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows or []):
        item = dict(row)
        ev = _evidence_for(item, evidence, idx)
        item["source_page"] = int(page)
        item["source_bbox"] = (ev or {}).get("bbox")
        out.append(item)
    return out


def attach_source_evidence(entries: Iterable[Dict[str, Any]], candidates: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Attach best-effort source page/bbox data to parsed report rows."""
    pool = [dict(x) for x in (candidates or []) if isinstance(x, dict)]
    result: List[Dict[str, Any]] = []
    for raw in entries or []:
        row = dict(raw)
        key = str(row.get("key") or "")
        name = _norm_name(row.get("name"))
        match = None
        for cand in pool:
            ckey = str(cand.get("key") or "")
            cname = _norm_name(cand.get("name"))
            if key and ckey and key != ckey:
                continue
            if not key and name and cname and name != cname:
                continue
            if not _close_num(row.get("value"), cand.get("value")):
                continue
            match = cand
            break
        if match:
            row["source_page"] = match.get("source_page")
            row["source_bbox"] = match.get("source_bbox")
        result.append(row)
    return result

def combine_page_entries(pages: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate repeated rows across photo pages without hiding conflicts."""
    out: List[Dict[str, Any]] = []
    by_key: Dict[str, int] = {}
    for row in pages:
        key = str(row.get("key") or "") or _norm_name(row.get("name"))
        if key not in by_key:
            by_key[key] = len(out)
            out.append(dict(row))
            continue
        idx = by_key[key]
        prev = out[idx]
        same = _close_num(prev.get("value"), row.get("value")) and _clean_text(prev.get("unit"), 32).lower() == _clean_text(row.get("unit"), 32).lower()
        if same:
            # Keep the stronger evidence/review state but do not create duplicate
            # clinical rows for the same marker. If only the duplicate row needs
            # review, surface that row's two-pass evidence instead of showing an
            # apparently clean pair from the first page.
            if not prev.get("source_bbox") and row.get("source_bbox"):
                prev["source_bbox"] = row.get("source_bbox")
                prev["source_page"] = row.get("source_page")
            if row.get("review_required") and not prev.get("review_required"):
                for field in ("pass1_value", "pass2_value", "pass1_unit", "pass2_unit", "review_id"):
                    if row.get(field) not in (None, ""):
                        prev[field] = row.get(field)
            prev["review_required"] = bool(prev.get("review_required") or row.get("review_required"))
            prev["review_reasons"] = sorted(set((prev.get("review_reasons") or []) + (row.get("review_reasons") or [])))
        else:
            prev["review_required"] = True
            prev["review_reasons"] = sorted(set((prev.get("review_reasons") or []) + ["across_pages_disagreement"]))
            prev["pass1_value"] = prev.get("value")
            prev["pass2_value"] = row.get("value")
            prev["pass1_unit"] = prev.get("unit") or ""
            prev["pass2_unit"] = row.get("unit") or ""
            prev["page_conflict_value"] = row.get("value")
            prev["page_conflict_page"] = row.get("source_page")
    return out


def merge_report_metadata(items: Iterable[Dict[str, Any]], entries: Optional[Iterable[Dict[str, Any]]] = None) -> Dict[str, Any]:
    metas = [normalize_report_meta(x) for x in items if isinstance(x, dict)]
    result = {"lab_name": "", "sample_date": "", "report_date": "", "report_type": "", "age_text": ""}
    disagreements: List[str] = []
    for field in result:
        vals = [m.get(field) for m in metas if m.get(field)]
        if vals:
            result[field] = vals[0]
            if any(v != vals[0] for v in vals[1:]):
                disagreements.append(field)
    if not result["report_type"] and entries:
        result["report_type"] = infer_report_type(entries)
    result["metadata_review_fields"] = sorted(set(disagreements))
    return result


def infer_report_type(entries: Iterable[Dict[str, Any]]) -> str:
    keys = {str(x.get("key") or "") for x in entries or []}
    if not keys:
        return ""
    if keys & {"hgb", "rbc", "hct", "wbc", "plt", "mcv", "mch", "mchc"}:
        return "CBC / Complete Blood Count"
    if keys & {"tsh", "free_t4", "free_t3"}:
        return "Thyroid panel"
    if keys & {"chol_total", "ldl", "hdl", "triglycerides"}:
        return "Lipid panel"
    if keys & {"alt", "ast", "alp", "bilirubin", "albumin"}:
        return "Liver panel"
    if keys & {"creatinine", "egfr", "bun", "urea"}:
        return "Kidney panel"
    return "Laboratory report"


def normalize_symptom_text(value: Any) -> str:
    s = str(value or "").lower()
    trans = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي"})
    s = s.translate(trans)
    return re.sub(r"\s+", " ", s)


# Conservative marker-to-symptom bridge. These are association hints only and
# every generated message explicitly states that the lab value does not prove
# the cause. The list is intentionally narrow rather than exhaustive.
_CONTEXT_SYMPTOM_KEYS = {
    ("hgb", "low"): ["دوخ", "تعب", "ضعف", "شحوب", "خفقان", "ضيق نفس", "dizz", "fatigue", "weak", "pale", "palpitation", "shortness of breath"],
    ("rbc", "low"): ["دوخ", "تعب", "ضعف", "شحوب", "ضيق نفس", "dizz", "fatigue", "weak", "pale", "shortness of breath"],
    ("hct", "low"): ["دوخ", "تعب", "ضعف", "شحوب", "ضيق نفس", "dizz", "fatigue", "weak", "pale", "shortness of breath"],
    ("ferritin", "low"): ["دوخ", "تعب", "ضعف", "fatigue", "dizz", "weak"],
    ("iron", "low"): ["دوخ", "تعب", "ضعف", "fatigue", "dizz", "weak"],
    ("glucose", "low"): ["دوخ", "رجف", "تعرق", "جوع", "dizz", "shak", "sweat", "hunger"],
    ("glucose", "high"): ["عطش", "تبول", "تعب", "thirst", "urination", "fatigue"],
    ("wbc", "high"): ["حراره", "حمى", "قشعر", "fever", "chill"],
    ("neut", "high"): ["حراره", "حمى", "قشعر", "fever", "chill"],
    ("plt", "low"): ["كدم", "نزيف", "لثه", "انف", "bruise", "bleed", "gum", "nosebleed"],
}


def build_health_context_links(indicators: Iterable[Dict[str, Any]], latest_record: Optional[Dict[str, Any]] = None, medications: str = "", lang: str = "ar") -> List[Dict[str, Any]]:
    """Build non-diagnostic links between labs, recent symptoms, and medicines."""
    ar = lang == "ar"
    rec = latest_record if isinstance(latest_record, dict) else {}
    symptoms_value = rec.get("symptoms")
    if isinstance(symptoms_value, (list, tuple)):
        symptom_parts = [_clean_text(x, 120) for x in symptoms_value if _clean_text(x, 120)]
        symptoms_value = "، ".join(symptom_parts)
    else:
        symptom_parts = [_clean_text(x, 120) for x in re.split(r"[,،;/]+", str(symptoms_value or "")) if _clean_text(x, 120)]
    symptom_raw = _clean_text(symptoms_value, 600)
    symptom_norm = normalize_symptom_text(symptom_raw)
    links: List[Dict[str, Any]] = []
    for ind in indicators or []:
        key = str(ind.get("key") or "")
        status = str(ind.get("status") or "")
        terms = _CONTEXT_SYMPTOM_KEYS.get((key, status)) or []
        if symptom_norm and terms and any(normalize_symptom_text(t) in symptom_norm for t in terms):
            name = _clean_text(ind.get("name"), 80)
            value = ind.get("value")
            unit = _clean_text(ind.get("unit"), 24)
            links.append({
                "type": "symptom_lab",
                "title": "معلومة قد تكون مرتبطة" if ar else "Information that may be related",
                "text": (
                    f"ذكرت في آخر تحليل أعراض محفوظ «{symptom_raw[:140]}»، ويظهر في التقرير المرتبط أن {name} ({value} {unit}) خارج نطاق مختبرك. قد توجد علاقة في بعض الحالات، لكن هذه المعلومة وحدها لا تحدد سبب الأعراض ولا تمثل تشخيصًا."
                    if ar else
                    f"In your latest saved symptom analysis, you reported “{symptom_raw[:140]}”, and the linked report shows {name} ({value} {unit}) outside your laboratory range. These can be related in some situations, but this information alone does not establish the cause or a diagnosis."
                ),
                "marker_key": key,
            })
            if len(links) >= 2:
                break

    med_text = _clean_text(medications, 500)
    if med_text:
        # Reuse the project's curated medication-warning layer. We expose a
        # medication as context only; we never assert that it caused a symptom
        # or a laboratory change. This keeps the cross-link useful while
        # preserving the boundary between association and diagnosis.
        recognized = medication_warnings.check_medications(med_text) or []
        if recognized:
            med = recognized[0]
            med_name = _clean_text(med.get("name_ar" if ar else "name_en"), 80)
            warning = _clean_text(med.get("warning_ar" if ar else "warning_en"), 260)
            warning_norm = normalize_symptom_text(warning)
            matched_symptom = ""
            for part in symptom_parts:
                pn = normalize_symptom_text(part)
                # Exact phrase matching is intentionally conservative; we do
                # not infer pharmacologic causation from broad semantic
                # similarity.
                if len(pn) >= 3 and pn in warning_norm:
                    matched_symptom = part
                    break
            if matched_symptom:
                text = (
                    f"ذكرت في آخر تحليل أعراض محفوظ «{matched_symptom}»، والدواء المسجل «{med_name}» له تنبيه عام في مكتبة الأدوية يذكر هذا العرض ضمن آثاره المحتملة: {warning} وجودهما معًا لا يثبت أن الدواء هو السبب؛ توقيت بدء العرض بالنسبة لبدء الدواء أو تغيير الجرعة يساعد الطبيب أو الصيدلي على التقييم. لا توقف أو تغيّر دواءً موصوفًا من نفسك."
                    if ar else
                    f"In your latest saved symptom analysis, you reported “{matched_symptom}”, and the recorded medicine “{med_name}” has a general library caution that includes this symptom among possible effects: {warning} Their co-occurrence does not prove the medicine caused the symptom; timing relative to starting the medicine or changing the dose can help a clinician or pharmacist assess it. Do not stop or change a prescribed medicine on your own."
                )
            else:
                text = (
                    f"الدواء المسجل «{med_name}» له تنبيه عام في مكتبة الأدوية: {warning} توقيت بدء العرض بالنسبة لبدء الدواء أو تغيير الجرعة قد يساعد الطبيب أو الصيدلي، لكنه لا يثبت أن الدواء هو السبب. لا توقف أو تغيّر دواءً موصوفًا من نفسك."
                    if ar else
                    f"The recorded medicine “{med_name}” has this general caution in the medicine library: {warning} The timing of a symptom relative to starting the medicine or changing a dose can help a clinician or pharmacist, but it does not prove the medicine caused the symptom. Do not stop or change a prescribed medicine on your own."
                )
            links.append({
                "type": "medication_context",
                "title": "دواؤك والسياق" if ar else "Your medicine and context",
                "text": text,
            })
        else:
            links.append({
                "type": "medication_context",
                "title": "دواؤك والسياق" if ar else "Your medicine and context",
                "text": (
                    "لديك أدوية مسجلة في ملفك الصحي. توقيت بدء العرض بالنسبة لبدء الدواء أو تغيير الجرعة قد يساعد الطبيب أو الصيدلي على فهم الصورة، لكن لا يثبت أن الدواء هو السبب. لا توقف أو تغيّر دواءً موصوفًا من نفسك."
                    if ar else
                    "You have medicines recorded in your health profile. The timing of a symptom relative to starting a medicine or changing a dose can help a clinician or pharmacist interpret the picture, but it does not prove the medicine is the cause. Do not stop or change a prescribed medicine on your own."
                ),
            })
    return links[:3]


def extract_report_metadata_from_text(text: str, entries: Optional[Iterable[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Conservative metadata extraction for text-layer PDFs.

    Dates are captured only when a nearby label makes their meaning clear.
    Unlabelled dates are not guessed as collection/report dates.
    """
    raw = str(text or "")
    lines = [re.sub(r"\s+", " ", x).strip() for x in re.split(r"[\r\n]+", raw) if x.strip()]
    meta: Dict[str, Any] = {}
    date_rx = r"([0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2}|[0-9]{1,2}[-/.][0-9]{1,2}[-/.][0-9]{2,4})"
    for line in lines[:120]:
        low = normalize_symptom_text(line)
        if not meta.get("sample_date") and any(k in low for k in ("sample date", "collection date", "collected", "specimen date", "تاريخ سحب", "تاريخ العينه", "تاريخ العينة")):
            m = re.search(date_rx, line, flags=re.I)
            if m:
                meta["sample_date"] = m.group(1)
        if not meta.get("report_date") and any(k in low for k in ("report date", "reported", "result date", "تاريخ التقرير", "تاريخ النتيجه", "تاريخ النتيجة")):
            m = re.search(date_rx, line, flags=re.I)
            if m:
                meta["report_date"] = m.group(1)
        if not meta.get("lab_name") and any(k in low for k in ("laboratory", "مختبر", "مختبرات", "lab ")):
            # Avoid capturing generic column headers such as "laboratory result".
            candidate = _clean_text(line, 120)
            if len(candidate) >= 4 and not re.search(r"reference range|result|النتيجه|النطاق المرجعي", low):
                meta["lab_name"] = candidate
    meta["report_type"] = infer_report_type(entries or [])
    return normalize_report_meta(meta)
