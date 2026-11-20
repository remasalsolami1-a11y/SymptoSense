"""The three consents (V68.6): exact wording, nothing pre-ticked, optional ones never block the service,
withdrawal really stops the related use, and the renamed 'comprehensive health picture' heading."""
import re
import uuid
from pathlib import Path

import pytest

import db
import webapp

AR = {
    "service": "أوافق على معالجة المعلومات الصحية التي أقدمها لتقديم تحليل الأعراض والنتائج المرتبطة به، وفق سياسة الخصوصية.",
    "analytics": "أوافق على استخدام إحصاءات الاستخدام والتقييمات وعمليات البحث المختصرة، وبيانات تحليل الأعراض المنظمة (العمر والجنس والأعراض ومدتها وشدتها ومستوى الاستعجال)، لتحسين أداء الموقع وتجربة المستخدم. لا تتضمن صادرات تجارب الأعراض اسمي أو بريدي الإلكتروني أو النصوص الحرة، ولا تُستخدم نصوص محادثاتي لهذا الغرض.",
    "analytics_note": "يمكنني سحب هذه الموافقة في أي وقت.",
    "research": "أوافق على استخدام بيانات الأعراض والتحليل بعد إزالة المعرّفات الشخصية المباشرة لدعم الأبحاث العلمية وتطوير المعرفة الصحية.",
    "research_note": "لا تشمل البيانات المشاركة اسمي أو بريدي الإلكتروني أو محادثاتي الخاصة.",
}
EN = {
    "service": "I agree to the processing of the health information I provide so that symptom analysis and its related results can be delivered, in accordance with the Privacy Policy.",
    "analytics": "I agree to the use of usage statistics, ratings, short searches, and structured symptom analysis data (age, gender, symptoms, duration, severity, and urgency) to improve the site and user experience. Symptom trial exports exclude my name, email, and free text. My chat transcripts are not used for this purpose.",
    "analytics_note": "I can withdraw this consent at any time.",
    "research": "I agree to the use of my symptom and analysis data, after direct personal identifiers are removed, to support scientific research and the development of health knowledge.",
    "research_note": "The shared data does not include my name, my email or my private chats.",
}
BODY = {"lang": "en", "age": 30, "gender": "female", "symptoms": ["headache", "fever"], "duration": "1-3 days", "severity": 3}
HDR = {"Host": "localhost"}


def _page(lang):
    return webapp.app.test_client().get(f"/{lang}/consent").get_data(as_text=True)


def _boxes(page):
    return re.findall(r"<input type=\"checkbox\" id=\"(?:service|analytics|research)Consent\"[^>]*>", page)


def _post(c, **kw):
    d = {"service_usage": True, "analytics_research": False, "research_participation": False}
    d.update(kw)
    r = c.post("/api/consent/preferences", json=d)
    assert r.status_code == 200 and r.get_json()["ok"]
    return r.get_json()


def _signed_in():
    db.init_db()
    uid, err = db.create_ss_user("consent-%s@example.test" % uuid.uuid4().hex[:8], "Consent Test", "StrongPassword123!")
    assert uid and not err
    conn = db._conn(); cur = conn.cursor()
    cur.execute("UPDATE ss_users SET email_verified=1,status='active' WHERE id=%s" % db.PH, (uid,))
    conn.commit(); conn.close()
    c = webapp.app.test_client()
    with c.session_transaction() as s:
        s["ss_user_id"] = uid
        s["user_csrf"] = "tok"
    c.environ_base["HTTP_X_CSRF_TOKEN"] = "tok"          # the real CSRF check stays on for signed-in POSTs
    return c, uid


def _flags(owner):
    conn = db._conn(); cur = conn.cursor()
    cur.execute("SELECT id,COALESCE(analytics_eligible,0),COALESCE(research_eligible,0) FROM records WHERE user_hash=%s" % db.PH, (db._hash_user(owner),))
    rows = cur.fetchall(); conn.close()
    return rows


# ---------- wording, order, badges, nothing pre-ticked ----------
@pytest.mark.parametrize("lang,t", [("ar", AR), ("en", EN)])
def test_exact_texts_in_the_required_order(lang, t):
    page = _page(lang)
    pos = [page.index(t["service"]), page.index(t["analytics"]), page.index(t["research"])]
    assert pos == sorted(pos)
    assert t["analytics_note"] in page and t["research_note"] in page
    for k in ("service", "analytics", "research"):
        assert page.count(t[k]) == 1, "each consent text appears once (no repetition)"


