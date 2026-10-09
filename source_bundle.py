"""Tests that grep application source use this so they keep working as code moves out of webapp.py.

``webapp_text`` = webapp.py + every module under routes/ + every file under inline_assets/. The tests therefore pin
behaviour/content, not the physical file a piece of code happens to live in.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _legacy_view_of_routes_module(text):
    """Render routes/<group>.py the way the code used to read inside webapp.py: ``@app.route`` plus the original
    protection decorators (login_required, admin_api_required(...)) directly above the ``def`` line."""
    import ast
    tree = ast.parse(text)
    wrappers = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "_WRAPPERS" for t in node.targets):
            wrappers = ast.literal_eval(node.value)
    lines = text.replace("\n@route(", "\n@app.route(").split("\n")
    out, i = [], 0
    # re-parse after the text replacement so line numbers still match (replacement keeps line count)
    tree = ast.parse("\n".join(lines))
    inserts = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and wrappers.get(node.name):
            inserts[node.lineno - 1] = ["@" + w.lstrip("@") for w in wrappers[node.name]]
    for idx, line in enumerate(lines):
        if idx in inserts:
            out.extend(inserts[idx])
        out.append(line)
    return "\n".join(out)


def webapp_text(root=None):
    base = Path(root) if root else ROOT
    parts = [(base / "webapp.py").read_text(encoding="utf-8")]
    for folder, pattern in (("routes", "*.py"), ("pagelib", "*.py"), ("services", "*.py"), ("inline_assets", "*")):
        d = base / folder
        if d.is_dir():
            for p in sorted(d.glob(pattern)):
                if p.is_file():
                    t = p.read_text(encoding="utf-8", newline="")
                    parts.append(_legacy_view_of_routes_module(t) if folder in ("routes", "pagelib", "services") and p.name != "__init__.py" else t)
    return "\n".join(parts)


def python_text(root=None):
    """webapp.py + routes/*.py only (valid Python, for tests that ``ast.parse`` the application code)."""
    base = Path(root) if root else ROOT
    parts = [(base / "webapp.py").read_text(encoding="utf-8")]
    for folder in ("routes", "pagelib", "services"):
        d = base / folder
        if d.is_dir():
            parts += [_legacy_view_of_routes_module(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.py")) if p.name != "__init__.py"]
    return "\n".join(parts)


def segment(marker, root=None):
    """Text from ``marker`` to the end of the single file that contains it (CSS blocks moved to inline_assets/)."""
    base = Path(root) if root else ROOT
    files = [base / "webapp.py"] + [q for f in ("routes", "pagelib", "services") if (base / f).is_dir() for q in sorted((base / f).glob("*.py"))] + sorted((base / "inline_assets").glob("*"))
    for p in files:
        text = p.read_text(encoding="utf-8", newline="")
        i = text.find(marker)
        if i >= 0:
            return text[i:]
    raise ValueError("marker not found: %r" % marker)


def between(start, end=None, root=None):
    """Code between two markers, searched file by file (routes moved out of webapp.py live in routes/*.py).

    Returns text from ``start`` up to ``end`` when both are in the same file, otherwise up to the end of that file."""
    base = Path(root) if root else ROOT
    files = [base / "webapp.py"] + [q for f in ("routes", "pagelib", "services") if (base / f).is_dir() for q in sorted(base.joinpath(f).glob("*.py")) if q.name != "__init__.py"]
    for p in files:
        text = p.read_text(encoding="utf-8")
        if p.parent.name in ("routes", "pagelib", "services"):
            text = _legacy_view_of_routes_module(text)
        i = text.find(start)
        if i < 0:
            continue
        j = text.find(end, i + len(start)) if end else -1
        return text[i:j] if j >= 0 else text[i:]
    raise ValueError("marker not found: %r" % start)


def function_source(name, root=None):
    """Exact source of one top-level function, wherever it lives (webapp.py, routes/, pagelib/, services/)."""
    import ast
    base = Path(root) if root else ROOT
    files = [base / "webapp.py"] + [q for f in ("routes", "pagelib", "services") if (base / f).is_dir() for q in sorted((base / f).glob("*.py"))]
    for p in files:
        text = p.read_text(encoding="utf-8")
        for node in ast.parse(text).body:
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return "\n".join(text.splitlines()[node.lineno - 1:node.end_lineno])
    raise ValueError("function not found: %s" % name)


CHAT_JS_ORDER = ("chat-core", "assistant", "body-map", "clarifications", "symptom-flow", "red-flags", "followup", "data-quality", "analysis-result", "result-tracking", "result-actions", "doctor-summary", "chat-boot")


def chat_view_text(root=None):
    """chat_view.py (page builder + translations) followed by the chat scripts it loads, in load order.

    The chat behaviour moved from one inline <script> into static/js/chat/*.js; tests that pin chat behaviour read this."""
    base = Path(root) if root else ROOT
    parts = [(base / "chat_view.py").read_text(encoding="utf-8")]
    for name in CHAT_JS_ORDER:
        parts.append((base / "static" / "js" / "chat" / (name + ".js")).read_text(encoding="utf-8"))
    return "\n".join(parts)
