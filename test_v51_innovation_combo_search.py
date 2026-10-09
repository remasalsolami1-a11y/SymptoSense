from __future__ import annotations
import source_bundle
import sys, types
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
try:
    import groq  # noqa
except Exception:
    mod = types.ModuleType('groq')
    class Groq: pass
    mod.Groq = Groq
    sys.modules['groq'] = mod

import medical_knowledge
import search_engine_v2
import symptom_combo_intelligence
import v51_innovation


def test_combo_catalog_is_substantial_and_bounded():
    assert symptom_combo_intelligence.count() >= 30
    for p in symptom_combo_intelligence.PATTERNS:
        assert len(p.symptoms) >= 2
        assert 0 < p.bonus <= 0.15
        assert p.targets


def test_combo_detection_for_common_patterns():
    hits = symptom_combo_intelligence.detect_patterns([
        {'slug': 'increased-thirst'}, {'slug': 'frequent-urination'}, {'slug': 'fatigue'}
    ], 'ar')
    assert any(x['slug'] == 'diabetes-pattern' for x in hits)
    hits = symptom_combo_intelligence.detect_patterns([
        {'slug': 'knee-pain'}, {'slug': 'joint-clicking'}
    ], 'ar')
    assert any(x['slug'] == 'oa-knee-pattern' for x in hits)


def test_combo_bonus_never_manufactures_match():
    # A target bonus without independently matched symptoms must not surface a disease.
    rows = medical_knowledge.match_diseases(
        medical_knowledge.normalize_symptoms(['صداع'], 'ar')['canonical'],
        'ar', pattern_bonuses={'type-2-diabetes-pattern': 0.18}
    )
    assert all(x['slug'] != 'type-2-diabetes-pattern' for x in rows)


def test_knowledge_bundle_exposes_combo_and_bonus():
    b = medical_knowledge.knowledge_bundle(['عطش شديد', 'كثرة التبول', 'تعب'], 2, 30, '', 'ar')
    assert any(x['slug'] == 'diabetes-pattern' for x in b['pattern_insights'])
    diabetes = next(x for x in b['matches'] if x['slug'] == 'type-2-diabetes-pattern')
    assert 0 < diabetes['pattern_bonus'] <= 0.18


def test_search_v3_understands_multi_symptom_colloquial_queries():
    cases = [
        ('ركبتي تطقطق وتوجعني', 'ar', {'knee-pain', 'joint-clicking'}),
        ('عطشان كثير وادخل الحمام كثير وتعبان', 'ar', {'increased-thirst', 'frequent-urination', 'fatigue'}),
        ('heart racing and dizzy', 'en', {'palpitations', 'dizziness'}),
    ]
    for q, lang, expected in cases:
        r = search_engine_v2.search(q, lang, 8)
        slugs = {x['slug'] for x in r['recognized_symptoms']}
        assert expected <= slugs, (q, slugs)
        assert r['engine_version'] == 'v4-intent-context-typo-aware'


def test_search_v3_keeps_typeahead_deterministic():
    ar = search_engine_v2.suggestions('قلبي يدق بسرعه', 'ar', 5)
    assert ar and ar[0]['slug'] == 'palpitations'
    assert all(x['kind'] in {'symptom', 'disease'} for x in ar)


def test_innovation_lab_synthetic_benchmarks_pass():
    safety = v51_innovation._safety_twin_cases()
    nlp = v51_innovation._nlp_stress_cases()
    assert safety and all(x['passed'] for x in safety)
    assert nlp and all(x['passed'] for x in nlp)


def test_innovation_lab_metrics_are_real():
    m = v51_innovation._knowledge_metrics()
    assert m['symptoms'] >= 120
    assert m['diseases'] >= 75
    assert m['links'] >= 350
    assert m['aliases_ar'] >= 300
    assert m['combos'] == symptom_combo_intelligence.count()


def test_routes_and_ui_are_wired():
    web = source_bundle.webapp_text()
    wow = (ROOT / 'v50_wow.py').read_text(encoding='utf-8')
    chat = source_bundle.chat_view_text()
    assert '@app.route("/admin/innovation-lab")' in web
    assert 'v51_innovation.render_innovation_lab' in web
    assert '/admin/innovation-lab' in wow
    assert 'pattern_insights' in chat
    assert 'Symptom pattern intelligence' in chat or 'ذكاء نمط الأعراض' in chat
    assert 'v5-comprehensive-library-search' in web
