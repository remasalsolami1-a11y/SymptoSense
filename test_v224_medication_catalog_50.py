import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _run_fresh_db(tmp_path, code):
    env = os.environ.copy()
    env.pop('DATABASE_URL', None)
    env['DB_PATH'] = str(tmp_path / 'v224-medications.db')
    cp = subprocess.run(
        [sys.executable, '-c', code], cwd=str(ROOT), env=env,
        capture_output=True, text=True, timeout=90,
    )
    assert cp.returncode == 0, cp.stdout + '\n' + cp.stderr


def test_catalog_contains_exactly_50_curated_bilingual_medications(tmp_path):
    code = r'''
import medication_warnings as m
assert len(m.MEDICATIONS) == 50, len(m.MEDICATIONS)
assert len(m.MEDICATION_SOURCES) == 50, len(m.MEDICATION_SOURCES)
for slug, entry in m.MEDICATIONS.items():
    name_ar, name_en, aliases, warn_ar, warn_en, uses_ar, uses_en, ia, ie = m._unpack(entry)
    assert name_ar.strip() and name_en.strip(), slug
    assert any(any('\u0600' <= ch <= '\u06ff' for ch in str(a)) for a in aliases), slug
    assert any(any('a' <= ch.lower() <= 'z' for ch in str(a)) for a in aliases), slug
    assert warn_ar.strip() and warn_en.strip() and uses_ar.strip() and uses_en.strip(), slug
    result = m.lookup_drug(name_en)
    assert result is not None, (slug, name_en)
    assert result['slug'] == slug, (slug, result['slug'])
    policy = result['source_policy']
    assert policy['ok'] is True, (slug, policy)
    assert policy['has_local'] is True, slug
    assert policy['clinical_provider_count'] >= 2, (slug, policy)
'''
    _run_fresh_db(tmp_path, code)


def test_common_arabic_english_brand_aliases_resolve(tmp_path):
    code = r'''
import medication_warnings as m
checks = {
    'كونكور': 'bisoprolol', 'Concor': 'bisoprolol',
    'أوزمبيك': 'semaglutide', 'Ozempic': 'semaglutide',
    'مونجارو': 'tirzepatide', 'Mounjaro': 'tirzepatide',
    'إليكويس': 'apixaban', 'Eliquis': 'apixaban',
    'سيبرالكس': 'escitalopram', 'Cipralex': 'escitalopram',
    'زينات': 'cefuroxime', 'Zinnat': 'cefuroxime',
    'فنتولين': 'salbutamol', 'Ventolin': 'salbutamol',
    'كريستور': 'rosuvastatin', 'Crestor': 'rosuvastatin',
    'جارديانس': 'empagliflozin', 'Jardiance': 'empagliflozin',
    'ليريكا': 'pregabalin', 'Lyrica': 'pregabalin',
}
for query, slug in checks.items():
    result = m.lookup_drug(query)
    assert result is not None, query
    assert result['slug'] == slug, (query, result['slug'], slug)
'''
    _run_fresh_db(tmp_path, code)
