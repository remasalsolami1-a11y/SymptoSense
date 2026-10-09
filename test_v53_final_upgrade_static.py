import source_bundle
import versioning
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()
SEC = (ROOT / 'web_security.py').read_text(encoding='utf-8')
DASH = (ROOT / 'dashboard.py').read_text(encoding='utf-8')
CHAT = source_bundle.chat_view_text()
READY = (ROOT / 'production_readiness.py').read_text(encoding='utf-8')
BRIDGE = (ROOT / 'static' / 'js' / 'interaction-bridge.js').read_text(encoding='utf-8')
SW = (ROOT / 'service-worker.js').read_text(encoding='utf-8')


def test_admin_primary_navigation_is_intentionally_small():
    views = set(re.findall(r'data-view="([^"]+)"', DASH))
    assert views == {'overview', 'analytics', 'users', 'knowledge', 'production', 'adminsettings', 'contentgaps', 'quality'}


def test_admin_and_home_surface_source_growth_and_strength():
    assert 'recent_source_additions' in WEB
    assert 'معرفة صحية تستند إلى مصادر موثوقة' in WEB
    assert 'projectStrengthStats' in DASH
    assert 'مصادر قوية أضيفت مؤخرًا' in DASH
    assert 'knowledgeQuality' in DASH
    assert 'source_coverage_pct' in DASH


def test_password_only_admin_policy_does_not_create_2fa_warning():
    assert 'if admin_2fa.required()' in READY
    assert 'ADMIN_2FA_REQUIRED=0' in READY


def test_fhir_is_not_in_user_account_dropdown():
    account_block = WEB[WEB.index("<details class=\"dd account-dd account-native\""):WEB.index("</details>", WEB.index("<details class=\"dd account-dd account-native\""))]
    assert 'FHIR' not in account_block
    assert '/fhir' not in account_block.lower()


def test_body_map_is_inside_symptom_flow_only():
    assert 'symptom-bodymap-disclosure' in CHAT
    assert 'استخدام خريطة الجسم' in CHAT
    # The home page no longer advertises the body map as a separate entry point.
    home_start = WEB.index('<section class="ss-home-hero"')
    home_end = WEB.index('</main>', home_start)
    assert 'bodymap=1' not in WEB[home_start:home_end]


def test_emergency_continue_button_has_direct_listener_and_renders_result():
    # V251: leaving the emergency overlay now needs an explicit second confirmation.
    assert "yesBtn.addEventListener('click', closeEmergency)" in CHAT
    assert 'renderResult(resultToShow)' in CHAT


def test_legacy_inline_handlers_are_supported_under_csp_bridge():
    assert "'toggleDD'" in BRIDGE
    assert "'editField'" in BRIDGE
    assert "script-src-attr 'none'" in SEC


def test_service_worker_has_current_cache_generation():
    assert versioning.SW_CACHE in SW
    assert "url.pathname.startsWith('/static/')" in SW
    assert versioning.SW_CACHE in SW


def test_project_has_git_and_docker_hygiene_files():
    assert (ROOT / '.gitignore').exists()
    assert (ROOT / '.dockerignore').exists()
