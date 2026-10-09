import source_bundle
import versioning
from pathlib import Path
import json
import os
import tempfile

ROOT = Path(__file__).resolve().parent
MED = (ROOT / "medication_email.py").read_text(encoding="utf-8")
PRIV = (ROOT / "privacy_features.py").read_text(encoding="utf-8")
DBTXT = (ROOT / "db.py").read_text(encoding="utf-8")
WEB = source_bundle.webapp_text()
SW = (ROOT / "service-worker.js").read_text(encoding="utf-8")
METRICS = json.loads((ROOT / "release_metrics.json").read_text(encoding="utf-8"))


def _sqlite(monkeypatch):
    import db, medication_email, privacy_features, medication_telegram
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    monkeypatch.setattr(db, "DATABASE_URL", "")
    monkeypatch.setattr(db, "USE_POSTGRES", False)
    monkeypatch.setattr(db, "PH", "?")
    monkeypatch.setattr(db, "DB_PATH", tmp.name)
    monkeypatch.setattr(db, "_DB_READY_KEY", None)
    monkeypatch.setattr(medication_email, "PH", "?")
    monkeypatch.setattr(medication_email, "_SCHEMA_READY_KEY", None)
    monkeypatch.setattr(medication_telegram, "PH", "?")
    monkeypatch.setattr(privacy_features, "PH", "?")
    monkeypatch.setattr(privacy_features, "_SCHEMA_READY", None)
    db.init_db()
    medication_email.init_schema()
    privacy_features.init_schema()
    return tmp.name, db, medication_email, privacy_features


def _count(db, table, where="", params=()):
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute(f"SELECT COUNT(*) FROM {table}" + (f" WHERE {where}" if where else ""), params)
        return int(c.fetchone()[0])
    finally:
        conn.close()


def test_v215_static_release_and_privacy_contract():
    assert 'MEDS_API_REVISION = "v216-runtime-lock-fix"' in WEB
    assert "MEDS_API_REVISION_JS='v216-runtime-lock-fix'" in WEB
    assert versioning.SW_CACHE in SW
    assert "earlyUrl.pathname.startsWith('/api/')" in SW
    assert METRICS["delivery_revision"] == versioning.REVISION
    assert "med_name TEXT NOT NULL DEFAULT ''" not in MED
    assert "INSERT INTO med_plan_tombstones(user_hash,plan_id,deleted_at)" in MED
    assert "SET med_name=''" in MED  # scrubs an intermediate V214 DB if one exists
    assert "_SCHEMA_READY_KEY" in MED
    assert "related dose history" in WEB
    assert "سجل الجرعات المرتبط به" in WEB


def test_tombstone_has_no_health_content_and_delete_clears_history(monkeypatch):
    path, db, medication_email, _ = _sqlite(monkeypatch)
    try:
        uid = 501
        pid = medication_email.save_plan(uid, {
            "med_name": "PRIVATE MED NAME", "times": ["08:00"], "frequency": "daily",
            "start_date": "2027-12-31", "timezone": "Asia/Riyadh", "delivery_channel": "email",
        })
        db.log_med_status(uid, 0, pid, "2027-12-31", "08:00", "taken")
        assert _count(db, "med_logs", "plan_id=?", (pid,)) == 1
        assert medication_email.delete_plan(uid, pid) is True
        conn = db._conn(); c = conn.cursor()
        try:
            c.execute("PRAGMA table_info(med_plan_tombstones)")
            cols = {r[1] for r in c.fetchall()}
            assert "med_name" not in cols
            c.execute("SELECT user_hash,plan_id,deleted_at FROM med_plan_tombstones WHERE plan_id=?", (pid,))
            row = c.fetchone()
            assert row and int(row[1]) == int(pid) and row[2]
        finally:
            conn.close()
        assert _count(db, "med_plans", "id=?", (pid,)) == 0
        assert _count(db, "med_logs", "plan_id=?", (pid,)) == 0
        assert _count(db, "medication_reminders", "plan_id=?", (pid,)) == 0
    finally:
        try: os.unlink(path)
        except OSError: pass


def test_privacy_center_sees_exports_and_deletes_numeric_medication_rows(monkeypatch):
    path, db, medication_email, privacy_features = _sqlite(monkeypatch)
    try:
        uid = 502
        owner = f"account-{uid}"
        pid = medication_email.save_plan(uid, {
            "med_name": "QA PRIVACY", "times": ["09:00"], "frequency": "daily",
            "start_date": "2027-12-31", "timezone": "Asia/Riyadh", "delivery_channel": "email",
        })
        db.log_med_status(uid, 0, pid, "2027-12-31", "09:00", "taken")
        assert privacy_features.stored_data_types(uid, owner)["medication_reminders"] is True
        export = privacy_features._safe_user_export(uid, owner)
        assert any(x.get("med_name") == "QA PRIVACY" for x in export["medication_reminders"])
        assert any(int(x.get("plan_id") or 0) == int(pid) for x in export["medication_history"])
        result = privacy_features.delete_health_data(uid, owner)
        assert result["deleted_items"] >= 3
        med_hash = db._hash_user(uid)
        for table in ("med_plans", "med_logs", "med_snoozes", "med_plan_tombstones"):
            assert _count(db, table, "user_hash=?", (med_hash,)) == 0
        for table in ("medication_reminders", "med_reminder_settings", "med_email_actions", "med_email_deliveries", "med_telegram_links", "med_telegram_deliveries"):
            assert _count(db, table, "user_id=?", (uid,)) == 0
        assert privacy_features.stored_data_types(uid, owner)["medication_reminders"] is False
    finally:
        try: os.unlink(path)
        except OSError: pass


def test_delete_ss_user_removes_numeric_medication_tables_and_tombstones(monkeypatch):
    path, db, medication_email, _ = _sqlite(monkeypatch)
    try:
        uid = 503
        # Create a minimal account row and both an active plan and a tombstone.
        conn = db._conn(); c = conn.cursor()
        now = "2026-10-03T00:00:00+00:00"
        c.execute("INSERT INTO ss_users(email,password_hash,name,role,status,created_at,email_verified) VALUES(?,?,?,?,?,?,?)",
                  ("v215@example.test", "x", "V216", "user", "active", now, 1))
        real_uid = int(c.lastrowid)
        conn.commit(); conn.close()
        uid = real_uid
        active = medication_email.save_plan(uid, {"med_name":"ACTIVE", "times":["10:00"], "frequency":"daily", "start_date":"2027-12-31"})
        gone = medication_email.save_plan(uid, {"med_name":"GONE", "times":["11:00"], "frequency":"daily", "start_date":"2027-12-31"})
        assert medication_email.delete_plan(uid, gone) is True
        assert _count(db, "med_plans", "id=?", (active,)) == 1
        assert _count(db, "med_plan_tombstones", "plan_id=?", (gone,)) == 1
        db.delete_ss_user(uid)
        assert _count(db, "ss_users", "id=?", (uid,)) == 0
        assert _count(db, "med_plans", "user_hash=?", (db._hash_user(uid),)) == 0
        assert _count(db, "med_plan_tombstones", "user_hash=?", (db._hash_user(uid),)) == 0
        assert _count(db, "medication_reminders", "user_id=?", (uid,)) == 0
    finally:
        try: os.unlink(path)
        except OSError: pass


def test_public_launch_cleanup_includes_all_modern_medication_tables():
    for table in (
        "medication_reminders", "med_reminder_settings", "med_email_actions",
        "med_email_deliveries", "med_telegram_links", "med_telegram_deliveries",
        "med_plan_tombstones",
    ):
        assert f'"{table}"' in DBTXT
