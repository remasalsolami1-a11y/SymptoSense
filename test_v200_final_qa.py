import source_bundle
import versioning
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()
SW = (ROOT / 'service-worker.js').read_text(encoding='utf-8')
DOCKER = (ROOT / 'Dockerfile').read_text(encoding='utf-8')
MIC = (ROOT / 'test_symptom_microphone.js').read_text(encoding='utf-8')
DEPLOY = (ROOT / 'DEPLOY_GUIDE_AR.md').read_text(encoding='utf-8')
METRICS = json.loads((ROOT / 'release_metrics.json').read_text(encoding='utf-8'))


def test_lab_upload_ui_is_single_pdf_only_before_server():
    assert 'id="fileInp" accept="application/pdf,.pdf"' in WEB
    assert 'if(list.length!==1)' in WEB
    assert "Blood-test analysis accepts PDF files only." in WEB
    assert 'LAB_PDF_MAX_BYTES = 25 * 1024 * 1024' in WEB


def test_lab_review_dashboard_counts_are_mutually_exclusive():
    assert 'const unresolvedIds=new Set(unresolved.map' in WEB
    assert 'const unresolvedRow=r.review_required&&r.review_id&&unresolvedIds.has' in WEB
    assert 'if(unresolvedRow)return false' in WEB


def test_pdf_only_control_is_present_and_camera_controls_are_absent():
    for token in (
        'id="bloodUploadBtn"',
        'id="fileInp" accept="application/pdf,.pdf"',
        'id="labPageTray"', 'LAB_PDF_MAX_BYTES = 25 * 1024 * 1024',
    ):
        assert token in WEB
    for token in ('id="bloodCameraBtn"', 'id="cameraInp"', 'cameraUseBtn', 'cameraRetakeBtn'):
        assert token not in WEB


def test_double_read_confirmation_is_server_enforced():
    for token in (
        'blood_extraction_receipt_v1',
        'blood_disagreement_confirmation_required',
        'required_review_ids',
        'confirmed_review_ids',
    ):
        assert token in WEB


def test_root_microphone_regression_test_uses_current_flat_layout():
    assert "path.join(__dirname, 'views/chat_view.py')" in MIC
    assert "path.join(__dirname, '../views/chat_view.py')" not in MIC


def test_release_metadata_and_pwa_cache_are_current():
    assert METRICS['delivery_revision'] == versioning.REVISION
    assert versioning.SW_CACHE in SW
    assert "SymptoSense Railway build profile: " + versioning.REVISION in DOCKER
    assert "SymptoSense " + versioning.REVISION + " production build validation passed" in DOCKER


def test_core_visual_assets_exist_and_are_nonempty():
    paths = [
        'static/images/symptosense-social-preview.png',
        'static/images/safeid-add-to-phone-guide.png',
        'static/images/about-hero.webp',
        'static/images/about-home-preview.webp',
        'static/images/about-story.webp',
        'icons/icon-192.png', 'icons/icon-512.png', 'icons/apple-touch-icon.png',
    ]
    for rel in paths:
        p = ROOT / rel
        assert p.is_file() and p.stat().st_size > 100, rel


def test_sentry_optional_production_setup_is_documented():
    assert 'SENTRY_DSN' in DEPLOY
