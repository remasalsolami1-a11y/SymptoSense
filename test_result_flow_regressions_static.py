import source_bundle
from pathlib import Path


ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text() + "\n" + source_bundle.chat_view_text()


def test_analysis_loading_message_is_removed_on_success_and_failure():
    start = WEB.index("async function runAnalysis()")
    end = WEB.index("function esc(", start)
    block = WEB[start:end]
    assert "addHtml(heartbeatLoader(TT('analyzing')), 'bot heartbeat-bubble');" in block
    assert "finishAnalysisLoading();" in block
    assert "function finishAnalysisLoading()" in WEB
    assert "querySelectorAll('.heartbeat-bubble')" in WEB


def test_differential_followups_replace_the_current_question_card():
    assert "function focusStepQuestion(msg, answerOverride)" in WEB
    focus = WEB[WEB.index("function focusStepQuestion(msg, answerOverride)"):WEB.index("function clearOpts", WEB.index("function focusStepQuestion(msg, answerOverride)"))]
    assert "bodyEl.textContent = '';" in focus
    start = WEB.index("async function startDifferentialQuestions()")
    end = WEB.index("function askQuestionFromResult", start)
    block = WEB[start:end]
    assert "focusStepQuestion('🩺 ' + d.question);" in block
    assert "ساعدنا نفهم أكثر" in block
    assert "addQ('🩺 ' + d.question)" not in block


def test_complete_input_is_not_described_as_missing_information():
    start = WEB.index("async function showDataQualityGate()")
    end = WEB.index("function improveDataQuality", start)
    block = WEB[start:end]
    assert "if(!q.sufficient)" in block
    assert "أكمل المعلومات المطلوبة أولًا" in block
    assert "تحليل الأعراض" in block
    assert "fn:function(){chooseBloodContextThenAnalyze();}" in block  # V219: explicit optional blood-context choice precedes analysis


def test_information_completeness_label_is_consistent():
    assert "اكتمال المعلومات المدخلة" in WEB
    assert "جودة المعلومات':'Data Quality" not in WEB
    assert "'جودة المعلومات' if ar else 'Data Quality'" not in WEB
    assert '"quality":"جودة المعلومات المدخلة"' not in WEB
