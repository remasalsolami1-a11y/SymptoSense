import source_bundle
import versioning
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()
DASH = (ROOT / 'dashboard.py').read_text(encoding='utf-8')
OFF = (ROOT / 'static/css/offline.css').read_text(encoding='utf-8')
SW = (ROOT / 'service-worker.js').read_text(encoding='utf-8')
RC = (ROOT / 'release_candidate.py').read_text(encoding='utf-8')


def test_exact_small_device_breakpoints_are_covered():
    for bp in ('430px', '390px', '375px', '320px'):
        assert f'max-width:{bp}' in WEB.replace(' ', '')
        assert f'max-width:{bp}' in DASH.replace(' ', '')
        assert f'max-width:{bp}' in OFF.replace(' ', '')


def test_public_typography_contract_is_unified():
    assert "'Tajawal','Segoe UI',Tahoma,sans-serif" in WEB
    assert "'Poppins','Tajawal','Segoe UI',sans-serif" in WEB
    assert "'Amiri'" not in WEB
    assert 'Inter,system-ui' not in OFF
    assert "font-family:'Poppins','Tajawal','Segoe UI',sans-serif" in DASH


def test_trust_center_is_compact_and_plain_language():
    for text in ('كيف يحافظ SymptoSense على سلامتك؟', 'إذا ظهرت علامة خطر', 'الخصوصية باختصار', 'ما الذي لا يفعله SymptoSense؟'):
        assert text in WEB
    assert 'trust-simple-grid' in WEB
    assert 'trust-more' in WEB


def test_admin_overview_is_simplified_and_perf_moves_to_readiness():
    overview = DASH.index('id="view-overview"')
    production = DASH.index('id="view-production"')
    perf = DASH.index('id="databasePerformanceCard"')
    assert not (overview < perf < production)
    assert perf > production
    assert 'المؤشرات الأهم فقط: الاستخدام، قوة المعرفة، سلامة المحتوى، والتقييمات.' in DASH


def test_release_and_cache_are_v66():
    assert versioning.APP_VERSION == __import__("release_candidate").APP_VERSION
    assert versioning.RC_ID == __import__("release_candidate").RC_ID
    assert versioning.SW_CACHE in SW
