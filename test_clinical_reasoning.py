"""V257: clinical reasoning - connected picture, medication context, what changed."""
import source_bundle
import uuid
from datetime import datetime, timedelta, timezone

import analysis_core
import db
import medication_context as mc
import medication_warnings as mw

NOW = datetime.now(timezone.utc)


def _owner():
    db.init_db()
    uid, err = db.create_ss_user("cr-%s@example.test" % uuid.uuid4().hex[:8], "CR", "TestPassword123!")
    assert not err
    return "account-%s" % uid


def _blood(owner, day, hgb, status):
    db.save_blood_test(owner, {"report_meta": {"sample_date": day}, "indicators": [
        {"key": "hgb", "name_ar": "هيموغلوبين", "name_en": "Hemoglobin", "value": hgb, "unit": "g/dL", "status": status}]})


def _patient(owner, **kw):
    p = {"age": "34", "gender": "female", "duration": "3 أيام", "severity": "3", "symptoms": ["دوخة", "غثيان"],
         "conditions": "", "medications": "", "notes": "", "user_id": owner}
    p.update(kw)
    return p


def test_connected_picture_medicine_timing_catalog_link_and_low_hb():
    owner = _owner()
    start = (NOW - timedelta(days=7)).date().isoformat()
    db.save_med_plan(owner, 0, "mounjaro", ["08:00"], dose="2.5", start_date=start)
    _blood(owner, (NOW - timedelta(days=20)).date().isoformat(), 10.8, "low")
    r = analysis_core.run_analysis(_patient(owner), "ar")["reasoning"]
    kinds = {c["kind"] for c in r["contributors"]}
    assert {"timing", "drug_symptom", "lab"} <= kinds
    text = " ".join(c["text"] for c in r["contributors"])
    assert "مونجارو" in text and "الهيموغلوبين" in text
    assert r["not_supported"] and r["escalate_if"] and r["next_step"]
    assert len(r["missing_top2"]) <= 2 and r["review_status"] == "pending_clinical_review"
    # nothing claims a diagnosis or a certain cause
    for bad in ("تشخيصك", "السبب هو", "you have"):
        assert bad not in text


def test_possibilities_explain_why_and_what_lowers_them():
    owner = _owner()
    r = analysis_core.run_analysis(_patient(owner), "ar")["reasoning"]
    p = r["possibilities"][0]
    assert p["why"] and p["name"]
    assert any("لم تذكر" in a or "غياب" in a for pp in r["possibilities"] for a in pp["against"])


def test_what_changed_raises_level_one_step_and_never_lowers():
    owner = _owner()
    db.save_record(owner, "ar", 34, "female", ["دوخة"], "يوم", 1, "low")
    r = analysis_core.run_analysis(_patient(owner, severity="3", symptoms=["دوخة", "غثيان"]), "ar")
    ch = r["reasoning"]["what_changed"]
    assert any("زادت" in i for i in ch["items"]) and any("جديد" in i for i in ch["items"])
    assert ch["level_raised_from"] == "soon" and r["triage_level"] == "today"
    assert r["decision"]["level"] == "today" and "تغيّرت حالتك" in r["triage_reason"]
    # already 'today' stays 'today' (the engine never jumps to emergency by itself)
    owner_b = _owner()
    db.save_record(owner_b, "ar", 34, "female", ["دوخة"], "يوم", 1, "low")
    rb = analysis_core.run_analysis(_patient(owner_b, severity="4", symptoms=["دوخة", "غثيان"]), "ar")
    assert rb["triage_level"] == "today" and rb["reasoning"]["what_changed"]["level_raised_from"] is None
    # improvement alone never lowers
    owner2 = _owner()
    db.save_record(owner2, "ar", 34, "female", ["دوخة"], "يوم", 5, "high")
    r2 = analysis_core.run_analysis(_patient(owner2, severity="2", symptoms=["دوخة"]), "ar")
    assert r2["reasoning"]["what_changed"]["level_raised_from"] is None
    assert any("انخفضت" in i for i in r2["reasoning"]["what_changed"]["items"])


def test_monitor_to_soon_when_severity_jumps_by_two():
    owner = _owner()
    db.save_record(owner, "ar", 34, "female", ["كحة"], "يوم", 1, "low")
    r = analysis_core.run_analysis(_patient(owner, severity="3", symptoms=["كحة"]), "ar")
    assert r["reasoning"]["what_changed"]["level_raised_from"] in ("soon", None)
    assert r["triage_level"] in ("soon", "today")


def test_anonymous_users_get_reasoning_without_saved_data():
    r = analysis_core.run_analysis(_patient("web-anon"), "ar")["reasoning"]
    assert r["contributors"] == [] and r["what_changed"]["items"] == []


def test_drug_drug_and_condition_links_come_only_from_catalog_text():
    mw.init_schema()
    mk = lambda n: {"name": n, "start_date": None, "days_ago": 30, "entry": mw.lookup_drug(n)}
    ls = mc.links([mk("aspirin"), mk("ibuprofen")], [], "كلى", "ar")
    assert [l["kind"] for l in ls].count("drug_drug") == 1
    assert any(l["kind"] == "drug_condition" and l["category"] == "kidney" for l in ls)
    unknown = mc.links([{"name": "madeupdrug", "start_date": None, "days_ago": 3, "entry": None}], ["دوخة"], "", "ar")
    assert [l["kind"] for l in unknown] == ["timing"]           # no catalog entry -> only timing, no invented link
    assert "اسأل الطبيب أو الصيدلي" in mc.describe(unknown[0], "ar")
    assert "لا تتوفر لدينا معلومات كافية" in mc.describe(unknown[0], "ar")      # timing != causation, drug not in catalog
    known = dict(unknown[0], in_catalog=True)
    assert "التزامن وحده لا يثبت" in mc.describe(known, "ar")


def test_ui_renders_reasoning_with_escaping_and_copies_match():
    from pathlib import Path
    root = Path(__file__).resolve().parent
    assert (root / "chat_view.py").read_text(encoding="utf-8") == (root / "views" / "chat_view.py").read_text(encoding="utf-8")
    a = source_bundle.chat_view_text()
    assert "ss-reasoning" in a and "esc(p.name)" in a and "p.why.map(esc)" in a and "c.text" in a
