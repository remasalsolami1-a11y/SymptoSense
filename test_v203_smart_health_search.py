import source_bundle
import versioning
from pathlib import Path
import ast
import time

import health_search
import search_engine_v2

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.python_text()
SW = (ROOT / 'service-worker.js').read_text(encoding='utf-8')


def test_sources_new_badge_removed_completely():
    assert '__STAT_SOURCES_NEW__' not in WEB
    assert '+5 مصادر جديدة' not in WEB
    assert '+5 new sources' not in WEB


def test_arabic_typo_correction_is_conservative_and_useful():
    result = search_engine_v2.search('غثين الحر', 'ar', 7)
    assert result['did_you_mean']['label'] == 'غثيان'
    assert result['recognized_symptoms'][0]['slug'] == 'nausea'
    lab = search_engine_v2.search('هيموجلبين', 'ar', 7)
    assert lab['did_you_mean']['kind'] == 'test'
    assert 'هيموجلوبين' in lab['did_you_mean']['label']


def test_english_common_words_are_never_auto_rewritten_to_medical_terms():
    result = search_engine_v2.search('why do i feel dizzy in heat', 'en', 7)
    assert result['normalized'].endswith('in heat')
    assert 'heart' not in result['normalized']
    assert result['did_you_mean'] is None
    assert result['recognized_symptoms'][0]['slug'] == 'dizziness'


def test_negated_symptom_is_not_treated_as_active_topic():
    result = search_engine_v2.search('ما عندي حرارة بس غثيان', 'ar', 7)
    slugs = [x['slug'] for x in result['recognized_symptoms']]
    assert 'nausea' in slugs
    assert 'fever' not in slugs
    topic = health_search.search_health('ما عندي حرارة بس غثيان', 'ar')
    assert topic and topic['title'] == 'الغثيان'


def test_full_question_intent_and_context_are_preserved():
    result = search_engine_v2.search('ليش يجيني غثين وقت الحر', 'ar', 7)
    assert result['query_intent'] == 'causes'
    assert 'heat' in result['contexts']
    assert result['recognized_symptoms'][0]['slug'] == 'nausea'


def test_short_shorthand_context_queries_use_relation_pipeline():
    tree = ast.parse(WEB)
    names = {'_normalize_health_query_text', '_health_search_context_relation_result'}
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    ns = {'health_search': health_search, 'logging': __import__('logging')}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'v203-context', 'exec'), ns)
    assert ns['_health_search_context_relation_result']('صداع الصيام', 'ar')['key'] == 'fasting_context_relation'
    assert ns['_health_search_context_relation_result']('دوخة الرياضة', 'ar')['key'] == 'exercise_context_relation'
    assert ns['_health_search_context_relation_result']('صداع الحر', 'ar')['key'] == 'heat_context_relation'


def test_typeahead_is_focused_and_supports_medicines_tests_and_typos():
    dizziness = search_engine_v2.suggestions('دوخة', 'ar', 10)
    labels = [x['label'] for x in dizziness]
    assert labels[0] == 'دوخة'
    assert 'الإجهاد الحراري' not in labels
    typo = search_engine_v2.suggestions('غثين الحر', 'ar', 10)
    assert typo and typo[0]['label'] == 'غثيان'
    med = search_engine_v2.suggestions('بنادول', 'ar', 10)
    assert med and med[0]['kind'] == 'medication'
    test = search_engine_v2.suggestions('هيموجلبين', 'ar', 10)
    assert test and test[0]['kind'] == 'test'


def test_candidate_cache_keeps_repeat_typeahead_fast_enough():
    # Warm the local index, then repeated typeahead should avoid DB rebuilds.
    search_engine_v2.suggestions('دوخة', 'ar', 5)
    start = time.perf_counter()
    for _ in range(5):
        search_engine_v2.suggestions('غثيان', 'ar', 5)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.5


def test_v203_ui_exposes_typo_recovery_without_replacing_query_silently():
    assert 'did_you_mean_v4' in WEB
    assert 'صححت كلمة محتملة في بحثك' in WEB
    assert 'Possible typo detected' in WEB
    assert 'search_intent_v4' in WEB
    assert 'search_contexts_v4' in WEB
    assert 'v5-comprehensive-library-search' in WEB


def test_v203_service_worker_cache_bumped():
    assert versioning.SW_CACHE in SW
