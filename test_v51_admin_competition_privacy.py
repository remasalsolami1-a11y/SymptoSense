import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_competition_tools_are_admin_only_and_not_public_navigation():
    web = source_bundle.webapp_text()
    dash = (ROOT / "dashboard.py").read_text(encoding="utf-8")
    assert '@app.route("/admin/competition-dashboard")' in web
    assert '@app.route("/admin/innovation-lab")' in web
    assert '_admin_page_gate("/admin/competition-dashboard")' in web
    assert '_admin_page_gate("/admin/innovation-lab")' in web
    assert 'href="/admin/competition-dashboard"' in dash
    # Innovation Lab remains admin-only but is intentionally omitted from the compact primary nav.
    assert '/admin/innovation-lab' in web
    assert 'href="/competition-dashboard">__COMP_LINK__' not in web


def test_innovation_apis_use_admin_rbac_csrf_and_private_cache():
    web = source_bundle.webapp_text()
    lab = (ROOT / "v51_innovation.py").read_text(encoding="utf-8")
    assert '@app.route("/api/admin/innovation-lab/probe", methods=["POST"])' in web
    assert '@app.route("/api/admin/innovation-lab/evidence", methods=["GET"])' in web
    assert web.count('@admin_api_required("analytics")') >= 2
    assert 'private, no-store' in web
    assert "'X-CSRF-Token'" in lab


def test_competition_tools_are_excluded_from_public_sitemap():
    web = source_bundle.webapp_text()
    sitemap_block = web.split('def sitemap_xml():', 1)[1].split('@app.route("/api/stats")', 1)[0]
    assert '"/competition-dashboard"' not in sitemap_block
    assert '"/innovation-lab"' not in sitemap_block
