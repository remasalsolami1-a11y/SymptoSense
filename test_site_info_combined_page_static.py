import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()
SITE = (ROOT / 'site_info_view.py').read_text(encoding='utf-8')
COMBINED = WEB + '\n' + SITE


def test_site_info_is_in_footer_not_community_stats():
    assert 'class="home-community-stat home-community-info" href="/site-info"' not in WEB
    assert '<a href="/about" class="f-owner">%s<br>%s</a>' in WEB
    assert '_PUBLIC_CANONICAL_MAP' in WEB and '"/site-info": "/about"' in WEB


def test_site_info_route_is_public_and_present():
    assert '@app.route("/site-info")' in WEB
    assert 'def site_info():' in WEB
    assert 'return redirect(_localized_url("/about"), code=301)' in WEB


def test_site_info_combines_requested_information():
    for section in ('id="about"', 'id="method"', 'id="privacy"', 'id="terms"', 'id="sources"'):
        assert section in COMBINED
    assert 'AI + Data Science + Digital Health' in COMBINED
    assert 'Remas Hameed Alsolami — Data Science and Analytics student and creator of SymptoSense' in COMBINED
    assert 'Designed & Developed by' in WEB
    assert 'Remas Alsolami — Data Science Project' in WEB


def test_site_info_mobile_layout_is_responsive():
    assert '@media(max-width:520px)' in COMBINED
    assert '.si-flow,.si-terms{grid-template-columns:1fr}' in COMBINED
    assert '.si-list-grid,.si-sources{grid-template-columns:1fr}' in COMBINED


def test_footer_does_not_duplicate_about_link():
    footer = WEB[WEB.index('def _footer():'):WEB.index('def _page(', WEB.index('def _footer():'))]
    assert 'href="/about-us"' not in footer
    assert '<a href="/about" class="f-owner">%s<br>%s</a>' in footer
