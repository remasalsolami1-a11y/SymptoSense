import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text() + "\n" + source_bundle.chat_view_text()
CORE = (ROOT / 'analysis_core.py').read_text(encoding='utf-8')
MK = (ROOT / 'medical_knowledge.py').read_text(encoding='utf-8')
EMAIL = (ROOT / 'medication_email.py').read_text(encoding='utf-8')
SW = (ROOT / 'service-worker.js').read_text(encoding='utf-8')


def test_mobile_age_step_is_visually_lower_and_result_scroll_is_reset():
    assert 'v27 mobile symptom polish' in WEB
    assert 'padding-top:clamp(116px,17svh,152px)' in WEB
    assert 'resetResultScroll' in WEB
    assert 'window.scrollTo(0,0)' in WEB


def test_source_grounded_single_symptom_context_is_allowed_but_labeled_low():
    assert 'strong_single_relation' in CORE
    assert '>= 0.65' in CORE
    assert '_has_trusted_medical_source(match)' in CORE


def test_expanded_common_condition_set_and_source_identity():
    for slug in (
        'tension-type-headache', 'allergic-rhinitis', 'irritable-bowel-syndrome',
        'overactive-thyroid', 'covid-19', 'pneumonia', 'vertigo-pattern'
    ):
        assert f'"{slug}"' in MK
    assert 'source_key = "cdc" if "cdc.gov"' in MK


def test_medication_email_action_route_and_email_engine_present():
    assert '/meds/email-action/<token>' in WEB
    assert 'def send_due_emails(' in EMAIL
    assert 'medication_reminders' in EMAIL
    assert 'med_email_deliveries' in EMAIL


def test_browser_push_components_are_removed_for_medication_reminders():
    assert '/api/push/' not in WEB
    assert 'Notification.requestPermission' not in WEB
    assert "self.addEventListener('push'" not in SW
    assert "self.addEventListener('notificationclick'" not in SW
