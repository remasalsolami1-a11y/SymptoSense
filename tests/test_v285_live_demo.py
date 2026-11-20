"""V285: public 3-minute demo runs the real engine, never saves, and works from embedded data."""
import json
import re

import pytest

import live_demo
import webapp

EXPECTED = {"mild": "low", "msa": "high", "dialect": "high", "negation": "low"}


@pytest.fixture()
def client():
    webapp.app.config["TESTING"] = True
    with webapp.app.test_client() as c:
        yield c


@pytest.mark.parametrize("sid, level", EXPECTED.items())
def test_each_scenario_reaches_the_intended_decision_through_the_engine(sid, level):
    r = live_demo.run(sid, "ar")
    assert r["decision"]["level"] == level
    assert r["saved"] is False and r["ai_used"] is False
    assert r["engine"] == live_demo.safety_engine.ENGINE_VERSION


def test_dialect_case_shows_the_typo_fix_and_the_same_rule_as_formal_arabic():
    msa, dialect = live_demo.run("msa"), live_demo.run("dialect")
    assert {c["typed"] for c in dialect["corrections"]} >= {"شفيفي"}
    concept_rules = lambda res: {r["rule_id"] for r in res["rules"] if r["rule_id"].startswith("concept_")}  # noqa: E731
    assert concept_rules(msa) == concept_rules(dialect) == {"concept_anaphylaxis"}
    for r in dialect["rules"]:
        for e in r["evidence"]:
            for q in e["quotes"]:
                assert dialect["text"][q["start"]:q["end"]] == q["text"]


def test_negation_case_lists_denied_concepts_and_fires_no_rule():
    r = live_demo.run("negation", "en")
    assert r["rules"] == [] and r["decision"]["layer"] == "triage"
    assert {c["concept"] for c in r["denied"]} >= {"chest_pain", "breathing"}


def test_unrelated_text_fires_nothing_in_denied_helper():
    assert live_demo.red_flag_concepts.denied_concepts("عندي زكام") == frozenset()


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_page_embeds_all_results_so_it_works_offline(client, lang):
    resp = client.get(f"/{lang}/live-demo")
    assert resp.status_code == 200
    page = resp.get_data(as_text=True)
    data = json.loads(re.search(r'<script[^>]*id="ldemo-data"[^>]*>(.*?)</script>', page, re.S).group(1))
    assert set(data["results"]) == set(EXPECTED)
    assert {k: v["decision"]["level"] for k, v in data["results"].items()} == EXPECTED
    assert 'role="tablist"' in page and page.count('role="tab"') == 4
    assert "997" in page  # safety disclaimer present


def test_api_runs_live_and_rejects_unknown_ids(client):
    r = client.get("/api/demo/run?id=dialect&lang=ar")
    assert r.status_code == 200 and "no-store" in r.headers["Cache-Control"]
    assert r.get_json()["decision"]["level"] == "high"
    assert client.get("/api/demo/run?id=../../etc").status_code == 404


def test_demo_never_writes_an_analysis_record(client):
    import db
    conn = db._conn(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM records"); before = c.fetchone()[0]; conn.close()
    for sid in EXPECTED:
        client.get(f"/api/demo/run?id={sid}")
    conn = db._conn(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM records"); after = c.fetchone()[0]; conn.close()
    assert after == before


def test_embedded_json_cannot_break_out_of_its_script_tag():
    _t, body, _css = live_demo.render_page("en")
    blob = body.split('id="ldemo-data">', 1)[1].split("</script>", 1)[0]
    assert "</" not in blob


def test_page_does_not_show_the_internal_engine_id():
    """V290: the internal id (deterministic-red-flag-…) stays in the JSON for checks, not on the page."""
    import safety_engine
    for lang in ("ar", "en"):
        page = "".join(live_demo.render_page(lang)).replace('"engine": "%s"' % safety_engine.ENGINE_VERSION, "")
        assert safety_engine.ENGINE_VERSION not in page  # only inside the embedded data, never as page text
    from pathlib import Path
    src = (Path(live_demo.__file__)).read_text(encoding="utf-8")
    assert "[r.engine]" not in src and "قواعد أمان ثابتة" in src
