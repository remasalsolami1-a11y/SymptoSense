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
from datetime import datetime, timezone

from flask import Flask, request, jsonify, render_template_string, session, send_file, Response

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
.dash-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 12px; }
.dash-stat { background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 14px; padding: 12px 6px; text-align: center; }
.dash-stat b { display: block; font-size: 22px; color: #0B2E6B; }
.dash-stat span { font-size: 12px; color: #64748B; }
.tools { max-width: 880px; margin: 30px auto 0; padding: 0 8px; }
.tools-h { text-align: center; font-size: 23px; font-weight: 800; color: #0B2E6B; }
.tools-sub { text-align: center; color: #64748B; margin-bottom: 16px; font-size: 14px; }
.tools-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.tool { background: #FFFFFF; border: 1.5px solid #E2E8F0; border-radius: 16px; padding: 18px 12px; text-align: center; text-decoration: none; color: #0F172A; transition: transform .15s ease, box-shadow .15s ease, border-color .15s ease; }
.tool:hover { transform: translateY(-3px); box-shadow: 0 10px 22px rgba(15,23,42,.08); border-color: #99F6E4; }
.tool .t-ic { font-size: 34px; display: block; margin-bottom: 8px; }
.tool b { display: block; font-size: 15px; color: #0F766E; margin-bottom: 4px; }
.tool p { font-size: 12.5px; color: #64748B; line-height: 1.6; }
@media (max-width: 640px) { .tools-grid { grid-template-columns: repeat(2, 1fr); } }
.cmp-table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }
.cmp-table th, .cmp-table td { border: 1px solid #E2E8F0; padding: 8px 10px; text-align: center; }
.cmp-table th { background: #F1F5F9; color: #0B2E6B; font-size: 12px; }
.hist-card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 14px 16px; margin-bottom: 12px; }
.hist-head { display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap; }
.pill { padding: 3px 11px; border-radius: 999px; font-size: 12px; font-weight: 700; }
.pill-hi { background: #fee2e2; color: #b91c1c; }
.pill-med { background: #fef3c7; color: #92400e; }
.pill-low { background: #dcfce7; color: #166534; }
.hist-row { margin-top: 8px; display: flex; gap: 6px; flex-wrap: wrap; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.em-overlay { position: fixed; inset: 0; z-index: 9999; display: none; align-items: center; justify-content: center; background: rgba(15,23,42,.55); backdrop-filter: blur(3px); padding: 18px; }
.blood-banner { margin: 12px auto 0; max-width: 560px; text-align: center; padding: 10px 16px; background: #F0FDFA; border: 1px solid #99F6E4; color: #115E59; border-radius: 12px; font-size: 13.5px; font-weight: 700; }
.rel-title { text-align: center; font-size: 13px; font-weight: 800; color: #0F766E; margin-top: 14px; }
.rel-chips { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-top: 8px; }
.rel-chip { padding: 8px 14px; border-radius: 999px; border: 1.5px dashed #14B8A6; background: #FFFFFF; color: #0F766E; font-size: 13px; font-weight: 700; cursor: pointer; }
.rel-chip:hover { background: #CCFBF1; }
.em-card { background: #FFFFFF; border: 2px solid #DC2626; border-radius: 22px; padding: 30px 26px; max-width: 460px; width: 100%; text-align: center; box-shadow: 0 26px 70px rgba(153,27,27,.35); animation: emPop .35s cubic-bezier(.34,1.56,.64,1); }
@keyframes emPop { from { transform: scale(.85); opacity: 0; } to { transform: scale(1); opacity: 1; } }
.em-card .em-icon { width: 74px; height: 74px; margin: 0 auto 12px; border-radius: 50%; background: #FEE2E2; display: flex; align-items: center; justify-content: center; font-size: 40px; }
.em-card h3 { font-size: 23px; font-weight: 800; color: #991B1B; margin: 0 0 8px; }
.em-card p { font-size: 15px; color: #475569; line-height: 1.7; margin: 0 0 14px; }
.em-flags { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-bottom: 18px; }
.em-chip { background: #FEF2F2; border: 1px solid #FECACA; color: #991B1B; font-size: 13px; font-weight: 700; padding: 6px 12px; border-radius: 999px; }
.em-btns { display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; }
.em-call { background: #DC2626; color: #FFFFFF; font-weight: 800; padding: 12px 22px; border-radius: 12px; font-size: 15px; text-decoration: none; transition: background .2s ease, transform .15s ease; }
.em-call:hover { background: #B91C1C; transform: translateY(-2px); }
.em-num { margin: 10px 0 2px; font-size: 16px; font-weight: 800; color: #B91C1C; letter-spacing: 1px; cursor: pointer; user-select: all; }
.em-proceed { background: #F1F5F9; color: #334155; font-weight: 700; padding: 12px 22px; border-radius: 12px; font-size: 15px; border: 1px solid #CBD5E1; cursor: pointer; transition: background .2s ease; }
.em-proceed:hover { background: #E2E8F0; }
.voice-overlay { position: fixed; inset: 0; z-index: 9999; display: none; align-items: center; justify-content: center; background: rgba(15,23,42,.55); backdrop-filter: blur(3px); padding: 18px; }
.voice-card { background: #FFFFFF; border-radius: 22px; padding: 30px 26px; max-width: 360px; width: 100%; text-align: center; box-shadow: 0 26px 70px rgba(2,44,34,.35); animation: emPop .35s cubic-bezier(.34,1.56,.64,1); }
.v-mic { width: 84px; height: 84px; margin: 0 auto 14px; border-radius: 50%; background: #F0FDFA; border: 3px solid #14B8A6; display: flex; align-items: center; justify-content: center; font-size: 42px; animation: vPulse 1.4s ease-in-out infinite; }
@keyframes vPulse { 0%,100% { box-shadow: 0 0 0 0 rgba(20,184,166,.45); transform: scale(1); } 50% { box-shadow: 0 0 0 18px rgba(20,184,166,0); transform: scale(1.06); } }
.v-title { font-size: 16px; font-weight: 800; color: #16324F; }
.cs-voice { display: inline-block; margin-top: 14px; padding: 10px 20px; border-radius: 999px; border: 1.5px dashed #14B8A6; background: #F0FDFA; color: #0F766E; font-weight: 800; font-size: 14px; cursor: pointer; transition: background .2s ease; }
.cs-voice:hover { background: #CCFBF1; }
.vstop { background: #14B8A6; color: #FFFFFF; font-weight: 800; padding: 11px 22px; border-radius: 12px; font-size: 14px; border: none; cursor: pointer; }
.vcnl { background: #F1F5F9; color: #334155; font-weight: 700; padding: 11px 22px; border-radius: 12px; font-size: 14px; border: 1px solid #CBD5E1; cursor: pointer; }
.warn { background: #FEF2F2; border: 1px solid #FECACA; color: #991B1B; padding: 10px 14px; border-radius: 12px; font-size: 14px; font-weight: 700; margin: 8px 0; }
.em-disc { font-size: 12px; color: #94A3B8; margin-top: 12px; }
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
.bl-explain { border: 1px solid #99F6E4; background: #F0FDFA; color: #0F766E; border-radius: 999px; padding: 2px 9px; font-size: 11px; font-weight: 700; cursor: pointer; font-family: inherit; margin-inline-start: 6px; white-space: nowrap; }
.bl-explain:hover { background: #CCFBF1; }
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
.res-person { text-align: center; background: #F0FDFA; border: 1px solid #99F6E4; color: #0F766E; font-weight: 800; font-size: 13px; border-radius: 999px; padding: 6px 14px; display: inline-block; margin-bottom: 10px; }
.res-urg { text-align: center; margin: 6px 0 10px; }
.res-triage { display: block; margin: 4px auto 4px; width: fit-content; font-size: 16px; font-weight: 800; padding: 8px 22px; border-radius: 999px; background: #0F766E; color: #fff; }
.triage-why { margin: 10px 0 4px; padding: 10px 12px; background: #F0FDFA; border: 1px solid #99F6E4; border-radius: 12px; font-size: 13.5px; color: #115E59; line-height: 1.8; }
.res-sim-toggle { text-align: center; margin: 10px 0 4px; }
.sim-box { padding: 14px; background: #FFF7ED; border: 1px solid #FDBA74; border-radius: 14px; font-size: 15px; color: #7C2D12; line-height: 1.9; }
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
<style>
.asst-fab { position: fixed; bottom: 22px; right: 22px; z-index: 999; width: 58px; height: 58px; border-radius: 50%; background: linear-gradient(135deg, #1769E0, #0F766E); color: #FFF; font-size: 26px; display: flex; align-items: center; justify-content: center; cursor: pointer; box-shadow: 0 10px 26px rgba(15,118,110,.45); border: none; animation: asstPulse 2.4s infinite; }
[dir="rtl"] .asst-fab { right: auto; left: 22px; }
@keyframes asstPulse { 0%,100% { box-shadow: 0 10px 26px rgba(15,118,110,.45); } 50% { box-shadow: 0 10px 34px rgba(23,105,224,.65); } }
.asst-panel { position: fixed; bottom: 92px; right: 22px; z-index: 999; width: 348px; max-width: calc(100vw - 28px); max-height: 560px; display: none; flex-direction: column; background: #FFFFFF; border: 1px solid #D7E7FA; border-radius: 20px; box-shadow: 0 20px 60px rgba(11,46,107,.22); overflow: hidden; }
[dir="rtl"] .asst-panel { right: auto; left: 22px; }
.asst-panel.open { display: flex; }
.asst-head { background: linear-gradient(120deg, #0B2E6B, #1769E0); color: #FFFFFF; padding: 14px 16px; display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.asst-head b { font-size: 15px; }
.asst-sub { font-size: 12px; opacity: .85; margin-top: 2px; }
.asst-head button { background: rgba(255,255,255,.16); color: #FFF; border: none; border-radius: 50%; width: 30px; height: 30px; font-size: 14px; cursor: pointer; }
.asst-body { flex: 1; overflow-y: auto; padding: 12px; background: #F6FAFF; min-height: 160px; max-height: 360px; }
.asst-msg { border-radius: 14px; padding: 9px 12px; margin: 6px 0; font-size: 14px; line-height: 1.6; max-width: 92%; word-break: break-word; }
.asst-user { background: #1769E0; color: #FFF; margin-left: auto; }
[dir="rtl"] .asst-user { margin-left: 0; margin-right: auto; }
.asst-bot { background: #FFFFFF; border: 1px solid #D7E7FA; color: #1e293b; }
.asst-qs { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.asst-chip { border: 1px solid #99F6E4; background: #FFFFFF; color: #0F766E; border-radius: 999px; padding: 6px 12px; font-size: 12px; font-weight: 700; cursor: pointer; font-family: inherit; }
.asst-chip:hover { background: #F0FDFA; }
.asst-emerg { background: #FEE2E2; border: 1px solid #FCA5A5; color: #7F1D1D; border-radius: 12px; padding: 10px 12px; margin: 8px 0; font-size: 13px; line-height: 1.7; }
.asst-emerg a { color: #B91C1C; font-weight: 800; }
.asst-foot { display: flex; gap: 8px; padding: 10px 12px; border-top: 1px solid #E2E8F0; background: #FFFFFF; }
.asst-inp { flex: 1; border: 1px solid #CBD5E1; border-radius: 10px; padding: 9px 12px; font-size: 14px; font-family: inherit; }
.asst-foot button { border: none; border-radius: 10px; background: #1769E0; color: #FFF; padding: 0 16px; font-size: 15px; cursor: pointer; }
.asst-disc { font-size: 11px; color: #94A3B8; text-align: center; padding: 7px; background: #F8FAFC; border-top: 1px dashed #E2E8F0; }
.asst-fb { display: flex; gap: 6px; align-items: center; margin: 2px 0 6px; }
.asst-fb-btn { border: 1px solid #D7E7FA; background: #FFFFFF; border-radius: 999px; padding: 4px 12px; font-size: 13px; cursor: pointer; font-family: inherit; }
.asst-fb-btn:hover { background: #F0FDFA; border-color: #99F6E4; }
.asst-fb-ok { font-size: 12px; color: #0F766E; font-weight: 700; }
.expl-bg { position: fixed; inset: 0; z-index: 1001; background: rgba(15,23,42,.55); display: none; align-items: center; justify-content: center; padding: 18px; }
.expl-bg.open { display: flex; }
.expl-modal { background: #FFFFFF; border-radius: 20px; max-width: 560px; width: 100%; max-height: 86vh; overflow-y: auto; padding: 22px; box-shadow: 0 30px 80px rgba(0,0,0,.35); }
.expl-modal .ex-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 4px; }
.expl-modal .ex-title { font-size: 19px; font-weight: 800; color: #134E4A; }
.expl-modal .ex-close { border: none; background: #F1F5F9; color: #475569; border-radius: 50%; width: 32px; height: 32px; font-size: 14px; cursor: pointer; }
.ex-levels { display: flex; gap: 8px; margin: 14px 0; flex-wrap: wrap; }
.ex-level { flex: 1; min-width: 130px; border: 2px solid #E2E8F0; background: #FFFFFF; border-radius: 14px; padding: 12px; text-align: center; cursor: pointer; font-family: inherit; transition: all .2s; }
.ex-level.on { border-color: #0F766E; background: #F0FDFA; box-shadow: 0 6px 16px rgba(15,118,110,.14); }
.ex-level .lv-ic { font-size: 22px; }
.ex-level .lv-t { font-size: 13px; font-weight: 800; color: #134E4A; margin-top: 4px; }
.ex-explain { background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 12px; padding: 14px; font-size: 14.5px; line-height: 1.9; color: #334155; min-height: 90px; }
.ex-assist-row { margin-top: 14px; text-align: center; }
.asst-modal-bg { position: fixed; inset: 0; z-index: 1002; background: rgba(15,23,42,.55); display: none; align-items: center; justify-content: center; padding: 18px; }
.asst-modal-bg.open { display: flex; }
.asst-modal { background: #FFFFFF; border-radius: 18px; max-width: 480px; width: 100%; padding: 20px; box-shadow: 0 30px 80px rgba(0,0,0,.35); }
.asst-modal-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 12px; color: #134E4A; font-size: 16px; }
.asst-modal-head button { border: none; background: #F1F5F9; color: #475569; border-radius: 50%; width: 30px; height: 30px; font-size: 13px; cursor: pointer; }
.asst-reasons { display: flex; flex-direction: column; gap: 8px; }
.asst-reason { border: 1px solid #E2E8F0; background: #F8FAFC; border-radius: 12px; padding: 11px 14px; font-size: 14px; cursor: pointer; font-family: inherit; text-align: start; color: #334155; }
.asst-reason:hover { border-color: #0F766E; background: #F0FDFA; color: #0F766E; }
@media (max-width: 520px) { .asst-panel { bottom: 82px; right: 10px; left: 10px; max-width: none; width: auto; } [dir="rtl"] .asst-panel { right: 10px; left: 10px; } }
</style>
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
<button class="asst-fab" id="asstFab" onclick="asstToggle()" title="__AST_TITLE__">🤖</button>
<div class="asst-panel" id="asstPanel">
  <div class="asst-head">
    <div><b>🤖 __AST_TITLE__</b><div class="asst-sub">__AST_SUB__</div></div>
    <button onclick="asstToggle()">✕</button>
  </div>
  <div class="asst-body" id="asstBody">
    <div class="asst-msg asst-bot">__AST_GREET__</div>
    <div class="asst-qs" id="asstQs"></div>
  </div>
  <div class="asst-foot">
    <input class="asst-inp" id="asstInput" placeholder="__AST_PH__" onkeydown="if(event.key==='Enter')asstSend()">
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
function asstToggle() {
  var p = document.getElementById('asstPanel');
  var f = document.getElementById('asstFab');
  var open = p.classList.toggle('open');
  f.textContent = open ? '✕' : '🤖';
  if (open) { document.getElementById('asstInput').focus(); }
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
    a.innerHTML = asstTT('emerg_txt') + ' <b>997</b><br><a href="/emergency">' + asstTT('emerg_btn') + '</a>';
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
  var hist = [];
  try { hist = JSON.parse(sessionStorage.getItem('asst_hist') || '[]'); } catch(e) {}
  hist.push({ role: 'user', content: text });
  hist = hist.slice(-8);
  sessionStorage.setItem('asst_hist', JSON.stringify(hist));
  asstTyping(true);
  fetch('/api/assistant', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages: hist, lang: document.documentElement.lang === 'en' ? 'en' : 'ar' }) })
    .then(function(r) { return r.json(); })
    .then(function(d) {
      asstTyping(false);
      if (d.ok) {
        asstReply(d.answer, d.emergency_flags || []);
        hist.push({ role: 'assistant', content: d.answer });
        sessionStorage.setItem('asst_hist', JSON.stringify(hist.slice(-16)));
        if (d.services && d.services.length) asstShowServices(d.services);
      } else {
        asstReply(asstTT('offline'));
      }
    })
    .catch(function() { asstTyping(false); asstReply(asstTT('offline')); });
}
function asstInitQs() {
  var qs = document.getElementById('asstQs');
  var arr = [asstTT('q1'), asstTT('q2'), asstTT('q3'), asstTT('q4')];
  qs.innerHTML = arr.map(function(q) {
    var qq = q.replace(/["'\\\\]/g, '');
    return '<button class="asst-chip" onclick="asstAsk(\\'' + qq + '\\')">' + q + '</button>';
  }).join('');
}
asstInitQs();
</script>
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
        "nav_family": "العائلة",
        "nav_firstaid": "الإسعافات", "nav_tips": "النصائح", "nav_relax": "الاسترخاء",
        "nav_calculators": "الحاسبات الصحية",
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
        "title_calculators": "SymptoSense — الحاسبات الصحية",
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
        "home_tools_t": "🤔 ماذا تحتاج؟",
        "home_tools_sub": "لست متأكداً من أين تبدأ؟ اختر ما يناسب حالتك.",
        "home_tools_1t": "أشعر بأعراض",
        "home_tools_1p": "تحليل الأعراض والحصول على توصيات",
        "home_tools_2t": "لدي فحص دم",
        "home_tools_2p": "قراءة وتحليل نتائج CBC",
        "home_tools_3t": "سؤال عن دواء",
        "home_tools_3p": "معلومات وتحذيرات عن الأدوية",
        "home_tools_4t": "الحالة طارئة",
        "home_tools_4p": "أرقام الطوارئ والإسعاف",
        "home_tools_5t": "أريد حساب مؤشر صحي",
        "home_tools_5p": "BMI والسعرات واحتياج السوائل والسكر",
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
    },
    "en": {
        "nav_home": "Home", "nav_chat": "Symptom Check", "nav_blood": "Blood Tests",
        "nav_meds": "Medications", "nav_emergency": "Emergency", "nav_checkin": "My Tracking",
        "nav_family": "Family",
        "nav_firstaid": "First Aid", "nav_tips": "Tips", "nav_relax": "Relax",
        "nav_calculators": "Health Calculators",
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
        "title_calculators": "SymptoSense — Health Calculators",
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
        "home_tools_t": "🤔 What do you need?",
        "home_tools_sub": "Not sure where to start? Pick what fits your situation.",
        "home_tools_1t": "I have symptoms",
        "home_tools_1p": "Symptom analysis and recommendations",
        "home_tools_2t": "I have a blood test",
        "home_tools_2p": "Read and analyze CBC results",
        "home_tools_3t": "A question about a drug",
        "home_tools_3p": "Drug information and warnings",
        "home_tools_4t": "It's an emergency",
        "home_tools_4p": "Emergency numbers and ambulance",
        "home_tools_5t": "I want to compute a health metric",
        "home_tools_5p": "BMI, calories, fluid needs and blood sugar",
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
        ("/search", "nav_search"), ("/calculators", "nav_calculators"), ("/meds", "nav_meds"), ("/family", "nav_family"), ("/emergency", "nav_emergency"), ("/tips", "nav_tips"),
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
    ast = CT["en" if lang == "en" else "ar"]
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
        .replace("__AST_TITLE__", ast["asst_title"])
        .replace("__AST_SUB__", ast["asst_sub"])
        .replace("__AST_GREET__", ast["asst_greet"])
        .replace("__AST_PH__", ast["asst_ph"])
        .replace("__AST_DISC__", ast["asst_disc"])
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
.lang-tile { position: relative; display: flex; flex-direction: column; align-items: center; gap: 6px; justify-content: center; background: #FFFFFF; border: 2px solid #99F6E4; border-radius: 22px; padding: 30px 22px; font-family: inherit; cursor: pointer; box-shadow: 0 6px 18px rgba(15,118,110,.08); transition: transform .2s ease, background .3s ease, box-shadow .2s ease, border-color .3s ease; }
.lang-tile .fl { font-size: 46px; line-height: 1; margin-bottom: 6px; }
.lang-badge { width: 58px; height: 58px; border-radius: 50%; background: #CCFBF1; color: #0F766E; font-size: 17px; font-weight: 800; letter-spacing: 1px; display: flex; align-items: center; justify-content: center; margin: 0 auto; transition: background .3s ease, color .3s ease; }
.lang-tile .lt { font-size: 23px; font-weight: 800; color: #134E4A; transition: color .3s ease; }
.lang-tile .ld { font-size: 14px; color: #64748B; transition: color .3s ease; }
.lang-tile .ck { position: absolute; top: 12px; right: 14px; width: 26px; height: 26px; border-radius: 50%; background: #FFFFFF; color: #0F766E; font-size: 15px; font-weight: 800; display: flex; align-items: center; justify-content: center; opacity: 0; transform: scale(.5); transition: opacity .2s ease, transform .25s ease, background .3s ease; }
.lang-tile:hover { background: #F0FDFA; border-color: #0F766E; transform: translateY(-3px); box-shadow: 0 12px 28px rgba(15,118,110,.15); }
.lang-tile.sel { background: #0F766E; border-color: #0F766E; box-shadow: 0 14px 34px rgba(15,118,110,.30); }
.lang-tile.sel .lt { color: #FFFFFF; }
.lang-tile.sel .ld { color: #D1FAE5; }
.lang-tile.sel .lang-badge { background: #FFFFFF; color: #0F766E; }
.lang-tile.sel .ck { background: #FFFFFF; color: #0F766E; opacity: 1; transform: scale(1); }
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
  .lang-tile .lt { font-size: 19px; }
}
"""


def welcome_page():
    cur = request.cookies.get("lang") or request.args.get("lang")
    if cur == "en":
        a0, a1, c0, c1, animate = "", " active", "", " sel", "false"
    elif cur == "ar":
        a0, a1, c0, c1, animate = " active", "", " sel", "", "false"
    else:
        a0, a1, c0, c1, animate = " active", "", " sel", "", "true"
    tiles = "".join(
        '<button class="lang-tile__C%s__" onclick="ssGo(\'%s\',this)"><span class="ck">✓</span><span class="fl">%s</span><span class="lt">%s</span><span class="ld">%s</span></button>'
        % (i, code, flag, label, desc)
        for i, (flag, label, code, desc) in enumerate(WELCOME_LANGS)
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
            .replace("lang-tile__C0__", "lang-tile" + c0)
            .replace("lang-tile__C1__", "lang-tile" + c1)
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

    <!--TOOLS-->

    <h2 class="sec-head" id="services">%s</h2>
    <p class="sec-sub">%s</p>
    <div class="features">
      <a class="feature serv" href="/chat"><div class="ic">🩺</div><h3>%s</h3><p>%s</p></a>
      <a class="feature serv" href="/blood"><div class="ic">🩸</div><h3>%s</h3><p>%s</p></a>
      <a class="feature serv" href="/meds"><div class="ic">💊</div><h3>%s</h3><p>%s</p></a>
      <a class="feature serv" href="/emergency"><div class="ic">🏥</div><h3>%s</h3><p>%s</p></a>
      <a class="feature serv" href="/firstaid"><div class="ic">🚨</div><h3>%s</h3><p>%s</p></a>
      <a class="feature serv" href="/calculators"><div class="ic">🧮</div><h3>%s</h3><p>%s</p></a>
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
        t("home_fa_t"), t("home_fa_p"), t("home_calc_t"), t("home_calc_p"), t("home_e_t"), t("home_e_p"),
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
    body = body.replace("<!--TOOLS-->", _tools_html(t))
    return _page(_t("title_landing"), body)


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
        "voice_chip": "🎙️ تحدث بدل الكتابة",
        "voice_btn": "🎙️ تحدث عن أعراضك",
        "voice_speaking": "استمع الآن... تحدث بوضوح عن أعراضك، ثم اضغط إيقاف",
        "voice_stop": "⏹️ إيقاف",
        "voice_cancel": "إلغاء",
        "voice_thinking": "🤔 أفهم كلامك...",
        "voice_no_audio": "لم يُلتقط صوت — حاول مرة أخرى",
        "voice_err": "تعذّر تحويل الصوت: ",
        "voice_none": "لم أتعرّف على أعراض محددة",
        "voice_confirm": "✅ نعم، أكمل",
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
        "voice_chip": "🎙️ Speak instead of typing",
        "voice_btn": "🎙️ Tell me your symptoms",
        "voice_speaking": "Listening... describe your symptoms clearly, then tap Stop",
        "voice_stop": "⏹️ Stop",
        "voice_cancel": "Cancel",
        "voice_thinking": "🤔 Understanding you...",
        "voice_no_audio": "No audio captured — try again",
        "voice_err": "Voice conversion failed: ",
        "voice_none": "No specific symptoms recognized",
        "voice_confirm": "✅ Yes, continue",
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
        <button onclick="startVoice()" id="micBtn" title="__MIC_TITLE__">🎙️</button>
        <button onclick="submitText()">__SEND__</button>
      </div>
    </div>
    <div class="muted" style="text-align:center;margin-top:10px;">__MUTED__</div>
    <div class="blood-banner" id="bloodBanner" style="display:none;"></div>
    <div class="em-overlay" id="emOverlay"></div>
    <div class="voice-overlay" id="voiceOverlay">
      <div class="voice-card">
        <div class="v-mic">🎙️</div>
        <div class="v-title">__VOICE_SP__</div>
        <div style="margin-top:16px;display:flex;gap:10px;justify-content:center;flex-wrap:wrap;">
          <button class="vstop" onclick="stopVoice()">__VOICE_STOP__</button>
          <button class="vcnl" onclick="cancelVoice()">__VOICE_CANCEL__</button>
        </div>
      </div>
    </div>

    <script>
    const T = __T__;
    const LANG = "__LANG__";
    function TT(k) { return T[k] || k; }
    const SYMS = __SYMS__;
    const DURS = __DURS__;
    const SEVS = __SEVS__;
    const CONDS = __CONDS__;
    const REL = __REL__;
    const CLAR = [
      {syms:['👁️ احمرار العيون','👁️ Eye redness'],
       node:{q:['هل تشعر بألم في العين؟','Do you feel pain in the eye?'],
         yes:{q:['هل الألم شديد؟','Is the pain severe?'],
           yes:{safety:['ألم شديد في العين مع احمرار','Severe eye pain with redness']},
           no:{q:['هل لديك إفرازات من العين؟','Do you have eye discharge?'],yes:{end:true},no:{end:true}}},
         no:{q:['هل لديك حكة في العين؟','Do you have itching in the eye?'],yes:{end:true},no:{end:true}}}},
      {syms:['🤕 صداع','🤕 Headache'],
       node:{q:['هل بدأ الصداع بشكل مفاجئ وشديد جداً؟','Did the headache start suddenly and very severely?'],
         yes:{safety:['صداع مفاجئ وشديد — يحتاج تقييماً عاجلاً','Sudden severe headache — needs urgent evaluation']},
         no:{q:['هل لديك حرارة؟','Do you have a fever?'],
           yes:{q:['هل لديك تيبس في الرقبة؟','Do you have neck stiffness?'],
             yes:{safety:['حرارة مع تيبس الرقبة — يحتاج تقييماً عاجلاً','Fever with neck stiffness — needs urgent evaluation']},
             no:{end:true}},
           no:{end:true}}}},
      {syms:['🤒 حمى','🤒 Fever'],
       node:{q:['هل لديك تيبس في الرقبة؟','Do you have neck stiffness?'],
         yes:{safety:['حرارة مع تيبس الرقبة','Fever with neck stiffness']},
         no:{q:['هل تشعر بصعوبة في التنفس؟','Do you have difficulty breathing?'],
           yes:{safety:['حرارة مع صعوبة تنفس','Fever with difficulty breathing']},
           no:{end:true}}}},
      {syms:['😷 سعال','😷 Cough'],
       node:{q:['هل يوجد دم مع السعال؟','Is there blood with the cough?'],
         yes:{safety:['سعال مصحوب بدم','Cough with blood']},
         no:{q:['هل تعاني من ضيق تنفس مع السعال؟','Do you have shortness of breath with the cough?'],
           yes:{safety:['سعال مع ضيق تنفس','Cough with shortness of breath']},
           no:{end:true}}}},
      {syms:['💫 دوار','💫 Dizziness'],
       node:{q:['هل فقدت الوعي أو شعرت بالإغماء؟','Did you lose consciousness or feel like fainting?'],
         yes:{safety:['دوار مع إغماء','Dizziness with fainting']},
         no:{end:true}}},
      {syms:['🫁 ضيق التنفس','🫁 Shortness of breath'],
       node:{q:['هل يزداد ضيق التنفس عند الاستلقاء؟','Does the breathlessness worsen when lying down?'],
         yes:{safety:['ضيق تنفس يزداد عند الاستلقاء','Breathlessness that worsens when lying down']},
         no:{end:true}}},
      {syms:['🦵 ألم في الرجل','🦵 Leg pain'],
       node:{q:['هل هناك تورم أو حرارة في الساق؟','Is there swelling or warmth in the leg?'],
         yes:{safety:['تورم أو حرارة في الساق مع ألم','Swelling or warmth in the leg with pain']},
         no:{end:true}}},
      {syms:['😖 ألم في البطن','😖 Stomach pain'],
       node:{q:['هل الألم شديد جداً؟','Is the pain very severe?'],
         yes:{q:['هل يمنعك الألم من الوقوف أو الحركة؟','Does the pain stop you from standing or moving?'],
           yes:{safety:['ألم بطن شديد يمنع الحركة','Severe stomach pain preventing movement']},
           no:{end:true}},
         no:{end:true}}},
      {syms:['😣 ألم الحلق','😣 Sore throat'],
       node:{q:['هل تجد صعوبة في البلع أو التنفس؟','Do you have trouble swallowing or breathing?'],
         yes:{safety:['صعوبة بلع أو تنفس مع ألم حلق','Difficulty swallowing or breathing with sore throat']},
         no:{end:true}}},
    ];
    document.getElementById('headP').textContent = TT('head_p');
    try { if (localStorage.getItem('symptosense_blood_id')) { const bb = document.getElementById('bloodBanner'); bb.textContent = TT('blood_banner'); bb.style.display = 'block'; } } catch (e) {}
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
      addHtml('<div class="chat-start"><div class="cs-logo">🩺</div><div class="cs-title">' + esc(TT('welcome')) + '</div><div class="cs-sub">' + esc(TT('start_sub')) + '</div><div class="cs-desc">' + esc(TT('start_desc')) + '</div><div class="cs-voice" onclick="startVoice()">🎙️ ' + esc(TT('voice_btn')) + '</div></div>', 'q start');
      askMember();
    }
    let MEMBERS = [];
    function askMember() {
      state.step = 'member';
      fetch('/api/family').then(r => r.json()).then(d => {
        MEMBERS = (d && d.members) || [];
        if (!MEMBERS.length) { state.member = null; askSymptoms(); return; }
        const items = [{label: TT('me_short'), fn:()=>{ state.member = null; add(TT('me_short'),'user'); askSymptoms(); }}];
        MEMBERS.forEach(m => items.push({label: m.name + (m.age ? ' — ' + m.age + ' ' + TT('yrs') : ''), fn:()=>{
          state.member = {id: m.id, name: m.name, age: m.age, gender: m.gender, conditions: m.conditions, medications: m.medications};
          if (m.age) state.age = m.age;
          if (m.gender) state.gender = m.gender;
          add(m.name + (m.age ? ' — ' + m.age + ' ' + TT('yrs') : ''), 'user');
          askSymptoms();
        }}));
        addQ('👥 ' + TT('for_whom'));
        showOpts(items);
      }).catch(() => { state.member = null; askSymptoms(); });
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
      if (state.member && state.member.age) askGender();
      else askAge();
    }

    // ---------------- Voice assistant ----------------
    let voiceRec = null, voiceChunks = [];
    function startVoice() {
      if (state.step === 'followup') { add(TT('voice_manual'), 'bot'); return; }
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) { add(TT('no_mic'), 'bot'); return; }
      clearOpts();
      addQ('🎙️ ' + TT('voice_speaking'));
      const ov = document.getElementById('voiceOverlay');
      ov.style.display = 'flex';
      navigator.mediaDevices.getUserMedia({audio:true}).then(function(stream){
        voiceChunks = [];
        voiceRec = new MediaRecorder(stream);
        voiceRec.ondataavailable = function(e){ if (e.data && e.data.size) voiceChunks.push(e.data); };
        voiceRec.onstop = sendVoice;
        voiceRec.start();
        setTimeout(function(){ if (voiceRec && voiceRec.state === 'recording') voiceRec.stop(); }, 15000);
      }).catch(function(){
        ov.style.display = 'none';
        add(TT('no_mic'), 'bot');
        askSymptoms();
      });
    }
    function stopVoice() { if (voiceRec && voiceRec.state === 'recording') voiceRec.stop(); }
    function cancelVoice() { if (voiceRec && voiceRec.state === 'recording') voiceRec.stop(); hideVoice(); }
    function hideVoice() { document.getElementById('voiceOverlay').style.display = 'none'; voiceRec = null; }
    async function sendVoice() {
      const type = (voiceRec && voiceRec.mimeType) || 'audio/webm';
      const blob = new Blob(voiceChunks, {type: type});
      voiceRec = null;
      hideVoice();
      if (!blob.size) { add(TT('voice_no_audio'), 'bot'); return; }
      add(TT('voice_thinking'), 'bot');
      const fd = new FormData();
      fd.append('file', blob, 'voice.webm');
      try {
        const r = await fetch('/api/voice', {method:'POST', body: fd});
        const d = await r.json();
        if (!d.ok) { add(TT('voice_err') + (d.error||''), 'bot'); return; }
        showParsed(d.text, d.parsed);
      } catch(e) { add(TT('conn_err'), 'bot'); }
    }
    function showParsed(text, parsed) {
      const symStr = parsed.symptoms && parsed.symptoms.length ? parsed.symptoms.join(LANG==='en' ? ', ' : '، ') : TT('voice_none');
      let h = '<div class="res-sec">🎙️ <i>"' + esc(text) + '"</i></div>';
      h += '<div class="res-sec"><b>' + esc(TT('voice_syms')) + '</b> ' + esc(symStr) + '</div>';
      if (parsed.duration) h += '<div class="res-sec"><b>' + esc(TT('duration')) + '</b> ' + esc(parsed.duration) + '</div>';
      if (parsed.severity) h += '<div class="res-sec"><b>' + esc(TT('severity')) + '</b> ' + esc(parsed.severity) + '/5</div>';
      h += '<div class="muted">' + esc(TT('voice_confirm_q')) + '</div>';
      addHtml(h, 'bot');
      showOpts([
        {label:TT('voice_confirm'), fn:()=>{ voiceConfirm(parsed); }},
        {label:TT('voice_retry'), fn:()=>{ startVoice(); }},
        {label:TT('voice_edit'), fn:()=>{ add(TT('voice_manual'),'bot'); askSymptoms(); }}
      ]);
    }
    function voiceConfirm(parsed) {
      if (parsed.symptoms && parsed.symptoms.length) {
        state.symptoms = parsed.symptoms;
        add(TT('chosen') + parsed.symptoms.join(LANG==='en' ? ', ' : '، '), 'user');
      }
      if (parsed.duration) state.duration = parsed.duration;
      if (parsed.severity) state.severity = parsed.severity;
      clearOpts();
      if (state.member && state.member.age) askGender();
      else askAge();
    }

    // ---------------- Missing-symptom clarification ----------------
    let clarQueue = [], clarIndex = 0;
    function startClarify() {
      clarQueue = [];
      clarIndex = 0;
      (state.symptoms || []).forEach(function(s){
        for (var i = 0; i < CLAR.length; i++) {
          if (CLAR[i].syms.indexOf(s) !== -1) { clarQueue.push(CLAR[i].node); break; }
        }
      });
      nextClarNode();
    }
    function nextClarNode() {
      if (clarIndex < clarQueue.length) walkClarNode(clarQueue[clarIndex++]);
      else runAnalysis();
    }
    function walkClarNode(node) {
      if (!node) { nextClarNode(); return; }
      if (node.safety) {
        const label = LANG === 'en' ? node.safety[1] : node.safety[0];
        addHtml('<div class="warn">🚨 ' + esc(label) + '</div>', 'bot');
        showEmergency({emergency:true, emergency_flags:[label], _clar:true});
        return;
      }
      if (node.q) {
        const q = LANG === 'en' ? node.q[1] : node.q[0];
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
      state.step = 'age';
      addQ(TT('age'));
      showText(TT('age_ph'));
    }
    function askGender() {
      if (state.gender) { if (state.duration) askSeverity(); else askDuration(); return; }
      state.step = 'gender';
      addQ(TT('gender'));
      showOpts([
        {label:TT('male'), fn:()=>{ state.gender='m'; add(TT('male'),'user'); if (state.duration) askSeverity(); else askDuration(); }},
        {label:TT('female'), fn:()=>{ state.gender='f'; add(TT('female'),'user'); if (state.duration) askSeverity(); else askDuration(); }}
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
      items.push({label:TT('voice_chip'), cls:'voice-opt', fn:()=>{ startVoice(); }});
      showOpts(items);
      renderRelated();
      appendStartBtn();
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
      if (state.duration) { askSeverity(); return; }
      state.step = 'duration';
      addQ(TT('duration'));
      showOpts(DURS.map(d=>({label:d, fn:()=>{ state.duration=d; add(d,'user'); askSeverity(); }})));
    }
    function askSeverity() {
      if (state.severity) { askConditions(); return; }
      state.step = 'severity';
      addQ(TT('severity'));
      showOpts(SEVS.map(([v,l])=>({label:l, fn:()=>{ state.severity=v; add(l,'user'); askConditions(); }})));
    }
    function askConditions() {
      if (state.conditions && state.member && state.member.conditions) { askMeds(); return; }
      state.step = 'conditions';
      addQ(G(TT('conditions_f'), TT('conditions_m')));
      const items = CONDS.map(c=>({label:c, fn:()=>{ state.conditions=c; add(c,'user'); askMeds(); }}));
      items.push({label:TT('other_diseases'), fn:()=>{ addQ(G(TT('other_diseases_f'), TT('other_diseases_m'))); showText(TT('cond_ph')); }});
      showOpts(items);
    }
    function askMeds() {
      if (state.medications && state.member && state.member.medications) { askNotes(); return; }
      state.step = 'medications';
      addQ(G(TT('meds_f'), TT('meds_m')));
      showOpts([{label:TT('skip'), fn:()=>{ add(TT('skip'),'user'); state.medications=''; askNotes(); }}]);
      showText(TT('meds_ph'), true);
    }
    function askNotes() {
      state.step = 'notes';
      addQ(G(TT('notes_f'), TT('notes_m')));
      showOpts([{label:TT('skip'), fn:()=>{ add(TT('skip'),'user'); state.notes=''; startClarify(); }}]);
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
        state.notes = v; startClarify();
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
        payload.member_id = (state.member && state.member.id) ? state.member.id : 0;
        try { const b = localStorage.getItem('symptosense_blood_id'); if (b) payload.blood_id = parseInt(b) || null; } catch (e) {}
        const r = await fetch('/api/analyze', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify(payload)
        });
        const d = await r.json();
        if (d.ok) { if (d.emergency) { showEmergency(d); } else { renderResult(d); } }
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
    function closeEmergency() {
      document.getElementById('emOverlay').style.display = 'none';
      if (lastResult && lastResult._clar) { lastResult = null; nextClarNode(); return; }
      if (lastResult) renderResult(lastResult);
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
      if (state.member && state.member.name) h += '<div class="res-person">' + esc(TT('person_badge')) + esc(state.member.name) + '</div>';
      h += '<div class="res-urg"><span class="pill2 ' + pcls + '"><span class="urg-lbl">' + uEmoji + ' ' + esc(TT('urg_label')) + '</span><span class="urg-val">' + esc(uVal) + '</span></span></div>';
      if (d.triage_label) h += '<div class="res-triage">' + esc(d.triage_label) + '</div>';
      if (d.triage_reason) h += '<div class="triage-why"><b>' + esc(TT('triage_why')) + '</b><div style="margin-top:6px;text-align:right;">' + esc(d.triage_reason).replace(/\\n/g, '<br>') + '</div></div>';
      if (d.rule_forced_high) h += '<div class="warn" style="margin:8px 0;">' + TT('forced_high') + '</div>';
      if (d.low_confidence) h += '<div class="muted" style="text-align:center;margin-bottom:8px;">' + TT('low_conf') + '</div>';
      h += '<div class="res-note"><b>' + esc(TT('assessment_label')) + '</b> ' + esc(d.personal_note) + '</div>';
      h += '<div class="res-disc">' + esc(TT('result_disclaimer')) + '</div>';
      h += '<div class="res-sim-toggle"><button id="simBtn" class="opt" onclick="setSim(1)">👤 ' + esc(TT('sim_btn')) + '</button><button id="detBtn" class="opt" style="display:none;" onclick="setSim(0)">🔬 ' + esc(TT('det_btn')) + '</button></div>';
      h += '<div id="resSimple" style="display:none;" class="res-sec sim-box">' + esc(d.simple_explanation || TT('sim_fallback')) + '</div>';
      h += '<div id="resDetail">';

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
          const nm = NAME(p, 'name_ar', 'name_en');
          h += '<div class="ml-row"><span>' + esc(nm) + ' <button class="bl-explain" onclick="openExplain(\\'' + esc(nm).replace(/["\'\\\\]/g, '') + '\\')">✨ ' + esc(TT('ml_explain')) + '</button></span><b>' + pct + '%</b></div>';
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
        .replace("__REL__", json.dumps(_related_map(ar), ensure_ascii=False))
        .replace("__SPEAK_ON__", CHAT["ar" if ar else "en"]["speak_on"])
        .replace("__SPEAK_TITLE__", CHAT["ar" if ar else "en"]["speak_title"])
        .replace("__INPUT_PH__", CHAT["ar" if ar else "en"]["input_ph"])
        .replace("__MIC_TITLE__", CHAT["ar" if ar else "en"]["mic_title"])
        .replace("__SEND__", CHAT["ar" if ar else "en"]["send"])
        .replace("__MUTED__", CHAT["ar" if ar else "en"]["muted"])
        .replace("__VOICE_SP__", CHAT["ar" if ar else "en"]["voice_speaking"])
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
        "asst_sub": "مساعد ذكي داخل الموقع",
        "asst_ph": "اكتب سؤالك...",
        "asst_greet": "أهلاً! أنا مساعد SymptoSense 🤖 اسألني عن الأعراض، الأدوية، فحص الدم، أو أفراد عائلتك، وسأوجّهك للخدمة المناسبة.",
        "asst_q1": "أشعر بألم في رأسي منذ يومين",
        "asst_q2": "كيف أرفع فحص الدم؟",
        "asst_q3": "ما هي خدمة صحة العائلة؟",
        "asst_q4": "كيف أتتبع أدويتي؟",
        "asst_emerg_txt": "⚠️ تظهر عليك علامات تستدعي الطوارئ. اتصل بالإسعاف فوراً:",
        "asst_emerg_btn": "صفحة الطوارئ ←",
        "asst_offline": "عذراً، لا أستطيع الرد الآن. جرّب صفحة فحص الأعراض أو راجع الطبيب عند الحاجة.",
        "asst_disc": "توعية فقط — ليس تشخيصاً نهائياً.",
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
        "calc_sub": "احسب مؤشرات صحية شائعة واحصل على نتائج وتقديرات مبسطة.",
        "calc_now": "احسب الآن",
        "calc_back": "↩ العودة للحاسبات",
        "calc_follow": "💡 هل تريد فهم النتيجة أكثر؟",
        "calc_ask": "🤖 اسأل المساعد الذكي",
        "calc_alert_t": "🚨 تنبيه",
        "calc_alert_msg": "النتيجة التي أدخلتها قد تستدعي تقييمًا طبيًا، خصوصًا إذا كانت لديك أعراض شديدة.",
        "calc_alert_high": "🚨 القراءة مرتفعة جدًا — يُنصح بالحصول على تقييم طبي عاجل، وإذا كانت مصحوبة بأعراض شديدة فاتصل بالإسعاف 997 فورًا.",
        "calc_alert_low": "🚨 القراءة منخفضة جدًا — إذا كانت مصحوبة بأعراض (رجفة، دوخة، عرق، تشوش) فتناول مصدر سكر سريع واطلب تقييمًا طبيًا، وإذا تدهورت الحالة فاتصل بالإسعاف 997.",
        "calc_em_btn": "🚨 إرشادات الطوارئ",
        "calc_disc": "⚠️ تنبيه صحي: جميع النتائج المعروضة في هذا القسم لأغراض التثقيف والحساب التقريبي فقط، ولا تُعد تشخيصًا طبيًا أو بديلًا عن استشارة الطبيب. لا تستخدم النتائج لتغيير الأدوية أو الجرعات أو خطة العلاج دون استشارة مختص.",
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
        "calc_sug_desc": "أدخل قراءة السكر لمعرفة تصنيفها بشكل عام.",
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
        "asst_sub": "On-site smart assistant",
        "asst_ph": "Type your question...",
        "asst_greet": "Hi! I'm SymptoSense's assistant 🤖 Ask me about symptoms, medications, blood tests, or family members, and I'll point you to the right service.",
        "asst_q1": "I've had a headache for two days",
        "asst_q2": "How do I upload a blood test?",
        "asst_q3": "What is the Family Health Hub?",
        "asst_q4": "How can I track my medications?",
        "asst_emerg_txt": "⚠️ You may be showing emergency signs. Call emergency services now:",
        "asst_emerg_btn": "Emergency page ←",
        "asst_offline": "Sorry, I can't reply right now. Try the symptom analysis page or see a doctor if needed.",
        "asst_disc": "Awareness only — not a final diagnosis.",
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
        "calc_sub": "Compute common health indicators and get simple results and estimates.",
        "calc_now": "Calculate now",
        "calc_back": "↩ Back to calculators",
        "calc_follow": "💡 Want to understand your result more?",
        "calc_ask": "🤖 Ask the smart assistant",
        "calc_alert_t": "🚨 Alert",
        "calc_alert_msg": "The result you entered may warrant medical evaluation, especially if you have severe symptoms.",
        "calc_alert_high": "🚨 The reading is very high — urgent medical evaluation is advised; if it's accompanied by severe symptoms, call emergency services 997 immediately.",
        "calc_alert_low": "🚨 The reading is very low — if accompanied by symptoms (shaking, dizziness, sweating, confusion), have a fast-acting sugar source and seek medical evaluation; if it worsens, call 997.",
        "calc_em_btn": "🚨 Emergency guide",
        "calc_disc": "⚠️ Health notice: all results shown in this section are for education and rough estimation only. They are not a medical diagnosis or a substitute for a doctor's consultation. Do not use the results to change medications, doses, or a treatment plan without a specialist.",
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
        "calc_sug_desc": "Enter a glucose reading to understand its general classification.",
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
      lr.innerHTML = '<div style="display:inline-block;padding:10px 18px;border-radius:12px;background:#F0FDFA;border:1px solid #99F6E4;color:#115E59;font-weight:700;">✅ ' + esc(TT('blood_linked')) + '</div>' +
        '<div style="margin-top:10px;"><a class="btn pri" href="/chat">' + esc(TT('blood_goto_chat')) + '</a></div>';
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
      <label class="lbl">__FAMPERSON__</label>
      <div id="membChips" style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;"></div>
      <div class="rc-title">__REMLISTH__</div>
      <div id="planList" style="margin-top:12px;"></div>
      <div style="margin-top:16px;border-top:1px dashed #CBD5E1;padding-top:14px;">
        <div class="grid2">
          <div><label class="lbl">__RNAME__</label><input class="inp" id="remName" placeholder="__RNAMEPH__"></div>
          <div><label class="lbl">__PDOSE__</label><input class="inp" id="pDose" placeholder="500mg"></div>
        </div>
        <div class="grid2">
          <div><label class="lbl">__RTIMES__</label><input class="inp" id="remTimes" placeholder="__RTIMESPH__"></div>
          <div><label class="lbl">__PDAYS__</label><input class="inp" id="pDays" type="number" min="1" placeholder="7"></div>
        </div>
        <div style="margin-top:12px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
          <button class="btn" onclick="addReminder()">__RSAVE__</button>
          <span id="remMsg" style="font-weight:600;color:#1677E8;"></span>
        </div>
      </div>
    </div>
    <div class="card" style="margin-top:16px;">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
        <b style="color:#134E4A;">__WADH__</b>
        <b style="color:#0F766E;" id="adhVal">—</b>
      </div>
      <div class="adh-bar"><div class="adh-fill" id="adhFill" style="width:0%;"></div></div>
    </div>
    <div class="warn">__MWARN__</div>
    <div class="warn" style="margin-top:16px;">__MWARN2__</div>
    <script>
    const T = __PT__;
    function TT(k) { return T[k] || k; }
    function esc(s) { const div=document.createElement('div'); div.textContent=s||''; return div.innerHTML; }
    const EMO = {'me':'👤','mother':'👩','father':'👨','daughter':'👧','son':'👦','grandparent':'👵','other':'🧑'};
    let selMember = 0;
    let members = [];
    function todayStr() { const d=new Date(); return d.getFullYear()+'-'+('0'+(d.getMonth()+1)).slice(-2)+'-'+('0'+d.getDate()).slice(-2); }
    function renderMemb() {
      const box = document.getElementById('membChips');
      let chips = '<span class="fam-chip' + (selMember===0?' sel':'') + '" onclick="pickMemb(0)">' + TT('me_short') + '</span>';
      members.forEach(m => {
        chips += '<span class="fam-chip' + (m.id===selMember?' sel':'') + '" onclick="pickMemb(' + m.id + ')">' + (EMO[m.relation]||'🧑') + ' ' + esc(m.name) + '</span>';
      });
      box.innerHTML = chips;
    }
    function pickMemb(id) { selMember = id; renderMemb(); loadPlans(); loadAdh(); }
    function loadMemb() {
      fetch('/api/family').then(r=>r.json()).then(d=>{
        if (d.ok) members = d.members || [];
        renderMemb();
      }).catch(()=>{});
    }
    function loadPlans() {
      fetch('/api/meds/today').then(r=>r.json()).then(d=>{
        const box = document.getElementById('planList');
        const mine = (d.plans||[]).filter(p => p.member_id === selMember);
        if (!mine.length) { box.innerHTML = '<div class="muted">' + TT('no_rem') + '</div>'; return; }
        let h = '<table class="tbl"><tr><th>' + TT('rem_name') + '</th><th>' + TT('rem_times') + '</th><th></th></tr>';
        mine.forEach(p => {
          h += '<tr><td><b>💊 ' + esc(p.med_name) + (p.dose ? ' <span class="muted">(' + esc(p.dose) + ')</span>' : '') + '</b></td><td><div style="display:flex;flex-direction:column;gap:4px;">';
          p.times.forEach(tm => {
            const st = p.status[tm] || '';
            h += '<span style="display:flex;align-items:center;gap:8px;"><b style="color:#0F766E;">🕐 ' + tm + '</b>' +
                 (st ? '<span class="mini-btn done">' + TT('fam_today_logged') + '</span>'
                     : '<span class="mini-btn tk" onclick="logMed(' + p.id + ',\\'' + tm + '\\',\\'taken\\')">' + TT('fam_take') + '</span>' +
                       '<span class="mini-btn sk" onclick="logMed(' + p.id + ',\\'' + tm + '\\',\\'skipped\\')">' + TT('fam_skip') + '</span>' +
                       '<span class="mini-btn lt" onclick="logMed(' + p.id + ',\\'' + tm + '\\',\\'deferred\\')">' + TT('fam_later') + '</span>') +
                 '</span>';
          });
          h += '</div></td><td><button class="opt" onclick="delPlan(' + p.id + ')">' + TT('del') + '</button></td></tr>';
        });
        h += '</table>';
        box.innerHTML = h;
      }).catch(()=>{});
    }
    function logMed(pid, tm, st) {
      fetch('/api/meds/log', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({
        plan_id: pid, time: tm, status: st, member_id: selMember, date: todayStr()
      })}).then(r=>r.json()).then(()=>{ loadPlans(); loadAdh(); });
    }
    function delPlan(pid) {
      fetch('/api/meds/plan/' + pid, {method:'DELETE'}).then(r=>r.json()).then(()=>{ loadPlans(); });
    }
    function loadAdh() {
      fetch('/api/meds/weekly?member=' + selMember).then(r=>r.json()).then(d=>{
        const v = (d.ok && d.percent !== null && d.percent !== undefined) ? d.percent : null;
        document.getElementById('adhVal').textContent = (v === null ? TT('fam_no_adherence') : TT('fam_week_adh').replace('%s', v));
        document.getElementById('adhFill').style.width = (v === null ? 0 : Math.min(100, v)) + '%';
      }).catch(()=>{});
    }
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
    function addReminder() {
      const name = document.getElementById('remName').value.trim();
      const tval = document.getElementById('remTimes').value.trim();
      const box = document.getElementById('remMsg');
      if (!name) { box.textContent = TT('name_first'); return; }
      const times = tval.split(/[,،\\s]+/).filter(Boolean);
      if (!times.length) { box.textContent = TT('times_ph_err'); return; }
      fetch('/api/meds/plan', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({
        member_id: selMember, med_name: name, dose: document.getElementById('pDose').value.trim(),
        times: times, days: document.getElementById('pDays').value || null
      })}).then(r=>r.json()).then(d=>{
        if (!d.ok) { box.textContent = TT('fam_err') + (d.error||''); box.style.color='#B91C1C'; return; }
        box.textContent = TT('saved'); box.style.color = '#1677E8';
        document.getElementById('remName').value=''; document.getElementById('remTimes').value=''; document.getElementById('pDose').value=''; document.getElementById('pDays').value='';
        loadPlans();
        if (!('Notification' in window)) { box.textContent = TT('no_notif'); return; }
        Notification.requestPermission().then(perm => {
          if (perm !== 'granted') { box.textContent = TT('enable_notif'); }
        });
      });
    }
    function checkTimes() {
      const now = new Date();
      const cur = ('0' + now.getHours()).slice(-2) + ':' + ('0' + now.getMinutes()).slice(-2);
      fetch('/api/meds/today').then(r=>r.json()).then(d=>{
        const lastKey = 'ss_last_notif_' + todayStr();
        const sent = {};
        try { (localStorage.getItem(lastKey)||'').split(',').forEach(t=>sent[t]=1); } catch(e) {}
        (d.plans||[]).forEach(p => {
          p.times.forEach(tm => {
            if (tm === cur && !sent[cur] && p.status[tm]) {
              sent[cur] = 1;
              localStorage.setItem(lastKey, Object.keys(sent).join(','));
              if (('Notification' in window) && Notification.permission === 'granted') {
                new Notification(TT('rem_notif_t'), { body: TT('rem_notif_b') + p.med_name + ' — ' + (p.member_name || '') });
              }
            }
          });
        });
      }).catch(()=>{});
    }
    setInterval(checkTimes, 30000);
    loadMemb();
    loadPlans();
    loadAdh();
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
        ("__FAMPERSON__", t["fam_person"]), ("__PDOSE__", t["fam_plan_dose"]),
        ("__PDAYS__", t["fam_plan_days"]), ("__WADH__", t["fam_week_adh"]),
    ]
    for k, v in repl:
        body = body.replace(k, v)
    return _page(_t("title_meds"), body, extra_css=FAM_CSS)


# ---------------------------------------------------------------- family health hub
FAM_CSS = """
.fam-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 14px; margin-top: 16px; }
.fam-card { background: #FFFFFF; border: 1px solid #D7E7FA; border-radius: 18px; padding: 18px; cursor: pointer; transition: transform .15s ease, box-shadow .15s ease; text-align: center; }
.fam-card:hover { transform: translateY(-3px); box-shadow: 0 12px 28px rgba(11,46,107,.12); }
.fam-av { width: 58px; height: 58px; margin: 0 auto 10px; border-radius: 50%; background: #F0FDFA; border: 2px solid #99F6E4; display: flex; align-items: center; justify-content: center; font-size: 28px; }
.fam-name { font-weight: 800; font-size: 16px; color: #134E4A; }
.fam-meta { font-size: 13px; color: #64748B; margin-top: 4px; }
.fam-stat { display: flex; justify-content: center; gap: 14px; margin-top: 10px; font-size: 12px; color: #475569; }
.fam-stat b { color: #0F766E; }
.fam-form { background: #FFFFFF; border: 1px solid #D7E7FA; border-radius: 18px; padding: 20px; margin-top: 16px; }
.fam-rel-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
.fam-chip { padding: 8px 14px; border-radius: 999px; border: 1.5px solid #14B8A6; background: #FFFFFF; color: #0F766E; font-size: 13px; font-weight: 700; cursor: pointer; }
.fam-chip.sel { background: #0F766E; color: #FFFFFF; }
.tl-item { display: flex; gap: 12px; align-items: flex-start; padding: 10px 0; border-bottom: 1px dashed #E2E8F0; font-size: 14px; }
.tl-dot { width: 34px; height: 34px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 17px; background: #F0FDFA; flex: 0 0 34px; }
.tl-date { color: #94A3B8; font-size: 12px; }
.tl-type { color: #475569; }
.tl-type b { color: #0B2E6B; }
.mplan-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 12px; padding: 10px 12px; margin-top: 8px; }
.mplan-time { font-weight: 800; color: #0F766E; min-width: 52px; }
.mplan-name { font-weight: 700; color: #1e293b; }
.mplan-status { display: flex; gap: 6px; flex-wrap: wrap; }
.mini-btn { border: 1px solid #CBD5E1; background: #FFFFFF; border-radius: 8px; padding: 5px 10px; font-size: 12px; font-weight: 700; cursor: pointer; }
.mini-btn.tk { border-color: #86EFAC; color: #166534; }
.mini-btn.sk { border-color: #FECACA; color: #991B1B; }
.mini-btn.lt { border-color: #FDE68A; color: #92400E; }
.mini-btn.done { opacity: .55; pointer-events: none; }
.adh-bar { height: 8px; background: #E2E8F0; border-radius: 8px; overflow: hidden; margin-top: 6px; }
.adh-fill { height: 100%; background: #14B8A6; border-radius: 8px; }
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
      <h3 style="color:#134E4A;">__ADD__</h3>
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
        <span id="famMsg" style="font-weight:700;color:#0F766E;"></span>
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
        if (!d.ok) { msg.textContent = TT('fam_err') + (d.error||''); msg.style.color='#B91C1C'; return; }
        msg.textContent = TT('fam_saved'); msg.style.color = '#0F766E';
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
    uid = _user_id()
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
            <h2 style="color:#134E4A;">__NAME__</h2>
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
        <div class="card" style="background:#F8FAFC;">
          <b>__LASTANA__</b>
          <div style="margin-top:6px;font-size:14px;color:#475569;">__ANA_TXT__</div>
        </div>
        <div class="card" style="background:#F8FAFC;">
          <b>__LASTCBC__</b>
          <div style="margin-top:6px;font-size:14px;color:#475569;">__CBC_TXT__</div>
        </div>
      </div>
      <div class="card" style="background:#F8FAFC;margin-top:12px;">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
          <b>__ADH__</b>
          <b style="color:#0F766E;">__ADH_PCT__</b>
        </div>
        <div class="adh-bar"><div class="adh-fill" style="width:__ADH_W__%;"></div></div>
      </div>
      <div style="margin-top:10px;font-size:13px;color:#475569;">
        <b>__MEDSREG__:</b> <span id="medsTxt">__MEDS_TXT__</span>
      </div>
    </div>

    <div class="card" style="margin-top:14px;">
      <h3 style="color:#134E4A;">__PLANT__</h3>
      <p class="muted">__PLANSUB__</p>
      <div id="planList" style="margin-top:12px;"><div class="muted">...</div></div>
      <div style="margin-top:16px;border-top:1px dashed #CBD5E1;padding-top:14px;">
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
          <span id="planMsg" style="font-weight:700;color:#0F766E;"></span>
        </div>
      </div>
    </div>

    <div class="card" style="margin-top:14px;">
      <h3 style="color:#134E4A;">__TL__</h3>
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
        msg.textContent = TT('fam_saved'); msg.style.color = '#0F766E';
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
.sea-box { display: flex; align-items: center; gap: 10px; background: #FFFFFF; border: 2px solid #0F766E; border-radius: 999px; padding: 7px 8px 7px 18px; box-shadow: 0 10px 30px rgba(15,118,110,.14); transition: box-shadow .25s ease, border-color .25s ease; }
.sea-box:focus-within { box-shadow: 0 14px 38px rgba(15,118,110,.22); border-color: #134E4A; }
.sea-box .sea-ic { font-size: 20px; color: #0F766E; }
.sea-box input { flex: 1; border: none; outline: none; font-size: 16px; font-family: inherit; padding: 11px 4px; background: transparent; color: #134E4A; min-width: 0; }
.sea-box input::placeholder { color: #94A3B8; }
.sea-box .sea-btn { border: none; background: linear-gradient(135deg, #0F766E, #134E4A); color: #FFF; font-weight: 800; font-size: 15px; padding: 12px 26px; border-radius: 999px; cursor: pointer; font-family: inherit; white-space: nowrap; }
.sea-box .sea-btn:hover { filter: brightness(1.12); }
.sea-hint { text-align: center; color: #64748B; font-size: 13px; margin-top: 12px; }
.sea-chips { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-top: 16px; }
.sea-chip { border: 1px solid #99F6E4; background: #F0FDFA; color: #0F766E; border-radius: 999px; padding: 8px 14px; font-size: 13.5px; font-weight: 700; cursor: pointer; font-family: inherit; transition: background .2s; }
.sea-chip:hover { background: #CCFBF1; }
.sea-result { margin-top: 22px; background: #FFFFFF; border: 1px solid #D7E7FA; border-radius: 20px; padding: 22px; box-shadow: 0 8px 24px rgba(11,46,107,.08); }
.sea-result .sr-head { display: flex; align-items: center; gap: 12px; border-bottom: 1px dashed #CBD5E1; padding-bottom: 12px; margin-bottom: 14px; }
.sea-result .sr-emoji { font-size: 34px; }
.sea-result .sr-title { font-size: 21px; font-weight: 800; color: #134E4A; }
.sea-result .sr-cat { display: inline-block; background: #F0FDFA; color: #0F766E; border: 1px solid #99F6E4; font-size: 11.5px; font-weight: 700; border-radius: 999px; padding: 3px 10px; margin-top: 4px; }
.sea-result .sr-sec { font-size: 14.5px; line-height: 1.9; color: #334155; margin-bottom: 12px; }
.sea-result .sr-sec b { color: #0F766E; display: block; margin-bottom: 4px; }
.sea-result .sr-causes { list-style: none; padding: 0; margin: 0 0 14px; }
.sea-result .sr-causes li { padding: 6px 22px 6px 0; position: relative; font-size: 14px; color: #334155; line-height: 1.7; }
.sea-result .sr-causes li::before { content: '•'; position: absolute; right: 4px; color: #0F766E; font-weight: 900; }
[dir="ltr"] .sea-result .sr-causes li { padding: 6px 0 6px 22px; }
[dir="ltr"] .sea-result .sr-causes li::before { right: auto; left: 4px; }
.sea-worry { background: #FEF2F2; border: 1px solid #FECACA; color: #7F1D1D; border-radius: 12px; padding: 12px 14px; font-size: 14px; line-height: 1.8; margin-bottom: 10px; }
.sea-doctor { background: #F0FDFA; border: 1px solid #99F6E4; color: #115E59; border-radius: 12px; padding: 12px 14px; font-size: 14px; line-height: 1.8; margin-bottom: 14px; }
.sea-actions { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 6px; }
.sea-actions .btn.sea-assist { background: linear-gradient(135deg, #1769E0, #0F766E); }
.sea-no { text-align: center; color: #64748B; margin-top: 22px; font-size: 14px; }
.sea-disc { background: #FFF7ED; border: 1px dashed #FDBA74; color: #9A3412; border-radius: 10px; padding: 10px 12px; font-size: 12.5px; line-height: 1.7; margin-top: 16px; text-align: center; }
@media (max-width: 560px) { .sea-box { flex-wrap: wrap; border-radius: 22px; padding: 12px; } .sea-box .sea-btn { width: 100%; } }
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
        }).catch(function() { box.innerHTML = '<div class="warn">' + esc(sT('sea_err')) + '</div>'; });
    }
    function catTxt(c) {
      const m = { symptom: 'sea_cat_symp', test: 'sea_cat_test', term: 'sea_cat_term', medication: 'sea_cat_med' };
      return sT(m[c] || 'sea_cat_term');
    }
    function renderResult(r) {
      const box = document.getElementById('seaRes');
      let h = '<div class="sea-result">';
      h += '<div class="sr-head"><span class="sr-emoji">' + esc(r.emoji || '🩺') + '</span><div><div class="sr-title">' + esc(r.title) + '</div><span class="sr-cat">' + esc(catTxt(r.category)) + '</span></div></div>';
      h += '<div class="sr-sec"><b>' + esc(sT('sea_what')) + '</b>' + esc(r.what) + '</div>';
      if (r.causes && r.causes.length) {
        h += '<b style="color:#0F766E;">' + esc(r.causes_label || sT('sea_causes')) + '</b><ul class="sr-causes">';
        r.causes.forEach(function(c) { h += '<li>' + esc(c) + '</li>'; });
        h += '</ul>';
      }
      if (r.worry) h += '<div class="sea-worry">🚨 <b>' + esc(sT('sea_worry')) + '</b><br>' + esc(r.worry) + '</div>';
      if (r.doctor) h += '<div class="sea-doctor">🩺 <b>' + esc(sT('sea_doctor')) + '</b><br>' + esc(r.doctor) + '</div>';
      h += '<div class="sea-actions">' +
        '<button class="btn" onclick="openExplain(\\'' + esc(r.title).replace(/["\'\\\\]/g, '') + '\\')">✨ ' + esc(sT('sea_explain')) + '</button>' +
        '<button class="btn pri sea-assist" onclick="askAboutTopic()">🤖 ' + esc(sT('sea_ask_assist')) + '</button>' +
        '</div>';
      h += '</div>';
      h += '<div class="sea-disc">' + esc(sT('sea_disc')) + '</div>';
      box.innerHTML = h;
      curTopic = r.title;
    }
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
    return _page(_t("title_search"), body, extra_css=SEARCH_CSS)


# ---------------------------------------------------------------- health calculators
CALC_CSS = """
.calc-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(255px, 1fr)); gap: 16px; margin-top: 4px; }
.calc-card { background: #FFFFFF; border: 1.5px solid #D7E7FA; border-radius: 18px; padding: 22px 18px; cursor: pointer; text-align: center; font-family: inherit; transition: transform .14s ease, box-shadow .14s ease, border-color .14s ease; }
.calc-card:hover { transform: translateY(-4px); box-shadow: 0 14px 30px rgba(22,119,232,.16); border-color: #1769E0; }
.calc-card .cc-ic { font-size: 42px; }
.calc-card h3 { font-size: 17px; font-weight: 800; color: #0B2E6B; margin: 10px 0 6px; }
.calc-card p { font-size: 13.5px; color: #475569; line-height: 1.8; margin-bottom: 14px; }
.calc-card .cc-btn { display: inline-block; background: linear-gradient(135deg, #1677E8, #0F766E); color: #FFF; font-weight: 800; font-size: 13.5px; padding: 10px 22px; border-radius: 999px; }
.calc-pane { display: none; }
.calc-pane.open { display: block; animation: fadeIn .35s ease both; }
.calc-back { margin-bottom: 12px; }
.calc-form .cf-row { margin-bottom: 14px; }
.calc-result { margin-top: 16px; background: #FFFFFF; border: 1.5px solid #D7E7FA; border-radius: 18px; padding: 20px; box-shadow: 0 8px 24px rgba(11,46,107,.08); }
.cr-value { font-size: 18px; font-weight: 800; color: #0B2E6B; }
.cr-value .cr-num { font-size: 26px; }
.cr-cat { display: inline-block; margin-top: 10px; font-weight: 800; font-size: 15px; padding: 8px 18px; border-radius: 999px; }
.cr-cat.c-green { background: #F0FDFA; color: #0F766E; border: 1px solid #99F6E4; }
.cr-cat.c-blue { background: #F0F7FF; color: #1769E0; border: 1px solid #BFDDFF; }
.cr-cat.c-yellow { background: #FEF9C3; color: #854D0E; border: 1px solid #FDE68A; }
.cr-cat.c-orange { background: #FFEDD5; color: #C2410C; border: 1px solid #FDBA74; }
.cr-cat.c-red { background: #FEE2E2; color: #B91C1C; border: 1px solid #FCA5A5; }
.cr-note { margin-top: 12px; font-size: 14px; line-height: 1.9; color: #334155; }
.cr-note .ped { display: block; margin-top: 8px; color: #92400E; background: #FEF3C7; border: 1px solid #FDE68A; border-radius: 10px; padding: 8px 12px; font-size: 13px; }
.cr-alert { margin-top: 14px; background: #FEF2F2; border: 1.5px solid #FCA5A5; color: #7F1D1D; border-radius: 14px; padding: 14px 16px; font-size: 14px; line-height: 1.8; }
.cr-alert a { color: #B91C1C; font-weight: 800; text-decoration: underline; }
.cr-assist { margin-top: 16px; border-top: 1px dashed #CBD5E1; padding-top: 14px; text-align: center; }
.cr-assist .cr-follow { font-size: 14px; font-weight: 700; color: #134E4A; margin-bottom: 10px; }
.cr-assist .btn { min-width: 220px; }
.calc-rows { margin-top: 10px; display: flex; flex-direction: column; gap: 8px; }
.cd-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 12px; padding: 12px 14px; font-size: 14px; }
.cd-row b { color: #0B2E6B; }
.cd-row .cd-first { background: #F0FDFA; border: 1px solid #99F6E4; color: #0F766E; font-size: 11.5px; font-weight: 800; border-radius: 999px; padding: 3px 10px; }
.cd-note { margin-top: 12px; background: #FFF7ED; border: 1px dashed #FDBA74; color: #9A3412; border-radius: 10px; padding: 10px 12px; font-size: 13px; line-height: 1.8; }
.calc-unit-row { display: flex; gap: 8px; flex-wrap: wrap; }
.calc-unit-row label { flex: 1; min-width: 140px; border: 2px solid #E2E8F0; border-radius: 12px; padding: 11px; text-align: center; cursor: pointer; font-size: 14px; font-weight: 700; color: #475569; font-family: inherit; }
.calc-unit-row input[type="radio"] { display: none; }
.calc-unit-row input[type="radio"]:checked + label { border-color: #0F766E; background: #F0FDFA; color: #0F766E; }
.calc-a1c-hint { font-size: 12.5px; color: #92400E; background: #FEF3C7; border: 1px solid #FDE68A; border-radius: 10px; padding: 8px 12px; margin-top: 8px; }
"""


def calculators_page():
    t = CT["en" if _lang() == "en" else "ar"]
    cards = [
        ("bmi", "⚖️", "calc_bmi_name", "calc_bmi_desc"),
        ("fluids", "💧", "calc_fluids_name", "calc_fluids_desc"),
        ("dose", "💊", "calc_dose_name", "calc_dose_desc"),
        ("cal", "🔥", "calc_cal_name", "calc_cal_desc"),
        ("sug", "🩸", "calc_sug_name", "calc_sug_desc"),
    ]
    cards_html = "".join(
        '<button class="calc-card" onclick="showCalc(\'%s\')"><div class="cc-ic">%s</div>'
        '<h3>%s</h3><p>%s</p><span class="cc-btn">%s</span></button>'
        % (k, ic, t[n], t[d], t["calc_now"])
        for k, ic, n, d in cards
    )
    body = """
    <div class="card">
      <h2>__CALCH__</h2>
      <p class="muted">__CALCSUB__</p>
      <div class="calc-grid">__CARDS__</div>
    </div>

    <div id="calcPaneArea" style="display:none;">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:6px;flex-wrap:wrap;">
        <h2 id="paneTitle" style="color:#134E4A;"></h2>
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

    <div class="warn">__CALCDISC__</div>
    <script>
    const T = __PT__;
    function esc(s) { const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }
    function CTT(k) { return T[k] || k; }
    function APILang() { return document.documentElement.lang === 'en' ? 'en' : 'ar'; }
    const PANE_TITLES = { bmi: 'calc_bmi_name', fluids: 'calc_fluids_name', dose: 'calc_dose_name', cal: 'calc_cal_name', sug: 'calc_sug_name' };
    const CAT_EMOJI = { green: '🟢', blue: '🔵', yellow: '🟡', orange: '🟠', red: '🔴' };
    let calcCtx = '';

    function showCalc(k) {
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
      if (calcCtx && typeof asstSendContextText === 'function') asstSendContextText(calcCtx);
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
    function assistHTML() {
      return '<div class="cr-assist"><div class="cr-follow">' + esc(CTT('calc_follow')) + '</div>' +
        '<button class="btn pri" onclick="askCalc()">' + esc(CTT('calc_ask')) + '</button></div>';
    }
    function renderBox(id, d, kind, valueLabel, unit, extraPed) {
      const box = document.getElementById(id);
      let h = '<div class="calc-result">';
      h += '<div class="cr-value">' + esc(valueLabel) + ' <span class="cr-num">' + fmtNum(d.value) + '</span> ' + esc(unit || '') + '</div>';
      h += catHTML(d, kind) + noteHTML(d, kind, extraPed);
      h += alertHTML(d) + assistHTML();
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
        h += alertHTML(d) + assistHTML() + '</div>';
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
        hh += assistHTML() + '</div>';
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
        bb += alertHTML(d) + assistHTML() + '</div>';
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
        hh += alertHTML(d) + assistHTML() + '</div>';
        document.getElementById('resSug').innerHTML = hh;
        if (d.type === 'a1c') calcCtx = CTT('calc_sug_ctx').replace('%v', fmtNum(d.value)).replace('%u', '%').replace('%t', 'HbA1c');
        else calcCtx = CTT('calc_sug_ctx').replace('%v', fmtNum(d.value)).replace('%u', d.unit).replace('%t', typeLabel);
      }, 'resSug');
    }
    </script>
    """
    repl = [
        ("__PT__", json.dumps(t, ensure_ascii=False)),
        ("__CALCH__", t["calc_h"]), ("__CALCSUB__", t["calc_sub"]),
        ("__CARDS__", cards_html), ("__CALCBACK__", t["calc_back"]),
        ("__CALCDISC__", t["calc_disc"]),
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
    try:
        rows = db.get_records(_user_id(), limit=50)
    except Exception:
        rows = []
    stats = {"total": len(rows), "high": 0, "medium": 0, "low": 0}
    for r in rows:
        u = (r.get("urgency") or "").lower()
        if u == "high":
            stats["high"] += 1
        elif u == "medium":
            stats["medium"] += 1
        else:
            stats["low"] += 1
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
    <div class="card" style="max-width:560px;margin:16px auto 0;">
      <h2>__DASH__</h2>
      <p class="muted">__DASHSUB__</p>
      <div class="dash-stats" id="dashStats"></div>
      <div id="dashBlood" style="margin-top:16px;"></div>
    </div>
    <script>
    const P = __PT__;
    function esc(s) { const d=document.createElement('div'); d.textContent=s||''; return d.innerHTML; }
    function bls(s) { return s === 'normal' ? P.bl_sn : (s === 'low' ? P.bl_sl : P.bl_sh); }
    function blc(s) { return s === 'normal' ? '#16a34a' : (s === 'low' ? '#d97706' : '#dc2626'); }
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
    (function renderStats(){
      const box = document.getElementById('dashStats');
      let h = '<div class="dash-stat"><b>' + P.stats_total + '</b><span>' + P.pr_count_an + '</span></div>';
      h += '<div class="dash-stat"><b style="color:#dc2626;">' + P.stats_high + '</b><span>' + P.pr_count_hi + '</span></div>';
      h += '<div class="dash-stat"><b style="color:#d97706;">' + P.stats_med + '</b><span>' + P.pr_count_med + '</span></div>';
      h += '<div class="dash-stat"><b style="color:#16a34a;">' + P.stats_low + '</b><span>' + P.pr_count_lo + '</span></div>';
      box.innerHTML = h;
    })();
    (async function renderBlood(){
      const box = document.getElementById('dashBlood');
      let r;
      try { r = await fetch('/api/blood/history'); } catch(e) { return; }
      let d;
      try { d = await r.json(); } catch(e) { return; }
      if (!d.ok || !d.tests || !d.tests.length) {
        box.innerHTML = '<div class="warn">' + esc(P.pr_blood_empty) + '</div>';
        return;
      }
      const last = d.tests[0];
      let h = '<div class="rc-title">' + esc(P.pr_blood_latest) + '</div>';
      h += '<p style="font-size:14px;line-height:1.8;">' + esc(last.summary || '') + '</p>';
      const up = d.tests.slice(0, 4);
      if (up.length > 1) h += '<div class="rc-title" style="margin-top:16px;">' + esc(P.pr_blood_compare) + '</div>';
      h += '<table class="cmp-table"><tr><th>' + esc(P.pr_blood_col) + '</th>';
      up.forEach(function(tst, i) {
        const when = tst.timestamp ? tst.timestamp.slice(0, 10) : (P.pr_t + ' ' + (up.length - i));
        h += '<th>' + esc(when) + '</th>';
      });
      h += '</tr>';
      const byName = {};
      up.forEach(function(tst) {
        (tst.indicators || []).forEach(function(it) {
          if (!byName[it.name]) byName[it.name] = [];
          byName[it.name].push({v: it.value, u: it.unit || '', s: it.status});
        });
      });
      const names = Object.keys(byName).slice(0, 14);
      names.forEach(function(nm) {
        const cells = byName[nm];
        h += '<tr><td><b>' + esc(nm) + '</b></td>';
        cells.forEach(function(c) {
          h += '<td><span style="color:' + blc(c.s) + ';font-weight:700;">' + esc(String(c.v)) + '</span> ' + esc(c.u) +
               '<div style="font-size:11px;color:' + blc(c.s) + ';">' + esc(bls(c.s)) + '</div></td>';
        });
        h += '</tr>';
      });
      h += '</table>';
      box.innerHTML = h;
    })();
    </script>
    """
    body = body.replace("__PRH__", t["pr_h"]).replace("__PRSUB__", t["pr_sub"])
    body = body.replace("__PRAGE__", t["pr_age"]).replace("__PRGEND__", t["pr_gender"])
    body = body.replace("__PRCOND__", t["pr_conditions"]).replace("__PRMEDS__", t["pr_meds"])
    body = body.replace("__PRALL__", t["pr_allergies"]).replace("__PRSAVE__", t["pr_save"])
    body = body.replace("__AGE__", esc(p.get("age"))).replace("__GENSEL__", gen_sel)
    body = body.replace("__COND__", esc(p.get("conditions"))).replace("__MEDS__", esc(p.get("medications")))
    body = body.replace("__ALL__", esc(p.get("allergies")))
    body = body.replace("__DASH__", t["pr_dash"]).replace("__DASHSUB__", t["pr_dash_sub"])
    body = body.replace("__PT__", json.dumps({
        "pr_saved": t["pr_saved"], "pr_err": t["pr_err"], "__LANG__": "en" if _lang() == "en" else "ar",
        "bl_sn": t["bl_sn"], "bl_sl": t["bl_sl"], "bl_sh": t["bl_sh"],
        "pr_count_an": t["pr_count_an"], "pr_count_hi": t["pr_count_hi"], "pr_count_med": t["pr_count_med"], "pr_count_lo": t["pr_count_lo"],
        "pr_blood_col": t["pr_blood_col"], "pr_blood_v": t["pr_blood_v"], "pr_t": t["pr_t"],
        "pr_blood_empty": t["pr_blood_empty"], "pr_blood_latest": t["pr_blood_latest"], "pr_blood_compare": t["pr_blood_compare"],
        "stats_total": stats["total"], "stats_high": stats["high"], "stats_med": stats["medium"], "stats_low": stats["low"],
    }, ensure_ascii=False))
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


@app.route("/family")
def family():
    return family_page()


@app.route("/family/<int:mid>")
def family_detail(mid):
    return family_detail_page(mid)


@app.route("/search")
def search():
    return search_page()


@app.route("/calculators")
def calculators():
    return calculators_page()


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
    pages = ["/", "/home", "/chat", "/blood", "/search", "/calculators", "/meds", "/family", "/emergency", "/checkin", "/firstaid", "/tips", "/relax", "/profile", "/history", "/about"]
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
        "assistant_feedback": db.assistant_feedback_stats(),
        "db_backend": "PostgreSQL" if db.USE_POSTGRES else "SQLite",
    })


def _voice_parse(text, lang):
    text = text or ""
    low = text.lower()
    if lang == "ar":
        sym_map = [
            (["صداع", "راس", "الرأس"], "🤕 صداع"),
            (["حمى", "حرارة", "سخونة"], "🤒 حمى"),
            (["سعال", "كحة", "كحه"], "😷 سعال"),
            (["صدر", "الصدري"], "🫀 ألم في الصدر"),
            (["غثيان", "قيء", "استفراغ"], "🤢 غثيان"),
            (["تعب", "إرهاق", "ارهاق", "خمول"], "😴 تعب وإرهاق"),
            (["تنفس", "نفس", "اختناق"], "🫁 ضيق التنفس"),
            (["دوار", "دوخة", "دوخه", "دوار"], "💫 دوار"),
            (["مفاصل", "عظام"], "🦴 ألم المفاصل"),
            (["بطن", "معدة"], "😖 ألم في البطن"),
            (["قشعريرة", "رعشة", "رجفه"], "🥶 قشعريرة"),
            (["عيون", "عين", "احمرار العين"], "👁️ احمرار العيون"),
            (["رجل", "رجلين", "ساق"], "🦵 ألم في الرجل"),
            (["حلق", "زور"], "😣 ألم الحلق"),
            (["حكة", "هرش", "هرشه"], "🖐️ حكة"),
        ]
        dur_rules = [
            (["من يومين", "يومين", "منذ يومين", "٢ أيام", "2 أيام"], "📅 1-3 أيام"),
            (["ثلاثة أيام", "ثلاث ايام", "٣ أيام", "3 أيام", "ثلاثة"], "📅 1-3 أيام"),
            (["أربعة أيام", "خمسة أيام", "٤ أيام", "٥ أيام", "4 أيام", "5 أيام"], "📅 4-7 أيام"),
            (["من أمس", "البارحة", "اليوم", "هذا الصباح", "الليلة", "منذ يوم", "من يوم"], "⏰ أقل من 24 ساعة"),
            (["أسبوعين", "اسبوعين"], "🗓️ أكثر من أسبوعين"),
            (["أسبوع", "اسبوع"], "🗓️ 1-2 أسبوع"),
            (["شهر", "أكثر من شهر"], "📆 أكثر من شهر"),
        ]
        sev_rules = [(["شديد جداً", "حرج", "مؤلم جداً"], 5), (["شديد", "قوي"], 4), (["متوسط"], 3), (["خفيف"], 2)]
    else:
        sym_map = [
            (["headache", "head hurts", "head pain"], "🤕 Headache"),
            (["fever", "temperature", "hot"], "🤒 Fever"),
            (["cough"], "😷 Cough"),
            (["chest", "heart pain"], "🫀 Chest pain"),
            (["nausea", "vomit"], "🤢 Nausea"),
            (["fatigue", "tired", "exhausted"], "😴 Fatigue"),
            (["breath", "breathing", "breathless", "choking"], "🫁 Shortness of breath"),
            (["dizzy", "dizziness"], "💫 Dizziness"),
            (["joint", "joints"], "🦴 Joint pain"),
            (["stomach", "abdominal", "belly", "abdomen"], "😖 Stomach pain"),
            (["chills", "shivering"], "🥶 Chills"),
            (["eye", "eyes"], "👁️ Eye redness"),
            (["leg", "legs"], "🦵 Leg pain"),
            (["throat", "sore throat"], "😣 Sore throat"),
            (["itch", "itching", "itchy"], "🖐️ Itching"),
        ]
        dur_rules = [
            (["since yesterday", "yesterday", "today", "this morning", "tonight", "last night"], "⏰ Less than 24 hours"),
            (["two days", "2 days", "couple of days", "three days", "3 days"], "📅 1-3 days"),
            (["two weeks", "2 weeks"], "🗓️ More than 2 weeks"),
            (["week"], "🗓️ 1-2 weeks"),
            (["month"], "📆 More than a month"),
            (["four days", "five days", "4 days", "5 days"], "📅 4-7 days"),
        ]
        sev_rules = [(["extremely severe", "critical", "unbearable", "severe pain"], 5), (["severe", "very bad"], 4), (["moderate"], 3), (["mild", "slight"], 2)]

    found = []
    for kws, label in sym_map:
        if any(k in low for k in kws) and label not in found:
            found.append(label)
    duration = None
    for kws, label in dur_rules:
        if any(k in low for k in kws):
            duration = label
            break
    severity = None
    for kws, val in sev_rules:
        if any(k in low for k in kws):
            severity = val
            break
    return {"symptoms": found, "duration": duration, "severity": severity}


@app.route("/api/voice", methods=["POST"])
def api_voice():
    f = request.files.get("file")
    if not f:
        return jsonify({"ok": False, "error": "لم يتم رفع ملف صوتي"})
    lang = "en" if _lang() == "en" else "ar"
    raw = f.read()
    try:
        client = analysis_core._groq_client()
        tr = client.audio.transcriptions.create(
            file=("voice.webm", raw),
            model="whisper-large-v3",
            language=lang,
        )
        text = (tr.text or "").strip()
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:150]}"})
    if not text:
        return jsonify({"ok": False, "error": "لم يُلتقط صوت واضح — حاول مرة أخرى"})
    return jsonify({"ok": True, "text": text, "parsed": _voice_parse(text, lang)})


@app.route("/api/blood/history", methods=["GET"])
def api_blood_history():
    try:
        db.init_db()
        member_id = request.args.get("member")
        tests = db.get_blood_tests(_user_id(), limit=8,
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
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"})


@app.route("/api/family", methods=["GET", "POST"])
def api_family():
    try:
        db.init_db()
        uid = _user_id()
        if request.method == "POST":
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
def api_family_one(mid):
    try:
        db.init_db()
        uid = _user_id()
        if request.method == "DELETE":
            db.delete_member(uid, mid)
            return jsonify({"ok": True})
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


@app.route("/api/meds/plan", methods=["GET", "POST"])
def api_meds_plan():
    try:
        db.init_db()
        uid = _user_id()
        if request.method == "POST":
            data = request.get_json(force=True)
            times = [str(t).strip() for t in (data.get("times") or []) if str(t).strip()]
            if not data.get("med_name") or not times:
                return jsonify({"ok": False, "error": "اسم الدواء وأوقات الاستخدام مطلوبة"})
            days = data.get("days")
            try:
                days = int(days) if days else None
            except (TypeError, ValueError):
                days = None
            pid = db.save_med_plan(
                uid, int(data.get("member_id") or 0),
                str(data.get("med_name") or "").strip(),
                times,
                str(data.get("dose") or "").strip(),
                days,
                data.get("start_date") or None,
            )
            return jsonify({"ok": True, "id": pid})
        member_id = request.args.get("member")
        plans = db.list_med_plans(uid, member_id=int(member_id) if member_id else None)
        members = {m["id"]: m["name"] for m in db.list_members(uid)}
        for p in plans:
            p["member_name"] = members.get(p["member_id"], "أنا" if p["member_id"] == 0 else "?")
        return jsonify({"ok": True, "plans": plans})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"})


@app.route("/api/meds/plan/<int:pid>", methods=["DELETE"])
def api_meds_plan_delete(pid):
    try:
        db.init_db()
        db.delete_med_plan(_user_id(), pid)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"})


@app.route("/api/meds/today", methods=["GET"])
def api_meds_today():
    try:
        db.init_db()
        uid = _user_id()
        plans = db.med_plans_today(uid)
        members = {m["id"]: m["name"] for m in db.list_members(uid)}
        for p in plans:
            p["member_name"] = members.get(p["member_id"], _t("me_short") if p["member_id"] == 0 else "")
        return jsonify({"ok": True, "plans": plans})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"})


@app.route("/api/meds/log", methods=["POST"])
def api_meds_log():
    try:
        db.init_db()
        data = request.get_json(force=True)
        plan_id = int(data.get("plan_id") or 0)
        log_time = str(data.get("time") or "")
        status = str(data.get("status") or "taken")
        log_date = str(data.get("date") or datetime.now(timezone.utc).date().isoformat())
        if not plan_id or not log_time or status not in ("taken", "skipped", "deferred"):
            return jsonify({"ok": False, "error": "بيانات غير مكتملة"})
        db.log_med_status(_user_id(), int(data.get("member_id") or 0), plan_id, log_date, log_time, status)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"})


@app.route("/api/meds/weekly", methods=["GET"])
def api_meds_weekly():
    try:
        db.init_db()
        member_id = request.args.get("member")
        a = db.med_adherence(_user_id(), member_id=int(member_id) if member_id else None)
        return jsonify({"ok": True, **a})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"})


@app.route("/api/timeline", methods=["GET"])
def api_timeline():
    try:
        db.init_db()
        member_id = int(request.args.get("member") or 0)
        days = int(request.args.get("days") or 30)
        events = db.member_timeline(_user_id(), member_id, days)
        return jsonify({"ok": True, "events": events})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"})


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    try:
        data = request.get_json(force=True)
        lang = "en" if data.get("lang") == "en" else "ar"
        member_id = data.get("member_id") or 0
        member = None
        if member_id:
            try:
                member = db.get_member(_user_id(), int(member_id))
            except Exception:
                member = None
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
            "member_id": int(member_id or 0),
        }
        if member:
            patient["member_name"] = member.get("name", "")
        blood_id = data.get("blood_id")
        if blood_id:
            try:
                bt = db.get_blood_test(_user_id(), blood_id)
                if bt and bt.get("data"):
                    patient["blood"] = bt["data"]
            except Exception:
                pass
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
                else:
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
        except Exception:
            pass
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
    try:
        data = request.get_json(force=True)
        lang = "en" if data.get("lang") == "en" else "ar"
        messages = [m for m in (data.get("messages") or []) if m.get("content")]
        last_text = messages[-1]["content"][:600] if messages else ""
        flags = analysis_core.detect_red_flags([], last_text, lang)
        services = _assistant_services(last_text, lang)
        if flags:
            if lang == "en":
                answer = ("I'm concerned about what you described — it can be an emergency sign ("
                          + ", ".join(flags) + "). Please call emergency services right away (997 in Saudi Arabia) or go to the nearest ER. Do not wait for a reply here.")
            else:
                answer = ("أقلقني ما وصفته — قد يكون علامة طارئة (" + "، ".join(flags) +
                          "). يرجى الاتصال بالإسعاف فوراً 997 أو التوجه لأقرب طوارئ. لا تنتظر الرد هنا.")
            return jsonify({"ok": True, "answer": answer, "emergency_flags": flags, "services": services})
        hist = []
        for m in messages[-6:]:
            role = "user" if m.get("role") == "user" else "assistant"
            hist.append({"role": role, "content": str(m.get("content") or "")[:600]})
        if lang == "en":
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
        return jsonify({"ok": True, "answer": answer, "emergency_flags": [], "services": services})
    except Exception as e:
        err = str(e)
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {err[:200]}"})


@app.route("/api/assistant/feedback", methods=["POST"])
def api_assistant_feedback():
    try:
        data = request.get_json(force=True)
        rating = int(data.get("rating") or 0)
        if rating not in (0, 1, 2):
            return jsonify({"ok": False, "error": "rating must be 0, 1 or 2"})
        message = (data.get("message") or "")[:1000]
        reason = (data.get("reason") or "").strip()[:200] or None
        db.init_db()
        db.save_assistant_feedback(_user_id(), message, rating, reason)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"})


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


@app.route("/api/search")
def api_search():
    try:
        lang = "en" if request.args.get("lang") == "en" else "ar"
        q = (request.args.get("q") or "").strip()
        if not q:
            return jsonify({"ok": True, "result": None, "suggestions": health_search.suggestion_terms(lang)})
        return jsonify({
            "ok": True,
            "result": health_search.search_health(q, lang),
            "suggestions": health_search.suggestion_terms(lang),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"})


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
    member_id = request.form.get("member_id") or 0
    member = None
    if member_id:
        try:
            member = db.get_member(_user_id(), int(member_id))
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
            blood_id = db.save_blood_test(_user_id(), payload, int(member_id or 0))
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
    port = int(os.environ.get("PORT", 5000))
    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=port, threads=8)
    except ImportError:
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    run_webapp()
