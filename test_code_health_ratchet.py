"""V253: code-health ratchets. Numbers may go down, never up; copies must not drift."""
import glob
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = json.loads((ROOT / "code_health_baseline.json").read_text(encoding="utf-8"))
SRC = [Path(f) for f in glob.glob(str(ROOT / "*.py")) if not Path(f).name.startswith("test_")]
# The split packages count too: moving code out of webapp.py must never hide debt from the ratchets.
SRC += [Path(f) for d in ("routes", "pagelib", "services") for f in glob.glob(str(ROOT / d / "*.py"))]
# innerHTML also counts where Python used to carry the browser code: inline_assets/ and the chat page scripts.
BROWSER_SRC = [Path(f) for f in glob.glob(str(ROOT / "inline_assets" / "*")) if Path(f).is_file()] + [Path(f) for f in glob.glob(str(ROOT / "static" / "js" / "chat" / "*.js"))]

DUPLICATES = [
    ("chat_view.py", "views/chat_view.py"),
    ("design-system.css", "static/css/design-system.css"),
    ("offline.css", "static/css/offline.css"),
    ("v83_user_tools.css", "static/css/v83_user_tools.css"),
    ("app-shell-v111.css", "static/css/app-shell-v111.css"),
    ("interaction-bridge.js", "static/js/interaction-bridge.js"),
    ("manage-profile.js", "static/js/manage-profile.js"),
    ("mini-charts.js", "static/js/mini-charts.js"),
    ("offline.js", "static/js/offline.js"),
    ("e2e_browser.py", "tools/e2e_browser.py"),
]


def _count(pattern):
    return sum(len(re.findall(pattern, p.read_text(encoding="utf-8"))) for p in SRC)


def test_broad_except_does_not_grow():
    n = _count(r"except\s+Exception\b")
    assert n <= BASE["except_exception_max"], "except Exception grew to %d (limit %d); catch specific errors" % (n, BASE["except_exception_max"])


def test_innerhtml_in_python_sources_does_not_grow():
    n = sum(p.read_text(encoding="utf-8", errors="ignore").count("innerHTML") for p in SRC + BROWSER_SRC)
    assert n <= BASE["innerhtml_python_max"], "innerHTML grew to %d (limit %d); use textContent or esc()" % (n, BASE["innerhtml_python_max"])


def test_standalone_static_js_has_no_innerhtml():
    n = sum(Path(f).read_text(encoding="utf-8").count("innerHTML") for f in glob.glob(str(ROOT / "static" / "js" / "*.js")))
    assert n <= BASE["innerhtml_static_js_max"]


def test_duplicated_assets_are_identical():
    for a, b in DUPLICATES:
        assert (ROOT / a).read_bytes() == (ROOT / b).read_bytes(), "%s and %s drifted apart" % (a, b)


def test_no_module_level_function_is_defined_twice():
    """A second ``def`` with the same name silently replaces the first at runtime (this hid a split follow-up system)."""
    import ast
    dups = []
    for p in SRC:
        tree = ast.parse(p.read_text(encoding="utf-8"))
        seen = {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.decorator_list:
                if node.name in seen:
                    dups.append("%s:%s (lines %d and %d)" % (p.name, node.name, seen[node.name], node.lineno))
                seen[node.name] = node.lineno
    allowed = set(BASE.get("duplicate_defs_allowed", []))
    new = [d for d in dups if d.split(" ")[0] not in allowed]
    assert not new, "duplicate function definitions: %s" % new


def test_blood_parser_layering_is_explicit():
    src = (ROOT / "blood_test.py").read_text(encoding="utf-8")
    assert "_parse_blood_text_v142" in src and "_V142_parse_blood_text" not in src
