#!/usr/bin/env python3
"""Move route functions out of webapp.py into routes/<group>.py without changing behaviour.

    python tools/extract_routes.py GROUP name1 name2 ...      # explicit function names
    python tools/extract_routes.py GROUP --prefix /api/meds   # every route whose first rule starts with a prefix

What it does (all checked, nothing guessed):
  * function source is copied line-for-line (HTML/CSS strings are never re-indented);
  * ``@app.route(...)`` becomes ``@route(...)``; the other decorators (login_required, ...) are recorded and applied at
    registration time, in the original order, so protection is unchanged;
  * every free name is classified: builtin / imported (import copied) / defined in webapp (listed in DEPS and injected by
    ``register``) / moved with the group.  Unknown names, ``global`` statements and anything else unsafe abort the move
    for that function (it stays in webapp.py);
  * names still used by webapp.py or by the tests (``webapp.<name>``) are re-exported with ``from routes.X import name``.
"""
from __future__ import annotations

import ast
import builtins
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "webapp.py"
BUILTINS = set(dir(builtins)) | {"__file__", "__name__", "__doc__"}

HELPER_FOOTER = '''def bind(namespace):
    """Inject the webapp helpers this module needs (proxies, resolved lazily on every call)."""
    missing = [n for n in DEPS if n not in namespace]
    if missing:
        raise RuntimeError("%s.%s: missing dependencies %%s" %% missing)
    g = globals()
    for n in DEPS:
        g[n] = _inject.dependency(namespace, n)
'''

ROUTE_HEADER = '''def route(rule, **opts):
    def deco(fn):
        _SPECS.setdefault(fn.__name__, {"fn": fn, "rules": []})["rules"].append((rule, opts))
        return fn
    return deco


'''

ROUTE_FOOTER = '''def register_routes(app, namespace):
    """Inject webapp dependencies, apply the original decorators, and add the URL rules (same endpoint names)."""
    missing = [n for n in DEPS if n not in namespace]
    if missing:
        raise RuntimeError("routes.%s: missing dependencies %%s" %% missing)
    g = globals()
    for n in DEPS:
        g[n] = _inject.dependency(namespace, n)
    g["app"] = app
    for name, spec in _SPECS.items():
        view = spec["fn"]
        for w in reversed(_WRAPPERS.get(name, ())):
            view = _inject.resolve_wrapper(w, g)(view)
        for rule, opts in spec["rules"]:
            kw = dict(opts)
            endpoint = kw.pop("endpoint", name)
            app.add_url_rule(rule, endpoint=endpoint, view_func=view, **kw)
'''


def bound_names(fn):
    names = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.arg):
            names.add(n.arg)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            names.add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n is not fn:
            names.add(n.name)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            names.add(n.name)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                names.add((a.asname or a.name).split(".")[0])
    return names


def loads(fn):
    return {n.id for n in ast.walk(fn) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}


