import source_bundle
from pathlib import Path
import mental_support

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()


def test_vent_mode_listens_before_advice():
    answer = mental_support.supportive_answer("أبي أفضفض، بس اسمعني شوي بدون حلول", "ar")
    assert "أسمعك" in answer
    assert "ما راح أقفز للحلول" in answer


def test_other_harm_has_safety_escalation():
    assert mental_support.safety_level("أنا معصب وأبي أقتله") == "other_harm"
    answer = mental_support.supportive_answer("أنا معصب وأبي أقتله", "ar")
    assert "أبعد نفسك" in answer
    assert "الطوارئ" in answer


def test_friend_mode_ui_is_conversational_not_clinical():
    assert '"asst_mh_title": "🤍 فضفضة"' in WEB
    assert '"asst_mh_o_anx": "بس أبي أفضفض"' in WEB
    assert '"asst_mh_o_sad": "ساعدني أفكر"' in WEB
    assert '"asst_mh_o_str": "هدّيني شوي"' in WEB
    assert "كصديق هادئ" in WEB or "صديق هادئ" in WEB


def test_identity_is_honest_if_asked():
    assert "لا تدّعي أنك إنسان أو صديق حقيقي" in WEB
    assert "مساعد دعم رقمي داخل SymptoSense" in WEB


def test_one_time_digital_disclosure_and_no_repeated_fallback_disclaimer():
    assert "هذي مساحة دعم رقمية، مو شخص حقيقي" in WEB
    # Local helper no longer appends a repetitive clinical note to every reply.
    block = WEB[WEB.index("def _assistant_local_mental_answer"):WEB.index("def _assistant_services")]
    assert "هذه مساحة دعم توعوي" not in block


def test_context_window_is_longer_for_conversation_continuity():
    assert "for m in messages[-10:]:" in WEB
