"""V68.15: single KB stats source, changelog pages, optional accountability details, 997/911 wording."""
import importlib
import os

import webapp


def test_kb_stats_is_single_source_for_home_and_trust():
    import kb_stats
    kb = kb_stats.get_kb_stats()
    assert kb["origin"] == "database"
    trust = webapp._public_trust_snapshot()["knowledge"]
    assert trust["verified_sources"] == kb["sources"]
    assert trust["symptoms"] == kb["symptoms"]
    assert trust["conditions"] == kb["conditions"]
    assert trust["red_flag_rules"] == kb["red_flags"]
    assert trust["coverage"]["symptoms_total"] == kb["symptoms"]
    assert trust["coverage"]["symptoms_linked"] == kb["symptoms_linked"] <= kb["symptoms"]
    webapp._refresh_home_knowledge_snapshot_background()
    home = webapp._home_knowledge_snapshot()
    assert home["verified_sources"] == kb["sources"]
    assert home["symptoms"] == kb["symptoms"]


def test_changelog_pages_exist_and_are_linked_and_in_sitemap():
    c = webapp.app.test_client()
    for lang, word in (("ar", "سجل التحديثات"), ("en", "Changelog")):
        r = c.get("/%s/changelog" % lang)
        assert r.status_code == 200
        body = r.get_data(as_text=True)
        assert word in body and "V76" in body and "V75" in body
    assert "/changelog" in c.get("/sitemap.xml").get_data(as_text=True)
    assert 'href="/ar/changelog"' in c.get("/ar/about").get_data(as_text=True)
    sources = c.get("/ar/how-we-work").get_data(as_text=True)
    assert "مراجعة V76" not in sources


def test_accountability_lines_only_when_configured(monkeypatch):
    import trust_pages
    for name in ("MEDICAL_REVIEWER_NAME", "ACADEMIC_SUPERVISOR_NAME", "CONTACT_EMAIL"):
        monkeypatch.setattr(trust_pages, name, "")
    assert trust_pages.accountability_html(True) == ""
    monkeypatch.setattr(trust_pages, "MEDICAL_REVIEWER_NAME", "<b>Dr</b>")
    monkeypatch.setattr(trust_pages, "CONTACT_EMAIL", "team@example.com")
    out = trust_pages.accountability_html(False)
    assert "&lt;b&gt;Dr" in out and "<b>Dr" not in out
    assert 'href="mailto:team@example.com"' in out


def test_emergency_page_lists_997_first_and_regional_911():
    c = webapp.app.test_client()
    body = c.get("/ar/emergency").get_data(as_text=True)
    cards = body[body.index('class="em-'):]
    assert cards.index("997") < cards.index("911")
    assert "الرياض ومكة المكرمة والمدينة المنورة والمنطقة الشرقية" in body
    assert 'href="tel:999"' in body and 'href="tel:998"' in body