@pytest.mark.parametrize("lang,req,opt", [("ar", "مطلوبة", "اختيارية"), ("en", "Required", "Optional")])
def test_one_required_two_optional_badges(lang, req, opt):
    page = _page(lang)
    assert len(re.findall(r'class="consent-badge required">%s<' % req, page)) == 1
    assert len(re.findall(r'class="consent-badge optional">%s<' % opt, page)) == 2
    for old in ("مطلوب للخدمة", "بحث اختياري", "Required for service", "Optional research", "نسخة مجهولة الهوية"):
        assert old not in page


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_fresh_visitor_sees_nothing_pre_ticked(lang):
    page = _page(lang)
    boxes = _boxes(page)
    assert len(boxes) == 3 and not any(re.search(r"\bchecked\b", b) for b in boxes), boxes


def test_direction_follows_the_language():
    assert 'dir="rtl"' in _page("ar") and 'dir="ltr"' in _page("en")


def test_label_renamed_everywhere_users_see_it():
    js = Path("static/js/chat/analysis-result.js").read_text(encoding="utf-8")
    assert "الصورة الصحية الشاملة" in js and "Comprehensive health picture" in js
    for p in list(Path("static").rglob("*.js")) + list(Path("pagelib").rglob("*.py")) + list(Path("routes").rglob("*.py")):
        t = p.read_text(encoding="utf-8", errors="ignore")
        assert "الصورة السريرية المترابطة" not in t and "Connected clinical picture" not in t, p


# ---------- save / reopen / decline / withdraw ----------
def test_saved_choices_are_shown_again_when_the_page_is_reopened():
    c = webapp.app.test_client()
    _post(c, analytics_research=True, research_participation=False)
    boxes = _boxes(c.get("/en/consent").get_data(as_text=True))
    state = [bool(re.search(r"\bchecked\b", b)) for b in boxes]
    assert state == [True, True, False]


def test_declining_both_optional_consents_never_blocks_the_analysis():
    c = webapp.app.test_client()
    _post(c)
    r = c.post("/api/analyze", json=BODY)
    assert r.status_code == 200 and r.get_json()["ok"]


def test_no_service_consent_blocks_only_the_analysis():
    c = webapp.app.test_client()
    _post(c, service_usage=False)
    assert c.post("/api/analyze", json=BODY).status_code == 403
    assert c.get("/en/consent").status_code == 200 and c.get("/privacy").status_code == 200


def test_signed_in_flags_follow_the_choices_and_withdrawal_unflags_old_records():
    c, uid = _signed_in()
    owner = "account-%s" % uid
    _post(c, analytics_research=True, research_participation=True)
    assert c.post("/api/analyze", json=dict(BODY, age=40)).get_json()["ok"]
    rows = _flags(owner)
    assert rows and all(a == 1 and r == 1 for _, a, r in rows)
    # withdrawing only research keeps analytics
    _post(c, analytics_research=True, research_participation=False)
    assert all(a == 1 and r == 0 for _, a, r in _flags(owner))
    # withdrawing analytics through the consent page also drops the flag on already-saved records
    _post(c, analytics_research=False, research_participation=False)
    assert all(a == 0 and r == 0 for _, a, r in _flags(owner))
    # and a later analysis is not flagged at all
    assert c.post("/api/analyze", json=dict(BODY, age=41)).get_json()["ok"]
    assert all(a == 0 and r == 0 for _, a, r in _flags(owner))


def test_privacy_center_withdrawal_endpoints_match_the_consent_page():
    c, uid = _signed_in()
    owner = "account-%s" % uid
    _post(c, analytics_research=True, research_participation=True)
    c.post("/api/analyze", json=BODY)
    r = c.post("/api/privacy/withdraw-research", headers=HDR)
    assert r.status_code == 200 and r.get_json()["consent"]["excluded_research_records"] >= 1
    assert all(a == 1 and r == 0 for _, a, r in _flags(owner))
    assert c.post("/api/privacy/withdraw-analytics", headers=HDR).status_code == 200
    assert all(a == 0 for _, a, _r in _flags(owner))


def test_research_choice_is_independent_of_analytics():
    c, uid = _signed_in()
    _post(c, analytics_research=False, research_participation=True)
    c.post("/api/analyze", json=BODY)
    assert all(a == 0 and r == 1 for _, a, r in _flags("account-%s" % uid))


