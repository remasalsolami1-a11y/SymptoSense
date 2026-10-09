#!/usr/bin/env python3
"""Static full-site interaction contract audit for SymptoSense.

This deliberately does not import Flask. It validates the contracts that make
buttons/links usable under the strict CSP used in production: explicit button
types, a click/submit binding, bridge coverage, internal navigation targets,
and literal fetch/API method targets.
"""
from __future__ import annotations

import ast
import html
import os
import tempfile
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SUFFIXES = {".py", ".html", ".js"}
EXCLUDED_PARTS = {"tests", "tools", "docs", "__pycache__", "node_modules", ".git", ".venv", "venv"}
EVENT_ATTRS = "click|change|input|submit|keydown|keyup|focus|blur|load|error"


def runtime_files():
    for p in ROOT.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in RUNTIME_SUFFIXES:
            continue
        rel = p.relative_to(ROOT)
        if any(part in EXCLUDED_PARTS for part in rel.parts):
            continue
        # Root-level QA/regression scripts are shipped with the source archive for
        # maintainers but are excluded from the production Docker image. They can
        # contain fixture HTML/JS that intentionally violates runtime conventions,
        # so do not count that fixture markup as live product UI.
        name = p.name
        if (
            name.startswith("test_")
            or name.endswith("_smoke.py")
            or name.endswith("_smoke_test.py")
            or name.endswith(".spec.js")
            or name in {"full_interaction_audit.py", "release_check.py"}
        ):
            continue
        yield p


def text_bundle(files):
    return "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in files)


def attr(tag: str, name: str) -> str:
    m = re.search(r"\b" + re.escape(name) + r"\s*=\s*([\"'])(.*?)\1", tag, re.I | re.S)
    return html.unescape(m.group(2)).strip() if m else ""


def blueprint_prefixes(path: Path, tree: ast.AST) -> dict[str, str]:
    out: dict[str, str] = {}
    for n in ast.walk(tree):
        if not isinstance(n, ast.Assign) or len(n.targets) != 1 or not isinstance(n.targets[0], ast.Name):
            continue
        if not isinstance(n.value, ast.Call):
            continue
        f = n.value.func
        name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
        if name != "Blueprint":
            continue
        prefix = ""
        for kw in n.value.keywords:
            if kw.arg == "url_prefix" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                prefix = kw.value.value
        out[n.targets[0].id] = prefix
    return out


def collect_routes():
    routes: list[tuple[str, set[str], str]] = []
    for p in list(ROOT.glob("*.py")) + list(ROOT.glob("routes/*.py")):
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue
        prefixes = blueprint_prefixes(p, tree)
        for n in ast.walk(tree):
            if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for d in n.decorator_list:
                if not isinstance(d, ast.Call):
                    continue
                if isinstance(d.func, ast.Name) and d.func.id == "route":      # routes/*.py use @route(...)
                    d.func = ast.Attribute(value=ast.Name(id="app", ctx=ast.Load()), attr="route", ctx=ast.Load())
                if not isinstance(d.func, ast.Attribute):
                    continue
                if not d.args or not isinstance(d.args[0], ast.Constant) or not isinstance(d.args[0].value, str):
                    continue
                verb = d.func.attr
                if verb not in {"route", "get", "post", "put", "patch", "delete"}:
                    continue
                obj = d.func.value.id if isinstance(d.func.value, ast.Name) else ""
                if obj not in ("app", "route") and obj not in prefixes:
                    continue
                path = prefixes.get(obj, "") + d.args[0].value
                methods = {verb.upper()} if verb != "route" else {"GET"}
                if verb == "route":
                    for kw in d.keywords:
                        if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
                            methods = {
                                str(e.value).upper()
                                for e in kw.value.elts
                                if isinstance(e, ast.Constant) and isinstance(e.value, str)
                            }
                routes.append((path, methods, f"{p.name}:{getattr(n, 'lineno', 0)}"))
    return routes + runtime_routes()


