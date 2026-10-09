import source_bundle
from pathlib import Path

import medical_knowledge as mk

ROOT = Path(__file__).resolve().parent
CHAT = source_bundle.chat_view_text()
CHAT_MIRROR = source_bundle.chat_view_text()
WEB = source_bundle.webapp_text()
ANALYSIS = (ROOT / "analysis_core.py").read_text(encoding="utf-8")


def test_chat_mirror_stays_identical():
    assert CHAT == CHAT_MIRROR


def test_male_flow_does_not_offer_period_timing():
    assert "function symptomWorseOptions()" in CHAT
    assert "if (!sexIsFemale() || !cycleContextRelevant()) return common;" in CHAT
    assert "const worse=symptomWorseOptions();" in CHAT
    # The period label remains available for relevant female flows, but no longer
    # lives in the common array shown to every user.
    common_block = CHAT.split("function symptomWorseOptions()", 1)[1].split("function trackJourney", 1)[0]
    assert "const cycle = LANG==='ar' ? 'وقت الدورة' : 'During period';" in common_block
    common_array = common_block.split("const common =", 1)[1].split("if (!sexIsFemale()", 1)[0]
    assert "وقت الدورة" not in common_array
    assert "During period" not in common_array


def test_reproductive_clarification_is_split_by_selected_sex():
    assert "GENERIC_FEMALE_REPRODUCTIVE_CLAR" in CHAT
    assert "GENERIC_MALE_REPRODUCTIVE_CLAR" in CHAT
    assert "ألم شديد ومفاجئ في خصية واحدة" in CHAT
    assert "احتمال حمل أو حمل مؤكد" in CHAT
    assert "if(sexIsMale() && (maleReproductive.test(x) || pelvic.test(x)))" in CHAT
    assert "if(sexIsFemale() && (femaleReproductive.test(x) || pelvic.test(x)))" in CHAT


def test_differential_request_carries_gender_to_backend():
    assert "gender:state.gender" in CHAT
    assert "gender = str(data.get(\"gender\") or \"\").strip().lower()" in WEB
    assert "gender=gender" in WEB


def test_male_differential_excludes_female_reproductive_patterns():
    result = mk.differential_question(
        ["Breast tenderness", "Mood swings"], gender="m", lang="en"
    )
    candidate_slugs = {x["slug"] for x in result.get("candidates", [])}
    assert not (candidate_slugs & mk.FEMALE_ONLY_DISEASE_SLUGS)
    assert result.get("symptom_slug") not in mk.FEMALE_ONLY_SYMPTOM_SLUGS


def test_female_differential_keeps_relevant_female_questions():
    result = mk.differential_question(
        ["Pelvic pain", "Fatigue"], gender="f", lang="en"
    )
    candidate_slugs = {x["slug"] for x in result.get("candidates", [])}
    assert "endometriosis-pattern" in candidate_slugs
    assert result.get("symptom_slug") == "menstrual-cramps"


def test_full_knowledge_bundle_filters_female_patterns_for_male_only():
    male = mk.knowledge_bundle(
        ["Breast tenderness", "Mood swings"], age=25, lang="en", gender="m"
    )
    female = mk.knowledge_bundle(
        ["Breast tenderness", "Mood swings"], age=25, lang="en", gender="f"
    )
    male_slugs = {x.get("slug") for x in male.get("matches", [])}
    female_slugs = {x.get("slug") for x in female.get("matches", [])}
    assert not (male_slugs & mk.FEMALE_ONLY_DISEASE_SLUGS)
    assert "premenstrual-syndrome-pattern" in female_slugs


def test_analysis_core_passes_gender_into_knowledge_bundle():
    assert 'gender=d.get("gender")' in ANALYSIS
