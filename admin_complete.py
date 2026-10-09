"""Complete, privacy-preserving Admin analytics and export helpers.

The functions in this module only read real persisted data.  Health and
medication analytics use records that were marked analytics-eligible at
collection time, suppress small cohorts, and never return email addresses,
passwords, tokens, chat text, or raw health profiles.
"""
from __future__ import annotations
import logging

import hashlib
import hmac
import io
import json
import os
import re
import secrets
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import db
import ml_diagnosis
import platform_v2
import privacy_features
import research_study
import release_candidate

PH = db.PH
_EPHEMERAL_EXPORT_SECRET = secrets.token_bytes(32)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _table_exists(cur, table: str) -> bool:
    if db.USE_POSTGRES:
        cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name=%s", (table,))
    else:
        cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return bool(cur.fetchone())


def _privacy_threshold() -> int:
    try:
        return max(3, min(20, int(os.environ.get("ANALYTICS_PRIVACY_THRESHOLD", "5"))))
    except (TypeError, ValueError):
        return 5


def _split_items(value) -> list[str]:
    ignored = {"", "none", "no", "n/a", "na", "لا", "لا يوجد", "لايوجد", "-"}
    result = []
    for raw in re.split(r"[,،;|\n]+", str(value or "")):
        item = re.sub(r"\s+", " ", raw).strip(" .-")[:100]
        if item.casefold() not in ignored and item:
            result.append(item)
    return result


def _age_group(age) -> str:
    try:
        value = int(age)
    except (TypeError, ValueError):
        return "Unknown"
    if value < 18:
        return "Under 18"
    if value <= 25:
        return "18–25"
    if value <= 35:
        return "26–35"
    if value <= 45:
        return "36–45"
    if value <= 55:
        return "46–55"
    return "56+"


def _gender(value) -> str:
    text = str(value or "").strip().casefold()
    if text in {"m", "male", "man", "ذكر"}:
        return "Male"
    if text in {"f", "female", "woman", "أنثى", "انثى"}:
        return "Female"
    if text in {"other", "آخر", "اخر"}:
        return "Other"
    return "Unknown"


def _risk(value) -> str:
    text = str(value or "").strip().casefold()
    if text in {"high", "urgent", "emergency"}:
        return "Urgent"
    if text in {"medium", "review", "needs_followup", "needs follow-up", "today"}:
        return "Needs Medical Review"
    if text in {"low", "normal"}:
        return "Low Risk"
    return "Unknown"


def _severity_band(value) -> str:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return "Unknown"
    if number <= 3:
        return "1–3"
    if number <= 6:
        return "4–6"
    return "7–10"


def _duration_band(value) -> str:
    text = str(value or "").strip().casefold()
    if not text:
        return "Unknown"
    if any(word in text for word in ("hour", "hours", "ساعة", "ساعات")):
        return "Hours"
    if any(word in text for word in ("day", "days", "يوم", "أيام", "ايام")):
        return "Days"
    if any(word in text for word in ("week", "weeks", "أسبوع", "اسبوع", "أسابيع")):
        return "Weeks"
    if any(word in text for word in ("month", "months", "شهر", "أشهر", "اشهر")):
        return "Months+"
    return "Other / unspecified"


def _safe_rows(counter: Counter, users: dict, threshold: int, limit=20) -> list[dict]:
    rows = []
    for label, count in counter.most_common(limit):
        distinct = len(users.get(label, set()))
        if distinct >= threshold:
            rows.append({"label": label, "count": int(count), "distinct_users": distinct})
    return rows


def _analytics_records(days: int | None = None) -> list[dict]:
    clauses = ["COALESCE(analytics_eligible,0)=1"]
    params = []
    if days:
        clauses.append(f"timestamp>={PH}")
        params.append((_now() - timedelta(days=days)).isoformat())
    conn = db._conn(); cur = conn.cursor()
    try:
        cur.execute(
            "SELECT user_hash,timestamp,lang,age,gender,symptoms,medications,duration,severity,urgency "
            "FROM records WHERE " + " AND ".join(clauses) + " ORDER BY timestamp",
            tuple(params),
        )
        return [
            {
                "user_hash": str(row[0]), "timestamp": str(row[1] or ""),
                "lang": str(row[2] or "unknown"), "age": row[3],
                "age_group": _age_group(row[3]), "gender": _gender(row[4]),
                "symptoms": _split_items(row[5]), "medications": _split_items(row[6]),
                "duration": _duration_band(row[7]), "duration_raw": str(row[7] or ""),
                "severity": row[8], "severity_band": _severity_band(row[8]),
                "risk": _risk(row[9]),
            }
            for row in cur.fetchall()
        ]
    finally:
        conn.close()


