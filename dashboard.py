"""SymptoSense unified admin dashboard.

The main web application renders ``DASHBOARD_HTML`` after session, role, and
CSRF checks.  The tiny standalone app at the bottom remains for local UI work.
"""
import os

from flask import Flask, jsonify, render_template_string

import db


app = Flask(__name__)

DASHBOARD_HTML = r"""
{% set ar = lang != 'en' %}
<!DOCTYPE html>
<html lang="{{ lang }}" dir="{{ 'rtl' if ar else 'ltr' }}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SymptoSense — Admin Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&family=Poppins:wght@400;600;700&display=swap');
:root{--p:#1976D2;--pd:#123B70;--pl:#EAF4FF;--sky:#64B5F6;--bg:#F5F9FF;--card:#fff;--line:#DCEBFA;--text:#40566F;--muted:#5F7185;--green:#166534;--greenbg:#ECFDF5;--yellow:#92400E;--yellowbg:#FFFBEB;--red:#991B1B;--redbg:#FEF2F2}
*{box-sizing:border-box;margin:0;padding:0;min-width:0}body{font-family:'Cairo','Poppins','Segoe UI',sans-serif;background:var(--bg);color:var(--text);min-height:100vh}button,input,select,textarea{font:inherit}button{cursor:pointer}a{text-decoration:none;color:inherit}
.top{position:sticky;top:0;z-index:40;background:rgba(255,255,255,.97);backdrop-filter:blur(14px);border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;gap:14px;padding:12px clamp(14px,3vw,34px)}
.brand{display:flex;align-items:center;gap:10px}.brand-ic{width:44px;height:44px;border-radius:14px;background:var(--pl);display:grid;place-items:center;font-size:22px}.brand b{color:var(--pd);font-size:20px}.brand b em{color:var(--p);font-style:normal}.brand small{display:block;color:var(--muted);font-size:11px}
.user{display:flex;align-items:center;gap:8px;flex-wrap:wrap;justify-content:flex-end}.role{padding:5px 10px;border-radius:999px;background:var(--pl);color:var(--pd);font-size:11px;font-weight:800}.top-a{padding:7px 11px;border:1px solid var(--line);border-radius:10px;background:#fff;color:var(--pd);font-size:12px;font-weight:700}
.layout{display:grid;grid-template-columns:235px minmax(0,1fr);max-width:1480px;margin:auto;min-height:calc(100vh - 70px)}.side{padding:20px 12px;border-inline-end:1px solid var(--line);background:#fff}.navbtn{width:100%;border:0;background:transparent;text-align:start;padding:11px 12px;border-radius:12px;color:var(--text);font-weight:700;margin:2px 0}.navbtn:hover,.navbtn.on{background:var(--pl);color:var(--p)}.main{padding:clamp(18px,3vw,30px)}
.view{display:none}.view.on{display:block}.head{display:flex;align-items:flex-end;justify-content:space-between;gap:14px;margin-bottom:18px;flex-wrap:wrap}.head h1{color:var(--pd);font-size:clamp(22px,3.5vw,31px)}.head p{color:var(--muted);font-size:13px}.actions{display:flex;gap:8px;flex-wrap:wrap}.btn{border:0;border-radius:11px;padding:9px 15px;background:var(--p);color:#fff;font-weight:800;font-size:13px}.btn.ghost{background:#fff;color:var(--pd);border:1px solid var(--line)}.btn.danger{background:var(--redbg);color:var(--red);border:1px solid #FECACA}.btn.small{padding:6px 10px;font-size:11px}.btn:disabled{opacity:.45;cursor:not-allowed}
.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:20px}.stat{background:#fff;border:1px solid var(--line);border-radius:17px;padding:17px;box-shadow:0 5px 18px rgba(25,118,210,.05)}.stat strong{display:block;color:var(--p);font-size:27px}.stat span{color:var(--pd);font-size:12px;font-weight:800}.stat small{display:block;color:var(--muted);font-size:10px;margin-top:2px}
.card{background:#fff;border:1px solid var(--line);border-radius:18px;padding:18px;margin-bottom:16px;box-shadow:0 5px 20px rgba(25,118,210,.05)}.card h2{color:var(--pd);font-size:16px;margin-bottom:12px}.two{display:grid;grid-template-columns:1fr 1fr;gap:14px}.chart{height:250px;position:relative}
.toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:12px}.search{flex:1;min-width:220px;border:1px solid var(--line);background:#fff;border-radius:11px;padding:10px 12px;color:var(--text)}.filter{border:1px solid var(--line);background:#fff;border-radius:11px;padding:9px 10px;color:var(--text)}
.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:14px}table{width:100%;border-collapse:collapse;min-width:760px;background:#fff}th,td{padding:11px 12px;text-align:start;border-bottom:1px solid var(--line);font-size:12px;vertical-align:top}th{background:var(--pl);color:var(--pd);font-weight:800;position:sticky;top:0}tr:last-child td{border-bottom:0}.muted{color:var(--muted);font-size:11px}.empty{text-align:center;color:#94A3B8;padding:25px}.badge{display:inline-flex;padding:4px 8px;border-radius:999px;font-size:10px;font-weight:800}.active,.verified,.online{color:var(--green);background:var(--greenbg)}.draft,.needs_review,.review,.not_configured{color:var(--yellow);background:var(--yellowbg)}.disabled,.urgent,.offline{color:var(--red);background:var(--redbg)}
.modal-bg{display:none;position:fixed;inset:0;z-index:100;background:rgba(15,23,42,.55);padding:18px;align-items:center;justify-content:center}.modal-bg.show{display:flex}.modal{background:#fff;border-radius:20px;width:min(780px,100%);max-height:92vh;overflow:auto;box-shadow:0 30px 80px rgba(15,23,42,.3)}.modal-head{position:sticky;top:0;background:#fff;display:flex;align-items:center;justify-content:space-between;padding:16px 18px;border-bottom:1px solid var(--line);z-index:2}.modal-head h2{color:var(--pd);font-size:18px}.close{width:36px;height:36px;border:0;border-radius:10px;background:var(--pl);color:var(--pd);font-weight:900}.form{padding:18px}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.field{display:flex;flex-direction:column;gap:5px}.field.full{grid-column:1/-1}.field label{font-size:11px;color:var(--pd);font-weight:800}.field input,.field select,.field textarea{border:1px solid var(--line);border-radius:10px;padding:10px;color:var(--text);background:#fff}.field textarea{min-height:82px;resize:vertical}.form-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:16px}.msg{display:none;margin:0 18px 16px;padding:10px 12px;border-radius:11px;font-size:12px}.msg.show{display:block}.msg.ok{background:var(--greenbg);color:var(--green)}.msg.err{background:var(--redbg);color:var(--red)}
.health{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.health-item{border:1px solid var(--line);border-radius:14px;padding:14px}.health-item b{color:var(--pd)}.audit-json{max-width:360px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;direction:ltr;text-align:start}
@media(max-width:1050px){.grid{grid-template-columns:repeat(2,1fr)}.layout{grid-template-columns:1fr}.side{position:sticky;top:69px;z-index:30;display:flex;gap:5px;overflow:auto;border-inline-end:0;border-bottom:1px solid var(--line);padding:8px}.navbtn{width:auto;white-space:nowrap}.main{padding:18px 12px}}
@media(max-width:700px){.top{align-items:flex-start}.brand small,.user>span:not(.role){display:none}.grid,.two,.health,.form-grid{grid-template-columns:1fr}.field.full{grid-column:auto}.main{padding:16px 10px}.card{padding:13px}.head{align-items:flex-start}.table-wrap{border:0}table{min-width:0}thead{display:none}tr{display:block;border:1px solid var(--line);border-radius:13px;margin-bottom:9px;padding:7px}td{display:flex;justify-content:space-between;gap:12px;border:0;padding:7px;font-size:12px}td:before{content:attr(data-label);font-weight:800;color:var(--pd)}.modal-bg{padding:7px}.modal{border-radius:15px}.user .top-a:first-of-type{display:none}}
</style>
</head>
<body>
<header class="top">
  <div class="brand"><div class="brand-ic">❤️‍🩹</div><div><b>Sympto<em>Sense</em></b><small>{{ 'لوحة الإدارة' if ar else 'Admin Dashboard' }}</small></div></div>
  <div class="user"><span>{{ admin_user.email }}</span><span class="role">{{ admin_user.role }}</span><a class="top-a" href="/?choose=1&next=/admin">🌐 {{ 'EN' if ar else 'AR' }}</a><a class="top-a" href="/home">{{ 'الموقع' if ar else 'Site' }}</a><a class="top-a" href="/logout">{{ 'خروج' if ar else 'Sign out' }}</a></div>
</header>
<div class="layout">
<aside class="side" id="side">
  <button class="navbtn on" data-view="overview">🏠 {{ 'لوحة التحكم' if ar else 'Dashboard' }}</button>
  <button class="navbtn" data-view="analytics">📊 {{ 'التحليلات' if ar else 'Analytics' }}</button>
  <button class="navbtn" data-view="knowledge">🧠 {{ 'المعرفة الطبية' if ar else 'Medical Knowledge' }}</button>
  <button class="navbtn" data-view="sources">📚 {{ 'المصادر الطبية' if ar else 'Medical Sources' }}</button>
  <button class="navbtn" data-view="content">📝 {{ 'المحتوى' if ar else 'Content' }}</button>
  <button class="navbtn" data-view="users">👥 {{ 'المستخدمون' if ar else 'Users' }}</button>
  <button class="navbtn" data-view="health">🖥️ {{ 'صحة النظام' if ar else 'System Health' }}</button>
  <button class="navbtn" data-view="audit">🔐 {{ 'سجل التدقيق' if ar else 'Audit Log' }}</button>
  <a class="navbtn" href="/home" style="display:block;margin-top:16px;border-top:1px solid var(--line);padding-top:16px">← {{ 'العودة إلى SymptoSense' if ar else 'Back to SymptoSense' }}</a>
</aside>
<main class="main">
  <section class="view on" id="view-overview">
    <div class="head"><div><h1>Admin Dashboard</h1><p>{{ 'إدارة ومراقبة SymptoSense' if ar else 'Manage and monitor SymptoSense' }}</p></div><button class="btn ghost" onclick="loadUsage()">🔄 {{ 'تحديث' if ar else 'Refresh' }}</button></div>
    <div class="grid" id="overviewStats"></div>
    <div class="two"><div class="card"><h2>{{ 'النشاط خلال 30 يومًا' if ar else 'Activity — 30 days' }}</h2><div class="chart"><canvas id="visChart"></canvas></div></div><div class="card"><h2>{{ 'حالة النظام' if ar else 'System status' }}</h2><div id="overviewHealth" class="health"></div></div></div>
    <div class="card"><h2>{{ 'الخصوصية' if ar else 'Privacy' }}</h2><p class="muted">{{ 'تعرض لوحة الإدارة بيانات تشغيلية وإدارية مجمعة فقط، ولا تعرض الأعراض أو المحادثات أو النتائج الصحية الشخصية في التحليلات.' if ar else 'Admin analytics use aggregate operational data only and do not expose symptoms, chats, or personal health results.' }}</p></div>
  </section>

  <section class="view" id="view-analytics">
    <div class="head"><div><h1>📈 {{ 'تحليلات الاستخدام' if ar else 'Usage analytics' }}</h1><p>{{ 'بيانات تشغيل مجمعة فقط؛ لا أعراض ولا محادثات ولا نتائج صحية شخصية.' if ar else 'Aggregate operational data only—no symptoms, chats, or personal health results.' }}</p></div><div class="actions"><select class="filter" id="analyticsDays" onchange="loadV2Analytics()"><option value="7">7 days</option><option value="30" selected>30 days</option><option value="90">90 days</option></select><button class="btn ghost" onclick="loadV2Analytics()">🔄</button></div></div>
    <div class="grid" id="v2AnalyticsStats"></div>
    <div class="two"><div class="card"><h2>{{ 'الخدمات الأكثر استخدامًا' if ar else 'Most-used services' }}</h2><div id="v2Services"></div></div><div class="card"><h2>{{ 'اللغة والجهاز' if ar else 'Language and device' }}</h2><div id="v2Segments"></div></div></div>
    <div class="two"><div class="card"><h2>{{ 'المستخدمون بمرور الوقت' if ar else 'Users over time' }}</h2><div class="chart"><canvas id="usersTimeline"></canvas></div></div><div class="card"><h2>{{ 'التحليلات بمرور الوقت' if ar else 'Analyses over time' }}</h2><div class="chart"><canvas id="analysesTimeline"></canvas></div></div></div>
    <div class="two"><div class="card"><h2>{{ 'استخدام المساعد الذكي' if ar else 'AI Assistant use' }}</h2><div class="chart"><canvas id="assistantTimeline"></canvas></div></div><div class="card"><h2>{{ 'أكثر الأعراض إدخالًا' if ar else 'Most-entered symptoms' }}</h2><div id="topSymptoms"></div></div></div>
    <div class="card"><h2>{{ 'النشاط العام' if ar else 'Overall activity' }}</h2><div class="chart"><canvas id="v2Timeline"></canvas></div></div>
    <div class="card"><h2>{{ 'الأقسام الأكثر زيارة' if ar else 'Most-visited sections' }}</h2><div class="table-wrap" id="v2Sections"></div></div>
  </section>

  <section class="view" id="view-knowledge"><div class="head"><div><h1>🧠 Medical Knowledge Base</h1><p>{{ 'إدارة الأمراض والأعراض والعلاقات وعلامات الخطر والفئات.' if ar else 'Manage diseases, symptoms, relationships, red flags, and categories.' }}</p></div><button class="btn ghost" onclick="loadKB()">🔄 {{ 'تحديث' if ar else 'Refresh' }}</button></div><div class="grid" id="kbStats"></div>
  <div class="card"><div class="toolbar"><button class="btn ghost" onclick="show('diseases')">🩺 {{ 'الأمراض' if ar else 'Diseases' }}</button><button class="btn ghost" onclick="show('symptoms')">🤕 {{ 'الأعراض' if ar else 'Symptoms' }}</button><button class="btn ghost" onclick="show('relationships')">🔗 {{ 'العلاقات' if ar else 'Relationships' }}</button><button class="btn ghost" onclick="show('redflags')">🚨 {{ 'علامات الخطر' if ar else 'Red Flags' }}</button><button class="btn" onclick="openEditor('category')">＋ {{ 'إضافة فئة' if ar else 'Add Category' }}</button></div><h2>{{ 'الفئات' if ar else 'Categories' }}</h2><div id="categories"></div></div>
  <div class="card"><h2>{{ 'تسلسل التقييم' if ar else 'Assessment flow' }}</h2><p class="muted">User Input → Symptom Normalization → Knowledge Retrieval → Matching → Safety Rules → AI Explanation → Risk → Sources</p></div></section>

  {% if admin_user.role == 'admin' %}
  <section class="view" id="view-content"><div class="head"><div><h1>📝 {{ 'إدارة المحتوى' if ar else 'Content management' }}</h1><p>{{ 'النصائح والأسئلة الشائعة والتوعية والنصوص التعريفية بالعربية والإنجليزية.' if ar else 'Bilingual tips, FAQs, awareness, and introductory copy.' }}</p></div><button class="btn edit-only" onclick="openContentEditor()">＋ {{ 'إضافة محتوى' if ar else 'Add content' }}</button></div><div class="card"><div class="toolbar"><input id="contentSearch" class="search" placeholder="{{ 'بحث...' if ar else 'Search...' }}" oninput="renderContent()"><select id="contentType" class="filter" onchange="renderContent()"><option value="">{{ 'كل الأنواع' if ar else 'All types' }}</option><option value="health_tip">Health tip</option><option value="faq">FAQ</option><option value="educational">Educational Content</option><option value="mental_health">Mental Health Content</option><option value="awareness">Awareness</option><option value="intro">Intro</option></select></div><div class="table-wrap" id="table-content"></div></div></section>
  {% for key, icon, title_ar, title_en in [('diseases','🩺','الأمراض','Diseases'),('symptoms','🤕','الأعراض','Symptoms'),('relationships','🔗','علاقات المرض والأعراض','Disease–symptom relationships'),('sources','📚','المصادر الطبية','Medical sources'),('redflags','🚨','قواعد علامات الخطر','Red-flag rules')] %}
  <section class="view" id="view-{{ key }}"><div class="head"><div><h1>{{ icon }} {{ title_ar if ar else title_en }}</h1><p>{{ 'البحث بالعربية أو الإنجليزية وإدارة الحالة والمحتوى.' if ar else 'Search in Arabic or English and manage content status.' }}</p></div><button class="btn edit-only" onclick="openEditor('{{ 'red_flag' if key == 'redflags' else ('relationship' if key == 'relationships' else key[:-1]) }}')">＋ {{ 'إضافة' if ar else 'Add' }}</button></div><div class="card"><div class="toolbar"><input class="search" id="search-{{ key }}" placeholder="{{ 'بحث...' if ar else 'Search...' }}" oninput="render('{{ key }}')"><select class="filter" id="filter-{{ key }}" onchange="render('{{ key }}')"><option value="">{{ 'كل الحالات' if ar else 'All statuses' }}</option><option value="active">Active</option><option value="draft">Draft</option><option value="disabled">Disabled</option>{% if key == 'sources' %}<option value="verified">Verified</option><option value="needs_review">Needs review</option>{% endif %}</select>{% if key in ['diseases','symptoms'] %}<select class="filter category-filter" id="extra-{{ key }}" onchange="render('{{ key }}')"><option value="">{{ 'كل الفئات' if ar else 'All categories' }}</option></select>{% elif key == 'sources' %}<select class="filter" id="extra-{{ key }}" onchange="render('{{ key }}')"><option value="">{{ 'كل الأنواع' if ar else 'All types' }}</option><option value="government">Government</option><option value="international_organization">International Organization</option><option value="national_health_service">National Health Service</option><option value="academic_medical_institution">Academic Medical Institution</option><option value="other_trusted_source">Other Trusted Source</option></select>{% elif key == 'relationships' %}<select class="filter" id="extra-{{ key }}" onchange="render('{{ key }}')"><option value="">{{ 'كل الأنماط' if ar else 'All typicality' }}</option><option value="very_common">Very common</option><option value="common">Common</option><option value="less_common">Less common</option></select>{% elif key == 'redflags' %}<select class="filter" id="extra-{{ key }}" onchange="render('{{ key }}')"><option value="">{{ 'كل المخاطر' if ar else 'All risks' }}</option><option value="urgent">Urgent</option><option value="review">Needs review</option></select>{% endif %}{% if key == 'diseases' %}<select class="filter" id="extra2-diseases" onchange="render('diseases')"><option value="">{{ 'كل درجات الشدة' if ar else 'All severity' }}</option><option value="mild">Mild</option><option value="moderate">Moderate</option><option value="severe">Severe</option></select>{% endif %}</div><div class="table-wrap" id="table-{{ key }}"></div></div></section>
  {% endfor %}

  <section class="view" id="view-audit"><div class="head"><div><h1>🧾 {{ 'سجل التعديلات' if ar else 'Audit log' }}</h1><p>{{ 'من عدّل ماذا ومتى، مع القيم السابقة والجديدة.' if ar else 'Who changed what and when, with previous and new values.' }}</p></div><button class="btn ghost" onclick="loadAudit()">🔄</button></div><div class="card"><div class="table-wrap" id="table-audit"></div></div></section>
  <section class="view" id="view-health"><div class="head"><div><h1>🖥️ {{ 'صحة النظام' if ar else 'System health' }}</h1><p>{{ 'حالة المكونات وآخر فحص وزمن الاستجابة.' if ar else 'Component state, last check, and response time.' }}</p></div><button class="btn ghost" onclick="loadHealth()">🔄</button></div><div class="health" id="healthGrid"></div></section>
  {% endif %}
  {% if admin_user.role == 'admin' %}
  <section class="view" id="view-users"><div class="head"><div><h1>👥 {{ 'إدارة المستخدمين' if ar else 'User management' }}</h1><p>{{ 'معرّف وحالة وتواريخ ودور فقط؛ لا تعرض هذه الشاشة أي بيانات صحية.' if ar else 'ID, status, dates, and role only; this screen exposes no health data.' }}</p></div><button class="btn ghost" onclick="loadUsers()">🔄</button></div><div class="card"><div class="table-wrap" id="table-users"></div></div></section>
  {% endif %}
</main>
</div>

<div class="modal-bg" id="modal"><div class="modal"><div class="modal-head"><h2 id="modalTitle"></h2><button class="close" onclick="closeModal()">✕</button></div><form class="form" id="editForm"><div class="form-grid" id="formFields"></div><div class="form-actions"><button type="button" class="btn ghost" onclick="closeModal()">{{ 'إلغاء' if ar else 'Cancel' }}</button><button type="submit" class="btn">{{ 'حفظ' if ar else 'Save' }}</button></div></form><div class="msg" id="modalMsg"></div></div></div>

<script>
const LANG={{ lang|tojson }}, AR=LANG==='ar', CSRF={{ csrf_token|tojson }}, ROLE={{ admin_user.role|tojson }};
const CAN_EDIT=ROLE==='admin';
let KB={diseases:[],symptoms:[],sources:[],relationships:[],red_flags:[],categories:[],statistics:{}}, CONTENT=[], editing={kind:null,id:null};
let overviewChart=null, activityChart=null, usersChart=null, analysesChart=null, assistantChart=null;
const txt=(a,e)=>AR?a:e;
const esc=v=>{const d=document.createElement('div');d.textContent=v==null?'':String(v);return d.innerHTML};
const statusBadge=s=>'<span class="badge '+esc(s||'draft')+'">'+esc(s||'draft')+'</span>';

async function req(url,opt={}){
  opt.headers=Object.assign({'Content-Type':'application/json','X-CSRF-Token':CSRF},opt.headers||{});
  const r=await fetch(url,opt); const d=await r.json().catch(()=>({error:'invalid_response'}));
  if(r.status===401){location.href=d.login_url||'/login?next=/admin';throw new Error('login_required')}
  if(!r.ok||d.ok===false)throw new Error(d.error||('HTTP '+r.status)); return d;
}

function show(name){
  document.querySelectorAll('.view').forEach(v=>v.classList.remove('on'));
  const knowledgeChildren=['diseases','symptoms','relationships','redflags'];
  const sideName=knowledgeChildren.includes(name)?'knowledge':name;
  document.querySelectorAll('.side .navbtn[data-view]').forEach(v=>v.classList.toggle('on',v.dataset.view===sideName));
  document.getElementById('view-'+name)?.classList.add('on');
  if(name==='overview')loadUsage();
  if(name==='analytics')loadV2Analytics();
  if(['knowledge','sources','diseases','symptoms','relationships','redflags'].includes(name))loadKB();
  if(name==='content')loadContent();
  if(name==='users')loadUsers();
  if(name==='health')loadHealth();
  if(name==='audit')loadAudit();
}
document.querySelectorAll('.side .navbtn[data-view]').forEach(b=>b.onclick=()=>show(b.dataset.view));
document.querySelectorAll('.edit-only').forEach(x=>x.style.display=CAN_EDIT?'':'none');

function miniBars(rows, labelKey='name'){
  const max=Math.max(1,...(rows||[]).map(x=>Number(x.count)||0));
  return (rows||[]).map(x=>'<div style="margin:10px 0"><div style="display:flex;justify-content:space-between;gap:12px;font-size:12px"><b>'+esc(String(x[labelKey]||'').replaceAll('_',' '))+'</b><span>'+esc(x.count||0)+'</span></div><div style="height:7px;background:#EAF4FF;border-radius:99px"><div style="height:100%;width:'+((Number(x.count)||0)/max*100)+'%;background:#1976D2;border-radius:99px"></div></div></div>').join('')||'<div class="empty">'+txt('لا توجد بيانات بعد','No data yet')+'</div>';
}
function lineChart(canvas, existing, rows, label){
  if(!window.Chart||!canvas)return existing;
  existing?.destroy();
  return new Chart(canvas,{type:'line',data:{labels:(rows||[]).map(x=>x.date),datasets:[{label,data:(rows||[]).map(x=>x.count),borderColor:'#1976D2',backgroundColor:'rgba(25,118,210,.10)',fill:true,tension:.32,pointRadius:1.5}]},options:{maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{beginAtZero:true,ticks:{precision:0}},x:{ticks:{maxTicksLimit:8}}}}});
}

async function loadUsage(){
  try{
    const [a,k,h]=await Promise.all([req('/api/admin/v2/analytics?days=30'),req('/api/admin/knowledge/stats'),req('/api/admin/system-health')]);
    const d=a.analytics||{}, s=k.statistics||{}, cards=[
      ['👥',d.total_users,txt('إجمالي المستخدمين','Total Users')],
      ['🩺',d.analyses,txt('إجمالي التحليلات','Total Analyses')],
      ['🤖',d.assistant_uses,txt('استخدام المساعد','AI Assistant Uses')],
      ['📚',s.total_sources,txt('المصادر الطبية','Medical Sources')],
      ['⚠️',(d.alerts||0)+' / '+(d.errors||0),txt('تنبيهات / أخطاء','Alerts / Errors')],
      ['📈',d.activity,txt('النشاط','Activity')],
    ];
    document.getElementById('overviewStats').innerHTML=cards.map(x=>'<div class="stat"><span style="font-size:20px">'+x[0]+'</span><strong>'+esc(x[1]??0)+'</strong><span>'+esc(x[2])+'</span></div>').join('');
    overviewChart=lineChart(document.getElementById('visChart'),overviewChart,d.timeline||[],txt('النشاط','Activity'));
    const health=h.health||{components:{},checked_at:''};
    document.getElementById('overviewHealth').innerHTML=Object.entries(health.components||{}).map(([name,v])=>'<div class="health-item"><div style="display:flex;justify-content:space-between;gap:8px"><b>'+esc(name.replaceAll('_',' '))+'</b>'+statusBadge(v.status)+'</div><p class="muted" style="margin-top:7px">'+esc(v.response_ms??'—')+' ms</p></div>').join('')||'<div class="empty">'+txt('لا توجد بيانات بعد','No data yet')+'</div>';
  }catch(e){console.error(e)}
}

async function loadV2Analytics(){
  try{
    const days=document.getElementById('analyticsDays')?.value||30;
    const d=(await req('/api/admin/v2/analytics?days='+days)).analytics||{}, p=d.periods||{};
    const items=[[d.total_users,txt('المستخدمون','Users')],[d.analyses,txt('التحليلات','Analyses')],[d.assistant_uses,txt('استخدامات المساعد','Assistant uses')],[d.alerts,txt('تنبيهات الأمان','Safety alerts')],[d.errors,txt('الأخطاء','Errors')],[d.average_response_ms??'—',txt('متوسط الاستجابة ms','Avg response ms')],[p.daily||0,txt('اليوم','Today')],[p.weekly||0,txt('آخر 7 أيام','Last 7 days')]];
    document.getElementById('v2AnalyticsStats').innerHTML=items.map(x=>'<div class="stat"><strong>'+esc(x[0]??0)+'</strong><span>'+esc(x[1])+'</span></div>').join('');
    document.getElementById('v2Services').innerHTML=miniBars(d.services||[]);
    document.getElementById('topSymptoms').innerHTML=miniBars(d.top_symptoms||[]);
    document.getElementById('v2Segments').innerHTML='<h3 style="font-size:13px;margin-bottom:6px">'+txt('اللغة','Language')+'</h3>'+Object.entries(d.languages||{}).map(([k,v])=>'<span class="badge active" style="margin:3px">'+esc(k)+': '+v+'</span>').join('')+'<h3 style="font-size:13px;margin:12px 0 6px">'+txt('الجهاز','Device')+'</h3>'+Object.entries(d.devices||{}).map(([k,v])=>'<span class="badge verified" style="margin:3px">'+esc(k)+': '+v+'</span>').join('');
    document.getElementById('v2Sections').innerHTML='<table><thead><tr><th>'+txt('المسار','Path')+'</th><th>'+txt('الاستخدام','Uses')+'</th></tr></thead><tbody>'+(d.sections||[]).map(x=>'<tr><td data-label="Path">'+esc(x.path)+'</td><td data-label="Uses">'+x.count+'</td></tr>').join('')+'</tbody></table>';
    usersChart=lineChart(document.getElementById('usersTimeline'),usersChart,d.users_timeline||[],txt('المستخدمون الجدد','New users'));
    analysesChart=lineChart(document.getElementById('analysesTimeline'),analysesChart,d.analyses_timeline||[],txt('التحليلات','Analyses'));
    assistantChart=lineChart(document.getElementById('assistantTimeline'),assistantChart,d.assistant_timeline||[],txt('المساعد','Assistant'));
    activityChart=lineChart(document.getElementById('v2Timeline'),activityChart,d.timeline||[],txt('النشاط','Activity'));
  }catch(e){console.error(e)}
}

async function loadKB(){
  try{
    KB=await req('/api/admin/knowledge/bootstrap');
    document.querySelectorAll('.category-filter').forEach(el=>{const cur=el.value;el.innerHTML='<option value="">'+txt('كل الفئات','All categories')+'</option>'+opts(KB.categories||[],c=>AR?c.name_ar:c.name_en);el.value=cur});
    renderStats(); ['diseases','symptoms','relationships','sources','redflags'].forEach(render); renderCategories();
  }catch(e){alert(e.message)}
}
function renderStats(){
  const s=KB.statistics||{},items=[[s.total_diseases,txt('إجمالي الأمراض','Total diseases')],[s.total_symptoms,txt('إجمالي الأعراض','Total symptoms')],[s.total_sources,txt('إجمالي المصادر','Total sources')],[s.verified_sources,txt('مصادر موثقة','Verified sources')],[s.active_diseases,txt('أمراض نشطة','Active diseases')],[s.active_symptoms,txt('أعراض نشطة','Active symptoms')],[s.sources_needing_review,txt('تحتاج مراجعة','Need review')],[s.last_knowledge_update?String(s.last_knowledge_update).slice(0,10):'—',txt('آخر تحديث','Last update')]];
  document.getElementById('kbStats').innerHTML=items.map(x=>'<div class="stat"><strong>'+esc(x[0]??0)+'</strong><span>'+esc(x[1])+'</span></div>').join('');
}
function renderCategories(){
  const box=document.getElementById('categories'), rows=KB.categories||[]; if(!box)return;
  box.innerHTML=rows.length?'<div class="table-wrap"><table><thead><tr><th>ID</th><th>'+txt('العربي','Arabic')+'</th><th>'+txt('الإنجليزي','English')+'</th><th>Status</th><th>'+txt('إجراءات','Actions')+'</th></tr></thead><tbody>'+rows.map(x=>'<tr><td>#'+x.id+'</td><td>'+esc(x.name_ar)+'</td><td>'+esc(x.name_en)+'</td><td>'+statusBadge(x.status)+'</td><td><button class="btn ghost small" onclick="openEditor(\'category\','+x.id+')">✏️</button> <button class="btn danger small" onclick="removeItem(\'category\','+x.id+')">🗑️</button></td></tr>').join('')+'</tbody></table></div>':'<div class="empty">'+txt('لا توجد فئات','No categories')+'</div>';
}
function getRows(kind){return kind==='redflags'?(KB.red_flags||[]):(KB[kind]||[])}
function render(kind){
  const box=document.getElementById('table-'+kind);if(!box)return;
  let rows=getRows(kind),q=(document.getElementById('search-'+kind)?.value||'').toLowerCase(),f=document.getElementById('filter-'+kind)?.value||'',extra=document.getElementById('extra-'+kind)?.value||'',extra2=document.getElementById('extra2-'+kind)?.value||'';
  rows=rows.filter(x=>{let ok=JSON.stringify(x).toLowerCase().includes(q)&&(!f||x.status===f||x.verification_status===f);if(extra){if(kind==='diseases'||kind==='symptoms')ok=ok&&String(x.category_id)===String(extra);else if(kind==='sources')ok=ok&&x.source_type===extra;else if(kind==='relationships')ok=ok&&x.typicality===extra;else if(kind==='redflags')ok=ok&&x.risk_level===extra}if(extra2&&kind==='diseases')ok=ok&&x.severity===extra2;return ok});
  let cols=[];
  if(kind==='diseases')cols=[['name_ar',txt('العربي','Arabic')],['name_en',txt('الإنجليزي','English')],['severity',txt('الشدة','Severity')],['status',txt('الحالة','Status')],['last_updated',txt('آخر تحديث','Last updated')]];
  if(kind==='symptoms')cols=[['name_ar',txt('العربي','Arabic')],['name_en',txt('الإنجليزي','English')],['severity_min',txt('أقل شدة','Min')],['severity_max',txt('أعلى شدة','Max')],['status',txt('الحالة','Status')]];
  if(kind==='sources')cols=[['source_name',txt('المصدر','Source')],['source_type',txt('النوع','Type')],['language',txt('اللغة','Language')],['official_url','URL'],['verification_status',txt('التحقق','Verification')],['last_verified',txt('آخر تحقق','Last verified')]];
  if(kind==='relationships')cols=[['disease_name_ar',txt('المرض','Disease')],['symptom_name_ar',txt('العرض','Symptom')],['weight',txt('الوزن','Weight')],['typicality',txt('النمطية','Typicality')],['status',txt('الحالة','Status')]];
  if(kind==='redflags')cols=[['name_ar',txt('القاعدة','Rule')],['risk_level',txt('الخطر','Risk')],['min_severity',txt('أقل شدة','Min severity')],['match_mode',txt('المطابقة','Mode')],['status',txt('الحالة','Status')]];
  const head=cols.map(c=>'<th>'+esc(c[1])+'</th>').join('')+'<th>'+txt('إجراءات','Actions')+'</th>';
  const body=rows.map(x=>'<tr>'+cols.map(c=>'<td data-label="'+esc(c[1])+'">'+((c[0]==='status'||c[0]==='verification_status'||c[0]==='risk_level')?statusBadge(x[c[0]]):(c[0]==='official_url'?'<a href="'+esc(x[c[0]]||'#')+'" target="_blank" rel="noopener">'+esc(x[c[0]]||'—')+'</a>':esc(x[c[0]]??'—')))+'</td>').join('')+'<td data-label="Actions"><button class="btn ghost small" onclick="openEditor(\''+(kind==='redflags'?'red_flag':kind==='relationships'?'relationship':kind.slice(0,-1))+'\','+x.id+')">✏️</button> <button class="btn danger small" onclick="removeItem(\''+(kind==='redflags'?'red_flag':kind==='relationships'?'relationship':kind.slice(0,-1))+'\','+x.id+')">🗑️</button></td></tr>').join('');
  box.innerHTML=rows.length?'<table><thead><tr>'+head+'</tr></thead><tbody>'+body+'</tbody></table>':'<div class="empty">'+txt('لا توجد بيانات','No data yet')+'</div>';
}
function opts(rows,label,id='id',selected=[]){selected=(selected||[]).map(String);return rows.map(x=>'<option value="'+esc(x[id])+'" '+(selected.includes(String(x[id]))?'selected':'')+'>'+esc(label(x))+'</option>').join('')}
function field(label,name,value='',type='text',full=false,extra=''){if(type==='textarea')return '<div class="field '+(full?'full':'')+'"><label>'+esc(label)+'</label><textarea name="'+name+'">'+esc(value)+'</textarea></div>';return '<div class="field '+(full?'full':'')+'"><label>'+esc(label)+'</label><input type="'+type+'" name="'+name+'" value="'+esc(value)+'" '+extra+'></div>'}
function selectField(label,name,options,value='',full=false,multiple=false){return '<div class="field '+(full?'full':'')+'"><label>'+esc(label)+'</label><select name="'+name+'" '+(multiple?'multiple size="6"':'')+'>'+options+'</select></div>'}

async function loadContent(){try{CONTENT=(await req('/api/admin/content')).content||[];renderContent()}catch(e){alert(e.message)}}
function renderContent(){
  const box=document.getElementById('table-content');if(!box)return;const q=(document.getElementById('contentSearch')?.value||'').toLowerCase(),type=document.getElementById('contentType')?.value||'',rows=CONTENT.filter(x=>(!type||x.content_type===type)&&JSON.stringify(x).toLowerCase().includes(q));
  box.innerHTML=rows.length?'<table><thead><tr><th>ID</th><th>'+txt('العنوان','Title')+'</th><th>'+txt('النوع','Type')+'</th><th>'+txt('الفئة','Category')+'</th><th>'+txt('الحالة','Status')+'</th><th>Version</th><th>'+txt('إجراءات','Actions')+'</th></tr></thead><tbody>'+rows.map(x=>'<tr><td>#'+x.id+'</td><td>'+esc(AR?x.title_ar:x.title_en)+'</td><td>'+esc(x.content_type)+'</td><td>'+esc(x.category)+'</td><td>'+statusBadge(x.status)+'</td><td>'+x.version+'</td><td><button class="btn ghost small" onclick="openContentEditor('+x.id+')">✏️</button> <button class="btn danger small" onclick="removeContent('+x.id+')">🗑️</button></td></tr>').join('')+'</tbody></table>':'<div class="empty">'+txt('لا يوجد محتوى','No content')+'</div>';
}
function openContentEditor(id=null){
  const x=id?CONTENT.find(v=>v.id===id)||{}:{}; editing={kind:'content',id}; document.getElementById('modalTitle').textContent=id?txt('تعديل المحتوى','Edit content'):txt('إضافة محتوى','Add content');
  const types=['health_tip','faq','educational','mental_health','awareness','intro'].map(v=>'<option value="'+v+'">'+v.replaceAll('_',' ')+'</option>').join('');
  document.getElementById('formFields').innerHTML=field('Slug','slug',x.slug)+selectField('Type','content_type',types,x.content_type)+field('العنوان العربي','title_ar',x.title_ar)+field('English title','title_en',x.title_en)+field('النص العربي','body_ar',x.body_ar,'textarea',true)+field('English body','body_en',x.body_en,'textarea',true)+field('Category','category',x.category||'general')+selectField('Status','status','<option value="active">Active</option><option value="draft">Draft</option><option value="disabled">Disabled</option>',x.status);
  fillValues(x); document.getElementById('modal').classList.add('show');
}
async function removeContent(id){if(!confirm(txt('حذف هذا المحتوى؟','Delete this content?')))return;try{await req('/api/admin/content/'+id,{method:'DELETE',body:'{}'});await loadContent()}catch(e){alert(e.message)}}

async function openEditor(kind,id=null){
  editing={kind,id};let x={};
  try{
    if(id&&['disease','symptom','source','red_flag'].includes(kind)){const d=await req('/api/admin/'+(kind==='red_flag'?'red-flags':kind+'s')+'/'+id);x=d[kind]||d.red_flag||{}}
    else if(id&&kind==='relationship')x=(KB.relationships||[]).find(r=>r.id===id)||{};
    else if(id&&kind==='category')x=(KB.categories||[]).find(r=>r.id===id)||{};
  }catch(e){alert(e.message);return}
  document.getElementById('modalTitle').textContent=(id?txt('تعديل ','Edit '):txt('إضافة ','Add '))+kind;
  const status=selectField('Status','status','<option value="active">Active</option><option value="draft">Draft</option><option value="disabled">Disabled</option>',x.status);
  let h='';
  if(kind==='category')h=field('الاسم العربي','name_ar',x.name_ar)+field('English name','name_en',x.name_en)+field('Slug','slug',x.slug)+status;
  if(kind==='disease'){
    const selected=(x.sources||[]).map(v=>v.id); const verified=(KB.sources||[]).filter(v=>v.status==='active'&&v.verification_status==='verified');
    h=field('الاسم العربي','name_ar',x.name_ar)+field('English name','name_en',x.name_en)+field('الوصف العربي','description_ar',x.description_ar,'textarea',true)+field('English description','description_en',x.description_en,'textarea',true)+selectField('Category','category_id','<option value="">—</option>'+opts(KB.categories||[],c=>AR?c.name_ar:c.name_en),x.category_id)+selectField('Severity','severity','<option value="mild">Mild</option><option value="moderate">Moderate</option><option value="severe">Severe</option>',x.severity)+field('عوامل الخطورة','risk_factors_ar',x.risk_factors_ar,'textarea')+field('Risk factors','risk_factors_en',x.risk_factors_en,'textarea')+field('الأسباب الشائعة','common_causes_ar',x.common_causes_ar,'textarea')+field('Common causes','common_causes_en',x.common_causes_en,'textarea')+field('علامات الخطر','red_flags_ar',x.red_flags_ar,'textarea')+field('Red flags','red_flags_en',x.red_flags_en,'textarea')+field('Related diseases (comma separated)','related_diseases',(x.related_diseases||[]).join(', '),'text',true)+field('الخطوة التالية','recommended_next_step_ar',x.recommended_next_step_ar,'textarea')+field('Recommended next step','recommended_next_step_en',x.recommended_next_step_en,'textarea')+field('Last updated','last_updated',x.last_updated||new Date().toISOString().slice(0,10),'date')+selectField('Verified medical sources','source_ids',opts(verified,v=>v.source_name,'id',selected),'',true,true)+status;
  }
  if(kind==='symptom'){
    const selected=(x.sources||[]).map(v=>v.id); const verified=(KB.sources||[]).filter(v=>v.status==='active'&&v.verification_status==='verified');
    h=field('الاسم العربي','name_ar',x.name_ar)+field('English name','name_en',x.name_en)+field('الوصف العربي','description_ar',x.description_ar,'textarea',true)+field('English description','description_en',x.description_en,'textarea',true)+selectField('Category','category_id','<option value="">—</option>'+opts(KB.categories||[],c=>AR?c.name_ar:c.name_en),x.category_id)+field('Severity min','severity_min',x.severity_min||1,'number',false,'min="1" max="5"')+field('Severity max','severity_max',x.severity_max||5,'number',false,'min="1" max="5"')+field('Aliases AR (comma separated)','aliases_ar',(x.aliases_ar||[]).join(', '), 'text',true)+field('Aliases EN (comma separated)','aliases_en',(x.aliases_en||[]).join(', '),'text',true)+field('علامات الخطر','red_flags_ar',x.red_flags_ar,'textarea')+field('Red flags','red_flags_en',x.red_flags_en,'textarea')+selectField('Verified medical sources','source_ids',opts(verified,v=>v.source_name,'id',selected),'',true,true)+status;
  }
  if(kind==='source')h=field('Source name','source_name',x.source_name)+field('Organization','organization',x.organization)+field('Official HTTPS URL','official_url',x.official_url,'url',true)+field('الوصف','description_ar',x.description_ar,'textarea')+field('Description','description_en',x.description_en,'textarea')+selectField('Language','language','<option value="multiple">Arabic + English</option><option value="ar">Arabic</option><option value="en">English</option>',x.language)+selectField('Reliability','reliability_level','<option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>',x.reliability_level)+selectField('Source type','source_type','<option value="government">Government</option><option value="international_organization">International Organization</option><option value="national_health_service">National Health Service</option><option value="academic_medical_institution">Academic Medical Institution</option><option value="other_trusted_source">Other Trusted Source</option>',x.source_type)+selectField('Verification','verification_status','<option value="verified">Verified</option><option value="needs_review">Needs Review</option><option value="disabled">Disabled</option>',x.verification_status)+field('Last verified','last_verified',x.last_verified||new Date().toISOString().slice(0,10),'date')+field('Priority','priority',x.priority||50,'number')+status;
  if(kind==='relationship')h=selectField('Disease','disease_id',opts(KB.diseases||[],d=>AR?d.name_ar:d.name_en,'id',[x.disease_id]),x.disease_id)+selectField('Symptom','symptom_id',opts(KB.symptoms||[],v=>AR?v.name_ar:v.name_en,'id',[x.symptom_id]),x.symptom_id)+field('Relevance / Weight (0.1–1)','weight',x.weight||.5,'number',false,'min="0.1" max="1" step="0.05"')+selectField('Typicality','typicality','<option value="very_common">Very common</option><option value="common">Common</option><option value="less_common">Less common</option>',x.typicality)+field('ملاحظات','notes_ar',x.notes_ar,'textarea')+field('Notes','notes_en',x.notes_en,'textarea')+status;
  if(kind==='red_flag')h=field('الاسم العربي','name_ar',x.name_ar)+field('English name','name_en',x.name_en)+selectField('Required symptoms','required_symptoms',opts(KB.symptoms||[],v=>(AR?v.name_ar:v.name_en)+' — '+v.slug,'slug',x.required_symptoms||[]),'',true,true)+field('Keywords AR (comma separated)','keywords_ar',(x.keywords_ar||[]).join(', '),'text',true)+field('Keywords EN (comma separated)','keywords_en',(x.keywords_en||[]).join(', '),'text',true)+selectField('Match mode','match_mode','<option value="all">All</option><option value="any">Any</option>',x.match_mode)+field('Min severity','min_severity',x.min_severity||1,'number',false,'min="1" max="5"')+selectField('Risk','risk_level','<option value="urgent">Urgent</option><option value="review">Needs review</option>',x.risk_level)+field('رسالة الأمان','message_ar',x.message_ar,'textarea')+field('Safety message','message_en',x.message_en,'textarea')+selectField('Verified source','source_id',opts((KB.sources||[]).filter(v=>v.status==='active'&&v.verification_status==='verified'),v=>v.source_name,'id',[x.source_id]),x.source_id)+status;
  document.getElementById('formFields').innerHTML=h; fillValues(x); document.getElementById('modal').classList.add('show');
}
function fillValues(x){for(const [n,v] of Object.entries(x||{})){const el=document.querySelector('#editForm [name="'+n+'"]');if(el&&!['source_ids','required_symptoms'].includes(n)&&!Array.isArray(v))el.value=v??''}}
function closeModal(){document.getElementById('modal').classList.remove('show');document.getElementById('modalMsg').className='msg'}

document.getElementById('editForm').onsubmit=async e=>{
  e.preventDefault();const f=new FormData(e.target),p=Object.fromEntries(f.entries()),kind=editing.kind,id=editing.id;
  if(e.target.elements.source_ids)p.source_ids=[...e.target.elements.source_ids.selectedOptions].map(o=>+o.value);
  if(e.target.elements.required_symptoms)p.required_symptoms=[...e.target.elements.required_symptoms.selectedOptions].map(o=>o.value);
  ['aliases_ar','aliases_en','related_diseases','keywords_ar','keywords_en'].forEach(k=>{if(p[k]!=null)p[k]=String(p[k]).split(',').map(v=>v.trim()).filter(Boolean)});
  ['category_id','severity_min','severity_max','priority','min_severity','source_id','disease_id','symptom_id'].forEach(k=>{if(p[k])p[k]=+p[k];else if(k==='category_id')p[k]=null});
  if(p.weight)p.weight=+p.weight;
  let url,method=id?'PUT':'POST';
  if(kind==='content')url='/api/admin/content'+(id?'/'+id:'');
  else {const plural=kind==='red_flag'?'red-flags':kind==='relationship'?'relationships':kind==='category'?'categories':kind+'s';url='/api/admin/'+plural+(id?'/'+id:'')}
  try{await req(url,{method,body:JSON.stringify(p)});document.getElementById('modalMsg').className='msg ok show';document.getElementById('modalMsg').textContent=txt('تم الحفظ بنجاح','Saved successfully');if(kind==='content')await loadContent();else await loadKB();setTimeout(closeModal,450)}catch(err){document.getElementById('modalMsg').className='msg err show';document.getElementById('modalMsg').textContent=err.message}
};
async function removeItem(kind,id){
  if(!confirm(txt('هل أنت متأكد؟ للمحتوى الطبي المنشور يفضّل التعطيل بدل الحذف.','Are you sure? For published medical content, disabling is usually safer.')))return;
  const plural=kind==='red_flag'?'red-flags':kind==='relationship'?'relationships':kind==='category'?'categories':kind+'s';
  try{await req('/api/admin/'+plural+'/'+id,{method:'DELETE',body:'{}'});await loadKB()}catch(e){alert(e.message)}
}

async function loadUsers(){
  try{const rows=(await req('/api/admin/users')).users||[];document.getElementById('table-users').innerHTML=rows.length?'<table><thead><tr><th>User ID</th><th>'+txt('الحالة','Status')+'</th><th>Role</th><th>'+txt('تاريخ التسجيل','Registration Date')+'</th><th>'+txt('آخر دخول','Last Login')+'</th><th>'+txt('إجراء','Action')+'</th></tr></thead><tbody>'+rows.map(x=>'<tr><td>#'+x.id+'</td><td>'+statusBadge(x.status)+'</td><td><span class="badge '+(x.role==='admin'?'verified':'draft')+'">'+esc(x.role)+'</span></td><td>'+esc((x.created_at||'—').slice(0,16))+'</td><td>'+esc((x.last_login||'—').slice(0,16))+'</td><td><button class="btn '+(x.status==='active'?'danger':'ghost')+' small" '+(x.role==='admin'?'disabled':'')+' onclick="toggleUser('+x.id+',\''+(x.status==='active'?'disabled':'active')+'\')">'+(x.status==='active'?txt('تعطيل','Disable'):txt('تفعيل','Activate'))+'</button></td></tr>').join('')+'</tbody></table>':'<div class="empty">'+txt('لا يوجد مستخدمون','No users')+'</div>'}catch(e){alert(e.message)}
}
async function toggleUser(id,status){if(!confirm(txt('تأكيد تغيير حالة الحساب؟','Confirm account status change?')))return;try{await req('/api/admin/users/'+id+'/status',{method:'PUT',body:JSON.stringify({status})});await loadUsers()}catch(e){alert(e.message)}}

async function loadHealth(){
  try{const h=(await req('/api/admin/system-health')).health||{};document.getElementById('healthGrid').innerHTML=Object.entries(h.components||{}).map(([k,v])=>'<div class="health-item"><div style="display:flex;justify-content:space-between;gap:8px"><b>'+esc(k.replaceAll('_',' '))+'</b>'+statusBadge(v.status)+'</div><p class="muted" style="margin-top:7px">'+txt('زمن الاستجابة: ','Response time: ')+(v.response_ms??'—')+' ms<br>'+txt('آخر فحص: ','Last checked: ')+esc(h.checked_at||'—')+(v.error?'<br><span style="color:#991B1B">'+esc(v.error)+'</span>':'')+'</p></div>').join('')||'<div class="empty">'+txt('لا توجد بيانات','No data')+'</div>'}catch(e){alert(e.message)}
}
async function loadAudit(){
  try{const rows=(await req('/api/admin/audit?limit=180')).audit||[];document.getElementById('table-audit').innerHTML=rows.length?'<table><thead><tr><th>Admin</th><th>Action</th><th>Entity</th><th>ID</th><th>Previous Value</th><th>New Value</th><th>Timestamp</th></tr></thead><tbody>'+rows.map(x=>'<tr><td>'+esc(x.admin_email||('Admin #'+(x.admin_id||'—')))+'</td><td>'+esc(x.action)+'</td><td>'+esc(x.entity_type)+'</td><td>'+esc(x.entity_id||'—')+'</td><td class="audit-json" title="'+esc(x.previous_value||'')+'">'+esc(x.previous_value||'—')+'</td><td class="audit-json" title="'+esc(x.new_value||'')+'">'+esc(x.new_value||'—')+'</td><td>'+esc((x.timestamp||'').slice(0,19))+'</td></tr>').join('')+'</tbody></table>':'<div class="empty">'+txt('لا يوجد سجل بعد','No audit entries yet')+'</div>'}catch(e){alert(e.message)}
}

loadUsage(); loadKB();
setInterval(()=>{if(document.visibilityState==='visible'&&document.getElementById('view-overview')?.classList.contains('on'))loadUsage()},60000);
</script>
</body></html>
"""


@app.route("/")
def index():
    # Local preview only. Production uses webapp.py with real session checks.
    return render_template_string(
        DASHBOARD_HTML,
        admin_user={"email": "local-preview", "role": "admin"},
        csrf_token="local-preview", lang="ar",
    )


@app.route("/api/stats")
def api_stats():
    db.init_db()
    return jsonify({"stats": db.get_usage_stats(days=7), "feedback": db.feedback_counts(), "fb_comments": []})


def run_dashboard():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)


if __name__ == "__main__":
    run_dashboard()
