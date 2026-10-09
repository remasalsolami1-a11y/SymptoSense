import source_bundle
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent


def test_railway_uses_docker_health_path_and_explicit_bootstrap_start_command():
    cfg = json.loads((ROOT / 'railway.json').read_text(encoding='utf-8'))
    assert cfg['build']['builder'] == 'DOCKERFILE'
    assert cfg['build']['dockerfilePath'] == 'Dockerfile'
    assert cfg['deploy']['healthcheckPath'] == '/health'
    assert cfg['deploy']['healthcheckTimeout'] == 300
    assert cfg['deploy']['startCommand'] == 'python railway_entrypoint.py'


def test_webapp_binds_to_railway_port_before_database_readiness_gate():
    src = source_bundle.webapp_text()
    tail = source_bundle.between('def run_webapp():')
    assert 'os.environ.get("PORT", 5000)' in tail
    assert 'serve(app, host="0.0.0.0", port=port, threads=_bounded_env_int("WEB_THREADS", 12, 4, 24))' in tail
    assert 'target=_initialize_core_runtime_services' in tail
    # The blocking core initialization must not run directly in run_webapp.
    assert 'db.init_db()' not in tail


def test_health_is_liveness_and_ready_is_strict_readiness_without_request_time_database_call():
    src = source_bundle.webapp_text()
    block = source_bundle.between('def _health_payload():', '@app.route("/")')
    assert 'core_database' in block
    assert '@app.route("/health", methods=["GET"])' in block
    assert 'return jsonify(_health_payload()), 200' in block
    assert '@app.route("/ready", methods=["GET"])' in block
    assert '200 if ready else 503' in block
    assert 'db.init_db()' not in block
    assert 'healthcheck.railway.app' in (ROOT / 'web_security.py').read_text(encoding='utf-8')


def test_core_database_initialization_retries_and_then_warms_optional_services():
    src = source_bundle.webapp_text()
    block = source_bundle.between('def _initialize_core_runtime_services():', 'def run_webapp():')
    assert 'STARTUP_DB_INIT_ATTEMPTS' in block
    assert 'db.init_db()' in block
    assert '_warm_optional_runtime_services()' in block
    assert 'time.sleep(min(2 * attempt, 10))' in block


def test_postgres_sessions_have_bounded_lock_and_statement_timeouts():
    src = (ROOT / 'db.py').read_text(encoding='utf-8')
    assert 'POSTGRES_LOCK_TIMEOUT_MS' in src
    assert 'POSTGRES_STATEMENT_TIMEOUT_MS' in src
    assert 'options=pg_options' in src


def test_chat_view_import_survives_flat_repository_upload():
    src = source_bundle.webapp_text()
    assert 'from chat_view import render_chat_page' in src
    assert 'from views.chat_view import render_chat_page' not in src
    assert (ROOT / 'chat_view.py').is_file()
    assert 'def render_chat_page' in source_bundle.chat_view_text()
