from pathlib import Path

WEBAPP = Path(__file__).resolve().parents[1] / "webapp.py"
TEXT = WEBAPP.read_text(encoding="utf-8")


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
    # The normal app shell is only used after the early bare return.
    assert block.index("if bare:") < block.index("ast = CT[")


def test_language_picker_keeps_requested_local_destination():
    block = _block("def welcome_page():", "\ndef home_page():")
    assert 'next_target = _safe_next_url("/home")' in block
    assert 'if next_target == "/" or next_target.startswith("/?")' in block
    assert 'body = body.replace("__NEXT__", json.dumps(next_target))' in block
    assert "window.location.href = SS_NEXT_PAGE || '/home'" in block


def test_language_picker_has_explicit_language_semantics():
    block = _block("def welcome_page():", "\ndef home_page():")
    for token in [
        'lang="ar" dir="rtl">افهم أعراضك.',
        'lang="en">Understand your symptoms.',
        'aria-label="اختيار العربية" lang="ar"',
        'aria-label="Choose English" lang="en"',
        'class="ss-sr-only"',
    ]:
        assert token in block, token