def main(argv):
    group = argv[0]
    prefixes = []
    explicit = []
    package = "routes"
    helpers = False
    it = iter(argv[1:])
    for a in it:
        if a == "--prefix":
            prefixes.append(next(it))
        elif a == "--package":
            package = next(it)
        elif a == "--helpers":
            helpers = True            # plain (non-route) functions, e.g. page builders
        else:
            explicit.append(a)
    src = WEB.read_text(encoding="utf-8")
    lines = src.splitlines(keepends=True)
    tree = ast.parse(src)

    top_defs, imports = set(), {}
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            top_defs.add(n.name)
        elif isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            for t in ast.walk(n):
                if isinstance(t, ast.Name) and isinstance(t.ctx, ast.Store):
                    top_defs.add(t.id)
        elif isinstance(n, ast.Import):
            for a in n.names:
                imports[(a.asname or a.name).split(".")[0]] = "import " + a.name + (" as " + a.asname if a.asname else "")
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                imports[a.asname or a.name] = "from %s%s import %s" % ("." * n.level, n.module or "", a.name + (" as " + a.asname if a.asname else ""))
    global_decl = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Global):
            global_decl.update(n.names)

    cand = []
    if helpers:
        for n in tree.body:
            if isinstance(n, ast.FunctionDef) and n.name in explicit and not n.decorator_list:
                cand.append(n)
    for n in ([] if helpers else tree.body):
        if not isinstance(n, ast.FunctionDef) or not n.decorator_list:
            continue
        d0 = n.decorator_list[0]
        if not (isinstance(d0, ast.Call) and isinstance(d0.func, ast.Attribute) and d0.func.attr == "route" and ast.unparse(d0.func.value) == "app"):
            continue
        rule = ast.literal_eval(d0.args[0]) if d0.args and isinstance(d0.args[0], ast.Constant) else ""
        if n.name in explicit or any(rule.startswith(p) for p in prefixes):
            cand.append(n)

    moved, skipped = [], []
    toplevel_used = set()
    for st in tree.body:
        if isinstance(st, (ast.FunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)):
            continue
        toplevel_used |= {x.id for x in ast.walk(st) if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load)}
    for n in list(cand):
        if helpers and n.name in toplevel_used:
            skipped.append((n.name, "used at import time by top-level code"))
            cand.remove(n)
    moved_names = {n.name for n in cand}
    plans = {}
    for n in cand:
        why = None
        for d in n.decorator_list:
            if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and ast.unparse(d.func.value) == "app" and d.func.attr == "route":
                continue
            if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and ast.unparse(d.func.value) == "app":
                why = "decorator app.%s" % d.func.attr
        gl = {x for g in ast.walk(n) if isinstance(g, ast.Global) for x in g.names}
        if gl:
            why = "uses global %s" % sorted(gl)
        free = (loads(n) - bound_names(n)) - BUILTINS
        for d in n.decorator_list:
            free |= loads(d) if not (isinstance(d, ast.Call) and ast.unparse(d.func) == "app.route") else loads(ast.Module(body=[ast.Expr(a) for a in d.args] + [ast.Expr(k.value) for k in d.keywords], type_ignores=[]))
        unknown = {f for f in free if f not in imports and f not in top_defs and f not in moved_names}
        if unknown:
            why = "unknown names %s" % sorted(unknown)
        if why:
            skipped.append((n.name, why))
        else:
            plans[n.name] = (n, free)
    # helper functions that were only free names of other moved functions stay in webapp (they are deps)
    moved = [plans[n.name][0] for n in cand if n.name in plans]
    names = {n.name for n in moved}
    deps, need_imports = set(), set()
    for n, free in plans.values():
        for f in free:
            if f in names:
                continue
            if f in imports and (imports[f].startswith("from routes.") or imports[f].startswith("from pagelib.")):
                deps.add(f)          # a name exported by another routes module: inject, never import (avoids cycles)
            elif f in imports and f not in top_defs:
                need_imports.add(f)
            elif f in top_defs:
                if f in global_decl:
                    skipped.append((n.name, "depends on rebound global %s" % f))
                deps.add(f)
            elif f in imports:
                need_imports.add(f)
    deps.discard("app")
    # exports: names used by remaining webapp code or by tests
    remaining_src = src
    for n in moved:
        remaining_src = remaining_src.replace("".join(lines[(n.decorator_list[0].lineno if n.decorator_list else n.lineno) - 1:n.end_lineno]), "")
    rem_tree = ast.parse(remaining_src)
    used_rem = {x.id for x in ast.walk(rem_tree) if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load)}
    test_text = "\n".join(p.read_text(encoding="utf-8") for p in ROOT.glob("test_*.py"))
    other_deps = set()
    for pkg in ("routes", "pagelib", "services"):
        for mp in (ROOT / pkg).glob("*.py") if (ROOT / pkg).is_dir() else []:
            m = re.search(r"^DEPS = \((.*?)\)\s*$", mp.read_text(encoding="utf-8"), re.S | re.M)
            if m:
                other_deps |= set(re.findall(r'"([^"]+)"', m.group(1)))
    exports = sorted(nm for nm in names if nm in used_rem or nm in other_deps or re.search(r"\bwebapp\.%s\b" % nm, test_text))

    if not moved:
        print("nothing to move for group %s" % group)
        for nm, why in skipped:
            print("  stays in webapp:", nm, "-", why)
        return
    kind = "Page builders" if helpers else "Routes"
    out = ['"""%s for group "%s", moved out of webapp.py (behaviour unchanged).\n\n'
           'Dependencies from webapp.py are injected at start-up; decorators like login_required are applied there in the\n'
           'original order. Generated by tools/extract_routes.py.\n"""\n' % (kind, group)]
    imp_lines = sorted({imports[i] for i in need_imports})
    out.append("from routes import _inject\n")
    out += [l + "\n" for l in imp_lines] + ["\n"]
    wrappers = {}
    body = []
    for n in moved:
        ws = []
        parts = []
        for d in n.decorator_list:
            seg = ast.get_source_segment(src, d)
            if isinstance(d, ast.Call) and ast.unparse(d.func) == "app.route":
                parts.append("@route" + seg[len("app.route"):] if seg.startswith("app.route") else "@route(" + seg.split("(", 1)[1])
            else:
                ws.append(seg)
        wrappers[n.name] = ws
        # source text from first decorator to end, dropping original decorator lines; re-add rewritten route decorators
        body_start = n.lineno - 1 if not n.decorator_list else max(d.end_lineno for d in n.decorator_list)
        fn_text = "".join(lines[body_start:n.end_lineno])
        # def line may share position with decorator end; n.lineno is the def line
        fn_text = "".join(lines[n.lineno - 1:n.end_lineno])
        body.append("\n".join(parts) + "\n" + fn_text.rstrip("\n") + "\n")
    out.append("DEPS = (%s)\n\n" % "".join('"%s", ' % d for d in sorted(deps)))
    if helpers:
        out.append("\n\n".join(body) + "\n\n")
        out.append(HELPER_FOOTER % (package, group))
    else:
        out.append("_SPECS = {}\n_WRAPPERS = {\n" + "".join('    "%s": (%s),\n' % (k, "".join(repr(w) + ", " for w in v)) for k, v in wrappers.items()) + "}\n\n\n")
        out.append(ROUTE_HEADER)
        out.append("\n\n".join(body) + "\n\n")
        out.append(ROUTE_FOOTER % group)
    (ROOT / package).mkdir(exist_ok=True)
    mod_path = ROOT / package / (group + ".py")
    mod_path.write_text("".join(out), encoding="utf-8")
    (ROOT / package / "__init__.py").touch()

    # rewrite webapp.py: remove moved nodes (bottom-up), leave a marker + exports
    for n in sorted(moved, key=lambda x: -x.lineno):
        s = (n.decorator_list[0].lineno if n.decorator_list else n.lineno) - 1
        e = n.end_lineno
        # swallow one trailing blank line
        while e < len(lines) and lines[e].strip() == "" and e - n.end_lineno < 2:
            e += 1
        lines[s:e] = []
    text = "".join(lines)
    alias = "%s_%s" % (package, group)
    reg = "import %s.%s as %s\n" % (package, group, alias)
    exp = ("from %s.%s import %s\n" % (package, group, ", ".join(exports))) if exports else ""
    call = "%s.%s(app, globals())\n" % (alias, "bind" if helpers else "register_routes")
    call = call.replace("(app, globals())", "(globals())") if helpers else call
    if '\nif __name__ == "__main__":' in text:
        i = text.rindex('\nif __name__ == "__main__":')
        text = text[:i] + "\n" + call + text[i:]
    else:
        text += "\n" + call
    # imports + exports go near the top-level imports end (after inline_assets import) to keep them above first use
    text = text.replace("import inline_assets\n", "import inline_assets\n" + reg + exp, 1)
    WEB.write_text(text, encoding="utf-8")
    print("moved %d functions to %s/%s.py; deps=%d exports=%s" % (len(moved), package, group, len(deps), exports))
    for nm, why in skipped:
        print("  stays in webapp:", nm, "-", why)


if __name__ == "__main__":
    main(sys.argv[1:])
