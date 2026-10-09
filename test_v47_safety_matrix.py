import json, sys, types
from pathlib import Path

ROOT=Path(__file__).resolve().parent
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
try:
    import groq  # noqa
except Exception:
    mod=types.ModuleType('groq')
    class Groq: pass
    mod.Groq=Groq; sys.modules['groq']=mod

import analysis_core

CASES=json.loads((ROOT/'runtime_data/safety_cases.json').read_text(encoding='utf-8'))

def test_safety_matrix_red_flags_are_stable():
    for case in CASES:
        flags=analysis_core.detect_red_flags(case['symptoms'],case.get('notes',''),case['lang'])
        assert bool(flags) is bool(case['expect_red_flag']), (case['id'],flags)

def test_negation_does_not_turn_into_emergency_signal():
    assert analysis_core.detect_red_flags(['صداع'],'لا يوجد ألم شديد في الصدر','ar') == []
    assert analysis_core.detect_red_flags(['headache'],'no severe chest pain','en') == []

def test_urgent_combination_rule_remains_active():
    assert analysis_core._rule_urgency(['chest pain','shortness of breath'],3,40) == 'high'
