"""V292.1: honest wording for question reasons and graph links, full sign-off states, one doctor-summary system."""
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

import clinical_signoff as cs
import doctor_summary
import health_file
import knowledge_graph as kg
import medical_knowledge as mk
import signoff_cli

ROOT = Path(__file__).resolve().parents[1]


# 1 ------------------------------------------------------------- why we ask
def _d(name, weight):
    return {"name_ar": name, "name_en": name, "symptoms": ({"x": weight} if weight is not None else {})}


def test_link_bands_follow_the_knowledge_base_weights():
    assert mk.symptom_link_band(0.9)[0] == "very_common"
    assert mk.symptom_link_band(0.6)[0] == "common"
    assert mk.symptom_link_band(0.4)[0] == "sometimes"
    assert mk.symptom_link_band(0.1)[0] == "weak"
    assert mk.symptom_link_band(0)[0] == mk.symptom_link_band(None)[0] == "absent"


def test_weak_link_is_not_called_common():
    r = mk._question_reason("س", "x", [_d("أ", 0.15), _d("ب", 0.8)], "ar")
    assert "ضعيف الارتباط بـ«أ»" in r and "شائع في «ب»" in r
    assert "شائع في «أ»" not in r


def test_missing_link_is_not_called_uncommon():
    r = mk._question_reason("س", "x", [_d("أ", 0.7), _d("ج", None)], "ar")
    assert "غير مدرج ضمن الروابط الحالية في قاعدة المعرفة لـ«ج»" in r
    assert "غير شائع" not in r
    en = mk._question_reason("S", "x", [_d("A", 0.7), _d("C", None)], "en")
    assert "not among the current links in the knowledge base for C" in en and "not in" not in en.replace("not among", "")


def test_no_links_at_all_falls_back_to_the_neutral_sentence():
    assert mk._question_reason("س", "x", [_d("أ", None)], "ar").startswith("يساعد هذا السؤال")


def test_live_question_reason_never_uses_the_old_wording():
    for syms in (["صداع", "غثيان"], ["حمى", "سعال"], ["دوخة"]):
        r = mk.differential_question(syms, lang="ar")
        if not r.get("done"):
            assert "غير شائع" not in r["question_reason"] and "دون تشخيص" in r["question_reason"]


# 2 ------------------------------------------------------------- knowledge graph
def test_graph_has_no_duplicate_links_and_every_link_has_a_kind():
    g = kg.graph()
    keys = [(e["a"], e["b"], e["kind"]) for e in g["edges"]]
    assert len(keys) == len(set(keys))
    assert all(e["kind"] in kg.KINDS for e in g["edges"])


def test_condition_source_is_labelled_as_the_condition_source_not_link_evidence():
    d = kg.neighborhood("symptom:dizziness", "ar")
    cond = [l for l in d["links"] if l["kind"] == "typical_symptom"]
    assert cond and all(l.get("strength") for l in cond)
    with_src = [l for l in cond if l["evidence_url"]]
    assert with_src and all(l["evidence_label"] == "مصدر الحالة" for l in with_src)
    assert all("وليس هذا الرابط وحده" in l["limit"] for l in cond)


def test_medicine_group_links_say_group_level_and_not_causation():
    d = kg.neighborhood("medicine:gi", "en")
    assert d["links"]
    for l in d["links"]:
        assert l["kind"] == "medicine_group" and l["evidence_url"] is None
        assert "not to every medicine" in l["limit"] and "caused" in l["limit"]
        assert "leaflet" not in l["relation"]


def test_lab_links_merge_low_and_high_and_say_they_are_not_proof():
    d = kg.neighborhood("lab:hgb", "ar")
    labs = [l for l in d["links"] if l["kind"] == "lab_symptom"]
    assert labs and all(l["weight"] is None and "strength" not in l for l in labs)
    assert all("ليس دليلًا على السبب" in l["limit"] and l["evidence_label"] == "مرجع المؤشر" for l in labs)


