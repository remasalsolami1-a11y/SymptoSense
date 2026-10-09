import source_bundle
from pathlib import Path
WEB=source_bundle.webapp_text()

def test_make_response_is_imported():
    assert "has_request_context, make_response" in "\n".join(WEB.splitlines()[:60])

def test_root_has_safe_language_fallback():
    s=WEB.index('@app.route("/")'); e=WEB.index('@app.route("/language/<code>"',s); b=WEB[s:e]
    assert "html = welcome_page()" in b and "except Exception:" in b
    assert 'href="/ar/"' in b and 'href="/en/"' in b

def test_500_html_also_gets_csp_nonces():
    s=WEB.index("def finalize_html_script_nonces"); b=WEB[s:s+1800]
    assert 'response.mimetype == "text/html"' in b
    assert "response.status_code < 500" not in b
    assert "<script nonce=" in b and "<style nonce=" in b

def test_500_request_id_is_escaped():
    s=WEB.index("def internal_error_page"); b=WEB[s:s+1800]
    assert 'html_lib.escape(str(request_id or ""), quote=True)' in b
