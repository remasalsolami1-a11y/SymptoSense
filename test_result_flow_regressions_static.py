from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = (ROOT / "webapp.py").read_text(encoding="utf-8")


def test_analysis_loading_message_is_removed_on_success_and_failure():
    start = WEB.index("async function runAnalysis()")
    end = WEB.index("function showEmergency", start)
    block = WEB[start:end]
    assert "const analyzingBubble = add(TT('analyzing'), 'bot');" in block
    assert block.count("finishAnalysisLoading();") >= 2
    assert "analyzingBubble.remove()" in block


def test_differential_followups_replace_the_current_question_card():
    assert "function focusStepQuestion(msg, answerOverride, kickerOverride)" in WEB
    assert "kicker.textContent = kickerOverride ||" in WEB
    start = WEB.index("async function startDifferentialQuestions()")
    end = WEB.index("function walkClarNode", start)
    block = WEB[start:end]
    assert "focusStepQuestion(" in block
    assert "d.question" in block
    assert "ساعدنا نفهم أكثر" in block
    assert "addQ('🩺 ' + d.question)" not in block


def test_complete_input_is_not_described_as_missing_information():
    start = WEB.index("function showIncompleteResult")
    end = WEB.index("function reAnalyzeWithMoreInfo", start)
    block = WEB[start:end]
    assert "const inputComplete" in block
    assert "بياناتك الأساسية مكتملة" in block
    assert "لم نجد مطابقة طبية موثوقة كافية" in block


def test_information_completeness_label_is_consistent():
    assert "اكتمال المعلومات المدخلة" in WEB
    assert "جودة المعلومات':'Data Quality" not in WEB
    assert "'جودة المعلومات' if ar else 'Data Quality'" not in WEB
    assert '"quality":"جودة المعلومات المدخلة"' not in WEB
