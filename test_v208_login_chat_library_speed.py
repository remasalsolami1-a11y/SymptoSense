import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_login_guest_button_has_dedicated_high_contrast_style():
    src = source_bundle.webapp_text()
    assert 'class="btn auth-guest-btn"' in src
    assert '.auth-card .auth-guest-btn' in src
    assert 'color:#123B70!important' in src
    assert 'background:#F7FBFE!important' in src
    login_block = src[src.index('@app.route("/login"'):src.index('@app.route("/admin/2fa/setup"')]
    assert 'class="btn ghost"' not in login_block


def test_guest_consent_fast_path_avoids_db_for_brand_new_session():
    src = source_bundle.webapp_text()
    block = src[src.index('def _consent_state():'):src.index('def _service_consent_ok():')]
    assert '"uid" not in session' in block
    assert '_guest_consent_state' in block
    assert 'privacy_features.get_consent' in block
    save = src[src.index('def api_consent_preferences():'):src.index('@app.route("/api/privacy/withdraw-analytics"')]
    assert 'session["_guest_consent_state"]' in save


def test_health_library_uses_bulk_source_readiness_not_n_plus_one():
    lib = (ROOT / "health_library.py").read_text(encoding="utf-8")
    index = lib[lib.index('def index(lang: str)'):lib.index('def detail(')]
    assert 'public_source_ready_ids("disease")' in index
    assert 'public_source_ready_ids("symptom")' in index
    assert 'public_source_ready("disease"' not in index
    assert 'public_source_ready("symptom"' not in index
    mk = (ROOT / "medical_knowledge.py").read_text(encoding="utf-8")
    helper = mk[mk.index('def public_source_ready_ids(kind):'):mk.index('def save_disease')]
    assert 'JOIN mk_sources' in helper
    assert 'return {eid for eid' in helper


def test_library_click_schema_is_guarded_once_per_database_identity():
    lib = (ROOT / "health_library.py").read_text(encoding="utf-8")
    block = lib[lib.index('def init_usage_schema():'):lib.index('def record_click')]
    assert '_USAGE_SCHEMA_READY == identity' in block
    assert '_USAGE_SCHEMA_LOCK' in block
