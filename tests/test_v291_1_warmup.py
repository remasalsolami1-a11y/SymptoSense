"""V291.1: the live demo computes once under a burst of first visitors, and heavy pages are
rendered once after start so the first real visitor does not wait."""
import threading

import live_demo
import railway_entrypoint
import webapp


def test_concurrent_cold_visits_compute_the_demo_once(monkeypatch):
    live_demo._CACHE.clear()
    calls = []
    real = live_demo.run
    monkeypatch.setattr(live_demo, "run", lambda sid, lang: calls.append(sid) or real(sid, lang))
    threads = [threading.Thread(target=live_demo.all_results, args=("ar",)) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(calls) == len(live_demo.SCENARIOS)
    assert live_demo._TTL >= 3600


def test_warmup_renders_heavy_pages_and_fills_the_demo_cache(caplog):
    live_demo._CACHE.clear()
    caplog.set_level("INFO")
    railway_entrypoint._warm_heavy_pages(webapp.app)
    assert {"ar", "en"} <= set(live_demo._CACHE)
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("warm-up path=")]
    assert len(lines) == len(railway_entrypoint.WARM_PATHS) and all("status=200" in l for l in lines)


def test_warmup_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("SYMPTOSENSE_WARMUP", "0")
    live_demo._CACHE.clear()
    railway_entrypoint._warm_heavy_pages(webapp.app)
    assert live_demo._CACHE == {}


def test_consent_page_never_leaves_the_visitor_stuck():
    import webapp as w
    html = w.app.test_client().get("/ar/consent?next=%2Far%2Fchat").get_data(as_text=True)
    # a slow save is retried once, then the error is shown next to the button
    assert "try{await save();}catch(first){await save();}" in html
    assert "btn.insertAdjacentElement('afterend',err)" in html
    # if the next page is slow to arrive, the visitor gets a visible link onward
    assert "setTimeout(function(){busy(false,oldText);showNear(" in html and "افتح تحليل الأعراض" in html
    # sent back here right after saving: tell the visitor cookies are blocked
    assert "ssConsentSavedAt" in html and "ملفات تعريف الارتباط" in html
    assert "__" + "OPEN__" not in html and "__" + "SLOW__" not in html and "__" + "COOKIE_ERR__" not in html


def test_result_shows_symptom_names_not_ids_and_arabic_confidence():
    import clinical_reasoning
    import medical_knowledge
    assert clinical_reasoning._symptom_name("stiff-neck", "ar") == "تيبس شديد في الرقبة"
    assert medical_knowledge._symptom_display_name("light-sensitivity", "en") == "Sensitivity to light"
    assert medical_knowledge._symptom_display_name("neck-pain", "ar") == "ألم الرقبة"
    from pathlib import Path
    js = (Path(__file__).resolve().parents[1] / "static" / "js" / "chat" / "analysis-result.js").read_text(encoding="utf-8")
    assert "m.negative_evidence_names||m.negative_evidence" in js
    assert "medium:LANG==='ar'?'متوسطة'" in js


def test_explain_simply_covers_library_topics_not_only_the_glossary():
    import webapp as w
    c = w.app.test_client()
    for term, lang in (("الدوخة", "ar"), ("Dizziness", "en"), ("الحمى", "ar"), ("السكري", "ar")):
        r = c.get("/api/explain", query_string={"term": term, "lang": lang}).get_json()["result"]
        assert r and all(r["levels"][k] for k in ("very_simple", "basic", "advanced")), term
        assert len(r["levels"]["very_simple"]) <= len(r["levels"]["basic"]) <= len(r["levels"]["advanced"])
    dz = c.get("/api/explain", query_string={"term": "الدوخة", "lang": "ar"}).get_json()["result"]["levels"]
    assert "من الأسباب الشائعة" in dz["basic"] and "متى تراجع الطبيب" in dz["advanced"] and "متى تستدعي الانتباه" in dz["advanced"]
    # glossary terms keep their hand-written levels; nonsense still gets "no explanation"
    assert c.get("/api/explain", query_string={"term": "anemia", "lang": "en"}).get_json()["result"].get("source") is None
    assert c.get("/api/explain", query_string={"term": "كلمة غير طبية xyz", "lang": "ar"}).get_json()["result"] is None


