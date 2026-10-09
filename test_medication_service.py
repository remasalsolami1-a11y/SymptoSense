"""MedicationService (business rules, no Flask) and the thin HTTP layer on top of it."""
import ast
import uuid
from pathlib import Path

import pytest

import db
import webapp
from services.medication_service import MEDS_API_REVISION, MedicationError, MedicationService

ROOT = Path(__file__).resolve().parent
PLAN = {"med_name": "QA SERVICE", "times": ["08:00"], "frequency": "daily", "start_date": "2027-12-31",
        "timezone": "Asia/Riyadh", "delivery_channel": "email"}


def _user():
    db.init_db()
    uid, _ = db.create_ss_user("ms-%s@example.test" % uuid.uuid4().hex[:8], "MS", "TestPassword123!")
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


def _svc():
    return MedicationService(lambda key: "me")


# ---- the service on its own (no request context) ---------------------------------------------------------------
def test_service_module_is_framework_free():
    tree = ast.parse((ROOT / "services" / "medication_service.py").read_text(encoding="utf-8"))
    imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imported |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert "flask" not in imported and "webapp" not in imported


def test_plan_lifecycle_through_the_service():
    uid = _user(); s = _svc()
    created = s.create_plan(uid, dict(PLAN))
    pid = created["id"]
    assert created["ok"] and created["delivery_channel"] == "email" and created["meds_revision"] == MEDS_API_REVISION
    listed = s.list_plans(uid)
    assert [p["id"] for p in listed["plans"]] == [pid] and listed["plans"][0]["member_name"] == "me"
    assert s.update_plan(uid, pid, dict(PLAN, med_name="QA SERVICE 2"))["id"] == pid
    assert s.delete_plan(uid, pid)["deleted"] is True
    assert s.list_plans(uid)["plans"] == []
    with pytest.raises(MedicationError) as e:
        s.delete_plan(uid, pid + 12345)
    assert (e.value.code, e.value.status) == ("not_found", 404)


def test_service_validates_inputs_like_the_routes_always_did():
    uid = _user(); s = _svc()
    for bad in ("abc", "-1"):
        with pytest.raises(MedicationError) as e:
            s.list_plans(uid, bad)
        assert (e.value.code, e.value.status) == ("invalid_member", 400)
    with pytest.raises(MedicationError) as e:
        s.calendar(uid, "-2", 10)
    assert e.value.code == "invalid_query"
    with pytest.raises(MedicationError) as e:
        s.log_status(uid, {"plan_id": 0, "time": "08:00"})
    assert e.value.code == "invalid_reminder_status"
    with pytest.raises(MedicationError) as e:
        s.log_status(uid, {"plan_id": 999999, "time": "08:00", "status": "taken"})
    assert (e.value.code, e.value.status) == ("forbidden", 403)
    assert s.calendar(uid, None, 500)["ok"]            # days are clamped, not rejected


def test_log_status_only_for_the_owners_plan():
    owner, other = _user(), _user(); s = _svc()
    pid = s.create_plan(owner, dict(PLAN))["id"]
    assert s.log_status(owner, {"plan_id": pid, "time": "08:00", "status": "taken", "date": "2027-12-31"}) == {"ok": True}
    with pytest.raises(MedicationError) as e:
        s.log_status(other, {"plan_id": pid, "time": "08:00", "status": "taken"})
    assert e.value.status == 403


def test_delivery_status_reads_the_worker_it_is_given():
    s = _svc()
    on = s.delivery_status({"started": True, "state": {"running": True, "last_run": "x"}})
    off = s.delivery_status({"started": False, "state": {}})
    assert on["worker_started"] is True and on["worker_running"] is True and on["last_run"] == "x"
    assert off["worker_started"] is False and off["worker_running"] is False


# ---- the HTTP layer --------------------------------------------------------------------------------------------
def test_delivery_status_endpoint_reports_the_live_worker_flag(monkeypatch):
    """Regression: the flag used to be captured when routes were registered, so it stayed False forever."""
    c = _client(_user())
    monkeypatch.setattr(webapp, "_MED_REMINDER_WORKER_STARTED", False)
    assert c.get("/api/meds/delivery-status").get_json()["worker_started"] is False
    monkeypatch.setattr(webapp, "_MED_REMINDER_WORKER_STARTED", True)
    assert c.get("/api/meds/delivery-status").get_json()["worker_started"] is True


def test_http_envelope_and_headers_are_unchanged(monkeypatch):
    monkeypatch.setattr(webapp, "_start_medication_reminder_worker_once", lambda: None)
    monkeypatch.setattr(webapp, "_kick_medication_delivery_now", lambda: None)
    c = _client(_user())
    r = c.post("/api/meds/plan", json=dict(PLAN))
    assert r.status_code == 200 and r.headers["X-SymptoSense-Meds-Revision"] == MEDS_API_REVISION
    assert "no-store" in r.headers["Cache-Control"]
    pid = r.get_json()["id"]
    g = c.get("/api/meds/plan")
    assert g.status_code == 200 and g.headers["Pragma"] == "no-cache" and g.headers["Expires"] == "0"
    assert c.get("/api/meds/plan?member=abc").status_code == 400
    assert c.get("/api/meds/plan?member=abc").get_json() == {"ok": False, "error": "invalid_member"}
    assert c.post("/api/meds/plan", json=dict(PLAN, delivery_channel="telegram", telegram_username="!!")).get_json()["error"] == "invalid_telegram_username"
    assert c.put("/api/meds/plan/%d" % pid, json=dict(PLAN, med_name="Z")).status_code == 200
    d = c.delete("/api/meds/plan/%d" % pid)
    assert d.status_code == 200 and d.get_json()["deleted"] is True and d.headers["Pragma"] == "no-cache"
    assert c.delete("/api/meds/plan/%d" % pid).status_code in (200, 404)
    assert c.post("/api/meds/log", json={"plan_id": 0}).get_json()["error"] == "invalid_reminder_status"
    assert c.get("/api/meds/weekly?member=-3").get_json() == {"ok": False, "error": "invalid_member"}
    assert c.get("/api/meds/calendar?days=zz").get_json() == {"ok": False, "error": "invalid_query"}


def test_routes_module_no_longer_carries_the_business_rules():
    src = (ROOT / "routes" / "medications.py").read_text(encoding="utf-8")
    for needle in ("medication_telegram", "db.log_med_status", "db.list_members", "plans_today"):
        assert needle not in src, needle + " belongs in services/medication_service.py"
    deps = ast.literal_eval(ast.parse(src).body[[isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "DEPS" for n in ast.parse(src).body].index(True)].value)
    assert len(deps) <= 11 and "MEDS_API_REVISION" not in deps and "_MED_REMINDER_WORKER_STARTED" not in deps
