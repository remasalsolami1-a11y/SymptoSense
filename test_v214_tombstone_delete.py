import source_bundle
import versioning
from pathlib import Path
import os
import tempfile

ROOT = Path(__file__).resolve().parent
MED = (ROOT / 'medication_email.py').read_text(encoding='utf-8')
WEB = source_bundle.webapp_text()
SW = (ROOT / 'service-worker.js').read_text(encoding='utf-8')


def _sqlite(monkeypatch):
    import db, medication_email
    tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    tmp.close()
    monkeypatch.setattr(db, 'DATABASE_URL', '')
    monkeypatch.setattr(db, 'USE_POSTGRES', False)
    monkeypatch.setattr(db, 'PH', '?')
    monkeypatch.setattr(db, 'DB_PATH', tmp.name)
    monkeypatch.setattr(db, '_DB_READY_KEY', None)
    monkeypatch.setattr(medication_email, 'PH', '?')
    db.init_db()
    medication_email.init_schema()
    return tmp.name, db, medication_email


def test_v214_has_durable_tombstone_and_api_revision_static():
    assert 'CREATE TABLE IF NOT EXISTS med_plan_tombstones' in MED
    assert 'PRIMARY KEY(user_hash, plan_id)' in MED
    assert 'NOT EXISTS (SELECT 1 FROM med_plan_tombstones' in MED
    assert 'medication_delete_tombstone_missing' in MED
    assert 'MEDS_API_REVISION = "v216-runtime-lock-fix"' in WEB
    assert 'MEDS_API_REVISION_JS' in WEB
    assert 'X-SymptoSense-Meds-Revision' in WEB
    assert "'/api/meds/plan?ts='+Date.now()" in WEB
    assert "earlyUrl.pathname.startsWith('/api/')" in SW
    assert versioning.SW_CACHE in SW


def test_delete_is_idempotent_and_tombstoned(monkeypatch):
    path, db, medication_email = _sqlite(monkeypatch)
    try:
        uid = 88
        pid = medication_email.save_plan(uid, {
            'med_name': 'QA V214 DELETE', 'times': ['08:00'], 'frequency': 'daily',
            'start_date': '2027-12-31', 'timezone': 'Asia/Riyadh', 'delivery_channel': 'email'
        })
        assert medication_email.delete_plan(uid, pid) is True
        # Repeating DELETE is safe and stays successful for the same owned tombstone.
        assert medication_email.delete_plan(uid, pid) is True
        conn = db._conn(); c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM med_plans WHERE id=?', (pid,))
        assert c.fetchone()[0] == 0
        c.execute('PRAGMA table_info(med_plan_tombstones)')
        cols = {r[1] for r in c.fetchall()}
        assert 'med_name' not in cols
        c.execute('SELECT deleted_at FROM med_plan_tombstones WHERE user_hash=? AND plan_id=?',
                  (db._hash_user(uid), pid))
        row = c.fetchone(); conn.close()
        assert row and row[0]
    finally:
        try: os.unlink(path)
        except OSError: pass


def test_tombstone_blocks_ghost_resurrection_and_init_purges_it(monkeypatch):
    path, db, medication_email = _sqlite(monkeypatch)
    try:
        uid = 89
        uh = db._hash_user(uid)
        pid = medication_email.save_plan(uid, {
            'med_name': 'QA V214 GHOST', 'times': ['09:15'], 'frequency': 'daily',
            'start_date': '2027-12-31', 'timezone': 'Asia/Riyadh', 'delivery_channel': 'email'
        })
        assert medication_email.delete_plan(uid, pid) is True

        # Simulate a stale rolling-deploy worker restoring the deleted base row.
        conn = db._conn(); c = conn.cursor()
        c.execute(
            'INSERT INTO med_plans(id,user_hash,member_id,med_name,dose,times,frequency,start_date,days,active,created) '
            'VALUES(?,?,?,?,?,?,?,?,?,?,?)',
            (pid, uh, 0, 'QA V214 GHOST', '', '["09:15"]', 'daily', '2027-12-31', None, 1, '2026-10-03T00:00:00+00:00')
        )
        conn.commit(); conn.close()

        # User-facing reads must never show a tombstoned plan, even before cleanup.
        assert all(int(p['id']) != int(pid) for p in medication_email.list_plans(uid, active_only=False))

        # A fresh worker/process runs one-time schema cleanup and physically removes
        # a resurrected ghost row. Ordinary reads do not perform database writes.
        medication_email._SCHEMA_READY_KEY = None
        medication_email.init_schema()
        conn = db._conn(); c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM med_plans WHERE id=?', (pid,))
        assert c.fetchone()[0] == 0
        c.execute('SELECT COUNT(*) FROM med_plan_tombstones WHERE user_hash=? AND plan_id=?', (uh, pid))
        assert c.fetchone()[0] == 1
        conn.close()
    finally:
        try: os.unlink(path)
        except OSError: pass


def test_tombstone_prevents_delivery_row_resync(monkeypatch):
    path, db, medication_email = _sqlite(monkeypatch)
    try:
        uid = 90
        pid = medication_email.save_plan(uid, {
            'med_name': 'QA V214 NO RESYNC', 'times': ['10:00'], 'frequency': 'daily',
            'start_date': '2027-12-31', 'timezone': 'Asia/Riyadh', 'delivery_channel': 'email'
        })
        assert medication_email.delete_plan(uid, pid) is True
        medication_email._sync_reminder_rows(uid, pid, {
            'med_name': 'QA V214 NO RESYNC', 'times': ['10:00'], 'frequency': 'daily',
            'start_date': '2027-12-31', 'timezone': 'Asia/Riyadh', 'active': True,
            'delivery_channel': 'email'
        })
        conn = db._conn(); c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM medication_reminders WHERE plan_id=?', (pid,))
        assert c.fetchone()[0] == 0
        conn.close()
    finally:
        try: os.unlink(path)
        except OSError: pass
