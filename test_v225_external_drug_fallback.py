import source_bundle
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _run(tmp_path, code):
    env = os.environ.copy()
    env.pop("DATABASE_URL", None)
    env["DB_PATH"] = str(tmp_path / "v225-external-drug.db")
    env["EXTERNAL_DRUG_LOOKUP_ENABLED"] = "1"
    cp = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=30,
    )
    assert cp.returncode == 0, cp.stdout + "\n" + cp.stderr


def test_external_lookup_requires_official_label_and_builds_safe_result(tmp_path):
    code = r'''
import external_drug_lookup as e
calls=[]
def fake(base, params):
    calls.append((base, dict(params)))
    if 'rxnav.nlm.nih.gov' in base:
        return {'drugGroup': {'conceptGroup': []}}
    if 'api.fda.gov' in base:
        return {'results': [{
            'openfda': {'brand_name':['ExampleBrand'], 'generic_name':['examplegeneric']},
            'indications_and_usage':['Used for an example indication.'],
            'warnings':['Important example warning.'],
            'drug_interactions':['Example interaction section.'],
        }]}
    raise AssertionError(base)
e._http_json=fake
r=e.lookup_external_drug('ExampleBrand')
assert r is not None
assert r['external'] is True
assert r['name_en']=='ExampleBrand'
assert r['generic_name']=='examplegeneric'
assert r['source_policy']['official_label'] is True
assert any(x['provider']=='openFDA' for x in r['sources'])
assert any(x['provider']=='DailyMed' for x in r['sources'])
'''
    _run(tmp_path, code)


def test_rxnorm_is_used_only_to_retry_identity_when_direct_label_lookup_misses(tmp_path):
    code = r'''
import external_drug_lookup as e
fda_calls=[]
def fake(base, params):
    if base==e.RXNORM_DRUGS_URL:
        return {'drugGroup': {'conceptGroup': [{'tty':'SBD','conceptProperties':[{'name':'Canonical Drug','rxcui':'123'}]}]}}
    if base==e.OPENFDA_LABEL_URL:
        fda_calls.append(params['search'])
        if 'Canonical Drug' in params['search']:
            return {'results':[{'openfda':{'brand_name':['Canonical Drug'],'generic_name':['generic x']},'warnings':['warning']} ]}
        return None
    raise AssertionError((base,params))
e._http_json=fake
r=e.lookup_external_drug('BrandTypo')
assert r is not None
assert r['matched_term']=='Canonical Drug'
assert len(fda_calls)==2
'''
    _run(tmp_path, code)


def test_no_official_label_means_no_result_instead_of_guessing(tmp_path):
    code = r'''
import external_drug_lookup as e
def fake(base, params):
    if base==e.RXNORM_DRUGS_URL:
        return {'drugGroup': {'conceptGroup': []}}
    if base==e.RXNORM_APPROX_URL:
        return {'approximateGroup': {'candidate': []}}
    if base==e.OPENFDA_LABEL_URL:
        return None
    raise AssertionError(base)
e._http_json=fake
assert e.lookup_external_drug('unknown-medicine-xyz') is None
'''
    _run(tmp_path, code)


def test_successful_external_result_is_cached_and_skips_second_network_lookup(tmp_path):
    code = r'''
import external_drug_lookup as e
count={'n':0}
def fake(base, params):
    count['n']+=1
    if base==e.RXNORM_DRUGS_URL:
        return {'drugGroup': {'conceptGroup': []}}
    if base==e.OPENFDA_LABEL_URL:
        return {'results':[{'openfda':{'generic_name':['cachedgeneric']},'warnings':['cached warning']} ]}
    raise AssertionError(base)
e._http_json=fake
r1=e.lookup_external_drug('CacheDrug')
first=count['n']
assert r1 is not None and first>=1
def fail(*a,**k):
    raise AssertionError('network should not be used on cache hit')
e._http_json=fail
r2=e.lookup_external_drug('CacheDrug')
assert r2 is not None and r2['cache_hit'] is True
'''
    _run(tmp_path, code)



def test_miss_is_cached_briefly_to_avoid_repeated_external_calls(tmp_path):
    code = r'''
import external_drug_lookup as e
count={'n':0}
def fake(base, params):
    count['n']+=1
    if base==e.OPENFDA_LABEL_URL:
        return None
    if base==e.RXNORM_DRUGS_URL:
        return {'drugGroup': {'conceptGroup': []}}
    if base==e.RXNORM_APPROX_URL:
        return {'approximateGroup': {'candidate': []}}
    raise AssertionError(base)
e._http_json=fake
assert e.lookup_external_drug('NoSuchDrugXYZ') is None
first=count['n']
assert first>=1
def fail(*a,**k):
    raise AssertionError('network should not repeat during miss cache TTL')
e._http_json=fail
assert e.lookup_external_drug('NoSuchDrugXYZ') is None
'''
    _run(tmp_path, code)

def test_webapp_keeps_local_first_and_only_then_external_fallback():
    text=source_bundle.webapp_text()
    route=source_bundle.between('@app.route("/api/drug")', '@app.route("/api/tip")')
    assert route.index('medication_warnings.lookup_drug(name)') < route.index('external_drug_lookup.lookup_external_drug(name)')
    assert 'len(name) > 120' in route
    assert 'source_kind = "external"' in route


def test_meds_ui_discloses_external_source_and_does_not_claim_unverified_information():
    text=source_bundle.webapp_text()
    assert 'تم جلب هذه المعلومات من مصدر دوائي خارجي موثوق' in text
    assert 'لن نعرض معلومات غير متحقق منها' in text
    assert 'ابحث بالاسم التجاري أو العلمي، بالعربي أو الإنجليزي' in text
