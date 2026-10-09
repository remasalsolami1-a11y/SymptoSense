"""Exercise new sourced patterns through extraction, ranking, and follow-ups."""
import pytest

import db
import medical_knowledge as mk
from medical_knowledge_extra import EXTRA_DISEASES, EXTRA_SYMPTOMS
import webapp


@pytest.fixture(autouse=True)
def isolated_knowledge(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_PATH', str(tmp_path / 'knowledge.db'))
    monkeypatch.setattr(db, '_DB_READY_KEY', None)
    monkeypatch.setattr(mk, '_READY_KEY', None)
    mk.init_schema()


@pytest.mark.parametrize('symptom', EXTRA_SYMPTOMS, ids=lambda s: s[0])
@pytest.mark.parametrize('lang', ['ar', 'en'])
def test_new_colloquial_symptoms_are_extracted_by_api(symptom, lang):
    phrase = symptom[4 if lang == 'ar' else 5][0]
    client = webapp.app.test_client()
    client.post('/api/consent/preferences', json={'service_usage': True})
    response = client.post('/api/symptoms/extract', json={'text': phrase, 'lang': lang})
    assert response.status_code == 200
    assert symptom[0] in {s['slug'] for s in response.get_json()['found']}


# Emergency/red-flag-pattern diseases intentionally never appear in
# knowledge_bundle()'s ranked "matches" list: knowledge_bundle() suppresses
# differential matching entirely once risk evaluation reaches "urgent"
# (see medical_knowledge.knowledge_bundle), replacing it with an explicit,
# translated safety explanation instead of a probabilistic disease name.
# That is deliberate -- naming a specific condition during a likely
# emergency could read as reassurance or a diagnosis. These five patterns
# are true emergencies by design, so they are verified separately below
# rather than against the "ranks #1 in matches" contract meant for the
# other, non-emergency extra diseases.
_URGENT_SUPPRESSED_SLUGS = {
    'stroke-warning-pattern', 'anaphylaxis-warning-pattern',
    'meningitis-warning-pattern', 'seizure-episode-pattern',
    'syncope-fainting-pattern',
}
_RANKED_EXTRA_DISEASES = [d for d in EXTRA_DISEASES if d['slug'] not in _URGENT_SUPPRESSED_SLUGS]
_URGENT_EXTRA_DISEASES = [d for d in EXTRA_DISEASES if d['slug'] in _URGENT_SUPPRESSED_SLUGS]


@pytest.mark.parametrize('disease', _RANKED_EXTRA_DISEASES, ids=lambda d: d['slug'])
@pytest.mark.parametrize('lang', ['ar', 'en'])
def test_new_patterns_rank_with_official_sources(disease, lang):
    bundle = mk.knowledge_bundle(list(disease['symptoms']), age=35, lang=lang)
    assert bundle['matches'][0]['slug'] == disease['slug']
    match = bundle['matches'][0]
    assert match['description'] == disease['description_' + lang]
    assert match['recommended_next_step'] == disease['next_' + lang]
    assert any(s['reference_url'] == disease['sources'][0][3] for s in match['sources'])


@pytest.mark.parametrize('disease', _URGENT_EXTRA_DISEASES, ids=lambda d: d['slug'])
@pytest.mark.parametrize('lang', ['ar', 'en'])
def test_urgent_patterns_suppress_ranked_matches_with_safety_explanation(disease, lang):
    """The five emergency-pattern additions (stroke, anaphylaxis, meningitis,
    seizure, syncope) must trigger risk level 'urgent' and, per
    knowledge_bundle()'s intentional design, must NOT surface a ranked
    disease match -- they get a safety explanation instead of a named
    condition, on purpose."""
    bundle = mk.knowledge_bundle(list(disease['symptoms']), age=35, lang=lang)
    assert bundle['risk']['level'] == 'urgent'
    assert bundle['matches'] == []
    assert bundle['risk'].get('reasons')


def test_followup_accepts_negative_answer_and_does_not_repeat():
    first = mk.differential_question(['heel-sole-pain'])
    assert first['symptom_slug'] == 'first-step-heel-pain'
    second = mk.differential_question(['heel-sole-pain'], asked=[first['symptom_slug']], negatives=[first['symptom_slug']])
    assert second['done']
    positive = mk.knowledge_bundle(['heel-sole-pain'])
    negative = mk.knowledge_bundle(['heel-sole-pain'], negatives=['first-step-heel-pain'])
    assert any(m['slug'] == 'plantar-fasciitis' for m in positive['matches'])
    assert not any(m['slug'] == 'plantar-fasciitis' for m in negative['matches'])


def test_emergency_overrides_new_patterns():
    result = mk.knowledge_bundle(['jaw-pain', 'chest-pain', 'shortness-of-breath'], severity=5, age=50)
    assert result['risk']['level'] == 'urgent'
    assert result['matches'] == []
    assert result['sources']


def test_reseeding_preserves_admin_edits_and_is_idempotent():
    conn = db._conn()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE mk_diseases SET description_en='Reviewed custom wording' WHERE slug='plantar-fasciitis'")
        cursor.execute('SELECT COUNT(*) FROM mk_disease_symptoms')
        count = cursor.fetchone()[0]
        mk._seed(cursor)
        mk._seed(cursor)
        cursor.execute("SELECT description_en FROM mk_diseases WHERE slug='plantar-fasciitis'")
        assert cursor.fetchone()[0] == 'Reviewed custom wording'
        cursor.execute('SELECT COUNT(*) FROM mk_disease_symptoms')
        assert cursor.fetchone()[0] == count
    finally:
        conn.close()
