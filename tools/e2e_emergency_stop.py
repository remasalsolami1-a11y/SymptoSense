#!/usr/bin/env python3
"""Browser check of the emergency stop overlay: it must be hard to dismiss by accident,
lock the page behind it, give case-specific guidance and require explicit confirmation.

    python tools/e2e_emergency_stop.py --base-url http://127.0.0.1:5000
"""
from __future__ import annotations

import argparse
import os
import sys

from playwright.sync_api import sync_playwright


def run(base_url: str, lang: str = "ar") -> list[str]:
    problems: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None)
        ctx = browser.new_context(viewport={"width": 390, "height": 844})
        page = ctx.new_page()
        page.route("**/*", lambda r: r.abort() if any(h in r.request.url for h in ("googleapis", "gstatic", "google-analytics", "googletagmanager")) else r.continue_())
        page.on("pageerror", lambda e: problems.append("JS pageerror: " + str(e)[:300]))
        page.goto(f"{base_url}/{lang}/chat", wait_until="networkidle")
        page.locator("input[name=service_usage]").evaluate("e=>e.click()")
        page.locator("button").filter(has_text="حفظ الاختيارات").first.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_selector("button:has-text('تحليل كامل')", timeout=30000)
        page.wait_for_timeout(1500)
        for cat, rid, need in (("general", "severe_chest_pain", "997"), ("selfharm", "self_harm_risk", "920033360"), ("poison", "overdose_poisoning", "997"), ("infant", "infant_fever_under_3m", "997"), ("appendix", "suspected_appendicitis", "997"), ("pregnancy", "pregnancy_pain_warning", "997"), ("clot", "dvt_pe_pattern", "997")):
            page.evaluate("(r)=>showEmergency({emergency:true,emergency_flags:['x'],safety_engine:{rule_ids:[r],flags:['x']}})", rid)
            page.wait_for_timeout(250)
            ov = page.locator("#emOverlay")
            if not ov.is_visible():
                problems.append(f"{cat}: overlay not visible"); continue
            if ov.get_attribute("role") != "alertdialog":
                problems.append(f"{cat}: role=alertdialog missing")
            if not page.locator(f"#emOverlay .em-card[data-em-cat='{cat}']").count():
                problems.append(f"{cat}: wrong category card")
            if need not in ov.inner_text() and not page.locator(f"#emOverlay a[href='tel:{need}']").count():
                problems.append(f"{cat}: {need} not shown")
            if cat == "selfharm" and not page.locator("#emOverlay a[href='tel:937']").count():
                problems.append("selfharm: 937 link missing")
            if page.evaluate("document.activeElement && document.activeElement.hasAttribute('data-em-callbtn')") is not True:
                problems.append(f"{cat}: call button not focused")
            if not page.evaluate("document.body.classList.contains('ss-em-open') && !!document.querySelector('[inert]')"):
                problems.append(f"{cat}: page behind overlay not locked")
            page.keyboard.press("Escape")
            ov.click(position={"x": 3, "y": 3})
            if not ov.is_visible():
                problems.append(f"{cat}: dismissed by Escape/backdrop")
            page.locator("#emOverlay [data-em-proceed]").click()
            if not page.locator("#emOverlay [data-em-confirm]").is_visible():
                problems.append(f"{cat}: no confirmation step")
            page.locator("#emOverlay [data-em-no]").click()
            if not ov.is_visible() or page.locator("#emOverlay [data-em-confirm]").is_visible():
                problems.append(f"{cat}: 'go back' did not return to call screen")
            page.locator("#emOverlay [data-em-proceed]").click()
            page.locator("#emOverlay [data-em-yes]").click()
            page.wait_for_timeout(500)
            if ov.is_visible() or page.evaluate("!!document.querySelector('[inert]')"):
                problems.append(f"{cat}: overlay/lock not released after confirmation")
        # Showing the overlay twice (safety-check then analysis) must still unlock the page afterwards.
        page.evaluate("()=>{const d={emergency:true,emergency_flags:['x'],safety_engine:{rule_ids:['severe_chest_pain'],flags:['x']}};showEmergency(d);showEmergency(d)}")
        page.wait_for_timeout(250)
        page.locator("#emOverlay [data-em-proceed]").click()
        page.locator("#emOverlay [data-em-yes]").click()
        page.wait_for_timeout(500)
        if page.evaluate("!!document.querySelector('[inert]')") or page.evaluate("document.body.classList.contains('ss-em-open')"):
            problems.append("double showEmergency left the page locked")
        # Clarification-tree red flag must stop the questions and show the emergency result.
        page.evaluate("()=>{walkClarNode({safety:['ألم صدر شديد','Severe chest pain']})}")
        page.locator("#emOverlay [data-em-proceed]").click()
        page.locator("#emOverlay [data-em-yes]").click()
        page.wait_for_timeout(1500)
        if not page.locator("#symptomResultReport").count():
            problems.append("clarification red flag did not end in an emergency result")
        # V252: warning-sign screen for the entered symptom; "yes" on an emergency-tier screen opens the overlay.
        page.evaluate("()=>{state.symptoms=['ألم صدر'];state.age=40;redflagAsked=[];state.redflag_yes=[];startRedflagScreens()}")
        try:
            page.wait_for_selector("#chatOptions button:has-text('نعم')", state="attached", timeout=8000)
            page.evaluate("()=>{const b=[...document.querySelectorAll('#chatOptions button')].find(x=>x.textContent.trim()==='نعم');b.click()}")
            page.wait_for_selector("#emOverlay", state="visible", timeout=5000)
            if "cp_radiating" not in page.evaluate("state.redflag_yes"):
                problems.append("red-flag screen: yes not recorded for the analysis payload")
        except Exception as exc:
            problems.append("red-flag screen did not lead to the emergency overlay: " + str(exc)[:200].replace("\n"," ") + " | options=" + page.locator("#chatOptions").inner_text()[:150] + " | step=" + str(page.evaluate("state.step")))
        browser.close()
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--lang", default="ar")
    a = ap.parse_args()
    probs = run(a.base_url, a.lang)
    for x in probs:
        print("FAIL:", x)
    print("OK" if not probs else f"{len(probs)} problem(s)")
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
