import source_bundle
import versioning
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _run(tmp_path, code):
    env = os.environ.copy()
    env.pop("DATABASE_URL", None)
    env["DB_PATH"] = str(tmp_path / "v227-drug-summary.db")
    env["DRUG_ARABIC_SUMMARY_ENABLED"] = "1"
    cp = subprocess.run(
        [sys.executable, "-c", code], cwd=str(ROOT), env=env,
        capture_output=True, text=True, timeout=30,
    )
    assert cp.returncode == 0, cp.stdout + "\n" + cp.stderr


def test_arabic_external_result_uses_grounded_generated_summary_and_caches(tmp_path):
    code = r'''
import external_drug_lookup as e
source={
 'external':True,'query':'ExampleDrug','name_en':'ExampleDrug','name_ar':'ExampleDrug','generic_name':'examplegeneric',
 'uses_en':'Used for allergic eye itching. A second long sentence that should not be dumped verbatim forever.',
 'warning_en':'Do not touch the dropper tip to the eye or surrounding surfaces. Remove contact lenses before use.',
 'interact_en':'No structured drug interaction section was returned.',
}
e._generate_arabic_summary=lambda r:{
 'uses_ar':'يُستخدم للمساعدة في الوقاية من الحكة المرتبطة بحساسية العين.',
 'warning_ar':'تجنب ملامسة طرف القطارة للعين أو الأسطح المحيطة، واتبع تعليمات النشرة بشأن العدسات اللاصقة.',
 'interact_ar':'لم تتوفر معلومات منظمة عن التداخلات في السجل المسترجع؛ راجع النشرة الرسمية أو الصيدلي.'
}
out=e.localize_external_result(source,'ar')
assert out['arabic_summary_status']=='generated'
assert 'يُستخدم' in out['uses_ar']
assert 'warning_ar_summary' in out
cached=e._cache_get('ExampleDrug')
assert cached and cached['uses_ar_summary']==out['uses_ar']
'''
    _run(tmp_path, code)


def test_cached_arabic_summary_skips_generator(tmp_path):
    code = r'''
import external_drug_lookup as e
source={
 'external':True,'query':'CachedArabic','name_en':'X','name_ar':'X','generic_name':'x',
 'uses_en':'English use.','warning_en':'English warning.','interact_en':'English interaction.',
 'uses_ar_summary':'استخدام عربي موثق.','warning_ar_summary':'تحذير عربي موثق.','interact_ar_summary':'تداخل عربي موثق.'
}
def fail(*a,**k): raise AssertionError('generator should not run')
e._generate_arabic_summary=fail
out=e.localize_external_result(source,'ar')
assert out['arabic_summary_status']=='cached'
assert out['uses_ar']=='استخدام عربي موثق.'
'''
    _run(tmp_path, code)


def test_arabic_page_never_silently_dumps_english_if_summary_unavailable(tmp_path):
    code = r'''
import external_drug_lookup as e
source={
 'external':True,'query':'NoTranslate','name_en':'X','name_ar':'X','generic_name':'x',
 'uses_en':'THIS IS AN ENGLISH USE PARAGRAPH.','warning_en':'THIS IS AN ENGLISH WARNING.','interact_en':'THIS IS AN ENGLISH INTERACTION.'
}
e._generate_arabic_summary=lambda r:None
out=e.localize_external_result(source,'ar')
assert out['arabic_summary_status']=='unavailable'
assert 'تعذر' in out['uses_ar'] and 'THIS IS' not in out['uses_ar']
assert 'تعذر' in out['warning_ar'] and 'THIS IS' not in out['warning_ar']
assert 'تعذر' in out['interact_ar'] and 'THIS IS' not in out['interact_ar']
'''
    _run(tmp_path, code)


def test_english_external_result_is_compact_not_full_label_dump(tmp_path):
    code = r'''
import external_drug_lookup as e
long='Sentence one. '+('Very long label content without useful UI breaks. '*80)
source={'external':True,'uses_en':long,'warning_en':long,'interact_en':long}
out=e.localize_external_result(source,'en')
assert len(out['uses_en']) <= 520
assert len(out['warning_en']) <= 620
assert len(out['interact_en']) <= 520
'''
    _run(tmp_path, code)


def test_drug_api_localizes_only_external_results_and_exposes_status():
    text=source_bundle.webapp_text()
    route=source_bundle.between('@app.route("/api/drug")', '@app.route("/api/tip")')
    assert 'if source_kind == "external"' in route
    assert 'external_drug_lookup.localize_external_result(d, lang)' in route
    assert '"arabic_summary_status"' in route


def test_arabic_ui_discloses_translation_and_has_safe_fallback():
    text=source_bundle.webapp_text()
    assert 'تم تلخيص وترجمة معلومات النشرة الرسمية إلى العربية لتسهيل القراءة' in text
    assert 'لم نعرض ترجمة غير متحقق منها' in text
    assert '.med-lang-note{' in text


def test_version_227_metadata_is_consistent():
    env=(ROOT/'.env.example').read_text(encoding='utf-8')
    rc=(ROOT/'release_candidate.py').read_text(encoding='utf-8')
    rs=(ROOT/'research_study.py').read_text(encoding='utf-8')
    sw=(ROOT/'service-worker.js').read_text(encoding='utf-8')
    assert "APP_VERSION=" + versioning.APP_VERSION in env
    assert versioning.APP_VERSION == __import__("release_candidate").APP_VERSION
    assert versioning.SW_CACHE in sw
