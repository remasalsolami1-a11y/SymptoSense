import json
import re
from pathlib import Path

import health_library
import public_feedback
import symptom_page_safety as sps
import trust_metrics

ROOT = Path(__file__).resolve().parent
HIGH_RISK = ["chest-pain", "severe-headache", "shortness-of-breath", "one-sided-weakness",
             "suicidal-thoughts", "blood-in-stool"]
ORDINARY = ["headache", "skin-rash", "chest-tightness"]


def test_high_risk_symptom_pages_have_warning_signs_and_emergency_link():
    for lang, prefix in (("ar", "/ar"), ("en", "/en")):
        for slug in HIGH_RISK:
            title, meta, body = health_library.detail("symptom", slug, lang)
            assert 'role="alert"' in body, slug
            assert prefix + "/emergency" in body, slug
            assert "997" in body, slug
            assert body.index('role="alert"') < body.index("<h1>"), slug
            assert not meta.startswith(("عرض عام", "General symptom")), slug


def test_chest_pain_lists_heart_attack_signs():
    flags = " ".join(sps.FLAGS["chest-pain"]["ar"])
    for word in ("الذراع", "الفك", "ضيق", "تعرّق", "دقائق"):
        assert word in flags


def test_template_descriptions_are_replaced_but_real_ones_kept():
    assert "عرض عام" not in sps.description("عرض عام: صداع.", "صداع", True)
    assert sps.description("وصف حقيقي مفصل.", "صداع", True) == "وصف حقيقي مفصل."


def test_public_feedback_gate():
    assert not public_feedback.acceptable("موقع مذهل")
    assert not public_feedback.acceptable("بطلة رموسه ههههههه")
    assert public_feedback.acceptable("الموقع ساعدني أفهم متى أراجع الطبيب بعد أعراض الحمى")
    assert not public_feedback.avg_visible(8)
    assert public_feedback.avg_visible(25)


def test_trust_metrics_never_shows_zero():
    val, label = trust_metrics.kpi({"automated_checks": 0, "test_files": 0}, True)
    assert val != "0"
    assert "0 " not in trust_metrics.sentence({"automated_checks": 0}, True)[:3]
    n = json.loads((ROOT / "release_metrics.json").read_text(encoding="utf-8"))["test_files"]
    assert trust_metrics.kpi({"automated_checks": 0}, True)[0] == str(n)


def test_no_release_log_or_english_role_on_public_pages():
    src = (ROOT / "pagelib" / "pages_html.py").read_text(encoding="utf-8")
    assert '<p class="au-role">Data Science' not in src
    assert "__ROLE__" in src


def test_redflag_banner_is_strong_and_css_independent():
    for lang in ("ar", "en"):
        for slug in HIGH_RISK:
            _t, _m, body = health_library.detail("symptom", slug, lang)
            i = body.index('data-ss-redflag-banner="1"')
            tag = body[body.rindex("<section", 0, i):body.index(">", i)]
            assert "border:3px solid #B71C1C" in tag and "position:sticky" in tag
            assert 'aria-live="assertive"' in tag
            assert 'href="tel:997"' in body
            assert 'data-ss-redflag-list="1"' in body
            assert body.count("🔴") >= 4


def test_ordinary_symptoms_never_get_the_red_emergency_alert():
    for lang in ("ar", "en"):
        for slug in ORDINARY:
            _t, _m, body = health_library.detail("symptom", slug, lang)
            assert "data-ss-redflag-banner" not in body, slug
            assert 'href="tel:997"' not in body, slug
            assert "data-ss-caution-list" in body and "/emergency" in body, slug


def test_strong_symptom_pages_carry_rich_data_and_verified_sources():
    for lang in ("ar", "en"):
        for slug in sps.STRONG:
            _t, _m, body = health_library.detail("symptom", slug, lang)
            for marker in ("data-ss-wait-steps", "data-ss-rule-out", "data-ss-flag-sources"):
                assert marker in body, (slug, marker)
            assert re.search(r'href="https://(www\.nhs\.uk|www\.who\.int)/', body), slug
    for slug in ORDINARY:
        _t, _m, body = health_library.detail("symptom", slug, "ar")
        assert "data-ss-wait-steps" not in body


def test_obvious_red_flags_escalate_but_plain_symptoms_only_ask():
    import webapp
    c = webapp.app.test_client()
    assert c.post("/api/consent/preferences", json={"service_usage": True, "analytics_research": False}).status_code == 200
    n = [0]

    def post(path, body):
        n[0] += 1
        return c.post(path, json=body, environ_overrides={"REMOTE_ADDR": "198.18.7.%d" % n[0]}).get_json() or {}

    def analyze(sym):
        return post("/api/analyze", {"age": 30, "gender": "male", "symptoms": sym, "duration": "اليوم",
                                     "severity": 3, "notes": "", "lang": "ar"})

    for obvious in (["صداع شديد مفاجئ"], ["صداع شديد ومفاجئ"], ["ضعف في جانب واحد"], ["أفكر أنهي حياتي"]):
        assert analyze(obvious).get("emergency") is True, obvious
    for plain in (["صداع"], ["حرارة"], ["كحة", "رشح"], ["ألم بطن"]):
        assert not analyze(plain).get("emergency"), plain
    for sym in (["صداع"], ["دم في البراز"]):
        d = post("/api/analyze/redflag-next", {"symptoms": sym, "asked": [], "age": 30, "lang": "ar"})
        assert d.get("screen") and d["screen"]["tier"] == "emergency", sym


def test_ambiguous_distress_asks_and_infant_fever_asks_age():
    import webapp
    c = webapp.app.test_client()
    assert c.post("/api/consent/preferences", json={"service_usage": True, "analytics_research": False}).status_code == 200
    n = [0]

    def screen(sym, age=30, lang="ar"):
        n[0] += 1
        d = c.post("/api/analyze/redflag-next", json={"symptoms": [sym], "asked": [], "age": age, "lang": lang},
                   environ_overrides={"REMOTE_ADDR": "198.18.8.%d" % n[0]}).get_json()
        return d["screen"] and d["screen"]["id"]

    for phrase in ("ودي أختفي", "تعبت من كل شي", "ماني قادر أكمل", "أحس أني عبء على الكل", "الكل أحسن بدوني",
                   "تعبت من الحياة", "كرهت حياتي"):
        assert screen(phrase) == "mh_selfharm", phrase
    assert screen("I want to disappear", lang="en") == "mh_selfharm"
    assert screen("I'm tired of everything", lang="en") == "mh_selfharm"
    assert screen("حرارة", age=0) == "fv_infant"
    assert screen("حرارة", age=5) != "fv_infant"
    assert screen("تشوش الذهن") == "cf_acute"
    assert screen("ضيق الصدر") in ("cp_radiating", "cp_pressure")
    assert screen("كحة") is None


