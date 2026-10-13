"""Shared pytest configuration.

* Since the canonical-language-URL change, legacy page URLs answer with a 301
  redirect to /ar/... or /en/.... Older tests request the legacy URL and expect
  the page itself, so GET requests transparently follow a canonical-language
  301/308 once. Tests that assert the redirect itself can pass
  ``follow_redirects=False`` explicitly (we only follow when the caller did not
  say anything) or call ``client.open`` with another method.
* Tests that pin the markup of UI that was replaced in V245-V247 (the old SVG
  body map and old landing/typography details) are skipped until rewritten.
"""
import pytest
from flask.testing import FlaskClient

_orig_open = FlaskClient.open


def _open(self, *args, **kwargs):
    explicit = "follow_redirects" in kwargs
    response = _orig_open(self, *args, **kwargs)
    method = str(kwargs.get("method") or "GET").upper()
    if (not explicit and method == "GET" and response.status_code in (301, 308)
            and getattr(self, "_canonical_follow_depth", 0) == 0):
        location = response.headers.get("Location", "")
        path = location.split("://", 1)[-1]
        path = "/" + path.split("/", 1)[1] if "://" in location and "/" in path else location
        if path.startswith(("/ar/", "/en/", "/ar", "/en")) and not path.startswith(("/ar/ar", "/en/en")):
            self._canonical_follow_depth = 1
            try:
                return _orig_open(self, path, method="GET",
                                  headers=kwargs.get("headers"))
            finally:
                self._canonical_follow_depth = 0
    return response


FlaskClient.open = _open

_OBSOLETE_IDS = {
    "test_stabilization.py::StabilizationTest::test_medications_has_iphone_home_screen_install_guidance",
}

# Every skipped test carries its own reason (why it is skipped and what replaces it).
SKIP_REASONS = {
    "test_stabilization.py::StabilizationTest::test_medications_has_iphone_home_screen_install_guidance":
        "feature removed: the iPhone 'add to home screen' card (#iosInstallCard) no longer exists on /meds; only the SafeID page keeps an install button",
}
OBSOLETE_UI_TESTS = {i: SKIP_REASONS.get(i, "obsolete: UI markup replaced in V245-V247; rewrite against current UI") for i in _OBSOLETE_IDS}

KNOWN_SEARCH_GAP = ()


def pytest_collection_modifyitems(config, items):
    import os
    run_all = os.environ.get("SS_RUN_SKIPPED_UI") == "1"      # SS_RUN_SKIPPED_UI=1 runs the skipped tests to see how they fail
    for item in items:
        if item.nodeid in OBSOLETE_UI_TESTS and not run_all:
            item.add_marker(pytest.mark.skip(reason=OBSOLETE_UI_TESTS[item.nodeid]))
        if item.nodeid in KNOWN_SEARCH_GAP:
            item.add_marker(pytest.mark.xfail(
                reason="known gap: /api/search consults the contextual handler before the topic KB and returns a generic direct answer for this topic",
                strict=False))
