from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent


def test_bootstrap_binds_before_importing_webapp():
    src = (ROOT / "railway_entrypoint.py").read_text(encoding="utf-8")
    bind = src.index("create_server(bootstrap_app")
    loader = src.index("threading.Thread(target=_load_full_application")
    assert bind < loader
    assert 'host="0.0.0.0"' in src
    assert 'os.environ.get("PORT")' in src


def test_bootstrap_health_waits_for_real_app_but_reports_core_database_state():
    src = (ROOT / "railway_entrypoint.py").read_text(encoding="utf-8")
    health = src[src.index("def bootstrap_app"):src.index("def _load_full_application")]
    assert '{"/health", "/healthz"}' in health
    assert 'app_loaded = snap["app"] is not None' in health
    assert 'core_ready = bool(core.get("ready"))' in health
    assert 'healthy = bool(app_loaded and not bootstrap_failed)' in health
    assert '"200 OK" if healthy else "503 Service Unavailable"' in health
    assert 'app = snap["app"]' in health


def test_railway_config_forces_bootstrap_command_over_stale_ui_settings():
    cfg = json.loads((ROOT / "railway.json").read_text(encoding="utf-8"))
    assert cfg["deploy"]["startCommand"] == "python railway_entrypoint.py"
    assert cfg["deploy"]["healthcheckPath"] == "/health"


def test_missing_database_reference_uses_attached_volume_only_as_fallback():
    src = (ROOT / "railway_runtime.py").read_text(encoding="utf-8")
    assert 'SYMPTOSENSE_DATABASE_MODE' in src
    assert 'sqlite-volume-fallback' in src
    assert 'RAILWAY_VOLUME_MOUNT_PATH' in src
    assert 'DATABASE_URL' in src


def test_docker_build_runs_release_check_before_bootstrap():
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "python -m pip check" in docker
    assert "python -m py_compile railway_entrypoint.py railway_runtime.py webapp.py" in docker
    assert 'CMD ["python", "railway_entrypoint.py"]' in docker