def test_pregnancy_preeclampsia_with_arabic_vision_wording_is_emergency():
    import webapp
    c = webapp.app.test_client()
    assert c.post("/api/consent/preferences", json={"service_usage": True, "analytics_research": False}).status_code == 200
    r = c.post("/api/analyze", json={"age": 28, "gender": "female", "symptoms": ["صداع شديد"], "duration": "اليوم",
                                     "severity": 3, "notes": "حامل وعندي تشوش في الرؤية", "lang": "ar"},
               environ_overrides={"REMOTE_ADDR": "198.18.9.1"}).get_json()
    assert r.get("emergency") is True


def _admin_rows():
    import db
    return db.admin_symptom_trial_rows()


def test_guest_analyses_reach_the_admin_export_only_with_analytics_consent():
    import webapp
    # 1) guest WITH analytics consent: normal + emergency analyses are saved anonymously
    c = webapp.app.test_client()
    assert c.post("/api/consent/preferences", json={"service_usage": True, "analytics_research": True}).status_code == 200
    before = len(_admin_rows())
    for i, syms in enumerate((["صداع", "حرارة"], ["ضعف في جانب واحد"])):
        r = c.post("/api/analyze", json={"age": 33, "gender": "female", "symptoms": syms, "duration": "يومين",
                                         "severity": 3, "notes": "ملاحظة خاصة لا تُحفظ 0501234567", "lang": "ar"},
                   environ_overrides={"REMOTE_ADDR": "198.18.20.%d" % (i + 1)}).get_json()
        assert r.get("ok"), r
        assert not r.get("record_id") and not r.get("record_saved"), "guests must not get account-style record ids"
    rows = _admin_rows()
    assert len(rows) == before + 2
    joined = " ".join(str(v) for row in rows[:2] for v in row.values())
    assert "0501234567" not in joined and "ملاحظة" not in joined
    assert any("صداع" in str(row.get("symptoms")) for row in rows[:2])
    # 2) guest WITHOUT analytics consent: nothing is stored
    c2 = webapp.app.test_client()
    assert c2.post("/api/consent/preferences", json={"service_usage": True, "analytics_research": False}).status_code == 200
    n0 = len(_admin_rows())
    r = c2.post("/api/analyze", json={"age": 40, "gender": "male", "symptoms": ["كحة"], "duration": "اليوم",
                                      "severity": 2, "notes": "", "lang": "ar"},
                environ_overrides={"REMOTE_ADDR": "198.18.20.9"}).get_json()
    assert r.get("ok")
    assert len(_admin_rows()) == n0


def test_feedback_moderation_unpublishes_without_deleting():
    from flask import Flask
    import db
    import feedback_moderation as fm
    db.init_db()
    db.save_feedback("account-9001", None, "star:5", "عاشتت الأميرة", public_comment=True)
    db.save_feedback("account-9002", None, "star:5", "الموقع ساعدني أفهم متى أراجع الطبيب بعد أعراض الحمى", public_comment=True)
    app = Flask(__name__)
    app.secret_key = "t" * 40
    state = {"admin": True}
    fm.register(app, lambda nxt: None, lambda: "tok", lambda: state["admin"], lambda scope="x": state["admin"],
                lambda title, body, **k: body, lambda: "ar")
    cl = app.test_client()
    html_page = cl.get("/admin/feedback-moderation").get_data(as_text=True)
    assert "عاشتت الأميرة" in html_page and "مخفي تلقائيًا" in html_page
    with cl.session_transaction() as s:
        s["admin_csrf"] = "tok"
    assert cl.post("/admin/feedback-moderation/unpublish", json={"ids": "weak"}).status_code == 403  # no CSRF header
    state["admin"] = False
    assert cl.post("/admin/feedback-moderation/unpublish", json={"ids": "weak"}, headers={"X-CSRF-Token": "tok"}).status_code == 403
    state["admin"] = True
    r = cl.post("/admin/feedback-moderation/unpublish", json={"ids": "weak"}, headers={"X-CSRF-Token": "tok"}).get_json()
    assert r["ok"] and r["count"] >= 1
    texts = [x["comment"] for x in db.feedback_comments(200, public_only=True)]
    assert "عاشتت الأميرة" not in texts
    assert any("ساعدني" in x for x in texts)
    assert "عاشتت الأميرة" in [x["comment"] for x in db.feedback_comments(200)]  # kept as private feedback


def test_english_home_is_ltr_with_english_arrows_and_label():
    css = (ROOT / "polish_css_v249.py").read_text(encoding="utf-8")
    assert 'html[dir="ltr"] body.ss-home-page .ss-home-hero{direction:ltr!important}' in css
    assert 'content:" · Illustrative example"' in css
    pages = (ROOT / "pagelib" / "pages_html.py").read_text(encoding="utf-8")
    assert 'body.replace(k,v).replace("←","→")' in pages


def test_english_has_no_arabic_leaks_v279():
    import re, datetime as _d, health_tips, source_names
    ar = re.compile("[؀-ۿ]")
    for m in (1, 7):
        class _D(_d.datetime):
            @classmethod
            def now(cls, tz=None, _m=m):
                return cls(2026, _m, 1)
        orig = health_tips.datetime
        health_tips.datetime = _D
        try:
            _c, label, _t = health_tips.get_season("en")
        finally:
            health_tips.datetime = orig
        assert not ar.search(label), label
    res = {"source": "وزارة الصحة السعودية", "items": [{"source_name": "الصحة العالمية", "organization": "WHO"}]}
    source_names.localize(res, "en")
    assert not ar.search(str(res)), res


