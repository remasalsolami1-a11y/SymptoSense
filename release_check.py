#!/usr/bin/env python3
"""Fast, dependency-light pre-release checks for SymptoSense.

This script intentionally uses only the Python standard library so it can run
before third-party dependencies are installed. The full pytest suite remains the
canonical verification after ``pip install -r requirements.txt -r requirements-dev.txt``.
"""
from __future__ import annotations

import os
import ast
import json
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent if HERE.name == "tools" else HERE
FAILURES: list[str] = []


def _web_modules() -> list:
    """webapp.py plus the modules split out of it (routes/, pagelib/, services/)."""
    out = [ROOT / "webapp.py"]
    for folder in ("routes", "pagelib", "services"):
        out += sorted(p for p in (ROOT / folder).glob("*.py") if p.name != "__init__.py")
    return out


def _web_text() -> str:
    """Python modules + the large static assets that used to be string literals inside webapp.py."""
    parts = [p.read_text(encoding="utf-8") for p in _web_modules()]
    parts += [p.read_text(encoding="utf-8", errors="ignore") for p in sorted((ROOT / "inline_assets").glob("*")) if p.is_file()]
    return "\n".join(parts)


def _runtime_source_bundle() -> str:
    """Return source text across the refactored web runtime modules."""
    paths = _web_modules() + [ROOT / "views" / "chat_view.py", ROOT / "web_security.py"] + sorted((ROOT / "static" / "js" / "chat").glob("*.js"))
    return "\n".join(path.read_text(encoding="utf-8") for path in paths if path.exists())


def fail(message: str) -> None:
    FAILURES.append(message)


def check_python_compile() -> None:
    """Syntax-check Python without creating __pycache__/pyc release artifacts."""
    for path in sorted(ROOT.rglob("*.py")):
        if any(part in {".venv", "venv", "node_modules"} for part in path.parts):
            continue
        try:
            source = path.read_text(encoding="utf-8")
            compile(source, str(path.relative_to(ROOT)), "exec")
        except Exception as exc:
            fail(f"Python compile failed for {path.relative_to(ROOT)}: {type(exc).__name__}")


def check_release_tree_hygiene() -> None:
    """Release source trees must not contain generated test/bytecode artifacts."""
    bad = []
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT)
        if path.is_dir() and path.name in {"__pycache__", ".pytest_cache"}:
            bad.append(str(rel) + "/")
        elif path.is_file() and (path.suffix in {".pyc", ".pyo"} or path.name in {".DS_Store"}):
            bad.append(str(rel))
    if bad:
        preview = ", ".join(sorted(bad)[:8])
        extra = f" (+{len(bad)-8} more)" if len(bad) > 8 else ""
        fail("Generated/cache artifacts are present in release tree: " + preview + extra)

    # Guard against a flattened .pytest_cache accidentally replacing project files.
    cache_tag = ROOT / "CACHEDIR.TAG"
    if cache_tag.exists():
        fail("CACHEDIR.TAG must not be present at the project root")
    readme = ROOT / "README.md"
    if readme.exists() and readme.read_text(encoding="utf-8", errors="ignore").lstrip().startswith("# pytest cache directory #"):
        fail("README.md was replaced by pytest cache metadata")
    gitignore = ROOT / ".gitignore"
    if gitignore.exists():
        gi = gitignore.read_text(encoding="utf-8", errors="ignore")
        if "Created by pytest automatically" in gi and gi.strip().endswith("*"):
            fail(".gitignore was replaced by pytest cache metadata")


def check_json_files() -> None:
    for rel in ("railway.json", "manifest.webmanifest", "ml_model.json", "release_metrics.json", "runtime_data/safety_cases.json"):
        path = ROOT / rel
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            fail(f"{rel} is invalid JSON: {type(exc).__name__}")


def check_runtime_competition_assets() -> None:
    """Keep competition evidence available after tests/ is excluded by Docker."""
    metrics_path = ROOT / "release_metrics.json"
    safety_path = ROOT / "runtime_data" / "safety_cases.json"
    try:
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        safety = json.loads(safety_path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"Runtime competition assets could not be loaded: {type(exc).__name__}")
        return
    if not isinstance(safety, list) or not safety:
        fail("runtime_data/safety_cases.json must contain at least one synthetic safety case")
        return
    expected_safety = int(metrics.get("safety_regression_cases") or 0)
    if expected_safety != len(safety):
        fail(f"release_metrics safety_regression_cases={expected_safety} but runtime fixture has {len(safety)}")
    source_test_files = len(list((ROOT / "tests").glob("test_*.py"))) if (ROOT / "tests").exists() else 0
    metric_test_files = int(metrics.get("test_files") or 0)
    if source_test_files and metric_test_files != source_test_files:
        fail(f"release_metrics test_files={metric_test_files} but source tree has {source_test_files}")
    v50 = (ROOT / "v50_wow.py").read_text(encoding="utf-8")
    v51 = (ROOT / "v51_innovation.py").read_text(encoding="utf-8")
    for runtime in (v50, v51):
        if 'runtime_data" / "safety_cases.json' not in runtime:
            fail("Competition runtime does not reference packaged synthetic safety cases")
            break


