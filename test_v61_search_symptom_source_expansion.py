import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import health_search
import medical_knowledge


def test_v61_bundled_counts_and_stronger_sources():
    assert len(medical_knowledge.SOURCES) >= 16
    assert len(medical_knowledge.SYMPTOMS) >= 185
    assert len(medical_knowledge.DISEASES) >= 108
    assert len(medical_knowledge.RED_RULES) >= 23
    source_slugs = {row[0] for row in medical_knowledge.SOURCES}
    assert {"nei", "nimh", "niaid", "nidcd", "nichd"} <= source_slugs


def test_v61_search_expanded_topics_are_sourced():
    assert len(health_search.SEARCH_KB) >= 80
    for query, expected in [
        ("دوخة من الحر", "الإجهاد الحراري"),
        ("حرقان فم المعدة", "قرحة المعدة أو الاثني عشر"),
        ("دورتي غير منتظمة وشعر زائد", "متلازمة تكيس المبايض (PCOS/PMOS)"),
        ("فقدت السمع فجأة", "فقدان السمع المفاجئ"),
        ("حكة تزيد بالليل", "الجرب"),
        ("حصوة كلى", "حصى الكلى"),
    ]:
        result = health_search.search_health(query, "ar")
        assert result is not None
        assert result["title"] == expected
        assert result.get("sources")
        assert all(str(s.get("url", "")).startswith("https://") for s in result["sources"])


def test_v61_symptom_normalization_and_matching(tmp_path, monkeypatch):
    # medical_knowledge/db read DB_PATH at import time, so use the already-created
    # test database configured by the test runner and validate the seeded catalog.
    medical_knowledge.init_schema()
    cases = [
        (["دوخة من الحر", "تعرق", "غثيان"], "heat-exhaustion"),
        (["حرقان فم المعدة", "اشبع بسرعه", "غثيان"], "peptic-ulcer-disease"),
        (["الم الحوض", "دورتي غزيره", "الم وقت الجماع"], "endometriosis-pattern"),
        (["دورتي غير منتظمه", "شعر زائد بالوجه", "حب شباب"], "polycystic-ovary-syndrome-pattern"),
        (["الحكة تزيد بالليل", "خطوط صغيره بالجلد مع حكة"], "scabies"),
        (["اذني توجع اذا لمستها", "صديد من الاذن"], "otitis-externa"),
        (["فقدت السمع فجأه"], "sudden-hearing-loss-warning-pattern"),
    ]
    for raw, expected_slug in cases:
        normalized = medical_knowledge.normalize_symptoms(raw, "ar")
        assert not normalized["unmatched"]
        matches = medical_knowledge.match_diseases(normalized["canonical"], "ar", limit=8)
        assert expected_slug in {m["slug"] for m in matches}


def test_v61_statistics_reflect_expansion():
    medical_knowledge.init_schema()
    stats = medical_knowledge.statistics()
    assert stats["verified_sources"] >= 16
    assert stats["active_diseases"] >= 108
    assert stats["active_symptoms"] >= 185
    assert stats["active_red_flags"] >= 23
    assert stats["recent_source_additions"] >= 9
    assert stats["source_coverage_pct"] == 100.0
    assert stats["symptom_coverage_pct"] >= 98.0
