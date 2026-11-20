"""V292: the knowledge graph is built only from the engine's own data and shows one item at a time."""
import blood_test
import knowledge_graph as kg
import medical_knowledge as mk
import webapp


def test_every_condition_symptom_edge_exists_in_the_knowledge_base():
    g = kg.graph()
    by = {d["slug"]: d for d in mk.DISEASES}
    cs = [e for e in g["edges"] if e["a"].startswith("condition:") and e["b"].startswith("symptom:")]
    assert len(cs) > 700
    for e in cs:
        assert e["b"].split(":", 1)[1] in by[e["a"].split(":", 1)[1]]["symptoms"]
    labs = [e for e in g["edges"] if e["a"].startswith("lab:") and e["b"].startswith("symptom:")]
    assert labs and all(e["a"].split(":", 1)[1] in blood_test.CBC_ASSOCIATED_SYMPTOMS for e in labs)
    st = kg.stats()
    assert st["by_type"]["condition"] == len(mk.DISEASES) and st["by_type"]["source"] > 100


def test_source_ids_are_stable_across_processes():
    ids = sorted(k for k in kg.graph()["nodes"] if k.startswith("source:"))
    kg._GRAPH = None
    assert ids == sorted(k for k in kg.graph()["nodes"] if k.startswith("source:"))


def test_neighbourhood_is_limited_and_explains_each_link():
    n = kg.neighborhood("symptom:dizziness", "ar")
    assert n["center"]["label"] == "دوخة" and 0 < len(n["links"]) <= 24
    assert {"condition", "lab"} <= set(n["by_type"])
    assert all(l["relation"] for l in n["links"])
    assert kg.neighborhood("nope:x") is None
    assert kg.search("هيموغ", "ar")[0]["id"] == "lab:hgb"


def test_page_and_api_work_in_both_languages_and_are_honest():
    c = webapp.app.test_client()
    ar = c.get("/ar/knowledge-graph").get_data(as_text=True)
    assert "شبكة المعرفة الصحية" in ar and "وليست نموذج ذكاء اصطناعي متعلّم" in ar and "/static/js/knowledge-graph.js" in ar
    assert "not a learned AI model" in c.get("/en/knowledge-graph").get_data(as_text=True)
    j = c.get("/api/knowledge-graph?node=lab:hgb&lang=en").get_json()
    assert j["ok"] and j["center"]["label"] == "Hemoglobin"
    assert c.get("/api/knowledge-graph?node=bad").status_code == 404
    assert 'href="/knowledge-graph"' in c.get("/ar/how-we-work").get_data(as_text=True)
