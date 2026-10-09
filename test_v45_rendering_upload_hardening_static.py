import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text() + "\n" + source_bundle.chat_view_text()
BLOOD = (ROOT / "blood_test.py").read_text(encoding="utf-8")


def test_dynamic_attribute_contexts_use_attribute_encoding_and_safe_links():
    assert "function escAttr(s)" in WEB
    assert "function safeLink(raw)" in WEB
    assert "data-question=\"'+escAttr(question)+'\"" in WEB
    assert "href=\"'+escAttr(safeLink(r.url))+'\"" in WEB
    assert "href=\"' + escAttr(safeLink(s.url)) + '\"" in WEB


def test_cbc_ocr_output_is_never_inserted_as_raw_html():
    assert "h += d.text_html || '';" not in WEB
    assert "Never trust OCR/LLM-derived content as HTML." in WEB
    assert "<b>Blood Test Report</b>" not in BLOOD
    assert "<b>تحليل الدم</b>" not in BLOOD


def test_voice_and_blood_uploads_have_parser_and_read_limits():
    assert '"/api/voice": _bounded_env_int("VOICE_UPLOAD_MAX_BYTES"' in WEB
    assert '"/api/blood": _bounded_env_int("BLOOD_UPLOAD_MAX_BYTES"' in WEB
    assert "f.read(voice_upload_limit + 1)" in WEB
    assert ("f.read(blood_upload_limit + 1)" in WEB or "up.read(blood_upload_limit + 1)" in WEB)


def test_all_literal_inline_scripts_are_syntax_checked_by_release_tool():
    checker_path = ROOT / "tools" / "release_check.py"
    if not checker_path.exists():
        checker_path = ROOT / "release_check.py"
    checker = checker_path.read_text(encoding="utf-8")
    assert "node" in checker and "--check" in checker
    assert "Inline JavaScript syntax" in checker