def test_explorer_shows_source_scope_and_limits_without_innerhtml():
    js = (ROOT / "static" / "js" / "knowledge-graph.js").read_text(encoding="utf-8")
    assert "l.evidence_label" in js and "kg-limit" in js and "innerHTML" not in js


# 3 ------------------------------------------------------------- clinical sign-off states
def _area(**kw):
    a = {"title_ar": "a", "title_en": "a", "status": "pending", "reviewer": None, "credentials": None, "date": None,
         "review_every_days": 365, "history": []}
    a.update(kw)
    return a


def test_all_five_states():
    today = date.today()
    assert cs.state(_area()) == "pending"
    assert cs.state(_area(status="in_review", reviewer="R")) == "in_review"
    assert cs.state(_area(status="rejected", reviewer="R", credentials="MD", date=today.isoformat())) == "rejected"
    assert cs.state(_area(status="approved", reviewer="R", credentials="MD", date=today.isoformat())) == "approved"
    old = (today - timedelta(days=400)).isoformat()
    assert cs.state(_area(status="approved", reviewer="R", credentials="MD", date=old)) == "expired"
    assert set(cs.STATE_LABELS) == {"pending", "in_review", "approved", "rejected", "expired"}


def test_future_dates_are_rejected_and_never_count_as_approved():
    future = (date.today() + timedelta(days=5)).isoformat()
    a = _area(status="approved", reviewer="R", credentials="MD", date=future)
    assert not cs.is_reviewed(a) and cs.state(a) == "pending"
    assert any("in the future" in p for p in cs.validate({"areas": {"x": a}}))
    h = _area(history=[{"action": "approve", "date": future}])
    assert any("history[0]" in p for p in cs.validate({"areas": {"x": h}}))


def test_status_labels_for_in_review_and_rejected_do_not_claim_review(monkeypatch):
    for st in ({"status": "in_review", "reviewer": "R"}, {"status": "rejected", "reviewer": "R", "credentials": "MD", "date": date.today().isoformat()}):
        monkeypatch.setattr(cs, "load", lambda path=None, st=st: {"areas": {"search_base": _area(**st)}})
        s = cs.status_for("search", "headache", "ar")
        assert s["reviewed"] is False and s["state"] == st["status"] and "راجعه" not in s["label"]


def test_cli_records_organization_scope_and_refuses_future_dates(tmp_path, monkeypatch):
    data = json.loads(cs.PATH.read_text(encoding="utf-8"))
    p = tmp_path / "s.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(cs, "PATH", p)
    future = (date.today() + timedelta(days=1)).isoformat()
    assert signoff_cli.main(["approve", "lab_cards", "--reviewer", "R", "--credentials", "MD", "--date", future]) == 2
    assert signoff_cli.main(["start-review", "lab_cards", "--reviewer", "R", "--organization", "Clinic", "--scope", "CBC cards"]) == 0
    assert cs.state(json.loads(p.read_text(encoding="utf-8"))["areas"]["lab_cards"]) == "in_review"
    today = date.today().isoformat()
    assert signoff_cli.main(["reject", "lab_cards", "--reviewer", "R", "--credentials", "MD", "--date", today, "--organization", "Clinic"]) == 0
    a = json.loads(p.read_text(encoding="utf-8"))["areas"]["lab_cards"]
    assert cs.state(a) == "rejected" and a["organization"] == "Clinic"
    assert [h["action"] for h in a["history"]] == ["start-review", "reject"] and a["history"][0]["scope"] == "CBC cards"


def test_registry_ships_without_any_sign_off_and_states_the_licence_limit():
    data = cs.load(cs.PATH)
    assert cs.validate(data) == []
    assert all(cs.state(a) == "pending" for a in data["areas"].values())  # no invented reviewers or dates
    assert "does not verify licences" in data["policy"]
    s = cs.summary()
    assert s["by_state"]["pending"] == s["total"] and "لا يتحقق" in s["credentials_note_ar"]


