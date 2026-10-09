"""Layers must agree on emergencies, and decisions are logged anonymously."""
import json
import os
import sqlite3
import tempfile
from pathlib import Path

_TMP = tempfile.TemporaryDirectory(prefix="ss-decision-")
os.environ.pop("DATABASE_URL", None)
os.environ["DB_PATH"] = str(Path(_TMP.name) / "d.sqlite3")
os.environ.setdefault("WEB_SECRET", "decision-log-secret-that-is-longer-than-32-characters")

import analysis_core  # noqa: E402
import decision_log  # noqa: E402
import safety_engine  # noqa: E402

GOLD = [c for c in json.loads((Path(__file__).parent / "runtime_data/emergency_golden.json").read_text(encoding="utf-8")) if c["expect_emergency"]]


def test_all_three_layers_agree_on_every_golden_emergency():
    disagreements = []
    for c in GOLD:
        patient = {"symptoms": [], "notes": c["text"], "severity": 3, "age": 40, "gender": "m"}
        engine = safety_engine.evaluate(patient, "ar")["emergency"]
        flags = bool(analysis_core.detect_red_flags([], c["text"], "ar"))
        full = analysis_core.run_analysis(dict(patient), "ar")
        full_high = full.get("urgency") == "high" or bool(full.get("emergency"))
        if not (engine and flags and full_high):
            disagreements.append((c["id"], engine, flags, full.get("urgency")))
    assert not disagreements, disagreements[:10]


def test_decision_log_is_anonymous_and_aggregates():
    assert decision_log.record("emergency", ["severe_breathing", "bad rule!"], "ar", "safety_check")
    assert decision_log.record("low", [], "en", "analyze")
    con = sqlite3.connect(os.environ["DB_PATH"])
    cols = [r[1] for r in con.execute("PRAGMA table_info(ss_safety_decisions)")]
    rows = con.execute("SELECT ts, level, rule_ids, lang, source FROM ss_safety_decisions").fetchall()
    con.close()
    assert cols == ["ts", "level", "rule_ids", "lang", "source"]  # no text / user / ip columns
    assert rows[0][2] == "severe_breathing"  # invalid rule names dropped
    assert rows[0][0].endswith(":00:00Z")  # hour bucket only
    s = decision_log.summary()
    assert s["total"] == 2 and s["by_level"]["emergency"] == 1
    assert ("severe_breathing", 1) in s["top_rules"]
