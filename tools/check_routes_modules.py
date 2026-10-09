#!/usr/bin/env python3
"""Static check for routes/*.py: no undefined names except the declared DEPS (+ app). Exit 1 on problems."""
import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
bad = 0
for p in sorted(list((ROOT / "routes").glob("*.py")) + list((ROOT / "pagelib").glob("*.py")) + list((ROOT / "services").glob("*.py"))):
    if p.name == "__init__.py":
        continue
    tree = ast.parse(p.read_text(encoding="utf-8"))
    deps = set()
    for n in tree.body:
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "DEPS" for t in n.targets):
            deps = set(ast.literal_eval(n.value))
    out = subprocess.run([sys.executable, "-m", "pyflakes", str(p)], capture_output=True, text=True).stdout
    for line in out.splitlines():
        m = re.search(r"undefined name '([^']+)'", line)
        if m and (m.group(1) in deps or m.group(1) == "app"):
            continue
        if "undefined name" not in line:
            continue
        if "undefined name" in line:
            print(line)
            bad += 1
sys.exit(1 if bad else 0)
