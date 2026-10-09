import source_bundle
import versioning
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()
BRIDGE = (ROOT / 'static/js/interaction-bridge.js').read_text(encoding='utf-8')
RC = (ROOT / 'release_candidate.py').read_text(encoding='utf-8')
SW = (ROOT / 'service-worker.js').read_text(encoding='utf-8')
ENV = (ROOT / '.env.example').read_text(encoding='utf-8')
STUDY = (ROOT / 'research_study.py').read_text(encoding='utf-8')


def test_pwa_banner_no_longer_covers_desktop_hero_ctas():
    assert '@media (min-width: 900px) {' in WEB
    assert '.pwa-install { left: 22px; right: auto; bottom: 22px; transform: none;' in WEB
    assert '[dir="rtl"] .pwa-install { left: 22px; right: auto; }' in WEB


def test_core_global_controls_use_direct_event_listeners():
    for token in (
        "installBtn.addEventListener('click'",
        "laterBtn.addEventListener('click'",
        '(function bindGlobalAssistantControls()',
        "bindClick('asstFab'",
        "bindClick('asstBack'",
        "bindClick('asstCloseBtn'",
        "bindClick('explCloseBtn'",
        "bindClick('exAssist'",
        "bindClick('asstModalCloseBtn'",
        '(function bindSmartContextControls()',
    ):
        assert token in WEB


def test_core_global_controls_do_not_depend_on_inline_onclick():
    ids = ['pwaInstallBtn','pwaLaterBtn','asstFab','asstBack','asstCloseBtn','explCloseBtn','exAssist','asstModalCloseBtn','smartCtxUse','smartCtxManual','smartCtxSkip']
    for bid in ids:
        m = re.search(r'<(?:button|div|a)\b[^>]*\bid=["\']'+re.escape(bid)+r'["\'][^>]*>', WEB, re.I|re.S)
        assert m, bid
        assert 'onclick=' not in m.group(0).lower(), (bid, m.group(0))


def test_interaction_bridge_watches_dynamically_inserted_legacy_controls():
    assert 'new MutationObserver' in BRIDGE
    assert 'record.addedNodes.forEach(scan)' in BRIDGE
    assert 'attributeFilter: Object.keys(EVENT_ATTRS)' in BRIDGE


def test_release_metadata_is_v71_everywhere():
    assert versioning.APP_VERSION == __import__("release_candidate").APP_VERSION
    assert versioning.RC_ID == __import__("release_candidate").RC_ID
    assert "APP_VERSION=" + versioning.APP_VERSION in ENV
    assert "RELEASE_CANDIDATE_ID=" + versioning.RC_ID in ENV
    assert versioning.APP_VERSION == __import__("research_study").APP_VERSION
    assert versioning.SW_CACHE in SW


def test_full_interaction_audit_tool_is_shipped():
    tool = (ROOT / 'tools/full_interaction_audit.py').read_text(encoding='utf-8')
    assert 'FULL INTERACTION AUDIT:' in tool
    assert 'button has no detectable action binding' in tool
    assert 'internal href has no GET route' in tool
    assert 'fetch target/method has no route' in tool
