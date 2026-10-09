import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_public_trust_page_and_snapshot_route_exist():
    src = source_bundle.webapp_text()
    assert "@app.route('/trust')" in src
    assert "@app.route('/api/trust-snapshot'" in src
    assert 'def _public_trust_snapshot()' in src
    assert 'Why trust this system?' in src or 'لماذا نثق بهذا النظام؟' in src


def test_home_page_links_to_trust_and_body_map_demo():
    src = source_bundle.webapp_text()
    assert '/trust' in src
    # Body map is intentionally embedded only inside the symptom-analysis flow.
    home_start = src.index('<section class="ss-home-hero"')
    home_end = src.index('</main>', home_start)
    assert '/chat?bodymap=1' not in src[home_start:home_end]


def test_chat_supports_body_map_quick_demo_mode_and_micro_animation():
    src = source_bundle.chat_view_text()
    web = source_bundle.webapp_text()
    assert 'symptom-bodymap-disclosure' in src
    assert 'استخدام خريطة الجسم' in src
    assert 'Use the body map' in src or 'استخدام خريطة الجسم' in src
    assert 'smartBodyFlash' in web
    assert 'smart-body-part.pulse' in web


def test_trust_snapshot_minimizes_public_operational_metadata():
    src = source_bundle.webapp_text()
    block = src[src.index('def _public_trust_snapshot():'):src.index("@app.route('/api/trust-snapshot'", src.index('def _public_trust_snapshot():'))]
    assert "'admin_accounts'" not in block
    assert "'database_backend'" not in block
    assert "'passkey_credentials'" not in block
    assert "'breakdown': user_generated_breakdown" not in block


def test_trust_page_uses_defined_html_escape_and_body_animation_preserves_positioning():
    src = source_bundle.webapp_text()
    trust = src[src.index("@app.route('/trust')"):src.index('@app.route("/methodology")')]
    assert "html_lib.escape(snap['generated_at'])" in trust
    assert "__DB__" not in trust
    assert '@keyframes smartBodyPulse{0%{box-shadow:' in src
    assert '@keyframes smartBodyPulse{0%{transform:' not in src
    assert '@media(prefers-reduced-motion:reduce){.smart-body-stage.flash' in src
