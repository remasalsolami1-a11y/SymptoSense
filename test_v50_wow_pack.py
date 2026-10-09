import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _fake_page(title, body, extra_css=""):
    return f"<title>{title}</title><style>{extra_css}</style>{body}"


def test_v50_routes_and_nav_links_exist():
    src = source_bundle.webapp_text()
    assert '@app.route("/command-center")' in src
    assert '@app.route("/health-story")' in src
    assert '@app.route("/admin/competition-dashboard")' in src
    # Legacy routes remain as compatibility aliases, while navigation uses the
    # canonical consolidated destinations.
    assert 'href="/health-command-center" role="menuitem"' in src
    assert 'href="/health-record" role="menuitem"' in src
    assert 'href="/competition-dashboard">__COMP_LINK__' not in src
    assert '/admin/competition-dashboard' in (ROOT / 'dashboard.py').read_text(encoding='utf-8')


def test_command_center_renders_real_data(monkeypatch):
    import v50_wow

    monkeypatch.setattr(v50_wow.db, "get_ss_user", lambda uid: {"name": "Demo User"})
    monkeypatch.setattr(v50_wow.db, "load_health_profile", lambda uid: {"display_name": "Demo User", "dob": "2000-01-01", "allergies": "None"})
    monkeypatch.setattr(v50_wow.advanced_features, "user_analysis_rows", lambda uid, limit=50: [{"id": 7, "timestamp": "2026-09-18T10:00:00+00:00", "symptoms": ["Headache"], "urgency": "low", "result": {"risk_level": "low"}}])
    monkeypatch.setattr(v50_wow.db, "get_blood_tests", lambda uid, limit=5: [{"id": 2, "timestamp": "2026-09-17T10:00:00+00:00", "data": {}}])
    monkeypatch.setattr(v50_wow.db, "list_med_plans", lambda uid, active_only=True: [{"id": 1, "med_name": "DemoMed"}])
    monkeypatch.setattr(v50_wow.db, "med_plans_today", lambda uid: [{"med_name": "DemoMed", "times": ["20:00"], "status": {"20:00": ""}}])
    monkeypatch.setattr(v50_wow.db, "get_latest_followup", lambda uid: {"outcome": "improved"})

    html = v50_wow.render_command_center(page=_fake_page, lang="en", account_uid="1", data_uid="account-1")
    assert "HEALTH COMMAND CENTER" in html
    assert "Demo User" in html
    assert "Headache" in html
    assert "DemoMed" in html
    assert "/health-story" in html


def test_health_story_timeline_filters_and_private_events(monkeypatch):
    import v50_wow

    monkeypatch.setattr(v50_wow.db, "member_timeline", lambda uid, mid, days=3650: [
        {"date": "2026-09-18", "type": "analysis", "title": "تحليل أعراض", "en_title": "Symptom analysis", "detail": "Headache", "id": 9},
        {"date": "2026-09-17", "type": "blood", "title": "فحص CBC", "en_title": "CBC test", "detail": "", "id": 3},
    ])
    monkeypatch.setattr(v50_wow.db, "get_followups", lambda uid, limit=200: [{"timestamp": "2026-09-19T00:00:00+00:00", "record_id": 9, "outcome": "improved"}])
    monkeypatch.setattr(v50_wow.advanced_features, "user_analysis_rows", lambda uid, limit=200: [{"symptoms": ["Headache", "Nausea"]}])

    html = v50_wow.render_health_story(page=_fake_page, lang="en", uid="u1")
    assert "My Health Story" in html
    assert 'data-type="analysis"' in html
    assert 'data-type="blood"' in html
    assert 'data-type="followup"' in html
    assert "Headache" in html
    assert "hs-filter" in html


def test_competition_dashboard_counts_from_project(monkeypatch):
    import v50_wow

    monkeypatch.setattr(v50_wow.medical_knowledge, "init_schema", lambda: None)
    def fake_list(kind, *args, **kwargs):
        return {"symptoms": [1, 2, 3], "diseases": [1, 2], "sources": [1, 2, 3, 4]}[kind]
    monkeypatch.setattr(v50_wow.medical_knowledge, "list_entities", fake_list)
    html = v50_wow.render_competition_dashboard(page=_fake_page, lang="en")
    assert "Competition Dashboard" in html
    assert 'data-count="3"' in html
    assert 'data-count="2"' in html
    assert 'data-count="4"' in html
    assert "Interactive Body Map" in html
    assert "Safety Matrix" in html
    assert "/demo" in html


def test_db_followups_helper_and_timeline_id_are_scoped():
    import db
    src = (ROOT / "db.py").read_text(encoding="utf-8")
    import inspect
    assert src.count("def get_followups(") == 1, "get_followups must exist exactly once (a second definition silently replaces the first)"
    assert src.count("def save_followup(") == 1
    assert "limit" in inspect.signature(db.get_followups).parameters
    assert "WHERE user_hash={PH}" in src
    assert '"id": rid' in src
