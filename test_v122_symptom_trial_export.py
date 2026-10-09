import source_bundle
from pathlib import Path
import os, sys, tempfile

ROOT=Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

DB=(ROOT/'db.py').read_text(encoding='utf-8')
WEB=source_bundle.webapp_text()
DASH=(ROOT/'dashboard.py').read_text(encoding='utf-8')
CORE=(ROOT/'analysis_core.py').read_text(encoding='utf-8')


def test_root_cause_fixed_export_reads_records_not_blood_tests():
    start=DB.index('def admin_symptom_trial_rows():')
    end=DB.index('def admin_symptom_trial_summary():',start)
    block=DB[start:end]
    assert 'FROM records' in block
    assert 'FROM blood_tests' not in block
    assert 'SELECT r.age, r.gender, r.symptoms, r.duration, res.data' in block


def test_excel_contains_only_requested_four_data_columns():
    start=DB.index('def admin_export_symptom_trials_xlsx():')
    end=DB.index('def admin_clear_symptom_trials():',start)
    block=DB[start:end]
    assert "headers=['Age | العمر','Gender | الجنس','Symptoms | الأعراض','Duration | المدة']" in block
    assert "'email'" not in block.lower()
    assert 'tester_code' not in block
    assert 'risk_level' not in block


def test_admin_ui_uses_symptom_trial_routes():
    assert 'href="/admin/analysis-trials"' in DASH
    assert 'href="/admin/analysis-trials/export.xlsx" download' in DASH
    assert 'العمر • الجنس • الأعراض • المدة فقط' in DASH
    assert 'لا تظهر الأسماء أو البريد الإلكتروني في أي ملف' in DASH


def test_guest_analysis_remains_ephemeral_and_signed_in_analysis_reports_save_state():
    assert 'if user_id and str(user_id).startswith("account-"):' in CORE
    assert '"record_saved": bool(record_id)' in CORE
    assert 'Authenticated symptom analysis could not be persisted' in CORE


def test_clear_symptom_trials_preserves_accounts_and_blood_tests():
    start=DB.index('def admin_clear_symptom_trials():')
    end=DB.index('def admin_blood_test_trial_summary():',start)
    block=DB[start:end]
    assert "DELETE FROM records" in block
    assert "DELETE FROM results" in block
    assert "DELETE FROM blood_tests" not in block
    assert "DELETE FROM ss_users" not in block


def test_runtime_rows_are_retrieved_from_saved_symptom_analyses_only(monkeypatch):
    import db
    tmp=tempfile.NamedTemporaryFile(suffix='.db',delete=False)
    tmp.close()
    monkeypatch.setattr(db,'DATABASE_URL','')
    monkeypatch.setattr(db,'USE_POSTGRES',False)
    monkeypatch.setattr(db,'PH','?')
    monkeypatch.setattr(db,'DB_PATH',tmp.name)
    monkeypatch.setattr(db,'_DB_READY_KEY',None)
    db.init_db()
    db.save_analysis_record_with_result(
        'account-1','ar',23,'f',['صداع','غثيان'],'يومين',2,'low',
        {'ok':True},member_id=0,
    )
    # CBC data must NOT leak into the symptom-trial export.
    db.save_blood_test('account-1',{'age':99,'gender':'m','summary':'cbc-only'},0)
    rows=db.admin_symptom_trial_rows()
    assert len(rows)==1
    assert rows[0]=={
        'age':23,
        'gender':'Female | أنثى',
        'symptoms':'صداع • غثيان',
        'duration':'يومين',
    }
    summary=db.admin_symptom_trial_summary()
    assert summary['saved_analyses']==1
    assert summary['distinct_testers']==1


def test_runtime_clear_removes_analysis_rows_but_keeps_cbc(monkeypatch):
    import db
    tmp=tempfile.NamedTemporaryFile(suffix='.db',delete=False)
    tmp.close()
    monkeypatch.setattr(db,'DATABASE_URL','')
    monkeypatch.setattr(db,'USE_POSTGRES',False)
    monkeypatch.setattr(db,'PH','?')
    monkeypatch.setattr(db,'DB_PATH',tmp.name)
    monkeypatch.setattr(db,'_DB_READY_KEY',None)
    db.init_db()
    db.save_analysis_record_with_result('account-2','en',30,'m',['headache'],'3 days',2,'low',{'ok':True})
    db.save_blood_test('account-2',{'age':30,'gender':'m','summary':'cbc'},0)
    result=db.admin_clear_symptom_trials()
    assert result['deleted_analyses']==1
    assert db.admin_symptom_trial_summary()['saved_analyses']==0
    assert db.admin_blood_test_trial_summary()['saved_tests']==1
