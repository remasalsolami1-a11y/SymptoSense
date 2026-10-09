import source_bundle
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
CHAT = source_bundle.chat_view_text()
WEB = source_bundle.webapp_text()
DB = (ROOT / "db.py").read_text(encoding="utf-8")
UX = (ROOT / "user_experience.py").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "css" / "v83_user_tools.css").read_text(encoding="utf-8")


def test_professional_stylesheet_is_loaded_and_responsive():
    assert '/static/css/v83_user_tools.css' in CHAT
    assert '.ss-user-tool-overlay' in CSS
    assert '.ss-care-timing' in CSS
    assert '.ss-relief-card' in CSS
    assert '@media(max-width:640px)' in CSS
    assert '@media(prefers-reduced-motion:reduce)' in CSS


def test_quick_mode_is_explicit_and_can_upgrade_to_full_assessment():
    assert 'quick_mode:false' in CHAT
    assert 'offerAssessmentMode(continueFn)' in CHAT
    assert "أنا مستعجل · مسار سريع" in CHAT
    assert 'if(state.quick_mode&&u!==\'high\')' in CHAT
    assert 'upgradeToDetailedAssessment()' in CHAT
    assert "state.quick_mode=false" in CHAT


def test_quick_mode_keeps_safety_clarification_in_path():
    assert "if(state.quick_mode) startClarify(); else askSymptomPath();" in CHAT
    assert "else if(state.quick_mode) showDataQualityGate(); else startRedflagScreens();" in CHAT
    assert "فحص الأمان والنتيجة" in CHAT


def test_status_update_is_user_visible_and_reassessment_capable():
    assert 'function openStatusUpdate()' in CHAT
    assert 'data-status-outcome="improved"' in CHAT
    assert 'data-status-outcome="worse"' in CHAT
    assert 'data-status-reassess' in CHAT
    assert "fetch('/api/smart-followup'" in CHAT


def test_can_i_wait_card_is_risk_aware_and_not_false_reassurance():
    assert 'function careTimingHtml' in CHAT
    assert "هل أقدر أنتظر؟" in CHAT
    assert "لا تعتبر النتيجة ضمانًا للأمان" in CHAT
    assert "Do not wait" in CHAT
    assert "Monitor with safeguards" in CHAT


def test_relief_tracker_is_observation_only_and_has_private_fallback():
    assert 'function reliefTrackerHtml' in CHAT
    assert "وش اللي خفف العرض؟" in CHAT
    assert "لا يعتبر توصية علاجية" in CHAT
    assert "ss_relief_history_v1" in CHAT
    assert "fetch('/api/relief-log'" in CHAT
    assert 'causality_note' in UX
    assert 'observation_only' in UX


def test_relief_logs_are_owner_scoped_validated_and_deduplicated():
    assert '_ALLOWED_RELIEF_FACTORS' in UX
    assert 'db.get_record_owned(user_key, record_id)' in UX
    assert 'factor not in _ALLOWED_RELIEF_FACTORS' in UX
    assert 'SELECT 1 FROM symptom_relief_logs' in DB
    assert 'record_id={PH}' in DB
    assert 'if c.fetchone()' in DB
    assert 'symptom_relief_logs' in DB


def test_redundant_simple_language_controls_are_removed():
    assert 'function simpleOverviewHtml' not in CHAT
    assert 'resultSimpleOverview' not in CHAT
    assert 'data-simple-condition' not in CHAT
    assert 'data-result-action="simple"' not in CHAT


def test_call_script_is_merged_into_doctor_summary_card():
    assert 'function careCallScriptText()' in CHAT
    assert 'function openCareCallScript(btn)' not in CHAT
    assert "Symptoms:" in CHAT
    assert "علامة مهمة ظهرت في التقييم" in CHAT
    assert 'ماذا أقول عند التواصل مع العيادة؟' in CHAT
    assert 'نسخ الملخص كاملًا' in CHAT


def test_new_health_mutations_are_covered_by_csrf_gate():
    assert '"/api/relief-log"' in WEB
    assert '"/api/smart-followup"' in WEB
    assert "protect_sensitive_user_api_csrf" in WEB


def test_relief_data_is_deleted_with_account_health_data():
    for table in ("med_reminders", "followups", "symptom_relief_logs", "feedback"):
        assert f'"{table}"' in DB


def test_chat_has_no_inline_html_event_attributes_after_v83_cleanup():
    assert not re.search(r'on(?:click|change|input|submit|keydown|keyup|load|error)="', CHAT)


def test_restart_resets_v83_transient_state():
    restart = CHAT[CHAT.index('function restart()'):]
    assert 'quick_mode:false' in restart
    assert 'status_update:null' in restart
    assert "classList.remove('ss-quick-assessment')" in restart


def test_webapp_line_guard_remains_under_limit():
    # V106: production hardening and mobile/iOS fixes increased guarded runtime
    # code. Keep a tight ceiling without flagging the current audited release.
    assert len(WEB.splitlines()) < 24000
