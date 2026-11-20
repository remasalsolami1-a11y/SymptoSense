import re, webapp
def test_coverage_card_is_count_not_percent():
    c = webapp.app.test_client()
    for path, word in (("/ar/", "وليس دقة طبية"), ("/en/", "not medical accuracy")):
        h = c.get(path).get_data(as_text=True)
        m = re.search(r'<section class="ss-strength.*?</section>', h, re.S)
        assert m and word in m.group(0), path
        assert "%" not in re.sub(r"<[^>]+>", "", m.group(0)), path

def test_english_home_sections_ltr_rule_present():
    import polish_css_v249
    assert 'html[dir="ltr"] body.ss-home-page :is(.ss-strength' in polish_css_v249.CSS
