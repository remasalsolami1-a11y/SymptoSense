"""User/Admin pages introduced in the V47 platform upgrade."""
from __future__ import annotations
import html as html_lib
import json
from datetime import datetime, timezone
from urllib.parse import urlencode
from flask import Blueprint, redirect, request, jsonify, session, url_for, abort

import db
import admin_2fa
import admin_security
import feature_flags
import medical_knowledge
import passkeys
import platform_v2
import web_security

_PASSKEY_JS = r"""
function b64uToBytes(v){v=(v||'').replace(/-/g,'+').replace(/_/g,'/');while(v.length%4)v+='=';const s=atob(v);return Uint8Array.from(s,c=>c.charCodeAt(0));}
function bytesToB64u(v){if(!v)return null;const a=new Uint8Array(v);let s='';a.forEach(b=>s+=String.fromCharCode(b));return btoa(s).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');}
function normalizeCreate(o){o.challenge=b64uToBytes(o.challenge);o.user.id=b64uToBytes(o.user.id);if(o.excludeCredentials)o.excludeCredentials=o.excludeCredentials.map(x=>({...x,id:b64uToBytes(x.id)}));return o;}
function normalizeGet(o){o.challenge=b64uToBytes(o.challenge);if(o.allowCredentials)o.allowCredentials=o.allowCredentials.map(x=>({...x,id:b64uToBytes(x.id)}));return o;}
function credentialJSON(c){const r=c.response||{};return {id:c.id,type:c.type,rawId:bytesToB64u(c.rawId),authenticatorAttachment:c.authenticatorAttachment||null,clientExtensionResults:c.getClientExtensionResults?c.getClientExtensionResults():{},response:{clientDataJSON:bytesToB64u(r.clientDataJSON),attestationObject:bytesToB64u(r.attestationObject),authenticatorData:bytesToB64u(r.authenticatorData),signature:bytesToB64u(r.signature),userHandle:bytesToB64u(r.userHandle),transports:r.getTransports?r.getTransports():[]}};}
"""


