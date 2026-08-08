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

from flask import Flask, request, jsonify, render_template_string, session, send_file, Response

import db
import ml_diagnosis
import medication_warnings
import geo_hospitals
import blood_test
import wellbeing
import health_tips
import analysis_core

from dashboard import DASHBOARD_HTML

app = Flask(__name__)
app.secret_key = os.environ.get("WEB_SECRET", "symptosense-dev-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024

BASE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Cairo', 'Segoe UI', Tahoma, sans-serif; background: #f6f9fb; color: #1e293b; }
a { text-decoration: none; color: inherit; }
.nav { background: #0f766e; color: #fff; display: flex; align-items: center; justify-content: space-between; padding: 12px 22px; position: sticky; top: 0; z-index: 50; box-shadow: 0 2px 10px rgba(0,0,0,.15); flex-wrap: wrap; gap: 8px; }
.nav .logo { font-size: 20px; font-weight: 800; letter-spacing: .3px; }
.nav .logo span { color: #99f6e4; }
.nav .links { display: flex; gap: 4px; flex-wrap: wrap; }
.nav .links a { color: #ccfbf1; padding: 7px 12px; border-radius: 8px; font-size: 14px; }
.nav .links a:hover { background: #115e59; color: #fff; }
.container { max-width: 1080px; margin: 0 auto; padding: 26px 18px; }
.hero { background: linear-gradient(135deg, #0f766e 0%, #0d9488 55%, #14b8a6 100%); color: #fff; border-radius: 20px; padding: 48px 36px; text-align: center; margin-bottom: 30px; }
.hero h1 { font-size: 40px; margin-bottom: 12px; }
.hero p { font-size: 17px; opacity: .95; max-width: 640px; margin: 0 auto 24px; line-height: 1.8; }
.btn { display: inline-block; background: #fff; color: #0f766e; font-weight: 700; padding: 13px 30px; border-radius: 12px; margin: 6px; font-size: 16px; border: none; cursor: pointer; }
.btn.ghost { background: rgba(255,255,255,.15); color: #fff; border: 1px solid rgba(255,255,255,.5); }
.btn:hover { transform: translateY(-1px); }
.btn.small { padding: 7px 14px; font-size: 13px; border-radius: 9px; margin: 3px; }
.btn.ghost.small { background: #f0f7f6; color: #0f766e; border: 1px solid #0f766e; }
.card { background: #fff; border-radius: 16px; padding: 22px; box-shadow: 0 1px 6px rgba(15,23,42,.06); border: 1px solid #e2e8f0; margin-bottom: 20px; }
.card h2 { color: #0f766e; margin-bottom: 12px; font-size: 20px; }
.features { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin-bottom: 24px; }
.feature { background: #fff; border: 1px solid #e2e8f0; border-radius: 14px; padding: 20px; }
.feature .ic { font-size: 30px; }
.feature h3 { font-size: 16px; margin: 10px 0 6px; color: #0f766e; }
.feature p { font-size: 14px; color: #475569; line-height: 1.7; }
a.feature.serv { display: block; text-decoration: none; transition: transform .12s ease, box-shadow .12s ease, border-color .12s ease; }
a.feature.serv:hover { transform: translateY(-3px); box-shadow: 0 8px 20px rgba(13,148,136,.14); border-color: #14b8a6; }
.steps { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
.step { background: #fff; border: 1px solid #e2e8f0; border-radius: 14px; padding: 20px; text-align: center; }
.step .n { width: 34px; height: 34px; border-radius: 50%; background: #0f766e; color: #fff; display: inline-flex; align-items: center; justify-content: center; font-weight: 800; }
.step h3 { margin: 10px 0 6px; font-size: 15px; }
.step p { font-size: 13px; color: #64748b; }
.warn { background: #fff7ed; border: 1px solid #fdba74; color: #7c2d12; border-radius: 12px; padding: 14px 18px; font-size: 14px; margin-bottom: 22px; }
.footer { text-align: center; padding: 22px; color: #94a3b8; font-size: 13px; background: #0f172a; color: #cbd5e1; margin-top: 30px; }
.footer a { color: #99f6e4; }
.chat-wrap { max-width: 680px; margin: 0 auto; background: #fff; border-radius: 18px; box-shadow: 0 4px 20px rgba(15,23,42,.08); border: 1px solid #e2e8f0; overflow: hidden; display: flex; flex-direction: column; height: 78vh; }
.chat-head { background: #0f766e; color: #fff; padding: 14px 18px; display: flex; align-items: center; gap: 10px; }
.chat-head .avatar { width: 40px; height: 40px; border-radius: 50%; background: #99f6e4; color: #0f766e; display: flex; align-items: center; justify-content: center; font-size: 20px; }
.chat-head h3 { font-size: 16px; }
.chat-head p { font-size: 12px; opacity: .85; }
.chat-head .spk-btn { margin-left: auto; background: rgba(255,255,255,.15); border: none; border-radius: 10px; padding: 8px 10px; font-size: 13px; cursor: pointer; color: #fff; white-space: nowrap; }
.chat-body { flex: 1; overflow-y: auto; padding: 18px; background: #f0f7f6; }
.bubble { max-width: 85%; margin-bottom: 10px; padding: 11px 15px; border-radius: 14px; font-size: 15px; line-height: 1.8; white-space: pre-wrap; }
.bubble.bot { background: #fff; border: 1px solid #e2e8f0; border-bottom-right-radius: 4px; }
.bubble.user { background: #0f766e; color: #fff; margin-left: auto; border-bottom-left-radius: 4px; }
.bubble.result { background: #fff; border: 1px solid #99f6e4; max-width: 100%; }
.chat-options { padding: 14px; background: #fff; border-top: 1px solid #e2e8f0; display: flex; flex-wrap: wrap; gap: 8px; }
.opt { background: #f0f7f6; border: 1.5px solid #0f766e; color: #0f766e; padding: 9px 16px; border-radius: 24px; font-size: 14px; cursor: pointer; }
.vidbtn { display:inline-block; margin-top:12px; background:#14b8a6; color:#fff; border:none; padding:10px 18px; border-radius:24px; font-size:14px; cursor:pointer; }
.vidbtn:hover { background:#0f766e; }
.vidwrap iframe { display:block; }
.opt.sel { background: #0f766e; color: #fff; }
.opt.danger { border-color: #dc2626; color: #dc2626; background: #fef2f2; }
.opt:hover { opacity: .9; }
.chat-input { display: flex; gap: 8px; padding: 12px 14px; background: #fff; border-top: 1px solid #e2e8f0; }
.chat-input input { flex: 1; border: 1px solid #cbd5e1; border-radius: 12px; padding: 12px 14px; font-size: 15px; font-family: inherit; }
.chat-input button { background: #0f766e; color: #fff; border: none; border-radius: 12px; padding: 12px 20px; font-size: 15px; cursor: pointer; }
.urg-low { border-right: 6px solid #16a34a; }
.urg-medium { border-right: 6px solid #d97706; }
.urg-high { border-right: 6px solid #dc2626; }
.sec-title { font-weight: 800; color: #0f766e; margin: 14px 0 6px; font-size: 15px; }
.res-sec { margin: 10px 0; }
.rec-item { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 12px; margin: 8px 0; }
.rec-item .src { color: #0d9488; font-size: 12px; }
.drop { border: 2px dashed #0f766e; border-radius: 16px; padding: 40px; text-align: center; color: #0f766e; cursor: pointer; background: #f0f7f6; margin-bottom: 16px; }
.drop.on { background: #ccfbf1; }
.muted { color: #64748b; font-size: 13px; }
.card label { display: block; font-size: 13px; font-weight: 700; color: #0f766e; margin-bottom: 4px; }
.card input, .card select { width: 100%; padding: 10px 12px; border: 1px solid #cbd5e1; border-radius: 10px; font-size: 14px; font-family: inherit; background: #f8fafc; color: #1e293b; }
.pr-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.hist-card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 14px 16px; margin-bottom: 12px; }
.hist-head { display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap; }
.pill { padding: 3px 11px; border-radius: 999px; font-size: 12px; font-weight: 700; }
.pill-hi { background: #fee2e2; color: #b91c1c; }
.pill-med { background: #fef3c7; color: #92400e; }
.pill-low { background: #dcfce7; color: #166534; }
.hist-row { margin-top: 8px; display: flex; gap: 6px; flex-wrap: wrap; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 700px) { .grid2 { grid-template-columns: 1fr; } .hero h1 { font-size: 30px; } .chat-wrap { height: 84vh; } }
label.lbl { display: block; font-size: 14px; font-weight: 700; margin: 12px 0 6px; color: #334155; }
input.inp, select.inp, textarea.inp { width: 100%; border: 1px solid #cbd5e1; border-radius: 10px; padding: 12px; font-size: 15px; font-family: inherit; }
table.tbl { width: 100%; border-collapse: collapse; font-size: 14px; }
table.tbl th, table.tbl td { border: 1px solid #e2e8f0; padding: 9px 11px; text-align: right; }
table.tbl th { background: #0f766e; color: #fff; }
.pill { display: inline-block; padding: 3px 12px; border-radius: 20px; font-size: 13px; font-weight: 700; }
.pill.low { background: #dcfce7; color: #166534; }
.pill.medium { background: #fef3c7; color: #92400e; }
.pill.high { background: #fee2e2; color: #991b1b; }
.badge { background: #0f766e; color: #fff; padding: 4px 12px; border-radius: 20px; font-size: 12px; }
.bar-bg { background: #e2e8f0; border-radius: 8px; height: 10px; width: 100%; margin: 4px 0; }
.bar-fill { background: #0d9488; height: 10px; border-radius: 8px; }
.spin { display: inline-block; width: 16px; height: 16px; border: 2px solid #99f6e4; border-top-color: transparent; border-radius: 50%; animation: sp 1s linear infinite; vertical-align: middle; }
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
.welcome-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 22px; box-shadow: 0 10px 30px rgba(15,23,42,.08); padding: 42px 30px; max-width: 560px; width: 100%; text-align: center; }
.welcome-card .logo-big { font-size: 62px; }
.welcome-card h1 { font-size: 30px; color: #0f766e; margin: 14px 0 8px; }
.welcome-card p { color: #475569; font-size: 15px; line-height: 1.8; margin-bottom: 26px; }
.lang-row { display: flex; gap: 14px; justify-content: center; flex-wrap: wrap; }
.lang-btn { flex: 1; min-width: 200px; background: #f0f7f6; border: 2px solid #0f766e; border-radius: 14px; padding: 22px 14px; cursor: pointer; transition: transform .12s ease, box-shadow .12s ease, background .12s ease; }
.lang-btn:hover { transform: translateY(-3px); box-shadow: 0 8px 20px rgba(13,148,136,.18); background: #ccfbf1; }
.lang-btn .lc { font-size: 34px; display: block; margin-bottom: 8px; }
.lang-btn .lt { font-size: 20px; font-weight: 800; color: #0f766e; display: block; }
.lang-btn .ld { font-size: 13px; color: #475569; display: block; margin-top: 4px; }
.multi-greet { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; margin: 0 0 22px; }
.greet-line { display: inline-flex; align-items: center; gap: 7px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 999px; padding: 6px 14px; font-size: 13.5px; color: #334155; }
.greet-line .gflag { font-size: 16px; }
.welcome-full { min-height: 100vh; display: flex; flex-direction: column; background: linear-gradient(180deg, #f6f9fb 0%, #e8f7f4 100%); }
.welcome-wall { flex: 1; display: flex; flex-wrap: wrap; align-content: flex-start; align-items: center; justify-content: center; gap: 8px 10px; padding: 36px 22px 18px; overflow: hidden; }
.greet-chip { display: inline-flex; align-items: center; gap: 6px; padding: 7px 14px; border-radius: 999px; background: rgba(255,255,255,.85); border: 1px solid #ccfbf1; box-shadow: 0 1px 4px rgba(13,148,136,.10); font-size: 14px; color: #0f766e; }
.welcome-pick { max-width: 620px; width: 92%; margin: 0 auto 36px; background: #fff; border: 1px solid #e2e8f0; border-radius: 22px; box-shadow: 0 10px 30px rgba(15,23,42,.10); padding: 26px 24px; text-align: center; }
.welcome-pick .logo-big { font-size: 52px; }
.welcome-pick h1 { font-size: 26px; color: #0f766e; margin: 10px 0 4px; }
.pick-btn { display: inline-block; margin: 4px; padding: 10px 26px; border-radius: 999px; border: 2px solid #0f766e; background: #0f766e; color: #fff; font-family: inherit; font-size: 15px; font-weight: 700; cursor: pointer; transition: transform .12s ease, background .12s ease; }
.pick-btn:hover { transform: translateY(-2px); background: #115e59; }
.nav .lang-sw { display: flex; align-items: center; gap: 4px; }
.nav .lang-sw a { font-size: 13px; padding: 4px 9px; border-radius: 8px; background: rgba(255,255,255,.12); color: #ccfbf1; }
.nav .lang-sw a.on { background: #99f6e4; color: #0f766e; font-weight: 700; }
"""

PAGE_FRAME = """
<!DOCTYPE html>
<html lang="__LANG__" dir="__DIR__">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
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
<meta property="og:type" content="website">
<meta property="og:site_name" content="SymptoSense">
<meta name="theme-color" content="#0ea5e9">
<style>__CSS__</style>
</head>
<body>
<script>
function setLang(l) {
  document.cookie = 'lang=' + l + ';path=/;max-age=31536000;SameSite=Lax';
  try { localStorage.setItem('ss_lang', l); } catch(e) {}
  location.href = (l === 'ar') ? '/home' : '/home';
}
</script>
__NAV__
<div class="container">
__BODY__
</div>
__FOOTER__
</body>
</html>
"""


def _user_id():
    if "uid" not in session:
        session["uid"] = secrets.token_hex(8)
    return "web-" + hashlib.sha1(session["uid"].encode()).hexdigest()[:12]


def _site_url():
    return os.environ.get("SITE_URL", "https://symptosense.up.railway.app").rstrip("/")


def _lang():
    lang = request.cookies.get("lang") or request.args.get("lang")
    return "en" if lang == "en" else "ar"


L = {
    "ar": {
        "nav_home": "الرئيسية", "nav_chat": "فحص الأعراض", "nav_blood": "تحليل الدم",
        "nav_meds": "الأدوية", "nav_emergency": "الطوارئ", "nav_checkin": "متابعتي",
        "nav_firstaid": "الإسعافات", "nav_tips": "النصائح", "nav_relax": "الاسترخاء",
        "nav_admin": "لوحة التحكم", "nav_about": "عن الموقع",
        "nav_profile": "ملفي", "nav_history": "سجلّي",
        "footer_note": "SymptoSense © 2026 — للتوعية الصحية فقط وليس بديلاً عن الاستشارة الطبية.",
        "footer_emergency": "في حالة الطوارئ اتصل بالإسعاف مباشرة: <b>997</b> (السعودية)",
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
        "title_about": "SymptoSense — عن الموقع",
        "desc": "مساعدك الذكي لتحليل الأعراض وتقييم الحالة الصحية الأولي بناءً على مصادر طبية موثوقة.",
        "w_title": "أهلاً بك في SymptoSense 👋",
        "w_sub": "مساعدك الذكي لتحليل الأعراض وتقييم الحالة الصحية. اختر اللغة للمتابعة.",
        "w_pick": "اختر لغتك للمتابعة 👇",
        "w_ar_l": "العربية 🇸🇦",
        "w_ar_d": "المتابعة باللغة العربية",
        "w_en_l": "English 🇬🇧",
        "w_en_d": "Continue in English",
        "home_hero_t1": "كيف تحسين؟",
        "home_hero_t2": "لنكتشف معاً 🩺",
        "home_hero_p": "أدخل أعراضك بخطوات بسيطة واحصل على تقييم أولي ذكي مدعوم بالذكاء الاصطناعي ومصادر طبية موثوقة (Mayo Clinic, NHS, WHO) — مع تحذيرات الأدوية، أقرب المستشفيات، تحليل فحوصات الدم، والإسعافات الأولية.",
        "home_btn_start": "ابدأ الفحص الآن 🚀",
        "home_btn_blood": "تحليل فحص الدم 📋",
        "home_features_title": "اختر ما تحتاج 🧰",
        "home_f_t": "فحص الأعراض", "home_f_p": "أدخل أعراضك واحصل على تقييم أولي ذكي مع خطورة الحالة (بسيط / موعد / طوارئ).",
        "home_b_t": "تحليل فحص الدم", "home_b_p": "ارفع صورة أو PDF لتحليل الدم (CBC) واحصل على تفسير القيم والمؤشرات.",
        "home_m_t": "البحث عن دواء", "home_m_p": "تحذيرات الأدوية والتفاعلات وإرشادات الاستخدام الآمن.",
        "home_h_t": "أقرب مستشفى", "home_h_p": "بناءً على موقعك، نعرض لك أقرب المرافق الصحية بالمسافة ورابط الخريطة.",
        "home_q_t": "أسئلة لطبيبك", "home_q_p": "أسئلة ذكية جاهزة تسألها لطبيبك في الموعد، مع علامات الخطر ومتى تراجع.",
        "home_fa_t": "الإسعافات الأولية", "home_fa_p": "خطوات سريعة واضحة للحالات الطارئة اليومية.",
        "home_t_t": "نصائح صحية", "home_t_p": "نصائح يومية عملية لصحة أفضل لك ولعائلتك.",
        "home_r_t": "استرخاء وتنفس", "home_r_p": "تمارين تنفس وهدوء لتخفيف التوتر والقلق.",
        "home_e_t": "أرقام الطوارئ", "home_e_p": "أرقام مهمة جاهزة للحالات الطارئة (997، 911، 937...).",
        "home_c_t": "متابعة يومية", "home_c_p": "سجّل حالتك يومياً وتابع تحسنك بمخطط واضح.",
        "home_how_title": "كيف يعمل؟",
        "home_s1_t": "أدخل معلوماتك", "home_s1_p": "العمر، الجنس، الأعراض، المدة، الشدة بأزرار بسيطة.",
        "home_s2_t": "تحليل فوري", "home_s2_p": "محرك ذكي يقيّم حالتك من مصادر طبية موثوقة مع نموذج ML.",
        "home_s3_t": "خطة واضحة", "home_s3_p": "الاحتمالات، التوصيات، متى تزور الطبيب، وأقرب المستشفيات.",
        "home_warn": "⚠️ <b>تنبيه:</b> هذا الموقع للتوعية الصحية فقط وليس تشخيصاً طبياً نهائياً. في حال وجود أعراض خطرة (ألم صدر حاد، صعوبة تنفس، نزيف حاد، فقدان وعي) اتصل بالإسعاف فوراً <b>997</b>.",
        "ab_t1": "ما هو SymptoSense؟",
        "ab_p1": "SymptoSense مساعد صحي توعوي يعتمد على الذكاء الاصطناعي لمساعدتك في فهم أعراضك والحصول على تقييم أولي مبني على مصادر طبية موثوقة (Mayo Clinic, NHS, WHO, CDC).",
        "ab_p2": "يوفّر الموقع: تحليل الأعراض مع تقييم الخطورة، تحذيرات الأدوية وتفاعلاتها، أقرب المستشفيات بناءً على موقعك، تحليل فحوصات الدم، الإسعافات الأولية، ونصائح صحية يومية.",
        "ab_p3": "يتم التحليل عبر نموذج ذكاء اصطناعي (Llama عبر Groq) مع طبقة تحقق بالقواعد ونموذج تعلم آلي لتقدير الاحتمالات — وكل ذلك كأداة توعية مساعدة.",
        "ab_p4": "هذا الموقع <b>ليس تشخيصاً طبياً نهائياً</b> ولا بديلاً عن استشارة الطبيب المختص. عند أي عرض خطر اتصل بالإسعاف فوراً.",
        "ab_srcs": "المصادر الطبية المعتمدة:",
        "ab_srcs_p": "Mayo Clinic، NHS، World Health Organization (WHO)، CDC، MedlinePlus — تُذكر داخل كل توصية مع رابطها.",
        "ab_note": "بياناتك تُخزّن بشكل مجهول (بدون هوية) وتُستخدم فقط لتحسين الخدمة والإحصاءات.",
        "chat_sub": "مساعد التحليل الذكي",
        "chat_head_p": "مساعد التحليل الذكي — بالعربية 🇸🇦",
        "chat_muted": "التوعية فقط وليس تشخيصاً نهائياً — راجع الطبيب عند أي شك.",
        "title_profile": "SymptoSense — الملف الشخصي",
        "title_history": "SymptoSense — سجل التشخيصات",
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
        "hs_h": "سجل التشخيصات 📄",
        "hs_sub": "كل التحليلات السابقة مع إمكانية تنزيلها PDF أو مشاركتها.",
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
    },
    "en": {
        "nav_home": "Home", "nav_chat": "Symptom Check", "nav_blood": "Blood Tests",
        "nav_meds": "Medications", "nav_emergency": "Emergency", "nav_checkin": "My Tracking",
        "nav_firstaid": "First Aid", "nav_tips": "Tips", "nav_relax": "Relax",
        "nav_admin": "Dashboard", "nav_about": "About",
        "nav_profile": "My profile", "nav_history": "My history",
        "footer_note": "SymptoSense © 2026 — Health awareness only; not a substitute for professional medical advice.",
        "footer_emergency": "In an emergency call an ambulance directly: <b>997</b> (Saudi Arabia)",
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
        "title_about": "SymptoSense — About",
        "desc": "Your smart assistant for analyzing symptoms and getting an initial health assessment based on trusted medical sources.",
        "w_title": "Welcome to SymptoSense 👋",
        "w_sub": "Your smart assistant for analyzing symptoms and assessing your health. Choose your language to continue.",
        "w_pick": "Pick your language to continue 👇",
        "w_ar_l": "العربية 🇸🇦",
        "w_ar_d": "Continue in Arabic",
        "w_en_l": "English 🇬🇧",
        "w_en_d": "Continue in English",
        "home_hero_t1": "How are you feeling?",
        "home_hero_t2": "Let's find out together 🩺",
        "home_hero_p": "Enter your symptoms in a few simple steps and get an initial smart assessment powered by AI and trusted medical sources (Mayo Clinic, NHS, WHO) — plus medication warnings, nearest hospitals, blood test analysis, and first aid.",
        "home_btn_start": "Start the check now 🚀",
        "home_btn_blood": "Blood test analysis 📋",
        "home_features_title": "What do you need? 🧰",
        "home_f_t": "Symptom Check", "home_f_p": "Enter your symptoms and get an initial smart assessment with urgency level (Mild / Appointment / Emergency).",
        "home_b_t": "Blood Test Analysis", "home_b_p": "Upload a photo or PDF of your CBC and get an interpretation of values and indicators.",
        "home_m_t": "Medication Check", "home_m_p": "Medication warnings, interactions, and safe-use guidance.",
        "home_h_t": "Nearest Hospital", "home_h_p": "Based on your location, we show the nearest health facilities with distance and a map link.",
        "home_q_t": "Questions for Your Doctor", "home_q_p": "Ready smart questions to ask your doctor, with danger signs and when to follow up.",
        "home_fa_t": "First Aid", "home_fa_p": "Clear, quick steps for everyday emergencies.",
        "home_t_t": "Health Tips", "home_t_p": "Practical daily tips for better health for you and your family.",
        "home_r_t": "Relaxation & Breathing", "home_r_p": "Breathing and calm exercises to relieve stress and anxiety.",
        "home_e_t": "Emergency Numbers", "home_e_p": "Important numbers ready for emergencies (997, 911, 937...).",
        "home_c_t": "Daily Tracking", "home_c_p": "Record your state daily and track your improvement with a clear chart.",
        "home_how_title": "How does it work?",
        "home_s1_t": "Enter your info", "home_s1_p": "Age, gender, symptoms, duration, and severity with simple buttons.",
        "home_s2_t": "Instant analysis", "home_s2_p": "A smart engine evaluates your case from trusted medical sources with an ML model.",
        "home_s3_t": "Clear plan", "home_s3_p": "Likely conditions, recommendations, when to see a doctor, and nearest hospitals.",
        "home_warn": "⚠️ <b>Note:</b> This website is for health awareness only and is not a final medical diagnosis. If you have dangerous symptoms (severe chest pain, difficulty breathing, heavy bleeding, loss of consciousness) call an ambulance immediately at <b>997</b>.",
        "ab_t1": "What is SymptoSense?",
        "ab_p1": "SymptoSense is an AI-powered health awareness assistant that helps you understand your symptoms and get an initial assessment based on trusted medical sources (Mayo Clinic, NHS, WHO, CDC).",
        "ab_p2": "The site provides: symptom analysis with urgency assessment, medication warnings and interactions, nearest hospitals based on your location, blood test analysis, first aid, and daily health tips.",
        "ab_p3": "Analysis runs through an AI model (Llama via Groq) with a rule-based verification layer and a machine-learning model for probabilities — all as a supportive awareness tool.",
        "ab_p4": "This website is <b>not a final medical diagnosis</b> and not a substitute for consulting a specialist. If you have any dangerous symptom, call an ambulance immediately.",
        "ab_srcs": "Trusted medical sources:",
        "ab_srcs_p": "Mayo Clinic, NHS, World Health Organization (WHO), CDC, MedlinePlus — mentioned within each recommendation with its link.",
        "ab_note": "Your data is stored anonymously (no identity) and used only to improve the service and statistics.",
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
        "hs_h": "Diagnosis History 📄",
        "hs_sub": "All previous analyses with PDF download and sharing options.",
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
    },
}


def _t(key):
    d = L.get(_lang(), L["ar"])
    return d.get(key, L["ar"].get(key, key))


def _nav():
    lang = _lang()
    links = [
        ("/home", "nav_home"), ("/chat", "nav_chat"), ("/blood", "nav_blood"),
        ("/meds", "nav_meds"), ("/emergency", "nav_emergency"), ("/checkin", "nav_checkin"),
        ("/firstaid", "nav_firstaid"), ("/tips", "nav_tips"), ("/relax", "nav_relax"),
        ("/profile", "nav_profile"), ("/history", "nav_history"),
        ("/admin", "nav_admin"), ("/about", "nav_about"),
    ]
    html = '<nav class="nav"><div class="logo">Sympto<span>Sense</span> 🏥</div><div class="links">'
    for href, key in links:
        html += '<a href="%s">%s</a>' % (href, _t(key))
    html += '</div>'
    html += ('<div class="lang-sw"><a href="#" onclick="setLang(&#39;ar&#39;);return false;" class="%s">ع</a>'
             '<a href="#" onclick="setLang(&#39;en&#39;);return false;" class="%s">EN</a></div>' %
             ("on" if lang == "ar" else "", "on" if lang == "en" else ""))
    html += '</nav>'
    return html


def _footer():
    return ('<div class="footer"><p>SymptoSense © 2026 — %s</p>'
            '<p style="margin-top:6px;">%s</p></div>' % (_t("footer_note"), _t("footer_emergency")))


def _page(title, body, desc=None):
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
    return (
        PAGE_FRAME
        .replace("__LANG__", "en" if lang == "en" else "ar")
        .replace("__DIR__", "ltr" if lang == "en" else "rtl")
        .replace("__TITLE__", title)
        .replace("__DESC__", desc)
        .replace("__KEYWORDS__", _t("keywords"))
        .replace("__CANONICAL__", base + request.path)
        .replace("__GSC_TAG__", gsc_tag)
        .replace("__CSS__", BASE_CSS)
        .replace("__NAV__", _nav())
        .replace("__FOOTER__", _footer())
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


def welcome_page():
    chips = "".join(
        '<span class="greet-chip"><span>%s</span>%s</span>' % (f, t)
        for f, t in GREETINGS
    )
    wall = chips * 6
    body = """
    <div class="welcome-full">
      <div class="welcome-wall">""" + wall + """</div>
      <div class="welcome-pick">
        <div class="logo-big">🏥</div>
        <h1>""" + _t("w_title") + """</h1>
        <p class="muted" style="margin-bottom:18px;">""" + _t("w_pick") + """</p>
        <div class="lang-row">
          <button class="pick-btn" onclick="setLang('ar')">🇸🇦 عربي</button>
          <button class="pick-btn" onclick="setLang('en')">English 🇬🇧</button>
        </div>
        <p class="muted" style="margin-top:20px;margin-bottom:0;">""" + _t("desc") + """</p>
      </div>
    </div>
    """
    return _page(_t("title_landing"), body)


def home_page():
    t = _t
    body = """
    <div class="hero">
      <h1>%s <span style="color:#ccfbf1;">%s</span></h1>
      <p>%s</p>
      <a class="btn" href="/chat">%s</a>
      <a class="btn ghost" href="/blood">%s</a>
    </div>

    <h2 style="text-align:center;margin-bottom:6px;">%s</h2>
    <div class="features">
      <a class="feature serv" href="/chat"><div class="ic">🩺</div><h3>%s</h3><p>%s</p></a>
      <a class="feature serv" href="/blood"><div class="ic">🩸</div><h3>%s</h3><p>%s</p></a>
      <a class="feature serv" href="/meds"><div class="ic">💊</div><h3>%s</h3><p>%s</p></a>
      <a class="feature serv" href="/chat"><div class="ic">🏥</div><h3>%s</h3><p>%s</p></a>
      <a class="feature serv" href="/chat"><div class="ic">❓</div><h3>%s</h3><p>%s</p></a>
      <a class="feature serv" href="/firstaid"><div class="ic">🚑</div><h3>%s</h3><p>%s</p></a>
      <a class="feature serv" href="/tips"><div class="ic">💡</div><h3>%s</h3><p>%s</p></a>
      <a class="feature serv" href="/relax"><div class="ic">🧘</div><h3>%s</h3><p>%s</p></a>
      <a class="feature serv" href="/emergency"><div class="ic">🚨</div><h3>%s</h3><p>%s</p></a>
      <a class="feature serv" href="/checkin"><div class="ic">📋</div><h3>%s</h3><p>%s</p></a>
    </div>

    <div class="card">
      <h2>%s</h2>
      <div class="steps">
        <div class="step"><span class="n">1</span><h3>%s</h3><p>%s</p></div>
        <div class="step"><span class="n">2</span><h3>%s</h3><p>%s</p></div>
        <div class="step"><span class="n">3</span><h3>%s</h3><p>%s</p></div>
      </div>
    </div>

    <div class="warn">%s</div>
    """ % (
        t("home_hero_t1"), t("home_hero_t2"), t("home_hero_p"),
        t("home_btn_start"), t("home_btn_blood"),
        t("home_features_title"),
        t("home_f_t"), t("home_f_p"), t("home_b_t"), t("home_b_p"),
        t("home_m_t"), t("home_m_p"), t("home_h_t"), t("home_h_p"),
        t("home_q_t"), t("home_q_p"), t("home_fa_t"), t("home_fa_p"),
        t("home_t_t"), t("home_t_p"), t("home_r_t"), t("home_r_p"),
        t("home_e_t"), t("home_e_p"), t("home_c_t"), t("home_c_p"),
        t("home_how_title"), t("home_s1_t"), t("home_s1_p"),
        t("home_s2_t"), t("home_s2_p"), t("home_s3_t"), t("home_s3_p"),
        t("home_warn"),
    )
    return _page(_t("title_landing"), body)


def about_page():
    t = _t
    body = """
    <div class="card">
      <h2>%s</h2>
      <p style="line-height:1.9;">%s</p>
      <p style="line-height:1.9;">%s</p>
      <p style="line-height:1.9;">%s</p>
    </div>
    <div class="card">
      <h2>%s</h2>
      <p style="line-height:1.9;">%s</p>
      <p class="muted">%s</p>
    </div>
    <div class="warn">%s</div>
    """ % (t("ab_t1"), t("ab_p1"), t("ab_p2"), t("ab_p3"), t("ab_srcs"), t("ab_srcs_p"), t("ab_note"), t("ab_p4"))
    return _page(_t("title_about"), body)


# ---------------------------------------------------------------- chat
CHAT = {
    "ar": {
        "welcome": "مرحباً بك في SymptoSense 🏥",
        "head_p": "مساعد التحليل الذكي — بالعربية 🇸🇦",
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
        "result_title": "📋 نتيجة التحليل",
        "urg_high": "طوارئ 🔴", "urg_medium": "يحتاج موعد طبيب 🟡", "urg_low": "بسيط 🟢",
        "forced_high": "⚠️ تم رفع الخطورة تلقائياً بناءً على الأعراض الحمراء.",
        "low_conf": "⚖️ الثقة منخفضة — يُفضل مراجعة الطبيب.",
        "possible": "🩺 الاحتمالات المحتملة",
        "medwarn": "💊 تحذيرات الأدوية",
        "medwarn_note": "التوعية فقط — لا توقفي دواءك الموصوف بدون استشارة الطبيب.",
        "ml_title": "📊 تحليل نموذج التعلم الآلي",
        "recs": "📌 التوصيات", "danger": "🚨 علامات الخطر", "when": "🕑 متى تراجع الطبيب",
        "home_care": "🏠 الرعاية المنزلية", "med_guid": "💊 إرشاد الدواء", "q_doc": "❓ اسأل طبيبك",
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
        "no_mic": "متصفحك لا يدعم الإدخال الصوتي.",
        "locating": "جاري تحديد موقعك... 📍",
        "loc_err_f": "تعذر الوصول لموقعك — تأكدي من تفعيل الموقع.",
        "loc_err_m": "تعذر الوصول لموقعك — تأكد من تفعيل الموقع.",
        "no_hosp": "ما لقينا مستشفيات قريبة.",
        "hosp_title": "🏥 أقرب المستشفيات", "map": "🗺️ فتح في الخريطة", "km": " كم",
        "sp_result": "نتيجة التحليل: الخطورة ", "sp_possible": "الاحتمالات المحتملة: ",
        "sp_recs": "التوصيات:", "sp_medwarn": "تحذيرات الأدوية:", "sp_danger": "علامات الخطر: ",
        "sp_when": "متى تراجع الطبيب: ", "sp_home": "الرعاية المنزلية: ",
        "sp_medguid": "إرشاد الدواء: ", "sp_qdoc": "أسئلة اسأل طبيبك: ",
    },
    "en": {
        "welcome": "Welcome to SymptoSense 🏥",
        "head_p": "Smart analysis assistant — English 🇬🇧",
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
        "result_title": "📋 Analysis result",
        "urg_high": "Emergency 🔴", "urg_medium": "Appointment needed 🟡", "urg_low": "Mild 🟢",
        "forced_high": "⚠️ Urgency raised automatically based on red-flag symptoms.",
        "low_conf": "⚖️ Low confidence — a doctor visit is recommended.",
        "possible": "🩺 Possible conditions",
        "medwarn": "💊 Medication warnings",
        "medwarn_note": "Awareness only — don't stop your prescribed medication without consulting your doctor.",
        "ml_title": "📊 Machine learning model analysis",
        "recs": "📌 Recommendations", "danger": "🚨 Danger signs", "when": "🕑 When to see a doctor",
        "home_care": "🏠 Home care", "med_guid": "💊 Medication guidance", "q_doc": "❓ Ask your doctor",
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
        "no_mic": "Your browser does not support voice input.",
        "locating": "Locating you... 📍",
        "loc_err_f": "Could not access your location — please enable location services.",
        "loc_err_m": "Could not access your location — please enable location services.",
        "no_hosp": "No nearby hospitals found.",
        "hosp_title": "🏥 Nearest hospitals", "map": "🗺️ Open in map", "km": " km",
        "sp_result": "Analysis result: severity ", "sp_possible": "Possible conditions: ",
        "sp_recs": "Recommendations:", "sp_medwarn": "Medication warnings:", "sp_danger": "Danger signs: ",
        "sp_when": "When to see a doctor: ", "sp_home": "Home care: ",
        "sp_medguid": "Medication guidance: ", "sp_qdoc": "Questions for your doctor: ",
    },
}


def chat_page():
    ar = _lang() == "ar"
    if ar:
        syms = [
            "🤕 صداع", "🤒 حمى", "😷 سعال", "🫀 ألم في الصدر", "🤢 غثيان", "😴 تعب وإرهاق",
            "🫁 ضيق التنفس", "💫 دوار", "🦴 ألم المفاصل", "😖 ألم في البطن", "🥶 قشعريرة", "👁️ احمرار العيون",
            "🦵 ألم في الرجل", "😣 ألم الحلق", "🖐️ حكة",
        ]
        durs = ["⏰ أقل من 24 ساعة", "📅 1-3 أيام", "📅 4-7 أيام", "🗓️ 1-2 أسبوع", "🗓️ أكثر من أسبوعين", "📆 أكثر من شهر"]
        sevs = [("1", "1️⃣ خفيف جداً"), ("2", "2️⃣ معتدل"), ("3", "3️⃣ متوسط"), ("4", "4️⃣ شديد"), ("5", "5️⃣ حرج جداً")]
        conds = ["لا يوجد أمراض سابقة", "سكري", "ضغط الدم", "أمراض قلب", "ربو"]
    else:
        syms = [
            "🤕 Headache", "🤒 Fever", "😷 Cough", "🫀 Chest pain", "🤢 Nausea", "😴 Fatigue",
            "🫁 Shortness of breath", "💫 Dizziness", "🦴 Joint pain", "😖 Stomach pain", "🥶 Chills", "👁️ Eye redness",
            "🦵 Leg pain", "😣 Sore throat", "🖐️ Itching",
        ]
        durs = ["⏰ Less than 24 hours", "📅 1-3 days", "📅 4-7 days", "🗓️ 1-2 weeks", "🗓️ More than 2 weeks", "📆 More than a month"]
        sevs = [("1", "1️⃣ Very mild"), ("2", "2️⃣ Mild"), ("3", "3️⃣ Moderate"), ("4", "4️⃣ Severe"), ("5", "5️⃣ Critical")]
        conds = ["No previous conditions", "Diabetes", "High blood pressure", "Heart disease", "Asthma"]

    body = """
    <div class="chat-wrap">
      <div class="chat-head">
        <div class="avatar">🏥</div>
        <div><h3>SymptoSense</h3><p id="headP"></p></div>
        <button id="spkBtn" class="spk-btn" onclick="toggleSpeak()" title="__SPEAK_TITLE__">__SPEAK_ON__</button>
      </div>
      <div class="chat-body" id="chatBody"></div>
      <div class="chat-options" id="chatOptions"></div>
      <div class="chat-input" id="chatInput" style="display:none;">
        <input type="text" id="textInp" placeholder="__INPUT_PH__" autocomplete="off">
        <button onclick="toggleMic()" id="micBtn" title="__MIC_TITLE__">🎤</button>
        <button onclick="submitText()">__SEND__</button>
      </div>
    </div>
    <div class="muted" style="text-align:center;margin-top:10px;">__MUTED__</div>

    <script>
    const T = __T__;
    const LANG = "__LANG__";
    function TT(k) { return T[k] || k; }
    const SYMS = __SYMS__;
    const DURS = __DURS__;
    const SEVS = __SEVS__;
    const CONDS = __CONDS__;
    document.getElementById('headP').textContent = TT('head_p');
    const state = { age:null, gender:null, symptoms:[], duration:null, severity:null, conditions:null, medications:null, notes:null, step:'age' };
    const bodyEl = document.getElementById('chatBody');
    const optsEl = document.getElementById('chatOptions');
    const inpEl = document.getElementById('chatInput');
    const textInp = document.getElementById('textInp');
    textInp.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') { e.preventDefault(); submitText(); }
    });

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
      const clean = s => String(s || '').replace(/[^\u0600-\u06FF\w\s.,!?()\-%/،؟]/g, ' ').replace(/\s{2,}/g, ' ').trim();
      const t = clean(txt);
      if (!t) return;
      speechSynthesis.cancel();
      const uu = new SpeechSynthesisUtterance(t);
      uu.lang = LANG === 'en' ? 'en-US' : 'ar-SA';
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
    function clearOpts() { optsEl.innerHTML = ''; }
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
      textInp.focus();
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

    function askAge() {
      state.step = 'age';
      add(TT('age'), 'bot');
      showText(TT('age_ph'));
    }
    function askGender() {
      state.step = 'gender';
      add(TT('gender'), 'bot');
      showOpts([
        {label:TT('male'), fn:()=>{ state.gender='m'; add(TT('male'),'user'); askSymptoms(); }},
        {label:TT('female'), fn:()=>{ state.gender='f'; add(TT('female'),'user'); askSymptoms(); }}
      ]);
    }
    function G(f, m) { return state.gender === 'm' ? m : f; }
    function askSymptoms() {
      state.step = 'symptoms';
      add(G(TT('syms_f'), TT('syms_m')), 'bot');
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
      items.push({label:TT('write_yourself'), fn:()=>{
        add(G(TT('custom_f'), TT('custom_m')), 'bot');
        showText(TT('sym_ph'));
      }});
      items.push({label:TT('done'), cls:'danger', fn:()=>{
        if (!state.symptoms.length) { add(G(TT('atleast_f'), TT('atleast_m')), 'bot'); return; }
        add(TT('chosen') + state.symptoms.join(LANG === 'en' ? ', ' : '، '), 'user');
        askDuration();
      }});
      showOpts(items);
    }
    function askDuration() {
      state.step = 'duration';
      add(TT('duration'), 'bot');
      showOpts(DURS.map(d=>({label:d, fn:()=>{ state.duration=d; add(d,'user'); askSeverity(); }})));
    }
    function askSeverity() {
      state.step = 'severity';
      add(TT('severity'), 'bot');
      showOpts(SEVS.map(([v,l])=>({label:l, fn:()=>{ state.severity=v; add(l,'user'); askConditions(); }})));
    }
    function askConditions() {
      state.step = 'conditions';
      add(G(TT('conditions_f'), TT('conditions_m')), 'bot');
      const items = CONDS.map(c=>({label:c, fn:()=>{ state.conditions=c; add(c,'user'); askMeds(); }}));
      items.push({label:TT('other_diseases'), fn:()=>{ add(G(TT('other_diseases_f'), TT('other_diseases_m')), 'bot'); showText(TT('cond_ph')); }});
      showOpts(items);
    }
    function askMeds() {
      state.step = 'medications';
      add(G(TT('meds_f'), TT('meds_m')), 'bot');
      showOpts([{label:TT('skip'), fn:()=>{ add(TT('skip'),'user'); state.medications=''; askNotes(); }}]);
      showText(TT('meds_ph'), true);
    }
    function askNotes() {
      state.step = 'notes';
      add(G(TT('notes_f'), TT('notes_m')), 'bot');
      showOpts([{label:TT('skip'), fn:()=>{ add(TT('skip'),'user'); state.notes=''; runAnalysis(); }}]);
      showText(TT('notes_ph'), true);
    }
    function submitText() {
      const v = send();
      if (!v) return;
      if (state.step === 'age') {
        const n = parseInt(v);
        if (!n || n < 1 || n > 120) { add(TT('age_invalid'), 'bot'); showText(TT('age_ph')); return; }
        state.age = n; askGender();
      } else if (state.step === 'symptoms') {
        state.symptoms.push(v);
        add(G(TT('added_f'), TT('added_m')), 'bot');
        askSymptoms();
      } else if (state.step === 'conditions') {
        state.conditions = v; askMeds();
      } else if (state.step === 'medications') {
        state.medications = v; askNotes();
      } else if (state.step === 'notes') {
        state.notes = v; runAnalysis();
      } else if (state.step === 'followup') {
        submitFollowup(v);
      }
    }
    async function runAnalysis() {
      hideText();
      clearOpts();
      add(TT('analyzing'), 'bot');
      try {
        const payload = Object.assign({}, state, {lang: LANG});
        const r = await fetch('/api/analyze', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify(payload)
        });
        const d = await r.json();
        if (d.ok) renderResult(d); else add(TT('err') + (d.error||'?'), 'bot');
      } catch(e) { add(TT('conn_err'), 'bot'); }
    }
    function esc(s) { const div=document.createElement('div'); div.textContent=s||''; return div.innerHTML; }
    function NAME(x, arKey, enKey) { return LANG === 'en' ? (x[enKey] || x[arKey]) : (x[arKey] || x[enKey]); }
    function pillLabel(u) { return u==='high' ? TT('urg_high') : (u==='medium' ? TT('urg_medium') : TT('urg_low')); }
    function renderResult(d) {
      lastResult = d;
      const u = d.urgency;
      const pill = pillLabel(u);
      const pcls = 'urg-' + u;
      let h = '<div class="sec-title">' + TT('result_title') + '</div>';
      h += '<div class="pill ' + pcls + '" style="margin:4px 0 10px;">' + pill + '</div>';
      h += '<div class="res-sec"><i>' + esc(d.personal_note) + '</i></div>';
      if (d.rule_forced_high) h += '<div class="warn" style="margin:8px 0;">' + TT('forced_high') + '</div>';
      if (d.low_confidence) h += '<div class="muted">' + TT('low_conf') + '</div>';

      if (d.possible_conditions) h += '<div class="sec-title">' + TT('possible') + '</div><div class="res-sec">' + esc(d.possible_conditions) + '</div>';
      if (d.med_warnings && d.med_warnings.length) {
        h += '<div class="sec-title">' + TT('medwarn') + '</div>';
        d.med_warnings.forEach(m => h += '<div class="rec-item"><b>' + esc(NAME(m, 'name_ar', 'name_en')) + '</b>: ' + esc(NAME(m, 'warning_ar', 'warning_en')) + '</div>');
        h += '<div class="muted">' + TT('medwarn_note') + '</div>';
      }
      if (d.ml_predictions && d.ml_predictions.length) {
        h += '<div class="sec-title">' + TT('ml_title') + '</div>';
        d.ml_predictions.forEach(p => {
          h += '<div style="font-size:13px;">' + esc(NAME(p, 'name_ar', 'name_en')) + ' (' + Math.round(p.probability*100) + '%)</div>';
          h += '<div class="bar-bg"><div class="bar-fill" style="width:' + Math.round(p.probability*100) + '%"></div></div>';
        });
      }
      if (d.recommendations && d.recommendations.length) {
        h += '<div class="sec-title">' + TT('recs') + '</div>';
        d.recommendations.forEach(r => {
          h += '<div class="rec-item">' + esc(r.tip);
          if (r.source && r.url) h += '<div class="src">🔗 <a href="' + esc(r.url) + '" target="_blank">' + esc(r.source) + '</a></div>';
          h += '</div>';
        });
      }
      if (d.danger_signs) h += '<div class="sec-title">' + TT('danger') + '</div><div class="res-sec">' + esc(d.danger_signs) + '</div>';
      if (d.when_to_seek_care) h += '<div class="sec-title">' + TT('when') + '</div><div class="res-sec">' + esc(d.when_to_seek_care) + '</div>';
      if (d.home_care) h += '<div class="sec-title">' + TT('home_care') + '</div><div class="res-sec">' + esc(d.home_care) + '</div>';
      if (d.medication_guidance) h += '<div class="sec-title">' + TT('med_guid') + '</div><div class="res-sec">' + esc(d.medication_guidance) + '</div>';
      if (d.questions_for_doctor) h += '<div class="sec-title">' + TT('q_doc') + '</div><div class="res-sec">' + esc(d.questions_for_doctor) + '</div>';
      addHtml('<div class="result">' + h + '</div>', 'result');
      addHtml('<div style="margin-top:10px;text-align:center;"><button class="opt" onclick="speakResult()">' + TT('listen_all') + '</button></div>', 'result');
      addHtml('<div class="sec-title">' + TT('fb_title') + '</div><div style="display:flex;gap:6px;flex-wrap:wrap;justify-content:center;">' +
        '<button class="opt" data-v="1" onclick="fb(this.dataset.v)">' + TT('fb_excellent') + '</button>' +
        '<button class="opt" data-v="2" onclick="fb(this.dataset.v)">' + TT('fb_good') + '</button>' +
        '<button class="opt" data-v="3" onclick="fb(this.dataset.v)">' + TT('fb_ok') + '</button>' +
        '<button class="opt" data-v="4" onclick="fb(this.dataset.v)">' + TT('fb_no') + '</button></div>' +
        '<div id="fbMsg" style="margin-top:8px;text-align:center;font-weight:600;color:#0f766e;"></div>', 'result');
      showOpts([
        {label:TT('ask_more'), fn:askFollowup},
        {label:TT('hospitals'), fn:findHospitals},
        {label:TT('new'), fn:restart},
        {label:TT('share'), fn:()=>{
          try { navigator.share({title:'SymptoSense', text:TT('share_txt') + pill}) } catch(e) {} }
        }
      ]);
    }
    let lastResult = null;
    function askFollowup() {
      state.step = 'followup';
      add(G(TT('followup_f'), TT('followup_m')), 'bot');
      showText(TT('followup_ph'));
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
      const clean = s => String(s || '').replace(/[^\u0600-\u06FF\w\s.,!?()\-%/،؟]/g, ' ').replace(/\s{2,}/g, ' ').trim();
      const d = lastResult;
      const u = d.urgency;
      const pill = u==='high' ? TT('urg_high') : (u==='medium' ? TT('urg_medium') : TT('urg_low'));
      let parts = [];
      parts.push(TT('sp_result') + clean(pill) + '.');
      if (d.personal_note) parts.push(clean(d.personal_note));
      if (d.possible_conditions) parts.push(TT('sp_possible') + clean(d.possible_conditions));
      if (d.recommendations && d.recommendations.length) {
        parts.push(TT('sp_recs'));
        d.recommendations.forEach(r => { if (r.tip) parts.push('- ' + clean(r.tip)); });
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
    let recog = null, micOn = false;
    function toggleMic() {
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SR) { add(TT('no_mic'), 'bot'); return; }
      if (micOn) { recog.stop(); return; }
      recog = new SR();
      recog.lang = LANG === 'en' ? 'en-US' : 'ar-SA';
      recog.interimResults = false;
      recog.maxAlternatives = 1;
      recog.onstart = () => { micOn = true; document.getElementById('micBtn').textContent = '🔴'; };
      recog.onend = () => { micOn = false; document.getElementById('micBtn').textContent = '🎤'; };
      recog.onresult = (e) => {
        const said = e.results[0][0].transcript;
        textInp.value = said;
        submitText();
      };
      recog.onerror = () => { micOn = false; document.getElementById('micBtn').textContent = '🎤'; };
      recog.start();
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
      Object.assign(state, {age:null,gender:null,symptoms:[],duration:null,severity:null,conditions:null,medications:null,notes:null});
      bodyEl.innerHTML = '';
      add(TT('welcome'), 'bot');
      askAge();
    }
    restart();
    </script>
    """
    return _page(_t("title_chat"), body
        .replace("__T__", json.dumps(CHAT["ar"] if ar else CHAT["en"], ensure_ascii=False))
        .replace("__LANG__", "ar" if ar else "en")
        .replace("__SYMS__", json.dumps(syms, ensure_ascii=False))
        .replace("__DURS__", json.dumps(durs, ensure_ascii=False))
        .replace("__SEVS__", json.dumps(sevs, ensure_ascii=False))
        .replace("__CONDS__", json.dumps(conds, ensure_ascii=False))
        .replace("__SPEAK_ON__", CHAT["ar" if ar else "en"]["speak_on"])
        .replace("__SPEAK_TITLE__", CHAT["ar" if ar else "en"]["speak_title"])
        .replace("__INPUT_PH__", CHAT["ar" if ar else "en"]["input_ph"])
        .replace("__MIC_TITLE__", CHAT["ar" if ar else "en"]["mic_title"])
        .replace("__SEND__", CHAT["ar" if ar else "en"]["send"])
        .replace("__MUTED__", CHAT["ar" if ar else "en"]["muted"]))



# ---------------------------------------------------------------- content pages i18n
CT = {
    "ar": {
        "blood_h": "🩸 تحليل فحص الدم (CBC)",
        "blood_sub": "ارفع صورة فحص الدم أو ملف PDF وسنستخرج القيم ونحللها ونرسم المخطط. (HGB, WBC, RBC, HCT, MCV, MCH, MCHC, PLT...)",
        "blood_gender": "الجنس", "blood_age": "العمر (اختياري — للطفل)",
        "blood_female": "أنثى", "blood_male": "ذكر", "blood_child": "طفل",
        "blood_age_ph": "مثال: 5",
        "blood_drop": "📂 اضغط هنا لاختيار صورة أو PDF",
        "blood_btn": "تحليل ⚡",
        "blood_first": "اختر ملف أولاً.",
        "blood_reading": "جاري قراءة الفحص...",
        "blood_err": "تعذر التحليل",
        "meds_h": "💊 فحص الأدوية والتفاعلات",
        "meds_sub": "اكتب الأدوية التي تتناولها (مع أي مرض مزمن) لنفحصها ضد قاعدة بيانات التحذيرات الدوائية.",
        "meds_label": "الأدوية / الحالة الصحية",
        "meds_ph": "مثال: فولتارين، وارفارين، ضغط الدم",
        "meds_btn": "فحص 🔍",
        "rem_h": "⏰ التذكير الدوائي",
        "rem_sub": "احفظ مواعيد أدويتك وذكّرك بها المتصفح كل يوم (الإشعارات تعمل ما دامت الصفحة مفتوحة).",
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
        "fa_h": "🚑 الإسعافات الأولية",
        "fa_sub": "اختر الحالة لعرض الإرشادات الإسعافية خطوة بخطوة.",
        "fa_warn": "⚠️ في الحالات الحرجة (توقف تنفس، نزيف حاد، فقدان وعي) اتصل بالإسعاف <b>997</b> فوراً.",
        "fa_video": "▶ شاهد فيديو توضيحي",
        "tips_h": "🍃 نصيحة صحية", "tips_btn": "نصيحة أخرى 🔄",
        "relax_h": "🧘 تمرين الاسترخاء والتنفس",
        "br_in": "استنشق 🌬️", "br_hold": "احبس 🧘", "br_out": "زفر 😮‍💨",
        "em_h": "🚨 أرقام الطوارئ في السعودية",
        "em_sub": "احتفظ بهذه الأرقام، وأجرها فوراً عند الحاجة.",
        "em_red": "الهلال الأحمر (إسعاف)", "em_unified": "الطوارئ الموحد",
        "em_937": "استشارات وزارة الصحة (24/7)", "em_police": "الشرطة", "em_civil": "الدفاع المدني",
        "em_warn": "⚠️ في حالة الأعراض الخطرة (ألم صدر حاد، صعوبة تنفس، نزيف حاد، فقدان وعي) اتصل بالإسعاف <b>997</b> فوراً ولا تنتظر.",
        "em_geo": "مستشفى قريب منك 📍",
        "em_geo_btn": "🔍 اعرض أقرب المستشفيات",
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
    },
    "en": {
        "blood_h": "🩸 Blood Test Analysis (CBC)",
        "blood_sub": "Upload a photo of your blood test or a PDF; we'll extract the values, analyze them, and draw the chart. (HGB, WBC, RBC, HCT, MCV, MCH, MCHC, PLT...)",
        "blood_gender": "Gender", "blood_age": "Age (optional — for children)",
        "blood_female": "Female", "blood_male": "Male", "blood_child": "Child",
        "blood_age_ph": "Example: 5",
        "blood_drop": "📂 Click here to choose a photo or PDF",
        "blood_btn": "Analyze ⚡",
        "blood_first": "Choose a file first.",
        "blood_reading": "Reading the test...",
        "blood_err": "Analysis failed",
        "meds_h": "💊 Medication & Interaction Checker",
        "meds_sub": "Enter the medications you take (with any chronic condition) to check them against the medication warnings database.",
        "meds_label": "Medications / Health condition",
        "meds_ph": "Example: Voltaren, Warfarin, high blood pressure",
        "meds_btn": "Check 🔍",
        "rem_h": "⏰ Medication Reminder",
        "rem_sub": "Save your medication times and the browser will remind you daily (notifications work while the page is open).",
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
        "fa_h": "🚑 First Aid",
        "fa_sub": "Choose a condition to view step-by-step first aid instructions.",
        "fa_warn": "⚠️ In critical cases (stopped breathing, heavy bleeding, loss of consciousness) call an ambulance at <b>997</b> immediately.",
        "fa_video": "▶ Watch a demo video",
        "tips_h": "🍃 Health tip", "tips_btn": "Another tip 🔄",
        "relax_h": "🧘 Relaxation & Breathing Exercise",
        "br_in": "Breathe in 🌬️", "br_hold": "Hold 🧘", "br_out": "Breathe out 😮‍💨",
        "em_h": "🚨 Emergency Numbers in Saudi Arabia",
        "em_sub": "Keep these numbers and call them immediately when needed.",
        "em_red": "Saudi Red Crescent (Ambulance)", "em_unified": "Unified Emergency",
        "em_937": "Ministry of Health consultations (24/7)", "em_police": "Police", "em_civil": "Civil Defense",
        "em_warn": "⚠️ For dangerous symptoms (severe chest pain, difficulty breathing, heavy bleeding, loss of consciousness) call an ambulance at <b>997</b> immediately; don't wait.",
        "em_geo": "A hospital near you 📍",
        "em_geo_btn": "🔍 Show nearest hospitals",
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
    },
}


# ---------------------------------------------------------------- blood
def blood_page():
    t = CT["en" if _lang() == "en" else "ar"]
    body = """
    <div class="card">
      <h2>__BH__</h2>
      <p class="muted">__BSUB__</p>
      <div style="margin-top:16px;">
        <div class="grid2">
          <div><label class="lbl">__BGENDER__</label><select class="inp" id="bg"><option value="f">__BF__</option><option value="m">__BM__</option><option value="c">__BC__</option></select></div>
          <div><label class="lbl">__BAGE__</label><input class="inp" type="number" id="ba" placeholder="__BAGEPH__"></div>
        </div>
        <div class="drop" id="drop">__BDROP__<br><span class="muted">JPG / PNG / PDF</span></div>
        <input type="file" id="fileInp" accept="image/*,application/pdf" style="display:none;">
        <button class="btn" onclick="uploadBlood()">__BBTN__</button>
        <div id="bloodRes" style="margin-top:18px;"></div>
      </div>
    </div>
    <script>
    const T = __PT__;
    function TT(k) { return T[k] || k; }
    const drop = document.getElementById('drop');
    const fileInp = document.getElementById('fileInp');
    drop.onclick = () => fileInp.click();
    drop.ondragover = e => { e.preventDefault(); drop.classList.add('on'); };
    drop.ondragleave = () => drop.classList.remove('on');
    drop.ondrop = e => { e.preventDefault(); drop.classList.remove('on'); if (e.dataTransfer.files[0]) fileInp.files = e.dataTransfer.files; };
    async function uploadBlood() {
      const f = fileInp.files[0];
      if (!f) { document.getElementById('bloodRes').innerHTML = '<div class="warn">' + TT('blood_first') + '</div>'; return; }
      const box = document.getElementById('bloodRes');
      box.innerHTML = '<div class="bubble bot" style="max-width:100%">' + TT('blood_reading') + ' <span class="spin"></span></div>';
      const fd = new FormData();
      fd.append('file', f);
      fd.append('gender', document.getElementById('bg').value);
      fd.append('age', document.getElementById('ba').value);
      const r = await fetch('/api/blood', { method:'POST', body: fd });
      const d = await r.json();
      if (!d.ok) { box.innerHTML = '<div class="warn">' + (d.error||TT('blood_err')) + '</div>'; return; }
      let h = '<div class="result bubble bot" style="max-width:100%">' + d.text_html;
      if (d.chart) h += '<div style="text-align:center;margin-top:12px;"><img src="data:image/png;base64,' + d.chart + '" style="max-width:100%;border-radius:10px;"></div>';
      h += '</div>';
      box.innerHTML = h;
    }
    </script>
    """
    repl = [
        ("__PT__", json.dumps(t, ensure_ascii=False)),
        ("__BH__", t["blood_h"]), ("__BSUB__", t["blood_sub"]),
        ("__BGENDER__", t["blood_gender"]), ("__BAGE__", t["blood_age"]),
        ("__BF__", t["blood_female"]), ("__BM__", t["blood_male"]), ("__BC__", t["blood_child"]),
        ("__BAGEPH__", t["blood_age_ph"]), ("__BDROP__", t["blood_drop"]), ("__BBTN__", t["blood_btn"]),
    ]
    for k, v in repl:
        body = body.replace(k, v)
    return _page(_t("title_blood"), body)


# ---------------------------------------------------------------- meds
def meds_page():
    t = CT["en" if _lang() == "en" else "ar"]
    body = """
    <div class="card">
      <h2>__MH__</h2>
      <p class="muted">__MSUB__</p>
      <label class="lbl">__MLABEL__</label>
      <textarea class="inp" id="medText" rows="3" placeholder="__MPH__"></textarea>
      <div style="margin-top:12px;"><button class="btn" onclick="checkMeds()">__MBTN__</button></div>
      <div id="medRes" style="margin-top:16px;"></div>
    </div>
    <div class="card" style="margin-top:16px;">
      <h2>__RH__</h2>
      <p class="muted">__RSUB__</p>
      <div class="grid2">
        <div><label class="lbl">__RNAME__</label><input class="inp" id="remName" placeholder="__RNAMEPH__"></div>
        <div><label class="lbl">__RTIMES__</label><input class="inp" id="remTimes" placeholder="__RTIMESPH__"></div>
      </div>
      <div style="margin-top:12px;"><button class="btn" onclick="addReminder()">__RSAVE__</button></div>
      <div id="remMsg" style="margin-top:8px;font-weight:600;color:#0f766e;"></div>
      <div id="remList" style="margin-top:12px;"></div>
    </div>
    <div class="warn">__MWARN__</div>
    <script>
    const T = __PT__;
    function TT(k) { return T[k] || k; }
    function enName(w) { return (T['meds_col'] === 'Medication') ? (w.name_en || w.name_ar) : (w.name_ar || w.name_en); }
    function enWarn(w) { return (T['meds_col'] === 'Medication') ? (w.warning_en || w.warning_ar) : (w.warning_ar || w.warning_en); }
    async function checkMeds() {
      const tval = document.getElementById('medText').value.trim();
      const box = document.getElementById('medRes');
      if (!tval) { box.innerHTML = '<div class="warn">' + TT('meds_write') + '</div>'; return; }
      box.innerHTML = '<div class="bubble bot">' + TT('meds_checking') + ' <span class="spin"></span></div>';
      const r = await fetch('/api/meds', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text:tval}) });
      const d = await r.json();
      if (!d.warnings.length) { box.innerHTML = '<div class="bubble bot">' + TT('meds_none') + '</div>'; return; }
      let h = '<table class="tbl"><tr><th>' + TT('meds_col') + '</th><th>' + TT('warn_col') + '</th></tr>';
      d.warnings.forEach(w => h += '<tr><td><b>' + esc(enName(w)) + '</b></td><td>' + esc(enWarn(w)) + '</td></tr>');
      h += '</table>';
      box.innerHTML = '<div class="bubble bot" style="max-width:100%">' + h + '</div>';
    }
    function esc(s) { const div=document.createElement('div'); div.textContent=s||''; return div.innerHTML; }
    function loadReminders() { try { return JSON.parse(localStorage.getItem('ss_reminders') || '[]'); } catch(e) { return []; } }
    function saveReminders(list) { localStorage.setItem('ss_reminders', JSON.stringify(list)); }
    function renderReminders() {
      const list = loadReminders();
      const box = document.getElementById('remList');
      if (!list.length) { box.innerHTML = '<div class="muted">' + TT('no_rem') + '</div>'; return; }
      let h = '<table class="tbl"><tr><th>' + TT('rem_name') + '</th><th>' + TT('rem_times') + '</th><th></th></tr>';
      list.forEach((r, i) => {
        h += '<tr><td><b>' + esc(r.name) + '</b></td><td>' + r.times.join(T['meds_col'] === 'Medication' ? ', ' : '، ') + '</td><td><button class="opt" onclick="removeRem(' + i + ')">' + TT('del') + '</button></td></tr>';
      });
      h += '</table>';
      box.innerHTML = h;
    }
    function addReminder() {
      const name = document.getElementById('remName').value.trim();
      const tval = document.getElementById('remTimes').value.trim();
      const box = document.getElementById('remMsg');
      if (!name) { box.textContent = TT('name_first'); return; }
      const times = tval.split(/[,،\\s]+/).filter(Boolean);
      if (!times.length) { box.textContent = TT('times_ph_err'); return; }
      if (!('Notification' in window)) { box.textContent = TT('no_notif'); return; }
      Notification.requestPermission().then(perm => {
        if (perm !== 'granted') { box.textContent = TT('enable_notif'); return; }
        const list = loadReminders();
        list.push({ name: name, times: times });
        saveReminders(list);
        document.getElementById('remName').value = '';
        document.getElementById('remTimes').value = '';
        box.textContent = TT('saved');
        renderReminders();
      });
    }
    function removeRem(i) {
      const list = loadReminders();
      list.splice(i, 1);
      saveReminders(list);
      renderReminders();
    }
    function checkTimes() {
      const now = new Date();
      const cur = ('0' + now.getHours()).slice(-2) + ':' + ('0' + now.getMinutes()).slice(-2);
      const list = loadReminders();
      list.forEach(r => {
        r.times.forEach(tm => {
          if (tm === cur && r.last !== cur) {
            r.last = cur;
            if (('Notification' in window) && Notification.permission === 'granted') {
              new Notification(TT('rem_notif_t'), { body: TT('rem_notif_b') + r.name });
            }
            saveReminders(list);
          }
        });
      });
    }
    setInterval(checkTimes, 30000);
    renderReminders();
    </script>
    """
    repl = [
        ("__PT__", json.dumps(t, ensure_ascii=False)),
        ("__MH__", t["meds_h"]), ("__MSUB__", t["meds_sub"]), ("__MLABEL__", t["meds_label"]),
        ("__MPH__", t["meds_ph"]), ("__MBTN__", t["meds_btn"]),
        ("__RH__", t["rem_h"]), ("__RSUB__", t["rem_sub"]),
        ("__RNAME__", t["rem_name"]), ("__RNAMEPH__", t["rem_name_ph"]),
        ("__RTIMES__", t["rem_times"]), ("__RTIMESPH__", t["rem_times_ph"]),
        ("__RSAVE__", t["rem_save"]), ("__MWARN__", t["meds_warn"]),
    ]
    for k, v in repl:
        body = body.replace(k, v)
    return _page(_t("title_meds"), body)


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
    <div class="card" style="text-align:center;">
      <h2>__TIPSH__</h2>
      <div id="tipBox" style="font-size:17px;line-height:2;padding:20px;background:#f0f7f6;border-radius:12px;margin:14px 0;"></div>
      <button class="btn" onclick="loadTip()">__TIPSB__</button>
    </div>
    <script>
    async function loadTip() {
      const box = document.getElementById('tipBox');
      box.innerHTML = '... <span class="spin"></span>';
      const r = await fetch('/api/tip');
      const d = await r.json();
      box.innerHTML = esc(d.tip);
    }
    function esc(s) { const div=document.createElement('div'); div.textContent=s||''; return div.innerHTML; }
    loadTip();
    </script>
    """
    body = body.replace("__TIPSH__", t["tips_h"]).replace("__TIPSB__", t["tips_btn"])
    return _page(_t("title_tips"), body)


# ---------------------------------------------------------------- relax
def relax_page():
    lang = "en" if _lang() == "en" else "ar"
    txt = wellbeing.relax_guide(lang)
    t = CT["en" if _lang() == "en" else "ar"]
    body = """
    <div class="card">
      <h2>__RELAXH__</h2>
      <div style="font-size:16px;line-height:2;background:#f0f7f6;border-radius:12px;padding:20px;white-space:pre-wrap;">__TXT__</div>
      <div style="text-align:center;margin-top:16px;"><div id="breathBox" style="font-size:30px;font-weight:800;color:#0f766e;height:70px;display:flex;align-items:center;justify-content:center;"></div></div>
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
    <div class="card">
      <h2>__EMH__</h2>
      <p class="muted">__EMSUB__</p>
      <div class="features" style="margin-top:14px;">
        <div class="feature"><div class="ic">🚑</div><h3>__EMRED__</h3><p><b style="font-size:26px;color:#dc2626;">997</b></p></div>
        <div class="feature"><div class="ic">📞</div><h3>__EMUNI__</h3><p><b style="font-size:26px;color:#dc2626;">911</b></p></div>
        <div class="feature"><div class="ic">🩺</div><h3>__EM937__</h3><p><b style="font-size:26px;color:#0f766e;">937</b></p></div>
        <div class="feature"><div class="ic">🚓</div><h3>__EMPOL__</h3><p><b style="font-size:26px;color:#0f766e;">999</b></p></div>
        <div class="feature"><div class="ic">🚒</div><h3>__EMCIV__</h3><p><b style="font-size:26px;color:#0f766e;">998</b></p></div>
      </div>
      <div class="warn" style="margin-top:8px;">__EMWARN__</div>
    </div>
    <div class="card" style="margin-top:18px;">
      <h2>__EMGEO__</h2>
      <p style="margin-top:6px;text-align:center;"><button class="btn" onclick="nearMe()">__EMGEOBTN__</button></p>
      <div id="geoMsg" style="text-align:center;margin-top:10px;font-weight:700;color:#0f766e;"></div>
      <div id="geoList" style="margin-top:12px;"></div>
    </div>
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
        ("__EMRED__", t["em_red"]), ("__EMUNI__", t["em_unified"]),
        ("__EM937__", t["em_937"]), ("__EMPOL__", t["em_police"]),
        ("__EMCIV__", t["em_civil"]), ("__EMWARN__", t["em_warn"]),
        ("__EMGEO__", t["em_geo"]), ("__EMGEOBTN__", t["em_geo_btn"]),
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
    t = CT["en" if _lang() == "en" else "ar"]
    body = """
    <div class="card">
      <h2>__CIH__</h2>
      <p class="muted">__CISUB__</p>
      <div style="margin-top:14px;text-align:center;">
        <button class="btn ghost" onclick="ci(1)">😞 1</button>
        <button class="btn ghost" onclick="ci(2)">😕 2</button>
        <button class="btn ghost" onclick="ci(3)">😐 3</button>
        <button class="btn ghost" onclick="ci(4)">🙂 4</button>
        <button class="btn ghost" onclick="ci(5)">😊 5</button>
      </div>
      <div id="ciMsg" style="margin-top:10px;font-weight:700;color:#0f766e;text-align:center;"></div>
      <div id="ciChart" style="margin-top:20px;text-align:center;"></div>
    </div>
    <script>
    const T = __PT__;
    function TT(k) { return T[k] || k; }
    async function ci(rating) {
      const r = await fetch('/api/checkin', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({rating: rating})});
      const d = await r.json();
      if (d.ok) { document.getElementById('ciMsg').textContent = TT('ci_saved'); loadChart(); }
      else document.getElementById('ciMsg').textContent = TT('ci_err') + (d.error || '?');
    }
    async function loadChart() {
      const r = await fetch('/api/checkin');
      const d = await r.json();
      const box = document.getElementById('ciChart');
      if (!d.ok) { box.innerHTML = '<div class="muted">' + TT('ci_chart_err') + '</div>'; return; }
      if (!d.rows.length) { box.innerHTML = '<div class="muted">' + TT('ci_empty') + '</div>'; return; }
      box.innerHTML = '<img src="' + d.chart + '" alt="' + TT('ci_alt') + '" style="max-width:100%;border-radius:12px;box-shadow:0 4px 14px rgba(0,0,0,.08);">';
    }
    loadChart();
    </script>
    """
    body = body.replace("__PT__", json.dumps(t, ensure_ascii=False))
    body = body.replace("__CIH__", t["ci_h"]).replace("__CISUB__", t["ci_sub"])
    return _page(_t("title_checkin"), body)


# ---------------------------------------------------------------- profile
def profile_page():
    db.init_db()
    t = L["en" if _lang() == "en" else "ar"]
    p = db.load_profile(_user_id()) or {}
    gen_sel = {
        "male": '<option value="male" selected>' + t["pr_g_male"] + '</option><option value="female">' + t["pr_g_female"] + '</option>',
        "female": '<option value="male">' + t["pr_g_male"] + '</option><option value="female" selected>' + t["pr_g_female"] + '</option>',
        "": '<option value="male">' + t["pr_g_male"] + '</option><option value="female">' + t["pr_g_female"] + '</option>',
    }.get(p.get("gender", ""), "")
    def esc(v):
        return (v or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    body = """
    <div class="card" style="max-width:560px;margin:0 auto;">
      <h2>__PRH__</h2>
      <p class="muted">__PRSUB__</p>
      <form id="pf" style="margin-top:14px;display:flex;flex-direction:column;gap:12px;">
        <div class="pr-grid">
          <div><label>__PRAGE__</label><input name="age" type="number" min="1" max="120" value="__AGE__" placeholder="18"></div>
          <div><label>__PRGEND__</label><select name="gender">__GENSEL__</select></div>
        </div>
        <div><label>__PRCOND__</label><input name="conditions" value="__COND__" placeholder="e.g. diabetes, asthma"></div>
        <div><label>__PRMEDS__</label><input name="medications" value="__MEDS__" placeholder="e.g. Metformin"></div>
        <div><label>__PRALL__</label><input name="allergies" value="__ALL__" placeholder="e.g. penicillin"></div>
        <button class="btn" type="submit" style="width:100%;">__PRSAVE__</button>
        <div id="pfMsg" style="text-align:center;font-weight:700;color:#0f766e;"></div>
      </form>
    </div>
    <script>
    const P = __PT__;
    document.getElementById('pf').addEventListener('submit', async function(e){
      e.preventDefault();
      const f = e.target;
      const r = await fetch('/api/profile', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({
        age: f.age.value, gender: f.gender.value, conditions: f.conditions.value,
        medications: f.medications.value, allergies: f.allergies.value, lang: P.__LANG__
      })});
      const d = await r.json();
      const m = document.getElementById('pfMsg');
      m.textContent = d.ok ? P.pr_saved : P.pr_err + (d.error ? ' (' + d.error + ')' : '');
    });
    </script>
    """
    body = body.replace("__PRH__", t["pr_h"]).replace("__PRSUB__", t["pr_sub"])
    body = body.replace("__PRAGE__", t["pr_age"]).replace("__PRGEND__", t["pr_gender"])
    body = body.replace("__PRCOND__", t["pr_conditions"]).replace("__PRMEDS__", t["pr_meds"])
    body = body.replace("__PRALL__", t["pr_allergies"]).replace("__PRSAVE__", t["pr_save"])
    body = body.replace("__AGE__", esc(p.get("age"))).replace("__GENSEL__", gen_sel)
    body = body.replace("__COND__", esc(p.get("conditions"))).replace("__MEDS__", esc(p.get("medications")))
    body = body.replace("__ALL__", esc(p.get("allergies")))
    body = body.replace("__PT__", json.dumps({"pr_saved": t["pr_saved"], "pr_err": t["pr_err"], "__LANG__": "en" if _lang() == "en" else "ar"}, ensure_ascii=False))
    return _page(_t("title_profile"), body)


# ---------------------------------------------------------------- history
def history_page():
    db.init_db()
    t = L["en" if _lang() == "en" else "ar"]
    rows = db.get_records(_user_id(), limit=25)
    if not rows:
        body = """
        <div class="card" style="max-width:640px;margin:0 auto;text-align:center;">
          <h2>__HSH__</h2>
          <p class="muted">__HSSUB__</p>
          <p style="margin-top:16px;">__HSEMPTY__</p>
          <p style="margin-top:10px;">__NOPROF__ <a href="/profile">__PROFLINK__</a></p>
        </div>
        """
        body = body.replace("__HSH__", t["hs_h"]).replace("__HSSUB__", t["hs_sub"])
        body = body.replace("__HSEMPTY__", t["hs_empty"])
        body = body.replace("__NOPROF__", t["hs_no_profile"]).replace("__PROFLINK__", t["hs_profile_link"])
        return _page(_t("title_history"), body)
    cards = ""
    urg_en = {"high": "Emergency", "medium": "Needs appointment", "low": "Simple"}
    urg_ar = {"high": "طوارئ", "medium": "يحتاج موعد طبيب", "low": "بسيط"}
    urg_map = urg_en if _lang() == "en" else urg_ar
    for r in rows:
        u = (r["urgency"] or "low").lower()
        u_label = urg_map.get(u, u)
        share_txt = (
            "SymptoSense: " + ", ".join(r["symptoms"]) + " → " + u_label
        )
        share_url = "https://wa.me/?text=" + share_txt.replace(" ", "%20")
        cards += """
        <div class="hist-card">
          <div class="hist-head"><b>📅 %s</b><span class="pill pill-%s">%s</span></div>
          <p class="muted">%s</p>
          <div class="hist-row"><a class="btn ghost small" href="/api/analyze/export/%s">%s</a>
          <a class="btn ghost small" href="%s" target="_blank" rel="noopener">📤 %s</a></div>
        </div>
        """ % (
            r["timestamp"][:16].replace("T", " "),
            "hi" if u == "high" else ("med" if u == "medium" else "low"),
            u_label,
            ", ".join(r["symptoms"]),
            r["id"],
            t["hs_dl"],
            share_url,
            t["hs_share"],
        )
    body = """
    <div class="card" style="max-width:760px;margin:0 auto;">
      <h2>__HSH__</h2>
      <p class="muted">__HSSUB__</p>
      <div style="margin-top:14px;">__CARDS__</div>
    </div>
    """
    body = body.replace("__HSH__", t["hs_h"]).replace("__HSSUB__", t["hs_sub"]).replace("__CARDS__", cards)
    return _page(_t("title_history"), body)


def _pdf_report(record, lang):
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    import arabic_reshaper
    from bidi.algorithm import get_display

    t = L["en" if lang == "en" else "ar"]
    w, h = A4
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(t["pdf_doc_title"])
    rtl = lang != "en"

    def T(s):
        if not s:
            return ""
        s = str(s)
        return get_display(arabic_reshaper.reshape(s)) if rtl else s

    c.setFont("Helvetica-Bold", 18)
    c.setFillColorRGB(0.06, 0.46, 0.42)
    c.drawString(50, h - 55, T("SymptoSense 🏥"))
    c.setFont("Helvetica-Bold", 15)
    c.setFillColorRGB(0.12, 0.16, 0.24)
    c.drawString(50, h - 80, T(t["pdf_doc_title"]))
    c.setFont("Helvetica", 10)
    c.setFillColorRGB(0.4, 0.45, 0.5)
    c.drawString(50, h - 98, T(record.get("timestamp", "")[:19].replace("T", " ")))

    y = h - 130
    def section(label, text, extra=14):
        nonlocal y
        c.setFont("Helvetica-Bold", 11)
        c.setFillColorRGB(0.06, 0.46, 0.42)
        c.drawString(50, y, T(label))
        y -= 4
        c.setFont("Helvetica", 10.5)
        c.setFillColorRGB(0.12, 0.16, 0.24)
        for chunk in str(text).split("\n"):
            line = T(chunk)
            while len(line) > 80:
                c.drawString(50, y, line[:80])
                line = line[80:]
                y -= extra
            c.drawString(50, y, line)
            y -= extra
        y -= 6

    urgs = {"high": "طوارئ", "medium": "يحتاج موعد طبيب", "low": "بسيط"} if rtl else {"high": "Emergency", "medium": "Needs appointment", "low": "Simple"}
    u = str(record.get("urgency") or "low").lower()
    urgency_text = urgs.get(u, u)
    recs = record.get("recommendations") or []
    rec_text = "\n".join(
        "- %s (%s)" % (r.get("tip") or "", r.get("source") or "")
        for r in recs if isinstance(r, dict) and r.get("tip")
    ) or "—"
    conds = record.get("possible_conditions") or "—"

    section(t["pdf_symptoms"], ", ".join(record.get("symptoms", [])))
    section(t["pdf_conditions"], conds)
    section(t["pdf_urgency"], urgency_text)
    section(t["pdf_recs"], rec_text)
    section(t["pdf_for"], "Age: %s | Gender: %s" % (record.get("age") or "—", record.get("gender") or "—"))

    c.setFont("Helvetica-Oblique", 9)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawString(50, 50, T(t["pdf_disclaimer"]))
    c.drawString(50, 38, T(t["pdf_source"]))
    c.showPage()
    c.save()
    buf.seek(0)
    return buf


# ---------------------------------------------------------------- routes
@app.route("/")
def index():
    return welcome_page()


@app.route("/home")
def home():
    return home_page()


@app.route("/about")
def about():
    return about_page()


@app.route("/chat")
def chat():
    return chat_page()


@app.route("/blood")
def blood():
    return blood_page()


@app.route("/meds")
def meds():
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


@app.route("/profile")
def profile():
    return profile_page()


@app.route("/history")
def history():
    return history_page()


@app.route("/admin")
def admin():
    return render_template_string(DASHBOARD_HTML)


@app.route("/robots.txt")
def robots_txt():
    base = _site_url()
    body = "User-agent: *\nAllow: /\nSitemap: " + base + "/sitemap.xml\n"
    return Response(body, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    base = _site_url()
    pages = ["/", "/home", "/chat", "/blood", "/meds", "/emergency", "/checkin", "/firstaid", "/tips", "/relax", "/profile", "/history", "/about"]
    urls = "\n".join(
        "  <url><loc>%s</loc><changefreq>weekly</changefreq><priority>%.1f</priority></url>"
        % (base + p, 1.0 if p == "/" else 0.7)
        for p in pages
    )
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n%s\n</urlset>\n' % urls
    return Response(xml, mimetype="application/xml")


@app.route("/api/stats")
def api_stats():
    db.init_db()
    stats = db.get_usage_stats(days=7)
    trends, _ = db.get_trends(days=7)
    top_symptoms = trends.most_common(8)
    urgency = dict(db.fetchall("SELECT urgency, COUNT(*) FROM records GROUP BY urgency"))
    lang = dict(db.fetchall("SELECT lang, COUNT(*) FROM records GROUP BY lang"))
    ages = [row[0] for row in db.fetchall("SELECT age FROM records WHERE age IS NOT NULL")]
    age_groups = {"0-17": 0, "18-30": 0, "31-45": 0, "46-60": 0, "60+": 0}
    for a in ages:
        if a <= 17: age_groups["0-17"] += 1
        elif a <= 30: age_groups["18-30"] += 1
        elif a <= 45: age_groups["31-45"] += 1
        elif a <= 60: age_groups["46-60"] += 1
        else: age_groups["60+"] += 1
    feedback = dict(db.fetchall("SELECT rating, COUNT(*) FROM feedback GROUP BY rating"))
    fb_comments = db.fetchall(
        "SELECT rating, comment, timestamp FROM feedback "
        "WHERE comment IS NOT NULL AND comment != '' ORDER BY timestamp DESC LIMIT 20"
    )
    return jsonify({
        "stats": stats,
        "symptoms": top_symptoms,
        "urgency": urgency,
        "lang": lang,
        "age_groups": list(age_groups.items()),
        "feedback": feedback,
        "fb_comments": [{"rating": r, "comment": c, "timestamp": t} for r, c, t in fb_comments],
        "db_backend": "PostgreSQL" if db.USE_POSTGRES else "SQLite",
    })


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    try:
        data = request.get_json(force=True)
        lang = "en" if data.get("lang") == "en" else "ar"
        patient = {
            "user_id": _user_id(),
            "age": data.get("age"),
            "gender": data.get("gender"),
            "symptoms": data.get("symptoms", []),
            "duration": data.get("duration"),
            "severity": data.get("severity", 1),
            "conditions": data.get("conditions", ""),
            "medications": data.get("medications", ""),
            "notes": data.get("notes", ""),
        }
        if not patient["conditions"] or not patient["medications"] or not patient["age"]:
            try:
                p = db.load_profile(_user_id())
                if p:
                    if not patient["age"]:
                        patient["age"] = p.get("age") or None
                    if not patient["gender"]:
                        patient["gender"] = p.get("gender") or None
                    if not patient["conditions"]:
                        patient["conditions"] = p.get("conditions") or ""
                    if not patient["medications"]:
                        patient["medications"] = p.get("medications") or ""
            except Exception:
                pass
        result = analysis_core.run_analysis(patient, lang=lang)
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"})


@app.route("/api/profile", methods=["POST"])
def api_profile():
    try:
        db.init_db()
        data = request.get_json(force=True)
        db.save_profile(
            _user_id(),
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


@app.route("/api/analyze/export/<int:record_id>")
def api_export_pdf(record_id):
    db.init_db()
    result = db.load_result(_user_id(), record_id)
    if not result:
        lang = _lang()
        t = L["en" if lang == "en" else "ar"]
        body = ('<div class="card" style="max-width:520px;margin:40px auto;text-align:center;">'
                '<h2>%s</h2><p style="margin-top:10px;"><a class="btn" href="/history">%s</a></p></div>'
                % (t["pdf_nf"], t["hs_dl"]))
        return _page(_t("title_history"), body)
    lang = "en" if result.get("lang") == "en" else "ar"
    buf = _pdf_report(result, lang)
    fname = "symptosense-report-%s.pdf" % record_id
    return send_file(
        buf, mimetype="application/pdf",
        as_attachment=True, download_name=fname,
    )


@app.route("/api/followup", methods=["POST"])
def api_followup():
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


@app.route("/api/checkin", methods=["GET", "POST"])
def api_checkin():
    uid = _user_id()
    if request.method == "POST":
        try:
            data = request.get_json(force=True)
            rating = int(data.get("rating"))
            if rating < 1 or rating > 5:
                return jsonify({"ok": False, "error": "التقييم من 1 إلى 5"})
            db.init_db()
            db.save_daily_checkin(uid, rating)
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"})
    try:
        db.init_db()
        rows = db.get_daily_checkins(uid, days=14)
        chart = None
        if rows:
            chart = _checkin_chart(rows)
        return jsonify({"ok": True, "rows": [{"date": d, "value": v} for d, v in rows], "chart": chart})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"})


@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    try:
        data = request.get_json(force=True)
        rating = data.get("rating")
        comment = (data.get("comment") or "").strip()[:500]
        db.init_db()
        db.save_feedback(_user_id(), None, rating, comment or None)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"})


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
    ax.plot(range(len(vals)), vals, marker="o", color="#14b8a6", linewidth=2)
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
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/tip")
def api_tip():
    return jsonify({"tip": health_tips.get_random_tip("en" if _lang() == "en" else "ar")})


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
    f = request.files.get("file")
    if not f:
        return jsonify({"ok": False, "error": "لم يتم رفع ملف"})
    gender = request.form.get("gender", "f")
    age = request.form.get("age") or None
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
        if age is None:
            age = auto_age
        results, notes, dangers, level, child_note = blood_test.analyze_blood(entries, gender, age)
        text_html = blood_test.build_text(results, gender, "en" if _lang() == "en" else "ar", notes, dangers, child_note)
        chart_b64 = None
        try:
            chart = blood_test.generate_blood_chart(results)
            if chart:
                chart_b64 = base64.b64encode(chart).decode("ascii")
        except Exception:
            chart_b64 = None
        return jsonify({"ok": True, "text_html": text_html, "chart": chart_b64, "level": level})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"})


def run_webapp():
    db.init_db()
    port = int(os.environ.get("PORT", 5000))
    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=port, threads=8)
    except ImportError:
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    run_webapp()
