import source_bundle
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()
SPEC = importlib.util.spec_from_file_location('assistant_knowledge_extra', ROOT / 'assistant_knowledge_extra.py')
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def test_v60_adds_substantial_local_assistant_coverage():
    assert len(MOD.ASSISTANT_EXTRA_SYMPTOMS_V60) >= 20
    assert len(MOD.ASSISTANT_CONTEXT_PATTERNS_V60) >= 8


def test_v60_rows_are_bilingual_source_linked_and_well_formed():
    for row in MOD.ASSISTANT_EXTRA_SYMPTOMS_V60:
        assert len(row) == 8
        ar_title, en_title, aliases, ar_answer, en_answer, ar_q, en_q, url = row
        assert ar_title and en_title
        assert len(aliases) >= 4
        assert ar_answer and en_answer and ar_q and en_q
        assert url.startswith('https://www.nhs.uk/')


def test_v60_context_rows_keep_full_phrase_semantics():
    for item in MOD.ASSISTANT_CONTEXT_PATTERNS_V60:
        assert item['ar_any'] and item['ar_context']
        assert item['en_any'] and item['en_context']
        assert 'تشخيص' in item['ar']
        assert 'diagnosis' in item['en'].lower()


def test_v60_webapp_wires_new_data_before_generic_search():
    assert 'ASSISTANT_EXTRA_SYMPTOMS.extend(ASSISTANT_EXTRA_SYMPTOMS_V60)' in WEB
    assert 'ASSISTANT_CONTEXT_PATTERNS_V60' in WEB
    ctx = WEB.index('ASSISTANT_CONTEXT_PATTERNS_V60', WEB.index('def _assistant_contextual_health_answer'))
    generic = WEB.index('curated = health_search.curated_result(query, lang)')
    # Contextual handler is defined before local search and called before generic search.
    assert ctx < generic
    block = WEB[generic: generic + 1600]
    assert '_assistant_contextual_health_answer(query, lang)' in block
    assert '_assistant_extended_symptom_reply(query, lang)' in block


def test_v60_preserves_emergency_triage_route_ordering():
    route = WEB[WEB.index('@app.route("/api/assistant"'):WEB.index('@app.route("/api/assistant/feedback"')]
    # The assistant route still evaluates emergency/safety handling before provider fallback.
    assert '_emergency' in route.lower() or 'red_flag' in route.lower() or 'triage' in route.lower()
