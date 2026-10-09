import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()
CHAT = source_bundle.chat_view_text()


def test_manifest_json_is_public_alias():
    assert '@app.route("/manifest.json")' in WEB
    assert '"/manifest.json"' in WEB
    assert '@app.route("/manifest.webmanifest")' in WEB


def test_manifest_launches_localized_routes():
    assert 'lang_prefix = f"/{lang_code}"' in WEB
    assert '"start_url": f"{lang_prefix}/?source=pwa"' in WEB
    assert 'f"{lang_prefix}/chat?source=pwa"' in WEB
    assert 'f"{lang_prefix}/meds?source=pwa"' in WEB
    assert 'f"{lang_prefix}/emergency?source=pwa"' in WEB


def test_consent_has_short_viewport_sticky_submit():
    assert 'id="consentMainSubmit"' in WEB
    assert 'id="consentStickyBar"' in WEB
    assert 'id="consentStickySubmit"' in WEB
    assert "form.requestSubmit(main)" in WEB
    assert "(max-height:760px), (max-width:560px)" in WEB


def test_new_guest_consent_check_skips_known_empty_db():
    assert 'session["_guest_consent_db_empty"] = True' in WEB
    assert 'session.get("_guest_consent_db_empty") is True' in WEB
    assert 'session.pop("_guest_consent_db_empty", None)' in WEB


def test_age_input_mobile_and_accessibility_hardening():
    assert "textInp.inputMode = ageMode ? 'numeric' : 'text'" in CHAT
    assert "[0-9٠-٩۰-۹]*" in CHAT
    assert "textInp.setAttribute('maxlength','3')" in CHAT
    assert "Age in years from 1 to 120" in CHAT
