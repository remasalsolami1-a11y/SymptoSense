import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEBAPP = (ROOT / "webapp.py").read_text(encoding="utf-8")
MANIFEST = json.loads((ROOT / "manifest.webmanifest").read_text(encoding="utf-8"))
SW = (ROOT / "service-worker.js").read_text(encoding="utf-8")


def test_geolocation_allowed_only_for_self():
    assert 'geolocation=(self)' in WEBAPP
    assert 'geolocation=()' not in WEBAPP


def test_youtube_nocookie_allowed_in_csp_report_only():
    assert "frame-src 'self' https://www.youtube-nocookie.com" in WEBAPP


def test_secure_cookie_defaults_on_railway_or_https_production():
    assert 'RAILWAY_PUBLIC_DOMAIN' in WEBAPP
    assert 'RAILWAY_ENVIRONMENT' in WEBAPP
    assert 'SESSION_COOKIE_SECURE=_secure_cookie' in WEBAPP


def test_pwa_uses_product_name_and_png_icons():
    assert MANIFEST["short_name"] == "SymptoSense"
    assert "V2" not in MANIFEST["name"]
    icon_paths = {item["src"] for item in MANIFEST["icons"]}
    assert "/icons/icon-192.png" in icon_paths
    assert "/icons/icon-512.png" in icon_paths
    assert '<link rel="apple-touch-icon" sizes="180x180" href="/icons/apple-touch-icon.png">' in WEBAPP


def test_service_worker_cache_was_bumped_for_pwa_changes():
    assert 'symptosense-shell-v7-production-cleanup' in SW


def test_optional_analytics_is_explicitly_gated():
    assert 'if not is_candidate or not _analytics_consent_ok()' in WEBAPP
    assert 'if _analytics_consent_ok():\n                    platform_v2.record_usage("safety_alert"' in WEBAPP


def test_public_api_exception_details_not_returned_verbatim():
    forbidden = [
        '"error": str(e)',
        '"error":str(e)',
        '"error": str(exc)',
        '"error":str(exc)',
        'f"{type(e).__name__}:',
        'f"{type(exc).__name__}:',
    ]
    for token in forbidden:
        assert token not in WEBAPP


def test_web_ai_timeout_is_bounded():
    assert 'timeout=45' not in WEBAPP
    assert 'timeout=20' in WEBAPP

BOT = (ROOT / "bot.py").read_text(encoding="utf-8")
WELLBEING = (ROOT / "wellbeing.py").read_text(encoding="utf-8")


def test_result_questions_use_existing_assistant_api_contract():
    assert "fetch('/api/chat'," not in WEBAPP
    assert "fetch('/api/assistant'," in WEBAPP
    assert "messages:[{role:'user', content:prompt}]" in WEBAPP
    assert "d.answer || TT('fallback_chat')" in WEBAPP


def test_password_copy_matches_eight_character_validation():
    assert 'كلمة المرور (٨ أحرف على الأقل)' in WEBAPP
    assert 'Password (minimum 8 characters)' in WEBAPP
    assert 'كلمة المرور (٦ أحرف على الأقل)' not in WEBAPP
    assert 'Password (min 6 characters)' not in WEBAPP


def test_notification_copy_is_arabic_and_gender_neutral():
    assert "'__NOTIF_ON__':tx('إشعارات الدواء','Medication Notifications')" in WEBAPP
    for token in ('فعّليه', 'أضيفي', 'افتحيه', 'فعّلي', 'سجّلي الدخول'):
        assert token not in WEBAPP


def test_bot_copy_has_no_targeted_feminine_prompts():
    for token in ('اضغطي', 'جربي'):
        assert token not in BOT


def test_wellbeing_copy_is_gender_neutral():
    for token in ('اجلسي', 'استلقي', 'استنشقي', 'احبسي', 'أخرجي', 'خذي'):
        assert token not in WELLBEING


def test_guest_symptom_flow_skips_family_api_until_login_confirmed():
    assert "if (!(userInfo && userInfo.ok && userInfo.logged_in))" in WEBAPP
    assert "return Promise.resolve({ok:true, members:[]});" in WEBAPP
    assert "if (r.status === 401) return {ok:true, members:[]};" in WEBAPP


def test_about_uses_static_real_screenshot_not_home_iframe():
    assert '<iframe src="/home"' not in WEBAPP
    assert ('/static/images/about-home-preview.webp' in WEBAPP) or ('data:image/webp;base64,' in WEBAPP) or ('data:image/png;base64,' in WEBAPP)
    assert (ROOT / 'static/images/about-home-preview.webp').exists()


def test_chat_result_assistant_prompt_keeps_escaped_newlines_in_runtime_html():
    """A Python triple-quoted template must emit JS \\n escapes, not literal line breaks."""
    import ast

    tree = ast.parse(WEBAPP)
    chat_body = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "chat_page":
            for stmt in node.body:
                if (
                    isinstance(stmt, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "body" for t in stmt.targets)
                    and isinstance(stmt.value, ast.Constant)
                    and isinstance(stmt.value.value, str)
                ):
                    chat_body = stmt.value.value
                    break
    assert chat_body is not None
    assert "const prompt = q + '\\n\\n' + contextLabel" in chat_body
    assert "const prompt = q + '\n\n' + contextLabel" not in chat_body
