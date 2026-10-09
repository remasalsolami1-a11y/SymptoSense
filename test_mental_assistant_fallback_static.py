import source_bundle
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _source_and_helper():
    source = source_bundle.webapp_text()
    tree = ast.parse(source_bundle.python_text())
    node = next(
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "_assistant_local_mental_answer"
    )
    module = ast.Module(body=[node], type_ignores=[])
    ns = {}
    exec(compile(ast.fix_missing_locations(module), "<mental-helper>", "exec"), ns)
    return source, ns["_assistant_local_mental_answer"]


def test_mental_fallback_is_useful_when_provider_is_down():
    _, helper = _source_and_helper()
    for text in [
        "أشعر بقلق كبير",
        "أشعر بالحزن",
        "أنا متوتر ومضغوط",
        "ما أقدر أنام",
        "أفكاري كثيرة ومتزاحمة",
        "أبي أتكلم عن شيء آخر",
    ]:
        answer = helper(text, "ar")
        assert answer
        assert "تعذر" not in answer
        # Friend-mode fallbacks should stay useful without appending the same
        # clinical disclaimer after every single message.
        assert len(answer.strip()) >= 20
        assert "هذه مساحة دعم توعوي" not in answer


def test_mental_fallback_keeps_crisis_guidance_local():
    _, helper = _source_and_helper()
    answer = helper("أبي أموت", "ar")
    assert "997" in answer
    assert "937" in answer
    assert "لا تبق وحدك" in answer


def test_mental_mode_has_dedicated_history_and_consent_handling():
    source, _ = _source_and_helper()
    assert "asst_hist_mh" in source
    assert "if (d.consent_required)" in source
    assert "asstMhOfflineReply(text)" in source
    assert "_assistant_local_mental_answer(last_text, lang)" in source


def test_mental_mode_is_captured_at_send_time():
    source, _ = _source_and_helper()
    assert "var requestIsMh = !!asstMhMode" in source
    assert "mode: requestIsMh ? 'mh' : ''" in source
    assert "var histKey = requestIsMh ? 'asst_hist_mh' : 'asst_hist';" in source
    assert "asstReply(requestIsMh ? asstMhOfflineReply(text) : asstTT('asst_offline'))" in source


def test_generic_health_fallback_is_blocked_inside_mental_mode():
    source, _ = _source_and_helper()
    assert "wrongMentalFallback" in source
    assert "if (requestIsMh && (!answer || wrongMentalFallback))" in source
    assert "if mode == \"mh\":" in source
    assert '"تحليل الأعراض"' in source
    assert "answer = _assistant_local_mental_answer(last_text, lang) or answer" in source
