import source_bundle
import json, sys, types
from pathlib import Path
ROOT=Path(__file__).resolve().parent
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
try:
    import groq  # noqa
except Exception:
    mod=types.ModuleType('groq')
    class Groq: pass
    mod.Groq=Groq; sys.modules['groq']=mod

import fhir_export
import search_engine_v2
import symptom_engine_v2


def test_symptom_engine_v2_state_machine_reaches_result_monotonically():
    state={}
    sequence=[28,'female',['صداع','غثيان'],'يومين',3,'',{'notes':'بدون إصابة'}]
    progress=[]
    for answer in sequence:
        out=symptom_engine_v2.apply_answer(state,answer,'ar'); state=out['state']; progress.append(out['progress'])
    assert progress == sorted(progress)
    assert state['complete'] is True and state['step']=='result'
    assert progress[-1] == 100


def test_search_engine_v2_normalizes_dialect_and_returns_contract():
    assert search_engine_v2.normalize('عندي دوخه و لوعه','ar')
    result=search_engine_v2.search('دوخه','ar',5)
    assert set(result) >= {'query','normalized','results','answer','coverage'}
    assert isinstance(result['results'],list)


def test_fhir_export_is_collection_and_not_diagnostic_condition():
    bundle=fhir_export.build_bundle(account_id=7,user={'name':'Test'},health_profile={'gender':'female'},analyses=[{'id':1,'symptoms':['headache'],'created_at':'2026-09-18T00:00:00+00:00'}],blood_tests=[],medications=[])
    assert bundle['resourceType']=='Bundle' and bundle['type']=='collection'
    types={e['resource']['resourceType'] for e in bundle['entry']}
    assert {'Patient','Observation','Composition'} <= types
    assert 'Condition' not in types


def test_v47_static_capabilities_present():
    web=source_bundle.webapp_text()
    api=(ROOT/'api_v1.py').read_text(encoding='utf-8')
    req=(ROOT/'requirements.txt').read_text(encoding='utf-8')
    assert '/static/css/design-system.css' in web
    assert 'request_tracing.begin_request()' in web
    assert '/api/v1/fhir/export' in api
    assert '/symptoms/session/answer' in api
    assert '/passkeys/register/options' in api
    assert 'source-monitor' in api
    assert 'webauthn' in req and 'redis' in req and 'rq' in req


def test_accessibility_automation_uses_axe_core_and_wcag_aa():
    pkg=json.loads((ROOT/'package.json').read_text(encoding='utf-8'))
    test=(ROOT/'accessibility.spec.js').read_text(encoding='utf-8')
    assert '@axe-core/playwright' in pkg['devDependencies']
    assert 'wcag22aa' in test and "['critical','serious']" in test


def test_medical_versioning_supports_non_destructive_rollback_contract():
    src=(ROOT/'medical_knowledge.py').read_text(encoding='utf-8')
    assert 'def rollback_version(' in src
    assert 'restored_from_version' in src
    assert 'rolled_back' in src


def test_v47_mutations_are_csrf_protected_and_rate_limited():
    web=source_bundle.webapp_text()
    api=(ROOT/'api_v1.py').read_text(encoding='utf-8')
    assert '"/api/v1/passkeys", "/api/v1/admin"' in web
    assert '_rate("api_v1_symptom_result", 20, 300)' in api
    assert '_rate("passkey_auth_verify", 20, 600)' in api


def test_background_jobs_track_rq_lifecycle_in_application_table():
    src=(ROOT/'background_jobs.py').read_text(encoding='utf-8')
    assert 'def _rq_runner(' in src
    assert '_run_tracked(job_id, job_name, payload, "rq")' in src
    assert 'q.enqueue(_rq_runner' in src


def test_passkeys_parse_browser_json_with_library_helpers():
    src=(ROOT/'passkeys.py').read_text(encoding='utf-8')
    assert 'parse_registration_credential_json' in src
    assert 'parse_authentication_credential_json' in src


def test_search_v2_invalid_limit_falls_back_instead_of_500():
    result=search_engine_v2.search('دوخة','ar','not-a-number')
    assert isinstance(result['results'],list)
