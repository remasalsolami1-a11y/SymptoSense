"""Real-browser checks of the family delete / archive screens (static/js/family-ops.js, family-delete.js, family-archive.js).

The real scripts run in Chromium; only the server answers are scripted, so every outcome (success, already gone,
refused, server error, dropped connection, slow reply) is exercised deterministically.
Skipped only when Playwright/Chromium cannot start (set CHROMIUM_PATH to a Chromium binary to run it).
"""
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
playwright = pytest.importorskip("playwright.sync_api")
ORIGIN = "http://ss.test"


def _chromium_ok():
    try:
        with playwright.sync_playwright() as p:
            p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None).close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _chromium_ok(), reason="Chromium not available (set CHROMIUM_PATH)")

DELETE_PAGE = ('<!doctype html><html lang="ar"><head><meta charset="utf-8"><meta name="symptosense-csrf" content="tok123"></head>'
               '<body><div id="famDelete" data-mid="7"></div><script src="/static/js/family-ops.js"></script>'
               '<script src="/static/js/family-delete.js"></script></body></html>')
ARCHIVE_PAGE = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="symptosense-csrf" content="tok123"></head>'
                '<body><div id="famArchive"></div><script src="/static/js/family-ops.js"></script>'
                '<script src="/static/js/family-archive.js"></script></body></html>')


class Site:
    """Scripted server: `answers[(METHOD, path)]` is a list consumed one per request (last one repeats): int status, 'abort', or ('slow', status)."""
    def __init__(self, page, html):
        self.page, self.html, self.calls, self.answers = page, html, [], {}
        self.archived = [{"id": 5, "name": "Sara", "records": 2, "blood_tests": 1, "vitals": 0}]
        page.route("**/*", self.handle)

    def handle(self, route):
        req = route.request
        path = req.url.replace(ORIGIN, "")
        if path.startswith("/static/js/"):
            return route.fulfill(status=200, content_type="application/javascript", body=(ROOT / path.lstrip("/")).read_text(encoding="utf-8"))
        if path in ("/", "/family/7"):
            return route.fulfill(status=200, content_type="text/html", body=self.html)
        if path == "/family":
            return route.fulfill(status=200, content_type="text/html", body="<html><body id=family-list>list</body></html>")
        if path == "/api/family/archived" and req.method == "GET":
            return route.fulfill(status=200, content_type="application/json", body=json.dumps({"ok": True, "archived": self.archived}))
        self.calls.append((req.method, path, req.headers.get("x-csrf-token")))
        queue = self.answers.get((req.method, path)) or [200]
        ans = queue.pop(0) if len(queue) > 1 else queue[0]
        if ans == "abort":
            return route.abort("connectionreset")
        if isinstance(ans, tuple) and ans[0] == "raw":                 # ("raw", status, content_type, body): arbitrary reply
            return route.fulfill(status=ans[1], content_type=ans[2], body=ans[3])
        slow = isinstance(ans, tuple)
        if slow:
            self.page.wait_for_timeout(700)
            ans = ans[1]
        body = {"ok": True} if ans == 200 else {"ok": False, "error": {404: "family_member_not_found", 403: "csrf", 500: "server"}.get(ans, "x")}
        return route.fulfill(status=ans, content_type="application/json", body=json.dumps(body))

    def n(self, method):
        return len([c for c in self.calls if c[0] == method])


@pytest.fixture()
def browser_page():
    with playwright.sync_playwright() as p:
        b = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None)
        pg = b.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        yield pg, errors
        b.close()
        assert not errors, errors


def _open_delete(pg, site):
    pg.goto(ORIGIN + "/family/7")
    pg.click("#famDelete >> text=حذف هذا الفرد")


def _status(pg, sel):
    return pg.inner_text(sel)