# 4 ------------------------------------------------------------- one doctor summary
def test_doctor_summary_module_delegates_to_health_file():
    assert doctor_summary.build is health_file.visit_summary
    src = (ROOT / "doctor_summary.py").read_text(encoding="utf-8")
    assert "_DURATIONS" not in src and "_URGENCY" not in src and "def _symptom_names" not in src


def test_health_file_uses_the_shared_bilingual_labels():
    d = {"days": 365, "member_id": 0, "counts": {"analyses": 1, "lab_reports": 0, "medicines": 0, "high_urgency": 0},
         "last_detail": {"date": "2026-11-01", "symptoms": ["صداع", "شي غريب"], "duration": "1-3 أيام", "severity": "2", "urgency": "medium"},
         "recurring": [], "symptoms": [{"symptom": "صداع", "count": 1, "recurring": False}], "high_urgency_dates": [],
         "attention_labs": [], "labs": [], "medicines": [], "vitals": [], "vitals_rows": [], "followup_outcomes": []}
    en = health_file.summary_text(d, "en")
    assert "Headache" in en and "شي غريب (patient's words)" in en and "1-3 days" in en and "Needs an appointment soon" in en
    page_en = health_file.render_doctor(d, "en")
    assert 'dir="ltr"' in page_en and "Headache" in page_en and "doc_lang=ar" in page_en
    page_ar = health_file.render_doctor(d, "ar")
    assert "صداع" in page_ar and "doc_lang=en" in page_ar


def test_health_file_page_offers_the_doctor_page_in_english(monkeypatch):
    import webapp
    c = webapp.app.test_client()
    with c.session_transaction() as s:
        s["ss_user_id"] = 987654
    r = c.get("/health-file?view=doctor&doc_lang=en")
    assert r.status_code in (200, 302)
    if r.status_code == 200:
        html = r.get_data(as_text=True)
        assert "One-page summary for your clinician" in html and "doc_lang=ar" in html


def test_chat_card_links_to_the_full_page_only_for_the_health_file_url():
    js = (ROOT / "static" / "js" / "chat" / "doctor-summary.js").read_text(encoding="utf-8")
    assert "j.full_page" in js and "health-file\\?view=doctor" in js


def test_denied_symptom_counts_against_only_the_conditions_it_is_linked_to():
    canonical = mk.normalize_symptoms(["حمى", "صداع"], "ar")["canonical"]
    matches = mk.match_diseases(canonical, negatives=["light-sensitivity", "neck-pain", "vomiting"], lang="ar", limit=10)
    assert matches
    weights = {d["slug"]: (d.get("symptoms") or {}) for d in mk.DISEASES}
    for m in matches:
        for slug in m["negative_evidence"]:
            assert float(weights.get(m["slug"], {}).get(slug, 0) or 0) > 0, (m["slug"], slug)
    flu = [m for m in matches if m["slug"] == "influenza"]
    assert flu and "light-sensitivity" not in flu[0]["negative_evidence"]


def test_shipped_graph_file_matches_the_knowledge_base_and_loads_without_building(monkeypatch):
    on_disk = json.loads(kg.DATA_PATH.read_text(encoding="utf-8"))
    assert on_disk == json.loads(json.dumps(kg.snapshot(), ensure_ascii=False)), "run: python tools/build_knowledge_graph.py"
    monkeypatch.setattr(kg, "_GRAPH", None)
    monkeypatch.setattr(kg, "build", lambda: (_ for _ in ()).throw(AssertionError("graph() must not build at request time")))
    g = kg.graph()
    assert len(g["nodes"]) == len(on_disk["nodes"]) and g["adj"]


def test_missing_graph_file_gives_an_empty_page_not_a_rebuild(monkeypatch, tmp_path):
    monkeypatch.setattr(kg, "_GRAPH", None)
    monkeypatch.setattr(kg, "DATA_PATH", tmp_path / "missing.json")
    assert kg.graph()["nodes"] == {} and kg.neighborhood("symptom:dizziness") is None
    monkeypatch.setattr(kg, "_GRAPH", None)


