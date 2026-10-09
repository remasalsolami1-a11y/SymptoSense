"""V252: clinical sign-off registry - honest labels, no overstated review, every card mapped to an area."""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

import clinical_signoff as cs
import health_search
import medical_knowledge
import redflag_screen
import webapp

ROOT = Path(__file__).resolve().parent


def test_registry_file_is_valid_and_honest():
    data = cs.load(cs.PATH)
    assert not cs.validate(data)
    assert {"emergency_rules", "redflag_screens", "search_new_v251", "search_base", "lab_cards", "library_core"} <= set(data["areas"])


def test_reviewed_requires_reviewer_credentials_and_date():
    data = copy.deepcopy(cs.load(cs.PATH))
    data["areas"]["search_base"].update(status="reviewed", reviewer="Dr X", credentials="", date="2026-10-20")
    assert any("missing credentials" in p for p in cs.validate(data))
    data["areas"]["search_base"].update(credentials="MD", reviewer=None)
    assert any("missing reviewer" in p for p in cs.validate(data))
    data["areas"]["search_base"].update(status="pending", reviewer="Dr X", credentials="MD")
    assert any("while status is pending" in p for p in cs.validate(data))


def test_status_label_never_claims_review_without_details(monkeypatch):
    fake = {"areas": {"search_base": {"title_ar": "a", "title_en": "a", "status": "reviewed", "reviewer": "Dr X", "credentials": "", "date": "2026-10-20"}}}
    monkeypatch.setattr(cs, "load", lambda path=None: fake)
    assert cs.status_for("search", "headache", "en")["reviewed"] is False
    fake["areas"]["search_base"]["credentials"] = "MD"
    st = cs.status_for("search", "headache", "en")
    assert st["reviewed"] is True and "Dr X" in st["label"] and "2026-10-20" in st["label"]


def test_every_content_key_maps_to_a_registered_area():
    areas = set(cs.load(cs.PATH)["areas"])
    keys = [("search", k) for k in health_search.SEARCH_KB] + [("search", "lab_ast")] + [("library", s[0]) for s in medical_knowledge.SYMPTOMS]
    keys += [("redflag", s["id"]) for s in redflag_screen.SCREENS] + [("emergency", "x")]
    for kind, key in keys:
        assert cs.area_for(kind, key) in areas, (kind, key)
    assert cs.area_for("search", "allergy") == "search_new_v251"
    assert cs.area_for("search", "headache") == "search_base"
    assert cs.area_for("search", "lab_crp") == "lab_cards"


def test_search_results_carry_a_review_status_and_endpoint_lists_areas():
    c = webapp.app.test_client()
    c.environ_base["REMOTE_ADDR"] = "192.0.2.99"
    assert c.post("/api/consent/preferences", json={"service_usage": True, "analytics_research": False}).status_code == 200
    r = c.get("/api/search", query_string={"q": "صداع", "lang": "ar"}).get_json()["result"]
    assert r["review"]["reviewed"] is False and "لم يُراجع" in r["review"]["label"]
    lab = c.get("/api/search", query_string={"q": "AST", "lang": "en"}).get_json()["result"]
    assert lab["review"]["area"] == "lab_cards"
    s = c.get("/api/clinical-signoff").get_json()
    assert s["ok"] and s["total"] == 9 and s["reviewed"] == 0


def test_badge_can_be_hidden_by_operator(monkeypatch):
    monkeypatch.setenv("SYMPTOSENSE_SHOW_REVIEW_STATUS", "0")
    assert "review" not in cs.annotate({"key": "headache"}, "ar")


def test_cli_check_passes_and_strict_blocks_while_pending():
    base = [sys.executable, str(ROOT / "tools" / "signoff.py"), "check"]
    assert subprocess.run(base, capture_output=True).returncode == 0
    strict = subprocess.run(base + ["--strict"], capture_output=True, text=True)
    assert strict.returncode == (0 if all(cs.is_reviewed(a) for a in cs.load(cs.PATH)["areas"].values()) else 1)


def test_cli_approve_validates_input(tmp_path, monkeypatch):
    sys.path.insert(0, str(ROOT / "tools"))
    import signoff
    monkeypatch.setattr(cs, "PATH", tmp_path / "s.json")
    (tmp_path / "s.json").write_text(json.dumps(cs.load(ROOT / "clinical_signoff.json")), encoding="utf-8")
    assert signoff.main(["approve", "lab_cards", "--reviewer", "Dr X", "--credentials", "MD", "--date", "20-10-2026"]) == 2
    assert signoff.main(["approve", "nope", "--reviewer", "Dr X", "--credentials", "MD", "--date", "2026-10-20"]) == 2
    assert signoff.main(["approve", "lab_cards", "--reviewer", "Dr X", "--credentials", "MD", "--date", "2026-10-20"]) == 0
    assert cs.is_reviewed(json.loads((tmp_path / "s.json").read_text(encoding="utf-8"))["areas"]["lab_cards"])
    assert signoff.main(["revoke", "lab_cards"]) == 0
    assert not cs.is_reviewed(json.loads((tmp_path / "s.json").read_text(encoding="utf-8"))["areas"]["lab_cards"])
