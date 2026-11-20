#!/usr/bin/env python3
"""Cross-viewport smoke test for SymptoSense's responsive shell/questionnaire.

This test intentionally uses the production CSS extracted from webapp.py and a
minimal DOM that mirrors the symptom questionnaire. It catches horizontal
scrolling, cramped age layout, Continue appearing above symptoms, and result
section ordering across representative viewports. It does not claim to replace
real-device Safari/Android tests for browser-specific APIs such as Web Push.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
from pathlib import Path
from typing import Dict

try:
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:  # Allows --help and static inspection without dev extras.
    sync_playwright = None

ROOT = Path(__file__).resolve().parent
WEBAPP = ROOT / "webapp.py"

DEVICES = {
    "iphone_se": (375, 667),
    "iphone_large": (430, 932),
    "android": (412, 915),
    "ipad": (820, 1180),
    "laptop": (1440, 900),
}


def extract_css() -> str:
    tree = ast.parse(WEBAPP.read_text(encoding="utf-8"))
    wanted = {"BASE_CSS", "V2_CSS", "PREMIUM_POLISH_CSS", "LANG_PICKER_CSS"}
    values: Dict[str, str] = {k: "" for k in wanted}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in wanted and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                values[name] = node.value.value
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and node.target.id in wanted:
            if isinstance(node.op, ast.Add) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                values[node.target.id] += node.value.value
    css = values["BASE_CSS"] + values["V2_CSS"] + values["PREMIUM_POLISH_CSS"] + values["LANG_PICKER_CSS"]
    return "\n".join(line for line in css.splitlines() if not line.strip().startswith("@import"))


def landing_fixture(css: str) -> str:
    """Render the real current welcome-page body without importing Flask."""
    tree = ast.parse(WEBAPP.read_text(encoding="utf-8"))
    body = ""
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "welcome_page":
            for child in node.body:
                if (isinstance(child, ast.Assign) and len(child.targets) == 1
                        and isinstance(child.targets[0], ast.Name) and child.targets[0].id == "body"
                        and isinstance(child.value, ast.Constant) and isinstance(child.value.value, str)):
                    body = child.value.value
                    break
            break
    if not body:
        raise RuntimeError("welcome_page body literal not found")
    body = (body.replace("__NEXT__", '"/home"')
                .replace("__LANG_AR_TARGET__", "/ar/")
                .replace("__LANG_EN_TARGET__", "/en/"))
    return ("<!doctype html><html lang='ar' dir='rtl'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1,viewport-fit=cover'>"
            + "<style>" + css + "</style></head><body>" + body + "</body></html>")


def fixture(css: str, state: str, lang: str) -> str:
    rtl = lang == "ar"
    direction = "rtl" if rtl else "ltr"
    if state == "age":
        inner = f"""
        <div class="chat-body" id="chatBody">
          <div class="step-focus-card">
            <div class="step-focus-kicker">{'الخطوة 1' if rtl else 'Step 1'}</div>
            <div class="step-focus-question" id="ageQuestion">{'كم عمرك؟' if rtl else 'How old are you?'}</div>
          </div>
        </div>
        <div class="chat-options" id="chatOptions"></div>
        <div class="chat-input" id="chatInput">
          <input id="ageInput" inputmode="numeric" placeholder="{'مثال: 28' if rtl else 'Example: 28'}">
          <button>{'إرسال' if rtl else 'Send'}</button>
        </div>"""
    elif state == "symptoms":
        labels = ["صداع", "حرارة", "سعال", "غثيان", "دوخة", "تعب"] if rtl else ["Headache", "Fever", "Cough", "Nausea", "Dizziness", "Fatigue"]
        opts = "".join(f'<button class="opt">{x}</button>' for x in labels)
        inner = f"""
        <div class="chat-body" id="chatBody"><div class="step-focus-card"><div class="step-focus-question">{'اختر الأعراض' if rtl else 'Choose symptoms'}</div></div></div>
        <div class="chat-options symptom-picker" id="chatOptions">{opts}<div id="relBlock"><b>{'أعراض مرتبطة' if rtl else 'Related symptoms'}</b></div><button id="continueButton" class="start-btn is-next">{'متابعة' if rtl else 'Continue'}</button></div>
        <div class="chat-input" id="chatInput" style="display:none"></div>"""
    else:
        titles = (
            ["مستوى الخطورة", "ماذا أفعل الآن؟", "الاحتمالات", "لماذا ظهر هذا التقييم؟", "علامات الخطر", "المصادر الطبية"]
            if rtl else
            ["Risk level", "What should I do now?", "Possible conditions", "Why this assessment?", "Warning signs", "Medical sources"]
        )
        sections = "".join(f'<section class="ss-report-card result-section" data-result-index="{i}"><h3>{t}</h3><p>Sample content for responsive layout testing.</p></section>' for i, t in enumerate(titles))
        inner = f'<div class="chat-body result-mode" id="chatBody">{sections}</div><div class="chat-options" id="chatOptions"></div><div class="chat-input" id="chatInput" style="display:none"></div>'
    return f"""<!doctype html><html lang="{lang}" dir="{direction}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><style>{css}</style></head>
    <body class="ss-chat-page" data-chat-step="{state}">
      <header class="ss-mobile-head"><b>SymptoSense</b></header>
      <main class="container"><div class="chat-wrap {'report-mode' if state == 'result' else ''}"><div class="chat-head"><div class="avatar">🏥</div><div><h3>SymptoSense</h3><p>Health assistant</p></div></div><div class="ss-flow"><div class="ss-flow-copy"><span>1 / 7</span><span>Questionnaire</span></div><div class="ss-flow-track"><div class="ss-flow-fill" style="width:20%"></div></div></div>{inner}</div></main>
      <nav class="ss-bnav"><a>⌂</a><a class="on">🩺</a><a>🧠</a><a>👤</a></nav>
    </body></html>"""


def run(output: Path | None = None, screenshots: Path | None = None) -> dict:
    if sync_playwright is None:
        raise RuntimeError(
            "Playwright is required for the device smoke test. "
            "Install development dependencies with: pip install -r requirements-dev.txt"
        )
    css = extract_css()
    report = {"checks": [], "passed": True}
    if screenshots:
        screenshots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        system_chromium = (
            shutil.which("chromium")
            or shutil.which("chromium-browser")
            or shutil.which("google-chrome")
            or shutil.which("google-chrome-stable")
        )
        launch_kwargs = {"headless": True}
        if system_chromium:
            launch_kwargs["executable_path"] = system_chromium
        # Some Linux CI/container environments run as root and need --no-sandbox.
        if os.name != "nt":
            launch_kwargs["args"] = ["--no-sandbox"]
        browser = p.chromium.launch(**launch_kwargs)
        try:
            for name, (width, height) in DEVICES.items():
                page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
                # Actual landing preview smoke test (set_content avoids file:// restrictions).
                page.set_content(landing_fixture(css), wait_until="domcontentloaded", timeout=5000)
                landing = page.evaluate("""() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth})""")
                ok = landing["sw"] <= landing["cw"] + 2
                report["checks"].append({"device": name, "lang": "ar", "state": "landing", "ok": ok, **landing})
                report["passed"] = report["passed"] and ok
                page.close()

                for lang in ("ar", "en"):
                    for state in ("age", "symptoms", "result"):
                        page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
                        page.set_content(fixture(css, state, lang), wait_until="domcontentloaded", timeout=5000)
                        data = page.evaluate("""(state) => {
                          const de=document.documentElement;
                          const base={sw:de.scrollWidth,cw:de.clientWidth,overflowX:de.scrollWidth>de.clientWidth+2};
                          if(state==='age'){
                            const q=document.getElementById('ageQuestion').getBoundingClientRect();
                            const i=document.getElementById('ageInput').getBoundingClientRect();
                            base.questionToInputGap=Math.round(i.top-q.bottom);
                            base.inputWidth=Math.round(i.width);
                            base.containerWidth=Math.round(document.querySelector('.container').getBoundingClientRect().width);
                          } else if(state==='symptoms'){
                            const c=document.getElementById('continueButton').getBoundingClientRect();
                            const opts=[...document.querySelectorAll('#chatOptions .opt')].map(x=>x.getBoundingClientRect());
                            base.continueBelowSymptoms=opts.every(x=>c.top>=x.bottom-1);
                            base.continueTop=Math.round(c.top);
                            base.lastSymptomBottom=Math.round(Math.max(...opts.map(x=>x.bottom)));
                          } else {
                            const ys=[...document.querySelectorAll('.result-section')].map(x=>Math.round(x.getBoundingClientRect().top));
                            base.resultOrder=ys.every((v,i)=>i===0||v>ys[i-1]);
                            base.resultTops=ys;
                          }
                          return base;
                        }""", state)
                        ok = not data["overflowX"]
                        if state == "age" and width <= 430:
                            ok = ok and data["questionToInputGap"] >= 40 and data["inputWidth"] >= min(300, width - 60)
                        if state == "symptoms":
                            ok = ok and data["continueBelowSymptoms"]
                        if state == "result":
                            ok = ok and data["resultOrder"]
                        entry = {"device": name, "lang": lang, "state": state, "ok": bool(ok), **data}
                        report["checks"].append(entry)
                        report["passed"] = report["passed"] and bool(ok)
                        if screenshots and lang == "ar" and state in {"age", "symptoms", "result"}:
                            page.screenshot(path=str(screenshots / f"{name}_{state}.png"), full_page=True)
                        page.close()
        finally:
            browser.close()
    if output:
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    result = run(args.output, args.screenshots)
    print(json.dumps({"passed": result["passed"], "checks": len(result["checks"]), "failed": [x for x in result["checks"] if not x["ok"]]}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
