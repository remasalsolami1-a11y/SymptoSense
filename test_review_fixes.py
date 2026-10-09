"""Regressions for bugs found in the code review (V263.2)."""
import ast
import re
from pathlib import Path

import pytest

import blood_test
from routes import _inject

ROOT = Path(__file__).resolve().parent


def test_b12_value_of_12_with_a_unit_is_not_silently_dropped():
    """A dead regex (literal backspace characters instead of \\b) made the unit check never match."""
    rows, _ = blood_test._parse_blood_text_v142("Vitamin B12 12.0 pg/mL")
    assert [(r["key"], r["value"], r["unit"]) for r in rows] == [("b12", 12.0, "pg/mL")]


def test_b12_12_without_any_unit_is_still_treated_as_the_test_name_noise():
    rows, _ = blood_test._parse_blood_text_v142("Vitamin B12")
    assert rows == []


def test_no_control_characters_inside_source_regexes():
    for path in list(ROOT.glob("*.py")) + list((ROOT / "routes").glob("*.py")) + list((ROOT / "pagelib").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        bad = [m.start() for m in re.finditer(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", text)]
        assert not bad, "%s has a raw control character at offset %s (use an escape like \\b)" % (path.name, bad[:3])


def test_route_modules_do_not_use_eval():
    for path in (ROOT / "routes").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", "") in {"eval", "exec"}]
        assert not calls, path.name


def test_wrapper_resolver_accepts_only_names_and_literal_calls():
    ns = {"plain": lambda f: f, "needs": lambda scope: (lambda f: (scope, f))}
    assert _inject.resolve_wrapper("plain", ns) is ns["plain"]
    assert _inject.resolve_wrapper('needs("analytics")', ns)("view") == ("analytics", "view")
    for bad in ('__import__("os").system("x")', "plain.__class__", "needs(open('x'))", "needs(scope='a')", "lambda f: f"):
        with pytest.raises((ValueError, SyntaxError, KeyError)):
            _inject.resolve_wrapper(bad, ns)


def test_progress_timer_is_declared_once_and_shared_with_the_emergency_screen():
    js = {p.name: p.read_text(encoding="utf-8") for p in (ROOT / "static/js/chat").glob("*.js")}
    declared = [n for n, t in js.items() if re.search(r"\blet progressTimer\b", t)]
    assert declared == ["chat-core.js"], declared                      # a second `let` would shadow it and re-break red-flags.js
    assert "clearTimeout(progressTimer)" in js["red-flags.js"]


def test_bridge_checks_the_key_filter_before_preventing_default():
    text = (ROOT / "static/js/interaction-bridge.js").read_text(encoding="utf-8")
    assert text.index("event.key !== key") < text.index("el.hasAttribute('data-ss-prevent')")
    assert (ROOT / "interaction-bridge.js").read_text(encoding="utf-8") == text


@pytest.mark.parametrize("text,key,unit", [
    ("Vitamin D 25-OH 25 nmol/L", "vitd", "nmol/L"), ("Vitamin B12 250 pmol/L", "b12", "pmol/L"),
    ("Free T4 14 pmol/L", "free_t4", "pmol/L"), ("Folate 20 nmol/L", "folate", "nmol/L")])
def test_si_units_are_labelled_correctly_and_classification_is_unchanged(text, key, unit):
    """nmol/L and pmol/L used to be read as the hematocrit unit L/L (substring match). Only the LABEL changes here:
    these markers stay 'unclassified' exactly as before, so no medical decision moves without clinical sign-off."""
    rows, _ = blood_test.parse_blood_text(text)
    assert [(r["key"], r["unit"]) for r in rows] == [(key, unit)]
    results = blood_test.analyze_blood(rows, "female", 30)[0]
    assert [(r["key"], r["unit"], r["status"]) for r in results] == [(key, unit, "unclassified")]


class _FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


def test_medlineplus_xml_is_parsed_with_defusedxml(monkeypatch):
    import medical_source_pipeline as msp
    good = ('<nlmSearchResult><list><document url="https://medlineplus.gov/x.html">'
            '<content name="title">Headache</content><content name="snippet">Info</content></document></list></nlmSearchResult>')
    monkeypatch.setattr(msp.requests, "get", lambda *a, **k: _FakeResponse(good))
    assert msp.medlineplus_search("headache") == [
        {"url": "https://medlineplus.gov/x.html", "title": "Headache", "snippet": "Info", "provider": "MedlinePlus"}]
    bomb = ('<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">]>'
            "<r>&b;</r>")
    monkeypatch.setattr(msp.requests, "get", lambda *a, **k: _FakeResponse(bomb))
    with pytest.raises(Exception) as err:
        msp.medlineplus_search("x")
    assert "ntit" in type(err.value).__name__                           # defusedxml.EntitiesForbidden


def test_defusedxml_is_a_declared_dependency_and_stdlib_xml_is_not_used_on_network_data():
    assert "defusedxml" in (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "xml.etree" not in (ROOT / "medical_source_pipeline.py").read_text(encoding="utf-8")


def test_no_duplicate_dict_keys_in_page_text_tables():
    import subprocess, sys, shutil
    ruff = shutil.which("ruff")
    if not ruff:
        pytest.skip("ruff not installed")
    out = subprocess.run([ruff, "check", "--select", "F601", "--no-cache", "pagelib", "routes", "services"], cwd=ROOT,
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stdout