def check_sqlite_integrity() -> None:
    path = ROOT / "symptosense.db"
    if not path.exists():
        return
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        row = conn.execute("PRAGMA integrity_check").fetchone()
        conn.close()
        if not row or row[0] != "ok":
            fail(f"SQLite integrity_check returned: {row!r}")
    except Exception as exc:
        fail(f"SQLite integrity check failed: {type(exc).__name__}")



def check_release_database_cleanliness() -> None:
    """The committed/template DB must not ship runtime/user-derived rows."""
    path = ROOT / "symptosense.db"
    if not path.exists():
        return
    runtime_tables = (
        "ss_users", "records", "results", "blood_tests", "ss_chat_history",
        "feedback", "assistant_feedback", "followups", "family_members",
        "ss_health_profiles", "med_plans", "med_logs", "med_reminders",
        "visits", "ss_usage_events", "mk_unmatched_log",
    )
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        existing = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        dirty = []
        for table in runtime_tables:
            if table not in existing:
                continue
            count = int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] or 0)
            if count:
                dirty.append(f"{table}={count}")
        conn.close()
        if dirty:
            fail("Release SQLite contains runtime/user-derived rows: " + ", ".join(dirty))
    except Exception as exc:
        fail(f"Release database cleanliness check failed: {type(exc).__name__}")

def check_release_metadata() -> None:
    """VERSION is the single source; every static copy must agree with it."""
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    major = version.split(".")[0]
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    sw = (ROOT / "service-worker.js").read_text(encoding="utf-8")
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    metrics = (ROOT / "release_metrics.json").read_text(encoding="utf-8")
    for name in ("release_candidate.py", "research_study.py"):
        src = (ROOT / name).read_text(encoding="utf-8")
        if "versioning" not in src:
            fail("%s must take its version from versioning.py (VERSION file)" % name)
        if re.search(r'"\d+\.\d+\.\d+"', src):
            fail("%s hardcodes a version number" % name)
    if f"APP_VERSION={version}" not in env:
        fail("APP_VERSION is inconsistent between VERSION and .env.example")
    if f"RELEASE_CANDIDATE_ID=SymptoSense-v{major}" not in env:
        fail("RELEASE_CANDIDATE_ID is inconsistent between VERSION and .env.example")
    if f"symptosense-shell-v{major}" not in sw:
        fail("Service-worker cache namespace was not bumped for the current major release")
    if f"build profile: V{major}" not in docker:
        fail("Dockerfile build profile does not match VERSION")
    if f'"delivery_revision": "V{major}"' not in metrics:
        fail("release_metrics.json delivery_revision does not match VERSION")


def check_security_invariants() -> None:
    web = _web_text()
    sec = (ROOT / "web_security.py").read_text(encoding="utf-8")
    required_web = (
        "SESSION_COOKIE_HTTPONLY=True",
        "SESSION_COOKIE_SECURE=_secure_cookie",
        "SESSION_REFRESH_EACH_REQUEST=False",
        "TRUSTED_HOSTS=_trusted_hosts or None",
        "MAX_API_JSON_BYTES",
        'response.headers.setdefault("X-Content-Type-Options", "nosniff")',
        'response.headers.setdefault("X-Frame-Options", "DENY")',
    )
    for token in required_web:
        if token not in web:
            fail(f"Missing web security invariant: {token}")
    for token in ("base-uri 'none'", "object-src 'none'", "frame-ancestors 'none'"):
        if token not in sec:
            fail(f"Missing CSP invariant: {token}")
    if "unsafe-eval" in sec:
        fail("CSP must not allow unsafe-eval")
    if "script-src 'self' 'unsafe-inline'" in sec:
        fail("CSP script elements must not rely on broad unsafe-inline")
    if "interaction-bridge.js" not in web:
        fail("CSP-safe interaction bridge is missing from rendered page shell")
    for token in ("script-src-elem 'self'", "script-src-attr 'none'", "style-src-elem 'self'", "style-src-attr 'unsafe-inline'", "nonce-"):
        if token not in sec:
            fail(f"Missing nonce-migration CSP invariant: {token}")



