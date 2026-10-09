import source_bundle
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import blood_test
import safety_engine


def test_safety_engine_regression_matrix_passes():
    report = safety_engine.validation_report()
    assert report["total"] >= 10
    assert report["all_passed"] is True
    assert report["passed"] == report["total"]


def test_blood_parser_keeps_unknown_pipe_rows():
    text = """Mystery Biomarker | 4.2 | mg/L | 1.0 | 5.0 | Normal
HGB | 130 | g/L | 120 | 155 | Normal
Second New Marker | 9.1 | mmol/L | 3.0 | 10.0 | High
"""
    rows, _age = blood_test.parse_blood_text(text)
    names = {str(x.get("name") or x.get("key") or "") for x in rows}
    assert any("Mystery Biomarker" in n for n in names)
    assert any("Second New Marker" in n for n in names)
    assert any(str(x.get("key")) == "hgb" for x in rows)


def test_v152_static_completeness_and_traceability_guards_present():
    web = source_bundle.webapp_text()
    chat = source_bundle.chat_view_text()
    dash = (ROOT / "dashboard.py").read_text(encoding="utf-8")
    assert "LAB_PDF_MAX_BYTES" in web
    assert "The whole PDF is read" in web
    assert '"complete_page_read"' in web
    assert '"pages_read"' in web and '"pages_total"' in web
    assert "image_passes" in web and "audit_pass=True" in web
    assert "_ensure_analysis_match_sources" in web
    assert "symptom_context_fallback" in web
    assert "مرجع داعم للسياق" in chat
    assert "/api/admin/quality-dashboard" in web
    assert 'data-view="quality"' in dash
    assert "loadQuality" in dash


def test_v153_quality_period_and_server_verified_lab_receipt_guards_present():
    web = source_bundle.webapp_text()
    assert 'SELECT data FROM blood_tests WHERE timestamp>=' in web
    assert 'blood_extraction_receipt_v1' in web
    assert "fd.append('extraction_receipt',labxExtractionReceipt||'')" in web
    assert 'request.form.get("extraction_meta")' not in web[web.index('if mode == "analyze_confirmed":'):web.index('allowed = set(blood_test.REFS.keys())')]
    assert '"server_verified": True' in web


def test_v153_blood_module_has_one_public_analyzer_and_describer():
    source = (ROOT / "blood_test.py").read_text(encoding="utf-8")
    assert source.count('def analyze_blood(entries, gender="", age=None):') == 1
    assert source.count('def describe_results(results, lang="ar"):') == 1
    assert 'def _analyze_blood_v142_base' in source
    assert 'def _analyze_blood_v143_base' in source
