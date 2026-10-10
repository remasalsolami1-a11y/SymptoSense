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
