import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def test_body_map_is_mounted_inside_symptom_step_on_first_render():
    src = source_bundle.chat_view_text()
    assert "function ensureBodyMapCard()" in src
    assert "disclosure.className = 'symptom-bodymap-disclosure symptom-bodymap-always-open';" in src
    assert "symptom-bodymap-header" in src
    assert "if (!compact) ensureBodyMapCard();" in src or "if (!compactSymptomUI()) ensureBodyMapCard();" in src

def test_body_map_no_longer_depends_on_legacy_query_mode():
    src = source_bundle.chat_view_text()
    assert "new URLSearchParams(location.search).get('bodymap')" not in src
    assert 'data-symptom-method="body"' in src
    assert "openBodyMapSheet" in src

def test_body_map_is_not_a_separate_home_or_trust_route():
    web = source_bundle.webapp_text()
    chat = source_bundle.chat_view_text()
    assert 'href="/chat?bodymap=1"' not in web
    assert "خريطة الجسم التفاعلية" in chat or "Interactive body map" in chat

def test_both_chat_views_stay_identical():
    a=source_bundle.chat_view_text()
    b=source_bundle.chat_view_text()
    assert a==b
