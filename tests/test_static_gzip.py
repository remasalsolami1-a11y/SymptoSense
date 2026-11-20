"""Static text assets are gzipped (once, cached) without breaking immutable caching or conditional requests."""
import gzip
import os
import tempfile

os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "g.db"))
import webapp  # noqa: E402


def _client():
    return webapp.app.test_client()


def test_big_static_css_and_js_are_gzipped_and_roundtrip():
    c = _client()
    for url in ("/static/css/app-shell-v111.css", "/static/js/chat/chat-core.js"):
        raw = c.get(url).data
        r = c.get(url, headers={"Accept-Encoding": "gzip"})
        assert r.headers.get("Content-Encoding") == "gzip" and "Accept-Encoding" in r.headers.get("Vary", "")
        assert gzip.decompress(r.data) == raw and len(r.data) < len(raw) * 0.6
        assert r.headers["ETag"].startswith("W/")


def test_no_gzip_without_accept_encoding_and_conditional_still_304():
    c = _client()
    url = "/static/js/chat/chat-core.js"
    r = c.get(url)
    assert r.headers.get("Content-Encoding") is None
    assert c.get(url, headers={"If-None-Match": r.headers["ETag"]}).status_code == 304


def test_images_are_not_touched():
    c = _client()
    r = c.get("/static/images/", headers={"Accept-Encoding": "gzip"})
    assert r.headers.get("Content-Encoding") != "gzip" or r.mimetype.startswith("text/")


def test_http_error_pages_are_bilingual_and_api_gets_json():
    from werkzeug.exceptions import Forbidden, MethodNotAllowed, TooManyRequests

    with webapp.app.test_request_context("/somewhere", headers={"Cookie": "lang=en"}):
        r = webapp._http_error_page(Forbidden())
        assert r.status_code == 403 and b"Access denied" in r.data and b"<h1>" in r.data
    with webapp.app.test_request_context("/somewhere", headers={"Cookie": "lang=ar"}):
        r = webapp._http_error_page(MethodNotAllowed())
        assert r.status_code == 405 and "غير مدعومة".encode() in r.data
    with webapp.app.test_request_context("/api/x", headers={"Cookie": "lang=ar"}):
        r = webapp._http_error_page(TooManyRequests())
        assert r.status_code == 429 and r.get_json()["ok"] is False and r.headers["Retry-After"] == "60"
    assert {403, 405, 429} <= set(webapp.app.error_handler_spec[None])
