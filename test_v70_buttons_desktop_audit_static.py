import source_bundle
import versioning
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()
CHAT = source_bundle.chat_view_text()
BRIDGE = (ROOT / "static" / "js" / "interaction-bridge.js").read_text(encoding="utf-8")
E2E = (ROOT / "tools" / "e2e_browser.py").read_text(encoding="utf-8")
RC = (ROOT / "release_candidate.py").read_text(encoding="utf-8")
SW = (ROOT / "service-worker.js").read_text(encoding="utf-8")


def test_home_primary_actions_have_native_or_direct_handlers():
    assert 'id="heroStartAnalysis" href="/chat"' in WEB
    assert 'id="heroAskAssistant" href="/home?assistant=general"' in WEB
    assert 'id="heroDemoOpen" type="button"' in WEB
    assert 'id="heroDemoClose" type="button"' in WEB
    assert 'id="heroDemoBackdrop"' in WEB
    # Home hero no longer depends on CSP-blocked executable inline attributes.
    hero = WEB[WEB.index('<section class="ss-home-hero"'):WEB.index('</section>', WEB.index('<section class="ss-home-hero"')) + 10]
    assert 'onclick="openHeroDemoModal()"' not in hero
    assert 'onclick="closeHeroDemoModal()"' not in hero
    assert 'onclick="asstToggle()"' not in hero
    for token in (
        "demoOpen.addEventListener('click', openDemo)",
        "demoClose.addEventListener('click', closeDemo)",
        "demoBackdrop.addEventListener('click', closeDemo)",
        "askAssistant.addEventListener('click'",
    ):
        assert token in WEB


def test_desktop_hero_has_stable_physical_grid_and_click_layer():
    assert "V70 desktop hero + clickability hardening" in WEB
    assert "direction:ltr!important" in WEB
    assert "body.ss-home-page .ss-hero-demo{grid-column:1!important" in WEB
    assert "body.ss-home-page .ss-hero-copy" in WEB and "grid-column:2!important" in WEB
    assert "body.ss-home-page .ss-hero-brand" in WEB and "white-space:nowrap!important" in WEB
    assert "body.ss-home-page .ss-hero-actions{position:relative!important;z-index:30!important;pointer-events:auto!important}" in WEB
    assert "body.ss-home-page .ss-hero-demo{pointer-events:none!important" in WEB
    assert "body.ss-home-page .ss-hero-primary,body.ss-home-page .ss-hero-secondary,body.ss-home-page .ss-hero-demo-cta{box-sizing:border-box!important;max-width:100%!important}" in WEB


def test_all_legacy_inline_calls_are_allowlisted_by_csp_bridge():
    blocks = []
    for name in ("ALLOWED_CALLS", "ADMIN_ALLOWED_CALLS"):
        m = re.search(r"var " + name + r" = new Set\(\[(.*?)\]\);", BRIDGE, re.S)
        assert m
        blocks.append(m.group(1))
    allowed = set(re.findall(r"'([A-Za-z_$][\w$]*)'", "\n".join(blocks)))
    event_re = re.compile(r"\son(?:click|change|input|submit|keydown|keyup|load|error|focus|blur)\s*=\s*([\"'])(.*?)\1", re.I | re.S)
    used = set()
    for source in (WEB, CHAT, (ROOT / "dashboard.py").read_text(encoding="utf-8"), (ROOT / "v47_routes.py").read_text(encoding="utf-8")):
        for match in event_re.finditer(source):
            value = match.group(2)
            for call in re.findall(r"(?<![.\w])([A-Za-z_$][\w$]*)\s*\(", value):
                if call not in {"if", "else", "Number", "int", "esc"}:
                    used.add(call)
    assert used - allowed == set()


def test_all_literal_buttons_have_explicit_type():
    for source in (WEB, CHAT, (ROOT / "dashboard.py").read_text(encoding="utf-8"), (ROOT / "v47_routes.py").read_text(encoding="utf-8")):
        for tag in re.findall(r"<button\b[^>]*>", source, flags=re.I | re.S):
            # Jinja / string-fragment generated tags can be syntactically partial in source;
            # complete literal tags must always state their type.
            if "{{" in tag or "'+" in tag or 'f"' in tag:
                continue
            assert re.search(r"\btype\s*=\s*[\"'](?:button|submit|reset)[\"']", tag, re.I), tag


def test_browser_e2e_now_clicks_home_ctas():
    assert '#heroDemoOpen' in E2E
    assert '#heroDemoClose' in E2E
    assert '#heroAskAssistant' in E2E
    assert '#heroStartAnalysis' in E2E
    assert 'page.wait_for_url("**/chat")' in E2E


def test_release_is_v70_and_cache_is_bumped():
    assert versioning.APP_VERSION == __import__("release_candidate").APP_VERSION
    assert versioning.RC_ID == __import__("release_candidate").RC_ID
    assert versioning.SW_CACHE in SW


def test_runtime_literal_buttons_across_site_have_explicit_type():
    skip = {"tests", "tools", ".pytest_cache", "__pycache__", ".git", "migrations"}
    candidates = []
    for pattern in ("*.py", "*.html"):
        for path in ROOT.rglob(pattern):
            if any(part in skip for part in path.parts):
                continue
            if path.name.startswith("test_") or path.name.endswith("_smoke_test.py") or path.name.endswith("_smoke.py") or path.name in {"full_interaction_audit.py", "release_check.py"}:
                continue
            candidates.append(path)
    checked = 0
    total = 0
    for path in candidates:
        source = path.read_text(encoding="utf-8", errors="ignore")
        for tag in re.findall(r"<button\b[^>]*>", source, flags=re.I | re.S):
            total += 1
            if "{{" in tag or "'+" in tag or 'f"' in tag:
                continue
            checked += 1
            assert re.search(r"\btype\s*=\s*[\"'](?:button|submit|reset)[\"']", tag, re.I), f"{path}: {tag}"
    assert total >= 240
    assert checked >= 200