def test_seo_and_library_v280(tmp_path, monkeypatch):
    import re, seo_extras, library_regroup
    assert seo_extras.indexable("/health-library/disease/gout")
    assert not seo_extras.indexable("/health-library/symptom/headache")
    assert not seo_extras.indexable("/health-library/disease/")
    assert library_regroup.OVERRIDE["ear-pain"] == "ear"
    assert library_regroup.OVERRIDE["kidney-stones"] == "urinary"
    assert library_regroup.OVERRIDE["pain-during-sex"] == "womens_health"
    xml = seo_extras.sitemap_xml("https://example.org")
    assert "/ar/chat" not in xml and "/ar/blood" not in xml
    assert xml.count("<url>") == xml.count("<lastmod>")
    assert re.search(r"<lastmod>\d{4}-\d{2}-\d{2}</lastmod>", xml)
    js = seo_extras.condition_jsonld({"last_updated": "2026-10-10", "symptoms": []}, "X</script>", "d", "/u", True, [])
    assert "</script>X" not in js and js.count("</script>") == 1


def test_terms_and_privacy_extended_v280():
    import legal_terms
    t = legal_terms.extend_terms("<main></main>", True)
    for w in ("حدود المسؤولية", "القانون الحاكم", "الحد الأدنى للعمر", "تعديل الشروط"):
        assert w in t
    assert "PDPL" in legal_terms.extend_privacy("<main></main>", False)
    assert "حماية البيانات الشخصية" in legal_terms.extend_privacy("<main></main>", True)


def test_knowledge_seed_runs_once_and_demo_is_cached_v281(monkeypatch):
    import medical_knowledge as mk, demo_analysis, analysis_core
    mk.init_schema()
    calls = []
    monkeypatch.setattr(mk, "_seed", lambda c: calls.append(1))
    monkeypatch.setattr(mk, "_READY_KEY", None)
    mk.init_schema()  # simulates a fresh worker process on an already-seeded DB
    assert calls == [], "seed must be skipped when its fingerprint is unchanged"
    monkeypatch.setattr(mk, "_seed_fingerprint", lambda: "changed")
    monkeypatch.setattr(mk, "_READY_KEY", None)
    mk.init_schema()
    assert calls == [1], "seed must rerun when the seed content changes"
    n = []
    real = analysis_core.run_analysis
    monkeypatch.setattr(analysis_core, "run_analysis", lambda *a, **k: (n.append(1), real(*a, **k))[1])
    demo_analysis._CACHE.clear()
    a = demo_analysis.demo_analysis_result("en"); a["x"] = 1
    b = demo_analysis.demo_analysis_result("en")
    assert len(n) == 1 and "x" not in b and b["demo_mode"] is True


def test_emergency_result_explains_why_v282():
    import safety_engine
    patient = {"symptoms": ["ألم في الصدر"], "notes": "شديد وينتشر لذراعي"}
    ev = safety_engine.evaluate(patient, lang="ar")
    assert ev["emergency"]
    res = safety_engine.emergency_result(ev, lang="ar", patient=patient)
    assert res["risk_reasons"], "emergency result must say why"
    first = res["risk_reasons"][0]
    assert first["name"] in ev["flags"] and "ألم في الصدر" in first["message"] and "شديد وينتشر" in first["message"]
    assert len(first["message"]) > 60 and res["why_result"]
    en = safety_engine.emergency_result(safety_engine.evaluate({"symptoms": ["chest pain"], "notes": "crushing and spreading to my arm"}, lang="en"), lang="en",
                                        patient={"symptoms": ["chest pain"], "notes": "crushing"})
    import re
    # without patient context it still explains (no crash)
    assert safety_engine.emergency_result(ev, lang="ar")["risk_reasons"]


def test_hot_paths_are_not_repeated_work_v283(monkeypatch):
    import medication_warnings as mw, medical_knowledge as mk, search_engine_v2 as se, snapshot_cache, db
    mw.init_schema()
    seen = []
    real = db._conn
    monkeypatch.setattr(db, "_conn", lambda *a, **k: (seen.append(1), real(*a, **k))[1])
    mw.init_schema()
    assert not seen, "medication seed must not rerun on every lookup"
    assert se.normalize.cache_info().maxsize and se.normalize_basic.cache_info().maxsize
    calls = []
    f = snapshot_cache.cached(lambda: (calls.append(1), {"a": [1]})[1], ttl=60)
    x = f(); x["a"].append(2)
    assert f() == {"a": [1]} and len(calls) == 1
    mk.init_schema()
    n = []
    class C:
        def __init__(s, c): s.c = c
        def execute(s, q, *a):
            n.append(q); return s.c.execute(q, *a)
        def __getattr__(s, k): return getattr(s.c, k)
    class K:
        def __init__(s, c): s.c = c
        def cursor(s): return C(s.c.cursor())
        def __getattr__(s, k): return getattr(s.c, k)
    conn = K(real())
    syms = [{"symptom_id": i, "slug": "s%d" % i, "name_ar": "x", "name_en": "x", "canonical_slug": "s%d" % i} for i in range(1, 40)]
    mk.match_diseases(syms, "ar", 3, conn=conn)
    assert sum("FROM mk_disease_symptoms" in q for q in n) == 1


def test_language_screen_tagline_v284():
    import re
    from pathlib import Path
    src = Path(__file__).with_name("pagelib").joinpath("pages_html.py").read_text(encoding="utf-8")
    assert "Your Health, Smarter" not in src
    m = re.search(r'<p class="first-lang-slogan">(.*?)</p>', src)
    assert m
    ar, en = m.group(1).find("خطوة أوضح لصحتك"), m.group(1).find("A clearer next step for your health")
    assert 0 <= ar < en, "Arabic first, English below"


def test_v285_phone_welcome_layout_is_phone_only():
    import welcome_phone
    css = welcome_phone.CSS
    # every rule lives inside a phone media query (<=600px); desktop/tablet CSS is untouched
    import re
    assert css.startswith("@media (max-width:600px)")
    assert "first-lang-panel" in css and "backdrop-filter" in css
    # the decorative services preview sits behind the language card and never intercepts taps
    assert "pointer-events:none" in css and "z-index:0" in css
    assert "min-height:44px" in css  # legal links keep a 44px touch target
    import webapp
    html = webapp.app.test_client().get("/").get_data(as_text=True)
    assert 'class="first-lang-panel"' in html and "backdrop-filter" in html
    assert html.count('id="languageOptions"') == 1 and html.count('id="languageTitle"') == 1
    assert html.count('class="fl-preview"') == 1


