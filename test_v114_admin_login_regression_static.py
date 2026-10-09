import source_bundle
from pathlib import Path

ROOT=Path(__file__).resolve().parent
WEB=source_bundle.webapp_text()

def test_login_does_not_initialize_optional_platform_schema():
    block=source_bundle.between('@app.route("/login", methods=["GET", "POST"])', '@app.route("/register"')
    assert "db.init_db()" in block
    assert "platform_v2.init_schema()" not in block

def test_api_login_does_not_initialize_optional_platform_schema():
    start=WEB.index('@app.route("/api/auth/login", methods=["POST"])')
    block=WEB[start:start+5000]
    assert "db.init_db()" in block
    assert "platform_v2.init_schema()" not in block

def test_admin_auth_core_is_independent_and_warmed_after_core_db():
    assert "def _warm_admin_auth_core():" in WEB
    assert "admin_2fa.init_schema()" in WEB
    assert "admin_security.init_schema()" in WEB
    assert "_start_admin_auth_core_warmup_once()" in WEB
    assert 'app.logger.info("ADMIN_AUTH core ready")' in WEB

def test_admin_login_has_retryable_not_ready_state():
    assert "admin_security_initializing" in WEB
    assert "_admin_auth_core_ready(2.0)" in WEB
    assert "login_admin_core_not_ready" in WEB

def test_login_telemetry_is_non_blocking():
    assert "def _record_login_telemetry_async" in WEB
    assert 'name="symptosense-login-telemetry"' in WEB
