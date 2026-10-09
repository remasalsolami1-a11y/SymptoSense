import source_bundle
from pathlib import Path

WEBAPP = Path(__file__).resolve().parent / 'webapp.py'
TEXT = source_bundle.webapp_text()


def test_med_ghost_buttons_are_visible_on_white_cards():
    assert '.med-shell .btn.ghost{background:#f7fbfe;color:var(--v2-blue-dark)' in TEXT
    assert '.med-time-add{min-height:44px;white-space:nowrap;background:#edf7fd!important' in TEXT


def test_save_automatically_uses_selected_time():
    assert 'if(!times.length){' in TEXT
    assert "const autoTime=time24FromParts(document.getElementById('remHour').value,document.getElementById('remMinute').value,document.getElementById('remPeriod').value);" in TEXT
    assert 'reminderTimes=[autoTime];syncReminderTimes();times=reminderTimes.slice()' in TEXT


def test_save_uses_visible_timezone_field():
    assert "const tzEl=document.getElementById('planTimezone');" in TEXT
    assert "timezone:(tzEl&&tzEl.value)||timezone" in TEXT


def test_save_has_actionable_error_messages():
    assert "code==='days_of_week_required'" in TEXT
    assert "code==='invalid_plan_date_range'" in TEXT
    assert "code==='medication_name_and_time_required'" in TEXT
    assert "r.status===401" in TEXT


def test_save_button_has_stable_selector():
    assert 'data-med-save="1"' in TEXT
