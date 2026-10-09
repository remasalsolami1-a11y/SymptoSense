import source_bundle
import versioning
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parent
WEB=source_bundle.webapp_text()
DOCKER=(ROOT/'Dockerfile').read_text(encoding='utf-8')
SW=(ROOT/'service-worker.js').read_text(encoding='utf-8')
CHAT=source_bundle.chat_view_text()
OFF=(ROOT/'offline.html').read_text(encoding='utf-8')

def test_safeid_action_buttons_are_non_submit_buttons():
    for bid in ('sidRotate','sidToggle','sidSave'):
        m=re.search(r'<button[^>]*\bid="'+bid+r'"[^>]*>',WEB)
        assert m, bid
        assert re.search(r'\btype="button"',m.group(0)),m.group(0)

def test_flat_deploy_rebuilds_static_asset_directories():
    for token in ('mkdir -p static/js static/css static/images icons',
                  'interaction-bridge.js manage-profile.js mini-charts.js offline.js static/js/',
                  'design-system.css offline.css v83_user_tools.css app-shell-v111.css static/css/'):
        assert token in DOCKER

def test_required_browser_assets_exist_at_served_paths():
    paths=[
      'static/js/interaction-bridge.js','static/js/manage-profile.js','static/js/mini-charts.js','static/js/offline.js',
      'static/css/design-system.css','static/css/offline.css','static/css/v83_user_tools.css',
      'static/images/symptosense-social-preview.png','static/images/safeid-add-to-phone-guide.png',
      'icons/icon-192.png','icons/icon-512.png','icons/apple-touch-icon.png'
    ]
    for rel in paths: assert (ROOT/rel).is_file(), rel

def test_asset_cache_revision_is_bumped():
    assert 'STATIC_ASSET_VERSION = f"{release_candidate.APP_VERSION}-193"' in WEB
    assert '/static/js/manage-profile.js?v=263' in WEB
    assert '/static/css/v83_user_tools.css?v=193' in CHAT
    assert versioning.SW_CACHE in SW
    assert '/static/css/offline.css?v=193' in OFF
    assert '/static/js/offline.js?v=193' in OFF