def complete_analytics(days=30) -> dict:
    """Return the Admin overview plus aggregate user/health/medication analytics."""
    platform_v2.init_schema(); privacy_features.init_schema()
    all_time = str(days).strip().lower() == "all"
    try:
        days = max(1, min(365, int(days))) if not all_time else None
    except (TypeError, ValueError):
        days = 30; all_time = False
    now = _now(); since = datetime(1970, 1, 1, tzinfo=timezone.utc) if all_time else now - timedelta(days=days)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week = now - timedelta(days=7); month = now - timedelta(days=30)
    threshold = _privacy_threshold()

    conn = db._conn(); cur = conn.cursor()
    try:
        def count(sql, params=()):
            cur.execute(sql, params)
            row = cur.fetchone()
            return int((row or [0])[0] or 0)

        total_users = count("SELECT COUNT(*) FROM ss_users")
        total_analyses = count("SELECT COUNT(*) FROM records")
        assistant_conversations = count("SELECT COUNT(*) FROM ss_usage_events WHERE event_type='assistant_use'")
        report_count = count("SELECT COUNT(*) FROM ss_usage_events WHERE event_type='report_generated'")
        web_reminders = count("SELECT COUNT(*) FROM med_plans WHERE COALESCE(active,1)=1") if _table_exists(cur, "med_plans") else 0
        bot_reminders = count("SELECT COUNT(*) FROM med_reminders WHERE COALESCE(active,1)=1") if _table_exists(cur, "med_reminders") else 0
        activity_today = count(f"SELECT COUNT(*) FROM ss_usage_events WHERE created_at>={PH}", (today.isoformat(),))
        activity_week = count(f"SELECT COUNT(*) FROM ss_usage_events WHERE created_at>={PH}", (week.isoformat(),))
        activity_month = count(f"SELECT COUNT(*) FROM ss_usage_events WHERE created_at>={PH}", (month.isoformat(),))
        new_users = count(f"SELECT COUNT(*) FROM ss_users WHERE created_at>={PH}", (since.isoformat(),))
        active_users = count(
            f"SELECT COUNT(DISTINCT user_id) FROM ss_login_activity WHERE success=1 AND user_id IS NOT NULL AND occurred_at>={PH}",
            (since.isoformat(),),
        )
        cur.execute(
            f"SELECT lang,COUNT(*) FROM ss_usage_events WHERE created_at>={PH} GROUP BY lang",
            (since.isoformat(),),
        )
        languages = {str(k or "unknown"): int(v) for k, v in cur.fetchall()}
        cur.execute(
            f"SELECT device_type,COUNT(*) FROM ss_usage_events WHERE created_at>={PH} GROUP BY device_type",
            (since.isoformat(),),
        )
        devices = {str(k or "unknown"): int(v) for k, v in cur.fetchall()}
    finally:
        conn.close()

    records = _analytics_records(None if all_time else days)
    cohort_users = {row["user_hash"] for row in records}
    cohort_safe = len(cohort_users) >= threshold

    symptoms = Counter(); symptom_users = defaultdict(set)
    severities = Counter(); severity_users = defaultdict(set)
    durations = Counter(); duration_users = defaultdict(set)
    ages = Counter(); age_users = defaultdict(set)
    genders = Counter(); gender_users = defaultdict(set)
    risks = Counter(); risk_users = defaultdict(set)
    medications = Counter(); medication_users = defaultdict(set)
    symptom_age_users = defaultdict(set); severity_month_users = defaultdict(set)
    medication_age_users = defaultdict(set); medication_month_users = defaultdict(set)
    for row in records:
        user = row["user_hash"]; age = row["age_group"]; month_key = row["timestamp"][:7] or "Unknown"
        ages[age] += 1; age_users[age].add(user)
        genders[row["gender"]] += 1; gender_users[row["gender"]].add(user)
        risks[row["risk"]] += 1; risk_users[row["risk"]].add(user)
        severities[row["severity_band"]] += 1; severity_users[row["severity_band"]].add(user)
        durations[row["duration"]] += 1; duration_users[row["duration"]].add(user)
        for symptom in set(row["symptoms"]):
            symptoms[symptom] += 1; symptom_users[symptom].add(user)
            symptom_age_users[(age, symptom)].add(user)
        for medication in set(row["medications"]):
            medications[medication] += 1; medication_users[medication].add(user)
            medication_age_users[(age, medication)].add(user)
            medication_month_users[(month_key, medication)].add(user)
        severity_month_users[(month_key, row["severity_band"])].add(user)

    safe_symptoms = _safe_rows(symptoms, symptom_users, threshold)
    safe_meds = _safe_rows(medications, medication_users, threshold)
    total_med_reports = sum(medications.values())
    medication_rows = []
    for item in safe_meds:
        medication = item["label"]
        ages_for_med = {
            age: len(users) for (age, name), users in medication_age_users.items()
            if name == medication and len(users) >= threshold
        }
        trends = [
            {"month": month_key, "count": len(users)}
            for (month_key, name), users in sorted(medication_month_users.items())
            if name == medication and len(users) >= threshold
        ]
        medication_rows.append({
            **item,
            "percentage": round(item["count"] * 100 / total_med_reports, 1) if total_med_reports else 0,
            "age_group_distribution": ages_for_med,
            "usage_trends": trends,
        })

    age_medication = []
    for age in ("Under 18", "18–25", "26–35", "36–45", "46–55", "56+"):
        choices = [
            (len(users), medication) for (group, medication), users in medication_age_users.items()
            if group == age and len(users) >= threshold
        ]
        if choices:
            count_value, name = max(choices)
            age_medication.append({"age_group": age, "medication": name, "distinct_users": count_value})

    heatmap_symptoms = [row["label"] for row in safe_symptoms[:8]]
    heatmap_ages = ["Under 18", "18–25", "26–35", "36–45", "46–55", "56+"]
    symptom_heatmap = [
        {
            "age_group": age,
            "values": [
                len(symptom_age_users[(age, symptom)])
                if len(symptom_age_users[(age, symptom)]) >= threshold else None
                for symptom in heatmap_symptoms
            ],
        }
        for age in heatmap_ages
    ]
    severity_months = sorted({key[0] for key in severity_month_users})[-12:]
    severity_heatmap = [
        {
            "month": month_key,
            "values": [
                len(severity_month_users[(month_key, band)])
                if len(severity_month_users[(month_key, band)]) >= threshold else None
                for band in ("1–3", "4–6", "7–10")
            ],
        }
        for month_key in severity_months
    ]

    health = {
        "sufficient_data": cohort_safe,
        "eligible_records": len(records), "eligible_users": len(cohort_users),
        "privacy_threshold": threshold,
        "most_reported_symptoms": safe_symptoms if cohort_safe else [],
        "severity_distribution": _safe_rows(severities, severity_users, threshold) if cohort_safe else [],
        "duration_distribution": _safe_rows(durations, duration_users, threshold) if cohort_safe else [],
        "age_groups": _safe_rows(ages, age_users, threshold) if cohort_safe else [],
        "gender_distribution": _safe_rows(genders, gender_users, threshold) if cohort_safe else [],
        "risk_distribution": _safe_rows(risks, risk_users, threshold) if cohort_safe else [],
        "heatmap": {"symptoms": heatmap_symptoms, "rows": symptom_heatmap} if cohort_safe else {"symptoms": [], "rows": []},
        "severity_by_month": {"bands": ["1–3", "4–6", "7–10"], "rows": severity_heatmap} if cohort_safe else {"bands": [], "rows": []},
    }
    medication = {
        "sufficient_data": bool(medication_rows), "privacy_threshold": threshold,
        "total_reported_mentions": total_med_reports if cohort_safe else None,
        "most_used": medication_rows if cohort_safe else [],
        "by_age_group": age_medication if cohort_safe else [],
        "disclaimer": "Descriptive user-reported patterns only; not a treatment recommendation.",
    }
    return {
        "days": "all" if all_time else days,
        "overview": {
            "total_users": total_users, "total_symptom_analyses": total_analyses,
            "total_assistant_conversations": assistant_conversations,
            "total_medication_reminders": web_reminders + bot_reminders,
            "total_health_reports": report_count,
            "today_activity": activity_today, "weekly_activity": activity_week,
            "monthly_activity": activity_month,
            "reminder_breakdown": {"web": web_reminders, "bot": bot_reminders},
            "assistant_count_source": "assistant_use operational events",
            "report_count_source": "report_generated operational events",
        },
        "users": {
            "total": total_users, "new": new_users, "active": active_users,
            "analyses": total_analyses, "languages": languages, "devices": devices,
            "age_groups": health["age_groups"], "privacy_threshold": threshold,
        },
        "health": health,
        "medications": medication,
    }