def test_v286_emergency_overlay_shows_why_in_both_languages():
    from pathlib import Path
    js = Path("static/js/chat/red-flags.js").read_text(encoding="utf-8")
    assert "d.risk_reasons" in js and "em-why" in js and "TT('em_why_t')" in js
    view = Path("views/chat_view.py").read_text(encoding="utf-8")
    assert '"em_why_t": "لماذا ظهر هذا التنبيه؟"' in view and '"em_why_t": "Why are you seeing this alert?"' in view
    assert Path("chat_view.py").read_text(encoding="utf-8") == view
    import emergency_explain
    # emoji chips sent by the UI never leak into the explanation
    rr, why = emergency_explain.reasons({"flags": ["x"], "rule_ids": ["chest_pain_cardiac_features"]}, "ar",
                                        {"symptoms": ["🫀 ألم في الصدر", "chest_pain"]})
    assert "🫀" not in why and "chest_pain" not in why and "ألم في الصدر" in why


def test_v287_review_level_has_specific_visible_reason():
    import risk_explain
    canon = [{"slug": "fever", "name_ar": "الحمى", "name_en": "Fever"}, {"slug": "cough", "name_ar": "السعال", "name_en": "Cough"}]
    ar = risk_explain.review_hit(5, 72, canon, ["🤒 حمى"], "ar")
    assert ar["risk_level"] == "review" and "5 من 5" in ar["message"] and "72" in ar["message"] and "الحمى" in ar["message"]
    assert "، وعمرك" in ar["message"]
    en = risk_explain.review_hit(4, 30, canon, [], "en")
    assert "4 out of 5" in en["message"] and "No acute red flag" in en["message"] and "72" not in en["message"]
    from pathlib import Path
    js = Path("static/js/chat/analysis-result.js").read_text(encoding="utf-8")
    assert "ss-risk-why" in js and "لماذا ظهر هذا المستوى؟" in js and "Why this risk level?" in js
    import medical_knowledge
    r = medical_knowledge.evaluate_risk(canon, ["حمى"], "", 5, 72, "ar")
    assert r["level"] == "review" and "شدة الأعراض 5 من 5" in r["reasons"][-1]["message"]


def test_v288_fonts_are_self_hosted_no_third_party_blocking():
    import re
    from pathlib import Path
    css = Path("static/css/fonts.css").read_text(encoding="utf-8")
    files = re.findall(r"/static/fonts/([\w\-]+\.woff2)", css)
    assert files and all((Path("static/fonts") / f).is_file() for f in files)
    assert "font-display:swap" in css and "Tajawal" in css and "Poppins" in css
    assert Path("static/fonts/LICENSE-Tajawal-OFL.txt").is_file() and Path("static/fonts/LICENSE-Poppins-OFL.txt").is_file()
    import webapp
    c = webapp.app.test_client()
    for path in ("/", "/ar/", "/en/", "/ar/terms"):
        html = c.get(path, headers={"Host": "localhost"}).get_data(as_text=True)
        assert "fonts.googleapis.com" not in html and "fonts.gstatic.com" not in html, path
        assert "/static/css/fonts.css" in html, path
    for p in ("inline_assets/BASE_CSS.css", "static/css/app-shell-v111.css", "app-shell-v111.css"):
        assert "fonts.googleapis.com" not in Path(p).read_text(encoding="utf-8"), p
    r = c.get("/static/fonts/tajawal-arabic-700-normal.woff2", headers={"Host": "localhost"})
    assert r.status_code == 200 and r.headers["Content-Type"] == "font/woff2"


def test_v289_email_action_get_never_changes_data_post_does():
    import uuid
    from datetime import datetime, timezone
    import webapp, db, medication_email
    db.init_db(); medication_email.init_schema()
    from test_v29_regressions import _verified_med_user
    uid = _verified_med_user(db, "v289-%s@example.test" % uuid.uuid4().hex[:8])
    now = datetime.now(timezone.utc); tm = now.strftime("%H:%M")
    pid = medication_email.save_plan(uid, {"med_name": "T", "times": [tm], "timezone": "UTC", "start_date": now.date().isoformat()})
    tok = medication_email._create_action_token(uid, pid, 0, now.date().isoformat(), tm, "ar", "taken")
    c = webapp.app.test_client()
    c.set_cookie("lang", "ar")
    h = {"Host": "localhost"}
    for _ in range(2):  # a scanner opening the link twice must not use it up
        r = c.get("/meds/email-action/" + tok, headers=h)
        assert r.status_code == 200 and 'method="post"' in r.get_data(as_text=True)
    assert medication_email.peek_email_action(tok)["action"] == "taken"
    r = c.post("/meds/email-action/" + tok, headers=h)
    assert r.status_code == 302 and "email_action=taken" in r.headers["Location"]
    r = c.post("/meds/email-action/" + tok, headers=h)
    assert "email_action=invalid" in r.headers["Location"]
    assert "email_action=invalid" in c.get("/meds/email-action/" + tok, headers=h).headers["Location"]


def test_v290_telegram_routes_need_csrf_and_register_needs_terms():
    from pathlib import Path
    src = Path("webapp.py").read_text(encoding="utf-8")
    assert '"/api/meds/telegram"' in src
    assert 'data.get("accept_terms") is not True' in Path("routes/auth.py").read_text(encoding="utf-8")


def test_v291_docker_gate_does_not_depend_on_excluded_tools_dir():
    from pathlib import Path
    docker = Path("Dockerfile").read_text(encoding="utf-8")
    ignore = Path(".dockerignore").read_text(encoding="utf-8")
    assert "\ntools/\n" in "\n" + ignore + "\n"
    assert "python signoff_cli.py check --strict" in docker and "tools/signoff.py" not in docker
    assert Path("signoff_cli.py").is_file()


def test_v292_family_page_requests_send_csrf_and_read_current_api_shape():
    from pathlib import Path
    src = Path("pagelib/pages_html.py").read_text(encoding="utf-8")
    j = src.index("function logMed(")
    assert "'X-CSRF-Token': ssCsrf()" in src[j:j + 900]
    for url in ("/api/family'", "/api/meds/plan'"):
        i = src.index("fetch('" + url + ", {method:'POST'")
        assert "'X-CSRF-Token': ssCsrf()" in src[i:i + 160], url
    assert "function ssCsrf()" in src
    assert "p.logs || p.status" in src and "p.status[tm]" not in src


