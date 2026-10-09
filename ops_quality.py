"""Admin quality centre + production readiness checks (V253).

* ``production_checks`` - what ``/health`` cannot prove: persistent database, real secret,
  HTTPS cookies. ``/ready`` returns 503 when a check fails inside a production runtime.
* ``quality_snapshot`` - privacy-safe numbers an admin can act on: 5xx rate, slowest routes,
  safety-check failures, analyses that were insufficient / low-confidence, searches that fell
  back to the generic shell (content gaps), decision-level mix, follow-up outcomes and the
  reasons users gave for unhelpful answers. Counters are per worker process and reset on restart.
"""
from __future__ import annotations

import os

import db
import ops_metrics


def production_checks(is_production, web_secret_configured, secure_cookie):
    """Return (ok, checks). Outside production every check is informational."""
    allow = os.environ.get("SYMPTOSENSE_ALLOW_EPHEMERAL", "") == "1"
    checks = [
        {"id": "persistent_database", "ok": bool(db.USE_POSTGRES) or allow,
         "detail": "postgres" if db.USE_POSTGRES else "sqlite (data is lost on redeploy unless a volume is mounted)"},
        {"id": "web_secret", "ok": bool(web_secret_configured), "detail": "configured" if web_secret_configured else "ephemeral - sessions reset on restart"},
        {"id": "secure_cookies", "ok": bool(secure_cookie), "detail": "secure" if secure_cookie else "not secure"},
    ]
    ok = all(c["ok"] for c in checks) if is_production else True
    return ok, checks


def clinical_gate_state():
    """Pending sign-off areas and whether the production build bypassed the gate (marker written by the Dockerfile)."""
    import clinical_signoff
    from pathlib import Path
    areas = clinical_signoff.load(clinical_signoff.PATH)["areas"]
    pending = sorted(k for k, a in areas.items() if not clinical_signoff.is_reviewed(a))
    marker = Path(__file__).with_name(".clinical_bypass")
    return {"pending": pending, "bypass_active": marker.exists(),
            "banner": "Clinical sign-off bypass is active" if marker.exists() and pending else ""}


def quality_snapshot():
    snap = ops_metrics.snapshot()
    c = snap["counters"]
    done = c.get("analysis_completed", 0)
    weak = c.get("analysis_insufficient", 0) + c.get("analysis_low_confidence", 0)
    out = {
        "service": {"uptime_s": snap["uptime_s"], "requests": snap["requests_total"], "responses_5xx": snap["responses_5xx"],
                    "error_rate_5xx": snap["error_rate_5xx"], "slowest_routes": snap["routes"][:8], "recent_errors": snap["recent_errors"]},
        "safety": {"check_failures": c.get("error:safety_check_failure", 0), "emergency_notices": c.get("safety_notice_shown", 0)},
        "analysis": {"completed": done, "insufficient": c.get("analysis_insufficient", 0), "low_confidence": c.get("analysis_low_confidence", 0),
                     "weak_rate": round(weak / done, 3) if done else 0.0, "with_missing_info": c.get("analysis_with_missing_info", 0),
                     "decisions": {k[len("decision_"):]: v for k, v in c.items() if k.startswith("decision_")}},
        "search": {"content_gaps": c.get("search_content_gap", 0)},
        "side_effects": {"audit_log_failures_total": c.get("audit_log_failures_total", 0),
                         "best_effort_failures_total": c.get("best_effort_failures_total", 0)},
        "clinical_signoff": clinical_gate_state(),
        "scope_note": "Per-process counters; they reset on restart. Query text and symptoms are never stored here.",
    }
    try:
        out["followups"] = db.followup_stats()
    except (db.DB_ERRORS + (ValueError, TypeError)) as exc:
        ops_metrics.event_error("quality_followup_stats", type(exc).__name__)
        out["followups"] = {}
    try:
        out["feedback_reasons"] = db.feedback_reason_stats()
    except (db.DB_ERRORS + (ValueError, TypeError)) as exc:
        ops_metrics.event_error("quality_feedback_stats", type(exc).__name__)
        out["feedback_reasons"] = []
    try:
        out["assistant_feedback"] = db.assistant_feedback_stats()
    except (db.DB_ERRORS + (ValueError, TypeError)) as exc:
        ops_metrics.event_error("quality_assistant_stats", type(exc).__name__)
        out["assistant_feedback"] = {}
    return out
