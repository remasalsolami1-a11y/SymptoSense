"""Behavioral regressions for the independently reproduced V44 review issues."""
import copy
from unittest import mock
import pytest
@pytest.fixture(scope="module", autouse=True)
def load_app_after_collection():
    # Existing integration modules configure their temporary DB at collection.
    global analysis_core, clinical_text, medical_knowledge, webapp
    import analysis_core
    import clinical_text
    import medical_knowledge
    import webapp


@pytest.mark.parametrize('text', ['severe chest pain', 'ألم شديد في الصدر', "I cannot breathe", 'لا أستطيع التنفس'])
def test_emergency_is_independent_of_display_language(text):
    patient = dict(symptoms=[text], age=30, gender='male', severity=1, duration='1 day', notes='')
    for lang in ('ar', 'en'):
        result = analysis_core.run_analysis(copy.deepcopy(patient), lang)
        assert result['emergency'] is True
        assert result['triage_level'] == 'emergency'
        assert result['risk_level'] == 'urgent'


@pytest.mark.parametrize('text', ["I don't have chest pain", 'I don’t have chest pain',
    'no chest pain or shortness of breath', 'لا يوجد صداع ولا ألم في الصدر',
    'ليس لدي صداع', 'no severe chest pain or severe shortness of breath'])
def test_negation_survives_normalization_and_full_analysis(text):
    normalized = medical_knowledge.normalize_symptoms([text])
    assert not normalized['canonical'], normalized
    result = analysis_core.run_analysis(dict(symptoms=[text], age=30, gender='male', severity=1, duration='1 day'), 'en')
    assert not result['emergency']
    assert result['risk_level'] == 'low'


@pytest.mark.parametrize('text,phrase', [
    ('no fever but severe chest pain', 'severe chest pain'),
    ('no fever. severe chest pain', 'severe chest pain'),
    ('no fever and I have severe chest pain', 'severe chest pain'),
    ('لا يوجد صداع لكن عندي ألم شديد في الصدر', 'ألم شديد في الصدر'),
    ("I don't want to live", "I don't want to live"),
])
def test_negation_does_not_hide_positive_or_crisis_phrases(text, phrase):
    assert clinical_text.contains_unnegated_phrase(text, phrase)


@pytest.mark.parametrize('text,expected', [
    ('عندي صداع من يومين', '📅 1-3 أيام'),
    ('عندي صداع منذ يومين', '📅 1-3 أيام'),
    ('عندي صداع من أمس', '⏰ أقل من 24 ساعة'),
    ('صداع منذ أسبوعين', '🗓️ 1-2 أسبوع'),
    ('صداع أكثر من أسبوعين', '🗓️ أكثر من أسبوعين'),
    ('headache for two weeks', '🗓️ 1-2 weeks'),
    ('headache for more than two weeks', '🗓️ More than 2 weeks'),
])
def test_voice_duration_boundaries(text, expected):
    lang = 'en' if text.isascii() else 'ar'
    assert webapp._voice_parse(text, lang)['duration'] == expected


def test_voice_does_not_invent_breathlessness_from_same_place():
    assert not webapp._voice_parse('عندي ألم في نفس المكان', 'ar')['symptoms']
    assert '🫁 ضيق التنفس' in webapp._voice_parse('عندي ضيق في التنفس', 'ar')['symptoms']


