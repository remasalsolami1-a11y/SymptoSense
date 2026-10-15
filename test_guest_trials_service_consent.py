"""Guest symptom analyses: the service consent runs the analysis; a (anonymous) copy is kept only with the optional analytics consent."""
import db
import webapp

BODY = {"lang": "en", "age": 30, "gender": "female", "symptoms": ["headache", "fever"], "duration": "1-3 days", "severity": 3,
        "notes": "my private note", "conditions": "asthma", "medications": "salbutamol"}


def _guest(consent):
    c = webapp.app.test_client()
    assert c.post("/api/consent/preferences", json=consent).status_code == 200
    return c


def _rows():
    return db.admin_symptom_trial_rows()


def test_service_consent_alone_runs_the_analysis_but_keeps_no_copy():
    before = len(_rows())
    r = _guest({"service_usage": True, "analytics_research": False, "research_participation": False}).post("/api/analyze", json=BODY)
    assert r.status_code == 200 and r.get_json()["ok"]
    assert len(_rows()) == before


def test_analytics_consent_keeps_an_anonymous_copy_without_private_fields():
    before = len(_rows())
    r = _guest({"service_usage": True, "analytics_research": True, "research_participation": False}).post("/api/analyze", json=BODY)
    assert r.status_code == 200 and r.get_json()["ok"]
    rows = _rows()
    assert len(rows) == before + 1
    newest = rows[0]
    assert newest["age"] == 30 and "headache" in newest["symptoms"].lower()
    blob = repr(newest)
    assert "private note" not in blob and "asthma" not in blob and "salbutamol" not in blob


def test_no_service_consent_means_no_analysis_and_nothing_saved():
    before = len(_rows())
    assert webapp.app.test_client().post("/api/analyze", json=BODY).status_code == 403
    assert len(_rows()) == before


def test_withdrawing_analytics_removes_the_guest_copy_from_the_admin_export():
    c = _guest({"service_usage": True, "analytics_research": True, "research_participation": False})
    c.post("/api/analyze", json=BODY)
    n = len(_rows())
    assert c.post("/api/consent/preferences", json={"service_usage": True, "analytics_research": False, "research_participation": False}).status_code == 200
    assert len(_rows()) == n - 1


def test_demo_mode_and_signed_in_rows_are_not_saved_by_the_guest_path():
    import guest_trials
    assert guest_trials.save("k", "en", {"symptoms": ["cough"]}, {}, True, True, False) is None
    assert guest_trials.save("k", "en", {"symptoms": ["cough"], "user_id": "account-1"}, {}, False, True, False) is None
    assert guest_trials.save("k", "en", {"symptoms": ["cough"]}, {}, False, False, False) is None
