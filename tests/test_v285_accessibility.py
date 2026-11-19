"""V285: measured accessibility results are clean and the fixes stay in place."""
import json
import re
from pathlib import Path

import webapp

ROOT = Path(__file__).resolve().parents[1]


def test_recorded_audit_covers_every_public_page_with_no_serious_violation():
    rep = json.loads((ROOT / "evaluation" / "results" / "accessibility.json").read_text(encoding="utf-8"))
    s = rep["summary"]
    assert s["pages"] >= 21 and s["page_checks"] == s["pages"] * 4  # 2 languages x 2 viewports
    assert s["checks_without_serious_or_critical"] == s["page_checks"]
    assert s["contrast_violation_nodes"] == 0 and s["touch_targets_below_24px"] == 0
    assert not s["pages_with_horizontal_overflow"] and not s["pages_missing_lang_or_dir"]
    assert "wcag22aa" in rep["axe_tags"]


def test_audit_page_list_matches_the_playwright_spec():
    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    import accessibility_audit
    spec = (ROOT / "accessibility.spec.js").read_text(encoding="utf-8")
    listed = re.search(r"const pages = \[(.*?)\];", spec, re.S).group(1)
    assert set(re.findall(r"'([^']*)'", listed)) == set(accessibility_audit.PAGES)


def test_every_auth_label_is_tied_to_its_input():
    c = webapp.app.test_client()
    for path in ("/ar/register", "/en/register", "/ar/login", "/en/login"):
        html = c.get(path).get_data(as_text=True)
        fors = re.findall(r'<label for="(auth-[a-z_]+)">', html)
        assert fors, path
        for f in fors:
            assert f'id="{f}"' in html, (path, f)
        assert '<label>__' not in html


def test_low_contrast_greys_are_gone():
    for p in ("routes/pages.py", "site_info_view.py", "webapp.py", "static/css/app-shell-v111.css", "inline_assets/PREMIUM_POLISH_CSS.css"):
        assert "60788b" not in (ROOT / p).read_text(encoding="utf-8").lower(), p
    assert "#657c8b" not in (ROOT / "health_library.py").read_text(encoding="utf-8")
