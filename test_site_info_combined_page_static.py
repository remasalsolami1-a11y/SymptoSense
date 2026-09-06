from pathlib import Path

WEB = (Path(__file__).resolve().parents[1] / 'webapp.py').read_text(encoding='utf-8')


def test_home_uses_single_site_info_card_not_under_links():
    assert 'class="home-community-stat home-community-info" href="/site-info"' in WEB
    assert 'class="home-community-links"' not in WEB
    assert '"__INFO_LABEL__": bi("معلومات الموقع", "Site information")' in WEB


def test_site_info_route_is_public_and_present():
    assert '@app.route("/site-info")' in WEB
    assert 'def site_info():' in WEB
    assert '"/methodology", "/site-info", "/community-dashboard"' in WEB


def test_site_info_combines_requested_information():
    for section in ('id="about"', 'id="method"', 'id="privacy"', 'id="terms"', 'id="sources"'):
        assert section in WEB
    assert 'AI + Data Science + Digital Health' in WEB
    assert 'Designed &amp; Developed by Remas Alsolami — Data Science Project' in WEB


def test_site_info_mobile_layout_is_responsive():
    assert '@media(max-width:520px)' in WEB
    assert '.si-flow,.si-terms{grid-template-columns:1fr}' in WEB
    assert '.si-list-grid,.si-sources{grid-template-columns:1fr}' in WEB
