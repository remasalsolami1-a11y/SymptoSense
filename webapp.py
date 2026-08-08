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
import random

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
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap');
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Cairo', 'Segoe UI', Tahoma, sans-serif; background: #F6F9FC; color: #1e293b; }
a { text-decoration: none; color: inherit; }
.nav { background: #FFFFFF; color: #0B2E6B; display: flex; align-items: center; justify-content: space-between; padding: 15px 26px; position: sticky; top: 0; z-index: 50; box-shadow: 0 2px 14px rgba(11,46,107,.07); flex-wrap: wrap; gap: 10px; border-bottom: 1px solid #D7E7FA; }
.nav .logo { font-size: 22px; font-weight: 800; letter-spacing: .3px; color: #0B2E6B; display: flex; align-items: center; gap: 6px; }
.nav .logo span { color: #1677E8; }
.nav .links { display: flex; gap: 2px; flex-wrap: wrap; }
.nav .links a { color: #17356D; padding: 8px 13px; border-radius: 10px; font-size: 15px; font-weight: 600; }
.nav .links a:hover { background: #E8F3FF; color: #1677E8; }
.container { max-width: 1080px; margin: 0 auto; padding: 26px 18px; }
.hero { background: linear-gradient(135deg, #1677E8 0%, #3b8aee 55%, #4d97ef 100%); color: #fff; border-radius: 20px; padding: 48px 36px; text-align: center; margin-bottom: 30px; }
.hero h1 { font-size: 40px; margin-bottom: 12px; }
.hero p { font-size: 17px; opacity: .95; max-width: 640px; margin: 0 auto 24px; line-height: 1.8; }
.btn { display: inline-block; background: #fff; color: #1677E8; font-weight: 700; padding: 13px 30px; border-radius: 12px; margin: 6px; font-size: 16px; border: none; cursor: pointer; }
.btn.ghost { background: rgba(255,255,255,.15); color: #fff; border: 1px solid rgba(255,255,255,.5); }
.btn:hover { transform: translateY(-1px); }
.btn.small { padding: 7px 14px; font-size: 13px; border-radius: 9px; margin: 3px; }
.btn.ghost.small { background: #F0F7FF; color: #1677E8; border: 1px solid #1677E8; }
.card { background: #fff; border-radius: 16px; padding: 22px; box-shadow: 0 1px 6px rgba(15,23,42,.06); border: 1px solid #e2e8f0; margin-bottom: 20px; }
.card h2 { color: #1677E8; margin-bottom: 12px; font-size: 20px; }
.features { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin-bottom: 24px; }
.feature { background: #fff; border: 1px solid #e2e8f0; border-radius: 14px; padding: 20px; }
.feature .ic { font-size: 30px; }
.feature h3 { font-size: 16px; margin: 10px 0 6px; color: #1677E8; }
.feature p { font-size: 14px; color: #475569; line-height: 1.7; }
a.feature.serv { display: block; text-decoration: none; transition: transform .12s ease, box-shadow .12s ease, border-color .12s ease; }
a.feature.serv:hover { transform: translateY(-3px); box-shadow: 0 8px 20px rgba(22,119,232,.14); border-color: #4d97ef; }
.steps { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
.step { background: #fff; border: 1px solid #e2e8f0; border-radius: 14px; padding: 20px; text-align: center; }
.step .n { width: 34px; height: 34px; border-radius: 50%; background: #1677E8; color: #fff; display: inline-flex; align-items: center; justify-content: center; font-weight: 800; }
.step h3 { margin: 10px 0 6px; font-size: 15px; }
.step p { font-size: 13px; color: #64748b; }
.warn { background: #fff7ed; border: 1px solid #fdba74; color: #7c2d12; border-radius: 12px; padding: 14px 18px; font-size: 14px; margin-bottom: 22px; }
.footer { text-align: center; padding: 30px 22px; color: #DCEEFF; font-size: 13px; background: #0B2E6B; margin-top: 30px; border-radius: 26px 26px 0 0; }
.footer a { color: #6fb2ff; }
.footer .f-links { display: flex; gap: 18px; justify-content: center; flex-wrap: wrap; margin: 10px 0 8px; font-size: 13px; }
.footer .f-links a { color: #DCEEFF; }
.footer .f-links a:hover { color: #FFFFFF; text-decoration: underline; }
.chat-wrap { max-width: 900px; margin: 0 auto; background: #fff; border-radius: 22px; box-shadow: 0 4px 20px rgba(15,23,42,.08); border: 1px solid #e2e8f0; overflow: hidden; display: flex; flex-direction: column; height: 78vh; }
.chat-head { background: #1677E8; color: #fff; padding: 14px 18px; display: flex; align-items: center; gap: 10px; }
.chat-head .avatar { width: 40px; height: 40px; border-radius: 50%; background: #BFDDFF; color: #1677E8; display: flex; align-items: center; justify-content: center; font-size: 20px; }
.chat-head h3 { font-size: 16px; }
.chat-head p { font-size: 12px; opacity: .85; }
.chat-head .spk-btn { margin-left: auto; background: rgba(255,255,255,.15); border: none; border-radius: 10px; padding: 8px 10px; font-size: 13px; cursor: pointer; color: #fff; white-space: nowrap; }
.chat-body { flex: 1; overflow-y: auto; padding: 18px; background: #F0F7FF; }
.bubble { max-width: 85%; margin-bottom: 10px; padding: 11px 15px; border-radius: 14px; font-size: 15px; line-height: 1.8; white-space: pre-wrap; }
.bubble.bot { background: #fff; border: 1px solid #e2e8f0; border-bottom-right-radius: 4px; }
.bubble.user { background: #1677E8; color: #fff; margin-left: auto; border-bottom-left-radius: 4px; }
.bubble.result { background: #fff; border: 1px solid #BFDDFF; max-width: 100%; }
.chat-options { padding: 14px; background: #fff; border-top: 1px solid #e2e8f0; display: flex; flex-wrap: wrap; gap: 8px; }
.opt { background: #FFFFFF; border: 1.5px solid #BFDDFF; color: #0B2E6B; padding: 10px 18px; border-radius: 24px; font-size: 14.5px; font-weight: 600; cursor: pointer; }
.vidbtn { display:inline-block; margin-top:12px; background:#4d97ef; color:#fff; border:none; padding:10px 18px; border-radius:24px; font-size:14px; cursor:pointer; }
.vidbtn:hover { background:#1677E8; }
.vidwrap iframe { display:block; }
.opt.sel { background: #1677E8; color: #fff; }
.opt.danger { border-color: #dc2626; color: #dc2626; background: #fef2f2; }
.opt:hover { opacity: .9; }
.chat-input { display: flex; gap: 8px; padding: 12px 14px; background: #fff; border-top: 1px solid #e2e8f0; }
.chat-input input { flex: 1; border: 1px solid #cbd5e1; border-radius: 12px; padding: 12px 14px; font-size: 15px; font-family: inherit; }
.chat-input button { background: #1677E8; color: #fff; border: none; border-radius: 12px; padding: 12px 20px; font-size: 15px; cursor: pointer; }
.urg-low { border-right: 6px solid #16a34a; }
.urg-medium { border-right: 6px solid #d97706; }
.urg-high { border-right: 6px solid #dc2626; }
.sec-title { font-weight: 800; color: #1677E8; margin: 14px 0 6px; font-size: 15px; }
.res-sec { margin: 10px 0; }
.rec-item { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 12px; margin: 8px 0; }
.rec-item .src { color: #3b8aee; font-size: 12px; }
.drop { border: 2px dashed #1677E8; border-radius: 16px; padding: 40px; text-align: center; color: #1677E8; cursor: pointer; background: #F0F7FF; margin-bottom: 16px; }
.drop.on { background: #E8F3FF; }
.muted { color: #64748b; font-size: 13px; }
.urg-lbl { display: block; font-size: 13px; font-weight: 700; opacity: .85; }
.urg-val { display: block; font-size: 21px; font-weight: 800; margin-top: 2px; }
.rec-card { background: #FFFFFF; border: 1px solid #BFDDFF; border-radius: 14px; padding: 12px 14px; margin: 10px 0; box-shadow: 0 2px 8px rgba(22,119,232,.06); }
.rec-head { display: flex; align-items: center; gap: 8px; color: #0B2E6B; font-size: 14.5px; }
.rec-num { flex: none; width: 22px; height: 22px; border-radius: 50%; background: #1677E8; color: #fff; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 800; }
.rec-body { color: #475569; font-size: 13.5px; line-height: 1.8; margin-top: 6px; }
.rec-card .src { color: #3b8aee; font-size: 12px; margin-top: 6px; }
.ml-row { display: flex; justify-content: space-between; font-size: 13.5px; margin-top: 8px; }
.ml-note { color: #64748b; font-size: 12px; margin-top: 8px; line-height: 1.7; }
.sel-sum { color: #64748b; font-size: 13px; font-weight: 600; margin-top: 6px; }
.res-sec.bullets { white-space: pre-line; line-height: 1.9; color: #475569; }
.card label { display: block; font-size: 13px; font-weight: 700; color: #1677E8; margin-bottom: 4px; }
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
table.tbl th { background: #1677E8; color: #fff; }
.pill { display: inline-block; padding: 3px 12px; border-radius: 20px; font-size: 13px; font-weight: 700; }
.pill.low { background: #dcfce7; color: #166534; }
.pill.medium { background: #fef3c7; color: #92400e; }
.pill.high { background: #fee2e2; color: #991b1b; }
.badge { background: #1677E8; color: #fff; padding: 4px 12px; border-radius: 20px; font-size: 12px; }
.bar-bg { background: #e2e8f0; border-radius: 8px; height: 10px; width: 100%; margin: 4px 0; }
.bar-fill { background: #3b8aee; height: 10px; border-radius: 8px; }
.spin { display: inline-block; width: 16px; height: 16px; border: 2px solid #BFDDFF; border-top-color: transparent; border-radius: 50%; animation: sp 1s linear infinite; vertical-align: middle; }
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
.welcome-card h1 { font-size: 30px; color: #1677E8; margin: 14px 0 8px; }
.welcome-card p { color: #475569; font-size: 15px; line-height: 1.8; margin-bottom: 26px; }
.lang-row { display: flex; gap: 14px; justify-content: center; flex-wrap: wrap; }
.lang-btn { flex: 1; min-width: 200px; background: #F0F7FF; border: 2px solid #1677E8; border-radius: 14px; padding: 22px 14px; cursor: pointer; transition: transform .12s ease, box-shadow .12s ease, background .12s ease; }
.lang-btn:hover { transform: translateY(-3px); box-shadow: 0 8px 20px rgba(22,119,232,.18); background: #E8F3FF; }
.lang-btn .lc { font-size: 34px; display: block; margin-bottom: 8px; }
.lang-btn .lt { font-size: 20px; font-weight: 800; color: #1677E8; display: block; }
.lang-btn .ld { font-size: 13px; color: #475569; display: block; margin-top: 4px; }
.multi-greet { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; margin: 0 0 22px; }
.greet-line { display: inline-flex; align-items: center; gap: 7px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 999px; padding: 6px 14px; font-size: 13.5px; color: #334155; }
.greet-line .gflag { font-size: 16px; }
.welcome-full { position: fixed; inset: 0; z-index: 60; background: linear-gradient(180deg, #F7FAFF 0%, #E8F3FF 100%); overflow: hidden; transition: opacity .8s ease; }
.welcome-full.fade-out { opacity: 0; }
.w-cloud { position: absolute; inset: 0; }
.gword { position: absolute; display: inline-block; font-family: 'Amiri', 'Cairo', serif; font-weight: 700; color: #1677E8; white-space: nowrap; text-shadow: 0 3px 18px rgba(22,119,232,.20); animation: floaty var(--dur,10s) ease-in-out var(--delay,0s) infinite; }
@keyframes floaty { 0%,100% { transform: rotate(var(--rot,0deg)) translateY(0); } 50% { transform: rotate(var(--rot,0deg)) translateY(-14px); } }
.lang-area { position: absolute; bottom: 30px; left: 0; right: 0; display: flex; flex-direction: column; align-items: center; gap: 12px; z-index: 5; }
.lang-opts { display: flex; gap: 10px; opacity: 0; transform: translateY(14px); pointer-events: none; transition: opacity .45s ease, transform .45s ease; }
.lang-opts.show { opacity: 1; transform: translateY(0); pointer-events: auto; }
.lang-btn { font-family: 'Cairo', 'Segoe UI', sans-serif; font-size: 15px; font-weight: 700; color: #1677E8; background: rgba(255,255,255,.9); border: 2px solid #1677E8; border-radius: 999px; padding: 10px 30px; cursor: pointer; box-shadow: 0 4px 16px rgba(22,119,232,.18); transition: transform .15s ease, background .15s ease; }
.lang-btn:hover { transform: translateY(-2px); background: #E8F3FF; }
.exit-curtain { position: fixed; z-index: 999; left: 50%; top: 50%; width: 150vmax; height: 150vmax; margin-left: -75vmax; margin-top: -75vmax; border-radius: 50%; background: radial-gradient(circle at center, #4d97ef, #1677E8 60%, #0B2E6B); transform: scale(0); opacity: 0; pointer-events: none; transition: transform .9s cubic-bezier(.65,0,.35,1), opacity .55s ease; }
.exit-curtain.open { transform: scale(1); opacity: 1; }
.welcome-pick { display: none; position: fixed; z-index: 61; top: 50%; left: 50%; transform: translate(-50%, -46%); max-width: 580px; width: 92%; background: #fff; border: 1px solid #e2e8f0; border-radius: 22px; box-shadow: 0 14px 40px rgba(15,23,42,.14); padding: 30px 26px; text-align: center; }
.welcome-pick.show { display: block; animation: pickIn .9s ease forwards; }
@keyframes pickIn { from { opacity: 0; transform: translate(-50%, -46%) scale(.94); } to { opacity: 1; transform: translate(-50%, -46%) scale(1); } }
.welcome-pick .logo-big { font-size: 52px; }
.welcome-pick h1 { font-size: 26px; color: #1677E8; margin: 10px 0 4px; }
.pick-btn { display: inline-block; margin: 4px; padding: 10px 26px; border-radius: 999px; border: 2px solid #1677E8; background: #1677E8; color: #fff; font-family: inherit; font-size: 15px; font-weight: 700; cursor: pointer; transition: transform .12s ease, background .12s ease; }
.pick-btn:hover { transform: translateY(-2px); background: #0B2E6B; }
body.page-exit { transition: opacity .45s ease, transform .45s ease; opacity: 0; transform: scale(1.02); }
.nav .lang-sw { display: flex; align-items: center; gap: 2px; background: #E8F3FF; border-radius: 999px; padding: 3px; }
.nav .lang-sw a { font-size: 13px; font-weight: 700; padding: 6px 14px; border-radius: 999px; color: #1677E8; }
.nav .lang-sw a:hover { background: #DCEEFF; }
.nav .lang-sw a.on { background: #1677E8; color: #FFFFFF; }
.dd { position: relative; }
.dd-btn { background: #E8F3FF; border: none; color: #1677E8; font-weight: 700; font-family: inherit; font-size: 14.5px; padding: 9px 15px; border-radius: 10px; cursor: pointer; display: inline-flex; align-items: center; gap: 5px; }
.dd-btn:hover { background: #DCEEFF; }
.dd-menu { display: none; position: absolute; top: calc(100% + 8px); right: 0; min-width: 215px; background: #FFFFFF; border: 1px solid #D7E7FA; border-radius: 14px; box-shadow: 0 16px 36px rgba(11,46,107,.16); padding: 8px; z-index: 90; }
.dd-menu.open { display: block; }
.dd-menu a { display: block; padding: 10px 13px; border-radius: 10px; color: #17356D; font-size: 14px; font-weight: 600; }
.dd-menu a:hover { background: #E8F3FF; color: #1677E8; }
html[dir="ltr"] .dd-menu { right: auto; left: 0; }
.nav .links a.on { background: #E8F3FF; color: #1677E8; }
.cbc { font-size: 15px; font-weight: 700; color: #0B2E6B; margin-bottom: 6px; }
.field-box { display: flex; align-items: center; gap: 12px; background: #F7FAFF; border: 1px solid #D7E7FA; border-radius: 14px; padding: 14px; }
.field-box .fb-ic { font-size: 24px; width: 46px; height: 46px; min-width: 46px; border-radius: 12px; background: #E8F3FF; display: flex; align-items: center; justify-content: center; }
.field-box .lbl { margin: 0 0 4px; color: #0B2E6B; }
.field-box input, .field-box select { background: #FFFFFF; }
.hint-note { text-align: center; color: #64748b; font-size: 12.5px; margin: 12px 0 16px; }
.drop { border: 2px dashed #4d97ef; border-radius: 18px; padding: 34px 20px; text-align: center; color: #0B2E6B; cursor: pointer; background: #F7FAFF; margin-bottom: 0; }
.drop .d-icon { font-size: 40px; margin-bottom: 8px; }
.drop .d-text { font-size: 15px; font-weight: 700; color: #0B2E6B; }
.drop .d-or { color: #64748b; font-size: 13px; margin: 6px 0; }
.drop .d-btn { display: inline-block; background: #1677E8; color: #FFFFFF; font-weight: 700; padding: 9px 22px; border-radius: 999px; font-size: 14px; }
.drop .d-note { color: #64748b; font-size: 12px; margin-top: 10px; }
.drop.on { background: #E8F3FF; border-color: #1677E8; }
.drop.selected { cursor: default; background: #EFF7FF; border-style: solid; border-color: #16a34a; }
.drop.selected .d-file { font-weight: 700; color: #0B2E6B; font-size: 15px; word-break: break-all; }
.d-del { margin-top: 8px; background: #FFFFFF; color: #dc2626; border: 1.5px solid #fca5a5; font-weight: 700; padding: 8px 20px; border-radius: 999px; font-size: 13.5px; cursor: pointer; font-family: inherit; }
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
.bl-table .bl-row:hover td { background: #F0F7FF; }
.bl-detail td { background: #F7FAFF; }
.bl-det-inner { font-size: 14px; line-height: 1.8; color: #334155; }
.bl-det-inner p { margin: 4px 0; }
.bl-det-inner b { color: #1677E8; }
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
.drug-card { background: #F7FAFF; border: 1px solid #D7E7FA; border-radius: 14px; padding: 18px; }
.drug-name { font-size: 19px; font-weight: 800; color: #0B2E6B; margin-bottom: 12px; }
.drug-sec { margin-bottom: 14px; }
.drug-sec-t { font-weight: 800; color: #1677E8; font-size: 14.5px; margin-bottom: 4px; }
.drug-sec-t.wr { color: #b45309; }
.drug-sec-t.wt { color: #dc2626; }
.drug-sec p { font-size: 14px; color: #334155; line-height: 1.8; }
.drug-note { font-size: 12.5px; color: #7A5B00; background: #FFF8E7; border: 1px solid #F5D78E; border-radius: 10px; padding: 10px 13px; }
.tip-card { background: linear-gradient(180deg, #F0FDFA 0%, #FFFFFF 70%); border: 1.5px solid #99F6E4; border-radius: 18px; padding: 22px 20px; }
.tip-top { display: flex; align-items: center; gap: 14px; margin-bottom: 12px; }
.tip-icon { font-size: 42px; width: 64px; height: 64px; min-width: 64px; border-radius: 16px; background: #CCFBF1; display: flex; align-items: center; justify-content: center; }
.tip-cat { display: inline-block; font-size: 12px; font-weight: 800; color: #0F766E; background: #CCFBF1; border-radius: 999px; padding: 3px 12px; margin-bottom: 4px; }
.tip-top h3 { font-size: 19px; color: #16324F; margin: 0; }
.tip-text { font-size: 14.5px; color: #334155; line-height: 1.9; margin-bottom: 12px; }
.tip-tip { font-size: 13.5px; color: #166534; background: #dcfce7; border: 1px solid #bbf7d0; border-radius: 12px; padding: 10px 14px; line-height: 1.8; }
.em-alert { background: #FEF3C7; border: 1.5px solid #F59E0B; color: #92400e; border-radius: 14px; padding: 13px 16px; font-size: 14px; margin: 14px 0 20px; line-height: 1.8; }
.em-grid3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 14px; }
@media (max-width: 760px) { .em-grid3 { grid-template-columns: 1fr; } }
.em-card { background: #FFFFFF; border: 1.5px solid #CCFBF1; border-radius: 18px; padding: 22px 18px; text-align: center; }
.em-card .em-ic { font-size: 34px; }
.em-card h3 { font-size: 16px; color: #16324F; margin: 10px 0 4px; }
.em-desc { font-size: 13px; color: #64748b; min-height: 42px; line-height: 1.7; }
.em-num { font-size: 34px; font-weight: 800; letter-spacing: 1px; margin: 10px 0; }
.em-num.red { color: #dc2626; }
.em-num.blue { color: #0F766E; }
.em-call { display: inline-block; background: #dc2626; color: #FFFFFF; font-weight: 700; padding: 10px 24px; border-radius: 999px; font-size: 14.5px; }
.em-call:hover { opacity: .9; }
.em-call.blue { background: #0F766E; }
.em-call.big { font-size: 17px; padding: 14px 40px; }
.em-mini { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 4px; }
@media (max-width: 640px) { .em-mini { grid-template-columns: 1fr; } }
.em-mini-card { display: flex; align-items: center; gap: 10px; background: #F0FDFA; border: 1px solid #CCFBF1; border-radius: 14px; padding: 14px 16px; flex-wrap: wrap; }
.em-mini-card .em-mini-num { margin-inline-start: auto; font-size: 22px; font-weight: 800; color: #0F766E; }
.em-danger { border: 1.5px solid #FECACA; }
.em-danger-h { color: #b91c1c !important; }
.em-signs { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; }
.em-sign { background: #fef2f2; border: 1px solid #fecaca; color: #7f1d1d; border-radius: 12px; padding: 12px 14px; font-size: 13.5px; font-weight: 700; text-align: center; }
.em-24h { display: inline-block; background: #CCFBF1; color: #0F766E; font-weight: 700; font-size: 13px; padding: 7px 16px; border-radius: 999px; }
.em-safety { background: #FEF3C7; border-color: #F59E0B; color: #92400e; }
.hh { display: flex; align-items: center; gap: 30px; background: linear-gradient(120deg, #E5F2FF 0%, #FFFFFF 78%); border: 1px solid #D7E7FA; border-radius: 34px; padding: 48px 44px; box-shadow: 0 18px 50px rgba(23,105,224,.10); margin-bottom: 34px; }
.hh-badge { display: inline-flex; align-items: center; gap: 8px; background: #DCEEFF; color: #0B2E6B; font-size: 13px; font-weight: 700; border-radius: 999px; padding: 8px 16px; margin-bottom: 18px; }
.hh-l { flex: 1.2; }
.hh-l h1 { font-size: 42px; line-height: 1.15; color: #0B2E6B; margin: 0 0 8px; }
.hh-l h1 .hl { color: #1677E8; }
.hh-sub { font-size: 19px; font-weight: 700; color: #17356D; margin-bottom: 10px; }
.hh-desc { font-size: 15.5px; color: #475569; line-height: 1.8; margin-bottom: 26px; max-width: 560px; }
.hh-btns { display: flex; gap: 12px; flex-wrap: wrap; }
.btn.pri { background: #1677E8; color: #FFFFFF; box-shadow: 0 10px 24px rgba(22,119,232,.30); }
.btn.pri:hover { background: #1255c0; transform: translateY(-2px); }
.btn.sec { background: #FFFFFF; color: #0B2E6B; border: 1.5px solid #C4DCF8; }
.btn.sec:hover { border-color: #1677E8; color: #1677E8; transform: translateY(-2px); }
.hh-r { flex: 1; display: flex; align-items: center; justify-content: center; position: relative; min-height: 420px; }
.hh-globe { position: absolute; width: 360px; height: 360px; border-radius: 50%; background: radial-gradient(circle, rgba(23,105,224,.14) 0%, rgba(23,105,224,.04) 55%, transparent 70%); }
.hh-globe::before, .hh-globe::after { content: ''; position: absolute; border-radius: 50%; border: 1.5px solid rgba(23,105,224,.18); inset: 12%; }
.hh-globe::after { inset: 26%; }
.hh-ic { position: absolute; font-size: 34px; filter: drop-shadow(0 6px 14px rgba(23,105,224,.25)); animation: floatic 5s ease-in-out infinite; }
.hh-ic.i1 { top: 6%; left: 6%; animation-delay: 0s; }
.hh-ic.i2 { top: 2%; right: 12%; animation-delay: 1.1s; }
.hh-ic.i3 { bottom: 12%; left: 12%; animation-delay: 2s; }
.hh-ic.i4 { bottom: 4%; right: 6%; animation-delay: .6s; }
.hh-ic.i5 { top: 36%; left: 0; animation-delay: 1.6s; }
.hh-ic.i6 { top: 34%; right: 0; animation-delay: .3s; }
.phone { width: 200px; height: 396px; background: #0B2E6B; border-radius: 40px; padding: 12px; box-shadow: 0 34px 70px rgba(11,46,107,.35), inset 0 0 0 2px rgba(255,255,255,.12); position: relative; z-index: 2; }
.phone-screen { width: 100%; height: 100%; border-radius: 30px; background: linear-gradient(180deg, #DCEEFF 0%, #FFFFFF 100%); display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: 20px; }
.phone-heart { width: 74px; height: 74px; border-radius: 50%; background: #FFFFFF; box-shadow: 0 10px 26px rgba(23,105,224,.30); display: flex; align-items: center; justify-content: center; font-size: 36px; margin-bottom: 18px; }
.phone-screen p { color: #0B2E6B; font-size: 15px; font-weight: 600; line-height: 1.7; }
.sec-head { text-align: center; color: #0B2E6B; font-size: 30px; margin: 40px 0 8px; }
.sec-sub { text-align: center; color: #64748b; font-size: 15px; margin-bottom: 26px; }
.feature { transition: transform .14s ease, box-shadow .14s ease, border-color .14s ease; }
.feature .ic { font-size: 38px; width: 64px; height: 64px; display: flex; align-items: center; justify-content: center; background: #E8F3FF; border-radius: 18px; margin-bottom: 12px; }
.feature h3 { font-size: 16.5px; margin: 10px 0 6px; color: #1677E8; }
.feature p { font-size: 14px; color: #475569; line-height: 1.7; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
a.feature.serv:hover { transform: translateY(-4px); box-shadow: 0 14px 30px rgba(22,119,232,.14); border-color: #1677E8; }
#more-services { display: none; }
.more-btn { display: block; margin: 0 auto 24px; background: #FFFFFF; color: #1677E8; border: 1.5px solid #1677E8; font-weight: 700; padding: 12px 30px; border-radius: 999px; font-size: 15px; cursor: pointer; font-family: inherit; }
.more-btn:hover { background: #E8F3FF; }
.how-wrap { display: flex; align-items: center; justify-content: center; gap: 0; flex-wrap: wrap; margin-bottom: 30px; }
.how-step { background: #fff; border: 1px solid #D7E7FA; border-radius: 18px; padding: 26px 22px; text-align: center; flex: 1; min-width: 210px; max-width: 260px; box-shadow: 0 4px 16px rgba(23,105,224,.06); }
.how-step .n { width: 44px; height: 44px; border-radius: 50%; background: linear-gradient(135deg, #1677E8, #1255c0); color: #fff; display: inline-flex; align-items: center; justify-content: center; font-weight: 800; font-size: 17px; margin-bottom: 12px; }
.how-step h3 { font-size: 16.5px; color: #0B2E6B; margin-bottom: 6px; }
.how-step p { font-size: 13.5px; color: #64748b; line-height: 1.7; }
.how-arrow { font-size: 26px; color: #1677E8; padding: 0 10px; font-weight: 800; }
html[dir="ltr"] .how-arrow.ar { display: none; }
html[dir="rtl"] .how-arrow.en { display: none; }
.warn2 { background: #FFF8E7; border: 1px solid #F5D78E; color: #7A5B00; border-radius: 16px; padding: 16px 20px; font-size: 14.5px; line-height: 1.9; margin-bottom: 22px; display: flex; gap: 10px; align-items: flex-start; }
.warn2 .w-ic { font-size: 22px; }
.ab-sub { color: #0F766E; font-size: 17px; margin: 0 0 10px; }
.src-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.src-chips span { background: #CCFBF1; color: #0F766E; font-weight: 800; font-size: 13px; padding: 6px 14px; border-radius: 999px; }
.bubble.q { background: #E8F3FF; border: 1px solid #BFDDFF; color: #0B2E6B; font-weight: 700; font-size: 16px; border-radius: 14px 14px 14px 4px; padding: 13px 16px; }
.bubble.q.start { max-width: 100%; background: linear-gradient(160deg, #E5F2FF 0%, #FFFFFF 90%); border: 1.5px solid #BFDDFF; }
.chat-start { text-align: center; padding: 12px 10px 8px; }
.chat-start .cs-logo { font-size: 46px; margin-bottom: 8px; }
.chat-start .cs-title { font-size: 21px; font-weight: 800; color: #0B2E6B; margin-bottom: 4px; }
.chat-start .cs-sub { font-size: 15px; font-weight: 700; color: #1677E8; margin-bottom: 10px; }
.chat-start .cs-desc { font-size: 13.5px; color: #475569; line-height: 1.9; }
.start-btn { display: block; width: 100%; margin-top: 10px; background: linear-gradient(135deg, #1677E8, #1255c0); color: #FFFFFF; border: none; border-radius: 999px; padding: 14px 20px; font-size: 16px; font-weight: 800; cursor: pointer; font-family: inherit; box-shadow: 0 10px 24px rgba(22,119,232,.30); }
.start-btn:hover { transform: translateY(-1px); box-shadow: 0 14px 30px rgba(22,119,232,.38); }
.res-card { background: linear-gradient(180deg, #F4F9FF 0%, #FFFFFF 70%); border: 1.5px solid #BFDDFF; border-radius: 20px; padding: 22px 20px; }
.res-title { text-align: center; font-size: 20px; font-weight: 800; color: #0B2E6B; margin-bottom: 12px; }
.res-urg { text-align: center; margin: 6px 0 10px; }
.pill2 { display: inline-block; font-size: 20px; font-weight: 800; padding: 10px 26px; border-radius: 999px; }
.pill2.low { background: #dcfce7; color: #166534; }
.pill2.med { background: #fef3c7; color: #92400e; }
.pill2.hi { background: #fee2e2; color: #b91c1c; }
.res-disc { text-align: center; font-size: 12.5px; color: #7A5B00; margin-bottom: 12px; padding: 8px 10px; background: #FFF8E7; border: 1px solid #F5D78E; border-radius: 10px; line-height: 1.7; }
.res-note { font-style: italic; color: #475569; line-height: 1.9; margin-bottom: 10px; font-size: 14px; }
.rc-title { font-weight: 800; color: #0B2E6B; margin: 14px 0 6px; font-size: 15.5px; }
@media (max-width: 860px) {
  .hh { flex-direction: column; padding: 30px 22px; }
  .hh-l h1 { font-size: 30px; }
  .hh-r { min-height: 300px; }
  .nav { padding: 12px 16px; }
}
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
<meta name="theme-color" content="#1677E8">
<style>__CSS__</style>
</head>
<body>
<script>
function setLang(l) {
  document.cookie = 'lang=' + l + ';path=/;max-age=31536000;SameSite=Lax';
  try { localStorage.setItem('ss_lang', l); } catch(e) {}
  location.href = (l === 'ar') ? '/home' : '/home';
}
function toggleDD(ev) {
  ev.stopPropagation();
  const m = document.querySelector('.dd-menu');
  if (m) m.classList.toggle('open');
}
document.addEventListener('click', function(ev) {
  const m = document.querySelector('.dd-menu');
  if (m && !ev.target.closest('.dd')) m.classList.remove('open');
});
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
        "nav_how": "كيف يعمل", "nav_features": "المميزات", "nav_contact": "تواصل معنا",
        "nav_profile": "ملفي", "nav_history": "سجلّي",
        "nav_explore": "الاستكشاف", "nav_q": "الأسئلة الطبية", "nav_geo": "أقرب مستشفى",
        "nav_aware": "التوعية", "nav_blog": "المدونة",
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
        "home_sub": "مساعدك الذكي لفهم الأعراض الصحية",
        "home_desc": "أدخل أعراضك في خطوات بسيطة واحصل على تقييم أولي ذكي يساعدك على فهم حالتك ومعرفة الخطوة المناسبة التالية — مع الحفاظ على خصوصيتك.",
        "home_btn1": "ابدأ التقييم الآن",
        "home_btn2": "كيف يعمل SymptoSense؟",
        "home_ph1": "افهم أعراضك",
        "home_ph2": "اعتني بصحتك",
        "home_services": "اختر ما تحتاج",
        "home_services_sub": "أدوات ذكية تساعدك على العناية بصحتك",
        "home_more": "عرض المزيد",
        "home_less": "عرض أقل",
        "home_how": "كيف يعمل؟",
        "home_step1_t": "أدخل أعراضك",
        "home_step1_p": "العمر، الجنس، الأعراض، المدة، والشدة بخطوات بسيطة.",
        "home_step2_t": "أجب عن أسئلة المتابعة",
        "home_step2_p": "أمراض سابقة، أدوية حالية، وأي معلومات إضافية مهمة.",
        "home_step3_t": "احصل على تقييم أولي",
        "home_step3_p": "مستوى الخطورة، الاحتمالات المحتملة، والتوصيات المناسبة.",
        "home_warn2": "<b>SymptoSense لا يقدّم تشخيصًا طبيًا نهائيًا</b> ولا يُغني عن استشارة الطبيب. في حال وجود أعراض خطرة (ألم صدر حاد، صعوبة تنفس، نزيف حاد، فقدان وعي) اتصل بالإسعاف فورًا <b>997</b>.",
        "ab_t1": "ما هو SymptoSense؟",
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
    },
    "en": {
        "nav_home": "Home", "nav_chat": "Symptom Check", "nav_blood": "Blood Tests",
        "nav_meds": "Medications", "nav_emergency": "Emergency", "nav_checkin": "My Tracking",
        "nav_firstaid": "First Aid", "nav_tips": "Tips", "nav_relax": "Relax",
        "nav_admin": "Dashboard", "nav_about": "About",
        "nav_how": "How it works", "nav_features": "Features", "nav_contact": "Contact",
        "nav_profile": "My profile", "nav_history": "My history",
        "nav_explore": "Explore", "nav_q": "Medical questions", "nav_geo": "Nearest hospital",
        "nav_aware": "Awareness", "nav_blog": "Blog",
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
        "home_sub": "Your smart assistant to understand health symptoms",
        "home_desc": "Enter your symptoms in a few simple steps and get an initial smart assessment that helps you understand your condition and know the right next step — while keeping your privacy.",
        "home_btn1": "Start assessment now",
        "home_btn2": "How does SymptoSense work?",
        "home_ph1": "Understand your symptoms",
        "home_ph2": "Take care of your health",
        "home_services": "What do you need?",
        "home_services_sub": "Smart tools to help you take care of your health",
        "home_more": "Show more",
        "home_less": "Show less",
        "home_how": "How does it work?",
        "home_step1_t": "Enter your symptoms",
        "home_step1_p": "Age, gender, symptoms, duration, and severity with simple buttons.",
        "home_step2_t": "Answer follow-up questions",
        "home_step2_p": "Past conditions, current medications, and any other important details.",
        "home_step3_t": "Get an initial assessment",
        "home_step3_p": "Urgency level, likely conditions, and appropriate recommendations.",
        "home_warn2": "<b>SymptoSense does not provide a final medical diagnosis</b> and is not a substitute for seeing a doctor. If you have dangerous symptoms (severe chest pain, difficulty breathing, heavy bleeding, loss of consciousness) call an ambulance immediately at <b>997</b>.",
        "ab_t1": "What is SymptoSense?",
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
    },
}


def _t(key):
    d = L.get(_lang(), L["ar"])
    return d.get(key, L["ar"].get(key, key))


def _nav():
    lang = _lang()
    path = request.path
    links = [
        ("/home", "nav_home"), ("/chat", "nav_chat"), ("/blood", "nav_blood"),
        ("/meds", "nav_meds"), ("/emergency", "nav_emergency"), ("/tips", "nav_tips"),
    ]
    html = '<nav class="nav"><div class="logo">Sympto<span>Sense</span> 🩺</div><div class="links">'
    for href, key in links:
        cls = ' class="on"' if path == href else ""
        html += '<a href="%s"%s>%s</a>' % (href, cls, _t(key))
    html += ('<div class="dd"><button class="dd-btn" onclick="toggleDD(event)">%s <span style="font-size:11px;">▼</span></button>'
             '<div class="dd-menu">'
             '<a href="/chat">%s</a>'
             '<a href="/emergency#geo">%s</a>'
             '<a href="/about">%s</a>'
             '</div></div>') % (_t("nav_explore"), _t("nav_q"), _t("nav_geo"),
                                 _t("nav_aware"))
    html += '</div>'
    html += ('<div class="lang-sw"><a href="#" onclick="setLang(&#39;ar&#39;);return false;" class="%s">العربية</a>'
             '<a href="#" onclick="setLang(&#39;en&#39;);return false;" class="%s">English</a></div>' %
             ("on" if lang == "ar" else "", "on" if lang == "en" else ""))
    html += '</nav>'
    return html


def _footer():
    return (
        '<div class="footer" id="contact">'
        '<p style="font-size:17px;font-weight:800;color:#FFFFFF;">SymptoSense ❤️‍🩹</p>'
        '<div class="f-links">'
        '<a href="/about">%s</a>'
        '<a href="/home#services">%s</a>'
        '<a href="/admin">%s</a>'
        '</div>'
        '<p>%s</p>'
        '<p style="margin-top:6px;">%s</p>'
        '</div>'
    ) % (_t("nav_about"), _t("nav_features"), _t("nav_admin"),
         _t("footer_note"), _t("footer_emergency"))


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
    return (
        PAGE_FRAME
        .replace("__LANG__", "en" if lang == "en" else "ar")
        .replace("__DIR__", "ltr" if lang == "en" else "rtl")
        .replace("__TITLE__", title)
        .replace("__DESC__", desc)
        .replace("__KEYWORDS__", _t("keywords"))
        .replace("__CANONICAL__", base + request.path)
        .replace("__GSC_TAG__", gsc_tag)
        .replace("__CSS__", BASE_CSS + extra_css)
        .replace("__NAV__", "" if bare else _nav())
        .replace("__FOOTER__", "" if bare else _footer())
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
    ("🇸🇦", "العربية", "ar", "واجهة عربية بالكامل"),
    ('<span class="flag-badge">UK</span>', "English", "en", "Full English interface"),
]

WELCOME_CSS = """
body { font-family: 'Poppins', 'Cairo', 'Segoe UI', Tahoma, sans-serif; background: #FFFFFF; color: #17356D; }
.w-container { max-width: 1200px; margin: 0 auto; padding: 0 18px; }
.w-nav { position: sticky; top: 0; z-index: 70; background: #FFFFFF; display: flex; align-items: center; justify-content: space-between; padding: 14px 34px; border-bottom: 1px solid #D7E7FA; }
.w-logo { display: flex; align-items: center; gap: 9px; font-size: 21px; font-weight: 800; cursor: pointer; }
.w-logo .sympto { color: #0B2E6B; }
.w-logo .sense { color: #1769E0; }
.w-links { display: flex; gap: 26px; }
.w-links a { position: relative; color: #17356D; font-size: 15px; font-weight: 500; padding-bottom: 6px; }
.w-links a:hover { color: #1769E0; }
.w-links a.on { color: #1769E0; font-weight: 700; }
.w-links a.on::after { content: ''; position: absolute; left: 0; right: 0; bottom: 0; height: 3px; border-radius: 3px; background: #1769E0; }
.hero-wrap { padding: 26px 20px 10px; }
.hero-card { display: flex; align-items: center; gap: 30px; background: linear-gradient(120deg, #E5F2FF 0%, #FFFFFF 70%); border: 1px solid #D7E7FA; border-radius: 34px; padding: 52px 46px; box-shadow: 0 18px 50px rgba(23,105,224,.10); }
.hero-left { flex: 1.15; }
.badge { display: inline-flex; align-items: center; gap: 8px; background: #DCEEFF; color: #0B2E6B; font-size: 13px; font-weight: 600; border-radius: 999px; padding: 8px 16px; margin-bottom: 22px; }
.hero-left h1 { font-size: 44px; line-height: 1.08; color: #0B2E6B; margin: 0 0 6px; }
.brand-big { display: block; font-size: 68px; font-weight: 800; color: #1769E0; letter-spacing: -.5px; }
.pulse-line { display: flex; align-items: center; gap: 10px; color: #1769E0; font-size: 20px; margin: 8px 0 14px; }
.pulse-line .ln { flex: 0 0 74px; height: 2px; border-radius: 2px; background: linear-gradient(90deg, #1769E0, transparent); }
.hero-sub { font-size: 18px; color: #17356D; opacity: .85; max-width: 520px; margin-bottom: 30px; line-height: 1.7; }
.wmsg { display: grid; }
.wmsg-item { grid-area: 1 / 1; opacity: 0; transform: translateY(10px); transition: opacity 1s ease, transform 1s ease; }
.wmsg-item.active { opacity: 1; transform: translateY(0); }
.wmsg-item .wflag { display: inline-block; vertical-align: middle; margin-right: 6px; font-size: 26px; line-height: 1; }
.flag-badge.sm { width: 27px; height: 27px; border-radius: 50%; background: linear-gradient(135deg, #0F766E, #134E4A); color: #FFFFFF; font-size: 11px; font-weight: 800; letter-spacing: .5px; display: inline-flex; align-items: center; justify-content: center; margin: 0; vertical-align: middle; }
.mini-features { display: grid; grid-template-columns: repeat(4, auto); gap: 22px; justify-content: start; }
.mf { text-align: center; }
.mf .ic { width: 54px; height: 54px; margin: 0 auto 8px; display: flex; align-items: center; justify-content: center; font-size: 26px; background: #DCEEFF; border-radius: 18px; }
.mf span { font-size: 13px; font-weight: 600; color: #0B2E6B; }
.hero-right { flex: 1; display: flex; align-items: center; justify-content: center; position: relative; min-height: 420px; }
.globe { position: absolute; width: 360px; height: 360px; border-radius: 50%; background: radial-gradient(circle, rgba(23,105,224,.14) 0%, rgba(23,105,224,.04) 55%, transparent 70%); }
.globe::before, .globe::after { content: ''; position: absolute; border-radius: 50%; border: 1.5px solid rgba(23,105,224,.18); inset: 12%; }
.globe::after { inset: 26%; }
.float-ic { position: absolute; font-size: 34px; filter: drop-shadow(0 6px 14px rgba(23,105,224,.25)); animation: floatic 5s ease-in-out infinite; }
.float-ic.f1 { top: 6%; left: 6%; animation-delay: 0s; }
.float-ic.f2 { top: 2%; right: 14%; animation-delay: 1.1s; }
.float-ic.f3 { bottom: 12%; left: 10%; animation-delay: 2s; }
.float-ic.f4 { bottom: 4%; right: 6%; animation-delay: .6s; }
.float-ic.f5 { top: 38%; left: 0; animation-delay: 1.6s; }
.float-ic.f6 { top: 34%; right: 0; animation-delay: .3s; }
@keyframes floatic { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-12px); } }
.phone { width: 214px; height: 424px; background: #0B2E6B; border-radius: 40px; padding: 12px; box-shadow: 0 34px 70px rgba(11,46,107,.40), inset 0 0 0 2px rgba(255,255,255,.12); position: relative; z-index: 2; }
.phone-screen { width: 100%; height: 100%; border-radius: 30px; background: linear-gradient(180deg, #DCEEFF 0%, #FFFFFF 100%); display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: 20px; }
.phone-heart { width: 74px; height: 74px; border-radius: 50%; background: #FFFFFF; box-shadow: 0 10px 26px rgba(23,105,224,.30); display: flex; align-items: center; justify-content: center; font-size: 36px; margin-bottom: 18px; }
.phone-screen p { color: #0B2E6B; font-size: 15px; font-weight: 600; line-height: 1.7; }
.lang-section { padding: 40px 20px 56px; text-align: center; }
.lang-section h2 { color: #134E4A; font-size: 30px; font-weight: 800; margin-bottom: 4px; }
.lang-section .muted { color: #64748b; font-size: 16px; margin-bottom: 28px; }
.lang-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; max-width: 660px; margin: 0 auto; }
.lang-tile { position: relative; display: flex; flex-direction: column; align-items: center; gap: 6px; justify-content: center; background: #FFFFFF; border: 2px solid #CCFBF1; border-radius: 22px; padding: 30px 22px; font-family: inherit; cursor: pointer; box-shadow: 0 6px 18px rgba(15,118,110,.08); transition: transform .15s ease, background .15s ease, box-shadow .15s ease, border-color .15s ease; }
.lang-tile .fl { font-size: 46px; line-height: 1; margin-bottom: 4px; }
.flag-badge { width: 58px; height: 58px; border-radius: 50%; background: linear-gradient(135deg, #0F766E, #134E4A); color: #FFFFFF; font-size: 17px; font-weight: 800; letter-spacing: 1px; display: flex; align-items: center; justify-content: center; margin: 0 auto; }
.lang-tile .lt { font-size: 23px; font-weight: 800; color: #134E4A; }
.lang-tile .ld { font-size: 14px; color: #64748B; }
.lang-tile .ck { position: absolute; top: 12px; right: 14px; width: 26px; height: 26px; border-radius: 50%; background: #0F766E; color: #FFFFFF; font-size: 15px; font-weight: 800; display: flex; align-items: center; justify-content: center; opacity: 0; transform: scale(.5); transition: opacity .15s ease, transform .2s ease; }
.lang-tile:hover, .lang-tile.sel { background: #F0FDFA; border-color: #0F766E; transform: translateY(-3px); box-shadow: 0 14px 32px rgba(15,118,110,.18); }
.lang-tile:hover .ck, .lang-tile.sel .ck { opacity: 1; transform: scale(1); }
.w-footer { background: #0B2E6B; color: #DCEEFF; text-align: center; padding: 34px 20px 26px; border-radius: 26px 26px 0 0; margin-top: 26px; }
.w-footer .fl { font-size: 20px; font-weight: 800; color: #FFFFFF; margin-bottom: 4px; }
.w-footer .fl em { font-style: normal; color: #6fb2ff; }
.w-footer p { font-size: 14px; margin-bottom: 14px; color: #c9dfff; }
.w-footer .wfl { display: flex; gap: 18px; justify-content: center; flex-wrap: wrap; font-size: 13px; margin-bottom: 14px; }
.w-footer .wfl a { color: #DCEEFF; }
.w-footer .wfl a:hover { color: #FFFFFF; text-decoration: underline; }
.w-footer .copy { font-size: 12px; color: #8fb4e8; }
.exit-curtain { position: fixed; z-index: 999; left: 50%; top: 50%; width: 150vmax; height: 150vmax; margin-left: -75vmax; margin-top: -75vmax; border-radius: 50%; background: radial-gradient(circle at center, #1769E0, #0B2E6B 65%, #08235b); transform: scale(0); opacity: 0; pointer-events: none; transition: transform .9s cubic-bezier(.65,0,.35,1), opacity .55s ease; }
.exit-curtain.open { transform: scale(1); opacity: 1; }
@media (max-width: 900px) {
  .w-nav { flex-direction: column; gap: 10px; padding: 12px 18px; }
  .w-links { gap: 16px; flex-wrap: wrap; justify-content: center; }
  .hero-card { flex-direction: column; padding: 34px 24px; }
  .brand-big { font-size: 46px; }
  .hero-left h1 { font-size: 34px; }
  .mini-features { grid-template-columns: repeat(2, auto); justify-content: center; }
  .hero-right { min-height: 360px; }
  .lang-grid { gap: 14px; }
  .lang-tile { padding: 22px 14px; }
  .lang-tile .fl { font-size: 36px; }
  .flag-badge { width: 46px; height: 46px; font-size: 14px; }
  .lang-tile .lt { font-size: 19px; }
}
"""


def welcome_page():
    cur = request.cookies.get("lang") or request.args.get("lang")
    if cur == "en":
        a0, a1, animate = "", " active", "false"
    elif cur == "ar":
        a0, a1, animate = " active", "", "false"
    else:
        a0, a1, animate = " active", "", "true"
    tiles = "".join(
        '<button class="lang-tile" onclick="ssGo(\'%s\',this)"><span class="ck">✓</span><span class="fl">%s</span><span class="lt">%s</span><span class="ld">%s</span></button>'
        % (code, flag, label, desc)
        for flag, label, code, desc in WELCOME_LANGS
    )
    body = """
    <div class="w-container">
      <div class="w-nav">
        <div class="w-logo"><span style="font-size:24px;">❤️‍🩹</span><span><span class="sympto">Sympto</span><span class="sense">Sense</span></span></div>
        <div class="w-links">
          <a href="/home" class="on">Home</a>
          <a href="/about">About</a>
          <a href="/home">Features</a>
          <a href="/home">How it works</a>
          <a href="/home">Contact</a>
        </div>
      </div>

      <div class="hero-wrap">
        <div class="hero-card">
          <div class="hero-left">
            <span class="badge">🔵 AI-Powered Health Assistant</span>
            <div class="wmsg" id="wmsg">
              <div class="wmsg-item__A0__">
                <h1><span class="wflag">🇸🇦</span> مرحبًا بك في <span class="brand-big">SymptoSense</span> 🩺</h1>
                <div class="pulse-line"><span class="ln"></span>❤️<span class="ln"></span></div>
                <p class="hero-sub">مساعدك الذكي لفهم الأعراض الصحية</p>
              </div>
              <div class="wmsg-item__A1__">
                <h1><span class="wflag"><span class="flag-badge sm">UK</span></span> Welcome to <span class="brand-big">SymptoSense</span> 🩺</h1>
                <div class="pulse-line"><span class="ln"></span>❤️<span class="ln"></span></div>
                <p class="hero-sub">Your smart assistant for understanding your symptoms</p>
              </div>
            </div>
            <div class="mini-features">
              <div class="mf"><div class="ic">🧠</div><span>Smart Analysis</span></div>
              <div class="mf"><div class="ic">🛡️</div><span>Reliable Information</span></div>
              <div class="mf"><div class="ic">🔒</div><span>Private &amp; Secure</span></div>
              <div class="mf"><div class="ic">❤️</div><span>Health First</span></div>
            </div>
          </div>
          <div class="hero-right">
            <div class="globe"></div>
            <span class="float-ic f1">🩺</span>
            <span class="float-ic f2">➕</span>
            <span class="float-ic f3">❤️</span>
            <span class="float-ic f4">🛡️</span>
            <span class="float-ic f5">🌱</span>
            <span class="float-ic f6">🌍</span>
            <div class="phone">
              <div class="phone-screen">
                <div class="phone-heart">❤️</div>
                <p>Understand your symptoms.<br>Take care of your health.</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="lang-section">
        <h2>🌐 اختر لغة الموقع</h2>
        <p class="muted">Choose your language</p>
        <div class="lang-grid">""" + tiles + """</div>
      </div>
    </div>

    <div class="w-footer">
      <div class="fl">Sympto<em>Sense</em> ❤️‍🩹</div>
      <p>Your health is our priority.</p>
      <div class="wfl"><a href="/about">Privacy Policy</a><a href="/about">Terms</a><a href="/home">Contact</a></div>
      <div class="copy">© 2026 SymptoSense. All rights reserved.</div>
    </div>

    <div class="exit-curtain" id="exitCurtain"></div>
    <script>
    function ssGo(code, el) {
      var tiles = document.querySelectorAll('.lang-tile');
      for (var i = 0; i < tiles.length; i++) tiles[i].classList.remove('sel');
      if (el) el.classList.add('sel');
      var lang = (code === 'ar') ? 'ar' : 'en';
      document.cookie = 'lang=' + lang + ';path=/;max-age=31536000;SameSite=Lax';
      try { localStorage.setItem('ss_lang', lang); } catch(e) {}
      document.getElementById('exitCurtain').classList.add('open');
      setTimeout(function(){ location.href = '/home'; }, 850);
    }
    (function(){
      var items = document.querySelectorAll('.wmsg-item');
      if (items.length < 2) return;
      var i = 0;
      for (var k = 0; k < items.length; k++) {
        if (items[k].classList.contains('active')) i = k;
      }
      if (!__ANIM__) return;
      setInterval(function(){
        items[i].classList.remove('active');
        i = (i + 1) % items.length;
        items[i].classList.add('active');
      }, 2600);
    })();
    </script>
    """
    html = _page(_t("title_landing"), body, bare=True, extra_css=WELCOME_CSS)
    html = (html
            .replace("wmsg-item__A0__", "wmsg-item" + a0)
            .replace("wmsg-item__A1__", "wmsg-item" + a1)
            .replace("__ANIM__", animate))
    return html.replace('dir="rtl"', 'dir="ltr"').replace('lang="ar"', 'lang="en"')


def home_page():
    t = _t
    body = """
    <div class="hh">
      <div class="hh-l">
        <span class="hh-badge">🤖 %s</span>
        <h1>%s <span class="hl">%s</span></h1>
        <p class="hh-sub">%s</p>
        <p class="hh-desc">%s</p>
        <div class="hh-btns">
          <a class="btn pri" href="/chat">🔵 %s</a>
          <a class="btn sec" href="#how">%s</a>
        </div>
      </div>
      <div class="hh-r">
        <div class="hh-globe"></div>
        <span class="hh-ic i1">🩺</span>
        <span class="hh-ic i2">❤️</span>
        <span class="hh-ic i3">📱</span>
        <span class="hh-ic i4">🤖</span>
        <span class="hh-ic i5">➕</span>
        <span class="hh-ic i6">🛡️</span>
        <div class="phone">
          <div class="phone-screen">
            <div class="phone-heart">❤️</div>
            <p>%s</p>
            <p>%s</p>
          </div>
        </div>
      </div>
    </div>

    <h2 class="sec-head" id="services">%s</h2>
    <p class="sec-sub">%s</p>
    <div class="features">
      <a class="feature serv" href="/chat"><div class="ic">🩺</div><h3>%s</h3><p>%s</p></a>
      <a class="feature serv" href="/blood"><div class="ic">🩸</div><h3>%s</h3><p>%s</p></a>
      <a class="feature serv" href="/meds"><div class="ic">💊</div><h3>%s</h3><p>%s</p></a>
      <a class="feature serv" href="/emergency"><div class="ic">🏥</div><h3>%s</h3><p>%s</p></a>
      <a class="feature serv" href="/firstaid"><div class="ic">🚨</div><h3>%s</h3><p>%s</p></a>
      <a class="feature serv" href="/emergency"><div class="ic">🚑</div><h3>%s</h3><p>%s</p></a>
      <div id="more-services">
        <a class="feature serv" href="/chat"><div class="ic">❓</div><h3>%s</h3><p>%s</p></a>
        <a class="feature serv" href="/tips"><div class="ic">💡</div><h3>%s</h3><p>%s</p></a>
        <a class="feature serv" href="/relax"><div class="ic">🧘</div><h3>%s</h3><p>%s</p></a>
        <a class="feature serv" href="/checkin"><div class="ic">📋</div><h3>%s</h3><p>%s</p></a>
      </div>
    </div>
    <button class="more-btn" id="moreBtn" onclick="var m=document.getElementById('more-services');var open=m.style.display!=='none';m.style.display=open?'none':'grid';document.getElementById('moreBtn').textContent=open?'%s':'%s';">%s</button>

    <h2 class="sec-head" id="how">%s</h2>
    <div class="how-wrap">
      <div class="how-step"><span class="n">01</span><h3>%s</h3><p>%s</p></div>
      <span class="how-arrow ar">←</span><span class="how-arrow en">→</span>
      <div class="how-step"><span class="n">02</span><h3>%s</h3><p>%s</p></div>
      <span class="how-arrow ar">←</span><span class="how-arrow en">→</span>
      <div class="how-step"><span class="n">03</span><h3>%s</h3><p>%s</p></div>
    </div>

    <div class="warn2"><span class="w-ic">⚠️</span><div>%s</div></div>
    """ % (
        t("home_badge"),
        t("home_h1"), t("home_h1b"), t("home_sub"), t("home_desc"),
        t("home_btn1"), t("home_btn2"),
        t("home_ph1"), t("home_ph2"),
        t("home_services"), t("home_services_sub"),
        t("home_f_t"), t("home_f_p"), t("home_b_t"), t("home_b_p"),
        t("home_m_t"), t("home_m_p"), t("home_h_t"), t("home_h_p"),
        t("home_fa_t"), t("home_fa_p"), t("home_e_t"), t("home_e_p"),
        t("home_q_t"), t("home_q_p"),
        t("home_t_t"), t("home_t_p"), t("home_r_t"), t("home_r_p"),
        t("home_c_t"), t("home_c_p"),
        t("home_more"), t("home_less"), t("home_more"),
        t("home_how"),
        t("home_step1_t"), t("home_step1_p"),
        t("home_step2_t"), t("home_step2_p"),
        t("home_step3_t"), t("home_step3_p"),
        t("home_warn2"),
    )
    return _page(_t("title_landing"), body)


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
    <div class="how-wrap">
      <div class="how-step"><span class="n">1</span><h3>%s</h3><p>%s</p></div>
      <span class="how-arrow ar">←</span><span class="how-arrow en">→</span>
      <div class="how-step"><span class="n">2</span><h3>%s</h3><p>%s</p></div>
      <span class="how-arrow ar">←</span><span class="how-arrow en">→</span>
      <div class="how-step"><span class="n">3</span><h3>%s</h3><p>%s</p></div>
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
        t("ab_how1_t"), t("ab_how1_p"),
        t("ab_how2_t"), t("ab_how2_p"),
        t("ab_how3_t"), t("ab_how3_p"),
        t("ab_srcs_h"), t("ab_srcs_p2"),
        t("ab_priv_h"), t("ab_priv_p"),
    )
    return _page(_t("title_about"), body)


# ---------------------------------------------------------------- chat
CHAT = {
    "ar": {
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
        "result_title": "📋 نتيجة التحليل",
        "urg_label": "مستوى الخطورة",
        "urg_high": "طوارئ", "urg_medium": "يحتاج إلى موعد طبي", "urg_low": "بسيط",
        "assessment_label": "التقييم الأولي:",
        "forced_high": "⚠️ تم رفع الخطورة تلقائياً بناءً على الأعراض الحمراء.",
        "low_conf": "⚖️ الثقة منخفضة — يُفضل مراجعة الطبيب.",
        "possible": "🩺 الاحتمالات المحتملة",
        "medwarn": "💊 تحذيرات الأدوية",
        "medwarn_note": "التوعية فقط — لا توقفي دواءك الموصوف بدون استشارة الطبيب.",
        "ml_title": "📊 تحليل نموذج التعلم الآلي",
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
        "result_title": "📋 Analysis result",
        "urg_label": "Severity level",
        "urg_high": "Emergency", "urg_medium": "Needs an appointment", "urg_low": "Mild",
        "assessment_label": "Initial assessment:",
        "forced_high": "⚠️ Urgency raised automatically based on red-flag symptoms.",
        "low_conf": "⚖️ Low confidence — a doctor visit is recommended.",
        "possible": "🩺 Possible conditions",
        "medwarn": "💊 Medication warnings",
        "medwarn_note": "Awareness only — don't stop your prescribed medication without consulting your doctor.",
        "ml_title": "📊 Machine learning model analysis",
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
    function addQ(msg) {
      const d = document.createElement('div');
      d.className = 'bubble q';
      d.textContent = msg;
      bodyEl.appendChild(d);
      bodyEl.scrollTop = bodyEl.scrollHeight;
      if (autoSpeak && msg !== lastSpokenMsg) { lastSpokenMsg = msg; speakText(msg); }
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

    function startChat() {
      addHtml('<div class="chat-start"><div class="cs-logo">🩺</div><div class="cs-title">' + esc(TT('welcome')) + '</div><div class="cs-sub">' + esc(TT('start_sub')) + '</div><div class="cs-desc">' + esc(TT('start_desc')) + '</div></div>', 'q start');
      askSymptoms();
    }
    function appendStartBtn() {
      const s = document.createElement('button');
      s.className = 'start-btn';
      s.textContent = TT('start_btn');
      s.onclick = beginAssessment;
      optsEl.appendChild(s);
    }
    function beginAssessment() {
      if (!state.symptoms.length) { add(TT('atleast'), 'bot'); return; }
      add(TT('chosen') + state.symptoms.join(LANG === 'en' ? ', ' : '، '), 'user');
      clearOpts();
      askAge();
    }
    function askAge() {
      state.step = 'age';
      addQ(TT('age'));
      showText(TT('age_ph'));
    }
    function askGender() {
      state.step = 'gender';
      addQ(TT('gender'));
      showOpts([
        {label:TT('male'), fn:()=>{ state.gender='m'; add(TT('male'),'user'); askDuration(); }},
        {label:TT('female'), fn:()=>{ state.gender='f'; add(TT('female'),'user'); askDuration(); }}
      ]);
    }
    function G(f, m) { return state.gender === 'm' ? m : f; }
    function askSymptoms() {
      state.step = 'symptoms';
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
      showOpts(items);
      appendStartBtn();
    }
    function askDuration() {
      state.step = 'duration';
      addQ(TT('duration'));
      showOpts(DURS.map(d=>({label:d, fn:()=>{ state.duration=d; add(d,'user'); askSeverity(); }})));
    }
    function askSeverity() {
      state.step = 'severity';
      addQ(TT('severity'));
      showOpts(SEVS.map(([v,l])=>({label:l, fn:()=>{ state.severity=v; add(l,'user'); askConditions(); }})));
    }
    function askConditions() {
      state.step = 'conditions';
      addQ(G(TT('conditions_f'), TT('conditions_m')));
      const items = CONDS.map(c=>({label:c, fn:()=>{ state.conditions=c; add(c,'user'); askMeds(); }}));
      items.push({label:TT('other_diseases'), fn:()=>{ addQ(G(TT('other_diseases_f'), TT('other_diseases_m'))); showText(TT('cond_ph')); }});
      showOpts(items);
    }
    function askMeds() {
      state.step = 'medications';
      addQ(G(TT('meds_f'), TT('meds_m')));
      showOpts([{label:TT('skip'), fn:()=>{ add(TT('skip'),'user'); state.medications=''; askNotes(); }}]);
      showText(TT('meds_ph'), true);
    }
    function askNotes() {
      state.step = 'notes';
      addQ(G(TT('notes_f'), TT('notes_m')));
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
        add(TT('added_n'), 'bot');
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
      const pcls = u==='high' ? 'hi' : (u==='medium' ? 'med' : 'low');
      const uEmoji = u==='high' ? '🔴' : (u==='medium' ? '🟡' : '🟢');
      const uVal = pillLabel(u);
      let h = '<div class="res-card">';
      h += '<div class="res-title">' + TT('result_card_title') + '</div>';
      h += '<div class="res-urg"><span class="pill2 ' + pcls + '"><span class="urg-lbl">' + uEmoji + ' ' + esc(TT('urg_label')) + '</span><span class="urg-val">' + esc(uVal) + '</span></span></div>';
      if (d.rule_forced_high) h += '<div class="warn" style="margin:8px 0;">' + TT('forced_high') + '</div>';
      if (d.low_confidence) h += '<div class="muted" style="text-align:center;margin-bottom:8px;">' + TT('low_conf') + '</div>';
      h += '<div class="res-note"><b>' + esc(TT('assessment_label')) + '</b> ' + esc(d.personal_note) + '</div>';
      h += '<div class="res-disc">' + esc(TT('result_disclaimer')) + '</div>';

      if (d.possible_conditions) h += '<div class="rc-title">' + TT('possible') + '</div><div class="res-sec">' + esc(d.possible_conditions) + '</div>';
      if (d.med_warnings && d.med_warnings.length) {
        h += '<div class="rc-title">' + TT('medwarn') + '</div>';
        d.med_warnings.forEach(m => h += '<div class="rec-item"><b>' + esc(NAME(m, 'name_ar', 'name_en')) + '</b>: ' + esc(NAME(m, 'warning_ar', 'warning_en')) + '</div>');
        h += '<div class="muted">' + TT('medwarn_note') + '</div>';
      }
      if (d.ml_predictions && d.ml_predictions.length) {
        h += '<div class="rc-title">' + TT('ml_title') + '</div>';
        d.ml_predictions.forEach(p => {
          const pct = Math.round(p.probability*100);
          h += '<div class="ml-row"><span>' + esc(NAME(p, 'name_ar', 'name_en')) + '</span><b>' + pct + '%</b></div>';
          h += '<div class="bar-bg"><div class="bar-fill" style="width:' + pct + '%"></div></div>';
        });
        h += '<div class="ml-note">' + esc(TT('ml_note')) + '</div>';
      }
      if (d.recommendations && d.recommendations.length) {
        h += '<div class="rc-title">' + TT('recs') + '</div>';
        d.recommendations.forEach((r, i) => {
          h += '<div class="rec-card"><div class="rec-head"><span class="rec-num">' + (i+1) + '</span><b>' + esc(r.title || r.tip) + '</b></div>';
          if (r.title && r.tip) h += '<div class="rec-body">' + esc(r.tip) + '</div>';
          if (r.source) h += '<div class="src">' + esc(TT('rec_src')) + ': ' + (r.url ? '<a href="' + esc(r.url) + '" target="_blank">' + esc(r.source) + '</a>' : esc(r.source)) + '</div>';
          h += '</div>';
        });
      }
      if (d.danger_signs) h += '<div class="rc-title">' + TT('danger') + '</div><div class="res-sec bullets">' + esc(d.danger_signs) + '</div>';
      if (d.when_to_seek_care) h += '<div class="rc-title">' + TT('when') + '</div><div class="res-sec">' + esc(d.when_to_seek_care) + '</div>';
      if (d.home_care) h += '<div class="rc-title">' + TT('home_care') + '</div><div class="res-sec bullets">' + esc(d.home_care) + '</div>';
      if (d.medication_guidance) h += '<div class="rc-title">' + TT('med_guid') + '</div><div class="res-sec">' + esc(d.medication_guidance) + '</div>';
      if (d.questions_for_doctor) h += '<div class="rc-title">' + TT('q_doc') + '</div><div class="res-sec">' + esc(d.questions_for_doctor) + '</div>';
      h += '</div>';
      addHtml(h, 'result');
      addHtml('<div style="margin-top:10px;text-align:center;"><button class="opt" onclick="speakResult()">' + TT('listen_all') + '</button></div>', 'result');
      addHtml('<div class="sec-title">' + TT('fb_title') + '</div><div style="display:flex;gap:6px;flex-wrap:wrap;justify-content:center;">' +
        '<button class="opt" data-v="1" onclick="fb(this.dataset.v)">' + TT('fb_excellent') + '</button>' +
        '<button class="opt" data-v="2" onclick="fb(this.dataset.v)">' + TT('fb_good') + '</button>' +
        '<button class="opt" data-v="3" onclick="fb(this.dataset.v)">' + TT('fb_ok') + '</button>' +
        '<button class="opt" data-v="4" onclick="fb(this.dataset.v)">' + TT('fb_no') + '</button></div>' +
        '<div id="fbMsg" style="margin-top:8px;text-align:center;font-weight:600;color:#1677E8;"></div>', 'result');
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
        .replace("__SPEAK_ON__", CHAT["ar" if ar else "en"]["speak_on"])
        .replace("__SPEAK_TITLE__", CHAT["ar" if ar else "en"]["speak_title"])
        .replace("__INPUT_PH__", CHAT["ar" if ar else "en"]["input_ph"])
        .replace("__MIC_TITLE__", CHAT["ar" if ar else "en"]["mic_title"])
        .replace("__SEND__", CHAT["ar" if ar else "en"]["send"])
        .replace("__MUTED__", CHAT["ar" if ar else "en"]["muted"]))



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
        "blood_reading": "جاري قراءة الفحص وتحليله...",
        "blood_err": "تعذر التحليل",
        "bl_summ": "📋 ملخص الفحص",
        "bl_sum_normal": "طبيعي", "bl_sum_follow": "يحتاج متابعة", "bl_sum_out": "خارج النطاق",
        "bl_mean_title": "💡 ماذا تعني هذه النتائج؟",
        "bl_do": "🩺 ماذا أفعل؟",
        "bl_col_ind": "المؤشر", "bl_col_val": "النتيجة", "bl_col_status": "الحالة",
        "bl_what": "ما هو؟", "bl_mean": "ماذا تعني النتيجة؟", "bl_ref": "النطاق المرجعي", "bl_when": "متى يحتاج مراجعة الطبيب؟",
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
        "blood_reading": "Reading and analyzing the test...",
        "blood_err": "Analysis failed",
        "bl_summ": "📋 Test Summary",
        "bl_sum_normal": "Normal", "bl_sum_follow": "Needs follow-up", "bl_sum_out": "Out of range",
        "bl_mean_title": "💡 What do these results mean?",
        "bl_do": "🩺 What should I do?",
        "bl_col_ind": "Indicator", "bl_col_val": "Result", "bl_col_status": "Status",
        "bl_what": "What is it?", "bl_mean": "What does the result mean?", "bl_ref": "Reference range", "bl_when": "When to see a doctor?",
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
          h += '<td><b>' + esc(it.name) + '</b></td><td>' + esc(String(it.value)) + ' ' + esc(it.unit || '') + '</td>';
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
    }
    function toggleInd(i) { const el = document.getElementById('bl-det-' + i); if (el) el.style.display = el.style.display === 'none' ? '' : 'none'; }
    function stCls(s) { return s === 'normal' ? 'p2-green' : (s === 'low' ? 'p2-orange' : 'p2-red'); }
    function stTxt(s) { return s === 'normal' ? TT('bl_status_n') : (s === 'low' ? TT('bl_status_l') : TT('bl_status_h')); }
    function lvlCls(l) { return l === 'normal' ? 'p2-green' : (l === 'see_doctor' ? 'p2-orange' : (l === 'urgent' ? 'p2-red' : 'p2-dark')); }
    function lvlTxt(l) { return TT('bl_lvl_' + l) || l; }
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
    t = CT["en" if _lang() == "en" else "ar"]
    body = """
    <div class="card">
      <h2>__MH__</h2>
      <p class="muted">__MSUB__</p>
      <div style="margin-top:16px;">
        <div class="search-box">
          <span class="sb-ic">🔎</span>
          <input class="inp" id="medInput" placeholder="__MPH__" onkeydown="if(event.key==='Enter'){searchDrug();}">
          <button class="btn pri sb-btn" onclick="searchDrug()">__MBTN__</button>
        </div>
        <div id="medRes" style="margin-top:16px;"></div>
      </div>
    </div>
    <div class="card" style="margin-top:16px;">
      <h2>__RH__</h2>
      <p class="muted">__RSUB__</p>
      <div class="grid2">
        <div><label class="lbl">__RNAME__</label><input class="inp" id="remName" placeholder="__RNAMEPH__"></div>
        <div><label class="lbl">__RTIMES__</label><input class="inp" id="remTimes" placeholder="__RTIMESPH__"></div>
      </div>
      <div style="margin-top:12px;"><button class="btn" onclick="addReminder()">__RSAVE__</button></div>
      <div id="remMsg" style="margin-top:8px;font-weight:600;color:#1677E8;"></div>
      <div class="rc-title">__REMLISTH__</div>
      <div id="remList" style="margin-top:12px;"></div>
    </div>
    <div class="warn">__MWARN__</div>
    <div class="warn" style="margin-top:16px;">__MWARN2__</div>
    <script>
    const T = __PT__;
    function TT(k) { return T[k] || k; }
    function esc(s) { const div=document.createElement('div'); div.textContent=s||''; return div.innerHTML; }
    async function searchDrug() {
      const name = document.getElementById('medInput').value.trim();
      const box = document.getElementById('medRes');
      if (!name) { box.innerHTML = '<div class="warn">' + esc(TT('meds_write')) + '</div>'; return; }
      box.innerHTML = '<div class="bubble bot">' + esc(TT('meds_searching')) + ' <span class="spin"></span></div>';
      const r = await fetch('/api/drug?name=' + encodeURIComponent(name));
      const d = await r.json();
      if (!d.ok) { box.innerHTML = '<div class="bubble bot">' + esc(TT('meds_nf')) + '</div>'; return; }
      box.innerHTML =
        '<div class="drug-card">' +
        '<div class="drug-name">💊 ' + esc(d.name) + '</div>' +
        '<div class="drug-sec"><div class="drug-sec-t">' + esc(TT('meds_sec_uses')) + '</div><p>' + esc(d.uses) + '</p></div>' +
        '<div class="drug-sec"><div class="drug-sec-t wr">' + esc(TT('meds_sec_warn')) + '</div><p>' + esc(d.warning) + '</p></div>' +
        '<div class="drug-sec"><div class="drug-sec-t">' + esc(TT('meds_sec_int')) + '</div><p>' + esc(d.interactions) + '</p></div>' +
        '<div class="drug-sec"><div class="drug-sec-t wt">' + esc(TT('meds_sec_consult')) + '</div><p>' + esc(TT('meds_consult_txt')) + '</p></div>' +
        '<div class="drug-note">' + esc(TT('meds_disc')) + '</div>' +
        '</div>';
    }
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
        ("__MH__", t["meds_h"]), ("__MSUB__", t["meds_sub"]),
        ("__MPH__", t["meds_ph"]), ("__MBTN__", t["meds_btn"]),
        ("__RH__", t["rem_h"]), ("__RSUB__", t["rem_sub"]),
        ("__RNAME__", t["rem_name"]), ("__RNAMEPH__", t["rem_name_ph"]),
        ("__RTIMES__", t["rem_times"]), ("__RTIMESPH__", t["rem_times_ph"]),
        ("__RSAVE__", t["rem_save"]), ("__MWARN__", t["meds_warn"]),
        ("__REMLISTH__", t["rem_list_h"]), ("__MWARN2__", t["meds_warn2"]),
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
      <div style="font-size:16px;line-height:2;background:#F0F7FF;border-radius:12px;padding:20px;white-space:pre-wrap;">__TXT__</div>
      <div style="text-align:center;margin-top:16px;"><div id="breathBox" style="font-size:30px;font-weight:800;color:#1677E8;height:70px;display:flex;align-items:center;justify-content:center;"></div></div>
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
    <style>body { background: #F8FAFC; }</style>
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
      <div id="geoMsg" style="text-align:center;margin-top:10px;font-weight:700;color:#0F766E;"></div>
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
      <div id="ciMsg" style="margin-top:10px;font-weight:700;color:#1677E8;text-align:center;"></div>
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
        <div id="pfMsg" style="text-align:center;font-weight:700;color:#1677E8;"></div>
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
        "- %s%s (%s)" % (
            (r.get("title") + ": ") if r.get("title") else "",
            r.get("tip") or r.get("title") or "",
            r.get("source") or "",
        )
        for r in recs if isinstance(r, dict) and (r.get("tip") or r.get("title"))
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
    ax.plot(range(len(vals)), vals, marker="o", color="#4d97ef", linewidth=2)
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


@app.route("/api/drug")
def api_drug():
    name = (request.args.get("name") or "").strip()
    d = medication_warnings.lookup_drug(name)
    if not d:
        return jsonify({"ok": False})
    lang = "en" if _lang() == "en" else "ar"
    return jsonify({
        "ok": True,
        "name": d["name_en"] if lang == "en" else d["name_ar"],
        "uses": d["uses_en"] if lang == "en" else d["uses_ar"],
        "warning": d["warning_en"] if lang == "en" else d["warning_ar"],
        "interactions": d["interact_en"] if lang == "en" else d["interact_ar"],
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
        return jsonify({
            "ok": True, "text_html": text_html, "chart": chart_b64, "level": level,
            "indicators": indicators,
            "notes": [n[0] if lang == "ar" else n[1] for n in notes],
            "dangers": [d[1] if lang == "ar" else d[2] for d in dangers],
            "summary": blood_test.summary_text(level, lang),
            "disclaimer": blood_test.disclaimer_text(lang),
            "child": bool(child_note),
            "child_note": blood_test.child_note_text(lang) if child_note else None,
        })
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
