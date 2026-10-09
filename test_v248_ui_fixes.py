"""Regression tests for the V248 mobile/desktop UI fixes."""
import source_bundle
import re
from pathlib import Path

import webapp

ROOT = Path(__file__).resolve().parent
CHAT = source_bundle.chat_view_text()
WEB = source_bundle.webapp_text()


def _served_css():
    css = webapp.BASE_CSS + webapp.V2_CSS + webapp.PREMIUM_POLISH_CSS
    for name in ("design-system.css", "v83_user_tools.css", "offline.css"):
        css += (ROOT / name).read_text(encoding="utf-8")
    css += " ".join(re.findall(r"<style[^>]*>(.*?)</style>", CHAT, re.S))
    return css + WEB


def test_classes_used_by_chat_view_are_not_styled_only_in_the_unloaded_v111_css():
    served = _served_css()
    v111 = (ROOT / "app-shell-v111.css").read_text(encoding="utf-8")
    used = set(re.findall(r'class="([^"]+)"', CHAT)) | set(re.findall(r"className\s*=\s*'([^']+)'", CHAT))
    tokens = {t for u in used for t in u.split() if re.fullmatch(r"[A-Za-z][\w-]{3,}", t)}
    orphaned = sorted(t for t in tokens if ("." + t) not in served and ("." + t) in v111)
    assert not orphaned, f"styled only in app-shell-v111.css (never loaded): {orphaned}"


def test_symptom_continue_button_stays_sticky_above_the_bottom_nav():
    css = webapp.PREMIUM_POLISH_CSS
    assert ".start-btn.start-btn.is-next" in css and "position:sticky!important" in css and "bottom:8px!important" in css


def test_consent_error_is_shown_next_to_the_required_checkbox():
    assert "art.insertAdjacentElement('afterend',err)" in WEB
    assert "consent-invalid" in WEB


def test_readiness_panel_shows_complete_instead_of_required_for_provided_fields():
    assert "f.status==='provided'?(LANG==='ar'?'مكتمل':'Complete')" in CHAT


def test_home_hero_cards_are_localized_not_hardcoded_english():
    assert "<b>Data Science</b>" not in WEB and "<b>Digital Health</b>" not in WEB
    assert "__TECH_DATA__" in WEB and '"__TECH_DATA__": bi("بيانات", "Data")' in WEB


def test_touch_targets_rule_exists():
    assert "min-height:44px" in webapp.PREMIUM_POLISH_CSS and ".hl-chip" in webapp.PREMIUM_POLISH_CSS
