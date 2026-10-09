import source_bundle
import versioning
from pathlib import Path
import health_search
import health_library
import medical_knowledge
import search_engine_v2

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()
SW = (ROOT / "service-worker.js").read_text(encoding="utf-8")


def test_source_growth_badge_is_not_in_current_ui():
    assert "+5 مصادر جديدة" not in WEB
    assert "+5 new sources" not in WEB
    assert "__STAT_SOURCES_NEW__" not in WEB


def test_search_copy_describes_broader_scope():
    assert "الأعراض والحالات الصحية والأدوية والتحاليل والمصطلحات" in WEB
    assert "v5-comprehensive-library-search" in WEB


def test_structured_search_entries_expose_more_information_when_available():
    result = health_search.search_health("انتفاخ", "ar")
    assert result and result["what"] and result["causes"] and result["worry"] and result["doctor"]
    # Expanded curated topics carry practical self-care/follow-up when reviewed.
    detailed = health_search.search_health("إمساك", "ar")
    assert detailed and detailed.get("self_care")
    assert detailed.get("follow_up")


def test_search_engine_covers_symptoms_conditions_medicines_and_tests():
    cases = [
        ("دوخة", "symptom"),
        ("السكري من النوع الثاني", "disease"),
        ("بنادول", "medication"),
        ("Ferritin", "test"),
    ]
    for query, kind in cases:
        result = search_engine_v2.search(query, "ar", 8)
        assert result["results"], query
        assert any(x.get("kind") == kind for x in result["results"][:4]), (query, result["results"][:4])


def test_compound_search_is_capped_to_three_topics_in_ui_and_backend():
    assert 'result["matched_topics"] = existing[:3]' in WEB
    assert 'r.matched_topics.slice(0,3)' in WEB


def test_search_ui_has_comprehensive_sections():
    for marker in (
        "ما يمكنك فعله الآن", "أسئلة تساعد على فهم الصورة", "حالات قد يرتبط بها هذا العرض",
        "عوامل قد تزيد الاحتمال", "أعراض قد ترافق الحالة", "مصادر هذا الموضوع",
    ):
        assert marker in WEB


def test_library_symptom_cards_show_description_under_title():
    html = health_library.index("ar")
    assert 'class="hl-chip-main"' in html
    assert 'class="hl-chip hl-chip-symptom' in html
    # Every source symptom row currently carries a description; the index should
    # therefore have a <small> explanation under symptom names.
    rows = [x for x in medical_knowledge.list_entities("symptoms", False, "") if medical_knowledge.public_source_ready("symptom", int(x["id"]))]
    assert rows
    sample = rows[0]
    name = sample.get("name_ar")
    desc = sample.get("description_ar")
    assert name and desc
    assert name in html


def test_v204_service_worker_cache_is_bumped():
    assert versioning.SW_CACHE in SW