def model_card() -> dict:
    """Expose only metrics and identifiers persisted by the actual trained model."""
    model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ml_model.json")
    try:
        with open(model_path, "rb") as handle:
            fingerprint = hashlib.sha256(handle.read()).hexdigest()[:12]
    except OSError:
        fingerprint = None
    meta = dict(ml_diagnosis.model_info() or {})
    metrics = {
        "accuracy": meta.get("test_accuracy"),
        "precision": meta.get("precision"),
        "recall": meta.get("recall"),
        "f1_score": meta.get("f1_score"),
    }
    unavailable = [name for name, value in metrics.items() if value is None]
    return {
        "available": bool(meta), "algorithm": meta.get("algorithm"),
        "model_version": ("sha256:" + fingerprint) if fingerprint else None,
        "metrics": metrics, "unavailable_metrics": unavailable,
        "n_train_samples": meta.get("n_train_samples"),
        "n_test_samples": meta.get("n_test_samples"),
        "n_classes": meta.get("n_classes"), "n_features": meta.get("n_features"),
        "used_for_primary_user_result": False,
        "note": "Stored test metrics are shown as-is. Missing metrics are not estimated.",
    }


def explainable_ai() -> dict:
    """Return a real global coefficient-spread view for the persisted BernoulliNB model."""
    rows = []
    for index, feature in enumerate(ml_diagnosis.VOCAB):
        coefficients = [float(class_values[index]) for class_values in ml_diagnosis.FEATURE_LOG_PROB]
        if not coefficients:
            continue
        top_index = max(range(len(coefficients)), key=coefficients.__getitem__)
        rows.append({
            "feature": feature,
            "coefficient_spread": round(max(coefficients) - min(coefficients), 6),
            "highest_class": ml_diagnosis.CLASSES[top_index],
            "highest_class_name_en": ml_diagnosis.CLASS_NAMES[ml_diagnosis.CLASSES[top_index]]["en"],
            "highest_class_name_ar": ml_diagnosis.CLASS_NAMES[ml_diagnosis.CLASSES[top_index]]["ar"],
        })
    rows.sort(key=lambda item: item["coefficient_spread"], reverse=True)
    return {
        "available": bool(rows), "method": "BernoulliNB learned log-probability coefficient spread",
        "features": rows,
        "model": model_card(),
        "used_for_primary_user_result": False,
        "note": "This is calculated from the persisted model parameters; it is not SHAP and is not fabricated feature importance.",
    }


def _anonymous_id(value) -> str:
    configured = os.environ.get("ADMIN_EXPORT_PSEUDONYM_SECRET") or os.environ.get("WEB_SECRET")
    secret = configured.encode() if configured else _EPHEMERAL_EXPORT_SECRET
    return "U-" + hmac.new(secret, str(value).encode(), hashlib.sha256).hexdigest()[:16].upper()


def _excel_value(value):
    """Prevent spreadsheet formula injection while preserving readable values."""
    if value is None:
        return ""
    if isinstance(value, (int, float, bool, datetime)):
        return value
    text = str(value)
    if text[:1] in {"=", "+", "-", "@"}:
        return "'" + text
    return text