@pytest.mark.parametrize("answer,expect_unlocked,expect_text", [
    ("abort", True, "لا نعرف"),          # connection dropped: outcome unknown, buttons come back
    (("raw", 200, "application/json", ""), True, "لا نعرف"),                  # 200 with an empty body: no confirmation
    (("raw", 200, "text/html", "<html>proxy page</html>"), True, "لا نعرف"),  # 200 with HTML: not our API
    (("raw", 200, "application/json", "{not json"), True, "لا نعرف"),         # invalid JSON
    (("raw", 200, "application/json", "{}"), True, "لا نعرف"),                # JSON without ok:true
    (("raw", 200, "application/json", '{"ok": false, "error": "x"}'), True, "لم يتغير شيء"),  # explicit refusal inside a 200
    (("raw", 404, "text/html", "<h1>Not Found</h1>"), True, "لا نعرف"),       # bare 404 (proxy/route) is NOT proof of deletion
    (500, True, "لا نعرف"),              # server error: outcome unknown
    (403, True, "لم يتغير شيء"),         # refused: definite failure, nothing changed
])
def test_delete_page_unsure_and_failed_outcomes_re_enable_buttons(browser_page, answer, expect_unlocked, expect_text):
    pg, _ = browser_page
    site = Site(pg, DELETE_PAGE); site.answers[("DELETE", "/api/family/7")] = [answer]
    _open_delete(pg, site)
    pg.click('#famDelete button:has-text("إزالة الفرد مع أرشفة")')
    pg.wait_for_selector('#famDelete [role=status]:has-text("%s")' % expect_text)
    assert pg.is_enabled('#famDelete button:has-text("إزالة الفرد مع أرشفة")')      # finally{} released the lock
    assert pg.is_enabled('#famDelete button:has-text("إلغاء")')
    assert pg.url == ORIGIN + "/family/7"
    assert site.calls == [("DELETE", "/api/family/7", "tok123")]
    # the failure is distinguishable: "unsure" mentions reloading, "failed" says nothing changed
    text = _status(pg, "#famDelete [role=status]")
    assert ("حدّثي الصفحة" in text) is (answer != 403 and not (isinstance(answer, tuple) and '"ok": false' in answer[3]))
    # and a retry works afterwards
    site.answers[("DELETE", "/api/family/7")] = [200]
    pg.click('#famDelete button:has-text("إزالة الفرد مع أرشفة")')
    pg.wait_for_url(ORIGIN + "/family")
    assert site.n("DELETE") == 2


@pytest.mark.parametrize("answer", [200, 404])
def test_delete_page_success_and_already_gone_both_leave_the_page(browser_page, answer):
    pg, _ = browser_page
    site = Site(pg, DELETE_PAGE); site.answers[("DELETE", "/api/family/7")] = [answer]
    _open_delete(pg, site)
    pg.click('#famDelete button:has-text("إزالة الفرد مع أرشفة")')
    pg.wait_for_url(ORIGIN + "/family")
    assert site.calls[0][1] == "/api/family/7"


def test_delete_page_permanent_delete_needs_two_presses_and_double_click_sends_one_request(browser_page):
    pg, _ = browser_page
    site = Site(pg, DELETE_PAGE); site.answers[("DELETE", "/api/family/7?delete_data=1")] = [("slow", 200)]
    _open_delete(pg, site)
    wipe = pg.locator('#famDelete button:has-text("حذف الفرد وجميع بياناته")')
    wipe.click()
    assert site.n("DELETE") == 0 and pg.locator('#famDelete button[data-armed="1"]').count() == 1
    pg.locator('#famDelete button[data-armed="1"]').dblclick()
    pg.wait_for_url(ORIGIN + "/family")
    assert [c[1] for c in site.calls if c[0] == "DELETE"] == ["/api/family/7?delete_data=1"]


def test_delete_page_confirmation_expires_after_eight_seconds(browser_page):
    pg, _ = browser_page
    site = Site(pg, DELETE_PAGE)
    _open_delete(pg, site)
    wipe = pg.locator('#famDelete button:has-text("حذف الفرد وجميع بياناته")')
    wipe.click()
    assert pg.locator('#famDelete button[data-armed="1"]').count() == 1
    pg.wait_for_timeout(7000)
    assert pg.locator('#famDelete button[data-armed="1"]').count() == 1       # still armed before 8 s
    pg.wait_for_timeout(1500)
    assert pg.locator('#famDelete button[data-armed="1"]').count() == 0       # disarmed after 8 s
    wipe.click()                                                               # a press after expiry only re-arms
    assert site.n("DELETE") == 0


