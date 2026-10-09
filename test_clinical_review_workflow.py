"""Clinical review queue: nothing is published before a second person approves."""
import os
import tempfile
from pathlib import Path

import pytest

_TMP = tempfile.TemporaryDirectory(prefix="ss-review-")
os.environ.pop("DATABASE_URL", None)
os.environ["DB_PATH"] = str(Path(_TMP.name) / "r.sqlite3")
os.environ.setdefault("WEB_SECRET", "review-secret-that-is-longer-than-32-characters")
os.environ["SESSION_COOKIE_SECURE"] = "0"
os.environ["SYMPTOSENSE_DISABLE_BACKUP_SCHEDULER"] = "1"

import clinical_review  # noqa: E402
import medical_knowledge  # noqa: E402
import webapp  # noqa: E402

webapp.db.init_db()

ALICE = {"id": 11, "email": "alice@example.org", "role": "admin", "status": "active"}
BOB = {"id": 12, "email": "bob@example.org", "role": "admin", "status": "active"}


@pytest.fixture()
def env(monkeypatch):
    users = {ALICE["id"]: ALICE, BOB["id"]: BOB}
    saved = []
    monkeypatch.setattr(webapp.db, "get_ss_user", lambda uid: users.get(int(uid)))
    monkeypatch.setattr(webapp, "_admin_session_valid", lambda touch=True: True)
    monkeypatch.setattr(webapp, "_admin_allowed", lambda scope="access": True)

    def fake_save(data, admin, entity_id=None):
        saved.append((dict(data), admin["email"], entity_id))
        return {"id": entity_id or 99, **data}

    monkeypatch.setattr(medical_knowledge, "save_disease", fake_save)
    monkeypatch.delenv("SYMPTOSENSE_REQUIRE_CLINICAL_REVIEW", raising=False)
    monkeypatch.delenv("SYMPTOSENSE_ALLOW_SELF_REVIEW", raising=False)
    client = webapp.app.test_client()
    client.set_cookie("lang", "ar")

    class Current(dict):
        def __setitem__(self, key, user):
            with client.session_transaction() as s:
                s["ss_user_id"] = user["id"]
                s["admin_csrf"] = "tok"
            super().__setitem__(key, user)

    current = Current()
    current["user"] = ALICE
    headers = {"X-CSRF-Token": "tok"}
    return client, headers, current, saved


def _submit(client, headers, name="تجربة"):
    return client.post("/api/admin/diseases", json={"name_ar": name, "name_en": "Trial", "status": "active"}, headers=headers)


def test_edit_is_queued_not_published(env):
    client, headers, _cur, saved = env
    r = _submit(client, headers)
    assert r.status_code == 202
    body = r.get_json()
    assert body["published"] is False and body["pending_review"]["status"] == "pending"
    assert saved == []  # live knowledge base untouched


def test_author_cannot_approve_own_proposal_but_other_reviewer_can(env):
    client, headers, cur, saved = env
    rid = _submit(client, headers).get_json()["pending_review"]["id"]
    own = client.post(f"/api/admin/clinical-reviews/{rid}/approve", json={}, headers=headers)
    assert own.status_code == 400 and own.get_json()["error"] == "self_review_not_allowed"
    assert saved == []
    cur["user"] = BOB
    ok = client.post(f"/api/admin/clinical-reviews/{rid}/approve", json={"note": "مراجعة سريرية"}, headers=headers)
    assert ok.status_code == 200 and ok.get_json()["review"]["status"] == "approved"
    assert saved and saved[0][1] == "bob@example.org" and saved[0][0]["name_ar"] == "تجربة"
    again = client.post(f"/api/admin/clinical-reviews/{rid}/approve", json={}, headers=headers)
    assert again.status_code == 409


def test_rejection_needs_a_note_and_publishes_nothing(env):
    client, headers, cur, saved = env
    rid = _submit(client, headers, "للرفض").get_json()["pending_review"]["id"]
    cur["user"] = BOB
    assert client.post(f"/api/admin/clinical-reviews/{rid}/reject", json={}, headers=headers).status_code == 400
    r = client.post(f"/api/admin/clinical-reviews/{rid}/reject", json={"note": "مصدر غير كاف"}, headers=headers)
    assert r.status_code == 200 and r.get_json()["review"]["status"] == "rejected"
    assert saved == []


def test_new_submission_supersedes_older_pending_for_same_entity(env):
    client, headers, _cur, _saved = env
    first = client.put("/api/admin/diseases/5", json={"name_ar": "أ", "name_en": "A"}, headers=headers).get_json()["pending_review"]["id"]
    second = client.put("/api/admin/diseases/5", json={"name_ar": "ب", "name_en": "B"}, headers=headers).get_json()["pending_review"]["id"]
    pend = {r["id"] for r in clinical_review.list_reviews("pending")}
    assert second in pend and first not in pend


def test_admin_page_lists_pending_and_requires_csrf_for_decisions(env):
    client, headers, _cur, _saved = env
    _submit(client, headers, "ظاهر في الصفحة")
    page = client.get("/admin/clinical-review")
    assert page.status_code == 200 and "ظاهر في الصفحة" in page.get_data(as_text=True)
    assert "admin-csrf" in page.get_data(as_text=True)
    rid = clinical_review.list_reviews("pending")[0]["id"]
    assert client.post(f"/api/admin/clinical-reviews/{rid}/reject", json={"note": "x"}).status_code == 403  # no CSRF header


def test_queue_can_be_disabled_for_local_development(env, monkeypatch):
    client, headers, _cur, saved = env
    monkeypatch.setenv("SYMPTOSENSE_REQUIRE_CLINICAL_REVIEW", "0")
    r = _submit(client, headers)
    assert r.status_code == 201 and saved
