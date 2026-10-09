"""Regression coverage for the five reproduced Signature review defects."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parent


@pytest.mark.parametrize('lang,note', [('en', 'severe chest pain'), ('ar', 'ألم صدر شديد')])
@pytest.mark.parametrize('context', [{'notes': ''}, {'notes': 'no chest pain'}, {'notes': 'x' * 1200}])
def test_safety_answer_survives_later_context(lang, note, context):
    import symptom_engine_v2 as engine
    state = None
    for answer in [25, 'female', 'headache', '1 day', 1, note, context]:
        state = engine.apply_answer(state, answer, lang)['state']
        # Exercise the same serialization/signature boundary as the API.
        state = engine.verify_state_token(engine.sign_state(state, 's' * 40), 's' * 40).to_dict()
    result = engine.analyze(state, lang)['result']
    assert result['emergency'] is True
    assert result['triage_level'] == 'emergency'


def test_old_signed_state_keeps_safety_answer():
    import symptom_engine_v2 as engine
    state = None
    for answer in [25, 'female', 'headache', '1 day', 1, 'severe chest pain']:
        state = engine.apply_answer(state, answer, 'en')['state']
    state.pop('red_flag_notes')
    state = engine.apply_answer(state, {'notes': ''}, 'en')['state']
    assert engine.analyze(state, 'en')['result']['emergency'] is True


def test_no_red_flags_still_allows_monitoring():
    import symptom_engine_v2 as engine
    state = None
    for answer in [25, 'female', 'headache', '1 day', 1, 'no chest pain', {'notes': ''}]:
        state = engine.apply_answer(state, answer, 'en')['state']
    assert engine.analyze(state, 'en')['result']['emergency'] is False


def test_real_page_and_database_integration(tmp_path):
    env = dict(os.environ, DB_PATH=str(tmp_path / 'integration.db'), DATABASE_URL='',
               WEB_SECRET='signature-test-secret-longer-than-32-characters',
               SESSION_COOKIE_SECURE='0', SITE_URL='http://localhost',
               SYMPTOSENSE_DISABLE_BACKUP_SCHEDULER='1',
               FEATURE_FHIR_EXPORT='1', FEATURE_API_V1='1')
    result = subprocess.run([sys.executable, str(Path(__file__).resolve())], cwd=ROOT,
                            env=env, text=True, capture_output=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr


def integration_check():
    sys.path.insert(0, str(ROOT))
    import time
    import db
    import webapp
    import platform_v2
    import medical_knowledge
    import privacy_features
    import advanced_features
    import admin_operational
    import medication_email
    import admin_security
    db.init_db()
    for module in (platform_v2, medical_knowledge, privacy_features, advanced_features,
                   admin_operational, medication_email):
        module.init_schema()
    uid, error = db.create_ss_user('signature-test@example.test', 'Test User', 'TestPassword123!')
    assert not error
    conn = db._conn()
    conn.execute("UPDATE ss_users SET role='admin',email_verified=1 WHERE id=?", (uid,))
    conn.commit(); conn.close()
    client = webapp.app.test_client()
    client.set_cookie('lang', 'en')
    with client.session_transaction() as session:
        session['ss_user_id'] = uid
        session['admin_2fa_verified'] = True
        session['admin_session_epoch'] = admin_security.current_epoch(uid)
        session['admin_last_seen'] = int(time.time())
    # Do not enable TESTING: CSRF hooks must remain active.
    for lang in ('en', 'ar'):
        client.set_cookie('lang', lang)
        page = client.get('/admin/judge-challenge')
        assert page.status_code == 200
        token = re.search(r'name="admin-csrf" content="([^"]+)"', page.get_data(as_text=True)).group(1)
        for case in webapp.judge_challenge.CASES:
            response = client.post('/api/admin/judge-challenge/run',
                json={'case_id': case['id'], 'lang': lang}, headers={'X-CSRF-Token': token})
            assert response.status_code == 200 and response.json['result']['passed']
        assert client.post('/api/admin/judge-challenge/run', json={'case_id':'chest-breath'}).status_code == 403
        manage = client.get('/manage', follow_redirects=True)
        assert manage.status_code == 200
        scripts = re.findall(r'<script\b[^>]*>(.*?)</script>', manage.get_data(as_text=True), re.S)
        if shutil.which('node'):
            for script in scripts:
                # JSON-LD is data, not an executable script.
                if script.lstrip().startswith('{'): continue
                checked = subprocess.run(['node', '--check'], input=script, text=True, capture_output=True)
                assert checked.returncode == 0, checked.stderr
    owner = f'account-{uid}'
    for key, member, symptom in [(owner, 0, 'own symptom'), (owner, 77, 'family symptom'),
                                  (str(uid), 0, 'other channel symptom'), ('account-999', 0, 'other account symptom')]:
        db.save_record(key, 'en', 25, 'female', [symptom], '1 day', 1, 'monitor', member_id=member)
        db.save_blood_test(key, {'Hb': 12.5}, member_id=member)
        db.save_med_plan(key, member, symptom + ' medication', ['08:00'])
    response = client.get('/api/v1/fhir/export')
    assert response.status_code == 200
    resources = [x['resource'] for x in response.json['entry']]
    obs = [x for x in resources if x['resourceType'] == 'Observation']
    assert len(obs) == 2
    assert all(x.get('effectiveDateTime') for x in obs)
    assert next(x for x in obs if 'valueString' in x)['valueString'] == 'own symptom'
    meds = [x for x in resources if x['resourceType'] == 'MedicationStatement']
    assert len(meds) == 1 and meds[0]['medicationCodeableConcept']['text'] == 'own symptom medication'
    text = json.dumps(response.json)
    assert 'family symptom' not in text and 'other channel' not in text and 'other account' not in text
    conn = db._conn(); conn.execute("UPDATE ss_users SET status='disabled' WHERE id=?", (uid,)); conn.commit(); conn.close()
    assert client.get('/api/v1/fhir/export').status_code == 401
    # A disabled account must not manage credentials through an old session.
    import passkeys
    passkeys.init_schema()
    regular, error = db.create_ss_user('passkey-cleanup@example.test', 'Regular', 'TestPassword123!')
    assert not error
    conn = db._conn()
    conn.execute("UPDATE ss_users SET email_verified=1 WHERE id=?", (regular,))
    for owner_id, credential in [(regular, 'cleanup-test'), (uid, 'other-owner-test')]:
        conn.execute("INSERT INTO passkey_credentials(user_id,credential_id,public_key,created_at) VALUES(?,?,?,?)",
                     (owner_id, credential, 'synthetic-key', '2026-09-19'))
    pid = conn.execute('SELECT id FROM passkey_credentials WHERE user_id=?', (regular,)).fetchone()[0]
    conn.commit(); conn.close()
    with client.session_transaction() as session:
        session.clear(); session['ss_user_id'] = regular; session['user_csrf'] = 'credential-test'
    headers = {'X-CSRF-Token': 'credential-test'}
    for status, verified in [('disabled', 1), ('active', 0)]:
        conn = db._conn()
        conn.execute('UPDATE ss_users SET status=?,email_verified=? WHERE id=?', (status, verified, regular))
        conn.commit(); conn.close()
        assert client.get('/api/v1/passkeys/status').status_code == 401
        for path in ('options', 'verify'):
            assert client.post('/api/v1/passkeys/register/' + path, json={}, headers=headers).status_code == 401
        assert client.delete(f'/api/v1/passkeys/{pid}', headers=headers).status_code == 401
    conn = db._conn()
    assert conn.execute('SELECT COUNT(*) FROM passkey_credentials WHERE user_id=?', (regular,)).fetchone()[0] == 1
    conn.execute("UPDATE ss_users SET status='active',email_verified=1 WHERE id=?", (regular,))
    conn.commit(); conn.close()
    assert client.get('/api/v1/passkeys/status').status_code == 200
    response = client.post('/api/account/delete', headers=headers)
    assert response.status_code == 200 and response.json['ok']
    conn = db._conn()
    assert conn.execute('SELECT COUNT(*) FROM passkey_credentials WHERE user_id=?', (regular,)).fetchone()[0] == 0
    assert conn.execute('SELECT COUNT(*) FROM passkey_credentials WHERE user_id=?', (uid,)).fetchone()[0] == 1
    conn.close()
    guest = webapp.app.test_client()
    response = guest.get('/api/v1/passkeys/status')
    assert response.status_code == 200 and response.json['data']['credentials'] == []
    print('Signature integration checks passed')


if __name__ == '__main__':
    integration_check()


def test_editor_treats_user_text_as_text_and_binds_controls():
    if not shutil.which('node'):
        pytest.skip('Node.js is needed to execute the profile editor')
    script = r'''
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const fields = {}, calls = [];
function element(tag) { return {tag, textContent:'', value:'', dataset:{}, style:{}, children:[],
  addEventListener(event, fn){this[event]=fn;}, appendChild(child){this.children.push(child);}, focus(){}}; }
const value = element('div'); value.textContent = '<img src=x onerror=alert(1)>'; fields.val_notes = value;
const context = {LANG_M:'en', document:{createElement:element, getElementById:id=>fields[id]},
  saveField:key=>calls.push('save:'+key), cancelEdit:key=>calls.push('cancel:'+key)};
vm.createContext(context); vm.runInContext(fs.readFileSync('static/js/manage-profile.js','utf8'),context);
context.editField('notes');
assert.equal(value.children[0].value, '<img src=x onerror=alert(1)>');
assert.equal(value.children[0].tag, 'input');
value.children[1].children[0].click(); value.children[1].children[1].click();
assert.deepEqual(calls, ['save:notes','cancel:notes']);
'''
    result = subprocess.run(['node', '-e', script], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_cbc_export_preserves_actual_parser_measurements():
    import blood_test
    import fhir_export
    entries, _ = blood_test.parse_blood_text('Hb: 12.5 g/dL\nWBC: 6.0 10^9/L')
    results, *_ = blood_test.analyze_blood(entries, 'female', 25)
    indicators = blood_test.describe_results(results, 'en')
    bundle = fhir_export.build_bundle(account_id=7, blood_tests=[{
        'id': 1, 'data': {'gender': 'female', 'age': 25, 'level': 'normal',
                         'summary': 'Test summary', 'indicators': indicators, 'notes': [], 'dangers': []}}])
    obs = next(x['resource'] for x in bundle['entry'] if x['resource']['resourceType'] == 'Observation')
    components = obs['component']
    assert len(components) == len(indicators) == 2
    for component, indicator in zip(components, indicators):
        assert component['code']['text'] == indicator['name']
        assert component['valueQuantity']['value'] == indicator['value']
        assert component['valueQuantity']['unit'] == indicator['unit']


@pytest.mark.parametrize('value', [float('nan'), float('inf'), True])
def test_cbc_export_rejects_invalid_measurements(value):
    import fhir_export
    bundle = fhir_export.build_bundle(account_id=7, blood_tests=[{
        'id': 1, 'data': {'indicators': [{'key': 'hgb', 'value': value, 'unit': 'g/dL'}]}}])
    obs = next(x['resource'] for x in bundle['entry'] if x['resource']['resourceType'] == 'Observation')
    assert 'component' not in obs
