"""V282 regression tests: public figures, terms, library page honesty and SEO."""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------- item 8: source count
def test_moh_937_source_is_registered_at_import_time_without_seeding():
    """A fresh process must see the 937 source before any database seeding.

    Previously it was appended inside _seed(), so a cold worker's bundled home
    statistics showed 29 sources while the database (and other pages) showed 30.
    """
    code = (
        "import sys; sys.path.insert(0, %r)\n"
        "import medical_knowledge as mk\n"
        "print(any(r[0] == 'saudi-moh-937' for r in mk.SOURCES))\n"
        "print(len({r[0] for r in mk.SOURCES}) == len(mk.SOURCES))\n" % str(ROOT)
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT, timeout=120)
    lines = [l for l in out.stdout.strip().splitlines() if l in ("True", "False")]
    assert lines == ["True", "True"], out.stdout + out.stderr


def test_bundled_home_fallback_matches_database_source_count():
    import kb_stats
    import webapp

    kb = kb_stats.get_kb_stats()
    assert kb["origin"] == "database"
    bundled = webapp._bundled_home_knowledge_snapshot()
    assert bundled["_origin"] == "bundled"
    assert bundled["verified_sources"] == kb["sources"]


# ---------------------------------------------------------------- item 10: duplicated hero copy
def test_home_hero_lead_rendered_once_and_title_words_separated():
    import webapp

    c = webapp.app.test_client()
    for path, lead_start, title in (
        ("/ar/", "مساعد صحي ذكي يساعدك على فهم أعراضك", "افهم أعراضك واعرف خطوتك التالية"),
        ("/en/", "A smart health assistant that helps you understand", "Understand your symptoms and know your next step"),
    ):
        html = c.get(path).get_data(as_text=True)
        assert html.count(lead_start) == 1, path
        assert "ss-hero-lead-mobile" not in html, path
        h1 = re.search(r'<h1 id="homeTitle">(.*?)</h1>', html, re.S).group(1)
        # Text extractors (search engines, screen readers) must not glue the two spans.
        assert re.sub(r"<[^>]+>", "", h1) == title, path


def test_home_css_has_no_orphan_mobile_lead_selector():
    css = (ROOT / "inline_assets" / "HOME_CSS.css").read_text(encoding="utf-8")
    assert ".ss-hero-lead-mobile" not in css


# ---------------------------------------------------------------- item 6: terms of use
def test_terms_page_has_full_sections_version_and_working_links():
    import webapp

    c = webapp.app.test_client()
    expected = {
        "ar": ("قبول الشروط", "الحساب ومسؤولية المستخدم", "الذكاء الاصطناعي", "الاستخدام المحظور",
               "الخدمات والروابط الخارجية", "حدود المسؤولية", "الملكية الفكرية", "إيقاف الحساب",
               "القانون الحاكم", "تعديل الشروط", "التواصل", "الحد الأدنى للعمر", "الإصدار 1.1"),
        "en": ("Accepting these terms", "Your account", "AI and automated content", "Prohibited use",
               "Third-party services", "Limitation of liability", "Intellectual property", "Suspension and termination",
               "Governing law", "Changes to these terms", "Contact", "Minimum age", "Version 1.1"),
    }
    for lang, words in expected.items():
        html = c.get("/%s/terms" % lang).get_data(as_text=True)
        main = html[html.index('<main class="v2-info-page"'):html.index("</main>")]
        for w in words:
            assert w in main, (lang, w)
        # every in-terms link is localised and resolves
        for href in re.findall(r'href="(/[^"#]*)"', main):
            assert href.startswith("/%s/" % lang), href
            r = c.get(href)
            # account pages (e.g. /manage) correctly send guests to sign in first
            assert r.status_code == 200 or (r.status_code == 302 and "/login" in r.headers["Location"]), href


# ---------------------------------------------------------------- item 5: library pages
def _jsonld(html):
    m = re.search(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S)
    return json.loads(m.group(1).replace("<\\/", "</"))


def test_condition_page_title_meta_and_absolute_schema_url():
    import webapp

    c = webapp.app.test_client()
    for lang, tail in (("ar", "الأعراض والأسباب ومتى تراجع الطبيب | SymptoSense"),
                       ("en", "symptoms, causes and when to see a doctor | SymptoSense")):
        html = c.get("/%s/health-library/disease/appendicitis" % lang).get_data(as_text=True)
        title = re.search(r"<title>(.*?)</title>", html, re.S).group(1)
        assert title.endswith(tail), title
        data = _jsonld(html)
        assert data["url"].startswith("http") and data["url"].endswith("/%s/health-library/disease/appendicitis" % lang)
        assert data["about"]["@type"] == "MedicalCondition"
    sym = c.get("/ar/health-library/symptom/headache").get_data(as_text=True)
    assert "الأسباب المحتملة ومتى تطلب الرعاية | SymptoSense" in re.search(r"<title>(.*?)</title>", sym, re.S).group(1)


