"""
webapp.py - الموقع الرسمي لـ SymptoSense
نفس محرك التحليل المستخدم في البوت (analysis_core) مع واجهة ويب عربية كاملة.
"""
import os
import io
import re
import json
import base64
import secrets
import hashlib
import hmac
import random
import time
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import parseaddr

CONTACT_TELEGRAM = os.environ.get("CONTACT_TELEGRAM", "rms_2o")

from functools import wraps
from flask import Flask, request, jsonify, render_template_string, session, send_file, send_from_directory, Response, redirect, url_for, g, abort, has_request_context

import db
import ml_diagnosis
import medication_warnings
import geo_hospitals
import blood_test
import wellbeing
import health_tips
import analysis_core
import health_search
import calculators as calcmod
import medical_knowledge
import platform_v2
import advanced_features
import admin_operational
import admin_complete
import medication_push
import privacy_features

from dashboard import DASHBOARD_HTML


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
            before_send=_scrub_sentry_event,
        )
        return True
    except Exception:
        return False


_sentry_enabled = _configure_error_monitoring()
app = Flask(__name__)
if os.environ.get("SENTRY_DSN", "").strip() and not _sentry_enabled:
    app.logger.warning("Sentry was requested but could not be initialized")
_configured_web_secret = os.environ.get("WEB_SECRET", "").strip()
# Never ship a publicly known session-signing key.  A generated development
# key is safer than a hard-coded fallback (but restarts invalidate sessions),
# while production deployments should always provide a stable WEB_SECRET.
app.secret_key = _configured_web_secret or secrets.token_hex(32)
if not _configured_web_secret:
    app.logger.warning("WEB_SECRET is not configured; using an ephemeral session key for this process")
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "0") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
)

# Do not log keys, recipients, reset tokens, or verification tokens. The detailed
# provider diagnostics are available to authenticated Admins via the endpoint
# below after the helper functions are loaded.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


V2_CSS = """
/* SymptoSense V2 — one quiet, accessible design system across every page. */
:root{--v2-blue:#287FC1;--v2-blue-dark:#163B5C;--v2-sky:#EAF5FC;--v2-bg:#F7FAFC;
--v2-card:#FFFFFF;--v2-text:#23384A;--v2-muted:#607487;--v2-line:#DCE8F0;
--v2-green:#267A52;--v2-green-bg:#EDF8F2;--v2-yellow:#8A651E;--v2-yellow-bg:#FFF8E7;
--v2-red:#A33A3A;--v2-red-bg:#FFF1F1;--v2-radius:16px;--v2-shadow:0 6px 20px rgba(31,86,127,.07)}
html{color-scheme:light}body{background:var(--v2-bg)!important;color:var(--v2-text)!important}
body[dir="ltr"]{font-family:'Poppins','Cairo','Segoe UI',sans-serif}
.container{max-width:1180px}.card,.ss-profile-card,.welcome-card,.hist-card,.manage-card,.memory-card{
background:var(--v2-card)!important;border:1px solid var(--v2-line)!important;border-radius:var(--v2-radius)!important;
box-shadow:var(--v2-shadow)!important}
.chat-wrap,.chat-options,.asst-panel{background:#fff!important;border-color:var(--v2-line)!important}.chat-body{background:#F7FAFC!important}.bubble.bot{background:#fff!important;border-color:var(--v2-line)!important;color:var(--v2-text)!important}.ss-bnav,.ss-mobile-head{background:rgba(255,255,255,.98)!important;border-color:var(--v2-line)!important}.ss-mobile-logo{color:var(--v2-blue-dark)!important}
h1,h2,h3,h4{color:var(--v2-blue-dark)}.muted{color:var(--v2-muted)!important}
.btn,.ss-btn-primary,.auth-btn{min-height:46px;border-radius:12px!important;box-shadow:none!important;font-weight:700!important}
.btn.pri,.ss-btn-primary,.auth-btn{background:var(--v2-blue)!important;color:#fff!important}
.btn:hover,.ss-btn-primary:hover,.auth-btn:hover{transform:none!important;filter:brightness(.97)}
input,select,textarea{border-color:var(--v2-line)!important;border-radius:12px!important;background:#fff!important;color:var(--v2-text)!important}
.warn{background:var(--v2-yellow-bg)!important;border-color:#EFDAA7!important;color:#6F531B!important}
.nav{padding:12px clamp(16px,3vw,34px);background:#fff!important;color:var(--v2-blue-dark)!important;box-shadow:0 2px 14px rgba(31,86,127,.04)!important;border-color:var(--v2-line)!important}
.nav .logo{color:var(--v2-blue-dark)!important}.nav .links{align-items:center;gap:3px}.nav .links a,.v2-services-btn{min-height:42px;display:inline-flex;align-items:center;color:var(--v2-text)!important}
.nav .links a.on{background:var(--v2-sky)!important;color:var(--v2-blue)!important}
.ss-mobile-lang,.dd-btn,.account-dd{background:var(--v2-sky)!important;border-color:var(--v2-line)!important;color:var(--v2-blue-dark)!important}
.dd-menu{background:#fff!important;border-color:var(--v2-line)!important}.dd-menu a{color:var(--v2-text)!important}.dd-menu a:hover{background:var(--v2-sky)!important;color:var(--v2-blue)!important}
.account-avatar,.account-menu-head{background:var(--v2-bg)!important;border-color:var(--v2-line)!important}.account-name,.account-menu-head strong{color:var(--v2-blue-dark)!important}.account-label,.account-menu-head small{color:var(--v2-muted)!important}
.v2-nav-cta{background:var(--v2-blue)!important;color:#fff!important;padding-inline:17px!important}
.v2-services-menu{min-width:260px}.v2-services-menu a{border-radius:8px!important}
.footer{background:#163B5C!important}.f-links{flex-wrap:wrap}
.v2-section-head{display:flex;justify-content:space-between;align-items:end;gap:14px;flex-wrap:wrap;margin:34px 0 16px}
.v2-section-head h2{font-size:clamp(21px,3vw,29px)}
.v2-services-more{border:1px solid var(--v2-line);border-radius:18px;background:#fff;overflow:hidden;margin:20px 0}
.v2-services-more summary{cursor:pointer;padding:16px 19px;color:var(--v2-blue-dark);font-weight:800;list-style:none;display:flex;justify-content:space-between}
.v2-services-more summary:after{content:'＋';color:var(--v2-blue)}.v2-services-more[open] summary:after{content:'−'}
.v2-more-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;padding:0 16px 16px}
.v2-more-link{padding:14px;border:1px solid var(--v2-line);border-radius:13px;color:var(--v2-blue-dark);font-weight:700;background:var(--v2-bg)}
.v2-more-link span{font-size:20px;display:block;margin-bottom:4px}
.v2-info-page{max-width:900px;margin:auto}.v2-info-page>section{background:#fff;border:1px solid var(--v2-line);border-radius:18px;padding:clamp(18px,3vw,28px);margin-bottom:14px;box-shadow:var(--v2-shadow)}
.v2-info-page h1{font-size:clamp(26px,4vw,38px);margin-bottom:10px}.v2-info-page h2{font-size:18px;margin-bottom:8px}.v2-info-page ul{padding-inline-start:22px}
.v2-source-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px}
.v2-source-card{background:#fff;border:1px solid var(--v2-line);border-radius:16px;padding:18px;box-shadow:var(--v2-shadow);display:flex;flex-direction:column;gap:8px}
.v2-source-card .source-type{font-size:11px;background:var(--v2-sky);color:var(--v2-blue-dark);padding:4px 8px;border-radius:999px;align-self:flex-start}
.v2-guest-profile{max-width:620px;margin:30px auto;text-align:center;padding:34px;background:#fff;border:1px solid var(--v2-line);border-radius:20px;box-shadow:var(--v2-shadow)}
.ss-flow{background:#fff;border-bottom:1px solid var(--v2-line);padding:10px 15px}.ss-flow-copy{display:flex;justify-content:space-between;gap:10px;color:var(--v2-muted);font-size:11px;font-weight:700;margin-bottom:6px}.ss-flow-track{height:6px;background:#E8F0F5;border-radius:999px;overflow:hidden}.ss-flow-fill{height:100%;width:14.285%;background:var(--v2-blue);border-radius:999px;transition:width .25s ease}
.asst-source-list{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-top:8px}.asst-source-list>b{width:100%;color:var(--v2-blue-dark);font-size:12px}
@media(max-width:900px){.v2-more-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:700px){.svc-grid[style]{grid-template-columns:1fr!important}}
@media(max-width:600px){.v2-more-grid,.v2-source-grid{grid-template-columns:1fr}.v2-more-grid{padding:0 12px 12px}.container{padding-inline:12px}.v2-section-head{margin-top:24px}}
body.ss-accessibility{font-size:112%;line-height:1.75}body.ss-accessibility .btn,body.ss-accessibility .opt,body.ss-accessibility .ss-btn-primary,body.ss-accessibility button{min-height:52px!important;padding-block:11px!important}body.ss-accessibility .card,body.ss-accessibility .res-card,body.ss-accessibility .hist-card{padding:clamp(20px,3vw,28px)!important}body.ss-accessibility *{scroll-behavior:auto!important}body.ss-accessibility *,body.ss-accessibility *::before,body.ss-accessibility *::after{animation-duration:.001ms!important;animation-iteration-count:1!important;transition-duration:.001ms!important}body.ss-accessibility :focus-visible{outline:3px solid #287FC1!important;outline-offset:3px!important}
/* Unified component layer — calm medical cards, controls, results and footer. */
.card,.auth-card,.res-card,.res-sec,.rec-card,.res-why,.res-action,.res-assess,.res-questions,.res-transparency,.trans-card,.hp-panel,.hp-stat,.hp-quick-link{
  background:var(--v2-card)!important;border:1px solid var(--v2-line)!important;border-radius:var(--v2-radius)!important;box-shadow:var(--v2-shadow)!important}
.res-card{padding:clamp(16px,3vw,24px)!important}.res-sec,.rec-card,.res-why,.res-action,.res-assess,.res-questions,.res-transparency{padding:16px!important;margin-block:10px!important}
.opt,.mini-btn,.dd-btn,.account-dd,.trans-add-btn{border-radius:12px!important;box-shadow:none!important;transition:border-color .18s ease,background .18s ease,color .18s ease!important}
.opt:hover,.mini-btn:hover{transform:none!important;border-color:var(--v2-blue)!important}
.hp-account-hero{background:var(--v2-sky)!important;color:var(--v2-blue-dark)!important;border:1px solid var(--v2-line)!important;box-shadow:var(--v2-shadow)!important}
.hp-account-email{color:var(--v2-muted)!important}.hp-avatar,.hp-secure{background:#fff!important;border-color:var(--v2-line)!important;color:var(--v2-blue-dark)!important}
.footer{background:#fff!important;color:var(--v2-muted)!important;border-top:1px solid var(--v2-line)!important;border-radius:26px 26px 0 0!important;box-shadow:none!important}
.footer .f-brand,.footer .f-sec h4,.footer .f-love{color:var(--v2-blue-dark)!important}.footer .f-tag,.footer .f-sec p,.footer .f-copy{color:var(--v2-muted)!important}.footer a,.footer .f-links a,.footer .f-sec .f-owner{color:var(--v2-blue)!important}.footer .f-tg{background:var(--v2-blue)!important;color:#fff!important}
.v2-symptom-chips{display:flex;gap:7px;flex-wrap:wrap;margin-top:9px}.v2-symptom-chip{display:inline-flex;align-items:center;min-height:34px;padding:6px 10px;border-radius:999px;background:var(--v2-sky);border:1px solid var(--v2-line);color:var(--v2-blue-dark);font-size:12px;font-weight:700}
.v2-low-confidence-card{margin:12px 0;padding:15px;border:1px solid #cfe4f5;border-radius:15px;background:#f7fbff;color:#284764}.v2-low-confidence-card h3{color:#123B70;margin-bottom:7px}.v2-low-confidence-card ul{margin:8px 20px 0;line-height:1.8}
.data-quality-card{margin:12px 0;padding:16px;border:1px solid #CFE3F2;border-radius:17px;background:#F8FCFF;color:#24445F}.dq-head{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:start;gap:12px}.dq-head>div:first-child{min-width:0}.dq-head>div:last-child{min-width:76px;max-width:110px;flex:none}.dq-score{font-size:23px;font-weight:900;color:#123B70;white-space:nowrap;direction:ltr;unicode-bidi:isolate;line-height:1.15}.dq-level{display:inline-flex;align-items:center;justify-content:center;max-width:100%;white-space:normal;word-break:normal;overflow-wrap:normal;font-size:11px;font-weight:800;padding:5px 9px;border-radius:999px;background:#EAF5FC;color:#225C86;line-height:1.35}.dq-track{height:9px;background:#E5EEF5;border-radius:999px;overflow:hidden;margin:11px 0}.dq-fill{height:100%;background:var(--v2-blue);border-radius:inherit;transition:width .28s ease}.dq-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.dq-item{padding:8px 10px;border-radius:11px;background:#fff;border:1px solid #E1ECF3;font-size:12px}.dq-item.missing{background:#FFF9ED;border-color:#F6E3B2}.dq-item.clarify{background:#FFF4EA;border-color:#F5D2AE}.dq-meta{display:flex;gap:10px;flex-wrap:wrap;margin-top:10px;font-size:11px;color:var(--v2-muted)}.xai-card{margin:13px 0;border:1px solid #D4E6F1;border-radius:17px;background:#fff;overflow:hidden}.xai-card summary{cursor:pointer;list-style:none;padding:15px 16px;font-weight:900;color:#123B70;background:#F7FBFE;display:flex;align-items:center;justify-content:space-between;gap:10px}.xai-card summary::-webkit-details-marker{display:none}.xai-body{padding:15px}.xai-basis{display:inline-flex;padding:5px 9px;border-radius:999px;background:#EAF5FC;color:#225C86;font-size:11px;font-weight:800;margin-bottom:10px}.xai-factor{padding:11px 0;border-bottom:1px solid #EDF2F6}.xai-factor:last-child{border-bottom:0}.xai-factor-head{display:flex;justify-content:space-between;gap:10px;align-items:center}.xai-influence{font-size:10px;font-weight:900;border-radius:999px;padding:4px 8px;background:#F1F5F9;color:#475569}.xai-influence.high{background:#EAF5FC;color:#155D8B}.xai-influence.medium{background:#FFF7E6;color:#8A5A00}.xai-influence.low{background:#F1F5F9;color:#526477}.xai-detail{font-size:12px;color:var(--v2-muted);line-height:1.7;margin-top:5px}.xai-meter{display:inline-flex;gap:3px;align-items:center;margin-inline-start:7px}.xai-meter i{display:block;width:18px;height:5px;border-radius:999px;background:#DFE7ED}.xai-meter i.on{background:#6EAED3}.xai-note{margin-top:10px;padding:10px 11px;background:#F8FAFC;border-radius:11px;color:#526477;font-size:11px;line-height:1.7}@media(max-width:600px){.dq-grid{grid-template-columns:1fr}.dq-head{grid-template-columns:minmax(0,1fr) 82px;align-items:start}.dq-score{font-size:22px}.dq-level{font-size:10px;padding:5px 6px}.xai-factor-head{align-items:flex-start;flex-direction:column}}.v2-emergency-card{background:var(--v2-red-bg);border:1px solid #F2CACA;border-inline-start:4px solid var(--v2-red);border-radius:16px;padding:16px;margin:12px 0;color:#713434}.v2-emergency-card h3{color:var(--v2-red);font-size:17px;margin-bottom:7px}.v2-emergency-card strong{display:block;color:#713434;margin-top:10px}.v2-emergency-card p{margin:4px 0;line-height:1.75}
.v2-condition-card{border-inline-start:3px solid var(--v2-blue)!important}.v2-match-badge{margin-inline-start:auto;background:var(--v2-sky);color:var(--v2-blue-dark);padding:4px 10px;border-radius:999px;font-size:11px;font-weight:800}.v2-match-list{display:grid;gap:5px;margin-top:8px}.v2-match-item{color:var(--v2-text);font-size:13px}
.v2-redflag-card{background:var(--v2-red-bg)!important;border-color:#F2CACA!important;border-inline-start:3px solid var(--v2-red)!important}.v2-redflag-card .rec-head b{color:var(--v2-red)!important}.v2-safe-note{background:var(--v2-green-bg);border:1px solid #CDE7D8;border-radius:14px;padding:13px 15px;color:var(--v2-green);font-weight:700;margin:8px 0 14px}.v2-disclaimer{background:var(--v2-bg);border:1px solid var(--v2-line);border-radius:14px;padding:13px 15px;color:var(--v2-muted);font-size:12px;line-height:1.75;margin-top:16px;text-align:center}
.v2-result-section-title{font-size:15px!important;color:var(--v2-blue-dark)!important;margin-top:18px!important;margin-bottom:8px!important}.v2-source-link{display:inline-flex;align-items:center;min-height:38px;margin-top:7px}
@keyframes v2FadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}.res-card,.v2-info-page>section,.card{animation:v2FadeUp .28s ease both}
@media(max-width:600px){.res-card{padding:14px!important}.res-assess-row{align-items:flex-start!important;gap:7px!important;flex-direction:column!important}.rec-head{align-items:flex-start!important;flex-wrap:wrap!important}.v2-match-badge{margin-inline-start:0}.v2-emergency-card{padding:14px}}
@media(prefers-reduced-motion:reduce){*,*:before,*:after{scroll-behavior:auto!important;animation-duration:.01ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important}}
"""

PREMIUM_POLISH_CSS = """
/* Premium product polish: final, non-functional presentation layer. */
:root{
  --ss-space-1:4px;--ss-space-2:8px;--ss-space-3:12px;--ss-space-4:16px;
  --ss-space-5:24px;--ss-space-6:32px;--ss-space-7:48px;--ss-space-8:64px;
  --ss-radius-sm:10px;--ss-radius-md:14px;--ss-radius-lg:20px;--ss-radius-xl:28px;
  --ss-shadow-sm:0 2px 10px rgba(22,59,92,.045);
  --ss-shadow-md:0 10px 30px rgba(22,59,92,.075);
  --ss-focus:0 0 0 4px rgba(40,127,193,.16);
}
body{background:#F7FAFC!important;color:#23384A!important;font-size:15px;line-height:1.75}
.container{width:min(100%,1180px);padding:clamp(20px,3vw,32px) clamp(14px,3vw,28px) clamp(42px,6vw,72px)}
h1,h2,h3,h4{letter-spacing:-.018em}h1{font-size:clamp(30px,4.6vw,48px);line-height:1.22}h2{font-size:clamp(22px,3vw,31px);line-height:1.3}h3{font-size:clamp(16px,2vw,19px);line-height:1.4}
p{max-width:72ch}.muted{color:#607487!important}
.nav{min-height:68px;padding-block:10px!important}.nav .links a{border-radius:10px!important;transition:background-color .2s ease,color .2s ease}.nav .links a:hover{background:#EAF5FC!important;color:#287FC1!important}
.card,.svc-card,.quick-card,.med-card,.hist-card,.history-card,.detail-card,.hp-panel,.hp-stat,.hp-quick-link,.auth-card{border-color:#DCE8F0!important;box-shadow:var(--ss-shadow-sm)!important}
.card,.svc-card,.med-card,.history-card,.detail-card,.auth-card{border-radius:var(--ss-radius-lg)!important}
.svc-card,.quick-card,.hp-quick-link{transition:transform .2s ease,border-color .2s ease,box-shadow .2s ease!important}
.svc-card:hover,.quick-card:hover,.hp-quick-link:hover{transform:translateY(-2px)!important;border-color:#BFD9EA!important;box-shadow:var(--ss-shadow-md)!important}
.btn,.ss-btn-primary,.ss-btn-danger,.auth-btn,.svc-btn,.mini-action,.med-retry{min-height:46px;border-radius:12px!important;padding:11px 19px;font-size:14px;font-weight:800!important;display:inline-flex;align-items:center;justify-content:center;gap:7px;transition:background-color .2s ease,border-color .2s ease,color .2s ease,transform .16s ease!important}
.btn:active,.ss-btn-primary:active,.auth-btn:active{transform:translateY(1px)!important}.btn[disabled],button[disabled]{cursor:not-allowed!important;opacity:.58!important;transform:none!important}
.btn:focus-visible,.auth-btn:focus-visible,.ss-btn-primary:focus-visible,.mini-action:focus-visible{outline:2px solid #287FC1!important;outline-offset:3px!important}
input,select,textarea,input.inp,select.inp,textarea.inp{min-height:48px;padding:11px 13px!important;border:1px solid #CADCE8!important;border-radius:12px!important;transition:border-color .18s ease,box-shadow .18s ease!important}
textarea,textarea.inp{min-height:112px;resize:vertical}input:focus,select:focus,textarea:focus{outline:none!important;border-color:#287FC1!important;box-shadow:var(--ss-focus)!important}
label,.lbl,.auth-field label{color:#29485F!important;font-weight:700!important;margin-bottom:6px!important}
.warn,.warn2,.v2-disclaimer,.privacy-note{border-radius:14px!important;box-shadow:none!important}
.footer{margin-top:clamp(36px,6vw,70px)!important;border-radius:0!important;padding-top:38px!important}
.asst-fab{animation:none!important;background:#287FC1!important;border:0!important;box-shadow:0 10px 26px rgba(40,127,193,.24)!important}.asst-panel{box-shadow:0 24px 70px rgba(22,59,92,.18)!important}.asst-msg{max-width:min(88%,620px);line-height:1.72}.asst-user{background:#287FC1!important}.asst-bot{box-shadow:var(--ss-shadow-sm)}
.chat-wrap{border-radius:22px!important;box-shadow:var(--ss-shadow-md)!important}.bubble{line-height:1.75}.bubble.bot{box-shadow:var(--ss-shadow-sm)}
.med-hero{background:#F8FCFF!important;border-radius:24px!important;box-shadow:none!important}.drug-card{border-radius:18px!important;box-shadow:var(--ss-shadow-sm)}.drug-name{font-size:20px!important}.drug-sec+ .drug-sec{padding-top:12px;border-top:1px solid #E7EFF4}
table th{color:#163B5C;background:#F4F9FC;font-weight:800}table td,table th{padding:12px 14px!important}
.auth-wrap{min-height:min(82vh,760px)}.auth-card{max-width:470px!important;padding:clamp(26px,4vw,38px)!important}.auth-card .auth-icon{font-size:38px!important}.auth-card .auth-sub{line-height:1.75}
.history-card h3{font-weight:800}.risk-pill{border:1px solid currentColor}
.hh{min-height:520px;padding:clamp(34px,5vw,58px)!important;gap:clamp(28px,5vw,62px)!important;background:#FFFFFF!important;border-radius:var(--ss-radius-xl)!important;box-shadow:var(--ss-shadow-md)!important}
.hh-l{flex:1.08}.hh-l h1{max-width:13ch;font-size:clamp(36px,5.2vw,58px)!important;line-height:1.24!important;margin-bottom:14px!important}.hh-sub{font-size:clamp(16px,2vw,20px)!important;margin-bottom:10px!important}.hh-desc{font-size:15px!important;line-height:1.9!important;margin-bottom:26px!important}.hh-badge{padding:0!important;background:transparent!important;border-radius:0!important;color:#287FC1!important;font-size:13px!important;letter-spacing:.03em;margin-bottom:14px!important}.hh-btns{gap:10px!important}.hh-btns .btn{margin:0!important}
.hh-r{min-height:340px!important}.hh-product-art{display:block;width:min(440px,100%);height:auto;object-fit:contain;filter:saturate(.88)}
.hh-product-visual{position:relative;width:min(440px,100%);aspect-ratio:1;border-radius:32px;border:1px solid #cfe3ef;background:#f4fafe;display:grid;place-items:center;overflow:hidden;box-shadow:0 16px 36px rgba(31,86,127,.10)}.hh-product-visual:before,.hh-product-visual:after{content:'';position:absolute;border:1px solid #c7e0ed;border-radius:50%}.hh-product-visual:before{width:76%;height:76%}.hh-product-visual:after{width:49%;height:49%;background:#fff;box-shadow:0 12px 30px rgba(31,86,127,.08)}.hh-product-core{position:relative;z-index:2;width:96px;height:96px;border-radius:28px;background:#287fc1;color:#fff;display:grid;place-items:center;font-size:42px;font-weight:900;box-shadow:0 13px 28px rgba(40,127,193,.22)}.hh-product-node{position:absolute;z-index:3;width:66px;height:66px;border-radius:20px;background:#fff;border:1px solid #d6e7f0;display:grid;place-items:center;font-size:28px;box-shadow:0 8px 20px rgba(31,86,127,.08)}.hh-p1{top:10%;left:11%}.hh-p2{top:11%;right:10%}.hh-p3{bottom:10%;left:12%}.hh-p4{bottom:10%;right:11%}
.home-trust{display:grid;justify-items:center;gap:4px;margin:-10px auto 36px;color:#607487;font-size:13px;text-align:center}.home-trust a{color:#287FC1;font-weight:800;text-decoration:none}.home-trust a:hover{text-decoration:underline}
.v2-section-head{margin-top:42px!important}.svc-grid{gap:14px!important}.svc-card{padding:22px!important}.svc-ic{width:48px!important;height:48px!important;border-radius:14px!important;font-size:24px!important}.svc-btn{background:transparent!important;color:#287FC1!important;padding:5px 0!important;min-height:auto!important}.svc-card:hover .svc-btn{background:transparent!important;color:#163B5C!important}
@media(max-width:1180px){.nav{display:none}.ss-mobile-head{display:flex}.ss-bnav{display:flex;justify-content:space-evenly;align-items:center}.ss-bnav a{flex:0 1 170px}.container{padding-bottom:calc(var(--bnav-h) + var(--safe-bottom) + 80px)}.asst-fab{bottom:calc(var(--bnav-h) + var(--safe-bottom) + 12px);left:12px;width:54px;height:54px;padding:0;justify-content:center}.asst-fab .asst-fab-lb{display:none}.asst-panel{left:12px;right:12px;bottom:calc(var(--bnav-h) + var(--safe-bottom) + 76px);width:auto;height:min(72dvh,600px)}[dir="rtl"] .asst-panel{left:12px;right:12px}}
@media(min-width:1181px){.nav{display:flex!important}.ss-mobile-head,.ss-bnav{display:none!important}.container{padding-bottom:clamp(42px,6vw,72px)!important}.asst-fab{bottom:22px!important}}
@media(max-width:900px){.hh{min-height:0;flex-direction:column;padding:30px 24px!important}.hh-l{width:100%}.hh-l h1{max-width:16ch}.hh-r{min-height:230px!important;width:100%}.hh-product-art{width:min(360px,88%)}.home-trust{margin-top:-12px}.svc-grid[style]{grid-template-columns:1fr!important}}
@media(max-width:600px){body{font-size:14px}.container{padding-inline:12px!important}.hh{padding:25px 19px!important;border-radius:22px!important}.hh-l h1{font-size:clamp(32px,10vw,42px)!important}.hh-r{min-height:190px!important}.hh-btns{display:grid!important;grid-template-columns:1fr}.hh-btns .btn{width:100%}.home-trust{text-align:center;margin-bottom:26px}.v2-section-head{margin-top:28px!important}.svc-card{padding:19px!important}.auth-card{padding:26px 18px!important}.footer{padding-inline:16px!important}.asst-msg{max-width:94%}}
@media(max-width:360px){.container{padding-inline:10px!important}.hh{padding:22px 16px!important}.hh-l h1{font-size:31px!important}.hh-r{min-height:168px!important}.btn,.ss-btn-primary,.auth-btn{width:100%}}


/* Symptom result report — UI/UX only. The API response remains the medical source of truth. */
body.ss-chat-page .chat-body.result-mode{padding:14px!important;background:#F7FAFC!important;overflow-y:auto!important;scroll-behavior:auto!important}
body.ss-chat-page .chat-wrap.report-mode .chat-options{display:none!important}
.ss-report{width:min(780px,100%);margin:0 auto;padding:0 0 8px;animation:none!important;color:var(--v2-text)}
.ss-report *{animation:none!important;min-width:0}
.ss-report-card,.ss-report-details{background:#fff;border:1px solid #DCE8F0;border-radius:17px;padding:17px;margin:0 0 12px;box-shadow:0 4px 14px rgba(31,86,127,.045)}
.ss-report-summary{border-top:4px solid #287FC1;padding-top:15px}
.ss-report-heading{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:13px}
.ss-report-heading h2,.ss-report-heading h3{font-size:17px;line-height:1.45;margin:0;color:#163B5C}
.ss-report-heading .ss-count{font-size:11px;font-weight:800;color:#526B7E;background:#F1F7FA;border:1px solid #DCE8F0;padding:5px 9px;border-radius:999px}
.ss-risk-row{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:13px 14px;border-radius:14px;margin-bottom:11px}
.ss-risk-row.low{background:#EDF8F2;border:1px solid #CFE9DA;color:#1E6846}.ss-risk-row.med{background:#FFF8E7;border:1px solid #F0DEAF;color:#7B5A18}.ss-risk-row.hi{background:#FFF1F1;border:1px solid #F1CCCC;color:#8E3333}
.ss-risk-label{font-size:12px;font-weight:800;opacity:.86}.ss-risk-value{font-size:20px;font-weight:900;line-height:1.35}
.ss-quality{padding:12px 14px;border-radius:14px;background:#F8FCFF;border:1px solid #D7E8F2;margin-bottom:11px}
.ss-quality-top{display:flex;align-items:center;justify-content:space-between;gap:10px;font-size:13px}.ss-quality-top strong{color:#163B5C}.ss-quality-score{font-weight:900;color:#287FC1;white-space:nowrap}
.ss-quality-track{height:7px;background:#E4EEF4;border-radius:999px;overflow:hidden;margin-top:8px}.ss-quality-fill{height:100%;background:#287FC1;border-radius:inherit}
.ss-summary-recommendation{padding:12px 14px;border-radius:14px;background:#F7FAFC;border:1px solid #E1EBF1;font-size:13px;line-height:1.75}.ss-summary-recommendation b{display:block;color:#163B5C;margin-bottom:3px}
.ss-input-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.ss-input-item{padding:11px 12px;border:1px solid #E1EBF1;border-radius:13px;background:#FBFDFE}.ss-input-label{display:block;color:#607487;font-size:11px;font-weight:800;margin-bottom:3px}.ss-input-value{display:block;color:#23384A;font-size:13px;font-weight:700;line-height:1.65;overflow-wrap:anywhere}
.ss-condition-list{display:grid;grid-template-columns:1fr;gap:9px}.ss-condition{padding:14px;border:1px solid #DDE9F0;border-radius:14px;background:#FBFDFE}.ss-condition-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}.ss-condition-name{font-size:15px;font-weight:900;color:#163B5C}.ss-match{display:inline-flex;align-items:center;justify-content:center;font-size:10.5px;font-weight:900;padding:5px 8px;border-radius:999px;background:#EAF5FC;color:#225C86;white-space:nowrap}.ss-condition-why{margin-top:8px;font-size:12px;line-height:1.75;color:#526B7E}.ss-condition-why b{color:#29485F}
.ss-step-list{display:grid;gap:9px}.ss-step{display:grid;grid-template-columns:34px minmax(0,1fr);gap:10px;padding:12px;border:1px solid #E1EBF1;border-radius:14px;background:#FBFDFE}.ss-step-no{width:32px;height:32px;border-radius:10px;display:grid;place-items:center;background:#EAF5FC;color:#1D6D9F;font-weight:900;font-size:12px}.ss-step-body b{display:block;color:#163B5C;font-size:13px;margin-bottom:4px}.ss-step-body p{margin:0;color:#40566F;font-size:12.5px;line-height:1.75}.ss-step-source{display:inline-flex;margin-top:7px;color:#287FC1;font-size:11.5px;font-weight:800}
.ss-flag-list,.ss-care-list{display:grid;gap:7px}.ss-flag,.ss-care{display:flex;align-items:flex-start;gap:8px;padding:10px 11px;border-radius:12px;line-height:1.7;font-size:12.5px}.ss-flag{background:#FFF7F7;border:1px solid #F2DADA;color:#713E3E}.ss-care{background:#F7FBF9;border:1px solid #D8E9DF;color:#315C48}.ss-empty-note{padding:11px 12px;border-radius:12px;background:#F7FAFC;border:1px solid #E1EBF1;color:#607487;font-size:12.5px}
.ss-question-chips{display:flex;flex-wrap:wrap;gap:7px}.ss-question-chip{border:1px solid #CFE1EC;background:#F8FCFF;color:#225C86;border-radius:999px;padding:8px 12px;min-height:40px;font-family:inherit;font-size:12px;font-weight:800;cursor:pointer}.ss-question-chip:hover{background:#EAF5FC}.ss-question-answer{margin-top:10px;padding:12px;border:1px solid #DCE8F0;border-radius:13px;background:#F7FAFC;font-size:12.5px;line-height:1.8;white-space:pre-wrap}.ss-question-answer[hidden]{display:none}
.ss-report-details{padding:0;overflow:hidden}.ss-report-details summary{cursor:pointer;list-style:none;padding:15px 17px;display:flex;align-items:center;justify-content:space-between;gap:10px;color:#163B5C;font-weight:900;font-size:14px;background:#fff}.ss-report-details summary::-webkit-details-marker{display:none}.ss-report-details summary::after{content:'＋';color:#287FC1;font-size:18px;line-height:1}.ss-report-details[open] summary::after{content:'−'}.ss-details-body{padding:0 17px 16px;border-top:1px solid #EDF2F5}.ss-details-block{padding-top:12px;font-size:12.5px;line-height:1.8;color:#526B7E}.ss-details-block b{color:#29485F}.ss-factor{padding:9px 0;border-bottom:1px solid #EDF2F5}.ss-factor:last-child{border-bottom:0}.ss-factor strong{color:#29485F}.ss-factor small{display:block;color:#607487;line-height:1.7;margin-top:3px}
.ss-source-list{display:grid;gap:9px;padding-top:12px}.ss-source-card{padding:12px;border:1px solid #E1EBF1;border-radius:13px;background:#FBFDFE}.ss-source-name{font-weight:900;color:#163B5C;font-size:13px}.ss-source-meta{display:flex;gap:6px 10px;flex-wrap:wrap;margin-top:5px;color:#607487;font-size:10.5px}.ss-source-title{margin-top:6px;color:#40566F;font-size:12px;line-height:1.65}.ss-source-link{display:inline-flex;align-items:center;justify-content:center;min-height:38px;margin-top:8px;padding:7px 11px;border-radius:10px;background:#EAF5FC;color:#1F6E9F;font-size:11.5px;font-weight:900}
.ss-report-actions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.ss-report-action{min-height:46px;border-radius:12px;border:1px solid #CFE1EC;background:#fff;color:#225C86;font-family:inherit;font-weight:850;font-size:12.5px;display:flex;align-items:center;justify-content:center;gap:6px;padding:9px 11px;cursor:pointer;text-decoration:none}.ss-report-action.primary{background:#287FC1;color:#fff;border-color:#287FC1}.ss-report-action:hover{filter:brightness(.98)}
.ss-feedback{text-align:center}.ss-feedback p{margin:0 0 10px;font-weight:800;color:#29485F}.ss-feedback-btns{display:flex;justify-content:center;gap:8px}.ss-feedback-btn{min-width:96px;min-height:42px;border-radius:12px;border:1px solid #D5E4ED;background:#fff;color:#29485F;font-family:inherit;font-weight:800;cursor:pointer}.ss-feedback-msg{margin-top:8px;color:#287FC1;font-size:12px;font-weight:800}
.ss-report-disclaimer{padding:12px 14px;border-radius:14px;background:#F7FAFC;border:1px solid #DCE8F0;color:#607487;font-size:11.5px;line-height:1.75;text-align:center}
@media(min-width:760px){.ss-condition-list{grid-template-columns:repeat(2,minmax(0,1fr))}.ss-condition-list .ss-condition:only-child{grid-column:1/-1}}
@media(max-width:640px){body.ss-chat-page .chat-body.result-mode{padding:9px!important}.ss-report-card{padding:14px;border-radius:15px;margin-bottom:9px}.ss-report-heading{margin-bottom:10px}.ss-report-heading h2,.ss-report-heading h3{font-size:15px}.ss-risk-row{padding:11px 12px}.ss-risk-value{font-size:18px}.ss-input-grid{grid-template-columns:1fr}.ss-condition-head{flex-direction:column;gap:7px}.ss-match{align-self:flex-start}.ss-step{grid-template-columns:30px minmax(0,1fr);padding:10px}.ss-step-no{width:29px;height:29px}.ss-question-chips{display:grid;grid-template-columns:1fr}.ss-question-chip{width:100%;border-radius:12px;text-align:start}.ss-report-actions{grid-template-columns:1fr}.ss-report-action{width:100%;min-height:48px}.ss-report-details summary{padding:13px 14px}.ss-details-body{padding:0 14px 14px}.ss-feedback-btn{flex:1;max-width:150px}.ss-report-disclaimer{font-size:11px}}

/* Symptom analysis — mobile-first layout refinement. */
.adaptive-step{display:inline-flex;align-items:center;max-width:100%;padding:4px 9px;border-radius:999px;background:#EAF5FC;color:#225C86;font-size:11px;font-weight:800;line-height:1.4;white-space:normal}
body.ss-chat-page .chat-wrap{isolation:isolate}
body.ss-chat-page .chat-head{flex:0 0 auto}
body.ss-chat-page .ss-flow{flex:0 0 auto}
body.ss-chat-page .chat-body{min-height:0}
body.ss-chat-page .chat-options{flex:0 0 auto}
body.ss-chat-page .chat-input{flex:0 0 auto}
body.ss-chat-page .likely-condition{border-inline-start:4px solid #287FC1!important;background:#F8FCFF!important}
body.ss-chat-page .smart-next{background:#FBFDFE!important}

@media(max-width:640px){
  body.ss-chat-page{height:100dvh;overflow:hidden;background:#F7FAFC!important}
  body.ss-chat-page .ss-mobile-head{display:none!important}
  body.ss-chat-page .footer{display:none!important}
  body.ss-chat-page .container{height:calc(100dvh - var(--bnav-h) - var(--safe-bottom));padding:8px 8px 6px!important;overflow:hidden}
  body.ss-chat-page .chat-wrap{height:100%!important;min-height:0!important;max-height:none!important;margin:0!important;border-radius:18px!important;border:1px solid #DCE8F0!important;box-shadow:0 8px 24px rgba(22,59,92,.08)!important}
  body.ss-chat-page .chat-head{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:8px 10px;padding:10px 11px!important;background:#287FC1!important}
  body.ss-chat-page .chat-head .avatar{grid-column:1;grid-row:1;width:36px;height:36px;font-size:18px}
  body.ss-chat-page .chat-head>div:nth-child(2){grid-column:2;grid-row:1;min-width:0}
  body.ss-chat-page .chat-head h3{font-size:15px!important;line-height:1.25;margin:0}
  body.ss-chat-page .chat-head p{font-size:10.5px!important;line-height:1.35;margin:2px 0 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  body.ss-chat-page .chat-head-toggles{grid-column:3;grid-row:1;display:flex!important;align-items:center;justify-content:flex-end;gap:6px;margin:0!important}
  body.ss-chat-page .chat-head .spk-btn{width:38px;height:38px;min-width:38px;padding:0!important;display:grid;place-items:center;border:1px solid rgba(255,255,255,.22)!important;border-radius:11px!important;font-size:0!important;background:rgba(255,255,255,.14)!important}
  body.ss-chat-page #voiceModeBtn::before{content:'🎙️';font-size:17px;line-height:1}
  body.ss-chat-page #spkBtn::before{content:'🔊';font-size:17px;line-height:1}
  body.ss-chat-page #profileSwitcher{grid-column:1/-1;grid-row:2;width:100%;margin:0!important;display:block!important}
  body.ss-chat-page #famSelect{width:100%!important;max-width:none!important;min-height:38px!important;height:38px;padding:5px 10px!important;border-radius:10px!important;font-size:12px!important;background:rgba(255,255,255,.14)!important;color:#fff!important;border-color:rgba(255,255,255,.28)!important;box-shadow:none!important}
  body.ss-chat-page #famSelect option{color:#1F3345;background:#fff}
  body.ss-chat-page .ss-flow{padding:8px 11px!important;background:#fff!important}
  body.ss-chat-page .ss-flow-copy{font-size:10.5px!important;margin-bottom:5px!important;gap:8px}
  body.ss-chat-page .ss-flow-copy span:last-child{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:end}
  body.ss-chat-page .ss-flow-track{height:5px!important}
  body.ss-chat-page .chat-body{padding:10px 10px 6px!important;background:#F7FAFC!important;scroll-padding-block:12px;overscroll-behavior:contain;-webkit-overflow-scrolling:touch}
  body.ss-chat-page .bubble{max-width:92%!important;margin-bottom:8px!important;padding:10px 12px!important;border-radius:13px!important;font-size:13.5px!important;line-height:1.65!important;overflow-wrap:anywhere;word-break:normal}
  body.ss-chat-page .bubble.q{max-width:100%!important;font-size:14px!important;font-weight:750!important;background:#F4F9FC!important;box-shadow:none!important}
  body.ss-chat-page .bubble.q.start{padding:12px!important}
  body.ss-chat-page .bubble.user{max-width:88%!important}
  body.ss-chat-page .bubble.result{max-width:100%!important;padding:0!important;border:0!important;background:transparent!important;box-shadow:none!important}
  body.ss-chat-page .chat-start{padding:3px 2px 1px!important}
  body.ss-chat-page .chat-start .cs-logo{font-size:34px!important;margin-bottom:3px!important}
  body.ss-chat-page .chat-start .cs-title{font-size:17px!important;margin-bottom:2px!important}
  body.ss-chat-page .chat-start .cs-sub{font-size:13px!important;margin-bottom:5px!important}
  body.ss-chat-page .chat-start .cs-desc{font-size:12px!important;line-height:1.65!important}
  body.ss-chat-page .cs-voice{display:inline-flex!important;align-items:center;justify-content:center;min-height:38px;margin-top:9px!important;padding:7px 12px!important;font-size:12px!important}
  body.ss-chat-page .chat-options{display:grid!important;grid-template-columns:1fr!important;gap:7px!important;max-height:min(36dvh,310px)!important;padding:9px!important;background:#fff!important;border-top:1px solid #E3EDF3!important;overflow-y:auto!important;overscroll-behavior:contain;-webkit-overflow-scrolling:touch}
  body.ss-chat-page .chat-options.symptom-picker{grid-template-columns:repeat(2,minmax(0,1fr))!important;max-height:min(42dvh,360px)!important}
  body.ss-chat-page .chat-options .opt{width:100%!important;min-height:46px!important;padding:9px 11px!important;border-radius:12px!important;font-size:13px!important;line-height:1.4!important;text-align:center!important;white-space:normal!important;overflow-wrap:anywhere}
  body.ss-chat-page .chat-options.symptom-picker .opt{min-height:50px!important;padding:8px 7px!important;font-size:12.5px!important}
  body.ss-chat-page .chat-options .start-btn{grid-column:1/-1!important;position:sticky!important;top:0!important;z-index:4!important;min-height:48px!important;margin:0 0 2px!important;border-radius:13px!important;padding:11px 14px!important;font-size:14px!important;box-shadow:0 5px 16px rgba(40,127,193,.16)!important}
  body.ss-chat-page .chat-options #relBlock{grid-column:1/-1!important}
  body.ss-chat-page .rel-title{margin-top:7px!important;font-size:11.5px!important}
  body.ss-chat-page .rel-chips{gap:6px!important;margin-top:6px!important}
  body.ss-chat-page .rel-chip{min-height:38px;padding:7px 10px!important;border-radius:11px!important;font-size:11.5px!important;line-height:1.35!important}
  body.ss-chat-page .chat-input{padding:8px!important;gap:6px!important;background:#fff!important;border-top:1px solid #E3EDF3!important;padding-bottom:max(8px,env(safe-area-inset-bottom))!important}
  body.ss-chat-page .chat-input input{min-width:0!important;min-height:46px!important;height:46px;padding:10px 11px!important;font-size:16px!important;border-radius:12px!important}
  body.ss-chat-page .chat-input button{min-width:46px!important;min-height:46px!important;height:46px;padding:0 11px!important;border-radius:12px!important;font-size:13px!important}
  body.ss-chat-page #micBtn{width:46px!important;padding:0!important;font-size:18px!important}
  body.ss-chat-page .res-card{padding:13px!important;border-radius:16px!important;box-shadow:none!important}
  body.ss-chat-page .res-title{font-size:17px!important;margin-bottom:9px!important}
  body.ss-chat-page .pill2{font-size:15px!important;padding:8px 16px!important;max-width:100%}
  body.ss-chat-page .urg-lbl{font-size:11.5px!important}
  body.ss-chat-page .urg-val{font-size:18px!important}
  body.ss-chat-page .res-assess{padding:12px!important;margin:8px 0!important;border-radius:13px!important}
  body.ss-chat-page .res-assess-h{font-size:14px!important;margin-bottom:6px!important}
  body.ss-chat-page .likely-condition div[style*='1.28rem']{font-size:1.12rem!important;line-height:1.45!important}
  body.ss-chat-page .warn{font-size:12px!important;line-height:1.65!important;padding:10px 11px!important}
  body.ss-chat-page .xai-card summary{padding:11px 12px!important;font-size:12.5px!important}
  body.ss-chat-page .xai-body{padding:12px!important}
}
@media(max-width:390px){
  body.ss-chat-page .chat-head{grid-template-columns:minmax(0,1fr) auto}
  body.ss-chat-page .chat-head .avatar{display:none!important}
  body.ss-chat-page .chat-head>div:nth-child(2){grid-column:1;grid-row:1}
  body.ss-chat-page .chat-head-toggles{grid-column:2;grid-row:1}
  body.ss-chat-page #profileSwitcher{grid-column:1/-1}
  body.ss-chat-page .chat-options.symptom-picker{grid-template-columns:1fr!important}
  body.ss-chat-page .chat-options.symptom-picker .opt{min-height:44px!important;font-size:13px!important}
  body.ss-chat-page .bubble{max-width:96%!important}
  body.ss-chat-page .bubble.user{max-width:92%!important}
}
@media(prefers-reduced-motion:reduce){.svc-card,.quick-card,.hp-quick-link,.btn,.auth-btn,input,select,textarea{transition:none!important}.svc-card:hover,.quick-card:hover,.hp-quick-link:hover{transform:none!important}}
"""

BASE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap');
* { box-sizing: border-box; margin: 0; padding: 0; min-width: 0; }
html, body { width: 100%; max-width: 100%; overflow-x: hidden; }
body { font-family: 'Cairo', 'Segoe UI', Tahoma, sans-serif; background: #F5F9FF; color: #40566F; -webkit-text-size-adjust: 100%; }
a { text-decoration: none; color: inherit; }
img, svg, video, iframe, canvas { max-width: 100%; height: auto; }
table { max-width: 100%; }
h1, h2, h3, h4, p, span, a, button, label { overflow-wrap: break-word; word-break: break-word; }
button, input, select, textarea { max-width: 100%; font-family: inherit; }
html { scroll-behavior: smooth; }
body { min-height: 100vh; min-height: 100dvh; line-height: 1.65; text-rendering: optimizeLegibility; }
button, .btn, .opt, .fam-chip, .mini-btn, .ss-bnav a { touch-action: manipulation; -webkit-tap-highlight-color: transparent; }
button:focus-visible, a:focus-visible, input:focus-visible, select:focus-visible, textarea:focus-visible, [tabindex]:focus-visible { outline: 3px solid rgba(25,118,210,.35); outline-offset: 3px; }
.nav { background: #FFFFFF; color: #123B70; display: flex; align-items: center; justify-content: space-between; padding: 15px 26px; position: sticky; top: 0; z-index: 50; box-shadow: 0 2px 14px rgba(25,118,210,.05); flex-wrap: wrap; gap: 10px; border-bottom: 1px solid #DCEBFA; }
.nav .logo { font-size: 22px; font-weight: 800; letter-spacing: .3px; color: #123B70; display: flex; align-items: center; gap: 6px; white-space: nowrap; }
.nav .logo span { color: #1976D2; }
.nav .links { display: flex; gap: 2px; flex-wrap: wrap; }
.nav .links a { color: #40566F; padding: 8px 14px; border-radius: 999px; font-size: 15px; font-weight: 600; }
.nav .links a:hover { color: #1976D2; background: #EAF4FF; }
:root { --bnav-h: 64px; --safe-bottom: env(safe-area-inset-bottom, 0px); --safe-top: env(safe-area-inset-top, 0px); --primary: #1976D2; --primary-hover: #1565C0; --primary-mid: #64B5F6; --primary-pale: #B8D8F8; --primary-light: #EAF4FF; --primary-dark: #123B70; --text-main: #123B70; --text-body: #40566F; --text-muted: #5F7185; --bg-page: #F5F9FF; --bg-card: #FFFFFF; --border-card: #DCEBFA; --shadow-card: 0 4px 18px rgba(25,118,210,.07); }
.nav .links a.on { background: #EAF4FF; color: #1976D2; font-weight: 700; }
.container { width: 100%; max-width: 1080px; margin: 0 auto; padding: clamp(20px, 3vw, 30px) clamp(16px, 3vw, 24px) 38px; }
/* Compact header used on tablets, phones and narrow laptops so links never crowd. */
.ss-mobile-head { display: none; position: sticky; top: 0; z-index: 70; min-height: 62px; align-items: center; justify-content: space-between; gap: 12px; padding: calc(10px + var(--safe-top)) clamp(12px, 3vw, 24px) 10px; background: rgba(255,255,255,.97); backdrop-filter: blur(14px); border-bottom: 1px solid var(--border-card); box-shadow: 0 4px 18px rgba(25,118,210,.07); }
.ss-mobile-logo { display: inline-flex; align-items: center; gap: 7px; color: var(--primary-dark); font-size: clamp(17px, 3.4vw, 21px); font-weight: 900; white-space: nowrap; }
.ss-mobile-logo span { color: var(--primary); }
.ss-mobile-actions { display: flex; align-items: center; justify-content: flex-end; gap: 8px; min-width: 0; }
.ss-mobile-lang, .ss-mobile-account { min-height: 42px; border-radius: 12px; display: inline-flex; align-items: center; justify-content: center; gap: 5px; font-weight: 800; font-family: inherit; }
.ss-mobile-lang { min-width: 46px; padding: 7px 10px; border: 1px solid var(--border-card); background: var(--primary-light); color: var(--primary-dark); cursor: pointer; }
.ss-mobile-account { max-width: 150px; padding: 7px 11px; border: 1px solid var(--primary-pale); background: var(--primary); color: #fff; }
.ss-mobile-account span:last-child { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ss-profile-card { background: var(--bg-card); border: 1px solid var(--border-card); border-radius: 18px; padding: 20px; margin-bottom: 16px; box-shadow: var(--shadow-card); }
.ss-profile-card h2 { font-size: 17px; font-weight: 800; color: var(--primary); margin-bottom: 14px; display: flex; align-items: center; gap: 8px; }
.ss-field { display: flex; align-items: flex-start; gap: 12px; padding: 12px 0; border-bottom: 1px solid var(--border-card); }
.ss-field:last-child { border-bottom: none; }
.ss-f-icon { font-size: 18px; flex: 0 0 auto; margin-top: 2px; }
.ss-field label { display: block; font-size: 12px; font-weight: 700; color: var(--text-muted); margin-bottom: 2px; text-transform: uppercase; letter-spacing: .3px; }
.ss-grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
@media (max-width: 500px) { .ss-grid2 { grid-template-columns: 1fr; } }
.ss-btn-primary { background: var(--primary); color: #fff; border: none; border-radius: 14px; padding: 13px 24px; font-size: 15px; font-weight: 700; cursor: pointer; font-family: inherit; display: inline-flex; align-items: center; gap: 8px; min-height: 48px; box-shadow: 0 8px 20px rgba(25,118,210,.18); transition: transform .15s, box-shadow .15s; }
.ss-btn-primary:hover { background: #1565C0; transform: scale(0.98); }
.ss-btn-danger { background: #FFF0F0; color: #991B1B; border: 1px solid #FECACA; border-radius: 14px; padding: 12px 20px; font-size: 14px; font-weight: 700; cursor: pointer; font-family: inherit; min-height: 48px; }
.ss-btn-row { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 16px; }
.ss-msg { padding: 12px 16px; border-radius: 14px; font-size: 14px; font-weight: 600; margin-top: 10px; }
.ss-msg.success { background: #EAF8F0; color: #166534; border: 1px solid #BBF7D0; }
.ss-msg.error { background: #FFF0F0; color: #991B1B; border: 1px solid #FECACA; }
.hp-account-hero { background: linear-gradient(135deg, #123B70, #1976D2); color: #fff; border-radius: 22px; padding: 24px; margin-bottom: 16px; box-shadow: 0 16px 36px rgba(25,118,210,.22); }
.hp-account-head { display: flex; align-items: center; gap: 15px; }
.hp-avatar { width: 64px; height: 64px; flex: 0 0 64px; border-radius: 20px; background: rgba(255,255,255,.18); display: flex; align-items: center; justify-content: center; font-size: 32px; border: 1px solid rgba(255,255,255,.28); }
.hp-account-name { font-size: 22px; font-weight: 800; line-height: 1.35; }
.hp-account-email { font-size: 13px; opacity: .9; direction: ltr; text-align: start; }
.hp-secure { margin-inline-start: auto; align-self: flex-start; background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.25); border-radius: 999px; padding: 6px 11px; font-size: 12px; font-weight: 700; white-space: nowrap; }
.hp-stats { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 10px; margin: 16px 0; }
.hp-stat { background: var(--bg-card); border: 1px solid var(--border-card); border-radius: 16px; padding: 15px 10px; text-align: center; box-shadow: var(--shadow-card); }
.hp-stat-icon { display: block; font-size: 22px; margin-bottom: 3px; }
.hp-stat-value { display: block; font-size: 22px; line-height: 1.2; color: var(--primary-dark); font-weight: 900; }
.hp-stat-label { display: block; color: var(--text-muted); font-size: 11px; font-weight: 700; margin-top: 4px; }
.hp-overview { display: grid; grid-template-columns: 1.15fr .85fr; gap: 14px; margin-bottom: 16px; }
.hp-panel { background: var(--bg-card); border: 1px solid var(--border-card); border-radius: 18px; padding: 18px; box-shadow: var(--shadow-card); }
.hp-panel h3 { color: var(--primary-dark); font-size: 16px; margin-bottom: 11px; display: flex; align-items: center; gap: 7px; }
.hp-chips { display: flex; flex-wrap: wrap; gap: 7px; }
.hp-chip { background: var(--primary-light); color: var(--primary-dark); border: 1px solid var(--border-card); border-radius: 999px; padding: 6px 11px; font-size: 13px; font-weight: 700; }
.hp-meta { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 12px; color: var(--text-muted); font-size: 12px; }
.hp-meta span { background: var(--bg-page); border-radius: 999px; padding: 4px 8px; border: 1px solid var(--border-card); }
.hp-essential { padding: 9px 0; border-bottom: 1px solid var(--border-card); }
.hp-essential:last-child { border-bottom: 0; }
.hp-essential b { color: var(--primary-dark); font-size: 12px; display: block; margin-bottom: 2px; }
.hp-essential span { color: var(--text-body); font-size: 13px; }
.hp-quick-links { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 9px; margin-bottom: 16px; }
.hp-quick-link { min-height: 82px; padding: 12px 8px; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; gap: 5px; background: var(--bg-card); border: 1px solid var(--border-card); border-radius: 15px; color: var(--primary-dark); font-size: 12px; font-weight: 800; box-shadow: var(--shadow-card); }
.hp-quick-link span { font-size: 23px; }
.hp-quick-link:hover { border-color: var(--primary); transform: translateY(-2px); }
/* Mobile Bottom Navigation */
.ss-bnav { display: none; position: fixed; bottom: 0; left: 0; right: 0; z-index: 90; background: rgba(255,255,255,0.96); backdrop-filter: blur(12px); border-top: 1px solid #DCEBFA; box-shadow: 0 -4px 18px rgba(25,118,210,.08); padding: 6px 0 var(--safe-bottom); padding-bottom: calc(6px + var(--safe-bottom)); }
.ss-bnav a { display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 8px 4px; text-decoration: none; color: #5F7185; font-size: 10px; font-weight: 700; min-width: 56px; min-height: 48px; justify-content: center; transition: color .2s; border-radius: 12px; }
.ss-bnav a.on { color: #0F5FB0; background: var(--primary-light); }
.ss-bnav a .bn-icon { font-size: 22px; line-height: 1; }
/* Completion bar */
.ss-completion { background: var(--bg-card); border: 1px solid var(--border-card); border-radius: 18px; padding: 18px 20px; margin-bottom: 16px; box-shadow: var(--shadow-card); }
.ss-completion .bar-track { background: var(--border-card); border-radius: 999px; height: 8px; margin: 10px 0 6px; overflow: hidden; }
.ss-completion .bar-fill-green { background: linear-gradient(90deg, var(--primary-dark), var(--primary-mid)); height: 100%; border-radius: 999px; transition: width .6s ease; }
.ss-completion .bar-label { font-size: 13px; color: var(--text-muted); font-weight: 600; }
/* Smart next step card */
.ss-next-step { background: linear-gradient(135deg, var(--primary-light), var(--bg-page)); border: 1.5px solid var(--border-card); border-radius: 18px; padding: 18px 20px; margin-bottom: 16px; }
.ss-next-step h3 { font-size: 16px; font-weight: 800; color: var(--primary-dark); margin-bottom: 6px; }
.ss-next-step p { font-size: 14px; color: var(--text-body); line-height: 1.7; margin-bottom: 12px; }
.manage-card { background:var(--bg-card); border-radius:16px; padding:18px; margin-bottom:12px; border:1px solid var(--border-card); box-shadow: var(--shadow-card); }
.manage-card-head { display:flex; align-items:center; gap:10px; margin-bottom:8px; }
.manage-icon { font-size:22px; }
.manage-label { font-weight:700; color:var(--primary-dark); font-size:15px; }
.manage-val { font-size:15px; color:var(--text-body); padding:8px 12px; background:var(--primary-light); border-radius:10px; margin-bottom:10px; min-height:20px; }
.manage-actions { display:flex; gap:8px; }
.manage-edit-btn { flex:1; padding:10px; border:2px solid var(--border-card); border-radius:10px; background:var(--bg-card); font-weight:600; cursor:pointer; font-size:14px; text-align:center; }
.manage-edit-btn:hover { border-color:var(--primary); color:var(--primary); }
.manage-del-btn { flex:1; padding:10px; border:2px solid #FECACA; border-radius:10px; background:var(--bg-card); color:#DC2626; font-weight:600; cursor:pointer; font-size:14px; text-align:center; }
.manage-del-btn:hover { background:#FEF2F2; }
.memory-card { background:var(--bg-card); border-radius:16px; padding:18px; margin-bottom:12px; border:1px solid var(--border-card); box-shadow: var(--shadow-card); }
.memory-card-head { display:flex; align-items:center; gap:10px; margin-bottom:8px; }
.memory-icon { font-size:22px; }
.memory-label { font-weight:700; color:var(--primary-dark); font-size:15px; }
.memory-val { font-size:15px; color:var(--text-body); padding:8px 12px; background:var(--primary-light); border-radius:10px; margin-bottom:8px; }
.memory-source { display:inline-block; font-size:12px; font-weight:600; padding:4px 10px; border-radius:20px; margin-bottom:8px; }
.memory-actions { display:flex; gap:8px; }
.memory-legend { display:flex; flex-wrap:wrap; gap:12px; padding:12px 16px; background:var(--primary-light); border-radius:12px; margin-bottom:16px; border:1px solid var(--border-card); }
.memory-legend-item { display:flex; align-items:center; gap:6px; font-size:12px; color:var(--text-muted); }
.memory-dot { width:8px; height:8px; border-radius:50%; }
.res-transparency { background:var(--primary-light); border-radius:14px; padding:18px; margin:12px 0; border:1px solid var(--border-card); }
.res-trans-h { font-weight:800; color:var(--primary-dark); font-size:16px; margin-bottom:4px; }
.res-trans-body { font-size:13px; color:var(--text-body); margin-bottom:14px; }
.trans-card { border-radius:12px; padding:14px; margin-bottom:10px; }
.trans-known { background:#F0FDF4; border:1px solid #BBF7D0; }
.trans-unclear { background:#FFFBEB; border:1px solid #FDE68A; }
.trans-notasked { background:var(--primary-light); border:1px solid var(--border-card); }
.trans-card-h { font-weight:700; font-size:14px; color:var(--primary-dark); margin-bottom:8px; display:flex; align-items:center; gap:8px; }
.trans-dot { width:10px; height:10px; border-radius:50%; display:inline-block; }
.trans-dot-green { background:#16A34A; }
.trans-dot-yellow { background:#F59E0B; }
.trans-dot-gray { background:var(--text-muted); }
.trans-items { display:flex; flex-direction:column; gap:4px; }
.trans-item { font-size:13px; color:var(--text-body); padding:4px 0; }
.trans-item-gray { color:var(--text-muted); }
.trans-add-btn { display:block; width:100%; padding:10px; margin-top:8px; border:2px dashed #FDE68A; border-radius:10px; background:#FFFBEB; color:#92400E; font-weight:600; font-size:13px; cursor:pointer; text-align:center; }
.trans-add-btn:hover { border-color:#F59E0B; background:#FEF3C7; }
.trans-note { font-size:12px; color:var(--text-muted); font-style:italic; margin-top:8px; }
.res-why { background:var(--primary-light); border-radius:14px; padding:18px; margin:12px 0; border:1px solid var(--border-card); }
.res-why-h { font-weight:800; color:var(--primary-dark); font-size:16px; margin-bottom:8px; }
.res-why-body { font-size:14px; line-height:1.8; color:var(--text-body); }
.res-action { border-radius:14px; padding:18px; margin:12px 0; }
.res-action-h { font-weight:800; color:var(--primary-dark); font-size:16px; margin-bottom:4px; }
.res-assess { background:var(--primary-light); border-radius:14px; padding:18px; margin:12px 0; border:1px solid var(--border-card); }
.res-assess-h { font-weight:800; color:var(--primary-dark); font-size:16px; margin-bottom:12px; }
.res-assess-row { display:flex; justify-content:space-between; align-items:center; padding:8px 0; border-bottom:1px solid var(--border-card); }
.res-assess-row:last-child { border-bottom:none; }
.res-assess-label { font-weight:600; color:var(--text-body); font-size:14px; }
.res-questions { background:linear-gradient(135deg,var(--primary-light),var(--bg-page)); border-radius:14px; padding:18px; margin:12px 0; border:1px solid var(--border-card); }
.res-questions-h { font-weight:800; color:var(--primary-dark); font-size:16px; margin-bottom:6px; }
.res-questions-body { font-size:13px; color:var(--text-body); margin-bottom:10px; }
/* Dark mode */
@media (prefers-color-scheme: dark) {
  body { background: #0F172A; color: #E2E8F0; }
  .nav { background: #1E293B; border-bottom-color: #334155; }
  .nav .logo { color: #E2E8F0; }
  .ss-mobile-head { background: rgba(30,41,59,.97); border-bottom-color: #334155; }
  .ss-mobile-logo { color: #E2E8F0; }
  .ss-mobile-lang { background: #172554; border-color: #334155; color: #BFDBFE; }
  .nav .links a { color: #CBD5E1; }
  .nav .links a.on { background: #1E3A5F; color: #60A5FA; }
  .card, .ss-profile-card, .ss-completion { background: #1E293B; border-color: #334155; }
  .card h2, .ss-profile-card h2 { color: #60A5FA; }
  .ss-field { border-bottom-color: #334155; }
  .ss-field label { color: #94A3B8; }
  .ss-next-step { background: linear-gradient(135deg, #1E293B, #172554); border-color: #1E3A5F; }
  .ss-next-step h3 { color: #93C5FD; }
  .ss-next-step p { color: #94A3B8; }
  .bubble.bot { background: #1E293B; border-color: #334155; }
  .chat-body { background: #0F172A; }
  .chat-options { background: #1E293B; border-color: #334155; }
  .opt { background: #1E293B; border-color: #334155; color: #E2E8F0; }
  .chat-input { background: #1E293B; border-color: #334155; }
  .chat-input input { background: #0F172A; border-color: #334155; color: #E2E8F0; }
  .chat-wrap { background: #1E293B; border-color: #334155; }
  .chat-head { background: var(--primary-dark); }
  .container { background: transparent; }
  .ss-bnav { background: #1E293B; border-color: #334155; }
  .ss-bnav a { color: #64748B; }
  .ss-bnav a.on { background: #1E3A5F; color: #60A5FA; }
  .welcome-card { background: #1E293B; border-color: #334155; }
  .ss-msg.success { background: #052E16; color: #4ADE80; border-color: #166534; }
  .ss-msg.error { background: #450A0A; color: #FCA5A5; border-color: #7F1D1D; }
  .ss-btn-danger { background: #450A0A; color: #FCA5A5; border-color: #7F1D1D; }
  .warn { background: #451A03; border-color: #92400E; color: #FCD34D; }
  .footer { background: #0F172A; }
  .asst-panel { background: #1E293B; border-color: #334155; }
  .asst-bot { background: #1E293B; border-color: #334155; color: #E2E8F0; }
  .asst-body { background: #0F172A; }
  .asst-inp { background: #0F172A; border-color: #334155; color: #E2E8F0; }
  .asst-opt { background: #1E293B; border-color: #334155; }
  .asst-opt .ao-t { color: #E2E8F0; }
  .asst-opt .ao-d { color: #94A3B8; }
  .asst-chip { background: #1E293B; border-color: #334155; color: #93C5FD; }
  .svc-card { background: #1E293B; border-color: #334155; }
  .quick-card { background: #1E293B; border-color: #334155; }
  .care-item { background: #1E293B; border-color: #334155; }
  .hh { background: transparent; }
  .hh-l { color: #E2E8F0; }
  .mh-card { background: #1E293B; border-color: #334155; }
  .hist-card { background: #1E293B; border-color: #334155; }
  .rec-card { background: #1E293B; border-color: #334155; }
  .res-card { background: #1E293B; border-color: #334155; }
  input.inp, select.inp, textarea.inp { background: #0F172A; border-color: #334155; color: #E2E8F0; }
  label.lbl { color: #CBD5E1; }
  .em-card { background: #1E293B; border-color: #7F1D1D; }
  .voice-card { background: #1E293B; }
  .expl-modal { background: #1E293B; border-color: #334155; }
  .ex-explain { background: #0F172A; border-color: #334155; }
  .asst-modal { background: #1E293B; border-color: #334155; }
  .res-why { background: #1E293B; border-color: #334155; }
  .res-why-h { color: #93C5FD; }
  .res-why-body { color: #CBD5E1; }
  .res-assess { background: #1E293B; border-color: #334155; }
  .res-assess-h { color: #93C5FD; }
  .res-assess-row { border-color: #334155; }
  .res-assess-label { color: #CBD5E1; }
  .res-questions { background: linear-gradient(135deg, #1E293B, #172554); border-color: #1E3A5F; }
  .res-questions-h { color: #93C5FD; }
  .res-questions-body { color: #94A3B8; }
  .manage-card { background: #1E293B; border-color: #334155; }
  .manage-label { color: #93C5FD; }
  .manage-val { background: #0F172A; color: #CBD5E1; }
  .manage-edit-btn { background: #1E293B; border-color: #334155; color: #E2E8F0; }
  .manage-del-btn { background: #450A0A; border-color: #7F1D1D; color: #FCA5A5; }
  .memory-card { background: #1E293B; border-color: #334155; }
  .memory-label { color: #93C5FD; }
  .memory-val { background: #0F172A; color: #CBD5E1; }
  .memory-legend { background: #0F172A; border-color: #334155; }
  .res-transparency { background: #1E293B; border-color: #334155; }
  .res-trans-h { color: #93C5FD; }
  .res-trans-body { color: #94A3B8; }
  .trans-card { border-color: #334155; }
  .trans-known { background: #052E16; border-color: #166534; }
  .trans-unclear { background: #451A03; border-color: #92400E; }
  .trans-notasked { background: #1E293B; border-color: #334155; }
  .trans-card-h { color: #E2E8F0; }
  .trans-item { color: #CBD5E1; }
  .trans-item-gray { color: #64748B; }
  .trans-note { color: #64748B; }
  .night-calm { background: #0F1729; border-color: #1E293B; }
}
.hero { background: linear-gradient(135deg, var(--primary) 0%, #42A5F5 55%, #64B5F6 100%); color: #fff; border-radius: 20px; padding: 48px 36px; text-align: center; margin-bottom: 30px; }
.hero h1 { font-size: 40px; margin-bottom: 12px; }
.hero p { font-size: 17px; opacity: .95; max-width: 640px; margin: 0 auto 24px; line-height: 1.8; }
.btn { display: inline-block; background: #fff; color: var(--primary); font-weight: 700; padding: 13px 30px; border-radius: 12px; margin: 6px; font-size: 16px; border: none; cursor: pointer; }
.btn.ghost { background: rgba(255,255,255,.15); color: #fff; border: 1px solid rgba(255,255,255,.5); }
.btn:hover { transform: translateY(-1px); }
.btn.small { padding: 7px 14px; font-size: 13px; border-radius: 9px; margin: 3px; }
.btn.ghost.small { background: var(--primary-light); color: var(--primary); border: 1px solid var(--primary); }
.card { background: var(--bg-card); border-radius: 16px; padding: 22px; box-shadow: var(--shadow-card); border: 1px solid var(--border-card); margin-bottom: 20px; }
.card h2 { color: var(--primary); margin-bottom: 12px; font-size: 20px; }
.features { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin-bottom: 24px; }
.feature { background: var(--bg-card); border: 1px solid var(--border-card); border-radius: 14px; padding: 20px; }
.feature .ic { font-size: 30px; }
.feature h3 { font-size: 16px; margin: 10px 0 6px; color: var(--primary); }
.feature p { font-size: 14px; color: var(--text-body); line-height: 1.7; }
a.feature.serv { display: block; text-decoration: none; transition: transform .12s ease, box-shadow .12s ease, border-color .12s ease; }
a.feature.serv:hover { transform: translateY(-3px); box-shadow: 0 8px 20px rgba(25,118,210,.14); border-color: var(--primary); }
.steps { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
.step { background: var(--bg-card); border: 1px solid var(--border-card); border-radius: 14px; padding: 20px; text-align: center; }
.step .n { width: 34px; height: 34px; border-radius: 50%; background: var(--primary); color: #fff; display: inline-flex; align-items: center; justify-content: center; font-weight: 800; }
.step h3 { margin: 10px 0 6px; font-size: 15px; }
.step p { font-size: 13px; color: var(--text-muted); }
.warn { background: #fff7ed; border: 1px solid #fdba74; color: #7c2d12; border-radius: 12px; padding: 14px 18px; font-size: 14px; margin-bottom: 22px; }
.footer { text-align: center; padding: 40px 22px 30px; color: #B9CCE8; font-size: 13px; background: var(--primary-dark); margin-top: 30px; border-radius: 26px 26px 0 0; }
.footer .f-brand { font-size: 22px; font-weight: 800; color: #FFFFFF; letter-spacing: .3px; }
.footer .f-brand span { color: #90CAF9; }
.footer .f-tag { margin-top: 4px; color: #B9CCE8; font-size: 14px; }
.footer a { color: #90CAF9; }
.footer .f-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 22px; max-width: 860px; margin: 24px auto 8px; text-align: start; }
.footer .f-sec h4 { color: #FFFFFF; font-size: 13px; font-weight: 800; margin: 0 0 8px; letter-spacing: .2px; }
.footer .f-sec p { color: #B9CCE8; line-height: 1.8; font-size: 12.8px; margin: 0; }
.footer .f-sec .f-owner { display: block; font-size: 13.5px; color: #EAF4FF; line-height: 1.9; }
.footer .f-sec .f-owner:hover { color: #FFFFFF; }
.footer .f-tg { display: inline-flex; align-items: center; gap: 8px; background: #1976D2; color: #FFFFFF; font-weight: 700; font-size: 13px; padding: 9px 16px; border-radius: 999px; text-decoration: none; margin-top: 2px; }
.footer .f-tg:hover { background: #1565C0; color: #FFFFFF; }
.footer .f-links { display: flex; gap: 18px; justify-content: center; flex-wrap: wrap; margin: 18px 0 22px; font-size: 13px; }
.footer .f-links a { color: #EAF4FF; }
.footer .f-links a:hover { color: #FFFFFF; text-decoration: underline; }
.footer .f-love { color: #FFFFFF; font-size: 14.5px; font-weight: 700; letter-spacing: .2px; }
.footer .f-love b { color: #90CAF9; font-weight: 800; }
.footer .f-copy { color: #8CA7CC; margin-top: 8px; font-size: 12px; }
.chat-wrap { max-width: 900px; margin: 0 auto; background: var(--bg-card); border-radius: 22px; box-shadow: var(--shadow-card); border: 1px solid var(--border-card); overflow: hidden; display: flex; flex-direction: column; height: 78vh; }
.chat-head { background: linear-gradient(135deg, #1976D2, #1565C0); color: #fff; padding: 14px 18px; display: flex; align-items: center; gap: 10px; }
.chat-head .avatar { width: 40px; height: 40px; border-radius: 50%; background: rgba(255,255,255,.2); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 20px; }
.chat-head h3 { font-size: 16px; }
.chat-head p { font-size: 12px; opacity: .85; }
.chat-head .spk-btn { margin: 0; background: rgba(255,255,255,.15); border: none; border-radius: 10px; padding: 8px 10px; font-size: 13px; cursor: pointer; color: #fff; white-space: nowrap; }
.chat-head-toggles { display: flex; align-items: center; gap: 8px; }
.chat-body { flex: 1; overflow-y: auto; padding: 18px; background: #F5F9FF; }
.bubble { max-width: 85%; margin-bottom: 10px; padding: 11px 15px; border-radius: 14px; font-size: 15px; line-height: 1.8; white-space: pre-wrap; }
.bubble.bot { background: var(--bg-card); border: 1px solid var(--border-card); border-bottom-right-radius: 4px; }
.bubble.user { background: var(--primary); color: #fff; margin-left: auto; border-bottom-left-radius: 4px; }
.bubble.result { background: var(--bg-card); border: 1px solid #DCEBFA; max-width: 100%; }
.chat-options { padding: 14px; background: var(--bg-card); border-top: 1px solid var(--border-card); display: flex; flex-wrap: wrap; gap: 8px; }
.opt { background: var(--bg-card); border: 1.5px solid #DCEBFA; color: var(--primary-dark); padding: 10px 18px; border-radius: 24px; font-size: 14.5px; font-weight: 600; cursor: pointer; }
.vidbtn { display:inline-block; margin-top:12px; background:var(--primary); color:#fff; border:none; padding:10px 18px; border-radius:24px; font-size:14px; cursor:pointer; }
.vidbtn:hover { background:#1565C0; }
.vidwrap iframe { display:block; }
.opt.sel { background: var(--primary); color: #fff; }
.opt.danger { border-color: #dc2626; color: #dc2626; background: #fef2f2; }
.opt:hover { opacity: .9; }
.chat-input { display: flex; gap: 8px; padding: 12px 14px; background: var(--bg-card); border-top: 1px solid var(--border-card); }
.chat-input input { flex: 1; border: 1px solid var(--border-card); border-radius: 12px; padding: 12px 14px; font-size: 15px; font-family: inherit; }
.chat-input button { background: var(--primary); color: #fff; border: none; border-radius: 12px; padding: 12px 20px; font-size: 15px; cursor: pointer; }
.urg-low { border-right: 6px solid #16a34a; }
.urg-medium { border-right: 6px solid #d97706; }
.urg-high { border-right: 6px solid #dc2626; }
.sec-title { font-weight: 800; color: var(--primary); margin: 14px 0 6px; font-size: 15px; }
.res-sec { margin: 10px 0; }
.rec-item { background: var(--primary-light); border: 1px solid var(--border-card); border-radius: 10px; padding: 10px 12px; margin: 8px 0; }
.rec-item .src { color: var(--primary); font-size: 12px; }
.drop { border: 2px dashed var(--primary); border-radius: 16px; padding: 40px; text-align: center; color: var(--primary); cursor: pointer; background: var(--primary-light); margin-bottom: 16px; }
.drop.on { background: #EAF4FF; }
.muted { color: var(--text-muted); font-size: 13px; }
.urg-lbl { display: block; font-size: 13px; font-weight: 700; opacity: .85; }
.urg-val { display: block; font-size: 21px; font-weight: 800; margin-top: 2px; }
.rec-card { background: var(--bg-card); border: 1px solid var(--border-card); border-radius: 14px; padding: 12px 14px; margin: 10px 0; box-shadow: var(--shadow-card); }
.rec-head { display: flex; align-items: center; gap: 8px; color: var(--primary-dark); font-size: 14.5px; }
.rec-num { flex: none; width: 22px; height: 22px; border-radius: 50%; background: var(--primary); color: #fff; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 800; }
.rec-body { color: var(--text-body); font-size: 13.5px; line-height: 1.8; margin-top: 6px; }
.rec-card .src { color: var(--primary); font-size: 12px; margin-top: 6px; }
.ml-row { display: flex; justify-content: space-between; font-size: 13.5px; margin-top: 8px; }
.ml-note { color: var(--text-muted); font-size: 12px; margin-top: 8px; line-height: 1.7; }
.sel-sum { color: var(--text-muted); font-size: 13px; font-weight: 600; margin-top: 6px; }
.res-sec.bullets { white-space: pre-line; line-height: 1.9; color: var(--text-body); }
.card label { display: block; font-size: 13px; font-weight: 700; color: var(--primary); margin-bottom: 4px; }
.card input, .card select { width: 100%; padding: 10px 12px; border: 1px solid var(--border-card); border-radius: 10px; font-size: 14px; font-family: inherit; background: var(--primary-light); color: var(--text-body); }
.pr-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.dash-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 12px; }
.dash-stat { background: var(--primary-light); border: 1px solid var(--border-card); border-radius: 14px; padding: 12px 6px; text-align: center; }
.dash-stat b { display: block; font-size: 22px; color: var(--primary-dark); }
.dash-stat span { font-size: 12px; color: var(--text-muted); }
.tools { max-width: 880px; margin: 30px auto 0; padding: 0 8px; }
.tools-h { text-align: center; font-size: 23px; font-weight: 800; color: var(--primary-dark); }
.tools-sub { text-align: center; color: var(--text-muted); margin-bottom: 16px; font-size: 14px; }
.tools-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.tool { background: var(--bg-card); border: 1.5px solid var(--border-card); border-radius: 16px; padding: 18px 12px; text-align: center; text-decoration: none; color: var(--text-body); transition: transform .15s ease, box-shadow .15s ease, border-color .15s ease; }
.tool:hover { transform: translateY(-3px); box-shadow: 0 10px 22px rgba(25,118,210,.08); border-color: var(--primary); }
.tool .t-ic { font-size: 34px; display: block; margin-bottom: 8px; }
.tool b { display: block; font-size: 15px; color: var(--primary); margin-bottom: 4px; }
.tool p { font-size: 12.5px; color: var(--text-muted); line-height: 1.6; }
@media (max-width: 640px) { .tools-grid { grid-template-columns: repeat(2, 1fr); } }
.cmp-table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }
.cmp-table th, .cmp-table td { border: 1px solid var(--border-card); padding: 8px 10px; text-align: center; }
.cmp-table th { background: var(--primary-light); color: var(--primary-dark); font-size: 12px; }
.hist-card { background: var(--primary-light); border: 1px solid var(--border-card); border-radius: 12px; padding: 14px 16px; margin-bottom: 12px; }
.hist-head { display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap; }
.pill { padding: 3px 11px; border-radius: 999px; font-size: 12px; font-weight: 700; }
.pill-hi { background: #fee2e2; color: #b91c1c; }
.pill-med { background: #fef3c7; color: #92400e; }
.pill-low { background: #dcfce7; color: #166534; }
.hist-row { margin-top: 8px; display: flex; gap: 6px; flex-wrap: wrap; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.em-overlay { position: fixed; inset: 0; z-index: 9999; display: none; align-items: center; justify-content: center; background: rgba(15,23,42,.55); backdrop-filter: blur(3px); padding: 18px; }
.blood-banner { margin: 12px auto 0; max-width: 560px; text-align: center; padding: 10px 16px; background: var(--primary-light); border: 1px solid var(--border-card); color: var(--primary-dark); border-radius: 12px; font-size: 13.5px; font-weight: 700; }
.rel-title { text-align: center; font-size: 13px; font-weight: 800; color: var(--primary); margin-top: 14px; }
.rel-chips { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-top: 8px; }
.rel-chip { padding: 8px 14px; border-radius: 999px; border: 1.5px dashed var(--primary); background: var(--bg-card); color: var(--primary); font-size: 13px; font-weight: 700; cursor: pointer; }
.rel-chip:hover { background: #EAF4FF; }
.em-card { background: #FFFFFF; border: 2px solid #DC2626; border-radius: 22px; padding: 30px 26px; max-width: 460px; width: 100%; text-align: center; box-shadow: 0 26px 70px rgba(153,27,27,.35); animation: emPop .35s cubic-bezier(.34,1.56,.64,1); }
@keyframes emPop { from { transform: scale(.85); opacity: 0; } to { transform: scale(1); opacity: 1; } }
.em-card .em-icon { width: 74px; height: 74px; margin: 0 auto 12px; border-radius: 50%; background: #FEE2E2; display: flex; align-items: center; justify-content: center; font-size: 40px; }
.em-card h3 { font-size: 23px; font-weight: 800; color: #991B1B; margin: 0 0 8px; }
.em-card p { font-size: 15px; color: var(--text-body); line-height: 1.7; margin: 0 0 14px; }
.em-flags { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-bottom: 18px; }
.em-chip { background: #FEF2F2; border: 1px solid #FECACA; color: #991B1B; font-size: 13px; font-weight: 700; padding: 6px 12px; border-radius: 999px; }
.em-btns { display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; }
.em-call { background: #DC2626; color: #FFFFFF; font-weight: 800; padding: 12px 22px; border-radius: 12px; font-size: 15px; text-decoration: none; transition: background .2s ease, transform .15s ease; }
.em-call:hover { background: #B91C1C; transform: translateY(-2px); }
.em-num { margin: 10px 0 2px; font-size: 16px; font-weight: 800; color: #B91C1C; letter-spacing: 1px; cursor: pointer; user-select: all; }
.em-proceed { background: var(--primary-light); color: var(--primary-dark); font-weight: 700; padding: 12px 22px; border-radius: 12px; font-size: 15px; border: 1px solid var(--border-card); cursor: pointer; transition: background .2s ease; }
.em-proceed:hover { background: var(--primary-pale); }
.voice-overlay { position: fixed; inset: 0; z-index: 9999; display: none; align-items: center; justify-content: center; background: rgba(15,23,42,.55); backdrop-filter: blur(3px); padding: 18px; }
.voice-card { background: var(--bg-card); border-radius: 22px; padding: 30px 26px; max-width: 360px; width: 100%; text-align: center; box-shadow: 0 26px 70px rgba(25,118,210,.15); animation: emPop .35s cubic-bezier(.34,1.56,.64,1); }
.v-mic { width: 84px; height: 84px; margin: 0 auto 14px; border-radius: 50%; background: var(--primary-light); border: 3px solid var(--primary); display: flex; align-items: center; justify-content: center; font-size: 42px; animation: vPulse 1.4s ease-in-out infinite; }
@keyframes vPulse { 0%,100% { box-shadow: 0 0 0 0 rgba(25,118,210,.45); transform: scale(1); } 50% { box-shadow: 0 0 0 18px rgba(25,118,210,0); transform: scale(1.06); } }
.v-title { font-size: 16px; font-weight: 800; color: var(--primary-dark); }
.cs-voice { display: inline-block; margin-top: 14px; padding: 10px 20px; border-radius: 999px; border: 1.5px dashed var(--primary); background: var(--primary-light); color: var(--primary); font-weight: 800; font-size: 14px; cursor: pointer; transition: background .2s ease; }
.cs-voice:hover { background: #EAF4FF; }
.vstop { background: var(--primary); color: #FFFFFF; font-weight: 800; padding: 11px 22px; border-radius: 12px; font-size: 14px; border: none; cursor: pointer; }
.vcnl { background: var(--primary-light); color: var(--text-body); font-weight: 700; padding: 11px 22px; border-radius: 12px; font-size: 14px; border: 1px solid var(--border-card); cursor: pointer; }
.warn { background: #FEF2F2; border: 1px solid #FECACA; color: #991B1B; padding: 10px 14px; border-radius: 12px; font-size: 14px; font-weight: 700; margin: 8px 0; }
.em-disc { font-size: 12px; color: var(--text-muted); margin-top: 12px; }
@media (max-width: 700px) { .grid2 { grid-template-columns: 1fr; } .hero h1 { font-size: 30px; } .chat-wrap { height: 84vh; } }
label.lbl { display: block; font-size: 14px; font-weight: 700; margin: 12px 0 6px; color: var(--text-body); }
input.inp, select.inp, textarea.inp { width: 100%; border: 1px solid var(--border-card); border-radius: 10px; padding: 12px; font-size: 15px; font-family: inherit; }
table.tbl { width: 100%; border-collapse: collapse; font-size: 14px; }
table.tbl th, table.tbl td { border: 1px solid var(--border-card); padding: 9px 11px; text-align: right; }
table.tbl th { background: var(--primary); color: #fff; }
.pill { display: inline-block; padding: 3px 12px; border-radius: 20px; font-size: 13px; font-weight: 700; }
.pill.low { background: #dcfce7; color: #166534; }
.pill.medium { background: #fef3c7; color: #92400e; }
.pill.high { background: #fee2e2; color: #991b1b; }
.badge { background: var(--primary); color: #fff; padding: 4px 12px; border-radius: 20px; font-size: 12px; }
.bar-bg { background: var(--border-card); border-radius: 8px; height: 10px; width: 100%; margin: 4px 0; }
.bar-fill { background: var(--primary); height: 10px; border-radius: 8px; }
.spin { display: inline-block; width: 16px; height: 16px; border: 2px solid #DCEBFA; border-top-color: transparent; border-radius: 50%; animation: sp 1s linear infinite; vertical-align: middle; }
@keyframes sp { to { transform: rotate(360deg); } }
@keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
.fade { animation: fadeIn .45s ease both; }
.hero, .card, .feature, .step, .welcome-card { animation: fadeIn .5s ease both; }
html[dir="ltr"] .bubble.user { margin-left: 0; margin-right: auto; }
html[dir="ltr"] .urg-low { border-right: none; border-left: 6px solid #16a34a; }
html[dir="ltr"] .urg-medium { border-right: none; border-left: 6px solid #d97706; }
html[dir="ltr"] .urg-high { border-right: none; border-left: 6px solid #dc2626; }
html[dir="ltr"] table.tbl th, html[dir="ltr"] table.tbl td { text-align: left; }
.welcome-wrap { min-height: 86vh; display: flex; align-items: center; justify-content: center; padding: 26px 18px; }
.welcome-card { background: var(--bg-card); border: 1px solid var(--border-card); border-radius: 22px; box-shadow: 0 10px 30px rgba(25,118,210,.08); padding: 42px 30px; max-width: 560px; width: 100%; text-align: center; }
.welcome-card .logo-big { font-size: 62px; }
.welcome-card h1 { font-size: 30px; color: var(--primary); margin: 14px 0 8px; }
.welcome-card p { color: var(--text-body); font-size: 15px; line-height: 1.8; margin-bottom: 26px; }
.lang-row { display: flex; gap: 14px; justify-content: center; flex-wrap: wrap; }
.lang-btn { flex: 1; min-width: 200px; background: var(--primary-light); border: 2px solid var(--primary); border-radius: 14px; padding: 22px 14px; cursor: pointer; transition: transform .12s ease, box-shadow .12s ease, background .12s ease; }
.lang-btn:hover { transform: translateY(-3px); box-shadow: 0 8px 20px rgba(25,118,210,.18); background: #EAF4FF; }
.lang-btn .lc { font-size: 34px; display: block; margin-bottom: 8px; }
.lang-btn .lt { font-size: 20px; font-weight: 800; color: var(--primary); display: block; }
.lang-btn .ld { font-size: 13px; color: var(--text-body); display: block; margin-top: 4px; }
.multi-greet { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; margin: 0 0 22px; }
.greet-line { display: inline-flex; align-items: center; gap: 7px; background: var(--primary-light); border: 1px solid var(--border-card); border-radius: 999px; padding: 6px 14px; font-size: 13.5px; color: var(--text-body); }
.greet-line .gflag { font-size: 16px; }
.welcome-full { position: fixed; inset: 0; z-index: 60; background: linear-gradient(180deg, #F5F9FF 0%, #EAF4FF 100%); overflow: hidden; transition: opacity .8s ease; }
.welcome-full.fade-out { opacity: 0; }
.w-cloud { position: absolute; inset: 0; }
.gword { position: absolute; display: inline-block; font-family: 'Amiri', 'Cairo', serif; font-weight: 700; color: var(--primary); white-space: nowrap; text-shadow: 0 3px 18px rgba(25,118,210,.20); animation: floaty var(--dur,10s) ease-in-out var(--delay,0s) infinite; }
@keyframes floaty { 0%,100% { transform: rotate(var(--rot,0deg)) translateY(0); } 50% { transform: rotate(var(--rot,0deg)) translateY(-14px); } }
.lang-area { position: absolute; bottom: 30px; left: 0; right: 0; display: flex; flex-direction: column; align-items: center; gap: 12px; z-index: 5; }
.lang-opts { display: flex; gap: 10px; opacity: 0; transform: translateY(14px); pointer-events: none; transition: opacity .45s ease, transform .45s ease; }
.lang-opts.show { opacity: 1; transform: translateY(0); pointer-events: auto; }
.lang-btn { font-family: 'Cairo', 'Segoe UI', sans-serif; font-size: 15px; font-weight: 700; color: var(--primary); background: rgba(255,255,255,.9); border: 2px solid var(--primary); border-radius: 999px; padding: 10px 30px; cursor: pointer; box-shadow: 0 4px 16px rgba(25,118,210,.18); transition: transform .15s ease, background .15s ease; }
.lang-btn:hover { transform: translateY(-2px); background: #EAF4FF; }
.exit-curtain { position: fixed; z-index: 999; left: 50%; top: 50%; width: 150vmax; height: 150vmax; margin-left: -75vmax; margin-top: -75vmax; border-radius: 50%; background: radial-gradient(circle at center, #64B5F6, var(--primary) 60%, var(--primary-dark)); transform: scale(0); opacity: 0; pointer-events: none; transition: transform .9s cubic-bezier(.65,0,.35,1), opacity .55s ease; }
.exit-curtain.open { transform: scale(1); opacity: 1; }
.welcome-pick { display: none; position: fixed; z-index: 61; top: 50%; left: 50%; transform: translate(-50%, -46%); max-width: 580px; width: 92%; background: var(--bg-card); border: 1px solid var(--border-card); border-radius: 22px; box-shadow: 0 14px 40px rgba(25,118,210,.14); padding: 30px 26px; text-align: center; }
.welcome-pick.show { display: block; animation: pickIn .9s ease forwards; }
@keyframes pickIn { from { opacity: 0; transform: translate(-50%, -46%) scale(.94); } to { opacity: 1; transform: translate(-50%, -46%) scale(1); } }
.welcome-pick .logo-big { font-size: 52px; }
.welcome-pick h1 { font-size: 26px; color: var(--primary); margin: 10px 0 4px; }
.pick-btn { display: inline-block; margin: 4px; padding: 10px 26px; border-radius: 999px; border: 2px solid var(--primary); background: var(--primary); color: #fff; font-family: inherit; font-size: 15px; font-weight: 700; cursor: pointer; transition: transform .12s ease, background .12s ease; }
.pick-btn:hover { transform: translateY(-2px); background: var(--primary-dark); }
body.page-exit { transition: opacity .45s ease, transform .45s ease; opacity: 0; transform: scale(1.02); }
.nav .lang-sw { display: flex; align-items: center; gap: 2px; background: var(--primary-light); border-radius: 999px; padding: 3px; }
.nav .lang-sw a { font-size: 13px; font-weight: 700; padding: 6px 14px; border-radius: 999px; color: var(--primary); }
.nav .lang-sw a:hover { background: #EAF4FF; }
.nav .lang-sw a.on { background: var(--primary); color: #FFFFFF; }
.dd { position: relative; }
.dd-btn { background: var(--primary-light); border: none; color: var(--primary); font-weight: 700; font-family: inherit; font-size: 14.5px; padding: 9px 15px; border-radius: 10px; cursor: pointer; display: inline-flex; align-items: center; gap: 5px; }
.dd-btn:hover { background: #EAF4FF; }
.dd-menu { display: none; position: absolute; top: calc(100% + 8px); right: 0; min-width: 215px; background: var(--bg-card); border: 1px solid var(--border-card); border-radius: 14px; box-shadow: 0 16px 36px rgba(25,118,210,.16); padding: 8px; z-index: 90; }
.dd-menu.open { display: block; }
.dd-menu a { display: block; padding: 10px 13px; border-radius: 10px; color: var(--text-body); font-size: 14px; font-weight: 600; }
.dd-menu a:hover { background: var(--primary-light); color: var(--primary); }
html[dir="ltr"] .dd-menu { right: auto; left: 0; }
.account-dd { display: flex; align-items: center; gap: 2px; padding: 3px; border: 1px solid var(--border-card); border-radius: 14px; background: var(--primary-light); }
.account-profile-link { display: flex; align-items: center; gap: 8px; padding: 3px 7px; border-radius: 10px; color: var(--primary-dark); min-width: 0; }
.account-profile-link:hover { background: var(--bg-card); }
.account-avatar { width: 34px; height: 34px; flex: 0 0 34px; display: grid; place-items: center; border-radius: 11px; background: var(--bg-card); color: var(--primary); border: 1px solid var(--border-card); font-size: 17px; }
.account-btn-copy { min-width: 0; line-height: 1.25; text-align: start; }
.account-name { display: block; max-width: 145px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--primary-dark); font-size: 12.5px; font-weight: 800; }
.account-label { display: block; color: var(--text-muted); font-size: 10px; font-weight: 700; margin-top: 2px; }
.account-menu-toggle { width: 32px; height: 34px; display: grid; place-items: center; border: 0; border-radius: 10px; background: transparent; color: var(--primary); font-size: 11px; cursor: pointer; }
.account-menu-toggle:hover, .account-menu-toggle[aria-expanded="true"] { background: var(--bg-card); }
.account-menu { min-width: 270px; padding: 8px; }
.account-menu-head { display: flex; align-items: center; gap: 10px; padding: 11px; margin-bottom: 6px; border-radius: 11px; background: var(--primary-light); border: 1px solid var(--border-card); }
.account-menu-head .account-avatar { width: 40px; height: 40px; flex-basis: 40px; font-size: 20px; }
.account-menu-head strong { display: block; max-width: 175px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--primary-dark); font-size: 13px; }
.account-menu-head small { display: block; max-width: 175px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-muted); font-size: 10.5px; direction: ltr; text-align: start; }
.account-menu a { display: flex; align-items: center; gap: 9px; }
.account-menu a.account-logout { color: #B91C1C; border-top: 1px solid var(--border-card); border-radius: 0 0 9px 9px; margin-top: 5px; padding-top: 11px; }
.account-menu a.account-logout:hover { background: #FEF2F2; color: #991B1B; }
@media (prefers-color-scheme: dark) {
  .dd-btn, .account-dd { background: #1E293B; border-color: #334155; color: #93C5FD; }
  .dd-menu { background: #1E293B; border-color: #334155; }
  .dd-menu a { color: #CBD5E1; }
  .dd-menu a:hover { background: #1E3A5F; color: #93C5FD; }
  .account-profile-link:hover, .account-menu-toggle:hover, .account-menu-toggle[aria-expanded="true"] { background: #0F172A; }
  .account-avatar { background: #0F172A; border-color: #334155; color: #60A5FA; }
  .account-name, .account-menu-head strong { color: #E2E8F0; }
  .account-label, .account-menu-head small { color: #94A3B8; }
  .account-menu-head { background: #0F172A; border-color: #334155; }
  .account-menu a.account-logout { border-color: #334155; color: #FCA5A5; }
  .account-menu a.account-logout:hover { background: #450A0A; color: #FCA5A5; }
}
.nav .links a.on { background: var(--primary-light); color: var(--primary); }
.cbc { font-size: 15px; font-weight: 700; color: var(--primary-dark); margin-bottom: 6px; }
.field-box { display: flex; align-items: center; gap: 12px; background: var(--primary-light); border: 1px solid var(--border-card); border-radius: 14px; padding: 14px; }
.field-box .fb-ic { font-size: 24px; width: 46px; height: 46px; min-width: 46px; border-radius: 12px; background: var(--primary-light); display: flex; align-items: center; justify-content: center; }
.field-box .lbl { margin: 0 0 4px; color: var(--primary-dark); }
.field-box input, .field-box select { background: var(--bg-card); }
.hint-note { text-align: center; color: var(--text-muted); font-size: 12.5px; margin: 12px 0 16px; }
.drop { border: 2px dashed var(--primary); border-radius: 18px; padding: 34px 20px; text-align: center; color: var(--primary-dark); cursor: pointer; background: var(--primary-light); margin-bottom: 0; }
.drop .d-icon { font-size: 40px; margin-bottom: 8px; }
.drop .d-text { font-size: 15px; font-weight: 700; color: var(--primary-dark); }
.drop .d-or { color: var(--text-muted); font-size: 13px; margin: 6px 0; }
.drop .d-btn { display: inline-block; background: var(--primary); color: #FFFFFF; font-weight: 700; padding: 9px 22px; border-radius: 999px; font-size: 14px; }
.drop .d-note { color: var(--text-muted); font-size: 12px; margin-top: 10px; }
.drop.on { background: #EAF4FF; border-color: var(--primary); }
.drop.selected { cursor: default; background: #EFF7FF; border-style: solid; border-color: #16a34a; }
.drop.selected .d-file { font-weight: 700; color: var(--primary-dark); font-size: 15px; word-break: break-all; }
.d-del { margin-top: 8px; background: var(--bg-card); color: #dc2626; border: 1.5px solid #fca5a5; font-weight: 700; padding: 8px 20px; border-radius: 999px; font-size: 13.5px; cursor: pointer; font-family: inherit; }
.d-del:hover { background: #fee2e2; }
.btn.pri.big { font-size: 17px; padding: 15px 44px; border-radius: 999px; }
.bl-table { margin-top: 12px; }
.bl-sum-chips { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin: 10px 0 12px; }
.bl-chip { font-size: 13px; font-weight: 800; padding: 8px 14px; border-radius: 999px; }
.bl-chip.cg { background: #dcfce7; color: #166534; }
.bl-chip.ca { background: #fef3c7; color: #92400e; }
.bl-chip.cr { background: #fee2e2; color: #b91c1c; }
.bl-table .pill2 { font-size: 12.5px; padding: 3px 12px; }
.bl-table .bl-row { cursor: pointer; }
.bl-table .bl-row:hover td { background: var(--primary-light); }
.bl-explain { border: 1px solid #DCEBFA; background: #EAF4FF; color: var(--primary); border-radius: 999px; padding: 2px 9px; font-size: 11px; font-weight: 700; cursor: pointer; font-family: inherit; margin-inline-start: 6px; white-space: nowrap; }
.bl-explain:hover { background: #EAF4FF; }
.bl-detail td { background: var(--primary-light); }
.bl-det-inner { font-size: 14px; line-height: 1.8; color: var(--text-body); }
.bl-det-inner p { margin: 4px 0; }
.bl-det-inner b { color: var(--primary); }
.bl-notes { margin-top: 12px; }
.bl-note { font-size: 12.5px; color: #7A5B00; background: #FFF8E7; border: 1px solid #F5D78E; border-radius: 10px; padding: 10px 13px; margin-top: 10px; }
.p2-green { background: #dcfce7; color: #166534; }
.p2-orange { background: #fef3c7; color: #92400e; }
.p2-red { background: #fee2e2; color: #b91c1c; }
.p2-dark { background: #dc2626; color: #FFFFFF; }
.search-box { display: flex; align-items: center; gap: 10px; }
.search-box .sb-ic { font-size: 22px; }
.search-box .inp { flex: 1; }
.search-box .sb-btn { margin: 0; white-space: nowrap; }
@media (max-width: 640px) { .search-box { flex-wrap: wrap; } .search-box .sb-btn { flex: 1; } }
.drug-card { background: var(--primary-light); border: 1px solid var(--border-card); border-radius: 14px; padding: 18px; }
.drug-name { font-size: 19px; font-weight: 800; color: var(--primary-dark); margin-bottom: 12px; }
.drug-sec { margin-bottom: 14px; }
.drug-sec-t { font-weight: 800; color: var(--primary); font-size: 14.5px; margin-bottom: 4px; }
.drug-sec-t.wr { color: #b45309; }
.drug-sec-t.wt { color: #dc2626; }
.drug-sec p { font-size: 14px; color: var(--text-body); line-height: 1.8; }
.drug-note { font-size: 12.5px; color: #7A5B00; background: #FFF8E7; border: 1px solid #F5D78E; border-radius: 10px; padding: 10px 13px; }
.tip-card { background: linear-gradient(180deg, var(--primary-light) 0%, #FFFFFF 70%); border: 1.5px solid var(--border-card); border-radius: 18px; padding: 22px 20px; }
.tip-top { display: flex; align-items: center; gap: 14px; margin-bottom: 12px; }
.tip-icon { font-size: 42px; width: 64px; height: 64px; min-width: 64px; border-radius: 16px; background: var(--primary-light); display: flex; align-items: center; justify-content: center; }
.tip-cat { display: inline-block; font-size: 12px; font-weight: 800; color: var(--primary); background: var(--primary-light); border-radius: 999px; padding: 3px 12px; margin-bottom: 4px; }
.tip-top h3 { font-size: 19px; color: var(--primary-dark); margin: 0; }
.tip-text { font-size: 14.5px; color: var(--text-body); line-height: 1.9; margin-bottom: 12px; }
.tip-tip { font-size: 13.5px; color: #166534; background: #dcfce7; border: 1px solid #bbf7d0; border-radius: 12px; padding: 10px 14px; line-height: 1.8; }
.em-alert { background: #FEF3C7; border: 1.5px solid #F59E0B; color: #92400e; border-radius: 14px; padding: 13px 16px; font-size: 14px; margin: 14px 0 20px; line-height: 1.8; }
.em-grid3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 14px; }
@media (max-width: 760px) { .em-grid3 { grid-template-columns: 1fr; } }
.em-card { background: var(--bg-card); border: 1.5px solid var(--border-card); border-radius: 18px; padding: 22px 18px; text-align: center; }
.em-card .em-ic { font-size: 34px; }
.em-card h3 { font-size: 16px; color: var(--primary-dark); margin: 10px 0 4px; }
.em-desc { font-size: 13px; color: var(--text-muted); min-height: 42px; line-height: 1.7; }
.em-num { font-size: 34px; font-weight: 800; letter-spacing: 1px; margin: 10px 0; }
.em-num.red { color: #dc2626; }
.em-num.blue { color: var(--primary); }
.em-call { display: inline-block; background: #dc2626; color: #FFFFFF; font-weight: 700; padding: 10px 24px; border-radius: 999px; font-size: 14.5px; }
.em-call:hover { opacity: .9; }
.em-call.blue { background: var(--primary); }
.em-call.big { font-size: 17px; padding: 14px 40px; }
.em-mini { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 4px; }
@media (max-width: 640px) { .em-mini { grid-template-columns: 1fr; } }
.em-mini-card { display: flex; align-items: center; gap: 10px; background: var(--primary-light); border: 1px solid var(--border-card); border-radius: 14px; padding: 14px 16px; flex-wrap: wrap; }
.em-mini-card .em-mini-num { margin-inline-start: auto; font-size: 22px; font-weight: 800; color: var(--primary); }
.em-danger { border: 1.5px solid #FECACA; }
.em-danger-h { color: #b91c1c !important; }
.em-signs { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; }
.em-sign { background: #fef2f2; border: 1px solid #fecaca; color: #7f1d1d; border-radius: 12px; padding: 12px 14px; font-size: 13.5px; font-weight: 700; text-align: center; }
.em-24h { display: inline-block; background: var(--primary-light); color: var(--primary); font-weight: 700; font-size: 13px; padding: 7px 16px; border-radius: 999px; }
.em-safety { background: #FEF3C7; border-color: #F59E0B; color: #92400e; }
.hh { display: flex; align-items: center; gap: 30px; background: linear-gradient(120deg, var(--primary-light) 0%, #FFFFFF 78%); border: 1px solid var(--border-card); border-radius: 34px; padding: 48px 44px; box-shadow: 0 18px 50px rgba(25,118,210,.10); margin-bottom: 34px; max-width: 100%; overflow: hidden; }
.hh-badge { display: inline-flex; align-items: center; gap: 8px; background: var(--primary-light); color: var(--primary-dark); font-size: 13px; font-weight: 700; border-radius: 999px; padding: 8px 16px; margin-bottom: 18px; }
.hh-l { flex: 1.2; min-width: 0; }
.hh-l h1 { font-size: clamp(26px, 6vw, 42px); line-height: 1.18; color: var(--primary-dark); margin: 0 0 8px; }
.hh-l h1 .hl { color: var(--primary); }
.hh-sub { font-size: clamp(15px, 3vw, 19px); font-weight: 700; color: var(--primary-dark); margin-bottom: 10px; }
.hh-desc { font-size: clamp(13.5px, 2.6vw, 15.5px); color: var(--text-body); line-height: 1.8; margin-bottom: 26px; max-width: 560px; }
.hh-btns { display: flex; gap: 12px; flex-wrap: wrap; }
.btn.pri { background: var(--primary); color: #FFFFFF; box-shadow: 0 10px 24px rgba(25,118,210,.30); }
.btn.pri:hover { background: #1565C0; transform: translateY(-2px); }
.btn.sec { background: #FFFFFF; color: var(--primary-dark); border: 1.5px solid var(--border-card); }
.btn.sec:hover { border-color: var(--primary); color: var(--primary); transform: translateY(-2px); }
.hh-r { flex: 1; display: flex; align-items: center; justify-content: center; position: relative; min-height: 420px; }
.hh-globe { position: absolute; width: 360px; height: 360px; border-radius: 50%; background: radial-gradient(circle, rgba(25,118,210,.14) 0%, rgba(25,118,210,.04) 55%, transparent 70%); }
.hh-globe::before, .hh-globe::after { content: ''; position: absolute; border-radius: 50%; border: 1.5px solid rgba(25,118,210,.18); inset: 12%; }
.hh-globe::after { inset: 26%; }
.hh-ic { position: absolute; font-size: 34px; filter: drop-shadow(0 6px 14px rgba(25,118,210,.25)); animation: floatic 5s ease-in-out infinite; }
.hh-ic.i1 { top: 6%; left: 6%; animation-delay: 0s; }
.hh-ic.i2 { top: 2%; right: 12%; animation-delay: 1.1s; }
.hh-ic.i3 { bottom: 12%; left: 12%; animation-delay: 2s; }
.hh-ic.i4 { bottom: 4%; right: 6%; animation-delay: .6s; }
.hh-ic.i5 { top: 36%; left: 0; animation-delay: 1.6s; }
.hh-ic.i6 { top: 34%; right: 0; animation-delay: .3s; }
.phone { width: 200px; height: 396px; background: var(--primary-dark); border-radius: 40px; padding: 12px; box-shadow: 0 34px 70px rgba(18,59,112,.35), inset 0 0 0 2px rgba(255,255,255,.12); position: relative; z-index: 2; }
.phone-screen { width: 100%; height: 100%; border-radius: 30px; background: linear-gradient(180deg, var(--primary-light) 0%, #FFFFFF 100%); display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: 20px; }
.phone-heart { width: 74px; height: 74px; border-radius: 50%; background: #FFFFFF; box-shadow: 0 10px 26px rgba(25,118,210,.30); display: flex; align-items: center; justify-content: center; font-size: 36px; margin-bottom: 18px; }
.phone-screen p { color: var(--primary-dark); font-size: 15px; font-weight: 600; line-height: 1.7; }
.sec-head { text-align: center; color: var(--primary-dark); font-size: 30px; margin: 40px 0 8px; }
.sec-sub { text-align: center; color: var(--text-muted); font-size: 15px; margin-bottom: 26px; }
.feature { transition: transform .14s ease, box-shadow .14s ease, border-color .14s ease; }
.feature .ic { font-size: 38px; width: 64px; height: 64px; display: flex; align-items: center; justify-content: center; background: var(--primary-light); border-radius: 18px; margin-bottom: 12px; }
.feature h3 { font-size: 16.5px; margin: 10px 0 6px; color: var(--primary); }
.feature p { font-size: 14px; color: var(--text-body); line-height: 1.7; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
a.feature.serv:hover { transform: translateY(-4px); box-shadow: 0 14px 30px rgba(25,118,210,.14); border-color: var(--primary); }
#more-services { display: none; }
.more-btn { display: block; margin: 0 auto 24px; background: var(--bg-card); color: var(--primary); border: 1.5px solid var(--primary); font-weight: 700; padding: 12px 30px; border-radius: 999px; font-size: 15px; cursor: pointer; font-family: inherit; }
.more-btn:hover { background: var(--primary-light); }
.how-wrap { display: flex; align-items: center; justify-content: center; gap: 0; flex-wrap: wrap; margin-bottom: 30px; }
.how-step { background: var(--bg-card); border: 1px solid var(--border-card); border-radius: 18px; padding: 26px 22px; text-align: center; flex: 1; min-width: 210px; max-width: 260px; box-shadow: 0 4px 16px rgba(25,118,210,.06); }
.how-step .n { width: 44px; height: 44px; border-radius: 50%; background: linear-gradient(135deg, var(--primary), #1565C0); color: #fff; display: inline-flex; align-items: center; justify-content: center; font-weight: 800; font-size: 17px; margin-bottom: 12px; }
.how-step h3 { font-size: 16.5px; color: var(--primary-dark); margin-bottom: 6px; }
.how-step p { font-size: 13.5px; color: var(--text-muted); line-height: 1.7; }
.how-arrow { font-size: 26px; color: var(--primary); padding: 0 10px; font-weight: 800; }
html[dir="ltr"] .how-arrow.ar { display: none; }
html[dir="rtl"] .how-arrow.en { display: none; }
.how-tl { position: relative; max-width: 720px; margin: 0 auto 32px; padding: 0; list-style: none; }
.how-tl::before { content: ''; position: absolute; left: 28px; top: 0; bottom: 0; width: 3px; background: linear-gradient(to bottom, var(--primary), var(--primary-light)); border-radius: 3px; }
html[dir="ltr"] .how-tl::before { left: 28px; }
html[dir="rtl"] .how-tl::before { left: auto; right: 28px; }
.how-tl-item { position: relative; display: flex; align-items: flex-start; gap: 16px; padding-bottom: 28px; }
html[dir="rtl"] .how-tl-item { flex-direction: row-reverse; text-align: right; }
.how-tl-item:last-child { padding-bottom: 0; }
.how-tl-dot { position: relative; z-index: 2; flex: 0 0 56px; height: 56px; border-radius: 50%; background: linear-gradient(135deg, var(--primary), #1565C0); color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 18px; box-shadow: 0 4px 14px rgba(25,118,210,.25); }
.how-tl-card { flex: 1; background: var(--bg-card); border: 1px solid var(--border-card); border-radius: 16px; padding: 20px 22px; box-shadow: 0 4px 16px rgba(25,118,210,.06); transition: transform .15s ease, box-shadow .15s ease; }
.how-tl-card:hover { transform: translateY(-2px); box-shadow: 0 10px 24px rgba(25,118,210,.10); }
.how-tl-card h3 { font-size: 16px; color: var(--primary-dark); margin: 0 0 6px; font-weight: 800; }
.how-tl-card p { font-size: 14px; color: var(--text-muted); line-height: 1.7; margin: 0; }
@media (max-width: 480px) {
  .how-tl::before { left: 18px; }
  html[dir="rtl"] .how-tl::before { left: auto; right: 18px; }
  .how-tl-dot { flex: 0 0 38px; height: 38px; font-size: 14px; }
  .how-tl-item { gap: 12px; padding-bottom: 20px; }
  .how-tl-card { padding: 16px; }
  .how-tl-card h3 { font-size: 15px; }
  .how-tl-card p { font-size: 13px; }
}
.warn2 { background: #FFF8E7; border: 1px solid #F5D78E; color: #7A5B00; border-radius: 16px; padding: 16px 20px; font-size: 14.5px; line-height: 1.9; margin-bottom: 22px; display: flex; gap: 10px; align-items: flex-start; }
.warn2 .w-ic { font-size: 22px; }
.ab-sub { color: var(--primary); font-size: 17px; margin: 0 0 10px; }
.src-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.src-chips span { background: var(--primary-light); color: var(--primary); font-weight: 800; font-size: 13px; padding: 6px 14px; border-radius: 999px; }
.bubble.q { background: var(--primary-light); border: 1px solid var(--border-card); color: var(--primary-dark); font-weight: 700; font-size: 16px; border-radius: 14px 14px 14px 4px; padding: 13px 16px; }
.bubble.q.start { max-width: 100%; background: linear-gradient(160deg, var(--primary-light) 0%, #FFFFFF 90%); border: 1.5px solid var(--border-card); }
.chat-start { text-align: center; padding: 12px 10px 8px; }
.chat-start .cs-logo { font-size: 46px; margin-bottom: 8px; }
.chat-start .cs-title { font-size: 21px; font-weight: 800; color: var(--primary-dark); margin-bottom: 4px; }
.chat-start .cs-sub { font-size: 15px; font-weight: 700; color: var(--primary); margin-bottom: 10px; }
.chat-start .cs-desc { font-size: 13.5px; color: var(--text-body); line-height: 1.9; }
.start-btn { display: block; width: 100%; margin-top: 10px; background: linear-gradient(135deg, var(--primary), #1565C0); color: #FFFFFF; border: none; border-radius: 999px; padding: 14px 20px; font-size: 16px; font-weight: 800; cursor: pointer; font-family: inherit; box-shadow: 0 10px 24px rgba(25,118,210,.30); }
.start-btn:hover { transform: translateY(-1px); box-shadow: 0 14px 30px rgba(25,118,210,.38); }
.start-btn.is-next { order: -1; margin: 0 0 6px; position: sticky; top: 6px; z-index: 3; }
.start-btn:disabled { cursor: not-allowed; opacity: .55; box-shadow: none; transform: none; }
.res-card { background: linear-gradient(180deg, var(--primary-light) 0%, #FFFFFF 70%); border: 1.5px solid var(--border-card); border-radius: 20px; padding: 22px 20px; }
.res-title { text-align: center; font-size: 20px; font-weight: 800; color: var(--primary-dark); margin-bottom: 12px; }
.res-person { text-align: center; background: var(--primary-light); border: 1px solid var(--border-card); color: var(--primary); font-weight: 800; font-size: 13px; border-radius: 999px; padding: 6px 14px; display: inline-block; margin-bottom: 10px; }
.res-urg { text-align: center; margin: 6px 0 10px; }
.res-triage { display: block; margin: 4px auto 4px; width: fit-content; font-size: 16px; font-weight: 800; padding: 8px 22px; border-radius: 999px; background: var(--primary); color: #fff; }
.triage-why { margin: 10px 0 4px; padding: 10px 12px; background: var(--primary-light); border: 1px solid var(--border-card); border-radius: 12px; font-size: 13.5px; color: var(--primary-dark); line-height: 1.8; }
.res-sim-toggle { text-align: center; margin: 10px 0 4px; }
.sim-box { padding: 14px; background: #FFF7ED; border: 1px solid #FDBA74; border-radius: 14px; font-size: 15px; color: #7C2D12; line-height: 1.9; }
.pill2 { display: inline-block; font-size: 20px; font-weight: 800; padding: 10px 26px; border-radius: 999px; }
.pill2.low { background: #dcfce7; color: #166534; }
.pill2.med { background: #fef3c7; color: #92400e; }
.pill2.hi { background: #fee2e2; color: #b91c1c; }
.res-disc { text-align: center; font-size: 12.5px; color: #7A5B00; margin-bottom: 12px; padding: 8px 10px; background: #FFF8E7; border: 1px solid #F5D78E; border-radius: 10px; line-height: 1.7; }
.res-note { font-style: italic; color: var(--text-body); line-height: 1.9; margin-bottom: 10px; font-size: 14px; }
.rc-title { font-weight: 800; color: var(--primary-dark); margin: 14px 0 6px; font-size: 15.5px; }
@media (max-width: 980px) {
  .hh { flex-direction: column; padding: 30px 22px; }
  .hh-r { min-height: 280px; }
}
@media (max-width: 600px) {
  .hh { padding: 24px 18px; border-radius: 24px; gap: 18px; }
  .hh-btns { width: 100%; }
  .hh-btns .btn { flex: 1; text-align: center; }
  .hh-r { min-height: 200px; transform: scale(.82); margin: -14px 0; }
}
@media (max-width: 400px) {
  .hh-r { display: none; }
}
/* ---- Smart Account System CSS ---- */
.auth-wrap { min-height: 86vh; display: flex; align-items: center; justify-content: center; padding: 26px 18px; }
.auth-card { background: var(--bg-card); border: 1px solid var(--border-card); border-radius: 22px; box-shadow: 0 10px 30px rgba(25,118,210,.08); padding: 42px 30px; max-width: 460px; width: 100%; text-align: center; animation: fadeIn .5s ease both; }
.auth-card .auth-icon { font-size: 48px; margin-bottom: 12px; }
.auth-card h1 { font-size: 26px; color: var(--primary-dark); margin: 0 0 6px; }
.auth-card .auth-sub { color: var(--text-muted); font-size: 15px; margin-bottom: 24px; }
.auth-card .auth-field { text-align: right; margin-bottom: 14px; }
.auth-card .auth-field label { display: block; font-size: 14px; font-weight: 700; color: var(--primary-dark); margin-bottom: 4px; }
.auth-card .auth-field input { width: 100%; border: 1.5px solid var(--border-card); border-radius: 12px; padding: 12px 14px; font-size: 15px; font-family: inherit; background: var(--primary-light); color: var(--text-body); transition: border-color .2s; }
.auth-card .auth-field input:focus { outline: none; border-color: var(--primary); background: var(--bg-card); }
.auth-card .auth-btn { width: 100%; background: var(--primary); color: #fff; border: none; border-radius: 12px; padding: 14px; font-size: 16px; font-weight: 700; cursor: pointer; font-family: inherit; transition: background .2s, transform .1s; }
.auth-card .auth-btn:hover { background: var(--primary-dark); transform: translateY(-1px); }
.auth-card .auth-link { margin-top: 16px; font-size: 14px; color: var(--text-muted); }
.auth-card .auth-link a { color: var(--primary); font-weight: 700; text-decoration: none; }
.auth-card .auth-link a:hover { text-decoration: underline; }
.auth-card .auth-error { background: #FEF2F2; border: 1px solid #FECACA; color: #991B1B; border-radius: 10px; padding: 10px 14px; font-size: 14px; font-weight: 600; margin-bottom: 14px; display: none; }
.auth-card .auth-error.show { display: block; }
/* Profile page */
.ss-profile-card { background: var(--bg-card); border: 1px solid var(--border-card); border-radius: 18px; padding: 24px; margin-bottom: 18px; box-shadow: var(--shadow-card); }
.ss-profile-card h2 { color: var(--primary); font-size: 18px; margin-bottom: 14px; display: flex; align-items: center; gap: 8px; }
.ss-profile-card .ss-field { display: flex; align-items: center; gap: 12px; background: var(--primary-light); border: 1px solid var(--border-card); border-radius: 14px; padding: 14px; margin-bottom: 10px; }
.ss-profile-card .ss-field .ss-f-icon { font-size: 22px; width: 42px; height: 42px; min-width: 42px; border-radius: 12px; background: var(--primary-light); display: flex; align-items: center; justify-content: center; }
.ss-profile-card .ss-field label { margin: 0 0 2px; color: var(--primary-dark); font-size: 13px; font-weight: 700; }
.ss-profile-card .ss-field input, .ss-profile-card .ss-field select, .ss-profile-card .ss-field textarea { background: var(--bg-card); border: 1px solid var(--border-card); border-radius: 10px; padding: 10px 12px; font-size: 14px; font-family: inherit; width: 100%; }
.ss-profile-card .ss-field textarea { min-height: 60px; resize: vertical; }
.ss-profile-card .ss-field input:focus, .ss-profile-card .ss-field select:focus, .ss-profile-card .ss-field textarea:focus { outline: none; border-color: var(--primary); }
.ss-grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
@media (max-width: 640px) { .ss-grid2 { grid-template-columns: 1fr; } }
.ss-btn-row { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 16px; }
.ss-btn-primary { background: var(--primary); color: #fff; border: none; border-radius: 12px; padding: 12px 24px; font-size: 15px; font-weight: 700; cursor: pointer; font-family: inherit; transition: background .2s; }
.ss-btn-primary:hover { background: var(--primary-dark); }
.ss-btn-danger { background: var(--bg-card); color: #dc2626; border: 1.5px solid #fca5a5; border-radius: 12px; padding: 12px 24px; font-size: 14px; font-weight: 700; cursor: pointer; font-family: inherit; transition: background .2s; }
.ss-btn-danger:hover { background: #fee2e2; }
.ss-msg { text-align: center; font-weight: 700; color: #16a34a; font-size: 14px; margin-top: 10px; }
.ss-msg.error { color: #dc2626; }
/* Privacy toggles */
.ss-toggle-row { display: flex; align-items: center; justify-content: space-between; background: var(--primary-light); border: 1px solid var(--border-card); border-radius: 14px; padding: 14px 16px; margin-bottom: 10px; }
.ss-toggle-row .ss-t-label { font-size: 14px; font-weight: 600; color: var(--text-body); flex: 1; }
.ss-toggle { position: relative; width: 48px; height: 26px; flex: 0 0 auto; }
.ss-toggle input { opacity: 0; width: 0; height: 0; }
.ss-toggle .ss-slider { position: absolute; inset: 0; background: var(--primary-pale); border-radius: 999px; cursor: pointer; transition: background .25s; }
.ss-toggle .ss-slider::before { content: ''; position: absolute; width: 20px; height: 20px; left: 3px; bottom: 3px; background: #fff; border-radius: 50%; transition: transform .25s; }
.ss-toggle input:checked + .ss-slider { background: var(--primary); }
.ss-toggle input:checked + .ss-slider::before { transform: translateX(22px); }
/* Smart context modal */
.ss-modal-overlay { position: fixed; inset: 0; z-index: 9998; display: none; align-items: center; justify-content: center; background: rgba(15,23,42,.5); backdrop-filter: blur(3px); padding: 18px; }
.ss-modal-overlay.open { display: flex; }
.ss-modal { background: var(--bg-card); border-radius: 22px; max-width: 440px; width: 100%; padding: 30px 26px; text-align: center; box-shadow: 0 24px 60px rgba(15,23,42,.25); animation: fadeIn .35s ease; }
.ss-modal h3 { font-size: 20px; color: var(--primary-dark); margin-bottom: 8px; }
.ss-modal p { font-size: 14px; color: var(--text-body); line-height: 1.7; margin-bottom: 14px; }
.ss-modal .ss-modal-list { text-align: start; background: var(--primary-light); border: 1px solid var(--border-card); border-radius: 12px; padding: 12px 14px; margin-bottom: 18px; font-size: 13.5px; color: var(--text-body); line-height: 1.8; }
.ss-modal .ss-modal-list b { color: var(--primary); }
.ss-modal .ss-modal-btns { display: flex; flex-direction: column; gap: 8px; }
.ss-modal .ss-modal-btn { border: none; border-radius: 12px; padding: 13px; font-size: 15px; font-weight: 700; cursor: pointer; font-family: inherit; transition: background .2s, transform .1s; }
.ss-modal .ss-modal-btn:hover { transform: translateY(-1px); }
.ss-modal .ss-modal-btn.primary { background: var(--primary); color: #fff; }
.ss-modal .ss-modal-btn.primary:hover { background: var(--primary-dark); }
.ss-modal .ss-modal-btn.secondary { background: var(--primary-light); color: var(--text-body); border: 1px solid var(--border-card); }
.ss-modal .ss-modal-btn.secondary:hover { background: var(--primary-pale); }
.ss-modal .ss-modal-btn.tertiary { background: transparent; color: var(--text-muted); }
/* Account gate used for private, cross-device features. */
.auth-gate-card { border: 1.5px solid var(--border-card); border-radius: 20px; padding: clamp(22px, 4vw, 34px); text-align: center; background: linear-gradient(145deg, var(--primary-light), var(--bg-card)); box-shadow: var(--shadow-card); }
.auth-gate-card .gate-icon { width: 64px; height: 64px; margin: 0 auto 12px; display: grid; place-items: center; border-radius: 18px; background: var(--bg-card); font-size: 30px; box-shadow: 0 8px 22px rgba(25,118,210,.12); }
.auth-gate-card h3 { color: var(--primary-dark); font-size: clamp(18px, 3vw, 22px); margin-bottom: 6px; }
.auth-gate-card p { color: var(--text-body); font-size: 14px; line-height: 1.8; max-width: 540px; margin: 0 auto; }
.auth-gate-actions { display: flex; justify-content: center; gap: 10px; flex-wrap: wrap; margin-top: 18px; }
.auth-gate-actions a { min-height: 46px; display: inline-flex; align-items: center; justify-content: center; padding: 11px 22px; border-radius: 12px; font-weight: 800; }
.auth-gate-actions .gate-login { background: var(--primary); color: #fff; }
.auth-gate-actions .gate-register { background: var(--bg-card); color: var(--primary); border: 1.5px solid var(--primary); }
.auth-only.is-locked { display: none !important; }

/* Responsive safety net shared by every page. */
@media (max-width: 1500px) {
  .nav { display: none; }
  .ss-mobile-head { display: flex; }
  .ss-bnav { display: flex; justify-content: space-evenly; align-items: center; }
  .ss-bnav a { flex: 0 1 170px; }
  .container { padding-bottom: calc(var(--bnav-h) + var(--safe-bottom) + 80px); }
  .asst-fab { bottom: calc(var(--bnav-h) + var(--safe-bottom) + 12px); left: 12px; width: 54px; height: 54px; padding: 0; justify-content: center; }
  [dir="rtl"] .asst-fab { left: 12px; right: auto; }
  .asst-fab .asst-fab-lb { display: none; }
  .asst-panel { left: 12px; right: 12px; bottom: calc(var(--bnav-h) + var(--safe-bottom) + 76px); width: auto; height: min(72dvh, 600px); }
  [dir="rtl"] .asst-panel { left: 12px; right: 12px; }
}
@media (max-width: 900px) {
  .hp-overview { grid-template-columns: 1fr; }
  .hp-stats, .hp-quick-links, .dash-stats { grid-template-columns: repeat(2, minmax(0,1fr)); }
  .chat-wrap { height: calc(100dvh - var(--bnav-h) - var(--safe-bottom) - 100px); min-height: 520px; max-height: 780px; }
  .how-arrow { display: none !important; }
  .how-wrap { gap: 12px; align-items: stretch; }
  .how-step { flex: 1 1 calc(50% - 12px); max-width: none; min-width: 220px; }
}
@media (max-width: 640px) {
  .container { padding: 14px 12px; padding-bottom: calc(var(--bnav-h) + var(--safe-bottom) + 24px); }
  .card, .ss-profile-card, .fam-form { padding: 16px; border-radius: 16px; margin-bottom: 14px; }
  .hero { padding: 30px 18px; border-radius: 18px; }
  .hero h1 { font-size: clamp(27px, 9vw, 34px); }
  .grid2, .ss-grid2, .pr-grid { grid-template-columns: 1fr; gap: 10px; }
  input.inp, select.inp, textarea.inp, .card input, .card select, .auth-card .auth-field input { min-height: 48px; font-size: 16px; }
  .btn, .ss-btn-primary, .ss-btn-danger { min-height: 46px; }
  .ss-btn-row > .btn, .ss-btn-row > .ss-btn-primary, .ss-btn-row > .ss-btn-danger { flex: 1 1 100%; justify-content: center; text-align: center; }
  .drop { padding: 26px 14px; }
  table.tbl { display: block; width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; white-space: nowrap; }
  body.ss-chat-page { height: 100dvh; overflow: hidden; overscroll-behavior: none; }
  body.ss-chat-page .container { height: calc(100dvh - 62px - var(--safe-top) - var(--bnav-h) - var(--safe-bottom)); padding: 6px 8px; overflow: hidden; }
  body.ss-chat-page .chat-wrap { height: 100%; min-height: 0; max-height: none; margin: 0; border-radius: 16px; }
  body.ss-chat-page .container > .muted, body.ss-chat-page .blood-banner { display: none !important; }
  body.ss-chat-page .asst-fab, body.ss-chat-page .asst-panel { display: none !important; }
  .chat-options { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); max-height: 42%; overflow-y: auto; overscroll-behavior: contain; -webkit-overflow-scrolling: touch; padding: 10px; }
  .chat-options .opt { width: 100%; min-height: 48px; padding: 9px 10px; border-radius: 14px; line-height: 1.45; }
  .chat-options .start-btn, .chat-options #relBlock { grid-column: 1/-1; }
  .chat-head { flex-wrap: wrap; padding: 10px 12px; gap: 6px; }
  .chat-head-toggles { display: flex; flex-wrap: nowrap; gap: 6px; margin-inline-start: auto; }
  .chat-head .spk-btn { margin: 0; padding: 6px 8px; font-size: 10.5px; }
  #profileSwitcher { order: 10; flex: 1 1 100%; width: 100%; margin: 0 !important; }
  #famSelect { width: 100%; max-width: none !important; min-height: 42px; }
  .chat-body { padding: 12px; }
  .bubble { max-width: 94%; font-size: 14px; }
  .chat-input { padding: 10px; gap: 6px; }
  .chat-input input { min-height: 46px; font-size: 16px; }
  .chat-input button { min-width: 44px; min-height: 46px; padding: 10px 12px; }
  .auth-wrap { min-height: auto; padding: 10px 0 24px; }
  .auth-card { padding: 28px 18px; border-radius: 18px; }
  .footer { padding: 30px 16px calc(var(--bnav-h) + var(--safe-bottom) + 20px); }
  .auth-gate-actions a { flex: 1 1 150px; }
  .hp-account-hero { padding: 19px 16px; border-radius: 18px; }
  .hp-account-head { align-items: flex-start; }
  .hp-avatar { width: 52px; height: 52px; flex-basis: 52px; border-radius: 16px; font-size: 26px; }
  .hp-account-name { font-size: 18px; }
  .hp-secure { display: none; }
  .hp-stats { grid-template-columns: repeat(2, minmax(0,1fr)); }
  .hp-overview { grid-template-columns: 1fr; }
  .hp-quick-links { grid-template-columns: repeat(2, minmax(0,1fr)); }
  .hp-account-email { overflow-wrap: anywhere; word-break: break-all; }
  .how-step { flex-basis: 100%; min-width: 0; }
  .ss-modal-overlay, .expl-bg, .asst-modal-bg { padding: 10px; }
  .ss-modal, .expl-modal, .asst-modal { padding: 18px 15px; border-radius: 18px; }
}
@media (max-width: 480px) {
  .ss-mobile-head { gap: 8px; padding-inline: 10px; }
  .ss-mobile-account { max-width: 112px; padding-inline: 9px; }
  .ss-mobile-lang { min-width: 42px; padding-inline: 8px; }
  .quick-grid { grid-template-columns: 1fr !important; }
  .care-grid { grid-template-columns: repeat(2, minmax(0,1fr)) !important; }
  .chat-head .avatar { width: 36px; height: 36px; }
  .chat-head h3 { font-size: 14px; }
  .chat-head p { font-size: 10.5px; }
  .bubble { max-width: 100%; }
  .opt { padding: 9px 13px; font-size: 13px; }
  .dash-stats { grid-template-columns: 1fr; }
  .pwa-install-copy { font-size: 12px; }
}
@media (max-width: 360px) {
  .container { padding-inline: 10px; }
  .quick-grid, .care-grid, .tools-grid { grid-template-columns: 1fr !important; }
  .ss-bnav a { min-width: 48px; font-size: 9px; }
  .ss-mobile-account span:last-child { display: none; }
  .ss-mobile-account { width: 42px; padding: 7px; }
  .chat-options { grid-template-columns: 1fr; }
  .chat-options .start-btn, .chat-options #relBlock { grid-column: 1; }
}
@media (orientation: landscape) and (max-height: 560px) {
  .chat-wrap { height: calc(100dvh - var(--bnav-h) - var(--safe-bottom) - 16px); min-height: 440px; }
  .asst-panel { height: calc(100dvh - var(--bnav-h) - 32px); }
}
/* Reduce motion */
@media (prefers-reduced-motion: reduce) {
  .auth-card, .ss-modal, .ss-profile-card { animation: none !important; transition: none !important; }
}
"""

PAGE_FRAME = """
<!DOCTYPE html>
<html lang="__LANG__" dir="__DIR__">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="icon" type="image/svg+xml" href="/brand-icon.svg">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="SymptoSense">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap" rel="stylesheet">
<title>__TITLE__</title>
<meta name="description" content="__DESC__">
<meta name="keywords" content="__KEYWORDS__">
<meta name="robots" content="index, follow">
__GSC_TAG__
<link rel="canonical" href="__CANONICAL__">
<meta property="og:title" content="__TITLE__">
<meta property="og:description" content="__DESC__">
<meta property="og:image" content="__OG_IMAGE__">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="SymptoSense — Understand your symptoms. Know your next step.">
<meta property="og:url" content="__CANONICAL__">
<meta property="og:type" content="website">
<meta property="og:site_name" content="SymptoSense">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="__TITLE__">
<meta name="twitter:description" content="__DESC__">
<meta name="twitter:image" content="__OG_IMAGE__">
<meta name="theme-color" content="#1976D2">
<style>__CSS__</style>
<style>
.asst-fab { position: fixed; bottom: 22px; left: 22px; z-index: 999; display: flex; align-items: center; gap: 9px; background: linear-gradient(135deg, #1976D2, var(--primary-dark)); color: #FFF; font-family: inherit; font-size: 16.5px; font-weight: 800; padding: 15px 26px; border-radius: 999px; cursor: pointer; border: 2px solid rgba(255,255,255,.35); box-shadow: 0 12px 30px rgba(25,118,210,.35); }
[dir="rtl"] .asst-fab { left: 22px; right: auto; }
.asst-fab .asst-fab-ic { font-size: 24px; line-height: 1; }
.asst-fab .asst-fab-lb { letter-spacing: .2px; }
.asst-fab.pulse { animation: asstPulse 2.6s infinite; }
.asst-fab:hover { transform: translateY(-2px); box-shadow: 0 16px 38px rgba(25,118,210,.42); }
@keyframes asstPulse { 0%,100% { box-shadow: 0 12px 30px rgba(25,118,210,.35); } 50% { box-shadow: 0 12px 42px rgba(25,118,210,.55); } }
.asst-panel { position: fixed; bottom: 96px; left: 22px; z-index: 999; width: 400px; max-width: calc(100vw - 24px); height: min(78vh, 600px); display: none; flex-direction: column; background: var(--bg-card); border: 1px solid var(--border-card); border-radius: 22px; box-shadow: 0 24px 70px rgba(25,118,210,.26); overflow: hidden; }
[dir="rtl"] .asst-panel { left: 22px; right: auto; }
.asst-panel.open { display: flex; }
/* Lock the document behind the assistant. Only the assistant body may scroll. */
html.ss-assistant-open { overflow: hidden !important; overscroll-behavior: none; }
body.ss-assistant-open { overflow: hidden !important; overscroll-behavior: none; }
body.ss-assistant-open::after { content: ""; position: fixed; inset: 0; z-index: 998; background: rgba(18,59,112,.14); pointer-events: auto; }
.asst-panel, .asst-fab { isolation: isolate; }
.asst-body { overscroll-behavior: contain; -webkit-overflow-scrolling: touch; }
.asst-head { background: linear-gradient(120deg, var(--primary-dark), #1976D2); color: #FFFFFF; padding: 14px 16px; display: flex; align-items: center; gap: 8px; flex: 0 0 auto; }
.asst-head .asst-back { background: rgba(255,255,255,.16); color: #FFF; border: none; border-radius: 50%; width: 30px; height: 30px; font-size: 15px; cursor: pointer; flex: 0 0 auto; }
.asst-head-tx { flex: 1; min-width: 0; }
.asst-head-tx b { font-size: 15px; display: block; }
.asst-sub { font-size: 12px; opacity: .85; margin-top: 2px; }
.asst-head > button:last-child { background: rgba(255,255,255,.16); color: #FFF; border: none; border-radius: 50%; width: 30px; height: 30px; font-size: 14px; cursor: pointer; flex: 0 0 auto; }
.asst-body { flex: 1; overflow-y: auto; padding: 14px; background: var(--bg-page); }
.asst-msg { border-radius: 14px; padding: 10px 14px; margin: 6px 0; font-size: 14px; line-height: 1.7; max-width: 94%; word-break: break-word; }
.asst-user { background: #1976D2; color: #FFF; margin-left: auto; }
[dir="rtl"] .asst-user { margin-left: 0; margin-right: auto; }
.asst-bot { background: var(--bg-card); border: 1px solid var(--border-card); color: var(--text-body); }
.asst-opts { display: grid; gap: 10px; margin: 10px 0 6px; }
.asst-opt { display: flex; align-items: center; gap: 12px; text-align: start; background: var(--bg-card); border: 1.5px solid var(--border-card); border-radius: 16px; padding: 12px 14px; cursor: pointer; font-family: inherit; box-shadow: 0 3px 12px rgba(25,118,210,.05); transition: transform .14s ease, box-shadow .14s ease, border-color .14s ease; }
.asst-opt:hover { transform: translateY(-2px); border-color: #1976D2; box-shadow: 0 8px 20px rgba(25,118,210,.14); }
.asst-opt .ao-ic { font-size: 24px; flex: 0 0 auto; }
.asst-opt .ao-tx { min-width: 0; }
.asst-opt .ao-t { display: block; font-size: 14.5px; font-weight: 800; color: var(--primary-dark); }
.asst-opt .ao-d { display: block; font-size: 12.5px; color: var(--text-muted); line-height: 1.5; margin-top: 2px; }
.asst-qs { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.asst-chip { border: 1px solid var(--border-card); background: var(--bg-card); color: var(--primary-dark); border-radius: 999px; padding: 6px 12px; font-size: 12px; font-weight: 700; cursor: pointer; font-family: inherit; }
.asst-chip:hover { background: var(--primary-light); }
.asst-emerg { background: #FEE2E2; border: 1px solid #FCA5A5; color: #7F1D1D; border-radius: 12px; padding: 10px 12px; margin: 8px 0; font-size: 13px; line-height: 1.7; }
.asst-emerg a { color: #B91C1C; font-weight: 800; }
.asst-foot { display: flex; gap: 8px; padding: 10px 12px; border-top: 1px solid var(--border-card); background: var(--bg-card); flex: 0 0 auto; }
.asst-inp { flex: 1; border: 1px solid var(--border-card); border-radius: 12px; padding: 10px 14px; font-size: 14px; font-family: inherit; }
.asst-foot button { border: none; border-radius: 12px; background: #1976D2; color: #FFF; padding: 0 16px; font-size: 15px; cursor: pointer; }
.asst-mh-btn { background: var(--primary-light) !important; color: var(--primary-dark) !important; font-size: 12px !important; white-space: nowrap; padding: 0 10px !important; }
.asst-disc { font-size: 11px; color: var(--text-muted); text-align: center; padding: 7px; background: var(--primary-light); border-top: 1px dashed var(--border-card); flex: 0 0 auto; }
.asst-panel.asst-mh { background: var(--bg-card); border-color: var(--border-card); }
.asst-panel.asst-mh .asst-head { background: linear-gradient(120deg, var(--primary-dark), var(--primary)); }
.asst-panel.asst-mh .asst-body { background: var(--bg-page); }
.asst-panel.asst-mh .asst-bot { background: var(--bg-card); border-color: var(--border-card); color: var(--text-body); font-size: 15px; }
.asst-panel.asst-mh .asst-user { background: var(--primary); }
.asst-panel.asst-mh .asst-opt { border-color: var(--border-card); box-shadow: none; }
.asst-panel.asst-mh .asst-opt:hover { border-color: var(--primary); box-shadow: 0 8px 20px rgba(25,118,210,.14); }
.asst-panel.asst-mh .asst-opt .ao-t { color: var(--primary-dark); }
.asst-panel.asst-mh .asst-chip { border-color: var(--border-card); color: var(--primary-dark); background: var(--bg-card); }
.asst-panel.asst-mh .asst-chip:hover { background: var(--primary-light); }
.asst-panel.asst-mh .asst-foot { background: var(--bg-card); }
.asst-panel.asst-mh .asst-foot button { background: var(--primary); }
.asst-panel.night-calm { background: #0F1729; border-color: #1E293B; }
.asst-panel.night-calm .asst-head { background: linear-gradient(120deg, #123B70, #1976D2); }
.asst-panel.night-calm .asst-body { background: #0F1729; }
.asst-panel.night-calm .asst-bot { background: #123B70; border-color: #1976D2; color: #EAF4FF; font-size: 15px; }
.asst-panel.night-calm .asst-user { background: #1976D2; }
.asst-panel.night-calm .asst-opt { border-color: #1976D2; background: #123B70; color: #B8D8F8; }
.asst-panel.night-calm .asst-opt:hover { border-color: #64B5F6; background: #1976D2; }
.asst-panel.night-calm .asst-opt .ao-t { color: #EAF4FF; }
.asst-panel.night-calm .asst-chip { border-color: #1976D2; color: #B8D8F8; background: #123B70; }
.asst-panel.night-calm .asst-chip:hover { background: #1976D2; }
.asst-panel.night-calm .asst-foot { background: #0F1729; }
.asst-panel.night-calm .asst-foot button { background: #1976D2; }
.asst-panel.night-calm .asst-inp { background: #123B70; border-color: #1976D2; color: #EAF4FF; }
.asst-breath { text-align: center; margin: 12px auto; width: 118px; height: 118px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 800; color: #fff; font-size: 15px; }
.asst-br-0 { background: radial-gradient(circle, #64B5F6, #1976D2); animation: brIn 4s ease-in-out infinite; }
.asst-br-1 { background: radial-gradient(circle, #1976D2, #1565C0); animation: brHold 7s ease-in-out infinite; }
.asst-br-2 { background: radial-gradient(circle, #123B70, #0D47A1); animation: brOut 8s ease-in-out infinite; }
@keyframes brIn { 0% { transform: scale(.72); } 100% { transform: scale(1.05); } }
@keyframes brHold { 0%,100% { transform: scale(1.05); } 50% { transform: scale(1.08); } }
@keyframes brOut { 0% { transform: scale(1.05); } 100% { transform: scale(.72); } }
.asst-panel.no-anim *, .asst-panel.no-anim *::before, .asst-panel.no-anim *::after { animation: none !important; transition: none !important; }
@media (prefers-reduced-motion: reduce) { .asst-fab.pulse, .asst-br-0, .asst-br-1, .asst-br-2, .ss-bnav a, .ss-completion .bar-fill-green, .welcome-card { animation: none !important; transition: none !important; } }
.asst-fb { display: flex; gap: 6px; align-items: center; margin: 2px 0 6px; }
.asst-fb-btn { border: 1px solid var(--border-card); background: var(--bg-card); border-radius: 999px; padding: 4px 12px; font-size: 13px; cursor: pointer; font-family: inherit; }
.asst-fb-btn:hover { background: var(--primary-light); border-color: var(--border-card); }
.asst-fb-ok { font-size: 12px; color: var(--primary); font-weight: 700; }
@media (max-width: 560px) {
  .asst-panel { bottom: calc(var(--bnav-h) + var(--safe-bottom)); left: 0; right: 0; width: 100%; max-width: none; height: min(76dvh, 620px); border-radius: 22px 22px 0 0; }
  [dir="rtl"] .asst-panel { left: 0; right: 0; }
  .asst-fab { bottom: calc(var(--bnav-h) + var(--safe-bottom) + 14px); left: auto; right: 14px; width: 52px; height: 52px; padding: 0; border-radius: 50%; justify-content: center; }
  [dir="rtl"] .asst-fab { left: auto; right: 14px; }
  .asst-fab .asst-fab-ic { font-size: 22px; }
  .asst-fab .asst-fab-lb { display: none; }
}
.expl-bg { position: fixed; inset: 0; z-index: 1001; background: rgba(15,23,42,.55); display: none; align-items: center; justify-content: center; padding: 18px; }
.expl-bg.open { display: flex; }
.expl-modal { background: var(--bg-card); border-radius: 20px; max-width: 560px; width: 100%; max-height: 86vh; overflow-y: auto; padding: 22px; box-shadow: 0 30px 80px rgba(0,0,0,.35); }
.expl-modal .ex-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 4px; }
.expl-modal .ex-title { font-size: 19px; font-weight: 800; color: var(--primary-dark); }
.expl-modal .ex-close { border: none; background: var(--primary-light); color: var(--text-body); border-radius: 50%; width: 32px; height: 32px; font-size: 14px; cursor: pointer; }
.ex-levels { display: flex; gap: 8px; margin: 14px 0; flex-wrap: wrap; }
.ex-level { flex: 1; min-width: 130px; border: 2px solid var(--border-card); background: var(--bg-card); border-radius: 14px; padding: 12px; text-align: center; cursor: pointer; font-family: inherit; transition: all .2s; }
.ex-level.on { border-color: var(--primary); background: var(--primary-light); box-shadow: 0 6px 16px rgba(25,118,210,.14); }
.ex-level .lv-ic { font-size: 22px; }
.ex-level .lv-t { font-size: 13px; font-weight: 800; color: var(--primary-dark); margin-top: 4px; }
.ex-explain { background: var(--primary-light); border: 1px solid var(--border-card); border-radius: 12px; padding: 14px; font-size: 14.5px; line-height: 1.9; color: var(--text-body); min-height: 90px; }
.ex-assist-row { margin-top: 14px; text-align: center; }
.asst-modal-bg { position: fixed; inset: 0; z-index: 1002; background: rgba(15,23,42,.55); display: none; align-items: center; justify-content: center; padding: 18px; }
.asst-modal-bg.open { display: flex; }
.asst-modal { background: var(--bg-card); border-radius: 18px; max-width: 480px; width: 100%; padding: 20px; box-shadow: 0 30px 80px rgba(0,0,0,.35); }
.asst-modal-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 12px; color: var(--primary-dark); font-size: 16px; }
.asst-modal-head button { border: none; background: var(--primary-light); color: var(--text-body); border-radius: 50%; width: 30px; height: 30px; font-size: 13px; cursor: pointer; }
.asst-reasons { display: flex; flex-direction: column; gap: 8px; }
.asst-reason { border: 1px solid var(--border-card); background: var(--primary-light); border-radius: 12px; padding: 11px 14px; font-size: 14px; cursor: pointer; font-family: inherit; text-align: start; color: var(--text-body); }
.asst-reason:hover { border-color: var(--primary); background: var(--primary-light); color: var(--primary); }
.pwa-install { position: fixed; z-index: 1300; left: 50%; bottom: calc(var(--bnav-h) + var(--safe-bottom) + 14px); transform: translateX(-50%); width: min(520px, calc(100vw - 24px)); display: none; align-items: center; gap: 12px; padding: 14px; border-radius: 18px; background: #fff; color: #123B70; border: 1px solid #DCEBFA; box-shadow: 0 18px 48px rgba(18,59,112,.22); }
.pwa-install.show { display: flex; }
.pwa-install-icon { width: 48px; height: 48px; border-radius: 13px; flex: 0 0 auto; }
.pwa-install-copy { flex: 1; font-size: 13px; line-height: 1.6; font-weight: 700; }
.pwa-install-actions { display: flex; gap: 7px; flex-wrap: wrap; }
.pwa-install button { border: 0; border-radius: 10px; padding: 9px 12px; min-height: 40px; font-family: inherit; font-weight: 800; cursor: pointer; }
.pwa-install .pwa-primary { background: #1976D2; color: #fff; }
.pwa-install .pwa-later { background: #EAF4FF; color: #123B70; }
@media (min-width: 1501px) { .pwa-install { bottom: 20px; } }
@media (max-width: 480px) { .pwa-install { align-items: flex-start; } .pwa-install-actions { flex-direction: column; } }
</style>
</head>
<body class="__BODY_CLASS__">
<div class="pwa-install" id="pwaInstall" role="dialog" aria-live="polite" aria-label="Install SymptoSense">
  <img class="pwa-install-icon" src="/icons/icon-192.png" alt="">
  <div class="pwa-install-copy" id="pwaInstallText"></div>
  <div class="pwa-install-actions">
    <button class="pwa-primary" id="pwaInstallBtn" type="button" onclick="pwaInstallNow()"></button>
    <button class="pwa-later" id="pwaLaterBtn" type="button" onclick="pwaDismiss()"></button>
  </div>
</div>
<script>
function setLang(l) {
  document.cookie = 'lang=' + l + ';path=/;max-age=31536000;SameSite=Lax';
  try { localStorage.setItem('ss_lang', l); } catch(e) {}
  location.href = (l === 'ar') ? '/home' : '/home';
}
function toggleDD(ev) {
  ev.stopPropagation();
  const current = ev.currentTarget ? ev.currentTarget.closest('.dd') : null;
  const menu = current ? current.querySelector('.dd-menu') : null;
  if (!menu) return;
  const willOpen = !menu.classList.contains('open');
  document.querySelectorAll('.dd-menu.open').forEach(function(other) {
    other.classList.remove('open');
    const trigger = other.parentElement ? other.parentElement.querySelector('button[aria-haspopup="menu"]') : null;
    if (trigger) trigger.setAttribute('aria-expanded', 'false');
  });
  menu.classList.toggle('open', willOpen);
  ev.currentTarget.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
}
document.addEventListener('click', function(ev) {
  if (ev.target.closest('.dd')) return;
  document.querySelectorAll('.dd-menu.open').forEach(function(menu) { menu.classList.remove('open'); });
  document.querySelectorAll('button[aria-haspopup="menu"]').forEach(function(button) { button.setAttribute('aria-expanded', 'false'); });
});
document.addEventListener('keydown', function(ev) {
  if (ev.key !== 'Escape') return;
  document.querySelectorAll('.dd-menu.open').forEach(function(menu) { menu.classList.remove('open'); });
  document.querySelectorAll('button[aria-haspopup="menu"]').forEach(function(button) { button.setAttribute('aria-expanded', 'false'); });
});
(function(){
  var p = location.pathname;
  var bnav = document.getElementById('ssBnav');
  if (!bnav) return;
  var links = bnav.querySelectorAll('a');
  links.forEach(function(a){
    var h = a.getAttribute('href');
    if (h && p.indexOf(h) === 0 && h !== '#') a.classList.add('on');
    else if (h === '/home' && p === '/') a.classList.add('on');
  });
});
</script>
__NAV__
<div class="container">
__BODY__
</div>
__FOOTER__
<nav class="ss-bnav" id="ssBnav" aria-label="Main navigation">
  <a href="/home" class="bn-home" aria-label="Home"><span class="bn-icon">🏠</span><span>__BNAV_HOME__</span></a>
  <a href="/chat" class="bn-chat" aria-label="Symptom analysis"><span class="bn-icon">🩺</span><span>__BNAV_CHAT__</span></a>
  <a href="#" class="bn-psych" onclick="openAsstMH();return false;" aria-label="Mental health"><span class="bn-icon">🧠</span><span>__BNAV_PSYCH__</span></a>
  <a href="/profile" class="bn-profile" aria-label="My profile"><span class="bn-icon">👤</span><span>__BNAV_PROFILE__</span></a>
</nav>
<button class="asst-fab pulse" id="asstFab" onclick="asstToggle()" title="__AST_TITLE__"><span class="asst-fab-ic">🤖</span><span class="asst-fab-lb">__AST_TITLE__</span></button>
<div class="asst-panel" id="asstPanel">
  <div class="asst-head">
    <button class="asst-back" id="asstBack" onclick="asstBackMain()" style="display:none;">↩</button>
    <div class="asst-head-tx"><b id="asstHeadT">🤖 __AST_TITLE__</b><div class="asst-sub" id="asstSubT">__AST_SUB__</div></div>
    <button onclick="asstToggle()">✕</button>
  </div>
  <div class="asst-body" id="asstBody">
    <div class="asst-msg asst-bot" id="asstGreet">__AST_GREET__</div>
    <div class="asst-opts" id="asstOpts"></div>
    <div class="asst-qs" id="asstQs"></div>
  </div>
  <div class="asst-foot">
    <input class="asst-inp" id="asstInput" placeholder="__AST_PH__" onkeydown="if(event.key==='Enter')asstSend()">
    <button class="asst-mh-btn" id="asstMhBtn" onclick="asstToggleAnim()" style="display:none;">__AST_MH_ANIM__</button>
    <button onclick="asstSend()">➤</button>
  </div>
  <div class="asst-disc">__AST_DISC__</div>
</div>
<div class="expl-bg" id="explBg" onclick="if(event.target===this)closeExplain()">
  <div class="expl-modal">
    <div class="ex-head"><div class="ex-title" id="exTitle"></div><button class="ex-close" onclick="closeExplain()">✕</button></div>
    <div class="ex-levels" id="exLevels"></div>
    <div class="ex-explain" id="exBody"></div>
    <div class="ex-assist-row"><button class="btn pri" id="exAssist" onclick="askAboutTerm()">🤖 __AST_EXPLAIN_ASK__</button></div>
  </div>
</div>
<div class="asst-modal-bg" id="asstModalBg" onclick="if(event.target===this)asstCloseModal()">
  <div class="asst-modal">
    <div class="asst-modal-head"><b id="asstModalTitle"></b><button onclick="asstCloseModal()">✕</button></div>
    <div class="asst-reasons" id="asstModalReasons"></div>
  </div>
</div>
<script>
var ASST_T = __AST_T__;
function asstTT(k) { return ASST_T[k] || k; }
var asstPageCtx = '';
var asstMhMode = false;
var asstBrTimer = null, asstBrPhase = 0;
var asstLockedScrollY = 0;
var asstBodyLockState = null;
function asstSetCtx(k) { asstPageCtx = k || ''; }
function asstIsTouchViewport() {
  return window.matchMedia && window.matchMedia('(hover: none), (pointer: coarse)').matches;
}
function asstFocusInput() {
  /* iOS Safari may move the whole viewport when focus() is called programmatically.
     Auto-focus only on desktop/fine-pointer devices; mobile users can tap the field. */
  if (asstIsTouchViewport() || window.innerWidth <= 768) return;
  var inp = document.getElementById('asstInput');
  if (!inp) return;
  try { inp.focus({preventScroll:true}); } catch (e) { inp.focus(); }
}
function asstLockPage() {
  if (document.body.classList.contains('ss-assistant-open')) return;
  asstLockedScrollY = window.pageYOffset || document.documentElement.scrollTop || 0;
  asstBodyLockState = {
    position: document.body.style.position,
    top: document.body.style.top,
    left: document.body.style.left,
    right: document.body.style.right,
    width: document.body.style.width
  };
  document.documentElement.classList.add('ss-assistant-open');
  document.body.classList.add('ss-assistant-open');
  document.body.style.position = 'fixed';
  document.body.style.top = (-asstLockedScrollY) + 'px';
  document.body.style.left = '0';
  document.body.style.right = '0';
  document.body.style.width = '100%';
}
function asstUnlockPage() {
  if (!document.body.classList.contains('ss-assistant-open')) return;
  document.documentElement.classList.remove('ss-assistant-open');
  document.body.classList.remove('ss-assistant-open');
  var st = asstBodyLockState || {};
  document.body.style.position = st.position || '';
  document.body.style.top = st.top || '';
  document.body.style.left = st.left || '';
  document.body.style.right = st.right || '';
  document.body.style.width = st.width || '';
  asstBodyLockState = null;
  /* Restore the exact pre-open position without animation. */
  window.scrollTo(0, asstLockedScrollY);
}
function asstToggle() {
  var p = document.getElementById('asstPanel');
  var f = document.getElementById('asstFab');
  var open = p.classList.toggle('open');
  f.querySelector('.asst-fab-ic').textContent = open ? '✕' : '🤖';
  f.querySelector('.asst-fab-lb').textContent = open ? asstTT('asst_close') : asstTT('asst_title');
  if (open) {
    asstLockPage();
    asstShowMain();
    asstFocusInput();
  } else {
    asstBreathStop();
    asstUnlockPage();
  }
}
function asstGreeting() {
  var c = asstPageCtx;
  if (c === 'sug') return asstTT('asst_calc_sug_greet');
  if (c === 'bmi') return asstTT('asst_calc_bmi_greet');
  if (c === 'fluids') return asstTT('asst_calc_fluids_greet');
  if (c === 'cal') return asstTT('asst_calc_cal_greet');
  if (c === 'dose') return asstTT('asst_calc_dose_greet');
  if (c === 'calc') return asstTT('asst_calc_greet');
  return asstTT('asst_greet');
}
function asstChips() {
  var c = asstPageCtx;
  if (asstMhMode) return [asstTT('asst_mh_calm_chip')];
  if (c === 'sug') return [asstTT('asst_q_sug1'), asstTT('asst_q_sug2'), asstTT('asst_q_sug3')];
  if (c === 'bmi') return [asstTT('asst_q_bmi1'), asstTT('asst_q_bmi2'), asstTT('asst_q_bmi3')];
  if (c === 'fluids') return [asstTT('asst_q_fluids1')];
  if (c === 'cal') return [asstTT('asst_q_cal1')];
  if (c === 'dose') return [asstTT('asst_q_dose1')];
  if (c === 'calc') return [asstTT('asst_q_calc1'), asstTT('asst_q_calc2'), asstTT('asst_q_calc3')];
  return [asstTT('asst_q1'), asstTT('asst_q2'), asstTT('asst_q3'), asstTT('asst_q4')];
}
function asstMainOpts() {
  return [
    { ic: '🩺', t: asstTT('asst_opt_symp'), d: asstTT('asst_opt_symp_d'), act: 'go', k: 'symp' },
    { ic: '🧠', t: asstTT('asst_opt_mh'), d: asstTT('asst_opt_mh_d'), act: 'mh', k: '' },
    { ic: '💊', t: asstTT('asst_opt_drug'), d: asstTT('asst_opt_drug_d'), act: 'go', k: 'drug' },
    { ic: '🧪', t: asstTT('asst_opt_blood'), d: asstTT('asst_opt_blood_d'), act: 'go', k: 'blood' },
    { ic: '❓', t: asstTT('asst_opt_q'), d: asstTT('asst_opt_q_d'), act: 'go', k: 'q' }
  ];
}
function asstMhOpts() {
  return [
    { ic: '😟', t: asstTT('asst_mh_o_anx'), d: asstTT('asst_mh_o_anx_d'), act: 'ask', k: 'anxiety' },
    { ic: '😔', t: asstTT('asst_mh_o_sad'), d: asstTT('asst_mh_o_sad_d'), act: 'ask', k: 'sadness' },
    { ic: '😣', t: asstTT('asst_mh_o_str'), d: asstTT('asst_mh_o_str_d'), act: 'ask', k: 'stress' },
    { ic: '😴', t: asstTT('asst_mh_o_slp'), d: asstTT('asst_mh_o_slp_d'), act: 'ask', k: 'sleep' },
    { ic: '💭', t: asstTT('asst_mh_o_tho'), d: asstTT('asst_mh_o_tho_d'), act: 'ask', k: 'thoughts' },
    { ic: '💬', t: asstTT('asst_mh_o_oth'), d: asstTT('asst_mh_o_oth_d'), act: 'ask', k: 'other' },
    { ic: '🌙', t: asstTT('asst_mh_opt_night'), d: asstTT('asst_mh_opt_night_d'), act: 'night', k: 'calm' }
  ];
}
function asstRenderOpts() {
  var box = document.getElementById('asstOpts');
  if (!box) return;
  var arr = asstMhMode ? asstMhOpts() : asstMainOpts();
  box.innerHTML = arr.map(function(o) {
    return '<button class="asst-opt" onclick="asstOptClick(\\'' + o.act + '\\',\\'' + o.k + '\\')">' +
      '<span class="ao-ic">' + o.ic + '</span>' +
      '<span class="ao-tx"><span class="ao-t">' + o.t + '</span><span class="ao-d">' + o.d + '</span></span></button>';
  }).join('');
}
function asstShowMain() {
  var g = document.getElementById('asstGreet');
  if (g) {
    var msgs = document.querySelectorAll('#asstBody .asst-msg:not(#asstGreet)');
    if (msgs.length === 0) { g.textContent = asstGreeting(); g.style.whiteSpace = 'pre-line'; }
  }
  asstRenderOpts();
  asstInitQs();
}
function asstInitQs() {
  var qs = document.getElementById('asstQs');
  if (!qs) return;
  qs.innerHTML = asstChips().map(function(q) {
    var qq = q.replace(/["'\\\\]/g, '');
    return '<button class="asst-chip" onclick="asstChipClick(\\'' + qq + '\\')">' + q + '</button>';
  }).join('');
}
function asstChipClick(txt) {
  if (asstMhMode && txt === asstTT('asst_mh_calm_chip')) { asstMhAction('calm'); return; }
  asstAsk(txt);
}
function asstEnterMH() {
  asstMhMode = true;
  document.getElementById('asstPanel').classList.add('asst-mh');
  document.getElementById('asstHeadT').textContent = asstTT('asst_mh_title');
  document.getElementById('asstSubT').textContent = asstTT('asst_mh_sub');
  document.getElementById('asstBack').style.display = '';
  document.getElementById('asstInput').placeholder = asstTT('asst_mh_ph');
  document.getElementById('asstMhBtn').style.display = '';
  var g = document.getElementById('asstGreet');
  if (g) { g.textContent = asstTT('asst_mh_greet'); g.style.whiteSpace = 'pre-line'; }
  asstRenderOpts();
  asstInitQs();
}
function asstBackMain() {
  asstBreathStop();
  asstMhMode = false;
  nightCalmMode = false;
  document.getElementById('asstPanel').classList.remove('asst-mh');
  document.getElementById('asstPanel').classList.remove('night-calm');
  document.getElementById('asstHeadT').textContent = '🤖 ' + asstTT('asst_title');
  document.getElementById('asstSubT').textContent = asstTT('asst_sub');
  document.getElementById('asstBack').style.display = 'none';
  document.getElementById('asstInput').placeholder = asstTT('asst_ph');
  document.getElementById('asstMhBtn').style.display = 'none';
  asstShowMain();
}
function asstToggleAnim() {
  var p = document.getElementById('asstPanel');
  p.classList.toggle('no-anim');
  document.getElementById('asstMhBtn').textContent = p.classList.contains('no-anim') ? asstTT('asst_mh_anim_on') : asstTT('asst_mh_anim');
}
function asstOptClick(act, k) {
  if (act === 'mh') { asstEnterMH(); return; }
  if (act === 'night') { asstEnterNightCalm(); return; }
  if (act === 'ask') { asstMhAction(k); return; }
  if (k === 'symp') { location.href = '/chat'; return; }
  if (k === 'drug') { location.href = '/meds'; return; }
  if (k === 'blood') { location.href = '/blood'; return; }
  if (k === 'calc') { location.href = '/calculators'; return; }
  if (k === 'q') { asstFocusInput(); return; }
}
function asstMhAction(k) {
  if (k === 'calm') {
    asstBreathStart();
    asstMhMsg(asstTT('asst_mh_calm_msg'));
    asstFocusInput();
    return;
  }
  var send = {
    'anxiety': asstTT('asst_mh_send_anx'),
    'sadness': asstTT('asst_mh_send_sad'),
    'stress': asstTT('asst_mh_send_str'),
    'sleep': asstTT('asst_mh_send_slp'),
    'thoughts': asstTT('asst_mh_send_tho'),
    'other': asstTT('asst_mh_send_oth')
  }[k] || asstTT('asst_mh_send_oth');
  asstSendContextText(send);
}
var nightCalmMode = false;
var nightCalmStep = 0;
function asstEnterNightCalm() {
  nightCalmMode = true;
  nightCalmStep = 0;
  asstMhMode = true;
  document.getElementById('asstPanel').classList.add('asst-mh');
  document.getElementById('asstPanel').classList.add('night-calm');
  document.getElementById('asstHeadT').textContent = asstTT('night_calm_title');
  document.getElementById('asstSubT').textContent = asstTT('night_calm_greet');
  document.getElementById('asstBack').style.display = '';
  document.getElementById('asstInput').placeholder = asstTT('asst_mh_ph');
  document.getElementById('asstMhBtn').style.display = 'none';
  var body = document.getElementById('asstBody');
  body.innerHTML = '';
  asstMhMsg(asstTT('night_calm_greet'));
  setTimeout(function(){
    addOptsToBody([
      {label: asstTT('night_calm_opt_calm'), fn: function(){ nightCalmAction('calm'); }},
      {label: asstTT('night_calm_opt_listen'), fn: function(){ nightCalmAction('listen'); }},
      {label: asstTT('night_calm_opt_think'), fn: function(){ nightCalmAction('think'); }},
      {label: asstTT('night_calm_opt_sleep'), fn: function(){ nightCalmAction('sleep'); }}
    ]);
  }, 400);
}
function nightCalmAction(choice) {
  clearNightOpts();
  if (choice === 'calm') {
    asstMhMsg(asstTT('night_calm_calm_reply'));
    setTimeout(function(){
      asstMhMsg(asstTT('night_calm_calm_step'));
      asstBreathStart();
      setTimeout(function(){
        addOptsToBody([{label: asstTT('night_calm_next'), fn: function(){
          clearNightOpts(); asstBreathStop();
          asstMhMsg(LANG==='ar' ? 'كيف تحس الآن؟ 🤍' : 'How are you feeling now? 🤍');
          addOptsToBody([
            {label: LANG==='ar' ? '🌿 أهدأ شوي' : '🌿 A bit calmer', fn: function(){ clearNightOpts(); asstMhMsg(LANG==='ar' ? 'هذا يسعدني 🤍 خذ وقتك.' : 'That makes me happy 🤍 Take your time.'); }},
            {label: LANG==='ar' ? '💭 مازالت الأفكار كثيرة' : '💭 Still have racing thoughts', fn: function(){ clearNightOpts(); nightCalmAction('think'); }},
            {label: LANG==='ar' ? '🫂 أبي أتكلم' : '🫂 I want to talk', fn: function(){ clearNightOpts(); nightCalmAction('listen'); }}
          ]);
        }}]);
      }, 12000);
    }, 1000);
  } else if (choice === 'listen') {
    asstMhMsg(asstTT('night_calm_listen_reply'));
    asstFocusInput();
  } else if (choice === 'think') {
    asstMhMsg(asstTT('night_calm_think_reply'));
    asstFocusInput();
  } else if (choice === 'sleep') {
    asstMhMsg(asstTT('night_calm_sleep_reply'));
    setTimeout(function(){
      addOptsToBody([
        {label: asstTT('night_calm_sleep_option1') || '🫂 Talk about my day', fn: function(){ clearNightOpts(); asstSendContextText(LANG==='ar' ? 'أبي أتكلم عن يومي' : 'I want to talk about my day'); }},
        {label: asstTT('night_calm_sleep_option2') || '🌿 Calming session', fn: function(){ clearNightOpts(); nightCalmAction('calm'); }},
        {label: asstTT('night_calm_sleep_option3') || '💭 Empty my thoughts', fn: function(){ clearNightOpts(); nightCalmAction('think'); }},
        {label: asstTT('night_calm_sleep_option4') || '🤍 Something simple', fn: function(){ clearNightOpts(); asstMhMsg(LANG==='ar' ? 'تبي تسمع صوت مطربق؟ ولا نصيحة بسيطة؟ 🤍' : 'Want some ambient sounds? Or a simple tip? 🤍'); }}
      ]);
    }, 500);
  }
}
function clearNightOpts() {
  var existing = document.querySelectorAll('.night-opts');
  existing.forEach(function(el){ el.remove(); });
}
function addOptsToBody(items) {
  var body = document.getElementById('asstBody');
  var div = document.createElement('div');
  div.className = 'night-opts';
  div.style.cssText = 'display:flex;flex-direction:column;gap:8px;padding:8px 0;';
  items.forEach(function(item){
    var btn = document.createElement('button');
    btn.style.cssText = 'width:100%;padding:14px 16px;border:2px solid #DCEBFA;border-radius:14px;background:#fff;font-size:15px;font-weight:600;cursor:pointer;text-align:' + (LANG==='ar' ? 'right' : 'left') + ';color:#40566F;transition:all .2s;min-height:48px;';
    btn.textContent = item.label;
    btn.onmouseover = function(){ this.style.borderColor='#1976D2'; this.style.background='#EAF4FF'; };
    btn.onmouseout = function(){ this.style.borderColor='#DCEBFA'; this.style.background='#fff'; };
    btn.onclick = item.fn;
    div.appendChild(btn);
  });
  body.appendChild(div);
  body.scrollTop = body.scrollHeight;
}
function openAsstMH() {
  var p = document.getElementById('asstPanel');
  if (!p.classList.contains('open')) asstToggle();
  asstEnterMH();
}
function asstMhMsg(text) {
  var body = document.getElementById('asstBody');
  var d = document.createElement('div');
  d.className = 'asst-msg asst-bot';
  d.textContent = text;
  body.appendChild(d);
  body.scrollTop = body.scrollHeight;
}
function asstBreathStart() {
  asstBreathStop();
  var b = document.getElementById('asstBreath');
  if (!b) {
    b = document.createElement('div');
    b.id = 'asstBreath';
    var body = document.getElementById('asstBody');
    body.appendChild(b);
  }
  b.style.display = '';
  var phases = [[asstTT('asst_br_in'), 4000], [asstTT('asst_br_hold'), 7000], [asstTT('asst_br_out'), 8000]];
  function step() {
    var ph = phases[asstBrPhase % 3];
    b.textContent = ph[0];
    b.className = 'asst-breath asst-br-' + (asstBrPhase % 3);
    asstBrPhase++;
    asstBrTimer = setTimeout(step, ph[1]);
  }
  step();
}
function asstBreathStop() {
  if (asstBrTimer) { clearTimeout(asstBrTimer); asstBrTimer = null; }
  var b = document.getElementById('asstBreath');
  if (b) b.style.display = 'none';
}
function asstSay(text) {
  var body = document.getElementById('asstBody');
  var d = document.createElement('div');
  d.className = 'asst-msg asst-user';
  d.textContent = text;
  body.appendChild(d);
  body.scrollTop = body.scrollHeight;
}
function asstTyping(on) {
  var body = document.getElementById('asstBody');
  var t = document.getElementById('asstTyp');
  if (on) {
    t = document.createElement('div');
    t.id = 'asstTyp';
    t.className = 'asst-msg asst-bot';
    t.textContent = '...';
    body.appendChild(t);
    body.scrollTop = body.scrollHeight;
  } else if (t) { t.remove(); }
}
var lastReplyText = '';
function asstReply(text, flags) {
  lastReplyText = text;
  var body = document.getElementById('asstBody');
  var d = document.createElement('div');
  d.className = 'asst-msg asst-bot';
  d.textContent = text;
  body.appendChild(d);
  if (flags && flags.length) {
    var a = document.createElement('div');
    a.className = 'asst-emerg';
    a.innerHTML = asstTT('asst_emerg_txt') + ' <b>997</b><br><a href="/emergency">' + asstTT('asst_emerg_btn') + '</a>';
    body.appendChild(a);
  }
  var fb = document.createElement('div');
  fb.className = 'asst-fb';
  fb.innerHTML = '<button class="asst-fb-btn" onclick="asstFb(this,1)">👍 ' + asstTT('asst_fb_good') + '</button>' +
    '<button class="asst-fb-btn" onclick="asstFb(this,2)">😐 ' + asstTT('asst_fb_partial') + '</button>' +
    '<button class="asst-fb-btn" onclick="asstFb(this,0)">👎 ' + asstTT('asst_fb_bad') + '</button>';
  body.appendChild(fb);
  body.scrollTop = body.scrollHeight;
}
function asstFb(btn, rating) {
  var bar = btn.closest('.asst-fb');
  if (!bar || bar.dataset.done) return;
  if (rating === 0) {
    asstOpenReasons(bar);
    return;
  }
  bar.dataset.done = '1';
  var ok = document.createElement('span');
  ok.className = 'asst-fb-ok';
  ok.textContent = asstTT('asst_fb_thanks');
  bar.innerHTML = '';
  bar.appendChild(ok);
  fetch('/api/assistant/feedback', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rating: rating, message: lastReplyText.slice(0, 500), reason: null }) })
    .then(function() {}).catch(function() {});
}
function asstOpenReasons(bar) {
  document.getElementById('asstModalTitle').textContent = asstTT('asst_fb_title');
  var reasons = [asstTT('asst_fr1'), asstTT('asst_fr2'), asstTT('asst_fr3'), asstTT('asst_fr4'), asstTT('asst_fr5'), asstTT('asst_fr6')];
  document.getElementById('asstModalReasons').innerHTML = reasons.map(function(r) {
    var rr = r.replace(/["'\\\\]/g, '');
    return '<button class="asst-reason" onclick="asstSendFb(\\'' + rr + '\\')">' + r + '</button>';
  }).join('');
  asstModalBar = bar;
  document.getElementById('asstModalBg').classList.add('open');
}
var asstModalBar = null;
function asstSendFb(reason) {
  var bar = asstModalBar;
  asstCloseModal();
  if (bar) {
    bar.dataset.done = '1';
    bar.innerHTML = '';
    var ok = document.createElement('span');
    ok.className = 'asst-fb-ok';
    ok.textContent = asstTT('asst_fb_sent');
    bar.appendChild(ok);
  }
  fetch('/api/assistant/feedback', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rating: 0, message: lastReplyText.slice(0, 500), reason: reason.slice(0, 120) }) })
    .then(function() {}).catch(function() {});
}
function asstCloseModal() {
  document.getElementById('asstModalBg').classList.remove('open');
}
function asstOpenWithContext(topic) {
  var lang = document.documentElement.lang === 'en' ? 'en' : 'ar';
  var tpl = asstTT('asst_ctx');
  var q = tpl.replace('%s', topic);
  asstSendContextText(q);
}
function asstSendContextText(fullText) {
  var p = document.getElementById('asstPanel');
  if (!p.classList.contains('open')) asstToggle();
  var inp = document.getElementById('asstInput');
  inp.value = fullText;
  asstSend();
}
function openExplain(term) {
  var bg = document.getElementById('explBg');
  document.getElementById('exTitle').textContent = '✨ ' + asstTT('sea_explain_title') + ': ' + term;
  document.getElementById('exBody').textContent = '...';
  document.getElementById('exLevels').innerHTML = '';
  document.getElementById('exAssist').style.display = 'none';
  bg.classList.add('open');
  fetch('/api/explain?term=' + encodeURIComponent(term) + '&lang=' + (document.documentElement.lang === 'en' ? 'en' : 'ar'))
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (!d.ok || !d.result) { document.getElementById('exBody').textContent = asstTT('sea_noexplain'); return; }
      var items = [['very_simple', '🟢'], ['basic', '🔵'], ['advanced', '🟣']];
      var lh = '';
      items.forEach(function(item, i) {
        lh += '<button class="ex-level' + (i === 0 ? ' on' : '') + '" data-lv="' + item[0] + '" onclick="showLv(this)">' +
          '<div class="lv-ic">' + item[1] + '</div><div class="lv-t">' + asstTT('lv_' + item[0]) + '</div></button>';
      });
      document.getElementById('exLevels').innerHTML = lh;
      document.getElementById('exBody').textContent = d.result.levels.very_simple;
      document.getElementById('exAssist').style.display = '';
    }).catch(function() { document.getElementById('exBody').textContent = asstTT('sea_noexplain'); });
}
function showLv(btn) {
  document.querySelectorAll('.ex-level').forEach(function(x) { x.classList.remove('on'); });
  btn.classList.add('on');
  var term = document.getElementById('exTitle').textContent.split(': ').slice(1).join(': ');
  fetch('/api/explain?term=' + encodeURIComponent(term) + '&lang=' + (document.documentElement.lang === 'en' ? 'en' : 'ar'))
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (!d.ok || !d.result) return;
      document.getElementById('exBody').textContent = d.result.levels[btn.dataset.lv] || '';
    }).catch(function() {});
}
function closeExplain() { document.getElementById('explBg').classList.remove('open'); }
function askAboutTerm() {
  var term = document.getElementById('exTitle').textContent.split(': ').slice(1).join(': ');
  closeExplain();
  if (typeof asstOpenWithContext === 'function') asstOpenWithContext(term);
}
function asstShowServices(svs) {
  var qs = document.getElementById('asstQs');
  qs.innerHTML = svs.map(function(s) {
    return '<button class="asst-chip" onclick="location.href=\\'' + s.url + '\\'">' + s.label + '</button>';
  }).join('');
}
function asstShowSources(sources) {
  if (!sources || !sources.length) return;
  var qs = document.getElementById('asstQs');
  var wrap = document.createElement('div');
  wrap.className = 'asst-source-list';
  var title = document.createElement('b');
  title.textContent = document.documentElement.lang === 'en' ? '📚 Medical sources' : '📚 المصادر الطبية';
  wrap.appendChild(title);
  sources.forEach(function(source) {
    var href = source.reference_url || source.official_url;
    if (!href || !href.startsWith('https://')) return;
    var link = document.createElement('a');
    link.className = 'asst-chip'; link.href = href; link.target = '_blank'; link.rel = 'noopener noreferrer';
    link.textContent = source.source_name || source.organization || (document.documentElement.lang === 'en' ? 'View source' : 'عرض المصدر');
    wrap.appendChild(link);
  });
  qs.appendChild(wrap);
}
function asstAsk(q) {
  document.getElementById('asstInput').value = q;
  asstSend();
}
function asstSend() {
  var inp = document.getElementById('asstInput');
  var text = inp.value.trim();
  if (!text) return;
  inp.value = '';
  asstSay(text);
  var lowerText = text.toLowerCase();
  var harmPhrases = ['انتحار', 'أضر بنفسي', 'أريد الموت', 'لا أريد العيش', 'suicide', 'kill myself', 'want to die', 'harm myself', 'end my life', 'end it all', 'أموت', 'أ完结', 'أتمنى الموت'];
  var isHarm = harmPhrases.some(function(p){ return lowerText.indexOf(p) !== -1; });
  if (isHarm) {
    var lang = document.documentElement.lang === 'en' ? 'en' : 'ar';
    var harmMsg = lang === 'ar'
      ? '🚨 أنت لست وحدك. أرجوك تواصل مع خط مساندة الصحة النفسية الآن على الرقم 937 أو الطوارئ 997. الحياة ثمينة وهناك من يساعدك.'
      : '🚨 You are not alone. Please reach out to the mental health support line now at 937 or emergency services at 997. Your life is precious and help is available.';
    var harmBtns = lang === 'ar'
      ? '<div style="margin-top:10px;"><a href="tel:937" style="display:inline-block;background:#1976D2;color:#fff;padding:8px 16px;border-radius:8px;text-decoration:none;font-weight:700;margin:4px;">📞 اتصال بخط 937</a><a href="tel:997" style="display:inline-block;background:#DC2626;color:#fff;padding:8px 16px;border-radius:8px;text-decoration:none;font-weight:700;margin:4px;">🚑 الطوارئ 997</a></div>'
      : '<div style="margin-top:10px;"><a href="tel:937" style="display:inline-block;background:#1976D2;color:#fff;padding:8px 16px;border-radius:8px;text-decoration:none;font-weight:700;margin:4px;">📞 Call 937</a><a href="tel:997" style="display:inline-block;background:#DC2626;color:#fff;padding:8px 16px;border-radius:8px;text-decoration:none;font-weight:700;margin:4px;">🚑 Emergency 997</a></div>';
    var d = document.createElement('div');
    d.className = 'asst-msg asst-bot';
    d.innerHTML = harmMsg + harmBtns;
    document.getElementById('asstBody').appendChild(d);
    return;
  }
  var hist = [];
  try { hist = JSON.parse(sessionStorage.getItem('asst_hist') || '[]'); } catch(e) {}
  hist.push({ role: 'user', content: text });
  hist = hist.slice(-8);
  sessionStorage.setItem('asst_hist', JSON.stringify(hist));
  asstTyping(true);
  fetch('/api/assistant', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages: hist, lang: document.documentElement.lang === 'en' ? 'en' : 'ar', mode: asstMhMode ? 'mh' : '' }) })
    .then(function(r) { return r.json(); })
    .then(function(d) {
      asstTyping(false);
      if (d.ok) {
        asstReply(d.answer, d.emergency_flags || []);
        hist.push({ role: 'assistant', content: d.answer });
        sessionStorage.setItem('asst_hist', JSON.stringify(hist.slice(-16)));
        if (d.services && d.services.length) asstShowServices(d.services);
        if (d.medical_sources && d.medical_sources.length) asstShowSources(d.medical_sources);
      } else {
        asstReply(asstTT('asst_offline'));
      }
    })
    .catch(function() { asstTyping(false); asstReply(asstTT('asst_offline')); });
}
asstInitQs();
</script>
<!-- Smart Context Modal -->
<div class="ss-modal-overlay" id="smartCtxModal">
  <div class="ss-modal">
    <div style="font-size:36px;margin-bottom:8px;">✨</div>
    <h3 id="smartCtxTitle">✨ استخدام معلوماتي المحفوظة؟</h3>
    <p id="smartCtxDesc">لديك معلومات محفوظة قد تساعد في جعل النتيجة أكثر تخصيصًا.</p>
    <div class="ss-modal-list" id="smartCtxList" style="display:none;">
      <span id="smartCtxFields"></span>
    </div>
    <div class="ss-modal-list" id="smartCtxMissingRow" style="display:none;margin-top:8px;border-color:#FDE68A;background:#FFFBEB;">
      <span id="smartCtxMissing"></span>
    </div>
    <div class="ss-modal-btns">
      <button class="ss-modal-btn primary" id="smartCtxUse" onclick="smartCtxAction('use')">✨ استخدام معلوماتي</button>
      <button class="ss-modal-btn secondary" id="smartCtxManual" onclick="smartCtxAction('manual')">إدخال المعلومات يدويًا</button>
      <button class="ss-modal-btn tertiary" id="smartCtxSkip" onclick="smartCtxAction('skip')">تخطي</button>
    </div>
  </div>
</div>
<script>
var smartCtxCallback = null;
var smartCtxProfile = null;
var smartCtxUserInfo = null;
function smartCtxShow(profile, callback, userInfo) {
  smartCtxProfile = profile;
  smartCtxCallback = callback;
  smartCtxUserInfo = userInfo || null;
  var modal = document.getElementById('smartCtxModal');
  if (!modal || !profile) { if (callback) callback('manual'); return; }
  var availFields = [];
  var missingFields = [];
  if (profile.display_name) availFields.push('👤 ' + (LANG === 'ar' ? 'الاسم: ' : 'Name: ') + profile.display_name);
  else missingFields.push('👤 ' + (LANG === 'ar' ? 'الاسم' : 'Name'));
  var hasAge = profile.age || profile.dob;
  if (hasAge) availFields.push('🎂 ' + (LANG === 'ar' ? 'العمر: ' : 'Age: ') + (profile.age || profile.dob));
  else missingFields.push('🎂 ' + (LANG === 'ar' ? 'تاريخ الميلاد' : 'Date of Birth'));
  if (profile.gender) availFields.push('⚧ ' + (LANG === 'ar' ? 'الجنس: ' : 'Gender: ') + (LANG === 'ar' ? (profile.gender === 'male' ? 'ذكر' : 'أنثى') : profile.gender));
  else missingFields.push('⚧ ' + (LANG === 'ar' ? 'الجنس' : 'Gender'));
  if (profile.height) availFields.push('📏 ' + (LANG === 'ar' ? 'الطول: ' : 'Height: ') + profile.height + ' cm');
  else missingFields.push('📏 ' + (LANG === 'ar' ? 'الطول' : 'Height'));
  if (profile.weight) availFields.push('⚖️ ' + (LANG === 'ar' ? 'الوزن: ' : 'Weight: ') + profile.weight + ' kg');
  else missingFields.push('⚖️ ' + (LANG === 'ar' ? 'الوزن' : 'Weight'));
  if (profile.medications) availFields.push('💊 ' + (LANG === 'ar' ? 'الأدوية: ' : 'Medications: ') + profile.medications);
  if (profile.allergies) availFields.push('⚠️ ' + (LANG === 'ar' ? 'الحساسية: ' : 'Allergies: ') + profile.allergies);
  if (profile.health_conditions) availFields.push('🩺 ' + (LANG === 'ar' ? 'الحالات الصحية: ' : 'Health Conditions: ') + profile.health_conditions);
  var listEl = document.getElementById('smartCtxList');
  var fieldsEl = document.getElementById('smartCtxFields');
  var missingEl = document.getElementById('smartCtxMissing');
  var missingRow = document.getElementById('smartCtxMissingRow');
  if (availFields.length && listEl && fieldsEl) {
    listEl.style.display = 'block';
    fieldsEl.innerHTML = '<div style="font-size:12px;color:#0B9F50;font-weight:700;margin-bottom:4px;">✅ ' + (LANG==='ar' ? 'المعلومات المحفوظة:' : 'Saved information:') + '</div>' + availFields.join('<br>');
  } else if (listEl) {
    listEl.style.display = 'none';
  }
  if (missingFields.length && missingEl && missingRow) {
    missingRow.style.display = 'block';
    missingEl.innerHTML = '<div style="font-size:12px;color:#D97706;font-weight:700;margin-bottom:4px;">⚠️ ' + (LANG==='ar' ? 'معلومات ناقصة:' : 'Missing information:') + '</div>' + missingFields.join('<br>') + '<div style="margin-top:6px;font-size:11px;color:#92400E;">' + (LANG==='ar' ? 'يمكنك إضافتها لاحقاً من صفحة الملف الشخصي' : 'You can add these later from your profile page') + '</div>';
  } else if (missingRow) {
    missingRow.style.display = 'none';
  }
  var titleEl = document.getElementById('smartCtxTitle');
  if (titleEl) titleEl.textContent = LANG === 'ar' ? '✨ استخدام معلومات ملفك الصحي' : '✨ Use your health profile';
  var descEl = document.getElementById('smartCtxDesc');
  if (descEl) descEl.textContent = LANG === 'ar' ? 'سيتم استخدام معلوماتك المحفوظة في التحليل الطبي' : 'Your saved info will be used in the medical analysis';
  modal.classList.add('open');
}
function smartCtxAction(action) {
  var modal = document.getElementById('smartCtxModal');
  if (modal) modal.classList.remove('open');
  if (smartCtxCallback) smartCtxCallback(action);
  smartCtxCallback = null;
}
</script>
<script>
(function () {
  var deferredPrompt = null;
  var box = document.getElementById('pwaInstall');
  var text = document.getElementById('pwaInstallText');
  var installBtn = document.getElementById('pwaInstallBtn');
  var laterBtn = document.getElementById('pwaLaterBtn');
  var isArabic = document.documentElement.lang === 'ar';

  function isStandalone() {
    return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
  }
  function recentlyDismissed() {
    try {
      var value = Number(localStorage.getItem('ss_pwa_dismissed') || 0);
      return value && (Date.now() - value < 7 * 24 * 60 * 60 * 1000);
    } catch (e) { return false; }
  }
  function hasReturnedBefore() {
    try {
      var visits = Number(localStorage.getItem('ss_pwa_visits') || 0) + 1;
      localStorage.setItem('ss_pwa_visits', String(visits));
      return visits > 1;
    } catch (e) { return false; }
  }
  var canOfferInstall = hasReturnedBefore();
  function offerAfterDelay(mode) {
    if (!canOfferInstall || (window.location.pathname !== '/' && window.location.pathname !== '/home')) return;
    window.setTimeout(function () { show(mode); }, 8000);
  }
  function show(mode, force) {
    if (!box || isStandalone() || (!force && recentlyDismissed())) return;
    box.dataset.mode = mode;
    if (mode === 'ios') {
      text.textContent = isArabic
        ? 'لتثبيت SymptoSense: اضغطي مشاركة ⬆️ ثم «إضافة إلى الشاشة الرئيسية».'
        : 'To install SymptoSense, tap Share ⬆️ then “Add to Home Screen”.';
      installBtn.textContent = isArabic ? 'حسنًا' : 'Got it';
    } else if (mode === 'native') {
      text.textContent = isArabic
        ? 'ثبّتي SymptoSense كتطبيق على جهازك للوصول إليه بسرعة.'
        : 'Install SymptoSense on your device for quick access.';
      installBtn.textContent = isArabic ? 'تثبيت' : 'Install';
    } else {
      text.textContent = isArabic
        ? 'من قائمة المتصفح اختاري «إضافة إلى الشاشة الرئيسية» أو «تثبيت التطبيق».'
        : 'From your browser menu, choose “Add to Home Screen” or “Install app”.';
      installBtn.textContent = isArabic ? 'حسنًا' : 'Got it';
    }
    laterBtn.textContent = isArabic ? 'لاحقًا' : 'Later';
    box.classList.add('show');
  }

  window.pwaDismiss = function () {
    if (box) box.classList.remove('show');
    try { localStorage.setItem('ss_pwa_dismissed', String(Date.now())); } catch (e) {}
  };
  window.pwaInstallNow = async function () {
    if (box && (box.dataset.mode === 'ios' || box.dataset.mode === 'manual')) {
      box.classList.remove('show');
      return;
    }
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    try { await deferredPrompt.userChoice; } catch (e) {}
    deferredPrompt = null;
    if (box) box.classList.remove('show');
  };
  window.pwaRequestInstall = async function () {
    if (isStandalone()) return;
    var isiOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
    if (isiOS) { show('ios', true); return; }
    if (deferredPrompt) { await window.pwaInstallNow(); return; }
    show('manual', true);
  };

  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/service-worker.js', { scope: '/' }).catch(function () {});
    });
  }
  window.addEventListener('beforeinstallprompt', function (event) {
    event.preventDefault();
    deferredPrompt = event;
    offerAfterDelay('native');
  });
  window.addEventListener('appinstalled', function () {
    if (box) box.classList.remove('show');
  });
  window.addEventListener('load', function () {
    var isiOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
    if (isiOS && !isStandalone()) offerAfterDelay('ios');
  });
})();
</script>
</body>
</html>
"""


def _user_id():
    if "uid" not in session:
        session["uid"] = secrets.token_hex(8)
    return "web-" + hashlib.sha1(session["uid"].encode()).hexdigest()[:12]


def _ss_user_id():
    """Get the logged-in SymptoSense user ID from session, or None."""
    return session.get("ss_user_id")


def _data_user_id():
    """Stable owner key for health records; falls back to the browser session for public use."""
    account_id = _ss_user_id()
    return "account-%s" % account_id if account_id else _user_id()


def _consent_subject_key():
    """Internal subject key for consent/data controls; never exposed in analytics output."""
    return _data_user_id()


def _consent_state():
    try:
        return privacy_features.get_consent(_consent_subject_key(), _ss_user_id())
    except Exception:
        return {"service_usage": False, "analytics_research": False, "needs_review": True}


def _service_consent_ok():
    state = _consent_state()
    return bool(state.get("service_usage")) and not bool(state.get("needs_review"))


def _analytics_consent_ok():
    """Analytics consent is valid only for the current consent/policy versions."""
    state = _consent_state()
    return bool(state.get("analytics_research")) and not bool(state.get("needs_review"))


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
            try:
                platform_v2.audit(int(user.get("id")), "session_timeout", "admin_session", "self", None, {"status": "expired"})
            except Exception:
                pass
            session.clear()
            g.admin_session_expired = True
            return False
    if touch:
        session["admin_last_seen"] = now_ts
    return True


def _admin_csrf_token():
    if "admin_csrf" not in session:
        session["admin_csrf"] = secrets.token_urlsafe(32)
    return session["admin_csrf"]


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


def _safe_next_url(default="/home"):
    """Accept only local redirects after login or registration."""
    target = (request.args.get("next") or default).strip()
    if not target.startswith("/") or target.startswith("//"):
        return default
    return target


@app.before_request
def require_first_language_choice():
    """Keep first-time visitors on the neutral language picker before any page UI."""
    if request.method != "GET":
        return None
    if request.cookies.get("lang") in {"ar", "en"} or request.args.get("lang") in {"ar", "en"}:
        return None
    path = request.path or "/"
    public_paths = {"/", "/manifest.webmanifest", "/service-worker.js", "/favicon.ico", "/offline", "/robots.txt", "/sitemap.xml"}
    if path in public_paths or path.startswith("/api/") or path.startswith("/icons/") or path.startswith("/share/health/"):
        return None
    target = request.full_path.rstrip("?")
    return redirect(url_for("index", next=target))


@app.before_request
def v2_request_timer():
    g.v2_started_at = time.perf_counter()
    g.request_id = secrets.token_hex(8)


@app.after_request
def v2_operational_metrics(response):
    """Collect content-free operational counts and anonymous journey activity."""
    try:
        path = request.path or "/"
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
            platform_v2.record_usage(event_type, path, _lang(), request.headers.get("User-Agent", ""), response.status_code, elapsed)
        if request.method == "GET" and response.status_code < 400 and response.mimetype == "text/html" and not path.startswith("/admin"):
            try:
                admin_operational.touch_session(_analytics_session_id(), request.headers.get("User-Agent", ""))
                if path in {"/home","/"}: admin_operational.record_journey(_analytics_session_id(), "home", request.headers.get("User-Agent", ""))
                elif path == "/chat": admin_operational.record_journey(_analytics_session_id(), "start_analysis", request.headers.get("User-Agent", ""))
            except Exception:
                pass
    except Exception:
        pass
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
.ss-login-toast{position:fixed;z-index:2147483000;top:18px;inset-inline-end:18px;width:min(390px,calc(100vw - 28px));display:grid;grid-template-columns:38px 1fr auto;align-items:start;gap:10px;padding:14px 15px;background:#fff;border:1px solid #CFE5F4;border-inline-start:4px solid #287FC1;border-radius:15px;box-shadow:0 16px 45px rgba(22,59,92,.16);color:#23384A;animation:ssToastIn .24s ease both}
.ss-login-toast .ss-toast-check{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;background:#EDF8F2;color:#267A52;font-weight:900}
.ss-login-toast strong{display:block;color:#163B5C;font-size:14px;line-height:1.45}.ss-login-toast p{margin:3px 0 0;color:#607487;font-size:13px;line-height:1.55}
.ss-login-toast button{border:0;background:transparent;color:#607487;font-size:19px;line-height:1;padding:5px;cursor:pointer;border-radius:8px}.ss-login-toast button:hover,.ss-login-toast button:focus-visible{background:#EAF5FC;color:#163B5C;outline:2px solid #287FC1;outline-offset:1px}
.ss-login-toast.ss-toast-out{animation:ssToastOut .2s ease both}@keyframes ssToastIn{from{opacity:0;transform:translateY(-10px)}to{opacity:1;transform:none}}@keyframes ssToastOut{to{opacity:0;transform:translateY(-8px)}}
@media(max-width:600px){.ss-login-toast{top:10px;inset-inline:14px;width:auto}}@media(prefers-reduced-motion:reduce){.ss-login-toast,.ss-login-toast.ss-toast-out{animation:none}}
</style>
<div id="ssLoginToast" class="ss-login-toast" role="status" aria-live="polite" aria-atomic="true">
  <span class="ss-toast-check" aria-hidden="true">✓</span><div><strong>__TITLE__</strong><p>__MESSAGE__</p></div>
  <button type="button" aria-label="__CLOSE__" onclick="ssCloseLoginToast()">×</button>
</div>
<script>(function(){var done=false;window.ssCloseLoginToast=function(){if(done)return;done=true;var el=document.getElementById('ssLoginToast');if(!el)return;el.classList.add('ss-toast-out');window.setTimeout(function(){if(el&&el.parentNode)el.parentNode.removeChild(el);},230);};window.setTimeout(window.ssCloseLoginToast,4800);}());</script>
""".replace("__TITLE__",title).replace("__MESSAGE__",message).replace("__CLOSE__",close_label)


@app.after_request
def inject_login_success_toast(response):
    """Inject the pending login toast into the first successful HTML page only."""
    try:
        kind=session.get("login_toast")
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
        pass
    return response


@app.after_request
def production_security_headers(response):
    """Apply browser hardening without exposing or processing user content."""
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), geolocation=(), payment=(), usb=()")
    if app.config.get("SESSION_COOKIE_SECURE"):
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    response.headers.setdefault(
        "Content-Security-Policy-Report-Only",
        "default-src 'self'; script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; "
        "connect-src 'self'; frame-src 'self'; worker-src 'self'; object-src 'none'; "
        "base-uri 'self'; form-action 'self'",
    )
    response.headers.setdefault("X-Request-ID", getattr(g, "request_id", ""))
    return response


@app.errorhandler(404)
def not_found_page(_error):
    ar = _lang() == "ar"
    body = """
    <main style="max-width:620px;margin:8vh auto;text-align:center;background:#fff;border:1px solid var(--v2-line);border-radius:22px;padding:36px">
      <div style="font-size:52px">🔎</div><h1>__TITLE__</h1><p class="muted">__TEXT__</p><a class="btn primary" href="/home">__BACK__</a>
    </main>"""
    body = body.replace("__TITLE__", "الصفحة غير موجودة" if ar else "Page not found").replace("__TEXT__", "تحقق من الرابط أو عد إلى الصفحة الرئيسية." if ar else "Check the address or return to the home page.").replace("__BACK__", "العودة للرئيسية" if ar else "Back to Home")
    return _page("404", body), 404


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
    body = body.replace("__TITLE__", "حدث خطأ" if ar else "Something went wrong").replace("__TEXT__", "تعذر تحميل الصفحة حاليًا. حاول مرة أخرى." if ar else "We couldn't load this page right now. Please try again.").replace("__RID__", request_id).replace("__BACK__", "العودة للرئيسية" if ar else "Back to Home")
    return _page("500", body), 500


def _site_url():
    """Return the canonical public URL used in transactional email links.

    Prefer an explicit SITE_URL, then Railway's own public-domain variable,
    then the active HTTPS request host.  Never fall back to a stale hard-coded
    project hostname because that makes verification/reset emails look valid
    while sending users to the wrong deployment.
    """
    explicit = os.environ.get("SITE_URL", "").strip().rstrip("/")
    if explicit:
        if not explicit.startswith(("https://", "http://")):
            explicit = "https://" + explicit.lstrip("/")
        return explicit
    railway_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "").strip().strip("/")
    if railway_domain:
        return "https://" + railway_domain
    if has_request_context():
        try:
            return request.url_root.rstrip("/")
        except Exception:
            pass
    # Local/offline fallback only. Production on Railway always exposes
    # RAILWAY_PUBLIC_DOMAIN, and custom domains should be set via SITE_URL.
    return "http://localhost:8080"


def _lang():
    lang = request.cookies.get("lang") or request.args.get("lang")
    return "en" if lang == "en" else "ar"


L = {
    "ar": {
        "nav_home": "الرئيسية", "nav_chat": "فحص الأعراض", "nav_blood": "تحليل الدم",
        "nav_meds": "الأدوية", "nav_emergency": "الطوارئ", "nav_checkin": "متابعتي",
        "nav_family": "العائلة",
        "nav_firstaid": "الإسعافات", "nav_tips": "النصائح", "nav_relax": "الاسترخاء",
        "nav_calculators": "الحاسبات الصحية",
        "nav_search": "البحث الصحي",
        "nav_admin": "لوحة التحكم", "nav_about": "من نحن",
        "nav_how": "كيف يعمل", "nav_features": "المميزات", "nav_contact": "تواصل معنا",
        "nav_profile": "ملفي", "nav_history": "سجلّي",
        "nav_explore": "الاستكشاف", "nav_q": "الأسئلة الطبية", "nav_geo": "أقرب مستشفى",
        "nav_aware": "التوعية", "nav_blog": "المدونة",
        "footer_note": "SymptoSense © 2026 — للتوعية الصحية فقط وليس بديلاً عن الاستشارة الطبية.",
        "footer_emergency": "في حالة الطوارئ اتصل بالإسعاف مباشرة: <b>997</b> (السعودية)",
        "footer_tag": "التوعية الصحية تبدأ بخطوة.",
        "footer_privacy": "الخصوصية",
        "footer_terms": "الشروط",
        "footer_contact": "تواصل معنا",
        "footer_copy": "© 2026 SymptoSense",
        "footer_slogan": "مساعدك الصحي الذكي",
        "footer_synopsis_t": "عن المشروع",
        "footer_synopsis_d": "SymptoSense منصة صحية ذكية تهدف إلى تبسيط الوصول إلى المعلومات والأدوات الصحية ومساعدة المستخدم على فهم حالته بشكل أوضح.",
        "footer_owner_t": "من نحن",
        "footer_owner_name": "ريماس حميد السلمي 🤍",
        "footer_owner_role": "طالبة علوم البيانات وتحليلها ومؤسسة SymptoSense",
        "footer_contact_t": "للتواصل",
        "footer_wa_btn": "💬 تواصل معي على تيليجرام",
        "footer_love": "صُنع بكل حب 🤍 بواسطة",
        "footer_love_name": "ريماس",
        "footer_copy_full": "© 2026 SymptoSense — جميع الحقوق محفوظة",
        "keywords": "تحليل الأعراض, فحص الأعراض, تشخيص مبدئي, صحة, طب, مستشفيات السعودية, SymptoSense",
        "title_landing": "SymptoSense — تحليل الأعراض بالذكاء الاصطناعي",
        "title_chat": "SymptoSense — فحص الأعراض",
        "title_blood": "SymptoSense — تحليل الدم",
        "title_meds": "SymptoSense — فحص الأدوية",
        "title_firstaid": "SymptoSense — الإسعافات الأولية",
        "title_tips": "SymptoSense — النصائح الصحية",
        "title_relax": "SymptoSense — الاسترخاء",
        "title_emergency": "SymptoSense — أرقام الطوارئ",
        "title_checkin": "SymptoSense — متابعة الحالة اليومية",
        "title_calculators": "SymptoSense — الحاسبات الصحية",
        "title_about": "SymptoSense — عن الموقع",
        "title_about_us": "SymptoSense — من نحن",
        "desc": "مساعدك الذكي لتحليل الأعراض وتقييم الحالة الصحية الأولي بناءً على مصادر طبية موثوقة.",
        "w_title": "أهلاً بك في SymptoSense 👋",
        "w_sub": "مساعدك الذكي لتحليل الأعراض وتقييم الحالة الصحية. اختر اللغة للمتابعة.",
        "w_pick": "اختر لغتك للمتابعة 👇",
        "w_taphint": "اضغط في أي مكان للمتابعة",
        "lang_btn": "اختر اللغة",
        "w_ar_l": "العربية 🇸🇦",
        "w_ar_d": "المتابعة باللغة العربية",
        "w_en_l": "English 🇬🇧",
        "w_en_d": "Continue in English",
        "home_hero_t1": "كيف تحسين؟",
        "home_hero_t2": "لنكتشف معاً 🩺",
        "home_hero_p": "أدخل أعراضك بخطوات بسيطة واحصل على تقييم أولي ذكي يعتمد على نموذج التحليل المعتمد في النظام — مع تحذيرات الأدوية، أقرب المستشفيات، تحليل فحوصات الدم، والإسعافات الأولية.",
        "home_btn_start": "ابدأ الفحص الآن 🚀",
        "home_btn_blood": "تحليل فحص الدم 📋",
        "home_features_title": "اختر ما تحتاج 🧰",
        "home_f_t": "فحص الأعراض", "home_f_p": "أدخل أعراضك واحصل على تقييم أولي ذكي مع خطورة الحالة (بسيط / موعد / طوارئ).",
        "home_b_t": "تحليل فحص الدم", "home_b_p": "ارفع صورة أو PDF لتحليل الدم (CBC) واحصل على تفسير القيم والمؤشرات.",
        "home_m_t": "البحث عن دواء", "home_m_p": "تحذيرات الأدوية والتفاعلات وإرشادات الاستخدام الآمن.",
        "home_h_t": "أقرب مستشفى", "home_h_p": "بناءً على موقعك، نعرض لك أقرب المرافق الصحية بالمسافة ورابط الخريطة.",
        "home_q_t": "أسئلة لطبيبك", "home_q_p": "أسئلة ذكية جاهزة تسألها لطبيبك في الموعد، مع علامات الخطر ومتى تراجع.",
        "home_fa_t": "الإسعافات الأولية", "home_fa_p": "خطوات سريعة واضحة للحالات الطارئة اليومية.",
        "home_calc_t": "الحاسبات الصحية", "home_calc_p": "احسب مؤشرات صحية شائعة (BMI، السعرات، السكر وغيرها) بنتائج مبسطة.",
        "home_t_t": "نصائح صحية", "home_t_p": "نصائح يومية عملية لصحة أفضل لك ولعائلتك.",
        "home_r_t": "استرخاء وتنفس", "home_r_p": "تمارين تنفس وهدوء لتخفيف التوتر والقلق.",
        "home_e_t": "أرقام الطوارئ", "home_e_p": "أرقام مهمة جاهزة للحالات الطارئة (997، 911، 937...).",
        "home_c_t": "متابعة يومية", "home_c_p": "سجّل حالتك يومياً وتابع تحسنك بمخطط واضح.",
        "home_how_title": "كيف يعمل؟",
        "home_s1_t": "أدخل معلوماتك", "home_s1_p": "العمر، الجنس، الأعراض، المدة، والشدة.",
        "home_s2_t": "يحلل النظام المعلومات", "home_s2_p": "نظام ذكي يحلل المعلومات المدخلة بالاعتماد على نموذج التحليل والمصادر الطبية المستخدمة في النظام.",
        "home_s3_t": "تحصل على تقييم أولي", "home_s3_p": "مستوى الخطورة، الاحتمالات المحتملة، والتوصيات المناسبة.",
        "home_warn": "⚠️ <b>تنبيه:</b> هذا الموقع للتوعية الصحية فقط وليس تشخيصاً طبياً نهائياً. في حال وجود أعراض خطرة (ألم صدر حاد، صعوبة تنفس، نزيف حاد، فقدان وعي) اتصل بالإسعاف فوراً <b>997</b>.",
        "home_badge": "مساعدك الصحي بالذكاء الاصطناعي",
        "home_h1": "مرحبًا بك في",
        "home_h1b": "SymptoSense",
        "home_sub": "مساعدك الصحي الذكي لفهم أعراضك",
        "home_desc": "أدخل أعراضك في خطوات بسيطة واحصل على تقييم أولي ذكي يساعدك على فهم حالتك ومعرفة الخطوة المناسبة التالية — مع الحفاظ على خصوصيتك.",
        "home_btn1": "ابدأ التقييم الآن ✨",
        "home_btn2": "كيف يعمل SymptoSense؟",
        "home_ph1": "افهم أعراضك",
        "home_ph2": "اعتني بصحتك",
        "home_services": "الخدمات الصحية 🩺",
        "home_services_sub": "أدوات ذكية تساعدك على فهم صحتك واتخاذ الخطوة المناسبة.",
        "home_more": "عرض المزيد",
        "home_less": "عرض أقل",
        "home_f_t": "فحص الأعراض",
        "home_f_p": "أدخل أعراضك واحصل على تقييم أولي يساعدك على فهم حالتك.",
        "home_f_btn": "ابدأ الآن",
        "home_b_t": "تحليل الدم",
        "home_b_p": "ارفع تقرير تحليل الدم واحصل على شرح مبسط للنتائج.",
        "home_b_btn": "حلل الآن",
        "home_m_t": "البحث عن دواء",
        "home_m_p": "ابحث عن معلومات حول الأدوية والجرعات وطريقة الاستخدام بأمان.",
        "home_m_btn": "ابحث الآن",
        "home_calc_t": "الحاسبات الصحية",
        "home_calc_p": "احسب مؤشرات صحية مثل BMI والسعرات وغيرها.",
        "home_calc_btn": "احسب الآن",
        "home_mh_t": "صحتي النفسية",
        "home_mh_p": "مساحة خاصة للحديث عن مشاعرك، القلق والتوتر مع مساعدك الذكي.",
        "home_mh_btn": "تحدث مع المساعد 🤍",
        "home_asst_t": "المساعد الذكي",
        "home_asst_sub": "اسأل مساعد SymptoSense عن أي شيء يخص صحتك — متاح دائمًا في أي وقت.",
        "home_asst_btn": "🤖 اسأل SymptoSense",
        "home_quick_t": "المساعدة السريعة 🚨",
        "home_quick_hosp_t": "أقرب مستشفى",
        "home_quick_hosp_p": "ابحث عن أقرب منشأة صحية مناسبة لموقعك.",
        "home_quick_em_t": "أرقام الطوارئ",
        "home_quick_em_p": "الوصول السريع إلى أرقام الطوارئ المهمة.",
        "home_care_t": "العناية والدعم 💙",
        "home_care_mh_t": "صحتي النفسية",
        "home_care_relax_t": "استرخاء وتهدئة",
        "home_care_check_t": "متابعة يومية",
        "home_care_tips_t": "نصائح صحية",
        "home_how": "كيف يعمل SymptoSense؟",
        "home_step1_t": "أدخل أعراضك",
        "home_step1_p": "صف حالتك الصحية بخطوات بسيطة.",
        "home_step2_t": "أجب عن الأسئلة",
        "home_step2_p": "أجب عن أسئلة ذكية تساعد على فهم حالتك بشكل أفضل.",
        "home_step3_t": "احصل على تقييم أولي",
        "home_step3_p": "احصل على معلومات وإرشادات تساعدك على معرفة الخطوة التالية.",
        "home_warn2": "<b>تنبيه:</b> المعلومات المقدمة في SymptoSense للتوعية الصحية وليست بديلًا عن استشارة الطبيب. في الحالات الطارئة أو الأعراض الشديدة، يرجى التواصل مع خدمات الطوارئ أو مراجعة أقرب منشأة صحية.",
        "ab_t1": "ما هو SymptoSense؟",
        "about_us_kicker": "قصتنا",
        "about_us_title": "من نحن",
        "about_us_p1": "بدأ شغفي من سؤال بسيط: كيف يمكن للتقنية أن تكون أقرب للإنسان؟",
        "about_us_p2": "أنا ريماس حميد السلمي، طالبة في تخصص علوم البيانات وتحليلها، وشغوفة ببناء الحلول التقنية التي تحمل أثرًا حقيقيًا في حياة الناس.",
        "about_us_p3": "ومن هنا جاءت فكرتي؛ أن أوظّف ما أتعلمه في علوم البيانات والتقنية لبناء حل يساعد على فهم الأعراض الصحية بصورة أوضح وأسهل. لم يكن هدفي إنشاء موقع فقط، بل صناعة تجربة تمنح المستخدم معرفة أولية تساعده على فهم ما يشعر به واتخاذ الخطوة المناسبة بوعي.",
        "about_us_p4": "أؤمن أن أعظم أثر للتقنية هو أن تجعل حياة الإنسان أبسط، ووعيه أكبر، وقراراته أذكى.",
        "about_us_name": "ريماس حميد السلمي",
        "about_us_role": "طالبة علوم البيانات وتحليلها ومؤسسة SymptoSense",
        "about_us_contact": "للتواصل:",
        "about_us_img1_alt": "هاتف ذكي تحيط به رموز صحية يعبّر عن فهم الأعراض والعناية بالصحة",
        "about_us_img2_alt": "تصميم صحي تقني يرمز إلى SymptoSense",
        "ab_p1": "SymptoSense مساعد صحي توعوي يعتمد على الذكاء الاصطناعي لمساعدتك في فهم أعراضك والحصول على تقييم أولي مبني على مصادر طبية موثوقة (Mayo Clinic, NHS, WHO, CDC).",
        "ab_p2": "يوفّر الموقع: تحليل الأعراض مع تقييم الخطورة، تحذيرات الأدوية وتفاعلاتها، أقرب المستشفيات بناءً على موقعك، تحليل فحوصات الدم، الإسعافات الأولية، ونصائح صحية يومية.",
        "ab_p3": "يتم التحليل عبر نموذج ذكاء اصطناعي (Llama عبر Groq) مع طبقة تحقق بالقواعد ونموذج تعلم آلي لتقدير الاحتمالات — وكل ذلك كأداة توعية مساعدة.",
        "ab_p4": "هذا الموقع <b>ليس تشخيصاً طبياً نهائياً</b> ولا بديلاً عن استشارة الطبيب المختص. عند أي عرض خطر اتصل بالإسعاف فوراً.",
        "ab_srcs": "المصادر الطبية المعتمدة:",
        "ab_srcs_p": "Mayo Clinic، NHS، World Health Organization (WHO)، CDC، MedlinePlus — تُذكر داخل كل توصية مع رابطها.",
        "ab_note": "بياناتك تُخزّن بشكل مجهول (بدون هوية) وتُستخدم فقط لتحسين الخدمة والإحصاءات.",
        "ab_hero_sub": "مساعدك الذكي لفهم صحتك",
        "ab_hero_p": "SymptoSense أداة توعوية تساعدك على فهم أعراضك، وتحليل فحوصات الدم، والحصول على معلومات دوائية وإرشادات صحية — بالاعتماد على مصادر طبية معتمدة — لمساعدتك على اتخاذ الخطوة الصحيحة نحو صحتك.",
        "ab_alert": "⚠️ SymptoSense أداة توعية مساعدة وليست بديلاً عن الطبيب. عند وجود أعراض خطرة اتصل بالإسعاف <b>997</b> فوراً.",
        "ab_services_h": "🧰 ماذا يقدم SymptoSense؟",
        "ab_sv1_t": "تحليل الأعراض", "ab_sv1_p": "تقييم أولي للأعراض مع مستوى الخطورة والاحتمالات المحتملة والتوصيات.",
        "ab_sv2_t": "تحليل فحص الدم", "ab_sv2_p": "رفع صورة فحص الدم (CBC) وتفسير القيم والنطاقات المرجعية.",
        "ab_sv3_t": "معلومات الأدوية", "ab_sv3_p": "الاستخدامات والتحذيرات والتداخلات مع تنبيهات الاستخدام الآمن.",
        "ab_sv4_t": "أرقام الطوارئ", "ab_sv4_p": "أرقام الإسعاف والطوارئ المهمة وعلامات الخطر التي تستدعي الاتصال فوراً.",
        "ab_sv5_t": "أقرب مستشفى", "ab_sv5_p": "تحديد أقرب المرافق الصحية بناءً على موقعك مع رابط الخريطة.",
        "ab_sv6_t": "نصائح صحية", "ab_sv6_p": "نصائح يومية عملية في التغذية والنوم والنشاط والوقاية.",
        "ab_how_h": "⚙️ كيف يعمل؟",
        "ab_how1_t": "أدخل معلوماتك", "ab_how1_p": "العمر، الجنس، الأعراض، المدة، والشدة.",
        "ab_how2_t": "يحلل النظام المعلومات", "ab_how2_p": "نظام ذكي يحلل المعلومات المدخلة بالاعتماد على نموذج التحليل والمصادر الطبية المستخدمة في النظام.",
        "ab_how3_t": "تحصل على تقييم أولي", "ab_how3_p": "مستوى الخطورة، الاحتمالات المحتملة، والتوصيات المناسبة.",
        "ab_srcs_h": "📚 مصادرنا الطبية",
        "ab_srcs_p2": "نعتمد في معلوماتنا على مصادر طبية موثوقة ومعترف بها، ويُذكر المصدر مع كل توصية ورابطها.",
        "ab_priv_h": "🔐 الخصوصية",
        "ab_priv_p": "نحترم خصوصيتك: تُخزَّن تقييماتك بمعرّف داخلي لا يتضمن هويتك، وتُستخدم البيانات فقط لتحسين الخدمة، ولا نشاركها مع أي طرف ثالث.",
        "chat_sub": "مساعد التحليل الذكي",
        "chat_head_p": "مساعد التحليل الذكي — بالعربية 🇸🇦",
        "chat_muted": "التوعية فقط وليس تشخيصاً نهائياً — راجع الطبيب عند أي شك.",
        "title_profile": "SymptoSense — الملف الشخصي",
        "title_history": "SymptoSense — سجل التقييمات",
        "pr_h": "ملفي الشخصي 👤",
        "pr_sub": "احفظ معلوماتك مرة واحدة ليتم استخدامها تلقائياً في كل تحليل وتُرفق بنتائجك.",
        "pr_age": "العمر",
        "pr_gender": "الجنس",
        "pr_g_male": "ذكر", "pr_g_female": "أنثى",
        "pr_conditions": "الأمراض المزمنة (مفصولة بفواصل)",
        "pr_meds": "الأدوية المنتظمة (مفصولة بفواصل)",
        "pr_allergies": "الحساسية (مفصولة بفواصل)",
        "pr_save": "💾 حفظ الملف",
        "pr_saved": "✅ تم حفظ ملفك بنجاح",
        "pr_err": "حدث خطأ أثناء الحفظ",
        "pr_load_err": "خطأ في قراءة الملف",
        "pr_dash": "📊 لوحتك الصحية",
        "pr_dash_sub": "ملخص تحليلاتك وفحوصاتك في مكان واحد.",
        "pr_count_an": "إجمالي التحاليل",
        "pr_count_hi": "طوارئ", "pr_count_med": "متوسطة", "pr_count_lo": "بسيطة",
        "pr_blood_h": "🧪 فحوصات الدم",
        "pr_blood_latest": "آخر فحص دموي",
        "pr_blood_compare": "📈 مقارنة الفحوصات",
        "pr_blood_empty": "لم تُرفع فحوصات دم بعد — استخدم صفحة تحليل الدم ثم اربط النتيجة هنا.",
        "pr_blood_col": "المؤشر", "pr_blood_v": "القيمة",
        "pr_t": "اختبار",
        "pr_no_records": "لا توجد تحاليل بعد — ابدأ فحص الأعراض من الصفحة الرئيسية.",
        "pr_go_chat": "ابدأ فحص الأعراض",
        "bl_sn": "طبيعي", "bl_sl": "منخفض", "bl_sh": "مرتفع",
        "hs_h": "سجل التقييمات 📄",
        "hs_sub": "كل تقييماتك الأولية السابقة مع إمكانية تنزيلها PDF أو مشاركتها.",
        "hs_empty": "لا توجد تحليلات بعد — ابدأ بفحص الأعراض من الصفحة الرئيسية.",
        "hs_date": "التاريخ",
        "hs_symptoms": "الأعراض",
        "hs_severity": "الشدة",
        "hs_urgency": "الخطورة",
        "hs_cond": "الأمراض المزمنة",
        "hs_meds": "الأدوية",
        "hs_dl": "⬇ PDF",
        "hs_share": "شارك",
        "hs_no_profile": "ليس لديك ملف شخصي بعد —",
        "hs_profile_link": "أنشئه من هنا",
        "pdf_doc_title": "تقرير تحليل الأعراض — SymptoSense",
        "pdf_for": "التقرير",
        "pdf_symptoms": "الأعراض",
        "pdf_conditions": "الاحتمالات المحتملة",
        "pdf_urgency": "تقييم الخطورة",
        "pdf_recs": "التوصيات",
        "pdf_disclaimer": "هذا التقرير توعوي وليس تشخيصاً طبياً نهائياً.",
        "pdf_source": "المصدر: SymptoSense (Mayo Clinic, NHS, WHO)",
        "pdf_nf": "التقرير غير موجود",
        "em_geo": "مستشفى قريب منك 📍",
        "em_geo_btn": "🔍 اعرض أقرب المستشفيات",
        "em_geo_searching": "جاري تحديد موقعك والبحث...",
        "em_geo_err": "تعذّر تحديد موقعك — تأكد من السماح بالموقع الجغرافي.",
        "em_geo_empty": "لم يتم العثور على مستشفيات قريبة.",
        "em_nearby": "أقرب المستشفيات:",
        "nav_login": "تسجيل الدخول 👤",
        "nav_myaccount": "حسابي 👤",
        "nav_health_profile": "ملفي الصحي",
        "nav_myhistory": "سجلي",
        "nav_privacy": "الخصوصية",
        "nav_logout": "تسجيل الخروج",
        "bnav_home": "الرئيسية",
        "bnav_chat": "التحليل",
        "bnav_psych": "النفسي",
        "bnav_profile": "ملفي",
        "title_login": "SymptoSense — تسجيل الدخول",
        "title_register": "SymptoSense — إنشاء حساب",
        "title_settings": "SymptoSense — إعدادات الخصوصية",
        "login_h": "مرحبًا بك مجددًا 💙",
        "login_sub": "سجّل دخولك للوصول إلى تجربتك الشخصية",
        "login_email": "البريد الإلكتروني",
        "login_pass": "كلمة المرور",
        "login_btn": "تسجيل الدخول",
        "login_noaccount": "ليس لديك حساب؟",
        "login_register": "إنشاء حساب",
        "login_error": "البريد الإلكتروني أو كلمة المرور غير صحيحة",
        "login_forgot": "نسيت كلمة المرور؟",
        "register_h": "أنشئ حسابك 💙",
        "register_sub": "ابدأ رحلتك الصحية مع SymptoSense",
        "register_name": "الاسم",
        "register_email": "البريد الإلكتروني",
        "register_pass": "كلمة المرور (٦ أحرف على الأقل)",
        "register_confirm": "تأكيد كلمة المرور",
        "register_btn": "إنشاء حساب",
        "register_hasaccount": "لديك حساب بالفعل؟",
        "register_login": "تسجيل الدخول",
        "register_error": "حدث خطأ — تأكد من صحة البيانات",
        "register_pass_mismatch": "كلمتا المرور غير متطابقتين",
        "profile_h": "ملفي الصحي 👤",
        "profile_sub": "معلوماتك الصحية اختيارية وتُستخدم فقط لتخصيص تجربتك وتحسين تحليل الأعراض عند موافقتك. يمكنك حذفها في أي وقت.",
        "profile_basic": "معلوماتي الأساسية",
        "profile_name": "الاسم",
        "profile_dob": "تاريخ الميلاد",
        "profile_gender": "الجنس",
        "profile_male": "ذكر",
        "profile_female": "أنثى",
        "profile_lang_pref": "اللغة المفضلة",
        "profile_health": "معلوماتي الصحية",
        "profile_height": "الطول (سم)",
        "profile_weight": "الوزن (كجم)",
        "profile_meds": "الأدوية الحالية",
        "profile_meds_ph": "مثال: بندول، فولتارين",
        "profile_allergies": "الحساسية",
        "profile_allergies_ph": "مثال: البنسلين",
        "profile_conditions": "الحالات الصحية",
        "profile_conditions_ph": "مثال: سكري، ضغط الدم",
        "profile_extra": "معلومات إضافية",
        "profile_extra_ph": "أي معلومات صحية أخرى تريدها حفظها",
        "profile_save": "حفظ المعلومات ✨",
        "profile_saved": "تم حفظ المعلومات بنجاح ✅",
        "profile_delete_btn": "حذف المعلومات 🗑️",
        "profile_delete_confirm": "هل أنت متأكد من حذف جميع معلوماتك الصحية؟",
        "profile_edit_btn": "تعديل معلوماتي ✏️",
        "profile_cancel": "إلغاء",
        "profile_deleted": "تم حذف المعلومات بنجاح",
        "profile_activity": "مستوى النشاط",
        "profile_completion": "اكتمال ملفك",
        "profile_completion_sub": "إكمال المعلومات يساعد على تحليل أكثر دقة",
        "profile_next_incomplete": "بقيت بعض المعلومات في ملفك",
        "profile_next_incomplete_sub": "إكمالها يساعد SymptoSense على تخصيص التحليل لك",
        "profile_next_complete": "معلوماتك جاهزة",
        "profile_next_complete_sub": "يمكنك الآن بدء تحليل الأعراض",
        "profile_next_start": "ابدأ تحليل الأعراض 🩺",
        "profile_next_continue": "أكمل معلوماتي ✨",
        "profile_history_title": "📊 تحليلاتي السابقة",
        "profile_history_empty": "لم تجرِ أي تحليلات بعد",
        "profile_symptoms_changed": "🔄 تغيّرت الأعراض؟",
        "profile_symptoms_changed_sub": "هل تغيرت الأعراض منذ آخر مرة استخدمت فيها SymptoSense؟",
        "profile_reassess": "إعادة التقييم 🔄",
        "preparing_analysis": "جاري تحضير ملخص التحليل...",
        "why_title": "لماذا هذه النتيجة؟",
        "action_title": "ماذا تفعل الآن؟",
        "action_high_1": "寻求急诊医疗 - لا تنتظر",
        "action_high_2": "اطلب سيارة إسعاف فوراً",
        "action_high_3": "لا تتأخر في زيارة المستشفى",
        "action_med_1": "حدد موعد مع طبيبك في أقرب وقت",
        "action_med_2": "راقب الأعراض وسجّل أي تغييرات",
        "action_med_3": "اتبع نصائح العناية المنزلية",
        "action_low_1": "يمكنك العناية بنفسك في المنزل",
        "action_low_2": "اشرب السوائل واسترح",
        "action_low_3": "إذا ساءت الأعراض، راجع الطبيب",
        "assess_title": "تقييم SymptoSense",
        "assess_safety": "🏥 السلامة:",
        "assess_completion": "📊 اكتمال المعلومات:",
        "assess_followup": "📅 المتابعة:",
        "assess_followup_default": "تابع الأعراض عند تغيرها",
        "assess_missing": "معلومات ناقصة",
        "questions_title": "أسئلة قد ترغب بطرحها",
        "questions_sub": "اضغط على أي سؤال لفتح المساعد:",
        "q_urgent_1": "ماذا أفعل الآن؟",
        "q_urgent_2": "هل أحتاج للمستشفى؟",
        "q_med_1": "متى أراجع الطبيب؟",
        "q_med_2": "ماذا أفعل في المنزل؟",
        "q_low_1": "كم من الوقت يستغرق الشفاء؟",
        "q_low_2": "متى أقلق؟",
        "q通用_1": "هل يمكنك شرح هذه النتيجة أكثر؟",
        "q通用_2": "ما الأسئلة التي يجب أن أسأل طبيبي؟",
        "save_profile": "💾 حفظ في ملفي الصحي",
        "save_login_required": "يجب تسجيل الدخول أولاً لحفظ المعلومات. سجّل الدخول من القائمة.",
        "save_nothing_new": "لا توجد معلومات جديدة لحفظها.",
        "save_success": "✅ تم حفظ المعلومات في ملفك الصحي بنجاح!",
        "save_error": "❌ حدث خطأ أثناء الحفظ، حاول مرة أخرى.",
        "incomplete_title": "🧪 خلينا نتأكد من شيء قبل ما أعطيك نتيجة.",
        "incomplete_q_age": "كم عمرك بالضبط؟ هذا يساعدنا على فهم حالتك بشكل أفضل.",
        "incomplete_q_gender": "ما الجنس؟ هذا مهم للتحليل الطبي.",
        "incomplete_q_duration": "متى بدأت الأعراض بالضبط؟",
        "incomplete_q_notes": "هل فيه شي ثاني تبي تضيفه؟",
        "incomplete_q_general": "محتاج معلومة إضافية صغيرة ل giving نتيجة أدق.",
        "incomplete_today": "اليوم",
        "incomplete_yesterday": "أمس",
        "incomplete_days": "عدة أيام",
        "incomplete_week": "أكثر من أسبوع",
        "incomplete_skip": "ما أتذكر بالضبط",
        "incomplete_reanalyzing": "🔄 جاري إعادة التحليل بالمعلومات الجديدة...",
        "incomplete_done": "✅ تمام، الآن عندي معلومات أفضل لفهم حالتك.",
        "activity_low": "قليل",
        "activity_moderate": "متوسط",
        "activity_high": "كثير",
        "settings_h": "إعدادات الخصوصية 🔒",
        "settings_sub": "تحكم في كيفية استخدام معلوماتك",
        "settings_assistant": "السماح باستخدام معلوماتي في المساعد",
        "settings_analysis": "السماح باستخدام معلوماتي في فحص الأعراض",
        "settings_calc": "السماح باستخدام معلوماتي في الحاسبات",
        "settings_chat": "حفظ سجل المحادثات",
        "settings_save": "حفظ الإعدادات",
        "settings_saved": "تم حفظ الإعدادات ✅",
        "smart_use_title": "✨ استخدام معلوماتي المحفوظة؟",
        "smart_use_desc": "لديك معلومات محفوظة قد تساعد في جعل النتيجة أكثر تخصيصًا.",
        "smart_use_list": "سيتم استخدام:",
        "smart_use_btn": "✨ استخدام معلوماتي",
        "smart_manual_btn": "إدخال المعلومات يدويًا",
        "smart_skip_btn": "تخطي",
        "smart_suggest_title": "💡 هل تريد اقتراحًا أكثر تخصيصًا؟",
        "smart_suggest_desc": "يمكنني استخدام بعض معلوماتك المحفوظة لتحسين الأسئلة والشرح.",
        "smart_suggest_btn": "✨ استخدم معلوماتي للحصول على اقتراح أفضل",
        "smart_decline_btn": "لا، تابع بدونها",
        "welcome_back": "مرحبًا بعودتك يا",
        "welcome_back_sub": "معلوماتك المحفوظة جاهزة لتخصيص تجربتك.",
        "no_account_sub": "أنشئ حسابك للحصول على تجربة شخصية",
        "chat_history_h": "سجل المحادثات 📋",
        "chat_history_sub": "محادثاتك السابقة مع المساعد",
        "chat_history_empty": "لا توجد محادثات بعد",
        "delete_account": "حذف الحساب",
        "delete_account_confirm": "هل أنت متأكد؟ سيتم حذف حسابك وجميع بياناتك نهائيًا.",
    },
    "en": {
        "nav_home": "Home", "nav_chat": "Symptom Check", "nav_blood": "Blood Tests",
        "nav_meds": "Medications", "nav_emergency": "Emergency", "nav_checkin": "My Tracking",
        "nav_family": "Family",
        "nav_firstaid": "First Aid", "nav_tips": "Tips", "nav_relax": "Relax",
        "nav_calculators": "Health Calculators",
        "nav_search": "Health Search",
        "nav_admin": "Dashboard", "nav_about": "About us",
        "nav_how": "How it works", "nav_features": "Features", "nav_contact": "Contact",
        "nav_profile": "My profile", "nav_history": "My history",
        "nav_explore": "Explore", "nav_q": "Medical questions", "nav_geo": "Nearest hospital",
        "nav_aware": "Awareness", "nav_blog": "Blog",
        "footer_note": "SymptoSense © 2026 — Health awareness only; not a substitute for professional medical advice.",
        "footer_emergency": "In an emergency call an ambulance directly: <b>997</b> (Saudi Arabia)",
        "footer_tag": "Health awareness starts with a step.",
        "footer_privacy": "Privacy",
        "footer_terms": "Terms",
        "footer_contact": "Contact us",
        "footer_copy": "© 2026 SymptoSense",
        "footer_slogan": "Your smart health assistant",
        "footer_synopsis_t": "About the project",
        "footer_synopsis_d": "SymptoSense is a smart health platform that simplifies access to reliable health information and tools, helping you understand your condition more clearly.",
        "footer_owner_t": "About us",
        "footer_owner_name": "Remas Hameed Alsolami 🤍",
        "footer_owner_role": "Data Science and Analytics student and founder of SymptoSense",
        "footer_contact_t": "Contact",
        "footer_wa_btn": "💬 Chat with me on Telegram",
        "footer_love": "Made with love 🤍 by",
        "footer_love_name": "Remas",
        "footer_copy_full": "© 2026 SymptoSense — All rights reserved",
        "keywords": "symptom checker, symptoms analysis, preliminary assessment, health, medicine, Saudi hospitals, SymptoSense",
        "title_landing": "SymptoSense — AI Symptom Checker",
        "title_chat": "SymptoSense — Symptom Checker",
        "title_blood": "SymptoSense — Blood Test Analysis",
        "title_meds": "SymptoSense — Medication Checker",
        "title_firstaid": "SymptoSense — First Aid",
        "title_tips": "SymptoSense — Health Tips",
        "title_relax": "SymptoSense — Relaxation",
        "title_emergency": "SymptoSense — Emergency Numbers",
        "title_checkin": "SymptoSense — Daily Tracking",
        "title_calculators": "SymptoSense — Health Calculators",
        "title_about": "SymptoSense — About the site",
        "title_about_us": "SymptoSense — About us",
        "desc": "Your smart assistant for analyzing symptoms and getting an initial health assessment based on trusted medical sources.",
        "w_title": "Welcome to SymptoSense 👋",
        "w_sub": "Your smart assistant for analyzing symptoms and assessing your health. Choose your language to continue.",
        "w_pick": "Pick your language to continue 👇",
        "w_taphint": "Tap anywhere to continue",
        "lang_btn": "Choose language",
        "w_ar_l": "العربية 🇸🇦",
        "w_ar_d": "Continue in Arabic",
        "w_en_l": "English 🇬🇧",
        "w_en_d": "Continue in English",
        "home_hero_t1": "How are you feeling?",
        "home_hero_t2": "Let's find out together 🩺",
        "home_hero_p": "Enter your symptoms in a few simple steps and get an initial smart assessment based on the system's analysis model — plus medication warnings, nearest hospitals, blood test analysis, and first aid.",
        "home_btn_start": "Start the check now 🚀",
        "home_btn_blood": "Blood test analysis 📋",
        "home_features_title": "What do you need? 🧰",
        "home_f_t": "Symptom Check", "home_f_p": "Enter your symptoms and get an initial smart assessment with urgency level (Mild / Appointment / Emergency).",
        "home_b_t": "Blood Test Analysis", "home_b_p": "Upload a photo or PDF of your CBC and get an interpretation of values and indicators.",
        "home_m_t": "Medication Check", "home_m_p": "Medication warnings, interactions, and safe-use guidance.",
        "home_h_t": "Nearest Hospital", "home_h_p": "Based on your location, we show the nearest health facilities with distance and a map link.",
        "home_q_t": "Questions for Your Doctor", "home_q_p": "Ready smart questions to ask your doctor, with danger signs and when to follow up.",
        "home_fa_t": "First Aid", "home_fa_p": "Clear, quick steps for everyday emergencies.",
        "home_calc_t": "Health Calculators", "home_calc_p": "Compute common health metrics (BMI, calories, sugar & more) with simple results.",
        "home_t_t": "Health Tips", "home_t_p": "Practical daily tips for better health for you and your family.",
        "home_r_t": "Relaxation & Breathing", "home_r_p": "Breathing and calm exercises to relieve stress and anxiety.",
        "home_e_t": "Emergency Numbers", "home_e_p": "Important numbers ready for emergencies (997, 911, 937...).",
        "home_c_t": "Daily Tracking", "home_c_p": "Record your state daily and track your improvement with a clear chart.",
        "home_how_title": "How does it work?",
        "home_s1_t": "Enter your info", "home_s1_p": "Age, gender, symptoms, duration, and severity.",
        "home_s2_t": "The system analyzes the info", "home_s2_p": "A smart system analyzes the entered information using the analysis model and the medical sources used in the system.",
        "home_s3_t": "Get an initial assessment", "home_s3_p": "Urgency level, likely conditions, and appropriate recommendations.",
        "home_warn": "⚠️ <b>Note:</b> This website is for health awareness only and is not a final medical diagnosis. If you have dangerous symptoms (severe chest pain, difficulty breathing, heavy bleeding, loss of consciousness) call an ambulance immediately at <b>997</b>.",
        "home_badge": "Your AI-Powered Health Assistant",
        "home_h1": "Welcome to",
        "home_h1b": "SymptoSense",
        "home_sub": "Your smart health assistant to understand your symptoms",
        "home_desc": "Enter your symptoms in a few simple steps and get an initial smart assessment that helps you understand your condition and know the right next step — while keeping your privacy.",
        "home_btn1": "Start assessment now ✨",
        "home_btn2": "How does SymptoSense work?",
        "home_ph1": "Understand your symptoms",
        "home_ph2": "Take care of your health",
        "home_services": "Health Services 🩺",
        "home_services_sub": "Smart tools to help you understand your health and take the right next step.",
        "home_more": "Show more",
        "home_less": "Show less",
        "home_f_t": "Symptom Check",
        "home_f_p": "Enter your symptoms and get an initial assessment that helps you understand your condition.",
        "home_f_btn": "Start now",
        "home_b_t": "Blood Test Analysis",
        "home_b_p": "Upload your blood test report and get a simple explanation of the results.",
        "home_b_btn": "Analyze now",
        "home_m_t": "Drug Search",
        "home_m_p": "Search for safe information about medications, doses, and how to use them.",
        "home_m_btn": "Search now",
        "home_calc_t": "Health Calculators",
        "home_calc_p": "Calculate health indicators like BMI, calories, and more.",
        "home_calc_btn": "Calculate now",
        "home_mh_t": "My Mental Health",
        "home_mh_p": "A private space to talk about your feelings, anxiety, and stress with your smart assistant.",
        "home_mh_btn": "Talk to the assistant 🤍",
        "home_asst_t": "Smart Assistant",
        "home_asst_sub": "Ask SymptoSense about anything health-related — always available whenever you need.",
        "home_asst_btn": "🤖 Ask SymptoSense",
        "home_quick_t": "Quick Help 🚨",
        "home_quick_hosp_t": "Nearest Hospital",
        "home_quick_hosp_p": "Find the nearest health facility suitable for your location.",
        "home_quick_em_t": "Emergency Numbers",
        "home_quick_em_p": "Quick access to the important emergency numbers.",
        "home_care_t": "Care & Support 💙",
        "home_care_mh_t": "Mental Health",
        "home_care_relax_t": "Relax & Calm",
        "home_care_check_t": "Daily Check-in",
        "home_care_tips_t": "Health Tips",
        "home_how": "How does SymptoSense work?",
        "home_step1_t": "Enter your symptoms",
        "home_step1_p": "Describe your health condition in simple steps.",
        "home_step2_t": "Answer questions",
        "home_step2_p": "Answer smart questions that help understand your condition better.",
        "home_step3_t": "Get an initial assessment",
        "home_step3_p": "Get information and guidance that help you know the next step.",
        "home_warn2": "<b>Note:</b> The information provided in SymptoSense is for health awareness and is not a substitute for a doctor's consultation. In emergency cases or severe symptoms, please contact emergency services or visit the nearest health facility.",
        "ab_t1": "What is SymptoSense?",
        "about_us_kicker": "Our story",
        "about_us_title": "About us",
        "about_us_p1": "My passion began with a simple question: How can technology feel closer to people?",
        "about_us_p2": "I am Remas Hameed Alsolami, a Data Science and Analytics student who is passionate about building technology solutions that make a genuine difference in people's lives.",
        "about_us_p3": "That is where my idea began: to use what I learn in data science and technology to build a solution that makes health symptoms clearer and easier to understand. My goal was not simply to create a website, but to design an experience that gives people initial knowledge, helps them understand what they are feeling, and supports them in choosing the right next step with greater awareness.",
        "about_us_p4": "I believe technology has its greatest impact when it makes people's lives simpler, their awareness greater, and their decisions smarter.",
        "about_us_name": "Remas Hameed Alsolami",
        "about_us_role": "Data Science and Analytics student and founder of SymptoSense",
        "about_us_contact": "Contact:",
        "about_us_img1_alt": "A smartphone surrounded by health symbols representing symptom understanding and health awareness",
        "about_us_img2_alt": "A digital health illustration representing SymptoSense",
        "ab_p1": "SymptoSense is an AI-powered health awareness assistant that helps you understand your symptoms and get an initial assessment based on trusted medical sources (Mayo Clinic, NHS, WHO, CDC).",
        "ab_p2": "The site provides: symptom analysis with urgency assessment, medication warnings and interactions, nearest hospitals based on your location, blood test analysis, first aid, and daily health tips.",
        "ab_p3": "Analysis runs through an AI model (Llama via Groq) with a rule-based verification layer and a machine-learning model for probabilities — all as a supportive awareness tool.",
        "ab_p4": "This website is <b>not a final medical diagnosis</b> and not a substitute for consulting a specialist. If you have any dangerous symptom, call an ambulance immediately.",
        "ab_srcs": "Trusted medical sources:",
        "ab_srcs_p": "Mayo Clinic, NHS, World Health Organization (WHO), CDC, MedlinePlus — mentioned within each recommendation with its link.",
        "ab_note": "Your data is stored anonymously (no identity) and used only to improve the service and statistics.",
        "ab_hero_sub": "Your smart assistant to understand your health",
        "ab_hero_p": "SymptoSense is an awareness tool that helps you understand your symptoms, analyze blood tests, get medication information, and health guidance — based on trusted medical sources — to help you take the right step for your health.",
        "ab_alert": "⚠️ SymptoSense is a supportive awareness tool and not a substitute for a doctor. For dangerous symptoms call an ambulance at <b>997</b> immediately.",
        "ab_services_h": "🧰 What does SymptoSense offer?",
        "ab_sv1_t": "Symptom Analysis", "ab_sv1_p": "An initial assessment with urgency level, likely conditions, and recommendations.",
        "ab_sv2_t": "Blood Test Analysis", "ab_sv2_p": "Upload a CBC photo and get interpretation of values and reference ranges.",
        "ab_sv3_t": "Medication Info", "ab_sv3_p": "Uses, warnings, and interactions with safe-use alerts.",
        "ab_sv4_t": "Emergency Numbers", "ab_sv4_p": "Important ambulance and emergency numbers plus danger signs.",
        "ab_sv5_t": "Nearest Hospital", "ab_sv5_p": "Find the nearest health facilities based on your location with a map link.",
        "ab_sv6_t": "Health Tips", "ab_sv6_p": "Practical daily tips on nutrition, sleep, activity, and prevention.",
        "ab_how_h": "⚙️ How does it work?",
        "ab_how1_t": "Enter your info", "ab_how1_p": "Age, gender, symptoms, duration, and severity.",
        "ab_how2_t": "The system analyzes the info", "ab_how2_p": "A smart system analyzes the entered information using the analysis model and the medical sources used in the system.",
        "ab_how3_t": "Get an initial assessment", "ab_how3_p": "Urgency level, likely conditions, and appropriate recommendations.",
        "ab_srcs_h": "📚 Our medical sources",
        "ab_srcs_p2": "We rely on trusted, recognized medical sources, and the source is mentioned with each recommendation and its link.",
        "ab_priv_h": "🔐 Privacy",
        "ab_priv_p": "We respect your privacy: your assessments are stored under an internal identifier that does not include your identity. Data is used only to improve the service and is never shared with third parties.",
        "chat_sub": "Smart analysis assistant",
        "chat_head_p": "Smart analysis assistant — English 🇬🇧",
        "chat_muted": "Awareness only, not a final diagnosis — see a doctor if in any doubt.",
        "title_profile": "SymptoSense — My Profile",
        "title_history": "SymptoSense — My History",
        "pr_h": "My Profile 👤",
        "pr_sub": "Save your details once and they will be used automatically in every analysis and included in your results.",
        "pr_age": "Age",
        "pr_gender": "Gender",
        "pr_g_male": "Male", "pr_g_female": "Female",
        "pr_conditions": "Chronic conditions (comma separated)",
        "pr_meds": "Regular medications (comma separated)",
        "pr_allergies": "Allergies (comma separated)",
        "pr_save": "💾 Save profile",
        "pr_saved": "✅ Profile saved successfully",
        "pr_err": "An error occurred while saving",
        "pr_load_err": "Error reading profile",
        "pr_dash": "📊 Your health dashboard",
        "pr_dash_sub": "Your analyses and tests in one place.",
        "pr_count_an": "Total analyses",
        "pr_count_hi": "Emergency", "pr_count_med": "Medium", "pr_count_lo": "Mild",
        "pr_blood_h": "🧪 Blood tests",
        "pr_blood_latest": "Latest blood test",
        "pr_blood_compare": "📈 Test comparison",
        "pr_blood_empty": "No blood tests uploaded yet — use the blood analysis page and link the result here.",
        "pr_blood_col": "Indicator", "pr_blood_v": "Value",
        "pr_t": "Test",
        "pr_no_records": "No analyses yet — start a symptom check from the home page.",
        "pr_go_chat": "Start symptom check",
        "bl_sn": "Normal", "bl_sl": "Low", "bl_sh": "High",
        "hs_h": "Assessment History 📄",
        "hs_sub": "All your previous initial assessments with PDF download and sharing options.",
        "hs_empty": "No analyses yet — start a symptom check from the home page.",
        "hs_date": "Date",
        "hs_symptoms": "Symptoms",
        "hs_severity": "Severity",
        "hs_urgency": "Urgency",
        "hs_cond": "Chronic conditions",
        "hs_meds": "Medications",
        "hs_dl": "⬇ PDF",
        "hs_share": "Share",
        "hs_no_profile": "You have no profile yet —",
        "hs_profile_link": "create one here",
        "pdf_doc_title": "Symptom Analysis Report — SymptoSense",
        "pdf_for": "Report",
        "pdf_symptoms": "Symptoms",
        "pdf_conditions": "Possible conditions",
        "pdf_urgency": "Urgency assessment",
        "pdf_recs": "Recommendations",
        "pdf_disclaimer": "This report is awareness information, not a final medical diagnosis.",
        "pdf_source": "Source: SymptoSense (Mayo Clinic, NHS, WHO)",
        "pdf_nf": "Report not found",
        "em_geo": "A hospital near you 📍",
        "em_geo_btn": "🔍 Show nearest hospitals",
        "em_geo_searching": "Locating you and searching...",
        "em_geo_err": "Could not locate you — please allow location access.",
        "em_geo_empty": "No nearby hospitals found.",
        "em_nearby": "Nearest hospitals:",
        "nav_login": "Login 👤",
        "nav_myaccount": "My Account 👤",
        "nav_health_profile": "Health Profile",
        "nav_myhistory": "My History",
        "nav_privacy": "Privacy",
        "nav_logout": "Logout",
        "bnav_home": "Home",
        "bnav_chat": "Analyze",
        "bnav_psych": "Mental",
        "bnav_profile": "Profile",
        "title_login": "SymptoSense — Login",
        "title_register": "SymptoSense — Register",
        "title_settings": "SymptoSense — Privacy Settings",
        "login_h": "Welcome back 💙",
        "login_sub": "Sign in to access your personalized experience",
        "login_email": "Email",
        "login_pass": "Password",
        "login_btn": "Sign In",
        "login_noaccount": "Don't have an account?",
        "login_register": "Create one",
        "login_error": "Invalid email or password",
        "login_forgot": "Forgot password?",
        "register_h": "Create your account 💙",
        "register_sub": "Start your health journey with SymptoSense",
        "register_name": "Name",
        "register_email": "Email",
        "register_pass": "Password (min 6 characters)",
        "register_confirm": "Confirm password",
        "register_btn": "Create Account",
        "register_hasaccount": "Already have an account?",
        "register_login": "Sign In",
        "register_error": "An error occurred — please check your details",
        "register_pass_mismatch": "Passwords do not match",
        "profile_h": "Health Profile 👤",
        "profile_sub": "Your health information is optional and is used only to personalize your experience and improve symptom analysis when you allow it. You can delete it at any time.",
        "profile_basic": "My Basic Info",
        "profile_name": "Name",
        "profile_dob": "Date of Birth",
        "profile_gender": "Gender",
        "profile_male": "Male",
        "profile_female": "Female",
        "profile_lang_pref": "Preferred Language",
        "profile_health": "My Health Info",
        "profile_height": "Height (cm)",
        "profile_weight": "Weight (kg)",
        "profile_meds": "Current Medications",
        "profile_meds_ph": "e.g. Paracetamol, Ibuprofen",
        "profile_allergies": "Allergies",
        "profile_allergies_ph": "e.g. Penicillin",
        "profile_conditions": "Health Conditions",
        "profile_conditions_ph": "e.g. Diabetes, High blood pressure",
        "profile_extra": "Additional Information",
        "profile_extra_ph": "Any other health information you'd like to save",
        "profile_save": "Save Information ✨",
        "profile_saved": "Information saved successfully ✅",
        "profile_delete_btn": "Delete Information 🗑️",
        "profile_delete_confirm": "Are you sure you want to delete all your health information?",
        "profile_edit_btn": "Edit my info ✏️",
        "profile_cancel": "Cancel",
        "profile_deleted": "Information deleted successfully",
        "profile_activity": "Activity Level",
        "profile_completion": "Profile Completion",
        "profile_completion_sub": "Completing your info helps generate more accurate analysis",
        "profile_next_incomplete": "Some info is missing from your profile",
        "profile_next_incomplete_sub": "Completing it helps SymptoSense personalize your analysis",
        "profile_next_complete": "Your profile is ready",
        "profile_next_complete_sub": "You can now start symptom analysis",
        "profile_next_start": "Start symptom analysis 🩺",
        "profile_next_continue": "Complete my info ✨",
        "profile_history_title": "📊 My Previous Analyses",
        "profile_history_empty": "No analyses yet",
        "profile_symptoms_changed": "🔄 Symptoms changed?",
        "profile_symptoms_changed_sub": "Have your symptoms changed since you last used SymptoSense?",
        "profile_reassess": "Reassess 🔄",
        "preparing_analysis": "Preparing analysis summary...",
        "why_title": "Why This Result?",
        "action_title": "What To Do Now",
        "action_high_1": "Seek emergency medical care now",
        "action_high_2": "Call an ambulance immediately",
        "action_high_3": "Do not delay hospital visit",
        "action_med_1": "Schedule a doctor appointment soon",
        "action_med_2": "Monitor symptoms and record changes",
        "action_med_3": "Follow home care tips below",
        "action_low_1": "You can manage with home care",
        "action_low_2": "Rest and stay hydrated",
        "action_low_3": "See a doctor if symptoms worsen",
        "assess_title": "SymptoSense Assessment",
        "assess_safety": "🏥 Safety:",
        "assess_completion": "📊 Info Completeness:",
        "assess_followup": "📅 Follow-up:",
        "assess_followup_default": "Monitor symptoms if they change",
        "assess_missing": "Missing information",
        "questions_title": "Questions You Might Ask",
        "questions_sub": "Click any question to open the assistant:",
        "q_urgent_1": "What should I do right now?",
        "q_urgent_2": "Do I need to go to the hospital?",
        "q_med_1": "When should I see a doctor?",
        "q_med_2": "What can I do at home?",
        "q_low_1": "How long will recovery take?",
        "q_low_2": "When should I worry?",
        "q通用_1": "Can you explain more about this result?",
        "q通用_2": "What questions should I ask my doctor?",
        "save_profile": "💾 Save to My Profile",
        "save_login_required": "Please log in first to save information. Log in from the menu.",
        "save_nothing_new": "No new information to save.",
        "save_success": "✅ Information saved to your health profile!",
        "save_error": "❌ Error saving. Please try again.",
        "incomplete_title": "🧪 Let me make sure I have enough info before giving you a result.",
        "incomplete_q_age": "How old are you exactly? This helps us understand your condition better.",
        "incomplete_q_gender": "What is your gender? This is important for medical analysis.",
        "incomplete_q_duration": "When exactly did the symptoms start?",
        "incomplete_q_notes": "Is there anything else you'd like to add?",
        "incomplete_q_general": "I need a small piece of info to give you a more accurate result.",
        "incomplete_today": "Today",
        "incomplete_yesterday": "Yesterday",
        "incomplete_days": "Several days ago",
        "incomplete_week": "More than a week ago",
        "incomplete_skip": "I don't remember exactly",
        "incomplete_reanalyzing": "🔄 Re-analyzing with the new information...",
        "incomplete_done": "✅ Great, now I have better info to understand your condition.",
        "activity_low": "Low",
        "activity_moderate": "Moderate",
        "activity_high": "High",
        "settings_h": "Privacy Settings 🔒",
        "settings_sub": "Control how your information is used",
        "settings_assistant": "Allow using my information in the assistant",
        "settings_analysis": "Allow using my information in symptom analysis",
        "settings_calc": "Allow using my information in calculators",
        "settings_chat": "Save conversation history",
        "settings_save": "Save Settings",
        "settings_saved": "Settings saved successfully ✅",
        "smart_use_title": "✨ Use my saved information?",
        "smart_use_desc": "You have saved information that could help make the result more personalized.",
        "smart_use_list": "The following will be used:",
        "smart_use_btn": "✨ Use my information",
        "smart_manual_btn": "Enter information manually",
        "smart_skip_btn": "Skip",
        "smart_suggest_title": "💡 Want a more personalized suggestion?",
        "smart_suggest_desc": "I can use some of your saved information to improve the questions and explanation.",
        "smart_suggest_btn": "✨ Use my information for a better suggestion",
        "smart_decline_btn": "No, continue without it",
        "welcome_back": "Welcome back,",
        "welcome_back_sub": "Your saved information is ready to personalize your experience.",
        "no_account_sub": "Create your account for a personalized experience",
        "chat_history_h": "Chat History 📋",
        "chat_history_sub": "Your previous conversations with the assistant",
        "chat_history_empty": "No conversations yet",
        "delete_account": "Delete Account",
        "delete_account_confirm": "Are you sure? Your account and all data will be permanently deleted.",
    },
}


def _t(key):
    d = L.get(_lang(), L["ar"])
    return d.get(key, L["ar"].get(key, key))


def _nav():
    from html import escape
    lang = _lang()
    path = request.path
    user = _ss_user()
    ar = lang == "ar"
    links = [
        ("/home", "الرئيسية" if ar else "Home"),
        ("/chat", "تحليل الأعراض" if ar else "Symptom analysis"),
    ]
    if user:
        links.append(("/profile", "الملف الشخصي" if ar else "Profile"))
    html = '<nav class="nav"><a href="/home" class="logo" dir="ltr">🩺 Sympto<span>Sense</span></a><div class="links">'
    for href, label in links:
        cls = ' class="on"' if path == href else ""
        html += '<a href="%s"%s>%s</a>' % (href, cls, label)
    html += '<a href="#" class="v2-nav-cta" onclick="asstToggle();return false;">🤖 %s</a>' % ("المساعد الذكي" if ar else "AI assistant")
    html += ('<div class="dd"><button type="button" class="dd-btn v2-services-btn" aria-haspopup="menu" aria-expanded="false" onclick="toggleDD(event)">%s <span aria-hidden="true">⌄</span></button>'
             '<div class="dd-menu v2-services-menu" role="menu">'
             '<a href="/blood">🧪 %s</a><a href="/meds">💊 %s</a><a href="/calculators">🧮 %s</a>'
             '<a href="/search">🔎 %s</a><a href="/sources">📚 %s</a><a href="/family">👨‍👩‍👧 %s</a>'
             '<a href="/tips">💡 %s</a><a href="/emergency">🚑 %s</a><a href="/about-us">ℹ️ %s</a>'
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
        html += ('<div class="dd account-dd">'
                 '<a href="/profile" class="account-profile-link" aria-label="%s">'
                 '<span class="account-avatar" aria-hidden="true">👤</span>'
                 '<span class="account-btn-copy"><span class="account-name">%s</span><span class="account-label">%s</span></span>'
                 '</a>'
                 '<button type="button" class="account-menu-toggle" aria-label="%s" aria-haspopup="menu" aria-expanded="false" onclick="toggleDD(event)">▼</button>'
                 '<div class="dd-menu account-menu" role="menu">'
                 '<div class="account-menu-head"><span class="account-avatar" aria-hidden="true">👤</span><div><strong>%s</strong><small>%s</small></div></div>'
                 '<a href="/profile" role="menuitem">👤 %s</a>'
                 '<a href="/manage" role="menuitem">📝 %s</a>'
                 '<a href="/history" role="menuitem">📋 %s</a>'
                 '<a href="/family" role="menuitem">👨‍👩‍👧 %s</a>'
                 '<a href="/settings" role="menuitem">⚙️ %s</a>'
                 '%s'
                 '<a href="/logout" role="menuitem" class="account-logout">🚪 %s</a>'
                 '</div></div>') % (
            profile_label, user_name, profile_label,
            ("خيارات الحساب" if lang == "ar" else "Account options"),
            user_name, user_email, profile_label, health_label,
            _t("nav_myhistory"), family_label, _t("nav_privacy"), admin_menu_link, _t("nav_logout"),
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
        '<span aria-hidden="true">🩺</span><b>Sympto<span>Sense</span></b></a>'
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
        '<div class="footer" id="contact">'
        '<div class="f-brand">Sympto<span>Sense</span> 💙</div>'
        '<p class="f-tag">%s</p>'
        '<div class="f-grid">'
        '<div class="f-sec"><h4>%s</h4><p>%s</p></div>'
        '<div class="f-sec"><h4>%s</h4><a href="/about-us" class="f-owner">%s<br>%s</a></div>'
        '<div class="f-sec"><h4>%s</h4>'
        '<a class="f-tg" href="%s" target="_blank" rel="noopener">%s</a>'
        '</div>'
        '</div>'
        '<div class="f-links">'
        '<a href="/about-us">%s</a>'
        '<a href="/privacy">%s</a>'
        '<a href="/terms">%s</a>'
        '<a href="/sources">%s</a>'
        '%s'
        '</div>'
        '<p class="f-love">%s <b>%s</b></p>'
        '<p class="f-copy">%s</p>'
        '</div>'
    ) % (_t("footer_slogan"),
         _t("footer_synopsis_t"), _t("footer_synopsis_d"),
         _t("footer_owner_t"), _t("footer_owner_name"), _t("footer_owner_role"),
         _t("footer_contact_t"), tg, _t("footer_wa_btn"),
         _t("nav_about"), _t("footer_privacy"), _t("footer_terms"),
         ("المصادر الطبية" if _lang() == "ar" else "Medical sources"),
         ('<a href="/admin">%s</a>' % _t("nav_admin")) if (_ss_user() or {}).get("role") == "admin" else "",
         _t("footer_love"), _t("footer_love_name"), _t("footer_copy_full"))


def _page(title, body, desc=None, bare=False, extra_css=""):
    if not desc:
        desc = _t("desc")
    lang = _lang()
    base = _site_url()
    gsc = os.environ.get("GOOGLE_SITE_VERIFICATION", "")
    gsc_tag = (
        '<meta name="google-site-verification" content="%s">' % gsc
        if gsc
        else ""
    )
    ast = CT["en" if lang == "en" else "ar"]
    body_class = ""
    try:
        prefs = advanced_features.get_preferences(_ss_user_id()) if _ss_user_id() else {"accessibility_mode": False}
        if prefs.get("accessibility_mode"):
            body_class = "ss-accessibility"
    except Exception:
        body_class = ""
    return (
        PAGE_FRAME
        .replace("__LANG__", "en" if lang == "en" else "ar")
        .replace("__DIR__", "ltr" if lang == "en" else "rtl")
        .replace("__BODY_CLASS__", body_class)
        .replace("__TITLE__", title)
        .replace("__DESC__", desc)
        .replace("__KEYWORDS__", _t("keywords"))
        .replace("__CANONICAL__", base + request.path)
        .replace("__OG_IMAGE__", base + "/static/images/symptosense-social-preview.png")
        .replace("__GSC_TAG__", gsc_tag)
        .replace("__CSS__", BASE_CSS + V2_CSS + extra_css + PREMIUM_POLISH_CSS)
        .replace("__NAV__", "" if bare else _nav())
        .replace("__FOOTER__", "" if bare else _footer())
        .replace("__BNAV_HOME__", _t("bnav_home"))
        .replace("__BNAV_CHAT__", _t("bnav_chat"))
        .replace("__BNAV_PSYCH__", _t("bnav_psych"))
        .replace("__BNAV_PROFILE__", _t("bnav_profile"))
        .replace("__AST_TITLE__", ast["asst_title"])
        .replace("__AST_SUB__", ast["asst_sub"])
        .replace("__AST_GREET__", ast["asst_greet"])
        .replace("__AST_PH__", ast["asst_ph"])
        .replace("__AST_DISC__", ast["asst_disc"])
        .replace("__AST_MH_ANIM__", ast["asst_mh_anim"])
        .replace("__AST_EXPLAIN_ASK__", ast["asst_explain_ask"])
        .replace("__AST_T__", json.dumps(ast, ensure_ascii=False))
        .replace("__BODY__", body)
    )


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

WELCOME_CSS = """
body { font-family: 'Poppins', 'Cairo', 'Segoe UI', Tahoma, sans-serif; background: #FFFFFF; color: #123B70; }
.w-container { max-width: 1200px; margin: 0 auto; padding: 0 18px; }
.w-nav { position: sticky; top: 0; z-index: 70; background: #FFFFFF; display: flex; align-items: center; justify-content: space-between; padding: 14px 34px; border-bottom: 1px solid #DCEBFA; gap: 10px; }
.w-logo { display: flex; align-items: center; gap: 9px; font-size: 21px; font-weight: 800; cursor: pointer; white-space: nowrap; flex: 0 0 auto; }
.w-logo .sympto { color: #123B70; }
.w-logo .sense { color: #1976D2; }
.w-links { display: flex; gap: 26px; align-items: center; }
.w-links a { position: relative; color: #123B70; font-size: 15px; font-weight: 500; padding-bottom: 6px; }
.w-links a:hover { color: #1976D2; }
.w-links a.on { color: #1976D2; font-weight: 700; }
.w-links a.on::after { content: ''; position: absolute; left: 0; right: 0; bottom: 0; height: 3px; border-radius: 3px; background: #1976D2; }
.w-menu-btn { display: none; align-items: center; justify-content: center; width: 40px; height: 40px; border: 1.5px solid #DCEBFA; border-radius: 12px; background: #F5F9FF; color: #123B70; font-size: 19px; cursor: pointer; flex: 0 0 auto; }
.hero-wrap { padding: 22px 16px 8px; max-width: 100%; }
.hero-card { display: flex; align-items: center; gap: 30px; background: linear-gradient(120deg, #E5F2FF 0%, #FFFFFF 70%); border: 1px solid #DCEBFA; border-radius: 34px; padding: 52px 46px; box-shadow: 0 18px 50px rgba(25,118,210,.10); max-width: 100%; overflow: hidden; }
.hero-left { flex: 1.15; min-width: 0; }
.badge { display: inline-flex; align-items: center; gap: 8px; background: #EAF4FF; color: #123B70; font-size: 13px; font-weight: 600; border-radius: 999px; padding: 8px 16px; margin-bottom: 22px; max-width: 100%; }
.hero-left h1 { font-size: clamp(24px, 6.5vw, 44px); line-height: 1.18; color: #123B70; margin: 0 0 6px; }
.brand-big { display: block; font-size: clamp(30px, 9vw, 68px); font-weight: 800; color: #1976D2; letter-spacing: -.5px; word-break: break-word; }
.pulse-line { display: flex; align-items: center; gap: 10px; color: #1976D2; font-size: 20px; margin: 8px 0 14px; }
.pulse-line .ln { flex: 0 0 54px; height: 2px; border-radius: 2px; background: linear-gradient(90deg, #1976D2, transparent); }
.hero-sub { font-size: clamp(14.5px, 3.2vw, 18px); color: #123B70; opacity: .85; max-width: 520px; margin-bottom: 24px; line-height: 1.7; }
.wmsg { display: grid; }
.wmsg-item { grid-area: 1 / 1; opacity: 0; transform: translateY(10px); transition: opacity 1s ease, transform 1s ease; }
.wmsg-item.active { opacity: 1; transform: translateY(0); }
.wmsg-item .wflag { display: inline-block; vertical-align: middle; margin-right: 6px; font-size: 26px; line-height: 1; }
.flag-badge.sm { width: 27px; height: 27px; border-radius: 50%; background: linear-gradient(135deg, #1976D2, #123B70); color: #FFFFFF; font-size: 11px; font-weight: 800; letter-spacing: .5px; display: inline-flex; align-items: center; justify-content: center; margin: 0; vertical-align: middle; }
.mini-features { display: grid; grid-template-columns: repeat(4, auto); gap: 22px; justify-content: start; }
.mf { text-align: center; }
.mf .ic { width: 54px; height: 54px; margin: 0 auto 8px; display: flex; align-items: center; justify-content: center; font-size: 26px; background: #EAF4FF; border-radius: 18px; }
.mf span { font-size: 13px; font-weight: 600; color: #123B70; }
.hero-right { flex: 1; display: flex; align-items: center; justify-content: center; position: relative; min-height: 420px; }
.globe { position: absolute; width: 360px; height: 360px; border-radius: 50%; background: radial-gradient(circle, rgba(25,118,210,.14) 0%, rgba(25,118,210,.04) 55%, transparent 70%); }
.globe::before, .globe::after { content: ''; position: absolute; border-radius: 50%; border: 1.5px solid rgba(25,118,210,.18); inset: 12%; }
.globe::after { inset: 26%; }
.float-ic { position: absolute; font-size: 34px; filter: drop-shadow(0 6px 14px rgba(25,118,210,.25)); animation: floatic 5s ease-in-out infinite; }
.float-ic.f1 { top: 6%; left: 6%; animation-delay: 0s; }
.float-ic.f2 { top: 2%; right: 14%; animation-delay: 1.1s; }
.float-ic.f3 { bottom: 12%; left: 10%; animation-delay: 2s; }
.float-ic.f4 { bottom: 4%; right: 6%; animation-delay: .6s; }
.float-ic.f5 { top: 38%; left: 0; animation-delay: 1.6s; }
.float-ic.f6 { top: 34%; right: 0; animation-delay: .3s; }
@keyframes floatic { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-12px); } }
.phone { width: 214px; height: 424px; background: #123B70; border-radius: 40px; padding: 12px; box-shadow: 0 34px 70px rgba(18,59,112,.40), inset 0 0 0 2px rgba(255,255,255,.12); position: relative; z-index: 2; }
.phone-screen { width: 100%; height: 100%; border-radius: 30px; background: linear-gradient(180deg, #EAF4FF 0%, #FFFFFF 100%); display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: 20px; }
.phone-heart { width: 74px; height: 74px; border-radius: 50%; background: #FFFFFF; box-shadow: 0 10px 26px rgba(25,118,210,.30); display: flex; align-items: center; justify-content: center; font-size: 36px; margin-bottom: 18px; }
.phone-screen p { color: #123B70; font-size: 15px; font-weight: 600; line-height: 1.7; }
.lang-section { padding: 36px 16px 48px; text-align: center; }
.lang-section h2 { color: #123B70; font-size: clamp(22px, 5vw, 30px); font-weight: 800; margin-bottom: 4px; }
.lang-section .muted { color: #64748b; font-size: 15px; margin-bottom: 24px; }
.lang-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; max-width: 660px; margin: 0 auto; }
.lang-tile { position: relative; display: flex; flex-direction: column; align-items: center; gap: 6px; justify-content: center; background: #FFFFFF; border: 2px solid #DCEBFA; border-radius: 22px; padding: 30px 22px; font-family: inherit; cursor: pointer; box-shadow: 0 6px 18px rgba(25,118,210,.08); transition: transform .2s ease, background .3s ease, box-shadow .2s ease, border-color .3s ease; }
.lang-tile .fl { font-size: 46px; line-height: 1; margin-bottom: 6px; }
.lang-badge { width: 58px; height: 58px; border-radius: 50%; background: #EAF4FF; color: #1976D2; font-size: 17px; font-weight: 800; letter-spacing: 1px; display: flex; align-items: center; justify-content: center; margin: 0 auto; transition: background .3s ease, color .3s ease; }
.lang-tile .lt { font-size: 23px; font-weight: 800; color: #123B70; transition: color .3s ease; }
.lang-tile .ld { font-size: 14px; color: #5F7185; transition: color .3s ease; }
.lang-tile .ck { position: absolute; top: 12px; right: 14px; width: 26px; height: 26px; border-radius: 50%; background: #FFFFFF; color: #1976D2; font-size: 15px; font-weight: 800; display: flex; align-items: center; justify-content: center; opacity: 0; transform: scale(.5); transition: opacity .2s ease, transform .25s ease, background .3s ease; }
.lang-tile:hover { background: #EAF4FF; border-color: #1976D2; transform: translateY(-3px); box-shadow: 0 12px 28px rgba(25,118,210,.15); }
.lang-tile.sel { background: #1976D2; border-color: #1976D2; box-shadow: 0 14px 34px rgba(25,118,210,.30); }
.lang-tile.sel .lt { color: #FFFFFF; }
.lang-tile.sel .ld { color: #D1FAE5; }
.lang-tile.sel .lang-badge { background: #FFFFFF; color: #1976D2; }
.lang-tile.sel .ck { background: #FFFFFF; color: #1976D2; opacity: 1; transform: scale(1); }
.w-footer { background: #123B70; color: #EAF4FF; text-align: center; padding: 34px 20px 26px; border-radius: 26px 26px 0 0; margin-top: 26px; }
.w-footer .fl { font-size: 20px; font-weight: 800; color: #FFFFFF; margin-bottom: 4px; }
.w-footer .fl em { font-style: normal; color: #6fb2ff; }
.w-footer p { font-size: 14px; margin-bottom: 14px; color: #c9dfff; }
.w-footer .wfl { display: flex; gap: 18px; justify-content: center; flex-wrap: wrap; font-size: 13px; margin-bottom: 14px; }
.w-footer .wfl a { color: #EAF4FF; }
.w-footer .wfl a:hover { color: #FFFFFF; text-decoration: underline; }
.w-footer .copy { font-size: 12px; color: #8fb4e8; }
.exit-curtain { position: fixed; z-index: 999; left: 50%; top: 50%; width: 150vmax; height: 150vmax; margin-left: -75vmax; margin-top: -75vmax; border-radius: 50%; background: radial-gradient(circle at center, #1976D2, #123B70 65%, #08235b); transform: scale(0); opacity: 0; pointer-events: none; transition: transform .9s cubic-bezier(.65,0,.35,1), opacity .55s ease; }
.exit-curtain.open { transform: scale(1); opacity: 1; }

/* ---------- Mobile-first responsive overhaul ---------- */
@media (max-width: 1200px) {
  .hero-right { min-height: 380px; }
}
@media (max-width: 900px) {
  .hero-card { flex-direction: column; padding: 34px 26px; text-align: center; }
  .hero-left { text-align: center; }
  .hero-sub { margin-left: auto; margin-right: auto; }
  .mini-features { grid-template-columns: repeat(2, auto); justify-content: center; }
  .hero-right { min-height: 320px; }
  .lang-grid { gap: 14px; }
  .lang-tile { padding: 22px 14px; }
  .lang-tile .fl { font-size: 36px; }
  .lang-tile .lt { font-size: 19px; }
}
@media (max-width: 768px) {
  .w-nav { padding: 10px 16px; min-height: 60px; max-height: 70px; }
  .w-logo { font-size: 18px; }
  .w-menu-btn { display: flex; }
  .w-links { position: absolute; top: 100%; left: 0; right: 0; background: #FFFFFF; border-bottom: 1px solid #DCEBFA; box-shadow: 0 14px 24px rgba(18,59,112,.10); flex-direction: column; align-items: stretch; gap: 0; padding: 6px 0; max-height: 0; overflow: hidden; opacity: 0; pointer-events: none; transition: max-height .25s ease, opacity .2s ease; }
  .w-links.open { max-height: 320px; opacity: 1; pointer-events: auto; }
  .w-links a { padding: 13px 22px; font-size: 15px; border-bottom: 1px solid #F0F5FC; }
  .w-links a.on::after { display: none; }
  .w-links a.on { background: #EAF4FF; }
  .hero-wrap { padding: 16px 14px 4px; }
  .hero-card { padding: 26px 18px; border-radius: 24px; gap: 20px; }
  .badge { margin-bottom: 16px; font-size: 12px; padding: 7px 14px; }
  .pulse-line { margin: 6px 0 10px; }
  .mini-features { gap: 14px; margin-top: 4px; }
  .mf .ic { width: 46px; height: 46px; font-size: 21px; border-radius: 14px; }
  .mf span { font-size: 12px; }
  .hero-right { min-height: 220px; }
  .phone { width: 148px; height: 292px; border-radius: 30px; padding: 8px; }
  .phone-screen { border-radius: 22px; padding: 12px; }
  .phone-heart { width: 52px; height: 52px; font-size: 26px; margin-bottom: 10px; }
  .phone-screen p { font-size: 12.5px; }
  .globe { width: 240px; height: 240px; }
  .float-ic { font-size: 22px; }
}
@media (max-width: 600px) {
  .mini-features { grid-template-columns: repeat(2, 1fr); width: 100%; max-width: 320px; margin: 4px auto 0; }
  .globe { display: none; }
  .float-ic { display: none; }
  .phone { width: 118px; height: 234px; border-radius: 24px; }
  .phone-heart { width: 42px; height: 42px; font-size: 20px; margin-bottom: 8px; }
  .phone-screen p { font-size: 11px; }
  .hero-right { min-height: 0; padding: 10px 0 4px; }
  .lang-grid { grid-template-columns: 1fr; max-width: 320px; }
}
@media (max-width: 480px) {
  .w-logo span:last-child { font-size: 17px; }
  .hero-left h1 { margin-bottom: 4px; }
  .hero-right { display: none; }
  .mini-features { grid-template-columns: 1fr 1fr; gap: 10px; }
  .mf .ic { width: 40px; height: 40px; font-size: 18px; margin-bottom: 5px; }
  .mf span { font-size: 11.5px; }
}
@media (max-width: 360px) {
  .w-nav { padding: 8px 12px; }
  .hero-card { padding: 20px 14px; }
}
"""


LANG_PICKER_CSS = """
html, body { min-height: 100%; background: #F5F9FF !important; color: #123B70; }
body { font-family: 'Poppins', 'Cairo', 'Segoe UI', sans-serif; }
.container { max-width: none; padding: 0; min-height: 100vh; min-height: 100dvh; }
.ss-bnav, .asst-fab, .asst-panel, .expl-bg, .asst-modal-bg, .ss-modal-overlay, .pwa-install { display: none !important; }
.first-lang { min-height: 100vh; min-height: 100dvh; display: flex; flex-direction: column; background: radial-gradient(circle at 50% 38%, #EAF4FF 0, #F5F9FF 45%, #FFFFFF 100%); }
.first-lang-head { min-height: 82px; display: flex; align-items: center; justify-content: center; padding: 18px; background: rgba(255,255,255,.88); border-bottom: 1px solid #DCEBFA; }
.first-lang-logo { display: inline-flex; align-items: center; gap: 10px; color: #123B70; font-size: clamp(20px,3vw,28px); font-weight: 900; letter-spacing: -.4px; }
.first-lang-logo em { color: #1976D2; font-style: normal; }
.first-lang-main { flex: 1; display: flex; align-items: center; justify-content: center; padding: 34px 18px; }
.first-lang-card { width: min(760px,100%); background: rgba(255,255,255,.94); border: 1px solid #DCEBFA; border-radius: 28px; padding: clamp(28px,5vw,54px); text-align: center; box-shadow: 0 22px 60px rgba(25,118,210,.12); }
.first-lang-icon { width: 88px; height: 88px; margin: 0 auto 20px; border-radius: 28px; display: flex; align-items: center; justify-content: center; font-size: 43px; background: linear-gradient(135deg,#EAF4FF,#D7EBFF); box-shadow: 0 12px 28px rgba(25,118,210,.15); }
.first-lang-card h1 { color: #123B70; font-size: clamp(25px,4.2vw,38px); line-height: 1.45; margin-bottom: 4px; }
.first-lang-card h2 { color: #123B70; font-size: clamp(21px,3.4vw,31px); line-height: 1.35; margin-bottom: 22px; }
.first-lang-prompt-ar { color: #40566F; font-size: clamp(17px,2.7vw,21px); font-weight: 700; direction: rtl; }
.first-lang-prompt-en { color: #5F7185; font-size: 15px; margin: 2px 0 24px; }
.first-lang-options { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 16px; }
.first-lang-option { min-height: 112px; display: flex; align-items: center; justify-content: center; gap: 13px; padding: 20px; background: #FFFFFF; color: #123B70; border: 2px solid #DCEBFA; border-radius: 19px; font: 800 clamp(18px,3vw,23px) inherit; cursor: pointer; box-shadow: 0 6px 18px rgba(25,118,210,.06); transition: transform .16s ease, border-color .16s ease, box-shadow .16s ease, background .16s ease; }
.first-lang-option:hover { transform: translateY(-3px); border-color: #1976D2; background: #EAF4FF; box-shadow: 0 13px 28px rgba(25,118,210,.14); }
.first-lang-option:active { transform: scale(.98); }
.first-lang-option:focus-visible { outline: 4px solid rgba(25,118,210,.24); outline-offset: 3px; }
.first-lang-flag { width: 48px; height: 48px; flex: 0 0 48px; border-radius: 50%; display: flex; align-items: center; justify-content: center; background: #EAF4FF; color: #1976D2; font-size: 14px; font-weight: 900; letter-spacing: .5px; }
.first-lang-note { margin-top: 22px; color: #5F7185; font-size: 12.5px; line-height: 1.8; }
.first-lang-loading { opacity: .7; pointer-events: none; }
.first-lang-brand { font-size: clamp(30px,5vw,48px)!important; line-height:1.2!important; margin-bottom:16px!important; direction:ltr; }
.first-lang-tag-ar { color:#163B5C;font-size:clamp(21px,3.3vw,31px);font-weight:900;direction:rtl;line-height:1.5; }
.first-lang-tag-en { color:#287FC1;font-size:clamp(17px,2.7vw,24px);font-weight:700;margin:2px 0 14px;direction:ltr; }
.first-lang-desc-ar,.first-lang-desc-en{max-width:660px;margin-inline:auto;color:#607487;line-height:1.9}.first-lang-desc-ar{direction:rtl;font-size:15px}.first-lang-desc-en{direction:ltr;font-size:14px;margin-top:3px}
.first-lang-start{min-height:50px;margin:21px auto 20px;border:0;border-radius:13px;padding:11px 30px;background:#287FC1;color:#fff;font:800 16px inherit;cursor:pointer;box-shadow:0 8px 20px rgba(40,127,193,.16)}
.first-lang-select-title{font-size:14px;color:#607487;font-weight:700;margin-bottom:10px}
@media (max-width: 600px) {
  .first-lang-head { min-height: 46px; padding: 10px; }
  .first-lang-logo { font-size: 17px; gap: 6px; }
  .first-lang-main { align-items: center; padding: 10px 12px; }
  .first-lang-card { border-radius: 18px; padding: 16px 14px; }
  .first-lang-icon { width: 46px; height: 46px; margin-bottom: 8px; border-radius: 16px; font-size: 22px; }
  .first-lang-brand { font-size: 22px !important; margin-bottom: 6px !important; }
  .first-lang-tag-ar { font-size: 15px; line-height: 1.3; }
  .first-lang-tag-en { font-size: 13px; margin: 2px 0 6px; }
  .first-lang-desc-ar, .first-lang-desc-en { display: none; }
  .first-lang-start { min-height: 38px; margin: 10px auto; padding: 8px 20px; font-size: 13.5px; }
  .first-lang-select-title { font-size: 13px; margin-bottom: 6px; }
  .first-lang-options { grid-template-columns: repeat(2,minmax(0,1fr)); gap: 8px; }
  .first-lang-option { min-height: 56px; justify-content: center; padding-inline: 8px; gap: 8px; font-size: 15px; }
  .first-lang-flag { width: 34px; height: 34px; flex: 0 0 34px; font-size: 13px; }
  .first-lang-note { margin-top: 10px; font-size: 12px; line-height: 1.6; }
}
@media (max-width: 360px) { .first-lang-card { padding-inline: 12px; } .first-lang-option { padding-inline: 6px; font-size: 14px; } }
@media (prefers-reduced-motion: reduce) { .first-lang-option { transition: none; } }
"""


def welcome_page():
    next_target = _safe_next_url("/home")
    body = """
    <main class="first-lang" aria-labelledby="languageTitle">
      <header class="first-lang-head">
        <div class="first-lang-logo" aria-label="SymptoSense"><span aria-hidden="true">❤️‍🩹</span><span>Sympto<em>Sense</em></span></div>
      </header>
      <section class="first-lang-main">
        <div class="first-lang-card">
          <div class="first-lang-icon" aria-hidden="true">🩺</div>
          <h1 class="first-lang-brand" lang="en">SymptoSense 🩺</h1>
          <p class="first-lang-tag-ar">افهم أعراضك. اعرف خطوتك التالية.</p>
          <p class="first-lang-tag-en" lang="en">Understand your symptoms. Know your next step.</p>
          <p class="first-lang-desc-ar">مساعد صحي ذكي يساعدك على فهم الأعراض وتقييم مستوى الخطورة بطريقة مبسطة.</p>
          <p class="first-lang-desc-en" lang="en">An AI-powered health assistant that helps you understand symptoms and assess risk in a simple way.</p>
          <button type="button" class="first-lang-start" onclick="document.getElementById('languageTitle').focus()">ابدأ الآن / Get Started</button>
          <p class="first-lang-select-title" id="languageTitle" tabindex="-1">اختر اللغة / Choose language</p>
          <div class="first-lang-options" role="group" aria-labelledby="languageTitle">
            <button type="button" class="first-lang-option" onclick="ssChooseLanguage('ar',this)" aria-label="المتابعة باللغة العربية">
              <span class="first-lang-flag" aria-hidden="true">SA</span><span dir="rtl">العربية</span>
            </button>
            <button type="button" class="first-lang-option" onclick="ssChooseLanguage('en',this)" aria-label="Continue in English UK">
              <span class="first-lang-flag" aria-hidden="true">UK</span><span lang="en">English (UK)</span>
            </button>
          </div>
          <p class="first-lang-note"><span dir="rtl">يمكنك تغيير اللغة لاحقًا من داخل الموقع</span><br><span lang="en">You can change the language later</span></p>
        </div>
      </section>
    </main>
    <script>
    var SS_NEXT_PAGE = __NEXT__;
    function ssChooseLanguage(code, button) {
      var lang = code === 'en' ? 'en' : 'ar';
      document.querySelectorAll('.first-lang-option').forEach(function(el){ el.classList.add('first-lang-loading'); el.disabled = true; });
      if (button) { button.style.borderColor = '#1976D2'; button.setAttribute('aria-pressed','true'); }
      document.cookie = 'lang=' + lang + ';path=/;max-age=31536000;SameSite=Lax';
      try { localStorage.setItem('ss_lang', lang); } catch(e) {}
      window.setTimeout(function(){ window.location.href = SS_NEXT_PAGE || '/home'; }, 180);
    }
    </script>
    """
    body = body.replace("__NEXT__", json.dumps(next_target))
    html = _page("SymptoSense — Choose language | اختر اللغة", body, bare=True, extra_css=LANG_PICKER_CSS)
    return html.replace('dir="rtl"', 'dir="ltr"').replace('lang="ar"', 'lang="en"')


HOME_CSS = """
.svc-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 16px; margin-bottom: 28px; }
.svc-card { background: #FFFFFF; border: 1px solid #DCEBFA; border-radius: 18px; padding: 22px; display: flex; flex-direction: column; align-items: flex-start; gap: 12px; box-shadow: 0 4px 16px rgba(25,118,210,.06); transition: transform .14s ease, box-shadow .14s ease, border-color .14s ease; }
.svc-card:hover { transform: translateY(-4px); border-color: #1976D2; box-shadow: 0 14px 30px rgba(25,118,210,.14); }
.svc-ic { width: 60px; height: 60px; border-radius: 16px; background: #EAF4FF; display: flex; align-items: center; justify-content: center; font-size: 30px; }
.svc-card h3 { color: #123B70; font-size: 17px; font-weight: 800; margin: 0; }
.svc-card p { color: #40566F; font-size: 14px; line-height: 1.7; margin: 0; }
.svc-btn { background: #1976D2; color: #FFFFFF; font-weight: 700; font-size: 14px; padding: 9px 22px; border-radius: 999px; margin-top: auto; }
.svc-card:hover .svc-btn { background: #1565C0; }
.mh-card { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; background: linear-gradient(120deg, #EAF4FF 0%, #F5F9FF 60%, #FFFFFF 100%); border: 1px solid #DCEBFA; border-radius: 18px; padding: 22px 24px; margin-bottom: 16px; box-shadow: 0 4px 16px rgba(25,118,210,.08); }
.mh-ic { width: 60px; height: 60px; border-radius: 16px; background: linear-gradient(135deg, #B8D8F8, #64B5F6); display: flex; align-items: center; justify-content: center; font-size: 30px; box-shadow: 0 8px 20px rgba(25,118,210,.20); }
.mh-tx { flex: 1; min-width: 220px; }
.mh-tx h3 { color: #123B70; font-size: 18px; font-weight: 800; margin: 0 0 4px; }
.mh-tx p { color: #40566F; font-size: 14px; line-height: 1.7; margin: 0; }
.mh-btn { background: linear-gradient(135deg, #1976D2, #123B70); color: #FFFFFF; font-weight: 700; font-size: 15px; padding: 11px 24px; border-radius: 999px; box-shadow: 0 8px 20px rgba(25,118,210,.25); }
.mh-btn:hover { transform: translateY(-1px); box-shadow: 0 12px 26px rgba(25,118,210,.32); }
.asst-cta { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; background: linear-gradient(120deg, #123B70 0%, #1976D2 100%); color: #FFFFFF; border-radius: 20px; padding: 26px 28px; margin-bottom: 14px; box-shadow: 0 18px 40px rgba(25,118,210,.22); }
.asst-cta-ic { font-size: 42px; }
.asst-cta-tx { flex: 1; min-width: 220px; }
.asst-cta-tx b { font-size: 20px; display: block; margin-bottom: 4px; }
.asst-cta-tx p { opacity: .92; font-size: 14px; line-height: 1.7; margin: 0; }
.asst-cta button { border: none; background: #FFFFFF; color: #123B70; font-weight: 800; font-size: 15px; padding: 12px 26px; border-radius: 999px; cursor: pointer; font-family: inherit; box-shadow: 0 8px 20px rgba(18,59,112,.22); }
.asst-cta button:hover { transform: translateY(-1px); box-shadow: 0 12px 26px rgba(18,59,112,.30); }
.quick-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 14px; margin-bottom: 30px; }
.quick-card { display: flex; align-items: flex-start; gap: 14px; background: #FFFFFF; border: 1px solid #DCEBFA; border-radius: 16px; padding: 18px; box-shadow: 0 3px 12px rgba(25,118,210,.06); transition: transform .14s ease, box-shadow .14s ease, border-color .14s ease; }
.quick-card:hover { transform: translateY(-2px); border-color: #1976D2; box-shadow: 0 10px 24px rgba(25,118,210,.12); }
.q-ic { width: 48px; height: 48px; flex: 0 0 48px; border-radius: 14px; background: #EAF4FF; display: flex; align-items: center; justify-content: center; font-size: 25px; }
.quick-card b { color: #123B70; font-size: 15.5px; }
.quick-card p { color: #40566F; font-size: 13.5px; line-height: 1.6; margin: 4px 0 0; }
.care-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 34px; }
.care-item { background: #FFFFFF; border: 1px solid #DCEBFA; border-radius: 16px; padding: 18px 14px; text-align: center; font-weight: 800; color: #123B70; font-size: 14.5px; transition: transform .14s ease, box-shadow .14s ease, border-color .14s ease; }
.care-item span { display: block; font-size: 27px; margin-bottom: 8px; }
.care-item:hover { transform: translateY(-2px); border-color: #1976D2; box-shadow: 0 8px 20px rgba(25,118,210,.10); }
@media (max-width: 640px) {
  .svc-grid { grid-template-columns: 1fr; }
  .mh-card, .asst-cta { flex-direction: column; align-items: flex-start; }
}
@media (max-width: 480px) {
  .svc-card { padding: 18px; }
  .mh-card, .asst-cta { padding: 18px; }
  .asst-cta-ic { font-size: 32px; }
  .asst-cta button, .mh-btn { width: 100%; text-align: center; }
  .quick-grid { grid-template-columns: 1fr; gap: 10px; }
  .care-grid { grid-template-columns: 1fr 1fr; gap: 10px; }
  .care-item { padding: 14px 10px; font-size: 13px; }
}
"""


def home_page():
    ar = _lang() == "ar"
    bi = lambda a, e: a if ar else e
    body = """
    <section class="hh" aria-labelledby="homeTitle">
      <div class="hh-l">
        <span class="hh-badge">SymptoSense · __TRUSTED_LABEL__</span>
        <h1 id="homeTitle">__TITLE__</h1>
        <p class="hh-sub">__SUB__</p>
        <p class="hh-desc">__DESC__</p>
        <div class="hh-btns"><a class="btn pri" href="/chat">__START__</a><button class="btn sec" onclick="asstToggle()">__ASK__</button></div>
      </div>
      <div class="hh-r" aria-hidden="true"><div class="hh-product-visual"><span class="hh-product-core">S</span><span class="hh-product-node hh-p1">📊</span><span class="hh-product-node hh-p2">🧠</span><span class="hh-product-node hh-p3">🩺</span><span class="hh-product-node hh-p4">✦</span></div></div>
    </section>

    <div class="home-trust"><span>__TRUST_COPY__</span><a href="/sources">__VIEW_SOURCES__</a></div>

    <div class="v2-section-head" id="services"><div><h2>__CORE_H__</h2><p class="muted">__CORE_P__</p></div></div>
    <div class="svc-grid" style="grid-template-columns:repeat(3,minmax(0,1fr));">
      <a class="svc-card" href="/chat"><span class="svc-ic">🩺</span><h3>__SYM_H__</h3><p>__SYM_P__</p><span class="svc-btn">__OPEN__</span></a>
      <a class="svc-card" href="#" onclick="asstToggle();return false;"><span class="svc-ic">🤖</span><h3>__AI_H__</h3><p>__AI_P__</p><span class="svc-btn">__OPEN__</span></a>
      <a class="svc-card" href="/blood"><span class="svc-ic">🧪</span><h3>__LAB_H__</h3><p>__LAB_P__</p><span class="svc-btn">__OPEN__</span></a>
    </div>

    <details class="v2-services-more">
      <summary>__MORE__</summary>
      <div class="v2-more-grid">
        <a class="v2-more-link" href="/meds"><span>💊</span>__MEDS__</a>
        <a class="v2-more-link" href="/calculators"><span>🧮</span>__CALC__</a>
        <a class="v2-more-link" href="/family"><span>👨‍👩‍👧</span>__FAMILY__</a>
        <a class="v2-more-link" href="/search"><span>🔎</span>__SEARCH__</a>
        <a class="v2-more-link" href="/sources"><span>📚</span>__SOURCES__</a>
        <a class="v2-more-link" href="#" onclick="openAsstMH();return false;"><span>🧠</span>__MENTAL__</a>
        <a class="v2-more-link" href="/relax"><span>🌿</span>__RELAX__</a>
        <a class="v2-more-link" href="/checkin"><span>📋</span>__CHECK__</a>
        <a class="v2-more-link" href="/tips"><span>💡</span>__TIPS__</a>
        <a class="v2-more-link" href="/firstaid"><span>🩹</span>__FIRSTAID__</a>
        <a class="v2-more-link" href="/emergency"><span>🚑</span>__EMERGENCY__</a>
        <a class="v2-more-link" href="/about-us"><span>ℹ️</span>__ABOUT__</a>
      </div>
    </details>
    <div class="warn2"><span class="w-ic">ℹ️</span><div>__DISC__</div></div>
    """
    replacements = {
        "__TITLE__": bi("افهم أعراضك. اعرف خطوتك التالية.", "Understand your symptoms. Know your next step."),
        "__TRUSTED_LABEL__": bi("مساعدك لفهم الأعراض", "Your guide to understanding symptoms"),
        "__TRUST_COPY__": bi("معلومات صحية مدعومة بمصادر طبية موثوقة", "Health information supported by trusted medical sources"),
        "__VIEW_SOURCES__": bi("عرض المصادر الطبية ←", "View medical sources →"),
        "__SUB__": bi("حلّل أعراضك بطريقة ذكية، وتعرّف على مستوى الخطورة والخطوة المناسبة لك.", "Analyze your symptoms intelligently and understand your risk level and the right next step."),
        "__DESC__": bi("معلومات صحية موثوقة تساعدك على فهم الأعراض واتخاذ قرار أفضل، دون تشخيص طبي.", "Trusted health information to help you understand symptoms and make a better-informed decision, without a medical diagnosis."),
        "__START__": bi("ابدأ تحليل الأعراض", "Start symptom analysis"), "__ASK__": bi("اسأل المساعد الذكي", "Ask the AI assistant"),
        "__CORE_H__": bi("الخدمات الرئيسية", "Core services"), "__CORE_P__": bi("ثلاثة مسارات واضحة لما تحتاجه غالبًا.", "Three clear paths for the things you need most."),
        "__SYM_H__": bi("تحليل الأعراض", "Symptom analysis"), "__SYM_P__": bi("تحليل الأعراض وتقييم مستوى الخطورة بخطوات واضحة.", "Review symptoms and assess risk through clear steps."),
        "__AI_H__": bi("المساعد الذكي", "AI assistant"), "__AI_P__": bi("أسئلة صحية، صحة نفسية، أدوية وتحاليل في تجربة تفاعلية.", "Interactive support for health questions, mental wellbeing, medicines, and labs."),
        "__LAB_H__": bi("تحليل التحاليل", "Lab analysis"), "__LAB_P__": bi("مساعدة مبسطة وتثقيفية لفهم نتائج التحاليل.", "Simple, educational help understanding laboratory results."),
        "__OPEN__": bi("فتح الخدمة", "Open service"), "__MORE__": bi("الخدمات الأخرى", "More services"),
        "__MEDS__": bi("معلومات الأدوية", "Medicine information"), "__CALC__": bi("الحاسبات الصحية", "Health calculators"),
        "__FAMILY__": bi("ملفات العائلة", "Family profiles"), "__SEARCH__": bi("البحث الصحي", "Health search"),
        "__SOURCES__": bi("المصادر الطبية", "Medical sources"), "__MENTAL__": bi("الصحة النفسية", "Mental wellbeing"),
        "__RELAX__": bi("تمارين الاسترخاء", "Relaxation"), "__CHECK__": bi("تسجيل المزاج", "Mood check-in"),
        "__TIPS__": bi("نصائح صحية", "Health tips"), "__FIRSTAID__": bi("الإسعافات الأولية", "First aid"),
        "__EMERGENCY__": bi("الطوارئ", "Emergency"), "__ABOUT__": bi("عن SymptoSense", "About SymptoSense"),
        "__DISC__": bi("هذه المعلومات للتوعية ولا تُعد تشخيصًا طبيًا. عند وجود أعراض خطرة اطلب الرعاية العاجلة.", "This information is educational and is not a medical diagnosis. Seek urgent care for danger signs."),
    }
    for key, value in replacements.items():
        body = body.replace(key, value)
    return _page(_t("title_landing"), body, extra_css=HOME_CSS)


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


ABOUT_US_CSS = """
.about-us-page{width:min(1160px,100%);margin:0 auto;display:grid;gap:clamp(18px,3.5vw,34px);padding-bottom:20px}.au-section{position:relative;overflow:hidden;border:1px solid var(--v2-line);border-radius:24px;background:#fff;box-shadow:var(--v2-shadow)}.au-split{display:grid;grid-template-columns:minmax(0,1fr) minmax(300px,.9fr);gap:clamp(24px,5vw,58px);align-items:center;padding:clamp(24px,5vw,52px)}.au-kicker{display:inline-flex;align-items:center;gap:7px;color:var(--v2-blue);font-size:12px;font-weight:900;margin-bottom:10px}.au-section h1,.au-section h2{color:var(--v2-blue-dark);line-height:1.35}.au-section h1{font-size:clamp(30px,4.5vw,50px);margin:0 0 8px}.au-section h2{font-size:clamp(23px,3vw,34px);margin:0 0 12px}.au-role{color:var(--v2-blue);font-weight:800;font-size:clamp(15px,1.7vw,18px);margin-bottom:18px}.au-copy{font-size:clamp(14.5px,1.35vw,16.5px);line-height:2;color:var(--v2-text);max-width:62ch}.au-copy p+p{margin-top:10px}.au-hero{background:linear-gradient(135deg,#F8FCFF,#EDF7FD 58%,#fff)}.au-hero .au-split{min-height:470px}.au-visual{min-height:320px;display:grid;place-items:center}.au-portrait-abstract{position:relative;width:min(390px,96%);aspect-ratio:1;border-radius:36px;background:#F4FAFE;border:1px solid #CFE3EF;display:grid;place-items:center;isolation:isolate}.au-portrait-abstract:before,.au-portrait-abstract:after{content:'';position:absolute;border-radius:50%;border:1px solid #BFDCEA;inset:11%}.au-portrait-abstract:after{inset:27%;background:#fff;border:0;box-shadow:0 14px 32px rgba(40,127,193,.09);z-index:-1}.au-r{width:92px;height:92px;border-radius:28px;background:var(--v2-blue);color:#fff;display:grid;place-items:center;font-size:42px;font-weight:900;box-shadow:0 13px 30px rgba(40,127,193,.2)}.au-float{position:absolute;width:64px;height:64px;border-radius:20px;background:#fff;border:1px solid #D4E6F1;display:grid;place-items:center;font-size:28px;box-shadow:0 8px 20px rgba(31,86,127,.08)}.au-f1{top:9%;left:11%}.au-f2{top:10%;right:9%}.au-f3{bottom:8%;left:13%}.au-f4{bottom:9%;right:11%}.au-story{background:#fff}.au-story .au-visual{order:-1}.au-story-flow{width:min(380px,96%);display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.au-story-node{min-height:116px;padding:18px;border:1px solid var(--v2-line);border-radius:20px;background:#F8FCFE;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;color:var(--v2-blue-dark);font-weight:800}.au-story-node span{font-size:30px;margin-bottom:6px}.au-story-node:last-child{background:var(--v2-blue);color:#fff;border-color:var(--v2-blue)}.au-idea-visual{width:min(390px,96%);position:relative}.au-idea-visual img{width:100%;display:block;border-radius:28px;border:1px solid #CEE3EF;box-shadow:0 16px 36px rgba(31,86,127,.10)}.au-chip{position:absolute;padding:8px 11px;border-radius:999px;background:#fff;border:1px solid #D5E6EF;color:var(--v2-blue-dark);font-size:11px;font-weight:900;box-shadow:0 7px 16px rgba(31,86,127,.07)}.au-c1{top:7%;left:-18px}.au-c2{top:45%;right:-20px}.au-c3{bottom:8%;left:-14px}.au-c4{bottom:30%;right:-18px}.au-purpose{padding:clamp(28px,5vw,52px);text-align:center;background:#F9FCFE}.au-purpose .au-copy{max-width:760px;margin:0 auto}.au-purpose-icons{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;max-width:700px;margin:24px auto 0}.au-purpose-item{padding:18px;border:1px solid var(--v2-line);border-radius:18px;background:#fff;color:var(--v2-blue-dark);font-weight:800}.au-purpose-item span{display:block;font-size:29px;margin-bottom:7px}.au-project{padding:clamp(28px,5vw,54px);text-align:center}.au-project-head{max-width:720px;margin:0 auto 24px}.au-device{display:flex;align-items:flex-end;justify-content:center;gap:20px;direction:ltr}.au-laptop{width:min(800px,88%)}.au-screen{aspect-ratio:16/9;padding:9px;border-radius:20px 20px 10px 10px;background:#163B5C;box-shadow:0 22px 48px rgba(22,59,92,.17)}.au-screen iframe{width:100%;height:100%;border:0;border-radius:12px;background:#fff;pointer-events:none}.au-base{height:14px;width:108%;margin-left:-4%;border-radius:4px 4px 18px 18px;background:#D6E0E8}.au-phone{width:135px;padding:7px;border-radius:25px;background:#163B5C;box-shadow:0 17px 36px rgba(22,59,92,.16)}.au-phone iframe{width:100%;aspect-ratio:9/18.5;border:0;border-radius:19px;background:#fff;pointer-events:none}.au-message{padding:clamp(28px,5vw,52px);background:#F5FAFE}.au-message-card{max-width:900px;margin:auto;display:grid;grid-template-columns:1fr 220px;align-items:center;gap:28px;padding:clamp(22px,4vw,36px);border-radius:23px;background:#fff;border:1px solid var(--v2-line);box-shadow:0 12px 30px rgba(31,86,127,.07)}.au-voice-mark{height:180px;border-radius:26px;background:#EAF5FC;display:grid;place-items:center;position:relative}.au-voice-mark:before{content:'R';width:78px;height:78px;border-radius:24px;background:var(--v2-blue);color:#fff;display:grid;place-items:center;font-size:34px;font-weight:900}.au-voice-icons{position:absolute;inset:0;display:flex;align-items:flex-end;justify-content:space-around;padding:16px;font-size:23px}.au-final{padding:clamp(40px,6vw,66px);text-align:center;background:linear-gradient(135deg,#F2F9FD,#fff)}.au-final p{max-width:650px;margin:0 auto 21px;line-height:1.9;color:var(--v2-text)}.au-final .btn{display:inline-flex;justify-content:center;min-width:190px}.au-reveal{animation:auIn .55s ease both}@keyframes auIn{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}.au-portrait-abstract,.au-story-flow,.au-idea-visual{animation:auFloat 6s ease-in-out infinite}@keyframes auFloat{50%{transform:translateY(-5px)}}@media(max-width:900px){.au-split{grid-template-columns:1fr}.au-hero .au-visual{order:-1}.au-story .au-visual{order:0}.au-message-card{grid-template-columns:1fr}.au-voice-mark{height:145px}.au-copy{max-width:none}.au-device .au-phone{display:none}.au-laptop{width:100%}}@media(max-width:620px){.about-us-page{gap:14px}.au-section{border-radius:20px}.au-split,.au-purpose,.au-project,.au-message,.au-final{padding:21px}.au-visual{min-height:260px}.au-story-flow{grid-template-columns:1fr 1fr}.au-story-node{min-height:92px;padding:12px;font-size:12px}.au-purpose-icons{grid-template-columns:1fr}.au-chip{position:static;display:inline-flex;margin:5px 3px 0}.au-idea-visual{display:flex;flex-wrap:wrap;justify-content:center}.au-idea-visual img{width:100%}.au-final .btn{width:100%}}@media(prefers-reduced-motion:reduce){.au-reveal,.au-portrait-abstract,.au-story-flow,.au-idea-visual{animation:none!important}}
"""

ABOUT_US_POLISH_CSS = """
.au-polished{width:min(1160px,100%);margin:0 auto;display:grid;gap:clamp(16px,3vw,30px);padding-bottom:20px}
.au-polished .au-section{position:relative;overflow:hidden;border:1px solid #dce8f0;border-radius:24px;background:#fff;box-shadow:0 10px 30px rgba(31,86,127,.07)}
.au-polished .au-split{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(320px,.95fr);gap:clamp(24px,5vw,58px);align-items:center;padding:clamp(26px,5vw,54px)}
.au-polished .au-kicker{display:inline-flex;align-items:center;gap:7px;color:#287fc1;font-size:12px;font-weight:900;letter-spacing:.02em;margin-bottom:10px}
.au-polished h1,.au-polished h2{color:#163b5c;line-height:1.35}.au-polished h1{font-size:clamp(30px,4.5vw,50px);margin:0 0 9px}.au-polished h2{font-size:clamp(23px,3vw,34px);margin:0 0 12px}
.au-polished .au-role{color:#287fc1;font-weight:800;font-size:clamp(15px,1.7vw,18px);margin-bottom:18px;direction:ltr;text-align:start}
.au-polished .au-copy{font-size:clamp(14.5px,1.35vw,16.5px);line-height:2;color:#23384a;max-width:64ch}.au-polished .au-copy p+p{margin-top:10px}
.au-polished .au-hero{background:#f8fcff}.au-polished .au-hero .au-split{min-height:470px}.au-polished .au-visual{min-height:300px;display:grid;place-items:center}
.au-polished .au-hero-art,.au-polished .au-story-art{display:block;width:min(440px,100%);height:auto;object-fit:contain;border-radius:28px;border:1px solid #cfe3ef;box-shadow:0 16px 36px rgba(31,86,127,.10)}
.au-polished .au-story-art{width:min(520px,100%)}.au-polished .au-story{background:#fff}
.au-polished .au-inline-visual{position:relative;width:min(440px,100%);aspect-ratio:1;border:1px solid #cfe3ef;border-radius:30px;background:#f4fafe;display:grid;place-items:center;box-shadow:0 16px 36px rgba(31,86,127,.10);overflow:hidden}.au-polished .au-inline-visual:before,.au-polished .au-inline-visual:after{content:'';position:absolute;border-radius:50%;border:1px solid #c7e0ed}.au-polished .au-inline-visual:before{width:76%;height:76%}.au-polished .au-inline-visual:after{width:49%;height:49%;background:#fff;box-shadow:0 12px 30px rgba(31,86,127,.08)}
.au-polished .au-inline-core{position:relative;z-index:2;width:96px;height:96px;border-radius:28px;background:#287fc1;color:#fff;display:grid;place-items:center;font-size:42px;font-weight:900;box-shadow:0 13px 28px rgba(40,127,193,.22)}.au-polished .au-inline-node{position:absolute;z-index:3;width:66px;height:66px;border-radius:20px;background:#fff;border:1px solid #d6e7f0;display:grid;place-items:center;font-size:28px;box-shadow:0 8px 20px rgba(31,86,127,.08)}.au-polished .au-n1{top:10%;inset-inline-start:11%}.au-polished .au-n2{top:11%;inset-inline-end:10%}.au-polished .au-n3{bottom:10%;inset-inline-start:12%}.au-polished .au-n4{bottom:10%;inset-inline-end:11%}
.au-polished .au-story-map{width:min(520px,100%);display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.au-polished .au-story-step{min-height:125px;padding:18px;border-radius:22px;border:1px solid #d6e7f0;background:#f8fcfe;color:#163b5c;display:grid;place-items:center;text-align:center;font-weight:800}.au-polished .au-story-step span{display:block;font-size:32px;margin-bottom:5px}.au-polished .au-story-step:last-child{background:#287fc1;color:#fff;border-color:#287fc1}
.au-polished .au-what{background:#f9fcfe}.au-polished .au-concept{min-height:290px;width:min(420px,100%);padding:28px;border-radius:30px;border:1px solid #cfe3ef;background:#fff;display:flex;align-items:center;justify-content:center;gap:12px;flex-wrap:wrap;color:#163b5c;font-size:30px;box-shadow:0 14px 34px rgba(31,86,127,.07)}
.au-polished .au-concept span{width:66px;height:66px;border-radius:20px;background:#eaf5fc;display:grid;place-items:center}.au-polished .au-concept i{flex-basis:100%;height:1px;background:#dce8f0}.au-polished .au-concept b{font-size:22px;color:#287fc1}
.au-polished .au-purpose{padding:clamp(30px,5vw,54px);text-align:center;background:#f8fcff}.au-polished .au-purpose .au-copy{max-width:780px;margin:0 auto}.au-polished .au-purpose-icons{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;max-width:710px;margin:24px auto 0}.au-polished .au-purpose-item{padding:18px;border:1px solid #dce8f0;border-radius:18px;background:#fff;color:#163b5c;font-weight:800}.au-polished .au-purpose-item span{display:block;font-size:29px;margin-bottom:7px}
.au-polished .au-project{padding:clamp(30px,5vw,56px);text-align:center}.au-polished .au-project-head{max-width:750px;margin:0 auto 24px}.au-polished .au-project-head p{color:#607487;line-height:1.8}
.au-polished .au-device{display:flex;align-items:flex-end;justify-content:center;direction:ltr}.au-polished .au-laptop{width:min(820px,94%)}.au-polished .au-screen{position:relative;aspect-ratio:16/9;padding:9px;border-radius:20px 20px 10px 10px;background:#163b5c;box-shadow:0 22px 48px rgba(22,59,92,.17);overflow:hidden}.au-polished .au-live-frame>img,.au-polished .au-live-frame>iframe{position:absolute;inset:9px;width:calc(100% - 18px);height:calc(100% - 18px);border:0;border-radius:12px;background:#f5f9fc}.au-polished .au-live-frame>img{object-fit:contain}.au-polished .au-live-frame>iframe{opacity:0;pointer-events:none;transition:opacity .2s ease}.au-polished .au-live-frame.is-loaded>iframe{opacity:1}.au-polished .au-base{height:14px;width:108%;margin-left:-4%;border-radius:4px 4px 18px 18px;background:#d6e0e8}
.au-polished .au-project-fallback{position:absolute;inset:9px;border-radius:12px;background:linear-gradient(145deg,#f8fcff,#eaf5fc);display:grid;place-items:center;padding:24px;text-align:center;color:#163b5c}.au-polished .au-project-fallback span{width:72px;height:72px;margin:0 auto 12px;border-radius:22px;background:#287fc1;color:#fff;display:grid;place-items:center;font-size:34px}.au-polished .au-project-fallback b{display:block;font-size:clamp(18px,3vw,30px)}.au-polished .au-project-fallback small{display:block;margin-top:7px;color:#607487}.au-polished .au-live-frame.is-loaded>.au-project-fallback{visibility:hidden}
.au-polished .au-message{padding:clamp(28px,5vw,52px);background:#f5fafe}.au-polished .au-message-card{max-width:900px;margin:auto;display:grid;grid-template-columns:1fr 210px;align-items:center;gap:28px;padding:clamp(22px,4vw,36px);border-radius:23px;background:#fff;border:1px solid #dce8f0}.au-polished blockquote{margin:0;color:#23384a;font-size:clamp(16px,2vw,20px);line-height:2}.au-polished cite{display:block;margin-top:14px;color:#287fc1;font-style:normal;font-weight:800}.au-polished .au-voice-mark{height:170px;border-radius:26px;background:#eaf5fc;display:grid;place-items:center;align-content:center;gap:15px;color:#163b5c}.au-polished .au-voice-mark>span{width:72px;height:72px;border-radius:22px;background:#287fc1;color:#fff;display:grid;place-items:center;font-size:32px;font-weight:900}
.au-polished .au-final{padding:clamp(42px,6vw,68px);text-align:center;background:#f8fcff}.au-polished .au-final p{max-width:650px;margin:0 auto 21px;line-height:1.9;color:#23384a}.au-polished .au-final .btn{display:inline-flex;justify-content:center;min-width:190px}
.au-polished .au-reveal{animation:auPolishIn .45s ease both}@keyframes auPolishIn{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
@media(max-width:900px){.au-polished .au-split{grid-template-columns:1fr}.au-polished .au-hero .au-text{order:1}.au-polished .au-hero .au-visual{order:0}.au-polished .au-message-card{grid-template-columns:1fr}.au-polished .au-voice-mark{height:135px}.au-polished .au-copy{max-width:none}.au-polished .au-laptop{width:100%}}
@media(max-width:620px){.au-polished{gap:14px}.au-polished .au-section{border-radius:20px}.au-polished .au-split,.au-polished .au-purpose,.au-polished .au-project,.au-polished .au-message,.au-polished .au-final{padding:20px}.au-polished .au-visual{min-height:0}.au-polished .au-hero .au-split{min-height:0}.au-polished .au-purpose-icons{grid-template-columns:1fr}.au-polished .au-concept{min-height:230px;padding:20px}.au-polished .au-concept span{width:56px;height:56px}.au-polished .au-screen{padding:6px}.au-polished .au-live-frame>img,.au-polished .au-live-frame>iframe{inset:6px;width:calc(100% - 12px);height:calc(100% - 12px)}.au-polished .au-final .btn{width:100%}}
@media(prefers-reduced-motion:reduce){.au-polished .au-reveal{animation:none!important}.au-polished .au-live-frame>iframe{transition:none!important}}
"""


def about_us_page():
    from html import escape
    ar = _lang() == "ar"
    bi = lambda arabic, english: escape(arabic if ar else english)
    body = """
    <main class="about-us-page au-polished" aria-labelledby="aboutUsTitle">
      <section class="au-section au-hero au-reveal"><div class="au-split">
        <div class="au-text"><span class="au-kicker">01 · __ABOUT__</span><h1 id="aboutUsTitle">__HELLO__</h1><p class="au-role">Data Science Student &amp; Creator of SymptoSense</p><div class="au-copy"><p>__INTRO__</p></div></div>
        <div class="au-visual" role="img" aria-label="__HERO_ALT__"><div class="au-inline-visual"><span class="au-inline-core">S</span><span class="au-inline-node au-n1">📊</span><span class="au-inline-node au-n2">🧠</span><span class="au-inline-node au-n3">🩺</span><span class="au-inline-node au-n4">✦</span></div></div>
      </div></section>

      <section class="au-section au-story au-reveal"><div class="au-split au-split-reverse">
        <div class="au-visual" role="img" aria-label="__STORY_ALT__"><div class="au-story-map"><div class="au-story-step"><div><span>💡</span>__IDEA__</div></div><div class="au-story-step"><div><span>📊</span>__DATA__</div></div><div class="au-story-step"><div><span>🤖</span>__AI__</div></div><div class="au-story-step"><div><span>🩺</span>SymptoSense</div></div></div></div>
        <div class="au-text"><span class="au-kicker">02 · 💡</span><h2>__STORY_TITLE__</h2><div class="au-copy"><p>__STORY_P1__</p><p>__STORY_P2__</p></div></div>
      </div></section>

      <section class="au-section au-what au-reveal"><div class="au-split">
        <div class="au-text"><span class="au-kicker">03 · 🩺</span><h2>__WHAT_TITLE__</h2><div class="au-copy"><p>__WHAT__</p></div></div>
        <div class="au-concept" aria-hidden="true"><span>🩺</span><span>＋</span><span>📊</span><span>＋</span><span>🤖</span><i></i><b>SymptoSense</b></div>
      </div></section>

      <section class="au-section au-purpose au-reveal"><span class="au-kicker">04 · ❤️</span><h2>__WHY_TITLE__</h2><div class="au-copy"><p>__WHY__</p></div><div class="au-purpose-icons" aria-label="__WHY_TITLE__"><div class="au-purpose-item"><span>💡</span>__IDEA__</div><div class="au-purpose-item"><span>❤️</span>__PURPOSE__</div><div class="au-purpose-item"><span>🩺</span>__HEALTH__</div></div></section>

      <section class="au-section au-project au-reveal"><div class="au-project-head"><span class="au-kicker">05 · 💻</span><h2>__REAL_TITLE__</h2><p>__REAL_COPY__</p></div><div class="au-device"><div class="au-laptop"><div class="au-screen au-live-frame"><div class="au-project-fallback" role="img" aria-label="__PROJECT_ALT__"><div><span>🩺</span><b>SymptoSense</b><small>__PROJECT_TAGLINE__</small></div></div><iframe src="/home" title="__FRAME_TITLE__" loading="lazy" tabindex="-1" onload="try{if(this.contentDocument&amp;&amp;this.contentDocument.body&amp;&amp;this.contentDocument.body.innerText.trim())this.parentElement.classList.add('is-loaded')}catch(e){}"></iframe></div><div class="au-base"></div></div></div></section>

      <section class="au-section au-message au-reveal"><div class="au-message-card"><div><span class="au-kicker">06 · ✍️</span><h2>__MESSAGE_TITLE__</h2><blockquote>__MESSAGE__</blockquote><cite>— __NAME__</cite></div><div class="au-voice-mark" aria-hidden="true"><span>R</span><div>💡 · 📊 · 🩺</div></div></div></section>

      <section class="au-section au-final au-reveal"><span class="au-kicker">07 · SymptoSense</span><h2>__DISCOVER__</h2><p>__FINAL__</p><a class="btn pri" href="/chat">__CTA__</a></section>
    </main>"""
    replacements = {
        "__ABOUT__": bi("عن ريماس", "About Remas"),
        "__HELLO__": bi("مرحبًا، أنا ريماس حميد السلمي 👋", "Hi, I'm Remas Hameed Alsolami 👋"),
        "__INTRO__": bi("أنا ريماس حميد السلمي، طالبة في تخصص علوم البيانات وتحليلها، وشغوفة ببناء الحلول التقنية التي تحمل أثرًا حقيقيًا في حياة الناس.", "I am Remas Hameed Alsolami, a Data Science and Analytics student who is passionate about building technology solutions that make a genuine difference in people's lives."),
        "__HERO_ALT__": bi("رسم تجريدي يجمع الرعاية الصحية والبيانات والذكاء الاصطناعي", "An abstract visual combining healthcare, data, and artificial intelligence"),
        "__STORY_ALT__": bi("رسم يوضح انتقال الفكرة عبر البيانات والذكاء الاصطناعي إلى تجربة صحية رقمية", "An illustration showing an idea becoming a digital health experience through data and AI"),
        "__STORY_TITLE__": bi("قصتي مع SymptoSense", "My story with SymptoSense"),
        "__STORY_P1__": bi("بدأ شغفي من سؤال بسيط: كيف يمكن للتقنية أن تكون أقرب للإنسان؟", "My passion began with a simple question: How can technology feel closer to people?"),
        "__STORY_P2__": bi("ومن هنا جاءت فكرتي؛ أن أوظّف ما أتعلمه في علوم البيانات والتقنية لبناء حل يساعد على فهم الأعراض الصحية بصورة أوضح وأسهل.", "That is where my idea began: to use what I learn in data science and technology to build a solution that makes health symptoms clearer and easier to understand."),
        "__WHAT_TITLE__": bi("ما هو SymptoSense؟", "What is SymptoSense?"),
        "__WHAT__": bi("لم يكن هدفي إنشاء موقع فقط، بل صناعة تجربة تمنح المستخدم معرفة أولية تساعده على فهم ما يشعر به واتخاذ الخطوة المناسبة بوعي.", "My goal was not simply to create a website, but to design an experience that gives people initial knowledge, helps them understand what they are feeling, and supports them in choosing the right next step with greater awareness."),
        "__WHY_TITLE__": bi("لماذا هذا المشروع مهم بالنسبة لي؟", "Why this project matters to me"),
        "__WHY__": bi("أؤمن أن أعظم أثر للتقنية هو أن تجعل حياة الإنسان أبسط، ووعيه أكبر، وقراراته أذكى.", "I believe technology has its greatest impact when it makes people's lives simpler, their awareness greater, and their decisions smarter."),
        "__IDEA__": bi("فكرة", "Idea"), "__DATA__": bi("بيانات", "Data"), "__AI__": bi("ذكاء اصطناعي", "AI"), "__PURPOSE__": bi("هدف", "Purpose"), "__HEALTH__": bi("صحة", "Healthcare"),
        "__REAL_TITLE__": bi("من فكرة إلى مشروع حقيقي", "From an idea to a real project"),
        "__REAL_COPY__": bi("واجهة من النسخة الحالية للمشروع، مع عرض بصري بديل إذا تعذر تحميل المعاينة الحية.", "A view of the current project, with a visual fallback when the live preview cannot load."),
        "__PROJECT_ALT__": bi("تصميم أصلي من SymptoSense يعرض تجربة صحية على الهاتف", "An original SymptoSense visual showing the mobile health experience"),
        "__PROJECT_TAGLINE__": bi("افهم أعراضك. اعرف خطوتك التالية.", "Understand your symptoms. Know your next step."),
        "__FRAME_TITLE__": bi("معاينة مباشرة لموقع SymptoSense", "Live preview of the SymptoSense website"),
        "__MESSAGE_TITLE__": bi("رسالة ريماس", "A message from Remas"),
        "__MESSAGE__": bi("SymptoSense هو مشروعي لتطبيق ما تعلمته في علوم البيانات والذكاء الاصطناعي على فكرة صحية تهدف إلى تقديم تجربة أبسط وأكثر تنظيمًا للمستخدم.", "SymptoSense is my project for applying what I have learned in data science and artificial intelligence to a health-focused idea that aims to give users a simpler, more organized experience."),
        "__NAME__": bi("ريماس حميد السلمي", "Remas Hameed Alsolami"),
        "__DISCOVER__": bi("تعرّف على SymptoSense 🩺", "Discover SymptoSense 🩺"),
        "__FINAL__": bi("افهم أعراضك. اعرف خطوتك التالية.", "Understand your symptoms. Know your next step."),
        "__CTA__": bi("جرّب SymptoSense", "Try SymptoSense"),
    }
    for key, value in replacements.items():
        body = body.replace(key, value)
    return _page(
        bi("من نحن — ريماس حميد السلمي", "About — Remas Hameed Alsolami"),
        body,
        desc=bi("تعرف على ريماس حميد السلمي وقصة تطوير SymptoSense.", "Meet Remas Hameed Alsolami and the story behind SymptoSense."),
        extra_css=ABOUT_US_POLISH_CSS,
    )


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


def privacy_page():
    ar = _lang() == "ar"
    bi = lambda a, e: a if ar else e
    body = """
    <main class="v2-info-page" aria-labelledby="privacyTitle">
      <section><h1 id="privacyTitle">🔒 __TITLE__</h1><p>__INTRO__</p></section>
      <section><h2>__COLLECT_H__</h2><ul><li>__COLLECT_1__</li><li>__COLLECT_2__</li><li>__COLLECT_3__</li></ul></section>
      <section><h2>__SAVE_H__</h2><p>__SAVE_P__</p></section>
      <section id="data-use"><h2>__USE_H__</h2><p>__USE_P__</p><p class="muted">__AI_IMPROVE__</p></section>
      <section><h2>__AI_H__</h2><p>__AI_P__</p></section>
      <section><h2>__CONTROL_H__</h2><p>__CONTROL_P__</p><div class="ss-btn-row"><a class="btn pri" href="/privacy-center">__SETTINGS__</a><a class="btn ghost" href="/manage">__MANAGE__</a></div></section>
      <section><h2>__ADMIN_H__</h2><p>__ADMIN_P__</p></section>
      <section><h2>__KB_H__</h2><p>__KB_P__</p></section>
    </main>
    """
    values = {
        "__TITLE__": bi("الخصوصية وحماية البيانات", "Privacy and data protection"),
        "__INTRO__": bi("نشرح هنا بلغة واضحة ما نستخدمه ولماذا، وما الذي يبقى تحت سيطرتك.", "This page explains, in plain language, what we use, why we use it, and what remains under your control."),
        "__COLLECT_H__": bi("ما البيانات التي نجمعها؟", "What data do we collect?"),
        "__COLLECT_1__": bi("بيانات الحساب الأساسية فقط عند اختيار إنشاء حساب: الاسم والبريد الإلكتروني وكلمة مرور مشفرة.", "Basic account data only when you choose to register: name, email, and a securely hashed password."),
        "__COLLECT_2__": bi("المعلومات الصحية التي تُدخلها داخل الخدمة أو تختار حفظها؛ لا نطلبها أثناء التسجيل.", "Health information you enter in a service or explicitly choose to save; it is not requested during sign-up."),
        "__COLLECT_3__": bi("بيانات تشغيل مجمعة مثل نوع الجهاز واللغة والخدمة المستخدمة، دون نص الأعراض أو المحادثة.", "Aggregate operational data such as device type, language, and service used—without symptom or chat text."),
        "__SAVE_H__": bi("ما الذي يتم حفظه؟", "What is saved?"),
        "__SAVE_P__": bi("للزائر، تبقى الخدمات الأساسية متاحة دون حساب. عند تسجيل الدخول، يمكن حفظ الملف والنتائج والمحادثات وفق إعدادات الخصوصية التي تختارها.", "Core services remain available to guests. When signed in, your profile, results, and conversations may be saved according to the privacy settings you choose."),
        "__USE_H__": bi("كيف نستخدم البيانات المصرح بها؟", "How do we use authorized data?"),
        "__USE_P__": bi("قد نستخدم البيانات المصرح بمشاركتها لأغراض التحليل الإحصائي ودراسة الأنماط والعلاقات بين الأعراض والعوامل المدخلة، بهدف تحسين وتطوير SymptoSense. يتم ذلك فقط وفق تفضيل Analytics الذي تختاره، وبصورة مجمعة ومجهولة الهوية قدر الإمكان مع إخفاء المجموعات الصغيرة.", "Authorized data may be used for statistical analysis and to study patterns and associations among submitted symptoms and factors, with the aim of improving SymptoSense. This occurs only according to your Analytics preference, using aggregated and anonymized data where possible and suppressing small groups."),
        "__AI_IMPROVE__": bi("حاليًا لا يستخدم SymptoSense سجلاتك الصحية لتدريب أو تحسين نموذج AI نفسه؛ لذلك لا يظهر خيار موافقة منفصل لهذا الغرض. إذا تغير هذا الاستخدام مستقبلًا فيجب تحديث الإشعار والموافقة قبل تطبيقه.", "SymptoSense currently does not use your health records to train or improve the underlying AI model itself, so a separate AI-improvement consent is not shown. If that use changes in the future, the notice and consent flow must be updated first."),
        "__AI_H__": bi("هل تُرسل البيانات إلى خدمة AI؟", "Is data sent to an AI service?"),
        "__AI_P__": bi("عند استخدام المساعد أو التحليل قد يُرسل النص اللازم لتوليد الرد إلى مزود الذكاء الاصطناعي المهيأ للمشروع. لا يُطلب من النموذج إنشاء مصادر أو تشخيص قطعي، وتُستخدم قاعدة المعرفة وقواعد الأمان عندما تكون متاحة. تجنب إدخال اسمك أو رقمك أو أي معرف شخصي داخل وصف الحالة.", "When you use the assistant or analysis, the text needed to generate a response may be sent to the AI provider configured for this deployment. The model is not permitted to invent sources or provide a definitive diagnosis, and the knowledge base and safety rules are used where available. Avoid entering names, phone numbers, or other identifiers in a health description."),
        "__CONTROL_H__": bi("الحذف والتحكم", "Deletion and control"),
        "__CONTROL_P__": bi("يمكنك تعطيل استخدام المعلومات المحفوظة، حذف حقول صحية منفردة، مسح السجل، أو حذف الحساب وبياناته من صفحات الإعدادات والإدارة الشخصية.", "You can disable use of saved information, remove individual health fields, clear history, or delete your account and its data from privacy settings and data management."),
        "__SETTINGS__": bi("مركز الخصوصية", "Privacy Center"), "__MANAGE__": bi("إدارة بياناتي", "Manage my data"),
        "__ADMIN_H__": bi("وصول المسؤولين", "Administrator access"),
        "__ADMIN_P__": bi("تحليلات الإدارة مجمعة قدر الإمكان. صفحة المستخدمين تعرض المعرّف والحالة والتواريخ والدور فقط، ولا تعرض الأعراض أو المحادثات أو النتائج الصحية افتراضيًا.", "Admin analytics are aggregated wherever possible. User management shows only an ID, status, dates, and role; it does not expose symptoms, chats, or personal health results by default."),
        "__KB_H__": bi("قاعدة المعرفة الطبية", "Medical knowledge base"),
        "__KB_P__": bi("تحتوي معلومات طبية عامة ومصادر وقواعد أمان فقط، ولا تحتوي بيانات مرضى أو محادثات شخصية.", "It contains general medical information, sources, and safety rules only—never patient records or personal conversations."),
    }
    for key, value in values.items():
        body = body.replace(key, value)
    return _page(values["__TITLE__"], body)


def consent_page():
    ar = _lang() == "ar"
    next_url = request.args.get("next") or "/chat"
    if not str(next_url).startswith("/") or str(next_url).startswith("//"):
        next_url = "/chat"
    title = "خصوصيتك تهمنا" if ar else "Your privacy matters"
    body = """
    <main class="v2-info-page consent-page">
      <section class="consent-hero"><span class="consent-icon">🔐</span><h1>__TITLE__</h1>
        <ul class="consent-hero-list">
          <li>__P1__</li>
          <li>__P2__</li>
          <li class="muted">__P3__</li>
        </ul>
      </section>
      <section>
        <form id="consentForm">
          <article class="consent-option"><label><input type="checkbox" id="serviceConsent"> <span><b>__SERVICE_H__</b><small>__SERVICE_P__</small></span></label><span class="consent-badge required">__REQUIRED__</span></article>
          <article class="consent-option"><label><input type="checkbox" id="analyticsConsent"> <span><b>__AN_H__</b><small>__AN_P__</small></span></label><span class="consent-badge optional">__OPTIONAL__</span></article>
          <div class="privacy-links"><a href="/privacy">__READ__</a><a href="/privacy#data-use">__HOW__</a></div>
          <div id="consentErr" class="warn" style="display:none;margin-top:12px"></div>
          <button class="btn pri" style="width:100%;margin-top:14px" type="submit">__CONTINUE__</button>
        </form>
      </section>
      <section><p class="v2-disclaimer">__DISC__</p></section>
    </main>
    <style>
    .consent-page{max-width:760px}.consent-hero{text-align:center}.consent-icon{font-size:44px}.consent-hero-list{list-style:none;margin:14px auto 0;padding:0;max-width:520px;text-align:start;display:grid;gap:10px}.consent-hero-list li{background:#F7FBFF;border:1px solid var(--v2-line);border-radius:12px;padding:10px 14px;font-size:14.5px;line-height:1.7;color:var(--v2-text)}.consent-hero-list li.muted{color:var(--v2-muted)}.consent-option{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:16px;border:1px solid var(--v2-line);border-radius:15px;margin:10px 0;background:#fff}.consent-option label{display:flex;gap:11px;align-items:flex-start;cursor:pointer;flex:1}.consent-option input{width:20px;height:20px;margin-top:2px;accent-color:var(--v2-blue)}.consent-option small{display:block;color:var(--v2-muted);line-height:1.7;margin-top:4px}.consent-badge{font-size:11px;font-weight:800;border-radius:999px;padding:4px 9px;white-space:nowrap}.consent-badge.required{background:var(--v2-sky);color:var(--v2-blue-dark)}.consent-badge.optional{background:#F3F6F8;color:var(--v2-muted)}.privacy-links{display:flex;justify-content:center;gap:18px;flex-wrap:wrap;margin:16px 0}.privacy-links a{color:var(--v2-blue);font-weight:700}@media(max-width:560px){.consent-option{flex-direction:column}.consent-badge{align-self:flex-start}}
    </style>
    <script>
    document.getElementById('consentForm').addEventListener('submit', async function(e){
      e.preventDefault();
      const service=document.getElementById('serviceConsent').checked, analytics=document.getElementById('analyticsConsent').checked, err=document.getElementById('consentErr'), btn=this.querySelector('button[type=submit]');
      if(!service){err.style.display='block';err.textContent=__SERVICE_ERR__;return;}
      if(btn.disabled)return;
      err.style.display='none';
      const oldText=btn.textContent; btn.disabled=true; btn.setAttribute('aria-busy','true'); btn.textContent=__SAVING__;
      try{
        const controller=new AbortController(); const timer=setTimeout(()=>controller.abort(),12000);
        const r=await fetch('/api/consent/preferences',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({service_usage:service,analytics_research:analytics}),signal:controller.signal});
        clearTimeout(timer);
        const d=await r.json();
        if(!r.ok||!d.ok)throw new Error(d.error||'consent_failed');
        window.location.replace(__NEXT__);
      }catch(ex){
        err.style.display='block';err.textContent=__GEN_ERR__;
        btn.disabled=false;btn.removeAttribute('aria-busy');btn.textContent=oldText;
      }
    });
    </script>
    """
    vals = {
        "__TITLE__": title,
        "__P1__": ("📝 نجمع بس المعلومات اللي تدخلينها بنفسك (الأعراض، العمر، المدة، الشدة) عشان نقدّم لك الخدمة." if ar else "📝 We only collect what you enter yourself (symptoms, age, duration, severity) to provide the service."),
        "__P2__": ("📊 بموافقتك، نقدر نستخدم بيانات مجمّعة ومجهولة الهوية لتحسين النظام." if ar else "📊 With your consent, aggregated anonymized data may help us improve the system."),
        "__P3__": ("⚠️ النتائج توعوية فقط، وما تغني عن رأي الطبيب." if ar else "⚠️ Results are educational only and don't replace a doctor's opinion."),
        "__SERVICE_H__": ("موافقة استخدام الخدمة" if ar else "Service usage consent"),
        "__SERVICE_P__": ("أوافق على معالجة معلوماتي لاستخدام خدمات SymptoSense — ضرورية لأي ميزة تحتاج بيانات صحية." if ar else "I agree to processing my information to use SymptoSense's services — required for any feature that needs health data."),
        "__AN_H__": ("التحليلات والبحث الإحصائي" if ar else "Analytics & statistical research"),
        "__AN_P__": ("أوافق على استخدام بياناتي بشكل مجمع ومجهول لتحسين النظام — اختياري ويمكنك رفضه." if ar else "I agree to use of my data in aggregated, anonymized form to improve the system — optional, you can decline."),
        "__REQUIRED__": ("مطلوب للخدمة" if ar else "Required for service"), "__OPTIONAL__": ("اختياري" if ar else "Optional"),
        "__READ__": ("اقرأ سياسة الخصوصية" if ar else "Read Privacy Policy"), "__HOW__": ("كيف نستخدم بياناتك؟" if ar else "How do we use your data?"),
        "__CONTINUE__": ("حفظ الاختيارات والمتابعة" if ar else "Save choices & continue"),
        "__SAVING__": json.dumps("جاري المتابعة…" if ar else "Continuing…"),
        "__DISC__": ("SymptoSense أداة معلوماتية وتحليلية ولا تحل محل الاستشارة الطبية أو التشخيص أو العلاج من قبل المختصين." if ar else "SymptoSense is an informational and analytical tool and does not replace professional medical advice, diagnosis, or treatment."),
        "__SERVICE_ERR__": json.dumps("يجب الموافقة على معالجة البيانات اللازمة لاستخدام خدمة التحليل." if ar else "Service usage consent is required to use the assessment service."),
        "__GEN_ERR__": json.dumps("تعذر حفظ الاختيارات الآن. حاول مرة أخرى." if ar else "Unable to save your choices right now. Please try again."),
        "__NEXT__": json.dumps(next_url),
    }
    for k,v in vals.items(): body=body.replace(k,str(v))
    return _page(title, body)


def privacy_center_page():
    ar=_lang()=="ar"; uid=_ss_user_id(); subject=_consent_subject_key(); consent=privacy_features.get_consent(subject,uid)
    stored=privacy_features.stored_data_types(int(uid), _data_user_id())
    data_types=[
      ("Profile Information" if not ar else "معلومات الملف الشخصي", stored.get("profile_information", False)),
      ("Health Profile" if not ar else "الملف الصحي", stored.get("health_profile", False)),
      ("Symptom Information" if not ar else "معلومات الأعراض", stored.get("symptom_information", False)),
      ("Analysis History" if not ar else "سجل التحليلات", stored.get("analysis_history", False)),
      ("Medication Reminders" if not ar else "تذكيرات الأدوية", stored.get("medication_reminders", False)),
      ("Reports / Temporary Shares" if not ar else "التقارير والمشاركات المؤقتة", stored.get("reports", False)),
      ("Assistant History" if not ar else "سجل المساعد", stored.get("assistant_history", False)),
    ]
    rows=''.join('<div class="pc-data-row"><span>%s</span><b>%s</b></div>'%(label,("محفوظة" if ar else "Stored") if present else ("لا توجد بيانات محفوظة حاليًا" if ar else "No stored data currently")) for label,present in data_types)
    analytics_on=bool(consent.get('analytics_research'))
    title="مركز الخصوصية" if ar else "Privacy Center"
    body="""
    <main class="privacy-center">
      <section class="pc-hero"><span>🔐</span><div><h1>__TITLE__</h1><p>__SUB__</p></div></section>
      <section class="pc-card"><h2>__MYDATA__</h2><p class="muted">__MYDATA_P__</p>__ROWS__</section>
      <section class="pc-card"><div class="pc-head"><div><h2>📊 __AN_H__</h2><p class="muted">__AN_P__</p></div><span class="pc-status __AN_CLS__">__AN_STATUS__</span></div><button class="btn ghost" onclick="toggleAnalytics()">__CHANGE__</button><button class="btn ghost danger-lite" id="withdrawBtn" onclick="withdrawAnalytics()" __WITHDRAW_DISABLED__>__WITHDRAW__</button></section>
      <section class="pc-card"><h2>📥 __DOWNLOAD_H__</h2><p class="muted">__DOWNLOAD_P__</p><a class="btn ghost" href="/api/privacy/download">__DOWNLOAD__</a></section>
      <section class="pc-card danger-zone"><h2>🗑️ __DELETE_H__</h2><p class="muted">__DELETE_P__</p><button class="btn ghost danger-lite" onclick="deleteHealthData()">__DELETE__</button><a class="btn ghost" href="/manage">__ACCOUNT__</a></section>
      <section class="pc-card"><h2>🧾 __VERSION_H__</h2><p>__VERSION_P__</p><a href="/privacy" class="v2-source-link">__POLICY__</a></section>
    </main>
    <style>.privacy-center{max-width:850px;margin:auto;display:grid;gap:14px}.pc-hero,.pc-card{background:#fff;border:1px solid var(--v2-line);border-radius:20px;padding:clamp(18px,3vw,26px);box-shadow:var(--v2-shadow)}.pc-hero{display:flex;gap:16px;align-items:center}.pc-hero>span{font-size:40px}.pc-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start}.pc-status{padding:6px 11px;border-radius:999px;font-size:12px;font-weight:800}.pc-status.on{background:var(--v2-green-bg);color:var(--v2-green)}.pc-status.off{background:#F2F4F6;color:var(--v2-muted)}.pc-data-row{display:flex;justify-content:space-between;gap:12px;padding:10px 0;border-bottom:1px solid var(--v2-line)}.pc-data-row b{font-size:12px;color:var(--v2-muted)}.danger-lite{color:var(--v2-red)!important;border-color:#efcaca!important}.danger-zone{border-color:#f0d4d4}@media(max-width:580px){.pc-head,.pc-data-row{flex-direction:column}}</style>
    <script>
    async function toggleAnalytics(){const enable=__AN_BOOL__?false:true; if(!enable){return withdrawAnalytics();} const r=await fetch('/api/consent/preferences',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({service_usage:true,analytics_research:true})});const d=await r.json();if(d.ok)location.reload();else alert(__ERR__);}
    async function withdrawAnalytics(){if(!confirm(__WITHDRAW_CONFIRM__))return;const r=await fetch('/api/privacy/withdraw-analytics',{method:'POST'});const d=await r.json();if(d.ok)location.reload();else alert(__ERR__);}
    async function deleteHealthData(){if(!confirm(__DELETE_CONFIRM__))return;const phrase=prompt(__DELETE_PHRASE__);if(phrase!==__DELETE_EXPECT__)return;const r=await fetch('/api/privacy/delete-health-data',{method:'POST'});const d=await r.json();if(d.ok){alert(__DELETE_OK__);location.reload()}else alert(__ERR__);}
    </script>
    """
    vals={
      '__TITLE__':title,'__SUB__':("أنت تعرف ما الذي نحتفظ به ولماذا، ويمكنك التحكم في استخدام بياناتك أو حذفها." if ar else "See what we store and why, and control how your data is used or deleted."),
      '__MYDATA__':("بياناتي" if ar else "My Data"),'__MYDATA_P__':("نعرض هنا أنواع البيانات الموجودة فعليًا لهذا الحساب فقط." if ar else "Only data categories currently stored for this account are shown here."),'__ROWS__':rows,
      '__AN_H__':("تحليلات البيانات" if ar else "Data Analytics"),'__AN_P__':("يسمح هذا الخيار باستخدام البيانات المصرح بها بشكل مجمع ومجهول الهوية قدر الإمكان للتحليل الإحصائي وتحسين النظام." if ar else "Allows authorized data to be used in aggregated and anonymized form where possible for statistical analysis and system improvement."),'__AN_CLS__':'on' if analytics_on else 'off','__AN_STATUS__':("مفعّل" if ar else "Enabled") if analytics_on else ("متوقف" if ar else "Disabled"),
      '__CHANGE__':("تغيير التفضيل" if ar else "Change Preference"),'__WITHDRAW__':("سحب موافقة التحليلات" if ar else "Withdraw Analytics Consent"),'__WITHDRAW_DISABLED__':'' if analytics_on else 'disabled',
      '__DOWNLOAD_H__':("تنزيل بياناتي" if ar else "Download My Data"),'__DOWNLOAD_P__':("نزّل نسخة من البيانات المرتبطة بحسابك. لا يتضمن الملف كلمات المرور أو رموز المصادقة أو الأسرار الداخلية." if ar else "Download a copy of data associated with your account. Passwords, authentication tokens, and internal secrets are excluded."),'__DOWNLOAD__':("📥 تنزيل بياناتي" if ar else "📥 Download My Data"),
      '__DELETE_H__':("حذف بياناتي الصحية" if ar else "Delete My Health Data"),'__DELETE_P__':("يحذف البيانات الصحية المحفوظة مع إبقاء الحساب نفسه. هذا الإجراء لا يمكن التراجع عنه." if ar else "Deletes stored health data while keeping your account. This action cannot be undone."),'__DELETE__':("حذف بياناتي الصحية" if ar else "Delete My Health Data"),'__ACCOUNT__':("إدارة الملف / حذف الحساب" if ar else "Manage profile / Delete account"),
      '__VERSION_H__':("نسخة الموافقة والسياسة" if ar else "Consent & policy version"),'__VERSION_P__':(("وافقت على نسخة %s من الموافقة ونسخة %s من سياسة الخصوصية."%(consent.get('consent_version') or '—',consent.get('privacy_policy_version') or '—')) if ar else ("Current consent version: %s · Privacy Policy version: %s"%(consent.get('consent_version') or '—',consent.get('privacy_policy_version') or '—'))),'__POLICY__':("قراءة سياسة الخصوصية" if ar else "Read Privacy Policy"),
      '__AN_BOOL__':'true' if analytics_on else 'false','__ERR__':json.dumps("تعذر تنفيذ الطلب الآن." if ar else "Unable to complete the request right now."),'__WITHDRAW_CONFIRM__':json.dumps("هل أنت متأكد من إيقاف استخدام بياناتك المحفوظة والجديدة في التحليلات المستقبلية؟" if ar else "Are you sure you want to stop your stored and future data from being used in future analytics?"),'__DELETE_CONFIRM__':json.dumps("سيتم حذف بياناتك الصحية المحفوظة مع إبقاء حسابك. هذا الإجراء لا يمكن التراجع عنه." if ar else "Your stored health data will be deleted while your account remains. This cannot be undone."),'__DELETE_PHRASE__':json.dumps("اكتب حذف للتأكيد" if ar else "Type delete to confirm"),'__DELETE_EXPECT__':json.dumps("حذف" if ar else "delete"),'__DELETE_OK__':json.dumps("تم حذف البيانات الصحية المحفوظة." if ar else "Stored health data was deleted."),
    }
    for k,v in vals.items():body=body.replace(k,str(v))
    return _page(title,body)


def user_profile_page():
    ar=_lang()=="ar"; user=_ss_user() or {}; hp=db.load_health_profile(_ss_user_id()) or {}; consent=_consent_state()
    name=hp.get('display_name') or user.get('name') or ("المستخدم" if ar else "User")
    title="ملفي" if ar else "My Profile"
    links=[
      ("👤","ملفي الصحي" if ar else "Health Profile","/manage"),
      ("📜","سجل التحليلات" if ar else "Analysis History","/history"),
      ("💡","ملاحظاتي الصحية" if ar else "My Health Insights","/health-insights"),
      ("📈","رحلتي الصحية" if ar else "My Health Journey","/health-journey"),
      ("💊","أدويتي وتذكيراتي" if ar else "My Medications & Reminders","/meds"),
      ("🔐","الخصوصية والبيانات" if ar else "Privacy & Data","/privacy-center"),
      ("⚙️","الإعدادات" if ar else "Settings","/settings"),
    ]
    cards=''.join('<a class="profile-link" href="%s"><span>%s</span><b>%s</b><small>›</small></a>'%(url,icon,label) for icon,label,url in links)
    privacy_text = ("تحليلات البيانات الاختيارية: " + ("مفعّلة" if consent.get('analytics_research') else "متوقفة")) if ar else ("Optional analytics: " + ("Enabled" if consent.get('analytics_research') else "Disabled"))
    body=("""
    <main class="profile-hub">
      <section class="profile-hero"><div class="hp-avatar">👤</div><div><p class="muted">%s</p><h1>%s</h1><p>%s</p></div></section>
      <section class="profile-links">%s</section>
      <section class="pc-card"><b>🔐 %s</b><p class="muted">%s</p><a class="btn ghost" href="/privacy-center">%s</a></section>
    </main>
    <style>.profile-hub{max-width:820px;margin:auto;display:grid;gap:14px}.profile-hero,.profile-links,.pc-card{background:#fff;border:1px solid var(--v2-line);border-radius:20px;padding:22px;box-shadow:var(--v2-shadow)}.profile-hero{display:flex;gap:16px;align-items:center}.hp-avatar{width:62px;height:62px;border-radius:18px;display:grid;place-items:center;background:var(--v2-sky);font-size:28px}.profile-links{display:grid;grid-template-columns:1fr 1fr;gap:10px}.profile-link{display:grid;grid-template-columns:38px 1fr auto;gap:9px;align-items:center;padding:14px;border:1px solid var(--v2-line);border-radius:14px;background:var(--v2-bg)}.profile-link>span{font-size:22px}.profile-link small{font-size:22px;color:var(--v2-blue)}@media(max-width:600px){.profile-links{grid-template-columns:1fr}.profile-hero{align-items:flex-start}}</style>
    """ % (("مرحبًا" if ar else "Welcome"), name, ("معلوماتك الصحية اختيارية ويمكنك التحكم بها أو حذفها في أي وقت." if ar else "Your health information is optional and can be changed or deleted at any time."), cards, ("خصوصيتك تحت تحكمك" if ar else "Your privacy is under your control"), privacy_text, ("فتح مركز الخصوصية" if ar else "Open Privacy Center")))
    return _page(title,body)


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


def sources_page():
    from html import escape
    ar = _lang() == "ar"
    medical_knowledge.init_schema()
    sources = medical_knowledge.list_entities("sources", False, verification="verified")
    cards = ""
    for source in sources:
        name = escape(source.get("source_name") or source.get("organization") or "")
        description = escape((source.get("description_ar") if ar else source.get("description_en")) or "")
        url = escape(source.get("official_url") or "", quote=True)
        source_type = escape((source.get("source_type") or "trusted").replace("_", " "))
        cards += ('<article class="v2-source-card"><span class="source-type">%s</span><h2>%s</h2><p class="muted">%s</p>'
                  '<a class="btn pri" href="%s" target="_blank" rel="noopener noreferrer">%s ↗</a></article>') % (
                      source_type, name, description, url, "زيارة المصدر" if ar else "Visit source")
    if not cards:
        cards = '<div class="card">%s</div>' % ("لا توجد مصادر نشطة حاليًا." if ar else "No active sources are currently available.")
    title = "المصادر الطبية الموثوقة" if ar else "Trusted medical sources"
    body = '<main class="v2-info-page" style="max-width:1040px"><section><h1>📚 %s</h1><p>%s</p></section><div class="v2-source-grid">%s</div></main>' % (
        title,
        "نعرض الروابط الرسمية الموثقة فقط، مرتبة حسب أولوية المصدر." if ar else "Only verified official links are shown, ordered by source priority.",
        cards,
    )
    return _page(title, body)


# ---------------------------------------------------------------- chat
CHAT = {
    "ar": {
        "me": "👤 أنا",
        "voice_mode_on": "🎙️ صوتي: مفعل",
        "voice_mode_off": "🔇 صوتي: متوقف",
        "voice_mode_title": "تبديل وضع المحادثة الصوتية",
        "voice_listening": "🎧 جاري الاستماع...",
        "voice_processing": "⏳ جاري المعالجة...",
        "voice_speaking_state": "🔊 جاري القراءة...",
        "welcome": "🩺 مرحبًا بك في SymptoSense",
        "head_p": "مساعدك الذكي لفهم الأعراض الصحية",
        "muted": "التوعية فقط وليس تشخيصاً نهائياً — راجع الطبيب عند أي شك.",
        "speak_on": "🔊 قراءة: مفعلة", "speak_off": "🔇 قراءة: متوقفة",
        "speak_title": "تشغيل/إيقاف القراءة الصوتية",
        "input_ph": "اكتب هنا...", "send": "إرسال", "mic_title": "إدخال صوتي",
        "age": "كم عمرك؟ (اكتب الرقم فقط) 🧒👵", "age_ph": "مثال: 28",
        "age_invalid": "يرجى إدخال عمر صحيح بين 1 و 120.",
        "gender": "ما جنسك؟", "male": "👨 ذكر", "female": "👩 أنثى",
        "syms_f": "ما هي أعراضك؟ اضغطي على الأعراض التي تشعرين بها (يمكنك اختيار أكثر من واحد). وإذا لم تجدي ما تشعرين به، اكتبيه في صندوق الكتابة. عند الانتهاء اضغطي: ✅ انتهيت",
        "syms_m": "ما هي أعراضك؟ اضغط على الأعراض التي تشعر بها (يمكنك اختيار أكثر من واحد). وإذا لم تجد ما تشعر به، اكتبه في صندوق الكتابة. عند الانتهاء اضغط: ✅ انتهيت",
        "write_yourself": "✍️ اكتب عرضاً بنفسك",
        "sym_ph": "مثال: ألم في الساق",
        "custom_f": "لم تجدي ما تشعرين به؟ اكتبيه هنا:",
        "custom_m": "لم تجد ما تشعر به؟ اكتبه هنا:",
        "atleast_f": "اختاري عرضاً واحداً على الأقل قبل المتابعة.",
        "atleast_m": "اختر عرضاً واحداً على الأقل قبل المتابعة.",
        "done": "✅ انتهيت", "chosen": "✅ تم اختيار: ",
        "added_f": "✅ أُضيف العرض. اضغطي ✅ انتهيت عند الانتهاء أو أضيفي المزيد.",
        "added_m": "✅ أُضيف العرض. اضغط ✅ انتهيت عند الانتهاء أو أضف المزيد.",
        "start_sub": "مساعدك الذكي لفهم الأعراض الصحية",
        "start_desc": "سأطرح عليك بعض الأسئلة عن الأعراض التي تشعر بها لمساعدتك في الحصول على تقييم أولي آمن وسهل.",
        "syms_q": "ما الأعراض التي تشعر بها؟",
        "syms_more": "هل لديك أعراض أخرى؟",
        "syms_hint": "اكتب الأعراض بالتفصيل، مثل: «أشعر بصداع شديد في الجهة اليمنى مع غثيان منذ يومين»",
        "write_yourself_n": "✍️ اكتب الأعراض بنفسك",
        "custom_n": "اكتب الأعراض هنا (أو استخدم الإدخال الصوتي 🎤):",
        "added_n": "✅ أُضيف العرض. أضف المزيد ثم اضغط «ابدأ التقييم».",
        "atleast": "اختر عرضًا واحدًا على الأقل قبل البدء.",
        "start_btn": "ابدأ التقييم ←",
        "for_whom": "لمن تريد إجراء التحليل؟",
        "me_short": "👤 أنا",
        "yrs": "سنة",
        "person_badge": "التحليل لـ: ",
        "result_card_title": "📋 نتيجة التحليل",
        "result_disclaimer": "⚠️ هذا التقييم لا يُعد تشخيصًا طبيًا، ولا يُغني عن استشارة الطبيب.",
        "duration": "كم مدة هذه الأعراض؟",
        "severity": "ما شدة الأعراض؟ (من 1 خفيف جداً إلى 5 حرج جداً)",
        "conditions_f": "هل لديكِ أمراض مزمنة سابقة؟",
        "conditions_m": "هل لديك أمراض مزمنة سابقة؟",
        "other_diseases": "✏️ أمراض أخرى",
        "other_diseases_f": "✏️ اكتبي الأمراض:", "other_diseases_m": "✏️ اكتب الأمراض:",
        "cond_ph": "مثال: غدة درقية",
        "meds_f": "هل تأخذين حالياً أي أدوية؟ اذكري أسماءها (أو اضغطي تخطي).",
        "meds_m": "هل تأخذ حالياً أي أدوية؟ اذكر أسماءها (أو اضغط تخطي).",
        "skip": "⏭️ تخطي", "meds_ph": "مثال: بنادول، فولتارين",
        "notes_f": "أي ملاحظات إضافية؟ (أو اضغطي تخطي)", "notes_m": "أي ملاحظات إضافية؟ (أو اضغط تخطي)",
        "notes_ph": "مثال: أعاني منذ الصباح بعد الأكل",
        "analyzing": "جاري التحليل... ⏳", "answering": "جاري الإجابة... ⏳",
        "err": "حدث خطأ: ", "conn_err": "تعذر الاتصال، حاول مجدداً.",
        "em_t": "🚑 اطلب الطوارئ الآن",
        "em_sub": "تحتوي إجابتك على أعراض قد تكون خطيرة وتحتاج إلى رعاية طبية عاجلة. لا تتأخر في طلب المساعدة.",
        "em_flags": "الأعراض التي استدعت التنبيه:",
        "em_call": "📞 اتصل بالطوارئ",
        "em_proceed": "فهمت، اعرض التحليل",
        "em_num": "997",
        "em_copy": "اضغط لنسخ الرقم",
        "em_copied": "✅ تم النسخ",
        "em_disc": "هذا التنبيه مبني على كلمات الأعراض فقط ولا يُغني عن الرأي الطبي الفوري.",
        "blood_banner": "🧪 فحص الدم مربوط — سيُراعى في التحليل",
        "related_title": "أعراض مرتبطة قد تهمك — اضغط للإضافة",
        "dq_title": "أسئلة مقترحة لحالتك",
        "dq_danger": "متى أذهب للطوارئ فوراً؟",
        "dq_sev": "هل مستوى الخطورة يعني التوجه للطوارئ؟",
        "dq_home": "ما الذي يمكنني فعله الآن لتخفيف الأعراض؟",
        "dq_doc": "ما المعلومات التي يجب أن أحضرها للطبيب؟",
        "sim_btn": "اشرحها لي ببساطة",
        "det_btn": "أريد التفاصيل",
        "sim_fallback": "الأعراض تحتاج متابعة، والأفضل استشارة طبيب للتأكد من الحالة.",
        "sim_title": "👤 شرح مبسّط",
        "voice_chip": "🎙️ صف أعراضك صوتيًا",
        "voice_btn": "🎙️ صف أعراضك صوتيًا",
        "voice_speaking": "استمع الآن... تحدث بوضوح عن أعراضك، ثم اضغط إيقاف",
        "voice_stop": "⏹️ إيقاف",
        "voice_cancel": "إلغاء",
        "voice_thinking": "🤔 أفهم كلامك...",
        "voice_no_audio": "لم يُلتقط صوت — حاول مرة أخرى",
        "voice_err": "تعذّر تحويل الصوت: ",
        "voice_none": "لم أتعرّف على أعراض محددة",
        "voice_confirm": "✅ تأكيد ومتابعة التحليل",
        "voice_edit": "✏️ أعدل يدوياً",
        "voice_retry": "🔁 أعد التسجيل",
        "voice_syms": "الأعراض:",
        "voice_confirm_q": "هل هذا صحيح؟",
        "voice_manual": "حسناً، اختر أعراضك يدوياً:",
        "clar_yes": "نعم", "clar_no": "لا",
        "result_title": "📋 نتيجة التحليل",
        "urg_label": "مستوى الخطورة",
        "triage_why": "لماذا تم تصنيف حالتك بهذا المستوى؟",
        "urg_high": "طوارئ", "urg_medium": "يحتاج إلى موعد طبي", "urg_low": "بسيط",
        "assessment_label": "التقييم الأولي:",
        "forced_high": "⚠️ تم رفع الخطورة تلقائياً بناءً على الأعراض الحمراء.",
        "low_conf": "⚖️ الثقة منخفضة — يُفضل مراجعة الطبيب.",
        "possible": "🩺 الاحتمالات المحتملة",
        "kb_title": "🧠 لماذا ظهرت هذه الاحتمالات؟",
        "kb_matched": "الأعراض المتوافقة",
        "match_strong": "توافق مرتفع", "match_moderate": "توافق متوسط", "match_weak": "توافق منخفض",
        "sources_title": "📚 المصادر الطبية",
        "view_source": "عرض المصدر", "verified_source": "مصدر موثّق",
        "last_updated_info": "آخر تحديث للمعلومات",
        "medwarn": "💊 تحذيرات الأدوية",
        "medwarn_note": "التوعية فقط — لا توقفي دواءك الموصوف بدون استشارة الطبيب.",
        "ml_title": "📊 تحليل نموذج التعلم الآلي",
        "ml_explain": "اشرحها ببساطة",
        "ml_note": "هذه النسب تمثل مخرجات النموذج وليست احتمالات تشخيصية مؤكدة.",
        "recs": "📌 ماذا يمكنك أن تفعل الآن؟", "danger": "🚨 متى تحتاج إلى مساعدة عاجلة؟",
        "when": "🩺 متى تراجع الطبيب؟", "rec_src": "المصدر",
        "home_care": "🏠 الرعاية المنزلية", "med_guid": "💊 إرشاد الدواء",
        "q_doc": "❓ أسئلة يمكنك طرحها على طبيبك",
        "listen_all": "🔊 استمع للتحليل كاملاً",
        "fb_title": "⭐ هل أفادك التحليل؟",
        "fb_excellent": "😍 ممتاز", "fb_good": "🙂 جيد", "fb_ok": "😐 عادي", "fb_no": "😞 لا",
        "fb_thanks": "شكراً لتقييمك 🌟",
        "ask_more": "💬 اسأل عن حالتك", "hospitals": "🏥 أقرب مستشفى", "new": "🔄 تحليل جديد",
        "share": "🔗 مشاركة", "share_txt": "تقييمي الأولي: ",
        "followup_f": "اكتبي سؤالك عن حالتك 👇", "followup_m": "اكتب سؤالك عن حالتك 👇",
        "followup_ph": "مثال: هل هذا طبيعي؟ متى أتحسن؟",
        "another_q": "💬 سؤال آخر",
        "no_speech": "متصفحك لا يدعم القراءة الصوتية.",
        "no_mic": "الإدخال الصوتي غير مدعوم على هذا الجهاز أو المتصفح. يمكنك الاستمرار بالكتابة.",
        "locating": "جاري تحديد موقعك... 📍",
        "loc_err_f": "تعذر الوصول لموقعك — تأكدي من تفعيل الموقع.",
        "loc_err_m": "تعذر الوصول لموقعك — تأكد من تفعيل الموقع.",
        "no_hosp": "ما لقينا مستشفيات قريبة.",
        "hosp_title": "🏥 أقرب المستشفيات", "map": "🗺️ فتح في الخريطة", "km": " كم",
        "sp_result": "نتيجة التحليل: الخطورة ", "sp_possible": "الاحتمالات المحتملة: ",
        "sp_recs": "التوصيات:", "sp_medwarn": "تحذيرات الأدوية:", "sp_danger": "علامات الخطر: ",
        "sp_when": "متى تراجع الطبيب: ", "sp_home": "الرعاية المنزلية: ",
        "sp_medguid": "إرشاد الدواء: ", "sp_qdoc": "أسئلة اسأل طبيبك: ",
        "assess_title": "ملخص التقييم", "assess_safety": "مستوى الخطورة",
        "assess_completion": "اكتمال المعلومات", "assess_followup": "المتابعة الموصى بها",
        "assess_followup_default": "راقب الأعراض واطلب تقييمًا طبيًا إذا استمرت أو ساءت.",
        "assess_missing": "معلومات لم تُضف بعد",
        "questions_title": "أسئلة قد تهمك", "questions_sub": "اختر سؤالًا لمعرفة المزيد عن النتيجة.",
        "q_urgent_1": "ماذا أفعل الآن؟", "q_urgent_2": "هل أحتاج إلى الذهاب للطوارئ؟",
        "q_med_1": "متى أراجع الطبيب؟", "q_med_2": "ماذا يمكنني فعله في المنزل؟",
        "q_low_1": "كم قد تستمر الأعراض؟", "q_low_2": "متى تستدعي الأعراض القلق؟",
        "q通用_1": "اشرح لي هذه النتيجة أكثر", "q通用_2": "ما الأسئلة التي أطرحها على الطبيب؟",
        "why_title": "لماذا ظهر هذا التقييم؟",
        "transparency_title": "ما الذي اعتمد عليه التقييم؟",
        "transparency_sub": "نوضح المعلومات المعروفة وما يحتاج إلى توضيح إضافي.",
        "trans_known": "معلومات مؤكدة من إجاباتك", "trans_known_none": "لا توجد معلومات مؤكدة إضافية.",
        "trans_unclear": "معلومات تحتاج إلى توضيح", "trans_unclear_confidence": "درجة الثقة محدودة",
        "trans_unclear_duration": "مدة الأعراض غير محددة", "trans_unclear_notes": "التفاصيل الإضافية مختصرة",
        "trans_unclear_none": "لا توجد معلومات غير واضحة.", "trans_add_info": "إضافة معلومات",
        "trans_notasked": "معلومات لم تُسأل بعد", "trans_notasked_sleep": "نمط النوم",
        "trans_notasked_appetite": "تغير الشهية", "trans_notasked_stress": "التوتر مؤخرًا",
        "trans_notasked_family": "التاريخ العائلي",
        "trans_notasked_note": "عدم سؤال هذه المعلومات لا يعني أنها غير مهمة طبيًا.",
        "trans_add_q": "ما المعلومة التي تريد إضافتها؟", "trans_add_duration": "مدة الأعراض",
        "trans_add_meds": "الأدوية الحالية", "trans_add_notes": "تفاصيل إضافية",
        "trans_add_meds_q": "اكتب أسماء الأدوية الحالية.", "trans_add_meds_hint": "مثال: اسم الدواء والجرعة إن عُرفت",
        "trans_add_notes_q": "أضف أي تفاصيل أخرى عن الأعراض.", "trans_add_notes_hint": "مثال: وقت البداية وما يزيد الأعراض أو يخففها",
        "trans_adding": "تمت إضافة المعلومة، جارٍ تحديث التقييم…", "trans_add_done": "تم تحديث المعلومات.",
        "incomplete_days": "منذ عدة أيام", "incomplete_today": "بدأت اليوم", "incomplete_yesterday": "بدأت أمس",
        "incomplete_week": "منذ أسبوع أو أكثر", "incomplete_done": "متابعة التحليل",
        "incomplete_reanalyzing": "جارٍ تحديث التحليل…", "new_analysis": "تحليل جديد",
        "save_profile": "حفظ في الملف الصحي", "save_success": "تم الحفظ بنجاح.",
        "save_error": "تعذر الحفظ حاليًا.", "save_login_required": "سجّل الدخول لحفظ المعلومات.",
        "save_nothing_new": "لا توجد معلومات جديدة للحفظ.",
        "no_speech_api": "القراءة الصوتية غير مدعومة في هذا المتصفح.",
        "fallback_chat": "تعذر إكمال الطلب الآن. حاول مرة أخرى.",
    },
    "en": {
        "me": "👤 Me",
        "voice_mode_on": "🎙️ Voice: On",
        "voice_mode_off": "🔇 Voice: Off",
        "voice_mode_title": "Toggle voice conversation mode",
        "voice_listening": "🎧 Listening...",
        "voice_processing": "⏳ Processing...",
        "voice_speaking_state": "🔊 Reading...",
        "welcome": "🩺 Welcome to SymptoSense",
        "head_p": "Your smart assistant to understand health symptoms",
        "muted": "Awareness only, not a final diagnosis — see a doctor if in any doubt.",
        "speak_on": "🔊 Read: On", "speak_off": "🔇 Read: Off",
        "speak_title": "Toggle voice reading",
        "input_ph": "Type here...", "send": "Send", "mic_title": "Voice input",
        "age": "How old are you? (type the number only) 🧒👵", "age_ph": "Example: 28",
        "age_invalid": "Please enter a valid age between 1 and 120.",
        "gender": "What is your gender?", "male": "👨 Male", "female": "👩 Female",
        "syms_f": "What are your symptoms? Tap the ones you have (you can pick more than one). If you don't find what you feel, type it in the text box. When done, tap: ✅ Done",
        "syms_m": "What are your symptoms? Tap the ones you have (you can pick more than one). If you don't find what you feel, type it in the text box. When done, tap: ✅ Done",
        "write_yourself": "✍️ Write your own symptom",
        "sym_ph": "Example: leg pain",
        "custom_f": "Don't find what you feel? Type it here:",
        "custom_m": "Don't find what you feel? Type it here:",
        "atleast_f": "Please pick at least one symptom before continuing.",
        "atleast_m": "Please pick at least one symptom before continuing.",
        "done": "✅ Done", "chosen": "✅ Selected: ",
        "added_f": "✅ Symptom added. Tap ✅ Done when finished or add more.",
        "added_m": "✅ Symptom added. Tap ✅ Done when finished or add more.",
        "start_sub": "Your smart assistant to understand health symptoms",
        "start_desc": "I'll ask you a few questions about the symptoms you feel to help you get an initial, safe, and easy assessment.",
        "syms_q": "What symptoms are you feeling?",
        "syms_more": "Do you have any other symptoms?",
        "syms_hint": "Describe your symptoms in detail, e.g. “I've had a severe headache on the right side with nausea for two days”",
        "write_yourself_n": "✍️ Write your own symptom",
        "custom_n": "Type your symptoms here (or use voice input 🎤):",
        "added_n": "✅ Added. Add more, then tap “Start assessment”.",
        "atleast": "Please select at least one symptom before starting.",
        "start_btn": "Start assessment →",
        "for_whom": "Who is this assessment for?",
        "me_short": "👤 Me",
        "yrs": "yrs",
        "person_badge": "Assessment for: ",
        "result_card_title": "📋 Analysis Result",
        "result_disclaimer": "⚠️ This assessment is not a medical diagnosis and does not replace seeing a doctor.",
        "duration": "How long have you had these symptoms?",
        "severity": "How severe are the symptoms? (1 = very mild, 5 = critical)",
        "conditions_f": "Do you have any pre-existing chronic conditions?",
        "conditions_m": "Do you have any pre-existing chronic conditions?",
        "other_diseases": "✏️ Other conditions",
        "other_diseases_f": "✏️ Type your conditions:", "other_diseases_m": "✏️ Type your conditions:",
        "cond_ph": "Example: thyroid",
        "meds_f": "Are you currently taking any medications? List their names (or tap Skip).",
        "meds_m": "Are you currently taking any medications? List their names (or tap Skip).",
        "skip": "⏭️ Skip", "meds_ph": "Example: Paracetamol, Voltaren",
        "notes_f": "Any additional notes? (or tap Skip)", "notes_m": "Any additional notes? (or tap Skip)",
        "notes_ph": "Example: feeling unwell since the morning after eating",
        "analyzing": "Analyzing... ⏳", "answering": "Answering... ⏳",
        "err": "Error: ", "conn_err": "Connection failed, please try again.",
        "em_t": "🚑 Call emergency now",
        "em_sub": "Your input includes symptoms that may be critical and require urgent medical care. Please do not delay seeking help.",
        "em_flags": "Symptoms that triggered the alert:",
        "em_call": "📞 Call emergency",
        "em_proceed": "I understand, show the analysis",
        "em_num": "997",
        "em_copy": "Tap to copy the number",
        "em_copied": "✅ Copied",
        "em_disc": "This alert is based on symptom keywords only and is not a substitute for immediate medical advice.",
        "blood_banner": "🧪 A blood test is linked — it will be considered in the analysis",
        "related_title": "Related symptoms that may matter — tap to add",
        "dq_title": "Suggested questions for your case",
        "dq_danger": "When should I go to the ER immediately?",
        "dq_sev": "Does the severity level mean I should go to the ER?",
        "dq_home": "What can I do right now to ease the symptoms?",
        "dq_doc": "What information should I bring to the doctor?",
        "sim_btn": "Explain it simply",
        "det_btn": "I want the details",
        "sim_fallback": "The symptoms need monitoring, and it's best to consult a doctor to confirm the condition.",
        "sim_title": "👤 Simple explanation",
        "voice_chip": "🎙️ Describe your symptoms by voice",
        "voice_btn": "🎙️ Describe your symptoms by voice",
        "voice_speaking": "Listening... describe your symptoms clearly, then tap Stop",
        "voice_stop": "⏹️ Stop",
        "voice_cancel": "Cancel",
        "voice_thinking": "🤔 Understanding you...",
        "voice_no_audio": "No audio captured — try again",
        "voice_err": "Voice conversion failed: ",
        "voice_none": "No specific symptoms recognized",
        "voice_confirm": "✅ Confirm & Analyze",
        "voice_edit": "✏️ Edit manually",
        "voice_retry": "🔁 Record again",
        "voice_syms": "Symptoms:",
        "voice_confirm_q": "Is this correct?",
        "voice_manual": "OK, choose your symptoms manually:",
        "clar_yes": "Yes", "clar_no": "No",
        "result_title": "📋 Analysis result",
        "urg_label": "Severity level",
        "triage_why": "Why was your case classified at this level?",
        "urg_high": "Emergency", "urg_medium": "Needs an appointment", "urg_low": "Mild",
        "assessment_label": "Initial assessment:",
        "forced_high": "⚠️ Urgency raised automatically based on red-flag symptoms.",
        "low_conf": "⚖️ Low confidence — a doctor visit is recommended.",
        "possible": "🩺 Possible conditions",
        "kb_title": "🧠 Why did these possibilities appear?",
        "kb_matched": "Matching symptoms",
        "match_strong": "Strong match", "match_moderate": "Moderate match", "match_weak": "Weak match",
        "sources_title": "📚 Medical sources",
        "view_source": "View source", "verified_source": "Verified source",
        "last_updated_info": "Information last updated",
        "medwarn": "💊 Medication warnings",
        "medwarn_note": "Awareness only — don't stop your prescribed medication without consulting your doctor.",
        "ml_title": "📊 Machine learning model analysis",
        "ml_explain": "Explain simply",
        "ml_note": "These percentages are model outputs, not confirmed diagnostic probabilities.",
        "recs": "📌 What can you do right now?", "danger": "🚨 When do you need urgent help?",
        "when": "🩺 When should you see a doctor?", "rec_src": "Source",
        "home_care": "🏠 Home care", "med_guid": "💊 Medication guidance",
        "q_doc": "❓ Questions you can ask your doctor",
        "listen_all": "🔊 Listen to the full analysis",
        "fb_title": "⭐ Was this analysis helpful?",
        "fb_excellent": "😍 Excellent", "fb_good": "🙂 Good", "fb_ok": "😐 Average", "fb_no": "😞 No",
        "fb_thanks": "Thanks for your feedback 🌟",
        "ask_more": "💬 Ask about your case", "hospitals": "🏥 Nearest hospital", "new": "🔄 New analysis",
        "share": "🔗 Share", "share_txt": "My initial assessment: ",
        "followup_f": "Type your question about your case 👇", "followup_m": "Type your question about your case 👇",
        "followup_ph": "Example: Is this normal? When will I improve?",
        "another_q": "💬 Another question",
        "no_speech": "Your browser does not support voice reading.",
        "no_mic": "Voice input is not supported on this device/browser. You can continue by typing.",
        "locating": "Locating you... 📍",
        "loc_err_f": "Could not access your location — please enable location services.",
        "loc_err_m": "Could not access your location — please enable location services.",
        "no_hosp": "No nearby hospitals found.",
        "hosp_title": "🏥 Nearest hospitals", "map": "🗺️ Open in map", "km": " km",
        "sp_result": "Analysis result: severity ", "sp_possible": "Possible conditions: ",
        "sp_recs": "Recommendations:", "sp_medwarn": "Medication warnings:", "sp_danger": "Danger signs: ",
        "sp_when": "When to see a doctor: ", "sp_home": "Home care: ",
        "sp_medguid": "Medication guidance: ", "sp_qdoc": "Questions for your doctor: ",
        "assess_title": "Assessment summary", "assess_safety": "Risk level",
        "assess_completion": "Information completeness", "assess_followup": "Recommended follow-up",
        "assess_followup_default": "Monitor your symptoms and seek medical evaluation if they persist or worsen.",
        "assess_missing": "Information not added yet",
        "questions_title": "Questions you may have", "questions_sub": "Choose a question to learn more about the result.",
        "q_urgent_1": "What should I do right now?", "q_urgent_2": "Do I need to go to the emergency department?",
        "q_med_1": "When should I see a doctor?", "q_med_2": "What can I do at home?",
        "q_low_1": "How long might the symptoms last?", "q_low_2": "When should I be concerned?",
        "q通用_1": "Explain this result in more detail", "q通用_2": "What should I ask my doctor?",
        "why_title": "Why did this assessment appear?",
        "transparency_title": "What did the assessment use?",
        "transparency_sub": "We show what is known and what may need more detail.",
        "trans_known": "Confirmed from your answers", "trans_known_none": "No additional confirmed information.",
        "trans_unclear": "Information needing clarification", "trans_unclear_confidence": "Confidence is limited",
        "trans_unclear_duration": "Symptom duration is not specified", "trans_unclear_notes": "Additional details are brief",
        "trans_unclear_none": "No unclear information.", "trans_add_info": "Add information",
        "trans_notasked": "Information not asked yet", "trans_notasked_sleep": "Sleep pattern",
        "trans_notasked_appetite": "Appetite changes", "trans_notasked_stress": "Recent stress",
        "trans_notasked_family": "Family history",
        "trans_notasked_note": "Not asking about these items does not mean they are medically unimportant.",
        "trans_add_q": "What information would you like to add?", "trans_add_duration": "Symptom duration",
        "trans_add_meds": "Current medications", "trans_add_notes": "Additional details",
        "trans_add_meds_q": "Enter your current medications.", "trans_add_meds_hint": "Example: medication name and dose, if known",
        "trans_add_notes_q": "Add any other details about your symptoms.", "trans_add_notes_hint": "Example: when they began and what makes them better or worse",
        "trans_adding": "Information added; updating the assessment…", "trans_add_done": "Information updated.",
        "incomplete_days": "For several days", "incomplete_today": "Started today", "incomplete_yesterday": "Started yesterday",
        "incomplete_week": "For a week or longer", "incomplete_done": "Continue assessment",
        "incomplete_reanalyzing": "Updating the assessment…", "new_analysis": "New assessment",
        "save_profile": "Save to health profile", "save_success": "Saved successfully.",
        "save_error": "Unable to save right now.", "save_login_required": "Sign in to save information.",
        "save_nothing_new": "There is no new information to save.",
        "no_speech_api": "Voice reading is not supported in this browser.",
        "fallback_chat": "Unable to complete the request right now. Please try again.",
    },
}


def _related_map(ar):
    if ar:
        return {
            "🤕 صداع": ["💫 دوار", "🤢 غثيان", "😴 تعب وإرهاق", "👁️ احمرار العيون", "🤒 حمى"],
            "🤒 حمى": ["🥶 قشعريرة", "😴 تعب وإرهاق", "😷 سعال", "😣 ألم الحلق"],
            "😷 سعال": ["🤒 حمى", "🫁 ضيق التنفس", "😣 ألم الحلق", "🫀 ألم في الصدر"],
            "🫀 ألم في الصدر": ["🫁 ضيق التنفس", "💫 دوار", "🤢 غثيان", "😴 تعب وإرهاق"],
            "🤢 غثيان": ["😖 ألم في البطن", "💫 دوار", "🤕 صداع"],
            "😴 تعب وإرهاق": ["🤒 حمى", "💫 دوار", "🫁 ضيق التنفس", "🦴 ألم المفاصل"],
            "🫁 ضيق التنفس": ["🫀 ألم في الصدر", "💫 دوار", "😷 سعال"],
            "💫 دوار": ["🤕 صداع", "🤢 غثيان", "🫀 ألم في الصدر", "😴 تعب وإرهاق"],
            "🦴 ألم المفاصل": ["😴 تعب وإرهاق", "🤒 حمى"],
            "😖 ألم في البطن": ["🤢 غثيان", "🤒 حمى"],
            "🥶 قشعريرة": ["🤒 حمى", "😴 تعب وإرهاق"],
            "👁️ احمرار العيون": ["🖐️ حكة", "🤕 صداع"],
            "🦵 ألم في الرجل": ["🫁 ضيق التنفس", "😴 تعب وإرهاق"],
            "😣 ألم الحلق": ["😷 سعال", "🤒 حمى"],
            "🖐️ حكة": ["👁️ احمرار العيون", "🤒 حمى"],
        }
    return {
        "🤕 Headache": ["💫 Dizziness", "🤢 Nausea", "😴 Fatigue", "👁️ Eye redness", "🤒 Fever"],
        "🤒 Fever": ["🥶 Chills", "😴 Fatigue", "😷 Cough", "😣 Sore throat"],
        "😷 Cough": ["🤒 Fever", "🫁 Shortness of breath", "😣 Sore throat", "🫀 Chest pain"],
        "🫀 Chest pain": ["🫁 Shortness of breath", "💫 Dizziness", "🤢 Nausea", "😴 Fatigue"],
        "🤢 Nausea": ["😖 Stomach pain", "💫 Dizziness", "🤕 Headache"],
        "😴 Fatigue": ["🤒 Fever", "💫 Dizziness", "🫁 Shortness of breath", "🦴 Joint pain"],
        "🫁 Shortness of breath": ["🫀 Chest pain", "💫 Dizziness", "😷 Cough"],
        "💫 Dizziness": ["🤕 Headache", "🤢 Nausea", "🫀 Chest pain", "😴 Fatigue"],
        "🦴 Joint pain": ["😴 Fatigue", "🤒 Fever"],
        "😖 Stomach pain": ["🤢 Nausea", "🤒 Fever"],
        "🥶 Chills": ["🤒 Fever", "😴 Fatigue"],
        "👁️ Eye redness": ["🖐️ Itching", "🤕 Headache"],
        "🦵 Leg pain": ["🫁 Shortness of breath", "😴 Fatigue"],
        "😣 Sore throat": ["😷 Cough", "🤒 Fever"],
        "🖐️ Itching": ["👁️ Eye redness", "🤒 Fever"],
    }


def chat_page():
    ar = _lang() == "ar"
    if ar:
        syms = [
            "🤕 صداع", "🤒 حمى", "😷 سعال", "🫀 ألم في الصدر", "🤢 غثيان", "😴 تعب وإرهاق",
            "🫁 ضيق التنفس", "💫 دوار", "🦴 ألم المفاصل", "😖 ألم في البطن", "🥶 قشعريرة", "👁️ احمرار العيون",
            "🦵 ألم في الرجل", "😣 ألم الحلق", "🖐️ حكة", "🖐️ تنميل أو خدر",
        ]
        durs = ["⏰ أقل من 24 ساعة", "📅 1-3 أيام", "📅 4-7 أيام", "🗓️ 1-2 أسبوع", "🗓️ أكثر من أسبوعين", "📆 أكثر من شهر"]
        sevs = [("1", "1️⃣ خفيف جداً"), ("2", "2️⃣ معتدل"), ("3", "3️⃣ متوسط"), ("4", "4️⃣ شديد"), ("5", "5️⃣ حرج جداً")]
        conds = ["لا يوجد أمراض سابقة", "سكري", "ضغط الدم", "أمراض قلب", "ربو"]
    else:
        syms = [
            "🤕 Headache", "🤒 Fever", "😷 Cough", "🫀 Chest pain", "🤢 Nausea", "😴 Fatigue",
            "🫁 Shortness of breath", "💫 Dizziness", "🦴 Joint pain", "😖 Stomach pain", "🥶 Chills", "👁️ Eye redness",
            "🦵 Leg pain", "😣 Sore throat", "🖐️ Itching", "🖐️ Numbness or tingling",
        ]
        durs = ["⏰ Less than 24 hours", "📅 1-3 days", "📅 4-7 days", "🗓️ 1-2 weeks", "🗓️ More than 2 weeks", "📆 More than a month"]
        sevs = [("1", "1️⃣ Very mild"), ("2", "2️⃣ Mild"), ("3", "3️⃣ Moderate"), ("4", "4️⃣ Severe"), ("5", "5️⃣ Critical")]
        conds = ["No previous conditions", "Diabetes", "High blood pressure", "Heart disease", "Asthma"]

    body = """
    <div class="chat-wrap">
      <div class="chat-head">
        <div class="avatar" id="chatAvatar">🏥</div>
        <div><h3>SymptoSense</h3><p id="headP"></p></div>
        <div id="profileSwitcher" style="margin-left:auto;display:flex;align-items:center;gap:6px;">
          <select id="famSelect" onchange="switchFamilyMember(this.value)" style="background:rgba(255,255,255,.15);color:#fff;border:1px solid rgba(255,255,255,.3);border-radius:8px;padding:6px 10px;font-size:13px;font-family:inherit;cursor:pointer;max-width:140px;" aria-label="Select family member">
            <option value="0">👤 __ME__</option>
          </select>
        </div>
        <div class="chat-head-toggles"><button id="voiceModeBtn" class="spk-btn" onclick="toggleVoiceMode()" title="__VOICE_MODE_TITLE__">__VOICE_MODE_OFF__</button>
        <button id="spkBtn" class="spk-btn" onclick="toggleSpeak()" title="__SPEAK_TITLE__">__SPEAK_ON__</button></div>
      </div>
      <div class="ss-flow" aria-live="polite"><div class="ss-flow-copy"><span id="flowStepLabel">__FLOW_STEP__</span><span id="flowStepName">__FLOW_DEMO__</span></div><div class="ss-flow-track" role="progressbar" aria-valuemin="1" aria-valuemax="7" aria-valuenow="1" id="flowProgress"><div class="ss-flow-fill" id="flowFill"></div></div></div>
      <div class="chat-body" id="chatBody"></div>
      <div class="chat-options" id="chatOptions"></div>
      <div class="chat-input" id="chatInput" style="display:none;" role="search" aria-label="Message input">
        <input type="text" id="textInp" placeholder="__INPUT_PH__" autocomplete="off" aria-label="Type your message">
        <button onclick="startVoice()" id="micBtn" title="__MIC_TITLE__" aria-label="Voice input">🎙️</button>
        <button onclick="submitText()" aria-label="Send message">__SEND__</button>
      </div>
    </div>
    <div class="muted" id="chatSafetyNote" style="text-align:center;margin-top:10px;">__MUTED__</div>
    <div class="blood-banner" id="bloodBanner" style="display:none;"></div>
    <div class="em-overlay" id="emOverlay"></div>
    <div class="voice-overlay" id="voiceOverlay">
      <div class="voice-card">
        <div class="v-mic">🎙️</div>
        <div class="v-title">__VOICE_SP__</div>
        <div style="margin-top:10px"><select id="voiceLang" aria-label="Voice language"><option value="ar-SA">🇸🇦 العربية</option><option value="en-GB">🇬🇧 English</option></select></div>
        <div class="muted" style="font-size:12px;margin-top:9px">__VOICE_PRIVACY__</div>
        <div style="margin-top:16px;display:flex;gap:10px;justify-content:center;flex-wrap:wrap;">
          <button class="vstop" onclick="stopVoice()">__VOICE_STOP__</button>
          <button class="vcnl" onclick="cancelVoice()">__VOICE_CANCEL__</button>
        </div>
      </div>
    </div>

    <script>
    document.body.classList.add('ss-chat-page');
    const T = __T__;
    const LANG = "__LANG__";
    function TT(k) { return T[k] || k; }
    const SYMS = __SYMS__;
    const DURS = __DURS__;
    const SEVS = __SEVS__;
    const CONDS = __CONDS__;
    const REL = __REL__;
    const CLAR = [
      {syms:['🖐️ تنميل أو خدر','🖐️ Numbness or tingling','تنميل أو خدر','Numbness or tingling','تنميل','خدر','Numbness'],
       node:{q:['هل بدأ التنميل فجأة في جهة واحدة من الوجه أو الذراع أو الساق؟','Did the numbness start suddenly on one side of the face, arm, or leg?'],
         yes:{safety:['تنميل مفاجئ في جهة واحدة — يحتاج تقييماً طارئاً','Sudden one-sided numbness — needs emergency assessment']},
         no:{options:[
           {label:['في اليدين أو الأصابع','Hands or fingers'],add:['تنميل اليدين أو الأصابع','Hand or finger numbness']},
           {label:['في القدمين أو أصابع القدم','Feet or toes'],add:['تنميل القدمين أو أصابع القدم','Foot or toe numbness']},
           {label:['في الوجه، وليس بشكل مفاجئ','Face, not sudden'],add:['تنميل الوجه','Facial numbness']},
           {label:['في أكثر من مكان أو في الجهتين','Several areas or both sides'],add:['تنميل في أكثر من مكان','Numbness in multiple areas']},
           {label:['في مكان آخر — سأكتبه','Another area — I will type it'],custom:true}
         ]}}},
      {syms:['🫀 ألم في الصدر','🫀 Chest pain','ألم الصدر','Chest pain'],
       node:{q:['هل بدأ ألم الصدر فجأة أو هو شديد الآن؟','Did the chest pain start suddenly, or is it severe now?'],
         yes:{safety:['ألم صدر مفاجئ أو شديد — يحتاج تقييماً عاجلاً','Sudden or severe chest pain — needs urgent assessment']},
         no:{q:['هل يصاحب الألم ضيق تنفس أو تعرّق بارد أو دوخة شديدة؟','Does it come with breathlessness, cold sweating, or severe dizziness?'],yes:{safety:['ألم الصدر مع أعراض مصاحبة مقلقة','Chest pain with concerning associated symptoms']},no:{end:true}}}},
      {syms:['🤢 غثيان','🤢 Nausea','غثيان','Nausea'],
       node:{q:['هل يوجد قيء متكرر أو لا تستطيع الاحتفاظ بالسوائل؟','Are you vomiting repeatedly or unable to keep fluids down?'],
         yes:{q:['هل يوجد دم في القيء أو ألم شديد جدًا في البطن؟','Is there blood in the vomit or very severe abdominal pain?'],yes:{safety:['قيء مع دم أو ألم بطن شديد جدًا','Vomiting blood or very severe abdominal pain']},no:{end:true}},
         no:{q:['هل بدأ الغثيان بعد طعام معين أو دواء جديد؟','Did the nausea begin after a particular food or a new medicine?'],yes:{end:true},no:{end:true}}}},
      {syms:['😴 تعب وإرهاق','😴 Fatigue','تعب وإرهاق','Fatigue'],
       node:{q:['هل التعب شديد ومفاجئ أو يصاحبه إغماء أو ضيق تنفس؟','Is the fatigue sudden and severe, or accompanied by fainting or breathlessness?'],
         yes:{safety:['تعب شديد مفاجئ مع علامة مقلقة','Sudden severe fatigue with a concerning sign']},
         no:{q:['هل يستمر التعب رغم النوم والراحة؟','Does the fatigue continue despite sleep and rest?'],yes:{end:true},no:{end:true}}}},
      {syms:['🦴 ألم المفاصل','🦴 Joint pain','ألم المفاصل','Joint pain'],
       node:{q:['هل المفصل متورم أو أحمر أو ساخن؟','Is the joint swollen, red, or hot?'],
         yes:{q:['هل يصاحب ذلك حمى أو عدم القدرة على تحريك المفصل؟','Is there fever or inability to move the joint?'],yes:{safety:['مفصل ساخن أو متورم مع حمى أو صعوبة حركة','Hot or swollen joint with fever or inability to move it']},no:{end:true}},
         no:{q:['هل بدأ الألم بعد إصابة أو مجهود واضح؟','Did the pain start after an injury or clear physical strain?'],yes:{end:true},no:{end:true}}}},
      {syms:['🥶 قشعريرة','🥶 Chills','قشعريرة','Chills'],
       node:{q:['هل توجد حمى مقاسة أو شعور واضح بارتفاع الحرارة؟','Do you have a measured fever or clearly feel feverish?'],
         yes:{q:['هل يصاحبها ضيق تنفس أو تشوش أو تيبس في الرقبة؟','Is there breathlessness, confusion, or neck stiffness?'],yes:{safety:['قشعريرة وحمى مع علامة خطر','Chills and fever with a red flag']},no:{end:true}},
         no:{q:['هل القشعريرة مستمرة أو تتكرر؟','Are the chills persistent or recurring?'],yes:{end:true},no:{end:true}}}},
      {syms:['🖐️ حكة','🖐️ Itching','حكة','Itching'],
       node:{q:['هل توجد صعوبة تنفس أو تورم في الشفاه أو اللسان أو الحلق؟','Is there trouble breathing or swelling of the lips, tongue, or throat?'],
         yes:{safety:['حكة مع صعوبة تنفس أو تورم بالفم أو الحلق','Itching with breathing difficulty or mouth/throat swelling']},
         no:{prompt:['أين تظهر الحكة؟','Where is the itching?'],options:[
           {label:['في مكان محدد','One specific area']},{label:['في أكثر من مكان','Several areas']},
           {label:['منتشرة في معظم الجسم','Across most of the body']},{label:['مكان آخر — سأكتبه','Another area — I will type it'],custom:true}
         ]}}},
      {syms:['👁️ احمرار العيون','👁️ Eye redness','احمرار العين','Eye redness'],
       node:{q:['هل تشعر بألم في العين؟','Do you feel pain in the eye?'],
         yes:{q:['هل الألم شديد؟','Is the pain severe?'],
           yes:{safety:['ألم شديد في العين مع احمرار','Severe eye pain with redness']},
           no:{q:['هل لديك إفرازات من العين؟','Do you have eye discharge?'],yes:{end:true},no:{end:true}}},
         no:{q:['هل لديك حكة في العين؟','Do you have itching in the eye?'],yes:{end:true},no:{end:true}}}},
      {syms:['🤕 صداع','🤕 Headache','صداع','Headache'],
       node:{q:['هل بدأ الصداع بشكل مفاجئ وشديد جداً؟','Did the headache start suddenly and very severely?'],
         yes:{safety:['صداع مفاجئ وشديد — يحتاج تقييماً عاجلاً','Sudden severe headache — needs urgent evaluation']},
         no:{q:['هل لديك حرارة؟','Do you have a fever?'],
           yes:{q:['هل لديك تيبس في الرقبة؟','Do you have neck stiffness?'],
             yes:{safety:['حرارة مع تيبس الرقبة — يحتاج تقييماً عاجلاً','Fever with neck stiffness — needs urgent evaluation']},
             no:{end:true}},
           no:{end:true}}}},
      {syms:['🤒 حمى','🤒 Fever','حمى','Fever'],
       node:{q:['هل لديك تيبس في الرقبة؟','Do you have neck stiffness?'],
         yes:{safety:['حرارة مع تيبس الرقبة','Fever with neck stiffness']},
         no:{q:['هل تشعر بصعوبة في التنفس؟','Do you have difficulty breathing?'],
           yes:{safety:['حرارة مع صعوبة تنفس','Fever with difficulty breathing']},
           no:{end:true}}}},
      {syms:['😷 سعال','😷 Cough','سعال','Cough'],
       node:{q:['هل يوجد دم مع السعال؟','Is there blood with the cough?'],
         yes:{safety:['سعال مصحوب بدم','Cough with blood']},
         no:{q:['هل تعاني من ضيق تنفس مع السعال؟','Do you have shortness of breath with the cough?'],
           yes:{safety:['سعال مع ضيق تنفس','Cough with shortness of breath']},
           no:{end:true}}}},
      {syms:['💫 دوار','💫 Dizziness','دوخة','Dizziness'],
       node:{q:['هل فقدت الوعي أو شعرت بالإغماء؟','Did you lose consciousness or feel like fainting?'],
         yes:{safety:['دوار مع إغماء','Dizziness with fainting']},
         no:{end:true}}},
      {syms:['🫁 ضيق التنفس','🫁 Shortness of breath','ضيق التنفس','Shortness of breath'],
       node:{q:['هل يزداد ضيق التنفس عند الاستلقاء؟','Does the breathlessness worsen when lying down?'],
         yes:{safety:['ضيق تنفس يزداد عند الاستلقاء','Breathlessness that worsens when lying down']},
         no:{end:true}}},
      {syms:['🦵 ألم في الرجل','🦵 Leg pain','ألم الرجل أو الساق','Leg pain'],
       node:{q:['هل هناك تورم أو حرارة في الساق؟','Is there swelling or warmth in the leg?'],
         yes:{safety:['تورم أو حرارة في الساق مع ألم','Swelling or warmth in the leg with pain']},
         no:{end:true}}},
      {syms:['😖 ألم في البطن','😖 Stomach pain','ألم البطن','Abdominal pain'],
       node:{q:['هل الألم شديد جداً؟','Is the pain very severe?'],
         yes:{q:['هل يمنعك الألم من الوقوف أو الحركة؟','Does the pain stop you from standing or moving?'],
           yes:{safety:['ألم بطن شديد يمنع الحركة','Severe stomach pain preventing movement']},
           no:{end:true}},
         no:{end:true}}},
      {syms:['😣 ألم الحلق','😣 Sore throat','ألم الحلق','Sore throat'],
       node:{q:['هل تجد صعوبة في البلع أو التنفس؟','Do you have trouble swallowing or breathing?'],
         yes:{safety:['صعوبة بلع أو تنفس مع ألم حلق','Difficulty swallowing or breathing with sore throat']},
         no:{end:true}}},
    ];
    document.getElementById('headP').textContent = TT('head_p');
    try { if (localStorage.getItem('symptosense_blood_id')) { const bb = document.getElementById('bloodBanner'); bb.textContent = TT('blood_banner'); bb.style.display = 'block'; } } catch (e) {}
    const state = { age:null, gender:null, symptoms:[], duration:null, severity:null, location:null, conditions:null, medications:null, allergies:null, notes:null, history_answered:false, step:'age', member_id:0, member_name:'__ME__', smart_prompt_shown:false, previous_record_id:null };
    // Result rendering also uses this profile context. Keep it in the shared
    // chat-script scope instead of declaring it only inside runAnalysis().
    let useSaved = false;
    let profileMissing = [];
    let userInfo = null;
    let compareBase = null;
    let lastAnalysisInput = null;
    let adaptiveQuestionNo = 0;
    const bodyEl = document.getElementById('chatBody');
    const optsEl = document.getElementById('chatOptions');
    const inpEl = document.getElementById('chatInput');
    const textInp = document.getElementById('textInp');
    const famSelect = document.getElementById('famSelect');
    function updateFlow(step) {
      var map = {member:1,age:1,gender:1,symptoms:2,duration:3,severity:4,notes:5,conditions:6,medications:6,allergies:6,review:7,followup:7};
      var number = map[step] || 1;
      var names = LANG === 'ar' ? ['العمر والجنس','الأعراض','مدة الأعراض','شدة الأعراض','الأعراض المصاحبة','التاريخ الصحي والأدوية والحساسيات','النتيجة'] : ['Age and sex','Symptoms','Symptom duration','Symptom severity','Associated symptoms','History, medicines and allergies','Result'];
      document.getElementById('flowStepLabel').textContent = (LANG === 'ar' ? 'الخطوة ' : 'Step ') + number + (LANG === 'ar' ? ' من 7' : ' of 7');
      document.getElementById('flowStepName').textContent = names[number - 1];
      document.getElementById('flowFill').style.width = ((number / 7) * 100) + '%';
      var bar = document.getElementById('flowProgress'); if (bar) bar.setAttribute('aria-valuenow', String(number));
    }
    textInp.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') { e.preventDefault(); submitText(); }
    });
    // Load family members into switcher
    (function loadFamilyMembers() {
      fetch('/api/family').then(r=>r.json()).then(d=>{
        if(d.ok && d.members && d.members.length) {
          const emojis = {'me':'👤','mother':'👩','father':'👨','daughter':'👧','son':'👦','grandparent':'👵','other':'🧑'};
          d.members.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m.id;
            const em = emojis[m.relation] || '🧑';
            opt.textContent = em + ' ' + m.name;
            famSelect.appendChild(opt);
          });
        }
      }).catch(()=>{});
    })();
    function switchFamilyMember(val) {
      state.member_id = parseInt(val) || 0;
      state.member_name = famSelect.options[famSelect.selectedIndex].textContent.replace(/^[^\\s]+\\s*/, '');
      state.age = null; state.gender = null;
    }

    function add(msg, cls) {
      const d = document.createElement('div');
      d.className = 'bubble ' + cls;
      d.textContent = msg;
      bodyEl.appendChild(d);
      bodyEl.scrollTop = bodyEl.scrollHeight;
      if (cls === 'bot' && autoSpeak && msg !== lastSpokenMsg) {
        lastSpokenMsg = msg;
        speakText(msg);
      }
      return d;
    }
    let autoSpeak = true;
    let lastSpokenMsg = '';
    function toggleSpeak() {
      autoSpeak = !autoSpeak;
      const b = document.getElementById('spkBtn');
      if (b) b.textContent = autoSpeak ? TT('speak_on') : TT('speak_off');
    }
    function speakText(txt) {
      if (!('speechSynthesis' in window)) return;
      const clean = s => String(s || '').replace(/[^\u0600-\u06FF\\w\\s.,!?()\\-%/،؟]/g, ' ').replace(/\\s{2,}/g, ' ').trim();
      const t = clean(txt);
      if (!t) return;
      speechSynthesis.cancel();
      const uu = new SpeechSynthesisUtterance(t);
      uu.lang = LANG === 'en' ? 'en-GB' : 'ar-SA';
      const pre = LANG === 'en' ? 'en' : 'ar';
      const v = speechSynthesis.getVoices().find(v => v.lang && v.lang.toLowerCase().indexOf(pre) === 0);
      if (v) uu.voice = v;
      uu.rate = 0.95;
      speechSynthesis.speak(uu);
    }
    function addHtml(html, cls) {
      const d = document.createElement('div');
      d.className = 'bubble ' + cls;
      d.innerHTML = html;
      bodyEl.appendChild(d);
      bodyEl.scrollTop = bodyEl.scrollHeight;
      return d;
    }
    function addQ(msg) {
      const d = document.createElement('div');
      d.className = 'bubble q';
      d.textContent = msg;
      bodyEl.appendChild(d);
      bodyEl.scrollTop = bodyEl.scrollHeight;
      if (autoSpeak && msg !== lastSpokenMsg) { lastSpokenMsg = msg; speakText(msg); }
      return d;
    }
    function clearOpts() { optsEl.innerHTML = ''; optsEl.classList.remove('symptom-picker'); }
    function showOpts(items) {
      clearOpts();
      items.forEach(it => {
        const b = document.createElement('button');
        b.className = 'opt' + (it.sel ? ' sel' : '') + (it.cls ? ' ' + it.cls : '');
        b.textContent = it.label;
        b.onclick = it.fn;
        optsEl.appendChild(b);
      });
    }
    function showText(placeholder, keepOpts) {
      if (!keepOpts) clearOpts();
      inpEl.style.display = 'flex';
      textInp.placeholder = placeholder;
      textInp.value = '';
      textInp.inputMode = state.step === 'age' ? 'numeric' : 'text';
      textInp.setAttribute('dir', state.step === 'age' ? 'ltr' : (LANG === 'ar' ? 'rtl' : 'ltr'));
      if (window.matchMedia('(hover:hover) and (pointer:fine)').matches) textInp.focus();
    }
    function hideText() { inpEl.style.display = 'none'; }
    function send() {
      const v = textInp.value.trim();
      if (!v) return;
      hideText();
      add(v, 'user');
      textInp.value = '';
      return v;
    }

    function startChat() {
      addHtml('<div class="chat-start"><div class="cs-logo">🩺</div><div class="cs-title">' + esc(TT('welcome')) + '</div><div class="cs-sub">' + esc(TT('start_sub')) + '</div><div class="cs-desc">' + esc(TT('start_desc')) + '</div><div class="cs-voice" onclick="startVoice()">🎙️ ' + esc(TT('voice_btn')) + '</div></div>', 'q start');
      const reId = parseInt(new URLSearchParams(location.search).get('reanalyze') || '0');
      if (reId) {
        fetch('/api/analysis/'+reId).then(r=>r.json()).then(function(d){
          if (!d.ok || !d.analysis) throw new Error('not_found');
          const a=d.analysis; compareBase={record_id:a.id,symptoms:(a.symptoms||[]).slice(),duration:a.duration,severity:a.severity,urgency:a.urgency};
          state.previous_record_id=a.id; state.age=a.age||null; state.gender=a.gender||null; state.symptoms=(a.symptoms||[]).slice(); state.duration=null; state.severity=null; state.notes=(a.result||{}).notes||''; state.smart_prompt_shown=true;
          add(LANG==='ar'?'تم تحميل التحليل السابق. عدّل الأعراض إذا احتجت، ثم سنسألك عن المدة والشدة من جديد.':'Previous analysis loaded. Edit symptoms if needed, then we will ask duration and severity again.','bot');
          askSymptoms();
        }).catch(function(){ add(LANG==='ar'?'تعذر تحميل التحليل السابق.':'Unable to load the previous analysis.','bot'); askMember(); });
        return;
      }
      try {
        fetch('/api/user-info').then(function(r){ return r.json(); }).then(function(ui){
          // Reuse this already-loaded account/profile context at result time so
          // clicking Analyze does not incur another sequential network request.
          userInfo = ui || null;
          window.__USER_INFO__ = ui || null;
          if (ui.ok && ui.logged_in && ui.has_profile && ui.privacy && ui.privacy.use_in_analysis && ui.profile) {
            smartCtxShow(ui.profile, function(action){
              if (action === 'use') {
                if (ui.profile.age) state.age = ui.profile.age;
                if (ui.profile.gender) state.gender = ui.profile.gender;
                add((LANG==='ar'?'تم استخدام معلومات الملف الشخصي ✅':'Profile info loaded ✅'), 'bot');
              }
              askMember();
            }, ui);
          } else {
            askMember();
          }
        }).catch(function(){ askMember(); });
      } catch(e) { askMember(); }
    }
    let MEMBERS = [];
    function askMember() {
      state.step = 'member';
      updateFlow(state.step);
      fetch('/api/family').then(r => r.json()).then(d => {
        MEMBERS = (d && d.members) || [];
        if (!MEMBERS.length) { state.member = null; askAge(); return; }
        const items = [{label: TT('me_short'), fn:()=>{ state.member = null; add(TT('me_short'),'user'); askAge(); }}];
        MEMBERS.forEach(m => items.push({label: m.name + (m.age ? ' — ' + m.age + ' ' + TT('yrs') : ''), fn:()=>{
          state.member = {id: m.id, name: m.name, age: m.age, gender: m.gender, conditions: m.conditions, medications: m.medications};
          if (m.age) state.age = m.age;
          if (m.gender) state.gender = m.gender;
          add(m.name + (m.age ? ' — ' + m.age + ' ' + TT('yrs') : ''), 'user');
          askAge();
        }}));
        addQ('👥 ' + TT('for_whom'));
        showOpts(items);
      }).catch(() => { state.member = null; askAge(); });
    }
    function appendStartBtn(first) {
      const s = document.createElement('button');
      s.className = 'start-btn' + (first ? ' is-next' : '');
      s.textContent = state.symptoms.length
        ? (LANG === 'ar' ? 'التالي: مدة الأعراض ←' : 'Next: symptom duration →')
        : TT('start_btn');
      s.disabled = !state.symptoms.length;
      s.setAttribute('aria-disabled', state.symptoms.length ? 'false' : 'true');
      s.onclick = beginAssessment;
      if (first && optsEl.firstChild) optsEl.insertBefore(s, optsEl.firstChild);
      else optsEl.appendChild(s);
    }
    function beginAssessment() {
      if (!state.symptoms.length) { add(TT('atleast'), 'bot'); return; }
      add(TT('chosen') + state.symptoms.join(LANG === 'en' ? ', ' : '، '), 'user');
      clearOpts();
      if (qualityReturnKey === 'main_symptom' || qualityReturnKey === 'associated_symptoms') { qualityReturnKey=null; showDataQualityGate(); return; }
      askDuration();
    }

    // ---------------- Voice symptom input ----------------
    // Audio is not uploaded or stored by SymptoSense. The browser performs speech
    // recognition when supported; only the transcript is sent for structured parsing.
    let voiceRec = null;
    function startVoice() {
      if (state.step === 'followup') { add(TT('voice_manual'), 'bot'); return; }
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SR) { add(TT('no_mic'), 'bot'); return; }
      clearOpts(); addQ('🎙️ ' + TT('voice_speaking'));
      const ov=document.getElementById('voiceOverlay'), sel=document.getElementById('voiceLang');
      if(sel) sel.value=LANG==='en'?'en-GB':'ar-SA'; ov.style.display='flex';
      voiceRec=new SR(); voiceRec.lang=sel?sel.value:(LANG==='en'?'en-GB':'ar-SA'); voiceRec.continuous=false; voiceRec.interimResults=false; voiceRec.maxAlternatives=1;
      voiceRec.onresult=function(ev){const text=((ev.results&&ev.results[0]&&ev.results[0][0]&&ev.results[0][0].transcript)||'').trim(); hideVoice(); if(!text){add(TT('voice_no_audio'),'bot');return;} parseVoiceTranscript(text);};
      voiceRec.onerror=function(ev){hideVoice(); const msg=(ev&&ev.error==='not-allowed')?(LANG==='ar'?'لم يتم منح إذن الميكروفون. يمكنك الاستمرار بالكتابة.':'Microphone permission was not granted. You can continue by typing.'):TT('voice_no_audio'); add(msg,'bot');};
      voiceRec.onend=function(){ if(document.getElementById('voiceOverlay').style.display!=='none' && voiceRec){ hideVoice(); }};
      try{voiceRec.start();}catch(e){hideVoice();add(TT('no_mic'),'bot');}
    }
    function stopVoice(){if(voiceRec){try{voiceRec.stop();}catch(e){}}}
    function cancelVoice(){if(voiceRec){try{voiceRec.abort();}catch(e){}}hideVoice();}
    function hideVoice(){document.getElementById('voiceOverlay').style.display='none';voiceRec=null;}
    async function parseVoiceTranscript(text){
      add(TT('voice_thinking'),'bot');
      try{const langSel=document.getElementById('voiceLang');const parseLang=(langSel&&langSel.value&&langSel.value.startsWith('en'))?'en':'ar';const r=await fetch('/api/voice/parse',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:text,lang:parseLang})});const d=await r.json();if(!r.ok||!d.ok){if(d.consent_required){location.href=d.consent_url;return;}add(TT('voice_err')+(d.error||''),'bot');return;}showParsed(d.text,d.parsed);}catch(e){add(TT('conn_err'),'bot');}
    }
    function showParsed(text, parsed) {
      const symStr = parsed.symptoms && parsed.symptoms.length ? parsed.symptoms.join(LANG==='en' ? ', ' : '، ') : TT('voice_none');
      let h='<div class="res-sec">🎙️ <i>"'+esc(text)+'"</i></div>';
      h+='<div class="res-assess"><div class="res-assess-h">'+esc(LANG==='ar'?'فهمنا التالي':'We understood')+'</div>';
      h+='<div class="res-assess-row"><span class="res-assess-label">🩺 '+esc(TT('voice_syms'))+'</span><span>'+esc(symStr)+'</span></div>';
      if(parsed.duration)h+='<div class="res-assess-row"><span class="res-assess-label">📅 '+esc(TT('duration'))+'</span><span>'+esc(parsed.duration)+'</span></div>';
      if(parsed.location)h+='<div class="res-assess-row"><span class="res-assess-label">📍 '+esc(LANG==='ar'?'المكان':'Location')+'</span><span>'+esc(parsed.location)+'</span></div>';
      if(parsed.severity_10)h+='<div class="res-assess-row"><span class="res-assess-label">📊 '+esc(TT('severity'))+'</span><span>'+esc(String(parsed.severity_10))+'/10</span></div>';
      h+='</div><div class="muted">'+esc(TT('voice_confirm_q'))+'</div>'; addHtml(h,'bot');
      showOpts([{label:TT('voice_confirm'),fn:()=>voiceConfirm(parsed)},{label:TT('voice_retry'),fn:startVoice},{label:TT('voice_edit'),fn:()=>{add(TT('voice_manual'),'bot');askSymptoms();}}]);
    }
    function voiceConfirm(parsed){
      if(parsed.symptoms&&parsed.symptoms.length){state.symptoms=parsed.symptoms;add(TT('chosen')+parsed.symptoms.join(LANG==='en'?', ':'، '),'user');}
      if(parsed.duration)state.duration=parsed.duration;if(parsed.severity)state.severity=parsed.severity;if(parsed.location){state.location=parsed.location;state.notes=((state.notes||'')+' '+(LANG==='ar'?'المكان: ':'Location: ')+parsed.location).trim();}
      clearOpts(); if(state.member&&state.member.age)askGender();else askAge();
    }

    // ---------------- Voice Conversation Mode ----------------
    let voiceMode = false;
    let liveRecognition = null;
    let voiceState = 'idle';
    function toggleVoiceMode() {
      voiceMode = !voiceMode;
      const btn = document.getElementById('voiceModeBtn');
      const avatar = document.getElementById('chatAvatar');
      if (voiceMode) {
        btn.textContent = TT('voice_mode_on');
        btn.style.background = 'rgba(46,173,104,.3)';
        if (avatar) avatar.textContent = '🎙️';
        startLiveRecognition();
      } else {
        btn.textContent = TT('voice_mode_off');
        btn.style.background = 'rgba(255,255,255,.15)';
        if (avatar) avatar.textContent = '🏥';
        stopLiveRecognition();
      }
    }
    function setVoiceState(s) {
      voiceState = s;
      const avatar = document.getElementById('chatAvatar');
      if (s === 'listening') { if (avatar) avatar.textContent = '🎧'; }
      else if (s === 'processing') { if (avatar) avatar.textContent = '⏳'; }
      else if (s === 'speaking') { if (avatar) avatar.textContent = '🔊'; }
      else { if (avatar) avatar.textContent = voiceMode ? '🎙️' : '🏥'; }
    }
    function startLiveRecognition() {
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SR) { add(TT('no_speech_api') || 'Voice recognition not supported in this browser', 'bot'); voiceMode = false; document.getElementById('voiceModeBtn').textContent = TT('voice_mode_off'); return; }
      liveRecognition = new SR();
      liveRecognition.lang = LANG === 'en' ? 'en-GB' : 'ar-SA';
      liveRecognition.continuous = true;
      liveRecognition.interimResults = true;
      let finalTranscript = '';
      let silenceTimer = null;
      liveRecognition.onresult = function(event) {
        let interim = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript;
          } else {
            interim += event.results[i][0].transcript;
          }
        }
        if (silenceTimer) clearTimeout(silenceTimer);
        if (finalTranscript.trim()) {
          silenceTimer = setTimeout(function() {
            if (voiceMode && finalTranscript.trim()) {
              setVoiceState('processing');
              submitVoiceText(finalTranscript.trim());
              finalTranscript = '';
            }
          }, 1500);
        }
      };
      liveRecognition.onerror = function(e) {
        if (e.error === 'no-speech' || e.error === 'aborted') {
          if (voiceMode) { setVoiceState('idle'); setTimeout(function(){ if (voiceMode) tryLiveRestart(); }, 500); }
          return;
        }
        if (voiceMode) { setTimeout(function(){ if (voiceMode) tryLiveRestart(); }, 1000); }
      };
      liveRecognition.onend = function() {
        if (voiceMode) { setVoiceState('idle'); setTimeout(function(){ if (voiceMode) tryLiveRestart(); }, 300); }
      };
      try { liveRecognition.start(); setVoiceState('listening'); } catch(e) {}
    }
    function tryLiveRestart() {
      if (!voiceMode || !liveRecognition) return;
      try { liveRecognition.start(); setVoiceState('listening'); } catch(e) { setTimeout(function(){ if (voiceMode) tryLiveRestart(); }, 500); }
    }
    function stopLiveRecognition() {
      if (liveRecognition) { try { liveRecognition.stop(); } catch(e) {} liveRecognition = null; }
      setVoiceState('idle');
    }
    async function submitVoiceText(text) {
      add(text, 'user');
      clearOpts();
      setVoiceState('processing');
      if (state.step === 'age') {
        const num = parseInt(text);
        if (num > 0 && num < 121) { state.age = num; setVoiceState('idle'); askGender(); }
        else { add(TT('age_invalid'), 'bot'); setVoiceState('listening'); }
      } else if (state.step === 'symptoms') {
        const lowerText = text.toLowerCase();
        const matched = SYMS.filter(function(s) { return lowerText.includes(s.replace(/[^\u0600-\u06FF\\w\\s]/g,'').trim().toLowerCase()); });
        if (matched.length) { state.symptoms = matched; add(TT('chosen') + matched.join(', '), 'user'); setVoiceState('idle'); askDuration(); }
        else { state.symptoms = [text]; add(TT('chosen') + text, 'user'); setVoiceState('idle'); askDuration(); }
      } else if (state.step === 'duration') {
        state.duration = text; setVoiceState('idle'); askSeverity();
      } else if (state.step === 'severity') {
        const num = parseInt(text);
        if (num >= 1 && num <= 5) { state.severity = num; setVoiceState('idle'); askConditions(); }
        else { state.severity = 3; setVoiceState('idle'); askConditions(); }
      } else if (state.step === 'conditions') {
        state.conditions = text; setVoiceState('idle'); askMeds();
      } else if (state.step === 'medications') {
        state.medications = text; setVoiceState('idle'); askNotes();
      } else if (state.step === 'notes') {
        state.notes = text; setVoiceState('idle'); showDataQualityGate();
      } else {
        state.notes = (state.notes || '') + ' ' + text;
        setVoiceState('idle');
        showDataQualityGate();
      }
    }
    // Override add() to auto-speak in voice mode
    const _origAdd = add;
    add = function(msg, cls) {
      _origAdd(msg, cls);
      if (voiceMode && cls === 'bot') {
        setVoiceState('speaking');
        const clean = s => String(s || '').replace(/[^\u0600-\u06FF\\w\\s.,!?()\\-%/،؟]/g, ' ').replace(/\\s{2,}/g, ' ').trim();
        const t = clean(msg);
        if (t && 'speechSynthesis' in window) {
          speechSynthesis.cancel();
          const uu = new SpeechSynthesisUtterance(t);
          uu.lang = LANG === 'en' ? 'en-GB' : 'ar-SA';
          uu.rate = 0.95;
          uu.onend = function() { if (voiceMode) { setVoiceState('listening'); tryLiveRestart(); } };
          speechSynthesis.speak(uu);
        }
      }
    };

    const GENERIC_CLAR={prompt:['أين تشعر بهذا العرض أو في أي جزء من الجسم يظهر؟','Where do you feel this symptom, or which part of the body does it affect?'],options:[
      {label:['الرأس أو الوجه','Head or face']},{label:['الصدر أو التنفس','Chest or breathing']},
      {label:['البطن أو الجهاز الهضمي','Abdomen or digestion']},{label:['الذراعان أو الساقان','Arms or legs']},
      {label:['أكثر من مكان','More than one area']},{label:['سأكتب المكان بالتفصيل','I will type the location'],custom:true}
    ]};
    // ---------------- Missing-symptom clarification ----------------
    let clarQueue = [], clarIndex = 0, clarCustomNext = null;
    let differentialAsked = [], differentialNegatives = [], differentialCount = 0, differentialCandidates = [];
    function startClarify() {
      clarQueue = [];
      clarIndex = 0;
      adaptiveQuestionNo = 0;
      differentialAsked = []; differentialNegatives = []; differentialCount = 0; differentialCandidates = [];
      (state.symptoms || []).forEach(function(s){
        var matched=false;
        for (var i = 0; i < CLAR.length; i++) {
          if (CLAR[i].syms.indexOf(s) !== -1) { clarQueue.push(CLAR[i].node); matched=true; break; }
        }
        if(!matched) clarQueue.push(GENERIC_CLAR);
      });
      nextClarNode();
    }
    function nextClarNode() {
      if (clarIndex < clarQueue.length) walkClarNode(clarQueue[clarIndex++]);
      else startDifferentialQuestions();
    }
    async function startDifferentialQuestions() {
      if (differentialCount >= 5) { showDataQualityGate(); return; }
      state.step = 'clarification';
      updateFlow('notes');
      clearOpts();
      try {
        const r = await fetch('/api/analyze/differential-question', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body:JSON.stringify({symptoms:state.symptoms, asked:differentialAsked, negatives:differentialNegatives, lang:LANG})
        });
        const d = await r.json();
        if (d.consent_required) { location.href=d.consent_url||'/consent?next=/chat'; return; }
        if (d.candidates && d.candidates.length) differentialCandidates = d.candidates;
        if (!d.ok || d.done || !d.question || !d.symptom_slug) { showDataQualityGate(); return; }
        differentialCount += 1;
        differentialAsked.push(d.symptom_slug);
        addHtml('<div class="adaptive-step">'+esc((LANG==='ar'?'سؤال تمييزي ':'Differential question ')+differentialCount)+'</div>','bot');
        addQ('🩺 ' + d.question);
        showOpts([
          {label:TT('clar_yes'), fn:function(){
            add(TT('clar_yes'),'user');
            if (d.symptom_name && state.symptoms.indexOf(d.symptom_name) === -1) state.symptoms.push(d.symptom_name);
            state.notes += (state.notes?' ':'') + d.question + ' -> ' + (LANG==='ar'?'نعم':'Yes');
            startDifferentialQuestions();
          }},
          {label:TT('clar_no'), fn:function(){
            add(TT('clar_no'),'user');
            differentialNegatives.push(d.symptom_slug);
            state.notes += (state.notes?' ':'') + d.question + ' -> ' + (LANG==='ar'?'لا':'No');
            startDifferentialQuestions();
          }}
        ]);
      } catch(e) { showDataQualityGate(); }
    }
    function walkClarNode(node) {
      if (!node) { nextClarNode(); return; }
      if (node.safety) {
        const label = LANG === 'en' ? node.safety[1] : node.safety[0];
        addHtml('<div class="warn">🚨 ' + esc(label) + '</div>', 'bot');
        showEmergency({emergency:true, emergency_flags:[label], _clar:true});
        return;
      }
      if (node.options) {
        const prompt=node.prompt?(LANG==='en'?node.prompt[1]:node.prompt[0]):(LANG==='ar'?'أين تشعر بالتنميل أو الخدر؟ اختر الوصف الأقرب.':'Where do you feel the numbness or tingling? Choose the closest description.');
        addQ('📍 ' + prompt);
        showOpts(node.options.map(function(opt){
          const label=LANG==='en'?opt.label[1]:opt.label[0];
          return {label:label,fn:function(){
            add(label,'user');
            if(opt.add){const symptom=LANG==='en'?opt.add[1]:opt.add[0];if(state.symptoms.indexOf(symptom)===-1)state.symptoms.push(symptom);}
            state.location=label;
            if(opt.custom){state.step='clarification';clarCustomNext=opt.next||null;showText(LANG==='ar'?'اكتب مكان التنميل، مثال: حول الفم أو أعلى الفخذ':'Type the location, e.g. around the mouth or upper thigh');return;}
            walkClarNode(opt.next||null);
          }};
        }));
        return;
      }
      if (node.q) {
        const q = LANG === 'en' ? node.q[1] : node.q[0];
        adaptiveQuestionNo += 1;
        addHtml('<div class="adaptive-step">'+esc((LANG==='ar'?'السؤال ':'Question ')+adaptiveQuestionNo+(LANG==='ar'?' · يتكيف حسب إجاباتك':' · adapts to your answers'))+'</div>','bot');
        addQ('🧩 ' + q);
        showOpts([
          {label:TT('clar_yes'), fn:()=>{
            add(TT('clar_yes'),'user');
            state.notes += (state.notes ? ' ' : '') + q + ' -> ' + (LANG==='en' ? 'Yes' : 'نعم');
            walkClarNode(node.yes || null);
          }},
          {label:TT('clar_no'), fn:()=>{
            add(TT('clar_no'),'user');
            state.notes += (state.notes ? ' ' : '') + q + ' -> ' + (LANG==='en' ? 'No' : 'لا');
            walkClarNode(node.no || null);
          }}
        ]);
        return;
      }
      nextClarNode();
    }
    function askAge() {
      if (state.age) { askGender(); return; }
      state.step = 'age';
      updateFlow(state.step);
      addQ(TT('age'));
      showText(TT('age_ph'));
    }
    function askGender() {
      if (state.gender) { askSymptoms(); return; }
      state.step = 'gender';
      updateFlow(state.step);
      addQ(TT('gender'));
      showOpts([
        {label:TT('male'), fn:()=>{ state.gender='m'; add(TT('male'),'user'); if(qualityReturnKey==='gender'){qualityReturnKey=null;showDataQualityGate();}else askSymptoms(); }},
        {label:TT('female'), fn:()=>{ state.gender='f'; add(TT('female'),'user'); if(qualityReturnKey==='gender'){qualityReturnKey=null;showDataQualityGate();}else askSymptoms(); }}
      ]);
    }
    function G(f, m) { return state.gender === 'm' ? m : f; }
    function trackJourney(stage) {
      try { fetch('/api/analytics/journey',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({stage:stage}),keepalive:true}).catch(function(){}); } catch(e) {}
    }
    async function extractSmartSymptoms(text) {
      const raw = String(text || '').trim();
      if (!raw) return;
      clearOpts(); add(LANG==='ar'?'أفهم وصفك وأطابقه مع قاعدة الأعراض…':'Understanding your description and matching it to the symptom knowledge base…','bot');
      try {
        const r = await fetch('/api/symptoms/extract',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:raw,lang:LANG})});
        const d = await r.json();
        const found = (d.found || []).map(function(x){ return LANG==='ar' ? (x.name_ar || x.name_en || x.slug) : (x.name_en || x.name_ar || x.slug); }).filter(Boolean);
        if (!found.length) {
          state.symptoms=Array.from(new Set((state.symptoms||[]).concat([raw])));
          add(LANG==='ar'?'تم اعتماد وصفك كما كتبته، وسنكمل الأسئلة الآن.':'Your description was saved as written. We will continue with the questions now.','bot');
          askDuration(); return;
        }
        addHtml('<div class="smart-found"><b>🧠 '+esc(LANG==='ar'?'وجدنا:':'We found:')+'</b><div style="margin-top:8px">'+found.map(x=>'✓ '+esc(x)).join('<br>')+'</div><p class="muted" style="margin:8px 0 0">'+esc(LANG==='ar'?'هل هذا صحيح؟':'Is this correct?')+'</p></div>','bot');
        showOpts([
          {label:LANG==='ar'?'✅ نعم، متابعة':'✅ Yes, continue',fn:function(){ state.symptoms=Array.from(new Set(found)); add(LANG==='ar'?'تم تأكيد الأعراض':'Symptoms confirmed','user'); askDuration(); }},
          {label:LANG==='ar'?'✏️ تعديل الأعراض':'✏️ Edit symptoms',fn:function(){ state.symptoms=Array.from(new Set(found)); askSymptoms(); }}
        ]);
      } catch(e) {
        state.symptoms=Array.from(new Set((state.symptoms||[]).concat([raw])));
        add(LANG==='ar'?'تم حفظ وصفك كما كتبته، وسنكمل الأسئلة الآن.':'Your description was saved as written. We will continue with the questions now.','bot');
        askDuration();
      }
    }
    function showSmartSymptomInput() {
      if (state.smart_prompt_shown) return;
      state.smart_prompt_shown=true;
      addHtml('<div class="smart-input-card"><b>🗣️ '+esc(LANG==='ar'?'اكتب اللي تحس فيه':'Describe what you are experiencing')+'</b><p class="muted">'+esc(LANG==='ar'?'مثال: من أمس عندي صداع قوي وأحس بغثيان.':'Example: Since yesterday I have a strong headache and feel nauseous.')+'</p><textarea id="smartSymptomText" class="field" rows="3" placeholder="'+esc(LANG==='ar'?'صف الأعراض بطريقتك…':'Describe your symptoms in your own words…')+'"></textarea><button class="ss-btn-primary" style="margin-top:8px" onclick="extractSmartSymptoms(document.getElementById(&quot;smartSymptomText&quot;).value)">'+esc(LANG==='ar'?'فهم الأعراض':'Find symptoms')+'</button></div>','q');
    }
    function askSymptoms() {
      trackJourney('symptoms');
      state.step = 'symptoms';
      updateFlow(state.step);
      if (!state.symptoms.length) showSmartSymptomInput();
      if (state.symptoms.length) {
        addHtml('➕ ' + esc(TT('syms_more')) + '<div class="sel-sum">' + esc(TT('chosen')) + ' ' + esc(state.symptoms.join(LANG === 'en' ? ', ' : '، ')) + '</div>', 'q');
      } else {
        addQ('🩺 ' + TT('syms_q'));
      }
      const items = SYMS.map((s,i)=>({
        label:s,
        sel: state.symptoms.includes(s),
        fn:()=>{
          if (state.symptoms.includes(s)) state.symptoms = state.symptoms.filter(x=>x!==s);
          else state.symptoms.push(s);
          askSymptoms();
        }
      }));
      const customs = state.symptoms.filter(s => !SYMS.includes(s));
      customs.forEach(s => items.push({
        label: s,
        sel: true,
        fn:()=>{ state.symptoms = state.symptoms.filter(x=>x!==s); askSymptoms(); }
      }));
      items.push({label:TT('write_yourself_n'), fn:()=>{
        addQ(TT('custom_n'));
        showText(TT('syms_hint'), true);
      }});
      items.push({label:TT('voice_chip'), cls:'voice-opt', fn:()=>{ startVoice(); }});
      showOpts(items);
      optsEl.classList.add('symptom-picker');
      if (state.symptoms.length) appendStartBtn(true);
      renderRelated();
      if (!state.symptoms.length) appendStartBtn(false);
    }
    function renderRelated() {
      const rel = [];
      (state.symptoms || []).forEach(function(s) {
        (REL[s] || []).forEach(function(r) {
          if (rel.indexOf(r) === -1 && state.symptoms.indexOf(r) === -1) rel.push(r);
        });
      });
      const old = document.getElementById('relBlock');
      if (old) old.remove();
      if (!rel.length) return;
      const blk = document.createElement('div');
      blk.id = 'relBlock';
      let h = '<div class="rel-title">💡 ' + esc(TT('related_title')) + '</div>';
      h += '<div class="rel-chips">';
      rel.slice(0, 8).forEach(function(r) {
        h += '<button class="rel-chip" onclick="addRelated(this, ' + JSON.stringify(r).replace(/"/g, '&quot;') + ')">' + esc(r) + '</button>';
      });
      h += '</div>';
      blk.innerHTML = h;
      optsEl.appendChild(blk);
    }
    function addRelated(btn, label) {
      if (state.symptoms.indexOf(label) === -1) state.symptoms.push(label);
      askSymptoms();
    }
    function askDuration() {
      trackJourney('questionnaire');
      if (state.duration) { askSeverity(); return; }
      state.step = 'duration';
      updateFlow(state.step);
      addQ(TT('duration'));
      showOpts(DURS.map(d=>({label:d, fn:()=>{ state.duration=d; add(d,'user'); if(qualityReturnKey==='duration'){qualityReturnKey=null;showDataQualityGate();}else askSeverity(); }})));
    }
    function askSeverity() {
      if (state.severity) { askNotes(); return; }
      state.step = 'severity';
      updateFlow(state.step);
      addQ(TT('severity'));
      showOpts(SEVS.map(([v,l])=>({label:l, fn:()=>{ state.severity=v; add(l,'user'); if(qualityReturnKey==='severity'){qualityReturnKey=null;showDataQualityGate();}else askNotes(); }})));
    }
    function askConditions() {
      if (state.conditions && state.member && state.member.conditions) { askMeds(); return; }
      state.step = 'conditions';
      updateFlow(state.step);
      addQ(G(TT('conditions_f'), TT('conditions_m')));
      const items = CONDS.map(c=>({label:c, fn:()=>{ state.conditions=c; state.history_answered=true; add(c,'user'); if(qualityReturnKey==='relevant_history'){qualityReturnKey=null;showDataQualityGate();}else askMeds(); }}));
      items.push({label:TT('other_diseases'), fn:()=>{ addQ(G(TT('other_diseases_f'), TT('other_diseases_m'))); showText(TT('cond_ph')); }});
      showOpts(items);
    }
    function askMeds() {
      state.history_answered = true;
      if (state.medications && state.member && state.member.medications) { askAllergies(); return; }
      state.step = 'medications';
      updateFlow(state.step);
      addQ(G(TT('meds_f'), TT('meds_m')));
      showOpts([{label:TT('skip'), fn:()=>{ add(TT('skip'),'user'); state.medications=''; askAllergies(); }}]);
      showText(TT('meds_ph'), true);
    }
    function askAllergies() {
      state.step = 'allergies'; updateFlow(state.step);
      addQ(LANG === 'ar' ? 'هل لديك أي حساسية معروفة؟ اذكرها أو اضغط تخطي.' : 'Do you have any known allergies? Add them or skip.');
      showOpts([{label:TT('skip'), fn:()=>{ add(TT('skip'),'user'); state.allergies=''; startClarify(); }}]);
      showText(LANG === 'ar' ? 'مثال: حساسية البنسلين' : 'Example: penicillin allergy', true);
    }
    function askNotes() {
      state.step = 'notes';
      updateFlow(state.step);
      addQ(G(TT('notes_f'), TT('notes_m')));
      showOpts([{label:TT('skip'), fn:()=>{ add(TT('skip'),'user'); state.notes=''; askConditions(); }}]);
      showText(TT('notes_ph'), true);
    }
    function submitText() {
      const v = send();
      if (!v) return;
      if (state.step === 'age') {
        const normalizedAge = String(v).replace(/[٠-٩]/g,function(d){return String('٠١٢٣٤٥٦٧٨٩'.indexOf(d));}).replace(/[۰-۹]/g,function(d){return String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d));});
        const n = parseInt(normalizedAge,10);
        if (!n || n < 1 || n > 120) { add(TT('age_invalid'), 'bot'); showText(TT('age_ph')); return; }
        state.age = n; if(qualityReturnKey==='age'){qualityReturnKey=null;showDataQualityGate();}else askGender();
      } else if (state.step === 'symptoms') {
        if (checkAmbiguous(v)) return;
        extractSmartSymptoms(v);
      } else if (state.step === 'conditions') {
        state.conditions = v; state.history_answered=true; if(qualityReturnKey==='relevant_history'){qualityReturnKey=null;showDataQualityGate();}else askMeds();
      } else if (state.step === 'medications') {
        state.medications = v; askAllergies();
      } else if (state.step === 'allergies') {
        state.allergies = v; startClarify();
      } else if (state.step === 'notes') {
        state.notes = v; askConditions();
      } else if (state.step === 'clarification') {
        state.location=v;
        state.notes += (state.notes?' ':'') + (LANG==='ar'?'مكان التنميل: ':'Numbness location: ') + v;
        const next=clarCustomNext; clarCustomNext=null; walkClarNode(next);
      } else if (state.step === 'followup') {
        submitFollowup(v);
      }
    }
    var AMBIG_PATTERNS = [
      {re:/(شوي كثير|كثير شوي|شوية كثير|كثير شوية)/i, type:'severity', opts:[
        {label:'🟢 خفيف', val:'خفيف', en:'Mild'},
        {label:'🟡 متوسط', val:'متوسط', en:'Moderate'},
        {label:'🔴 شديد', val:'شديد', en:'Severe'}
      ]},
      {re:/(دوخة لما أقوم|دوخة عند الوقوف|دوخة وأقوم)/i, type:'timing', opts:[
        {label:'🪑 حتى وأنا جالس', val:'مستمرة حتى بالجلوس', en:'Even while sitting'},
        {label:'🚶 فقط عند الوقوف', val:'فقط عند الوقوف', en:'Only when standing'},
        {label:'🔄 الاثنين', val:'الاثنين', en:'Both'},
        {label:'🤷 مو متأكد', val:'غير متأكد', en:'Not sure'}
      ]},
      {re:/(يعورني شوي|قليلاً|شوية|خفيف شوي)/i, type:'severity_mild', opts:[
        {label:'🟢 خفيف', val:'خفيف', en:'Mild'},
        {label:'🟡 متوسط', val:'متوسط', en:'Moderate'},
        {label:'🔴 شديد', val:'شديد', en:'Severe'}
      ]},
      {re:/(ألم صدر|胸口痛|chest pain)/i, type:'chest', opts:[
        {label:'🔴 شديد جداً', val:'شديد جداً', en:'Very severe'},
        {label:'🟡 متوسط', val:'متوسط', en:'Moderate'},
        {label:'🟢 خفيف', val:'خفيف', en:'Mild'}
      ]},
      {re:/(أحياناً|أكيد أحياناً|بعض الأحيان|من حين لآخر)/i, type:'frequency', opts:[
        {label:'📅 يومياً', val:'يومياً', en:'Daily'},
        {label:'📅 عدة مرات بالأسبوع', val:'عدة مرات بالأسبوع', en:'Several times a week'},
        {label:'📅 نادراً', val:'نادراً', en:'Rarely'}
      ]},
      {re:/(أحس بـ|أشعر بـ|عندي شعور)/i, type:'vague_feeling', opts:[
        {label:'😣 ألم', val:'ألم', en:'Pain'},
        {label:'😰 ضيق', val:'ضيق', en:'Tightness'},
        {label:'🤢 غثيان', val:'غثيان', en:'Nausea'},
        {label:'🔥 حرقة', val:'حرقة', en:'Burning'}
      ]},
      {re:/(تعبان|تعبانة|متأثر|متأثرة|مو تمام|مو بخير)/i, type:'general', opts:[
        {label:'🤕 رأس', val:'صداع', en:'Headache'},
        {label:'🤒 حرارة', val:'حرارة', en:'Fever'},
        {label:'🤢 بطن', val:'ألم بطن', en:'Stomach'},
        {label:'💪 عضلات', val:'ألم عضلات', en:'Muscles'},
        {label:'🫁 تنفس', val:'ضيق تنفس', en:'Breathing'}
      ]}
    ];
    var _ambigState = null;
    function checkAmbiguous(text) {
      for (var i = 0; i < AMBIG_PATTERNS.length; i++) {
        var p = AMBIG_PATTERNS[i];
        if (p.re.test(text)) {
          _ambigState = {pattern: p, original: text};
          showClarifyUI(p, text);
          return true;
        }
      }
      return false;
    }
    function showClarifyUI(pattern, originalText) {
      var clarMsg = LANG === 'ar'
        ? '🤍 أبي أتأكد إني فهمتك صح.\\n\\nلما تقول **"' + esc(originalText) + '"**، تقصد:'
        : '🤍 I want to make sure I understand you.\\n\\nWhen you say **"' + esc(originalText) + '"**, you mean:';
      var clarMsgShort = LANG === 'ar'
        ? 'بس خليني أتأكد من نقطة صغيرة 🤍\\nوش تقصد أكثر؟'
        : 'Just making sure I understand 🤍\\nWhat do you mean exactly?';
      add(clarMsg, 'bot');
      var items = pattern.opts.map(function(o) {
        return {
          label: o.label,
          fn: function() {
            add(o.label, 'user');
            clearOpts();
            var resolved = o.val;
            if (pattern.type === 'severity' || pattern.type === 'severity_mild') {
              var symptomPart = originalText.replace(/(شوي كثير|كثير شوي|شوية كثير|كثير شوية|يعورني شوي|قليلاً|شوية|خفيف شوي)/gi, '').trim();
              if (symptomPart) resolved = symptomPart + ' ' + o.val;
              else resolved = o.val;
            } else if (pattern.type === 'timing') {
              resolved = 'دوخة ' + o.val;
            } else if (pattern.type === 'chest') {
              resolved = 'ألم صدر ' + o.val;
            } else if (pattern.type === 'general') {
              resolved = o.val;
            } else if (pattern.type === 'vague_feeling') {
              var bodyPart = originalText.replace(/(أحس بـ|أشعر بـ|عندي شعور)/gi, '').trim();
              resolved = o.val + (bodyPart ? ' ' + bodyPart : '');
            }
            state.symptoms.push(resolved);
            add(TT('added_n'), 'bot');
            _ambigState = null;
            askSymptoms();
          }
        };
      });
      items.push({
        label: TT('write_yourself_n'),
        fn: function() {
          add(TT('write_yourself_n'), 'user');
          clearOpts();
          addQ(TT('custom_n'));
          showText(TT('syms_hint'), true);
        }
      });
      showOpts(items);
    }
    let lastDataQuality = null;
    let qualityReturnKey = null;
    function dataQualityPayload(){
      return {lang:LANG,age:state.age,gender:state.gender,symptoms:(state.symptoms||[]),duration:state.duration,severity:state.severity,conditions:state.conditions||'',medications:state.medications||'',allergies:state.allergies||'',notes:state.notes||'',location:state.location||'',history_answered:!!state.history_answered};
    }
    function dataQualityHtml(q, compact){
      if(!q) return '';
      const pct=Math.max(0,Math.min(100,parseInt(q.score||0)));
      const levelIcon=q.level==='excellent'?'🟢':(q.level==='good'?'🟡':(q.level==='limited'?'🟠':'🔴'));
      let h='<div class="data-quality-card"><div class="dq-head"><div><b>📊 '+esc(LANG==='ar'?'جودة المعلومات':'Data Quality')+'</b><div class="muted" style="margin-top:3px">'+esc(q.meaning||'')+'</div></div><div style="text-align:center"><div class="dq-score">'+pct+'%</div><div class="dq-level">'+levelIcon+' '+esc(q.level_label||'')+'</div></div></div><div class="dq-track"><div class="dq-fill" style="width:'+pct+'%"></div></div>';
      if(!compact){
        h+='<div class="dq-grid">'+(q.fields||[]).map(function(f){const icon=f.status==='provided'?'✅':(f.status==='needs_clarification'?'⚠️':'⚠️');const cls=f.status==='provided'?'':(f.status==='needs_clarification'?' clarify':' missing');return '<div class="dq-item'+cls+'">'+icon+' <b>'+esc(f.label)+'</b><div class="muted">'+esc(f.required?(LANG==='ar'?'مطلوب':'Required'):(LANG==='ar'?'موصى به':'Recommended'))+'</div></div>';}).join('')+'</div>';
      }
      h+='<div class="dq-meta"><span>'+esc(LANG==='ar'?'المطلوب مكتمل: ':'Required complete: ')+esc(String(q.required_completion||0))+'%</span><span>'+esc(LANG==='ar'?'السياق الموصى به: ':'Recommended context: ')+esc(String(q.recommended_completion||0))+'%</span></div></div>';
      return h;
    }
    async function fetchDataQuality(){
      const r=await fetch('/api/analyze/data-quality',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(dataQualityPayload())});
      const d=await r.json();
      if(d.consent_required){location.href=d.consent_url||'/consent?next=/chat';throw new Error('consent_required');}
      if(!r.ok||!d.ok) throw new Error(d.error||'quality_failed');
      lastDataQuality=d.data_quality; return d.data_quality;
    }
    async function showDataQualityGate(){
      clearOpts(); hideText();
      add(LANG==='ar'?'أراجع اكتمال المعلومات قبل التحليل…':'Checking information completeness before analysis…','bot');
      try{
        const q=await fetchDataQuality();
        addHtml(dataQualityHtml(q,false),'bot');
        const missing=(q.missing||[]);
        if(!q.sufficient){
          add(LANG==='ar'?'أكملي المعلومات المطلوبة أولًا. إذا ظهرت علامة خطر، ستظل طبقة الأمان لها الأولوية عند تشغيل التقييم.':'Please complete the required information first. If a red flag is present, the safety layer still takes priority when the assessment runs.','bot');
          showOpts([{label:'➕ '+(LANG==='ar'?'تحسين معلوماتي':'Improve My Information'),fn:function(){improveDataQuality(q);}}]);
          return;
        }
        const opts=[{label:'🩺 '+(LANG==='ar'?'تحليل الأعراض':'Analyze symptoms'),fn:function(){runAnalysis();}}];
        if(missing.length) opts.push({label:'➕ '+(LANG==='ar'?'تحسين معلوماتي':'Improve My Information'),fn:function(){improveDataQuality(q);}});
        showOpts(opts);
      }catch(e){ if(String(e.message)!=='consent_required'){ add(LANG==='ar'?'تعذر حساب جودة المعلومات الآن. يمكنك متابعة الأسئلة ثم المحاولة مرة أخرى.':'Unable to calculate data quality right now. Continue the questions and try again.','bot'); showOpts([{label:'🔄 '+(LANG==='ar'?'إعادة المحاولة':'Try again'),fn:showDataQualityGate}]); } }
    }
    function improveDataQuality(q){
      clearOpts();
      const missing=(q&&q.missing)||[];
      const required=missing.find(x=>x.required)||missing[0];
      if(!required){showDataQualityGate();return;}
      const key=required.key; qualityReturnKey=key;
      add((LANG==='ar'?'سنضيف: ':'Let’s add: ')+required.label,'bot');
      if(key==='age'){state.age=null;askAge();return;}
      if(key==='gender'){state.gender=null;askGender();return;}
      if(key==='main_symptom'||key==='associated_symptoms'){askSymptoms();return;}
      if(key==='duration'){state.duration=null;askDuration();return;}
      if(key==='severity'){state.severity=null;askSeverity();return;}
      if(key==='relevant_history'){state.history_answered=false;state.conditions=null;askConditions();return;}
      askSymptoms();
    }
    async function runAnalysis() {
      trackJourney(state.previous_record_id ? 'reanalyze' : 'analysis');
      hideText();
      clearOpts();
      add(TT('analyzing'), 'bot');
      try {
        const payload = Object.assign({}, state, {lang: LANG});
        payload.member_id = state.member_id || 0;
        lastAnalysisInput = JSON.parse(JSON.stringify(payload));
        if (state.previous_record_id) payload.previous_record_id = state.previous_record_id;
        try { const b = localStorage.getItem('symptosense_blood_id'); if (b) payload.blood_id = parseInt(b) || null; } catch (e) {}
        useSaved = false;
        profileMissing = [];
        // /api/user-info was already loaded when the chat started. Reusing it
        // removes one full request/DB round-trip from the Analyze button path.
        userInfo = userInfo || window.__USER_INFO__ || null;
        if (userInfo && userInfo.ok && userInfo.logged_in && userInfo.has_profile && userInfo.privacy && userInfo.privacy.use_in_analysis) {
          useSaved = true;
          payload.use_saved = true;
          profileMissing = userInfo.missing_fields || [];
        }
        const analysisController = new AbortController();
        const analysisTimer = setTimeout(function(){ analysisController.abort(); }, 15000);
        let r;
        try {
          r = await fetch('/api/analyze', {
            method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify(payload), signal: analysisController.signal
          });
        } finally {
          clearTimeout(analysisTimer);
        }
        const d = await r.json();
        if (d.consent_required) { location.href=d.consent_url||'/consent?next=/chat'; return; }
        if (d.ok) {
          trackJourney('result');
          if (d.emergency) { showEmergency(d); }
          else {
            if (d.assessment_status === 'insufficient' || d.assessment_status === 'low_confidence' || d.low_confidence) {
              showIncompleteResult(d);
            } else {
              renderResult(d);
              if (useSaved && profileMissing.length > 0 && userInfo && userInfo.profile) {
                var missingLabels = profileMissing.map(function(m){ return m.label; }).join(', ');
                var msg = LANG === 'ar'
                  ? '💡 ملاحظة: لم تتم إضافة ' + missingLabels + ' بعد. يمكنك إضافتها من <a href="/profile" style="color:#1976D2;font-weight:700;">ملفي الصحي</a> لجعل النتائج أكثر دقة.'
                  : '💡 Note: ' + missingLabels + ' were not included. Add them in your <a href="/profile" style="color:#1976D2;font-weight:700;">health profile</a> for more accurate results.';
                addHtml(msg, 'bot');
              }
            }
          }
        }
        else add(TT('err') + (d.error||'?'), 'bot');
      } catch(e) { add(TT('conn_err'), 'bot'); }
    }
    function showEmergency(d) {
      lastResult = d;
      const ov = document.getElementById('emOverlay');
      const list = (d.emergency_flags || []).map(function(f){ return '<span class="em-chip">🚨 ' + esc(f) + '</span>'; }).join('');
      ov.innerHTML = '<div class="em-card"><div class="em-icon">🚑</div><h3>' + esc(TT('em_t')) + '</h3><p>' + esc(TT('em_sub')) + '</p><div class="em-flags">' + list + '</div><div class="em-btns"><a class="em-call" href="tel:' + esc(TT('em_num')) + '">' + esc(TT('em_call')) + '</a></div>' +
        '<div class="em-num" onclick="copyEmNum(this)" title="' + esc(TT('em_copy')) + '">☎️ ' + esc(TT('em_num')) + '</div>' +
        '<div class="em-btns"><button class="em-proceed" onclick="closeEmergency()">' + esc(TT('em_proceed')) + '</button></div><div class="em-disc">' + esc(TT('em_disc')) + '</div></div>';
      ov.style.display = 'flex';
    }
    function copyEmNum(el) {
      const num = (TT('em_num') || '').trim();
      const done = function(){ const o = el.textContent; el.textContent = TT('em_copied'); setTimeout(function(){ el.textContent = o; }, 1400); };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(num).then(done, done);
      } else {
        try { const ta = document.createElement('textarea'); ta.value = num; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); document.body.removeChild(ta); } catch(e) {}
        done();
      }
    }
    function showIncompleteResult(d) {
      lastResult=d;
      const title = LANG==='ar'?'🧠 المعلومات المتوفرة غير كافية لإجراء تقييم موثوق':'🧠 Not Enough Information';
      const intro = LANG==='ar'?'لن يعرض SymptoSense احتمالًا طبيًا عندما لا تكون المعلومات أو المطابقة الموثوقة كافية.':'SymptoSense will not show a medical possibility when the information or grounded match is insufficient.';
      const needed=(d.needed_information||[]).filter(Boolean);
      add(title, 'bot');
      let msg='<div class="v2-low-confidence-card"><p>'+esc(intro)+'</p>'+(needed.length?'<b>'+(LANG==='ar'?'معلومات إضافية مطلوبة:':'Additional information needed:')+'</b><ul>'+needed.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul>':'')+'</div>';
      addHtml(msg,'bot');
      showOpts([
        {label:'✏️ '+(LANG==='ar'?'إضافة معلومات':'Add information'), fn:function(){clearOpts();improveDataQuality(d.data_quality||lastDataQuality||{missing:[]});}},
        {label:'📚 '+(LANG==='ar'?'عرض المصادر الموثوقة':'View trusted sources'), fn:function(){clearOpts();renderResult(d);}},
        {label:'🩺 '+(LANG==='ar'?'عرض النتيجة الآمنة':'View safe result'), fn:function(){clearOpts();renderResult(d);}}
      ]);
    }
    function reAnalyzeWithMoreInfo(previousD) {
      add(TT('incomplete_reanalyzing'), 'bot');
      clearOpts();
      var payload = Object.assign({}, state, {lang: LANG});
      payload.member_id = (state.member && state.member.id) ? state.member.id : 0;
      fetch('/api/analyze', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify(payload)
      }).then(function(r){return r.json();}).then(function(d2){
        if(d2.consent_required){location.href=d2.consent_url||'/consent?next=/chat';return;}
        if (d2.ok && !d2.emergency) {
          add(TT('incomplete_done'), 'bot');
          renderResult(d2);
        } else if (d2.emergency) {
          showEmergency(d2);
        } else {
          renderResult(previousD);
        }
      }).catch(function(){ renderResult(previousD); });
    }
    function closeEmergency() {
      document.getElementById('emOverlay').style.display = 'none';
      if (lastResult && lastResult._clar) { lastResult = null; nextClarNode(); return; }
      if (lastResult) renderResult(lastResult);
    }
    function askQuestionFromResult(q) {
      add('💬 ' + q, 'user');
      clearOpts();
      fetch('/api/chat', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({msg:q, lang:LANG, symptoms:state.symptoms, context:lastResult})
      }).then(function(r){return r.json();}).then(function(d){
        if (d.ok) add(d.reply || TT('fallback_chat'), 'bot');
        else add(TT('err'), 'bot');
        showOpts([
          {label:TT('ask_more'), fn:askFollowup},
          {label:TT('new_analysis'), fn:function(){ restart(); }},
          {label:TT('save_profile'), fn:saveMissingToProfile}
        ]);
      }).catch(function(){ add(TT('conn_err'), 'bot'); });
    }
    function addMissingInfo() {
      add(TT('trans_adding'), 'user');
      clearOpts();
      addQ(TT('trans_add_q'));
      showOpts([
        {label:'📅 ' + TT('trans_add_duration'), fn:function(){
          add(TT('trans_add_duration'), 'user'); clearOpts();
          showOpts([
            {label:'📅 ' + TT('incomplete_today'), fn:function(){ state.duration = LANG==='ar'?'اليوم':'Today'; reAnalyzeWithMoreInfo(lastResult); }},
            {label:'📅 ' + TT('incomplete_yesterday'), fn:function(){ state.duration = LANG==='ar'?'أمس':'Yesterday'; reAnalyzeWithMoreInfo(lastResult); }},
            {label:'📅 ' + TT('incomplete_days'), fn:function(){ state.duration = LANG==='ar'?'عدة أيام':'Several days'; reAnalyzeWithMoreInfo(lastResult); }},
            {label:'📅 ' + TT('incomplete_week'), fn:function(){ state.duration = LANG==='ar'?'أكثر من أسبوع':'More than a week'; reAnalyzeWithMoreInfo(lastResult); }}
          ]);
        }},
        {label:'💊 ' + TT('trans_add_meds'), fn:function(){
          add(TT('trans_add_meds'), 'user'); clearOpts();
          addQ(TT('trans_add_meds_q')); showText(TT('trans_add_meds_hint'), true);
        }},
        {label:'📝 ' + TT('trans_add_notes'), fn:function(){
          add(TT('trans_add_notes'), 'user'); clearOpts();
          addQ(TT('trans_add_notes_q')); showText(TT('trans_add_notes_hint'), true);
        }},
        {label:'✅ ' + TT('trans_add_done'), fn:function(){
          add(TT('trans_add_done'), 'user'); clearOpts();
        }}
      ]);
    }
    function saveMissingToProfile() {
      if (!window.__USER_INFO__ || !window.__USER_INFO__.logged_in) {
        add(TT('save_login_required'), 'bot');
        return;
      }
      var updates = {};
      if (state.age && !window.__USER_INFO__.profile?.age) updates.age = state.age;
      if (state.gender && !window.__USER_INFO__.profile?.gender) updates.gender = state.gender;
      if (state.weight && !window.__USER_INFO__.profile?.weight) updates.weight = state.weight;
      if (state.height && !window.__USER_INFO__.profile?.height) updates.height = state.height;
      if (Object.keys(updates).length === 0) {
        add(TT('save_nothing_new'), 'bot');
        return;
      }
      fetch('/api/health-profile', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify(updates)
      }).then(function(r){return r.json();}).then(function(d){
        if (d.ok) add(TT('save_success'), 'bot');
        else add(TT('save_error'), 'bot');
      }).catch(function(){ add(TT('conn_err'), 'bot'); });
    }
    function esc(s) { const div=document.createElement('div'); div.textContent=s||''; return div.innerHTML; }
    function NAME(x, arKey, enKey) { return LANG === 'en' ? (x[enKey] || x[arKey]) : (x[arKey] || x[enKey]); }
    function pillLabel(u) { return u==='high' ? TT('urg_high') : (u==='medium' ? TT('urg_medium') : TT('urg_low')); }
    function explainabilityHtml(d){
      const x=d&&d.explainability; if(!x) return '';
      const factors=(x.factors||[]);
      const infLabel={high:(LANG==='ar'?'تأثير أعلى':'Higher contribution'),medium:(LANG==='ar'?'تأثير متوسط':'Moderate contribution'),low:(LANG==='ar'?'تأثير أقل':'Lower contribution')};
      let body='<details class="xai-card"><summary><span>🔍 '+esc(LANG==='ar'?'لماذا ظهر هذا التقييم؟':'Why this assessment?')+'</span><span>⌄</span></summary><div class="xai-body"><div class="xai-basis">'+esc(x.basis_label||'')+'</div>';
      if(factors.length){
        body+='<div><b>'+esc(LANG==='ar'?'العوامل التي استخدمها التقييم':'Factors used in this assessment')+'</b></div>';
        factors.forEach(function(f){const inf=f.influence||'low';const n=inf==='high'?3:(inf==='medium'?2:1);let meter='<span class="xai-meter" aria-label="'+esc(infLabel[inf]||inf)+'">';for(let i=1;i<=3;i++)meter+='<i class="'+(i<=n?'on':'')+'"></i>';meter+='</span>';body+='<div class="xai-factor"><div class="xai-factor-head"><b>'+esc(f.label||'')+'</b><span><span class="xai-influence '+esc(inf)+'">'+esc(infLabel[inf]||inf)+'</span>'+meter+'</span></div>'+(f.detail?'<div class="xai-detail">'+esc(f.detail)+'</div>':'')+'</div>';});
      } else {
        body+='<div class="muted">'+esc(LANG==='ar'?'لا توجد عوامل إضافية يمكن نسبها بشكل موثوق إلى التقييم الحالي.':'No additional factors can be reliably attributed to the current assessment.')+'</div>';
      }
      body+='<div class="xai-note"><b>'+esc(LANG==='ar'?'ماذا يعني ذلك؟':'What does this mean?')+'</b><br>'+esc(x.meaning||'')+'</div>';
      if(x.auxiliary_model_note) body+='<div class="xai-note">🤖 '+esc(x.auxiliary_model_note)+'</div>';
      body+='</div></details>'; return body;
    }
    function reportLines(value) {
      const raw = String(value || '').replace(/\\r/g, '').trim();
      if (!raw) return [];
      return raw.split(/\\n+/).map(function(x){ return x.replace(/^\\s*[•–—-]\\s*/, '').trim(); }).filter(Boolean);
    }
    function displayGender(value) {
      const v = String(value || '').toLowerCase();
      if (v === 'f' || v === 'female' || v === 'أنثى') return LANG === 'ar' ? 'أنثى' : 'Female';
      if (v === 'm' || v === 'male' || v === 'ذكر') return LANG === 'ar' ? 'ذكر' : 'Male';
      return value || '—';
    }
    function matchLevelLabel(level) {
      const map = LANG === 'ar'
        ? {strong:'توافق مرتفع', moderate:'توافق متوسط', weak:'توافق منخفض'}
        : {strong:'Strong match', moderate:'Moderate match', weak:'Weak match'};
      return map[level] || level || (LANG === 'ar' ? 'غير محدد' : 'Not specified');
    }
    function resultQuestionList(d) {
      const u = (d || {}).urgency || 'low';
      if (u === 'high') return [TT('q_urgent_1'), TT('q_urgent_2'), TT('q通用_1'), TT('q通用_2')];
      if (u === 'medium') return [TT('q_med_1'), TT('q_med_2'), TT('q通用_1'), TT('q通用_2')];
      return [TT('q_low_1'), TT('q_low_2'), TT('q通用_1'), TT('q通用_2')];
    }
    async function askResultQuestion(question) {
      const box = document.getElementById('reportQuestionAnswer');
      if (!box || !question) return;
      box.hidden = false;
      box.textContent = TT('answering');
      try {
        const ctx = Object.assign({}, lastResult || {}, {lang: LANG});
        const r = await fetch('/api/followup', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({question:question, context:ctx})});
        const d = await r.json();
        box.textContent = d.ok ? (d.answer || '') : (TT('err') + (d.error || '?'));
      } catch(e) {
        box.textContent = TT('conn_err');
      }
    }
    function renderResult(d) {
      lastResult = d;
      state.step = 'review';
      updateFlow(state.step);
      hideText();
      clearOpts();

      // Result mode replaces the questionnaire inside the SAME chat container.
      // The page viewport is left untouched while the report replaces the questionnaire.
      const wrap = bodyEl.closest('.chat-wrap');
      if (wrap) wrap.classList.add('report-mode');
      bodyEl.classList.add('result-mode');
      optsEl.hidden = true;
      const safetyNote = document.getElementById('chatSafetyNote');
      if (safetyNote) safetyNote.style.visibility = 'hidden'; // preserve page height / viewport position

      const u = d.urgency || 'low';
      const riskClass = u === 'high' ? 'hi' : (u === 'medium' ? 'med' : 'low');
      const riskEmoji = u === 'high' ? '🔴' : (u === 'medium' ? '🟡' : '🟢');
      const riskValue = d.urgency_text || pillLabel(u);
      const input = lastAnalysisInput || state || {};
      const q = d.data_quality || {};
      const qScoreRaw = Number(q.score);
      const hasQScore = Number.isFinite(qScoreRaw);
      const qScore = hasQScore ? Math.max(0, Math.min(100, Math.round(qScoreRaw))) : null;
      const qLabel = (qScore === 100 || Number(q.required_completion) === 100)
        ? (LANG === 'ar' ? 'مكتملة' : 'Complete')
        : (q.level_label || '');
      const recs = (d.recommendations || []).filter(function(r){ return r && (r.tip || r.title); });
      const summaryRec = recs.length ? (recs[0].title || recs[0].tip) : (d.triage_label || d.risk_label || riskValue);
      const matches = Array.isArray(d.knowledge_matches) ? d.knowledge_matches : [];
      const sources = Array.isArray(d.medical_sources) ? d.medical_sources : [];
      const dangerLines = reportLines(d.danger_signs);
      const homeLines = reportLines(d.home_care);
      const questions = resultQuestionList(d);

      let h = '<div class="ss-report" id="symptomResultReport">';

      // 1) Summary
      h += '<section class="ss-report-card ss-report-summary">'
        + '<div class="ss-report-heading"><h2>📋 '+esc(LANG==='ar'?'نتيجة التحليل':'Analysis result')+'</h2></div>'
        + '<div class="ss-risk-row '+riskClass+'"><div><div class="ss-risk-label">'+esc(LANG==='ar'?'مستوى الخطورة':'Risk level')+'</div><div class="ss-risk-value">'+riskEmoji+' '+esc(riskValue)+'</div></div></div>';
      if (hasQScore) {
        h += '<div class="ss-quality"><div class="ss-quality-top"><strong>'+esc(LANG==='ar'?'جودة المعلومات المدخلة':'Information completeness')+'</strong><span class="ss-quality-score">'+qScore+'%'+(qLabel?' — '+esc(qLabel):'')+'</span></div><div class="ss-quality-track" aria-hidden="true"><div class="ss-quality-fill" style="width:'+qScore+'%"></div></div></div>';
      }
      if (summaryRec) h += '<div class="ss-summary-recommendation"><b>'+esc(LANG==='ar'?'التوصية الحالية':'Current recommendation')+'</b>'+esc(summaryRec)+'</div>';
      h += '</section>';

      // 2) Entered information (request payload only, not a recalculation)
      const inputRows = [
        [LANG==='ar'?'الأعراض':'Symptoms', Array.isArray(input.symptoms) ? input.symptoms.join(LANG==='ar'?'، ':', ') : input.symptoms],
        [LANG==='ar'?'المدة':'Duration', input.duration],
        [LANG==='ar'?'شدة الأعراض':'Symptom severity', input.severity ? String(input.severity)+'/5' : ''],
        [LANG==='ar'?'العمر':'Age', input.age ? String(input.age) : ''],
        [LANG==='ar'?'الجنس':'Sex', displayGender(input.gender)]
      ].filter(function(x){ return x[1] !== null && x[1] !== undefined && String(x[1]).trim() !== ''; });
      h += '<section class="ss-report-card"><div class="ss-report-heading"><h3>👤 '+esc(LANG==='ar'?'المعلومات المدخلة':'Entered information')+'</h3></div><div class="ss-input-grid">';
      inputRows.forEach(function(row){ h += '<div class="ss-input-item"><span class="ss-input-label">'+esc(row[0])+'</span><span class="ss-input-value">'+esc(String(row[1]))+'</span></div>'; });
      h += '</div></section>';

      // 3) Possible conditions — preserve backend order; do not recalculate or re-score.
      h += '<section class="ss-report-card"><div class="ss-report-heading"><h3>🩺 '+esc(LANG==='ar'?'الاحتمالات المحتملة':'Possible conditions')+'</h3></div><div class="ss-condition-list">';
      if (u === 'high') {
        h += '<div class="ss-empty-note" style="border-color:#F2CACA;background:#FFF7F7;color:#7A3535">🚨 '+esc(LANG==='ar'?'هذه احتمالات ممكنة مبنية على مطابقة الأعراض، وليست تفسيرًا مؤكدًا لعلامة الخطر ولا تشخيصًا. لا تؤخر طلب الرعاية العاجلة بسبب هذه الاحتمالات.':'These are possible matches based on the reported symptoms, not a confirmed explanation of the red flag or a diagnosis. Do not delay urgent care because of these possibilities.')+'</div>';
      }
      if (matches.length) {
        matches.forEach(function(m){
          const name = NAME(m,'name_ar','name_en') || '';
          const matched = (m.matched_symptoms || []).map(function(x){ return NAME(x,'name_ar','name_en'); }).filter(Boolean);
          h += '<article class="ss-condition"><div class="ss-condition-head"><div class="ss-condition-name">'+esc(name)+'</div><span class="ss-match">'+esc(matchLevelLabel(m.match_level))+'</span></div>';
          if (matched.length) h += '<div class="ss-condition-why"><b>'+esc(LANG==='ar'?'لماذا ظهر هذا الاحتمال؟':'Why did this appear?')+'</b><br>'+esc(LANG==='ar'?'الأعراض المتوافقة: ':'Matching symptoms: ')+esc(matched.join(LANG==='ar'?'، ':', '))+'</div>';
          else if (m.description) h += '<div class="ss-condition-why"><b>'+esc(LANG==='ar'?'لماذا ظهر هذا الاحتمال؟':'Why did this appear?')+'</b><br>'+esc(m.description)+'</div>';
          h += '</article>';
        });
      } else if (d.possible_conditions) {
        reportLines(d.possible_conditions).forEach(function(line){ h += '<article class="ss-condition"><div class="ss-condition-why" style="margin-top:0">'+esc(line)+'</div></article>'; });
      } else {
        h += '<div class="ss-empty-note">'+esc(LANG==='ar'?'لا توجد احتمالات موثوقة إضافية في النتيجة الحالية.':'No additional trusted possibilities are available in the current result.')+'</div>';
      }
      h += '</div></section>';

      // 4) What to do now — existing API recommendations only.
      h += '<section class="ss-report-card"><div class="ss-report-heading"><h3>🧭 '+esc(LANG==='ar'?'ماذا أفعل الآن؟':'What should I do now?')+'</h3></div><div class="ss-step-list">';
      let stepNo = 1;
      recs.forEach(function(r){
        const title = r.title || (LANG==='ar'?'الآن':'Now');
        const tip = r.tip || '';
        h += '<div class="ss-step"><span class="ss-step-no">'+stepNo+'</span><div class="ss-step-body"><b>'+esc(title)+'</b>'+(tip?'<p>'+esc(tip)+'</p>':'')+(r.url?'<a class="ss-step-source" href="'+esc(r.url)+'" target="_blank" rel="noopener noreferrer">'+esc(LANG==='ar'?'عرض المصدر':'View source')+'</a>':'')+'</div></div>';
        stepNo += 1;
      });
      if (d.medication_guidance) {
        h += '<div class="ss-step"><span class="ss-step-no">'+stepNo+'</span><div class="ss-step-body"><b>💊 '+esc(LANG==='ar'?'إرشاد الدواء':'Medication guidance')+'</b><p>'+esc(d.medication_guidance)+'</p></div></div>'; stepNo += 1;
      }
      if (d.when_to_seek_care) {
        h += '<div class="ss-step"><span class="ss-step-no">'+stepNo+'</span><div class="ss-step-body"><b>'+esc(LANG==='ar'?'متى أراجع الطبيب؟':'When should I see a doctor?')+'</b><p>'+esc(d.when_to_seek_care)+'</p></div></div>'; stepNo += 1;
      }
      if (stepNo === 1) h += '<div class="ss-empty-note">'+esc(LANG==='ar'?'لا توجد توصيات إضافية في النتيجة الحالية.':'No additional recommendations are available in the current result.')+'</div>';
      h += '</div></section>';

      // 5) Danger signs
      h += '<section class="ss-report-card"><div class="ss-report-heading"><h3>🚨 '+esc(LANG==='ar'?'علامات تستدعي الانتباه':'Warning signs')+'</h3></div>';
      if (dangerLines.length) { h += '<div class="ss-flag-list">'; dangerLines.forEach(function(line){ h += '<div class="ss-flag"><span>•</span><span>'+esc(line)+'</span></div>'; }); h += '</div>'; }
      else h += '<div class="ss-empty-note">'+esc(LANG==='ar'?'لم يتم تحديد علامات خطر من المعلومات المدخلة.':'No warning signs were identified from the information entered.')+'</div>';
      h += '</section>';

      // 6) Home care — only if the API already provides it.
      if (homeLines.length) {
        h += '<section class="ss-report-card"><div class="ss-report-heading"><h3>🏠 '+esc(LANG==='ar'?'الرعاية المنزلية':'Home care')+'</h3></div><div class="ss-care-list">';
        homeLines.forEach(function(line){ h += '<div class="ss-care"><span>•</span><span>'+esc(line)+'</span></div>'; });
        h += '</div></section>';
      }

      // 7) Existing follow-up assistant prompts
      h += '<section class="ss-report-card"><div class="ss-report-heading"><h3>💡 '+esc(TT('questions_title'))+'</h3></div><div class="ss-question-chips">';
      questions.filter(Boolean).forEach(function(question){ h += '<button type="button" class="ss-question-chip" data-question="'+esc(question)+'">'+esc(question)+'</button>'; });
      h += '</div><div class="ss-question-answer" id="reportQuestionAnswer" aria-live="polite" hidden></div></section>';

      // 8) Why this assessment — collapsible, API data only.
      h += '<details class="ss-report-details"><summary>🧠 '+esc(LANG==='ar'?'لماذا ظهر هذا التقييم؟':'Why did this assessment appear?')+'</summary><div class="ss-details-body">';
      if (d.why_result) h += '<div class="ss-details-block">'+esc(d.why_result)+'</div>';
      const xai = d.explainability || {};
      if (xai.basis_label) h += '<div class="ss-details-block"><b>'+esc(xai.basis_label)+'</b></div>';
      (xai.factors || []).forEach(function(f){ h += '<div class="ss-factor"><strong>'+esc(f.label || '')+'</strong>'+(f.detail?'<small>'+esc(f.detail)+'</small>':'')+'</div>'; });
      if (xai.meaning) h += '<div class="ss-details-block"><b>'+esc(LANG==='ar'?'ماذا يعني ذلك؟':'What does this mean?')+'</b><br>'+esc(xai.meaning)+'</div>';
      if (d.risk_reasons && d.risk_reasons.length) {
        h += '<div class="ss-details-block"><b>'+esc(LANG==='ar'?'عوامل أثرت على مستوى الخطورة':'Factors affecting the risk level')+'</b>';
        d.risk_reasons.forEach(function(r){ const txt=r.message||r.description||r.name||''; if(txt) h += '<div class="ss-factor">'+esc(txt)+'</div>'; });
        h += '</div>';
      }
      h += '</div></details>';

      // 9) Medical sources — collapsible, URLs hidden behind explicit buttons.
      h += '<details class="ss-report-details"><summary><span>📚 '+esc(LANG==='ar'?'المصادر الطبية':'Medical sources')+' — '+sources.length+' '+esc(LANG==='ar'?'مصادر':'sources')+'</span></summary><div class="ss-details-body"><div class="ss-source-list">';
      if (sources.length) {
        sources.forEach(function(src){
          const url = src.reference_url || src.official_url || '';
          const title = LANG==='ar' ? (src.reference_title_ar || src.reference_title_en || '') : (src.reference_title_en || src.reference_title_ar || '');
          h += '<article class="ss-source-card"><div class="ss-source-name">'+esc(src.source_name || src.organization || 'Source')+'</div>';
          const meta=[]; if(src.organization && src.organization !== src.source_name) meta.push(src.organization); if(src.source_type) meta.push(String(src.source_type).replace(/_/g,' ')); if(src.last_verified || src.source_last_verified) meta.push((LANG==='ar'?'آخر تحقق: ':'Last verified: ')+(src.last_verified||src.source_last_verified));
          if(meta.length) h += '<div class="ss-source-meta">'+meta.map(function(x){return '<span>'+esc(x)+'</span>';}).join('')+'</div>';
          if(title) h += '<div class="ss-source-title">'+esc(title)+'</div>';
          if(url) h += '<a class="ss-source-link" href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">'+esc(LANG==='ar'?'عرض المصدر':'View source')+'</a>';
          h += '</article>';
        });
      } else h += '<div class="ss-empty-note">'+esc(LANG==='ar'?'لا توجد مصادر إضافية مرفقة بهذه النتيجة.':'No additional sources are attached to this result.')+'</div>';
      h += '</div></div></details>';

      // 10) Existing actions only.
      h += '<section class="ss-report-card"><div class="ss-report-heading"><h3>'+esc(LANG==='ar'?'الإجراءات':'Actions')+'</h3></div><div class="ss-report-actions">';
      h += '<button type="button" class="ss-report-action primary" onclick="restart()">🔄 '+esc(LANG==='ar'?'إعادة التحليل':'New analysis')+'</button>';
      if (d.record_id) {
        h += '<button type="button" class="ss-report-action" onclick="downloadAnalysisReport(this,'+Number(d.record_id)+')">📄 '+esc(LANG==='ar'?'تحميل التقرير':'Download report')+'</button>';
        h += '<button type="button" class="ss-report-action" onclick="openDoctorHandoff('+Number(d.record_id)+')">🩺 '+esc(LANG==='ar'?'ملخص الطبيب':'Doctor summary')+'</button>';
      }
      if ('speechSynthesis' in window) h += '<button type="button" class="ss-report-action" onclick="speakResult()">🔊 '+esc(LANG==='ar'?'الاستماع للتحليل':'Listen to analysis')+'</button>';
      h += '</div><div id="reportActionStatus" class="ss-feedback-msg" aria-live="polite" hidden></div></section>';

      // 11) Feedback — reuse current endpoint/rating semantics.
      h += '<section class="ss-report-card ss-feedback"><p>'+esc(LANG==='ar'?'هل كانت نتيجة التحليل مفيدة؟':'Was this analysis result useful?')+'</p><div class="ss-feedback-btns"><button type="button" class="ss-feedback-btn" onclick="fb(1)">👍 '+esc(LANG==='ar'?'نعم':'Yes')+'</button><button type="button" class="ss-feedback-btn" onclick="fb(4)">👎 '+esc(LANG==='ar'?'لا':'No')+'</button></div><div id="fbMsg" class="ss-feedback-msg" aria-live="polite"></div></section>';

      // 12) One disclaimer only.
      h += '<div class="ss-report-disclaimer">⚠️ '+esc(LANG==='ar'?'هذه النتيجة توعوية ولا تُعد تشخيصًا طبيًا نهائيًا ولا تغني عن استشارة الطبيب عند الحاجة.':'This result is educational, is not a final medical diagnosis, and does not replace professional medical advice when needed.')+'</div>';
      h += '</div>';

      const host = document.createElement('div');
      host.className = 'bubble result';
      host.innerHTML = h;
      bodyEl.replaceChildren(host);
      // Reset only the INTERNAL report pane so the summary is visible; the page viewport is untouched.
      bodyEl.scrollTop = 0;

      host.querySelectorAll('.ss-question-chip').forEach(function(btn){ btn.addEventListener('click', function(){ askResultQuestion(btn.dataset.question || ''); }); });
      host.querySelectorAll('details.ss-report-details').forEach(function(detail){
        detail.addEventListener('toggle', function(){
          const keep = bodyEl.scrollTop;
          requestAnimationFrame(function(){ bodyEl.scrollTop = keep; });
        });
      });
    }
    async function downloadAnalysisReport(btn, recordId){
      const original = btn ? btn.innerHTML : '';
      const status = document.getElementById('reportActionStatus');
      if (status) { status.hidden = true; status.textContent = ''; }
      if (btn) { btn.disabled = true; btn.textContent = LANG==='ar' ? '⏳ جاري تجهيز التقرير…' : '⏳ Preparing report…'; }
      try {
        const response = await fetch('/api/analyze/export/'+encodeURIComponent(String(recordId)), {credentials:'same-origin'});
        const type = (response.headers.get('content-type') || '').toLowerCase();
        if (!response.ok || !type.includes('application/pdf')) {
          let message = LANG==='ar' ? 'تعذر تحميل التقرير حاليًا. حاول مرة أخرى.' : 'Unable to download the report right now. Please try again.';
          try { const data = await response.json(); if (data && data.error) message = data.error; } catch(e) {}
          throw new Error(message);
        }
        const blob = await response.blob();
        if (!blob.size) throw new Error(LANG==='ar' ? 'ملف التقرير فارغ.' : 'The report file is empty.');
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'symptosense-report-'+recordId+'.pdf';
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        setTimeout(function(){ URL.revokeObjectURL(url); link.remove(); }, 2000);
      } catch (err) {
        const msg = (err && err.message) || (LANG==='ar' ? 'تعذر تحميل التقرير حاليًا.' : 'Unable to download the report.');
        if (status) { status.textContent = msg; status.hidden = false; } else { alert(msg); }
      } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = original; }
      }
    }
    async function openDoctorHandoff(recordId){
      let candidates=[];try{const d=await fetch('/api/handoff/candidates').then(r=>r.json());candidates=(d.analyses||[]).filter(x=>x.id!==recordId);}catch(e){}
      const overlay=document.createElement('div');overlay.id='handoffOverlay';overlay.style.cssText='position:fixed;inset:0;background:rgba(15,35,55,.45);z-index:1005;display:flex;align-items:center;justify-content:center;padding:16px;overflow:auto';
      const fields=[['symptoms',LANG==='ar'?'الأعراض':'Symptoms'],['duration',LANG==='ar'?'المدة':'Duration'],['severity',LANG==='ar'?'الشدة':'Severity'],['location',LANG==='ar'?'المكان':'Location'],['notes',LANG==='ar'?'الملاحظات':'Notes'],['medications',LANG==='ar'?'معلومات الأدوية':'Medication information']];
      const choices=fields.map(x=>'<label style="display:flex;gap:8px;align-items:center;padding:8px 0"><input type="checkbox" data-share="'+x[0]+'"> '+esc(x[1])+'</label>').join('');
      const prev=candidates.length?'<div style="margin-top:10px"><label style="display:flex;gap:8px;align-items:center"><input type="checkbox" data-share="previous_assessments" id="includePrevious"> '+esc(LANG==='ar'?'تقييمات سابقة مختارة':'Selected previous assessments')+'</label><div id="prevChoices" style="display:none;margin:8px 0;padding:10px;background:var(--v2-bg);border-radius:12px">'+candidates.slice(0,6).map(x=>'<label style="display:block;padding:5px"><input type="checkbox" data-prev="'+x.id+'"> '+esc((x.symptoms||[]).join(LANG==='ar'?'، ':', '))+' · '+esc(String(x.timestamp||'').slice(0,10))+'</label>').join('')+'</div></div>':'';
      overlay.innerHTML='<div style="width:min(620px,100%);background:#fff;border-radius:20px;padding:22px;border:1px solid var(--v2-line);box-shadow:0 24px 70px rgba(20,50,80,.22)"><div style="display:flex;justify-content:space-between;gap:10px"><div><h2>🗣️ '+esc(LANG==='ar'?'تجهيز ملخص لزيارة الطبيب':'Prepare for a Doctor Visit')+'</h2><p class="muted">'+esc(LANG==='ar'?'اختر فقط المعلومات التي تريد مشاركتها. لا يتم اختيار أي حقل تلقائيًا.':'Choose only what you want to share. No field is selected by default.')+'</p></div><button type="button" class="opt" id="closeHandoff">✕</button></div><div style="margin-top:12px"><b>'+esc(LANG==='ar'?'اختر ما تريد مشاركته':'Choose what to share')+'</b>'+choices+prev+'</div><label style="display:block;margin-top:12px"><b>'+esc(LANG==='ar'?'مدة صلاحية الرابط':'Link expiration')+'</b><select id="handoffExpiry" style="width:100%;margin-top:6px"><option value="15">15 '+esc(LANG==='ar'?'دقيقة':'minutes')+'</option><option value="60">1 '+esc(LANG==='ar'?'ساعة':'hour')+'</option><option value="1440">24 '+esc(LANG==='ar'?'ساعة':'hours')+'</option></select></label><div id="handoffStatus" class="muted" style="margin-top:10px"></div><button type="button" class="btn pri" id="generateHandoff" style="width:100%;margin-top:12px">📱 '+esc(LANG==='ar'?'إنشاء QR مؤقت':'Generate Temporary QR')+'</button><div id="handoffResult"></div></div>';
      document.body.appendChild(overlay);document.getElementById('closeHandoff').onclick=()=>overlay.remove();const ip=document.getElementById('includePrevious');if(ip)ip.onchange=()=>document.getElementById('prevChoices').style.display=ip.checked?'block':'none';
      document.getElementById('generateHandoff').onclick=async function(){const selected={};overlay.querySelectorAll('[data-share]').forEach(x=>selected[x.dataset.share]=x.checked);if(!Object.values(selected).some(Boolean)){document.getElementById('handoffStatus').textContent=LANG==='ar'?'اختر معلومة واحدة على الأقل.':'Select at least one item.';return;}const previous_ids=Array.from(overlay.querySelectorAll('[data-prev]:checked')).map(x=>parseInt(x.dataset.prev));document.getElementById('handoffStatus').textContent=LANG==='ar'?'جاري إنشاء الرابط المؤقت…':'Generating temporary link…';try{const r=await fetch('/api/handoff/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({record_id:recordId,selected:selected,previous_ids:previous_ids,expires_minutes:parseInt(document.getElementById('handoffExpiry').value)})});const d=await r.json();if(!r.ok||!d.ok)throw new Error(d.error||'failed');window.__handoffToken=d.token;const qr=d.qr_data_uri?'<img alt="QR" src="'+d.qr_data_uri+'" style="width:220px;max-width:100%;margin:12px auto;display:block">':'';document.getElementById('handoffResult').innerHTML='<div class="res-assess" style="margin-top:12px;text-align:center">'+qr+'<a class="v2-source-link" href="'+esc(d.share_url)+'" target="_blank" rel="noopener">'+esc(LANG==='ar'?'فتح رابط المشاركة':'Open share link')+'</a><div class="muted" id="handoffCountdown" style="margin:8px 0"></div><button type="button" class="btn ghost" id="copyHandoff">🔗 '+esc(LANG==='ar'?'نسخ الرابط':'Copy Link')+'</button> <button type="button" class="btn ghost danger-lite" id="revokeHandoff">'+esc(LANG==='ar'?'إلغاء الرابط':'Revoke Link')+'</button></div>';document.getElementById('copyHandoff').onclick=()=>navigator.clipboard&&navigator.clipboard.writeText(d.share_url);document.getElementById('revokeHandoff').onclick=()=>revokeDoctorLink(d.token);startHandoffCountdown(d.expires_at);document.getElementById('handoffStatus').textContent='';}catch(e){const m=String((e&&e.message)||'');document.getElementById('handoffStatus').textContent=m.includes('selected_information_empty')?(LANG==='ar'?'المعلومة التي اخترتها غير موجودة في هذا التحليل. اختر معلومة أخرى للمشاركة.':'The selected item has no saved value in this analysis. Choose another item to share.'):(LANG==='ar'?'تعذر إنشاء الرابط.':'Unable to create the link.');}};
    }
    function startHandoffCountdown(expiresAt){const el=document.getElementById('handoffCountdown');if(!el)return;const tick=()=>{const ms=new Date(expiresAt).getTime()-Date.now();if(ms<=0){el.textContent=LANG==='ar'?'انتهت صلاحية الرابط.':'Link expired.';return;}const m=Math.ceil(ms/60000);el.textContent=(LANG==='ar'?'ينتهي الرابط خلال ':'Link expires in ')+m+(LANG==='ar'?' دقيقة':' min');setTimeout(tick,30000)};tick();}
    async function revokeDoctorLink(token){if(!confirm(LANG==='ar'?'إلغاء الرابط الآن؟':'Revoke this link now?'))return;const r=await fetch('/api/handoff/revoke',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:token})});const d=await r.json();if(d.ok){const box=document.getElementById('handoffResult');if(box)box.innerHTML='<div class="v2-safe-note">'+esc(LANG==='ar'?'تم إلغاء الرابط ولم يعد متاحًا.':'The link was revoked and is no longer available.')+'</div>';}}

    let lastResult = null;
    function beginReanalysis(id) {
      trackJourney('reanalyze');
      compareBase={record_id:id,symptoms:(state.symptoms||[]).slice(),duration:state.duration,severity:state.severity,urgency:(lastResult||{}).urgency||'low'};
      state.previous_record_id=id; state.duration=null; state.severity=null; state.smart_prompt_shown=true;
      add(LANG==='ar'?'سنستخدم بيانات التحليل السابق. عدّل الأعراض إن تغيرت ثم اضغط بدء التحليل.':'We will reuse the previous analysis. Edit symptoms if they changed, then start the assessment.','bot');
      askSymptoms();
    }
    function askFollowup() {
      state.step = 'followup';
      add(G(TT('followup_f'), TT('followup_m')), 'bot');
      showText(TT('followup_ph'));
      renderSuggestedQs();
    }
    function setSim(v) {
      const s = document.getElementById('resSimple'), d = document.getElementById('resDetail');
      const sb = document.getElementById('simBtn'), db = document.getElementById('detBtn');
      if (s) s.style.display = v ? 'block' : 'none';
      if (d) d.style.display = v ? 'none' : 'block';
      if (sb) sb.style.display = v ? 'none' : 'inline-block';
      if (db) db.style.display = v ? 'inline-block' : 'none';
    }
    function renderSuggestedQs() {
      const old = document.getElementById('dqBlock');
      if (old) old.remove();
      const qs = [TT('dq_danger'), TT('dq_sev'), TT('dq_home'), TT('dq_doc')];
      if ((lastResult || {}).triage_level === 'emergency' || (lastResult || {}).triage_level === 'today') {
        qs[0] = TT('dq_danger');
      }
      const blk = document.createElement('div');
      blk.id = 'dqBlock';
      let h = '<div class="rel-title">💡 ' + esc(TT('dq_title')) + '</div>';
      h += '<div class="rel-chips">';
      qs.forEach(function(q, i) {
        h += '<button class="rel-chip" onclick="dqAsk(' + i + ')">' + esc(q) + '</button>';
      });
      h += '</div>';
      blk.innerHTML = h;
      optsEl.appendChild(blk);
    }
    function dqAsk(i) {
      const qs = [TT('dq_danger'), TT('dq_sev'), TT('dq_home'), TT('dq_doc')];
      add(qs[i], 'user');
      submitFollowup(qs[i]);
    }
    async function submitFollowup(q) {
      add(TT('answering'), 'bot');
      try {
        const ctx = Object.assign({}, lastResult || {}, {lang: LANG});
        const r = await fetch('/api/followup', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({question:q, context:ctx})});
        const d = await r.json();
        if (d.ok) add(d.answer, 'bot'); else add(TT('err') + (d.error||'?'), 'bot');
      } catch(e) { add(TT('conn_err'), 'bot'); }
      showOpts([
        {label:TT('another_q'), fn:askFollowup},
        {label:TT('new'), fn:restart}
      ]);
    }
    function speakResult() {
      if (!lastResult) return;
      if (!('speechSynthesis' in window)) { add(TT('no_speech'), 'bot'); return; }
      const clean = s => String(s || '').replace(/[^\u0600-\u06FF\\w\\s.,!?()\\-%/،؟]/g, ' ').replace(/\\s{2,}/g, ' ').trim();
      const d = lastResult;
      const u = d.urgency;
      const pill = u==='high' ? TT('urg_high') : (u==='medium' ? TT('urg_medium') : TT('urg_low'));
      let parts = [];
      parts.push(TT('urg_label') + ' ' + clean(pill) + '.');
      if (d.personal_note) parts.push(TT('assessment_label') + ' ' + clean(d.personal_note));
      if (d.possible_conditions) parts.push(TT('sp_possible') + clean(d.possible_conditions));
      if (d.recommendations && d.recommendations.length) {
        parts.push(TT('sp_recs'));
        d.recommendations.forEach(r => {
          const t = ((r.title ? r.title + ': ' : '') + (r.tip || ''));
          if (t) parts.push('- ' + clean(t));
        });
      }
      if (d.med_warnings && d.med_warnings.length) {
        parts.push(TT('sp_medwarn'));
        d.med_warnings.forEach(m => { const w = NAME(m, 'warning_ar', 'warning_en'); if (w) parts.push('- ' + clean(w)); });
      }
      if (d.danger_signs) parts.push(TT('sp_danger') + clean(d.danger_signs));
      if (d.when_to_seek_care) parts.push(TT('sp_when') + clean(d.when_to_seek_care));
      if (d.home_care) parts.push(TT('sp_home') + clean(d.home_care));
      if (d.medication_guidance) parts.push(TT('sp_medguid') + clean(d.medication_guidance));
      if (d.questions_for_doctor) parts.push(TT('sp_qdoc') + clean(d.questions_for_doctor));
      speakText(parts.join(' '));
    }
    function fb(rating) {
      fetch('/api/feedback', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({rating: rating})});
      document.getElementById('fbMsg').textContent = TT('fb_thanks');
    }
    async function findHospitals() {
      clearOpts();
      add(TT('locating'), 'bot');
      navigator.geolocation.getCurrentPosition(async pos => {
        const r = await fetch('/api/hospitals', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({lat:pos.coords.latitude, lng:pos.coords.longitude})
        });
        const d = await r.json();
        if (!d.hospitals || !d.hospitals.length) { add(TT('no_hosp'), 'bot'); return; }
        let h = '<div class="sec-title">' + TT('hosp_title') + '</div>';
        d.hospitals.forEach(x => h += '<div class="rec-item"><b>' + esc(x.name) + '</b> — ' + x.distance_km + TT('km') + '<br><a href="' + esc(x.maps_url) + '" target="_blank">' + TT('map') + '</a></div>');
        addHtml(h, 'result');
      }, () => { add(G(TT('loc_err_f'), TT('loc_err_m')), 'bot'); });
    }
    function restart() {
      Object.assign(state, {age:null,gender:null,symptoms:[],duration:null,severity:null,location:null,conditions:null,medications:null,allergies:null,notes:null,history_answered:false,previous_record_id:null,smart_prompt_shown:false}); compareBase=null; qualityReturnKey=null; lastDataQuality=null; lastAnalysisInput=null;
      bodyEl.innerHTML = '';
      bodyEl.classList.remove('result-mode');
      bodyEl.scrollTop = 0;
      optsEl.hidden = false;
      const wrap = bodyEl.closest('.chat-wrap'); if (wrap) wrap.classList.remove('report-mode');
      const safetyNote = document.getElementById('chatSafetyNote'); if (safetyNote) safetyNote.style.visibility = 'visible';
      startChat();
    }
    startChat();
    </script>
    """
    return _page(_t("title_chat"), body
        .replace("__T__", json.dumps(CHAT["ar"] if ar else CHAT["en"], ensure_ascii=False))
        .replace("__LANG__", "ar" if ar else "en")
        .replace("__SYMS__", json.dumps(syms, ensure_ascii=False))
        .replace("__DURS__", json.dumps(durs, ensure_ascii=False))
        .replace("__SEVS__", json.dumps(sevs, ensure_ascii=False))
        .replace("__CONDS__", json.dumps(conds, ensure_ascii=False))
        .replace("__REL__", json.dumps(_related_map(ar), ensure_ascii=False))
        .replace("__ME__", CHAT["ar" if ar else "en"]["me"])
        .replace("__VOICE_MODE_TITLE__", CHAT["ar" if ar else "en"]["voice_mode_title"])
        .replace("__VOICE_MODE_OFF__", CHAT["ar" if ar else "en"]["voice_mode_off"])
        .replace("__SPEAK_ON__", CHAT["ar" if ar else "en"]["speak_on"])
        .replace("__SPEAK_TITLE__", CHAT["ar" if ar else "en"]["speak_title"])
        .replace("__INPUT_PH__", CHAT["ar" if ar else "en"]["input_ph"])
        .replace("__MIC_TITLE__", CHAT["ar" if ar else "en"]["mic_title"])
        .replace("__SEND__", CHAT["ar" if ar else "en"]["send"])
        .replace("__MUTED__", CHAT["ar" if ar else "en"]["muted"])
        .replace("__FLOW_STEP__", "الخطوة 1 من 7" if ar else "Step 1 of 7")
        .replace("__FLOW_DEMO__", "العمر والجنس" if ar else "Age and sex")
        .replace("__VOICE_SP__", CHAT["ar" if ar else "en"]["voice_speaking"])
        .replace("__VOICE_PRIVACY__", "لا يحفظ SymptoSense التسجيل الصوتي؛ يتم إرسال النص الناتج فقط للمعالجة." if ar else "SymptoSense does not store the audio recording; only the resulting transcript is sent for parsing.")
        .replace("__VOICE_STOP__", CHAT["ar" if ar else "en"]["voice_stop"])
        .replace("__VOICE_CANCEL__", CHAT["ar" if ar else "en"]["voice_cancel"]))



# ---------------------------------------------------------------- content pages i18n
CT = {
    "ar": {
        "blood_h": "🩸 تحليل فحص الدم",
        "blood_cbc": "Complete Blood Count (CBC)",
        "blood_sub": "سنساعدك على فهم نتائج فحص الدم (CBC) بطريقة مبسطة وواضحة. ارفع صورة الفحص أو ملف PDF وسنفسّر لك القيم.",
        "blood_gender": "الجنس",
        "blood_gender_ph": "اختر الجنس",
        "blood_female": "أنثى", "blood_male": "ذكر", "blood_child": "طفل",
        "blood_age": "العمر",
        "blood_age_ph": "أدخل العمر بالسنوات",
        "blood_hint": "تُستخدم هذه المعلومات للمساعدة في تفسير القيم وفقاً للنطاقات المرجعية المناسبة.",
        "blood_hint2": "💡 تأكد من وضوح صورة الفحص وإضاءتها لقراءة أدق للقيم.",
        "blood_alert": "⚠️ تنبيه: التفسير أدناه توعوي فقط وليس بديلاً عن مراجعة الطبيب أو المختبر. راجع طبيبك لأي قراءة خارج النطاق الطبيعي.",
        "blood_drop": "اسحب ملف الفحص هنا",
        "blood_drop_or": "أو",
        "blood_drop_btn": "📁 اختيار ملف",
        "blood_drop_note": "PDF • JPG • PNG • حتى 10 ميجابايت",
        "blood_file_del": "تغيير الملف 🔄",
        "blood_btn": "🔍 تحليل نتائج الفحص",
        "blood_first": "اختر ملف الفحص أولاً.",
        "blood_link": "🔗 ربط هذه النتيجة بتحليل الأعراض",
        "blood_link_hint": "سيراعي التحليل نتائج فحصك الدموي تلقائياً.",
        "blood_linked": "تم ربط نتيجة الفحص بالتحليل",
        "blood_goto_chat": "ابدأ فحص الأعراض الآن",
        "blood_reading": "جاري قراءة الفحص وتحليله...",
        "blood_err": "تعذر التحليل",
        "bl_summ": "📋 ملخص الفحص",
        "bl_sum_normal": "طبيعي", "bl_sum_follow": "يحتاج متابعة", "bl_sum_out": "خارج النطاق",
        "bl_mean_title": "💡 ماذا تعني هذه النتائج؟",
        "bl_do": "🩺 ماذا أفعل؟",
        "bl_col_ind": "المؤشر", "bl_col_val": "النتيجة", "bl_col_status": "الحالة",
        "bl_what": "ما هو؟", "bl_mean": "ماذا تعني النتيجة؟", "bl_ref": "النطاق المرجعي", "bl_when": "متى يحتاج مراجعة الطبيب؟",
        "bl_explain": "اشرحها ببساطة",
        "bl_notes": "ملاحظات",
        "bl_status_n": "طبيعي", "bl_status_l": "منخفض", "bl_status_h": "مرتفع",
        "bl_lvl_normal": "ضمن الطبيعي ✅", "bl_lvl_see_doctor": "استشارة طبيب", "bl_lvl_urgent": "تقييم عاجل", "bl_lvl_emergency": "طوارئ 🚨",
        "meds_h": "💊 معلومات الدواء",
        "meds_sub": "اكتب اسم الدواء لتعرف استخداماته، تحذيراته، والتداخلات المحتملة.",
        "meds_label": "اسم الدواء",
        "meds_ph": "مثال: بنادول، فولتارين، أسبرين",
        "meds_btn": "🔎 بحث",
        "meds_searching": "جاري البحث...",
        "meds_nf": "لم نجد هذا الدواء في قاعدة بياناتنا. تأكد من الإملاء أو استشر الطبيب أو الصيدلي.",
        "meds_sec_uses": "الاستخدامات",
        "meds_sec_warn": "⚠️ التحذيرات",
        "meds_sec_int": "التداخلات المحتملة",
        "meds_sec_consult": "❗ متى تستشير",
        "meds_consult_txt": "إذا كنت حاملاً أو مرضعة، أو تتناول أدوية أخرى، أو تعاني من أمراض مزمنة — استشر الطبيب أو الصيدلي قبل الاستخدام.",
        "meds_disc": "هذه المعلومات للتوعية فقط ولا تغني عن استشارة الطبيب أو الصيدلي.",
        "meds_warn2": "المعلومات الدوائية المقدمة لا تغني عن النشرة الدوائية أو استشارة الطبيب أو الصيدلي.",
        "rem_h": "⏰ تذكير الأدوية",
        "rem_sub": "احفظ مواعيد أدويتك وذكّرك بها المتصفح كل يوم (الإشعارات تعمل ما دامت الصفحة مفتوحة).",
        "rem_list_h": "🔔 تذكيراتك",
        "rem_name": "اسم الدواء", "rem_times": "المواعيد (ساعة:دقيقة)",
        "rem_name_ph": "مثال: بنادول", "rem_times_ph": "مثال: 08:00، 14:00، 20:00",
        "rem_save": "حفظ التذكير 💊",
        "meds_warn": "⚠️ لا توقف أو تغيّر جرعة أي دواء موصوف بدون استشارة الطبيب أو الصيدلي.",
        "meds_write": "اكتب الأدوية أولاً.",
        "meds_checking": "جاري الفحص...",
        "meds_none": "✅ لم نجد تحذيرات مطابقة للأدوية المكتوبة.",
        "meds_col": "الدواء", "warn_col": "التحذير",
        "no_rem": "لا توجد تذكيرات بعد.",
        "del": "حذف 🗑️",
        "name_first": "اكتب اسم الدواء أولاً.",
        "times_ph_err": "اكتب الأوقات مثل: 08:00، 14:00، 20:00",
        "no_notif": "متصفحك لا يدعم الإشعارات.",
        "enable_notif": "فعّل الإشعارات من إعدادات المتصفح حتى يعمل التذكير.",
        "saved": "✅ تم حفظ التذكير. سينبهك المتصفح في الأوقات المحددة (طالما الصفحة مفتوحة).",
        "rem_notif_t": "💊 تذكير دوائي", "rem_notif_b": "حان وقت أخذ: ",
        "fam_h": "👨‍👩‍👧 مركز صحة العائلة",
        "fam_sub": "سجلّات صحية منفصلة لكل من تعتني بهم — لتحليلات وفحوصات وأدوية لكل فرد بدون خلط.",
        "me_short": "👤 أنا",
        "fam_add": "➕ إضافة فرد من العائلة",
        "fam_edit": "✏️ تعديل",
        "fam_del": "حذف 🗑️",
        "fam_empty": "لا يوجد أفراد بعد. أضف فرداً من العائلة لبدء متابعة صحته.",
        "fam_who": "من تريد إضافته؟",
        "fam_rel_me": "أنا", "fam_rel_mother": "الأم", "fam_rel_father": "الأب",
        "fam_rel_daughter": "الابنة", "fam_rel_son": "الابن", "fam_rel_grandparent": "الجد/الجدة", "fam_rel_other": "شخص آخر",
        "fam_name": "الاسم", "fam_name_ph": "مثال: أمي",
        "fam_age": "العمر أو تاريخ الميلاد", "fam_age_ph": "مثال: 48",
        "fam_gender": "الجنس", "fam_g_f": "أنثى", "fam_g_m": "ذكر",
        "fam_conditions": "الأمراض السابقة", "fam_meds": "الأدوية",
        "fam_allergies": "الحساسية", "fam_notes": "ملاحظات",
        "fam_save": "حفظ",
        "fam_last_analysis": "🩺 آخر تحليل أعراض",
        "fam_last_cbc": "🩸 آخر فحص CBC",
        "fam_meds_reg": "💊 الأدوية المسجلة",
        "fam_adherence": "الالتزام",
        "fam_followup": "📈 المتابعة",
        "fam_timeline": "📅 السجل الصحي",
        "fam_no_analysis": "لا يوجد تحليل بعد",
        "fam_no_cbc": "لا يوجد فحص بعد",
        "fam_no_meds": "لا توجد أدوية مسجلة",
        "fam_add_analysis": "تحليل أعراض ←",
        "fam_add_cbc": "رفع فحص CBC ←",
        "fam_no_adherence": "—",
        "fam_years": "سنة",
        "fam_back": "→ عودة للعائلة",
        "fam_plan_title": "💊 تذكيرات الأدوية",
        "fam_plan_sub": "أدوية «%s» ومواعيدها — بجانب كل موعد: أخذته / تخطي / تذكير لاحقاً.",
        "fam_take": "✅ أخذته",
        "fam_skip": "⏭️ تخطي",
        "fam_later": "⏰ لاحقاً",
        "fam_add_plan": "➕ إضافة دواء",
        "fam_plan_name": "اسم الدواء",
        "fam_plan_name_ph": "مثال: بنادول",
        "fam_plan_dose": "الجرعة (اختياري)",
        "fam_plan_times": "مواعيد الاستخدام (ساعة:دقيقة)",
        "fam_plan_times_ph": "مثال: 08:00، 20:00",
        "fam_plan_days": "المدة بالأيام (اختياري)",
        "fam_plan_start": "تاريخ البداية",
        "fam_plan_save": "حفظ التذكير 💊",
        "fam_week_adh": "💊 التزامك هذا الأسبوع: %s%",
        "fam_due_today": "حان موعد الدواء",
        "fam_person": "الشخص",
        "fam_relations": "العلاقة",
        "fam_actions": "إجراءات",
        "fam_open": "فتح الملف",
        "fam_today_logged": "مُسجّل",
        "fam_analysis": "تحليل أعراض",
        "fam_cbc": "فحص CBC",
        "fam_med": "دواء",
        "fam_days": "يوم",
        "fam_no_events": "لا توجد أحداث في آخر 30 يوماً.",
        "fam_delete_confirm": "حذف هذا الفرد؟ سيتم فصل سجلاته.",
        "fam_saved": "✅ تم الحفظ.",
        "fam_err": "خطأ: ",
        "fam_done": "تم",
        "fam_each_person": "كل فرد له ملفه الخاص: العمر، الجنس، الأمراض، الأدوية، التحاليل والتحليلات السابقة.",
        "fam_hub_intro": "مكان واحد لإدارة السجلات الصحية للأشخاص الذين تعتني بهم.",
        "asst_title": "اسأل SymptoSense",
        "asst_sub": "المساعد الذكي للموقع",
        "asst_ph": "اكتب سؤالك...",
        "asst_close": "إغلاق",
        "asst_greet": "أهلًا! 👋\nأنا مساعد SymptoSense. كيف أقدر أساعدك اليوم؟",
        "asst_opt_symp": "أعراض صحية",
        "asst_opt_symp_d": "احكِ لي عن الأعراض التي تشعر بها.",
        "asst_opt_drug": "سؤال عن دواء",
        "asst_opt_drug_d": "استفسر عن دواء أو جرعته أو تحذيراته.",
        "asst_opt_blood": "تحليل دم",
        "asst_opt_blood_d": "افهم نتائج فحص الدم بشرح مبسط.",
        "asst_opt_mh": "صحتي النفسية",
        "asst_opt_mh_d": "مساحة هادئة للحديث عن مشاعرك والقلق والتوتر.",
        "asst_opt_calc": "حاسبة صحية",
        "asst_opt_calc_d": "احسب مؤشرًا صحيًا مثل BMI أو السعرات.",
        "asst_opt_q": "سؤال صحي",
        "asst_opt_q_d": "اسألني عن موضوع صحي تريد فهمه.",
        "asst_mh_title": "🤍 صحتي النفسية",
        "asst_mh_sub": "مساحة هادئة لك",
        "asst_mh_greet": "أنا معك 🤍\nوش أكثر شيء حاب تتكلم عنه؟",
        "asst_mh_o_anx": "القلق",
        "asst_mh_o_anx_d": "قلق أو أفكار تدور في رأسك.",
        "asst_mh_o_sad": "الحزن",
        "asst_mh_o_sad_d": "مزاج منخفض أو حزن.",
        "asst_mh_o_str": "التوتر",
        "asst_mh_o_str_d": "توتر أو ضغط نفسي.",
        "asst_mh_o_slp": "النوم",
        "asst_mh_o_slp_d": "صعوبة في النوم أو الأرق.",
        "asst_mh_o_tho": "أفكار كثيرة",
        "asst_mh_o_tho_d": "أفكار متزاحمة ومشوشة.",
        "asst_mh_o_oth": "شيء آخر",
        "asst_mh_o_oth_d": "موضوع آخر تحب تشاركه.",
        "asst_mh_send_anx": "أشعر بقلق كبير",
        "asst_mh_send_sad": "أشعر بالحزن",
        "asst_mh_send_str": "أنا متوتر ومضغوط",
        "asst_mh_send_slp": "ما أقدر أنام",
        "asst_mh_send_tho": "أفكاري كثيرة ومتزاحمة",
        "asst_mh_send_oth": "أبي أتكلم عن شيء آخر",
        "asst_mh_calm_chip": "🌿 ساعدني أهدأ",
        "asst_mh_opt1": "أبي أتكلم",
        "asst_mh_opt1_d": "إذا تحتاج أحد يسمعك.",
        "asst_mh_opt2": "ساعدني أهدأ",
        "asst_mh_opt2_d": "إذا كنت متوترًا أو تشعر بالهلع الآن.",
        "asst_mh_opt3": "أبي أفهم شعوري",
        "asst_mh_opt3_d": "إذا كنت تريد فهم ما تشعر به بشكل أفضل.",
        "asst_mh_ph": "احكِ لي براحتك...",
        "asst_mh_anim": "إيقاف الحركة",
        "asst_mh_anim_on": "تشغيل الحركة",
        "asst_mh_talk_msg": "🤍 أنا معك هنا. ابدأ بأي شيء يشغل بالك — حتى لو كان الكلام غير مرتب، لا بأس. أنا أسمعك.",
        "asst_mh_calm_msg": "🌿 خذ نفسًا عميقًا معي… شاهد الدائرة وتنفس معها. خذ وقتك، أنا هنا.",
        "asst_mh_feel_msg": "🧠 خذ وقتك… متى ظهر هذا الشعور؟ وش كان قبله؟ اكتب ما يخطر ببالك مهما كان بسيطًا.",
        "asst_br_in": "تنفّس",
        "asst_br_hold": "احبس",
        "asst_br_out": "أخرج",
        "asst_mh_opt_night": "🌙 Night Calm",
        "asst_mh_opt_night_d": "وضع هادئ للراحة قبل النوم.",
        "night_calm_title": "🌙 Night Calm",
        "night_calm_greet": "خلينا نخلي كل شيء أهدأ شوي.\nما تحتاج تحل كل شيء الليلة. 🤍",
        "night_calm_q": "وش تحتاج الآن؟",
        "night_calm_opt_calm": "🌿 أحتاج أهدأ",
        "night_calm_opt_listen": "🫂 أبي أحد يسمعني",
        "night_calm_opt_think": "💭 أفكاري كثيرة",
        "night_calm_opt_sleep": "😴 أبي أستعد للنوم",
        "night_calm_calm_reply": "حاضر 🤍\nما نحتاج نسوي شيء كبير الآن.\nخلينا نركز على اللحظة اللي أنت فيها.",
        "night_calm_calm_step": "🌿 خذ نفسًا مريحًا.\nلا تحاول تأخذ نفسًا عميقًا بالقوة.\nفقط خذه بهدوء.\n\nأنا معك. 🤍",
        "night_calm_next": "جاهز/ة للخطوة التالية",
        "night_calm_listen_reply": "أنا هنا 🤍\nاحكِ لي اللي بخاطرك، حتى لو ما عرفت/ي ترتبه.",
        "night_calm_think_reply": "أفهمك 🤍\nأحيانًا لما تتجمع الأشياء كلها في الرأس، حتى الشيء الصغير يصير ثقيل.\n\nوش أكثر فكرة قاعدة تضغط عليك الآن؟",
        "night_calm_sleep_reply": "خلينا نهدّي اليوم شوي.\n\nهل تبغى:\n🫂 تتكلم عن يومك\n🌿 جلسة تهدئة قصيرة\n💭 أفرغ أفكاري\n🤍 شيء بسيط يساعدني أهدأ",
        "night_calm_safety": "🤍 أنا سامعك، وكلامك مهم.\nلكن لأنك قلت شيئًا يجعلني قلقًا على سلامتك، خلينا نركز عليك الآن قبل أي شيء آخر.\n\nهل أنت في خطر مباشر الآن؟",
        "night_calm_safety_call": "📞 اتصال بخط 937 | 🚑 الطوارئ 997",
        "memory_title": "🧠 ذاكرتي مع SymptoSense",
        "memory_subtitle": "المعلومات التي تسمح للمساعد باستخدامها لتخصيص تجربتك.",
        "memory_control": "أنت المتحكم — تستطيع رؤية أي معلومة محفوظة، تعديلها أو حذفها في أي وقت.",
        "memory_add": "➕ إضافة معلومة",
        "memory_manage": "🧹 إدارة ذاكرتي",
        "memory_source_profile": "من ملفك الشخصي",
        "memory_source_chat": "ذكرتها في هذه المحادثة",
        "memory_source_memory": "حفظتها في ذاكرتي",
        "memory_source_unknown": "غير معروفة",
        "memory_empty": "لا توجد معلومات محفوظة بعد.",
        "memory_empty_sub": "عندما تشارك معلومات مع المساعد، يمكن حفظها هنا.",
        "manage_title": "إدارة معلوماتي",
        "manage_subtitle": "تحكم بالمعلومات المحفوظة في حسابك. يمكنك تعديلها أو حذف أي معلومة في أي وقت.",
        "manage_edit": "تعديل",
        "manage_delete": "حذف",
        "manage_not_set": "غير محدد",
        "manage_saved": "✅ تم الحفظ بنجاح",
        "manage_error": "❌ حدث خطأ",
        "manage_deleted": "✅ تم الحذف بنجاح",
        "manage_delete_all": "🧹 حذف جميع معلوماتي",
        "manage_delete_confirm": "هل أنت متأكد؟ سيؤدي ذلك إلى حذف جميع المعلومات الصحية المحفوظة.",
        "manage_delete_type": "اكتب 'حذف' للتأكيد",
        "transparency_title": "وش نعرف عن حالتك؟",
        "transparency_sub": "هذه المعلومات التي استخدمناها في التحليل:",
        "trans_known": "نعرف",
        "trans_known_none": "لا توجد معلومات مؤكدة",
        "trans_unclear": "غير واضح",
        "trans_unclear_confidence": "ثقة تحليل منخفضة",
        "trans_unclear_duration": "لم تحدد المدة",
        "trans_unclear_notes": "ملاحظات قصيرة جداً",
        "trans_unclear_none": "لا توجد معلومات غير واضحة",
        "trans_notasked": "لم نسأل عنه",
        "trans_notasked_sleep": "نمط النوم",
        "trans_notasked_appetite": "تغيرات الشهية",
        "trans_notasked_stress": "التوتر الأخير",
        "trans_notasked_family": "التاريخ العائلي",
        "trans_notasked_note": "💡 مو كل معلومة ناقصة تعني أن هناك مشكلة. بعض المعلومات قد لا تكون ضرورية لتحليلك الحالي.",
        "trans_add_info": "➕ إضافة معلومة",
        "trans_add_q": "وش المعلومة اللي تبي تضيفها؟",
        "trans_add_duration": "المدة",
        "trans_add_meds": "الأدوية",
        "trans_add_meds_q": "وش الأدوية اللي تتناولها حالياً؟",
        "trans_add_meds_hint": "اكتب الأدوية بالاسم أو الاستخدام",
        "trans_add_notes": "ملاحظات إضافية",
        "trans_add_notes_q": "وش الملاحظة اللي تبي تضيفها؟",
        "trans_add_notes_hint": "اكتب أي معلومة إضافية",
        "trans_add_done": "✅ شكراً، المعلومات كافية",
        "trans_adding": "أبي أضيف معلومة إضافية",
        "asst_calc_greet": "🤍 أنا هنا إذا احتجتني\nعندك سؤال عن إحدى الحاسبات؟ اسألني.",
        "asst_calc_bmi_greet": "⚖️ ظهرت لك نتيجة BMI؟\nأقدر أشرح لك معناها بطريقة بسيطة.",
        "asst_calc_sug_greet": "🩸 تبغى تفهم قراءة السكر؟\nأقدر أوضح لك معنى النتيجة حسب نوع القياس.",
        "asst_calc_fluids_greet": "💧 عندك سؤال عن احتياج السوائل؟\nأقدر أساعدك.",
        "asst_calc_cal_greet": "🔥 عندك سؤال عن السعرات؟\nأقدر أوضح لك الفكرة.",
        "asst_calc_dose_greet": "💊 عندك سؤال عن مواعيد الدواء؟\nأقدر أساعدك.",
        "asst_q_calc1": "وش أفضل حاسبة أبدأ فيها؟",
        "asst_q_calc2": "كيف أستخدم حاسبة السكر؟",
        "asst_q_calc3": "هل النتائج دقيقة؟",
        "asst_q_sug1": "وش معنى قراءة السكر؟",
        "asst_q_sug2": "وش الفرق بين صائم وبعد الأكل؟",
        "asst_q_sug3": "هل قراءتي طبيعية؟",
        "asst_q_bmi1": "اشرح لي معنى نتيجتي BMI",
        "asst_q_bmi2": "هل BMI دقيق دائمًا؟",
        "asst_q_bmi3": "وش الوزن المثالي لطولي؟",
        "asst_q_fluids1": "كم أحتاج أشرب ماء باليوم؟",
        "asst_q_cal1": "وش السعرات المناسبة لي؟",
        "asst_q_dose1": "كيف أنظم مواعيد دوائي؟",
        "asst_q1": "أشعر بألم في رأسي منذ يومين",
        "asst_q2": "كيف أرفع فحص الدم؟",
        "asst_q3": "ما هي خدمة صحة العائلة؟",
        "asst_q4": "كيف أتتبع أدويتي؟",
        "asst_emerg_txt": "⚠️ تظهر عليك علامات تستدعي الطوارئ. اتصل بالإسعاف فوراً:",
        "asst_emerg_btn": "صفحة الطوارئ ←",
        "asst_offline": "عذراً، لا أستطيع الرد الآن. جرّب صفحة فحص الأعراض أو راجع الطبيب عند الحاجة.",
        "asst_disc": "هذه المعلومات للتوعية ولا تُعد تشخيصًا طبيًا أو نفسيًا. في الحالات الطارئة، اطلب المساعدة من مختص أو خدمات الطوارئ.",
        "asst_svc_symp": "فحص الأعراض", "asst_svc_blood": "تحليل فحص الدم",
        "asst_svc_family": "مركز صحة العائلة", "asst_svc_meds": "صفحة الأدوية",
        "asst_svc_hosp": "أقرب مستشفى",
        "fa_h": "🚑 الإسعافات الأولية",
        "fa_sub": "اختر الحالة لعرض الإرشادات الإسعافية خطوة بخطوة.",
        "fa_warn": "⚠️ في الحالات الحرجة (توقف تنفس، نزيف حاد، فقدان وعي) اتصل بالإسعاف <b>997</b> فوراً.",
        "fa_video": "▶ شاهد فيديو توضيحي",
        "tips_h": "🌿 مركز النصائح الصحية",
        "tips_sub": "نصائح يومية عملية لصحة أفضل لك ولعائلتك.",
        "tips_btn": "نصيحة أخرى 🔄",
        "tips_warn": "⚠️ النصائح أعلاه توعوية عامة ولا تُغني عن استشارة الطبيب، خاصةً إذا كانت لديك حالة صحية خاصة.",
        "relax_h": "🧘 تمرين الاسترخاء والتنفس",
        "br_in": "استنشق 🌬️", "br_hold": "احبس 🧘", "br_out": "زفر 😮‍💨",
        "em_h": "🚨 الطوارئ",
        "em_sub": "أرقام الطوارئ في السعودية — احتفظ بها وأجرها فوراً عند الحاجة.",
        "em_alert": "⚠️ إذا كنت تواجه حالة طبية طارئة، اتصل بخدمات الطوارئ فوراً ولا تعتمد على التحليل الإلكتروني.",
        "em_red": "الهلال الأحمر (إسعاف)", "em_unified": "الطوارئ الموحد",
        "em_937": "وزارة الصحة",
        "em_red_desc": "الإسعاف والطوارئ الطبية",
        "em_unified_desc": "الرقم الموحد للطوارئ في جميع المناطق",
        "em_937_desc": "استشارات صحية مجانية على مدار الساعة",
        "em_call": "اتصل الآن",
        "em_police": "الشرطة", "em_civil": "الدفاع المدني",
        "em_police_desc": "طوارئ الشرطة", "em_civil_desc": "طوارئ الدفاع المدني",
        "em_signs_h": "⚠️ علامات تستدعي طلب المساعدة فوراً",
        "em_s1": "😮‍💨 صعوبة تنفس شديدة",
        "em_s2": "💔 ألم صدر شديد أو مفاجئ",
        "em_s3": "😵 فقدان الوعي",
        "em_s4": "🩸 نزيف لا يتوقف",
        "em_s5": "🗣️ أعراض سكتة دماغية مفاجئة",
        "em_call_btn": "📞 اتصل بالطوارئ",
        "em_geo_title": "📍 أقرب مستشفى إليك",
        "em_geo_sub": "ابحث عن أقرب مستشفى أو مركز طوارئ بناءً على موقعك الحالي.",
        "em_geo_24h": "متوفر على مدار الساعة 24/7",
        "em_safety": "🛡️ السلامة أولًا — لا تنتظر أبداً عندما تكون الأعراض خطرة؛ كل دقيقة قد تكون مهمة.",
        "em_warn": "⚠️ في حالة الأعراض الخطرة (ألم صدر حاد، صعوبة تنفس، نزيف حاد، فقدان وعي) اتصل بالإسعاف <b>997</b> فوراً ولا تنتظر.",
        "em_geo": "مستشفى قريب منك 📍",
        "em_geo_btn": "🔎 البحث عن أقرب مستشفى",
        "em_geo_searching": "جاري تحديد موقعك والبحث...",
        "em_geo_err": "تعذّر تحديد موقعك — تأكد من السماح بالموقع الجغرافي.",
        "em_geo_empty": "لم يتم العثور على مستشفيات قريبة.",
        "em_nearby": "أقرب المستشفيات:",
        "ci_h": "📋 متابعة الحالة اليومية",
        "ci_sub": "سجّل حالتك كل يوم (من 1 سيء جداً إلى 5 ممتاز) وتابع تحسنك بالمخطط.",
        "ci_saved": "تم تسجيل حالتك ✅ (5 = ممتاز، 1 = سيء جداً)",
        "ci_err": "خطأ: ",
        "ci_chart_err": "تعذر تحميل المخطط.",
        "ci_empty": "لا توجد تسجيلات بعد — سجّل أول تقييم من الأزرار فوق.",
        "ci_alt": "مخطط التحسن",
        "nav_search": "البحث الصحي",
        "title_search": "SymptoSense — البحث الصحي الذكي",
        "sea_h": "🔎 البحث الصحي الذكي",
        "sea_sub": "ابحث عن أي عرض أو تحليل أو مصطلح طبي أو دواء بلغة بسيطة، وافهم متى يستدعي الانتباه ومتى تراجع الطبيب.",
        "sea_ph": "اكتب سؤالك... مثال: ليش أحس أن الدنيا تلف؟ أو وش معنى WBC؟",
        "sea_btn": "ابحث 🔍",
        "sea_hint": "جرّب البحث بلغة طبيعية: «ليش أحس أن الدنيا تلف؟» أو «وش معنى WBC؟»",
        "sea_warn": "⚠️ المعلومات المعروضة توعوية عامة وليست تشخيصاً طبياً — في حالات الطوارئ اتصل بالإسعاف 997 فوراً.",
        "sea_what": "ما هي؟",
        "sea_causes": "💡 الأسباب الشائعة",
        "sea_worry": "متى تستدعي الانتباه؟",
        "sea_doctor": "متى أراجع الطبيب؟",
        "sea_explain": "اشرحها لي ببساطة",
        "sea_ask_assist": "اسأل المساعد عن هذا",
        "sea_disc": "🩺 معلومات للتوعية الصحية العامة فقط ولا تُعد تشخيصاً.",
        "sea_noresult": "لا توجد نتيجة مطابقة. جرّب كلمات أخرى أو اسأل المساعد بالزر العائم.",
        "sea_err": "حدث خطأ في البحث، حاول مرة أخرى.",
        "sea_cat_symp": "عرض", "sea_cat_test": "فحص", "sea_cat_term": "مصطلح", "sea_cat_med": "دواء",
        "sea_explain_title": "اشرحها لي ببساطة",
        "sea_noexplain": "لم نجد شرحاً مبسطاً لهذا المصطلح حالياً.",
        "lv_very_simple": "بسيط جداً", "lv_basic": "مبسّط", "lv_advanced": "متقدم",
        "asst_explain_ask": "اسأل المساعد عن هذا",
        "asst_ctx": "كنت أبحث عن \"%s\" — هل يمكنك إعطائي مزيداً من التفاصيل عنها؟",
        "asst_fb_good": "مفيدة", "asst_fb_partial": "جزئياً", "asst_fb_bad": "غير مفيدة",
        "asst_fb_thanks": "شكراً لتقييمك! 🎉", "asst_fb_sent": "شكراً لملاحظاتك! ✅",
        "asst_fb_title": "ما سبب عدم فائدتها؟",
        "asst_fr1": "الشرح غير واضح", "asst_fr2": "الإجابة طويلة جداً", "asst_fr3": "لم تجب عن سؤالي",
        "asst_fr4": "أريد معلومات أكثر", "asst_fr5": "الإجابة غير مناسبة", "asst_fr6": "سبب آخر",
        "calc_h": "🧮 الحاسبات الصحية",
        "calc_sub": "أدوات بسيطة تساعدك تفهم بعض المؤشرات الصحية. احسب، افهم النتيجة، وإذا احتجت اسأل SymptoSense.",
        "calc_now": "احسب الآن",
        "calc_back": "↩ العودة للحاسبات",
        "calc_follow": "💡 وش معنى النتيجة؟",
        "calc_ask": "🤖 اسأل SymptoSense",
        "calc_ask_bmi_t": "💡 وش معنى النتيجة؟",
        "calc_ask_bmi_b": "🤖 خل SymptoSense يشرحها لك",
        "calc_ask_sug_t": "💡 وش معنى هذا الرقم؟",
        "calc_ask_sug_b": "🤖 اسأل SymptoSense",
        "calc_alert_t": "🚨 تنبيه",
        "calc_alert_msg": "النتيجة التي أدخلتها قد تستدعي تقييمًا طبيًا، خصوصًا إذا كانت لديك أعراض شديدة.",
        "calc_alert_high": "🚨 القراءة مرتفعة جدًا — يُنصح بالحصول على تقييم طبي عاجل، وإذا كانت مصحوبة بأعراض شديدة فاتصل بالإسعاف 997 فورًا.",
        "calc_alert_low": "🚨 القراءة منخفضة جدًا — إذا كانت مصحوبة بأعراض (رجفة، دوخة، عرق، تشوش) فتناول مصدر سكر سريع واطلب تقييمًا طبيًا، وإذا تدهورت الحالة فاتصل بالإسعاف 997.",
        "calc_em_btn": "🚨 إرشادات الطوارئ",
        "calc_disc_t": "مهم تعرف",
        "calc_disc": "النتائج تقديرية وللتثقيف فقط، ولا تستبدل استشارة الطبيب. لا تغيّر دواءك أو جرعتك بناءً على نتيجة الحاسبة.",
        "calc_err": "حدث خطأ في الحساب — تحقق من القيم المدخلة.",
        "calc_bmi_name": "مؤشر كتلة الجسم",
        "calc_bmi_desc": "احسب مؤشر كتلة الجسم بناءً على طولك ووزنك.",
        "calc_bmi_w": "الوزن (كجم)",
        "calc_bmi_w_ph": "مثال: 70",
        "calc_bmi_h": "الطول (سم)",
        "calc_bmi_h_ph": "مثال: 175",
        "calc_bmi_btn": "احسب BMI",
        "calc_bmi_val": "⚖️ مؤشر كتلة الجسم:",
        "calc_bmi_unit": "كجم/م²",
        "calc_bmi_cat_under": "نقص في الوزن",
        "calc_bmi_cat_normal": "ضمن النطاق المعتاد",
        "calc_bmi_cat_over": "زيادة في الوزن",
        "calc_bmi_cat_obese": "سمنة",
        "calc_bmi_cat_under_severe": "نقص حاد في الوزن",
        "calc_bmi_cat_obese_severe": "سمنة شديدة",
        "calc_bmi_note_under": "مؤشرك أقل من النطاق المعتاد. قد يكون السبب بنية الجسم أو عوامل أخرى — والمؤشر وحده لا يكفي للتقييم.",
        "calc_bmi_note_normal": "مؤشرك ضمن النطاق المعتاد. BMI مؤشر عام وليس تشخيصًا طبيًا، وقد لا يكون مناسبًا لتقييم جميع الأشخاص (كرياضيي القوة والأطفال وكبار السن والحوامل).",
        "calc_bmi_note_over": "مؤشرك أعلى من النطاق المعتاد. BMI مؤشر عام وليس تشخيصًا طبيًا، وقد لا يكون مناسبًا لتقييم جميع الأشخاص.",
        "calc_bmi_note_obese": "مؤشرك ضمن نطاق السمنة. يُنصح بمراجعة الطبيب لتقييم الحالة، فالمؤشر وحده لا يحدد الخطورة.",
        "calc_bmi_note_under_severe": "مؤشرك منخفض جدًا وقد يستدعي تقييمًا طبيًا لمعرفة الأسباب ووضع الخطة المناسبة.",
        "calc_bmi_note_obese_severe": "مؤشرك مرتفع جدًا ويستدعي تقييمًا طبيًا شاملًا.",
        "calc_bmi_ctx": "المستخدم لديه BMI = %s كجم/م²",
        "calc_age": "العمر",
        "calc_age_ph": "بالسنوات",
        "calc_weight": "الوزن",
        "calc_weight_ph": "بالكيلوجرام",
        "calc_act": "مستوى النشاط",
        "calc_act_low": "🟢 منخفض",
        "calc_act_med": "🟡 متوسط",
        "calc_act_high": "🔴 مرتفع",
        "calc_fluids_name": "احتياج السوائل",
        "calc_fluids_desc": "احصل على تقدير تقريبي لاحتياجك اليومي من السوائل.",
        "calc_fluids_btn": "احسب الاحتياج",
        "calc_fluids_val": "💧 التقدير التقريبي:",
        "calc_fluids_unit": "لتر يوميًا",
        "calc_fluids_note": "هذا تقدير عام وقد تختلف احتياجات السوائل حسب النشاط والطقس والحالة الصحية وغيرها.",
        "calc_fluids_ctx": "التقدير التقريبي لاحتياج السوائل = %s لتر يوميًا",
        "calc_dose_name": "فاصل الجرعات",
        "calc_dose_desc": "نظم أوقات الدواء حسب الفاصل الذي حدده الطبيب أو الصيدلي.",
        "calc_dose_warn": "مهم: الحاسبة لا تحدد الجرعة ولا تقترح علاجًا.",
        "calc_dose_med": "اسم الدواء (اختياري)",
        "calc_dose_med_ph": "مثال: بنادول",
        "calc_dose_first": "وقت الجرعة الأولى",
        "calc_dose_iv": "الفاصل بين الجرعات",
        "calc_dose_every": "كل %s ساعات",
        "calc_dose_btn": "احسب المواعيد",
        "calc_dose_table": "📅 جدول المواعيد",
        "calc_dose_first_dose": "الجرعة الأولى",
        "calc_dose_next": "الجرعة التالية",
        "calc_am": "ص", "calc_pm": "م",
        "calc_dose_note": "⚠️ استخدم هذه الأداة لتنظيم المواعيد التي حددها الطبيب أو الصيدلي فقط. لا تغيّر الجرعة أو عدد مرات الاستخدام بناءً على هذه الحاسبة.",
        "calc_dose_ctx": "المستخدم لديه دواء «%s» ويريد مساعدة في فهم مواعيد الجرعات",
        "calc_gender": "الجنس",
        "calc_male": "ذكر",
        "calc_female": "أنثى",
        "calc_hgt": "الطول",
        "calc_hgt_ph": "بالسنتيمتر",
        "calc_act2_low": "🪑 قليل",
        "calc_act2_med": "🚶 متوسط",
        "calc_act2_high": "🏃 مرتفع",
        "calc_cal_name": "السعرات اليومية",
        "calc_cal_desc": "احسب تقدير احتياجك اليومي من السعرات.",
        "calc_cal_btn": "احسب السعرات",
        "calc_cal_val": "🔥 احتياجك اليومي التقديري:",
        "calc_cal_unit": "سعرة حرارية",
        "calc_cal_note": "الرقم تقديري وقد يختلف حسب عوامل متعددة. لا تُستخدم الحاسبة لإنشاء حمية أو خطة علاجية تلقائية.",
        "calc_cal_ctx": "احتياج المستخدم اليومي التقديري من السعرات = %s سعرة حرارية",
        "calc_sug_name": "مستوى السكر",
        "calc_sug_desc": "أدخل قراءة السكر وحدد نوع القياس لفهمها بشكل عام.",
        "calc_sug_tag": "الحاسبة الأكثر حساسية — التفسير يعتمد على نوع القياس",
        "calc_sug_hint": "القراءة تختلف حسب نوع القياس: صائم ≠ بعد الأكل ≠ عشوائي ≠ HbA1c. اختر النوع الصحيح قبل تفسير النتيجة.",
        "calc_sug_type": "نوع القياس",
        "calc_sug_fast": "🕐 صائم",
        "calc_sug_post": "🍽️ بعد الأكل بساعتين",
        "calc_sug_random": "🔄 عشوائي",
        "calc_sug_a1c": "🩸 HbA1c",
        "calc_sug_reading": "القراءة",
        "calc_sug_reading_ph": "مثال: 95",
        "calc_sug_unit": "الوحدة",
        "calc_sug_unit_mg": "mg/dL",
        "calc_sug_unit_mmol": "mmol/L",
        "calc_sug_a1c_hint": "HbA1c تقاس بالنسبة المئوية (%)",
        "calc_sug_btn": "تحليل القراءة",
        "calc_sug_val": "🩸 قراءة السكر:",
        "calc_sug_cat_low": "منخفض عن النطاق المعتاد",
        "calc_sug_cat_very_low": "منخفض جدًا — قد يكون خطيرًا",
        "calc_sug_cat_normal": "ضمن النطاق المعتاد",
        "calc_sug_cat_elevated": "أعلى من النطاق المعتاد",
        "calc_sug_cat_high": "نطاق مرتفع",
        "calc_sug_cat_very_high": "مرتفع جدًا",
        "calc_sug_note_low": "قراءتك أقل من النطاق المعتاد. إذا كانت مصحوبة بأعراض (رجفة، تعرق، دوخة، جوع شديد) فتناول مصدر سكر سريع، وإذا لم تتحسن فاطلب تقييمًا طبيًا.",
        "calc_sug_note_very_low": "قراءة منخفضة جدًا تستدعي تقييمًا طبيًا فوريًا، خاصة مع أعراض مثل التشوش أو الإغماء — اطلب الرعاية فورًا.",
        "calc_sug_note_normal": "قراءتك ضمن النطاق المعتاد لنوع القياس المختار.",
        "calc_sug_note_elevated": "قراءتك أعلى من النطاق المعتاد. قد تحتاج القراءة إلى متابعة أو تقييم طبي، ولا تكفي قراءة واحدة لتأكيد التشخيص.",
        "calc_sug_note_high": "قراءتك تقع ضمن نطاق مرتفع لنوع القياس المختار. يُنصح بإعادة الفحص والتقييم لدى الطبيب، ولا تكفي قراءة واحدة لتأكيد التشخيص.",
        "calc_sug_note_very_high": "قراءة مرتفعة جدًا — يُنصح بالحصول على تقييم طبي فوري، ولا تكفي قراءة واحدة لتأكيد التشخيص.",
        "calc_sug_note_ped": "تختلف النطاقات عند الأطفال، راجع الطبيب لتفسير دقيق.",
        "calc_sug_ctx": "المستخدم لديه قراءة %v %u، نوع القياس %t",
    },
    "en": {
        "blood_h": "🩸 Blood Test Analysis",
        "blood_cbc": "Complete Blood Count (CBC)",
        "blood_sub": "We'll help you understand your blood test (CBC) results in a simple, clear way. Upload a photo or PDF of your test and we'll interpret the values for you.",
        "blood_gender": "Gender",
        "blood_gender_ph": "Select gender",
        "blood_female": "Female", "blood_male": "Male", "blood_child": "Child",
        "blood_age": "Age",
        "blood_age_ph": "Enter age in years",
        "blood_hint": "These details help interpret your values against the appropriate reference ranges.",
        "blood_hint2": "💡 Make sure the test photo is clear and well-lit for more accurate reading.",
        "blood_alert": "⚠️ Note: the interpretation below is for awareness only and is not a substitute for a doctor or lab review. See your doctor for any out-of-range value.",
        "blood_drop": "Drag your test file here",
        "blood_drop_or": "or",
        "blood_drop_btn": "📁 Choose file",
        "blood_drop_note": "PDF • JPG • PNG • up to 10 MB",
        "blood_file_del": "Change file 🔄",
        "blood_btn": "🔍 Analyze Test Results",
        "blood_first": "Choose a test file first.",
        "blood_link": "🔗 Link this result to symptom analysis",
        "blood_link_hint": "The analysis will automatically consider your blood test results.",
        "blood_linked": "Blood test linked to the analysis",
        "blood_goto_chat": "Start symptom check now",
        "blood_reading": "Reading and analyzing the test...",
        "blood_err": "Analysis failed",
        "bl_summ": "📋 Test Summary",
        "bl_sum_normal": "Normal", "bl_sum_follow": "Needs follow-up", "bl_sum_out": "Out of range",
        "bl_mean_title": "💡 What do these results mean?",
        "bl_do": "🩺 What should I do?",
        "bl_col_ind": "Indicator", "bl_col_val": "Result", "bl_col_status": "Status",
        "bl_what": "What is it?", "bl_mean": "What does the result mean?", "bl_ref": "Reference range", "bl_when": "When to see a doctor?",
        "bl_explain": "Explain simply",
        "bl_notes": "Notes",
        "bl_status_n": "Normal", "bl_status_l": "Low", "bl_status_h": "High",
        "bl_lvl_normal": "Within normal ✅", "bl_lvl_see_doctor": "See a doctor", "bl_lvl_urgent": "Urgent evaluation", "bl_lvl_emergency": "Emergency 🚨",
        "meds_h": "💊 Medication Info",
        "meds_sub": "Type a medication name to see its uses, warnings, and possible interactions.",
        "meds_label": "Medication name",
        "meds_ph": "Example: Paracetamol, Voltaren, Aspirin",
        "meds_btn": "🔎 Search",
        "meds_searching": "Searching...",
        "meds_nf": "We couldn't find this medication in our database. Check the spelling or consult your doctor or pharmacist.",
        "meds_sec_uses": "Uses",
        "meds_sec_warn": "⚠️ Warnings",
        "meds_sec_int": "Possible interactions",
        "meds_sec_consult": "❗ When to consult",
        "meds_consult_txt": "If you are pregnant or breastfeeding, take other medications, or have chronic conditions — consult your doctor or pharmacist before use.",
        "meds_disc": "This information is for awareness only and does not replace consulting a doctor or pharmacist.",
        "meds_warn2": "The medication information provided does not replace the official leaflet or a consultation with your doctor or pharmacist.",
        "rem_h": "⏰ Medication Reminder",
        "rem_sub": "Save your medication times and the browser will remind you daily (notifications work while the page is open).",
        "rem_list_h": "🔔 Your reminders",
        "rem_name": "Medication name", "rem_times": "Times (hour:minute)",
        "rem_name_ph": "Example: Paracetamol", "rem_times_ph": "Example: 08:00, 14:00, 20:00",
        "rem_save": "Save reminder 💊",
        "meds_warn": "⚠️ Don't stop or change the dose of any prescribed medication without consulting your doctor or pharmacist.",
        "meds_write": "Enter the medications first.",
        "meds_checking": "Checking...",
        "meds_none": "✅ No matching warnings found for the medications you entered.",
        "meds_col": "Medication", "warn_col": "Warning",
        "no_rem": "No reminders yet.",
        "del": "Delete 🗑️",
        "name_first": "Enter the medication name first.",
        "times_ph_err": "Enter times like: 08:00, 14:00, 20:00",
        "no_notif": "Your browser does not support notifications.",
        "enable_notif": "Enable notifications in your browser settings for the reminder to work.",
        "saved": "✅ Reminder saved. Your browser will notify you at the set times (while the page is open).",
        "rem_notif_t": "💊 Medication reminder", "rem_notif_b": "Time to take: ",
        "fam_h": "👨‍👩‍👧 Family Health Hub",
        "fam_sub": "Separate health records for everyone you care for — analyses, tests, and medications for each person without mixing data.",
        "me_short": "👤 Me",
        "fam_add": "➕ Add family member",
        "fam_edit": "✏️ Edit",
        "fam_del": "Delete 🗑️",
        "fam_empty": "No family members yet. Add one to start tracking their health.",
        "fam_who": "Who do you want to add?",
        "fam_rel_me": "Me", "fam_rel_mother": "Mother", "fam_rel_father": "Father",
        "fam_rel_daughter": "Daughter", "fam_rel_son": "Son", "fam_rel_grandparent": "Grandparent", "fam_rel_other": "Other",
        "fam_name": "Name", "fam_name_ph": "e.g. Mom",
        "fam_age": "Age or date of birth", "fam_age_ph": "e.g. 48",
        "fam_gender": "Gender", "fam_g_f": "Female", "fam_g_m": "Male",
        "fam_conditions": "Previous conditions", "fam_meds": "Medications",
        "fam_allergies": "Allergies", "fam_notes": "Notes",
        "fam_save": "Save",
        "fam_last_analysis": "🩺 Last symptom analysis",
        "fam_last_cbc": "🩸 Last CBC test",
        "fam_meds_reg": "💊 Registered medications",
        "fam_adherence": "Adherence",
        "fam_followup": "📈 Follow-up",
        "fam_timeline": "📅 Health history",
        "fam_no_analysis": "No analysis yet",
        "fam_no_cbc": "No test yet",
        "fam_no_meds": "No registered medications",
        "fam_add_analysis": "Symptom analysis →",
        "fam_add_cbc": "Upload CBC →",
        "fam_no_adherence": "—",
        "fam_years": "yrs",
        "fam_back": "→ Back to family",
        "fam_plan_title": "💊 Medication reminders",
        "fam_plan_sub": "Medications for «%s» and their times — next to each time: Taken / Skip / Remind later.",
        "fam_take": "✅ Taken",
        "fam_skip": "⏭️ Skip",
        "fam_later": "⏰ Later",
        "fam_add_plan": "➕ Add medication",
        "fam_plan_name": "Medication name",
        "fam_plan_name_ph": "e.g. Panadol",
        "fam_plan_dose": "Dose (optional)",
        "fam_plan_times": "Usage times (hour:minute)",
        "fam_plan_times_ph": "e.g. 08:00, 20:00",
        "fam_plan_days": "Duration in days (optional)",
        "fam_plan_start": "Start date",
        "fam_plan_save": "Save reminder 💊",
        "fam_week_adh": "💊 This week's adherence: %s%",
        "fam_due_today": "Medication time",
        "fam_person": "Person",
        "fam_relations": "Relation",
        "fam_actions": "Actions",
        "fam_open": "Open file",
        "fam_today_logged": "Logged",
        "fam_analysis": "Symptom analysis",
        "fam_cbc": "CBC test",
        "fam_med": "Medication",
        "fam_days": "days",
        "fam_no_events": "No events in the last 30 days.",
        "fam_delete_confirm": "Delete this member? Their records will be detached.",
        "fam_saved": "✅ Saved.",
        "fam_err": "Error: ",
        "fam_done": "Done",
        "fam_each_person": "Each person has their own profile: age, gender, conditions, medications, tests, and past analyses.",
        "fam_hub_intro": "One place to manage health records for the people you care for.",
        "asst_title": "Ask SymptoSense",
        "asst_sub": "The site's smart assistant",
        "asst_ph": "Type your question...",
        "asst_close": "Close",
        "asst_greet": "Hello! 👋\nI'm SymptoSense. How can I help you today?",
        "asst_opt_symp": "Physical symptoms",
        "asst_opt_symp_d": "Tell me about the symptoms you're feeling.",
        "asst_opt_drug": "A question about a drug",
        "asst_opt_drug_d": "Ask about a medication, its dose, or warnings.",
        "asst_opt_blood": "Blood test",
        "asst_opt_blood_d": "Understand your blood test results in simple terms.",
        "asst_opt_mh": "My mental health",
        "asst_opt_mh_d": "A calm space to talk about your feelings, anxiety, and stress.",
        "asst_opt_calc": "Health calculator",
        "asst_opt_calc_d": "Calculate a health metric like BMI or calories.",
        "asst_opt_q": "Health question",
        "asst_opt_q_d": "Ask me about any health topic you want to understand.",
        "asst_mh_title": "🤍 My mental health",
        "asst_mh_sub": "A calm space for you",
        "asst_mh_greet": "I'm with you 🤍\nWhat would you like to talk about most?",
        "asst_mh_o_anx": "Anxiety",
        "asst_mh_o_anx_d": "Worry or thoughts running through your head.",
        "asst_mh_o_sad": "Sadness",
        "asst_mh_o_sad_d": "Low mood or sadness.",
        "asst_mh_o_str": "Stress",
        "asst_mh_o_str_d": "Tension or pressure.",
        "asst_mh_o_slp": "Sleep",
        "asst_mh_o_slp_d": "Difficulty sleeping or insomnia.",
        "asst_mh_o_tho": "Many thoughts",
        "asst_mh_o_tho_d": "Racing, jumbled thoughts.",
        "asst_mh_o_oth": "Something else",
        "asst_mh_o_oth_d": "Another topic you'd like to share.",
        "asst_mh_send_anx": "I feel very anxious",
        "asst_mh_send_sad": "I feel sad",
        "asst_mh_send_str": "I'm stressed and tense",
        "asst_mh_send_slp": "I can't sleep",
        "asst_mh_send_tho": "I have many racing thoughts",
        "asst_mh_send_oth": "I want to talk about something else",
        "asst_mh_calm_chip": "🌿 Help me calm down",
        "asst_mh_opt1": "I want to talk",
        "asst_mh_opt1_d": "If you need someone to listen.",
        "asst_mh_opt2": "Help me calm down",
        "asst_mh_opt2_d": "If you feel anxious or panicked right now.",
        "asst_mh_opt3": "Help me understand my feeling",
        "asst_mh_opt3_d": "If you want to understand what you feel better.",
        "asst_mh_ph": "Tell me freely...",
        "asst_mh_anim": "Stop motion",
        "asst_mh_anim_on": "Start motion",
        "asst_mh_talk_msg": "🤍 I'm here with you. Start with anything on your mind — even if it's unorganized. I'm listening.",
        "asst_mh_calm_msg": "🌿 Take a deep breath with me... watch the circle and breathe with it. Take your time, I'm here.",
        "asst_mh_feel_msg": "🧠 Take your time... when did this feeling appear? What came before it? Write whatever comes to mind, however small.",
        "asst_br_in": "Breathe in",
        "asst_br_hold": "Hold",
        "asst_br_out": "Breathe out",
        "asst_mh_opt_night": "🌙 Night Calm",
        "asst_mh_opt_night_d": "A calm mode for rest before sleep.",
        "night_calm_title": "🌙 Night Calm",
        "night_calm_greet": "Let's make everything a little calmer.\nYou don't have to figure everything out tonight. 🤍",
        "night_calm_q": "What do you need right now?",
        "night_calm_opt_calm": "🌿 I need to calm down",
        "night_calm_opt_listen": "🫂 I need someone to listen",
        "night_calm_opt_think": "💭 My thoughts are racing",
        "night_calm_opt_sleep": "😴 Help me prepare for sleep",
        "night_calm_calm_reply": "Of course 🤍\nWe don't need to do anything big right now.\nLet's focus on this moment you're in.",
        "night_calm_calm_step": "🌿 Take a comfortable breath.\nDon't force a deep breath.\nJust breathe gently.\n\nI'm here with you. 🤍",
        "night_calm_next": "Ready for the next step",
        "night_calm_listen_reply": "I'm here 🤍\nTell me what's on your mind, even if you can't organize it.",
        "night_calm_think_reply": "I understand 🤍\nSometimes when everything piles up in your head, even small things feel heavy.\n\nWhat thought is weighing on you the most right now?",
        "night_calm_sleep_reply": "Let's wind down the day a little.\n\nWould you like to:\n🫂 Talk about your day\n🌿 A short calming session\n💭 Empty my thoughts\n🤍 Something simple to help me relax",
        "night_calm_safety": "🤍 I hear you, and what you're saying matters.\nBut because you said something that worries me about your safety, let's focus on you right now.\n\nAre you in immediate danger?",
        "night_calm_safety_call": "📞 Call support line 937 | 🚑 Emergency 997",
        "memory_title": "🧠 My Memory With You",
        "memory_subtitle": "Information you allow the assistant to use to personalize your experience.",
        "memory_control": "You're in control — see any saved info, edit or delete it anytime.",
        "memory_add": "➕ Add Information",
        "memory_manage": "🧹 Manage My Memory",
        "memory_source_profile": "From your profile",
        "memory_source_chat": "Mentioned in this chat",
        "memory_source_memory": "Saved in my memory",
        "memory_source_unknown": "Unknown",
        "memory_empty": "No saved information yet.",
        "memory_empty_sub": "When you share information with the assistant, it can be saved here.",
        "manage_title": "Manage My Info",
        "manage_subtitle": "Control the information saved in your account. Edit or delete any info anytime.",
        "manage_edit": "Edit",
        "manage_delete": "Delete",
        "manage_not_set": "Not set",
        "manage_saved": "✅ Saved successfully",
        "manage_error": "❌ Error occurred",
        "manage_deleted": "✅ Deleted successfully",
        "manage_delete_all": "🧹 Delete All My Info",
        "manage_delete_confirm": "Are you sure? This will delete all saved health information.",
        "manage_delete_type": "Type 'delete' to confirm",
        "transparency_title": "What We Know About Your Condition",
        "transparency_sub": "This is the information we used in the analysis:",
        "trans_known": "Known",
        "trans_known_none": "No confirmed information",
        "trans_unclear": "Unclear",
        "trans_unclear_confidence": "Low analysis confidence",
        "trans_unclear_duration": "Duration not specified",
        "trans_unclear_notes": "Notes too brief",
        "trans_unclear_none": "No unclear information",
        "trans_notasked": "Not Asked",
        "trans_notasked_sleep": "Sleep pattern",
        "trans_notasked_appetite": "Appetite changes",
        "trans_notasked_stress": "Recent stress",
        "trans_notasked_family": "Family history",
        "trans_notasked_note": "💡 Not every missing piece means a problem. Some information may not be necessary for your current analysis.",
        "trans_add_info": "➕ Add More Info",
        "trans_add_q": "What information would you like to add?",
        "trans_add_duration": "Duration",
        "trans_add_meds": "Medications",
        "trans_add_meds_q": "What medications are you currently taking?",
        "trans_add_meds_hint": "Type medication names or usage",
        "trans_add_notes": "Additional notes",
        "trans_add_notes_q": "What note would you like to add?",
        "trans_add_notes_hint": "Type any additional information",
        "trans_add_done": "✅ Thanks, the info is sufficient",
        "trans_adding": "I want to add more information",
        "asst_calc_greet": "🤍 I'm here if you need me\nGot a question about one of the calculators? Ask me.",
        "asst_calc_bmi_greet": "⚖️ Got a BMI result?\nI can explain what it means simply.",
        "asst_calc_sug_greet": "🩸 Want to understand a sugar reading?\nI can clarify the result based on the measurement type.",
        "asst_calc_fluids_greet": "💧 Got a question about fluid needs?\nI can help.",
        "asst_calc_cal_greet": "🔥 Got a question about calories?\nI can explain the idea.",
        "asst_calc_dose_greet": "💊 Got a question about dose times?\nI can help.",
        "asst_q_calc1": "Which calculator should I start with?",
        "asst_q_calc2": "How do I use the sugar calculator?",
        "asst_q_calc3": "Are the results accurate?",
        "asst_q_sug1": "What does a sugar reading mean?",
        "asst_q_sug2": "What's the difference between fasting and post-meal?",
        "asst_q_sug3": "Is my reading normal?",
        "asst_q_bmi1": "Explain what my BMI means",
        "asst_q_bmi2": "Is BMI always accurate?",
        "asst_q_bmi3": "What's the ideal weight for my height?",
        "asst_q_fluids1": "How much water should I drink a day?",
        "asst_q_cal1": "What calories are right for me?",
        "asst_q_dose1": "How do I organize my dose times?",
        "asst_q1": "I've had a headache for two days",
        "asst_q2": "How do I upload a blood test?",
        "asst_q3": "What is the Family Health Hub?",
        "asst_q4": "How can I track my medications?",
        "asst_emerg_txt": "⚠️ You may be showing emergency signs. Call emergency services now:",
        "asst_emerg_btn": "Emergency page ←",
        "asst_offline": "Sorry, I can't reply right now. Try the symptom analysis page or see a doctor if needed.",
        "asst_disc": "This information is educational and is not a medical or mental-health diagnosis. In an emergency, contact a professional or emergency services.",
        "asst_svc_symp": "Symptom check", "asst_svc_blood": "Blood test analysis",
        "asst_svc_family": "Family Health Hub", "asst_svc_meds": "Medications page",
        "asst_svc_hosp": "Nearest hospital",
        "fa_h": "🚑 First Aid",
        "fa_sub": "Choose a condition to view step-by-step first aid instructions.",
        "fa_warn": "⚠️ In critical cases (stopped breathing, heavy bleeding, loss of consciousness) call an ambulance at <b>997</b> immediately.",
        "fa_video": "▶ Watch a demo video",
        "tips_h": "🌿 Health Tips Center",
        "tips_sub": "Practical daily tips for better health for you and your family.",
        "tips_btn": "Another tip 🔄",
        "tips_warn": "⚠️ The tips above are general awareness advice and do not replace a doctor's consultation, especially if you have a specific health condition.",
        "relax_h": "🧘 Relaxation & Breathing Exercise",
        "br_in": "Breathe in 🌬️", "br_hold": "Hold 🧘", "br_out": "Breathe out 😮‍💨",
        "em_h": "🚨 Emergency",
        "em_sub": "Emergency numbers in Saudi Arabia — keep them and call immediately when needed.",
        "em_alert": "⚠️ If you have a medical emergency, call emergency services immediately and don't rely on electronic analysis.",
        "em_red": "Red Crescent (Ambulance)", "em_unified": "Unified Emergency",
        "em_937": "Ministry of Health",
        "em_red_desc": "Ambulance & medical emergencies",
        "em_unified_desc": "Unified emergency number across all regions",
        "em_937_desc": "Free health consultations around the clock",
        "em_call": "Call now",
        "em_police": "Police", "em_civil": "Civil Defense",
        "em_police_desc": "Police emergency", "em_civil_desc": "Civil defense emergency",
        "em_signs_h": "⚠️ Signs that require immediate help",
        "em_s1": "😮‍💨 Severe difficulty breathing",
        "em_s2": "💔 Severe or sudden chest pain",
        "em_s3": "😵 Loss of consciousness",
        "em_s4": "🩸 Bleeding that won't stop",
        "em_s5": "🗣️ Sudden stroke symptoms",
        "em_call_btn": "📞 Call emergency",
        "em_geo_title": "📍 Nearest hospital to you",
        "em_geo_sub": "Find the nearest hospital or emergency center based on your current location.",
        "em_geo_24h": "Available 24/7",
        "em_safety": "🛡️ Safety first — never wait when symptoms are dangerous; every minute may matter.",
        "em_warn": "⚠️ For dangerous symptoms (severe chest pain, difficulty breathing, heavy bleeding, loss of consciousness) call an ambulance at <b>997</b> immediately; don't wait.",
        "em_geo": "A hospital near you 📍",
        "em_geo_btn": "🔎 Find nearest hospital",
        "em_geo_searching": "Locating you and searching...",
        "em_geo_err": "Could not locate you — please allow location access.",
        "em_geo_empty": "No nearby hospitals found.",
        "em_nearby": "Nearest hospitals:",
        "ci_h": "📋 Daily Health Tracking",
        "ci_sub": "Record your state every day (1 = very bad, 5 = excellent) and track your improvement on the chart.",
        "ci_saved": "State recorded ✅ (5 = excellent, 1 = very bad)",
        "ci_err": "Error: ",
        "ci_chart_err": "Could not load the chart.",
        "ci_empty": "No records yet — record your first rating using the buttons above.",
        "ci_alt": "Improvement chart",
        "nav_search": "Health Search",
        "title_search": "SymptoSense — Smart Health Search",
        "sea_h": "🔎 Smart Health Search",
        "sea_sub": "Search any symptom, lab test, medical term, or medication in plain language — and understand when it needs attention or a doctor visit.",
        "sea_ph": "Type your question... e.g. Why do I feel like the room is spinning? or What does WBC mean?",
        "sea_btn": "Search 🔍",
        "sea_hint": "Try natural language: \"Why does the room spin?\" or \"What does WBC mean?\"",
        "sea_warn": "⚠️ The information shown is general awareness content and is not a medical diagnosis — in emergencies call 997 immediately.",
        "sea_what": "What is it?",
        "sea_causes": "💡 Common causes",
        "sea_worry": "When should it worry me?",
        "sea_doctor": "When should I see a doctor?",
        "sea_explain": "Explain it simply",
        "sea_ask_assist": "Ask the assistant",
        "sea_disc": "🩺 Awareness information only — not a diagnosis.",
        "sea_noresult": "No matching result. Try different words or ask the assistant using the floating button.",
        "sea_err": "Search failed, please try again.",
        "sea_cat_symp": "Symptom", "sea_cat_test": "Lab test", "sea_cat_term": "Term", "sea_cat_med": "Medication",
        "sea_explain_title": "Explain it simply",
        "sea_noexplain": "No simple explanation found for this term yet.",
        "lv_very_simple": "Very simple", "lv_basic": "Simple", "lv_advanced": "Advanced",
        "asst_explain_ask": "Ask the assistant about this",
        "asst_ctx": "I was looking up \"%s\" — can you give me more details about it?",
        "asst_fb_good": "Useful", "asst_fb_partial": "Partially", "asst_fb_bad": "Not useful",
        "asst_fb_thanks": "Thanks for your rating! 🎉", "asst_fb_sent": "Thanks for your feedback! ✅",
        "asst_fb_title": "Why wasn't this helpful?",
        "asst_fr1": "The explanation was unclear", "asst_fr2": "The answer was too long", "asst_fr3": "It didn't answer my question",
        "asst_fr4": "I need more information", "asst_fr5": "The answer wasn't relevant", "asst_fr6": "Other reason",
        "calc_h": "🧮 Health Calculators",
        "calc_sub": "Simple tools to help you understand some health indicators. Calculate, understand the result, and if you need more, ask SymptoSense.",
        "calc_now": "Calculate now",
        "calc_back": "↩ Back to calculators",
        "calc_follow": "💡 What does the result mean?",
        "calc_ask": "🤖 Ask SymptoSense",
        "calc_ask_bmi_t": "💡 What does the result mean?",
        "calc_ask_bmi_b": "🤖 Let SymptoSense explain it",
        "calc_ask_sug_t": "💡 What does this number mean?",
        "calc_ask_sug_b": "🤖 Ask SymptoSense",
        "calc_alert_t": "🚨 Alert",
        "calc_alert_msg": "The result you entered may warrant medical evaluation, especially if you have severe symptoms.",
        "calc_alert_high": "🚨 The reading is very high — urgent medical evaluation is advised; if it's accompanied by severe symptoms, call emergency services 997 immediately.",
        "calc_alert_low": "🚨 The reading is very low — if accompanied by symptoms (shaking, dizziness, sweating, confusion), have a fast-acting sugar source and seek medical evaluation; if it worsens, call 997.",
        "calc_em_btn": "🚨 Emergency guide",
        "calc_disc_t": "Good to know",
        "calc_disc": "The results are estimates for education only and don't replace a doctor's consultation. Don't change your medication or dose based on a calculator result.",
        "calc_err": "Calculation error — please check the entered values.",
        "calc_bmi_name": "Body Mass Index",
        "calc_bmi_desc": "Compute your Body Mass Index based on your height and weight.",
        "calc_bmi_w": "Weight (kg)",
        "calc_bmi_w_ph": "e.g. 70",
        "calc_bmi_h": "Height (cm)",
        "calc_bmi_h_ph": "e.g. 175",
        "calc_bmi_btn": "Calculate BMI",
        "calc_bmi_val": "⚖️ Body Mass Index:",
        "calc_bmi_unit": "kg/m²",
        "calc_bmi_cat_under": "Underweight",
        "calc_bmi_cat_normal": "Within the usual range",
        "calc_bmi_cat_over": "Overweight",
        "calc_bmi_cat_obese": "Obesity",
        "calc_bmi_cat_under_severe": "Severely underweight",
        "calc_bmi_cat_obese_severe": "Severe obesity",
        "calc_bmi_note_under": "Your index is below the usual range. This may relate to body build or other factors — the index alone is not enough for assessment.",
        "calc_bmi_note_normal": "Your index is within the usual range. BMI is a general indicator, not a medical diagnosis, and may not suit everyone (power athletes, children, older adults, pregnant women).",
        "calc_bmi_note_over": "Your index is above the usual range. BMI is a general indicator, not a medical diagnosis, and may not suit everyone.",
        "calc_bmi_note_obese": "Your index falls in the obesity range. A doctor visit is advised for a full assessment — the index alone doesn't define the risk.",
        "calc_bmi_note_under_severe": "Your index is very low and may warrant a medical evaluation to identify the causes.",
        "calc_bmi_note_obese_severe": "Your index is very high and warrants a full medical evaluation.",
        "calc_bmi_ctx": "The user's BMI is %s kg/m²",
        "calc_age": "Age",
        "calc_age_ph": "in years",
        "calc_weight": "Weight",
        "calc_weight_ph": "in kilograms",
        "calc_act": "Activity level",
        "calc_act_low": "🟢 Low",
        "calc_act_med": "🟡 Moderate",
        "calc_act_high": "🔴 High",
        "calc_fluids_name": "Fluid Needs",
        "calc_fluids_desc": "Get a rough estimate of your daily fluid needs.",
        "calc_fluids_btn": "Calculate needs",
        "calc_fluids_val": "💧 Rough estimate:",
        "calc_fluids_unit": "liters daily",
        "calc_fluids_note": "This is a general estimate — fluid needs vary with activity, weather, health status and more.",
        "calc_fluids_ctx": "The user's rough daily fluid need is %s liters",
        "calc_dose_name": "Dose Interval",
        "calc_dose_desc": "Organize your medication times according to the interval set by your doctor or pharmacist.",
        "calc_dose_warn": "Important: this calculator does not set the dose and does not suggest a treatment.",
        "calc_dose_med": "Medication name (optional)",
        "calc_dose_med_ph": "e.g. Panadol",
        "calc_dose_first": "First dose time",
        "calc_dose_iv": "Interval between doses",
        "calc_dose_every": "Every %s hours",
        "calc_dose_btn": "Calculate times",
        "calc_dose_table": "📅 Dose schedule",
        "calc_dose_first_dose": "First dose",
        "calc_dose_next": "Next dose",
        "calc_am": "AM", "calc_pm": "PM",
        "calc_dose_note": "⚠️ Use this tool only to organize the times set by your doctor or pharmacist. Do not change the dose or frequency based on this calculator.",
        "calc_dose_ctx": "The user takes a medication \"%s\" and wants help understanding dose times",
        "calc_gender": "Gender",
        "calc_male": "Male",
        "calc_female": "Female",
        "calc_hgt": "Height",
        "calc_hgt_ph": "in centimeters",
        "calc_act2_low": "🪑 Sedentary",
        "calc_act2_med": "🚶 Moderate",
        "calc_act2_high": "🏃 Active",
        "calc_cal_name": "Daily Calories",
        "calc_cal_desc": "Estimate your daily calorie needs.",
        "calc_cal_btn": "Calculate calories",
        "calc_cal_val": "🔥 Estimated daily need:",
        "calc_cal_unit": "calories",
        "calc_cal_note": "The number is an estimate and may vary due to many factors. This calculator is not used to create a diet or automatic treatment plan.",
        "calc_cal_ctx": "The user's estimated daily calorie need is %s calories",
        "calc_sug_name": "Blood Sugar Level",
        "calc_sug_desc": "Enter a glucose reading and choose the measurement type to understand it in general.",
        "calc_sug_tag": "The most sensitive calculator — the interpretation depends on the measurement type",
        "calc_sug_hint": "The reading differs by measurement type: fasting ≠ after-meal ≠ random ≠ HbA1c. Choose the right type before interpreting the result.",
        "calc_sug_type": "Measurement type",
        "calc_sug_fast": "🕐 Fasting",
        "calc_sug_post": "🍽️ 2 hours after a meal",
        "calc_sug_random": "🔄 Random",
        "calc_sug_a1c": "🩸 HbA1c",
        "calc_sug_reading": "Reading",
        "calc_sug_reading_ph": "e.g. 95",
        "calc_sug_unit": "Unit",
        "calc_sug_unit_mg": "mg/dL",
        "calc_sug_unit_mmol": "mmol/L",
        "calc_sug_a1c_hint": "HbA1c is measured as a percentage (%)",
        "calc_sug_btn": "Analyze reading",
        "calc_sug_val": "🩸 Glucose reading:",
        "calc_sug_cat_low": "Below the usual range",
        "calc_sug_cat_very_low": "Very low — may be dangerous",
        "calc_sug_cat_normal": "Within the usual range",
        "calc_sug_cat_elevated": "Above the usual range",
        "calc_sug_cat_high": "High range",
        "calc_sug_cat_very_high": "Very high",
        "calc_sug_note_low": "Your reading is below the usual range. If accompanied by symptoms (shaking, sweating, dizziness, strong hunger), have a fast-acting sugar source; if it doesn't improve, seek medical evaluation.",
        "calc_sug_note_very_low": "A very low reading warrants immediate medical evaluation, especially with symptoms such as confusion or fainting — seek care right away.",
        "calc_sug_note_normal": "Your reading is within the usual range for the selected measurement type.",
        "calc_sug_note_elevated": "Your reading is above the usual range. It may need follow-up or medical evaluation, and a single reading is not enough to confirm a diagnosis.",
        "calc_sug_note_high": "Your reading falls in a high range for the selected measurement type. Re-testing and evaluation by a doctor are advised; a single reading is not enough to confirm a diagnosis.",
        "calc_sug_note_very_high": "A very high reading — immediate medical evaluation is advised, and a single reading is not enough to confirm a diagnosis.",
        "calc_sug_note_ped": "Ranges differ for children — ask your doctor for an accurate interpretation.",
        "calc_sug_ctx": "The user has a reading of %v %u, measurement type %t",
    },
}


# ---------------------------------------------------------------- blood
def blood_page():
    t = CT["en" if _lang() == "en" else "ar"]
    body = """
    <div class="card">
      <h2>__BH__</h2>
      <p class="cbc">__BCBC__</p>
      <p class="muted">__BSUB__</p>
      <div style="margin-top:20px;">
        <div class="grid2">
          <div class="field-box">
            <div class="fb-ic">👤</div>
            <div style="flex:1;">
              <label class="lbl">__BGENDER__</label>
              <select class="inp" id="bg"><option value="" disabled selected>__BGENDERPH__</option><option value="f">__BF__</option><option value="m">__BM__</option><option value="c">__BC__</option></select>
            </div>
          </div>
          <div class="field-box">
            <div class="fb-ic">🎂</div>
            <div style="flex:1;">
              <label class="lbl">__BAGE__</label>
              <input class="inp" type="number" id="ba" placeholder="__BAGEPH__">
            </div>
          </div>
        </div>
        <p class="hint-note">__BHINT__</p>
        <p class="hint-note">__BHINT2__</p>
        <div class="warn" style="margin-bottom:16px;">__BALERT__</div>
        <div class="drop" id="drop">
          <div class="d-icon">📄</div>
          <div class="d-text">__BDROP__</div>
          <div class="d-or">__BDROPOR__</div>
          <div class="d-btn">__BDROPBTN__</div>
          <div class="d-note">__BDROPNOTE__</div>
        </div>
        <input type="file" id="fileInp" accept="image/*,application/pdf" style="display:none;">
        <div style="text-align:center;margin-top:18px;">
          <button class="btn pri big" onclick="uploadBlood()">__BBTN__</button>
        </div>
        <div id="bloodRes" style="margin-top:18px;"></div>
        <div id="linkRow" style="margin-top:12px;text-align:center;"></div>
      </div>
    </div>
    <script>
    const T = __PT__;
    function TT(k) { return T[k] || k; }
    function esc(s) { const d=document.createElement('div'); d.textContent=s||''; return d.innerHTML; }
    const drop = document.getElementById('drop');
    const fileInp = document.getElementById('fileInp');
    let selFile = null;
    drop.onclick = (ev) => { if (selFile) return; fileInp.click(); };
    drop.ondragover = e => { e.preventDefault(); if (!selFile) drop.classList.add('on'); };
    drop.ondragleave = () => drop.classList.remove('on');
    drop.ondrop = e => { e.preventDefault(); drop.classList.remove('on'); if (e.dataTransfer.files[0]) { fileInp.files = e.dataTransfer.files; pickFile(); } };
    fileInp.onchange = () => { if (fileInp.files[0]) pickFile(); };
    function pickFile() {
      const f = fileInp.files[0];
      selFile = f;
      const size = f.size / 1024 / 1024;
      const sz = size >= 1 ? size.toFixed(1) + ' MB' : Math.round(f.size / 1024) + ' KB';
      drop.classList.add('selected');
      drop.innerHTML = '<div class="d-icon">✅</div><div class="d-file">' + esc(f.name) + '</div><div class="d-or">' + sz + '</div>' +
        '<button class="d-del" onclick="delFile(event)">' + esc(TT('blood_file_del')) + '</button>';
    }
    function delFile(ev) {
      ev.stopPropagation();
      selFile = null; fileInp.value = '';
      drop.classList.remove('selected');
      drop.innerHTML = '<div class="d-icon">📄</div><div class="d-text">' + esc(TT('blood_drop')) + '</div>' +
        '<div class="d-or">' + esc(TT('blood_drop_or')) + '</div><div class="d-btn">' + esc(TT('blood_drop_btn')) + '</div>' +
        '<div class="d-note">' + esc(TT('blood_drop_note')) + '</div>';
      fileInp.click();
    }
    async function uploadBlood() {
      if (!selFile) { document.getElementById('bloodRes').innerHTML = '<div class="warn">' + esc(TT('blood_first')) + '</div>'; return; }
      const box = document.getElementById('bloodRes');
      box.innerHTML = '<div class="bubble bot" style="max-width:100%">' + esc(TT('blood_reading')) + ' <span class="spin"></span></div>';
      const fd = new FormData();
      fd.append('file', selFile);
      fd.append('gender', document.getElementById('bg').value);
      fd.append('age', document.getElementById('ba').value);
      const r = await fetch('/api/blood', { method: 'POST', body: fd });
      const d = await r.json();
      if (d.consent_required) { location.href=d.consent_url||'/consent?next=/blood'; return; }
      if (!d.ok) { box.innerHTML = '<div class="warn">' + esc(d.error || TT('blood_err')) + '</div>'; return; }
      let h = '<div class="result bubble bot" style="max-width:100%">';
      if (d.indicators && d.indicators.length) {
        h += '<div class="res-title">' + esc(TT('bl_summ')) + '</div>';
        let g = 0, a = 0, r = 0;
        const lv = d.level || 'normal';
        d.indicators.forEach(function(it) { if (it.status === 'normal') g++; else if (lv === 'urgent' || lv === 'emergency') r++; else a++; });
        h += '<div class="bl-sum-chips">' +
          '<span class="bl-chip cg">🟢 ' + esc(TT('bl_sum_normal')) + ' ' + g + '</span>' +
          '<span class="bl-chip ca">🟡 ' + esc(TT('bl_sum_follow')) + ' ' + a + '</span>' +
          '<span class="bl-chip cr">🔴 ' + esc(TT('bl_sum_out')) + ' ' + r + '</span>' +
          '</div>';
        h += '<div style="margin:10px 0 12px;"><span class="pill2 ' + lvlCls(d.level) + '">' + esc(lvlTxt(d.level)) + '</span></div>';
        if (d.summary) h += '<p style="font-size:14px;line-height:1.8;">' + esc(d.summary) + '</p>';
        h += '<table class="tbl bl-table"><tr><th>' + esc(TT('bl_col_ind')) + '</th><th>' + esc(TT('bl_col_val')) + '</th><th>' + esc(TT('bl_col_status')) + '</th></tr>';
        d.indicators.forEach(function(it, i) {
          h += '<tr class="bl-row" onclick="toggleInd(' + i + ')">';
          h += '<td><b>' + esc(it.name) + '</b> <button class="bl-explain" onclick="event.stopPropagation();openExplain(\\'' + esc(it.name).replace(/["\'\\\\]/g, '') + '\\')" title="' + esc(TT('bl_explain')) + '">✨ ' + esc(TT('bl_explain')) + '</button></td><td>' + esc(String(it.value)) + ' ' + esc(it.unit || '') + '</td>';
          h += '<td><span class="pill2 ' + stCls(it.status) + '">' + esc(stTxt(it.status)) + '</span></td></tr>';
          h += '<tr class="bl-detail" id="bl-det-' + i + '" style="display:none;"><td colspan="3"><div class="bl-det-inner">';
          if (it.what) h += '<p><b>' + esc(TT('bl_what')) + '</b> ' + esc(it.what) + '</p>';
          if (it.meaning) h += '<p><b>' + esc(TT('bl_mean')) + '</b> ' + esc(it.meaning) + '</p>';
          h += '<p><b>' + esc(TT('bl_ref')) + '</b> ' + esc(it.low) + ' – ' + esc(it.high) + ' ' + esc(it.unit || '') + '</p>';
          if (it.when) h += '<p><b>' + esc(TT('bl_when')) + '</b> ' + esc(it.when) + '</p>';
          h += '</div></td></tr>';
        });
        h += '</table>';
        if (d.notes && d.notes.length) {
          h += '<div class="bl-notes"><div class="rc-title">' + esc(TT('bl_mean_title')) + '</div>';
          d.notes.forEach(function(n) { h += '<p style="font-size:13.5px;line-height:1.8;">• ' + esc(n) + '</p>'; });
          h += '</div>';
        }
        if (d.dangers && d.dangers.length) {
          h += '<div class="bl-notes"><div class="rc-title">' + esc(TT('bl_do')) + '</div><div class="warn" style="margin-top:8px;">';
          d.dangers.forEach(function(n) { h += '<p>🚨 ' + esc(n) + '</p>'; });
          h += '</div></div>';
        }
        if (d.child) h += '<div class="bl-note">👶 ' + esc(d.child_note) + '</div>';
        h += '<div class="bl-note">' + esc(d.disclaimer) + '</div>';
      } else {
        h += d.text_html || '';
      }
      if (d.chart) h += '<div style="text-align:center;margin-top:14px;"><img src="data:image/png;base64,' + d.chart + '" alt="' + esc(TT('bl_summ')) + '" style="max-width:100%;border-radius:12px;box-shadow:0 4px 14px rgba(0,0,0,.08);"></div>';
      h += '</div>';
      box.innerHTML = h;
      if (d.blood_id) {
        const lr = document.getElementById('linkRow');
        lr.innerHTML = '<button class="btn pri" onclick="linkBlood(' + d.blood_id + ')">' + esc(TT('blood_link')) + '</button>' +
          '<p style="font-size:12.5px;color:#64748b;margin-top:8px;">' + esc(TT('blood_link_hint')) + '</p>';
      }
    }
    function linkBlood(id) {
      try { localStorage.setItem('symptosense_blood_id', String(id)); } catch (e) {}
      const lr = document.getElementById('linkRow');
      lr.innerHTML = '<div style="display:inline-block;padding:10px 18px;border-radius:12px;background:#EAF4FF;border:1px solid #DCEBFA;color:#123B70;font-weight:700;">✅ ' + esc(TT('blood_linked')) + '</div>' +
        '<div style="margin-top:10px;"><a class="btn pri" href="/chat">' + esc(TT('blood_goto_chat')) + '</a></div>';
    }
    function toggleInd(i) { const el = document.getElementById('bl-det-' + i); if (el) el.style.display = el.style.display === 'none' ? '' : 'none'; }
    function stCls(s) { return s === 'normal' ? 'p2-green' : (s === 'low' ? 'p2-orange' : 'p2-red'); }
    function stTxt(s) { return s === 'normal' ? TT('bl_status_n') : (s === 'low' ? TT('bl_status_l') : TT('bl_status_h')); }
    function lvlCls(l) { return l === 'normal' ? 'p2-green' : (l === 'see_doctor' ? 'p2-orange' : (l === 'urgent' ? 'p2-red' : 'p2-dark')); }
    function lvlTxt(l) { return TT('bl_lvl_' + l) || l; }
    (function(){
      fetch('/api/user-info').then(function(r){ return r.json(); }).then(function(ui){
        if (ui.ok && ui.logged_in && ui.profile) {
          var p = ui.profile;
          var bg = document.getElementById('bg');
          var ba = document.getElementById('ba');
          if (bg && p.gender && !bg.value) { bg.value = p.gender; }
          if (ba) {
            var age = p.age;
            if (!age && p.dob) {
              try { var bd = new Date(p.dob); var now = new Date(); age = Math.floor((now - bd) / (365.25 * 24 * 60 * 60 * 1000)); } catch(e) {}
            }
            if (age && !ba.value) ba.value = age;
          }
        }
      }).catch(function(){});
    })();
    </script>
    """
    repl = [
        ("__PT__", json.dumps(t, ensure_ascii=False)),
        ("__BH__", t["blood_h"]), ("__BCBC__", t["blood_cbc"]), ("__BSUB__", t["blood_sub"]),
        ("__BGENDER__", t["blood_gender"]), ("__BAGE__", t["blood_age"]),
        ("__BGENDERPH__", t["blood_gender_ph"]),
        ("__BF__", t["blood_female"]), ("__BM__", t["blood_male"]), ("__BC__", t["blood_child"]),
        ("__BAGEPH__", t["blood_age_ph"]), ("__BHINT__", t["blood_hint"]),
        ("__BHINT2__", t["blood_hint2"]), ("__BALERT__", t["blood_alert"]),
        ("__BDROP__", t["blood_drop"]), ("__BDROPOR__", t["blood_drop_or"]),
        ("__BDROPBTN__", t["blood_drop_btn"]), ("__BDROPNOTE__", t["blood_drop_note"]),
        ("__BBTN__", t["blood_btn"]),
    ]
    for k, v in repl:
        body = body.replace(k, v)
    return _page(_t("title_blood"), body)


# ---------------------------------------------------------------- meds
def meds_page():
    ar=_lang()=="ar"; logged_in=bool(_ss_user_id())
    def tx(a,e): return a if ar else e
    body=r'''
    <style>
    .med-shell{max-width:1050px;margin:0 auto}.med-hero{padding:27px;border:1px solid var(--v2-line);border-radius:24px;background:linear-gradient(135deg,#fff,#f1f9fe);margin-bottom:16px}.med-grid{display:grid;grid-template-columns:1.25fr .75fr;gap:15px}.med-card{background:#fff;border:1px solid var(--v2-line);border-radius:18px;padding:19px;box-shadow:var(--v2-shadow);margin-bottom:14px}.med-title{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}.med-form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.med-form-grid .wide{grid-column:1/-1}.weekdays{display:flex;gap:6px;flex-wrap:wrap}.weekday{border:1px solid var(--v2-line);border-radius:999px;background:#fff;padding:7px 10px;cursor:pointer}.weekday.on{background:var(--v2-sky);border-color:var(--v2-blue);color:var(--v2-blue-dark);font-weight:800}.plan{border:1px solid var(--v2-line);border-radius:16px;padding:15px;margin:10px 0}.plan-head{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}.times{display:flex;gap:7px;flex-wrap:wrap;margin-top:9px}.time-pill{border-radius:999px;background:var(--v2-sky);padding:6px 10px;font-size:12px;font-weight:800;color:var(--v2-blue-dark)}.time-actions{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}.mini-action{border:1px solid var(--v2-line);background:#fff;border-radius:10px;padding:7px 9px;cursor:pointer;font-weight:700}.push-state{display:flex;gap:9px;align-items:center;padding:12px;border-radius:14px;background:var(--v2-bg);border:1px solid var(--v2-line)}.dot{width:9px;height:9px;border-radius:50%;background:#a33a3a}.dot.on{background:#267a52}.setting-row{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:11px 0;border-bottom:1px solid var(--v2-line)}.setting-row:last-child{border-bottom:0}.cal-row{display:grid;grid-template-columns:95px 75px 1fr auto;gap:8px;padding:9px 0;border-bottom:1px solid var(--v2-line);align-items:center}.status-taken{color:#267a52}.status-skipped{color:#a33a3a}.status-snoozed{color:#8a651e}.status-scheduled{color:var(--v2-muted)}.summary-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.summary-box{padding:12px;border:1px solid var(--v2-line);border-radius:14px;background:var(--v2-bg);text-align:center}.summary-box b{display:block;font-size:20px;color:var(--v2-blue-dark)}.privacy-note{padding:13px;border-radius:14px;background:var(--v2-sky);color:var(--v2-blue-dark);font-size:13px;line-height:1.7}.ios-note{padding:11px;border-radius:12px;background:#fff8e7;color:#6f531b;font-size:12px;margin-top:9px}.drug-card{border:1px solid var(--v2-line);border-radius:16px;padding:16px;background:#fff}.drug-sec{margin-top:11px}.drug-name{font-weight:900;color:var(--v2-blue-dark);font-size:18px}.hide{display:none!important}@media(max-width:760px){.med-grid,.med-form-grid{grid-template-columns:1fr}.summary-grid{grid-template-columns:repeat(2,1fr)}.cal-row{grid-template-columns:80px 65px 1fr}.cal-row .cal-med{grid-column:1/-1}.plan-head{flex-direction:column}.med-card{padding:15px}}@media(max-width:430px){.summary-grid{grid-template-columns:1fr 1fr}.cal-row{grid-template-columns:1fr 1fr}.cal-row .cal-med{grid-column:1/-1}}
    .ios-install-card{margin-top:10px;padding:14px;border-radius:16px;border:1px solid #cfe3ef;background:#f2f9fd;text-align:center;color:#163b5c}.ios-install-card .ios-mascot{font-size:34px;display:block;margin-bottom:5px}.ios-install-card b{display:block;margin-bottom:5px}.ios-install-card p{font-size:12px;line-height:1.7;margin:0 0 10px}
    </style>
    <main class="med-shell">
      <section class="med-hero"><h1>💊 __MY_MEDS__</h1><p class="muted">__HERO_SUB__</p></section>
      <section class="med-card">
        <h2>🔎 __INFO_TITLE__</h2><p class="muted">__INFO_SUB__</p>
        <div class="search-box"><span class="sb-ic">🔎</span><input class="inp" id="medInput" placeholder="__SEARCH_PH__" onkeydown="if(event.key==='Enter')searchDrug()"><button class="btn pri sb-btn" onclick="searchDrug()">__SEARCH__</button></div><div id="medRes" style="margin-top:14px"></div>
      </section>
      <section id="loginGate" class="med-card __GATE_HIDE__" style="text-align:center"><h2>🔐 __LOGIN_TITLE__</h2><p class="muted">__LOGIN_TEXT__</p><a class="ss-btn-primary" href="/login?next=/meds">__SIGN_IN__</a></section>
      <div id="privateArea" class="__PRIVATE_HIDE__">
        <div class="med-grid">
          <div>
            <section class="med-card">
              <div class="med-title"><div><h2 style="margin:0">💊 __REMINDERS__</h2><p class="muted" style="margin:5px 0 0">__REM_SUB__</p></div><button class="btn ghost" onclick="resetPlanForm()">＋ __ADD__</button></div>
              <div id="planList" style="margin-top:14px"></div>
            </section>
            <section class="med-card" id="planFormCard">
              <h3 id="planFormTitle">＋ __ADD_MED__</h3>
              <input type="hidden" id="editPlanId">
              <div class="med-form-grid">
                <div><label class="lbl">__MED_NAME__</label><input class="inp" id="remName" maxlength="120"></div>
                <div><label class="lbl">__DOSE__</label><input class="inp" id="pDose" maxlength="120" placeholder="__OPTIONAL__"></div>
                <div class="wide"><label class="lbl">__TIMES__</label><input class="inp" id="remTimes" placeholder="08:00, 20:00"><small class="muted">__MULTI_TIME__</small></div>
                <div><label class="lbl">__FREQ__</label><select class="inp" id="frequency" onchange="toggleWeekdays()"><option value="daily">__DAILY__</option><option value="specific_days">__SPECIFIC__</option></select></div>
                <div><label class="lbl">__TZ__</label><input class="inp" id="planTimezone" readonly></div>
                <div id="weekdaysWrap" class="wide hide"><label class="lbl">__DAYS__</label><div class="weekdays" id="weekdayButtons"></div></div>
                <div><label class="lbl">__START__</label><input class="inp" type="date" id="startDate"></div>
                <div><label class="lbl">__END__</label><input class="inp" type="date" id="endDate"></div>
                <div class="wide"><label class="lbl">__NOTES__</label><textarea class="inp" id="medNotes" rows="2" maxlength="600" placeholder="__OPTIONAL__"></textarea></div>
              </div>
              <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:13px"><button class="ss-btn-primary" onclick="savePlan()">__SAVE__</button><button class="btn ghost" onclick="resetPlanForm()">__CANCEL__</button><span id="planMsg" class="muted"></span></div>
              <div class="privacy-note" style="margin-top:13px">⚠️ __SAFETY__</div>
            </section>
          </div>
          <aside>
            <section class="med-card">
              <h2>🔔 __NOTIF__</h2><div class="push-state"><span id="pushDot" class="dot"></span><div><b id="pushLabel">__CHECKING__</b><small class="muted" id="pushSupport" style="display:block"></small></div></div>
              <button id="enablePushBtn" class="ss-btn-primary" style="width:100%;margin-top:10px" onclick="enablePush()">__ENABLE__</button>
              <button id="disablePushBtn" class="btn ghost hide" style="width:100%;margin-top:8px" onclick="disablePush()">__DISABLE__</button>
              <div id="iosHelp" class="ios-note hide">__IOS_HELP__</div>
              <div id="iosInstallCard" class="ios-install-card hide"><span class="ios-mascot" aria-hidden="true">🐣📱</span><b>__IOS_INSTALL_TITLE__</b><p>__IOS_INSTALL_TEXT__</p><button type="button" class="btn ghost" style="width:100%" onclick="pwaRequestInstall()">__IOS_INSTALL_BUTTON__</button></div>
              <div class="setting-row"><span>__NOTIF_ON__</span><input type="checkbox" id="notifEnabled" checked onchange="saveNotifSettings()"></div>
              <div class="setting-row"><span>__SOUND__</span><input type="checkbox" id="notifSound" checked onchange="saveNotifSettings()"></div>
              <div class="setting-row"><span>__SNOOZE__</span><select id="snoozeMinutes" class="inp" style="max-width:115px" onchange="saveNotifSettings()"><option>5</option><option selected>10</option><option>15</option><option>30</option></select></div>
            </section>
            <section class="med-card"><h2>📊 __SUMMARY__</h2><div id="summaryGrid" class="summary-grid"></div><p class="muted" style="font-size:12px;margin-top:10px">__ADH_NOTE__</p></section>
          </aside>
        </div>
        <section class="med-card"><div class="med-title"><div><h2 style="margin:0">📅 __CALENDAR__</h2><p class="muted" style="margin:5px 0 0">__CAL_SUB__</p></div><select class="inp" id="calDays" style="max-width:150px" onchange="loadCalendar()"><option value="7">7 __DAYS_WORD__</option><option value="30" selected>30 __DAYS_WORD__</option></select></div><div id="calendarList" style="margin-top:12px"></div></section>
      </div>
    </main>
    <script>
    const AR=__AR__, LOGGED_IN=__LOGGED_IN__; let plans=[],editing=null,weekdays=[];
    const W=AR?['الاثنين','الثلاثاء','الأربعاء','الخميس','الجمعة','السبت','الأحد']:['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
    const esc=v=>{const d=document.createElement('div');d.textContent=v==null?'':String(v);return d.innerHTML};
    const timezone=(()=>{try{return Intl.DateTimeFormat().resolvedOptions().timeZone||'Asia/Riyadh'}catch(e){return'Asia/Riyadh'}})();
    function today(){const d=new Date();return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0')}
    function renderWeekdays(){document.getElementById('weekdayButtons').innerHTML=W.map((x,i)=>'<button type="button" class="weekday '+(weekdays.includes(i)?'on':'')+'" onclick="toggleDay('+i+')">'+x+'</button>').join('')}
    function toggleDay(i){weekdays=weekdays.includes(i)?weekdays.filter(x=>x!==i):weekdays.concat([i]);renderWeekdays()}
    function toggleWeekdays(){document.getElementById('weekdaysWrap').classList.toggle('hide',document.getElementById('frequency').value!=='specific_days')}
    function resetPlanForm(){editing=null;weekdays=[];['editPlanId','remName','pDose','endDate','medNotes'].forEach(id=>document.getElementById(id).value='');document.getElementById('remTimes').value='';document.getElementById('frequency').value='daily';document.getElementById('startDate').value=today();document.getElementById('planTimezone').value=timezone;document.getElementById('planFormTitle').textContent='＋ '+(AR?'إضافة دواء':'Add Medication');document.getElementById('planMsg').textContent='';toggleWeekdays();renderWeekdays();document.getElementById('planFormCard').scrollIntoView({behavior:'smooth',block:'start'})}
    function editPlan(id){const p=plans.find(x=>x.id===id);if(!p)return;editing=id;weekdays=(p.days_of_week||[]).slice();document.getElementById('remName').value=p.med_name||'';document.getElementById('pDose').value=p.dose||'';document.getElementById('remTimes').value=(p.times||[]).join(', ');document.getElementById('frequency').value=p.frequency||'daily';document.getElementById('startDate').value=(p.start_date||today()).slice(0,10);document.getElementById('endDate').value=(p.end_date||'').slice(0,10);document.getElementById('medNotes').value=p.notes||'';document.getElementById('planTimezone').value=p.timezone||timezone;document.getElementById('planFormTitle').textContent=AR?'تعديل التذكير':'Edit Reminder';toggleWeekdays();renderWeekdays();document.getElementById('planFormCard').scrollIntoView({behavior:'smooth',block:'start'})}
    async function savePlan(){const name=document.getElementById('remName').value.trim(),times=document.getElementById('remTimes').value.split(/[,،\s]+/).map(x=>x.trim()).filter(Boolean),msg=document.getElementById('planMsg');if(!name||!times.length){msg.textContent=AR?'اسم الدواء ووقت تذكير واحد على الأقل مطلوبان.':'Medication name and at least one reminder time are required.';return}const payload={med_name:name,dose:document.getElementById('pDose').value.trim(),times,frequency:document.getElementById('frequency').value,days_of_week:weekdays,start_date:document.getElementById('startDate').value||today(),end_date:document.getElementById('endDate').value||null,notes:document.getElementById('medNotes').value.trim(),timezone,notifications_enabled:true};const url=editing?'/api/meds/plan/'+editing:'/api/meds/plan',method=editing?'PUT':'POST';const r=await fetch(url,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}),d=await r.json();if(!r.ok||!d.ok){msg.textContent=AR?'تعذر حفظ التذكير.':'Unable to save reminder.';return}msg.textContent='✓ '+(AR?'تم الحفظ':'Saved');await loadPlans();await loadCalendar();setTimeout(resetPlanForm,500)}
    async function loadPlans(){if(!LOGGED_IN)return;const r=await fetch('/api/meds/plan'),d=await r.json();plans=(d.plans||[]).filter(p=>p.active);const box=document.getElementById('planList');if(!plans.length){box.innerHTML='<p class="muted">'+(AR?'لا توجد تذكيرات دوائية بعد.':'No medication reminders yet.')+'</p>';return}box.innerHTML=plans.map(p=>'<article class="plan"><div class="plan-head"><div><b>💊 '+esc(p.med_name)+'</b>'+(p.dose?'<small class="muted" style="display:block">'+esc(p.dose)+'</small>':'')+'<small class="muted">'+esc(p.frequency==='specific_days'?(AR?'أيام محددة':'Specific days'):(AR?'يوميًا':'Daily'))+' · '+esc(p.timezone||timezone)+'</small></div><div><button class="mini-action" onclick="editPlan('+p.id+')">✏️ '+(AR?'تعديل':'Edit')+'</button> <button class="mini-action" onclick="deletePlan('+p.id+')">🗑️ '+(AR?'حذف':'Delete')+'</button></div></div><div class="times">'+(p.times||[]).map(tm=>'<span class="time-pill">⏰ '+esc(tm)+'</span>').join('')+'</div><div class="time-actions">'+(p.times||[]).map(tm=>'<span><button class="mini-action" onclick="mark('+p.id+',\''+tm+'\',\'taken\')">✓ '+(AR?'تم أخذه':'Taken')+'</button> <button class="mini-action" onclick="snooze('+p.id+',\''+tm+'\')">😴 '+(AR?'غفوة':'Snooze')+'</button> <button class="mini-action" onclick="mark('+p.id+',\''+tm+'\',\'skipped\')">— '+(AR?'تخطي':'Skip')+'</button></span>').join('')+'</div></article>').join('')}
    async function deletePlan(id){if(!confirm(AR?'حذف هذا التذكير؟':'Delete this reminder?'))return;await fetch('/api/meds/plan/'+id,{method:'DELETE'});loadPlans();loadCalendar()}
    async function mark(id,tm,status){await fetch('/api/meds/log',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plan_id:id,time:tm,status,date:today()})});loadCalendar()}
    async function snooze(id,tm){const mins=Number(document.getElementById('snoozeMinutes').value||10);await fetch('/api/meds/snooze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plan_id:id,time:tm,date:today(),minutes:mins})});loadCalendar()}
    async function loadCalendar(){if(!LOGGED_IN)return;const d=await fetch('/api/meds/calendar?days='+document.getElementById('calDays').value).then(r=>r.json());const sm=d.summary||{},g=document.getElementById('summaryGrid');g.innerHTML=[[sm.scheduled||0,AR?'مجدول':'Scheduled'],[sm.taken||0,AR?'تم أخذه':'Taken'],[sm.skipped||0,AR?'تم تخطيه':'Skipped'],[(sm.adherence||0)+'%',AR?'استجابة للتذكيرات':'Reminder response']].map(x=>'<div class="summary-box"><b>'+x[0]+'</b><span>'+x[1]+'</span></div>').join('');const e=(d.entries||[]).slice().reverse(),box=document.getElementById('calendarList');if(!e.length){box.innerHTML='<p class="muted">'+(AR?'لا يوجد سجل تذكيرات بعد.':'No reminder history yet.')+'</p>';return}const st={taken:AR?'✓ تم أخذه':'✓ Taken',skipped:AR?'— تم تخطيه':'— Skipped',snoozed:AR?'😴 غفوة':'😴 Snoozed',deferred:AR?'😴 غفوة':'😴 Snoozed',scheduled:AR?'○ مجدول':'○ Scheduled'};box.innerHTML=e.slice(0,120).map(x=>'<div class="cal-row"><span>'+esc(x.date)+'</span><b>'+esc(x.time)+'</b><span class="cal-med">'+esc(x.med_name)+'</span><span class="status-'+esc(x.status)+'">'+esc(st[x.status]||x.status)+'</span></div>').join('')}
    function urlB64ToUint8Array(base64String){const padding='='.repeat((4-base64String.length%4)%4),base64=(base64String+padding).replace(/-/g,'+').replace(/_/g,'/'),raw=atob(base64);return Uint8Array.from([...raw].map(c=>c.charCodeAt(0)))}
    function pushSupported(){return location.protocol==='https:'&&'serviceWorker'in navigator&&'PushManager'in window&&'Notification'in window}
    async function refreshPush(){if(!LOGGED_IN)return;const dot=document.getElementById('pushDot'),label=document.getElementById('pushLabel'),support=document.getElementById('pushSupport'),on=document.getElementById('enablePushBtn'),off=document.getElementById('disablePushBtn'),isiOS=/iPad|iPhone|iPod/.test(navigator.userAgent),standalone=window.matchMedia('(display-mode: standalone)').matches||window.navigator.standalone===true;document.getElementById('iosInstallCard').classList.toggle('hide',!(isiOS&&!standalone));document.getElementById('iosHelp').classList.toggle('hide',!isiOS);if(!pushSupported()){label.textContent=AR?'الإشعارات غير مدعومة على هذا الجهاز/المتصفح.':"Push notifications aren't supported on this device/browser.";support.textContent=AR?'يتطلب Web Push اتصال HTTPS ومتصفحًا يدعمه.':'Web Push requires HTTPS and browser support.';on.classList.add('hide');return}const d=await fetch('/api/push/status').then(r=>r.json());const perm=Notification.permission;dot.classList.toggle('on',d.subscribed&&perm==='granted');label.textContent=d.subscribed&&perm==='granted'?(AR?'الإشعارات مفعلة':'Notifications ON'):(AR?'الإشعارات متوقفة':'Notifications OFF');support.textContent=!d.configured?(AR?'خدمة Push لم يتم إعداد مفاتيحها على الخادم بعد.':'Push keys are not configured on the server yet.'):(perm==='denied'?(AR?'الإذن مرفوض. فعّليه من إعدادات المتصفح.':'Permission is blocked. Enable it in browser settings.'):'');on.classList.toggle('hide',d.subscribed&&perm==='granted');off.classList.toggle('hide',!(d.subscribed&&perm==='granted'));const s=d.settings||{};document.getElementById('notifEnabled').checked=s.enabled!==false;document.getElementById('notifSound').checked=s.sound!==false;document.getElementById('snoozeMinutes').value=String(s.snooze_minutes||10)}
    async function enablePush(){if(!pushSupported())return;const cfg=await fetch('/api/push/vapid-public').then(r=>r.json());if(!cfg.configured||!cfg.public_key){alert(AR?'خدمة Push غير مهيأة على الخادم.':'Push is not configured on the server.');return}const perm=await Notification.requestPermission();if(perm!=='granted'){refreshPush();return}const reg=await navigator.serviceWorker.register('/service-worker.js');const sub=await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:urlB64ToUint8Array(cfg.public_key)});const r=await fetch('/api/push/subscribe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({subscription:sub.toJSON(),timezone,lang:AR?'ar':'en'})});if(!r.ok){alert(AR?'تعذر تفعيل الإشعارات.':'Unable to enable notifications.');return}await saveNotifSettings();refreshPush()}
    async function disablePush(){try{const reg=await navigator.serviceWorker.ready,sub=await reg.pushManager.getSubscription();if(sub){await fetch('/api/push/unsubscribe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({endpoint:sub.endpoint})});await sub.unsubscribe()}}catch(e){}document.getElementById('notifEnabled').checked=false;await saveNotifSettings();refreshPush()}
    async function saveNotifSettings(){if(!LOGGED_IN)return;await fetch('/api/meds/settings',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:document.getElementById('notifEnabled').checked,sound:document.getElementById('notifSound').checked,snooze_minutes:Number(document.getElementById('snoozeMinutes').value||10),timezone})})}
    async function searchDrug(){const name=document.getElementById('medInput').value.trim(),box=document.getElementById('medRes');if(!name)return;box.innerHTML='<div class="med-loading"><span class="spin"></span>'+(AR?'جاري تحميل المعلومات…':'Loading information…')+'</div>';try{const r=await fetch('/api/drug?name='+encodeURIComponent(name));if(!r.ok)throw new Error('http');const d=await r.json();if(!d.ok)throw new Error('api');if(!d.result){box.innerHTML='<p class="muted">'+(AR?'لم يتم العثور على معلومات موثوقة لهذا البحث.':'No trusted information was found for this search.')+'</p>';return}box.innerHTML='<article class="drug-card"><div class="drug-name">💊 '+esc(d.name)+'</div><div class="drug-sec"><b>'+(AR?'معلومات عامة':'General information')+'</b><p>'+esc(d.uses||'—')+'</p></div><div class="drug-sec"><b>'+(AR?'تنبيهات مهمة':'Important warnings')+'</b><p>'+esc(d.warning||'—')+'</p></div><div class="drug-sec"><b>'+(AR?'التداخلات المتوفرة':'Available interaction information')+'</b><p>'+esc(d.interactions||'—')+'</p></div><p class="privacy-note">'+(AR?'هذه المعلومات توعوية فقط. لا تبدأ أو توقف أو تغيّر دواءً أو جرعةً بناءً على هذه الصفحة.':'This is awareness information only. Do not start, stop, or change a medication or dose based on this page.')+'</p></article>'}catch(e){box.innerHTML='<div class="med-error">'+(AR?'حدث خطأ. تعذر تحميل المعلومات حاليًا. حاول مرة أخرى.':'Something went wrong. We could not load this information right now. Please try again.')+'<br><button class="med-retry" onclick="searchDrug()">'+(AR?'إعادة المحاولة':'Try Again')+'</button></div>'}}
    if(LOGGED_IN){document.getElementById('startDate').value=today();document.getElementById('planTimezone').value=timezone;renderWeekdays();loadPlans();loadCalendar();refreshPush()}
    </script>
    '''
    repl={
      '__MY_MEDS__':tx('أدويتي وتذكيراتي','My Medications & Reminders'),'__HERO_SUB__':tx('نظّم تذكيرات الأدوية التي أدخلتها بنفسك. لا يصف SymptoSense دواءً ولا يقترح جرعة.','Organize reminders for medications you enter yourself. SymptoSense does not prescribe medication or suggest doses.'),
      '__INFO_TITLE__':tx('معلومات الدواء','Medication Information'),'__INFO_SUB__':tx('اعرض المعلومات المتاحة من المصادر الموجودة في النظام فقط.','View only the verified information currently available in the system.'),'__SEARCH_PH__':tx('اكتب اسم الدواء','Enter medication name'),'__SEARCH__':tx('بحث','Search'),
      '__LOGIN_TITLE__':tx('سجّل الدخول لاستخدام التذكيرات','Sign in to use reminders'),'__LOGIN_TEXT__':tx('البحث متاح للجميع، أما التذكيرات والسجل فخاصة بحسابك.','Search is public; reminders and history are private to your account.'),'__SIGN_IN__':tx('تسجيل الدخول','Sign in'),
      '__REMINDERS__':tx('تذكيرات الأدوية','Medication Reminders'),'__REM_SUB__':tx('أنت من تحدد الاسم والوقت والجرعة الاختيارية.','You choose the name, time, and optional dose.'),'__ADD__':tx('إضافة','Add'),'__ADD_MED__':tx('إضافة دواء','Add Medication'),'__MED_NAME__':tx('اسم الدواء','Medication Name'),'__DOSE__':tx('الجرعة (اختيارية)','Dose (Optional)'),'__OPTIONAL__':tx('اختياري','Optional'),'__TIMES__':tx('أوقات التذكير','Reminder Times'),'__MULTI_TIME__':tx('يمكن إضافة أكثر من وقت، مثال: 08:00, 20:00','Multiple times are supported, e.g. 08:00, 20:00'),'__FREQ__':tx('التكرار','Frequency'),'__DAILY__':tx('يوميًا','Daily'),'__SPECIFIC__':tx('أيام محددة','Specific Days'),'__TZ__':tx('المنطقة الزمنية','Timezone'),'__DAYS__':tx('الأيام','Days'),'__START__':tx('تاريخ البداية','Start Date'),'__END__':tx('تاريخ النهاية (اختياري)','End Date (Optional)'),'__NOTES__':tx('ملاحظات (اختيارية)','Notes (Optional)'),'__SAVE__':tx('حفظ التذكير','Save Reminder'),'__CANCEL__':tx('إلغاء','Cancel'),'__SAFETY__':tx('هذه الميزة للتذكير فقط. لا تستخدمها لاتخاذ قرار ببدء دواء أو إيقافه أو تغيير الجرعة.','This feature is for reminders only. Do not use it to decide to start, stop, or change a medication or dose.'),
      '__NOTIF__':tx('إشعارات الدواء','Medication Notifications'),'__CHECKING__':tx('جاري التحقق…','Checking…'),'__ENABLE__':tx('تفعيل الإشعارات','Enable Notifications'),'__DISABLE__':tx('إيقاف الإشعارات','Disable Notifications'),'__IOS_HELP__':tx('على iPhone/iPad، Web Push متاح لتطبيقات الويب المضافة إلى الشاشة الرئيسية على الإصدارات المدعومة. أضف SymptoSense إلى Home Screen ثم فعّل الإشعارات من داخل التطبيق.','On supported iPhone/iPad versions, Web Push is available for web apps added to the Home Screen. Add SymptoSense to Home Screen, then enable notifications from the app.'),'__IOS_INSTALL_TITLE__':tx('آيفونك يحتاج خطوة صغيرة 🐣','Your iPhone needs one small step 🐣'),'__IOS_INSTALL_TEXT__':tx('أضيفي SymptoSense إلى الشاشة الرئيسية، ثم افتحيه من الأيقونة وفعّلي الإشعارات حتى تصلك تذكيرات الدواء بعد إغلاق الصفحة.','Add SymptoSense to your Home Screen, open it from the icon, then enable notifications to receive medication reminders after closing the page.'),'__IOS_INSTALL_BUTTON__':tx('طريقة الإضافة للشاشة الرئيسية','How to add to Home Screen'),'__NOTIF_ON__':tx('Medication Notifications','Medication Notifications'),'__SOUND__':tx('صوت التذكير','Reminder Sound'),'__SNOOZE__':tx('مدة الغفوة (دقيقة)','Snooze (minutes)'),
      '__SUMMARY__':tx('ملخص التذكيرات','Reminder Summary'),'__ADH_NOTE__':tx('النسبة تعكس استجابتك للتذكيرات فقط، وليست تقييمًا طبيًا للالتزام بالعلاج.','This percentage reflects reminder responses only; it is not a medical assessment of treatment adherence.'),'__CALENDAR__':tx('سجل التذكيرات','Reminder Calendar'),'__CAL_SUB__':tx('✓ تم أخذه · ○ مجدول · — تم تخطيه','✓ Taken · ○ Scheduled · — Skipped'),'__DAYS_WORD__':tx('أيام','days'),
      '__AR__':'true' if ar else 'false','__LOGGED_IN__':'true' if logged_in else 'false','__GATE_HIDE__':'hide' if logged_in else '','__PRIVATE_HIDE__':'' if logged_in else 'hide'
    }
    for k,v in repl.items(): body=body.replace(k,str(v))
    return _page(tx('الأدوية والتذكيرات','Medications & Reminders'), body, extra_css=MEDS_CSS)


@app.route("/service-worker.js")
def service_worker_file():
    response=send_from_directory(BASE_DIR,"service-worker.js",mimetype="application/javascript")
    response.headers["Cache-Control"]="no-cache, no-store, must-revalidate"
    response.headers["Service-Worker-Allowed"]="/"
    return response


@app.route("/manifest.webmanifest")
def manifest_file():
    return send_from_directory(BASE_DIR,"manifest.webmanifest",mimetype="application/manifest+json")


@app.route("/brand-icon.svg")
def brand_icon():
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 192 192" role="img" aria-label="SymptoSense">
    <rect width="192" height="192" rx="46" fill="#287FC1"/>
    <path d="M39 99h28l12-27 18 52 14-31 10 18h32" fill="none" stroke="#fff" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>'''
    response = Response(svg, mimetype="image/svg+xml")
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@app.route("/icons/<path:filename>")
def pwa_icon_file(filename):
    response = send_from_directory(os.path.join(BASE_DIR,"icons"),filename)
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
.med-retry{margin-top:10px;border:0;border-radius:10px;background:#1976d2;color:#fff;padding:9px 14px;font:inherit;font-weight:800;cursor:pointer}
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
.fam-stat b { color: #1976D2; }
.fam-form { background: #FFFFFF; border: 1px solid #DCEBFA; border-radius: 18px; padding: 20px; margin-top: 16px; }
.fam-rel-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
.fam-chip { padding: 8px 14px; border-radius: 999px; border: 1.5px solid #1976D2; background: #FFFFFF; color: #1976D2; font-size: 13px; font-weight: 700; cursor: pointer; }
.fam-chip.sel { background: #1976D2; color: #FFFFFF; }
.tl-item { display: flex; gap: 12px; align-items: flex-start; padding: 10px 0; border-bottom: 1px dashed #DCEBFA; font-size: 14px; }
.tl-dot { width: 34px; height: 34px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 17px; background: #EAF4FF; flex: 0 0 34px; }
.tl-date { color: #94A3B8; font-size: 12px; }
.tl-type { color: #40566F; }
.tl-type b { color: #123B70; }
.mplan-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; background: #F5F9FF; border: 1px solid #DCEBFA; border-radius: 12px; padding: 10px 12px; margin-top: 8px; }
.mplan-time { font-weight: 800; color: #1976D2; min-width: 52px; }
.mplan-name { font-weight: 700; color: #40566F; }
.mplan-status { display: flex; gap: 6px; flex-wrap: wrap; }
.mini-btn { border: 1px solid #DCEBFA; background: #FFFFFF; color: #40566F; border-radius: 8px; padding: 5px 10px; font-size: 12px; font-weight: 700; cursor: pointer; }
.mini-btn.tk { border-color: #86EFAC; color: #166534; }
.mini-btn.sk { border-color: #FECACA; color: #991B1B; }
.mini-btn.lt { border-color: #FDE68A; color: #92400E; }
.mini-btn.done { opacity: .55; pointer-events: none; }
.adh-bar { height: 8px; background: #DCEBFA; border-radius: 8px; overflow: hidden; margin-top: 6px; }
.adh-fill { height: 100%; background: #1976D2; border-radius: 8px; }
"""


def _fam_emoji(relation):
    return {
        "me": "👤", "mother": "👩", "father": "👨", "daughter": "👧",
        "son": "👦", "grandparent": "👵", "other": "🧑",
    }.get(relation, "🧑")


def family_page():
    ar = _lang() == "ar"
    t = CT["en" if _lang() == "en" else "ar"]
    body = """
    <div class="card">
      <h2>__H__</h2>
      <p class="muted">__SUB__</p>
      <div class="muted" style="font-size:13px;margin-top:6px;">__INTRO__</div>
      <div class="fam-grid" id="famGrid"><div class="muted">...</div></div>
    </div>
    <div class="fam-form">
      <h3 style="color:#123B70;">__ADD__</h3>
      <label class="lbl">__WHO__</label>
      <div class="fam-rel-chips" id="relChips"></div>
      <div class="grid2" style="margin-top:6px;">
        <div><label class="lbl">__NAME__</label><input class="inp" id="fName" placeholder="__NAMEPH__"></div>
        <div><label class="lbl">__AGE__</label><input class="inp" id="fAge" placeholder="__AGEPH__"></div>
      </div>
      <div class="grid2">
        <div><label class="lbl">__GEN__</label>
          <select class="inp" id="fGender"><option value="f">__GF__</option><option value="m">__GM__</option></select>
        </div>
        <div><label class="lbl">__COND__</label><input class="inp" id="fCond" placeholder="..."></div>
      </div>
      <div class="grid2">
        <div><label class="lbl">__MEDS__</label><input class="inp" id="fMeds" placeholder="..."></div>
        <div><label class="lbl">__ALL__</label><input class="inp" id="fAll" placeholder="..."></div>
      </div>
      <div style="margin-top:12px;display:flex;gap:10px;flex-wrap:wrap;align-items:center;">
        <button class="btn pri" onclick="saveFam()">__SAVE__</button>
        <span id="famMsg" style="font-weight:700;color:#1976D2;"></span>
      </div>
    </div>
    <script>
    const T = __PT__;
    const LANG = "__LANG__";
    function TT(k) { return T[k] || k; }
    function esc(s) { const div=document.createElement('div'); div.textContent=s||''; return div.innerHTML; }
    const RELS = [
      ['me', TT('fam_rel_me')], ['mother', TT('fam_rel_mother')], ['father', TT('fam_rel_father')],
      ['daughter', TT('fam_rel_daughter')], ['son', TT('fam_rel_son')],
      ['grandparent', TT('fam_rel_grandparent')], ['other', TT('fam_rel_other')]
    ];
    const EMO = {'me':'👤','mother':'👩','father':'👨','daughter':'👧','son':'👦','grandparent':'👵','other':'🧑'};
    let rel = 'other';
    function renderChips() {
      document.getElementById('relChips').innerHTML = RELS.map(r =>
        '<span class="fam-chip' + (r[0]===rel?' sel':'') + '" onclick="pickRel(\\'' + r[0] + '\\')">' + r[1] + '</span>').join('');
    }
    function pickRel(r) { rel = r; renderChips(); }
    function loadFam() {
      fetch('/api/family').then(r=>r.json()).then(d=>{
        if (d.error === 'login_required') { location.href = d.login_url || '/login?next=/family'; return; }
        const box = document.getElementById('famGrid');
        if (!d.ok || !d.members.length) { box.innerHTML = '<div class="muted">' + TT('fam_empty') + '</div>'; return; }
        let h = '<div class="fam-card" onclick="location.href=\\'/profile\\'"><div class="fam-av">👤</div><div class="fam-name">' + TT('me_short') + '</div><div class="fam-meta">' + TT('fam_rel_me') + '</div></div>';
        d.members.forEach(m => {
          const adh = m.adherence !== null && m.adherence !== undefined ? m.adherence + '%' : TT('fam_no_adherence');
          h += '<div class="fam-card" onclick="location.href=\\'/family/' + m.id + '\\'">' +
            '<div class="fam-av">' + EMO[m.relation] + '</div>' +
            '<div class="fam-name">' + esc(m.name) + '</div>' +
            '<div class="fam-meta">' + (m.age ? m.age + ' ' + TT('fam_years') : '') + (m.gender ? ' • ' + (m.gender==='f'?TT('fam_g_f'):TT('fam_g_m')) : '') + '</div>' +
            '<div class="fam-stat"><span>🩺 <b>' + m.records_count + '</b></span><span>💊 <b>' + adh + '</b></span></div>' +
            '</div>';
        });
        box.innerHTML = h;
      }).catch(()=>{ document.getElementById('famGrid').innerHTML = '<div class="warn">' + TT('fam_err') + '</div>'; });
    }
    function saveFam() {
      const name = document.getElementById('fName').value.trim();
      const msg = document.getElementById('famMsg');
      if (!name) { msg.textContent = TT('fam_name'); msg.style.color = '#B91C1C'; return; }
      fetch('/api/family', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({
        relation: rel, name: name,
        age: document.getElementById('fAge').value.trim(),
        gender: document.getElementById('fGender').value,
        conditions: document.getElementById('fCond').value.trim(),
        medications: document.getElementById('fMeds').value.trim(),
        allergies: document.getElementById('fAll').value.trim()
      })}).then(r=>r.json()).then(d=>{
        if (d.error === 'login_required') { location.href = d.login_url || '/login?next=/family'; return; }
        if (!d.ok) { msg.textContent = TT('fam_err') + (d.error||''); msg.style.color='#B91C1C'; return; }
        msg.textContent = TT('fam_saved'); msg.style.color = '#1976D2';
        ['fName','fAge','fCond','fMeds','fAll'].forEach(i=>document.getElementById(i).value='');
        loadFam();
      });
    }
    renderChips();
    loadFam();
    </script>
    """
    for k, v in [
        ("__PT__", json.dumps(t, ensure_ascii=False)),
        ("__LANG__", "en" if _lang() == "en" else "ar"),
        ("__H__", t["fam_h"]), ("__SUB__", t["fam_sub"]), ("__INTRO__", t["fam_hub_intro"]),
        ("__ADD__", t["fam_add"]), ("__WHO__", t["fam_who"]),
        ("__NAME__", t["fam_name"]), ("__NAMEPH__", t["fam_name_ph"]),
        ("__AGE__", t["fam_age"]), ("__AGEPH__", t["fam_age_ph"]),
        ("__GEN__", t["fam_gender"]), ("__GF__", t["fam_g_f"]), ("__GM__", t["fam_g_m"]),
        ("__COND__", t["fam_conditions"]), ("__MEDS__", t["fam_meds"]),
        ("__ALL__", t["fam_allergies"]), ("__SAVE__", t["fam_save"]),
    ]:
        body = body.replace(k, v)
    return _page(_t("title_home"), body, extra_css=FAM_CSS)


def family_detail_page(mid):
    ar = _lang() == "ar"
    t = CT["en" if _lang() == "en" else "ar"]
    uid = _data_user_id()
    member = db.get_member(uid, mid) if mid else None
    if not member:
        body = ('<div class="card" style="max-width:520px;margin:40px auto;text-align:center;">'
                '<h2>%s</h2><p style="margin-top:10px;"><a class="btn" href="/family">%s</a></p></div>'
                % (t["fam_empty"], t["fam_back"]))
        return _page(_t("title_home"), body)
    last_rec = None
    try:
        recs = db.get_records(uid, limit=1, member_id=mid)
        if recs:
            last_rec = recs[0]
    except Exception:
        pass
    last_blood = None
    try:
        bts = db.get_blood_tests(uid, limit=1, member_id=mid)
        if bts:
            last_blood = bts[0]
    except Exception:
        pass
    adh = db.med_adherence(uid, member_id=mid)["percent"]
    plans = db.list_med_plans(uid, member_id=mid)
    gender_txt = (t["fam_g_f"] if member["gender"] == "f" else t["fam_g_m"]) if member["gender"] else ""
    ana_txt = (", ".join(last_rec["symptoms"][:3]) + " • " + last_rec["timestamp"][:10]) if last_rec else t["fam_no_analysis"]
    cbc_txt = (last_blood["data"].get("level", "") + " • " + (last_blood["timestamp"] or "")[:10]) if last_blood else t["fam_no_cbc"]
    meds_txt = "; ".join(p["med_name"] for p in plans[:4]) if plans else t["fam_no_meds"]
    body = """
    <div class="card">
      <div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;justify-content:space-between;">
        <div style="display:flex;align-items:center;gap:14px;">
          <div class="fam-av" style="width:64px;height:64px;font-size:32px;margin:0;">__AV__</div>
          <div>
            <h2 style="color:#123B70;">__NAME__</h2>
            <div class="muted">__META__</div>
          </div>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          <a class="btn small" href="/chat?m=__MID__">__ANA__</a>
          <a class="btn small" href="/blood?m=__MID__">__CBC__</a>
          <a class="btn small ghost" href="/family">__BACK__</a>
        </div>
      </div>
      <div class="grid2" style="margin-top:16px;">
        <div class="card" style="background:#F5F9FF;">
          <b>__LASTANA__</b>
          <div style="margin-top:6px;font-size:14px;color:#40566F;">__ANA_TXT__</div>
        </div>
        <div class="card" style="background:#F5F9FF;">
          <b>__LASTCBC__</b>
          <div style="margin-top:6px;font-size:14px;color:#40566F;">__CBC_TXT__</div>
        </div>
      </div>
      <div class="card" style="background:#F5F9FF;margin-top:12px;">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
          <b>__ADH__</b>
          <b style="color:#1976D2;">__ADH_PCT__</b>
        </div>
        <div class="adh-bar"><div class="adh-fill" style="width:__ADH_W__%;"></div></div>
      </div>
      <div style="margin-top:10px;font-size:13px;color:#40566F;">
        <b>__MEDSREG__:</b> <span id="medsTxt">__MEDS_TXT__</span>
      </div>
    </div>

    <div class="card" style="margin-top:14px;">
      <h3 style="color:#123B70;">__PLANT__</h3>
      <p class="muted">__PLANSUB__</p>
      <div id="planList" style="margin-top:12px;"><div class="muted">...</div></div>
      <div style="margin-top:16px;border-top:1px dashed #DCEBFA;padding-top:14px;">
        <div class="grid2">
          <div><label class="lbl">__PNAME__</label><input class="inp" id="pName" placeholder="__PNAMEPH__"></div>
          <div><label class="lbl">__PDOSE__</label><input class="inp" id="pDose" placeholder="500mg"></div>
        </div>
        <div class="grid2">
          <div><label class="lbl">__PTIMES__</label><input class="inp" id="pTimes" placeholder="__PTIMESPH__"></div>
          <div><label class="lbl">__PDAYS__</label><input class="inp" id="pDays" type="number" min="1" placeholder="7"></div>
        </div>
        <div style="margin-top:12px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
          <button class="btn pri" onclick="savePlan()">__PSAVE__</button>
          <span id="planMsg" style="font-weight:700;color:#1976D2;"></span>
        </div>
      </div>
    </div>

    <div class="card" style="margin-top:14px;">
      <h3 style="color:#123B70;">__TL__</h3>
      <div id="timeline" style="margin-top:10px;"><div class="muted">...</div></div>
    </div>
    <script>
    const T = __PT__;
    const LANG = "__LANG__";
    const MID = __MID__;
    const MEMNAME = "__MEMNAME__";
    function TT(k) { return T[k] || k; }
    function esc(s) { const div=document.createElement('div'); div.textContent=s||''; return div.innerHTML; }
    function todayStr() { const d=new Date(); return d.getFullYear()+'-'+('0'+(d.getMonth()+1)).slice(-2)+'-'+('0'+d.getDate()).slice(-2); }
    function loadPlans() {
      fetch('/api/meds/today').then(r=>r.json()).then(d=>{
        const box = document.getElementById('planList');
        const mine = (d.plans||[]).filter(p => p.member_id === MID);
        if (!mine.length) { box.innerHTML = '<div class="muted">' + TT('fam_no_meds') + '</div>'; return; }
        let h = '';
        mine.forEach(p => {
          h += '<div class="rc-title">' + esc(p.med_name) + (p.dose ? ' <span class="muted">(' + esc(p.dose) + ')</span>' : '') + '</div>';
          p.times.forEach(tm => {
            const st = p.status[tm] || '';
            let btn = '';
            if (st) { btn = '<span class="mini-btn done">' + TT('fam_today_logged') + '</span>'; }
            else {
              btn = '<span class="mini-btn tk" onclick="logMed(' + p.id + ',\\'' + tm + '\\',\\'taken\\')">' + TT('fam_take') + '</span>' +
                    '<span class="mini-btn sk" onclick="logMed(' + p.id + ',\\'' + tm + '\\',\\'skipped\\')">' + TT('fam_skip') + '</span>' +
                    '<span class="mini-btn lt" onclick="logMed(' + p.id + ',\\'' + tm + '\\',\\'deferred\\')">' + TT('fam_later') + '</span>';
            }
            h += '<div class="mplan-row"><span class="mplan-time">🕐 ' + tm + '</span><span class="mplan-name">' + (st?('💊 '+esc(st)):'') + '</span><span class="mplan-status">' + btn + '</span></div>';
          });
        });
        box.innerHTML = h;
      }).catch(()=>{});
    }
    function logMed(pid, tm, st) {
      fetch('/api/meds/log', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({
        plan_id: pid, time: tm, status: st, member_id: MID, date: todayStr()
      })}).then(r=>r.json()).then(()=>{ loadPlans(); refreshAdh(); });
    }
    function refreshAdh() {
      fetch('/api/meds/weekly?member=' + MID).then(r=>r.json()).then(d=>{
        if (d.ok && d.percent !== null && d.percent !== undefined) {
          document.querySelector('.adh-fill').style.width = d.percent + '%';
          const el = document.querySelector('.adh-bar').previousElementSibling;
          el.querySelector('b').textContent = TT('fam_week_adh').replace('%s', d.percent);
        }
      }).catch(()=>{});
    }
    function savePlan() {
      const name = document.getElementById('pName').value.trim();
      const tval = document.getElementById('pTimes').value;
      const msg = document.getElementById('planMsg');
      const times = tval.split(/[,،\\s]+/).filter(Boolean);
      if (!name || !times.length) { msg.textContent = TT('fam_name'); msg.style.color='#B91C1C'; return; }
      fetch('/api/meds/plan', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({
        member_id: MID, med_name: name, dose: document.getElementById('pDose').value.trim(),
        times: times, days: document.getElementById('pDays').value || null
      })}).then(r=>r.json()).then(d=>{
        if (!d.ok) { msg.textContent = TT('fam_err') + (d.error||''); msg.style.color='#B91C1C'; return; }
        msg.textContent = TT('fam_saved'); msg.style.color = '#1976D2';
        document.getElementById('pName').value=''; document.getElementById('pDose').value=''; document.getElementById('pTimes').value=''; document.getElementById('pDays').value='';
        loadPlans();
        if (('Notification' in window) && Notification.permission === 'default') Notification.requestPermission();
      });
    }
    function loadTimeline() {
      fetch('/api/timeline?member=' + MID + '&days=30').then(r=>r.json()).then(d=>{
        const box = document.getElementById('timeline');
        if (!d.ok || !d.events.length) { box.innerHTML = '<div class="muted">' + TT('fam_no_events') + '</div>'; return; }
        const EMO = {'analysis':'🩺','blood':'🩸','med':'💊'};
        let h = '';
        d.events.forEach(e => {
          const title = LANG === 'en' ? e.en_title : e.title;
          h += '<div class="tl-item"><div class="tl-dot">' + (EMO[e.type]||'📋') + '</div>' +
               '<div><div class="tl-date">' + e.date + '</div><div class="tl-type">' + esc(title) + (e.detail?' — <span class="muted">'+esc(e.detail)+'</span>':'') + '</div></div></div>';
        });
        box.innerHTML = h;
      }).catch(()=>{});
    }
    loadPlans();
    loadTimeline();
    </script>
    """
    for k, v in [
        ("__PT__", json.dumps(t, ensure_ascii=False)),
        ("__LANG__", "en" if _lang() == "en" else "ar"),
        ("__MID__", str(mid)),
        ("__MEMNAME__", member["name"]),
        ("__AV__", _fam_emoji(member.get("relation", "other"))),
        ("__NAME__", member["name"]),
        ("__META__", (member.get("age") or "?") + " " + t["fam_years"] + (" • " + gender_txt if gender_txt else "")),
        ("__ANA__", t["fam_add_analysis"]), ("__CBC__", t["fam_add_cbc"]), ("__BACK__", t["fam_back"]),
        ("__LASTANA__", t["fam_last_analysis"]), ("__ANA_TXT__", ana_txt),
        ("__LASTCBC__", t["fam_last_cbc"]), ("__CBC_TXT__", cbc_txt),
        ("__ADH__", t["fam_week_adh"]), ("__ADH_PCT__", (str(adh) + "%") if adh is not None else t["fam_no_adherence"]),
        ("__ADH_W__", str(int(adh)) if adh is not None else "0"),
        ("__MEDSREG__", t["fam_meds_reg"]), ("__MEDS_TXT__", meds_txt),
        ("__PLANT__", t["fam_plan_title"]), ("__PLANSUB__", t["fam_plan_sub"] % member["name"]),
        ("__PNAME__", t["fam_plan_name"]), ("__PNAMEPH__", t["fam_plan_name_ph"]),
        ("__PDOSE__", t["fam_plan_dose"]), ("__PTIMES__", t["fam_plan_times"]),
        ("__PTIMESPH__", t["fam_plan_times_ph"]), ("__PDAYS__", t["fam_plan_days"]),
        ("__PSAVE__", t["fam_plan_save"]), ("__TL__", t["fam_timeline"]),
    ]:
        body = body.replace(k, v)
    return _page(_t("title_home"), body, extra_css=FAM_CSS)


# ---------------------------------------------------------------- health search
SEARCH_CSS = """
.sea-wrap { max-width: 720px; margin: 0 auto; }
.sea-box { display: flex; align-items: center; gap: 10px; background: #FFFFFF; border: 2px solid #1976D2; border-radius: 999px; padding: 7px 8px 7px 18px; box-shadow: 0 10px 30px rgba(25,118,210,.14); transition: box-shadow .25s ease, border-color .25s ease; }
.sea-box:focus-within { box-shadow: 0 14px 38px rgba(25,118,210,.22); border-color: #123B70; }
.sea-box .sea-ic { font-size: 20px; color: #1976D2; }
.sea-box input { flex: 1; border: none; outline: none; font-size: 16px; font-family: inherit; padding: 11px 4px; background: transparent; color: #123B70; min-width: 0; }
.sea-box input::placeholder { color: #94A3B8; }
.sea-box .sea-btn { border: none; background: linear-gradient(135deg, #1976D2, #123B70); color: #FFF; font-weight: 800; font-size: 15px; padding: 12px 26px; border-radius: 999px; cursor: pointer; font-family: inherit; white-space: nowrap; }
.sea-box .sea-btn:hover { filter: brightness(1.12); }
.sea-hint { text-align: center; color: #5F7185; font-size: 13px; margin-top: 12px; }
.sea-chips { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-top: 16px; }
.sea-chip { border: 1px solid #DCEBFA; background: #EAF4FF; color: #1976D2; border-radius: 999px; padding: 8px 14px; font-size: 13.5px; font-weight: 700; cursor: pointer; font-family: inherit; transition: background .2s; }
.sea-chip:hover { background: #EAF4FF; }
.sea-result { margin-top: 22px; background: #FFFFFF; border: 1px solid #DCEBFA; border-radius: 20px; padding: 22px; box-shadow: 0 8px 24px rgba(18,59,112,.08); }
.sea-result .sr-head { display: flex; align-items: center; gap: 12px; border-bottom: 1px dashed #DCEBFA; padding-bottom: 12px; margin-bottom: 14px; }
.sea-result .sr-emoji { font-size: 34px; }
.sea-result .sr-title { font-size: 21px; font-weight: 800; color: #123B70; }
.sea-result .sr-cat { display: inline-block; background: #EAF4FF; color: #1976D2; border: 1px solid #DCEBFA; font-size: 11.5px; font-weight: 700; border-radius: 999px; padding: 3px 10px; margin-top: 4px; }
.sea-result .sr-sec { font-size: 14.5px; line-height: 1.9; color: #40566F; margin-bottom: 12px; }
.sea-result .sr-sec b { color: #1976D2; display: block; margin-bottom: 4px; }
.sea-result .sr-causes { list-style: none; padding: 0; margin: 0 0 14px; }
.sea-result .sr-causes li { padding: 6px 22px 6px 0; position: relative; font-size: 14px; color: #40566F; line-height: 1.7; }
.sea-result .sr-causes li::before { content: '•'; position: absolute; right: 4px; color: #1976D2; font-weight: 900; }
[dir="ltr"] .sea-result .sr-causes li { padding: 6px 0 6px 22px; }
[dir="ltr"] .sea-result .sr-causes li::before { right: auto; left: 4px; }
.sea-worry { background: #FEF2F2; border: 1px solid #FECACA; color: #7F1D1D; border-radius: 12px; padding: 12px 14px; font-size: 14px; line-height: 1.8; margin-bottom: 10px; }
.sea-doctor { background: #EAF4FF; border: 1px solid #DCEBFA; color: #123B70; border-radius: 12px; padding: 12px 14px; font-size: 14px; line-height: 1.8; margin-bottom: 14px; }
.sea-query-context { background:#F8FBFF; border:1px solid #DCEBFA; border-radius:14px; padding:10px 12px; margin:0 0 14px; color:#40566F; font-size:13px; line-height:1.7; }
.sea-query-context b { color:#123B70; }
.sea-topic-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; margin:14px 0; }
.sea-topic-card { border:1px solid #DCEBFA; border-radius:16px; padding:16px; background:#FBFDFF; min-width:0; }
.sea-topic-head { display:flex; align-items:center; gap:9px; margin-bottom:10px; }
.sea-topic-emoji { font-size:26px; flex:0 0 auto; }
.sea-topic-title { color:#123B70; font-weight:800; font-size:16px; line-height:1.55; }
.sea-topic-card .sr-sec { margin-bottom:10px; }
.sea-topic-card .sr-causes { margin-bottom:10px; }
.sea-topic-card .sea-worry, .sea-topic-card .sea-doctor { margin-top:9px; margin-bottom:0; }
.sea-actions { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 6px; }
.sea-actions .btn.sea-assist { background: linear-gradient(135deg, #1976D2, #1976D2); }
.sea-no { text-align: center; color: #5F7185; margin-top: 22px; font-size: 14px; }
.sea-disc { background: #FFF7ED; border: 1px dashed #FDBA74; color: #9A3412; border-radius: 10px; padding: 10px 12px; font-size: 12.5px; line-height: 1.7; margin-top: 16px; text-align: center; }
@media (max-width: 560px) { .sea-box { flex-wrap: wrap; border-radius: 22px; padding: 12px; } .sea-box .sea-btn { width: 100%; } .sea-topic-grid { grid-template-columns:1fr; } .sea-result { padding:16px; border-radius:16px; } .sea-actions .btn { width:100%; } }
"""


def search_page():
    t = CT["en" if _lang() == "en" else "ar"]
    body = """
    <div class="card">
      <h2>__SEAH__</h2>
      <p class="muted">__SEASUB__</p>
      <div class="sea-wrap">
        <div class="sea-box">
          <span class="sea-ic">🔎</span>
          <input id="seaInput" placeholder="__SEAPH__" onkeydown="if(event.key==='Enter')doSearch()">
          <button class="sea-btn" onclick="doSearch()">__SEABTN__</button>
        </div>
        <p class="sea-hint">__SEAHINT__</p>
        <div class="sea-chips" id="seaChips"></div>
      </div>
      <div id="seaRes" style="margin-top:8px;"></div>
    </div>
    <div class="warn">__SEAWARN__</div>
    <script>
    const ST = __PT__;
    function sT(k) { return ST[k] || k; }
    function esc(s) { const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }
    let curTopic = '';
    let curExplain = '';
    const API_LANG = function() { return document.documentElement.lang === 'en' ? 'en' : 'ar'; };
    function loadSuggestions() {
      fetch('/api/search?lang=' + API_LANG())
        .then(function(r) { return r.json(); })
        .then(function(d) {
          const box = document.getElementById('seaChips');
          if (!box || !d.suggestions) return;
          box.innerHTML = d.suggestions.map(function(s) {
            return '<button class="sea-chip" onclick="pickSug(\\'' + s[1].replace(/["'\\\\]/g, '') + '\\')">' + esc(s[0]) + ' ' + esc(s[1]) + '</button>';
          }).join('');
        }).catch(function() {});
    }
    function pickSug(q) { document.getElementById('seaInput').value = q; doSearch(); }
    function doSearch() {
      const inp = document.getElementById('seaInput');
      const q = (inp ? inp.value : '').trim();
      const box = document.getElementById('seaRes');
      if (!q) { box.innerHTML = '<div class="sea-no">' + esc(sT('sea_ph')) + '</div>'; return; }
      box.innerHTML = '<div style="text-align:center;padding:24px;">... <span class="spin"></span></div>';
      fetch('/api/search?q=' + encodeURIComponent(q) + '&lang=' + API_LANG())
        .then(function(r) { return r.json(); })
        .then(function(d) {
          if (!d.ok) { box.innerHTML = '<div class="warn">' + esc(d.error || sT('sea_err')) + '</div>'; return; }
          if (!d.result) { box.innerHTML = '<div class="sea-no">' + esc(sT('sea_noresult')) + '</div>'; return; }
          renderResult(d.result);
        }).catch(function() { box.innerHTML = '<div class="warn">' + esc(API_LANG()==='ar'?'حدث خطأ. تعذر تحميل المعلومات حاليًا. حاول مرة أخرى.':"Something went wrong. We could not load this information right now. Please try again.") + '<br><button class="btn pri" style="margin-top:10px" onclick="doSearch()">'+esc(API_LANG()==='ar'?'إعادة المحاولة':'Try Again')+'</button></div>'; });
    }
    function catTxt(c) {
      const m = { symptom: 'sea_cat_symp', test: 'sea_cat_test', term: 'sea_cat_term', medication: 'sea_cat_med' };
      if (c === 'combined') return API_LANG()==='ar' ? 'أعراض/مفاهيم متعددة' : 'Multiple symptoms/concepts';
      return sT(m[c] || 'sea_cat_term');
    }
    function renderTopicCard(t) {
      let h = '<div class="sea-topic-card">';
      h += '<div class="sea-topic-head"><span class="sea-topic-emoji">' + esc(t.emoji || '🩺') + '</span><div class="sea-topic-title">' + esc(t.title || '') + '</div></div>';
      if (t.what) h += '<div class="sr-sec">' + esc(t.what) + '</div>';
      if (t.causes && t.causes.length) {
        h += '<b style="color:#1976D2;">' + esc(t.causes_label || sT('sea_causes')) + '</b><ul class="sr-causes">';
        t.causes.forEach(function(c) { h += '<li>' + esc(c) + '</li>'; });
        h += '</ul>';
      }
      if (t.worry) h += '<div class="sea-worry">🚨 <b>' + esc(sT('sea_worry')) + '</b><br>' + esc(t.worry) + '</div>';
      if (t.doctor) h += '<div class="sea-doctor">🩺 <b>' + esc(sT('sea_doctor')) + '</b><br>' + esc(t.doctor) + '</div>';
      if (t.sources && t.sources.length) {
        h += '<div class="sr-sec"><b>' + (API_LANG()==='ar'?'📚 مصادر هذا العرض':'📚 Sources for this symptom') + '</b><ul class="sr-causes">';
        t.sources.forEach(function(s) {
          if (s && s.url) h += '<li><a href="' + esc(s.url) + '" target="_blank" rel="noopener noreferrer">' + esc(s.name||s.organization||s.url) + '</a></li>';
        });
        h += '</ul></div>';
      }
      h += '</div>';
      return h;
    }
    function renderSources(sources) {
      if (!sources || !sources.length) return '';
      let h = '<div class="sr-sec"><b>'+(API_LANG()==='ar'?'📚 المصادر الطبية':'📚 Medical sources')+'</b><ul class="sr-causes">';
      sources.forEach(function(s){
        if (!s || !s.url) return;
        h += '<li><a href="'+esc(s.url)+'" target="_blank" rel="noopener noreferrer">'+esc(s.name||s.organization||s.url)+'</a></li>';
      });
      h += '</ul></div>';
      return h;
    }
    function renderResult(r) {
      const box = document.getElementById('seaRes');
      let h = '<div class="sea-result">';
      h += '<div class="sr-head"><span class="sr-emoji">' + esc(r.emoji || '🩺') + '</span><div><div class="sr-title">' + esc(r.title) + '</div><span class="sr-cat">' + esc(catTxt(r.category)) + '</span></div></div>';
      if (r.original_query) {
        h += '<div class="sea-query-context"><b>' + (API_LANG()==='ar'?'بحثك: ':'Your search: ') + '</b>' + esc(r.original_query) + '</div>';
      }
      if (r.what) h += '<div class="sr-sec"><b>' + esc(sT('sea_what')) + '</b>' + esc(r.what) + '</div>';

      if (r.matched_topics && r.matched_topics.length) {
        h += '<div class="sea-topic-grid">';
        r.matched_topics.forEach(function(t) { h += renderTopicCard(t); });
        h += '</div>';
      } else {
        if (r.causes && r.causes.length) {
          h += '<b style="color:#1976D2;">' + esc(r.causes_label || sT('sea_causes')) + '</b><ul class="sr-causes">';
          r.causes.forEach(function(c) { h += '<li>' + esc(c) + '</li>'; });
          h += '</ul>';
        }
        if (r.worry) h += '<div class="sea-worry">🚨 <b>' + esc(sT('sea_worry')) + '</b><br>' + esc(r.worry) + '</div>';
      }

      if (r.doctor) h += '<div class="sea-doctor">🩺 <b>' + esc(sT('sea_doctor')) + '</b><br>' + esc(r.doctor) + '</div>';
      h += renderSources(r.sources);
      h += '<div class="sea-actions">';
      if (!r.matched_topics || r.matched_topics.length === 1) {
        h += '<button class="btn" onclick="openExplainCurrent()">✨ ' + esc(sT('sea_explain')) + '</button>';
      }
      h += '<button class="btn pri sea-assist" onclick="askAboutTopic()">🤖 ' + esc(sT('sea_ask_assist')) + '</button>';
      if (r.category === 'combined') {
        h += '<button class="btn" onclick="startSymptomAnalysis()">🩺 ' + (API_LANG()==='ar'?'ابدأ تحليل الأعراض':'Start symptom analysis') + '</button>';
      }
      h += '</div></div>';
      h += '<div class="sea-disc">' + esc(sT('sea_disc')) + '</div>';
      box.innerHTML = h;
      curTopic = r.original_query || r.title;
      curExplain = r.title || '';
    }
    function openExplainCurrent() {
      if (curExplain && typeof openExplain === 'function') openExplain(curExplain);
    }
    function startSymptomAnalysis() { window.location.href = '/chat'; }
    function askAboutTopic() {
      if (typeof asstOpenWithContext === 'function') asstOpenWithContext(curTopic);
    }
    const seaInp = document.getElementById('seaInput');
    if (seaInp) seaInp.addEventListener('focus', loadSuggestions);
    loadSuggestions();
    </script>
    """
    repl = [
        ("__PT__", json.dumps(t, ensure_ascii=False)),
        ("__SEAH__", t["sea_h"]), ("__SEASUB__", t["sea_sub"]),
        ("__SEAPH__", t["sea_ph"]), ("__SEABTN__", t["sea_btn"]),
        ("__SEAHINT__", t["sea_hint"]), ("__SEAWARN__", t["sea_warn"]),
        ("__SEAASK__", t["sea_ask_assist"]),
    ]
    for k, v in repl:
        body = body.replace(k, v)
    return _page("البحث الصحي" if _lang()=="ar" else "Health Search", body, extra_css=SEARCH_CSS)


# ---------------------------------------------------------------- health calculators
CALC_CSS = """
.calc-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-top: 6px; }
.calc-card { background: #FFFFFF; border: 1.5px solid #DCEBFA; border-radius: 18px; padding: 22px 18px; cursor: pointer; text-align: center; font-family: inherit; transition: transform .14s ease, box-shadow .14s ease, border-color .14s ease; }
.calc-card:hover { transform: translateY(-4px); box-shadow: 0 14px 30px rgba(25,118,210,.16); border-color: #1976D2; }
.calc-card .cc-ic { font-size: 40px; }
.calc-card h3 { font-size: 17px; font-weight: 800; color: #123B70; margin: 8px 0 6px; }
.calc-card p { font-size: 13.5px; color: #40566F; line-height: 1.8; margin-bottom: 14px; }
.calc-card .cc-btn { display: inline-block; background: linear-gradient(135deg, #1976D2, #123B70); color: #FFF; font-weight: 800; font-size: 13.5px; padding: 10px 22px; border-radius: 999px; }
.calc-card .cc-tag { display: inline-block; background: #EAF4FF; color: #1976D2; border: 1px solid #DCEBFA; border-radius: 999px; padding: 4px 12px; font-size: 11.5px; font-weight: 800; margin-bottom: 4px; }
.calc-card.cal-fea { grid-column: 1 / -1; background: linear-gradient(120deg, #FFFFFF, #F2F8FF); border: 2px solid #1976D2; box-shadow: 0 8px 24px rgba(25,118,210,.10); }
.calc-card.cal-fea .cc-ic { font-size: 44px; }
.calc-card.cal-fea p { font-size: 14px; }
.calc-sub { max-width: 720px; }
.calc-pane { display: none; }
.calc-pane.open { display: block; animation: fadeIn .35s ease both; }
.calc-back { margin-bottom: 12px; }
.calc-form .cf-row { margin-bottom: 14px; }
.calc-sug-hint { display: flex; gap: 10px; align-items: flex-start; background: #EAF4FF; border: 1px solid #DCEBFA; border-radius: 12px; padding: 12px 14px; font-size: 13px; line-height: 1.8; color: #123B70; margin-bottom: 14px; }
.calc-result { margin-top: 16px; background: #FFFFFF; border: 1.5px solid #DCEBFA; border-radius: 18px; padding: 20px; box-shadow: 0 8px 24px rgba(18,59,112,.08); }
.cr-value { font-size: 18px; font-weight: 800; color: #123B70; }
.cr-value .cr-num { font-size: 26px; }
.cr-cat { display: inline-block; margin-top: 10px; font-weight: 800; font-size: 15px; padding: 8px 18px; border-radius: 999px; }
.cr-cat.c-green { background: #EAF4FF; color: #1976D2; border: 1px solid #DCEBFA; }
.cr-cat.c-blue { background: #EAF4FF; color: #1976D2; border: 1px solid #DCEBFA; }
.cr-cat.c-yellow { background: #FEF9C3; color: #854D0E; border: 1px solid #FDE68A; }
.cr-cat.c-orange { background: #FFEDD5; color: #C2410C; border: 1px solid #FDBA74; }
.cr-cat.c-red { background: #FEE2E2; color: #B91C1C; border: 1px solid #FCA5A5; }
.cr-note { margin-top: 12px; font-size: 14px; line-height: 1.9; color: #40566F; }
.cr-note .ped { display: block; margin-top: 8px; color: #92400E; background: #FEF3C7; border: 1px solid #FDE68A; border-radius: 10px; padding: 8px 12px; font-size: 13px; }
.cr-alert { margin-top: 14px; background: #FEF2F2; border: 1.5px solid #FCA5A5; color: #7F1D1D; border-radius: 14px; padding: 14px 16px; font-size: 14px; line-height: 1.8; }
.cr-alert a { color: #B91C1C; font-weight: 800; text-decoration: underline; }
.cr-assist { margin-top: 16px; border-top: 1px dashed #DCEBFA; padding-top: 14px; text-align: center; }
.cr-assist .cr-follow { font-size: 15px; font-weight: 800; color: #123B70; margin-bottom: 10px; }
.cr-assist .btn { min-width: 250px; background: linear-gradient(135deg, #1976D2, #123B70); color: #FFF; border: none; }
.cr-assist .btn:hover { transform: translateY(-1px); }
.calc-rows { margin-top: 10px; display: flex; flex-direction: column; gap: 8px; }
.cd-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; background: #F5F9FF; border: 1px solid #DCEBFA; border-radius: 12px; padding: 12px 14px; font-size: 14px; }
.cd-row b { color: #123B70; }
.cd-row .cd-first { background: #EAF4FF; border: 1px solid #DCEBFA; color: #1976D2; font-size: 11.5px; font-weight: 800; border-radius: 999px; padding: 3px 10px; }
.cd-note { margin-top: 12px; background: #FFF7ED; border: 1px dashed #FDBA74; color: #9A3412; border-radius: 10px; padding: 10px 12px; font-size: 13px; line-height: 1.8; }
.calc-unit-row { display: flex; gap: 8px; flex-wrap: wrap; }
.calc-unit-row label { flex: 1; min-width: 140px; border: 2px solid #DCEBFA; border-radius: 12px; padding: 11px; text-align: center; cursor: pointer; font-size: 14px; font-weight: 700; color: #40566F; font-family: inherit; }
.calc-unit-row input[type="radio"] { display: none; }
.calc-unit-row input[type="radio"]:checked + label { border-color: #1976D2; background: #EAF4FF; color: #1976D2; }
.calc-a1c-hint { font-size: 12.5px; color: #92400E; background: #FEF3C7; border: 1px solid #FDE68A; border-radius: 10px; padding: 8px 12px; margin-top: 8px; }
.calc-disc-card { display: flex; gap: 12px; align-items: flex-start; background: #FFFFFF; border: 1px solid #DCEBFA; border-radius: 16px; padding: 16px 18px; margin-bottom: 22px; box-shadow: 0 4px 14px rgba(18,59,112,.05); }
.calc-disc-card .cdc-ic { font-size: 22px; line-height: 1.4; }
.calc-disc-card .cdc-t { font-weight: 800; color: #123B70; margin-bottom: 4px; font-size: 15px; }
.calc-disc-card .cdc-p { font-size: 13.5px; color: #40566F; line-height: 1.9; }
@media (max-width: 640px) { .calc-grid { grid-template-columns: 1fr; } }
"""


def calculators_page():
    t = CT["en" if _lang() == "en" else "ar"]
    cards = [
        ("bmi", "⚖️", "calc_bmi_name", "calc_bmi_desc", ""),
        ("fluids", "💧", "calc_fluids_name", "calc_fluids_desc", ""),
        ("dose", "💊", "calc_dose_name", "calc_dose_desc", ""),
        ("cal", "🔥", "calc_cal_name", "calc_cal_desc", ""),
        ("sug", "🩸", "calc_sug_name", "calc_sug_desc", "cal-fea"),
    ]
    cards_html = "".join(
        '<button class="calc-card %s" onclick="showCalc(\'%s\')"><div class="cc-ic">%s</div>'
        '<h3>%s</h3>%s<p>%s</p><span class="cc-btn">%s</span></button>'
        % (cls, k, ic, t[n], ('<span class="cc-tag">%s</span>' % t["calc_sug_tag"]) if cls else "", t[d], t["calc_now"])
        for k, ic, n, d, cls in cards
    )
    body = """
    <div class="card">
      <h2>__CALCH__</h2>
      <p class="muted calc-sub">__CALCSUB__</p>
      <div class="calc-grid">__CARDS__</div>
    </div>

    <div id="calcPaneArea" style="display:none;">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:6px;flex-wrap:wrap;">
        <h2 id="paneTitle" style="color:#123B70;"></h2>
        <button class="btn ghost calc-back" onclick="backToGrid()">__CALCBACK__</button>
      </div>

      <div class="calc-pane open" id="pane-bmi">
        <div class="card">
          <div class="calc-form">
            <div class="grid2">
              <div class="cf-row"><label class="lbl">__BW__</label><input class="inp" id="bmiW" type="number" inputmode="decimal" placeholder="__BWPH__"></div>
              <div class="cf-row"><label class="lbl">__BH__</label><input class="inp" id="bmiH" type="number" inputmode="decimal" placeholder="__BHPH__"></div>
            </div>
            <button class="btn pri start-btn" onclick="runBMI()">__BBTN__</button>
          </div>
          <div id="resBMI"></div>
        </div>
      </div>

      <div class="calc-pane" id="pane-fluids">
        <div class="card">
          <div class="calc-form">
            <div class="grid2">
              <div class="cf-row"><label class="lbl">__AGE__</label><input class="inp" id="flAge" type="number" inputmode="numeric" placeholder="__AGEPH__"></div>
              <div class="cf-row"><label class="lbl">__WEIGHT__</label><input class="inp" id="flW" type="number" inputmode="decimal" placeholder="__WPH__"></div>
            </div>
            <div class="cf-row"><label class="lbl">__ACT__</label>
              <select class="inp" id="flAct">
                <option value="low">__ACTLOW__</option>
                <option value="medium">__ACTMED__</option>
                <option value="high">__ACTHIGH__</option>
              </select>
            </div>
            <button class="btn pri start-btn" onclick="runFluids()">__FBTN__</button>
          </div>
          <div id="resFluids"></div>
        </div>
      </div>

      <div class="calc-pane" id="pane-dose">
        <div class="card">
          <div class="warn">__DWARN__</div>
          <div class="calc-form">
            <div class="cf-row"><label class="lbl">__DMED__</label><input class="inp" id="dMed" placeholder="__DMEDPH__"></div>
            <div class="grid2">
              <div class="cf-row"><label class="lbl">__DFIRST__</label><input class="inp" id="dFirst" type="time" value="08:00"></div>
              <div class="cf-row"><label class="lbl">__DIV__</label><select class="inp" id="dIv"></select></div>
            </div>
            <button class="btn pri start-btn" onclick="runDose()">__DBTN__</button>
          </div>
          <div id="resDose"></div>
        </div>
      </div>

      <div class="calc-pane" id="pane-cal">
        <div class="card">
          <div class="calc-form">
            <div class="grid2">
              <div class="cf-row"><label class="lbl">__AGE__</label><input class="inp" id="calAge" type="number" inputmode="numeric" placeholder="__AGEPH__"></div>
              <div class="cf-row"><label class="lbl">__GENDER__</label>
                <select class="inp" id="calG">
                  <option value="male">__MALE__</option>
                  <option value="female">__FEMALE__</option>
                </select>
              </div>
            </div>
            <div class="grid2">
              <div class="cf-row"><label class="lbl">__HGT__</label><input class="inp" id="calH" type="number" inputmode="decimal" placeholder="__HGTPH__"></div>
              <div class="cf-row"><label class="lbl">__WEIGHT__</label><input class="inp" id="calW" type="number" inputmode="decimal" placeholder="__WPH__"></div>
            </div>
            <div class="cf-row"><label class="lbl">__ACT__</label>
              <select class="inp" id="calAct">
                <option value="low">__ACT2LOW__</option>
                <option value="medium">__ACT2MED__</option>
                <option value="high">__ACT2HIGH__</option>
              </select>
            </div>
            <button class="btn pri start-btn" onclick="runCal()">__CBTN__</button>
          </div>
          <div id="resCal"></div>
        </div>
      </div>

      <div class="calc-pane" id="pane-sug">
        <div class="card">
          <div class="calc-sug-hint">🩸 __SUGHINT__</div>
          <div class="calc-form">
            <div class="grid2">
              <div class="cf-row"><label class="lbl">__AGE__</label><input class="inp" id="sgAge" type="number" inputmode="numeric" placeholder="__AGEPH__"></div>
              <div class="cf-row"><label class="lbl">__STYPE__</label>
                <select class="inp" id="sgType" onchange="sugTypeChange()">
                  <option value="fasting">__SFAST__</option>
                  <option value="post">__SPOST__</option>
                  <option value="random">__SRAND__</option>
                  <option value="a1c">__SA1C__</option>
                </select>
              </div>
            </div>
            <div class="cf-row"><label class="lbl">__SREAD__</label><input class="inp" id="sgVal" type="number" inputmode="decimal" placeholder="__SREADPH__"></div>
            <div class="cf-row" id="sgUnitRow">
              <label class="lbl">__SUNIT__</label>
              <div class="calc-unit-row">
                <input type="radio" name="sgUnit" id="sgMg" value="mg" checked>
                <label for="sgMg">__SUNMG__</label>
                <input type="radio" name="sgUnit" id="sgMmol" value="mmol">
                <label for="sgMmol">__SUNMMOL__</label>
              </div>
            </div>
            <div class="calc-a1c-hint" id="sgA1cHint" style="display:none;">__SA1CHINT__</div>
            <button class="btn pri start-btn" onclick="runSugar()">__SBTN__</button>
          </div>
          <div id="resSug"></div>
        </div>
      </div>
    </div>

    <div class="calc-disc-card">
      <div class="cdc-ic">⚠️</div>
      <div>
        <div class="cdc-t">__CALCDISCT__</div>
        <div class="cdc-p">__CALCDISC__</div>
      </div>
    </div>
    <script>
    const T = __PT__;
    function esc(s) { const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }
    function CTT(k) { return T[k] || k; }
    function APILang() { return document.documentElement.lang === 'en' ? 'en' : 'ar'; }
    const PANE_TITLES = { bmi: 'calc_bmi_name', fluids: 'calc_fluids_name', dose: 'calc_dose_name', cal: 'calc_cal_name', sug: 'calc_sug_name' };
    const CAT_EMOJI = { green: '🟢', blue: '🔵', yellow: '🟡', orange: '🟠', red: '🔴' };
    let calcCtx = '';
    let asstCalcKind = 'calc';
    if (typeof asstSetCtx === 'function') asstSetCtx('calc');

    function showCalc(k) {
      asstCalcKind = k;
      if (typeof asstSetCtx === 'function') asstSetCtx(k);
      document.getElementById('calcPaneArea').style.display = '';
      document.getElementById('paneTitle').textContent = CTT(PANE_TITLES[k]);
      document.querySelectorAll('.calc-pane').forEach(function(p) { p.classList.remove('open'); });
      document.getElementById('pane-' + k).classList.add('open');
      if (k === 'dose') initIv();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
    function backToGrid() {
      document.getElementById('calcPaneArea').style.display = 'none';
      document.getElementById('calcPaneArea').scrollIntoView({ behavior: 'smooth' });
    }
    function initIv() {
      const sel = document.getElementById('dIv');
      if (sel.dataset.init) return;
      sel.dataset.init = '1';
      const opts = [4, 6, 8, 12, 24];
      sel.innerHTML = opts.map(function(v) {
        return '<option value="' + v + '">' + CTT('calc_dose_every').replace('%s', v) + '</option>';
      }).join('');
      sel.value = '8';
    }
    function sugTypeChange() {
      const a1c = document.getElementById('sgType').value === 'a1c';
      document.getElementById('sgUnitRow').style.display = a1c ? 'none' : '';
      document.getElementById('sgA1cHint').style.display = a1c ? '' : 'none';
    }
    function askCalc() {
      if (typeof asstSetCtx === 'function') asstSetCtx(asstCalcKind || 'calc');
      if (calcCtx && typeof asstSendContextText === 'function') asstSendContextText(calcCtx);
    }
    function assistHTML(kind) {
      let askT = CTT('calc_follow'), askB = CTT('calc_ask');
      if (kind === 'bmi') { askT = CTT('calc_ask_bmi_t'); askB = CTT('calc_ask_bmi_b'); }
      else if (kind === 'sug') { askT = CTT('calc_ask_sug_t'); askB = CTT('calc_ask_sug_b'); }
      return '<div class="cr-assist"><div class="cr-follow">' + esc(askT) + '</div>' +
        '<button class="btn pri" onclick="askCalc()">' + esc(askB) + '</button></div>';
    }
    function fmtNum(n) { return String(n).replace(/\\B(?=(\\d{3})+(?!\\d))/g, ','); }
    function fmtTime(h, m) {
      const p = h < 12 ? CTT('calc_am') : CTT('calc_pm');
      let hh = h % 12; if (hh === 0) hh = 12;
      return hh + ':' + (m < 10 ? '0' + m : m) + ' ' + p;
    }
    function catHTML(d, kind) {
      if (!d.category) return '';
      const lbl = CTT('calc_' + kind + '_cat_' + d.category);
      return '<div class="cr-cat c-' + d.color + '">' + (CAT_EMOJI[d.color] || '') + ' ' + esc(lbl) + '</div>';
    }
    function noteHTML(d, kind, extraPed) {
      let n = CTT('calc_' + kind + '_note_' + d.category) || '';
      if (extraPed) n += ' <span class="ped">⚠️ ' + esc(CTT('calc_sug_note_ped')) + '</span>';
      return '<div class="cr-note">' + esc(n) + '</div>';
    }
    function alertHTML(d) {
      if (!d.alert) return '';
      let msg = CTT('calc_alert_msg');
      if (d.alert_kind === 'high') msg = CTT('calc_alert_high');
      if (d.alert_kind === 'low') msg = CTT('calc_alert_low');
      return '<div class="cr-alert">' + esc(CTT('calc_alert_t')) + ' — ' + esc(msg) +
        ' <br><a href="/emergency">' + esc(CTT('calc_em_btn')) + ' →</a></div>';
    }
    function renderBox(id, d, kind, valueLabel, unit, extraPed) {
      const box = document.getElementById(id);
      let h = '<div class="calc-result">';
      h += '<div class="cr-value">' + esc(valueLabel) + ' <span class="cr-num">' + fmtNum(d.value) + '</span> ' + esc(unit || '') + '</div>';
      h += catHTML(d, kind) + noteHTML(d, kind, extraPed);
      h += alertHTML(d) + assistHTML(kind);
      h += '</div>';
      box.innerHTML = h;
    }
    function calcGet(params, cb, errId) {
      const box = document.getElementById(errId || 'resBMI');
      fetch('/api/calc?' + params).then(function(r) { return r.json(); }).then(function(d) {
        if (d.ok) cb(d); else box.innerHTML = '<div class="warn">' + esc(CTT('calc_err')) + '</div>';
      }).catch(function() { box.innerHTML = '<div class="warn">' + esc(CTT('calc_err')) + '</div>'; });
    }
    function runBMI() {
      const w = parseFloat(document.getElementById('bmiW').value);
      const h = parseFloat(document.getElementById('bmiH').value);
      if (!w || !h) { document.getElementById('resBMI').innerHTML = '<div class="warn">' + esc(CTT('calc_err')) + '</div>'; return; }
      calcGet('kind=bmi&w=' + w + '&h=' + h + '&lang=' + APILang(), function(d) {
        renderBox('resBMI', d, 'bmi', CTT('calc_bmi_val'), CTT('calc_bmi_unit'));
        calcCtx = CTT('calc_bmi_ctx').replace('%s', fmtNum(d.value));
      }, 'resBMI');
    }
    function runFluids() {
      const a = parseFloat(document.getElementById('flAge').value);
      const w = parseFloat(document.getElementById('flW').value);
      if (!a || !w) { document.getElementById('resFluids').innerHTML = '<div class="warn">' + esc(CTT('calc_err')) + '</div>'; return; }
      const act = document.getElementById('flAct').value;
      calcGet('kind=fluids&age=' + a + '&w=' + w + '&act=' + act + '&lang=' + APILang(), function(d) {
        let h = '<div class="calc-result">';
        h += '<div class="cr-value">' + esc(CTT('calc_fluids_val')) + ' <span class="cr-num">' + fmtNum(d.value) + '</span> ' + esc(CTT('calc_fluids_unit')) + '</div>';
        h += '<div class="cr-note">' + esc(CTT('calc_fluids_note')) + '</div>';
        h += alertHTML(d) + assistHTML('fluids') + '</div>';
        document.getElementById('resFluids').innerHTML = h;
        calcCtx = CTT('calc_fluids_ctx').replace('%s', fmtNum(d.value));
      }, 'resFluids');
    }
    function runDose() {
      const val = document.getElementById('dFirst').value || '08:00';
      const parts = val.split(':');
      const h = parseInt(parts[0], 10), m = parseInt(parts[1], 10);
      const iv = document.getElementById('dIv').value || '8';
      const med = document.getElementById('dMed').value.trim() || '—';
      calcGet('kind=dose&h=' + h + '&m=' + m + '&iv=' + iv + '&lang=' + APILang(), function(d) {
        let hh = '<div class="calc-result">';
        hh += '<div class="cr-value">' + esc(CTT('calc_dose_table')) + '</div>';
        hh += '<div class="calc-rows">';
        d.schedule.forEach(function(s) {
          hh += '<div class="cd-row"><span>💊 <b>' + esc(fmtTime(s.h, s.m)) + '</b></span>' +
            (s.first ? '<span class="cd-first">' + esc(CTT('calc_dose_first_dose')) + '</span>' : '<span class="muted">' + esc(CTT('calc_dose_next')) + '</span>') + '</div>';
        });
        hh += '</div><div class="cd-note">' + esc(CTT('calc_dose_note')) + '</div>';
        hh += assistHTML('dose') + '</div>';
        document.getElementById('resDose').innerHTML = hh;
        calcCtx = CTT('calc_dose_ctx').replace('%s', med);
      }, 'resDose');
    }
    function runCal() {
      const a = parseFloat(document.getElementById('calAge').value);
      const h = parseFloat(document.getElementById('calH').value);
      const w = parseFloat(document.getElementById('calW').value);
      if (!a || !h || !w) { document.getElementById('resCal').innerHTML = '<div class="warn">' + esc(CTT('calc_err')) + '</div>'; return; }
      const g = document.getElementById('calG').value;
      const act = document.getElementById('calAct').value;
      calcGet('kind=cal&age=' + a + '&g=' + g + '&h=' + h + '&w=' + w + '&act=' + act + '&lang=' + APILang(), function(d) {
        let bb = '<div class="calc-result">';
        bb += '<div class="cr-value">' + esc(CTT('calc_cal_val')) + ' <span class="cr-num">≈ ' + fmtNum(d.value) + '</span> ' + esc(CTT('calc_cal_unit')) + '</div>';
        bb += '<div class="cr-note">' + esc(CTT('calc_cal_note')) + '</div>';
        bb += alertHTML(d) + assistHTML('cal') + '</div>';
        document.getElementById('resCal').innerHTML = bb;
        calcCtx = CTT('calc_cal_ctx').replace('%s', fmtNum(d.value));
      }, 'resCal');
    }
    function runSugar() {
      const a = parseFloat(document.getElementById('sgAge').value);
      const val = parseFloat(document.getElementById('sgVal').value);
      if (!val) { document.getElementById('resSug').innerHTML = '<div class="warn">' + esc(CTT('calc_err')) + '</div>'; return; }
      const type = document.getElementById('sgType').value;
      const unit = type === 'a1c' ? 'a1c' : (document.querySelector('input[name="sgUnit"]:checked') || { value: 'mg' }).value;
      calcGet('kind=sugar&val=' + val + '&unit=' + unit + '&type=' + type + '&age=' + (a || '') + '&lang=' + APILang(), function(d) {
        const typeLabel = CTT('calc_sug_' + ({ fasting: 'fast', post: 'post', random: 'random', a1c: 'a1c' })[d.type]);
        let hh = '<div class="calc-result">';
        hh += '<div class="cr-value">' + esc(CTT('calc_sug_val')) + ' <span class="cr-num">' + fmtNum(d.value) + '</span> ' + esc(d.unit) + ' · ' + esc(typeLabel) + '</div>';
        hh += catHTML(d, 'sug') + noteHTML(d, 'sug', !!d.pediatric);
        hh += alertHTML(d) + assistHTML('sug') + '</div>';
        document.getElementById('resSug').innerHTML = hh;
        if (d.type === 'a1c') calcCtx = CTT('calc_sug_ctx').replace('%v', fmtNum(d.value)).replace('%u', '%').replace('%t', 'HbA1c');
        else calcCtx = CTT('calc_sug_ctx').replace('%v', fmtNum(d.value)).replace('%u', d.unit).replace('%t', typeLabel);
      }, 'resSug');
    }
    (function(){
      fetch('/api/user-info').then(function(r){ return r.json(); }).then(function(ui){
        if (ui.ok && ui.logged_in && ui.profile) {
          var p = ui.profile;
          var age = p.age;
          if (!age && p.dob) {
            try { var bd = new Date(p.dob); var now = new Date(); age = Math.floor((now - bd) / (365.25 * 24 * 60 * 60 * 1000)); } catch(e) {}
          }
          if (age) {
            var fields = ['flAge', 'calAge', 'sgAge'];
            fields.forEach(function(id) {
              var el = document.getElementById(id);
              if (el && !el.value) el.value = age;
            });
          }
          if (p.weight) {
            var wFields = ['bmiW', 'flW', 'calW'];
            wFields.forEach(function(id) {
              var el = document.getElementById(id);
              if (el && !el.value) el.value = p.weight;
            });
          }
          if (p.height) {
            var hFields = ['bmiH', 'calH'];
            hFields.forEach(function(id) {
              var el = document.getElementById(id);
              if (el && !el.value) el.value = p.height;
            });
          }
          if (p.gender) {
            var gFields = ['calG'];
            var gVal = p.gender === 'male' ? 'm' : (p.gender === 'female' ? 'f' : '');
            if (gVal) {
              gFields.forEach(function(id) {
                var el = document.getElementById(id);
                if (el && !el.value) el.value = gVal;
              });
            }
          }
        }
      }).catch(function(){});
    })();
    </script>
    """
    repl = [
        ("__PT__", json.dumps(t, ensure_ascii=False)),
        ("__CALCH__", t["calc_h"]), ("__CALCSUB__", t["calc_sub"]),
        ("__CARDS__", cards_html), ("__CALCBACK__", t["calc_back"]),
        ("__CALCDISC__", t["calc_disc"]), ("__CALCDISCT__", t["calc_disc_t"]),
        ("__SUGHINT__", t["calc_sug_hint"]),
        ("__BW__", t["calc_bmi_w"]), ("__BWPH__", t["calc_bmi_w_ph"]),
        ("__BH__", t["calc_bmi_h"]), ("__BHPH__", t["calc_bmi_h_ph"]),
        ("__BBTN__", t["calc_bmi_btn"]),
        ("__AGE__", t["calc_age"]), ("__AGEPH__", t["calc_age_ph"]),
        ("__WEIGHT__", t["calc_weight"]), ("__WPH__", t["calc_weight_ph"]),
        ("__ACT__", t["calc_act"]), ("__ACTLOW__", t["calc_act_low"]),
        ("__ACTMED__", t["calc_act_med"]), ("__ACTHIGH__", t["calc_act_high"]),
        ("__FBTN__", t["calc_fluids_btn"]),
        ("__DWARN__", t["calc_dose_warn"]), ("__DMED__", t["calc_dose_med"]),
        ("__DMEDPH__", t["calc_dose_med_ph"]), ("__DFIRST__", t["calc_dose_first"]),
        ("__DIV__", t["calc_dose_iv"]), ("__DBTN__", t["calc_dose_btn"]),
        ("__GENDER__", t["calc_gender"]), ("__MALE__", t["calc_male"]),
        ("__FEMALE__", t["calc_female"]), ("__HGT__", t["calc_hgt"]),
        ("__HGTPH__", t["calc_hgt_ph"]),
        ("__ACT2LOW__", t["calc_act2_low"]), ("__ACT2MED__", t["calc_act2_med"]),
        ("__ACT2HIGH__", t["calc_act2_high"]), ("__CBTN__", t["calc_cal_btn"]),
        ("__STYPE__", t["calc_sug_type"]), ("__SFAST__", t["calc_sug_fast"]),
        ("__SPOST__", t["calc_sug_post"]), ("__SRAND__", t["calc_sug_random"]),
        ("__SA1C__", t["calc_sug_a1c"]), ("__SREAD__", t["calc_sug_reading"]),
        ("__SREADPH__", t["calc_sug_reading_ph"]), ("__SUNIT__", t["calc_sug_unit"]),
        ("__SUNMG__", t["calc_sug_unit_mg"]), ("__SUNMMOL__", t["calc_sug_unit_mmol"]),
        ("__SA1CHINT__", t["calc_sug_a1c_hint"]), ("__SBTN__", t["calc_sug_btn"]),
    ]
    for k, v in repl:
        body = body.replace(k, v)
    return _page(_t("title_calculators"), body, extra_css=CALC_CSS)


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
          html += '<div class="vidbtn" onclick="loadVid(this,\\'' + vid + '\\')">' + esc('__FAVIDEO__') + '</div><div class="vidwrap"></div>';
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
    body = body.replace("__CATS__", json.dumps(cats, ensure_ascii=False))
    body = body.replace("__VIDS__", json.dumps(vids, ensure_ascii=False))
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
      <div style="text-align:center;margin-top:14px;"><button class="btn" onclick="loadTip()">__TIPSB__</button></div>
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
      <div style="text-align:center;margin-top:16px;"><div id="breathBox" style="font-size:30px;font-weight:800;color:#1976D2;height:70px;display:flex;align-items:center;justify-content:center;"></div></div>
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
def emergency_page():
    t = CT["en" if _lang() == "en" else "ar"]
    body = """
    <style>body { background: #F5F9FF; }</style>
    <div class="card">
      <h2>__EMH__</h2>
      <p class="muted">__EMSUB__</p>
      <div class="em-alert">__EMALERT__</div>
      <div class="em-grid3">
        <div class="em-card">
          <div class="em-ic">🚑</div>
          <h3>__EMRED__</h3>
          <p class="em-desc">__EMREDD__</p>
          <div class="em-num red">997</div>
          <a class="em-call" href="tel:997">📞 __EMCALL__</a>
        </div>
        <div class="em-card">
          <div class="em-ic">📞</div>
          <h3>__EMUNI__</h3>
          <p class="em-desc">__EMUNID__</p>
          <div class="em-num red">911</div>
          <a class="em-call" href="tel:911">📞 __EMCALL__</a>
        </div>
        <div class="em-card">
          <div class="em-ic">🩺</div>
          <h3>__EM937__</h3>
          <p class="em-desc">__EM937D__</p>
          <div class="em-num blue">937</div>
          <a class="em-call blue" href="tel:937">📞 __EMCALL__</a>
        </div>
      </div>
      <div class="em-mini">
        <div class="em-mini-card">🚓 <b>__EMPOL__</b><span class="em-mini-num">999</span><p class="muted" style="flex-basis:100%;">__EMPOLD__</p></div>
        <div class="em-mini-card">🚒 <b>__EMCIV__</b><span class="em-mini-num">998</span><p class="muted" style="flex-basis:100%;">__EMCIVD__</p></div>
      </div>
    </div>
    <div class="card em-danger">
      <h2 class="em-danger-h">__EMSIGNH__</h2>
      <div class="em-signs">
        <div class="em-sign">__EMS1__</div>
        <div class="em-sign">__EMS2__</div>
        <div class="em-sign">__EMS3__</div>
        <div class="em-sign">__EMS4__</div>
        <div class="em-sign">__EMS5__</div>
      </div>
      <div style="text-align:center;margin-top:16px;">
        <a class="em-call big" href="tel:997">__EMCALLBTN__</a>
      </div>
    </div>
    <div class="card" id="geo">
      <h2>__EMGEOT__</h2>
      <p class="muted">__EMGEOSUB__</p>
      <div style="text-align:center;margin-top:14px;">
        <span class="em-24h">🕐 __EMGEO24H__</span>
        <div style="margin-top:14px;"><button class="btn pri big" onclick="nearMe()">__EMGEOBTN__</button></div>
      </div>
      <div id="geoMsg" style="text-align:center;margin-top:10px;font-weight:700;color:#1976D2;"></div>
      <div id="geoList" style="margin-top:12px;"></div>
    </div>
    <div class="warn em-safety">__EMSAFETY__</div>
    <script>
    const EM = __PT__;
    async function nearMe() {
      const msg = document.getElementById('geoMsg');
      const list = document.getElementById('geoList');
      msg.textContent = EM.em_geo_searching;
      list.innerHTML = '';
      if (!navigator.geolocation) { msg.textContent = EM.em_geo_err; return; }
      navigator.geolocation.getCurrentPosition(async function(pos) {
        try {
          const r = await fetch('/api/hospitals', {method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({lat: pos.coords.latitude, lng: pos.coords.longitude})});
          const d = await r.json();
          if (!d.ok) { msg.textContent = EM.em_geo_err + (d.error ? ' (' + d.error + ')' : ''); return; }
          if (!d.hospitals || !d.hospitals.length) { msg.textContent = EM.em_geo_empty; return; }
          msg.textContent = '';
          let html = '<h3 style="margin-bottom:8px;">' + EM.em_nearby + '</h3>';
          d.hospitals.forEach(function(h) {
            html += '<div class="hist-card"><div class="hist-head"><b>🏥 ' + (h.name || '?') + '</b></div>' +
              '<p class="muted">📍 ' + (h.distance_km || '') + ' km</p>' +
              (h.maps_url ? '<a class="btn ghost small" href="' + h.maps_url + '" target="_blank" rel="noopener">🗺️ ' + EM.em_geo_btn + '</a>' : '') +
              '</div>';
          });
          list.innerHTML = html;
        } catch(e) { msg.textContent = EM.em_geo_err; }
      }, function() { msg.textContent = EM.em_geo_err; }, {timeout: 15000});
    }
    </script>
    """
    repl = [
        ("__EMH__", t["em_h"]), ("__EMSUB__", t["em_sub"]),
        ("__EMALERT__", t["em_alert"]),
        ("__EMRED__", t["em_red"]), ("__EMUNI__", t["em_unified"]), ("__EM937__", t["em_937"]),
        ("__EMREDD__", t["em_red_desc"]), ("__EMUNID__", t["em_unified_desc"]), ("__EM937D__", t["em_937_desc"]),
        ("__EMCALL__", t["em_call"]),
        ("__EMPOL__", t["em_police"]), ("__EMCIV__", t["em_civil"]),
        ("__EMPOLD__", t["em_police_desc"]), ("__EMCIVD__", t["em_civil_desc"]),
        ("__EMSIGNH__", t["em_signs_h"]),
        ("__EMS1__", t["em_s1"]), ("__EMS2__", t["em_s2"]), ("__EMS3__", t["em_s3"]),
        ("__EMS4__", t["em_s4"]), ("__EMS5__", t["em_s5"]),
        ("__EMCALLBTN__", t["em_call_btn"]),
        ("__EMGEOT__", t["em_geo_title"]), ("__EMGEOSUB__", t["em_geo_sub"]),
        ("__EMGEO24H__", t["em_geo_24h"]), ("__EMGEOBTN__", t["em_geo_btn"]),
        ("__EMSAFETY__", t["em_safety"]),
        ("__PT__", json.dumps({
            "em_geo_searching": t["em_geo_searching"], "em_geo_err": t["em_geo_err"],
            "em_geo_empty": t["em_geo_empty"], "em_nearby": t["em_nearby"],
            "em_geo_btn": t["em_geo_btn"],
        }, ensure_ascii=False)),
    ]
    for k, v in repl:
        body = body.replace(k, v)
    return _page(_t("title_emergency"), body)


# ---------------------------------------------------------------- checkin
def checkin_page():
    ar = _lang() == "ar"
    if not _ss_user_id():
        body = '''
        <main style="max-width:560px;margin:38px auto;padding:0 12px">
          <section class="card" style="text-align:center;padding:28px 22px">
            <div style="font-size:42px;margin-bottom:8px">📋</div>
            <h1>__TITLE__</h1>
            <p class="muted" style="margin:10px 0 18px">__TEXT__</p>
            <a class="btn primary" href="/login?next=/checkin">__LOGIN__</a>
          </section>
        </main>
        '''.replace("__TITLE__", "متابعة الحالة اليومية" if ar else "Daily Health Tracking") \
           .replace("__TEXT__", "سجّل الدخول لحفظ ومتابعة حالتك اليومية." if ar else "Sign in to save and track your daily health status.") \
           .replace("__LOGIN__", "تسجيل الدخول" if ar else "Sign in")
        return _page(_t("title_checkin"), body)

    labels = {
        "title": "📋 متابعة الحالة اليومية" if ar else "📋 Daily Health Tracking",
        "sub": "سجّل حالتك اليوم وتابع تحسنك بمرور الوقت." if ar else "Record how you feel today and follow your progress over time.",
        "question": "كيف كانت حالتك اليوم؟" if ar else "How were you feeling today?",
        "save": "حفظ تسجيل اليوم" if ar else "Save today's check-in",
        "update": "تعديل تسجيل اليوم" if ar else "Update today's check-in",
        "today_saved": "لقد سجلت حالتك اليوم بالفعل." if ar else "You already recorded today's check-in.",
        "saved": "تم حفظ تسجيل حالتك اليوم بنجاح ✓" if ar else "Today's check-in was saved successfully ✓",
        "updated": "تم تعديل تسجيل اليوم بنجاح ✓" if ar else "Today's check-in was updated successfully ✓",
        "history": "📊 سجل حالتي" if ar else "📊 My Check-in History",
        "summary": "📈 ملخص حالتك" if ar else "📈 Your Summary",
        "today": "اليوم" if ar else "Today",
        "week": "متوسط آخر 7 أيام" if ar else "Average of last 7 days",
        "count": "عدد التسجيلات" if ar else "Total check-ins",
        "date": "التاريخ" if ar else "Date",
        "status": "الحالة" if ar else "Status",
        "rating": "التقييم" if ar else "Rating",
        "empty": "لا توجد تسجيلات سابقة بعد." if ar else "No previous check-ins yet.",
        "error": "تعذر حفظ أو تحميل التسجيلات الآن. حاول مرة أخرى." if ar else "Unable to save or load check-ins right now. Please try again.",
        "very_bad": "سيئة جدًا" if ar else "Very bad",
        "bad": "سيئة" if ar else "Bad",
        "medium": "متوسطة" if ar else "Average",
        "good": "جيدة" if ar else "Good",
        "excellent": "ممتازة" if ar else "Excellent",
    }
    body = r'''
    <style>
      .ss-checkin-shell{max-width:820px;margin:0 auto;padding:8px 0 28px}
      .ss-checkin-card{background:#fff;border:1px solid #D7E6F1;border-radius:22px;padding:24px;box-shadow:0 10px 30px rgba(27,74,112,.07);margin-bottom:18px}
      .ss-checkin-card h1,.ss-checkin-card h2{margin:0;color:#184568}.ss-checkin-card p{line-height:1.8}
      .ss-checkin-question{font-size:18px;font-weight:800;color:#24445F;margin:20px 0 12px}
      .ss-mood-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}
      .ss-mood-option{appearance:none;border:1.5px solid #D7E6F1;background:#F9FCFE;border-radius:16px;min-height:100px;padding:12px 8px;cursor:pointer;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;color:#35556F;font:inherit;transition:border-color .18s,box-shadow .18s,background .18s,transform .18s}
      .ss-mood-option .emoji{font-size:30px;line-height:1}.ss-mood-option .label{font-size:12px;font-weight:800;text-align:center;line-height:1.45}
      .ss-mood-option:hover{border-color:#9ECBE8;background:#F3FAFE}.ss-mood-option:focus-visible{outline:3px solid rgba(40,127,193,.22);outline-offset:2px}
      .ss-mood-option.selected{border-color:#287FC1;background:#EAF6FD;box-shadow:0 0 0 3px rgba(40,127,193,.12);transform:translateY(-1px)}
      .ss-checkin-save{width:100%;margin-top:16px;min-height:48px;border:0;border-radius:13px;background:#287FC1;color:#fff;font-weight:900;font-size:15px;cursor:pointer;padding:12px 16px}.ss-checkin-save:disabled{opacity:.5;cursor:not-allowed}
      .ss-checkin-msg{min-height:24px;margin-top:10px;text-align:center;font-size:13px;font-weight:800}.ss-checkin-msg.ok{color:#237352}.ss-checkin-msg.err{color:#B23A3A}
      .ss-today-note{display:none;margin-top:14px;padding:12px 14px;border-radius:13px;background:#F3F9FD;border:1px solid #D7E6F1;color:#35556F}.ss-today-note.show{display:block}
      .ss-summary-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:14px}.ss-summary-item{padding:14px;border:1px solid #E2EDF4;border-radius:15px;background:#F9FCFE}.ss-summary-item span{display:block;color:#6B7F91;font-size:11px;margin-bottom:5px}.ss-summary-item strong{color:#184568;font-size:14px}
      .ss-history-table{width:100%;border-collapse:separate;border-spacing:0;margin-top:14px;overflow:hidden;border:1px solid #E2EDF4;border-radius:15px}.ss-history-table th,.ss-history-table td{padding:12px 14px;text-align:start;border-bottom:1px solid #E8F0F5}.ss-history-table th{background:#F5FAFD;color:#536B7D;font-size:12px}.ss-history-table td{font-size:13px;color:#2F4D63}.ss-history-table tr:last-child td{border-bottom:0}
      .ss-history-mobile{display:none;margin-top:12px}.ss-history-row-card{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:13px 14px;border:1px solid #E2EDF4;border-radius:14px;background:#FAFCFE;margin-bottom:9px}.ss-history-date{font-weight:800;color:#24445F;font-size:13px}.ss-history-state{display:flex;align-items:center;gap:8px}.ss-history-state .emoji{font-size:24px}.ss-history-state strong{font-size:13px;color:#35556F}
      .ss-empty-checkins{text-align:center;padding:20px;color:#738798;border:1px dashed #D7E6F1;border-radius:14px;margin-top:12px}.ss-login-needed{text-align:center;max-width:520px;margin:40px auto}.ss-checkin-icon{font-size:42px;margin-bottom:8px}
      @media(max-width:640px){.ss-checkin-shell{padding:4px 0 20px}.ss-checkin-card{padding:18px 15px;border-radius:18px;margin-bottom:14px}.ss-mood-grid{grid-template-columns:repeat(5,minmax(0,1fr));gap:6px}.ss-mood-option{min-height:88px;padding:9px 4px;border-radius:13px}.ss-mood-option .emoji{font-size:26px}.ss-mood-option .label{font-size:10px}.ss-summary-grid{grid-template-columns:1fr}.ss-history-table{display:none}.ss-history-mobile{display:block}}
      @media(max-width:370px){.ss-mood-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.ss-mood-option:nth-child(4),.ss-mood-option:nth-child(5){min-height:82px}}
    </style>
    <main class="ss-checkin-shell">
      <section class="ss-checkin-card">
        <h1>__TITLE__</h1>
        <p class="muted">__SUB__</p>
        <div class="ss-checkin-question">__QUESTION__</div>
        <div class="ss-mood-grid" id="moodGrid" role="radiogroup" aria-label="__QUESTION__">
          <button type="button" class="ss-mood-option" data-rating="1" role="radio" aria-checked="false"><span class="emoji">😞</span><span class="label">__V1__</span></button>
          <button type="button" class="ss-mood-option" data-rating="2" role="radio" aria-checked="false"><span class="emoji">😕</span><span class="label">__V2__</span></button>
          <button type="button" class="ss-mood-option" data-rating="3" role="radio" aria-checked="false"><span class="emoji">😐</span><span class="label">__V3__</span></button>
          <button type="button" class="ss-mood-option" data-rating="4" role="radio" aria-checked="false"><span class="emoji">🙂</span><span class="label">__V4__</span></button>
          <button type="button" class="ss-mood-option" data-rating="5" role="radio" aria-checked="false"><span class="emoji">😊</span><span class="label">__V5__</span></button>
        </div>
        <div class="ss-today-note" id="todayNote"></div>
        <button type="button" class="ss-checkin-save" id="saveCheckin" disabled>__SAVE__</button>
        <div id="ciMsg" class="ss-checkin-msg" aria-live="polite"></div>
      </section>

      <section class="ss-checkin-card" id="summaryCard">
        <h2>__SUMMARY__</h2>
        <div class="ss-summary-grid">
          <div class="ss-summary-item"><span>__TODAY__</span><strong id="sumToday">—</strong></div>
          <div class="ss-summary-item"><span>__WEEK__</span><strong id="sumWeek">—</strong></div>
          <div class="ss-summary-item"><span>__COUNT__</span><strong id="sumCount">0</strong></div>
        </div>
      </section>

      <section class="ss-checkin-card">
        <h2>__HISTORY__</h2>
        <div id="historyEmpty" class="ss-empty-checkins" hidden>__EMPTY__</div>
        <table class="ss-history-table" id="historyTable" hidden>
          <thead><tr><th>__DATE__</th><th>__STATUS__</th><th>__RATING__</th></tr></thead>
          <tbody id="historyBody"></tbody>
        </table>
        <div class="ss-history-mobile" id="historyMobile"></div>
      </section>
    </main>
    <script>
    (function(){
      const AR=__AR__;
      const labels={1:__L1__,2:__L2__,3:__L3__,4:__L4__,5:__L5__};
      const emoji={1:'😞',2:'😕',3:'😐',4:'🙂',5:'😊'};
      const text={save:__SAVE_JS__,update:__UPDATE_JS__,todaySaved:__TODAY_SAVED__,saved:__SAVED__,updated:__UPDATED__,error:__ERROR__};
      const today=(function(){const d=new Date(),pad=n=>String(n).padStart(2,'0');return d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate());})();
      let selected=null,todayRecord=null;
      const options=[...document.querySelectorAll('.ss-mood-option')],save=document.getElementById('saveCheckin'),msg=document.getElementById('ciMsg');
      function setSelected(v){selected=Number(v);options.forEach(b=>{const on=Number(b.dataset.rating)===selected;b.classList.toggle('selected',on);b.setAttribute('aria-checked',on?'true':'false')});save.disabled=!selected;save.textContent=todayRecord?text.update:text.save;}
      options.forEach(b=>b.addEventListener('click',()=>setSelected(b.dataset.rating)));
      function stateText(v){v=Number(v);return (emoji[v]||'')+' '+(labels[v]||v);}
      function formatDate(s){try{return new Intl.DateTimeFormat(AR?'ar-SA-u-ca-gregory':'en-GB',{day:'numeric',month:'long',year:'numeric'}).format(new Date(s+'T12:00:00'));}catch(e){return s}}
      function render(d){
        const rows=Array.isArray(d.rows)?d.rows:[];todayRecord=d.today||null;
        if(todayRecord){setSelected(todayRecord.value);const note=document.getElementById('todayNote');note.classList.add('show');note.textContent=text.todaySaved+' '+stateText(todayRecord.value);}
        else{document.getElementById('todayNote').classList.remove('show');save.textContent=text.save;}
        document.getElementById('sumToday').textContent=todayRecord?stateText(todayRecord.value):'—';
        document.getElementById('sumCount').textContent=String(d.summary&&d.summary.count!=null?d.summary.count:rows.length);
        const avg=d.summary&&d.summary.last7_average;document.getElementById('sumWeek').textContent=avg?stateText(Math.max(1,Math.min(5,Math.round(avg))))+' ('+avg+')':'—';
        const empty=document.getElementById('historyEmpty'),table=document.getElementById('historyTable'),tbody=document.getElementById('historyBody'),mobile=document.getElementById('historyMobile');
        tbody.innerHTML='';mobile.innerHTML='';
        if(!rows.length){empty.hidden=false;table.hidden=true;return;}empty.hidden=true;table.hidden=false;
        rows.forEach(r=>{const v=Number(r.value);const tr=document.createElement('tr');tr.innerHTML='<td>'+formatDate(r.date)+'</td><td><span style="font-size:20px">'+emoji[v]+'</span></td><td>'+labels[v]+'</td>';tbody.appendChild(tr);const card=document.createElement('div');card.className='ss-history-row-card';card.innerHTML='<div class="ss-history-date">'+formatDate(r.date)+'</div><div class="ss-history-state"><span class="emoji">'+emoji[v]+'</span><strong>'+labels[v]+'</strong></div>';mobile.appendChild(card);});
      }
      async function load(){try{const r=await fetch('/api/checkin?date='+encodeURIComponent(today),{headers:{'Accept':'application/json'}});const d=await r.json();if(r.status===401){location.href='/login?next=/checkin';return;}if(!r.ok||!d.ok){const err=new Error(d.error||'load_failed');err.requestId=d.request_id||'';throw err;}render(d);}catch(e){msg.className='ss-checkin-msg err';msg.textContent=text.error+(e.requestId?(' · '+e.requestId):'');}}
      save.addEventListener('click',async function(){if(!selected)return;save.disabled=true;msg.textContent='';try{const r=await fetch('/api/checkin',{method:'POST',headers:{'Content-Type':'application/json','Accept':'application/json'},body:JSON.stringify({rating:selected,date:today})});const d=await r.json();if(d.consent_required&&d.consent_url){location.href=d.consent_url;return;}if(r.status===401){location.href='/login?next=/checkin';return;}if(!r.ok||!d.ok){const err=new Error(d.error||'save_failed');err.requestId=d.request_id||'';throw err;}msg.className='ss-checkin-msg ok';msg.textContent=d.created?text.saved:text.updated;render(d);}catch(e){msg.className='ss-checkin-msg err';msg.textContent=text.error+(e.requestId?(' · '+e.requestId):'');}finally{save.disabled=!selected;}});
      load();
    })();
    </script>
    '''
    repl={
      '__TITLE__':labels['title'],'__SUB__':labels['sub'],'__QUESTION__':labels['question'],'__SAVE__':labels['save'],
      '__V1__':labels['very_bad'],'__V2__':labels['bad'],'__V3__':labels['medium'],'__V4__':labels['good'],'__V5__':labels['excellent'],
      '__SUMMARY__':labels['summary'],'__TODAY__':labels['today'],'__WEEK__':labels['week'],'__COUNT__':labels['count'],'__HISTORY__':labels['history'],
      '__DATE__':labels['date'],'__STATUS__':labels['status'],'__RATING__':labels['rating'],'__EMPTY__':labels['empty'],
      '__AR__':'true' if ar else 'false','__L1__':json.dumps(labels['very_bad'],ensure_ascii=False),'__L2__':json.dumps(labels['bad'],ensure_ascii=False),'__L3__':json.dumps(labels['medium'],ensure_ascii=False),'__L4__':json.dumps(labels['good'],ensure_ascii=False),'__L5__':json.dumps(labels['excellent'],ensure_ascii=False),
      '__SAVE_JS__':json.dumps(labels['save'],ensure_ascii=False),'__UPDATE_JS__':json.dumps(labels['update'],ensure_ascii=False),'__TODAY_SAVED__':json.dumps(labels['today_saved'],ensure_ascii=False),'__SAVED__':json.dumps(labels['saved'],ensure_ascii=False),'__UPDATED__':json.dumps(labels['updated'],ensure_ascii=False),'__ERROR__':json.dumps(labels['error'],ensure_ascii=False),
    }
    for k,v in repl.items(): body=body.replace(k,v)
    return _page(_t("title_checkin"), body)

# ---------------------------------------------------------------- routes
@app.route("/")
def index():
    """Always keep the public root as the language-selection landing page.

    The selected language is still stored and used throughout the site, but a
    previous choice must not silently skip the landing screen when the visitor
    opens the main site URL again.
    """
    return welcome_page()


@app.route("/home")
def home():
    # Older installed PWA versions used /home?source=pwa as their start URL.
    # Send those launches through the picker too, without affecting normal
    # navigation to /home after a language has been selected.
    if request.args.get("source") == "pwa":
        return redirect(url_for("index", next="/home"))
    return home_page()


@app.route("/about")
def about():
    # Keep the legacy URL working, but use the single personal About Us experience.
    return redirect(url_for("about_us"))


@app.route("/about-us")
def about_us():
    return about_us_page()


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


@app.route("/sources")
def sources():
    return sources_page()


@app.route("/chat")
def chat():
    if not _service_consent_ok():
        return redirect(url_for("consent", next="/chat"))
    return chat_page()


@app.route("/blood")
def blood():
    return blood_page()


@app.route("/meds")
def meds():
    # Keep the page reachable so users can inspect/delete already-stored data.
    # Creating or modifying sensitive reminder data is consent-gated server-side.
    return meds_page()


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


@app.route("/manage")
@login_required
def manage_page():
    db.init_db()
    uid = _ss_user_id()
    user = db.get_ss_user(uid)
    hp = db.load_health_profile(uid) or {}
    lang = _lang()
    t = L.get(lang, L["ar"])
    def esc(s):
        return (str(s) or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    age = ""
    if hp.get("dob"):
        try:
            from datetime import date
            born = date.fromisoformat(hp["dob"])
            today = date.today()
            age = str(today.year - born.year - ((today.month, today.day) < (born.month, born.day)))
        except Exception:
            pass
    gender_map = {"male": "ذكر", "female": "أنثى", "ذكر": "ذكر", "أنثى": "أنثى"}
    gender_label = gender_map.get(hp.get("gender", ""), hp.get("gender", ""))
    fields = [
        {"key": "display_name", "icon": "📛", "label": t.get("profile_name", "الاسم"), "value": hp.get("display_name", user.get("name", ""))},
        {"key": "dob", "icon": "🎂", "label": t.get("profile_dob", "تاريخ الميلاد"), "value": hp.get("dob", "") + (" (%s سنة)" % age if age else "")},
        {"key": "gender", "icon": "⚧", "label": t.get("profile_gender", "الجنس"), "value": gender_label},
        {"key": "height", "icon": "📏", "label": t.get("profile_height", "الطول"), "value": hp.get("height", "") + (" cm" if hp.get("height") else "")},
        {"key": "weight", "icon": "⚖️", "label": t.get("profile_weight", "الوزن"), "value": hp.get("weight", "") + (" kg" if hp.get("weight") else "")},
        {"key": "medications", "icon": "💊", "label": t.get("profile_meds", "الأدوية"), "value": hp.get("medications", "")},
        {"key": "allergies", "icon": "⚠️", "label": t.get("profile_allergies", "الحساسيات"), "value": hp.get("allergies", "")},
        {"key": "health_conditions", "icon": "🩺", "label": t.get("profile_conditions", "الحالات الصحية"), "value": hp.get("health_conditions", "")},
        {"key": "extra_info", "icon": "📝", "label": t.get("profile_extra", "معلومات إضافية"), "value": hp.get("extra_info", "")},
    ]
    cards_html = ""
    for f in fields:
        val_display = esc(f["value"]) if f["value"] else '<span style="color:#94A3B8;font-style:italic;">' + (t.get("manage_not_set", "غير محدد") if lang == "ar" else "Not set") + '</span>'
        cards_html += '''<div class="manage-card" id="card_%s">
        <div class="manage-card-head"><span class="manage-icon">%s</span><span class="manage-label">%s</span></div>
        <div class="manage-val" id="val_%s">%s</div>
        <div class="manage-actions">
          <button class="manage-edit-btn" onclick="editField('%s')">✏️ %s</button>
          <button class="manage-del-btn" onclick="deleteField('%s', '%s')">🗑️ %s</button>
        </div>
      </div>''' % (f["key"], f["icon"], esc(f["label"]), f["key"], val_display, f["key"], t.get("manage_edit", "تعديل") if lang == "ar" else "Edit", f["key"], esc(f["label"]), t.get("manage_delete", "حذف") if lang == "ar" else "Delete")
    title = t.get("manage_title", "إدارة معلوماتي") if lang == "ar" else "Manage My Info"
    subtitle = t.get("manage_subtitle", "تحكم بالمعلومات المحفوظة في حسابك. يمكنك تعديلها أو حذف أي معلومة في أي وقت.") if lang == "ar" else "Control the information saved in your account. Edit or delete any info anytime."
    delete_all_btn = t.get("manage_delete_all", "🧹 حذف جميع معلوماتي") if lang == "ar" else "🧹 Delete All My Info"
    delete_confirm = t.get("manage_delete_confirm", "هل أنت متأكد؟ سيؤدي ذلك إلى حذف جميع المعلومات الصحية المحفوظة.") if lang == "ar" else "Are you sure? This will delete all saved health information."
    delete_type = t.get("manage_delete_type", "اكتب 'حذف' للتأكيد") if lang == "ar" else "Type 'delete' to confirm"
    save_msg_ok = t.get("manage_saved", "✅ تم الحفظ بنجاح") if lang == "ar" else "✅ Saved successfully"
    save_msg_err = t.get("manage_error", "❌ حدث خطأ") if lang == "ar" else "❌ Error occurred"
    deleted_msg = t.get("manage_deleted", "✅ تم الحذف بنجاح") if lang == "ar" else "✅ Deleted successfully"
    body = '''
    <div style="max-width:640px;margin:0 auto;padding:0;">
      <div class="ss-profile-card" style="text-align:center;">
        <div style="font-size:42px;margin-bottom:8px;">🧹</div>
        <h2 style="justify-content:center;">''' + title + '''</h2>
        <p class="muted">''' + subtitle + '''</p>
      </div>
      <div id="manageCards">''' + cards_html + '''</div>
      <div style="margin-top:24px;padding:20px;background:#FEF2F2;border-radius:16px;border:1px solid #FECACA;">
        <h3 style="color:#DC2626;margin:0 0 8px 0;">''' + delete_all_btn + '''</h3>
        <p style="color:#7F1D1D;font-size:14px;margin:0 0 12px 0;">''' + delete_confirm + '''</p>
        <button onclick="showDeleteAll()" class="ss-btn-danger" style="width:100%;">''' + delete_all_btn + '''</button>
      </div>
      <div id="deleteAllModal" style="display:none;position:fixed;inset:0;z-index:1003;background:rgba(15,23,42,.55);align-items:center;justify-content:center;padding:18px;">
        <div style="background:#fff;border-radius:18px;padding:24px;max-width:400px;width:100%;box-shadow:0 30px 80px rgba(0,0,0,.35);">
          <h3 style="margin:0 0 12px;color:#DC2626;">⚠️ ''' + delete_confirm + '''</h3>
          <p style="color:#5F7185;font-size:14px;">''' + delete_type + '''</p>
          <input type="text" id="deleteConfirmInput" style="width:100%;padding:12px;border:2px solid #DCEBFA;border-radius:12px;margin:12px 0;font-size:16px;" placeholder="''' + ('حذف' if lang == 'ar' else 'delete') + '''">
          <div style="display:flex;gap:8px;">
            <button onclick="closeDeleteAll()" style="flex:1;padding:12px;border:2px solid #DCEBFA;border-radius:12px;background:#fff;color:#40566F;font-weight:600;cursor:pointer;">''' + (t.get("profile_cancel", "إلغاء") if lang == "ar" else "Cancel") + '''</button>
            <button onclick="confirmDeleteAll()" id="deleteAllConfirmBtn" disabled style="flex:1;padding:12px;border:none;border-radius:12px;background:#DC2626;color:#fff;font-weight:600;cursor:pointer;opacity:0.5;">''' + (t.get("profile_delete_btn", "حذف") if lang == "ar" else "Delete") + '''</button>
          </div>
        </div>
      </div>
    </div>
    <script>
    var LANG_M = "''' + lang + '''";
    var FIELDS_M = ''' + str([{"key": f["key"], "label": f["label"]} for f in fields]) + ''';
    function editField(key) {
      var valEl = document.getElementById('val_' + key);
      var current = valEl.textContent.trim();
      if (current === ' ''' + (t.get("manage_not_set", "غير محدد") if lang == "ar" else "Not set") + '''') current = '';
      valEl.innerHTML = '<input type="text" id="edit_' + key + '" value="' + current.replace(/"/g, '&quot;') + '" style="width:100%;padding:10px;border:2px solid #1976D2;border-radius:10px;font-size:15px;margin:4px 0;">' +
        '<div style="display:flex;gap:8px;margin-top:8px;">' +
        '<button onclick="saveField(\\'' + key + '\\')" style="flex:1;padding:10px;background:#1976D2;color:#fff;border:none;border-radius:10px;font-weight:700;cursor:pointer;">✅ ' + (LANG_M==='ar'?'حفظ':'Save') + '</button>' +
        '<button onclick="cancelEdit(\\'' + key + '\\', \\'' + current.replace(/'/g, "\\\\'") + '\\')" style="flex:1;padding:10px;background:#EAF4FF;color:#123B70;border:1px solid #DCEBFA;border-radius:10px;font-weight:600;cursor:pointer;">✕ ' + (LANG_M==='ar'?'إلغاء':'Cancel') + '</button>' +
        '</div>';
      document.getElementById('edit_' + key).focus();
    }
    function cancelEdit(key, orig) {
      var valEl = document.getElementById('val_' + key);
      valEl.innerHTML = orig || '<span style="color:#94A3B8;font-style:italic;">''' + (t.get("manage_not_set", "غير محدد") if lang == "ar" else "Not set") + '''</span>';
    }
    async function saveField(key) {
      var inp = document.getElementById('edit_' + key);
      var val = inp ? inp.value.trim() : '';
      var r = await fetch('/api/health-profile/field', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({field:key, value:val})});
      var d = await r.json();
      if (d.ok) {
        var valEl = document.getElementById('val_' + key);
        valEl.innerHTML = val || '<span style="color:#94A3B8;font-style:italic;">''' + (t.get("manage_not_set", "غير محدد") if lang == "ar" else "Not set") + '''</span>';
        showManageMsg("''' + save_msg_ok + '''", "success");
      } else {
        showManageMsg("''' + save_msg_err + '''", "error");
      }
    }
    async function deleteField(key, label) {
      var c = LANG_M==='ar' ? 'هل أنت متأكد من حذف ' + label + '؟' : 'Are you sure you want to delete ' + label + '?';
      if (!confirm(c)) return;
      var r = await fetch('/api/health-profile/field/delete', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({field:key})});
      var d = await r.json();
      if (d.ok) {
        var valEl = document.getElementById('val_' + key);
        valEl.innerHTML = '<span style="color:#94A3B8;font-style:italic;">''' + (t.get("manage_not_set", "غير محدد") if lang == "ar" else "Not set") + '''</span>';
        showManageMsg("''' + deleted_msg + '''", "success");
      }
    }
    function showDeleteAll() { document.getElementById('deleteAllModal').style.display = 'flex'; }
    function closeDeleteAll() { document.getElementById('deleteAllModal').style.display = 'none'; document.getElementById('deleteConfirmInput').value = ''; document.getElementById('deleteAllConfirmBtn').disabled = true; document.getElementById('deleteAllConfirmBtn').style.opacity = '0.5'; }
    document.addEventListener('DOMContentLoaded', function(){
      var inp = document.getElementById('deleteConfirmInput');
      if (inp) inp.addEventListener('input', function(){
        var btn = document.getElementById('deleteAllConfirmBtn');
        var match = LANG_M==='ar' ? (this.value.trim()==='حذف') : (this.value.trim().toLowerCase()==='delete');
        btn.disabled = !match;
        btn.style.opacity = match ? '1' : '0.5';
      });
    });
    async function confirmDeleteAll() {
      var r = await fetch('/api/health-profile/delete', {method:'POST'});
      var d = await r.json();
      if (d.ok) { window.location.href = '/profile'; }
    }
    function showManageMsg(msg, type) {
      var d = document.createElement('div');
      d.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);z-index:9999;padding:12px 24px;border-radius:12px;font-weight:700;font-size:14px;' + (type==='success' ? 'background:#DCFCE7;color:#166534;border:1px solid #BBF7D0;' : 'background:#FEE2E2;color:#991B1B;border:1px solid #FECACA;');
      d.textContent = msg;
      document.body.appendChild(d);
      setTimeout(function(){ d.remove(); }, 2000);
    }
    </script>
    '''
    return _page(title, body)


@app.route("/memory")
@login_required
def memory_page():
    db.init_db()
    uid = _ss_user_id()
    user = db.get_ss_user(uid)
    hp = db.load_health_profile(uid) or {}
    privacy = db.load_privacy_settings(uid) or {}
    lang = _lang()
    t = L.get(lang, L["ar"])
    def esc(s):
        return (str(s) or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    title = t.get("memory_title", "ذاكرتي مع SymptoSense") if lang == "ar" else "My Memory With You"
    subtitle = t.get("memory_subtitle", "المعلومات التي تسمح للمساعد باستخدامها لتخصيص تجربتك.") if lang == "ar" else "Information you allow the assistant to use to personalize your experience."
    control_text = t.get("memory_control", "أنت المتحكم — تستطيع رؤية أي معلومة محفوظة، تعديلها أو حذفها في أي وقت.") if lang == "ar" else "You're in control — see any saved info, edit or delete it anytime."
    add_btn = t.get("memory_add", "➕ إضافة معلومة") if lang == "ar" else "➕ Add Information"
    manage_btn = t.get("memory_manage", "🧹 إدارة ذاكرتي") if lang == "ar" else "🧹 Manage My Memory"
    source_profile = t.get("memory_source_profile", "من ملفك الشخصي") if lang == "ar" else "From your profile"
    source_chat = t.get("memory_source_chat", "ذكرتها في هذه المحادثة") if lang == "ar" else "Mentioned in this chat"
    source_memory = t.get("memory_source_memory", "حفظتها في ذاكرتي") if lang == "ar" else "Saved in my memory"
    source_unknown = t.get("memory_source_unknown", "غير معروفة") if lang == "ar" else "Unknown"
    items_html = ""
    mem_items = []
    fields_map = [
        ("display_name", "📛", t.get("profile_name", "الاسم")),
        ("dob", "🎂", t.get("profile_dob", "تاريخ الميلاد")),
        ("gender", "⚧", t.get("profile_gender", "الجنس")),
        ("height", "📏", t.get("profile_height", "الطول")),
        ("weight", "⚖️", t.get("profile_weight", "الوزن")),
        ("medications", "💊", t.get("profile_meds", "الأدوية")),
        ("allergies", "⚠️", t.get("profile_allergies", "الحساسيات")),
        ("health_conditions", "🩺", t.get("profile_conditions", "الحالات الصحية")),
        ("extra_info", "📝", t.get("profile_extra", "معلومات إضافية")),
    ]
    for key, icon, label in fields_map:
        val = hp.get(key, "")
        if val:
            source = source_profile
            source_color = "#1976D2"
            source_bg = "#EAF4FF"
            mem_items.append({"key": key, "icon": icon, "label": label, "value": val, "source": source, "source_color": source_color, "source_bg": source_bg})
    for item in mem_items:
        items_html += '''<div class="memory-card">
        <div class="memory-card-head"><span class="memory-icon">%s</span><span class="memory-label">%s</span></div>
        <div class="memory-val">%s</div>
        <div class="memory-source" style="color:%s;background:%s;">🔵 %s</div>
        <div class="memory-actions">
          <a href="/manage" style="flex:1;text-align:center;padding:10px;border:2px solid #DCEBFA;border-radius:10px;text-decoration:none;font-weight:600;color:#123B70;font-size:14px;">✏️ %s</a>
        </div>
      </div>''' % (item["icon"], esc(item["label"]), esc(item["value"]), item["source_color"], item["source_bg"], item["source"], t.get("manage_edit", "تعديل") if lang == "ar" else "Edit")
    if not mem_items:
        items_html = '<div style="text-align:center;padding:32px;color:#94A3B8;"><p style="font-size:40px;margin-bottom:8px;">🧠</p><p>' + (t.get("memory_empty", "لا توجد معلومات محفوظة بعد.") if lang == "ar" else "No saved information yet.") + '</p><p style="font-size:13px;">' + (t.get("memory_empty_sub", "عندما تشارك معلومات مع المساعد، يمكن حفظها هنا.") if lang == "ar" else "When you share information with the assistant, it can be saved here.") + '</p></div>'
    legend_html = '''<div class="memory-legend">
      <div class="memory-legend-item"><span class="memory-dot" style="background:#1976D2;"></span> %s</div>
      <div class="memory-legend-item"><span class="memory-dot" style="background:#64B5F6;"></span> %s</div>
      <div class="memory-legend-item"><span class="memory-dot" style="background:#B8D8F8;"></span> %s</div>
      <div class="memory-legend-item"><span class="memory-dot" style="background:#94A3B8;"></span> %s</div>
    </div>''' % (source_profile, source_chat, source_memory, source_unknown)
    body = '''
    <div style="max-width:640px;margin:0 auto;padding:0;">
      <div class="ss-profile-card" style="text-align:center;">
        <div style="font-size:42px;margin-bottom:8px;">🧠</div>
        <h2 style="justify-content:center;">''' + title + '''</h2>
        <p class="muted">''' + subtitle + '''</p>
        <div style="margin-top:12px;padding:12px 16px;background:#EAF4FF;border-radius:12px;border:1px solid #DCEBFA;font-size:13px;color:#123B70;">🔐 ''' + control_text + '''</div>
      </div>
      ''' + legend_html + '''
      <div id="memoryItems">''' + items_html + '''</div>
      <div style="margin-top:16px;text-align:center;">
        <a href="/manage" style="display:inline-block;padding:14px 24px;background:#1976D2;color:#fff;border-radius:12px;text-decoration:none;font-weight:700;width:100%;text-align:center;">''' + manage_btn + '''</a>
      </div>
    </div>
    '''
    return _page(title, body)


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
        cards.append(f'''<article class="history-card">
          <div class="history-card-top"><div><small>{date}</small><h3>{symptoms}</h3></div><span class="risk-pill {risk_cls}">{risk_label}</span></div>
          <p class="muted">{'المدة' if ar else 'Duration'}: {duration}</p>
          <div class="history-actions"><a class="btn ghost" href="/history/{int(row['id'])}">{'عرض التحليل' if ar else 'View Analysis'}</a><button class="btn ghost danger-lite" onclick="deleteAnalysis({int(row['id'])})">{'حذف' if ar else 'Delete'}</button></div>
        </article>''')
    body='''
    <main class="history-shell">
      <section class="history-heading"><div><span class="eyebrow">📜 __TITLE__</span><h1>__H1__</h1><p>__SUB__</p></div><a class="btn primary" href="/chat">__NEW__</a></section>
      <section class="history-grid">__CARDS__</section>
    </main>
    <style>
    .history-shell{max-width:980px;margin:auto;display:grid;gap:16px}.history-heading,.history-card{background:#fff;border:1px solid var(--v2-line);border-radius:20px;box-shadow:var(--v2-shadow)}.history-heading{padding:24px;display:flex;justify-content:space-between;gap:20px;align-items:center}.history-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.history-card{padding:18px}.history-card-top{display:flex;justify-content:space-between;gap:14px;align-items:flex-start}.history-card h3{margin:5px 0 0;font-size:17px}.history-card small{color:var(--v2-muted)}.risk-pill{padding:6px 10px;border-radius:999px;font-size:12px;font-weight:800;white-space:nowrap}.risk-pill.low{background:var(--v2-green-bg);color:var(--v2-green)}.risk-pill.medium{background:#FFF6DB;color:#8A6400}.risk-pill.high{background:#FDECEC;color:var(--v2-red)}.history-actions{display:flex;gap:8px;margin-top:14px}.danger-lite{color:var(--v2-red)!important;border-color:#efcaca!important}@media(max-width:700px){.history-grid{grid-template-columns:1fr}.history-heading{flex-direction:column;align-items:stretch}.history-card-top{flex-direction:column}}
    </style>
    <script>async function deleteAnalysis(id){if(!confirm(__CONFIRM__))return;const r=await fetch('/api/analysis/'+id,{method:'DELETE'});if(r.ok)location.reload();else alert(__ERROR__);}</script>
    '''
    body=body.replace('__TITLE__',title).replace('__H1__','تحليلاتي السابقة' if ar else 'My previous analyses').replace('__SUB__','هذه النتائج خاصة بحسابك ولا يستطيع مستخدم آخر فتحها.' if ar else 'These results are private to your account and cannot be opened by another user.').replace('__NEW__','تحليل جديد' if ar else 'New analysis').replace('__CARDS__',''.join(cards)).replace('__CONFIRM__',json.dumps('هل تريد حذف هذا التحليل؟ لا يمكن التراجع عن الحذف.' if ar else 'Delete this analysis? This cannot be undone.')).replace('__ERROR__',json.dumps('تعذر حذف التحليل.' if ar else 'Unable to delete the analysis.'))
    return _page(title, body)


def analysis_detail_page(record_id):
    """Render one stored analysis only when it belongs to the authenticated user."""
    ar=_lang()=="ar"
    row=advanced_features.get_user_analysis(_data_user_id(), record_id)
    if not row:
        abort(404)
    from html import escape
    result=row.get('result') or {}
    risk=(result.get('risk_level') or row.get('urgency') or 'low').lower()
    risk_map={
      'low':('منخفض' if ar else 'Low risk','low'),
      'medium':('يحتاج متابعة' if ar else 'Needs follow-up','medium'),
      'high':('عاجل' if ar else 'Urgent','high'),
      'urgent':('عاجل' if ar else 'Urgent','high'),
    }
    risk_label,risk_cls=risk_map.get(risk,(escape(str(risk)),'medium'))
    syms=''.join('<span class="sym-chip">%s</span>'%escape(str(x)) for x in (row.get('symptoms') or [])) or '<span>—</span>'
    dq=result.get('data_quality') or {}
    dq_html=''
    if isinstance(dq,dict) and dq.get('score') is not None:
        score=max(0,min(100,int(round(float(dq.get('score') or 0)))))
        level=escape(str(dq.get('level_label') or dq.get('level') or ''))
        dq_html=f'''<section class="detail-card"><div class="section-head"><h2>📊 {'جودة المعلومات' if ar else 'Data Quality'}</h2><b>{score}% · {level}</b></div><div class="detail-progress"><span style="width:{score}%"></span></div><p class="muted">{'يقيس هذا اكتمال المعلومات المتاحة للتحليل فقط، وليس احتمال مرض أو دقة تشخيص.' if ar else 'This measures information completeness only, not disease probability or diagnostic accuracy.'}</p></section>'''
    xai=result.get('explainability') or {}
    xai_html=''
    if isinstance(xai,dict) and xai:
        factors=[]
        for f in (xai.get('factors') or [])[:8]:
            if not isinstance(f,dict): continue
            label=escape(str(f.get('label') or f.get('feature') or '—'))
            influence=escape(str(f.get('influence_label') or f.get('influence') or ''))
            reason=escape(str(f.get('detail') or f.get('explanation') or f.get('reason') or ''))
            factors.append(f'<li><b>{label}</b><span>{influence}</span><small>{reason}</small></li>')
        if factors:
            xai_html=f'''<details class="detail-card xai-detail"><summary>🔍 {'لماذا ظهر هذا التقييم؟' if ar else 'Why this assessment?'}</summary><p class="muted">{'يعرض هذا العوامل التي ساهمت في قواعد السلامة والمطابقة المعرفية الفعلية، وليس أسبابًا طبية مؤكدة.' if ar else 'This shows factors that contributed to the actual safety and knowledge-matching logic, not confirmed medical causes.'}</p><ul>{''.join(factors)}</ul><p class="notice">{'العوامل المعروضة لا تؤكد تشخيصًا ولا تحدد سبب الأعراض.' if ar else 'The factors shown do not confirm a diagnosis or identify the cause of symptoms.'}</p></details>'''
    poss=escape(str(result.get('possible_conditions') or ''))
    poss_html=f'<section class="detail-card"><h2>🩺 {"الاحتمالات المعلوماتية" if ar else "Informational possibilities"}</h2><p>{poss}</p></section>' if poss else ''
    sources=[]
    for src in (result.get('medical_sources') or []):
        if not isinstance(src,dict): continue
        name=escape(str(src.get('source_name') or src.get('name') or src.get('organization') or 'Source'))
        url=str(src.get('official_url') or src.get('url') or '')
        link=f'<a href="{escape(url)}" target="_blank" rel="noopener noreferrer">{name}</a>' if url.startswith(('https://','http://')) else name
        sources.append(f'<li>{link}</li>')
    sources_html=f'''<section class="detail-card"><h2>📚 {'المصادر الطبية' if ar else 'Medical Sources'}</h2><ul class="source-list">{''.join(sources)}</ul></section>''' if sources else ''
    date=escape(str(row.get('timestamp') or '—'))[:19].replace('T',' ')
    duration=escape(str(row.get('duration') or '—')); severity=escape(str(row.get('severity') if row.get('severity') is not None else '—'))
    body=f'''
    <main class="analysis-detail-shell">
      <div class="detail-nav"><a href="/history">← {'العودة للسجل' if ar else 'Back to history'}</a></div>
      <section class="detail-hero"><div><span class="eyebrow">🩺 {'نتيجة التقييم' if ar else 'Assessment Result'}</span><h1>{date}</h1></div><span class="risk-pill {risk_cls}">{risk_label}</span></section>
      <section class="detail-card"><h2>{'الأعراض التي أدخلتها' if ar else 'Reported symptoms'}</h2><div class="sym-list">{syms}</div><div class="mini-grid"><div><small>{'المدة' if ar else 'Duration'}</small><b>{duration}</b></div><div><small>{'الشدة' if ar else 'Severity'}</small><b>{severity}</b></div></div></section>
      {dq_html}{poss_html}{xai_html}{sources_html}
      <section class="detail-card notice"><b>⚠️ {'تنبيه' if ar else 'Important notice'}</b><p>{'هذه المعلومات للتوعية ولا تُعد تشخيصًا طبيًا أو بديلًا عن استشارة الطبيب.' if ar else 'This information is for educational purposes and is not a medical diagnosis or a substitute for professional medical advice.'}</p></section>
    </main>
    <style>.analysis-detail-shell{{max-width:900px;margin:auto;display:grid;gap:14px}}.detail-nav a{{color:var(--v2-blue);font-weight:700}}.detail-hero,.detail-card{{background:#fff;border:1px solid var(--v2-line);border-radius:20px;padding:clamp(18px,3vw,24px);box-shadow:var(--v2-shadow)}}.detail-hero{{display:flex;justify-content:space-between;align-items:center;gap:18px}}.eyebrow{{color:var(--v2-blue);font-weight:800}}.risk-pill{{padding:7px 11px;border-radius:999px;font-size:12px;font-weight:800}}.risk-pill.low{{background:var(--v2-green-bg);color:var(--v2-green)}}.risk-pill.medium{{background:#FFF6DB;color:#8A6400}}.risk-pill.high{{background:#FDECEC;color:var(--v2-red)}}.sym-list{{display:flex;flex-wrap:wrap;gap:8px}}.sym-chip{{background:var(--v2-sky);border:1px solid var(--v2-line);border-radius:999px;padding:7px 10px}}.mini-grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:14px}}.mini-grid>div{{background:var(--v2-bg);border-radius:12px;padding:12px;display:grid;gap:4px}}.mini-grid small,.xai-detail small{{color:var(--v2-muted)}}.detail-progress{{height:9px;background:#EAF0F4;border-radius:999px;overflow:hidden}}.detail-progress span{{display:block;height:100%;background:var(--v2-blue);border-radius:999px}}.section-head{{display:flex;justify-content:space-between;gap:14px}}.xai-detail summary{{cursor:pointer;font-weight:800;font-size:18px}}.xai-detail li{{display:grid;grid-template-columns:1fr auto;gap:6px;padding:10px 0;border-bottom:1px solid var(--v2-line)}}.xai-detail li small{{grid-column:1/-1}}.source-list{{display:grid;gap:8px}}.notice{{background:#F8FBFE}}@media(max-width:600px){{.detail-hero,.section-head{{align-items:flex-start;flex-direction:column}}.mini-grid{{grid-template-columns:1fr}}}}</style>
    '''
    return _page('نتيجة التحليل' if ar else 'Analysis Result', body)


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
    return redirect(url_for("history"))


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
    if any(brevo_values.values()):
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
    if any(smtp_values.values()):
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
        except Exception: pass
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


def _send_auth_email(email, subject, html, category="auth"):
    """Send transactional auth email through configured SMTP or Resend."""
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
    if state.get("provider")=="brevo":
        return _send_auth_email_brevo(email,subject,html,category)
    if state.get("provider")=="smtp":
        return _send_auth_email_smtp(email,subject,html,category,state)
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
                "tags": [{"name":"category","value":re.sub(r"[^A-Za-z0-9_-]", "_", category)[:64] or "auth"}],
            },
        )
        if response.status_code < 300:
            app.logger.info("Auth email accepted by provider; category=%s status=%s", category, response.status_code)
            return True, None
        safe_error, provider_code=_classify_resend_error(response)
        app.logger.warning("Auth email provider rejected request; category=%s status=%s provider_code=%s diagnostic=%s", category, response.status_code, provider_code, safe_error)
        return False, safe_error
    except Exception as exc:
        app.logger.warning("Auth email send failed; category=%s error_type=%s", category, type(exc).__name__)
        return False, "email_provider_error"


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
    verify_url=_site_url().rstrip("/")+"/verify-email/"+token
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
        "افهم أعراضك. اعرف خطوتك التالية." if ar else
        "Understand your symptoms. Know your next step.",
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
        except Exception: pass
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
        "account_not_found": "لا يوجد حساب بهذا البريد. أنشئ حسابًا أولًا." if ar else "No account found. Please create an account first.",
        "incorrect_credentials": "البريد الإلكتروني أو كلمة المرور غير صحيحة." if ar else "Incorrect email or password.",
        "account_unavailable": "يتعذر تسجيل الدخول إلى هذا الحساب حاليًا." if ar else "This account is currently unavailable.",
        "verification_required": "يجب التحقق من البريد الإلكتروني قبل تسجيل الدخول." if ar else "Please verify your email before signing in.",
    }
    return messages.get(code, "تعذر تسجيل الدخول. حاول مرة أخرى." if ar else "Unable to sign in. Please try again.")


@app.route("/login", methods=["GET", "POST"])
def login():
    db.init_db(); platform_v2.init_schema()
    lang=_lang(); t=L["en" if lang=="en" else "ar"]
    error=None; error_code=None
    next_param=_safe_next_url("/profile")
    if next_param.startswith("/family"):
        reason="سجّلي الدخول لحفظ ملفات العائلة ومتابعتها بأمان من أي جهاز." if lang=="ar" else "Sign in to securely save and access family profiles on any device."
    elif next_param.startswith("/meds"):
        reason="سجّلي الدخول لحفظ تذكيرات الأدوية وربطها بحسابك." if lang=="ar" else "Sign in to save medication reminders to your account."
    else:
        reason="بعد تسجيل الدخول يمكنك الوصول إلى ملفك ونتائجك المحفوظة." if lang=="ar" else "After signing in, you can access your profile and saved results."
    if request.method=="POST" and not _auth_csrf_valid():
        error=_auth_form_expired_message(lang); error_code="csrf_failed"
    elif request.method=="POST":
        email=(request.form.get("email") or "").strip().lower(); password=request.form.get("password") or ""
        network_origin=request.remote_addr or "unknown"
        rate_blocked=not platform_v2.login_attempt_allowed(email,network_origin)
        result=({"ok":False,"error":"rate_limited"} if rate_blocked
                else db.authenticate_ss_user_status(email,password))
        user_id=result.get("user_id") if result.get("ok") else None
        if result.get("error")=="verification_required" and result.get("user_id"):
            session.clear(); session["pending_verification_user_id"]=int(result["user_id"]); session.permanent=True
            sent, send_error = _issue_verification_email(int(result["user_id"]), lang)
            session["verification_send_state"]="sent" if sent else (send_error or "verification_required")
            return redirect(url_for("verify_email_pending"))
        if user_id:
            db.promote_existing_owner_admin(user_id)
        login_user=db.get_ss_user(user_id) if user_id else None
        if not rate_blocked:
            platform_v2.record_login_attempt(email,network_origin,bool(user_id))
        platform_v2.log_login(email,user_id,bool(user_id),bool(login_user and login_user.get("role")=="admin"),request.headers.get("User-Agent",""))
        if user_id:
            session.clear(); session["ss_user_id"]=int(user_id); session.permanent=True
            is_admin=bool(login_user and login_user.get("role")=="admin")
            session["login_toast"]="admin" if is_admin else "user"
            if is_admin:
                session["admin_last_seen"]=int(datetime.now(timezone.utc).timestamp())
                try: platform_v2.audit(int(user_id),"login","admin_session","self",None,{"status":"success"})
                except Exception: pass
            redirect_target="/admin" if is_admin else next_param
            _admin_auth_debug("login_success",login_user,granted=is_admin,redirect_target=redirect_target)
            return redirect(redirect_target)
        error_code=result.get("error") or "incorrect_credentials"
        _admin_auth_debug("login_failed",None,granted=False,redirect_target=None)
        if db.is_owner_admin_email(email):
            try: platform_v2.audit(None,"login_failed","admin_session","owner",None,{"status":"failed"})
            except Exception: pass
        error=(("محاولات تسجيل دخول كثيرة. انتظر 15 دقيقة ثم حاول مرة أخرى."
                if lang=="ar" else "Too many sign-in attempts. Wait 15 minutes and try again.")
               if error_code=="rate_limited" else _auth_login_error(lang,error_code))
    create_action=('<div style="margin-top:12px"><a class="auth-btn" style="display:inline-flex;text-decoration:none;justify-content:center;background:#fff!important;color:#287FC1!important;border:1px solid #BFD9EC" href="/register?next=__NEXT__">__CREATE__</a></div>') if error_code=="account_not_found" else ""
    body="""
    <div class="auth-wrap"><div class="auth-card">
      <div class="auth-icon">🩺</div><div style="font-weight:900;color:#163B5C;font-size:20px;direction:ltr;margin-bottom:5px">SymptoSense 🩺</div>
      <h1>__H__</h1><p class="auth-sub">__SUB__</p><div class="auth-reason">🔐 __REASON__</div>
      <div class="auth-error __ERR_CLASS__">__ERR__</div>__CREATE_ACTION__
      <form method="POST" action="/login?next=__NEXT__">
        <input type="hidden" name="csrf_token" value="__CSRF__">
        <div class="auth-field"><label>__EMAIL__</label><input type="email" name="email" required placeholder="name@example.com" autocomplete="email"></div>
        <div class="auth-field"><label>__PASS__</label><input type="password" name="password" required placeholder="••••••••" autocomplete="current-password"></div>
        <button type="submit" class="auth-btn">__BTN__</button>
      </form>
      <p class="auth-link" style="margin-top:12px"><a href="/forgot-password">__FORGOT__</a></p>
      <p class="auth-link">__NOACCT__ <a href="/register?next=__NEXT__">__REG__</a></p>
      <div style="display:flex;align-items:center;gap:10px;margin:16px 0;color:#94A3B8"><span style="height:1px;background:#DCE8F0;flex:1"></span><span>__OR__</span><span style="height:1px;background:#DCE8F0;flex:1"></span></div>
      <a class="btn ghost" style="width:100%;justify-content:center" href="/home">__GUEST__</a>
    </div></div>
    """
    from html import escape
    vals={"__H__":"مرحبًا بعودتك" if lang=="ar" else "Welcome back","__SUB__":"سجّل الدخول للوصول إلى معلوماتك ونتائجك المحفوظة." if lang=="ar" else "Sign in to access your saved information and results.","__REASON__":reason,"__EMAIL__":t["login_email"],"__PASS__":t["login_pass"],"__BTN__":t["login_btn"],"__FORGOT__":"نسيت كلمة المرور؟" if lang=="ar" else "Forgot password?","__NOACCT__":t["login_noaccount"],"__REG__":t["login_register"],"__OR__":"أو" if lang=="ar" else "or","__GUEST__":"المتابعة كزائر" if lang=="ar" else "Continue as guest","__NEXT__":escape(next_param),"__CSRF__":_auth_csrf_token(),"__ERR_CLASS__":"show" if error else "","__ERR__":error or "","__CREATE__":"إنشاء حساب" if lang=="ar" else "Create Account"}
    create_action=create_action.replace("__NEXT__",escape(next_param)).replace("__CREATE__",vals["__CREATE__"])
    vals["__CREATE_ACTION__"]=create_action
    for k,v in vals.items(): body=body.replace(k,v)
    return _page(t["title_login"],body)


@app.route("/register", methods=["GET", "POST"])
def register():
    db.init_db(); platform_v2.init_schema()
    lang=_lang(); t=L["en" if lang=="en" else "ar"]; error=None
    next_param=_safe_next_url("/profile")
    if request.method=="POST" and not _auth_csrf_valid():
        error=_auth_form_expired_message(lang)
    elif request.method=="POST":
        name=(request.form.get("name") or "").strip(); email=(request.form.get("email") or "").strip().lower()
        password=request.form.get("password") or ""; confirm=request.form.get("confirm") or ""; accepted=request.form.get("accept_terms")=="on"
        if not accepted: error="يجب الموافقة على سياسة الخصوصية وشروط الاستخدام." if lang=="ar" else "You must accept the privacy policy and terms of use."
        elif password!=confirm: error=t["register_pass_mismatch"]
        elif len(password)<8: error="استخدم 8 أحرف على الأقل لكلمة المرور." if lang=="ar" else "Use at least 8 characters for your password."
        else:
            user_id,err=db.create_ss_user(email,name,password)
            if user_id:
                session.clear(); session["pending_verification_user_id"]=int(user_id); session["post_verify_next"]=next_param; session.permanent=True
                sent,send_error=_issue_verification_email(int(user_id),lang)
                try: platform_v2.record_usage("new_account","/register",lang,request.headers.get("User-Agent",""),201,None)
                except Exception: pass
                session["verification_send_state"]="sent" if sent else (send_error or "failed")
                return redirect(url_for("verify_email_pending"))
            mapping={"email_exists":"يوجد حساب بهذا البريد بالفعل. سجّل الدخول بدلًا من إنشاء حساب جديد." if lang=="ar" else "An account with this email already exists. Please sign in instead.","owner_account_must_exist":"حساب مالك المشروع يجب أن يكون موجودًا مسبقًا ولا يمكن إنشاؤه من صفحة التسجيل." if lang=="ar" else "The project owner account must already exist and cannot be created from this page.","password_too_short":"استخدم 8 أحرف على الأقل لكلمة المرور." if lang=="ar" else "Use at least 8 characters for your password.","invalid_email":"أدخل بريدًا إلكترونيًا صالحًا." if lang=="ar" else "Enter a valid email address.","invalid_name":"أدخل اسمًا صالحًا." if lang=="ar" else "Enter a valid name."}
            error=mapping.get(err,t["register_error"])
    body="""
    <div class="auth-wrap"><div class="auth-card"><div class="auth-icon">🩺</div><div style="font-weight:900;color:#163B5C;font-size:20px;direction:ltr;margin-bottom:5px">SymptoSense 🩺</div>
      <h1>__H__</h1><p class="auth-sub">__SUB__</p><div class="auth-error __ERR_CLASS__">__ERR__</div>
      <form method="POST" action="/register?next=__NEXT__">
        <input type="hidden" name="csrf_token" value="__CSRF__">
        <div class="auth-field"><label>__NAME__</label><input type="text" name="name" required autocomplete="name"></div>
        <div class="auth-field"><label>__EMAIL__</label><input type="email" name="email" required placeholder="name@example.com" autocomplete="email"></div>
        <div class="auth-field"><label>__PASS__</label><input type="password" name="password" required minlength="8" autocomplete="new-password"></div>
        <div class="auth-field"><label>__CONFIRM__</label><input type="password" name="confirm" required minlength="8" autocomplete="new-password"></div>
        <label style="display:flex;align-items:flex-start;gap:9px;text-align:start;font-size:13px;line-height:1.7;margin:12px 0;color:#40566F"><input type="checkbox" name="accept_terms" required style="width:18px;height:18px;margin-top:3px"><span>__ACCEPT__</span></label>
        <button type="submit" class="auth-btn">__BTN__</button>
      </form><p class="auth-link">__HASACCT__ <a href="/login?next=__NEXT__">__LOGIN__</a></p>
    </div></div>
    """
    from html import escape
    accept=('أوافق على <a href="/privacy" target="_blank">سياسة الخصوصية</a> و<a href="/terms" target="_blank">شروط الاستخدام</a>.' if lang=="ar" else 'I agree to the <a href="/privacy" target="_blank">Privacy Policy</a> and <a href="/terms" target="_blank">Terms of Use</a>.')
    vals={"__H__":t["register_h"],"__SUB__":"أنشئ حسابك، ثم تحقّق من بريدك الإلكتروني قبل تسجيل الدخول." if lang=="ar" else "Create your account, then verify your email before signing in.","__NAME__":t["register_name"],"__EMAIL__":t["register_email"],"__PASS__":t["register_pass"],"__CONFIRM__":t["register_confirm"],"__BTN__":t["register_btn"],"__HASACCT__":t["register_hasaccount"],"__LOGIN__":t["register_login"],"__ACCEPT__":accept,"__NEXT__":escape(next_param),"__CSRF__":_auth_csrf_token(),"__ERR_CLASS__":"show" if error else "","__ERR__":error or ""}
    for k,v in vals.items(): body=body.replace(k,v)
    return _page(t["title_register"],body)


@app.route("/verify-email", methods=["GET", "POST"])
def verify_email_pending():
    db.init_db(); platform_v2.init_schema(); ar=_lang()=="ar"
    uid=session.get("pending_verification_user_id"); notice=""; error=""
    user=db.get_ss_user(uid) if uid else None
    if user and user.get("email_verified"):
        session.pop("pending_verification_user_id",None)
        return redirect("/login")
    if request.method=="POST" and not _auth_csrf_valid():
        error=_auth_form_expired_message(_lang())
    elif request.method=="POST":
        action=request.form.get("action") or "resend"
        if not user:
            error="ابدأ من تسجيل الدخول أو إنشاء حساب." if ar else "Start from sign in or create an account."
        elif action=="verify_code":
            verified_uid, code_status = platform_v2.consume_email_verification_code(int(uid), request.form.get("verification_code") or "")
            if verified_uid:
                pending_next=session.pop("post_verify_next",None) or "/profile"
                session.pop("pending_verification_user_id",None)
                session["ss_user_id"]=int(verified_uid); session.permanent=True
                verified_user=db.get_ss_user(int(verified_uid))
                is_admin=bool(verified_user and verified_user.get("role")=="admin")
                session["login_toast"]="admin" if is_admin else "user"
                return redirect("/admin" if is_admin else (pending_next if isinstance(pending_next,str) and pending_next.startswith("/") and not pending_next.startswith("//") and not pending_next.startswith("/admin") else "/profile"))
            messages={
                "expired": "انتهت صلاحية الرمز. اطلب رمزًا جديدًا." if ar else "The code expired. Request a new code.",
                "used": "تم استخدام هذا الرمز. اطلب رمزًا جديدًا." if ar else "This code was already used. Request a new code.",
                "too_many_attempts": "محاولات كثيرة. اطلب رمزًا جديدًا." if ar else "Too many attempts. Request a new code.",
            }
            error=messages.get(code_status,"رمز التحقق غير صحيح." if ar else "The verification code is incorrect.")
        elif action=="change_email":
            new_email=(request.form.get("new_email") or "").strip().lower()
            current_password=request.form.get("current_password") or ""
            ok,err=db.update_unverified_email(int(uid),new_email,current_password)
            if ok:
                try: platform_v2.invalidate_email_verifications(int(uid))
                except Exception: pass
                user=db.get_ss_user(uid)
                sent,reason=_issue_verification_email(int(uid),_lang())
                notice=("تم تحديث البريد وإرسال رابط تحقق جديد." if ar else "Email updated and a new verification link was sent.") if sent else ("تم تحديث البريد، لكن تعذر إرسال الرسالة. تحقق من إعداد مزود البريد." if ar else "Email updated, but the message could not be sent. Check the email provider configuration.")
            else:
                if err in {"invalid_email","email_exists"}:
                    error="البريد غير صالح أو مستخدم بالفعل." if ar else "The email is invalid or already in use."
                elif err=="incorrect_password":
                    error="كلمة المرور الحالية غير صحيحة." if ar else "The current password is incorrect."
                else:
                    error="تعذر تغيير البريد." if ar else "Unable to change the email."
        else:
            sent,reason=_issue_verification_email(int(uid),_lang())
            if sent: notice="أرسلنا رمز تحقق جديدًا إلى بريدك الإلكتروني." if ar else "We sent a new verification code to your email."
            elif reason in {"cooldown","rate_limited"}: error="يرجى الانتظار قبل طلب رسالة تحقق أخرى." if ar else "Please wait before requesting another verification email."
            elif reason=="email_not_configured": error="خدمة البريد غير مضبوطة بعد. أضف إعدادات SMTP أو Resend في Railway." if ar else "Email delivery is not configured. Add SMTP or Resend settings in Railway."
            elif reason=="email_invalid_api_key": error="مفتاح Resend غير صالح. حدّث RESEND_API_KEY في Railway." if ar else "The Resend API key is invalid. Update RESEND_API_KEY in Railway."
            elif reason=="email_test_domain_restricted": error="إعداد Resend الحالي مخصص للاختبار فقط. لإرسال الرسائل لكل المستخدمين يجب توثيق Domain في Resend واستخدامه في RESEND_FROM." if ar else "The current Resend sender is test-only. Verify a domain in Resend and use it in RESEND_FROM to email all users."
            elif reason=="email_sender_domain_unverified": error="الدومين المستخدم في RESEND_FROM غير موثق في Resend." if ar else "The domain used by RESEND_FROM is not verified in Resend."
            elif reason=="email_sender_placeholder": error="قيمة RESEND_FROM ما زالت مثالًا تجريبيًا. استبدلها بعنوان من دومين موثق في Resend." if ar else "RESEND_FROM is still a placeholder. Replace it with an address on a verified Resend domain."
            elif reason=="email_api_key_placeholder": error="قيمة RESEND_API_KEY ما زالت مثالًا وليست مفتاح Resend فعليًا." if ar else "RESEND_API_KEY is still a placeholder, not a real Resend API key."
            elif reason=="email_sender_invalid": error="صيغة RESEND_FROM غير صحيحة. استخدم: SymptoSense <noreply@your-domain.com>." if ar else "RESEND_FROM is invalid. Use: SymptoSense <noreply@your-domain.com>."
            elif reason=="email_smtp_not_configured": error="إعداد Gmail غير مكتمل. تأكد من إضافة جميع متغيرات SMTP في Railway." if ar else "Gmail configuration is incomplete. Add all SMTP variables in Railway."
            elif reason=="email_smtp_auth_failed": error="رفض Gmail تسجيل الدخول. تأكد من البريد وكلمة مرور التطبيق App Password، وليس كلمة مرور Gmail العادية." if ar else "Gmail rejected the sign-in. Check the email and App Password; do not use the normal Gmail password."
            elif reason=="email_smtp_connection_failed": error="تعذر الاتصال بخادم Gmail. تحقق من إعدادات SMTP ثم حاول مجددًا." if ar else "Could not connect to Gmail. Check the SMTP settings and try again."
            elif reason=="email_smtp_sender_invalid": error="صيغة SMTP_FROM غير صحيحة. استخدم: SymptoSense <your-email@gmail.com>." if ar else "SMTP_FROM is invalid. Use: SymptoSense <your-email@gmail.com>."
            elif reason=="email_smtp_port_invalid": error="قيمة SMTP_PORT غير صحيحة. استخدم 587 مع TLS." if ar else "SMTP_PORT is invalid. Use 587 with TLS."
            elif reason=="email_brevo_not_configured": error="إعداد Brevo غير مكتمل. أضف متغيرات BREVO الثلاثة في Railway." if ar else "Brevo is incomplete. Add all three BREVO variables in Railway."
            elif reason in {"email_brevo_auth_failed","email_brevo_key_placeholder"}: error="مفتاح Brevo غير صالح. أنشئ API Key جديدًا وحدّث BREVO_API_KEY في Railway." if ar else "The Brevo API key is invalid. Create a new key and update BREVO_API_KEY in Railway."
            elif reason=="email_brevo_sender_invalid": error="بريد المرسل في Brevo غير صالح أو غير موثق. تحقق من BREVO_FROM_EMAIL وحالة Verified." if ar else "The Brevo sender is invalid or unverified. Check BREVO_FROM_EMAIL and its Verified status."
            elif reason=="email_brevo_rate_limited": error="تم بلوغ حد الإرسال في Brevo. انتظر تجدد الحد اليومي ثم حاول مجددًا." if ar else "The Brevo sending limit was reached. Wait for the daily allowance to reset."
            elif reason in {"email_brevo_connection_failed","email_brevo_delivery_failed"}: error="تعذر إرسال الرسالة عبر Brevo الآن. تحقق من الإعدادات ثم حاول مجددًا." if ar else "Brevo could not send the email. Check the configuration and try again."
            else: error="تعذر إرسال رسالة التحقق الآن. تحقق من إعدادات البريد في Railway ثم حاول مرة أخرى." if ar else "Unable to send the verification email. Check the email configuration in Railway and try again."
    state=session.pop("verification_send_state",None)
    if state and not notice and not error:
        if state=="sent":
            notice="أرسلنا رمز التحقق إلى بريدك الإلكتروني." if ar else "We sent the verification code to your email."
        elif state in {"cooldown","rate_limited"}:
            notice="يرجى التحقق من بريدك أولًا. أُرسل رمز مؤخرًا؛ استخدمه أو انتظر قليلًا قبل طلب رمز جديد." if ar else "Please verify your email first. A code was sent recently; use it or wait before requesting a new one."
        elif state=="email_not_configured":
            error="خدمة البريد غير مضبوطة. أضف إعدادات SMTP أو Resend في Railway قبل محاولة الإرسال." if ar else "Email delivery is not configured. Add SMTP or Resend settings in Railway before resending."
        elif state=="email_invalid_api_key":
            error="مفتاح Resend غير صالح. حدّث RESEND_API_KEY في Railway." if ar else "The Resend API key is invalid. Update RESEND_API_KEY in Railway."
        elif state=="email_test_domain_restricted":
            error="مرسل Resend الحالي للاختبار فقط. وثّق Domain في Resend ثم حدّث RESEND_FROM." if ar else "The current Resend sender is test-only. Verify a domain in Resend and update RESEND_FROM."
        elif state=="email_sender_domain_unverified":
            error="الدومين الموجود في RESEND_FROM غير موثق في Resend." if ar else "The domain in RESEND_FROM is not verified in Resend."
        elif state=="email_sender_placeholder":
            error="قيمة RESEND_FROM ما زالت مثالًا تجريبيًا. استبدلها بعنوان من دومين موثق في Resend." if ar else "RESEND_FROM is still a placeholder. Replace it with an address on a verified Resend domain."
        elif state=="email_api_key_placeholder":
            error="قيمة RESEND_API_KEY ما زالت مثالًا وليست مفتاح Resend فعليًا." if ar else "RESEND_API_KEY is still a placeholder, not a real Resend API key."
        elif state=="email_sender_invalid":
            error="صيغة RESEND_FROM غير صحيحة." if ar else "RESEND_FROM is invalid."
        elif state=="email_smtp_not_configured":
            error="إعداد Gmail غير مكتمل. أضف جميع متغيرات SMTP في Railway." if ar else "Gmail configuration is incomplete. Add all SMTP variables in Railway."
        elif state=="email_smtp_auth_failed":
            error="رفض Gmail تسجيل الدخول. تحقّق من App Password والبريد المرسل." if ar else "Gmail rejected the sign-in. Check the App Password and sender email."
        elif state=="email_smtp_connection_failed":
            error="تعذر الاتصال بخادم Gmail. تحقق من إعدادات SMTP وحاول مجددًا." if ar else "Could not connect to Gmail. Check the SMTP settings and try again."
        elif state=="email_smtp_sender_invalid":
            error="صيغة SMTP_FROM غير صحيحة." if ar else "SMTP_FROM is invalid."
        elif state=="email_smtp_port_invalid":
            error="قيمة SMTP_PORT غير صحيحة؛ استخدم 587." if ar else "SMTP_PORT is invalid; use 587."
        elif state=="email_brevo_not_configured":
            error="إعداد Brevo غير مكتمل. أضف متغيرات BREVO الثلاثة في Railway." if ar else "Brevo is incomplete. Add all three BREVO variables in Railway."
        elif state in {"email_brevo_auth_failed","email_brevo_key_placeholder"}:
            error="مفتاح Brevo غير صالح. حدّث BREVO_API_KEY في Railway." if ar else "The Brevo API key is invalid. Update BREVO_API_KEY in Railway."
        elif state=="email_brevo_sender_invalid":
            error="بريد Brevo المرسل غير صالح أو غير موثق." if ar else "The Brevo sender is invalid or unverified."
        elif state=="email_brevo_rate_limited":
            error="تم بلوغ حد Brevo اليومي. حاول بعد تجدد الحد." if ar else "The Brevo daily sending limit was reached. Try again after it resets."
        elif state in {"email_brevo_connection_failed","email_brevo_delivery_failed"}:
            error="تعذر إرسال الرسالة عبر Brevo الآن. حاول مجددًا." if ar else "Brevo could not send the email. Try again."
        elif state=="verification_required":
            notice="يرجى التحقق من بريدك الإلكتروني أولًا. إذا لم تصل الرسالة، استخدم إعادة الإرسال." if ar else "Please verify your email first. If the message did not arrive, use resend."
        else:
            error="تعذر إرسال رسالة التحقق حاليًا. تحقق من إعدادات البريد في Railway ثم حاول مرة أخرى." if ar else "The verification email could not be sent. Check the email configuration in Railway and try again."
    masked=""
    if user and user.get("email"):
        e=str(user["email"]); parts=e.split("@",1); masked=(parts[0][:2]+"***@"+parts[1]) if len(parts)==2 else "***"
    body="""
    <div class="auth-wrap"><div class="auth-card"><div class="auth-icon">📧</div><h1>__TITLE__</h1><p class="auth-sub">__SUB__</p><p class="muted" style="direction:ltr">__MASKED__</p>
      __NOTICE____ERROR__
      <form method="post" style="margin-bottom:12px"><input type="hidden" name="csrf_token" value="__CSRF__"><input type="hidden" name="action" value="verify_code"><div class="auth-field"><label>__CODELABEL__</label><input type="text" name="verification_code" required inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{6}" maxlength="6" style="direction:ltr;text-align:center;font-size:25px;letter-spacing:7px" placeholder="000000"></div><button class="auth-btn" type="submit">__VERIFYBTN__</button></form>
      <form method="post"><input type="hidden" name="csrf_token" value="__CSRF__"><input type="hidden" name="action" value="resend"><button class="auth-btn" type="submit">__RESEND__</button></form>
      <details style="margin-top:14px;text-align:start"><summary style="cursor:pointer;font-weight:700">__CHANGE__</summary><form method="post" style="margin-top:10px"><input type="hidden" name="csrf_token" value="__CSRF__"><input type="hidden" name="action" value="change_email"><div class="auth-field"><label>__NEWEMAIL__</label><input type="email" name="new_email" required autocomplete="email"></div><div class="auth-field"><label>__PASSWORD__</label><input type="password" name="current_password" required autocomplete="current-password"></div><button class="btn ghost" type="submit">__SAVEEMAIL__</button></form></details>
      <p class="auth-link"><a href="/login">__BACK__</a></p>
    </div></div>
    """
    notice_html='<div class="ss-msg success" style="display:block">'+notice+'</div>' if notice else ""
    error_html='<div class="auth-error show">'+error+'</div>' if error else ""
    vals={"__TITLE__":"📧 تحقق من بريدك الإلكتروني" if ar else "📧 Verify Your Email","__SUB__":"أدخل رمز التحقق المكوّن من 6 أرقام الذي أرسلناه إلى بريدك." if ar else "Enter the six-digit verification code sent to your email.","__MASKED__":masked,"__NOTICE__":notice_html,"__ERROR__":error_html,"__CODELABEL__":"رمز التحقق" if ar else "Verification code","__VERIFYBTN__":"تأكيد الرمز" if ar else "Verify Code","__RESEND__":"إرسال رمز جديد" if ar else "Send New Code","__CHANGE__":"تغيير البريد الإلكتروني" if ar else "Change Email","__NEWEMAIL__":"البريد الإلكتروني الجديد" if ar else "New email","__PASSWORD__":"كلمة المرور الحالية" if ar else "Current password","__SAVEEMAIL__":"حفظ وإرسال رمز جديد" if ar else "Save & send new code","__BACK__":"العودة إلى تسجيل الدخول" if ar else "Back to Login","__CSRF__":_auth_csrf_token()}
    for k,v in vals.items(): body=body.replace(k,v)
    return _page("تحقق من البريد" if ar else "Verify Email",body)


@app.route("/verify-email/<token>")
def verify_email_token(token):
    ar=_lang()=="ar"; status=platform_v2.email_verification_status(token)
    # Auto-login is allowed only when the verification link is opened in the
    # same browser session that created the account. Possession of a valid
    # email token alone never creates a session on another browser/device.
    pending_uid=session.get("pending_verification_user_id")
    pending_next=session.get("post_verify_next") or "/profile"
    if status=="valid":
        uid,result=platform_v2.consume_email_verification(token)
        if uid:
            same_registration_session=bool(pending_uid and int(pending_uid)==int(uid))
            session.pop("pending_verification_user_id",None); session.pop("post_verify_next",None)
            if same_registration_session:
                session["ss_user_id"]=int(uid); session["login_toast"]="user"; session.permanent=True
                target=pending_next if isinstance(pending_next,str) and pending_next.startswith("/") and not pending_next.startswith("//") else "/profile"
                if target.startswith("/admin"):
                    target="/profile"
                return redirect(target)
            body='<div class="auth-wrap"><div class="auth-card"><div class="auth-icon">✅</div><h1>%s</h1><p class="auth-sub">%s</p><a class="auth-btn" href="/login">%s</a></div></div>' % (("تم التحقق من البريد الإلكتروني" if ar else "Email verified"),("يمكنك تسجيل الدخول الآن." if ar else "You can sign in now."),("تسجيل الدخول" if ar else "Back to Login"))
            return _page("تم التحقق" if ar else "Email Verified",body)
        status=result
    msg={"expired":"انتهت صلاحية رابط التحقق." if ar else "This verification link has expired.","used":"تم استخدام رابط التحقق بالفعل." if ar else "This verification link has already been used.","invalid":"رابط التحقق غير صالح." if ar else "This verification link is invalid."}.get(status,"تعذر التحقق من الرابط." if ar else "Unable to verify this link.")
    body='<div class="auth-wrap"><div class="auth-card"><div class="auth-icon">⚠️</div><h1>%s</h1><p class="auth-sub">%s</p><a class="auth-btn" href="/login">%s</a></div></div>' % (("تعذر التحقق" if ar else "Verification unavailable"),msg,("العودة إلى تسجيل الدخول" if ar else "Back to Login"))
    return _page("تحقق من البريد" if ar else "Verify Email",body),400


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    db.init_db(); platform_v2.init_schema(); ar=_lang()=="ar"; sent=False; form_error=""
    if request.method=="POST" and not _auth_csrf_valid():
        form_error=_auth_form_expired_message(_lang())
    elif request.method=="POST":
        email=(request.form.get("email") or "").strip().lower()
        provider_state=_auth_email_provider_state()
        provider_error=not provider_state.get("configured")
        if platform_v2.email_is_valid(email) and not provider_error:
            token,user_id,reason=platform_v2.create_password_reset(email)
            if token and user_id:
                reset_url=_site_url().rstrip("/")+"/reset-password/"+token
                ok,send_error=_send_password_reset_email(email,reset_url,_lang())
                if not ok:
                    try: platform_v2.discard_password_reset_token(token)
                    except Exception: pass
                    provider_error=True
        sent=True
    generic="إذا كان الحساب موجودًا لهذا البريد، فقد تم إرسال رابط إعادة تعيين كلمة المرور." if ar else "If an account exists for this email, a password reset link has been sent."
    # Keep the public response identical whether the account exists, the
    # request was throttled, or the provider had a transient failure. Details
    # remain in server logs/configuration diagnostics only.
    body="""<div class="auth-wrap"><div class="auth-card"><div class="auth-icon">🔑</div><h1>__TITLE__</h1><p class="auth-sub">__SUB__</p>__NOTICE____ERROR__<form method="post"><input type="hidden" name="csrf_token" value="__CSRF__"><div class="auth-field"><label>__EMAIL__</label><input type="email" name="email" required autocomplete="email" placeholder="name@example.com"></div><button class="auth-btn" type="submit">__BTN__</button></form><p class="auth-link"><a href="/login">__BACK__</a></p></div></div>"""
    notice=('<div class="ss-msg success" style="display:block">%s</div>' % generic) if sent else ""
    error_html=('<div class="auth-error show">%s</div>' % form_error) if form_error else ""
    vals={"__TITLE__":"نسيت كلمة المرور؟" if ar else "Forgot Password?","__SUB__":"أدخل بريدك لإرسال رابط إعادة تعيين مؤقت." if ar else "Enter your email to receive a temporary reset link.","__EMAIL__":"البريد الإلكتروني" if ar else "Email","__BTN__":"إرسال رابط الاستعادة" if ar else "Send Reset Link","__BACK__":"العودة إلى تسجيل الدخول" if ar else "Back to Login","__NOTICE__":notice,"__ERROR__":error_html,"__CSRF__":_auth_csrf_token()}
    for k,v in vals.items(): body=body.replace(k,v)
    return _page(vals["__TITLE__"],body)


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    ar=_lang()=="ar"; status=platform_v2.password_reset_status(token); error=""; success=False
    if status!="valid":
        msg={"expired":"انتهت صلاحية رابط إعادة التعيين." if ar else "This password reset link has expired.","used":"تم استخدام رابط إعادة التعيين بالفعل." if ar else "This password reset link has already been used.","invalid":"رابط إعادة التعيين غير صالح." if ar else "This password reset link is invalid."}.get(status,"الرابط غير متاح." if ar else "This link is unavailable.")
        body='<div class="auth-wrap"><div class="auth-card"><div class="auth-icon">⚠️</div><h1>%s</h1><p class="auth-sub">%s</p><a class="auth-btn" href="/forgot-password">%s</a></div></div>' % (("تعذر إعادة التعيين" if ar else "Reset unavailable"),msg,("طلب رابط جديد" if ar else "Request a new link"))
        return _page("استعادة كلمة المرور" if ar else "Reset Password",body),400
    if request.method=="POST" and not _auth_csrf_valid():
        error=_auth_form_expired_message(_lang())
    elif request.method=="POST":
        password=request.form.get("password") or ""; confirm=request.form.get("confirm") or ""
        if password!=confirm: error="كلمتا المرور غير متطابقتين." if ar else "Passwords do not match."
        else:
            try:
                success=platform_v2.consume_password_reset(token,password)
                if not success: error="الرابط غير صالح أو انتهت صلاحيته." if ar else "This link is invalid or has expired."
            except ValueError: error="استخدم 8 أحرف على الأقل." if ar else "Use at least 8 characters."
    if success:
        # Password-reset completion revokes the current browser session. The
        # user must authenticate again with the new password.
        session.clear()
        body='<div class="auth-wrap"><div class="auth-card"><div class="auth-icon">✅</div><h1>%s</h1><p class="auth-sub">%s</p><a class="auth-btn" href="/login">%s</a></div></div>' % (("تمت إعادة تعيين كلمة المرور بنجاح" if ar else "Password reset successfully"),("يمكنك تسجيل الدخول بكلمة المرور الجديدة." if ar else "You can now sign in with your new password."),("العودة إلى تسجيل الدخول" if ar else "Back to Login"))
    else:
        body="""<div class="auth-wrap"><div class="auth-card"><div class="auth-icon">🔐</div><h1>__TITLE__</h1><div class="auth-error __ERR_CLASS__">__ERROR__</div><form method="post"><input type="hidden" name="csrf_token" value="__CSRF__"><div class="auth-field"><label>__PASS__</label><input type="password" name="password" required minlength="8" autocomplete="new-password"></div><div class="auth-field"><label>__CONFIRM__</label><input type="password" name="confirm" required minlength="8" autocomplete="new-password"></div><button class="auth-btn" type="submit">__BTN__</button></form></div></div>"""
        vals={"__TITLE__":"إعادة تعيين كلمة المرور" if ar else "Reset Password","__PASS__":"كلمة المرور الجديدة" if ar else "New Password","__CONFIRM__":"تأكيد كلمة المرور الجديدة" if ar else "Confirm New Password","__BTN__":"إعادة تعيين كلمة المرور" if ar else "Reset Password","__CSRF__":_auth_csrf_token(),"__ERR_CLASS__":"show" if error else "","__ERROR__":error}
        for k,v in vals.items(): body=body.replace(k,v)
    return _page("استعادة كلمة المرور" if ar else "Reset Password",body)


@app.route("/logout")
def logout():
    try:
        u=_ss_user()
        if u and u.get("role")=="admin": platform_v2.audit(int(u.get("id")),"logout","admin_session","self",None,{"status":"success"})
    except Exception: pass
    session.clear(); return redirect("/home")


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    db.init_db()
    lang = _lang()
    t = L["en" if lang == "en" else "ar"]
    msg = None
    if request.method == "POST":
        data = {
            "use_in_assistant": request.form.get("use_in_assistant") == "on",
            "use_in_analysis": request.form.get("use_in_analysis") == "on",
            "use_in_calculators": request.form.get("use_in_calculators") == "on",
            "save_chat_history": request.form.get("save_chat_history") == "on",
        }
        db.save_privacy_settings(_ss_user_id(), data)
        advanced_features.save_preferences(int(_ss_user_id()), request.form.get("accessibility_mode") == "on")
        msg = t["settings_saved"]
    privacy = db.load_privacy_settings(_ss_user_id())
    prefs = advanced_features.get_preferences(int(_ss_user_id()))
    def chk(v):
        return 'checked' if v else ''
    body = """
    <div class="card" style="max-width:560px;margin:0 auto;">
      <h2>__H__</h2>
      <p class="muted">__SUB__</p>
      <form method="POST" style="margin-top:16px;">
        <div class="ss-toggle-row">
          <span class="ss-t-label">__T1__</span>
          <label class="ss-toggle"><input type="checkbox" name="use_in_assistant" __CHK1__><span class="ss-slider"></span></label>
        </div>
        <div class="ss-toggle-row">
          <span class="ss-t-label">__T2__</span>
          <label class="ss-toggle"><input type="checkbox" name="use_in_analysis" __CHK2__><span class="ss-slider"></span></label>
        </div>
        <div class="ss-toggle-row">
          <span class="ss-t-label">__T3__</span>
          <label class="ss-toggle"><input type="checkbox" name="use_in_calculators" __CHK3__><span class="ss-slider"></span></label>
        </div>
        <div class="ss-toggle-row">
          <span class="ss-t-label">__T4__</span>
          <label class="ss-toggle"><input type="checkbox" name="save_chat_history" __CHK4__><span class="ss-slider"></span></label>
        </div>
        <div class="ss-toggle-row">
          <span class="ss-t-label">__ACCESS__<small style="display:block;color:#64748b;font-weight:500;margin-top:3px">__ACCESS_SUB__</small></span>
          <label class="ss-toggle"><input type="checkbox" name="accessibility_mode" __CHK_ACCESS__><span class="ss-slider"></span></label>
        </div>
        <div class="ss-btn-row">
          <button type="submit" class="ss-btn-primary">__SAVE__</button>
        </div>
      </form>
      <div class="ss-msg __MSG_CLASS__">__MSG__</div>
    </div>
    """
    body = body.replace("__H__", t["settings_h"]).replace("__SUB__", t["settings_sub"])
    body = body.replace("__T1__", t["settings_assistant"]).replace("__T2__", t["settings_analysis"])
    body = body.replace("__T3__", t["settings_calc"]).replace("__T4__", t["settings_chat"])
    body = body.replace("__CHK1__", chk(privacy.get("use_in_assistant", True)))
    body = body.replace("__CHK2__", chk(privacy.get("use_in_analysis", True)))
    body = body.replace("__CHK3__", chk(privacy.get("use_in_calculators", True)))
    body = body.replace("__CHK4__", chk(privacy.get("save_chat_history", True)))
    body = body.replace("__CHK_ACCESS__", chk(prefs.get("accessibility_mode", False)))
    body = body.replace("__ACCESS__", "♿ وضع سهولة الوصول" if lang == "ar" else "♿ Accessibility Mode")
    body = body.replace("__ACCESS_SUB__", "خط أكبر، أزرار ومسافات أوضح، حركة أقل، وتركيز لوحة مفاتيح أفضل." if lang == "ar" else "Larger text and controls, clearer spacing, reduced motion, and improved keyboard focus.")
    body = body.replace("__SAVE__", t["settings_save"])
    if msg:
        body = body.replace("__MSG_CLASS__", "").replace("__MSG__", msg)
    else:
        body = body.replace("__MSG_CLASS__", "ss-msg").replace("__MSG__", "")
    return _page(t["title_settings"], body)


@app.route("/api/admin/auth-email-status", methods=["GET"])
@admin_api_required("access")
def api_admin_auth_email_status():
    """Non-sensitive production diagnostics for verification/reset email delivery."""
    state=_auth_email_provider_state()
    return jsonify({
        "ok": True,
        "provider": state.get("provider") or "none",
        "configured": bool(state.get("configured")),
        "missing": state.get("missing") or [],
        "invalid": state.get("invalid") or [],
        "sender_address_valid": bool(state.get("sender_address_valid")),
        "sender_domain": state.get("sender_domain") or None,
        "uses_resend_test_domain": bool(state.get("uses_resend_test_domain")),
        "production_recipient_delivery_ready": bool(state.get("production_recipient_delivery_ready")),
        "site_url": state.get("site_url"),
        "site_url_source": state.get("site_url_source"),
        "web_secret_configured": bool(os.environ.get("WEB_SECRET", "").strip()),
        "secure_session_cookie": bool(app.config.get("SESSION_COOKIE_SECURE")),
    })


@app.route("/api/admin/auth-email-test", methods=["POST"])
@admin_api_required("access")
def api_admin_auth_email_test():
    """Send one generic test message to the currently authenticated Admin."""
    user=_ss_user() or {}
    email=(user.get("email") or "").strip().lower()
    if not email:
        return jsonify({"ok":False,"error":"admin_email_unavailable"}),400
    ar=_lang()=="ar"
    subject="اختبار بريد SymptoSense" if ar else "SymptoSense email test"
    html=(
        '<div dir="rtl" style="font-family:Arial,sans-serif"><h2>نجح اتصال البريد</h2><p>هذه رسالة اختبار لإعداد Email Verification وPassword Reset في SymptoSense.</p></div>'
        if ar else
        '<div style="font-family:Arial,sans-serif"><h2>Email delivery is connected</h2><p>This is a test of the SymptoSense Email Verification and Password Reset delivery configuration.</p></div>'
    )
    ok,reason=_send_auth_email(email,subject,html,"auth_test")
    try: platform_v2.audit(int(user.get("id")),"test_auth_email","authentication","delivery",None,{"status":"success" if ok else "failed","reason":reason or "accepted"})
    except Exception: pass
    return jsonify({"ok":bool(ok),"error":None if ok else reason}), (200 if ok else 502)


@app.route("/api/auth/register", methods=["POST"])
def api_register():
    db.init_db(); platform_v2.init_schema()
    try:
        data=request.get_json(force=True)
        name=(data.get("name") or "").strip(); email=(data.get("email") or "").strip().lower()
        password=data.get("password") or ""; confirm=data.get("confirm",password) or ""
        if password!=confirm: return jsonify({"ok":False,"error":"password_mismatch"}),400
        if len(password)<8: return jsonify({"ok":False,"error":"password_too_short"}),400
        if "accept_terms" in data and data.get("accept_terms") is not True: return jsonify({"ok":False,"error":"terms_required"}),400
        user_id,err=db.create_ss_user(email,name,password)
        if not user_id: return jsonify({"ok":False,"error":err}),400
        session.clear(); session["pending_verification_user_id"]=int(user_id); session.permanent=True
        sent,send_error=_issue_verification_email(int(user_id),_lang())
        return jsonify({"ok":True,"verification_required":True,"email_sent":bool(sent),"email_error":send_error if not sent else None,"redirect_url":"/verify-email"}),201
    except Exception as e:
        app.logger.warning("API register failed; error_type=%s",type(e).__name__)
        return jsonify({"ok":False,"error":"registration_failed"}),500


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    db.init_db(); platform_v2.init_schema()
    try:
        data=request.get_json(force=True); email=(data.get("email") or "").strip().lower(); password=data.get("password") or ""
        network_origin=request.remote_addr or "unknown"
        if not platform_v2.login_attempt_allowed(email,network_origin):
            return jsonify({"ok":False,"error":"rate_limited"}),429
        result=db.authenticate_ss_user_status(email,password); user_id=result.get("user_id") if result.get("ok") else None
        if result.get("error")=="verification_required" and result.get("user_id"):
            session.clear(); session["pending_verification_user_id"]=int(result["user_id"]); session.permanent=True
            return jsonify({"ok":False,"error":"verification_required","redirect_url":"/verify-email"}),403
        if user_id: db.promote_existing_owner_admin(user_id)
        login_user=db.get_ss_user(user_id) if user_id else None
        platform_v2.record_login_attempt(email,network_origin,bool(user_id))
        platform_v2.log_login(email,user_id,bool(user_id),bool(login_user and login_user.get("role")=="admin"),request.headers.get("User-Agent",""))
        if user_id:
            session.clear(); session["ss_user_id"]=int(user_id); session.permanent=True
            is_admin=bool(login_user and login_user.get("role")=="admin")
            session["login_toast"]="admin" if is_admin else "user"
            if is_admin:
                session["admin_last_seen"]=int(datetime.now(timezone.utc).timestamp())
                try: platform_v2.audit(int(user_id),"login","admin_session","self",None,{"status":"success"})
                except Exception: pass
            redirect_target="/admin" if is_admin else "/profile"
            _admin_auth_debug("api_login_success",login_user,granted=is_admin,redirect_target=redirect_target)
            return jsonify({"ok":True,"redirect_url":redirect_target,"role":login_user.get("role","user"),"is_admin":is_admin,"user":login_user})
        _admin_auth_debug("api_login_failed",None,granted=False,redirect_target=None)
        code=result.get("error") or "incorrect_credentials"
        if db.is_owner_admin_email(email):
            try: platform_v2.audit(None,"login_failed","admin_session","owner",None,{"status":"failed"})
            except Exception: pass
        status=404 if code=="account_not_found" else 401
        if code=="account_unavailable": status=403
        return jsonify({"ok":False,"error":code,"create_account_url":"/register" if code=="account_not_found" else None}),status
    except Exception as e:
        app.logger.warning("API login failed; error_type=%s",type(e).__name__)
        return jsonify({"ok":False,"error":"login_failed"}),500


@app.route("/api/auth/resend-verification", methods=["POST"])
def api_resend_verification():
    uid=session.get("pending_verification_user_id")
    if not uid: return jsonify({"ok":False,"error":"verification_session_required"}),401
    sent,reason=_issue_verification_email(int(uid),_lang())
    if sent: return jsonify({"ok":True})
    if reason in {"cooldown","rate_limited"}: return jsonify({"ok":False,"error":"please_wait"}),429
    return jsonify({"ok":False,"error":reason or "email_send_failed"}),503


@app.route("/api/health-profile", methods=["GET", "POST"])
@login_required
def api_health_profile():
    db.init_db()
    uid = _ss_user_id()
    if request.method == "GET":
        profile = db.load_health_profile(uid) or {}
        return jsonify({"ok": True, "profile": profile})
    if not _service_consent_ok():
        return _consent_required_json("/manage")
    try:
        data = request.get_json(force=True)
        db.save_health_profile(uid, data)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200]})


@app.route("/api/health-profile/delete", methods=["POST"])
@login_required
def api_delete_health_profile():
    db.init_db()
    try:
        db.delete_health_profile(_ss_user_id())
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200]})


@app.route("/api/health-profile/field", methods=["POST"])
@login_required
def api_update_health_field():
    db.init_db()
    if not _service_consent_ok():
        return _consent_required_json("/manage")
    uid = _ss_user_id()
    data = request.get_json(force=True)
    field = data.get("field", "")
    value = data.get("value", "")
    allowed = {"display_name", "dob", "gender", "height", "weight", "activity_level", "medications", "allergies", "health_conditions", "extra_info", "lang"}
    if field not in allowed:
        return jsonify({"ok": False, "error": "Invalid field"})
    try:
        existing = db.load_health_profile(uid) or {}
        existing[field] = value
        db.save_health_profile(uid, existing)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200]})


@app.route("/api/health-profile/field/delete", methods=["POST"])
@login_required
def api_delete_health_field():
    db.init_db()
    uid = _ss_user_id()
    data = request.get_json(force=True)
    field = data.get("field", "")
    allowed = {"display_name", "dob", "gender", "height", "weight", "activity_level", "medications", "allergies", "health_conditions", "extra_info"}
    if field not in allowed:
        return jsonify({"ok": False, "error": "Invalid field"})
    try:
        existing = db.load_health_profile(uid) or {}
        existing[field] = ""
        db.save_health_profile(uid, existing)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200]})


@app.route("/api/consent/status", methods=["GET"])
def api_consent_status():
    try:
        state = privacy_features.get_consent(_consent_subject_key(), _ss_user_id())
        return jsonify({"ok": True, "consent": state, "ai_improvement_available": privacy_features.AI_IMPROVEMENT_ACTIVE})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:160]}), 500


@app.route("/api/consent/preferences", methods=["POST"])
def api_consent_preferences():
    try:
        data = request.get_json(silent=True) or {}
        # Explicit booleans only; omitted values are never interpreted as consent.
        service = data.get("service_usage") is True
        analytics = data.get("analytics_research") is True
        state = privacy_features.save_consent(_consent_subject_key(), _ss_user_id(), service, analytics)
        return jsonify({"ok": True, "consent": state})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:160]}), 400


@app.route("/api/privacy/withdraw-analytics", methods=["POST"])
@login_required
def api_withdraw_analytics():
    try:
        state = privacy_features.withdraw_analytics(_consent_subject_key(), _ss_user_id())
        return jsonify({"ok": True, "consent": state})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:160]}), 400


@app.route("/api/privacy/delete-health-data", methods=["POST"])
@login_required
def api_delete_health_data():
    try:
        result = privacy_features.delete_health_data(int(_ss_user_id()), _data_user_id())
        return jsonify({"ok": True, **result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:160]}), 500


@app.route("/api/privacy/download", methods=["GET"])
@login_required
def api_download_my_data():
    try:
        buf = privacy_features.user_export_bytes(int(_ss_user_id()), _data_user_id())
        return send_file(buf, mimetype="application/json; charset=utf-8", as_attachment=True, download_name="SymptoSense_My_Data_%s.json" % datetime.now(timezone.utc).date().isoformat())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:160]}), 500


@app.route("/api/privacy", methods=["GET", "POST"])
@login_required
def api_privacy():
    db.init_db()
    uid = _ss_user_id()
    if request.method == "GET":
        return jsonify({"ok": True, "privacy": db.load_privacy_settings(uid)})
    try:
        data = request.get_json(force=True)
        db.save_privacy_settings(uid, data)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200]})


@app.route("/api/account/delete", methods=["POST"])
@login_required
def api_delete_account():
    db.init_db()
    try:
        uid = _ss_user_id()
        platform_v2.init_schema()
        db.delete_ss_user(uid)
        session.clear()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200]})


@app.route("/api/chat-history", methods=["GET"])
@login_required
def api_chat_history():
    db.init_db()
    try:
        history = db.get_chat_history(_ss_user_id(), limit=50)
        return jsonify({"ok": True, "history": history})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200]})


@app.route("/api/chat-history/clear", methods=["POST"])
@login_required
def api_clear_chat_history():
    db.init_db()
    try:
        db.clear_chat_history(_ss_user_id())
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200]})


@app.route("/api/user-info", methods=["GET"])
def api_user_info():
    """Return current user info and profile for smart context."""
    db.init_db()
    uid = _ss_user_id()
    user = db.get_ss_user(uid) if uid else None
    profile = db.load_health_profile(uid) if uid else None
    privacy = db.load_privacy_settings(uid) if uid else None
    missing = []
    available = []
    critical_fields = {"age": "العمر|Age", "gender": "الجنس|Gender", "height": "الطول|Height", "weight": "الوزن|Weight"}
    if profile:
        age_val = profile.get("age") if profile.get("age") else None
        if not age_val and profile.get("dob"):
            try:
                from datetime import date
                born = date.fromisoformat(profile.get("dob"))
                today = date.today()
                age_val = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
            except Exception:
                pass
        profile_data = {
            "age": str(age_val) if age_val else "",
            "gender": profile.get("gender", ""),
            "height": profile.get("height", ""),
            "weight": profile.get("weight", ""),
            "medications": profile.get("medications", ""),
            "allergies": profile.get("allergies", ""),
            "health_conditions": profile.get("health_conditions", ""),
        }
        for k, label in critical_fields.items():
            if profile_data.get(k):
                available.append({"key": k, "label": label.split("|")[0] if _lang() == "ar" else label.split("|")[1], "value": profile_data[k]})
            else:
                missing.append({"key": k, "label": label.split("|")[0] if _lang() == "ar" else label.split("|")[1]})
        for extra_k in ["medications", "allergies", "health_conditions"]:
            if profile_data.get(extra_k):
                available.append({"key": extra_k, "label": extra_k, "value": profile_data[extra_k]})
    else:
        missing = [{"key": k, "label": v.split("|")[0] if _lang() == "ar" else v.split("|")[1]} for k, v in critical_fields.items()]
    return jsonify({
        "ok": True,
        "logged_in": bool(uid),
        "user": user,
        "role": (user or {}).get("role", "user"),
        "is_admin": bool(user and user.get("role") == "admin"),
        "profile": profile,
        "privacy": privacy,
        "missing_fields": missing,
        "available_fields": available,
        "has_profile": bool(profile),
    })


@app.route("/api/symptoms/extract", methods=["POST"])
def api_symptoms_extract():
    data=request.get_json(silent=True) or {}
    lang="en" if data.get("lang")=="en" else "ar"
    return jsonify({"ok": True, **advanced_features.smart_extract_symptoms(data.get("text", ""), lang)})


@app.route("/api/user/preferences", methods=["GET", "POST"])
@login_required
def api_user_preferences():
    advanced_features.init_schema()
    if request.method == "GET":
        return jsonify({"ok": True, "preferences": advanced_features.get_preferences(int(_ss_user_id()))})
    data=request.get_json(silent=True) or {}
    advanced_features.save_preferences(int(_ss_user_id()), accessibility_mode=bool(data.get("accessibility_mode")))
    return jsonify({"ok": True, "preferences": advanced_features.get_preferences(int(_ss_user_id()))})


@app.route("/api/health-summary", methods=["GET"])
@login_required
def api_health_summary():
    return jsonify({"ok": True, "summary": advanced_features.personal_health_summary(_data_user_id(), "en" if _lang()=="en" else "ar")})


@app.route("/api/analysis/<int:record_id>", methods=["GET", "DELETE"])
@login_required
def api_user_analysis_item(record_id):
    if request.method == "DELETE":
        ok=advanced_features.delete_user_analysis(_data_user_id(), record_id)
        return jsonify({"ok": ok}), (200 if ok else 404)
    row=advanced_features.get_user_analysis(_data_user_id(), record_id)
    if not row: return jsonify({"ok": False, "error": "not_found"}), 404
    return jsonify({"ok": True, "analysis": row})


@app.route("/api/analysis-history", methods=["GET"])
def api_analysis_history():
    """Return the logged-in user's recent analyses for profile page."""
    db.init_db()
    uid = _ss_user_id()
    if not uid:
        return jsonify({"ok": True, "records": [], "logged_in": False})
    records = db.get_records(_data_user_id(), limit=10, member_id=0)
    return jsonify({"ok": True, "records": records, "logged_in": True})


@app.route("/admin/login")
def admin_login():
    """Backward-compatible route; Admin uses the normal authenticated account."""
    return redirect(url_for("login", next="/admin"))


@app.route("/admin/verify")
def admin_verify():
    return redirect(url_for("admin"))


@app.route("/admin/claim", methods=["GET", "POST"])
def admin_claim():
    """Legacy route retained only so old links do not break.

    Admin assignment no longer uses a claim token. It is synchronized from the
    already-authenticated existing owner account.
    """
    if not _ss_user_id():
        return redirect(url_for("login", next="/admin"))
    if _admin_session_valid():
        return redirect(url_for("admin"))
    msg = "هذه الصفحة لم تعد مطلوبة. صلاحية Admin مرتبطة بحساب مالكة المشروع المصادق عليه فقط." if _lang() == "ar" else "This page is no longer required. Admin access is tied only to the authenticated project-owner account."
    return _page("Admin", '<div class="card" style="max-width:620px;margin:40px auto;text-align:center"><h2>🔒 Admin</h2><p class="muted">%s</p><a class="btn" href="/home">Home</a></div>' % msg), 403


@app.route("/admin")
def admin():
    if not _ss_user_id():
        _admin_auth_debug("admin_route", None, granted=False, redirect_target="/login?next=/admin")
        return redirect(url_for("login", next="/admin"))
    current_user = _ss_user()
    if not _admin_session_valid():
        if getattr(g, "admin_session_expired", False):
            return redirect(url_for("login", next="/admin"))
        _admin_auth_debug("admin_route", current_user, granted=False, redirect_target="403")
        t = L["en" if _lang() == "en" else "ar"]
        msg = "هذه الصفحة متاحة لحساب Admin فقط." if _lang() == "ar" else "This page is available to the Admin account only."
        return _page("Admin", '<div class="card" style="max-width:560px;margin:40px auto;text-align:center;"><h2>🔒 Admin</h2><p class="muted">%s</p><a class="btn" href="/home">%s</a></div>' % (msg, t.get("nav_home", "Home"))), 403
    _admin_auth_debug("admin_route", current_user, granted=True, redirect_target="/admin")
    medical_knowledge.init_schema()
    return render_template_string(
        DASHBOARD_HTML,
        admin_user=_ss_user(),
        csrf_token=_admin_csrf_token(),
        lang="en" if _lang() == "en" else "ar",
    )


@app.route("/admin/<section>")
def admin_section(section):
    allowed={"knowledge-graph","anomalies","audit-log","ask-data","insights","ai-performance","explainable-ai","data-export","privacy-analytics","health-analytics","medications","heatmap","settings","dropoff","live-activity"}
    if section not in allowed:
        return redirect(url_for("admin"))
    if not _ss_user_id():
        return redirect(url_for("login", next=request.path))
    if not _admin_session_valid():
        if getattr(g, "admin_session_expired", False):
            return redirect(url_for("login", next=request.path))
        return _page("Admin", '<div class="card" style="max-width:560px;margin:40px auto;text-align:center"><h2>🔒 403</h2><p class="muted">Admin access only.</p><a class="btn" href="/home">Home</a></div>'), 403
    return redirect(url_for("admin") + "#" + section)


@app.route("/robots.txt")
def robots_txt():
    base = _site_url()
    body = "User-agent: *\nAllow: /\nSitemap: " + base + "/sitemap.xml\n"
    return Response(body, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    base = _site_url()
    pages = ["/", "/home", "/chat", "/blood", "/search", "/calculators", "/meds", "/family", "/emergency", "/checkin", "/firstaid", "/tips", "/relax", "/profile", "/history", "/about", "/about-us", "/sources", "/privacy", "/terms", "/login", "/register", "/forgot-password", "/settings"]
    urls = "\n".join(
        "  <url><loc>%s</loc><changefreq>weekly</changefreq><priority>%.1f</priority></url>"
        % (base + p, 1.0 if p == "/" else 0.7)
        for p in pages
    )
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n%s\n</urlset>\n' % urls
    return Response(xml, mimetype="application/xml")


@app.route("/api/stats")
@admin_api_required("analytics")
def api_stats():
    db.init_db()
    stats = db.get_usage_stats(days=7)
    trends, _ = db.get_trends(days=7)
    top_symptoms = trends.most_common(8)
    urgency = dict(db.fetchall("SELECT urgency, COUNT(*) FROM records WHERE COALESCE(analytics_eligible,0)=1 GROUP BY urgency"))
    lang = dict(db.fetchall("SELECT lang, COUNT(*) FROM records WHERE COALESCE(analytics_eligible,0)=1 GROUP BY lang"))
    ages = [row[0] for row in db.fetchall("SELECT age FROM records WHERE age IS NOT NULL AND COALESCE(analytics_eligible,0)=1")]
    age_groups = {"0-17": 0, "18-30": 0, "31-45": 0, "46-60": 0, "60+": 0}
    for a in ages:
        if a <= 17: age_groups["0-17"] += 1
        elif a <= 30: age_groups["18-30"] += 1
        elif a <= 45: age_groups["31-45"] += 1
        elif a <= 60: age_groups["46-60"] += 1
        else: age_groups["60+"] += 1
    feedback = db.feedback_counts()
    return jsonify({
        "stats": stats,
        "symptoms": top_symptoms,
        "urgency": urgency,
        "lang": lang,
        "age_groups": list(age_groups.items()),
        "feedback": feedback,
        # Free-text feedback may contain health or identifying information, so
        # the Admin analytics endpoint exposes aggregate counts only.
        "fb_comments": [],
        "assistant_feedback": db.assistant_feedback_stats(),
        "db_backend": "PostgreSQL" if db.USE_POSTGRES else "SQLite",
    })


# ---------------------------------------------------------------- Medical Knowledge Base APIs

def _mk_error(exc, status=400):
    request_id=getattr(g,"request_id","")
    app.logger.warning("API request failed; request_id=%s route=%s error_type=%s",request_id,request.path,type(exc).__name__)
    return jsonify({"ok":False,"error":"تعذر إكمال الطلب حاليًا." if _lang()=="ar" else "Unable to complete the request right now.","request_id":request_id}),status


@app.route("/api/diseases", methods=["GET"])
def api_diseases():
    try:
        rows = medical_knowledge.list_entities(
            "diseases", False, request.args.get("q", ""),
            request.args.get("category"), request.args.get("severity"),
        )
        return jsonify({"ok": True, "diseases": rows})
    except Exception as exc:
        return _mk_error(exc)


@app.route("/api/diseases/<int:entity_id>", methods=["GET"])
def api_disease_detail(entity_id):
    item = medical_knowledge.get_entity("disease", entity_id, public=True)
    return jsonify({"ok": bool(item), "disease": item}) if item else _mk_error("not_found", 404)


@app.route("/api/diseases/<int:entity_id>/sources", methods=["GET"])
def api_disease_sources(entity_id):
    item = medical_knowledge.get_entity("disease", entity_id, public=True)
    return jsonify({"ok": bool(item), "sources": (item or {}).get("sources", [])}) if item else _mk_error("not_found", 404)


@app.route("/api/symptoms", methods=["GET"])
def api_symptoms():
    try:
        rows = medical_knowledge.list_entities(
            "symptoms", False, request.args.get("q", ""), request.args.get("category")
        )
        return jsonify({"ok": True, "symptoms": rows})
    except Exception as exc:
        return _mk_error(exc)


@app.route("/api/symptoms/<int:entity_id>", methods=["GET"])
def api_symptom_detail(entity_id):
    item = medical_knowledge.get_entity("symptom", entity_id, public=True)
    return jsonify({"ok": bool(item), "symptom": item}) if item else _mk_error("not_found", 404)


@app.route("/api/symptoms/<int:entity_id>/sources", methods=["GET"])
def api_symptom_sources(entity_id):
    item = medical_knowledge.get_entity("symptom", entity_id, public=True)
    return jsonify({"ok": bool(item), "sources": (item or {}).get("sources", [])}) if item else _mk_error("not_found", 404)


@app.route("/api/sources", methods=["GET"])
def api_sources():
    try:
        rows = medical_knowledge.list_entities(
            "sources", False, request.args.get("q", ""), verification="verified"
        )
        return jsonify({"ok": True, "sources": rows})
    except Exception as exc:
        return _mk_error(exc)


@app.route("/api/admin/knowledge/bootstrap", methods=["GET"])
@admin_api_required("access")
def api_admin_knowledge_bootstrap():
    try:
        include = _admin_allowed("medical")
        return jsonify({
            "ok": True,
            "role": _admin_role(),
            "can_edit": include,
            # Analytics admins receive aggregate statistics only.  Medical
            # content rows are available only to the two editing roles.
            "categories": medical_knowledge.categories() if include else [],
            "diseases": medical_knowledge.list_entities("diseases", True) if include else [],
            "symptoms": medical_knowledge.list_entities("symptoms", True) if include else [],
            "sources": medical_knowledge.list_entities("sources", True) if include else [],
            "relationships": medical_knowledge.list_relationships() if include else [],
            "red_flags": medical_knowledge.list_entities("red_flags", True) if include else [],
            "statistics": medical_knowledge.statistics(),
        })
    except Exception as exc:
        return _mk_error(exc)


@app.route("/api/admin/knowledge/stats", methods=["GET"])
@admin_api_required("analytics")
def api_admin_knowledge_stats():
    return jsonify({"ok": True, "statistics": medical_knowledge.statistics()})


@app.route("/api/admin/categories", methods=["GET", "POST"])
@admin_api_required("medical")
def api_admin_categories():
    try:
        if request.method == "GET":
            return jsonify({"ok": True, "categories": medical_knowledge.categories(request.args.get("q", ""), True)})
        return jsonify({"ok": True, "category": medical_knowledge.save_category(request.get_json(silent=True) or {}, _ss_user())}), 201
    except Exception as exc:
        return _mk_error(exc)


@app.route("/api/admin/categories/<int:entity_id>", methods=["PUT", "DELETE"])
@admin_api_required("medical")
def api_admin_category(entity_id):
    try:
        if request.method == "DELETE":
            return jsonify({"ok": medical_knowledge.delete_category(entity_id, _ss_user())})
        return jsonify({"ok": True, "category": medical_knowledge.save_category(request.get_json(silent=True) or {}, _ss_user(), entity_id)})
    except Exception as exc:
        return _mk_error(exc)


@app.route("/api/admin/diseases", methods=["GET", "POST"])
@admin_api_required("medical")
def api_admin_diseases():
    try:
        if request.method == "GET":
            return jsonify({"ok": True, "diseases": medical_knowledge.list_entities("diseases", True, request.args.get("q", ""), request.args.get("category"), request.args.get("severity"))})
        return jsonify({"ok": True, "disease": medical_knowledge.save_disease(request.get_json(silent=True) or {}, _ss_user())}), 201
    except Exception as exc:
        return _mk_error(exc)


@app.route("/api/admin/diseases/<int:entity_id>", methods=["GET", "PUT", "DELETE"])
@admin_api_required("medical")
def api_admin_disease(entity_id):
    try:
        if request.method == "GET":
            item = medical_knowledge.get_entity("disease", entity_id)
            return jsonify({"ok": bool(item), "disease": item}) if item else _mk_error("not_found", 404)
        if request.method == "DELETE":
            return jsonify({"ok": medical_knowledge.delete_entity("disease", entity_id, _ss_user())})
        return jsonify({"ok": True, "disease": medical_knowledge.save_disease(request.get_json(silent=True) or {}, _ss_user(), entity_id)})
    except Exception as exc:
        return _mk_error(exc)


@app.route("/api/admin/symptoms", methods=["GET", "POST"])
@admin_api_required("medical")
def api_admin_symptoms():
    try:
        if request.method == "GET":
            return jsonify({"ok": True, "symptoms": medical_knowledge.list_entities("symptoms", True, request.args.get("q", ""), request.args.get("category"))})
        return jsonify({"ok": True, "symptom": medical_knowledge.save_symptom(request.get_json(silent=True) or {}, _ss_user())}), 201
    except Exception as exc:
        return _mk_error(exc)


@app.route("/api/admin/symptoms/<int:entity_id>", methods=["GET", "PUT", "DELETE"])
@admin_api_required("medical")
def api_admin_symptom(entity_id):
    try:
        if request.method == "GET":
            item = medical_knowledge.get_entity("symptom", entity_id)
            return jsonify({"ok": bool(item), "symptom": item}) if item else _mk_error("not_found", 404)
        if request.method == "DELETE":
            return jsonify({"ok": medical_knowledge.delete_entity("symptom", entity_id, _ss_user())})
        return jsonify({"ok": True, "symptom": medical_knowledge.save_symptom(request.get_json(silent=True) or {}, _ss_user(), entity_id)})
    except Exception as exc:
        return _mk_error(exc)


@app.route("/api/admin/sources", methods=["GET", "POST"])
@admin_api_required("medical")
def api_admin_sources():
    try:
        if request.method == "GET":
            return jsonify({"ok": True, "sources": medical_knowledge.list_entities("sources", True, request.args.get("q", ""), verification=request.args.get("verification"))})
        return jsonify({"ok": True, "source": medical_knowledge.save_source(request.get_json(silent=True) or {}, _ss_user())}), 201
    except Exception as exc:
        return _mk_error(exc)


@app.route("/api/admin/sources/<int:entity_id>", methods=["GET", "PUT", "DELETE"])
@admin_api_required("medical")
def api_admin_source(entity_id):
    try:
        if request.method == "GET":
            item = medical_knowledge.get_entity("source", entity_id)
            return jsonify({"ok": bool(item), "source": item}) if item else _mk_error("not_found", 404)
        if request.method == "DELETE":
            return jsonify({"ok": medical_knowledge.delete_entity("source", entity_id, _ss_user())})
        return jsonify({"ok": True, "source": medical_knowledge.save_source(request.get_json(silent=True) or {}, _ss_user(), entity_id)})
    except Exception as exc:
        return _mk_error(exc)


@app.route("/api/admin/relationships", methods=["GET", "POST"])
@admin_api_required("medical")
def api_admin_relationships():
    try:
        if request.method == "GET":
            return jsonify({"ok": True, "relationships": medical_knowledge.list_relationships(request.args.get("q", ""))})
        return jsonify({"ok": True, "relationship": medical_knowledge.save_relationship(request.get_json(silent=True) or {}, _ss_user())}), 201
    except Exception as exc:
        return _mk_error(exc)


@app.route("/api/admin/relationships/<int:entity_id>", methods=["PUT", "DELETE"])
@admin_api_required("medical")
def api_admin_relationship(entity_id):
    try:
        if request.method == "DELETE":
            return jsonify({"ok": medical_knowledge.delete_entity("relationship", entity_id, _ss_user())})
        return jsonify({"ok": True, "relationship": medical_knowledge.save_relationship(request.get_json(silent=True) or {}, _ss_user(), entity_id)})
    except Exception as exc:
        return _mk_error(exc)


@app.route("/api/admin/red-flags", methods=["GET", "POST"])
@admin_api_required("medical")
def api_admin_red_flags():
    try:
        if request.method == "GET":
            return jsonify({"ok": True, "red_flags": medical_knowledge.list_entities("red_flags", True, request.args.get("q", ""))})
        return jsonify({"ok": True, "red_flag": medical_knowledge.save_red_flag(request.get_json(silent=True) or {}, _ss_user())}), 201
    except Exception as exc:
        return _mk_error(exc)


@app.route("/api/admin/red-flags/<int:entity_id>", methods=["GET", "PUT", "DELETE"])
@admin_api_required("medical")
def api_admin_red_flag(entity_id):
    try:
        if request.method == "GET":
            item = medical_knowledge.get_entity("red_flag", entity_id)
            return jsonify({"ok": bool(item), "red_flag": item}) if item else _mk_error("not_found", 404)
        if request.method == "DELETE":
            return jsonify({"ok": medical_knowledge.delete_entity("red_flag", entity_id, _ss_user())})
        return jsonify({"ok": True, "red_flag": medical_knowledge.save_red_flag(request.get_json(silent=True) or {}, _ss_user(), entity_id)})
    except Exception as exc:
        return _mk_error(exc)


@app.route("/api/admin/<kind>/<int:entity_id>/sources", methods=["POST", "DELETE"])
@admin_api_required("medical")
def api_admin_source_link(kind, entity_id):
    if kind not in {"diseases", "symptoms"}:
        return _mk_error("invalid_entity", 404)
    singular = "disease" if kind == "diseases" else "symptom"
    try:
        data = request.get_json(silent=True) or {}
        if request.method == "DELETE":
            return jsonify({"ok": medical_knowledge.delete_source_link(singular, entity_id, int(data.get("source_id")), _ss_user())})
        return jsonify({"ok": True, "link": medical_knowledge.save_source_link(singular, entity_id, data, _ss_user())})
    except Exception as exc:
        return _mk_error(exc)


@app.route("/api/admin/knowledge/audit", methods=["GET"])
@admin_api_required("medical")
def api_admin_knowledge_audit():
    return jsonify({"ok": True, "audit": medical_knowledge.audit_log(request.args.get("limit", 100))})


@app.route("/api/admin/knowledge/versions/<entity_type>/<int:entity_id>", methods=["GET"])
@admin_api_required("medical")
def api_admin_knowledge_versions(entity_type, entity_id):
    return jsonify({"ok": True, "versions": medical_knowledge.versions(entity_type, entity_id)})


@app.route("/api/admin/system-health", methods=["GET"])
@admin_api_required("medical")
def api_admin_system_health():
    started = time.perf_counter()
    health = medical_knowledge.system_health()
    required = {"/admin", "/api/admin/v2/analytics", "/api/admin/system-health"}
    registered = {rule.rule for rule in app.url_map.iter_rules()}
    missing = sorted(required - registered)
    health["components"]["api"] = {
        "status": "online" if not missing else "offline",
        "response_ms": round((time.perf_counter() - started) * 1000, 1),
        "error": None if not missing else "Missing routes: " + ", ".join(missing),
    }
    if not _configured_web_secret and health["components"].get("authentication", {}).get("status") == "online":
        health["components"]["authentication"]["status"] = "degraded"
        health["components"]["authentication"]["error"] = "WEB_SECRET is not configured; sessions use an ephemeral process key"
    return jsonify({"ok": True, "health": health})


@app.route("/api/admin/audit", methods=["GET"])
@admin_api_required("access")
def api_admin_audit():
    limit = max(1, min(300, int(request.args.get("limit", 150))))
    medical_rows = medical_knowledge.audit_log(limit)
    system_rows = platform_v2.audit_log(limit)
    privacy_rows = privacy_features.privacy_audit_events(limit)
    rows = [{**row, "source": "medical"} for row in medical_rows]
    for row in system_rows:
        rows.append({
            "id": row.get("id"), "admin_id": row.get("admin_id"),
            "action": row.get("action"), "entity_type": row.get("entity_type"), "entity_id": row.get("entity_id"),
            "previous_value": row.get("previous_value"), "new_value": row.get("new_value"), "timestamp": row.get("timestamp"), "source": "system",
        })
    rows.extend(privacy_rows)
    for row in rows:
        action = str(row.get("action") or "")
        row["result"] = "failed" if ("failed" in action or "denied" in action) else ("expired" if "timeout" in action else "success")
        row["admin_account"] = db.OWNER_ADMIN_EMAIL if (row.get("admin_id") or row.get("entity_id") == "owner") else ("User/Privacy" if row.get("source") == "privacy" else "System")
    rows.sort(key=lambda x: str(x.get("timestamp") or ""), reverse=True)
    return jsonify({"ok": True, "audit": rows[:limit]})


@app.route("/api/admin/users", methods=["GET"])
@admin_api_required("super")
def api_admin_users():
    return jsonify({"ok": True, "users": platform_v2.list_users_admin()})


@app.route("/api/admin/users/<int:user_id>/role", methods=["PUT"])
@admin_api_required("access")
def api_admin_user_role(user_id):
    return jsonify({"ok": False, "error": "role_management_disabled"}), 403


@app.route("/api/admin/v2/analytics", methods=["GET"])
@admin_api_required("analytics")
def api_admin_v2_analytics():
    try:
        return jsonify({"ok": True, "analytics": platform_v2.analytics_summary(request.args.get("days", 30))})
    except Exception as exc:
        return _mk_error(exc)


@app.route("/api/admin/complete-analytics", methods=["GET"])
@admin_api_required("analytics")
def api_admin_complete_analytics():
    try:
        return jsonify({"ok": True, "analytics": admin_complete.complete_analytics(request.args.get("days", 30))})
    except Exception as exc:
        return _mk_error(exc)


@app.route("/api/admin/content", methods=["GET", "POST"])
@admin_api_required("medical")
def api_admin_content():
    try:
        if request.method == "GET":
            return jsonify({"ok": True, "content": platform_v2.list_content(False, request.args.get("q", ""), request.args.get("type", ""))})
        return jsonify({"ok": True, "content": platform_v2.save_content(request.get_json(silent=True) or {}, int(_ss_user_id()))})
    except Exception as exc:
        return _mk_error(exc)


@app.route("/api/admin/content/<int:content_id>", methods=["GET", "PUT", "DELETE"])
@admin_api_required("medical")
def api_admin_content_item(content_id):
    try:
        if request.method == "GET":
            item = platform_v2.get_content(content_id)
            return jsonify({"ok": bool(item), "content": item}) if item else _mk_error("not_found", 404)
        if request.method == "DELETE":
            platform_v2.delete_content(content_id, int(_ss_user_id()))
            return jsonify({"ok": True})
        return jsonify({"ok": True, "content": platform_v2.save_content(request.get_json(silent=True) or {}, int(_ss_user_id()), content_id)})
    except Exception as exc:
        return _mk_error(exc)


@app.route("/api/content", methods=["GET"])
def api_public_content():
    try:
        return jsonify({"ok": True, "content": platform_v2.list_content(True, request.args.get("q", ""), request.args.get("type", ""))})
    except Exception as exc:
        return _mk_error(exc)


@app.route("/api/admin/users/<int:user_id>/status", methods=["PUT"])
@admin_api_required("super")
def api_admin_user_status(user_id):
    try:
        data = request.get_json(silent=True) or {}
        return jsonify({"ok": True, "user": platform_v2.set_user_status(user_id, data.get("status"), int(_ss_user_id()))})
    except Exception as exc:
        return _mk_error(exc)


@app.route("/api/admin/security/activity", methods=["GET"])
@admin_api_required("super")
def api_admin_security_activity():
    return jsonify({"ok": True, "activity": platform_v2.login_activity(request.args.get("limit", 200))})


@app.route("/api/admin/security/audit", methods=["GET"])
@admin_api_required("super")
def api_admin_security_audit():
    return jsonify({"ok": True, "audit": platform_v2.audit_log(request.args.get("limit", 200))})


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


@app.route("/api/admin/analytics-export/preview", methods=["GET"])
@admin_api_required("analytics")
def api_admin_analytics_export_preview():
    try:
        filters=_admin_analytics_filters()
        return jsonify({"ok":True, **admin_operational.medication_analytics_preview(filters)})
    except Exception as exc: return _mk_error(exc)


@app.route("/api/admin/analytics-export/xlsx", methods=["GET"])
@admin_api_required("analytics")
def api_admin_analytics_export_xlsx():
    filters=_admin_analytics_filters()
    try:
        supplied=request.headers.get("X-CSRF-Token",""); expected=session.get("admin_csrf","")
        if not expected or not secrets.compare_digest(supplied,expected):
            return jsonify({"ok":False,"error":"csrf_failed"}),403
        buf=admin_operational.export_medication_analytics_excel(filters)
        filter_types=[k for k in ("age_group","gender","medication","symptom","risk") if filters.get(k)]
        platform_v2.audit(int(_ss_user_id()),"exported","analytics","medication_analytics",None,{"period":filters.get("period"),"filter_types":filter_types,"privacy":"aggregated_anonymized"})
        stamp=datetime.now().strftime("%Y-%m-%d")
        return send_file(buf,mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",as_attachment=True,download_name=f"SymptoSense_Data_Analytics_{stamp}.xlsx")
    except Exception as exc:
        try: platform_v2.audit(int(_ss_user_id()),"export_failed","analytics","medication_analytics",None,{"error_type":type(exc).__name__})
        except Exception: pass
        return _mk_error(exc)


@app.route("/api/admin/dropoff", methods=["GET"])
@admin_api_required("analytics")
def api_admin_dropoff():
    try:
        period=(request.args.get("period") or "30d").lower()
        if period not in {"today","7d","30d","90d","custom"}: period="30d"
        device=(request.args.get("device") or "").lower()
        if device not in {"","mobile","desktop","tablet"}: device=""
        return jsonify({"ok":True,"dropoff":admin_operational.dropoff_analysis(period,request.args.get("start"),request.args.get("end"),device)})
    except Exception as exc: return _mk_error(exc)


@app.route("/api/admin/live-activity", methods=["GET"])
@admin_api_required("analytics")
def api_admin_live_activity():
    try:
        cat=(request.args.get("category") or "all").lower()
        if cat not in {"all","analysis","assistant","reports","authentication","system"}: cat="all"
        win=(request.args.get("window") or "hour").lower()
        if win not in {"hour","today","7d"}: win="hour"
        return jsonify({"ok":True,"activity":admin_operational.live_activity(request.args.get("limit",80),cat,win)})
    except Exception as exc: return _mk_error(exc)


@app.route("/api/admin/ui-audit", methods=["POST"])
@admin_api_required("access")
def api_admin_ui_audit():
    data=request.get_json(silent=True) or {}; action=str(data.get("action") or "")
    allowed={"opened_analytics","changed_analytics_filters","opened_live_activity","changed_dashboard_settings","opened_dropoff"}
    if action not in allowed: return jsonify({"ok":False,"error":"invalid_action"}),400
    platform_v2.audit(int(_ss_user_id()),action,"admin_dashboard",None,None,{"section":str(data.get("section") or "")[:40]})
    return jsonify({"ok":True})


@app.route("/api/admin/export/xlsx", methods=["GET"])
@admin_api_required("access")
def api_admin_export_xlsx():
    try:
        supplied=request.headers.get("X-CSRF-Token",""); expected=session.get("admin_csrf","")
        if not expected or not secrets.compare_digest(supplied,expected):
            return jsonify({"ok":False,"error":"csrf_failed"}),403
        buf = admin_complete.export_admin_workbook()
        platform_v2.audit(int(_ss_user_id()), "exported", "admin_data", "excel", None, {"format": "xlsx", "privacy": "pseudonymized_consent_eligible", "sheets": 5})
        stamp = datetime.now().strftime("%Y-%m-%d")
        return send_file(buf, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", as_attachment=True, download_name=f"SymptoSense_Export_{stamp}.xlsx")
    except Exception as exc:
        try: platform_v2.audit(int(_ss_user_id()), "export_failed", "admin_data", "excel", None, {"error_type": type(exc).__name__})
        except Exception: pass
        return _mk_error(exc)


@app.route("/api/admin/audit/export", methods=["GET"])
@admin_api_required("access")
def api_admin_audit_export():
    try:
        supplied=request.headers.get("X-CSRF-Token",""); expected=session.get("admin_csrf","")
        if not expected or not secrets.compare_digest(supplied,expected):
            return jsonify({"ok":False,"error":"csrf_failed"}),403
        buf = advanced_features.export_audit_excel()
        platform_v2.audit(int(_ss_user_id()), "exported", "audit_log", "excel", None, {"format": "xlsx"})
        stamp = datetime.now().strftime("%Y-%m-%d")
        return send_file(buf, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", as_attachment=True, download_name=f"SymptoSense_Audit_{stamp}.xlsx")
    except Exception as exc:
        return _mk_error(exc)


@app.route("/api/admin/ai-performance", methods=["GET"])
@admin_api_required("analytics")
def api_admin_ai_performance():
    try:
        performance=advanced_features.ai_performance(request.args.get("days",30))
        performance["model"]=admin_complete.model_card()
        return jsonify({"ok":True,"performance":performance})
    except Exception as exc: return _mk_error(exc)


@app.route("/api/admin/explainable-ai", methods=["GET"])
@admin_api_required("analytics")
def api_admin_explainable_ai():
    try:
        return jsonify({"ok": True, "explainability": admin_complete.explainable_ai()})
    except Exception as exc:
        return _mk_error(exc)


@app.route("/api/admin/profile", methods=["GET"])
@admin_api_required("access")
def api_admin_profile():
    user=_ss_user() or {}
    try: timeout=max(5,min(240,int(os.environ.get("ADMIN_SESSION_TIMEOUT_MINUTES","30"))))
    except (TypeError,ValueError): timeout=30
    return jsonify({"ok":True,"profile":{
        "email":user.get("email"),"role":"Administrator","last_login":user.get("last_login"),
        "session_timeout_minutes":timeout,"change_password_available":True,
        "two_factor_available":False,"two_factor_status":"not_supported_by_current_authentication_backend",
    }})


@app.route("/api/admin/profile/password", methods=["POST"])
@admin_api_required("access")
def api_admin_profile_password():
    data=request.get_json(silent=True) or {}
    current=str(data.get("current_password") or ""); new=str(data.get("new_password") or "")
    confirm=str(data.get("confirm_password") or "")
    if not hmac.compare_digest(new,confirm):
        return jsonify({"ok":False,"error":"password_mismatch"}),400
    ok,error=db.change_ss_user_password(int(_ss_user_id()),current,new)
    if not ok:
        try: platform_v2.audit(int(_ss_user_id()),"password_change_failed","admin_security","self",None,{"status":"failed","reason":error})
        except Exception: pass
        return jsonify({"ok":False,"error":error}),400
    platform_v2.audit(int(_ss_user_id()),"password_changed","admin_security","self",None,{"status":"success"})
    # Rotate all session state after a credential change to prevent fixation.
    user_id=int(_ss_user_id()); session.clear(); session["ss_user_id"]=user_id; session.permanent=True
    session["admin_last_seen"]=int(datetime.now(timezone.utc).timestamp()); _admin_csrf_token()
    return jsonify({"ok":True,"message":"password_changed"})


@app.route("/api/admin/knowledge-graph", methods=["GET"])
@admin_api_required("medical")
def api_admin_knowledge_graph():
    try: return jsonify({"ok": True, "graph": advanced_features.knowledge_graph_data()})
    except Exception as exc: return _mk_error(exc)


@app.route("/api/admin/anomalies", methods=["GET"])
@admin_api_required("analytics")
def api_admin_anomalies():
    try: return jsonify({"ok": True, "anomalies": advanced_features.anomaly_detection()})
    except Exception as exc: return _mk_error(exc)


@app.route("/api/admin/automatic-insights", methods=["GET"])
@admin_api_required("analytics")
def api_admin_automatic_insights():
    try: return jsonify({"ok": True, "insights": advanced_features.automatic_insights()})
    except Exception as exc: return _mk_error(exc)


@app.route("/api/admin/privacy-analytics", methods=["GET"])
@admin_api_required("access")
def api_admin_privacy_analytics():
    try:
        return jsonify({"ok": True, "analytics": privacy_features.anonymous_health_analytics()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:160]}), 500


@app.route("/api/admin/ask-data", methods=["POST"])
@admin_api_required("analytics")
def api_admin_ask_data():
    try:
        data=request.get_json(silent=True) or {}
        answer=advanced_features.ask_your_data(data.get("question", ""), "en" if data.get("lang")=="en" else "ar")
        if answer.get("ok"):
            platform_v2.audit(int(_ss_user_id()), "queried", "ask_your_data", "aggregate", None, {"result_type": answer.get("type")})
        return jsonify(answer), (200 if answer.get("ok") else 400)
    except Exception as exc: return _mk_error(exc)


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
            (["ضيق تنفس", "ضيق في التنفس", "صعوبة التنفس", "نفس", "اختناق"], "🫁 ضيق التنفس"),
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
            (["أسبوعين", "اسبوعين"], "🗓️ أكثر من أسبوعين"), (["أسبوع", "اسبوع"], "🗓️ 1-2 أسبوع"), (["شهر"], "📆 أكثر من شهر"),
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
            (["four days", "five days", "4 days", "5 days"], "📅 4-7 days"), (["two weeks", "2 weeks"], "🗓️ More than 2 weeks"),
            (["week"], "🗓️ 1-2 weeks"), (["month"], "📆 More than a month"),
        ]
        locations = [
            (["right side", "on the right", "right lower"], "Right side"), (["left side", "on the left", "left lower"], "Left side"),
            (["lower abdomen", "lower belly"], "Lower abdomen"), (["upper abdomen", "upper belly"], "Upper abdomen"), (["middle", "center"], "Center"),
        ]
        words = {"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,"ten":10}
    found=[]
    for kws,label in sym_map:
        if any(k in low for k in kws) and label not in found: found.append(label)
    duration=next((label for kws,label in dur_rules if any(k in low for k in kws)),None)
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


@app.route("/api/voice/parse", methods=["POST"])
def api_voice_parse():
    if not _service_consent_ok():
        return jsonify({"ok":False,"error":"consent_required","consent_url":"/consent?next=/chat"}),403
    data=request.get_json(silent=True) or {}; text=str(data.get("text") or "").strip()[:1200]
    lang="en" if data.get("lang")=="en" else "ar"
    if not text:
        return jsonify({"ok":False,"error":"empty_transcript"}),400
    return jsonify({"ok":True,"text":text,"parsed":_voice_parse(text,lang),"audio_stored":False})


@app.route("/api/voice", methods=["POST"])
def api_voice():
    # Raw audio upload is intentionally disabled: voice input uses the browser's
    # speech-recognition capability and only the resulting text is sent here.
    return jsonify({"ok":False,"error":"raw_audio_upload_disabled_use_client_speech_recognition","audio_stored":False}),410


@app.route("/api/blood/history", methods=["GET"])
def api_blood_history():
    try:
        db.init_db()
        member_id = request.args.get("member")
        tests = db.get_blood_tests(_data_user_id(), limit=8,
                                   member_id=int(member_id) if member_id else None)
        out = []
        for bt in tests:
            data = bt["data"] or {}
            out.append({
                "id": bt["id"],
                "timestamp": bt.get("timestamp") or "",
                "level": data.get("level"),
                "summary": data.get("summary"),
                "indicators": data.get("indicators") or [],
            })
        return jsonify({"ok": True, "tests": out})
    except Exception as e:
        request_id=getattr(g,"request_id","")
        app.logger.error("Analysis failed; request_id=%s error_type=%s",request_id,type(e).__name__)
        return jsonify({"ok":False,"error":"تعذر تشغيل التحليل حاليًا. حاول مرة أخرى." if _lang()=="ar" else "Unable to run the assessment right now. Please try again.","request_id":request_id}),500


@app.route("/api/family", methods=["GET", "POST"])
@api_login_required
def api_family():
    try:
        db.init_db()
        uid = _data_user_id()
        if request.method == "POST":
            if not _service_consent_ok(): return _consent_required_json("/family")
            data = request.get_json(force=True)
            mid = db.save_member(
                uid,
                str(data.get("relation") or "other"),
                str(data.get("name") or "").strip(),
                str(data.get("age") or "").strip(),
                str(data.get("gender") or "").strip(),
                str(data.get("conditions") or "").strip(),
                str(data.get("medications") or "").strip(),
                str(data.get("allergies") or "").strip(),
                str(data.get("notes") or "").strip(),
            )
            return jsonify({"ok": True, "id": mid})
        members = db.list_members(uid)
        for m in members:
            m["records_count"] = len(db.get_records(uid, limit=100, member_id=m["id"]))
            m["adherence"] = db.med_adherence(uid, member_id=m["id"])["percent"]
        return jsonify({"ok": True, "members": members})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"})


@app.route("/api/family/<int:mid>", methods=["POST", "DELETE"])
@api_login_required
def api_family_one(mid):
    try:
        db.init_db()
        uid = _data_user_id()
        if request.method == "DELETE":
            db.delete_member(uid, mid)
            return jsonify({"ok": True})
        if not _service_consent_ok(): return _consent_required_json("/family")
        data = request.get_json(force=True)
        db.update_member(
            uid, mid,
            str(data.get("relation") or "other"),
            str(data.get("name") or "").strip(),
            str(data.get("age") or "").strip(),
            str(data.get("gender") or "").strip(),
            str(data.get("conditions") or "").strip(),
            str(data.get("medications") or "").strip(),
            str(data.get("allergies") or "").strip(),
            str(data.get("notes") or "").strip(),
        )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"})


@app.route("/api/analytics/journey", methods=["POST"])
def api_analytics_journey():
    if not _analytics_consent_ok():
        return jsonify({"ok":True,"recorded":False,"reason":"analytics_consent_disabled"})
    data=request.get_json(silent=True) or {}; stage=str(data.get("stage") or "")
    if stage not in admin_operational.JOURNEY_STAGES:
        return jsonify({"ok":False,"error":"invalid_stage"}),400
    try:
        admin_operational.record_journey(_analytics_session_id(),stage,request.headers.get("User-Agent", ""))
        admin_operational.touch_session(_analytics_session_id(),request.headers.get("User-Agent", ""))
        if stage=="analysis": platform_v2.record_usage("analysis_started","/chat",_lang(),request.headers.get("User-Agent",""),200,None)
        elif stage=="reanalyze": platform_v2.record_usage("reanalysis_started","/chat",_lang(),request.headers.get("User-Agent",""),200,None)
        return jsonify({"ok":True})
    except Exception:
        return jsonify({"ok":True})


@app.route("/api/meds/plan", methods=["GET", "POST"])
@api_login_required
def api_meds_plan():
    try:
        db.init_db(); medication_push.init_schema(); uid=_data_user_id()
        if request.method=="POST":
            if not _service_consent_ok(): return _consent_required_json("/meds")
            data=request.get_json(silent=True) or {}
            pid=medication_push.save_plan(uid,data)
            return jsonify({"ok":True,"id":pid})
        member_id=request.args.get("member")
        plans=medication_push.list_plans(uid,member_id=int(member_id) if member_id else None)
        members={m["id"]:m["name"] for m in db.list_members(uid)}
        for plan in plans: plan["member_name"]=members.get(plan["member_id"], _t("me_short") if plan["member_id"]==0 else "")
        return jsonify({"ok":True,"plans":plans})
    except PermissionError as exc: return jsonify({"ok":False,"error":str(exc)}),403
    except Exception as exc: return _mk_error(exc)


@app.route("/api/meds/plan/<int:pid>", methods=["PUT", "DELETE"])
@api_login_required
def api_meds_plan_item(pid):
    try:
        medication_push.init_schema(); uid=_data_user_id()
        if request.method=="DELETE":
            if not medication_push.disable_plan(uid,pid): return jsonify({"ok":False,"error":"not_found"}),404
            return jsonify({"ok":True})
        if not _service_consent_ok(): return _consent_required_json("/meds")
        updated=medication_push.save_plan(uid,request.get_json(silent=True) or {},plan_id=pid)
        return jsonify({"ok":True,"id":updated})
    except PermissionError as exc: return jsonify({"ok":False,"error":str(exc)}),403
    except Exception as exc: return _mk_error(exc)


@app.route("/api/meds/today", methods=["GET"])
@api_login_required
def api_meds_today():
    try:
        uid=_data_user_id(); plans=medication_push.plans_today(uid)
        members={m["id"]:m["name"] for m in db.list_members(uid)}
        for plan in plans: plan["member_name"]=members.get(plan["member_id"], _t("me_short") if plan["member_id"]==0 else "")
        return jsonify({"ok":True,"plans":plans})
    except Exception as exc: return _mk_error(exc)


@app.route("/api/meds/log", methods=["POST"])
@api_login_required
def api_meds_log():
    if not _service_consent_ok(): return _consent_required_json("/meds")
    try:
        data=request.get_json(silent=True) or {}; plan_id=int(data.get("plan_id") or 0); log_time=str(data.get("time") or "")
        status=str(data.get("status") or "taken"); log_date=str(data.get("date") or datetime.now(timezone.utc).date().isoformat())
        if not plan_id or not log_time or status not in ("taken","skipped"):
            return jsonify({"ok":False,"error":"invalid_reminder_status"}),400
        owned={p["id"]:p for p in medication_push.list_plans(_data_user_id(),active_only=False)}
        if plan_id not in owned: return jsonify({"ok":False,"error":"forbidden"}),403
        db.log_med_status(_data_user_id(),int(data.get("member_id") or owned[plan_id].get("member_id") or 0),plan_id,log_date,log_time,status)
        return jsonify({"ok":True})
    except Exception as exc: return _mk_error(exc)


@app.route("/api/meds/snooze", methods=["POST"])
@api_login_required
def api_meds_snooze():
    if not _service_consent_ok(): return _consent_required_json("/meds")
    try:
        data=request.get_json(silent=True) or {}; mins=medication_push.schedule_snooze(_data_user_id(),int(data.get("plan_id") or 0),int(data.get("member_id") or 0),str(data.get("date") or datetime.now(timezone.utc).date().isoformat()),str(data.get("time") or ""),data.get("minutes"))
        return jsonify({"ok":True,"minutes":mins})
    except PermissionError as exc: return jsonify({"ok":False,"error":str(exc)}),403
    except Exception as exc: return _mk_error(exc)


@app.route("/api/meds/weekly", methods=["GET"])
@api_login_required
def api_meds_weekly():
    try:
        member_id=request.args.get("member"); return jsonify({"ok":True,**medication_push.weekly_summary(_data_user_id(),int(member_id) if member_id else None)})
    except Exception as exc: return _mk_error(exc)


@app.route("/api/meds/calendar", methods=["GET"])
@api_login_required
def api_meds_calendar():
    try:
        member_id=request.args.get("member"); days=max(1,min(90,int(request.args.get("days") or 30)))
        return jsonify({"ok":True,**medication_push.reminder_calendar(_data_user_id(),int(member_id) if member_id else None,days)})
    except Exception as exc: return _mk_error(exc)


@app.route("/api/meds/settings", methods=["GET", "PUT"])
@api_login_required
def api_meds_settings():
    try:
        if request.method=="GET": return jsonify({"ok":True,"settings":medication_push.get_settings(_data_user_id())})
        if not _service_consent_ok(): return _consent_required_json("/meds")
        return jsonify({"ok":True,"settings":medication_push.save_settings(_data_user_id(),request.get_json(silent=True) or {})})
    except Exception as exc: return _mk_error(exc)


@app.route("/api/push/vapid-public", methods=["GET"])
def api_push_vapid_public():
    cfg=medication_push.push_config()
    return jsonify({"ok":True,"configured":cfg.get("configured",False),"public_key":cfg.get("public_key","")})


@app.route("/api/push/status", methods=["GET"])
@api_login_required
def api_push_status():
    return jsonify({"ok":True,**medication_push.subscription_status(_data_user_id())})


@app.route("/api/push/subscribe", methods=["POST"])
@api_login_required
def api_push_subscribe():
    if not _service_consent_ok(): return _consent_required_json("/meds")
    try:
        data=request.get_json(silent=True) or {}; sub=data.get("subscription") or {}
        medication_push.subscribe(_data_user_id(),sub,data.get("timezone") or "Asia/Riyadh",data.get("lang") or _lang())
        return jsonify({"ok":True})
    except Exception as exc: return _mk_error(exc)


@app.route("/api/push/unsubscribe", methods=["POST", "DELETE"])
@api_login_required
def api_push_unsubscribe():
    try:
        data=request.get_json(silent=True) or {}; medication_push.unsubscribe(_data_user_id(),data.get("endpoint")); return jsonify({"ok":True})
    except Exception as exc: return _mk_error(exc)


@app.route("/api/push/action", methods=["POST"])
def api_push_action():
    try:
        data=request.get_json(silent=True) or {}; result=medication_push.handle_push_action(str(data.get("token") or ""),str(data.get("action") or "")); return jsonify({"ok":True,**result})
    except PermissionError as exc: return jsonify({"ok":False,"error":str(exc)}),403
    except Exception as exc: return _mk_error(exc)


@app.route("/api/admin/push/test", methods=["POST"])
@admin_api_required("access")
def api_admin_push_test():
    try:
        data=request.get_json(silent=True) or {}; result=medication_push.send_test_to_user(_data_user_id(),_lang(),data.get("endpoint"))
        platform_v2.audit(int(_ss_user_id()),"sent_test_notification","push","current_admin_device",None,{"success":bool(result.get("ok"))})
        return jsonify(result), (200 if result.get("ok") else 400)
    except Exception as exc: return _mk_error(exc)


@app.route("/api/timeline", methods=["GET"])
@api_login_required
def api_timeline():
    try:
        db.init_db()
        member_id = int(request.args.get("member") or 0)
        days = int(request.args.get("days") or 30)
        events = db.member_timeline(_data_user_id(), member_id, days)
        return jsonify({"ok": True, "events": events})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"})


@app.route("/api/analyze/differential-question", methods=["POST"])
def api_analyze_differential_question():
    try:
        if not _service_consent_ok():
            return _consent_required_json("/chat")
        data = request.get_json(silent=True) or {}
        lang = "en" if data.get("lang") == "en" else "ar"
        symptoms = data.get("symptoms") or []
        if isinstance(symptoms, str):
            symptoms = [symptoms]
        asked = data.get("asked") or []
        negatives = data.get("negatives") or []
        result = medical_knowledge.differential_question(
            [str(x).strip() for x in symptoms if str(x).strip()][:30],
            asked=[str(x) for x in asked][:20],
            negatives=[str(x) for x in negatives][:20],
            lang=lang,
        )
        result["ok"] = True
        return jsonify(result)
    except Exception as exc:
        return jsonify({"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:160]}"}), 400


@app.route("/api/analyze/data-quality", methods=["POST"])
def api_analyze_data_quality():
    try:
        if not _service_consent_ok():
            return _consent_required_json("/chat")
        data=request.get_json(silent=True) or {}
        lang="en" if data.get("lang")=="en" else "ar"
        symptoms=data.get("symptoms") or []
        if isinstance(symptoms,str): symptoms=[symptoms]
        patient={
            "age":data.get("age"),"gender":data.get("gender"),"symptoms":[str(x).strip() for x in symptoms if str(x).strip()][:20],
            "duration":data.get("duration"),"severity":data.get("severity"),"conditions":str(data.get("conditions") or "")[:1000],
            "medications":str(data.get("medications") or "")[:1000],"allergies":str(data.get("allergies") or "")[:1000],
            "notes":str(data.get("notes") or "")[:2000],"location":str(data.get("location") or "")[:200],
            "history_answered":bool(data.get("history_answered")),
        }
        return jsonify({"ok":True,"data_quality":analysis_core.assess_data_quality(patient,lang)})
    except Exception as exc:
        return jsonify({"ok":False,"error":f"{type(exc).__name__}: {str(exc)[:160]}"}),400


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    try:
        db.init_db(); privacy_features.init_schema()
        consent = privacy_features.get_consent(_consent_subject_key(), _ss_user_id())
        if not consent.get("service_usage") or consent.get("needs_review"):
            lang0 = _lang()
            return jsonify({"ok": False, "error": "يلزم اختيار تفضيلات الخصوصية قبل تحليل الأعراض." if lang0 == "ar" else "Please choose your privacy preferences before symptom analysis.", "consent_required": True, "consent_url": "/consent?next=/chat"}), 403
        data = request.get_json(silent=True) or {}
        lang = "en" if data.get("lang") == "en" else "ar"
        symptoms = data.get("symptoms") or []
        if isinstance(symptoms, str):
            symptoms = [symptoms]
        symptoms = [str(s).strip() for s in symptoms if str(s).strip()][:20]
        if not symptoms:
            msg = "يرجى اختيار عرض واحد على الأقل قبل بدء التحليل." if lang == "ar" else "Please select at least one symptom before starting the assessment."
            return jsonify({"ok": False, "error": msg}), 400
        try:
            member_id = int(data.get("member_id") or 0)
        except (TypeError, ValueError):
            member_id = 0
        raw_severity = data.get("severity")
        try:
            severity = max(1, min(5, int(raw_severity))) if raw_severity not in (None, "") else None
        except (TypeError, ValueError):
            severity = None
        use_saved = data.get("use_saved", False)
        member = None
        if member_id:
            try:
                member = db.get_member(_data_user_id(), int(member_id))
            except Exception:
                member = None
        patient = {
            "user_id": _data_user_id(),
            "age": data.get("age"),
            "gender": data.get("gender"),
            "symptoms": symptoms,
            "duration": data.get("duration"),
            "severity": severity,
            "conditions": data.get("conditions", ""),
            "medications": data.get("medications", ""),
            "allergies": data.get("allergies", ""),
            "notes": str(data.get("notes") or "")[:2000],
            "location": str(data.get("location") or "")[:200],
            "history_answered": bool(data.get("history_answered")),
            "member_id": member_id,
        }
        if member:
            patient["member_name"] = member.get("name", "")
        blood_id = data.get("blood_id")
        if blood_id:
            try:
                bt = db.get_blood_test(_data_user_id(), blood_id)
                if bt and bt.get("data"):
                    patient["blood"] = bt["data"]
            except Exception:
                pass
        # Smart context: use saved health profile if requested and permitted
        if use_saved and not member:
            uid = _ss_user_id()
            if uid:
                privacy = db.load_privacy_settings(uid)
                if privacy.get("use_in_analysis", True):
                    hp = db.load_health_profile(uid)
                    if hp:
                        if not patient["age"] and hp.get("dob"):
                            try:
                                from datetime import date
                                dob = hp["dob"]
                                born = date.fromisoformat(dob)
                                today = date.today()
                                patient["age"] = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
                            except Exception:
                                pass
                        if not patient["gender"] and hp.get("gender"):
                            patient["gender"] = hp["gender"]
                        if not patient["conditions"] and hp.get("health_conditions"):
                            patient["conditions"] = hp["health_conditions"]
                        if not patient["medications"] and hp.get("medications"):
                            patient["medications"] = hp["medications"]
                        if not patient["allergies"] and hp.get("allergies"):
                            patient["allergies"] = hp["allergies"]
        # Fallback to legacy profile if still missing
        if not patient["conditions"] or not patient["medications"] or not patient["age"]:
            try:
                if member:
                    if not patient["age"]:
                        patient["age"] = member.get("age") or None
                    if not patient["gender"]:
                        patient["gender"] = member.get("gender") or None
                    if not patient["conditions"]:
                        patient["conditions"] = member.get("conditions") or ""
                    if not patient["medications"]:
                        patient["medications"] = member.get("medications") or ""
                    if not patient["allergies"]:
                        patient["allergies"] = member.get("allergies") or ""
                else:
                    p = db.load_profile(_data_user_id())
                    if p:
                        if not patient["age"]:
                            patient["age"] = p.get("age") or None
                        if not patient["gender"]:
                            patient["gender"] = p.get("gender") or None
                        if not patient["conditions"]:
                            patient["conditions"] = p.get("conditions") or ""
                        if not patient["medications"]:
                            patient["medications"] = p.get("medications") or ""
                        if not patient["allergies"]:
                            patient["allergies"] = p.get("allergies") or ""
            except Exception:
                pass
        result = analysis_core.run_analysis(patient, lang=lang)
        if result.get("record_id"):
            try:
                privacy_features.set_record_analytics_eligibility(int(result["record_id"]), _analytics_consent_ok())
            except Exception:
                pass
        previous_record_id = data.get("previous_record_id")
        if previous_record_id and result.get("record_id"):
            try:
                advanced_features.link_reanalysis(_data_user_id(), int(previous_record_id), int(result.get("record_id")))
            except Exception:
                pass
        # Save chat history if user is logged in and privacy allows
        uid = _ss_user_id()
        if uid:
            privacy = db.load_privacy_settings(uid)
            if privacy.get("save_chat_history", True):
                try:
                    symptoms_text = ", ".join(patient.get("symptoms", []))
                    db.save_chat_message(uid, "user", symptoms_text)
                    if result.get("possible_conditions"):
                        db.save_chat_message(uid, "assistant", str(result.get("possible_conditions", ""))[:500])
                except Exception:
                    pass
        try:
            flags = analysis_core.detect_red_flags(patient["symptoms"], patient["notes"], lang)
            if flags:
                result["emergency"] = True
                if member and member.get("name"):
                    pfx = ("لدى " + member["name"] + ": ") if lang == "ar" else ("For " + member["name"] + ": ")
                    flags = [pfx + f for f in flags]
                result["emergency_flags"] = flags
                if member and member.get("name"):
                    result["emergency_person"] = member["name"]
                platform_v2.record_usage("safety_alert", "/api/analyze", lang, request.headers.get("User-Agent", ""), 200, service="symptom_analysis")
        except Exception:
            pass
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"})


@app.route("/api/profile", methods=["POST"])
def api_profile():
    if not _service_consent_ok():
        return _consent_required_json("/manage")
    try:
        db.init_db()
        data = request.get_json(force=True)
        db.save_profile(
            _data_user_id(),
            "en" if data.get("lang") == "en" else "ar",
            str(data.get("age") or "").strip(),
            str(data.get("gender") or "").strip(),
            str(data.get("conditions") or "").strip(),
            str(data.get("medications") or "").strip(),
            str(data.get("allergies") or "").strip(),
        )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"})


@app.route("/api/handoff/candidates", methods=["GET"])
def api_handoff_candidates():
    try:
        rows=advanced_features.user_analysis_rows(_data_user_id(),limit=12)
        out=[{"id":r.get("id"),"timestamp":r.get("timestamp"),"symptoms":r.get("symptoms") or [],"risk_level":(r.get("result") or {}).get("risk_level") or r.get("urgency")} for r in rows]
        return jsonify({"ok":True,"analyses":out})
    except Exception as e:
        return jsonify({"ok":False,"error":str(e)[:160]}),500


@app.route("/api/handoff/create", methods=["POST"])
def api_handoff_create():
    try:
        data=request.get_json(silent=True) or {}
        result=privacy_features.create_handoff(_data_user_id(),int(data.get("record_id") or 0),data.get("selected") or {},data.get("previous_ids") or [],int(data.get("expires_minutes") or 60))
        payload_lang = "en" if (result.get("payload") or {}).get("lang") == "en" else "ar"
        # Build the QR from the dedicated PUBLIC HTML route only.  Using the
        # canonical public host avoids reverse-proxy/API-path leakage on Railway,
        # and the language query lets a recipient open it without an existing
        # SymptoSense language cookie.
        share_path = url_for("public_health_handoff", token=result["token"], lang=payload_lang)
        share_url = _site_url().rstrip("/") + share_path
        return jsonify({"ok":True,"token":result["token"],"share_url":share_url,"expires_at":result["expires_at"],"qr_data_uri":privacy_features.qr_png_data_uri(share_url)})
    except PermissionError as e:
        return jsonify({"ok":False,"error":str(e)}),403
    except Exception as e:
        return jsonify({"ok":False,"error":str(e)[:160]}),400


@app.route("/api/handoff/revoke", methods=["POST"])
def api_handoff_revoke():
    try:
        data=request.get_json(silent=True) or {}
        ok=privacy_features.revoke_handoff(_data_user_id(),str(data.get("token") or ""))
        return jsonify({"ok":bool(ok)}) if ok else (jsonify({"ok":False,"error":"not_found_or_not_owned"}),404)
    except Exception as e:
        return jsonify({"ok":False,"error":str(e)[:160]}),400


@app.route("/share/health/<token>")
def public_health_handoff(token):
    item=privacy_features.get_handoff(token); ar=_lang()=="ar"
    if not item or item.get("status") in ("expired","revoked"):
        msg=("هذا الرابط لم يعد متاحًا." if item and item.get("status")=="revoked" else "انتهت صلاحية رابط الملخص الصحي أو أنه غير صالح.") if ar else ("This link is no longer available." if item and item.get("status")=="revoked" else "This health summary link has expired or is invalid.")
        return _page("Health Summary",'<main class="v2-info-page"><section style="text-align:center"><h1>🔒 Health Summary</h1><p>%s</p></section></main>'%msg),410
    payload=item.get("payload") or {}; sec=payload.get("sections") or {}; lang="en" if payload.get("lang")=="en" else "ar"; ar=lang=="ar"
    labels={"symptoms":"الأعراض المبلغ عنها" if ar else "Reported Symptoms","duration":"المدة" if ar else "Duration","severity":"الشدة" if ar else "Severity","location":"المكان" if ar else "Location","notes":"معلومات إضافية" if ar else "Additional Information","medications":"معلومات الأدوية التي اختار المستخدم مشاركتها" if ar else "Medication information selected by the user","previous_assessments":"تقييمات سابقة مختارة" if ar else "Selected Previous Assessments"}
    blocks=[]
    for key in ("symptoms","duration","severity","location","notes","medications"):
        val=sec.get(key)
        if val not in (None,"",[]):
            if isinstance(val,list): val="، ".join(map(str,val)) if ar else ", ".join(map(str,val))
            blocks.append('<section><h2>%s</h2><p>%s</p></section>'%(labels[key],str(val).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')))
    prev=sec.get("previous_assessments") or []
    if prev:
        lis=''.join('<li>%s — %s — %s</li>'%(("، ".join(x.get("symptoms") or []) if ar else ", ".join(x.get("symptoms") or [])),x.get("duration") or "—",x.get("risk_level") or "—") for x in prev)
        blocks.append('<section><h2>%s</h2><ul>%s</ul></section>'%(labels["previous_assessments"],lis))
    if not blocks:
        empty_msg = "لا توجد معلومات متاحة ضمن الحقول التي اختارها المستخدم لهذا الرابط. أنشئ رابط مشاركة جديدًا واختر معلومات موجودة في التحليل." if ar else "No information is available in the fields selected for this link. Create a new share link and choose information that exists in the analysis."
        blocks.append('<section><p class="v2-safe-note">%s</p></section>' % empty_msg)
    disc="يحتوي هذا الملخص على معلومات أبلغ عنها المستخدم ويهدف للمساعدة في توصيل المعلومات إلى مختص صحي. لا يحل محل التقييم الطبي المتخصص." if ar else "This summary contains user-reported information and is intended to help communicate information to a healthcare professional. It does not replace professional medical evaluation."
    body='<main class="v2-info-page"><section><h1>🗣️ SymptoSense Health Summary</h1><p class="muted">%s</p></section>%s<section><p class="v2-disclaimer">%s</p></section></main>'%(payload.get("created_at") or "",''.join(blocks),disc)
    return _page("SymptoSense Health Summary",body)


def _pdf_report(result, lang="ar"):
    """Create the symptom-analysis PDF from the already-saved analysis result.

    Uses PyMuPDF Story so Arabic shaping/RTL work without relying on a bundled
    application font. No medical values are recalculated here: this function
    only formats the data already stored for the analysis.
    """
    import html as _html
    try:
        import fitz
    except Exception as exc:
        raise RuntimeError("PDF renderer is unavailable") from exc

    ar = lang != "en"

    def esc(value):
        return _html.escape(str(value if value not in (None, "") else "—"))

    def as_lines(value):
        if value in (None, "", []):
            return []
        if isinstance(value, (tuple, list)):
            out = []
            for item in value:
                if isinstance(item, dict):
                    text = item.get("tip") or item.get("text") or item.get("message") or item.get("name") or item.get("title") or ""
                    if text:
                        out.append(str(text))
                elif item not in (None, ""):
                    out.append(str(item))
            return out
        text = str(value).replace("\r", "\n")
        parts = []
        for line in text.split("\n"):
            line = re.sub(r"^\s*[-•*]+\s*", "", line).strip()
            if line:
                parts.append(line)
        return parts or [text.strip()]

    def data_quality_text():
        dq = result.get("data_quality")
        if isinstance(dq, dict):
            val = dq.get("percentage")
            if val is None:
                val = dq.get("percent")
            if val is None:
                val = dq.get("score")
            label = dq.get("label_ar" if ar else "label_en") or dq.get("label") or ""
            if val is not None:
                try:
                    val = round(float(val))
                    return (f"{val}% - {label}" if label else f"{val}%")
                except Exception:
                    pass
        if isinstance(dq, (int, float)):
            return f"{round(float(dq))}%"
        return "—"

    risk = str(result.get("urgency") or result.get("risk_level") or "low").lower()
    risk_labels = ({
        "low": "خطورة منخفضة", "monitor": "خطورة منخفضة", "medium": "يحتاج مراجعة طبية",
        "review": "يحتاج مراجعة طبية", "high": "طوارئ", "urgent": "طوارئ", "emergency": "طوارئ",
    } if ar else {
        "low": "Low risk", "monitor": "Low risk", "medium": "Needs medical review",
        "review": "Needs medical review", "high": "Emergency", "urgent": "Emergency", "emergency": "Emergency",
    })
    risk_label = result.get("risk_label") or risk_labels.get(risk) or ("تقييم صحي" if ar else "Health assessment")

    symptoms = result.get("symptoms") or []
    if not isinstance(symptoms, list):
        symptoms = as_lines(symptoms)
    symptom_text = ("، ".join(map(str, symptoms)) if ar else ", ".join(map(str, symptoms))) or "—"
    gender_raw = str(result.get("gender") or "").strip().lower()
    if ar:
        gender = {"f":"أنثى", "female":"أنثى", "m":"ذكر", "male":"ذكر"}.get(gender_raw, result.get("gender") or "—")
    else:
        gender = {"f":"Female", "female":"Female", "m":"Male", "male":"Male"}.get(gender_raw, result.get("gender") or "—")

    conditions = result.get("knowledge_matches") or []
    condition_blocks = []
    for item in conditions:
        if not isinstance(item, dict):
            continue
        name = (item.get("name_ar") if ar else item.get("name_en")) or item.get("name") or item.get("disease_name") or ""
        if not name:
            continue
        score = item.get("score")
        if score is None:
            score = item.get("matching_score")
        if score is None:
            score = item.get("match_score")
        score_html = ""
        if score not in (None, ""):
            score_html = f'<span class="pill">{esc("التوافق" if ar else "Match")}: {esc(score)}</span>'
        reason = item.get("why") or item.get("reason") or item.get("match_reason") or ""
        condition_blocks.append(
            '<div class="condition"><div class="condition-head"><strong>%s</strong>%s</div>%s</div>' % (
                esc(name), score_html, ('<p>%s</p>' % esc(reason)) if reason else ''
            )
        )
    if not condition_blocks:
        raw_pc = result.get("possible_conditions") or ""
        if raw_pc:
            condition_blocks.append('<div class="condition"><p>%s</p></div>' % esc(raw_pc))

    recommendations = result.get("recommendations") or []
    rec_lines = as_lines(recommendations)
    danger_lines = as_lines(result.get("danger_signs"))
    home_lines = as_lines(result.get("home_care"))
    seek_lines = as_lines(result.get("when_to_seek_care"))
    doctor_lines = as_lines(result.get("questions_for_doctor"))

    source_cards = []
    for src in (result.get("medical_sources") or []):
        if not isinstance(src, dict):
            continue
        name = src.get("source_name") or src.get("organization") or src.get("name") or ("مصدر طبي" if ar else "Medical source")
        title = (src.get("reference_title_ar") if ar else src.get("reference_title_en")) or src.get("reference_title_en") or src.get("reference_title_ar") or ""
        source_cards.append('<div class="source"><strong>%s</strong>%s</div>' % (esc(name), ('<small>%s</small>' % esc(title)) if title else ''))

    labels = ({
        "title":"تقرير تحليل الأعراض", "subtitle":"SymptoSense - ملخص صحي توعوي",
        "summary":"نتيجة التحليل", "risk":"مستوى الخطورة", "quality":"جودة المعلومات المدخلة",
        "entered":"المعلومات المدخلة", "symptoms":"الأعراض", "duration":"المدة", "severity":"شدة الأعراض",
        "age":"العمر", "gender":"الجنس", "conditions":"الاحتمالات المحتملة", "now":"ماذا أفعل الآن؟",
        "warnings":"علامات تستدعي الانتباه", "home":"الرعاية المنزلية", "doctor":"أسئلة للطبيب",
        "sources":"المصادر الطبية", "none":"لم يتم تحديد معلومات إضافية ضمن هذا القسم.",
        "disclaimer":"هذه النتيجة توعوية ولا تُعد تشخيصًا طبيًا نهائيًا ولا تغني عن استشارة الطبيب عند الحاجة.",
        "generated":"تاريخ إنشاء التقرير",
    } if ar else {
        "title":"Symptom Analysis Report", "subtitle":"SymptoSense - Educational health summary",
        "summary":"Analysis result", "risk":"Risk level", "quality":"Information completeness",
        "entered":"Information entered", "symptoms":"Symptoms", "duration":"Duration", "severity":"Symptom severity",
        "age":"Age", "gender":"Gender", "conditions":"Possible conditions", "now":"What should I do now?",
        "warnings":"Warning signs", "home":"Home care", "doctor":"Questions for your clinician",
        "sources":"Medical sources", "none":"No additional information was provided for this section.",
        "disclaimer":"This result is educational, is not a final medical diagnosis, and does not replace professional medical advice when needed.",
        "generated":"Report generated",
    })

    def list_html(lines, empty=False):
        if not lines:
            return ('<p class="muted">%s</p>' % esc(labels["none"])) if empty else ""
        return '<ul>%s</ul>' % ''.join('<li>%s</li>' % esc(x) for x in lines)

    direction = "rtl" if ar else "ltr"
    align = "right" if ar else "left"
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html_doc = f"""<!doctype html>
<html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box}} body{{font-family:sans-serif;color:#23384A;font-size:10.5pt;line-height:1.55;direction:{direction};text-align:{align};}}
h1{{font-size:22pt;color:#163B5C;margin:0 0 4px}} h2{{font-size:14pt;color:#163B5C;margin:0 0 10px}} p{{margin:4px 0 8px}}
.header{{border-bottom:2px solid #DCE8F0;padding-bottom:14px;margin-bottom:16px}} .muted{{color:#607487}} .card{{border:1px solid #DCE8F0;border-radius:12px;padding:14px;margin:0 0 12px;background:#FFFFFF}}
.summary{{background:#F3F9FD}} .risk{{font-size:16pt;font-weight:700;color:#163B5C}} .pill{{display:inline-block;border:1px solid #DCE8F0;border-radius:999px;padding:2px 8px;font-size:8.5pt;color:#607487}}
.grid{{display:flex;flex-wrap:wrap;gap:8px}} .field{{width:48%;border:1px solid #E4EDF3;border-radius:9px;padding:8px}} .field b{{display:block;color:#607487;font-size:8.5pt;margin-bottom:2px}}
.condition,.source{{border:1px solid #E4EDF3;border-radius:9px;padding:10px;margin:7px 0}} .condition-head{{display:flex;justify-content:space-between;gap:8px;align-items:center}} .source small{{display:block;color:#607487;margin-top:3px}}
ul{{margin:4px 0 0;padding-{'right' if ar else 'left'}:20px}} li{{margin:3px 0}} .disclaimer{{border:1px solid #EFDAA7;background:#FFF8E7;border-radius:10px;padding:10px;color:#6F531B;margin-top:15px}}
</style></head><body>
<div class="header"><h1>{esc(labels['title'])}</h1><p class="muted">{esc(labels['subtitle'])}</p><p class="muted">{esc(labels['generated'])}: {esc(generated)}</p></div>
<div class="card summary"><h2>{esc(labels['summary'])}</h2><div class="risk">{esc(labels['risk'])}: {esc(risk_label)}</div><p><b>{esc(labels['quality'])}:</b> {esc(data_quality_text())}</p></div>
<div class="card"><h2>{esc(labels['entered'])}</h2><div class="grid">
<div class="field"><b>{esc(labels['symptoms'])}</b>{esc(symptom_text)}</div>
<div class="field"><b>{esc(labels['duration'])}</b>{esc(result.get('duration'))}</div>
<div class="field"><b>{esc(labels['severity'])}</b>{esc(result.get('severity'))}</div>
<div class="field"><b>{esc(labels['age'])}</b>{esc(result.get('age'))}</div>
<div class="field"><b>{esc(labels['gender'])}</b>{esc(gender)}</div>
</div></div>
<div class="card"><h2>{esc(labels['conditions'])}</h2>{''.join(condition_blocks) or '<p class="muted">'+esc(labels['none'])+'</p>'}</div>
<div class="card"><h2>{esc(labels['now'])}</h2>{list_html(rec_lines + seek_lines, True)}</div>
<div class="card"><h2>{esc(labels['warnings'])}</h2>{list_html(danger_lines, True)}</div>
{('<div class="card"><h2>'+esc(labels['home'])+'</h2>'+list_html(home_lines)+'</div>') if home_lines else ''}
{('<div class="card"><h2>'+esc(labels['doctor'])+'</h2>'+list_html(doctor_lines)+'</div>') if doctor_lines else ''}
{('<div class="card"><h2>'+esc(labels['sources'])+'</h2>'+''.join(source_cards)+'</div>') if source_cards else ''}
<div class="disclaimer">{esc(labels['disclaimer'])}</div>
</body></html>"""

    buf = io.BytesIO()
    writer = fitz.DocumentWriter(buf)
    page = fitz.paper_rect("a4")
    story = fitz.Story(html=html_doc)
    more = True
    page_count = 0
    try:
        while more:
            page_count += 1
            if page_count > 40:
                raise RuntimeError("PDF exceeded safe page limit")
            device = writer.begin_page(page)
            more, _ = story.place(fitz.Rect(42, 42, page.width - 42, page.height - 42))
            story.draw(device)
            writer.end_page()
    finally:
        writer.close()
    buf.seek(0)
    if not buf.getvalue().startswith(b"%PDF"):
        raise RuntimeError("Invalid PDF output")
    return buf


@app.route("/api/analyze/export/<int:record_id>")
def api_export_pdf(record_id):
    db.init_db()
    result = db.load_result(_data_user_id(), record_id)
    if not result:
        lang = _lang()
        t = L["en" if lang == "en" else "ar"]
        body = ('<div class="card" style="max-width:520px;margin:40px auto;text-align:center;">'
                '<h2>%s</h2><p style="margin-top:10px;"><a class="btn" href="/history">%s</a></p></div>'
                % (t["pdf_nf"], t["hs_dl"]))
        return _page(_t("title_history"), body)
    lang = "en" if result.get("lang") == "en" else "ar"
    buf = _pdf_report(result, lang)
    try:
        platform_v2.record_usage("report_generated", "/api/analyze/export", lang, request.headers.get("User-Agent", ""), 200, None)
        admin_operational.record_journey(_analytics_session_id(), "report", request.headers.get("User-Agent", ""))
    except Exception:
        pass
    fname = "symptosense-report-%s.pdf" % record_id
    return send_file(
        buf, mimetype="application/pdf",
        as_attachment=True, download_name=fname,
    )


@app.route("/api/followup", methods=["POST"])
def api_followup():
    if not _service_consent_ok():
        return _consent_required_json("/chat")
    try:
        data = request.get_json(force=True)
        question = (data.get("question") or "").strip()
        ctx = data.get("context") or {}
        lang = "en" if ctx.get("lang") == "en" else "ar"
        if not question:
            return jsonify({"ok": False, "error": "السؤال فارغ" if lang == "ar" else "Empty question"})
        if lang == "en":
            prompt = (
                "You are SymptoSense, a friendly health awareness assistant. Answer in clear, warm English.\n"
                "These are the user's previous analysis summaries:\n"
                f"Symptoms: {ctx.get('symptoms')}\n"
                f"Result: {ctx.get('possible_conditions')}\n"
                f"Urgency: {ctx.get('urgency')}\n"
                f"Recommendations: {ctx.get('recommendations')}\n\n"
                f"The user now asks: {question}\n\n"
                "Answer briefly (150 words max) and remind that this is awareness information, not a final diagnosis."
            )
        else:
            prompt = (
                "أنت SymptoSense، مساعد صحي توعوي. أجب بالعربية بأسلوب سعودي واضح وودود.\n"
                "هذه ملخصات تحليل سابق للمستخدم:\n"
                f"الأعراض: {ctx.get('symptoms')}\n"
                f"النتيجة: {ctx.get('possible_conditions')}\n"
                f"الخطورة: {ctx.get('urgency')}\n"
                f"التوصيات: {ctx.get('recommendations')}\n\n"
                f"سؤال المستخدم الآن: {question}\n\n"
                "أجب بإيجاز (150 كلمة كحد أقصى) وذكّر أن هذه معلومات توعوية وليست تشخيصاً نهائياً."
            )
        client = analysis_core._groq_client()
        r = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=500,
            timeout=45,
        )
        answer = r.choices[0].message.content.strip()
        return jsonify({"ok": True, "answer": answer})
    except Exception as e:
        err = str(e)
        if "GROQ_API_KEY" in err or not err:
            fallback = ("أهلاً! لا أستطيع الرد الكامل حالياً، لكن المعلومات العامة تشير إلى ضرورة مراجعة الطبيب عند استمرار الأعراض أو ازديادها سوءاً. هذه إجابة توعوية وليست تشخيصاً نهائياً."
                        if lang != "en" else
                        "Hi! I can't give a full reply right now, but in general you should see a doctor if symptoms persist or worsen. This is awareness information, not a final diagnosis.")
            return jsonify({"ok": True, "answer": fallback})
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {err[:200]}"})


def _assistant_services(text, lang):
    low = text.lower()
    if lang == "en":
        if any(k in low for k in ("blood", "cbc", "hemoglobin", "lab", "test result")):
            return [{"label": "Blood test analysis", "url": "/blood"}]
        if any(k in low for k in ("calculator", "bmi", "body mass", "calorie", "fluid", "water intake", "dose interval", "blood sugar level", "sugar level")):
            return [{"label": "Health Calculators", "url": "/calculators"}]
        if any(k in low for k in ("what is", "what's", "meaning", "means", "explain", "what does")):
            return [{"label": "Health search", "url": "/search"}]
        if any(k in low for k in ("symptom", "pain", "cough", "fever", "headache", "feel", "aching")):
            return [{"label": "Symptom check", "url": "/chat"}]
        if any(k in low for k in ("family", "mom", "mother", "dad", "father", "child", "kids")):
            return [{"label": "Family Health Hub", "url": "/family"}]
        if any(k in low for k in ("medication", "drug", "medicine", "pill", "dose")):
            return [{"label": "Medications page", "url": "/meds"}]
        if any(k in low for k in ("hospital", "clinic", "doctor", "emergency")):
            return [{"label": "Nearest hospital", "url": "/emergency#geo"}]
    else:
        if any(k in text for k in ("دم", "فحص", "cbc", "هيموجلوبين", "التحليل")):
            return [{"label": "تحليل فحص الدم", "url": "/blood"}]
        if any(k in text for k in ("حاسبة", "مؤشر كتلة", "كتلة الجسم", "bmi", "سعرات", "احتياج السوائل", "شرب الماء", "فاصل الجرعات", "مواعيد الدواء", "قراءة السكر")):
            return [{"label": "الحاسبات الصحية", "url": "/calculators"}]
        if any(k in text for k in ("معنى", "ما هو", "ما هي", "اشرح", "تفسير", "وش يعني", "يعني ايش")):
            return [{"label": "البحث الصحي", "url": "/search"}]
        if any(k in text for k in ("ألم", "أعراض", "سعال", "حرارة", "صداع", "أشعر", "مرض")):
            return [{"label": "فحص الأعراض", "url": "/chat"}]
        if any(k in text for k in ("عائلة", "أمي", "أبي", "أم ", "ابني", "ابنتي", "الطفل", "فرد")):
            return [{"label": "مركز صحة العائلة", "url": "/family"}]
        if any(k in text for k in ("دواء", "أدوية", "حبة", "جرعة")):
            return [{"label": "صفحة الأدوية", "url": "/meds"}]
        if any(k in text for k in ("مستشفى", "عيادة", "طبيب", "طوارئ")):
            return [{"label": "أقرب مستشفى", "url": "/emergency#geo"}]
    return []


@app.route("/api/assistant", methods=["POST"])
def api_assistant():
    lang = "ar"
    services = []
    if not _service_consent_ok():
        return _consent_required_json("/assistant")
    try:
        data = request.get_json(force=True)
        lang = "en" if data.get("lang") == "en" else "ar"
        mode = data.get("mode") or ""
        messages = [m for m in (data.get("messages") or []) if m.get("content")]
        last_text = messages[-1]["content"][:600] if messages else ""
        flags = analysis_core.detect_red_flags([], last_text, lang)
        services = [] if mode == "mh" else _assistant_services(last_text, lang)
        if flags:
            if lang == "en":
                answer = ("I'm concerned about what you described — it can be an emergency sign ("
                          + ", ".join(flags) + "). Please call emergency services right away (997 in Saudi Arabia) or go to the nearest ER. Do not wait for a reply here.")
            else:
                answer = ("أقلقني ما وصفته — قد يكون علامة طارئة (" + "، ".join(flags) +
                          "). يرجى الاتصال بالإسعاف فوراً 997 أو التوجه لأقرب طوارئ. لا تنتظر الرد هنا.")
            return jsonify({"ok": True, "answer": answer, "emergency_flags": flags, "services": services})
        kb_bundle = None
        assistant_sources = []
        if mode != "mh" and last_text:
            try:
                kb_bundle = medical_knowledge.knowledge_bundle([last_text], severity=1, notes=last_text, lang=lang)
                assistant_sources = kb_bundle.get("sources", [])[:5]
            except Exception:
                kb_bundle = None
        hist = []
        for m in messages[-6:]:
            role = "user" if m.get("role") == "user" else "assistant"
            hist.append({"role": role, "content": str(m.get("content") or "")[:600]})
        if mode == "mh":
            if lang == "en":
                sys = (
                    "You are the calm mental-wellbeing space inside SymptoSense. Answer in warm, gentle, short English "
                    "(90 words max), using caring language. Never diagnose, judge, or push solutions. Your role is to listen, "
                    "validate, reassure, and suggest simple steps (slow breathing, resting, talking to someone close, or seeing a professional). "
                    "If the user expresses thoughts of self-harm or suicide: respond immediately with firm kindness that they should "
                    "contact the mental health support line 937 or emergency services 997 right now — never minimize it. "
                    "Remind them you are not a replacement for a specialist."
                )
            else:
                sys = (
                    "أنت مساحة هادئة للصحة النفسية داخل موقع SymptoSense. تحدث بالعربية بأسلوب سعودي ودود ودافئ، بجمل قصيرة ولطيفة (90 كلمة كحد أقصى). "
                    "لا تشخّص ولا تحكم ولا تحاول حل المشكلة بقوة؛ مهمتك أن تسمع وتطمئن وتقترح خطوات بسيطة (تنفس عميق، أخذ قسط، التحدث مع شخص قريب، مراجعة مختص). "
                    "إذا عبر المستخدم عن أفكار إيذاء النفس أو الانتحار: استجب فورًا وبحزم وحنان بأنه يجب التواصل مع خط مساندة الصحة النفسية 937 أو الطوارئ 997 الآن، "
                    "ولا تقلل من الأمر أبدًا. ذكّر أنه لا يستبدل المختص."
                )
        elif lang == "en":
            sys = (
                "You are SymptoSense's in-site assistant. Answer briefly in warm English (120 words max). "
                "You help navigate the site: /chat symptom analysis, /blood CBC upload, /meds medication info & reminders, "
                "/family Family Health Hub with per-person records, /search smart health search, /calculators health calculators (BMI, fluids, calories, blood sugar), "
                "/emergency emergency numbers & nearest hospitals, "
                "/checkin daily tracking. If the user describes severe symptoms (chest pain, breathing trouble, bleeding, confusion, fainting), "
                "urge them to call emergency services (997) immediately. Always add that this is awareness information, not a final diagnosis."
            )
        else:
            sys = (
                "أنت المساعد الداخلي لموقع SymptoSense. أجب بإيجاز وبالعربية بأسلوب سعودي ودود (120 كلمة كحد أقصى). "
                "تساعد في التوجيه داخل الموقع: /chat فحص الأعراض، /blood رفع فحص الدم، /meds معلومات وتذكير الأدوية، "
                "/family مركز صحة العائلة بسجلات منفصلة لكل فرد، /search البحث الصحي الذكي، /calculators الحاسبات الصحية (BMI والسوائل والسعرات والسكر)، /emergency أرقام الطوارئ وأقرب مستشفى، /checkin المتابعة اليومية. "
                "إذا وصف المستخدم أعراضاً خطرة (ألم صدر، صعوبة تنفس، نزيف، تشوش، إغماء) حثه على الاتصال بالإسعاف 997 فوراً. "
                "وذكّر دائماً أن هذه معلومات توعوية وليست تشخيصاً نهائياً."
            )
        sys += (" Never invent diseases, symptoms, medicines, doses, percentages, sources, or links. "
                "If reliable information is unavailable, say so clearly. Do not present a definitive diagnosis."
                if lang == "en" else
                " لا تخترع أمراضًا أو أعراضًا أو أدوية أو جرعات أو نسبًا أو مصادر أو روابط. إذا لم تتوفر معلومة موثوقة فاذكر ذلك بوضوح، ولا تقدم تشخيصًا قطعيًا.")
        if kb_bundle and kb_bundle.get("matches"):
            grounded = []
            for match in kb_bundle["matches"][:3]:
                grounded.append({
                    "condition": match.get("name_en") if lang == "en" else match.get("name_ar"),
                    "match_level": match.get("match_level"),
                    "matched_symptoms": [s.get("name_en") if lang == "en" else s.get("name_ar") for s in match.get("matched_symptoms", [])],
                })
            sys += (" Use only this retrieved knowledge-base context for condition explanations: " if lang == "en" else
                    " استخدم فقط سياق قاعدة المعرفة المسترجع التالي عند شرح الحالات: ") + json.dumps(grounded, ensure_ascii=False)
        msgs = [{"role": "system", "content": sys}] + hist
        try:
            client = analysis_core._groq_client()
            r = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=msgs,
                temperature=0.5,
                max_tokens=400,
                timeout=45,
            )
            answer = r.choices[0].message.content.strip()
        except Exception:
            answer = ("أهلاً! لا أستطيع الرد الكامل الآن، لكن استخدم فحص الأعراض أو راجع الطبيب عند استمرار الأعراض. هذه إجابة توعوية وليست تشخيصاً نهائياً."
                      if lang == "ar" else
                      "Hi! I can't give a full reply right now, but use the symptom checker or see a doctor if symptoms persist. This is awareness info, not a final diagnosis.")
        return jsonify({"ok": True, "answer": answer, "emergency_flags": [], "services": services,
                        "medical_sources": assistant_sources})
    except Exception as e:
        err = str(e)
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {err[:200]}"})


@app.route("/api/assistant/feedback", methods=["POST"])
def api_assistant_feedback():
    if not _analytics_consent_ok():
        return jsonify({"ok":True,"recorded":False,"reason":"analytics_consent_disabled"})
    try:
        data = request.get_json(force=True)
        rating = int(data.get("rating") or 0)
        if rating not in (0, 1, 2):
            return jsonify({"ok": False, "error": "rating must be 0, 1 or 2"})
        message = (data.get("message") or "")[:1000]
        reason = (data.get("reason") or "").strip()[:200] or None
        db.init_db()
        db.save_assistant_feedback(_data_user_id(), message, rating, reason)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"})


def _checkin_api_payload(account_id, day):
    rows = db.get_web_daily_checkin_history(account_id, limit=180)
    today = db.get_web_daily_checkin_for_date(account_id, day)
    try:
        end_day = datetime.strptime(day, "%Y-%m-%d").date()
    except Exception:
        end_day = datetime.now(timezone.utc).date()
    start_day = end_day - timedelta(days=6)
    recent = []
    for row in rows:
        try:
            row_day = datetime.strptime(str(row.get("date") or ""), "%Y-%m-%d").date()
        except Exception:
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


@app.route("/api/checkin", methods=["GET", "POST"])
def api_checkin():
    # Daily tracking is intentionally account-bound. Guest/session identifiers
    # are not used because the history must follow the signed-in user only.
    if not _ss_user_id():
        return jsonify({
            "ok": False,
            "login_required": True,
            "error": "سجّل الدخول لحفظ ومتابعة حالتك اليومية." if _lang() == "ar" else "Sign in to save and track your daily health status.",
        }), 401

    # Daily tracking intentionally avoids the full database migration pass.
    # Production Railway databases may contain legacy tables whose unrelated
    # migrations can fail even though daily tracking only needs user_data.
    # The db.save/get_web_daily_checkin helpers ensure the minimal user_data
    # storage they need without touching legacy daily_checkins migrations.
    account_id = _ss_user_id()
    if request.method == "POST":
        if not _service_consent_ok():
            return _consent_required_json("/checkin")
        try:
            data = request.get_json(force=True) or {}
            rating = int(data.get("rating"))
            if rating < 1 or rating > 5:
                return jsonify({"ok": False, "error": "التقييم من 1 إلى 5" if _lang() == "ar" else "Rating must be from 1 to 5"}), 400
            day = str(data.get("date") or "").strip()
            try:
                datetime.strptime(day, "%Y-%m-%d")
            except Exception:
                return jsonify({"ok": False, "error": "invalid_date"}), 400
            saved = db.save_web_daily_checkin(account_id, rating, day)
            payload = _checkin_api_payload(account_id, day)
            payload.update({"created": bool(saved.get("created")), "updated": not bool(saved.get("created"))})
            return jsonify(payload)
        except Exception as e:
            request_id = getattr(g, "request_id", "")
            app.logger.exception("Daily check-in save failed; request_id=%s error_type=%s", request_id, type(e).__name__)
            return jsonify({
                "ok": False,
                "error": "تعذر حفظ تسجيل الحالة الآن." if _lang() == "ar" else "Unable to save the daily check-in right now.",
                "error_code": "checkin_save_failed",
                "request_id": request_id,
            }), 500

    try:
        day = str(request.args.get("date") or datetime.now(timezone.utc).date().isoformat()).strip()
        try:
            datetime.strptime(day, "%Y-%m-%d")
        except Exception:
            day = datetime.now(timezone.utc).date().isoformat()
        return jsonify(_checkin_api_payload(account_id, day))
    except Exception as e:
        request_id = getattr(g, "request_id", "")
        app.logger.exception("Daily check-in load failed; request_id=%s error_type=%s", request_id, type(e).__name__)
        return jsonify({
            "ok": False,
            "error": "تعذر تحميل تسجيلات الحالة الآن." if _lang() == "ar" else "Unable to load daily check-ins right now.",
            "error_code": "checkin_load_failed",
            "request_id": request_id,
        }), 500


@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    if not _analytics_consent_ok():
        return jsonify({"ok":True,"recorded":False,"reason":"analytics_consent_disabled"})
    try:
        data = request.get_json(force=True)
        rating = data.get("rating")
        comment = (data.get("comment") or "").strip()[:500]
        db.init_db()
        db.save_feedback(_data_user_id(), None, rating, comment or None)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"})


@app.route("/api/search")
def api_search():
    try:
        lang = "en" if request.args.get("lang") == "en" else "ar"
        q = (request.args.get("q") or "").strip()
        if not q:
            return jsonify({"ok": True, "result": None, "suggestions": health_search.suggestion_terms(lang)})

        result = health_search.search_health(q, lang)

        def _entity_sources(entity):
            sources = []
            for source in (entity or {}).get("sources", []):
                url = source.get("reference_url") or source.get("official_url")
                if not url:
                    continue
                sources.append({
                    "name": source.get("source_name"),
                    "organization": source.get("organization"),
                    "url": url,
                })
            return sources

        def _enrich_search_topic(topic):
            """Add trusted source metadata without replacing curated search text.

            Previously this route replaced a useful search result with a Medical
            Knowledge Base symptom object whose ``causes`` list was empty. That
            made the UI show only the symptom name. Keep the search result as the
            source of explanatory copy and use the editable KB only to enrich it.
            """
            if not topic or topic.get("category") != "symptom":
                return topic
            probe = topic.get("title") or ""
            normalized = medical_knowledge.normalize_symptoms([probe], lang)
            canonical = normalized.get("canonical") or []
            if not canonical:
                return topic
            symptom = canonical[0]
            entity = medical_knowledge.get_entity("symptom", symptom["symptom_id"], public=True)
            if not entity:
                return topic
            sources = _entity_sources(entity)
            if sources:
                topic["sources"] = sources
            # Only fill missing fields. Never erase richer curated health-search
            # content and never recalculate medical logic in this endpoint.
            if not topic.get("worry"):
                topic["worry"] = entity.get("red_flags_en") if lang == "en" else entity.get("red_flags_ar")
            if not topic.get("what"):
                topic["what"] = entity.get("description_en") if lang == "en" else entity.get("description_ar")
            return topic

        if result:
            if result.get("matched_topics"):
                result["matched_topics"] = [_enrich_search_topic(dict(t)) for t in result["matched_topics"]]
                # Sources stay attached to the concept they support. Do not merge
                # them into one compound list that could look like a source for a
                # causal relationship between the symptoms.
                result["sources"] = []
            else:
                result = _enrich_search_topic(result)
        else:
            # Fallback to the editable Medical Knowledge Base when the curated
            # health-search glossary does not recognize the query at all.
            normalized = medical_knowledge.normalize_symptoms([q], lang)
            canonical = normalized.get("canonical") or []
            if canonical:
                symptom = canonical[0]
                entity = medical_knowledge.get_entity("symptom", symptom["symptom_id"], public=True)
                if entity:
                    result = {
                        "key": entity.get("slug"), "emoji": "🩺", "category": "symptom",
                        "title": entity.get("name_en") if lang == "en" else entity.get("name_ar"),
                        "what": entity.get("description_en") if lang == "en" else entity.get("description_ar"),
                        "causes": [],
                        "causes_label": "💡 Common causes" if lang == "en" else "💡 الأسباب المحتملة",
                        "worry": entity.get("red_flags_en") if lang == "en" else entity.get("red_flags_ar"),
                        "doctor": (
                            "Seek medical review if symptoms persist, worsen, or a red flag appears."
                            if lang == "en" else
                            "اطلب مراجعة طبية إذا استمرت الأعراض أو ساءت أو ظهرت علامة خطر."
                        ),
                        "sources": _entity_sources(entity),
                        "recognized_topics": [entity.get("name_en") if lang == "en" else entity.get("name_ar")],
                        "original_query": q,
                    }

        return jsonify({
            "ok": True,
            "result": result,
            "suggestions": health_search.suggestion_terms(lang),
        })
    except Exception as e:
        return _mk_error(e, 500)


@app.route("/api/explain")
def api_explain():
    try:
        lang = "en" if request.args.get("lang") == "en" else "ar"
        term = (request.args.get("term") or "").strip()[:120]
        return jsonify({"ok": True, "result": health_search.explain_term(term, lang) if term else None})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"})


@app.route("/api/calc")
def api_calc():
    try:
        kind = (request.args.get("kind") or "").strip()
        if kind == "bmi":
            w = float(request.args.get("w", ""))
            h = float(request.args.get("h", ""))
            if w <= 0 or w > 500 or h <= 0 or h > 250:
                return jsonify({"ok": False, "error": "invalid bmi input"})
            return jsonify({"ok": True, "kind": "bmi", **calcmod.calc_bmi(w, h)})
        if kind == "fluids":
            age = float(request.args.get("age", ""))
            w = float(request.args.get("w", ""))
            act = request.args.get("act", "low")
            if w <= 0 or w > 500 or age <= 0 or age > 120 or act not in ("low", "medium", "high"):
                return jsonify({"ok": False, "error": "invalid fluids input"})
            return jsonify({"ok": True, "kind": "fluids", **calcmod.calc_fluids(int(age), w, act)})
        if kind == "dose":
            hh = int(float(request.args.get("h", "")))
            mm = int(float(request.args.get("m", "")))
            iv = int(float(request.args.get("iv", "")))
            if iv not in calcmod.DOSE_INTERVALS:
                return jsonify({"ok": False, "error": "invalid interval"})
            return jsonify({"ok": True, "kind": "dose", **calcmod.calc_doses(hh, mm, iv)})
        if kind == "cal":
            age = float(request.args.get("age", ""))
            g = request.args.get("g", "male")
            h = float(request.args.get("h", ""))
            w = float(request.args.get("w", ""))
            act = request.args.get("act", "low")
            if age <= 0 or age > 120 or w <= 0 or w > 500 or h <= 0 or h > 250:
                return jsonify({"ok": False, "error": "invalid calories input"})
            return jsonify({"ok": True, "kind": "cal", **calcmod.calc_calories(int(age), g, h, w, act)})
        if kind == "sugar":
            val = float(request.args.get("val", ""))
            unit = request.args.get("unit", "mg")
            mtype = request.args.get("type", "fasting")
            age_raw = request.args.get("age", "").strip()
            age = int(float(age_raw)) if age_raw else None
            if mtype not in calcmod.SUGAR_TYPES:
                return jsonify({"ok": False, "error": "invalid measurement type"})
            if val <= 0 or (mtype == "a1c" and val > 25):
                return jsonify({"ok": False, "error": "invalid reading"})
            res = calcmod.calc_sugar(val, unit, mtype, age=age)
            return jsonify({"ok": True, "kind": "sugar", "type": mtype, **res})
        return jsonify({"ok": False, "error": "unknown kind"})
    except (ValueError, TypeError) as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}"})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}"})


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


@app.route("/api/hospitals", methods=["POST"])
def api_hospitals():
    data = request.get_json(force=True)
    lat, lng = data.get("lat"), data.get("lng")
    try:
        hospitals = geo_hospitals.find_nearby_hospitals(float(lat), float(lng))
        return jsonify({"ok": True, "hospitals": hospitals})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/meds", methods=["POST"])
def api_meds():
    data = request.get_json(force=True)
    try:
        warnings = medication_warnings.check_medications(data.get("text", "")) or []
        return jsonify({"ok": True, "warnings": warnings})
    except Exception as e:
        return _mk_error(e,500)


@app.route("/api/drug")
def api_drug():
    name = (request.args.get("name") or "").strip()
    d = medication_warnings.lookup_drug(name)
    if not d:
        return jsonify({"ok": True, "result": None})
    lang = "en" if _lang() == "en" else "ar"
    return jsonify({
        "ok": True, "result": True,
        "name": d["name_en"] if lang == "en" else d["name_ar"],
        "uses": d["uses_en"] if lang == "en" else d["uses_ar"],
        "warning": d["warning_en"] if lang == "en" else d["warning_ar"],
        "interactions": d["interact_en"] if lang == "en" else d["interact_ar"],
        "last_updated": d.get("updated_at"),
    })


@app.route("/api/tip")
def api_tip():
    return jsonify(health_tips.get_tip_card("en" if _lang() == "en" else "ar"))


@app.route("/api/firstaid/<key>")
def api_firstaid(key):
    lang = "en" if _lang() == "en" else "ar"
    label, text = wellbeing.first_aid_text(key, lang)
    return jsonify({"label": label, "text": text})


def _downscale_jpeg(image_bytes, max_side=1600, quality=85):
    from PIL import Image
    img = Image.open(io.BytesIO(image_bytes))
    img = img.convert("RGB")
    w, h = img.size
    scale = min(1.0, max_side / max(w, h))
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=quality)
    return out.getvalue()


def _extract_blood_from_image(client, image_bytes):
    b64 = base64.b64encode(image_bytes).decode("ascii")
    resp = client.chat.completions.create(
        model="llama-3.2-90b-vision-preview",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": (
                    "Extract ALL blood test (CBC) values from this lab report image. "
                    "Return ONLY lines in this exact form, one per line, no explanations: "
                    "HGB 13.5\nWBC 11.2\nRBC 4.8\nHCT 40\nMCV 90\nMCH 30\nMCHC 33\n"
                    "PLT 250\nNeut 55\nLymph 30\nRDW 12.5\n"
                    "If a value is missing or unreadable, skip that line. "
                    "If the patient is a child, start with: Child <age>.")},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ],
        }],
        max_tokens=500,
        temperature=0,
        timeout=45,
    )
    return resp.choices[0].message.content or ""


@app.route("/api/blood", methods=["POST"])
def api_blood():
    if not _service_consent_ok(): return _consent_required_json("/blood")
    f = request.files.get("file")
    if not f:
        return jsonify({"ok": False, "error": "لم يتم رفع ملف"})
    gender = request.form.get("gender", "f")
    age = request.form.get("age") or None
    member_id = request.form.get("member_id") or 0
    member = None
    if member_id:
        try:
            member = db.get_member(_data_user_id(), int(member_id))
        except Exception:
            member = None
    try:
        age = int(age) if age else None
    except ValueError:
        age = None
    raw = f.read()
    fname = (f.filename or "").lower()
    try:
        if fname.endswith(".pdf"):
            import fitz
            pdf = fitz.open(stream=raw, filetype="pdf")
            pix = pdf[0].get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
            img = _downscale_jpeg(pix.tobytes("png"))
            client = analysis_core._groq_client()
            extracted = _extract_blood_from_image(client, img)
        elif fname.endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")):
            img = _downscale_jpeg(raw)
            client = analysis_core._groq_client()
            extracted = _extract_blood_from_image(client, img)
        else:
            return jsonify({"ok": False, "error": "الصيغة غير مدعومة (JPG / PNG / PDF)"})
    except Exception as e:
        return jsonify({"ok": False, "error": f"قراءة الملف فشلت: {type(e).__name__}: {str(e)[:150]}"})

    try:
        entries, auto_age = blood_test.parse_blood_text(extracted)
        if not entries:
            return jsonify({"ok": False, "error": "ما قدرنا نستخرج القيم من الصورة — تأكدي من وضوح الصورة وأعدي المحاولة."})
        if age is None and member and member.get("age"):
            try:
                age = int(member["age"])
            except (TypeError, ValueError):
                pass
        if age is None:
            age = auto_age
        results, notes, dangers, level, child_note = blood_test.analyze_blood(entries, gender, age)
        lang = "en" if _lang() == "en" else "ar"
        text_html = blood_test.build_text(results, gender, lang, notes, dangers, child_note)
        indicators = blood_test.describe_results(results, lang)
        chart_b64 = None
        try:
            chart = blood_test.generate_blood_chart(results)
            if chart:
                chart_b64 = base64.b64encode(chart).decode("ascii")
        except Exception:
            chart_b64 = None
        payload = {
            "gender": gender, "age": age, "level": level,
            "summary": blood_test.summary_text(level, lang),
            "indicators": indicators,
            "notes": [n[0] if lang == "ar" else n[1] for n in notes],
            "dangers": [d[1] if lang == "ar" else d[2] for d in dangers],
        }
        blood_id = None
        try:
            blood_id = db.save_blood_test(_data_user_id(), payload, int(member_id or 0))
        except Exception:
            blood_id = None
        return jsonify({
            "ok": True, "text_html": text_html, "chart": chart_b64, "level": level,
            "indicators": indicators,
            "notes": [n[0] if lang == "ar" else n[1] for n in notes],
            "dangers": [d[1] if lang == "ar" else d[2] for d in dangers],
            "summary": blood_test.summary_text(level, lang),
            "disclaimer": blood_test.disclaimer_text(lang),
            "child": bool(child_note),
            "child_note": blood_test.child_note_text(lang) if child_note else None,
            "blood_id": blood_id,
            "member_name": member.get("name") if member else None,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"})


def run_webapp():
    db.init_db()
    try:
        owner_state = db.ensure_owner_admin_by_email()
        app.logger.info(
            "ADMIN_AUTH startup owner_found=%s role_sync=%s reason=%s",
            bool(owner_state.get("found")), bool(owner_state.get("promoted")), owner_state.get("reason", "unknown")
        )
    except Exception as exc:
        app.logger.error("ADMIN_AUTH startup role synchronization failed: %s", type(exc).__name__)
    medical_knowledge.init_schema()
    platform_v2.init_schema()
    privacy_features.init_schema()
    advanced_features.init_schema()
    admin_operational.init_schema()
    medication_push.init_schema()
    medication_push.start_embedded_worker_once()
    port = int(os.environ.get("PORT", 5000))
    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=port, threads=8)
    except ImportError:
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    run_webapp()