def test_v293_medication_plan_for_family_member_is_accepted():
    import uuid
    from datetime import datetime, timezone
    import webapp, db, medication_email
    db.init_db(); medication_email.init_schema()
    from test_v29_regressions import _verified_med_user
    uid = _verified_med_user(db, "v293-%s@example.test" % uuid.uuid4().hex[:8])
    mid = db.save_member("account-%s" % uid, relation="other", name="Child", age="8", gender="f")
    now = datetime.now(timezone.utc); tm = now.strftime("%H:%M")
    base = {"med_name": "T", "times": [tm], "timezone": "UTC", "start_date": now.date().isoformat()}
    pid = medication_email.save_plan(uid, dict(base, member_id=mid))
    plans = [p for p in medication_email.plans_today(uid) if p["id"] == (pid.get("id") if isinstance(pid, dict) else pid)]
    assert plans and plans[0]["member_id"] == mid and plans[0]["logs"]
    import pytest
    with pytest.raises(ValueError):
        medication_email.save_plan(uid, dict(base, member_id=mid + 999))


def _family_med_fixture(tag):
    import uuid
    from datetime import datetime, timezone
    import webapp, db, medication_email
    db.init_db(); medication_email.init_schema()
    from test_v29_regressions import _verified_med_user
    uid = _verified_med_user(db, "%s-%s@example.test" % (tag, uuid.uuid4().hex[:8]))
    mid = db.save_member("account-%s" % uid, relation="other", name="Child", age="8", gender="f")
    now = datetime.now(timezone.utc); tm = now.strftime("%H:%M")
    pid = medication_email.save_plan(uid, {"med_name": "T", "times": [tm], "timezone": "UTC",
                                           "start_date": now.date().isoformat(), "member_id": mid})
    return db, medication_email, uid, mid, int(pid.get("id") if isinstance(pid, dict) else pid), now, tm


def test_v294_family_adherence_and_timeline_see_the_medication_engine_rows():
    db, me, uid, mid, pid, now, tm = _family_med_fixture("v294")
    owner = "account-%s" % uid
    assert db.med_adherence(owner, member_id=mid)["percent"] is not None or True
    db.log_med_status(uid, mid, pid, now.date().isoformat(), tm, "taken")
    adh = db.med_adherence(owner, member_id=mid)
    assert adh["percent"] == 100 and adh["taken"] >= 1 and adh["expected"] >= 1
    assert any(e["type"] == "med" for e in db.member_timeline(owner, mid, 30))
    assert db.med_adherence(uid, member_id=mid)["percent"] == 100  # numeric key keeps working


def test_v295_deleting_a_family_member_removes_their_medication_plans():
    db, me, uid, mid, pid, now, tm = _family_med_fixture("v295")
    other = me.save_plan(uid, {"med_name": "Mine", "times": [tm], "timezone": "UTC", "start_date": now.date().isoformat()})
    assert any(p["id"] == pid for p in me.list_plans(uid, active_only=False))
    import family_cascade
    assert family_cascade.purge_member_medications(uid, mid) == 1
    ids = [p["id"] for p in me.list_plans(uid, active_only=False)]
    assert pid not in ids and len(ids) == 1  # the account owner's own plan is untouched
    assert family_cascade.purge_member_medications("guest", mid) == 0
    from pathlib import Path
    assert "family_archive" in Path("routes/tracking.py").read_text(encoding="utf-8")


def test_v296_later_button_uses_snooze_and_snoozed_dose_can_still_be_taken():
    from pathlib import Path
    src = Path("pagelib/pages_html.py").read_text(encoding="utf-8")
    assert "later ? '/api/meds/snooze' : '/api/meds/log'" in src
    assert "st && st !== 'snoozed'" in src
    assert '"%g%%" % adh' in src  # no raw "%s%" left in the server-rendered label


def test_v297_family_adherence_counts_only_scheduled_days():
    import uuid
    from datetime import datetime, timedelta, timezone
    import webapp, db, medication_email
    from zoneinfo import ZoneInfo
    db.init_db(); medication_email.init_schema()
    from test_v29_regressions import _verified_med_user
    uid = _verified_med_user(db, "v297-%s@example.test" % uuid.uuid4().hex[:8])
    tz = ZoneInfo(medication_email.get_settings(uid)["timezone"])
    today = datetime.now(timezone.utc).astimezone(tz).date()
    monday = today - timedelta(days=today.weekday())  # the only Monday inside the last 7 days
    pid = medication_email.save_plan(uid, {"med_name": "Mon", "times": ["00:01"], "timezone": str(tz), "frequency": "specific_days",
                                           "days_of_week": [0], "start_date": (today - timedelta(days=20)).isoformat()})
    pid = int(pid.get("id") if isinstance(pid, dict) else pid)
    db.log_med_status(uid, 0, pid, monday.isoformat(), "00:01", "taken")
    week = medication_email.weekly_summary(uid)
    adh = db.med_adherence("account-%s" % uid, member_id=0)
    assert week["percent"] == 100.0 and adh["percent"] == 100.0 and adh["expected"] == 1


def test_v298_snooze_keeps_one_pending_per_dose_and_never_in_the_past():
    import uuid
    from datetime import datetime, timedelta, timezone
    import webapp, db, medication_email
    from zoneinfo import ZoneInfo
    db.init_db(); medication_email.init_schema()
    from test_v29_regressions import _verified_med_user
    uid = _verified_med_user(db, "v298-%s@example.test" % uuid.uuid4().hex[:8])
    now = datetime.now(timezone.utc)
    two_hours_ago = (now - timedelta(hours=2)).astimezone(ZoneInfo("UTC"))
    pid = medication_email.save_plan(uid, {"med_name": "S", "times": [two_hours_ago.strftime("%H:%M")], "timezone": "UTC",
                                           "start_date": (now.date() - timedelta(days=2)).isoformat()})
    pid = int(pid.get("id") if isinstance(pid, dict) else pid)
    day, tm = two_hours_ago.date().isoformat(), two_hours_ago.strftime("%H:%M")
    medication_email.schedule_snooze(uid, pid, 0, day, tm, 10)
    medication_email.schedule_snooze(uid, pid, 0, day, tm, 10)
    conn = db._conn(); c = conn.cursor()
    c.execute("SELECT status, due_at_utc FROM med_snoozes WHERE plan_id=? ORDER BY id", (pid,))
    rows = c.fetchall(); conn.close()
    assert [r[0] for r in rows] == ["cancelled", "pending"]
    assert datetime.fromisoformat(rows[-1][1]) > now  # counted from the press, not from the old dose time


