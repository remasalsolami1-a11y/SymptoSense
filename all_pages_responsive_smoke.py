#!/usr/bin/env python3
"""Broad cross-device responsive smoke test for public and Admin UI shells.

This is intentionally DOM/CSS focused: it loads the production CSS and worst-case
representative layouts (dense grids, forms, tables, long text, modal dialogs)
across common iPhone, Android, iPad and desktop viewports. It catches page-level
horizontal overflow and mobile form/dialog regressions without requiring a DB.
"""
from __future__ import annotations

import ast
import json
import os
import re
import shutil
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
WEBAPP = ROOT / "webapp.py"
DASHBOARD = ROOT / "dashboard.py"

DEVICES = {
    "phone_320": (320, 568),
    "phone_360": (360, 640),
    "iphone_se": (375, 667),
    "iphone_390": (390, 844),
    "android_412": (412, 915),
    "iphone_large": (430, 932),
    "phone_landscape": (667, 375),
    "iphone_landscape": (844, 390),
    "tablet_768": (768, 1024),
    "ipad_820": (820, 1180),
    "ipad_landscape": (1180, 820),
    "laptop_1280": (1280, 720),
    "laptop_1366": (1366, 768),
    "desktop_1440": (1440, 900),
    "desktop_1920": (1920, 1080),
}


def _string_constant(path: Path, name: str) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    value = ""
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id == name and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                value = node.value.value
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                value += node.value.value
    return value


def public_css() -> str:
    css = _string_constant(WEBAPP, "BASE_CSS") + _string_constant(WEBAPP, "V2_CSS") + _string_constant(WEBAPP, "PREMIUM_POLISH_CSS")
    return "\n".join(line for line in css.splitlines() if not line.strip().startswith("@import"))


def admin_css() -> str:
    html = _string_constant(DASHBOARD, "DASHBOARD_HTML")
    m = re.search(r"<style>(.*?)</style>", html, re.S)
    if not m:
        raise RuntimeError("Admin style block not found")
    return "\n".join(line for line in m.group(1).splitlines() if not line.strip().startswith("@import"))


def public_fixture(css: str, lang: str) -> str:
    direction = "rtl" if lang == "ar" else "ltr"
    long_text = "نص تجريبي طويل لاختبار التفاف المحتوى على جميع المقاسات بدون خروج خارج الشاشة" if lang == "ar" else "A deliberately long responsive text value that must wrap without escaping the viewport"
    return f'''<!doctype html><html lang="{lang}" dir="{direction}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><style>{css}</style>
    <style>
      .tools-grid,.community-kpis,.trust-kpis,.si-flow{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}}
      .med-grid{{display:grid;grid-template-columns:1.25fr .75fr;gap:15px}}.med-form-grid,.calc-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}}
      .community-section,.med-card,.detail-card{{padding:18px;border:1px solid #dce8f0;border-radius:18px;background:#fff}}
      .consent-option{{display:flex;justify-content:space-between;gap:12px;padding:17px;border:1px solid #dce8f0;border-radius:15px}}.consent-option label{{display:flex;gap:10px;flex:1}}
      .ss-mood-grid{{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}}.ss-mood-option{{min-height:100px}}
      .test-table{{min-width:760px;width:100%;border-collapse:collapse}}.test-table td{{padding:10px;border:1px solid #ddd}}
    </style></head><body>
      <header class="ss-mobile-head" style="display:flex"><b class="ss-mobile-logo">SymptoSense</b><div class="ss-mobile-actions"><button class="ss-mobile-lang">EN</button><a class="ss-mobile-account"><span>👤</span><span>{long_text}</span></a></div></header>
      <main class="container">
        <section class="tools-grid">{''.join('<article class="card"><h3>Card</h3><p>'+long_text+'</p><button class="btn pri">Action</button></article>' for _ in range(4))}</section>
        <section class="med-grid"><article class="med-card"><div class="med-form-grid"><label>{long_text}<input value="123"></label><label>{long_text}<select><option>Option</option></select></label></div></article><article class="med-card"><p>{long_text}</p></article></section>
        <section class="calc-grid"><article class="card"><textarea>{long_text}</textarea></article><article class="card"><button class="btn">Calculate</button></article></section>
        <section class="community-kpis">{''.join('<article class="card"><strong>123</strong><span>'+long_text+'</span></article>' for _ in range(4))}</section>
        <section class="trust-kpis">{''.join('<article class="card"><strong>99%</strong><span>'+long_text+'</span></article>' for _ in range(4))}</section>
        <section class="si-flow">{''.join('<article class="card"><b>'+str(i)+'</b><p>'+long_text+'</p></article>' for i in range(1,5))}</section>
        <section class="consent-option"><label><input type="checkbox"><span>{long_text}</span></label><span class="consent-badge">OPTIONAL LONG BADGE</span></section>
        <section class="ss-mood-grid">{''.join('<button class="ss-mood-option">🙂<span>'+str(i)+'</span></button>' for i in range(5))}</section>
        <div class="table-wrap"><table class="test-table"><tbody><tr>{''.join('<td>'+long_text+'</td>' for _ in range(5))}</tr></tbody></table></div>
      </main>
      <div class="ss-modal-overlay open"><section class="ss-modal"><h3>Modal</h3><p>{long_text}</p><input value="test"><button class="ss-modal-btn primary">Save</button></section></div>
    </body></html>'''


