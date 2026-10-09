"""Regression coverage for defensive Telegram callback parsing.

This test extracts only the pure callback parser from bot.py so it can run
without requiring Telegram/Groq runtime dependencies in a lightweight QA env.
"""
import ast
from pathlib import Path


def _load_callback_choice():
    source = Path("bot.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_callback_choice"
    )
    namespace = {}
    module = ast.Module(body=[function], type_ignores=[])
    exec(compile(module, "<callback-choice>", "exec"), namespace)
    return namespace["_callback_choice"]


def test_callback_choice_accepts_valid_indexes_only():
    choose = _load_callback_choice()
    options = ["first", "second", "third"]
    assert choose("sym_0", "sym_", options) == "first"
    assert choose("sym_2", "sym_", options) == "third"


def test_callback_choice_rejects_malformed_or_stale_data():
    choose = _load_callback_choice()
    options = ["first", "second", "third"]
    for data in ("sym_", "sym_abc", "sym_-1", "sym_3", "sym_999", "dur_1", None):
        assert choose(data, "sym_", options) is None


def test_callback_branches_use_defensive_parser():
    source = Path("bot.py").read_text(encoding="utf-8")
    assert '_callback_choice(data, "sym_", _flat_syms(tx))' in source
    assert '_callback_choice(data, "dur_", opts)' in source
    assert '_callback_choice(data, "sev_", opts)' in source
    assert '_callback_choice(data, "cond_", _flat_conds(tx))' in source
    for unsafe in ("_flat_syms(tx)[int(data[4:])]", "opts[int(data[4:])]", "_flat_conds(tx)[int(data[5:])]" ):
        assert unsafe not in source
