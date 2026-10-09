import source_bundle
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import blood_test


def test_cbc_uses_lab_reference_and_preserves_gl_units():
    entries, age = blood_test.parse_blood_text('HGB | 130 | g/L | 130 | 170')
    assert age is None
    assert entries[0]['unit'] == 'g/L'
    results, *_ = blood_test.analyze_blood(entries, gender='m', age=30)
    r = results[0]
    assert r['status'] == 'normal'
    assert r['reference_source'] == 'lab_reference'
    assert r['canonical_value'] == 13.0


def test_cbc_hct_fraction_converts_to_percent():
    entries, _ = blood_test.parse_blood_text('HCT | 0.40 | L/L | |')
    results, *_ = blood_test.analyze_blood(entries, gender='f', age=30)
    assert results[0]['value'] == 40.0
    assert results[0]['unit'] == '%'
    # V145+ keeps the unit conversion but deliberately refuses to classify
    # against an app-wide adult fallback when the uploaded report has no
    # laboratory reference range. This is safer than presenting a guessed
    # normal/high/low label as if it came from the user's lab.
    assert results[0]['status'] == 'unclassified'
    assert results[0]['verification_level'] == 'needs_review'


def test_cbc_ambiguous_neutrophils_without_unit_not_misclassified():
    results, *_ = blood_test.analyze_blood([('neut', 5.0)], gender='f', age=30)
    assert results[0]['status'] == 'unclassified'


def test_cbc_child_without_lab_range_does_not_use_adult_range():
    entries, _ = blood_test.parse_blood_text('HGB | 11.5 | g/dL | |')
    results, *_ = blood_test.analyze_blood(entries, gender='f', age=7)
    assert results[0]['status'] == 'unclassified'


def test_no_deprecated_groq_models_left_in_runtime_code():
    text = source_bundle.webapp_text() + (ROOT / 'bot.py').read_text()
    assert 'llama-3.2-90b-vision-preview' not in text
    assert 'model="llama-3.3-70b-versatile"' not in text
    assert 'GROQ_TEXT_MODEL' in text
    assert 'GROQ_VISION_MODEL' in text


def test_guest_analysis_is_ephemeral_in_source_contract():
    web = source_bundle.webapp_text()
    core = (ROOT / 'analysis_core.py').read_text()
    assert '"user_id": None if demo_mode else (("account-%s" % _ss_user_id()) if _ss_user_id() else None)' in web
    assert 'if user_id and str(user_id).startswith("account-")' in core


def test_login_does_not_expose_missing_account():
    dbtxt = (ROOT / 'db.py').read_text()
    assert 'if not row:\n            # Generic credentials response prevents account enumeration.\n            return {"ok": False, "error": "incorrect_credentials"}' in dbtxt


def test_local_alias_matcher_uses_phrase_boundaries():
    text = source_bundle.webapp_text()
    assert 'def _symptom_phrase_match' in text
    assert 're.escape(alias)' in text
    # Regression strings from the audit should no longer be matched by raw `alias in hay`.
    block = text[text.index('def _local_symptom_hits'):text.index('@app.route("/api/symptoms/extract"')]
    assert ' in hay for alias' not in block
