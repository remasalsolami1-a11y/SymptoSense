"""
webapp.py - الموقع الرسمي لـ SymptoSense
نفس محرك التحليل المستخدم في البوت (analysis_core) مع واجهة ويب عربية كاملة.
"""
import logging
import os
import railway_runtime
railway_runtime.normalize_environment()
import io
import zipfile
import csv
import re
import json
import base64
import secrets
import hashlib
import hmac
import html as html_lib
import time
import threading
import queue
import smtplib
import ssl
import ipaddress
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import parseaddr
from urllib.parse import urlsplit, quote, urlencode
CONTACT_TELEGRAM = os.environ.get("CONTACT_TELEGRAM", "rms_2o")
from functools import lru_cache, wraps
from flask import Flask, request, jsonify, render_template_string, session, send_file, send_from_directory, Response, redirect, url_for, g, abort, has_request_context, make_response
import db
import best_effort
import inline_assets
from services.medication_service import MEDS_API_REVISION  # noqa: F401 - re-exported; the revision lives with the service
from pagelib.pages_html import blood_page, meds_page, safeid_page
from services.search_answers import _health_search_question_answer, _health_search_relation_result, _pdf_report, _search_contextual_structured_result
import services.search_answers as services_search_answers
from services.search_answers import _assistant_general_local_fallback
import pagelib.pages_html as pagelib_pages_html
from pagelib.pages_html import about_us_page, analysis_detail_page, calculators_page, checkin_page, consent_page, emergency_page, family_detail_page, family_page, home_page, privacy_center_page, privacy_page, search_page, sources_page, welcome_page
import routes.pages as routes_pages
from routes.pages import health_library_detail, methodology, trust
import routes.admin as routes_admin
import routes.tracking as routes_tracking
import routes.assistant as routes_assistant
from routes.assistant import api_analyze
import routes.auth as routes_auth
from routes.auth import reset_password, verify_email_token
import routes.labs as routes_labs
import routes.medications as routes_medications
import medication_warnings
import external_drug_lookup
import geo_hospitals
import blood_test
import lab_intake
import wellbeing
import health_tips
import admin_knowledge_routes
import health_trends_page
import health_library
import analysis_core
import health_search
import health_search_extra
from assistant_knowledge_extra import ASSISTANT_EXTRA_SYMPTOMS_V60, ASSISTANT_CONTEXT_PATTERNS_V60
import calculators as calcmod
import medical_knowledge
import search_lab_cards, search_fidelity
import medical_source_pipeline
import medical_taxonomy
import symptom_guidance
import content_priority
import clinical_text
import symptom_context
import safety_engine
import decision_log
import clinical_review
import platform_v2
import advanced_features
import admin_operational
import admin_complete
import medication_email
import medication_telegram
import privacy_features
import research_validation
import production_readiness
import production_verification
import performance_benchmark
import research_study
import release_candidate
import admin_2fa
import admin_security
import data_retention
import backup_restore
import web_security
import api_v1
import user_experience
import feature_flags
import request_tracing
import ops_metrics
import ops_quality
import passkeys
import background_jobs
import source_monitor
import v50_wow
import v51_innovation
import judge_challenge
import search_engine_v2
import content_gaps
import v47_routes
from chat_view import render_chat_page
from site_info_view import render_site_info_page
from demo_analysis import demo_analysis_result
from dashboard import DASHBOARD_HTML
def _json_for_script(value, *, ensure_ascii=False):
    """Backward-compatible wrapper around the tested script-context encoder."""
    return web_security.json_for_script(value, ensure_ascii=ensure_ascii)
def _scrub_sentry_event(event, _hint=None):
    """Keep error telemetry content-free: no request, user, health, or breadcrumb data."""
    cleaned = dict(event or {})
    for field in ("request", "user", "breadcrumbs", "extra", "contexts"):
        cleaned.pop(field, None)
    return cleaned
def _configure_error_monitoring():
    """Enable privacy-first Sentry only when Production explicitly provides a DSN."""
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        sentry_sdk.init(
            dsn=dsn,
            integrations=[FlaskIntegration()],
            send_default_pii=False,
            include_local_variables=False,
            max_breadcrumbs=0,
            traces_sample_rate=0.0,
            profiles_sample_rate=0.0,
            release=release_candidate.APP_VERSION,
            environment=(os.environ.get("SENTRY_ENVIRONMENT") or os.environ.get("RAILWAY_ENVIRONMENT_NAME") or ("production" if os.environ.get("RAILWAY_ENVIRONMENT") else "development")),
            before_send=_scrub_sentry_event,
        )
        return True
    except Exception:
        logging.getLogger(__name__).warning("Handled exception in _configure_error_monitoring; fallback applied (handler 85)")
        return False
_sentry_enabled = _configure_error_monitoring()
app = Flask(__name__)
STATIC_ASSET_VERSION = f"{release_candidate.APP_VERSION}-193"
app.wsgi_app = railway_runtime.RailwayHealthcheckMiddleware(app.wsgi_app)
if os.environ.get("SENTRY_DSN", "").strip() and not _sentry_enabled:
    app.logger.warning("Sentry was requested but could not be initialized")
_configured_web_secret = os.environ.get("WEB_SECRET", "").strip()
_RAILWAY_RUNTIME = bool(
    os.environ.get("RAILWAY_ENVIRONMENT")
    or os.environ.get("RAILWAY_ENVIRONMENT_NAME")
    or os.environ.get("RAILWAY_PROJECT_ID")
    or os.environ.get("RAILWAY_PUBLIC_DOMAIN")
)
if _RAILWAY_RUNTIME:
    missing = []
    if len(_configured_web_secret) < 32:
        missing.append("WEB_SECRET (>=32 characters)")
    if not os.environ.get("DATABASE_URL", "").strip() and not os.environ.get("SYMPTOSENSE_DATABASE_MODE", "").startswith("sqlite-"):
        missing.append("DATABASE_URL")
    if missing:
        app.logger.error("Unsafe production configuration; missing: %s; continuing only so Railway can expose diagnostics", ", ".join(missing))
app.secret_key = _configured_web_secret or secrets.token_hex(32)
if not _configured_web_secret:
    app.logger.warning("WEB_SECRET is not configured; using an ephemeral development session key")
app.config["MAX_CONTENT_LENGTH"] = 26 * 1024 * 1024
_secure_cookie_env = os.environ.get("SESSION_COOKIE_SECURE")
_is_https_production = bool(
    os.environ.get("RAILWAY_ENVIRONMENT")
    or os.environ.get("RAILWAY_PUBLIC_DOMAIN")
    or os.environ.get("SITE_URL", "").strip().lower().startswith("https://")
)
if _RAILWAY_RUNTIME:
    _secure_cookie = True
else:
    _secure_cookie = (
        _secure_cookie_env == "1"
        if _secure_cookie_env is not None
        else _is_https_production
    )
_trusted_hosts = web_security.trusted_hosts_from_environment()
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=_secure_cookie,
    SESSION_COOKIE_NAME="__Host-symptosense_session" if _secure_cookie else "symptosense_session",
    SESSION_COOKIE_PATH="/",
    SESSION_COOKIE_DOMAIN=None,
    SESSION_REFRESH_EACH_REQUEST=False,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
    TRUSTED_HOSTS=_trusted_hosts or None,
    PREFERRED_URL_SCHEME="https" if _is_https_production or _RAILWAY_RUNTIME else "http",
    # Bound multipart form complexity independently from MAX_CONTENT_LENGTH.
    MAX_FORM_MEMORY_SIZE=1024 * 1024,
    MAX_FORM_PARTS=100,
)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
V2_CSS = inline_assets.text("V2_CSS.css")
PREMIUM_POLISH_CSS = inline_assets.text("PREMIUM_POLISH_CSS.css")
PREMIUM_POLISH_CSS += inline_assets.text("PREMIUM_POLISH_CSS_1.css")
PREMIUM_POLISH_CSS += inline_assets.text("PREMIUM_POLISH_CSS_2.css")
PREMIUM_POLISH_CSS += """
/* ===== Final symptom-chat viewport + audio UX fix 2026-09-08 ===== */
/* Keep the questionnaire complete and scrollable instead of clipping it to 100dvh. */
body.ss-chat-page{overflow-x:hidden!important}
@media (max-width:900px){
  body.ss-chat-page{height:auto!important;min-height:100svh!important;overflow-y:auto!important;overscroll-behavior-y:auto!important;background:#F7FAFC!important}
  body.ss-chat-page .container{height:auto!important;min-height:calc(100svh - var(--bnav-h) - var(--safe-bottom))!important;overflow:visible!important;padding:8px 8px calc(var(--bnav-h) + var(--safe-bottom) + 18px)!important}
  body.ss-chat-page .chat-wrap{width:100%!important;height:auto!important;min-height:calc(100svh - var(--bnav-h) - var(--safe-bottom) - 18px)!important;max-height:none!important;overflow:hidden!important;margin:0 auto!important;display:flex!important;flex-direction:column!important}
  body.ss-chat-page .chat-body{flex:0 0 auto!important;min-height:96px!important;max-height:none!important;overflow:visible!important;padding:10px!important}
  body.ss-chat-page .chat-body.result-mode{flex:0 0 auto!important;max-height:none!important;overflow:visible!important}
  body.ss-chat-page .chat-options{flex:0 0 auto!important;min-height:0!important;max-height:none!important;overflow:visible!important;align-content:start!important}
  body.ss-chat-page .chat-options.symptom-picker{max-height:min(42svh,390px)!important;overflow-y:auto!important;-webkit-overflow-scrolling:touch!important}
  body.ss-chat-page .chat-input{position:relative!important;inset:auto!important;flex:0 0 auto!important;padding-bottom:10px!important}
  body.ss-chat-page #chatSafetyNote{margin:10px 8px calc(var(--bnav-h) + var(--safe-bottom) + 8px)!important}
  body.ss-chat-page .step-focus-card{scroll-margin-top:10px!important}
}
@media (max-width:420px){
  body.ss-chat-page .chat-head{padding:9px 10px!important}
  body.ss-chat-page .chat-head-toggles{gap:7px!important}
  body.ss-chat-page .chat-head .chat-audio-btn{width:44px!important;height:44px!important;min-width:44px!important}
  body.ss-chat-page .chat-options:not(.symptom-picker){grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:9px!important}
  body.ss-chat-page .chat-options:not(.symptom-picker) .opt{min-height:54px!important;font-size:14px!important}
  body.ss-chat-page .chat-input input{font-size:16px!important}
}
@media (max-width:340px){
  body.ss-chat-page .chat-options:not(.symptom-picker){grid-template-columns:1fr!important}
}
@media (min-width:901px){
  body.ss-chat-page{min-height:100vh!important;overflow-y:auto!important}
  body.ss-chat-page .chat-wrap{height:clamp(560px,76vh,760px)!important;min-height:560px!important;max-height:760px!important}
  body.ss-chat-page .chat-body{overflow-y:auto!important}
  body.ss-chat-page .chat-options{max-height:38%!important;overflow-y:auto!important}
}
"""
PREMIUM_POLISH_CSS += inline_assets.text("PREMIUM_POLISH_CSS_3.css")
PREMIUM_POLISH_CSS += inline_assets.text("PREMIUM_POLISH_CSS_4.css")
PREMIUM_POLISH_CSS += """
/* ===== Full-screen symptom questionnaire on phones/tablets 2026-09-14 ===== */
/* Scope is deliberately limited to the symptom-analysis page. */
@media (max-width:900px){
  body.ss-chat-page .container{
    width:100%!important;
    height:calc(100svh - var(--bnav-h) - var(--safe-bottom))!important;
    min-height:calc(100svh - var(--bnav-h) - var(--safe-bottom))!important;
    padding:0!important;
  }
  body.ss-chat-page .chat-wrap{
    width:100%!important;
    height:100%!important;
    min-height:100%!important;
    max-height:100%!important;
    margin:0!important;
    border:0!important;
    border-radius:0!important;
    box-shadow:none!important;
    display:flex!important;
    flex-direction:column!important;
  }
  body.ss-chat-page .chat-body:not(.result-mode){
    flex:0 0 auto!important;
    display:block!important;
    min-height:0!important;
  }
  body.ss-chat-page .chat-options{flex:0 0 auto!important}
  body.ss-chat-page .chat-input{
    flex:0 0 auto!important;
    margin-top:0!important;
  }
}
@supports (height:100dvh){
  @media (max-width:900px){
    body.ss-chat-page .container{
      height:calc(100dvh - var(--bnav-h) - var(--safe-bottom))!important;
      min-height:calc(100dvh - var(--bnav-h) - var(--safe-bottom))!important;
    }
  }
}
"""
PREMIUM_POLISH_CSS += """
/* ===== Mobile active-question position fix 2026-09-14 ===== */
@media (max-width:900px){
  body.ss-chat-page .chat-body:not(.result-mode){
    padding-top:clamp(22px,4svh,36px)!important;
  }
}
@media (max-height:680px) and (max-width:900px){
  body.ss-chat-page .chat-body:not(.result-mode){padding-top:14px!important}
}
"""
PREMIUM_POLISH_CSS += inline_assets.text("PREMIUM_POLISH_CSS_5.css")
PREMIUM_POLISH_CSS += """
/* ===== iPhone questionnaire position — final override 2026-09-14 ===== */
/* Keep the first age / gender question visually centered in the usable area.
   This block intentionally comes after the symptom-picker overrides above,
   which previously reset the spacing back to 14px and made the fix invisible. */
@media (max-width:900px){
  body.ss-chat-page[data-chat-step="age"] .chat-body:not(.result-mode){
    padding:clamp(52px,7svh,82px) 12px 0!important;
  }
  body.ss-chat-page[data-chat-step="gender"] .chat-body:not(.result-mode){
    padding:clamp(42px,6svh,68px) 12px 0!important;
  }
  body.ss-chat-page[data-chat-step="age"] .step-focus-card,
  body.ss-chat-page[data-chat-step="gender"] .step-focus-card{
    border:1px solid #D7E7F1!important;
    border-radius:18px!important;
    padding:17px 16px!important;
  }
  body.ss-chat-page[data-chat-step="age"] .chat-input{
    margin:16px 12px 12px!important;
  }
  body.ss-chat-page[data-chat-step="gender"] .chat-options{
    margin-top:16px!important;
    border-top:1px solid #D7E7F1!important;
    border-radius:16px!important;
  }
}
@media (max-width:900px) and (max-height:700px){
  body.ss-chat-page[data-chat-step="age"] .chat-body:not(.result-mode),
  body.ss-chat-page[data-chat-step="gender"] .chat-body:not(.result-mode){
    padding-top:24px!important;
  }
}
"""
PREMIUM_POLISH_CSS += """
/* Compact mobile questionnaire: one scrolling container and grouped inputs. */
@media(max-width:900px){
  body.ss-chat-page{height:100dvh!important;min-height:0!important;max-height:100dvh!important;overflow:hidden!important;background:#F4F8FC!important}
  body.ss-chat-page .container{display:block!important;height:calc(100dvh - var(--bnav-h) - var(--safe-bottom))!important;min-height:0!important;overflow-y:auto!important;overflow-x:hidden!important;padding:0 0 20px!important;background:#F4F8FC!important;overscroll-behavior:contain}
  body.ss-chat-page .chat-wrap{display:block!important;height:auto!important;min-height:0!important;max-height:none!important;overflow:visible!important;border:0!important;border-radius:0!important;background:#F4F8FC!important;margin:0!important;box-shadow:none!important}
  body.ss-chat-page .chat-head{position:relative!important;top:auto!important;box-shadow:none!important}
  body.ss-chat-page #chatBody{height:auto!important;min-height:0!important;max-height:none!important;overflow:visible!important;padding:20px 12px 0!important;background:transparent!important}
  body.ss-chat-page #chatBody .step-focus-card{height:auto!important;min-height:0!important;padding:18px 16px 12px!important;margin:0!important;border:1px solid #D7E7F1!important;border-bottom:0!important;border-radius:16px 16px 0 0!important;background:#fff!important}
  body.ss-chat-page #chatBody .step-focus-question{font-size:18px!important;line-height:1.6!important}
  body.ss-chat-page #chatOptions{height:auto!important;min-height:0!important;max-height:none!important;overflow:visible!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:10px!important;margin:0 12px 14px!important;padding:12px!important;border:1px solid #D7E7F1!important;border-top:0!important;border-radius:0 0 16px 16px!important}
  body.ss-chat-page #chatOptions:empty{display:none!important}
  body.ss-chat-page .chat-wrap.report-mode #chatOptions{display:none!important}
  body.ss-chat-page #chatOptions .opt{min-height:58px!important;height:auto!important;width:100%!important;font-size:14px!important;line-height:1.5!important;padding:10px 8px!important;white-space:normal!important;display:flex!important;align-items:center!important;justify-content:center!important}
  body.ss-chat-page #chatInput{position:relative!important;inset:auto!important;margin:0 12px 14px!important;padding:12px!important;border:1px solid #D7E7F1!important;border-top:0!important;border-radius:0 0 16px 16px!important;gap:8px!important;background:#fff!important}
  body.ss-chat-page #chatInput input{font-size:16px!important;min-height:48px!important}
  body.ss-chat-page #chatSafetyNote{margin:12px!important}
}
"""
PREMIUM_POLISH_CSS += inline_assets.text("PREMIUM_POLISH_CSS_6.css")
PREMIUM_POLISH_CSS += inline_assets.text("PREMIUM_POLISH_CSS_7.css")
PREMIUM_POLISH_CSS += r"""
/* ===== v30 phone questionnaire layout: full-width age step + Continue below symptoms ===== */
@media (max-width:640px){
  /* Age should start directly below progress and use the phone width instead of
     floating in the middle of a large empty area. */
  body.ss-chat-page[data-chat-step="age"] #chatBody:not(.result-mode),
  body.ss-chat-page[data-chat-step="gender"] #chatBody:not(.result-mode){
    padding:14px 12px 0!important;
  }
  body.ss-chat-page[data-chat-step="age"] .step-focus-card,
  body.ss-chat-page[data-chat-step="gender"] .step-focus-card{
    width:100%!important;max-width:none!important;margin:0!important;
    border-radius:18px 18px 0 0!important;
    padding:18px 16px 14px!important;
    box-shadow:none!important;
  }
  body.ss-chat-page[data-chat-step="age"] #chatInput{
    display:grid!important;grid-template-columns:1fr!important;
    width:auto!important;max-width:none!important;
    margin:0 12px 16px!important;padding:12px!important;
    border:1px solid #D4E5EF!important;border-top:0!important;
    border-radius:0 0 18px 18px!important;background:#fff!important;
    box-shadow:0 7px 20px rgba(27,75,111,.055)!important;
  }
  body.ss-chat-page[data-chat-step="age"] #chatInput input{
    width:100%!important;min-height:54px!important;height:54px!important;
    font-size:18px!important;text-align:start!important;border-radius:14px!important;
  }
  body.ss-chat-page[data-chat-step="age"] #chatInput button{
    width:100%!important;min-height:50px!important;height:50px!important;
    border-radius:14px!important;font-size:15px!important;font-weight:900!important;
  }
  body.ss-chat-page[data-chat-step="gender"] #chatOptions{
    width:auto!important;max-width:none!important;margin:0 12px 16px!important;
  }

  /* Symptom choices first, then the follow-up/Continue action below them. */
  body.ss-chat-page[data-chat-step="symptoms"] #chatOptions.symptom-picker .opt{
    order:0!important;
  }
  body.ss-chat-page[data-chat-step="symptoms"] #chatOptions.symptom-picker #relBlock{
    order:5!important;
  }
  body.ss-chat-page[data-chat-step="symptoms"] #chatOptions.symptom-picker .start-btn{
    order:10!important;position:static!important;top:auto!important;
    grid-column:1/-1!important;width:100%!important;
    min-height:54px!important;margin:6px 0 0!important;
    border-radius:14px!important;font-size:15px!important;font-weight:900!important;
    box-shadow:0 5px 14px rgba(40,127,193,.12)!important;
  }
}
"""
PREMIUM_POLISH_CSS += inline_assets.text("PREMIUM_POLISH_CSS_8.css")
PREMIUM_POLISH_CSS += r"""
/* ===== v32 mobile age spacing — question first, breathing room, answer field ===== */
@media (max-width:640px){
  /* Keep the age question near the top, then add deliberate vertical breathing
     room before the answer field. The form remains full-width on the phone. */
  body.ss-chat-page[data-chat-step="age"] #chatBody .step-focus-card{
    padding:28px 20px clamp(58px,8svh,74px)!important;
  }
  body.ss-chat-page[data-chat-step="age"] #chatBody .step-focus-question{
    margin:0!important;
  }
  body.ss-chat-page[data-chat-step="age"] #chatInput{
    padding:0 20px 28px!important;
    gap:14px!important;
  }
  body.ss-chat-page[data-chat-step="age"] #chatInput input{
    min-height:58px!important;
    height:58px!important;
  }
}
@media (max-width:640px) and (max-height:700px){
  body.ss-chat-page[data-chat-step="age"] #chatBody .step-focus-card{
    padding-bottom:46px!important;
  }
}
"""
PREMIUM_POLISH_CSS += r"""
/* ===== v36 symptom flow regression guard — choices first, Continue last on every device ===== */
body.ss-chat-page[data-chat-step="symptoms"] #chatOptions.symptom-picker .start-btn{
  order:999!important;
  position:static!important;
  inset:auto!important;
  grid-column:1/-1!important;
  width:100%!important;
  margin:10px 0 0!important;
}
"""
PREMIUM_POLISH_CSS += inline_assets.text("PREMIUM_POLISH_CSS_9.css")
PREMIUM_POLISH_CSS += inline_assets.text("PREMIUM_POLISH_CSS_10.css")

PREMIUM_POLISH_CSS += inline_assets.text("PREMIUM_POLISH_CSS_11.css")

BASE_CSS = inline_assets.text("BASE_CSS.css")
PAGE_FRAME = inline_assets.text("PAGE_FRAME.html")
def _user_id():
    if "uid" not in session:
        session["uid"] = secrets.token_hex(8)
        # V210: this is a brand-new random guest owner key, so no persisted
        # consent row can exist for it yet. Remember that fact in the signed
        # session and avoid a pointless hosted-DB lookup on the first trip to
        # /chat or /consent. The marker is cleared as soon as consent is saved.
        session["_guest_consent_db_empty"] = True
    return "web-" + hashlib.sha1(session["uid"].encode(), usedforsecurity=False).hexdigest()[:12]
def _ss_user_id():
    """Get the logged-in SymptoSense user ID from session, or None."""
    return session.get("ss_user_id")
def _data_user_id():
    """Stable owner key for health records; falls back to the browser session for public use."""
    account_id = _ss_user_id()
    return "account-%s" % account_id if account_id else _user_id()
def _medication_user_id():
    """Numeric signed-in account id used by medication reminder tables.

    The general health-data owner key is intentionally a string such as
    ``account-12``. Medication reminder/email/Telegram tables, however, store a
    foreign-style numeric account id. Keeping this conversion in one helper
    prevents accidental ``int('account-12')`` failures.
    """
    account_id = _ss_user_id()
    if account_id in (None, ""):
        raise PermissionError("login_required")
    return int(account_id)
def _consent_subject_key():
    """Internal subject key for consent/data controls; never exposed in analytics output."""
    return _data_user_id()
def _consent_state():
    """Return consent without making avoidable hosted-DB round trips.

    Guest consent belongs to the browser session. Once it has been read/saved we
    keep a tiny, version-checked mirror in the signed Flask session cookie. This
    makes repeated visits to /chat instant instead of opening a PostgreSQL
    connection just to decide whether a consent redirect is needed. Signed-in
    accounts still read the database so cross-device privacy changes remain
    authoritative. A brand-new guest cannot already have a persisted consent
    row, so we can safely return the default state without touching the DB.
    """
    try:
        account_id = _ss_user_id()
        default_state = {
            "service_usage": False, "analytics_research": False,
            "research_participation": False, "ai_improvement": False,
            "consent_version": privacy_features.CONSENT_VERSION,
            "privacy_policy_version": privacy_features.PRIVACY_POLICY_VERSION,
            "needs_review": True, "updated_at": None,
        }
        if has_request_context() and not account_id:
            mirror = session.get("_guest_consent_state")
            if isinstance(mirror, dict):
                if (mirror.get("consent_version") == privacy_features.CONSENT_VERSION
                        and mirror.get("privacy_policy_version") == privacy_features.PRIVACY_POLICY_VERSION):
                    return mirror
            # No guest owner key means there cannot be an older DB row for this
            # browser yet. A V210 session marker also proves that the random
            # owner key was created locally and has never been persisted. Avoid
            # opening PostgreSQL merely to rediscover the default state.
            if "uid" not in session or session.get("_guest_consent_db_empty") is True:
                return default_state

        key = (_consent_subject_key(), account_id)
        if has_request_context():
            cached = getattr(g, "_ss_consent_state_cache", None)
            if cached and cached.get("key") == key:
                return cached.get("value") or {}
        value = privacy_features.get_consent(key[0], key[1])
        if has_request_context():
            g._ss_consent_state_cache = {"key": key, "value": value}
            if not account_id:
                session["_guest_consent_state"] = {
                    k: value.get(k) for k in (
                        "service_usage", "analytics_research", "research_participation",
                        "ai_improvement", "consent_version", "privacy_policy_version",
                        "needs_review", "updated_at"
                    )
                }
                # If the compatibility lookup found no historical consent,
                # future checks in this guest session can stay DB-free.
                if not value.get("updated_at") and not value.get("service_usage"):
                    session["_guest_consent_db_empty"] = True
        return value
    except Exception:
        logging.getLogger(__name__).warning("Handled exception in _consent_state; fallback applied (handler 3531)")
        return {"service_usage": False, "analytics_research": False, "research_participation": False, "needs_review": True}
def _service_consent_ok():
    state = _consent_state()
    return bool(state.get("service_usage")) and not bool(state.get("needs_review"))
def _consent_required_json(next_path="/chat"):
    """Return the standard JSON response used when service consent is required.

    Several API routes rely on this helper.  Keep the destination local to the
    application so a crafted ``next`` value cannot become an external redirect.
    """
    target = str(next_path or "/chat").strip() or "/chat"
    if not target.startswith("/") or target.startswith("//"):
        target = "/chat"
    ar = _lang() == "ar"
    return jsonify({
        "ok": False,
        "error": (
            "يلزم اختيار تفضيلات الخصوصية والموافقة على استخدام الخدمة أولًا."
            if ar else
            "Please choose your privacy preferences and consent to service usage first."
        ),
        "consent_required": True,
        "consent_url": url_for("consent", next=target),
    }), 403
def _analytics_consent_ok():
    """Analytics consent is valid only for the current consent/policy versions."""
    state = _consent_state()
    return bool(state.get("analytics_research")) and not bool(state.get("needs_review"))
def _research_consent_ok():
    """Scientific-research participation is separate from product analytics."""
    state = _consent_state()
    return bool(state.get("research_participation")) and not bool(state.get("needs_review"))

def _analytics_session_id():
    """Random per-browser-session identifier used only for anonymous journey analytics."""
    sid=session.get("_analytics_sid")
    if not sid:
        sid=secrets.token_urlsafe(18)
        session["_analytics_sid"]=sid
    return sid

def _ss_user():
    """Get the logged-in user info dict, or None.

    If the authenticated session belongs to the configured existing project
    owner, repair that same account's persisted role to ``admin``. No user is
    created and no password/credential is read or stored here.
    """
    uid = _ss_user_id()
    if not uid:
        return None
    user = db.get_ss_user(uid)
    if user and db.is_owner_admin_email(user.get("email")) and user.get("role") != "admin":
        if db.promote_existing_owner_admin(uid):
            user = db.get_ss_user(uid)
    return user

def _ss_health():
    """Get the logged-in user's health profile, or None."""
    uid = _ss_user_id()
    if not uid:
        return None
    return db.load_health_profile(uid)

def _ss_privacy():
    """Get the logged-in user's privacy settings."""
    uid = _ss_user_id()
    if not uid:
        return {"use_in_assistant": True, "use_in_analysis": True, "use_in_calculators": True, "save_chat_history": True}
    return db.load_privacy_settings(uid)

def login_required(f):
    """Require an authenticated *and email-verified* account."""
    @wraps(f)
    def decorated(*args, **kwargs):
        uid = _ss_user_id()
        if not uid:
            next_url = request.full_path.rstrip("?")
            return redirect(url_for("login", next=next_url))
        user = db.get_ss_user(uid)
        if not user or user.get("status") != "active":
            session.clear()
            return redirect(url_for("login"))
        if not bool(user.get("email_verified", True)):
            session.pop("ss_user_id", None)
            session.pop("admin_last_seen", None)
            session["pending_verification_user_id"] = int(uid)
            session.permanent = True
            return redirect(url_for("verify_email_pending"))
        return f(*args, **kwargs)
    return decorated

def api_login_required(f):
    """JSON-friendly guard for private APIs, including verification status."""
    @wraps(f)
    def decorated(*args, **kwargs):
        uid = _ss_user_id()
        if not uid:
            destination = "/family" if request.path.startswith("/api/family") else "/meds"
            return jsonify({
                "ok": False,
                "error": "login_required",
                "login_url": url_for("login", next=destination),
            }), 401
        user = db.get_ss_user(uid)
        if not user or user.get("status") != "active":
            session.clear()
            return jsonify({"ok": False, "error": "login_required"}), 401
        if not bool(user.get("email_verified", True)):
            session.pop("ss_user_id", None)
            session.pop("admin_last_seen", None)
            session["pending_verification_user_id"] = int(uid)
            return jsonify({
                "ok": False,
                "error": "verification_required",
                "verification_url": url_for("verify_email_pending"),
            }), 403
        return f(*args, **kwargs)
    return decorated

def _admin_role():
    user = _ss_user()
    if not user or user.get("status") != "active":
        return "user"
    return "admin" if user.get("role") == "admin" else "user"

def _admin_allowed(scope="access"):
    """Single-owner RBAC: every admin capability requires role=admin."""
    return _admin_role() == "admin"

def _admin_session_valid(touch=True):
    """Validate the normal session, persisted role, and Admin idle timeout."""
    user = _ss_user()
    if not user or user.get("status") != "active" or user.get("role") != "admin":
        return False
    if admin_2fa.required() and not bool(session.get("admin_2fa_verified")):
        g.admin_2fa_required = True
        return False
    try:
        expected_epoch = admin_security.current_epoch(int(user.get("id")))
        if int(session.get("admin_session_epoch") or 0) != int(expected_epoch):
            session.clear()
            g.admin_session_expired = True
            return False
    except Exception:
        # Security state must fail closed for the privileged Admin surface.
        logging.getLogger(__name__).debug("Handled exception in _admin_session_valid; fallback applied (handler 3693)")
        session.clear(); g.admin_session_expired = True; return False
    try:
        timeout_minutes = max(5, min(240, int(os.environ.get("ADMIN_SESSION_TIMEOUT_MINUTES", "30"))))
    except (TypeError, ValueError):
        timeout_minutes = 30
    now_ts = int(datetime.now(timezone.utc).timestamp())
    last_seen = session.get("admin_last_seen")
    if last_seen is not None:
        try:
            expired = now_ts - int(last_seen) > timeout_minutes * 60
        except (TypeError, ValueError):
            expired = True
        if expired:
            best_effort.call(platform_v2.audit, int(user.get('id')), 'session_timeout', 'admin_session', 'self', None, {'status': 'expired'})
            session.clear()
            g.admin_session_expired = True
            return False
    if touch:
        session["admin_last_seen"] = now_ts
    return True

def _complete_admin_2fa_login(user_id: int, method: str = "totp"):
    """Promote a password-verified + second-factor-verified Admin session."""
    uid = int(user_id)
    user = db.get_ss_user(uid)
    if not user or user.get("status") != "active" or user.get("role") != "admin":
        raise ValueError("admin_account_unavailable")
    session.clear()
    session["ss_user_id"] = uid
    session["login_toast"] = "admin"
    session["admin_last_seen"] = int(datetime.now(timezone.utc).timestamp())
    session["admin_2fa_verified"] = True
    session["admin_2fa_method"] = str(method or "totp")
    session["admin_session_epoch"] = admin_security.current_epoch(uid)
    session.permanent = True
    best_effort.call(platform_v2.audit, uid, 'login_2fa_verified', 'admin_session', 'self', None, {'status': 'success', 'method': str(method or 'totp')})
    return user

def _begin_admin_2fa_challenge(user_id: int):
    """Create a short-lived pre-auth session after the Admin password succeeds."""
    session.clear()
    session["pending_admin_2fa_user_id"] = int(user_id)
    session["pending_admin_2fa_started_at"] = int(datetime.now(timezone.utc).timestamp())
    session.permanent = True

def _pending_admin_2fa_user():
    uid = session.get("pending_admin_2fa_user_id")
    started = session.get("pending_admin_2fa_started_at")
    if not uid or not started:
        return None
    try:
        if int(datetime.now(timezone.utc).timestamp()) - int(started) > 10 * 60:
            session.clear(); return None
    except (TypeError, ValueError):
        session.clear(); return None
    user = db.get_ss_user(int(uid))
    if not user or user.get("status") != "active" or user.get("role") != "admin":
        session.clear(); return None
    return user

def _admin_csrf_token():
    if "admin_csrf" not in session:
        session["admin_csrf"] = secrets.token_urlsafe(32)
    return session["admin_csrf"]

def _user_csrf_token():
    """Session-bound CSRF token used by signed-in, state-changing user APIs."""
    if "user_csrf" not in session:
        session["user_csrf"] = secrets.token_urlsafe(32)
    return session["user_csrf"]

def _user_csrf_valid():
    supplied = request.headers.get("X-CSRF-Token", "") or request.form.get("csrf_token", "")
    expected = session.get("user_csrf", "")
    return bool(expected and supplied and hmac.compare_digest(supplied, expected))

@app.before_request
def validate_api_request_size_and_json():
    """Bound request work before Flask parses JSON or multipart bodies.

    Per-request limits protect both Content-Length and chunked uploads. Route
    code still performs a second bounded read for defense in depth.
    """
    upload_limits = {
        "/api/voice": _bounded_env_int("VOICE_UPLOAD_MAX_BYTES", 8 * 1024 * 1024, 1024 * 1024, 12 * 1024 * 1024),
        "/api/blood": _bounded_env_int("BLOOD_UPLOAD_MAX_BYTES", 25 * 1024 * 1024, 2 * 1024 * 1024, 25 * 1024 * 1024),
    }
    upload_limit = upload_limits.get(request.path)
    if upload_limit is not None and request.method == "POST":
        # Allow a small multipart-envelope overhead while keeping the uploaded
        # file itself bounded by the explicit route-level read below.
        request.max_content_length = upload_limit + 256 * 1024
        if request.content_length is not None and request.content_length > request.max_content_length:
            return jsonify({"ok": False, "error": "Upload too large.", "error_code": "payload_too_large"}), 413

    if request.path.startswith("/api/") and request.is_json and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        max_json_bytes = _bounded_env_int("MAX_API_JSON_BYTES", 262144, 16384, 1048576)
        request.max_content_length = max_json_bytes
        if request.content_length is not None and request.content_length > max_json_bytes:
            return jsonify({"ok": False, "error": "JSON payload too large.", "error_code": "payload_too_large"}), 413
        if not isinstance(request.get_json(silent=True), dict):
            return jsonify({"ok": False, "error": "Invalid JSON object.", "error_code": "invalid_input"}), 400
    return None

def _analysis_input_error(data):
    """Validate and bound client-controlled shapes before matching or saved-data access."""
    list_fields = ("symptoms", "negative_symptoms", "negatives", "asked")
    for field in list_fields:
        value = data.get(field)
        if value is None:
            continue
        if field == "symptoms" and isinstance(value, str):
            if len(value) > 2000:
                return field
            continue
        if (
            not isinstance(value, list)
            or len(value) > 40
            or any(not isinstance(x, str) or len(x) > 240 for x in value)
        ):
            return field
    string_limits = {
        "lang": 8, "gender": 32, "duration": 160, "conditions": 3000,
        "medications": 3000, "allergies": 3000, "notes": 5000, "location": 240,
    }
    for field, max_len in string_limits.items():
        value = data.get(field)
        if value is not None and (not isinstance(value, str) or len(value) > max_len):
            return field
    for field in ("use_saved", "history_answered"):
        if field in data and not isinstance(data[field], bool):
            return field
    for field, lower, upper in (("age", 0, 130), ("severity", 1, 5), ("member_id", 0, 2147483647), ("blood_id", 1, 2147483647), ("previous_record_id", 1, 2147483647)):
        value = data.get(field)
        if value in (None, ""):
            continue
        if field == "age":
            if clinical_text.parse_age_years(value) is None:
                return field
            continue
        try:
            number = float(value)
            if isinstance(value, bool) or not lower <= number <= upper or (field != "age" and not number.is_integer()):
                return field
        except (TypeError, ValueError, OverflowError):
            return field
    return None

@app.before_request
def protect_sensitive_user_api_csrf():
    """Protect browser-originated mutations of signed-in user health/profile data.

    Medication email actions use one-time URL tokens and intentionally remain
    outside this browser-session CSRF gate. Guest analysis/CBC calls remain
    available because this hook is activated only for signed-in sessions; when
    signed in, health-result persistence is protected with the session CSRF token.
    """
    if app.config.get("TESTING"):
        return None
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"} or not _ss_user_id():
        return None
    path = request.path or ""
    protected_prefixes = (
        "/api/health-profile", "/api/privacy/", "/api/family", "/api/safeid",
        "/api/meds/plan", "/api/meds/log", "/api/meds/snooze",
        "/api/meds/settings", "/api/handoff/", "/api/checkin",
        "/api/account/delete", "/api/chat-history/clear", "/api/user/preferences",
        "/api/analysis/", "/api/profile", "/api/analyze", "/api/blood",
        "/api/assistant/feedback", "/api/feedback", "/api/relief-log", "/api/smart-followup",
        "/api/followup/", "/api/vitals",
        "/api/v1/passkeys", "/api/v1/admin",
    )
    if path.startswith(protected_prefixes) and not _user_csrf_valid():
        return jsonify({"ok": False, "error": "csrf_failed"}), 403
    return None

_ADMIN_AUTH_CORE_LOCK = threading.Lock()
_ADMIN_AUTH_CORE_EVENT = threading.Event()
_ADMIN_AUTH_CORE_STATE = {"started": False, "ready": False, "error": None}

def _warm_admin_auth_core():
    """Prepare only the security tables required by Admin sign-in.

    V113 made optional schemas lazy for startup stability. Admin sign-in should
    not depend on the large optional platform_v2 schema, but it does need the
    small 2FA/session-control tables. Warm those independently and fail with a
    clear retry state instead of letting a login request hang or 500.
    """
    with _ADMIN_AUTH_CORE_LOCK:
        if _ADMIN_AUTH_CORE_STATE["ready"]:
            _ADMIN_AUTH_CORE_EVENT.set()
            return True
        if _ADMIN_AUTH_CORE_STATE["started"]:
            return False
        _ADMIN_AUTH_CORE_STATE["started"] = True
        _ADMIN_AUTH_CORE_STATE["error"] = None
    try:
        admin_2fa.init_schema()
        admin_security.init_schema()
        with _ADMIN_AUTH_CORE_LOCK:
            _ADMIN_AUTH_CORE_STATE["ready"] = True
        app.logger.info("ADMIN_AUTH core ready")
        return True
    except Exception as exc:
        with _ADMIN_AUTH_CORE_LOCK:
            _ADMIN_AUTH_CORE_STATE["error"] = type(exc).__name__
        app.logger.warning("ADMIN_AUTH core warmup failed error_type=%s", type(exc).__name__)
        return False
    finally:
        _ADMIN_AUTH_CORE_EVENT.set()

