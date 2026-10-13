"""Guest symptom analyses are kept (anonymously) once the service consent is accepted (owner decision, V68.5)."""
import io
import sqlite3

import openpyxl
import pytest

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


def test_service_consent_alone_saves_the_guest_analysis_anonymously():
    before = len(_rows())
    r = _guest({"service_usage": True, "analytics_research": False, "research_participation": False}).post("/api/analyze", json=BODY)
    assert r.status_code == 200 and r.get_json()["ok"]
    rows = _rows()
    assert len(rows) == before + 1
    newest = rows[0]
    assert newest["age"] == 30 and "headache" in newest["symptoms"] and newest["duration"] == "1-3 days"
    blob = repr(newest)
    assert "private note" not in blob and "asthma" not in blob and "salbutamol" not in blob


def test_no_service_consent_means_no_analysis_and_nothing_saved():
    before = len(_rows())
    c = webapp.app.test_client()
    r = c.post("/api/analyze", json=BODY)
    assert r.status_code == 403
    assert len(_rows()) == before


def test_guest_rows_are_not_flagged_for_analytics_or_research_without_those_consents():
    c = _guest({"service_usage": True, "analytics_research": False, "research_participation": False})
    c.post("/api/analyze", json=BODY)
    conn = db._conn(); cur = conn.cursor()
    cur.execute("SELECT * FROM records ORDER BY id DESC LIMIT 1"); cols = [d[0] for d in cur.description]; rec = dict(zip(cols, cur.fetchone()))
    conn.close()
    flags = {k: v for k, v in rec.items() if "consent" in k or "eligible" in k or "research" in k or "analytics" in k}
    assert flags and not any(bool(v) for v in flags.values()), flags


def test_research_export_still_excludes_guests_without_research_consent():
    import admin_complete
    _guest({"service_usage": True, "analytics_research": False, "research_participation": False}).post("/api/analyze", json=BODY)
    wb = openpyxl.load_workbook(io.BytesIO(admin_complete.export_admin_workbook("official").getvalue()))
    sheet = wb["Symptom Analyses"]
    assert sheet.max_row <= 4, "a guest without research consent leaked into the research export"


@pytest.mark.parametrize("lang,needle", [("en", "anonymous copy of age, gender, symptoms and duration"), ("ar", "نسخة مجهولة الهوية من العمر والجنس والأعراض والمدة")])
def test_the_consent_text_tells_the_visitor_what_is_saved(lang, needle):
    page = webapp.app.test_client().get(f"/{lang}/consent").get_data(as_text=True)
    assert needle in page


def test_signed_in_users_unchanged_and_demo_mode_not_saved():
    import guest_trials
    assert guest_trials.save("k", "en", {"symptoms": ["cough"]}, {}, True, False, False) is None      # demo mode
    assert guest_trials.save("k", "en", {"symptoms": ["cough"], "user_id": "account-1"}, {}, False, False, False) is None
