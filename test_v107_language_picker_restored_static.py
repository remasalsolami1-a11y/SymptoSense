import source_bundle
import versioning
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parent
WEB=source_bundle.webapp_text()
SW=(ROOT/"service-worker.js").read_text(encoding="utf-8")
MANIFEST=json.loads((ROOT/"manifest.webmanifest").read_text(encoding="utf-8"))

def test_root_does_not_skip_picker_for_saved_language():
    s=WEB.index('@app.route("/")'); e=WEB.index('@app.route("/language/<code>"',s); b=WEB[s:e]
    assert "welcome_page()" in b
    assert 'redirect(url_for("home")' not in b
    assert 'response.headers["Cache-Control"] = "no-store, max-age=0"' in b

def test_old_installed_pwa_start_url_is_compatible():
    s=WEB.index('@app.route("/home")'); b=WEB[s:s+1200]
    assert 'request.args.get("source") == "pwa"' in b
    assert 'url_for("index", next="/home")' in b
    assert 'request.cookies.get("lang")' not in b

def test_new_manifest_uses_language_prefixed_start():
    assert MANIFEST["start_url"]=="/ar/?source=pwa"
    assert '"start_url": f"{lang_prefix}/?source=pwa"' in WEB

def test_language_selection_does_not_loop():
    assert 'ar_target = _localized_target_from_legacy(next_target, "ar")' in WEB and 'en_target = _localized_target_from_legacy(next_target, "en")' in WEB
    s=WEB.index('@app.route("/home")'); b=WEB[s:s+1200]
    assert "and not selected" in b

def test_service_worker_cache_bumped():
    assert versioning.SW_CACHE in SW