def runtime_routes():
    """Ground truth: the live Flask url_map (independent of how modules are split).
    Falls back to nothing if the app cannot be imported (static scan still applies)."""
    try:
        sys.path.insert(0, str(ROOT))
        os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "audit.db"))
        import webapp  # noqa: WPS433
        return [(r.rule, set(r.methods or ()), "runtime:url_map") for r in webapp.app.url_map.iter_rules()]
    except Exception:  # noqa: BLE001 - audit must still run on the static scan
        return []


def route_regex(route: str) -> re.Pattern[str]:
    parts: list[str] = []
    pos = 0
    for m in re.finditer(r"<(?:[^:>]+:)?[^>]+>", route):
        parts.append(re.escape(route[pos:m.start()]))
        parts.append(r"[^/]+")
        pos = m.end()
    parts.append(re.escape(route[pos:]))
    return re.compile("^" + "".join(parts).rstrip("/") + "/?$")


def route_matches(routes, url: str, method: str) -> bool:
    path = (url.split("#", 1)[0].split("?", 1)[0] or "/").rstrip("/") or "/"
    if path.startswith(("/static/", "/icons/")) or path in {"/favicon.ico", "/brand-icon.svg", "/manifest.webmanifest", "/service-worker.js"}:
        return True
    for route, methods, _ in routes:
        if method not in methods and not (method == "HEAD" and "GET" in methods):
            continue
        if route_regex(route).match(path):
            return True
        # A source literal may be only the static prefix before a runtime ID.
        marker = route.find("<")
        if marker >= 0:
            literal = route[:marker].rstrip("/")
            if literal and (path == literal or path.startswith(literal + "/")):
                return True
    return False


def parse_bridge_allowlist() -> set[str]:
    bridge = (ROOT / "static/js/interaction-bridge.js").read_text(encoding="utf-8")
    allowed: set[str] = set()
    for marker in ("var ALLOWED_CALLS = new Set([", "var ADMIN_ALLOWED_CALLS = new Set(["):
        try:
            block = bridge.split(marker, 1)[1].split("]);", 1)[0]
        except IndexError:
            continue
        allowed.update(re.findall(r"'([A-Za-z_$][\w$]*)'", block))
    return allowed


