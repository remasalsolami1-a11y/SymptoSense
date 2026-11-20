"""Measured accessibility audit of every public page (V285).

For each page × language (ar, en) × viewport (mobile 390 px, desktop 1280 px):
  * axe-core 4.10 with the WCAG 2.0/2.1/2.2 A + AA rule sets, violations by impact;
  * touch targets: visible links/buttons/inputs smaller than 24×24 CSS px
    (WCAG 2.2 SC 2.5.8, AA) and smaller than 44×44 (SC 2.5.5, AAA, advisory);
  * horizontal overflow (page wider than the viewport), and <html lang/dir>.

    python tools/accessibility_audit.py --base http://127.0.0.1:5002 [--axe path/to/axe.min.js]

axe.min.js is looked up in --axe, $AXE_JS, then node_modules/axe-core (installed by
`npm install`, as a dependency of @axe-core/playwright). Results are written to
evaluation/results/accessibility.json. Automated checks find only part of WCAG
issues; ACCESSIBILITY_CHECKLIST_AR.md lists the manual checks.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evaluation" / "results" / "accessibility.json"

PAGES = ("", "chat", "consent", "search", "blood", "meds", "calculators", "emergency", "firstaid", "tips", "relax",
         "health-library", "health-trends", "about", "how-we-work", "privacy", "terms", "contact", "login", "register", "live-demo")
VIEWPORTS = {"mobile": (390, 844), "desktop": (1280, 900)}
TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]

_TARGETS_JS = """() => {
  const sel = 'a[href],button,input:not([type=hidden]),select,textarea,summary,[role=button],[role=tab],[role=link],[tabindex]:not([tabindex="-1"])';
  const small24 = [], small44 = [];
  for (const el of document.querySelectorAll(sel)) {
    const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    if (!r.width || !r.height || cs.visibility === 'hidden' || cs.display === 'none') continue;
    if (el.closest('[aria-hidden=true],[inert]')) continue;
    // WCAG 2.5.8 exception: a link inside a sentence is sized by the line of text
    const inline = el.tagName === 'A' && cs.display === 'inline' && el.parentElement && /P|LI|SPAN|TD/.test(el.parentElement.tagName);
    const label = (el.getAttribute('aria-label') || el.textContent || el.getAttribute('name') || el.id || el.tagName).trim().slice(0, 40);
    if (!inline && (r.width < 24 || r.height < 24)) small24.push(label + ' ' + Math.round(r.width) + 'x' + Math.round(r.height));
    if (!inline && (r.width < 44 || r.height < 44)) small44.push(label);
  }
  const de = document.documentElement;
  return {small24, small44: small44.length, overflow: de.scrollWidth > window.innerWidth + 1,
          lang: de.getAttribute('lang') || '', dir: de.getAttribute('dir') || ''};
}"""


def _axe_source(arg: str | None) -> str:
    for cand in (arg, os.environ.get("AXE_JS"), ROOT / "node_modules" / "axe-core" / "axe.min.js"):
        if cand and Path(cand).exists():
            return Path(cand).read_text(encoding="utf-8")
    sys.exit("axe.min.js not found: run `npm install` or pass --axe")


def _consent(page, base, lang):
    page.goto(f"{base}/{lang}/consent?next=/{lang}/chat", wait_until="networkidle")
    if page.query_selector("#serviceConsent"):
        page.check("#serviceConsent")
        page.click("#consentMainSubmit")
        page.wait_for_timeout(1200)


def audit(base: str, axe_js: str, pages=PAGES) -> dict:
    from playwright.sync_api import sync_playwright

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for vp, (w, h) in VIEWPORTS.items():
            for lang in ("ar", "en"):
                ctx = browser.new_context(viewport={"width": w, "height": h}, reduced_motion="reduce", bypass_csp=True)  # to inject axe only
                page = ctx.new_page()
                _consent(page, base, lang)
                for slug in pages:
                    url = f"{base}/{lang}/{slug}"
                    resp = page.goto(url, wait_until="networkidle")
                    page.wait_for_timeout(300)
                    page.add_script_tag(content=axe_js)
                    axe = page.evaluate("tags => axe.run(document, {runOnly: {type: 'tag', values: tags}, resultTypes: ['violations']})", TAGS)
                    extra = page.evaluate(_TARGETS_JS)
                    violations = [{"id": v["id"], "impact": v["impact"], "help": v["help"], "nodes": len(v["nodes"]),
                                   "targets": [", ".join(n["target"]) for n in v["nodes"][:5]]} for v in axe["violations"]]
                    results.append({"page": "/" + slug, "lang": lang, "viewport": vp, "status": resp.status if resp else None,
                                    "final_url": page.url.replace(base, ""), "violations": violations,
                                    "touch_below_24": extra["small24"], "touch_below_44": extra["small44"],
                                    "horizontal_overflow": extra["overflow"], "html_lang": extra["lang"], "html_dir": extra["dir"]})
                ctx.close()
        browser.close()
    return summarise(results)


def summarise(results: list[dict]) -> dict:
    by_impact: dict[str, int] = {}
    rules: dict[str, dict] = {}
    for r in results:
        for v in r["violations"]:
            by_impact[v["impact"]] = by_impact.get(v["impact"], 0) + v["nodes"]
            rule = rules.setdefault(v["id"], {"help": v["help"], "impact": v["impact"], "pages": 0, "nodes": 0})
            rule["pages"] += 1
            rule["nodes"] += v["nodes"]
    checks = len(results)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "axe_tags": TAGS,
        "summary": {
            "page_checks": checks,
            "pages": len({r["page"] for r in results}),
            "checks_without_serious_or_critical": sum(not any(v["impact"] in ("serious", "critical") for v in r["violations"]) for r in results),
            "checks_without_any_violation": sum(not r["violations"] for r in results),
            "violation_nodes_by_impact": by_impact,
            "contrast_violation_nodes": sum(v["nodes"] for r in results for v in r["violations"] if v["id"] == "color-contrast"),
            "touch_targets_below_24px": sum(len(r["touch_below_24"]) for r in results),
            "touch_targets_below_44px": sum(r["touch_below_44"] for r in results),
            "pages_with_horizontal_overflow": sorted({f'{r["page"]} ({r["lang"]}, {r["viewport"]})' for r in results if r["horizontal_overflow"]}),
            "pages_missing_lang_or_dir": sorted({f'{r["page"]} ({r["lang"]})' for r in results if not (r["html_lang"] and r["html_dir"])}),
        },
        "rules": dict(sorted(rules.items(), key=lambda kv: -kv[1]["nodes"])),
        "results": results,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="http://127.0.0.1:5002")
    ap.add_argument("--axe")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--pages", nargs="*")
    a = ap.parse_args(argv)
    rep = audit(a.base.rstrip("/"), _axe_source(a.axe), tuple(a.pages) if a.pages else PAGES)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    s = rep["summary"]
    print(json.dumps(s, ensure_ascii=False, indent=1))
    for rid, r in list(rep["rules"].items())[:15]:
        print(f'{r["impact"]:9} {rid:28} pages={r["pages"]:3} nodes={r["nodes"]:4}  {r["help"]}')
    return 0 if s["checks_without_serious_or_critical"] == s["page_checks"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
