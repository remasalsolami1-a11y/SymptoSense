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
{% set requested_view = request.args.get('view', 'overview') %}
{% set settings_open = requested_view == 'adminsettings' %}
<!DOCTYPE html>
<html lang="{{ lang }}" dir="{{ 'rtl' if ar else 'ltr' }}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>SymptoSense — Admin Dashboard</title>
<script src="/static/js/mini-charts.js?v={{ asset_version }}"></script>
<script src="/static/js/interaction-bridge.js?v={{ asset_version }}" defer></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;600;700;800;900&family=Poppins:wght@400;600;700&display=swap');
:root{--p:#1565c0;--pd:#123B70;--pl:#EAF4FF;--sky:#64B5F6;--bg:#F5F9FF;--card:#fff;--line:#DCEBFA;--text:#40566F;--muted:#5F7185;--green:#166534;--greenbg:#ECFDF5;--yellow:#92400E;--yellowbg:#FFFBEB;--red:#991B1B;--redbg:#FEF2F2}
*{box-sizing:border-box;margin:0;padding:0;min-width:0}body{font-family:'Tajawal','Segoe UI',Tahoma,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}button,input,select,textarea{font:inherit}button{cursor:pointer}a{text-decoration:none;color:inherit}html[dir='ltr'] body{font-family:'Poppins','Tajawal','Segoe UI',sans-serif}html[dir='rtl'] body{font-family:'Tajawal','Segoe UI',Tahoma,sans-serif}
.top{position:sticky;top:0;z-index:40;background:rgba(255,255,255,.97);backdrop-filter:blur(14px);border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;gap:14px;padding:12px clamp(14px,3vw,34px)}
.brand{display:flex;align-items:center;gap:10px}.brand-ic{width:44px;height:44px;border-radius:14px;background:var(--pl);display:grid;place-items:center;font-size:22px}.brand b{font-family:'Poppins','Tajawal','Segoe UI',sans-serif;color:transparent;font-size:20px;font-weight:800;letter-spacing:-.5px;background:linear-gradient(98deg,#0A376D 0%,#0B477E 32%,#0E678C 56%,#11919D 78%,#18A7A5 100%);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}.brand b em{color:transparent;-webkit-text-fill-color:transparent;font-style:normal}.brand small{display:block;color:var(--muted);font-size:11px}
.user{display:flex;align-items:center;gap:8px;flex-wrap:wrap;justify-content:flex-end}.role{padding:5px 10px;border-radius:999px;background:var(--pl);color:var(--pd);font-size:11px;font-weight:800}.top-a{padding:7px 11px;border:1px solid var(--line);border-radius:10px;background:#fff;color:var(--pd);font-size:12px;font-weight:700}
.layout{display:grid;grid-template-columns:235px minmax(0,1fr);max-width:1480px;margin:auto;min-height:calc(100vh - 70px)}.side{padding:20px 12px;border-inline-end:1px solid var(--line);background:#fff}.nav-section{margin:16px 10px 6px;color:var(--muted);font-size:10px;font-weight:900;letter-spacing:.04em;text-transform:uppercase}.nav-section:first-child{margin-top:2px}.navbtn{width:100%;border:0;background:transparent;text-align:start;padding:11px 12px;border-radius:12px;color:var(--text);font-weight:700;margin:2px 0}.navbtn:hover,.navbtn.on{background:var(--pl);color:var(--p)}.nav-advanced{margin:12px 4px 4px;border:1px solid var(--line);border-radius:12px;background:#fbfdff;overflow:hidden}.nav-advanced summary{list-style:none;cursor:pointer;padding:10px 12px;color:var(--muted);font-size:11px;font-weight:900}.nav-advanced summary::-webkit-details-marker{display:none}.nav-advanced summary:after{content:'▾';float:inline-end}.nav-advanced[open] summary:after{content:'▴'}.nav-advanced .navbtn{font-size:12px;margin:0;border-radius:0;border-top:1px solid #edf4fa}.main{padding:clamp(18px,3vw,30px)}
.view{display:none}.view.on{display:block}.head{display:flex;align-items:flex-end;justify-content:space-between;gap:14px;margin-bottom:18px;flex-wrap:wrap}.head h1{color:var(--pd);font-size:clamp(22px,3.5vw,31px)}.head p{color:var(--muted);font-size:13px}.actions{display:flex;gap:8px;flex-wrap:wrap}.btn{border:0;border-radius:11px;padding:9px 15px;background:var(--p);color:#fff;font-weight:800;font-size:13px}.btn.ghost{background:#fff;color:var(--pd);border:1px solid var(--line)}.btn.danger{background:var(--redbg);color:var(--red);border:1px solid #FECACA}.btn.small{padding:6px 10px;font-size:11px}.btn:disabled{opacity:.45;cursor:not-allowed}
.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:20px}.stat{background:#fff;border:1px solid var(--line);border-radius:17px;padding:17px;box-shadow:0 5px 18px rgba(25,118,210,.05)}.stat strong{display:block;color:var(--p);font-size:27px}.stat span{color:var(--pd);font-size:12px;font-weight:800}.stat small{display:block;color:var(--muted);font-size:10px;margin-top:2px}
.pulse-hero{position:relative;overflow:hidden;background:linear-gradient(135deg,#0B3269 0%,#155D9A 55%,#1A8CC7 100%);color:#fff;border-radius:22px;padding:20px;margin-bottom:16px;box-shadow:0 18px 38px rgba(18,59,112,.16)}.pulse-hero:after{content:"";position:absolute;width:240px;height:240px;border-radius:50%;right:-70px;top:-110px;background:rgba(255,255,255,.09)}.pulse-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;position:relative;z-index:1}.pulse-head h2{color:#fff;margin:0;font-size:19px}.pulse-head p{margin-top:5px;color:rgba(255,255,255,.78);font-size:11px}.pulse-badge{padding:6px 10px;border-radius:999px;background:rgba(255,255,255,.13);border:1px solid rgba(255,255,255,.2);font-size:10px;font-weight:900}.pulse-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin-top:16px;position:relative;z-index:1}.pulse-stat{background:rgba(255,255,255,.11);border:1px solid rgba(255,255,255,.16);border-radius:15px;padding:12px;backdrop-filter:blur(8px)}.pulse-stat strong{display:block;font-size:24px;color:#fff;line-height:1.2}.pulse-stat span{display:block;margin-top:4px;font-size:10.5px;font-weight:800;color:rgba(255,255,255,.88)}.pulse-sections{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px}.pulse-panel{background:#fff;border:1px solid var(--line);border-radius:18px;padding:16px}.pulse-panel h3{font-size:14px;color:var(--pd);margin-bottom:10px}.pulse-mini{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.pulse-row{padding:10px 11px;border-radius:12px;background:#F8FBFF;border:1px solid #E5EFF8}.pulse-row b{display:block;font-size:18px;color:var(--p)}.pulse-row small{display:block;color:var(--muted);font-size:10px;margin-top:2px}.pulse-note{margin-top:10px;color:var(--muted);font-size:10px;line-height:1.7}@media(max-width:900px){.pulse-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.pulse-sections{grid-template-columns:1fr}}@media(max-width:520px){.pulse-grid,.pulse-mini{grid-template-columns:1fr 1fr}.pulse-stat strong{font-size:21px}}
.perf-shell{background:linear-gradient(135deg,#F8FBFF 0%,#EEF7FF 100%);border:1px solid #CFE4F8;border-radius:18px;padding:17px}.perf-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap}.perf-head h3{color:var(--pd);font-size:15px;margin:0}.perf-head p{color:var(--muted);font-size:10.5px;line-height:1.7;margin-top:4px}.perf-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:9px;margin-top:14px}.perf-metric{background:#fff;border:1px solid var(--line);border-radius:13px;padding:12px}.perf-metric strong{display:block;color:var(--pd);font-size:20px;line-height:1.25}.perf-metric span{display:block;color:var(--muted);font-size:9.5px;margin-top:4px;font-weight:700}.perf-compare{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}.perf-side{background:#fff;border:1px solid var(--line);border-radius:14px;padding:13px}.perf-side b{display:flex;justify-content:space-between;gap:8px;color:var(--pd);font-size:11px}.perf-track{height:10px;background:#EDF3F8;border-radius:999px;overflow:hidden;margin-top:10px}.perf-fill{height:100%;border-radius:999px;background:#78909C;min-width:2px}.perf-side.after .perf-fill{background:#1565c0}.perf-note{margin-top:10px;padding:9px 11px;border-radius:11px;background:#fff;border:1px dashed #C7DDF0;color:var(--muted);font-size:9.5px;line-height:1.7}.perf-empty{padding:18px;text-align:center;color:var(--muted);font-size:11px;line-height:1.8}.perf-status{font-size:10px;color:var(--muted);margin-top:7px}@media(max-width:900px){.perf-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.perf-compare{grid-template-columns:1fr}}@media(max-width:520px){.perf-grid{grid-template-columns:1fr 1fr}.perf-metric strong{font-size:18px}}
.ops-list{display:grid;gap:12px}.ops-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:16px;align-items:center;padding:15px;border:1px solid var(--line);border-radius:15px;background:#FBFDFF}.ops-copy{min-width:0}.ops-title{display:flex;align-items:center;gap:8px;flex-wrap:wrap;color:var(--pd);font-weight:800;font-size:14px}.ops-copy p{margin-top:5px;color:var(--muted);font-size:11px;line-height:1.7}.ops-note{margin-top:7px;color:var(--muted);font-size:11px;line-height:1.7;overflow-wrap:anywhere}.ops-actions{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}.ops-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:10px}.ops-stat{background:#fff;border:1px solid var(--line);border-radius:11px;padding:9px}.ops-stat strong{display:block;color:var(--p);font-size:18px}.ops-stat span{display:block;color:var(--muted);font-size:9px;margin-top:2px}.badge.neutral{background:#F1F5F9;color:#475569}@media(max-width:760px){.ops-row{grid-template-columns:1fr}.ops-actions{justify-content:flex-start}.ops-stats{grid-template-columns:repeat(2,minmax(0,1fr))}}
.card{background:#fff;border:1px solid var(--line);border-radius:18px;padding:18px;margin-bottom:16px;box-shadow:0 5px 20px rgba(25,118,210,.05)}.card h2{color:var(--pd);font-size:16px;margin-bottom:12px}.two{display:grid;grid-template-columns:1fr 1fr;gap:14px}.chart{height:250px;position:relative}.chart-empty{position:absolute;inset:0;display:none;place-items:center;text-align:center;padding:22px;color:var(--muted);font-size:12px;line-height:1.7;background:linear-gradient(180deg,rgba(255,255,255,.92),rgba(248,251,255,.96));border-radius:12px}
.toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:12px}.search{flex:1;min-width:220px;border:1px solid var(--line);background:#fff;border-radius:11px;padding:10px 12px;color:var(--text)}.filter{border:1px solid var(--line);background:#fff;border-radius:11px;padding:9px 10px;color:var(--text)}
.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:14px}table{width:100%;border-collapse:collapse;min-width:760px;background:#fff}th,td{padding:11px 12px;text-align:start;border-bottom:1px solid var(--line);font-size:12px;vertical-align:top}th{background:var(--pl);color:var(--pd);font-weight:800;position:sticky;top:0}tr:last-child td{border-bottom:0}.muted{color:var(--muted);font-size:11px}.empty{text-align:center;color:#94A3B8;padding:25px}.badge{display:inline-flex;padding:4px 8px;border-radius:999px;font-size:10px;font-weight:800}.active,.verified,.online{color:var(--green);background:var(--greenbg)}.draft,.needs_review,.review,.not_configured{color:var(--yellow);background:var(--yellowbg)}.disabled,.urgent,.offline{color:var(--red);background:var(--redbg)}
.modal-bg{display:none;position:fixed;inset:0;z-index:100;background:rgba(15,23,42,.55);padding:18px;align-items:center;justify-content:center}.modal-bg.show{display:flex}.modal{background:#fff;border-radius:20px;width:min(780px,100%);max-height:92vh;overflow:auto;box-shadow:0 30px 80px rgba(15,23,42,.3)}.modal-head{position:sticky;top:0;background:#fff;display:flex;align-items:center;justify-content:space-between;padding:16px 18px;border-bottom:1px solid var(--line);z-index:2}.modal-head h2{color:var(--pd);font-size:18px}.close{width:36px;height:36px;border:0;border-radius:10px;background:var(--pl);color:var(--pd);font-weight:900}.form{padding:18px}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.field{display:flex;flex-direction:column;gap:5px}.field.full{grid-column:1/-1}.field label{font-size:11px;color:var(--pd);font-weight:800}.field input,.field select,.field textarea{border:1px solid var(--line);border-radius:10px;padding:10px;color:var(--text);background:#fff}.field textarea{min-height:82px;resize:vertical}
#valVerified{width:18px!important;height:18px!important;padding:0!important;accent-color:var(--p)}
.form-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:16px}.msg{display:none;margin:0 18px 16px;padding:10px 12px;border-radius:11px;font-size:12px}.msg.show{display:block}.msg.ok{background:var(--greenbg);color:var(--green)}.msg.err{background:var(--redbg);color:var(--red)}
.health{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.health-item{border:1px solid var(--line);border-radius:14px;padding:14px}.health-item b{color:var(--pd)}.audit-json{max-width:360px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;direction:ltr;text-align:start}.data-actions{display:flex;gap:8px;flex-wrap:wrap}.export-status{font-size:12px;color:var(--muted);margin-top:8px}.graph-shell{height:520px;border:1px solid var(--line);border-radius:16px;background:linear-gradient(#fbfdff,#f4faff);position:relative;overflow:auto;cursor:grab;touch-action:none}.graph-shell.dragging{cursor:grabbing;user-select:none}.graph-stage{position:absolute;inset:0;transform-origin:0 0}.graph-node{position:absolute;min-width:110px;max-width:180px;padding:8px 10px;border:1px solid var(--line);border-radius:12px;background:#fff;box-shadow:0 5px 16px rgba(18,59,112,.08);font-size:11px}.graph-node.disease{border-color:#9dcaea}.graph-node.symptom{border-color:#b8dfca}.graph-node.red_flag{border-color:#efc4c4}.graph-node.source{border-color:#d9caef}.graph-edge{position:absolute;height:1px;background:#c8d9e6;transform-origin:left center;pointer-events:none}.graph-panel{margin-top:12px;padding:14px;border:1px solid var(--line);border-radius:14px;background:#fff}.insight-card{padding:15px;border:1px solid var(--line);border-radius:15px;background:#fff;margin:9px 0}.ask-box{display:flex;gap:8px}.ask-box textarea{flex:1;border:1px solid var(--line);border-radius:12px;padding:12px;min-height:84px}.ds-note{padding:12px;border-radius:12px;background:var(--pl);color:var(--pd);font-size:12px}
.analytics-filters{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}.analytics-filters label{display:flex;flex-direction:column;gap:5px;font-size:11px;font-weight:800;color:var(--pd)}.privacy-banner{padding:13px;border:1px solid var(--line);border-radius:14px;background:var(--pl);color:var(--pd);font-size:12px;line-height:1.7}.funnel-list{display:flex;flex-direction:column;gap:8px}.funnel-row{border:1px solid var(--line);border-radius:13px;padding:10px;background:#fff}.funnel-top{display:flex;justify-content:space-between;gap:12px;font-size:12px}.funnel-track{height:12px;background:#eef5fa;border-radius:999px;margin-top:7px;overflow:hidden}.funnel-fill{height:100%;background:var(--p);border-radius:999px}.live-feed{max-height:460px;overflow:auto}.live-event{display:grid;grid-template-columns:86px 1fr auto;gap:10px;padding:10px 0;border-bottom:1px solid var(--line);align-items:center}.live-event:last-child{border-bottom:0}.live-dot{width:9px;height:9px;border-radius:50%;background:#2b8a5e;display:inline-block;margin-inline-end:6px}.live-dot.err{background:#a33a3a}.export-preview{display:grid;grid-template-columns:repeat(5,1fr);gap:9px}.export-preview .stat strong{font-size:20px}@media(max-width:800px){.analytics-filters,.export-preview{grid-template-columns:1fr 1fr}}@media(max-width:520px){.analytics-filters,.export-preview{grid-template-columns:1fr}.live-event{grid-template-columns:72px 1fr}.live-event .badge{display:none}}
.heatmap-wrap{overflow:auto}.heatmap-grid{display:grid;gap:4px;min-width:620px;align-items:stretch}.heatmap-cell{min-height:48px;border-radius:9px;display:grid;place-items:center;padding:6px;text-align:center;font-size:11px;border:1px solid var(--line)}.heatmap-label{background:var(--pl);color:var(--pd);font-weight:800}.security-list{display:grid;gap:10px}.security-row{display:flex;justify-content:space-between;gap:16px;padding:12px;border:1px solid var(--line);border-radius:12px}.profile-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.profile-value{font-weight:800;color:var(--pd);word-break:break-word}
@media(max-width:1050px){.grid{grid-template-columns:repeat(2,1fr)}.layout{grid-template-columns:1fr}.side{position:sticky;top:69px;z-index:30;display:flex;gap:5px;overflow:auto;border-inline-end:0;border-bottom:1px solid var(--line);padding:8px}.nav-section{display:none}.navbtn{width:auto;white-space:nowrap;flex:0 0 auto}.main{padding:18px 12px}}
@media(max-width:700px){.top{align-items:flex-start}.brand small,.user>span:not(.role){display:none}.grid,.two,.health,.form-grid{grid-template-columns:1fr}.field.full{grid-column:auto}.main{padding:16px 10px}.card{padding:13px}.head{align-items:flex-start}.table-wrap{border:0}table{min-width:0}thead{display:none}tr{display:block;border:1px solid var(--line);border-radius:13px;margin-bottom:9px;padding:7px}td{display:flex;justify-content:space-between;gap:12px;border:0;padding:7px;font-size:12px}td:before{content:attr(data-label);font-weight:800;color:var(--pd)}.modal-bg{padding:7px}.modal{border-radius:15px}.user .top-a:first-of-type{display:none}}
.success{color:var(--green);background:var(--greenbg)}.failed{color:var(--red);background:var(--redbg)}.expired,.degraded{color:var(--yellow);background:var(--yellowbg)}
@media(max-width:700px){.profile-grid{grid-template-columns:1fr}}

/* Cross-device admin hardening. */
html{-webkit-text-size-adjust:100%;text-size-adjust:100%;max-width:100%;overflow-x:clip}
body{max-width:100%;overflow-x:hidden;min-height:100dvh}
img,svg,canvas{max-width:100%;height:auto}
.main,.view,.card,.two,.grid,.health,.profile-grid,.form-grid,.pulse-grid,.pulse-sections,.perf-grid,.perf-compare{min-width:0;max-width:100%}
.top{padding-left:max(clamp(14px,3vw,34px),env(safe-area-inset-left));padding-right:max(clamp(14px,3vw,34px),env(safe-area-inset-right));padding-top:max(12px,env(safe-area-inset-top))}
.side{scrollbar-width:thin;-webkit-overflow-scrolling:touch;overscroll-behavior-inline:contain}
.table-wrap,.heatmap-wrap,.graph-shell,.live-feed{max-width:100%;-webkit-overflow-scrolling:touch}
.modal-bg{overflow:auto;-webkit-overflow-scrolling:touch}.modal{max-width:calc(100vw - 24px);max-height:calc(100dvh - 24px)}
textarea{resize:vertical}.audit-json{max-width:100%;overflow-wrap:anywhere}.head>*,.toolbar>*,.security-row>*,.live-event>*{min-width:0}

@media(min-width:701px) and (max-width:1050px){
  .two,.pulse-sections{grid-template-columns:1fr!important}
  .grid,.pulse-grid,.perf-grid,.export-preview{grid-template-columns:repeat(2,minmax(0,1fr))!important}
  .main{padding-inline:16px}
}
@media(max-width:700px){
  input,select,textarea{font-size:16px!important}
  .top{gap:8px;flex-wrap:wrap;padding:9px max(10px,env(safe-area-inset-right)) 9px max(10px,env(safe-area-inset-left))}
  .brand{min-width:0}.brand b{font-size:17px}.brand-ic{width:38px;height:38px;border-radius:12px}
  .user{gap:6px;max-width:100%}.user>span:first-child{display:none}.top-a{padding:7px 9px}
  .side{top:62px;padding-left:max(8px,env(safe-area-inset-left));padding-right:max(8px,env(safe-area-inset-right))}
  .main{padding:14px max(9px,env(safe-area-inset-right)) 24px max(9px,env(safe-area-inset-left))}
  .head{gap:10px}.head h1{font-size:clamp(21px,7vw,28px)}
  .actions,.data-actions,.toolbar,.ask-box,.form-actions{width:100%}
  .actions>.btn,.data-actions>.btn,.data-actions>a.btn,.toolbar>.btn,.form-actions>.btn{flex:1 1 150px;text-align:center;justify-content:center}
  .search{min-width:0;flex:1 1 100%}.filter{flex:1 1 140px}
  .ask-box{flex-direction:column}.ask-box .btn{width:100%}
  .security-row{flex-direction:column;gap:8px}
  .chart{height:220px}
  .graph-shell{height:430px}
  .modal-bg{padding:6px}.modal{width:100%;max-width:100%;max-height:calc(100dvh - 12px);border-radius:14px}
  .modal-head,.form{padding:14px}
  td{overflow-wrap:anywhere;text-align:end}td:before{text-align:start;flex:0 0 42%;max-width:42%}
}
@media(max-width:520px){
  .pulse-grid,.pulse-mini,.perf-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important}
  .perf-compare{grid-template-columns:1fr!important}
  .live-event{grid-template-columns:64px minmax(0,1fr)!important}
  .chart{height:200px}
  .card{border-radius:15px}
}
@media(max-width:360px){
  .grid,.pulse-grid,.pulse-mini,.perf-grid,.export-preview{grid-template-columns:1fr!important}
  .role{display:none}.top-a{font-size:11px;padding:6px 8px}
  .navbtn{padding:10px;font-size:12px}
  .main{padding-inline:7px}.card{padding:11px}
  .btn{width:100%}.actions>.btn,.data-actions>.btn,.data-actions>a.btn,.form-actions>.btn{flex-basis:100%}
}
:where(a,button,input,select,textarea,[tabindex]):focus-visible{outline:3px solid #0B69C7!important;outline-offset:3px!important}
/* V66 exact mobile pass: 430 / 390 / 375 / 320 */
@media(max-width:430px){.top{padding-inline:9px}.brand b{font-size:16px}.brand small{font-size:9.5px}.user{width:auto}.user .role{display:none}.top-a{font-size:10.5px;padding:6px 8px}.side{gap:4px}.navbtn{font-size:11.5px;padding:9px 10px}.main{padding-inline:8px}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.stat{padding:13px 10px}.stat strong{font-size:23px}.head h1{font-size:24px}.head p{font-size:11.5px}.actions>.btn,.data-actions>.btn,.data-actions>a.btn{flex:1 1 100%;width:100%}.card{padding:12px}.perf-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important}}
@media(max-width:390px){.top{position:sticky}.brand-ic{display:none}.brand{gap:5px}.grid{grid-template-columns:1fr}.pulse-grid,.pulse-mini,.perf-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important}.main{padding-inline:7px}.card{border-radius:14px}.ops-row{padding:12px}.ops-actions{display:grid;grid-template-columns:1fr;width:100%}.ops-actions .btn{width:100%}}
@media(max-width:375px){.top-a{padding:6px 7px}.navbtn{font-size:11px}.head h1{font-size:22px}.chart{height:190px}.modal-head,.form{padding:12px}}
@media(max-width:320px){.brand b{font-size:14.5px}.brand small{display:none}.user{gap:4px}.top-a{font-size:9.5px;padding:5px 6px}.side{top:54px;padding-inline:5px}.navbtn{padding:8px 9px;font-size:10.5px}.main{padding:10px 5px 20px}.card{padding:10px}.pulse-grid,.pulse-mini,.perf-grid{grid-template-columns:1fr!important}.stat strong{font-size:21px}.btn{font-size:11.5px;padding:8px 10px}}
/* V69 admin typography/size consistency pass. */
button,.btn,.top-a,.navbtn{min-height:44px}.btn.small{min-height:40px}
.card,.stat,.pulse-panel,.perf-shell,.ops-row{border-radius:16px}
.perf-metric span,.perf-note,.ops-stat span{font-size:10.5px}
@media(max-width:430px){.brand small{font-size:10px}.top-a{font-size:10.5px;min-height:44px}.navbtn{min-height:44px}.perf-metric span,.perf-note,.ops-stat span{font-size:10px}}
@media(max-width:320px){.top-a{font-size:10px}.navbtn{font-size:10.5px}.btn{font-size:11.5px;min-height:44px}}
</style>
</head>
<body>
<header class="top">
  <div class="brand"><div class="brand-ic">❤️‍🩹</div><div><b>Sympto<em>Sense</em></b><small>{{ 'لوحة الإدارة' if ar else 'Admin Dashboard' }}</small></div></div>
  <div class="user"><span>{{ admin_user.email }}</span><span class="role">{{ admin_user.role }}</span><a class="top-a" href="/?choose=1&next=/admin">🌐 {{ 'EN' if ar else 'AR' }}</a><a class="top-a" href="/home">{{ 'الموقع' if ar else 'Site' }}</a><a class="top-a" href="/logout">{{ 'خروج' if ar else 'Sign out' }}</a></div>
</header>
<div class="layout">
<aside class="side" id="side">
  <div class="nav-section">{{ 'الأساس' if ar else 'Core' }}</div>
  <button type="button" class="navbtn{{ '' if settings_open else ' on' }}" data-view="overview">🏠 {{ 'الرئيسية' if ar else 'Overview' }}</button>
  <button type="button" class="navbtn" data-view="analytics">📊 {{ 'الاستخدام' if ar else 'Usage' }}</button>
  <button type="button" class="navbtn" data-view="quality">✅ {{ 'جودة التحليل' if ar else 'Analysis Quality' }}</button>
  <button type="button" class="navbtn" data-view="users">👥 {{ 'المستخدمون' if ar else 'Users' }}</button>
  <button type="button" class="navbtn" data-view="knowledge">🧠 {{ 'المعرفة والمصادر' if ar else 'Knowledge & Sources' }}</button>
  <button type="button" class="navbtn" data-view="contentgaps">🧩 {{ 'فجوات المحتوى' if ar else 'Content Gaps' }}</button>
  <button type="button" class="navbtn" data-view="production">🚦 {{ 'السلامة والجاهزية' if ar else 'Safety & Readiness' }}</button>
  <a class="navbtn{{ ' on' if settings_open else '' }}" data-view="adminsettings" href="/admin?view=adminsettings#labTrialCleanupCard">⚙️ {{ 'الإعدادات' if ar else 'Settings' }}</a>
  <a class="navbtn" href="/admin/analysis-trials">📊 {{ 'ملفات Excel للتجارب' if ar else 'Trial Excel Files' }}</a>
  <a class="navbtn" href="/home" style="display:block;margin-top:12px;border-top:1px solid var(--line);padding-top:16px">← {{ 'العودة إلى SymptoSense' if ar else 'Back to SymptoSense' }}</a>
</aside>
<main class="main">
  <section class="view{{ '' if settings_open else ' on' }}" id="view-overview">
    <div class="head"><div><h1>{{ 'لوحة التحكم' if ar else 'Admin Dashboard' }}</h1><p>{{ 'المؤشرات الأهم فقط: الاستخدام، قوة المعرفة، سلامة المحتوى، والتقييمات.' if ar else 'Only the signals that matter most: usage, knowledge strength, content safety, and feedback.' }}</p></div><div class="data-actions"><button class="btn ghost" type="button" id="allResultsBtn">📋 {{ 'عرض جميع نتائج التحليلات' if ar else 'All analysis results' }}</button><a class="btn" href="/admin/clinical-review">🩺 {{ 'مراجعة المحتوى الطبي' if ar else 'Clinical review' }}</a><a class="btn" href="/admin/competition-dashboard">✨ {{ 'لوحة المسابقة' if ar else 'Competition Dashboard' }}</a><button class="btn ghost" type="button" id="overviewRefreshBtn">🔄 {{ 'تحديث' if ar else 'Refresh' }}</button></div></div>
    <div class="grid" id="overviewStats"></div>
    <div class="card" id="projectStrengthCard"><div class="head" style="margin-bottom:10px"><div><h2 style="margin:0">🛡️ {{ 'قوة SymptoSense بالأرقام' if ar else 'SymptoSense Strength at a Glance' }}</h2><p class="muted" style="margin-top:5px">{{ 'قياسات مباشرة للتغطية والمصادر وقواعد السلامة؛ لا تمثل دقة تشخيصية أو تحققًا سريريًا.' if ar else 'Live coverage, source, and safety metrics; they are not diagnostic-accuracy or clinical-validation claims.' }}</p></div><button class="btn ghost small" type="button" id="knowledgeDetailsBtn">{{ 'التفاصيل' if ar else 'Details' }} ←</button></div><div class="grid" id="projectStrengthStats" style="margin-bottom:8px"></div><div class="muted" id="projectStrengthNote"></div></div>
    <div class="two"><div class="card"><h2>{{ 'النشاط خلال 30 يومًا' if ar else 'Activity — 30 days' }}</h2><div class="chart"><canvas id="visChart"></canvas></div></div><div class="card"><h2>⭐ {{ 'التقييمات' if ar else 'Feedback' }}</h2><div class="grid" id="feedbackStats" style="grid-template-columns:repeat(2,minmax(0,1fr));margin-bottom:0"></div><p class="muted" style="margin-top:10px">{{ 'تعليقات مجهولة الهوية؛ لا تعرض بيانات صحية أو تعريفية.' if ar else 'Anonymous feedback only; no health or identifying data is shown.' }}</p></div></div>
  </section>

  <section class="view" id="view-results">
    <div class="head"><div><h1>📋 {{ 'جميع نتائج التحليلات' if ar else 'All Analysis Results' }}</h1><p>{{ 'عرض بحثي مجهول الهوية للنتائج المحفوظة التي وافق أصحابها بشكل مستقل على المشاركة في البحث العلمي، بدون أسماء أو بريد أو محادثات أو موقع دقيق.' if ar else 'De-identified research view of saved records with separate scientific-research consent, without names, email, chats, or precise location.' }}</p></div><div class="actions"><button type="button" class="btn" data-ss-click="exportData">📥 {{ 'تصدير البحث' if ar else 'Export Research Data' }}</button><button type="button" class="btn ghost" data-ss-click="loadAnalysisResults" data-ss-args="[1]">🔄 {{ 'تحديث' if ar else 'Refresh' }}</button></div></div>
    <div class="privacy-banner">🔒 {{ 'تظهر هنا فقط التحليلات التي وافق أصحابها بشكل مستقل على المشاركة في البحث العلمي. المعرّفات مجهولة وثابتة للربط البحثي، ولا تظهر البيانات التعريفية المباشرة.' if ar else 'Only analyses with separate scientific-research consent appear here. Stable pseudonymous IDs support research linkage without exposing direct identifiers.' }}</div>
    <div class="grid" id="analysisResultsStats" style="margin-top:14px"></div>
    <div class="card">
      <div class="toolbar">
        <input id="analysisResultsSearch" class="search" placeholder="{{ 'ابحث بالعرض، الاحتمال، معرّف التحليل...' if ar else 'Search symptom, possibility, analysis ID...' }}" data-ss-keydown="loadAnalysisResults" data-ss-key="Enter" data-ss-args="[1]">
        <select id="analysisResultsRisk" class="filter" data-ss-change="loadAnalysisResults" data-ss-args="[1]"><option value="">{{ 'كل مستويات الخطورة' if ar else 'All risk levels' }}</option><option value="low">{{ 'منخفض' if ar else 'Low Risk' }}</option><option value="medium">{{ 'يحتاج مراجعة' if ar else 'Needs Review' }}</option><option value="high">{{ 'عاجل' if ar else 'Urgent' }}</option></select>
        <select id="analysisResultsLang" class="filter" data-ss-change="loadAnalysisResults" data-ss-args="[1]"><option value="">{{ 'كل اللغات' if ar else 'All languages' }}</option><option value="ar">العربية</option><option value="en">English</option></select>
        <button type="button" class="btn ghost" data-ss-click="loadAnalysisResults" data-ss-args="[1]">🔎 {{ 'بحث' if ar else 'Search' }}</button>
      </div>
      <div class="table-wrap" id="analysisResultsTable"></div>
      <div class="data-actions" id="analysisResultsPager" style="justify-content:center;margin-top:12px"></div>
    </div>
    <div class="card" id="analysisResultDetails" style="display:none"></div>
  </section>

  <section class="view" id="view-analytics">
    <div class="head"><div><h1>📈 {{ 'تحليلات الاستخدام' if ar else 'Usage analytics' }}</h1><p>{{ 'بيانات تشغيل مجمعة فقط؛ لا أعراض ولا محادثات ولا نتائج صحية شخصية.' if ar else 'Aggregate operational data only—no symptoms, chats, or personal health results.' }}</p></div><div class="actions"><select class="filter" id="analyticsDays" data-ss-change="loadV2Analytics"><option value="7">7 days</option><option value="30" selected>30 days</option><option value="90">90 days</option></select><button type="button" class="btn ghost" data-ss-click="loadV2Analytics">🔄</button></div></div>
    <div class="grid" id="v2AnalyticsStats"></div>
    <div class="two"><div class="card"><h2>{{ 'الخدمات الأكثر استخدامًا' if ar else 'Most-used services' }}</h2><div id="v2Services"></div></div><div class="card"><h2>{{ 'اللغة والجهاز' if ar else 'Language and device' }}</h2><div id="v2Segments"></div></div></div>
    <div class="two"><div class="card"><h2>{{ 'المستخدمون بمرور الوقت' if ar else 'Users over time' }}</h2><div class="chart"><canvas id="usersTimeline"></canvas></div></div><div class="card"><h2>{{ 'التحليلات بمرور الوقت' if ar else 'Analyses over time' }}</h2><div class="chart"><canvas id="analysesTimeline"></canvas></div></div></div>
    <div class="two"><div class="card"><h2>{{ 'استخدام المساعد الذكي' if ar else 'AI Assistant use' }}</h2><div class="chart"><canvas id="assistantTimeline"></canvas></div></div><div class="card"><h2>{{ 'أكثر الأعراض إدخالًا' if ar else 'Most-entered symptoms' }}</h2><div id="topSymptoms"></div></div></div>
    <div class="card"><h2>{{ 'النشاط العام' if ar else 'Overall activity' }}</h2><div class="chart"><canvas id="v2Timeline"></canvas></div></div>
    <div class="card"><h2>{{ 'الأقسام الأكثر زيارة' if ar else 'Most-visited sections' }}</h2><div class="table-wrap" id="v2Sections"></div></div>
  </section>

  <section class="view" id="view-quality">
    <div class="head"><div><h1>✅ {{ 'لوحة جودة التحليل' if ar else 'Analysis Quality Dashboard' }}</h1><p>{{ 'مؤشرات تشغيلية للتحقق من اكتمال القراءة، تغطية المصادر، واختبارات محرك الأمان. لا تمثل دقة تشخيصية أو تحققًا سريريًا.' if ar else 'Operational verification metrics for read completeness, source coverage, and safety-engine regression tests. These are not diagnostic-accuracy or clinical-validation claims.' }}</p></div><div class="actions"><select class="filter" id="qualityDays"><option value="7">7 days</option><option value="30" selected>30 days</option><option value="90">90 days</option></select><button type="button" class="btn ghost" id="qualityRefreshBtn">🔄 {{ 'تحديث' if ar else 'Refresh' }}</button></div></div>
    <div class="privacy-banner">🔒 {{ 'تعرض هذه اللوحة أرقامًا مجمعة فقط ولا تعرض أعراض المستخدمين أو قيم التحاليل أو بيانات التعريف.' if ar else 'This dashboard shows aggregate metrics only and does not expose symptoms, lab values, or identifying data.' }}</div>
    <div class="two" style="margin-top:14px">
      <div class="card"><h2>🩺 {{ 'جودة تحليل الأعراض' if ar else 'Symptom-analysis quality' }}</h2><div class="grid" id="qualitySymptomStats" style="margin-top:12px"></div><div id="qualitySafety" style="margin-top:12px"></div></div>
      <div class="card"><h2>🧪 {{ 'جودة تحليل الدم' if ar else 'Lab-analysis quality' }}</h2><div class="grid" id="qualityBloodStats" style="margin-top:12px"></div><div id="qualityCompleteness" style="margin-top:12px"></div></div>
    </div>
    <div class="card"><h2>📚 {{ 'التغطية بالمصادر والاكتمال' if ar else 'Source & completeness coverage' }}</h2><div class="grid" id="qualityCoverageStats" style="margin-top:12px"></div><p class="muted" id="qualityNotes" style="margin-top:12px"></p></div>
  </section>

  <section class="view" id="view-healthanalytics">
    <div class="head"><div><h1>🩺 {{ 'تحليل بيانات الأعراض' if ar else 'Symptom Analytics' }}</h1><p>{{ 'إحصاءات وصفية من السجلات الموافق على استخدامها، مع إخفاء المجموعات الصغيرة.' if ar else 'Descriptive statistics from consent-eligible records with small-cohort suppression.' }}</p></div><button type="button" class="btn ghost" data-ss-click="loadHealthAnalytics">🔄</button></div>
    <div class="privacy-banner" id="healthAnalyticsNotice"></div><div class="grid" id="healthAnalyticsStats" style="margin-top:14px"></div>
    <div class="card"><div class="head" style="margin-bottom:10px"><div><h2 style="margin:0">🧪 {{ 'جاهزية بيانات البحث' if ar else 'Research Data Readiness' }}</h2><p class="muted" style="margin-top:5px">{{ 'يوضح حجم العينة المتاح وجودة العرض للبحث الوصفي؛ لا يعني صلاحية الاستدلال السريري أو إثبات السببية.' if ar else 'Shows sample availability for descriptive research; it does not establish clinical validity, causal inference, or adequate statistical power.' }}</p></div><button type="button" class="btn ghost" data-ss-click="show" data-ss-args="[&quot;dataexport&quot;]">📥 {{ 'ملف البحث' if ar else 'Research export' }}</button></div><div class="grid" id="researchReadiness" style="margin-bottom:0"></div></div>
    <div class="two"><div class="card"><h2>{{ 'الأعراض الأكثر تسجيلًا' if ar else 'Most Reported Symptoms' }}</h2><div class="chart"><canvas id="healthSymptomsChart"></canvas></div></div><div class="card"><h2>{{ 'توزيع الشدة' if ar else 'Severity Distribution' }}</h2><div class="chart"><canvas id="healthSeverityChart"></canvas></div></div></div>
    <div class="two"><div class="card"><h2>{{ 'توزيع المدة' if ar else 'Duration Distribution' }}</h2><div class="chart"><canvas id="healthDurationChart"></canvas></div></div><div class="card"><h2>{{ 'مستويات الخطورة' if ar else 'Risk Level Distribution' }}</h2><div class="chart"><canvas id="healthRiskChart"></canvas></div></div></div>
    <div class="two"><div class="card"><h2>{{ 'الفئات العمرية' if ar else 'Age Group Patterns' }}</h2><div class="chart"><canvas id="healthAgeChart"></canvas></div></div><div class="card"><h2>{{ 'توزيع الجنس' if ar else 'Gender Distribution' }}</h2><div class="chart"><canvas id="healthGenderChart"></canvas></div></div></div>
    <div class="privacy-banner">{{ 'هذه التحليلات وصفية فقط ولا تثبت أن عرضًا يسبب مرضًا.' if ar else 'These analytics are descriptive only and do not establish that a symptom causes a disease.' }}</div>
  </section>

  <section class="view" id="view-medications">
    <div class="head"><div><h1>💊 {{ 'تحليل الأدوية المبلغ عنها' if ar else 'Medication Analytics' }}</h1><p>{{ 'أنماط مجمعة لما أبلغ عنه المستخدمون فقط، وليست توصيات علاجية.' if ar else 'Aggregate user-reported patterns only—not treatment recommendations.' }}</p></div><button type="button" class="btn ghost" data-ss-click="loadMedicationAnalytics">🔄</button></div>
    <div class="privacy-banner" id="medicationNotice"></div><div class="grid" id="medicationStats" style="margin-top:14px"></div>
    <div class="two"><div class="card"><h2>{{ 'الأدوية الأكثر تسجيلًا' if ar else 'Most Used Medications' }}</h2><div class="chart"><canvas id="medicationChart"></canvas></div></div><div class="card"><h2>{{ 'الدواء الأكثر تسجيلًا حسب العمر' if ar else 'Medication by Age Group' }}</h2><div id="medicationAge"></div></div></div>
    <div class="card"><h2>{{ 'أنماط الاستخدام عبر الوقت' if ar else 'Reported Usage Trends' }}</h2><div class="chart"><canvas id="medicationTrendChart"></canvas></div></div>
  </section>

  <section class="view" id="view-privacyanalytics">
    <div class="head"><div><h1>🔐 {{ 'تحليلات صحية مجهولة' if ar else 'Anonymous Health Analytics' }}</h1><p>{{ 'تستخدم هذه الشاشة فقط السجلات التي وافق أصحابها على Analytics، وتخفي المجموعات الأصغر من حد الخصوصية.' if ar else 'This view uses only records whose owners granted Analytics consent and suppresses groups below the privacy threshold.' }}</p></div><button type="button" class="btn ghost" data-ss-click="loadPrivacyAnalytics">🔄</button></div>
    <div class="grid" id="privacyAnalyticsStats"></div>
    <div class="card"><h2>{{ 'نظرة على موافقات البيانات' if ar else 'Data Consent Overview' }}</h2><div class="grid" id="consentStats" style="margin-bottom:0"></div></div>
    <div class="two"><div class="card"><h2>{{ 'الأعراض الأكثر تسجيلًا' if ar else 'Most Reported Symptoms' }}</h2><div id="privacySymptoms"></div></div><div class="card"><h2>{{ 'توزيع الفئات العمرية' if ar else 'Age Group Distribution' }}</h2><div id="privacyAges"></div></div></div>
    <div class="two"><div class="card"><h2>{{ 'أنماط الأدوية المسجلة' if ar else 'Medication Patterns' }}</h2><div id="privacyMeds"></div></div><div class="card"><h2>{{ 'توزيع مستوى الخطورة' if ar else 'Risk Distribution' }}</h2><div id="privacyRisk"></div></div></div>
    <div class="privacy-banner" id="privacyThresholdNote"></div>
  </section>

  <section class="view" id="view-production">
    <div class="head"><div><h1>🚦 {{ 'جاهزية التشغيل' if ar else 'Operational Readiness' }}</h1><p>{{ 'حالة المكونات الأساسية واختبارات الاتصال في مكان واحد بدون تكرار.' if ar else 'Core component health and live connectivity checks in one place without duplication.' }}</p></div><button class="btn ghost" id="productionRefreshBtn" type="button">🔄 {{ 'إعادة الفحص' if ar else 'Run checks' }}</button></div>
    <div class="grid" id="productionStats"></div>
    <div class="card" id="databasePerformanceCard"><div class="perf-shell"><div class="perf-head"><div><h3>⚡ {{ 'دليل الأداء القابل للقياس — Before / After' if ar else 'Measured Performance Evidence — Before / After' }}</h3><p>{{ 'اختبار فعلي لنفس الاستعلام على نفس PostgreSQL لقياس أثر Connection Pooling.' if ar else 'A real same-query benchmark against the same PostgreSQL database to measure the effect of connection pooling.' }}</p></div><div class="data-actions"><button class="btn small" id="runPerfBenchmarkBtn" type="button">▶ {{ 'تشغيل قياس سريع' if ar else 'Run Quick Benchmark' }}</button><button class="btn ghost small" id="refreshPerfBenchmarkBtn" type="button">↻ {{ 'تحديث' if ar else 'Refresh' }}</button></div></div><div id="performanceBenchmark"><div class="perf-empty">{{ 'جاري تحميل آخر قياس محفوظ…' if ar else 'Loading latest saved benchmark…' }}</div></div><div id="performanceBenchmarkStatus" class="perf-status"></div></div></div>
    <div class="card"><div class="head" style="margin-bottom:10px"><div><h2 style="margin:0">{{ 'مكونات التشغيل الأساسية' if ar else 'Core production components' }}</h2><p class="muted" style="margin-top:5px">{{ 'الحالات التي لها اختبار عملي مستقل أدناه لا تتكرر هنا.' if ar else 'Items with dedicated live checks below are not repeated here.' }}</p></div></div><div id="productionComponents" class="health"></div></div>
    <div class="card">
      <div class="head" style="margin-bottom:12px"><div><h2 style="margin:0">🧪 {{ 'اختبارات الاتصال والتشغيل' if ar else 'Live connectivity checks' }}</h2><p class="muted" style="margin-top:5px">{{ 'اختبارات آمنة ومباشرة للبريد، السجلات التقنية، وتذكيرات الجرعات عبر البريد.' if ar else 'Safe live checks for email, technical logging, and medication reminder delivery.' }}</p></div></div>
      <div class="ops-list">
        <div class="ops-row">
          <div class="ops-copy"><div class="ops-title">📧 {{ 'البريد' if ar else 'Email' }} <span id="emailCheckBadge" class="badge neutral">—</span></div><p>{{ 'يرسل رسالة عامة إلى بريد Admin فقط. لا تحتوي على بيانات صحية.' if ar else 'Sends a generic message only to the Admin inbox; no health data is included.' }}</p><div id="productionEmailNote" class="ops-note"></div></div>
          <div class="ops-actions"><button class="btn" id="productionEmailTestBtn" type="button">📨 {{ 'إرسال اختبار' if ar else 'Send test' }}</button><button class="btn ghost" id="confirmEmailDeliveryBtn" type="button">✓ {{ 'وصلتني الرسالة' if ar else 'I received it' }}</button></div>
        </div>
        <div class="ops-row">
          <div class="ops-copy"><div class="ops-title">🛡️ {{ 'السجلات ومراقبة الأخطاء' if ar else 'Logs & error monitoring' }} <span id="sentryCheckBadge" class="badge neutral">—</span></div><p>{{ 'سجلات Railway تعمل دائمًا. Sentry تكامل خارجي اختياري ويمكن اختباره فقط إذا كان SENTRY_DSN مضبوطًا.' if ar else 'Railway/application logs are always available. Sentry is optional and can be tested only when SENTRY_DSN is configured.' }}</p><div id="sentryVerificationNote" class="ops-note"></div></div>
          <div class="ops-actions"><button class="btn ghost" id="sentryTestBtn" type="button">🧪 {{ 'اختبار Sentry' if ar else 'Test Sentry' }}</button></div>
        </div>
        <div class="ops-row">
          <div class="ops-copy"><div class="ops-title">📧 {{ 'تذكيرات الأدوية عبر البريد' if ar else 'Medication reminders by email' }} <span id="medEmailCheckBadge" class="badge neutral">—</span></div><p>{{ 'القناة الوحيدة لتذكيرات الجرعات هي البريد الإلكتروني المسجّل بالحساب؛ لا يستخدم النظام Web Push لهذه الميزة.' if ar else 'Medication dose reminders use the account email only; this feature no longer uses Web Push.' }}</p><div id="medEmailVerificationStats" class="ops-stats"></div><div id="medEmailVerificationNote" class="ops-note"></div></div>
          <div class="ops-actions"><button class="btn ghost" id="medEmailRefreshBtn" type="button" aria-label="Refresh">↻</button></div>
        </div>
      </div>
    </div>
  </section>

  <section class="view" id="view-validation">
    <div class="head"><div><h1>🧪 {{ 'التحقق البحثي المستقل' if ar else 'Independent Research Validation' }}</h1><p>{{ 'قارن نتيجة SymptoSense بإجابة مرجعية مستقلة ضمن بروتوكول واضح وقابل للتصدير والمراجعة.' if ar else 'Compare SymptoSense output with an independent reference under a clear, exportable review protocol.' }}</p></div><div class="actions"><button type="button" class="btn ghost" data-ss-click="downloadValidation" data-ss-args="[&quot;blinded&quot;]">🙈 {{ 'نموذج مراجعة مستقل' if ar else 'Blinded reviewer export' }}</button><button type="button" class="btn ghost" data-ss-click="downloadValidation" data-ss-args="[&quot;results&quot;]">📊 {{ 'تصدير النتائج' if ar else 'Export results' }}</button><button type="button" class="btn" data-ss-click="openValidationEditor">＋ {{ 'إضافة حالة تحقق' if ar else 'Add validation case' }}</button></div></div>
    <div class="privacy-banner">{{ 'الحالات الأولية مجرد قوالب للاختبار وليست حقيقة سريرية معتمدة. استخدم «نموذج مراجعة مستقل» لإخفاء نتيجة النظام عن المراجع قدر الإمكان، ثم وثّق المرجع وصفة المراجع قبل إدخال الحالة في المقاييس.' if ar else 'Starter cases are workflow templates, not clinical ground truth. Use the blinded reviewer export to keep system output hidden from the reference reviewer where practical, then document the reviewer and source before including a case in metrics.' }}</div>
    <div class="card"><div class="head" style="margin-bottom:10px"><div><h2 style="margin:0">🔒 {{ 'تجميد نسخة الدراسة' if ar else 'Research Version Freeze' }}</h2><p class="muted" style="margin-top:5px">{{ 'يثبت إصدار التطبيق وبصمة محرك تحليل الأعراض. إذا تغير المحرك بعد بدء الدراسة ستظهر حالة عدم تطابق بوضوح.' if ar else 'Pins the app release and symptom-triage engine fingerprint. Any later engine change is surfaced as a reproducibility mismatch.' }}</p></div><button type="button" class="btn" id="freezeResearchBtn" data-ss-click="freezeResearchStudy">🔒 {{ 'تجميد النسخة الحالية' if ar else 'Freeze current version' }}</button></div><div id="researchStudyFreeze" class="export-status"></div></div>
    <div class="grid" id="validationStats" style="margin-top:14px"></div>
    <div class="card" id="validationProtocol"></div>
    <div class="card"><div class="table-wrap" id="validationTable"></div></div>
  </section>

  <section class="view" id="view-dataexport">
    <div class="head"><div><h1>📊 {{ 'مركز التصدير والبحث' if ar else 'Research & Export Center' }}</h1><p>{{ 'ملفات منظمة للبحث وتحليل البيانات مع الحفاظ على الخصوصية وربط الجداول بمعرّفات مجهولة ثابتة.' if ar else 'Research-ready exports with stable pseudonymous IDs and privacy-preserving linkage across sheets.' }}</p></div></div>
    <div class="privacy-banner"><b>{{ 'تنبيه:' if ar else 'Important:' }}</b> {{ 'التصدير البحثي يشمل فقط السجلات ذات الموافقة البحثية المنفصلة ومن عمر 18 سنة فأكثر، ويستبعد البريد والأسماء وكلمات المرور والمحادثات والموقع الدقيق والتعليقات النصية الحرة.' if ar else 'The research export includes separately research-consented records from participants aged 18+ only and excludes email, names, passwords, chats, exact location, and raw free-text feedback comments.' }}</div>
    <div class="card" style="margin-top:14px"><div class="head" style="margin-bottom:12px"><div><h2>{{ 'ملف البحث العلمي' if ar else 'Scientific Research Workbook' }}</h2><p class="muted">{{ 'ملف مختصر للبحث العلمي فقط: ملخص الدراسة، المشاركون، تحليلات الأعراض مع النتائج، وقاموس المتغيرات.' if ar else 'A concise scientific dataset only: study overview, participants, symptom analyses with results, and a research dictionary.' }}</p></div><button type="button" class="btn" data-ss-click="exportData">📥 {{ 'تحميل ملف البحث' if ar else 'Download Research Workbook' }}</button> <button class="btn ghost" type="button" data-ss-click="exportPilotWorkbook">🧪 {{ 'بيانات التجربة المنفصلة' if ar else 'Separate Pilot Data' }}</button></div><div class="grid" style="margin-bottom:0"><div class="stat"><strong>4</strong><span>{{ 'أوراق بحثية فقط' if ar else 'Research sheets only' }}</span></div><div class="stat"><strong>↔</strong><span>{{ 'ربط مجهول بين المشاركين والتحليلات' if ar else 'Pseudonymous participant-analysis linkage' }}</span></div><div class="stat"><strong>🔒</strong><span>{{ 'السجلات المؤهلة فقط' if ar else 'Eligible records only' }}</span></div><div class="stat"><strong>📖</strong><span>{{ 'قاموس متغيرات وحدود الاستخدام' if ar else 'Variable dictionary & limitations' }}</span></div></div><div id="researchExportStatus" class="export-status"></div></div>
    <div class="card"><h2>{{ 'تقرير تحليلات الأدوية المفلتر' if ar else 'Filtered Medication Analytics Report' }}</h2><p class="muted" style="margin-bottom:12px">{{ 'استخدم الفلاتر أدناه إذا كنت تريد تقريرًا وصفيًا مخصصًا للأدوية والاقترانات والاتجاهات.' if ar else 'Use the filters below when you need a descriptive medication-focused report with associations and trends.' }}</p><div class="analytics-filters">
      <label>{{ 'الفترة' if ar else 'Date range' }}<select class="filter" id="aePeriod" data-ss-change="toggleExportDates auditUI" data-ss-multi data-ss-args="[[],[&quot;changed_analytics_filters&quot;,&quot;dataexport&quot;]]"><option value="7d">{{ 'آخر 7 أيام' if ar else 'Last 7 days' }}</option><option value="30d" selected>{{ 'آخر 30 يومًا' if ar else 'Last 30 days' }}</option><option value="90d">{{ 'آخر 3 أشهر' if ar else 'Last 3 months' }}</option><option value="180d">{{ 'آخر 6 أشهر' if ar else 'Last 6 months' }}</option><option value="all">{{ 'كل البيانات المتاحة' if ar else 'All available data' }}</option><option value="custom">{{ 'فترة مخصصة' if ar else 'Custom range' }}</option></select></label>
      <label id="aeStartWrap" style="display:none">{{ 'من' if ar else 'Start' }}<input class="filter" type="date" id="aeStart" data-ss-change="auditUI" data-ss-args="[&quot;changed_analytics_filters&quot;,&quot;dataexport&quot;]"></label><label id="aeEndWrap" style="display:none">{{ 'إلى' if ar else 'End' }}<input class="filter" type="date" id="aeEnd" data-ss-change="auditUI" data-ss-args="[&quot;changed_analytics_filters&quot;,&quot;dataexport&quot;]"></label>
      <label>{{ 'الفئة العمرية' if ar else 'Age group' }}<select class="filter" id="aeAge" data-ss-change="auditUI" data-ss-args="[&quot;changed_analytics_filters&quot;,&quot;dataexport&quot;]"><option value="">{{ 'الكل' if ar else 'All' }}</option><option value="Under 18">{{ 'أقل من 18' if ar else 'Under 18' }}</option><option value="18–25">18–25</option><option value="26–35">26–35</option><option value="36–45">36–45</option><option value="46–55">46–55</option><option value="56+">56+</option></select></label>
      <label>{{ 'الجنس' if ar else 'Gender' }}<select class="filter" id="aeGender" data-ss-change="auditUI" data-ss-args="[&quot;changed_analytics_filters&quot;,&quot;dataexport&quot;]"><option value="">{{ 'الكل' if ar else 'All' }}</option><option value="Female">{{ 'أنثى' if ar else 'Female' }}</option><option value="Male">{{ 'ذكر' if ar else 'Male' }}</option><option value="Other">{{ 'آخر' if ar else 'Other' }}</option></select></label>
      <label>{{ 'الدواء' if ar else 'Medication' }}<input class="filter" id="aeMedication" maxlength="100" data-ss-change="auditUI" data-ss-args="[&quot;changed_analytics_filters&quot;,&quot;dataexport&quot;]" placeholder="Optional"></label><label>{{ 'العرض' if ar else 'Symptom' }}<input class="filter" id="aeSymptom" maxlength="100" data-ss-change="auditUI" data-ss-args="[&quot;changed_analytics_filters&quot;,&quot;dataexport&quot;]" placeholder="Optional"></label>
      <label>{{ 'مستوى الخطورة' if ar else 'Risk level' }}<select class="filter" id="aeRisk" data-ss-change="auditUI" data-ss-args="[&quot;changed_analytics_filters&quot;,&quot;dataexport&quot;]"><option value="">{{ 'الكل' if ar else 'All' }}</option><option value="Low Risk">{{ 'منخفض' if ar else 'Low Risk' }}</option><option value="Needs Follow-up">{{ 'يحتاج متابعة' if ar else 'Needs Follow-up' }}</option><option value="Urgent">{{ 'عاجل' if ar else 'Urgent' }}</option></select></label>
    </div><div class="data-actions" style="margin-top:14px"><button type="button" class="btn ghost" data-ss-click="previewAnalyticsExport">📊 {{ 'معاينة الملخص' if ar else 'Preview summary' }}</button><button type="button" class="btn" data-ss-click="downloadAnalyticsExport">📥 {{ 'تحميل تقرير الأدوية' if ar else 'Download Medication Report' }}</button></div><div id="aeStatus" class="export-status"></div></div>
    <div id="aePreview" class="export-preview"></div>
  </section>

  <section class="view" id="view-dropoff">
    <div class="head"><div><h1>📉 {{ 'رحلة المستخدم والتسرب' if ar else 'User Journey & Drop-off' }}</h1><p>{{ 'مراحل مجهولة الهوية فقط؛ لا يتم تخزين الأعراض أو هوية المستخدم في أحداث الرحلة.' if ar else 'Anonymous journey stages only; symptoms and user identity are not stored in journey events.' }}</p></div><button type="button" class="btn ghost" data-ss-click="loadDropoff">🔄</button></div>
    <div class="card"><div class="toolbar"><select class="filter" id="dropPeriod" data-ss-change="toggleDropDates auditUI loadDropoff" data-ss-multi data-ss-args="[[],[&quot;changed_analytics_filters&quot;,&quot;dropoff&quot;],[]]"><option value="today">{{ 'اليوم' if ar else 'Today' }}</option><option value="7d">{{ 'آخر 7 أيام' if ar else 'Last 7 Days' }}</option><option value="30d" selected>{{ 'آخر 30 يومًا' if ar else 'Last 30 Days' }}</option><option value="90d">{{ 'آخر 3 أشهر' if ar else 'Last 3 Months' }}</option><option value="custom">{{ 'فترة مخصصة' if ar else 'Custom Range' }}</option></select><select class="filter" id="dropDevice" data-ss-change="auditUI loadDropoff" data-ss-multi data-ss-args="[[&quot;changed_analytics_filters&quot;,&quot;dropoff&quot;],[]]"><option value="">{{ 'كل الأجهزة' if ar else 'All devices' }}</option><option value="mobile">{{ 'جوال' if ar else 'Mobile' }}</option><option value="desktop">{{ 'كمبيوتر' if ar else 'Desktop' }}</option><option value="tablet">{{ 'جهاز لوحي' if ar else 'Tablet' }}</option></select><input class="filter" type="date" id="dropStart" style="display:none" data-ss-change="auditUI loadDropoff" data-ss-multi data-ss-args="[[&quot;changed_analytics_filters&quot;,&quot;dropoff&quot;],[]]"><input class="filter" type="date" id="dropEnd" style="display:none" data-ss-change="auditUI loadDropoff" data-ss-multi data-ss-args="[[&quot;changed_analytics_filters&quot;,&quot;dropoff&quot;],[]]"></div><div class="grid" id="dropStats"></div><div id="funnelList" class="funnel-list"></div></div>
  </section>

  <section class="view" id="view-live">
    <div class="head"><div><h1>⚡ {{ 'النشاط المباشر' if ar else 'Live Activity' }}</h1><p>{{ 'أحداث تشغيلية فقط وبدون أسماء أو بريد أو أعراض أو تفاصيل طبية.' if ar else 'Operational events only—no names, emails, symptoms, or medical details.' }}</p></div><div class="actions"><button type="button" id="livePause" class="btn ghost" data-ss-click="toggleLive">⏸ {{ 'إيقاف التحديث' if ar else 'Pause Live Updates' }}</button></div></div>
    <div class="grid" id="liveStats"></div><div class="two"><div class="card"><div class="toolbar"><select id="liveCategory" class="filter" data-ss-change="auditUI loadLive" data-ss-multi data-ss-args="[[&quot;changed_analytics_filters&quot;,&quot;live&quot;],[]]"><option value="all">{{ 'الكل' if ar else 'All' }}</option><option value="analysis">{{ 'التحليل' if ar else 'Analysis' }}</option><option value="assistant">{{ 'المساعد' if ar else 'Assistant' }}</option><option value="reports">{{ 'التقارير' if ar else 'Reports' }}</option><option value="authentication">{{ 'تسجيل الدخول' if ar else 'Authentication' }}</option><option value="system">{{ 'النظام' if ar else 'System' }}</option></select><select id="liveWindow" class="filter" data-ss-change="auditUI loadLive" data-ss-multi data-ss-args="[[&quot;changed_analytics_filters&quot;,&quot;live&quot;],[]]"><option value="hour">{{ 'آخر ساعة' if ar else 'Last hour' }}</option><option value="today">{{ 'اليوم' if ar else 'Today' }}</option><option value="7d">{{ 'آخر 7 أيام' if ar else 'Last 7 days' }}</option></select></div><h2>{{ 'الأحداث' if ar else 'Event feed' }}</h2><div id="liveFeed" class="live-feed"></div></div><div class="card"><h2>{{ 'النشاط عبر الوقت' if ar else 'Activity over time' }}</h2><div class="chart"><canvas id="liveChart"></canvas></div></div></div>
  </section>

  <section class="view" id="view-ai"><div class="head"><div><h1>🧠 {{ 'أداء الذكاء الاصطناعي' if ar else 'AI Performance' }}</h1><p>{{ 'مؤشرات تشغيلية مجمعة بدون محادثات أو بيانات صحية شخصية.' if ar else 'Aggregate operational metrics without chats or personal health data.' }}</p></div><button type="button" class="btn ghost" data-ss-click="loadAI">🔄</button></div><div class="grid" id="aiStats"></div><div class="two"><div class="card"><h2>{{ 'جودة معلومات التحليل' if ar else 'Analysis Data Quality' }}</h2><div id="aiQualitySummary" class="muted"></div></div><div class="card"><h2>{{ 'أكثر المعلومات نقصًا' if ar else 'Most frequently missing information' }}</h2><div id="aiMissing"></div></div></div><div class="two"><div class="card"><h2>{{ 'طلبات AI عبر الوقت' if ar else 'AI requests over time' }}</h2><div class="chart"><canvas id="aiTimeline"></canvas></div></div><div class="card"><h2>{{ 'الميزات الأكثر استخدامًا' if ar else 'Most used AI features' }}</h2><div id="aiFeatures"></div></div></div><div class="two"><div class="card"><h2>{{ 'زمن الاستجابة عبر الوقت' if ar else 'Response time over time' }}</h2><div class="chart"><canvas id="aiResponseTimeline"></canvas></div></div><div class="card"><h2>{{ 'أعراض غير متعرف عليها' if ar else 'Unrecognized symptoms' }}</h2><div id="aiUnknown"></div></div></div><div class="two"><div class="card"><h2>{{ 'أنواع الأخطاء' if ar else 'Failure types' }}</h2><div id="aiErrors"></div></div><div class="card"><h2>{{ 'أحدث الطلبات الفاشلة' if ar else 'Recent failed requests' }}</h2><div class="table-wrap" id="aiFailures"></div></div></div></section>

  <section class="view" id="view-xai"><div class="head"><div><h1>🔎 Explainable AI</h1><p>{{ 'شرح مبني على معاملات نموذج BernoulliNB الفعلية، بدون SHAP أو أهمية وهمية.' if ar else 'Explanation from the real BernoulliNB parameters—no fabricated SHAP or feature importance.' }}</p></div><button type="button" class="btn ghost" data-ss-click="loadXAI">🔄</button></div><div class="grid" id="xaiStats"></div><div class="card"><div class="privacy-banner" id="xaiNote"></div><h2 style="margin-top:14px">{{ 'أهم الميزات حسب انتشار المعاملات' if ar else 'Top features by coefficient spread' }}</h2><div id="xaiFeatures"></div></div></section>

  <section class="view" id="view-askdata"><div class="head"><div><h1>💬 Ask Your Data</h1><p>{{ 'أسئلة باللغة الطبيعية فوق استعلامات مجمعة ومسموح بها فقط.' if ar else 'Natural-language questions over allow-listed aggregate queries only.' }}</p></div></div><div class="card"><div class="ds-note">🔒 {{ 'Read-only: لا يتم تنفيذ SQL يكتبه المستخدم، ولا يمكن تعديل قاعدة البيانات.' if ar else 'Read-only: user-written SQL is never executed and the database cannot be modified from this feature.' }}</div><div class="ask-box" style="margin-top:12px"><textarea id="askQuestion" placeholder="{{ 'مثال: ما أكثر 5 أعراض تم تسجيلها؟' if ar else 'Example: What are the top 5 reported symptoms?' }}"></textarea><button type="button" class="btn" data-ss-click="askData">{{ 'اسأل' if ar else 'Ask' }}</button></div><div id="askAnswer" style="margin-top:14px"></div><div class="chart" style="margin-top:12px"><canvas id="askChart"></canvas></div></div></section>

  <section class="view" id="view-insights"><div class="head"><div><h1>💡 {{ 'الملاحظات التلقائية' if ar else 'Automatic Insights' }}</h1><p>{{ 'اتجاهات ومقارنات مبنية على بيانات فعلية مجمعة.' if ar else 'Trends and comparisons based on real aggregate data.' }}</p></div><button type="button" class="btn ghost" data-ss-click="loadInsights">🔄</button></div><div id="autoInsights"></div></section>

  <section class="view" id="view-graph"><div class="head"><div><h1>🧬 Medical Knowledge Graph</h1><p>{{ 'علاقات فعلية من قاعدة المعرفة الطبية ومصادرها الموثقة.' if ar else 'Real relationships from the medical knowledge base and verified sources.' }}</p></div><button type="button" class="btn ghost" data-ss-click="loadGraph">🔄</button></div><div class="grid" id="graphStats"></div><div class="card"><div class="toolbar"><input id="graphSearch" class="search" placeholder="{{ 'ابحث عن مرض، عرض أو مصدر...' if ar else 'Search disease, symptom, or source...' }}" data-ss-input="renderGraph"><select id="graphType" class="filter" data-ss-change="renderGraph"><option value="">{{ 'كل الأنواع' if ar else 'All entity types' }}</option><option value="disease">Disease</option><option value="symptom">Symptom</option><option value="red_flag">Red Flag</option><option value="source">Medical Source</option></select><button type="button" class="btn ghost" data-ss-click="graphZoom" data-ss-args="[0.15]">＋</button><button type="button" class="btn ghost" data-ss-click="graphZoom" data-ss-args="[-0.15]">−</button><button type="button" class="btn ghost" data-ss-click="graphReset">Reset</button></div><div class="graph-shell" id="graphShell"><div class="graph-stage" id="graphStage"></div></div><div class="graph-panel" id="graphPanel">{{ 'اضغط على عقدة لعرض التفاصيل.' if ar else 'Click a node to view details.' }}</div></div></section>

  <section class="view" id="view-anomalies"><div class="head"><div><h1>🚨 {{ 'اكتشاف الأنماط غير المعتادة' if ar else 'Anomaly Detection' }}</h1><p>{{ 'مقارنة شفافة مع خط أساس حديث؛ النشاط غير المعتاد لا يعني اختراقًا.' if ar else 'Transparent recent-baseline comparison; unusual activity does not imply a security breach.' }}</p></div><button type="button" class="btn ghost" data-ss-click="loadAnomalies">🔄</button></div><div id="anomalyList"></div></section>

  <section class="view" id="view-heatmap"><div class="head"><div><h1>🌡️ {{ 'الخريطة الحرارية للصحة السكانية' if ar else 'Population Health Heatmap' }}</h1><p>{{ 'مصفوفات مجمعة وغير محددة للهوية؛ لا تعرض مواقع أو سجلات فردية.' if ar else 'Aggregate, non-identifying matrices with no location or individual records.' }}</p></div><button type="button" class="btn ghost" data-ss-click="loadHeatmap">🔄</button></div><div class="card"><h2>{{ 'تكرار الأعراض حسب الفئة العمرية' if ar else 'Symptom frequency by age group' }}</h2><div class="heatmap-wrap" id="symptomHeatmap"></div></div><div class="card"><h2>{{ 'الشدة حسب الشهر' if ar else 'Severity by month' }}</h2><div class="heatmap-wrap" id="severityHeatmap"></div></div><div class="privacy-banner" id="heatmapNotice"></div></section>

  <section class="view" id="view-knowledge"><div class="head"><div><h1>🧠 Medical Knowledge Base</h1><p>{{ 'إدارة الأمراض والأعراض والعلاقات وعلامات الخطر والفئات، مع متابعة دورية لحداثة المحتوى والمصادر.' if ar else 'Manage diseases, symptoms, relationships, red flags, and categories with periodic content-review tracking.' }}</p></div><button type="button" class="btn ghost" data-ss-click="loadKB">🔄 {{ 'تحديث' if ar else 'Refresh' }}</button></div><div class="grid" id="kbStats"></div>
  <div class="card" id="knowledgeQualityCard"><div class="head" style="margin-bottom:10px"><div><h2 style="margin:0">🛡️ {{ 'جودة التغطية والمصادر' if ar else 'Coverage & Source Quality' }}</h2><p class="muted" style="margin-top:5px">{{ 'تقيس الترابط الفعلي بين الأعراض والحالات والمصادر؛ الحجم وحده لا يكفي.' if ar else 'Measures real symptom-to-condition linkage and source coverage; size alone is not enough.' }}</p></div><span class="badge verified" id="knowledgeVersion">—</span></div><div class="grid" id="knowledgeQuality"></div><div class="ds-note" id="knowledgeQualityNote"></div></div>
  <div class="card"><div class="head" style="margin-bottom:10px"><div><h2 style="margin:0">🩻 {{ 'مراجعة المحتوى الطبي الدورية' if ar else 'Periodic Medical Content Review' }}</h2><p class="muted" style="margin-top:5px">{{ 'تظهر الأمراض والأعراض والمصادر وعلامات الخطر التي فقدت مصدرًا موثقًا أو تجاوزت مدة المراجعة.' if ar else 'Flags diseases, symptoms, sources, and red flags with missing verified sources or overdue review dates.' }}</p></div><div class="actions"><select id="reviewAge" class="filter" data-ss-change="loadKnowledgeReview"><option value="180">180 {{ 'يوم' if ar else 'days' }}</option><option value="365" selected>365 {{ 'يوم' if ar else 'days' }}</option><option value="540">540 {{ 'يوم' if ar else 'days' }}</option></select><button type="button" class="btn ghost" data-ss-click="loadKnowledgeReview">🔄</button></div></div><div class="grid" id="knowledgeReviewStats" style="margin-bottom:12px"></div><div class="table-wrap" id="knowledgeReviewTable"></div></div>
  <div class="card"><div class="toolbar"><button type="button" class="btn ghost" data-ss-click="show" data-ss-args="[&quot;diseases&quot;]">🩺 {{ 'الأمراض' if ar else 'Diseases' }}</button><button type="button" class="btn ghost" data-ss-click="show" data-ss-args="[&quot;symptoms&quot;]">🤕 {{ 'الأعراض' if ar else 'Symptoms' }}</button><button type="button" class="btn ghost" data-ss-click="show" data-ss-args="[&quot;relationships&quot;]">🔗 {{ 'العلاقات' if ar else 'Relationships' }}</button><button type="button" class="btn ghost" data-ss-click="show" data-ss-args="[&quot;redflags&quot;]">🚨 {{ 'علامات الخطر' if ar else 'Red Flags' }}</button><button type="button" class="btn" data-ss-click="openEditor" data-ss-args="[&quot;category&quot;]">＋ {{ 'إضافة فئة' if ar else 'Add Category' }}</button></div><h2>{{ 'الفئات' if ar else 'Categories' }}</h2><div id="categories"></div></div>
  <div class="card"><h2>{{ 'تسلسل التقييم' if ar else 'Assessment flow' }}</h2><p class="muted">User Input → Symptom Normalization → Knowledge Retrieval → Matching → Safety Rules → AI Explanation → Risk → Sources</p></div></section>

  <section class="view" id="view-contentgaps">
    <div class="head"><div><h1>🧩 {{ 'فجوات المحتوى' if ar else 'Content Gaps' }}</h1><p>{{ 'قائمة عمل تلقائية توضّح أين يحتاج البحث وتحليل الأعراض والمصادر إلى تحسين فعلي.' if ar else 'An automatic work queue showing where search, symptom analysis, and source coverage need real improvement.' }}</p></div><div class="actions"><select id="contentGapDays" class="filter" data-ss-change="loadContentGaps"><option value="7">7 {{ 'أيام' if ar else 'days' }}</option><option value="30" selected>30 {{ 'يومًا' if ar else 'days' }}</option><option value="90">90 {{ 'يومًا' if ar else 'days' }}</option></select><button class="btn ghost" type="button" data-ss-click="loadContentGaps">🔄 {{ 'تحديث' if ar else 'Refresh' }}</button></div></div>
    <div class="privacy-banner">🔒 {{ 'تعرض هذه الصفحة إشارات تحسين مجهولة الهوية. لا تُخزن هوية المستخدم أو الجلسة مع فجوات البحث، ولا يُخزن نص محادثة المساعد. عبارات البحث غير المطابقة لا تسجل إلا بعد موافقة Analytics وبعد إزالة الأرقام والمعرّفات الواضحة.' if ar else 'This page shows privacy-aware improvement signals. User/session identity is not stored with search gaps, and assistant message text is not stored. Unmatched search phrases are logged only after Analytics consent and after removing numbers and obvious identifiers.' }}</div>
    <div class="grid" id="contentGapStats" style="margin-top:14px"></div>
    <div class="two">
      <div class="card"><h2>🔎 {{ 'بحث لم يجد تغطية محلية' if ar else 'Searches needing local coverage' }}</h2><p class="muted">{{ 'عبارات مختصرة غير مرتبطة بهوية تساعدك على معرفة المواضيع أو المرادفات الناقصة.' if ar else 'Short de-identified phrases that reveal missing topics or aliases.' }}</p><div class="table-wrap" id="gapSearches"></div></div>
      <div class="card"><h2>🤕 {{ 'أعراض لم يفهمها المحرك' if ar else 'Unmatched symptom wording' }}</h2><p class="muted">{{ 'مأخوذة من سجل تغطية الأعراض الاختياري بعد موافقة Analytics.' if ar else 'From the optional symptom-coverage log after Analytics consent.' }}</p><div class="table-wrap" id="gapSymptoms"></div></div>
    </div>
    <div class="two">
      <div class="card"><h2>📚 {{ 'حالات تحتاج مصادر أقوى' if ar else 'Conditions needing stronger sourcing' }}</h2><p class="muted">{{ 'حالات نشطة لديها أقل من مصدرين موثقين ونشطين.' if ar else 'Active conditions backed by fewer than two active verified sources.' }}</p><div class="table-wrap" id="gapSources"></div></div>
      <div class="card"><h2>🧠 {{ 'فجوات الربط والتغطية' if ar else 'Coverage & linkage gaps' }}</h2><p class="muted">{{ 'أعراض نشطة بلا روابط حالات أو بلا مصدر موثق على مستوى العرض.' if ar else 'Active symptoms with no condition links or no verified symptom-level source.' }}</p><div class="table-wrap" id="gapCoverage"></div></div>
    </div>
    <div class="two">
      <div class="card"><h2>🗓️ {{ 'قائمة المراجعة الطبية' if ar else 'Medical review queue' }}</h2><p class="muted">{{ 'المحتوى أو المصادر التي تحتاج مراجعة أو لديها نقص في التوثيق.' if ar else 'Content or sources needing review or stronger documentation.' }}</p><div class="table-wrap" id="gapReview"></div></div>
      <div class="card"><h2>💬 {{ 'إشارات من تقييم المساعد' if ar else 'Assistant feedback signals' }}</h2><p class="muted">{{ 'فئات أسباب فقط مثل «لم تتم الإجابة» أو «احتاج تفاصيل أكثر»؛ لا نخزن نص السؤال هنا.' if ar else 'Reason categories only, such as “not answered” or “need more”; question text is not stored here.' }}</p><div class="table-wrap" id="gapAssistant"></div></div>
    </div>
  </section>

  {% if admin_user.role == 'admin' %}
  <section class="view" id="view-content"><div class="head"><div><h1>📝 {{ 'إدارة المحتوى' if ar else 'Content management' }}</h1><p>{{ 'النصائح والأسئلة الشائعة والتوعية والنصوص التعريفية بالعربية والإنجليزية.' if ar else 'Bilingual tips, FAQs, awareness, and introductory copy.' }}</p></div><button type="button" class="btn edit-only" data-ss-click="openContentEditor">＋ {{ 'إضافة محتوى' if ar else 'Add content' }}</button></div><div class="card"><div class="toolbar"><input id="contentSearch" class="search" placeholder="{{ 'بحث...' if ar else 'Search...' }}" data-ss-input="renderContent"><select id="contentType" class="filter" data-ss-change="renderContent"><option value="">{{ 'كل الأنواع' if ar else 'All types' }}</option><option value="health_tip">Health tip</option><option value="faq">FAQ</option><option value="educational">Educational Content</option><option value="mental_health">Mental Health Content</option><option value="awareness">Awareness</option><option value="intro">Intro</option></select></div><div class="table-wrap" id="table-content"></div></div></section>
  {% for key, icon, title_ar, title_en in [('diseases','🩺','الأمراض','Diseases'),('symptoms','🤕','الأعراض','Symptoms'),('relationships','🔗','علاقات المرض والأعراض','Disease–symptom relationships'),('sources','📚','المصادر الطبية','Medical sources'),('redflags','🚨','قواعد علامات الخطر','Red-flag rules')] %}
  <section class="view" id="view-{{ key }}"><div class="head"><div><h1>{{ icon }} {{ title_ar if ar else title_en }}</h1><p>{{ 'البحث بالعربية أو الإنجليزية وإدارة الحالة والمحتوى.' if ar else 'Search in Arabic or English and manage content status.' }}</p></div><button type="button" class="btn edit-only" data-ss-click="openEditor" data-ss-args="[&quot;{{ 'red_flag' if key == 'redflags' else ('relationship' if key == 'relationships' else key[:-1]) }}&quot;]">＋ {{ 'إضافة' if ar else 'Add' }}</button></div><div class="card"><div class="toolbar"><input class="search" id="search-{{ key }}" placeholder="{{ 'بحث...' if ar else 'Search...' }}" data-ss-input="render" data-ss-args="[&quot;{{ key }}&quot;]"><select class="filter" id="filter-{{ key }}" data-ss-change="render" data-ss-args="[&quot;{{ key }}&quot;]"><option value="">{{ 'كل الحالات' if ar else 'All statuses' }}</option><option value="active">Active</option><option value="draft">Draft</option><option value="disabled">Disabled</option>{% if key == 'sources' %}<option value="verified">Verified</option><option value="needs_review">Needs review</option>{% endif %}</select>{% if key in ['diseases','symptoms'] %}<select class="filter category-filter" id="extra-{{ key }}" data-ss-change="render" data-ss-args="[&quot;{{ key }}&quot;]"><option value="">{{ 'كل الفئات' if ar else 'All categories' }}</option></select>{% elif key == 'sources' %}<select class="filter" id="extra-{{ key }}" data-ss-change="render" data-ss-args="[&quot;{{ key }}&quot;]"><option value="">{{ 'كل الأنواع' if ar else 'All types' }}</option><option value="government">Government</option><option value="international_organization">International Organization</option><option value="national_health_service">National Health Service</option><option value="academic_medical_institution">Academic Medical Institution</option><option value="clinical_guideline_body">Clinical Guideline Body</option><option value="other_trusted_source">Other Trusted Source</option></select>{% elif key == 'relationships' %}<select class="filter" id="extra-{{ key }}" data-ss-change="render" data-ss-args="[&quot;{{ key }}&quot;]"><option value="">{{ 'كل الأنماط' if ar else 'All typicality' }}</option><option value="very_common">Very common</option><option value="common">Common</option><option value="less_common">Less common</option></select>{% elif key == 'redflags' %}<select class="filter" id="extra-{{ key }}" data-ss-change="render" data-ss-args="[&quot;{{ key }}&quot;]"><option value="">{{ 'كل المخاطر' if ar else 'All risks' }}</option><option value="urgent">Urgent</option><option value="review">Needs review</option></select>{% endif %}{% if key == 'diseases' %}<select class="filter" id="extra2-diseases" data-ss-change="render" data-ss-args="[&quot;diseases&quot;]"><option value="">{{ 'كل درجات الشدة' if ar else 'All severity' }}</option><option value="mild">Mild</option><option value="moderate">Moderate</option><option value="severe">Severe</option></select>{% endif %}</div><div class="table-wrap" id="table-{{ key }}"></div></div></section>
  {% endfor %}

  <section class="view" id="view-audit"><div class="head"><div><h1>🧾 {{ 'سجل التعديلات' if ar else 'Audit log' }}</h1><p>{{ 'من عدّل ماذا ومتى، مع القيم السابقة والجديدة.' if ar else 'Who changed what and when, with previous and new values.' }}</p></div><div class="actions"><button type="button" class="btn" data-ss-click="exportAudit">📥 {{ 'تصدير السجل' if ar else 'Export Audit Log' }}</button><button type="button" class="btn ghost" data-ss-click="loadAudit">🔄</button></div></div><div class="card"><div class="toolbar"><input id="auditSearch" class="search" placeholder="{{ 'بحث في الإجراء أو الكيان...' if ar else 'Search action or entity...' }}" data-ss-input="renderAudit"></div><div class="table-wrap" id="table-audit"></div></div></section>
  <section class="view" id="view-health"><div class="head"><div><h1>🖥️ {{ 'صحة النظام' if ar else 'System health' }}</h1><p>{{ 'حالة المكونات وآخر فحص وزمن الاستجابة.' if ar else 'Component state, last check, and response time.' }}</p></div><button type="button" class="btn ghost" data-ss-click="loadHealth">🔄</button></div><div class="health" id="healthGrid"></div></section>
  {% endif %}
  {% if admin_user.role == 'admin' %}
  <section class="view" id="view-users"><div class="head"><div><h1>👥 {{ 'إدارة المستخدمين' if ar else 'User management' }}</h1><p>{{ 'معرّف وحالة وتواريخ ودور فقط؛ لا تعرض هذه الشاشة أي بيانات صحية.' if ar else 'ID, status, dates, and role only; this screen exposes no health data.' }}</p></div><button type="button" class="btn ghost" data-ss-click="loadUsers">🔄</button></div><div class="card"><div class="table-wrap" id="table-users"></div></div></section>
  <section class="view{{ ' on' if settings_open else '' }}" id="view-adminsettings"><div class="head"><div><h1>⚙️ {{ 'ملف وإعدادات Admin' if ar else 'Admin Profile & Settings' }}</h1><p>{{ 'الحساب الإداري الوحيد وإعدادات الأمان المتاحة في نظام المصادقة الحالي.' if ar else 'The sole Admin account and security controls supported by the current authentication system.' }}</p></div></div><div class="two"><div class="card"><h2>{{ 'ملف Admin' if ar else 'Admin Profile' }}</h2><div class="profile-grid" id="adminProfile"></div></div><div class="card"><h2>{{ 'إعدادات الأمان' if ar else 'Security Settings' }}</h2><div class="security-list" id="adminSecurity"></div></div></div><div class="card" id="adminInternalTools"><div class="head" style="margin-bottom:8px"><div><h2 style="margin:0">🧰 {{ 'أدوات داخلية عند الحاجة' if ar else 'Internal tools when needed' }}</h2><p class="muted" style="margin-top:5px">{{ 'أخفينا الأدوات التقنية من القائمة الرئيسية لتبقى لوحة الأدمن مركزة.' if ar else 'Technical tools are kept out of the main navigation so the dashboard stays focused.' }}</p></div><div class="data-actions"><button class="btn ghost" type="button" id="openAuditFromSettingsBtn">🔐 {{ 'سجل التدقيق' if ar else 'Audit log' }}</button><a class="btn ghost" href="/admin/competition-dashboard">✨ {{ 'لوحة المسابقة' if ar else 'Competition dashboard' }}</a></div></div></div>
    <div class="card"><div class="head" style="margin-bottom:12px"><div><h2>📧 {{ 'بريد التحقق والاستعادة' if ar else 'Verification & Reset Email' }}</h2><p>{{ 'حالة إعداد مزود البريد بدون عرض أي مفاتيح أو Tokens. اختبار الإرسال موجود فقط في صفحة جاهزية التشغيل.' if ar else 'Email-provider configuration without exposing keys or tokens. Live sending is tested only in Operational Readiness.' }}</p></div></div><div class="profile-grid" id="authEmailStatus"></div></div><div class="card"><h2>{{ 'تغيير كلمة المرور' if ar else 'Change Password' }}</h2><form id="adminPasswordForm" class="form-grid"><div class="field"><label>{{ 'كلمة المرور الحالية' if ar else 'Current password' }}</label><input type="password" name="current_password" required autocomplete="current-password"></div><div class="field"><label>{{ 'كلمة المرور الجديدة' if ar else 'New password' }}</label><input type="password" name="new_password" minlength="8" required autocomplete="new-password"></div><div class="field"><label>{{ 'تأكيد كلمة المرور' if ar else 'Confirm new password' }}</label><input type="password" name="confirm_password" minlength="8" required autocomplete="new-password"></div><div class="field" style="justify-content:flex-end"><button class="btn" type="submit">{{ 'حفظ كلمة المرور' if ar else 'Save password' }}</button></div></form><div id="adminPasswordStatus" class="export-status"></div></div><div class="card"><h2>🛡️ {{ 'إنهاء كل جلسات الأدمن' if ar else 'Sign out all Admin sessions' }}</h2><p class="muted">{{ 'أدخل كلمة المرور الحالية لإنهاء جميع جلسات الأدمن على كل الأجهزة. ستحتاج لتسجيل الدخول من جديد.' if ar else 'Enter the current password to invalidate every Admin session on every device. A fresh sign-in will be required.' }}</p><div class="form-grid"><div class="field"><label>{{ 'كلمة المرور الحالية' if ar else 'Current password' }}</label><input type="password" id="logoutAllAdminPassword" autocomplete="current-password"></div><div class="field" style="justify-content:flex-end"><button class="btn danger" type="button" data-ss-click="logoutAllAdminSessions">{{ 'إنهاء كل الجلسات' if ar else 'Sign out all sessions' }}</button></div></div><div id="logoutAllAdminStatus" class="export-status"></div></div>
    <div class="card" id="labTrialCleanupCard">
      <div class="head" style="margin-bottom:10px">
        <div>
          <h2 style="margin:0">📊 {{ 'ملفات Excel للتجارب' if ar else 'Trial Excel Files' }}</h2>
          <p class="muted" style="margin-top:5px">{{ 'ملف مستقل لتحليل الأعراض وملف مستقل لتحليل الدم. لا تظهر الأسماء أو البريد الإلكتروني في أي ملف.' if ar else 'Separate files for symptom analysis and blood analysis. Names and email addresses are not included.' }}</p>
        </div>
      </div>
      <div class="two" style="align-items:stretch">
        <div class="card" style="margin:0;background:#f8fbfd">
          <h3 style="margin:0 0 6px">🩺 {{ 'ملف تحليل الأعراض' if ar else 'Symptom Analysis File' }}</h3>
          <p class="muted" style="margin:0 0 10px">{{ 'العمر • الجنس • الأعراض • المدة فقط' if ar else 'Age • Gender • Symptoms • Duration only' }}</p>
          <div class="profile-grid" id="labTrialSummary"><div class="health-item"><small class="muted">{{ 'جارٍ التحقق…' if ar else 'Checking…' }}</small><div class="profile-value">—</div></div></div>
          <div class="data-actions" style="margin-top:12px"><a class="btn" href="/admin/analysis-trials/export.xlsx" download>📥 {{ 'تحميل ملف تحليل الأعراض' if ar else 'Download Symptom Analysis File' }}</a></div>
        </div>
        <div class="card" style="margin:0;background:#f8fbfd">
          <h3 style="margin:0 0 6px">🩸 {{ 'ملف تحليل الدم' if ar else 'Blood Analysis File' }}</h3>
          <p class="muted" style="margin:0 0 10px">{{ 'العمر • الجنس • القيم المنخفضة / الناقصة فقط' if ar else 'Age • Gender • Low / deficient values only' }}</p>
          <div class="profile-grid" id="bloodTrialSummary"><div class="health-item"><small class="muted">{{ 'جارٍ التحقق…' if ar else 'Checking…' }}</small><div class="profile-value">—</div></div></div>
          <div class="data-actions" style="margin-top:12px"><a class="btn" href="/admin/blood-trials/export.xlsx" download>📥 {{ 'تحميل ملف تحليل الدم' if ar else 'Download Blood Analysis File' }}</a></div>
        </div>
      </div>
      <p class="muted" style="margin-top:12px">{{ 'ملف تحليل الدم يجمع فقط التحليلات التي تمت بعد تسجيل الدخول والموافقة الصريحة على حفظ بيانات تحليل الدم.' if ar else 'The blood-analysis file includes only analyses completed after sign-in and explicit blood-data consent.' }}</p>
      <div class="data-actions" style="margin-top:12px"><a class="btn danger" href="/admin/analysis-trials#delete">🧹 {{ 'حذف تجارب تحليل الأعراض' if ar else 'Delete symptom trials' }}</a></div>
      <div id="labExportStatus" class="export-status"></div>
    </div>
    <div class="data-actions"><a class="btn danger" href="/logout">{{ 'تسجيل الخروج من هذا الجهاز' if ar else 'Logout this device' }}</a></div></section>
  {% endif %}
</main>
</div>

{% if launch_reset_enabled %}<div class="modal-bg" id="launchResetModal"><div class="modal" style="max-width:650px"><div class="modal-head"><h2>🧹 {{ 'إعادة ضبط بيانات التجربة قبل النشر' if ar else 'Reset Test Data Before Launch' }}</h2><button class="close" type="button" data-ss-click="closeLaunchReset">✕</button></div><div class="form"><div class="privacy-banner" style="background:var(--redbg);border-color:#FECACA;color:var(--red)"><b>{{ 'تنبيه مهم:' if ar else 'Important:' }}</b> {{ 'هذا الإجراء نهائي. سيحذف بيانات التجربة والمستخدمين غير الإداريين ونتائج التحليلات والتقييمات وبيانات الأدوية وتذكيرات البريد وسجلات الاستخدام، حتى يبدأ الموقع نظيفًا عند النشر.' if ar else 'This is permanent. It removes test data, non-Admin users, analysis results, ratings, medication/reminder data, medication-email delivery logs, and usage logs so the public site starts clean.' }}</div><div class="ds-note" style="margin-top:12px"><b>{{ 'سيبقى محفوظًا:' if ar else 'Preserved:' }}</b> {{ 'حساب Admin الحالي، قاعدة المعرفة الطبية، المصادر الموثقة، والمحتوى الثابت للموقع.' if ar else 'the current Admin account, medical knowledge base, trusted sources, and curated site content.' }}</div><div class="form-grid" style="margin-top:14px"><div class="field full"><label>{{ 'كلمة مرور Admin الحالية' if ar else 'Current Admin password' }}</label><input id="launchResetPassword" type="password" autocomplete="current-password" placeholder="••••••••"></div><div class="field full"><label>{{ 'للتأكيد اكتب RESET' if ar else 'Type RESET to confirm' }}</label><input id="launchResetPhrase" type="text" autocomplete="off" placeholder="RESET"></div></div><div id="launchResetStatus" class="export-status" style="min-height:20px"></div><div class="form-actions"><button class="btn ghost" type="button" data-ss-click="closeLaunchReset">{{ 'إلغاء' if ar else 'Cancel' }}</button><button class="btn danger" id="launchResetButton" type="button" data-ss-click="performLaunchReset">🧹 {{ 'حذف بيانات التجربة وتهيئة الموقع للنشر' if ar else 'Delete Test Data & Prepare for Launch' }}</button></div></div></div></div>{% endif %}


<div class="modal-bg" id="labTrialCleanupModal">
  <div class="modal" style="max-width:650px">
    <div class="modal-head">
      <h2>🧪 {{ 'بيانات تجارب تحليل الأعراض' if ar else 'Symptom Analysis Trial Data' }}</h2>
      <button class="close" type="button" data-ss-click="closeLabTrialCleanup">✕</button>
    </div>
    <div class="form">
      <div class="privacy-banner" style="background:var(--redbg);border-color:#FECACA;color:var(--red)">
        <b>{{ 'تنبيه:' if ar else 'Warning:' }}</b>
        {{ 'سيتم حذف تجارب تحليل الأعراض المحفوظة ونتائجها المرتبطة. هذا الإجراء نهائي.' if ar else 'Saved symptom-analysis trials and linked results will be permanently deleted.' }}
      </div>
      <div class="ds-note" style="margin-top:12px">
        <b>{{ 'لن يتم حذف:' if ar else 'Preserved:' }}</b>
        {{ 'حسابات المستخدمين، CBC، ملفات المستخدمين، الأدوية والتذكيرات، أو قاعدة المعرفة.' if ar else 'user accounts, CBC data, profiles, medications/reminders, or the knowledge base.' }}
      </div>
      <div class="form-grid" style="margin-top:14px">
        <div class="field full"><label>{{ 'كلمة مرور Admin الحالية' if ar else 'Current Admin password' }}</label><input id="labCleanupPassword" type="password" autocomplete="current-password" placeholder="••••••••"></div>
        <div class="field full"><label>{{ 'للتأكيد اكتب DELETE TRIALS' if ar else 'Type DELETE TRIALS to confirm' }}</label><input id="labCleanupPhrase" type="text" autocomplete="off" placeholder="DELETE TRIALS"></div>
      </div>
      <div id="labCleanupStatus" class="export-status" style="min-height:20px"></div>
      <div class="form-actions">
        <button class="btn ghost" type="button" data-ss-click="closeLabTrialCleanup">{{ 'إلغاء' if ar else 'Cancel' }}</button>
        <button class="btn danger" id="labCleanupButton" type="button" data-ss-click="performLabTrialCleanup">🧹 {{ 'حذف تجارب تحليل الأعراض' if ar else 'Delete Symptom Trials' }}</button>
      </div>
    </div>
  </div>
</div>

<div class="modal-bg" id="modal"><div class="modal"><div class="modal-head"><h2 id="modalTitle"></h2><button type="button" class="close" data-ss-click="closeModal">✕</button></div><form class="form" id="editForm"><div class="form-grid" id="formFields"></div><div class="form-actions"><button type="button" class="btn ghost" data-ss-click="closeModal">{{ 'إلغاء' if ar else 'Cancel' }}</button><button type="submit" class="btn">{{ 'حفظ' if ar else 'Save' }}</button></div></form><div class="msg" id="modalMsg"></div></div></div>

<div class="modal-bg" id="validationModal"><div class="modal"><div class="modal-head"><h2>🧪 {{ 'حالة تحقق بحثي' if ar else 'Research validation case' }}</h2><button class="close" type="button" data-ss-click="closeValidationEditor">✕</button></div><form class="form" id="validationForm"><input type="hidden" id="validationId"><div class="form-grid">
<div class="field"><label>{{ 'رمز الحالة' if ar else 'Case code' }}</label><input id="valCode" required maxlength="80" placeholder="CASE-001"></div>
<div class="field"><label>{{ 'صفة المراجع' if ar else 'Reviewer role' }}</label><input id="valReviewer" maxlength="160" placeholder="Clinician / Faculty reviewer"></div>
<div class="field full"><label>{{ 'ملخص الحالة المعيارية (بدون بيانات شخصية)' if ar else 'Reference case summary (no personal data)' }}</label><textarea id="valSummary" maxlength="1600"></textarea></div>
<div class="field"><label>{{ 'الخطورة المرجعية' if ar else 'Reference risk' }}</label><select id="valRefRisk" required><option value="low">Low</option><option value="medium">Needs review</option><option value="high">Urgent/Emergency</option></select></div>
<div class="field"><label>{{ 'خطورة النظام' if ar else 'System risk' }}</label><select id="valSysRisk"><option value="">{{ 'لم يُختبر بعد' if ar else 'Not tested yet' }}</option><option value="low">Low</option><option value="medium">Needs review</option><option value="high">Urgent/Emergency</option></select></div>
<div class="field"><label>{{ 'مجموعة الحالة' if ar else 'Scenario group' }}</label><input id="valGroup" maxlength="80" placeholder="respiratory / neurologic"></div>
<div class="field" style="display:flex;align-items:end"><label style="display:flex;align-items:center;gap:9px;border:1px solid var(--line);padding:12px;border-radius:12px;width:100%"><input id="valVerified" type="checkbox" style="width:auto"> <span>{{ 'مرجع مستقل موثق (يدخل في المقاييس)' if ar else 'Independently verified reference (include in metrics)' }}</span></label></div>
<div class="field"><label>{{ 'الحالة المرجعية' if ar else 'Reference condition' }}</label><input id="valRefCond" maxlength="300"></div><div class="field"><label>{{ 'أعلى احتمال من النظام' if ar else 'System top condition' }}</label><input id="valSysCond" maxlength="600"></div>
<div class="field full"><label>{{ 'المرجع/المصدر' if ar else 'Reference source' }}</label><input id="valSource" maxlength="1000" placeholder="DOI / guideline / reviewer reference"></div>
<div class="field full"><label>{{ 'ملاحظات' if ar else 'Notes' }}</label><textarea id="valNotes" maxlength="1600"></textarea></div>
</div><div id="validationMsg" class="msg"></div><div class="form-actions"><button type="button" class="btn ghost" data-ss-click="closeValidationEditor">{{ 'إلغاء' if ar else 'Cancel' }}</button><button type="submit" class="btn">{{ 'حفظ' if ar else 'Save' }}</button></div></form></div></div>

<script>
const LANG={{ lang|tojson }}, AR=LANG==='ar', CSRF={{ csrf_token|tojson }}, ROLE={{ admin_user.role|tojson }};
const CAN_EDIT=ROLE==='admin';
let KB={diseases:[],symptoms:[],sources:[],relationships:[],red_flags:[],categories:[],statistics:{}}, CONTENT=[], AUDIT=[], GRAPH={nodes:[],edges:[],stats:{}}, VALIDATION=[], editing={kind:null,id:null};
let overviewChart=null, activityChart=null, usersChart=null, analysesChart=null, assistantChart=null, aiChart=null, aiResponseChart=null, askChartObj=null, liveChartObj=null;
let healthSymptomsChart=null,healthSeverityChart=null,healthDurationChart=null,healthRiskChart=null,healthAgeChart=null,healthGenderChart=null,medicationChartObj=null,medicationTrendChartObj=null;
let livePaused=false, liveTimer=null;
let graphScale=1;
const txt=(a,e)=>AR?a:e;
const esc=v=>{const d=document.createElement('div');d.textContent=v==null?'':String(v);return d.innerHTML};
// JSON arguments for data-ss-args (HTML-attribute safe); see static/js/interaction-bridge.js
const ssArgs=a=>JSON.stringify(a).replaceAll('&','&amp;').replaceAll('"','&quot;').replaceAll('<','&lt;');
const statusBadge=s=>'<span class="badge '+esc(s||'draft')+'">'+esc(s||'draft')+'</span>';

async function req(url,opt={}){
  opt.headers=Object.assign({'Content-Type':'application/json','X-CSRF-Token':CSRF},opt.headers||{});
  const r=await fetch(url,opt); const d=await r.json().catch(()=>({error:'invalid_response'}));
  if(r.status===401){location.href=d.login_url||'/login?next=/admin';throw new Error('login_required')}
  if(!r.ok||d.ok===false)throw new Error(d.error||('HTTP '+r.status)); return d;
}

function openLaunchReset(){
  const m=document.getElementById('launchResetModal');
  document.getElementById('launchResetPassword').value='';
  document.getElementById('launchResetPhrase').value='';
  document.getElementById('launchResetStatus').textContent='';
  document.getElementById('launchResetButton').disabled=false;
  m?.classList.add('show');
  setTimeout(()=>document.getElementById('launchResetPassword')?.focus(),50);
}
function closeLaunchReset(){document.getElementById('launchResetModal')?.classList.remove('show')}
async function performLaunchReset(){
  const password=document.getElementById('launchResetPassword').value;
  const phrase=(document.getElementById('launchResetPhrase').value||'').trim().toUpperCase();
  const out=document.getElementById('launchResetStatus'),btn=document.getElementById('launchResetButton');
  if(!password){out.textContent=txt('أدخل كلمة مرور Admin الحالية.','Enter the current Admin password.');return}
  if(phrase!=='RESET'){out.textContent=txt('اكتب RESET كما هي لتأكيد الحذف النهائي.','Type RESET exactly to confirm permanent deletion.');return}
  if(!confirm(txt('تأكيد أخير: سيتم حذف كل بيانات التجربة والمستخدمين غير الإداريين نهائيًا. هل تريد المتابعة؟','Final confirmation: all test data and non-Admin users will be permanently deleted. Continue?')))return;
  btn.disabled=true; out.textContent=txt('جارٍ حذف بيانات التجربة وتهيئة الموقع للنشر…','Deleting test data and preparing the site for launch…');
  try{
    const d=await req('/api/admin/reset-test-data',{method:'POST',body:JSON.stringify({current_password:password,confirmation:'RESET'})});
    const r=d.reset||{};
    out.textContent='✓ '+txt('تمت إعادة الضبط بنجاح. حُذف ','Reset complete. Removed ')+(r.deleted_rows||0)+txt(' سجلًا، وحُذف ',' rows and ')+(r.removed_users||0)+txt(' مستخدمًا تجريبيًا. سيتم تحديث اللوحة…',' test users. Refreshing the dashboard…');
    setTimeout(()=>location.href='/admin',1400);
  }catch(e){
    const map={current_password_incorrect:txt('كلمة مرور Admin غير صحيحة.','Incorrect Admin password.'),reset_confirmation_required:txt('تأكيد RESET غير صحيح.','RESET confirmation is incorrect.')};
    out.textContent=map[e.message]||txt('تعذرت إعادة الضبط. لم يتم حذف البيانات.','Reset failed. No data was deleted.');
    btn.disabled=false;
  }
}


async function exportLabTrialsExcel(){
  const out=document.getElementById('labExportStatus');
  if(out)out.textContent=txt('جاري تجهيز ملف Excel…','Preparing Excel workbook…');
  try{
    const r=await fetch('/admin/analysis-trials/export.xlsx',{credentials:'same-origin'});
    if(!r.ok)throw new Error('export_failed');
    const blob=await r.blob(),url=URL.createObjectURL(blob),a=document.createElement('a');
    a.href=url;
    const cd=r.headers.get('content-disposition')||'';
    a.download=(cd.match(/filename="?([^";]+)/)||[])[1]||('SymptoSense_Symptom_Trials_'+new Date().toISOString().slice(0,10)+'.xlsx');
    document.body.appendChild(a);a.click();a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1500);
    if(out)out.textContent='✓ '+txt('تم إنشاء ملف Excel لتجارب تحليل الأعراض.','Symptom-trial Excel workbook created.');
  }catch(e){
    if(out)out.textContent=txt('تعذر تصدير تجارب تحليل الأعراض إلى Excel.','Unable to export symptom trials to Excel.');
  }
}

async function loadLabTrialSummary(){
  const box=document.getElementById('labTrialSummary');
  if(!box)return;
  try{
    const s=(await req('/api/admin/analysis-trials')).summary||{};
    box.innerHTML=[
      [s.saved_analyses||0,txt('تحليلات أعراض محفوظة','Saved symptom analyses')],
      [s.distinct_testers||0,txt('حسابات جرّبت تحليل الأعراض','Accounts that tried symptom analysis')]
    ].map(x=>'<div class="health-item"><small class="muted">'+esc(x[1])+'</small><div class="profile-value">'+esc(x[0])+'</div></div>').join('');
  }catch(e){
    box.innerHTML='<div class="empty">'+txt('تعذر قراءة عدد تجارب تحليل الأعراض.','Unable to read symptom-trial counts.')+'</div>';
  }
}
async function loadBloodTrialSummary(){
  const box=document.getElementById('bloodTrialSummary');
  if(!box)return;
  try{
    const s=(await req('/api/admin/blood-trials')).summary||{};
    box.innerHTML=[
      [s.saved_tests||0,txt('تحليلات دم محفوظة','Saved blood analyses')],
      [s.distinct_testers||0,txt('حسابات جرّبت تحليل الدم','Accounts that tried blood analysis')]
    ].map(x=>'<div class="health-item"><small class="muted">'+esc(x[1])+'</small><div class="profile-value">'+esc(x[0])+'</div></div>').join('');
  }catch(e){
    box.innerHTML='<div class="empty">'+txt('تعذر قراءة عدد تجارب تحليل الدم.','Unable to read blood-analysis counts.')+'</div>';
  }
}

function openLabTrialCleanup(){
  document.getElementById('labCleanupPassword').value='';
  document.getElementById('labCleanupPhrase').value='';
  document.getElementById('labCleanupStatus').textContent='';
  document.getElementById('labCleanupButton').disabled=false;
  document.getElementById('labTrialCleanupModal')?.classList.add('show');
  setTimeout(()=>document.getElementById('labCleanupPassword')?.focus(),50);
}
function closeLabTrialCleanup(){document.getElementById('labTrialCleanupModal')?.classList.remove('show')}
async function performLabTrialCleanup(){
  const password=document.getElementById('labCleanupPassword').value;
  const phrase=(document.getElementById('labCleanupPhrase').value||'').trim().toUpperCase();
  const out=document.getElementById('labCleanupStatus'),btn=document.getElementById('labCleanupButton');
  if(!password){out.textContent=txt('أدخل كلمة مرور Admin الحالية.','Enter the current Admin password.');return}
  if(phrase!=='DELETE TRIALS'){out.textContent=txt('اكتب DELETE TRIALS كما هي لتأكيد الحذف.','Type DELETE TRIALS exactly to confirm deletion.');return}
  if(!confirm(txt('تأكيد أخير: سيتم حذف تجارب تحليل الأعراض ونتائجها فقط، بدون حذف المستخدمين أو CBC. متابعة؟','Final confirmation: saved symptom-analysis trials and linked results will be deleted, without deleting users or CBC data. Continue?')))return;
  btn.disabled=true;
  out.textContent=txt('جارٍ حذف تجارب تحليل الأعراض السابقة…','Deleting previous symptom trials…');
  try{
    const d=await req('/api/admin/analysis-trials/clear',{method:'POST',body:JSON.stringify({current_password:password,confirmation:'DELETE TRIALS'})});
    const r=d.cleared||{};
    out.textContent='✓ '+txt('تم حذف ','Deleted ')+(r.deleted_analyses||0)+txt(' تجربة تحليل أعراض تخص ',' saved symptom-analysis trials across ')+(r.affected_testers||0)+txt(' حسابًا. لم يتم حذف أي حساب مستخدم.',' accounts. No user accounts were deleted.');
    await loadLabTrialSummary();
    await loadBloodTrialSummary();
    setTimeout(()=>closeLabTrialCleanup(),1600);
  }catch(e){
    const map={
      current_password_incorrect:txt('كلمة مرور Admin غير صحيحة.','Incorrect Admin password.'),
      trial_delete_confirmation_required:txt('تأكيد DELETE TRIALS غير صحيح.','DELETE TRIALS confirmation is incorrect.')
    };
    out.textContent=map[e.message]||txt('تعذر حذف تجارب تحليل الأعراض. لم يتم حذف البيانات.','Unable to clear symptom trials. No data was deleted.');
    btn.disabled=false;
  }
}

function readinessBadge(status){const cls=status==='online'||status==='ready'?'online':status==='offline'||status==='not_ready'?'offline':status==='optional'?'neutral':'review';const labels={online:txt('جاهز','Ready'),ready:txt('جاهز','Ready'),degraded:txt('يحتاج انتباه','Needs attention'),attention:txt('يحتاج انتباه','Needs attention'),offline:txt('غير جاهز','Not ready'),not_ready:txt('غير جاهز','Not ready'),optional:txt('اختياري','Optional')};return '<span class="badge '+cls+'">'+esc(labels[status]||status||'—')+'</span>'}
function setBadge(id,status,label){const el=document.getElementById(id);if(!el)return;el.className='badge '+(status==='online'?'online':status==='offline'?'offline':status==='review'?'review':'neutral');el.textContent=label||'—'}
function componentLabel(key,v){const arLabels={database:'قاعدة البيانات',ai:'مزود الذكاء الاصطناعي',session_secret:'مفتاح الجلسة',pseudonym_hash_secret:'مفتاح إخفاء الهوية',security_baseline:'أمان المتصفح',admin_owner:'حساب الأدمن',launch_reset_lock:'حماية إعادة الضبط',admin_session_control:'جلسة الأدمن',rate_limiting:'تحديد معدل الطلبات',data_retention:'الاحتفاظ بالبيانات',research_consent:'موافقة البحث',research_validation:'التحقق البحثي',research_version_freeze:'تجميد نسخة البحث',release_candidate:'نسخة الإصدار',medical_knowledge:'المعرفة الطبية',route_smoke:'المسارات الأساسية',backup_evidence:'النسخ الاحتياطي'};return AR?(arLabels[key]||v.label||key.replaceAll('_',' ')):(v.label||key.replaceAll('_',' '))}
async function loadProductionReadiness(compact=false){
  const stats=document.getElementById('productionStats'),components=document.getElementById('productionComponents');
  try{
    const r=(await req('/api/admin/production-readiness')).readiness||{},cs=r.components||{};
    const online=Object.values(cs).filter(x=>x.status==='online').length,attention=Object.values(cs).filter(x=>x.status==='degraded').length,offline=Object.values(cs).filter(x=>x.status==='offline').length;
    const summaryRows=[[readinessBadge(r.overall),txt('الحالة العامة','Overall')],[r.version||'—',txt('إصدار التطبيق','App version')],[online,txt('مكونات جاهزة','Ready components')],[offline+attention,txt('تحتاج انتباه','Need attention')]];
    if(stats)stats.innerHTML=summaryRows.map(x=>'<div class="stat"><strong style="font-size:18px">'+(String(x[0]).includes('<span')?x[0]:esc(x[0]))+'</strong><span>'+esc(x[1])+'</span></div>').join('');
    const dedicated=new Set(['email','error_monitoring','medication_email','admin_2fa']);
    if(components)components.innerHTML=Object.entries(cs).filter(([key])=>!dedicated.has(key)).map(([key,v])=>{let extra='';if(key==='research_consent')extra='<br>'+txt('مشاركون موافقون: ','Consented participants: ')+esc(v.consented_participants||0)+' · '+txt('تحليلات مؤهلة: ','Eligible analyses: ')+esc(v.eligible_analyses||0);if(key==='research_version_freeze'&&v.frozen_at)extra='<br>'+txt('إصدار الدراسة: ','Study version: ')+esc(v.study_version||'—')+' · '+txt('تاريخ التجميد: ','Frozen at: ')+esc(v.frozen_at);return '<div class="health-item"><div style="display:flex;justify-content:space-between;gap:8px"><b>'+esc(componentLabel(key,v))+'</b>'+readinessBadge(v.status)+'</div><p class="muted" style="margin-top:7px;line-height:1.7">'+esc(v.detail||'')+extra+'</p></div>'}).join('')||'<div class="empty">'+txt('لا توجد بيانات','No data')+'</div>';
    await loadOperationalChecks();
  }catch(e){if(stats)stats.innerHTML='<div class="empty">'+txt('تعذر فحص الجاهزية','Readiness check failed')+'</div>';if(components)components.innerHTML='<div class="empty">'+esc(e.message)+'</div>';console.error(e)}
}
function emailErrorText(code){const m={admin_email_unavailable:txt('بريد حساب Admin غير متاح.','Admin email is unavailable.'),email_brevo_not_configured:txt('إعداد Brevo غير مكتمل. راجعي BREVO_API_KEY وBREVO_FROM_EMAIL وBREVO_FROM_NAME.','Brevo is incomplete. Check the three BREVO variables.'),email_brevo_auth_failed:txt('مفتاح Brevo مرفوض. حدّثي BREVO_API_KEY.','Brevo rejected the API key. Update BREVO_API_KEY.'),email_brevo_key_placeholder:txt('مفتاح Brevo ما زال قيمة تجريبية/Placeholder.','BREVO_API_KEY is still a placeholder.'),email_brevo_sender_invalid:txt('بريد المرسل في Brevo غير صالح أو غير موثّق.','The Brevo sender email is invalid or unverified.'),email_brevo_sender_rejected:txt('Brevo رفض بريد المرسل. تحققي أن BREVO_FROM_EMAIL موثّق.','Brevo rejected the sender. Verify BREVO_FROM_EMAIL.'),email_brevo_recipient_rejected:txt('تعذر الإرسال إلى بريد Admin.','The Admin recipient was rejected.'),email_brevo_rate_limited:txt('Brevo حدّ الطلبات مؤقتًا. انتظري قليلًا ثم أعيدي المحاولة.','Brevo temporarily rate-limited requests. Wait and retry.'),email_brevo_connection_failed:txt('تعذر الاتصال بخدمة Brevo الآن. أعيدي المحاولة بعد قليل.','Unable to reach Brevo right now. Try again shortly.'),email_brevo_delivery_failed:txt('Brevo رفض عملية الإرسال. راجعي حالة المرسل والمفتاح.','Brevo rejected the delivery request. Check sender verification and the API key.'),rate_limited:txt('انتظري قليلًا قبل إعادة اختبار البريد.','Wait a little before testing email again.')};return m[code]||code||txt('خطأ غير معروف','Unknown error')}
async function loadEmailCheck(){const note=document.getElementById('productionEmailNote'),btn=document.getElementById('productionEmailTestBtn');try{const d=await req('/api/admin/auth-email-status');if(d.configured&&!(d.invalid||[]).length){setBadge('emailCheckBadge','online',txt('مهيأ','Configured'));if(note&&!note.dataset.result)note.textContent=txt('المزود: ','Provider: ')+(d.provider||'—')+' · '+txt('جاهز لإرسال اختبار إلى بريد Admin.','Ready to send a test to the Admin inbox.');if(btn)btn.disabled=false}else{setBadge('emailCheckBadge','offline',txt('يحتاج إعداد','Needs setup'));if(note)note.textContent=txt('ناقص/غير صالح: ','Missing/invalid: ')+[...(d.missing||[]),...(d.invalid||[])].join(', ');if(btn)btn.disabled=true}}catch(e){setBadge('emailCheckBadge','offline',txt('تعذر الفحص','Check failed'));if(note)note.textContent=e.message;if(btn)btn.disabled=true}}
async function testProductionEmail(){const note=document.getElementById('productionEmailNote'),btn=document.getElementById('productionEmailTestBtn');if(btn)btn.disabled=true;if(note){note.dataset.result='1';note.textContent=txt('جاري إرسال رسالة الاختبار إلى بريد Admin…','Sending the test message to the Admin inbox…')}try{await req('/api/admin/auth-email-test',{method:'POST',body:'{}'});if(note)note.textContent=txt('✓ تم قبول الرسالة للإرسال. افحصي البريد ثم اضغطي «وصلتني الرسالة».','✓ Message accepted for delivery. Check the inbox, then confirm receipt.')}catch(e){if(note)note.textContent=txt('تعذر إرسال البريد: ','Email test failed: ')+emailErrorText(e.message)}finally{if(btn)btn.disabled=false}}
async function confirmProductionEmail(){const note=document.getElementById('productionEmailNote');if(!confirm(txt('أكد فقط إذا وصلت رسالة اختبار SymptoSense فعليًا إلى صندوق بريد Admin.','Confirm only if the test message actually reached the Admin inbox.')))return;try{await req('/api/admin/auth-email-confirm',{method:'POST',body:'{}'});if(note){note.dataset.result='1';note.textContent='✓ '+txt('تم توثيق وصول البريد فعليًا.','Live inbox delivery verified.')}}catch(e){if(note)note.textContent=txt('أرسل اختبار البريد أولًا ثم أكد وصوله.','Send the email test first, then confirm receipt.')}}
async function loadErrorMonitoringCheck(){const note=document.getElementById('sentryVerificationNote'),btn=document.getElementById('sentryTestBtn');try{const d=await req('/api/admin/error-monitoring/status');if(!d.configured){setBadge('sentryCheckBadge','neutral',txt('اختياري','Optional'));if(note)note.textContent=txt('سجلات التطبيق وRailway تعمل. Sentry غير مفعّل وهو اختياري.','Application/Railway logs are active. Sentry is not configured and is optional.');if(btn){btn.disabled=true;btn.title=txt('أضيفي SENTRY_DSN فقط إذا أردتِ Sentry.','Add SENTRY_DSN only if you want Sentry.')}}else{setBadge('sentryCheckBadge',d.last_test?'online':'review',d.last_test?txt('تم اختباره','Tested'):txt('مهيأ','Configured'));if(note)note.textContent=d.last_test?txt('✓ تم تسجيل اختبار سابق بنجاح.','✓ A previous safe test was recorded.'):txt('Sentry مهيأ ويمكن تشغيل اختبار آمن.','Sentry is configured and ready for a safe test.');if(btn)btn.disabled=false}}catch(e){setBadge('sentryCheckBadge','offline',txt('تعذر الفحص','Check failed'));if(note)note.textContent=e.message;if(btn)btn.disabled=true}}
async function testErrorMonitoring(){const note=document.getElementById('sentryVerificationNote'),btn=document.getElementById('sentryTestBtn');if(btn)btn.disabled=true;if(note)note.textContent=txt('جاري إرسال حدث تقني آمن…','Sending a privacy-safe technical event…');try{const d=await req('/api/admin/error-monitoring/test',{method:'POST',body:'{}'});setBadge('sentryCheckBadge','online',txt('تم اختباره','Tested'));if(note)note.textContent='✓ '+txt('تم إنشاء حدث اختبار آمن. Event ID: ','Safe test event created. Event ID: ')+(d.event_id||'—')}catch(e){if(note)note.textContent=e.message==='sentry_not_configured'?txt('Sentry اختياري وغير مفعّل. لا يلزم إضافته لتشغيل الموقع.','Sentry is optional and not configured. It is not required for the site to run.'):txt('تعذر اختبار مراقبة الأخطاء: ','Error-monitoring test failed: ')+e.message}finally{await loadErrorMonitoringCheck()}}
function adminVapidKeyToArray(base64String){const padding='='.repeat((4-base64String.length%4)%4),base64=(base64String+padding).replace(/-/g,'+').replace(/_/g,'/'),raw=atob(base64),out=new Uint8Array(raw.length);for(let i=0;i<raw.length;i++)out[i]=raw.charCodeAt(i);return out}
async function loadMedicationEmailStatus(){const box=document.getElementById('medEmailVerificationStats'),note=document.getElementById('medEmailVerificationNote');if(!box)return;try{const d=await req('/api/admin/medication-email/status'),ok=!!d.configured;box.innerHTML=[[d.sent||0,txt('أُرسل','Sent')],[d.failed||0,txt('فشل','Failed')],[d.provider||'—',txt('المزوّد','Provider')]].map(x=>'<div class="ops-stat"><strong>'+esc(x[0])+'</strong><span>'+esc(x[1])+'</span></div>').join('');setBadge('medEmailCheckBadge',ok?'online':'offline',ok?txt('مهيأ','Configured'):txt('يحتاج إعداد','Needs setup'));if(note)note.textContent=ok?txt('✓ تذكيرات الجرعات ترسل عبر البريد فقط. آخر إرسال: ','✓ Dose reminders are email-only. Last sent: ')+(d.last_sent_at||'—'):txt('أضيفي إعداد Brevo أو Resend قبل تشغيل Cron التذكيرات.','Configure Brevo or Resend before enabling the reminder cron job.')}catch(e){setBadge('medEmailCheckBadge','offline',txt('تعذر الفحص','Check failed'));box.textContent='';if(note)note.textContent=e.message}}
async function loadOperationalChecks(){await Promise.all([loadEmailCheck(),loadErrorMonitoringCheck(),loadMedicationEmailStatus()])}
function bindProductionControls(){const pairs=[['productionRefreshBtn',()=>loadProductionReadiness()],['productionEmailTestBtn',testProductionEmail],['confirmEmailDeliveryBtn',confirmProductionEmail],['sentryTestBtn',testErrorMonitoring],['medEmailRefreshBtn',loadMedicationEmailStatus]];pairs.forEach(([id,fn])=>{const el=document.getElementById(id);if(el&&!el.dataset.bound){el.dataset.bound='1';el.addEventListener('click',fn)}})}
bindProductionControls();
async function loadResearchStudy(){
  const box=document.getElementById('researchStudyFreeze'),btn=document.getElementById('freezeResearchBtn');if(!box)return;
  try{const d=await req('/api/admin/research-study'),st=d.study||{},rc=d.release||{};const ok=st.frozen&&st.integrity_ok;box.innerHTML=(ok?'✓ ':'⚠️ ')+esc(st.detail||'')+'<br>'+txt('نسخة الدراسة: ','Study version: ')+esc(st.study_version||'—')+' · '+txt('نسخة التطبيق: ','App version: ')+esc(st.app_version||st.current_app_version||rc.app_version||'—')+(st.frozen_at?'<br>'+txt('جُمّدت في: ','Frozen at: ')+esc(st.frozen_at):'')+'<br>'+txt('Release Candidate: ','Release Candidate: ')+esc(rc.release_candidate_id||'—');if(btn){btn.disabled=!!st.frozen;btn.textContent=st.frozen?txt('🔒 النسخة مجمّدة','🔒 Version frozen'):txt('🔒 تجميد النسخة الحالية','🔒 Freeze current version')}}catch(e){box.textContent=txt('تعذر قراءة حالة نسخة الدراسة.','Unable to read research-version state.')}
}
async function freezeResearchStudy(){
  if(!confirm(txt('بعد التجميد ستُستخدم هذه البصمة لمراقبة أي تغيير في محرك تحليل الأعراض أثناء الدراسة. متابعة؟','This pins the symptom-triage engine fingerprint so later changes are flagged during the study. Continue?')))return;
  const typed=prompt(txt('اكتب FREEZE للتأكيد:','Type FREEZE to confirm:'));if((typed||'').trim().toUpperCase()!=='FREEZE')return;
  const note=prompt(txt('ملاحظة اختيارية للدراسة (مثال: نسخة الدراسة الأساسية):','Optional study note:'),'')||'';
  try{await req('/api/admin/research-study/freeze',{method:'POST',body:JSON.stringify({confirmation:'FREEZE',note})});await loadResearchStudy();await loadProductionReadiness(true)}catch(e){alert(txt('تعذر تجميد النسخة: ','Unable to freeze version: ')+e.message)}
}
function validationRiskLabel(v){return v==='high'?txt('عاجل/طوارئ','Urgent/Emergency'):v==='medium'?txt('يحتاج مراجعة','Needs review'):txt('منخفض','Low')}
async function loadResearchValidation(){
  loadResearchStudy();
  const table=document.getElementById('validationTable'),stats=document.getElementById('validationStats');if(!table)return;
  table.innerHTML='<div class="empty">'+txt('جاري التحميل…','Loading…')+'</div>';
  try{const d=await req('/api/admin/research-validation?limit=500'),sm=d.summary||{};VALIDATION=d.cases||[];
    stats.innerHTML=[[sm.verified_cases||0,txt('حالات موثقة مستقلة','Verified reference cases')],[(sm.verified_progress_pct||0)+'%',txt('التقدم نحو 100 حالة','Progress toward 100 cases')],[sm.risk_agreement_pct==null?'—':sm.risk_agreement_pct+'%',txt('اتفاق مستوى الخطورة','Risk agreement')],[sm.balanced_accuracy_pct==null?'—':sm.balanced_accuracy_pct+'%',txt('Balanced accuracy','Balanced accuracy')],[sm.urgent_sensitivity_pct==null?'—':sm.urgent_sensitivity_pct+'%',txt('حساسية الحالات العاجلة','Urgent sensitivity')],[sm.urgent_specificity_pct==null?'—':sm.urgent_specificity_pct+'%',txt('نوعية الحالات العاجلة','Urgent specificity')],[sm.cohens_kappa_risk==null?'—':sm.cohens_kappa_risk,txt('كابا لمستوى الخطورة','Risk Cohen’s kappa')],[sm.distinct_reference_sources||0,txt('مراجع/مصادر مستقلة','Distinct reference sources')]].map(x=>'<div class="stat"><strong>'+esc(x[0])+'</strong><span>'+esc(x[1])+'</span></div>').join('');
    const proto=sm.protocol||{},pc=sm.per_class||{};document.getElementById('validationProtocol').innerHTML='<div class="head" style="margin-bottom:10px"><div><h2 style="margin:0">📐 '+txt('بروتوكول الدراسة','Study protocol')+'</h2><p class="muted" style="margin-top:5px">'+esc(proto.protocol_version||'RV-1.0')+'</p></div>'+readinessBadge(sm.study_ready?'online':'review')+'</div><div class="two"><div class="insight-card"><b>'+txt('المخرج الأساسي','Primary endpoint')+'</b><div class="muted" style="margin-top:6px">'+esc(proto.primary_endpoint||'—')+'</div></div><div class="insight-card"><b>'+txt('قاعدة المرجع','Reference rule')+'</b><div class="muted" style="margin-top:6px">'+esc(proto.reference_rule||'—')+'</div></div></div><div class="grid" style="margin-top:10px;margin-bottom:0">'+['low','medium','high'].map(k=>'<div class="stat"><strong>'+(pc[k]?.n||0)+'</strong><span>'+esc(validationRiskLabel(k))+'</span><small>'+txt('Recall: ','Recall: ')+esc(pc[k]?.recall_pct==null?'—':pc[k].recall_pct+'%')+' · '+txt('Precision: ','Precision: ')+esc(pc[k]?.precision_pct==null?'—':pc[k].precision_pct+'%')+'</small></div>').join('')+'</div>';
    table.innerHTML=VALIDATION.length?'<table><thead><tr><th>'+txt('الرمز','Code')+'</th><th>'+txt('الحالة','Reference status')+'</th><th>'+txt('المرجع','Reference risk')+'</th><th>'+txt('النظام','System risk')+'</th><th>'+txt('الاتفاق','Agreement')+'</th><th>'+txt('الحالة المرجعية','Reference condition')+'</th><th>'+txt('أعلى احتمال','System condition')+'</th><th>'+txt('الإجراء','Action')+'</th></tr></thead><tbody>'+VALIDATION.map(x=>'<tr><td><b>'+esc(x.case_code)+'</b><div class="muted">'+esc((x.scenario_group||x.dataset_origin||'').slice(0,80))+'</div></td><td>'+(x.reference_verified?'<span class="badge verified">'+txt('موثق','Verified')+'</span>':'<span class="badge review">'+txt('بانتظار المراجعة','Pending')+'</span>')+'</td><td>'+esc(validationRiskLabel(x.reference_risk))+'</td><td>'+esc(x.system_risk?validationRiskLabel(x.system_risk):txt('لم يُختبر','Not tested'))+'</td><td>'+(x.reference_verified&&x.system_risk?readinessBadge(x.risk_agreement?'online':'offline'):'—')+'</td><td>'+esc(x.reference_condition||'—')+'</td><td>'+esc(x.system_condition||'—')+'</td><td><button type="button" class="btn ghost small" data-ss-click="openValidationEditor" data-ss-args="'+ssArgs([x.id])+'">'+txt('مراجعة/تعديل','Review/Edit')+'</button> <button type="button" class="btn danger small" data-ss-click="deleteValidationCase" data-ss-args="'+ssArgs([x.id])+'">'+txt('حذف','Delete')+'</button></td></tr>').join('')+'</tbody></table>':'<div class="empty">'+txt('لا توجد حالات تحقق بعد.','No validation cases yet.')+'</div>';
  }catch(e){table.innerHTML='<div class="empty">'+esc(e.message)+'</div>'}
}
function downloadValidation(mode){const a=document.createElement('a');a.href='/api/admin/research-validation/export?mode='+encodeURIComponent(mode||'results');a.download='';document.body.appendChild(a);a.click();a.remove()}
function openValidationEditor(id){const x=id?VALIDATION.find(r=>r.id===id):null;document.getElementById('validationId').value=x?.id||'';document.getElementById('valCode').value=x?.case_code||'';document.getElementById('valReviewer').value=x?.reviewer_role||'';document.getElementById('valSummary').value=x?.case_summary||'';document.getElementById('valRefRisk').value=x?.reference_risk||'low';document.getElementById('valSysRisk').value=x?.system_risk||'';document.getElementById('valRefCond').value=x?.reference_condition||'';document.getElementById('valSysCond').value=x?.system_condition||'';document.getElementById('valSource').value=x?.source_reference||'';document.getElementById('valGroup').value=x?.scenario_group||'';document.getElementById('valVerified').checked=!!x?.reference_verified;document.getElementById('valNotes').value=x?.notes||'';document.getElementById('validationMsg').className='msg';document.getElementById('validationMsg').textContent='';document.getElementById('validationModal')?.classList.add('show')}
function closeValidationEditor(){document.getElementById('validationModal')?.classList.remove('show')}
async function deleteValidationCase(id){if(!confirm(txt('حذف حالة التحقق؟','Delete this validation case?')))return;try{await req('/api/admin/research-validation/'+id,{method:'DELETE'});await loadResearchValidation()}catch(e){alert(e.message)}}
document.getElementById('validationForm')?.addEventListener('submit',async function(e){e.preventDefault();const id=document.getElementById('validationId').value,payload={case_code:document.getElementById('valCode').value,reviewer_role:document.getElementById('valReviewer').value,case_summary:document.getElementById('valSummary').value,reference_risk:document.getElementById('valRefRisk').value,system_risk:document.getElementById('valSysRisk').value,reference_condition:document.getElementById('valRefCond').value,system_condition:document.getElementById('valSysCond').value,source_reference:document.getElementById('valSource').value,scenario_group:document.getElementById('valGroup').value,reference_verified:document.getElementById('valVerified').checked,notes:document.getElementById('valNotes').value},msg=document.getElementById('validationMsg');try{await req('/api/admin/research-validation'+(id?'/'+id:''),{method:id?'PUT':'POST',body:JSON.stringify(payload)});closeValidationEditor();await loadResearchValidation()}catch(err){msg.className='msg show err';msg.textContent=err.message}});

function qualityStat(label,value,note){return '<div class="stat"><span>'+esc(label)+'</span><b>'+esc(value??0)+'</b>'+(note?'<small class="muted">'+esc(note)+'</small>':'')+'</div>'}
async function loadQuality(){
  const days=document.getElementById('qualityDays')?.value||30;
  const sbox=document.getElementById('qualitySymptomStats'),bbox=document.getElementById('qualityBloodStats'),safe=document.getElementById('qualitySafety'),complete=document.getElementById('qualityCompleteness'),cover=document.getElementById('qualityCoverageStats'),notes=document.getElementById('qualityNotes');
  if(sbox)sbox.innerHTML='<div class="empty">'+txt('جاري تحميل مؤشرات الجودة…','Loading quality metrics…')+'</div>';
  try{
    const d=await req('/api/admin/quality-dashboard?days='+encodeURIComponent(days)),s=d.symptoms||{},b=d.blood||{},v=s.safety_validation||{};
    if(sbox)sbox.innerHTML=[qualityStat(txt('تحليلات مكتملة','Completed analyses'),s.completed||0),qualityStat(txt('طلبات فاشلة','Failed requests'),s.failed||0),qualityStat(txt('نسبة النجاح','Success rate'),(s.success_rate||0)+'%'),qualityStat(txt('تنبيهات الأمان','Safety alerts'),s.safety_alerts||0)].join('');
    if(bbox)bbox.innerHTML=[qualityStat(txt('استخراجات مكتملة','Completed extractions'),b.extractions_completed||0),qualityStat(txt('تحليلات مكتملة','Completed analyses'),b.analyses_completed||0),qualityStat(txt('قراءة ملف كامل','Full-file reads'),b.full_file_reads||0),qualityStat(txt('قيم تحتاج مراجعة','Values needing review'),b.values_needing_review||0)].join('');
    if(safe){const ok=!!v.all_passed;safe.innerHTML='<div class="insight-card"><b>'+(ok?'✅ ':'⚠️ ')+txt('اختبارات محرك الأمان','Safety-engine regression tests')+'</b><div class="muted" style="margin-top:6px">'+esc((v.passed||0)+' / '+(v.total||0))+' · '+esc((v.pass_rate||0)+'%')+' · '+esc(v.engine||'')+'</div></div>'}
    if(complete)complete.innerHTML='<div class="insight-card"><b>📄 '+txt('اكتمال قراءة الملفات','Full-report read completeness')+'</b><div class="muted" style="margin-top:6px">'+esc((b.full_file_read_rate||0)+'%')+' · '+esc((b.pages_read||0)+' / '+(b.pages_total||0))+' '+txt('صفحة','pages')+'</div></div>';
    if(cover)cover.innerHTML=[qualityStat(txt('تغطية مصادر تحليل الأعراض','Symptom source coverage'),(s.knowledge_source_coverage_pct||0)+'%'),qualityStat(txt('تغطية الأعراض المدعومة','Symptom support coverage'),(s.symptom_support_coverage_pct||0)+'%'),qualityStat(txt('تغطية مصادر قيم الدم','Lab-value source coverage'),(b.source_coverage_pct||0)+'%'),qualityStat(txt('قراءات ملفات موثقة من السيرفر','Server-verified file reads'),b.files_with_completeness_metadata||0)].join('');
    if(notes){const n=d.notes||{};notes.textContent=[n.accuracy_claim,n.telemetry_scope].filter(Boolean).join(' · ');}
  }catch(e){if(sbox)sbox.innerHTML='<div class="empty">'+esc(e.message)+'</div>';if(bbox)bbox.textContent='';if(safe)safe.textContent='';if(complete)complete.textContent='';if(cover)cover.textContent='';}
}
document.getElementById('qualityRefreshBtn')?.addEventListener('click',loadQuality);
document.getElementById('qualityDays')?.addEventListener('change',loadQuality);

function show(name){
  document.querySelectorAll('.view').forEach(v=>v.classList.remove('on'));
  const knowledgeChildren=['diseases','symptoms','relationships','redflags'];
  const sideName=knowledgeChildren.includes(name)?'knowledge':name;
  document.querySelectorAll('.side .navbtn[data-view]').forEach(v=>v.classList.toggle('on',v.dataset.view===sideName));
  document.getElementById('view-'+name)?.classList.add('on');
  if(name==='overview')loadUsage();
  if(name==='production')loadProductionReadiness();
  if(name==='contentgaps')loadContentGaps();
  if(name==='validation')loadResearchValidation();
  if(name==='analytics'){loadV2Analytics();auditUI('opened_analytics','analytics')}
  if(name==='quality')loadQuality();
  if(name==='healthanalytics')loadHealthAnalytics();
  if(name==='results')loadAnalysisResults(1);
  if(name==='medications')loadMedicationAnalytics();
  if(name==='privacyanalytics'){loadPrivacyAnalytics();auditUI('opened_analytics','privacyanalytics')}
  if(name==='dataexport'){previewAnalyticsExport();auditUI('opened_analytics','dataexport')}
  if(name==='dropoff'){loadDropoff();auditUI('opened_dropoff','dropoff')}
  if(name==='live'){loadLive();startLive();auditUI('opened_live_activity','live')}else if(liveTimer){clearInterval(liveTimer);liveTimer=null}
  if(name==='ai')loadAI();
  if(name==='xai')loadXAI();
  if(name==='askdata'){};
  if(name==='insights')loadInsights();
  if(name==='graph')loadGraph();
  if(name==='anomalies')loadAnomalies();
  if(name==='heatmap')loadHeatmap();
  if(['knowledge','sources','diseases','symptoms','relationships','redflags'].includes(name))loadKB();
  if(name==='content')loadContent();
  if(name==='users')loadUsers();
  if(name==='health')loadHealth();
  if(name==='audit')loadAudit();
  if(name==='adminsettings'){loadAdminProfile();loadLabTrialSummary();loadBloodTrialSummary();}
}
document.querySelectorAll('.side .navbtn[data-view]').forEach(b=>{
  b.addEventListener('click',e=>{
    const name=b.dataset.view;
    if(document.getElementById('view-'+name)){
      e.preventDefault();
      show(name);
      if(name==='adminsettings')history.replaceState(null,'','/admin?view=adminsettings#labTrialCleanupCard');
      else if(name==='overview')history.replaceState(null,'','/admin');
    }
  });
});
document.getElementById('overviewRefreshBtn')?.addEventListener('click',()=>loadUsage());
document.getElementById('allResultsBtn')?.addEventListener('click',()=>show('results'));
document.getElementById('knowledgeDetailsBtn')?.addEventListener('click',()=>show('knowledge'));
document.getElementById('openAuditFromSettingsBtn')?.addEventListener('click',()=>show('audit'));
document.getElementById('runPerfBenchmarkBtn')?.addEventListener('click',()=>runPerformanceBenchmark());
document.getElementById('refreshPerfBenchmarkBtn')?.addEventListener('click',()=>loadPerformanceBenchmark());
document.querySelectorAll('.edit-only').forEach(x=>x.style.display=CAN_EDIT?'':'none');

function miniBars(rows, labelKey='name'){
  const max=Math.max(1,...(rows||[]).map(x=>Number(x.count)||0));
  return (rows||[]).map(x=>'<div style="margin:10px 0"><div style="display:flex;justify-content:space-between;gap:12px;font-size:12px"><b>'+esc(String(x[labelKey]||'').replaceAll('_',' '))+'</b><span>'+esc(x.count||0)+'</span></div><div style="height:7px;background:#EAF4FF;border-radius:99px"><div style="height:100%;width:'+((Number(x.count)||0)/max*100)+'%;background:#1565c0;border-radius:99px"></div></div></div>').join('')||'<div class="empty">'+txt('لا توجد بيانات بعد','No data yet')+'</div>';
}
function setChartEmpty(canvas,isEmpty,message){
  if(!canvas||!canvas.parentElement)return;const box=canvas.parentElement;let note=box.querySelector('.chart-empty');
  if(!note){note=document.createElement('div');note.className='chart-empty';box.appendChild(note)}
  note.textContent=message||txt('لا توجد بيانات كافية للعرض','Not enough data to display');note.style.display=isEmpty?'grid':'none';canvas.style.display=isEmpty?'none':'block';
}
function lineChart(canvas, existing, rows, label){
  if(!window.Chart||!canvas)return existing;existing?.destroy();rows=rows||[];
  setChartEmpty(canvas,!rows.length,txt('لا توجد بيانات كافية لهذا المخطط بعد.','Not enough data for this chart yet.'));
  if(!rows.length)return null;
  return new Chart(canvas,{type:'line',data:{labels:rows.map(x=>x.date),datasets:[{label,data:rows.map(x=>x.count),borderColor:'#1565c0',backgroundColor:'rgba(25,118,210,.10)',fill:true,tension:.32,pointRadius:1.5}]},options:{maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{beginAtZero:true,ticks:{precision:0}},x:{ticks:{maxTicksLimit:8}}}}});
}
function categoryChart(canvas,existing,rows,label,type='bar'){
  if(!window.Chart||!canvas)return existing;existing?.destroy();rows=rows||[];
  setChartEmpty(canvas,!rows.length,txt('لا توجد بيانات كافية بعد، أو أن النتائج أقل من حد الخصوصية.','Not enough data yet, or the cohort is below the privacy threshold.'));
  if(!rows.length)return null;
  const colors=['#1565c0','#64B5F6','#2E9D74','#F2B84B','#8B6FC0','#D96969','#63A8A5','#78909C'];
  return new Chart(canvas,{type,data:{labels:rows.map(x=>x.label),datasets:[{label,data:rows.map(x=>Number(x.count)||0),backgroundColor:colors,borderColor:colors,borderWidth:1,borderRadius:type==='bar'?7:0}]},options:{maintainAspectRatio:false,plugins:{legend:{display:type!=='bar'}},scales:type==='bar'?{y:{beginAtZero:true,ticks:{precision:0}}}:{}}});
}


let ANALYSIS_RESULTS=[];
function safeResultUrl(value){try{const u=new URL(String(value||''),location.origin);return /^https?:$/.test(u.protocol)?u.href:''}catch(e){return ''}}
function resultText(value){return esc(value||'—').replace(/\n/g,'<br>')}
function resultListText(value){if(!value)return '<span class="muted">—</span>';return '<div style="white-space:normal;line-height:1.8">'+resultText(value)+'</div>'}
function closeAnalysisResultDetails(){const detail=document.getElementById('analysisResultDetails');if(detail)detail.style.display='none';}
function renderResultDetails(id){
  const r=ANALYSIS_RESULTS.find(x=>x.analysis_id===id),box=document.getElementById('analysisResultDetails');if(!r||!box)return;
  const sources=(r.medical_sources||[]).map(x=>{const href=safeResultUrl(x.url);return '<div style="margin:5px 0">📚 '+esc(x.name||'Source')+(href?' · <a href="'+esc(href)+'" target="_blank" rel="noopener" style="color:var(--p);text-decoration:underline">'+txt('فتح المصدر','Open source')+'</a>':'')+'</div>'}).join('')||'<span class="muted">—</span>';
  const recs=(r.recommendations||[]).map(x=>'<div class="insight-card"><b>'+esc(x.title||txt('توصية','Recommendation'))+'</b><div class="muted" style="margin-top:5px;white-space:normal">'+resultText(x.tip||'')+'</div>'+(x.source?'<div class="muted" style="margin-top:5px">'+esc(x.source)+'</div>':'')+'</div>').join('')||'<span class="muted">—</span>';
  const dq=r.data_quality||{};
  const info=[
    [txt('معرّف التحليل','Analysis ID'),r.analysis_id],[txt('معرّف المشارك المجهول','Anonymous Participant ID'),r.participant_id],[txt('التاريخ','Date'),r.timestamp||r.date],
    [txt('اللغة','Language'),r.lang],[txt('الفئة العمرية','Age Group'),r.age_group],[txt('الجنس','Gender'),r.gender],[txt('الأعراض','Symptoms'),(r.symptoms||[]).join('، ')],
    [txt('المدة','Duration'),r.duration],[txt('الشدة','Severity'),r.severity],[txt('مستوى الخطورة','Risk Level'),r.risk],[txt('الثقة','Confidence'),r.confidence||'—'],
    [txt('حالة التقييم','Assessment Status'),r.assessment_status||'—'],[txt('طوارئ','Emergency'),r.emergency?txt('نعم','Yes'):txt('لا','No')]
  ];
  box.innerHTML='<div class="head" style="margin-bottom:12px"><div><h2 style="margin:0">🧾 '+txt('تفاصيل نتيجة التحليل','Analysis Result Details')+'</h2><p class="muted" style="margin-top:4px">'+esc(r.analysis_id)+'</p></div><button type="button" class="btn ghost" data-ss-click="closeAnalysisResultDetails">✕ '+txt('إغلاق','Close')+'</button></div>'+
    '<div class="grid">'+info.map(x=>'<div class="stat"><strong style="font-size:15px;overflow-wrap:anywhere">'+esc(x[1]??'—')+'</strong><span>'+esc(x[0])+'</span></div>').join('')+'</div>'+
    '<div class="two"><div><div class="insight-card"><b>'+txt('الاحتمالات / ملخص النتيجة','Possible Conditions / Result Summary')+'</b>'+resultListText(r.possible_conditions)+'</div><div class="insight-card"><b>'+txt('لماذا ظهرت النتيجة؟','Why this result?')+'</b>'+resultListText(r.why_result)+'</div><div class="insight-card"><b>'+txt('مطابقات قاعدة المعرفة','Knowledge Matches')+'</b>'+resultListText(r.knowledge_matches)+'</div><div class="insight-card"><b>'+txt('أسباب الخطورة','Risk Reasons')+'</b>'+resultListText(r.risk_reasons)+'</div><div class="insight-card"><b>'+txt('علامات الخطر','Danger Signs')+'</b>'+resultListText(r.danger_signs)+'</div></div>'+
    '<div><div class="insight-card"><b>'+txt('متى يطلب الرعاية الطبية؟','When to Seek Care')+'</b>'+resultListText(r.when_to_seek_care)+'</div><div class="insight-card"><b>'+txt('الرعاية المنزلية','Home Care')+'</b>'+resultListText(r.home_care)+'</div><div class="insight-card"><b>'+txt('إرشاد الأدوية','Medication Guidance')+'</b>'+resultListText(r.medication_guidance)+'</div><div class="insight-card"><b>'+txt('أسئلة للطبيب','Questions for Doctor')+'</b>'+resultListText(r.questions_for_doctor)+'</div><div class="insight-card"><b>'+txt('معلومات ما زالت مطلوبة','Needed Information')+'</b>'+resultListText(r.needed_information)+'</div></div></div>'+
    '<div class="two"><div class="insight-card"><b>'+txt('التوصيات','Recommendations')+'</b>'+recs+'</div><div><div class="insight-card"><b>'+txt('المصادر الطبية','Medical Sources')+'</b><div style="margin-top:7px">'+sources+'</div></div><div class="insight-card"><b>'+txt('جودة البيانات','Data Quality')+'</b><div class="muted" style="margin-top:7px">'+txt('الدرجة: ','Score: ')+esc(dq.score??'—')+' · '+txt('المستوى: ','Level: ')+esc(dq.level??'—')+' · '+txt('اكتمال المطلوب: ','Required completion: ')+esc(dq.required_completion??'—')+'</div></div><div class="insight-card"><b>'+txt('سياق صحي مبلّغ عنه','Reported Health Context')+'</b><div class="muted" style="margin-top:7px"><b>'+txt('الحالات: ','Conditions: ')+'</b>'+esc(r.reported_conditions||'—')+'<br><b>'+txt('الأدوية: ','Medications: ')+'</b>'+esc(r.reported_medications||'—')+'</div></div></div></div>';
  box.style.display='block';box.scrollIntoView({behavior:'smooth',block:'start'});
}
async function loadAnalysisResults(page=1){
  const table=document.getElementById('analysisResultsTable');if(!table)return;table.innerHTML='<div class="empty">'+txt('جاري تحميل النتائج…','Loading results…')+'</div>';
  const q=document.getElementById('analysisResultsSearch')?.value||'',risk=document.getElementById('analysisResultsRisk')?.value||'',lang=document.getElementById('analysisResultsLang')?.value||'';
  try{const d=(await req('/api/admin/analysis-results?page='+encodeURIComponent(page)+'&per_page=50&q='+encodeURIComponent(q)+'&risk='+encodeURIComponent(risk)+'&lang='+encodeURIComponent(lang))).results||{};ANALYSIS_RESULTS=d.records||[];
    const risks=d.risk_counts||{};document.getElementById('analysisResultsStats').innerHTML=[[d.total_eligible||0,txt('كل التحليلات المؤهلة','Eligible Analyses')],[d.with_saved_output||0,txt('نتائج محفوظة','Saved Outputs')],[risks['Urgent']||0,txt('عاجل','Urgent')],[d.total_filtered||0,txt('مطابق للفلاتر','Matching Filters')]].map(x=>'<div class="stat"><strong>'+esc(x[0])+'</strong><span>'+esc(x[1])+'</span></div>').join('');
    table.innerHTML=ANALYSIS_RESULTS.length?'<table><thead><tr><th>'+txt('معرّف التحليل','Analysis ID')+'</th><th>'+txt('التاريخ','Date')+'</th><th>'+txt('الأعراض','Symptoms')+'</th><th>'+txt('الشدة','Severity')+'</th><th>'+txt('الخطورة','Risk')+'</th><th>'+txt('الاحتمالات/النتيجة','Possibilities / Result')+'</th><th>'+txt('الثقة','Confidence')+'</th><th>'+txt('التفاصيل','Details')+'</th></tr></thead><tbody>'+ANALYSIS_RESULTS.map(r=>'<tr><td><b>'+esc(r.analysis_id)+'</b><div class="muted">'+esc(r.participant_id)+'</div></td><td>'+esc(r.date||'—')+'</td><td>'+esc((r.symptoms||[]).join('، ')||'—')+'</td><td>'+esc(r.severity||'—')+'</td><td><span class="badge '+(r.risk==='Urgent'?'urgent':r.risk==='Low Risk'?'active':'review')+'">'+esc(r.risk||'—')+'</span></td><td style="max-width:340px;white-space:normal">'+esc((r.possible_conditions||'—').slice(0,260))+'</td><td>'+esc(r.confidence||'—')+'</td><td><button type="button" class="btn ghost small" data-ss-click="renderResultDetails" data-ss-args="'+ssArgs([r.analysis_id])+'">'+txt('عرض','View')+'</button></td></tr>').join('')+'</tbody></table>':'<div class="empty">'+txt('لا توجد نتائج مطابقة.','No matching results.')+'</div>';
    const pager=document.getElementById('analysisResultsPager'),cur=Number(d.page||1),pages=Number(d.pages||1);pager.innerHTML='<button type="button" class="btn ghost small" '+(cur<=1?'disabled':'')+' data-ss-click="loadAnalysisResults" data-ss-args="'+ssArgs([cur-1])+'">← '+txt('السابق','Previous')+'</button><span class="muted" style="align-self:center">'+txt('صفحة ','Page ')+cur+' / '+pages+'</span><button type="button" class="btn ghost small" '+(cur>=pages?'disabled':'')+' data-ss-click="loadAnalysisResults" data-ss-args="'+ssArgs([cur+1])+'">'+txt('التالي','Next')+' →</button>';
    const detail=document.getElementById('analysisResultDetails');if(detail)detail.style.display='none';
  }catch(e){table.innerHTML='<div class="empty">'+txt('تعذر تحميل نتائج التحليلات.','Unable to load analysis results.')+'</div>';console.error(e)}
}

async function loadPrivacyAnalytics(){
  try{
    const d=(await req('/api/admin/privacy-analytics')).analytics||{};
    const top=(d.most_reported_symptoms||[])[0];
    document.getElementById('privacyAnalyticsStats').innerHTML=[
      [d.eligible_records||0,txt('سجلات مؤهلة للتحليل','Analytics-Eligible Records')],
      [top?top.label:'—',txt('أكثر عرض مسجل','Most Reported Symptom')],
      [d.consent_subjects||0,txt('تفضيلات Analytics المسجلة','Recorded Analytics Preferences')],
      [d.privacy_threshold||0,txt('حد الخصوصية','Privacy Threshold')]
    ].map(x=>'<div class="stat"><strong>'+esc(x[0])+'</strong><span>'+esc(x[1])+'</span></div>').join('');
    const cm=d.consent_metrics||{};document.getElementById('consentStats').innerHTML=[
      [(cm.granted||0)+'%',txt('موافقة','Granted')],[(cm.declined||0)+'%',txt('رفض','Declined')],[(cm.withdrawn||0)+'%',txt('مسحوبة','Withdrawn')]
    ].map(x=>'<div class="stat"><strong>'+esc(x[0])+'</strong><span>'+esc(x[1])+'</span></div>').join('');
    document.getElementById('privacySymptoms').innerHTML=miniBars(d.most_reported_symptoms||[],'label');
    document.getElementById('privacyAges').innerHTML=miniBars(d.age_groups||[],'label');
    document.getElementById('privacyMeds').innerHTML=miniBars(d.medication_patterns||[],'label');
    const risks=(d.risk_distribution||[]).map(x=>({label:x.label==='high'?txt('عاجل','Urgent'):x.label==='medium'?txt('يحتاج متابعة','Needs Follow-up'):x.label==='low'?txt('منخفض','Low Risk'):x.label,count:x.count}));
    document.getElementById('privacyRisk').innerHTML=miniBars(risks,'label');
    document.getElementById('privacyThresholdNote').textContent=txt('لا تُعرض أي فئة يقل عدد سجلاتها عن '+(d.privacy_threshold||0)+' لحماية الخصوصية.','Groups with fewer than '+(d.privacy_threshold||0)+' records are suppressed to protect privacy.');
  }catch(e){console.error(e)}
}

async function completeAnalytics(days=30){return (await req('/api/admin/complete-analytics?days='+encodeURIComponent(days))).analytics||{}}
async function loadHealthAnalytics(){
  try{const d=await completeAnalytics(document.getElementById('analyticsDays')?.value||30),h=d.health||{},ok=h.sufficient_data;
    document.getElementById('healthAnalyticsNotice').textContent=ok?txt('تُعرض فقط الفئات التي تضم ','Only cohorts with at least ')+(h.privacy_threshold||0)+txt(' مستخدمين مختلفين.',' distinct users are shown.'):txt('البيانات غير كافية لعرض تحليلات صحية مجمعة بأمان.','Not enough data for privacy-safe aggregate health analytics.');
    document.getElementById('healthAnalyticsStats').innerHTML=[[h.eligible_records||0,txt('السجلات المؤهلة','Eligible Records')],[h.eligible_users||0,txt('المستخدمون المجهولون','Anonymous Users')],[(h.most_reported_symptoms||[]).length,txt('أعراض قابلة للعرض','Displayable Symptoms')],[h.privacy_threshold||0,txt('حد الخصوصية','Privacy Threshold')]].map(x=>'<div class="stat"><strong>'+esc(x[0])+'</strong><span>'+esc(x[1])+'</span></div>').join('');
    const rr=document.getElementById('researchReadiness');if(rr){const enough=Number(h.eligible_users||0)>=Number(h.privacy_threshold||0);rr.innerHTML=[[h.eligible_records||0,txt('تحليلات قابلة للتصدير','Exportable analyses')],[h.eligible_users||0,txt('مشاركون مجهولون','De-identified participants')],[enough?txt('متاح','Available'):txt('عينة صغيرة','Small sample'),txt('الرسوم المجمعة','Aggregate charts')],[txt('وصفي/استكشافي','Descriptive / exploratory'),txt('الاستخدام البحثي الحالي','Current research use')]].map(x=>'<div class="stat"><strong>'+esc(x[0])+'</strong><span>'+esc(x[1])+'</span></div>').join('')}
    healthSymptomsChart=categoryChart(document.getElementById('healthSymptomsChart'),healthSymptomsChart,h.most_reported_symptoms||[],txt('التكرار','Frequency'));
    healthSeverityChart=categoryChart(document.getElementById('healthSeverityChart'),healthSeverityChart,h.severity_distribution||[],txt('التكرار','Frequency'),'doughnut');
    healthDurationChart=categoryChart(document.getElementById('healthDurationChart'),healthDurationChart,h.duration_distribution||[],txt('التكرار','Frequency'));
    healthRiskChart=categoryChart(document.getElementById('healthRiskChart'),healthRiskChart,h.risk_distribution||[],txt('التكرار','Frequency'),'doughnut');
    healthAgeChart=categoryChart(document.getElementById('healthAgeChart'),healthAgeChart,h.age_groups||[],txt('التكرار','Frequency'));
    healthGenderChart=categoryChart(document.getElementById('healthGenderChart'),healthGenderChart,h.gender_distribution||[],txt('التكرار','Frequency'),'doughnut');
  }catch(e){console.error(e)}
}
async function loadMedicationAnalytics(){
  try{const d=await completeAnalytics(document.getElementById('analyticsDays')?.value||30),m=d.medications||{},rows=m.most_used||[];
    document.getElementById('medicationNotice').textContent=m.sufficient_data?txt('أنماط وصفية مبنية على البلاغات المجمعة فقط. لا تعني الملاءمة أو الفعالية أو الأمان.','Descriptive aggregate reporting patterns only. They do not imply suitability, effectiveness, or safety.'):txt('البيانات غير كافية لعرض أنماط أدوية تحمي الخصوصية.','Not enough data for privacy-safe medication patterns.');
    document.getElementById('medicationStats').innerHTML=[[m.total_reported_mentions??'—',txt('إجمالي البلاغات','Total Reports')],[rows.length,txt('أدوية قابلة للعرض','Displayable Medications')],[(rows[0]?.label||'—'),txt('الأكثر تسجيلًا','Most Reported')],[m.privacy_threshold||0,txt('حد الخصوصية','Privacy Threshold')]].map(x=>'<div class="stat"><strong>'+esc(x[0])+'</strong><span>'+esc(x[1])+'</span></div>').join('');
    medicationChartObj=categoryChart(document.getElementById('medicationChart'),medicationChartObj,rows.map(x=>({label:x.label+' · '+x.percentage+'%',count:x.count})),txt('البلاغات','Reports'));
    document.getElementById('medicationAge').innerHTML=(m.by_age_group||[]).length?'<table><thead><tr><th>'+txt('الفئة العمرية','Age Group')+'</th><th>'+txt('الأكثر تسجيلًا','Most Reported')+'</th><th>'+txt('مستخدمون','Users')+'</th></tr></thead><tbody>'+m.by_age_group.map(x=>'<tr><td>'+esc(x.age_group)+'</td><td>'+esc(x.medication)+'</td><td>'+esc(x.distinct_users)+'</td></tr>').join('')+'</tbody></table>':'<div class="empty">'+txt('لا توجد بيانات كافية','Not enough data')+'</div>';
    const monthly={};rows.forEach(x=>(x.usage_trends||[]).forEach(t=>monthly[t.month]=(monthly[t.month]||0)+Number(t.count||0)));medicationTrendChartObj=lineChart(document.getElementById('medicationTrendChart'),medicationTrendChartObj,Object.entries(monthly).sort().map(([date,count])=>({date,count})),txt('البلاغات','Reports'));
  }catch(e){console.error(e)}
}
function heatColor(value,max){if(value==null)return '#F4F7FA';const alpha=.14+.72*(Number(value||0)/Math.max(1,max));return 'rgba(25,118,210,'+alpha+')'}
function heatGrid(headers,rows,rowKey){const values=rows.flatMap(r=>r.values||[]).filter(v=>v!=null),max=Math.max(1,...values),cols=headers.length+1;let html='<div class="heatmap-grid" style="grid-template-columns:150px repeat('+headers.length+',minmax(72px,1fr))"><div class="heatmap-cell heatmap-label">—</div>'+headers.map(h=>'<div class="heatmap-cell heatmap-label">'+esc(h)+'</div>').join('');rows.forEach(r=>{html+='<div class="heatmap-cell heatmap-label">'+esc(r[rowKey])+'</div>'+(r.values||[]).map(v=>'<div class="heatmap-cell" style="background:'+heatColor(v,max)+';color:'+(v!=null&&v/max>.55?'#fff':'#163B5C')+'">'+(v==null?'—':esc(v))+'</div>').join('')});return html+'</div>'}
async function loadHeatmap(){try{const h=(await completeAnalytics(document.getElementById('analyticsDays')?.value||30)).health||{},a=h.heatmap||{},s=h.severity_by_month||{};document.getElementById('symptomHeatmap').innerHTML=(a.symptoms||[]).length?heatGrid(a.symptoms,a.rows||[],'age_group'):'<div class="empty">'+txt('البيانات غير كافية','Not enough data')+'</div>';document.getElementById('severityHeatmap').innerHTML=(s.bands||[]).length?heatGrid(s.bands,s.rows||[],'month'):'<div class="empty">'+txt('البيانات غير كافية','Not enough data')+'</div>';document.getElementById('heatmapNotice').textContent=txt('تعني الشرطة — أن الخلية أقل من حد الخصوصية أو لا تحتوي بيانات.','A dash means the cell is below the privacy threshold or has no data.')}catch(e){console.error(e)}}

async function loadDataPulse(){
  const hero=document.getElementById('pulseHeroStats'),peopleBox=document.getElementById('pulsePeople'),kbBox=document.getElementById('pulseKnowledge'),backend=document.getElementById('pulseBackend');
  if(!hero)return;
  try{
    const d=await req('/api/admin/data-pulse'),p=d.people||{},a=d.activity||{},data=d.data||{},k=d.knowledge||{};
    if(backend)backend.textContent=(d.database_backend||'Database')+' · '+txt('مجمّع وآمن','Aggregate only');
    const heroItems=[
      ['👥',p.registered_users||0,txt('مستخدمون مسجلون','Registered users')],
      ['🩺',a.symptom_analyses||0,txt('تحليلات أعراض','Symptom analyses')],
      ['🗂️',data.stored_data_records||0,txt('سجلات التطبيق المتتبعة','Tracked application records')],
      ['🧬',data.knowledge_items||0,txt('عناصر معرفة وفهرسة','Knowledge & index items')]
    ];
    hero.innerHTML=heroItems.map(x=>'<div class="pulse-stat"><span>'+x[0]+'</span><strong>'+esc(x[1])+'</strong><span>'+esc(x[2])+'</span></div>').join('');
    const people=[
      [p.unique_visitors||0,txt('زوار فريدون مجهولو الهوية','Anonymous unique visitors')],
      [a.blood_tests||0,txt('تحاليل CBC محفوظة','Saved CBC analyses')],
      [a.chat_messages||0,txt('رسائل مساعد محفوظة','Saved assistant messages')],
      [a.followups||0,txt('متابعات أعراض','Symptom follow-ups')],
      [a.daily_checkins||0,txt('تسجيلات يومية','Daily check-ins')],
      [a.medication_plans||0,txt('خطط أدوية','Medication plans')],
      [a.feedback||0,txt('تقييمات','Feedback ratings')],
      [a.saved_comments||0,txt('تعليقات مكتوبة','Written comments')]
    ];
    peopleBox.innerHTML=people.map(x=>'<div class="pulse-row"><b>'+esc(x[0])+'</b><small>'+esc(x[1])+'</small></div>').join('');
    const knowledge=[
      [k.symptoms||0,txt('أعراض','Symptoms')],[k.conditions||0,txt('حالات','Conditions')],
      [k.relationships||0,txt('علاقات عرض ↔ حالة','Symptom ↔ condition links')],[k.combos||0,txt('أنماط Combo','Combo patterns')],
      [k.search_aliases||0,txt('مرادفات وصياغات بحث','Search aliases / phrasings')],[k.red_flag_rules||0,txt('قواعد سلامة','Safety rules')],
      [k.verified_sources||0,txt('مصادر موثقة','Verified sources')],[p.family_profiles||0,txt('ملفات عائلية','Family profiles')]
    ];
    kbBox.innerHTML=knowledge.map(x=>'<div class="pulse-row"><b>'+esc(x[0])+'</b><small>'+esc(x[1])+'</small></div>').join('')+'<div class="pulse-note" style="grid-column:1/-1">🔒 '+esc(txt('هذه أعداد مجمعة فقط؛ لا تعرض أسماء أو بريد أو نصوص صحية شخصية. رقم «سجلات التطبيق» هو مجموع الصفوف المتتبعة الموضحة في التفصيل، وليس حجم التخزين بالميجابايت أو حجم مجموعة بيانات بحثية.','Aggregate counts only—no names, emails, or personal health text. “Tracked application records” is the sum of the listed application rows, not storage size in MB or a research-dataset size.'))+'</div>';
  }catch(e){hero.innerHTML='<div class="pulse-stat" style="grid-column:1/-1"><span>⚠️</span><strong>—</strong><span>'+esc(txt('تعذر تحميل نبض البيانات','Unable to load data pulse'))+'</span></div>'}
}

async function loadUsage(){
  try{
    const [a,k,c,f]=await Promise.all([req('/api/admin/v2/analytics?days=30'),req('/api/admin/knowledge/stats'),req('/api/admin/complete-analytics?days=30'),req('/api/stats')]);
    const d=a.analytics||{}, s=k.statistics||{}, o=c.analytics?.overview||{}, cards=[
      ['👥',o.total_users,txt('إجمالي المستخدمين','Total Users')],
      ['🩺',o.total_symptom_analyses,txt('تحليلات الأعراض','Symptom Analyses')],
      ['🤖',o.total_assistant_conversations,txt('محادثات المساعد','Assistant Conversations')],
      ['☀️',o.today_activity,txt('نشاط اليوم','Today Activity')],
    ];
    document.getElementById('overviewStats').innerHTML=cards.map(x=>'<div class="stat"><span style="font-size:20px">'+x[0]+'</span><strong>'+esc(x[1]??0)+'</strong><span>'+esc(x[2])+'</span></div>').join('');
    const strength=document.getElementById('projectStrengthStats'),strengthNote=document.getElementById('projectStrengthNote');
    if(strength){const strengthItems=[
      [s.verified_sources||0,txt('مصادر طبية موثقة','Verified medical sources')],
      [s.active_diseases||0,txt('حالات صحية مغطاة','Covered conditions')],
      [s.active_symptoms||0,txt('أعراض نشطة وفريدة','Active unique symptoms')],
      ['+'+(s.symptom_growth_since_v74||0),txt('صافي زيادة الأعراض منذ V74','Net symptom growth since V74')],
      ['+'+(s.search_term_growth_since_v74||0),txt('زيادة أسماء ومرادفات البحث','Search name/alias growth')],
      [String(s.symptom_coverage_pct??0)+'%',txt('تغطية ربط الأعراض','Mapped symptom coverage')]
    ];strength.innerHTML=strengthItems.map(x=>'<div class="stat"><strong>'+esc(x[0])+'</strong><span>'+esc(x[1])+'</span></div>').join('');}
    if(strengthNote)strengthNote.textContent=txt('V76: ','V76: ')+txt('روابط مصدر–حالة: ','Source–condition citations: ')+(s.disease_source_links||0)+' · '+txt('روابط عرض–حالة: ','Symptom–condition links: ')+(s.total_relationships||0)+' (+'+(s.relationship_growth_since_v74||0)+') · '+txt('أسماء ومرادفات قابلة للمطابقة: ','Searchable names/aliases: ')+(s.search_term_entries||0)+' · '+txt('مصادر قوية أضيفت مؤخرًا: ','Authoritative sources added recently: ')+(s.recent_source_additions||0)+' · '+txt('الحالات المدعومة بمصدر: ','Conditions with sources: ')+(s.source_coverage_pct??0)+'% · '+txt('دُمج تكرار واحد وحُلّت تعارضات المرادفات.','One duplicate concept was merged and alias conflicts were resolved.');
    overviewChart=lineChart(document.getElementById('visChart'),overviewChart,d.timeline||[],txt('النشاط','Activity'));
    const fb=f.feedback||{}, reasons=f.feedback_reasons||[];
    const reasonLabels={clear:txt('واضحة','Clear'),helpful:txt('مفيدة','Helpful'),too_short:txt('مختصرة جدًا','Too short'),too_long:txt('طويلة جدًا','Too long'),unclear:txt('غير واضحة','Unclear'),not_relevant:txt('غير مرتبطة','Not relevant'),missing_detail:txt('تحتاج تفاصيل أكثر','Needs more detail'),other:txt('سبب آخر','Other')};
    const topReason=reasons.length?((reasonLabels[reasons[0].reason]||reasons[0].reason)+' · '+reasons[0].count):'—';
    document.getElementById('feedbackStats').innerHTML=[[fb.average_5?Number(fb.average_5).toFixed(1)+'/5':'—/5',txt('متوسط التقييم','Average Rating')],[fb.total||0,txt('إجمالي التقييمات','Total Ratings')],[f.fb_comments?.length||0,txt('التعليقات المحفوظة','Saved Comments')],[topReason,txt('أكثر سبب متكرر','Top Feedback Reason')]].map(x=>'<div class="stat"><strong>'+esc(x[0])+'</strong><span>'+esc(x[1])+'</span></div>').join('');
    loadPerformanceBenchmark();
  }catch(e){console.error(e);loadPerformanceBenchmark()}
}

function performanceNumber(v,digits=2){const n=Number(v);return Number.isFinite(n)?n.toFixed(digits):'—'}
function renderPerformanceBenchmark(data){
  const box=document.getElementById('performanceBenchmark');if(!box)return;
  const b=data?.benchmark;
  if(!data?.available){box.innerHTML='<div class="perf-empty">'+txt('القياس متاح عند استخدام PostgreSQL فقط. البيئة الحالية: ','This benchmark is available with PostgreSQL only. Current backend: ')+esc(data?.database_backend||'—')+'</div>';return}
  if(!b){box.innerHTML='<div class="perf-empty"><b>'+txt('Connection Pooling مفعّل، لكن لا يوجد قياس محفوظ بعد.','Connection pooling is enabled, but no saved measurement exists yet.')+'</b><br>'+txt('اضغط «تشغيل قياس سريع» للحصول على أرقام Before/After حقيقية وتخزينها للعرض.','Run the quick benchmark to capture and save real Before/After numbers.')+'</div>';return}
  const before=Number(b.before?.mean_ms),after=Number(b.after?.mean_ms),max=Math.max(before||0,after||0,0.001),bw=Math.max(2,Math.min(100,(before/max)*100)),aw=Math.max(2,Math.min(100,(after/max)*100));
  const improvement=Number(b.improvement_pct),positive=Number.isFinite(improvement)&&improvement>=0;
  box.innerHTML='<div class="perf-grid">'+[
    [performanceNumber(b.before?.mean_ms)+' ms',txt('قبل: متوسط العملية','Before: mean operation')],
    [performanceNumber(b.after?.mean_ms)+' ms',txt('بعد: متوسط العملية','After: mean operation')],
    [performanceNumber(b.speedup_x,1)+'×',txt('عامل التسريع','Measured speedup')],
    [(positive?'−':'')+performanceNumber(Math.abs(improvement),1)+'%',txt(positive?'انخفاض زمن الاتصال':'تغير زمن الاتصال',positive?'Latency reduction':'Latency change')],
    [performanceNumber(b.saved_ms_per_operation)+' ms',txt('موفّر لكل عملية','Saved per DB operation')]
  ].map(x=>'<div class="perf-metric"><strong>'+esc(x[0])+'</strong><span>'+esc(x[1])+'</span></div>').join('')+'</div>'+
  '<div class="perf-compare"><div class="perf-side"><b><span>BEFORE · '+esc(txt('اتصال جديد لكل عملية','New connection per operation'))+'</span><span>'+performanceNumber(b.before?.mean_ms)+' ms</span></b><div class="perf-track"><div class="perf-fill" style="width:'+bw+'%"></div></div><div class="muted" style="margin-top:7px">p95 '+performanceNumber(b.before?.p95_ms)+' ms · n='+esc(b.before?.n??b.sequential_requests??'—')+'</div></div><div class="perf-side after"><b><span>AFTER · Connection Pooling</span><span>'+performanceNumber(b.after?.mean_ms)+' ms</span></b><div class="perf-track"><div class="perf-fill" style="width:'+aw+'%"></div></div><div class="muted" style="margin-top:7px">p95 '+performanceNumber(b.after?.p95_ms)+' ms · n='+esc(b.after?.n??b.sequential_requests??'—')+'</div></div></div>'+
  '<div class="perf-note"><b>'+txt('الضغط المتزامن: ','Concurrent load: ')+'</b>'+esc(b.concurrent?.total_requests??'—')+' '+txt('عملية · قبل ','operations · before ')+performanceNumber(b.concurrent?.before_wall_ms)+' ms · '+txt('بعد ','after ')+performanceNumber(b.concurrent?.after_wall_ms)+' ms · <b>'+performanceNumber(b.concurrent?.speedup_x,1)+'×</b><br><b>'+txt('آخر قياس: ','Last measured: ')+'</b>'+esc((b.measured_at||'—').replace('T',' '))+' · '+esc(b.benchmark_type||'—')+'<br>ℹ️ '+txt('هذا القياس يعزل تكلفة الحصول على اتصال قاعدة البيانات فقط، ولا يمثل زمن تحميل الصفحة كاملًا.','This isolates database connection-acquisition overhead; it is not full page or end-to-end latency.')+'</div>';
}
async function loadPerformanceBenchmark(){
  const status=document.getElementById('performanceBenchmarkStatus');
  try{const d=await req('/api/admin/performance-benchmark');renderPerformanceBenchmark(d);if(status)status.textContent=''}catch(e){if(status)status.textContent=txt('تعذر تحميل قياس الأداء: ','Unable to load performance benchmark: ')+e.message}
}
async function runPerformanceBenchmark(){
  const btn=document.getElementById('runPerfBenchmarkBtn'),status=document.getElementById('performanceBenchmarkStatus');
  if(btn)btn.disabled=true;if(status)status.textContent=txt('يتم الآن قياس Before/After على قاعدة البيانات الفعلية…','Running a real Before/After measurement against the active database…');
  try{const d=await req('/api/admin/performance-benchmark',{method:'POST',body:'{}'});renderPerformanceBenchmark(d);if(status)status.textContent='✓ '+txt('تم حفظ القياس الحقيقي وعرضه في لوحة الأدمن.','Measured result saved and displayed in Admin.')}
  catch(e){if(status)status.textContent=e.message==='postgres_required'?txt('هذا القياس يحتاج PostgreSQL.','This benchmark requires PostgreSQL.'):e.message==='benchmark_already_running'?txt('يوجد قياس آخر قيد التشغيل حاليًا.','Another benchmark is already running.'):txt('تعذر تشغيل القياس: ','Benchmark failed: ')+e.message}
  finally{if(btn)btn.disabled=false}
}

async function loadDataScienceOverview(){
  try{const [g,i,a,p]=await Promise.all([req('/api/admin/knowledge-graph'),req('/api/admin/automatic-insights'),req('/api/admin/anomalies'),req('/api/admin/ai-performance?days=30')]);const gs=g.graph?.stats||{},ins=i.insights?.insights||[],an=a.anomalies?.findings||[],perf=p.performance||{},v=[[gs.diseases||0,txt('أمراض في الرسم','Graph Diseases')],[gs.symptoms||0,txt('أعراض في الرسم','Graph Symptoms')],[gs.verified_sources||0,txt('مصادر موثقة','Verified Sources')],[ins.length,txt('ملاحظات مولدة','Generated Insights')],[an.length,txt('أنماط غير معتادة','Detected Anomalies')],[perf.total_ai_requests||0,txt('طلبات AI','AI Requests')]];document.getElementById('dataScienceOverview').innerHTML=v.map(x=>'<div class="stat"><strong>'+esc(x[0])+'</strong><span>'+esc(x[1])+'</span></div>').join('')}catch(e){console.error(e)}}

async function loadV2Analytics(){
  try{
    const days=document.getElementById('analyticsDays')?.value||30;
    const [base,full]=await Promise.all([req('/api/admin/v2/analytics?days='+days),req('/api/admin/complete-analytics?days='+days)]),d=base.analytics||{},u=full.analytics?.users||{},p=d.periods||{};
    const items=[[u.total,txt('المستخدمون','Users')],[u.new,txt('المستخدمون الجدد','New Users')],[u.active,txt('المستخدمون النشطون','Active Users')],[u.analyses,txt('التحليلات','Analyses')],[d.assistant_uses,txt('استخدامات المساعد','Assistant uses')],[d.alerts,txt('تنبيهات الأمان','Safety alerts')],[d.errors,txt('الأخطاء','Errors')],[d.average_response_ms??'—',txt('متوسط الاستجابة ms','Avg response ms')]];
    document.getElementById('v2AnalyticsStats').innerHTML=items.map(x=>'<div class="stat"><strong>'+esc(x[0]??0)+'</strong><span>'+esc(x[1])+'</span></div>').join('');
    document.getElementById('v2Services').innerHTML=miniBars(d.services||[]);
    document.getElementById('topSymptoms').innerHTML=miniBars(d.top_symptoms||[]);
    document.getElementById('v2Segments').innerHTML='<h3 style="font-size:13px;margin-bottom:6px">'+txt('اللغة','Language')+'</h3>'+Object.entries(u.languages||{}).map(([k,v])=>'<span class="badge active" style="margin:3px">'+esc(k)+': '+v+'</span>').join('')+'<h3 style="font-size:13px;margin:12px 0 6px">'+txt('الجهاز','Device')+'</h3>'+Object.entries(u.devices||{}).map(([k,v])=>'<span class="badge verified" style="margin:3px">'+esc(k)+': '+v+'</span>').join('')+'<h3 style="font-size:13px;margin:12px 0 6px">'+txt('الفئات العمرية المسموح بعرضها','Privacy-safe age groups')+'</h3>'+miniBars(u.age_groups||[],'label');
    document.getElementById('v2Sections').innerHTML='<table><thead><tr><th>'+txt('المسار','Path')+'</th><th>'+txt('الاستخدام','Uses')+'</th></tr></thead><tbody>'+(d.sections||[]).map(x=>'<tr><td data-label="Path">'+esc(x.path)+'</td><td data-label="Uses">'+x.count+'</td></tr>').join('')+'</tbody></table>';
    usersChart=lineChart(document.getElementById('usersTimeline'),usersChart,d.users_timeline||[],txt('المستخدمون الجدد','New users'));
    analysesChart=lineChart(document.getElementById('analysesTimeline'),analysesChart,d.analyses_timeline||[],txt('التحليلات','Analyses'));
    assistantChart=lineChart(document.getElementById('assistantTimeline'),assistantChart,d.assistant_timeline||[],txt('المساعد','Assistant'));
    activityChart=lineChart(document.getElementById('v2Timeline'),activityChart,d.timeline||[],txt('النشاط','Activity'));
  }catch(e){console.error(e)}
}

function auditUI(action,section){req('/api/admin/ui-audit',{method:'POST',body:JSON.stringify({action,section})}).catch(()=>{})}
function toggleExportDates(){const on=document.getElementById('aePeriod').value==='custom';document.getElementById('aeStartWrap').style.display=on?'flex':'none';document.getElementById('aeEndWrap').style.display=on?'flex':'none'}
function exportQuery(prefix='ae'){const ids={period:'Period',start:'Start',end:'End',age_group:'Age',gender:'Gender',medication:'Medication',symptom:'Symptom',risk:'Risk'},q=new URLSearchParams();Object.entries(ids).forEach(([k,sfx])=>{const el=document.getElementById(prefix+sfx);if(el&&el.value)q.set(k,el.value)});return q.toString()}
async function previewAnalyticsExport(){const st=document.getElementById('aeStatus');try{st.textContent=txt('جاري تجهيز المعاينة…','Preparing preview…');const d=await req('/api/admin/analytics-export/preview?'+exportQuery());const p=d.preview||{};document.getElementById('aePreview').innerHTML=[[p.total_medication_records||0,txt('سجلات أدوية','Medication records')],[p.unique_medications||0,txt('أدوية فريدة','Unique medications')],[p.most_frequent_medication||'—',txt('الأكثر تسجيلًا','Most recorded')],[p.most_represented_age_group||'—',txt('الفئة العمرية الأبرز','Most represented age group')],[p.top_association||'—',txt('أعلى اقتران متاح','Top available association')]].map(x=>'<div class="stat"><strong>'+esc(x[0])+'</strong><span>'+esc(x[1])+'</span></div>').join('');st.textContent=p.sufficient?txt('✓ المعاينة جاهزة. حد الخصوصية: ','✓ Preview ready. Privacy threshold: ')+d.privacy_threshold:txt('لا توجد بيانات كافية لإظهار تفاصيل آمنة.','Insufficient data for privacy-safe detail.')}catch(e){st.textContent=txt('تعذر تجهيز المعاينة.','Unable to prepare preview.')}}
async function downloadAnalyticsExport(){const st=document.getElementById('aeStatus');st.textContent=txt('جاري تجهيز البيانات…','Preparing your data…');try{const r=await fetch('/api/admin/analytics-export/xlsx?'+exportQuery(),{headers:{'X-CSRF-Token':CSRF}});if(!r.ok)throw new Error('export_failed');const blob=await r.blob(),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;const cd=r.headers.get('content-disposition')||'';a.download=(cd.match(/filename="?([^";]+)/)||[])[1]||'SymptoSense_Data_Analytics.xlsx';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1500);st.textContent=txt('✓ تم إنشاء تقرير Excel بنجاح.','✓ Excel report generated successfully.')}catch(e){st.textContent=txt('تعذر تصدير البيانات. حاول مرة أخرى.','Unable to export data. Please try again.')}}
function toggleDropDates(){const on=document.getElementById('dropPeriod').value==='custom';document.getElementById('dropStart').style.display=on?'inline-block':'none';document.getElementById('dropEnd').style.display=on?'inline-block':'none'}
async function loadDropoff(){try{const q=new URLSearchParams({period:document.getElementById('dropPeriod').value,device:document.getElementById('dropDevice').value});if(document.getElementById('dropPeriod').value==='custom'){q.set('start',document.getElementById('dropStart').value);q.set('end',document.getElementById('dropEnd').value)}const d=(await req('/api/admin/dropoff?'+q)).dropoff||{},hi=d.highest_dropoff||{};document.getElementById('dropStats').innerHTML=[[d.sessions||0,txt('الجلسات','Sessions')],[(d.completion_rate||0)+'%',txt('نسبة الإكمال','Completion rate')],[hi.label||'—',txt('أعلى مرحلة تسرب','Highest drop-off')],[(hi.dropoff_rate||0)+'%',txt('نسبة أعلى تسرب','Highest drop-off rate')]].map(x=>'<div class="stat"><strong>'+esc(x[0])+'</strong><span>'+esc(x[1])+'</span></div>').join('');const stages=d.stages||[],max=Math.max(1,...stages.map(x=>x.users||0));document.getElementById('funnelList').innerHTML=stages.length?stages.map(x=>'<div class="funnel-row" title="Users: '+x.users+' · Conversion: '+x.conversion_rate+'% · Drop-off: '+x.dropoff_rate+'%"><div class="funnel-top"><b>'+esc(x.label)+'</b><span>'+x.users+' · '+x.conversion_rate+'% · ↓ '+x.dropoff_rate+'%</span></div><div class="funnel-track"><div class="funnel-fill" style="width:'+Math.max(2,(x.users/max*100))+'%"></div></div></div>').join(''):'<div class="empty">'+txt('لا توجد بيانات نشاط بعد.','No activity data available yet.')+'</div>'}catch(e){console.error(e)}}
async function loadLive(){if(livePaused)return;try{const q=new URLSearchParams({category:document.getElementById('liveCategory').value,window:document.getElementById('liveWindow').value});const d=(await req('/api/admin/live-activity?'+q)).activity||{},m=d.metrics||{};document.getElementById('liveStats').innerHTML=[[m.active_sessions||0,txt('جلسات نشطة','Active Sessions')],[m.analyses_today||0,txt('تحليلات اليوم','Analyses Today')],[m.analyses_in_progress||0,txt('تحليلات قيد التنفيذ','Analyses in Progress')],[m.reports_today||0,txt('تقارير اليوم','Reports Today')]].map(x=>'<div class="stat"><strong>'+esc(x[0])+'</strong><span>'+esc(x[1])+'</span></div>').join('');const rows=d.events||[];document.getElementById('liveFeed').innerHTML=rows.length?rows.map(x=>'<div class="live-event"><time>'+esc(String(x.timestamp||'').slice(11,19))+'</time><div><span class="live-dot '+(x.status==='error'?'err':'')+'"></span><b>'+esc(x.label)+'</b></div><span class="badge '+(x.status==='error'?'offline':'online')+'">'+esc(x.category)+'</span></div>').join(''):'<div class="empty">'+txt('لا توجد بيانات نشاط بعد.','No activity data available yet.')+'</div>';liveChartObj=lineChart(document.getElementById('liveChart'),liveChartObj,d.trend||[],txt('الأحداث','Events'))}catch(e){console.error(e)}}
function startLive(){if(liveTimer)clearInterval(liveTimer);if(!livePaused)liveTimer=setInterval(()=>{if(document.visibilityState==='visible'&&document.getElementById('view-live')?.classList.contains('on'))loadLive()},5000)}
function toggleLive(){livePaused=!livePaused;document.getElementById('livePause').textContent=livePaused?('▶ '+txt('استئناف التحديث','Resume Live Updates')):('⏸ '+txt('إيقاف التحديث','Pause Live Updates'));if(livePaused&&liveTimer){clearInterval(liveTimer);liveTimer=null}else{loadLive();startLive()}}
function gapEmpty(message){return '<div class="empty">'+esc(message||txt('لا توجد فجوات مسجلة ضمن هذه الفترة.','No gaps recorded in this period.'))+'</div>'}
function gapDate(value){const s=String(value||'');return s?s.slice(0,10):'—'}
function gapReasonLabel(reason){const m={not_answered:["لم تتم الإجابة","Not answered"],need_more:["احتاج تفاصيل أكثر","Needed more detail"],not_relevant:["الإجابة غير مرتبطة","Not relevant"],unclear:["الإجابة غير واضحة","Unclear"]};return (m[reason]||[String(reason||'—'),String(reason||'—')])[AR?0:1]}
async function loadContentGaps(){
  const stats=document.getElementById('contentGapStats');
  if(!stats)return;
  const days=document.getElementById('contentGapDays')?.value||30;
  const ids=['gapSearches','gapSymptoms','gapSources','gapCoverage','gapReview','gapAssistant'];
  stats.innerHTML='<div class="empty">'+txt('جاري تحليل فجوات المحتوى…','Analyzing content gaps…')+'</div>';
  ids.forEach(id=>{const el=document.getElementById(id);if(el)el.innerHTML=gapEmpty(txt('جاري التحميل…','Loading…'))});
  try{
    const d=await req('/api/admin/content-gaps?days='+encodeURIComponent(days)+'&limit=20'),g=d.content_gaps||{},sm=g.summary||{};
    const cards=[
      [sm.unique_search_gaps||0,txt('عبارات بحث تحتاج تغطية','Search gaps')],
      [sm.unmatched_symptom_occurrences||0,txt('مرات عدم فهم عرض','Unmatched symptom uses')],
      [sm.weak_source_conditions||0,txt('حالات تحتاج مصادر أقوى','Weak-source conditions')],
      [sm.coverage_items||0,txt('فجوات ربط/توثيق','Coverage gaps')],
      [sm.review_due||0,txt('عناصر تحتاج مراجعة','Review queue')],
      [sm.assistant_unmet_feedback||0,txt('إشارات نقص من المساعد','Assistant gap signals')]
    ];
    stats.innerHTML=cards.map(x=>'<div class="stat"><strong>'+esc(x[0])+'</strong><span>'+esc(x[1])+'</span></div>').join('');

    const search=g.search_gaps||[],sx=document.getElementById('gapSearches');
    sx.innerHTML=search.length?'<table><thead><tr><th>'+txt('العبارة','Phrase')+'</th><th>'+txt('اللغة','Lang')+'</th><th>'+txt('التكرار','Count')+'</th><th>'+txt('آخر ظهور','Last seen')+'</th></tr></thead><tbody>'+search.map(x=>'<tr><td><b>'+esc(x.phrase)+'</b></td><td>'+esc(x.lang||'—')+'</td><td>'+esc(x.count||0)+'</td><td>'+esc(gapDate(x.last_seen))+'</td></tr>').join('')+'</tbody></table>':gapEmpty();

    const unmatched=g.unmatched_symptoms||[],ux=document.getElementById('gapSymptoms');
    ux.innerHTML=unmatched.length?'<table><thead><tr><th>'+txt('العبارة','Phrase')+'</th><th>'+txt('اللغة','Lang')+'</th><th>'+txt('التكرار','Count')+'</th></tr></thead><tbody>'+unmatched.map(x=>'<tr><td><b>'+esc(x.phrase)+'</b></td><td>'+esc(x.lang||'—')+'</td><td>'+esc(x.count||0)+'</td></tr>').join('')+'</tbody></table>':gapEmpty();

    const weak=g.weak_source_conditions||[],wx=document.getElementById('gapSources');
    wx.innerHTML=weak.length?'<table><thead><tr><th>'+txt('الحالة','Condition')+'</th><th>'+txt('مصادر موثقة','Verified sources')+'</th></tr></thead><tbody>'+weak.map(x=>'<tr><td><b>'+esc(AR?x.name_ar:x.name_en)+'</b><div class="muted">'+esc(x.slug||'')+'</div></td><td>'+esc(x.verified_source_count||0)+'</td></tr>').join('')+'</tbody></table>':gapEmpty(txt('كل الحالات لديها مصدران موثقان على الأقل.','Every condition has at least two verified sources.'));

    const cov=g.coverage_gaps||[],cx=document.getElementById('gapCoverage');
    cx.innerHTML=cov.length?'<table><thead><tr><th>'+txt('العرض','Symptom')+'</th><th>'+txt('روابط حالات','Condition links')+'</th><th>'+txt('مصادر العرض','Symptom sources')+'</th></tr></thead><tbody>'+cov.map(x=>'<tr><td><b>'+esc(AR?x.name_ar:x.name_en)+'</b><div class="muted">'+esc(x.slug||'')+'</div></td><td>'+esc(x.condition_links||0)+'</td><td>'+esc(x.verified_source_count||0)+'</td></tr>').join('')+'</tbody></table>':gapEmpty(txt('لا توجد فجوات ربط أو توثيق على مستوى العرض.','No symptom-level linkage/source gaps.'));

    const review=g.review_queue||[],rx=document.getElementById('gapReview');
    rx.innerHTML=review.length?'<table><thead><tr><th>'+txt('العنصر','Item')+'</th><th>'+txt('النوع','Type')+'</th><th>'+txt('الحالة','Status')+'</th><th>'+txt('آخر مراجعة','Last review')+'</th></tr></thead><tbody>'+review.map(x=>'<tr><td><b>'+esc(AR?x.name_ar:x.name_en)+'</b></td><td>'+esc(x.entity_type||'—')+'</td><td>'+statusBadge(x.review_status||'review')+'</td><td>'+esc(gapDate(x.last_reviewed))+'</td></tr>').join('')+'</tbody></table>':gapEmpty(txt('كل المحتوى ضمن فترة المراجعة المحددة.','All content is within the configured review window.'));

    const unmet=g.assistant_unmet_reasons||[],ax=document.getElementById('gapAssistant');
    ax.innerHTML=unmet.length?'<table><thead><tr><th>'+txt('إشارة التحسين','Signal')+'</th><th>'+txt('التكرار','Count')+'</th></tr></thead><tbody>'+unmet.map(x=>'<tr><td><b>'+esc(gapReasonLabel(x.reason))+'</b></td><td>'+esc(x.count||0)+'</td></tr>').join('')+'</tbody></table>':gapEmpty(txt('لا توجد تقييمات سلبية مصنفة للمساعد ضمن البيانات الحالية.','No categorized negative assistant feedback in the current data.'));
  }catch(e){
    stats.innerHTML='<div class="empty">'+esc(txt('تعذر تحميل فجوات المحتوى: ','Unable to load content gaps: ')+e.message)+'</div>';
    ids.forEach(id=>{const el=document.getElementById(id);if(el)el.innerHTML=gapEmpty(txt('تعذر التحميل.','Unable to load.'))});
  }
}

async function loadKB(){
  try{
    KB=await req('/api/admin/knowledge/bootstrap');
    document.querySelectorAll('.category-filter').forEach(el=>{const cur=el.value;el.innerHTML='<option value="">'+txt('كل الفئات','All categories')+'</option>'+opts(KB.categories||[],c=>AR?c.name_ar:c.name_en);el.value=cur});
    renderStats(); ['diseases','symptoms','relationships','sources','redflags'].forEach(render); renderCategories();
    loadKnowledgeReview();
  }catch(e){alert(e.message)}
}
async function loadKnowledgeReview(){
  const stats=document.getElementById('knowledgeReviewStats'),table=document.getElementById('knowledgeReviewTable');if(!stats||!table)return;
  table.innerHTML='<div class="empty">'+txt('جاري فحص المحتوى…','Checking content…')+'</div>';
  try{const days=document.getElementById('reviewAge')?.value||365,d=(await req('/api/admin/knowledge/review-status?days='+encodeURIComponent(days))).review||{},c=d.counts||{},rows=d.queue||[];stats.innerHTML=[[c.verified||0,txt('محدث وموثق','Current & verified')],[c.outdated||0,txt('متجاوز مدة المراجعة','Outdated')],[c.source_missing||0,txt('مصدر موثق مفقود','Missing verified source')],[c.needs_review||0,txt('يحتاج مراجعة','Needs review')]].map(x=>'<div class="stat"><strong>'+esc(x[0])+'</strong><span>'+esc(x[1])+'</span></div>').join('');table.innerHTML=rows.length?'<table><thead><tr><th>'+txt('النوع','Type')+'</th><th>'+txt('المحتوى','Content')+'</th><th>'+txt('الحالة','Status')+'</th><th>'+txt('آخر مراجعة','Last reviewed')+'</th><th>'+txt('العمر بالأيام','Age (days)')+'</th><th>'+txt('المصادر','Sources')+'</th></tr></thead><tbody>'+rows.slice(0,100).map(x=>'<tr><td>'+esc(x.entity_type)+'</td><td><b>'+esc(AR?(x.name_ar||x.name_en):(x.name_en||x.name_ar))+'</b></td><td>'+statusBadge(x.review_status)+'</td><td>'+esc(x.last_reviewed||'—')+'</td><td>'+esc(x.age_days==null?'—':x.age_days)+'</td><td>'+esc(x.source_count==null?'—':x.source_count)+'</td></tr>').join('')+'</tbody></table>':'<div class="empty">✓ '+txt('لا توجد عناصر مستحقة للمراجعة ضمن المدة المحددة.','No items are due for review in the selected interval.')+'</div>'}catch(e){table.innerHTML='<div class="empty">'+esc(e.message)+'</div>'}
}
function renderStats(){
  const s=KB.statistics||{},items=[[s.active_diseases,txt('حالات نشطة','Active conditions')],[s.active_symptoms,txt('أعراض نشطة وفريدة','Active unique symptoms')],[s.total_relationships,txt('روابط عرض–حالة','Symptom–condition links')],['+'+(s.symptom_growth_since_v74||0),txt('صافي زيادة الأعراض منذ V74','Net symptom growth since V74')],[s.search_term_entries||0,txt('أسماء ومرادفات البحث','Search names / aliases')],['+'+(s.search_term_growth_since_v74||0),txt('زيادة البحث منذ V74','Search-entry growth since V74')],[s.verified_sources,txt('مصادر موثقة','Verified sources')],[s.active_red_flags,txt('قواعد أمان نشطة','Active safety rules')],[s.high_authority_sources,txt('مصادر عالية السلطة','High-authority sources')],[s.last_knowledge_update?String(s.last_knowledge_update).slice(0,10):'—',txt('آخر تحديث','Last update')]];
  document.getElementById('kbStats').innerHTML=items.map(x=>'<div class="stat"><strong>'+esc(x[0]??0)+'</strong><span>'+esc(x[1])+'</span></div>').join('');
  const quality=document.getElementById('knowledgeQuality'),version=document.getElementById('knowledgeVersion'),note=document.getElementById('knowledgeQualityNote');
  if(version)version.textContent=s.knowledge_version||'—';
  if(quality){const q=[[String(s.symptom_support_coverage_pct??s.symptom_coverage_pct??0)+'%',txt('تغطية الأعراض بالمصدر/الأمان','Source/safety symptom support')],[String(s.symptom_coverage_pct??0)+'%',txt('مرتبطة بحالة صحية','Mapped to a health condition')],[s.safety_only_symptoms??0,txt('أعراض أمان فقط','Safety-only symptoms')],[s.unsupported_symptoms??s.unlinked_symptoms??0,txt('أعراض بلا دعم بعد','Unsupported symptoms')],[String(s.source_coverage_pct??0)+'%',txt('الحالات المدعومة بمصادر','Conditions with sources')],[s.avg_sources_per_disease??0,txt('متوسط المصادر لكل حالة','Avg sources per condition')]];quality.innerHTML=q.map(x=>'<div class="stat"><strong>'+esc(x[0])+'</strong><span>'+esc(x[1])+'</span></div>').join('')}
  if(note){const dist=s.source_type_distribution||{};const strong=(s.high_authority_sources??0);const pending=(s.sources_needing_review??0);note.innerHTML='🔎 '+esc(txt('مصادر عالية السلطة: ','High-authority sources: '))+esc(strong)+' · '+esc(txt('روابط مصدر–حالة: ','Source–condition links: '))+esc(s.disease_source_links??0)+' · '+esc(txt('بانتظار مراجعة: ','Pending review: '))+esc(pending)+(Object.keys(dist).length?' · '+esc(txt('تنوع أنواع المصادر: ','Source-type diversity: '))+esc(Object.keys(dist).length):'')}
}
function renderCategories(){
  const box=document.getElementById('categories'), rows=KB.categories||[]; if(!box)return;
  box.innerHTML=rows.length?'<div class="table-wrap"><table><thead><tr><th>ID</th><th>'+txt('العربي','Arabic')+'</th><th>'+txt('الإنجليزي','English')+'</th><th>Status</th><th>'+txt('إجراءات','Actions')+'</th></tr></thead><tbody>'+rows.map(x=>'<tr><td>#'+x.id+'</td><td>'+esc(x.name_ar)+'</td><td>'+esc(x.name_en)+'</td><td>'+statusBadge(x.status)+'</td><td><button type="button" class="btn ghost small" data-ss-click="openEditor" data-ss-args="'+ssArgs(['category',x.id])+'">✏️</button> <button type="button" class="btn danger small" data-ss-click="removeItem" data-ss-args="'+ssArgs(['category',x.id])+'">🗑️</button></td></tr>').join('')+'</tbody></table></div>':'<div class="empty">'+txt('لا توجد فئات','No categories')+'</div>';
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
  const body=rows.map(x=>'<tr>'+cols.map(c=>'<td data-label="'+esc(c[1])+'">'+((c[0]==='status'||c[0]==='verification_status'||c[0]==='risk_level')?statusBadge(x[c[0]]):(c[0]==='official_url'?'<a href="'+esc(x[c[0]]||'#')+'" target="_blank" rel="noopener">'+esc(x[c[0]]||'—')+'</a>':esc(x[c[0]]??'—')))+'</td>').join('')+'<td data-label="Actions"><button type="button" class="btn ghost small" data-ss-click="openEditor" data-ss-args="'+ssArgs([(kind==='redflags'?'red_flag':kind==='relationships'?'relationship':kind.slice(0,-1)),x.id])+'">✏️</button> <button type="button" class="btn danger small" data-ss-click="removeItem" data-ss-args="'+ssArgs([(kind==='redflags'?'red_flag':kind==='relationships'?'relationship':kind.slice(0,-1)),x.id])+'">🗑️</button></td></tr>').join('');
  box.innerHTML=rows.length?'<table><thead><tr>'+head+'</tr></thead><tbody>'+body+'</tbody></table>':'<div class="empty">'+txt('لا توجد بيانات','No data yet')+'</div>';
}
function opts(rows,label,id='id',selected=[]){selected=(selected||[]).map(String);return rows.map(x=>'<option value="'+esc(x[id])+'" '+(selected.includes(String(x[id]))?'selected':'')+'>'+esc(label(x))+'</option>').join('')}
function field(label,name,value='',type='text',full=false,extra=''){if(type==='textarea')return '<div class="field '+(full?'full':'')+'"><label>'+esc(label)+'</label><textarea name="'+name+'">'+esc(value)+'</textarea></div>';return '<div class="field '+(full?'full':'')+'"><label>'+esc(label)+'</label><input type="'+type+'" name="'+name+'" value="'+esc(value)+'" '+extra+'></div>'}
function selectField(label,name,options,value='',full=false,multiple=false){return '<div class="field '+(full?'full':'')+'"><label>'+esc(label)+'</label><select name="'+name+'" '+(multiple?'multiple size="6"':'')+'>'+options+'</select></div>'}

async function loadContent(){try{CONTENT=(await req('/api/admin/content')).content||[];renderContent()}catch(e){alert(e.message)}}
function renderContent(){
  const box=document.getElementById('table-content');if(!box)return;const q=(document.getElementById('contentSearch')?.value||'').toLowerCase(),type=document.getElementById('contentType')?.value||'',rows=CONTENT.filter(x=>(!type||x.content_type===type)&&JSON.stringify(x).toLowerCase().includes(q));
  box.innerHTML=rows.length?'<table><thead><tr><th>ID</th><th>'+txt('العنوان','Title')+'</th><th>'+txt('النوع','Type')+'</th><th>'+txt('الفئة','Category')+'</th><th>'+txt('الحالة','Status')+'</th><th>Version</th><th>'+txt('إجراءات','Actions')+'</th></tr></thead><tbody>'+rows.map(x=>'<tr><td>#'+x.id+'</td><td>'+esc(AR?x.title_ar:x.title_en)+'</td><td>'+esc(x.content_type)+'</td><td>'+esc(x.category)+'</td><td>'+statusBadge(x.status)+'</td><td>'+x.version+'</td><td><button type="button" class="btn ghost small" data-ss-click="openContentEditor" data-ss-args="'+ssArgs([x.id])+'">✏️</button> <button type="button" class="btn danger small" data-ss-click="removeContent" data-ss-args="'+ssArgs([x.id])+'">🗑️</button></td></tr>').join('')+'</tbody></table>':'<div class="empty">'+txt('لا يوجد محتوى','No content')+'</div>';
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
  if(kind==='source')h=field('Source name','source_name',x.source_name)+field('Organization','organization',x.organization)+field('Official HTTPS URL','official_url',x.official_url,'url',true)+field('الوصف','description_ar',x.description_ar,'textarea')+field('Description','description_en',x.description_en,'textarea')+selectField('Language','language','<option value="multiple">Arabic + English</option><option value="ar">Arabic</option><option value="en">English</option>',x.language)+selectField('Reliability','reliability_level','<option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>',x.reliability_level)+selectField('Source type','source_type','<option value="government">Government</option><option value="international_organization">International Organization</option><option value="national_health_service">National Health Service</option><option value="academic_medical_institution">Academic Medical Institution</option><option value="clinical_guideline_body">Clinical Guideline Body</option><option value="other_trusted_source">Other Trusted Source</option>',x.source_type)+selectField('Verification','verification_status','<option value="verified">Verified</option><option value="needs_review">Needs Review</option><option value="disabled">Disabled</option>',x.verification_status)+field('Last verified','last_verified',x.last_verified||new Date().toISOString().slice(0,10),'date')+field('Priority','priority',x.priority||50,'number')+status;
  if(kind==='relationship')h=selectField('Disease','disease_id',opts(KB.diseases||[],d=>AR?d.name_ar:d.name_en,'id',[x.disease_id]),x.disease_id)+selectField('Symptom','symptom_id',opts(KB.symptoms||[],v=>AR?v.name_ar:v.name_en,'id',[x.symptom_id]),x.symptom_id)+field('Relevance / Weight (0.1–1)','weight',x.weight||.5,'number',false,'min="0.1" max="1" step="0.05"')+selectField('Typicality','typicality','<option value="very_common">Very common</option><option value="common">Common</option><option value="less_common">Less common</option>',x.typicality)+field('ملاحظات','notes_ar',x.notes_ar,'textarea')+field('Notes','notes_en',x.notes_en,'textarea')+status;
  if(kind==='red_flag'){
    const rfStatus=selectField('Status','status','<option value="active">Active</option><option value="disabled">Disabled</option>',x.status||'active');
    h=field('الاسم العربي','name_ar',x.name_ar)+field('English name','name_en',x.name_en)
      +field('الوصف العربي','description_ar',x.description_ar,'textarea',true)+field('English description','description_en',x.description_en,'textarea',true)
      +selectField('Required symptoms','required_symptoms',opts(KB.symptoms||[],v=>(AR?v.name_ar:v.name_en)+' — '+v.slug,'slug',x.required_symptoms||[]),'',true,true)
      +field('Keywords AR (comma separated)','keywords_ar',(x.keywords_ar||[]).join(', '),'text',true)+field('Keywords EN (comma separated)','keywords_en',(x.keywords_en||[]).join(', '),'text',true)
      +selectField('Match mode','match_mode','<option value="all">All</option><option value="any">Any</option>',x.match_mode)
      +field('Min severity','min_severity',x.min_severity||1,'number',false,'min="1" max="5"')
      +selectField('Risk','risk_level','<option value="urgent">Urgent</option><option value="review">Needs review</option>',x.risk_level)
      +field('رسالة الأمان','message_ar',x.message_ar,'textarea')+field('Safety message','message_en',x.message_en,'textarea')
      +field('الإجراء الموصى به','recommended_action_ar',x.recommended_action_ar,'textarea',true)+field('Recommended action','recommended_action_en',x.recommended_action_en,'textarea',true)
      +selectField('Verified source','source_id',opts((KB.sources||[]).filter(v=>v.status==='active'&&v.verification_status==='verified'),v=>v.source_name,'id',[x.source_id]),x.source_id)
      +field('Official reference URL','reference_url',x.reference_url,'url',true)
      +field('Last updated','last_updated',(x.last_updated||new Date().toISOString()).slice(0,10),'date')+rfStatus;
  }
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
  try{const saveRes=await req(url,{method,body:JSON.stringify(p)});document.getElementById('modalMsg').className='msg ok show';document.getElementById('modalMsg').textContent=(saveRes&&saveRes.pending_review)?txt('أُرسل للمراجعة السريرية ولم يُنشر بعد. يعتمده مراجع آخر من صفحة المراجعة.','Sent for clinical review - not published yet. Another reviewer approves it on the review page.'):txt('تم الحفظ بنجاح','Saved successfully');if(kind==='content')await loadContent();else await loadKB();setTimeout(closeModal,450)}catch(err){document.getElementById('modalMsg').className='msg err show';document.getElementById('modalMsg').textContent=err.message}
};
async function removeItem(kind,id){
  if(!confirm(txt('هل أنت متأكد؟ للمحتوى الطبي المنشور يفضّل التعطيل بدل الحذف.','Are you sure? For published medical content, disabling is usually safer.')))return;
  const plural=kind==='red_flag'?'red-flags':kind==='relationship'?'relationships':kind==='category'?'categories':kind+'s';
  try{await req('/api/admin/'+plural+'/'+id,{method:'DELETE',body:'{}'});await loadKB()}catch(e){alert(e.message)}
}

async function exportData(){
  const boxes=[document.getElementById('exportStatus'),document.getElementById('researchExportStatus')].filter(Boolean);boxes.forEach(box=>box.textContent=txt('جاري تجهيز ملف البحث الشامل…','Preparing the comprehensive research workbook…'));
  try{const r=await fetch('/api/admin/export/xlsx',{headers:{'X-CSRF-Token':CSRF}});if(!r.ok)throw new Error('export_failed');const b=await r.blob();const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='SymptoSense_Research_Export_'+new Date().toISOString().slice(0,10)+'.xlsx';document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(a.href);boxes.forEach(box=>box.textContent='✓ '+txt('تم إنشاء ملف البحث الشامل','Research workbook created'))}catch(e){boxes.forEach(box=>box.textContent=txt('تعذر تصدير ملف البحث. حاول مرة أخرى.','Unable to export the research workbook. Please try again.'))}
}
async function exportPilotWorkbook(){const boxes=[document.getElementById('exportStatus'),document.getElementById('researchExportStatus')].filter(Boolean);boxes.forEach(box=>box.textContent=txt('جاري تجهيز بيانات Pilot المنفصلة…','Preparing separate Pilot data…'));try{const r=await fetch('/api/admin/export/pilot-xlsx',{headers:{'X-CSRF-Token':CSRF}});if(!r.ok)throw new Error('export_failed');const b=await r.blob();const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='SymptoSense_Pilot_Data_'+new Date().toISOString().slice(0,10)+'.xlsx';document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(a.href);boxes.forEach(box=>box.textContent='✓ '+txt('تم إنشاء ملف Pilot منفصل','Separate Pilot workbook created'))}catch(e){boxes.forEach(box=>box.textContent=txt('تعذر تصدير بيانات Pilot.','Unable to export Pilot data.'))}}
async function exportAudit(){try{const r=await fetch('/api/admin/audit/export',{headers:{'X-CSRF-Token':CSRF}});if(!r.ok)throw new Error();const b=await r.blob(),a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='SymptoSense_Audit_'+new Date().toISOString().slice(0,10)+'.xlsx';a.click();URL.revokeObjectURL(a.href)}catch(e){alert(txt('تعذر التصدير','Unable to export'))}}

async function loadAI(){
  try{const [pr,hr]=await Promise.all([req('/api/admin/ai-performance?days=30'),req('/api/admin/system-health')]);const p=pr.performance||{},svc=hr.health?.components?.ai_service||{},q=p.data_quality||{},m=p.model||{},mm=m.metrics||{};const items=[[p.total_ai_requests,txt('إجمالي طلبات AI','Total AI Requests')],[p.successful,txt('الطلبات الناجحة','Successful Analyses')],[p.failed,txt('الطلبات الفاشلة','Failed Requests')],[p.avg_response_ms??'—',txt('متوسط الاستجابة ms','Average Response ms')],[p.success_rate+'%',txt('نسبة النجاح','Success Rate')],[p.failure_rate+'%',txt('نسبة الفشل','Failure Rate')],[m.model_version||'—',txt('إصدار النموذج','Model Version')],[mm.accuracy==null?'—':(Number(mm.accuracy)*100).toFixed(1)+'%',txt('دقة الاختبار المخزنة','Stored Test Accuracy')],[mm.precision==null?'—':mm.precision,txt('Precision','Precision')],[mm.recall==null?'—':mm.recall,txt('Recall','Recall')],[mm.f1_score==null?'—':mm.f1_score,txt('F1 Score','F1 Score')],[(svc.status||'unknown')+' · '+(svc.response_ms??'—')+' ms',txt('حالة خدمة AI','AI Service Status')]];document.getElementById('aiStats').innerHTML=items.map(x=>'<div class="stat"><strong>'+esc(x[0]??0)+'</strong><span>'+esc(x[1])+'</span></div>').join('');document.getElementById('aiQualitySummary').innerHTML=q.sample_size?txt('محسوب من ','Calculated from ')+esc(q.sample_size)+' '+txt('تحليلًا مؤهلًا للتحليلات المجمعة. النسبة تقيس اكتمال المعلومات فقط ولا تمثل دقة تشخيص.','analytics-eligible analyses. The score measures input completeness only and is not diagnostic accuracy.'):'<span class="empty">'+txt('لا توجد بيانات جودة كافية بعد.','No data-quality records available yet.')+'</span>';const missNames={main_symptom:txt('العرض الرئيسي','Main symptom'),duration:txt('مدة الأعراض','Duration'),severity:txt('الشدة','Severity'),age:txt('العمر','Age'),gender:txt('الجنس','Gender'),associated_symptoms:txt('الأعراض المصاحبة','Associated symptoms'),relevant_history:txt('التاريخ الصحي ذي الصلة','Relevant medical history')};document.getElementById('aiMissing').innerHTML=(q.most_missing||[]).length?miniBars((q.most_missing||[]).map(x=>({name:(missNames[x.name]||x.name)+' · '+x.percentage+'%',count:x.count}))):'<div class="empty">'+txt('لا توجد حقول ناقصة مسجلة بعد.','No missing-field data recorded yet.')+'</div>';document.getElementById('aiFeatures').innerHTML=miniBars(p.features||[]);document.getElementById('aiErrors').innerHTML=miniBars((p.errors||[]).map(x=>({name:'HTTP '+x.type,count:x.count})));document.getElementById('aiUnknown').innerHTML=miniBars(p.unrecognized||[]);const failures=p.recent_failures||[];document.getElementById('aiFailures').innerHTML=failures.length?'<table><thead><tr><th>'+txt('الوقت','Time')+'</th><th>'+txt('الخدمة','Service')+'</th><th>Status</th></tr></thead><tbody>'+failures.map(x=>'<tr><td>'+esc((x.timestamp||'').slice(0,19))+'</td><td>'+esc(x.service||'—')+'</td><td>'+esc(x.status||'—')+'</td></tr>').join('')+'</tbody></table>':'<div class="empty">'+txt('لا توجد طلبات فاشلة في الفترة المحددة.','No failed requests in the selected period.')+'</div>';aiChart=lineChart(document.getElementById('aiTimeline'),aiChart,p.timeline||[],txt('الطلبات','Requests'));aiResponseChart=lineChart(document.getElementById('aiResponseTimeline'),aiResponseChart,p.response_timeline||[],txt('مللي ثانية','Milliseconds'))}catch(e){console.error(e)}
}

async function loadXAI(){try{const x=(await req('/api/admin/explainable-ai')).explainability||{},m=x.model||{},metrics=m.metrics||{};document.getElementById('xaiStats').innerHTML=[[m.algorithm||'—',txt('الخوارزمية','Algorithm')],[m.model_version||'—',txt('إصدار النموذج','Model Version')],[m.n_features??'—',txt('عدد الميزات','Features')],[metrics.accuracy==null?'—':(Number(metrics.accuracy)*100).toFixed(1)+'%',txt('دقة الاختبار','Test Accuracy')]].map(v=>'<div class="stat"><strong>'+esc(v[0])+'</strong><span>'+esc(v[1])+'</span></div>').join('');document.getElementById('xaiNote').textContent=txt('الطريقة: ','Method: ')+(x.method||'—')+' · '+txt('النموذج مساعد ولا يحدد النتيجة الطبية الأساسية المعروضة للمستخدم.','The model is auxiliary and does not determine the primary medical result shown to users.');document.getElementById('xaiFeatures').innerHTML=(x.features||[]).length?'<table><thead><tr><th>Feature</th><th>Coefficient spread</th><th>'+txt('أعلى فئة','Highest class')+'</th></tr></thead><tbody>'+x.features.map(f=>'<tr><td>'+esc(f.feature)+'</td><td>'+esc(f.coefficient_spread)+'</td><td>'+esc(AR?f.highest_class_name_ar:f.highest_class_name_en)+'</td></tr>').join('')+'</tbody></table>':'<div class="empty">'+txt('غير متاح','Unavailable')+'</div>'}catch(e){console.error(e)}}

async function askData(){
  const q=document.getElementById('askQuestion').value.trim(),box=document.getElementById('askAnswer');if(!q)return;box.innerHTML='<div class="muted">'+txt('جارٍ تحليل السؤال...','Analyzing the question...')+'</div>';
  try{const d=await req('/api/admin/ask-data',{method:'POST',body:JSON.stringify({question:q,lang:LANG})});box.innerHTML='<div class="insight-card"><b>'+txt('الإجابة','Answer')+'</b><p style="margin-top:7px">'+esc(d.answer||'')+'</p></div>';if(window.Chart&&d.data?.length){askChartObj?.destroy();askChartObj=new Chart(document.getElementById('askChart'),{type:d.type==='donut'?'doughnut':'bar',data:{labels:d.data.map(x=>x.label),datasets:[{data:d.data.map(x=>x.value),backgroundColor:['#64B5F6','#90CAF9','#A5D6A7','#FFE082','#B39DDB']}]},options:{maintainAspectRatio:false,plugins:{legend:{display:d.type==='donut'}}}})}}catch(e){box.innerHTML='<div class="insight-card"><b>'+txt('تعذر تنفيذ السؤال','Unable to answer this question')+'</b><p class="muted">'+esc(e.message)+'</p></div>'}
}
async function loadInsights(){
 try{const d=(await req('/api/admin/automatic-insights')).insights||{},box=document.getElementById('autoInsights');if(!d.sufficient_data){box.innerHTML='<div class="card empty">'+txt('لا توجد بيانات كافية لإنشاء ملاحظة موثوقة.','Insufficient data to generate a reliable insight.')+'</div>';return}box.innerHTML=(d.insights||[]).length?(d.insights||[]).map(x=>'<article class="insight-card"><span class="badge verified">'+esc(x.category)+'</span><h3 style="margin-top:8px;color:var(--pd)">'+esc(x.title)+'</h3><p>'+esc(x.previous)+' → '+esc(x.current)+' ('+(x.change_pct>0?'+':'')+esc(x.change_pct)+'%)</p><small class="muted">'+txt('الثقة: ','Confidence: ')+esc(x.confidence)+'</small></article>').join(''):'<div class="card empty">'+txt('لا توجد تغييرات مهمة وفق القواعد الحالية.','No material changes under the current rules.')+'</div>'}catch(e){console.error(e)}
}
async function loadAnomalies(){
 try{const d=(await req('/api/admin/anomalies')).anomalies||{},box=document.getElementById('anomalyList');if(!d.sufficient_data){box.innerHTML='<div class="card empty">'+txt('بيانات غير كافية لاكتشاف أنماط غير معتادة بشكل موثوق.','Insufficient data for reliable anomaly detection.')+'</div>';return}box.innerHTML=(d.findings||[]).length?(d.findings||[]).map(x=>'<article class="insight-card"><span class="badge '+(x.severity==='critical'?'urgent':'review')+'">'+esc(x.severity)+'</span> <span class="badge review">'+esc(x.status||'unusual_activity')+'</span><h3 style="margin-top:8px">'+esc(x.metric.replaceAll('_',' '))+'</h3><p>'+txt('القيمة الحالية: ','Current value: ')+esc(x.current)+' · '+txt('النطاق المتوقع: ','Expected range: ')+esc(x.expected_low)+'–'+esc(x.expected_high)+'</p><small class="muted">'+esc(x.date)+' · '+txt('نشاط غير معتاد لا يعني مشكلة طبية أو وباءً.','Unusual activity does not imply a medical problem or an outbreak.')+'</small></article>').join(''):'<div class="card empty">'+txt('لم يتم اكتشاف نشاط غير معتاد وفق خط الأساس الحالي.','No unusual activity detected against the current baseline.')+'</div>'}catch(e){console.error(e)}
}
async function loadGraph(){try{GRAPH=(await req('/api/admin/knowledge-graph')).graph||{nodes:[],edges:[],stats:{}};const s=GRAPH.stats||{},items=[[s.diseases,txt('الأمراض','Diseases')],[s.symptoms,txt('الأعراض','Symptoms')],[s.relationships,txt('العلاقات','Relationships')],[s.verified_sources,txt('المصادر الموثقة','Verified Sources')],[s.unlinked_symptoms,txt('أعراض غير مرتبطة','Unlinked Symptoms')]];document.getElementById('graphStats').innerHTML=items.map(x=>'<div class="stat"><strong>'+esc(x[0]??0)+'</strong><span>'+esc(x[1])+'</span></div>').join('');renderGraph()}catch(e){console.error(e)}}
function renderGraph(){
 const stage=document.getElementById('graphStage');if(!stage)return;const q=(document.getElementById('graphSearch')?.value||'').toLowerCase(),typ=document.getElementById('graphType')?.value||'';let nodes=(GRAPH.nodes||[]).filter(n=>(!typ||n.type===typ)&&(!q||JSON.stringify(n).toLowerCase().includes(q)));if(graphFocusId){const rel=new Set([graphFocusId]);(GRAPH.edges||[]).forEach(e=>{if(e.from===graphFocusId)rel.add(e.to);if(e.to===graphFocusId)rel.add(e.from)});nodes=nodes.filter(n=>rel.has(n.id))}nodes=nodes.slice(0,120);const ids=new Set(nodes.map(n=>n.id));let edges=(GRAPH.edges||[]).filter(e=>ids.has(e.from)&&ids.has(e.to)).slice(0,300);const W=900,cols=6,gapX=145,gapY=88,pos={};nodes.forEach((n,i)=>{pos[n.id]={x:25+(i%cols)*gapX,y:24+Math.floor(i/cols)*gapY}});let html='';edges.forEach(e=>{const a=pos[e.from],b=pos[e.to];if(!a||!b)return;const dx=b.x-a.x,dy=b.y-a.y,len=Math.sqrt(dx*dx+dy*dy),ang=Math.atan2(dy,dx)*180/Math.PI;html+='<div class="graph-edge" style="left:'+(a.x+55)+'px;top:'+(a.y+20)+'px;width:'+len+'px;transform:rotate('+ang+'deg)"></div>'});nodes.forEach(n=>{const p=pos[n.id],name=AR?(n.name_ar||n.source_name):(n.name_en||n.source_name)||n.name_ar;html+='<button type="button" class="graph-node '+esc(n.type)+'" style="left:'+p.x+'px;top:'+p.y+'px" data-ss-click="graphDetails" data-ss-args="'+ssArgs([n.id])+'"><b>'+esc(name||n.id)+'</b><small style="display:block;color:var(--muted)">'+esc(n.type.replaceAll('_',' '))+'</small></button>'});stage.innerHTML=html;stage.style.width=W+'px';stage.style.height=(Math.ceil(nodes.length/cols)*gapY+100)+'px';stage.style.transform='scale('+graphScale+')';
}
function graphDetails(id){const n=(GRAPH.nodes||[]).find(x=>x.id===id);if(!n)return;const rel=(GRAPH.edges||[]).filter(e=>e.from===id||e.to===id);document.getElementById('graphPanel').innerHTML='<b>'+esc(AR?(n.name_ar||n.source_name):(n.name_en||n.source_name)||n.name_ar||n.id)+'</b><p class="muted" style="margin-top:6px">'+esc((AR?n.description_ar:n.description_en)||n.organization||n.official_url||'')+'</p><p class="muted">'+txt('العلاقات: ','Relationships: ')+rel.length+' · '+txt('آخر تحديث/تحقق: ','Last updated/verified: ')+esc(n.last_updated||n.updated_at||n.last_verified||'—')+'</p><div class="data-actions"><button type="button" class="btn ghost small" data-ss-click="graphFocus" data-ss-args="'+ssArgs([id])+'">'+txt('عرض العلاقات المباشرة','Show related nodes')+'</button><button type="button" class="btn ghost small" data-ss-click="graphFocus" data-ss-args="[null]">'+txt('عرض الكل','Show all')+'</button></div>'}
function graphZoom(d){graphScale=Math.max(.55,Math.min(1.8,graphScale+d));document.getElementById('graphStage').style.transform='scale('+graphScale+')'}function graphFocus(id){graphFocusId=id;renderGraph()}function graphReset(){graphScale=1;graphFocusId=null;const sh=document.getElementById('graphShell');if(sh){sh.scrollLeft=0;sh.scrollTop=0}renderGraph()}
(function(){const sh=document.getElementById('graphShell');if(!sh)return;let down=false,x=0,y=0,sl=0,st=0;sh.addEventListener('pointerdown',e=>{if(e.target.closest('.graph-node'))return;down=true;x=e.clientX;y=e.clientY;sl=sh.scrollLeft;st=sh.scrollTop;sh.classList.add('dragging');sh.setPointerCapture?.(e.pointerId)});sh.addEventListener('pointermove',e=>{if(!down)return;sh.scrollLeft=sl-(e.clientX-x);sh.scrollTop=st-(e.clientY-y)});['pointerup','pointercancel','pointerleave'].forEach(ev=>sh.addEventListener(ev,()=>{down=false;sh.classList.remove('dragging')}))})();

async function loadUsers(){
  try{const rows=(await req('/api/admin/users')).users||[];document.getElementById('table-users').innerHTML=rows.length?'<table><thead><tr><th>User ID</th><th>'+txt('الحالة','Status')+'</th><th>Role</th><th>'+txt('البريد موثق','Email Verified')+'</th><th>'+txt('تاريخ التسجيل','Registration Date')+'</th><th>'+txt('آخر دخول','Last Login')+'</th><th>'+txt('إجراء','Action')+'</th></tr></thead><tbody>'+rows.map(x=>'<tr><td>#'+x.id+'</td><td>'+statusBadge(x.status)+'</td><td><span class="badge '+(x.role==='admin'?'verified':'draft')+'">'+esc(x.role)+'</span></td><td>'+statusBadge(x.email_verified?'verified':'disabled')+'</td><td>'+esc((x.created_at||'—').slice(0,16))+'</td><td>'+esc((x.last_login||'—').slice(0,16))+'</td><td><button type="button" class="btn '+(x.status==='active'?'danger':'ghost')+' small" '+(x.role==='admin'?'disabled':'')+' data-ss-click="toggleUser" data-ss-args="'+ssArgs([x.id,(x.status==='active'?'disabled':'active')])+'">'+(x.status==='active'?txt('تعطيل','Disable'):txt('تفعيل','Activate'))+'</button></td></tr>').join('')+'</tbody></table>':'<div class="empty">'+txt('لا يوجد مستخدمون','No users')+'</div>'}catch(e){alert(e.message)}
}
async function toggleUser(id,status){if(!confirm(txt('تأكيد تغيير حالة الحساب؟','Confirm account status change?')))return;try{await req('/api/admin/users/'+id+'/status',{method:'PUT',body:JSON.stringify({status})});await loadUsers()}catch(e){alert(e.message)}}

async function loadHealth(){
  try{const h=(await req('/api/admin/system-health')).health||{};document.getElementById('healthGrid').innerHTML=Object.entries(h.components||{}).map(([k,v])=>'<div class="health-item"><div style="display:flex;justify-content:space-between;gap:8px"><b>'+esc(k.replaceAll('_',' '))+'</b>'+statusBadge(v.status)+'</div><p class="muted" style="margin-top:7px">'+txt('زمن الاستجابة: ','Response time: ')+(v.response_ms??'—')+' ms<br>'+txt('آخر فحص: ','Last checked: ')+esc(h.checked_at||'—')+(v.error?'<br><span style="color:#991B1B">'+esc(v.error)+'</span>':'')+'</p></div>').join('')||'<div class="empty">'+txt('لا توجد بيانات','No data')+'</div>'}catch(e){alert(e.message)}
}
async function loadAdminProfile(){
 try{
  const [profileResponse,emailResponse,twoFactorResponse]=await Promise.all([req('/api/admin/profile'),req('/api/admin/auth-email-status'),req('/api/admin/2fa/status')]);
  const p=profileResponse.profile||{},m=emailResponse||{},tf=twoFactorResponse.two_factor||{};
  document.getElementById('adminProfile').innerHTML=[[txt('البريد الإلكتروني','Email'),p.email||'—'],[txt('الدور','Role'),p.role||'Administrator'],[txt('آخر دخول','Last Login'),(p.last_login||'—').slice(0,19)],[txt('نوع الحساب','Account Type'),txt('الحساب الإداري الوحيد','Sole Admin Account')]].map(x=>'<div class="health-item"><small class="muted">'+esc(x[0])+'</small><div class="profile-value">'+esc(x[1])+'</div></div>').join('');
  const securityRows=['<div class="security-row"><span>'+txt('انتهاء الجلسة عند الخمول','Idle session timeout')+'</span><b>'+esc(p.session_timeout_minutes)+' min</b></div>','<div class="security-row"><span>'+txt('آخر إنهاء شامل للجلسات','Last global sign-out')+'</span><b>'+esc((p.last_forced_logout||'—').slice(0,19))+'</b></div>','<div class="security-row"><span>'+txt('تغيير الدور ذاتيًا','Self role changes')+'</span><b>'+txt('محظور','Blocked')+'</b></div>'];if(tf.required){securityRows.splice(1,0,'<div class="security-row"><span>2FA</span><b>'+(tf.enabled?txt('مفعّل عبر Authenticator','Enabled via Authenticator'):txt('غير مفعّل','Not enabled'))+'</b></div>','<div class="security-row"><span>'+txt('رموز الاسترداد المتبقية','Recovery codes remaining')+'</span><b>'+esc(tf.recovery_codes_remaining??0)+'</b></div>','<div class="security-row"><span>'+txt('إدارة 2FA','Manage 2FA')+'</span><b><a href="/admin/2fa/manage">'+txt('فتح','Open')+'</a></b></div>')}document.getElementById('adminSecurity').innerHTML=securityRows.join('');
  const ready=!!m.production_recipient_delivery_ready,configured=!!m.configured;
  const diagnostics=[
   [txt('إعداد Resend','Resend configuration'),configured?txt('مكتمل','Configured'):txt('غير مكتمل','Incomplete'),configured],
   [txt('الإرسال لكل المستخدمين','Delivery to all users'),ready?txt('جاهز','Ready'):txt('غير جاهز','Not ready'),ready],
   [txt('دومين المرسل','Sender domain'),m.sender_domain||'—',!!m.sender_address_valid],
   [txt('رابط الموقع داخل الرسائل','Email link base URL'),m.site_url||'—',!!m.site_url],
  ];
  let details='';
  if((m.missing||[]).length)details+='<div class="privacy-banner" style="margin-top:10px">'+txt('متغيرات ناقصة: ','Missing variables: ')+esc(m.missing.join(', '))+'</div>';
  if((m.invalid||[]).length)details+='<div class="privacy-banner" style="margin-top:10px">'+txt('إعدادات غير صالحة: ','Invalid configuration: ')+esc(m.invalid.join(', '))+'</div>';
  if(m.uses_resend_test_domain)details+='<div class="privacy-banner" style="margin-top:10px">'+txt('resend.dev للاختبار فقط. وثّقي دومينًا حقيقيًا للإرسال لكل المستخدمين.','resend.dev is test-only. Verify a real domain to send to all users.')+'</div>';
  if(m.provider==='smtp')details+='<div class="privacy-banner" style="margin-top:10px">'+txt('الإرسال مضبوط عبر Gmail SMTP.','Email delivery is configured through Gmail SMTP.')+'</div>';
  if(m.provider==='brevo')details+='<div class="privacy-banner" style="margin-top:10px">'+txt('الإرسال مضبوط عبر Brevo HTTPS API ومتوافق مع Railway.','Email delivery is configured through the Brevo HTTPS API and is compatible with Railway.')+'</div>';
  document.getElementById('authEmailStatus').innerHTML=diagnostics.map(x=>'<div class="health-item"><small class="muted">'+esc(x[0])+'</small><div class="profile-value">'+statusBadge(x[2]?'verified':'disabled')+' '+esc(x[1])+'</div></div>').join('')+details;
 }catch(e){const el=document.getElementById('authEmailStatus');if(el)el.innerHTML='<div class="empty">'+esc(e.message)+'</div>'}
}
document.getElementById('adminPasswordForm')?.addEventListener('submit',async e=>{e.preventDefault();const out=document.getElementById('adminPasswordStatus'),data=Object.fromEntries(new FormData(e.target).entries());out.textContent=txt('جارٍ تحديث كلمة المرور…','Updating password…');try{const r=await req('/api/admin/profile/password',{method:'POST',body:JSON.stringify(data)});out.textContent=txt('✓ تم تغيير كلمة المرور وإنهاء كل الجلسات. سجّل الدخول من جديد.','✓ Password changed and all Admin sessions were revoked. Sign in again.');e.target.reset();setTimeout(()=>location.href=(r.login_url||'/login?next=/admin'),700)}catch(err){out.textContent=txt('تعذر تغيير كلمة المرور: ','Unable to change password: ')+err.message}});
async function logoutAllAdminSessions(){const out=document.getElementById('logoutAllAdminStatus'),password=document.getElementById('logoutAllAdminPassword')?.value||'';if(!password){out.textContent=txt('أدخل كلمة المرور الحالية أولًا.','Enter the current password first.');return}if(!confirm(txt('سيتم إنهاء جميع جلسات الأدمن على كل الأجهزة. متابعة؟','All Admin sessions on every device will be invalidated. Continue?')))return;out.textContent=txt('جارٍ إنهاء الجلسات…','Signing out all sessions…');try{const r=await req('/api/admin/sessions/logout-all',{method:'POST',body:JSON.stringify({current_password:password})});location.href=r.login_url||'/login?next=/admin'}catch(e){out.textContent=txt('تعذر إنهاء الجلسات: ','Unable to sign out sessions: ')+e.message}}
async function loadAudit(){try{AUDIT=(await req('/api/admin/audit?limit=300')).audit||[];renderAudit()}catch(e){alert(e.message)}}
function renderAudit(){const q=(document.getElementById('auditSearch')?.value||'').toLowerCase(),rows=(AUDIT||[]).filter(x=>!q||JSON.stringify(x).toLowerCase().includes(q));document.getElementById('table-audit').innerHTML=rows.length?'<table><thead><tr><th>Admin Account</th><th>Action</th><th>Entity</th><th>ID</th><th>Result</th><th>Previous Value</th><th>New Value</th><th>Timestamp</th></tr></thead><tbody>'+rows.map(x=>'<tr><td>'+esc(x.admin_account||'System')+'</td><td>'+esc(x.action)+'</td><td>'+esc(x.entity_type)+'</td><td>'+esc(x.entity_id||'—')+'</td><td>'+statusBadge(x.result||'success')+'</td><td class="audit-json" title="'+esc(x.previous_value||'')+'">'+esc(x.previous_value||'—')+'</td><td class="audit-json" title="'+esc(x.new_value||'')+'">'+esc(x.new_value||'—')+'</td><td>'+esc((x.timestamp||'').slice(0,19))+'</td></tr>').join('')+'</tbody></table>':'<div class="empty">'+txt('لا يوجد سجل بعد','No audit entries yet')+'</div>'}

const SERVER_VIEW=new URLSearchParams(location.search).get('view')||'';if(SERVER_VIEW==='adminsettings')show('adminsettings');
const HASH=(location.hash||'').replace('#','');const HM={'knowledge-graph':'graph','anomalies':'anomalies','audit-log':'audit','ask-data':'askdata','insights':'insights','ai-performance':'ai','explainable-ai':'xai','data-export':'dataexport','production-readiness':'production','research-validation':'validation','privacy-analytics':'privacyanalytics','health-analytics':'healthanalytics','medications':'medications','heatmap':'heatmap','settings':'adminsettings','dropoff':'dropoff','live-activity':'live','content-gaps':'contentgaps'};if(HASH&&HM[HASH])show(HM[HASH]);else{loadUsage();loadKB();}
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
    return jsonify({"stats": db.get_usage_stats(days=7), "feedback": db.feedback_counts(), "fb_comments": db.feedback_comments(100, public_only=False)})


def run_dashboard():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)


if __name__ == "__main__":
    run_dashboard()