def test_bottom_bar_marks_the_current_tab_and_page_ends_above_it():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    frame = (root / "inline_assets" / "PAGE_FRAME.html").read_text(encoding="utf-8")
    assert "function ssMarkBnav()" in frame and "document.addEventListener('DOMContentLoaded', ssMarkBnav)" in frame
    assert "location.pathname.replace(/^\\/(ar|en)(?=\\/|$)/, '')" in frame
    css = (root / "inline_assets" / "V291_SHARED_CSS.css").read_text(encoding="utf-8")
    assert "html body:has(.footer){padding-bottom:0!important}" in css
    assert "html body .ss-bnav a.on .bn-icon{background:#E3EFFB!important" in css


def test_contact_is_the_project_email_not_telegram():
    import webapp as w
    c = w.app.test_client()
    home = c.get("/ar/").get_data(as_text=True)
    foot = home[home.index('<div class="footer"'):]
    assert 'class="f-tg" href="mailto:symptosense@outlook.com"' in foot and "t.me/" not in foot
    contact = c.get("/ar/contact").get_data(as_text=True)
    assert 'href="mailto:symptosense@outlook.com"' in contact and "t.me/" not in contact
    assert "symptosense@outlook.com" in contact


def test_phone_layout_is_decluttered_without_touching_larger_screens():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    home = (root / "inline_assets" / "V291_HOME_CSS.css").read_text(encoding="utf-8")
    shared = (root / "inline_assets" / "V291_SHARED_CSS.css").read_text(encoding="utf-8")
    block = home[home.index("V291.2 phones only: calmer home"):]
    assert block.split("{", 1)[0].endswith("@media (max-width:767px)")
    # V292.1: nothing on the home page is hidden on phones any more; the phone layout gets more room instead
    import re
    for sel in (".ss-trust-links", ".ss-knowledge-sources", ".ss-core-open", ".ss-hero-kicker"):
        assert not re.search(re.escape(sel) + r"[^{}]*\{display:none", home), sel
    # V292.1 (owner's choice): on phones the body drawing sits under the title; only the example result card is left out
    assert not re.search(r"\.ss-hero-demo\{display:none", home)
    assert ".ss-hero-demo{grid-row:3!important" in home and ".ss-hero-demo .ss-result-card," in home
    assert "nothing hidden" in home and ".ss-core-grid{gap:14px!important}" in home
    assert "f-sec:not([data-sec=\"contact\"])" not in shared and ".chat-start .cs-logo" not in shared
    sblock = shared[shared.index("V291.2 phones only: one layer"):]
    assert "@media (max-width:767px){html body #main-content>.card{border:0!important" in sblock
    assert "html body .em-card{display:grid!important" in sblock


def test_phone_pages_use_one_side_margin_and_fluid_text():
    from pathlib import Path
    css = (Path(__file__).resolve().parents[1] / "inline_assets" / "V291_SHARED_CSS.css").read_text(encoding="utf-8")
    block = css[css.index("V291.3 phones: the page fits the screen"):]
    assert "padding-left:max(16px,env(safe-area-inset-left))!important" in block
    assert "font-size:clamp(14.5px,3.9vw,16px)" in block and "h1{font-size:clamp(23px,6.6vw,29px)" in block


def test_consent_given_before_sign_in_carries_to_the_account():
    import db
    import privacy_features as pf
    import uuid
    db.init_db()
    uid, _ = db.create_ss_user("carry-%s@example.test" % uuid.uuid4().hex[:8], "Carry Tester", "CarryPass-2026!")
    mirror = {"service_usage": True, "analytics_research": False, "research_participation": False,
              "consent_version": pf.CONSENT_VERSION, "privacy_policy_version": pf.PRIVACY_POLICY_VERSION}
    assert pf.adopt_guest_consent(uid, mirror) is True
    state = pf.get_consent("account-%s" % uid, uid)
    assert state["service_usage"] and not state["needs_review"] and not state["analytics_research"]
    # the account's own choice is never overwritten, and an old-version or no-service mirror is ignored
    assert pf.adopt_guest_consent(uid, dict(mirror, analytics_research=True)) is False
    assert pf.adopt_guest_consent(uid, dict(mirror, consent_version="old")) is False
    assert pf.adopt_guest_consent(uid, dict(mirror, service_usage=False)) is False


