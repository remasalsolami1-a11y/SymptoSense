import source_bundle
import versioning
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()
DASH = (ROOT / "dashboard.py").read_text(encoding="utf-8")
CHAT = source_bundle.chat_view_text()
MK = (ROOT / "medical_knowledge.py").read_text(encoding="utf-8")
GAPS = (ROOT / "content_gaps.py").read_text(encoding="utf-8")
PRIV = (ROOT / "privacy_features.py").read_text(encoding="utf-8")
RC = (ROOT / "release_candidate.py").read_text(encoding="utf-8")
SW = (ROOT / "service-worker.js").read_text(encoding="utf-8")


def test_smart_followup_allows_up_to_five_targeted_questions():
    assert "const SMART_FOLLOWUP_MAX = 5" in CHAT
    assert "differentialCount >= SMART_FOLLOWUP_MAX" in CHAT
    assert "ساعدنا نفهم أكثر · سؤال " in CHAT
    assert "Help us understand better · Question " in CHAT
    assert '"max_questions": max_questions' in MK
    assert '"question_number": min(len(asked) + 1, max_questions)' in MK


def test_smart_followup_re_ranks_after_yes_and_no_answers():
    assert "state.symptoms.push(d.symptom_name)" in CHAT
    assert "differentialNegatives.push(d.symptom_slug)" in CHAT
    assert "symptoms:state.symptoms, asked:differentialAsked, negatives:differentialNegatives" in CHAT


def test_content_gaps_admin_surface_and_api_exist():
    assert 'data-view="contentgaps"' in DASH
    assert 'id="view-contentgaps"' in DASH
    assert "loadContentGaps()" in DASH
    assert '"/api/admin/content-gaps"' in WEB
    assert "content_gaps.report(days=days, limit=limit)" in WEB


def test_content_gap_logging_is_analytics_gated_and_identity_free():
    assert 'result.get("query_only") and _analytics_consent_ok()' in WEB
    assert "best_effort.call(content_gaps.log_search_gap, q, lang)" in WEB
    assert "search_gap_user_ids_stored\": False" in GAPS
    assert "search_gap_session_ids_stored\": False" in GAPS
    assert "_EMAIL_RE" in GAPS and "_PHONE_RE" in GAPS and "_DIGIT_RE" in GAPS


def test_search_gap_retention_and_launch_reset_are_covered():
    retention = (ROOT / "data_retention.py").read_text(encoding="utf-8")
    db_text = (ROOT / "db.py").read_text(encoding="utf-8")
    assert '"ss_search_gap_log","created_at"' in retention
    assert '"ss_search_gap_log"' in db_text


def test_privacy_versions_and_copy_updated_for_new_analytics_signal():
    assert 'CONSENT_VERSION = os.environ.get("CONSENT_VERSION", "2.1")' in PRIV
    assert 'PRIVACY_POLICY_VERSION = os.environ.get("PRIVACY_POLICY_VERSION", "2.1")' in PRIV
    assert "بدون ربطها بحساب أو جلسة" in WEB


def test_v67_release_metadata_and_pwa_cache_match():
    assert versioning.APP_VERSION == __import__("release_candidate").APP_VERSION
    assert versioning.RC_ID == __import__("release_candidate").RC_ID
    assert versioning.SW_CACHE in SW
