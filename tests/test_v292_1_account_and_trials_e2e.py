"""V292.1 end-to-end: a new account (register → verify → sign in), then a symptom analysis and a blood report
reach the two Admin workbooks with the requested fields only. Runs the real routes, CSRF included."""
import io
import json
import re
import uuid
from urllib.parse import urlparse

import db
import webapp


def _csrf(html):
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def test_new_account_then_trials_reach_both_workbooks(monkeypatch):
    from openpyxl import load_workbook
    sent = []
    monkeypatch.setattr(webapp, "_send_auth_email", lambda email, subject, html, category="auth": (sent.append(html) or True, None))
    c = webapp.app.test_client()
    c.set_cookie("lang", "ar", domain="localhost")
    email, pw = "e2e-%s@example.test" % uuid.uuid4().hex[:10], "CorrectHorse1!"

    r = c.post("/register", data={"name": "E2E", "email": email, "password": pw, "confirm": pw, "accept_terms": "on",
                                  "csrf_token": _csrf(c.get("/register").get_data(as_text=True))})
    assert r.status_code == 302 and urlparse(r.headers["Location"]).path == "/verify-email"
    link = [urlparse(h).path for h in re.findall(r'href="([^"]+)"', sent[-1]) if "/verify-email/" in h][0]
    assert c.get(link).status_code == 302
    c.get("/logout")
    bad = c.post("/login", data={"email": email, "password": "Wrong-Password1", "csrf_token": _csrf(c.get("/login").get_data(as_text=True))})
    assert bad.status_code == 200 and not c.get("/api/user-info").get_json().get("logged_in")
    ok = c.post("/login", data={"email": email, "password": pw, "csrf_token": _csrf(c.get("/login").get_data(as_text=True))})
    assert ok.status_code == 302 and c.get("/api/user-info").get_json().get("logged_in") is True

    h = {"X-CSRF-Token": c.get("/api/session/csrf").get_json()["token"]}
    assert c.post("/api/consent/preferences", json={"service_usage": True, "analytics_research": True, "research_participation": False}, headers=h).status_code == 200
    a = c.post("/api/analyze", headers=h, json={"lang": "ar", "age": 34, "gender": "female", "duration": "يومين", "severity": 3,
                                               "symptoms": ["😖 ألم في البطن", "🤢 غثيان"]}).get_json()
    assert a["ok"] and a["record_id"]
    ws = load_workbook(db.admin_export_symptom_trials_xlsx()).active
    rows = [[ws.cell(r_, i).value for i in range(1, 5)] for r_ in range(5, ws.max_row + 1)]
    assert [34, "Female | أنثى", "ألم البطن • غثيان", "Days"] in rows

    import fitz
    doc = fitz.open(); page = doc.new_page(); y = 72
    for line in ("Complete Blood Count", "Hemoglobin 10.1 g/dL 12.0 - 15.5", "MCV 71 fL 80 - 100", "WBC 6.2 x10^9/L 4.0 - 11.0"):
        page.insert_text((72, y), line); y += 20
    ex = c.post("/api/blood", headers=h, content_type="multipart/form-data", data={
        "mode": "extract", "gender": "f", "age": "34", "blood_collection_consent": "1", "file": (io.BytesIO(doc.tobytes()), "cbc.pdf")}).get_json()
    assert ex["ok"] and ex["extraction_receipt"] and ex["entries"]
    an = c.post("/api/blood", headers=h, data={
        "mode": "analyze_confirmed", "gender": "f", "age": "34", "blood_collection_consent": "1",
        "confirmed_entries": json.dumps(ex["entries"], ensure_ascii=False), "extraction_receipt": ex["extraction_receipt"],
        "confirmed_review_ids": json.dumps([e["review_id"] for e in ex["entries"] if e.get("review_id")])}).get_json()
    assert an["ok"]
    ws = load_workbook(db.admin_export_blood_collection_xlsx()).active
    cells = [[ws.cell(r_, i).value for i in range(1, 4)] for r_ in range(5, ws.max_row + 1)]
    assert any(row[0] == 34 and row[1] == "Female | أنثى" and "هيموغلوبين: 10.1" in str(row[2]) and "WBC" not in str(row[2]) for row in cells)
    blob = json.dumps(cells, ensure_ascii=False)
    assert email not in blob and "E2E" not in blob   # no identity in the workbook
