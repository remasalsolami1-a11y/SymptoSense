import source_bundle
import versioning
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CHAT=source_bundle.chat_view_text() if (ROOT/"chat_view.py").exists() else Path(__file__).with_name("chat_view.py").read_text(encoding="utf-8")
CSS=(ROOT/"app-shell-v111.css").read_text(encoding="utf-8") if (ROOT/"app-shell-v111.css").exists() else Path(__file__).with_name("app-shell-v111.css").read_text(encoding="utf-8")
WEB=source_bundle.webapp_text() if (ROOT/"webapp.py").exists() else Path(__file__).with_name("webapp.py").read_text(encoding="utf-8")
SW=(ROOT/"service-worker.js").read_text(encoding="utf-8") if (ROOT/"service-worker.js").exists() else Path(__file__).with_name("service-worker.js").read_text(encoding="utf-8")

def test_mobile_defaults_to_body_map_and_renders_inline():
    assert "let symptomInputMethod = 'body';" in CHAT
    assert "pane.innerHTML=renderBodyMapCard();" in CHAT
    assert "symptom-method-pane-body" in CHAT

def test_body_selection_reveals_common_symptoms_and_custom_entry():
    assert "الأعراض الأكثر شيوعًا في هذه المنطقة" in CHAT
    assert "ما لقيت الوصف المناسب؟" in CHAT or "ما لقيت عرضك؟" in CHAT
    assert "data-body-other-input" in CHAT
    assert "data-body-symptom" in CHAT

def test_mobile_method_switcher_is_compact_not_large_cards():
    assert "symptom-method-tabs-compact" in CHAT
    assert "V238 inline body-map symptom entry" in CSS
    assert "min-height:48px!important" in CSS

def test_v238_cache_bust():
    assert "/assets/app-shell-v112.css?v=268" in WEB
    assert "symptosense-app-shell-v112-v268" in WEB
    assert versioning.SW_CACHE in SW
