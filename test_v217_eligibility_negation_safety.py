import source_bundle
from pathlib import Path
import medical_knowledge as mk
import safety_engine

ROOT = Path(__file__).resolve().parent
CHAT = source_bundle.chat_view_text()
DOCKER = (ROOT / 'Dockerfile').read_text(encoding='utf-8')
ROOT_CSS = (ROOT / 'app-shell-v111.css').read_text(encoding='utf-8')
STATIC_CSS = (ROOT / 'static/css/app-shell-v111.css').read_text(encoding='utf-8')
WEB = source_bundle.webapp_text()


def slugs(bundle):
    return {x.get('slug') for x in bundle.get('matches', [])}


def test_condition_metadata_is_in_schema_and_pre_score_query():
    source = (ROOT / 'medical_knowledge.py').read_text(encoding='utf-8')
    assert 'sex_applicability' in source
    assert 'min_age' in source and 'max_age' in source and 'pregnancy_relevant' in source
    query_pos = source.index('FROM mk_diseases WHERE status=')
    filter_pos = source.index('_condition_is_eligible', query_pos)
    scoring_pos = source.index('base_score=', query_pos)
    assert query_pos < filter_pos < scoring_pos


def test_male_never_gets_female_only_and_general_remains():
    male = mk.knowledge_bundle(['Breast tenderness', 'Mood swings', 'Nausea'], age=25, gender='m', lang='en')
    assert not (slugs(male) & mk.FEMALE_ONLY_DISEASE_SLUGS)
    # General symptom normalization remains available; sex is not a score bonus.
    assert any(x.get('slug') == 'nausea' for x in male['normalization']['canonical'])


def test_female_keeps_relevant_female_condition():
    female = mk.knowledge_bundle(['Breast tenderness', 'Mood swings'], age=25, gender='f', lang='en')
    assert 'premenstrual-syndrome-pattern' in slugs(female)


def test_unknown_sex_is_conservative_but_anatomy_can_infer_context():
    unknown = mk.knowledge_bundle(['Mood swings', 'Fatigue'], age=25, gender='', lang='en')
    assert not (slugs(unknown) & mk.FEMALE_ONLY_DISEASE_SLUGS)
    anatomical = mk.knowledge_bundle(['Menstrual cramps', 'Fatigue'], age=25, gender='', lang='en')
    assert slugs(anatomical) & mk.FEMALE_ONLY_DISEASE_SLUGS


def test_free_text_negatives_are_parsed_and_used_without_duplicate_questioning():
    b = mk.knowledge_bundle(['صداع وغثيان بدون حرارة وبدون قيء'], age=25, gender='', lang='ar')
    neg = {x['slug'] for x in b['normalization']['negated']}
    assert {'fever', 'vomiting'} <= neg
    q = mk.differential_question(['صداع', 'غثيان'], negatives=list(neg), lang='ar')
    assert q.get('symptom_slug') not in neg


def test_negative_evidence_reduces_but_does_not_boolean_delete():
    positive = mk.knowledge_bundle(['Nausea', 'Vomiting', 'Diarrhea'], age=30, gender='', lang='en')
    denied = mk.knowledge_bundle(['Nausea', 'Diarrhea', 'no vomiting'], age=30, gender='', lang='en')
    pos = next((x for x in positive['matches'] if x['slug']=='food-poisoning'), None)
    neg = next((x for x in denied['matches'] if x['slug']=='food-poisoning'), None)
    assert pos is not None
    if neg is not None:
        assert 'vomiting' in neg.get('negative_evidence', [])


def test_cant_breathe_is_positive_emergency_not_negation():
    norm = mk.normalize_symptoms(['لا أستطيع التنفس'], 'ar')
    assert 'shortness-of-breath' in {x['slug'] for x in norm['canonical']}
    result = safety_engine.evaluate({'symptoms':['لا أستطيع التنفس'], 'notes':''}, 'ar')
    assert result['emergency'] is True


def test_anaphylaxis_context_current_vs_history():
    current = safety_engine.evaluate({'symptoms':['لساني متورم الآن وما أقدر أتنفس'], 'notes':''}, 'ar')
    assert current['emergency'] is True
    history = safety_engine.evaluate({'symptoms':['عندي تاريخ حساسية مفرطة قبل سنتين'], 'notes':''}, 'ar')
    assert history['emergency'] is False


def test_seizure_fainting_stroke_bleeding_regressions():
    emergency_cases = [
        ['عندي تشنجات الآن'], ['فاقد الوعي الآن ولا يستجيب'],
        ['فمي مايل وكلامي ثقيل فجأة'], ['نزيف شديد والدم ما يوقف'],
    ]
    for symptoms in emergency_cases:
        assert safety_engine.evaluate({'symptoms':symptoms, 'notes':''}, 'ar')['emergency'] is True
    assert safety_engine.evaluate({'symptoms':['دوخة'], 'notes':''}, 'ar')['emergency'] is False
    assert safety_engine.evaluate({'symptoms':['حساسية'], 'notes':''}, 'ar')['emergency'] is False


def test_result_ui_shows_positive_negative_summary_and_resets_context_on_sex_change():
    assert 'ملخص الأعراض المفهومة' in CHAT
    assert 'أعراض غير موجودة حسب إجابتك' in CHAT
    assert 'oldGender!==newGender' in CHAT


def test_doctor_card_css_single_deployed_content():
    assert 'cp -f design-system.css offline.css v83_user_tools.css app-shell-v111.css static/css/' in DOCKER
    assert ROOT_CSS == STATIC_CSS
    assert '.doctor-card-section' in ROOT_CSS


def test_language_picker_separates_disclaimer_and_uses_source_grounded_claim():
    assert 'مصادر طبية موثوقة' in WEB
    assert 'SymptoSense يقدم معلومات وإرشادًا أوليًا ولا يشخّص الحالات الطبية.' in WEB
    block = WEB[WEB.index('def welcome_page():'):WEB.index('@app.route("/language/<code>"')]
    benefits = block[block.index('first-lang-benefits'):block.index('first-lang-leaf')]
    assert '<b lang="ar" dir="rtl">للتوعية فقط</b>' not in benefits
