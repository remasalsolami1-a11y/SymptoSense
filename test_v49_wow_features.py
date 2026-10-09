import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_interactive_body_map_markup_and_logic_present():
    src = source_bundle.chat_view_text()
    assert "BODY_MAP_REGIONS" in src
    assert "smart-body-card" in src
    assert "showBodyRegion" in src
    assert "toggleBodyMapSymptom" in src
    assert "Interactive body map" in src or "خريطة الجسم التفاعلية" in src


def test_premium_source_cards_are_present_in_chat_and_sources_page():
    chat_src = source_bundle.chat_view_text()
    web_src = source_bundle.webapp_text()
    assert "ss-source-mark" in web_src
    assert "ss-source-badges" in web_src
    assert "v2-source-mark" in web_src
    assert "v2-source-badges" in web_src
    assert "function sourceInitials" in chat_src
    assert "Open source" in chat_src or "عرض المصدر الأصلي" in chat_src
