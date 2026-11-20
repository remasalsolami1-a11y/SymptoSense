#!/usr/bin/env python3
"""Full-flow browser test: consent -> questionnaire -> result screen.

Fails (exit 1) on ANY uncaught JavaScript error, console error, failed
same-origin request (>=400), or when the result's first screen is missing its
safety elements.  Usage:

    python tools/e2e_full_flow.py --base-url http://127.0.0.1:5000 [--lang ar]
"""
from __future__ import annotations

import argparse
import os
import sys

from playwright.sync_api import sync_playwright

IGNORED_HOSTS = ("googleapis", "gstatic", "google-analytics", "googletagmanager")

LABELS = {
    "ar": dict(full="تحليل كامل", send="إرسال", sex="ذكر", quick="اختيار سريع", symptom="صداع",
               cont="متابعة التحليل", duration="1-3 أيام", severity="متوسط",
               pattern=("فجأة", "مستمر", "مع الحركة", "الراحة"), show="إظهار التحليل الآن",
               save="حفظ الاختيارات"),
}


def run(base_url: str, lang: str = "ar", width: int = 390, height: int = 844) -> list[str]:
    L = LABELS[lang]
    problems: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None)
        ctx = browser.new_context(viewport={"width": width, "height": height}, is_mobile=width < 600, has_touch=width < 600)
        page = ctx.new_page()
        page.route("**/*", lambda r: r.abort() if any(h in r.request.url for h in IGNORED_HOSTS) else r.continue_())
        page.on("pageerror", lambda e: problems.append("JS pageerror: " + str(e)[:300]))
        state = {"axe": False}  # axe itself triggers CSP console noise; ignore it while it runs
        page.on("console", lambda m: problems.append("console.error: " + m.text[:200])
                if m.type == "error" and "Failed to load resource" not in m.text and not state["axe"] else None)
        page.on("response", lambda r: problems.append(f"HTTP {r.status} {r.url[-70:]}")
                if r.status >= 400 and not any(h in r.url for h in IGNORED_HOSTS) else None)

        LAYOUT_JS = """() => { const vw = document.documentElement.clientWidth, bad = [];
          const over = document.documentElement.scrollWidth - vw;
          document.querySelectorAll('.container button, .container input, .container select, .container textarea, .container a').forEach(e => {
            const r = e.getBoundingClientRect(), cs = getComputedStyle(e);
            if (!r.width || !r.height || cs.visibility === 'hidden' || cs.display === 'none') return;
            if (r.right > vw + 1 || r.left < -1) bad.push('outside viewport: ' + (e.innerText || e.placeholder || e.id || e.tagName).trim().slice(0, 30) + ' [' + Math.round(r.left) + ',' + Math.round(r.right) + ']');
            else if (e.tagName === 'BUTTON' && e.scrollWidth > e.clientWidth + 2 && cs.overflow !== 'visible') bad.push('clipped button text: ' + e.innerText.trim().slice(0, 30));
          });
          return {over: over, bad: bad.slice(0, 4)}; }"""
        seen_layout = set()

        def layout(label):
            try:
                res = page.evaluate(LAYOUT_JS)
            except Exception:
                return
            if res["over"] > 2 and ("overflow", label) not in seen_layout:
                seen_layout.add(("overflow", label)); problems.append(f"layout@{width}: horizontal overflow {res['over']}px after '{label}'")
            for b in res["bad"]:
                if (b, label) not in seen_layout:
                    seen_layout.add((b, label)); problems.append(f"layout@{width}: {b} after '{label}'")

        def click(text, scope=".container button, .container [role=button]", timeout=10000, pause=1200):
            page.locator(scope).filter(has_text=text).first.click(timeout=timeout)
            page.wait_for_timeout(pause)
            layout(text)

        page.goto(f"{base_url}/{lang}/chat", wait_until="networkidle")
        page.locator("input[name=service_usage]").evaluate("e=>e.click()")
        page.locator(f"button:has-text('{L['save']}')").first.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1500)
        page.wait_for_selector(f"button:has-text('{L['full']}')", timeout=30000)
        page.wait_for_timeout(1000)
        # Emergency wording must short-circuit through the live endpoint (dialect phrases, not exact keywords).
        for phrase in ("مش قادر اتنفس", "صدري ينعصر وعرقان", "قلبي واقف"):
            res = page.evaluate(
                "async (t)=>{const r=await fetch('/api/analyze/safety-check',{method:'POST',headers:{'Content-Type':'application/json'},"
                "body:JSON.stringify({symptoms:[t],notes:'',lang:'ar',age:40,severity:3})});return r.json()}", phrase)
            if not res.get("emergency"):
                problems.append(f"emergency endpoint missed: {phrase} -> {str(res)[:120]}")
        def answer_until_symptom():
            click(L["full"], scope="button")
            page.locator(".container input[type=text]").first.fill("30")
            click(L["send"], pause=1200)
            click(L["sex"], pause=1500)
            click(L["quick"], pause=800)
            click(L["symptom"], pause=800)

        # Closing the tab mid-way must not lose the answers: reload -> resume prompt -> start over.
        answer_until_symptom()
        page.evaluate("window.dispatchEvent(new Event('pagehide'))")
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(2500)
        if not page.locator(".container").filter(has_text="غير مكتمل").count():
            problems.append("draft: unfinished-assessment prompt not shown after reload")
        else:
            click("ابدأ من جديد", pause=1500)
        answer_until_symptom()
        click(L["cont"], pause=1500)
        for key in (L["duration"], L["severity"]):
            click(key, pause=2500)
        for key in L["pattern"]:
            click(key, pause=300)
        page.locator(".container button:has-text('متابعة')").last.click()
        page.wait_for_timeout(3000)

        # Adaptive follow-up questions: answer conservatively until the "show now" button appears.
        for _ in range(12):
            if page.locator(f".container button:has-text('{L['show']}')").count():
                break
            if page.locator(".container input:visible, .container textarea:visible").count():
                page.locator(".container input:visible, .container textarea:visible").first.fill("لا")
                click(L["send"], pause=3000)
                continue
            for key in ("تخطي", "لا", "متابعة", "نعم", "حفظ"):
                btn = page.locator(".container button").filter(has_text=key)
                if btn.count():
                    btn.first.click(timeout=8000)
                    page.wait_for_timeout(3000)
                    break
            else:
                break
        click(L["show"], pause=4000)
        for _ in range(4):  # a second round may offer "symptom analysis"
            nxt = page.locator(".container button, .container a").filter(has_text="تحليل الأعراض")
            if page.locator("#symptomResultReport").count() or not nxt.count():
                break
            nxt.first.click(timeout=8000)
            page.wait_for_timeout(9000)

        page.wait_for_selector("#symptomResultReport", timeout=30000)
        report = page.locator("#symptomResultReport")
        if not report.locator(".ss-risk-value").inner_text().strip():
            problems.append("result: risk level text is empty (colour alone is not enough)")
        if not page.locator("#symptomResultReport a.ss-call-btn[href='tel:997']").count():
            problems.append("result: emergency call button (tel:997) missing")
        if not page.locator("#symptomResultReport .ss-disclaimer").count():
            problems.append("result: 'does not replace a doctor' disclaimer missing")
        order = page.evaluate("""()=>{const r=document.getElementById('symptomResultReport');
            const q=s=>{const e=r.querySelector(s);return e?e.getBoundingClientRect().top:1e9};
            return {risk:q('.ss-risk-value'),call:q('.ss-call-btn'),todo:q('.ss-step-list'),details:q('.ss-details-divider'),understood:q('.ss-understood-card')}}""")
        if not (order["risk"] < order["call"] < order["todo"] < order["details"] < order["understood"]):
            problems.append(f"result: first-screen order wrong {order}")
        # Accessibility of the result screen (WCAG 2.x A/AA); skipped when axe is not installed.
        try:
            from axe_playwright_python.sync_playwright import Axe
        except Exception:
            Axe = None
        if Axe is not None:
            state["axe"] = True
            res = Axe().run(page, options={"runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]}})
            for v in res.response.get("violations", []):
                if v.get("impact") in ("critical", "serious"):
                    nodes = "; ".join((n.get("html", "")[:110] + " -> " + str((n.get("any") or [{}])[0].get("message", ""))[:90]) for n in v.get("nodes", [])[:4])
                    problems.append(f"a11y {v['impact']}: {v['id']} ({len(v.get('nodes', []))} nodes) {v.get('help', '')} :: {nodes}")
        else:
            print("note: axe-playwright-python not installed; accessibility check skipped")
        if page.evaluate("document.documentElement.scrollWidth-document.documentElement.clientWidth") > 2:
            problems.append("result: horizontal overflow")
        browser.close()
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:5000")
    ap.add_argument("--lang", default="ar", choices=sorted(LABELS))
    ap.add_argument("--width", type=int, default=390)
    ap.add_argument("--height", type=int, default=844)
    a = ap.parse_args()
    problems = run(a.base_url.rstrip("/"), a.lang, a.width, a.height)
    for item in problems:
        print("FAIL:", item)
    print("full-flow e2e:", "FAILED" if problems else "ok")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
