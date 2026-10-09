from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_release_check_does_not_use_compileall_or_emit_bytecode_contract():
    src = (ROOT / "release_check.py").read_text(encoding="utf-8")
    assert "compileall" not in src
    assert "compile(source" in src
    assert "check_release_tree_hygiene" in src
    assert "__pycache__" in src and ".pytest_cache" in src


def test_railway_liveness_fast_path_is_host_independent_and_narrow():
    src = (ROOT / "railway_runtime.py").read_text(encoding="utf-8")
    assert "if path in self._PATHS and method in" in src
    assert "host == self._HOST" not in src
    assert "Content-Length" in src
