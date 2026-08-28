"""Complete, privacy-preserving Admin analytics and export helpers.

The functions in this module only read real persisted data.  Health and
medication analytics use records that were marked analytics-eligible at
collection time, suppress small cohorts, and never return email addresses,
passwords, tokens, chat text, or raw health profiles.
"""
from __future__ import annotations

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


def export_admin_workbook() -> io.BytesIO:
    """Create the five requested sheets from current, consent-eligible data."""
    from openpyxl import Workbook
    from openpyxl.comments import Comment
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    platform_v2.init_schema(); privacy_features.init_schema()
    analytics = complete_analytics("all")
    threshold = analytics["health"]["privacy_threshold"]
    records = _analytics_records(None)
    conn = db._conn(); cur = conn.cursor()
    try:
        cur.execute("SELECT id,created_at FROM ss_users ORDER BY id")
        user_rows = cur.fetchall()
        cur.execute(
            f"SELECT user_id FROM ss_consent_state WHERE analytics_research=1 "
            f"AND consent_version={PH} AND privacy_policy_version={PH} AND user_id IS NOT NULL",
            (privacy_features.CONSENT_VERSION, privacy_features.PRIVACY_POLICY_VERSION),
        )
        consented_ids = {int(row[0]) for row in cur.fetchall()}
        latest_login = {}
        if _table_exists(cur, "ss_login_activity"):
            cur.execute("SELECT user_id,device_type,occurred_at FROM ss_login_activity WHERE success=1 AND user_id IS NOT NULL ORDER BY occurred_at")
            for user_id, device, timestamp in cur.fetchall():
                latest_login[int(user_id)] = (str(device or "Not available"), str(timestamp or ""))
        med_rows = []
        if _table_exists(cur, "med_plans"):
            cur.execute("SELECT user_hash,med_name,created,frequency,active FROM med_plans ORDER BY created")
            med_rows = cur.fetchall()
    finally:
        conn.close()

    record_by_hash = defaultdict(list)
    for row in records:
        record_by_hash[row["user_hash"]].append(row)
    allowed_account_hashes = {db._hash_user(f"account-{user_id}") for user_id in consented_ids}

    users_export = []
    for user_id, created_at in user_rows:
        account_hash = db._hash_user(f"account-{int(user_id)}")
        eligible = record_by_hash.get(account_hash, [])
        latest = eligible[-1] if eligible else None
        platform = latest_login.get(int(user_id), ("Not available", ""))[0]
        users_export.append([
            _anonymous_id(f"account:{user_id}"),
            (latest or {}).get("age_group", "Not available"),
            (latest or {}).get("gender", "Not available"),
            str(created_at or "")[:10],
            (latest or {}).get("lang", "Not available"),
            platform,
        ])

    analyses_export = []
    for row in records:
        analyses_export.append([
            _anonymous_id("record-owner:" + row["user_hash"]), row["timestamp"][:10],
            ", ".join(row["symptoms"]), row["duration_raw"], row["severity"], row["risk"],
            row["lang"], row["age_group"], row["gender"],
        ])

    medications_export = []
    for user_hash, medication, created, frequency, active in med_rows:
        if str(user_hash) not in allowed_account_hashes:
            continue
        medications_export.append([
            _anonymous_id("record-owner:" + str(user_hash)), medication, str(created or "")[:10],
            frequency or "Not available", "Active" if int(active or 0) else "Inactive",
        ])

    med_analytics_export = []
    for row in analytics["medications"]["most_used"]:
        med_analytics_export.append([
            row["label"], row["count"], row["percentage"],
            json.dumps(row["age_group_distribution"], ensure_ascii=False, sort_keys=True),
            json.dumps(row["usage_trends"], ensure_ascii=False),
        ])
    symptom_analytics_export = []
    severity_json = json.dumps(
        {item["label"]: item["count"] for item in analytics["health"]["severity_distribution"]},
        ensure_ascii=False, sort_keys=True,
    )
    age_json = json.dumps(
        {item["label"]: item["count"] for item in analytics["health"]["age_groups"]},
        ensure_ascii=False, sort_keys=True,
    )
    safe_symptoms = analytics["health"]["most_reported_symptoms"]
    symptom_total = sum(item["count"] for item in safe_symptoms)
    for row in safe_symptoms:
        symptom_analytics_export.append([
            row["label"], row["count"], round(row["count"] * 100 / symptom_total, 1) if symptom_total else 0,
            age_json, severity_json,
        ])

    wb = Workbook(); wb.remove(wb.active)
    wb.properties.title = "SymptoSense privacy-preserving Admin export"
    wb.properties.description = (
        "No emails, passwords, tokens, secrets, or chat content. Health rows are limited to analytics-eligible data."
    )
    header_fill = PatternFill("solid", fgColor="163B5C")
    privacy_note = (
        f"Privacy threshold: {threshold} distinct users for aggregate health/medication rows. "
        "Individual sheets use pseudonymous IDs and analytics-consented/eligible data only."
    )

    def add_sheet(name, headers, values):
        ws = wb.create_sheet(name)
        ws.append(headers)
        for row in values:
            ws.append([_excel_value(value) for value in row])
        for cell in ws[1]:
            cell.font = Font(color="FFFFFF", bold=True)
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws["A1"].comment = Comment(privacy_note, "SymptoSense")
        ws.freeze_panes = "A2"; ws.auto_filter.ref = ws.dimensions
        for column in range(1, len(headers) + 1):
            values_for_width = [str(ws.cell(row, column).value or "") for row in range(1, min(ws.max_row, 300) + 1)]
            width = min(48, max(12, max((len(value) for value in values_for_width), default=10) + 2))
            ws.column_dimensions[get_column_letter(column)].width = width
        for row in ws.iter_rows():
            for cell in row:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
        return ws

    add_sheet("Users", ["Anonymous User ID", "Age (grouped)", "Gender", "Registration Date", "Language", "Platform"], users_export)
    add_sheet("Symptom Analyses", ["Anonymous User ID", "Date", "Symptoms", "Duration", "Severity", "Risk Level", "Language", "Age Group", "Gender"], analyses_export)
    add_sheet("Medications", ["Anonymous User ID", "Medication", "Date", "Reminder Frequency", "Status"], medications_export)
    add_sheet("Medication Analytics", ["Medication", "Total Reports", "Percentage", "Age Group Distribution", "Usage Trends"], med_analytics_export)
    add_sheet("Symptom Analytics", ["Symptom", "Frequency", "Percentage", "Age Group", "Severity Distribution"], symptom_analytics_export)
    output = io.BytesIO(); wb.save(output); output.seek(0)
    return output
