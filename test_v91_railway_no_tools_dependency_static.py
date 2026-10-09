import versioning
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def test_docker_build_has_no_tools_dependency():
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "SymptoSense Railway build profile: " + versioning.REVISION in docker
    assert "tools/release_check.py" not in docker
    assert "tools/check_translations.py" not in docker
    assert "test -s tools/" not in docker

def test_tools_are_excluded_from_production_context():
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert "tools/" in dockerignore
    assert "!tools/" not in dockerignore

def test_runtime_entrypoints_are_root_level():
    railway = (ROOT / "railway.json").read_text(encoding="utf-8")
    procfile = (ROOT / "Procfile").read_text(encoding="utf-8")
    assert "python railway_entrypoint.py" in railway
    assert "web: python railway_entrypoint.py" in procfile
