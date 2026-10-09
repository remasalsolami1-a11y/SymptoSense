"""End-to-end coverage of the shared local search and assistant additions."""
from urllib.parse import urlparse
from unittest import mock

from trusted_sources_wiring import ALLOWED_HOSTS as ALLOWED_SOURCE_HOSTS
import pytest

import health_search
from health_search_extra import EXTRA_SEARCH_KB
import webapp


@pytest.mark.parametrize('key', sorted(EXTRA_SEARCH_KB))
@pytest.mark.parametrize('lang', ['ar', 'en'])
def test_new_topics_have_bilingual_content_sources_and_work_in_both_apis(key, lang, monkeypatch):
    monkeypatch.setenv('ASSISTANT_RATE_LIMIT_MAX', '1000')
    monkeypatch.delenv('GROQ_API_KEY', raising=False)
    entry = EXTRA_SEARCH_KB[key]
    query = entry[lang]['title']
    client = webapp.app.test_client()
    client.environ_base['REMOTE_ADDR'] = '192.0.2.' + str(1 + sorted(EXTRA_SEARCH_KB).index(key) + (24 if lang == 'en' else 0))
    client.set_cookie('lang', lang, domain='localhost')
    assert client.post('/api/consent/preferences', json={'service_usage': True, 'analytics_research': False}).status_code == 200
    # A covered question must not fall through to an unrelated contextual handler
    # or an external model, even when the provider is unavailable.
    with mock.patch.object(webapp, '_assistant_contextual_health_answer', side_effect=AssertionError('unexpected fallback')):
        search = client.get('/api/search', query_string={'q': query, 'lang': lang})
        assistant = client.post('/api/assistant', json={'lang': lang, 'messages': [{'role': 'user', 'content': query}]})
    assert search.status_code == assistant.status_code == 200
    result = search.get_json()['result']
    response = assistant.get_json()
    assert result['key'] == key
    assert result['curated_answer'] is True
    assert response['answer'] == result['direct_answer']
    assert entry[lang]['worry'] in response['answer']
    assert entry[lang]['follow_up'] in response['answer']
    assert response['medical_sources'] == result['sources'] == entry['sources']
    for source in result['sources']:
        assert urlparse(source['url']).hostname in ALLOWED_SOURCE_HOSTS
        assert source['last_verified'] in {'2026-09-17', '2026-10-07'}


@pytest.mark.parametrize('query,key,lang', [
    ('ليش شعري يتساقط؟', 'hair_loss', 'ar'),
    ('وش اسوي عندي امساك', 'constipation', 'ar'),
    ('ليش بطني ينتفخ بعد الاكل', 'bloating', 'ar'),
    ('ليش قلبي يدق بسرعة بعد القهوة', 'palpitations', 'ar'),
    ('كيف اخفف مغص الدورة', 'period_pain', 'ar'),
    ('ما هو TSH؟', 'tsh', 'ar'),
    ('What is ferritin?', 'ferritin', 'en'),
    ('why does my heart race after coffee?', 'palpitations', 'en'),
    ('what can I do if I cannot sleep', 'insomnia', 'en'),
    ('when to see a doctor for toothache', 'toothache', 'en'),
])
def test_real_questions_retain_correct_topic_and_guidance(query, key, lang):
    result = health_search.search_health(query, lang)
    assert result['key'] == key
    assert result['curated_answer']
    assert result['original_query'] == query
    assert result['sources']
    assert EXTRA_SEARCH_KB[key][lang]['worry'] in result['direct_answer']


@pytest.mark.parametrize('query', [
    'ليس عندي إمساك', 'no hair loss', 'hair loss after a new medicine',
    'خفقان مع مونجارو', 'constipation in a newborn', 'bloating and chest pain',
    'TSH 99', 'creatinine kinase', 'ferritin supplement dose',
    'I have a tshirt', 'وش سبب ألم الأذن مع دوخة شديدة',
])
def test_unknown_modifiers_values_and_negation_do_not_get_canned_answer(query):
    assert health_search.curated_result(query) is None


def test_sources_remain_topic_specific_and_are_not_mutated():
    first = health_search.search_health('Ferritin', 'en')
    first['sources'][0]['url'] = 'https://invalid.example'
    assert health_search.search_health('Ferritin', 'en')['sources'][0]['url'].startswith('https://medlineplus.gov/')
    result = health_search.search_health('hair loss and bloating', 'en')
    assert result['category'] == 'combined'
    assert {topic['key'] for topic in result['matched_topics']} == {'hair_loss', 'bloating'}
    assert all(topic['sources'] for topic in result['matched_topics'])


def test_question_intents_use_distinct_relevant_details():
    reason = health_search.curated_result('what causes constipation', 'en')['direct_answer']
    care = health_search.curated_result('how can I manage constipation', 'en')['direct_answer']
    doctor = health_search.curated_result('when to see a doctor for constipation', 'en')['direct_answer']
    assert 'Low fibre' in reason
    assert care.startswith(EXTRA_SEARCH_KB['constipation']['en']['self_care'])
    assert doctor.startswith(EXTRA_SEARCH_KB['constipation']['en']['doctor'])


def test_emergency_triage_precedes_new_assistant_content():
    client = webapp.app.test_client()
    client.environ_base['REMOTE_ADDR'] = '192.0.2.100'
    client.post('/api/consent/preferences', json={'service_usage': True, 'analytics_research': False})
    with mock.patch.object(health_search, 'curated_result', side_effect=AssertionError('must triage first')):
        response = client.post('/api/assistant', json={
            'lang': 'en', 'messages': [{'role': 'user', 'content': 'severe chest pain and difficulty breathing with palpitations'}]
        }).get_json()
    assert response['emergency_flags']
    assert 'emergency' in response['answer'].lower()