def test_family_save_follows_the_consent_redirect():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "pagelib" / "pages_html.py").read_text(encoding="utf-8")
    assert "if (d.consent_required && d.consent_url) { location.href = d.consent_url; return; }" in src


def test_assistant_reply_is_tidied_before_display():
    import assistant_tidy as a
    t = "أسباب شائعة: التوتر وقلة النوم. استخدم /chat أو /checkin للمتابعة. تذكّر إن هالمعلومات توعوية"
    out = a.tidy(t, "ar")
    assert "/chat" not in out and "صفحة تحليل الأعراض" in out and "المتابعة اليومية" in out
    assert out.endswith("للمتابعة.")
    # never cut away an emergency number
    assert a.tidy("الأعراض شديدة. اتصل بالإسعاف 997 فورًا لو", "ar").endswith("997 فورًا لو")
    assert a.tidy("Open /en/chat to start.", "en") == "Open the symptom check page to start."


def test_lab_report_header_line_is_not_read_as_a_test():
    import blood_test as bt
    text = ("Al Borg Laboratories      Sample date: 2026-11-18\nPatient: Test  Age: 52 Y\n"
            "Potassium            6.4      H     mmol/L   3.5-5.1\nVitamin X  12  ng/mL  30-100\n")
    rows = bt.parse_blood_text(text)
    rows = rows[0] if isinstance(rows, tuple) else rows
    names = " ".join(str(r.get("name") or r.get("key")) for r in rows)
    values = [r.get("value") for r in rows]
    assert 2026.0 not in values and "Borg" not in names
    assert 6.4 in values and 12.0 in values


def test_blood_analysis_works_without_research_consent_and_stays_out_of_research_data():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    labs = (root / "routes" / "labs.py").read_text(encoding="utf-8")
    assert '"error": "blood_collection_consent_required"' not in labs
    assert '"blood_collection_consent": bool(collection_consent_ok)' in labs
    assert 'request.form.get("blood_collection_consent") or "").strip() == "0"' in labs
    page = (root / "pagelib" / "pages_html.py").read_text(encoding="utf-8")
    assert "function bloodConsentAccepted(){ return true; }" in page
    assert "fd.append('blood_collection_consent',bloodResearchConsent()?'1':'0');" in page
    assert "اختياري: المساهمة في تطوير المشروع" in page
    db_src = (root / "db.py").read_text(encoding="utf-8")
    assert "if data.get('blood_collection_consent') is not True:" in db_src  # research export filter unchanged


def test_unticking_blood_research_box_withdraws_the_stored_consent():
    import db
    import uuid
    db.init_db()
    owner = "account-qa-%s" % uuid.uuid4().hex[:8]
    db.save_blood_collection_consent(owner, "v-test")
    assert db.has_blood_collection_consent(owner, "v-test")
    db.withdraw_blood_collection_consent(owner)
    assert not db.has_blood_collection_consent(owner, "v-test")


def test_footer_columns_layout_on_every_screen():
    from pathlib import Path
    css = (Path(__file__).resolve().parents[1] / "inline_assets" / "V291_SHARED_CSS.css").read_text(encoding="utf-8")
    block = css[css.index("V292.1 footer: three tidy columns"):]
    P = "html body:not(#ss-f292) .footer"
    assert P + " .f-grid{display:grid!important;grid-template-columns:minmax(0,1.5fr) minmax(0,1fr) minmax(0,1fr)!important" in block
    assert "@media (max-width:600px){" + P + " .f-inner{padding:32px 16px 16px!important}" + P + " .f-grid{grid-template-columns:1fr!important" in block
    assert P + " .f-bottom{display:flex!important;justify-content:space-between!important" in block



def test_tools_strip_starts_on_the_left_and_scrolls_right():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    home = (root / "inline_assets" / "V291_HOME_CSS.css").read_text(encoding="utf-8")
    P = "html body.ss-home-page:not(#ss-v291):not(#ss-v292):not(#ss-v293)"
    assert P + " .ss-tools-scroll," + P + " .ss-tools-dots{direction:ltr!important}" in home
    assert P + " .ss-tools-scroll>.ss-tool{direction:rtl!important}" in home
    assert "__ALL_TOOLS__ →" in (root / "pagelib" / "pages_html.py").read_text(encoding="utf-8")