def test_seed_date_is_not_presented_as_a_clinical_review():
    import webapp

    c = webapp.app.test_client()
    html = c.get("/ar/health-library/disease/appendicitis").get_data(as_text=True)
    assert "آخر تحديث للمحتوى:" in html and "آخر مراجعة:" not in html
    data = _jsonld(html)
    assert "lastReviewed" not in data and re.match(r"\d{4}-\d{2}-\d{2}$", data["dateModified"])
    # The 937 link is described as care navigation, not as evidence for the content.
    assert "مصادر سعودية وعالمية داعمة للمحتوى" not in html
    assert "مرجع سعودي رسمي (937) للاستشارة ومسار الرعاية" in html


def test_last_independent_approval_ignores_self_review_and_pending(tmp_path, monkeypatch):
    """SQL logic against an isolated SQLite file (no shared state with parallel tests)."""
    import clinical_review
    import db

    monkeypatch.setattr(db, "USE_POSTGRES", False)
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "reviews.db"))
    monkeypatch.setattr(clinical_review, "_READY", False)
    conn = db._conn()
    clinical_review._ensure(conn)
    rows = [  # (status, note, reviewed_at)
        ("approved", "ok [self-review]", "2026-11-09T10:00:00+00:00"),
        ("approved", "checked against NHS", "2026-11-05T10:00:00+00:00"),
        ("rejected", "wrong", "2026-11-10T10:00:00+00:00"),
    ]
    for status, note, at in rows:
        conn.cursor().execute(
            "INSERT INTO mk_clinical_reviews (entity_type, entity_id, name, payload, status, requested_by_id, "
            "requested_at, reviewer_id, reviewed_at, note, result_entity_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("disease", 7, "t", "{}", status, 1, at, 2, at, note, 7))
    conn.commit()
    conn.close()
    assert clinical_review.last_independent_approval("disease", 7) == "2026-11-05"
    assert clinical_review.last_independent_approval("disease", 8) is None
    assert clinical_review.last_independent_approval("bogus", 7) is None
    monkeypatch.setattr(clinical_review, "_READY", False)


def test_condition_page_shows_review_only_when_an_independent_approval_exists(monkeypatch):
    import clinical_review
    import webapp

    c = webapp.app.test_client()
    monkeypatch.setattr(clinical_review, "last_independent_approval", lambda kind, eid: "2026-11-05")
    html = c.get("/ar/health-library/disease/appendicitis").get_data(as_text=True)
    assert 'آخر مراجعة: <bdi dir="ltr">2026-11-05</bdi>' in html
    assert _jsonld(html)["lastReviewed"] == "2026-11-05"
    monkeypatch.setattr(clinical_review, "last_independent_approval", lambda kind, eid: None)
    html = c.get("/ar/health-library/disease/appendicitis").get_data(as_text=True)
    assert "آخر مراجعة:" not in html and "lastReviewed" not in _jsonld(html)


# ---------------------------------------------------------------- item 13: Saudi sources
def test_saudi_condition_references_are_https_allowlisted_and_wired():
    import urllib.parse

    import health_library
    import medical_knowledge as mk
    import saudi_sources

    diseases = {d["slug"]: d for d in mk.DISEASES}
    for slug, (title_ar, title_en, url) in saudi_sources.DISEASE_REFERENCES.items():
        p = urllib.parse.urlparse(url)
        assert p.scheme == "https" and p.netloc in saudi_sources.ALLOWED_HOSTS, url
        assert "default.aspx" not in url.lower() and not url.lower().endswith(".pdf"), url  # a page about the condition
        assert slug in diseases, slug
        assert any(r[0] == "saudi-moh" and r[3] == url for r in diseases[slug]["sources"]), slug
        # rendered on the public page, after the originally curated (primary) source
        item = health_library._entity_by_slug("disease", slug)
        urls = [s.get("reference_url") for s in item["sources"]]
        assert url in urls and urls.index(url) > 0, slug
    # attached to the existing MOH organisation: no new source rows
    assert {r[0] for r in mk.SOURCES} >= {"saudi-moh"}


# ---------------------------------------------------------------- V283
def test_home_demo_shows_match_levels_not_probabilities():
    import webapp

    c = webapp.app.test_client()
    for lang, words in (("ar", ("توافق أعلى", "توافق جزئي", "توافق محدود")), ("en", ("Stronger match", "Partial match", "Limited match"))):
        html = c.get("/%s/" % lang).get_data(as_text=True)
        demo = html[html.index('class="ss-hero-demo-card"'):html.index('class="ss-hero-demo-card note"')]
        assert not re.search(r"<small>\s*\d+\s*[%٪]", demo), lang
        for w in words:
            assert w in demo, (lang, w)
        widths = [int(w) for w in re.findall(r"width:(\d+)%", demo)]
        assert len(widths) == 3 and widths == sorted(widths, reverse=True) and sum(widths) != 100


def test_emergency_page_lists_mental_health_line_without_claiming_24_7():
    import webapp

    c = webapp.app.test_client()
    for lang, not_24 in (("ar", "لا يعمل على مدار الساعة"), ("en", "not open 24/7")):
        html = c.get("/%s/emergency" % lang).get_data(as_text=True)
        assert 'href="tel:920033360"' in html, lang
        assert not_24 in html, lang
        # the 24/7 and danger fallbacks stay reachable right next to it
        block = html[html.index('class="em-mental-crisis"'):html.index('class="em-mini"')]
        for tel in ("tel:997", "tel:937", "tel:920033360"):
            assert tel in block, (lang, tel)


def test_saudi_health_guides_render_indexed_sourced_and_safe():
    import urllib.parse

    import health_guides
    import seo_extras
    import webapp

    c = webapp.app.test_client()
    sitemap = c.get("/sitemap.xml").get_data(as_text=True)
    library = c.get("/ar/health-library").get_data(as_text=True)
    assert len(health_guides.GUIDES) == 3
    for slug, g in health_guides.GUIDES.items():
        assert seo_extras.indexable("/health-library/guide/" + slug)
        assert "/ar/health-library/guide/%s</loc>" % slug in sitemap
        assert 'href="/ar/health-library/guide/%s"' % slug in library
        for lang in ("ar", "en"):
            r = c.get("/%s/health-library/guide/%s" % (lang, slug))
            html = r.get_data(as_text=True)
            assert r.status_code == 200, (lang, slug)
            assert '<meta name="robots" content="index, follow">' in html
            assert re.search(r"<title>[^<]+\| SymptoSense</title>", html)
            assert 'href="tel:997"' in html and "997" in g["emergency"][0 if lang == "ar" else 1]
            data = _jsonld(html)
            assert data["url"].startswith("http") and data["citation"] and "lastReviewed" not in data
            for _a, _e, url in g["sources"]:
                assert urllib.parse.urlparse(url).scheme == "https" and url in data["citation"]
        # no medicine doses in a public guide
        text = json.dumps(g, ensure_ascii=False)
        assert not re.search(r"\d+\s*(?:mg|ملغ|units?|وحدات|وحدة|ml|مل)\b(?!/)", text)
    assert c.get("/ar/health-library/guide/not-a-guide").status_code == 404
    assert not seo_extras.indexable("/health-library/guide/not-a-guide")


def test_diabetes_fasting_thresholds_match_the_cited_source():
    import health_guides

    g = health_guides.GUIDES["diabetes-and-ramadan-fasting"]
    warn = " ".join(x[0] + " " + x[1] for x in g["warning"][1])
    for figure in ("70 ملغ/دل", "3.9", "300 ملغ/دل", "16.7", "70 mg/dL", "300 mg/dL"):
        assert figure in warn
    assert any("jhah.com" in u for _a, _e, u in g["sources"])  # source of the thresholds


def test_visual_regression_compare_flags_only_real_changes(tmp_path):
    from PIL import Image

    sys.path.insert(0, str(ROOT / "tools"))
    import visual_regression as vr

    before, after, report = tmp_path / "b", tmp_path / "a", tmp_path / "r"
    before.mkdir(), after.mkdir()
    Image.new("RGB", (40, 40), "white").save(before / "same.png")
    Image.new("RGB", (40, 40), "white").save(after / "same.png")
    Image.new("RGB", (40, 40), "white").save(before / "moved.png")
    img = Image.new("RGB", (40, 40), "white")
    img.paste((0, 0, 0), (10, 10, 20, 20))
    img.save(after / "moved.png")
    assert vr.compare(before, after, report, threshold=0) == 1
    assert (report / "moved.png").exists() and not (report / "same.png").exists()
    assert vr.compare(before, after, None, threshold=100) == 0  # 100 changed pixels tolerated
