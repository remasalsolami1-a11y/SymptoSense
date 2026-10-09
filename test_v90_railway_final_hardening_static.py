import versioning
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent


def test_build_has_current_fingerprint_and_no_tools_runtime_dependency():
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "SymptoSense Railway build profile: " + versioning.REVISION in docker
    assert "python tools/release_check.py" not in docker
    assert 'CMD ["python", "railway_entrypoint.py"]' in docker
    # Compatibility copy may exist, but runtime must never start from tools/.
    assert "tools/railway_entrypoint.py" not in docker


def test_production_docker_context_does_not_depend_on_tools():
    ignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert "tools/" in ignore
    assert "!tools/" not in ignore
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "tools/release_check.py" not in docker
    assert "tools/check_translations.py" not in docker


def test_bootstrap_health_reports_core_database_readiness_without_blocking_liveness():
    src = (ROOT / "railway_entrypoint.py").read_text(encoding="utf-8")
    assert 'core_ready = bool(core.get("ready"))' in src
    assert "healthy = bool(app_loaded and not bootstrap_failed)" in src
    assert '"200 OK" if healthy else "503 Service Unavailable"' in src


def test_railway_config_points_to_root_dockerfile_and_entrypoint():
    cfg = json.loads((ROOT / "railway.json").read_text(encoding="utf-8"))
    assert cfg["build"]["builder"] == "DOCKERFILE"
    assert cfg["build"]["dockerfilePath"] == "Dockerfile"
    assert cfg["deploy"]["startCommand"] == "python railway_entrypoint.py"
    assert cfg["deploy"]["healthcheckPath"] == "/health"
    assert 60 <= int(cfg["deploy"]["healthcheckTimeout"]) <= 300