def test_archive_restore_failures_are_reported_and_buttons_come_back(browser_page):
    pg, _ = browser_page
    site = Site(pg, ARCHIVE_PAGE)
    url = ("POST", "/api/family/archived/5/restore")
    pg.goto(ORIGIN + "/")
    pg.wait_for_selector('#famArchive button:has-text("Restore")')
    for answer, text in (("abort", "cannot tell"), (500, "cannot tell"), (403, "nothing was changed")):
        site.answers[url] = [answer]
        pg.click('#famArchive button:has-text("Restore")')
        pg.wait_for_selector('#famArchive [role=status]:has-text("%s")' % text)
        assert pg.is_enabled('#famArchive button:has-text("Restore")') and pg.is_enabled('#famArchive button:has-text("Delete permanently")')
        pg.evaluate("document.querySelector('#famArchive [role=status]').textContent=''")
    assert site.n("POST") == 3
    site.answers[url] = [200]
    pg.click('#famArchive button:has-text("Restore")')
    pg.wait_for_function("window.performance.getEntriesByType('navigation')[0].type === 'reload'")


def test_archive_duplicate_clicks_while_a_request_runs_send_one_request(browser_page):
    pg, _ = browser_page
    site = Site(pg, ARCHIVE_PAGE); site.answers[("POST", "/api/family/archived/5/restore")] = [("slow", 200)]
    pg.goto(ORIGIN + "/")
    pg.wait_for_selector('#famArchive button:has-text("Restore")')
    pg.locator('#famArchive button:has-text("Restore")').dblclick()
    pg.wait_for_function("window.performance.getEntriesByType('navigation')[0].type === 'reload'")
    assert site.n("POST") == 1


def test_archive_permanent_delete_double_confirm_timeout_unknown_and_gone(browser_page):
    pg, _ = browser_page
    site = Site(pg, ARCHIVE_PAGE)
    url = ("DELETE", "/api/family/archived/5")
    pg.goto(ORIGIN + "/")
    erase = pg.locator('#famArchive button:has-text("Delete permanently")')
    erase.wait_for()
    erase.click()
    assert site.n("DELETE") == 0 and pg.locator('#famArchive button[data-armed="1"]').count() == 1
    pg.wait_for_timeout(8600)
    assert pg.locator('#famArchive button[data-armed="1"]').count() == 0 and "Delete permanently" in erase.inner_text()
    # connection drops during the confirmed delete: uncertain message, buttons back, confirmation reset
    site.answers[url] = ["abort"]
    erase.click(); pg.locator('#famArchive button[data-armed="1"]').click()
    pg.wait_for_selector('#famArchive [role=status]:has-text("cannot tell")')
    assert pg.is_enabled('#famArchive button:has-text("Restore")') and "Delete permanently" in erase.inner_text()
    assert site.n("DELETE") == 1
    # someone else already removed it: 404 refreshes the list
    site.answers[url] = [404]
    erase.click(); pg.locator('#famArchive button[data-armed="1"]').click()
    pg.wait_for_function("window.performance.getEntriesByType('navigation')[0].type === 'reload'")
    assert site.n("DELETE") == 2


def test_archive_restore_with_unusable_replies_never_reloads_and_keeps_buttons(browser_page):
    pg, _ = browser_page
    site = Site(pg, ARCHIVE_PAGE)
    url = ("POST", "/api/family/archived/5/restore")
    pg.goto(ORIGIN + "/")
    pg.wait_for_selector('#famArchive button:has-text("Restore")')
    pg.evaluate("window.__marker = 1")
    for reply in (("raw", 200, "application/json", ""), ("raw", 200, "text/html", "<p>x</p>"), ("raw", 200, "application/json", "[]"),
                  ("raw", 200, "application/json", "null"), ("raw", 404, "application/json", "{}")):
        site.answers[url] = [reply]
        pg.click('#famArchive button:has-text("Restore")')
        pg.wait_for_selector('#famArchive [role=status]:has-text("cannot tell")')
        assert pg.is_enabled('#famArchive button:has-text("Restore")') and pg.is_enabled('#famArchive button:has-text("Delete permanently")')
        pg.evaluate("document.querySelector('#famArchive [role=status]').textContent=''")
    assert pg.evaluate("window.__marker") == 1              # the page was never reloaded on an unconfirmed answer
    assert site.n("POST") == 5                              # exactly one request per click, no hidden retries