def create_blueprint(*, page_renderer, lang_getter, current_user_id, current_user,
                     login_required_decorator, admin_api_required_decorator,
                     admin_session_valid, admin_login_endpoint, safe_next_url,
                     begin_admin_2fa_challenge):
    bp = Blueprint("v47_pages", __name__)

    def ar(): return lang_getter() == "ar"

    @bp.get("/demo")
    def competition_demo():
        return redirect("/chat?demo=1")

    def passkey_login_user(user_id: int) -> dict:
        user = db.get_ss_user(int(user_id))
        if not user or user.get("status") != "active" or not bool(user.get("email_verified", True)):
            raise ValueError("account_unavailable")
        db.promote_existing_owner_admin(int(user_id))
        user = db.get_ss_user(int(user_id)) or user
        is_admin = user.get("role") == "admin"
        if is_admin and admin_2fa.required():
            begin_admin_2fa_challenge(int(user_id))
            st = admin_2fa.status(int(user_id))
            return {"authenticated": False, "next": "/admin/2fa" if st.get("enabled") else "/admin/2fa/setup", "admin_2fa_required": True}
        session.clear(); session["ss_user_id"] = int(user_id); session.permanent = True
        session["login_toast"] = "admin" if is_admin else "user"
        if is_admin:
            session["admin_last_seen"] = int(datetime.now(timezone.utc).timestamp())
            session["admin_2fa_verified"] = not admin_2fa.required()
            session["admin_session_epoch"] = admin_security.current_epoch(int(user_id))
        try:
            platform_v2.audit(int(user_id), "passkey_login", "account_security", "self", None, {"status":"success"})
        except Exception:
            pass
        return {"authenticated": True, "next": "/admin" if is_admin else "/profile", "admin": is_admin}

    @bp.get("/passkeys")
    @login_required_decorator
    def passkeys_page():
        if not (feature_flags.PASSKEYS and feature_flags.API_V1):
            abort(404)
        is_ar=ar(); cfg=passkeys.config(); creds=passkeys.list_for_user(int(current_user_id()))
        rows="".join(
            '<div class="ss-card" style="padding:14px"><div class="ss-row" style="justify-content:space-between"><div><b>%s</b><div class="ss-muted">%s</div></div><button type="button" class="ss-btn ss-btn-danger js-delete-passkey" data-id="%s">%s</button></div></div>' % (
                html_lib.escape(str(x.get("label") or "Passkey"), quote=True),
                html_lib.escape(str(x.get("created_at") or ""), quote=True), int(x["id"]), "حذف" if is_ar else "Delete"
            ) for x in creds
        ) or ('<p class="ss-muted">لا توجد مفاتيح مرور مسجلة بعد.</p>' if is_ar else '<p class="ss-muted">No passkeys registered yet.</p>')
        available=bool(cfg.get("library") and cfg.get("secure_origin"))
        unavailable="" if available else ('<div class="ss-alert ss-alert-warning">ميزة مفاتيح المرور تحتاج HTTPS ومكتبة WebAuthn على الخادم.</div>' if is_ar else '<div class="ss-alert ss-alert-warning">Passkeys require HTTPS and the server WebAuthn dependency.</div>')
        success_text=json.dumps('تمت إضافة مفتاح المرور بنجاح.' if is_ar else 'Passkey added successfully.',ensure_ascii=False)
        fail_text=json.dumps('تعذر إضافة مفتاح المرور. تأكد من دعم الجهاز والمحاولة عبر HTTPS.' if is_ar else 'Could not add the passkey. Make sure the device supports it and the site is using HTTPS.',ensure_ascii=False)
        confirm_text=json.dumps('حذف مفتاح المرور؟' if is_ar else 'Delete this passkey?',ensure_ascii=False)
        disabled='' if available else 'disabled'
        body=f'''<main class="container" style="max-width:850px;padding-top:26px;padding-bottom:40px"><div class="ss-stack"><section class="ss-card"><span class="ss-badge">WebAuthn</span><h1>{"مفاتيح المرور" if is_ar else "Passkeys"}</h1><p class="ss-muted">{"سجّل الدخول ببصمة الجهاز أو Face ID أو Windows Hello دون الاعتماد على كلمة المرور وحدها." if is_ar else "Use your device biometrics, Face ID, or Windows Hello instead of relying on a password alone."}</p>{unavailable}<button type="button" id="addPasskey" class="ss-btn ss-btn-primary" {disabled}>🔐 {"إضافة مفتاح مرور" if is_ar else "Add passkey"}</button><div id="passkeyMsg" class="ss-alert" style="display:none;margin-top:12px"></div></section><section><h2>{"المفاتيح المسجلة" if is_ar else "Registered passkeys"}</h2><div class="ss-stack">{rows}</div></section></div></main>
<script>{_PASSKEY_JS}
const msg=document.getElementById('passkeyMsg');function showMsg(t,ok){{msg.style.display='block';msg.className='ss-alert '+(ok?'ss-alert-success':'ss-alert-danger');msg.textContent=t;}}
document.getElementById('addPasskey')?.addEventListener('click',async()=>{{try{{const opts=await (await fetch('/api/v1/passkeys/register/options',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:'{{}}'}})).json();const cred=await navigator.credentials.create({{publicKey:normalizeCreate(opts)}});const r=await fetch('/api/v1/passkeys/register/verify',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{credential:credentialJSON(cred),label:'Device passkey'}})}});const j=await r.json();if(!r.ok||!j.ok)throw new Error('registration_failed');showMsg({success_text},true);setTimeout(()=>location.reload(),700);}}catch(e){{showMsg({fail_text},false);}}}});
document.querySelectorAll('.js-delete-passkey').forEach(b=>b.addEventListener('click',async()=>{{if(!confirm({confirm_text}))return;const r=await fetch('/api/v1/passkeys/'+b.dataset.id,{{method:'DELETE'}});if(r.ok)location.reload();}}));</script>'''
        return page_renderer("مفاتيح المرور" if is_ar else "Passkeys",body)

    @bp.get("/passkeys/login")
    def passkeys_login_page():
        if not (feature_flags.PASSKEYS and feature_flags.API_V1):
            abort(404)
        is_ar=ar(); next_target=safe_next_url("/profile")
        next_query=html_lib.escape(urlencode({"next": next_target}), quote=True)
        next_js=web_security.json_for_script(next_target, ensure_ascii=False)
        fail_text=web_security.json_for_script('تعذر تسجيل الدخول بمفتاح المرور. جرّب كلمة المرور أو مفتاحًا مسجلًا على هذا الجهاز.' if is_ar else 'Passkey sign-in failed. Try your password or a passkey registered on this device.', ensure_ascii=False)
        body=f'''<main class="container" style="max-width:620px;padding-top:42px"><section class="ss-card" style="text-align:center"><div style="font-size:42px">🔐</div><h1>{"تسجيل الدخول بمفتاح مرور" if is_ar else "Sign in with a passkey"}</h1><p class="ss-muted">{"استخدم البصمة أو Face ID أو Windows Hello المرتبط بحسابك." if is_ar else "Use the fingerprint, Face ID, or Windows Hello passkey linked to your account."}</p><button type="button" id="passkeyLogin" class="ss-btn ss-btn-primary">{"متابعة بمفتاح المرور" if is_ar else "Continue with passkey"}</button><div id="passkeyLoginMsg" class="ss-alert" style="display:none;margin-top:12px"></div><p><a href="/login?{next_query}">{"استخدام كلمة المرور بدلًا من ذلك" if is_ar else "Use password instead"}</a></p></section></main>
<script>{_PASSKEY_JS}
const out=document.getElementById('passkeyLoginMsg');document.getElementById('passkeyLogin').addEventListener('click',async()=>{{try{{const opts=await (await fetch('/api/v1/passkeys/auth/options',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:'{{}}'}})).json();const cred=await navigator.credentials.get({{publicKey:normalizeGet(opts)}});const r=await fetch('/api/v1/passkeys/auth/verify',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{credential:credentialJSON(cred)}})}});const j=await r.json();if(!r.ok||!j.ok)throw new Error('auth_failed');location.href=(j.data&&j.data.next)||{next_js};}}catch(e){{out.style.display='block';out.className='ss-alert ss-alert-danger';out.textContent={fail_text};}}}});</script>'''
        return page_renderer("Passkey Login",body)

    @bp.get("/admin/source-monitor")
    @login_required_decorator
    def admin_source_monitor_page():
        if not (feature_flags.SOURCE_MONITOR and feature_flags.API_V1):
            abort(404)
        if not admin_session_valid(): return redirect(url_for(admin_login_endpoint))
        is_ar=ar()
        body=f'''<main class="container" style="max-width:1100px;padding-top:26px"><div class="ss-stack"><section class="ss-card"><span class="ss-badge">Source Governance</span><h1>{"مراقبة المصادر الطبية" if is_ar else "Medical source monitor"}</h1><p class="ss-muted">{"يفحص حداثة المصادر وحالتها ويكشف الروابط المكسورة دون تعديل المحتوى تلقائيًا." if is_ar else "Checks source freshness and availability and flags broken links without automatically changing medical content."}</p><button type="button" id="runSourceMonitor" class="ss-btn ss-btn-primary">▶ {"تشغيل الفحص" if is_ar else "Run monitor"}</button><span id="sourceJob" class="ss-muted"></span></section><section class="ss-card"><div id="sourceSummary" class="ss-row"></div><div id="sourceTable" class="ss-table-wrap"><p style="padding:14px" class="ss-muted">{"جاري تحميل الحالة…" if is_ar else "Loading status…"}</p></div></section></div></main>
<script>
const isAr={str(is_ar).lower()};const sum=document.getElementById('sourceSummary'),table=document.getElementById('sourceTable'),job=document.getElementById('sourceJob');
function esc(s){{return String(s??'').replace(/[&<>\"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}}[c]));}}
async function loadStatus(){{const r=await fetch('/api/v1/admin/source-monitor');const j=await r.json();if(!r.ok||!j.ok){{table.textContent=isAr?'تعذر تحميل الحالة':'Unable to load status';return;}}const d=j.data||{{}},items=d.items||[],review=(d.review||{{}}).counts||{{}};sum.innerHTML=`<span class="ss-badge">${{isAr?'المصادر المفحوصة':'Checked sources'}}: ${{items.length}}</span><span class="ss-badge">${{isAr?'قديمة':'Outdated'}}: ${{review.outdated||0}}</span><span class="ss-badge">${{isAr?'تحتاج مراجعة':'Needs review'}}: ${{review.needs_review||0}}</span>`;table.innerHTML='<table class="ss-table"><thead><tr><th>ID</th><th>URL</th><th>'+(isAr?'الحالة':'State')+'</th><th>HTTP</th><th>'+(isAr?'آخر فحص':'Checked')+'</th></tr></thead><tbody>'+items.map(x=>`<tr><td>${{x.source_id}}</td><td><code>${{esc(x.url)}}</code></td><td>${{esc(x.state)}}</td><td>${{x.http_status??'—'}}</td><td>${{esc(x.checked_at)}}</td></tr>`).join('')+'</tbody></table>';}}
document.getElementById('runSourceMonitor').addEventListener('click',async()=>{{job.textContent=isAr?'جاري جدولة الفحص…':'Queueing…';const r=await fetch('/api/v1/admin/source-monitor/run',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:'{{}}'}});const j=await r.json();if(!r.ok||!j.ok){{job.textContent=isAr?'تعذر تشغيل الفحص':'Unable to start';return;}}const id=j.data.job_id;job.textContent=(isAr?'رقم المهمة: ':'Job: ')+id;for(let i=0;i<30;i++){{await new Promise(r=>setTimeout(r,1000));const q=await (await fetch('/api/v1/admin/jobs/'+id)).json();if(q.data&&['finished','failed'].includes(q.data.status)){{job.textContent=q.data.status;await loadStatus();break;}}}}}});loadStatus();
</script>'''
        return page_renderer("Source Monitor",body)

    @bp.post("/api/admin/knowledge/versions/<entity_type>/<int:entity_id>/rollback")
    @admin_api_required_decorator("medical")
    def admin_knowledge_rollback(entity_type,entity_id):
        data=request.get_json(silent=True) or {}
        try:
            version=int(data.get("version")); result=medical_knowledge.rollback_version(entity_type,entity_id,version,current_user()); return jsonify({"ok":True,"rollback":result})
        except (TypeError,ValueError) as exc:
            code = str(exc)
            allowed = {"invalid_entity", "version_not_found", "invalid_version", "invalid_input"}
            return jsonify({"ok":False,"error":code if code in allowed else "invalid_rollback_request"}),400

    return bp, passkey_login_user
