import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()
DASH = (ROOT / "dashboard.py").read_text(encoding="utf-8")


def test_requested_brand_line_is_primary_home_message():
    assert "افهم أعراضك واعرف" in WEB
    assert "خطوتك التالية" in WEB
    assert "Understand your symptoms and" in WEB
    assert "know your next step" in WEB


def test_home_strength_surfaces_sources_and_coverage():
    for token in ("__STAT_SOURCES__", "__STAT_CONDITIONS__", "__STAT_SYMPTOMS__", "__STAT_RULES__", "__STAT_COVERAGE__"):
        assert token in WEB
    assert "معرفة صحية تستند إلى مصادر موثوقة" in WEB


def test_admin_navigation_is_compact_and_strength_is_visible():
    assert "projectStrengthStats" in DASH
    assert "قوة SymptoSense بالأرقام" in DASH
    assert "المعرفة والمصادر" in DASH
    assert "السلامة والجاهزية" in DASH
