import source_bundle
from pathlib import Path

import health_search
import medical_knowledge

ROOT = Path(__file__).resolve().parent


def test_v74_counts_and_source_diversity_increased():
    assert len(medical_knowledge.SOURCES) >= 22
    assert len(medical_knowledge.SYMPTOMS) >= 247
    assert len(medical_knowledge.DISEASES) >= 156
    assert len(health_search.SEARCH_KB) >= 126
    source_slugs = {row[0] for row in medical_knowledge.SOURCES}
    assert {"nidcr", "niams", "womens-health", "aha", "aad"}.issubset(source_slugs)


def test_v74_new_common_phrases_reach_expected_source_grounded_pattern():
    samples = {
        "اطحن اسناني بالنوم": ("bruxism-pattern", "nidcr"),
        "لساني يحرق": ("burning-mouth-syndrome-pattern", "nidcr"),
        "انتفاخ تحت الفك وقت الاكل": ("salivary-gland-obstruction-pattern", "nidcr"),
        "طفح من الحر": ("heat-rash-pattern", "nhs"),
        "جلدي محروق من الشمس": ("sunburn-pattern", "nhs"),
        "قرصة حشرة": ("insect-bite-sting-pattern", "nhs"),
        "دمل": ("boil-skin-abscess-pattern", "nhs"),
        "اتعرق كثير بدون سبب": ("hyperhidrosis-pattern", "nhs"),
        "كتفي متيبس": ("frozen-shoulder-pattern", "nhs"),
        "يدي توجع من استخدام الماوس": ("repetitive-strain-injury-pattern", "nhs"),
        "ألم قصبة الساق بعد الجري": ("shin-splints-pattern", "nhs"),
        "الدورة متأخرة": ("missed-late-period-pattern", "nhs"),
        "جفاف مهبلي": ("vaginal-dryness-pattern", "nhs"),
        "طنين الأذن": ("tinnitus-pattern", "nidcd"),
    }
    for phrase, (slug, source_slug) in samples.items():
        bundle = medical_knowledge.knowledge_bundle([phrase], severity=1, notes=phrase, lang="ar")
        match = (bundle.get("matches") or [None])[0]
        assert match is not None, phrase
        assert match["slug"] == slug, phrase
        source = match.get("explanation_source") or {}
        actual = str(source.get("source_name") or source.get("slug") or "").lower()
        assert source_slug.replace("-", "") in actual.replace("-", "").replace(" ", ""), (phrase, source)


def test_v74_health_search_recognizes_new_topics_with_references():
    for phrase in [
        "حرق شمس", "صرير الأسنان", "انتفاخ تحت الفك وقت الاكل", "طفح من الحر",
        "قرصة حشرة", "دمل", "تعرق مفرط", "كتف متجمد", "ألم قصبة الساق بعد الجري",
        "الدورة متأخرة", "جفاف مهبلي", "طنين الأذن", "قرحة بالفم",
    ]:
        result = health_search.search_health(phrase, "ar")
        assert result.get("recognized_topics"), phrase
        assert result.get("sources"), phrase
        assert all((row.get("url") or "").startswith("https://") for row in result["sources"]), phrase


def test_v74_specialty_sources_enrich_existing_conditions():
    diseases = {d["slug"]: d for d in medical_knowledge.DISEASES}
    expected = {
        "dry-mouth-pattern": "nidcr",
        "gum-disease": "nidcr",
        "fibromyalgia": "niams",
        "osteoarthritis": "niams",
        "rheumatoid-arthritis": "niams",
        "gout": "niams",
        "endometriosis-pattern": "womens-health",
        "polycystic-ovary-syndrome-pattern": "womens-health",
        "syncope-fainting-pattern": "aha",
        "heart-palpitations": "aha",
        "acne-vulgaris": "aad",
    }
    for slug, source_slug in expected.items():
        assert slug in diseases
        assert any(row[0] == source_slug for row in diseases[slug].get("sources", [])), slug


def test_v74_no_duplicate_core_ids_and_all_conditions_have_sources():
    symptom_slugs = [row[0] for row in medical_knowledge.SYMPTOMS]
    disease_slugs = [row["slug"] for row in medical_knowledge.DISEASES]
    source_slugs = [row[0] for row in medical_knowledge.SOURCES]
    assert len(symptom_slugs) == len(set(symptom_slugs))
    assert len(disease_slugs) == len(set(disease_slugs))
    assert len(source_slugs) == len(set(source_slugs))
    assert all(d.get("sources") for d in medical_knowledge.DISEASES)


def test_v74_pages_show_live_expansion_counts_and_new_source_families():
    web = source_bundle.webapp_text()
    assert '"search_topics": len(getattr(health_search, "SEARCH_KB", {}) or {})' in web
    assert "__STAT_SEARCH__" in web
    assert ("موضوعات في البحث الصحي" in web) or ("أعراض متاحة للبحث الصحي" in web)
    assert "NIDCR" in web and "NIAMS" in web and "AHA" in web
    assert "تغطية المحتوى الحالية" in web
    assert "روابط مباشرة بين الحالات والمراجع" in web
    exp = (ROOT / "medical_knowledge_expansion_v6.py").read_text(encoding="utf-8")
    assert "womens-health" in exp and "aad" in exp


def test_v74_source_domains_are_allowlisted_and_version_updated():
    assert {"womenshealth.gov", "heart.org", "aad.org"}.issubset(medical_knowledge.DEFAULT_ALLOWED_DOMAINS)
    source = (ROOT / "medical_knowledge.py").read_text(encoding="utf-8")
    assert any(v in source for v in ("2026.09-v74-source-data-expansion", "2026.09-v75-search-symptom-expansion", "2026.09-v76-full-site-audit"))