def test_stale_csrf_token_is_refreshed_and_the_request_retried_once():
    import webapp
    frame = (ROOT / "inline_assets" / "PAGE_FRAME.html").read_text(encoding="utf-8")
    assert "j.error !== 'csrf_failed'" in frame and "/api/session/csrf" in frame and "__ssRetried" in frame
    c = webapp.app.test_client()
    r = c.get("/api/session/csrf")
    assert r.status_code == 200 and r.get_json() == {"ok": True, "token": ""} and "no-store" in r.headers["Cache-Control"]
    with c.session_transaction() as s:
        s["ss_user_id"] = 424242
        s["user_csrf"] = "current-token"
    tok = c.get("/api/session/csrf").get_json()["token"]
    assert tok in ("current-token", "")  # empty only if the test user does not exist in this database


def test_css_and_static_urls_change_whenever_their_content_changes():
    import hashlib
    import webapp
    html = webapp.app.test_client().get("/ar/privacy").get_data(as_text=True)
    assert "/assets/app-shell-v112.css?v=" + webapp.APP_SHELL_VERSION in html and "__SHELL_V__" not in html
    assert webapp.APP_SHELL_VERSION.endswith(hashlib.sha1(webapp._APP_SHELL_CSS.encode("utf-8")).hexdigest()[:10])
    assert webapp.STATIC_ASSET_VERSION.endswith("-" + webapp._static_fingerprint()) and "?v=" + webapp.STATIC_ASSET_VERSION in html


def test_common_negation_forms_and_the_word_taqayyu():
    cases = {
        "ما عندي تقيؤ": ([], ["vomiting"]),
        "ما عندي حرارة ولا تقيؤ": ([], ["fever", "vomiting"]),
        "ما فيني صداع ولا دوخة": ([], ["dizziness", "headache"]),
        "مافيني حرارة": ([], ["fever"]),
        "ما بي دوخة": ([], ["dizziness"]),
        "عندي تقيؤ وصداع": (["headache", "vomiting"], []),
        "عندي صداع وما عندي تقيؤ": (["headache"], ["vomiting"]),
    }
    for text, (present, denied) in cases.items():
        r = mk.normalize_symptoms([text], "ar")
        assert sorted(c["slug"] for c in r["canonical"]) == present, text
        assert sorted(x["slug"] for x in r["negated"]) == denied, text


def test_live_demo_shows_ordinary_symptoms_and_every_denial_once():
    import live_demo
    mild = live_demo.run("mild", "ar")
    assert mild["symptoms"] == ["صداع"]
    assert {c["label"] for c in mild["denied"]} | set(mild["symptoms_denied"]) == {"حمى", "قيء"}
    neg = live_demo.run("negation", "ar")
    assert "ضيق التنفس" not in neg["symptoms_denied"]  # already shown as the safety concept
    js = live_demo._JS
    assert "r.symptoms" in js and "T.sym" in js and "innerHTML" not in js


def test_services_menu_finds_its_button_through_the_page_wide_click_listener():
    frame = (ROOT / "inline_assets" / "PAGE_FRAME.html").read_text(encoding="utf-8")
    body = frame[frame.index("function toggleDD(ev)"):frame.index("document.addEventListener('click', function(ev) {", frame.index("function toggleDD(ev)"))]
    assert "ev.target.closest('[data-ss-click=\"toggleDD\"]" in body
    assert "ev.currentTarget" not in body.split("\n", 1)[1]  # the delegated listener's currentTarget is the document


def test_body_map_glow_never_covers_the_symptom_buttons():
    css = (ROOT / "inline_assets" / "V291_SHARED_CSS.css").read_text(encoding="utf-8")
    assert ".smart-body-stage::before,.smart-body-stage::after{pointer-events:none!important}" in css
    assert ".smart-body-results{position:relative!important;z-index:1!important}" in css


