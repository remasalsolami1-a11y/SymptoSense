from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from web_security import (
    build_csp,
    json_for_script,
    normalize_public_base_url,
    safe_internal_path,
    trusted_hosts_from_environment,
)


def test_json_for_script_blocks_script_breakout():
    payload = '</script><script>alert(1)</script>&\u2028'
    out = json_for_script(payload)
    assert '</script>' not in out.lower()
    assert '<' not in out and '>' not in out and '&' not in out
    assert '\\u003c' in out and '\\u0026' in out


def test_safe_internal_path_rejects_open_redirect_variants():
    for bad in (
        'https://evil.example/x', '//evil.example/x', '/\\evil.example/x',
        '/%2f%2fevil.example/x', '/%5cevil.example/x', '/%0d%0aLocation:evil', '\r\nLocation:https://evil.example',
    ):
        assert safe_internal_path(bad, '/home') == '/home'
    assert safe_internal_path('/chat?x=1#result', '/home') == '/chat?x=1#result'


def test_trusted_hosts_derive_custom_and_railway_domains():
    hosts = trusted_hosts_from_environment({
        'SITE_URL': 'https://symptosensehealth.com',
        'RAILWAY_PUBLIC_DOMAIN': 'symptosense-production.up.railway.app',
        'TRUSTED_HOSTS': '',
    })
    assert 'symptosensehealth.com' in hosts
    assert 'www.symptosensehealth.com' in hosts
    assert 'symptosense-production.up.railway.app' in hosts
    assert 'healthcheck.railway.app' in hosts


def test_trusted_hosts_allow_railway_healthcheck_without_public_domain():
    hosts = trusted_hosts_from_environment({
        'RAILWAY_ENVIRONMENT': 'production',
        'RAILWAY_PRIVATE_DOMAIN': 'symptosense.railway.internal',
        'TRUSTED_HOSTS': 'symptosensehealth.com',
    })
    assert 'symptosensehealth.com' in hosts
    assert 'symptosense.railway.internal' in hosts
    assert 'healthcheck.railway.app' in hosts


def test_csp_has_strong_non_script_directives():
    csp = build_csp(secure_transport=True)
    assert "object-src 'none'" in csp
    assert "base-uri 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "upgrade-insecure-requests" in csp
    assert "unsafe-eval" not in csp


def test_public_base_url_is_origin_only_and_rejects_unsafe_values():
    assert normalize_public_base_url("symptosensehealth.com/path?q=1") == "https://symptosensehealth.com"
    assert normalize_public_base_url("https://www.symptosensehealth.com/anything") == "https://www.symptosensehealth.com"
    assert normalize_public_base_url("https://user:pass@example.com") == ""
    assert normalize_public_base_url("javascript:alert(1)") == ""
    assert normalize_public_base_url("https://example.com\r\nInjected: x") == ""
