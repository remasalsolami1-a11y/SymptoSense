import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import health_search


def _load_helper():
    source = (ROOT / 'webapp.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_assistant_local_health_answer')
    module = ast.Module(body=[node], type_ignores=[])
    ns = {'health_search': health_search}
    exec(compile(ast.fix_missing_locations(module), '<assistant-helper>', 'exec'), ns)
    return ns['_assistant_local_health_answer'], source


def test_dizziness_gets_useful_local_answer():
    helper, _ = _load_helper()
    answer = helper('دوخة', 'ar')
    assert 'الدوخة' in answer
    assert 'الجفاف' in answer
    assert 'لا أستطيع الرد الكامل' not in answer
    assert 'ليست تشخيص' in answer


def test_compound_query_keeps_both_topics():
    helper, _ = _load_helper()
    answer = helper('أحس بطعم سكر عند الدوخة', 'ar')
    assert 'طعم حلو' in answer
    assert 'الدوخة' in answer


def test_assistant_route_uses_local_fallback_and_symptom_chip():
    _, source = _load_helper()
    assert '_assistant_local_mental_answer(last_text, lang)' in source
    assert '_assistant_local_health_answer(last_text, lang)' in source
    assert '"دوخة", "دوار", "غثيان", "تنميل"' in source