def test_research_never_includes_minors():
    c, uid = _signed_in()
    _post(c, analytics_research=True, research_participation=True)
    c.post("/api/analyze", json=dict(BODY, age=12))
    assert all(r == 0 for _, _a, r in _flags("account-%s" % uid))


# ---------- guests ----------
def test_guest_copy_needs_the_analytics_consent_and_is_unflagged_on_withdrawal():
    c = webapp.app.test_client()
    _post(c, analytics_research=True)
    c.post("/api/analyze", json=BODY)
    n = len(db.admin_symptom_trial_rows())
    _post(c, analytics_research=False)
    assert len(db.admin_symptom_trial_rows()) == n - 1


# ---------- feedback (ratings are analytics data) ----------
def test_rating_is_stored_only_with_the_analytics_consent():
    def count():
        conn = db._conn(); cur = conn.cursor(); cur.execute("SELECT COUNT(*) FROM feedback"); n = cur.fetchone()[0]; conn.close(); return n
    c = webapp.app.test_client()
    _post(c)
    db.init_db(); n0 = count()
    r = c.post("/api/feedback", json={"rating": 5}).get_json()
    assert r["ok"] and r["recorded"] is False and r["reason"] == "analytics_consent_disabled" and count() == n0
    _post(c, analytics_research=True)
    r = c.post("/api/feedback", json={"rating": 5}).get_json()
    assert r["ok"] and r["recorded"] is True and count() == n0 + 1
    assert c.post("/api/feedback", json={"rating": 9}).status_code == 400   # validation unchanged


def test_unsaved_rating_message_is_honest_in_the_ui():
    js = Path("static/js/chat/result-actions.js").read_text(encoding="utf-8")
    assert "d.recorded===false" in js and "لم يُحفظ التقييم" in js


# ---------- admin symptom-trials export ----------
def test_admin_trials_export_lists_only_analytics_consented_records():
    c, uid = _signed_in()
    _post(c)
    before = len(db.admin_symptom_trial_rows())
    c.post("/api/analyze", json=dict(BODY, age=52))
    assert len(db.admin_symptom_trial_rows()) == before
    _post(c, analytics_research=True)
    c.post("/api/analyze", json=dict(BODY, age=53))
    assert len(db.admin_symptom_trial_rows()) == before + 1


# ---------- privacy policy agrees with the consent page ----------
@pytest.mark.parametrize("lang", ["ar", "en"])
def test_policy_describes_three_independent_consents(lang):
    page = webapp.app.test_client().get(f"/{lang}/privacy").get_data(as_text=True)
    assert ("ثلاث موافقات منفصلة" if lang == "ar" else "three separate consents") in page
    assert ("2.2" in page)
    assert "2.0 —" not in page


# ---------- V68.12: short visible analytics text + details with the full text ----------
SHORT = {
    "ar": "أوافق على استخدام إحصاءات الموقع وبيانات الأعراض المنظمة (العمر، الجنس، الأعراض، المدة، الشدة، الاستعجال) لتحسين الموقع. لا تشمل اسمي أو بريدي أو نصوص محادثاتي.",
    "en": "I agree to the use of site statistics and structured symptom data (age, gender, symptoms, duration, severity, urgency) to improve the site. This does not include my name, email or chat transcripts.",
}


@pytest.mark.parametrize("lang,t", [("ar", AR), ("en", EN)])
def test_analytics_short_text_visible_and_full_text_in_details(lang, t):
    page = _page(lang)
    assert page.count(SHORT[lang]) == 1
    m = re.search(r'<details class="consent-more"><summary>([^<]+)</summary><small>(.*?)</small></details>', page, re.S)
    assert m, "the full analytics text sits inside a details block"
    assert m.group(2) == t["analytics"]
    assert m.group(1) == ("التفاصيل" if lang == "ar" else "Details")
    # the short text comes first, the details follow, then the withdrawal note
    assert page.index(SHORT[lang]) < page.index("consent-more") < page.index(t["analytics_note"])
    # the short sentence is much shorter than the full one
    assert len(SHORT[lang]) < 0.75 * len(t["analytics"])


def test_service_and_research_have_no_details_block():
    page = _page("ar")
    assert page.count('class="consent-more"') == 1


def test_consent_version_is_2_5():
    import privacy_features
    assert privacy_features.CONSENT_VERSION == "2.5"
