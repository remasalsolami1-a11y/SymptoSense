#!/usr/bin/env python3
"""Public browser smoke/E2E checks for a deployed or local SymptoSense build.

Usage:
    python tools/e2e_browser.py --base-url http://127.0.0.1:5000

The suite intentionally avoids real personal/medical data. The symptom flow uses
SymptoSense's fictional demo mode, which is not persisted to health history.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


@dataclass(frozen=True)
class Viewport:
    name: str
    width: int
    height: int


VIEWPORTS = (
    Viewport("iphone-390", 390, 844),
    Viewport("mobile-430", 430, 932),
    Viewport("ipad", 768, 1024),
    Viewport("laptop", 1366, 768),
    Viewport("desktop", 1440, 900),
)


def _assert_no_horizontal_overflow(page, label: str) -> None:
    overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    if overflow > 2:
        raise AssertionError(f"{label}: horizontal overflow detected ({overflow}px)")


def _set_language(context, base_url: str, lang: str = "en") -> None:
    context.add_cookies([
        {"name": "lang", "value": lang, "url": base_url, "path": "/", "sameSite": "Lax"}
    ])


def _grant_service_consent(page) -> None:
    result = page.evaluate(
        """async () => {
          const r = await fetch('/api/consent/preferences', {
            method:'POST', headers:{'Content-Type':'application/json'},
            body:JSON.stringify({service_usage:true, analytics_research:false, research_participation:false})
          });
          return {status:r.status, body:await r.json()};
        }"""
    )
    if result["status"] != 200 or not result["body"].get("ok"):
        raise AssertionError(f"Consent setup failed: {result}")


def run(base_url: str, headed: bool = False) -> int:
    failures: list[str] = []
    base_url = base_url.rstrip("/") + "/"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        try:
            # One end-to-end interaction pass validates the strict CSP bridge,
            # language picker, assistant controls, and the non-persistent demo.
            preflight = browser.new_context(viewport={"width": 390, "height": 844})
            page = preflight.new_page()
            page.set_default_timeout(20_000)
            try:
                response = page.goto(base_url, wait_until="domcontentloaded")
                csp = (response.headers.get("content-security-policy", "") if response else "")
                if "script-src-attr 'none'" not in csp or "script-src 'self' 'unsafe-inline'" in csp:
                    raise AssertionError(f"strict script CSP missing: {csp}")
                page.locator(".first-lang-option[lang='en']").wait_for(state="visible")
                page.locator(".first-lang-option[lang='en']").click()
                page.wait_for_url("**/home")
                # Home CTAs must be usable under the enforced CSP, without relying
                # on executable inline event attributes.
                page.locator("#heroDemoOpen").click()
                page.locator("#heroDemoModal:not([hidden])").wait_for(state="visible")
                page.locator("#heroDemoClose").click()
                page.locator("#heroDemoModal[hidden]").wait_for(state="attached")
                page.locator("#heroAskAssistant").click()
                page.locator("#asstPanel.open").wait_for(state="visible")
                page.locator("#asstPanel .asst-head > button:last-child").click()
                page.locator("#asstPanel:not(.open)").wait_for(state="attached")

                # The floating assistant trigger remains available away from the
                # home hero, where it is intentionally hidden to avoid duplicate CTAs.
                page.goto(urljoin(base_url, "sources"), wait_until="domcontentloaded")
                page.locator("#asstFab").click()
                page.locator("#asstPanel.open").wait_for(state="visible")
                page.locator("#asstPanel .asst-head > button:last-child").click()
                page.goto(urljoin(base_url, "home"), wait_until="domcontentloaded")

                _grant_service_consent(page)
                page.locator("#heroStartAnalysis").click()
                page.wait_for_url("**/chat")
                page.go_back(wait_until="domcontentloaded")
                page.goto(urljoin(base_url, "chat?demo=1"), wait_until="domcontentloaded")
                page.locator(".ss-demo-flow-note").wait_for(state="visible")
                page.get_by_role("button", name="Run demo assessment").click()
                page.locator(".ss-report-heading").wait_for(state="visible", timeout=30_000)
                demo_record_id = page.evaluate("lastResult ? lastResult.record_id : 'missing'")
                demo_mode = page.evaluate("lastResult ? lastResult.demo_mode : false")
                if demo_record_id not in (None, 0):
                    raise AssertionError(f"demo unexpectedly persisted record_id={demo_record_id}")
                if demo_mode is not True:
                    raise AssertionError("demo result was not tagged as demo_mode")
                disclaimer = page.locator(".ss-report-disclaimer").inner_text().lower()
                if "does not provide a medical diagnosis" not in disclaimer:
                    raise AssertionError("non-diagnostic result disclaimer missing")
            except (AssertionError, PlaywrightTimeoutError, Exception) as exc:
                failures.append(f"interaction-preflight: {type(exc).__name__}: {exc}")
            finally:
                preflight.close()

            for vp in VIEWPORTS:
                context = browser.new_context(viewport={"width": vp.width, "height": vp.height})
                _set_language(context, base_url, "en")
                page = context.new_page()
                page.set_default_timeout(12_000)
                try:
                    page.goto(urljoin(base_url, "home"), wait_until="domcontentloaded")
                    page.locator("#homeTitle").wait_for(state="visible")
                    page.locator("#heroStartAnalysis").wait_for(state="visible")
                    page.locator("#heroDemoOpen").wait_for(state="visible")
                    page.locator("#heroAskAssistant").wait_for(state="visible")
                    _assert_no_horizontal_overflow(page, f"{vp.name}/home")

                    # Public informational pages should render without overflow.
                    for path in ("sources", "methodology", "calculators", "blood"):
                        page.goto(urljoin(base_url, path), wait_until="domcontentloaded")
                        _assert_no_horizontal_overflow(page, f"{vp.name}/{path}")

                    # Exercise the fictional/non-persistent demo path.
                    page.goto(urljoin(base_url, "home"), wait_until="domcontentloaded")
                    _grant_service_consent(page)
                    page.goto(urljoin(base_url, "chat?demo=1"), wait_until="domcontentloaded")
                    page.locator(".ss-demo-flow-note").wait_for(state="visible")
                    page.locator(".chat-wrap").wait_for(state="visible")
                    _assert_no_horizontal_overflow(page, f"{vp.name}/chat-demo")
                    demo_text = page.locator(".ss-demo-flow-note").inner_text()
                    if "will not be saved" not in demo_text.lower():
                        raise AssertionError(f"{vp.name}: demo privacy notice missing")
                except (AssertionError, PlaywrightTimeoutError, Exception) as exc:
                    failures.append(f"{vp.name}: {type(exc).__name__}: {exc}")
                finally:
                    context.close()
        finally:
            browser.close()

    if failures:
        print("E2E CHECK: FAIL")
        for failure in failures:
            print(" -", failure)
        return 1
    print(f"E2E CHECK: PASS ({len(VIEWPORTS)} viewport profiles)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:5000")
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()
    return run(args.base_url, args.headed)


if __name__ == "__main__":
    raise SystemExit(main())
