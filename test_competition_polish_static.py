from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = (ROOT / 'webapp.py').read_text(encoding='utf-8')
DB = (ROOT / 'db.py').read_text(encoding='utf-8')
DASH = (ROOT / 'dashboard.py').read_text(encoding='utf-8')

def test_public_community_dashboard_exists_as_pilot():
    assert '@app.route("/community-dashboard")' in WEB
    assert 'public_site_summary(comment_limit=24)' in WEB
    assert 'الاختبار الأولي للمستخدمين — Pilot' in WEB
    assert 'التعليقات الفردية مخفية في نسخة المسابقة' in WEB

def test_public_comments_are_opt_in():
    assert 'public_comment = bool(data.get("public_comment")) and bool(comment)' in WEB
    assert 'public_only=True' in DB
    assert 'public_comment INTEGER NOT NULL DEFAULT 0' in DB

def test_feedback_is_five_star_and_has_comment():
    assert 'selectFeedbackStar' in WEB
    assert 'rating_must_be_1_to_5' in WEB
    assert 'star:%d' in WEB
    assert 'feedback_comment' in WEB

def test_feedback_is_explicit_not_blocked_by_analytics_consent():
    start = WEB.index('def api_feedback():')
    end = WEB.index('@app.route("/api/search")', start)
    block = WEB[start:end]
    assert '_analytics_consent_ok()' not in block

def test_home_has_how_it_works_without_duplicate_community_dashboard():
    start = WEB.index('def home_page():')
    end = WEB.index('\n\ndef _tools_html', start)
    block = WEB[start:end]
    assert 'كيف يعمل SymptoSense؟' in block
    assert 'home-community' not in block
    assert 'href="/community-dashboard"' not in block
    assert '@app.route("/community-dashboard")' in WEB

def test_about_has_methodology_box():
    assert 'AI + Data Science + Digital Health' in WEB
    assert 'href="/methodology"' in WEB
    assert '@app.route("/methodology")' in WEB

def test_footer_is_professional():
    assert 'Designed & Developed by' in WEB
    assert 'Remas Alsolami — Data Science Project' in WEB

def test_accessibility_menu_groups_voice_and_reading():
    assert 'class="chat-access"' in WEB
    assert '__ACCESSIBILITY__' in WEB
    assert '__VOICE_INPUT__' in WEB
    assert 'id="spkBtn"' in WEB
    assert 'id="micBtn"' in WEB
    assert 'toggleSpeak' in WEB
    assert 'toggleQuickMic' in WEB

def test_result_core_order_is_dashboard_like():
    danger = WEB.index('// 5) Danger signs')
    sources = WEB.index('// 6) Medical sources', danger)
    home = WEB.index('// 7) Home care', sources)
    assert danger < sources < home

def test_admin_dashboard_renders_feedback_comments():
    assert 'feedbackStats' in DASH
    assert 'feedbackComments' in DASH
    assert "req('/api/stats')" in DASH
    assert 'db.feedback_comments(100, public_only=False)' in DASH
    assert 'x.timestamp||x.created_at' in DASH

def test_competition_runtime_fallbacks_are_resilient():
    assert 'def _followup_local_answer' in WEB
    assert '"fallback": True' in WEB
    assert '@app.route("/api/analyze/export-current", methods=["POST"])' in WEB
    assert "body:JSON.stringify({result:lastResult||{},lang:LANG})" in WEB

def test_assistant_modes_are_visually_separated_and_links_are_real():
    assert 'function asstRestoreModeHistory(isMh)' in WEB
    assert "sessionStorage.getItem(isMh ? 'asst_hist_mh' : 'asst_hist')" in WEB
    assert 'href="#"' not in WEB

def test_general_questions_do_not_route_to_cbc_by_single_blood_word():
    start = WEB.index('def _assistant_services')
    end = WEB.index('@app.route("/api/assistant"', start)
    block = WEB[start:end]
    assert '("دم", "فحص"' not in block
    assert '"تحليل دم"' in block

def test_symptom_page_has_only_one_assistant_surface():
    assert 'body.ss-chat-page .asst-fab,body.ss-chat-page .asst-panel{display:none!important}' in WEB


def test_voice_controls_are_only_exposed_inside_accessibility_menu():
    chat_start = WEB.index('def chat_page():')
    chat_end = WEB.index('\n\n@app.route("/blood")', chat_start)
    block = WEB[chat_start:chat_end]
    header = block[block.index('<div class="chat-head">'):block.index('<div class="ss-flow"')]
    assert 'class="chat-head-toggles"' not in header
    assert '<details class="chat-access"' in header
    assert 'id="spkBtn"' in header
    assert 'id="micBtn"' in header
    assert '__ACCESSIBILITY__' in header
    assert 'let autoSpeak = false;' in block
    assert "items.push({label:TT('voice_chip')" not in block
    assert "onclick=\"speakResult()\"" not in block


def test_home_uses_trust_strip_without_duplicate_bottom_disclaimer():
    start = WEB.index('def home_page():')
    end = WEB.index('\n\ndef _tools_html', start)
    block = WEB[start:end]
    assert 'class="ss-trust-row"' in block
    assert '__TRUST_INFO__' in block and '__TRUST_PRIV__' in block and '__TRUST_NODIAG__' in block
    assert 'class="warn2"' not in block


def test_public_dashboard_exposes_published_comment_count():
    assert '"comment_count": comment_count' in DB
    assert '__COMMENT_COUNT__' in WEB
    assert 'تعليق منشور' in WEB