def check_javascript_syntax() -> None:
    """Syntax-check standalone and inline JavaScript when Node is available.

    Inline scripts are extracted from literal HTML strings in webapp.py. Page
    placeholders such as ``__PT__`` are valid JS identifiers, so this catches
    accidental quote/bracket regressions without importing Flask.
    """
    node = shutil.which("node")
    if not node:
        print(" - JavaScript syntax: skipped (node unavailable)")
        return

    standalone_files = [ROOT / "service-worker.js"] + sorted((ROOT / "static" / "js").rglob("*.js"))
    for standalone in standalone_files:
        if not standalone.exists():
            continue
        proc = subprocess.run([node, "--check", str(standalone)], capture_output=True, text=True)
        if proc.returncode:
            fail(f"{standalone.relative_to(ROOT)} failed JavaScript syntax check")

    scripts: list[tuple[str, int, str]] = []
    for html_asset in sorted((ROOT / "inline_assets").glob("*.html")):
        for match in re.finditer(r"<script(?:\s[^>]*)?>(.*?)</script>", html_asset.read_text(encoding="utf-8"), flags=re.I | re.S):
            scripts.append((html_asset.name, 0, match.group(1)))
    for source_path in _web_modules() + [
        ROOT / "views" / "chat_view.py",
        ROOT / "dashboard.py",
        ROOT / "v47_routes.py",
    ]:
        if not source_path.exists():
            continue
        try:
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue  # Python compile check reports this already.
        for node_obj in ast.walk(tree):
            if isinstance(node_obj, ast.Constant) and isinstance(node_obj.value, str) and "<script" in node_obj.value.lower():
                for match in re.finditer(r"<script(?:\s[^>]*)?>(.*?)</script>", node_obj.value, flags=re.I | re.S):
                    scripts.append((source_path.name, getattr(node_obj, "lineno", 0), match.group(1)))
    for filename, line, script in scripts:
        # Ignore Python formatting helper templates such as <script>%s</script>;
        # they are containers for already-rendered script text, not browser JS.
        if script.strip() in {"%s", "%r"}:
            continue
        # Dashboard HTML is a Jinja template. Replace template expressions with
        # harmless JS literals before syntax checking; the browser sees the
        # rendered values, not the ``{{ ... }}`` source tokens.
        prepared = re.sub(r"\{\{.*?\}\}", "null", script, flags=re.S)
        prepared = re.sub(r"\{%.*?%\}", "", prepared, flags=re.S)
        proc = subprocess.run([node, "--check", "-"], input=prepared, capture_output=True, text=True)
        if proc.returncode:
            detail = (proc.stderr or "syntax error").splitlines()[0][:160]
            fail(f"Inline JavaScript syntax failed near {filename}:{line}: {detail}")


def check_xss_regression_invariants() -> None:
    web = _runtime_source_bundle()
    required = (
        "function escAttr(s)",
        "function safeLink(raw)",
        "escAttr(safeLink(r.url))",
        "escAttr(question)",
        "Never trust OCR/LLM-derived content as HTML.",
        "blood_upload_limit + 1",
        "voice_upload_limit + 1",
    )
    for token in required:
        if token not in web:
            fail(f"Missing XSS/upload regression invariant: {token}")
    forbidden = (
        "h += d.text_html || '';",
        "data-question=\"'+esc(question)+'\"",
        "href=\"'+esc(r.url)+'\"",
    )
    for token in forbidden:
        if token in web:
            fail(f"Unsafe legacy rendering pattern returned: {token}")


