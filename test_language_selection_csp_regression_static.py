import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEBAPP = source_bundle.webapp_text()
SECURITY = (ROOT / "web_security.py").read_text(encoding="utf-8")


def test_csp_blocks_inline_handlers_but_picker_uses_real_links():
    assert "script-src-attr 'none'" in SECURITY
    start = WEBAPP.index("def welcome_page():")
    end = WEBAPP.index("\ndef home_page():", start)
    block = WEBAPP[start:end]
    assert 'onclick="ssChooseLanguage' not in block
    assert 'href="__LANG_AR_TARGET__"' in block
    assert 'href="__LANG_EN_TARGET__"' in block
    assert 'html_lib.escape(ar_target, quote=True)' in block
    assert 'html_lib.escape(en_target, quote=True)' in block


def test_legacy_language_route_preserves_safe_destination():
    start = WEBAPP.index("def choose_language(code):")
    end = WEBAPP.index('\n\n@app.route("/home")', start)
    block = WEBAPP[start:end]
    assert 'web_security.safe_internal_path(request.args.get("next"), "/home")' in block
    assert '_localized_target_from_legacy(next_target, lang)' in block
    assert 'code=303' in block


def test_direct_language_selection_persists_cookie_globally():
    assert 'def persist_explicit_language_selection(response):' in WEBAPP
    assert 'request.args.get("set_lang") == "1"' in WEBAPP
    assert 'response.set_cookie(' in WEBAPP
    assert 'samesite="Lax"' in WEBAPP
