import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ADMIN = (ROOT / "admin_complete.py").read_text(encoding="utf-8")
DASH = (ROOT / "dashboard.py").read_text(encoding="utf-8")
WEB = source_bundle.webapp_text()


def test_dashboard_has_all_analysis_results_button_and_view():
    assert "عرض جميع نتائج التحليلات" in DASH
    assert 'id="view-results"' in DASH
    assert "loadAnalysisResults" in DASH
    assert "renderResultDetails" in DASH


def test_analysis_results_api_is_admin_only_and_deidentified():
    assert '@app.route("/api/admin/analysis-results", methods=["GET"])' in WEB
    assert '@admin_api_required("access")' in WEB
    assert "admin_complete.admin_analysis_results" in WEB
    assert "research_eligible_deidentified" in ADMIN
    assert "COALESCE(r.research_eligible,0)=1" in ADMIN


def test_analysis_results_exclude_direct_identifiers_and_raw_private_fields():
    block = ADMIN[ADMIN.index("def admin_analysis_results"):ADMIN.index("def export_admin_workbook")]
    lower = block.lower()
    assert "email" not in lower
    assert "password" not in lower
    assert "chat" in lower  # documented as deliberately excluded
    assert '"notes"' not in lower
    assert '"allergies"' not in lower
    assert '"location"' not in lower


def test_result_detail_includes_research_useful_output_fields():
    for field in [
        "possible_conditions", "why_result", "danger_signs", "when_to_seek_care",
        "home_care", "medication_guidance", "questions_for_doctor",
        "knowledge_matches", "risk_reasons", "medical_sources", "data_quality",
    ]:
        assert field in ADMIN
        assert field in DASH
