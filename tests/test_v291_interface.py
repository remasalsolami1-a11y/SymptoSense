"""V291: interface review — one line-icon set, readable text, start button first on phones,
clear home figures, assistant button off key pages, Arabic footer, English wording."""
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import ui_icons
import webapp

ROOT = Path(__file__).resolve().parents[1]
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")


@pytest.fixture(scope="module")
def client():
    return webapp.app.test_client()


def _get(client, path):
    return client.get(path, follow_redirects=True).get_data(as_text=True)


def test_every_icon_is_well_formed_decorative_svg():
    assert len(ui_icons.ICONS) >= 25 and "ISC" in ui_icons.LICENSE or "Permission to use" in ui_icons.LICENSE
    for name in ui_icons.ICONS:
        svg = ui_icons.svg(name, 20, "x")
        root = ET.fromstring(svg)
        assert root.tag.endswith("svg") and root.get("aria-hidden") == "true" and root.get("focusable") == "false"
        assert root.get("stroke") == "currentColor" and "<svg" not in svg[5:], name
        assert len(list(root)) >= 1, name


def test_home_uses_line_icons_not_emoji_in_icon_slots(client):
    for path in ("/ar/", "/en/"):
        html = _get(client, path)
        main = html[html.index('<main class="ss-home-shell"'):html.index("</main>")]
        for cls in ("ss-core-icon", "ss-how-icon", "ss-trust-ic"):
            slots = re.findall(r'class="%s">(.*?)</(?:span|i)>' % cls, main, re.S)
            assert slots and all("<svg" in s and not EMOJI.search(re.sub(r"<[^>]+>", "", s)) for s in slots), (path, cls)
        tools = re.findall(r'<a class="ss-tool"[^>]*><span class="ic">(.*?)</span>', main, re.S)
        assert len(tools) == 10 and all(t.startswith("<svg") for t in tools)


def test_bottom_bar_header_and_assistant_button_use_icons(client):
    html = _get(client, "/ar/")
    nav = html[html.index('id="ssBnav"'):]
    nav = nav[:nav.index("</nav>")]
    assert nav.count('<span class="bn-icon" aria-hidden="true"><svg') == 4 and not EMOJI.search(nav)
    fab = re.search(r'<button type="button" class="asst-fab" id="asstFab".*?</button>', html, re.S).group(0)
    assert "ic-open" in fab and "ic-close" in fab and "🤖" not in fab and "pulse" not in fab
    head = html[html.index('<header class="ss-mobile-head"'):html.index("</header>")]
    assert head.count("<svg") == 2 and "🌐" not in head and "👤" not in head
    frame = (ROOT / "inline_assets" / "PAGE_FRAME.html").read_text(encoding="utf-8")
    assert "f.classList.toggle('is-open', open);" in frame and "'✕' : '🤖'" not in frame


def test_assistant_button_is_hidden_on_pages_where_it_covered_content():
    frame = (ROOT / "inline_assets" / "PAGE_FRAME.html").read_text(encoding="utf-8")
    m = re.search(r"\(\^\|\\/\)\(([a-z|-]+)\)", frame)
    assert m and set(m.group(1).split("|")) >= {"emergency", "live-demo", "login", "register", "consent", "chat"}
    assert "html.ss-no-fab .asst-fab{display:none!important}" in (ROOT / "inline_assets" / "V291_SHARED_CSS.css").read_text(encoding="utf-8")


def test_emergency_cards_use_icons(client):
    html = _get(client, "/ar/emergency")
    cards = re.findall(r'<div class="em-ic">(.*?)</div>', html, re.S)
    assert len(cards) == 3 and all(c.startswith("<svg") for c in cards)
    assert "__EMI_" not in html


def test_home_figures_are_four_clear_counts(client):
    n = json.loads((ROOT / "evaluation" / "results" / "e2e_results.json").read_text(encoding="utf-8"))["api_engine_agreement"]["n"]
    for path, label in (("/ar/", "حالة اختبار تُقاس عليها سلامة القرار"), ("/en/", "Test cases the safety decisions are measured on")):
        box = re.search(r'<section class="ss-strength.*?</section>', _get(client, path), re.S).group(0)
        stats = re.findall(r'<div class="ss-strength-stat[^"]*"><strong>([^<]+)</strong><span>([^<]+)</span>', box)
        assert len(stats) == 4
        assert (str(n), label) in stats
        assert len({v for v, _l in stats}) == 4  # no repeated number


def test_readability_and_layout_rules_are_loaded(client):
    home_css = (ROOT / "inline_assets" / "V291_HOME_CSS.css").read_text(encoding="utf-8")
    for rule in (".ss-hero-actions{grid-row:5!important", ".ss-hero-demo{grid-row:8!important", ".ss-home-hero::after{display:none!important}",
                 ".ss-demo-note{display:none!important}", ".ss-core-card p{font-size:14.5px!important"):
        assert rule in home_css, rule
    assert "V291_HOME_CSS.css" in (ROOT / "webapp.py").read_text(encoding="utf-8")
    css = client.get("/assets/app-shell-v112.css").get_data(as_text=True)
    assert ".footer .f-sec p,.footer .f-owner,.footer .f-tg{font-size:14.5px!important" in css
    html = _get(client, "/ar/")
    assert ".ss-hero-actions{grid-row:5!important" in html


def test_arabic_footer_has_no_english_line_and_english_footer_keeps_it(client):
    ar = _get(client, "/ar/")
    foot = ar[ar.index('<p class="f-love">'):]
    foot = foot[:foot.index("</p>")]
    assert "تصميم وتطوير" in foot and "Designed" not in foot
    en = _get(client, "/en/")
    assert "Designed &amp; Developed by" in en or "Designed & Developed by" in en


def test_english_wording_fixes():
    L = json.loads((ROOT / "inline_assets" / "L.json").read_text(encoding="utf-8"))["en"]
    CT = json.loads((ROOT / "inline_assets" / "CT.json").read_text(encoding="utf-8"))["en"]
    assert "AI Symptom Checker" not in L["title_landing"]
    assert L["nav_login"] == "Sign in" and L["nav_logout"] == "Sign out"
    assert "analysis model and the medical sources used in the system" not in L["home_s2_p"]
    assert CT["asst_emerg_btn"].endswith("→") and CT["fam_back"].startswith("←")
    assert "←" not in CT["asst_emerg_btn"]
