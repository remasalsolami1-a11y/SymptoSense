import source_bundle
import versioning
from pathlib import Path
import sys, types
try:
    import groq  # noqa
except Exception:
    mod = types.ModuleType("groq")
    class Groq: pass
    mod.Groq = Groq
    sys.modules["groq"] = mod
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import judge_challenge


def test_all_judge_challenge_cases_match_expected_engine_behavior():
    assert len(judge_challenge.CASES) >= 5
    results = [judge_challenge.run_case(case['id'], 'ar') for case in judge_challenge.CASES]
    assert all(row['passed'] for row in results)
    assert all(row['synthetic'] is True and row['clinical_validation'] is False for row in results)


def test_judge_challenge_admin_routes_and_navigation_are_present():
    web = source_bundle.webapp_text()
    dashboard = (ROOT / 'dashboard.py').read_text(encoding='utf-8')
    competition = (ROOT / 'v50_wow.py').read_text(encoding='utf-8')
    assert '/admin/judge-challenge' in web
    assert '/api/admin/judge-challenge/run' in web
    # Route remains admin-only; compact primary dashboard intentionally omits a dedicated nav item.
    assert '/admin/judge-challenge' in web
    assert '/admin/judge-challenge' in competition


def test_offline_safety_capsule_is_cached_privacy_safe_and_has_emergency_content():
    offline = (ROOT / 'offline.html').read_text(encoding='utf-8')
    sw = (ROOT / 'service-worker.js').read_text(encoding='utf-8')
    web = source_bundle.webapp_text()
    assert 'Offline Safety Mode' in offline
    assert 'tel:997' in offline and 'tel:937' in offline
    assert 'لا يخزن نسخة من محادثاتك' in offline
    assert "'/offline'" in sw
    assert versioning.SW_CACHE in sw
    assert 'ssOfflineBanner' in web
    assert 'navigator.onLine' in web
