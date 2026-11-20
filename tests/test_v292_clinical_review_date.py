"""V292: a clinical review comes only from a named clinician's sign-off, never from editing a record."""
import copy
import json
from datetime import date, timedelta

import clinical_signoff as cs
import medical_knowledge as mk
import signoff_cli


def test_editing_a_record_is_not_a_clinical_review():
    r = mk.periodic_review_status()
    diseases = [x for x in r["all"] if x["entity_type"] == "disease"]
    assert diseases and all(x["review_basis"] == "clinician_signoff" for x in diseases)
    pending = not cs.is_reviewed(cs.area("knowledge_base"))
    if pending:
        assert all(x["review_status"] != "verified" and x["reason"] == "no_clinical_review" for x in diseases)
    assert all("last_edited" in x for x in diseases)
    srcs = [x for x in r["all"] if x["entity_type"] == "source"]
    assert srcs and all(x["review_basis"] == "source_verification" for x in srcs)


def test_signoff_makes_content_reviewed_until_the_interval_ends(monkeypatch):
    data = copy.deepcopy(cs.load(cs.PATH))
    today = date.today()
    data["areas"]["knowledge_base"].update(status="reviewed", reviewer="Dr. Test", credentials="MD", date=today.isoformat())
    monkeypatch.setattr(cs, "load", lambda path=None: data)
    r = mk.periodic_review_status()
    diseases = [x for x in r["all"] if x["entity_type"] == "disease" and x["source_count"]]
    assert diseases and all(x["review_status"] == "verified" for x in diseases)
    old = (today - timedelta(days=400)).isoformat()
    data["areas"]["knowledge_base"]["date"] = old
    assert not cs.is_current(data["areas"]["knowledge_base"])
    lapsed = cs.status_for("library", "x")
    assert "expired" not in lapsed or lapsed["reviewed"] is False


def test_every_area_has_an_interval_and_a_history(tmp_path, monkeypatch):
    data = cs.load(cs.PATH)
    assert "knowledge_base" in data["areas"] and cs.validate(data) == []
    for aid, a in data["areas"].items():
        assert a["review_every_days"] == (180 if aid in ("emergency_rules", "redflag_screens") else 365)
        assert isinstance(a["history"], list)
    copy_path = tmp_path / "signoff.json"
    copy_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(cs, "PATH", copy_path)
    assert signoff_cli.main(["approve", "lab_cards", "--reviewer", "Dr. A", "--credentials", "MD", "--date", "2026-11-01"]) == 0
    assert signoff_cli.main(["revoke", "lab_cards"]) == 0
    hist = json.loads(copy_path.read_text(encoding="utf-8"))["areas"]["lab_cards"]["history"]
    assert [h["action"] for h in hist] == ["approve", "revoke"] and hist[0]["reviewer"] == "Dr. A" and hist[0]["recorded_at"]


def test_follow_up_question_says_which_possibilities_it_separates():
    r = mk.differential_question(["صداع", "غثيان"], lang="ar")
    assert not r["done"] and r["question_reason"].startswith("نسأل عن «%s»" % r["symptom_name"])
    assert "«" in r["question_reason"].split("لأنه", 1)[1]
    from pathlib import Path
    js = (Path(__file__).resolve().parents[1] / "static" / "js" / "chat" / "followup.js").read_text(encoding="utf-8")
    assert "stepNote(" in js and "d.question_reason" in js


def test_why_we_ask_is_shown_inside_the_question_card():
    # focusStepQuestion clears the chat body, so the note must be added after it, into the card.
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "static" / "js" / "chat"
    core = (root / "chat-core.js").read_text(encoding="utf-8")
    assert "function stepNote(stepText, whyText)" in core and "ss-why-q" in core
    for name, focus in (("followup.js", "focusStepQuestion('🩺 ' + d.question);"), ("red-flags.js", "focusStepQuestion('⚠️ ' + sc.question);")):
        js = (root / name).read_text(encoding="utf-8")
        assert js.index(focus) < js.index("stepNote(") and "ss-why-q" not in js
