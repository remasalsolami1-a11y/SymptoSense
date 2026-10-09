import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text() + '\n' + source_bundle.chat_view_text()


def test_age_step_is_no_longer_vertically_centered_on_phone():
    marker = 'v30 phone questionnaire layout: full-width age step + Continue below symptoms'
    assert marker in WEB
    block = WEB.split(marker, 1)[1].split('BASE_CSS =', 1)[0]
    assert 'padding:14px 12px 0!important' in block
    assert 'width:100%!important;max-width:none!important;margin:0!important' in block
    assert 'grid-template-columns:1fr!important' in block
    assert 'body.ss-chat-page[data-chat-step="age"] #chatInput button' in block


def test_continue_button_is_appended_after_symptom_choices():
    assert "function appendStartBtn()" in WEB
    assert "optsEl.appendChild(s);" in WEB
    assert "insertBefore(s, optsEl.firstChild)" not in WEB
    symptom_fn = WEB.split('function askSymptoms()', 1)[1].split('function renderRelated()', 1)[0]
    assert symptom_fn.index('showOpts(items);') < symptom_fn.index('renderRelated();') < symptom_fn.index('appendStartBtn();')
    assert "'التالي: مدة الأعراض'" in WEB


def test_phone_css_orders_continue_after_related_symptoms():
    block = WEB.split('v30 phone questionnaire layout: full-width age step + Continue below symptoms', 1)[1].split('BASE_CSS =', 1)[0]
    assert '#relBlock{\n    order:5!important;' in block
    assert '.start-btn{\n    order:10!important;' in block
