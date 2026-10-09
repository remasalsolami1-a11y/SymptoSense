"""V260: webapp.py was split into routes/*.py - the public surface must be exactly what it was, and protection kept."""
import ast
import json
from pathlib import Path

import pytest

import webapp

ROOT = Path(__file__).resolve().parent


def _rules():
    return sorted([r.rule, sorted(r.methods - {"HEAD", "OPTIONS"}), r.endpoint] for r in webapp.app.url_map.iter_rules())


def test_url_map_is_identical_to_the_pre_split_baseline():
    base = json.loads((ROOT / "route_map_baseline.json").read_text(encoding="utf-8"))
    now = _rules()
    new = [r for r in now if r not in base]
    gone = [r for r in base if r not in now]
    assert not gone, "routes disappeared: %s" % gone[:5]
    assert not new, "routes added - update route_map_baseline.json on purpose: %s" % new[:5]


def test_every_routes_module_registered_its_views():
    mods = [p.stem for p in (ROOT / "routes").glob("*.py") if p.stem not in ("__init__", "_inject")]
    assert len(mods) >= 7
    endpoints = set(webapp.app.view_functions)
    for m in mods:
        mod = __import__("routes." + m, fromlist=["_SPECS"])
        assert mod._SPECS, m
        for name, spec in mod._SPECS.items():
            for _rule, opts in spec["rules"]:
                ep = opts.get("endpoint", name)
                assert ep in endpoints, "%s.%s (endpoint %s) not registered" % (m, name, ep)


def test_declared_deps_exist_in_webapp():
    for pkg in ("routes", "pagelib", "services"):
        for p in (ROOT / pkg).glob("*.py"):
            if p.stem in ("__init__", "_inject"):
                continue
            mod = __import__(pkg + "." + p.stem, fromlist=["DEPS"])
            missing = [d for d in getattr(mod, "DEPS", ()) if not hasattr(webapp, d)]
            assert not missing, (pkg, p.name, missing)


def test_moved_modules_have_no_undefined_names():
    import subprocess
    import sys
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "check_routes_modules.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_protection_decorators_survived_the_move():
    anon = webapp.app.test_client()
    # api_login_required -> 401 JSON, login_required -> redirect, admin_api_required -> 401/403
    assert anon.get("/api/meds/plan").status_code in (401, 403)
    assert anon.get("/api/vitals").status_code == 401
    assert anon.get("/api/admin/analysis-results").status_code in (401, 403)
    r = anon.get("/admin/lab-trials", follow_redirects=False)
    assert r.status_code in (301, 302, 303, 401, 403)
    # and every wrapper recorded for the moved views is still applied: spot-check by name
    import routes.admin as ra
    assert any("admin_api_required" in w for ws in ra._WRAPPERS.values() for w in ws)


def test_webapp_stays_small_and_does_not_regrow():
    web = ROOT / "webapp.py"
    assert len(web.read_text(encoding="utf-8").splitlines()) < 6500
    assert web.stat().st_size < 400_000
    routes_left = sum(1 for n in ast.parse(web.read_text(encoding="utf-8")).body
                      if isinstance(n, ast.FunctionDef) and any(isinstance(d, ast.Call) and ast.unparse(d.func) == "app.route" for d in n.decorator_list))
    assert routes_left <= 70, "new routes belong in routes/<group>.py (tools/extract_routes.py shows how)"


def test_monkeypatching_webapp_helpers_still_reaches_moved_routes(monkeypatch):
    monkeypatch.setattr(webapp, "_ss_user_id", lambda: None)
    c = webapp.app.test_client()
    assert c.get("/api/meds/plan").status_code in (401, 403)


def test_no_injected_dependency_is_rebound_at_runtime():
    """Plain values are injected once at registration. A name that webapp.py rebinds later (``global X``) would freeze at
    its start-up value inside the moved code (this hid ``_MED_REMINDER_WORKER_STARTED`` as always-False). Those names must
    be reached through a function instead."""
    import ast
    rebound = {n for node in ast.walk(ast.parse((ROOT / "webapp.py").read_text(encoding="utf-8"))) if isinstance(node, ast.Global) for n in node.names}
    offenders = []
    for pkg in ("routes", "pagelib", "services"):
        for p in (ROOT / pkg).glob("*.py"):
            if p.stem in ("__init__", "_inject"):
                continue
            mod = __import__(pkg + "." + p.stem, fromlist=["DEPS"])
            offenders += [(p.name, d) for d in getattr(mod, "DEPS", ()) if d in rebound and not callable(getattr(webapp, d, None))]
    assert not offenders, offenders
