import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()
# Admin knowledge-base routes were extracted from webapp.py into their own
# module; static "route string is in WEB" checks need both sources now.
WEB += (ROOT / 'admin_knowledge_routes.py').read_text(encoding='utf-8')
WEB += '\n' + source_bundle.chat_view_text()
DASH = (ROOT / 'dashboard.py').read_text(encoding='utf-8')
EMAIL = (ROOT / 'medication_email.py').read_text(encoding='utf-8')
SW = (ROOT / 'service-worker.js').read_text(encoding='utf-8')
VALID = (ROOT / 'research_validation.py').read_text(encoding='utf-8')
KNOW = (ROOT / 'medical_knowledge.py').read_text(encoding='utf-8')
READY = (ROOT / 'production_readiness.py').read_text(encoding='utf-8')


def test_v36_medication_email_delivery_is_observable():
    assert 'CREATE TABLE IF NOT EXISTS med_email_deliveries' in EMAIL
    assert 'def delivery_summary' in EMAIL
    assert 'def send_due_emails' in EMAIL
    assert '/api/admin/medication-email/status' in WEB
    assert 'تذكيرات الأدوية عبر البريد' in DASH
    assert "self.addEventListener('push'" not in SW


def test_v36_research_validation_has_independent_blinded_workflow():
    assert 'def study_protocol()' in VALID
    assert 'primary_endpoint' in VALID
    assert 'blinding_rule' in VALID
    assert 'minimum_verified_cases' in VALID
    assert 'def export_rows(blinded: bool = False)' in VALID
    assert 'balanced_accuracy_pct' in VALID
    assert 'macro_f1_pct' in VALID
    assert 'per_class' in VALID
    assert 'study_ready' in VALID
    assert '/api/admin/research-validation/export' in WEB
    assert 'نموذج مراجعة مستقل' in DASH
    assert 'تصدير النتائج' in DASH


def test_v36_medical_content_review_queue_exists():
    assert 'def periodic_review_status' in KNOW
    assert "review='source_missing'" in KNOW
    assert "review='outdated'" in KNOW
    assert "red_flag_max_age_days" in KNOW
    assert '/api/admin/knowledge/review-status' in WEB
    assert 'مراجعة المحتوى الطبي الدورية' in DASH
    assert 'مصدر موثق مفقود' in DASH


def test_v36_result_priority_order_is_decision_first():
    result = WEB.split('function renderResult(d)', 1)[1].split('function ', 1)[0]
    markers = [
        '// 1) Summary',
        '// 2) What to do now',
        '// 3) Symptom assessment',
        '// 4) Why this assessment',
        '// 5) Danger signs',
        '// 6) Medical sources',
        '// 7) Home care',
    ]
    positions = [result.index(m) for m in markers]
    assert positions == sorted(positions)


def test_v36_mental_followup_and_local_plan_are_available():
    assert 'function asstMhMaybeCheckin()' in WEB
    assert 'function asstMhPlanFromHistory()' in WEB
    assert 'function asstMhFinishCheckin(choice,card)' in WEB
    assert 'أفضل شوي' in WEB and 'نفس الشيء' in WEB and 'أسوأ' in WEB
    assert "localStorage.setItem('ss_mh_plan_v1'" in WEB
    assert "لا تُضاف لبيانات البحث" in WEB
    assert "asstMhUrgentSupport()" in WEB
    assert "'My plan':'خطتي', 'plan'" in WEB


def test_v36_symptom_continue_is_last_on_all_viewports():
    assert 'v36 symptom flow regression guard' in WEB
    block = WEB.split('v36 symptom flow regression guard', 1)[1].split('BASE_CSS =', 1)[0]
    assert 'order:999!important' in block
    symptom_fn = WEB.split('function askSymptoms()', 1)[1].split('function renderRelated()', 1)[0]
    assert symptom_fn.index('showOpts(items);') < symptom_fn.index('renderRelated();') < symptom_fn.index('appendStartBtn();')


def test_v36_version_default_is_updated():
    assert 'release_candidate.APP_VERSION' in READY
