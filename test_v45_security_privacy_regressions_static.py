import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()
DB = (ROOT / "db.py").read_text(encoding="utf-8")
MED = (ROOT / "medication_warnings.py").read_text(encoding="utf-8")
SECURITY = (ROOT / "web_security.py").read_text(encoding="utf-8")


def _block(text, start, end):
    i = text.index(start)
    j = text.find(end, i)
    return text[i:j if j >= 0 else len(text)]


def test_inline_script_json_escapes_html_tag_breakout():
    assert '.replace("<",' in SECURITY and '\\u003c' in SECURITY
    assert '.replace(">",' in SECURITY and '\\u003e' in SECURITY
    assert '.replace("&",' in SECURITY and '\\u0026' in SECURITY
    block = _block(WEB, "def _json_for_script", "def _scrub_sentry_event")
    assert 'return web_security.json_for_script' in block

def test_landing_and_consent_use_script_safe_next():
    welcome = _block(WEB, "def welcome_page():", "def home_page():")
    consent = _block(WEB, "def consent_page():", "def privacy_center_page")
    assert '_json_for_script(next_target)' in welcome
    assert 'next_url = _safe_next_url("/chat")' in consent
    assert '"__NEXT__": _json_for_script(next_url)' in consent


def test_profile_and_family_output_encode_user_names():
    profile = _block(WEB, "def user_profile_page():", "def terms_page():")
    family = _block(WEB, "def family_detail_page(mid):", "# ---------------------------------------------------------------- health search")
    assert "profile_dashboard_html.render(data, lang)" in profile
    page = (ROOT / "pagelib/profile_dashboard_html.py").read_text(encoding="utf-8")
    assert "_e(ident.name or t[\"title\"])" in page          # the user's name is HTML-escaped by the renderer
    assert "def _e(value)" in page and "escape(str(value), quote=True)" in page
    assert 'const MEMNAME = __MEMNAME_JS__;' in family
    assert '("__MEMNAME_JS__", _json_for_script(member_name))' in family
    assert '("__NAME__", html_lib.escape(member_name, quote=True))' in family
    assert 'html_lib.escape(str(ana_txt), quote=True)' in family
    assert 'html_lib.escape(str(meds_txt), quote=True)' in family


def test_manage_profile_never_uses_innerhtml_for_saved_value_rendering():
    manage = _block(WEB, "def manage_page():", "@app.route(\"/api/health-profile/field\"")
    assert 'function renderFieldValue(valEl, value)' in manage
    assert 'if (value) { valEl.textContent = value; return; }' in manage
    assert 'valEl.innerHTML = val ||' not in manage
    assert 'valEl.innerHTML = orig ||' not in manage
    editor = (ROOT / "static/js/manage-profile.js").read_text(encoding="utf-8")
    assert '/static/js/manage-profile.js' in manage
    assert 'input.value = current' in editor
    assert 'innerHTML' not in editor


def test_assistant_payload_has_type_and_size_validation():
    block = _block(WEB, '@app.route("/api/assistant", methods=["POST"])', '@app.route("/api/assistant/feedback"')
    assert 'request.get_json(silent=True)' in block
    assert 'not isinstance(data, dict)' in block
    assert 'not isinstance(raw_messages, list) or len(raw_messages) > 20' in block
    assert 'total_chars > 12000' in block
    assert 'item.get("role") not in {"user", "assistant"}' in block
    assert 'not isinstance(item, dict)' in block
    assert 'not isinstance(content, str)' in block


def test_assistant_feedback_does_not_store_free_text():
    route = _block(WEB, '@app.route("/api/assistant/feedback"', 'def _checkin_api_payload')
    assert 'db.save_assistant_feedback(_data_user_id(), None, rating, reason)' in route
    assert 'lastReplyText.slice(0, 500)' not in WEB
    assert 'allowed_reasons = {"unclear", "too_long", "not_answered", "need_more", "not_relevant", "other"}' in route
    assert "['unclear', asstTT('asst_fr1')]" in WEB
    db_block = _block(DB, 'def save_assistant_feedback', 'def assistant_feedback_stats')
    assert '(_hash_user(user_id), None, rating, reason,' in db_block
    assert 'assistant_feedback_no_text_v1' in DB


def test_railway_forces_secure_cookie():
    config = _block(WEB, '_secure_cookie_env = os.environ.get("SESSION_COOKIE_SECURE")', 'app.config.update(')
    assert 'if _RAILWAY_RUNTIME:' in config
    assert '_secure_cookie = True' in config


def test_antibiotic_interaction_copy_is_conservative_and_seed_migrates():
    # The current bundled amoxicillin copy intentionally avoids a broad
    # contraception claim and instead tells users to review all medicines with
    # a clinician/pharmacist. Keep the legacy-seed migration guard so older
    # stored wording can still be upgraded safely.
    assert 'قد توجد تداخلات مع بعض الأدوية' in MED
    assert 'tell your doctor or pharmacist about all medicines and supplements you use' in MED
    assert 'لا تغيّر الجرعة أو المدة بنفسك' in MED
    assert 'medical_seed_meta' in MED
    assert 'legacy_seed_match' in MED
