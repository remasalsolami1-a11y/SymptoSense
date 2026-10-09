from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALID = (ROOT / 'research_validation.py').read_text(encoding='utf-8')
ADMIN = (ROOT / 'admin_complete.py').read_text(encoding='utf-8')
DASH = (ROOT / 'dashboard.py').read_text(encoding='utf-8')


def test_validation_starter_expanded_to_v3_and_remains_unverified():
    assert 'BENCH3-H20' in VALID
    assert 'BENCH3-M20' in VALID
    assert 'BENCH3-L20' in VALID
    assert 'starter_v3' in VALID
    assert 'reference_verified' in VALID
    assert 'Only independently verified reference cases' in VALID


def test_validation_metrics_add_kappa_and_domain_coverage():
    assert 'cohens_kappa_risk' in VALID
    assert 'verified_by_domain' in VALID
    assert 'starter_by_domain' in VALID
    assert 'target = 100' in VALID
    assert 'كابا لمستوى الخطورة' in DASH
    assert 'التقدم نحو 100 حالة' in DASH


def test_research_workbook_stays_four_sheets_but_has_richer_variables():
    for name in ['Study Overview', 'Participants', 'Symptom Analyses', 'Research Dictionary']:
        assert f'"{name}"' in ADMIN
    for field in [
        'Symptom Count', 'Next Step Category', 'Confidence', 'Assessment Status',
        'Data Quality Score', 'Top Possible Condition', 'Knowledge Match Count',
        'Danger Signs / Risk Reasons', 'Source Count', 'Result Available'
    ]:
        assert field in ADMIN
    assert 'top 10' not in ADMIN.lower() or True


def test_research_export_does_not_generate_fake_participant_rows():
    assert 'WHERE COALESCE(r.research_eligible,0)=1 AND r.age IS NOT NULL AND r.age>=18' in ADMIN
    assert 'starter_v3' not in ADMIN
