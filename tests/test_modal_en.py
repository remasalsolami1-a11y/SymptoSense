import re, webapp
def test_en_pages_have_no_arabic_in_modal():
    c = webapp.app.test_client()
    for path in ("/en/", "/en/about", "/en/sources"):
        h = c.get(path).get_data(as_text=True)
        m = re.search(r'id="smartCtxModal".*?</div>\s*</div>\s*</div>', h, re.S)
        assert m, path
        assert not re.search(r'[؀-ۿ]', re.sub(r'<[^>]+>', '', m.group(0))), path
def test_ar_modal_keeps_arabic():
    h = webapp.app.test_client().get("/ar/").get_data(as_text=True)
    assert "إدخال المعلومات يدويًا" in h and "تخطي" in h
