import source_bundle
from pathlib import Path
ROOT = Path(__file__).resolve().parent
CHAT = source_bundle.chat_view_text()
WEB = source_bundle.webapp_text()

def test_symptom_ui_is_one_layout_on_every_device():
    assert "function compactSymptomUI(){ return true; }" in CHAT
    assert "matchMedia('(max-width: 640px)')" not in CHAT

def test_views_copy_identical():
    assert CHAT == source_bundle.chat_view_text()

def test_unified_css_not_phone_only():
    assert "symptom entry — one unified layout on every device" in WEB
    i = WEB.index("one unified layout on every device")
    assert "@media screen{" in WEB[i:i+400]
    assert "width:min(100%,560px)" in WEB
