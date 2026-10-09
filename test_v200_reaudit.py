import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()


def test_blood_ui_is_pdf_only_and_has_no_camera_path():
    assert 'id="fileInp" accept="application/pdf,.pdf"' in WEB
    assert 'id="bloodUploadBtn"' in WEB
    assert 'id="bloodCameraBtn"' not in WEB
    assert 'id="cameraInp"' not in WEB
    assert 'capture="environment"' not in WEB


def test_server_rejects_non_pdf_before_report_extraction():
    guard = WEB.index('if upload_kind != "pdf"')
    pdf_open = WEB.index('fitz.open(stream=raw, filetype="pdf")', guard)
    assert guard < pdf_open
    assert '"error_code": "pdf_only_required"' in WEB[guard:pdf_open]


def test_pdf_intake_accepts_text_and_scanned_pdf_paths_without_page_count_rejection():
    assert 'V207 PDF-only intake: valid PDFs are not rejected by page count.' in WEB
    assert 'pdf_page_limit' not in WEB
    assert 'pending_vision = []' in WEB
    assert '_safe_pdf_page_png(page)' in WEB


def test_disagreement_confirmation_guards_remain_present():
    for token in (
        "blood_disagreement_confirmation_required",
        "required_review_ids",
        "confirmed_review_ids",
        'data-labx-action="evidence"',
    ):
        assert token in WEB