def admin_fixture(css: str, lang: str) -> str:
    direction = "rtl" if lang == "ar" else "ltr"
    long_text = "قيمة طويلة لاختبار لوحة الإدارة على الجوال والتابلت" if lang == "ar" else "Long admin value for responsive wrapping across devices"
    return f'''<!doctype html><html lang="{lang}" dir="{direction}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><style>{css}</style></head><body>
      <header class="top"><div class="brand"><div class="brand-ic">❤️</div><div><b>SymptoSense</b><small>Admin Dashboard</small></div></div><div class="user"><span>admin@example.com</span><span class="role">admin</span><a class="top-a">Site</a><a class="top-a">Sign out</a></div></header>
      <div class="layout"><aside class="side">{''.join('<button class="navbtn">Navigation '+str(i)+'</button>' for i in range(12))}</aside><main class="main">
        <div class="head"><div><h1>Admin Dashboard</h1><p>{long_text}</p></div><div class="data-actions"><button class="btn">Export</button><button class="btn ghost">Refresh</button></div></div>
        <div class="grid">{''.join('<article class="stat"><strong>123</strong><span>'+long_text+'</span></article>' for _ in range(4))}</div>
        <section class="pulse-hero"><div class="pulse-grid">{''.join('<article class="pulse-stat"><strong>98%</strong><span>'+long_text+'</span></article>' for _ in range(4))}</div></section>
        <section class="perf-shell"><div class="perf-grid">{''.join('<article class="perf-metric"><strong>12 ms</strong><span>'+long_text+'</span></article>' for _ in range(5))}</div></section>
        <section class="two"><div class="card"><div class="chart"></div></div><div class="card"><div class="security-row"><span>{long_text}</span><button class="btn">Action</button></div></div></section>
        <div class="toolbar"><input class="search" value="{long_text}"><select class="filter"><option>All</option></select><button class="btn">Search</button></div>
        <div class="table-wrap"><table><thead><tr><th>A</th><th>B</th><th>C</th></tr></thead><tbody><tr><td data-label="A">{long_text}</td><td data-label="B">{long_text}</td><td data-label="C">{long_text}</td></tr></tbody></table></div>
      </main></div>
      <div class="modal-bg show"><div class="modal"><div class="modal-head"><h2>Edit</h2><button class="close">×</button></div><div class="form"><div class="form-grid"><div class="field"><label>Name</label><input value="test"></div><div class="field"><label>Notes</label><textarea>{long_text}</textarea></div></div></div></div></div>
    </body></html>'''


def inspect(page, width: int) -> dict:
    return page.evaluate('''() => {
      const de=document.documentElement;
      const modal=document.querySelector('.ss-modal,.modal');
      const inp=document.querySelector('input,textarea,select');
      const r=modal?modal.getBoundingClientRect():null;
      return {
        sw:de.scrollWidth,cw:de.clientWidth,overflowX:de.scrollWidth>de.clientWidth+2,
        modalFits:!r || (r.left>=-2 && r.right<=de.clientWidth+2 && r.height<=window.innerHeight+2),
        inputFont:inp?parseFloat(getComputedStyle(inp).fontSize):0,
        navOverlap:(()=>{const xs=[...document.querySelectorAll('.side .navbtn')].map(x=>x.getBoundingClientRect());for(let i=0;i<xs.length;i++){for(let j=i+1;j<xs.length;j++){const a=xs[i],b=xs[j];if(Math.min(a.right,b.right)-Math.max(a.left,b.left)>2 && Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>2)return true;}}return false;})()
      };
    }''')


def run(output: Path | None = None) -> dict:
    report={"passed":True,"checks":[]}
    pub=public_css(); adm=admin_css()
    with sync_playwright() as p:
        executable=shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome") or shutil.which("google-chrome-stable")
        kw={"headless":True}
        if executable: kw["executable_path"]=executable
        if os.name != "nt": kw["args"]=["--no-sandbox"]
        browser=p.chromium.launch(**kw)
        try:
            for device,(width,height) in DEVICES.items():
                for lang in ("ar","en"):
                    for surface,html in (("public",public_fixture(pub,lang)),("admin",admin_fixture(adm,lang))):
                        page=browser.new_page(viewport={"width":width,"height":height},device_scale_factor=1)
                        page.set_content(html,wait_until="domcontentloaded",timeout=5000)
                        data=inspect(page,width)
                        ok=(not data["overflowX"]) and data["modalFits"] and (not data.get("navOverlap", False))
                        if width<=640:
                            ok=ok and data["inputFont"]>=15.9
                        entry={"device":device,"viewport":[width,height],"lang":lang,"surface":surface,"ok":bool(ok),**data}
                        report["checks"].append(entry); report["passed"] = report["passed"] and bool(ok)
                        page.close()
        finally:
            browser.close()
    if output:
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return report


if __name__ == "__main__":
    import argparse
    ap=argparse.ArgumentParser(); ap.add_argument("--output",type=Path); args=ap.parse_args()
    result=run(args.output)
    failed=[x for x in result["checks"] if not x["ok"]]
    print(json.dumps({"passed":result["passed"],"checks":len(result["checks"]),"failed":failed},ensure_ascii=False,indent=2))
    raise SystemExit(0 if result["passed"] else 1)