@pytest.mark.parametrize('selected,allowed', [(False, False), (False, True), (True, False), (True, True)])
def test_legacy_profile_requires_both_user_choice_and_privacy(selected, allowed):
    # Call the real route, capturing the patient passed to the analysis engine.
    with webapp.app.test_request_context('/api/analyze', method='POST', json={'symptoms':['headache'], 'use_saved':selected}), \
         mock.patch.object(webapp.db, 'init_db'), \
         mock.patch.object(webapp.privacy_features, 'init_schema'), \
         mock.patch.object(webapp, '_request_allowed', return_value=True), \
         mock.patch.object(webapp, '_consent_state', return_value={'service_usage':True}), \
         mock.patch.object(webapp, '_ss_user_id', return_value=7), \
         mock.patch.object(webapp, '_data_user_id', return_value='account-7'), \
         mock.patch.object(webapp.db, 'load_privacy_settings', return_value={'use_in_analysis':allowed, 'save_chat_history':False}), \
         mock.patch.object(webapp.db, 'load_health_profile', return_value={}), \
         mock.patch.object(webapp.db, 'load_profile', return_value={'age':70,'conditions':'old condition','medications':'old medicine','allergies':'old allergy'}) as legacy, \
         mock.patch.object(analysis_core, 'run_analysis', return_value={'ok':True}) as run:
        response = webapp.api_analyze()
        assert response.status_code == 200
        patient = run.call_args.args[0]
        if selected and allowed:
            assert patient['age'] == 70 and patient['medications'] == 'old medicine'
            legacy.assert_called_once()
        else:
            assert patient['age'] is None and patient['medications'] == ''
            assert patient['conditions'] == '' and patient['allergies'] == ''
            legacy.assert_not_called()


@pytest.mark.parametrize('data', [{'symptoms':42}, {'symptoms':[{}]}, {'symptoms':['headache'],'duration':42},
    {'symptoms':['headache'],'use_saved':'false'}, {'symptoms':['headache'],'negative_symptoms':'no pain'},
    {'symptoms':['headache'],'age':'nan'}, {'symptoms':['headache'],'age':-2}])
def test_invalid_analysis_fields_return_400_before_engine(data):
    with webapp.app.test_request_context('/api/analyze', method='POST', json=data), \
         mock.patch.object(webapp.db, 'init_db'), \
         mock.patch.object(webapp.privacy_features, 'init_schema'), \
         mock.patch.object(webapp, '_request_allowed', return_value=True), \
         mock.patch.object(webapp, '_consent_state', return_value={'service_usage':True}), \
         mock.patch.object(analysis_core, 'run_analysis') as run:
        response, status = webapp.api_analyze()
        assert status == 400
        assert response.get_json()['error_code'] == 'invalid_input'
        run.assert_not_called()


@pytest.mark.parametrize('path', ['/api/analyze','/api/hospitals','/api/assistant'])
@pytest.mark.parametrize('payload', ['[1]', 'null', '"hello"', '{bad'])
def test_non_object_json_is_rejected_by_real_request_hook(path, payload):
    response = webapp.app.test_client().post(path, data=payload, content_type='application/json')
    assert response.status_code == 400
    assert response.get_json()['error_code'] == 'invalid_input'


@pytest.mark.parametrize('text', ['no severe chest pain', "I don't have severe shortness of breath", 'لا يوجد نزيف شديد', 'لا يوجد صداع شديد'])
def test_kb_risk_keywords_respect_negation_in_notes(text):
    for lang in ('ar', 'en'):
        risk = medical_knowledge.evaluate_risk([], raw_symptoms=[], notes=text, severity=3, age=30, lang=lang)
        assert not risk['emergency'], risk


# Since V198 detect_red_flags() only returns *immediate* ambulance-level flags;
# ambiguous aliases (confusion, fainting, stiff neck, ...) go through adaptive
# follow-up and the clinical triage layer instead. This test therefore covers
# the immediate chest/breathing aliases only.
_IMMEDIATE_ALIASES = (
    "severe chest pain", "crushing chest pain", "squeezing chest pain",
    "chest feels tight or heavy", "severe shortness of breath",
    "severe difficulty breathing", "can't breathe", "cannot breathe", "choking",
    "لا أقدر أتنفس", "لا اقدر اتنفس", "لا أستطيع التنفس", "ما اقدر اتنفس",
)


def test_red_flag_labels_are_translatable_for_all_aliases():
    for phrase in _IMMEDIATE_ALIASES:
        for lang in ('ar', 'en'):
            assert analysis_core.detect_red_flags([phrase], lang=lang), (phrase, lang)
