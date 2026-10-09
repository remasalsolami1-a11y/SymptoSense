import source_bundle
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CHAT=source_bundle.chat_view_text()
CHAT2=source_bundle.chat_view_text()
WEB=source_bundle.webapp_text()
CSS=(ROOT/"static/css/v83_user_tools.css").read_text(encoding="utf-8")

def test_clinic_and_doctor_action_is_unified_with_icon_and_label_spans():
    for src in (CHAT,CHAT2):
        assert 'data-result-action="care-script"' not in src
        assert 'data-doctor-card-action' in src
        assert 'class="ss-action-icon"' in src
        assert 'class="ss-action-label"' in src
        assert 'ملخص للعيادة والطبيب' in src

def test_mobile_followup_grid_is_two_columns():
    assert 'grid-template-columns:repeat(2,minmax(0,1fr))' in CSS
    assert '.ss-user-actions .ss-report-actions{grid-template-columns:repeat(2,minmax(0,1fr))!important' in WEB

def test_mobile_action_keeps_icon_and_text_in_same_row():
    assert 'flex-direction:row' in CSS
    assert '.ss-user-actions .ss-action-icon' in CSS
    assert '.ss-user-actions .ss-action-label' in CSS

def test_global_mobile_rule_no_longer_forces_followup_one_column():
    assert '.ss-report-actions{grid-template-columns:1fr!important}' not in WEB
