import source_bundle
import versioning
from pathlib import Path
import re
import json

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()
DASH = (ROOT / "dashboard.py").read_text(encoding="utf-8")
CHAT = source_bundle.chat_view_text()
CHAT_MIRROR = source_bundle.chat_view_text()
BRIDGE = (ROOT / "static/js/interaction-bridge.js").read_text(encoding="utf-8")
SW = (ROOT / "service-worker.js").read_text(encoding="utf-8")
METRICS = json.loads((ROOT / "release_metrics.json").read_text(encoding="utf-8"))

def _allowlist():
    blocks = []
    for name in ("ALLOWED_CALLS", "ADMIN_ALLOWED_CALLS"):
        m = re.search(r"var " + name + r" = new Set\(\[(.*?)\]\);", BRIDGE, re.S)
        assert m
        blocks.append(m.group(1))
    return set(re.findall(r"'([A-Za-z_$][\w$]*)'", "\n".join(blocks)))

def test_all_literal_inline_calls_are_allowlisted():
    allowed = _allowlist()
    event_re = re.compile(r"\son(?:click|change|input|submit|keydown|keyup|load|error|focus|blur)\s*=\s*([\"'])(.*?)\1", re.I | re.S)
    used = set()
    for source in (WEB, DASH, CHAT, CHAT_MIRROR, (ROOT / "v47_routes.py").read_text(encoding="utf-8")):
        for m in event_re.finditer(source):
            for call in re.findall(r"(?<![.\w])([A-Za-z_$][\w$]*)\s*\(", m.group(2)):
                if call not in {"if", "else", "Number", "String", "JSON", "confirm", "alert", "encodeURIComponent", "int", "esc"}:
                    used.add(call)
    assert used - allowed == set()

def test_mobile_body_sheet_close_has_direct_binding():
    for source in (CHAT, CHAT_MIRROR):
        assert "data-close-body-sheet" in source
        assert "sheet.querySelector('[data-close-body-sheet]')" in source
        assert "closeBtn.addEventListener('click'" in source

def test_admin_lab_actions_have_server_fallbacks():
    assert 'href="/admin/analysis-trials"' in DASH
    assert 'href="/admin/analysis-trials/export.xlsx"' in DASH
    assert '@app.route("/admin/lab-trials", methods=["GET", "POST"])' in WEB

def test_admin_navigation_targets_exist():
    nav = set(re.findall(r'data-view="([A-Za-z0-9_-]+)"', DASH))
    views = set(re.findall(r'id="view-([A-Za-z0-9_-]+)"', DASH))
    assert nav <= views

def test_release_metadata_is_synchronized():
    assert METRICS["delivery_revision"] == versioning.REVISION  # current release metadata
    assert METRICS["test_files"] == len(list(ROOT.glob("test_*.py")))
    assert versioning.SW_CACHE in SW
