from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent


def test_production_build_does_not_depend_on_tools_directory():
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "python tools/release_check.py" not in docker
    assert "tools/railway_entrypoint.py" not in docker
    assert "python -m py_compile railway_entrypoint.py railway_runtime.py webapp.py" in docker
    assert 'CMD ["python", "railway_entrypoint.py"]' in docker


def test_railway_start_command_uses_root_entrypoint():
    cfg = json.loads((ROOT / "railway.json").read_text(encoding="utf-8"))
    assert cfg["deploy"]["startCommand"] == "python railway_entrypoint.py"
    assert cfg["deploy"]["healthcheckPath"] == "/health"


def test_dockerignore_excludes_qa_tools_and_keeps_root_runtime_checks():
    ignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert "tools/*" in ignore
    assert "tools/" in ignore
    assert "release_check.py" in ignore
    assert "release_check.py" in ignore
    assert (ROOT / "release_check.py").is_file()
    assert (ROOT / "tools" / "check_translations.py").is_file()
    assert (ROOT / "railway_entrypoint.py").is_file()
