import source_bundle
import sys, types
from pathlib import Path

ROOT=Path(__file__).resolve().parent
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
try:
    import groq  # noqa
except Exception:
    mod=types.ModuleType('groq')
    class Groq: pass
    mod.Groq=Groq
    sys.modules['groq']=mod

import analysis_core
import v52_signature


def test_judge_challenge_has_five_synthetic_scenarios_and_four_paths():
    rows=v52_signature.CHALLENGE_SCENARIOS
    assert len(rows)==5
    actual={v52_signature.evaluate_scenario(r['id'],'','ar')['actual'] for r in rows}
    assert {'emergency','review','monitor','clarify'} <= actual


def test_judge_challenge_does_not_persist_or_claim_clinical_validation():
    src=(ROOT/'v52_signature.py').read_text(encoding='utf-8')
    assert 'analysis_core.run_analysis' not in src
    assert 'clinical validation' in src or 'تحققًا سريريًا' in src
    assert '/api/admin/judge-challenge/evaluate' in src


def test_sudden_limb_weakness_and_vision_loss_are_redundant_red_flags():
    assert analysis_core.detect_red_flags(['ضعف مفاجئ بالطرف'],'','ar')
    assert analysis_core.detect_red_flags(['فقدان مفاجئ للرؤية'],'','ar')
    assert analysis_core.detect_red_flags(['sudden vision loss'],'','en')


def test_offline_safety_capsule_is_cached_and_privacy_safe():
    sw=(ROOT/'service-worker.js').read_text(encoding='utf-8')
    offline=(ROOT/'offline.html').read_text(encoding='utf-8')
    web=source_bundle.webapp_text()
    # The former /offline-safety page was consolidated into the single static
    # /offline safety page. Navigation falls back to this cached page.
    assert "'/offline'" in sw and "caches.match('/offline')" in sw
    assert '@app.route("/offline")' in web
    assert '997' in offline and '937' in offline
    assert 'التحليل الكامل والمساعد الذكي غير متاحين' in offline
    assert 'لا يخزن نسخة من محادثاتك أو تحليلاتك الصحية' in offline
    assert 'localStorage' not in offline and 'indexedDB' not in offline


def test_judge_challenge_is_admin_only_in_navigation_and_routes():
    web=source_bundle.webapp_text()
    mod=(ROOT/'judge_challenge.py').read_text(encoding='utf-8')
    assert 'import judge_challenge' in web
    assert '@app.route("/admin/judge-challenge")' in web
    assert '_admin_page_gate("/admin/judge-challenge")' in web
    assert '@app.route("/api/admin/judge-challenge/run", methods=["POST"])' in web
    assert '@admin_api_required("analytics")' in web
    assert 'Not clinical validation' in mod
