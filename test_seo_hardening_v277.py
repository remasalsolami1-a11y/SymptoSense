import json, re
import webapp

BASE = "https://symptosensehealth.com"


def _get(path):
    c = webapp.app.test_client()
    return c.get(path, base_url=BASE)


def test_sitemap_lists_only_urls_that_return_200_without_a_session():
    xml = _get("/sitemap.xml").get_data(as_text=True)
    locs = re.findall(r"<loc>(.*?)</loc>", xml)
    assert locs and not any(l.endswith(("/chat", "/blood")) for l in locs)
    c = webapp.app.test_client()
    for loc in locs:
        r = c.get(loc.replace(BASE, ""), base_url=BASE)
        assert r.status_code == 200, (loc, r.status_code)


def test_sitemap_xdefault_points_to_matching_arabic_page_and_has_no_changefreq():
    xml = _get("/sitemap.xml").get_data(as_text=True)
    assert "changefreq" not in xml
    m = re.search(r"<loc>%s/ar/about</loc>(.*?)</url>" % re.escape(BASE), xml, re.S)
    assert m and 'hreflang="x-default" href="%s/ar/about"' % BASE in m.group(1)
    home = re.search(r"<loc>%s/ar/</loc>(.*?)</url>" % re.escape(BASE), xml, re.S)
    assert home and 'hreflang="x-default" href="%s/"' % BASE in home.group(1)


def test_page_level_xdefault_matches_sitemap_for_inner_pages():
    h = _get("/en/about").get_data(as_text=True)
    assert 'hreflang="x-default" href="%s/ar/about"' % BASE in h


def test_jsonld_only_on_home_pages_and_is_valid_minimal_json():
    for lang in ("ar", "en"):
        h = _get("/%s/" % lang).get_data(as_text=True)
        blocks = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', h, re.S)
        assert len(blocks) == 1
        data = json.loads(blocks[0])
        types = {n["@type"] for n in data["@graph"]}
        assert types == {"Organization", "WebSite"}
        assert "aggregateRating" not in blocks[0] and "FAQPage" not in blocks[0]
    assert "application/ld+json" not in _get("/ar/about").get_data(as_text=True)


def test_about_title_contains_platform_name():
    assert "SymptoSense" in re.search(r"<title>(.*?)</title>", _get("/ar/about").get_data(as_text=True)).group(1)
    assert "SymptoSense" in re.search(r"<title>(.*?)</title>", _get("/en/about").get_data(as_text=True)).group(1)


def test_hidden_banner_and_modal_are_hidden_from_assistive_tech_until_shown():
    h = _get("/ar/about").get_data(as_text=True)
    assert 'id="ssOfflineBanner" role="status" aria-live="polite" hidden' in h
    assert re.search(r'id="smartCtxModal"[^>]*aria-hidden="true"', h)
    assert "setAttribute('aria-hidden','false')" in h


def test_login_and_register_descriptions_differ():
    c = webapp.app.test_client()
    d = [re.search(r'<meta name="description" content="([^"]*)"', c.get(p, base_url=BASE).get_data(as_text=True)).group(1) for p in ("/ar/login", "/ar/register")]
    assert d[0] != d[1]
