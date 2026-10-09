from __future__ import annotations
import source_bundle

import ast
import io
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import medical_knowledge
import search_engine_v2

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.python_text()
CHAT = source_bundle.chat_view_text()


def test_v75_symptom_library_is_broader_and_source_grounded():
    rows = medical_knowledge.list_entities("symptoms", include_inactive=False, search="")
    assert len(rows) >= 280
    for slug in [
        "dry-cough", "eye-itching", "ear-pressure", "hip-pain",
        "radiating-leg-pain", "waking-unrefreshed", "calf-ache-standing",
    ]:
        row = next(r for r in rows if r["slug"] == slug)
        entity = medical_knowledge.get_entity("symptom", row["id"], public=True)
        assert entity
        assert entity.get("sources"), slug


def test_every_active_symptom_has_a_direct_source_for_library_search():
    rows = medical_knowledge.list_entities("symptoms", include_inactive=False, search="")
    unsourced = []
    for row in rows:
        entity = medical_knowledge.get_entity("symptom", row["id"], public=True)
        if not (entity or {}).get("sources"):
            unsourced.append(row["slug"])
    assert unsourced == []


def _slugs(query: str, lang: str = "ar") -> set[str]:
    return {x["slug"] for x in search_engine_v2.search(query, lang).get("recognized_symptoms", [])}


def test_multi_symptom_search_understands_three_arabic_symptoms_without_generic_duplicates():
    slugs = _slugs("كحة ناشفة وانفي يحكني وعيني تحكني", "ar")
    assert {"dry-cough", "nasal-itching", "eye-itching"} <= slugs
    assert "cough" not in slugs
    assert "itching" not in slugs


def test_multi_symptom_search_handles_common_combination_and_specificity():
    slugs = _slugs("رجلي تتشنج بالليل وعروقي بارزة", "ar")
    assert {"leg-cramps", "visible-varicose-veins"} <= slugs
    assert "seizure" not in slugs

    slugs = _slugs("فمي ناشف وريحة فمي", "ar")
    assert {"dry-mouth", "bad-breath"} <= slugs
    assert "dehydration" not in slugs


def test_multi_symptom_search_english_specificity():
    slugs = _slugs("leg cramps at night and bulging veins in legs", "en")
    assert {"leg-cramps", "visible-varicose-veins"} <= slugs
    assert "phlegm" not in slugs


def test_health_search_api_is_connected_to_full_active_symptom_library():
    assert "symptom_rows = medical_knowledge.list_entities(\"symptoms\", include_inactive=False, search=\"\")" in WEB
    assert "recognized_hits = [h for h in (v2_search.get(\"recognized_symptoms\") or []) if _hit_actually_in_query(h)][:8]" in WEB
    assert 'result["combined_summary"]' in WEB
    assert 'result["matched_topics"] = existing[:3]' in WEB
    assert "عدة أعراض" in WEB


def test_symptom_library_is_first_calculator_card():
    block = source_bundle.function_source("calculators_page")
    assert 'href="/health-library"' in block
    assert "library_card + \"\".join(" in block
    assert 'cards_html = library_card + "".join(' in block
    assert '("__CARDS__", cards_html)' in block


def test_report_and_feedback_buttons_use_direct_csp_safe_listeners():
    # Requested result actions should no longer depend on blocked inline onclick.
    assert 'data-result-action="download"' in CHAT
    assert 'class="ss-star-btn"' in CHAT
    assert 'data-star="' in CHAT
    assert "host.querySelectorAll('[data-result-action]').forEach" in CHAT
    assert "btn.addEventListener('click'" in CHAT
    assert "feedbackSubmitBtn.addEventListener('click',submitFeedback)" in CHAT
    assert "host.querySelectorAll('.ss-star-btn').forEach" in CHAT
    # Download keeps a current-result fallback for guests / unavailable saved records.
    assert "/api/analyze/export/" in CHAT
    assert "/api/analyze/export-current" in CHAT
    # Feedback explicitly sends same-origin credentials and structured context.
    assert "credentials:'same-origin'" in CHAT
    assert "context:'analysis_result'" in CHAT


def test_pdf_renderer_still_generates_pdf_and_includes_direct_explanation_source():
    tree = ast.parse(WEB)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_pdf_report")
    mod = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(mod)
    ns = {
        "io": io, "re": re, "logging": logging,
        "datetime": datetime, "timezone": timezone, "__name__": "v75_pdf_test",
    }
    exec(compile(mod, "<v75_pdf_test>", "exec"), ns)
    result = {
        "symptoms": ["صداع", "غثيان"], "duration": "يوم", "severity": 3,
        "age": 22, "gender": "f", "urgency": "low", "risk_label": "خطورة منخفضة",
        "data_quality": {"score": 100},
        "knowledge_matches": [{
            "name_ar": "الصداع النصفي", "score": "توافق جزئي", "why": "توجد أعراض متقاطعة.",
            "explanation_source": {
                "source_name": "NHS", "reference_title_ar": "Migraine — NHS",
                "reference_url": "https://www.nhs.uk/conditions/migraine/",
            },
        }],
        "recommendations": [{"title": "المتابعة", "tip": "راقب الأعراض."}],
        "medical_sources": [{
            "source_name": "NHS", "reference_title_ar": "Migraine — NHS",
            "reference_url": "https://www.nhs.uk/conditions/migraine/",
        }],
    }
    data = ns["_pdf_report"](result, "ar").getvalue()
    assert data.startswith(b"%PDF")
    assert len(data) > 1500


def test_pages_report_v75_search_expansion_not_old_v74_release_copy():
    assert "أعراض جديدة في V75" in WEB
    assert "ما الذي أُضيف في V75؟" in WEB
    assert "أعراض متاحة للبحث الصحي" in WEB
    assert "البحث الصحي يطابق مكتبة الأعراض النشطة ويجمع عدة أعراض في بحث واحد" in WEB