def _analysis_result_text(value, limit: int = 4000) -> str:
    """Return a readable bounded string for Admin research-result display."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()[:limit]
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                label = item.get("name_en") or item.get("name_ar") or item.get("name") or item.get("title") or item.get("label") or item.get("message") or item.get("tip") or item.get("text")
                if label:
                    parts.append(str(label))
            elif item not in (None, ""):
                parts.append(str(item))
        return "; ".join(parts)[:limit]
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)[:limit]
    return str(value)[:limit]


def admin_analysis_results(query: str = "", risk: str = "", lang: str = "", page: int = 1, per_page: int = 50) -> dict:
    """Return de-identified saved analysis results for the Admin research view.

    Only separately research-consented records are included. Direct identifiers, chat text,
    raw notes/allergies, exact location, and free-text feedback are deliberately
    excluded. Result details remain descriptive/non-diagnostic research data.
    """
    platform_v2.init_schema(); privacy_features.init_schema(); db.init_db()
    try:
        page = max(1, int(page))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = max(10, min(100, int(per_page)))
    except (TypeError, ValueError):
        per_page = 50
    query_cf = str(query or "").strip().casefold()[:160]
    risk_key = str(risk or "").strip().casefold()
    lang_key = str(lang or "").strip().casefold()
    risk_aliases = {
        "high": "Urgent", "urgent": "Urgent", "emergency": "Urgent",
        "medium": "Needs Medical Review", "review": "Needs Medical Review", "needs medical review": "Needs Medical Review",
        "low": "Low Risk", "normal": "Low Risk", "low risk": "Low Risk",
        "unknown": "Unknown",
    }
    risk_filter = risk_aliases.get(risk_key, "")
    if lang_key not in {"", "ar", "en"}:
        lang_key = ""

    def parse_result(value):
        if isinstance(value, dict):
            return value
        if not value:
            return {}
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (TypeError, ValueError, OverflowError):
            logging.getLogger(__name__).debug("Handled exception in parse_result; fallback applied (handler 474)")
            return {}

    def source_rows(result):
        out=[]
        for src in result.get("medical_sources") or []:
            if isinstance(src, dict):
                name = src.get("name") or src.get("source_name") or src.get("title") or src.get("organization") or src.get("url") or "Source"
                url = src.get("url") or src.get("official_url") or src.get("source_url") or ""
                out.append({"name": str(name)[:240], "url": str(url)[:1000]})
            elif src:
                out.append({"name": str(src)[:240], "url": ""})
        return out[:20]

    def recommendation_rows(result):
        out=[]
        for rec in result.get("recommendations") or []:
            if not isinstance(rec, dict):
                continue
            out.append({
                "title": str(rec.get("title") or "")[:300],
                "tip": str(rec.get("tip") or rec.get("text") or "")[:2500],
                "source": str(rec.get("source") or "")[:300],
                "url": str(rec.get("url") or rec.get("source_url") or "")[:1000],
            })
        return out[:12]

    conn=db._conn(); cur=conn.cursor()
    try:
        cur.execute(
            "SELECT r.id,r.user_hash,r.timestamp,r.lang,r.age,r.gender,r.symptoms,r.conditions,r.medications,"
            "r.duration,r.severity,r.urgency,r.research_study_version,r.research_app_version,res.data "
            "FROM records r LEFT JOIN results res ON res.record_id=r.id AND res.user_hash=r.user_hash "
            "WHERE COALESCE(r.research_eligible,0)=1 AND r.age IS NOT NULL AND r.age>=18 ORDER BY r.timestamp DESC,r.id DESC"
        )
        raw_rows=cur.fetchall()
    finally:
        conn.close()

    records=[]
    risk_counts=Counter(); lang_counts=Counter(); with_output=0
    for row in raw_rows:
        rid,user_hash,timestamp,row_lang,age,gender,symptoms_raw,conditions_raw,medications_raw,duration,severity,urgency,study_version,app_version,result_raw=row
        result=parse_result(result_raw)
        h=str(user_hash); risk_label=_risk(urgency)
        risk_counts[risk_label]+=1; lang_counts[str(row_lang or "unknown")]+=1
        if result: with_output+=1
        symptoms=_split_items(symptoms_raw)
        raw_id=_anonymous_id(f"analysis:{h}:{rid}")
        item={
            "analysis_id":"A-"+raw_id[2:],
            "participant_id":_anonymous_id("subject:"+h),
            "timestamp":str(timestamp or ""),
            "date":str(timestamp or "")[:10],
            "lang":str(row_lang or "unknown"),
            "age_group":_age_group(age),
            "gender":_gender(gender),
            "symptoms":symptoms,
            "symptom_count":len(symptoms),
            "duration":str(duration or ""),
            "severity":severity if severity is not None else "",
            "risk":risk_label,
            "research_study_version":str(study_version or "UNFROZEN")[:80],
            "research_app_version":str(app_version or "")[:80],
            "reported_conditions":str(conditions_raw or "")[:2000],
            "reported_medications":str(medications_raw or "")[:2000],
            "has_saved_output":bool(result),
            "assessment_status":str(result.get("assessment_status") or "")[:120],
            "confidence":str(result.get("confidence") or "")[:80],
            "emergency":bool(result.get("emergency", False)),
            "risk_label":str(result.get("risk_label") or "")[:300],
            "possible_conditions":_analysis_result_text(result.get("possible_conditions"), 5000),
            "why_result":_analysis_result_text(result.get("why_result"), 5000),
            "danger_signs":_analysis_result_text(result.get("danger_signs"), 5000),
            "when_to_seek_care":_analysis_result_text(result.get("when_to_seek_care"), 5000),
            "home_care":_analysis_result_text(result.get("home_care"), 5000),
            "medication_guidance":_analysis_result_text(result.get("medication_guidance"), 4000),
            "questions_for_doctor":_analysis_result_text(result.get("questions_for_doctor"), 5000),
            "knowledge_matches":_analysis_result_text(result.get("knowledge_matches"), 4000),
            "risk_reasons":_analysis_result_text(result.get("risk_reasons"), 4000),
            "needed_information":_analysis_result_text(result.get("needed_information"), 4000),
            "medical_sources":source_rows(result),
            "recommendations":recommendation_rows(result),
            "data_quality":result.get("data_quality") if isinstance(result.get("data_quality"), dict) else {},
            "knowledge_last_updated":str(result.get("knowledge_last_updated") or "")[:100],
        }
        search_blob=" ".join([
            item["analysis_id"], item["participant_id"], " ".join(symptoms), item["possible_conditions"],
            item["knowledge_matches"], item["risk_label"], item["reported_conditions"], item["reported_medications"],
        ]).casefold()
        if query_cf and query_cf not in search_blob:
            continue
        if risk_filter and item["risk"] != risk_filter:
            continue
        if lang_key and item["lang"].casefold() != lang_key:
            continue
        records.append(item)

    total_filtered=len(records); start=(page-1)*per_page; end=start+per_page
    pages=max(1, (total_filtered + per_page - 1)//per_page)
    if page>pages:
        page=pages; start=(page-1)*per_page; end=start+per_page
    return {
        "records":records[start:end],
        "page":page,"per_page":per_page,"pages":pages,"total_filtered":total_filtered,
        "total_eligible":len(raw_rows),"with_saved_output":with_output,
        "risk_counts":dict(risk_counts),"language_counts":dict(lang_counts),
        "privacy":"research_eligible_deidentified",
        "legacy_privacy_label":"analytics_eligible_deidentified",
    }

def export_admin_workbook(dataset_scope: str = "official") -> io.BytesIO:
    """Create a concise, research-ready workbook from separately research-consented data.

    The workbook is intentionally limited to four sheets needed for a scientific
    study: study overview, de-identified participants, symptom analyses with the
    saved system output, and a research data dictionary. Direct identifiers,
    raw chat content, exact location, raw notes/allergies, and free-text feedback comments
    are excluded.
    """
    from openpyxl import Workbook
    from openpyxl.comments import Comment
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    platform_v2.init_schema(); privacy_features.init_schema()
    dataset_scope = "pilot" if str(dataset_scope or "").strip().lower() == "pilot" else "official"
    study_state = research_study.status()
    frozen_study = str(study_state.get("study_version") or "") if study_state.get("frozen") else ""
    frozen_app = str(study_state.get("app_version") or "") if study_state.get("frozen") else ""
    freeze_integrity_ok = bool(study_state.get("frozen") and study_state.get("integrity_ok"))
    analytics = complete_analytics("all")
    threshold = analytics["health"]["privacy_threshold"]
    generated_at = _now().astimezone().strftime("%Y-%m-%d %H:%M %Z")

    def parse_json(value):
        if not value:
            return {}
        if isinstance(value, dict):
            return value
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (TypeError, ValueError, OverflowError):
            logging.getLogger(__name__).debug("Handled exception in parse_json; fallback applied (handler 617)")
            return {}

    def text_value(value):
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (list, tuple, set)):
            parts = []
            for item in value:
                if isinstance(item, dict):
                    label = item.get("name") or item.get("name_ar") or item.get("name_en") or item.get("title") or item.get("tip") or item.get("label")
                    if label:
                        parts.append(str(label).strip())
                elif item not in (None, ""):
                    parts.append(str(item).strip())
            return "; ".join(x for x in parts if x)
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False)
        return str(value).strip()

    def match_name(match, lang="ar"):
        if not isinstance(match, dict):
            return ""
        if str(lang or "").lower() == "en":
            return str(match.get("name_en") or match.get("name") or match.get("name_ar") or "").strip()
        return str(match.get("name_ar") or match.get("name") or match.get("name_en") or "").strip()

    def next_step_category(risk):
        return {
            "Urgent": "Emergency / Urgent care",
            "Needs Medical Review": "Medical review",
            "Needs Follow-up": "Medical follow-up",
            "Low Risk": "Self-care / monitor",
        }.get(str(risk or ""), "Unclassified")

    def quality_score(result):
        quality = result.get("data_quality") if isinstance(result, dict) else None
        if isinstance(quality, dict):
            score = quality.get("score")
            try:
                return int(score) if score is not None else ""
            except (TypeError, ValueError, OverflowError):
                logging.getLogger(__name__).debug("Handled exception in quality_score; fallback applied (handler 660)")
                return ""
        return ""

    def subject_id(user_hash: str) -> str:
        return _anonymous_id("subject:" + str(user_hash))

    def analysis_id(user_hash: str, record_id) -> str:
        raw = _anonymous_id(f"analysis:{user_hash}:{record_id}")
        return "A-" + raw[2:]

    conn = db._conn(); cur = conn.cursor()
    try:
        base_sql = (
            "SELECT r.id,r.user_hash,r.timestamp,r.lang,r.age,r.gender,r.symptoms,r.conditions,r.medications,"
            "r.duration,r.severity,r.urgency,r.research_study_version,r.research_app_version,res.data "
            "FROM records r LEFT JOIN results res ON res.record_id=r.id AND res.user_hash=r.user_hash "
            "WHERE COALESCE(r.research_eligible,0)=1 AND r.age IS NOT NULL AND r.age>=18"
        )
        cur.execute("SELECT COUNT(*) FROM records WHERE COALESCE(research_eligible,0)=1 AND age IS NOT NULL AND age>=18")
        all_research_eligible_count = int((cur.fetchone() or (0,))[0] or 0)
        if dataset_scope == "official":
            # Official research exports are intentionally empty until a frozen,
            # integrity-matching study version exists.  This prevents Pilot/
            # UNFROZEN rows from being mixed into the final study by accident.
            if freeze_integrity_ok:
                cur.execute(
                    base_sql + f" AND r.research_study_version={PH} AND r.research_app_version={PH} ORDER BY r.timestamp,r.id",
                    (frozen_study, frozen_app),
                )
                eligible_rows = cur.fetchall()
            else:
                eligible_rows = []
        else:
            # Pilot export is deliberately separate from the official workbook.
            # It contains eligible rows that do not match the active frozen
            # study/app pair (or all eligible rows when no valid freeze exists).
            if freeze_integrity_ok:
                cur.execute(
                    base_sql + f" AND NOT (COALESCE(r.research_study_version,'')={PH} AND COALESCE(r.research_app_version,'')={PH}) ORDER BY r.timestamp,r.id",
                    (frozen_study, frozen_app),
                )
                eligible_rows = cur.fetchall()
            else:
                cur.execute(base_sql + " ORDER BY r.timestamp,r.id")
                eligible_rows = cur.fetchall()

        followup_rows = []
        if _table_exists(cur, "symptom_followups"):
            cur.execute("SELECT user_hash,record_id,timestamp,outcome FROM symptom_followups ORDER BY timestamp")
            followup_rows = cur.fetchall()

        feedback_rows = []
        if _table_exists(cur, "feedback"):
            cur.execute("SELECT user_hash,record_id,rating,timestamp FROM feedback ORDER BY timestamp")
            feedback_rows = cur.fetchall()
    finally:
        conn.close()

    allowed_hashes = {str(row[1]) for row in eligible_rows}

    # One compact row per participant. No account type, registration date,
    # platform, login date, email, name, or other administrative fields.
    participant_state = {}
    for row in eligible_rows:
        _, user_hash, _ts, lang, age, gender, *_ = row
        h = str(user_hash)
        item = participant_state.setdefault(h, {
            "age_group": _age_group(age),
            "gender": _gender(gender),
            "language": str(lang or "unknown"),
        })
        if item["age_group"] in {"Unknown", "Not available"}:
            item["age_group"] = _age_group(age)
        if item["gender"] in {"Unknown", "Not available"}:
            item["gender"] = _gender(gender)
        if item["language"] in {"unknown", "Not available"}:
            item["language"] = str(lang or "unknown")

    participants_export = [
        [subject_id(h), info["age_group"], info["gender"], info["language"]]
        for h, info in sorted(participant_state.items(), key=lambda x: subject_id(x[0]))
    ]

    # Latest follow-up and rating are merged into the analysis table instead of
    # being exported as separate administrative sheets.
    followup_by_analysis = {}
    for user_hash, record_id, timestamp, outcome in followup_rows:
        h = str(user_hash)
        if h in allowed_hashes:
            followup_by_analysis[(h, int(record_id))] = (str(timestamp or ""), str(outcome or ""))

    rating_by_analysis = {}
    for user_hash, record_id, rating, timestamp in feedback_rows:
        h = str(user_hash)
        if h in allowed_hashes:
            rating_by_analysis[(h, int(record_id))] = (str(timestamp or ""), str(rating or ""))

    analyses_export = []
    symptom_counter = Counter(); risk_counter = Counter(); language_counter = Counter()
    confidence_counter = Counter(); status_counter = Counter(); next_step_counter = Counter()
    date_values = []; output_available = 0; followup_available = 0; rating_available = 0
    source_total = 0; knowledge_match_total = 0; emergency_total = 0
    quality_scores = []
    missing_counts = Counter()

    for row in eligible_rows:
        rid, user_hash, timestamp, lang, age, gender, symptoms_raw, conditions_raw, medications_raw, duration_raw, severity, urgency, study_version, app_version, result_raw = row
        h = str(user_hash); sid = subject_id(h); aid = analysis_id(h, rid)
        symptoms = _split_items(symptoms_raw)
        symptom_counter.update(set(symptoms))
        risk = _risk(urgency); risk_counter[risk] += 1
        language_counter[str(lang or "unknown")] += 1
        date_str = str(timestamp or "")[:10]
        if date_str:
            date_values.append(date_str)

        if not symptoms: missing_counts["symptoms"] += 1
        if not str(duration_raw or "").strip(): missing_counts["duration"] += 1
        if severity in (None, ""): missing_counts["severity"] += 1

        result = parse_json(result_raw)
        if result:
            output_available += 1

        recommendations = []
        seek = text_value(result.get("when_to_seek_care"))
        if seek:
            recommendations.append(seek)
        for rec in result.get("recommendations") or []:
            if isinstance(rec, dict):
                title = text_value(rec.get("title"))
                tip = text_value(rec.get("tip"))
                line = f"{title}: {tip}" if title and tip else (tip or title)
                if line:
                    recommendations.append(line)
            elif rec:
                recommendations.append(text_value(rec))
        recommendation_text = " | ".join(dict.fromkeys(x for x in recommendations if x))

        sources = []
        for src in result.get("medical_sources") or []:
            if isinstance(src, dict):
                label = src.get("name") or src.get("source_name") or src.get("title") or src.get("url")
                if label:
                    sources.append(str(label).strip())
            elif src:
                sources.append(str(src).strip())
        # Recommendation-level source names are also useful for research transparency.
        for rec in result.get("recommendations") or []:
            if isinstance(rec, dict) and rec.get("source"):
                sources.append(str(rec.get("source")).strip())

        followup = followup_by_analysis.get((h, int(rid)), ("", ""))[1]
        rating = rating_by_analysis.get((h, int(rid)), ("", ""))[1]
        if followup:
            followup_available += 1
        if rating:
            rating_available += 1
        emergency_flag = bool(result.get("emergency", False)) or str(result.get("urgency", "")).lower() == "high"
        if emergency_flag:
            emergency_total += 1

        confidence = str(result.get("confidence") or "unknown").strip().lower()
        assessment_status = str(result.get("assessment_status") or "unknown").strip().lower()
        confidence_counter[confidence] += 1
        status_counter[assessment_status] += 1
        step_category = next_step_category(risk)
        next_step_counter[step_category] += 1

        matches = result.get("knowledge_matches") if isinstance(result.get("knowledge_matches"), list) else []
        match_names = [match_name(m, lang) for m in matches if match_name(m, lang)]
        top_condition = match_names[0] if match_names else ""
        match_count = len(matches)
        knowledge_match_total += match_count

        danger_signs = text_value(result.get("danger_signs"))
        risk_reasons = text_value(result.get("risk_reasons"))
        source_names = list(dict.fromkeys(x for x in sources if x))
        source_count = len(source_names)
        source_total += source_count
        qscore = quality_score(result)
        if isinstance(qscore, int):
            quality_scores.append(qscore)

        analyses_export.append([
            aid,
            sid,
            date_str,
            str(study_version or "UNFROZEN"),
            str(app_version or ""),
            str(lang or "unknown"),
            ", ".join(symptoms),
            len(symptoms),
            str(duration_raw or ""),
            severity if severity is not None else "",
            risk,
            step_category,
            emergency_flag,
            confidence,
            assessment_status,
            qscore,
            str(conditions_raw or ""),
            top_condition,
            match_count,
            text_value(result.get("possible_conditions")),
            danger_signs or risk_reasons,
            recommendation_text,
            followup,
            rating,
            source_count,
            "; ".join(source_names),
            bool(result),
        ])

    n_records = len(eligible_rows)
    n_subjects = len(participant_state)
    completeness = lambda missing: round((n_records - missing) * 100 / n_records, 1) if n_records else 0.0

    participant_age_counter = Counter(info["age_group"] for info in participant_state.values())
    participant_gender_counter = Counter(info["gender"] for info in participant_state.values())

    mean_quality = round(sum(quality_scores) / len(quality_scores), 1) if quality_scores else ""
    mean_sources = round(source_total / n_records, 2) if n_records else 0.0
    mean_matches = round(knowledge_match_total / n_records, 2) if n_records else 0.0

    research_summary = [
        ["Generated at", generated_at],
        ["Dataset scope", "Official frozen-study dataset" if dataset_scope == "official" else "Pilot / non-frozen dataset"],
        ["Freeze integrity valid", freeze_integrity_ok],
        ["Frozen study version", frozen_study],
        ["Frozen app version", frozen_app],
        ["All research-eligible rows before study-version filtering", all_research_eligible_count],
        ["Rows excluded from this workbook by study-version scope", max(0, all_research_eligible_count - len(eligible_rows))],
        ["App version", release_candidate.APP_VERSION],
        ["Active research study version", (research_study.status().get("study_version") or "UNFROZEN")],
        ["Research version frozen", bool(research_study.status().get("frozen"))],
        ["Research algorithm integrity", research_study.status().get("integrity_ok")],
        ["Research eligibility criterion", "Explicit scientific-research consent + age 18 or older; record marked research_eligible=1"],
        ["Eligible participants", n_subjects],
        ["Eligible symptom analyses", n_records],
        ["First eligible analysis date", min(date_values) if date_values else ""],
        ["Last eligible analysis date", max(date_values) if date_values else ""],
        ["Analyses with saved system output", output_available],
        ["Low-risk analyses", risk_counter.get("Low Risk", 0)],
        ["Needs-review analyses", risk_counter.get("Needs Medical Review", 0) + risk_counter.get("Needs Follow-up", 0)],
        ["Urgent analyses", risk_counter.get("Urgent", 0)],
        ["Arabic analyses", language_counter.get("ar", 0)],
        ["English analyses", language_counter.get("en", 0)],
        ["Symptoms completeness (%)", completeness(missing_counts["symptoms"])],
        ["Duration completeness (%)", completeness(missing_counts["duration"])],
        ["Severity completeness (%)", completeness(missing_counts["severity"])],
        ["Analyses with follow-up outcome", followup_available],
        ["Analyses with rating", rating_available],
        ["Emergency flag rate (%)", round(100.0 * emergency_total / n_records, 1) if n_records else 0.0],
        ["Mean data-quality score", mean_quality],
        ["Mean knowledge matches per analysis", mean_matches],
        ["Mean medical sources per analysis", mean_sources],
        ["High-confidence analyses", confidence_counter.get("high", 0)],
        ["Medium-confidence analyses", confidence_counter.get("medium", 0)],
        ["Low-confidence analyses", confidence_counter.get("low", 0)],
        ["Assessment status — sufficient", status_counter.get("sufficient", 0)],
        ["Assessment status — low confidence", status_counter.get("low_confidence", 0)],
        ["Assessment status — insufficient", status_counter.get("insufficient", 0)],
    ]

    for group, count in sorted(participant_age_counter.items()):
        research_summary.append([f"Participants — age group {group}", count])
    for group, count in sorted(participant_gender_counter.items()):
        research_summary.append([f"Participants — gender {group}", count])
    for category, count in sorted(next_step_counter.items()):
        research_summary.append([f"Next-step category — {category}", count])
    for rank, (symptom, count) in enumerate(symptom_counter.most_common(10), 1):
        research_summary.append([f"Top symptom #{rank}: {symptom}", count])

    data_dictionary = [
        ["Participants", "Anonymous User ID", "معرّف المشارك المجهول", "Stable pseudonymous participant key used to link analyses without exporting identity.", "Not a name, email, or account identifier."],
        ["Participants", "Age Group", "الفئة العمرية", "Grouped age at the time of analysis.", "Grouped to reduce identifiability."],
        ["Participants", "Gender", "الجنس", "Normalized self-reported gender.", "May be Unknown or unavailable."],
        ["Participants", "Primary Language", "اللغة الأساسية", "Primary language observed in eligible analyses.", "Arabic or English when available."],
        ["Symptom Analyses", "Research Analysis ID", "معرّف التحليل", "Pseudonymous key for one eligible symptom analysis.", "Links the row to the participant without exposing identity."],
        ["Symptom Analyses", "Analysis Date", "تاريخ التحليل", "Calendar date of the eligible analysis.", "Time-of-day is omitted to reduce identifiability."],
        ["Symptom Analyses", "Research Study Version", "إصدار الدراسة", "Frozen research-study version associated with the analysis at collection time.", "UNFROZEN/UNFROZEN-CHANGED means the analysis was collected without a matching frozen research version."],
        ["Symptom Analyses", "App Version", "إصدار التطبيق", "Application release associated with the research-eligible analysis.", "Use with Research Study Version to reproduce the evaluated system."],
        ["Symptom Analyses", "Language", "اللغة", "Language used for the analysis.", "Descriptive variable."],
        ["Symptom Analyses", "Symptoms", "الأعراض", "User-reported symptoms included in the analysis.", "Self-reported; not a diagnosis."],
        ["Symptom Analyses", "Duration", "المدة", "User-reported duration of symptoms.", "May be missing or approximate."],
        ["Symptom Analyses", "Severity", "الشدة", "User-reported symptom severity.", "Interpret using the app scale used during data collection."],
        ["Symptom Analyses", "Risk Level", "مستوى الخطورة", "Safety/triage category generated by the symptom flow.", "Not a diagnosis or disease probability."],
        ["Symptom Analyses", "Emergency Flag", "علامة الطوارئ", "Whether emergency/red-flag logic was triggered.", "Safety flag only; not a diagnosis."],
        ["Symptom Analyses", "Reported Conditions", "الحالات الصحية المبلغ عنها", "User-reported medical context when provided.", "Self-reported and may be incomplete."],
        ["Symptom Analyses", "Possible Conditions / Result Summary", "الاحتمالات / ملخص النتيجة", "Saved non-diagnostic educational result from the system.", "Must not be interpreted as confirmed diagnosis."],
        ["Symptom Analyses", "Recommendation / Next Step", "التوصية / الخطوة التالية", "Saved care guidance and next-step text shown to the user.", "Educational guidance, not medical treatment."],
        ["Symptom Analyses", "Follow-up Outcome", "نتيجة المتابعة", "Latest saved follow-up outcome linked to the analysis, when available.", "User-reported outcome."],
        ["Symptom Analyses", "Rating", "التقييم", "Latest saved numeric/user rating linked to the analysis, when available.", "Free-text feedback is excluded."],
        ["Symptom Analyses", "Symptom Count", "عدد الأعراض", "Number of symptoms included in the analysis.", "Useful for descriptive analysis; does not measure clinical complexity."],
        ["Symptom Analyses", "Next Step Category", "فئة الخطوة التالية", "Standardized action category derived from the saved risk level.", "Created for analysis convenience; retain the original recommendation text for context."],
        ["Symptom Analyses", "Confidence", "مستوى الثقة", "System confidence label saved with the result.", "Not a diagnostic probability or accuracy estimate."],
        ["Symptom Analyses", "Assessment Status", "حالة اكتمال التقييم", "Whether the symptom flow had sufficient information or was limited/low-confidence.", "Interpret together with data-quality score."],
        ["Symptom Analyses", "Data Quality Score", "درجة اكتمال البيانات", "0-100 score measuring completeness of information supplied to the analysis flow.", "This is not clinical accuracy or disease probability."],
        ["Symptom Analyses", "Top Possible Condition", "أول احتمال ظاهر", "First source-grounded condition name in the saved knowledge matches, when displayable.", "Non-diagnostic educational output."],
        ["Symptom Analyses", "Knowledge Match Count", "عدد مطابقات قاعدة المعرفة", "Number of source-grounded knowledge-base matches saved with the analysis.", "May be zero when confidence gating suppresses condition names."],
        ["Symptom Analyses", "Danger Signs / Risk Reasons", "علامات الخطر / أسباب الخطورة", "Saved danger-sign guidance or risk reasons associated with the result.", "Safety information; not a diagnosis."],
        ["Symptom Analyses", "Source Count", "عدد المصادر", "Number of distinct medical source labels attached to the result.", "A count of attached sources, not a source-quality score."],
        ["Symptom Analyses", "Result Available", "توفر النتيجة", "Whether a saved structured system result was available for the analysis.", "Useful for missing-data reporting."],
        ["Symptom Analyses", "Medical Sources", "المصادر الطبية", "Source names saved with the result or its recommendations.", "For transparency; verify source versions when citing in a paper."],
    ]

    wb = Workbook(); wb.remove(wb.active)
    wb.properties.title = "SymptoSense Research Export"
    wb.properties.subject = "Concise privacy-preserving research dataset"
    wb.properties.description = (
        "Four-sheet de-identified export from separately research-consented records, separated into official frozen-study or pilot scope. Excludes direct identifiers, raw chat content, exact location, raw notes/allergies, and free-text feedback comments."
    )

    navy = "163B5C"; pale = "EAF5FC"; gray = "607487"; line = "DCE8F0"
    header_fill = PatternFill("solid", fgColor=navy)
    title_fill = PatternFill("solid", fgColor=pale)
    thin = Side(style="thin", color=line)
    scope_note = (
        "Official dataset: only rows matching the active frozen study/app version are included."
        if dataset_scope == "official" else
        "Pilot dataset: rows not matching the active frozen study/app version are kept separate from official study results."
    )
    privacy_note = (
        f"{scope_note} Research consent + age 18+ are required. Aggregate dashboard threshold: {threshold} distinct users. "
        "Direct identifiers, raw chat content, exact location, raw notes/allergies, and free-text feedback comments are excluded."
    )

    def add_sheet(name, title, headers, values, note=None):
        ws = wb.create_sheet(name)
        end_col = max(1, len(headers))
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=end_col)
        ws.cell(1, 1, title)
        ws.cell(1, 1).font = Font(size=15, bold=True, color=navy)
        ws.cell(1, 1).fill = title_fill
        ws.cell(1, 1).alignment = Alignment(vertical="center")
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=end_col)
        ws.cell(2, 1, note or privacy_note)
        ws.cell(2, 1).font = Font(size=9, color=gray)
        ws.cell(2, 1).alignment = Alignment(wrap_text=True, vertical="top")
        header_row = 4
        for j, header in enumerate(headers, 1):
            cell = ws.cell(header_row, j, header)
            cell.font = Font(color="FFFFFF", bold=True)
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = Border(bottom=thin)
        for row_num, row in enumerate(values, header_row + 1):
            for col_num, value in enumerate(row, 1):
                cell = ws.cell(row_num, col_num, _excel_value(value))
                cell.alignment = Alignment(vertical="top", wrap_text=True)
                cell.border = Border(bottom=thin)
        ws.freeze_panes = f"A{header_row + 1}"
        ws.auto_filter.ref = f"A{header_row}:{get_column_letter(end_col)}{max(header_row, ws.max_row)}"
        ws.sheet_view.showGridLines = False
        ws["A4"].comment = Comment(note or privacy_note, "SymptoSense")
        for col in range(1, end_col + 1):
            vals = [str(ws.cell(r, col).value or "") for r in range(1, min(ws.max_row, 300) + 1)]
            width = min(44, max(12, max((len(v) for v in vals), default=10) + 2))
            ws.column_dimensions[get_column_letter(col)].width = width
        ws.row_dimensions[1].height = 25
        ws.row_dimensions[2].height = 34
        return ws

    add_sheet(
        "Study Overview",
        "SymptoSense — Scientific Study Overview",
        ["Metric", "Value"],
        research_summary,
        "A concise descriptive snapshot of the eligible study dataset. These values do not establish clinical effectiveness or diagnostic accuracy."
    )
    add_sheet(
        "Participants",
        "De-identified Research Participants",
        ["Anonymous User ID", "Age Group", "Gender", "Primary Language"],
        participants_export,
        "One row per eligible participant. Only the minimum demographic variables needed for research analysis are included."
    )
    add_sheet(
        "Symptom Analyses",
        "Scientific Symptom Analysis Dataset",
        [
            "Research Analysis ID", "Anonymous User ID", "Analysis Date", "Research Study Version", "App Version", "Language",
            "Symptoms", "Symptom Count", "Duration", "Severity", "Risk Level",
            "Next Step Category", "Emergency Flag", "Confidence", "Assessment Status",
            "Data Quality Score", "Reported Conditions", "Top Possible Condition",
            "Knowledge Match Count", "Possible Conditions / Result Summary",
            "Danger Signs / Risk Reasons", "Recommendation / Next Step",
            "Follow-up Outcome", "Rating", "Source Count", "Medical Sources", "Result Available"
        ],
        analyses_export,
        "One row per eligible symptom analysis. System outputs are non-diagnostic educational guidance and must not be treated as confirmed clinical diagnoses."
    )
    add_sheet(
        "Research Dictionary",
        "Research Data Dictionary",
        ["Sheet", "Field", "Arabic Label", "Definition", "Research Note / Limitation"],
        data_dictionary,
        "Variable definitions and interpretation notes for methodology, analysis, and reporting."
    )

    output = io.BytesIO(); wb.save(output); output.seek(0)
    return output
