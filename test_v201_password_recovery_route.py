import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()


def test_tokenized_auth_routes_bypass_first_visit_language_picker():
    assert 'if legacy_public or _is_tokenized_auth_path(path):' in WEB
    assert 'or _is_tokenized_auth_path(path):' in WEB
    assert '_TOKENIZED_AUTH_PREFIXES = ("/reset-password/", "/verify-email/")' in WEB


def test_transactional_email_links_keep_token_route_and_carry_language():
    assert '_transactional_auth_url("reset-password", token, _lang())' in WEB
    assert '_transactional_auth_url("verify-email", token, lang)' in WEB
    assert 'urlencode({"lang": safe_lang, "set_lang": "1"})' in WEB


def test_language_picker_does_not_rewrite_reset_token_into_missing_page():
    assert 'if _is_tokenized_auth_path(parsed.path):' in WEB
    assert 'target = parsed.path' in WEB
    assert 'query_items.extend([("lang", lang if lang in _SUPPORTED_LANGS else "ar"), ("set_lang", "1")])' in WEB


def test_language_prefixed_legacy_token_links_remain_compatible():
    assert 'localized_reset_token = subpath.startswith("reset-password/")' in WEB
    assert 'localized_verify_token = subpath.startswith("verify-email/")' in WEB
    assert 'return reset_password(subpath.split("/", 1)[1])' in WEB
    assert 'return verify_email_token(subpath.split("/", 1)[1])' in WEB
