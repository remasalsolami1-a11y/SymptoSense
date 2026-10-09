import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def text(name):
    return (ROOT / name).read_text(encoding='utf-8')

def test_research_freeze_covers_web_request_logic():
    s = text('research_study.py')
    assert '"webapp.py"' in s
    assert 'record_matches_active_freeze' in s

def test_official_and_pilot_exports_are_separate():
    s = text('admin_complete.py')
    assert 'dataset_scope: str = "official"' in s
    assert 'dataset_scope == "official"' in s
    w = source_bundle.webapp_text()
    assert '/api/admin/export/pilot-xlsx' in w
    assert 'export_admin_workbook("official")' in w
    assert 'export_admin_workbook("pilot")' in w

def test_bot_does_not_log_raw_symptoms_or_user_id_in_analysis_events():
    s = text('bot.py')
    assert 'ANALYSIS START: user=%s symptoms=%s' not in s
    assert 'ANALYSIS DONE: user=%s' not in s

def test_admin_session_and_rate_controls_present():
    w = source_bundle.webapp_text()
    assert 'admin_security.current_epoch' in w
    assert '/api/admin/sessions/logout-all' in w
    assert '_request_allowed("assistant"' in w
    assert '_request_allowed("register"' in w

def test_retention_cleanup_does_not_time_delete_health_records():
    s = text('data_retention.py')
    assert 'Never deletes symptom/health records' in s
    assert 'HEALTH_DATA_RETENTION_DAYS' in s

def test_accessibility_landmarks_and_focus_are_global():
    w = source_bundle.webapp_text()
    assert 'class="ss-skip-link"' in w
    assert 'id="main-content"' in w
    assert ':focus-visible' in w
    assert 'prefers-reduced-motion' in w
    assert 'aria-modal="true"' in w
