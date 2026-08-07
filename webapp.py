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
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', Tahoma, sans-serif; background: #f6f9fb; color: #1e293b; }
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
.chat-body { flex: 1; overflow-y: auto; padding: 18px; background: #f0f7f6; }
.bubble { max-width: 85%; margin-bottom: 10px; padding: 11px 15px; border-radius: 14px; font-size: 15px; line-height: 1.8; white-space: pre-wrap; }
.bubble.bot { background: #fff; border: 1px solid #e2e8f0; border-bottom-right-radius: 4px; }
.bubble.user { background: #0f766e; color: #fff; margin-left: auto; border-bottom-left-radius: 4px; }
.bubble.result { background: #fff; border: 1px solid #99f6e4; max-width: 100%; }
.chat-options { padding: 14px; background: #fff; border-top: 1px solid #e2e8f0; display: flex; flex-wrap: wrap; gap: 8px; }
.opt { background: #f0f7f6; border: 1.5px solid #0f766e; color: #0f766e; padding: 9px 16px; border-radius: 24px; font-size: 14px; cursor: pointer; }
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
"""

PAGE_FRAME = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__</title>
<meta name="description" content="__DESC__">
<meta name="keywords" content="تحليل الأعراض, فحص الأعراض, تشخيص مبدئي, صحة, طب, مستشفيات السعودية, SymptoSense">
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
<nav class="nav">
  <div class="logo">Sympto<span>Sense</span> 🏥</div>
  <div class="links">
    <a href="/">الرئيسية</a>
    <a href="/chat">فحص الأعراض</a>
    <a href="/blood">تحليل الدم</a>
    <a href="/meds">الأدوية</a>
    <a href="/emergency">الطوارئ</a>
    <a href="/checkin">متابعتي</a>
    <a href="/firstaid">الإسعافات</a>
    <a href="/tips">النصائح</a>
    <a href="/relax">الاسترخاء</a>
    <a href="/admin">لوحة التحكم</a>
  </div>
</nav>
<div class="container">
__BODY__
</div>
<div class="footer">
  <p>SymptoSense © 2026 — للتوعية الصحية فقط وليس بديلاً عن الاستشارة الطبية.</p>
  <p style="margin-top:6px;">في حالة الطوارئ اتصل بالإسعاف مباشرة: <b>997</b> (السعودية)</p>
</div>
</body>
</html>
"""


def _user_id():
    if "uid" not in session:
        session["uid"] = secrets.token_hex(8)
    return "web-" + hashlib.sha1(session["uid"].encode()).hexdigest()[:12]


def _site_url():
    return os.environ.get("SITE_URL", "https://symptosense.up.railway.app").rstrip("/")


def _page(title, body, desc=None):
    if not desc:
        desc = "SymptoSense — مساعدك الذكي لتحليل الأعراض وتقييم الحالة الصحية الأولي بناءً على مصادر طبية موثوقة."
    base = _site_url()
    gsc = os.environ.get("GOOGLE_SITE_VERIFICATION", "")
    gsc_tag = (
        '<meta name="google-site-verification" content="%s">' % gsc
        if gsc
        else ""
    )
    return (
        PAGE_FRAME
        .replace("__TITLE__", title)
        .replace("__DESC__", desc)
        .replace("__CANONICAL__", base + request.path)
        .replace("__GSC_TAG__", gsc_tag)
        .replace("__CSS__", BASE_CSS)
        .replace("__BODY__", body)
    )


# ---------------------------------------------------------------- landing
def landing_page():
    body = """
    <div class="hero">
      <h1>كيف تحسين؟ <span style="color:#ccfbf1;">لنكتشف معاً 🩺</span></h1>
      <p>أدخلي أعراضك بخطوات بسيطة واحصلي على تقييم أولي ذكي مدعوم بالذكاء الاصطناعي ومصادر طبية موثوقة (Mayo Clinic, NHS, WHO) — مع تحذيرات الأدوية، أقرب المستشفيات، تحليل فحوصات الدم، والإسعافات الأولية.</p>
      <a class="btn" href="/chat">ابدأ الفحص الآن 🚀</a>
      <a class="btn ghost" href="/blood">تحليل فحص الدم 📋</a>
    </div>

    <h2 style="text-align:center;margin-bottom:6px;">اختر ما تحتاج 🧰</h2>
    <div class="features">
      <a class="feature serv" href="/chat"><div class="ic">🩺</div><h3>فحص الأعراض</h3><p>أدخلي أعراضك واحصلي على تقييم أولي ذكي مع خطورة الحالة.</p></a>
      <a class="feature serv" href="/blood"><div class="ic">🩸</div><h3>تحليل فحص الدم</h3><p>ارفعي صورة أو PDF لتحليل الدم (CBC) وافهمي قيمك.</p></a>
      <a class="feature serv" href="/meds"><div class="ic">💊</div><h3>البحث عن دواء</h3><p>تحذيرات الأدوية والتفاعلات وإرشادات الاستخدام الآمن.</p></a>
      <a class="feature serv" href="/firstaid"><div class="ic">🚑</div><h3>الإسعافات الأولية</h3><p>خطوات سريعة واضحة للحالات الطارئة اليومية.</p></a>
      <a class="feature serv" href="/tips"><div class="ic">💡</div><h3>نصائح صحية</h3><p>نصائح يومية عملية لصحة أفضل لك ولعائلتك.</p></a>
      <a class="feature serv" href="/relax"><div class="ic">🧘</div><h3>استرخاء وتنفس</h3><p>تمارين تنفس وهدوء لتخفيف التوتر والقلق.</p></a>
      <a class="feature serv" href="/emergency"><div class="ic">🚨</div><h3>أرقام الطوارئ</h3><p>أرقام مهمة جاهزة للحالات الطارئة (997، 911، 937...).</p></a>
      <a class="feature serv" href="/checkin"><div class="ic">📋</div><h3>متابعة يومية</h3><p>سجّلي حالتك يومياً وتابعي تحسنك بمخطط واضح.</p></a>
    </div>

    <div class="features">
      <div class="feature"><div class="ic">🧠</div><h3>تحليل ذكي</h3><p>تحليل أعراضك بالذكاء الاصطناعي مع احتمال الأمراض وتقييم الخطورة (بسيط / موعد / طوارئ).</p></div>
      <div class="feature"><div class="ic">💊</div><h3>تحذيرات الأدوية</h3><p>فحص أدويتك ضد قاعدة بيانات التفاعلات الدوائية وإرشاد حذر عن الاستمرار.</p></div>
      <div class="feature"><div class="ic">🏥</div><h3>أقرب مستشفى</h3><p>بناءً على موقعك، نعرض لك أقرب المرافق الصحية بالمسافة ورابط الخريطة.</p></div>
      <div class="feature"><div class="ic">🩸</div><h3>تحليل فحص الدم</h3><p>ارفع صورة أو PDF لتحليل الدم (CBC) واحصل على تفسير القيم والمؤشرات.</p></div>
      <div class="feature"><div class="ic">❓</div><h3>أسئلة لطبيبك</h3><p>أسئلة ذكية جاهزة تسألها لطبيبك في الموعد، مع علامات الخطر ومتى تراجع.</p></div>
      <div class="feature"><div class="ic">🧘</div><h3>رعاية شاملة</h3><p>إسعافات أولية، نصائح صحية يومية، وتمارين استرخاء وتنفس للمساعدة.</p></div>
    </div>

    <div class="card">
      <h2>كيف يعمل؟</h2>
      <div class="steps">
        <div class="step"><span class="n">1</span><h3>أدخل معلوماتك</h3><p>العمر، الجنس، الأعراض، المدة، الشدة بأزرار بسيطة.</p></div>
        <div class="step"><span class="n">2</span><h3>تحليل فوري</h3><p>محرك ذكي يقيّم حالتك من مصادر طبية موثوقة مع نموذج ML.</p></div>
        <div class="step"><span class="n">3</span><h3>خطة واضحة</h3><p>الاحتمالات، التوصيات، متى تزور الطبيب، وأقرب المستشفيات.</p></div>
      </div>
    </div>

    <div class="warn">⚠️ <b>تنبيه:</b> هذا الموقع للتوعية الصحية فقط وليس تشخيصاً طبياً نهائياً. في حال وجود أعراض خطرة (ألم صدر حاد، صعوبة تنفس، نزيف حاد، فقدان وعي) اتصل بالإسعاف فوراً <b>997</b>.</div>
    """
    return _page("SymptoSense — تحليل الأعراض بالذكاء الاصطناعي", body)


# ---------------------------------------------------------------- chat
def chat_page():
    syms = [
        "🤕 صداع", "🤒 حمى", "😷 سعال", "🫀 ألم في الصدر", "🤢 غثيان", "😴 تعب وإرهاق",
        "🫁 ضيق التنفس", "💫 دوار", "🦴 ألم المفاصل", "😖 ألم في البطن", "🥶 قشعريرة", "👁️ احمرار العيون",
        "🦵 ألم في الرجل", "😣 ألم الحلق", "🖐️ حكة",
    ]
    durs = ["⏰ أقل من 24 ساعة", "📅 1-3 أيام", "📅 4-7 أيام", "🗓️ 1-2 أسبوع", "🗓️ أكثر من أسبوعين", "📆 أكثر من شهر"]
    sevs = [("1", "1️⃣ خفيف جداً"), ("2", "2️⃣ معتدل"), ("3", "3️⃣ متوسط"), ("4", "4️⃣ شديد"), ("5", "5️⃣ حرج جداً")]
    conds = ["لا يوجد أمراض سابقة", "سكري", "ضغط الدم", "أمراض قلب", "ربو"]

    body = """
    <div class="chat-wrap">
      <div class="chat-head">
        <div class="avatar">🏥</div>
        <div><h3>SymptoSense</h3><p>مساعد التحليل الذكي — بالعربية 🇸🇦</p></div>
      </div>
      <div class="chat-body" id="chatBody"></div>
      <div class="chat-options" id="chatOptions"></div>
      <div class="chat-input" id="chatInput" style="display:none;">
        <input type="text" id="textInp" placeholder="اكتب هنا..." autocomplete="off">
        <button onclick="toggleMic()" id="micBtn" title="إدخال صوتي">🎤</button>
        <button onclick="submitText()">إرسال</button>
      </div>
    </div>
    <div class="muted" style="text-align:center;margin-top:10px;">التوعية فقط وليس تشخيصاً نهائياً — راجعي الطبيب عند أي شك.</div>

    <script>
    const SYMS = __SYMS__;
    const DURS = __DURS__;
    const SEVS = __SEVS__;
    const CONDS = __CONDS__;
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
      return d;
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
      add('كم عمرك؟ (اكتب الرقم فقط) 🧒👵', 'bot');
      showText('مثال: 28');
    }
    function askGender() {
      state.step = 'gender';
      add('ما جنسك؟', 'bot');
      showOpts([
        {label:'👨 ذكر', fn:()=>{ state.gender='m'; add('👨 ذكر','user'); askSymptoms(); }},
        {label:'👩 أنثى', fn:()=>{ state.gender='f'; add('👩 أنثى','user'); askSymptoms(); }}
      ]);
    }
    function G(f, m) { return state.gender === 'm' ? m : f; }
    function askSymptoms() {
      state.step = 'symptoms';
      add(G(
        'ما هي أعراضك؟\\n\\nاضغطي على الأعراض التي تشعرين بها (يمكنك اختيار أكثر من واحد).\\nإذا لم تجدي عرضك، اكتبيه مباشرة في صندوق الكتابة.\\n\\nعند الانتهاء اضغطي: ✅ انتهيت',
        'ما هي أعراضك؟\\n\\nاضغط على الأعراض التي تشعر بها (يمكنك اختيار أكثر من واحد).\\nإذا لم تجد عرضك، اكتبه مباشرة في صندوق الكتابة.\\n\\nعند الانتهاء اضغط: ✅ انتهيت'
      ), 'bot');
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
      items.push({label:'✍️ اكتب عرضاً بنفسك', fn:()=>{
        add(G('✍️ اكتبي العرض الذي تشعرين به:', '✍️ اكتب العرض الذي تشعر به:'), 'bot');
        showText('مثال: ألم في الساق');
      }});
      items.push({label:'✅ انتهيت', cls:'danger', fn:()=>{
        if (!state.symptoms.length) { add(G('اختاري عرضاً واحداً على الأقل قبل المتابعة.', 'اختر عرضاً واحداً على الأقل قبل المتابعة.'), 'bot'); return; }
        add('✅ تم اختيار: ' + state.symptoms.join('، '), 'user');
        askDuration();
      }});
      showOpts(items);
    }
    function askDuration() {
      state.step = 'duration';
      add('كم مدة هذه الأعراض؟', 'bot');
      showOpts(DURS.map(d=>({label:d, fn:()=>{ state.duration=d; add(d,'user'); askSeverity(); }})));
    }
    function askSeverity() {
      state.step = 'severity';
      add('ما شدة الأعراض؟ (من 1 خفيف جداً إلى 5 حرج جداً)', 'bot');
      showOpts(SEVS.map(([v,l])=>({label:l, fn:()=>{ state.severity=v; add(l,'user'); askConditions(); }})));
    }
    function askConditions() {
      state.step = 'conditions';
      add(G('هل لديكِ أمراض مزمنة سابقة؟', 'هل لديك أمراض مزمنة سابقة؟'), 'bot');
      const items = CONDS.map(c=>({label:c, fn:()=>{ state.conditions=c; add(c,'user'); askMeds(); }}));
      items.push({label:'✏️ أمراض أخرى', fn:()=>{ add(G('✏️ اكتبي الأمراض:', '✏️ اكتب الأمراض:'), 'bot'); showText('مثال: غدة درقية'); }});
      showOpts(items);
    }
    function askMeds() {
      state.step = 'medications';
      add(G('هل تأخذين حالياً أي أدوية؟ اذكري أسماءها (أو اضغطي تخطي).', 'هل تأخذ حالياً أي أدوية؟ اذكر أسماءها (أو اضغط تخطي).'), 'bot');
      showOpts([{label:'⏭️ تخطي', fn:()=>{ add('⏭️ تخطي','user'); state.medications=''; askNotes(); }}]);
      showText('مثال: بنادول، فولتارين', true);
    }
    function askNotes() {
      state.step = 'notes';
      add(G('أي ملاحظات إضافية؟ (أو اضغطي تخطي)', 'أي ملاحظات إضافية؟ (أو اضغط تخطي)'), 'bot');
      showOpts([{label:'⏭️ تخطي', fn:()=>{ add('⏭️ تخطي','user'); state.notes=''; runAnalysis(); }}]);
      showText('مثال: أعاني منذ الصباح بعد الأكل', true);
    }
    function submitText() {
      const v = send();
      if (!v) return;
      if (state.step === 'age') {
        const n = parseInt(v);
        if (!n || n < 1 || n > 120) { add('يرجى إدخال عمر صحيح بين 1 و 120.', 'bot'); showText('مثال: 28'); return; }
        state.age = n; askGender();
      } else if (state.step === 'symptoms') {
        state.symptoms.push(v);
        add(G('✅ أُضيف العرض. اضغطي ✅ انتهيت عند الانتهاء أو أضيفي المزيد.', '✅ أُضيف العرض. اضغط ✅ انتهيت عند الانتهاء أو أضف المزيد.'), 'bot');
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
      add('جاري التحليل... ⏳', 'bot');
      try {
        const r = await fetch('/api/analyze', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify(state)
        });
        const d = await r.json();
        if (d.ok) renderResult(d); else add('حدث خطأ: ' + (d.error||'غير معروف'), 'bot');
      } catch(e) { add('تعذر الاتصال، حاول مجدداً.', 'bot'); }
    }
    function esc(s) { const div=document.createElement('div'); div.textContent=s||''; return div.innerHTML; }
    function renderResult(d) {
      lastResult = d;
      const u = d.urgency;
      const pill = u==='high' ? 'طوارئ 🔴' : (u==='medium' ? 'يحتاج موعد طبيب 🟡' : 'بسيط 🟢');
      const pcls = 'urg-' + u;
      let h = '<div class="sec-title">📋 نتيجة التحليل</div>';
      h += '<div class="pill ' + pcls + '" style="margin:4px 0 10px;">' + pill + '</div>';
      h += '<div class="res-sec"><i>' + esc(d.personal_note) + '</i></div>';
      if (d.rule_forced_high) h += '<div class="warn" style="margin:8px 0;">⚠️ تم رفع الخطورة تلقائياً بناءً على الأعراض الحمراء.</div>';
      if (d.low_confidence) h += '<div class="muted">⚖️ الثقة منخفضة — يُفضل مراجعة الطبيب.</div>';

      if (d.possible_conditions) h += '<div class="sec-title">🩺 الاحتمالات المحتملة</div><div class="res-sec">' + esc(d.possible_conditions) + '</div>';
      if (d.med_warnings && d.med_warnings.length) {
        h += '<div class="sec-title">💊 تحذيرات الأدوية</div>';
        d.med_warnings.forEach(m => h += '<div class="rec-item"><b>' + esc(m.name_ar) + '</b>: ' + esc(m.warning_ar) + '</div>');
        h += '<div class="muted">التوعية فقط — لا توقفي دواءك الموصوف بدون استشارة الطبيب.</div>';
      }
      if (d.ml_predictions && d.ml_predictions.length) {
        h += '<div class="sec-title">📊 تحليل نموذج التعلم الآلي</div>';
        d.ml_predictions.forEach(p => {
          h += '<div style="font-size:13px;">' + esc(p.name_ar) + ' (' + Math.round(p.probability*100) + '%)</div>';
          h += '<div class="bar-bg"><div class="bar-fill" style="width:' + Math.round(p.probability*100) + '%"></div></div>';
        });
      }
      if (d.recommendations && d.recommendations.length) {
        h += '<div class="sec-title">📌 التوصيات</div>';
        d.recommendations.forEach(r => {
          h += '<div class="rec-item">' + esc(r.tip);
          if (r.source && r.url) h += '<div class="src">🔗 <a href="' + esc(r.url) + '" target="_blank">' + esc(r.source) + '</a></div>';
          h += '</div>';
        });
      }
      if (d.danger_signs) h += '<div class="sec-title">🚨 علامات الخطر</div><div class="res-sec">' + esc(d.danger_signs) + '</div>';
      if (d.when_to_seek_care) h += '<div class="sec-title">🕑 متى تراجع الطبيب</div><div class="res-sec">' + esc(d.when_to_seek_care) + '</div>';
      if (d.home_care) h += '<div class="sec-title">🏠 الرعاية المنزلية</div><div class="res-sec">' + esc(d.home_care) + '</div>';
      if (d.medication_guidance) h += '<div class="sec-title">💊 إرشاد الدواء</div><div class="res-sec">' + esc(d.medication_guidance) + '</div>';
      if (d.questions_for_doctor) h += '<div class="sec-title">❓ اسأل طبيبك</div><div class="res-sec">' + esc(d.questions_for_doctor) + '</div>';
      addHtml('<div class="result">' + h + '</div>', 'result');
      addHtml('<div style="margin-top:10px;text-align:center;"><button class="opt" onclick="speakResult()">🔊 استمع للنتيجة</button></div>', 'result');
      addHtml('<div class="sec-title">⭐ هل أفادك التحليل؟</div><div style="display:flex;gap:6px;flex-wrap:wrap;justify-content:center;">' +
        '<button class="opt" data-v="1" onclick="fb(this.dataset.v)">😍 ممتاز</button>' +
        '<button class="opt" data-v="2" onclick="fb(this.dataset.v)">🙂 جيد</button>' +
        '<button class="opt" data-v="3" onclick="fb(this.dataset.v)">😐 عادي</button>' +
        '<button class="opt" data-v="4" onclick="fb(this.dataset.v)">😞 لا</button></div>' +
        '<div id="fbMsg" style="margin-top:8px;text-align:center;font-weight:600;color:#0f766e;"></div>', 'result');
      showOpts([
        {label:'💬 اسأل عن حالتك', fn:askFollowup},
        {label:'🏥 أقرب مستشفى', fn:findHospitals},
        {label:'🔄 تحليل جديد', fn:restart},
        {label:'🔗 مشاركة', fn:()=>{
          try { navigator.share({title:'SymptoSense', text:'تقييمي الأولي: ' + pill}) } catch(e) {} }
        }
      ]);
    }
    let lastResult = null;
    function askFollowup() {
      state.step = 'followup';
      add(G('اكتبي سؤالك عن حالتك 👇', 'اكتب سؤالك عن حالتك 👇'), 'bot');
      showText('مثال: هل هذا طبيعي؟ متى أتحسن؟');
    }
    async function submitFollowup(q) {
      add('جاري الإجابة... ⏳', 'bot');
      try {
        const r = await fetch('/api/followup', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({question:q, context:lastResult || {}})});
        const d = await r.json();
        if (d.ok) add(d.answer, 'bot'); else add('خطأ: ' + (d.error||'غير معروف'), 'bot');
      } catch(e) { add('تعذر الاتصال، حاول مجدداً.', 'bot'); }
      showOpts([
        {label:'💬 سؤال آخر', fn:askFollowup},
        {label:'🔄 تحليل جديد', fn:restart}
      ]);
    }
    function speakResult() {
      if (!lastResult) return;
      if (!('speechSynthesis' in window)) { add('متصفحك لا يدعم القراءة الصوتية.', 'bot'); return; }
      const u = lastResult.urgency;
      const pill = u==='high' ? 'طوارئ' : (u==='medium' ? 'يحتاج موعد طبيب' : 'بسيط');
      const txt = 'نتيجة التحليل: الخطورة ' + pill + '. ' + (lastResult.personal_note || '') + ' ' + (lastResult.possible_conditions || '');
      speechSynthesis.cancel();
      const uu = new SpeechSynthesisUtterance(txt);
      uu.lang = 'ar-SA';
      speechSynthesis.speak(uu);
    }
    function fb(rating) {
      fetch('/api/feedback', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({rating: rating})});
      document.getElementById('fbMsg').textContent = 'شكراً لتقييمك 🌟';
    }
    let recog = null, micOn = false;
    function toggleMic() {
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SR) { add('متصفحك لا يدعم الإدخال الصوتي.', 'bot'); return; }
      if (micOn) { recog.stop(); return; }
      recog = new SR();
      recog.lang = 'ar-SA';
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
      add('جاري تحديد موقعك... 📍', 'bot');
      navigator.geolocation.getCurrentPosition(async pos => {
        const r = await fetch('/api/hospitals', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({lat:pos.coords.latitude, lng:pos.coords.longitude})
        });
        const d = await r.json();
        if (!d.hospitals || !d.hospitals.length) { add('ما لقينا مستشفيات قريبة.', 'bot'); return; }
        let h = '<div class="sec-title">🏥 أقرب المستشفيات</div>';
        d.hospitals.forEach(x => h += '<div class="rec-item"><b>' + esc(x.name) + '</b> — ' + x.distance_km + ' كم<br><a href="' + esc(x.maps_url) + '" target="_blank">🗺️ فتح في الخريطة</a></div>');
        addHtml(h, 'result');
      }, () => { add(G('تعذر الوصول لموقعك — تأكدي من تفعيل الموقع.', 'تعذر الوصول لموقعك — تأكد من تفعيل الموقع.'), 'bot'); });
    }
    function restart() {
      Object.assign(state, {age:null,gender:null,symptoms:[],duration:null,severity:null,conditions:null,medications:null,notes:null});
      bodyEl.innerHTML = '';
      add('مرحباً بك في SymptoSense 🏥', 'bot');
      askAge();
    }
    restart();
    </script>
    """
    return _page("SymptoSense — فحص الأعراض", body.replace("__SYMS__", json.dumps(syms, ensure_ascii=False)).replace("__DURS__", json.dumps(durs, ensure_ascii=False)).replace("__SEVS__", json.dumps(sevs, ensure_ascii=False)).replace("__CONDS__", json.dumps(conds, ensure_ascii=False)))



# ---------------------------------------------------------------- blood
def blood_page():
    body = """
    <div class="card">
      <h2>🩸 تحليل فحص الدم (CBC)</h2>
      <p class="muted">ارفع صورة فحص الدم أو ملف PDF وسنستخرج القيم ونحللها ونرسم المخطط. (HGB, WBC, RBC, HCT, MCV, MCH, MCHC, PLT...)</p>
      <div style="margin-top:16px;">
        <div class="grid2">
          <div><label class="lbl">الجنس</label><select class="inp" id="bg"><option value="f">أنثى</option><option value="m">ذكر</option><option value="c">طفل</option></select></div>
          <div><label class="lbl">العمر (اختياري — للطفل)</label><input class="inp" type="number" id="ba" placeholder="مثال: 5"></div>
        </div>
        <div class="drop" id="drop">📂 اضغطي هنا لاختيار صورة أو PDF<br><span class="muted">JPG / PNG / PDF</span></div>
        <input type="file" id="fileInp" accept="image/*,application/pdf" style="display:none;">
        <button class="btn" onclick="uploadBlood()">تحليل ⚡</button>
        <div id="bloodRes" style="margin-top:18px;"></div>
      </div>
    </div>
    <script>
    const drop = document.getElementById('drop');
    const fileInp = document.getElementById('fileInp');
    drop.onclick = () => fileInp.click();
    drop.ondragover = e => {{ e.preventDefault(); drop.classList.add('on'); }};
    drop.ondragleave = () => drop.classList.remove('on');
    drop.ondrop = e => {{ e.preventDefault(); drop.classList.remove('on'); if (e.dataTransfer.files[0]) fileInp.files = e.dataTransfer.files; }};
    async function uploadBlood() {{
      const f = fileInp.files[0];
      if (!f) {{ document.getElementById('bloodRes').innerHTML = '<div class="warn">اختر ملف أولاً.</div>'; return; }}
      const box = document.getElementById('bloodRes');
      box.innerHTML = '<div class="bubble bot" style="max-width:100%">جاري قراءة الفحص... <span class="spin"></span></div>';
      const fd = new FormData();
      fd.append('file', f);
      fd.append('gender', document.getElementById('bg').value);
      fd.append('age', document.getElementById('ba').value);
      const r = await fetch('/api/blood', {{ method:'POST', body: fd }});
      const d = await r.json();
      if (!d.ok) {{ box.innerHTML = '<div class="warn">' + (d.error||'تعذر التحليل') + '</div>'; return; }}
      let h = '<div class="result bubble bot" style="max-width:100%">' + d.text_html;
      if (d.chart) h += '<div style="text-align:center;margin-top:12px;"><img src="data:image/png;base64,' + d.chart + '" style="max-width:100%;border-radius:10px;"></div>';
      h += '</div>';
      box.innerHTML = h;
    }}
    </script>
    """
    return _page("SymptoSense — تحليل الدم", body)


# ---------------------------------------------------------------- meds
def meds_page():
    body = """
    <div class="card">
      <h2>💊 فحص الأدوية والتفاعلات</h2>
      <p class="muted">اكتبي الأدوية التي تتناولينها (مع أي مرض مزمن) لنفحصها ضد قاعدة بيانات التحذيرات الدوائية.</p>
      <label class="lbl">الأدوية / الحالة الصحية</label>
      <textarea class="inp" id="medText" rows="3" placeholder="مثال: فولتارين، وارفارين، ضغط الدم"></textarea>
      <div style="margin-top:12px;"><button class="btn" onclick="checkMeds()">فحص 🔍</button></div>
      <div id="medRes" style="margin-top:16px;"></div>
    </div>
    <div class="card" style="margin-top:16px;">
      <h2>⏰ التذكير الدوائي</h2>
      <p class="muted">احفظي مواعيد أدويتك وذكّرك بها المتصفح كل يوم (الإشعارات تعمل ما دامت الصفحة مفتوحة).</p>
      <div class="grid2">
        <div><label class="lbl">اسم الدواء</label><input class="inp" id="remName" placeholder="مثال: بنادول"></div>
        <div><label class="lbl">المواعيد (ساعة:دقيقة)</label><input class="inp" id="remTimes" placeholder="مثال: 08:00، 14:00، 20:00"></div>
      </div>
      <div style="margin-top:12px;"><button class="btn" onclick="addReminder()">حفظ التذكير 💊</button></div>
      <div id="remMsg" style="margin-top:8px;font-weight:600;color:#0f766e;"></div>
      <div id="remList" style="margin-top:12px;"></div>
    </div>
    <div class="warn">⚠️ لا توقفي أو تغيري جرعة أي دواء موصوف بدون استشارة الطبيب أو الصيدلي.</div>
    <script>
    async function checkMeds() {{
      const t = document.getElementById('medText').value.trim();
      const box = document.getElementById('medRes');
      if (!t) {{ box.innerHTML = '<div class="warn">اكتبي الأدوية أولاً.</div>'; return; }}
      box.innerHTML = '<div class="bubble bot">جاري الفحص... <span class="spin"></span></div>';
      const r = await fetch('/api/meds', {{ method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify({{text:t}}) }});
      const d = await r.json();
      if (!d.warnings.length) {{ box.innerHTML = '<div class="bubble bot">✅ لم نجد تحذيرات مطابقة للأدوية المكتوبة.</div>'; return; }}
      let h = '<table class="tbl"><tr><th>الدواء</th><th>التحذير</th></tr>';
      d.warnings.forEach(w => h += '<tr><td><b>' + esc(w.name_ar) + '</b></td><td>' + esc(w.warning_ar) + '</td></tr>');
      h += '</table>';
      box.innerHTML = '<div class="bubble bot" style="max-width:100%">' + h + '</div>';
    }}
    function esc(s) {{ const div=document.createElement('div'); div.textContent=s||''; return div.innerHTML; }}
    function loadReminders() {{ try {{ return JSON.parse(localStorage.getItem('ss_reminders') || '[]'); }} catch(e) {{ return []; }} }}
    function saveReminders(list) {{ localStorage.setItem('ss_reminders', JSON.stringify(list)); }}
    function renderReminders() {{
      const list = loadReminders();
      const box = document.getElementById('remList');
      if (!list.length) {{ box.innerHTML = '<div class="muted">لا توجد تذكيرات بعد.</div>'; return; }}
      let h = '<table class="tbl"><tr><th>الدواء</th><th>المواعيد</th><th></th></tr>';
      list.forEach((r, i) => {{
        h += '<tr><td><b>' + esc(r.name) + '</b></td><td>' + r.times.join('، ') + '</td><td><button class="opt" onclick="removeRem(' + i + ')">حذف 🗑️</button></td></tr>';
      }});
      h += '</table>';
      box.innerHTML = h;
    }}
    function addReminder() {{
      const name = document.getElementById('remName').value.trim();
      const tval = document.getElementById('remTimes').value.trim();
      const box = document.getElementById('remMsg');
      if (!name) {{ box.textContent = 'اكتبي اسم الدواء أولاً.'; return; }}
      const times = tval.split(/[,،\\s]+/).filter(Boolean);
      if (!times.length) {{ box.textContent = 'اكتبي الأوقات مثل: 08:00، 14:00، 20:00'; return; }}
      if (!('Notification' in window)) {{ box.textContent = 'متصفحك لا يدعم الإشعارات.'; return; }}
      Notification.requestPermission().then(perm => {{
        if (perm !== 'granted') {{ box.textContent = 'فعلي الإشعارات من إعدادات المتصفح حتى يعمل التذكير.'; return; }}
        const list = loadReminders();
        list.push({{ name: name, times: times }});
        saveReminders(list);
        document.getElementById('remName').value = '';
        document.getElementById('remTimes').value = '';
        box.textContent = '✅ تم حفظ التذكير. سينبهك المتصفح في الأوقات المحددة (طالما الصفحة مفتوحة).';
        renderReminders();
      }});
    }}
    function removeRem(i) {{
      const list = loadReminders();
      list.splice(i, 1);
      saveReminders(list);
      renderReminders();
    }}
    function checkTimes() {{
      const now = new Date();
      const cur = ('0' + now.getHours()).slice(-2) + ':' + ('0' + now.getMinutes()).slice(-2);
      const list = loadReminders();
      list.forEach(r => {{
        r.times.forEach(t => {{
          if (t === cur && r.last !== cur) {{
            r.last = cur;
            if (('Notification' in window) && Notification.permission === 'granted') {{
              new Notification('💊 تذكير دوائي', {{ body: 'حان وقت أخذ: ' + r.name }});
            }}
            saveReminders(list);
          }}
        }});
      }});
    }}
    setInterval(checkTimes, 30000);
    renderReminders();
    </script>
    """
    return _page("SymptoSense — فحص الأدوية", body)


# ---------------------------------------------------------------- first aid
def firstaid_page():
    cats = wellbeing.first_aid_categories("ar")
    body = """
    <div class="card">
      <h2>🚑 الإسعافات الأولية</h2>
      <p class="muted">اختر الحالة لعرض الإرشادات الإسعافية خطوة بخطوة.</p>
      <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:14px;" id="faBtns"></div>
      <div id="faRes" style="margin-top:18px;"></div>
    </div>
    <div class="warn">⚠️ في الحالات الحرجة (توقف تنفس، نزيف حاد، فقدان وعي) اتصل بالإسعاف <b>997</b> فوراً.</div>
    <script>
    const CATS = __CATS__;
    const wrap = document.getElementById('faBtns');
    CATS.forEach(([k, label]) => {{
      const b = document.createElement('button');
      b.className = 'opt';
      b.textContent = label;
      b.onclick = async () => {{
        const r = await fetch('/api/firstaid/' + k);
        const d = await r.json();
        document.getElementById('faRes').innerHTML = '<div class="bubble bot" style="max-width:100%"><b>' + esc(d.label) + '</b>\\n\\n' + esc(d.text) + '</div>';
      }};
      wrap.appendChild(b);
    }});
    function esc(s) {{ const div=document.createElement('div'); div.textContent=s||''; return div.innerHTML; }}
    </script>
    """.replace("__CATS__", json.dumps(cats, ensure_ascii=False))
    return _page("SymptoSense — الإسعافات الأولية", body)


# ---------------------------------------------------------------- tips
def tips_page():
    body = """
    <div class="card" style="text-align:center;">
      <h2>🍃 نصيحة صحية</h2>
      <div id="tipBox" style="font-size:17px;line-height:2;padding:20px;background:#f0f7f6;border-radius:12px;margin:14px 0;"></div>
      <button class="btn" onclick="loadTip()">نصيحة أخرى 🔄</button>
    </div>
    <script>
    async function loadTip() {{
      const box = document.getElementById('tipBox');
      box.innerHTML = '... <span class="spin"></span>';
      const r = await fetch('/api/tip');
      const d = await r.json();
      box.innerHTML = esc(d.tip);
    }}
    function esc(s) {{ const div=document.createElement('div'); div.textContent=s||''; return div.innerHTML; }}
    loadTip();
    </script>
    """
    return _page("SymptoSense — النصائح الصحية", body)


# ---------------------------------------------------------------- relax
def relax_page():
    txt = wellbeing.relax_guide("ar")
    body = """
    <div class="card">
      <h2>🧘 تمرين الاسترخاء والتنفس</h2>
      <div style="font-size:16px;line-height:2;background:#f0f7f6;border-radius:12px;padding:20px;white-space:pre-wrap;">__TXT__</div>
      <div style="text-align:center;margin-top:16px;"><div id="breathBox" style="font-size:30px;font-weight:800;color:#0f766e;height:70px;display:flex;align-items:center;justify-content:center;"></div></div>
    </div>
    <script>
    const phases = [['استنشق 🌬️', 4], ['احبس 🧘', 7], ['زفر 😮‍💨', 8]];
    let pi = 0;
    function tick() {{
      const [label, secs] = phases[pi];
      document.getElementById('breathBox').textContent = label;
      pi = (pi + 1) % phases.length;
      setTimeout(tick, secs * 1000);
    }}
    tick();
    </script>
    """.replace("__TXT__", txt)
    return _page("SymptoSense — الاسترخاء", body)


# ---------------------------------------------------------------- emergency
def emergency_page():
    body = """
    <div class="card">
      <h2>🚨 أرقام الطوارئ في السعودية</h2>
      <p class="muted">احتفظي بهذه الأرقام، وأجريها فوراً عند الحاجة.</p>
      <div class="features" style="margin-top:14px;">
        <div class="feature"><div class="ic">🚑</div><h3>الهلال الأحمر (إسعاف)</h3><p><b style="font-size:26px;color:#dc2626;">997</b></p></div>
        <div class="feature"><div class="ic">📞</div><h3>الطوارئ الموحد</h3><p><b style="font-size:26px;color:#dc2626;">911</b></p></div>
        <div class="feature"><div class="ic">🩺</div><h3>استشارات وزارة الصحة (24/7)</h3><p><b style="font-size:26px;color:#0f766e;">937</b></p></div>
        <div class="feature"><div class="ic">🚓</div><h3>الشرطة</h3><p><b style="font-size:26px;color:#0f766e;">999</b></p></div>
        <div class="feature"><div class="ic">🚒</div><h3>الدفاع المدني</h3><p><b style="font-size:26px;color:#0f766e;">998</b></p></div>
      </div>
      <div class="warn" style="margin-top:8px;">⚠️ في حالة الأعراض الخطرة (ألم صدر حاد، صعوبة تنفس، نزيف حاد، فقدان وعي) اتصل بالإسعاف <b>997</b> فوراً ولا تنتظر.</div>
    </div>
    """
    return _page("SymptoSense — أرقام الطوارئ", body)


# ---------------------------------------------------------------- checkin
def checkin_page():
    body = """
    <div class="card">
      <h2>📋 متابعة الحالة اليومية</h2>
      <p class="muted">سجّلي حالتك كل يوم (من 1 سيء جداً إلى 5 ممتاز) وتابعي تحسنك بالمخطط.</p>
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
    async function ci(rating) {
      const r = await fetch('/api/checkin', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({rating: rating})});
      const d = await r.json();
      if (d.ok) { document.getElementById('ciMsg').textContent = 'تم تسجيل حالتك ✅ (5 = ممتاز، 1 = سيء جداً)'; loadChart(); }
      else document.getElementById('ciMsg').textContent = 'خطأ: ' + (d.error || 'غير معروف');
    }
    async function loadChart() {
      const r = await fetch('/api/checkin');
      const d = await r.json();
      const box = document.getElementById('ciChart');
      if (!d.ok) { box.innerHTML = '<div class="muted">تعذر تحميل المخطط.</div>'; return; }
      if (!d.rows.length) { box.innerHTML = '<div class="muted">لا توجد تسجيلات بعد — سجّلي أول تقييم من الأزرار فوق.</div>'; return; }
      box.innerHTML = '<img src="' + d.chart + '" alt="مخطط التحسن" style="max-width:100%;border-radius:12px;box-shadow:0 4px 14px rgba(0,0,0,.08);">';
    }
    loadChart();
    </script>
    """
    return _page("SymptoSense — متابعة الحالة اليومية", body)


# ---------------------------------------------------------------- routes
@app.route("/")
def index():
    return landing_page()


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
    pages = ["/", "/chat", "/blood", "/meds", "/emergency", "/checkin", "/firstaid", "/tips", "/relax"]
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
        result = analysis_core.run_analysis(patient, lang="ar")
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"})


@app.route("/api/followup", methods=["POST"])
def api_followup():
    try:
        data = request.get_json(force=True)
        question = (data.get("question") or "").strip()
        ctx = data.get("context") or {}
        if not question:
            return jsonify({"ok": False, "error": "السؤال فارغ"})
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
            return jsonify({"ok": True, "answer": "أهلاً! لا أستطيع الرد الكامل حالياً، لكن المعلومات العامة تشير إلى ضرورة مراجعة الطبيب عند استمرار الأعراض أو ازديادها سوءاً. هذه إجابة توعوية وليست تشخيصاً نهائياً."})
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
    ax.set_title("تحسن حالتك")
    ax.set_ylabel("الشدة")
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
    return jsonify({"tip": health_tips.get_random_tip("ar")})


@app.route("/api/firstaid/<key>")
def api_firstaid(key):
    label, text = wellbeing.first_aid_text(key, "ar")
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
        text_html = blood_test.build_text(results, gender, "ar", notes, dangers, child_note)
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