def _start_admin_auth_core_warmup_once():
    with _ADMIN_AUTH_CORE_LOCK:
        if _ADMIN_AUTH_CORE_STATE["ready"] or _ADMIN_AUTH_CORE_STATE["started"]:
            return
    threading.Thread(
        target=_warm_admin_auth_core,
        name="symptosense-admin-auth-core",
        daemon=True,
    ).start()

def _admin_auth_core_ready(wait_seconds=1.5):
    if _ADMIN_AUTH_CORE_STATE["ready"]:
        return True
    _start_admin_auth_core_warmup_once()
    try:
        _ADMIN_AUTH_CORE_EVENT.wait(max(0.0, float(wait_seconds)))
    except Exception:
        pass
    return bool(_ADMIN_AUTH_CORE_STATE["ready"])

def _record_login_telemetry_async(email, network_origin, user_id, success, is_admin, user_agent):
    """Observability must never be a hard dependency of authentication."""
    def _job():
        best_effort.call(platform_v2.record_login_attempt, email, network_origin, bool(success))
        best_effort.call(platform_v2.log_login, email, user_id, bool(success), bool(is_admin), user_agent)
    threading.Thread(target=_job, name="symptosense-login-telemetry", daemon=True).start()

def _admin_auth_debug(event, user=None, granted=None, redirect_target=None):
    """Temporary, non-sensitive Admin authentication diagnostics.

    Logs only authentication state, numeric user id, effective role, whether the
    account matches the configured owner, authorization result, and redirect.
    Passwords, tokens, email addresses, medical data, and request bodies are
    never logged here. Set ADMIN_AUTH_DEBUG=0 to disable after verification.
    """
    if os.environ.get("ADMIN_AUTH_DEBUG", "0") != "1":
        return
    try:
        u = user if isinstance(user, dict) else (_ss_user() if _ss_user_id() else None)
        app.logger.info(
            "ADMIN_AUTH event=%s authenticated=%s user_id=%s role=%s owner_match=%s admin_access=%s redirect=%s",
            str(event)[:40],
            bool(u),
            (u or {}).get("id"),
            (u or {}).get("role", "user"),
            bool(u and db.is_owner_admin_email(u.get("email"))),
            ("granted" if granted is True else "denied" if granted is False else "n/a"),
            (redirect_target or "-"),
        )
    except Exception:
        logging.getLogger(__name__).warning("Handled exception in _admin_auth_debug; fallback applied (handler 3832)")
        pass

def admin_api_required(scope="access"):
    """Protect every Admin API with server-side authentication, RBAC, and CSRF."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not _ss_user_id():
                _admin_auth_debug("admin_api", None, granted=False, redirect_target="401")
                return jsonify({"ok": False, "error": "login_required", "login_url": url_for("login", next="/admin")}), 401
            current_user = _ss_user()
            if not _admin_session_valid():
                if getattr(g, "admin_2fa_required", False):
                    session.clear()
                    return jsonify({"ok": False, "error": "admin_2fa_required", "login_url": url_for("login", next="/admin")}), 401
                if not _ss_user_id() and getattr(g, "admin_session_expired", False):
                    return jsonify({"ok": False, "error": "admin_session_expired", "login_url": url_for("login", next="/admin")}), 401
                _admin_auth_debug("admin_api", current_user, granted=False, redirect_target="403")
                return jsonify({"ok": False, "error": "forbidden"}), 403
            if not _admin_allowed(scope):
                _admin_auth_debug("admin_api", current_user, granted=False, redirect_target="403")
                return jsonify({"ok": False, "error": "forbidden"}), 403
            _admin_auth_debug("admin_api", current_user, granted=True, redirect_target=request.path)
            if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
                supplied = request.headers.get("X-CSRF-Token", "")
                expected = session.get("admin_csrf", "")
                if not expected or not secrets.compare_digest(supplied, expected):
                    return jsonify({"ok": False, "error": "csrf_failed"}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator

def _client_ip() -> str:
    """Return a validated client IP without trusting proxy headers locally.

    Railway supplies X-Real-IP at its trusted edge. Outside Railway we ignore
    that header so a direct client cannot spoof the rate-limit identity.
    """
    candidate = ""
    if _RAILWAY_RUNTIME:
        candidate = (request.headers.get("X-Real-IP") or "").strip()
    if not candidate:
        candidate = (request.remote_addr or "").strip()
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return "unknown"

def _request_rate_identity(extra: str = "") -> str:
    """Ephemeral identity string fed into a salted server-side rate-limit hash."""
    actor = f"user:{_ss_user_id()}" if _ss_user_id() else f"ip:{_client_ip()}"
    return actor + ("|" + str(extra)[:180] if extra else "")

_LOCAL_RATE_LIMIT = {}
_LOCAL_RATE_LIMIT_LOCK = threading.Lock()

def _local_request_allowed(scope: str, identity: str, max_requests: int, window_seconds: int) -> bool:
    """Process-local safety net when the shared limiter is unavailable.

    It is intentionally conservative for authentication endpoints. In a
    multi-worker deployment this is not a replacement for the shared limiter,
    but it prevents a database/limiter outage from becoming an unlimited login
    or password-reset endpoint.
    """
    now = time.monotonic()
    key = (str(scope), hashlib.sha256(str(identity).encode("utf-8")).hexdigest())
    cutoff = now - max(1, int(window_seconds))
    with _LOCAL_RATE_LIMIT_LOCK:
        recent = [ts for ts in _LOCAL_RATE_LIMIT.get(key, []) if ts >= cutoff]
        if len(recent) >= max(1, int(max_requests)):
            _LOCAL_RATE_LIMIT[key] = recent
            return False
        recent.append(now)
        _LOCAL_RATE_LIMIT[key] = recent
        # Bound memory even if callers generate many distinct identities.
        if len(_LOCAL_RATE_LIMIT) > 5000:
            stale = [k for k, values in _LOCAL_RATE_LIMIT.items() if not values or values[-1] < cutoff]
            for k in stale[:2500]:
                _LOCAL_RATE_LIMIT.pop(k, None)
        return True

def _request_allowed(scope: str, max_requests: int, window_seconds: int, extra: str = "") -> bool:
    identity = _request_rate_identity(extra)
    try:
        return platform_v2.request_allowed(scope, identity, max_requests, window_seconds)
    except Exception:
        logging.getLogger(__name__).warning("Shared rate limiter unavailable; using process-local fallback")
        return _local_request_allowed(scope, identity, max_requests, window_seconds)

def _bounded_env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    """Read an integer environment setting without letting bad deploy config cause a 500."""
    try:
        value = int(os.environ.get(name, str(default)) or default)
    except (TypeError, ValueError):
        value = int(default)
    return max(int(minimum), min(int(maximum), value))

def _login_pair_allowed(email: str, network_origin: str, scope: str) -> bool:
    """Per-account/network throttle with a fail-safe local fallback."""
    try:
        return platform_v2.login_attempt_allowed(email, network_origin)
    except Exception:
        logging.getLogger(__name__).warning("Login pair limiter unavailable; using process-local fallback")
        identity = f"{str(email).lower()[:254]}|{str(network_origin)[:180]}"
        return _local_request_allowed(scope + "_pair", identity, 10, 15 * 60)

def _rate_limited_response(lang=None):
    ar = (lang or _lang()) == "ar"
    return jsonify({"ok":False,"error":"طلبات كثيرة خلال فترة قصيرة. انتظر قليلًا ثم حاول مرة أخرى." if ar else "Too many requests in a short period. Please wait and try again.","error_code":"rate_limited"}),429

def _safe_next_url(default="/home"):
    """Accept only a normal same-origin path for post-auth redirects."""
    return web_security.safe_internal_path(request.args.get("next"), default)

def _csp_nonce():
    """Return one unpredictable CSP nonce for the current request."""
    nonce = getattr(g, "csp_nonce", "")
    if not nonce:
        nonce = secrets.token_urlsafe(18)
        g.csp_nonce = nonce
    return nonce

@app.before_request
def require_first_language_choice():
    """Keep first-time visitors on the neutral language picker before any page UI."""
    if request.method != "GET":
        return None
    # A canonical /ar/... or /en/... URL is itself an explicit language choice.
    if _path_lang(request.path):
        return None
    if request.cookies.get("lang") in {"ar", "en"} or request.args.get("lang") in {"ar", "en"}:
        return None
    path = request.path or "/"
    legacy_public = path in _PUBLIC_CANONICAL_MAP or path.startswith("/health-library/") or (path.startswith("/history/") and path[len("/history/"):].strip("/").isdigit())
    if legacy_public or _is_tokenized_auth_path(path):
        return None
    public_paths = {"/", "/manifest.webmanifest", "/manifest.json", "/safeid.webmanifest", "/service-worker.js", "/favicon.ico", "/offline", "/robots.txt", "/sitemap.xml", "/brand-icon.svg", "/health", "/healthz", "/ready", "/readyz"}
    if path in public_paths or path.startswith("/language/") or path.startswith("/api/") or path.startswith("/icons/") or path.startswith("/static/") or path.startswith("/assets/") or path.startswith("/share/health/") or path.startswith("/safeid/"):
        return None
    target = request.full_path.rstrip("?")
    return redirect(url_for("index", next=target))

@app.before_request
def redirect_legacy_public_urls():
    """301 legacy page URLs to one canonical language path.

    API/admin/assets/tokenized emergency routes intentionally stay unchanged.
    """
    if request.method not in {"GET", "HEAD"}:
        return None
    path = request.path or "/"
    requested_lang = request.args.get("lang") or request.args.get("set_lang")
    if path == "/" and requested_lang in _SUPPORTED_LANGS:
        clean = [(k, v) for k, v in request.args.items(multi=True) if k not in {"lang", "set_lang"}]
        target = f"/{requested_lang}/"
        if clean:
            target += "?" + urlencode(clean)
        return redirect(target, code=301)
    if path == "/" or _path_lang(path):
        # If an old ?lang= value is attached to a canonical path, move to the
        # corresponding language path without keeping the query parameter.
        current_lang = _path_lang(path)
        if current_lang and requested_lang in _SUPPORTED_LANGS and requested_lang != current_lang:
            suffix = _strip_lang_prefix(path)
            clean = [(k, v) for k, v in request.args.items(multi=True) if k not in {"lang", "set_lang"}]
            target = _localized_url(suffix, requested_lang)
            if clean:
                target += ("&" if "?" in target else "?") + urlencode(clean)
            return redirect(target, code=301)
        return None
    if path.startswith(("/api/", "/admin", "/static/", "/assets/", "/icons/", "/share/health/", "/safeid/")) or _is_tokenized_auth_path(path):
        return None

    dynamic_known = path.startswith("/health-library/") or (path.startswith("/history/") and path[len("/history/"):].strip("/").isdigit())
    if path not in _PUBLIC_CANONICAL_MAP and not dynamic_known:
        return None

    lang = request.args.get("lang") if request.args.get("lang") in _SUPPORTED_LANGS else request.cookies.get("lang")
    lang = lang if lang in _SUPPORTED_LANGS else "ar"
    suffix = _canonical_suffix(path)
    drop_keys = {"lang", "set_lang"}
    if path in _HEALTH_RECORD_TAB_MAP:
        drop_keys.add("tab")
    clean = [(k, v) for k, v in request.args.items(multi=True) if k not in drop_keys]
    if path == "/assistant" and not any(k == "assistant" for k, _ in clean):
        clean.insert(0, ("assistant", "general"))
    fragment = _MERGED_FRAGMENT_MAP.get(path, "")
    if path in _HEALTH_RECORD_TAB_MAP:
        clean.insert(0, ("tab", _HEALTH_RECORD_TAB_MAP[path]))
    target = _localized_url(suffix, lang)
    if clean:
        target += ("&" if "?" in target else "?") + urlencode(clean)
    if fragment:
        target += "#" + fragment
    return redirect(target, code=301)

_GZIP_STATIC_TYPES = {"text/css", "application/javascript", "text/javascript", "image/svg+xml", "application/json"}
_GZIP_CACHE: dict = {}


def _gzip_cached(path, raw):
    """gzip once per static file content (level 9); dynamic responses keep the cheaper level 5."""
    import gzip
    import zlib
    if not path.startswith("/static/"):
        return gzip.compress(raw, compresslevel=5)
    key = (path, len(raw), zlib.crc32(raw))
    packed = _GZIP_CACHE.get(key)
    if packed is None:
        if len(_GZIP_CACHE) > 256:
            _GZIP_CACHE.clear()
        packed = _GZIP_CACHE[key] = gzip.compress(raw, compresslevel=9)
    return packed


@app.after_request
def compress_large_text_responses(response):
    """Compress large text responses after all HTML/CSP mutators finish.

    The app shell is HTML-heavy. Gzip greatly reduces transfer size on mobile
    networks without changing application behavior. Streaming/file responses,
    already-compressed responses and tiny payloads are left untouched.
    """
    try:
        # Static files are served as file passthrough; read the small text ones so they can be gzipped too.
        if (
            response.direct_passthrough
            and response.status_code == 200
            and request.method == "GET"
            and request.path.startswith("/static/")
            and response.mimetype in _GZIP_STATIC_TYPES
            and (response.content_length or 0) < 2_000_000
        ):
            response.direct_passthrough = False
            response.get_data()
        if (
            request.method != "HEAD"
            and not response.direct_passthrough
            and response.status_code not in {204, 304}
            and "gzip" in (request.headers.get("Accept-Encoding") or "").lower()
            and not response.headers.get("Content-Encoding")
            and response.mimetype in {
                "text/html", "text/css", "application/javascript",
                "text/javascript", "application/json", "image/svg+xml",
            }
        ):
            raw = response.get_data()
            if len(raw) >= 1400:
                import gzip
                packed = _gzip_cached(request.path, raw)
                if len(packed) + 64 < len(raw):
                    response.set_data(packed)
                    response.headers["Content-Encoding"] = "gzip"
                    if response.headers.get("ETag") and not response.headers["ETag"].startswith("W/"):
                        response.headers["ETag"] = "W/" + response.headers["ETag"]  # representation differs from the identity body
                    vary = {x.strip() for x in (response.headers.get("Vary") or "").split(",") if x.strip()}
                    vary.add("Accept-Encoding")
                    response.headers["Vary"] = ", ".join(sorted(vary))
                    response.headers["Content-Length"] = str(len(packed))
    except Exception:
        app.logger.debug("Response compression skipped")
    return response

@app.after_request
def persist_explicit_language_selection(response):
    """Persist language from canonical paths or the legacy one-time query picker."""
    path_selected = _path_lang(request.path)
    query_selected = request.args.get("lang")
    selected = path_selected or (query_selected if query_selected in _SUPPORTED_LANGS else None)
    explicit_query = request.args.get("set_lang") == "1" and query_selected in _SUPPORTED_LANGS
    if selected in _SUPPORTED_LANGS and (request.cookies.get("lang") != selected or explicit_query):
        response.set_cookie(
            "lang", selected,
            max_age=365 * 24 * 60 * 60,
            path="/",
            secure=bool(app.config.get("SESSION_COOKIE_SECURE")),
            httponly=False,
            samesite="Lax",
        )
        if explicit_query:
            response.headers["Cache-Control"] = "no-store, max-age=0"
    return response

_ANALYTICS_QUEUE = queue.Queue(maxsize=2000)
_ANALYTICS_WORKER_STARTED = False
_ANALYTICS_WORKER_LOCK = threading.Lock()

def _operational_analytics_worker():
    while True:
        task = _ANALYTICS_QUEUE.get()
        try:
            if task is None:
                return
            event_type, path, lang, user_agent, status, elapsed, sid, journey_stage = task
            platform_v2.record_usage(event_type, path, lang, user_agent, status, elapsed)
            if sid:
                admin_operational.touch_session(sid, user_agent)
                if journey_stage:
                    admin_operational.record_journey(sid, journey_stage, user_agent)
        except Exception as exc:
            app.logger.debug("Async analytics write skipped: %s", type(exc).__name__)
        finally:
            _ANALYTICS_QUEUE.task_done()

def _start_operational_analytics_worker_once():
    global _ANALYTICS_WORKER_STARTED
    if _ANALYTICS_WORKER_STARTED:
        return
    with _ANALYTICS_WORKER_LOCK:
        if _ANALYTICS_WORKER_STARTED:
            return
        thread = threading.Thread(
            target=_operational_analytics_worker,
            name="symptosense-analytics-writer",
            daemon=True,
        )
        thread.start()
        _ANALYTICS_WORKER_STARTED = True

def _queue_operational_analytics(task):
    """Best-effort analytics must never delay a user-facing response."""
    try:
        _start_operational_analytics_worker_once()
        _ANALYTICS_QUEUE.put_nowait(task)
    except queue.Full:
        app.logger.debug("Analytics queue full; dropping optional event")
    except Exception:
        app.logger.debug("Analytics queue unavailable")

@app.before_request
def v2_request_timer():
    g.v2_started_at = time.perf_counter()
    if feature_flags.REQUEST_TRACING:
        request_tracing.begin_request()
    else:
        g.request_id = secrets.token_hex(8)

@app.after_request
def log_slow_requests(response):
    """Log slow routes without query strings or user/health content."""
    try:
        started = getattr(g, "v2_started_at", None)
        if started is not None:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            ops_metrics.observe(request.url_rule.rule if request.url_rule else "(unmatched)", int(response.status_code), elapsed_ms)
            threshold_ms = _bounded_env_int("SLOW_REQUEST_LOG_MS", 2500, 500, 60000)
            if elapsed_ms >= threshold_ms:
                app.logger.warning(
                    "SLOW_REQUEST method=%s path=%s status=%s elapsed_ms=%s",
                    request.method, request.path, int(response.status_code), elapsed_ms,
                )
    except Exception:
        pass
    return response

@app.before_request
def reject_cross_site_mutations():
    """Reject browser cross-site state-changing requests before route logic.

    CSRF tokens remain the primary protection for authenticated mutations. This
    browser-origin gate is defense in depth and also protects public POST APIs
    from being silently invoked by another website in a visitor's browser.
    Requests without browser Origin/Sec-Fetch metadata (for example local CLI
    health checks) are left to the route's normal authentication/rate limits.
    """
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    fetch_site = (request.headers.get("Sec-Fetch-Site") or "").strip().lower()
    if fetch_site == "cross-site":
        return jsonify({"ok": False, "error": "cross_site_request_blocked"}), 403
    origin = (request.headers.get("Origin") or "").strip()
    if not origin or origin == "null":
        return None
    try:
        parsed = urlsplit(origin)
        origin_host = parsed.netloc.lower()
        request_host = (request.host or "").lower()
        if not parsed.scheme or origin_host != request_host:
            return jsonify({"ok": False, "error": "origin_mismatch"}), 403
    except Exception:
        logging.getLogger(__name__).warning("Handled exception in reject_cross_site_mutations; fallback applied (handler 3938)")
        return jsonify({"ok": False, "error": "invalid_origin"}), 403
    return None

@app.after_request
def finalize_html_script_nonces(response):
    """Nonce every rendered script/style block after all response injectors ran.

    Flask executes after-request handlers in reverse registration order. This
    function is intentionally registered before the other response mutators so
    it runs last and also covers the one-time login toast.
    """
    try:
        if response.mimetype == "text/html" and not response.direct_passthrough:
            nonce = _csp_nonce()
            markup = response.get_data(as_text=True)
            markup = re.sub(
                r"<script(?![^>]*\bnonce=)([^>]*)>",
                lambda m: '<script nonce="' + nonce + '"' + m.group(1) + '>',
                markup,
                flags=re.IGNORECASE,
            )
            markup = re.sub(
                r"<style(?![^>]*\bnonce=)([^>]*)>",
                lambda m: '<style nonce="' + nonce + '"' + m.group(1) + '>',
                markup,
                flags=re.IGNORECASE,
            )
            response.set_data(markup)
    except Exception:
        app.logger.warning("Unable to finalize CSP nonces for HTML response")
    return response

@app.after_request
def v2_operational_metrics(response):
    """Record optional product analytics only after explicit analytics consent.

    Server logs still capture request failures for reliability/security, but product
    usage, page-view and journey telemetry are not persisted when Analytics is off.
    """
    try:
        path = request.path or "/"
        is_candidate = (
            response.status_code >= 400
            or (request.method == "POST" and (path == "/api/analyze" or path.startswith("/api/assistant")))
            or (request.method == "GET" and (path in {"/sources", "/medical-sources"} or (response.mimetype == "text/html" and not path.startswith("/admin"))))
        )
        if getattr(g, "symptosense_demo", False):
            return response
        if not is_candidate or not _analytics_consent_ok():
            return response
        event_type = None
        if response.status_code >= 400:
            event_type = "error"
        elif request.method == "POST" and path == "/api/analyze":
            event_type = "analysis_complete"
        elif request.method == "POST" and path.startswith("/api/assistant"):
            event_type = "assistant_use"
        elif request.method == "GET" and path in {"/sources","/medical-sources"}:
            event_type = "source_accessed"
        elif request.method == "GET" and response.mimetype == "text/html" and not path.startswith("/admin"):
            event_type = "page_view"
        if event_type:
            elapsed = round((time.perf_counter() - getattr(g, "v2_started_at", time.perf_counter())) * 1000)
            user_agent = request.headers.get("User-Agent", "")
            sid = None
            journey_stage = None
            if request.method == "GET" and response.status_code < 400 and response.mimetype == "text/html" and not path.startswith("/admin"):
                sid = _analytics_session_id()
                if path in {"/home", "/"}:
                    journey_stage = "home"
                elif path == "/chat":
                    journey_stage = "start_analysis"
            _queue_operational_analytics((
                event_type, path, _lang(), user_agent, response.status_code,
                elapsed, sid, journey_stage,
            ))
    except Exception as exc:
        app.logger.debug("Optional analytics recording skipped: %s", type(exc).__name__)
    return response

def _login_toast_markup(kind, lang):
    """Accessible, in-site login confirmation shown once per login event."""
    ar=lang=="ar"
    if kind=="admin":
        title="👑 أهلًا بك، ريماس" if ar else "👑 Welcome, Remas"
        message="تم تسجيل الدخول إلى لوحة التحكم بنجاح." if ar else "You signed in to the Admin Dashboard successfully."
    else:
        title="👋 أهلًا بك في SymptoSense" if ar else "👋 Welcome to SymptoSense"
        message="تم تسجيل الدخول بنجاح." if ar else "You signed in successfully."
    close_label="إغلاق الإشعار" if ar else "Close notification"
    return """