# ---- Symptom-trial Excel: chip symptoms must reach the workbook as catalog names ----
def _ui_symptom_chips():
    import json as _json, re as _re
    from pathlib import Path as _P
    import webapp
    out = {"ar": set(), "en": set()}
    for f in ("static/js/chat/symptom-flow.js", "static/js/chat/body-map.js"):
        for arr in _re.findall(r"symptoms:\[([^\]]*)\]", (_P(__file__).resolve().parents[1] / f).read_text(encoding="utf-8")):
            for x in _re.findall(r"'([^']+)'", arr):
                out["ar" if _re.search("[؀-ۿ]", x) else "en"].add(x)
    c = webapp.app.test_client()
    assert c.post("/api/consent/preferences", json={"service_usage": True}).status_code == 200
    for lang in ("ar", "en"):
        c.set_cookie("lang", lang)
        page = c.get("/chat").get_data(as_text=True)
        out[lang] |= set(_json.loads(_re.search(r"const SYMS = (.*?);\n", page).group(1)))
    return out


def test_every_symptom_chip_is_understood_by_the_engine():
    import medical_knowledge as mk
    chips = _ui_symptom_chips()
    assert len(chips["ar"]) >= 20 and len(chips["en"]) >= 20
    for lang, items in chips.items():
        missing = [x for x in sorted(items) if not mk.normalize_symptoms([x], lang)["canonical"]]
        assert not missing, (lang, missing)


def test_symptom_trial_export_names_chip_and_described_symptoms_but_withholds_free_text():
    import research_projection as rp
    proj = rp.ResearchProjection()
    assert proj.symptom_terms(["😖 ألم في البطن", "🦵 ألم في الرجل"], "ar") == ["ألم البطن", "ألم الرجل أو الساق"]
    assert proj.symptom_terms(["🔥 Pain or burning when urinating"], "en") == ["Painful urination"]
    assert proj.symptom_terms(["😵 إغماء أو فقدان وعي"], "ar") == ["فقدان الوعي"]
    # A name or other prose never crosses the export boundary.
    assert proj.symptom_terms(["اسمي سارة"], "ar") == [rp.WITHHELD]
    assert proj.symptom_terms(["صداع", "اسمي سارة"], "ar") == ["صداع", rp.WITHHELD]


def test_guest_trial_row_carries_the_chip_symptoms():
    import db, webapp
    c = webapp.app.test_client()
    assert c.post("/api/consent/preferences", json={"service_usage": True, "analytics_research": True, "research_participation": False}).status_code == 200
    r = c.post("/api/analyze", json={"lang": "ar", "age": 27, "gender": "female", "symptoms": ["😖 ألم في البطن", "🤢 غثيان"], "duration": "يوم", "severity": 3},
               environ_overrides={"REMOTE_ADDR": "198.18.30.7"})
    assert r.status_code == 200 and r.get_json()["ok"]
    newest = db.admin_symptom_trial_rows()[0]
    assert newest["age"] == 27 and newest["symptoms"] == "ألم البطن • غثيان"


def test_phone_language_page_shows_the_whole_services_preview_in_one_language():
    import welcome_phone
    css = welcome_phone.CSS
    assert css.startswith("@media (max-width:600px)")
    # sidebar and shield badge come back on phones; only the small heart card stays hidden (it would sit under the card)
    assert ".fl-preview .fl-pv-side{display:flex!important" in css and ".fl-preview .fl-pv-badge{display:grid!important" in css
    assert ".fl-preview .fl-pv-pulse{display:none!important}" in css
    # tiles show the page language only, not Arabic and English glued together
    assert '.first-lang--ar .fl-preview [data-copy="en"]' in css and '.first-lang--en .fl-preview [data-copy="ar"]' in css
    assert 'ss-welcome-page .fl-preview [data-copy="en"]{display:inline!important}' not in css


