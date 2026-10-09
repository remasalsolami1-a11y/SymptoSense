import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEXT = source_bundle.webapp_text()


def meds_block():
    return source_bundle.between('@app.route("/api/meds/plan"', 'def api_admin_medication_email_status')


def test_medication_account_helper_uses_signed_in_numeric_id():
    assert 'def _medication_user_id()' in TEXT
    helper = source_bundle.between('def _medication_user_id()', 'def _consent_subject_key()')
    assert '_ss_user_id()' in helper
    assert 'return int(account_id)' in helper
    assert 'account-%s' not in helper


def test_all_medication_email_and_telegram_routes_use_numeric_helper():
    block = meds_block()
    assert '_medication_user_id()' in block
    bad = [
        'medication_email.save_plan(_data_user_id()',
        'medication_email.list_plans(_data_user_id()',
        'medication_email.plans_today(_data_user_id()',
        'medication_email.schedule_snooze(_data_user_id()',
        'medication_email.weekly_summary(_data_user_id()',
        'medication_email.reminder_calendar(_data_user_id()',
        'medication_email.get_settings(_data_user_id()',
        'medication_email.save_settings(_data_user_id()',
        'medication_telegram.status(_data_user_id()',
        'medication_telegram.create_connect_link(_data_user_id()',
        'medication_telegram.disconnect(_data_user_id()',
    ]
    for needle in bad:
        assert needle not in block, needle