<style>
.ss-login-toast{position:fixed;z-index:2147483000;top:18px;inset-inline-end:18px;width:min(390px,calc(100vw - 28px));display:grid;grid-template-columns:38px 1fr auto;align-items:start;gap:10px;padding:14px 15px;background:#fff;border:1px solid #CFE5F4;border-inline-start:4px solid #1f6fae;border-radius:15px;box-shadow:0 16px 45px rgba(22,59,92,.16);color:#23384A;animation:ssToastIn .24s ease both}
.ss-login-toast .ss-toast-check{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;background:#EDF8F2;color:#267A52;font-weight:900}
.ss-login-toast strong{display:block;color:#163B5C;font-size:14px;line-height:1.45}.ss-login-toast p{margin:3px 0 0;color:#566a7d;font-size:13px;line-height:1.55}
.ss-login-toast button{border:0;background:transparent;color:#566a7d;font-size:19px;line-height:1;padding:5px;cursor:pointer;border-radius:8px}.ss-login-toast button:hover,.ss-login-toast button:focus-visible{background:#EAF5FC;color:#163B5C;outline:2px solid #1f6fae;outline-offset:1px}
.ss-login-toast.ss-toast-out{animation:ssToastOut .2s ease both}@keyframes ssToastIn{from{opacity:0;transform:translateY(-10px)}to{opacity:1;transform:none}}@keyframes ssToastOut{to{opacity:0;transform:translateY(-8px)}}
@media(max-width:600px){.ss-login-toast{top:10px;inset-inline:14px;width:auto}}@media(prefers-reduced-motion:reduce){.ss-login-toast,.ss-login-toast.ss-toast-out{animation:none}}
</style>
<div id="ssLoginToast" class="ss-login-toast" role="status" aria-live="polite" aria-atomic="true">
  <span class="ss-toast-check" aria-hidden="true">✓</span><div><strong>__TITLE__</strong><p>__MESSAGE__</p></div>
  <button type="button" aria-label="__CLOSE__" data-ss-click="ssCloseLoginToast">×</button>
</div>
<script>(function(){var done=false;window.ssCloseLoginToast=function(){if(done)return;done=true;var el=document.getElementById('ssLoginToast');if(!el)return;el.classList.add('ss-toast-out');window.setTimeout(function(){if(el&&el.parentNode)el.parentNode.removeChild(el);},230);};window.setTimeout(window.ssCloseLoginToast,4800);}());</script>
""".replace("__TITLE__",title).replace("__MESSAGE__",message).replace("__CLOSE__",close_label)

@app.after_request
def inject_login_success_toast(response):
    """Inject the pending login toast into the first successful HTML page only."""
    try:
        kind=session.get("login_toast")
        if request.path == "/":
            return response
        if not kind or response.status_code!=200 or response.mimetype!="text/html" or response.direct_passthrough:
            return response
        html=response.get_data(as_text=True)
        if "</body>" not in html.lower():
            return response
        marker=html.lower().rfind("</body>")
        html=html[:marker]+_login_toast_markup(kind,_lang())+html[marker:]
        response.set_data(html)
        session.pop("login_toast",None)
    except Exception:
        logging.getLogger(__name__).warning("Handled exception in inject_login_success_toast; fallback applied (handler 4027)")
        pass
    return response

@app.after_request
def request_trace_headers(response):
    if feature_flags.REQUEST_TRACING:
        return request_tracing.finish_response(response)
    return response

@app.after_request
def production_security_headers(response):
    """Apply browser hardening and prevent caching of health/account data."""
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), geolocation=(self), microphone=(self), payment=(), usb=(), browsing-topics=()")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
    response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
    response.headers.setdefault("X-DNS-Prefetch-Control", "off")
    response.headers.setdefault("Origin-Agent-Cluster", "?1")
    if app.config.get("SESSION_COOKIE_SECURE"):
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    nonce = _csp_nonce()
    csp = web_security.build_csp(secure_transport=bool(app.config.get("SESSION_COOKIE_SECURE")), nonce=nonce)
    response.headers.setdefault("Content-Security-Policy", csp)
    if os.environ.get("CSP_STRICT_REPORT_ONLY", "0").strip().lower() in {"1", "true", "yes", "on"}:
        response.headers.setdefault("Content-Security-Policy-Report-Only", web_security.build_strict_script_csp_report_only(nonce=nonce))
    response.headers.setdefault("X-Request-ID", getattr(g, "request_id", ""))

    path = request.path or "/"
    logical_path = _strip_lang_prefix(path)
    sensitive_prefixes = (
        "/admin", "/profile", "/history", "/health-record", "/health-file", "/meds", "/medications", "/family",
        "/privacy-center", "/consent", "/chat", "/mental", "/wellbeing", "/blood", "/checkin",
        "/safeid", "/manage", "/settings", "/health-command-center", "/health-file", "/vitals",
        "/login", "/register", "/verify", "/forgot-password", "/reset-password",
        "/api/", "/reports/", "/report/", "/export/", "/share/health/",
    )
    # Any authenticated HTML response may contain personalized/account data even
    # if its URL is not in the explicit list. Never store it in browser/proxy caches.
    is_sensitive = logical_path.startswith(sensitive_prefixes) or bool(_ss_user_id()) or response.mimetype in {
        "application/pdf", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    }
    if is_sensitive or path == "/":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0" if path == "/" else "private, no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        vary = {x.strip() for x in (response.headers.get("Vary") or "").split(",") if x.strip()}
        vary.add("Cookie")
        response.headers["Vary"] = ", ".join(sorted(vary))
        private_index_prefixes = (
            "/admin", "/profile", "/history", "/family", "/settings", "/checkin",
            "/login", "/register", "/verify", "/forgot-password", "/reset-password",
            "/share/health/", "/reports/", "/report/", "/export/",
        )
        if response.mimetype == "text/html" and (bool(_ss_user_id()) or logical_path.startswith(private_index_prefixes)):
            response.headers.setdefault("X-Robots-Tag", "noindex, nofollow, noarchive")
    if logical_path.startswith("/health-library/"):
        # SEO-only: detail pages stay usable inside SymptoSense but should not
        # appear as standalone Google results. Keep crawling allowed so Google
        # can see this noindex directive and follow internal links.
        response.headers["X-Robots-Tag"] = "noindex, follow, noarchive"
    if path.startswith("/share/health/"):
        # Public-by-token health summaries must not be cached, indexed, or leak
        # their token through the Referer header when a user follows a link.
        response.headers["Cache-Control"] = "private, no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        response.headers["Referrer-Policy"] = "no-referrer"
    # Static presentation assets are versioned or content-addressed and safe to
    # cache aggressively. This removes repeated network waits between pages.
    if path.startswith("/static/") or path.startswith("/assets/") or path.startswith("/icons/") or path in {"/favicon.ico", "/brand-icon.svg"}:
        # Only URLs carrying a ?v= cache-buster may be immutable for a year; an
        # unversioned icon/static URL could never be refreshed once cached.
        if request.args.get("v"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "public, max-age=604800"
        response.headers.pop("Pragma", None)
        response.headers.pop("Expires", None)
    if path == "/":
        response.headers["X-SymptoSense-Landing"] = "bare-v8"
    if path == "/logout":
        # Clear the browser HTTP cache after sign-out without deleting local
        # storage/PWA data or notification subscriptions.
        response.headers.setdefault("Clear-Site-Data", '"cache"')
    return response

@app.errorhandler(413)
def request_entity_too_large(_error):
    ar = _lang() == "ar"
    message = "حجم الملف أكبر من الحد المسموح (15 MB)." if ar else "The file is larger than the 15 MB limit."
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": message, "error_code": "file_too_large"}), 413
    body = (
        '<main style="max-width:620px;margin:8vh auto;text-align:center;background:#fff;'
        'border:1px solid var(--v2-line);border-radius:22px;padding:36px">'
        '<div style="font-size:52px">📄</div><h1>%s</h1><p class="muted">%s</p>'
        '<a class="btn primary" href="/blood">%s</a></main>'
    ) % (
        "الملف كبير جدًا" if ar else "File too large",
        html_lib.escape(message),
        "العودة لتحليل CBC" if ar else "Back to CBC analysis",
    )
    return _page("413", body), 413

@app.errorhandler(404)
def not_found_page(_error):
    ar = _lang() == "ar"
    body = """
    <main style="max-width:620px;margin:8vh auto;text-align:center;background:#fff;border:1px solid var(--v2-line);border-radius:22px;padding:36px">
      <div style="font-size:52px">🔎</div><h1>__TITLE__</h1><p class="muted">__TEXT__</p><a class="btn primary" href="/home">__BACK__</a>
    </main>"""
    body = body.replace("__TITLE__", "الصفحة غير موجودة" if ar else "Page not found").replace("__TEXT__", "تحقق من الرابط أو عد إلى الصفحة الرئيسية." if ar else "Check the address or return to the home page.").replace("__BACK__", "العودة للرئيسية" if ar else "Back to Home")
    return _page("404", body), 404

_HTTP_ERROR_COPY = {
    403: ("🔒", "غير مسموح", "Access denied", "ليست لديك صلاحية لفتح هذه الصفحة. سجّل الدخول بالحساب المناسب أو عد للرئيسية.", "You don't have permission to open this page. Sign in with the right account or go back home."),
    405: ("🧭", "طريقة الطلب غير مدعومة", "Request not supported", "هذا الرابط لا يقبل هذا النوع من الطلبات. عد للرئيسية وحاول مرة أخرى.", "This link doesn't accept that kind of request. Go back home and try again."),
    429: ("⏳", "محاولات كثيرة", "Too many attempts", "أرسلت طلبات كثيرة خلال وقت قصير. انتظر دقيقة ثم حاول مرة أخرى.", "You sent many requests in a short time. Wait a minute and try again."),
}


def _http_error_page(error):
    code = getattr(error, "code", 500)
    icon, title_ar, title_en, text_ar, text_en = _HTTP_ERROR_COPY.get(code, _HTTP_ERROR_COPY[403])
    ar = _lang() == "ar"
    if request.path.startswith("/api/"):
        resp = jsonify({"ok": False, "error": text_ar if ar else text_en, "code": code})
        resp.status_code = code
        if code == 429:
            resp.headers["Retry-After"] = "60"
        return resp
    body = (
        '<main style="max-width:620px;margin:8vh auto;text-align:center;background:#fff;border:1px solid var(--v2-line);border-radius:22px;padding:36px">'
        '<div style="font-size:52px" aria-hidden="true">%s</div><h1>%s</h1><p class="muted">%s</p><a class="btn primary" href="/home">%s</a></main>'
    ) % (icon, title_ar if ar else title_en, text_ar if ar else text_en, "العودة للرئيسية" if ar else "Back to home")
    resp = make_response(_page(str(code), body), code)
    if code == 429:
        resp.headers["Retry-After"] = "60"
    return resp


for _code in _HTTP_ERROR_COPY:
    app.register_error_handler(_code, _http_error_page)


@app.errorhandler(500)
def internal_error_page(_error):
    ar = _lang() == "ar"; request_id = getattr(g, "request_id", "")
    app.logger.error("Unhandled request failure; request_id=%s route=%s", request_id, request.path)
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "تعذر إكمال الطلب حاليًا." if ar else "Unable to complete the request right now.", "request_id": request_id}), 500
    body = """
    <main style="max-width:620px;margin:8vh auto;text-align:center;background:#fff;border:1px solid var(--v2-line);border-radius:22px;padding:36px">
      <div style="font-size:52px">⚠️</div><h1>__TITLE__</h1><p class="muted">__TEXT__</p><p class="muted">Request ID: __RID__</p><a class="btn primary" href="/home">__BACK__</a>
    </main>"""
    body = body.replace("__TITLE__", "حدث خطأ" if ar else "Something went wrong").replace("__TEXT__", "تعذر تحميل الصفحة حاليًا. حاول مرة أخرى." if ar else "We couldn't load this page right now. Please try again.").replace("__RID__", html_lib.escape(str(request_id or ""), quote=True)).replace("__BACK__", "العودة للرئيسية" if ar else "Back to Home")
    return _page("500", body), 500

def _site_url():
    """Return the canonical public URL used in transactional email links.

    Prefer an explicit SITE_URL, then Railway's own public-domain variable,
    then the active HTTPS request host.  Never fall back to a stale hard-coded
    project hostname because that makes verification/reset emails look valid
    while sending users to the wrong deployment.
    """
    explicit = web_security.normalize_public_base_url(os.environ.get("SITE_URL", ""))
    if explicit:
        return explicit
    railway = web_security.normalize_public_base_url(os.environ.get("RAILWAY_PUBLIC_DOMAIN", ""))
    if railway:
        return railway
    if has_request_context():
        try:
            current = web_security.normalize_public_base_url(request.url_root)
            if current:
                return current
        except Exception:
            logging.getLogger(__name__).warning("Handled exception in _site_url; fallback applied (handler 4128)")
            pass
    # Local/offline fallback only. Production on Railway always exposes
    # RAILWAY_PUBLIC_DOMAIN, and custom domains should be set via SITE_URL.
    return "http://localhost:8080"

_SUPPORTED_LANGS = {"ar", "en"}
_TOKENIZED_AUTH_PREFIXES = ("/reset-password/", "/verify-email/")

def _is_tokenized_auth_path(path=None):
    """Return True only for one-time authentication links that carry a token.

    These URLs must bypass the first-visit language picker. Otherwise a user
    opening an email link in a fresh browser can be redirected to /ar/... or
    /en/... and lose the dedicated token route, producing a 404 page.
    """
    value = str(path if path is not None else (request.path if has_request_context() else ""))
    for prefix in _TOKENIZED_AUTH_PREFIXES:
        if value.startswith(prefix):
            token = value[len(prefix):].strip("/")
            return bool(token and "/" not in token)
    return False

def _transactional_auth_url(kind, token, lang=None):
    """Build a public one-time auth URL without relying on prior cookies.

    The language is carried in the query string rather than inserted into the
    route path so the token endpoint remains canonical and works in a new
    browser/device.
    """
    kind = str(kind or "").strip("/")
    if kind not in {"reset-password", "verify-email"}:
        raise ValueError("unsupported_auth_link_kind")
    safe_lang = lang if lang in _SUPPORTED_LANGS else (_lang() if has_request_context() else "ar")
    safe_token = quote(str(token or ""), safe="-._~")
    return "%s/%s/%s?%s" % (
        _site_url().rstrip("/"), kind, safe_token,
        urlencode({"lang": safe_lang, "set_lang": "1"}),
    )

# Canonical public information architecture. Old URLs remain as 301 redirects
# so bookmarks keep working without creating duplicate search-engine entries.
_PUBLIC_CANONICAL_MAP = {
    "/home": "/",
    # Legacy symptom-analysis bookmarks used /symptoms. Keep them working and
    # canonicalize them to the current /chat flow instead of returning a 404.
    "/symptoms": "/chat",
    "/chat": "/chat",
    "/blood": "/blood",
    "/assistant": "/",
    "/search": "/search",
    "/calculators": "/calculators",
    "/meds": "/meds",
    "/emergency": "/emergency",
    "/firstaid": "/firstaid",
    "/tips": "/tips",
    "/relax": "/relax",
    "/health-library": "/health-library",
    "/health-trends": "/health-trends",
    "/community-dashboard": "/community-dashboard",
    "/about": "/about",
    "/about-us": "/about",
    "/site-info": "/about",
    "/trust": "/how-we-work",
    "/methodology": "/how-we-work",
    "/sources": "/how-we-work",
    "/privacy": "/privacy",
    "/privacy-center": "/privacy-center",
    "/consent": "/consent",
    "/how-we-work": "/how-we-work",
    "/health-record": "/health-record",
    "/health-file": "/health-file",
    "/vitals": "/vitals",
    "/terms": "/terms",
    "/profile": "/profile",
    "/family": "/family",
    "/checkin": "/checkin",
    "/safeid": "/safeid",
    "/settings": "/settings",
    "/manage": "/manage",
    "/memory": "/memory",
    "/login": "/login",
    "/register": "/register",
    "/verify-email": "/verify-email",
    "/forgot-password": "/forgot-password",
    "/command-center": "/health-command-center",
    "/health-command-center": "/health-command-center",
    "/health-story": "/health-record",
    "/history": "/health-record",
    "/my-results": "/health-record",
    "/health-report": "/health-record",
    "/health-insights": "/health-record",
    "/health-journey": "/health-record",
    "/health-twin": "/health-record",
}

_MERGED_FRAGMENT_MAP = {
    "/trust": "trust",
    "/methodology": "methodology",
    "/sources": "sources",
}

_HEALTH_RECORD_TAB_MAP = {
    "/history": "results",
    "/my-results": "results",
    "/health-report": "results",
    "/health-insights": "insights",
    "/health-journey": "timeline",
    "/health-twin": "twin",
    "/health-story": "timeline",
}

def _path_lang(path=None):
    path = str(path if path is not None else (request.path if has_request_context() else ""))
    parts = path.split("/", 2)
    if len(parts) >= 2 and parts[1] in _SUPPORTED_LANGS:
        return parts[1]
    return None

def _strip_lang_prefix(path=None):
    path = str(path if path is not None else (request.path if has_request_context() else "/")) or "/"
    lang = _path_lang(path)
    if not lang:
        return path
    prefix = "/" + lang
    rest = path[len(prefix):]
    return rest or "/"

def _lang():
    # /ar/... and /en/... are the canonical language signal. Legacy ?lang=
    # remains accepted only for old bookmarks and is redirected to the path form.
    path_lang = _path_lang()
    if path_lang:
        return path_lang
    lang = request.args.get("lang") or request.cookies.get("lang")
    return "en" if lang == "en" else "ar"

def _canonical_suffix(path):
    """Map one legacy page path to the canonical language-neutral suffix."""
    path = str(path or "/")
    path = _strip_lang_prefix(path)
    if path.startswith("/history/"):
        tail = path[len("/history/"):].strip("/")
        if tail.isdigit():
            return "/health-record/" + tail
    if path.startswith("/health-library/"):
        return path
    return _PUBLIC_CANONICAL_MAP.get(path, path)

def _localized_url(path="/", lang=None):
    """Return the canonical /ar/... or /en/... URL for a site page."""
    lang = lang if lang in _SUPPORTED_LANGS else _lang()
    parsed = urlsplit(str(path or "/"))
    suffix = _canonical_suffix(parsed.path or "/")
    if suffix == "/":
        target = f"/{lang}/"
    else:
        target = f"/{lang}{suffix}"
    if parsed.query:
        target += "?" + parsed.query
    if parsed.fragment:
        target += "#" + parsed.fragment
    return target

def _localized_target_from_legacy(raw_target, lang):
    parsed = urlsplit(str(raw_target or "/home"))
    # One-time authentication routes are intentionally language-neutral paths.
    # Preserve them and carry the requested language in the query instead of
    # converting /reset-password/<token> into /ar/reset-password/<token>.
    if _is_tokenized_auth_path(parsed.path):
        try:
            from urllib.parse import parse_qsl
            query_items = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k not in {"lang", "set_lang"}]
        except Exception:
            query_items = []
        query_items.extend([("lang", lang if lang in _SUPPORTED_LANGS else "ar"), ("set_lang", "1")])
        target = parsed.path
        if query_items:
            target += "?" + urlencode(query_items)
        if parsed.fragment:
            target += "#" + parsed.fragment
        return target
    suffix = _canonical_suffix(parsed.path or "/home")
    query_items = []
    try:
        from urllib.parse import parse_qsl
        query_items = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k not in {"lang", "set_lang"}]
    except Exception:
        query_items = []
    if parsed.path == "/assistant" and not any(k == "assistant" for k, _ in query_items):
        query_items.insert(0, ("assistant", "general"))
    target = _localized_url(suffix, lang)
    if query_items:
        target += ("&" if "?" in target else "?") + urlencode(query_items)
    if parsed.fragment:
        target += "#" + parsed.fragment
    return target

def _localize_html_links(markup, lang):
    """Rewrite only known user-facing root-relative links; APIs/assets stay untouched."""
    if not markup or lang not in _SUPPORTED_LANGS:
        return markup
    def rewrite_url(raw):
        if not raw.startswith("/") or raw.startswith(("/api/", "/admin", "/static/", "/assets/", "/icons/", "/share/", "/safeid/", "/ar/", "/en/")):
            return raw
        parsed = urlsplit(raw)
        path = parsed.path or "/"
        fragment = parsed.fragment
        extra_query = parsed.query
        if path == "/assistant" and not extra_query:
            extra_query = "assistant=general"
        if path in _MERGED_FRAGMENT_MAP:
            fragment = _MERGED_FRAGMENT_MAP[path]
        if path in _HEALTH_RECORD_TAB_MAP:
            tab = _HEALTH_RECORD_TAB_MAP[path]
            query_pairs = [("tab", tab)]
            if extra_query:
                from urllib.parse import parse_qsl
                query_pairs.extend((k, v) for k, v in parse_qsl(extra_query, keep_blank_values=True) if k != "tab")
            extra_query = urlencode(query_pairs)
        known = path in _PUBLIC_CANONICAL_MAP or path.startswith("/history/") or path.startswith("/health-library/")
        if not known:
            return raw
        target = _localized_url(path, lang)
        # _localized_url carries the original query/fragment, so rebuild from path
        # when merge-specific query/fragment rules apply.
        base_target = _localized_url(urlsplit(path).path, lang)
        if extra_query:
            base_target += "?" + extra_query
        if fragment:
            base_target += "#" + fragment
        return base_target
    pattern = re.compile(r'(?P<attr>\bhref)=(?P<q>["\'])(?P<url>/[^"\']*)(?P=q)', re.IGNORECASE)
    return pattern.sub(lambda m: f'{m.group("attr")}={m.group("q")}{html_lib.escape(rewrite_url(html_lib.unescape(m.group("url"))), quote=True)}{m.group("q")}', markup)

L = inline_assets.data("L.json")

def _t(key):
    d = L.get(_lang(), L["ar"])
    return d.get(key, L["ar"].get(key, key))

def _nav():
    from html import escape
    lang = _lang()
    path = _strip_lang_prefix(request.path)
    user = _ss_user()
    ar = lang == "ar"
    links = [
        ("/home", "الرئيسية" if ar else "Home"),
        ("/chat", "تحليل الأعراض" if ar else "Symptom analysis"),
    ]
    if user:
        links.append(("/profile", "الملف الشخصي" if ar else "Profile"))
    html = '<nav class="nav"><a href="/home" class="logo" dir="ltr"><img class="ss-nav-logo-mark" src="/brand-icon.svg" width="29" height="29" alt="" aria-hidden="true"><span class="ss-brand-gradient">SymptoSense</span></a><div class="links">'
    for href, label in links:
        cls = ' class="on"' if (path == href or (href == "/home" and path == "/")) else ""
        html += '<a href="%s"%s>%s</a>' % (href, cls, label)
    html += '<a href="/home?assistant=general" class="v2-nav-cta" data-ss-click="openAsstGeneral" data-ss-prevent>🤖 %s</a>' % ("المساعد الذكي" if ar else "AI assistant")
    html += ('<div class="dd"><button type="button" class="dd-btn v2-services-btn" aria-haspopup="menu" aria-expanded="false" data-dd-toggle="1" data-ss-click="toggleDD" data-ss-args="[&quot;$event&quot;]">%s <span aria-hidden="true">⌄</span></button>'
             '<div class="dd-menu v2-services-menu" role="menu">'
             '<a href="/blood">🧪 %s</a><a href="/meds">💊 %s</a><a href="/calculators">🧮 %s</a>'
             '<a href="/search">🔎 %s</a><a href="/how-we-work#sources">📚 %s</a><a href="/family">👨‍👩‍👧 %s</a>'
             '<a href="/tips">💡 %s</a><a href="/emergency">🚑 %s</a><a href="/about">ℹ️ %s</a>'
             '</div></div>') % (
                 "الخدمات" if ar else "Services", "تحليل التحاليل" if ar else "Lab analysis",
                 "الأدوية" if ar else "Medicines", "الحاسبات الصحية" if ar else "Health calculators",
                 "البحث الصحي" if ar else "Health search", "المصادر الطبية" if ar else "Medical sources",
                 "العائلة" if ar else "Family", "نصائح صحية" if ar else "Health tips",
                 "الطوارئ" if ar else "Emergency", "عن المنصة" if ar else "About",
             )
    html += '</div>'
    html += '<div style="display:flex;align-items:center;gap:8px;">'
    if user:
        user_name = escape(user.get("name") or _t("nav_profile"))
        user_email = escape(user.get("email") or "")
        profile_label = "ملفي الشخصي" if lang == "ar" else "My profile"
        health_label = "بياناتي الصحية" if lang == "ar" else "My health information"
        family_label = "ملفات العائلة" if lang == "ar" else "Family profiles"
        admin_menu_link = ('<a href="/admin" role="menuitem">⚙️ %s</a>' % ("لوحة الإدارة" if lang == "ar" else "Admin Dashboard")) if user.get("role") == "admin" else ""
        html += ('<details class="dd account-dd account-native">'
                 '<summary class="account-menu-summary" aria-label="%s">'
                 '<span class="account-avatar" aria-hidden="true">👤</span>'
                 '<span class="account-btn-copy"><span class="account-name">%s</span><span class="account-label">%s</span></span>'
                 '<span class="account-menu-arrow" aria-hidden="true">▼</span>'
                 '</summary>'
                 '<div class="dd-menu account-menu" role="menu">'
                 '<div class="account-menu-head"><span class="account-avatar" aria-hidden="true">👤</span><div><strong>%s</strong><small>%s</small></div></div>'
                 '<a href="/profile" role="menuitem">👤 %s</a>'
                 '<a href="/manage" role="menuitem">📝 %s</a>'
                 '<a href="/health-command-center" role="menuitem">✨ %s</a><a href="/health-record" role="menuitem">📋 %s</a>'
                 '<a href="/family" role="menuitem">👨‍👩‍👧 %s</a>'
                 '<a href="/settings" role="menuitem">⚙️ %s</a>'
                 '<a href="/passkeys" role="menuitem">🔐 %s</a>'
                 '%s'
                 '<a href="/logout" role="menuitem" class="account-logout">🚪 %s</a>'
                 '</div></details>') % (
            ("خيارات الحساب" if lang == "ar" else "Account options"),
            user_name, profile_label,
            user_name, user_email, profile_label, health_label,
            ("مركز صحتي" if lang == "ar" else "Health Command Center"),
            ("سجلي الصحي" if lang == "ar" else "My Health Record"),
            family_label, _t("nav_privacy"),
            ("مفاتيح المرور" if lang == "ar" else "Passkeys"),
            admin_menu_link, _t("nav_logout"),
        )
    else:
        html += '<a href="/profile" class="dd-btn" style="text-decoration:none;">👤 %s</a>' % ("ملفي" if ar else "My profile")
    lang_picker_href = "/?choose=1&amp;next=" + escape(path)
    desktop_lang_label = "🌐 اختيار اللغة" if lang == "ar" else "🌐 Choose language"
    html += '<div class="lang-sw"><a href="%s" class="on">%s</a></div>' % (lang_picker_href, desktop_lang_label)
    html += '</div></nav>'
    if user:
        short_name = (user.get("name") or ("ملفي" if lang == "ar" else "Profile")).strip().split()[0]
        mobile_account_label = escape(short_name)
        mobile_account_href = "/profile"
        mobile_account_aria = "فتح الملف الشخصي" if lang == "ar" else "Open my profile"
    else:
        mobile_account_label = "دخول" if lang == "ar" else "Sign in"
        mobile_account_href = "/login?next=/profile"
        mobile_account_aria = "تسجيل الدخول" if lang == "ar" else "Sign in"
    lang_label = "اللغة" if lang == "ar" else "Language"
    lang_aria = "اختيار لغة الموقع" if lang == "ar" else "Choose site language"
    mobile_admin = '<a class="ss-mobile-lang" href="/admin" aria-label="Admin Dashboard"><span aria-hidden="true">⚙️</span><span>Admin</span></a>' if user and user.get("role") == "admin" else ""
    html += (
        '<header class="ss-mobile-head">'
        '<a href="/home" class="ss-mobile-logo" dir="ltr" aria-label="SymptoSense home">'
        '<img class="ss-nav-logo-mark" src="/brand-icon.svg" width="24" height="24" alt="" aria-hidden="true"><b class="ss-brand-gradient">SymptoSense</b></a>'
        '<div class="ss-mobile-actions">'
        '<a class="ss-mobile-lang" href="%s" aria-label="%s"><span aria-hidden="true">🌐</span><span>%s</span></a>'
        '%s'
        '<a class="ss-mobile-account" href="%s" aria-label="%s"><span aria-hidden="true">👤</span><span>%s</span></a>'
        '</div></header>'
    ) % (lang_picker_href, lang_aria, lang_label, mobile_admin, mobile_account_href, mobile_account_aria, mobile_account_label)
    return html

def _footer():
    tg = "https://t.me/" + CONTACT_TELEGRAM if CONTACT_TELEGRAM else "#"
    return (
        '<div class="footer" id="contact"><div class="f-inner">'
        '<a class="f-brand" href="/home" aria-label="SymptoSense"><img class="f-logo" src="/brand-icon.svg" width="40" height="40" alt="" aria-hidden="true" decoding="async" loading="lazy"><span class="ss-brand-gradient">SymptoSense</span></a>'
        '<p class="f-tag">%s</p>'
        '<div class="f-grid">'
        '<div class="f-sec"><h4>%s</h4><p>%s</p></div>'
        '<div class="f-sec"><h4>%s</h4><a href="/about" class="f-owner">%s<br>%s</a></div>'
        '<div class="f-sec"><h4>%s</h4>'
        '<a class="f-tg" href="%s" target="_blank" rel="noopener">%s</a>'
        '</div>'
        '</div>'
        '<div class="f-links">'
        '<a href="/privacy">%s</a>'
        '<a href="/terms">%s</a>'
        '<a href="/sources">%s</a>'
        '%s'
        '</div>'
        '<hr class="f-sep" aria-hidden="true"><p class="f-love"><span>%s</span> <b>%s</b></p>'
        '<p class="f-copy">%s</p>'
        '</div></div>'
    ) % (_t("footer_slogan"),
         _t("footer_synopsis_t"), _t("footer_synopsis_d"),
         _t("footer_owner_t"), _t("footer_owner_name"), _t("footer_owner_role"),
         _t("footer_contact_t"), tg, _t("footer_wa_btn"),
         _t("footer_privacy"), _t("footer_terms"),
         ("المصادر الطبية" if _lang() == "ar" else "Medical sources"),
         ('<a href="/admin">%s</a>' % _t("nav_admin")) if (_ss_user() or {}).get("role") == "admin" else "",
         _t("footer_love"), _t("footer_love_name"),
         _t("footer_copy_full"))


PREMIUM_POLISH_CSS += inline_assets.text("PREMIUM_POLISH_CSS_12.css")


PREMIUM_POLISH_CSS += r"""
/* ===== V69 final whole-site size, shape, controls, and typography audit ===== */
/* Controls: consistent touch size without inflating small explanatory text. */
button,.btn,.opt,.auth-btn,.ss-btn,.ss-btn-primary,.ss-btn-danger,.ss-report-action,.ss-feedback-btn,.ss-feedback-submit,.doctor-card-close,.symptom-path-next,.symptom-path-skip,.w-menu-btn,.sea-btn,.retry{min-height:44px!important}
.doctor-card-close,.w-menu-btn{min-width:44px!important;width:44px!important;height:44px!important}
input:not([type="checkbox"]):not([type="radio"]):not([type="range"]),select,textarea{min-height:44px}
/* Primary surfaces use one geometry; nested chips remain pills by design. */
.card,.ss-card,.ss-report-card,.sea-result,.sea-topic-card,.calc-card,.trust-simple-card,.manage-card,.memory-card,.ss-profile-card{border-radius:16px!important}
input:not([type="checkbox"]):not([type="radio"]):not([type="range"]),select,textarea,.btn,.opt,.auth-btn,.ss-btn,.ss-report-action{border-radius:12px!important}
/* Readability floors for real UI copy on compact screens. */
@media(max-width:767px){
  body.ss-home-page .ss-hero-kicker{font-size:10.5px!important}
  body.ss-home-page .ss-trust-row{font-size:10.5px!important}
  body.ss-home-page .ss-tool small{font-size:10.5px!important;line-height:1.45!important}
  body.ss-home-page .ss-how-step small{font-size:10.5px!important;line-height:1.5!important}
  body.ss-home-page .ss-source-badge{font-size:10px!important}
  .ss-bnav a{font-size:9.8px!important;line-height:1.2!important}
  .symptom-path-node b{font-size:10.5px!important}.symptom-path-node small{font-size:10px!important}
}
@media(max-width:390px){
  .ss-bnav a{font-size:9.5px!important}
  body.ss-home-page .ss-hero-kicker{font-size:10px!important}
}
@media(max-width:340px){
  .ss-bnav a{font-size:9.5px!important}
  body.ss-home-page .ss-hero-kicker{font-size:10px!important}
}
/* The answer-impact copy intentionally stays compact, but never unreadable. */
.followup-impact-title{font-size:10.5px!important}.followup-impact-answer{font-size:10.3px!important}.followup-impact-detail{font-size:10.5px!important}.followup-impact-note{font-size:9.6px!important}
/* Keep cards visually quiet and consistent instead of mixing large shadow styles. */
.ss-report-card,.card,.ss-card,.sea-result,.sea-topic-card,.calc-card{box-shadow:0 5px 18px rgba(31,86,127,.055)!important}
/* Modal sizing stays inside the viewport on all small devices. */
.doctor-card,.ss-modal,.expl-modal,.asst-modal{max-width:calc(100vw - 20px)!important}
@media(max-width:430px){.doctor-card,.ss-modal,.expl-modal,.asst-modal{max-width:calc(100vw - 12px)!important}.doctor-card-overlay,.ss-modal-overlay,.expl-bg,.asst-modal-bg{padding:6px!important}}
"""


PREMIUM_POLISH_CSS += inline_assets.text("PREMIUM_POLISH_CSS_13.css")

PREMIUM_POLISH_CSS += inline_assets.text("PREMIUM_POLISH_CSS_14.css")


PREMIUM_POLISH_CSS += inline_assets.text("PREMIUM_POLISH_CSS_15.css")


PREMIUM_POLISH_CSS += inline_assets.text("PREMIUM_POLISH_CSS_16.css")

PREMIUM_POLISH_CSS += inline_assets.text("PREMIUM_POLISH_CSS_17.css")

import polish_css_v249
PREMIUM_POLISH_CSS += polish_css_v249.CSS

@app.route("/assets/app-shell-v112.css")
def app_shell_v112_css():
    """Serve shared UI CSS from application memory.

    This keeps the V111 caching/performance benefit without depending on a
    newly-added static file being copied by every deployment path.
    """
    css = BASE_CSS + V2_CSS + PREMIUM_POLISH_CSS
    response = Response(css, mimetype="text/css")
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.set_etag("symptosense-app-shell-v112-v272")
    return response

def _page(title, body, desc=None, bare=False, extra_css=""):
    # SEO-only metadata for Google/search/social previews.
    # This does NOT change any visible text, buttons, layout, or page body.
    lang = _lang()
    seo_core = {
        "/": {
            "ar": (
                "SymptoSense | افهم أعراضك واعرف خطوتك التالية",
                "منصة صحية رقمية تساعدك على فهم الأعراض وقراءة نتائج التحاليل بشكل أوضح، مع تنبيهات علامات الخطر ومصادر طبية موثوقة.",
            ),
            "en": (
                "SymptoSense | Understand your symptoms and know your next step",
                "A digital health platform that helps you understand symptoms and blood test results more clearly, with red-flag guidance and trusted medical sources.",
            ),
        },
        "/home": {
            "ar": (
                "SymptoSense | افهم أعراضك واعرف خطوتك التالية",
                "منصة صحية رقمية تساعدك على فهم الأعراض وقراءة نتائج التحاليل بشكل أوضح، مع تنبيهات علامات الخطر ومصادر طبية موثوقة.",
            ),
            "en": (
                "SymptoSense | Understand your symptoms and know your next step",
                "A digital health platform that helps you understand symptoms and blood test results more clearly, with red-flag guidance and trusted medical sources.",
            ),
        },
        "/chat": {
            "ar": (
                "تحليل الأعراض | من العرض إلى الخطوة التالية",
                "ابدأ بالعرض الذي تشعر به، وأجب عن أسئلة متابعة تساعد على توضيح حالتك ومعرفة ما يستدعي الانتباه أو المراجعة الطبية.",
            ),
            "en": (
                "Symptom Analysis | From symptom to the next step",
                "Start with what you feel and answer focused follow-up questions to better understand your symptoms, warning signs, and when medical review may be appropriate.",
            ),
        },
        "/blood": {
            "ar": (
                "تحليل الدم | افهم أرقام تحليلك بوضوح",
                "افهم نتائج تحليل الدم والقيم الخارجة عن نطاق مختبرك بلغة مبسطة، مع تنبيهات ومصادر طبية موثوقة دون تشخيص.",
            ),
            "en": (
                "Blood Test Analysis | Understand your results clearly",
                "Understand blood-test results and values outside your laboratory range in plain language, with safety guidance and trusted medical sources without diagnosis.",
            ),
        },
        "/privacy": {"ar": ("سياسة الخصوصية | SymptoSense", "تعرّف على كيفية جمع SymptoSense للبيانات واستخدامها وحمايتها وحقوقك المتعلقة بالخصوصية."), "en": ("Privacy Policy | SymptoSense", "Learn how SymptoSense collects, uses, protects, and manages your data and privacy choices.")},
        "/terms": {"ar": ("شروط الاستخدام | SymptoSense", "اطّلع على شروط استخدام SymptoSense وحدود الخدمة والمسؤوليات المرتبطة باستخدام الموقع."), "en": ("Terms of Use | SymptoSense", "Review the terms for using SymptoSense, service limitations, and responsibilities related to the platform.")},
        "/meds": {"ar": ("الأدوية والتذكيرات | SymptoSense", "معلومات توعوية عن الأدوية والتنبيهات والتداخلات، مع أدوات تذكير تساعدك على تنظيم أدويتك بأمان."), "en": ("Medications & Reminders | SymptoSense", "Educational medication information, warnings and interactions, plus reminder tools to help organize medicines safely.")},
        "/firstaid": {"ar": ("الإسعافات الأولية | SymptoSense", "إرشادات إسعاف أولي مبسطة للحالات الشائعة، مع توضيح متى تحتاج للاتصال بالطوارئ فورًا."), "en": ("First Aid | SymptoSense", "Simple first-aid guidance for common situations, including when emergency help is needed immediately.")},
        "/calculators": {"ar": ("الحاسبات الصحية | SymptoSense", "حاسبات صحية تقديرية لمؤشر كتلة الجسم والاحتياج اليومي ومؤشرات عامة، للتوعية وليست للتشخيص."), "en": ("Health Calculators | SymptoSense", "Estimated health calculators for BMI, daily needs, and general indicators for education, not diagnosis.")},
        "/emergency": {"ar": ("الطوارئ | SymptoSense", "علامات الخطر وأرقام الطوارئ في السعودية، ومتى تحتاج إلى الإسعاف أو مساعدة صحية فورية."), "en": ("Emergency Guidance | SymptoSense", "Emergency warning signs and Saudi emergency numbers, including when to seek ambulance or immediate medical help.")},
        "/search": {"ar": ("البحث الصحي | SymptoSense", "ابحث عن أعراض وفحوص ومفاهيم صحية بلغة مبسطة مع روابط لمصادر طبية موثوقة."), "en": ("Health Search | SymptoSense", "Search symptoms, tests, and health topics in plain language with links to trusted medical sources.")},
        "/sources": {"ar": ("المصادر الطبية | SymptoSense", "استعرض المصادر الطبية والحكومية الموثوقة التي يستند إليها المحتوى التوعوي في SymptoSense."), "en": ("Medical Sources | SymptoSense", "Explore the trusted medical and government sources used to support educational content across SymptoSense.")},
        "/tips": {"ar": ("نصائح صحية | SymptoSense", "نصائح صحية عامة ومبسطة تساعدك على العناية بصحتك اليومية، للتوعية ولا تغني عن الرعاية الطبية."), "en": ("Health Tips | SymptoSense", "Plain-language general health tips for everyday wellbeing, for education and not a substitute for medical care.")},
        "/relax": {"ar": ("الاسترخاء والتنفس | SymptoSense", "تمارين تنفس واسترخاء بسيطة تساعد على التهدئة ودعم الرفاه النفسي دون أن تكون علاجًا طبيًا."), "en": ("Relaxation & Breathing | SymptoSense", "Simple breathing and relaxation exercises for calm and wellbeing; not a medical treatment.")},
    }
    logical_path = _strip_lang_prefix(request.path)
    core_meta = seo_core.get(logical_path, {}).get(lang)
    if core_meta:
        seo_title, seo_desc = core_meta
        title = seo_title
        if not desc:
            desc = seo_desc
    elif not desc:
        desc = _t("desc")

    # SEO-only: keep health-library detail pages available to users and links,
    # but ask search engines not to index each individual condition/symptom page.
    # The library index itself (/health-library) remains indexable.
    private_noindex = {
        "/health-record", "/profile", "/family", "/checkin", "/safeid", "/settings", "/manage",
        "/memory", "/health-command-center", "/privacy-center", "/consent", "/login", "/register",
        "/verify-email", "/forgot-password", "/competition", "/competition-dashboard", "/innovation-lab", "/safety-lab"
    }
    robots_directive = (
        "noindex, follow, noarchive"
        if logical_path.startswith("/health-library/") or logical_path in private_noindex
        else "index, follow"
    )
    base = _site_url()
    # PAGE_FRAME intentionally accepts raw HTML only for ``body`` and trusted
    # CSS/navigation fragments. Metadata and attribute values are always encoded
    # here so future callers cannot accidentally turn a page title or URL into XSS.
    safe_title = html_lib.escape(str(title or ""), quote=True)
    safe_desc = html_lib.escape(str(desc or ""), quote=True)
    safe_keywords = html_lib.escape(str(_t("keywords") or ""), quote=True)
    if request.path == "/":
        canonical_path = "/"
    elif _path_lang(request.path):
        canonical_path = request.path
    else:
        canonical_path = request.path
    canonical = html_lib.escape(base + canonical_path, quote=True)
    if request.path == "/":
        hreflang_tags = (
            '<link rel="alternate" hreflang="ar" href="%s/ar/">'
            '<link rel="alternate" hreflang="en" href="%s/en/">'
            '<link rel="alternate" hreflang="x-default" href="%s/">'
        ) % (html_lib.escape(base, quote=True), html_lib.escape(base, quote=True), html_lib.escape(base, quote=True))
    elif _path_lang(request.path):
        suffix = _strip_lang_prefix(request.path)
        ar_href = base + _localized_url(suffix, "ar")
        en_href = base + _localized_url(suffix, "en")
        hreflang_tags = (
            '<link rel="alternate" hreflang="ar" href="%s">'
            '<link rel="alternate" hreflang="en" href="%s">'
            '<link rel="alternate" hreflang="x-default" href="%s/">'
        ) % (html_lib.escape(ar_href, quote=True), html_lib.escape(en_href, quote=True), html_lib.escape(base, quote=True))
    else:
        hreflang_tags = ""
    og_image = html_lib.escape(base + "/static/images/symptosense-social-preview.png", quote=True)
    gsc = os.environ.get("GOOGLE_SITE_VERIFICATION", "")
    gsc_tag = (
        '<meta name="google-site-verification" content="%s">' % html_lib.escape(gsc, quote=True)
        if gsc
        else ""
    )

    # The public language picker is intentionally a *true* bare page.  Earlier
    # versions hid the app navigation/assistant with CSS, but still shipped their
    # DOM, JavaScript, modals and install prompt to first-time visitors.  Besides
    # being unnecessary work, assistive technology could still discover some of
    # those hidden controls.  Keep the first screen focused on one task only:
    # choose a language, then enter the app.
    if bare:
        bare_css = """
        *,*::before,*::after{box-sizing:border-box}
        html,body{margin:0;padding:0;width:100%;min-height:100%}
        button,input,select,textarea{font:inherit}
        button{color:inherit}
        .ss-sr-only{position:absolute!important;width:1px!important;height:1px!important;padding:0!important;margin:-1px!important;overflow:hidden!important;clip:rect(0,0,0,0)!important;white-space:nowrap!important;border:0!important}
        """ + extra_css
        return f"""<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="apple-touch-icon" sizes="180x180" href="/icons/apple-touch-icon.png">
<link rel="icon" type="image/svg+xml" href="/brand-icon.svg">
<link rel="stylesheet" href="/static/css/design-system.css?v={html_lib.escape(STATIC_ASSET_VERSION, quote=True)}">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="SymptoSense">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;600;700;800;900&family=Poppins:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<title>{safe_title}</title>
<meta name="description" content="{safe_desc}">
<meta name="keywords" content="{safe_keywords}">
<meta name="robots" content="{robots_directive}">
{gsc_tag}
<link rel="canonical" href="{canonical}">
{hreflang_tags}
<meta property="og:title" content="{safe_title}">
<meta property="og:description" content="{safe_desc}">
<meta property="og:image" content="{og_image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="SymptoSense — Understand your symptoms and know your next step">
<meta property="og:url" content="{canonical}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="SymptoSense">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{safe_title}">
<meta name="twitter:description" content="{safe_desc}">
<meta name="twitter:image" content="{og_image}">
<meta name="theme-color" content="#F8FCFF">
<style>{bare_css}</style>
</head>
<body>{body}</body>
</html>"""

    ast = CT["en" if lang == "en" else "ar"]
    body_class = ""
    try:
        prefs = advanced_features.get_preferences(_ss_user_id()) if _ss_user_id() else {"accessibility_mode": False}
        if prefs.get("accessibility_mode"):
            body_class = "ss-accessibility"
    except Exception:
        logging.getLogger(__name__).warning("Handled exception in _page; fallback applied (handler 5076)")
        body_class = ""
    rendered = (
        PAGE_FRAME
        .replace("__LANG__", "en" if lang == "en" else "ar")
        .replace("__DIR__", "ltr" if lang == "en" else "rtl")
        .replace("__BODY_CLASS__", body_class)
        .replace("__USER_CSRF__", _user_csrf_token() if _ss_user_id() else "")
        .replace("__TITLE__", safe_title)
        .replace("__DESC__", safe_desc)
        .replace("__KEYWORDS__", safe_keywords)
        .replace("__ROBOTS__", robots_directive)
        .replace("__CANONICAL__", canonical)
        .replace("__HREFLANG__", hreflang_tags)
        .replace("__OG_IMAGE__", og_image)
        .replace("__GSC_TAG__", gsc_tag)
        .replace("__EXTRA_CSS__", extra_css)
        .replace("__NAV__", _nav())
        .replace("__FOOTER__", _footer())
        .replace("__BNAV_HOME__", _t("bnav_home"))
        .replace("__BNAV_CHAT__", _t("bnav_chat"))
        .replace("__BNAV_PSYCH__", _t("bnav_psych"))
        .replace("__BNAV_PROFILE__", _t("bnav_profile"))
        .replace("__SKIP_TO_CONTENT__", "تخطي إلى المحتوى" if lang == "ar" else "Skip to content")
        .replace("__OFFLINE_TITLE__", "أنت الآن بدون اتصال — وضع الأمان متاح" if lang == "ar" else "You are offline — Safety Mode is available")
        .replace("__OFFLINE_SUB__", "لن يعمل الذكاء الاصطناعي أو التحليل الكامل حتى يعود الاتصال." if lang == "ar" else "AI and full analysis stay unavailable until connectivity returns.")
        .replace("__OFFLINE_OPEN__", "فتح وضع الأمان" if lang == "ar" else "Open Safety Mode")
        .replace("__MAIN_NAV_LABEL__", "التنقل الرئيسي" if lang == "ar" else "Main navigation")
        .replace("__AST_BACK_LABEL__", "رجوع" if lang == "ar" else "Back")
        .replace("__AST_CLOSE_LABEL__", "إغلاق المساعد" if lang == "ar" else "Close assistant")
        .replace("__AST_SEND_LABEL__", "إرسال الرسالة" if lang == "ar" else "Send message")
        .replace("__AST_TITLE__", ast["asst_title"])
        .replace("__AST_SUB__", ast["asst_sub"])
        .replace("__AST_GREET__", ast["asst_greet"])
        .replace("__AST_PH__", ast["asst_ph"])
        .replace("__AST_DISC__", ast["asst_disc"])
        .replace("__AST_CTX__", "استخدم ملفي الصحي المحفوظ في الإجابة (للمسجّلين فقط)" if lang == "ar" else "Use my saved health file in answers (signed-in only)")
        .replace("__AST_EXPLAIN_ASK__", ast["asst_explain_ask"])
        .replace("__AST_T__", _json_for_script(ast, ensure_ascii=False))
        .replace("__MAIN_ROLE__", "" if re.search(r'<main\b|role="main"', body) else ' role="main"')
        .replace("__MAIN_H1__", "" if re.search(r"<h1\b", body) else '<h1 class="sr-only">%s</h1>' % safe_title)
        .replace("__BODY__", body)
        .replace("__ASSET_VERSION__", html_lib.escape(STATIC_ASSET_VERSION, quote=True))
    )
    return _localize_html_links(rendered, lang)

# ---------------------------------------------------------------- landing
# ---------------------------------------------------------------- welcome / landing / about
GREETINGS = [
    ("🇸🇦", "مرحباً بكم"), ("🇬🇧", "Welcome"), ("🇹🇷", "Hoş geldiniz"),
    ("🇵🇭", "Maligayang pagdating"), ("🇫🇷", "Bienvenue"), ("🇪🇸", "Bienvenidos"),
    ("🇩🇪", "Willkommen"), ("🇮🇳", "स्वागत है"), ("🇵🇰", "خوش آمدید"),
    ("🇮🇩", "Selamat datang"), ("🇧🇩", "স্বাগতম"), ("🇷🇺", "Добро пожаловать"),
    ("🇨🇳", "欢迎"), ("🇯🇵", "ようこそ"), ("🇰🇷", "환영합니다"),
    ("🇺🇦", "Ласкаво просимо"), ("🇬🇷", "Καλώς ήρθατε"), ("🇮🇹", "Benvenuti"),
    ("🇧🇷", "Bem-vindo"), ("🇳🇱", "Welkom"), ("🇵🇱", "Witamy"),
    ("🇨🇿", "Vítejte"), ("🇸🇪", "Välkommen"), ("🇳🇴", "Velkommen"),
    ("🇩🇰", "Velkommen"), ("🇫🇮", "Tervetuloa"), ("🇷🇴", "Bine ați venit"),
    ("🇭🇺", "Üdvözöljük"), ("🇮🇱", "ברוכים הבאים"), ("🇮🇷", "خوش آمدید"),
    ("🇰🇿", "Қош келдіңіз"), ("🇺🇿", "Xush kelibsiz"), ("🇲🇾", "Selamat datang"),
    ("🇻🇳", "Chào mừng"), ("🇹🇭", "ยินดีต้อนรับ"), ("🇹🇿", "Karibu"),
    ("🇿🇦", "Welkom"), ("🇦🇿", "Xoş gəldiniz"), ("🇰🇬", "Кош келдиңиз"),
    ("🇪🇹", "እንኳን ደህና መጡ"),
]

WELCOME_LANGS = [
    ('<span class="lang-badge">SA</span>', "العربية", "ar", "واجهة عربية بالكامل"),
    ('<span class="lang-badge">UK</span>', "English", "en", "Full English interface"),
]

WELCOME_CSS = inline_assets.text("WELCOME_CSS.css")

LANG_PICKER_CSS = inline_assets.text("LANG_PICKER_CSS.css")

HOME_CSS = inline_assets.text("HOME_CSS.css")
_HOME_KNOWLEDGE_CACHE = {"at": 0.0, "data": None, "refreshing": False}
_HOME_KNOWLEDGE_LOCK = threading.Lock()

def _bundled_home_knowledge_snapshot():
    """Non-blocking *bundled-content* metrics when live database stats are unavailable.

    medical_knowledge seeds SOURCES/SYMPTOMS/DISEASES/RED_RULES, not DEFAULT_*.
    The fallback is labeled as bundled rather than presented as live database data.
    """
    try:
        sources = getattr(medical_knowledge, "SOURCES", ()) or ()
        symptoms = getattr(medical_knowledge, "SYMPTOMS", ()) or ()
        diseases = getattr(medical_knowledge, "DISEASES", ()) or ()
        red_rules = getattr(medical_knowledge, "RED_RULES", ()) or ()
        retired = set(getattr(medical_knowledge, "SYMPTOM_CANONICAL_MIGRATIONS", {}) or {})
        source_slugs = {str(row[0]) for row in sources if isinstance(row, (tuple, list)) and row}
        symptom_slugs = {str(row[0]) for row in symptoms if isinstance(row, (tuple, list)) and row and str(row[0]) not in retired}
        disease_by_slug = {str(row["slug"]): row for row in diseases if isinstance(row, dict) and row.get("slug")}
        disease_links = set()
        direct_support = set()
        disease_source_links = set()
        for slug, disease in disease_by_slug.items():
            disease_symptoms = {str(s) for s in (disease.get("symptoms") or {}) if str(s) in symptom_slugs}
            for sym in disease_symptoms:
                disease_links.add((slug, sym))
            for ref in disease.get("sources") or ():
                if isinstance(ref, (tuple, list)) and ref and str(ref[0]) in source_slugs:
                    disease_source_links.add((slug, str(ref[0])))
                    direct_support.update(disease_symptoms)
        safety_support = set()
        for rule in red_rules:
            if isinstance(rule, (tuple, list)) and len(rule) > 11 and str(rule[11]) in source_slugs:
                safety_support.update(str(s) for s in (rule[3] or ()) if str(s) in symptom_slugs)
        support = direct_support | safety_support
        unique_rules = {str(row[0]) for row in red_rules if isinstance(row, (tuple, list)) and row}
        alias_count = sum(len(row[4] or ()) + len(row[5] or ()) for row in symptoms if isinstance(row, (tuple, list)) and len(row) > 5 and str(row[0]) in symptom_slugs)
        terms = len(symptom_slugs) * 2 + alias_count
        return {
            "_origin": "bundled", "verified_sources": len(source_slugs),
            "conditions": len(disease_by_slug), "symptoms": len(symptom_slugs),
            "red_flags": len(unique_rules), "source_links": len(disease_source_links),
            "coverage": round(100 * len({sym for _, sym in disease_links}) / len(symptom_slugs), 1) if symptom_slugs else 0.0,
            "support_coverage": round(100 * len(support) / len(symptom_slugs), 1) if symptom_slugs else 0.0,
            "safety_only_symptoms": len(safety_support - {sym for _, sym in disease_links}),
            "unsupported_symptoms": max(0, len(symptom_slugs) - len(support)),
            "source_coverage": round(100 * sum(any(link[0] == slug for link in disease_source_links) for slug in disease_by_slug) / len(disease_by_slug), 1) if disease_by_slug else 0.0,
            "high_authority": sum(1 for r in sources if len(r) > 4 and r[4] in ("government", "international_organization", "national_health_service", "clinical_guideline_body")),
            "recent_source_additions": 0,
            "search_topics": len(getattr(health_search, "SEARCH_KB", {}) or {}),
            "searchable_symptoms": len(symptom_slugs),
            "release_sources_added": 0, "release_conditions_added": 0,
            "release_symptoms_added": 0, "release_search_entries": 0,
            "v76_symptoms_added": 0,
            "symptom_growth_since_v74": max(0, len(symptom_slugs) - 247),
            "relationship_growth_since_v74": max(0, len(disease_links) - 715),
            "search_term_entries": terms,
            "search_term_growth_since_v74": max(0, terms - 1876),
            "v76_duplicate_concepts_merged": 0, "v76_alias_collisions_resolved": 0,
        }
    except Exception as exc:
        logging.getLogger(__name__).warning("Bundled knowledge count failed: %s", type(exc).__name__)
        # Do not imply that 0 means no medical content if statistics cannot be measured.
        return {"_origin": "unavailable"}

def _merge_home_knowledge_stats(stats, fallback):
    snap = {
        "_origin": "live",
        "verified_sources": int(stats.get("verified_sources") or 0),
        "conditions": int(stats.get("active_diseases") or 0),
        "symptoms": int(stats.get("active_symptoms") or 0),
        "red_flags": int(stats.get("active_red_flags") or 0),
        "source_links": int(stats.get("disease_source_links") or 0),
        "coverage": float(stats.get("symptom_coverage_pct") or 0.0),
        "support_coverage": float(stats.get("symptom_support_coverage_pct") or stats.get("symptom_coverage_pct") or 0.0),
        "safety_only_symptoms": int(stats.get("safety_only_symptoms") or 0),
        "unsupported_symptoms": int(stats.get("unsupported_symptoms") or 0),
        "source_coverage": float(stats.get("source_coverage_pct") or 0.0),
        "high_authority": int(stats.get("high_authority_sources") or 0),
        "recent_source_additions": int(stats.get("recent_source_additions") or 0),
        "search_topics": len(getattr(health_search, "SEARCH_KB", {}) or {}),
        "searchable_symptoms": int(stats.get("active_symptoms") or 0),
        "release_sources_added": fallback.get("release_sources_added", 0),
        "release_conditions_added": fallback.get("release_conditions_added", 0),
        "release_symptoms_added": fallback.get("release_symptoms_added", 0),
        "release_search_entries": fallback.get("release_search_entries", 0),
        "v76_symptoms_added": int(stats.get("v76_symptoms_added") or fallback.get("v76_symptoms_added", 0)),
        "symptom_growth_since_v74": int(stats.get("symptom_growth_since_v74") or fallback.get("symptom_growth_since_v74", 0)),
        "relationship_growth_since_v74": int(stats.get("relationship_growth_since_v74") or fallback.get("relationship_growth_since_v74", 0)),
        "search_term_entries": int(stats.get("search_term_entries") or fallback.get("search_term_entries", 0)),
        "search_term_growth_since_v74": int(stats.get("search_term_growth_since_v74") or fallback.get("search_term_growth_since_v74", 0)),
        "v76_duplicate_concepts_merged": int(stats.get("v76_duplicate_concepts_merged") or fallback.get("v76_duplicate_concepts_merged", 0)),
        "v76_alias_collisions_resolved": int(stats.get("v76_alias_collisions_resolved") or fallback.get("v76_alias_collisions_resolved", 0)),
    }
    if not any((snap["verified_sources"], snap["conditions"], snap["symptoms"], snap["red_flags"])):
        return fallback

    # A successful read from the database is authoritative.  Do not use max()
    # with the bundled seed: admins may have disabled/retired content in production.
    return snap

def _refresh_home_knowledge_snapshot_background():
    """Refresh live stats away from the request thread.

    `medical_knowledge.statistics()` may initialize optional PostgreSQL schemas.
    Doing that inside /home can hold the request long enough for Railway to emit
    an upstream timeout. Background refresh keeps the public page responsive.
    """
    fallback = _bundled_home_knowledge_snapshot()
    try:
        stats = medical_knowledge.statistics()
        snap = _merge_home_knowledge_stats(stats, fallback)
        with _HOME_KNOWLEDGE_LOCK:
            _HOME_KNOWLEDGE_CACHE["data"] = snap
            _HOME_KNOWLEDGE_CACHE["at"] = time.time()
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "Unable to refresh public knowledge snapshot in background; using bundled fallback error_type=%s",
            type(exc).__name__,
        )
        with _HOME_KNOWLEDGE_LOCK:
            if not _HOME_KNOWLEDGE_CACHE.get("data"):
                _HOME_KNOWLEDGE_CACHE["data"] = fallback
                _HOME_KNOWLEDGE_CACHE["at"] = time.time()
    finally:
        with _HOME_KNOWLEDGE_LOCK:
            _HOME_KNOWLEDGE_CACHE["refreshing"] = False

def _home_knowledge_snapshot():
    """Return immediately; refresh PostgreSQL-backed statistics asynchronously."""
    now = time.time()
    fallback = _bundled_home_knowledge_snapshot()
    with _HOME_KNOWLEDGE_LOCK:
        cached = _HOME_KNOWLEDGE_CACHE.get("data")
        cached_at = float(_HOME_KNOWLEDGE_CACHE.get("at") or 0)
        fresh = bool(cached and now - cached_at < 300)
        if not fresh and not _HOME_KNOWLEDGE_CACHE.get("refreshing"):
            _HOME_KNOWLEDGE_CACHE["refreshing"] = True
            threading.Thread(
                target=_refresh_home_knowledge_snapshot_background,
                name="symptosense-home-stats-refresh",
                daemon=True,
            ).start()
        return cached or fallback

def _tools_html(t):
    return """
    <div class="tools">
      <h2 class="tools-h">""" + t("home_tools_t") + """</h2>
      <p class="tools-sub">""" + t("home_tools_sub") + """</p>
      <div class="tools-grid">
        <a class="tool" href="/chat"><span class="t-ic">🩺</span><b>""" + t("home_tools_1t") + """</b><p>""" + t("home_tools_1p") + """</p></a>
        <a class="tool" href="/blood"><span class="t-ic">🩸</span><b>""" + t("home_tools_2t") + """</b><p>""" + t("home_tools_2p") + """</p></a>
        <a class="tool" href="/meds"><span class="t-ic">💊</span><b>""" + t("home_tools_3t") + """</b><p>""" + t("home_tools_3p") + """</p></a>
        <a class="tool" href="/emergency"><span class="t-ic">🚨</span><b>""" + t("home_tools_4t") + """</b><p>""" + t("home_tools_4p") + """</p></a>
        <a class="tool" href="/calculators"><span class="t-ic">🧮</span><b>""" + t("home_tools_5t") + """</b><p>""" + t("home_tools_5p") + """</p></a>
      </div>
    </div>
    """

ABOUT_US_CSS = inline_assets.text("ABOUT_US_CSS.css")

ABOUT_US_POLISH_CSS = inline_assets.text("ABOUT_US_POLISH_CSS.css")

def about_page():
    t = _t
    body = """
    <div class="card">
      <h2>%s</h2>
      <h3 class="ab-sub">%s</h3>
      <p style="line-height:1.9;">%s</p>
    </div>
    <div class="warn">%s</div>

    <h2 class="sec-head">%s</h2>
    <div class="features">
      <div class="feature"><div class="ic">🤖</div><h3>%s</h3><p>%s</p></div>
      <div class="feature"><div class="ic">🩸</div><h3>%s</h3><p>%s</p></div>
      <div class="feature"><div class="ic">💊</div><h3>%s</h3><p>%s</p></div>
      <div class="feature"><div class="ic">🚨</div><h3>%s</h3><p>%s</p></div>
      <div class="feature"><div class="ic">🏥</div><h3>%s</h3><p>%s</p></div>
      <div class="feature"><div class="ic">🌿</div><h3>%s</h3><p>%s</p></div>
    </div>

    <h2 class="sec-head">%s</h2>
    <div class="how-tl" role="list" aria-label="%s">
      <div class="how-tl-item" role="listitem">
        <div class="how-tl-dot" aria-hidden="true">1</div>
        <div class="how-tl-card"><h3>%s</h3><p>%s</p></div>
      </div>
      <div class="how-tl-item" role="listitem">
        <div class="how-tl-dot" aria-hidden="true">2</div>
        <div class="how-tl-card"><h3>%s</h3><p>%s</p></div>
      </div>
      <div class="how-tl-item" role="listitem">
        <div class="how-tl-dot" aria-hidden="true">3</div>
        <div class="how-tl-card"><h3>%s</h3><p>%s</p></div>
      </div>
    </div>

    <div class="card">
      <h2>%s</h2>
      <p style="line-height:1.9;">%s</p>
      <div class="src-chips">
        <span>Mayo Clinic</span><span>NHS</span><span>WHO</span><span>CDC</span><span>MedlinePlus</span>
      </div>
    </div>

    <div class="card">
      <h2>%s</h2>
      <p style="line-height:1.9;">%s</p>
    </div>
    """ % (
        t("ab_t1"), t("ab_hero_sub"), t("ab_hero_p"), t("ab_alert"),
        t("ab_services_h"),
        t("ab_sv1_t"), t("ab_sv1_p"), t("ab_sv2_t"), t("ab_sv2_p"),
        t("ab_sv3_t"), t("ab_sv3_p"), t("ab_sv4_t"), t("ab_sv4_p"),
        t("ab_sv5_t"), t("ab_sv5_p"), t("ab_sv6_t"), t("ab_sv6_p"),
        t("ab_how_h"),
        t("ab_how_h"),
        t("ab_how1_t"), t("ab_how1_p"),
        t("ab_how2_t"), t("ab_how2_p"),
        t("ab_how3_t"), t("ab_how3_p"),
        t("ab_srcs_h"), t("ab_srcs_p2"),
        t("ab_priv_h"), t("ab_priv_p"),
    )
    return _page(_t("title_about"), body)

def user_profile_page():
    """Personal health dashboard. All data arrives through ProfileDashboardService (read-only aggregation)."""
    from services.profile_dashboard_service import ProfileDashboardService, db_sources
    from pagelib import profile_dashboard_html
    lang = _lang()
    user = _ss_user() or {}
    try:
        medication_id = _medication_user_id()
    except (PermissionError, ValueError, TypeError):
        medication_id = None
    sources = db_sources(db, account_id=_ss_user_id(), data_id=_data_user_id(), medication_id=medication_id,
                         consent_state=_consent_state, account_name=str(user.get("name") or ""))
    data = ProfileDashboardService(sources).build()
    return _page("ملفي" if lang == "ar" else "My Profile", profile_dashboard_html.render(data, lang))

def terms_page():
    ar = _lang() == "ar"
    title = "شروط الاستخدام" if ar else "Terms of use"
    body = """
    <main class="v2-info-page"><section><h1>📄 __TITLE__</h1><p>__P1__</p></section>
    <section><h2>__H2__</h2><p>__P2__</p></section><section><h2>__H3__</h2><p>__P3__</p></section>
    <section><h2>__H4__</h2><p>__P4__</p></section></main>
    """
    values = {
        "__TITLE__": title,
        "__P1__": "SymptoSense أداة تثقيفية ومساعدة على فهم الأعراض، وليست بديلًا عن الطبيب أو خدمات الطوارئ." if ar else "SymptoSense is an educational symptom-understanding aid, not a substitute for a clinician or emergency services.",
        "__H2__": "ليست أداة تشخيص" if ar else "Not a diagnostic tool",
        "__P2__": "النتائج احتمالات تثقيفية قابلة للخطأ ولا تؤكد مرضًا أو تنفيه. لا تغيّر دواءً موصوفًا بناءً عليها." if ar else "Results are fallible educational possibilities and neither confirm nor rule out disease. Do not change prescribed medicine based on them.",
        "__H3__": "الحالات العاجلة" if ar else "Urgent situations",
        "__P3__": "إذا ظهرت علامة خطر أو تدهورت الحالة، اطلب الرعاية العاجلة فورًا بدل انتظار نتيجة الموقع." if ar else "If danger signs appear or the condition worsens, seek urgent care immediately rather than waiting for a website result.",
        "__H4__": "الاستخدام المسؤول" if ar else "Responsible use",
        "__P4__": "استخدم معلومات عامة، ولا تدخل بيانات تعريفية لشخص آخر دون إذنه. المصادر الخارجية تخضع لسياسات الجهة المالكة لها." if ar else "Use general information and do not enter another person's identifying data without permission. External sources are governed by their owners' policies.",
    }
    for key, value in values.items():
        body = body.replace(key, value)
    return _page(title, body)

def contact_page():
    ar = _lang() == "ar"
    title = "تواصل معنا" if ar else "Contact us"
    tg_url = ("https://t.me/" + CONTACT_TELEGRAM) if CONTACT_TELEGRAM else ""
    body = """
    <main class="v2-info-page ss-contact-page" aria-labelledby="contactTitle">
      <section>
        <h1 id="contactTitle">💬 __TITLE__</h1>
        <p>__INTRO__</p>
        __ACTION__
        <p class="muted">__NOTE__</p>
      </section>
    </main>
    <style>
      .ss-contact-page section{max-width:720px;margin-inline:auto;text-align:center}
      .ss-contact-page .ss-contact-action{display:inline-flex;align-items:center;justify-content:center;min-height:48px;margin-top:12px;padding:0 20px;border-radius:14px;background:#1565c0;color:#fff;font-weight:800;text-decoration:none}
    </style>
    """
    action = ('<a class="ss-contact-action" href="%s" target="_blank" rel="noopener noreferrer">%s</a>' % (html_lib.escape(tg_url, quote=True), ("فتح Telegram" if ar else "Open Telegram"))) if tg_url else ''
    values = {
        "__TITLE__": title,
        "__INTRO__": ("للاستفسارات العامة المتعلقة بالموقع يمكنك استخدام قناة التواصل الرسمية أدناه." if ar else "For general questions about the site, use the official contact channel below."),
        "__ACTION__": action,
        "__NOTE__": ("لا ترسل أعراضًا أو نتائج تحاليل أو معلومات صحية حساسة عبر قنوات التواصل العامة." if ar else "Do not send symptoms, lab results, or sensitive health information through general contact channels."),
    }
    for key, value in values.items():
        body = body.replace(key, value)
    return _page(title, body)

# ---------------------------------------------------------------- chat
# ---------------------------------------------------------------- symptom-analysis chat view
# Heavy rendering/JavaScript lives in chat_view.py; Flask route wiring stays here.
def chat_page():
    html = render_chat_page(lang=_lang(), page=_page, t=_t, json_for_script=_json_for_script)
    # Let the page know it is signed in so it does not probe private APIs (401 noise) as a guest.
    if isinstance(html, str) and _ss_user_id():
        html = html.replace("<body", '<body data-logged-in="1"', 1)
    return html

# ---------------------------------------------------------------- content pages i18n
CT = inline_assets.data("CT.json")

# ---------------------------------------------------------------- blood
BLOOD_COLLECTION_CONSENT_VERSION = "blood-v1"

def _blood_saved_result_response(saved, lang, member_name=None):
    """Return a previously saved lab result in the same shape as /api/blood.

    Exact-file duplicates reuse the stored interpretation instead of re-running
    PDF/image extraction or adding another database/Excel row.
    """
    data = (saved or {}).get("data") or {}
    if not isinstance(data, dict):
        data = {}
    return {
        "ok": True,
        "stage": "result",
        "duplicate_file": True,
        "reused_saved_result": True,
        "duplicate_message": (
            "هذا الملف سبق تحليله؛ عرضنا نتيجته المحفوظة ولم نضف سجلًا جديدًا."
            if lang == "ar" else
            "This exact file was analyzed before. The saved result was reused and no new record was added."
        ),
        "text_html": data.get("text_html") or "",
        "chart": data.get("chart"),
        "level": data.get("level"),
        "indicators": data.get("indicators") or [],
        "notes": data.get("notes") or [],
        "dangers": data.get("dangers") or [],
        "summary": data.get("summary") or "",
        "disclaimer": data.get("disclaimer") or blood_test.disclaimer_text(lang),
        "child": bool(data.get("child")),
        "child_note": data.get("child_note"),
        "blood_id": (saved or {}).get("id"),
        "member_name": member_name or data.get("member_name"),
        "patterns": data.get("patterns") or [],
        "relationships": data.get("relationships") or [],
        "trend": data.get("trend") or [],
        "doctor_summary": data.get("doctor_summary") or "",
        "doctor_questions": data.get("doctor_questions") or [],
        "clinical_context": data.get("clinical_context") or {},
        "context_notes": data.get("context_notes") or [],
        "attention": data.get("attention") or {},
        "verification": data.get("verification") or {},
        "medical_sources": data.get("medical_sources") or [],
        "extraction_meta": data.get("extraction_meta") or {},
        "report_meta": data.get("report_meta") or {},
        "health_context_links": data.get("health_context_links") or [],
        "confirmed_by_user": bool(data.get("confirmed_by_user")),
    }

# ---------------------------------------------------------------- meds
@app.route("/service-worker.js")
def service_worker_file():
    response=send_from_directory(BASE_DIR,"service-worker.js",mimetype="application/javascript")
    response.headers["Cache-Control"]="no-cache, no-store, must-revalidate"
    response.headers["Service-Worker-Allowed"]="/"
    return response

def _safeid_install_token(token):
    token = str(token or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,180}", token):
        abort(404)
    return token


def _safeid_share_url(token):
    return _site_url().rstrip("/") + url_for("public_safeid", token=token)


def _safeid_qr_png_bytes(token, size=512):
    """Build a padded square QR icon for the exact current SafeID token."""
    token = _safeid_install_token(token)
    data_uri = privacy_features.qr_png_data_uri(_safeid_share_url(token))
    if not data_uri or "," not in data_uri:
        abort(503)
    try:
        raw = base64.b64decode(data_uri.split(",", 1)[1], validate=True)
        from PIL import Image
        src = Image.open(io.BytesIO(raw)).convert("RGB")
        size = max(128, min(1024, int(size)))
        # Leave a quiet white border so launchers that round icons do not crop
        # QR modules. NEAREST keeps module edges crisp.
        inner = max(96, int(size * 0.78))
        resampling = getattr(getattr(Image, "Resampling", Image), "NEAREST")
        src = src.resize((inner, inner), resampling)
        canvas = Image.new("RGB", (size, size), "white")
        off = (size - inner) // 2
        canvas.paste(src, (off, off))
        out = io.BytesIO(); canvas.save(out, format="PNG", optimize=True)
        return out.getvalue()
    except Exception:
        logging.getLogger(__name__).exception("SafeID QR install icon generation failed")
        abort(503)


@app.route("/static/images/symptosense-social-preview.png")
def social_preview_image():
    """Serve the social preview even when a deployment flattens asset folders.

    Competition uploads have occasionally reached Railway with root files but
    without nested folders. Prefer the normal static asset, then fall back to a
    root-level copy bundled with the release.
    """
    candidates = [
        os.path.join(BASE_DIR, "static", "images", "symptosense-social-preview.png"),
        os.path.join(BASE_DIR, "symptosense-social-preview.png"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            response = send_file(path, mimetype="image/png", conditional=True)
            response.headers["Cache-Control"] = "public, max-age=86400"
            return response
    abort(404)

@app.route("/icons/<path:filename>")
def pwa_icon_file(filename):
    # Normal package layout first; root-level duplicates make the release
    # resilient if a manual GitHub/Railway upload accidentally flattens folders.
    safe_name = os.path.basename(str(filename or ""))
    if safe_name != filename or safe_name not in {"icon-192.png", "icon-512.png", "apple-touch-icon.png", "icon.svg", "about-us-phone.webp"}:
        abort(404)
    nested = os.path.join(BASE_DIR, "icons", safe_name)
    root_copy = os.path.join(BASE_DIR, safe_name)
    path = nested if os.path.isfile(nested) else root_copy
    if not os.path.isfile(path):
        abort(404)
    response = send_file(path, conditional=True)
    response.headers["Cache-Control"] = "public, max-age=604800"
    return response


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(BASE_DIR, "favicon.ico", mimetype="image/x-icon")

@app.route("/offline")
def offline():
    return send_from_directory(BASE_DIR, "offline.html")

# ---------------------------------------------------------------- family health hub
MEDS_CSS = """
.med-error{padding:14px;border:1px solid #fecaca;border-radius:14px;background:#fff1f2;color:#991b1b}
.med-retry{margin-top:10px;border:0;border-radius:10px;background:#1565c0;color:#fff;padding:9px 14px;font:inherit;font-weight:800;cursor:pointer}
.med-loading{display:flex;align-items:center;gap:10px;padding:18px;color:#5f7185}
"""

FAM_CSS = """
.fam-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 14px; margin-top: 16px; }
.fam-card { background: #FFFFFF; border: 1px solid #DCEBFA; border-radius: 18px; padding: 18px; cursor: pointer; transition: transform .15s ease, box-shadow .15s ease; text-align: center; }
.fam-card:hover { transform: translateY(-3px); box-shadow: 0 12px 28px rgba(18,59,112,.12); }
.fam-av { width: 58px; height: 58px; margin: 0 auto 10px; border-radius: 50%; background: #EAF4FF; border: 2px solid #DCEBFA; display: flex; align-items: center; justify-content: center; font-size: 28px; }
.fam-name { font-weight: 800; font-size: 16px; color: #123B70; }
.fam-meta { font-size: 13px; color: #5F7185; margin-top: 4px; }
.fam-stat { display: flex; justify-content: center; gap: 14px; margin-top: 10px; font-size: 12px; color: #40566F; }
.fam-stat b { color: #1565c0; }
.fam-form { background: #FFFFFF; border: 1px solid #DCEBFA; border-radius: 18px; padding: 20px; margin-top: 16px; }
.fam-rel-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
.fam-chip { padding: 8px 14px; border-radius: 999px; border: 1.5px solid #1565c0; background: #FFFFFF; color: #1565c0; font-size: 13px; font-weight: 700; cursor: pointer; }
.fam-chip.sel { background: #1565c0; color: #FFFFFF; }
.tl-item { display: flex; gap: 12px; align-items: flex-start; padding: 10px 0; border-bottom: 1px dashed #DCEBFA; font-size: 14px; }
.tl-dot { width: 34px; height: 34px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 17px; background: #EAF4FF; flex: 0 0 34px; }
.tl-date { color: #94A3B8; font-size: 12px; }
.tl-type { color: #40566F; }
.tl-type b { color: #123B70; }
.mplan-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; background: #F5F9FF; border: 1px solid #DCEBFA; border-radius: 12px; padding: 10px 12px; margin-top: 8px; }
.mplan-time { font-weight: 800; color: #1565c0; min-width: 52px; }
.mplan-name { font-weight: 700; color: #40566F; }
.mplan-status { display: flex; gap: 6px; flex-wrap: wrap; }
.mini-btn { border: 1px solid #DCEBFA; background: #FFFFFF; color: #40566F; border-radius: 8px; padding: 5px 10px; font-size: 12px; font-weight: 700; cursor: pointer; }
.mini-btn.tk { border-color: #86EFAC; color: #166534; }
.mini-btn.sk { border-color: #FECACA; color: #991B1B; }
.mini-btn.lt { border-color: #FDE68A; color: #92400E; }
.mini-btn.done { opacity: .55; pointer-events: none; }
.adh-bar { height: 8px; background: #DCEBFA; border-radius: 8px; overflow: hidden; margin-top: 6px; }
.adh-fill { height: 100%; background: #1565c0; border-radius: 8px; }
"""

def _fam_emoji(relation):
    return {
        "me": "👤", "mother": "👩", "father": "👨", "daughter": "👧",
        "son": "👦", "grandparent": "👵", "other": "🧑",
    }.get(relation, "🧑")

# ---------------------------------------------------------------- health search
SEARCH_CSS = inline_assets.text("SEARCH_CSS.css")

# ---------------------------------------------------------------- health calculators
CALC_CSS = inline_assets.text("CALC_CSS.css")

# ---------------------------------------------------------------- first aid
FA_VIDEOS = {
    "burns": {"ar": "HaC2oiBB7sI", "en": "ASY_ImKX6B0"},
    "choking": {"ar": "dZ9-i_UpjlA", "en": "HGBBu4zr8sM"},
    "bleeding": {"ar": "gjQ8VCMGClc", "en": "NxO5LvgqZe0"},
    "poisoning": {"ar": "KEfLi97i_mI", "en": "eTrlm6Nyo6g"},
    "fracture": {"ar": "lY7DLGaz4ek", "en": "2v8vlXgGXwE"},
    "fainting": {"ar": "3CJt648ex8M", "en": "ddHKwkMwNyI"},
    "heatstroke": {"ar": "lp1Q0K9cJ8E", "en": "R6VdoV8dZRc"},
    "cpr": {"ar": "Lc5rSYTnqLM", "en": "BQNNOh8c8ks"},
}

def firstaid_page():
    lang = "en" if _lang() == "en" else "ar"
    cats = wellbeing.first_aid_categories(lang)
    t = CT["en" if _lang() == "en" else "ar"]
    vids = {}
    for k, v in FA_VIDEOS.items():
        yid = v.get(lang)
        if yid:
            vids[k] = "https://www.youtube-nocookie.com/embed/%s?rel=0&hl=%s" % (yid, lang)
    body = """
    <div class="card">
      <h2>__FAH__</h2>
      <p class="muted">__FASUB__</p>
      <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:14px;" id="faBtns"></div>
      <div id="faRes" style="margin-top:18px;"></div>
    </div>
    <div class="warn">__FAWARN__</div>
    <script>
    const CATS = __CATS__;
    const VIDS = __VIDS__;
    const wrap = document.getElementById('faBtns');
    CATS.forEach(([k, label]) => {
      const b = document.createElement('button');
      b.className = 'opt';
      b.textContent = label;
      b.onclick = async () => {
        const r = await fetch('/api/firstaid/' + k);
        const d = await r.json();
        let html = '<div class="bubble bot" style="max-width:100%"><b>' + esc(d.label) + '</b>\\n\\n' + esc(d.text) + '</div>';
        const vid = VIDS[k];
        if (vid) {
          html += '<div class="vidbtn" data-ss-click="loadVid" data-ss-args="' + ssArgs(['$this', vid]) + '">' + esc('__FAVIDEO__') + '</div><div class="vidwrap"></div>';
        }
        document.getElementById('faRes').innerHTML = html;
      };
      wrap.appendChild(b);
    });
    function loadVid(el, url) {
      el.outerHTML = '<iframe src="' + url + '" title="First aid video" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen style="width:100%;aspect-ratio:16/9;border:0;border-radius:12px;margin-top:12px;" loading="lazy" referrerpolicy="strict-origin-when-cross-origin"></iframe>';
    }
    function esc(s) { const div=document.createElement('div'); div.textContent=s||''; return div.innerHTML; }
    </script>
    """
    body = body.replace("__CATS__", _json_for_script(cats, ensure_ascii=False))
    body = body.replace("__VIDS__", _json_for_script(vids, ensure_ascii=False))
    body = body.replace("__FAH__", t["fa_h"]).replace("__FASUB__", t["fa_sub"]).replace("__FAWARN__", t["fa_warn"])
    body = body.replace("__FAVIDEO__", t["fa_video"])
    return _page(_t("title_firstaid"), body)

# ---------------------------------------------------------------- tips
def tips_page():
    t = CT["en" if _lang() == "en" else "ar"]
    body = """
    <div class="card">
      <h2>__TIPSH__</h2>
      <p class="muted">__TIPSSUB__</p>
      <div id="tipBox" style="margin-top:16px;"></div>
      <div style="text-align:center;margin-top:14px;"><button type="button" class="btn" data-ss-click="loadTip">__TIPSB__</button></div>
    </div>
    <div class="warn">__TIPSWARN__</div>
    <script>
    async function loadTip() {
      const box = document.getElementById('tipBox');
      box.innerHTML = '<div style="text-align:center;padding:24px;">... <span class="spin"></span></div>';
      const r = await fetch('/api/tip');
      const d = await r.json();
      box.innerHTML =
        '<div class="tip-card">' +
        '<div class="tip-top"><span class="tip-icon">' + esc(d.icon) + '</span>' +
        '<div><span class="tip-cat">' + esc(d.cat) + '</span><h3>' + esc(d.title) + '</h3></div></div>' +
        '<p class="tip-text">' + esc(d.text) + '</p>' +
        '<div class="tip-tip">💡 ' + esc(d.tip) + '</div>' +
        '</div>';
    }
    function esc(s) { const div=document.createElement('div'); div.textContent=s||''; return div.innerHTML; }
    loadTip();
    </script>
    """
    body = body.replace("__TIPSH__", t["tips_h"]).replace("__TIPSB__", t["tips_btn"])
    body = body.replace("__TIPSSUB__", t["tips_sub"]).replace("__TIPSWARN__", t["tips_warn"])
    return _page(_t("title_tips"), body)

# ---------------------------------------------------------------- relax
def relax_page():
    lang = "en" if _lang() == "en" else "ar"
    txt = wellbeing.relax_guide(lang)
    t = CT["en" if _lang() == "en" else "ar"]
    body = """
    <div class="card">
      <h2>__RELAXH__</h2>
      <div style="font-size:16px;line-height:2;background:#EAF4FF;border-radius:12px;padding:20px;white-space:pre-wrap;">__TXT__</div>
      <div style="text-align:center;margin-top:16px;"><div id="breathBox" style="font-size:30px;font-weight:800;color:#1565c0;height:70px;display:flex;align-items:center;justify-content:center;"></div></div>
    </div>
    <script>
    const phases = [['__BRIN__', 4], ['__BRHOLD__', 7], ['__BROUT__', 8]];
    let pi = 0;
    function tick() {
      const [label, secs] = phases[pi];
      document.getElementById('breathBox').textContent = label;
      pi = (pi + 1) % phases.length;
      setTimeout(tick, secs * 1000);
    }
    tick();
    </script>
    """
    body = body.replace("__TXT__", txt)
    body = body.replace("__RELAXH__", t["relax_h"])
    body = body.replace("__BRIN__", t["br_in"]).replace("__BRHOLD__", t["br_hold"]).replace("__BROUT__", t["br_out"])
    return _page(_t("title_relax"), body)

# ---------------------------------------------------------------- emergency
# ---------------------------------------------------------------- checkin
# ---------------------------------------------------------------- routes
def _health_payload():
    """Return process + startup state without performing request-time DB work.

    Railway's deploy healthcheck is a liveness gate: once the web process is
    listening on the injected PORT, /health must return a 2xx response quickly.
    Database readiness is reported in the payload and is exposed separately by
    /ready so a slow PostgreSQL wake-up or migration cannot turn a reachable
    web process into a five-minute Railway network failure.
    """
    core = globals().get("_STARTUP_CORE_STATE", {})
    warmup = globals().get("_STARTUP_WARMUP_STATE", {})
    ready = bool(core.get("ready"))
    failed = bool(core.get("failed"))
    status = "healthy" if ready else ("degraded" if failed else "starting")
    payload = {
        "ok": True,
        "service": "SymptoSense",
        "status": status,
        "ready": ready,
        "core_database": "ready" if ready else ("failed" if failed else "starting"),
        "core_database_attempts": int(core.get("attempts") or 0),
        "optional_warmup": (
            "finished" if warmup.get("finished") else
            "running" if warmup.get("running") else
            "pending"
        ),
        "storage_backend": "postgres" if db.USE_POSTGRES else "sqlite",
        "storage_mode": os.environ.get("SYMPTOSENSE_DATABASE_MODE", "postgres" if db.USE_POSTGRES else "sqlite-local"),
        "web_secret_source": os.environ.get("SYMPTOSENSE_WEB_SECRET_SOURCE", "configured" if _configured_web_secret else "development-ephemeral"),
    }
    return payload

@app.route("/health", methods=["GET"])
def healthcheck():
    """Railway liveness endpoint: reachable web process => HTTP 200."""
    return jsonify(_health_payload()), 200

@app.route("/healthz", methods=["GET"])
def healthcheck_alias():
    """Compatibility liveness alias for platforms/tools that use /healthz."""
    return jsonify(_health_payload()), 200

@app.route("/ready", methods=["GET"])
@app.route("/readyz", methods=["GET"])
def readiness_check():
    """Strict readiness probe for diagnostics and external monitors."""
    payload = _health_payload()
    ready = bool(payload.get("ready"))
    prod_ok, checks = ops_quality.production_checks(_RAILWAY_RUNTIME, bool(_configured_web_secret), bool(app.config.get("SESSION_COOKIE_SECURE")))
    payload["production_checks"] = checks
    ready = ready and prod_ok
    payload["ok"] = ready
    return jsonify(payload), (200 if ready else 503)


@app.route("/")
def index():
    """Always show the language picker when the app/root is opened."""
    try:
        html = welcome_page()
    except Exception:
        request_id = getattr(g, "request_id", "")
        app.logger.exception("Language picker render failed; request_id=%s", request_id)
        html = """<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#F8FCFF">
<title>SymptoSense — Choose language</title>
<style>
*{box-sizing:border-box}html,body{margin:0;min-height:100%;font-family:Arial,Tajawal,sans-serif;background:#f8fcff;color:#12395c}
main{min-height:100vh;display:grid;place-items:center;padding:24px}
.card{width:min(460px,100%);background:#fff;border:1px solid #dcebf5;border-radius:24px;padding:30px;box-shadow:0 18px 50px rgba(25,118,210,.10);text-align:center}
h1{margin:0 0 8px;font-size:30px}.sub{margin:0 0 24px;color:#627789}
.opts{display:grid;grid-template-columns:1fr 1fr;gap:12px}
a{display:flex;align-items:center;justify-content:center;gap:8px;min-height:64px;border:1px solid #cfe3f2;border-radius:17px;text-decoration:none;color:#12395c;font-weight:800;background:#fff}
a:hover{background:#f2f9ff}
small{display:block;margin-top:18px;color:#8092a1}
</style>
</head>
<body>
<main><section class="card">
<h1>SymptoSense</h1>
<p class="sub">اختر اللغة / Choose language</p>
<div class="opts">
<a href="/ar/" lang="ar" dir="rtl">🇸🇦 العربية</a>
<a href="/en/" lang="en">🇬🇧 English</a>
</div>
<small>Safe fallback language screen</small>
</section></main>
</body></html>"""
    response = make_response(html)
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.route("/language/<code>", methods=["GET"])
def choose_language(code):
    """Compatibility route for older cached language-picker pages."""
    lang = "en" if str(code).lower() == "en" else "ar"
    next_target = web_security.safe_internal_path(request.args.get("next"), "/home")
    if next_target == "/" or next_target.startswith("/?"):
        next_target = "/home"
    return redirect(_localized_target_from_legacy(next_target, lang), code=303)

@app.route("/home")
def home():
    selected = request.args.get("lang") if request.args.get("lang") in {"ar", "en"} else None
    # Keep the installed-PWA language-picker compatibility path.
    if request.args.get("source") == "pwa" and not selected:
        return redirect(url_for("index", next="/home"), code=303)
    return redirect(_localized_url("/", selected or _lang()), code=301)

@app.route("/about")
def about():
    return redirect(_localized_url("/about"), code=301)

@app.route("/about-us")
def about_us():
    return redirect(_localized_url("/about"), code=301)

@app.route("/site-info")
def site_info():
    return redirect(_localized_url("/about"), code=301)

def _count_automated_checks():
    root = os.path.dirname(os.path.abspath(__file__))
    total = 0
    files = 0
    py_tests = os.path.join(root, 'tests')
    if os.path.isdir(py_tests):
        for base, _dirs, names in os.walk(py_tests):
            for name in names:
                if not name.endswith('.py'):
                    continue
                files += 1
                try:
                    text = open(os.path.join(base, name), 'r', encoding='utf-8').read()
                except Exception:
                    continue
                total += len(re.findall(r'^\s*def\s+test_[A-Za-z0-9_]+\s*\(', text, re.M))
    e2e_dir = os.path.join(root, 'e2e')
    if os.path.isdir(e2e_dir):
        for base, _dirs, names in os.walk(e2e_dir):
            for name in names:
                if not name.endswith(('.js', '.ts')):
                    continue
                files += 1
                try:
                    text = open(os.path.join(base, name), 'r', encoding='utf-8').read()
                except Exception:
                    continue
                total += len(re.findall(r'\btest\s*\(', text))
    return {'checks': int(total), 'files': int(files)}

def _public_trust_snapshot():
    db.init_db()
    platform_v2.init_schema()
    medical_knowledge.init_schema()
    conn = db._conn()
    cur = conn.cursor()
    try:
        def count(sql, params=()):
            cur.execute(sql, params)
            row = cur.fetchone()
            return int((row or [0])[0] or 0)

        def table_exists(table):
            if db.USE_POSTGRES:
                cur.execute("SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=%s LIMIT 1", (table,))
                return cur.fetchone() is not None
            cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (table,))
            return cur.fetchone() is not None

        def table_count(table, where=''):
            if not table_exists(table):
                return 0
            sql = 'SELECT COUNT(*) FROM ' + table + ((" WHERE " + where) if where else '')
            return count(sql)

        registered_users = count("SELECT COUNT(*) FROM ss_users WHERE COALESCE(role,'user') <> 'admin'") if table_exists('ss_users') else 0
        unique_visitors = count('SELECT COUNT(DISTINCT user_hash) FROM visits') if table_exists('visits') else 0
        symptom_analyses = table_count('records')
        blood_tests = table_count('blood_tests')
        chat_messages = table_count('ss_chat_history')
        followups = table_count('symptom_followups')
        daily_checkins = table_count('ss_daily_checkins') if table_exists('ss_daily_checkins') else table_count('daily_checkins')
        medication_plans = table_count('med_plans')
        medication_logs = table_count('med_logs')
        medication_reminders = table_count('med_reminders')
        feedback_rows = table_count('feedback')
        assistant_feedback = table_count('assistant_feedback')
        family_profiles = table_count('family_members')
        health_profiles = table_count('ss_health_profiles')
        visits = table_count('visits')
        usage_events = table_count('ss_usage_events')
        analysis_results = table_count('results')
        user_generated_breakdown = {
            'symptom_analyses': symptom_analyses,
            'analysis_results': analysis_results,
            'blood_tests': blood_tests,
            'chat_messages': chat_messages,
            'followups': followups,
            'daily_checkins': daily_checkins,
            'medication_plans': medication_plans,
            'medication_logs': medication_logs,
            'medication_reminders': medication_reminders,
            'feedback': feedback_rows,
            'assistant_feedback': assistant_feedback,
            'family_profiles': family_profiles,
            'health_profiles': health_profiles,
            'visits': visits,
            'usage_events': usage_events,
        }
        stored_data_records = int(sum(user_generated_breakdown.values()))
    finally:
        conn.close()

    knowledge = v51_innovation._knowledge_metrics()
    coverage = v51_innovation._coverage_matrix()
    tests = _count_automated_checks()
    features = feature_flags.public_state()
    knowledge_total = int(knowledge.get('symptoms', 0)) + int(knowledge.get('diseases', 0)) + int(knowledge.get('links', 0)) + int(knowledge.get('red_rules', 0)) + int(knowledge.get('sources', 0)) + int(knowledge.get('combos', 0)) + int(knowledge.get('aliases_ar', 0)) + int(knowledge.get('aliases_en', 0))
    return {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'people': {
            'registered_users': registered_users,
            'unique_visitors': unique_visitors,
        },
        'activity': {
            'symptom_analyses': symptom_analyses,
            'blood_tests': blood_tests,
        },
        'data': {
            'stored_data_records': stored_data_records,
            'knowledge_items': knowledge_total,
        },
        'knowledge': {
            'symptoms': int(knowledge.get('symptoms', 0)),
            'conditions': int(knowledge.get('diseases', 0)),
            'relationships': int(knowledge.get('links', 0)),
            'red_flag_rules': int(knowledge.get('red_rules', 0)),
            'verified_sources': int(knowledge.get('sources', 0)),
            'combos': int(knowledge.get('combos', 0)),
            'search_aliases': int(knowledge.get('aliases_ar', 0)) + int(knowledge.get('aliases_en', 0)),
            'coverage': coverage,
        },
        'quality': {
            'automated_checks': int(tests.get('checks', 0)),
            'test_files': int(tests.get('files', 0)),
        },
        'security': {
            'passkeys_enabled': bool(features.get('passkeys')),
            'fhir_export_enabled': bool(features.get('fhir_export')),
            'source_monitor_enabled': bool(features.get('source_monitor')),
            'api_v1_enabled': bool(features.get('api_v1')),
        },
        'privacy_note': 'Aggregate counts only; no personal health text, emails, names, or chat content is exposed on this page.',
    }

@app.route('/api/trust-snapshot', methods=['GET'])
def api_trust_snapshot():
    try:
        return jsonify({'ok': True, **_public_trust_snapshot()})
    except Exception as exc:
        return _mk_error(exc)

@app.route('/assistant')
def assistant_entry():
    # Consent and bookmarked assistant links must return to the actual UI.
    return redirect(url_for('home', assistant='general'))


@app.route('/api/health-library/click', methods=['POST'])
def api_health_library_click():
    try:
        data = request.get_json(silent=True) or {}
        ok = health_library.record_click(str(data.get('kind') or ''), str(data.get('slug') or ''))
        return jsonify({'ok': bool(ok)})
    except Exception:
        # Anonymous popularity analytics must never interrupt navigation.
        return jsonify({'ok': False}), 200



def _safeid_subject_from_request():
    raw = str(request.args.get("subject") or "self").strip().lower()
    if raw.startswith("member-"):
        try:
            return "member", max(0, int(raw.split("-", 1)[1]))
        except (TypeError, ValueError, OverflowError):
            return "self", 0
    return "self", 0


def _safeid_subject_owned(subject_type, subject_id):
    if subject_type == "self":
        return True
    try:
        return bool(db.get_member(_data_user_id(), int(subject_id)))
    except Exception:
        return False


def _safeid_public_response(html, status=200):
    response = make_response(html, status)
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response.headers["Cache-Control"] = "no-store, private"
    return response


def public_safeid(token):
    ar = _lang() == "ar"
    public_css = r'''
    .em-public{width:min(760px,100%);margin:20px auto;display:grid;gap:14px}.em-card{border:1px solid #dce8f0;border-radius:22px;background:#fff;padding:22px}.em-head{text-align:center;background:linear-gradient(180deg,#f8fcff,#f2f9fd)}.em-badge{display:inline-flex;padding:6px 10px;border-radius:999px;background:#e9f5fb;color:#176f9e;font-weight:900;font-size:11px}.em-head h1{color:#0b3775;margin:12px 0 6px}.em-head p{color:#6f8393;margin:0}.em-title{display:flex;align-items:center;gap:9px;margin-bottom:12px}.em-title span{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;background:#edf7fd}.em-title h2{margin:0;color:#173e60;font-size:18px}.em-field{padding:12px 0;border-bottom:1px solid #edf2f5}.em-field:last-child{border-bottom:0}.em-field b{display:block;color:#3b5c72;font-size:11px}.em-field p{margin:4px 0 0;color:#203e53;line-height:1.7;white-space:pre-wrap;overflow-wrap:anywhere}.em-contact{background:#f8fcfa;border-color:#d8eee3}.em-person{display:flex;align-items:center;gap:10px;margin-bottom:12px}.em-person .avatar{width:42px;height:42px;border-radius:50%;display:grid;place-items:center;background:#e8f6ef;color:#188653;font-size:20px}.em-person b{display:block;color:#173e60}.em-person small{color:#7a8d9e}.em-actions{display:grid;grid-template-columns:1fr 1fr;gap:9px}.em-call,.em-sms{text-decoration:none;text-align:center;border-radius:12px;padding:12px;font-weight:900}.em-call{background:#e9f8f0;color:#14844f}.em-sms{background:#eaf4fb;color:#176fa7}.em-note{font-size:10px;color:#758897;line-height:1.7;margin-top:10px}.em-warning{background:#fff8e7;color:#755b1d;border-radius:12px;padding:10px;font-size:10px;line-height:1.7}.em-empty{text-align:center;color:#7b8f9f;padding:10px}@media(max-width:600px){.em-card{padding:17px}.em-actions{grid-template-columns:1fr}}
    '''
    card = privacy_features.get_safeid_public(token)
    if not card:
        body = '<main class="em-public"><section class="em-card em-head"><div style="font-size:46px">🔒</div><h1>%s</h1><p>%s</p></section></main>' % (
            "وصول الطوارئ غير متاح" if ar else "Emergency access unavailable",
            "قد يكون الرمز متوقفًا أو تم استبداله برمز جديد." if ar else "The code may be paused or replaced with a new one.")
        return _safeid_public_response(_page("SymptoSense", body, extra_css=public_css), 410)

    mode = "found" if str(request.args.get("mode") or "").lower() == "found" else "emergency"
    payload = privacy_features.safeid_public_payload(token, mode) or {"fields": [], "contact_available": False, "emergency_contact": None}
    labels = {
        "allergies": ("الحساسية الدوائية", "Drug allergies"),
        "medications": ("الأدوية المهمة", "Important medications"),
        "conditions": ("حالات صحية مهمة", "Important health conditions"),
        "emergency_note": ("ملاحظة للطوارئ", "Emergency note"),
    }
    fields = []
    for item in payload.get("fields") or []:
        key = item.get("key")
        if key not in labels:
            continue
        label = labels[key][0 if ar else 1]
        fields.append('<div class="em-field"><b>%s</b><p>%s</p></div>' % (
            html_lib.escape(label), html_lib.escape(str(item.get("value") or ""))))
    medical_html = ''.join(fields) if fields else '<div class="em-empty">%s</div>' % (
        "لا توجد معلومات طوارئ مضافة." if ar else "No emergency information has been added.")

    contact = payload.get("emergency_contact") or {}
    contact_html = ""
    if payload.get("contact_available") and contact.get("phone"):
        phone = str(contact.get("phone") or "")
        name = str(contact.get("name") or "").strip()
        relation = str(contact.get("relation") or "").strip()
        message = str(contact.get("message") or "").strip() or (
            "تم العثور على صاحب هذا الرمز ويحتاج إلى مساعدة. يرجى التواصل معه فورًا." if ar
            else "The person linked to this emergency code has been found and may need help. Please make contact as soon as possible."
        )
        who = name or ("جهة الطوارئ" if ar else "Emergency contact")
        rel = relation or ("جهة اتصال محددة مسبقًا" if ar else "Preselected contact")
        call_href = "tel:" + phone
        sms_href = "sms:%s?body=%s" % (phone, quote(message))
        contact_html = '''
        <section class="em-card em-contact">
          <div class="em-title"><span>☎</span><h2>%s</h2></div>
          <div class="em-person"><div class="avatar">●</div><div><b>%s</b><small>%s</small></div></div>
          <div class="em-actions"><a class="em-call" href="%s">☎ %s</a><a class="em-sms" href="%s">💬 %s</a></div>
          <p class="em-note">%s</p>
        </section>
        ''' % (
            "جهة الاتصال في الطوارئ" if ar else "Emergency contact",
            html_lib.escape(who), html_lib.escape(rel), html_lib.escape(call_href, quote=True),
            "اتصال بجهة الطوارئ" if ar else "Call emergency contact", html_lib.escape(sms_href, quote=True),
            "إرسال تنبيه" if ar else "Send alert",
            "اختر الاتصال أو إرسال تنبيه وقت الحاجة." if ar else "Choose to call or send an alert when needed."
        )

    body = '''
    <main class="em-public">
      <section class="em-card em-head"><span class="em-badge">🚑 SymptoSense</span><h1>%s</h1><p>%s</p></section>
      <section class="em-card"><div class="em-title"><span>❤</span><h2>%s</h2></div>%s</section>
      %s
      <div class="em-warning">⚠️ %s</div>
    </main>
    ''' % (
        "معك وقت الحاجة" if ar else "Here when needed",
        "معلوماتك المهمة وتواصلك، جاهزة وقت الطوارئ." if ar else "Important information and emergency contact, ready when needed.",
        "معلومات الطوارئ" if ar else "Emergency information", medical_html, contact_html,
        "هذه المعلومات أضافها صاحب الرمز للمساعدة وقت الطوارئ، ولا تُعد سجلًا طبيًا موثقًا أو بديلًا عن التقييم الطبي." if ar else "This information was added by the code owner to help in an emergency and is not a verified medical record or a substitute for professional assessment."
    )
    return _safeid_public_response(_page(
        "معك وقت الحاجة | SymptoSense" if ar else "Here when needed | SymptoSense",
        body,
        desc=("معلومات طوارئ وجهة اتصال يحددها المستخدم مسبقًا." if ar else "User-selected emergency information and contact."),
        extra_css=public_css,
    ))


@app.route("/privacy")
def privacy():
    return privacy_page()

@app.route("/consent")
def consent():
    return consent_page()

@app.route("/privacy-center")
@login_required
def privacy_center():
    return privacy_center_page()

@app.route("/terms")
def terms():
    return terms_page()

@app.route("/contact")
def contact():
    return contact_page()

@app.route("/sources")
def sources():
    return sources_page()

@app.route("/chat")
def chat():
    if not _service_consent_ok():
        return redirect(_localized_url("/consent") + "?" + urlencode({"next": _localized_url("/chat")}))
    return chat_page()

@app.route("/firstaid")
def firstaid():
    return firstaid_page()

@app.route("/tips")
def tips():
    return tips_page()

@app.route("/relax")
def relax():
    return relax_page()

@app.route("/emergency")
def emergency():
    return emergency_page()

@app.route("/checkin")
def checkin():
    return checkin_page()

@app.route("/family")
@login_required
def family():
    return family_page()

@app.route("/family/<int:mid>")
@login_required
def family_detail(mid):
    return family_detail_page(mid)

@app.route("/search")
def search():
    return search_page()

@app.route("/calculators")
def calculators():
    return calculators_page()

@app.route("/profile")
@login_required
def profile():
    return user_profile_page()

@app.route("/command-center")
@app.route("/health-command-center")
@login_required
def health_command_center():
    return v50_wow.render_command_center(page=_page, lang=_lang(), account_uid=_ss_user_id(), data_uid=_data_user_id())

@app.route("/health-story")
@login_required
def health_story():
    return v50_wow.render_health_story(page=_page, lang=_lang(), uid=_data_user_id())

def _admin_page_gate(next_path: str):
    """Return an auth response for Admin-only HTML tools, otherwise None."""
    if not _ss_user_id():
        return redirect(url_for("login", next=next_path))
    current_user = _ss_user()
    if not _admin_session_valid():
        if getattr(g, "admin_2fa_required", False):
            session.clear()
            return redirect(url_for("login", next=next_path))
        if getattr(g, "admin_session_expired", False):
            return redirect(url_for("login", next=next_path))
        msg = "هذه الصفحة متاحة لحساب Admin فقط." if _lang() == "ar" else "This page is available to the Admin account only."
        return _page("Admin", '<div class="card" style="max-width:560px;margin:40px auto;text-align:center"><h2>🔒 Admin</h2><p class="muted">%s</p><a class="btn" href="/home">Home</a></div>' % msg), 403
    if not _admin_allowed("analytics"):
        _admin_auth_debug("competition_tools", current_user, granted=False, redirect_target="403")
        return _page("Admin", '<div class="card" style="max-width:560px;margin:40px auto;text-align:center"><h2>🔒 403</h2><p class="muted">Admin analytics access required.</p><a class="btn" href="/admin">Admin</a></div>'), 403
    return None

# Legacy public URLs are retained only as protected redirects so bookmarked links
# do not expose competition/research tooling to normal site visitors.
@app.route("/competition-dashboard")
@app.route("/competition")
def competition_dashboard_legacy():
    denied = _admin_page_gate("/admin/competition-dashboard")
    if denied is not None:
        return denied
    response = redirect(url_for("admin_competition_dashboard"), code=301)
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response

@app.route("/innovation-lab")
@app.route("/safety-lab")
def innovation_lab_legacy():
    denied = _admin_page_gate("/admin/innovation-lab")
    if denied is not None:
        return denied
    return redirect(url_for("admin_innovation_lab"))

def _detect_recurring_symptom_pattern(rows, lang, min_count=3, window_days=14):
    """Look across the user's recent saved analyses for a symptom that keeps
    coming back, and surface it as a proactive "see a doctor" nudge instead
    of waiting for the person to notice the pattern themselves.

    Returns a dict {"symptom":..., "count":..., "days":...} for the most
    frequent qualifying symptom, or None if nothing meets the threshold.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    counts = {}
    for row in rows:
        ts = str(row.get("timestamp") or "")
        try:
            ts_norm = ts.replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts_norm)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
        if dt < cutoff:
            continue
        for s in (row.get("symptoms") or []):
            key = str(s).strip().lower()
            if not key:
                continue
            entry = counts.setdefault(key, {"label": str(s).strip(), "count": 0})
            entry["count"] += 1
    if not counts:
        return None
    best = max(counts.values(), key=lambda x: x["count"])
    if best["count"] < min_count:
        return None
    return {"symptom": best["label"], "count": best["count"], "days": window_days}

def history_page():
    """Private analysis history. Data is scoped to the authenticated owner in SQL."""
    ar = _lang() == "ar"
    rows = advanced_features.user_analysis_rows(_data_user_id(), limit=200)
    title = "سجل التحليلات" if ar else "Analysis History"
    if not rows:
        body = '''
        <main class="history-shell">
          <section class="history-hero"><div><span class="eyebrow">📜 __TITLE__</span><h1>__EMPTY_H__</h1><p>__EMPTY_P__</p></div><a class="btn primary" href="/chat">__START__</a></section>
        </main>
        <style>.history-shell{max-width:900px;margin:auto}.history-hero{background:#fff;border:1px solid var(--v2-line);border-radius:22px;padding:clamp(22px,4vw,38px);box-shadow:var(--v2-shadow);display:flex;justify-content:space-between;gap:20px;align-items:center}.eyebrow{color:var(--v2-blue);font-weight:800}@media(max-width:650px){.history-hero{flex-direction:column;align-items:stretch}}</style>
        '''
        body = body.replace("__TITLE__", title).replace("__EMPTY_H__", "لا توجد تحليلات محفوظة بعد" if ar else "No saved analyses yet").replace("__EMPTY_P__", "أكمل تحليلًا لبدء سجل خاص بحسابك." if ar else "Complete an assessment to start your private history.").replace("__START__", "بدء تحليل" if ar else "Start an analysis")
        return _page(title, body)

    from html import escape
    pattern = _detect_recurring_symptom_pattern(rows, "ar" if ar else "en")
    pattern_banner = ""
    if pattern:
        pattern_banner = (
            '<section class="history-pattern-banner">'
            '<b>🔁 ' + (escape(f"لاحظنا تكرارًا: \u2018{pattern['symptom']}\u2019 سُجِّل {pattern['count']} مرات خلال آخر {pattern['days']} يومًا.") if ar
                        else escape(f"We noticed a pattern: \u2018{pattern['symptom']}\u2019 was logged {pattern['count']} times in the last {pattern['days']} days.")) + '</b>'
            '<p>' + (escape("التكرار وحده لا يعني بالضرورة وجود مشكلة، لكن يُفضّل مراجعة الطبيب لتقييم السبب إذا استمر النمط.") if ar
                     else escape("Repetition alone doesn't necessarily mean something is wrong, but it's worth seeing a doctor to evaluate the cause if the pattern continues.")) + '</p>'
            '</section>'
        )
    cards=[]
    for row in rows:
        result=row.get("result") or {}
        risk=(result.get("risk_level") or row.get("urgency") or "low").lower()
        risk_map={
          "low": ("منخفض" if ar else "Low risk", "low"),
          "medium": ("يحتاج متابعة" if ar else "Needs follow-up", "medium"),
          "high": ("عاجل" if ar else "Urgent", "high"),
          "urgent": ("عاجل" if ar else "Urgent", "high"),
        }
        risk_label,risk_cls=risk_map.get(risk,(escape(str(risk)),"medium"))
        symptoms=', '.join(escape(str(x)) for x in (row.get('symptoms') or [])) or '—'
        date=escape(str(row.get('timestamp') or '—'))[:16].replace('T',' ')
        duration=escape(str(row.get('duration') or '—'))
        edit_url=('/ar/chat' if ar else '/en/chat')+f"?reanalyze={int(row['id'])}&edit=1&from=history"
        cards.append(f'''<article class="history-card">
          <div class="history-card-top"><div><small>{date}</small><h3>{symptoms}</h3></div><span class="risk-pill {risk_cls}">{risk_label}</span></div>
          <p class="muted">{'المدة' if ar else 'Duration'}: {duration}</p>
          <div class="history-actions"><a class="btn ghost" href="/history/{int(row['id'])}">{'عرض التحليل' if ar else 'View Analysis'}</a><a class="btn ghost edit-answers-link" href="{edit_url}">✏️ {'تعديل إجاباتي' if ar else 'Edit answers'}</a><button type="button" class="btn ghost danger-lite" data-ss-click="deleteAnalysis" data-ss-args="[{int(row['id'])}]">{'حذف' if ar else 'Delete'}</button></div>
        </article>''')
    body='''
    <main class="history-shell">
      <section class="history-heading"><div><span class="eyebrow">📜 __TITLE__</span><h1>__H1__</h1><p>__SUB__</p></div><a class="btn primary" href="/chat">__NEW__</a></section>
      __PATTERN_BANNER__
      <section class="history-grid">__CARDS__</section>
    </main>
    <style>
    .history-shell{max-width:980px;margin:auto;display:grid;gap:16px}.history-heading,.history-card{background:#fff;border:1px solid var(--v2-line);border-radius:20px;box-shadow:var(--v2-shadow)}.history-heading{padding:24px;display:flex;justify-content:space-between;gap:20px;align-items:center}.history-pattern-banner{background:#FFF8E8;border:1px solid #F3DFA6;border-radius:18px;padding:18px 22px}.history-pattern-banner b{display:block;color:#7A5B00;font-size:15px}.history-pattern-banner p{margin:6px 0 0;color:#8A6400;font-size:13px;line-height:1.7}.history-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.history-card{padding:18px}.history-card-top{display:flex;justify-content:space-between;gap:14px;align-items:flex-start}.history-card h3{margin:5px 0 0;font-size:17px}.history-card small{color:var(--v2-muted)}.risk-pill{padding:6px 10px;border-radius:999px;font-size:12px;font-weight:800;white-space:nowrap}.risk-pill.low{background:var(--v2-green-bg);color:var(--v2-green)}.risk-pill.medium{background:#FFF6DB;color:#8A6400}.risk-pill.high{background:#FDECEC;color:var(--v2-red)}.history-actions{display:flex;gap:8px;margin-top:14px}.danger-lite{color:var(--v2-red)!important;border-color:#efcaca!important}@media(max-width:700px){.history-grid{grid-template-columns:1fr}.history-heading{flex-direction:column;align-items:stretch}.history-card-top{flex-direction:column}}
    </style>
    <script>async function deleteAnalysis(id){if(!confirm(__CONFIRM__))return;const r=await fetch('/api/analysis/'+id,{method:'DELETE'});if(r.ok)location.reload();else alert(__ERROR__);}</script>
    '''
    body=body.replace('__TITLE__',title).replace('__H1__','تحليلاتي السابقة' if ar else 'My previous analyses').replace('__SUB__','هذه النتائج خاصة بحسابك ولا يستطيع مستخدم آخر فتحها.' if ar else 'These results are private to your account and cannot be opened by another user.').replace('__NEW__','تحليل جديد' if ar else 'New analysis').replace('__PATTERN_BANNER__',pattern_banner).replace('__CARDS__',''.join(cards)).replace('__CONFIRM__',_json_for_script('هل تريد حذف هذا التحليل؟ لا يمكن التراجع عن الحذف.' if ar else 'Delete this analysis? This cannot be undone.')).replace('__ERROR__',_json_for_script('تعذر حذف التحليل.' if ar else 'Unable to delete the analysis.'))
    return _page(title, body)

@app.route("/history")
@app.route("/my-results")
@app.route("/health-report")
@login_required
def history():
    return history_page()

@app.route("/history/<int:record_id>")
@login_required
def history_detail(record_id):
    return analysis_detail_page(record_id)

@app.route("/health-insights")
@app.route("/health-journey")
@app.route("/health-twin")
def health_history_aliases():
    return redirect(url_for("health_story"))

# ---- V174 consolidated information architecture + language-prefixed routes ----

def _html_from_response(value):
    if isinstance(value, Response):
        return value.get_data(as_text=True)
    if isinstance(value, tuple):
        value = value[0]
        if isinstance(value, Response):
            return value.get_data(as_text=True)
    return str(value or "")


def _extract_main_as_div(rendered):
    text = _html_from_response(rendered)
    match = re.search(r"<main\b([^>]*)>(.*?)</main>", text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return '<div class="card">%s</div>' % html_lib.escape(text[:1000])
    return '<div%s>%s</div>' % (match.group(1), match.group(2))


def _extract_styles(rendered, markers=()):
    text = _html_from_response(rendered)
    styles = re.findall(r"<style[^>]*>(.*?)</style>", text, flags=re.IGNORECASE | re.DOTALL)
    if not markers:
        return ""
    return "\n".join(css for css in styles if any(marker in css for marker in markers))


def _extract_scripts(rendered, markers=()):
    text = _html_from_response(rendered)
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", text, flags=re.IGNORECASE | re.DOTALL)
    if not markers:
        return ""
    chosen = [js for js in scripts if any(marker in js for marker in markers)]
    return "".join('<script>%s</script>' % js for js in chosen)


def how_we_work_page():
    """One public page for trust, methodology and sources."""
    ar = _lang() == "ar"
    trust_html = trust()
    method_html = methodology()
    source_html = sources()
    trust_fragment = _extract_main_as_div(trust_html)
    method_fragment = _extract_main_as_div(method_html)
    source_fragment = _extract_main_as_div(source_html)
    extra_css = _extract_styles(trust_html, (".trust-page", ".trust-hero")) + "\n" + _extract_styles(method_html, (".method-page", ".method-hero"))
    shell_css = r"""
    .ia-hub{width:min(1120px,100%);margin:auto;display:grid;gap:16px}.ia-hub-head{padding:24px;border:1px solid #dce8f0;border-radius:22px;background:linear-gradient(135deg,#f8fcff,#f3f9fd)}.ia-hub-head h1{margin:0;color:#163b5c;font-size:clamp(28px,4vw,42px)}.ia-hub-head p{margin:8px 0 0;color:#60788b;line-height:1.8}.ia-tabs{display:flex;gap:8px;flex-wrap:wrap;position:sticky;top:8px;z-index:5;padding:8px;border:1px solid #dce8f0;border-radius:16px;background:rgba(255,255,255,.94);backdrop-filter:blur(10px)}.ia-tabs a{flex:1;min-width:150px;text-align:center;text-decoration:none;padding:10px 12px;border-radius:11px;color:#456276;font-weight:900}.ia-tabs a.on,.ia-tabs a:hover{background:#eaf5fc;color:#1e6e9f}.ia-panel{display:none}.ia-panel.on{display:block}.ia-panel>div{width:100%!important;max-width:none!important;margin:0!important}.ia-anchor{scroll-margin-top:90px}@media(max-width:620px){.ia-hub-head{padding:19px 16px}.ia-tabs{position:static}.ia-tabs a{min-width:0;font-size:12px}}
    """
    body = '''<div class="ia-hub">
      <section class="ia-hub-head"><h1>%s</h1><p>%s</p></section>
      <nav class="ia-tabs" aria-label="%s"><a href="#trust" data-ia-tab="trust">%s</a><a href="#methodology" data-ia-tab="methodology">%s</a><a href="#sources" data-ia-tab="sources">%s</a></nav>
      <section id="trust" class="ia-panel ia-anchor" data-ia-panel="trust">%s</section>
      <section id="methodology" class="ia-panel ia-anchor" data-ia-panel="methodology">%s</section>
      <section id="sources" class="ia-panel ia-anchor" data-ia-panel="sources">%s</section>
    </div>
    <script>(function(){var tabs=[].slice.call(document.querySelectorAll('[data-ia-tab]'));var panels=[].slice.call(document.querySelectorAll('[data-ia-panel]'));function show(name){if(!name||!document.querySelector('[data-ia-panel="'+name+'"]'))name='trust';tabs.forEach(function(a){a.classList.toggle('on',a.dataset.iaTab===name);});panels.forEach(function(p){p.classList.toggle('on',p.dataset.iaPanel===name);});}tabs.forEach(function(a){a.addEventListener('click',function(){show(this.dataset.iaTab);});});window.addEventListener('hashchange',function(){show(location.hash.slice(1));});show(location.hash.slice(1));})();</script>''' % (
        "كيف يعمل SymptoSense" if ar else "How SymptoSense works",
        "الثقة والأمان، المنهجية، والمصادر الطبية في مكان واحد." if ar else "Trust and safety, methodology, and medical sources in one place.",
        "أقسام كيف نعمل" if ar else "How we work sections",
        "الثقة والأمان" if ar else "Trust & safety",
        "المنهجية" if ar else "Methodology",
        "المصادر" if ar else "Sources",
        trust_fragment, method_fragment, source_fragment,
    )
    return _page(
        "كيف يعمل SymptoSense | الثقة والمنهجية والمصادر" if ar else "How SymptoSense Works | Trust, Methodology & Sources",
        body,
        desc=("تعرف على منهجية SymptoSense، قواعد السلامة، حدود النظام، والمصادر الطبية الموثوقة في صفحة واحدة." if ar else "Explore SymptoSense methodology, safety rules, system boundaries, and trusted medical sources in one page."),
        extra_css=extra_css + shell_css,
    )


def health_record_hub_page():
    """One private route for results, insights, timeline and Health Twin tabs."""
    ar = _lang() == "ar"
    tab = str(request.args.get("tab") or "results").lower()
    if tab not in {"results", "insights", "timeline", "twin"}:
        tab = "results"
    if tab == "results":
        rendered = history_page()
        fragment = _extract_main_as_div(rendered)
        feature_css = _extract_styles(rendered, (".history-shell", ".history-heading"))
        feature_scripts = _extract_scripts(rendered, ("deleteAnalysis",))
    else:
        rendered = health_story()
        fragment = _extract_main_as_div(rendered)
        feature_css = _extract_styles(rendered, (".hs-page", ".hs-hero", ".hs-timeline"))
        feature_scripts = _extract_scripts(rendered, ("hs-filter", "healthStoryTimeline"))
    labels = {
        "results": ("النتائج", "Results"),
        "insights": ("الرؤى", "Insights"),
        "timeline": ("الخط الزمني", "Timeline"),
        "twin": ("Health Twin", "Health Twin"),
    }
    tabs = ''.join(
        '<a class="%s" href="%s?tab=%s">%s</a>' % (
            "on" if key == tab else "", _localized_url("/health-record"), key, html_lib.escape(labels[key][0 if ar else 1])
        ) for key in ("results", "insights", "timeline", "twin")
    ) + '<a href="%s">%s</a>' % (_localized_url("/health-file"), "ملفي الصحي" if ar else "Health file") + '<a href="%s">%s</a>' % (_localized_url("/vitals"), "قياساتي" if ar else "My vitals")
    note = "" if tab in {"results", "timeline"} else (
        '<div class="hr-context">%s</div>' % (
            "يعرض هذا التبويب حاليًا سياق رحلتك الصحية المحفوظة، إلى أن تتوسع طبقة الرؤى/Health Twin بمخرجات مستقلة." if ar else
            "This tab currently uses your saved health-story context until Insights/Health Twin gains a dedicated output layer."
        )
    )
    css = r"""
    .hr-hub{width:min(1180px,100%);margin:auto;display:grid;gap:14px}.hr-tabs{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;padding:8px;background:#fff;border:1px solid #dce8f0;border-radius:16px;position:sticky;top:8px;z-index:5}.hr-tabs a{text-align:center;text-decoration:none;padding:10px;border-radius:11px;font-weight:900;color:#557086}.hr-tabs a.on{background:#eaf5fc;color:#1e6e9f}.hr-context{padding:11px 13px;border-radius:12px;background:#f8fbfe;border:1px solid #dce8f0;color:#61798b;font-size:12px;line-height:1.7}.hr-content>div{max-width:none!important;width:100%!important;margin:0!important}@media(max-width:620px){.hr-tabs{grid-template-columns:1fr 1fr;position:static}.hr-tabs a{font-size:12px}}
    """
    body = '<div class="hr-hub"><nav class="hr-tabs" aria-label="%s">%s</nav>%s<section class="hr-content">%s</section>%s</div>' % (
        "سجلي الصحي" if ar else "My health record", tabs, note, fragment, feature_scripts
    )
    return _page("سجلي الصحي" if ar else "My Health Record", body, extra_css=feature_css + css)


@app.route("/<lang_code>/")
def localized_home(lang_code):
    if lang_code not in _SUPPORTED_LANGS:
        abort(404)
    return home_page()


@app.route("/<lang_code>/<path:subpath>", methods=["GET", "POST"])
def localized_page_dispatch(lang_code, subpath):
    if lang_code not in _SUPPORTED_LANGS:
        abort(404)
    subpath = str(subpath or "").strip("/")
    # A few localized pages contain same-page POST forms. Keep POST narrowly
    # enabled only for those real form flows; every other localized page remains
    # GET-only so the language dispatcher cannot accidentally expose extra POST
    # surfaces.
    localized_post_pages = {"verify-email", "forgot-password", "settings"}
    localized_reset_token = subpath.startswith("reset-password/") and bool(subpath.split("/", 1)[1].strip("/")) and "/" not in subpath.split("/", 1)[1].strip("/")
    localized_verify_token = subpath.startswith("verify-email/") and bool(subpath.split("/", 1)[1].strip("/")) and "/" not in subpath.split("/", 1)[1].strip("/")
    if request.method == "POST" and subpath not in localized_post_pages and not localized_reset_token:
        abort(405)
    if not subpath or subpath == "home":
        return redirect(f"/{lang_code}/", code=301)
    if subpath == "admin" or subpath.startswith("admin/"):
        return redirect("/" + subpath, code=302)
    # Compatibility for previously generated/cached language-prefixed auth
    # links. New emails use the canonical language-neutral token path.
    if localized_reset_token:
        return reset_password(subpath.split("/", 1)[1])
    if localized_verify_token:
        if request.method != "GET":
            abort(405)
        return verify_email_token(subpath.split("/", 1)[1])
    localized_aliases = {
        "about-us": ("/about", ""), "site-info": ("/about", ""),
        # Compatibility for old links/bookmarks that used /<lang>/symptoms.
        "symptoms": ("/chat", ""),
        "trust": ("/how-we-work", "trust"), "methodology": ("/how-we-work", "methodology"),
        "sources": ("/how-we-work", "sources"),
        "command-center": ("/health-command-center", ""),
        "history": ("/health-record?tab=results", ""), "my-results": ("/health-record?tab=results", ""),
        "health-report": ("/health-record?tab=results", ""), "health-insights": ("/health-record?tab=insights", ""),
        "health-journey": ("/health-record?tab=timeline", ""), "health-twin": ("/health-record?tab=twin", ""),
        "health-story": ("/health-record?tab=timeline", ""),
    }
    if subpath in localized_aliases:
        suffix, fragment = localized_aliases[subpath]
        target = _localized_url(suffix, lang_code)
        if fragment:
            target += "#" + fragment
        return redirect(target, code=301)
    if subpath == "about":
        return about_us_page()
    if subpath == "how-we-work":
        return how_we_work_page()
    if subpath == "privacy":
        return privacy_page()
    if subpath == "health-record":
        if not _ss_user_id():
            return redirect(url_for("login", next=request.full_path.rstrip("?")))
        return health_record_hub_page()
    if subpath.startswith("health-record/"):
        rid = subpath.split("/", 1)[1]
        if rid.isdigit():
            return history_detail(int(rid))
        abort(404)
    if subpath.startswith("health-library/"):
        parts = subpath.split("/", 2)
        if len(parts) == 3:
            return health_library_detail(parts[1], parts[2])
        abort(404)
    if subpath.startswith("family/"):
        mid = subpath.split("/", 1)[1]
        if mid.isdigit():
            return family_detail(int(mid))
        abort(404)
    endpoint_map = {
        "chat": "chat", "blood": "blood", "assistant": "assistant_entry",
        "search": "search", "calculators": "calculators", "meds": "meds",
        "emergency": "emergency", "firstaid": "firstaid", "tips": "tips", "relax": "relax",
        "health-library": "health_library_index", "health-trends": "health_trends",
        "community-dashboard": "community_dashboard", "terms": "terms", "contact": "contact",
        "profile": "profile", "family": "family", "checkin": "checkin", "safeid": "safeid",
        "settings": "settings", "manage": "manage_page", "memory": "memory_page",
        "login": "login", "register": "register", "verify-email": "verify_email_pending",
        "forgot-password": "forgot_password", "health-command-center": "health_command_center",
        "privacy-center": "privacy_center", "consent": "consent", "health-file": "health_file_page", "vitals": "vitals_page",
    }
    endpoint = endpoint_map.get(subpath)
    if not endpoint:
        abort(404)
    view = app.view_functions.get(endpoint)
    if not view:
        abort(404)
    return view()


# ---- Smart Account System routes ----

def _auth_csrf_token():
    """Return a session-bound token used only by Authentication HTML forms."""
    if not session.get("auth_csrf"):
        session["auth_csrf"] = secrets.token_urlsafe(32)
    return session["auth_csrf"]

def _auth_csrf_valid():
    supplied = request.form.get("csrf_token", "") or request.headers.get("X-CSRF-Token", "")
    expected = session.get("auth_csrf", "")
    return bool(supplied and expected and secrets.compare_digest(str(supplied), str(expected)))

def _auth_form_expired_message(lang):
    return "انتهت صلاحية النموذج. حدّث الصفحة وحاول مجددًا." if lang == "ar" else "This form expired. Refresh the page and try again."

def _auth_email_provider_state():
    brevo_values={
        "api_key":os.environ.get("BREVO_API_KEY","").strip(),
        "sender_email":os.environ.get("BREVO_FROM_EMAIL","").strip().lower(),
        "sender_name":os.environ.get("BREVO_FROM_NAME","").strip(),
    }
    # Brevo uses HTTPS, so it works on Railway plans where outbound SMTP is
    # disabled. Its presence takes priority over SMTP and Resend.
    smtp_complete=all(os.environ.get(name, "").strip() for name in ("SMTP_HOST","SMTP_PORT","SMTP_USERNAME","SMTP_PASSWORD","SMTP_FROM"))
    resend_complete=all(os.environ.get(name, "").strip() for name in ("RESEND_API_KEY","RESEND_FROM"))
    # Select a partial Brevo configuration only when there is no complete
    # alternative. This preserves useful diagnostics while preventing a stale
    # BREVO_FROM_NAME/API key from blocking a working SMTP or Resend setup.
    if all(brevo_values.values()) or (any(brevo_values.values()) and not smtp_complete and not resend_complete):
        missing=[]
        if not brevo_values["api_key"]: missing.append("BREVO_API_KEY")
        if not brevo_values["sender_email"]: missing.append("BREVO_FROM_EMAIL")
        if not brevo_values["sender_name"]: missing.append("BREVO_FROM_NAME")
        invalid=[]
        if brevo_values["api_key"].lower() in {"replace_me","changeme","your_brevo_api_key"} or "ضع" in brevo_values["api_key"]:
            invalid.append("BREVO_API_KEY_PLACEHOLDER")
        if brevo_values["sender_email"] and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$",brevo_values["sender_email"]):
            invalid.append("BREVO_FROM_EMAIL_INVALID")
        return {
            "provider":"brevo","configured":not missing and not invalid,
            "missing":missing,"invalid":invalid,
            "sender_address_valid":bool(brevo_values["sender_email"] and "BREVO_FROM_EMAIL_INVALID" not in invalid),
            "sender_domain":brevo_values["sender_email"].rsplit("@",1)[1] if "@" in brevo_values["sender_email"] else "",
            "uses_resend_test_domain":False,
            "production_recipient_delivery_ready":bool(not missing and not invalid),
            "site_url":_site_url(),
            "site_url_source": ("SITE_URL" if os.environ.get("SITE_URL", "").strip() else ("RAILWAY_PUBLIC_DOMAIN" if os.environ.get("RAILWAY_PUBLIC_DOMAIN", "").strip() else ("request_host" if has_request_context() else "local_fallback"))),
        }
    smtp_values={
        "host": os.environ.get("SMTP_HOST", "").strip(),
        "port": os.environ.get("SMTP_PORT", "").strip(),
        "username": os.environ.get("SMTP_USERNAME", "").strip(),
        "password": os.environ.get("SMTP_PASSWORD", "").strip(),
        "sender": os.environ.get("SMTP_FROM", "").strip(),
    }
    # Any SMTP value explicitly selects SMTP, so stale Resend variables cannot
    # override a Gmail deployment.
    if all(smtp_values.values()) or (any(smtp_values.values()) and not resend_complete):
        missing=[]
        env_names={"host":"SMTP_HOST","port":"SMTP_PORT","username":"SMTP_USERNAME","password":"SMTP_PASSWORD","sender":"SMTP_FROM"}
        for key,env_name in env_names.items():
            if not smtp_values[key]: missing.append(env_name)
        invalid=[]
        sender_address=parseaddr(smtp_values["sender"])[1].strip().lower() if smtp_values["sender"] else ""
        if smtp_values["sender"] and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$",sender_address):
            invalid.append("SMTP_FROM_INVALID")
        try:
            smtp_port=int(smtp_values["port"] or 0)
            if not (1 <= smtp_port <= 65535): raise ValueError
        except (TypeError,ValueError):
            smtp_port=0
            if smtp_values["port"]: invalid.append("SMTP_PORT_INVALID")
        use_tls=os.environ.get("SMTP_USE_TLS", "1").strip().lower() not in {"0","false","no","off"}
        return {
            "provider":"smtp","configured":not missing and not invalid,
            "missing":missing,"invalid":invalid,
            "sender_address_valid":bool(sender_address and "SMTP_FROM_INVALID" not in invalid),
            "sender_domain":sender_address.rsplit("@",1)[1] if "@" in sender_address else "",
            "uses_resend_test_domain":False,
            "production_recipient_delivery_ready":bool(not missing and not invalid),
            "smtp_host":smtp_values["host"],"smtp_port":smtp_port,"smtp_use_tls":use_tls,
            "site_url":_site_url(),
            "site_url_source": ("SITE_URL" if os.environ.get("SITE_URL", "").strip() else ("RAILWAY_PUBLIC_DOMAIN" if os.environ.get("RAILWAY_PUBLIC_DOMAIN", "").strip() else ("request_host" if has_request_context() else "local_fallback"))),
        }
    missing=[]
    api_key=os.environ.get("RESEND_API_KEY", "").strip()
    sender=os.environ.get("RESEND_FROM", "").strip()
    if not api_key: missing.append("RESEND_API_KEY")
    if not sender: missing.append("RESEND_FROM")
    sender_address=parseaddr(sender)[1].strip().lower() if sender else ""
    sender_domain=sender_address.rsplit("@",1)[1] if "@" in sender_address else ""
    invalid=[]
    if api_key and ("your_resend" in api_key.lower() or re.match(r"^re_x+$", api_key.lower()) or api_key.lower() in {"resend_api_key", "replace_me", "changeme"}):
        invalid.append("RESEND_API_KEY_PLACEHOLDER")
    if sender and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$",sender_address): invalid.append("RESEND_FROM_INVALID")
    if sender_domain in {"your_verified_domain","your_verified_domain.com","example.com"} or "your_" in sender_domain or "your_verified_domain" in sender_domain:
        invalid.append("RESEND_FROM_PLACEHOLDER")
    return {
        "provider":"resend",
        "configured": not missing and not invalid,
        "missing": missing,
        "invalid": invalid,
        "sender_address_valid": bool(sender_address and not invalid),
        "sender_domain": sender_domain,
        "uses_resend_test_domain": sender_domain == "resend.dev",
        "production_recipient_delivery_ready": bool(not missing and not invalid and sender_domain != "resend.dev"),
        "site_url": _site_url(),
        "site_url_source": ("SITE_URL" if os.environ.get("SITE_URL", "").strip() else ("RAILWAY_PUBLIC_DOMAIN" if os.environ.get("RAILWAY_PUBLIC_DOMAIN", "").strip() else ("request_host" if has_request_context() else "local_fallback"))),
    }

def _send_auth_email_smtp(email, subject, html, category, state):
    """Send auth mail over STARTTLS/SSL without logging credentials or PII."""
    sender=os.environ.get("SMTP_FROM", "").strip()
    username=os.environ.get("SMTP_USERNAME", "").strip()
    password=os.environ.get("SMTP_PASSWORD", "").strip()
    if str(state.get("smtp_host") or "").lower()=="smtp.gmail.com":
        password=password.replace(" ", "")
    message=EmailMessage()
    message["From"]=sender; message["To"]=email; message["Subject"]=subject
    plain=re.sub(r"<[^>]+>", " ", html or "")
    message.set_content(re.sub(r"\s+", " ", plain).strip())
    message.add_alternative(html, subtype="html")
    host=state["smtp_host"]; port=int(state["smtp_port"])
    try:
        if port==465:
            with smtplib.SMTP_SSL(host,port,timeout=15,context=ssl.create_default_context()) as server:
                server.login(username,password); server.send_message(message)
        else:
            with smtplib.SMTP(host,port,timeout=15) as server:
                server.ehlo()
                if state.get("smtp_use_tls",True):
                    server.starttls(context=ssl.create_default_context()); server.ehlo()
                server.login(username,password); server.send_message(message)
        app.logger.info("Auth email accepted by SMTP provider; category=%s",category)
        return True,None
    except smtplib.SMTPAuthenticationError:
        app.logger.warning("Auth SMTP authentication failed; category=%s",category)
        return False,"email_smtp_auth_failed"
    except smtplib.SMTPRecipientsRefused:
        app.logger.warning("Auth SMTP recipient rejected; category=%s",category)
        return False,"email_recipient_rejected"
    except (smtplib.SMTPException,OSError,TimeoutError):
        app.logger.warning("Auth SMTP delivery failed; category=%s",category)
        return False,"email_smtp_connection_failed"

def _send_auth_email_brevo(email, subject, html, category):
    """Send auth mail through Brevo's HTTPS API without logging PII/secrets."""
    try:
        import requests
        response=requests.post(
            "https://api.brevo.com/v3/smtp/email",timeout=15,
            headers={
                "accept":"application/json","content-type":"application/json",
                "api-key":os.environ.get("BREVO_API_KEY","").strip(),
            },
            json={
                "sender":{"name":os.environ.get("BREVO_FROM_NAME","").strip(),"email":os.environ.get("BREVO_FROM_EMAIL","").strip().lower()},
                "to":[{"email":email}],"subject":subject,"htmlContent":html,
                "tags":[re.sub(r"[^A-Za-z0-9_-]","_",category)[:64] or "auth"],
            },
        )
        if response.status_code < 300:
            app.logger.info("Auth email accepted by Brevo API; category=%s status=%s",category,response.status_code)
            return True,None
        status=int(response.status_code or 0); code=""
        try:
            payload=response.json() or {}; code=str(payload.get("code") or "").lower()
        except Exception as exc: app.logger.debug("Non-critical operation skipped: %s", type(exc).__name__)
        if status in {401,403}: reason="email_brevo_auth_failed"
        elif status==429: reason="email_brevo_rate_limited"
        elif status in {400,404} and ("sender" in code or "invalid_parameter" in code): reason="email_brevo_sender_invalid"
        else: reason="email_brevo_delivery_failed"
        app.logger.warning("Auth Brevo API rejected request; category=%s status=%s diagnostic=%s",category,status,reason)
        return False,reason
    except (OSError,TimeoutError):
        app.logger.warning("Auth Brevo API connection failed; category=%s",category)
        return False,"email_brevo_connection_failed"
    except Exception as exc:
        app.logger.warning("Auth Brevo API delivery failed; category=%s error_type=%s",category,type(exc).__name__)
        return False,"email_brevo_delivery_failed"

def _classify_resend_error(response):
    """Map Resend failures to safe diagnostic codes without logging PII."""
    status=int(getattr(response,"status_code",0) or 0)
    name=""; message=""
    try:
        payload=response.json() if response is not None else {}
        if isinstance(payload,dict):
            name=str(payload.get("name") or payload.get("code") or "")[:80]
            message=str(payload.get("message") or "").lower()
    except Exception:
        logging.getLogger(__name__).warning("Handled exception in _classify_resend_error; fallback applied (handler 12774)")
        pass
    if status in {401,403} and (name=="invalid_api_key" or "api key is invalid" in message):
        return "email_invalid_api_key", name or "invalid_api_key"
    if status==403 and ("only send testing emails" in message or "testing emails to your own" in message):
        return "email_test_domain_restricted", name or "validation_error"
    if status==403 and ("domain" in message and "not verified" in message):
        return "email_sender_domain_unverified", name or "validation_error"
    if status==422:
        return "email_validation_error", name or "validation_error"
    return "email_provider_error", name or ("http_%s" % status if status else "provider_error")

def _auth_email_plain_text(html):
    """Create a readable text alternative for transactional auth messages."""
    text=re.sub(r"<br\s*/?>", "\n", html or "", flags=re.I)
    text=re.sub(r"</(?:p|div|h[1-6]|li|tr)>", "\n", text, flags=re.I)
    text=re.sub(r"<[^>]+>", " ", text)
    text=html_lib.unescape(text)
    text=re.sub(r"[ \t]+", " ", text)
    text=re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()

def _auth_email_fallback_candidates(primary_provider):
    """Return fully configured alternate providers without exposing secrets."""
    candidates=[]

    if primary_provider != "brevo":
        api_key=os.environ.get("BREVO_API_KEY","").strip()
        sender=os.environ.get("BREVO_FROM_EMAIL","").strip().lower()
        sender_name=os.environ.get("BREVO_FROM_NAME","").strip()
        placeholder=api_key.lower() in {"replace_me","changeme","your_brevo_api_key"} or "ضع" in api_key
        if api_key and sender and sender_name and not placeholder and re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$",sender):
            candidates.append(("brevo",None))

    if primary_provider != "smtp":
        host=os.environ.get("SMTP_HOST","").strip()
        port_raw=os.environ.get("SMTP_PORT","").strip()
        username=os.environ.get("SMTP_USERNAME","").strip()
        password=os.environ.get("SMTP_PASSWORD","").strip()
        sender=os.environ.get("SMTP_FROM","").strip()
        sender_address=parseaddr(sender)[1].strip().lower() if sender else ""
        try:
            port=int(port_raw)
            port_ok=1 <= port <= 65535
        except (TypeError,ValueError):
            port=0; port_ok=False
        if host and username and password and sender and port_ok and re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$",sender_address):
            candidates.append(("smtp",{
                "smtp_host":host,"smtp_port":port,
                "smtp_use_tls":os.environ.get("SMTP_USE_TLS","1").strip().lower() not in {"0","false","no","off"},
            }))

    if primary_provider != "resend":
        api_key=os.environ.get("RESEND_API_KEY","").strip()
        sender=os.environ.get("RESEND_FROM","").strip()
        sender_address=parseaddr(sender)[1].strip().lower() if sender else ""
        sender_domain=sender_address.rsplit("@",1)[1] if "@" in sender_address else ""
        key_placeholder=bool(api_key and ("your_resend" in api_key.lower() or re.match(r"^re_x+$",api_key.lower()) or api_key.lower() in {"resend_api_key","replace_me","changeme"}))
        sender_placeholder=bool(sender_domain in {"your_verified_domain","your_verified_domain.com","example.com"} or "your_" in sender_domain or "your_verified_domain" in sender_domain)
        if api_key and sender and not key_placeholder and not sender_placeholder and re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$",sender_address):
            candidates.append(("resend",None))

    # Keep failover deterministic and favor HTTPS APIs on Railway.
    order={"brevo":0,"resend":1,"smtp":2}
    candidates.sort(key=lambda item: order.get(item[0],99))
    return candidates

def _send_auth_email_resend(email, subject, html, category):
    try:
        import requests
        response=requests.post(
            "https://api.resend.com/emails", timeout=12,
            headers={"Authorization":"Bearer "+os.environ.get("RESEND_API_KEY", "").strip(), "Content-Type":"application/json"},
            json={
                "from": os.environ.get("RESEND_FROM", "").strip(),
                "to": [email],
                "subject": subject,
                "html": html,
                "text": _auth_email_plain_text(html),
                "tags": [{"name":"category","value":re.sub(r"[^A-Za-z0-9_-]", "_", category)[:64] or "auth"}],
            },
        )
        if response.status_code < 300:
            app.logger.info("Auth email accepted by Resend API; category=%s status=%s", category, response.status_code)
            return True, None
        safe_error, provider_code=_classify_resend_error(response)
        app.logger.warning("Auth Resend API rejected request; category=%s status=%s provider_code=%s diagnostic=%s", category, response.status_code, provider_code, safe_error)
        return False, safe_error
    except Exception as exc:
        app.logger.warning("Auth Resend API send failed; category=%s error_type=%s", category, type(exc).__name__)
        return False, "email_provider_error"

def _send_auth_email_via(provider, email, subject, html, category, state=None):
    if provider=="brevo":
        return _send_auth_email_brevo(email,subject,html,category)
    if provider=="smtp":
        return _send_auth_email_smtp(email,subject,html,category,state or {})
    if provider=="resend":
        return _send_auth_email_resend(email,subject,html,category)
    return False,"email_not_configured"

def _send_auth_email(email, subject, html, category="auth"):
    """Send auth email, then fail over to another fully configured provider."""
    state=_auth_email_provider_state()
    if not state["configured"]:
        app.logger.warning("Auth email provider not configured; missing=%s invalid=%s", ",".join(state["missing"]), ",".join(state.get("invalid") or []))
        if state.get("provider")=="brevo":
            if "BREVO_API_KEY_PLACEHOLDER" in (state.get("invalid") or []): return False,"email_brevo_key_placeholder"
            if "BREVO_FROM_EMAIL_INVALID" in (state.get("invalid") or []): return False,"email_brevo_sender_invalid"
            return False,"email_brevo_not_configured"
        if state.get("provider")=="smtp":
            if "SMTP_FROM_INVALID" in (state.get("invalid") or []): return False,"email_smtp_sender_invalid"
            if "SMTP_PORT_INVALID" in (state.get("invalid") or []): return False,"email_smtp_port_invalid"
            return False,"email_smtp_not_configured"
        if "RESEND_FROM_PLACEHOLDER" in (state.get("invalid") or []):
            return False, "email_sender_placeholder"
        if "RESEND_API_KEY_PLACEHOLDER" in (state.get("invalid") or []):
            return False, "email_api_key_placeholder"
        if state.get("invalid"):
            return False, "email_sender_invalid"
        return False, "email_not_configured"

    primary=state.get("provider") or "resend"
    sent,reason=_send_auth_email_via(primary,email,subject,html,category,state)
    if sent:
        return True,None

    primary_reason=reason or "email_provider_error"
    for fallback,fallback_state in _auth_email_fallback_candidates(primary):
        app.logger.warning("Auth email primary provider failed; category=%s primary=%s diagnostic=%s trying_fallback=%s", category,primary,primary_reason,fallback)
        fallback_sent,fallback_reason=_send_auth_email_via(fallback,email,subject,html,category,fallback_state)
        if fallback_sent:
            app.logger.info("Auth email failover succeeded; category=%s provider=%s",category,fallback)
            return True,None
        app.logger.warning("Auth email fallback failed; category=%s provider=%s diagnostic=%s",category,fallback,fallback_reason or "email_provider_error")

    # Preserve the primary diagnostic because it explains why the preferred
    # production provider failed, while still having attempted safe fallbacks.
    return False,primary_reason

def _render_auth_email(lang, title, greeting, paragraphs, button_label, action_url,
                       link_fallback, footer_tagline=None, post_button_paragraphs=None,
                       verification_code=None):
    """Render a compact, email-client-safe transactional message."""
    from html import escape

    ar = lang == "ar"
    direction = "rtl" if ar else "ltr"
    align = "right" if ar else "left"
    safe_url = escape(str(action_url), quote=True)
    safe_title = escape(str(title))
    safe_greeting = escape(str(greeting))
    safe_button = escape(str(button_label))
    safe_fallback = escape(str(link_fallback))
    paragraph_html = "".join(
        '<p style="margin:0 0 16px;color:#243b53;font-size:16px;line-height:1.75;">%s</p>'
        % escape(str(paragraph))
        for paragraph in paragraphs
    )
    post_button_html = "".join(
        '<p style="margin:0 0 16px;color:#243b53;font-size:16px;line-height:1.75;">%s</p>'
        % escape(str(paragraph))
        for paragraph in (post_button_paragraphs or [])
    )
    tagline_html = (
        '<div style="margin-top:4px;color:#486581;font-size:13px;line-height:1.6;">%s</div>'
        % escape(str(footer_tagline))
        if footer_tagline else ""
    )
    code_html = (
        '<div style="margin:22px 0;padding:16px;border:1px solid #b9d9ee;background:#eef7fc;'
        'border-radius:10px;text-align:center;direction:ltr;">'
        '<div style="color:#486581;font-size:13px;margin-bottom:7px;">%s</div>'
        '<div style="color:#12355b;font-size:32px;line-height:1.2;font-weight:800;letter-spacing:8px;">%s</div></div>'
        % (("رمز التحقق" if ar else "Verification code"), escape(str(verification_code)))
        if verification_code else ""
    )
    return '''<!doctype html>
<html lang="{lang}" dir="{direction}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background-color:#f3f8fc;font-family:Arial,'Helvetica Neue',sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%;background-color:#f3f8fc;">
    <tr><td align="center" style="padding:24px 12px;">
      <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:600px;background-color:#ffffff;border:1px solid #d9e8f3;border-radius:14px;">
        <tr><td style="padding:30px 28px 12px;text-align:{align};">
          <div style="color:#1769aa;font-size:20px;font-weight:700;line-height:1.4;">SymptoSense 🩺</div>
        </td></tr>
        <tr><td style="padding:8px 28px 30px;text-align:{align};">
          <h1 style="margin:0 0 20px;color:#12355b;font-size:26px;line-height:1.35;font-weight:700;">{title}</h1>
          <p style="margin:0 0 16px;color:#243b53;font-size:16px;line-height:1.75;">{greeting}</p>
          {paragraphs}
          {code}
          <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:24px 0;">
            <tr><td bgcolor="#1976b9" style="border-radius:8px;text-align:center;">
              <a href="{url}" style="display:inline-block;padding:13px 24px;color:#ffffff;text-decoration:none;font-size:16px;font-weight:700;line-height:1.4;">{button}</a>
            </td></tr>
          </table>
          {post_button}
          <p style="margin:24px 0 8px;color:#486581;font-size:14px;line-height:1.7;">{fallback}</p>
          <p style="margin:0;direction:ltr;text-align:left;word-break:break-all;font-size:13px;line-height:1.6;">
            <a href="{url}" style="color:#1769aa;text-decoration:underline;word-break:break-all;">{url}</a>
          </p>
        </td></tr>
        <tr><td style="padding:20px 28px;background-color:#eef6fb;border-top:1px solid #d9e8f3;text-align:{align};border-radius:0 0 14px 14px;">
          <div style="color:#12355b;font-size:14px;font-weight:700;line-height:1.6;">SymptoSense 🩺</div>
          {tagline}
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>'''.format(
        lang="ar" if ar else "en", direction=direction, align=align,
        title=safe_title, greeting=safe_greeting, paragraphs=paragraph_html,
        post_button=post_button_html,
        code=code_html,
        url=safe_url, button=safe_button, fallback=safe_fallback,
        tagline=tagline_html,
    )

def _issue_verification_email(user_id, lang=None):
    lang = lang or _lang()
    token, code, email, reason = platform_v2.create_email_verification_code(int(user_id))
    if not token:
        return False, reason or "verification_unavailable"
    verify_url=_transactional_auth_url("verify-email", token, lang)
    ar=lang=="ar"
    subject="تأكيد بريدك الإلكتروني — SymptoSense" if ar else "Confirm your email — SymptoSense"
    html=_render_auth_email(
        lang,
        "تأكيد بريدك الإلكتروني" if ar else "Confirm your email",
        "مرحبًا 👋" if ar else "Hi 👋",
        ([
            "شكرًا لإنشاء حسابك في SymptoSense 🩺",
            "استخدم رمز التحقق أدناه، أو اضغط على الزر، لإكمال إعداد حسابك:",
        ] if ar else [
            "Thanks for creating your SymptoSense 🩺 account.",
            "Use the verification code below, or select the button, to finish setting up your account:",
        ]),
        "تأكيد البريد الإلكتروني" if ar else "Confirm Email",
        verify_url,
        "إذا لم يعمل الزر، يمكنك فتح الرابط التالي:" if ar else
        "If the button doesn't work, open the following link:",
        "افهم أعراضك واعرف خطوتك التالية" if ar else
        "Understand your symptoms and know your next step",
        ([
            "هذا الرابط صالح لفترة محدودة ويمكن استخدامه مرة واحدة فقط.",
            "إذا لم تقم بإنشاء حساب في SymptoSense، يمكنك تجاهل هذه الرسالة بأمان.",
        ] if ar else [
            "This link is valid for a limited time and can only be used once.",
            "If you didn't create a SymptoSense account, you can safely ignore this email.",
        ]),
        verification_code=code,
    )
    sent, send_error=_send_auth_email(email, subject, html, "verify_email")
    if not sent:
        try: platform_v2.discard_email_verification_token(token)
        except Exception as exc: app.logger.debug("Non-critical operation skipped: %s", type(exc).__name__)
        return False, send_error
    return True, None

def _send_password_reset_email(email, reset_url, lang=None):
    lang=lang or _lang(); ar=lang=="ar"
    subject="إعادة تعيين كلمة المرور — SymptoSense" if ar else "Reset your password — SymptoSense"
    html=_render_auth_email(
        lang,
        "إعادة تعيين كلمة المرور" if ar else "Reset your password",
        "مرحبًا،" if ar else "Hi,",
        ([
            "تلقينا طلبًا لإعادة تعيين كلمة مرور حسابك في SymptoSense.",
            "اضغط على الزر التالي لإنشاء كلمة مرور جديدة:",
        ] if ar else [
            "We received a request to reset the password for your SymptoSense account.",
            "Use the button below to create a new password:",
        ]),
        "إعادة تعيين كلمة المرور" if ar else "Reset Password",
        reset_url,
        "إذا لم يعمل الزر، يمكنك فتح الرابط التالي:" if ar else
        "If the button doesn't work, open the following link:",
        None,
        ([
            "هذا الرابط مؤقت ويمكن استخدامه مرة واحدة فقط.",
            "إذا لم تطلب إعادة تعيين كلمة المرور، تجاهل هذه الرسالة ولن يتم تغيير حسابك.",
        ] if ar else [
            "This link is temporary and can only be used once.",
            "If you didn't request a password reset, you can safely ignore this email. Your account will remain unchanged.",
        ]),
    )
    return _send_auth_email(email, subject, html, "password_reset")

def _auth_login_error(lang, code):
    ar=lang=="ar"
    messages={
        "account_not_found": "البريد الإلكتروني أو كلمة المرور غير صحيحة." if ar else "Incorrect email or password.",
        "incorrect_credentials": "البريد الإلكتروني أو كلمة المرور غير صحيحة." if ar else "Incorrect email or password.",
        "account_unavailable": "يتعذر تسجيل الدخول إلى هذا الحساب حاليًا." if ar else "This account is currently unavailable.",
        "verification_required": "يجب التحقق من البريد الإلكتروني قبل تسجيل الدخول." if ar else "Please verify your email before signing in.",
    }
    return messages.get(code, "تعذر تسجيل الدخول. حاول مرة أخرى." if ar else "Unable to sign in. Please try again.")

_LOCAL_SYMPTOM_CATALOG = [
    {"slug":"syncope","name_ar":"😵 إغماء أو فقدان وعي","name_en":"😵 Fainting or loss of consciousness","aliases":["إغماء","اغماء","أغمى علي","اغمى علي","فقدت الوعي","فقدان الوعي","غشيان","غشي","إغماء مع فقدان وعي","قرب الإغماء أو خفة شديدة بالرأس","syncope","fainting","fainted","passed out","loss of consciousness","blackout","near-fainting","presyncope"]},
    {"slug":"palpitations","name_ar":"💓 خفقان القلب","name_en":"💓 Heart palpitations","aliases":["خفقان","خفقان القلب","دقات قلبي سريعة","نبضي سريع","تسارع دقات القلب","تسارع النبض","palpitations","heart palpitations","racing heart","pounding heartbeat"]},
    {"slug":"vomiting","name_ar":"🤮 قيء","name_en":"🤮 Vomiting","aliases":["قيء","تقيؤ","استفراغ","ترجيع","ارجع","أرجع","vomiting","vomit","throwing up","being sick"]},
    {"slug":"diarrhea","name_ar":"🚽 إسهال","name_en":"🚽 Diarrhea","aliases":["إسهال","اسهال","براز مائي","diarrhea","diarrhoea","watery stool","loose stool"]},
    {"slug":"constipation","name_ar":"🚻 إمساك","name_en":"🚻 Constipation","aliases":["إمساك","امساك","صعوبة التبرز","constipation","hard stool"]},
    {"slug":"rash","name_ar":"🩹 طفح جلدي","name_en":"🩹 Skin rash","aliases":["طفح","طفح جلدي","حبوب منتشرة","rash","skin rash"]},
    {"slug":"dysuria","name_ar":"🔥 حرقة أو ألم عند التبول","name_en":"🔥 Pain or burning when urinating","aliases":["حرقة البول","حرقة بول","حرقان البول","حرقان بول","حرقان عند التبول","ألم عند التبول","الم عند التبول","dysuria","painful urination","burning when urinating","burning urination"]},
    {"slug":"frequency","name_ar":"🚻 كثرة التبول","name_en":"🚻 Frequent urination","aliases":["كثرة التبول","اتبول كثير","أدخل الحمام كثير","frequent urination","peeing often","urinating often"]},
    {"slug":"hematuria","name_ar":"🩸 دم في البول","name_en":"🩸 Blood in urine","aliases":["دم في البول","بول دم","البول أحمر","البول احمر","blood in urine","bloody urine","hematuria"]},
    {"slug":"blood_stool","name_ar":"🩸 دم في البراز","name_en":"🩸 Blood in stool","aliases":["دم في البراز","براز دموي","براز اسود","براز أسود","blood in stool","bloody stool","black stool","melena"]},
    {"slug":"swelling","name_ar":"🫧 تورم","name_en":"🫧 Swelling","aliases":["تورم","انتفاخ الأطراف","انتفاخ الرجل","swelling","edema","oedema"]},
    {"slug":"confusion","name_ar":"🧠 تشوش أو ارتباك","name_en":"🧠 Confusion","aliases":["تشوش","ارتباك","لخبطة بالوعي","تغير الوعي","confusion","disorientation","altered mental status"]},
    {"slug":"seizure","name_ar":"⚡ نوبة تشنج","name_en":"⚡ Seizure","aliases":["نوبة تشنج","اختلاج","تشنجات مع فقدان وعي","seizure","convulsion","fit"]},
    {"slug":"vision_change","name_ar":"👀 تغير أو تشوش في الرؤية","name_en":"👀 Vision change or blurred vision","aliases":["تشوش النظر","زغللة","زغلله","ضبابية الرؤية","فقدان النظر","blurred vision","vision change","vision loss"]},
    {"slug":"back_pain","name_ar":"🦴 ألم الظهر","name_en":"🦴 Back pain","aliases":["ألم الظهر","الم الظهر","وجع الظهر","back pain","backache"]},
    {"slug":"neck_pain","name_ar":"🧍 ألم الرقبة","name_en":"🧍 Neck pain","aliases":["ألم الرقبة","الم الرقبة","وجع الرقبة","neck pain"]},
    {"slug":"ear_pain","name_ar":"👂 ألم الأذن","name_en":"👂 Ear pain","aliases":["ألم الأذن","الم الاذن","وجع الاذن","ear pain","earache"]},
    {"slug":"tinnitus","name_ar":"🔊 طنين الأذن","name_en":"🔊 Tinnitus","aliases":["طنين","صفير الاذن","صفير الأذن","tinnitus","ringing in ears"]},
    {"slug":"appetite_loss","name_ar":"🍽️ فقدان الشهية","name_en":"🍽️ Loss of appetite","aliases":["فقدان الشهية","ما لي نفس للاكل","مالي نفس للأكل","loss of appetite","poor appetite"]},
    {"slug":"weight_loss","name_ar":"⚖️ فقدان وزن غير مقصود","name_en":"⚖️ Unintentional weight loss","aliases":["فقدان وزن","نقص وزن بدون سبب","نحفت بدون سبب","unintentional weight loss","unexplained weight loss"]},
    {"slug":"tremor","name_ar":"🫨 رجفة أو رعشة","name_en":"🫨 Tremor or shaking","aliases":["رجفة","رعشة","ارتجاف","tremor","shaking"]},
]

# Broad local recognition layer.  This intentionally focuses on symptom concepts
# and common everyday wording rather than disease diagnosis.  Anything that is
# still unknown is kept verbatim and handled by the universal domain clarifier
# in the chat UI, so the flow never depends on a finite symptom list.
_LOCAL_SYMPTOM_CATALOG.extend([
    {"slug":"wheezing","name_ar":"🫁 صفير أو أزيز في التنفس","name_en":"🫁 Wheezing","aliases":["صفير التنفس","صفير في الصدر","ازيز","أزيز","wheezing","wheeze"]},
    {"slug":"nasal_congestion","name_ar":"👃 احتقان أو انسداد الأنف","name_en":"👃 Nasal congestion","aliases":["احتقان الانف","احتقان الأنف","انسداد الانف","انسداد الأنف","خشمي مسدود","stuffy nose","blocked nose","nasal congestion"]},
    {"slug":"runny_nose","name_ar":"🤧 سيلان الأنف","name_en":"🤧 Runny nose","aliases":["سيلان الانف","سيلان الأنف","رشح","runny nose","nasal discharge"]},
    {"slug":"sneezing","name_ar":"🤧 عطاس","name_en":"🤧 Sneezing","aliases":["عطاس","اعطس","أعطس","sneezing","sneeze"]},
    {"slug":"coughing_blood","name_ar":"🩸 دم مع السعال","name_en":"🩸 Coughing up blood","aliases":["دم مع السعال","كحة دم","سعال دموي","دم في البلغم","coughing blood","coughing up blood","blood in phlegm","hemoptysis"]},
    {"slug":"blue_lips","name_ar":"🔵 ازرقاق الشفاه أو الجلد","name_en":"🔵 Blue or grey lips/skin","aliases":["ازرقاق الشفاه","زرقة الشفاه","شفايف زرقاء","ازرقاق الجلد","blue lips","blue skin","cyanosis"]},
    {"slug":"chest_pressure","name_ar":"🫀 ضغط أو ثقل في الصدر","name_en":"🫀 Chest pressure or tightness","aliases":["ضغط في الصدر","ثقل في الصدر","شد في الصدر","ضيق الصدر","chest pressure","chest tightness","chest heaviness"]},
    {"slug":"weakness","name_ar":"🧠 ضعف مفاجئ أو عام","name_en":"🧠 Weakness","aliases":["ضعف مفاجئ","ضعف عام","ضعف في اليد","ضعف في الرجل","ما اقدر احرك","weakness","weak arm","weak leg"]},
    {"slug":"speech_problem","name_ar":"🗣️ صعوبة أو ثقل في الكلام","name_en":"🗣️ Speech difficulty","aliases":["ثقل الكلام","صعوبة الكلام","تلخبط الكلام","ما اقدر اتكلم","speech difficulty","slurred speech","trouble speaking"]},
    {"slug":"balance_problem","name_ar":"⚖️ عدم اتزان","name_en":"⚖️ Balance problem","aliases":["عدم اتزان","اختلال التوازن","امشي واتمايل","عدم توازن","loss of balance","balance problem","unsteady"]},
    {"slug":"memory_problem","name_ar":"🧠 مشكلة أو فقدان في الذاكرة","name_en":"🧠 Memory problem","aliases":["نسيان شديد","فقدان الذاكرة","ضعف الذاكرة","memory loss","amnesia","memory problem"]},
    {"slug":"heartburn","name_ar":"🔥 حرقة المعدة أو الحموضة","name_en":"🔥 Heartburn or acid reflux","aliases":["حرقة المعدة","حرقان المعدة","حموضة","ارتجاع","ارتجاع المريء","heartburn","acid reflux","reflux"]},
    {"slug":"bloating","name_ar":"🎈 انتفاخ البطن","name_en":"🎈 Bloating","aliases":["انتفاخ البطن","نفخة","غازات بالبطن","bloating","bloated"]},
    {"slug":"gas","name_ar":"💨 غازات","name_en":"💨 Gas","aliases":["غازات","تجشؤ","تكريع","gas","belching","burping","flatulence"]},
    {"slug":"swallowing_problem","name_ar":"🥤 صعوبة البلع","name_en":"🥤 Difficulty swallowing","aliases":["صعوبة البلع","ما اقدر ابلع","ألم عند البلع","الم عند البلع","dysphagia","difficulty swallowing","trouble swallowing"]},
    {"slug":"rectal_bleeding","name_ar":"🩸 نزيف أو دم من الشرج","name_en":"🩸 Rectal bleeding","aliases":["نزيف من الشرج","دم من الشرج","نزيف شرجي","rectal bleeding","bleeding from bottom"]},
    {"slug":"urinary_urgency","name_ar":"🚻 إلحاح مفاجئ للتبول","name_en":"🚻 Urinary urgency","aliases":["الحاح البول","إلحاح البول","احتاج الحمام فجأة","urinary urgency","urgent urination"]},
    {"slug":"urine_retention","name_ar":"🚫 صعوبة أو عدم القدرة على التبول","name_en":"🚫 Difficulty or inability to urinate","aliases":["ما اقدر اتبول","صعوبة التبول","احتباس البول","عدم التبول","urinary retention","cannot urinate","difficulty urinating"]},
    {"slug":"flank_pain","name_ar":"🫘 ألم الخاصرة","name_en":"🫘 Flank pain","aliases":["ألم الخاصرة","الم الخاصرة","وجع الخاصرة","ألم الجنب تحت الاضلاع","flank pain","kidney pain"]},
    {"slug":"pelvic_pain","name_ar":"🌸 ألم الحوض","name_en":"🌸 Pelvic pain","aliases":["ألم الحوض","الم الحوض","وجع الحوض","pelvic pain"]},
    {"slug":"period_pain","name_ar":"🌸 ألم أو مغص الدورة","name_en":"🌸 Period pain/cramps","aliases":["الم الدورة","ألم الدورة","مغص الدورة","تقلصات الدورة","period pain","period cramps","menstrual cramps","dysmenorrhea"]},
    {"slug":"irregular_period","name_ar":"📅 عدم انتظام الدورة","name_en":"📅 Irregular periods","aliases":["الدورة غير منتظمة","عدم انتظام الدورة","تلخبط الدورة","irregular period","irregular periods"]},
    {"slug":"missed_period","name_ar":"📅 تأخر أو غياب الدورة","name_en":"📅 Missed or late period","aliases":["تأخر الدورة","الدورة متأخرة","غياب الدورة","ما جاتني الدورة","missed period","late period","amenorrhea"]},
    {"slug":"heavy_period","name_ar":"🩸 غزارة الدورة أو نزيف مهبلي شديد","name_en":"🩸 Heavy periods or vaginal bleeding","aliases":["غزارة الدورة","دورة غزيرة","نزيف الدورة","نزيف مهبلي","heavy period","heavy periods","heavy menstrual bleeding","vaginal bleeding"]},
    {"slug":"vaginal_discharge","name_ar":"🌸 إفرازات مهبلية غير معتادة","name_en":"🌸 Unusual vaginal discharge","aliases":["افرازات مهبلية","إفرازات مهبلية","إفرازات غريبة","vaginal discharge","unusual discharge"]},
    {"slug":"testicular_pain","name_ar":"♂️ ألم الخصية","name_en":"♂️ Testicular pain","aliases":["ألم الخصية","الم الخصية","وجع الخصية","testicular pain","testicle pain"]},
    {"slug":"testicular_swelling","name_ar":"♂️ تورم الخصية","name_en":"♂️ Testicular swelling","aliases":["تورم الخصية","انتفاخ الخصية","testicular swelling","swollen testicle"]},
    {"slug":"muscle_pain","name_ar":"💪 ألم العضلات","name_en":"💪 Muscle pain","aliases":["ألم العضلات","الم العضلات","وجع العضلات","شد عضلي","muscle pain","muscle ache","myalgia"]},
    {"slug":"shoulder_pain","name_ar":"💪 ألم الكتف","name_en":"💪 Shoulder pain","aliases":["ألم الكتف","الم الكتف","وجع الكتف","shoulder pain"]},
    {"slug":"arm_pain","name_ar":"💪 ألم الذراع","name_en":"💪 Arm pain","aliases":["ألم الذراع","الم الذراع","وجع اليد","وجع الذراع","arm pain"]},
    {"slug":"knee_pain","name_ar":"🦵 ألم الركبة","name_en":"🦵 Knee pain","aliases":["ألم الركبة","الم الركبة","وجع الركبة","knee pain"]},
    {"slug":"ankle_pain","name_ar":"🦶 ألم الكاحل","name_en":"🦶 Ankle pain","aliases":["ألم الكاحل","الم الكاحل","وجع الكاحل","ankle pain"]},
    {"slug":"foot_pain","name_ar":"🦶 ألم القدم","name_en":"🦶 Foot pain","aliases":["ألم القدم","الم القدم","وجع القدم","foot pain"]},
    {"slug":"injury","name_ar":"🩹 إصابة أو رضّة","name_en":"🩹 Injury or bruise","aliases":["إصابة","اصابة","رضة","كدمة","طيحة","سقوط","injury","bruise","fall"]},
    {"slug":"wound","name_ar":"🩹 جرح","name_en":"🩹 Wound","aliases":["جرح","جرح مفتوح","wound","cut"]},
    {"slug":"burn","name_ar":"🔥 حرق","name_en":"🔥 Burn","aliases":["حرق","حروق","انحرقت","burn","burns","scald"]},
    {"slug":"hives","name_ar":"🩹 شرى أو أرتكاريا","name_en":"🩹 Hives","aliases":["شرى","ارتكاريا","أرتكاريا","حساسية جلد","hives","urticaria"]},
    {"slug":"skin_lump","name_ar":"🟠 كتلة أو تورم موضعي","name_en":"🟠 Lump or localized swelling","aliases":["كتلة","ورم موضعي","حبة كبيرة","lump","mass","localized swelling"]},
    {"slug":"eye_pain","name_ar":"👁️ ألم العين","name_en":"👁️ Eye pain","aliases":["ألم العين","الم العين","وجع العين","eye pain"]},
    {"slug":"vision_loss","name_ar":"👁️ فقدان أو نقص مفاجئ في النظر","name_en":"👁️ Sudden vision loss","aliases":["فقدان النظر","فقدت النظر","نقص مفاجئ بالنظر","ما اشوف فجأة","vision loss","sudden loss of vision"]},
    {"slug":"hearing_loss","name_ar":"👂 ضعف أو فقدان السمع","name_en":"👂 Hearing loss","aliases":["ضعف السمع","فقدان السمع","ما اسمع","hearing loss","reduced hearing"]},
    {"slug":"hoarseness","name_ar":"🗣️ بحة الصوت","name_en":"🗣️ Hoarse voice","aliases":["بحة الصوت","صوتي مبحوح","بحه","hoarse voice","hoarseness"]},
    {"slug":"toothache","name_ar":"🦷 ألم الأسنان","name_en":"🦷 Toothache","aliases":["ألم الاسنان","ألم الأسنان","الم الاسنان","وجع السن","وجع الأسنان","toothache","tooth pain"]},
    {"slug":"mouth_ulcer","name_ar":"👄 قرحة أو تقرحات الفم","name_en":"👄 Mouth ulcer","aliases":["قرحة الفم","تقرحات الفم","حمو الفم","mouth ulcer","mouth sore"]},
    {"slug":"swollen_glands","name_ar":"🫧 تضخم أو تورم الغدد","name_en":"🫧 Swollen glands","aliases":["تورم الغدد","تضخم الغدد","غدد منتفخة","swollen glands","swollen lymph nodes"]},
    {"slug":"night_sweats","name_ar":"🌙 تعرق ليلي","name_en":"🌙 Night sweats","aliases":["تعرق ليلي","عرق بالليل","اصحى متعرق","night sweats"]},
    {"slug":"excessive_sweating","name_ar":"💦 تعرق زائد","name_en":"💦 Excessive sweating","aliases":["تعرق زائد","عرق كثير","تعرق شديد","excessive sweating","hyperhidrosis"]},
    {"slug":"excessive_thirst","name_ar":"🥤 عطش شديد أو زائد","name_en":"🥤 Excessive thirst","aliases":["عطش شديد","عطشان دايم","اشرب كثير","excessive thirst","very thirsty","polydipsia"]},
    {"slug":"weight_gain","name_ar":"⚖️ زيادة وزن غير مفسرة","name_en":"⚖️ Unexplained weight gain","aliases":["زيادة وزن بدون سبب","زاد وزني بدون سبب","unexplained weight gain","unexpected weight gain"]},
    {"slug":"insomnia","name_ar":"🌙 أرق أو صعوبة النوم","name_en":"🌙 Insomnia","aliases":["أرق","ارق","ما اقدر انام","صعوبة النوم","insomnia","trouble sleeping","can't sleep"]},
    {"slug":"sleepiness","name_ar":"😴 نعاس زائد","name_en":"😴 Excessive sleepiness","aliases":["نعاس زائد","نعسان طول الوقت","نوم كثير","excessive sleepiness","daytime sleepiness","hypersomnia"]},
    {"slug":"anxiety","name_ar":"😟 قلق أو نوبة هلع","name_en":"😟 Anxiety or panic","aliases":["قلق","توتر شديد","هلع","نوبة هلع","خوف مفاجئ","anxiety","panic","panic attack"]},
    {"slug":"low_mood","name_ar":"🧠 مزاج منخفض أو حزن مستمر","name_en":"🧠 Low mood","aliases":["حزن مستمر","مزاجي سيء","اكتئاب","كآبة","low mood","depressed mood","sad all the time"]},
    {"slug":"easy_bruising","name_ar":"🟣 كدمات متكررة أو سهلة","name_en":"🟣 Easy bruising","aliases":["كدمات بدون سبب","اكدم بسهولة","كدمات كثيرة","easy bruising","bruising easily"]},
    {"slug":"nosebleed","name_ar":"🩸 نزيف الأنف","name_en":"🩸 Nosebleed","aliases":["نزيف الانف","نزيف الأنف","رعاف","nosebleed","nose bleed","epistaxis"]},
])

def _normalize_symptom_search_text(value):
    text = str(value or "").strip().lower()
    text = text.translate(str.maketrans({"أ":"ا","إ":"ا","آ":"ا","ى":"ي","ؤ":"و","ئ":"ي","ة":"ه"}))
    text = re.sub(r"[ًٌٍَُِّْـ]", "", text)
    text = re.sub(r"[^\w\u0600-\u06FF]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())

def _symptom_phrase_match(hay, alias):
    """Match a normalized symptom as a whole word/phrase, never as a substring.

    This prevents short aliases such as ``fit``, ``cut``, ``gas``, ``mass`` and
    ``burn`` from matching inside unrelated words such as benefit, acute,
    gastric, massage and burning/dysuria text.
    """
    alias = _normalize_symptom_search_text(alias)
    if not hay or not alias:
        return False
    return bool(re.search(r"(?:^|\s)" + re.escape(alias) + r"(?:$|\s)", hay))

def _local_symptom_hits(text):
    hay = _normalize_symptom_search_text(text)
    if not hay:
        return []
    matches = []
    for item in _LOCAL_SYMPTOM_CATALOG:
        aliases = sorted((item.get("aliases") or []), key=lambda a: len(_normalize_symptom_search_text(a)), reverse=True)
        best = next((a for a in aliases if _symptom_phrase_match(hay, a)), None)
        if best:
            matches.append((len(_normalize_symptom_search_text(best)), item))
    # Prefer the most specific phrase when aliases overlap. Keep distinct
    # symptoms, but do not let a shorter alias outrank a longer phrase.
    matches.sort(key=lambda pair: pair[0], reverse=True)
    out = []
    seen = set()
    for _, item in matches:
        if item["slug"] in seen:
            continue
        seen.add(item["slug"])
        out.append({"slug":item["slug"],"name_ar":item["name_ar"],"name_en":item["name_en"],"source":"local_clinical_alias"})
    return out[:12]

@app.route("/api/health-summary", methods=["GET"])
@login_required
def api_health_summary():
    return jsonify({"ok": True, "summary": advanced_features.personal_health_summary(_data_user_id(), "en" if _lang()=="en" else "ar")})

# ---------------------------------------------------------------- Medical Knowledge Base APIs

def _mk_error(exc, status=400):
    request_id=getattr(g,"request_id","")
    app.logger.warning("API request failed; request_id=%s route=%s error_type=%s",request_id,request.path,type(exc).__name__)
    return jsonify({"ok":False,"error":"تعذر إكمال الطلب حاليًا." if _lang()=="ar" else "Unable to complete the request right now.","request_id":request_id}),status

@app.route("/api/sources", methods=["GET"])
def api_sources():
    try:
        rows = medical_knowledge.list_entities(
            "sources", False, request.args.get("q", ""), verification="verified"
        )
        return jsonify({"ok": True, "sources": rows})
    except Exception as exc:
        return _mk_error(exc)

admin_knowledge_routes.register(app, admin_api_required, _mk_error, _admin_allowed, _admin_role, _ss_user)

@app.route("/api/content", methods=["GET"])
def api_public_content():
    try:
        return jsonify({"ok": True, "content": platform_v2.list_content(True, request.args.get("q", ""), request.args.get("type", ""))})
    except Exception as exc:
        return _mk_error(exc)

def _admin_analytics_filters():
    allowed_age={"","Under 18","18–25","26–35","36–45","46–55","56+"}
    allowed_gender={"","Female","Male","Other","Unknown"}
    allowed_risk={"","Low Risk","Needs Follow-up","Urgent"}
    period=(request.args.get("period") or "30d").lower()
    if period not in {"7d","30d","90d","180d","all","custom"}: period="30d"
    age=request.args.get("age_group","")
    gender=request.args.get("gender","")
    risk=request.args.get("risk","")
    return {
        "period":period,"start":request.args.get("start","")[:10],"end":request.args.get("end","")[:10],
        "age_group":age if age in allowed_age else "","gender":gender if gender in allowed_gender else "",
        "medication":(request.args.get("medication") or "")[:100],"symptom":(request.args.get("symptom") or "")[:100],
        "risk":risk if risk in allowed_risk else "",
    }

def _voice_parse(text, lang):
    """Parse a speech transcript into user-reviewable fields without storing audio."""
    text = str(text or "").strip()
    low = text.lower()
    if lang == "ar":
        sym_map = [
            (["صداع", "راسي", "رأسي", "الرأس", "راس"], "🤕 صداع"),
            (["حمى", "حرارة", "سخونة"], "🤒 حمى"), (["سعال", "كحة", "كحه"], "😷 سعال"),
            (["ألم في الصدر", "وجع الصدر", "صدري", "صدر"], "🫀 ألم في الصدر"),
            (["غثيان", "ترجيع", "استفراغ", "قيء"], "🤢 غثيان"),
            (["تعب", "إرهاق", "ارهاق", "خمول"], "😴 تعب وإرهاق"),
            (["ضيق تنفس", "ضيق في التنفس", "صعوبة التنفس", "اختناق"], "🫁 ضيق التنفس"),
            (["دوار", "دوخة", "دوخه"], "💫 دوار"), (["مفاصل", "عظام"], "🦴 ألم المفاصل"),
            (["بطني يعورني", "ألم بطني", "الم في البطن", "ألم في البطن", "بطن", "معدة"], "😖 ألم في البطن"),
            (["قشعريرة", "رعشة", "رجفه"], "🥶 قشعريرة"), (["احمرار العين", "عيوني حمراء", "عين", "عيون"], "👁️ احمرار العيون"),
            (["ألم في الرجل", "ألم في الساق", "ساق", "رجل"], "🦵 ألم في الرجل"), (["ألم الحلق", "حلق", "زور"], "😣 ألم الحلق"),
            (["حكة", "هرش", "هرشه"], "🖐️ حكة"),
        ]
        dur_rules = [
            (["من أمس", "من امس", "البارحة", "منذ أمس", "من يوم", "منذ يوم"], "⏰ أقل من 24 ساعة"),
            (["يومين", "ثلاثة أيام", "ثلاث ايام", "2 أيام", "3 أيام", "٢ أيام", "٣ أيام"], "📅 1-3 أيام"),
            (["أربعة أيام", "خمسة أيام", "4 أيام", "5 أيام", "٤ أيام", "٥ أيام"], "📅 4-7 أيام"),
            (["أكثر من أسبوعين", "اكثر من اسبوعين"], "🗓️ أكثر من أسبوعين"), (["أسبوعين", "اسبوعين"], "🗓️ 1-2 أسبوع"), (["أسبوع", "اسبوع"], "🗓️ 1-2 أسبوع"), (["شهر"], "📆 أكثر من شهر"),
        ]
        locations = [
            (["الجهة اليمنى", "اليمين", "يمين"], "الجهة اليمنى"), (["الجهة اليسرى", "اليسار", "يسار"], "الجهة اليسرى"),
            (["أسفل البطن", "اسفل البطن"], "أسفل البطن"), (["أعلى البطن", "اعلى البطن"], "أعلى البطن"),
            (["منتصف", "الوسط"], "المنتصف"),
        ]
        words = {"واحد":1,"واحدة":1,"اثنين":2,"اثنان":2,"ثلاثة":3,"أربعة":4,"اربعة":4,"خمسة":5,"ستة":6,"سبعة":7,"ثمانية":8,"تسعة":9,"عشرة":10}
    else:
        sym_map = [
            (["headache", "head hurts", "head pain"], "🤕 Headache"), (["fever", "temperature"], "🤒 Fever"), (["cough"], "😷 Cough"),
            (["chest pain", "chest hurts"], "🫀 Chest pain"), (["nausea", "vomit", "vomiting"], "🤢 Nausea"), (["fatigue", "tired", "exhausted"], "😴 Fatigue"),
            (["shortness of breath", "breathless", "difficulty breathing"], "🫁 Shortness of breath"), (["dizzy", "dizziness"], "💫 Dizziness"),
            (["joint pain", "joints"], "🦴 Joint pain"), (["abdominal pain", "stomach pain", "belly pain", "abdomen"], "😖 Stomach pain"),
            (["chills", "shivering"], "🥶 Chills"), (["red eye", "eye redness"], "👁️ Eye redness"), (["leg pain"], "🦵 Leg pain"),
            (["sore throat", "throat pain"], "😣 Sore throat"), (["itch", "itching", "itchy"], "🖐️ Itching"),
        ]
        dur_rules = [
            (["since yesterday", "yesterday", "one day", "1 day"], "⏰ Less than 24 hours"),
            (["two days", "2 days", "three days", "3 days", "couple of days"], "📅 1-3 days"),
            (["four days", "five days", "4 days", "5 days"], "📅 4-7 days"), (["more than two weeks", "more than 2 weeks", "over two weeks", "over 2 weeks"], "🗓️ More than 2 weeks"), (["two weeks", "2 weeks"], "🗓️ 1-2 weeks"),
            (["week"], "🗓️ 1-2 weeks"), (["month"], "📆 More than a month"),
        ]
        locations = [
            (["right side", "on the right", "right lower"], "Right side"), (["left side", "on the left", "left lower"], "Left side"),
            (["lower abdomen", "lower belly"], "Lower abdomen"), (["upper abdomen", "upper belly"], "Upper abdomen"), (["middle", "center"], "Center"),
        ]
        words = {"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,"ten":10}
    found=[]
    for kws,label in sym_map:
        if clinical_text.contains_unnegated_any(text, kws) and label not in found:
            found.append(label)
    duration = next((label for phrase, label in sorted(
        ((phrase, label) for kws, label in dur_rules for phrase in kws),
        key=lambda item: len(item[0]), reverse=True,
    ) if clinical_text.contains_unnegated_phrase(text, phrase)), None)
    location=next((label for kws,label in locations if any(k in low for k in kws)),None)
    severity10=None
    # Prefer an explicit x/10 or "x out of ten" statement.
    m=re.search(r"\b(10|[1-9])\s*(?:/|من|out of)\s*10\b", low)
    if m: severity10=int(m.group(1))
    if severity10 is None:
        for w,n in words.items():
            if re.search(r"\b"+re.escape(w)+r"\b",low) and (("عشرة" in low or "من عشرة" in low) if lang=="ar" else ("out of ten" in low or "out of 10" in low)):
                severity10=n;break
    if severity10 is None:
        if any(x in low for x in (["شديد جدًا","شديد جدا","لا يحتمل"] if lang=="ar" else ["unbearable","extremely severe"])): severity10=9
        elif any(x in low for x in (["شديد","قوي"] if lang=="ar" else ["severe","very bad"])): severity10=8
        elif any(x in low for x in (["متوسط"] if lang=="ar" else ["moderate"])): severity10=5
        elif any(x in low for x in (["خفيف"] if lang=="ar" else ["mild","slight"])): severity10=3
    severity5 = max(1,min(5,int(round((severity10 or 0)/2)))) if severity10 else None
    return {"symptoms":found,"duration":duration,"location":location,"severity":severity5,"severity_10":severity10,"transcript":text}

_FAMILY_RELATIONS = {"me", "mother", "father", "daughter", "son", "grandparent", "other"}

def _family_member_payload(data):
    """Validate and normalize family-profile fields without changing their meaning."""
    if not isinstance(data, dict):
        raise ValueError("invalid_input")
    relation = str(data.get("relation") or "other").strip().lower()
    if relation not in _FAMILY_RELATIONS:
        relation = "other"
    name = str(data.get("name") or "").strip()[:120]
    if not name:
        raise ValueError("name_required")
    age = str(data.get("age") or "").strip()[:32]
    if age and clinical_text.parse_age_years(age) is None:
        raise ValueError("invalid_age")
    gender = str(data.get("gender") or "").strip().lower()
    gender = {"male": "m", "female": "f"}.get(gender, gender)
    if gender not in {"", "m", "f"}:
        raise ValueError("invalid_gender")
    return {
        "relation": relation,
        "name": name,
        "age": age,
        "gender": gender,
        "conditions": str(data.get("conditions") or "").strip()[:2000],
        "medications": str(data.get("medications") or "").strip()[:2000],
        "allergies": str(data.get("allergies") or "").strip()[:2000],
        "notes": str(data.get("notes") or "").strip()[:4000],
    }


import health_file, clinical_signoff, emergency_gate
emergency_gate.register(app)
clinical_signoff.register(app)
health_file.register(app, login_required, api_login_required, _data_user_id, _page, _lang, _mk_error)
import followup
followup.register(app, api_login_required, _data_user_id, _lang, _mk_error)
import vitals
vitals.register(app, login_required, api_login_required, _data_user_id, _page, _lang, _mk_error)
import redflag_screen
redflag_screen.register(app, _service_consent_ok, _consent_required_json, _mk_error)

def _sanitize_analysis_notes_for_safety(value):
    """Remove negated follow-up question text before deterministic triage.

    The chat used to store the full question followed by ``-> لا/No``.  That
    meant phrases such as "blood in vomit" or "shortness of breath" remained
    inside ``notes`` even when the user explicitly answered NO, causing false
    red-flag matches.  Keep positive answers and free text, but strip only the
    negated question fragments.
    """
    text = " ".join(str(value or "").split())[:2000]
    if not text:
        return ""
    pattern = re.compile(r'[^؟?!]{0,420}[؟?]\s*->\s*(?:لا|no)\b', re.IGNORECASE)
    previous = None
    while previous != text:
        previous = text
        text = pattern.sub(' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:2000]

_CURATED_ANALYSIS_SOURCES = {
    "general": [
        {"source_name":"وزارة الصحة السعودية","organization":"Saudi Ministry of Health","source_type":"government","reference_title_ar":"المحتوى التثقيفي الصحي","reference_title_en":"Health educational content","reference_url":"https://www.moh.gov.sa/healthawareness/educationalcontent/pages/default.aspx","last_verified":"2026-09-09"},
        {"source_name":"NHS","organization":"NHS","source_type":"national_health_service","reference_title_ar":"دليل الأعراض من A إلى Z","reference_title_en":"Symptoms A to Z","reference_url":"https://www.nhs.uk/symptoms/","last_verified":"2026-09-09"},
        {"source_name":"MedlinePlus","organization":"U.S. National Library of Medicine","source_type":"government","reference_title_ar":"دليل الأعراض والمواضيع الصحية","reference_title_en":"Symptoms and health topics","reference_url":"https://medlineplus.gov/symptoms.html","last_verified":"2026-09-09"},
        {"source_name":"CDC","organization":"Centers for Disease Control and Prevention","source_type":"government","reference_title_ar":"المواضيع الصحية A-Z","reference_title_en":"Health Topics A-Z","reference_url":"https://www.cdc.gov/health-topics.html","last_verified":"2026-09-09"},
        {"source_name":"WHO","organization":"World Health Organization","source_type":"international_health_organization","reference_title_ar":"المواضيع الصحية","reference_title_en":"Health topics","reference_url":"https://www.who.int/health-topics","last_verified":"2026-09-09"},
    ],
    "syncope": [
        {"source_name":"NHS","organization":"NHS","source_type":"national_health_service","reference_title_ar":"الإغماء (Fainting)","reference_title_en":"Fainting","reference_url":"https://www.nhs.uk/symptoms/fainting/","last_verified":"2026-09-09"},
        {"source_name":"MedlinePlus","organization":"U.S. National Library of Medicine","source_type":"government","reference_title_ar":"الإغماء / الغشي","reference_title_en":"Syncope / Fainting","reference_url":"https://medlineplus.gov/fainting.html","last_verified":"2026-09-09"},
        {"source_name":"American Heart Association","organization":"American Heart Association","source_type":"other_trusted_source","reference_title_ar":"الغشي (الإغماء)","reference_title_en":"Syncope (Fainting)","reference_url":"https://www.heart.org/en/health-topics/arrhythmia/symptoms-diagnosis--monitoring-of-arrhythmia/syncope-fainting","last_verified":"2026-09-09"},
        {"source_name":"Mayo Clinic","organization":"Mayo Clinic","source_type":"academic_medical_institution","reference_title_ar":"الإغماء: الإسعافات الأولية","reference_title_en":"Fainting: First aid","reference_url":"https://www.mayoclinic.org/first-aid/first-aid-fainting/basics/art-20056606","last_verified":"2026-09-09"},
    ],
    "palpitations": [
        {"source_name":"NHS","organization":"NHS","source_type":"national_health_service","reference_title_ar":"خفقان القلب","reference_title_en":"Heart palpitations","reference_url":"https://www.nhs.uk/symptoms/heart-palpitations/","last_verified":"2026-09-09"},
        {"source_name":"MedlinePlus","organization":"U.S. National Library of Medicine","source_type":"government","reference_title_ar":"خفقان القلب","reference_title_en":"Heart palpitations","reference_url":"https://medlineplus.gov/ency/article/003081.htm","last_verified":"2026-09-09"},
    ],
    "gastro": [
        {"source_name":"NHS","organization":"NHS","source_type":"national_health_service","reference_title_ar":"الإسهال والقيء","reference_title_en":"Diarrhoea and vomiting","reference_url":"https://www.nhs.uk/conditions/diarrhoea-and-vomiting/","last_verified":"2026-09-09"},
        {"source_name":"MedlinePlus","organization":"U.S. National Library of Medicine","source_type":"government","reference_title_ar":"الغثيان والقيء لدى البالغين","reference_title_en":"Nausea and vomiting – adults","reference_url":"https://medlineplus.gov/ency/article/003117.htm","last_verified":"2026-09-09"},
        {"source_name":"MedlinePlus","organization":"U.S. National Library of Medicine","source_type":"government","reference_title_ar":"الإسهال","reference_title_en":"Diarrhea","reference_url":"https://medlineplus.gov/diarrhea.html","last_verified":"2026-09-09"},
    ],
    "urinary": [
        {"source_name":"NHS","organization":"NHS","source_type":"national_health_service","reference_title_ar":"التهابات المسالك البولية","reference_title_en":"Urinary tract infections (UTIs)","reference_url":"https://www.nhs.uk/conditions/urinary-tract-infections-utis/","last_verified":"2026-09-09"},
        {"source_name":"NHS","organization":"NHS","source_type":"national_health_service","reference_title_ar":"وجود دم في البول","reference_title_en":"Blood in urine","reference_url":"https://www.nhs.uk/symptoms/blood-in-urine/","last_verified":"2026-09-09"},
    ],
    "breathing": [
        {"source_name":"NHS","organization":"NHS","source_type":"national_health_service","reference_title_ar":"ضيق التنفس","reference_title_en":"Shortness of breath","reference_url":"https://www.nhs.uk/symptoms/shortness-of-breath/","last_verified":"2026-09-09"},
    ],
}

def _analysis_source_groups(symptoms):
    text=_normalize_symptom_search_text(" ".join(str(x) for x in (symptoms or [])))
    groups=["general"]
    def has(*terms):
        return any(_normalize_symptom_search_text(t) in text for t in terms)
    if has("اغماء","فقدان الوعي","غشي","fainting","syncope","loss of consciousness","near-fainting"):
        groups.append("syncope")
    if has("خفقان","تسارع دقات القلب","palpitations","racing heart"):
        groups.append("palpitations")
    if has("قيء","استفراغ","اسهال","إسهال","vomiting","diarrhea","diarrhoea"):
        groups.append("gastro")
    if has("حرقة البول","حرقان البول","الم عند التبول","دم في البول","كثره التبول","dysuria","burning urination","blood in urine","frequent urination"):
        groups.append("urinary")
    if has("ضيق التنفس","shortness of breath","breathlessness"):
        groups.append("breathing")
    return groups

def _augment_analysis_sources(result, symptoms):
    result=result or {}
    sources=list(result.get("medical_sources") or [])
    seen=set()
    for src in sources:
        url=str(src.get("reference_url") or src.get("official_url") or "").strip()
        if url: seen.add(url.rstrip("/"))
    for group in _analysis_source_groups(symptoms):
        for src in _CURATED_ANALYSIS_SOURCES.get(group, []):
            key=src["reference_url"].rstrip("/")
            if key not in seen:
                sources.append(dict(src)); seen.add(key)
    result["medical_sources"]=sources[:12]
    return result


def _ensure_analysis_match_sources(result):
    """Ensure every structured possibility is traceable to at least one source.

    Disease-specific sources from the knowledge engine always win.  When a
    structured match has no direct source attached, the UI receives a clearly
    marked *context* source from the overall symptom references rather than
    presenting an unsourced explanation as if it were fully grounded.
    """
    result = result or {}
    matches = result.get("knowledge_matches") or []
    if not isinstance(matches, list):
        return result
    fallback = None
    for src in (result.get("medical_sources") or []):
        if not isinstance(src, dict):
            continue
        url = src.get("reference_url") or src.get("official_url") or src.get("url")
        if url:
            fallback = dict(src)
            fallback["source_scope"] = "symptom_context_fallback"
            break
    direct = 0
    total = 0
    for item in matches:
        if not isinstance(item, dict):
            continue
        total += 1
        existing = item.get("explanation_source")
        sources = item.get("sources") if isinstance(item.get("sources"), list) else []
        if isinstance(existing, dict) and (existing.get("reference_url") or existing.get("official_url") or existing.get("url")):
            existing.setdefault("source_scope", "condition_specific")
            direct += 1
            continue
        if sources and isinstance(sources[0], dict):
            src = dict(sources[0]); src.setdefault("source_scope", "condition_specific")
            item["explanation_source"] = src
            direct += 1
        elif fallback:
            item["explanation_source"] = dict(fallback)
            direct += 1
    result["source_traceability"] = {
        "structured_results": total,
        "results_with_source": direct,
        "coverage_pct": round((direct * 100.0 / total), 1) if total else 100.0,
    }
    return result

def _groq_chat_completion_with_retry(messages, *, max_completion_tokens=240, temperature=0.4, timeout=6):
    """Single bounded provider attempt for competition-safe responsiveness.

    If the external provider is unavailable or slow, fail fast so the curated
    local fallback can answer instead of making the user wait through retries.
    """
    try:
        client = analysis_core._groq_client()
        return client.chat.completions.create(
            model=os.environ.get("GROQ_TEXT_MODEL", "openai/gpt-oss-120b").strip() or "openai/gpt-oss-120b",
            messages=messages,
            temperature=temperature,
            max_completion_tokens=max_completion_tokens,
            timeout=min(float(timeout or 6), 6.0),
        )
    except Exception as exc:
        raise exc

def _followup_local_answer(question, context, lang):
    """Safe, context-aware answer when the external assistant is unavailable."""
    ar = lang != "en"
    ctx = context if isinstance(context, dict) else {}

    def clean(value, limit=700):
        if isinstance(value, list):
            parts = []
            for item in value[:5]:
                if isinstance(item, dict):
                    item = item.get("tip") or item.get("title") or item.get("name") or ""
                if str(item or "").strip():
                    parts.append(str(item).strip())
            value = "، ".join(parts) if ar else "; ".join(parts)
        return " ".join(str(value or "").split())[:limit]

    q = clean(question, 300).lower()
    urgency = clean(ctx.get("urgency") or ctx.get("risk_level"), 30).lower()
    possibilities = clean(ctx.get("possible_conditions"), 650)
    recommendations = clean(ctx.get("recommendations"), 650)
    danger = clean(ctx.get("danger_signs") or ctx.get("emergency_flags"), 650)
    seek = clean(ctx.get("when_to_seek_care"), 500)
    urgent = urgency in {"high", "urgent", "emergency"}

    if urgent:
        return (
            "النتيجة صنّفت الحالة كعاجلة. لا تنتظر شرحًا إضافيًا ولا تعتمد على الاحتمالات المعروضة؛ اتصل بالإسعاف 997 أو توجّه إلى أقرب طوارئ الآن. "
            "هذه إرشادات سلامة وليست تشخيصًا."
            if ar else
            "The result classified this as urgent. Do not wait for another explanation or rely on the listed possibilities; call emergency services or go to the nearest ER now. This is safety guidance, not a diagnosis."
        )
    if any(k in q for k in (("خطر", "طوارئ", "متى أراجع", "علامات") if ar else ("danger", "urgent", "emergency", "when should", "warning"))):
        detail = danger or seek
        return (("علامات الانتباه المذكورة في نتيجتك: " + detail + " إذا ظهرت علامة جديدة أو ساءت الأعراض، اطلب تقييمًا طبيًا عاجلًا. هذه معلومات توعوية وليست تشخيصًا.")
                if ar and detail else
                ("راقب أي تدهور واضح أو ظهور علامة خطر جديدة، واطلب تقييمًا طبيًا عاجلًا عند حدوث ذلك. هذه معلومات توعوية وليست تشخيصًا.")
                if ar else
                ("Warning signs listed in your result: " + detail + " Seek urgent medical assessment if a new warning sign appears or symptoms worsen. This is educational information, not a diagnosis.")
                if detail else
                "Watch for clear worsening or any new warning sign, and seek urgent medical assessment if that happens. This is educational information, not a diagnosis.")
    if any(k in q for k in (("ماذا أفعل", "وش أسوي", "الخطوة", "العلاج") if ar else ("what should i do", "next step", "treatment"))):
        detail = recommendations or seek
        if detail:
            return (("الخطوة المقترحة في نتيجتك: " + detail + " لا تبدأ أو توقف دواءً موصوفًا دون سؤال طبيب أو صيدلي. هذه معلومات توعوية وليست تشخيصًا.")
                    if ar else
                    ("The suggested next step in your result is: " + detail + " Do not start or stop prescribed medicine without asking a clinician or pharmacist. This is educational information, not a diagnosis."))
    if possibilities:
        return (("ظهرت هذه الاحتمالات لأنها تشترك مع بعض الأعراض التي أدخلتها: " + possibilities + " ترتيبها لا يؤكد مرضًا بعينه، وقد تتشابه الأعراض بين حالات مختلفة. راجع مختصًا إذا استمرت الأعراض أو ساءت.")
                if ar else
                ("These possibilities appeared because they overlap with some of the symptoms you entered: " + possibilities + " Their order does not confirm a condition, and different conditions can share symptoms. Seek medical review if symptoms persist or worsen."))
    local = _assistant_local_health_answer(question, lang)
    return local or (("لا تتوفر تفاصيل كافية لشرح أدق الآن. راقب الأعراض واطلب تقييمًا طبيًا إذا استمرت أو ازدادت. هذه معلومات توعوية وليست تشخيصًا.")
                     if ar else
                     "There is not enough detail for a more specific explanation right now. Monitor symptoms and seek medical review if they persist or worsen. This is educational information, not a diagnosis.")

def _assistant_contextual_health_answer(text, lang):
    """Handle short health phrases whose meaning depends on their modifier/context.

    The generic health search can otherwise reduce a phrase such as
    "غثيان الدورة" to the standalone topic "غثيان". Keep the full phrase
    intact for common context-dependent intents before generic topic lookup.
    """
    query = " ".join(str(text or "").strip().split())[:600]
    if not query:
        return None
    low = query.lower()
    norm = _normalize_health_query_text(query)
    ar = lang != "en"

    # V60 curated phrase-level contexts. These are checked before generic topic
    # search so modifiers such as timing/trigger are not silently discarded.
    for item in globals().get("ASSISTANT_CONTEXT_PATTERNS_V60", ()):
        if ar:
            has_topic = any(_normalize_health_query_text(k) in norm for k in item.get("ar_any", []))
            has_context = any(_normalize_health_query_text(k) in norm for k in item.get("ar_context", []))
            if has_topic and has_context:
                return item.get("ar")
        else:
            has_topic = any(str(k).lower() in low for k in item.get("en_any", []))
            has_context = any(str(k).lower() in low for k in item.get("en_context", []))
            if has_topic and has_context:
                return item.get("en")

    # Heat-related dizziness: preserve the trigger/context instead of reducing
    # a phrase such as "أحس بدوخة وقت الحر" to generic dizziness.
    dizziness_ar = ("دوخه", "دوار", "ادوخ", "دايخ", "دايخه", "لف الدنيا", "عدم اتزان")
    heat_ar = ("وقت الحر", "بالحر", "مع الحر", "في الحر", "من الحر", "الجو حار", "الجو الحار", "جو حار", "حر شديد", "تحت الشمس", "في الشمس", "بالشمس", "من الشمس", "وقت الشمس")
    dizziness_en = ("dizzy", "dizziness", "lightheaded", "light-headed", "vertigo")
    heat_en = ("hot weather", "in the heat", "when it is hot", "when it's hot", "when its hot", "under the sun", "in the sun", "heat exposure")
    has_dizziness = any(_normalize_health_query_text(k) in norm for k in dizziness_ar) if ar else any(k in low for k in dizziness_en)
    has_heat_context = any(_normalize_health_query_text(k) in norm for k in heat_ar) if ar else any(k in low for k in heat_en)
    if has_dizziness and has_heat_context:
        if ar:
            return (
                "الدوخة وقت الحر قد تكون من علامات الإجهاد الحراري أو الجفاف مع التعرّق. "
                "انتقل لمكان بارد واجلس، وبرّد الجلد بالماء، واشرب السوائل إذا كنت واعيًا وقادرًا على البلع. "
                "اطلب الطوارئ عند التشوش أو الإغماء أو حرارة شديدة، أو إذا لم تتحسن بعد 30 دقيقة من التبريد. "
                "هل تخف الدوخة بعد الابتعاد عن الحر؟ "
                "هذه معلومات توعوية وليست تشخيصًا."
            )
        return (
            "Dizziness in hot weather may indicate heat exhaustion or dehydration from sweating. "
            "Move somewhere cool, sit down, cool your skin with water, and drink fluids if fully alert and able to swallow. "
            "Seek emergency help for confusion, fainting, very high temperature, or no improvement after 30 minutes of cooling. "
            "Does the dizziness ease away from the heat? "
            "This is educational information, not a diagnosis."
        )

    # Menstrual-period nausea: answer the combined intent, not generic nausea.
    period_ar = ("الدوره", "الحيض", "الطمث")
    nausea_ar = ("غثيان", "لوعه", "لوعة", "ترجيع", "استفراغ", "قيء")
    period_en = ("period", "menstrual", "menstruation", "menses")
    nausea_en = ("nausea", "nauseous", "vomit", "vomiting", "sick")
    has_period = any(_normalize_health_query_text(k) in norm for k in period_ar) if ar else any(k in low for k in period_en)
    has_nausea = (("غث" in norm) or any(_normalize_health_query_text(k) in norm for k in nausea_ar)) if ar else any(k in low for k in nausea_en)
    if has_period and has_nausea:
        if ar:
            return (
                "الغثيان مع الدورة ممكن يحصل عند بعض الأشخاص بسبب تغيّرات الهرمونات ومواد مثل البروستاغلاندينات، خصوصًا إذا كان معه مغص. "
                "يمكن تجربة وجبات خفيفة وتناول السوائل على دفعات مع الراحة. إذا كان القيء متكررًا أو تعذر الاحتفاظ بالسوائل، أو ظهرت دوخة أو إغماء أو نزيف شديد أو ألم غير معتاد، فالأفضل طلب تقييم طبي. "
                "هذه معلومات توعوية وليست تشخيصًا."
            )
        return (
            "Nausea around a period can happen for some people because of hormonal changes and prostaglandins, especially when cramps are present. "
            "Small meals, frequent sips of fluid, and rest may help. Seek medical care if vomiting is repeated, you cannot keep fluids down, you feel faint, bleeding is unusually heavy, or pain is severe/unusual. "
            "This is educational information, not a diagnosis."
        )

    return None

# Source-reviewed symptom education. No diagnosis or medicine doses are inferred.
# NHS references reviewed 2026-09-14; keep the bilingual copy alongside its source.
ASSISTANT_EXTRA_SYMPTOMS = [
    ("تساقط الشعر", "Hair loss", ["شعري يتساقط", "شعري يطيح", "تساقط الشعر", "hair loss", "hair falling out"],
     "قد يرتبط تساقط الشعر بالوراثة أو الضغط النفسي أو مرض سابق أو نقص الحديد. فحص فروة الرأس يساعد على تحديد السبب قبل اختيار العلاج.",
     "Hair loss can relate to family history, stress, previous illness, or iron deficiency. A scalp assessment helps identify the cause before choosing treatment.",
     "هل التساقط منتشر أم على شكل فراغات محددة؟", "Is the loss widespread or in distinct patches?", "https://www.nhs.uk/symptoms/hair-loss/"),
    ("الإمساك", "Constipation", ["امساك", "الإمساك", "البراز قاسي", "صعوبة التبرز", "constipation", "hard stools"],
     "قد تساعد زيادة الألياف تدريجيًا والسوائل والحركة على الإمساك. راجع مختصًا إذا استمر أو صاحبه دم في البراز أو نقص وزن غير مقصود؛ ولا توقف دواءً موصوفًا من نفسك.",
     "Gradually increasing fibre, fluids, and activity may help constipation. Seek review if it persists or occurs with blood in stool or unintentional weight loss; do not stop prescribed medicines on your own.",
     "منذ متى تغيّر التبرز عن المعتاد؟", "How long have your bowel habits differed from normal?", "https://www.nhs.uk/conditions/constipation/"),
    ("ألم الأسنان", "Toothache", ["الم الاسنان", "ضرس يوجع", "ضرسي يعورني", "ضرسي يوجعني", "اسناني توجعني", "toothache", "tooth pain", "tooth hurts"],
     "ألم الأسنان يحتاج طبيب أسنان لتحديد السبب، خصوصًا إذا استمر أكثر من يومين أو صاحبه تورم أو حرارة. تورم الفم أو الرقبة مع صعوبة التنفس أو البلع يستدعي الطوارئ.",
     "A dentist can identify the cause of toothache, especially if it lasts over 2 days or comes with swelling or fever. Mouth or neck swelling with breathing or swallowing difficulty needs emergency care.",
     "هل يوجد تورم أو ألم عند العض؟", "Is there swelling or pain when biting?", "https://www.nhs.uk/symptoms/toothache/"),
    ("ألم الرقبة", "Neck pain", ["الم الرقبه", "رقبتي توجعني", "رقبتي تعورني", "تيبس الرقبه", "neck pain", "stiff neck", "neck hurts"],
     "قد يرتبط ألم الرقبة بوضعية النوم أو الجلوس أو شد العضلات، لكن هذا لا يحدد السبب لديك. راجع مختصًا إذا استمر لأسابيع أو صاحبه وخز أو برودة في الذراع.",
     "Neck pain can relate to sleeping position, posture, or muscle strain, but that does not establish your cause. Seek review if it lasts weeks or comes with tingling or a cold arm.",
     "هل بدأ بعد إصابة أم دون إصابة؟", "Did it begin after an injury or without one?", "https://www.nhs.uk/symptoms/neck-pain-and-stiff-neck/"),
    ("حكة الجلد", "Itchy skin", ["حكه", "جلدي يحكني", "جسمي يحكني", "حكة الجلد", "itchy skin", "itching"],
     "قد تكون الحكة مرتبطة بجفاف الجلد أو تهيجه. تجنب المنتجات المعطرة واستخدم مرطبًا غير معطر. اطلب تقييمًا إذا كانت شديدة أو منتشرة أو مستمرة أو أثناء الحمل.",
     "Itching can relate to dry or irritated skin. Avoid perfumed products and use an unperfumed moisturiser. Seek assessment if it is severe, widespread, persistent, or occurs during pregnancy.",
     "هل الحكة في مكان محدد، وهل معها طفح؟", "Is the itching localised, and is there a rash?", "https://www.nhs.uk/symptoms/itchy-skin/"),
    ("الرعشة", "Tremor", ["رعشه", "رجفه", "يدي ترجف", "يديني ترجف", "tremor", "shaking hands", "hands shake"],
     "قد تصبح الرعشة أوضح مع التعب أو التوتر أو الكافيين، وقد ترتبط بأدوية أو حالات أخرى. تحتاج تقييمًا إذا زادت أو أثرت على نشاطك؛ ولا توقف دواءً موصوفًا دون مراجعة.",
     "Tremor may become more noticeable with tiredness, stress, or caffeine; medicines and other conditions can also contribute. Seek assessment if it worsens or affects activities; do not stop prescribed medicine without advice.",
     "هل تظهر في الراحة أم عند استعمال اليد؟", "Does it happen at rest or when using your hand?", "https://www.nhs.uk/symptoms/tremor-or-shaking-hands/"),
    ("مشكلات الذاكرة", "Memory problems", ["انسى كثير", "انسي كثير", "نسيان متكرر", "مشاكل الذاكره", "memory problems", "memory loss", "forget things"],
     "النسيان المتكرر قد يرتبط بالتوتر أو مشكلات النوم أو أسباب أخرى قابلة للعلاج. إذا أثر على حياتك اليومية فاحجز تقييمًا، ولا تفترض أنه سبب واحد محدد.",
     "Repeated forgetfulness can relate to stress, sleep problems, or other treatable causes. Arrange assessment if it affects daily life rather than assuming one particular cause.",
     "هل بدأ حديثًا أم زاد تدريجيًا؟", "Did it start recently or increase gradually?", "https://www.nhs.uk/symptoms/memory-loss-amnesia/"),
    ("العطش الزائد", "Excessive thirst", ["عطش زايد", "عطش زائد", "عطشان دايم", "عطشان دائما", "عطش مستمر", "excessive thirst", "always thirsty"],
     "العطش المستمر رغم شرب السوائل يحتاج تقييمًا إذا استمر عدة أيام، خصوصًا مع كثرة التبول. قد يراجع الطبيب أسبابًا مثل الأدوية أو السكري؛ العطش وحده لا يؤكد التشخيص.",
     "Persistent thirst despite drinking needs assessment if it lasts several days, especially with frequent urination. A clinician may check causes such as medicines or diabetes; thirst alone does not confirm a diagnosis.",
     "هل يصاحبه تبول أكثر من المعتاد؟", "Are you urinating more often than usual?", "https://www.nhs.uk/symptoms/thirst/"),
]

# V60: broaden deterministic assistant coverage while keeping emergency triage first.
ASSISTANT_EXTRA_SYMPTOMS.extend(ASSISTANT_EXTRA_SYMPTOMS_V60)

def _assistant_phrase_present(query, phrase):
    """Whole normalized words: avoid matching, for example, 'مع' in 'معدة'."""
    import re as _re
    query = _normalize_health_query_text(query)
    phrase = _normalize_health_query_text(phrase)
    return bool(phrase and _re.search(r"(?<!\w)" + _re.escape(phrase) + r"(?!\w)", query))

def _assistant_has_context(query):
    markers = ("وقت", "بعد", "قبل", "مع", "اثناء", "خلال", "لما", "عندما", "بالليل", "الصباح",
               "when", "after", "before", "during", "with", "at night", "pregnant", "حامل")
    return any(_assistant_phrase_present(query, marker) for marker in markers)

def _assistant_extended_symptom_reply(query, lang):
    """Answer newly covered symptoms, or ask a specific question about context."""
    ar = lang != "en"
    matches = [row for row in ASSISTANT_EXTRA_SYMPTOMS
               if any(_assistant_phrase_present(query, alias) for alias in row[2])]
    if not matches:
        return None
    # Negation and multiple symptoms need clarification, not a guessed diagnosis.
    # If the matched alias itself already contains the timing/trigger (for
    # example "عرق بالليل"), treat that context as covered instead of
    # downgrading a curated answer to a generic clarification question.
    row = matches[0]
    matched_aliases = [alias for alias in row[2] if _assistant_phrase_present(query, alias)]
    context_is_covered = any(_assistant_has_context(alias) for alias in matched_aliases)
    uncertain = ((_assistant_has_context(query) and not context_is_covered) or len(matches) > 1 or any(
        _assistant_phrase_present(query, word) for word in ("بدون", "ما عندي", "ليس", "no", "not", "without")))
    if uncertain:
        answer = (("بخصوص «" + query + "»: ارتباط الأعراض أو توقيتها يحتاج تفاصيل إضافية. " + row[5])
                  if ar else ("About “" + query + "”: the symptom combination or timing needs more detail. " + row[6]))
        return {"answer": answer, "sources": []}
    answer = (row[3] + " " + row[5] + " هذه معلومات توعوية وليست تشخيصًا.") if ar else (
        row[4] + " " + row[6] + " This is educational information, not a diagnosis.")
    return {"answer": answer, "sources": [{"title": (row[0] if ar else row[1]) + " — NHS", "url": row[7], "source_name": "NHS"}]}

def _assistant_local_health_answer(text, lang):
    """Build a useful offline/general-health answer from curated local knowledge.

    This is used only when the external assistant provider is unavailable. It
    does not diagnose or calculate a new medical score; it summarizes the
    existing curated health-search content so simple questions such as
    "دوخة" still receive a useful answer.
    """
    query = (text or "").strip()[:600]
    if not query:
        return None
    curated = health_search.curated_result(query, lang)
    if curated is not None:
        return curated["direct_answer"]
    contextual = _assistant_contextual_health_answer(query, lang)
    if contextual:
        return contextual
    extended = _assistant_extended_symptom_reply(query, lang)
    if extended:
        return extended["answer"]
    try:
        result = health_search.search_health(query, lang)
    except Exception:
        logging.getLogger(__name__).warning("Handled exception in _assistant_local_health_answer; fallback applied (handler 16588)")
        result = None
    if not result:
        return _assistant_general_local_fallback(query, lang)

    ar = lang != "en"

    def _clean(value):
        return " ".join(str(value or "").split())

    def _topic_block(topic):
        title = _clean(topic.get("title"))
        what = _clean(topic.get("what"))
        causes = [_clean(x) for x in (topic.get("causes") or []) if _clean(x)][:4]
        worry = _clean(topic.get("worry"))
        doctor = _clean(topic.get("doctor"))
        emoji = _clean(topic.get("emoji")) or "🩺"
        lines = [f"{emoji} {title}" if title else emoji]
        if what:
            lines.append(what)
        if causes:
            label = _clean(topic.get("causes_label")) or ("أسباب محتملة" if ar else "Possible causes")
            lines.append(label + ": " + ("، " if ar else ", ").join(causes) + ".")
        if worry:
            lines.append(("متى يحتاج الأمر انتباهًا؟ " if ar else "When to seek urgent attention: " ) + worry)
        elif doctor:
            lines.append(("متى تُطلب مراجعة طبية؟ " if ar else "When to seek medical review: " ) + doctor)
        return "\n".join(lines)

    # If the query contains an important timing/trigger modifier but the local
    # search only found a generic topic, do not pretend that generic topic is
    # an answer to the full question. Prefer the exact-query fallback instead.
    has_context_modifier = _assistant_has_context(query)

    topics = result.get("matched_topics") or []
    if has_context_modifier:
        # `result` is usually one broad topic here. A context-aware local
        # handler above would already have returned if we can answer safely.
        # Otherwise preserve the full question instead of dropping its modifier.
        return (
            "سؤالك عن «" + query + "»؛ توقيت العرض أو ما يسبقه مهم، ولا تكفي معلومات عامة عن العرض لتفسيره. "
            "لا تتوفر لدي إجابة موثوقة تخص هذا الارتباط الآن. هل يتكرر في نفس الظروف، وكم يستمر؟ "
            "إذا صاحبه إغماء أو ألم صدر أو ضيق تنفس شديد، اطلب الطوارئ."
            if ar else
            "Your question is about “" + query + "”. Its timing or trigger matters; general symptom information does not explain that connection. "
            "I do not have a reliable answer for this specific connection right now. Does it recur in the same circumstances, and how long does it last? "
            "Seek emergency help for fainting, chest pain, or severe breathing difficulty."
        )
    if topics:
        intro = (
            "تعرفت على أكثر من عرض أو مفهوم في سؤالك. وجودها معًا لا يعني أن لها سببًا واحدًا، وهذه معلومات مختصرة عن كل واحد:"
            if ar else
            "I recognized more than one symptom or health concept. Having them together does not mean they share one cause; here is brief information about each:"
        )
        blocks = [_topic_block(t) for t in topics[:2]]
        answer = intro + "\n\n" + "\n\n".join(blocks)
    else:
        answer = _topic_block(result)

    disclaimer = (
        "هذه معلومات توعوية وليست تشخيصًا. إذا كانت الأعراض شديدة أو مستمرة أو تزداد سوءًا، فاطلب تقييمًا طبيًا."
        if ar else
        "This is awareness information, not a diagnosis. If symptoms are severe, persistent, or worsening, seek medical evaluation."
    )
    return (answer + "\n\n" + disclaimer).strip()

def _assistant_local_mental_answer(text, lang):
    """Safe, deterministic fallback for the mental-wellbeing assistant.

    Import locally so this helper stays self-contained in static regression
    tests as well as in normal app execution.
    """
    import mental_support as _mental_support
    answer = _mental_support.supportive_answer(text, lang)
    if not answer:
        return None
    # Keep ordinary replies conversational. The mental-health panel shows the
    # digital-support / not-a-professional disclosure once when the mode opens;
    # repeating it after every message makes the conversation feel scripted.
    return answer

def _assistant_services(text, lang):
    low = text.lower()
    if lang == "en":
        if any(k in low for k in ("calculator", "bmi", "body mass", "calorie", "fluid", "water intake", "dose interval", "blood sugar level", "sugar level")):
            return [{"label": "Health Calculators", "url": "/calculators"}]
        if any(k in low for k in ("what is", "what's", "meaning", "means", "explain", "what does")):
            return [{"label": "Health search", "url": "/search"}]
        if any(k in low for k in ("blood test", "cbc", "hemoglobin result", "lab result", "laboratory result", "test results")):
            return [{"label": "Blood test analysis", "url": "/blood"}]
        if any(k in low for k in ("symptom", "pain", "cough", "fever", "headache", "dizziness", "dizzy", "nausea", "numbness", "feel", "aching")):
            return [{"label": "Symptom check", "url": "/chat"}]
        if any(k in low for k in ("family", "mom", "mother", "dad", "father", "child", "kids")):
            return [{"label": "Family Health Hub", "url": "/family"}]
        if any(k in low for k in ("medication", "drug", "medicine", "pill", "dose")):
            return [{"label": "Medications page", "url": "/meds"}]
        if any(k in low for k in ("hospital", "clinic", "doctor", "emergency")):
            return [{"label": "Nearest hospital", "url": "/emergency#geo"}]
    else:
        if any(k in low for k in ("حاسبة", "مؤشر كتلة", "كتلة الجسم", "bmi", "سعرات", "احتياج السوائل", "شرب الماء", "فاصل الجرعات", "مواعيد الدواء", "قراءة السكر")):
            return [{"label": "الحاسبات الصحية", "url": "/calculators"}]
        if any(k in low for k in ("معنى", "ما هو", "ما هي", "اشرح", "تفسير", "وش يعني", "يعني ايش")):
            return [{"label": "البحث الصحي", "url": "/search"}]
        if any(k in low for k in ("تحليل دم", "تحليل الدم", "فحص دم", "فحص الدم", "cbc", "نتيجة المختبر", "نتائج المختبر", "نتيجة التحليل", "نتائج التحاليل", "هيموجلوبين")):
            return [{"label": "تحليل فحص الدم", "url": "/blood"}]
        if any(k in low for k in ("ألم", "أعراض", "سعال", "حرارة", "صداع", "دوخة", "دوار", "غثيان", "تنميل", "أشعر", "مرض")):
            return [{"label": "تحليل الأعراض", "url": "/chat"}]
        if any(k in low for k in ("عائلة", "أمي", "أبي", "أم ", "ابني", "ابنتي", "الطفل", "فرد")):
            return [{"label": "مركز صحة العائلة", "url": "/family"}]
        if any(k in low for k in ("دواء", "أدوية", "حبة", "جرعة")):
            return [{"label": "صفحة الأدوية", "url": "/meds"}]
        if any(k in low for k in ("مستشفى", "عيادة", "طبيب", "طوارئ")):
            return [{"label": "أقرب مستشفى", "url": "/emergency#geo"}]
    return []

def _assistant_compact_response(answer, lang="ar", mode=""):
    """Keep ordinary assistant replies short even if a provider ignores the prompt.

    Emergency / crisis instructions are intentionally left untouched so safety
    information and phone numbers are never truncated.
    """
    text = str(answer or "").strip()
    if not text:
        return text
    low = text.lower()
    safety_markers = ("997", "937", "emergency", "طوارئ", "انتحار", "إيذاء النفس", "self-harm", "suicide")
    if any(marker in low for marker in safety_markers):
        return text
    max_words = 70 if mode == "mh" else 80
    words = text.split()
    if len(words) <= max_words:
        return text

    # Prefer ending at a sentence boundary near the limit instead of cutting
    # a sentence in the middle. If none exists, use a clean word limit.
    import re as _re
    sentences = _re.split(r'(?<=[.!?؟])\s+', text)
    kept = []
    count = 0
    for sent in sentences:
        sw = sent.split()
        if kept and count + len(sw) > max_words:
            break
        if not kept and len(sw) > max_words:
            break
        kept.append(sent.strip())
        count += len(sw)
        if count >= max_words:
            break
    if kept:
        compact = " ".join(x for x in kept if x).strip()
        if compact:
            return compact
    return " ".join(words[:max_words]).rstrip("،,;:") + ("…" if lang == "ar" else "…")

def _checkin_api_payload(account_id, day):
    rows = db.get_web_daily_checkin_history(account_id, limit=180)
    today = db.get_web_daily_checkin_for_date(account_id, day)
    try:
        end_day = datetime.strptime(day, "%Y-%m-%d").date()
    except (TypeError, ValueError, OverflowError):
        logging.getLogger(__name__).debug("Handled exception in _checkin_api_payload; fallback applied (handler 16934)")
        end_day = datetime.now(timezone.utc).date()
    start_day = end_day - timedelta(days=6)
    recent = []
    for row in rows:
        try:
            row_day = datetime.strptime(str(row.get("date") or ""), "%Y-%m-%d").date()
        except (TypeError, ValueError, OverflowError):
            logging.getLogger(__name__).debug("Handled exception in _checkin_api_payload; fallback applied (handler 16941)")
            continue
        if start_day <= row_day <= end_day:
            recent.append(row)
    avg = round(sum(float(r.get("value") or 0) for r in recent) / len(recent), 1) if recent else None
    return {
        "ok": True,
        "today": today,
        "rows": [{"date": r.get("date"), "value": int(r.get("value") or 0)} for r in rows],
        "summary": {"count": len(rows), "last7_average": avg},
        "storage_version": "user_data_v1",
    }

def _normalize_health_query_text(value):
    """Normalize Arabic/English health-search text for robust context matching."""
    import re as _re
    text = " ".join(str(value or "").strip().lower().split())
    # Arabic diacritics/tatweel and common letter variants.
    text = _re.sub(r"[\u064b-\u065f\u0670\u0640]", "", text)
    text = text.translate(str.maketrans({"أ":"ا","إ":"ا","آ":"ا","ى":"ي","ؤ":"و","ئ":"ي","ة":"ه"}))
    return text

from search_support import (_health_search_topic_meta, _health_search_tokens,  # noqa: E402
                            _health_search_result_relevant, _health_search_query_shell)

def _health_search_medication_context(query, lang):
    """Find a medicine mentioned anywhere in the user's full search query.

    The medication page normally searches an exact drug name. Health search is
    different: users write relationships such as "دوخة مع مونجارو". This helper
    extracts the medicine without discarding the rest of the question.
    """
    import re as _re
    q = " ".join(str(query or "").strip().split())[:600]
    if not q:
        return None
    norm = _normalize_health_query_text(q)

    # A small high-confidence bridge for tirzepatide/Mounjaro. This is kept here
    # because older production medication tables may not yet contain the brand.
    mounjaro_aliases = (
        "منجارو", "المنجارو", "مونجارو", "المونجارو", "تيرزيباتيد", "تيرزيباتايد",
        "mounjaro", "tirzepatide",
    )
    if any(_normalize_health_query_text(a) in norm for a in mounjaro_aliases):
        return {
            "slug": "mounjaro_tirzepatide",
            "name_ar": "مونجارو (تيرزيباتيد)",
            "name_en": "Mounjaro (tirzepatide)",
            "uses_ar": "دواء يُستخدم لتحسين التحكم بسكر الدم لدى بعض البالغين المصابين بالسكري من النوع الثاني وفق الوصفة الطبية.",
            "uses_en": "A prescription medicine used to improve blood sugar control in some adults with type 2 diabetes.",
            "warning_ar": "قد يسبب أعراضًا هضمية مثل الغثيان أو القيء أو الإسهال، وقد يؤدي فقدان السوائل إلى الجفاف. يزداد خطر انخفاض السكر عند استخدامه مع الإنسولين أو أدوية تحفّز إفراز الإنسولين.",
            "warning_en": "It can cause gastrointestinal effects such as nausea, vomiting, or diarrhea, which may lead to dehydration. The risk of low blood sugar is higher when used with insulin or insulin secretagogues.",
            "interact_ar": "يزداد خطر انخفاض السكر عند الجمع مع الإنسولين أو أدوية مثل السلفونيل يوريا؛ أي تعديل للجرعات يكون بواسطة الطبيب.",
            "interact_en": "Low-blood-sugar risk is higher with insulin or medicines such as sulfonylureas; dose changes should be made by the prescriber.",
            "sources": [
                {"name": "FDA — Mounjaro Prescribing Information", "organization": "U.S. FDA", "url": "https://www.accessdata.fda.gov/drugsatfda_docs/label/2026/215866s009lbl.pdf"},
                {"name": "Mounjaro Prescribing Information", "organization": "Eli Lilly", "url": "https://pi.lilly.com/us/mounjaro-uspi.pdf"},
            ],
        }

    # Reuse medicines already curated in the production database. Try short
    # n-grams so "دوخة بعد المتفورمين" can still locate "متفورمين".
    tokens = _re.findall(r"[A-Za-z0-9\u0621-\u064a]+", q)
    candidates = []
    for width in (3, 2, 1):
        for i in range(0, max(0, len(tokens)-width+1)):
            piece = " ".join(tokens[i:i+width]).strip()
            if len(piece) >= 3:
                candidates.append(piece)
    seen = set()
    for piece in candidates:
        key = _normalize_health_query_text(piece)
        if key in seen:
            continue
        seen.add(key)
        try:
            d = medication_warnings.lookup_drug(piece)
        except Exception:
            logging.getLogger(__name__).warning("Handled exception in _health_search_medication_context; fallback applied (handler 17182)")
            d = None
        if d:
            return {
                "slug": "local_medication",
                "name_ar": d.get("name_ar") or piece,
                "name_en": d.get("name_en") or piece,
                "uses_ar": d.get("uses_ar") or "",
                "uses_en": d.get("uses_en") or "",
                "warning_ar": d.get("warning_ar") or "",
                "warning_en": d.get("warning_en") or "",
                "interact_ar": d.get("interact_ar") or "",
                "interact_en": d.get("interact_en") or "",
                "sources": [],
            }
    return None

def _health_search_symptom_for_relation(query, lang, medication=None):
    """Extract a symptom/health topic from a relationship query without losing the modifier.

    The old implementation searched the whole phrase once.  A fuzzy matcher can
    then choose one token and silently discard the medicine/context.  Here we
    first try the full query, then a residual query with the recognized medicine
    removed.  Only a real symptom result is accepted.
    """
    import re as _re
    q = " ".join(str(query or "").strip().split())[:600]
    if not q:
        return None

    probes = [q]
    residual = q
    med = medication or {}
    names = [
        med.get("name_ar"), med.get("name_en"),
        "منجارو", "المنجارو", "مونجارو", "المونجارو", "تيرزيباتيد", "تيرزيباتايد",
        "mounjaro", "tirzepatide",
    ]
    for name in names:
        if not name:
            continue
        residual = _re.sub(_re.escape(str(name)), " ", residual, flags=_re.IGNORECASE)
    # Remove only relationship glue; keep the symptom words and useful timing.
    glue = (
        r"\b(?:مع|بسبب|من|بعد|قبل|اثناء|أثناء|وقت|عند|هل|ليش|لماذا|وش|ايش|ماذا)\b"
        if lang != "en" else
        r"\b(?:with|from|because|after|before|during|while|when|is|does|can|why|what)\b"
    )
    residual = _re.sub(glue, " ", residual, flags=_re.IGNORECASE)
    residual = " ".join(residual.split()).strip(" -–—؟?")
    if residual and residual != q:
        probes.append(residual)

    seen = set()
    for probe in probes:
        key = _normalize_health_query_text(probe)
        if not key or key in seen:
            continue
        seen.add(key)
        try:
            candidate = health_search.search_health(probe, lang)
        except Exception:
            logging.getLogger(__name__).warning("Handled exception in _health_search_symptom_for_relation; fallback applied (handler 17245)")
            candidate = None
        if isinstance(candidate, dict) and candidate.get("category") == "symptom":
            return candidate
    return None

def _strip_search_answer_heading(value, lang):
    """Remove accidental duplicated labels such as 'إجابة على سؤالك'."""
    import re as _re
    text = str(value or "").strip()
    if not text:
        return ""
    if lang == "en":
        patterns = [r"^\s*(?:answer to your question|answer|summary)\s*[:\-–—]*\s*"]
    else:
        patterns = [r"^\s*(?:إجابة\s+على\s+سؤالك|الاجابة\s+على\s+سؤالك|الإجابة\s+على\s+سؤالك|الخلاصة)\s*[:\-–—]*\s*"]
    for pat in patterns:
        text = _re.sub(pat, "", text, count=1, flags=_re.IGNORECASE).strip()
    return text

@lru_cache(maxsize=1)
def _plain_topic_alias_set():
    return frozenset(clinical_text.normalize_clinical_text(alias)
                     for entry in health_search._CURATED_KB.values() for alias in entry.get("aliases", ()))


def _plain_topic_curated_result(query, lang):
    """Curated card for a bare topic name (exact alias match), else None."""
    norm = clinical_text.normalize_clinical_text(query)
    if norm and norm in _plain_topic_alias_set():
        return health_search.curated_result(query, lang)
    return None


@app.route("/api/explain")
def api_explain():
    try:
        lang = "en" if request.args.get("lang") == "en" else "ar"
        term = (request.args.get("term") or "").strip()[:120]
        return jsonify({"ok": True, "result": health_search.explain_term(term, lang) if term else None})
    except Exception as e:
        return _mk_error(e, 500)

def _checkin_chart(rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    base = os.path.dirname(os.path.abspath(__file__))
    for p in (
        os.path.join(base, "fonts", "NotoSansArabic-Regular.ttf"),
        os.path.join(base, "NotoSansArabic-Regular.ttf"),
    ):
        if os.path.exists(p):
            font_manager.fontManager.addfont(p)
            plt.rcParams["font.family"] = font_manager.FontProperties(fname=p).get_name()
            break
    days = [d[0][5:] for d in rows]
    vals = [d[1] for d in rows]
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.plot(range(len(vals)), vals, marker="o", color="#42A5F5", linewidth=2)
    ax.set_ylim(0.5, 5.5)
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_xticks(range(len(days)))
    ax.set_xticklabels(days, fontsize=9)
    ax.set_title("تحسن حالتك" if _lang() == "ar" else "Your improvement")
    ax.set_ylabel("الشدة" if _lang() == "ar" else "Severity")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140)
    plt.close(fig)
    buf.seek(0)
    return "data:image/png;base64," + base64.b64encode(buf.read()).decode()

@app.route("/api/tip")
def api_tip():
    return jsonify(health_tips.get_tip_card("en" if _lang() == "en" else "ar"))

@app.route("/api/firstaid/<key>")
def api_firstaid(key):
    lang = "en" if _lang() == "en" else "ar"
    label, text = wellbeing.first_aid_text(key, lang)
    return jsonify({"label": label, "text": text})

def _downscale_jpeg(image_bytes, max_side=1600, quality=85):
    """Decode an uploaded image with explicit pixel bounds before raster load.

    Phone cameras frequently store portrait orientation in EXIF instead of the
    pixel matrix, so transpose before sending the normalized JPEG to vision.
    """
    from PIL import Image, ImageOps
    img = Image.open(io.BytesIO(image_bytes))
    w, h = img.size
    if w <= 0 or h <= 0 or w > 12000 or h > 12000 or (w * h) > 25_000_000:
        raise ValueError("image_dimensions_too_large")
    img = ImageOps.exif_transpose(img).convert("RGB")
    # EXIF transpose can swap width/height. Re-read dimensions so portrait
    # camera photos are never stretched while being normalized.
    w, h = img.size
    scale = min(1.0, max_side / max(w, h))
    if scale < 1.0:
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=quality, optimize=True)
    return out.getvalue()

def _safe_pdf_page_png(page, max_side=1800, max_pixels=6_000_000):
    """Rasterize one PDF page without allowing pathological page dimensions."""
    import fitz
    rect = page.rect
    w, h = float(rect.width), float(rect.height)
    if w <= 0 or h <= 0 or w > 50_000 or h > 50_000:
        raise ValueError("pdf_page_dimensions_invalid")
    scale = min(1.5, max_side / max(w, h), (max_pixels / (w * h)) ** 0.5)
    if not (scale > 0):
        raise ValueError("pdf_page_scale_invalid")
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    if pix.width * pix.height > max_pixels * 1.05:
        raise ValueError("pdf_page_render_too_large")
    return pix.tobytes("png")

def _detect_blood_upload_kind(raw):
    """Detect a valid PDF candidate from bytes only.

    V207 blood-test intake is intentionally PDF-only. The filename and browser
    MIME type are not trusted; PyMuPDF performs structural validation later.
    """
    payload = bytes(raw or b"")
    if not payload:
        return "unknown"
    if b"%PDF-" in payload[:1024]:
        return "pdf"
    return "unknown"


def _extract_blood_from_image(client, image_bytes, audit_pass=False):
    b64 = base64.b64encode(image_bytes).decode("ascii")
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": (
                (("INDEPENDENT COMPLETENESS AUDIT. Scan the image again from top to bottom and left to right. " if audit_pass else "") +
                "Read this laboratory report conservatively. Do not diagnose, convert, infer, or invent any value. "
                "FIRST return exactly one metadata line in this format: META | LAB=<printed laboratory name or blank> | SAMPLE_DATE=<YYYY-MM-DD only if unambiguous, otherwise blank> | REPORT_DATE=<YYYY-MM-DD only if unambiguous, otherwise blank> | REPORT_TYPE=<printed/inferred panel label such as CBC, Thyroid, Lipids, or blank> | AGE=<printed age with unit or blank>. "
                "SECOND return one image-quality line: QUALITY | STATUS=<good|warn|fail> | ISSUES=<semicolon-separated issues or blank>. Use fail only when the page is materially unreadable, severely blurred/dark/overexposed, or important report content appears cut off. "
                "THEN extract EVERY laboratory test row visible, not only common CBC tests. For each test return: TEST | NAME | VALUE | UNIT | REF_LOW | REF_HIGH | STATUS | BBOX. "
                "BBOX is the approximate row rectangle as x1,y1,x2,y2 normalized from 0 to 1000; leave it blank if uncertain. Example: TEST | HGB | 130 | g/L | 130 | 170 | Normal | 115,220,900,270. "
                "Preserve the printed test name, numeric value, unit, reference limits, and the laboratory's own Normal/Low/High label when shown. For unfamiliar tests, KEEP the printed name instead of omitting it. "
                "If a unit, reference limit, status, metadata field, or BBOX is not printed/readable, leave only that field blank. Skip only test rows whose numeric result itself is unreadable. "
                "Return plain text only with no prose before or after these lines.") )},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        ],
    }]
    primary = os.environ.get("GROQ_VISION_MODEL", "qwen/qwen3.8-27b").strip() or "qwen/qwen3.8-27b"
    fallback = os.environ.get("GROQ_VISION_MODEL_FALLBACK", "").strip()
    last_error = None
    for model in dict.fromkeys([primary, fallback]):
        if not model:
            continue
        try:
            resp = client.chat.completions.create(
                model=model, messages=messages, max_completion_tokens=1800,
                temperature=0, timeout=20,
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:
            last_error = exc
            app.logger.warning("CBC vision model unavailable; model=%s error_type=%s", model, type(exc).__name__)
    if last_error:
        raise last_error
    raise RuntimeError("No Groq vision model configured")

def _register_v47_platform_once():
    if "v47_pages" not in app.blueprints:
        pages_bp, passkey_login_callback = v47_routes.create_blueprint(
            page_renderer=_page,
            lang_getter=_lang,
            current_user_id=_ss_user_id,
            current_user=_ss_user,
            login_required_decorator=login_required,
            admin_api_required_decorator=admin_api_required,
            admin_session_valid=_admin_session_valid,
            admin_login_endpoint="admin_login",
            safe_next_url=_safe_next_url,
            begin_admin_2fa_challenge=_begin_admin_2fa_challenge,
        )
        app.register_blueprint(pages_bp)
    else:
        # Blueprint already exists only in unusual import/reload scenarios.
        passkey_login_callback = lambda uid: {"authenticated": False, "next": "/login"}
    if feature_flags.API_V1 and "api_v1" not in app.blueprints:
        api_bp = api_v1.create_blueprint(
            current_user_id=_ss_user_id,
            current_user=_ss_user,
            login_user_with_passkey=passkey_login_callback,
            lang_getter=_lang,
            site_url_getter=_site_url,
            admin_allowed=lambda scope="access": bool(_admin_allowed(scope) and _admin_session_valid()),
            rate_allowed=_request_allowed,
            data_user_id_getter=_data_user_id,
            state_signing_key_getter=lambda: app.secret_key,
            session_cookie_name_getter=lambda: app.config.get("SESSION_COOKIE_NAME", "symptosense_session"),
        )
        app.register_blueprint(api_bp)

_register_v47_platform_once()
user_experience.register(app, _ss_user_id, _data_user_id, _service_consent_ok, _consent_required_json)

_STARTUP_CORE_STATE = {
    "running": False,
    "ready": False,
    "failed": False,
    "attempts": 0,
    "error_type": "",
}
_STARTUP_CORE_LOCK = threading.Lock()

_STARTUP_WARMUP_STATE = {
    "running": False,
    "finished": False,
    "warnings": [],
}
_STARTUP_WARMUP_LOCK = threading.Lock()

def _warm_optional_runtime_services():
    """Warm optional schemas/services after the web port is already available.

    Every feature below already initializes its own schema lazily when used.
    Running the warmup in the background keeps Railway's deploy-time /health
    probe independent from non-critical migrations, maintenance, backups, and
    notification workers. A failure is logged and isolated to that feature
    instead of preventing the entire site from becoming reachable.
    """
    with _STARTUP_WARMUP_LOCK:
        if _STARTUP_WARMUP_STATE["running"] or _STARTUP_WARMUP_STATE["finished"]:
            return
        _STARTUP_WARMUP_STATE["running"] = True

    # Stability-first startup: do not run a long DDL/schema storm immediately
    # after core DB readiness. Every optional module already calls init_schema()
    # lazily from the feature that needs it. The old eager list could stall on
    # medical_knowledge.init_schema() and make Railway return "upstream error"
    # even though the deployment itself was still marked Active.
    eager_optional = str(os.environ.get("STARTUP_EAGER_OPTIONAL_SCHEMAS") or "").strip().lower() in {"1", "true", "yes", "on"}
    steps = [("owner_admin", db.ensure_owner_admin_by_email)]
    if eager_optional:
        steps.extend([
            ("medical_knowledge", medical_knowledge.init_schema),
            ("background_jobs", background_jobs.init_schema),
            ("source_monitor", source_monitor.init_schema),
            ("passkeys", passkeys.init_schema),
            ("platform_v2", platform_v2.init_schema),
            ("privacy_features", privacy_features.init_schema),
            ("admin_2fa", admin_2fa.init_schema),
            ("admin_security", admin_security.init_schema),
            ("research_validation", research_validation.init_schema),
            ("research_study", research_study.init_schema),
            ("production_verification", production_verification.init_schema),
            ("advanced_features", advanced_features.init_schema),
            ("admin_operational", admin_operational.init_schema),
            ("medication_email", medication_email.init_schema),
        ])
    else:
        app.logger.info("STARTUP optional schemas mode=lazy")
    warnings = []
    for name, func in steps:
        try:
            result = func()
            if name == "owner_admin" and isinstance(result, dict):
                app.logger.info(
                    "ADMIN_AUTH startup owner_found=%s role_sync=%s reason=%s",
                    bool(result.get("found")), bool(result.get("promoted")), result.get("reason", "unknown")
                )
        except Exception as exc:
            warnings.append(name)
            app.logger.warning("STARTUP optional warmup failed step=%s error_type=%s", name, type(exc).__name__)

    # V216: database-heavy housekeeping and encrypted backup creation are not
    # allowed to compete with user requests inside the web process by default.
    # Run them from a Railway cron/worker, or explicitly opt in after sizing the
    # database/service. This prevents catalog/table locks and pg_dump work from
    # consuming the same resources as Waitress request threads.
    retention_in_web = str(os.environ.get("RETENTION_HOUSEKEEPING_IN_WEB") or "0").strip().lower() in {"1","true","yes","on"}
    if retention_in_web:
        try:
            cleanup = data_retention.run_cleanup()
            app.logger.info("RETENTION housekeeping deleted_total=%s", int(cleanup.get("deleted_total") or 0))
        except Exception as exc:
            warnings.append("retention")
            app.logger.warning("RETENTION housekeeping skipped: %s", type(exc).__name__)
    else:
        app.logger.info("RETENTION housekeeping deferred outside web process")

    backup_in_web = str(os.environ.get("BACKUP_SCHEDULER_IN_WEB") or "0").strip().lower() in {"1","true","yes","on"}
    if backup_in_web:
        try:
            if backup_restore.start_scheduler_once():
                app.logger.info("BACKUP encrypted scheduler started in web process")
        except Exception as exc:
            warnings.append("backup_scheduler")
            app.logger.warning("BACKUP scheduler not started: %s", type(exc).__name__)
    else:
        app.logger.info("BACKUP scheduler deferred outside web process")


    with _STARTUP_WARMUP_LOCK:
        _STARTUP_WARMUP_STATE["warnings"] = warnings
        _STARTUP_WARMUP_STATE["running"] = False
        _STARTUP_WARMUP_STATE["finished"] = True
    app.logger.info("STARTUP optional warmup finished warnings=%s", len(warnings))


# ---------------------------------------------------------------------------
# Medication reminder delivery worker (email baseline + optional Telegram)
# ---------------------------------------------------------------------------
_MED_REMINDER_WORKER_STARTED = False
_MED_REMINDER_WORKER_LOCK = threading.Lock()
_MED_REMINDER_WORKER_STATE = {
    "running": False,
    "last_run": None,
    "last_result": None,
    "last_error": None,
}


def _medication_reminder_delivery_loop():
    """Continuously deliver due reminders from the always-on web service."""
    interval = _bounded_env_int("MED_REMINDER_WORKER_INTERVAL_SECONDS", 30, 10, 300)
    time.sleep(2)
    while True:
        try:
            result = medication_email.send_due_emails()
            _MED_REMINDER_WORKER_STATE["running"] = True
            _MED_REMINDER_WORKER_STATE["last_run"] = datetime.now(timezone.utc).isoformat()
            _MED_REMINDER_WORKER_STATE["last_result"] = dict(result or {})
            _MED_REMINDER_WORKER_STATE["last_error"] = None
            if (result or {}).get("sent") or (result or {}).get("failed"):
                app.logger.info(
                    "MED_REMINDER delivery cycle sent=%s failed=%s skipped=%s provider=%s",
                    (result or {}).get("sent", 0),
                    (result or {}).get("failed", 0),
                    (result or {}).get("skipped", 0),
                    (result or {}).get("provider", "none"),
                )
        except Exception as exc:
            _MED_REMINDER_WORKER_STATE["running"] = True
            _MED_REMINDER_WORKER_STATE["last_run"] = datetime.now(timezone.utc).isoformat()
            _MED_REMINDER_WORKER_STATE["last_error"] = type(exc).__name__
            app.logger.warning("MED_REMINDER delivery cycle failed error_type=%s", type(exc).__name__)
        time.sleep(interval)


def _medication_worker_snapshot():
    """Live view of the reminder worker (the started flag is rebound at runtime, so routes must not capture it)."""
    return {"started": _MED_REMINDER_WORKER_STARTED, "state": dict(_MED_REMINDER_WORKER_STATE)}


def _start_medication_reminder_worker_once():
    global _MED_REMINDER_WORKER_STARTED
    if _MED_REMINDER_WORKER_STARTED:
        return False
    with _MED_REMINDER_WORKER_LOCK:
        if _MED_REMINDER_WORKER_STARTED:
            return False
        thread = threading.Thread(
            target=_medication_reminder_delivery_loop,
            name="symptosense-medication-reminders",
            daemon=True,
        )
        thread.start()
        _MED_REMINDER_WORKER_STARTED = True
        _MED_REMINDER_WORKER_STATE["running"] = True
        app.logger.info("MED_REMINDER embedded delivery worker started")
        return True


def _kick_medication_delivery_now():
    """Run a best-effort delivery pass immediately after save/edit."""
    def _job():
        try:
            result = medication_email.send_due_emails()
            _MED_REMINDER_WORKER_STATE["last_run"] = datetime.now(timezone.utc).isoformat()
            _MED_REMINDER_WORKER_STATE["last_result"] = dict(result or {})
            _MED_REMINDER_WORKER_STATE["last_error"] = None
        except Exception as exc:
            _MED_REMINDER_WORKER_STATE["last_error"] = type(exc).__name__
            app.logger.warning("MED_REMINDER immediate delivery check failed error_type=%s", type(exc).__name__)
    threading.Thread(target=_job, name="symptosense-medication-reminder-kick", daemon=True).start()

def _initialize_core_runtime_services():
    """Initialize the hard database dependency without delaying port binding.

    `/health` is the deploy-time liveness probe, while `/ready` reflects this
    routine's database state. Transient PostgreSQL wakeups/locks get bounded
    retries; permanent failures remain visible through readiness and Deploy Logs.
    """
    # Give the main thread a deterministic head start to bind Waitress before
    # any PostgreSQL work begins. This keeps the failure mode explicit readiness
    # (/ready may return 503 while starting) rather than a network-level unreachable container.
    time.sleep(0.5)
    with _STARTUP_CORE_LOCK:
        if _STARTUP_CORE_STATE["running"] or _STARTUP_CORE_STATE["ready"]:
            return
        _STARTUP_CORE_STATE["running"] = True
        _STARTUP_CORE_STATE["failed"] = False
        _STARTUP_CORE_STATE["error_type"] = ""

    attempts = _bounded_env_int("STARTUP_DB_INIT_ATTEMPTS", 6, 1, 10)
    for attempt in range(1, attempts + 1):
        with _STARTUP_CORE_LOCK:
            _STARTUP_CORE_STATE["attempts"] = attempt
        started = time.perf_counter()
        try:
            app.logger.info("STARTUP core database initialization attempt=%s/%s", attempt, attempts)
            db.init_db()
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            with _STARTUP_CORE_LOCK:
                _STARTUP_CORE_STATE["ready"] = True
                _STARTUP_CORE_STATE["failed"] = False
                _STARTUP_CORE_STATE["running"] = False
                _STARTUP_CORE_STATE["error_type"] = ""
            app.logger.info("STARTUP core database ready elapsed_ms=%s attempts=%s", elapsed_ms, attempt)
            _start_admin_auth_core_warmup_once()
            _start_medication_reminder_worker_once()

            def _deferred_optional_warmup():
                delay = _bounded_env_int("STARTUP_OPTIONAL_DELAY_SECONDS", 12, 0, 60)
                if delay:
                    time.sleep(delay)
                _warm_optional_runtime_services()

            threading.Thread(
                target=_deferred_optional_warmup,
                name="symptosense-optional-startup",
                daemon=True,
            ).start()
            app.logger.info("STARTUP optional services deferred")
            return
        except Exception as exc:
            error_type = type(exc).__name__
            app.logger.warning(
                "STARTUP core database attempt failed attempt=%s/%s error_type=%s",
                attempt, attempts, error_type,
            )
            with _STARTUP_CORE_LOCK:
                _STARTUP_CORE_STATE["error_type"] = error_type
            if attempt < attempts:
                # Keep total retry delay comfortably inside Railway's default
                # five-minute healthcheck window while allowing a waking DB or
                # short DDL lock to clear.
                time.sleep(min(2 * attempt, 10))

    with _STARTUP_CORE_LOCK:
        _STARTUP_CORE_STATE["running"] = False
        _STARTUP_CORE_STATE["failed"] = True
    app.logger.error("STARTUP core database initialization exhausted retries")

def run_webapp():
    railway_runtime.log_runtime_context(app.logger)
    # Bind the Railway-assigned port immediately; /ready tracks the background
    # database initialization without blocking network reachability.
    threading.Thread(
        target=_initialize_core_runtime_services,
        name="symptosense-core-startup",
        daemon=True,
    ).start()

    port = int(os.environ.get("PORT", 5000))
    app.logger.info("STARTUP web server binding host=0.0.0.0 port=%s", port)
    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=port, threads=_bounded_env_int("WEB_THREADS", 12, 4, 24))
    except ImportError:
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

routes_medications.register_routes(app, globals())

routes_labs.register_routes(app, globals())

routes_auth.register_routes(app, globals())

routes_assistant.register_routes(app, globals())

routes_tracking.register_routes(app, globals())

routes_admin.register_routes(app, globals())

routes_pages.register_routes(app, globals())

pagelib_pages_html.bind(globals())

services_search_answers.bind(globals())

if __name__ == "__main__":
    run_webapp()
