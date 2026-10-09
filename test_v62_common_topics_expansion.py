import source_bundle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import health_search
import medical_knowledge


def test_v62_catalog_growth_and_source():
    assert len(medical_knowledge.SOURCES) >= 17
    assert len(medical_knowledge.SYMPTOMS) >= 204
    assert len(medical_knowledge.DISEASES) >= 128
    assert len(health_search.SEARCH_KB) >= 100
    assert "acog" in {row[0] for row in medical_knowledge.SOURCES}


def test_v62_common_search_topics():
    cases = [
        ("حبة في الجفن", "شعيرة الجفن"),
        ("دورة غزيرة", "غزارة الدورة"),
        ("ريحة سمكية", "اختلال البكتيريا المهبلية (BV)"),
        ("شق شرجي", "الشق الشرجي"),
        ("عسر هضم", "عسر الهضم"),
        ("رعاف", "نزيف الأنف"),
        ("الم الثدي", "ألم الثدي"),
        ("حلقي يوجع", "ألم الحلق"),
        ("ثؤلول", "الثآليل"),
    ]
    for query, expected in cases:
        result = health_search.search_health(query, "ar")
        assert result is not None
        assert result["title"] == expected
        assert result.get("sources")
        assert all(str(s.get("url", "")).startswith("https://") for s in result["sources"])


def test_v62_common_symptom_engine_matches():
    medical_knowledge.init_schema()
    cases = [
        (["الم اسفل الظهر"], "mechanical-low-back-pain"),
        (["ركبتي توجع"], "common-knee-pain-pattern"),
        (["كتفي يوجع"], "common-shoulder-pain-pattern"),
        (["حبة في الجفن"], "stye"),
        (["دورة غزيرة"], "heavy-menstrual-bleeding-pattern"),
        (["اعراض قبل الدورة"], "premenstrual-syndrome-pattern"),
        (["عسر هضم"], "functional-dyspepsia-pattern"),
        (["حكة بالمهبل"], "vaginal-thrush-pattern"),
        (["ريحة سمكية"], "bacterial-vaginosis-pattern"),
        (["الم وقت التبرز"], "anal-fissure"),
        (["رعاف"], "nosebleed-pattern"),
        (["حبة حرارة على الشفايف"], "cold-sore"),
        (["حلقي يوجع"], "simple-sore-throat-pattern"),
    ]
    for raw, expected_slug in cases:
        normalized = medical_knowledge.normalize_symptoms(raw, "ar")
        assert not normalized["unmatched"], (raw, normalized)
        matches = medical_knowledge.match_diseases(normalized["canonical"], "ar", limit=8)
        assert expected_slug in {m["slug"] for m in matches}, (raw, [m["slug"] for m in matches])


def test_v62_specific_phrase_suppression():
    medical_knowledge.init_schema()
    normalized = medical_knowledge.normalize_symptoms(["حبة حرارة على الشفايف"], "ar")
    slugs = {x["slug"] for x in normalized["canonical"]}
    assert "lip-blisters" in slugs
    assert "fever" not in slugs

    normalized = medical_knowledge.normalize_symptoms(["حكة بالمهبل"], "ar")
    slugs = {x["slug"] for x in normalized["canonical"]}
    assert "vaginal-itching" in slugs
    assert "itching" not in slugs


def test_v62_statistics_and_ui_copy():
    medical_knowledge.init_schema()
    stats = medical_knowledge.statistics()
    assert stats["verified_sources"] >= 17
    assert stats["active_diseases"] >= 128
    assert stats["active_symptoms"] >= 204
    assert stats["source_coverage_pct"] == 100.0
    webapp = source_bundle.webapp_text()
    # Later library-quality audits replaced the old V62 marketing sentence with
    # a measured summary that avoids inflating topic counts.
    assert "جودة مكتبة الأعراض" in webapp
    assert "لا تضخيم الأرقام" in webapp
