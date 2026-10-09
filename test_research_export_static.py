import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ADMIN = (ROOT / "admin_complete.py").read_text(encoding="utf-8")
DASH = (ROOT / "dashboard.py").read_text(encoding="utf-8")
WEB = source_bundle.webapp_text()


def test_research_export_has_clear_research_sheets():
    for name in [
        "Study Overview", "Participants", "Symptom Analyses", "Research Dictionary",
    ]:
        assert f'"{name}"' in ADMIN
    for removed in [
        "Analysis Outputs", "Medications", "Follow-up Outcomes", "Feedback Ratings",
        "Usage Summary", "Data Quality", "Data Dictionary",
    ]:
        assert f'add_sheet("{removed}"' not in ADMIN


def test_export_uses_one_pseudonymous_subject_key_across_tables():
    assert 'def subject_id(user_hash: str)' in ADMIN
    assert '_anonymous_id("subject:" + str(user_hash))' in ADMIN
    assert 'subject_id(h)' in ADMIN


def test_research_export_excludes_high_risk_direct_content():
    lower = ADMIN.lower()
    assert "free-text feedback comments" in lower and "excluded" in lower
    assert "exact location" in lower
    assert "raw chat content" in lower
    assert 'select email' not in lower[lower.index('def export_admin_workbook'):]


def test_admin_has_research_export_center_and_readiness_block():
    assert "مركز التصدير والبحث" in DASH
    assert "Scientific Research Workbook" in DASH
    assert 'id="researchReadiness"' in DASH
    assert "Research Data Readiness" in DASH


def test_empty_analytics_charts_explain_privacy_suppression():
    assert "setChartEmpty" in DASH
    assert "below the privacy threshold" in DASH
    assert "النتائج أقل من حد الخصوصية" in DASH


def test_export_audit_metadata_matches_research_workbook():
    assert '"sheets": 4' in WEB
    assert '"purpose": "scientific_research_export"' in WEB
    assert "SymptoSense_Research_Export_" in WEB
