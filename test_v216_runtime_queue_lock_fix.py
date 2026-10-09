import source_bundle
import versioning
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_advanced_features_schema_is_cached():
    s = read("advanced_features.py")
    assert "_SCHEMA_READY_KEY" in s and "_SCHEMA_LOCK" in s
    assert "key = db._database_identity()" in s


def test_operational_schema_is_cached():
    s = read("admin_operational.py")
    assert "_SCHEMA_READY_KEY" in s and "_SCHEMA_LOCK" in s


def test_telegram_schema_is_cached():
    s = read("medication_telegram.py")
    assert "_SCHEMA_READY_KEY" in s and "_SCHEMA_LOCK" in s


def test_heavy_maintenance_is_out_of_web_by_default():
    s = source_bundle.webapp_text()
    assert "RETENTION_HOUSEKEEPING_IN_WEB" in s
    assert "BACKUP_SCHEDULER_IN_WEB" in s
    env = read(".env.example")
    assert "RETENTION_HOUSEKEEPING_IN_WEB=0" in env
    assert "BACKUP_SCHEDULER_IN_WEB=0" in env


def test_bounded_server_and_pool_capacity():
    web = source_bundle.webapp_text()
    entry = read("railway_entrypoint.py")
    db = read("db.py")
    assert '_bounded_env_int("WEB_THREADS", 12, 4, 24)' in web
    assert '_bounded_env_int("WEB_THREADS", 12, 4, 24)' in entry
    assert '_bounded_env_int("POSTGRES_POOL_MAX", 16, minconn, 50)' in db


def test_slow_request_logging_is_privacy_safe():
    s = source_bundle.webapp_text()
    assert "SLOW_REQUEST method=%s path=%s status=%s elapsed_ms=%s" in s
    start = s.index("def log_slow_requests")
    end = s.index("def reject_cross_site_mutations")
    assert "request.full_path" not in s[start:end]


def test_v216_revision_markers():
    assert "v216-runtime-lock-fix" in source_bundle.webapp_text()
    assert versioning.SW_CACHE in read("service-worker.js")
    assert "\"delivery_revision\": \"%s\"" % versioning.REVISION in read("release_metrics.json")
