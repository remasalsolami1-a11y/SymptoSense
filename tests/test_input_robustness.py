"""Malformed JSON values must be answered with a 4xx (or the normal reply), never a 500.

Found by type-mutation fuzzing of every /api route in the V68 pre-release review.
"""
import pytest

import webapp
from test_checkin_validation import _client

HUGE = 10 ** 30
INF = float("inf")
NOT_OBJECTS = [[], ["a"], "x", 5, None]


def _anon():
    return webapp.app.test_client()


@pytest.mark.parametrize("body", [{"email": ["a"], "password": "x"}, {"email": {"a": 1}, "password": "x"}, {"email": 5, "password": "x"},
                                  {"email": "a@b.co", "password": ["x"]}, {"email": "a@b.co", "password": {"a": 1}}] + NOT_OBJECTS)
def test_login_bad_types(body):
    r = _anon().post("/api/auth/login", json=body)
    assert 400 <= r.status_code < 500, (body, r.status_code)


@pytest.mark.parametrize("body", [{"name": {"a": 1}, "email": "q@b.co", "password": "x" * 9, "accept_terms": True},
                                  {"name": ["a"], "email": "q@b.co", "password": "x" * 9, "accept_terms": True},
                                  {"name": "Name Ok", "email": ["q"], "password": "x" * 9, "accept_terms": True},
                                  {"name": "Name Ok", "email": "q@b.co", "password": ["x"] * 9, "accept_terms": True},
                                  {"name": "Name Ok", "email": "q@b.co", "password": "x" * 9, "confirm": {"a": 1}, "accept_terms": True}] + NOT_OBJECTS)
def test_register_bad_types(body):
    r = _anon().post("/api/auth/register", json=body)
    assert 400 <= r.status_code < 500, (body, r.status_code)


CASES = [
    ("POST", "/api/health-profile/field", {"field": ["a"], "value": "x"}),
    ("POST", "/api/health-profile/field", {"field": {"a": 1}, "value": "x"}),
    ("POST", "/api/health-profile/field", {"field": "display_name", "value": ["a"]}),
    ("POST", "/api/health-profile/field", {"field": "height", "value": {"a": 1}}),
    ("POST", "/api/health-profile/field/delete", {"field": ["a"]}),
    ("POST", "/api/handoff/create", {"record_id": HUGE}),
    ("POST", "/api/handoff/create", {"record_id": INF}),
    ("POST", "/api/handoff/create", {"record_id": ["a"]}),
    ("POST", "/api/handoff/create", {"record_id": 1, "expires_minutes": ["a"]}),
    ("POST", "/api/handoff/create", {"record_id": 1, "expires_minutes": HUGE}),
    ("POST", "/api/meds", {"text": ["a"]}),
    ("POST", "/api/meds", {"text": {"a": 1}}),
    ("POST", "/api/analyze/redflag-next", {"symptoms": {"a": 1}}),
    ("POST", "/api/analyze/redflag-next", {"symptoms": ["chest pain"], "asked": True}),
    ("POST", "/api/analyze/redflag-next", {"symptoms": ["chest pain"], "asked": 5}),
    ("POST", "/api/analyze/redflag-next", {"symptoms": ["chest pain"], "age": True}),
    ("POST", "/api/analyze/redflag-next", {"symptoms": ["chest pain"], "age": ["a"]}),
    ("POST", "/api/analyze/redflag-next", {"symptoms": ["chest pain"], "age": {"a": 1}}),
    ("POST", "/api/followup/answer", {"record_id": INF, "outcome": "better"}),
    ("POST", "/api/followup/answer", {"record_id": HUGE, "outcome": "better"}),
    ("POST", "/api/followup/answer", {"record_id": ["a"], "outcome": "better"}),
    ("POST", "/api/smart-followup", {"record_id": INF, "outcome": "better"}),
    ("POST", "/api/smart-followup", {"record_id": HUGE, "outcome": "better"}),
    ("POST", "/api/relief-log", {"record_id": INF, "factor": "rest"}),
    ("POST", "/api/relief-log", {"record_id": HUGE, "factor": "rest"}),
    ("POST", "/api/relief-log", {"record_id": ["a"], "factor": "rest"}),
    ("GET", "/api/relief-log?record_id=" + "9" * 30, None),
    ("GET", "/api/relief-log?record_id=%C2%B2", None),
    ("GET", "/api/blood/history?member=" + "9" * 30, None),
    ("GET", "/api/blood/history?member=%C2%B2", None),
    ("GET", "/api/timeline?member=" + "9" * 30, None),
    ("GET", "/api/timeline?days=" + "9" * 30, None),
    ("GET", "/api/timeline?days=%C2%B2", None),
    ("GET", "/api/timeline?days=inf", None),
]
for _body in NOT_OBJECTS:
    for _path in ("/api/health-profile/field", "/api/health-profile/field/delete", "/api/handoff/create", "/api/meds",
                  "/api/analyze/redflag-next", "/api/followup/answer", "/api/smart-followup", "/api/relief-log"):
        CASES.append(("POST", _path, _body))


@pytest.mark.parametrize("method,path,body", CASES, ids=lambda v: str(v)[:60])
def test_malformed_values_never_500(method, path, body):
    c = _client()
    r = c.get(path) if method == "GET" else c.post(path, json=body)
    assert r.status_code < 500, (method, path, body, r.status_code, r.get_data(as_text=True)[:200])


def test_normal_requests_are_unchanged():
    c = _client()
    assert c.get("/api/timeline").status_code == 200
    assert c.get("/api/timeline?days=7&member=0").status_code == 200
    assert c.get("/api/blood/history").status_code == 200
    assert c.post("/api/health-profile/field", json={"field": "display_name", "value": "Sara Ali"}).get_json()["ok"] is True
    assert c.post("/api/meds", json={"text": "paracetamol ibuprofen"}).status_code == 200
    assert c.post("/api/analyze/redflag-next", json={"symptoms": ["chest pain"], "age": 40}).get_json()["ok"] is True
    assert _anon().post("/api/auth/login", json={"email": "nobody@example.test", "password": "wrong-password"}).status_code in (400, 401, 403)
