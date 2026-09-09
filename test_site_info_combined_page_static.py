from pathlib import Path

WEB = (Path(__file__).resolve().parents[1] / 'webapp.py').read_text(encoding='utf-8')


def test_site_info_is_in_footer_not_community_stats():
    assert 'class="home-community-stat home-community-info" href="/site-info"' not in WEB
    assert '<a href="/site-info">%s</a>' in WEB
    assert '("معلومات الموقع" if _lang() == "ar" else "Site information")' in WEB


def test_site_info_route_is_public_and_present():
    assert '@app.route("/site-info")' in WEB
    assert 'def site_info():' in WEB
    assert '"/methodology", "/site-info", "/community-dashboard"' in WEB


def test_site_info_combines_requested_information():
    for section in ('id="about"', 'id="method"', 'id="privacy"', 'id="terms"', 'id="sources"'):
        assert section in WEB
    assert 'AI + Data Science + Digital Health' in WEB
    assert 'Remas Hameed Alsolami — Data Science and Analytics student and creator of SymptoSense' in WEB
    assert 'Designed & Developed by' in WEB
    assert 'Remas Alsolami — Data Science Project' in WEB


def test_site_info_mobile_layout_is_responsive():
    assert '@media(max-width:520px)' in WEB
    assert '.si-flow,.si-terms{grid-template-columns:1fr}' in WEB
    assert '.si-list-grid,.si-sources{grid-template-columns:1fr}' in WEB


def test_footer_does_not_duplicate_about_link():
    footer = WEB[WEB.index('def _footer():'):WEB.index('def _page(', WEB.index('def _footer():'))]
    assert '<a href="/about-us">%s</a>' not in footer
    assert '<a href="/site-info">%s</a>' in footer