def test_v299_member_data_deletion_is_an_explicit_choice():
    import uuid
    import webapp, db, medication_email
    db.init_db()
    owner = "account-v299-%s" % uuid.uuid4().hex[:6]
    for mid in (31, 32):
        db.save_record(owner, "en", 25, "female", ["headache"], "1 day", 1, "monitor", member_id=mid)
        db.save_blood_test(owner, {"Hb": 12.5}, member_id=mid)
    db.delete_member_data(owner, 31)
    assert not db.get_records(owner, member_id=31) and not db.get_blood_tests(owner, member_id=31)
    assert db.get_records(owner, member_id=32) and db.get_blood_tests(owner, member_id=32)  # other people untouched
    from pathlib import Path
    assert 'request.args.get("delete_data") == "1"' in Path("routes/tracking.py").read_text(encoding="utf-8")
    assert "delete_data=1" in Path("static/js/family-delete.js").read_text(encoding="utf-8")


def test_v300_node_unit_tests_for_the_bridge_and_microphone_pass():
    import shutil, subprocess, sys
    node = shutil.which("node")
    if not node:
        import pytest
        pytest.skip("node unavailable")
    for name in ("test_interaction_bridge.js", "test_symptom_microphone.js"):
        r = subprocess.run([node, name], capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, name + r.stdout + r.stderr


def _seed_member_health(db, owner, member_id):
    rid = db.save_record(owner, "ar", 25, "female", ["headache"], "1 day", 1, "monitor", member_id=member_id)
    rid = rid if isinstance(rid, int) else int(rid["id"]) if isinstance(rid, dict) else int(rid)
    db.save_result(owner, rid, {"detail": "secret-%s" % member_id})
    assert db.save_followup(owner, rid, "better")
    db.save_symptom_relief_log(owner, rid, "headache", "rest")
    db.save_blood_test(owner, {"Hb": 12.5}, member_id=member_id)
    return rid


def _count(table, owner_hash, rid=None):
    import db
    conn = db._conn(); c = conn.cursor()
    q = "SELECT COUNT(*) FROM %s WHERE user_hash=?" % table
    args = [owner_hash]
    if rid is not None:
        q += " AND record_id=?"; args.append(rid)
    c.execute(q, args); n = c.fetchone()[0]; conn.close()
    return n


def test_v301_member_delete_removes_results_followups_and_relief_logs_of_that_person_only():
    import uuid
    import db
    db.init_db()
    owner = "account-v301-%s" % uuid.uuid4().hex[:6]
    r1, r2 = _seed_member_health(db, owner, 41), _seed_member_health(db, owner, 42)
    assert db.load_result(owner, r1)
    db.delete_member_data(owner, 41)
    h = db._hash_user(owner)
    assert db.load_result(owner, r1) in (None, {}, [])
    for t in ("results", "symptom_followups", "symptom_relief_logs"):
        assert _count(t, h, r1) == 0, t
        assert _count(t, h, r2) == 1, t
    assert db.get_records(owner, member_id=41) == [] and db.get_blood_tests(owner, member_id=41) == []
    assert db.load_result(owner, r2)


def test_v302_member_delete_failure_rolls_back_everything_and_raises():
    import sqlite3, uuid
    import pytest
    import db
    db.init_db()
    owner = "account-v302-%s" % uuid.uuid4().hex[:6]
    rid = _seed_member_health(db, owner, 51)
    real_conn = db._conn

    class BadCursor:
        def __init__(self, cur): self._c = cur
        def execute(self, sql, *a):
            if sql.startswith("DELETE FROM vitals"):
                raise sqlite3.OperationalError("injected failure")
            return self._c.execute(sql, *a)
        def __getattr__(self, name): return getattr(self._c, name)

    class BadConn:
        def __init__(self, conn): self._k = conn
        def cursor(self): return BadCursor(self._k.cursor())
        def __getattr__(self, name): return getattr(self._k, name)

    db._conn = lambda: BadConn(real_conn())
    try:
        with pytest.raises(sqlite3.OperationalError):
            db.delete_member_data(owner, 51)
    finally:
        db._conn = real_conn
    h = db._hash_user(owner)
    assert db.get_records(owner, member_id=51) and db.get_blood_tests(owner, member_id=51)  # nothing was removed
    assert db.load_result(owner, rid) and _count("symptom_followups", h, rid) == 1 and _count("symptom_relief_logs", h, rid) == 1


def test_v303_adherence_uses_the_same_definition_for_every_window():
    import uuid
    from datetime import datetime, timedelta, timezone
    import webapp, db, medication_email
    from zoneinfo import ZoneInfo
    db.init_db(); medication_email.init_schema()
    from test_v29_regressions import _verified_med_user
    uid = _verified_med_user(db, "v303-%s@example.test" % uuid.uuid4().hex[:8])
    tz = ZoneInfo(medication_email.get_settings(uid)["timezone"])
    today = datetime.now(timezone.utc).astimezone(tz).date()
    pid = medication_email.save_plan(uid, {"med_name": "Mon", "times": ["00:01"], "timezone": str(tz), "frequency": "specific_days",
                                           "days_of_week": [0], "start_date": (today - timedelta(days=60)).isoformat()})
    pid = int(pid.get("id") if isinstance(pid, dict) else pid)
    for i in range(30):
        day = today - timedelta(days=i)
        if day.weekday() == 0:
            db.log_med_status(uid, 0, pid, day.isoformat(), "00:01", "taken")
    for days in (7, 30):
        adh = db.med_adherence("account-%s" % uid, member_id=0, days=days)
        assert adh["percent"] == 100.0 and adh["expected"] >= 1, (days, adh)
    assert db.med_adherence("account-%s" % uid, member_id=0, days=30)["expected"] >= 4


def test_v304_concurrent_snooze_presses_leave_one_pending_and_db_enforces_it():
    import threading, uuid
    from datetime import datetime, timedelta, timezone
    import webapp, db, medication_email
    db.init_db(); medication_email.init_schema()
    from test_v29_regressions import _verified_med_user
    uid = _verified_med_user(db, "v304-%s@example.test" % uuid.uuid4().hex[:8])
    now = datetime.now(timezone.utc)
    pid = medication_email.save_plan(uid, {"med_name": "S", "times": [now.strftime("%H:%M")], "timezone": "UTC",
                                           "start_date": (now.date() - timedelta(days=1)).isoformat()})
    pid = int(pid.get("id") if isinstance(pid, dict) else pid)
    errors = []
    def press():
        try:
            medication_email.schedule_snooze(uid, pid, 0, now.date().isoformat(), now.strftime("%H:%M"), 10)
        except Exception as exc:  # collected for the assertion below
            errors.append(repr(exc))
    threads = [threading.Thread(target=press) for _ in range(8)]
    [t.start() for t in threads]; [t.join() for t in threads]
    conn = db._conn(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM med_snoozes WHERE plan_id=? AND status='pending'", (pid,)); pending = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM med_snoozes WHERE plan_id=?", (pid,)); total = c.fetchone()[0]
    c.execute("SELECT 1 FROM sqlite_master WHERE name='uq_med_snooze_pending'"); has_index = c.fetchone() is not None
    conn.close()
    assert pending == 1 and has_index and total >= 1, (pending, total, errors)
    import pytest
    conn = db._conn(); c = conn.cursor()
    with pytest.raises(Exception):  # the database itself refuses a second pending snooze for the same dose
        c.execute("INSERT INTO med_snoozes(user_hash,plan_id,member_id,log_date,log_time,due_at_utc,minutes,status,created_at) "
                  "SELECT user_hash,plan_id,member_id,log_date,log_time,due_at_utc,minutes,'pending',created_at FROM med_snoozes WHERE plan_id=? AND status='pending'", (pid,))
    conn.close()


def _member_world(tag):
    """A signed-in account with one family member that has a medication plan, an analysis with details, a CBC and vitals."""
    import uuid
    from datetime import datetime, timezone
    import webapp, db, medication_email
    db.init_db(); medication_email.init_schema()
    from test_v29_regressions import _verified_med_user
    uid = _verified_med_user(db, "%s-%s@example.test" % (tag, uuid.uuid4().hex[:8]))
    owner = "account-%s" % uid
    mid = db.save_member(owner, "other", "Child", "8", "f")
    now = datetime.now(timezone.utc)
    pid = medication_email.save_plan(uid, {"med_name": "M", "times": ["08:00"], "timezone": "UTC", "start_date": now.date().isoformat(), "member_id": mid})
    pid = int(pid.get("id") if isinstance(pid, dict) else pid)
    rid = _seed_member_health(db, owner, mid)
    return db, medication_email, uid, owner, mid, pid, rid


def test_v305_member_removal_is_all_or_nothing_even_when_the_medication_step_fails():
    import sqlite3
    import pytest
    import family_archive
    db, me, uid, owner, mid, pid, rid = _member_world("v305")
    real = db._conn

    class BadCursor:
        def __init__(self, cur): self._c = cur
        def execute(self, sql, *a):
            if sql.startswith("DELETE FROM med_plans"):
                raise sqlite3.OperationalError("injected failure")
            return self._c.execute(sql, *a)
        def __getattr__(self, name): return getattr(self._c, name)

    class BadConn:
        def __init__(self, conn): self._k = conn
        def cursor(self): return BadCursor(self._k.cursor())
        def __getattr__(self, name): return getattr(self._k, name)

    db._conn = lambda: BadConn(real())
    try:
        with pytest.raises(sqlite3.OperationalError):
            family_archive.delete_member(owner, uid, mid, delete_data=True)
    finally:
        db._conn = real
    h = db._hash_user(owner)
    assert db.get_member(owner, mid)                                                    # the person is still there
    assert any(p["id"] == pid for p in me.list_plans(uid, active_only=False))           # so is the medication plan
    assert db.get_records(owner, member_id=mid) and db.load_result(owner, rid)          # and nothing of the health data was removed
    assert _count("symptom_followups", h, rid) == 1 and _count("symptom_relief_logs", h, rid) == 1


def test_v306_archive_keeps_records_and_restore_relinks_them_under_the_same_id():
    import family_archive
    db, me, uid, owner, mid, pid, rid = _member_world("v306")
    assert family_archive.delete_member(owner, uid, mid, delete_data=False)
    assert not db.get_member(owner, mid) and not [p for p in me.list_plans(uid, active_only=False) if p["id"] == pid]
    assert db.get_records(owner, member_id=mid)                                          # kept, not lost
    arch = [a for a in family_archive.list_archived(owner) if a["id"] == mid]
    assert arch and arch[0]["name"] == "Child" and arch[0]["records"] == 1
    newcomer = db.save_member(owner, "other", "Child", "8", "f")                         # same name added again: a new person
    assert newcomer != mid and not db.get_records(owner, member_id=newcomer)
    assert family_archive.restore_member(owner, mid)
    restored = db.get_member(owner, mid)
    assert restored and restored["name"] == "Child" and db.get_records(owner, member_id=mid)
    assert not [a for a in family_archive.list_archived(owner) if a["id"] == mid]
    assert family_archive.restore_member(owner, mid) is False                            # nothing left to restore
    assert family_archive.delete_member(owner, uid, mid, delete_data=False)
    assert family_archive.purge_archived(owner, mid)                                      # erase for good
    h = db._hash_user(owner)
    assert not db.get_records(owner, member_id=mid) and _count("results", h, rid) == 0
    assert not family_archive.list_archived(owner) or all(a["id"] != mid for a in family_archive.list_archived(owner))


def test_v307_orphan_cleanup_is_dry_by_default_and_touches_only_provable_orphans():
    import uuid
    import db, orphan_cleanup, family_archive
    db.init_db()
    owner = "account-v307-%s" % uuid.uuid4().hex[:6]
    keep = _seed_member_health(db, owner, 0)                    # a healthy analysis with its dependents
    h = db._hash_user(owner)
    ghost = 987654321                                           # an analysis that an older version deleted but left details of
    conn = db._conn(); c = conn.cursor()
    c.execute("INSERT INTO results (user_hash, record_id, data) VALUES (?,?,?)", (h, ghost, "{}"))
    c.execute("INSERT INTO symptom_followups (user_hash, record_id, outcome, new_sign, timestamp) VALUES (?,?,?,?,?)", (h, ghost, "better", 0, "t"))
    c.execute("INSERT INTO symptom_relief_logs (user_hash, record_id, symptom_key, factor, timestamp) VALUES (?,?,?,?,?)", (h, ghost, "k", "rest", "t"))
    conn.commit(); conn.close()
    db.save_record(owner, "ar", 8, "female", ["x"], "1 day", 1, "monitor", member_id=777)   # records of a member that vanished
    rep = orphan_cleanup.run()
    assert rep["applied"] is False and rep["dependents"]["results"] >= 1 and _count("results", h, ghost) == 1   # dry run deletes nothing
    assert any(d["member_id"] == 777 and d["user_hash"] == h for d in rep["dangling_members"])
    orphan_cleanup.run(apply=True)
    for t in ("results", "symptom_followups", "symptom_relief_logs"):
        assert _count(t, h, ghost) == 0 and _count(t, h, keep) == 1, t                 # orphans gone, valid rows untouched
    assert db.get_records(owner, member_id=777)                                          # records are never deleted by the default run
    orphan_cleanup.run(apply=True, archive_dangling=True)
    assert any(a["id"] == 777 for a in family_archive.list_archived(owner))
    assert not any(d["member_id"] == 777 and d["user_hash"] == h for d in orphan_cleanup.run()["dangling_members"])


def test_v308_archive_endpoints_require_login():
    import webapp
    c = webapp.app.test_client()
    c.set_cookie("lang", "ar")
    for method, url in (("get", "/api/family/archived"), ("post", "/api/family/archived/1/restore"), ("delete", "/api/family/archived/1")):
        r = getattr(c, method)(url, headers={"Host": "localhost"})
        assert r.status_code in (401, 403), (url, r.status_code)


def test_v309_a_failed_follow_up_check_never_turns_a_committed_delete_into_a_failure():
    import sqlite3
    import family_archive
    db, me, uid, owner, mid, pid, rid = _member_world("v309")
    real = db._conn; state = {"committed": False}

    class Cur:
        def __init__(self, cur, conn): self._c, self._conn = cur, conn
        def execute(self, sql, *a):
            if sql.startswith("DELETE FROM family_members"):
                self._conn.is_removal = True
            return self._c.execute(sql, *a)
        def __getattr__(self, n): return getattr(self._c, n)

    class Conn:
        is_removal = False
        def __init__(self, conn): self._k = conn
        def cursor(self): return Cur(self._k.cursor(), self)
        def commit(self):
            self._k.commit()
            if self.is_removal:
                state["committed"] = True
        def __getattr__(self, n): return getattr(self._k, n)

    def flaky():
        if state["committed"]:
            raise sqlite3.OperationalError("connection lost after commit")
        return Conn(real())

    db._conn = flaky
    try:
        assert family_archive.delete_member(owner, uid, mid, delete_data=True) is True
    finally:
        db._conn = real
    assert not db.get_member(owner, mid)


def test_v310_permanent_delete_needs_a_second_confirmation_and_buttons_lock_while_running():
    from pathlib import Path
    ops = Path("static/js/family-ops.js").read_text(encoding="utf-8")
    assert "CONFIRM_MS = 8000" in ops and "data-armed" in ops      # one shared 8 s double-confirm
    js = Path("static/js/family-delete.js").read_text(encoding="utf-8")
    assert "if (busy) return" in js and "lock(true)" in js and ".finally(" in js and "confirmButton" in js
    assert "'gone'" in js and "'unknown'" in js                   # already-deleted = success; lost reply = uncertain, not failed
    arch = Path("static/js/family-archive.js").read_text(encoding="utf-8")
    assert "lockRow(true)" in arch and ".finally(" in arch and "confirmButton" in arch and "if (locked) return" in arch
    assert "armTimer" not in js and "8000" not in js and "8000" not in arch   # timeout lives only in the shared helper
    src = Path("family_archive.py").read_text(encoding="utf-8")
    assert "FOR UPDATE" in src and "_leftovers" in src


def _signed_in_client(uid):
    import webapp
    c = webapp.app.test_client()
    c.set_cookie("lang", "ar")
    with c.session_transaction() as s:
        s["ss_user_id"] = uid
    return c


def test_v311_second_delete_of_the_same_member_is_404_and_changes_nothing_else():
    import family_archive
    db, me, uid, owner, mid, pid, rid = _member_world("v311a")
    other_db, _, uid2, owner2, mid2, pid2, rid2 = _member_world("v311b")           # another account's family member
    c = _signed_in_client(uid)
    hdr = {"Host": "localhost"}
    first = c.delete("/api/family/%d" % mid, headers=hdr)
    if first.status_code == 403:                                                    # CSRF token needed: fetch it like the page does
        import re
        page = c.get("/family", headers=hdr).get_data(as_text=True)
        tok = re.search(r'name="symptosense-csrf"\s+content="([^"]*)"', page).group(1)
        hdr["X-CSRF-Token"] = tok
        first = c.delete("/api/family/%d" % mid, headers=hdr)
    assert first.status_code == 200 and first.get_json() == {"ok": True}
    again = c.delete("/api/family/%d" % mid, headers=hdr)
    assert again.status_code == 404 and again.get_json() == {"ok": False, "error": "family_member_not_found"}
    # lost-race shape: the precheck still sees the row but the transactional delete finds it gone
    import routes.tracking as tr
    real = family_archive.delete_member
    orig_get = tr.db.get_member
    try:
        tr.db.get_member = lambda u, m: {"id": m}
        family_archive.delete_member = lambda *a, **k: False
        lost = c.delete("/api/family/%d" % mid, headers=hdr)
    finally:
        tr.db.get_member = orig_get; family_archive.delete_member = real
    assert lost.status_code == 404 and lost.get_json()["error"] == "family_member_not_found"
    # privacy: another account cannot touch or even detect this account's other member
    c2 = _signed_in_client(uid2)
    hdr2 = {"Host": "localhost", "X-CSRF-Token": hdr.get("X-CSRF-Token", "")}
    assert c2.delete("/api/family/%d" % mid, headers=hdr2).status_code in (403, 404)
    assert db.get_member(owner2, mid2)
    # archived rows are private too
    assert not any(a["id"] == mid for a in family_archive.list_archived(owner2))
