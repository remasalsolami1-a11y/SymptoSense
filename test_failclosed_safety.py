"""V253: safety checks must fail closed, never silently return "no red flag"."""
import re
from pathlib import Path

import pytest

import analysis_core
import ops_metrics
import webapp

ROOT = Path(__file__).resolve().parent
SAFETY_FILES = ["safety_engine.py", "emergency_lexicon.py", "context_triage.py", "redflag_screen.py", "clinical_text.py", "search_fidelity.py"]


def test_detect_red_flags_raises_and_counts_when_the_engine_crashes(monkeypatch):
    import safety_engine

    def boom(*a, **k):
        raise ValueError("engine bug")
    monkeypatch.setattr(safety_engine, "evaluate", boom)
    ops_metrics.reset()
    with pytest.raises(analysis_core.SafetyCheckError):
        analysis_core.detect_red_flags(["ألم صدر"], "", "ar")
    snap = ops_metrics.snapshot()
    assert snap["counters"]["error:safety_check_failure"] == 1 and snap["recent_errors"][-1]["detail"] == "ValueError"


def test_analyze_endpoint_returns_error_not_a_reassuring_result_when_safety_crashes(monkeypatch):
    import safety_engine
    monkeypatch.setattr(safety_engine, "evaluate", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    c = webapp.app.test_client()
    c.environ_base["REMOTE_ADDR"] = "192.0.2.51"
    assert c.post("/api/consent/preferences", json={"service_usage": True, "analytics_research": False}).status_code == 200
    r = c.post("/api/analyze", json={"age": 30, "gender": "male", "symptoms": ["ألم صدر"], "duration": "يوم", "severity": 2, "notes": "", "lang": "ar"})
    assert r.status_code >= 500
    assert not (r.get_json() or {}).get("ok")


def test_no_silent_swallow_in_safety_modules():
    """`except Exception:` followed directly by pass/return/continue (without logging) is forbidden here."""
    bad = []
    for name in SAFETY_FILES:
        lines = (ROOT / name).read_text(encoding="utf8").split("\n")
        for i, line in enumerate(lines):
            if re.match(r"\s*except( Exception)?\s*:", line):
                nxt = " ".join(x.strip() for x in lines[i + 1:i + 3])
                if re.match(r"(pass|continue|return\b)", nxt) and "log" not in nxt:
                    bad.append(f"{name}:{i + 1}")
    # Known, reviewed non-safety-critical fallbacks (normalisation helpers returning "unknown"/"no match").
    allowed = {"redflag_screen.py:125"}
    assert [b for b in bad if b not in allowed] == []


def test_safety_engine_and_lexicon_have_no_broad_except_at_all():
    for name in ("safety_engine.py", "emergency_lexicon.py"):
        assert "except Exception" not in (ROOT / name).read_text(encoding="utf8"), name


def test_ops_metrics_record_routes_without_query_strings():
    ops_metrics.reset()
    c = webapp.app.test_client()
    c.get("/health?secret=abc")
    c.get("/api/search?q=%D8%B5%D8%AF%D8%A7%D8%B9&lang=ar")
    snap = ops_metrics.snapshot()
    names = [r["route"] for r in snap["routes"]]
    assert all("secret" not in n and "q=" not in n for n in names)
    assert snap["requests_total"] >= 1