def check_interaction_bridge_contract() -> None:
    """Ensure every legacy event call is covered by the CSP-safe bridge.

    This allows the enforced CSP to keep ``script-src-attr 'none'`` while older
    server-rendered markup is migrated incrementally without silent dead buttons.
    """
    bridge_path = ROOT / "static" / "js" / "interaction-bridge.js"
    if not bridge_path.exists():
        fail("Missing CSP interaction bridge")
        return
    bridge = bridge_path.read_text(encoding="utf-8")
    dashboard_path = ROOT / "dashboard.py"
    if dashboard_path.exists():
        dashboard = dashboard_path.read_text(encoding="utf-8")
        if re.search(r"\son(?:click|change|input|submit|keydown|keyup|load|error|focus|blur)\s*=", dashboard, re.I) and "/static/js/interaction-bridge.js" not in dashboard:
            fail("Dashboard uses legacy inline event attributes but does not load the CSP-safe interaction bridge")
    if "eval(" in bridge or "new Function(" in bridge:
        fail("Interaction bridge must not use eval/new Function")
    try:
        allow_block = bridge.split("var ALLOWED_CALLS = new Set([", 1)[1].split("]);", 1)[0]
        admin_block = bridge.split("var ADMIN_ALLOWED_CALLS = new Set([", 1)[1].split("]);", 1)[0]
    except IndexError:
        fail("Interaction bridge allow-list could not be parsed")
        return
    allowed = set(re.findall(r"'([A-Za-z_$][\w$]*)'", allow_block))
    allowed.update(re.findall(r"'([A-Za-z_$][\w$]*)'", admin_block))
    used: set[str] = set()
    event_re = re.compile(
        r"\s(on(?:click|change|input|submit|keydown|keyup|load|error|focus|blur))\s*=\s*([\"'])(.*?)\2",
        re.I | re.S,
    )
    for source_path in _web_modules() + sorted((ROOT / "inline_assets").glob("*.html")) + sorted((ROOT / "static" / "js" / "chat").glob("*.js")) + [
        ROOT / "views" / "chat_view.py",
        ROOT / "dashboard.py",
        ROOT / "v47_routes.py",
    ]:
        if not source_path.exists():
            continue
        text = source_path.read_text(encoding="utf-8")
        for match in event_re.finditer(text):
            value = match.group(3)
            for call in re.finditer(r"(?:^|;|\))\s*([A-Za-z_$][\w$]*)\s*\(", value):
                name = call.group(1)
                if name not in {"if", "Number", "int", "esc"}:
                    used.add(name)
    missing = sorted(used - allowed)
    if missing:
        fail("Interaction bridge is missing legacy calls: " + ", ".join(missing))



def check_translation_quality() -> None:
    checker = ROOT / "tools" / "check_translations.py"
    if not checker.exists():
        fail("Missing translation quality checker")
        return
    proc = subprocess.run([sys.executable, str(checker)], capture_output=True, text=True, cwd=str(ROOT))
    if proc.returncode:
        detail = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip().splitlines()
        fail("Translation quality check failed" + (": " + detail[-1][:180] if detail else ""))

def check_no_obvious_committed_secrets() -> None:
    candidates = [ROOT / ".env.example", ROOT / "release_candidate.py"] + _web_modules()
    secret_re = re.compile(r"(?i)(api[_-]?key|password|private[_-]?key|web_secret)\s*=\s*['\"]([A-Za-z0-9_\-]{24,})['\"]")
    for path in candidates:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in secret_re.finditer(text):
            value = match.group(2)
            if value.lower() not in {"your-domain", "example"}:
                fail(f"Possible hard-coded secret in {path.name}: {match.group(1)}")


def check_clinical_signoff_gate() -> None:
    """Production releases are blocked while any medical content area lacks a named clinician's sign-off.

    Active when RELEASE_TARGET=production (the Dockerfile sets the equivalent gate). The only way around it is an
    explicit, logged override: ALLOW_UNSIGNED_CLINICAL=1. Development checks stay green so work can continue.
    """
    if os.environ.get("RELEASE_TARGET", "").strip().lower() != "production":
        return
    import clinical_signoff
    pending = [k for k, a in clinical_signoff.load(clinical_signoff.PATH)["areas"].items() if not clinical_signoff.is_reviewed(a)]
    if not pending:
        return
    if os.environ.get("ALLOW_UNSIGNED_CLINICAL", "") == "1":
        print("WARNING: clinical sign-off OVERRIDDEN for production; pending areas: " + ", ".join(pending))
        return
    FAILURES.append("clinical sign-off pending for: " + ", ".join(pending) + " (set ALLOW_UNSIGNED_CLINICAL=1 only as a deliberate, documented override)")


def main() -> int:
    for check in (
        check_python_compile,
        check_release_tree_hygiene,
        check_json_files,
        check_runtime_competition_assets,
        check_sqlite_integrity,
        check_release_database_cleanliness,
        check_release_metadata,
        check_security_invariants,
        check_javascript_syntax,
        check_xss_regression_invariants,
        check_interaction_bridge_contract,
        check_translation_quality,
        check_no_obvious_committed_secrets,
        check_clinical_signoff_gate,
    ):
        check()
    if FAILURES:
        print("RELEASE CHECK: FAILED")
        for item in FAILURES:
            print(f" - {item}")
        return 1
    print("RELEASE CHECK: PASS")
    print(" - Python compile: ok (no bytecode artifacts created)")
    print(" - Release tree hygiene: clean")
    print(" - JSON files: ok")
    print(" - Runtime competition assets: packaged and consistent")
    print(" - SQLite integrity: ok")
    print(" - Release database cleanliness: ok")
    print(" - Release metadata: consistent")
    print(" - Security invariants: present")
    print(" - JavaScript syntax: ok when Node is available")
    print(" - XSS/upload regression invariants: present")
    print(" - CSP interaction bridge contract: covered")
    print(" - Translation quality gate: passed")
    print(" - Obvious committed secrets: none found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
