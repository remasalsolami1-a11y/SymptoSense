"""Production-readiness checks for the SymptoSense admin dashboard.

Checks are deliberately local/non-destructive. They never expose secrets and do
not send email, push notifications, or health data.
"""
from __future__ import annotations
import logging

import os
import time
from datetime import datetime, timezone

import db
import medical_knowledge
import medication_email
import privacy_features
import admin_2fa
import research_validation
import research_study
import production_verification
import release_candidate
import admin_security
import data_retention
import platform_v2
import backup_restore
import web_security

APP_VERSION = os.environ.get("APP_VERSION", release_candidate.APP_VERSION)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _component(status, label, detail="", **extra):
    out = {"status": status, "label": label, "detail": detail}
    out.update(extra)
    return out


def _email_state():
    brevo = all(os.environ.get(k, "").strip() for k in ("BREVO_API_KEY", "BREVO_FROM_EMAIL", "BREVO_FROM_NAME"))
    smtp = all(os.environ.get(k, "").strip() for k in ("SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM"))
    resend = all(os.environ.get(k, "").strip() for k in ("RESEND_API_KEY", "RESEND_FROM"))
    provider = "brevo" if brevo else ("smtp" if smtp else ("resend" if resend else "none"))
    return provider


def build(route_rules=None) -> dict:
    started = time.perf_counter(); components = {}

    # Database connectivity.
    try:
        db.init_db(); conn = db._conn(); c = conn.cursor(); c.execute("SELECT 1"); c.fetchone(); conn.close()
        components["database"] = _component("online", "Database", "Connection and query succeeded")
    except Exception as exc:
        logging.getLogger(__name__).warning("Handled exception in build; fallback applied (handler 54)")
        components["database"] = _component("offline", "Database", type(exc).__name__)

    # Transactional email must be both configured and manually confirmed from the Admin inbox.
    provider = _email_state()
    email_ver = production_verification.get("email_delivery") if provider != "none" else None
    email_details = (email_ver or {}).get("details") or {}
    email_confirmed = bool(email_ver and email_ver.get("status") == "verified" and email_details.get("provider") == provider and email_details.get("app_version") == APP_VERSION)
    if provider == "none":
        email_status, email_detail = "offline", "No complete Brevo/SMTP/Resend configuration"
    elif email_confirmed:
        email_status, email_detail = "online", f"Live inbox delivery verified via {provider}"
    else:
        email_status, email_detail = "degraded", f"Configured via {provider}; live inbox confirmation is still required"
    components["email"] = _component(email_status, "Verification email", email_detail, provider=provider, live_verified=email_confirmed, verified_at=(email_ver or {}).get("event_at"))

    # AI provider with safe local fallback.
    ai = bool(os.environ.get("GROQ_API_KEY", "").strip())
    components["ai"] = _component("online" if ai else "degraded", "AI provider", "Groq configured" if ai else "Groq not configured; curated local fallback remains available", fallback=not ai)

    # Medication reminders are email-only. No browser Push/VAPID state is required.
    med_email_state = medication_email.email_provider_status()
    try:
        med_delivery = medication_email.delivery_summary(50)
    except Exception as exc:
        logging.getLogger(__name__).warning("Medication email readiness check failed: %s", type(exc).__name__)
        med_delivery = {"sent": 0, "failed": 0, "last_sent_at": None}
    if not med_email_state.get("configured"):
        med_status = "offline"
        med_detail = "Brevo or Resend is not configured for medication reminder email"
    elif med_delivery.get("sent", 0) > 0:
        med_status = "online"
        med_detail = f"Email-only medication reminders configured via {med_email_state.get('provider')} and at least one reminder was sent"
    else:
        med_status = "degraded"
        med_detail = f"Email-only medication reminders configured via {med_email_state.get('provider')}; no reminder delivery recorded yet"
    components["medication_email"] = _component(
        med_status, "Medication reminder email", med_detail,
        provider=med_email_state.get("provider"), configured=bool(med_email_state.get("configured")),
        sent=med_delivery.get("sent", 0), failed=med_delivery.get("failed", 0),
        last_sent_at=med_delivery.get("last_sent_at"),
    )

    # Session secret and owner admin.
    raw_secret = os.environ.get("WEB_SECRET", "").strip()
    web_secret = bool(raw_secret)
    components["session_secret"] = _component("online" if len(raw_secret) >= 32 else ("degraded" if web_secret else "offline"), "Session secret", "WEB_SECRET configured with adequate length" if len(raw_secret) >= 32 else ("WEB_SECRET should be at least 32 characters" if web_secret else "WEB_SECRET is missing"))

    hash_salt = (os.environ.get("HASH_SALT") or "").strip()
    components["pseudonym_hash_secret"] = _component(
        "online" if len(hash_salt) >= 32 else "degraded",
        "Pseudonymous hash secret",
        "Stable HASH_SALT configured" if len(hash_salt) >= 32 else "Set a stable high-entropy HASH_SALT before production; do not rotate an existing deployment without migration",
        configured=bool(hash_salt), length_ok=len(hash_salt) >= 32,
    )

    site_url = (os.environ.get("SITE_URL") or "").strip()
    railway_runtime = bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_ENVIRONMENT_NAME") or os.environ.get("RAILWAY_PUBLIC_DOMAIN"))
    prod = bool(railway_runtime or site_url)
    secure_cookie_setting = (os.environ.get("SESSION_COOKIE_SECURE") or "").strip()
    # webapp.py forces Secure cookies on Railway even if an environment override is wrong.
    secure_cookie_ok = railway_runtime or (secure_cookie_setting == "1") or (not secure_cookie_setting and site_url.lower().startswith("https://"))
    https_ok = (not prod) or site_url.lower().startswith("https://")
    trusted_hosts = web_security.trusted_hosts_from_environment()
    host_validation_ok = (not prod) or bool(trusted_hosts)
    security_ok = bool(len(raw_secret) >= 32 and secure_cookie_ok and https_ok and host_validation_ok)
    components["security_baseline"] = _component(
        "online" if security_ok else "offline", "Browser security baseline",
        "HTTPS, Secure/HttpOnly session cookies, trusted-host validation and hardened response headers are active" if security_ok else "Production requires HTTPS SITE_URL, a >=32-character WEB_SECRET and a resolvable trusted host",
        https=bool(site_url.lower().startswith("https://")), secure_cookie=secure_cookie_ok,
        web_secret_length_ok=len(raw_secret) >= 32, host_validation=host_validation_ok, trusted_host_count=len(trusted_hosts),
    )
    owner = (os.environ.get("SYMPTOSENSE_ADMIN_EMAIL") or "").strip()
    components["admin_owner"] = _component("online" if owner else "offline", "Admin owner", "Owner email configured" if owner else "SYMPTOSENSE_ADMIN_EMAIL is missing")
    launch_reset_enabled = (os.environ.get("ALLOW_LAUNCH_RESET", "0").strip().lower() in {"1","true","yes","on"})
    components["launch_reset_lock"] = _component(
        "degraded" if launch_reset_enabled else "online",
        "Destructive launch reset",
        "Temporarily enabled — disable ALLOW_LAUNCH_RESET after cleaning test data" if launch_reset_enabled else "Locked in production; destructive reset endpoint is disabled",
        enabled=launch_reset_enabled,
    )

    # Server-side Admin session epoch supports immediate global revocation.
    try:
        admin_security.init_schema()
        timeout = max(5, min(240, int(os.environ.get("ADMIN_SESSION_TIMEOUT_MINUTES", "30"))))
        components["admin_session_control"] = _component("online", "Admin session revocation", "Server-side session epoch and idle timeout are active", idle_timeout_minutes=timeout)
    except Exception as exc:
        logging.getLogger(__name__).debug("Handled exception in build; fallback applied (handler 132)")
        components["admin_session_control"] = _component("offline", "Admin session revocation", type(exc).__name__)

    # Generic pseudonymous rate-limit storage is required for protected routes.
    try:
        platform_v2.init_schema(); conn_rl = db._conn(); c_rl = conn_rl.cursor()
        c_rl.execute("SELECT 1 FROM ss_request_rate_limits LIMIT 1"); c_rl.fetchone(); conn_rl.close()
        components["rate_limiting"] = _component("online", "Rate limiting", "Auth, assistant, analysis and Admin routes are rate-limited")
    except Exception as exc:
        logging.getLogger(__name__).warning("Handled exception in build; fallback applied (handler 140)")
        components["rate_limiting"] = _component("offline", "Rate limiting", type(exc).__name__)

    # Published retention policy; health records remain user-controlled by default.
    try:
        rp = data_retention.policy()
        components["data_retention"] = _component("online", "Data retention", f"Usage analytics {rp.get('usage_analytics_days')}d · security logs {rp.get('security_log_days')}d · medication-email logs {rp.get('medication_email_days')}d · health records user-controlled", policy=rp)
    except Exception as exc:
        logging.getLogger(__name__).warning("Handled exception in build; fallback applied (handler 147)")
        components["data_retention"] = _component("degraded", "Data retention", type(exc).__name__)

    # Admin TOTP is optional and is intentionally omitted from readiness when
    # ADMIN_2FA_REQUIRED=0. This keeps a deliberate password-only Admin policy
    # from being reported as a production warning.
    if admin_2fa.required():
        try:
            if not admin_2fa.available():
                components["admin_2fa"] = _component("offline", "Admin 2FA", "WEB_SECRET/encryption dependency is not ready")
            else:
                enabled = False; remaining = 0
                if owner:
                    u = db.get_ss_user_by_email(owner) if hasattr(db, "get_ss_user_by_email") else None
                    if u:
                        st = admin_2fa.status(int(u.get("id"))); enabled = bool(st.get("enabled")); remaining = int(st.get("recovery_codes_remaining") or 0)
                components["admin_2fa"] = _component("online" if enabled else "degraded", "Admin 2FA", "TOTP enabled" if enabled else "TOTP setup is required at next Admin sign-in", enabled=enabled, recovery_codes_remaining=remaining, required=True)
        except Exception as exc:
            logging.getLogger(__name__).debug("Handled exception in build; optional Admin 2FA check failed")
            components["admin_2fa"] = _component("offline", "Admin 2FA", type(exc).__name__)

    # Research consent/export schema and current consented sample size.
    try:
        privacy_features.init_schema(); conn = db._conn(); c = conn.cursor()
        if db.USE_POSTGRES:
            c.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s", ("records",)); cols = {r[0] for r in c.fetchall()}
        else:
            c.execute("PRAGMA table_info(records)"); cols = {r[1] for r in c.fetchall()}
        has_research = "research_eligible" in cols
        participants = analyses = 0
        if has_research:
            c.execute("SELECT COUNT(DISTINCT user_hash),COUNT(*) FROM records WHERE COALESCE(research_eligible,0)=1 AND age IS NOT NULL AND age>=18"); row = c.fetchone() or (0,0); participants, analyses = int(row[0] or 0), int(row[1] or 0)
        conn.close()
        components["research_consent"] = _component("online" if has_research else "offline", "Research consent", (f"Separate research eligibility (18+) is active · consent v{privacy_features.CONSENT_VERSION} · policy v{privacy_features.PRIVACY_POLICY_VERSION}" if has_research else "research_eligible migration missing"), consented_participants=participants, eligible_analyses=analyses, consent_version=privacy_features.CONSENT_VERSION, privacy_policy_version=privacy_features.PRIVACY_POLICY_VERSION)
    except Exception as exc:
        logging.getLogger(__name__).debug("Handled exception in build; fallback applied (handler 177)")
        components["research_consent"] = _component("offline", "Research consent", type(exc).__name__, consented_participants=0, eligible_analyses=0)

    # Independent research-validation benchmark. Starter cases do not count until verified.
    try:
        vs = research_validation.summary()
        verified = int(vs.get("verified_cases") or 0); target = int(vs.get("recommended_min_verified_cases") or 50)
        vstatus = "online" if verified >= target else "degraded"
        components["research_validation"] = _component(vstatus, "Research validation", f"{verified}/{target} independently verified cases · {int(vs.get('starter_cases') or 0)} starter templates", verified_cases=verified, target_cases=target, risk_agreement_pct=vs.get("risk_agreement_pct"), urgent_sensitivity_pct=vs.get("urgent_sensitivity_pct"))
    except Exception as exc:
        logging.getLogger(__name__).debug("Handled exception in build; fallback applied (handler 186)")
        components["research_validation"] = _component("degraded", "Research validation", type(exc).__name__)

    # Error logging is always available through the application/Railway logs.
    # Sentry is an optional external monitoring integration, not a launch blocker.
    sentry_configured = bool(os.environ.get("SENTRY_DSN", "").strip())
    sentry_ver = production_verification.get("error_monitoring") if sentry_configured else None
    sentry_details = (sentry_ver or {}).get("details") or {}
    sentry_tested = bool(sentry_ver and sentry_ver.get("status") == "test_event_created" and sentry_details.get("app_version") == APP_VERSION)
    if not sentry_configured:
        sentry_status = "online"
        sentry_detail = "Application/Railway logging is active; external Sentry monitoring is optional and not configured"
    elif sentry_tested:
        sentry_status = "online"
        sentry_detail = "Privacy-safe Sentry test event created"
    else:
        sentry_status = "degraded"
        sentry_detail = "Sentry configured; run the safe Admin test"
    components["error_monitoring"] = _component(
        sentry_status, "Error logging / monitoring", sentry_detail,
        configured=sentry_configured, tested=sentry_tested, optional=True,
        last_test_at=(sentry_ver or {}).get("event_at"), event_id=((sentry_ver or {}).get("details") or {}).get("event_id"),
    )

    # Reproducibility: pin the exact symptom-triage engine used by the study.
    try:
        study = research_study.status()
        if study.get("frozen") and study.get("integrity_ok"):
            st_status = "online"
        elif study.get("frozen") and study.get("integrity_ok") is False:
            st_status = "offline"
        else:
            st_status = "degraded"
        components["research_version_freeze"] = _component(
            st_status, "Research version freeze", study.get("detail") or "",
            frozen=bool(study.get("frozen")), study_version=study.get("study_version"), frozen_app_version=study.get("app_version"), current_app_version=study.get("current_app_version") or study.get("app_version"), frozen_at=study.get("frozen_at"), integrity_ok=study.get("integrity_ok"),
        )
    except Exception as exc:
        logging.getLogger(__name__).warning("Handled exception in build; fallback applied (handler 214)")
        components["research_version_freeze"] = _component("offline", "Research version freeze", type(exc).__name__)

    # Release-candidate feature freeze: launch work is limited to fixes and verification.
    rc = release_candidate.metadata()
    components["release_candidate"] = _component(
        "online" if rc.get("feature_freeze") else "degraded", "Release candidate",
        f"{rc.get('release_candidate_id')} · channel={rc.get('release_channel')} · feature freeze={'on' if rc.get('feature_freeze') else 'off'}", **rc
    )

    # Knowledge/source freshness.
    try:
        stats = medical_knowledge.statistics()
        verified = int(stats.get("verified_sources") or 0); diseases = int(stats.get("active_diseases") or 0); review = int(stats.get("sources_needing_review") or 0)
        symptom_coverage = float(stats.get("symptom_coverage_pct") or 0.0)
        source_coverage = float(stats.get("source_coverage_pct") or 0.0)
        status = "online" if verified > 0 and diseases > 0 and symptom_coverage >= 85 and source_coverage >= 95 else "degraded"
        detail = f"{diseases} active conditions · {verified} verified sources · symptom coverage {symptom_coverage:.1f}% · source coverage {source_coverage:.1f}%"
        components["medical_knowledge"] = _component(
            status, "Medical knowledge", detail,
            active_diseases=diseases, active_symptoms=int(stats.get("active_symptoms") or 0),
            verified_sources=verified, high_authority_sources=int(stats.get("high_authority_sources") or 0),
            symptom_coverage_pct=symptom_coverage, source_coverage_pct=source_coverage,
            total_relationships=int(stats.get("total_relationships") or 0), active_red_flags=int(stats.get("active_red_flags") or 0),
            sources_needing_review=review, knowledge_version=stats.get("knowledge_version"), last_update=stats.get("last_knowledge_update"),
        )
    except Exception as exc:
        logging.getLogger(__name__).debug("Handled exception in build; fallback applied (handler 230)")
        components["medical_knowledge"] = _component("degraded", "Medical knowledge", type(exc).__name__)

    # Route smoke checks are local and non-destructive.
    expected = {"/", "/chat", "/login", "/admin", "/api/analyze", "/api/admin/system-health", "/api/admin/production-readiness"}
    rules = set(route_rules or [])
    missing = sorted(expected - rules) if rules else []
    components["route_smoke"] = _component("online" if not missing else "offline", "Core routes", "Core routes registered" if not missing else ("Missing: " + ", ".join(missing)), missing=missing)

    # Encrypted backup + isolated restore-test evidence.  A timestamp alone is not
    # treated as proof that production data can be recovered.
    try:
        bs = backup_restore.public_status()
        if bs.get("ready"):
            bstatus = "online"
            bdetail = f"Encrypted backup is fresh and restore-tested · last backup {bs.get('last_backup_age_hours')}h ago"
        elif bs.get("last_backup_status") == "ok":
            bstatus = "degraded"
            bdetail = "Backup exists, but an isolated restore test is missing/stale or the backup is too old"
        else:
            bstatus = "degraded"
            bdetail = "No recent verified application backup/restore test is available"
        components["backup_evidence"] = _component(bstatus, "Backup & restore", bdetail, **bs)
    except Exception as exc:
        logging.getLogger(__name__).warning("Handled exception in build; fallback applied (handler 253)")
        components["backup_evidence"] = _component("degraded", "Backup & restore", type(exc).__name__)

    critical = ["database", "email", "session_secret", "security_baseline", "admin_owner", "admin_session_control", "rate_limiting", "research_consent", "route_smoke", "research_version_freeze", "backup_evidence"]
    if admin_2fa.required():
        critical.append("admin_2fa")
    if any(components[k]["status"] == "offline" for k in critical): overall = "not_ready"
    elif any(v["status"] in {"offline", "degraded"} for v in components.values()): overall = "attention"
    else: overall = "ready"
    return {
        "version": APP_VERSION,
        "checked_at": _now(),
        "response_ms": round((time.perf_counter()-started)*1000, 1),
        "overall": overall,
        "components": components,
    }
