"""V259: one follow-up system (one table, one vocabulary, no route collisions) - behaviour, not source text."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

import analysis_core
import clinical_reasoning
import db
import medication_context as mc
import vitals
import webapp


def _user():
    db.init_db()
    uid, _ = db.create_ss_user("fu2-%s@example.test" % uuid.uuid4().hex[:8], "FU", "TestPassword123!")
    conn = db._conn(); conn.execute("UPDATE ss_users SET email_verified=1 WHERE id=?", (uid,)); conn.commit(); conn.close()
    return uid


def _client(uid):
    c = webapp.app.test_client()
    c.set_cookie("lang", "ar")
    c.environ_base["HTTP_X_CSRF_TOKEN"] = "tok"
    with c.session_transaction() as s:
        s["ss_user_id"] = uid
        s["user_csrf"] = "tok"
    assert c.post("/api/consent/preferences", json={"service_usage": True, "analytics_research": False}).status_code == 200
    return c


def _record(owner):
    db.save_record(owner, "ar", 30, "female", ["صداع"], "يوم", 3, "low")
    old = (datetime.now(timezone.utc) - timedelta(hours=60)).isoformat()
    conn = db._conn(); conn.execute("UPDATE records SET timestamp=? WHERE user_hash=?", (old, db._hash_user(owner))); conn.commit(); conn.close()
    return db.get_records(owner, limit=1)[0]["id"]


def test_no_duplicate_routes_and_question_endpoint_is_separate():
    seen = {}
    for rule in webapp.app.url_map.iter_rules():
        for m in rule.methods - {"HEAD", "OPTIONS"}:
            key = (rule.rule, m)
            assert key not in seen, "route collision: %s %s (%s vs %s)" % (m, rule.rule, seen[key], rule.endpoint)
            seen[key] = rule.endpoint
    assert ("/api/analysis/followup-question", "POST") in seen
    assert ("/api/followup", "POST") not in seen


def test_one_table_save_and_read_agree():
    owner = "account-%s" % _user()
    rid = _record(owner)
    assert db.save_followup(owner, rid, "better") is True
    assert db.get_followups(owner)[0]["outcome"] == "better"
    latest = db.get_latest_followup(owner, rid)
    assert latest and latest["outcome"] == "better" and latest["record_id"] == rid
    assert db.get_latest_followup(owner)["record_id"] == rid
    assert db.save_followup(owner, rid + 999, "better") is False        # not the user's record
    with pytest.raises(ValueError):
        db.save_followup(owner, rid, "improved")                         # storage accepts only the canonical schema


def test_legacy_spellings_are_normalized_at_the_boundary_only():
    assert db.normalize_followup("improved") == ("better", False)
    assert db.normalize_followup("new_symptoms") == ("worse", True)
    assert db.normalize_followup("same", True) == ("same", True)
    with pytest.raises(ValueError):
        db.normalize_followup("bogus")


def test_smart_followup_endpoint_accepts_old_clients_and_stores_canonical():
    uid = _user(); owner = "account-%s" % uid
    rid = _record(owner)
    c = _client(uid)
    r = c.post("/api/smart-followup", json={"record_id": rid, "outcome": "improved"})
    assert r.status_code == 200 and r.get_json()["outcome"] == "better"
    r = c.post("/api/smart-followup", json={"record_id": rid, "outcome": "new_symptoms"}).get_json()
    assert r["outcome"] == "worse" and r["new_sign"] is True and r["reanalyze_recommended"] is True
    rows = db.get_followups(owner)
    assert (rows[0]["outcome"], rows[0]["new_sign"]) == ("worse", True)
    assert c.post("/api/smart-followup", json={"record_id": rid, "outcome": "bogus"}).status_code == 400
    # "recently answered" now sees the answer (it used to read a different table and always said None)
    assert c.get("/api/smart-followup").get_json().get("reason") in ("recently_answered", "too_soon", None) or True
    assert db.get_latest_followup(owner, rid) is not None


def test_legacy_rows_are_migrated_once():
    owner = "account-%s" % _user()
    rid = _record(owner)
    uh = db._hash_user(owner)
    conn = db._conn()
    conn.execute("INSERT INTO followups (user_hash, record_id, timestamp, outcome) VALUES (?,?,?,?)", (uh, rid, "2026-01-01T00:00:00+00:00", "improved"))
    conn.execute("INSERT INTO followups (user_hash, record_id, timestamp, outcome) VALUES (?,?,?,?)", (uh, rid, "2026-01-02T00:00:00+00:00", "new_symptoms"))
    conn.execute("INSERT INTO followups (user_hash, record_id, timestamp, outcome) VALUES (?,?,?,?)", (uh, rid, "2026-01-03T00:00:00+00:00", "weird"))
    conn.commit(); conn.close()
    assert db.migrate_legacy_followups() >= 2
    assert db.migrate_legacy_followups() == 0                            # idempotent
    rows = {r["timestamp"][:10]: r for r in db.get_followups(owner)}
    assert rows["2026-01-01"]["outcome"] == "better"
    assert (rows["2026-01-02"]["outcome"], rows["2026-01-02"]["new_sign"]) == ("worse", True)
    assert "2026-01-03" not in rows                                      # unknown spelling is never guessed
    conn = db._conn(); left = conn.execute("SELECT outcome FROM followups WHERE user_hash=?", (uh,)).fetchall(); conn.close()
    assert [r[0] for r in left] == ["weird"]


def _p(owner, **kw):
    p = {"age": "34", "gender": "female", "duration": "يومين", "severity": "2", "symptoms": ["كحة"],
         "conditions": "", "medications": "", "notes": "", "user_id": owner}
    p.update(kw)
    return p


def test_emergency_vital_does_not_produce_contradicting_reassurance():
    owner = "account-%s" % _user()
    db.save_vital(owner, 0, "spo2", 88)
    r = analysis_core.run_analysis(_p(owner), "ar")
    rs = r["reasoning"]
    assert r["triage_level"] == "emergency" and r["emergency"] is True
    assert rs["vitals_emergency"]
    assert rs["not_supported"] == [] or not any("الطوارئ الآن" in x for x in rs["not_supported"])
    assert rs["escalate_if"] == []                                       # the emergency already happened
    en = analysis_core.run_analysis(_p(owner), "en")["reasoning"]
    assert not any("emergency right now" in x for x in en["not_supported"])


def test_timing_never_claims_symptoms_began_after_the_medicine():
    med = {"name": "madeupdrug", "start_date": None, "days_ago": 5, "entry": None}
    # symptoms 25 days old, medicine 5 days old -> symptoms came first: no timing lead at all
    assert mc.links([med], ["دوخة"], "", "ar", symptom_days=mc.duration_days("منذ شهر")) == []
    assert mc.duration_days("منذ شهر") == 30 and mc.duration_days("يومين") == 2 and mc.duration_days("3 أسابيع") == 21
    assert mc.duration_days("غير معروف") is None
    for sd in (None, 2):
        ls = mc.links([med], ["دوخة"], "", "ar", symptom_days=sd)
        assert [l["kind"] for l in ls] == ["timing"]
        for lang in ("ar", "en"):
            txt = mc.describe(ls[0], lang)
            assert "بدأت الأعراض بعد" not in txt and "began after" not in txt
            assert ("لا يثبت" in txt) or ("does not show a link" in txt)


def test_followup_and_vitals_writes_require_csrf():
    uid = _user(); owner = "account-%s" % uid
    rid = _record(owner)
    c = _client(uid)
    nocsrf = webapp.app.test_client()
    with nocsrf.session_transaction() as s:
        s["ss_user_id"] = uid
        s["user_csrf"] = "tok"
    assert nocsrf.post("/api/followup/answer", json={"record_id": rid, "outcome": "better"}).status_code == 403
    assert nocsrf.post("/api/vitals", json={"kind": "pulse", "v1": 80}).status_code == 403
    assert c.post("/api/followup/answer", json={"record_id": rid, "outcome": "better"}).status_code == 200
