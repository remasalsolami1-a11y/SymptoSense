import source_bundle
from pathlib import Path

WEB = source_bundle.webapp_text()

def test_language_flow_keeps_direct_server_side_navigation():
    assert 'def persist_explicit_language_selection(response):' in WEB
    assert 'request.args.get("lang") or request.cookies.get("lang")' in WEB
    assert '"start_url": f"{lang_prefix}/?source=pwa"' in WEB

def test_picker_links_remain_direct_and_clickable():
    assert 'ar_target = _localized_target_from_legacy(next_target, "ar")' in WEB
    assert 'en_target = _localized_target_from_legacy(next_target, "en")' in WEB
    block = WEB[WEB.index(".first-lang-loading"):WEB.index(".first-lang-loading")+120]
    assert "pointer-events:none" not in block
