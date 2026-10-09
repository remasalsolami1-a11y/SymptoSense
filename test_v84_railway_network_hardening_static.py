import source_bundle
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import railway_runtime


def _call_wsgi(app, *, host='healthcheck.railway.app', path='/health', method='GET'):
    captured = {}
    def start_response(status, headers):
        captured['status'] = status
        captured['headers'] = dict(headers)
    environ = {'HTTP_HOST': host, 'PATH_INFO': path, 'REQUEST_METHOD': method}
    body = b''.join(app(environ, start_response))
    return captured, body


def test_railway_health_fast_path_returns_200_without_flask():
    def downstream(_environ, _start_response):
        raise AssertionError('Railway healthcheck should not reach Flask/downstream app')
    app = railway_runtime.RailwayHealthcheckMiddleware(downstream)
    meta, body = _call_wsgi(app)
    assert meta['status'].startswith('200')
    assert meta['headers']['X-SymptoSense-Liveness'] == '1'
    assert b'"ok":true' in body and b'"status":"alive"' in body


def test_health_fast_path_is_host_independent_but_path_scoped():
    calls = []
    def downstream(environ, start_response):
        calls.append((environ['HTTP_HOST'], environ['PATH_INFO']))
        start_response('418 Teapot', [('Content-Type', 'text/plain')])
        return [b'downstream']
    app = railway_runtime.RailwayHealthcheckMiddleware(downstream)
    meta, body = _call_wsgi(app, host='symptosensehealth.com')
    assert meta['status'].startswith('200') and b'"ok":true' in body
    assert not calls
    meta, body = _call_wsgi(app, host='symptosensehealth.com', path='/ready')
    assert meta['status'].startswith('418') and body == b'downstream'
    assert calls


def test_head_health_has_empty_body_but_still_200():
    app = railway_runtime.RailwayHealthcheckMiddleware(lambda *_: (_ for _ in ()).throw(AssertionError()))
    meta, body = _call_wsgi(app, method='HEAD')
    assert meta['status'].startswith('200')
    assert body == b''
    assert int(meta['headers']['Content-Length']) > 0


def test_docker_workdir_and_entrypoint_are_isolated_from_legacy_volume_mounts():
    docker = (ROOT / 'Dockerfile').read_text(encoding='utf-8')
    assert 'WORKDIR /opt/symptosense/app' in docker
    assert 'WORKDIR /app' not in docker
    assert 'WORKDIR /srv/symptosense' not in docker
    assert 'CMD ["python", "railway_entrypoint.py"]' in docker


def test_webapp_installs_fast_path_and_keeps_strict_readiness():
    src = source_bundle.webapp_text()
    assert 'RailwayHealthcheckMiddleware(app.wsgi_app)' in src
    assert 'railway_runtime.log_runtime_context(app.logger)' in src
    assert '@app.route("/ready", methods=["GET"])' in src
    assert '200 if ready else 503' in src


def test_railway_config_still_uses_liveness_path_and_injected_port_contract():
    cfg = json.loads((ROOT / 'railway.json').read_text(encoding='utf-8'))
    assert cfg['deploy']['healthcheckPath'] == '/health'
    assert cfg['deploy']['healthcheckTimeout'] == 300
    assert cfg['deploy']['startCommand'] == 'python railway_entrypoint.py'
    src = source_bundle.webapp_text()
    assert 'os.environ.get("PORT", 5000)' in src


def test_environment_compatibility_keeps_fail_fast_but_accepts_safe_legacy_names():
    env = {
        'SECRET_KEY': 'x' * 40,
        'PGUSER': 'user',
        'PGPASSWORD': 'p@ss word',
        'PGHOST': 'db.railway.internal',
        'PGPORT': '5432',
        'PGDATABASE': 'railway',
    }
    railway_runtime.normalize_environment(env)
    assert env['WEB_SECRET'] == 'x' * 40
    assert env['DATABASE_URL'].startswith('postgresql://user:p%40ss%20word@db.railway.internal:5432/railway')
