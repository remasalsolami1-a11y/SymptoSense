#!/usr/bin/env python3
"""Make sure every name listed in a moved module's DEPS exists in webapp.py (defined there or re-exported)."""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
web = (ROOT / "webapp.py").read_text(encoding="utf-8")
tree = ast.parse(web)
have = set()
for n in tree.body:
    if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
        have.add(n.name)
    elif isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
        have |= {x.id for x in ast.walk(n) if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store)}
    elif isinstance(n, (ast.Import, ast.ImportFrom)):
        have |= {(a.asname or a.name).split(".")[0] for a in n.names}
defs = {}
for pkg in ("routes", "pagelib", "services"):
    for mp in sorted((ROOT / pkg).glob("*.py")):
        if mp.name.startswith("_"):
            continue
        t = ast.parse(mp.read_text(encoding="utf-8"))
        for n in t.body:
            if isinstance(n, ast.FunctionDef):
                defs.setdefault(n.name, "%s.%s" % (pkg, mp.stem))
add = {}
problems = []
for pkg in ("routes", "pagelib", "services"):
    for mp in sorted((ROOT / pkg).glob("*.py")):
        if mp.name.startswith("_"):
            continue
        m = re.search(r"^DEPS = \((.*?)\)\s*$", mp.read_text(encoding="utf-8"), re.S | re.M)
        for d in re.findall(r'"([^"]+)"', m.group(1)) if m else []:
            if d not in have:
                if d in defs:
                    add.setdefault(defs[d], set()).add(d)
                else:
                    problems.append((mp.name, d))
if add and "--apply" in sys.argv:
    lines = "".join("from %s import %s\n" % (mod, ", ".join(sorted(names))) for mod, names in sorted(add.items()))
    web = web.replace("import inline_assets\n", "import inline_assets\n" + lines, 1)
    (ROOT / "webapp.py").write_text(web, encoding="utf-8")
print("exports to add:", {k: sorted(v) for k, v in add.items()})
print("unresolved:", problems)
sys.exit(1 if problems or (add and "--apply" not in sys.argv) else 0)
