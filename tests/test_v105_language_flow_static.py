import source_bundle
from pathlib import Path
WEB=source_bundle.webapp_text()

def test_root_keeps_language_picker_visible():
    s=WEB.index('@app.route("/")'); e=WEB.index('@app.route("/language/<code>"',s); b=WEB[s:e]
    assert "welcome_page()" in b
    assert 'redirect(url_for("home")' not in b
    assert 'response.headers["Cache-Control"] = "no-store, max-age=0"' in b

def test_pwa_launch_goes_through_language_picker():
    s=WEB.index('@app.route("/home")'); b=WEB[s:s+1200]
    assert 'request.args.get("source") == "pwa"' in b
    assert 'redirect(url_for("index", next="/home"), code=303)' in b

def test_manifest_launches_in_selected_language():
    assert '"start_url": f"{lang_prefix}/?source=pwa"' in WEB

def test_language_buttons_still_go_directly_to_requested_page():
    assert 'ar_target = _localized_target_from_legacy(next_target, "ar")' in WEB
    assert 'en_target = _localized_target_from_legacy(next_target, "en")' in WEB
