import source_bundle
import versioning
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

import lab_intake
import blood_test


def _doc_bytes(size=(1200, 1600), blur=0, bg="white"):
    img = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(img)
    if size[0] >= 800 and size[1] >= 1000:
        for y in range(80, size[1] - 80, 42):
            draw.text((75, y), "Hemoglobin 12.3 g/dL  12.0 - 15.0  Normal", fill="black")
            draw.line((65, y + 20, size[0] - 80, y + 20), fill=(130, 130, 130), width=1)
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=90)
    return out.getvalue()


def test_quality_gate_accepts_readable_document_without_false_glare_warning():
    q = lab_intake.assess_image_quality(_doc_bytes())
    assert q["blocking"] is False
    assert q["issues"] == []
    assert "glare_or_overexposure" not in q["warnings"]


def test_quality_gate_blocks_dark_low_resolution_and_severe_blur():
    dark = lab_intake.assess_image_quality(_doc_bytes(bg=(5, 5, 5)))
    small = lab_intake.assess_image_quality(_doc_bytes(size=(300, 400)))
    blur = lab_intake.assess_image_quality(_doc_bytes(blur=8))
    assert dark["blocking"] and "too_dark" in dark["issues"]
    assert small["blocking"] and "low_resolution" in small["issues"]
    assert blur["blocking"] and "very_blurry_or_low_contrast" in blur["issues"]


def test_vision_payload_parses_metadata_quality_rows_and_bbox():
    payload = lab_intake.parse_vision_payload(
        "META | LAB=Example Lab | SAMPLE_DATE=2026-09-30 | REPORT_DATE=2026-10-01 | REPORT_TYPE=CBC | AGE=22 years\n"
        "QUALITY | STATUS=good | ISSUES=\n"
        "TEST | HGB | 10.8 | g/dL | 12 | 15 | Low | 100,200,900,250\n"
    )
    assert payload["meta"]["lab_name"] == "Example Lab"
    assert payload["meta"]["sample_date"] == "2026-09-30"
    assert payload["quality"]["status"] == "good"
    assert payload["evidence"][0]["bbox"] == [100, 200, 900, 250]
    rows, age = blood_test.parse_blood_text(payload["clean_text"])
    assert rows and rows[0]["value"] == 10.8


def test_double_pass_agreement_does_not_require_confirmation():
    a = lab_intake.parse_vision_payload("TEST | HGB | 10.8 | g/dL | 12 | 15 | Low | 100,200,900,250")
    b = lab_intake.parse_vision_payload("TEST | HGB | 10.8 | g/dL | 12 | 15 | Low | 102,202,902,252")
    rows, _ = lab_intake.merge_double_pass(a, b, page=1)
    hgb = next(x for x in rows if x["key"] == "hgb")
    assert hgb["review_required"] is False
    assert hgb["source_page"] == 1
    assert hgb["source_bbox"]


def test_double_pass_value_disagreement_requires_explicit_confirmation_id():
    a = lab_intake.parse_vision_payload("TEST | HGB | 10.8 | g/dL | 12 | 15 | Low | 100,200,900,250")
    b = lab_intake.parse_vision_payload("TEST | HGB | 16.8 | g/dL | 12 | 15 | High | 100,200,900,250")
    rows, _ = lab_intake.merge_double_pass(a, b, page=1)
    hgb = next(x for x in rows if x["key"] == "hgb")
    assert hgb["review_required"] is True
    assert "value_disagreement" in hgb["review_reasons"]
    assert hgb["review_id"]
    assert hgb["pass1_value"] == 10.8
    assert hgb["pass2_value"] == 16.8


def test_one_pass_only_row_requires_review():
    a = lab_intake.parse_vision_payload("TEST | HGB | 10.8 | g/dL | 12 | 15 | Low | 100,200,900,250")
    b = lab_intake.parse_vision_payload("QUALITY | STATUS=good | ISSUES=")
    rows, _ = lab_intake.merge_double_pass(a, b, page=1)
    assert rows[0]["review_required"] is True
    assert "seen_in_one_pass_only" in rows[0]["review_reasons"]


def test_multi_page_duplicate_is_deduped_but_cross_page_conflict_is_reviewed():
    same = [
        {"key":"hgb","name":"HGB","value":10.8,"unit":"g/dL","review_required":False,"review_reasons":[],"source_page":1,"review_id":"a"},
        {"key":"hgb","name":"HGB","value":10.8,"unit":"g/dL","review_required":False,"review_reasons":[],"source_page":2,"review_id":"b"},
    ]
    out = lab_intake.combine_page_entries(same)
    assert len(out) == 1 and out[0]["review_required"] is False
    conflict = same[:1] + [{"key":"hgb","name":"HGB","value":16.8,"unit":"g/dL","review_required":False,"review_reasons":[],"source_page":2,"review_id":"c"}]
    out2 = lab_intake.combine_page_entries(conflict)
    assert len(out2) == 1 and out2[0]["review_required"] is True
    assert "across_pages_disagreement" in out2[0]["review_reasons"]