def test_footer_brand_name_never_breaks_onto_two_lines():
    """Safari on a phone wrapped the footer name as «SymptoSens / e» (web font swapped in after layout)."""
    from pathlib import Path
    css = Path(__file__).resolve().parents[1].joinpath("inline_assets", "V291_SHARED_CSS.css").read_text(encoding="utf-8")
    assert ".footer .f-brand>span{white-space:nowrap!important" in css


def test_knowledge_graph_and_health_library_count_the_same_symptoms():
    """The graph page said 288 symptoms and the library 290: the two red-flag-only symptoms had no condition link."""
    import knowledge_graph as kg
    import medical_knowledge as mk
    mk.init_schema()
    ready = mk.public_source_ready_ids("symptom")
    library = [x for x in mk.list_entities("symptoms", False, "") if int(x["id"]) in ready]
    assert kg.stats()["by_type"]["symptom"] == len(library)
    for slug in ("severe-bleeding", "suicidal-thoughts"):
        d = kg.neighborhood("symptom:" + slug, "ar")
        assert d and d["total_links"] == 0 and "علامة خطر" in d["center"]["note"]


def test_home_hero_cards_name_what_the_site_actually_does():
    import webapp
    page = webapp.app.test_client().get("/ar/home").get_data(as_text=True)
    for word in ("يفهم عاميتك", "يوقف عند الخطر", "كل جواب بمصدر", "بياناتك لك"):
        assert word in page
    assert "<b>ذكاء اصطناعي</b>" not in page


def test_symptom_explorer_lists_shared_conditions_from_existing_links_only():
    import knowledge_graph as kg
    r = kg.explore(["symptom:headache", "symptom:fever", "symptom:stiff-neck", "symptom:not-a-symptom", "condition:influenza"], "en")
    assert [c["id"] for c in r["chosen"]] == ["symptom:headache", "symptom:fever", "symptom:stiff-neck"]
    assert 0 < len(r["results"]) <= 6 and r["total"] >= len(r["results"])
    counts = [x["count"] for x in r["results"]]
    assert counts == sorted(counts, reverse=True) and counts[0] == 3   # conditions sharing more symptoms come first
    g = kg.graph()
    for row in r["results"]:   # every match is an existing condition-symptom link, never a new claim
        for m in row["matched"]:
            assert any(g["edges"][i]["kind"] == "typical_symptom" and row["condition"]["id"] in (g["edges"][i]["a"], g["edges"][i]["b"])
                       for i in g["adj"][m["symptom"]["id"]])
    # a red-flag combination from the safety rules is reported, with the rule's own advice
    alarm = kg.explore(["symptom:chest-pain", "symptom:shortness-of-breath"], "ar")["alarms"]
    assert any(a["label"] == "ألم الصدر مع ضيق التنفس" for a in alarm)


def test_symptom_explorer_api_and_page():
    import webapp
    c = webapp.app.test_client()
    d = c.get("/api/knowledge-graph?explore=symptom:headache,symptom:fever&lang=ar").get_json()
    assert d["ok"] and d["results"] and d["results"][0]["count"] == 2
    s = c.get("/api/knowledge-graph?q=%D8%B5%D8%AF%D8%A7%D8%B9&type=symptom&lang=ar").get_json()
    assert s["ok"] and s["results"] and all(x["type"] == "symptom" for x in s["results"])
    page = c.get("/ar/knowledge-graph").get_data(as_text=True)
    assert 'id="kgX"' in page and "قارن عدة أعراض" in page and "وليست تشخيصًا" in page
    assert "/static/js/knowledge-graph.js?v=" in page and "__ASSET_VERSION__" not in page


def test_why_am_i_asked_is_a_button_with_what_the_answer_changes():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "static" / "js" / "chat"
    core = (root / "chat-core.js").read_text(encoding="utf-8")
    assert "ss-why-btn" in core and "aria-expanded" in core and "ليش أسألك هذا؟" in core
    follow = (root / "followup.js").read_text(encoding="utf-8")
    assert "«نعم»: تتقدّم الاحتمالات" in follow and "«لا»: تتراجع الاحتمالات" in follow
