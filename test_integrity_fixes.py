from pathlib import Path
import importlib


def test_messages_module_imports_and_uses_curated_symptoms():
    messages = importlib.import_module("messages")
    ar = messages.get_symptoms_message("ar")
    en = messages.get_symptoms_message("en")
    assert "صداع" in ar
    assert "Headache" in en
    assert "from ..database" not in Path("messages.py").read_text(encoding="utf-8")


def test_training_pipeline_uses_deterministic_rng_and_canonical_order():
    text = Path("train_model.py").read_text(encoding="utf-8")
    assert "rng = random.Random(RANDOM_SEED)" in text
    assert "tuple(sorted({" in text
    assert "random_state=RANDOM_SEED" in text


def test_dev_requirements_include_training_dependencies():
    deps = Path("requirements-dev.txt").read_text(encoding="utf-8").lower()
    assert "numpy" in deps
    assert "scikit-learn" in deps


def test_dev_requirements_include_device_smoke_dependency():
    deps = Path("requirements-dev.txt").read_text(encoding="utf-8").lower()
    assert "playwright" in deps


def test_backend_smoke_is_directly_executable_from_project_root():
    text = Path("v36_backend_smoke.py").read_text(encoding="utf-8")
    assert "sys.path.insert(0, str(ROOT))" in text
