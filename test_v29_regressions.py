import importlib
import os
import sys
import tempfile
import types
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def _stub_groq():
    if "groq" not in sys.modules:
        mod = types.ModuleType("groq")
        mod.Groq = type("Groq", (), {})
        sys.modules["groq"] = mod


def test_multi_symptom_result_hides_one_symptom_weak_leftovers():
    _stub_groq()
    tmp = tempfile.TemporaryDirectory(prefix="ss-v29-match-")
    os.environ.pop("DATABASE_URL", None)
    os.environ["DB_PATH"] = str(Path(tmp.name) / "test.sqlite3")
    import db, medical_knowledge, analysis_core
    importlib.reload(db); importlib.reload(medical_knowledge); importlib.reload(analysis_core)
    patient = {
        "age": 25, "gender": "f", "symptoms": ["صداع", "غثيان"],
        "duration": "يوم", "severity": 2, "conditions": "", "medications": "",
        "allergies": "", "history_answered": True, "negative_symptoms": ["vomiting"],
        "user_id": "v29-test",
    }
    result = analysis_core.run_analysis(patient, "ar")
    weak = [m for m in (result.get("knowledge_matches") or []) if m.get("match_level") == "weak"]
    assert all(len(m.get("matched_symptoms") or []) >= 2 for m in weak)
    assert "التهاب الجيوب الأنفية" not in (result.get("possible_conditions") or "")


def test_single_symptom_can_still_show_source_grounded_low_match():
    _stub_groq()
    tmp = tempfile.TemporaryDirectory(prefix="ss-v29-single-")
    os.environ.pop("DATABASE_URL", None)
    os.environ["DB_PATH"] = str(Path(tmp.name) / "test.sqlite3")
    import db, medical_knowledge, analysis_core
    importlib.reload(db); importlib.reload(medical_knowledge); importlib.reload(analysis_core)
    patient = {
        "age": 25, "gender": "f", "symptoms": ["تساقط الشعر"],
        "duration": "أسبوع", "severity": 2, "conditions": "", "medications": "",
        "allergies": "", "history_answered": True, "negative_symptoms": [],
        "user_id": "v29-single",
    }
    result = analysis_core.run_analysis(patient, "ar")
    assert result.get("assessment_status") == "complete"
    assert result.get("knowledge_matches")
    assert any(m.get("match_level") == "weak" for m in result["knowledge_matches"])
    assert "توافق منخفض" in (result.get("possible_conditions") or "")


def _verified_med_user(db, email):
    uid, err = db.create_ss_user(email, "Medication Test", "StrongPassword123!")
    assert uid and not err
    conn = db._conn(); c = conn.cursor()
    c.execute("UPDATE ss_users SET email_verified=1,status='active' WHERE id=?", (uid,))
    conn.commit(); conn.close()
    return uid


def test_email_action_taken_prevents_later_snooze_for_same_occurrence():
    tmp = tempfile.TemporaryDirectory(prefix="ss-v29-email-")
    os.environ.pop("DATABASE_URL", None)
    os.environ["DB_PATH"] = str(Path(tmp.name) / "email.sqlite3")
    import db, medication_email
    importlib.reload(db); importlib.reload(medication_email)
    db.init_db(); medication_email.init_schema()
    uid = _verified_med_user(db, "v29-email@example.test")
    now = datetime.now(timezone.utc); tm = now.strftime("%H:%M")
    pid = medication_email.save_plan(uid, {"med_name":"Test","times":[tm],"timezone":"UTC","start_date":now.date().isoformat()})
    taken = medication_email._create_action_token(uid,pid,0,now.date().isoformat(),tm,"ar","taken")
    snooze = medication_email._create_action_token(uid,pid,0,now.date().isoformat(),tm,"ar","snooze")
    assert medication_email.handle_email_action(taken)["status"] == "taken"
    try:
        medication_email.handle_email_action(snooze)
    except PermissionError as exc:
        assert "already_taken" in str(exc)
    else:
        raise AssertionError("snooze after taken must be rejected")


def test_email_snooze_creates_one_pending_occurrence():
    tmp = tempfile.TemporaryDirectory(prefix="ss-v29-snooze-")
    os.environ.pop("DATABASE_URL", None)
    os.environ["DB_PATH"] = str(Path(tmp.name) / "email.sqlite3")
    import db, medication_email
    importlib.reload(db); importlib.reload(medication_email)
    db.init_db(); medication_email.init_schema()
    uid = _verified_med_user(db, "v29-snooze@example.test")
    now = datetime.now(timezone.utc); tm = now.strftime("%H:%M")
    pid = medication_email.save_plan(uid, {"med_name":"Test","times":[tm],"timezone":"UTC","start_date":now.date().isoformat()})
    medication_email.schedule_snooze(uid,pid,0,now.date().isoformat(),tm,10)
    conn=db._conn(); c=conn.cursor(); c.execute("SELECT COUNT(*) FROM med_snoozes WHERE status='pending'")
    assert c.fetchone()[0] == 1
    conn.close()