def test_report_metadata_merge_flags_disagreement_and_infers_panel():
    rows = [{"key":"hgb"},{"key":"wbc"}]
    meta = lab_intake.merge_report_metadata([
        {"lab_name":"A Lab","sample_date":"2026-09-30","report_type":""},
        {"lab_name":"A Lab","sample_date":"2026-10-01","report_type":""},
    ], rows)
    assert meta["lab_name"] == "A Lab"
    assert meta["report_type"].startswith("CBC")
    assert "sample_date" in meta["metadata_review_fields"]


def test_report_preview_is_jpeg_base64_and_not_persisted_by_helper(tmp_path):
    before = set(tmp_path.iterdir())
    preview = lab_intake.make_page_preview(_doc_bytes())
    assert isinstance(preview, str) and len(preview) > 100
    assert set(tmp_path.iterdir()) == before


def test_health_context_lab_symptom_link_is_non_diagnostic():
    indicators = [{"key":"hgb","name":"Hemoglobin","value":10.2,"unit":"g/dL","status":"low"}]
    links = lab_intake.build_health_context_links(indicators, {"symptoms":["دوخة","تعب"]}, "", "ar")
    assert links
    text = links[0]["text"]
    assert "قد توجد علاقة" in text
    assert "لا تحدد سبب" in text
    assert "تشخيص" in text


def test_health_context_recognized_medication_is_context_not_causation():
    links = lab_intake.build_health_context_links([], {"symptoms":["nausea"]}, "metformin", "en")
    assert links
    text = links[-1]["text"].lower()
    assert "metformin" in text
    assert "nausea" in text
    assert "does not prove" in text
    assert "do not stop" in text


def test_history_uses_report_sample_date_before_database_timestamp():
    current = [{"key":"hgb","name":"Hemoglobin","value":11.4,"unit":"g/dL"}]
    prior = [{"timestamp":"2026-01-01T00:00:00Z","data":{"report_meta":{"sample_date":"2025-12-15"},"indicators":[{"key":"hgb","value":10.7,"unit":"g/dL"}]}}]
    trend = blood_test.compare_with_history(current, prior, "en", current_report_meta={"sample_date":"2026-08-12"})
    assert trend["available"] is True
    series = trend["items"][0]["series"]
    assert series[0]["timestamp"] == "2025-12-15"
    assert series[-1]["timestamp"] == "2026-08-12"


def test_webapp_contains_pdf_only_intake_and_server_confirmation_guards():
    text = source_bundle.webapp_text()
    required = [
        'id="bloodUploadBtn"', 'id="fileInp" accept="application/pdf,.pdf"',
        'request.files.getlist("files")', 'pdf_only_required',
        'required_review_ids', 'blood_disagreement_confirmation_required',
        'id="labEvidenceModal"', 'health_context_links', 'report_meta',
    ]
    for token in required:
        assert token in text, token
    assert 'id="bloodCameraBtn"' not in text
    assert 'id="cameraInp"' not in text


def test_webapp_does_not_persist_source_page_previews_in_saved_payload():
    text = source_bundle.webapp_text()
    start = text.index('payload = {', text.index('summary_text = blood_test.summary_text', text.index('def api_blood')))
    payload_block = text[start:text.index('blood_id = None', start)]
    assert '"source_pages"' not in payload_block
    assert '"source_file_stored": False' in payload_block


def test_vision_quality_issue_mapping_is_specific_and_conservative():
    assert "page_may_be_cropped" in lab_intake.canonical_vision_quality_issues(["bottom of page appears cut off"])
    assert "very_blurry_or_low_contrast" in lab_intake.canonical_vision_quality_issues(["image is blurry"])
    assert lab_intake.canonical_vision_quality_issues(["unreadable table structure"]) == ["vision_reported_unreadable"]


def test_pdf_or_image_source_evidence_can_be_attached_without_changing_value():
    entries = [{"key":"hgb","value":10.8,"unit":"g/dL"}, {"key":"wbc","value":6.1,"unit":"10^9/L"}]
    candidates = [{"key":"hgb","value":10.8,"source_page":2,"source_bbox":[100,200,900,260]}]
    out = lab_intake.attach_source_evidence(entries, candidates)
    assert out[0]["value"] == 10.8
    assert out[0]["source_page"] == 2
    assert out[0]["source_bbox"] == [100,200,900,260]
    assert "source_page" not in out[1]


def test_service_worker_cache_is_bumped_for_v199_camera_ui():
    sw = Path(__file__).with_name("service-worker.js").read_text(encoding="utf-8")
    assert versioning.SW_CACHE in sw


def test_v207_frontend_and_server_enforce_pdf_only_upload():
    text = source_bundle.webapp_text()
    assert 'accept="application/pdf,.pdf"' in text
    assert "Blood-test analysis accepts PDF files only." in text
    assert '"error_code": "pdf_only_required"' in text
    assert 'capture="environment"' not in text


def test_v199_confirmation_dashboard_counts_are_mutually_exclusive():
    text = source_bundle.webapp_text()
    assert "const unresolvedIds=new Set" in text
    assert "if(unresolvedRow)return false" in text
    assert "const needsReview=unresolved.length" in text