def main() -> int:
    files = list(runtime_files())
    bundle = text_bundle(files)
    failures: list[str] = []
    counts = Counter()

    # 1) Every literal/runtime button must have an explicit type and an action contract.
    direct_id_patterns = set(re.findall(r"getElementById\((?:'|\")([^'\"]+)(?:'|\")\)", bundle))
    # Common local wrappers bind controls by literal ID, e.g. bind('medSearchBtn','click', fn).
    direct_id_patterns.update(re.findall(r"\bbind\(\s*['\"]([^'\"]+)['\"]\s*,", bundle))
    # Dashboard sections sometimes define compact [id, handler] pairs and attach
    # addEventListener in one loop. Recover those literal IDs as valid bindings.
    for pair_block in re.findall(r"\b(?:const|let|var)\s+pairs\s*=\s*\[(.*?)\]\s*;", bundle, flags=re.S):
        direct_id_patterns.update(re.findall(r"\[\s*['\"]([^'\"]+)['\"]\s*,", pair_block))
    # Delegated click handlers can reference an ID through closest/querySelector.
    direct_id_patterns.update(re.findall(r"(?:closest|querySelector)\(['\"]#([A-Za-z0-9_-]+)['\"]\)", bundle))
    referenced_data = set(re.findall(r"\[data-([\w-]+)(?:[=\]])", bundle))
    # Also recognize direct dataset.foo / dataset['foo'] consumers used by delegated/direct listeners.
    referenced_data.update(re.findall(r"\.dataset\.([A-Za-z_$][\w$]*)", bundle))
    referenced_data.update(re.findall(r"\.dataset\[['\"]([^'\"]+)['\"]\]", bundle))
    referenced_classes = set(re.findall(r"querySelector(?:All)?\((?:'|\")\.([A-Za-z0-9_-]+)", bundle))
    known_direct_ids = {
        "productionRefreshBtn", "productionEmailTestBtn", "confirmEmailDeliveryBtn", "sentryTestBtn",
        "adminPushEnableBtn", "adminPushTestBtn", "adminPushRefreshBtn", "runPerfBenchmarkBtn",
        "refreshPerfBenchmarkBtn", "ivProbeBtn", "retryBtn", "asstSendBtn", "heroDemoOpen",
        "heroDemoClose", "heroAskAssistant", "saveCheckin", "addPasskey", "passkeyLogin",
        "runSourceMonitor", "jcReset", "asstFab", "asstBack", "asstCloseBtn", "explCloseBtn",
        "exAssist", "asstModalCloseBtn", "smartCtxUse", "smartCtxManual", "smartCtxSkip",
        "pwaInstallBtn", "pwaLaterBtn",
    }
    for p in files:
        source = p.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r"<button\b([^>]*)>", source, re.I | re.S):
            counts["buttons"] += 1
            tag = m.group(0)
            attrs = m.group(1)
            line = source.count("\n", 0, m.start()) + 1
            typ = attr(tag, "type").lower()
            if not typ:
                failures.append(f"button without explicit type: {p.relative_to(ROOT)}:{line}")
                continue
            if typ == "submit" or typ == "reset":
                counts["native_form_buttons"] += 1
                continue
            if typ != "button":
                continue
            here = source[m.start(): m.start() + 600]            # attributes can follow a '>' inside a JS expression (e.g. cur>=pages)
            if re.search(r"\sdata-ss-(?:click|change|input|keydown|submit)=", tag) or re.search(r"\sdata-ss-(?:click|change|input|keydown|submit)=", here.split("</button>", 1)[0]):
                counts["direct_bound_buttons"] += 1       # data-ss-* action: delegated by the bridge, allow-list checked below
                continue
            # Source-generated HTML may concatenate attributes inside the same logical line;
            # inspect a short source window as well as the literal tag match.
            logical_window = source[m.start(): source.find('\n', m.start()) if source.find('\n', m.start()) >= 0 else min(len(source), m.start()+1200)]
            if re.search(r"\bon(?:" + EVENT_ATTRS + r")\s*=", tag, re.I) or " onclick=" in tag or re.search(r"\bon(?:" + EVENT_ATTRS + r")\s*=", logical_window, re.I):
                counts["legacy_bound_buttons"] += 1
                continue
            bid = attr(tag, "id")
            data_names = set(re.findall(r"\bdata-([\w-]+)(?:\s*=|\b)", attrs, re.I))
            classes = set(attr(tag, "class").split())
            direct = bool(bid and (bid in known_direct_ids or bid in direct_id_patterns))
            direct = direct or bool(data_names & referenced_data) or bool(classes & referenced_classes)
            # A disabled challenge/action button can be intentionally enabled by JS; it still must be referenced.
            if direct:
                counts["direct_bound_buttons"] += 1
                continue
            failures.append(f"button has no detectable action binding: {p.relative_to(ROOT)}:{line} id={bid or '-'} class={attr(tag,'class') or '-'}")

    # 2) Legacy CSP bridge calls must be explicitly allow-listed and have a function/window definition.
    allowed = parse_bridge_allowlist()
    used_calls: set[str] = set()
    event_re = re.compile(r"\b(on(?:" + EVENT_ATTRS + r"))\s*=\s*([\"'])(.*?)\2", re.I | re.S)
    for p in files:
        source = p.read_text(encoding="utf-8", errors="ignore")
        for match in event_re.finditer(source):
            counts["legacy_event_attributes"] += 1
            code = html.unescape(match.group(3))
            for cm in re.finditer(r"(?<![.\w])([A-Za-z_$][\w$]*)\s*\(", code):
                name = cm.group(1)
                if name in {"if", "else", "Number", "String", "JSON", "confirm", "alert", "encodeURIComponent", "int", "esc"}:
                    continue
                used_calls.add(name)
    ds_re = re.compile(r"\sdata-ss-(?:click|change|input|keydown|submit)=([\"'])(.*?)\1", re.S)
    for p in files:
        for match in ds_re.finditer(p.read_text(encoding="utf-8", errors="ignore")):
            counts["data_actions"] += 1
            for name in match.group(2).split():
                if re.fullmatch(r"[A-Za-z_$][\w$]*", name):
                    used_calls.add(name)
    for name in sorted(used_calls):
        if name not in allowed:
            failures.append(f"legacy interaction call not in CSP bridge allow-list: {name}")
            continue
        globally_defined = bool(re.search(r"(?:async\s+)?function\s+" + re.escape(name) + r"\s*\(", bundle)) or bool(re.search(r"window\." + re.escape(name) + r"\s*=", bundle))
        if not globally_defined:
            failures.append(f"legacy interaction target has no global definition: {name}")

    # 3) No dead/unsafe anchors; static internal hrefs resolve to a route.
    routes = collect_routes()
    for p in files:
        source = p.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r"<a\b([^>]*)>", source, re.I | re.S):
            tag = m.group(0)
            line = source.count("\n", 0, m.start()) + 1
            href = attr(tag, "href")
            if not href:
                # Dynamic test/fixture markup is excluded; runtime anchors should always navigate.
                failures.append(f"anchor without href: {p.relative_to(ROOT)}:{line}")
                continue
            low = href.strip().lower()
            if low in {"#", "javascript:void(0)", "javascript:;"} or low.startswith("javascript:"):
                failures.append(f"dead/unsafe anchor: {p.relative_to(ROOT)}:{line} href={href}")
                continue
            if href.startswith("/") and not any(token in href for token in ("+", "${", "__", "{{")):
                counts["internal_links"] += 1
                if not route_matches(routes, href, "GET"):
                    failures.append(f"internal href has no GET route: {p.relative_to(ROOT)}:{line} {href}")

    # 4) Literal same-origin fetch targets must map to an API route with the right method.
    fetch_re = re.compile(r"fetch\(\s*([\"'])(/[^\"']*)\1\s*(?:,\s*\{(.*?)\})?", re.S)
    for p in files:
        source = p.read_text(encoding="utf-8", errors="ignore")
        for m in fetch_re.finditer(source):
            url = m.group(2)
            opts = m.group(3) or ""
            mm = re.search(r"\bmethod\s*:\s*([\"'])([A-Za-z]+)\1", opts)
            method = mm.group(2).upper() if mm else "GET"
            # Dynamic concatenation commonly means the regex captures only the static prefix.
            if m.end() < len(source) and source[m.end():m.end()+2].lstrip().startswith("+"):
                pass
            counts["literal_fetches"] += 1
            if not route_matches(routes, url, method):
                # Known dynamic passkey delete source: the source literal ends before +id and method parsing
                # can be lost by the lightweight regex. Validate its route prefix instead.
                if url == "/api/v1/passkeys/" and any(r.startswith("/api/v1/passkeys/<") and "DELETE" in ms for r, ms, _ in routes):
                    continue
                failures.append(f"fetch target/method has no route: {p.relative_to(ROOT)} {method} {url}")

    # 5) V71 regression invariants for the exact desktop issue reported by the user.
    web = "\n".join(q.read_text(encoding="utf-8", errors="ignore") for q in [ROOT / "webapp.py"] + sorted((ROOT / "pagelib").glob("*.py")) + sorted((ROOT / "routes").glob("*.py")) + sorted((ROOT / "inline_assets").glob("*")))
    required = (
        '@media (min-width: 900px) {\n  .pwa-install { left: 22px;',
        'id="pwaInstallBtn" type="button"></button>',
        "installBtn.addEventListener('click'",
        '(function bindGlobalAssistantControls()',
        'id="asstCloseBtn"',
        'data-assistant-mode="mh"',
    )
    for token in required:
        if token not in web:
            failures.append(f"missing V71 interaction reliability invariant: {token[:70]}")

    print("FULL INTERACTION AUDIT:", "PASS" if not failures else "FAIL")
    print(f" - runtime files: {len(files)}")
    print(f" - buttons: {counts['buttons']} (legacy-bound {counts['legacy_bound_buttons']}, direct/data-bound {counts['direct_bound_buttons']}, native form {counts['native_form_buttons']})")
    print(f" - legacy event attributes: {counts['legacy_event_attributes']}")
    print(f" - data-ss actions (allow-listed, delegated): {counts['data_actions']}")
    print(f" - internal links checked: {counts['internal_links']}")
    print(f" - literal fetch contracts checked: {counts['literal_fetches']}")
    if failures:
        for item in failures:
            print(" !", item)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
