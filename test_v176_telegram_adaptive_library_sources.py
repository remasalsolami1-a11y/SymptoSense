import source_bundle
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import safety_engine

def read(name):
    return (ROOT/name).read_text(encoding='utf-8')

def test_red_flag_bypass_matrix_includes_new_urgent_patterns():
    report=safety_engine.validation_report()
    assert report['all_passed']
    ids={x['id'] for x in report['cases']}
    assert {'ar_active_seizure','ar_self_harm','en_active_seizure','en_self_harm'} <= ids

def test_adaptive_flow_is_three_to_five_and_has_human_fallback():
    chat=source_bundle.chat_view_text()
    mk=read('medical_knowledge.py')
    web=source_bundle.webapp_text()
    assert 'const SMART_FOLLOWUP_MAX = 5;' in chat
    assert 'if(differentialCount >= 3)' in chat
    assert 'استشارة بشرية · 937' in chat
    assert '/api/analyze/safety-check' in web
    assert 'max_questions = 5' in mk
    assert 'if len(asked) >= 3 and top_count >= 3' in mk

def test_email_is_baseline_and_telegram_is_optional_layer():
    web=source_bundle.webapp_text(); email=read('medication_email.py'); tg=read('medication_telegram.py'); env=read('.env.example')
    assert 'البريد الإلكتروني — الافتراضي' in web
    assert 'Telegram يظهر فقط إذا اخترته من نموذج التذكير' in web
    assert 'medication_telegram.send_due' in email
    assert 'TELEGRAM_BOT_TOKEN=' in env and 'TELEGRAM_WEBHOOK_SECRET=' in env
    assert 'create_connect_link' in tg and 'handle_start' in tg

def test_health_library_presentation_features_present():
    lib=read('health_library.py')
    for token in ['hlSearch','hl-sidebar','الأكثر بحثًا هذا الأسبوع','_pain_bucket','hl-chip-disease','hl-chip-symptom','آخر مراجعة']:
        assert token in lib
    assert 'health_library_clicks' in lib
    assert 'source_quality_audit' in lib

def test_official_source_pipeline_is_review_only():
    pipe=read('medical_source_pipeline.py'); mk=read('medical_knowledge.py')
    assert 'medical_source_review_queue' in pipe
    assert 'auto_publish' in pipe and 'False' in pipe
    assert 'who_icd11_search' in pipe and 'medlineplus_search' in pipe and 'nhs_content' in pipe
    assert 'two_verified_sources_required' in mk
    assert 'local_saudi_source_required' in mk
    assert 'independent_global_source_required' in mk
