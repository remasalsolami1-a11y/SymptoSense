import source_bundle
from pathlib import Path

WEBAPP = Path(__file__).resolve().parent / "webapp.py"
TEXT = source_bundle.webapp_text()

def _block(start_token, end_token):
    start = TEXT.index(start_token)
    end = TEXT.index(end_token, start)
    return TEXT[start:end]

def test_bare_landing_has_its_own_minimal_document_shell():
    block = _block("def _page(", "\n\n# ---------------------------------------------------------------- landing")
    assert "if bare:" in block
    assert '<body>{body}</body>' in block
    assert '<link rel="manifest" href="/manifest.webmanifest">' in block
    assert '/static/images/symptosense-social-preview.png' in block
    assert block.index("if bare:") < block.index("ast = CT[")

def test_language_picker_keeps_requested_local_destination_directly():
    block = _block("def welcome_page():", "\ndef home_page():")
    assert 'next_target = _safe_next_url("/home")' in block
    assert 'if next_target == "/" or next_target.startswith("/?")' in block
    assert 'ar_target = _localized_target_from_legacy(next_target, "ar")' in block
    assert 'en_target = _localized_target_from_legacy(next_target, "en")' in block
    assert 'href="__LANG_AR_TARGET__"' in block
    assert 'href="__LANG_EN_TARGET__"' in block

def test_language_picker_has_explicit_language_semantics():
    block = _block("def welcome_page():", "\ndef home_page():")
    for token in [
        'lang="ar" dir="rtl">افهم أعراضك<em>واعرف خطوتك التالية</em>',
        'lang="en">Understand your symptoms<em>and know your next step</em>',
        'aria-label="اختيار العربية" lang="ar"',
        'aria-label="Choose English" lang="en"',
        'class="ss-sr-only"',
    ]:
        assert token in block, token
